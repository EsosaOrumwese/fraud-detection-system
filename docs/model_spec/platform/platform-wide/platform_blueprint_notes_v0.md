
# Top view of the platform
Here’s the “whole picture from above” (still brainstormy, but *designer-authoritative enough* to prevent drift).

---

## 1) The platform picture (end-to-end flow)

### A. World/run orchestration (offline “world build” loop)

```
RunRequest
  -> Scenario Runner (SR)
      -> (invoke OR reuse) Data Engine
      -> verify required PASS gates
      -> write SR ledger (run_plan/run_record/run_status)
      -> publish RunReadySignal + run_facts_view (pins + refs)
```

SR is explicitly “conductor + ledger” and the system-of-record for run identity, readiness, and the downstream join surface (`run_facts_view`).
Data Engine is a black box that promises deterministic, immutable outputs per partition identity and exposes output discovery + gates via its interface pack. 

**Key join artifact:** `run_facts_view` is literally the “bridge” that points downstream to engine evidence + authoritative outputs by ref.

---

### B. Event intake → durable log (trust boundary + distribution)

```
Producers (engine streams, DF outputs, AL outcomes, case/label emissions)
  -> Ingestion Gate (IG)  [admit | quarantine | duplicate] + receipts
  -> Event Bus (EB)       durable append + replay (at-least-once)
```

IG is the trust boundary: admit/quarantine/duplicate with receipts + evidence pointers, and it ensures joinability to the correct run/world.
EB is the distribution + durability plane: append immutably, deliver at-least-once, replay within retention; it does **not** validate/transform.

---

### C. Real-time decision loop (hot path)

```
EB admitted_events
  -> Identity & Entity Graph (IEG)   run/world-scoped projection + graph_version
  -> Online Feature Plane (OFP)      feature snapshots + provenance + snapshot hash
  -> Degrade Ladder (DL)             degrade_mode + capabilities mask (deterministic)
  -> Decision Fabric (DF)            decision + action intents + provenance
  -> Actions Layer (AL)              effectively-once execution + immutable outcomes
  -> Decision Log/Audit (DLA)        append-only audit record (+ optional outcomes)
```

* IEG: read-mostly projection, run/world-scoped via ContextPins, envelope-driven updates, authoritative for its own projection + `graph_version`.
* OFP: real-time context compiler; serves deterministic feature snapshots with `feature_snapshot_hash` + freshness + input_basis provenance.
* DL: explicit degrade decision + mask (no silent coupling), deterministic + hysteresis + fail-closed.
* DF: decisioning core; must obey DL mask; emits DecisionResponse + idempotent ActionIntents + provenance.
* AL: executes ActionIntents effectively-once via `(ContextPins, idempotency_key)` and emits immutable ActionOutcome history.
* DLA: immutable “flight recorder”; append-only AuditDecisionRecord, idempotent ingest, quarantine on incomplete provenance, by-ref + hashes posture.

---

### D. Case + labels (human truth loop)

```
DF/AL/DLA pointers
  -> Case Mgmt / Workbench (cases + immutable timelines)
      -> emits authoritative investigator assertions
          -> Label Store (append-only label timelines + as-of queries)
```

Case Mgmt is the human-in-the-loop control surface with immutable timelines; it emits LabelAssertions into Label Store (Label Store is truth).
Label Store is the lagged truth plane with **effective_time vs observed_time** and leakage-safe “as-of” reads.

---

### E. Learning + evolution (offline model loop)

```
EB history + DLA exports + Label Store
  -> Offline Feature Plane shadow (rebuild snapshots/datasets deterministically + parity)
  -> Model Factory (training runs + eval evidence + gate receipt + bundle)
  -> Model/Policy Registry (bundle lifecycle + deterministic “active bundle” resolution)
  -> DF uses Registry to resolve what policy/model is active
```

* Offline feature shadow: deterministic reconstruction + parity evidence vs online snapshot hash. 
* Model Factory: reproducible training runs (`train_run_id`), leakage discipline, bundles + PASS/FAIL gate receipt, publishes to registry.
* Registry: deployable truth; immutable bundles + lifecycle + deterministic “active bundle” resolution per scope; evidence-based promotion (PASS required).

---

### F. Meta planes (substrate + safety)

* **Run/Operate plane:** orchestration + artifact store + bus ops + config/secrets + deployment + admin surfaces; must not break determinism/immutability and must keep changes auditable.
* **Observability/Governance:** correlation standards + golden signals + corridor checks + unified lineage view + change control governance events.

---

## 2) “Truth ownership” (system-of-record map)

This is the drift-killer: **if two components both claim the same truth, you get chaos**.

* **Data Engine** → truth for *world outputs* (surfaces/streams) + engine gates/receipts; deterministic immutability per partition identity. 
* **Scenario Runner** → truth for *run identity + readiness + join surface* (`run_facts_view`) + run lifecycle status + run intent/outcome ledger.
* **Ingestion Gate** → truth for *admission/quarantine/duplicate outcomes* + receipts + canonical admitted record.
* **Event Bus** → truth for *stream position + replay semantics within retention* (partition/offset/checkpoints), not payload meaning.
* **IEG** → truth for *entity/edge projection + graph_version* (run/world-scoped), not world truth.
* **OFP** → truth for *served feature snapshot + provenance + snapshot hash*.
* **DL** → truth for *degrade_mode + capabilities mask + provenance*.
* **DF** → truth for *decision response + action intents + decision provenance*.
* **AL** → truth for *action outcomes + attempt history* (effectively-once semantics).
* **DLA** → truth for *canonical audit decision record* (append-only + supersedes chains) + audit quarantine.
* **Case Mgmt** → truth for *cases + immutable timelines*; labels are emitted to Label Store. 
* **Label Store** → truth for *labels as append-only timelines + as-of queries* (effective vs observed time).
* **Model Factory** → truth for *training runs + evaluation evidence + produced bundles + gate receipts*.
* **Model/Policy Registry** → truth for *bundle lifecycle + which bundle is ACTIVE per scope*.

---

## 3) The “connection points” you must keep pinned (to prevent drift)

These are the small number of cross-component facts that everything snaps to:

1. **ContextPins everywhere**
   Across the hot path, you’re repeatedly pinning the same run/world scope (`scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`). Rails explicitly calls this out, and IEG/OFP/DLA rely on it.

2. **“No PASS → no read” is platform law**
   Engine produces PASS artifacts; SR must not declare READY without required PASS evidence; downstream must gate.

3. **Run join surface is SR’s `run_facts_view` + READY signal pointer**
   Downstream should start from READY → `run_facts_view` → ArtifactRefs (no guessing, no scanning “latest”).

4. **Event boundary shape is canonical envelope; payload contracts evolve separately**
   Your canonical envelope requires at least `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` and carries optional pins/trace fields.
   **Drift warning to pin soon:** IG docs talk in `event_time`/`ingest_time` terms; canonical envelope currently uses `ts_utc`/`emitted_at_utc`. That naming mismatch is exactly the kind of cross-boundary drift that will bite later.

5. **Envelope-driven updates for IEG (and OFP parity) require `observed_identifiers[]`**
   IEG v0 wants to stay envelope-driven and not parse payloads.
   Your canonical-event pack explicitly tightens v1 so `transaction_event` requires `observed_identifiers[]` at the envelope level to support that. 

6. **Watermark basis is the shared “replay determinism” hook**
   IEG `graph_version` is defined as a monotonic token based on per-partition `next_offset_to_apply` watermark vector; OFP provenance similarly carries an input_basis watermark vector.

7. **Degrade is explicit, enforced, and recorded**
   DL outputs mode + mask; DF must obey; DLA must record; no silent coupling.

8. **Idempotency is end-to-end, but “key recipes” live locally**

* IG: dedupe key + receipts (admit/quarantine/duplicate).
* AL: `(ContextPins, idempotency_key)` uniqueness; duplicates re-emit canonical outcome.
* DLA: `(ContextPins, audit_record_id)` idempotent ingest. 

---

## 4) Minimal “holes” (things not fully pinned yet, but required to avoid drift)

Not new docs — just missing **definitions** we’ll want to pin at the platform-map level:

1. **FeatureGroup version authority (where OFP/Shadow/MF get “what features exist + versions + TTL”)**
   OFP and OFS-Shadow both depend on a pinned feature definition registry/version set.
   Right now it’s referenced as an input; the platform map should say *who is authoritative for it* (even if it’s “config pack in artifact store”).

2. **DatasetManifest semantics for offline training inputs**
   Model Factory consumes dataset manifests/refs and pins digests/windows/join keys for reproducibility + leakage control.
   Offline feature shadow mentions emitting dataset manifests/refs — but the shared meaning of “DatasetManifest” needs to be pinned once so MF doesn’t drift from OFS.

3. **Event archive vs EB retention boundary**
   OFS-Shadow explicitly allows replay from EB retention *or from an archive*; EB retention itself is a pinned concept but implementation/open questions remain.
   You don’t need to solve storage now, but the big-picture map should state whether “training horizon > retention” is in-scope for v0.

---

# Component Network within Platform

## Global primitives we pin now (v0 designer anchor)

**GP0.1 — ContextPins (identity) + Seed taxonomy**
We treat **ContextPins** as the platform’s canonical join pins: `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`; if an internal record/event claims run-joinability, it carries the full set.
`seed` is a **separate** “run realisation” field: required at engine invocation and required on any RNG-derived/run-scoped outputs/events, but not necessarily required on every envelope-shaped record.

**GP0.2 — Canonical Event Envelope is the bus boundary**
Anything treated as “admitted traffic” is a **CanonicalEventEnvelope** with required `{event_id, event_type, ts_utc, manifest_fingerprint}` and optional pins (`parameter_hash`, `seed`, `scenario_id`, `run_id`) plus trace/provenance fields (`trace_id`, `span_id`, `producer`, `schema_version`, `payload`).

**GP0.3 — Time semantics never collapse**
We keep four times conceptually distinct:

* **Domain event time** = `ts_utc` (this is what downstream “means”).
* **Producer emission time** = `emitted_at_utc` (optional; producer clock).
* **Ingestion time** = IG processing/commit time (lives in IG stamps/receipts; must not overwrite domain time).
* **Apply time** = consumer/application time (e.g., offsets/watermarks; not written back into the event).

**GP0.4 — “By-ref” is the default truth transport**
Across planes, we pass **refs/locators** (and optional digests), not copied payloads: `EngineOutputLocator` / ArtifactRef-like pointers are the join mechanism, and “scan latest and hope” is disallowed for anything that must be reproducible.

**GP0.5 — Validation gating is a platform law**
“No PASS → no read” is non-negotiable: gated datasets/streams are only treated as authoritative with the required **PASS evidence**. PASS is represented as `gate_receipt` (gate_id, status, scope + optional digest/artifacts).
Scenario Runner must not declare a run READY without the required PASS evidence for that run/world. 

**GP0.6 — Determinism + replay safety in an at-least-once world**
Assume duplicates and retries everywhere: all boundaries must be safe under at-least-once delivery, meaning deterministic outcomes under replay and explicit idempotency keys where side-effects exist.
When we publish a digest/hash (snapshot hash, audit_record_id, content_digest), it must be computed deterministically (stable ordering + stable canonicalization rules).

**GP0.7 — Watermarks are the universal “what was applied” token**
Replay/provenance uses **per-partition offsets** as the stable progress tokens. IEG’s `graph_version` is defined by an applied-offset watermark vector (+ stream identity). OFP similarly records an `input_basis` watermark vector for snapshot provenance.

**GP0.8 — Degrade is explicit, enforced, and recorded**
Degrade Ladder emits `{degrade_mode, capabilities_mask, provenance}` deterministically from signals; Decision Fabric must treat the mask as **hard constraints**; Audit must record the degrade posture used.

**GP0.9 — No hidden “now”: as-of is explicit across serving + learning**
Online Feature Plane requests have an explicit `as_of_time_utc`; Label Store exposes labels with explicit effective/observed time semantics; training joins must be leakage-safe using “as-of” rules rather than implicit wall-clock assumptions.

**GP0.10 — Active bundle resolution is deterministic**
Model/Policy Registry resolves exactly one ACTIVE bundle per scope deterministically (no “latest by default”), and Decision Fabric consumes that bundle ref (with identity/digest posture) as part of provenance.

---

### Two immediate “realignment notes” (so drift doesn’t sneak in)

* Your IG spec currently speaks `event_time`/`ingest_time`; the platform anchor is `ts_utc` + IG ingestion stamp, with `emitted_at_utc` optional. We’ll treat IG naming as a mapping to these anchor fields when refining later.
* Rails/RT canonical pack defines ContextPins as 4 fields; the engine interface needs `seed` for invocation and many run-scoped artefacts. The anchor is: **ContextPins (4) + Seed (separate, required when applicable)**.

Here's what I mean: there are **two small “vocabulary mismatches”** between (a) the *binding* contracts you already have and (b) some of the conceptual/spec-design notes. If we pin the mapping now, we can later refine the drifting docs without confusion.

**1) IG’s `event_time` / `ingest_time` vs the canonical envelope’s time fields**

* Your **Canonical Event Envelope** (the contract that crosses IG/EB) uses:

  * `ts_utc` = the event’s domain/meaningful time
  * `emitted_at_utc` = optional “producer emitted this at…” time 
* Your **Ingestion Gate spec-design** uses:

  * `event_time` (domain time)
  * `ingest_time` (when IG processed/committed it) 
* Your **concept canonical pack** also uses `event_time_utc` / `ingest_time_utc` naming. 

So the *concept* is consistent (domain time vs ingestion time), but **the names differ**.

What I’m proposing we pin as the platform primitive:

* **Domain event time** is the one that lives on the canonical envelope: `ts_utc`.
  → Treat IG’s `event_time` (and concept’s `event_time_utc`) as **aliases that normalize to `ts_utc` on admission**.
* **Ingestion time** is real, but it’s **IG metadata/receipt time**, not the event’s meaning.
  → If we keep the envelope minimal, `ingest_time` lives in IG receipts/stamps, not as the event’s domain time.
* `emitted_at_utc` stays optional for producers that can supply it. 

**2) ContextPins (4 fields) vs `seed` (needed for determinism)**

* Cross-cutting rails define **ContextPins** as the canonical “pins carried everywhere” set:
  `{scenario_id, run_id, manifest_fingerprint, parameter_hash}`
* The engine interface + invocation contract require `seed` (and explain it as the realisation key for RNG-consuming lanes).

So the mismatch is: **some things need `seed` for reproducibility**, but we don’t want to force `seed` into the “carried everywhere” join pins if it’s not always relevant.

What I’m proposing we pin as the platform primitive:

* **ContextPins stay 4** (they’re the universal join pins).
* **`seed` is separate** and becomes **required when the artifact/event is seed-variant** (i.e., depends on RNG / engine realisation), and always required for engine invocation.
* If an event/record omits `seed`, it must either be genuinely non-seed-variant *or* be able to derive it via a by-ref pointer that includes it (e.g., a locator/ref pinned to a seeded output).

---

## Cross Plane Relationships

## #1 World Builder ↔ Control & Ingress (Data Engine ↔ Scenario Runner)

### What this relationship *is*

This boundary is the **handshake that turns “a world can be generated” into “the platform is allowed to operate on a pinned run.”**

### The non-negotiable truths to pin (designer-authoritative)

**1) SR is the readiness authority.**
Only **Scenario Runner** can declare a run “READY.” Nothing else in the platform gets to imply readiness by existing files, timestamps, or “latest outputs.”

**2) Engine is the world evidence authority.**
Data Engine is truth for: the immutable world/event artifacts it writes and the PASS/FAIL evidence it emits. SR never re-derives “equivalent” world truth.

**3) SR’s READY means: pinned + evidenced + joinable.**
A run is READY only when SR can publish a join surface that is:

* **Pinned** (identity is explicit; no ambiguity),
* **Evidenced** (required PASS proofs exist for this exact pinned world/run scope),
* **Joinable** (downstream components can start from SR’s join surface and locate everything they need by ref).

**4) Downstream never “discovers” the Engine.**
No downstream component should scan engine directories, query “latest,” or invoke the engine. Downstream starts at SR’s join surface. Always.

---

## Production behavior of this boundary

### Happy path (fresh run)

1. SR receives a run request (scenario binding + pins).
2. SR issues an engine invocation (or equivalent run instruction).
3. Engine materializes outputs and emits gate PASS evidence.
4. SR verifies required PASS evidence and composes the join surface.
5. SR publishes READY (and the join surface becomes the platform entrypoint).

### The join surface (what SR must publish)

Think of SR publishing exactly two conceptual things:

* **RunReady signal**: “this run is admissible for downstream.”
* **RunFacts view**: “here are the pinned references + proofs you should use.”

At minimum, that join surface must carry:

* the **pins** (run/world identity),
* **refs/locators** to the engine outputs that matter for downstream,
* the **PASS evidence** that makes those refs admissible.

(How these are stored can be implementation; the *meaning* is what’s pinned.)

---

## Reuse vs rerun (so we don’t drift later)

This is the biggest place teams get confused, so we pin it now:

### World identity vs run attempt identity

* **World identity** = the tuple that makes the world deterministic (conceptually: manifest + parameters + seed + scenario binding).
* **Run identity** (`run_id`) = the operational “attempt / orchestration instance” that ties together ingestion, tracing, audit, and lifecycle.

**Pinned rule:** SR is allowed to create a new run (new `run_id`) that **reuses** a previously materialized world, as long as it can still publish the join surface with valid PASS evidence and correct refs.

### When reuse is allowed

SR may reuse an existing world materialization if:

* the requested world identity matches,
* required PASS proofs exist for that exact identity scope,
* the referenced outputs resolve cleanly,
* and the reuse does not break the platform’s audit story (SR records that it reused).

### When rerun is required

SR must rerun (or treat the run as not-ready) if:

* required PASS evidence is missing/FAIL,
* the world identity doesn’t match,
* or required outputs cannot be referenced deterministically.

**Pinned rule:** SR never “half-readies” a run. READY is binary.

---

## Failure semantics at this boundary

If the engine cannot produce required outputs or required PASS evidence:

* SR must **not** declare READY.
* SR marks the run as failed (or not-ready) and retains the evidence trail (so the failure is explainable).
* Downstream components must have **no legitimate path** to proceed “anyway.”

---

## What this lets us do next

With #1 pinned like this, every later spec (SR, IG, EB, etc.) has a stable anchor:

* SR has **one job** at this boundary: produce a join surface whose references are admissible.
* Engine has **one job** at this boundary: materialize deterministic world artifacts + emit admissibility proofs.
* Downstream has **one rule**: start at SR join surface, never bypass it.

---

## #2: Control & Ingress ↔ Real-Time Decision Loop.

This boundary is the platform’s **“facts gate + facts log”** handshake: *nothing becomes decisionable truth until it is admitted, and once admitted it becomes replayable fact.*

### What this relationship *is*

* **Ingestion Gate (IG)** is the **trust boundary**: it decides *admit vs quarantine vs duplicate* and produces the evidence trail for that decision.
* **Event Bus (EB)** is the **durable fact log**: append-only, replayable, at-least-once delivery. It does **not** decide meaning; it preserves what was admitted.

### Production truths to pin (designer-authoritative)

**1) “Only one front door” into the hot path.**
If something can influence identity, features, decisions, actions, audit, labels, or training facts, it enters **through IG → EB**. No “side channel” feeds directly into IEG/OFP/DF/etc.

**2) IG is the *admission authority*; EB is the *fact authority*.**

* IG is truth for: *admission outcomes* and the *reason/evidence* (including quarantine).
* EB is truth for: *the admitted sequence* (partition/offset order + replay semantics).

**3) Canonical envelope is the boundary shape.**
What EB stores and what consumers read is a canonical envelope shape (plus whatever payload schema you allow behind it). If it’s not canonical, it’s not admitted.

**4) Admission is not “done” until EB acknowledges append.**
IG must only emit “ADMITTED” when the event is durably appended to EB. In practice, that means the IG receipt can safely carry (or reference) the event’s EB coordinates (partition + offset) as the “where it lives” pointer. This makes audit, replay, and forensic joins deterministic.

**5) At-least-once is assumed, so idempotency is mandatory at the boundary.**
IG must behave deterministically under retries/duplicates:

* same event arriving again does not create a new fact,
* it yields a stable “duplicate/admitted already” outcome (with a pointer to the original append),
  so downstream doesn’t amplify duplicates into inconsistent projections.

**6) Quarantine is first-class (no silent drops).**
If an event is malformed, unjoinable, unauthorized, or suspicious: it is quarantined with a receipt + evidence pointers. “Drop on the floor” is disallowed because it destroys auditability and makes debugging impossible.

**7) Joinability checks are enforced at the boundary.**
For streams that are meant to drive the current run/world, IG enforces that the event carries the required pins (and that the run/world context is admissible). Unknown/unready contexts → quarantine. (This is how SR’s readiness truth becomes *enforceable* rather than “advisory.”)

**8) EB provides the replay tokens that power determinism downstream.**
Downstream consumers use EB’s coordinates to form watermarks (“what I have applied”), which then become the basis for deterministic graph/versioning and feature snapshot provenance.

---

## How it behaves in production (simple narrative)

1. A producer emits an event (engine traffic, DF outputs, AL outcomes, labels, etc.).
2. IG validates the envelope + joinability + policy, then chooses:

   * **ADMIT** → append to EB → emit receipt (with pointer to EB location and/or digest), or
   * **DUPLICATE** → emit receipt pointing at the already-appended fact, or
   * **QUARANTINE** → store evidence by-ref → emit receipt with reason/evidence pointers.
3. EB becomes the single replayable record.
4. Hot-path components (IEG/OFP/DF/…) only consume from EB and treat “what’s in EB” as the factual basis.

---

## The one-line “Plane Pin” for #2

**IG is the sole admission authority and EB is the sole durable fact log for decisionable events; admission is atomic with EB append, duplicates are handled deterministically, quarantines are first-class, and hot-path consumers only accept reality from EB (with replay coordinates powering downstream determinism).**

---

## #3: World Builder ↔ Downstream planes (RTDL / Label+Case / Learning).

This relationship is about one thing: **how the Engine’s “world truth” becomes usable by the rest of the platform without leaking, drifting, or bypassing trust rules.**

---

## What this relationship *is*

The **World Builder (Data Engine)** produces two kinds of “things”:

1. **Traffic** (event-like streams) — meant to flow through the platform like real events.
2. **Surfaces** (reference datasets / truth products / audit evidence / telemetry) — meant to be *read by ref* as pinned artifacts.

Downstream planes must treat those differently.

---

## Production truths to pin (designer-authoritative)

### 1) Engine output roles are real boundaries (not “labels”)

Every engine output is treated as one of:

* **business_traffic** → eligible to enter the hot path
* **truth_products** → hidden/privileged truth (evaluation/training), *not* hot-path input
* **audit_evidence** → used for audit/forensics (not traffic)
* **ops_telemetry** → operational signals only (not traffic)

**Pinned rule:** only **business_traffic** is allowed to influence decisioning directly.

---

### 2) Engine traffic still uses the IG → EB front door

Even if the engine is “internal,” **engine traffic does not bypass admission**.

**Pinned rule:** if it’s treated as traffic, it goes **Engine → IG → EB → consumers** (canonical envelope and all).

This keeps:

* joinability enforcement (run/world pins),
* consistent dedupe,
* quarantine for malformed/out-of-scope events,
* and a single replayable record.

---

### 3) Engine surfaces are consumed by reference, never by copying

Engine surfaces/truth/audit outputs are not “ingested” as events.

**Pinned rule:** surfaces are consumed **by-ref via locators/refs**, never by copying their contents into other planes as a new “source of truth.”

So downstream stores pointers + digests/proofs, not duplicated datasets.

---

### 4) “No PASS → no read” applies to Engine material everywhere

Downstream components do not treat an engine artifact as admissible unless:

* it is explicitly referenced (locator/ref),
* and the required PASS evidence exists for that exact pinned scope.

**Pinned rule:** engine artifacts are **not discoverable by scanning**, and **not trustworthy without PASS evidence**.

---

### 5) SR is the broker of “which engine material matters”

Downstream doesn’t get to decide “which world” to use.

**Pinned rule:** downstream components start from SR’s join surface for a run, and the join surface is the authoritative map of engine refs + proofs for that run/world.

This prevents “latest world” bugs, accidental cross-run mixing, and drift.

---

### 6) Truth products never leak into the hot path

Because it’s a closed world, the engine can generate “ground truth.” That’s useful — but dangerous if it leaks.

**Pinned rule:** engine **truth_products** can be used for:

* offline evaluation,
* training set construction,
* test harnesses,
  but are **never** used as hot-path features/inputs unless explicitly declared as such (rare, and would be a major design decision).

---

### 7) Audit evidence and telemetry are routed to the right planes

* **audit_evidence** is for Decision Log/Audit / governance / forensic replay.
* **ops_telemetry** is for observability signals (and can influence behavior only through explicit control surfaces like Degrade Ladder).

**Pinned rule:** neither is treated as business traffic.

---

### 8) One immutability posture across the boundary

Engine outputs are immutable once written for a pinned identity.

**Pinned rule:** downstream systems must not “patch” engine facts; if something must be corrected, it happens as:

* a *new* artifact/version with new identity, and/or
* a *new* run with a new join surface that points at the corrected refs.

---

## The one-line “Plane Pin” for #3

**Engine outputs enter the platform in two modes: business traffic goes through IG→EB as canonical events, while all other engine material is consumed by-ref as gated, immutable artifacts referenced from SR’s join surface; truth products/audit/telemetry never masquerade as traffic, and nothing downstream discovers or trusts engine material without explicit refs + PASS evidence.**

---

## #4 Real-Time Decision Loop ↔ Label & Case

This boundary is where the platform separates **“what we decided/did”** from **“what is actually true (ground truth)”** — without losing auditability.

### Production truth (designer-authoritative)

**1) RTDL outputs are *evidence*, not ground truth.**
Decisions, action intents, and action outcomes are *what the system chose and what it did*, plus the provenance of why. That is crucial evidence for investigations, but it is **not** “truth labels.” The canonical “flight recorder” for this evidence is the Decision Log/Audit record set (append-only, corrections via supersedes). 

**2) Case work consumes evidence by reference and builds an immutable case story.**
Case Mgmt / Workbench takes triggers and **evidence refs** (from DF decisions, AL outcomes, DLA pointers), and maintains a **case object + append-only case timeline** (“what happened / what was done / who did it / when”). It may optionally emit case events back onto the stream for automation/audit, but it remains the work surface for humans.

**3) Labels become truth only when written to Label Store.**
Investigators (and delayed external outcomes like disputes/chargebacks) produce **label assertions**; Label Store is the **single source of truth** for labels as append-only timelines with “as-of” semantics (effective vs observed time). System-derived outcomes can be stored as **evidence**, but they are not automatically “truth” unless your label policy explicitly says so.

**4) Manual interventions must go through the same action pathway as automated ones.**
If a human action changes the world (block, release, queue, notify, etc.), it must be expressed as an **ActionIntent** and executed via the **Actions Layer** (effectively-once + immutable outcomes), so it’s dedupe-safe and auditable the same way automated actions are.

**5) The join across RTDL ↔ Case/Labels is stable identifiers + refs, not copied payloads.**
The “bridge” is: ContextPins + event/decision/action IDs + **by-ref evidence pointers** (audit record IDs, EB coordinates, artifact refs). Case/labels should not duplicate big event payloads just to be “complete”; they point to the factual record.

### The one-sentence plane pin for #4

**RTDL produces an auditable evidence trail (decisions + actions + outcomes + provenance); Case Mgmt consumes that evidence by-ref to build immutable investigation timelines; ground truth exists only as append-only label timelines in Label Store; and any human-driven side effects must run through the same Actions Layer pathway so outcomes stay dedupe-safe and fully auditable.**

---

## #5 Label & Case ↔ Learning & Evolution

This boundary is where **human truth becomes machine learning truth** — without leakage, ambiguity, or silent rewrites.

### Production truth (designer-authoritative)

**1) Label Store is the only label truth used for learning.**
Learning pipelines do not infer labels from outcomes, heuristics, or “what the system decided.” They consume labels only from **Label Store** (append-only timelines).

**2) Labels are timelines, not single values.**
A “label” is not a scalar — it’s an evolving record with:

* subject (event/entity/flow),
* label value,
* provenance,
* **effective_time** (when the label is true in the world),
* **observed_time** (when the platform learned it).

**3) Training joins are “as-of” by rule (leakage-safe).**
When learning builds datasets, it must do **as-of joins**:

* features/events are taken up to an as-of boundary,
* labels are taken as-of the same boundary,
* and anything observed after the decision point is excluded unless explicitly modeling delayed feedback.

**4) Case workflow produces labels, but doesn’t dictate training semantics.**
Case Mgmt is the operational/human workflow; Label Store defines the semantics learning uses (timelines + as-of). Case tools can emit label assertions, corrections, or confidence—but learning reads them through Label Store rules, not ad-hoc case exports.

**5) Corrections are handled as append-only truth evolution.**
If a label changes, it is a new assertion on the timeline (with provenance), not a destructive update. Learning can then reproduce “what we knew then” vs “what we know now.”

**6) Learning must be able to reproduce any dataset build.**
Any training dataset build must be reproducible from:

* the pinned event history source (EB/Archive),
* Label Store timelines,
* and the declared as-of window.
  So “dataset build” is treated like a deterministic transformation, not an ad-hoc export.

### The one-sentence plane pin for #5

**Learning consumes labels only from Label Store as append-only timelines, and training/eval datasets are built using explicit leakage-safe “as-of” joins (effective vs observed time), so any model can be reproduced against exactly what the platform knew at the time of decision.**

---

## #6 Real-Time Decision Loop ↔ Learning & Evolution

This boundary is: **production reality → replayable training reality** (without training/serving drift).

### Production truths to pin (designer-authoritative)

**1) Learning only learns from replayable facts, not from live internal state.**
Learning consumes the *factual record* (admitted events and auditable decision context), not whatever happened to be in online caches at the time. The replayable basis is **EB history** + the **audit/provenance record** that explains what the system knew and why it acted.

**2) RTDL must leave “rebuild targets” behind (so learning can reproduce decisions).**
For every decision point, the platform must be able to reconstruct:

* what events were considered (via EB coordinates / watermarks),
* what entity context applied (via `graph_version`),
* what features were served (via `feature_snapshot_hash` + provenance),
* what degrade posture constrained behavior (mode + capabilities mask),
* what policy/model bundle was used (bundle ref).

**3) Offline Feature Plane Shadow is the contract bridge between serving and training.**
Its job is **deterministic reconstruction**: given EB history + the same feature definitions/versions, it rebuilds feature snapshots/datasets “as-of time T,” and produces **parity evidence** against online serving (e.g., matching `feature_snapshot_hash` under the same `input_basis` + `graph_version`).

**4) Watermarks are the shared “what was applied” truth across hot path and offline rebuild.**
EB offsets (watermark vectors) are the universal progress token; OFP records an `input_basis` watermark vector, and IEG produces `graph_version` from its applied watermark state. These two together define the replay boundary for “what the system could have known.”

**5) Dataset assembly is explicit and reproducible (not ad-hoc exports).**
Offline assembly emits dataset/feature manifests (windows, join keys, versions, digests) so Model Factory can reproduce training inputs exactly. “Training dataset” is treated as a pinned artifact, not a query someone reruns differently next week.

**6) Audit is the glue: it preserves decision-time provenance for learning.**
Decision Log/Audit is the canonical “what we knew/why we acted” store, and it must record enough by-ref provenance (snapshot hash, versions, bundle ref, degrade posture, evidence pointers) for forensic replay and training set correctness checks.

### One-sentence plane pin for #6

**Learning is fed by the replayable factual record (EB) plus decision-time provenance (audit + feature snapshot hashes + watermarks + graph_version + degrade + bundle refs), and the Offline Feature Shadow deterministically rebuilds the serving context to produce reproducible datasets and parity evidence so training cannot drift from what the platform actually served.**

---

## #7 Learning & Evolution ↔ Real-Time Decision Loop

This boundary is: **what learning produces becomes deployable decision logic**, in a way that is deterministic, auditable, and safe to operate.

### Production truths to pin (designer-authoritative)

**1) Registry is the only deployable truth source.**
The output of Learning (models + policies) affects production decisions only via the **Model/Policy Registry**. Nothing in RTDL loads “a model file” directly from a random path, a training run folder, or “latest artifact.”

**2) “Active bundle” resolution is deterministic by rule.**
For any decision scope (tenant/env/scenario/run or whatever you choose), registry resolution returns exactly one **ACTIVE bundle** by deterministic rules — not “most recent,” not “who deployed last.”

**3) Bundle promotion is evidence-led.**
A bundle is promotable only with the required **evidence** attached (evaluation artifacts, lineage, reproducibility pins, PASS gate receipt where required). This prevents “mystery models” and enforces change control.

**4) Decision Fabric must record the resolved bundle reference in provenance.**
Every decision must be explainable later: DF records the bundle identity (and digest posture where you choose) as part of the decision provenance, so replay/audit can re-run the same logic.

**5) Rollouts and rollbacks are first-class, auditable changes.**
Changing ACTIVE bundles is an operational act that must be visible in governance/audit streams. RTDL behavior changes only via this explicit mechanism (no shadow config toggles).

**6) Compatibility is a platform contract, not a “best effort.”**
A deployed bundle must declare compatibility with:

* the feature definitions/versions it expects,
* required inputs,
* and any constraints (e.g., degrade mask compatibility).
  If incompatible, registry resolution must fail closed or route to a safe fallback (depending on your degrade policy).

### One-sentence plane pin for #7

**Learning influences production only through the Registry: it publishes evidence-backed, reproducible bundles; the Registry deterministically resolves exactly one ACTIVE bundle per scope; Decision Fabric consumes that resolution and records the bundle ref in provenance; and promotions/rollbacks are explicit, auditable changes with compatibility rules that fail closed or degrade safely.**

---

## #8 Observability & Governance ↔ All planes

This relationship is: **the platform is operable, explainable, and safe** — without hidden coupling.

### Production truths to pin (designer-authoritative)

**1) Observability/Governance is not a “side system”; it defines the rules of safe operation.**
Every plane must emit enough structured facts to support:

* lineage (“what produced what”),
* audit (“why did we do that”),
* and ops safety (“are we healthy enough to act”).

**2) No silent mutation: Obs/Gov never changes behavior by stealth.**
Obs/Gov can *inform* behavior only through explicit control surfaces:

* **Degrade Ladder** consumes health/lag signals and produces an explicit constraints mask;
* change control uses explicit promotion/rollback events;
* governance actions are logged and reviewable.

**3) Correlation conventions are mandatory across planes.**
To trace an outcome end-to-end, all planes must carry correlation identifiers consistently:

* `run_id` + ContextPins for run/world scope,
* `event_id` for event lineage,
* decision/action/audit IDs for accountability,
* trace fields for request/processing correlation.
  Without this, you can’t debug or prove anything in production.

**4) “No PASS → no read” is a governance rule, not just an engine rule.**
Gating posture applies broadly: readiness, dataset builds, promotions, and any “truth surface” must have PASS evidence, and consumers must treat PASS as a prerequisite to trust.

**5) Governance must see change.**
Any change that can affect outcomes (model/policy rollouts, config changes, retention/backfill operations, access changes, action executions) must emit auditable governance facts. If something can change behavior without being visible, the system is not production-ready.

**6) Observability provides the inputs for safe constraints (degrade), not a second decision engine.**
Obs/Gov provides “golden signals” and corridor checks; DL turns that into explicit constraints; DF obeys those constraints; DLA records what constraints were in force.

### One-sentence plane pin for #8

**Obs/Gov makes the platform safe and explainable by enforcing universal correlation + lineage + auditable change facts; it never silently mutates behavior, instead influencing the system only through explicit control surfaces (notably Degrade and governed rollouts), and it extends “no PASS → no read” from the engine into a platform-wide trust rule.**

---

## #9 Run/Operate ↔ All planes

This relationship is: **the platform’s operational substrate** — how everything runs in production — without breaking determinism, auditability, or trust boundaries.

### Production truths to pin (designer-authoritative)

**1) Run/Operate is the substrate, not a truth source for domain facts.**
Run/Operate provides scheduling/orchestration, storage, configuration, secrets, and runtime controls — but it must not become an alternate “source of business truth.” Domain truths live in the planes (SR readiness, EB facts, labels, registry, etc.).

**2) Run/Operate must not introduce hidden nondeterminism.**
No implicit “now,” no unordered merges, no environment-dependent randomness, no silent retries that change semantics without being recorded. If a nondeterministic factor exists, it must be captured as an explicit input pin or an explicit provenance fact.

**3) Run/Operate is responsible for persistence of by-ref artifacts and evidence.**
Because the platform’s posture is “by-ref,” Run/Operate must provide the durable substrate for:

* SR ledgers (`run_plan`, `run_record`, `run_status`, `run_facts_view`),
* quarantine evidence pointers from IG,
* audit evidence pointers from DLA,
* dataset manifests and training/eval bundles,
* registry bundles and governance artifacts.

**4) Run/Operate is the execution fabric for orchestration, but not the decision fabric.**
It can execute workflows (run engine, run training, run backfills, deploy bundle), but **it does not decide** what is true or what action should happen. Decisions and actions remain inside DF/AL and governed processes.

**5) Run/Operate is the only place platform-wide lifecycle control can live (start/stop/drain/backfill).**
Controlled shutdowns, drains, replay windows, retention, and backfills are operational acts. They must be done via Run/Operate so they are consistent and auditable across planes.

**6) Any operational act that can change outcomes must be auditable.**
If an operational change can affect what decisions get made (deploying bundles, changing config, changing retention, toggling ingestion policy), it must surface as explicit governance facts and be traceable end-to-end.

### One-sentence plane pin for #9

**Run/Operate provides the orchestration + storage + config/secrets substrate that all planes depend on, but it must preserve determinism and never become a shadow source of domain truth; it persists by-ref artifacts/evidence and owns lifecycle operations (deploy/drain/backfill/retention), with any outcome-affecting operational action made explicit and auditable.**

---

## #10 Run/Operate ↔ Observability & Governance

This relationship is: **operations are governed** and **governance is actionable** — so the platform can change safely in production.

### Production truths to pin (designer-authoritative)

**1) Every operational change emits a governance fact.**
Run/Operate must surface “this happened” events for anything that can affect outcomes or reproducibility, including:

* deployments/releases,
* config/policy changes,
* model/policy promotions/rollbacks,
* retention changes,
* backfills/replays,
* access/control changes,
* emergency stops/drains.
  If an operator can change behavior without leaving a governance trail, the system isn’t production-ready.

**2) Observability/Governance defines the corridor checks Run/Operate must respect.**
Obs/Gov owns the “are we allowed to proceed?” posture:

* SLO/corridor checks (health, lag, error budgets),
* lineage completeness checks,
* “no PASS → no read” compliance checks,
* rollout safety gates.
  Run/Operate uses these checks to decide proceed/degrade/halt.

**3) Governance must be able to explain any run or decision ex post.**
That requires Run/Operate to preserve:

* the exact configs/pins used,
* run/training/deploy identifiers,
* evidence pointers/digests,
  so governance can reconstruct “what was in force” at any point.

**4) Emergency controls are explicit and traceable.**
If there is a kill-switch, drain, or forced-degrade operation, it must:

* be explicit (not silent),
* have a clear scope (what it affects),
* and be recorded as a governance fact with provenance (who/why/when).

### One-sentence plane pin for #10

**Run/Operate and Obs/Gov form the platform’s safe-change loop: Run/Operate emits auditable governance facts for all outcome-affecting operations, while Obs/Gov defines the corridor checks and trust rules (SLOs, lineage, PASS compliance, rollout gates) that Run/Operate must respect to proceed, degrade, or halt in a controlled, traceable way.**

---

## Cross component relationships/cross-plan pins

Now that the **10 cross-plane pins** are set, the component joins worth defining next are the ones that make those pins *real in production* (front doors, replay tokens, provenance, and the two truth loops).

Here’s the **shortlist** I’d define next (in the order I’d cover them):

### Front door + run truth joins

**J1. SR ↔ Data Engine** — invocation, reuse rules, what SR must collect as evidence (locators + PASS receipts).
**J2. SR → Downstream entrypoint** — what exactly constitutes the join surface (`run_ready_signal` / `run_facts_view`) and what downstream is forbidden from doing (no “scan latest”). 
**J3. Producers → Ingestion Gate** — admission rules: canonical envelope, joinability to run/world, duplicate handling, quarantine posture.
**J4. Ingestion Gate ↔ Event Bus** — “admitted” means durably appended; how receipts point to EB coordinates; atomicity expectations.

### Hot path determinism + provenance joins

**J5. Event Bus → Consumers** — replay semantics + watermark/offset meaning (the universal “what was applied” token).
**J6. Event Bus → IEG** — envelope-first updates + how `graph_version` is derived from applied watermarks. 
**J7. (EB + IEG) → OFP** — how OFP builds snapshots; `input_basis` watermark vector; snapshot hash/provenance meaning.
**J8. OFP → DF** — what DF can assume from a FeatureSnapshot (hash, freshness, provenance) and what it must record.
**J9. Degrade Ladder → DF** — capabilities mask as hard constraints + recording posture.
**J10. Registry → DF** — deterministic “active bundle” resolution + fail-closed/fallback rule.
**J11. DF → Actions Layer** — ActionIntent idempotency key semantics + what counts as “same intent.”
**J12. (DF/AL/IG) → Decision Log/Audit** — what the flight recorder must persist by-ref (receipts, hashes, bundle ref, degrade posture) and correction/supersedes posture.

### Human truth + learning loop joins

**J13. Case Workbench → Label Store** — label assertion semantics (effective vs observed time, append-only timelines).
**J14. (Label Store + EB/Archive) → Offline Shadow** — “as-of” join rules + what replay source is authoritative when EB retention ends.
**J15. Offline Shadow → Model Factory** — DatasetManifest meaning (windows, join keys, digests, feature versions) so MF inputs are reproducible.
**J16. Model Factory → Registry** — what a “publishable bundle” must include (evidence/provenance/PASS posture) and how rollout becomes auditable truth.

---

## J1) Scenario Runner ↔ Data Engine

This join is the **world-build handshake**: SR turns a run request into **engine completion evidence**.

**What SR sends (the invocation contract):**
SR invokes the engine with an `engine_invocation` carrying at least:
`manifest_fingerprint, parameter_hash, seed, run_id, scenario_binding` (and optional `request_id` for idempotency). 

**What the engine returns (completion evidence):**
Engine completion evidence is **not** “a success boolean.” It’s:

* **Output locators** (`engine_output_locator`) that point at the produced artifacts (with pins + optional digest). 
* **PASS/FAIL evidence** as **gate receipts** (`gate_receipt`) scoped to the exact identity.

**What SR must do with that evidence:**
SR is allowed to declare “engine step complete” only when it can **record** and later **replay**:

* which outputs were produced (by locator),
* which required gates passed (by receipt),
* under which pins (ContextPins + seed where applicable).

If required PASS evidence is missing or FAIL → SR does **not** declare READY. (SR can mark run failed/quarantined, but not READY.)

**Reuse (still designer-mode, production truth):**
SR may “reuse” existing engine outputs **only** if it can reconstruct the same completion evidence set (locators + required PASS receipts) for the requested pins. Reuse is **explicitly recorded** in SR’s run_record (so it’s auditable). 

---

## J2) Scenario Runner → Downstream entrypoint (the join surface)

This join is the **platform entrypoint**: downstream starts here or it’s a bug.

**What SR publishes:**
SR publishes a **READY signal** (`run_ready_signal`) and the **join surface** (`run_facts_view`). 

**Production truth:**

* `run_ready_signal` is the **trigger** (monotonic: once READY, SR doesn’t “undo” READY; any correction is a new declared state or a superseding run story, not silent mutation). 
* `run_facts_view` is the **map**: pinned references to engine outputs + the required PASS evidence to treat those refs as admissible.

**What downstream is forbidden from doing:**
Downstream components must not:

* scan engine outputs,
* infer “latest run,”
* or independently decide what world to use.
  They start from SR’s join surface and follow refs.

**What downstream must do:**
Downstream must treat **PASS receipts** as prerequisites: “no PASS → no read.”

---

## J3) Producers → Ingestion Gate

This join is the **trust boundary** for anything that will influence decisions, audit, labels, or learning.

**What producers must supply (minimum):**
A canonical event envelope that includes required fields:
`event_id, event_type, ts_utc, manifest_fingerprint` (and the relevant optional pins like `scenario_id/run_id/parameter_hash/seed` depending on whether the event is run/world-joinable). 

**What IG decides (and is authoritative for):**
IG decides **exactly one** of: ADMIT / DUPLICATE / QUARANTINE — and produces a receipt/evidence trail for that decision. It must not “silently fix” bad inputs into good ones; if it can’t validate/anchor under policy, it quarantines. 

**Joinability enforcement (critical):**
If an event is meant to participate in the current run/world, IG enforces that it’s joinable to a **valid run context** (and, in practice, a READY run). If not joinable → quarantine/hold, not “best effort.”

---

## J4) Ingestion Gate ↔ Event Bus

This join is **admission becomes durable fact**.

**Production truth:**

* EB is append/replay; it is **not** validator/transformer. 
* “Admitted” must mean: **durably appended**. IG must not emit “ADMITTED” unless EB has acknowledged the append.
* EB is system-of-record for **partition + offset** and replay semantics; these offsets become the replay tokens downstream uses (watermarks).

**Partitioning posture (important detail):**
EB should not infer partitioning from domain logic; it expects a partition key / routing decision at the edge. In v0, that means IG is responsible for stamping/choosing the partitioning key for admitted events.

**Duplicates:**
EB is at-least-once. IG should aim to prevent duplicate appends (and emit DUPLICATE receipts pointing to the original), but downstream must still be safe if duplicates exist.

---

## J5) Event Bus → Consumers (replay + offsets + checkpoints)

**What EB gives the whole platform:** a replayable fact log where the *only* universally meaningful “position” is **(stream_name, partition_id, offset)**, with ordering guaranteed **only within a partition** and delivery **at-least-once** (duplicates/redelivery are normal). 

**The pinned semantic that enables determinism:** consumer progress is expressed as a **checkpoint** whose `offset` is the **next offset to read/apply (exclusive)**. That “exclusive-next” meaning is what later becomes the universal watermark basis.

**Also pinned (because it impacts determinism):** EB requires a `partition_key` for routing, but EB does not define its composition — it just requires it to be stable and deterministic for every published event. 

---

## J6) Event Bus → Identity & Entity Graph (IEG)

**What IEG consumes:** admitted events from EB, assuming duplicates + out-of-order delivery.

**The pinned replay safety rule:** IEG applies events idempotently using an **update_key** derived from **ContextPins + event_id + a pinned semantics id** (so replay/redelivery can’t double-apply). 

**The pinned meaning of `graph_version`:** it is a **monotonic token** representing “what EB facts have been applied” for a given ContextPins graph — concretely, a **per-partition applied-offset watermark vector (exclusive next offsets) plus stream_name**.

**What crosses the join to downstream:** whenever IEG is used as context, downstream records the `graph_version` that was used so the decision context can be replayed/audited later. 

---

## J7) (EB + IEG) → Online Feature Plane (OFP)

**What OFP consumes:** admitted events from EB to maintain aggregates/state, and (optionally) IEG queries to resolve canonical keys + capture `graph_version` for provenance.

**The pinned replay safety rule:** OFP’s aggregate updates are idempotent using a key derived from **EB position × FeatureKey × FeatureGroup**:
`(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)` — so duplicate deliveries don’t double-count.

**The pinned provenance contract of a served snapshot:** every successful `get_features` must return provenance that includes:

* ContextPins
* `feature_snapshot_hash` (deterministic)
* group versions used + freshness/stale posture
* `as_of_time_utc` (explicit; no hidden “now”)
* `graph_version` (if IEG was consulted)
* `input_basis` = applied-event watermark vector
  …and the snapshot hash must deterministically cover the relevant blocks (features map, freshness, graph_version, input_basis, etc.) with stable ordering.

That’s the bridge that makes offline parity possible later (rebuild the same snapshot under the same `input_basis`/`graph_version`). 

---

## J8) Online Feature Plane → Decision Fabric (DF)

**Pinned time rule (kills “hidden now” bugs):** DF treats `event_time` as the canonical decision boundary and calls OFP with `as_of_time_utc = event_time_utc` (v0 posture).

**Pinned provenance rule:** DF must record, in decision provenance, what OFP gave it:

* `feature_snapshot_hash`
* group versions
* freshness/stale flags
* `input_basis` watermark vector
  (and `graph_version` if IEG was consulted).

**Pinned correctness rule:** DF does not invent missing context — if required features aren’t available, DF records unavailability and follows its pinned fail-safe posture; it also must obey degrade constraints (e.g., only request/use allowed feature groups).

---

## J9) Degrade Ladder → Decision Fabric

**What crosses the join:** a **DegradeDecision** that is *explicit, deterministic, and recordable* — `mode`, `capabilities_mask`, and provenance (plus a decided-at timestamp / optional deterministic decision id). 

**Production truth to pin:**

* DF must treat `capabilities_mask` as **hard constraints**, not “advice.” If a capability is off, DF behaves as if that tool/feature/model/action **doesn’t exist**.
* Degrade must be **explicitly recorded** in decision provenance (and therefore audit) so later you can say: “this decision was made under posture X.”
* If DL is unavailable or cannot produce a decision, DF fails **toward safety** (i.e., a stricter posture, not a looser one) and records that fallback.

---

## J10) Model/Policy Registry → Decision Fabric

**What crosses the join:** a deterministic answer to “what should I use *for this decision right now*?” — an **ActiveBundleRef** (bundle id + immutable artifact refs + compatibility metadata).

**Production truth to pin:**

* Registry resolution is **deterministic** (no “latest”). For a given scope, DF gets **one active bundle** by rule.
* DF must record the resolved bundle reference in provenance (so decisions are reproducible/explainable later).
* Compatibility is enforced at the join: if the active bundle is not compatible with the current feature definitions or the current degrade mask (e.g., requires capabilities that are currently disabled), DF must fall back to its safe posture and record why.

---

## J11) Decision Fabric → Actions Layer

**What crosses the join:** **ActionIntents** (what should be done) — not “execution.” DF declares; AL executes.

**Production truth to pin:**

* Every ActionIntent must carry a **deterministic `idempotency_key`** and enough join identifiers to bind it to context (ContextPins + decision/event identifiers).
* Actions Layer enforces effectively-once execution using **(ContextPins, idempotency_key)** as the uniqueness scope. Duplicate intents must never re-execute; they re-emit the canonical outcome. 
* Every attempt yields an **ActionOutcome** (including failures), outcomes are immutable, and duplicate re-emits are byte-identical. 

(And per your plane #2, intents/outcomes are “real traffic,” so they still enter the rest of the system via IG→EB; this join is about *semantic authority* between DF and AL.)

---

## J12) (DF + optional AL/IG evidence) → Decision Log/Audit

**What crosses the join:** the **minimum immutable facts** needed to reproduce/justify a decision later, without embedding raw payloads.

**Production truth to pin:**

* DLA’s primary ingest is DF’s DecisionResponse (decision + actions + provenance). AL outcomes can be ingested to close the loop (“intent vs executed”), but DF provenance is the non-negotiable base.
* The canonical audit record must include by-ref / hashed pointers to:

  * the event reference basis (what was decided on),
  * `feature_snapshot_hash` + `input_basis`,
  * `graph_version` (if used),
  * degrade posture (mode + enough to identify the mask used),
  * resolved policy/model bundle reference,
  * actions (including idempotency keys),
  * and audit metadata (ingested_at, supersedes link on correction).
* DLA is **append-only**. Corrections happen via a **supersedes chain**, not overwrites. Ingest is idempotent. If provenance is incomplete, DLA quarantines the audit record rather than silently writing a “half-truth.” 

---

## J13) Case Workbench → Label Store

**What crosses the join:** **LabelAssertions** (human or external adjudication facts) written as append-only timeline entries.

**Production truth to pin:**

* Label Store is the **single truth writer** for labels; Case Workbench is the UI/workflow that *produces assertions*, but the label becomes truth only once stored.
* Labels are **timelines** (append-only), not “update-in-place.”
* Every label assertion must carry:

  * subject (event/entity/flow),
  * value + optional confidence,
  * provenance (who/what process),
  * **effective_time** (when it is true),
  * **observed_time** (when we learned it).
* Corrections are new assertions that supersede/override in interpretation; the historical record remains.

---

## J14) (Label Store + EB/Archive) → Offline Feature Plane Shadow

**What crosses the join:** the **inputs needed for deterministic rebuild** of datasets/snapshots “as-of time T.”

**Production truth to pin:**

* Offline Shadow is allowed to read **event history** from EB within retention, and from an **archive** beyond retention, but both must be treated as **the same logical fact stream** (same identity + same ordering basis per partition).
* Labels are read from Label Store using explicit **as-of** rules (effective vs observed time) to prevent leakage.
* Offline Shadow rebuild is deterministic and must record its basis:

  * input event window (by offsets or by declared time window tied to offsets),
  * as-of boundary,
  * feature definitions/versions used,
  * and any parity anchors (e.g., target snapshot hashes).

---

## J15) Offline Feature Shadow → Model Factory

**What crosses the join:** **DatasetManifests** (pinned dataset definitions) + evidence.

**Production truth to pin:**

* Offline Shadow does not just “hand over a dataframe.” It produces a **DatasetManifest** that pins:

  * dataset identity,
  * time window / as-of boundaries,
  * join keys and entity scoping,
  * feature group versions,
  * digests/refs to materializations,
  * and provenance (what sources + which transformations).
* Model Factory treats DatasetManifests as immutable inputs: training runs are reproducible only if the exact manifests can be re-resolved later.

---

## J16) Model Factory → Model/Policy Registry

**What crosses the join:** deployable **Bundles** + evidence for promotion.

**Production truth to pin:**

* A published bundle is not just “a model artifact.” It is a package with:

  * bundle identity,
  * immutable refs/digests to artifacts (model weights, rules, thresholds, metadata),
  * training run provenance (which DatasetManifests were used),
  * evaluation evidence,
  * and PASS/FAIL receipts where your governance posture requires it.
* Registry is the **only authority** that decides “ACTIVE,” and promotion/rollback must be auditable.
* Compatibility metadata (expected feature versions/inputs) must be part of what crosses this join so DF can enforce safe resolution later.

---

## Cross-cutting Rails + 3 Overlay Families

Think of rails as the **platform laws** that sit *on top of* the plane pins + J1–J16 joins we just defined. I’m going to pin the rail set as **production truth**, and for each one I’ll state **where it bites** (which joins it governs). No diplomacy with the v0 docs — these rails become the authority.

---

### Rail R1 — Identity propagation (ContextPins + seed discipline)

**Production truth:** Anything that claims to be run/world-joinable must carry **ContextPins** `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`. `seed` is required when the thing is **seed-variant** (engine invocation, RNG-derived outputs, seeded streams/snapshots), but ContextPins remain the universal join pins.
**Where it bites:** J1, J2, J3, J6–J8, J11–J16.

---

### Rail R2 — Traffic vs surfaces (role separation)

**Production truth:** Only **business_traffic** is allowed to drive the hot path. Engine **truth_products / audit_evidence / ops_telemetry** are never treated as decisionable traffic; they are consumed **by-ref** (and gated) in the appropriate planes (audit/governance/learning).
**Where it bites:** J2–J4 (what enters the bus), J12 (audit), J14–J16 (learning).

---

### Rail R3 — Canonical event envelope is the only admitted event shape

**Production truth:** The “admitted event” shape is the canonical envelope. If it can influence decisions/audit/labels/learning, it must be representable as a canonical envelope; otherwise it’s not admitted.
**Where it bites:** J3, J4, and any producer that emits to IG/EB.

---

### Rail R4 — “No PASS → no read” is platform-wide

**Production truth:** Gating is not an engine-only rule. A consumer treats an artifact/dataset/bundle as admissible only when the required **PASS evidence** exists for the exact pinned scope. SR readiness is impossible without required PASS; training inputs and deployable bundles follow the same posture.
**Where it bites:** J1–J2 (READY), J14–J16 (datasets/bundles), plus any engine-surface consumption.

---

### Rail R5 — By-ref truth transport + digest posture

**Production truth:** Across boundaries we move **refs/locators + optional digests**, not copied payloads or ad-hoc re-materializations. When a digest is present, it is treated as a first-class integrity claim: mismatches are not “warnings,” they are **inadmissible** and trigger quarantine/fail-closed behavior.
**Where it bites:** J2 (join surface), J12 (audit), J14–J16 (datasets/bundles), plus engine surface reads.

---

### Rail R6 — Replay semantics are expressed only in EB coordinates (watermark basis)

**Production truth:** The only universal replay/progress token is EB coordinates: `(stream, partition, offset)` with **exclusive-next** checkpoint meaning. Higher-level “versions” are derived from this:

* IEG `graph_version` = applied watermark vector
* OFP `input_basis` = applied watermark vector used for the snapshot
  **Where it bites:** J5–J8 (the replay spine), and any offline rebuild that claims parity.

---

### Rail R7 — End-to-end idempotency (at-least-once is assumed everywhere)

**Production truth:** Duplicates are normal; semantics must be stable under replay.

* Invocation uses an idempotency handle (`request_id`)
* IG enforces deterministic admit/duplicate/quarantine
* AL enforces effectively-once via `(ContextPins, idempotency_key)`
* DLA ingest is idempotent; labels are append-only assertions (no destructive overwrite)
  **Where it bites:** J1, J3–J4, J11–J13 (and anywhere side-effects exist).

---

### Rail R8 — Time semantics never collapse (domain vs ingest vs as-of)

**Production truth:**

* `ts_utc` is the **domain event time** (meaning)
* IG adds **ingestion time** as metadata/receipt truth
* OFP/learning use explicit **as-of time** (no hidden “now”)
* Labels carry **effective_time vs observed_time**
  **Where it bites:** J3 (ingest), J8 (feature requests), J13–J15 (labels + training).

---

### Rail R9 — Append-only truth + supersedes for corrections

**Production truth:** Ledger-like truths are append-only. Corrections happen by *new records* that supersede prior records (never silent mutation). This applies to: audit records, label timelines, run ledger facts, and registry lifecycle events.
**Where it bites:** J2 (SR ledger/join surface), J12 (DLA), J13 (Label Store), J16 (Registry lifecycle).

---

### Rail R10 — Degrade is explicit, enforced, and recorded

**Production truth:** Degrade Ladder produces an explicit mode + capabilities mask; DF treats the mask as **hard constraints**. The degrade posture used is recorded in provenance/audit (so later we can explain behavior under degraded operation). Failures in degrade evaluation fail **toward safety**.
**Where it bites:** J9 (DL→DF), J12 (audit provenance), and indirectly J8/J10/J11 (what DF is allowed to do).

---

### Rail R11 — Registry resolution is deterministic + compatibility-aware

**Production truth:** Decisioning never uses “latest.” Registry resolution returns exactly one ACTIVE bundle per scope by deterministic rules, and the resolved bundle ref is recorded in decision provenance. If bundle requirements are incompatible with available feature versions or degrade constraints, the system fails closed or routes to a defined safe fallback (but never silently proceeds).
**Where it bites:** J10 (Registry→DF), J16 (MF→Registry), and J8 (feature compatibility expectations).

---

### Rail R12 — Quarantine is first-class (no silent drops)

**Production truth:** Any boundary that rejects something must produce a quarantine outcome with evidence pointers (by-ref) so the platform can be audited and debugged. “Drop and forget” is disallowed for anything that matters.
**Where it bites:** J3 (IG), J12 (audit incomplete provenance), and any ingestion of labels/bundles/manifests.

---

### Rail R13 — Correlation is mandatory (end-to-end traceability)

**Production truth:** The platform must support end-to-end explanation: events, decisions, actions, audit, cases, labels, training runs, and bundles must be linkable through stable IDs (event_id/decision_id/action ids + ContextPins + trace fields). If you can’t trace it, you can’t operate it safely.
**Where it bites:** Everywhere events/records cross boundaries; especially J2–J4, J12–J16.

---

### Rail R14 — Governed change is explicit (no invisible behavior changes)

**Production truth:** Any change that can affect outcomes or reproducibility (deployments, config/policy changes, promotion/rollback, retention/backfills) must be expressed as auditable governance facts. “Someone changed it” is not a valid production story.
**Where it bites:** J1–J2 (run orchestration), J16 (registry lifecycle), plus Run/Operate ↔ Obs/Gov edges.

---

### Rail R15 — Feature definition/version authority is singular

**Production truth:** There is one authoritative notion of feature group definitions + versions. Online serving (OFP), offline rebuild (Shadow), dataset manifests, and deployable bundles must all refer to the same versioned feature definitions—otherwise you get training/serving drift by construction.
**Where it bites:** J7–J8 (OFP), J15 (Shadow→MF), J16/J10 (bundle compatibility + resolution).

---

## Overlay family A — Access / control

This is the “who is allowed to do what” layer. It attaches at the **choke points** where the platform can be changed or influenced.

**A1. Publish/admit is controlled at IG (the front door).**
Only authenticated/authorized producers may publish; authorization is evaluated at least by `(producer, event_type, scope)` where scope includes ContextPins where applicable. Anything unauthorized is quarantined (never silently dropped).
**Attaches to:** **J3–J4** (Producers→IG, IG↔EB).

**A2. Quarantine access is controlled and auditable.**
Reading quarantined payload/evidence and releasing/reprocessing quarantined items are privileged acts, always emitting an auditable governance fact.
**Attaches to:** **J3** primarily (and Run/Operate↔Obs/Gov).

**A3. Action execution is controlled at Actions Layer, not in UIs or DF alone.**
DF and humans may *request* actions, but only Actions Layer can *execute* them; Actions Layer must enforce an allowlist of action types and scope rules. “Manual action” is just another ActionIntent with higher privilege, not a bypass.
**Attaches to:** **J11** (DF→AL) and the Case/ops pathways.

**A4. Promotion/rollback is controlled at Registry (deployable truth).**
Who can publish bundles and who can change ACTIVE bundles is strictly controlled; those operations always emit governance facts.
**Attaches to:** **J16** (MF→Registry) and **J10** (Registry→DF resolution).

**A5. Label writes are controlled at Label Store (ground truth).**
Only trusted writers (case workflow / adjudication ingest) may write labels; label write actions are auditable, and destructive edits are disallowed (append-only truth).
**Attaches to:** **J13** (Case→LabelStore).

That’s the access/control overlay: **control happens where truth enters or outcomes change**, not scattered across components.

A deep dive: Alright — **Access/Control at the three choke points** (IG, Actions, Registry). This is the production truth overlay that keeps the platform safe and auditable, without inventing extra components.

### 1) Ingestion Gate (IG): who may introduce “decisionable facts”

**Pin:** *No identity → no admission.* Every event must have an attributable producer identity, and IG is the authority that decides whether that producer is allowed to submit that **event_type** into the platform.

* **Producer identity source (AuthN):** IG derives the producer principal from the transport identity (service account / mTLS / token) and treats the envelope’s `producer` field as the declared identity. If both exist, they must be consistent; mismatch is not “warning,” it’s **quarantine**.
* **Authorization (AuthZ) is an allowlist:** allowlist is conceptually `(producer_principal, event_type, scope)` where scope includes run/world pins when applicable (ContextPins; seed when seed-variant). If unauthorized → quarantine + receipt.
* **Outcome is always explicit:** IG never silently drops. It emits ADMIT / DUPLICATE / QUARANTINE, and the receipt records the auth outcome + reason taxonomy. 
* **Policy version is part of the audit story:** IG records *which* allowlist/policy revision it evaluated (a config/version id). (Where it’s stored is Run/Operate; the pin is: the decision must be traceable.)

Result: the hot path only sees facts that passed an explicit, attributable, policy-versioned trust boundary.

---

### 2) Actions Layer (AL): who may cause side effects

**Pin:** *Only AL executes.* Everyone else (Decision Fabric, Case UI, Ops) can only **request** actions.

* **Every ActionIntent carries an actor principal** (who requested it) and an origin (automated decision vs human/case vs ops). AL uses that identity to authorize execution.
* **Authorization is an allowlist by action type + scope:** conceptually `(actor_principal, action_type, scope)` where scope binds to ContextPins / target entity / environment. If not authorized → AL emits a **Denied ActionOutcome** (still immutable, still idempotent), and nothing executes. 
* **Idempotency remains law under control decisions:** deny/allow must be stable under retries using the same idempotency key; duplicates do not create different outcomes. 
* **Outcomes are fully attributable:** ActionOutcome records the actor principal + policy version used to authorize + the intent linkage. This is how you defend “why did we block this” later.

Result: “manual override” is not a bypass; it’s a higher-privilege ActionIntent that still goes through the same execution and audit pathway.

---

### 3) Registry: who may change deployable truth

**Pin:** *Registry is the only gate for production logic changes.* And lifecycle changes are privileged and auditable.

There are three classes of operations, each with distinct privileges:

1. **Resolve/Read (used by DF):** DF may resolve active bundle for scope; this is read permission (low privilege) but still attributable (service principal).
2. **Publish bundle (used by Model Factory):** MF may publish bundles, but publication does not automatically activate them.
3. **Lifecycle mutation (promote/activate/rollback):** privileged (human approver and/or controlled automation). Each mutation emits an append-only RegistryEvent with `actor` and `reason` (so the system can explain any change).

Also pinned from your concept: “who can perform transitions” exists as a registry concern, and exact auth mechanism is intentionally left implementation-open as long as posture + audit fields exist.

Result: production decision logic changes are never “someone swapped a file”; they’re explicit, attributable lifecycle events.

---

### The simple mental model

* **IG controls what becomes a fact.**
* **AL controls what becomes a side effect.**
* **Registry controls what becomes decision logic.**

Here are the **minimum audit “policy facts”** each choke point must emit (one line each):

**IG (admission):** `ingestion_receipt = {receipt_id, producer_principal (+declared envelope.producer), authz_policy_rev, event_id/event_type/ts_utc, (ContextPins if joinable), decision=ADMIT|DUPLICATE|QUARANTINE, reason_codes, evidence_ref -> (eb_partition,eb_offset) OR quarantine_record_ref, optional event_digest}`.

**Actions Layer (execution):** `action_outcome = {outcome_id, actor_principal, authz_policy_rev, ContextPins, action_type, idempotency_key, linked decision_id/event_id, decision=EXECUTED|DENIED|FAILED, attempt, optional evidence_refs/digests}`. 

**Registry (deployable truth):** `registry_event = {registry_event_id, actor_principal, governance_action=publish|approve|promote|rollback|retire, from_state->to_state, bundle_id + immutable refs/digests, scope, approval_policy_rev, reason, evidence_refs (eval + GateReceipt where required)}`.

---

## Overlay family B — Schema / version evolution

This is the “how we change shapes without breaking the platform” layer.

**B1. Envelope is stable; payload is versioned.**
The canonical envelope stays minimal and changes rarely; payload evolution is carried via `event_type` and/or `schema_version`. IG enforces the platform’s acceptance policy for versions.
**Attaches to:** **J3–J4** (admission) and then all consumers via EB.

**B2. Unknown/unsupported versions never silently flow into decisioning.**
If IG can’t validate a payload version under policy, it quarantines (or routes to a known-safe fallback stream). No “best effort parse” that yields partial truth.
**Attaches to:** **J3** (and by extension protects J6–J12). 

**B3. Feature definitions are versioned and singular (serving + offline + bundles must agree).**
OFP must record the feature group versions used; Offline Shadow rebuild uses those exact versions; bundles declare the feature versions they require. This is the platform’s anti-drift guarantee.
**Attaches to:** **J7–J8**, **J15**, **J16/J10**.

**B4. Registry resolution is compatibility-aware.**
Registry never resolves an ACTIVE bundle that cannot be satisfied by the currently-available feature versions and constraints (including degrade). If incompatible: fail closed or route to a defined safe fallback, but never silently proceed.
**Attaches to:** **J10** and **J9**.

**B5. Deprecation is explicit and time-bounded.**
Breaking changes require either a new `event_type` (new semantic contract) or a major payload version shift; old versions remain supported for a declared window or are explicitly quarantined.
**Attaches to:** **J3–J4** and operational governance.

That’s schema/version evolution: **IG gates version acceptance; DF consumes only compatibility-safe resolved bundles; offline parity locks versioning across training/serving.**

A deep dive: Alright — **Schema/version evolution** has two choke points in this platform:

1. **IG** decides what schema versions are *admissible facts* (what gets onto EB).
2. **Registry** decides what model/policy bundles are *compatible to execute* (what DF is allowed to use).

Below are the **designer-authoritative pins** for both.

---

## 1) Schema/version evolution at IG (admission boundary)

### SV-IG.1 — Envelope is stable; payloads evolve behind it

The **canonical envelope** is the platform’s stable outer shape (the thing IG/EB/consumers can always rely on). Payload schemas evolve per `event_type` and `schema_version`, but the envelope’s required fields remain minimal and long-lived.

### SV-IG.2 — Every admitted event must declare schema identity

An admitted event must be classifiable as:
`(event_type, schema_version)` plus the envelope core (`event_id`, `ts_utc`, `manifest_fingerprint`). If `schema_version` (or equivalent) is absent, IG treats that as **not admissible** unless the platform explicitly defines a default for that event_type (defaulting is dangerous; safest v0 posture is “must declare”).

### SV-IG.3 — Admission policy is explicit allowlist per event_type + version range

IG maintains an **explicit acceptance policy** for each `event_type`:

* allowed `schema_version` range(s),
* whether unknown fields are permitted,
* whether coercions/normalizations are permitted (generally: no “semantic repairs,” only safe mechanical normalization like field renames if explicitly pinned).

If an event_type/version is not allowed → **quarantine with receipt** (never silently drop, never “best effort parse”).

### SV-IG.4 — Forward-compatibility is additive-only; breaking changes are new versions or new types

The platform posture is:

* **Additive changes** (new optional fields) are forward-compatible.
* **Breaking changes** (changing meaning, changing required fields, changing units, changing key semantics) must be a **new schema_version** (or even a new `event_type` if semantics fundamentally change).

IG enforces this by validating required fields and rejecting/ quarantining incompatible versions.

### SV-IG.5 — Unknown versions don’t flow into decisioning

If IG can’t validate `(event_type, schema_version)` under policy, it doesn’t “let it through and hope downstream copes.” It quarantines. That’s how you prevent subtle production drift and “shadow schema” behavior. 

### SV-IG.6 — IG receipts must capture schema facts

To make schema evolution operable, the IG receipt must record (at minimum):

* `event_type`, `schema_version`,
* validation outcome (pass/fail),
* the acceptance policy revision used (so you can later explain “why was v3 rejected yesterday but admitted today?”).

(Implementation detail of where that policy revision lives is Run/Operate; the pin is: it’s traceable.)

---

## 2) Registry compatibility (what DF is allowed to execute)

### SV-R.1 — Bundles declare compatibility; DF never guesses

Every deployable bundle in the Registry must declare a **compatibility contract** so DF can make a safe choice deterministically. At minimum, compatibility must cover:

* **Feature definition dependencies**: which FeatureGroup set + versions the bundle expects (this is the big one; it prevents training/serving drift by construction).
* **Required capabilities**: the minimum capabilities the bundle requires (so degrade can disable bundles safely).
* **Input contract version** (conceptually): the version of DF↔bundle interface the bundle expects (even if it’s implicit v0 now, it becomes explicit as you evolve).

### SV-R.2 — Registry resolution is compatibility-aware (not just “ACTIVE”)

Registry resolution must not return a bundle that is ACTIVE-but-incompatible with the currently available platform context. “ACTIVE” is necessary, not sufficient.

Compatibility checks at resolution time include:

* requested scope resolves to one ACTIVE bundle,
* DF/OFP can satisfy required feature groups/versions,
* degrade posture allows required capabilities.

If incompatible, the system **fails closed or routes to an explicitly defined safe fallback** (but never silently proceeds with a half-compatible bundle).

### SV-R.3 — DF must record the resolved bundle and compatibility basis

Decision provenance must include:

* the resolved bundle ref (id + digest posture),
* the feature group versions actually used (from OFP),
* degrade posture in force.

This is what makes decisions explainable and replayable after rollouts.

### SV-R.4 — Compatibility is also enforced at promotion time

When Model Factory publishes/promotes a bundle, Registry requires the bundle to ship the compatibility metadata + evidence (eval results, lineage, gate receipts if required). Promotion without compatibility metadata is not “allowed but discouraged”; it’s **not a valid deployable artifact**.

---

## The two operational “moves” this enables (without extra system complexity)

### Move 1: Rolling schema changes on the bus

* Producers dual-emit old+new versions (or upgrade in place if additive).
* IG allowlists both versions during the migration window.
* Consumers can be upgraded gradually because the envelope is stable and validation is enforced at IG.

### Move 2: Rolling model/policy changes safely

* Model Factory publishes bundle + compatibility contract + evidence.
* Registry promotes bundle to ACTIVE only via governed lifecycle action.
* DF always resolves deterministically and can refuse incompatible bundles under degrade or feature mismatch.

---

## Overlay family C — History / backfill

This is the “what happens when time passes” layer: retention ends, late facts arrive, you need replay beyond the bus.

**C1. Archive is a logical extension of EB, not a separate truth.**
When EB retention ends, the archive is treated as the continuation of the admitted fact stream (same envelope semantics, same event identity). Offline Shadow may read from EB or archive, but must record which source and basis.
**Attaches to:** **J14** (and relies on J5 watermark semantics).

**C2. Backfill is never silent; it is declared and auditable.**
Any backfill/reprocess that can change derived truths (IEG projections, feature aggregates, datasets, parity results) must be explicitly declared (who/why/scope/basis) and produces outputs that are versioned/traceable—not stealth overwrites.
**Attaches to:** **J14–J16**, and Run/Operate↔Obs/Gov.

**C3. Watermarks remain monotonic even under backfill.**
Consumers never “go backward.” New arrivals/backfilled facts create new offsets; derived versions advance. If you rebuild “as-of time T,” you rebuild using an explicit basis (offset/window) and label as-of rules, not by pretending the stream changed history.
**Attaches to:** **J5–J8** and **J14**.

**C4. Dataset manifests must pin the history basis.**
Any dataset used for training/eval must carry the exact replay basis (offset ranges/windows) and as-of boundaries so it can be reproduced later even after retention changes.
**Attaches to:** **J15** (Shadow→MF) and **J16** (MF→Registry evidence).

That’s history/backfill: **archive is the continuation of facts; backfills are declared; watermarks don’t lie; dataset manifests pin replay basis.**

---

### What you’ll see next when we “dive deep”

We can now go family by family and pin the few decisions that matter most (still minimal, no doc explosion). If you want the most leverage first, we start with:

1. **Access/control at IG + Actions + Registry** (because it’s production safety), then
2. **Schema/version evolution at IG + Registry compatibility**, then
3. **History/backfill at archive + manifests**.

---

A deep dive: Alright — **History/backfill at archive + manifests**.

This overlay family answers: *when time passes, retention expires, late facts arrive, or you need to recompute—how do we keep truth reproducible and auditable?*

## H1 — Archive is a continuation of EB, not a second truth

**Production truth:** The archive is the **long-horizon extension** of the admitted event stream. It preserves the **same logical events** (same `event_id`, same envelope semantics) as EB; it is not a different “dataset of events.”

* EB is the hot retention window; archive is the cold long window.
* Consumers that replay beyond EB retention do so from archive **as if it were EB**, and they record the basis used.

**Attaches to:** J14 (Offline Shadow inputs), and everything that depends on replay determinism (J5–J8).

---

## H2 — Replay basis is always explicit (no “grab all history”)

**Production truth:** Any rebuild/training dataset creation must declare its **replay basis** explicitly:

* either as offset ranges per partition (preferred where available),
* or as time windows that are anchored to offsets via recorded checkpoints/watermarks.

Meaning: “we trained on last 90 days” is not enough — it must be “last 90 days **as defined by these offsets/checkpoints**.”

**Attaches to:** J14 (Shadow reads), J15 (Manifest), J16 (bundle evidence).

---

## H3 — Backfill is declared and auditable (never silent)

**Production truth:** Any operation that changes derived outputs (features, projections, datasets, parity results, metrics) must be a **declared backfill** with:

* scope (which streams/partitions/time windows),
* reason,
* who initiated,
* and what outputs were re-derived.

Backfill does not “edit history.” It produces new derived artifacts and leaves an audit trail.

**Attaches to:** J14–J16, and Run/Operate ↔ Obs/Gov.

---

## H4 — Watermarks don’t lie (monotonic progress even under backfill)

**Production truth:** Consumers treat applied offsets/watermarks as **monotonic**. Backfills and late arrivals don’t cause “time travel”; they create new offsets and therefore new watermark states. If you need a historical rebuild “as-of time T,” you use an explicit replay basis rather than pretending the stream changed.

This is what keeps:

* `graph_version` meaningful,
* `input_basis` meaningful,
* and parity checks reproducible.

**Attaches to:** J5–J8 and J14.

---

## H5 — DatasetManifest is the pinned bridge artifact for learning

**Production truth:** DatasetManifests are not optional paperwork — they are the *unit of reproducibility*.

A DatasetManifest must pin enough to rebuild the dataset later:

* replay basis (offset ranges/checkpoints + stream identities),
* label as-of boundary (effective/observed time posture),
* join keys + entity scope,
* feature definition versions used,
* digests/refs to materializations,
* and provenance (pipeline version/config).

**Attaches to:** J15 (Shadow→MF), J16 (MF→Registry evidence), and (indirectly) J6–J8 parity.

---

## H6 — Late labels are normal; “as-of” makes them safe

**Production truth:** Labels arrive late and can be corrected. Training joins must use Label Store’s **as-of** semantics so you can produce:

* “what we knew then” datasets (for honest evaluation),
* and “what we know now” datasets (for improved training),
  without confusing the two.

**Attaches to:** J13–J15.

---

### The one-sentence overlay pin for History/Backfill

**Archive extends EB’s admitted fact stream; all rebuilds/training datasets declare an explicit replay basis; backfills are declared and auditable; watermarks remain monotonic; and DatasetManifests pin the exact history/label/feature-version basis so learning and deployment are reproducible even after retention and late truth changes.**
