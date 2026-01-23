# Model Policy/Registry Design Authority

This file is a rough collection of design or brainstorm notes for the Model Policy/Registry. It views the whole platform as a network and expands open the model policy/registry's position in this network and illuminates it.

---

Cool — we’ll keep MPR’s internals as a black box for now and **design its role/behavior at the network level** (what it must do, how it must behave at joins, what it must emit, and how other components must be able to rely on it).

## 0) MPR’s job in the platform graph (what it *is*)

MPR is the platform’s **controlled source of deployable truth**: it takes **bundles + evidence** from learning, governs their lifecycle (publish → approve → promote/rollback/retire), and gives Decision Fabric a **deterministic, compatibility-safe** answer to “what should I run for this decision right now?”.   

### Authority boundaries (hard)

MPR **owns**:

* the meaning of **ACTIVE** (and history of how it changed) 
* the deterministic **resolution rules** per scope 
* the **compatibility gate** at resolution (never return an ACTIVE-but-incompatible bundle) 
* the **registry_event** audit fact for every governed change 

MPR **does not own**:

* training/eval computation (Model Factory owns that) 
* feature computation/availability (OFP owns feature snapshots + provenance) 
* degrade posture (DL owns the capabilities mask; DF must obey it) 

## 1) MPR’s outer-network placement (who it talks to, and why)

```
Offline Shadow -> Model Factory --(J16 publish bundle+evidence)-->  MPR  --(J10 resolve active)-->  Decision Fabric
                                            ^                     |
                                            |                     v
                                  (governed lifecycle actions)   registry_event stream + audit query
                                            |                     |
                                      Run/Operate + Gov tools   Observability/Audit sinks
```

* **J16 (MF → MPR):** bundles are *packages* (identity + immutable artifact refs/digests + DatasetManifest lineage + eval evidence + PASS receipts where required + compatibility metadata).  
* **J10 (MPR → DF):** deterministic ActiveBundleRef; DF records it in decision provenance; compatibility enforced at the join, including degrade mask constraints.  
* **Deployment posture:** MPR is an **always-on control-plane service** (low QPS but authoritative). 

## 2) The boundary ports (MPR as a black box with explicit handshakes)

### Port P1 — PublishBundle (Model Factory → MPR)  [J16]

**Purpose:** register a candidate deployable bundle *by-ref*, with enough evidence to later govern promotion.

**What must cross (minimum truths):**

* **Bundle identity** (stable id + version)
* **Immutable refs + digests** to artifacts (weights/rules/thresholds/metadata) 
* **Training lineage**: which **DatasetManifests** were used (immutable inputs) 
* **Evaluation evidence refs**
* **PASS/FAIL receipts where governance posture requires** (platform-wide “No PASS → no read”, and this rail explicitly bites learning/bundles) 
* **Compatibility contract** (feature group versions expected + required capabilities) 

**Hard behaviors:**

* **Idempotent publish:** same `(bundle_id, version)` again ⇒ return “already registered” (no duplicate truth).
* **Immutability:** publish does **not** allow edits to artifact refs/digests/compatibility; “fix” = new version. (This is how you keep audit + reproducibility coherent.) 
* **Publish ≠ Active:** a bundle can exist forever as non-active; activation is governed. 

**Failure posture (fail-closed):**

* missing required fields/evidence ⇒ reject
* digest mismatch / ref integrity failure ⇒ reject (inadmissible by-ref truth posture) 
* missing compatibility metadata ⇒ reject as “not a deployable artifact” 

---

### Port P2 — GovernLifecycle (Run/Operate / Gov actor / automation → MPR)

**Purpose:** controlled changes to deployable truth (approve/promote/rollback/retire).

**Allowed actions (minimum set):**

* approve
* promote (make ACTIVE)
* rollback (switch ACTIVE to a prior approved candidate)
* retire (remove from eligible set)

**Hard behaviors:**

* **Every action emits an auditable registry_event** with the minimum pinned fields:
  `registry_event = {registry_event_id, actor_principal, governance_action=publish|approve|promote|rollback|retire, from_state->to_state, bundle_id + immutable refs/digests, scope, approval_policy_rev, reason, evidence_refs}` 
* **One ACTIVE per scope** (see “ScopeKey” below). If promote would violate it, it must fail or deterministically supersede via an explicit transition (never implicit). 
* **Promotion requires evidence posture** (PASS where required; compatibility metadata required).  
* **Idempotent transitions:** repeating the same transition should be a no-op (or return the already-achieved state) — because the platform assumes retries. 

---

### Port P3 — ResolveActive (Decision Fabric → MPR)  [J10]

**Purpose:** DF asks: “what bundle am I allowed to execute for this decision right now?”

**Inputs MPR must consider (at minimum):**

* `scope_key`
* **degrade capabilities mask** (hard constraints; if a capability is off, DF behaves as if that model/tool doesn’t exist) 
* enough “platform compatibility basis” to check required feature group versions (details pinned below)

**Outputs:**

* **ActiveBundleRef**: bundle id + immutable artifact refs/digests + compatibility metadata 
* plus a **resolution token** (monotonic “what registry event made this true”) so DF can record/prove what it used.

**Hard behaviors:**

* **Deterministic:** no “latest”; same inputs ⇒ same answer. 
* **Compatibility-aware:** MPR must not return an ACTIVE bundle that cannot be satisfied by required feature versions or is disallowed by the degrade mask; if incompatible, fail closed or route only to an explicitly-defined safe fallback.  
* DF must record the resolved bundle ref in provenance (replay/explainability).  

---

### Port P4 — EmitRegistryEvents (MPR → audit/obs consumers)

**Purpose:** make promotions/rollbacks explainable and operable (and allow DF to cache safely).

Pinned: MPR “emits registry events.” 
Pinned: those registry_events have a required minimal fact shape. 

**Authoritative stance (designer pin):**

* MPR must provide a **monotonic event stream** of `registry_event`s that can be consumed by:

  * audit writers / observability
  * DF (optional) for cache invalidation
* Transport is flexible (pull cursor, push stream, etc.), but the *semantic* must exist.

---

## 3) The three “outer” decisions I’m pinning now (because everything depends on them)

### Pin MPR-D1 — ScopeKey (what “one ACTIVE per scope” means)

For v0, **scope is deliberately minimal** to avoid combinatorial explosion:

**ScopeKey = `{ environment, bundle_slot, tenant_id? }`**

* `environment`: local/dev/prod (always present; env ladder must not change semantics) 
* `bundle_slot`: the DF execution slot name (e.g., `"fraud_primary_model"`, `"fraud_policy_bundle"`)
* `tenant_id`: optional (only if you truly run multi-tenant)

Rule: **at most one ACTIVE bundle per ScopeKey**. 

This keeps “routing complexity” out of the registry. If DF later needs corridor-based A/B routing, that becomes a *policy inside the bundle* or a v1 scope expansion—never an accidental v0 drift.

### Pin MPR-D2 — Compatibility contract shape (minimum)

Every bundle must declare compatibility at least across:

* **Feature group versions required** (anti training/serving drift) 
* **Required capabilities** (so degrade can disable bundles safely) 
* **Input contract version** (conceptual DF↔bundle interface version; starts as implicit v0 but must be recordable) 

Promotion without this metadata is invalid. 

### Pin MPR-D3 — Fail-closed posture at resolution

If the “active” bundle is incompatible with:

* the current feature-definition basis, or
* the degrade mask,
  **MPR resolution must not return it**. It returns a typed failure (or an explicitly pinned safe fallback), and DF proceeds with safe posture + records why. 

## 4) How this stays production-real (without designing internals yet)

### “Low-QPS control plane” vs “hot-path DF”

MPR is authoritative but **should not be on the critical per-event latency path** unless you choose to be. The design supports both:

* **Simple mode:** DF calls ResolveActive for each decision (works, but higher coupling).
* **Production-typical mode:** DF caches by `scope_key`, and MPR’s **registry_event stream** invalidates/refreshes the cache. This aligns with MPR being always-on, low-QPS control plane. 

### CI/CD lane alignment

This is explicitly a third promotion lane:

* Model Factory publishes bundles; Registry governs activation; DF resolves deterministically and records bundle ref. 

So the “what changed?” story is always answerable:

* **A registry_event changed ACTIVE**
* decisions cite the ActiveBundleRef that resulted  

## 5) Two end-to-end interaction sequences (outer-network view)

### Sequence A — Normal rollout

1. Offline Shadow produces DatasetManifests → MF trains/evals on those manifests 
2. MF → MPR PublishBundle (bundle package + evidence + compatibility) 
3. Gov actor → MPR Approve, then Promote(scope) → emits registry_event 
4. DF → MPR ResolveActive(scope, degrade_mask) → ActiveBundleRef 
5. DF records ActiveBundleRef in provenance 

### Sequence B — Incident rollback

1. Gov actor/automation triggers Rollback(scope → prior approved)
2. MPR appends registry_event(rollback) with reason/evidence/policy_rev 
3. DF resolves again (or cache invalidated) → previous ActiveBundleRef
4. Decisions now cite the rolled-back bundle ref (explainability preserved) 

---

Yes — there’s a **small set of MPR primitives** worth pinning *before* we deep-dive joins, because they determine what “Publish”, “ACTIVE”, “Resolve”, and “Compatibility” even mean (and therefore what must cross boundaries).

Below are the pins I’d lock now (v0 designer-authoritative), with why each matters.

---

## Pins to lock before joins

### 1) Meaning of the core words (so nobody smuggles semantics)

Pin these as **global meanings** (stable across envs):

* **PUBLISH** = “register an immutable candidate bundle (by-ref)”; **never implies ACTIVE**. 
* **ACTIVE** = “the single deployable truth DF is allowed to execute for a scope,” and only Registry can change it. 
* **ROLLBACK / RETIRE** = explicit governed lifecycle mutations (auditable facts), not silent edits.
* **CORRECTION** = new records/versions that supersede; no silent mutation. 

Why this must be pinned: it prevents “publish = deploy” drift and keeps the platform’s “governed change is explicit” rail intact. 

---

### 2) ScopeKey (what “one ACTIVE” means)

Pin: **one ACTIVE bundle per ScopeKey**. 

My v0 ScopeKey pin (minimal + drift-resistant):

* `environment` (local/dev/prod) — MUST be part of scope (env ladder semantics).
* `bundle_slot` (the DF execution slot / model_family+policy_name abstraction)
* optional `tenant_id` (only if multi-tenant is real in your platform)

Why now: it defines how DF queries resolution and how promotion/rollback conflicts are detected.

---

### 3) Bundle identity + immutability posture (what a “bundle” *is*)

Pin: **Bundle = immutable package of deployable decision logic**:

* `bundle_id + bundle_version` identify the bundle
* bundle contents are **by-ref artifact pointers + digests** (MPR does not store the bytes; object store does) 
* once published, the bundle’s artifact refs/digests/compat metadata **do not change**; corrections are new versions (supersedes chain).

Why now: this determines publish idempotency, auditability, and how DF can prove what it executed.

---

### 4) Evidence posture (what must be true before ACTIVE is allowed)

Pin: **ACTIVE is evidence-gated**, and evidence is carried **by-ref** and recorded in registry events.

Concrete v0 pin:

* **Publish may accept a bundle as “registered” even if not promotable yet** (so you can stage candidates),
* but **Promote/Activate requires required evidence**, including GateReceipt PASS *where required by policy*.

This aligns with the platform-wide “No PASS → no read” discipline, expressed here as “No PASS → no ACTIVE.”

---

### 5) Compatibility contract (minimum fields bundles must declare)

This one is *already pinned by the platform*; we just make it explicit as an MPR primitive:

Pin: every bundle must declare compatibility across:

* **Feature group dependencies + versions** (anti training/serving drift)
* **Required capabilities** (so degrade can disable safely)
* **Input contract version** (DF↔bundle interface version, even if “v0 implicit” today) 

Promotion without this metadata is not a valid deployable artifact. 

---

### 6) Resolution semantics (the deterministic function)

Pin these now (because they determine DF↔MPR inputs/outputs):

* **Never “latest.”** Resolution is deterministic + compatibility-aware.
* **Fail-closed (or explicit safe fallback)** when incompatible; never silently proceed.
* Resolution returns **one ActiveBundleRef + a monotonic “why this is true” token** (registry event seq/id) so DF can cache and still be correct.

This is exactly Rail R11 / SV-R.2, so it’s non-negotiable.

---

### 7) RegistryEvent is the authoritative audit fact

Pin: **every lifecycle mutation appends a `registry_event`** with the minimum fields already pinned in the blueprint.

This is what makes “deployable truth changes are explainable” real, and it supports DF cache invalidation safely.

---

### 8) Privilege tiers (what kinds of callers exist)

Pin the three classes (authority boundary):

1. **Resolve/Read** (DF service principal)
2. **Publish** (Model Factory)
3. **Lifecycle mutation** (privileged actor / controlled automation)

And every privileged change is attributable + reasoned.

(Exact auth tech stays loose; posture is pinned.)

---

### 9) “Rejection/quarantine is first-class” for bundle intake

Platform rail says: boundaries don’t silently drop; they produce debuggable outcomes. 

Pin for MPR: if a publish/promotion request is rejected, MPR produces a **durable rejection record** (or equivalent evidence pointer) with reason codes and refs to the submitted bundle/evidence so it can be audited/debugged (not just a transient HTTP error).

---

### 10) Environment ladder invariance (registry meaning can’t change per env)

Pin: Registry semantics are identical in local/dev/prod; environments only change operational envelope + stricter policies.

This matters because “ACTIVE in dev” and “ACTIVE in prod” must be the same *kind* of truth, just in different scopes (hence ScopeKey includes `environment`).

---

## Net: the minimal “pin set” I recommend locking now

If we lock only **five**, lock these (they force everything else cleanly):

1. ScopeKey + “one ACTIVE per scope” 
2. Bundle immutability + by-ref + digests
3. Evidence-gated promotion (“no PASS → no ACTIVE”)
4. Compatibility contract minimums 
5. Deterministic fail-closed resolution

Once those are pinned, the joins become much easier to design without hidden assumptions.

---

Absolutely — if we keep **MPR opaque**, then “all joins/paths/loops” means: **every boundary interaction that must exist (pinned), every production-typical one that may exist (allowed), and every closed feedback cycle where MPR is a vertex in the loop**.

Below is the **complete outer-network picture around MPR** for a production-ready platform, grounded in your authoritative blueprint + deployment notes.

---

## 1) The full join surface of MPR (vertex opaque)

### A) Pinned joins (must exist)

**J16 — Model Factory → MPR (Publish bundle + evidence)**
Publish crosses as a *package* (identity, immutable refs/digests, DatasetManifest lineage, eval evidence, PASS/FAIL receipts where required, and compatibility metadata). 

**J10 — Decision Fabric ↔ MPR (Resolve active bundle)**
DF asks; MPR returns a deterministic **ActiveBundleRef**; DF must record it in decision provenance; compatibility is enforced at the join (fail closed / safe fallback, never “half-compatible proceed”).

**Lifecycle mutation (Privileged actor/controlled automation → MPR)**
Approve/promote/rollback/retire are privileged and auditable; publication is not activation; every mutation emits an append-only `registry_event`.

**RegistryEvent emission (MPR → Obs/Gov durable facts)**
Registry is a choke point like IG/AL, and must emit a durable policy fact:
`registry_event = {actor_principal, governance_action, from→to, bundle refs/digests, scope, approval_policy_rev, reason, evidence_refs…}`

---

### B) Production substrate joins (required for “production-ready”, even if not modeled as “components”)

These are part of the production platform’s *stateful substrate map*:

**MPR ↔ Registry DB (authoritative)**
Lifecycle truth + resolution state lives here.

**MPR ↔ Object store (bundle blobs + evidence pointers)**
Bundle artifacts and evidence live by-ref in object storage; registry stores refs/digests.

**MPR ↔ Policy profile/config artifact (approval_policy_rev + registry rules)**
Policy config is outcome-affecting, versioned, auditable; registry events cite which approval policy revision was used.

---

### C) Allowed / production-typical joins (optional but realistic)

**MPR → EB “control facts” topic (broadcast registry_event for caching/invalidation)**
Your deployment notes explicitly allow a low-volume control stream carrying governance facts incl. registry lifecycle events. This is optional transport, but very production-typical.

**Runtime incident/perf signals → controlled automation → MPR rollback**
Conceptually allowed as “controlled automation”; still must emit governed lifecycle events (no bypass).

---

## 2) The complete edge map (one picture)

```
                         (policy profiles / approval_policy_rev)
                                   |
                                   v
         +--------------------+  [MPR]  +----------------------+
         |  Model Factory     |--J16--->|  Resolve/Read (DF)   |
         |  (bundle+evidence) |         |<--J10--> Active ref  |
         +--------------------+         +----------------------+
                    |                                |
                    |                                v
                    |                         (decision provenance
                    |                          cites bundle ref)
                    |
      (privileged)  v
   approve/promote/rollback
   +--------------------+
   | Gov actor /        |
   | controlled auto    |
   +--------------------+

 [MPR] -- registry_event (durable fact) --> Obs/Gov sinks / audit stores
   |
   +--> (optional) EB control topic: registry lifecycle facts
   |
   +--> Registry DB (authoritative)
   |
   +--> Object store (bundle blobs + evidence refs)
```

Pinned joins are J16 + J10; everything else above is either pinned choke-point behavior or required substrate for a production-ready deployment shape.

---

## 3) All production paths that *include* MPR (opaque vertex)

### Path P1 — “Training output becomes production logic” (the core boundary path)

`Offline Shadow → Model Factory → (J16) MPR → (J10) DF`
DatasetManifests feed MF; MF publishes bundles; registry governs activation; DF resolves deterministically and records the ref.

### Path P2 — “Hot path decision uses deployable truth” (resolution is in the RTDL)

`DF → (J10) MPR → DF`
Then DF executes using that resolved bundle and records bundle ref + compatibility basis (feature versions + degrade posture) in provenance.

### Path P3 — “Governed rollout”

`Gov actor/automation → MPR (promote) → registry_event → DF resolves new ACTIVE`
This is how you get “what changed?” answered: the registry_event changed ACTIVE.

### Path P4 — “Incident rollback”

`Obs/alerts → controlled automation → MPR (rollback) → registry_event → DF resolves previous ACTIVE`
Rollback is explicit and auditable; no silent swaps.

### Path P5 — “Environment promotion”

`Dev registry: approve/promote → (separately) Prod registry: approve/promote`
Promotion across envs is *selection of approved artifacts* (same semantics, different ScopeKey/environment).

### Path P6 — “Schema/feature evolution forces safe resolution”

`Feature definition/version change (policy/profile) → MPR resolution compatibility gate → DF safe fallback OR new bundle published → promote`
Registry compatibility is one of the platform’s two “schema evolution choke points” (IG for admitted facts; Registry for executable bundles).

---

## 4) All closed loops involving MPR (production feedback cycles)

### Loop L1 — The **Learning ↔ Serving loop** (the big one)

`DF decisions → decision provenance/audit → Offline Shadow rebuild → DatasetManifests → MF trains → MPR publishes/promotes → DF resolves new bundle → …`
MPR is the only bridge where learning output becomes deployable truth.

### Loop L2 — The **Governance/rollback loop**

`MPR promote → production outcomes/metrics → alerts → controlled automation/humans → MPR rollback → …`
All changes remain governed facts (`registry_event`).

### Loop L3 — The **Compatibility drift prevention loop**

`Feature definitions evolve (policy/profile) → MPR compatibility gate blocks unsafe bundle → DF safe fallback → MF publishes updated compatible bundle → MPR promotes → DF resolves`
This is exactly the “no training/serving drift by construction” intent.

### Loop L4 — The **Backfill → retrain → redeploy loop**

`Backfill declared (auditable) → Offline Shadow rebuilds datasets → MF retrains → MPR publishes/promotes → DF resolves`
Backfill is explicit + auditable; manifests pin replay basis; bundles carry that lineage.

### Loop L5 — The **Cache invalidation loop** (if you choose EB/control broadcast)

`MPR registry_event → EB control stream → DF cache invalidation → DF resolves fresh`
Optional transport; very production-typical.

---

## 5) The “nothing missed” claim (what does *not* directly join MPR)

By your pins, **no other component** is allowed to “load models directly” or bypass registry lifecycle; learning affects production **only via MPR**, and DF’s executable choice **only via J10 resolution**.

---

Here’s the **ordered expansion sequence** for the complete **MPR** outer-network **joins → paths → loops** (vertex still opaque). This ordering is chosen to minimize drift: **define the handshakes first**, then the end-to-end flows that depend on them, then the feedback cycles.  

## 1) Joins to expand first (boundary handshakes)

1. **J16 — Model Factory → MPR: PublishBundle (+ evidence + compatibility)** 
2. **Privileged Governance Actor/Automation → MPR: GovernLifecycle** (approve / promote / rollback / retire) 
3. **MPR → RegistryEvent sinks: EmitRegistryEvents** (durable governance facts for audit/ops) 
4. **J10 — Decision Fabric ↔ MPR: ResolveActive** (deterministic + compatibility-aware + fail-closed / safe fallback) 
5. **Optional (production-typical): MPR → EB control topic** (broadcast `registry_event` for DF cache invalidation) 
6. **Production substrate joins (still part of “production-ready”):**

   * MPR ↔ **Registry DB** (authoritative state) 
   * MPR ↔ **Object store** (bundle/evidence blobs by-ref) 
   * MPR ↔ **Approval policy profile/config** (`approval_policy_rev`) 

## 2) Paths to expand next (multi-edge sequences)

7. **Path: Learning output becomes deployable truth**
   `Offline Shadow → Model Factory → (J16) MPR → (J10) DF` 
8. **Path: Governed rollout**
   `Gov actor/automation → MPR (approve/promote) → registry_event → DF resolves new ACTIVE` 
9. **Path: Runtime decision usage**
   `DF → (J10) MPR resolve → DF executes + records ActiveBundleRef in provenance` 
10. **Path: Incident rollback**
    `Signals → controlled action → MPR rollback → registry_event → DF resolves previous ACTIVE` 
11. **Path: Environment promotion** (dev → prod as separate scopes, same semantics) 
12. **Path: Compatibility evolution / safe-block**
    `Feature/contract changes → MPR compatibility gate blocks unsafe ACTIVE → DF safe posture → MF publishes compatible → MPR promotes` 

## 3) Loops to expand last (closed feedback cycles)

13. **Loop: Learning ↔ Serving**
    `DF decisions/provenance → Offline Shadow rebuild → MF → MPR → DF` 
14. **Loop: Governance/rollback**
    `Promote → outcomes/alerts → rollback → …` 
15. **Loop: Compatibility drift prevention**
    `Feature evolution → block/upgrade bundle → redeploy → …` 
16. **Loop: Backfill → retrain → redeploy**
    `Backfill declared → rebuild datasets → MF → MPR → DF → …` 
17. **Loop: Cache invalidation loop** (if you choose control broadcast)
    `registry_event → EB control → DF cache invalidation → resolve fresh` 

If you want to start expanding immediately: we begin at **(1) J16 PublishBundle**, because it defines the canonical “bundle package” shape that everything else (lifecycle, resolution, audit, and loops) depends on.

---

Alright — expanding **the first 3 joins** with **MPR kept opaque**, but with *fully explicit boundary semantics* so nothing “hand-waves” into the black box.

The 3 joins are tightly coupled: **J16 (publish)** and **GovernLifecycle** *both must emit* the **registry_event** policy fact (Join #3).

---

# Join 1 — J16: Model Factory → MPR (PublishBundle)

## What this join *is for*

Model Factory produces **deployable bundles**; MPR is the **only authority** that turns those into deployable truth (ACTIVE) via governed lifecycle. So J16’s job is **registration of a candidate bundle package** with enough evidence and metadata to later govern promotion safely.

## Parties + posture

* **Caller:** Model Factory (a scheduled/on-demand job unit) 
* **Callee:** MPR (always-on control-plane service) 
* **Privilege:** “Publish” is distinct from “Resolve/Read” and from “Lifecycle mutation” (different privilege tier). 

## What *must cross* this join (the “bundle package”)

Your blueprint pins the minimum content of a published bundle package. I’m making that explicit as a “PublishBundle package” (not a spec, but the required truths):

### A) Bundle identity (immutable)

* `bundle_id`
* `bundle_version`
  This is the durable handle DF will later cite in provenance (after resolution).

### B) Immutable artifact refs + digests (by-ref truth, no payload copies)

* A bundle is not “a model file”; it’s a **package** of deployable artifacts: weights, rules, thresholds, metadata, policy configs, etc., each as **ref + digest**.
* **Digest posture is law:** when a digest is present it is a first-class integrity claim; mismatches are *inadmissible* (fail closed / reject). 

*(This is what keeps “someone swapped a file in the bucket” from ever being a thing.)* 

### C) Training provenance (reproducibility pins)

* `training_run_id` (or equivalent training execution id)
* **DatasetManifest refs** used as training inputs (immutable inputs; re-resolvable later)

This matters because J15→J16 is the reproducibility chain: **Offline Shadow pins dataset definitions; MF trains on those pins; MPR stores that lineage as evidence for promotion**.

### D) Evaluation evidence (what justifies “this should ship”)

* refs/digests to eval reports, metrics, plots, parity checks, stress tests, etc.

### E) PASS/FAIL receipts where governance posture requires it

The platform rail is explicit: **“No PASS → no read” is platform-wide**, not engine-only; it applies to “truth surfaces” including **deployable bundles**.

So, publish must carry:

* **GateReceipt refs/embeds** where your approval policy requires them (it may be PASS or FAIL — FAIL is still evidence, but non-promotable).

### F) Compatibility contract (required at publish/promotion time)

This is pinned under Registry compatibility:

Every bundle must declare compatibility covering (at minimum):

* **Feature group dependencies + versions** (anti training/serving drift)
* **Required capabilities** (so degrade can disable bundles safely)
* **Input contract version** (DF↔bundle interface version, even if implicit v0 today)

And: promotion without compatibility metadata is not “discouraged”; it’s **not a valid deployable artifact**. 

---

## MPR obligations at this join (what the black box must guarantee)

### 1) Publish is idempotent

Publishing the same `(bundle_id, bundle_version)` more than once must be safe (retries are normal in production). If identical, MPR returns “already registered” rather than creating duplicate truth.

### 2) Publish is *immutable registration*, not a mutable “update”

After publish, artifact refs/digests and declared compatibility are immutable; “correction” means publishing a **new version** (append-only correction posture).

### 3) Publish does **not** change production behavior

Publish never implies ACTIVE; only governed lifecycle mutation can change deployable truth.

### 4) Publish must be auditable (it emits a policy fact)

A publish is itself a governance_action and must emit a `registry_event` with `governance_action=publish` and the required fields (see Join 3).

---

## Failure outcomes (must be explicit)

At publish time, MPR must explicitly reject (or accept-but-mark-ineligible) when:

* artifact refs are missing or unverifiable under digest posture 
* compatibility contract missing (not a deployable artifact) 
* lineage missing (cannot justify reproducibility)
* receipt requirements violated under approval policy (policy-gated)

**Designer stance (authoritative):**
Publish may register a bundle that is **not promotable yet**, *but it must be clearly classified* as “registered but ineligible”, with reason codes, and it must still emit a registry_event reflecting that intake decision. This preserves auditability and avoids “mystery models.”

---

# Join 2 — Privileged Governance Actor/Automation → MPR (GovernLifecycle)

## What this join *is for*

This is the **only** mechanism that can change deployable truth. It’s the Registry equivalent of IG admission and AL execution: **a production choke point** whose changes must be privileged and auditable.

## Parties + posture

* **Caller:** human approver(s) and/or controlled automation (Run/Operate lane)
* **Callee:** MPR (always-on control-plane) 
* **Privilege:** highest tier for “deployable truth changes” (separate from publish and resolve). 

## Actions that must exist (minimum set)

From your pinned `registry_event.governance_action` enum:

* `approve`
* `promote`
* `rollback`
* `retire`

*(Publish is join 1, but still a governance_action in the event stream.)* 

## The scope rule that governs everything

The platform pins: Registry resolves exactly **one ACTIVE per scope** (and rollouts/rollbacks are explicit).

**Therefore this join must operate “per ScopeKey”.**
Even while MPR stays opaque, the governance action must always specify:

* `scope` (ScopeKey)
* `target_bundle` (bundle_id + version)
* `approval_policy_rev` (policy basis for allowing the action)

## What the black box must guarantee (production semantics)

### 1) Linearizable lifecycle per scope (conflict is explicit, never silent)

Two promote/rollback actions racing on the same scope must not lead to “split brain ACTIVE”. One wins; the other receives an explicit conflict outcome referencing the winning registry_event. (This is the only way DF caching is safe.)

### 2) “No PASS → no ACTIVE” (evidence-gated promotion)

Your rails say gating applies to bundles: a bundle is promotable only with required evidence attached (including PASS gate receipt where required).

So:

* **approve** can be “business approval” (human signoff) but cannot override missing required evidence where policy requires PASS.
* **promote** must fail if evidence posture not satisfied.

### 3) Compatibility enforced at promotion time too

Promotion requires compatibility metadata; otherwise it’s not a valid deployable artifact. 

### 4) Promote/rollback must be *auditable* and must encode replacement

Because ACTIVE changes are a first-class operational act, the event must clearly represent:

* which bundle became active,
* which bundle (if any) was replaced,
* why, under which policy revision, and with what evidence.

*(The pinned minimal `registry_event` has one `bundle_id`; the “replaced bundle” can be carried as an additional ref field without violating pins, but the semantics must be present.)* 

### 5) Idempotency is required (retries don’t create extra changes)

For any lifecycle mutation request, MPR must support an idempotency strategy (e.g., request id / idempotency key). Repeating the same mutation request must not create multiple conflicting “changes of truth.”

### 6) Retire is explicit and safe

Retire must never silently delete history. It marks a bundle as ineligible for future activation. If retiring the currently ACTIVE bundle, then either:

* retirement requires a simultaneous rollback/promote to another bundle, **or**
* retirement leaves the scope with “no active” (resolution fails closed / safe fallback), and that fact is recorded.

**Designer stance (authoritative):** Allow “no active” as a valid state per scope (it’s the cleanest fail-closed posture); DF then follows its safety policy (deny / degrade-safe fallback) and records why.

---

# Join 3 — MPR → RegistryEvent sinks (EmitRegistryEvents)

## What this join *is for*

Observability/Governance must “see change”; anything that can affect outcomes must emit auditable governance facts. For Registry, that fact is `registry_event`.

This join is how the platform remains explainable:

* “Why did decisions change?” → “Because ACTIVE changed” → “Here is the registry_event.”

## The pinned minimal event shape (non-negotiable)

Your blueprint pins the minimum one-line audit fact:

`registry_event = {registry_event_id, actor_principal, governance_action=publish|approve|promote|rollback|retire, from_state->to_state, bundle_id + immutable refs/digests, scope, approval_policy_rev, reason, evidence_refs (eval + GateReceipt where required)}`

So the join must deliver *at least* that.

## Delivery semantics (what “emit” must mean in production)

### 1) Append-only + durable

RegistryEvents are an immutable timeline: no edits-in-place, no silent deletion, no re-ordering. Consumers may receive at-least-once duplicates; dedupe is by `registry_event_id`.

### 2) Monotonic cursor (so other systems can catch up)

To be operable, consumers need a stable way to “read from event N onward”. So “emit” must support:

* either a streamed sequence with offsets/cursors,
* or a pull API keyed by a monotonic sequence id.

(Transport is flexible; monotonic consumption semantics are required for ops, audit, and safe caching.)

### 3) Sinks that must exist (at least)

At minimum, registry_event must be deliverable to:

* **Obs/Gov / Audit sinks** (for change control and explainability)
* and it is production-typical (optional) to also publish it onto a **low-volume control stream** for consumers (like DF) to invalidate caches safely.

Your deployment notes already anticipate a “control facts” channel (low volume) that can carry governance facts like registry lifecycle events.

## What’s produced when (tying joins 1 and 2 to join 3)

* Every **PublishBundle** must yield a `registry_event(governance_action=publish)` once the bundle is durably registered.
* Every **lifecycle mutation** (approve/promote/rollback/retire) must yield exactly one durable registry_event describing the transition and evidence basis.

---

## A quick “join choreography” view (opaque MPR)

```
Model Factory --(PublishBundle pkg)--> MPR --(registry_event timeline)--> Audit/Obs sinks (+ optional control stream)
Gov actor/auto --(approve/promote/rollback/retire)--> MPR --(registry_event timeline)--> same sinks
```

(Choreography implied by pinned registry_event and “registry is the only gate for logic changes.”)

---

Great — we’ll expand **joins #4–#6** with **MPR still opaque**, but with production-grade boundary semantics (inputs/outputs, guarantees, failure postures, and what other components may rely on).

---

# Join 4 — J10: Decision Fabric ↔ MPR (ResolveActive)

## What this join *exists to do*

DF needs a deterministic answer to: **“what decision logic am I allowed to execute for this decision right now?”**
MPR returns an **ActiveBundleRef** (bundle id + immutable artifact refs + compatibility metadata), and DF must record it in provenance.

## The pinned production truths (non-negotiable)

1. **Deterministic resolution (no “latest”)**: for a given scope, DF gets one active bundle by rule.
2. **Compatibility enforced at the join**: MPR must not resolve an ACTIVE bundle that is incompatible with (a) current feature definitions/versions or (b) the current degrade mask. If incompatible → **fail closed** or route to an explicitly defined safe fallback; never “half-compatible proceed.”
3. **Provenance is mandatory**: DF records the resolved bundle ref, the feature group versions actually used (from OFP), and the degrade posture in force.

## What crosses the join (conceptual handshake)

### Request (DF → MPR) must include:

* **ScopeKey** (the uniqueness domain for ACTIVE)
* **Degrade constraints**: `capabilities_mask` is a hard constraint (if capability is off, DF behaves as if that tool/model doesn’t exist).
* **Feature-definition basis** sufficient to judge compatibility

  * v0 best posture: DF supplies a stable **FeatureDefinitionSet / FeatureGroupVersions basis** (or equivalent token) representing “what feature definitions are in force right now,” so MPR can do compatibility checks without guessing.

*(This is consistent with your pin that feature definitions are versioned and singular across serving/offline/bundles.)*

### Response (MPR → DF) returns:

* `status` ∈ {**RESOLVED**, **NO_ACTIVE**, **INCOMPATIBLE**, **FORBIDDEN/NOT_AUTHZ**}
* If RESOLVED: **ActiveBundleRef** = (bundle id + immutable refs/digests + compatibility metadata)
* A monotonic **resolution proof token** (e.g., the registry_event cursor / “why this is true”) so DF can cache safely and still be correct under changes.

## The production behaviors DF is allowed to rely on

* **One ACTIVE per scope** (or “no active” is a valid fail-closed state).
* **Fail-closed semantics**: if MPR cannot guarantee compatibility, it refuses to resolve (or returns only an explicitly defined safe fallback).
* **At-least-once safe**: duplicate resolve requests can’t cause state change; they just return the same answer for the same inputs. (The platform assumes retry reality everywhere.)

## “Safe fallback” — where it lives (designer pin)

v0 stance: **fallback is primarily DF’s safe posture**, triggered by explicit MPR non-resolution reasons (NO_ACTIVE/INCOMPATIBLE). If you later want a registry-provided fallback bundle, it must be **explicitly declared** and still compatibility-checked (no magical “backup”).

## Two production-grade modes (both valid under your pins)

1. **Direct call mode**: DF calls ResolveActive each decision. Works, simple, more coupling.
2. **Cache + invalidation mode**: DF caches per scope_key + feature_basis + degrade_mask, and invalidates when registry_event changes (join #5). This is the typical production shape.

---

# Join 5 — Optional: MPR → EB control topic (broadcast registry events for cache invalidation)

## Why this join exists (and why it’s optional)

MPR is a low-QPS authoritative control-plane service; DF is hot-path. Broadcasting registry lifecycle facts onto a **control stream** lets consumers (DF, ops tooling) react quickly without polling. Your deployment notes explicitly allow control-plane facts on `fp.bus.control.v1`.

## What crosses this join

* **Registry lifecycle facts** (registry_event), emitted as low-volume control events (at-least-once).

### Important pin: “bus messages still obey the platform envelope posture”

If MPR emits onto EB, those events must be classifiable and versioned like everything else (stable envelope, payload version behind it). That’s the platform’s schema-evolution stance.

## Semantics that make this production-safe

* **Not authoritative**: EB control emission is a *broadcast/notification*; the authoritative truth remains the Registry DB + audit sinks.
* **Dedupe**: consumers dedupe by `registry_event_id` (or equivalent) because delivery is at-least-once.
* **Partitioning** (recommended): partition by `scope_key` so per-scope event ordering is preserved for cache invalidation logic (implementation detail, but the semantic need is real).

## What DF does with it (production-typical)

* Maintain a small “latest registry_event cursor per scope” cache.
* When a promote/rollback arrives for scope X, invalidate/refresh the cached ActiveBundleRef for X.
* Record the event cursor used when making decisions (so later: “this decision used bundle ref Y because registry_event Z was active”).

---

# Join 6 — Production substrate joins (must exist in a production-ready platform)

These aren’t “other components,” but they are **required state substrates** that make MPR real in production shape. Local/dev may collapse them, but semantics cannot change.

## 6a) MPR ↔ Registry DB (authoritative lifecycle + resolution)

Pinned substrate view: **Registry DB is an authoritative DB** (non-rebuildable truth) holding “lifecycle + resolution.”

### What the DB must support (semantically)

* Uniqueness constraint: **at most one ACTIVE per ScopeKey**.
* Durable history: the “event timeline” (or equivalent) that backs audit queries and registry_event emission.
* Conflict visibility: concurrent lifecycle mutations must result in explicit conflicts, never split-brain ACTIVE. (This is what makes DF caching safe.)

### What *cannot* be true

* “ACTIVE changed but no durable record exists” is forbidden (breaks the platform’s governance-facts rail).

## 6b) MPR ↔ Object store (bundle blobs + evidence artifacts by-ref)

Pinned substrate view: object store holds by-ref artifacts including **manifests/bundles**, audit records, receipts, etc.

### What this join means for MPR semantics

* Registry DB stores **refs + digests**; object store holds the bytes.
* Bundles/evidence are **immutable artifacts** (no overwrite). If something changes, it is a new object + new digest + new bundle version.
* “Meaning is owned by the writer component”: object store doesn’t “make things true” by itself; MPR is the authority for bundle truth; MF is the producer of candidate artifacts; activation remains governed by MPR.

## 6c) MPR ↔ Approval policy profile/config (`approval_policy_rev`)

Pinned config posture: **policy config is outcome-affecting**, versioned, and auditable; registry events must cite the **approval policy revision used**.

### What must be true at this join

* MPR evaluates publish/lifecycle actions under a specific **approval policy revision** (the active profile), and records that `approval_policy_rev` in every relevant registry_event.
* Policy/profile revisions have identity + digest + monotonic revision/tag (so you can answer “what rules were in force?”).
* Policy/profile changes follow the same governance shape: proposed → approved → active, with rollback. (This is pinned for policy configs in general and explicitly in the CI/CD lane story.)

### A subtle but important consequence (designer pin)

**Resolution behavior is policy-shaped**, so when DF resolves a bundle, it is valuable (and production-typical) for the response to carry the **registry policy rev used for resolution** (even if you don’t expose it to end users). This aligns with the platform-wide requirement that components can report which policy rev they operated under.

---

## Where we are now

With #4–#6 expanded, MPR’s opaque vertex has a fully pinned **read join (ResolveActive)**, an optional but production-typical **event broadcast join**, and the **required substrate attachments** that make it a real control-plane authority.

---

Alright — expanding **#7–#9 (paths)** end-to-end, with **MPR still opaque**. I’ll keep each path “production-real”: explicit artifacts, where truth lives, what’s recorded for replay/explainability, and what happens on failure.

---

## Path #7 — Learning output becomes deployable truth

`Offline Shadow → Model Factory → (J16) MPR → (J10) DF`

### What this path exists to guarantee

A “new model/policy” is only allowed to influence decisions if it is:

1. trained on a **pinned, reproducible dataset basis** (DatasetManifest), and
2. published to MPR as an **immutable bundle package** with evidence + compatibility, and
3. later resolved by DF as the **compatibility-safe ACTIVE** bundle.

### Step-by-step sequence (outer-network view)

**1) Offline Shadow produces *training truth inputs***

* Reads replay history from **EB and/or archive**; replay basis must be explicit (offset ranges/checkpoints, not “last 90 days” hand-waving).
* Uses Label Store with **as-of semantics** so datasets can represent “what we knew then” vs “what we know now.” 
* Uses **singular, versioned feature definitions** (same authority used by serving).
* Writes:

  * dataset materializations under `ofs/…`
  * the **DatasetManifest** (the unit of reproducibility) alongside them.

**Pinned output of this step:** the DatasetManifest must pin replay basis + label as-of boundary + feature definition versions + digests/refs + pipeline provenance.

---

**2) Model Factory trains/evaluates using manifests as immutable inputs**

* Treats DatasetManifests as **immutable inputs**; reproducibility depends on re-resolving the exact manifests later.
* Produces:

  * bundle artifacts + **digests**
  * evaluation evidence
  * (and retains the dataset manifests used as lineage)
* Writes training/eval evidence under `mf/…` (production-shaped layout).

---

**3) Model Factory publishes the candidate to MPR (J16)**
What crosses must be a **bundle package**:

* bundle identity
* immutable refs/digests to artifacts
* training provenance: **which DatasetManifests were used**
* evaluation evidence
* PASS/FAIL receipts where governance posture requires
* compatibility metadata (feature versions expected, input expectations)

This is where “learning output becomes a *deployable candidate*” (but not yet ACTIVE).

---

**4) MPR durably registers (but does not activate)**

* Stores lifecycle truth in `registry` DB and bundle blobs under `registry/bundles/…` (by-ref, digest posture).
* Emits a durable one-line **registry_event** for publish (auditability).

---

**5) DF can only use it once it becomes ACTIVE and resolves compatibility-safe (J10)**

* DF uses MPR as the choke point for “what should I execute right now?”, and records the resolved bundle ref.
  *(The governed activation itself is Path #8.)*

### “What this path makes answerable” (production sanity)

* “What dataset did this bundle train on?” → the bundle package references **DatasetManifests**.
* “Why did decisioning change?” → a **registry_event changed ACTIVE**, and decisions cite bundle ref.

---

## Path #8 — Governed rollout

`Gov actor/automation → MPR (approve/promote) → registry_event → DF resolves new ACTIVE`

### What this path exists to guarantee

Deployable truth changes are **explicit, attributable, and auditable** — no “someone swapped a model.”

### Step-by-step sequence

**1) Preconditions**

* Candidate bundle exists in MPR (published) with required evidence + compatibility metadata (otherwise it’s not a valid deployable artifact).

---

**2) Privileged actor/controlled automation issues lifecycle actions**

* `approve` and `promote` are privileged changes; they operate **per ScopeKey** and must preserve “one ACTIVE per scope.”
* Each action is evaluated under a specific **approval_policy_rev** and must carry a reason/evidence basis.

---

**3) MPR commits the change and emits the governance fact**

* MPR appends a `registry_event`:

  * who did it (`actor_principal`)
  * what action (`approve|promote|…`)
  * from→to state
  * bundle refs/digests
  * scope
  * `approval_policy_rev`
  * reason + evidence refs (eval + GateReceipt where required)
* This is the durable “why ACTIVE changed” record.

*(Optionally, this can also be broadcast on `fp.bus.control.v1` as a low-volume control fact for cache invalidation; the authoritative truth remains registry DB + audit sinks.)*

---

**4) DF resolves the new ACTIVE (and proves it in provenance)**

* DF resolves deterministically; no “latest.”
* Compatibility is enforced: if the new ACTIVE is incompatible with feature versions or degrade mask, DF must fall back to safe posture and record why.
* DF records the resolved bundle reference in decision provenance (so later “what changed?” is answerable).

---

**5) Operationally, rollout is “select approved artifacts,” not “change semantics by env”**
Across local/dev/prod, promotion is selecting approved artifacts/profiles/bundles; semantics don’t fork by environment.

### Key production failure cases (and required outcomes)

* Two promotes race for same scope → one wins; the other gets an explicit conflict (no split-brain ACTIVE).
* Promote attempted without required evidence/compat metadata → hard fail (not deployable).

---

## Path #9 — Runtime decision usage

`DF → (J10) MPR resolve → DF executes + records ActiveBundleRef in provenance`

This path is where registry “active truth” actually becomes **executed behavior**, and where provenance must be strong enough to replay/explain.

### Runtime sequence (what DF does in production)

**0) DF receives a decision trigger**

* Either consumes an admitted business event from `fp.bus.traffic.v1` or receives a synchronous request; DF is hot path.

---

**1) DF binds time + context for the decision**

* Uses `event_time_utc` as the decision boundary and requests features with `as_of_time_utc = event_time_utc` (no hidden “now”). 
* DF obtains OFP features **with pinned provenance**:

  * `feature_snapshot_hash`
  * feature group versions used
  * freshness/stale posture
  * `input_basis` watermark vector
  * `graph_version` (if IEG consulted) 

---

**2) DF obtains Degrade posture (hard constraints)**

* DL provides `mode + capabilities_mask`. DF treats the mask as **hard constraints** (capability off ⇒ tool/model/action “doesn’t exist”).
* Degrade posture is recorded in provenance; if DL is unavailable DF fails **toward safety** and records the fallback.

---

**3) DF resolves Active bundle via MPR (J10)**

* DF supplies:

  * ScopeKey
  * degrade capabilities mask
  * enough feature-definition basis to judge compatibility
* MPR returns:

  * **ActiveBundleRef** (id + immutable refs/digests + compatibility metadata) 
  * or a non-resolution (NO_ACTIVE / INCOMPATIBLE), which DF must treat as a safe-posture trigger.

---

**4) DF executes the decision under the resolved bundle**

* Loads bundle artifacts by-ref (or uses a cached/loaded bundle) but always under digest posture (mismatch ⇒ inadmissible).
* Applies the bundle to the event + feature snapshot, respecting degrade constraints.

---

**5) DF emits decision output with mandatory provenance**
Deployment notes pin the key: DF is mostly stateless but must persist provenance **in emitted events**.

**Minimum decision provenance must include:**

* resolved bundle ref (id + digest posture)
* feature snapshot provenance (`feature_snapshot_hash`, group versions, `input_basis`, `graph_version` if any)
* degrade posture used

This is what makes decisions explainable after rollouts/rollbacks.

*(Downstream: DF may emit ActionIntents, and audit log consumes DF’s decision+provenance as the non-negotiable base — but the key point for this path is that the bundle ref and compatibility basis are recorded.)*

### Runtime failure postures (must be explicit)

* **MPR says INCOMPATIBLE/NO_ACTIVE** → DF follows safe posture and records why.
* **OFP missing required features** → DF records unavailability and follows fail-safe posture (no invention). 
* **DL unavailable** → DF fails toward safety and records fallback.

---

Yep — here are **#10–#12 expanded** end-to-end, with **MPR still opaque**, but with production-real triggers, artifacts, and the “what must be recorded so it’s explainable later” story.

---

## Path #10 — Incident rollback

`Signals → controlled action → MPR rollback → registry_event → DF resolves previous ACTIVE`

### What this path guarantees

When something goes wrong in serving, the platform can **revert deployable truth** quickly **without silent changes**, and every downstream decision remains explainable as “bundle X was active because registry_event Y.”

### Production signal sources (what can legitimately trigger rollback)

Rollback triggers come from **Ops/Obs**, not from “gut feel,” and they must be attributable. In your deployment notes, prod is explicitly “no human memory; every change is a fact,” and dev is “real enough to catch incompatible bundles / missing PASS evidence,” which implies rollback signals are **structured and acted upon via controlled automation or a privileged actor**.

**Typical rollback signals** (examples; the pin is “signals exist and are observable facts,” not the exact metric list):

* DF/AL outcome error rates spike (failed actions, denied actions, unexpected distributions)
* model/policy compatibility failures (MPR resolution returns incompatible / no-active too often)
* feature snapshot health issues (OFP freshness/stale posture or missing required features)
* safety corridor breaches that trip Degrade Ladder changes (which constrain DF hard)

### Step-by-step sequence

**1) Detect + triage**

* Obs/Gov pipeline produces the evidence trail (metrics/traces/logs), correlated with the universal keys (decision/event/bundle).

**2) Controlled action decides “rollback scope + target”**

* A **privileged actor** or **controlled automation** chooses:

  * `scope_key` (the scope whose ACTIVE is changing), and
  * the rollback target bundle (typically “previous approved”)

**3) Execute rollback via MPR lifecycle mutation**

* MPR performs `governance_action=rollback` (or equivalently an explicit promote of the previous bundle) **per scope**, preserving “one active per scope.”

**4) MPR emits the governing fact**

* MPR appends a `registry_event` capturing actor, action, from→to state, bundle refs/digests, scope, approval policy revision, reason, evidence refs.

**5) DF begins using the prior bundle deterministically**
Two valid production modes:

* **Polling/resolve mode:** DF resolves J10 as needed; it will now resolve to the prior bundle.
* **Event-driven invalidation mode (optional):** registry lifecycle events are broadcast to `fp.bus.control.v1` so DF invalidates caches immediately.

**6) DF records the rollback effect in provenance**

* Every post-rollback decision cites the resolved **ActiveBundleRef** and compatibility basis (feature group versions used + degrade posture). This is explicitly pinned as the reason decisions remain explainable after rollouts/rollbacks.

### Failure posture (must be explicit)

* If rollback leaves **no active bundle** for a scope, J10 resolution must fail closed (or safe fallback) and DF records why.
* Rollback cannot be “edit the model file”: artifacts are immutable and activation is governed (bundle rollback is its own lane).

---

## Path #11 — Environment promotion (dev → prod as separate scopes, same semantics)

*(“promotion is selecting approved artifacts/profiles — not forking meaning”)*

### What this path guarantees

You don’t have three different platforms. **Local/dev/prod share the same graph + rails + meanings**; “ACTIVE” means the same thing everywhere, and promotion is a controlled change of **environment profile / policy strictness**, not semantics.

### The authoritative promotion posture

Across environments, CI/CD promotes **three immutable things**:

1. code artifacts,
2. policy/profile revisions,
3. model/policy bundles (Registry lifecycle).
   And **every promotion/rollback emits governance facts.**

### Step-by-step sequence (bundle lane)

Think of this as “the same bundle bytes become ACTIVE in a different environment scope.”

**1) Candidate succeeds in dev**

* Bundle is published + approved + promoted in **dev** scope; dev validates end-to-end compatibility and degrade behavior (dev must catch failures prod would catch).

**2) Promotion package is immutable**

* The promoted bundle is identified by `bundle_id/version` + immutable refs/digests + evidence refs + compatibility metadata. No rebuilding “for prod.”

**3) Deliver to prod environment’s Registry context**
Two production-valid outer shapes (both preserve pins; choose whichever matches how you run environments):

* **Separate env stacks:** prod has its own Registry DB/object prefix; MF (or a controlled release job) publishes the same bundle package into prod MPR (J16).
* **Single Registry with environment in ScopeKey:** same service/DB, but lifecycle actions are per `{environment,…}` scope. (Semantics identical either way; the ScopeKey includes environment.)

**4) Prod approval/promotion is governed**

* Prod uses stricter policy configs and stronger auth; a privileged actor/automation performs approve/promote for **prod** scope, emitting `registry_event` with `approval_policy_rev`.

**5) DF in prod resolves deterministically**

* DF resolves J10 in prod scope and records bundle ref + compatibility basis.

### What must never happen (banned by your pins)

* “We rebuilt the model for prod” (artifact drift) — forbidden by build-once/run-anywhere and bundle immutability.
* “ACTIVE means something different in prod” — forbidden by environment ladder invariants.

---

## Path #12 — Compatibility evolution / safe-block

`Feature/contract changes → MPR compatibility gate blocks unsafe ACTIVE → DF safe posture → MF publishes compatible → MPR promotes`

### What this path guarantees

You can evolve features/contracts without silently breaking decisioning because the platform has **two evolution choke points**:

* IG gates **schema/version** admission onto EB,
* Registry gates **bundle compatibility** for execution.

For this path we focus on the Registry side: **DF never guesses**; bundles declare compatibility; resolution is compatibility-aware; if incompatible, fail closed or explicit safe fallback.

### The three compatibility break triggers (production-real)

1. **Feature definition/version change** (OFP feature groups evolve) — but they’re singular and versioned across serving/offline/bundles.
2. **DF↔bundle input contract change** (the conceptual interface version evolves).
3. **Degrade posture change** disables capabilities the bundle requires (capabilities mask is a hard constraint).

### Step-by-step sequence

**1) Platform context changes**

* OFP begins serving under new feature group versions and records them in snapshot provenance; DF records them in decision provenance.
* Or DL changes degrade posture and DF treats the capabilities mask as hard constraints.

**2) DF resolves via MPR with compatibility basis**

* DF calls J10 with scope + degrade constraints + enough feature-definition basis for compatibility checks (conceptually, “these feature group versions are in force”).

**3) MPR blocks unsafe ACTIVE**

* If the currently ACTIVE bundle requires feature versions DF/OFP can’t satisfy, or requires capabilities currently disabled, resolution **must not return it**. It fails closed or returns only an explicitly defined safe fallback.

**4) DF enters safe posture and records why**

* DF does not invent missing context; it records unavailability/incompatibility and takes its pinned fail-safe posture (which may mean “no action,” “manual review,” “baseline rule bundle,” etc. — but always explicit and recorded).

**5) Model Factory publishes a compatible bundle**

* MF trains/evals (or re-packages policy) under the new feature definition basis and publishes a new bundle that declares updated compatibility + evidence. Promotion without compatibility metadata is invalid.

**6) Registry promotes; DF resumes normal resolution**

* A governed lifecycle action promotes the compatible bundle; a registry_event is emitted; DF resolves and records new bundle ref + compatibility basis.

### The “explicit deprecation window” guardrail (prevents surprise breakage)

When changes are breaking, the platform posture is explicit and time-bounded deprecation (no “surprise” incompatibility). That’s how you avoid waking up to “everything incompatible” overnight.

---

Below are **loops #13–#17** expanded as *production-grade outer-network cycles* with **MPR kept opaque**. I’ll make each loop explicit as: **what triggers it → what must be recorded → what truth moves where → what closes the loop → what guardrails prevent drift/time-travel**.

---

# #13 — Loop: Learning ↔ Serving (the main “model improvement” flywheel)

`DF decisions/provenance → Offline Shadow rebuild → Model Factory → MPR → DF`

## What this loop exists to guarantee

Learning is fed only by **replayable facts + decision-time provenance**, and whatever learning produces can influence production **only via MPR**.

## The cycle (one full turn)

### 1) DF makes decisions and leaves “rebuild targets” behind

For each decision point, DF must emit/record enough to reconstruct *exactly what the platform could have known at that time*:

* event basis via **EB coordinates / watermarks**,
* entity context via `graph_version`,
* features via `feature_snapshot_hash` + `input_basis`,
* degrade posture (mode + mask id),
* bundle ref (the resolved MPR bundle).

This provenance is the “hook” learning uses later; learning must not depend on live caches.

### 2) DLA (audit) turns those into an immutable flight-recorder stream

DLA ingests DF’s decision response + provenance as the **non-negotiable base**; it is append-only, idempotent, quarantines incomplete provenance, and supports corrections via supersedes chains.

### 3) Offline Shadow deterministically rebuilds training reality

Offline Shadow reads:

* admitted events from **EB (or Archive beyond retention)** as one logical fact stream,
* labels from Label Store with leakage-safe **as-of** joins (effective vs observed time),
* feature definitions that are **versioned and singular** across serving/offline/bundles.

It then emits **DatasetManifests** + materializations (the unit of reproducibility), and parity evidence vs serving (e.g., matching `feature_snapshot_hash` under same `input_basis` + `graph_version`).

### 4) Model Factory trains/evals on pinned manifests

Model Factory consumes DatasetManifests (not ad-hoc exports), produces training/eval evidence, and publishes a bundle candidate.

### 5) MPR is the only bridge back into serving

MPR registers immutable bundles and governs lifecycle; DF must resolve from MPR and record the resolved bundle ref in provenance. Nothing “loads a model file from latest.”

## Guardrails that make this loop “closed world” (no drift)

* **Replay basis is always explicit** (offset ranges/checkpoints), and **DatasetManifests pin it** so training can be reproduced later even after retention changes.
* Labels are **append-only timelines** and training joins are **as-of** (leakage safe). 
* Feature definitions are **singular + versioned**; serving and offline must agree.

---

# #14 — Loop: Governance / rollback (the safety flywheel)

`Promote → outcomes/alerts → rollback → …`

## What this loop exists to guarantee

Serving can be changed quickly under incident conditions, but **only through governed, auditable changes** (registry events), never silent swaps.

## The cycle

### 1) Promotion changes deployable truth

A promotion/rollback/retire is a privileged lifecycle mutation that must emit the one-line policy fact:
`registry_event = {actor, action, from→to, bundle refs/digests, scope, approval_policy_rev, reason, evidence_refs…}`

### 2) Outcomes/alerts surface “something is wrong”

Signals come from Obs/Gov and from the behavior of DF/AL/DLA (error rates, corridor checks, feature health, degrade escalations). The key is: *signals are observable facts* used by Run/Operate or humans.

### 3) Controlled automation or a privileged actor rolls back

Rollback is explicit and per scope; it produces a new registry_event, and DF’s subsequent decisions cite the new resolved bundle ref (so “what changed?” remains answerable).

## Guardrails

* Rollbacks are **first-class** and auditable; DF behavior changes **only** via these explicit mechanisms.
* Audit/provenance is the glue that ties “outcome changed” to “bundle changed” without hand-waving.

---

# #15 — Loop: Compatibility drift prevention (anti “training/serving mismatch”)

`Feature evolution → block/upgrade bundle → redeploy → …`

## What this loop exists to guarantee

Even if features evolve or degrade constraints tighten, DF never executes an “ACTIVE-but-incompatible” bundle. Compatibility is enforced **at resolution**, not by hope.

## The cycle

### 1) Platform context evolves

Any of these can shift:

* feature group versions in force (OFP records versions used),
* DF↔bundle input contract version (conceptual),
* degrade posture/capabilities mask (hard constraint).

### 2) MPR resolution checks compatibility (not just ACTIVE)

Bundles must declare compatibility (feature group versions, required capabilities, input contract version). Resolution must refuse incompatible bundles: **fail closed or explicit safe fallback**.

### 3) DF records the compatibility basis it actually used

Decision provenance must include:

* resolved bundle ref,
* feature group versions actually used (from OFP),
* degrade posture in force.

### 4) Learning produces a compatible bundle and redeploys through MPR

Model Factory publishes a new bundle with updated compatibility metadata + evidence; registry promotes via governed change; DF resumes normal resolution.

## Guardrails

* **Feature definitions are singular + versioned** across serving/offline/bundles (this is the anti-drift anchor).
* Registry compatibility is a choke point symmetric to IG’s schema/version gating (one gates *facts*, one gates *executable truth*).

---

# #16 — Loop: Backfill → retrain → redeploy (truth evolves without “time travel”)

`Backfill declared → rebuild datasets → MF → MPR → DF → …`

## What this loop exists to guarantee

When late facts arrive, bugs are fixed, or retention changes, you can recompute derived outputs—**but never by silently overwriting truth**. Backfills are declared, scoped, auditable, and watermarks don’t lie.

## The cycle

### 1) Backfill is explicitly declared (a governance fact)

A backfill must declare scope, purpose, basis (offset ranges/checkpoints), and outputs regenerated; it emits a durable governance fact and produces new derived artifacts.

### 2) Rebuild derived stores / datasets using an explicit replay basis

Offline Shadow rebuild uses EB/Archive as one logical stream and records the basis; DatasetManifests pin it. “Last 90 days” is not enough; it must be “these offsets/checkpoints.”

### 3) Train on the new pinned manifests (optionally compare to “what we knew then”)

Because labels are timelines with effective vs observed time, you can generate both:

* “what we knew then” datasets (honest evaluation), and
* “what we know now” datasets (improved training),
  without mixing them.

### 4) Publish/promote via MPR and redeploy

Same as the main learning loop: MF publishes a new candidate; MPR governs activation; DF resolves and records the bundle ref.

## Guardrails (the “never mutate primary truth” line)

Backfill can regenerate **derived** stores/artifacts; it cannot “backfill” primary truths like EB admitted events, Label Store timelines, Registry lifecycle history, or immutable engine outputs for a pinned identity.
Watermarks remain monotonic; backfill creates new offsets/versions, not time travel.

---

# #17 — Loop: Cache invalidation loop (optional but production-typical)

`registry_event → fp.bus.control.v1 → DF cache invalidation → resolve fresh`

## What this loop exists to guarantee

MPR stays a low-QPS control plane, while DF is hot path. A low-volume control stream makes DF converge quickly on “current ACTIVE” without polling.

## The cycle

### 1) MPR emits registry lifecycle events

Registry emits durable registry_event facts, and (optionally) also publishes them to `fp.bus.control.v1`.

### 2) DF subscribes and invalidates per scope

DF maintains a per-scope cache keyed by `(scope_key, feature_basis, degrade_mask)` (conceptually), and invalidates on relevant registry_event changes. (Transport is optional; semantic requirement is “DF can become consistent quickly.”)

### 3) DF resolves fresh and records the registry cursor/basis

After invalidation DF resolves again and decisions continue to record bundle ref + feature versions + degrade posture—keeping explainability intact across rollouts.

## Guardrails

* Control stream is **notification**, not authority; Registry DB + registry_event history remain the source of truth.
* At-least-once delivery implies DF dedupes by registry_event_id / cursor (no double-rollout effects).

---

Yes — the **environment ladder** changes *how strict / how durable / how scalable* these joins/paths/loops are operated, but it must **not** change what they *mean*. Your deployment notes pin this hard: **local/dev/prod run the same platform graph + rails/join semantics; only the operational envelope differs**.

Here’s what matters specifically for the **MPR-centric joins/paths/loops**.

---

## 1) The ladder’s non-negotiables that directly constrain MPR

### The meanings must not change across envs

The words **READY / ADMITTED / ACTIVE / LABEL AS-OF / BACKFILL** must mean the same thing everywhere. So “ACTIVE” is always **Registry-controlled deployable truth**, even on your laptop.

### Rails/join semantics must not change across envs

In particular, these rails are directly implicated in MPR interactions:

* by-ref refs/locators (no “scan latest”)
* no-PASS-no-read (expressed for MPR as “no evidence → no ACTIVE” under policy)
* deterministic registry resolution
* idempotency + append-only/supersedes governance facts

### Promotion is profile selection, not semantic forking

Across environments you promote **immutable code artifacts**, **versioned policy/profile revisions**, and **model/policy bundles**; you don’t rebuild “for prod,” and you don’t introduce “prod-only semantics.”

---

## 2) What *should* vary by environment (and how that touches your joins)

Your notes allow differences in: **scale, retention/archive, security strictness, reliability posture, observability depth, and cost knobs**—but those differences must not alter the meaning of the interfaces.

That maps to MPR like this:

### A) Security strictness (most visible on MPR joins)

* **Local:** you can use permissive principals/allowlists, but the *mechanism* (privileged lifecycle mutation vs publish vs resolve) must still exist.
* **Dev:** must be “real enough” to catch failures prod would catch—explicitly including **registry lifecycle privileges** and **incompatible bundles**.
* **Prod:** strongest authn/authz + strict change control; “every change is a fact.”

**Implication:** the *join semantics* don’t change; the **policy profile** (strictness) changes.

### B) Observability depth (affects loops #14/#17 strongly)

* Local can be inspect-by-hand.
* Prod must have governance dashboards, alerts, corridor checks (degrade triggers are meaningful).

**Implication:** rollback loop (#14) and cache invalidation loop (#17) become more automated/fast in prod, but they’re still the same loop.

### C) Retention + archive (affects loops #13/#16 strongly)

Retention windows differ by env profile, but **replay semantics and watermark meaning do not**; archive is the long-horizon extension used for offline rebuilds beyond EB retention.

**Implication:** in local/dev you may not have deep history; you still must express training/backfill on explicit replay bases (offset ranges/checkpoints), just over smaller windows.

---

## 3) Join-by-join: what the ladder changes vs what it cannot change

### J16 PublishBundle (MF → MPR)

**Cannot change:** bundle publish is immutable/by-ref + auditable; Registry activation is separate governed step.
**Can change:** evidence strictness at publish-time vs promote-time via policy profile:

* local can allow “register but ineligible”
* dev should enforce enough to catch missing PASS evidence / missing compatibility metadata
* prod enforces strict “no evidence → no ACTIVE” under approval policy

### GovernLifecycle (privileged actor/automation → MPR)

**Cannot change:** governed lifecycle always emits governance facts; Registry is the deployable truth choke point.
**Can change:** who is allowed to do it (principals), approval gates, and how automation is wired (manual in local, semi-automated in dev, tightly controlled in prod).

### EmitRegistryEvents (MPR → sinks, optional EB control)

**Cannot change:** registry events exist as durable facts (append-only posture); they are how “what changed?” becomes answerable.
**Can change:** distribution:

* local can just persist + print + minimal dashboards
* dev/prod typically also broadcast to `fp.bus.control.v1` for fast convergence/cache invalidation

### J10 ResolveActive (DF ↔ MPR)

**Cannot change:** deterministic resolution + compatibility-aware + fail-closed posture is platform law.
**Can change:** performance strategy:

* local can call MPR directly (no caching)
* prod will usually cache and invalidate on registry events to keep MPR off the hot path

### Substrate joins (DB/object store/policy profile)

**Cannot change:** Registry has an authoritative DB and bundles/evidence are by-ref objects; policy config is versioned and auditable, not “env state.”
**Can change:** local can collapse these into one small stack; prod uses hardened/HA equivalents—but semantics stay.

---

## 4) Path/loop implications that are easy to miss

### Path #11 (environment promotion) becomes “scope separation,” not “different rules”

To keep “not three platforms,” you need **ScopeKey to include environment** (whether by separate registries or a single registry with env in scope). That’s how dev ACTIVE never bleeds into prod ACTIVE while keeping meaning identical.

### Loop #13 (learning ↔ serving) must be runnable locally in “tiny” form

Your CI/CD pin explicitly wants a local integration flow that includes **offline shadow + registry resolution at least once**—because otherwise you’ll build a system that only works in prod.

### Loop #16 (backfill) is *more frequent* in dev, but most constrained in prod

Backfills are explicit, scoped, auditable; they can regenerate derived state/artifacts, but **cannot** “mutate truth” like EB admitted events, registry lifecycle history, label timelines, or immutable engine outputs. That constraint applies in every env; prod just enforces it hardest.

---

## The crisp designer takeaway

Treat the environment ladder as:

* **Same meanings, same joins, same loops** everywhere (no semantic forks).
* Differences are purely in **profiles** (policy strictness + wiring), **durability**, **retention/archive**, **scale**, and **observability/automation**, with promotion being **selection of approved artifacts/revisions** (code/config/bundles), not rebuilds.

---

Yep — here are the **environment profile knobs** (plus the *deployment facts you should keep in your head*) for the **opaque MPR vertex**, in a way that keeps you pointed in the right direction before we “enter” it.

Everything below respects the ladder pin: **same graph + same rail semantics across local/dev/prod; only the operational envelope changes**, and promotion is **profile selection**, not code forks.

---

## 1) First: what MPR is in deployment terms

MPR is an **always-on control-plane service** (low QPS but authoritative): it **serves bundle resolution**, **accepts governed lifecycle changes**, and **emits registry events**.
It anchors to:

* an **authoritative registry DB** (lifecycle truth, one-active-per-scope constraints),
* an **object store** (bundle/evidence blobs by-ref),
* and optionally the **control bus** for low-volume governance facts (e.g., registry_event broadcast).

---

## 2) The environment profile knob taxonomy you should use (platform-wide, applies cleanly to MPR)

Your platform pins a clean split:

### A) Wiring profile (non-semantic)

Endpoints, ports, credentials sources, timeouts, resource limits. 

### B) Policy profile (outcome-affecting)

Rules that change what the system is allowed to do (therefore **versioned + auditable**, and referenced by `policy_rev`/`approval_policy_rev` in facts).

This is the core “knob framework” for the ladder.

---

## 3) MPR wiring knobs (what can vary by env without changing meaning)

These are “how it runs” knobs:

1. **Registry DB wiring**

* DB endpoint(s), TLS, connection pool sizes, migration mode, query timeouts.

2. **Object store wiring**

* bucket/prefix roots, credentials injection, digest verification toggle **must stay ON** (that part is semantic), retry/backoff.

3. **Control-bus wiring (optional)**

* whether MPR broadcasts `registry_event` onto `fp.bus.control.v1` for cache invalidation, broker endpoints, topic names.

4. **Service sizing**

* concurrency, worker threads, request queue depth, CPU/mem limits (especially important if you add signature/digest verification on publish).

5. **Availability posture**

* local: single instance is fine
* dev: “prod-shaped” (independent service, real networking)
* prod: HA + backups are expected for authoritative services.

6. **Caching posture (consumer-side)**

* DF can either call resolve directly or cache and invalidate via registry events; prod typically prefers cache+invalidation to keep MPR off the hot path.

---

## 4) MPR policy-profile knobs (these *are* semantic and must be versioned + auditable)

These control what MPR will accept/activate and how it resolves.

### A) Lifecycle governance strictness

* Who may **publish** (MF principal allowlist)
* Who may **mutate lifecycle** (approve/promote/rollback/retire principals)
* Required “two-person rule” / approvals (optional, but policy-driven)
* Required reason codes / evidence refs for each action

### B) Evidence requirements (“no PASS → no ACTIVE” in registry form)

* What evidence is required before:

  * a bundle is merely **registered**
  * a bundle is **eligible**
  * a bundle can be **promoted to ACTIVE**
* What GateReceipt/PASS artifacts are required (policy-controlled)

### C) Compatibility strictness

* What constitutes “compatible” for J10 resolution:

  * feature group versions required
  * input contract version required
  * required capabilities (must respect degrade mask)
* Fail-closed vs explicit safe fallback policy (still must be explicit; never silent).

### D) Scope model

* What fields define ScopeKey (env always included conceptually),
* “one ACTIVE per scope” enforcement rules,
* whether “no active” is allowed as a state (I recommend **yes** for fail-closed).

### E) Deprecation windows

* time-bounded support windows for old bundle compatibility versions (prevents surprise incompatibility storms).

### F) Governance facts emission policy

* registry_event emission is non-negotiable; policy can tune **where** it’s delivered (audit sink only vs audit + control bus), sampling is not allowed for governance facts (they are “truth”).

---

## 5) Environment defaults for MPR (practical “direction”, not specs)

### Local (fast iteration, but rails must still exist)

* permissive auth **but still distinct roles**: publish vs resolve vs lifecycle mutation.
* allow “register but ineligible” bundles (so you can iterate)
* minimal HA (single DB, single registry instance)
* optionally skip control-bus broadcast (polling is fine)

### Dev (must catch prod failures)

Dev must catch: **unauthorized lifecycle changes, incompatible bundles, missing PASS evidence**.
So:

* “real enough” authz (separate principals, policy revs enforced)
* compatibility checks fully enforced
* evidence requirements close to prod (at least for promotion)
* prefer enabling registry_event broadcast for DF cache invalidation realism

### Prod (hardened governance)

* strict change control: promotions/rollbacks are governed facts; “no human memory”
* HA + backups for registry DB (because registry history is primary truth)
* control-bus broadcast for fast convergence is typical
* strict audit retention for registry events

---

## 6) “Other information to have in your head” before we open the box

### A) MPR’s outputs are **governance facts**, not “logs”

Registry must emit a durable policy fact per change:
`registry_event = {registry_event_id, actor_principal, governance_action, from→to, bundle refs/digests, scope, approval_policy_rev, reason, evidence_refs…}` 
That fact is what powers: explainability, rollback, DF cache invalidation, and “what changed?” debugging.

### B) Registry history is **not backfillable**

Backfills can rebuild derived stores, but **cannot** “rewrite” registry lifecycle history. So the registry DB needs backup/recovery posture in prod; you don’t treat it as rebuildable.

### C) Observability knobs you’ll want from day one

Minimum metrics for Registry are explicitly pinned: resolve latency, lifecycle mutation counts, incompatibility rejects. 
Traces should propagate end-to-end (DF spans include Registry calls).

### D) CI/CD must exercise “registry resolution at least once”

Your deployment notes pin that integration testing should run a small end-to-end flow that includes **registry resolution** (so you don’t build a registry that only works in prod).

---

If you keep just one mental model: **MPR is an always-on, low-QPS, authoritative control-plane service whose *policy profile* is the semantic knob and whose *wiring profile* is the operational knob; dev must enforce prod-like failures; prod must make every change a fact.**

---

## USER: PAUSE FOR REFLECTION

Absolutely — here’s the **outer-network “freeze frame” for MPR** (vertex still treated as opaque), written as a **drift guardrail**: what is pinned, what other components are allowed to assume, and what we are *not* allowed to accidentally invent when we step inside.

---

## 1) MPR’s outer-network identity and authority boundary

### What MPR *is* in the platform graph

MPR is the **only gate for deployable decision-logic changes**: it is the system-of-record for **bundle lifecycle** and **ACTIVE selection**. Anything that changes “what DF executes” must become an explicit, attributable registry lifecycle fact — not an implicit file swap or an implementation detail.

### Three operation classes (privilege separation is pinned)

1. **Resolve/Read** (DF)
2. **Publish bundle** (Model Factory) — *publish ≠ active*
3. **Lifecycle mutation** (approve/promote/rollback/retire) — privileged and auditable

If we violate this separation inside the component (e.g., “publish auto-activates”), we’ve drifted.

---

## 2) The complete pinned join surface around opaque MPR

### J16 — Model Factory → MPR (PublishBundle)

**Pinned meaning:** Model Factory publishes **deployable bundles + evidence for promotion**, and the “bundle” is a package: identity, immutable refs/digests, training provenance (DatasetManifests), evaluation evidence, required PASS/FAIL receipts under governance posture, and compatibility metadata. MPR owns ACTIVE and any promotion/rollback must be auditable.

### J10 — MPR → Decision Fabric (ResolveActive)

**Pinned meaning:** MPR returns a deterministic answer: an **ActiveBundleRef** (bundle id + immutable artifact refs + compatibility metadata). Resolution is deterministic (no “latest”), one active by rule per scope, and compatibility is enforced at the join (feature definitions + degrade constraints). DF must record the resolved bundle ref in decision provenance.

### Governance actor / controlled automation → MPR (Lifecycle mutation)

**Pinned meaning:** approve/promote/rollback/retire are privileged changes, attributable, and must emit an append-only registry event with actor + reason.

### MPR → Obs/Gov sinks (RegistryEvent emission)

**Pinned meaning:** Registry emits a minimum one-line **policy fact**:
`registry_event = {registry_event_id, actor_principal, governance_action=publish|approve|promote|rollback|retire, from_state->to_state, bundle_id + immutable refs/digests, scope, approval_policy_rev, reason, evidence_refs (eval + GateReceipt where required)}`

### Optional: MPR → fp.bus.control.v1 (control-facts broadcast)

**Allowed meaning:** low-volume control facts (including registry lifecycle events) may be broadcast for convergence/cache invalidation, but **broadcast is not the authority** — the registry’s durable history is.

### Production substrate attachments (still part of “outer reality”)

MPR is an **always-on service** with durable dependencies (authoritative DB + object store by-ref artifacts). Local may collapse, but the **deployment unit role** stays the same.

---

## 3) Rails that explicitly “bite” MPR at the boundary (non-negotiable)

These are not implementation preferences — they are outer-network laws:

* **Deterministic registry resolution** + **compatibility-aware** selection; never “latest”; fail closed or explicit safe fallback.
* **No PASS → no read is platform-wide**, and applies to deployable bundles (promotion/evidence posture must respect required PASS where policy demands it).
* **By-ref truth transport + digest posture:** refs/locators + digests across boundaries; digest mismatch is inadmissible.
* **Append-only + supersedes:** corrections are new records; registry lifecycle events are never silently mutated.
* **Quarantine is first-class:** if something is rejected, it must be explainable with durable reason/evidence pointers (no “drop and forget”).
* **Correlation is mandatory:** bundles must remain linkable to training runs, manifests, evidence, and decisions.

---

## 4) Paths/loops we’ve established and what *must remain true* about them

I’m not re-explaining each path; this is the **anti-drift “what these imply about MPR”** list:

* **#7 Learning→Deployable candidate:** MPR must be able to hold a bundle package that explicitly references **DatasetManifests** and evidence, so training/serving drift is traceable.
* **#8 Governed rollout:** “ACTIVE changed” must be explainable by **a registry_event** (actor + policy rev + evidence + reason).
* **#9 Runtime usage:** DF must record resolved bundle ref **and** the compatibility basis (feature group versions used + degrade posture) so decisions are replayable/explainable.
* **#10 Incident rollback:** rollback is just another governed lifecycle event; “what changed” must still be answerable.
* **#11 Environment promotion:** the platform meaning doesn’t fork by env; env differences are profile knobs. “Prod behavior” must be explainable as “same code + profile + governed artifacts.”
* **#12 Compatibility evolution:** when features or degrade constraints change, MPR must *block* unsafe bundles at resolution time (ACTIVE is necessary, not sufficient).
* **#13–#16 loops:** they all rely on: explicit replay basis (manifests), append-only governance facts, monotonic watermarks/backfill declaration, and the registry’s deterministic/compatibility-aware resolution.
* **#17 cache invalidation loop:** optional, but if used, it’s “notification”; authority remains the registry’s durable event history.

---

## 5) Drift traps (if we do any of these inside MPR, we’ve broken the outer network)

* “**Publish activates**” (breaks privilege separation + governance)
* “Resolve returns **latest**” (breaks deterministic resolution)
* “Resolve ignores **degrade mask** or feature-version compatibility” (breaks compatibility-aware resolution)
* “Bundle bytes can be **mutated in place**” (breaks append-only/supersedes + by-ref/digest posture)
* “Lifecycle changes occur without emitting a **registry_event** with `approval_policy_rev`” (breaks the choke-point policy fact requirement)
* “Policy config is **unversioned environment state**” (breaks explainability: you can’t answer ‘what rules were in force?’)

---

## 6) What is intentionally still free (so we don’t over-bind before we step inside)

We can choose these when illuminating internals **without changing outer meaning**:

* storage implementation (event-sourced vs relational tables, indexing strategies), as long as append-only governance facts exist
* API transport shape (HTTP/gRPC/CLI), as long as the join semantics and privilege tiers exist
* whether to broadcast registry events onto `fp.bus.control.v1` (optional)
* caching strategy (DF polling vs cache+invalidation), as long as DF can remain consistent and provenance stays correct

---

## 7) Environment ladder drift-check (before we go inside)

The ladder pin is explicit: **local/dev/prod must keep the same platform graph and join semantics**; only scale/retention/security/reliability/observability differ; promotion is profile posture, not meaning.

For MPR specifically, this means:

* **Scope includes environment** (in whatever form you implement), so “dev ACTIVE” and “prod ACTIVE” never collide while meaning stays identical.
* dev must catch prod-grade failures: unauthorized lifecycle changes, incompatible bundles, missing PASS evidence.

---

If this freeze-frame looks right to you, we’re ready to “enter the vertex” in the safest way: **derive the minimum internal subnodes strictly from these join obligations** (publish intake, lifecycle engine, deterministic resolver, event emission, policy profile reader) — without inventing new outward edges.

---

Yep — first-layer illumination = **identify the internal subnetworks (modules) that must exist inside MPR** to satisfy the *outer* joins/paths/loops **without inventing new external edges**. Each subnetwork below remains an **opaque box** for now. Everything here is derived from the pinned outer obligations: J16 publish, lifecycle mutation, `registry_event` emission, and J10 deterministic/compatibility-aware resolve (plus optional control-bus broadcast + env ladder posture).  

---

## MPR internal subnetworks (opaque boxes)

### 1) Front Door Ports

**Role:** implement the boundary *ports* cleanly and idempotently.
**Owns:** request normalization + idempotency keys + basic shape validation for:

* PublishBundle (J16)
* GovernLifecycle (approve/promote/rollback/retire)
* ResolveActive (J10)
* Audit/Query endpoints
* Event-feed endpoints (cursor/poll/stream) 

---

### 2) Policy & Authorization Gate

**Role:** enforce “who can do what” + “under which policy revision” as a first-class fact.
**Owns:** privilege tiers + `approval_policy_rev` binding for governed actions; reject/forbid outcomes (no silent accept). 

---

### 3) Bundle Intake & Attestation

**Role:** turn an inbound “bundle package” into an **immutable registered candidate** (or a durable rejection record).
**Owns:** by-ref + digest posture checks, completeness classification (“registered but ineligible” vs “eligible”), evidence references capture, compatibility metadata requiredness.
**Output:** an immutable “bundle record” reference used everywhere else. 

---

### 4) Lifecycle Engine

**Role:** the governed state machine per ScopeKey (“one ACTIVE per scope”) with explicit conflict handling.
**Owns:** approve/promote/rollback/retire semantics, linearization per scope, and the *only* place where ACTIVE changes are decided. 

---

### 5) Registry Ledger & Projections

**Role:** make MPR audit-real and drift-proof.
**Owns (authoritative):** append-only `registry_event` timeline (publish + lifecycle actions) and projections derived from it:

* ActiveIndex (current ACTIVE per ScopeKey)
* Eligibility/Status views (what’s promotable / why not)
* “Active at time/cursor” reconstruction for audit 

*(Key posture: history is authoritative; “current active” is a projection.)* 

---

### 6) Deterministic Resolver & Compatibility Checker

**Role:** serve J10: “what am I allowed to run now?”
**Owns:** deterministic selection + compatibility enforcement:

* ScopeKey lookup (via ActiveIndex)
* feature-definition/version basis checks
* degrade capabilities-mask checks
* fail-closed / explicit fallback signaling
  **Output:** ActiveBundleRef **plus a monotonic proof token** (cursor/event id) so DF can cache safely. 

---

### 7) Event Emission & Fanout

**Role:** deliver `registry_event` facts to the outside world reliably.
**Owns:** at-least-once delivery semantics, cursoring, and optional broadcast to `fp.bus.control.v1` for fast convergence/cache invalidation.  

*(Important: emission is **notification**; the authoritative truth is the ledger/DB.)* 

---

### 8) Audit & Explain Query Surface

**Role:** let ops/governance ask “what changed / why / what was active then?”
**Owns:** read-only queries powered by ledger/projections:

* bundle history + evidence pointers
* lifecycle timeline per scope
* active-at-cursor/time
* rejection reasons (first-class) 

---

### 9) Substrate Adapters

**Role:** the “plumbing boundary” to production substrates.
**Owns:** connectors + transactions against:

* Registry DB (authoritative)
* Object store (bundle/evidence blobs by-ref)
* Control bus (optional) 

---

## Minimal internal connectivity (still opaque boxes)

```text
        (J16 Publish)                 (J10 Resolve)                 (registry_event emit)
MF  -> [Front Door] -> [Policy/Auth] -> [Bundle Intake] -> [Ledger+Projections] -> [Emitter] -> sinks/(optional bus)
                                  \                     \
                                   \-> [Lifecycle Engine] -> (writes registry_event + updates projections)
                                                        \
                                                         -> [Resolver+Compat] -> DF
                                      \
                                       -> [Audit/Explain] (reads ledger/projections)
                          (All use Substrate Adapters to DB/ObjectStore/Bus)
```

 

---

## Environment ladder note (so we don’t drift later)

These subnetworks **exist in every env**; local/dev may *collapse them into one process*, but the **semantic boundaries** (privilege tiers, append-only governance facts, deterministic/compatibility-aware resolve) must remain identical. 

---

Yep. With the **internal subnetworks still opaque**, the next useful thing is to map the **internal joins (edges)** between those boxes, then the **internal paths** (multi-edge flows), and finally the **internal loops** (closed cycles that make it production-safe: retries, projections, reconciliation).

Everything below is driven by the pinned outer obligations: **publish bundles (J16), govern lifecycle, emit `registry_event`, resolve deterministically + compatibility-aware (J10)**.

---

## 0) One-line internal graph (boxes opaque)

```text
          (Publish / Govern / Resolve / Query)
                 |
                 v
 [Front Door] -> [Policy/Auth] -> +------------------------------+
                                 |                              |
                                 v                              v
                         [Bundle Intake]                 [Lifecycle Engine]
                                 |                              |
                                 v                              v
                           [Bundle Store]  --->  [Ledger + Projections]  ---> [Resolver+Compat] ---> (Resolve response)
                                                     |
                                                     v
                                               [Event Fanout] ---> (audit sinks, optional control bus)
                                                     ^
                                                     |
                                               [Audit Query]
```

* “Ledger + Projections” is the **internal truth spine** because registry changes must be **append-only governance facts** and corrections are by new records.
* Resolver must be **deterministic + compatibility-aware** and fail closed / safe fallback.

---

## 1) Internal joins (box-to-box edges)

I’m naming these **IJ#** so we can reference them later.

### IJ1 — Front Door → Policy/Auth

**Crosses:** caller principal + request class (publish / lifecycle / resolve / query) + idempotency key + request payload (normalized).
**Guarantee:** every request is classified into a privilege tier; policy revision binding is established here (“which rules are in force”).

### IJ2 — Policy/Auth → Bundle Intake

**Crosses:** “authorized publish” decision + `approval_policy_rev` (or equivalent policy binding) + validated PublishBundle package.
**Guarantee:** intake never guesses; it operates under an explicit policy revision.

### IJ3 — Bundle Intake → Bundle Store

**Crosses:** immutable bundle identity + refs/digests + lineage refs (DatasetManifests) + evidence refs + compatibility metadata + intake classification (eligible vs ineligible + reasons).
**Guarantee:** bundles are registered **immutably**; corrections are new versions, not edits.

### IJ4 — Bundle Store → Ledger + Projections

**Crosses:** “bundle registered” fact (and any “rejected/quarantined” fact), including the minimal `registry_event` fields for `governance_action=publish`.
**Guarantee:** publish is auditable and append-only.

### IJ5 — Policy/Auth → Lifecycle Engine

**Crosses:** authorized lifecycle action (approve/promote/rollback/retire) + target scope + target bundle ref + `approval_policy_rev` + reason + evidence refs.
**Guarantee:** lifecycle mutations are privileged and policy-bound.

### IJ6 — Lifecycle Engine → Ledger + Projections

**Crosses:** state transition fact(s) (append-only), plus the **“one ACTIVE per scope”** enforcement outcome (success or explicit conflict).
**Guarantee:** governed change is explicit; “ACTIVE changed” is always explainable by a registry event.

### IJ7 — Ledger + Projections → Resolver + Compatibility

**Crosses:** current ActiveIndex for a scope + bundle compatibility metadata + monotonic cursor/event token (“why this is true”).
**Guarantee:** resolver’s answer is stable and reproducible under a cursor.

### IJ8 — Policy/Auth → Resolver + Compatibility

**Crosses:** authorized read decision + (optional) active policy revision for resolution rules.
**Guarantee:** resolution rules are policy-shaped but policy-revision-traceable.

### IJ9 — Resolver + Compatibility → Front Door (response)

**Crosses:** ResolveActiveResponse = (RESOLVED + ActiveBundleRef + cursor) OR (NO_ACTIVE / INCOMPATIBLE + reason codes / safe fallback indicator).
**Guarantee:** **never** return ACTIVE-but-incompatible; fail closed or explicit fallback.

### IJ10 — Ledger + Projections → Event Fanout

**Crosses:** newly appended `registry_event`s (publish/approve/promote/rollback/retire) as an ordered stream (at least per scope) + cursor.
**Guarantee:** registry events are durable facts and can be consumed with a cursor.

### IJ11 — Event Fanout → Outside sinks (audit sinks, optional control bus)

**Crosses:** `registry_event` facts to Obs/Gov/Audit; optionally broadcast to `fp.bus.control.v1` (notification, not authority).

### IJ12 — Front Door / Policy/Auth → Audit Query

**Crosses:** read-only query requests (history, active-at-cursor, bundle metadata, rejection reasons).
**Guarantee:** audit/explain queries never mutate; they are powered by ledger/projections.

### IJ13 — Audit Query ↔ Ledger + Projections

**Crosses:** query plans and results: timelines, state-at-time/cursor, evidence pointers.
**Guarantee:** “what changed / who / why / under which policy rev” is answerable.

---

## 2) Internal paths (production flows through the internal graph)

These are the **multi-edge traversals** that correspond to the external join behaviors.

### IP1 — PublishBundle intake path (J16)

`Front Door → Policy/Auth → Bundle Intake → Bundle Store → Ledger+Projections → Event Fanout → (ack response)`

* Produces a `registry_event(publish)` no matter what (accepted/duplicate/rejected is still a fact).

### IP2 — Approve path (lifecycle)

`Front Door → Policy/Auth → Lifecycle Engine → Ledger+Projections → Event Fanout → response`

* Appends `registry_event(approve)` with policy rev + actor + reason/evidence refs.

### IP3 — Promote path (lifecycle)

Same as IP2, but lifecycle engine must enforce **one ACTIVE per scope** and append `registry_event(promote)` (including from→to state).

### IP4 — Rollback/Retire path (lifecycle)

Same as IP2, but appends `registry_event(rollback|retire)` and updates the ActiveIndex projection accordingly.

### IP5 — ResolveActive path (J10)

`Front Door → Policy/Auth → Resolver+Compat ↔ (Ledger+Projections) → response`

* Deterministic selection + compatibility check + cursor returned for caching/provenance.

### IP6 — RegistryEvent feed path (emit + consumption readiness)

`Ledger+Projections → Event Fanout → (audit sinks) (+ optional fp.bus.control.v1)`

* Delivery is at-least-once; dedupe is by `registry_event_id`; fanout supports cursoring.

### IP7 — Audit/explain query path

`Front Door → Policy/Auth → Audit Query ↔ Ledger+Projections → response`

* Used by ops/governance to answer “what was active then, and why?”

### IP8 — Rehydration / cold-start path (production reality)

`Ledger (history) → Projections rebuild → Resolver correctness restored → Fanout cursor restored`

* Required because MPR is always-on but must survive restarts without losing truth.

---

## 3) Internal loops (closed cycles that exist in production)

These are the “it keeps working under retries/failures/restarts” loops.

### IL1 — Event-sourcing loop (truth → projection → serve)

`append registry_event → update projections → resolver/audit reads projections → (repeat)`
This loop is what makes “append-only, corrections via new records” real and keeps ACTIVE reconstructable.

### IL2 — Fanout reliability loop (outbox-style)

`new registry_event → fanout attempt → (ack) mark delivered OR (fail) retry later`
At-least-once delivery is assumed; dedupe key is `registry_event_id`.

### IL3 — Idempotency loop (publish/lifecycle retries)

`duplicate request arrives → Front Door sees idempotency key / same bundle identity → returns existing outcome (no duplicate truth)`
This keeps MF/Gov retries safe.

### IL4 — Conflict loop (one ACTIVE per scope under concurrency)

`promote requested while another promote is in-flight → lifecycle engine detects conflict → returns explicit conflict → caller retries/chooses`
Prevents split-brain ACTIVE.

### IL5 — Policy revision loop (rules evolve without mystery)

`new policy/profile revision activated → Policy/Auth + Resolver use it → registry_event records approval_policy_rev for each action`
This is how you answer “what rules were in force?” across environments.

### IL6 — Reconciliation loop (self-healing after partial failures)

`periodic reconciler compares: ledger ↔ projections ↔ fanout cursor → repairs by replaying ledger`
This is what prevents “projection drift” from becoming a silent correctness issue. (Semantic requirement: no silent divergence; repair by replay.)

---

Yep — we’ll **illuminate IJ1–IJ4** as **internal boundary handshakes** (modules still opaque), and I’ll **pin what is “in-bounds” vs “drift”** so we don’t accidentally break the outer network.

For reference, these joins sit on the **PublishBundle spine**:

```
[Front Door] --IJ1--> [Policy/Auth] --IJ2--> [Bundle Intake] --IJ3--> [Bundle Store] --IJ4--> [Ledger+Projections]
```

Everything here is constrained by the platform rails: **governed change is explicit**, **append-only + supersedes**, **by-ref + digests**, **idempotency**, **policy rev traceability**, and “Registry is the only gate for decision-logic changes.”

---

# Before we start: 4 designer pins for IJ1–IJ4 (anti-drift)

### Pin IJ-P0 — Policy rev is bound once and carried forward

Once Policy/Auth picks the `approval_policy_rev` (or more generally “the policy revision in force”) for a request, **downstream modules must not re-evaluate under a different rev**. Every acceptance/denial outcome is traceable to that rev.

### Pin IJ-P1 — Publish does **not** activate (ever)

Publish creates a **candidate bundle record** only. Anything that makes bundles ACTIVE belongs to the lifecycle path, not the publish spine.

### Pin IJ-P2 — “Reject” must be explainable, but only *identified* things become registry facts

* If a publish request is identifiable (has bundle_id+version), then accept/duplicate/reject outcomes must be durable and explainable (no “drop and forget”).
* If a request is malformed *before identity exists* (no bundle_id/version), it becomes a security/ops log event, not a registry lifecycle fact.

### Pin IJ-P3 — Bundle immutability is enforced at the *Bundle Store boundary*

After IJ3 commits a bundle record, it is **immutable**. Corrections happen only as **new bundle versions** (supersedes), never mutation-in-place.

---

# IJ1 — Front Door → Policy/Auth

## Purpose

Convert “an incoming request” into a **policy-bound request context**:

* classify operation (publish vs lifecycle vs resolve vs query),
* bind identity + idempotency + correlation,
* bind the policy profile revision that must be used,
* fail early on missing/invalid *envelope* fields.

This is the internal counterpart of “choke points evaluate allowlists under policy rev and produce attributable outcomes.”

## What crosses IJ1 (the internal “RequestContext”)

At minimum:

* `request_class`: PUBLISH_BUNDLE | LIFECYCLE_MUTATION | RESOLVE_ACTIVE | AUDIT_QUERY
* `caller_principal` + authN result (who is asking)
* `idempotency_key` (explicit key if provided; otherwise derived, see below)
* `request_fingerprint` (stable hash over normalized payload for replay-safe dedupe)
* `trace_context` (trace_id/span_id for correlation)
* `normalized_payload` (canonicalized, no surprises)
* `policy_profile_id` + resolved `approval_policy_rev` (the revision in force)

### Idempotency precedence (designer pin)

For publish, idempotency must be stable under retries:

1. If caller supplies an explicit idempotency key → use it.
2. Else derive from `(bundle_id, bundle_version, request_fingerprint)` once those exist.

## Allowed outcomes at IJ1

* **PROCEED** with a complete RequestContext (goes to Policy/Auth)
* **REJECT_EARLY** for malformed/unparseable/identity-missing requests

### What is *not* allowed (drift)

* Front Door silently “fixes” payloads (e.g., invents bundle_id/version).
* Front Door chooses different semantics by environment (“if prod do X”). Profiles may change strictness, not meaning.

---

# IJ2 — Policy/Auth → Bundle Intake

## Purpose

Turn “a request” into an **authorized, policy-bound publish attempt**.

This join is where MPR enforces the platform pin: **Registry is the only gate for deployable truth changes**, and privilege tiers exist (resolve vs publish vs lifecycle mutation).

## What crosses IJ2 (the “AuthorizedPublishContext”)

* `authz_decision`: ALLOW | DENY
* `approval_policy_rev`: the revision used for the decision (must be recorded later)
* `reason_codes`: why allow/deny (policy-driven taxonomy)
* `publish_package`: validated minimum publish bundle package (identity + refs/digests + provenance/evidence refs + compatibility metadata)
* `request_context`: idempotency + trace + principal + request_fingerprint

### Evidence posture (designer stance, aligned to pins)

* **Publish may register “ineligible” bundles** (missing some evidence) as long as it’s explicit and durable.
* **Promotion requires required evidence** under approval policy (“no PASS → no ACTIVE” for bundles where policy demands PASS).

## Allowed outcomes at IJ2

* **ALLOW_PUBLISH** (go to Bundle Intake)
* **DENY_PUBLISH** (terminates publish; if bundle identity exists, a durable rejection fact will be recorded downstream)

### What is *not* allowed (drift)

* Bundle Intake re-evaluates authorization or swaps policy revisions.
* “Warn-only” authorization failures that still proceed. (Choke points must be explicit.)

---

# IJ3 — Bundle Intake → Bundle Store

## Purpose

Convert an authorized publish attempt into an **immutable bundle record** (or a durable rejection record), using the platform’s by-ref/digest posture and append-only correction rule.

## What crosses IJ3 (the “BundleRecord” write intent)

At minimum, Bundle Intake passes:

### A) Identity

* `bundle_id`
* `bundle_version`

### B) Artifact refs + digests (by-ref truth transport)

* list/map of artifact refs (object-store locators) + digests (content-addressed posture)

### C) Provenance refs

* training_run_id
* DatasetManifest refs (immutable training basis)
* eval report refs (and other evidence pointers)

### D) Compatibility metadata (required to be deployable)

* required feature group versions / schema expectations
* required capabilities
* input contract version expectation

### E) Intake classification (key for later lifecycle safety)

Bundle Intake must classify the candidate **without guessing**:

* `status`: REGISTERED_ELIGIBLE | REGISTERED_INELIGIBLE | REJECTED
* `ineligibility_reasons`: missing required evidence, missing compatibility fields, digest unverifiable, etc.
* `attestation_status`: VERIFIED | UNVERIFIED | FAILED
  (This allows “object store temporarily unavailable” to be represented safely as **UNVERIFIED → ineligible**.)

### F) Audit binding

* `submitter_principal`
* `approval_policy_rev`
* `submitted_at_utc` (request time)

## Bundle Store guarantees

* **Idempotent write** on `(bundle_id, bundle_version)`:

  * same content → return existing record (DUPLICATE)
  * different content → CONFLICT (explicit)
* **Immutability**: once written, bundle record is never mutated (corrections are new versions).

### What is *not* allowed (drift)

* “Update the bundle in place.”
* “Accept without compatibility metadata” and call it deployable.
* “Assume PASS” or “assume digests are fine.”

---

# IJ4 — Bundle Store → Ledger + Projections

## Purpose

Turn “bundle record committed (or rejected)” into the **append-only governance fact** stream + projections that power:

* audit (“what happened, who, why?”),
* deterministic resolution later,
* optional event fanout.

This aligns with the platform pin: **Registry must emit a one-line registry_event policy fact**.

## What crosses IJ4 (the “PublishEvent” write intent)

Bundle Store emits:

* `registry_event_id` (new)
* `governance_action = publish`
* `actor_principal` (submitter)
* `approval_policy_rev`
* `bundle_id + immutable refs/digests` (by-ref posture)
* `scope` field may be “N/A” for publish if you treat publish as scope-agnostic; if you require scope-at-publish, include it consistently (either way must be deterministic).
* `from_state -> to_state` (e.g., NONE→REGISTERED_ELIGIBLE, NONE→REGISTERED_INELIGIBLE, NONE→REJECTED)
* `reason` + `evidence_refs` (eval + gate receipts where applicable)

### Projection updates triggered by IJ4

Without opening the box, IJ4 must update at least:

* BundleIndex (bundle_id/version → bundle record ref)
* Eligibility view (why promotable or not)
* Publish timeline for audit queries

## Atomicity expectation (designer pin)

IJ4 must be **atomic** with bundle registration in the sense that:

* you don’t end up with a bundle record that has no corresponding publish registry_event, or vice versa.

(Implementation can be outbox/event-sourcing/retry, but the semantic guarantee must hold.)

### What is *not* allowed (drift)

* Publish succeeds but no durable registry_event exists (breaks “changes are facts”).
* “Publish registry_event” is emitted with a different `approval_policy_rev` than was used to authorize the publish.

---

## Quick environment ladder note for IJ1–IJ4

These joins must behave the same in local/dev/prod; only the **policy profile strictness** varies:

* Local may allow REGISTERED_INELIGIBLE more often (fast iteration).
* Dev must catch prod failures (unauthorized publishers, incompatible bundles, missing required evidence).
* Prod enforces strictest policy gates; every change remains an attributable fact.

---

Locked. We’ll illuminate **IJ5–IJ8** as **internal handshakes** (boxes still opaque), and I’ll **declare what is “in-bounds” vs “drift”** relative to the *outer* platform network.

These joins sit on the **Lifecycle + Resolve spine**:

```
[Policy/Auth] --IJ5--> [Lifecycle Engine] --IJ6--> [Ledger+Projections] --IJ7--> [Resolver+Compat]
      \                                                                 ^
       \--IJ8-----------------------------------------------------------/
```

They are constrained by the platform pins:

* **Registry is the only gate for production logic changes** (resolve/read vs publish vs lifecycle mutation) 
* Every lifecycle mutation is an append-only **registry_event** with `approval_policy_rev` etc.
* **Resolution is deterministic + compatibility-aware**, and must consider feature versions + degrade constraints; fail closed or explicit safe fallback.
* Rails (idempotency, append-only+supersedes, degrade mask hard constraint, deterministic registry resolution) are invariant across env ladder.

---

# Designer pins for IJ5–IJ8 (anti-drift)

### Pin L-P1 — Lifecycle actions are “policy-bound transactions”

Every lifecycle request is evaluated under a specific `approval_policy_rev`, and that exact rev must appear in the resulting `registry_event` (if any). No downstream re-evaluation under a different rev.

### Pin L-P2 — No-op requests do **not** create new registry events

Platform pin is “every **change** is a fact,” not “every request is a fact.” So idempotent retries must return the same result without appending extra events unless state actually changes.

### Pin R-P1 — Resolver answers from a consistent “registry snapshot”

Resolver must read ActiveIndex + bundle compatibility metadata as a consistent unit and return a monotonic proof token (cursor/event id) so DF can cache safely and provenance can cite “why this was true.”

### Pin R-P2 — Resolver never returns ACTIVE-but-incompatible

Compatibility-aware resolution is mandatory (feature versions + degrade posture constraints). If incompatible: fail closed or explicitly defined safe fallback—never “best effort proceed.”

---

# IJ5 — Policy/Auth → Lifecycle Engine

## Purpose

Turn “a privileged lifecycle intent” into an **authorized, policy-revision-bound, idempotent mutation request**.

This join exists because lifecycle mutation is the highest-privilege operation class in Registry.

## What crosses IJ5 (AuthorizedLifecycleAction)

**Minimum fields:**

### A) Identity + targeting

* `governance_action` ∈ {approve, promote, rollback, retire}
* `scope_key` (includes environment; one ACTIVE per scope)
* `target_bundle_ref` = (bundle_id + bundle_version)
  *(Lifecycle operates on a registered bundle; it cannot “activate a file path.”)*

### B) Authority + policy binding

* `actor_principal` (human approver or controlled automation principal)
* `approval_policy_rev` (explicit revision in force)
* `reason` + `reason_codes` (policy-driven taxonomy)

### C) Evidence pointers

* `evidence_refs` (eval refs and GateReceipt refs where required by policy)

### D) Idempotency & correlation

* `idempotency_key` + `request_fingerprint` + `trace_context`
  (Idempotency is a platform rail and must hold under retries.)

## Allowed outcomes at IJ5

* **ALLOW_LIFECYCLE_MUTATION** → enter Lifecycle Engine
* **DENY_FORBIDDEN** → stop; do not reach Lifecycle Engine

## Drift traps (not allowed)

* Policy/Auth “allows but doesn’t bind a policy rev.” (breaks auditability: can’t answer “what rules were in force?”)
* Lifecycle Engine accepts requests without `scope_key` (breaks “one ACTIVE per scope” determinism).

---

# IJ6 — Lifecycle Engine → Ledger + Projections

## Purpose

Convert “a successful lifecycle transition” into the **append-only registry_event fact** and update projections (especially ActiveIndex), preserving “one ACTIVE per scope.”

This join is the Registry analogue of IG receipts and AL outcomes: **choke point → one-line policy fact**.

## Preconditions Lifecycle Engine must enforce before it can emit

These are implied by the platform’s Registry compatibility pins:

* Target bundle exists and is not RETIRED (or is eligible for the intended transition).
* Promotion-time requirements satisfied:

  * compatibility metadata present (required) 
  * required evidence present (eval + GateReceipt where required)
* “one ACTIVE per scope” holds after the transition.

## What crosses IJ6 (TransitionEvent + ProjectionDelta)

### A) The `registry_event` (minimum pinned fields)

`registry_event = {registry_event_id, actor_principal, governance_action, from_state->to_state, bundle_id + immutable refs/digests, scope, approval_policy_rev, reason, evidence_refs}`

*(Note: “bundle_id + immutable refs/digests” means IJ6 must have access to the committed bundle record digest posture, not just id/version.)*

### B) Projection updates (opaque but required)

* **ActiveIndex update** (scope_key → active bundle ref)
* Lifecycle state view update (bundle state per scope)
* Optional: “current policy rev in force” view (for ops)

## Allowed outcomes at IJ6 (Lifecycle Engine view)

* **COMMIT_SUCCESS** → append registry_event + update projections
* **CONFLICT** (race on same scope) → explicit conflict response referencing the winning registry_event/cursor
* **PRECONDITION_FAILED** (missing evidence/compat, unknown bundle, invalid transition)
* **NO_OP** (idempotent repeat / already in desired state)

This aligns with “idempotency law” and “no split brain ACTIVE” posture.

## Atomicity expectation (designer pin)

A successful lifecycle transition must not result in “ACTIVE changed but no registry_event exists,” or “registry_event exists but projections don’t reflect it.” If anything breaks, repair is by replaying the ledger, not inventing state.

## Drift traps (not allowed)

* Promote changes ActiveIndex without emitting registry_event.
* Two actives per scope (ever).
* Promotion proceeds without compatibility metadata (explicitly invalid). 

---

# IJ7 — Ledger + Projections → Resolver + Compatibility

## Purpose

Give Resolver everything it needs to answer J10 deterministically, with compatibility enforcement, and with a proof token suitable for caching/provenance.

This join is where “append-only truth spine” becomes “safe executable choice.”

## What crosses IJ7 (ResolutionInputSnapshot)

Resolver receives a consistent snapshot containing:

### A) Active selection basis

* `scope_key`
* current active bundle pointer: (bundle_id + bundle_version + bundle_record_ref)
* monotonic **cursor** or “registry view token” (e.g., latest registry_event sequence for that scope)

### B) Bundle compatibility contract (from the bundle record)

* required feature group versions
* required capabilities
* input contract version expectation

### C) Safety posture hints

* eligibility state (if “no active” is allowed, represent it explicitly)
* optional: current deprecation windows / resolution policy parameters (policy-shaped, traceable)

## Guarantee of IJ7

Given the same `scope_key` and the same cursor + same caller-supplied compatibility basis (feature versions / degrade mask from DF), the resolver must return the same outcome. (This is the “no latest” deterministic contract.)

## Drift traps (not allowed)

* Resolver reads ActiveIndex at one moment and bundle compatibility metadata at another, producing a mixed answer (breaks determinism and caching safety).
* Resolver treats “ACTIVE” as sufficient and skips compatibility checks.

---

# IJ8 — Policy/Auth → Resolver + Compatibility

## Purpose

Ensure even “read/resolve” is:

* authorized (service principal),
* policy-revision traceable,
* and constrained by the current resolution policy posture (if policy shapes resolution behavior).

Outer pins explicitly call out operation classes and traceability of policy revs.

## What crosses IJ8 (AuthorizedResolveContext)

* `caller_principal` (DF service identity) 
* `authz_decision` (ALLOW/DENY)
* `resolution_policy_rev` (or reuse `approval_policy_rev` naming if you keep one rev family) 
* optional: resolution constraints from policy profile (e.g., “allow registry fallback bundles?”)
* correlation + trace context

## Guarantee of IJ8

Resolver can report (in logs/response metadata) **which policy rev** shaped the resolution decision, so operators can answer “why did this resolve yesterday but not today?”—the same reason IG receipts carry policy rev for schema acceptance.

## Drift traps (not allowed)

* Resolver behavior changes across envs without policy rev changes (breaks environment ladder invariants).
* “Read is unaudited / un-attributable.” (DF identity still matters as a principal.)

---

## Quick environment-ladder sanity for IJ5–IJ8

Same join semantics everywhere; only policy strictness differs:

* **Local:** permissive principals, but still distinct operation classes + policy rev binding exists.
* **Dev:** must catch prod-grade failures (unauthorized lifecycle changes, incompatible bundles, missing PASS evidence).
* **Prod:** strict change control; every mutation is a fact; strong authn/authz.

---

Locked. We’ll illuminate **IJ9–IJ13** as **internal boundary handshakes** (all nodes still opaque), and I’ll explicitly call out what is **in-bounds vs drift** relative to the *outer* platform network we froze.  

These joins sit on the **Resolve + Events + Audit** spines:

```text
[Resolver+Compat] --IJ9--> [Front Door]  (ResolveActive response)
[Ledger+Projections] --IJ10--> [Event Fanout] --IJ11--> (Audit sinks, optional fp.bus.control.v1)
[Front Door/Policy] --IJ12--> [Audit Query] <---IJ13---> [Ledger+Projections]
```

---

# Global pins for IJ9–IJ13 (anti-drift)

### Pin E1 — Cursor/proof token is mandatory for correctness in production

Anything that *serves* (resolve) or *emits* (registry events) must carry a monotonic **cursor/proof token** so consumers can cache, replay, and explain “why this was true.” 

### Pin E2 — Fanout is **notification**, not authority

If we broadcast to `fp.bus.control.v1`, it’s an optimization for convergence. The authoritative truth remains the registry’s durable history/projections.  

### Pin A1 — Audit queries are ledger-backed, never “log-backed”

Anything answering “what changed / who / why / under which policy rev” must be derived from the registry’s durable event history and projections, not best-effort logs. 

---

# IJ9 — Resolver + Compatibility → Front Door (ResolveActive response)

## Purpose

Return the **only permissible answer** for J10: a deterministic, compatibility-safe resolution result that DF can cite in provenance and cache safely. Determinism + compatibility-aware resolution are pinned. 

## What crosses IJ9 (ResolveActiveResponse)

Think of this as a stable “decision about deployable truth” envelope.

### A) Status (typed outcomes)

* `RESOLVED`
* `NO_ACTIVE` (scope has no active bundle)
* `INCOMPATIBLE` (active exists but cannot be used under supplied constraints)
* `FORBIDDEN` (caller not authorized)
* `TEMP_UNAVAILABLE` (optional; only when you can’t safely answer)

### B) If `RESOLVED`: the ActiveBundleRef (by-ref + digest posture)

* `bundle_id`, `bundle_version`
* immutable artifact refs + digests
* compatibility metadata (what it requires)
  This is what DF records. 

### C) Proof token / cursor (mandatory)

* `registry_cursor` (or equivalent) = “why this is true”
  This is what makes caching + audit sane. 

### D) Compatibility evaluation summary (needed to avoid hidden assumptions)

* `compat_basis_echo` (what DF supplied that mattered):

  * feature-definition basis / feature-group versions
  * degrade capabilities mask
* `compat_result` (if not RESOLVED):

  * missing feature groups / version mismatches
  * disallowed capabilities (by degrade mask)
  * contract mismatch indicator
* `reason_codes` (small taxonomy)

### E) Policy trace (recommended, drift-resistant)

* `resolution_policy_rev` (or reuse `approval_policy_rev` name family)
  So “why did it resolve yesterday but not today?” is answerable. 

## Guarantees (what’s in-bounds)

* **Never return ACTIVE-but-incompatible.** If incompatible → `INCOMPATIBLE` or explicit safe fallback (but fallback must be explicit, not silent). 
* **Deterministic for the same inputs.** For identical `(scope_key, compat_basis, degrade_mask)` at a given registry cursor, you must return the same result. 
* **Fail-closed over guessy.** `TEMP_UNAVAILABLE` is acceptable only when you cannot guarantee correctness; never “best effort resolve.” 

## Drift traps (not allowed)

* Returning “latest active” without cursor.
* Returning RESOLVED while omitting digests/refs (breaks by-ref + digest posture).
* Treating degrade mask as “advice” instead of a hard constraint. 

---

# IJ10 — Ledger + Projections → Event Fanout

## Purpose

Stream **newly appended** `registry_event` facts (publish/approve/promote/rollback/retire) into a fanout subsystem that can deliver them to sinks and optionally to the control bus. Emission of registry events is pinned. 

## What crosses IJ10 (RegistryEventBatch / Outbox feed)

* one or more `registry_event` records, each containing the pinned minimum fields:

  * `registry_event_id`
  * `actor_principal`
  * `governance_action` = publish|approve|promote|rollback|retire
  * `from_state -> to_state`
  * `bundle_id` + immutable refs/digests
  * `scope` (ScopeKey)
  * `approval_policy_rev`
  * `reason`
  * `evidence_refs` 
* a monotonic `cursor` (global or per-scope; either is fine as long as consumption is cursorable)

## Guarantees (what’s in-bounds)

* **Append-only feed:** fanout never edits events; it only ships what the ledger wrote. 
* **Cursorable consumption:** fanout can resume from cursor N after restart. (This is what makes production survivable.) 
* **At-least-once delivery assumptions:** duplicates are possible; dedupe key is `registry_event_id`. 

## Ordering stance (designer pin)

* Minimum requirement: **per-scope ordering** must be preserved (promote then rollback should not arrive reversed for the same scope).
* Global ordering across unrelated scopes is optional.

## Drift traps (not allowed)

* Emitting only “promote” events but not “publish/approve/rollback/retire” (breaks auditability).
* Fanout inventing or rewriting fields (e.g., changing `approval_policy_rev`). 

---

# IJ11 — Event Fanout → Outside sinks (Audit sinks, optional control bus)

## Purpose

Deliver registry events to:

1. **Audit/Obs/Gov sinks** (durable governance record consumption), and
2. optionally `fp.bus.control.v1` for fast convergence/cache invalidation.  

## What crosses IJ11

### A) To audit/obs sinks

* the same `registry_event` facts (no transformation that changes meaning)
* delivery metadata:

  * sink name
  * delivery attempt id
  * delivered cursor watermark

### B) To control bus (optional)

* `registry_event` as a **low-volume control fact** event
  (Transport is allowed; authority remains ledger.)  

## Guarantees (what’s in-bounds)

* **Notification, not authority:** consumers may use it to invalidate caches, but the canonical truth remains the registry DB/ledger.  
* **At-least-once delivery:** duplicates allowed; sinks dedupe by `registry_event_id`. 
* **Failure handling is explicit:** if a sink is down, fanout retries; if it can’t, it records undelivered status (so ops can see it).

## Drift traps (not allowed)

* Treating bus broadcast as “the” source of truth.
* Dropping events silently on sink failure (“logs will show it”). Audit requires durable facts. 

---

# IJ12 — Front Door / Policy/Auth → Audit Query

## Purpose

Support the “explainability contract”: ops/governance can ask *what changed, when, who did it, and why*, and can reconstruct *what was active at cursor/time*. This is pinned by the registry_event requirement and the platform’s governance posture. 

## What crosses IJ12 (AuthorizedAuditQueryRequest)

### A) Query identity & authorization

* `caller_principal`
* `authz_decision` (read privileges can be tiered)
* `policy_rev` for audit access rules (traceable)

### B) Query types (minimum set)

* `GetActive(scope_key, at_cursor | at_time)`
* `GetBundle(bundle_id, bundle_version)`
* `ListRegistryEvents(scope_key?, cursor_range?, time_range?, actions?)`
* `ExplainBundleLifecycle(bundle_id, bundle_version)` (timeline + reasons + evidence pointers)
* `ListRejections(scope_key? | publisher? | time_range?)` (first-class, no “lost rejects”)

### C) Consistency selector (key production knob)

* `as_of_cursor` (preferred) or `as_of_time`
  This is how you avoid “racey answers” while the system is changing.

### D) Paging

* `page_cursor`, `limit`

## Guarantees (what’s in-bounds)

* **Read-only:** audit queries never mutate state. 
* **Ledger-backed:** answers are derivable from ledger/projections (not best-effort logs). 
* **Explainable rejects:** if a publish/lifecycle request is rejected *after identity exists*, the reason/evidence pointers remain queryable (quarantine-first-class rail). 

## Drift traps (not allowed)

* “Active-at-time” computed from current ActiveIndex without using cursor/time semantics (gives wrong answers after rollbacks).
* Hiding `approval_policy_rev` / actor fields (breaks governance explainability). 

---

# IJ13 — Audit Query ↔ Ledger + Projections

## Purpose

This is the internal **truth retrieval join**: audit queries are answered using projections for speed but must remain faithful to the append-only ledger (and be repairable by replay).

## What crosses IJ13

### From Audit Query → Ledger/Projections

* a query plan:

  * which projection(s) can answer it quickly (ActiveIndex, BundleIndex, EventTimeline)
  * whether a ledger replay is required (e.g., “active at cursor N” if projection isn’t materialized at that cursor)
  * target cursor/time boundaries

### From Ledger/Projections → Audit Query

* query results containing (minimum):

  * `registry_event` timeline slices
  * state at cursor/time (active bundle ref, lifecycle state)
  * evidence pointers (eval refs, GateReceipt refs)
  * `approval_policy_rev`, `actor_principal`, reasons
    All of these are pinned fields for explainability. 

## Guarantees (what’s in-bounds)

* **Answerability:** “what changed / who / why / under which policy rev” is always answerable from durable facts. 
* **Projection correctness:** projections may lag temporarily, but correctness is guaranteed by replaying the ledger (reconciliation loop). 
* **Supersedes-aware history:** corrections are represented as new records/events; audit must surface the chain rather than mutating history. 

## Drift traps (not allowed)

* Projections becoming the “truth” and diverging from ledger without a replay-repair mechanism.
* Audit responses that can’t cite the governing registry_event(s). 

---

## Environment ladder sanity (for IJ9–IJ13)

Same semantics everywhere; differences are profile knobs:

* Local may not broadcast control events; prod typically does. 
* Dev/prod enforce stricter audit access and stronger guarantees around cursoring and event retention, but the meaning of the joins doesn’t change.  

---

Locked — let’s **illuminate IP1–IP4** as **production-grade internal flows** (modules remain opaque), using the **IJ1–IJ13 joins** we already pinned. I’ll be explicit about: **what moves, what gets committed, what becomes a `registry_event`, what is idempotent, and where conflicts/failures surface**.

These paths are the internal realizations of your pinned outer truths: Registry is the only gate for deployable logic changes; lifecycle changes are privileged/auditable; `registry_event` is the choke-point fact; and rails (idempotency, append-only+supersedes, by-ref+digest posture, deterministic resolution) must hold identically across environments.

---

## IP1 — PublishBundle intake path (J16 realized internally)

**External meaning:** MF publishes an immutable bundle package + evidence/compat metadata to Registry (publish ≠ active).

### Flow (happy path)

1. **Front Door** *(IJ1)*

   * Normalizes request, binds: `request_class=PUBLISH_BUNDLE`, `caller_principal`, `trace_context`, `idempotency_key` (caller-supplied or derived), `request_fingerprint`.
   * **In-bounds:** no payload invention; it only normalizes/canonicalizes.

2. **Policy/Auth** *(IJ1 → IJ2)*

   * Authorizes “publish bundle” for MF principal, binds **`approval_policy_rev`** (policy config is versioned and traceable).
   * Output: **AuthorizedPublishContext** = (ALLOW + policy_rev + reason codes).

3. **Bundle Intake & Attestation** *(IJ2 → IJ3)*

   * Validates package completeness under policy posture:

     * identity (`bundle_id`, `bundle_version`)
     * refs+digests (by-ref truth transport; digest mismatches are inadmissible)
     * lineage refs (DatasetManifests) + eval evidence refs
     * **compatibility metadata required** (feature versions/capabilities/contract)
   * Classifies outcome **without activating anything**:

     * `REGISTERED_ELIGIBLE` vs `REGISTERED_INELIGIBLE` vs `REJECTED`
     * with explicit `reason_codes` (e.g., missing evidence → ineligible; digest mismatch → reject).

4. **Bundle Store (immutable commit)** *(IJ3)*

   * Commits bundle record (by-ref + digests) **immutably**; corrections are new versions.
   * Idempotency on `(bundle_id, bundle_version)`:

     * **CREATED** (new)
     * **DUPLICATE** (same content) → return existing record
     * **CONFLICT** (same id/version, different content) → explicit conflict outcome

5. **Ledger + Projections (publish becomes a policy fact)** *(IJ4)*

   * Appends `registry_event(governance_action=publish, from_state->to_state, …, approval_policy_rev, reason, evidence_refs)` and updates projections (BundleIndex / Eligibility view).
   * Returns a **monotonic cursor / proof token** for later explainability/caching. 

6. **Event Fanout (notification path)** *(IJ10 → IJ11)*

   * Fanout ships `registry_event` to audit/obs sinks; optionally broadcasts on `fp.bus.control.v1` (notification, not authority).

7. **Ack response**

   * Returned once **bundle record + publish registry_event are durable**. Fanout delivery may lag; that’s OK because it’s notification.

### Idempotency / retry behavior (must hold)

* Retry with same `(bundle_id, bundle_version)` and same content → **DUPLICATE**: return the **original registry_event_id + cursor**, no new event. (Rails: duplicates don’t create different outcomes.)

### Failure surfaces (where the path stops)

* **Authz deny at Policy/Auth**: response FORBIDDEN; no bundle committed; no registry_event (no change occurred).
* **REJECTED at Intake/Store** (digest mismatch, missing compat contract, malformed refs): record a `registry_event(publish)` with `to_state=REJECTED` **only once per identifiable attempt**; retries are no-op returning the same rejection outcome.
* **CONFLICT** (attempt to overwrite identity): explicit conflict response; may emit a publish registry_event with reason code `IDENTITY_CONFLICT` (audit useful), but must not mutate the existing bundle record.

**Drift traps (not allowed):**

* “Publish auto-activates.”
* Accepting bundles without compatibility metadata (not deployable).
* Treating digest mismatches as warnings.

---

## IP2 — Approve path (lifecycle)

**External meaning:** privileged approval (human/automation) marks a candidate as approved under policy; emits an auditable registry event.

### Flow (happy path)

1. **Front Door** *(IJ1)*

   * Parses `governance_action=approve`, `scope_key`, `target_bundle_ref`, `idempotency_key`, `reason`.

2. **Policy/Auth** *(IJ5)*

   * Authorizes lifecycle mutation; binds **`approval_policy_rev`**.

3. **Lifecycle Engine** *(IJ5 → IJ6)*

   * Loads current lifecycle state for `(scope_key, bundle)` and checks preconditions (e.g., bundle exists; not retired; meets eligibility gates required for approval under policy).
   * Determines state transition: `REGISTERED_* → APPROVED` (scope-bound approval, since scope includes env).

4. **Ledger + Projections** *(IJ6)*

   * Appends `registry_event(approve)` with required fields, updates lifecycle projections.

5. **Event Fanout** *(IJ10 → IJ11)*

   * Ships event to sinks; optional broadcast to control bus.

6. **Response**

   * Returns `APPROVED` + `registry_event_id` + cursor.

### Idempotency / retry behavior

* Repeating approve for the same `(scope_key, bundle)`:

  * If already approved, return **NO_OP** with pointer to the existing approval event/cursor; do **not** append a new registry event. (Change-facts, not request-facts.)

### Failure surfaces

* Unauthorized → FORBIDDEN
* Unknown bundle / invalid scope → PRECONDITION_FAILED
* Not eligible under policy (missing required evidence to approve) → PRECONDITION_FAILED with reason codes

**Drift trap:** approval happening “implicitly” during publish.

---

## IP3 — Promote path (lifecycle; sets ACTIVE)

**External meaning:** governed activation changes deployable truth: **one ACTIVE per scope**; emits `registry_event(promote)`; DF later resolves deterministically.

### Flow (happy path)

1. **Front Door** *(IJ1)*

   * Request: `governance_action=promote`, `scope_key`, `target_bundle_ref`, `reason`, `idempotency_key`.

2. **Policy/Auth** *(IJ5)*

   * Authorizes promote; binds `approval_policy_rev`.

3. **Lifecycle Engine** *(IJ5 → IJ6)*

   * Preconditions (promotion-time enforcement is pinned):

     * bundle is APPROVED for that scope
     * required evidence exists (eval + GateReceipt where required)
     * compatibility metadata present (promotion without compat metadata is invalid)
   * Enforces **one ACTIVE per scope**:

     * if another bundle is ACTIVE, promote performs an explicit replace (atomic switch)
     * if none active, promote sets ACTIVE from NONE
   * Produces an atomic “active mapping delta” for projections.

4. **Ledger + Projections** *(IJ6)*

   * Appends `registry_event(promote)` capturing from_state→to_state and the scope; updates **ActiveIndex(scope→bundle)**.
   * (Allowed extension): include `replaced_bundle_ref` in the event payload for audit clarity.

5. **Event Fanout** *(IJ10 → IJ11)*

   * Ships the promote event; optional broadcast for DF cache invalidation.

6. **Response**

   * Returns `PROMOTED` + cursor.

### Idempotency / retry behavior

* Promote same target that is already ACTIVE → **NO_OP** with pointer to the existing promote event/cursor; no new event.
* Two promote requests race for same scope → explicit **CONFLICT** (no split-brain ACTIVE).

### Failure surfaces

* Missing evidence / missing compat metadata → PRECONDITION_FAILED
* Bundle not approved → PRECONDITION_FAILED
* Unauthorized → FORBIDDEN

**Drift traps (not allowed):**

* More than one ACTIVE per scope.
* Promote succeeds without emitting a registry_event.

---

## IP4 — Rollback / Retire path (lifecycle)

**External meaning:** controlled reversal or retirement; must be explicit, auditable, and update ActiveIndex accordingly.

### IP4a — Rollback

Rollback is effectively “promote a previous approved bundle,” but with `governance_action=rollback` so audit semantics are clear.

**Flow**

1. Front Door *(IJ1)*: `rollback`, `scope_key`, `target_bundle_ref` (or “previous approved”), reason, idempotency key
2. Policy/Auth *(IJ5)*: authorize + bind `approval_policy_rev`
3. Lifecycle Engine *(IJ5→IJ6)*:

   * Preconditions: target bundle exists, approved, not retired, still compatible-declared
   * Enforce one ACTIVE per scope, compute replacement delta
4. Ledger+Projections *(IJ6)*: append `registry_event(rollback)`; update ActiveIndex
5. Fanout *(IJ10→IJ11)*: ship event; optional control bus broadcast
6. Response: `ROLLED_BACK` + cursor

**Idempotency**

* Rolling back to already-active target → NO_OP, no new event.

### IP4b — Retire

Retire marks a bundle as ineligible for future activation.

**Flow**

1. Front Door *(IJ1)*: `retire`, `scope_key` (or global retire if you later choose), `target_bundle_ref`, reason
2. Policy/Auth *(IJ5)*: authorize + bind policy rev
3. Lifecycle Engine *(IJ5→IJ6)*:

   * Transition bundle state to RETIRED in that scope
   * If the retired bundle is currently ACTIVE, **two allowed postures**:

     * require a replacement in the same request (atomic “retire+switch”), **or**
     * allow scope to become **NO_ACTIVE** (fail-closed posture)
4. Ledger+Projections *(IJ6)*: append `registry_event(retire)`; update ActiveIndex (maybe to NONE)
5. Fanout *(IJ10→IJ11)*
6. Response: `RETIRED` (+ possibly `scope_now_has_no_active=true`)

**Designer pin (staying in-bounds):** “no active” is a valid safe state per scope; DF then fails closed or uses an explicitly defined safe fallback.

**Drift trap:** retiring a bundle by deleting history or mutating bundle bytes. (Append-only + supersedes is law.)

---

## Environment ladder sanity for IP1–IP4

These paths are **semantically identical** in local/dev/prod; env only changes **policy strictness, security posture, and operational envelope**, not meaning.
Dev must catch prod failures (unauthorized lifecycle actions, incompatible bundles, missing PASS evidence) while still letting local iterate fast.

---

Locked — illuminating **IP5–IP8** as **production-grade internal flows**, with all modules still **opaque**, but with explicit **what moves / what’s guaranteed / where it can fail / what makes it drift**.

These paths are the “serving + observability + survivability” half of MPR’s internal network, and they’re directly constrained by your pinned rails: deterministic/compatibility-aware resolution, append-only governance facts, cursorable event streams, and environment ladder invariance.  

---

## IP5 — ResolveActive path (J10 realized internally)

**Internal shape:**
`Front Door → Policy/Auth → Resolver+Compat ↔ (Ledger+Projections) → response`

### What this path exists to guarantee

DF gets a **deterministic, compatibility-safe** answer to “what bundle may I execute for this scope *under these constraints*?”, and DF can **cache** safely and **prove** later what it used via a cursor/token. 

### Step-by-step flow (happy path)

1. **Front Door (IJ1)**

   * Accepts ResolveActive request:

     * `scope_key` (must include environment)
     * `degrade_capabilities_mask` (hard constraint)
     * `feature_definition_basis` / feature-group versions basis (enough to check compatibility)
     * correlation (`trace_context`)
   * Normalizes the request to a canonical shape (no guessing).

2. **Policy/Auth (IJ8)**

   * Authz: DF principal allowed to resolve for that scope.
   * Binds `resolution_policy_rev` (or reuse `approval_policy_rev` naming family — but it must be traceable). 

3. **Resolver+Compat obtains a consistent registry snapshot (IJ7)**

   * Reads from **Ledger+Projections** a consistent snapshot for `scope_key`:

     * current ACTIVE bundle pointer (or explicit “NO_ACTIVE”)
     * bundle compatibility metadata
     * monotonic **registry_cursor** / proof token

4. **Resolver+Compat evaluates compatibility**

   * Checks:

     * feature-group versions required vs provided basis
     * required capabilities vs degrade mask
     * input contract version if applicable
   * Produces one of:

     * **RESOLVED + ActiveBundleRef + cursor**
     * **NO_ACTIVE + cursor**
     * **INCOMPATIBLE + cursor + reason codes**
   * **Pinned:** never return ACTIVE-but-incompatible; fail closed / explicit safe fallback only. 

5. **Response returned via Front Door (IJ9)**

   * Includes:

     * status
     * ActiveBundleRef (if resolved) with immutable refs/digests
     * `registry_cursor`
     * compatibility evaluation summary + reason codes
     * policy rev (recommended) 

### Idempotency / caching contract (production-real)

* For the same:

  * `scope_key`
  * `feature_basis`
  * `degrade_mask`
  * and same registry cursor
    → you must return the same response (deterministic).
    This is what makes DF caching safe and is required by your deterministic-resolution rail. 

### Failure postures (explicit)

* **FORBIDDEN**: authz denied (DF principal not allowed)
* **TEMP_UNAVAILABLE**: only if MPR cannot guarantee correctness (e.g., cannot read a consistent snapshot); never “best effort”
* **INCOMPATIBLE**: active exists but cannot be used under constraints (explicit reasons)
* **NO_ACTIVE**: scope deliberately has no active bundle (safe state)

### Drift traps (not allowed)

* “Resolve returns latest” (no cursor)
* “Resolve ignores degrade mask”
* “Resolve returns RESOLVED without digests/refs” (breaks by-ref + digest posture)
* “Resolve is non-deterministic due to time-of-day or local randomness” 

---

## IP6 — RegistryEvent feed path (emit + consumption readiness)

**Internal shape:**
`Ledger+Projections → Event Fanout → (audit sinks) (+ optional fp.bus.control.v1)`

### What this path exists to guarantee

Every publish/approve/promote/rollback/retire becomes a **durable governance fact** that can be consumed **cursorably** and delivered **at-least-once** to audit/obs (and optionally to the control bus for fast convergence).  

### Step-by-step flow

1. **Ledger appends registry_event** (happens in IP1–IP4 via IJ4/IJ6)

   * The ledger is the authority; events are immutable.

2. **Ledger+Projections exposes new events to Fanout (IJ10)**

   * Fanout reads:

     * event batch
     * monotonic cursor (global or per-scope; per-scope ordering must be preserved)

3. **Fanout delivers to sinks (IJ11)**

   * **Audit/Obs sinks**: mandatory
   * **Optional control bus**: `fp.bus.control.v1` low-volume broadcast for cache invalidation / convergence 

4. **Delivery tracking**

   * Fanout records delivery attempts and last-delivered cursor per sink.
   * Retries until delivered (at-least-once).

### Guarantees

* **At-least-once** delivery; duplicates possible; dedupe key is `registry_event_id`.
* **Cursor-based resumption** after restart.
* **Notification not authority** for control bus; registry DB/ledger remains truth.  

### Failure postures

* Sink down → fanout retries; non-delivery is visible (ops can see backlog)
* Control bus down → does not block registry correctness; only slows convergence

### Drift traps (not allowed)

* Dropping events silently (breaks governance-facts rail)
* Fanout “rewriting” events (e.g., changing policy rev fields)
* Treating control bus as the authoritative history 

---

## IP7 — Audit / explain query path

**Internal shape:**
`Front Door → Policy/Auth → Audit Query ↔ Ledger+Projections → response`

### What this path exists to guarantee

Operators can answer:

* “what is active now?”
* “what was active at cursor/time X?”
* “who changed it, why, under which policy revision?”
* “why was a bundle rejected/ineligible?”
  using **ledger-backed facts**, not best-effort logs. 

### Step-by-step flow (happy path)

1. **Front Door (IJ1)**

   * Accepts query with:

     * query type
     * filters (scope, bundle id/version, action types)
     * `as_of_cursor` or `as_of_time`
     * pagination cursor

2. **Policy/Auth (IJ12)**

   * Authz for audit reads (may be tiered)
   * Binds an audit access policy rev (traceable)

3. **Audit Query module issues ledger/projection query (IJ13)**

   * Uses projections for speed (ActiveIndex, BundleIndex, EventTimeline)
   * If query requires exact “state at cursor,” it must use the cursor semantics and, if necessary, reconstruct from ledger.

4. **Response**

   * Returns:

     * the relevant `registry_event` slice(s)
     * active mapping at cursor/time (if asked)
     * evidence pointers (eval refs, GateReceipt refs)
     * `actor_principal`, `approval_policy_rev`, reasons

### Guarantees

* **Read-only**
* **As-of semantics are honored** (cursor/time boundary)
* **Explainability**: responses always cite governing registry events and policy revs 

### Failure postures

* FORBIDDEN if caller not permitted
* BAD_QUERY for invalid filters/ranges
* TEMP_UNAVAILABLE only if ledger/projections cannot be read consistently

### Drift traps (not allowed)

* Answering “active at time X” from *current* ActiveIndex without cursor/time logic
* Omitting policy rev / actor fields
* Returning a state that cannot cite the governing registry_event(s) 

---

## IP8 — Rehydration / cold-start path (production survivability)

**Internal shape:**
`Ledger (history) → Projections rebuild → Resolver correctness restored → Fanout cursor restored`

### What this path exists to guarantee

MPR can restart (or scale out) and still be correct, because:

* history is append-only,
* “current state” is a projection,
* projections can be rebuilt from ledger,
* fanout can resume from last delivered cursor.  

### Step-by-step flow

1. **Boot: load durable anchors**

   * Discover latest ledger cursor (or per-scope cursors)
   * Load last-known projection checkpoints (if any)
   * Load fanout per-sink delivery cursors (outbox state)

2. **Projection rebuild**

   * Replay registry_event history (from checkpoint cursor to head) to rebuild:

     * ActiveIndex (one active per scope)
     * BundleIndex / lifecycle states
     * Eligibility view / rejection view
   * If projections are missing/corrupt, rebuild from genesis (slower but correct).

3. **Resolver readiness**

   * Resolver is not allowed to serve “RESOLVED” answers until it can read a consistent snapshot (ActiveIndex + bundle compat metadata) at a known cursor.
   * Until then: `TEMP_UNAVAILABLE` (fail closed). 

4. **Fanout readiness**

   * Fanout resumes from stored per-sink delivery cursor and continues delivering any undelivered events (at-least-once).
   * Control bus broadcast is optional; audit sinks are mandatory.

### Guarantees

* No split-brain ACTIVE after restart (replay enforces one active per scope)
* No lost governance facts (ledger is durable; fanout resumes)
* Correctness > freshness: serving may be temporarily unavailable rather than wrong 

### Drift traps (not allowed)

* Treating projections as authoritative without rebuild/reconcile capability
* Serving resolve responses before projections are consistent (“stale but fine” is not allowed for deployable truth)
* Resetting fanout cursors and silently re-emitting events without dedupe semantics 

---

## Environment ladder note for IP5–IP8

* **Semantics identical** across local/dev/prod.
* What changes: HA, retention, security strictness, and whether you enable optional control bus broadcast.
* Dev must be “prod-shaped enough” to catch incompatibility/evidence/auth failures; local can be lighter but must preserve the same meanings. 

---

Absolutely — illuminating **IL1–IL3** as **production loops** (all subcomponents remain opaque), but with the *exact* semantics they must enforce so we don’t drift from the outer network.

These three loops are the “platform-rail enforcement machinery” inside MPR:

* IL1 makes **append-only governance facts** real and keeps ACTIVE reconstructable.
* IL2 makes **event emission reliable** without making the bus authoritative.
* IL3 makes **retries safe** (no duplicate truth, no double-promotions).

---

# IL1 — Event-sourcing loop: truth → projections → serve

### The loop

`append registry_event → update projections → resolver/audit reads projections → (repeat)`

### What this loop exists to guarantee (pinned)

1. **History is the authority**: every meaningful change is captured as an immutable `registry_event` (publish/approve/promote/rollback/retire).
2. **Current state is derived**: “ACTIVE per scope” is a projection computed from the event stream.
3. **Rebuildability**: after restart/corruption, projections can be rebuilt by replaying the ledger, preserving “one ACTIVE per scope.”
4. **Explainability**: any “current answer” (resolve/audit) can cite the governing cursor/event(s).

This matches your governance rails: append-only + supersedes, deterministic resolution, and “changes are facts.” 

### Production semantics (how the loop must behave)

* **Single source of truth:** the ledger of `registry_event`s is authoritative; projections are caches/views.
* **Projection update rule:** each new event applies a deterministic transition to projections:

  * bundle index updates (bundle metadata, eligibility)
  * lifecycle state updates
  * ActiveIndex updates (scope → bundle or scope → NONE)
* **Per-scope linearity:** for a given `scope_key`, events must be applied in order; this is how you prevent split-brain ACTIVE.
* **Cursor discipline:** every projection state corresponds to a known **cursor** (or per-scope cursor), so “as-of cursor” queries and resolve caching are meaningful.

### What can be loose (implementation choice)

* Whether you store events in a dedicated “ledger” table or a log-like store, as long as the semantics above hold.
* Whether projections are updated synchronously with event append or asynchronously (as long as you have a clear “projection lag” posture and a rebuild path).

### Failure posture (must be explicit, fail-closed)

* If resolver cannot read a consistent projection snapshot at a known cursor, it returns **TEMP_UNAVAILABLE** rather than guessing. This preserves “deployable truth correctness > availability.”

### Drift traps (not allowed)

* Treating projections as authoritative without a replay/rebuild path.
* Allowing projection updates to “invent” state not backed by a registry_event.
* Resolving from “latest state” without being able to cite the cursor/event basis.

---

# IL2 — Fanout reliability loop: outbox-style delivery

### The loop

`new registry_event → fanout attempt → (ack) mark delivered OR (fail) retry later`

### What this loop exists to guarantee (pinned)

* **RegistryEvent emission is durable and complete** (auditability).
* Delivery is **at-least-once**; consumers dedupe by `registry_event_id`.
* Optional broadcast on `fp.bus.control.v1` is **notification**, not authority.

This aligns with your pinned “control facts” channel and audit fact posture.  

### Production semantics (the outbox contract)

* **Outbox feed:** fanout reads registry_events from the ledger using a cursor.
* **Per-sink watermark:** fanout maintains `last_delivered_cursor` per sink (audit sink(s), optional bus).
* **Delivery attempt rules:**

  * deliver event batch
  * on success: advance watermark
  * on failure: retry with backoff; do not advance watermark
* **Dedupe:** downstream dedupes by `registry_event_id`. Fanout itself may also dedupe for safety.

### Two required sink categories

1. **Audit/Obs/Gov sinks** (must exist; this is the governance record consumer)
2. **Optional control-bus sink** (`fp.bus.control.v1`) for fast convergence/cache invalidation

### Failure posture

* If control bus is down: registry correctness is unaffected; only convergence slows.
* If audit sink is down: fanout backlog grows and must be visible; you do **not** drop governance facts.

### Drift traps (not allowed)

* “Fire-and-forget” emission (loses events).
* Making the bus the authoritative history.
* Reordering events for the same scope at delivery time.

---

# IL3 — Idempotency loop: retries don’t create new truth

### The loop

`duplicate request arrives → Front Door detects idempotency key / identity → return existing outcome (no duplicate truth)`

### What this loop exists to guarantee (pinned)

Your platform assumes retries everywhere (at-least-once realities). Therefore:

* Publishing the same bundle twice must not create two different bundle truths.
* Approving/promoting/rolling back twice must not create two different “changes of truth.”
* Idempotent retries must return the same outcome (and, crucially, not append extra registry_events unless state changes).

### Production semantics (what is “same request”?)

There are two valid idempotency anchors:

**A) Explicit idempotency key** (preferred)

* Caller supplies an `Idempotency-Key` for publish/lifecycle actions.
* MPR stores outcome keyed by `(caller_principal, request_class, idempotency_key)`.

**B) Derived idempotency** (fallback)

* For publish: `(bundle_id, bundle_version, request_fingerprint)`
* For lifecycle: `(scope_key, governance_action, target_bundle_ref, request_fingerprint)`
  (Still stable under retries, but explicit keys are cleaner.)

### What the loop must do

* On duplicate request:

  * return the **previous outcome** (status + registry_event_id/cursor where applicable)
  * do **not** create a new bundle record
  * do **not** append a new registry_event unless the state actually changes

### Special cases (must be handled explicitly)

* **Publish duplicates**:

  * same id/version and same digests → DUPLICATE (return original publish outcome)
  * same id/version but different content → CONFLICT (explicit; never overwrite)
* **Lifecycle duplicates**:

  * promote already-active bundle → NO_OP (return pointer to the promote event/cursor that made it active)
  * approve already-approved → NO_OP
  * rollback to already-active target → NO_OP

### Drift traps (not allowed)

* “Every request emits an event” (breaks the meaning of registry_event as change fact).
* Allowing duplicates to create new events with new ids (breaks audit and caching).
* Silent conflict resolution (“last write wins”) on bundle identity or on per-scope ACTIVE.

---

## How these loops compose (why they’re separate)

* **IL1** guarantees internal truth correctness and reconstructability.
* **IL2** guarantees external observability/convergence without changing truth authority.
* **IL3** guarantees safety under retries so IL1’s ledger isn’t polluted with duplicate pseudo-changes.

---

Yep. We’ll illuminate **IL4–IL6** as **production loops** that operate *inside* the MPR vertex, with all nodes still opaque — but with **crisp semantics** so we don’t drift past the outer boundary pins (idempotency, append-only, policy-rev traceability, deterministic/compat-aware resolution, etc.).

---

# IL4 — Conflict loop (one ACTIVE per scope under concurrency)

### The loop

`(two lifecycle mutations collide on same scope) → lifecycle engine detects conflict → explicit conflict outcome → caller retries/chooses (with new idempotency intent)`

### Why this loop must exist

Your outer rails require:

* **1 ACTIVE per scope** deterministically (no split-brain), 
* **end-to-end idempotency** under retries (at-least-once reality), 
* and lifecycle changes are privileged + auditable (no silent outcomes).

So internal concurrency can’t be “last write wins” — it must be **linearized per scope**.

### Designer pin: “Scope-linearizability”

**All lifecycle mutations affecting a given `scope_key` are serialized.**
Implementation can vary (transactional lock, compare-and-swap, etc.), but the semantic is: *there exists a single total order of successful mutations per scope.*

### What counts as a “conflict”

Any of these overlapping in time for the **same `scope_key`**:

* promote vs promote
* promote vs rollback
* promote vs retire
* approve vs promote (if approve is a precondition and state changes underneath)
* rollback vs rollback, retire vs retire, etc.

### Conflict outcome contract (what the engine must return)

A **CONFLICT** is not just “409” — it must be *actionable* and *stable*:

**CONFLICT response must include:**

* `scope_key`
* `conflict_reason_code` (e.g., `SCOPE_MUTATION_RACE`, `ACTIVE_CHANGED`, `STATE_ADVANCED`)
* `current_scope_cursor` (the latest committed cursor/event seq for that scope)
* `current_active_bundle_ref` (or explicit NONE)
* `winning_registry_event_id` (if known)
  So the caller can decide: retry, choose another target, or stop.

### Idempotency interaction (hard pin)

For a given **idempotency_key**, MPR must never flip a result later:

* If a lifecycle request returns **CONFLICT**, repeating *the same request with the same idempotency key* must return the *same conflict outcome* (same “winning cursor” or a clearly defined stable marker).
* If the caller wants to attempt again after reading the new active state, they must do so with a **new idempotency intent** (new idempotency key), because it’s a new logical action.

This prevents accidental “one click became two promotes.”

### What must **not** happen (drift traps)

* Two actives per scope ever (even transiently). 
* “Last write wins” overwriting an ACTIVE mapping without an explicit lifecycle event. 
* Conflicts emitting `registry_event`s as if a change occurred (events are **change facts**, not request facts).

---

# IL5 — Policy revision loop (rules evolve without mystery)

### The loop

`new policy/profile revision activated → Policy/Auth + Resolver start using it → every outcome cites policy_rev → operators can answer “what rules were in force?”`

### Why this loop must exist

Your platform pins:

* **policy config is outcome-affecting, versioned, auditable**, not “environment state,”
* **components report which policy rev they used**, and registry events cite `approval_policy_rev`,
* promotion is **profile selection**, not code forks (no “if prod do X”).

So MPR must have a clean internal mechanism to *adopt* policy revisions and make that adoption observable.

### Designer pins for IL5

#### Pin P5.1 — Policy rev bound per request (no mid-flight swap)

When a request enters MPR and passes Policy/Auth, it is **bound** to a specific:

* `approval_policy_rev` (for publish/lifecycle actions),
* and `resolution_policy_rev` (for resolve) if you keep them distinct.

That rev must be carried through and cited in any resulting `registry_event` or resolve metadata.

#### Pin P5.2 — Policy rev adoption is explicit in service state

MPR must expose “what policy rev am I currently using?” as part of its operational state (health/readiness/info).
This is not an outer-domain fact, but it’s essential to avoid “mystery behavior” during rollouts.

#### Pin P5.3 — Policy changes follow propose→approved→active with rollback

Policy/profile revisions themselves follow the same governance shape you pinned: propose → approve → activate → rollback.
MPR doesn’t have to *own* that lifecycle, but it must **consume the active revision** deterministically.

### What the loop does in production

1. **A new policy/profile revision becomes ACTIVE** (via the policy-config lane).
2. **Policy/Auth starts evaluating under the new rev** for subsequent requests (publish/lifecycle/resolve).
3. Every new `registry_event` includes the `approval_policy_rev` used. 
4. (Recommended) Resolve responses include the policy rev used so “resolve changed” is explainable.

### Drift traps

* Policy rev is not recorded in `registry_event` (breaks explainability).
* Behavior changes across envs without a profile change (“prod-only semantics”).
* Requests are evaluated under one rev and the emitted event claims another (audit poison).

---

# IL6 — Reconciliation loop (self-healing after partial failures)

### The loop

`periodic reconciler compares: ledger ↔ projections ↔ fanout cursor → repairs by replaying ledger (and re-enqueueing fanout)`

### Why this loop must exist

Because your rails pin:

* **append-only + supersedes** for ledger-like truths (registry events included),
* **quarantine / no silent drops** at boundaries, 
* and registry is a **control-plane always-on authority** that must survive restarts without losing truth.

In production, partial failures happen:

* event appended but projection update crashed,
* projection corrupted,
* fanout fell behind,
* sink outage left undelivered events.

So MPR needs a loop that detects divergence and repairs *without mutating history*.

### Reconciliation invariants (designer pins)

#### Pin R6.1 — Ledger is the single source of truth

Reconciliation never “patches” ledger history. It repairs *derived* state by **replaying ledger events**.

#### Pin R6.2 — Resolver correctness beats availability

If projections can’t be trusted (unknown cursor / detected divergence), resolver must **fail closed** (`TEMP_UNAVAILABLE`) rather than serving potentially wrong ACTIVE answers.

#### Pin R6.3 — Fanout is repairable by re-delivery (at-least-once)

If a sink missed events, re-delivery is allowed; sinks dedupe by `registry_event_id`.

### What reconciliation checks (semantically)

At minimum it compares:

1. **Ledger head vs projection cursor**

* “Have projections applied all events up to ledger head (globally or per-scope)?”
* If not, replay from last good cursor.

2. **Projection invariant: one ACTIVE per scope**

* If projection says two actives, or differs from what ledger replay implies → projection is wrong → rebuild from ledger.

3. **Outbox/fanout completeness**

* For each sink, does `last_delivered_cursor` lag ledger head?
* If yes, fanout resumes at that cursor and ships remaining events.

4. **Orphan detection (optional but useful)**

* Bundle record exists but no corresponding `publish` registry event → fix by appending missing publish event only if the system can prove it should exist; otherwise quarantine the orphan and require operator intervention.
  (Reason: we cannot invent history. If we can’t prove, we quarantine.)

### Drift traps

* Silent divergence tolerated (“projection drift is fine”) — not allowed; must be repairable by replay.
* Reconciliation mutates bundle bytes or overwrites state in place (violates append-only/supersedes).
* Reconciliation treats control-bus broadcast as authoritative history.

---

## Environment ladder implications for IL4–IL6

These loops exist **in all envs** (same semantics), but the **operational envelope** changes:

* **Local:** may run reconciliation on startup/manual; concurrency is low; policy rev changes are infrequent.
* **Dev:** must surface the same failure modes prod would (conflicts, missing policy rev traceability, projection rebuild) so you catch drift early.
* **Prod:** continuous reconciliation + strong change control; “no human memory” (every change is attributable fact).

---

Yep — this is a good moment to **pin the “non-joins / forbidden edges”** (and a few “must-not-happen” non-paths) so we don’t accidentally smuggle extra coupling into the vertex when we go deeper.

I’ll split them into **outer-network non-joins** (component boundary) and **internal non-joins** (between your opaque subnetworks). Everything here is in service of the already-pinned rails: Registry is the deployable-truth choke point, deterministic resolution, append-only governance facts, by-ref+digest posture, and env-ladder invariance.  

---

## A) Outer-network non-joins for MPR (forbidden external edges)

### A1) MPR must not become a data-plane participant

**Forbidden:** MPR consuming business traffic, joining features, joining labels, or participating in event ingestion.
MPR is control-plane **deployable truth**, not a data-plane processor. 

### A2) No bypass of Registry for “what to execute”

**Forbidden:** DF selecting bundles by scanning object storage, “latest”, tags, or a config file.
**Allowed:** DF loads bytes **by-ref** only *after* MPR resolves ActiveBundleRef. 

### A3) Model Factory must not “deploy to DF”

**Forbidden:** MF pushing models/policies directly into DF runtime as an activation mechanism.
MF only publishes candidates to Registry; activation is governed via MPR lifecycle. 

### A4) MPR must not depend on EB as an authority source

**Forbidden:** MPR reading the control bus (or any bus topic) as “truth of ACTIVE.”
If MPR emits to `fp.bus.control.v1`, that’s **notification**, not authority.  

### A5) No “environment-only semantics”

**Forbidden:** prod-only logic paths (“if prod, allow X”; “if dev, skip compatibility”).
Env differences must be **profiles** (policy/wiring), not semantic forks. 

### A6) Registry history is not backfillable/mutable truth

**Forbidden:** “backfill” rewriting registry lifecycle history.
Backfill can regenerate **derived** stores, but registry governance facts are primary truth.  

---

## B) Internal non-joins inside MPR (forbidden edges between opaque subnetworks)

### B1) Publish must not touch ACTIVE

**Forbidden edge:** `Bundle Intake/Bundle Store → ActiveIndex (or Lifecycle Engine)`
Publish registers candidates only. Only the **Lifecycle Engine** can change ACTIVE. 

### B2) Resolver must be read-only

**Forbidden edges:**

* `Resolver → Ledger (append)`
* `Resolver → Projections (write)`
  Resolver never mutates state; it only reads a consistent snapshot and returns a deterministic answer. 

### B3) Audit Query must be read-only

**Forbidden edge:** `Audit Query → Lifecycle Engine`
Audit/explain is powered by ledger/projections only; no side effects. 

### B4) Event Fanout must not manufacture truth

**Forbidden edges:**

* `Fanout → Ledger (write)`
* `Fanout → Projections (write)`
  Fanout ships events; it doesn’t create, alter, or “correct” them. 

### B5) Policy/Auth must not “silently override” facts downstream

**Forbidden:** Policy/Auth re-evaluated later under a different policy revision for the *same request*.
Once a request is policy-bound, downstream modules must carry that binding (so `approval_policy_rev` in the emitted registry_event is truthful). 

### B6) Substrate adapters must not add hidden discovery behavior

**Forbidden:** “background scans” of object store to discover bundles or infer ACTIVE.
Only explicit publish/lifecycle events produce registry truth; no scanning-latest. 

### B7) Reconciliation must not invent or mutate history

**Forbidden:** reconciliation writing “patch events” unless it can prove they are required and deterministic.
The safe rule: reconcile by **replaying ledger** to rebuild derived state; never edit history. 

---

## C) Non-paths (must-not-happen flows)

### C1) “Resolve triggers promotion”

**Forbidden path:** `ResolveActive → Promote`
Resolution is not deployment; lifecycle mutation is privileged and explicit. 

### C2) “Publish triggers promotion”

**Forbidden path:** `PublishBundle → Promote`
Promotion requires privileged governance action and emits its own registry_event. 

### C3) “Control bus drives lifecycle”

**Forbidden path:** `fp.bus.control.v1 → MPR lifecycle state`
Notifications never drive authority state.  

### C4) “Silent compatibility downgrade”

**Forbidden:** returning a bundle even when incompatible, hoping DF handles it.
Compatibility-aware resolution must fail closed or explicitly route to a declared safe fallback. 

---

## USER: PAUSE FOR REFLECTION

Got it. Here’s the **“frozen reflection”** of what we’ve established so far — the *outer-network contract* for MPR, plus the *first-layer inner network* (opaque modules) and the *internal joins/paths/loops* that make the vertex production-real. This is the anchor I’ll keep in mind so we don’t drift as we go deeper.

---

## 1) What this vertex is in the platform network

**MPR = deployable-truth authority.**
It is the *only* gate that can change “what Decision Fabric executes.” Nothing else is allowed to smuggle model/policy activation through side channels (object-store scanning, config switches, MF pushing directly into DF, bus messages being treated as truth).

**Three operation classes are sacred:**

1. **Resolve/Read** (DF calls to get ActiveBundleRef)
2. **Publish** (MF registers candidate bundle packages; publish ≠ active)
3. **Lifecycle mutation** (approve/promote/rollback/retire; privileged + auditable)

This privilege separation is the single strongest anti-drift spine we’ve pinned.

---

## 2) Frozen outer boundary: the complete join surface around MPR

We pinned the full boundary surface of the vertex (MPR opaque), and agreed what is mandatory vs optional:

### Mandatory joins

* **J16 (Model Factory → MPR): PublishBundle**
  Bundle = immutable package *by-ref + digests*, with training lineage (DatasetManifests), eval evidence, receipts where policy requires, and compatibility metadata.
* **Lifecycle mutation (Gov actor/controlled automation → MPR):** approve/promote/rollback/retire
* **RegistryEvent emission (MPR → audit/obs sinks):** append-only governance facts for every *change* (and publish outcomes where identity exists)
* **J10 (DF ↔ MPR): ResolveActive**
  Deterministic + compatibility-aware + fail-closed/safe fallback; DF records resolved bundle ref in provenance.

### Optional but production-typical join

* **MPR → fp.bus.control.v1:** broadcast registry events for fast convergence/cache invalidation
  *Notification only*, never the authority.

### Production substrate attachments (still part of “production-ready reality”)

* **Registry DB** (authoritative lifecycle truth; one-active-per-scope constraints)
* **Object store** (bundle/evidence blobs by-ref; registry stores refs/digests)
* **Policy/profile config** (outcome-affecting, versioned, auditable; referenced by `approval_policy_rev`)

---

## 3) Pinned semantics that must never drift

These are the “word meanings” and laws that constrain everything:

### Bundle truth and immutability

* Bundle identity = `(bundle_id, bundle_version)`.
* Bundle contents are **immutable** once registered; “fix” is a new version (supersedes), not mutation-in-place.
* Bundle transport is **by-ref + digests**; digest mismatch is inadmissible.

### ACTIVE and scope

* **One ACTIVE per ScopeKey**.
* **ScopeKey includes environment** (local/dev/prod) to preserve ladder invariance while keeping meaning identical.

### Evidence posture

* Publish can register “ineligible” candidates, but **promote to ACTIVE is evidence-gated** under policy.
* Platform’s “No PASS → no read” expresses here as **“No required evidence → no ACTIVE.”**

### Compatibility posture

* Bundles must declare compatibility (feature-group versions, required capabilities, input contract version).
* **Resolve never returns ACTIVE-but-incompatible.** It fails closed or uses explicitly pinned safe fallback rules.

### RegistryEvent posture

* `registry_event` is the durable “change fact” for every lifecycle mutation (and publish outcomes where identifiable).
* Events are append-only; corrections are supersedes chains, not edits.

### Environment ladder invariant

* Same meanings everywhere; only profile strictness/wiring/HA/retention/obs depth changes.
  No “prod-only semantics.”

---

## 4) Outer paths and loops we mapped (what MPR enables end-to-end)

### Paths (#7–#12)

* **#7 Learning → deployable candidate:** Offline Shadow → MF → MPR publish
* **#8 Governed rollout:** promote → registry_event → DF resolves new active
* **#9 Runtime usage:** DF resolve → execute → record provenance (bundle ref + compat basis + degrade posture)
* **#10 Incident rollback:** signals → rollback → registry_event → DF resolves prior active
* **#11 Environment promotion:** same semantics; different environment scope (or separate stacks)
* **#12 Compatibility evolution / safe-block:** evolving features/capabilities → MPR blocks incompatible active → DF safe posture → new compatible bundle published/promoted

### Loops (#13–#17)

* **#13 Learning ↔ Serving:** DF provenance → Offline Shadow rebuild → MF → MPR → DF
* **#14 Governance/rollback loop:** promote → outcomes → rollback → …
* **#15 Drift prevention loop:** feature/capability evolution → block/upgrade → redeploy
* **#16 Backfill loop:** declared backfill → rebuild manifests → retrain → redeploy (no rewriting registry truth)
* **#17 Cache invalidation loop:** registry_event → control bus → DF invalidates → resolves fresh (optional)

These loops are why MPR must be “ledger + deterministic resolver,” not just a file store.

---

## 5) First-layer illumination inside the vertex: opaque internal subnetworks

We established the **minimal internal modules** MPR must contain to satisfy the above without inventing new external edges:

1. **Front Door Ports** (request normalization, idempotency handling, routing)
2. **Policy & Authorization Gate** (privilege tiers; policy revision binding)
3. **Bundle Intake & Attestation** (validate by-ref/digests; classify eligible/ineligible/rejected)
4. **Lifecycle Engine** (approve/promote/rollback/retire per scope; one-active-per-scope linearization)
5. **Registry Ledger & Projections** (append-only event spine + derived views like ActiveIndex)
6. **Deterministic Resolver & Compatibility Checker** (J10 semantics; fail-closed; cursor/proof token)
7. **Event Emission & Fanout** (deliver registry_event to sinks; optional control bus)
8. **Audit & Explain Query Surface** (active-at-cursor, timelines, reasons, evidence pointers)
9. **Substrate Adapters** (DB/object store/control bus connectors)

We kept these opaque to avoid overload, but forced their existence by outer obligations.

---

## 6) The internal network wiring we pinned (joins, paths, loops)

### Internal joins (IJ1–IJ13)

We named the “box-to-box” edges and pinned their semantics:

* **IJ1–IJ4:** publish spine
  Front Door → Policy/Auth → Bundle Intake → Bundle Store → Ledger+Projections
  Key pins: policy rev bound once, publish never activates, immutability at store boundary, publish becomes an auditable fact.

* **IJ5–IJ8:** lifecycle + resolve spine
  Policy/Auth → Lifecycle Engine → Ledger+Projections → Resolver+Compat (+ Policy/Auth → Resolver)
  Key pins: lifecycle is policy-bound transaction, no split-brain active, resolver reads consistent snapshot, never returns incompatible.

* **IJ9–IJ13:** response + events + audit
  Resolver → Front Door response; Ledger → Fanout → sinks/bus; Audit Query reads Ledger/Projections
  Key pins: cursor/proof token, fanout is notification, audit is ledger-backed.

### Internal paths (IP1–IP8)

* **IP1** PublishBundle intake path
* **IP2** Approve path
* **IP3** Promote path (sets ACTIVE)
* **IP4** Rollback/Retire path
* **IP5** ResolveActive path (J10 internal realization)
* **IP6** RegistryEvent feed path (emit & deliver)
* **IP7** Audit/explain query path
* **IP8** Rehydration/cold start path (rebuild projections; resume fanout; fail closed until consistent)

### Internal loops (IL1–IL6)

* **IL1** Event-sourcing loop: ledger → projections → serve
* **IL2** Fanout reliability loop (outbox-style at-least-once delivery)
* **IL3** Idempotency loop (retries don’t create new truth)
* **IL4** Conflict loop (scope-linearizability; explicit conflict outcomes)
* **IL5** Policy revision adoption loop (rules evolve without mystery; rev traceability)
* **IL6** Reconciliation loop (ledger ↔ projections ↔ fanout; repair by replay; no invented history)

These loops are the “production-hardening machinery” that make the vertex survivable.

---

## 7) Non-joins and forbidden paths we explicitly pinned

We pinned the “what must never exist” list to prevent accidental coupling:

* MPR is not data-plane (no traffic/features/labels ingestion or joins).
* DF must not bypass registry (no scanning object store, no “latest”, no config toggles for active).
* MF must not “deploy into DF” (publish only).
* Publish must not touch ACTIVE.
* Resolver and Audit are read-only (no writes).
* Fanout does not manufacture truth; control bus never becomes authority.
* Reconciliation never mutates history; repair is replay-based.

This non-join set is as important as the joins, because it prevents “hidden edges” from creeping in.

---

## 8) The remaining “still-free” choices (so we don’t overbind too early)

We deliberately left implementation-shaped choices open as long as semantics hold:

* Event-sourced vs relational implementation of the ledger/projections
* Global cursor vs per-scope cursor model (semantic requirement: cursorable + per-scope ordering)
* Whether to enable control-bus broadcast (#17) in v0 or keep it as v1+
* Whether “registry-provided fallback bundles” exist vs DF-only safe posture (we pinned “no silent fallback” either way)

---

## 9) What this reflection is for: the drift checklist I will enforce going forward

When we go deeper into any opaque box, I will continuously check:

* Does this new internal edge violate any non-join?
* Does it preserve: one-active-per-scope, append-only governance facts, policy rev traceability, deterministic compat-aware resolution, by-ref+digest posture, fail-closed behavior?
* Does it avoid inventing new *external* joins?

If any deeper design contradicts these, I’ll call it drift and pin a correction immediately.

---

Yep — this is the right moment to **pin the deployment posture + environment ladder knobs** for the MPR vertex *before* we go deeper into the nodes.

I’m going to lay down a **v0 production-shaped deployment stance** that Codex can implement against, while keeping tech choices flexible (Kafka/S3/Postgres “style”, not vendor-locked). This aligns with your deployment-tooling pins and the platform blueprint rails.

---

## 1) Deployment-unit stance for MPR

### Pin D-U1: MPR is an always-on control-plane service

MPR runs continuously (dev/prod; local may collapse) and provides:

* ResolveActive (read QPS)
* lifecycle mutation endpoints (low QPS, privileged)
* publish intake endpoint (job caller)
* registry_event emission (fanout worker)

### Pin D-U2: “One deployment unit, multiple internal workers” is the default

Codex should implement MPR as **one service** that can host:

* API server (Front Door)
* background “outbox/fanout” worker
* periodic reconciler (optional at first; can be enabled in dev/prod)

Local can run all of that in one process; dev/prod can run multiple replicas behind a load balancer *without changing semantics*.

---

## 2) Stateful substrate mapping for this vertex

### Pin D-S1: Registry DB is authoritative for lifecycle truth

MPR must use a transactional DB for:

* bundle lifecycle state + “one ACTIVE per scope” constraints
* append-only registry_event history (or equivalent authoritative timeline)
* idempotency outcome records (publish + lifecycle)

Deployment notes already map MPR to Postgres schema `registry` as authoritative.

### Pin D-S2: Object store is the by-ref blob substrate for bundles/evidence

* Bundle artifacts live under `registry/bundles/…`
* DB stores refs + digests; object store does not “own meaning,” the writer does (MPR/MF).

### Pin D-S3: Control-bus publish is optional but first-class

If enabled, MPR may publish lifecycle events to `fp.bus.control.v1` as low-volume control facts (for DF cache invalidation / fast convergence).
**But**: bus broadcast is **notification**, not authority (truth is DB + durable history).

---

## 3) Environment ladder knobs for this vertex

### Pin D-E1: Profiles, not code forks

Environments differ only by **profiles**:

* **Wiring profile**: endpoints, timeouts, scaling, etc.
* **Policy profile**: outcome-affecting rules (evidence requirements, lifecycle strictness, compatibility strictness, deprecation windows) — versioned and auditable.

### Pin D-E2: Policy revisions must be traceable

Every outcome-affecting decision must cite the policy revision used:

* `registry_event` includes `approval_policy_rev` (pinned in blueprint).
  (And for resolve responses, it’s strongly recommended to include a `resolution_policy_rev` for explainability, even if it’s the same revision family.)

### Pin D-E3: Secrets are never provenance

Secrets must never appear in bundles/manifests/registry events. Inject at runtime only; provenance may reference a secret *identity* (e.g., `key_id`) but never material. 

---

## 4) Recommended local/dev/prod defaults for MPR

These are defaults Codex can implement immediately via profiles:

### Local profile (fast iteration)

* Single-instance MPR + Postgres + MinIO + Redpanda
* Minimal auth (still keep operation class separation: publish vs lifecycle vs resolve)
* Fanout can be “best-effort” to local sinks, but **DB history is still authoritative**
* Control-bus broadcast optional

### Dev profile (must catch prod failures)

* “Prod-shaped” networking + durable volumes
* Strict-enough authz to catch unauthorized lifecycle changes
* Compatibility checks fully enforced (fail closed)
* Evidence gates enforced at least for promotion
* Prefer enabling control-bus broadcast so DF cache invalidation behavior is exercised

### Prod profile (hardened governance)

* HA DB posture + backups (registry truth is part of the “can’t lose this” set)
* MPR replicas for read scaling; lifecycle mutations remain scope-linearizable via DB constraints/transactions
* Fanout/outbox enabled (no lost registry_event emission)
* Strict policy profile + explicit change control (“changes are facts”)

---

## 5) Operational pins Codex should build toward

### Pin D-O1: Readiness gates are semantic (fail closed)

MPR should be “ready” only when:

* DB reachable + migrations applied
* it can enforce “one ACTIVE per scope”
* resolver can read a consistent snapshot
  Otherwise ResolveActive returns TEMP_UNAVAILABLE (better unavailable than wrong).

### Pin D-O2: Outbox-style fanout in prod shape

Registry events are the platform’s choke-point facts; emission must be durable:

* write event into DB (authoritative)
* separate delivery tracking per sink (audit sinks + optional control bus)
* at-least-once delivery; dedupe by `registry_event_id`

### Pin D-O3: Minimal observability contract for MPR

At minimum, emit metrics/traces for:

* resolve latency + outcome counts (RESOLVED/NO_ACTIVE/INCOMPATIBLE/FORBIDDEN)
* lifecycle mutation counts (approve/promote/rollback/retire) + conflicts
* fanout backlog / last delivered cursor per sink
  (OTLP everywhere is part of the platform assumptions.)

---

## 6) What Codex needs from you (deployment-wise)

Exactly as your tooling notes say:

1. one “bring up local infra” command (Compose)
2. local profile with endpoints + policy revs
3. one golden integration script that includes **registry resolve** at least once

---

Yep — that assumption is the right mental model: **illumination should not change the network**, it should only reveal the machinery that already *must* exist to satisfy the pinned joins/paths/loops (and we’ll treat any surprise dependency as drift and reject it).

## Internal nodes we’ve established (still opaque)

1. **Registry Ledger & Projections** (append-only `registry_event` spine + ActiveIndex/BundleIndex/etc.)
2. **Lifecycle Engine** (approve/promote/rollback/retire; one-ACTIVE-per-scope; conflict handling)
3. **Bundle Intake & Attestation** (validate publish package; by-ref+digest posture; eligible/ineligible/rejected classification)
4. **Bundle Store** (immutable bundle records; id/version idempotency; conflict detection)
5. **Deterministic Resolver & Compatibility Checker** (ResolveActive; fail-closed; cursor/proof token)
6. **Policy & Authorization Gate** (privilege tiers; policy rev binding; evidence/compat strictness rules)
7. **Event Emission & Fanout** (outbox-style delivery to audit sinks; optional control-bus broadcast)
8. **Audit & Explain Query Surface** (active-at-cursor/time; timelines; rejection reasons; evidence pointers)
9. **Front Door Ports** (request normalization; idempotency keys; routing; “no payload invention”)
10. **Substrate Adapters** (DB/object-store/control-bus connectors; wiring profile)

## The order I’d brainstorm/illuminate (minimizes drift)

1. **Ledger & Projections** (cursor model + what projections exist)
2. **Lifecycle Engine** (state machine + one-active-per-scope + conflicts)
3. **Bundle Store + Bundle Record shape** (immutability + idempotency + conflict rules)
4. **Bundle Intake & Attestation** (classification + digest/refs verification rules)
5. **Resolver & Compatibility** (exact compat inputs/outputs + reason taxonomy + fail-closed rules)
6. **Policy/Auth Gate** (policy profiles + rev binding across publish/lifecycle/resolve)
7. **Event Fanout** (outbox semantics + per-sink cursors + optional control-bus)
8. **Audit/Explain Surface** (query types + “as-of cursor” semantics)
9. **Front Door Ports** (idempotency wiring + request canonicalization)
10. **Substrate Adapters** (concrete wiring knobs; paths/prefixes; env ladder profiles)

If you’re ready, we start at **(1) Ledger & Projections**, because it’s the truth spine everything else hangs off.

---

Yep — we now “enter” **Ledger & Projections** and expose the machinery inside it, while keeping *its* internal pieces modular and not exploding into full specs.

## What this node must do (reminder)

Ledger & Projections is the **truth spine** of MPR:

* **Ledger**: an append-only, durable timeline of `registry_event`s (publish/approve/promote/rollback/retire) that makes “changes are facts” real.
* **Projections**: rebuildable read-models derived from the ledger that make **ResolveActive** and **Audit** fast and deterministic.
* **Rebuild/Reconcile**: after restarts/partial failures, restore correctness by replaying the ledger.

Nothing here changes the outer network; it just implements it.

---

## Designer pins for Ledger & Projections (v0, authoritative)

### Pin L1 — Two identifiers per event: `registry_event_id` + `event_seq`

* `registry_event_id`: immutable unique ID for dedupe and references (UUID-like).
* `event_seq`: **monotonic integer** assigned at append time; this is the **cursor** for “as-of” queries, fanout, and deterministic resolution.

Why: it gives you both *stable identity* and *ordered cursoring*.

### Pin L2 — Cursor model is **global**, with per-scope ordering guaranteed

We use a **single global `event_seq`**. Per-scope ordering is guaranteed because:

* lifecycle mutations are scope-linearized (IL4),
* events for the same `scope_key` are appended in that order.

(You can still maintain per-scope “head seq” as a projection for speed.)

### Pin L3 — Write path is “event + projection delta” in one DB transaction (v0)

When a publish or lifecycle mutation succeeds:

* append the `registry_event`
* update the necessary projection rows (ActiveIndex, lifecycle state, etc.)
  …**atomically**.

If the process crashes after commit, correctness is still recoverable by replay, but v0 avoids “event committed but projection lagged” complexity.

### Pin L4 — Projections are caches; ledger is authority

Any projection may be rebuilt from the ledger. If projection corruption/drift is detected, the fix is **replay** (never patch history).

### Pin L5 — Fanout reads from ledger; ledger never depends on fanout

Fanout delivery state is tracked, but emission is **notification**, not authority.

---

## Internal subnodes inside Ledger & Projections (one level deeper)

### 1) **Event Append Gate**

Opaque responsibility: accept “event intents” from publish/lifecycle flows and turn them into **committed ledger entries**.

* assigns `event_seq`
* enforces append-only (no updates/deletes)
* enforces basic invariants (required fields present)

### 2) **Registry Event Store**

Opaque responsibility: durable storage of the event stream.

Think: `registry_event` table (append-only), indexed by:

* `event_seq`
* `scope_key`
* `bundle_id/version`
* `governance_action`
* time

### 3) **Projection Engine**

Opaque responsibility: deterministic handlers that apply each event to read-model tables.

It owns:

* handler registry (which event types update which projections)
* deterministic application logic
* per-projection checkpoints (what `event_seq` has been applied)

### 4) **Core Projections**

These are the minimal read-models MPR needs in production:

* **ScopeHead**: `scope_key -> last_event_seq`
* **ActiveIndex**: `scope_key -> active_bundle_ref + active_set_event_seq`
* **BundleIndex**: `bundle_id/version -> bundle metadata needed by resolver/audit (including compatibility contract pointers/fields)`
* **BundleScopeState**: `(scope_key, bundle_id/version) -> lifecycle_state + last_state_event_seq`
* **EligibilityView**: `bundle_id/version -> eligible/ineligible + reasons` (or scope-aware if you decide eligibility depends on scope)
* **RejectionView**: durable record of rejected identifiable publish attempts (reason codes, policy rev)

### 5) **Cursor & “As-Of” Service**

Opaque responsibility: translate “as-of cursor/time” into consistent answers:

* “active at cursor N”
* “timeline slice from cursor A..B”

This is what makes audit/explain queries and reproducible resolution possible.

### 6) **Rebuild & Reconcile Supervisor**

Opaque responsibility: keep the system sane under restart and partial failure:

* rebuild projections by replaying ledger (from checkpoint or from genesis)
* verify invariants (one active per scope)
* detect drift between ledger head and projection checkpoints
* repair by replay (never mutate history)

### 7) **Fanout Cursor State**

This is *not* the fanout worker; it’s the durable per-sink cursor bookkeeping the fanout worker uses.

* `sink_id -> last_delivered_event_seq`
* backlog visibility

---

## Internal joins inside this node (box-to-box)

```text
  (from Publish/Lifecycle)
        |
        v
 [Event Append Gate] ---> [Registry Event Store] ---> [Projection Engine] ---> [Core Projections]
        |                        |                          |
        |                        |                          +--> [Projection Checkpoints]
        |                        |
        |                        +--> [Cursor/As-Of Service]
        |
        +--> [Fanout Cursor State]  (fanout worker reads this, but does not write the ledger)
```

---

## The 4 critical flows this node must support

### A) **Append event + update projections** (write correctness)

Input: an “event intent” (publish/approve/promote/rollback/retire), already authorized upstream.

Output (atomic):

* ledger row with `(registry_event_id, event_seq, …)`
* projection deltas:

  * update BundleScopeState
  * update ActiveIndex when promote/rollback/retire affects ACTIVE
  * update ScopeHead
  * update Eligibility/Rejection views as relevant

Invariant: if the event exists, projections can be made to match it (now or by replay).

### B) **Resolve support** (read correctness)

Resolver reads:

* ActiveIndex for `scope_key`
* BundleIndex for that bundle’s compatibility metadata
* returns the cursor `event_seq` that was the basis (“why this was true”)

Requirement: reads must be from a consistent snapshot (same DB transaction or equivalent).

### C) **Audit/explain support** (as-of correctness)

Audit Query asks:

* “active at cursor N” → Cursor/As-Of Service reconstructs from ledger/projections
* “who changed it and why” → event timeline slice by scope/bundle/action

Requirement: every answer can cite governing `registry_event_id` and policy rev.

### D) **Rehydration / rebuild** (survivability)

On restart:

* read ledger head `event_seq`
* for each projection, read last applied checkpoint
* replay events to catch up
* only then declare “ready to serve resolve” (fail-closed otherwise)

---

## Invariants this node enforces (drift detectors)

These are the “if violated, rebuild or fail closed” checks:

1. **Append-only**: no event updates/deletes.
2. **Monotonic cursor**: `event_seq` strictly increases.
3. **One ACTIVE per scope** in ActiveIndex.
4. **Projection determinism**: replaying the same event stream yields the same projection state.
5. **Cursor fidelity**: projection checkpoints never exceed ledger head.

---

## What stays flexible for Codex (implementation freedom)

* Relational tables vs event-store-like table layout (as long as append-only + cursor hold)
* Whether projections are updated synchronously (v0 pin) but implemented via triggers/outbox/worker
* Global cursor vs per-scope cursor: **I pinned global for v0**, but Codex can optimize later with per-scope materialized heads without changing semantics
* Exact indexing strategy (performance)

---

Yes — let’s “enter” the **Lifecycle Engine** and expose the machinery inside it, while keeping its internal pieces modular (still not a full spec).

Lifecycle Engine is the **only internal subnetwork allowed to change ACTIVE** (one-ACTIVE-per-scope), and every *successful* change must become an append-only `registry_event` fact with `approval_policy_rev`, actor, reason, etc. 

---

## What the Lifecycle Engine is responsible for

### Core responsibilities (pinned)

* Execute privileged actions: **approve / promote / rollback / retire** (per scope). 
* Enforce **scope linearizability**: one total order of lifecycle mutations per `scope_key` (prevents split-brain ACTIVE). 
* Enforce **one ACTIVE per scope** at all times. 
* Emit **exactly one change-fact `registry_event`** per successful state change (NO_OP and CONFLICT do not mint new change facts). 
* Remain **policy-bound**: the `approval_policy_rev` chosen upstream is the revision recorded in the resulting event. 

### Explicit non-responsibilities (anti-drift)

* Does **not** publish bundles (that’s Intake/Store).
* Does **not** resolve ACTIVE for DF (that’s Resolver).
* Does **not** “scan object store” or accept “latest”.
* Does **not** emit to the bus as authority (fanout is notification only).  

---

## Internal machinery (subnodes inside Lifecycle Engine)

Think of the Lifecycle Engine as these opaque sub-boxes wired together:

1. **Action Intake Adapter**

* Receives an **AuthorizedLifecycleAction** (from Policy/Auth via IJ5): `{scope_key, governance_action, target_bundle_ref, actor_principal, approval_policy_rev, reason, evidence_refs, idempotency_key}`.

2. **Idempotency Journal (Lifecycle)**

* Ensures retries don’t create extra transitions:

  * same idempotency key ⇒ return the **same outcome** (SUCCESS/NO_OP/CONFLICT/PRECONDITION_FAILED), and if SUCCESS, the same `registry_event_id`/cursor pointer.

3. **Scope Transaction Coordinator**

* The concurrency unit is **`scope_key`**.
* Establishes scope-linearizability (lock/transaction boundary) so two promotes can’t both “win”.

4. **Scope State Snapshot Reader**

* Reads current scope state required to plan transition:

  * current ACTIVE bundle (or NONE)
  * current scope “epoch/cursor” (for conflict detection)
  * current per-bundle lifecycle states (Approved? Retired?).

5. **Bundle Eligibility & Evidence Gate**

* Checks that the *target bundle* is allowed for this action under policy:

  * exists and is registered
  * not retired (unless policy allows “unretire”—v0: no)
  * promotion-time evidence present (eval + required receipts)
  * compatibility metadata present (required for promotion). 

6. **Transition Planner (State Machine Evaluator)**

* Determines `from_state -> to_state` for the target bundle (and implied secondary changes like demoting a prior active).

7. **Active Switcher**

* Applies the “one ACTIVE per scope” law:

  * promote/rollback sets ACTIVE to target bundle
  * previous active (if any) is demoted to APPROVED (no extra event; it’s implied by the promote/rollback event).

8. **Conflict Detector**

* If the scope changed since the request’s snapshot/epoch, returns an explicit **CONFLICT** including:

  * current active bundle
  * current scope cursor
  * winning event pointer (if known).

9. **Event + Projection-Delta Builder**

* Builds the **single change-fact** to be appended:

  * `registry_event(governance_action=approve|promote|rollback|retire, actor_principal, approval_policy_rev, scope, from_state->to_state, bundle refs/digests, reason, evidence_refs, …)` 
* Produces the minimal projection delta needed by Ledger+Projections (ActiveIndex, BundleScopeState, ScopeHead).

10. **Commit Executor**

* Performs the commit as an atomic unit with the ledger/projection system (v0 posture): either everything is durably true, or nothing is. 

---

## Minimal lifecycle state model (what it “reasons over”)

Two key “things” exist conceptually:

### A) **Scope state** (per `scope_key`)

* current `active_bundle_ref` (bundle_id/version or NONE)
* last scope cursor/epoch

### B) **Bundle state within scope** (per `(scope_key, bundle_id, bundle_version)`)

States (v0 minimal):

* `REGISTERED_ELIGIBLE` / `REGISTERED_INELIGIBLE` (comes from Intake; lifecycle can’t change eligibility by magic)
* `APPROVED`
* `ACTIVE`
* `RETIRED`

*(“REJECTED” is a publish outcome; it’s not a lifecycle state you can promote.)*

---

## Action semantics (state machine at a glance)

### `approve(scope, bundle)`

Preconditions:

* bundle exists + eligible (or policy allows “approve but not promotable” — v0: allow approve only if eligible)

Transition:

* `REGISTERED_ELIGIBLE -> APPROVED`
* If already APPROVED/ACTIVE: **NO_OP**

Emits:

* one `registry_event(approve)` on change. 

---

### `promote(scope, bundle)`  (sets ACTIVE)

Preconditions (promotion-time gates):

* bundle is APPROVED for that scope
* required evidence/receipts present per policy
* compatibility metadata present (required deployable contract) 

Transition:

* target: `APPROVED -> ACTIVE`
* previous active (if any): `ACTIVE -> APPROVED` (implied)

Emits:

* one `registry_event(promote)` including scope + bundle refs/digests + policy rev + reason. 

Conflict:

* if another promote/rollback won on same scope concurrently → **CONFLICT** (no event minted).

---

### `rollback(scope, bundle)`  (audit-distinct from promote)

Semantics are promote-like, but tagged `rollback` for clarity in audit.

Preconditions:

* target bundle exists + approved + not retired
* required evidence/compat still valid under policy

Transition:

* target becomes ACTIVE; previous active demoted to APPROVED.

Emits:

* one `registry_event(rollback)`.

---

### `retire(scope, bundle)`

Preconditions:

* bundle exists

Transition:

* bundle -> RETIRED (in that scope)

If retiring the currently ACTIVE bundle:

* **v0 pinned stance:** allow scope to become **NO_ACTIVE** (fail-closed state), or optionally allow “retire+switch” if target provided. (But never silent switch.) 

Emits:

* one `registry_event(retire)`.

---

## Internal dataflow diagram (still opaque sub-boxes)

```text
AuthorizedLifecycleAction (IJ5)
      |
      v
[Idempotency Journal] --dup--> (return prior outcome)
      |
      v
[Scope Txn Coordinator]  (serialize per scope_key)
      |
      v
[Scope Snapshot Reader] ---> [Eligibility+Evidence Gate] ---> [Transition Planner]
      |                                   |                         |
      |                                   +--precondition fail------+
      v
[Active Switcher] ---> [Conflict Detector] ---> (CONFLICT outcome)
      |
      v
[Event+Delta Builder] ---> (registry_event intent + projection delta)
      |
      v
[Commit Executor] ---> (success -> IJ6 to Ledger+Projections)
```

---

## Environment ladder note (deployment-aligned)

Lifecycle Engine semantics are identical in local/dev/prod; the **policy profile** changes strictness and the **scope_key includes environment**, so “dev ACTIVE” and “prod ACTIVE” never collide while meaning stays the same.  

---

Locked — we’re now “entering” **Bundle Store + Bundle Record shape** and exposing the machinery inside it.

This subnetwork’s job is **not** to decide ACTIVE or resolve compatibility at runtime. Its job is to make “a bundle” a **durable, immutable, content-identifiable thing** that the rest of MPR can safely reason over (lifecycle, resolver, audit).

---

## 1) What Bundle Store is responsible for

### Responsibilities (in-bounds)

* **Immutable registration** of bundle candidates keyed by `(bundle_id, bundle_version)`.
* **Idempotent writes**: retries don’t create new truth.
* **Conflict detection**: same id/version cannot be overwritten with different content.
* **Digest posture enforcement** for bundle artifacts and (optionally) a bundle-level manifest digest.
* Provide a **read surface** for:

  * Resolver (needs compatibility + artifact refs/digests)
  * Lifecycle Engine (needs “does this bundle exist / is it eligible / do required refs exist?”)
  * Audit (needs evidence pointers + lineage pointers)

### Non-responsibilities (anti-drift)

* **Does not activate** bundles (no writing ActiveIndex / no lifecycle transitions).
* **Does not decide** eligibility policy (it stores the outcome; Intake computes it).
* **Does not scan** object store (“latest” is forbidden).
* **Does not emit** registry events as authority (Ledger does; store only supplies facts).

---

## 2) Bundle Store internal machinery (subnodes)

Think of Bundle Store as these internal boxes (still modular):

1. **Canonical Bundle Assembler**

* Takes the intake’s validated package and produces a **canonical “BundleRecordDraft”** with stable field ordering and normalized forms (so hashes are stable).

2. **Bundle Fingerprinter**

* Computes a deterministic `bundle_fingerprint` (hash of the canonical draft).
* Optionally computes a `bundle_manifest_digest` if you write a bundle-manifest object (recommended).

3. **Idempotency & Identity Guard**

* Enforces uniqueness on `(bundle_id, bundle_version)`.
* If record exists:

  * same fingerprint ⇒ **DUPLICATE** (return existing record)
  * different fingerprint ⇒ **CONFLICT** (explicit; never overwrite)

4. **Integrity / Attestation Checker**

* Verifies “by-ref + digest posture”:

  * artifact refs are well-formed
  * digests exist where required
  * optionally: objects exist / digests match (or marks UNVERIFIED if the object store is temporarily unavailable)

5. **Record Writer (DB)**

* Writes the immutable `bundle_record` row(s) + indexes.
* Writes only once per id/version.

6. **Manifest Writer (Object Store)**

* (Optional but strongly recommended) writes a single **bundle manifest file** containing the canonical bundle record, so the bundle can be re-verified independently.
* Stores its digest in DB.

7. **Read Adapter**

* Fetches bundle records by id/version (and optionally by fingerprint/digest).

---

## 3) The BundleRecord shape (v0 authoritative)

This is the “minimum stable schema” that downstream relies on. Not a full spec — just the shape we’re pinning.

### A) Identity

* `bundle_id`
* `bundle_version`
* `created_at_utc`
* `submitted_by_principal`

### B) Content identity / immutability anchors

* `bundle_fingerprint` (hash of canonical record)
* `bundle_manifest_ref` (optional object-store ref)
* `bundle_manifest_digest` (optional, but if ref exists, digest is required)

### C) Artifacts (by-ref + digests)

A list/map of bundle artifacts (each entry):

* `artifact_role` (e.g., model_weights, policy_rules, thresholds, metadata)
* `artifact_ref` (object-store locator)
* `artifact_digest` (required for immutability)
* optional: `artifact_size`, `content_type`

### D) Compatibility contract (required to ever be deployable)

* `required_feature_groups` (ids + required versions)
* `required_capabilities` (the capabilities that must *not* be disabled by degrade mask)
* `input_contract_version`

### E) Provenance & lineage pointers

* `training_run_id` (or equivalent)
* `dataset_manifest_refs[]` (immutable training basis)
* optional: `code_artifact_ref` / `pipeline_rev` pointers (if you carry them)

### F) Evidence pointers (what justifies approval/promotion)

* `eval_evidence_refs[]` (reports/metrics)
* `gate_receipt_refs[]` (where policy requires receipts)

### G) Intake classification (stored, not invented later)

* `intake_status`: `REGISTERED_ELIGIBLE | REGISTERED_INELIGIBLE | REJECTED`
* `reason_codes[]` (why ineligible/rejected)
* `attestation_status`: `VERIFIED | UNVERIFIED | FAILED`

> Key pin: **Bundle Store never upgrades an ineligible bundle to eligible**. Only a new bundle version can change that.

---

## 4) The write path inside Bundle Store (what actually happens)

### WriteBundleRecord (the internal flow)

Input: `BundleRecordDraft` from Bundle Intake (already authorized + policy-bound upstream)

1. **Canonicalize** → compute `bundle_fingerprint`
2. **Check uniqueness** on `(bundle_id, bundle_version)`:

   * No existing record → proceed
   * Existing record with same fingerprint → DUPLICATE (return existing)
   * Existing record with different fingerprint → CONFLICT (stop)
3. **Integrity check**:

   * If object store reachable: verify refs exist + digests match → `VERIFIED`
   * If not reachable: do *not* guess → `UNVERIFIED` and likely mark `REGISTERED_INELIGIBLE`
4. **Commit immutable record** in DB
5. **(Optional) Write bundle manifest** object + store digest/ref
6. Return outcome:

   * `CREATED | DUPLICATE | CONFLICT`
   * include `bundle_record_ref` and `bundle_fingerprint`

### Atomicity pin with the ledger

For v0, we keep the clean posture:

* “bundle record committed” and “publish registry_event appended” must be *logically atomic* (same DB transaction family).
* If they ever diverge, reconciliation repairs by replay/quarantine — not by inventing history.

---

## 5) Conflict semantics (the core drift-preventer)

### CONFLICT definition (authoritative)

A conflict exists if:

* same `(bundle_id, bundle_version)` is presented again
* but `bundle_fingerprint` differs

Outcome:

* reject with `IDENTITY_CONFLICT` (or similar reason code)
* do not modify existing record
* this is *not* a lifecycle change and must not silently proceed

This is how you prevent “someone overwrote model bytes under the same version.”

---

## 6) How other internal nodes are allowed to use Bundle Store

### Resolver may read:

* compatibility contract
* artifact refs/digests
* fingerprint/manifest digest (for provenance)

### Lifecycle Engine may read:

* existence of bundle record
* intake status (eligible/ineligible) + reasons
* evidence pointers presence (it may require them per policy before promotion)

### Audit may read:

* full record + evidence + lineage pointers
* fingerprint/digest anchors

**No other node is allowed to:**

* mutate bundle record
* “fix” missing evidence inside the same version
* scan object store to discover bundles

---

## 7) Environment ladder stance for Bundle Store

* Bundle records are **environment-agnostic** candidates (same id/version can be approved/promoted in different env scopes).
* Environment separation happens in **ScopeKey** (lifecycle/projections), not by rewriting bundle records.
* Local/dev/prod can differ in attestation strictness *by policy profile*, but not in meaning.

---

### Quick internal diagram

```text
[Bundle Intake] 
    |
    v
[Canonical Assembler] -> [Fingerprinter] -> [Idempotency/Identity Guard]
                                     |                 |
                                     |                 +--> CONFLICT/DUPLICATE
                                     v
                           [Integrity/Attestation]
                                     |
                                     v
                              [Record Writer] -> (optional) [Manifest Writer]
                                     |
                                     v
                               BundleRecord (immutable)
```

---

If you want the next node to illuminate, the clean next step is **Bundle Intake & Attestation** (because it defines the admissibility checks + eligibility/rejection classification that feeds the Bundle Store).

---

Locked — we’re “entering” **Bundle Intake & Attestation** and exposing the machinery inside it.

This node is the **admission/quality gate** for *candidate bundle packages* at **publish time**. It decides (under a bound `approval_policy_rev`) whether a publish package becomes a **well-formed, immutable bundle record draft**, and whether that draft is **eligible**, **ineligible**, or **rejected** — **without** changing ACTIVE.

---

## 1) What this node must do (authoritative)

### Responsibilities

* **Normalize** the incoming publish package into a canonical internal form (stable hashing/fingerprinting).
* **Validate** required structure and semantics (no invented fields, no “best guess”).
* **Verify by-ref + digest posture** for bundle artifacts (attestation).
* **Apply policy-bound intake rules** (strictness comes from `approval_policy_rev`, not environment hacks).
* **Classify** outcome:

  * `REGISTERED_ELIGIBLE` (can proceed to lifecycle actions, subject to later approvals)
  * `REGISTERED_INELIGIBLE` (stored but cannot be promoted; reasons are explicit)
  * `REJECTED` (inadmissible package; do not store as a bundle version)
* Produce a **BundleRecordDraft** for Bundle Store (immutable commit) **plus** a structured “intake outcome” used by ledger/event emission later.

### Non-responsibilities (anti-drift)

* Does **not** approve/promote/rollback/retire (never touches ACTIVE).
* Does **not** emit registry events directly as truth (it prepares facts; ledger writes).
* Does **not** scan object store (“latest”) or “discover” bundles.
* Does **not** mutate previous bundle versions.

---

## 2) Inputs and outputs at the boundary

### Input (from Policy/Auth via IJ2)

**AuthorizedPublishContext** (already policy-bound):

* `caller_principal` (Model Factory principal)
* `approval_policy_rev`
* `idempotency_key` + `request_fingerprint` + `trace_context`
* `publish_package` (bundle identity + artifact refs/digests + lineage + evidence refs + compat metadata)

### Output (to Bundle Store via IJ3)

**BundleRecordDraft**:

* canonical bundle record (identity, artifacts, digests, compat contract, lineage/evidence refs)
* intake classification + reason codes
* (optional) a computed `bundle_manifest` (to be written later by Bundle Store)

Plus: **IntakeOutcome** for response/ledger fields:

* `intake_status` ∈ {ELIGIBLE, INELIGIBLE, REJECTED}
* `reason_codes[]`
* `policy_rev_used`
* `attestation_summary` (what was verified)

---

## 3) Internal subnodes (machinery) inside Bundle Intake & Attestation

Treat each as an opaque box for now; this is the minimal internal decomposition that keeps it production-real:

1. **Package Canonicalizer**

   * canonicalizes field order, normalizes refs, normalizes evidence pointer lists
   * produces a stable internal “canonical package” (so fingerprints are deterministic)

2. **Structural Validator**

   * checks presence and shape of mandatory fields:

     * `bundle_id`, `bundle_version`
     * artifact list/map
     * compatibility contract
     * evidence pointers (may be empty, but must be well-formed)
     * lineage pointers (policy-dependent requiredness)
   * rejects malformed packages early (no state change downstream)

3. **Policy-Bound Rule Evaluator**

   * takes `approval_policy_rev` and produces *intake rules*, e.g.:

     * which artifact roles are required/allowed
     * whether DatasetManifest lineage is mandatory for this publisher/slot
     * minimal evidence required for “eligible” classification (not for ACTIVE; just eligibility)
   * **Pin:** policy revision is bound once; downstream must not re-decide.

4. **Compatibility Contract Validator**

   * validates that compat contract exists and is complete:

     * required feature groups + versions
     * required capabilities
     * input contract version
   * **Pin:** missing compat contract is **REJECTED** (not a deployable candidate).

5. **Artifact Inventory Builder**

   * converts the package’s artifact section into a normalized inventory:

     * each item has `artifact_role`, `artifact_ref`, `artifact_digest`
   * checks:

     * role is known/allowed by policy
     * digest is present where required (v0: required for all deployable artifacts)

6. **Attestation Engine**

   * verifies by-ref + digest posture against the object store (conceptually):

     * object exists
     * digest matches (or object digest equals provided digest)
   * returns:

     * VERIFIED (all required artifacts verified)
     * FAILED (digest mismatch, missing object, malformed ref)
     * TRANSIENT_UNAVAILABLE (object store unreachable / timeout)

   **Designer pin (important):**

   * **TRANSIENT_UNAVAILABLE is not “ineligible.”** It is a *request failure* → publish should return a transient error and **not commit any bundle record**. This avoids “we registered a bundle only because infra was down.”

7. **Eligibility Classifier**

   * combines:

     * structural validity
     * compatibility validity
     * attestation result
     * policy-rule checks (lineage/evidence completeness)
   * outputs one of:

     * **REJECTED** (inadmissible)
     * **REGISTERED_INELIGIBLE** (admissible record, but cannot be promoted)
     * **REGISTERED_ELIGIBLE** (admissible and promotable *in principle*)

8. **Draft Builder**

   * produces the final BundleRecordDraft:

     * canonical fields
     * compatibility contract
     * artifacts + digests
     * lineage + evidence refs
     * intake_status + reasons
   * hands off to Bundle Store (which enforces immutability/idempotency/conflict)

---

## 4) The classification rules (what becomes REJECT vs INELIGIBLE)

### Hard REJECT (inadmissible; do not write a bundle version)

* malformed or missing `(bundle_id, bundle_version)`
* missing/invalid compatibility contract
* artifact digest missing (for required artifacts)
* artifact ref malformed
* artifact object not found (when object store is reachable)
* digest mismatch (inadmissible by posture)
* unknown/forbidden artifact_role (policy violation)

### Register but INELIGIBLE (admissible record, but cannot be promoted)

* verified artifacts + compat contract OK, but:

  * missing required evaluation evidence for “eligible” per policy
  * missing required receipts for eligibility (not necessarily promotion — policy-defined)
  * missing required lineage pointers (DatasetManifests) **if** policy says “must exist for this publisher/slot”
  * policy-gate failures like “manual approval required” or “staging-only”

### Transient failure (no state change)

* object store unreachable / timeout during required attestation
* policy profile store unreachable
* any condition where correctness can’t be guaranteed

---

## 5) Reason-code taxonomy (minimal, drift-resistant)

You’ll want these reason codes early because they power audit/explain and operator workflows.

**REJECT_*** (inadmissible):

* `REJECT_SCHEMA_INVALID`
* `REJECT_COMPAT_MISSING`
* `REJECT_COMPAT_INVALID`
* `REJECT_ARTIFACT_REF_INVALID`
* `REJECT_ARTIFACT_DIGEST_MISSING`
* `REJECT_ARTIFACT_NOT_FOUND`
* `REJECT_DIGEST_MISMATCH`
* `REJECT_ROLE_FORBIDDEN`

**INELIGIBLE_*** (registered but not promotable):

* `INELIGIBLE_EVAL_EVIDENCE_MISSING`
* `INELIGIBLE_RECEIPT_MISSING`
* `INELIGIBLE_LINEAGE_MISSING`
* `INELIGIBLE_POLICY_GATE_FAILED` (with subreason)
* `INELIGIBLE_MANUAL_APPROVAL_REQUIRED`

**TRANSIENT_*** (no commit):

* `TRANSIENT_OBJECT_STORE_UNAVAILABLE`
* `TRANSIENT_POLICY_STORE_UNAVAILABLE`

---

## 6) Internal flow diagram (still opaque subnodes)

```text
AuthorizedPublishContext
      |
      v
[Package Canonicalizer]
      |
      v
[Structural Validator] ----(malformed)----> REJECT (no commit)
      |
      v
[Policy-Bound Rule Evaluator] ---> [Compatibility Validator] --(missing/invalid)--> REJECT
      |
      v
[Artifact Inventory Builder] ---> [Attestation Engine]
      |                                |
      |                                +--(transient unavailable)--> TRANSIENT_FAIL (no commit)
      |                                +--(missing/mismatch)--------> REJECT
      v
[Eligibility Classifier] ---> (ELIGIBLE / INELIGIBLE / REJECT)
      |
      v
[Draft Builder] ---> BundleRecordDraft ---> Bundle Store (immutability/idempotency/conflict)
```

---

## 7) Environment ladder posture for this node

* **Semantics identical** across local/dev/prod (no forks).
* What changes is the **policy profile strictness**:

  * Local: allow more “registered but ineligible” (fast iteration)
  * Dev: must catch prod failures (compat missing, digest posture, missing required lineage/evidence)
  * Prod: strictest gates, but still the same meanings and outcomes.

---

If you want the next node to illuminate, the natural follow-on is **Resolver & Compatibility Checker**, because it consumes the compatibility contract and turns “ACTIVE” into a safe executable choice under degrade + feature-version constraints.

---

Absolutely. We’re now “entering” **Resolver & Compatibility Checker** and exposing the internal machinery that makes **J10 ResolveActive** true in production — while still keeping *its* internal pieces modular (opaque sub-boxes), not a full spec.

This node is the **read-side choke point**: it turns “ACTIVE is set” into “DF is allowed to execute this bundle *under these constraints*,” with **deterministic, compatibility-aware, fail-closed** semantics. 

---

## 1) What this node is responsible for

### Responsibilities (in-bounds)

* Serve **ResolveActive(scope_key, compat_basis, degrade_mask)** deterministically.
* Enforce compatibility at read-time:

  * required feature-group versions vs provided basis
  * required capabilities vs degrade mask (hard constraint)
  * input contract version compatibility
  * deprecation window / policy gates (if configured)
* Return:

  * **ActiveBundleRef** (id/version + immutable artifact refs/digests + compat metadata)
  * a **proof token** (monotonic cursor) suitable for caching + provenance
  * explicit non-resolution outcomes (**NO_ACTIVE**, **INCOMPATIBLE**, **FORBIDDEN**, **TEMP_UNAVAILABLE**) with reason codes.

### Non-responsibilities (anti-drift)

* **Never mutates** lifecycle state or projections (read-only).
* **Does not** “pick latest,” scan object storage, or infer ACTIVE from tags.
* **Does not** re-run bundle attestation against object store (that’s publish-time intake/attestation); at resolve-time it relies on immutable records and fail-closed if records are inconsistent.
* **Does not** silently “downgrade” requirements (no best-effort execution). 

---

## 2) Resolver input and output (what crosses the boundary)

### Input (from DF via Front Door / Policy/Auth)

Minimum required fields:

* `scope_key`
  (includes environment; one ACTIVE per scope was pinned earlier)
* `compat_basis` (DF’s “what’s in force” basis), at least:

  * `feature_group_versions` (or equivalent “feature definition set token”)
  * `input_contract_version` (if DF supplies/knows it)
* `degrade_capabilities_mask`
  (hard constraint; capability off ⇒ bundle requiring it is unusable)
* optional: `as_of_registry_cursor` (rare but valuable for replay/explain tooling; default “current head”)

Policy/Auth additionally binds:

* `caller_principal` (DF service identity)
* `resolution_policy_rev` (traceable policy revision shaping resolution behavior) 

### Output (ResolveActiveResponse)

* `status` ∈ {`RESOLVED`, `NO_ACTIVE`, `INCOMPATIBLE`, `FORBIDDEN`, `TEMP_UNAVAILABLE`}
* `registry_cursor` (monotonic proof token; v0 uses the ledger’s `event_seq`)
* if `RESOLVED`: `ActiveBundleRef`:

  * `bundle_id`, `bundle_version`
  * immutable `artifact_refs + digests`
  * compatibility contract (echoed or referenced)
  * optional: `bundle_fingerprint` / `bundle_manifest_digest` anchors
* `reason_codes[]` + `compat_summary` (especially on non-RESOLVED)
* recommended: `resolution_policy_rev` echo (for explainability)

This matches the pinned requirement that resolution is deterministic + compatibility-aware and must support caching/provenance. 

---

## 3) Internal machinery (subnodes inside Resolver & Compatibility)

Treat each as an opaque box for now; together they implement IP5.

### 1) **Resolve Request Canonicalizer**

* Normalizes incoming resolve request:

  * canonicalizes feature group version map ordering
  * normalizes degrade mask representation
  * validates presence of `scope_key`
* Produces a stable `resolve_request_fingerprint` (for debugging/correlation, not for state).

### 2) **Authz/Policy Context Binder**

* Confirms read authorization (DF principal) and attaches:

  * `resolution_policy_rev`
  * any policy-shaped resolution rules (e.g., “allow registry-declared fallback?”)

> Pin: policy revision is bound once; downstream doesn’t silently swap it.

### 3) **Snapshot Reader**

Reads a **consistent registry snapshot** (as-of cursor) from Ledger+Projections:

* ActiveIndex: `scope_key -> active_bundle_ref | NONE`
* BundleIndex: bundle compatibility contract + artifact refs/digests (for that bundle)
* ScopeHead / cursor: the `event_seq` at which the snapshot is valid
* Optionally, the **event that set ACTIVE** (`active_set_event_seq` / `active_set_event_id`) for provenance

> Pin: resolver must not read “ACTIVE” from one cursor and bundle metadata from another (mixed snapshot is drift).

### 4) **Candidate Selector**

* If ActiveIndex says NONE → `NO_ACTIVE`
* Else produces a single candidate bundle ref (because “one ACTIVE per scope” is enforced elsewhere)

### 5) **Compatibility Evaluator**

Pure function that checks candidate bundle against constraints:

Checks (v0 minimum):

* **Capabilities check**: `bundle.required_capabilities ⊆ enabled_capabilities(degrade_mask)`
* **Feature-version check**: `bundle.required_feature_groups` satisfied by `compat_basis.feature_group_versions`
* **Input contract check**: bundle’s `input_contract_version` compatible with DF’s (exact match v0; policy may later allow compatible ranges)
* **Deprecation window check** (policy-shaped): if bundle compatibility is expired under current profile → incompatible

Outputs:

* PASS or FAIL
* structured failure details (missing groups, version mismatches, disabled capabilities, contract mismatch)

### 6) **Fallback Resolver (explicit, optional)**

Default v0 stance remains: **fallback lives in DF safe posture**, triggered by explicit non-resolution.
If you later enable registry-defined fallback bundles, they must be:

* explicitly declared in policy/profile
* resolved deterministically
* still compatibility-checked (no magic “backup”)

This subnode either:

* does nothing (v0), or
* chooses a declared fallback candidate and re-runs compatibility evaluation.

### 7) **Response Builder**

* Builds ResolveActiveResponse with:

  * status
  * cursor/proof token
  * ActiveBundleRef if allowed
  * reason codes and compat summary
  * policy rev echo

### 8) **Cache Advisory Generator (read-only hints)**

Produces optional hints DF can use:

* `etag = registry_cursor` (or `active_set_event_seq`)
* `scope_head_seq`
* “not modified since” semantics
* recommended cache key components: `(scope_key, feature_basis_token, degrade_mask_id, registry_cursor)`

> This keeps MPR off the hot path without changing semantics.

---

## 4) Reason-code taxonomy (minimal, drift-resistant)

These reason codes are what prevent opaque “it failed” outcomes.

### `NO_ACTIVE_*`

* `NO_ACTIVE_SCOPE_EMPTY` (scope intentionally has no active)
* `NO_ACTIVE_SCOPE_UNKNOWN` (scope key invalid / not configured — policy-dependent)

### `INCOMPATIBLE_*`

* `INCOMPATIBLE_CAPABILITY_DISABLED:<cap>`
* `INCOMPATIBLE_FEATURE_GROUP_MISSING:<group>`
* `INCOMPATIBLE_FEATURE_VERSION_MISMATCH:<group>:need=X:have=Y`
* `INCOMPATIBLE_INPUT_CONTRACT_MISMATCH:need=X:have=Y`
* `INCOMPATIBLE_DEPRECATED` (outside allowed deprecation window)
* `INCOMPATIBLE_POLICY_BLOCKED` (policy says “do not use this bundle under current mode/profile”)

### `TEMP_UNAVAILABLE_*` (fail-closed; no guessing)

* `TEMP_UNAVAILABLE_SNAPSHOT_READ_FAILED`
* `TEMP_UNAVAILABLE_POLICY_STORE_UNAVAILABLE`
* `TEMP_UNAVAILABLE_PROJECTION_INCONSISTENT` (detected cursor mismatch)

### `FORBIDDEN_*`

* `FORBIDDEN_CALLER_NOT_AUTHZ`
* `FORBIDDEN_SCOPE_NOT_ALLOWED`

---

## 5) Determinism contract (the key “no drift” guarantee)

### Deterministic mapping (authoritative)

For a fixed:

* `scope_key`
* `compat_basis` (feature group versions + contract basis)
* `degrade_mask`
* `as_of_registry_cursor` (explicit or implicit current head)

the resolver must return the **same**:

* `status`
* `ActiveBundleRef` (if resolved)
* `reason_codes`
* `registry_cursor`

No time-of-day, no random fallback, no “latest.”

This is the internal embodiment of the platform’s deterministic registry resolution rail. 

---

## 6) Failure posture (fail closed, but operable)

### When to return `TEMP_UNAVAILABLE`

Only when correctness cannot be guaranteed, e.g.:

* can’t read a consistent snapshot (ActiveIndex and BundleIndex not at same cursor)
* projections are rebuilding / reconciliation is running
* policy profile cannot be loaded (if it shapes resolution)

### What must **not** happen

* Returning RESOLVED without being able to cite cursor/proof token.
* Returning RESOLVED if compatibility cannot be verified against the provided basis.
* “Best effort resolve” under uncertainty.

---

## 7) Environment ladder considerations (deployment-aligned)

Resolver semantics must be identical across envs; differences are **profiles**:

* dev/prod likely enable stronger policy gates and stricter deprecation windows
* prod typically relies more on DF caching + optional control-bus invalidation
* local may be simpler, but still must obey: deterministic + compat-aware + fail closed  

---

## 8) Quick internal diagram (opaque subnodes)

```text
ResolveActive request
   |
   v
[Canonicalizer] -> [Authz/Policy Binder]
   |
   v
[Snapshot Reader] -> [Candidate Selector] -> [Compatibility Evaluator]
                                         \-> [Fallback Resolver] (optional, explicit)
   |
   v
[Response Builder] -> ResolveActiveResponse (status + ActiveBundleRef + cursor + reasons)
   |
   v
[Cache Advisory] (optional hints)
```

---

Yep — we’re now “entering” the **Policy/Auth Gate** and exposing the machinery inside it (still modular, not a full spec).

This node is the **policy-bound choke point** that enforces:

* privilege tiers (publish vs lifecycle mutation vs resolve vs audit),
* **policy revision binding** (`approval_policy_rev` / `resolution_policy_rev`),
* explicit allow/deny outcomes with reason codes,
* and “profiles not forks” across the environment ladder.  

---

## 1) What Policy/Auth Gate is responsible for

### Responsibilities

1. **Bind policy revision once per request**

   * Every allowed/denied action is evaluated under an explicit policy revision.
   * Any resulting `registry_event` must cite `approval_policy_rev` (pinned). 

2. **Enforce privilege tiers**

   * PublishBundle (MF principal)
   * Lifecycle mutation (privileged actor/controlled automation)
   * ResolveActive (DF principal)
   * Audit queries (ops/governance principals) 

3. **Policy-shaped strictness (environment ladder safe)**

   * Local/dev/prod differ via **policy/wiring profiles**, not semantic forks. 

4. **Produce explicit outcomes**

   * ALLOW / DENY with durable, structured `reason_codes` (no “warn but proceed”). 

### Non-responsibilities (anti-drift)

* Does not decide ACTIVE (Lifecycle Engine does).
* Does not verify artifact digests (Bundle Intake/Attestation does).
* Does not resolve compatibility (Resolver does).
* Does not emit governance facts directly (Ledger/Event fanout does). 

---

## 2) Inputs/outputs at the boundaries of this node

### Input: `RequestContext` (from Front Door)

* `request_class`: PUBLISH_BUNDLE | LIFECYCLE_MUTATION | RESOLVE_ACTIVE | AUDIT_QUERY
* `caller_principal` (authn result)
* `scope_key` (when applicable)
* `idempotency_key` + `request_fingerprint`
* `normalized_payload`
* `trace_context`

### Outputs (policy-bound contexts)

* **AuthorizedPublishContext** → Bundle Intake
  `{ALLOW/DENY, approval_policy_rev, reason_codes, validated publish package}`
* **AuthorizedLifecycleAction** → Lifecycle Engine
  `{ALLOW/DENY, approval_policy_rev, reason_codes, action, scope, target bundle, reason/evidence refs}`
* **AuthorizedResolveContext** → Resolver
  `{ALLOW/DENY, resolution_policy_rev, reason_codes, caller principal}`
* **AuthorizedAuditQuery** → Audit Query
  `{ALLOW/DENY, audit_policy_rev, reason_codes, query spec}` 

> Designer pin: **The policy revision chosen here is carried forward and must match what later gets recorded** (especially in `registry_event`). 

---

## 3) Internal machinery (subnodes inside Policy/Auth Gate)

### 1) Principal Mapper

* Normalizes authn identity into a stable `principal_id` + roles/claims.
* Produces the “who is asking?” surface used everywhere.

### 2) Operation Classifier

* Confirms the request class from Front Door (publish vs lifecycle vs resolve vs audit).
* Extracts key selectors (scope_key, bundle_slot, tenant_id) that influence policy rules.

### 3) Active Policy Resolver

* Selects which **policy profile** applies (by environment + component + operation class).
* Resolves the **active revision**: `approval_policy_rev` (or `resolution_policy_rev`).
* This is the “profiles not forks” heart.  

### 4) Policy Artifact Loader + Integrity Verifier

* Loads the policy artifact by-ref (config is outcome-affecting) and verifies integrity (digest/ID).
* Caches the active revision (with TTL/refresh) to avoid hot-path dependence on storage.
* Fail-closed if the active revision can’t be proven. 

### 5) Authorization Evaluator (RBAC/ABAC)

* Applies “who can do what” rules:

  * MF may publish, not mutate lifecycle
  * Gov principals may mutate lifecycle, not necessarily publish
  * DF may resolve, not publish/mutate
  * Audit principals may query. 

### 6) Preconditions & Required-Fields Guard

Policy doesn’t just govern *who*, it governs *what must be present*:

* For lifecycle actions: reason codes required, evidence refs required, scope required, target bundle required.
* For publish: compatibility metadata required to be considered deployable; other fields may affect eligibility. 

### 7) Policy Decision Binder (idempotency-safe)

* Ensures repeated requests with the same idempotency intent don’t “flip” due to policy rev changing mid-retry.
* Practical posture: record `{idempotency_key → policy_rev_used + allow/deny + reasons}` when first evaluated, and reuse it on duplicates.
  (This aligns with your end-to-end retry/idempotency rail.) 

### 8) Decision Explainer (reason code generator)

* Produces a compact taxonomy of `reason_codes` so denies are debuggable and auditable.
* Ensures no opaque “denied” without context.

---

## 4) What lives in the policy profiles (the knobs this gate controls)

These are the **semantic knobs** (versioned + auditable), not wiring knobs.

### PublishBundle policy knobs

* Allowed publisher principals (MF allowlist)
* Required fields for *admissibility* vs *eligibility*
* Allowed/required artifact roles
* “Allow REGISTERED_INELIGIBLE?” (yes in local; yes in dev; yes in prod if explicit)
* Required lineage pointers (DatasetManifests) for eligibility
* Evidence requirements for eligibility classification

### Lifecycle policy knobs (approve/promote/rollback/retire)

* Allowed actor principals
* Required reason codes / required evidence refs
* Promotion gates:

  * require compatibility metadata (always)
  * require receipts (where policy demands)
  * require “approved first”
* Whether “retire ACTIVE ⇒ scope becomes NO_ACTIVE” is allowed (we pinned **yes**) 

### Resolve policy knobs

* Allowed DF principals / scopes
* Whether registry-defined fallback is allowed (v0 default: **no**, DF safe posture instead)
* Compatibility strictness (exact match vs compatible ranges for contract/versioning)
* Deprecation windows enforcement

### Audit policy knobs

* Who can query what
* Whether certain evidence pointers are redacted in lower environments

---

## 5) Minimal reason-code taxonomy (so nothing is opaque)

### DENY (publish)

* `DENY_PUBLISH_NOT_AUTHZ`
* `DENY_PUBLISH_POLICY_REV_UNKNOWN`
* `DENY_PUBLISH_SCOPE_NOT_ALLOWED` (if you scope publish by env/tenant)

### DENY (lifecycle)

* `DENY_LIFECYCLE_NOT_PRIVILEGED`
* `DENY_LIFECYCLE_POLICY_REV_UNKNOWN`
* `DENY_LIFECYCLE_REASON_REQUIRED`
* `DENY_LIFECYCLE_EVIDENCE_REQUIRED`

### DENY (resolve)

* `DENY_RESOLVE_NOT_AUTHZ`
* `DENY_RESOLVE_SCOPE_NOT_ALLOWED`
* `DENY_RESOLVE_POLICY_REV_UNKNOWN`

### DENY (audit)

* `DENY_AUDIT_NOT_AUTHZ`
* `DENY_AUDIT_SCOPE_NOT_ALLOWED`

These reason codes are **policy-gate outcomes**; “compatibility failures” are handled downstream by Resolver as `INCOMPATIBLE_*`.

---

## 6) Failure posture (what happens if policy is unavailable)

Designer pin for v0:

* **Mutating operations** (publish, lifecycle): if active policy revision cannot be loaded/verified → **fail closed** (DENY with `*_POLICY_REV_UNKNOWN`).
* **Resolve**: may use a cached active revision if it is still within cache TTL and its digest is known; otherwise fail closed (`TEMP_UNAVAILABLE_POLICY_STORE_UNAVAILABLE`).
  This preserves correctness while keeping hot path stable in prod.

---

## 7) Drift traps (what this gate must never allow)

* Any lifecycle mutation without a bound `approval_policy_rev` (breaks auditability). 
* “Warn-only” denies that still proceed.
* Environment-specific semantic forks (“prod allows X regardless of policy profile”). 
* Re-evaluating the same idempotency intent under a different policy rev and returning a different outcome (retry drift). 

---

### Quick internal diagram (opaque subnodes)

```text
RequestContext
   |
   v
[Principal Mapper] -> [Operation Classifier]
   |
   v
[Active Policy Resolver] -> [Policy Loader+Verifier]
   |
   v
[AuthZ Evaluator] -> [Required-Fields Guard] -> [Decision Binder] -> Authorized*Context + reason_codes
```

---

If you want the next node to illuminate, the best continuation is **Event Emission & Fanout** (because it operationalizes `registry_event` durability and optional control-bus broadcast without ever becoming an authority source).

---

Got it — we’re now “entering” **Event Emission & Fanout** (the outbox-style machinery), and exposing what must exist inside it for production correctness, while keeping its internal pieces modular.

This node exists to make your pinned rule real: **registry_event is a durable governance fact**, delivered reliably to audit/obs sinks, and *optionally* broadcast to `fp.bus.control.v1` as **notification** (never authority).  

---

## 1) What Event Fanout is responsible for

### Responsibilities (in-bounds)

* Read **new registry_event facts** from the authoritative ledger using a monotonic cursor (`event_seq`).
* Deliver those events to one or more **sinks** with **at-least-once** semantics.
* Maintain **per-sink delivery cursors** so fanout can resume after restart and not lose governance facts.
* Make delivery failures visible (backlog/lag), never silent.
* Optionally publish to the **control bus** (low volume) for DF cache invalidation / convergence.

### Non-responsibilities (anti-drift)

* Does **not** create or modify registry_event content.
* Does **not** decide lifecycle outcomes.
* Does **not** become the authority source of truth (bus broadcast is notification only).
* Does **not** require synchronous delivery for MPR correctness (correctness comes from ledger). 

---

## 2) Fanout’s internal subnodes (machinery)

### 1) **Sink Registry**

Defines the set of delivery targets and their semantics:

* `sink_id`
* `sink_type` ∈ {AUDIT_SINK, OBS_SINK, CONTROL_BUS}
* delivery mode (push, append, API call)
* enable/disable by environment profile

### 2) **Outbox Reader**

Reads from the ledger (authoritative DB) using a cursor:

* fetch batch of registry_events where `event_seq > last_delivered_seq(sink)`
* preserves **per-scope ordering** by default; global ordering is naturally preserved by `event_seq`.

### 3) **Delivery Cursor Store**

Durable per-sink state:

* `sink_id -> last_delivered_event_seq`
* plus delivery health metadata (last_attempt_time, consecutive_failures, etc.)

This is what makes restarts safe.

### 4) **Batcher & Shaper**

* Groups events into delivery batches (size/time bounded).
* Optionally wraps events in a sink-specific envelope **without changing meaning** (e.g., add `delivered_at`, `sink_id`, but never rewrite policy fields).

### 5) **Delivery Workers**

One worker per sink (or pooled workers), each implementing:

* send batch
* handle ack/failure
* retry with backoff

### 6) **Ack Handler**

On successful delivery:

* advances `last_delivered_event_seq` for that sink
* records success metrics

### 7) **Retry & Backoff Controller**

* exponential backoff with jitter (implementation detail)
* circuit-breaker posture so a dead sink doesn’t overload the system
* but **never drops events**

### 8) **Health/Backlog Reporter**

Publishes metrics:

* `fanout_lag_events = ledger_head_seq - last_delivered_seq(sink)`
* `fanout_lag_time` (approx from event timestamps)
* `deliveries_success/failure`
* `consecutive_failures`

This powers the governance/ops loop and prevents silent failures. 

---

## 3) Sinks and their semantics (what fanout must support)

### Sink A: **Audit / Governance sinks** (mandatory)

* Purpose: durable consumption of registry_event facts for auditability.
* Delivery: at-least-once, dedupe by `registry_event_id`.

### Sink B: **Observability sink** (optional but typical)

* Purpose: timelines/dashboards.
* Still at-least-once; best effort is OK only if audit sink is authoritative.

### Sink C: **Control bus** (`fp.bus.control.v1`) (optional)

* Purpose: low-volume notification for DF cache invalidation / convergence.
* **Explicit pin:** bus delivery is notification, not authority. 

---

## 4) The outbox loop (how it actually runs)

### Fanout main loop (per sink)

1. Load `last_delivered_event_seq` for sink.
2. Read next batch of events from ledger where `event_seq > last_delivered_event_seq`.
3. Deliver batch.
4. If success:

   * advance cursor to max `event_seq` delivered
5. If failure:

   * do not advance cursor
   * record failure + backoff
6. Repeat.

This is the internal expression of IL2.

---

## 5) Ordering guarantees (designer pin)

### Pin F1 — Per-scope order must be preserved at delivery

For the same `scope_key`, deliver events in increasing `event_seq`.
This ensures consumers (especially DF cache invalidation) don’t see rollback before promote for that scope.

Global order across scopes can be best-effort, but with a global cursor it usually holds naturally.

---

## 6) Delivery guarantees and failure posture

### Guarantees (authoritative)

* **At-least-once** delivery to each enabled sink.
* **No silent drops.**
* **Cursorable resumption** after restart.
* **No mutation** of registry_event meaning.

### Failure posture (what happens when sinks are down)

* **Audit sink down:** backlog grows; MPR can still serve resolve and accept lifecycle changes (ledger is authority), but ops sees lag and can treat it as degraded state if desired.
* **Control bus down:** only convergence/caching slows; correctness unaffected.
* **Obs sink down:** dashboards may lag; audit still authoritative.

---

## 7) Fanout’s boundary with the rest of MPR (joins)

### Input join (IJ10): Ledger → Fanout

* Supplies immutable registry_event rows + monotonic cursor (`event_seq`).

### Output join (IJ11): Fanout → sinks/bus

* Ships those same facts outward.

### Critical non-join pins

* Fanout must never write to ledger.
* Fanout must never “fix” missing fields or substitute policy rev.
* Fanout must never treat “bus publish succeeded” as proof of truth.

---

## 8) Environment ladder knobs specific to fanout

### Local

* Could run with only one sink (local audit file/table) and disable control bus.
* Still uses the same cursor semantics.

### Dev

* Prefer enabling control bus so DF cache invalidation behavior is tested.
* Audit sink enabled.

### Prod

* Audit sink mandatory and durable.
* Control bus enabled (typical) for fast convergence.
* Multiple fanout workers OK, but per-sink cursor advancement must remain consistent.

All of this is profile-driven, not code forks. 

---

## 9) Quick internal diagram

```text
          [Registry Event Store / Ledger]
                     |
                  (IJ10)
                     v
              [Outbox Reader]
                     |
             +-------+--------+
             |                |
     [Batcher/Shaper]   [Cursor Store]
             |                |
        +----+----+           |
        |         |           |
 [Delivery Worker A]   [Delivery Worker Bus]  ...
        |         |
   (ack/fail)  (ack/fail)
        v         v
   [Ack Handler / Retry Controller]
        |
        v
 [Health/Backlog Reporter]
```

---

If you want the next node to illuminate, the clean continuation is **Audit & Explain Query Surface**, because it’s the consumer of ledger/projections on the read side and is where “as-of cursor/time” semantics must be made explicit.

---

Got it — we’re now “entering” **Audit & Explain Query Surface** and exposing the machinery inside it.

This node is the **read-only explainer** for the vertex: it turns the ledger/projections into answers like “what changed?”, “who changed it?”, “why?”, “what was active then?”, and “why was this bundle rejected/ineligible?”, using **as-of cursor/time semantics** (never best-effort logs). 

---

## 1) What Audit & Explain is responsible for

### Responsibilities (in-bounds)

* Provide **read-only** query endpoints for:

  * active resolution history verify (“what was ACTIVE at cursor/time X?”)
  * lifecycle timeline (“show registry events for scope/bundle”)
  * bundle inspection (compatibility contract, evidence pointers, lineage pointers)
  * publish rejection/ineligibility explanations (reason codes + pointers)
  * policy-rev trace (“what rules were in force for this change?”)

* Support **as-of semantics**:

  * **as_of_cursor** (preferred, deterministic)
  * **as_of_time** (supported, but must map deterministically to cursor boundaries)

* Guarantee that every answer can cite:

  * governing `registry_event_id`
  * `event_seq` (cursor)
  * `actor_principal`
  * `approval_policy_rev`
  * `reason` + `evidence_refs` 

### Non-responsibilities (anti-drift)

* Must not mutate any state (no lifecycle actions, no “repair”).
* Must not fabricate history from logs.
* Must not answer “active at time” from the current ActiveIndex without cursor/time mapping.
* Must not redact or omit pinned governance fields unless policy explicitly defines redaction (and then it must be traceable).

---

## 2) Inputs / outputs

### Input: AuthorizedAuditQuery (from Front Door + Policy/Auth via IJ12)

* `caller_principal`
* `authz_decision`
* `audit_policy_rev` (traceable)
* `query_type`
* `filters` (scope_key, bundle_id/version, governance_action, time range, cursor range)
* `as_of_cursor` or `as_of_time`
* `page_cursor`, `limit`

### Output: QueryResponse

* `results[]` (typed by query)
* always includes:

  * `as_of_cursor_used` (even if caller requested time)
  * paging metadata
* and for explain/timeline outputs, includes:

  * `registry_event` slices with pinned fields
  * pointers to evidence/lineage/bundle manifests

---

## 3) Internal subnodes (machinery) inside Audit & Explain

### 1) Query Router

* Parses `query_type` and dispatches to the right handler.
* Enforces “read-only” invariant.

### 2) Cursor Resolver (As-Of Service)

This is the heart of correctness.

* If caller provides `as_of_cursor`: validate it (<= ledger head), use directly.
* If caller provides `as_of_time`: map to cursor deterministically:

  * find the greatest `event_seq` whose `event_time_utc <= as_of_time`
  * return that as `as_of_cursor_used`

> Designer pin: all “time” queries become “cursor” queries internally.

### 3) Projection Query Engine

* Uses projections for speed:

  * ActiveIndex
  * BundleScopeState
  * BundleIndex
  * Eligibility/Rejection views
  * EventTimeline indexes
* Always tags results with the cursor they’re valid at.

### 4) Ledger Slice Reader

* For timeline queries and strict as-of correctness, fetches `registry_event` rows in cursor ranges:

  * `event_seq between A and B`
  * filtered by scope/bundle/action
* This is the authoritative basis for “who/why”.

### 5) State Reconstructor (Active-at-cursor)

Answers: “What was ACTIVE for scope S at cursor C?”

Two permissible strategies (both in-bounds):

* **Projection-at-cursor** (if you materialize ActiveIndex history by cursor)
* **Reconstruct by replay** from last checkpoint ≤ C:

  * start from known ActiveIndex state at checkpoint
  * apply events up to C for that scope

v0 recommendation: keep it simple:

* store `active_set_event_seq` (the event that set ACTIVE) and reconstruct from event slices for as-of queries.

### 6) Explain Assembler

Builds human-usable explanations without inventing facts:

* bundles together:

  * current/at-cursor active bundle ref
  * the registry_event(s) that caused it
  * actor + policy rev + reason + evidence pointers
* Optionally formats “supersedes” chains.

### 7) Redaction/Disclosure Filter (policy-shaped)

* Applies audit policy rules:

  * some principals may see full evidence pointers
  * others see redacted pointers (still traceable)
* Redaction itself must be explainable (policy rev + reason).

### 8) Pagination & Stability Controller

* Ensures paging is stable under concurrent writes:

  * paging uses cursor ranges, not “offset N”
  * page_cursor is a cursor token, not a row number

---

## 4) Query types we should pin (minimal but complete)

### Q1 — GetActive(scope_key, as_of_cursor|time)

Returns:

* `scope_key`
* `active_bundle_ref` or NONE
* `active_set_event_seq` + `active_set_event_id`
* `as_of_cursor_used`

### Q2 — ListRegistryEvents(filters, cursor_range|time_range)

Returns:

* ordered registry_event slice(s), each with pinned fields
* `next_page_cursor`

### Q3 — ExplainScope(scope_key, as_of_cursor|time)

Returns:

* the active bundle ref (at cursor)
* the promoting/rollback event(s) that produced it
* the previous active if relevant (from event payload)
* policy rev + actor + reasons + evidence pointers

### Q4 — GetBundle(bundle_id, bundle_version)

Returns:

* bundle record: artifacts refs/digests, compat contract, lineage pointers, evidence pointers, intake status

### Q5 — ExplainBundleLifecycle(bundle_id, bundle_version, scope?)

Returns:

* timeline of events affecting that bundle (publish + approvals + promotions + retirements)
* plus current state per scope

### Q6 — ListRejections / IneligibilityReasons(filters)

Returns:

* identifiable publish attempts that were rejected or stored ineligible
* reason codes and evidence pointers (if any)

---

## 5) As-of semantics (the critical pinned rule)

### Designer pin AOS1 — Cursor is the truth boundary

All audit answers are computed “as-of cursor C”.

* `as_of_time` is only a convenience that maps deterministically to `as_of_cursor_used`.
* Every response echoes `as_of_cursor_used` so later you can replay/verify.

### Designer pin AOS2 — No “current state” answers unless asked

If a caller doesn’t provide an as-of selector:

* default is `as_of_cursor = ledger_head_seq` (explicitly stated in response)
* never implicitly answer from “whatever the DB says now” without disclosing cursor.

---

## 6) Failure posture (keep it operable, not magical)

* FORBIDDEN if caller lacks audit rights.
* BAD_QUERY for invalid selectors (unknown scope, invalid cursor, bad ranges).
* TEMP_UNAVAILABLE only if ledger/projections cannot be read consistently.

No partial, untraceable answers.

---

## 7) Drift traps (what this node must never do)

* Answer “active at time X” by reading **current** ActiveIndex.
* Omit `approval_policy_rev` / actor / reason from explain outputs.
* Use logs instead of ledger for governance history.
* Provide unstable pagination that changes while you page.

---

## 8) Quick internal diagram (opaque subnodes)

```text
AuthorizedAuditQuery
   |
   v
[Query Router]
   |
   +--> [Cursor Resolver] ----> as_of_cursor_used
   |
   +--> [Projection Query Engine] ----+
   |                                 |
   +--> [Ledger Slice Reader] -------+--> [State Reconstructor] --> [Explain Assembler]
                                     |
                                [Redaction Filter]
                                     |
                                     v
                              QueryResponse (+ paging + as_of_cursor_used)
```

---

If you want the next thing to illuminate, the natural follow-on is **Front Door Ports** (because it wires idempotency keys, request canonicalization, and routing to the correct node — and it’s where “no payload invention” must be enforced).

---

Got it — we’re now “entering” **Front Door Ports** and exposing the machinery inside it.

This node is the **boundary intake router** for the whole MPR service. It’s where we enforce:

* request canonicalization (no hidden assumptions),
* idempotency key handling (retry-safe),
* routing to the correct internal port (publish vs lifecycle vs resolve vs audit),
* and strict separation of operation classes.

It must remain thin: it **does not** decide policy, lifecycle, compatibility, or event emission — it just makes sure requests are well-formed and routed deterministically.

---

## 1) What Front Door Ports are responsible for

### Responsibilities (in-bounds)

1. **Expose the four boundary ports** (outer joins reflected internally):

   * PublishBundle (J16)
   * GovernLifecycle (approve/promote/rollback/retire)
   * ResolveActive (J10)
   * Audit/Explain queries + Event-feed access (if you expose it via API)

2. **Parse + normalize** requests into a canonical internal `RequestContext`

   * stable field normalization
   * stable defaulting rules (only where explicitly allowed)
   * explicit error on missing mandatory fields

3. **Idempotency wiring**

   * accept explicit idempotency keys
   * derive stable idempotency keys when not provided (only after identity exists)
   * ensure duplicate requests do not create new state changes

4. **Request classification + routing**

   * determine `request_class` and route to:

     * Policy/Auth → Bundle Intake (publish)
     * Policy/Auth → Lifecycle Engine (lifecycle)
     * Policy/Auth → Resolver (resolve)
     * Policy/Auth → Audit Query (audit)

5. **Correlation hooks**

   * attach `trace_context` / `request_id` consistently so later audit/debug can tie everything together

### Non-responsibilities (anti-drift)

* **No authorization decisions** (Policy/Auth does that).
* **No bundle validation/attestation** (Bundle Intake does that).
* **No lifecycle state change** (Lifecycle Engine does that).
* **No compatibility evaluation** (Resolver does that).
* **No emission** of registry events (Ledger/Fanout does that).
* **No “helpful fix-ups”** that invent missing identity/fields.

---

## 2) The core internal object: `RequestContext` (what Front Door produces)

Front Door produces a canonical `RequestContext` that every downstream module relies on.

Minimum fields:

* `request_class`: `PUBLISH_BUNDLE | LIFECYCLE_MUTATION | RESOLVE_ACTIVE | AUDIT_QUERY`
* `caller_principal` (authn result; may be “unknown” if authn fails)
* `trace_context` (trace_id/span_id)
* `request_id` (server-generated unique id)
* `received_at_utc`
* `idempotency_key` (explicit or derived)
* `request_fingerprint` (hash of normalized payload; stable)
* `normalized_payload` (canonical form)
* `scope_key` (if applicable)
* `target_bundle_ref` (if applicable)

> Pin: if Front Door cannot construct a coherent RequestContext without guessing, it rejects the request early.

---

## 3) Internal subnodes (machinery) inside Front Door Ports

### 1) Endpoint Router (Port multiplexer)

* Maps incoming request to a port:

  * `/publish`
  * `/lifecycle/approve`
  * `/lifecycle/promote`
  * `/lifecycle/rollback`
  * `/lifecycle/retire`
  * `/resolve`
  * `/audit/...`
* Establishes `request_class`.

### 2) Authn Extractor

* Extracts and validates caller identity (token/API key/mTLS identity).
* Produces `caller_principal` or fails early (401).

*(Authz is downstream.)*

### 3) Payload Canonicalizer

* Canonicalizes the payload:

  * normalizes JSON keys ordering
  * normalizes lists/maps into stable order where order is not semantically meaningful
  * normalizes case and whitespace where defined (e.g., bundle_id trimming)
* Produces `normalized_payload`.

> Pin: canonicalization is deterministic and does not change meaning.

### 4) Request Fingerprinter

* Computes `request_fingerprint = hash(normalized_payload + request_class)`.

Used for:

* derived idempotency
* conflict debugging
* audit trails

### 5) Idempotency Key Resolver (critical)

Rules (authoritative):

**If caller supplies `Idempotency-Key`:**

* use it (after sanity validation).

**If no idempotency key is supplied:**

* Derive only when identity exists:

  * **Publish:** `hash(bundle_id + bundle_version + request_fingerprint)`
  * **Lifecycle:** `hash(scope_key + governance_action + target_bundle_ref + request_fingerprint)`
  * **Resolve/Audit:** idempotency is not required (read-only), but you can still compute a fingerprint for tracing.

> Pin: no identity ⇒ no derived idempotency ⇒ reject with “missing identity fields.”

### 6) Required-Fields Gate (early validation)

Front Door enforces only “routing-level” required fields:

* Publish requires `bundle_id`, `bundle_version` at minimum (to avoid unidentifiable requests).
* Lifecycle requires `scope_key`, `target_bundle_ref`, and action name.
* Resolve requires `scope_key`, `degrade_mask`, and a feature-basis token/map.
* Audit requires query type and at least one selector (scope or bundle or cursor range).

Everything deeper (compat completeness, evidence completeness) is downstream.

### 7) Rate/Abuse Guard (non-semantic)

* Per-principal rate limits
* payload size limits
* request timeouts

These are wiring knobs and must not change semantics.

### 8) Response Normalizer

* Ensures responses are consistent:

  * includes `request_id`
  * includes `registry_cursor` where applicable (resolve responses)
  * includes `registry_event_id` and cursor for successful lifecycle changes
  * includes typed error codes + reason codes (no opaque 500s)

---

## 4) The four “Front Door ports” (how each is handled)

### Port FD1 — PublishBundle

* Build RequestContext with:

  * `bundle_id/version`
  * idempotency key
  * request fingerprint
* Route: Policy/Auth → Bundle Intake → Bundle Store → Ledger → Fanout

Early rejects:

* missing bundle_id/version
* oversized payload

### Port FD2 — GovernLifecycle (approve/promote/rollback/retire)

* Build RequestContext with:

  * `scope_key`
  * action
  * target_bundle_ref
  * reason/evidence refs (presence only; content checks downstream)
* Route: Policy/Auth → Lifecycle Engine → Ledger → Fanout

Early rejects:

* missing scope/target/action

### Port FD3 — ResolveActive

* Build RequestContext with:

  * `scope_key`
  * `degrade_capabilities_mask`
  * `feature_basis` (feature group versions)
* Route: Policy/Auth → Resolver → response

Early rejects:

* missing degrade mask or feature basis

### Port FD4 — Audit/Explain

* Build RequestContext with:

  * query type
  * selectors (`as_of_cursor` or `as_of_time`, scope/bundle filters)
* Route: Policy/Auth → Audit Query → response

Early rejects:

* invalid cursor format, insane ranges

---

## 5) Drift traps (what Front Door must never do)

* Invent missing identity fields (bundle_id/version, scope_key).
* Auto-promote or auto-approve on publish (“helpful convenience”).
* Interpret “missing feature basis” as “use latest”.
* Hide failures: must return typed outcomes with reason codes.
* Perform policy decisions (authz) or compatibility checks.

---

## 6) Environment ladder knobs (deployment-aligned)

Front Door’s semantics are identical across envs; profiles only tune:

* rate limits
* authn mechanisms (local may use dev tokens; prod uses strong identity)
* request size limits / timeouts

No “prod-only behavior” branches.

---

## 7) Mini diagram (Front Door internals)

```text
Incoming HTTP/gRPC
   |
   v
[Endpoint Router]
   |
   v
[Authn Extractor] -> caller_principal
   |
   v
[Payload Canonicalizer] -> normalized_payload
   |
   v
[Fingerprinter] -> request_fingerprint
   |
   v
[Idempotency Resolver] -> idempotency_key
   |
   v
[Required-Fields Gate]
   |
   v
RequestContext -> route to Policy/Auth -> downstream node
```

---

If you want to continue in the same rhythm, the next node to illuminate is **Substrate Adapters** (DB/object store/control bus connectors + wiring profiles), because it’s the last “machinery” node we haven’t opened and it ties directly into the environment ladder and deployment posture we pinned.

---

Got it — we’re now “entering” **Substrate Adapters** and exposing the machinery inside it.

This node is the **plumbing boundary** between the MPR service’s internal network and the production substrates:

* Registry DB (authoritative truth)
* Object store (bundle/evidence blobs by-ref)
* Control bus (optional notification channel)
* Policy/profile store (versioned outcome-affecting configs)

The key rule: adapters provide **reliable, explicit I/O** — they must not invent semantics, scan “latest,” or smuggle hidden joins.

---

## 1) What Substrate Adapters are responsible for

### Responsibilities (in-bounds)

* Provide **typed, minimal, deterministic** interfaces to each substrate.
* Enforce **wiring profiles** (endpoints, credentials, timeouts) per environment.
* Provide **retries/backoff** where safe, without changing meaning.
* Provide **integrity hooks** (digest verification where applicable).
* Provide **observability** (metrics/traces) for every external I/O call.

### Non-responsibilities (anti-drift)

* No “business logic”: no eligibility decisions, no lifecycle decisions, no compatibility decisions.
* No hidden discovery: must never “scan bucket for latest bundle” or infer ACTIVE.
* No silent transformation that changes meaning.
* No caching that can change outcome (except safe caches of immutable blobs or policy artifacts with explicit TTL and rev identity).

---

## 2) The adapter set (what concrete adapters exist)

You need **four** adapter families:

1. **Registry DB Adapter** (authoritative state)
2. **Object Store Adapter** (immutable blob refs + digest posture)
3. **Control Bus Publisher Adapter** (optional notification stream)
4. **Policy/Profile Store Adapter** (versioned outcome-affecting configs)

(You can implement policy/profile store as “object store + cache,” but conceptually it’s separate because it shapes outcomes and must be revision-addressable.)

---

## 3) Registry DB Adapter (authoritative)

### What it must expose (typed operations)

Minimum operations needed by the internal nodes we’ve designed:

**Ledger/Event operations**

* `append_registry_event(event)` → returns `(registry_event_id, event_seq)`
* `read_events_after(seq, limit)` / `read_events_range(seq_a, seq_b, filters)`
* `get_ledger_head_seq()`

**Projection operations**

* `get_active(scope_key, as_of_seq?)`
* `set_active(scope_key, bundle_ref, active_set_event_seq)` (used only by projection updater in same txn)
* `get_bundle_scope_state(scope_key, bundle_ref)`
* `set_bundle_scope_state(...)`
* `get_scope_head(scope_key)`
* `set_scope_head(scope_key, last_seq)`

**Bundle store operations**

* `get_bundle_record(bundle_id, version)`
* `insert_bundle_record_if_absent(bundle_record)` → returns CREATED/DUPLICATE/CONFLICT
* `list_rejections(...)` / `insert_rejection_record(...)` (if you store rejections separately)

**Idempotency operations**

* `get_idempotency_outcome(idempotency_key, request_class, principal)`
* `set_idempotency_outcome(...)`

**Fanout cursor operations**

* `get_sink_cursor(sink_id)`
* `set_sink_cursor(sink_id, last_delivered_seq)`

### Transaction posture (pinned)

* Supports **scope-linearizable lifecycle mutation** via transactions/locks on `scope_key`.
* Supports “event + projection delta” commit atomicity (v0 pin).

### Wiring knobs (environment profile)

* DB URL(s), TLS, pool size, statement timeout
* migration mode (auto vs manual)
* read replica use (optional; must not violate consistency requirements)

### Drift traps

* Adapter exposing “update event” methods (ledger must be append-only).
* Adapter providing “get latest bundle” convenience queries.
* Adapter allowing projection writes outside controlled paths.

---

## 4) Object Store Adapter (by-ref blobs + digests)

### What it must expose (typed operations)

**Read/verify**

* `head(ref)` → existence + metadata
* `get(ref)` → bytes/stream
* `verify_digest(ref, expected_digest)` → PASS/FAIL/NOT_FOUND/UNAVAILABLE

**Write immutable**

* `put_immutable(ref, bytes, content_digest)` → returns final ref + digest
* (optional) `put_manifest(bundle_id, version, manifest_bytes)` → returns manifest_ref + digest

**Ref utilities**

* `parse_ref(string)` and `render_ref(parts)`
* `normalize_ref(ref)` (canonical formatting; no semantics)

### Path/prefix conventions (directional pins)

* bundle blobs under something like: `registry/bundles/{bundle_id}/{bundle_version}/...`
* bundle manifest under: `registry/bundles/{bundle_id}/{bundle_version}/bundle_manifest.json`
* evidence blobs may be under:

  * `mf/...` (written by Model Factory)
  * `ofs/...` (written by Offline Shadow)
  * but MPR stores refs, not bytes

### Digest posture (pinned)

* If a digest is required, missing digest is an error.
* Digest mismatch is **inadmissible**, not warning.

### Availability posture

* For publish-time attestation, “object store unavailable” is a **transient failure** (no commit).
* For resolve-time, object store is not required (resolver relies on stored refs/digests); if later you load artifacts at runtime, DF handles that — not MPR.

### Drift traps

* Listing “latest objects” or scanning prefixes to infer state.
* Overwriting objects in place (must be immutable).

---

## 5) Control Bus Publisher Adapter (optional notification)

### What it must expose

* `publish_control_fact(topic, key, event)` → ack/fail
* (optional) `publish_batch(...)`

### Contract posture (pinned)

* At-least-once publishing is fine; consumers dedupe by `registry_event_id`.
* Bus is notification; it is never read as truth by MPR.

### Wiring knobs

* broker endpoints, topic name (`fp.bus.control.v1`), auth, timeouts
* partition key strategy (recommended: `scope_key` for per-scope ordering)

### Drift traps

* Adapter used as a read source of truth.
* Publishing “derived state” that isn’t backed by a ledger event.

---

## 6) Policy/Profile Store Adapter (outcome-affecting config)

### What it must expose

* `get_active_policy_rev(env, component, operation_class)` → `policy_rev_id`
* `fetch_policy_artifact(policy_rev_id)` → bytes + digest
* `verify_policy_digest(policy_rev_id, expected_digest)` (if you store digests in DB)

### Caching posture (safe)

* Cache by **policy_rev_id** (immutable) with TTL
* Never cache “active policy” without also caching the rev id and re-checking it periodically
* Fail closed if active rev can’t be determined/verified (mutations), and for resolve you may allow short-lived cached rev if explicitly configured.

### Drift traps

* Using “latest policy file in bucket.”
* Treating missing policy artifact as “use default.”

---

## 7) Cross-cutting adapter concerns (things Codex should implement once)

### A) Unified Retry/Backoff policy

* Safe retries: idempotent reads, publish-to-bus (at-least-once), object head/get
* Unsafe retries: DB writes without idempotency key; must be wrapped in transactions and idempotency journaling.

### B) Observability wrapper

Every adapter call should emit:

* trace spans (with substrate name, operation, duration, result code)
* counters (success/fail)
* latency histograms

### C) Error taxonomy mapping

Adapters should map raw errors to a small stable set:

* NOT_FOUND
* CONFLICT
* INVALID
* UNAVAILABLE
* TIMEOUT
* PERMISSION_DENIED

So upstream modules can produce consistent reason codes.

### D) Profile injection

Adapters must be configured entirely via **profiles**:

* wiring profile (endpoints/creds/timeouts)
* policy profile (rev selection rules, strictness)
  No code branching on “if prod.”

---

## 8) Mini internal diagram (Substrate Adapters)

```text
           [MPR Internal Nodes]
                    |
        +-----------+------------+
        |           |            |
        v           v            v
   [DB Adapter] [Object Store] [Policy Store]
        |           |            |
        v           v            v
   Registry DB   Blob Store    Policy Artifacts

                    |
                    v
           [Control Bus Publisher] (optional)
                    |
                    v
             fp.bus.control.v1
```

---

## 9) The “non-joins” for adapters (must-not-happen)

* No adapter performs discovery (“scan bucket for latest bundle”).
* No adapter invents defaults that change outcomes.
* No adapter writes ledger history except append-only event insert operations.
* No adapter reads the control bus as authority.

---

## USER: PAUSE FOR REFLECTION

Totally fair to pause here — we’ve just turned MPR from a black box into a **production-shaped internal graph** with explicit laws, and it’s genuinely a lot of machinery (but it’s *cohesive*, not sprawling).

## What we’ve actually built (in one sentence)

A **control-plane ledgered authority** that converts “candidate bundles” into **governed deployable truth**, and converts “deployable truth” into **deterministic, compatibility-safe resolution**, while remaining replayable, auditable, and safe under retries, concurrency, and restarts.

## Why it feels complex (and why it’s the *right* kind of complexity)

Almost every moving part exists to satisfy one of five hard platform rails you pinned:

1. **Governed change as a fact**
   → Ledger (`registry_event`) + Audit Query + Fanout

2. **Deterministic resolution**
   → Resolver reads a consistent snapshot + returns a cursor/proof token

3. **Compatibility-aware execution safety**
   → Compatibility checker + fail-closed outcomes + degrade-mask hard constraints

4. **At-least-once + idempotency reality**
   → idempotency journaling, duplicate handling, conflict loop, no-op semantics

5. **Production survivability** (restart, partial failure, sink outages)
   → rehydration path + reconciliation loop + outbox fanout cursors

So the “complexity” isn’t optional features — it’s the minimum scaffolding that makes the outer network truthful in production.

## The comforting part: the graph has a single spine

Everything hangs off one backbone:

**Ledger (append-only events) → Projections → Resolver/Audit + Fanout**

That means:

* If you keep the ledger/projection cursor discipline clean, the rest stays consistent.
* If something goes wrong, the repair story is “replay the ledger,” not “debug mystery state.”

## What we successfully avoided (which would have made it *worse*)

We explicitly pinned non-joins that prevent hidden coupling:

* No publish→ACTIVE shortcuts
* No resolver writes
* No bus-as-authority
* No object-store scanning / “latest”
* No environment-only semantics forks

Those are the classic sources of drift and accidental complexity, and we kept them out.

## A practical way to hold it in your head

Think of MPR as **three planes** inside one service:

### Plane 1: Intake + Identity (write candidate truth)

Front Door → Policy/Auth → Bundle Intake → Bundle Store → Ledger

### Plane 2: Governance (change deployable truth)

Front Door → Policy/Auth → Lifecycle Engine → Ledger (→ ActiveIndex update)

### Plane 3: Serving + Explainability (read deployable truth safely)

DF Resolve → Policy/Auth → Resolver+Compat (reads projections)
Audit → Policy/Auth → Audit Query (reads ledger/projections)
Ledger → Fanout → sinks/bus

Everything we illuminated fits into one of these planes.

---

