# Decision Fabric Design Authority

This file is a rough collection of design or brainstorm notes for the Decision Fabric. It views the whole platform as a network and expands open the decision fabric's position in this network and illuminates it.

---

Alright — we’ll treat **DF’s inner network as opaque** for now and pin DF’s **outer role** as a vertex inside the already-pinned platform graph. Everything below is **designer-authoritative for this brainstorm**, and it must not violate: **ContextPins**, **Canonical Event Envelope**, **no hidden time**, **by-ref truth**, **at-least-once safety**, **watermarks**, **explicit degrade**, **IG as trust boundary**, and the **hot-path join definitions** you’ve already pinned.   

---

## DF’s role in the larger network

### DF exists to answer one question, one way

**Given an admitted event, what do we decide and what do we intend to do — under an explicit degrade posture — with enough provenance to replay/explain later?**  

### DF is system-of-record for (and only for)

DF is authoritative for:

* **Decision outcome** (what we decided)
* **Action intents** (what we plan to do; not execution)
* **Decision provenance** (what inputs/basis/posture were used)  

DF is *not* authoritative for:

* event admission validity (IG)
* durable append/replay semantics (EB)
* identity truth (IEG)
* feature computation (OFP)
* side-effect execution (AL)
* audit record storage rules (DLA) 

---

## DF as a black box: the boundary contract (conceptual, but pinned)

### Inputs DF is allowed to rely on

#### 1) Primary stimulus: an **admitted event** (from EB)

* DF consumes events **after IG admission**; EB delivery is **at-least-once** (duplicates/out-of-order are real). 
* The event boundary is **CanonicalEventEnvelope** with required fields `{event_id, event_type, ts_utc, manifest_fingerprint}`. Optional pins may exist (`parameter_hash`, `scenario_id`, `run_id`, `seed`).  
* DF must treat `ts_utc` as **domain event time** (not “now”). 

**Designer pin DF-B1 (trigger eligibility):** DF only “decision-triggers” on an allowlist of event families (e.g., `transaction_*`); it must not re-consume its own decision/action output event types (loop prevention). EB may contain many event types; DF must be selective.  

#### 2) Required control input: **DegradeDecision** (from DL)

* DL provides `mode` + `capabilities_mask` + provenance. DF must treat the mask as **hard constraints** (not advice). 
* If DL is unavailable/invalid, DF must fail **toward safety** (stricter posture) and record the fallback. 

#### 3) Required policy selection input: **ActiveBundleRef** (from Registry)

* Registry returns a deterministic “what should I use for this decision right now?” answer (no “latest”). 
* Compatibility is enforced at this join: if bundle is incompatible with degrade mask or feature definitions, DF falls back safely and records why. 

#### 4) Optional context input: **IEG** (only if allowed by degrade)

* When used, DF must record the `graph_version` used for context.  

#### 5) Optional feature input: **OFP snapshots** (only as allowed by degrade)

* DF calls OFP with **as_of_time_utc = event_time** (no hidden “now”). 
* DF records OFP provenance: `feature_snapshot_hash`, group versions, freshness, and `input_basis` watermark vector (and `graph_version` if IEG was consulted). 

---

### Outputs DF must produce

#### A) **DecisionResponse** (authoritative decision artifact)

This is the unit DLA treats as the non-negotiable base for audit ingest. 

**Designer pin DF-B2:** DecisionResponse must be *joinable and replay-defensible* without embedding raw payload:

* by-ref pointer to the event basis (`event_ref` or equivalent)
* degrade posture used
* active bundle ref used
* OFP snapshot hash + `input_basis` (+ `graph_version` if used)
* decision outcome + actions + action idempotency keys  

#### B) **ActionIntent(s)** (for AL)

* DF declares what should be done; **AL executes** and enforces effectively-once via `(ContextPins, idempotency_key)`. 
* Duplicate intents must never re-execute; they re-emit canonical outcome. 

#### C) Publication path: DF outputs are “producer traffic”

DF outputs are “real traffic” and must enter the fact log via the trust boundary: **DF → IG → EB**, not side-channels. 

(Implementation may publish “directly” to the bus, but **semantically** it must be equivalent to going through IG admission rules; otherwise the platform loses its single trust boundary posture.) 

---

## How DF operates in the larger network

### DF’s hot-path operating loop (externally observable)

For each eligible admitted event:

1. **Frame the decision boundary**

* Input identity: `event_id`, `event_type`, `event_time = ts_utc`, `manifest_fingerprint`
* Join pins: **ContextPins** `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` must be present for run-joinable decisions.  

2. **Fetch DegradeDecision and enforce it (hard constraint)**

* Degrade governs what DF *is allowed to do* (call IEG? call OFP? which feature groups? which action postures?). 

3. **Resolve ActiveBundleRef**

* Deterministic, compatible with current degrade + feature definition posture; record it. 

4. **Acquire context/features conditionally**

* If allowed, consult IEG (record `graph_version`). 
* If allowed, consult OFP (with `as_of_time_utc = event_time`) and record snapshot provenance (`feature_snapshot_hash`, versions, freshness, `input_basis`). 

5. **Produce DecisionResponse + ActionIntents**

* Outcome + intents must be deterministic given the captured posture/bundle/snapshot basis. 

6. **Publish outputs as envelope events**

* Use Canonical Event Envelope at the boundary; preserve/propagate ContextPins; do not overwrite domain time.  

7. **Downstream consequences**

* AL executes intents effectively-once. 
* DLA ingests DecisionResponse; quarantines incomplete provenance; corrections use supersedes chain (no overwrites). 

---

## The crucial interaction semantics per neighbor

### EB → DF: at-least-once stimulus, by-ref basis

**Designer pin DF-E1:** DF treats the admitted event as immutable fact input; duplicates are expected. DF must be safe under replay/redelivery.  

### DL → DF: explicit degrade, fail-closed

**Designer pin DF-E2:** “No bypass” is literal. If `allow_ieg=false`, DF behaves as if IEG doesn’t exist; same for OFP groups/models/actions. If DL is down, DF tightens posture and records it. 

### Registry → DF: deterministic bundle resolution, compatibility enforcement

**Designer pin DF-E3:** DF never picks “latest.” It uses Registry resolution and records the resulting bundle ref. If incompatible with degrade or feature definitions, DF chooses safe fallback and records why. 

### OFP/IEG ↔ DF: “what DF knew” must be reproducible

**Designer pin DF-E4:** DF always calls OFP with `as_of_time_utc = event_time` and records OFP’s `input_basis` and `feature_snapshot_hash` (and `graph_version` if relevant). This is the bridge for offline parity later. 

### DF → AL: intents only, effectively-once is downstream

**Designer pin DF-E5:** DF emits ActionIntents with deterministic `idempotency_key`, and AL enforces uniqueness via `(ContextPins, idempotency_key)`; duplicates never re-execute. 

### DF (+ optional AL evidence) → DLA: audit is evidence-first

**Designer pin DF-E6:** DF’s DecisionResponse must include enough by-ref + hashed pointers for DLA to record a complete immutable audit fact. If DF provenance is incomplete, DLA quarantines rather than writing a “half-truth.” 

---

## Two designer pins we must settle now (because they shape everything downstream)

### Pin 1: DF’s authoritative ingress mode

Deployment notes allow “bus or synchronous decision API requests.” 

**Designer decision DF-P1:** For v0, DF’s *authoritative* decisions are **EB-driven only**.
If a synchronous Decision API exists, it must either:

* be **non-authoritative preview** (no ActionIntents, no audit truth), **or**
* be a thin producer that **submits the request as an event through IG → EB** and returns a correlation handle (so the authoritative decision still happens via EB). 

This preserves the platform’s single “fact entry” posture and replayability.

### Pin 2: ActionIntent idempotency key recipe (safety against conflicting duplicates)

Platform pins that AL uniqueness is `(ContextPins, idempotency_key)` but says key recipes live locally.  

**Designer decision DF-P2 (safer than action_type-only):**
`idempotency_key = H(ContextPins, event_id, action_domain)`
Where `action_domain` is coarse (“txn_disposition”, “auth_stepup”, “case_queue”, etc.).
Reason: if duplicates/retries ever produce different action types, a domain-key prevents multiple conflicting side-effects from executing for the same event. This is the cleanest way to remain safe under at-least-once delivery without requiring DF to be stateful.  

(We can still include `action_type` inside the intent payload; we’re only pinning the uniqueness key.)

---

## DF’s safe failure posture (outer expectation)

This is not “model logic,” it’s **platform safety law** for DF:

**Designer pin DF-S1:** If DF cannot decide safely (missing required degrade decision, required bundle resolution fails, required OFP features unavailable when needed), DF must:

* fail toward safety, and
* emit conservative intents (e.g., step-up / review posture), and
* record *why* (dependency error + retryable flag) in provenance.  

---

Yes — **before joins**, there are a few **DF identity pins** that are worth locking, because otherwise every join (DL/OFP/IEG/AL/DLA/EB) ends up arguing from different implicit assumptions.

Below are the **minimal “DF-as-a-vertex” pins** I would set now (designer-authoritative for v0).

---

## DF pins to lock before joins

### DF-P0 — DF’s authority surface (what it *is*)

DF is system-of-record for **DecisionResponse + ActionIntents + DecisionProvenance**, and *only* those. It never becomes admission authority, feature authority, identity authority, execution authority, or audit storage authority.  

### DF-P1 — Authoritative ingress mode

**Authoritative decisions are EB-driven.** If you expose a synchronous “Decision API”, it is either:

* a non-authoritative preview, or
* a thin wrapper that submits a request through **IG → EB** and returns a handle.
  Reason: your platform pins EB as the durable fact log and IG as the trust boundary; letting authoritative decisions happen “off-bus” creates two realities.  

### DF-P2 — One decision unit per stimulus

For v0, DF processes **one eligible admitted event → one DecisionResponse + 0..N ActionIntents**.
No “batch decisioning” and no implicit aggregation windows (those belong in OFP/IEG). This keeps replay/offset reasoning clean.  

### DF-P3 — Trigger allowlist + loop prevention

DF only triggers on an explicit allowlist of **business-driving event types**, and must not treat:

* its own DecisionResponse/ActionIntent events, or
* AL outcomes,
  as new decision triggers (unless explicitly whitelisted later). This prevents accidental feedback loops.  

### DF-P4 — Time semantics are non-negotiable

DF’s decision boundary time is **`event_time = ts_utc`** from the canonical envelope, and OFP calls must use **`as_of_time_utc = event_time`**. No hidden “now.”

### DF-P5 — Hard vs conditional dependencies

* **Required every time:** DL (DegradeDecision) + Registry (ActiveBundleRef).
* **Conditional:** IEG/OFP are used only if allowed by the degrade mask (and if required inputs are missing, DF fails-safe).
  This matches your pinned “mask is hard constraints” rule and avoids silent coupling.

### DF-P6 — Determinism target (what must be replay-stable)

Given the same:

* admitted event (envelope + payload),
* DegradeDecision (mode + mask),
* ActiveBundleRef,
* OFP snapshot provenance (`feature_snapshot_hash`, `input_basis`, group versions/freshness),
* and `graph_version` (if IEG used),
  DF must produce the **same DecisionResponse and ActionIntents** (byte-stable ordering). This is the “offline parity bridge” your platform already pins.

### DF-P7 — Output publication posture

DF outputs are **canonical envelope events** and enter the durable record via the trust boundary semantics: **DF → IG → EB** (even if implemented as a direct publish, the semantics must match IG admission/dedupe/quarantine posture).

### DF-P8 — Output identity + idempotency anchors (don’t leave this implicit)

The envelope explicitly requires a stable `event_id` for dedupe/idempotency. 
So we should pin **deterministic identities** for DF outputs:

* DecisionResponse event_id = `H(ContextPins, input_event_id, "decision")`
* ActionIntent event_id = `H(ContextPins, input_event_id, "intent", action_domain)`
  …and ActionIntent carries its own `idempotency_key` for AL’s uniqueness scope.

*(This keeps DF safe under EB redelivery + DF retries, without requiring DF to persist a “decisions DB.”)*

### DF-P9 — Fail-safe posture (what happens when DF can’t know enough)

If DF can’t decide safely (DL unavailable, bundle incompatible, required features missing/stale beyond allowance), DF must:

* choose the pinned safe outcome (e.g., step-up/review posture),
* emit intents consistent with the degrade mask,
* and record the failure reason + retryability in provenance.

### DF-P10 — No truth leakage rule (closed-world hygiene)

DF must never treat engine **truth_products/audit_evidence/ops_telemetry** as decision-driving input. Only **business_traffic** flows into EB as traffic and can influence DF directly.

---

If we lock only these pins, we can brainstorm joins without drift because we’ll already know:

* what counts as a DF “request,”
* what DF must output,
* what DF is allowed to depend on,
* how replay/idempotency works,
* and what “safe failure” means.

---

Below is the **complete join / path / loop inventory** around **Decision Fabric (DF)** **while keeping DF opaque** (a black box). Everything listed is either explicitly in the platform blueprint/deployment notes or is a direct consequence of those pins (trust boundary, replay tokens, by-ref evidence, explicit degrade, learning loop).

---

## 1) All direct joins touching DF (DF’s neighborhood)

### A) Data-plane joins (hot path)

1. **EB → DF** *(primary stimulus)*
   Admitted canonical-envelope events delivered **at-least-once** with partition/offset replay coordinates.

2. **DL → DF** *(hard constraints)*
   `DegradeDecision = {mode, capabilities_mask, provenance}`; mask is **hard constraints**; fail-closed if DL unavailable.

3. **Registry → DF** *(active policy/model selection)*
   Deterministic **ActiveBundleRef** resolution; DF records bundle ref; incompatibility ⇒ safe fallback + record why.

4. **OFP → DF** *(feature snapshot)*
   DF requests snapshots using **as_of_time_utc = event_time** and receives `feature_snapshot_hash`, group versions, freshness, and `input_basis` watermark vector (plus `graph_version` if IEG consulted). DF must record this provenance.

5. **IEG → DF** *(identity/graph context, conditional)*
   IEG is a run/world-scoped projection; when used, DF records the `graph_version` (derived from applied watermark vectors).

6. **DF → IG** *(DF as a producer)*
   DF emits **DecisionResponse + ActionIntents** as canonical envelope events **through the trust boundary** (admit/duplicate/quarantine + receipts).

7. **IG → (EB)** *(durable append)*
   “ADMITTED” means durably appended; EB is the replayable fact log; offsets are the universal replay tokens.

8. **(EB) → AL** *(AL consumes intents)*
   AL executes intents effectively-once using `(ContextPins, idempotency_key)` and emits immutable **ActionOutcomes** back as traffic via IG→EB.

9. **(EB) → DLA** *(audit flight recorder)*
   DLA consumes decisions/intents/outcomes + IG evidence pointers; writes append-only audit records; quarantines incomplete provenance; corrections via supersedes chains.

### B) Control-plane joins that constrain DF in production

10. **Obs/Gov → DL → DF** *(safety corridor loop)*
    DL is fed by observability signals (lag/errors/etc.) and can emit posture changes (optionally onto control bus).

11. **Run/Operate → DF (operational control)** *(start/stop/drain/config activation)*
    Run/Operate owns lifecycle operations; outcome-affecting ops must emit governance facts (no silent changes).

12. **Registry lifecycle events → DF (optional subscription / cache invalidation)**
    Registry emits lifecycle events (control bus); DF may subscribe to avoid polling, but semantics remain “deterministic active resolution + record bundle ref.”

### C) Optional ingress join (allowed by notes, but must not create a second reality)

13. **External caller → DF (Decision API requests)** *(optional)*
    Notes allow “synchronous decision API requests” as a possible DF input, but if used **authoritatively**, it must align with the IG→EB truth posture (otherwise you create two decision realities).

---

## 2) All production paths DF participates in (multi-hop sequences)

### Path P1 — Core hot decision path (the one every “production-ready” run exercises)

```
Producer traffic (engine streams / external txn / etc.)
  -> IG (admit|duplicate|quarantine + receipts)
  -> EB (durable append + replay coords)
  -> DF (consumes admitted events)
     -> (calls DL + Registry + OFP + optional IEG)
     -> emits DecisionResponse + ActionIntents
  -> IG -> EB
  -> AL (executes intents) -> IG -> EB (ActionOutcomes)
  -> DLA (records decision + intent + outcome + evidence pointers)
```

This is exactly your pinned “front door + durable log + hot path + audit recorder” chain.

### Path P2 — World/run gating path that *indirectly* controls DF’s reality

```
RunRequest -> SR -> Engine (invoke/reuse)
  -> SR verifies PASS gates
  -> SR publishes run_ready_signal + run_facts_view (join surface)
  -> IG uses run context to enforce joinability (READY runs get admitted traffic)
  -> EB -> DF ...
```

DF may never “choose a world,” but **its upstream reality is shaped by SR’s READY + IG joinability enforcement**.

### Path P3 — Decision → Case → Labels (human truth loop)

```
DF/AL/DLA pointers
  -> Case Workbench (immutable timelines)
     -> Label Store (append-only label assertions; effective_time vs observed_time)
```

DF doesn’t write labels; it produces the evidence trail that humans use to label.

### Path P4 — Learning / evolution path (offline model loop)

```
EB history (+ archive when retention expires) + DLA exports + Label Store (as-of)
  -> Offline Feature Shadow (rebuilds deterministic datasets/snapshots)
  -> Model Factory (training/eval + evidence/PASS posture)
  -> Registry (bundle publish + governed activation)
  -> DF uses Registry active resolution in hot path
```

This is the **closed loop** that changes DF behavior *only* via governed bundle activation.

### Path P5 — Degrade/safety control path (explicit operational feedback loop)

```
Obs/Gov signals (lag/errors/SLO corridor)
  -> DL computes degrade posture (mode + mask; fail-closed)
  -> DF obeys mask (hard constraints) and records posture in provenance
  -> DLA makes posture-visible in audit; Obs/Gov monitors outcomes
```

This is your “no silent coupling” safety loop.

### Path P6 — Backfill / replay operations that affect DF *only via derived state*

```
Run/Operate declares backfill (scope/basis/outputs) + governance facts
  -> rebuilds derived stores (IEG projection, OFP state, offline datasets, audit indexes)
  -> DF sees new IEG/OFP bases (new graph_version / input_basis) on future decisions
  -> primary truths (EB events, labels, registry history, SR ledgers, engine outputs) are never silently mutated
```

This matters because it’s how “production” stays reproducible under retention/late data/bug fixes.

### Path P7 — Optional synchronous request path (only safe in one of two forms)

* **Preview-only:** Caller → DF → returns non-authoritative preview (no intents/audit truth).
* **Authoritative:** Caller → IG→EB (as a canonical event) → DF → IG→EB → AL/DLA.
  This is the only way to avoid splitting “what happened” into bus vs non-bus worlds.

---

## 3) All meaningful loops (cycles) involving DF

### Loop L1 — Action closure loop (automated)

**EB event → DF decision → ActionIntent → AL outcome → EB**
Whether the loop re-triggers DF depends on your trigger allowlist, but the *cycle exists* structurally in production.

### Loop L2 — Human supervision loop

**Decision evidence → Case Workbench → Label Store → Offline Shadow → Model Factory → Registry → DF**
This is the “learning changes decisioning” loop, explicitly mediated by governed activation.

### Loop L3 — Safety/degrade loop

**Outcomes/lag/errors → Obs/Gov → DL → DF posture → outcomes/lag/errors**
Crucially: the control signal is explicit and auditable (not implicit behavior drift).

### Loop L4 — Quarantine remediation loop (trust-boundary loop)

**Producer emits → IG quarantines → operator/policy/governance change → IG admits → EB → DF**
Quarantine is first-class; remediation must be explicit and governed (no silent “fixup”).

### Loop L5 — Backfill/rebuild loop (derived-state correction loop)

**Bug/schema/feature-definition change → Run/Operate declares backfill → rebuild OFP/IEG/offline datasets → DF uses new bases**
Primary facts don’t change; only derived views get rebuilt, with explicit basis/provenance.

### Loop L6 — Audit completeness loop

**DF emits decision → DLA ingests OR quarantines on missing provenance → fix/republish/supersedes chain**
Audit refuses “half-truths,” forcing the system to converge via explicit correction.

---

## 4) “Looks like a loop, but forbidden” (drift traps)

These are *not* “possible” in a production-ready platform under your pins:

* **DF ← engine truth_products/audit_evidence/ops_telemetry** as decision-driving inputs (only business_traffic may influence decisioning directly).
* **DF bypasses IG/EB** for authoritative outputs (breaks single trust boundary + replayable fact log).
* **DF uses hidden “now”** instead of `ts_utc`/explicit as-of time for feature context. 
* **Backfill “mutates history”** (EB events / label timelines / registry history / SR ledgers / engine outputs).

---

Here’s the **order to expand** the full DF **production** outer-network map (keeping DF opaque), structured so we lock **atomic joins first**, then **composed paths**, then **loops/cycles** (which mostly reuse the paths).

## A) Joins (atomic handshakes) — expand in this order

**J1. EB → DF** (stimulus: admitted canonical-envelope events + replay coords)
**J2. DL → DF** (DegradeDecision: mode + capabilities_mask; hard constraints) 
**J3. Registry → DF** (ActiveBundleRef resolution + compatibility) 
**J4. OFP → DF** (feature snapshot as-of `ts_utc`; returns snapshot hash + `input_basis`)
**J5. IEG → DF** (identity/graph context; `graph_version` capture) 
**J6. DF → IG** (publish DecisionResponse + ActionIntents; admit/dup/quarantine semantics) 
**J7. IG → EB** (durable append + replay tokens) 
**J8. EB → AL** (AL consumes ActionIntents)
**J9. AL → IG → EB** (ActionOutcomes back onto the log)
**J10. EB → DLA** (audit ingest of decisions/intents/outcomes + evidence pointers)

**Control-plane joins (still production, but after data-plane):**
**J11. Obs/Gov → DL** (signals that drive degrade posture)
**J12. Run/Operate → DF** (lifecycle ops: drain/backfill controls; governed changes)
**J13. Registry → DF (lifecycle events)** (optional subscription/cache invalidation)
**J14. External caller → DF (optional Decision API)** (must not create a second “truth world”)

---

## B) Paths (multi-hop sequences) — expand in this order

**P1. Core hot decision path** (Producer→IG→EB→DF→IG→EB→AL→IG→EB→DLA)
**P2. Run/world gating path** (SR READY + run_facts_view shaping what DF can ever see)
**P3. Degrade/safety control path** (Obs/Gov→DL→DF posture→outcomes→Obs/Gov)
**P4. Quarantine remediation path** (IG quarantine→operator/governance action→admit→EB→DF)
**P5. Decision → Case → Label path** (evidence→Case Workbench→Label Store timelines)
**P6. Learning/evolution path** (EB+DLA+Labels→Offline Shadow→MF→Registry→DF)
**P7. Backfill/rebuild path (derived state)** (Run/Operate→rebuild IEG/OFP/offline→DF sees new bases)
**P8. Optional synchronous request path** (preview-only or event-submitted authoritative path)

---

## C) Loops (cycles) — expand in this order

**L1. Action closure loop** (EB→DF→Intent→AL→Outcome→EB)
**L2. Safety/degrade loop** (outcomes/lag/errors→DL→DF posture→outcomes/lag/errors)
**L3. Quarantine remediation loop** (quarantine→fix/govern→admit→replay)
**L4. Audit completeness loop** (DLA quarantine/supersedes chain to converge on complete evidence)
**L5. Human supervision loop** (decisions→cases→labels→learning→registry→DF)
**L6. Backfill/rebuild loop** (derived-state correction→new bases→parity/audit visibility)

---

Absolutely — we’ll expand **J1–J5** as **production joins** around an **opaque DF** (black box), and we’ll pin the semantics that prevent drift.

I’ll treat the following as *hard platform law* for these joins: **Canonical Event Envelope**, **ContextPins discipline**, **at-least-once + offsets/watermarks**, **explicit degrade (hard mask)**, **deterministic registry resolution**, **as-of is explicit**, and **provenance must carry basis tokens**.

---

## J1 — Event Bus → Decision Fabric (EB → DF)

### Why this join exists (DF’s “stimulus”)

EB is the durable replay log; DF is an always-on consumer. **DF only decides on admitted facts delivered by EB.** EB is not a validator/transformer; admission truth was decided upstream by IG.

### What crosses the join

**DF receives two layers of information:**

1. **The canonical event itself (envelope + payload)**
   Anything admitted must conform to the **Canonical Event Envelope**, whose required fields are:

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` 

Optional but common pins:

* `parameter_hash`, `scenario_id`, `run_id`, `seed` 

Versioning/tracing fields:

* `schema_version`, `trace_id`, `span_id`, `producer`, `parent_event_id`, plus `payload` object 

2. **The EB position (the replay token)**
   EB’s universal position is **(stream_name, partition_id, offset)**; ordering is only within a partition; delivery is **at-least-once** (duplicates/redelivery are normal).

**Pinned checkpoint semantic:** a consumer’s checkpoint `offset` is the **next offset to read/apply (exclusive-next)**. This is the watermark basis everywhere.

### What DF is allowed to assume (because IG already enforced it)

* Events reaching DF are **admitted** (durably appended) and **joinable** to a valid run context when they claim run/world participation (else IG would quarantine/hold).
* Unknown/unsupported `(event_type, schema_version)` should not flow into decisioning; IG quarantines instead.

### What DF must do at this boundary (even though DF is “opaque”)

These are **boundary behaviors**, not internal pipeline design:

**J1-PIN A — DF must treat EB input as immutable fact and be replay-safe.**
Because EB is at-least-once, DF must expect duplicates and redelivery and must not “double-act” on retries. Replay-safety is mandatory platform-wide.

**J1-PIN B — DF’s decision boundary time is `ts_utc` (domain time).**
We do not collapse time semantics; `ts_utc` is the meaning-bearing time; ingestion/apply times are separate concepts and must not overwrite it.

**J1-PIN C — DF must construct and carry an explicit event basis reference.**
At minimum, DF needs a by-ref pointer to *what it decided on*:

* `event_id` (envelope identity) + EB coordinates `(stream, partition, offset)`
  This is the by-ref audit/replay anchor later.

**J1-PIN D — Trigger allowlist + self-loop protection.**
DF must only “decision-trigger” on an allowlist of event families (e.g., business traffic types). DF must not accidentally treat its own outputs (decision/action events) as triggers unless explicitly whitelisted later (or you create uncontrolled feedback loops).

### Failure / edge cases at J1

* **Duplicate deliveries:** DF re-sees same `event_id` and/or same EB position; DF must produce stable outputs under replay.
* **Out-of-order by `ts_utc`:** EB order ≠ time order; DF must respect `ts_utc` as boundary time (especially for OFP as-of calls later).
* **Schema evolution:** If an admitted event still lacks required payload fields for DF’s decision logic, DF cannot pretend; it must go to fail-safe posture downstream and record the mismatch (IG guarantees envelope validity; it doesn’t guarantee DF can interpret every payload).

---

## J2 — Degrade Ladder → Decision Fabric (DL → DF)

### Why this join exists

DL exists to prevent silent coupling under stress. **DF must not “self-degrade” implicitly; it must obey an explicit posture and record it.**

### What crosses the join

A **DegradeDecision** that is:

* explicit,
* deterministic/recordable,
* and includes at minimum: `mode`, `capabilities_mask`, and provenance (plus decided-at timestamp / optional decision id).

### The non-negotiable semantics (pins)

**J2-PIN A — The mask is hard constraints, not advice.**
If capability is off, DF behaves as if the tool/model/feature/action **does not exist**. No bypass.

**J2-PIN B — DF must record the exact DL snapshot used per decision.**
Not “current mode,” but “mode used for this decision.” That’s how audit/replay remains meaningful.

**J2-PIN C — Fail toward safety (fail-closed).**
If DL is unavailable/invalid, DF tightens posture (stricter constraints) and records the fallback reason.

### What DF needs from DL operationally (still join-level)

This is the minimal “production-ready” handshake expectation:

* **Access pattern can be pull or push**, but outcome must be the same:

  * Pull: DF asks DL for a decision at decision-time.
  * Push: DL publishes posture updates and DF uses latest known one.
* **Either way:** the DegradeDecision must have an identity (explicit token or decided-at) so DF can cite exactly what it used.

### Edge cases at J2

* **Rapid posture changes:** DF may process sequential events under different postures; that’s fine — but only if each decision cites the posture used. 
* **Mask restricts OFP/IEG:** DF must treat “disallowed” differently from “unavailable” (both are recorded, but one is a policy safety choice, the other is an outage).

---

## J3 — Model/Policy Registry → Decision Fabric (Registry → DF)

### Why this join exists

Registry is **deployable truth**: it is the only place production decision logic changes become active. DF must be able to answer “what changed?” by pointing to a registry lifecycle event and bundle reference.

### What crosses the join

An **ActiveBundleRef**: a deterministic answer to “what should I use for this decision right now?” containing:

* bundle identity (id),
* immutable artifact refs + digests posture,
* compatibility metadata.

### The non-negotiable semantics (pins)

**J3-PIN A — Resolution is deterministic (no “latest”).**
For a given scope, registry returns **exactly one** active bundle by rule.

**J3-PIN B — Compatibility is enforced at resolution, not guessed by DF.**
Bundles must declare compatibility (feature group deps + required capabilities + DF↔bundle input contract version conceptually), and resolution must be compatibility-aware.

**J3-PIN C — DF records the resolved bundle ref used.**
So every decision is explainable (“this decision used bundle X”).

**J3-PIN D — Incompatibility ⇒ safe fallback, recorded.**
If ACTIVE-but-incompatible (feature mismatch or capabilities disabled by degrade), DF falls back to its safe posture and records why.

### Scope (what DF asks the registry “for”)

We must pin this conceptually (without over-spec):

* DF resolves a bundle **per decision scope**, where scope minimally includes:

  * decision domain (derived from `event_type` family),
  * ContextPins where relevant (so “run/world-scoped logic” can exist if needed),
  * and the current degrade posture constraints (for compatibility checks).

*(Exact scope keys can evolve later, but “domain + pins + compatibility context” must be explicit, not implicit.)*

### Failure / edge cases at J3

* **Registry unreachable:** DF must not guess “last known active” unless that behavior is explicitly declared safe. v0 safe posture is: fail-closed into conservative decisioning and record registry unavailability.
* **Rollouts/rollbacks:** bundle changes are lifecycle events; decisions remain reproducible because each decision cites the bundle ref actually used.

---

## J4 — Online Feature Plane → Decision Fabric (OFP → DF)

### Why this join exists

OFP is the “real-time context compiler.” DF must not compute features ad hoc; it must consume **served snapshots** that are provenance-rich, replay-defensible, and leakage-safe by “as-of” semantics + explicit basis tokens.

### What DF requests (conceptually)

A `get_features` request that includes:

* ContextPins (so snapshots are joinable),
* FeatureKeys (key_type/key_id in your broader design),
* requested FeatureGroups + versions,
* `as_of_time_utc` explicitly set.

**Pinned time rule:** DF calls OFP with `as_of_time_utc = event_time`, where `event_time` is derived from envelope `ts_utc`.

### What crosses the join (OFP → DF response)

OFP returns:

* feature values (payload),
* and **required provenance** including:

  * ContextPins
  * `feature_snapshot_hash` (deterministic)
  * group versions used + freshness/stale posture
  * `as_of_time_utc`
  * `input_basis` = applied-event watermark vector
  * `graph_version` if IEG was consulted
  * and the snapshot hash must deterministically cover these blocks with stable ordering.

### The non-negotiable semantics (pins)

**J4-PIN A — No hidden “now.”**
As-of must be explicit; DF never allows a wall-clock default to silently decide feature time.

**J4-PIN B — DF must record OFP provenance in decision provenance.**
At minimum: `feature_snapshot_hash`, group versions, freshness/staleness flags, `input_basis` (and `graph_version` if present).

**J4-PIN C — DF doesn’t invent missing context.**
If required features aren’t available, DF records unavailability and follows its fail-safe posture; it also obeys degrade constraints (e.g., only request allowed groups).

### Why `input_basis` matters (this is the production-replay bridge)

Because events can arrive late and because OFP is a projector, “as-of time” alone is not enough. The snapshot is defined by:

* as-of time, **and**
* which admitted facts had been applied when the snapshot was served (`input_basis`).

That’s what makes offline parity possible later.

### Failure / edge cases at J4

Even without DF internals, the join must support explicit outcomes:

* partial availability by group,
* stale groups vs fresh groups,
* not-found vs empty vs unavailable, and
* “served under degrade restrictions.”

(DF’s internal reaction is DF design; the join requirement is that OFP makes these states explicit so DF can record them rather than guess.)

---

## J5 — Identity & Entity Graph → Decision Fabric (IEG → DF)

### Why this join exists

IEG is the run/world-scoped identity projection and relationship graph. DF uses it (when allowed) to resolve canonical entity references and/or neighborhood context, and must be able to replay/audit exactly which projection state it relied on.

### What crosses the join

A context response plus a **`graph_version`** token.

**Pinned meaning of `graph_version`:**
A monotonic token representing “what EB facts have been applied” for a given ContextPins graph — concretely a **per-partition applied-offset watermark vector (exclusive-next offsets) plus stream identity**.

### The non-negotiable semantics (pins)

**J5-PIN A — IEG consumes EB with duplicates/out-of-order; updates are idempotent.**
IEG applies events using an update key derived from **ContextPins + event_id + a pinned semantics id**, preventing double-apply under replay.

**J5-PIN B — Whenever DF uses IEG, DF records the `graph_version` used.**
So later you can reconstruct “what did DF know?” with a basis token, not a vague time.

**J5-PIN C — Degrade can forbid IEG usage, and DF must comply.**
If forbidden, DF must behave as if IEG does not exist and record “disallowed.”

### Failure / edge cases at J5

* **IEG lag / eventual consistency:** IEG may be behind EB; that’s acceptable *only if graph_version makes the basis explicit* so decisions remain explainable.
* **IEG unavailable:** DF must not invent identities or neighbors; it proceeds without IEG context (or fails safe if that absence blocks safe decisioning) and records unavailability. (This is a required safety posture implied by “no inventing missing context” and the hard-mask worldview.)

---

## One “wiring” note that ties J1–J5 together (so drift can’t hide)

For a **single decision**, DF’s provenance must be able to answer, by-ref:

* **What event** was decided on (J1): `event_id` + EB coords
* Under **which degrade posture** (J2): DL decision snapshot
* Using **which active bundle** (J3): ActiveBundleRef
* With **which features snapshot** (J4): `feature_snapshot_hash` + `input_basis` (+ freshness + versions)
* And **which identity projection basis** if used (J5): `graph_version`

If any of those five anchors is missing, you lose replay/explainability and DLA will eventually have to quarantine “half-truth” audit records.

---

Great — we’ll expand **J6–J10** as *production joins* around an **opaque DF**, focusing on what must be true at the boundaries so the rest of the platform can rely on it.

I’m going to treat these rails as non-negotiable while expanding: **IG is the only admission authority, EB is the durable fact log, canonical envelope is the boundary, admission is atomic with EB append, duplicates are normal so idempotency is mandatory, quarantine is first-class, and intents/outcomes are “real traffic” that still goes through IG→EB**.

---

## J6 — Decision Fabric → Ingestion Gate (DF → IG)

### Why this join exists

DF is a **producer** of “decision loop evidence” (DecisionResponse + ActionIntents). Those outputs must become **decisionable facts** only by passing through the same trust boundary as everything else: **IG**. This preserves the “only one front door” rule.

### What DF submits (conceptually)

DF submits **canonical-envelope events** to IG on the traffic plane (e.g. `fp.bus.traffic.v1`), with payloads that are DF-defined.

At minimum, each DF-produced event must satisfy the envelope schema:

* required: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
* optional pins: `parameter_hash`, `seed`, `scenario_id`, `run_id`
* optional trace: `trace_id`, `span_id`, `parent_event_id`, `producer`, `schema_version`
* payload is isolated under `payload` (envelope forbids extra top-level fields).

**Designer pin for J6:** DF emits at least two event families:

1. **DecisionResponse event** (the authoritative “decision fact” for audit)
2. **ActionIntent event(s)** (what AL executes)
   Both are “real traffic” and must go through IG→EB.

### What IG enforces on DF output (same as any producer)

IG applies **the full admission gate**:

1. **Identity / AuthN consistency**

* IG derives the producer principal from the transport identity and treats envelope `producer` as the declared identity; mismatch is **quarantine**, not a warning.

2. **Authorization allowlist**

* AuthZ is conceptually `(producer_principal, event_type, scope)` where scope includes run/world pins (ContextPins) when applicable. Unauthorized → quarantine + receipt.

3. **Envelope validity + payload version policy**

* If it’s not canonical envelope, it’s not admitted.
* Payload evolution is allowed only via `event_type` and/or `schema_version`; unknown/unsupported versions are quarantined (or routed), never “best effort parsed into partial truth.”

4. **Joinability checks**

* If an event is run/world-joinable, it must carry the required pins (`{manifest_fingerprint, parameter_hash, scenario_id, run_id}`) and must be admissible for the current run/world. Unknown/unready contexts → quarantine.

5. **Deterministic handling of duplicates**

* Same event arriving again must not create a new fact; IG returns a stable **DUPLICATE** outcome pointing to the original fact.

### What IG returns to DF (the “receipt truth”)

IG’s outcome is always explicit: **ADMIT / DUPLICATE / QUARANTINE** (never silent drop). The receipt must be attributable and policy-versioned, and must point by-ref to where the fact lives (or where quarantine evidence lives).

Pinned minimal receipt shape (platform-level truth):
`ingestion_receipt = {receipt_id, producer_principal (+ declared envelope.producer), authz_policy_rev, event_id/event_type/ts_utc, (ContextPins if joinable), decision=ADMIT|DUPLICATE|QUARANTINE, reason_codes, evidence_ref -> (eb_partition, eb_offset) OR quarantine_record_ref, optional event_digest}`

### The critical DF obligation at J6 (to make retries safe)

Because **at-least-once** is real and “admission is idempotent”, DF must reuse the same `event_id` when re-submitting the *same logical* decision/intent, so IG can dedupe deterministically. The envelope explicitly defines `event_id` as the stable idempotency/dedup key at ingest/bus boundaries.

---

## J7 — Ingestion Gate → Event Bus (IG → EB)

### Why this join exists

IG is the **admission authority**, but EB is the **fact authority**. “Admitted” only becomes true once EB durably appends the event.

### What crosses the join

For **ADMIT**:

* IG appends the canonical event to EB (traffic topic), and EB returns **(partition, offset)**.
* IG then issues the receipt with an **evidence_ref** pointing to those EB coordinates.

For **DUPLICATE**:

* IG does *not* create a new fact; it returns a receipt pointing to the existing EB coordinates (or equivalent pointer).

For **QUARANTINE**:

* No append occurs; IG stores quarantine evidence by-ref and returns a receipt with the quarantine pointer.

### Pinned atomicity rule (this is the drift killer)

**Admission is not “done” until EB acknowledges append.** IG must only emit **ADMITTED** when EB append is durable, so the receipt can safely carry EB coordinates as the “where it lives” pointer.

### Partitioning and replay tokens

EB provides partition+offset replay semantics (exclusive-next checkpoint meaning). A production-friendly pin from your deployment notes: **IG stamps a deterministic `partition_key` for any event it admits; EB enforces partition+offset semantics**.

This matters because:

* ordering guarantees exist only within a partition,
* offsets are the universal basis for downstream watermarks, graph versions, and snapshot bases.

---

## J8 — Event Bus → Actions Layer (EB → AL)

### Why this join exists

AL is the **only executor**. Everyone else (DF, humans, ops) only **requests** actions. AL consumes ActionIntents as facts from EB and produces immutable outcomes.

### What AL consumes

* ActionIntents are delivered via EB with at-least-once semantics (duplicates normal).
* Each ActionIntent must carry:

  * a deterministic `idempotency_key`
  * ContextPins (so uniqueness is scoped)
  * decision/event identifiers linking the intent to its origin decision
  * actor identity (principal) + origin (automated vs human/case vs ops), because AL authorizes execution based on the requester identity.

### What AL guarantees at this join (semantic authority)

1. **Effectively-once execution**

* AL enforces uniqueness using **(ContextPins, idempotency_key)** as the scope.
* Duplicate intents must never re-execute; they re-emit the canonical outcome.

2. **Authorization is enforced here**

* AL enforces allowlists by action type + scope using the actor principal.
* If not authorized → **Denied ActionOutcome**, still immutable and idempotent; nothing executes.

3. **Outcomes exist for every attempt**

* Every attempt yields an ActionOutcome (including failures), outcomes are immutable, and duplicate re-emits are byte-identical.

Operationally, AL persists idempotency + outcome history in its own store (`actions` DB), but that’s “inside AL”; the join-level truth is: duplicates don’t multiply side effects.

---

## J9 — Actions Layer → Ingestion Gate → Event Bus (AL → IG → EB)

### Why this join exists

ActionOutcomes are **evidence** and must become durable replayable facts like everything else; they are also inputs to audit, cases, and learning. So outcomes are “real traffic” and still enter via IG→EB.

### What AL emits

AL emits **ActionOutcome** events through IG, which then appends them to EB if admitted. Deployment mapping pins this: outcomes go to the traffic bus and AL may store optional evidence blobs separately.

### Minimum outcome content that must be joinable/auditable

Your platform pins a minimal “policy fact” shape for outcomes:
`action_outcome = {outcome_id, actor_principal, authz_policy_rev, ContextPins, action_type, idempotency_key, linked decision_id/event_id, decision=EXECUTED|DENIED|FAILED, attempt, optional evidence_refs/digests}`

Key consequences:

* **Attribution is mandatory** (who caused the side effect, under which auth policy revision).
* **Idempotency remains law** even for deny/allow decisions (duplicates must not create different outcomes).

### IG/EB behavior for outcomes (inherits J6/J7)

Outcomes are just another producer stream to IG:

* envelope validation + producer identity consistency
* AuthZ allowlist for AL as a producer for `action_outcome` event types
* dedupe/quarantine discipline
* “admitted” only after EB append acknowledged

---

## J10 — Event Bus → Decision Log/Audit (EB → DLA)

### Why this join exists

DLA is the **append-only flight recorder**. It turns “what happened on the bus” into immutable audit records with by-ref pointers so you can replay, explain, and investigate without copying payloads everywhere.

### What DLA consumes

From EB traffic:

* DF DecisionResponse events (primary ingest)
* ActionIntent events (optional; useful to capture what was requested even if outcomes lag)
* AL ActionOutcome events (optional but important to “close the loop”)

From IG/object store (by-ref evidence):

* IG receipts and/or quarantine refs (and optionally EB coordinates) to capture the admission truth and auth policy revs as evidence.

### What DLA must write (the canonical audit record set)

Pinned truths:

* DLA’s primary ingest is **DF’s DecisionResponse** (decision + actions + provenance).
* The canonical audit record must include **by-ref / hashed pointers** to:

  * event basis (what was decided on),
  * `feature_snapshot_hash` + `input_basis`,
  * `graph_version` (if used),
  * degrade posture (mode + enough to identify mask used),
  * resolved policy/model bundle ref,
  * actions (including idempotency keys),
  * audit metadata (`ingested_at`, `supersedes` link on correction).

### Append-only + corrections posture

* DLA is **append-only**.
* Corrections happen via a **supersedes chain**, not overwrite.
* Ingest is idempotent.

### Quarantine posture for audit (don’t write half-truths)

If DF provenance is incomplete, DLA quarantines the audit record rather than silently writing a half-truth.

### Storage / plumbing pin (production-ready expectation)

Deployment mapping pins that DLA writes immutable audit records to an object prefix like `dla/audit/...`, may maintain an optional `audit_index`, and may emit optional pointer events to an audit topic.

---

## One cross-join “closure” pin (J6–J10 must compose cleanly)

To keep this whole segment deterministic and audit-joinable, the platform relies on three choke-point “facts” being present and linkable:

1. **IG receipt** for each admitted DF decision/intent/outcome (policy rev + EB coords)
2. **ActionOutcome** for each intent (executed/denied/failed, immutable, attributable)
3. **DLA record** that ties decision → intents → outcomes by stable identifiers and by-ref pointers (append-only, idempotent, supersedes for corrections)

That triangle is what makes your “audit join view” possible without copying payloads or inventing hidden state. 

---

Cool — expanding **control-plane joins J11–J14** (per *our* numbering: **Obs/Gov→DL**, **Run/Operate→DF**, **Registry lifecycle→DF**, **External caller→DF**). These are the joins that make the platform *operable without hidden coupling* and keep “what changed / are we safe / why did we act” answerable in production.

---

## J11 — Observability & Governance → Degrade Ladder (Obs/Gov → DL)

### Why this join exists

Obs/Gov must **not** silently mutate behavior; it influences the hot path **only through explicit control surfaces**, and DL is the primary one: it consumes health/lag “golden signals” + corridor checks and emits an explicit constraints mask.

### What crosses the join (inputs to DL)

Think in two buckets:

#### 1) **Signals (continuous telemetry)**

Minimum signal family (production-shaped):

* **Golden signals** per service: throughput, latency (p95), error rate (by class), saturation/backlog.
* **Platform-specific safety signals** that DL *especially* cares about:

  * EB consumer lag per partition + “watermark age” (how far applied offsets are behind) for IEG/OFP/DLA consumers
  * OFP staleness/missing-feature rates + snapshot failures
  * DF fallback / “blocked by degrade mask” rate + registry-resolution failures
  * IG admit/quarantine/auth/schema failure rates (because if admission is unhealthy, “acting” is unsafe)

#### 2) **Corridor checks (governance safety gates)**

These are the “are we allowed to proceed?” checks:

* lineage / correlation completeness posture (can we still explain decisions end-to-end?)
* “no PASS → no read” compliance, extended beyond the engine into platform trust posture
* rollout safety gates / error budget corridor breaches

### How DL must treat these inputs (the pinned semantics)

**J11-PIN A — DL input must be recordable as evidence**
DL’s output can’t be “we degraded because vibes.” DL needs a **DegradeInputSnapshot** concept (even if implemented as a pointer) that captures:

* which signals/checks were used,
* which window/aggregation period,
* and which **threshold profile revision** (policy config rev) defined “safe/unsafe.”

**J11-PIN B — No silent coupling (explicit output only)**
Obs/Gov doesn’t flip DF behavior directly; it only provides inputs. DL turns them into an explicit mask, and DF later cites that mask in provenance.

**J11-PIN C — Deterministic + hysteresis + fail-closed**
DL must be deterministic (given the same input snapshot) and should include hysteresis to avoid flapping. If DL can’t evaluate (missing telemetry / pipeline outage), it fails **toward safety** (stricter posture).

### Practical “production patterns” (still join-level)

Either pattern is valid as long as the pins above hold:

* **Pull:** DL queries the observability store (metrics/traces/log summaries) on an interval.
* **Push:** Obs/Gov emits periodic “corridor state” facts and DL consumes them.

The key is: whatever DL used must be *referencable* (snapshot id or window+rev), so DF/DLA can later say “this decision happened under posture X because corridor state Y under threshold profile rev Z.”

---

## J12 — Run/Operate → Decision Fabric (Run/Operate → DF)

### Why this join exists

Run/Operate is the platform’s operational substrate: orchestration, deployment, config/secrets, runtime controls, retention/backfill operations. It **must not** become a shadow source of business truth, and it must not introduce hidden nondeterminism.

### What crosses the join (conceptual)

This join is *not* “domain data.” It’s **lifecycle control + governed configuration**.

#### 1) Lifecycle control (start/stop/drain/pause/replay)

Run/Operate owns platform-wide lifecycle operations (start/stop/drain/backfill) and these operations must be consistent and auditable.

Production-ready DF expects:

* **Drain**: stop taking new work after a declared point (e.g., consumer group checkpoint discipline)
* **Pause/Resume**: controlled stop of consumption without pretending the system is “healthy”
* **Emergency stop**: explicit, recorded “we are not allowed to act” posture

*(Exact mechanics are implementer territory; the join pin is that lifecycle ops exist and are auditable.)*

#### 2) Config + change control (profiles)

Your platform pins that **configs can change outcomes**, so policy config is governed and versioned; wiring config is not semantic.

So DF must receive (at deploy/startup, and possibly on activation):

* **Wiring profile** (endpoints/timeouts/resources)
* **Policy profile revisions** that affect behavior, e.g.:

  * DL threshold profile rev (affects degrade)
  * registry lifecycle/compat policy rev (affects which bundles are eligible)
  * action allowlist policy rev (affects AL; DF should still log what it assumes)

**J12-PIN A — “code X + profile Y” must be reportable**
Components must not contain “prod fork” semantics. DF’s behavior must be explainable as *the same build artifact* plus an environment profile selection.

**J12-PIN B — Outcome-affecting operational acts emit governance facts**
Deployments, config activations, retention changes, backfills, access/control changes — these must be durable governance facts (not just logs).

#### 3) Backfill/rebuild controls (the big “production reality” lever)

Run/Operate triggers backfills/replays, but they must be explicit, scoped, and auditable:

* declare scope, purpose, basis (offset/time windows), outputs
* regenerate only **derived** state (IEG projections, OFP state, offline datasets/manifests, audit indexes)
* never “mutate truth” (EB admitted events, label timelines, registry history, SR ledgers, engine outputs for a pinned identity)

**What DF must expect from this join:**
Backfills don’t “rewrite DF.” They change the *derived* contexts DF may consult (OFP/IEG bases), and that must be visible via `input_basis`/`graph_version` provenance and via the governance fact “backfill Z executed.”

---

## J13 — Registry lifecycle events → Decision Fabric (Registry → DF, event stream)

### Why this join exists

Registry is the **only gate for production logic changes**; rollouts/rollbacks are first-class and auditable; DF must always be able to answer “what changed?” by pointing to a registry lifecycle event and the bundle ref it used.

### What crosses the join

A stream of **RegistryEvent** facts (publish/approve/promote/rollback/retire), each **attributable** and **by-ref**.

Minimum conceptual payload (pinned in blueprint):
`registry_event = {registry_event_id, actor_principal, governance_action, from_state->to_state, bundle_id + immutable refs/digests, scope, approval_policy_rev, reason, evidence_refs (eval + GateReceipt where required)}`

### How DF uses it (without becoming “push-driven truth”)

Two valid production designs:

#### Option A: DF resolves bundles on-demand (pull)

DF calls Registry per decision to get the deterministic ActiveBundleRef. Events are just for observability/governance.

#### Option B: DF subscribes to events (push + cache invalidation)

DF listens to registry events to:

* warm cache / update “current active per scope”
* detect rollouts quickly
* reduce registry read QPS

**J13-PIN A — Events are optimization, not authority**
Even if DF caches, the authoritative rule remains: Registry deterministically resolves one ACTIVE bundle per scope, and DF records the resolved bundle ref used for each decision.

### Edge cases DF must tolerate (join-level reality)

* Duplicate/out-of-order registry events → DF must treat them idempotently by `registry_event_id` and `from_state→to_state`.
* “ACTIVE but incompatible” under current feature definitions or degrade mask → resolution must fail closed or route to explicit safe fallback; DF never guesses compatibility.
* Race window: decision resolved just before a promote event arrives → that’s fine; decision provenance cites the old bundle; after promote, decisions cite the new bundle. Audit joins to the registry timeline remain consistent.

---

## J14 — External caller → Decision Fabric (optional Decision API)

### Why this join exists (and why it’s dangerous)

Deployment notes allow DF to consume “events (or synchronous decision API requests),” but your platform posture is: **IG controls what becomes a fact** and EB is the replayable durable record. So an external Decision API must not create a second “truth world.”

### Production-safe ways to do it (two modes)

#### Mode 1: **Preview / what-if (non-authoritative)**

External caller asks DF “what would you do?”

* DF returns a response, but **must not emit ActionIntents** and must not claim this is a durable decision fact.
* If you log it, it must be labeled clearly as preview/what-if so it can’t be confused with audited production decisions.
  This mode is useful for UI experiments, analyst tooling, or offline evaluation probes — but it must not trigger outcomes.

*(This respects “single truth world” by not minting durable decision facts off-bus.)*

#### Mode 2: **Authoritative request (event-submitted)**

External caller submits a **DecisionRequest event via IG**, so it becomes an admitted fact, then DF processes it from EB like everything else.

Conceptual flow:

```
External caller -> IG (authenticated ingress, policy-validated)
  -> EB (admitted DecisionRequest event)
  -> DF (consumes from EB, decides)
  -> IG -> EB (DecisionResponse + ActionIntents)
```

Key pins:

* **AuthN/AuthZ belongs at the boundary** (IG ingress policy, versioned and auditable).
* Request must be **idempotent** (caller supplies request id / idempotency key; event_id derived deterministically so retries dedupe cleanly).
* Response must be **joinable and replayable** (correlation keys preserved end-to-end; trace propagation).

**Optional latency pattern:** the API can return immediately with a handle (event_id), or block waiting for the DecisionResponse to appear (implementation choice). The authoritative truth is still the admitted event stream.

### The “no implicit scope” rule for J14

Because your platform is strict about joinability and pinned context, external callers must not rely on implied defaults:

* if the request is run/world scoped, it must carry the required pins, or IG quarantines it
* if there is a “live” scope, that scope must be explicit as a pinned profile/config choice (not hidden logic).

---

Perfect — here are **P1–P4 expanded as production narratives** (still brainstorm mode; DF stays a black box). I’ll keep everything consistent with your pinned rails: **IG is the sole admission authority, EB is the sole durable fact log, canonical envelope is the boundary shape, offsets are the replay spine, idempotency is mandatory, time semantics never collapse, degrade is explicit+recorded, quarantine is first-class, and SR’s READY + run_facts_view is the downstream entrypoint**.

---

## P1 — Core hot decision path

**Producer → IG → EB → DF → IG → EB → AL → IG → EB → DLA**

### What this path *does* (the “facts-to-outcomes-to-audit” spine)

It turns admitted events into:

1. **a decision fact** (DecisionResponse),
2. **an execution fact** (ActionOutcome), and
3. **an audit fact** (append-only audit record),
   all of which remain replayable and explainable **by-ref**.

### Preconditions (production truth)

* **Anything that can influence decisions enters through IG → EB.**
* Every admitted event is a **Canonical Event Envelope** with required fields `{event_id, event_type, ts_utc, manifest_fingerprint}`.
* EB delivery is **at-least-once** and the only universal progress token is `(stream, partition, offset)` with **exclusive-next** checkpoint meaning.

### Production sequence (what happens, step-by-step)

#### 1) Producer submits a candidate fact → IG

Producers include **engine traffic, external txns, DF outputs, AL outcomes, label/case emissions**.

IG validates:

* envelope shape + policy + joinability to a valid run/world context (when run-scoped),
  then chooses exactly one: **ADMIT / DUPLICATE / QUARANTINE**, and emits a receipt with evidence pointers.

#### 2) If ADMIT: IG appends → EB (fact becomes durable)

Admission is not “done” until EB acknowledges append. Once appended, the event gets stable EB coordinates `(partition, offset)` which become the replay token.

#### 3) EB distributes admitted facts (multiple consumers, different authorities)

From the same admitted log:

* **DF consumes** eligible event types (decision triggers).
* **IEG projector consumes** and updates the graph projection + `graph_version`.
* **OFP projector consumes** and updates feature state; serves snapshots with `feature_snapshot_hash` + `input_basis`.
* **DLA consumes** decisions/intents/outcomes later (see step 7).

The key: they all reference the same replay spine (offsets).

#### 4) DF consumes an admitted event → produces decision + intents (still opaque internally)

DF’s boundary obligations (even while opaque):

* Treat the admitted event as immutable fact input; be stable under duplicates (at-least-once).
* Use `ts_utc` as **domain event time**; do not collapse time semantics.
* Obey DL’s explicit mask as **hard constraints**, and record the degrade posture used.
* Resolve exactly one ACTIVE bundle per scope via Registry (no “latest”) and record bundle ref in provenance.
* If it queries OFP/IEG, it must record `feature_snapshot_hash` + `input_basis` and/or `graph_version` so the decision is replay-defensible.

DF then emits:

* **DecisionResponse** (decision + provenance)
* **ActionIntent(s)** with deterministic idempotency anchors
  as canonical-envelope events (producer traffic).

#### 5) DF outputs go through IG → EB (again)

DF is just another producer at the trust boundary. IG applies the same admit/duplicate/quarantine discipline; “drop on the floor” is disallowed.

#### 6) AL consumes ActionIntent(s) → executes effectively-once → emits ActionOutcome(s)

AL is the **only executor**, and it enforces effectively-once using `(ContextPins, idempotency_key)`; duplicates must not multiply side-effects. Outcomes are immutable history facts.

Then AL emits **ActionOutcome** events via IG → EB (same front door).

#### 7) DLA consumes decisions + intents + outcomes + IG evidence → writes audit record

DLA is the append-only **flight recorder**:

* idempotent ingest
* append-only audit records
* quarantine if provenance is incomplete
* corrections via supersedes chains (no silent mutation)

### Where this path “bites” in production (what must hold)

* **Idempotency is end-to-end:** IG dedupe/receipts, DF stable outputs, AL effectively-once, DLA idempotent ingest.
* **Replay determinism depends on offsets:** all “versions” (IEG `graph_version`, OFP `input_basis`) are derived from EB coordinates.
* **Auditability depends on by-ref pointers:** receipts + EB coords + snapshot hashes make decisions explainable without copying everything.

---

## P2 — Run/world gating path

**SR READY + run_facts_view shapes what DF can ever see**

### What this path *does*

It makes the platform’s world/run choice **enforceable** and **non-guessable**:

* SR is system-of-record for run identity + readiness
* `run_facts_view` is the join surface map
* READY is the trigger
* Downstream starts here or it’s a bug

### Production sequence

#### 1) RunRequest → SR

SR is “conductor + ledger” for:

* invoke-or-reuse engine
* verify required PASS gates
* write run_plan/run_record/run_status
* publish READY + `run_facts_view`

#### 2) SR ↔ Data Engine: completion evidence, not “success”

Engine completion evidence is:

* **Output locators** pointing to produced artifacts
* **PASS/FAIL evidence** as gate receipts scoped to exact identity

SR declares engine step complete only if it can record/replay:

* which outputs were produced (by locator)
* which required gates passed (by receipt)
* under which pins (ContextPins + seed where applicable)

If PASS is missing/FAIL → SR does **not** declare READY. READY is binary; SR never “half-readies.”

#### 3) SR publishes downstream entrypoint: READY + run_facts_view

* READY is monotonic (no undo; corrections are new declared state or superseding story).
* `run_facts_view` is the *map* of pinned references + required PASS evidence.

Downstream is forbidden from:

* scanning engine outputs
* inferring “latest”
* choosing its own world
  It must follow the join surface.

#### 4) How that affects what DF ever sees

IG enforces joinability at the boundary:

* events meant to drive the run/world must carry the required pins and be admissible to a valid (in practice READY) context
* unknown/unready contexts → quarantine/hold, not “best effort”

So DF’s reality is indirectly gated by:

* SR’s READY + run_facts_view (truth for “this run exists + is admissible”)
* IG’s joinability enforcement (truth for “this event belongs to that run”)

#### 5) Engine “business_traffic” enters through the same front door

Your platform pin is explicit: if it’s treated as traffic, it goes **Engine → IG → EB → consumers** with canonical envelope.

(Implementation can be pull or push, but the *meaning* must remain: engine traffic doesn’t bypass admission and is joinable to SR’s run context.)

---

## P3 — Degrade/safety control path

**Obs/Gov → DL → DF posture → outcomes → Obs/Gov**

### What this path *does*

It makes “are we safe to act?” an explicit, auditable control loop:

* Obs/Gov provides signals + corridor checks
* DL converts that into an explicit constraints mask
* DF obeys and records the posture used
* outcomes feed back into the signals

### Production sequence

#### 1) Everything emits observable facts + golden signals

Minimum production signals include throughput/latency/errors/saturation for every always-on unit, plus platform-specific ones like:

* IG admit/quarantine/auth/schema fail rates
* EB consumer lag / watermark age (IEG/OFP/DLA)
* OFP staleness/missing-feature rates
* DF fallback/blocked-by-mask rates
* AL denied/fail rates

#### 2) DL consumes these + threshold profiles → produces DegradeDecision

DL outputs:

* `degrade_mode + capabilities_mask` (deterministic + hysteresis)
* fail-closed if it can’t evaluate
* can optionally publish posture updates to control bus
  and persists current posture in its own truth store.

#### 3) DF obeys the mask as hard constraints (no silent coupling)

If a capability is off, DF behaves as if it doesn’t exist; DF records the exact degrade posture used in decision provenance/audit.

This is where degrade becomes enforceable: it’s not “we were slow so we kinda did less,” it’s “posture X forbade feature group Y and stage Z.”

#### 4) Outcomes + audit visibility close the loop

AL outcomes and DF/DLA facts make the degrade posture visible in effect, and Obs/Gov can see:

* whether degrade reduced load/latency
* whether fallbacks spiked
* whether staleness reduced
* whether quarantine increased (meaning admission was unsafe)

---

## P4 — Quarantine remediation path

**IG quarantine → operator/governance action → admit → EB → DF**

### What this path *does*

It turns “rejected at boundary” into an auditable, fixable story — not silent loss:

* quarantine is first-class
* evidence is stored by-ref
* remediation is explicit and governed
* eventual admission (if it happens) is traceable back to the quarantine origin

### Production sequence

#### 1) IG quarantines (never drops)

When a producer submits an event that can’t be admitted under policy or can’t be anchored to a valid run/world context, IG:

* stores evidence by-ref (object store)
* emits a receipt with reason codes + evidence pointers
* (optionally) emits pointer events to an audit/control topic

Typical quarantine classes:

* envelope invalid / schema_version unsupported
* auth/authz failure
* joinability failure (unknown/unready run context)
* policy rejects (type not allowed / forbidden scope)

#### 2) Triage happens as an explicit operational act

Remediation is not “edit the past.” It’s one of:

* **Fix producer** and resubmit a corrected event (new fact)
* **Update policy allowlist** (schema/event_type/authz) and re-evaluate quarantined items
* **Resolve joinability** (run becomes READY; release held/quarantined events)
* **Declare backfill/replay** for derived stores if necessary, but never mutate truth facts

Any outcome-affecting change must emit governance facts (“change must be visible”).

#### 3) Release/admit is a new explicit decision with evidence linkage

When an item leaves quarantine:

* IG performs admission checks again under the new policy/run context
* if admitted, it appends to EB and issues a new receipt
* the release/admit story must remain linkable to the original quarantine evidence (by receipt/evidence pointers)

#### 4) Once admitted, the item enters the normal hot path

After admission, it becomes replayable fact and DF can see it (P1 resumes).

### Two important “production realities” to keep pinned here

* **Quarantine isn’t always resolvable** (some items remain quarantined forever; that’s okay as long as the system is auditable and doesn’t pretend).
* **Late admission is allowed**, but determinism demands visibility: late facts change derived projections via offsets/watermarks, and that must be reflected in `graph_version` / `input_basis` provenance, not silently hidden.

---

Alright — expanding **P5–P8** as *production* paths, still keeping **DF opaque**, but making the **outer expectations** explicit so DF can later be designed to fit them without drift.

---

## P5 — Decision → Case → Label path

**(evidence → Case Workbench → Label Store timelines)**

### What this path is for

It turns “automated suspicion/decision evidence” into **human-reviewed truth** that the platform can use later **without rewriting history**.

### Production sequence (facts flow)

1. **EB already contains the basis facts**
   Transactions / events were admitted via **IG → EB** (so they’re replayable and attributable).

2. **DF emits decision evidence onto EB (via IG)**
   DF produces:

   * a **DecisionResponse** (decision + provenance pointers)
   * 0..N **ActionIntents** (including, commonly, “route to case queue” / “request review”)
     These are “real traffic” and must follow **DF → IG → EB**.

3. **AL emits ActionOutcomes onto EB (via IG)**
   If DF requested a “case route/open” intent, AL executes (effectively-once) and emits an **ActionOutcome** (e.g., `QUEUED`, `CREATED`, `DENIED`, `FAILED`). 

4. **Case Workbench consumes *facts* and assembles an immutable case timeline**
   Case Workbench is not a “decision service”; it’s a **timeline composer** that builds a case record out of:

   * the triggering transaction/event(s)
   * DF DecisionResponse + provenance pointers
   * ActionIntents and ActionOutcomes
   * any subsequent analyst actions
     The key outer expectation: cases must be **joinable by reference** to the durable log and audit evidence; not ad hoc screenshots.

5. **Analysts emit LabelAssertions; Label Store records append-only label timelines**
   Label Store is the system-of-record for labels as **append-only assertions**, with explicit:

   * *observed time* (when we learned it)
   * *effective time* (what time the label applies to, when relevant)
     Corrections are new assertions / supersedes, not overwrites. 

### What DF must provide so this path “works” (outer expectations on DF)

* **Joinability hooks:** DF outputs must carry ContextPins + stable identifiers so Case Workbench can link decisions → intents → outcomes → underlying facts.
* **Provenance pointers:** DF must not say “trust me”; it must cite the posture/basis (degrade used, bundle used, feature snapshot hash + basis) so the case timeline can explain *why* the system acted.
* **No label ownership:** DF never writes labels; it can suggest/route to review, but truth comes from Case/Label systems. 

### Production edge cases (that must be supported, not avoided)

* **Conflicting labels** (multiple analysts / later corrections): Label Store timeline handles it; consumers query “as-of” or “effective.” 
* **Late-arriving outcomes** (intent now, outcome later): case timelines must remain consistent; audit remains append-only.
* **Degrade mode periods:** decisions made under stricter masks must still be reviewable and comparable to normal operation (the mask used must be visible).

---

## P6 — Learning/evolution path

**(EB + DLA + Labels → Offline Shadow → Model Factory → Registry → DF)**

### What this path is for

It’s how the platform **improves** decisioning while staying closed-world, reproducible, and auditable: DF changes only through **governed activation** (Registry), not silent model swaps.

### Production sequence (from facts to a new active bundle)

1. **Primary evidence sources are immutable logs/timelines**

* **EB history**: the admitted event stream (transactions, decisions, intents, outcomes, etc.). 
* **DLA exports**: audit-grade joins tying decision → basis → actions → outcomes (append-only, supersedes allowed).
* **Label Store timelines**: append-only label assertions with time semantics. 

2. **Offline Shadow rebuilds deterministic training/eval surfaces**
   Offline Shadow consumes those sources and produces:

* training examples (features + targets)
* evaluation sets
* provenance for each example (what it was derived from, as-of semantics)
  Crucial: offline must be able to reconstruct “what DF could have known” using the same **basis tokens** that the online side records (OFP `input_basis`, IEG `graph_version`).

3. **Model Factory trains + evaluates under governed gates**
   Model Factory outputs:

* model artifacts
* evaluation evidence (metrics, reports, PASS/FAIL gates as required)
* a packaged “bundle candidate” (model + policy + feature contracts)

4. **Registry publishes and governs activation**
   Registry receives the bundle candidate + evidence pointers and drives:

* publish → approve → promote/activate (or reject/retire/rollback)
  Once active, DF resolves the active bundle deterministically per scope and records it in every decision.

### What DF must provide so this path “works”

* **Decision provenance must be “parity-ready”**: if DF uses OFP/IEG, it must record the snapshot identifiers/basis so offline can reproduce the same context.
* **Bundle ref must be recorded per decision**: so you can measure impact, do rollbacks, and attribute errors to a specific activation.

### Production realities to plan for

* **Rollbacks are normal**: Registry lifecycle events must make it trivial to answer “when did behavior change and why?” without digging through code.
* **Label delay**: training truth often arrives days/weeks later; the pipeline must handle late supervision without mutating earlier facts. 

---

## P7 — Backfill/rebuild path (derived state)

**(Run/Operate → rebuild IEG/OFP/offline/audit indexes → DF sees new bases)**

### What this path is for

It is the “production reality” mechanism for fixing or regenerating **derived stores** when:

* retention forces rehydration from archives,
* a projector bug is fixed,
* late facts arrive,
* feature definitions change (served logic changes),
* audit/index materializations need rebuild
  …**without mutating primary truths**.

### Production sequence

1. **Run/Operate declares a backfill as an explicit governed act**
   A backfill must be declared with:

* scope (streams/partitions, offset ranges and/or time windows)
* target stores (IEG projection, OFP state, Offline Shadow datasets, audit indexes)
* reason + operator principal + policy rev
  This is essential: “backfill happened” must be visible and joinable, not just a log line.

2. **Rebuild only derived state**
   Rebuild targets:

* IEG’s projection state (and therefore future `graph_version` readings)
* OFP’s served state (and therefore future `input_basis`/snapshot hashes)
* Offline Shadow datasets
* Optional audit indexes
  Non-targets (never rewritten):
* EB admitted facts
* label timelines
* registry history
* SR run ledgers
* engine outputs for a pinned identity

3. **After rebuild, DF doesn’t “change the past”; it sees new bases going forward**
   Past decisions remain valid historical facts (with old provenance). Future decisions may cite:

* newer `graph_version` states
* new OFP `input_basis` and snapshot hashes
* possibly new active bundles (if Registry activation occurred)
  This keeps causality honest: you can explain why a decision changed without pretending you rewrote history.

### Outer expectation on DF

DF must carry basis tokens in provenance so backfill effects are visible:

* “this decision used OFP snapshot X with basis Y”
* “this decision used IEG graph_version G”

---

## P8 — Optional synchronous request path

**(preview-only OR event-submitted authoritative path)**

### Why this path exists

Sometimes you want:

* **interactive UX** (analyst tooling, dashboards, testing)
* **external integration** (a partner asks for a decision now)
  But the platform must not create two inconsistent realities.

### Mode A — Preview / what-if (non-authoritative)

**External caller → DF → response**

* DF may compute a response, but it must be explicitly labeled *preview*.
* It must not emit ActionIntents or claim durable decision truth.
* If you record previews, they must be segregated so they cannot be confused with audited decision facts.

This mode is safe because it doesn’t violate: “IG→EB is the truth entry” and “EB is replay spine.”

### Mode B — Authoritative synchronous request (event-submitted)

**External caller → IG → EB → DF → IG → EB**, with the caller optionally waiting for the DecisionResponse.

* The authoritative request is a canonical-envelope **DecisionRequest** event admitted by IG (AuthN/AuthZ enforced, joinability enforced).
* DF processes it like any other admitted stimulus and publishes DecisionResponse/ActionIntents via IG→EB. 
* The API can either:

  * return immediately with the handle (`event_id` / correlation id), or
  * block until it observes the DecisionResponse on EB (bounded wait).

### Critical pins for Mode B

* **Idempotency:** retries must dedupe cleanly at IG/EB using stable ids.
* **Explicit scope:** if run/world scoped, the request must carry required pins or it’s quarantined; no implicit “default run.” 
* **Auditability:** authoritative requests must generate the same downstream evidence chain as any other decision (receipts, offsets, DLA record).

---

Absolutely — here are **L1–L6 expanded as production-grade cycles** around an **opaque DF** (we only talk about what the loop *requires* from DF at the boundaries, not DF internals).

I’ll stick to your pinned rails: **IG is the only admission authority; EB is the durable fact log; at-least-once is assumed; idempotency is mandatory; time semantics don’t collapse; degrade is explicit + enforced + recorded; audit is append-only with supersedes; quarantine is first-class; labels are append-only timelines with as-of semantics; learning uses DatasetManifests with explicit replay basis; backfills are declared + auditable and only rebuild derived state.**

---

## L1 — Action closure loop

**EB → DF → ActionIntent → AL → ActionOutcome → EB**

### What this loop *is*

This is the core “decision becomes a side effect” closure, expressed purely as **facts on the log**:

```
(admitted business event on EB)
  -> DF produces DecisionResponse + ActionIntent(s)
      -> AL executes effectively-once
          -> AL emits ActionOutcome(s)
              -> Outcomes land back on EB (and feed audit/case/metrics)
```

DF declares; **AL is the only executor**, and it enforces effectively-once using **(ContextPins, idempotency_key)**; duplicates never multiply side effects; outcomes are immutable history facts.

### Why this loop exists

Because you want **closed-world realism**: decisions have consequences, and consequences are observable, replayable, and auditable.

### What must be pinned for the loop to be safe

**L1-PIN A — Idempotency across the whole cycle**

* EB delivery is at-least-once; DF can see duplicates; AL can see duplicates. 
* Therefore DF’s ActionIntents must carry deterministic idempotency keys, and AL must dedupe in its authoritative `actions` truth store.

**L1-PIN B — Attribution and policy rev must survive the cycle**
Every ActionIntent carries an **actor principal + origin**, and every ActionOutcome records the actor principal + the **authz policy revision** used to allow/deny execution. This is how you later defend “why did we block/allow?”

**L1-PIN C — Outcomes are “real traffic” and must go through IG→EB**
Intents/outcomes don’t bypass the trust boundary; they re-enter the same durable record like any other producer traffic.

### What “closure” means (loop termination condition)

For each decision stimulus, the action loop is considered **closed** when, for each ActionIntent idempotency scope, an immutable ActionOutcome exists (EXECUTED / DENIED / FAILED).

**Production reality:** closure can be delayed (timeouts, external integrations, retries). That’s fine because the log carries partial truth, and the audit plane can show “intent issued, outcome pending.”

### The drift trap in this loop (and the pin to prevent it)

**Drift trap:** DF accidentally “re-decides” in response to ActionOutcome events and creates an uncontrolled feedback loop.

**L1-PIN D (designer): DF does not treat ActionOutcome events as decision triggers by default.**
If you *want* follow-up decisioning (e.g., “if EXECUTION_FAILED then queue a case”), that must be a deliberate allowlist decision trigger rule, not an accidental consequence of “DF consumes everything.” (This is consistent with your general “allowlist event types; avoid self-trigger loops” posture.)

---

## L2 — Safety/degrade loop

**signals / corridor checks → DL → DF posture → outcomes / load → signals**

### What this loop *is*

This loop makes “are we safe to act?” explicit and auditable:

```
Obs/Gov signals + corridor checks
  -> DL emits DegradeDecision(mode + capabilities_mask + provenance)
      -> DF obeys mask as hard constraints and records posture
          -> decisions/actions change load and outcomes
              -> new signals feed DL again
```

DL is deterministic + hysteresis + fail-closed, and DF must treat the capabilities mask as **hard constraints** (no bypass) and record the exact posture used per decision.

### Why this loop exists

To prevent silent coupling: if OFP is stale, IEG lags, registry is unstable, or the bus is backing up, the platform must not “kind of” degrade — it must **declare** what it’s doing and why.

### What’s “allowed” to change under degrade

Only what the mask allows. Typical constraint classes (conceptual, not schema-bound):

* allow/forbid IEG queries
* restrict feature groups in OFP
* disable model stages (or all model calls)
* restrict action posture (e.g., “STEP_UP_ONLY”)

### What must be pinned for the loop to be stable

**L2-PIN A — DL output must be referencable**
DL posture isn’t “current mood”; it must be recordable and citeable in decision provenance/audit (“decision was made under posture X”).

**L2-PIN B — Fail-closed, not fail-open**
If DL can’t evaluate (telemetry gaps, DL outage), DF assumes a stricter posture and records the fallback.

**L2-PIN C — Hysteresis / anti-flap is required**
Your blueprint explicitly pins hysteresis; without it, you’ll thrash between modes and make outcomes non-comparable.

### The loop’s “success metric”

Not “DL changed mode,” but:

* the system returns to a corridor where **decision provenance remains complete** and
* load/lag/staleness return to safe bounds.

(And because posture is recorded, you can measure effect: “what happened to outcomes and case volume under DEGRADED_1?”)

---

## L3 — Quarantine remediation loop

**candidate event → IG quarantine → triage/governance → re-evaluate → admit or remain quarantined**

### What this loop *is*

Quarantine is first-class, not a dead-end:

```
Producer submits candidate event
  -> IG decides QUARANTINE (with receipt + evidence pointers)
      -> operators/workflows inspect evidence
          -> fix producer OR change policy OR resolve joinability (e.g., run becomes READY)
              -> IG re-evaluates
                  -> ADMIT (append to EB) OR still QUARANTINE
```

IG never silently drops; it emits ADMIT / DUPLICATE / QUARANTINE with evidence pointers.

### Why this loop exists

Because without it, you lose auditability and you can’t debug production. Quarantine is how the platform says: “I saw it, I rejected it, here is why, and here is the evidence.”

### What causes quarantine (production categories)

* schema/version not admissible under policy
* auth/authz mismatch or forbidden producer/event_type/scope
* joinability failure (e.g., unknown/unready run/world pins)
* malformed envelope / missing required pins (for run-joinable facts)

### What remediation is allowed to do (and what it must not do)

**Allowed remediation actions**

* fix the producer and resubmit (new candidate fact)
* promote a policy config revision (e.g., admission allowlist) as a governed change
* resolve joinability (e.g., SR publishes READY + join surface; then IG can admit held/quarantined run-scoped traffic)

**Forbidden remediation action**

* “patch the event” into something else silently. Your pins forbid silent mutation of truth — re-admission must be explicit and evidenced.

### Closure / termination conditions

* **Resolved**: event becomes ADMITTED and is appended to EB (now eligible for DF/IEG/OFP/etc).
* **Unresolved but stable**: event remains quarantined indefinitely, but the platform still has a durable evidence trail and metrics.

---

## L4 — Audit completeness loop

**EB decisions/intents/outcomes → DLA ingest → (audit record OR audit quarantine) → correction via supersedes → DLA**

### What this loop *is*

DLA refuses to be a “half-truth sink.” It either writes a complete audit record or quarantines until the story is complete:

```
DF emits DecisionResponse (+ provenance)
  -> DLA ingests
      -> if provenance complete: write append-only AuditDecisionRecord
      -> else: audit quarantine (evidence pointers)
          -> correction occurs (new records that supersede)
              -> DLA converges to a complete append-only record chain
```

DLA is append-only; corrections are **supersedes chains**; ingest is idempotent; incomplete provenance triggers quarantine.

### Why this loop exists

Because “we can’t explain why we acted” is a production failure mode as serious as “we acted incorrectly.” Audit completeness is what makes the system defensible.

### What DLA requires (the minimum completeness set)

The canonical audit record must include (by-ref/hashed pointers):

* the event basis reference
* OFP `feature_snapshot_hash` + `input_basis`
* IEG `graph_version` (if used)
* degrade posture used (mode + enough to identify mask)
* resolved bundle ref (active policy/model)
* actions (including idempotency keys)
* audit metadata including supersedes link

### How the loop converges (without rewriting history)

**L4-PIN A — Only the authoritative writer can correct its truth**

* DF is authoritative for decision + provenance.
* DLA is authoritative for audit record set semantics (append-only, supersedes).
  So convergence happens by **new DF records** (or new evidence pointers) plus new DLA records that supersede prior ones — never by editing old records.

**L4-PIN B — Audit quarantine evidence is a first-class artifact**
Your substrate map explicitly treats quarantine evidence (IG and sometimes DLA) as a primary “can’t lose it” truth family.

### Practical production note

This loop often feeds back into L2: if audit completeness drops (too many quarantines), Obs/Gov can force stricter degrade posture (“stop doing complex decisions until provenance integrity returns”). That stays consistent because degrade is the explicit control surface.

---

## L5 — Human supervision loop

**decisions/actions/audit evidence → cases → labels → offline shadow → model factory → registry → DF**

### What this loop *is*

This is the “improve decisioning without lying to yourself” loop:

```
RTDL evidence (decisions + intents + outcomes + audit pointers)
  -> Case Workbench builds immutable case timeline (by-ref)
      -> investigators emit LabelAssertions
          -> Label Store holds append-only label timelines (effective vs observed time, as-of reads)
              -> Offline Shadow builds leakage-safe datasets using explicit replay basis + as-of labels
                  -> Model Factory trains/evaluates and produces bundles + evidence
                      -> Registry governs activation (append-only lifecycle events)
                          -> DF resolves ACTIVE bundle deterministically and records bundle ref per decision
```

Key truths:

* RTDL outputs are **evidence**, not ground truth.
* Ground truth labels exist only in Label Store, as append-only timelines with **effective_time vs observed_time** and as-of semantics.
* Learning is reproducible only if datasets are pinned by **DatasetManifests** with explicit replay basis and as-of boundary.
* Decision logic changes are governed at Registry; DF records bundle ref used; registry lifecycle changes are auditable.

### Why this loop exists

So you can answer (honestly):

* “What did we know at the time?”
* “What changed our behavior?”
* “Is the model better, or did we leak future truth into training?”

### The key drift-killer pins inside this loop

**L5-PIN A — “As-of” is mandatory for training joins**
Labels arrive late and can be corrected; dataset builds must separate “what we knew then” vs “what we know now.”

**L5-PIN B — Feature versioning is singular across online/offline/bundles**
OFP records feature group versions; Offline Shadow uses those versions; bundles declare which versions they require; Registry resolves compatibility-aware.

**L5-PIN C — Registry is the only gate for deployable truth**
No silent swaps. Promotion/rollback is an auditable lifecycle mutation.

---

## L6 — Backfill/rebuild loop

**derived-state correction → new bases → parity/audit visibility (without mutating primary truths)**

### What this loop *is*

This is how production survives retention, late facts, projector bugs, and definition changes:

```
Need arises (retention boundary, late data, bug fix, feature definition change)
  -> Run/Operate declares backfill (scope + basis + purpose + outputs) as a governance fact
      -> rebuild derived stores/artifacts (IEG, OFP, offline datasets/manifests, audit indexes)
          -> new graph_version / input_basis states appear
              -> DF decisions going forward cite these new bases (provenance makes it visible)
```

Pins:

* Archive is a continuation of EB (same logical events); replay basis is always explicit.
* Backfill is declared, scoped, auditable; rebuilds **derived state only**; never mutates primary truths (EB events, label timelines, registry history, SR ledgers, engine outputs for a pinned identity).
* Watermarks are monotonic even under backfill; offsets don’t “lie.”

### Why this loop exists

Because without it, your platform will either:

* become non-reproducible after retention expires, or
* “fix” correctness by rewriting history (forbidden), or
* drift between online and offline due to unpinned bases.

### What changes after a backfill (and what doesn’t)

**Changes (allowed):**

* derived projections and their basis tokens (IEG `graph_version`, OFP `input_basis`, offline materializations/manifests, indexes)

**Never changes (forbidden):**

* the admitted event history itself (EB/Archive)
* label truth timelines (append-only)
* registry lifecycle history (append-only)
* SR run ledger/join surface history (append-only with supersedes)
* engine outputs for a pinned identity (immutable; fixes create new identity/version)

### Where this loop “touches” DF (while DF remains opaque)

DF’s only obligation is: **its provenance must make basis shifts visible** (so you can later explain why a decision under backfill/rebuild differs). That’s exactly why you pinned `graph_version` / `input_basis` as replay determinism hooks.

---

## How these loops interlock (the important coupling to keep explicit)

* **L1 generates outcomes** that feed **L4 audit closure** and **L5 human review**.
* **L4 audit gaps** and **L3 quarantine spikes** are legitimate inputs to **L2 degrade** (safety corridor).
* **L6 backfills** can temporarily increase lag/staleness → **L2 degrade** protects the system while rebuilding.
* **L5 learning** changes DF behavior *only* through Registry lifecycle events, never through silent swaps.

---

Yes — the environment ladder **touches every join/path/loop**, but only in *one allowed way*: it can change the **operational envelope**, not the **meaning** of the graph.

### The core ladder rule (applies to *all* J/P/L)

* **Local / Dev / Prod run the same platform graph and the same rails/join semantics** (ContextPins, canonical envelope, no-PASS-no-read, by-ref, watermarks/offsets, idempotency, append-only + supersedes, degrade mask as hard constraint, deterministic registry resolution, as-of semantics).
* Environments differ only by **profiles** (wiring + policy strictness), not code forks (“if prod then …”).
* If those semantics differ across envs, it’s not a ladder; it’s “three different platforms.” 

---

## What the ladder is allowed to change (and how it affects your J/P/L)

These are the only “dials” that can legitimately differ by env, while leaving J/P/L meaning intact:

1. **Scale** (volume, throughput, concurrency) 
2. **Retention + Archive enablement** (short local, medium dev, long prod + archive continuity) — but **offset/watermark meaning must not change**
3. **Security strictness + approval gates** (permissive local, “real enough” dev, strict prod) — mechanism exists everywhere
4. **Reliability posture** (HA, backups, incident tooling) 
5. **Observability depth** (debug-local vs SLO/corridor prod) — but correlation propagation remains identical

---

## The big consequence for joins/paths/loops: “policy config is part of behavior”

Most ladder-drift happens because people treat env config as “convenience.” Your docs pin the opposite:

* **Outcome-affecting policy config** (IG allowlists, schema acceptance, AL allowlists, registry rules/compat, SR required gates, degrade thresholds/corridors, retention/backfill rules) must be **versioned + auditable**, and its **revision must appear in receipts/provenance**.
* Promotion across envs is: **same code artifact + different approved profile/policy posture**, not “rewrite for prod.”

This directly impacts:

* **J6/J7 (DF→IG→EB)**: admission policy rev on receipts changes by env, but *ADMIT/DUPLICATE/QUARANTINE semantics don’t*.
* **J8/J9 (AL)**: action allowlists stricter in prod; outcomes always attributable and idempotent regardless.
* **J2/J11 (DL)**: degrade thresholds/corridors differ by env; DL still produces explicit masks and DF still obeys/records them.

---

## Loop-by-loop: what the ladder changes (and what it must not)

### L1 Action closure (EB→DF→AL→EB)

* **Allowed env differences:** real side effects might be stubbed/mocked locally; throughput + retries differ.
* **Must not change:** idempotency semantics and “outcome is a fact” (AL must still produce immutable outcomes even in local).

### L2 Safety/degrade loop (Obs→DL→DF)

* **Allowed env differences:** thresholds are looser locally (or “manual mode”), tighter in prod; observability sampling differs.
* **Must not change:** degrade is an explicit mask, fail-closed posture exists, DF records which posture it used.

### L3 Quarantine remediation loop (IG quarantine→fix→admit)

* **Allowed env differences:** local uses more permissive allowlists; prod requires approvals/strict policies.
* **Must not change:** quarantine is first-class (no silent drop), evidence pointers exist, re-admission is explicit.

### L4 Audit completeness loop (DLA quarantine/supersedes)

* **Allowed env differences:** storage depth/indexing/search tooling can be minimal locally.
* **Must not change:** append-only + supersedes semantics; “no half-truths” (quarantine incomplete provenance).

### L5 Human supervision loop (cases→labels→learning→registry→DF)

* **Allowed env differences:** volume of cases/labels; approval gates on promotions (light local, stricter dev, strict prod).
* **Must not change:** label store is append-only timelines with as-of semantics; learning influences production **only via Registry activation**, and DF records bundle ref.

### L6 Backfill/rebuild loop (derived state only)

* **Allowed env differences:** retention window length; archive enablement; frequency of backfills.
* **Must not change:** archive (if enabled) is a continuation of EB; replay basis is explicit; backfills are declared+auditable; only derived state is rebuilt; offsets/watermarks stay meaningful/monotonic.

---

## The practical ladder check that protects you from drift

Your CI/CD pin effectively says: every environment should be able to run **one “golden” end-to-end flow** with the same semantics (just smaller locally):
**SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA**, plus at least one label + offline shadow + registry resolution.

If that flow works in local with the same rails (even at tiny scale), dev catches the “real enough” failures (auth/quarantine/compat/gates), and prod is just stricter profiles + governance gates — then your joins/paths/loops remain the same platform, not three versions.

---

Here’s the **environment profile knob sheet** + the **deployment truths** you should keep in mind for **DF (still opaque)**. I’m keeping it directional (not vendor/tool specific), but concrete enough to guide how we “enter” DF without drift.

---

## 0) DF’s pinned deployment shape

DF is an **always-on service** on the hot path: it consumes admitted events (or optional synchronous requests), calls **OFP / IEG / DL / Registry**, and emits **Decision + ActionIntent** events back onto the traffic bus (canonical envelope). DF is “mostly stateless,” and its persistence burden is: **provenance must be carried in the emitted events** (bundle ref, snapshot hash, graph_version, degrade posture).

---

## 1) Profile structure: two buckets (don’t mix these)

Your deployment notes pin that “config” is not just tuning — it can change outcomes — so we must split:

### A) Wiring profile (non-semantic)

Endpoints, ports, resource limits, timeouts, scaling. It can change without claiming decision semantics changed (still logged for ops).

### B) Policy profile (outcome-affecting)

Admission allowlists, schema acceptance, action allowlists, registry eligibility/compat rules, DL thresholds/corridors, SR required gates, retention/backfill rules. These are **governed artifacts**: versioned + auditable, with stable identity + digest + monotonic revision, and provenance/receipts should cite the revision used.

---

## 2) Environment ladder knobs for DF (what may differ by env)

Across local/dev/prod, **rails and join semantics must not change**; only operational envelope changes (scale, retention/archive, security strictness, reliability, observability, cost).

So the DF-related env knobs are:

### A) Scale knobs

* EB consumer concurrency / max in-flight work
* batch sizes (consume + publish)
* worker pool sizing
* cache sizes (Registry/DL/OFP/IEG responses)
* autoscaling triggers (CPU, queue depth, consumer lag)

### B) Retention + archive knobs (affects replay windows, not semantics)

* EB retention length (short local, medium dev, longer prod)
* archive enabled/disabled
* “how far back can we replay” controls
  Retention length can differ; **offset/watermark semantics don’t.**

### C) Security strictness knobs (mechanism exists everywhere)

* service identity requirements (mTLS, tokens)
* AuthZ allowlists (what DF can read/call, what it can publish)
* approvals required for policy/bundle activations and backfills
  Dev should be “real enough”; prod strict.

### D) Reliability knobs

* retry budgets (per dependency)
* circuit breaker thresholds
* DL / Registry / OFP / IEG dependency timeouts and fallbacks
* HA posture (single instance local vs replicated dev/prod)

### E) Observability depth knobs (propagation semantics identical)

* trace sampling rate (higher local, lower prod)
* metric retention / alert thresholds
* dashboards/alerts enabled
  But: correlation keys and trace propagation are platform law.

---

## 3) DF wiring profile knobs (what you’ll actually configure per env)

These are the “DF runs anywhere” deployment knobs.

### Bus consumption (EB → DF)

* topic name(s) (e.g., `fp.bus.traffic.v1`)
* consumer group id
* start position policy (earliest/latest) for new groups
* checkpoint/commit policy (interval, sync/async)
* max poll/batch size, max in-flight
* dead-letter/quarantine integration is **not DF’s job** (IG is front door), but DF should expose “can’t process” as explicit outcomes/provenance later

Your blueprint pins the checkpoint meaning: `offset` is **exclusive-next** (next offset to read/apply).

### Publishing (DF → IG/EB)

* “publish path” endpoint (DF→IG API OR direct bus publish with IG-equivalent semantics)
* partition_key strategy for DF outputs (must be deterministic and stable)
  EB requires a deterministic `partition_key` but doesn’t define its composition.

### Dependency endpoints

* DL endpoint (or control-topic subscription)
* Registry endpoint (and optional lifecycle-event subscription)
* OFP endpoint
* IEG endpoint
  Plus: timeouts, retries/backoff, circuit breakers, and local caches (TTL).

### Runtime resources

* CPU/memory limits
* worker/thread counts
* queue sizes / backpressure thresholds
* graceful shutdown/drain timeouts

### Secrets injection (never in provenance)

* credentials for service identities / mTLS / tokens
* external integration secrets (if any; usually more on AL)
  Secrets must never appear in run ledgers/receipts/bundles/manifests/audit; at most a **key id**.

### Observability wiring

* OTLP collector endpoint
* log sink settings
* trace sampling rate (env knob)

---

## 4) DF policy profile knobs (the “this changes outcomes” knobs)

These should be treated like governed artifacts: versioned, promoted, and cited in DF provenance.

### A) Trigger policy (what DF will treat as decision stimuli)

* allowlist of `event_type` families that can trigger decisions
* explicit “never-trigger” list (DF outputs, AL outcomes unless explicitly allowed)
  (Prevents accidental feedback loops.)

### B) Dependency usage policy (within DL constraints)

Even though DL mask is the hard constraint, DF still needs policy on:

* which OFP feature groups are required vs optional per decision domain
* feature staleness tolerance (how stale is acceptable)
* “missing features” posture (safe fallback vs block)
  (These become **outcome-affecting**.)

### C) Fail-safe posture policy

* default safe outcome and safe intents when decisioning can’t be done safely
* retryability classification (recorded)

### D) Action intent shaping policy

* mapping decision outcomes → allowed action domains/types
* deterministic idempotency key recipe (must stay stable across envs)

### E) Provenance minimum policy

* what must be present before DF is allowed to emit a “normal” decision
* when to emit “degraded decision” vs “safe fallback”
  This matters because DLA will quarantine “half-truths.”

### F) Registry compatibility policy (guardrails)

* what bundle contract versions are acceptable
* whether “last-known-good bundle” is allowed (and under what conditions)
* rollout posture (canary scope, if used)
  (Still: Registry is deployable truth; DF records bundle ref used per decision.)

### G) Degrade policy inputs (owned by DL, but promoted as policy artifacts)

* DL threshold profile revisions + corridor checks are policy configs and are env-profiled (looser local, meaningful in prod), but remain explicit and recordable.

---

## 5) The “other deployment info” you should carry into DF internals

These are the big drift-killers when you stop treating DF as opaque:

### A) Promotion lanes (DF must survive all three)

CI/CD in your world promotes:

1. **code artifacts** (build once, run anywhere),
2. **policy/profile revisions**, and
3. **model/policy bundles** via Registry lifecycle.

So DF internals must be designed to make “code X + profile Y + bundle Z” observable in outputs/provenance.

### B) Minimum observability you should design DF around

DF must emit (at least) the platform-mandated metrics:

* decision latency
* fallback/safe-mode rate
* registry-resolution failures
* “blocked by degrade mask” rate
  …and it must propagate trace context end-to-end.

### C) Run/Operate never becomes DF’s shadow truth source

Run/Operate owns deploy/drain/backfill/retention and must emit governance facts for outcome-affecting operational acts; DF must *not* rely on hidden nondeterminism from ops (implicit “now”, silent retries that change meaning, etc.).

---

## A tight “bring-with-you” checklist before we enter DF

If you keep only these in your head, you’ll stay aligned:

1. **Profiles split**: wiring vs policy (policy is governed, cited). 
2. **DF unit**: always-on, mostly stateless, provenance-in-events.
3. **Bus reality**: at-least-once, offsets are spine, partition_key is deterministic.
4. **Observability law**: correlation everywhere; golden signals + lag/watermark metrics; traces propagate.
5. **Env ladder**: only operational envelope changes, not semantics.

When you’re ready to “enter DF,” the first internal thing I’ll want to lock is: **how DF maps these knobs into deterministic runtime behavior** (especially output identity/idempotency, dependency timeouts + fail-safe posture, and how policy revisions get stamped into provenance).

---

## USER: PAUSE FOR REFLECTION

Yep — this is the exact moment to **freeze the outer network truth** for DF so we don’t “accidentally redesign the platform” while we go inside the vertex.

Below is the **DF Outer Network Checkpoint** (designer-authoritative for this thread), grounded in your platform blueprint + deployment shape + engine interface rails.

---

## 1) DF’s identity as a vertex (what DF is allowed to be)

### DF’s truth ownership

DF is system-of-record for:

* **DecisionResponse**
* **ActionIntents**
* **Decision provenance** (what it knew + what constrained it). 

DF is **not** allowed to become authoritative for:

* admission/quarantine/duplicate (IG),
* stream meaning or ordering beyond partition offsets (EB),
* identity truth (IEG),
* feature computation (OFP),
* execution truth (AL),
* audit record semantics (DLA),
* labels (Label Store).

**No drift rule:** if DF starts “owning” any of the above, we’re no longer implementing the pinned network.

---

## 2) The only admissible boundary surfaces around DF (joins that define DF’s reality)

### DF’s only authoritative stimulus

**EB → DF**: DF decides only from **admitted events** on EB. EB is the durable fact log; delivery is at-least-once; replay tokens are partition/offset checkpoints.

**Canonical envelope is the boundary shape** for anything admitted and decisionable (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`, plus optional pins).

**Traffic role separation (engine-side law):** only **business_traffic** is allowed to drive the hot path; truth_products/audit_evidence/ops_telemetry do not become decision-driving traffic.

### DF’s hard constraints (control truth)

**DL → DF**: DF must treat `capabilities_mask` as **hard constraints** (no “best effort”), fail-closed, and record the exact posture used per decision.

**Registry → DF**: DF must resolve exactly one “active bundle” deterministically per scope (no “latest”), enforce compatibility (incl. degrade + feature versions), and record the bundle reference used.

### DF’s conditional context joins (derived truth)

**IEG → DF**: if DF uses identity/graph context, it must record the **graph_version** (watermark-based token).

**OFP → DF**: if DF uses features, it must request with **explicit as-of time** and record the provenance (`feature_snapshot_hash`, versions, freshness, `input_basis`, plus `graph_version` if consulted).

### DF’s only admissible way to “speak” to the platform

**DF → IG → EB**: DF outputs are producer traffic. They must go through the trust boundary semantics (admit/duplicate/quarantine + receipts) and become durable facts only via EB append. “Side-channel decision truth” is banned.

And downstream:

* **AL consumes ActionIntents** and is the only executor (effectively-once via `(ContextPins, idempotency_key)`), emitting immutable outcomes back onto the same bus path.
* **DLA consumes DF/AL/IG evidence** to write the append-only flight recorder; quarantines incomplete provenance; corrections via supersedes chains.

### Optional DF ingress (must not create a second truth world)

Deployment shape allows synchronous requests as an option, but **authoritative decisions must still obey “only one front door into the hot path.”** That means: preview-only, or event-submitted via IG→EB.

---

## 3) The composed production paths that DF participates in (no more, no less)

We already enumerated P1–P8; here’s the **outer-network drift check** version:

* **P1 (core hot path):** Producer → IG → EB → DF → IG → EB → AL → IG → EB → DLA. This is the “facts → decision → intent → outcome → audit” spine.
* **P2 (run gating):** SR’s READY + `run_facts_view` makes run/world truth enforceable; IG joinability protects DF from cross-run mixing.
* **P3 (degrade loop path):** Obs/Gov signals → DL posture → DF constrained behavior → outcomes/lag → signals. Explicit + recorded.
* **P4 (quarantine remediation path):** IG quarantine → explicit triage/governance change → re-evaluate → admit → EB → DF. No silent drop; no silent edits.
* **P5 (case/labels):** DF/AL/DLA outputs are *evidence*, Case Workbench builds immutable timelines, Label Store holds append-only label truth.
* **P6 (learning):** EB history + DLA exports + Label Store → Offline Shadow → Model Factory → Registry → DF. DF changes only via governed activation.
* **P7 (backfill):** Run/Operate declares backfill (auditable), rebuilds derived state (IEG/OFP/offline/indexes), DF’s future decisions cite new bases via provenance; primary truths never mutate.
* **P8 (optional sync):** preview-only or event-submitted authoritative path; never a second reality.

If DF’s internal design doesn’t preserve these paths exactly, we’re drifting.

---

## 4) The production loops that must remain true as we “enter” DF

* **L1 action closure:** EB event → DF intent → AL outcome → EB. DF must avoid accidental trigger loops on outcomes unless explicitly allowlisted.
* **L2 degrade loop:** explicit mask controls behavior; no silent coupling.
* **L3 quarantine remediation:** quarantine is first-class; explicit re-admission with evidence.
* **L4 audit completeness:** DLA quarantines half-truths; supersedes chain for correction.
* **L5 human supervision:** evidence → cases → labels → learning → registry → DF. Labels are timelines; as-of joins; no learning from “what the system decided.”
* **L6 backfill/rebuild:** only derived state rebuilds; basis tokens make changes visible.

---

## 5) Drift bans (things we must not accidentally introduce while designing DF internals)

These are **explicitly banned moves** per the pins:

1. **DF cannot bypass IG→EB** for authoritative outputs.
2. **DF cannot use hidden “now”**; decision boundary time is domain time (`ts_utc`), and OFP uses explicit as-of.
3. **DF cannot treat truth_products/audit_evidence/ops_telemetry as traffic.**
4. **DF cannot “pick latest” bundles**; registry resolution is deterministic + compatibility-aware.
5. **DF cannot silently change behavior under stress**; it must obey DL mask and record the posture used.
6. **DF cannot emit “half-provenance decisions”** and pretend audit will sort it out; DLA quarantines half-truths.
7. **DF cannot rely on scanning/discovery** for run/world truth; SR’s join surface is the broker.

---

## 6) The extra “designer pins” we introduced in this chat (beyond the blueprint) to prevent drift later

These are not contradicted by the platform docs (they’re in the “key recipes live locally” gap), but once stated, we will treat them as **our authoritative DF v0 stance** going inside:

* **Authoritative decisioning is EB-driven.** Any synchronous Decision API is either preview-only or event-submitted via IG→EB so we never create two truth worlds.
* **Trigger allowlist + self-loop protection** (DF does not treat DF/AL outputs as triggers unless explicitly pinned).
* **Action intent idempotency keys are deterministic and “domain-safe”** (we’ll define the recipe when we enter DF, but it must prevent conflicting duplicates from causing multiple side effects).

(Everything else we’ve said is already explicitly in the blueprint rails.)

---

## Bottom line before we “enter DF”

If DF’s inner design:

* consumes only admitted canonical-envelope traffic,
* obeys DL mask as hard constraints,
* resolves registry bundles deterministically and records them,
* uses OFP/IEG only with explicit basis/provenance tokens,
* emits decisions/intents only through IG→EB,
* and leaves an audit-joinable trail (so DLA can record without half-truths),

…then we can safely illuminate the vertex without drifting from the pinned outer network.

---

Yep — one level deeper, but still **opaque boxes inside DF**. Think of this as “DF’s internal neighborhoods” (subnetworks) and the **edges between them**, without opening any neighborhood yet.

Here’s the **minimal, production-shaped** internal decomposition I’d pin for DF.

---

## DF internal subnetworks (L1 modules), all still opaque

### DF-A — Intake and Normalization

**Role:** Turn “something arrived” into a canonical DF work item.
**Inputs:** EB events (primary), optional sync preview requests (if enabled).
**Outputs:** `WorkItem` (event ref + pins + parsed envelope + trigger classification).
**Pins it must enforce:** trigger allowlist + loop prevention (don’t decision-trigger on DF/AL/DLA outputs unless explicitly pinned).

---

### DF-B — Decision Boundary and Basis Fence

**Role:** Define *what this decision is allowed to know* (time + replay basis).
**Inputs:** `WorkItem`.
**Outputs:** `DecisionBoundary` (event_time from `ts_utc`, event_basis pointer, optional no-peek fence metadata).
**Pins it must enforce:** no hidden “now”; event_time is the decision boundary; basis is explicit (joinable to offsets/watermarks).

---

### DF-C — Constraints and Bundle Selection

**Role:** Compute the *allowed* decision posture and select “what logic is active.”
**Inputs:** `DecisionBoundary`.
**Outputs:** `DecisionPlan` = {degrade posture snapshot, active bundle ref, compatibility outcome}.
**Pins it must enforce:** DL mask is hard constraints; registry selection is deterministic; incompatibility → safe posture + explicit reason.

---

### DF-D — Context Acquisition

**Role:** Acquire the *context DF is permitted to use* (conditionally).
**Inputs:** `DecisionPlan` + `DecisionBoundary`.
**Outputs:** `ContextSnapshot` = {optional IEG context + graph_version, optional OFP snapshot + input_basis + snapshot hash + freshness}.
**Pins it must enforce:** only call OFP/IEG if allowed by degrade; always use explicit as-of = event_time; capture basis tokens.

---

### DF-E — Decision Execution

**Role:** Produce the decision outcome from stimulus + plan + context (still opaque logic).
**Inputs:** `DecisionBoundary` + `DecisionPlan` + `ContextSnapshot`.
**Outputs:** `DecisionDraft` (decision outcome + internal rationale hooks, but not yet packaged).
**Pins it must enforce:** determinism target: given the same boundary/plan/snapshot, decision output is stable.

---

### DF-F — Intent Synthesis and Output Identity

**Role:** Turn a decision into **ActionIntents** and assign stable identities.
**Inputs:** `DecisionDraft` + `DecisionBoundary` + `DecisionPlan`.
**Outputs:** `DecisionOutputs` = {DecisionResponse, 0..N ActionIntents} with deterministic `event_id`s and `idempotency_key`s.
**Pins it must enforce:** domain-safe idempotency; stable event_ids for dedupe; intent shaping must respect degrade constraints.

---

### DF-G — Provenance and Evidence Packaging

**Role:** Assemble the minimum provenance bundle required for audit/replay/case learning.
**Inputs:** `DecisionOutputs` + `DecisionPlan` + `ContextSnapshot` + `DecisionBoundary`.
**Outputs:** `DecisionPackage` (DecisionResponse + intents + provenance block).
**Pins it must enforce:** no half-truth decisions (if provenance minimum missing, force safe fallback or explicitly mark as constrained so DLA won’t “lie by omission”).

---

### DF-H — Publish and Receipt Handling

**Role:** Emit packaged outputs through the trust boundary and handle admission outcomes.
**Inputs:** `DecisionPackage`.
**Outputs:** Publish attempts + IG receipts (ADMIT/DUPLICATE/QUARANTINE) + publish observability signals.
**Pins it must enforce:** DF outputs become facts only via IG→EB semantics; retries must be idempotent via stable IDs.

---

### DF-X — Cross-cutting Rails (not a separate pipeline, but a “mesh” across all boxes)

These aren’t “steps,” they’re constraints that touch every module:

* **Determinism & Idempotency rail** (stable identities, stable ordering)
* **Safety rail** (fail-closed posture, conservative defaults)
* **Observability rail** (trace propagation, golden signals, correlation keys)
* **Policy provenance rail** (record which posture/bundle/snapshot basis was used)

(We won’t open these yet; just acknowledge they exist.)

---

## How these subnetworks connect (still opaque inside each)

```text
EB events / (optional preview req)
          |
          v
     [DF-A Intake]
          |
          v
 [DF-B Boundary/Basis]
          |
          v
 [DF-C Constraints+Bundle] <---(DL, Registry joins happen “behind” this box)
          |
          v
 [DF-D Context Acquire]   <---(OFP, IEG joins happen “behind” this box)
          |
          v
  [DF-E Decision Exec]
          |
          v
 [DF-F Intent+Identity]
          |
          v
 [DF-G Provenance Pack]
          |
          v
 [DF-H Publish+Receipts]  ---> IG -> EB
```

---

## Why this is the right L1 cut (so we don’t drift later)

* It mirrors the **outer joins** cleanly: DL/Registry “live” behind DF-C, OFP/IEG behind DF-D, IG behind DF-H, EB behind DF-A.
* It makes the three hardest invariants explicit early:

  1. **boundary time & basis** (DF-B)
  2. **hard constraints** (DF-C)
  3. **audit-grade provenance** (DF-G)

---

Yep. Here’s the **internal join / path / loop map** for DF **in production**, keeping each L1 subnetwork **opaque** (DF-A … DF-H, DF-X). I’m going to name internal joins as **I-J#**, paths as **I-P#**, loops as **I-L#** so we don’t collide with the platform-level J/P/L you already pinned.

---

## Internal joins (edges) inside DF

### The main decision spine (data-plane joins)

**I-J1: DF-A → DF-B (Intake → Boundary/Basis)**
`WorkItem` framing handoff: parsed envelope, event_ref, pins, trigger classification.

**I-J2: DF-B → DF-C (Boundary → Constraints/Bundle)**
`DecisionBoundary` handoff: event_time (`ts_utc`), basis pointer, scope keys for plan selection.

**I-J3: DF-C → DF-D (Plan → Context Acquisition)**
`DecisionPlan` handoff: degrade posture snapshot + active bundle ref + “allowed capabilities” + “what context is permitted.”

**I-J4: DF-D → DF-E (Context → Decision Exec)**
`ContextSnapshot` handoff: OFP snapshot (hash+basis+freshness) and/or IEG context (graph_version), or explicit “not used” reasons.

**I-J5: DF-E → DF-F (Decision Exec → Intent+Identity)**
`DecisionDraft` handoff: outcome + internal decision summary (still opaque) to turn into stable external forms.

**I-J6: DF-F → DF-G (Outputs → Provenance Pack)**
`DecisionOutputs` handoff: DecisionResponse + ActionIntents (with deterministic IDs + idempotency anchors), not yet fully provenance-complete.

**I-J7: DF-G → DF-H (Package → Publish/Receipts)**
`DecisionPackage` handoff: outputs + provenance block ready to be treated as “traffic” for IG admission.

### The “done-ness” join (critical in production)

**I-J8: DF-H → DF-A (Receipts/Completion → Intake checkpointing)**
This is the internal handshake that decides: **when is a WorkItem considered “done”** (and therefore safe to advance the EB consumer checkpoint / acknowledge completion)?

Pinned conceptually (not implementation detail):

* *Done* means DF has attempted to publish its outputs and received an **IG receipt outcome** (ADMIT/DUPLICATE/QUARANTINE) for each output event it is responsible for.
* Only then does DF treat the input as complete and allow intake checkpointing to move forward.

This join is the core “no lost decisions” vs “duplicates are safe” balance.

### Cross-cutting rail joins (control-plane mesh touches multiple nodes)

These are not “steps,” but they are real joins in production:

**I-J9: DF-X ↔ DF-A (Observability + Backpressure)**
Lag / error / queue depth signals influence intake pacing and drain behavior (without changing semantics).

**I-J10: DF-X ↔ DF-C (Policy snapshotting / cache / lifecycle)**
DL posture snapshots and registry bundle resolution can be cached/subscribed, but DF-C must produce a **per-WorkItem plan snapshot** that becomes immutable for that WorkItem.

**I-J11: DF-X ↔ DF-D (Dependency governance)**
Timeout budgets, circuit posture, and “allowed feature groups” controls are applied here, but DF-D must still return explicit snapshot provenance or explicit absence reasons.

**I-J12: DF-X ↔ DF-H (Publish governance)**
Drain/pause controls, publish retry budgets, and receipt recording/metrics.

---

## Internal paths (end-to-end sequences) in DF

### I-P1 — Normal authoritative decision path (EB-driven)

`DF-A → DF-B → DF-C → DF-D → DF-E → DF-F → DF-G → DF-H → (I-J8 complete)`

This is the “everything available and allowed” path.

### I-P2 — Non-trigger path (intake sees an event DF shouldn’t decision on)

`DF-A → (classify as non-trigger) → DF-X metrics → (complete/commit with no outputs)`

Key: **still deterministic and observable**, but produces no DecisionResponse/Intents.

### I-P3 — Constraints-only safe fallback path (no context used)

Used when:

* degrade mask forbids OFP/IEG, **or**
* required dependencies unavailable and policy says “fail safe now.”

Path:
`DF-A → DF-B → DF-C → (skip DF-D/DF-E heavy work) → DF-F → DF-G → DF-H`

DF still emits a DecisionResponse (safe outcome) and possibly intents (e.g., review/step-up), with provenance stating why context wasn’t used.

### I-P4 — Context-limited path (partial context)

Two common variants:

* **I-P4a (OFP only):** `A→B→C→D(OFP)→E→F→G→H`
* **I-P4b (IEG only):** `A→B→C→D(IEG)→E→F→G→H`

Driven by degrade mask or availability. Provenance must explicitly reflect what was used and what wasn’t.

### I-P5 — Preview path (optional, non-authoritative)

If enabled:
`External preview request → DF-A → DF-B → DF-C → DF-D → DF-E → DF-F → (return to caller)`

No DF-H publish (no intents into the platform truth world), and the response is tagged preview/what-if.

### I-P6 — Publish “duplicate accepted” path

`… → DF-H → IG returns DUPLICATE receipts → I-J8 completion`

This is normal under retries/redelivery. DF treats DUPLICATE as success and completes safely.

### I-P7 — Publish quarantine path (rare but production-real)

`… → DF-H → IG returns QUARANTINE receipts → DF-X alerts/metrics → I-J8 completion (with “quarantined output” recorded)`

Key: DF must not “fix” or bypass quarantine internally. Quarantine is a first-class outcome.

---

## Internal loops (cycles) that exist in production DF

### I-L1 — Input replay loop (idempotency loop)

EB redelivers the same input event (or DF restarts and replays). That re-enters **I-P1/I-P3/I-P4**, but the loop is made safe by:

* stable output identities,
* and publish receipts / dedupe.

Conceptually: `DF-A (same WorkItem again) → … → DF-H (DUPLICATE) → complete`

### I-L2 — Dependency retry / circuit loop (bounded)

For DF-D (OFP/IEG) and DF-H (publish), bounded retry happens as:
`attempt → failure → retry within budget → (success | degrade-to-safe | emit constrained decision)`

This loop must be bounded and must not introduce hidden “eventually we changed the decision” behavior for the same WorkItem unless explicitly recorded.

### I-L3 — Plan snapshot loop (resolve → verify → fallback)

Inside DF-C as a black box, there is a conceptual cycle:
`resolve degrade + bundle → compatibility check → (ok | choose safe fallback | resolve alternate allowed bundle)`

The important production property is that DF-C outputs exactly one **DecisionPlan snapshot** per WorkItem, and that snapshot is what downstream boxes obey (no mid-flight plan mutation).

### I-L4 — Provenance completeness loop (fetch-or-fallback)

DF-G is where “audit-grade completeness” is enforced. The cycle is:
`assemble provenance → detect missing required anchors → (try to fetch missing anchor | downgrade to safe constrained decision)`

This prevents “half-truth decisions” that would later poison audit.

### I-L5 — Receipt-driven completion loop (commit gating)

This is the big one operationally:
`DF-A processes input → DF-H publishes → wait for receipts → complete → advance input checkpoint`

If DF crashes between publish and checkpoint, replay will occur and yield duplicates — which is acceptable because IDs are stable and IG dedupes.

### I-L6 — Control-plane refresh loop (cache/subscription)

Even with DF opaque, production DF will run a continuous loop:

* DL posture refresh (push or pull)
* Registry lifecycle refresh (push or pull)
* dependency health sampling
  These updates affect **future** WorkItems (new plans), not in-flight ones.

---

## One internal graph view (still opaque nodes)

```text
             (control-plane mesh: DF-X)
       +-----------------------------------+
       |  caches / subscriptions / drain    |
       |  observability / backpressure      |
       +--+-----------+-----------+---------+
          |           |           |
          v           v           v
[DF-A] -> [DF-B] -> [DF-C] -> [DF-D] -> [DF-E] -> [DF-F] -> [DF-G] -> [DF-H]
  ^                                                                             |
  |--------------------------- I-J8: receipts -> completion/ack ----------------|
```

---

If you’re aligned with this inventory, the clean next step is: pick **one internal loop** to illuminate first (usually **I-L5 receipt-driven completion** or **I-L3 plan snapshot**, because they constrain everything else), while keeping all other boxes opaque.

---

Yep. We’ll illuminate **I-J1 → I-J4** as **boundary handshakes between opaque DF subnetworks**, and I’ll explicitly declare what is **in-bounds** vs **out-of-bounds** relative to the platform pins (canonical envelope, ContextPins+seed taxonomy, explicit as-of, watermarks, hard degrade mask, deterministic bundle resolution, replay safety).

I’m going to describe each join in the same structure:

* **Purpose**
* **What crosses the join (conceptual object)**
* **Hard invariants (non-negotiable)**
* **Explicit failure/edge states**
* **Drift bans (what is *not* allowed)**

---

# I-J1 — DF-A → DF-B

## Intake & Normalization → Decision Boundary & Basis

### Purpose

Turn “an EB delivery happened” into a **single, canonical internal unit of work** that downstream logic can treat deterministically and safely under replay.

### What crosses the join: `WorkItem`

`WorkItem` is the *internal* carrier for one EB-delivered event plus its replay coordinates.

Minimum conceptual fields (not a schema, just the boundary truth):

* **`envelope`**: the **CanonicalEventEnvelope** (validated shape)
  Required fields: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`. 
  Optional pins (if present): `parameter_hash`, `scenario_id`, `run_id`, `seed`, plus trace fields (`trace_id`, `span_id`, `producer`, `schema_version`, `parent_event_id`).
* **`event_ref`**: by-ref pointer to what DF consumed (at minimum `stream_name`, `partition_id`, `offset`)
  This is the replay anchor that later becomes part of decision provenance (by-ref posture).
* **`pins`**: **ContextPins + Seed taxonomy**
  ContextPins are `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`; `seed` is separate and carried when applicable.
* **`trigger_classification`**: {`TRIGGER` | `NON_TRIGGER` | `IGNORE`} + **reason**
  (Reason is part of observability and later audit explainability; event types are allowlisted by policy.)
* **`ingest_meta`**: “apply time” facts local to DF (received_at, consumer_group, attempt)
  **Important:** these are *not* domain time; they’re for ops only.

### Hard invariants (non-negotiable)

1. **Envelope validity is enforced before I-J1 completes**
   If the object is not a canonical envelope (missing required fields, extra top-level fields beyond the schema), it does not become a WorkItem.

2. **Time semantics don’t collapse**
   `ts_utc` remains the domain decision time candidate. `received_at` is not allowed to substitute for it.

3. **Replay safety is assumed**
   DF must assume duplicates and retries; I-J1 must be safe under “same `event_id` seen again” and/or “same EB position seen again.”

### Explicit failure/edge states (must be representable)

* `INVALID_ENVELOPE` (schema breach) → quarantine internally (or drop into a DF “non-decisionable” path with explicit metrics); never silently parse partial truth.
* `MISSING_REQUIRED_PINS` (for run-joinable classes) → classify as non-trigger (or safe fallback later), but must be explicit.

### Drift bans

* **Not allowed:** DF-A “fixes” the envelope (e.g., invents ts_utc, rewrites pins, drops unknown fields) — that violates the platform boundary contract.
* **Not allowed:** DF-A decides using any context from OFP/IEG/DL/Registry; that belongs downstream (DF-B/C/D).
* **Not allowed:** “scan latest” behavior during intake (by-ref is law). 

---

# I-J2 — DF-B → DF-C

## Decision Boundary & Basis → Constraints & Bundle Selection

### Purpose

Freeze “what this decision is about” into a **DecisionBoundary** that downstream planning must obey — especially time, pins, and replay basis.

### What crosses the join: `DecisionBoundary`

Minimum conceptual fields:

* **`decision_key`**: deterministic identifier for the decision attempt, derived from pins + input event identity (so it’s stable under replay). (Exact recipe can be pinned later, but it must be deterministic.)
* **`event_time_utc`**: **exactly** the envelope `ts_utc` (domain event time).
* **`event_ref`**: the EB by-ref pointer (stream/partition/offset) carried forward.
* **`pins`**: ContextPins (+ seed when applicable).
* **`decision_scope`**: a deterministic scope key derived from `event_type` family + pins (used for registry resolution + policy selection).
  This is outcome-affecting and must be traceable to a **policy revision**.
* **`basis_fence` (v0 pin)**: an explicit “no-peek” hint derived from EB ordering:

  * offsets are **exclusive-next** checkpoints 
  * so for an input event at offset `o`, the safe fence for that same partition is `next_offset_to_apply = o+1`
    This is the anchor we use to avoid consuming “future” context from the same partition.

### Hard invariants (non-negotiable)

1. **Boundary time is `ts_utc`, always** (no hidden “now”).
2. **Basis is explicit and by-ref** (the event_ref is carried forward as an audit anchor).
3. **Pins are not optional if the event claims run/world joinability** (ContextPins are the canonical join pins; seed is separate and carried when applicable).

### Explicit failure/edge states

* `UNSCOPED_EVENT` (missing pins that are required for this event family)
  → DecisionBoundary still exists, but `decision_scope` may be “non-joinable”; downstream planning must treat it as constrained and likely safe-fallback.
* `AMBIGUOUS_SCOPE` (event_type maps to multiple decision domains)
  → forbidden; scope mapping must be deterministic and policy-owned (profiled + versioned).

### Drift bans

* **Not allowed:** DF-B calling DL/Registry/OFP/IEG. DF-B defines the boundary; it doesn’t fetch context.
* **Not allowed:** replacing missing `ts_utc` with `emitted_at_utc` or arrival time; if `ts_utc` is missing, the envelope is invalid (J1 should have rejected).

---

# I-J3 — DF-C → DF-D

## Constraints & Bundle Selection → Context Acquisition

### Purpose

Produce a **single, immutable DecisionPlan snapshot** for this WorkItem:

* what DF is **allowed** to do (degrade mask),
* what logic is **active** (registry bundle),
* what context is **permitted/required** (feature groups, IEG usage),
* and what must be recorded for provenance.

### What crosses the join: `DecisionPlan`

Minimum conceptual fields:

* **`degrade_decision`**: `{mode, capabilities_mask, provenance_ref/decided_at}`
  Mask is **hard constraints** and must be recorded per decision.
* **`bundle_ref`**: deterministic ActiveBundleRef (id + digest posture + compatibility metadata).
  Resolution is deterministic; no “latest.” DF must record the chosen ref.
* **`allowed_capabilities`**: derived from mask ∩ bundle requirements
  (e.g., “IEG allowed?”, “which feature groups may be requested?”).
* **`context_requirements`**: for this decision_scope, which context sources are:

  * REQUIRED vs OPTIONAL vs FORBIDDEN
    (This is what later drives safe fallback vs “continue with less.”)
* **`policy_revisions`**: references to outcome-affecting policy/profile revisions used to build the plan (DL threshold profile rev, registry compat policy rev, DF trigger policy rev, etc.).

### Hard invariants (non-negotiable)

1. **Degrade mask is authoritative**
   If `capabilities_mask` forbids a capability, DF-D must behave as if it doesn’t exist.

2. **Bundle resolution is deterministic and compatibility-aware**
   If the active bundle is incompatible with mask or feature definitions, the plan must force a safe posture and record why.

3. **Plan snapshot immutability**
   Once DF-C emits a DecisionPlan for a WorkItem, it must not be mutated mid-flight by later DL/Registry updates. (Updates affect *future* WorkItems.) This is required for replay determinism.

### Explicit failure/edge states

* `DL_UNAVAILABLE` → plan becomes `FAIL_CLOSED` (stricter posture), recorded.
* `REGISTRY_UNAVAILABLE` → plan forces safe fallback (or “last-known-good” only if you later pin that as allowable policy); recorded.
* `ACTIVE_BUNDLE_INCOMPATIBLE` → safe plan + explicit reason. 

### Drift bans

* **Not allowed:** DF-D “chooses to call OFP/IEG anyway” if the plan forbids it.
* **Not allowed:** DF-C produces “best effort” plan without recording which policy revisions were in force (policy config is governed behavior).

---

# I-J4 — DF-D → DF-E

## Context Acquisition → Decision Execution

### Purpose

Make DF-E purely decision logic (compute) by providing it a **frozen ContextSnapshot**:

* what context was obtained,
* what was not obtained (and why),
* and the provenance tokens needed for audit/replay/learning parity.

### What crosses the join: `ContextSnapshot`

Minimum conceptual fields:

#### OFP block (if used)

* `features`: opaque map
* `provenance`:

  * `feature_snapshot_hash` (deterministic)
  * group versions used + freshness/stale posture
  * `as_of_time_utc` (must equal DecisionBoundary event_time)
  * `input_basis` watermark vector
  * `graph_version` if IEG consulted
    (This is pinned as required provenance for `get_features` and DF’s recording obligations.)

#### IEG block (if used)

* `identity_context`: opaque
* `graph_version`: applied-offset watermark vector (+ stream identity), recorded when used.

#### Explicit “not used” reasons (must be structured)

For each context source, DF-D returns one of:

* `USED`
* `FORBIDDEN_BY_MASK`
* `NOT_REQUESTED_BY_PLAN`
* `UNAVAILABLE`
* `STALE_BEYOND_TOLERANCE`
* `NOT_FOUND`
* **`BASIS_VIOLATION`** *(see below)*

### Hard invariants (non-negotiable)

1. **No hidden “now”**
   OFP requests must use explicit `as_of_time_utc`, and DF-D must preserve it in the snapshot provenance.

2. **Watermark/basis tokens are first-class outputs**
   DF-E is not allowed to “assume” context freshness; it must be told via `input_basis` / `graph_version` and explicit freshness flags.

3. **DF-E must not call OFP/IEG**
   All external context calls happen in DF-D; DF-E consumes a frozen snapshot. This is how we keep provenance complete and behavior deterministic.

### Designer authority: the “basis violation” rule (in-bounds declaration)

To stay **inline with the replay/determinism boundary**, I’m pinning this v0 rule:

**If DF-D receives OFP/IEG context whose returned `input_basis` / `graph_version` indicates the same partition has applied offsets beyond the DecisionBoundary fence for the input event’s partition, DF must treat that context as `BASIS_VIOLATION` and proceed without it (or fall back safely), recording the violation.**

Why this is in-bounds:

* Offsets/watermarks are the universal “what was applied” token.
* Deterministic outcomes under replay are a platform law. 
* If we knowingly use “future” applied context relative to the input event’s partition ordering, replay can diverge.

This is the cleanest way to prevent hidden “future knowledge” without forcing us to fully spec OFP/IEG “serve-as-of-offset” mechanics right now.

### Explicit failure/edge states

* OFP returns stale/missing features → DF-D marks `STALE_BEYOND_TOLERANCE` or `UNAVAILABLE` (per plan), and DF-E must treat the decision as constrained (often safe fallback).
* IEG unavailable or forbidden → DF-D returns explicit reason; DF-E must not invent identity context.

### Drift bans

* **Not allowed:** DF-D silently omits provenance tokens (snapshot hash, input_basis, graph_version) when context is used.
* **Not allowed:** DF-D “fixes” freshness by reinterpreting it; freshness/stale posture must be explicit and carried forward. 

---

## Quick “shape check” (so we don’t drift as we go deeper)

If we keep just these truths intact:

* I-J1 yields a validated **WorkItem** (canonical envelope + EB ref + pins + trigger classification).
* I-J2 yields a deterministic **DecisionBoundary** (ts_utc + by-ref basis + scope + fence).
* I-J3 yields an immutable **DecisionPlan** (hard mask + deterministic active bundle + policy rev refs).
* I-J4 yields a frozen **ContextSnapshot** with explicit provenance tokens and explicit “not used” reasons.

…then DF-E and downstream joins can be designed without ever violating the outer network laws.

---

Absolutely. We’ll illuminate **I-J5 → I-J8** as **production internal boundary joins** between still-opaque subnetworks, and I’ll **declare pins** where the platform boundary would otherwise get fuzzy (idempotency, provenance, completion). Everything below is **authoritative for this DF thread** unless it contradicts your already-pinned platform laws (canonical envelope, IG trust boundary, EB replay spine, AL effectively-once, DLA append-only, explicit degrade, deterministic registry).

---

# I-J5 — DF-E → DF-F

## Decision Execution → Intent + Identity

### Purpose

Convert “a decision exists” into **stable, externalizable outputs**:

* one **DecisionResponse** (the authoritative decision fact), and
* zero or more **ActionIntents** (what AL should attempt),
  with **deterministic identity + idempotency anchors** so retries/redelivery don’t create new facts.

### What crosses the join: `DecisionDraft`

This is the **opaque** internal result of DF-E, but the boundary contract requires it contains enough structure for DF-F to safely externalize.

Minimum conceptual content:

* **`decision_outcome`**: a canonical outcome enum + any scored/typed fields (opaque scoring ok)
* **`decision_scope`**: the domain bucket (derived from event_type family)
* **`intent_candidates[]`**: a list of *intended* actions, each with:

  * `action_domain` (coarse bucket: e.g., `txn_disposition`, `case_queue`, `notify`)
  * `action_type` (specific verb)
  * `action_key` (deterministic “which one” key inside the domain; see pin below)
  * `action_params` (opaque, but deterministic; must not include nondeterministic timestamps)
* **`explainability_hooks`** (opaque): reason codes / rule hits / model signals — allowed, but must be deterministic given the frozen boundary/plan/snapshot.

### Hard invariants (non-negotiable)

1. **No external calls on/after I-J5**
   DF-F must not consult OFP/IEG/DL/Registry. All those choices are already frozen in Boundary/Plan/Snapshot upstream. This is required for provenance integrity and replay determinism.

2. **DecisionDraft must be “purely derived”**
   No nondeterministic fields (“now”, random IDs, iteration-order dependent maps) may appear in any field that will later influence output IDs or idempotency keys.

3. **Degrade constraints are re-enforced here**
   Even if DF-E is correct, DF-F is a safety backstop: if the plan/mask forbids an action_domain or action_type, DF-F must drop/replace it with allowed safe equivalents (and mark that in explainability hooks).

### Designer pin (authoritative): **deterministic intent identity seed**

To avoid “multiple actions in same domain collide” while still preventing conflicting duplicates, DF-F will require every intent has a deterministic **`action_key`**:

* **`action_key`** is a stable identifier derived from the intent’s *target*, e.g.:

  * `case_queue`: `queue_name + case_subject_id`
  * `notify`: `channel + recipient_id`
  * `txn_disposition`: `txn_id` (or `auth_id`)
    If no natural target exists, the key is a stable literal like `"primary"` (meaning “at most one intent in this domain per event”).

This keeps the system both expressive and deterministic.

### Explicit edge/failure states

* `NO_ACTIONS` (valid): decision produces no intents.
* `MASK_FORBIDS_ALL_ACTIONS` (valid): intents list becomes empty + reason marked.
* `DRAFT_INCONSISTENT` (invalid): intent missing domain/type/key → DF-F must coerce to safe fallback behavior (usually “review/step-up”) rather than emitting malformed intents.

### Drift bans

* **Not allowed:** DF-F invents a new decision outcome because publish looks hard. Outcomes are decided in DF-E; DF-F only externalizes/filters.
* **Not allowed:** emitting intents that depend on wall-clock time or random IDs.

---

# I-J6 — DF-F → DF-G

## Outputs + Identity → Provenance Pack

### Purpose

Take “stable outputs exist” and attach the **minimum audit/replay/learning provenance** so DLA/cases/offline can join everything by-ref without half-truths.

### What crosses the join: `DecisionOutputs`

This is the “skeleton” that is already identity-stable.

Minimum conceptual content:

* **DecisionResponse (internal form)**:

  * `decision_event_id` (stable)
  * `decision_scope`
  * `decision_outcome`
  * `basis_ref` (input `event_id` + EB coords pointer)
* **ActionIntents[] (internal form)**:

  * `intent_event_id` (stable)
  * `idempotency_key` (for AL uniqueness scope)
  * `action_domain`, `action_type`, `action_key`
  * `decision_event_id` pointer (so intents join to the decision)
  * `basis_ref` pointer (optional if you want all intents joinable without decision lookup)

### Designer pin (authoritative): **output identity recipes**

These recipes are how we guarantee idempotency under replay without storing a “decisions DB”.

* **DecisionResponse `event_id`**
  `H("decision_response", ContextPins, input_event_id, decision_scope)`
  (One per input event per scope; deterministic.)

* **ActionIntent `event_id`**
  `H("action_intent", ContextPins, input_event_id, action_domain, action_key)`

* **ActionIntent `idempotency_key`** (what AL uses)
  `H(ContextPins, input_event_id, action_domain, action_key)`
  This preserves the earlier “domain-safe” stance (prevents conflicting duplicates from multiplying side effects) while allowing multiple intents in the same domain when they have different `action_key`.

### Hard invariants (non-negotiable)

1. **Stable ordering**
   ActionIntents must be emitted in a canonical order (e.g., `(action_domain, action_key, action_type)` lexicographic). This prevents “same decision, different ordering” drift.

2. **Linkage is explicit**
   Every intent must reference `decision_event_id` (and every decision must reference its input basis). You must never rely on “temporal proximity” for joins.

3. **No missing identity anchors**
   If DF-F cannot compute stable IDs/keys, it must force safe fallback behavior upstream of publish (emit no intents and mark reason), rather than emitting unstable identities.

### Explicit edge/failure states

* `INTENT_COLLISION` (two intents hash to same `(domain,key)`): DF-F must coalesce deterministically (keep canonical “winner” by rule) and record the collision in explainability hooks.
* `ID_RECIPE_VERSION` (optional): If you ever evolve these recipes, you must version them explicitly so old vs new is auditable (policy-profiled, not “silent code change”).

### Drift bans

* **Not allowed:** generating UUIDs for DecisionResponse/Intent IDs.
* **Not allowed:** letting map iteration order determine intent order.

---

# I-J7 — DF-G → DF-H

## Provenance Pack → Publish + Receipts

### Purpose

Convert “outputs + provenance exist” into **canonical envelope events** ready for IG admission, and define the publish unit that DF-H must deliver.

### What crosses the join: `DecisionPackage`

Contains:

* **`publish_set[]`**: a list of envelope events ready to submit
* **`required_set[]`**: subset that must receive terminal receipts for the WorkItem to be complete
* **`provenance_block`**: the minimum provenance DF is responsible for

### What “provenance_block” must contain (minimum viable)

For each DecisionResponse (and referenced by intents):

* **Input basis**: `input_event_id`, `event_type`, `event_ts_utc`, EB coords pointer
* **Degrade posture used**: mode + enough identity to reference the mask snapshot
* **Bundle used**: ActiveBundleRef
* **OFP provenance** (if OFP used): `feature_snapshot_hash`, versions, freshness flags, `as_of_time_utc`, `input_basis`
* **IEG provenance** (if IEG used): `graph_version`
* **Explicit “not used” reasons** for each dependency (forbidden, unavailable, stale, etc.)

This aligns with your “audit must be evidence-first and replay-defensible” posture.

### Designer pin (authoritative): **event causality chain**

To make audit/case joins visually and mechanically clean:

* DecisionResponse envelope:

  * `parent_event_id = input_event_id`
* ActionIntent envelope:

  * `parent_event_id = decision_event_id`
* (Later, AL should set ActionOutcome `parent_event_id = intent_event_id` — AL’s side.)

This forms a causality chain without inventing new graph machinery.

### Envelope time semantics (avoid drift)

* **For DF outputs, envelope `ts_utc` is the DF-output event time** (decision issuance / intent issuance time).
* The **input event time** (`basis.event_ts_utc`) remains inside the provenance/basis block; DF must not overwrite it.
  This keeps domain time semantics honest while preserving the input boundary you use for OFP as-of.

### Publish-set ordering (designer pin)

Publish in this order:

1. DecisionResponse
2. ActionIntents (canonical sorted order)

Rationale: ensures the decision fact exists before intents appear, improving audit/case coherence (even though AL can execute without it).

### Drift bans

* **Not allowed:** DF-G omits required provenance and still marks the DecisionResponse “normal.” DLA will quarantine half-truths; we must not rely on downstream to guess. 
* **Not allowed:** publishing intents without a decision pointer.

---

# I-J8 — DF-H → DF-A

## Receipts/Completion → Intake checkpointing (the “done-ness” join)

### Purpose

Define exactly **when DF may advance the EB consumer checkpoint** for the input event (i.e., treat the WorkItem as complete), without risking lost decisions or duplicated side effects.

This join is the internal bridge between:

* at-least-once input delivery (EB) and
* idempotent output admission (IG dedupe + receipts).

### What crosses the join: `CompletionRecord`

A structured summary of:

* `input_event_ref` (stream/partition/offset) + `input_event_id`
* `publish_attempts[]` (for observability)
* `receipt_set[]` (one per published output event_id), each receipt being:

  * ADMIT / DUPLICATE / QUARANTINE + evidence pointer (EB coords or quarantine ref) + reason codes
* `completion_outcome` (defined below)

### Designer pin (authoritative): **terminal receipt semantics**

For DF purposes, **ADMIT**, **DUPLICATE**, and **QUARANTINE** are all **terminal** outcomes for an output event.

* ADMIT/DUPLICATE = “output fact exists (or already existed)”
* QUARANTINE = “output could not be admitted; remediation is external”

We do **not** block the entire input stream forever on quarantined outputs; that would deadlock production. Quarantine is first-class and must be visible, not retried forever.

### Completion outcomes (what DF-A is allowed to do next)

DF-A may only advance the input checkpoint when one of these is true:

1. **`COMPLETE_NOOP`**
   Input was NON_TRIGGER / IGNORE → no publish required.

2. **`COMPLETE_OK`**
   Every event in `required_set[]` has a terminal receipt and every such receipt is ADMIT or DUPLICATE.

3. **`COMPLETE_WITH_QUARANTINE`**
   Every event in `required_set[]` has a terminal receipt, but one or more are QUARANTINE.
   → DF advances checkpoint **and** emits a high-severity signal/metric (this is an operational incident / policy mismatch / bad provenance story).

**Not allowed:** “attempted publish” without receipts is never completion.

### What is `required_set[]`? (designer pin)

* For **TRIGGER** inputs: **DecisionResponse is always required.**
  DF is system-of-record for the decision fact; even safe fallback decisions are decisions.
* ActionIntents are required **only if produced** (i.e., if `publish_set` contains them).
  If DF decided “no action,” there’s nothing to require.

### The crash/replay correctness story (why this is in-bounds)

* If DF crashes **before** checkpoint advances, EB will redeliver input → DF reprocesses → emits same output event_ids → IG returns DUPLICATE receipts → completion occurs.
* If DF crashes **after** checkpoint advances, the input won’t be redelivered, but that’s safe because required outputs already have terminal receipts.

This is exactly how we reconcile at-least-once inputs with idempotent outputs without adding a big DF state store.

### Drift bans

* **Banned:** advancing the input checkpoint after only publishing the DecisionResponse but before confirming all produced ActionIntents have terminal receipts (that can silently lose side effects).
* **Banned:** generating new IDs on retry (breaks dedupe, creates multiple facts).
* **Banned:** treating “timeout talking to IG” as QUARANTINE. QUARANTINE is an IG decision with evidence; transient publish failure is “not complete yet.”

---

## Quick “no drift” summary for I-J5 → I-J8

If we preserve just these truths, DF internals can evolve without violating the platform boundary:

* I-J5 produces deterministic intent candidates and outcomes (no nondeterminism).
* I-J6 stamps stable **event_id** + **idempotency_key** with canonical ordering.
* I-J7 packages canonical envelope events with full provenance and a clean causality chain.
* I-J8 gates input completion strictly on terminal IG receipts for required outputs.

---

Yes. **I-J9 → I-J12** are the “cross-cutting rails joins” where DF becomes **production-shaped** without changing DF’s meaning. The key design boundary here is:

> **DF-X may change *pacing, caching, budgets, and visibility* — but may not change *decision semantics*.**
> Any semantic change must come from **DL (mask)** or **Registry (bundle)**, and must be recorded.

Below I’ll illuminate each join as a real production handshake between opaque boxes.

---

# I-J9 — DF-X ↔ DF-A

## Observability + Backpressure ↔ Intake

### Purpose

Keep DF stable under real load (lag, bursts, dependency outages) **without dropping or reinterpreting facts**, and support **drain/pause** operations.

### What crosses the join

**DF-A → DF-X (telemetry stream):**

* intake rate, in-flight work count, internal queue depth
* EB consumer lag / “age since `ts_utc`” distribution
* failure counts by class (invalid envelope, non-trigger, constrained/safe fallback, etc.)
* checkpoint progress stats (how often completions occur; how many work items waiting on receipts)

**DF-X → DF-A (IntakeControl directives):**

* `pause | resume` (explicit operational state)
* `max_inflight` / `target_rate` (throttle)
* `drain_mode` (stop fetching new work; finish/flush in-flight)
* `reason_codes` + `control_snapshot_id` (so “why did DF slow down?” is explainable)

### Hard invariants

1. **Backpressure can only affect *when* DF processes, not *what* DF decides.**
   DF-X must not change trigger allowlists, rewrite pins, or alter decision boundaries.

2. **No silent loss.**
   “Pause/drain” must never imply dropping EB events. It only controls read rate and in-flight concurrency.

3. **Checkpointing remains gated by I-J8 completion.**
   DF-X may slow intake if publish/receipts stall, but it cannot authorize early checkpoint advance (that would drift from the “receipts are terminal evidence” posture).

### Explicit edge states (production-real)

* **Publish stall** (IG unreachable / receipts delayed) → DF-X throttles or pauses DF-A to prevent memory blow-up, while preserving correctness.
* **Drain requested** (Run/Operate) → DF-X instructs DF-A to stop acquiring new items and finish in-flight deterministically.

### Drift bans

* **Banned:** “adaptive semantics” (e.g., DF-X quietly changes decision thresholds). That belongs only to DL/Registry.
* **Banned:** DF-X forces DF-A to “skip” events to catch up (breaks replay truth).

---

# I-J10 — DF-X ↔ DF-C

## Policy Snapshotting / Cache / Lifecycle ↔ Constraints & Bundle Selection

### Purpose

Let DF-C build a **per-WorkItem immutable DecisionPlan** using **explicit snapshots** of:

* DL posture (mask)
* Registry active bundle resolution
* DF policy revisions (trigger map / compatibility policy / fail-safe policy)

…while allowing production optimizations (cache, subscriptions) that do **not** create nondeterministic plan changes mid-flight.

### What crosses the join

**DF-X → DF-C (PolicySnapshot):**

* `dl_snapshot` = {mode, capabilities_mask, decided_at, snapshot_id, age}
* `registry_snapshot` = {active_bundle_ref, lifecycle_event_id(optional), snapshot_id, age}
* `policy_revisions` = {df_trigger_policy_rev, compat_policy_rev, fail_safe_policy_rev, …}
* `freshness_flags` = {dl_is_stale?, registry_is_stale?} (policy-profiled thresholds)

**DF-C → DF-X (PlanUsageRecord):**

* “for WorkItem X, I used dl_snapshot_id A and bundle_ref B”
* plus compatibility outcome (OK / incompatible → safe fallback)

### Hard invariants

1. **Per-WorkItem immutability:** once DF-C emits a DecisionPlan, it is frozen for that WorkItem. Registry/DL updates affect only *future* WorkItems.

2. **Deterministic resolution:** registry selection is deterministic (no “latest”), and DF must record the bundle reference used.

3. **Fail-closed posture on uncertainty:** if DL/Registry snapshots are missing/expired, DF-C must produce a plan that forces safe behavior and records the failure mode.

### Explicit edge states

* DL unreachable → DF-X may provide “last known” snapshot **with age**; DF-C policy decides whether it is usable; otherwise fail-closed.
* Registry unreachable / incompatible bundle → DF-C produces safe fallback plan and stamps explicit reason (so DLA/cases can see it later).

### Drift bans

* **Banned:** DF-X “helpfully” swaps bundles inside a WorkItem because a new activation happened mid-processing.
* **Banned:** DF-C uses unstamped “current posture” without snapshot identity (kills auditability).

---

# I-J11 — DF-X ↔ DF-D

## Dependency Governance ↔ Context Acquisition

### Purpose

Make dependency interaction production-safe and auditable:

* enforce budgets (timeouts/retries/circuits/rate limits)
* enforce **mask-based permissioning** (what DF is allowed to call/request)
* ensure DF-D returns **explicit provenance or explicit non-use reasons** (never silent gaps)

### What crosses the join

**DF-X → DF-D (CallPolicy):**

* timeout budgets per dependency (OFP/IEG)
* retry budget + backoff class (bounded)
* circuit state (open/half-open/closed)
* concurrency limit / rate limit
* allowed feature groups list (from degrade mask & bundle requirements)
* staleness tolerances (policy-profiled)
* required provenance fields (snapshot hash, basis tokens, etc.)

**DF-D → DF-X (CallOutcome telemetry + provenance):**

* success/failure stats by dependency
* explicit outcome classification: USED / FORBIDDEN / UNAVAILABLE / STALE / NOT_FOUND / BASIS_VIOLATION
* captured provenance tokens when USED:

  * OFP: `feature_snapshot_hash`, `input_basis`, versions, freshness, as-of time
  * IEG: `graph_version`

### Hard invariants

1. **As-of is explicit and must match the DecisionBoundary:** DF-D must never call OFP with hidden “now.”

2. **Mask is law:** if degrade forbids IEG or a feature group, DF-D must behave as if it doesn’t exist and must return `FORBIDDEN_BY_MASK` (not “unavailable”).

3. **Provenance is mandatory when context is used:** DF-D cannot return context without the basis tokens that make it replay/explainable (`input_basis`, `graph_version`).

### Explicit edge states

* OFP partially available → DF-D returns per-group results + per-group freshness; DF-E later decides how to proceed, but DF-D must be explicit.
* IEG lagging behind EB → still valid if `graph_version` makes the basis explicit; DF must not pretend it used “current truth.”

### Drift bans

* **Banned:** DF-X/DF-D silently substituting cached features/identity without provenance (that becomes hidden truth).
* **Banned:** DF-D “helpfully” widening its request beyond allowed feature groups.

---

# I-J12 — DF-X ↔ DF-H

## Publish Governance ↔ Publish + Receipts

### Purpose

Ensure DF outputs become platform facts **only via IG admission semantics**, and keep publish behavior stable under outages, retries, and drain operations.

### What crosses the join

**DF-X → DF-H (PublishPolicy):**

* publish ordering rule (DecisionResponse before Intents)
* batching limits (max events per publish set)
* retry budgets + timeouts + circuit posture toward IG
* receipt wait policy (how long to wait before “not complete”)
* drain/pause controls (coordinate with I-J9)
* required telemetry fields / correlation propagation

**DF-H → DF-X (PublishLedger signals):**

* publish attempts (count, latency, failure class)
* per-event receipt outcomes: ADMIT / DUPLICATE / QUARANTINE + evidence pointers
* “blocked work items” count (waiting on receipts)
* high-severity incidents: quarantine spikes, repeated publish failures

### Hard invariants

1. **IG outcomes are the only terminal receipts:** ADMIT/DUPLICATE/QUARANTINE are explicit, evidence-bearing outcomes. “Timeout talking to IG” is not a receipt and must not be treated as completion.

2. **Publish governance must respect I-J8 completion semantics:** DF-H cannot tell DF-A to checkpoint without terminal receipts for the required set.

3. **Receipt recording is part of DF’s operability:** DF-X must ensure quarantine and duplicate outcomes are visible (metrics/logs) because they drive P4 remediation and L2 degrade posture.

### Explicit edge states

* **IG outage / publish failures** → DF-X reduces intake (I-J9), DF-H retries within budget; beyond budget the WorkItem remains “not complete yet,” not silently skipped.
* **Quarantine on DF output** → DF completes with `COMPLETE_WITH_QUARANTINE` (per our earlier pin), and DF-X raises incident signals; remediation is external (policy/fix), not internal bypass.

### Drift bans

* **Banned:** DF-H re-minting new event_ids on retry (breaks dedupe; creates multiple truths).
* **Banned:** bypassing IG semantics (direct bus publish that doesn’t replicate admit/duplicate/quarantine discipline).

---

## One last “DF-X is not a shadow brain” pin

Across I-J9…I-J12, DF-X may:

* **throttle, pause, drain**
* **cache and snapshot policy inputs**
* **govern timeouts/retries/circuits**
* **enforce provenance completeness at boundaries**

DF-X may **not**:

* change decision logic,
* override degrade mask,
* override registry bundle selection,
* rewrite input facts or output facts.

That keeps DF internal evolution safely inside the pinned platform network.

---

Got it. We’ll illuminate **I-P1 → I-P4** as **production internal paths** across the opaque L1 subnetworks (DF-A…DF-H, DF-X), focusing on **what must be true at each boundary** and **what makes each path distinct**—without opening any subnetwork internals yet.

I’ll start with the **path selector** (how DF chooses which path it is on), then expand each path.

---

# Path selector (how DF lands on I-P1 vs I-P2 vs I-P3 vs I-P4)

Think of the selector as two gates:

### Gate 1 — “Is this a decision trigger?”

* If **NON_TRIGGER / IGNORE** → **I-P2**
* If **TRIGGER** → go to Gate 2

### Gate 2 — “Can/should DF use context for this trigger?”

DF-C (Constraints+Bundle) emits a **DecisionPlan** that fully determines what’s allowed/required.

* If the plan says **FORCE_SAFE / CONSTRAINTS_ONLY** (because of degrade mask, missing prerequisites, registry incompatibility, or policy) → **I-P3**
* Otherwise DF-D attempts to acquire context:

  * If context acquired **fully enough** per plan → **I-P1**
  * If context acquired **partially** (allowed but missing/limited/stale) and plan allows degraded execution → **I-P4**
  * If context is **none** and plan still allows a safe decision → **I-P3**

That’s the clean, no-drift rule: **path selection is determined by (trigger classification) + (DecisionPlan) + (ContextSnapshot results)**. Nothing else.

---

# I-P1 — Normal authoritative decision path (EB-driven, full context allowed/available)

**Spine:**
`DF-A → DF-B → DF-C → DF-D → DF-E → DF-F → DF-G → DF-H → I-J8 complete`

## When this path applies

* Input is **TRIGGER**
* DecisionPlan allows needed capabilities (IEG/OFP, feature groups, etc.)
* OFP/IEG are available enough and return provenance tokens
* No policy forces an immediate safe fallback

## Step-by-step (opaque modules, explicit handshakes)

### 1) DF-A Intake produces `WorkItem`

* Validated canonical envelope + extracted pins + EB replay coords
* Trigger classification = TRIGGER
* Carries `event_ref` (stream/partition/offset)

### 2) DF-B Boundary produces `DecisionBoundary`

* `event_time_utc := envelope.ts_utc` (domain time)
* `basis_ref := input event_id + event_ref`
* deterministic `decision_scope`
* `basis_fence` (no-peek hint derived from the input’s partition/offset)

### 3) DF-C Constraints+Bundle produces immutable `DecisionPlan`

* DL posture snapshot (mode + mask + identity)
* Registry ActiveBundleRef (deterministic)
* Compatibility outcome (OK)
* Context contract: which sources/groups are required vs optional vs forbidden

### 4) DF-D Context Acquisition produces `ContextSnapshot`

* OFP called with `as_of_time_utc = event_time_utc`
* IEG consulted if allowed
* Returns:

  * OFP: `feature_snapshot_hash`, group versions, freshness flags, `input_basis`
  * IEG: `graph_version`
* Returns explicit “used/not used” reasons (even if everything is used)

### 5) DF-E Decision Execution produces `DecisionDraft`

* Uses **only** Boundary + Plan + Snapshot
* Produces deterministic `decision_outcome` + `intent_candidates[]`

### 6) DF-F Intent+Identity produces `DecisionOutputs`

* Applies mask as a final backstop (drops forbidden intents)
* Assigns stable:

  * DecisionResponse `event_id`
  * ActionIntent `event_id`
  * ActionIntent `idempotency_key`
* Canonical ordering for intents

### 7) DF-G Provenance Pack produces `DecisionPackage`

* Builds canonical envelope events
* Attaches provenance block (basis + degrade + bundle + snapshot tokens + “not used” reasons)
* Publish set ordering: decision first, then intents

### 8) DF-H Publish emits to IG and collects receipts

* For each output event, DF-H must obtain terminal receipt: ADMIT/DUPLICATE/QUARANTINE

### 9) I-J8 Completion gating

* Completion occurs only after **terminal receipts** exist for the required set
* Outcomes:

  * `COMPLETE_OK` (ADMIT/DUPLICATE for all required outputs)
  * or `COMPLETE_WITH_QUARANTINE` (still terminal, but incident-worthy)

**Production hallmark of I-P1:** it leaves behind a complete “audit-joinable triangle”:

* input basis pointer,
* decision+intent facts on EB,
* provenance tokens (bundle + degrade + snapshot basis).

---

# I-P2 — Non-trigger path (DF sees events it must not decision on)

**Spine:**
`DF-A → (classify NON_TRIGGER/IGNORE) → DF-X metrics → complete/commit with no outputs`

## When this path applies

* Event type is not allowlisted for decisioning
* Or it is explicitly blacklisted (e.g., DF’s own outputs, AL outcomes, DLA pointers)
* Or it is a control-plane event DF should never decide on

## What happens

### 1) DF-A Intake still validates and frames

* Creates a WorkItem but sets classification = NON_TRIGGER/IGNORE with reason code

### 2) DF-X records visibility (no silent skips)

* Metrics: “skipped by policy”, counts by event_type, lag stats
* Optional trace span so you can debug “why wasn’t this decided?”

### 3) Completion is immediate (no publish required)

* DF advances the input checkpoint because the “work” was to observe and intentionally do nothing.
* **No DecisionResponse, no ActionIntents.**

**Production hallmark of I-P2:** it prevents accidental feedback loops and keeps DF’s work domain tight, while still being observable.

---

# I-P3 — Constraints-only safe fallback path (no context used)

**Spine (conceptual):**
`DF-A → DF-B → DF-C → (skip DF-D heavy context) → (minimal decision compute) → DF-F → DF-G → DF-H → I-J8 complete`

## When this path applies

* Degrade mask forbids OFP/IEG (hard constraint), **or**
* Registry/DL are unavailable beyond policy tolerance, **or**
* Active bundle incompatible with current capability mask / feature contract, **or**
* Policy for this decision_scope says: “If required context missing, do SAFE_FALLBACK immediately.”

## The key design declaration (authoritative)

**In I-P3, the “decision outcome” is forced by the DecisionPlan.**
Meaning: DF-C emits a plan that explicitly specifies:

* `decision_mode = SAFE_FALLBACK` (or equivalent)
* allowed safe intents template(s) (e.g., “route to review”, “step-up”, “hold”)
* required provenance fields for a constrained decision

This keeps us consistent with our earlier boundary: DF-F does not “invent” a decision; it externalizes a decision that is *already chosen by the plan under constraints*.

## Step-by-step highlights

### DF-C produces a forced-plan snapshot

* Records exactly why: `FORBIDDEN_BY_MASK`, `DL_UNAVAILABLE_FAIL_CLOSED`, `REGISTRY_UNAVAILABLE`, `INCOMPATIBLE_BUNDLE`, etc.

### DF-D is not invoked for live context

* DF still produces an explicit “context not used” block with reasons (for audit honesty).

### DF-E heavy compute may be skipped

* The “decision compute” is essentially: choose the forced safe outcome + safe intents defined by policy for this scope.

### Downstream behaves like normal

* DF-F stamps stable IDs/keys
* DF-G packages provenance explicitly saying this was constraints-only
* DF-H publishes and I-J8 gates completion on receipts

**Production hallmark of I-P3:** DF remains operational and safe even when the world is partially unavailable—without silently degrading and without inventing context.

---

# I-P4 — Context-limited path (partial context; degraded-but-not-forced)

**Spine:**
`DF-A → DF-B → DF-C → DF-D (partial) → DF-E (degraded exec) → DF-F → DF-G → DF-H → I-J8 complete`

## When this path applies

* Trigger is valid
* Plan allows some context usage
* But DF-D returns partial context because:

  * some feature groups missing/stale
  * IEG forbidden/unavailable/lagging
  * basis-fence violation detected
  * OFP available but constrained by mask (only subset groups allowed)

## Variants (still the same path shape)

### I-P4a — OFP-only (IEG forbidden/unavailable)

* DF-D returns OFP snapshot + explicit “IEG not used” reason

### I-P4b — IEG-only (OFP forbidden/unavailable)

* DF-D returns graph context + explicit “OFP not used” reason

### I-P4c — Partial OFP groups (mixed freshness)

* DF-D returns feature snapshot with per-group availability/freshness flags

### I-P4d — Basis-fence violation

* DF-D rejects context as `BASIS_VIOLATION` and returns explicit reason (so DF-E can’t unknowingly use “future” context)

## Step-by-step highlights

### DF-D returns a **structured partial snapshot**

For every source/group it returns one of:

* USED
* FORBIDDEN_BY_MASK
* UNAVAILABLE
* STALE_BEYOND_TOLERANCE
* NOT_FOUND
* BASIS_VIOLATION

…and when USED, it must include provenance tokens (`feature_snapshot_hash`, `input_basis`, `graph_version`, freshness).

### DF-E executes in “degraded context mode”

* The DecisionPlan defines what is required vs optional:

  * If required context is missing → DF-E must transition to a safe fallback outcome (but still within I-P4 mechanics), and record why.
  * If optional context is missing → proceed with reduced logic.

### DF-G makes the “degradedness” visible

* Provenance explicitly indicates partial context and why
* This is crucial for audit, case review, and offline parity

**Production hallmark of I-P4:** DF can continue producing decisions under constrained context while remaining honest about what it knew.

---

## The “don’t drift” summary across I-P1–I-P4

* **I-P1** = full context, normal decision, full provenance, receipts gate completion
* **I-P2** = no decision by policy, observable skip, checkpoint advances with no publish
* **I-P3** = forced safe outcome by constraints plan, no context, explicit reasons, publish+receipts still required
* **I-P4** = partial context snapshot, degraded execution, explicit provenance of what was missing/forbidden/stale, publish+receipts still required

---

Absolutely — we’ll illuminate **I-P5 → I-P7** as production paths across the opaque DF subnetworks, and I’ll pin the **boundary semantics** that keep them inside the platform network laws (single truth world via IG→EB, explicit provenance, idempotency, quarantine as first-class, no hidden time).

---

# I-P5 — Preview / What-if path (optional, non-authoritative)

**Spine:**
`External preview request → DF-A → DF-B → DF-C → DF-D → DF-E → DF-F → (return to caller)`
**No DF-G/DF-H publish. No IG receipts. No EB facts.**

## When this path applies

* A caller explicitly requests a **preview** / “what would you do?” decision.
* This path is permitted only if it does **not** mint durable decision truth or trigger side effects.

## What makes it safe (designer pins)

### P5-PIN A — Preview never creates platform truth

* **No ActionIntents** that would be consumed by AL.
* **No publish** to IG/EB.
  This preserves the “single truth world” posture: authoritative decisions live on EB as admitted facts, not in API responses.

### P5-PIN B — Preview outputs are explicitly marked

The response must be stamped with a hard label like:

* `is_preview=true`
* `non_authoritative=true`
* includes `preview_reason` and `caller_principal` (attribution).

This prevents “someone screenshotted an API response and treated it as an audit fact.”

### P5-PIN C — Preview uses the same *planning constraints* as production

Even though it’s non-authoritative, preview must still:

* obey the current DL mask (hard constraints),
* resolve bundle via Registry (deterministic),
* use explicit as-of semantics for OFP (based on the supplied event time).

Otherwise preview becomes misleading (“preview did X, prod would not have been allowed to do X”).

### P5-PIN D — Explicit time and basis required

Preview must supply an input event in canonical-envelope form or equivalent:

* must include `ts_utc` (domain time) and pins as applicable, or DF treats it as constrained.

If the caller can’t provide a proper basis, DF may still produce a response — but it must be explicitly marked “basis incomplete / constrained preview.”

## What the response looks like (conceptually)

Preview returns something like:

* decision outcome (what DF would decide)
* “would-intents” list (advisory only; **not** actionable)
* provenance summary (degrade posture id, bundle ref, feature snapshot hash if used)
* explicit “non-authoritative” stamp

## Drift bans

* **Banned:** silently publishing preview decisions onto EB.
* **Banned:** returning ActionIntents with valid idempotency keys that could be mistaken for executable requests.
* **Banned:** using hidden “now” for OFP as-of time.

---

# I-P6 — Publish “duplicate accepted” path (idempotent success under replay)

**Spine:**
`(any of I-P1/I-P3/I-P4) → DF-G → DF-H → IG returns DUPLICATE → I-J8 completion`

## When this path applies

* DF replays the same input (EB redelivery / DF restart), **or**
* DF retries publishing because it didn’t observe receipts, **or**
* multiple instances race to produce the same output (should be rare but possible in failover scenarios)

IG decides an output is a **duplicate** when it sees the same output `event_id` again and can point to the already-admitted fact.

## What must be true for DUPLICATE to be a “success” (designer pins)

### P6-PIN A — Output identities must be stable

DF must re-emit the **same** `event_id` for the same logical DecisionResponse/Intent under replay. This is what makes dedupe possible at IG.

### P6-PIN B — DUPLICATE is terminal

DUPLICATE is a terminal receipt outcome (same as ADMIT, from DF’s completion perspective).
That means DF can safely complete the WorkItem and advance checkpoint once all required outputs have terminal receipts.

### P6-PIN C — DUPLICATE receipts must be linkable

The receipt must point to evidence:

* either the original EB coordinates of the already-admitted event, or another stable fact pointer.

This is important because DLA and operators need to see “this publish was a retry/duplicate, here’s the original fact.”

## Typical production sequences

### Sequence 1 — Clean replay

* DF processes input again
* DF publishes DecisionResponse + Intents
* IG replies DUPLICATE for each
* DF completes (`COMPLETE_OK`) and moves on

### Sequence 2 — Publish uncertainty (receipt lost)

* DF published previously, but crashed before recording receipts
* On restart, DF republishes
* IG replies DUPLICATE (because facts already exist)
* DF completes; no double side effects occur downstream because AL also dedupes by `(ContextPins, idempotency_key)`.

## Drift bans

* **Banned:** generating new event_ids on retry (turns replay into “new facts”).
* **Banned:** treating “no receipt yet” as success; success is ADMIT/DUPLICATE/QUARANTINE receipt, not “we sent it.”

---

# I-P7 — Publish quarantine path (output rejected by IG; still completes with incident posture)

**Spine:**
`(any decision path) → DF-G → DF-H → IG returns QUARANTINE → DF-X signals → I-J8 completion (COMPLETE_WITH_QUARANTINE)`

## When this path applies

IG quarantines DF output because it cannot be admitted under policy / shape / joinability. Common causes:

* envelope invalid or schema_version unsupported
* DF missing required pins for a run-scoped fact
* producer identity mismatch / AuthZ denies event_type
* “policy corridor” rejects (e.g., event_type not allowed for DF principal)

## The critical design decision (authoritative)

### P7-PIN A — QUARANTINE is terminal, and DF must not deadlock

A quarantined output is a **terminal receipt**; DF completes the WorkItem (so the pipeline doesn’t stall indefinitely), but it marks `COMPLETE_WITH_QUARANTINE` and emits high-severity signals.

Why this is in-bounds:

* Quarantine is explicitly first-class at IG.
* Remediation is external (policy/config/fix), not inside DF.

### P7-PIN B — DF must surface quarantine as an operational incident

DF-X must emit:

* metric counters by quarantine reason code
* alert threshold hooks (quarantine spike = likely deployment/policy mismatch)
* optional “quarantine pointer” linkage so operators can inspect evidence.

### P7-PIN C — DF must not try to “fix” quarantined outputs on the fly

No auto-rewriting pins, changing event_type, or stripping fields to sneak past IG.
That would create a second truth world (what DF *wanted* vs what the platform *admitted*).

### P7-PIN D — Quarantine must be explainable by-ref

The IG receipt should point to:

* a quarantine record in object store, and
* reason codes + policy rev.
  DF should capture the receipt as part of completion evidence (so later audits can see: “DF attempted to publish, platform refused, here is why.”)

## How this affects downstream loops

* **Audit (DLA)**: DLA won’t see the missing decision fact on EB, which is precisely why quarantine must produce strong operator visibility and remediation workflows (P4/L3).
* **Action loop (AL)**: if intents were quarantined, AL never executes them — again consistent: the platform didn’t admit them.

## Drift bans

* **Banned:** DF continuing to publish alternate “shadow outputs” elsewhere to compensate.
* **Banned:** DF advancing input checkpoint without recording the quarantine receipt (must be visible + attributable).

---

## Quick comparison (so you can keep the map in your head)

```text
I-P5  Preview:        DF-A..DF-F -> return (no publish, no receipts, explicitly non-authoritative)
I-P6  Duplicate ok:    ... -> DF-H -> IG:DUPLICATE -> complete OK (idempotent replay success)
I-P7  Quarantine:      ... -> DF-H -> IG:QUARANTINE -> complete w/ incident (remediate externally)
```

---

Yes — let’s illuminate **I-L1 → I-L3** as **production loops** inside DF, still treating every subnetwork (DF-A…DF-H, DF-X) as an **opaque box**. I’ll pin the **loop laws** so we don’t drift when we later open the boxes.

---

# I-L1 — Input replay / idempotency loop

**“Same input arrives again” → DF reprocesses safely → outputs dedupe → completion remains correct**

## Where it lives in the internal network

This loop spans the entire main spine and closes through the completion edge:

`DF-A → … → DF-H → (I-J8 receipts) → DF-A checkpointing`

## What triggers I-L1 in production

All of these are “normal”:

* EB at-least-once redelivery (consumer restart, rebalance, transient commit failure)
* DF crash after publish but before checkpoint advance
* Operator-initiated replay (reprocessing a window)
* Upstream duplication (same business fact admitted twice with same `event_id`)

## The loop’s correctness goal

Reprocessing **must not** create:

* extra decision facts,
* extra intents,
* extra side effects,
* or a different “truth world”.

It may create **duplicate publish attempts**, but the platform must collapse them into a single durable set of facts.

## Designer pins (authoritative loop laws)

### L1-PIN A — Output identity must be stable under replay

For the same input event and scope, DF must re-emit the **same**:

* DecisionResponse `event_id`
* ActionIntent `event_id`
* ActionIntent `idempotency_key`

This is what makes IG dedupe and AL effectively-once “click” together.

### L1-PIN B — Receipts gate completion (I-J8 is the loop’s lock)

DF may only treat an input as complete when **terminal receipts** exist for the required output set:

* ADMIT / DUPLICATE / QUARANTINE are terminal outcomes
* “we sent it but didn’t hear back” is **not** terminal

This is what prevents “lost decisions” under crash/restart.

### L1-PIN C — DUPLICATE is a success state, not an error

When IG returns **DUPLICATE**, DF must treat it as “the fact already exists”, complete the WorkItem, and advance the input checkpoint.

### L1-PIN D — Duplicate *mismatch* is a first-class correctness failure

This is the only extra pin I’m adding beyond what we already implied, because it prevents silent drift:

* DF must attach a deterministic `payload_digest` (or equivalent content hash) to each output event it attempts to publish.
* IG, on duplicate detection, must either:

  * confirm the digest matches the already-admitted fact and return DUPLICATE, **or**
  * return a **DUPLICATE_MISMATCH** (treated like quarantine / incident) if the payload differs.

Why I’m pinning this: it’s the cleanest way to guarantee replay doesn’t “try to rewrite history” while still letting DF be mostly stateless.

## The canonical replay story (why this loop is safe)

**Crash window A: DF crashes before receipts / before checkpoint**

* EB redelivers input
* DF recomputes and republishes same output IDs
* IG returns DUPLICATE (or ADMIT if prior publish never landed)
* DF completes via I-J8

**Crash window B: DF crashes after receipts / after checkpoint**

* input won’t be redelivered
* safe because required outputs already have terminal receipts

## Drift bans for I-L1

* DF minting new output IDs on retry (creates multiple truths)
* DF advancing checkpoint without terminal receipts (can lose intents)
* DF treating its own outputs / AL outcomes as triggers by default (creates feedback loops)

---

# I-L2 — Dependency retry / circuit loop (bounded)

**“attempt → failure → retry within budget → (success | safe fallback | constrained decision)”**

## Where it lives

Two places:

* **DF-D**: calls to OFP / IEG (context acquisition)
* **DF-H**: publish calls to IG + receipt acquisition

## What triggers it

* transient network failures / timeouts
* downstream overload (rate limits, circuit opens)
* eventual-consistency lag (IEG behind EB; OFP snapshot not yet materialized)
* policy forbiddance (not retried; treated as terminal “FORBIDDEN_BY_MASK”)

## Designer pins (authoritative loop laws)

### L2-PIN A — Retries are bounded and budgeted

Every dependency interaction has:

* a retry budget (attempt count and/or wall-clock budget)
* a timeout budget
* a circuit state (closed / half-open / open)

When the budget is exhausted, DF must move to an explicit outcome:

* **context path:** proceed without that context or switch to safe fallback (I-P3/I-P4)
* **publish path:** remain “not complete yet” (do not checkpoint) unless IG has given terminal receipts

### L2-PIN B — Retries must not mutate decision semantics silently

Within **a single WorkItem**, DF must follow **commit-and-freeze**:

* DF-D may retry until it obtains a ContextSnapshot that satisfies the plan.
* Once DF-D returns a “committed” ContextSnapshot for this WorkItem, DF must **not** keep retrying to “get a better snapshot”.
* Any transition caused by retry exhaustion must be recorded explicitly:

  * `UNAVAILABLE`, `STALE_BEYOND_TOLERANCE`, `BASIS_VIOLATION`, etc.
  * and whether we fell back to constraints-only.

This prevents “we waited 200ms longer and the decision changed” from becoming a hidden behavior.

### L2-PIN C — As-of time never changes across retries

All OFP calls for a WorkItem must use:

* `as_of_time_utc = DecisionBoundary.event_time_utc`
  Retries never “slide” time forward.

### L2-PIN D — Mask forbiddance is terminal (no retries)

If the DecisionPlan says a capability/group is forbidden:

* DF-D returns `FORBIDDEN_BY_MASK`
* no retry loop is allowed (it’s not an outage, it’s policy)

### L2-PIN E — Publish retries are *resends of the same events*

In DF-H:

* retry = resend the same canonical envelope events with the same event_ids and digests
* never mint new event_ids
* “timeout waiting for receipts” is not success; it simply means “not complete yet”

## Loop termination conditions

**Context termination (DF-D):**

* Success with provenance tokens → proceed (I-P1 / I-P4)
* Budget exhausted → constrained snapshot → safe fallback (I-P3) or degraded exec (I-P4)

**Publish termination (DF-H):**

* All required outputs have terminal receipts → complete (I-J8)
* Quarantine receipts exist → complete with quarantine + incident signals
* No receipts yet → not complete; DF-X throttles intake to prevent runaway backlog

## Drift bans for I-L2

* “eventually decide differently” for the same WorkItem without recording why
* falling back to cached features/identity without provenance tokens
* treating transient publish failure as QUARANTINE (quarantine is an IG decision with evidence)

---

# I-L3 — Plan snapshot loop (resolve → verify → fallback)

**“resolve DL + Registry → compatibility check → (OK | safe fallback | alternate bundle)”**

## Where it lives

Inside **DF-C (Constraints + Bundle Selection)**, using inputs from DF-X’s snapshot/caching rails.

## What triggers it

Every TRIGGER WorkItem: DF must produce exactly **one immutable plan** for that WorkItem, even if:

* DL updates mid-processing
* Registry activates a new bundle mid-processing
* caches refresh mid-processing

## Designer pins (authoritative loop laws)

### L3-PIN A — Exactly one DecisionPlan snapshot per WorkItem

DF-C must emit one plan object that downstream boxes obey.
Updates after plan emission apply only to future WorkItems.

### L3-PIN B — Compatibility is checked *before* context acquisition

The plan must determine:

* what context is permitted/required,
* what feature groups are allowed,
* whether the active bundle is compatible with the degrade mask and feature contract posture.

### L3-PIN C — Fallback is explicit and typed

The plan must end in one of these terminal plan outcomes:

1. **PLAN_OK**

* active bundle accepted
* context contract computed (required vs optional vs forbidden)

2. **PLAN_SAFE_FALLBACK**

* used when DL is unavailable (fail-closed), Registry unavailable, or incompatibility is irreconcilable
* forces I-P3 constraints-only path
* records reason codes + policy revisions

3. **PLAN_ALT_BUNDLE**

* only if Registry provides a deterministic alternate allowed bundle (e.g., rules-only)
* still deterministic; still recorded; still compatibility-checked

### L3-PIN D — Plan identity is stampable

Plan must have a stable identifier for provenance:

* `plan_id = H(dl_snapshot_id, bundle_ref, policy_revision_set, decision_scope)`
  This isn’t a “spec schema”; it’s the conceptual requirement so later we can say “this decision used plan X”.

### L3-PIN E — DL/Registry staleness is policy-owned, not guessed

If DF-X provides “last known” DL posture or bundle cache:

* DF-C must see the **age** and decide (by policy profile) whether it’s usable
* otherwise fail-closed to safe fallback

## Drift bans for I-L3

* mid-flight plan mutation (“oops, DL changed, let’s switch plans halfway through”)
* nondeterministic “choose latest” bundle selection
* hiding policy revision identities (outcome-affecting config must be citeable)

---

## The short “loop triangle” to keep in your head

* **I-L1** guarantees *replay safety* (stable IDs + receipts gate completion).
* **I-L2** guarantees *bounded resilience* (retries don’t create hidden semantic drift).
* **I-L3** guarantees *single-plan determinism* (one immutable plan per WorkItem).

---

Absolutely. Here are **I-L4 → I-L6**, illuminated as **production loops inside DF** (still treating DF-A…DF-H and DF-X as opaque). I’ll pin what’s **in-bounds** vs **drift** so when we open boxes later we don’t accidentally violate the platform rails (IG trust boundary + receipts, EB replay spine, canonical envelope, DLA “no half-truths”).

---

# I-L4 — Provenance completeness loop

**“assemble → verify anchors → (repair from already-frozen inputs | downgrade to constrained decision) → publish”**

## Why this loop exists (production reality)

DLA’s posture is “**append-only audit; quarantine half-truths**.” If DF emits decisions that lack the minimum evidence anchors, you either:

* poison audit (worst), or
* create lots of DLA quarantines (operational failure).

So DF must enforce **audit-grade completeness** *before* publish. 

## Where it lives

Primarily in **DF-G (Provenance Pack)**, but it may force a **controlled back-edge** to earlier opaque boxes (without opening them).

## The loop, as a state machine

### State 1 — Assemble candidate package

Inputs available at this point (already frozen upstream):

* `DecisionBoundary` (from DF-B)
* `DecisionPlan` (from DF-C)
* `ContextSnapshot` (from DF-D)
* `DecisionOutputs` (from DF-F)

DF-G builds a candidate `DecisionPackage` (DecisionResponse + intents + provenance block) ready to become canonical envelope events. 

### State 2 — Check required anchors (completeness gate)

I’m pinning **two tiers** of anchors:

#### Tier-0 “must exist or do not publish”

These must exist or the WorkItem is *not publishable* (treat as bug / wait for replay):

* **Input basis**: `input_event_id` + EB `(stream, partition, offset)` pointer (by-ref)
* **Decision boundary time**: `event_time_utc` = envelope `ts_utc`
* **Context pins**: at least `{manifest_fingerprint}` and (for run-scoped traffic) the full ContextPins set
* **DecisionResponse event identity** (stable `event_id`)

If any Tier-0 is missing, DF cannot produce an honest decision fact. The correct behavior is: **do not publish, do not checkpoint, surface an internal bug signal, rely on replay.** (This keeps the platform truthful.)

#### Tier-1 “must be made explicit (value or explicit non-use reason)”

These must either be present **or** be explicitly “not used” with a reason code:

* **Degrade posture used** (mode + snapshot identity)
* **Bundle used** (ActiveBundleRef) *or* explicit “registry unavailable → fallback bundle”
* **OFP provenance if OFP used**: `feature_snapshot_hash`, `input_basis`, group versions + freshness, `as_of_time_utc`
* **IEG provenance if IEG used**: `graph_version`
* **Dependency non-use reasons** (`FORBIDDEN_BY_MASK`, `UNAVAILABLE`, `STALE_BEYOND_TOLERANCE`, `BASIS_VIOLATION`, etc.)

This tier is what prevents “half-truth” decisions: even when something is missing, DF must say **why** and **under what posture**.

### State 3 — Repair attempt (NO new truth resolution)

If Tier-1 pieces are missing, DF-G is allowed to “repair” only by:

* pulling the missing fields from the already-frozen upstream objects (Boundary/Plan/Snapshot/Outputs), or
* re-deriving deterministic fields (like stable ordering, hashes) from those objects.

**DF-G is NOT allowed** to re-call DL/Registry/OFP/IEG here (that would create a “mid-flight plan mutation” drift and replay divergence). Any re-resolution belongs to a **new WorkItem** / future plan snapshot.

### State 4 — Downgrade to constrained decision (controlled back-edge)

If Tier-1 is still incomplete after repair (e.g., plan says OFP required but OFP snapshot is missing beyond tolerance), DF must **downgrade**:

* It triggers a controlled back-edge:
  `DF-G → (signal to rebuild outputs as SAFE_FALLBACK) → DF-F/DF-E minimal → DF-G reassemble`

This is still consistent with the “opaque boxes” rule: we’re not opening DF-E; we’re just declaring that DF-G can demand a **safe constrained** output variant.

### State 5 — Final package is marked with provenance grade

DF-G stamps a grade:

* `provenance_grade = COMPLETE` (normal)
* `provenance_grade = CONSTRAINED` (safe fallback / partial context)
* (never “complete” when tier-1 is missing)

This gives DLA/cases/offline an honest signal without guessing.

## Drift bans for I-L4

* **Banned:** emitting “normal” DecisionResponse without degrade snapshot identity and bundle ref (or explicit fallback reason).
* **Banned:** DF-G silently filling missing context by re-querying OFP/IEG at publish time.
* **Banned:** “we’ll let DLA quarantine it” as normal operation — DF should converge first. 

---

# I-L5 — Receipt-driven completion loop

**“publish → wait for terminal receipts → then (and only then) advance input checkpoint”**

## Why this loop exists

EB is at-least-once; DF will replay. The only safe way to avoid **lost outputs** or **double side effects** is to make completion depend on **IG’s terminal receipt outcomes** (ADMIT/DUPLICATE/QUARANTINE). 

## Where it lives

This loop spans:

* **DF-H (Publish+Receipts)** and
* **DF-A (Intake checkpointing)**
  connected by **I-J8** (“done-ness join”).

## The loop, as states

### State 1 — WorkItem ready to publish

DF-A has a WorkItem; DF pipeline produced a `DecisionPackage` (from DF-G).

### State 2 — Publish attempt (DF-H)

DF-H submits the `publish_set[]` to IG (decision first, then intents).

### State 3 — Receipt aggregation

For each output event_id in the **required_set[]**, DF-H waits for a **terminal receipt**:

* **ADMIT**: fact appended to EB (receipt includes evidence pointer)
* **DUPLICATE**: fact already exists (receipt points to original evidence)
* **QUARANTINE**: fact refused (receipt points to quarantine evidence) 

**Important pin:** “timeout talking to IG” is *not a receipt*.

### State 4 — Completion decision (I-J8)

DF computes completion outcome:

* `COMPLETE_OK` if every required output has ADMIT or DUPLICATE
* `COMPLETE_WITH_QUARANTINE` if every required output has a terminal receipt, but one or more are QUARANTINE
* otherwise: **NOT COMPLETE**

### State 5 — Input checkpoint advance (DF-A)

Only after completion is terminal does DF-A advance the EB consumer checkpoint for the input event.

## Why this is replay-correct (the crash windows)

* Crash **before** receipts/checkpoint → replay occurs → DF republishes same IDs → IG dedupes → completes safely
* Crash **after** receipts/checkpoint → replay doesn’t happen → safe because outputs are already facts (or quarantined with evidence)

## The operational truth (the “pending work” backlog)

In production, there will be WorkItems stuck in “waiting for receipts.” DF-X (backpressure) must cap in-flight count and optionally drain/pause, but **must not** violate receipt gating.

## Drift bans for I-L5

* **Banned:** checkpointing input after only publishing DecisionResponse but before intents have terminal receipts (can silently lose side effects).
* **Banned:** re-minting event_ids on retry (turns retries into new truths).
* **Banned:** treating transient publish failures as QUARANTINE (quarantine is an IG decision with evidence). 

---

# I-L6 — Control-plane refresh loop

**“refresh snapshots → expose snapshot IDs to planning → affect future WorkItems only”**

## Why this loop exists

DF depends on living control inputs:

* DL posture (mask)
* Registry lifecycle (active bundle)
* dependency health and local circuit states
* policy/profile revisions

These must refresh continuously in production, but **must not mutate in-flight WorkItems** (immutability is required for replay determinism).

## Where it lives

Inside **DF-X** (the cross-cutting rails mesh), feeding DF-C/DF-D/DF-H.

## The loop, broken into sub-loops

### L6-a — DL posture refresh

Two permissible mechanisms:

* **push** (DL publishes posture updates)
* **pull** (DF polls DL)

Outputs of this sub-loop:

* `dl_snapshot_id`
* `mode + capabilities_mask`
* `decided_at` and `age`
* `staleness_flag` (policy-owned)

**Pin:** If posture is stale/unavailable, DF-C must fail-closed when building a plan for new WorkItems.

### L6-b — Registry lifecycle refresh

Mechanisms:

* subscribe to registry events (cache invalidation/warm cache)
* poll for active bundle per scope

Outputs:

* `bundle_ref` + digests + compatibility metadata
* optional `registry_event_id` used to reach that state
* `age` and `staleness_flag`

**Pin:** Events can warm cache; they never replace deterministic resolution. Bundle changes apply **only** to new WorkItems’ plans.

### L6-c — Dependency health sampling & circuit updates

DF-X samples:

* OFP availability / staleness rates
* IEG lag/availability
* IG publish health (timeouts, receipt latency)

Outputs:

* circuit state (open/half-open/closed)
* retry budgets / timeouts
* concurrency limits

**Pin:** These affect *attempt behavior* (whether DF-D tries, how long it waits), but do not “change what’s allowed”—DL mask still rules permissioning.

### L6-d — Policy profile revision refresh

Outcome-affecting policy config must be:

* versioned
* promoted across env ladder
* stamped into DecisionPlan/provenance for new WorkItems

**Pin:** policy revisions do not silently apply mid-flight; DF-C stamps the revision set into the plan snapshot.

## The key immutability rule (the drift killer)

**Control-plane refresh affects only future WorkItems.**
In-flight WorkItems must use the **plan snapshot** created at DF-C time. That’s how replay stays reproducible.

## Drift bans for I-L6

* **Banned:** switching bundles or degrade posture mid-WorkItem because “a new update arrived.”
* **Banned:** using unstamped “current state” without snapshot IDs/ages.
* **Banned:** local dependency health overriding the DL mask (health can make something unavailable, but cannot make a forbidden capability “allowed”).

---

## The “how these loops compose” checkpoint

* **I-L4** ensures the thing DF publishes is **audit-honest** (complete or explicitly constrained).
* **I-L5** ensures DF’s processing is **lossless and replay-safe** (receipts gate completion).
* **I-L6** ensures DF remains **operable** as a service without mutating decision semantics mid-flight.

---

Yes — it’s worth making the **negative topology** explicit: the *things that must not be connected* (non-joins / forbidden edges / forbidden back-edges). This is one of the best drift killers before we go deeper.

Below is the **DF non-join set** (authoritative for this thread unless it contradicts pinned platform law).

---

## A) External non-joins around DF (banned platform edges)

1. **DF ↔ Data Engine**
   DF must **not** read engine surfaces/outputs directly (especially not on the hot path). Engine outputs enter the platform via **SR join surface + IG→EB**; DF consumes admitted events.
   (Engine “truth_products/audit_evidence/ops_telemetry” are explicitly not traffic; only `business_traffic` is eligible to drive the hot path.) 

2. **DF ↔ Scenario Runner (SR)**
   DF must not depend on SR ledgers or `run_facts_view` directly. That’s enforced upstream by IG’s joinability checks; DF’s stimulus is EB admitted events.

3. **DF ↔ Event Bus (EB) as a bypass**
   DF must **not** “write straight to EB” in a way that bypasses IG semantics. DF outputs are producer traffic and must go through the admission discipline (admit/duplicate/quarantine + receipts), even if implemented as a direct publish.

4. **DF ↔ Decision Log/Audit store (DLA) direct writes**
   DF must not write audit records to `dla/audit/...` or mutate audit truth. DLA is the audit writer; DF only emits decision facts/provenance as traffic.

5. **DF ↔ Label Store / Case store direct writes**
   DF must not write labels or cases as truth. DF can emit intents that cause AL/case tooling to act, but labels are append-only assertions written by the Label Store.

6. **DF ↔ “truth” inputs that would leak the closed world**
   DF must not treat engine `truth_products` / `audit_evidence` / `ops_telemetry` as decision-driving inputs. Those are supervision/forensics surfaces, not traffic. 

---

## B) Internal DF non-joins (banned edges between DF subnetworks)

These keep provenance, determinism, and replay safety clean.

### 1) “No external calls” boundaries (hard)

* **DF-E (Decision Execution)** must not call OFP/IEG/DL/Registry (it must consume the frozen Boundary/Plan/Snapshot).
* **DF-F (Intent+Identity)** must not call OFP/IEG/DL/Registry.
* **DF-G (Provenance Pack)** must not call OFP/IEG/DL/Registry.
* **DF-H (Publish)** must not call OFP/IEG/DL/Registry.

This is how we prevent “mid-flight changes” and missing provenance.

### 2) “No early semantics” boundaries (hard)

* **DF-A (Intake)** must not consult DL/Registry/OFP/IEG to decide anything; it only frames the WorkItem and applies trigger allowlists.
* **DF-B (Boundary/Basis)** must not consult DL/Registry/OFP/IEG; it freezes `event_time` and basis.

### 3) “No mid-flight mutation” boundaries (hard)

* **DF-X (rails)** must not mutate an in-flight WorkItem’s plan/scope/IDs. It can throttle/circuit/cache, but it cannot change semantics.
* **DF-C (Constraints+Bundle)** must emit **one immutable DecisionPlan per WorkItem**; DF-X refreshes apply only to future WorkItems.

### 4) “No publish-driven re-decision” (hard)

* **DF-H** must not cause DF-E/DF-F to “re-decide” because publish was slow. Retries are resends of the *same* output IDs, not new decisions.

---

## C) Forbidden loops and forbidden triggers (non-loops)

1. **DF must not decision-trigger on its own outputs by default**
   DF output event_types (DecisionResponse/ActionIntent) are not triggers unless explicitly allowlisted (otherwise you get uncontrolled feedback). This stays consistent with “DF consumes admitted events” without becoming “DF consumes everything.”

2. **DF must not decision-trigger on AL ActionOutcomes by default**
   If you ever want “outcome-driven decisions,” that’s a deliberate policy extension, not an accidental loop.

3. **No mid-flight “replan loop”**
   Within a single WorkItem, DF is forbidden from:

* resolving DL posture twice “because it changed,” or
* resolving a new bundle mid-flight “because a registry event arrived.”
  That would break replay determinism and provenance honesty.

4. **No “DLA quarantine fixes decision” loop**
   DLA quarantining incomplete provenance must not cause DF to silently patch or overwrite a past decision. Corrections are new facts (supersedes chains), not edits.

---

## D) Non-joins about time and provenance (forbidden substitutions)

1. **No hidden “now”**
   DF must not substitute wall-clock time for the decision boundary time. The boundary time is `ts_utc` from the canonical envelope (required), and `emitted_at_utc` is optional but not a replacement.

2. **No invented context**
   DF must not invent missing features/identity/mode. Missing inputs must be recorded explicitly and handled via constrained/safe posture.

3. **No “half-truth” publish**
   DF must not emit a “normal” decision without the minimum provenance anchors (degrade posture used, bundle ref used, and when context is used, snapshot tokens like `feature_snapshot_hash`/`input_basis` and `graph_version`).

---

## E) Environment ladder non-joins (forbidden deployment drift)

1. **No code forks by environment**
   No “if prod do X.” Environments are profiles (wiring + policy strictness), not semantic branches.

2. **Policy config is not an implicit environment state**
   Outcome-affecting policy (IG allowlists, registry rules, DL thresholds, etc.) must be versioned and cited — not “whatever dev happens to have.”

---

## USER: PAUSE FOR REFLECTION

Here’s the **design checkpoint** for the DF vertex (outer network + inner network we’ve sketched), so we carry the same map forward and don’t drift.

## 1) Platform laws we treated as non-negotiable

These are the rails everything else was built around:

* **IG is the sole admission authority**: ADMIT / DUPLICATE / QUARANTINE + receipts + evidence pointers; no “drop on the floor.”  
* **EB is the sole durable fact log**: append + replay tokens (partition/offset); downstream determinism is built on offsets/watermarks. 
* **Canonical Event Envelope is the boundary shape** with required fields `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`; optional pins include `parameter_hash`, `scenario_id`, `run_id`, `seed`. 
* **DL is explicit safety posture** (deterministic + hysteresis + fail-closed): DF must obey mask (hard constraints) and record posture used. 
* **Registry governs deployable decision logic**: deterministic “active bundle” resolution; DF records bundle ref used per decision.
* **Engine output role boundary**: only `business_traffic` influences decisioning directly; truth/audit/telemetry never leak into hot-path input.
* **Environment ladder pin**: local/dev/prod run the *same graph + semantics*; only operational envelope changes via profiles (policy vs wiring config).

## 2) DF as a vertex in the outer network

### DF’s authority (what DF is system-of-record for)

* **DecisionResponse + ActionIntents + DecisionProvenance** (and nothing else).

### DF’s outer adjacency (what it touches)

* **EB → DF** stimulus (admitted, at-least-once, with replay coords).
* **DL → DF** hard constraints mask (fail-closed).
* **Registry → DF** deterministic active bundle resolution.
* **OFP/IEG → DF** conditional context with provenance (`feature_snapshot_hash`+`input_basis`, `graph_version`).
* **DF → IG → EB** decision+intent facts (canonical envelope, receipts). 
* **EB → AL → IG → EB** action execution and immutable outcomes.
* **EB → DLA** append-only flight recorder; DLA quarantines incomplete provenance; supersedes for correction.

### Outer paths & loops we pinned

* **P1 hot spine**: Producer→IG→EB→DF→IG→EB→AL→IG→EB→DLA.
* **P2 run gating**: SR READY + run_facts_view makes run truth enforceable via IG joinability (DF never “chooses world”). 
* **L1 action closure**: EB→DF→Intent→AL→Outcome→EB. 
* **L2 degrade loop**: signals→DL→DF constrained behavior→signals (explicit, recorded). 
* **L3 quarantine remediation**: IG quarantine → governed remediation → re-eval → admit or remain.
* **L4 audit completeness**: DLA append-only; quarantine half-truths; supersedes chains.
* **L5 learning loop**: EB/DLA/Labels→Offline Shadow→Model Factory→Registry→DF.
* **L6 backfill loop**: Run/Operate declares backfill; rebuild derived state; primary truths never mutate.

## 3) DF inner network (L1 modules), still opaque

We decomposed DF into these internal subnetworks (boxes):

* **DF-A Intake & Normalization**
* **DF-B Decision Boundary & Basis Fence**
* **DF-C Constraints & Bundle Selection**
* **DF-D Context Acquisition**
* **DF-E Decision Execution**
* **DF-F Intent Synthesis & Output Identity**
* **DF-G Provenance & Evidence Packaging**
* **DF-H Publish & Receipt Handling**
* **DF-X Cross-cutting Rails** (observability/backpressure/caching/governance budgets)

This cut intentionally mirrors outer joins: DL/Registry “behind DF-C”, OFP/IEG “behind DF-D”, IG “behind DF-H”, EB “behind DF-A”.

## 4) DF internal joins we established (still opaque boxes)

### Main spine joins

* **I-J1** DF-A→DF-B: `WorkItem` = canonical envelope + pins + EB coords + trigger classification.
* **I-J2** DF-B→DF-C: `DecisionBoundary` = event_time (`ts_utc`) + basis ref + deterministic scope + basis fence.
* **I-J3** DF-C→DF-D: `DecisionPlan` snapshot = degrade posture + active bundle ref + allowed/required context contract + policy rev refs.
* **I-J4** DF-D→DF-E: `ContextSnapshot` = (optional) OFP snapshot + provenance + (optional) IEG context + `graph_version` + explicit “not used” reasons.
* **I-J5** DF-E→DF-F: `DecisionDraft` → stable intents and output candidates (no external calls).
* **I-J6** DF-F→DF-G: stable IDs + idempotency anchors + canonical ordering.
* **I-J7** DF-G→DF-H: canonical envelope publish set + provenance block.
* **I-J8** DF-H→DF-A: **receipt-driven completion**: input checkpoint moves only after terminal receipts exist for required outputs. 

### Rails joins

* **I-J9** DF-X↔DF-A: backpressure/drain/pause; *pacing only*, never semantics.
* **I-J10** DF-X↔DF-C: policy snapshotting/caching (DL posture + Registry bundle) with age/revision stamping; plan immutability per WorkItem.
* **I-J11** DF-X↔DF-D: dependency budgets + mask-permissioning; explicit context outcomes + provenance.
* **I-J12** DF-X↔DF-H: publish budgets + receipt health + quarantine/duplicate signals; must preserve I-J8 semantics.

## 5) DF internal paths we pinned (production behaviors)

* **I-P1 Normal authoritative**: A→B→C→D→E→F→G→H→(I-J8 complete)
* **I-P2 Non-trigger**: intake classifies as NON_TRIGGER/IGNORE; observable skip; no outputs.
* **I-P3 Constraints-only safe fallback**: plan forces safe outcome (mask forbids / dependencies missing beyond tolerance); no live context; still publishes DecisionResponse (and safe intents if any).
* **I-P4 Context-limited**: partial OFP/IEG context; degraded execution; explicit provenance of what was missing/forbidden/stale.
* **I-P5 Preview (optional)**: returns non-authoritative preview; **no publish** (no second truth world).
* **I-P6 Duplicate accepted**: IG returns DUPLICATE receipts on replay; treated as success; complete safely. 
* **I-P7 Output quarantined**: IG returns QUARANTINE receipt; DF completes with incident posture; remediation is external.

## 6) DF internal loops we pinned (production stability)

* **I-L1 Input replay loop**: stable IDs + IG dedupe + receipt gating make reprocessing safe.
* **I-L2 Dependency retry/circuit loop**: bounded retries; no “silent semantic drift” for the same WorkItem; as-of time never slides.
* **I-L3 Plan snapshot loop**: resolve DL+Registry → compatibility → single immutable plan per WorkItem.
* **I-L4 Provenance completeness loop**: enforce “no half-truth” before publish; downgrade to constrained decision if required anchors missing.
* **I-L5 Receipt-driven completion loop**: publish → wait for terminal receipts → only then checkpoint. 
* **I-L6 Control-plane refresh loop**: DL/Registry/policy revisions refresh continuously but apply only to future WorkItems (no mid-flight mutation).

## 7) Negative topology we explicitly banned (non-joins)

This was a big drift-prevention step:

* **No DF→Engine direct read** (engine truth/audit/telemetry cannot become hot-path input; only business_traffic via IG→EB).
* **No DF bypass of IG→EB** for authoritative outputs. 
* **No DF direct writes to DLA/Label Store/Case truth** (DF only emits traffic facts). 
* **No external calls from DF-E/F/G/H**; external joins are confined to DF-C (DL/Registry) and DF-D (OFP/IEG), and publish confined to DF-H.
* **No mid-flight plan mutation** (DL/Registry refresh affects future WorkItems only).
* **No hidden “now” substitution for `ts_utc`**. 

## 8) Deployment + environment ladder takeaways for DF

* DF is a **hot-path always-on service**; “mostly stateless,” but must persist provenance in emitted events; local/dev/prod differ via **profiles**, not code forks.
* We separated **policy config** (outcome-affecting; versioned + auditable) from **wiring config** (endpoints/resources). 
* CI/CD “golden flow” sanity: SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA (plus at least one label + offline + registry resolve) is the minimum integration proof.

## 9) “Designer adds” we introduced (beyond the docs)

These were the extra pins we declared where the authoritative docs leave degrees of freedom:

* **Basis fence / no-peek rule** (avoid “future knowledge” from OFP/IEG relative to the input’s partition position).
* **Action intent identity anchored by (domain, action_key)** to prevent conflicting duplicates while still allowing multiple intents per domain.
* **Receipt-driven completion as the only valid definition of “done”** inside DF.
* **Provenance tiers**: publish only if Tier-0 anchors exist; Tier-1 must be present or explicitly “not used” with reasons.

(These are the key internal drift killers when we go deeper.)

---

### The mental picture we should keep as we open boxes next

DF is a **plan-and-snapshot constrained pipeline**:
**WorkItem → DecisionBoundary → DecisionPlan → ContextSnapshot → DecisionDraft → Stable Outputs → Provenance Package → IG Receipts → Completion.**

If we preserve that chain, we can illuminate DF-C/DF-D/DF-H internally without accidentally breaking the outer network or the environment ladder.

---

Cool — before we open DF’s opaque boxes any further, here are the **deployment + environment-ladder pins** I want “locked” as designer. This is **not** an implementation spec; it’s the minimum set of **production-shaping constraints** so Codex can build DF without accidentally drifting the platform semantics.

---

## 1) Deployable-unit stance for DF v0

### Pin D-1: DF is **one deployable service**, not N microservices

All L1 subnetworks (DF-A…DF-H + DF-X) run **in-process** within the same deployment unit.
Reason: your correctness hinges on **per-WorkItem plan immutability + receipt-gated completion**; splitting boxes into separate services makes that far harder and adds drift surfaces.

### Pin D-2: External I/O surfaces are exactly these

DF’s deployment exposes/consumes only:

* **Consume:** EB (traffic topic)
* **Call out (sync):** DL, Registry, OFP, IEG
* **Publish (sync/async):** IG (or a publish path that is semantically IG-equivalent)
* **Optional:** Preview API endpoint (strictly non-authoritative)

No other sinks/sources (no direct DLA writes, no direct Label Store writes, no engine reads).

---

## 2) Concurrency + ordering stance (this is the biggest deployment pin)

### Pin D-3: **Partition-serial processing** within DF, parallel across partitions

DF must not process offset `o+1` for the same partition until `o` is **complete** under I-J8 (terminal receipts for required outputs).
Parallelism comes from **multiple partitions** (and multiple DF instances in the same consumer group), not from out-of-order intra-partition work.

Why: it keeps the “basis fence / no-peek” story honest and keeps checkpointing simple and correct.

### Pin D-4: Backpressure is a first-class deployment behavior

When publish/receipts stall (IG slow/unreachable), DF must **throttle/pause intake** rather than accumulating unbounded in-flight work. (This is DF-X ↔ DF-A in production form.)

---

## 3) State posture (what DF is allowed to persist)

### Pin D-5: DF is “mostly stateless” — **no mandatory decision DB**

DF correctness must not depend on a persistent “decisions store.”
Replay safety is achieved by:

* stable output IDs + idempotency keys, and
* IG receipts + dedupe,
* AL effectively-once,
* I-J8 receipt-gated completion.

### Pin D-6: Caches are allowed, but must be **snapshot-stamped**

Caches for DL posture and Registry resolution are allowed as performance optimizations, but DF-C must always stamp:

* snapshot identity + age
* policy revision ids used
  …and must freeze that into the per-WorkItem DecisionPlan (no mid-flight mutation).

---

## 4) Profile model for the environment ladder

### Pin D-7: Split profiles into two classes

* **Wiring profile (non-semantic):** endpoints, timeouts, pool sizes, batch sizes, cache sizes, tracing export, etc.
* **Policy profile (semantic / outcome-affecting):** trigger allowlists, fail-safe posture, staleness tolerances, DL corridor thresholds, Registry compat rules, publish/receipt budgets that change “what gets emitted,” etc.

Policy profile revisions must be treated as governed artifacts and must be stampable into provenance/telemetry.

### Pin D-8: Environments differ only by profile values, not code forks

No `if prod:` semantics. Local/dev/prod run the same DF graph, just with different profile strictness.

---

## 5) What changes (legitimately) across Local / Dev / Prod

### Local

* Single instance, small resources, low retention assumptions
* Permissive knobs for convenience **but** the same semantics:

  * still uses canonical envelope
  * still uses receipt gating (even if IG/EB are local stubs)
  * still stamps snapshots/plan IDs
* Preview mode is most useful here.

### Dev (“real enough”)

* AuthN/AuthZ and schema policies close to prod
* More verbose observability + easier quarantine inspection
* Smaller scale than prod, but *same* failure modes exercised (timeouts, retries, degraded paths)

### Prod

* Strict policy revisions + approval gates
* HA posture, longer retention/archive, SLO corridor monitoring feeding DL
* Quarantine spikes treated as incidents, not “expected noise”

---

## 6) Deployment-time health + ops controls (without changing semantics)

### Pin D-9: DF must support **pause/drain**

* **Pause:** stop consuming new events (or hold them) without losing state
* **Drain:** stop fetching new work, finish in-flight to I-J8 completion

### Pin D-10: Readiness is “can make progress,” not “all deps perfect”

DF should be considered runnable even if OFP/IEG are unhealthy, because DL fail-closed + safe fallback exist.
But if **IG publish/receipts are down**, DF cannot progress safely, so readiness should reflect that (or DF should auto-pause consumption).

---

## 7) Observability pins Codex must not miss

### Pin D-11: Correlation keys are required everywhere

Every WorkItem and every publish attempt must carry:

* input `event_id` + `(partition, offset)`
* `decision_event_id`
* intent `event_id` + `idempotency_key`
* trace fields (trace_id/span_id) propagated from input where present

### Pin D-12: Golden metrics (minimum)

* EB consumer lag (by partition) + in-flight count
* publish latency + receipt latency
* counts of ADMIT/DUPLICATE/QUARANTINE on DF outputs (by reason code)
* path selection rates: I-P1/I-P2/I-P3/I-P4
* constrained/safe-fallback rate + dependency failure rates (OFP/IEG/DL/Registry)

These are what make the degrade loop (DL) and quarantine remediation loop operable.

---

## 8) Promotion sanity (the one integration check to keep you honest)

### Pin D-13: The “golden end-to-end” must run in every env (scaled down locally)

At minimum:
EB stimulus → DF (I-P1 + I-P3 exercised) → IG receipts → EB outputs → AL outcome → DLA ingest
…and at least one case/label path + one registry bundle change in dev/prod.

If that flow works identically (semantics-wise) across the ladder, you won’t drift when you open DF’s internals.

---

## 9) Quick deployment drift bans

* No direct EB publish that bypasses IG semantics
* No mid-flight plan mutation due to cache refresh
* No intra-partition out-of-order processing
* No “complete” without terminal receipts for required outputs
* No environment-specific code behavior

---

Yep — at this point, **illumination should only reveal internals that satisfy the already-pinned joins/paths/loops**. If we hit a “node requires something different,” that’s a signal we missed a constraint earlier, not that the network is changing.

## Nodes (DF internal subnetworks)

* **DF-A** Intake & Normalization
* **DF-B** Decision Boundary & Basis Fence
* **DF-C** Constraints & Bundle Selection
* **DF-D** Context Acquisition
* **DF-E** Decision Execution
* **DF-F** Intent Synthesis & Output Identity
* **DF-G** Provenance & Evidence Packaging
* **DF-H** Publish & Receipt Handling
* **DF-X** Cross-cutting Rails (backpressure, caching/snapshots, budgets, observability)

## Illumination order I recommend (highest constraint first)

1. **DF-H Publish & Receipt Handling**
   Because it defines “done-ness” (I-J8), idempotent publish semantics, and backpressure coupling.
2. **DF-C Constraints & Bundle Selection**
   Because it freezes the DecisionPlan snapshot (DL mask + Registry bundle + compatibility + policy rev stamping).
3. **DF-B Decision Boundary & Basis Fence**
   Because it pins event_time/as-of and the replay/basis fence that everything downstream must respect.
4. **DF-F Intent Synthesis & Output Identity**
   Because stable IDs + idempotency keys are the backbone of replay safety and action correctness.
5. **DF-G Provenance & Evidence Packaging**
   Because it enforces “no half-truth” before publish and defines the audit-grade minimum set.
6. **DF-D Context Acquisition**
   Because it must implement the as-of + provenance rules and basis-violation handling under budgets.
7. **DF-A Intake & Normalization**
   Because it’s mostly boundary hygiene + trigger classification, once the downstream requirements are fixed.
8. **DF-E Decision Execution**
   Because it’s the most “logic heavy” and should be constrained by all the earlier pins, not the other way around.
9. **DF-X Rails (as its own focused pass)**
   We’ll weave DF-X into each node as needed, then do one final pass to ensure caching/budgets/observability don’t change semantics.

If you want, we can start immediately with **DF-H** and keep it to one level deep: internal sub-nodes + their internal joins/loops (still opaque), the same way we did for DF as a whole.

---

Alright — **DF-H (Publish & Receipt Handling)** is the *mechanical heart* of “facts become facts” and “done-ness is real.” We’ll expose its machinery as an **internal network of sub-nodes** (still opaque), plus the **joins/paths/loops** inside DF-H.

I’m going to pin a v0 stance up front, because DF-H gets messy if we leave it ambiguous:

### DF-H v0 stance (designer-authoritative)

**DF-H must obtain IG receipts (ADMIT/DUPLICATE/QUARANTINE) for every published output event as part of the publish flow**, because `event_id` is the stable idempotency/dedupe key at ingest/bus boundaries. 
IG is authoritative for **exactly one of ADMIT/DUPLICATE/QUARANTINE with a receipt/evidence trail**. 

How DF-H “talks to IG” (HTTP vs “producer traffic input”) is implementer choice, but **semantically** DF-H must be able to: `submit(event|batch) -> receipts(event|batch)`. 

---

## 1) DF-H boundaries

### Inputs to DF-H

From **DF-G**, DF-H receives a `DecisionPackage` containing:

* `publish_set[]`: canonical-envelope events to submit
* `required_set[]`: which of those must reach a *terminal* receipt before the input WorkItem is complete
* correlation hooks: input basis ref, decision_event_id, intent ids/keys, etc.

The canonical envelope requires `event_id,event_type,ts_utc,manifest_fingerprint` and forbids extra top-level fields (payload must live under `payload`). 

### Outputs from DF-H

To **I-J8 (DF-A completion)**:

* `ReceiptBundle`: per output `event_id` → receipt outcome + evidence pointer
* `CompletionRecord`: `COMPLETE_OK | COMPLETE_WITH_QUARANTINE | NOT_COMPLETE`

To **DF-X (rails)**:

* publish health signals (latency, retries, receipt lag)
* quarantine spikes by reason code
* blocked-work counts (waiting on receipts)

---

## 2) DF-H internal subnetworks (sub-nodes inside DF-H)

Think of DF-H as a small publish engine with a strict state machine:

### H1 — Publish Session Coordinator

**Role:** Own the per-WorkItem publish lifecycle.

* accepts `DecisionPackage`
* holds a “session state” until required receipts are terminal

### H2 — Publish Plan Normalizer

**Role:** Make the publish set deterministic and safe:

* enforce **ordering**: DecisionResponse first, then ActionIntents (canonical sorted order)
* validate **stable identities exist** (`event_id` present; optional digests present)
* decide which events share a `partition_key` hint (see pin below)

### H3 — IG Transport Adapter

**Role:** “Submit events and obtain receipts.”

* supports `submit_batch(events)` → `receipt_batch`
* implements timeouts/retries/circuit posture (but does not change semantics)

(Implementation detail can be HTTP ingress, or “producer traffic input” + synchronous receipt lookup; DF-H only cares that it gets receipts.) 

### H4 — Receipt Correlator & Verifier

**Role:** Turn IG responses into trustworthy receipt facts:

* correlate receipts back to submitted `event_id`s
* verify receipt completeness (every submitted event has a receipt outcome OR is explicitly pending)
* (recommended) verify `payload_digest` matches on DUPLICATE

### H5 — Receipt Ledger (Per-Session State)

**Role:** Store “what we know so far” for this session:

* per `event_id`: {status, evidence_ref, reason_codes, attempt_count, last_attempt_at}
* terminality tracking for `required_set[]`

### H6 — Completion Gate (I-J8 producer)

**Role:** Decide whether DF may complete the *input* WorkItem:

* `COMPLETE_OK` if all required have terminal receipts and none are QUARANTINE
* `COMPLETE_WITH_QUARANTINE` if all required are terminal but some are QUARANTINE
* otherwise `NOT_COMPLETE`

### H7 — Incident/Telemetry Emitter

**Role:** Convert “receipt truth” into operable signals:

* quarantine spikes, duplicate mismatch, receipt lag SLO breach
* emits structured signals to DF-X (and optionally pointer events if your platform uses them)

### HX — DF-X Interface Surface (Publish Governance)

Not a node by itself, but the interface DF-H uses for:

* retry budgets, timeouts, circuit state
* drain/pause signals
* max outstanding blocked sessions

---

## 3) DF-H internal joins (edges)

I’ll name these **H-J#** (local to DF-H):

* **H-J1:** DF-G → H1 (`DecisionPackage`)
* **H-J2:** H1 → H2 (`PublishPlan`: ordered events + required_set + correlation)
* **H-J3:** H2 → H3 (`SubmitBatch`: events + optional partition_key hints)
* **H-J4:** H3 → H4 (`RawReceipts`: receipt batch or timeout/transport error)
* **H-J5:** H4 → H5 (`VerifiedReceiptUpdates`)
* **H-J6:** H5 → H6 (`CompletionInputs`: required_set terminality view)
* **H-J7:** H6 → DF-A (I-J8) (`CompletionRecord` + receipt bundle)
* **H-J8:** H5/H7 → DF-X (publish health + incidents)
* **H-J9:** DF-X → H1/H3 (budgets: retry/timeout/circuit + drain/pause)

---

## 4) DF-H internal paths (how it behaves in production)

### H-P1 Normal success (all ADMIT)

1. H1 starts session
2. H2 normalizes ordering (DecisionResponse → intents)
3. H3 submits batch
4. H4 verifies receipts
5. H5 marks all required as terminal ADMIT
6. H6 emits `COMPLETE_OK` to DF-A via I-J8

### H-P2 Duplicate success (some/all DUPLICATE)

Same as H-P1, except H4 marks some receipts as DUPLICATE.
**Designer pin:** DUPLICATE is terminal success (the fact already exists). This follows the envelope’s idempotency meaning for `event_id`. 

### H-P3 Quarantine terminal (one or more QUARANTINE)

1–4 same
5. H5 marks QUARANTINE for some required outputs
6. H6 emits `COMPLETE_WITH_QUARANTINE`
7. H7 raises incident signals (quarantine is not “expected noise,” it’s a remediation trigger)  

### H-P4 Transport uncertainty (timeout / network failure)

* H3 submit returns “unknown” (no receipts)
* H5 cannot mark terminal
* H6 returns `NOT_COMPLETE`
* DF-X throttles/pause intake via I-J9/I-J12 until publish can progress (no checkpoint drift)

### H-P5 Partial receipt set (decision receipt arrived, intent receipts missing)

This is the dangerous one:

* DecisionResponse is ADMIT/DUPLICATE but at least one intent has no terminal receipt.
* **Pinned behavior:** session is still `NOT_COMPLETE` until *all produced intents in required_set* have terminal receipts.
* DF-X must apply backpressure to avoid unbounded in-flight work.

### H-P6 Drain/pause path

* Run/Operate triggers drain (via DF-X)
* H1 stops starting new sessions
* H3/H4/H5 continue driving existing sessions until they reach terminal receipts (or remain blocked and DF pauses safely)

---

## 5) DF-H internal loops (the “production reality” cycles)

### H-L1 Resend loop (idempotent retries)

When H3 fails or receipts are missing:

* retry is **resending the exact same events** (same `event_id`, same payload, same digests)
* on success, IG returns ADMIT or DUPLICATE
* loop ends only when receipts are terminal, not when “send succeeded”

This directly implements “assume duplicates and retries everywhere” without changing meaning. 

### H-L2 Receipt correlation loop (completeness + mismatch handling)

Receipts must be correlated to submitted `event_id`.

* If a receipt batch is missing entries → treat as **not complete**, retry/query again.
* If IG reports DUPLICATE but the payload digest differs (recommended check) → treat as **mismatch incident** (do not silently accept “history rewrite”).

### H-L3 Backpressure coupling loop (publish health → intake control)

* Rising “blocked sessions waiting on receipts” triggers DF-X to throttle/pause DF-A (I-J9)
* Once receipt progress recovers, DF-X resumes intake
  This preserves correctness under outages without creating drift.

### H-L4 Quarantine feedback loop (quarantine spikes → degrade/governance)

Not inside DF-H alone, but DF-H is the source:

* Quarantine spikes → DF-X surfaces to Obs/Gov → DL may tighten posture
  This keeps “safe to act” explicit and auditable. 

---

## 6) DF-H pins (the ones Codex must not violate)

### DFH-1 Publish ordering is deterministic

DecisionResponse must be published before intents, and intent order is canonical.

### DFH-2 Required set definition (ties to I-J8)

For trigger inputs: **DecisionResponse is always required**.
ActionIntents are required if produced.

### DFH-3 Completion requires terminal receipts

No terminal receipts → `NOT_COMPLETE` → no input checkpoint advance.

### DFH-4 Terminal receipt semantics

Only IG can produce terminal outcomes: **ADMIT / DUPLICATE / QUARANTINE**. 
Transport errors are *not receipts*.

### DFH-5 Quarantine is terminal but incident-worthy

DF completes with quarantine (doesn’t deadlock the partition forever), but raises a remediation signal. 

### DFH-6 Partitioning hint (optional but recommended)

IG stamps a deterministic `partition_key` for admitted events. 
**Recommendation:** DF-H supplies the same partition_key hint for DecisionResponse + intents for a WorkItem (e.g., `H(ContextPins, input_event_id)`), so EB ordering keeps the decision/intent cluster coherent downstream.

### DFH-7 No bypasses

DF-H must not “write to EB directly” without IG-equivalent receipt semantics. 

---

## 7) Environment ladder knobs specific to DF-H

Semantics identical across envs; only operational envelope changes.

* **Local:** tiny retry budgets, permissive auth, IG may be a local stub—but it must still return ADMIT/DUPLICATE/QUARANTINE receipts consistently.
* **Dev:** “real enough” authz and schema/policy enforcement so quarantine paths are exercised (not masked).
* **Prod:** strict authz; tighter publish SLOs; quarantine spikes page operators; DL corridor checks meaningful.

Policy config is outcome-affecting and must be versioned/auditable (receipts/provenance cite policy rev).

---

## What we should illuminate next inside DF-H (one more layer, if you want)

If we go one step deeper *within DF-H*, the highest-value opaque box to open is **H3 (IG Transport Adapter)** as a state machine:

* how it represents “unknown outcome” after timeout,
* whether it supports batch submit + per-event receipts,
* how it retries without changing event identity,
* how it persists/doesn’t persist per-session state across process restarts.

But we can stop here if this is the “right amount of machinery” before moving to the next DF node (DF-C).

---

Alright — now we illuminate **DF-C (Constraints & Bundle Selection)**. This is the internal “policy brain” that **freezes a DecisionPlan snapshot per WorkItem**: what DF is allowed to do (DL mask), what logic is active (Registry bundle), and what context is permitted/required (feature groups, IEG usage), all **stamped with policy revisions** so replay/audit can’t drift.

We’ll expose DF-C as its own **internal network of sub-nodes** (still mostly opaque), plus its **internal joins/paths/loops**.

---

## 0) DF-C v0 stance (designer-authoritative)

DF-C must produce **exactly one immutable `DecisionPlan` snapshot per WorkItem**, derived from:

* **DecisionBoundary** (event_time, pins, scope) from DF-B
* **DL posture snapshot** (mode + capabilities_mask + identity)
* **Registry resolution** (ActiveBundleRef + compatibility metadata)
* **DF policy profile revisions** (trigger map, compatibility rules, fail-safe rules)

…and DF-C must never mutate that plan mid-flight, even if DL/Registry update. Updates affect only future WorkItems.

---

## 1) DF-C boundaries

### Inputs to DF-C (from DF-B)

`DecisionBoundary` provides:

* `decision_scope` (deterministic domain derived from event_type family + pins)
* `event_time_utc` (envelope `ts_utc`)
* `pins` (ContextPins + seed taxonomy)
* `basis_fence` (no-peek hint, optional but pinned earlier)

### Outputs from DF-C (to DF-D)

`DecisionPlan` snapshot provides:

* `plan_id` (stable hash of inputs)
* `degrade_decision` snapshot identity + mask
* `active_bundle_ref` (or explicit fallback bundle policy)
* `compatibility_outcome` (OK / ALT_BUNDLE / SAFE_FALLBACK)
* `allowed_capabilities` (derived from mask ∩ bundle requirements ∩ policy)
* `context_contract` (required/optional/forbidden context sources + feature groups)
* `policy_revision_set` (outcome-affecting policy revs used to build plan)
* explicit “why” reason codes if plan is constrained/fallback

---

## 2) DF-C internal subnetworks (sub-nodes inside DF-C)

### C1 — Scope Resolver

**Role:** Normalize and validate the `decision_scope`.

* maps `(event_type, schema_version)` → `decision_domain`
* validates pins required for this domain (run-scoped vs global)
* yields `scope_key` used for registry resolution and context policy lookup

### C2 — Policy Snapshot Loader (DF-X interface)

**Role:** Ingest the current governed policy revisions for DF-C decisions:

* trigger policy rev (allowlist/ignore list)
* compatibility policy rev (bundle acceptance rules)
* fail-safe policy rev (what to do when inputs are missing)
* staleness tolerance policy revs (DL snapshot age, registry cache age, etc.)

*(This is where “policy profile” comes in; it must be stampable.)*

### C3 — Degrade Snapshot Fetcher

**Role:** Obtain a **DL snapshot** to use for this WorkItem:

* either from DF-X cache/subscription
* or directly from DL (pull) if cache is missing/stale
  Outputs `dl_snapshot = {mode, mask, decided_at, snapshot_id, age}`.

### C4 — Bundle Resolver

**Role:** Obtain the **ActiveBundleRef** for this scope:

* either from DF-X cache/event warmup
* or on-demand registry resolution
  Outputs `bundle_ref = {bundle_id, digests, contract metadata, required capabilities, feature deps, lifecycle ids}` plus `age`.

### C5 — Compatibility Evaluator

**Role:** Decide if `bundle_ref` is usable **under the DL mask + policy**.
Produces one of:

* `COMPAT_OK`
* `COMPAT_ALT_BUNDLE` (deterministic alternate like “rules-only safe bundle”)
* `COMPAT_FAIL` (forces safe fallback path)

### C6 — Context Contract Builder

**Role:** From (scope + bundle requirements + mask + policy) build a **context contract**:

* whether IEG is REQUIRED/OPTIONAL/FORBIDDEN
* whether OFP is REQUIRED/OPTIONAL/FORBIDDEN
* which feature groups are REQUIRED vs OPTIONAL vs FORBIDDEN
* staleness tolerance per group (policy-driven)
* “if missing required group → safe fallback” vs “degraded exec allowed” (this is the P3 vs P4 boundary)

### C7 — Plan Assembler + Stamper

**Role:** Produce the immutable `DecisionPlan`:

* stamps `plan_id`
* stamps `policy_revision_set`
* stamps snapshot identities and ages (DL snapshot id, registry resolution id)
* stamps explicit reason codes if constrained
* freezes plan for this WorkItem

### C8 — Plan Cache/Telemetry Publisher (DF-X)

**Role:** Publish “plan usage” facts to DF-X:

* metrics by plan outcome (OK/SAFE_FALLBACK/ALT_BUNDLE)
* reasons (DL stale, registry unavailable, incompatible bundle, etc.)
* used snapshot ids and policy rev ids (for audit and debugging)

---

## 3) DF-C internal joins (edges)

I’ll name these **C-J#** (local to DF-C):

* **C-J1:** DF-B → C1 (`DecisionBoundary`)
* **C-J2:** C1 → C2 (`scope_key` + “pins validity status”)
* **C-J3:** C2 → C3 (`policy rev set` → DL fetch rules)
* **C-J4:** C2 → C4 (`policy rev set` + scope → registry fetch rules)
* **C-J5:** C3 + C4 → C5 (`dl_snapshot` + `bundle_ref` + compat policy → compat result)
* **C-J6:** C1 + C5 + C2 → C6 (scope + compat + mask + policy → context contract)
* **C-J7:** C3 + C4 + C5 + C6 + C2 → C7 (assemble + stamp plan)
* **C-J8:** C7 → DF-D (`DecisionPlan`)
* **C-J9:** C7 → C8/DF-X (telemetry + plan usage record)

---

## 4) DF-C internal paths (how it behaves in production)

### C-P1 Normal plan (everything healthy)

1. C1 resolves scope cleanly
2. C3 gets current DL snapshot
3. C4 resolves active bundle
4. C5 says COMPAT_OK
5. C6 builds context contract (required/optional groups)
6. C7 emits `DecisionPlan(PLAN_OK)`
   → feeds I-P1 or I-P4 depending on what DF-D later acquires

### C-P2 Fail-closed plan (DL unavailable / invalid)

* C3 fails to obtain acceptable DL snapshot
* **Pinned behavior:** fail-closed → plan forces `SAFE_FALLBACK` (constraints-only)
* C7 emits `DecisionPlan(PLAN_SAFE_FALLBACK, reason=DL_UNAVAILABLE_FAIL_CLOSED)`

### C-P3 Registry unavailable plan

* C4 cannot resolve bundle within policy tolerance
* **Pinned behavior:** safe fallback unless a deterministic “last-known-good allowed” policy exists
* Default v0: `PLAN_SAFE_FALLBACK` (reason=REGISTRY_UNAVAILABLE)

### C-P4 Incompatible active bundle (mask conflict or feature contract mismatch)

* C5 finds bundle requires forbidden capabilities or incompatible feature contract
* If registry/policy provides deterministic alternate: `PLAN_ALT_BUNDLE`
* Else: `PLAN_SAFE_FALLBACK`

### C-P5 Scoped-but-not-joinable plan (pins missing for this domain)

* C1 marks scope as non-joinable (e.g., run-scoped domain missing run_id/scenario_id)
* Plan outcome is constrained: either safe fallback or “non-trigger” depends on policy.
  **Designer pin:** if the event was classified as TRIGGER upstream, DF-C should still produce a plan that forces safe behavior rather than silently changing it to non-trigger; the skip decision belongs to DF-A trigger policy.

---

## 5) DF-C internal loops (the production cycles inside DF-C)

### C-L1 Plan snapshot loop (resolve → verify → fallback)

This is our earlier **I-L3**, realized inside DF-C:

* resolve DL + bundle → compatibility check → (OK | ALT_BUNDLE | SAFE_FALLBACK)
  Key pin: **one plan per WorkItem**, immutable.

### C-L2 Cache refresh loop (DF-X assisted)

* DF-X may keep DL snapshots and bundle refs warm
* DF-C consumes caches but must stamp:

  * snapshot age
  * snapshot identity
  * policy rev ids
    If cache stale beyond tolerance → DF-C forces safe behavior (fail-closed).

### C-L3 “P3 vs P4 boundary” loop (context contract decision)

This is the most important internal loop to pin clearly:

DF-C must decide, per scope, whether missing context causes:

* **FORCED SAFE FALLBACK (I-P3)**, or
* **DEGRADED EXECUTION ALLOWED (I-P4)**.

This decision is owned by the **context contract** and must be policy-driven and stamped.

---

## 6) The critical DF-C design pins (Codex must not drift)

### DFC-1 One immutable plan per WorkItem

No mid-flight changes due to DL/Registry updates.

### DFC-2 DL mask is hard constraints

Mask forbids capabilities → plan must mark them forbidden (not “try anyway”).

### DFC-3 Registry resolution is deterministic

No “latest.” DF-C records bundle ref used (or fallback mode).

### DFC-4 Context contract is explicit and complete

For each context source and feature group:

* REQUIRED / OPTIONAL / FORBIDDEN
* staleness tolerance rules
* “missing required” behavior (safe fallback vs degraded allowed)

### DFC-5 Plan stamps policy revision set

Outcome-affecting policy must be citeable: trigger policy rev, compat policy rev, fail-safe policy rev, staleness tolerance revs.

---

## 7) Minimal “machinery diagram” for DF-C (still opaque inside each box)

```text
DF-B DecisionBoundary
        |
        v
      [C1 Scope Resolver] -----> scope_key + pin validity
        |
        v
   [C2 Policy Snapshot Loader] ----> policy_revision_set
        |                 |
        |                 +------------------------------+
        v                                                v
[C3 Degrade Snapshot]                           [C4 Bundle Resolver]
        |                                                |
        +-------------------+----------------------------+
                            v
                 [C5 Compatibility Evaluator]
                            |
                            v
                 [C6 Context Contract Builder]
                            |
                            v
                [C7 Plan Assembler + Stamper] ---> DecisionPlan -> DF-D
                            |
                            v
                    [C8 Telemetry/Cache to DF-X]
```

---

## What to illuminate next (inside DF-C) without overwhelming

The single highest-leverage seam is **C6 (Context Contract Builder)** because it decides:

* when DF must go to safe fallback (I-P3),
* when degraded execution is allowed (I-P4),
* what feature groups are required/optional,
* and how staleness tolerance is applied.

---

Alright — illuminating **DF-B: Decision Boundary & Basis Fence**.

DF-B is the **“freeze the world for this one decision”** module. It does *not* decide anything; it defines **what the decision is allowed to mean**, in terms of **time**, **identity pins**, and **replay basis**. Everything downstream (DL/Registry/OFP/IEG, decision logic, provenance) hangs off this boundary.

Key platform anchors DF-B must obey:

* **Domain time = `ts_utc`** on the canonical envelope; time semantics never collapse. 
* Canonical envelope required fields include `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`. 
* **ContextPins = `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`**, with `seed` as a separate taxonomy field (required when applicable, not always). 
* Consumer progress offsets are **exclusive-next** (“next offset to read/apply”), and that meaning becomes the watermark basis. 

---

## 1) DF-B boundary contract

### Input (from DF-A via I-J1)

`WorkItem = {envelope, event_ref(stream,partition,offset), pins, trigger_classification, ingest_meta}`
(Envelope is already validated by DF-A; DF-B still asserts invariants.)

### Output (to DF-C via I-J2)

`DecisionBoundary = {boundary_id, decision_key, event_time_utc, basis_ref, pins_normalized, joinability_flags, scope_seed, basis_fence}`

Where:

* `event_time_utc := envelope.ts_utc` (domain/meaning time)
* `basis_ref` is by-ref (never “scan latest”) 
* `basis_fence` uses exclusive-next offset semantics 

---

## 2) DF-B internal subnetworks (sub-nodes inside DF-B)

### B1 — Boundary Asserter

**Role:** Re-assert the envelope invariants DF-B relies on:

* required envelope fields exist (especially `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`) 
* `additionalProperties=false` posture (payload isolation under `payload`) is respected 
* `event_ref` exists (stream/partition/offset present)

### B2 — Pin Extractor + Normalizer

**Role:** Produce a canonical internal representation of pins:

* `context_pins = {manifest_fingerprint, parameter_hash?, scenario_id?, run_id?}`
* `seed?` treated separately (carried if present/needed) 
  **Note:** “normalize” here means *representation only* (e.g., consistent types/strings), not rewriting truth.

### B3 — Joinability Classifier

**Role:** Decide which join contracts *can* apply:

* `run_joinable = true` iff the event claims run scope *and* carries full ContextPins 
* `seeded = true` iff seed is present (or required by later policy for this event family)

This is not decision logic; it’s boundary metadata for DF-C (“plan must treat missing pins explicitly”).

### B4 — Event Time Resolver

**Role:** Freeze decision boundary time:

* `event_time_utc := ts_utc` (always)
* `emitted_at_utc` stays optional metadata; never substitutes for `ts_utc`

### B5 — Basis Reference Builder

**Role:** Construct the by-ref anchor:

* `basis_ref = {input_event_id, stream_name, partition_id, offset}`
  This is the “what we decided on” pointer used by provenance and audit.

### B6 — Scope Seed Builder

**Role:** Produce a deterministic **scope seed** for DF-C to resolve into a decision domain/scope.

* Inputs: `(event_type, schema_version?, joinability flags, pins presence)`
* Output: `scope_seed` (a stable tuple or hash)

**Designer clarification (to avoid drift with DF-C):**
DF-B produces **scope_seed**, not the final “which bundle is active” scope decision. DF-C’s **Scope Resolver (C1)** is where the policy-owned domain mapping is applied and stamped with policy revs.

### B7 — Basis Fence Builder

**Role:** Compute the **no-peek fence** that prevents “future knowledge” leaks.

* Using the pinned meaning of offsets: checkpoint offset is exclusive-next. 
* For an input event at `(stream S, partition P, offset o)`:

  * `fence[S,P].max_next_offset_to_apply = o + 1`
  * other partitions are unconstrained by default

This fence is later used as:

* a **request hint** (if OFP/IEG support basis-bounded serving), and
* a **verification hook** (DF-D can reject context as `BASIS_VIOLATION` if returned `input_basis/graph_version` implies “applied beyond fence”).

### B8 — Boundary ID + Decision Key Stamper

**Role:** Generate stable identifiers:

* `boundary_id` = stable hash of `{basis_ref, context_pins, scope_seed, boundary_recipe_version}`
* `decision_key` = stable per-decision identifier used downstream for joins/telemetry

**Pin:** these IDs must be deterministic under replay (no UUIDs unless derived deterministically), consistent with “assume duplicates/retries everywhere.” 

### B9 — Boundary Emission + Telemetry Hook

**Role:** Emit `DecisionBoundary` and record minimal metrics:

* boundary build failures
* joinability flags distribution
* time skew diagnostics (optional: `ts_utc` vs now, for ops only)

---

## 3) DF-B internal joins (edges)

Call these **B-J#** (inside DF-B):

* **B-J1:** WorkItem → B1 (assert envelope + ref)
* **B-J2:** B1 → B2 (pins extraction)
* **B-J3:** B2 → B3 (joinability flags)
* **B-J4:** B1 → B4 (time resolve from `ts_utc`)
* **B-J5:** B1 → B5 (basis_ref from event_ref + event_id)
* **B-J6:** (B1,B2,B3) → B6 (scope_seed)
* **B-J7:** B5 → B7 (basis_fence from offset)
* **B-J8:** (B4,B5,B6,B7,B2,B3) → B8 (IDs)
* **B-J9:** B8 → output `DecisionBoundary` (to DF-C)

---

## 4) DF-B internal paths (production behavior)

### B-P1 Normal path (healthy WorkItem)

WorkItem valid → pins normalized → joinability flags → event_time set from `ts_utc` → basis_ref built → scope_seed built → basis_fence built → IDs stamped → DecisionBoundary emitted.

### B-P2 “Not run-joinable” boundary (pins incomplete)

WorkItem valid but missing some ContextPins:

* DF-B still emits a DecisionBoundary, but sets:

  * `run_joinable=false`
  * `missing_pins=[…]`
    Downstream DF-C must plan accordingly (often safe fallback).

### B-P3 Fatal boundary construction (should be impossible if DF-A is correct)

If required envelope fields are missing (especially `ts_utc` or `event_id`) or event_ref is missing:

* DF-B emits **no boundary**
* raises a hard internal error signal
* does **not** allow progression (this would otherwise create half-truth decisions)

This aligns with your “Tier-0 anchors must exist or don’t publish” posture.

### B-P4 Multi-topic / multi-stream intake

If DF consumes multiple traffic topics, DF-B includes `stream_name` in basis_ref and fence, ensuring the fence is specific to the actual stream identity (important for watermark vectors).

---

## 5) DF-B loops (small but real)

### B-L1 Canonicalization loop (representation-only)

* parse pins and times into canonical internal types
* **never** rewrite truth (no inventing missing pins, no substituting `emitted_at_utc` for `ts_utc`)

### B-L2 Fence computation loop

* always compute `o+1` exclusive-next fence for the input partition 
* downstream can later compare returned watermark vectors to this fence (basis violation detection).

### B-L3 Stability loop (deterministic hashing)

Any hashes/IDs computed here must use stable ordering / canonical serialization (same bytes under replay), consistent with the platform determinism rail. 

---

## 6) DF-B drift bans (explicit “non-joins” inside DF-B)

* **No external calls** from DF-B (no DL, no Registry, no OFP, no IEG).
* **No hidden “now”**: `event_time_utc` is always `ts_utc`.
* **No scanning/discovery**: basis is always by-ref (stream/partition/offset). 
* **No pin invention**: missing ContextPins/seed are reported as missing; never synthesized. 

---

## 7) Environment ladder knobs for DF-B

DF-B is intentionally **semantics-stable** across local/dev/prod. The only env knobs are operational:

* telemetry verbosity/sampling
* strictness of “fatal vs constrained” handling for malformed WorkItems (but **must not** accept missing `ts_utc`/`event_id`; those are required by the envelope) 

---

### What to illuminate next (inside DF-B) with the most leverage

If we go one more layer down, the most important internal subnode is **B7 Basis Fence Builder**, because it’s the bridge between:

* the input event’s EB position (offset), and
* the later “basis violation” enforcement when consuming OFP/IEG context (watermark vectors).

---

Alright — **DF-F (Intent Synthesis & Output Identity)** is the “make it real + make it replay-safe” module: it turns an internal decision draft into **stable, executable intent facts** (still *not execution*) with **deterministic identities**, **idempotency anchors**, and **canonical ordering** so the whole platform survives duplicates/replay.

Below is DF-F’s machinery as an **internal network of sub-nodes** (still opaque inside each sub-node), plus DF-F’s internal joins/paths/loops.

---

## 0) DF-F boundary contract

### Inputs to DF-F (from DF-E via I-J5)

A `DecisionDraft` that includes (conceptually):

* `draft_outcome` (e.g., APPROVE/DECLINE/STEP_UP/REVIEW)
* `intent_candidates[]` (each with proposed action_type + parameters + target info)
* `decision_scope` (domain bucket)
* references/handles to the already-frozen `DecisionBoundary` and `DecisionPlan` (or those objects attached inline)

### Outputs from DF-F (to DF-G via I-J6)

`DecisionOutputs` (internal form), containing:

* **DecisionResponse skeleton**: outcome + links + stable `decision_event_id`
* **ActionIntent skeletons**: each with stable `intent_event_id` + **deterministic `idempotency_key`**
* a deterministic `actions[]` ordering
* “enforcement notes” (what got suppressed/clipped by constraints) for provenance later

DF-F does **not** talk to DL/Registry/OFP/IEG (no external calls). It’s pure transformation of already frozen inputs.

---

## 1) DF-F internal subnetworks (sub-nodes inside DF-F)

### F1 — Draft Validator & Binder

**Role:** Ensure the draft is self-consistent and bind it to the boundary/plan.

* asserts `decision_scope` exists
* asserts `ContextPins` exist (or flags missing pins explicitly)
* pulls `action_posture` / action constraints from the frozen DecisionPlan

### F2 — Outcome→Action Policy Mapper

**Role:** Map `draft_outcome` to a **canonical action posture** (what intents *should* exist).

* centralizes “outcome implies action” mapping (e.g., APPROVE → APPROVE_TRANSACTION)
* produces a “desired intents template” (still abstract)

*(Your conceptual DF doc points at this mapping and deterministic behavior; we treat that as compatible vocabulary, not authority.)

### F3 — Constraint Enforcer (Hard Clamp)

**Role:** Apply **DecisionPlan constraints** as hard limits *at output time*.

* enforces DL `action_posture` constraints (e.g., STEP_UP_ONLY disallows APPROVE intents)
* enforces action allowlists by *plan* (not AL; AL will enforce too, but DF must not emit obviously forbidden intents)

**Designer pin (important): output coherence clamp**
If the draft outcome implies forbidden actions under the plan, DF-F must deterministically **clip** the output to a coherent safe posture:

* e.g., `action_posture=STEP_UP_ONLY` ⇒ final outcome becomes `STEP_UP`, intents become `STEP_UP_AUTH` (and optionally `QUEUE_CASE`)
  …and DF-F emits “clipped_by_constraints” metadata so DF-G can record it in provenance.

This avoids the incoherent state “DecisionOutcome=APPROVE but no approve intent exists.”

### F4 — Intent Canonicalizer

**Role:** Turn candidate intents into a canonical internal structure:

* normalizes `parameters` (stable key ordering, stable numeric/string forms)
* strips/forbids nondeterministic fields (`now`, random ids, unordered maps)
* stamps required join fields that must exist in payload later:

  * ContextPins
  * `request_id`/`input_event_id` linkage
  * `decision_event_id` linkage (once known)

### F5 — Action Key Builder

**Role:** Derive a deterministic **action key** for uniqueness *within an action domain*.

* `action_domain` is coarse (“txn_disposition”, “case_queue”, “notify”…)
* `action_key` binds to the intended target:

  * txn_disposition → txn_id/auth_id
  * case_queue → (queue_name + subject_id)
  * notify → (channel + recipient_id)
    If no natural target exists, use `"primary"` (meaning “at most one per domain per input event”).

### F6 — Identity & Idempotency Hasher

**Role:** Produce stable identities that make replay safe.
Canonical Event Envelope defines `event_id` as **stable idempotency/dedup identity at ingest/bus boundaries**. 
AL enforces effectively-once via **(ContextPins, idempotency_key)**. 

**Designer pin (DF-F v0): domain-safe idempotency**

* `idempotency_key = H(ContextPins, input_event_id, action_domain, action_key)`
* `intent_event_id = H("action_intent", ContextPins, input_event_id, action_domain, action_key)`
* `decision_event_id = H("decision_response", ContextPins, input_event_id, decision_scope)`

This is stricter/safer than action_type-only because it prevents conflicting duplicates from producing multiple side effects in the same domain, while still allowing multiple intents when `action_key` differs.

### F7 — Collision Resolver

**Role:** Handle “two intents collide” deterministically.
Collision means: two intents produce the same `(action_domain, action_key)` for the same input.

* deterministic coalesce rule: pick winner by (domain priority, action_type priority, stable tie-break on canonicalized params digest)
* losers are dropped with a recorded “collision_suppressed” note for provenance

### F8 — Ordering & Serialization Guard

**Role:** Enforce deterministic ordering and stable serialization boundaries.

* canonical sort of `actions[]` (we pin: sort by `(action_domain, action_key, action_type)` lexicographically)
* stable serialization for any hashing/digest use
  Your conceptual DF doc explicitly calls for deterministic ordering to prevent drift; we adopt the stronger ordering above.

### F9 — Attribution Stamping (Actor/Origin)

**Role:** Ensure every intent is attributable (even though AL enforces execution).
Platform pins: ActionIntents should carry an actor principal + origin, and AL uses that identity to authorize execution.
So DF-F stamps:

* `actor_principal = df_service_principal` (declared identity)
* `origin = "AUTOMATED_DF"`
  This becomes part of the intent payload (not envelope fields).

### F10 — Output Assembler

**Role:** Assemble the final `DecisionOutputs` internal object:

* `DecisionResponse` skeleton (final_outcome + actions[] + linkage ids)
* intents array with ids/keys/ordering/attribution
* enforcement notes (clipped_by_constraints, collisions, suppressed intents)

---

## 2) DF-F internal joins (edges)

Call these **F-J#** (inside DF-F):

* **F-J1:** DecisionDraft → F1 (validate/bind to boundary/plan)
* **F-J2:** F1 → F2 (outcome→action mapping)
* **F-J3:** (F2 + plan constraints) → F3 (hard clamp / clip)
* **F-J4:** F3 → F4 (canonicalize intents + params)
* **F-J5:** F4 → F5 (derive action_domain/action_key)
* **F-J6:** F5 → F6 (compute ids + idempotency keys)
* **F-J7:** F6 → F7 (collision resolution)
* **F-J8:** F7 → F8 (canonical ordering + stable serialization guard)
* **F-J9:** F8 → F9 (actor/origin stamping)
* **F-J10:** F9 → F10 (assemble DecisionOutputs → DF-G)

---

## 3) DF-F internal paths (production behaviors)

### F-P1 Normal path (no constraints triggered)

Draft outcome maps to expected intent(s) → canonicalize → derive keys → compute ids → sort → stamp actor/origin → emit outputs.

### F-P2 STEP_UP_ONLY clamp path

Plan says `action_posture=STEP_UP_ONLY`:

* F3 drops any approve/decline intents
* final outcome becomes STEP_UP
* emits STEP_UP_AUTH (and optionally QUEUE_CASE)
  …and records `clipped_by_constraints=true` for provenance.

### F-P3 No-actions path

Some decisions may intentionally emit zero intents (policy choice).

* DF-F emits DecisionResponse with empty actions[] and records `no_actions_reason`.

### F-P4 Collision path

Two candidate intents resolve to same `(domain,key)`:

* F7 coalesces deterministically
* records suppressed intent(s) for provenance

---

## 4) DF-F internal loops (production cycles)

### F-L1 Determinism loop (canonicalization → hash → recheck)

DF-F must be stable under replay:

* canonicalize parameters
* compute ids/keys
* re-canonicalize / verify stable serialization (no nondeterministic ordering)

### F-L2 Constraint clamp loop (draft inconsistency → coercion)

If draft produces a forbidden combination:

* clamp outcome/intents to safe coherent posture
* never emit “incoherent truth” (APPROVE outcome with STEP_UP_ONLY posture)

### F-L3 Collision loop (coalesce until unique)

If coalescing still yields collisions (e.g., multiple “primary” keys), DF-F repeats deterministic collapse until each `(domain,key)` is unique.

---

## 5) DF-F drift bans (explicit non-joins)

* **No external calls** (DL/Registry/OFP/IEG) inside DF-F.
* **No UUID minting** for ids/keys; all identity is deterministic from boundary/plan/draft.
* **No hidden time** in parameters (no “now” stamps that change hashes).
* **No relying on map iteration order**; ordering must be explicitly canonical. 
* **No emitting intents without ContextPins + linkage identifiers**, because AL’s uniqueness scope and audit joins depend on them.

---

## 6) Environment ladder knobs for DF-F

DF-F semantics do **not** vary by env. Only observability verbosity may differ:

* emit more debug “suppressed intent reasons” in local/dev
* but ids/ordering/mapping must be identical across local/dev/prod (otherwise replay parity breaks)

---

If you want the next node after DF-F, the natural follow-on is **DF-G (Provenance & Evidence Packaging)**, because DF-F produces the enforcement notes (clamps/collisions) that DF-G must record to keep audit honest.

---

Alright — **DF-G (Provenance & Evidence Packaging)** is the module that turns “a decision + intents exist” into an **audit-honest, replay-defensible, by-ref package** that can safely become platform truth via DF-H → IG → EB.

It is also the module that enforces your rule: **no half-truth decisions** (DLA must not be forced to guess or quarantine “normal” decisions due to missing anchors). 

---

## 0) DF-G v0 stance (designer-authoritative)

DF-G must output **exactly one of**:

1. **A COMPLETE DecisionPackage**
   “Normal” decision, provenance anchors complete.

2. **A CONSTRAINED DecisionPackage**
   Decision is explicitly constrained (degrade/missing context/forced safe fallback), and provenance states **what was missing and why**.

3. **A BLOCKED (non-publishable) condition**
   Only when **Tier-0 anchors are missing** (e.g., missing `event_id` / `ts_utc` / basis ref). In this case DF-G must **not** allow publish and must not allow completion (replay/bug signal).

DF-G must never emit something that *looks normal* but is missing required provenance. 

---

## 1) DF-G boundary contract

### Inputs to DF-G

DF-G binds together four already-frozen artifacts:

* **DecisionBoundary** (from DF-B): event_time, basis_ref, pins, scope_seed/fence
* **DecisionPlan** (from DF-C): DL snapshot identity + mask, bundle_ref, context contract, policy rev set
* **ContextSnapshot** (from DF-D): OFP provenance (`feature_snapshot_hash`, `input_basis`, freshness, versions) and/or IEG `graph_version`, plus explicit non-use reasons
* **DecisionOutputs** (from DF-F): stable `decision_event_id`, `intent_event_id`s, `idempotency_key`s, canonical ordering, clamp/collision notes

### Output of DF-G

A `DecisionPackage` to DF-H containing:

* `publish_set[]`: canonical envelope events ready to submit
* `required_set[]`: which outputs must receive terminal receipts before input completion
* `provenance_block`: the audit/replay bundle (complete or constrained)
* `provenance_grade`: `COMPLETE | CONSTRAINED`
* optional `payload_digest` per event (recommended for duplicate-mismatch detection)

Canonical envelope requirements at the boundary remain in force (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`, payload under `payload`). 

---

## 2) DF-G internal subnetworks (sub-nodes inside DF-G)

### G1 — Input Binder

**Role:** Collect and bind the four inputs into one “decision assembly context.”

* validates expected references exist (e.g., DecisionOutputs references DecisionBoundary)
* normalizes field locations (e.g., “where is input_event_id?”)

### G2 — Provenance Model Builder

**Role:** Build the internal provenance object (still not envelope-wrapped).
It produces a structured provenance record with sections:

* `basis` (input event + EB coords)
* `constraints` (degrade posture used)
* `bundle` (active bundle ref)
* `context` (OFP snapshot + IEG graph info, or explicit non-use reasons)
* `transform_notes` (clamped_by_constraints, collisions, suppressed intents)
* `policy_revisions` (profile revisions that affected outcome)

### G3 — Evidence Pointer Assembler

**Role:** Ensure provenance is **by-ref**, not copy-everything:

* basis pointer: `(stream, partition, offset)` + `input_event_id`
* snapshot tokens: `feature_snapshot_hash`, `input_basis`, `graph_version`
* DL snapshot identity and decided_at
* bundle refs/digests and lifecycle ids if present

### G4 — Completeness Gate

**Role:** Enforce the “no half-truth” law via a tiered check.

**Tier-0 (must exist or BLOCK):**

* `input_event_id`
* `(stream, partition, offset)` basis pointer
* `input_event_time_utc = ts_utc`
* `manifest_fingerprint`
* stable `decision_event_id`
  If any missing → **BLOCK** (do not publish; do not complete).

**Tier-1 (must be present OR explicitly non-used with reason):**

* DL posture identity (or fail-closed fallback identity)
* bundle_ref (or explicit “registry unavailable → fallback plan”)
* if OFP used: `feature_snapshot_hash` + `input_basis` + versions/freshness + `as_of_time_utc`
* if IEG used: `graph_version`
* explicit non-use reasons per source/group

### G5 — Constrained Downgrade Orchestrator

**Role:** If Tier-1 cannot be satisfied for a “normal” decision, DF-G forces a **constrained form**:

* either downgrade to `CONSTRAINED` (safe fallback / degraded exec allowed) while keeping decision IDs stable where appropriate
* or request a controlled rebuild of outputs as safe fallback (back-edge to DF-F/DF-E via the already-pinned downgrade loop)

*(Mechanically: DF-G doesn’t “decide,” it demands a constrained output variant when provenance would otherwise be dishonest.)*

### G6 — Envelope Builder

**Role:** Wrap the DecisionResponse and each ActionIntent into **CanonicalEventEnvelope** events:

* sets required envelope fields
* sets `parent_event_id` chain:

  * DecisionResponse parent = input_event_id
  * ActionIntent parent = decision_event_id
* keeps input domain time in provenance; envelope `ts_utc` for DF outputs is issuance time (not replacing the input’s `ts_utc`)

### G7 — Deterministic Serialization + Digest

**Role:** Ensure stable bytes under replay:

* canonical JSON ordering for payload/provenance
* computes `payload_digest` (recommended) so duplicates can be verified as identical

### G8 — Publish Set Composer

**Role:** Build `publish_set[]` + `required_set[]` deterministically:

* ordering: DecisionResponse first, then intents in canonical order
* required_set policy:

  * DecisionResponse always required for TRIGGER decisions
  * intents required if produced

### G9 — Provenance Telemetry Emitter

**Role:** Emit structured signals to DF-X:

* grade counts (COMPLETE vs CONSTRAINED)
* reasons for constrained decisions
* missing-anchor blocks (Tier-0 violations are bugs)
* clamp/collision rates

---

## 3) DF-G internal joins (edges)

Call these **G-J#**:

* **G-J1:** inputs → G1 (bind)
* **G-J2:** G1 → G2 (build provenance model)
* **G-J3:** G2 → G3 (assemble evidence pointers)
* **G-J4:** (G2+G3) → G4 (completeness check)
* **G-J5:** G4 → G5 (downgrade/repair decision)
* **G-J6:** (final provenance + outputs) → G6 (envelope wrap)
* **G-J7:** G6 → G7 (stable serialize + digest)
* **G-J8:** G7 → G8 (publish_set + required_set)
* **G-J9:** G8 → DF-H (DecisionPackage)
* **G-J10:** G4/G9 → DF-X (telemetry/incidents)

---

## 4) DF-G internal paths (production behaviors)

### G-P1 Normal COMPLETE package

All anchors exist → Tier-0 and Tier-1 satisfied → envelope wrap → publish_set emitted with `provenance_grade=COMPLETE`.

### G-P2 Degraded but honest CONSTRAINED package

Context partially missing or forbidden → Tier-1 satisfied via explicit non-use reasons → emit constrained decision with `provenance_grade=CONSTRAINED`.

### G-P3 Forced downgrade (repair by rebuild)

Tier-1 for “normal” cannot be met (e.g., plan said OFP required but snapshot absent beyond tolerance) → G5 forces safe fallback output variant → repackage as CONSTRAINED.

### G-P4 BLOCK (Tier-0 failure)

Missing input basis/time/id anchors → DF-G refuses to produce publish_set.
This is treated as an internal correctness failure (do not publish; do not complete; rely on replay/bug remediation).

---

## 5) DF-G internal loops (production cycles)

### G-L1 Provenance completeness loop (assemble → check → repair)

Assemble provenance → check tiers → attempt repair from already-frozen inputs → if still missing, downgrade.

### G-L2 Downgrade loop (constrained rebuild)

When downgrade is required:

* request constrained output variant
* re-run packaging
* converge to CONSTRAINED, never to “normal but missing anchors”

### G-L3 Determinism loop (serialize → hash → verify stability)

Canonicalize payload/provenance → hash → ensure ordering stable → stamp digest.

---

## 6) DF-G drift bans (explicit non-joins)

* **No external calls**: DF-G must not call DL/Registry/OFP/IEG (it only consumes their frozen snapshots).
* **No silent omissions**: if something wasn’t used, DF-G must say **why** (forbidden vs unavailable vs stale).
* **No “normal” flag without Tier-1**: if provenance is incomplete, it must be CONSTRAINED or BLOCKED.
* **No rewriting domain truth**: DF-G never changes the input event basis/time; it only references it.
* **No non-deterministic serialization**: ordering must be explicit (no map iteration drift).

---

## 7) Environment ladder knobs for DF-G

Semantics identical across local/dev/prod. Only operational knobs:

* verbosity of provenance-debug telemetry (more in local/dev)
* strictness of “BLOCK” reporting thresholds (but Tier-0 must always block; that’s invariant)
* retention of internal packaging traces (ops convenience only)

---

If you want the next node after DF-G, the natural next is **DF-D (Context Acquisition)**, because DF-G’s Tier-1 requirements directly constrain what DF-D must always return (provenance tokens or explicit non-use reasons).

---

Alright — **DF-D (Context Acquisition)** is the module that turns **DecisionPlan + DecisionBoundary** into a **frozen ContextSnapshot** that DF-E can safely use, with **explicit as-of time**, **explicit provenance tokens**, **hard obeying degrade mask**, and **basis-fence / no-peek enforcement**.

This node is *where “what DF knew” becomes concrete* (and replay-defensible).

---

## 0) DF-D v0 stance (designer-authoritative)

DF-D must output a `ContextSnapshot` in which **every context source** is in one of these explicit states:

* `USED` (with required provenance tokens)
* `FORBIDDEN_BY_MASK`
* `NOT_REQUESTED_BY_PLAN`
* `UNAVAILABLE`
* `STALE_BEYOND_TOLERANCE`
* `NOT_FOUND`
* `BASIS_VIOLATION`

…and DF-D must **never**:

* call OFP with hidden “now” (as_of must be explicit),
* call IEG when `allow_ieg=false`,
* return “context used” without **provenance** (`feature_snapshot_hash`, `input_basis`, `graph_version` when applicable).

---

## 1) DF-D boundary contract

### Inputs (from DF-C + DF-B)

* `DecisionPlan`:

  * DL mask fields (`allow_ieg`, `allowed_feature_groups`, etc.)
  * context contract: required/optional/forbidden sources + feature groups
* `DecisionBoundary`:

  * `event_time_utc := ts_utc` (domain time boundary)
  * `basis_ref` (stream/partition/offset pointer)
  * `basis_fence` (no-peek hint based on exclusive-next offset semantics)

### Output (to DF-E)

`ContextSnapshot`:

* `ofp`: optional feature snapshot + provenance (`feature_snapshot_hash`, group versions, freshness, `as_of_time_utc`, `input_basis`, and `graph_version` if OFP consulted IEG)
* `ieg`: optional identity/graph context + `graph_version`
* `keying`: what FeatureKeys were used (canonical vs reduced) + explicit limitation reason when IEG not used
* explicit per-source reasons when not used

---

## 2) DF-D internal subnetworks (sub-nodes inside DF-D)

### D1 — Context Request Planner

**Role:** Turn `DecisionPlan + DecisionBoundary` into a concrete acquisition plan:

* which sources to call (IEG? OFP?)
* which feature groups to request (required vs optional)
* which keys are needed to call OFP
* establishes “requiredness”: missing required context ⇒ force safe fallback later (DF-E / DF-G)

### D2 — Mask Enforcer (hard gate)

**Role:** Apply DL mask as hard constraints:

* if `allow_ieg=false` ⇒ mark IEG as `FORBIDDEN_BY_MASK` (no calls)
* enforce `allowed_feature_groups` allowlist on OFP request groups (no bypass)

### D3 — FeatureKey Builder

**Role:** Build canonical FeatureKeys for OFP:

* preferred: canonical entity IDs from IEG (EntityRef)
* if IEG is forbidden/unavailable, derive best-effort keys from what’s in the event payload and **record limitation** (reduced keying)

### D4 — IEG Client

**Role:** When allowed, call IEG for:

* identity resolution (canonical IDs)
* optional neighbor context (only if plan requires)
  Return: identity context + `graph_version` token

### D5 — OFP Request Builder

**Role:** Build `get_features` request:

* `as_of_time_utc = DecisionBoundary.event_time_utc` (no hidden now)
* groups restricted by allowlist + plan contract
* attach ContextPins + requested group versions (if applicable)

### D6 — OFP Client

**Role:** Call OFP and obtain:

* features + required provenance (`feature_snapshot_hash`, versions, freshness, `input_basis`, optional `graph_version`)

### D7 — Freshness & Missingness Interpreter

**Role:** Normalize OFP group-level states:

* `stale=true` / freshness blocks
* NOT_FOUND (no data)
* UNAVAILABLE (call failed)
  These must be explicit because later stage gating depends on them (e.g., “stale ⇒ Stage 2 skip”).

### D8 — Basis Fence Checker (no-peek enforcement)

**Role:** Enforce the designer “basis fence” rule:

* Compare returned `input_basis` (and/or `graph_version`) to the **DecisionBoundary fence**.
* If, for the **same stream+partition as the input event**, the returned applied “next offset” is **greater than** `o+1`, mark as `BASIS_VIOLATION` and treat the context as unusable for this WorkItem.
  This uses the pinned meaning of checkpoints/watermarks (exclusive-next offsets).

### D9 — Snapshot Assembler

**Role:** Assemble the final `ContextSnapshot`:

* include OFP/IEG content when USED
* include provenance tokens always when USED
* include explicit reasons otherwise

### D10 — Commit Gate (one snapshot per WorkItem)

**Role:** Enforce “commit and freeze”:

* DF-D may retry within budgets (see DF-X policy), but once it returns a ContextSnapshot for this WorkItem, it is **final** (no further “try to get better features”).
  This prevents silent decision drift for the same input.

### D11 — DF-X Interface (budgets/circuits/telemetry)

**Role:** Apply dependency governance from DF-X:

* retry budgets, timeouts, circuit state, rate limits
* emit call outcome metrics (UNAVAILABLE rates, stale rates, basis violations, etc.)

---

## 3) DF-D internal joins (edges)

Call these **D-J#**:

* **D-J1:** Plan+Boundary → D1 (acquisition plan)
* **D-J2:** D1 → D2 (mask enforcement)
* **D-J3:** (D2 + event payload) → D3 (feature keys)
* **D-J4:** D2 → D4 (IEG call permitted?)
* **D-J5:** (D3 + D1) → D5 (OFP request build)
* **D-J6:** D5 → D6 (OFP call)
* **D-J7:** D6 → D7 (freshness/missingness normalize)
* **D-J8:** (D7 + D4 results) → D8 (basis fence check)
* **D-J9:** (D7 + D8 + D4) → D9 (snapshot assembly)
* **D-J10:** D9 → D10 (commit/freeze)
* **D-J11:** D10 → DF-E (ContextSnapshot)
* **D-J12:** (D4/D6/D8) → D11/DF-X (telemetry + budgets)

---

## 4) DF-D internal paths (production behaviors)

### D-P1 Full context (IEG + OFP)

* allow_ieg=true, OFP groups allowed
* IEG resolves canonical keys + graph_version
* OFP returns features + provenance
* basis fence passes
  → ContextSnapshot: `ieg=USED`, `ofp=USED`

### D-P2 OFP only

* allow_ieg=false **or** IEG unavailable
* DF-D derives reduced FeatureKeys (record limitation)
* OFP returns snapshot (may include graph_version only if OFP consults IEG internally)
  → ContextSnapshot: `ieg=FORBIDDEN/UNAVAILABLE`, `ofp=USED`

### D-P3 IEG only

* OFP forbidden by mask or not requested by plan
* IEG used for identity context
  → ContextSnapshot: `ieg=USED`, `ofp=FORBIDDEN/NOT_REQUESTED`

### D-P4 Partial OFP groups (mixed freshness / missing)

* OFP returns some groups stale, some not found
* DF-D marks each group state explicitly
  → DF-E later uses this to deterministically skip stage 2 under stale/missing rules

### D-P5 Basis violation

* OFP/IEG returns `input_basis/graph_version` indicating applied offsets beyond fence for the input’s partition
  → DF-D sets `BASIS_VIOLATION` and returns context as “not usable” (forces degraded execution or safe fallback later).

### D-P6 Dependency unavailable

* OFP timeout/unavailable
  → DF-D returns `UNAVAILABLE` with explicit reason; DF-E proceeds conservatively (often safe fallback)

---

## 5) DF-D internal loops (production cycles)

### D-L1 Bounded retry loop (dependency governance)

* For OFP/IEG calls, retry within DF-X budgets only
* retries do **not** slide `as_of_time_utc` (always event_time)
* once a snapshot is committed for a WorkItem, stop retrying (no “better snapshot” drift)

### D-L2 Keying loop (IEG helps key OFP)

* if allowed, DF-D may call IEG first to canonicalize keys
* if not allowed/unavailable, DF-D proceeds with reduced keys and records limitation

### D-L3 Fence verification loop

* every successful OFP/IEG response is verified against basis_fence
* on violation: mark unusable and stop trying to “get a compliant snapshot” unless the plan explicitly allows a retry attempt (still bounded)

---

## 6) DF-D drift bans (explicit non-joins)

* **No hidden “now”:** OFP calls must use `as_of_time_utc = event_time_utc`
* **No IEG calls when forbidden:** `allow_ieg=false` means *no bypass*
* **No feature group overreach:** must obey allowed_feature_groups allowlist
* **No “context used” without provenance tokens:** snapshot hash + input_basis (+ graph_version when used)
* **No mid-flight plan mutation:** DF-D follows the DecisionPlan snapshot; refresh applies only to future WorkItems (handled by DF-X).

---

## 7) Environment ladder knobs for DF-D

Semantics identical across envs; only operational envelope changes:

* timeouts/retry budgets/circuit thresholds
* cache TTLs for DL/Registry snapshots (still stamped + aged)
* observability verbosity (more in local/dev)
  But: as-of semantics, mask enforcement, and provenance capture must **not** change across local/dev/prod.

---

If you want the next node to illuminate, we should go to **DF-A (Intake & Normalization)** or **DF-E (Decision Execution)**. I’d recommend **DF-A next** (it’s short, but it locks trigger classification + WorkItem framing cleanly), then **DF-E** last (it’s where the “staged pipeline” lives).

---

Alright — **DF-A (Intake & Normalization)** is the “front porch” of DF: it turns **EB deliveries** into **canonical WorkItems** (or explicit skip records), enforces **trigger policy + loop prevention**, and owns the **per-partition serial lane** + **checkpoint gating** (wired to I-J8).

Below is DF-A’s machinery as an **internal network of sub-nodes** (still opaque inside each sub-node), plus DF-A’s internal joins/paths/loops.

---

## 0) DF-A v0 stance (designer-authoritative)

* DF-A **never decides**; it only frames work and enforces *input hygiene + trigger policy*.
* DF-A **does not call** DL/Registry/OFP/IEG/IG (no external joins). It’s pure intake + scheduling + checkpoint control.
* DF-A enforces **partition-serial processing**: **one in-flight WorkItem per partition**; next offset in that partition is not dispatched until current WorkItem is terminally complete via **I-J8**.
* DF-A may **skip** (checkpoint past) non-trigger or malformed inputs, but only with **explicit incident visibility** (metrics + correlation pointers). It must never silently drop.

---

## 1) DF-A boundary contract

### Inputs into DF-A

From EB (consumer delivery):

* `stream/topic`, `partition`, `offset`
* raw event bytes (expected to be CanonicalEventEnvelope JSON)
* optional broker metadata (arrival timestamp, headers)

### Outputs from DF-A

1. **To DF-B (I-J1):** `WorkItem`

   * validated envelope
   * `event_ref = (stream, partition, offset)`
   * extracted pins + trace fields
   * trigger classification (TRIGGER / NON_TRIGGER / IGNORE) + reason

2. **To DF-X (I-J9):** telemetry + backpressure signals

   * per-partition lag / in-flight count / queue depth
   * skip counts by reason
   * “blocked waiting on receipts” counts (from I-J8 feedback)

3. **To EB checkpointing:** commit decisions (advance offsets) only when allowed (see “Completion Gate” below)

4. **From DF-H via I-J8:** `CompletionRecord` for in-flight WorkItems (terminal receipts summary)

---

## 2) DF-A internal subnetworks (sub-nodes inside DF-A)

### A1 — Consumer Adapter

**Role:** Interface to EB consumer group.

* polls batches
* handles partition assignment/rebalance events
* exposes `(stream, partition, offset, bytes)` deliveries into DF-A

### A2 — Envelope Parser

**Role:** Decode raw bytes → structured envelope.

* parse JSON
* reject non-JSON / oversized / corrupted payloads

### A3 — Envelope Validator

**Role:** Assert “this is a CanonicalEventEnvelope enough for DF.”

* required fields exist: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
* `payload` exists (or is allowed empty)
* does **not** rewrite; only validates

### A4 — Pin & Trace Extractor

**Role:** Extract and normalize:

* ContextPins fields (if present)
* seed (if present)
* trace correlation fields (trace_id/span_id/producer/schema_version/parent_event_id)

> “Normalize” here means representation only (e.g., string form), not inventing missing pins.

### A5 — Trigger Classifier (Policy-owned)

**Role:** Decide TRIGGER vs NON_TRIGGER vs IGNORE.

* allowlist of decision-trigger event families
* hard ignore list (DF outputs, AL outcomes, DLA pointers, registry events, etc.) unless explicitly whitelisted
* emits `classification_reason` and stamps the trigger policy revision id used

### A6 — Partition Lane Scheduler

**Role:** Enforce **partition-serial** processing.

* maintains one lane per partition:

  * `in_flight[partition] = WorkItem?`
  * `queue[partition] = buffered deliveries`
* only dispatches next WorkItem when the partition is free

### A7 — WorkItem Builder

**Role:** Build the canonical `WorkItem` object.

* includes:

  * envelope
  * `event_ref`
  * extracted pins/trace
  * trigger classification + policy rev id
  * minimal ingest meta (received_at, attempt)

### A8 — Completion Tracker & Checkpointer

**Role:** Own “when can I commit offset?”

* registers in-flight WorkItems by `(partition, offset, event_id)`
* receives `CompletionRecord` from I-J8
* commits offsets only when:

  * NON_TRIGGER / IGNORE: immediately after classification
  * TRIGGER: only after I-J8 terminal completion

### A9 — Intake Incident Emitter

**Role:** Make “skips” and “bad inputs” visible.

* metrics + logs with:

  * `(stream,partition,offset)` pointer
  * raw payload digest (optional)
  * reason code
  * event_id if known
* feeds DF-X so Obs/Gov + DL can react if needed (e.g., quarantine/invalid spikes)

### AX — DF-X Interface Surface

Not a node by itself, but DF-A consumes:

* pause/resume/drain directives
* max inflight / throttle targets
* “publish health” signals that should cause intake throttling

---

## 3) DF-A internal joins (edges)

Call these **A-J#**:

* **A-J1:** A1 → A2 (raw delivery)
* **A-J2:** A2 → A3 (parsed envelope candidate)
* **A-J3:** A3 → A4 (validated envelope → pins/trace)
* **A-J4:** (A3/A4) → A5 (classify trigger)
* **A-J5:** A5 → A6 (enqueue into per-partition lane with classification)
* **A-J6:** A6 → A7 (dispatch build WorkItem if TRIGGER and lane free)
* **A-J7:** A7 → DF-B (I-J1 WorkItem)
* **A-J8:** A5 → A8 (NON_TRIGGER/IGNORE completion: checkpoint advance)
* **A-J9:** I-J8 CompletionRecord → A8 (TRIGGER completion: checkpoint advance)
* **A-J10:** (A2/A3/A5) → A9 (incidents/skip telemetry)
* **A-J11:** DF-X ↔ A6/A8 (pause/drain/backpressure controls)

---

## 4) DF-A internal paths (production behaviors)

### A-P1 Normal TRIGGER path

1. A1 polls event `(p,o)`
2. A2 parses → A3 validates
3. A4 extracts pins/trace
4. A5 classifies **TRIGGER**
5. A6 ensures partition lane is free
6. A7 builds WorkItem → emits to DF-B (I-J1)
7. A8 marks `(p,o)` as in-flight (no checkpoint yet)
8. Later: I-J8 completion arrives → A8 commits offset `o+1` (exclusive-next)

### A-P2 NON_TRIGGER path (intentional skip)

Same as A-P1 through A5, but classification is NON_TRIGGER/IGNORE:

* A8 immediately commits offset `o+1`
* A9 increments skip metrics with reason code
* No WorkItem enters DF-B

### A-P3 Malformed / invalid envelope path (rare but production-real)

* A2 fails parse OR A3 fails validation (missing required fields)
* **Pinned behavior:** DF-A does **not** stall the partition forever.

  * It records a high-severity intake incident (A9) with `(stream,partition,offset)` and a raw digest if possible.
  * It classifies as `IGNORE_INVALID_ENVELOPE` and commits offset `o+1`.

Why this is in-bounds: the event is already a durable fact on EB; DF cannot “quarantine” it out of existence. Stalling would deadlock the lane permanently; skipping with explicit incident visibility preserves liveness and forces remediation upstream.

### A-P4 Pause/drain path (operational control)

* DF-X sets `pause` or `drain_mode`
* A6 stops dispatching new WorkItems
* A8 continues to wait for I-J8 completions of in-flight items
* Once drained, A1 may stop polling or only buffer without dispatch (implementation choice)

---

## 5) DF-A internal loops (production cycles)

### A-L1 Poll → Buffer → Dispatch (per-partition lane loop)

* continuously poll batches
* buffer by partition
* dispatch only when partition lane free
  This is how we enforce **partition-serial** without relying on “best effort ordering.”

### A-L2 Completion → Checkpoint loop (the correctness lock)

* TRIGGER item enters lane at offset `o`
* checkpoint cannot advance past `o` until I-J8 says complete
* once complete, commit `o+1` and release lane

This loop is what prevents “we decided but never admitted outputs” drift.

### A-L3 Backpressure loop (publish health drives intake pacing)

* if DF-H/IG receipts stall, I-J8 completions slow down
* A8 sees growing blocked in-flight
* DF-X tells A6/A1 to throttle or pause
  This keeps DF stable under outages without changing semantics.

### A-L4 Rebalance loop (consumer group churn)

* partitions can be revoked/assigned
* DF-A must:

  * stop dispatching revoked partitions
  * allow in-flight work to finish or be retried after reassignment
* correctness preserved because replay + stable output IDs + receipt gating handle duplicates safely

---

## 6) DF-A “non-joins” (explicit drift bans)

* **No external joins** (no DL/Registry/OFP/IEG/IG calls).
* **No rewrite of envelope/pins/time**:

  * never invent `ts_utc`
  * never substitute arrival time for `ts_utc`
  * never fabricate ContextPins
* **No out-of-order within partition** (no “process offset o+1 while o is incomplete”).
* **No early checkpoint for TRIGGER items** (checkpoint is gated on I-J8 completion).
* **No silent skips** (every skip/malformed event must generate observable signals with pointers).

---

## 7) Environment ladder knobs for DF-A (deployment-facing, semantics-stable)

Semantics must be identical across local/dev/prod; only these knobs vary:

* poll batch size / max buffered per partition
* max in-flight partitions per instance (or per consumer group)
* incident telemetry verbosity
* pause/drain behavior defaults

But: **partition-serial + receipt-gated checkpointing** must not change across envs.

---

If you want to continue the illumination in the recommended order, the last “big” opaque node is **DF-E (Decision Execution)** — the staged decision pipeline itself — now fully constrained by everything we’ve pinned (boundary/plan/snapshot, output identity, provenance, publish receipts).

---

Alright — **DF-E (Decision Execution)** is the *compute core* of DF: it takes a frozen **DecisionBoundary + DecisionPlan + ContextSnapshot** and produces a deterministic **DecisionDraft** (outcome + action recommendations + explainability hooks) with **no external calls** and **no hidden time**.

Everything that makes DF “production safe” upstream (boundary/plan/snapshot) exists so DF-E can be **pure**, **replay-stable**, and **auditable**.

---

## 0) DF-E boundary contract

### Inputs (frozen upstream)

* **DecisionBoundary**: `event_time_utc = ts_utc`, basis_ref `(stream,partition,offset)` + `input_event_id`, pins/scope seed, basis fence. 
* **DecisionPlan**: DL posture snapshot (mode + mask identity), active bundle ref, context contract (required/optional/forbidden), policy rev set.  
* **ContextSnapshot**: optional IEG context + `graph_version`, optional OFP snapshot + `feature_snapshot_hash` + `input_basis` + freshness + versions + explicit “not used” reasons.

### Output (to DF-F)

**DecisionDraft** (still internal, no stable IDs yet):

* `draft_outcome` (canonical enum)
* `intent_candidates[]` (action_domain/type + target hints + parameters; deterministic)
* `decision_signals` (scores/rules/features used—opaque but stable)
* `stage_report` (what ran / what was skipped + why)
* `constraint_notes` (missing required context, mask forbiddance, basis violation, etc.)

**DF-E does not** assign `event_id`s or idempotency keys — DF-F does that.

---

## 1) DF-E internal subnetworks (sub-nodes inside DF-E)

### E1 — Program Resolver (bundle → decision program)

**Role:** Pick the “DecisionProgram” for this `decision_scope` from the active bundle.

* maps `decision_scope` → a deterministic program entry (rules + model(s) + thresholds + action templates)
* validates program is compatible with plan’s allowed capabilities

### E2 — Preconditions & Contract Checker

**Role:** Decide whether DF-E can execute “normal” logic or must go constrained.

* checks **context contract** from the plan:

  * required context present/usable?
  * required feature groups present and not stale beyond tolerance?
  * basis violations flagged?
* produces `exec_mode`:

  * `FULL` / `DEGRADED` / `CONSTRAINED_SAFE`

### E3 — Context Adapter (snapshot → canonical inputs)

**Role:** Convert event payload + context snapshot into canonical internal inputs:

* canonical entity references (if IEG used)
* feature vector(s) (if OFP used)
* missingness map (per group/feature)
* explicit “context limitations” flags (e.g., IEG forbidden)

### E4 — Rule Stage Engine

**Role:** Deterministic rules (no randomness):

* evaluates rule predicates against payload + adapted context
* outputs:

  * hard blocks/overrides (e.g., “must step-up”)
  * rule scores / reason codes

### E5 — Model Stage Engine (local inference only)

**Role:** Run 0..N model scorers from the active bundle **only if allowed by plan + exec_mode**.

* produces:

  * scores (quantized deterministically)
  * uncertainty/bounds (optional)
  * model reason codes (opaque, but stable)

> Pin: model inference must be deterministic for the same inputs (no dropout, no nondeterministic threads affecting outputs). If necessary, DF-E quantizes/rounds scores to a stable representation before output.

### E6 — Policy Combiner / Decision Synthesizer

**Role:** Combine rule signals + model signals + policy thresholds into a single `draft_outcome`.

* applies deterministic precedence:

  * mask/contract constraints > hard rules > model policy > default
* produces a `decision_trace` (minimal, stable explanation hooks)

### E7 — Action Recommendation Generator

**Role:** Convert outcome + signals into **intent candidates** (not yet final actions):

* uses program action templates per outcome
* emits candidates with:

  * `action_domain`, `action_type`
  * target hints (so DF-F can compute action_key deterministically)
  * parameters (deterministic, canonicalized)

### E8 — Safe Fallback Engine

**Role:** When `exec_mode=CONSTRAINED_SAFE`, force safe posture:

* outputs safe outcome (e.g., review/step-up/hold) according to policy
* emits safe intent candidates only (consistent with plan constraints)
* records “why constrained” in constraint notes

### E9 — Determinism Guard & Canonicalizer

**Role:** Ensure DF-E outputs are replay-stable:

* canonical ordering for any lists/maps in DecisionDraft
* stable numeric formatting/quantization
* stable “stage_report” ordering

### E10 — Draft Assembler

**Role:** Assemble the final DecisionDraft:

* outcome
* intent_candidates[]
* stage_report
* decision_signals summary
* constraint_notes / explainability hooks

---

## 2) DF-E internal joins (edges)

Call these **E-J#**:

* **E-J1:** (Boundary + Plan) → **E1** (resolve DecisionProgram)
* **E-J2:** (Boundary + Plan + ContextSnapshot) → **E2** (exec_mode + gating)
* **E-J3:** (Payload + ContextSnapshot) → **E3** (canonical inputs + missingness)
* **E-J4:** (E3 inputs + Program) → **E4** (rule signals)
* **E-J5:** (E3 inputs + Program + exec_mode) → **E5** (model scores)
* **E-J6:** (E4 + E5 + Plan) → **E6** (draft_outcome + decision_trace)
* **E-J7:** (E6 + Program + Plan) → **E7** (intent_candidates)
* **E-J8:** (E2 gating failures) → **E8** (safe outcome + safe intents)
* **E-J9:** (all outputs) → **E9** (canonicalize/quantize)
* **E-J10:** **E9** → **E10** → DF-F (DecisionDraft)

---

## 3) DF-E internal paths (production behaviors)

### E-P1 Full execution path (normal)

`E1 → E2(exec_mode=FULL) → E3 → E4 → E5 → E6 → E7 → E9 → E10`

* rules + models run
* outcome computed
* intent candidates emitted

### E-P2 Rules-only path

When plan/mask forbids model stage or OFP missing but still enough for rules:
`E1 → E2(exec_mode=DEGRADED) → E3 → E4 → (skip E5) → E6 → E7 → E9 → E10`

* model stage skipped with explicit reason in stage_report

### E-P3 Constrained safe fallback path

When required context is missing/invalid or basis violation occurs:
`E1 → E2(exec_mode=CONSTRAINED_SAFE) → E8 → E9 → E10`

* no rule/model stages run (or only minimal “always safe” checks)
* safe outcome + safe intents, plus explicit constraint notes

### E-P4 Degraded partial-context path

When some optional groups missing/stale but policy allows degraded execution:
`E1 → E2(exec_mode=DEGRADED) → E3(partial) → E4/E5(as allowed) → E6 → E7 → E9 → E10`

* stage_report makes missingness visible (so audit/offline parity remain honest)

---

## 4) DF-E internal loops (production cycles)

### E-L1 Stage gating loop

DF-E repeatedly applies deterministic “can I run this stage?” checks:

* plan forbids → skip
* required inputs missing → fall back
* optional inputs missing → degraded stage variant
  This is how DF-E stays consistent with I-P3 vs I-P4 without ad-hoc behavior.

### E-L2 Consistency loop (outcome ↔ constraints)

After synthesizing an outcome, DF-E verifies it’s coherent with allowed action posture:

* if outcome implies forbidden posture under plan, DF-E downgrades to a coherent safe outcome (and records why)
  (DF-F still acts as the final clamp, but DF-E shouldn’t emit obviously incoherent drafts.)

### E-L3 Determinism loop

Before emitting DecisionDraft:

* canonicalize ordering
* quantize numeric outputs
* ensure “explainability hooks” are deterministic and stable under replay

---

## 5) DF-E drift bans (explicit non-joins)

* **No external calls** (no DL/Registry/OFP/IEG/IG) — DF-E consumes frozen inputs only.
* **No hidden “now”** (no wall-clock in logic; only boundary time from `ts_utc` is meaningful). 
* **No randomness** (or if any internal RNG exists, it must be deterministically derived from the boundary and pinned).
* **No mid-flight plan mutation** (plan snapshot is immutable for the WorkItem).
* **No output identity minting** (IDs/keys belong to DF-F).

---

## 6) Environment ladder notes for DF-E

DF-E semantics must be identical across local/dev/prod **given the same bundle + plan + snapshot**. Differences across envs should come only from:

* which bundle is active (via Registry promotion),
* operational resources/latency (not semantics),
* observability verbosity.

---

If you want the *next* slice, the most leverage inside DF-E is to open **E2 (Preconditions & Contract Checker)** and **E6 (Policy Combiner)** just enough to pin:

* the exact rule for “required missing ⇒ forced safe fallback” vs “optional missing ⇒ degraded allowed,” and
* the deterministic precedence order (mask/contract > rules > models > default).

---

Got it — this is the **DF-X Rails focused pass**: the machinery that makes DF **production-operable** (pacing, budgets, caching, observability, governance stamping) **without changing DF semantics**.

I’ll keep DF-X as an internal network of **opaque subnodes** with clear joins/loops, aligned to the platform laws (profiles, explicit governance, IG/EB truth boundary).  

---

## 0) DF-X prime law

**DF-X may change *how fast* DF operates, not *what DF decides*.**
Semantic authority remains:

* **DL** for constraints (mask), and
* **Registry** for active bundle selection,
* with **DecisionBoundary** time/basis pinned by `ts_utc` + offsets. 

So DF-X can:

* throttle/pause/drain,
* set retry/timeout/circuit budgets,
* cache *snapshots* of DL/Registry and stamp snapshot IDs/ages,
* emit metrics/incidents and corridor signals.

DF-X cannot:

* override DL mask,
* override Registry selection,
* mutate an in-flight WorkItem plan,
* rewrite payloads/pins/timestamps,
* bypass IG/EB semantics.

---

## 1) DF-X subnodes (internal subnetworks inside DF-X)

### X1 — Profile Loader and Revision Tracker

**Role:** Load **wiring profile** vs **policy profile** and expose revision IDs.

* wiring: endpoints, pool sizes, timeouts
* policy: trigger policy rev, compat policy rev, fail-safe policy rev, staleness tolerance revs, publish semantics revs
  Policy revisions are outcome-affecting and must be stampable. 

### X2 — WorkItem Governance Stamp Service

**Role:** Provide **stampable identifiers** used across DF:

* `policy_revision_set_id`
* “profile revision ids”
  This is what DF-C and DF-G embed in plan/provenance.

### X3 — DL Snapshot Manager

**Role:** Maintain DL posture snapshots:

* pull/push ingestion
* snapshot identity + decided_at + age
* staleness classification (policy-owned)
  Fail-closed posture if snapshot unavailable/invalid. 

### X4 — Registry Snapshot Manager

**Role:** Maintain Registry resolution snapshots:

* per scope cache (optional)
* lifecycle event warmup (optional)
* returns `ActiveBundleRef` + age + any lifecycle pointer
  Deterministic resolution remains authoritative; cache is optimization only. 

### X5 — Dependency Governor

**Role:** Own call budgets for OFP/IEG/IG (and optionally DL/Registry calls):

* timeouts, retry budgets, backoff class
* concurrency limits / rate limits
* circuit state (open/half-open/closed)
  This node never changes “allowed”; it only controls “attempt.” 

### X6 — Backpressure and Lane Controller

**Role:** Convert health signals into **IntakeControl**:

* max inflight per partition / per instance
* pause/resume
* drain mode
  It couples directly to DF-A lane scheduling and the receipt-gated completion story.

### X7 — Publish Health Monitor

**Role:** Monitor DF-H’s publish/receipt pipeline:

* receipt latency, timeout rates, blocked sessions
* ADMIT/DUPLICATE/QUARANTINE distributions
  Feeds X6 backpressure decisions and incident triggers.

### X8 — Observability and Correlation Hub

**Role:** Standardize:

* correlation keys (input basis pointer, decision_event_id, intent ids/keys)
* trace propagation
* golden metrics for DF health
  This is “visibility rails,” not semantics. 

### X9 — Incident Router

**Role:** Turn structured anomalies into operator-visible incidents:

* quarantine spikes
* duplicate-mismatch (if digests don’t match)
* blocked publish SLO breach
* missing Tier-0 anchors (bug)
  Optionally emits corridor signals to Obs/Gov.

### X10 — Refresh Scheduler

**Role:** Periodic refresh loop owner for:

* DL snapshots
* registry warm cache
* dependency health sampling
* profile rev refresh
  Crucially: refresh affects **future WorkItems only**.

---

## 2) DF-X interfaces to DF nodes (the “rails joins” we already pinned)

These are the four rails joins you asked us to illuminate earlier, now grounded in DF-X internals:

### I-J9 DF-X ↔ DF-A (Intake control)

* **DF-A → DF-X:** queue depth, lag, blocked-on-receipts counts
* **DF-X → DF-A:** pause/resume/drain, max inflight, throttle targets
  (Produced by X6 using signals from X7/X8.)

### I-J10 DF-X ↔ DF-C (Policy snapshots)

* **DF-X → DF-C:** `{dl_snapshot, registry_snapshot, policy_revision_set}`
* **DF-C → DF-X:** plan usage record (plan_id, snapshot ids, reasons)
  (Driven by X3+X4+X1/X2.)

### I-J11 DF-X ↔ DF-D (Dependency governance)

* **DF-X → DF-D:** call policies (budgets/circuits + allowed groups list passed through from plan)
* **DF-D → DF-X:** call outcomes (UNAVAILABLE/STALE/BASIS_VIOLATION rates, latency)
  (Driven by X5.)

### I-J12 DF-X ↔ DF-H (Publish governance)

* **DF-X → DF-H:** publish budgets/circuit + drain/pause + telemetry requirements
* **DF-H → DF-X:** receipt outcomes + blocked sessions + quarantine reasons
  (Driven by X5+X7+X6+X9.)

---

## 3) DF-X internal paths (how DF-X operates in production)

### X-P1 Boot path

1. X1 loads wiring+policy profiles
2. X2 stamps current policy revision set id
3. X10 starts refresh loops (DL/Registry/health sampling)
4. X6 starts with safe default throttle (low inflight until publish health is known)

### X-P2 Steady-state path (per WorkItem)

* DF-C requests snapshots → X3/X4 provide snapshot IDs + ages + policy rev set
* DF-D requests budgets → X5 provides call policy
* DF-H requests publish budgets → X5 provides publish policy
* X8 collects correlation + metrics for this WorkItem

### X-P3 Publish stall path (IG slow/unreachable)

* X7 detects receipt lag/blocked sessions
* X6 pushes `pause` or sharply reduces inflight to DF-A
* X9 raises incident if thresholds exceed corridor
  Semantics unchanged; only pacing shifts.

### X-P4 Quarantine spike path

* X7 observes QUARANTINE uptick (by reason code)
* X9 raises incident + emits corridor signal to Obs/Gov (optional)
* X6 may apply throttle to reduce damage while operators remediate
  Quarantine remains terminal and visible (no bypass).

### X-P5 DL/Registry outage path (fail-closed)

* X3 can’t refresh DL → marks snapshot stale/unavailable
* DF-C sees that and forces safe fallback plans (fail-closed)
* X9 emits “control surface degraded” incident
  DF still runs, but constrained (per pinned degrade behavior). 

---

## 4) DF-X loops (the production cycles that must not drift)

### X-L1 Refresh loop

X10 periodically refreshes:

* DL snapshot (X3)
* Registry warm cache (X4)
* dependency health/circuits (X5)
* profile revisions (X1/X2)
  **Pin:** these updates apply only to **future WorkItems**; DF-C plan snapshots remain immutable once emitted.

### X-L2 Circuit loop

X5 updates circuit states from call outcomes:

* too many failures → open circuit → stop calling temporarily
* half-open probing on schedule
  This affects attempt behavior, not semantics.

### X-L3 Backpressure loop

X7 → X6 → DF-A:

* publish health degrades → throttle/pause intake
* publish recovers → resume intake
  Preserves receipt-gated completion; prevents memory blow-ups.

### X-L4 Governance corridor loop

X8/X9 → (optional) Obs/Gov → DL:

* repeated incidents (audit gaps, quarantine spikes, staleness) can trigger DL posture changes
  DF then obeys mask; DF-X never directly changes semantics.

### X-L5 Promotion loop (env ladder)

X1/X2 track profile revisions; Registry changes bundles via lifecycle events.
DF-X ensures **code artifact stays same**, behavior changes are explainable as:
`code_build + policy_profile_rev + dl_snapshot_id + bundle_ref` 

---

## 5) DF-X “non-joins” and drift bans (explicit)

* **No mid-flight plan mutation:** DF-X must not swap bundles or degrade posture for an in-flight WorkItem (only future ones).
* **No semantic overrides:** DF-X cannot “decide” or rewrite outcomes; only DL/Registry do.
* **No hidden defaults:** DF-X must not introduce hidden “now” for as-of; that is pinned by DecisionBoundary and enforced in DF-D.
* **No bypasses:** DF-X cannot create alternate output sinks; DF-H remains the only publish path (IG semantics).
* **No env code forks:** environment differences are profile values, not code branches. 

---

## 6) Environment ladder knobs for DF-X (what Codex will need later)

These are the **allowed** env-profile differences DF-X owns, without changing semantics:

### Wiring knobs (safe to differ)

* timeouts, retry budgets, circuit thresholds
* concurrency/inflight caps
* cache sizes/TTLs
* trace sampling rates, metric export endpoints
* drain/pause defaults

### Policy knobs (governed; must be stamped)

* DL corridor thresholds (what triggers degrade)
* registry compatibility strictness / “last known good” allowance (if ever allowed)
* staleness tolerances for feature groups
* incident thresholds that trigger corridor signals
  All must be versioned and appear in plan/provenance stamps. 

---

If you want to sanity-check that DF-X doesn’t “accidentally become a decision service,” the quick test is:

> Can you replay a WorkItem later and get the same DecisionPlan/DecisionDraft given the same Boundary + snapshots?
> If DF-X could change the answer mid-flight, we violated immutability.

Next move is yours: we can either (a) do a **tight integration pass** (“for each node, what DF-X knobs touch it?”), or (b) start tightening one subnode inside DF-X (usually **X5 Dependency Governor** or **X6 Backpressure Controller**) if you want Codex-ready clarity without writing specs.

---

## USER: PAUSE FOR REFLECTION

Yep — quick pause, but with something concrete you can hold onto.

## What we’ve actually built (at a glance)

We started with DF as a vertex in the platform graph, then revealed its **internal graph** as a pipeline of **opaque subnetworks** plus a **cross-cutting rails mesh**:

**DF-A → DF-B → DF-C → DF-D → DF-E → DF-F → DF-G → DF-H → (I-J8 back to DF-A)**
with **DF-X** touching A/C/D/H (pacing, snapshots, budgets, observability) without changing semantics.

That “A→…→H + receipt-gated completion” is the spine that keeps:

* **replay safe** (stable IDs + dedupe),
* **auditable** (by-ref provenance),
* **operable** (backpressure + drain),
* **truth-boundary clean** (IG is the only front door; EB is the fact log).

## Why it feels complex

Because DF isn’t “a model service.” It’s a **truth production service** in a closed-world platform:

* it must behave correctly under **at-least-once delivery**,
* under **dependency degradation** (OFP/IEG/DL/Registry),
* under **policy evolution** (Registry activation + DL masks),
* while remaining **replay-defensible** (offset/watermark basis tokens),
* and leaving an **audit-complete trail** (DLA won’t accept half-truths).

Those constraints create “necessary complexity,” not optional ornament.

## The three invariants that make the whole thing mentally manageable

If you remember only these, you won’t drift:

1. **One WorkItem → one immutable plan snapshot → one frozen context snapshot → one stable output set.**
   (No mid-flight mutation; updates affect future WorkItems only.)

2. **Outputs become facts only through IG receipts; completion is receipt-gated.**
   (No receipt, not done. DUPLICATE is success. QUARANTINE is terminal + incident.)

3. **Every decision is explainable by reference:**
   input basis ref + degrade snapshot + bundle ref + feature snapshot hash/basis + graph_version (if used).
   (No hidden “now,” no invented context.)

## What this pause tells us about next steps

We’ve now made the vertex “production-shaped.” From here, going deeper should mostly be:

* tightening a few “recipes” (scope mapping, action_domain/action_key taxonomy, provenance minimum set), and
* stress-testing with edge cases (replay, publish stall, staleness, quarantine spikes).

No new vertices, no new joins — just increasing resolution inside the boxes we already defined.

---