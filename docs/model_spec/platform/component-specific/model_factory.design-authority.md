# Model Factory Design Authority

This file is a rough collection of design or brainstorm notes for the Model Factory. It views the whole platform as a network and expands open the model factory's position in this network and illuminates it.

---

Cool — we’ll do this exactly the way you asked:

* **MF inner network stays a black box for now.**
* We define **MF’s role + outer obligations** inside the already-pinned platform network.
* What I say here becomes **authoritative design** for MF (within your pinned platform/engine laws).

Everything below is anchored to your platform joins/pins for **J15 (OFS→MF)** and **J16 (MF→Registry)** plus the deployment truth table (MF is a **job**, not an always-on service).   

---

# 1) What MF *is* in the platform network (authoritative)

**Model Factory is the platform’s offline “build authority” for deployable decision policy artifacts.**
It takes **pinned training datasets** (DatasetManifests) + **versioned training/config profiles**, produces **reproducible training/eval evidence**, packages **deployable Bundles**, and publishes them to the Registry.  

MF is **not**:

* an online decisioning component (DF is) 
* a label truth owner (Label Store is) 
* a feature-definition authority (feature versions are singular and must be referenced, not invented) 
* an activation authority (Registry alone decides ACTIVE and governs promotion/rollback)  

**MF is a job deployment unit**: reads `ofs/...` manifests/materializations + profiles, writes `mf/...` evidence artifacts, and publishes bundles to Registry via API; optional governance facts to `fp.bus.control.v1`.  

---

# 2) MF’s neighbors and the allowed edges (the outer network)

Below is the *only* interaction surface MF needs in v0 to fit the pinned network (everything else is indirect via manifests or via Registry).

## Edge A — Offline Feature Shadow → MF (J15)

**What crosses the join:** **DatasetManifests + evidence.** 

### MF’s required posture on this edge (authoritative)

MF treats DatasetManifests as:

* **immutable inputs**
* **the unit of reproducibility**
* **the unit of auditability** 

So MF must *refuse* “here’s a dataframe / folder / latest snapshot” as an input unless it’s represented as a manifest with pinned basis. (That’s not “spec,” that’s the outer law of how MF is allowed to be invoked.) 

### What MF assumes must be inside the DatasetManifest (outer expectation)

Because OFS is pinned to record deterministic rebuild basis, MF expects the manifest to pin (at minimum):

* dataset identity
* time window and **as-of boundary**
* join keys and entity scoping
* **feature group versions used** (single feature authority rail)
* refs + digests to materializations
* provenance: sources and transformations (including EB/Archive basis + label store rules)  

MF does **not** re-derive these. If they’re missing, MF treats the dataset as **not admissible**.

## Edge B — Run/Operate → MF (trigger / governance edge)

MF does not self-decide “when to train.” It is **triggered** (scheduled, manual, or pipeline) by Run/Operate. Run/Operate is pinned as the orchestrator that triggers jobs and emits governance facts around backfills/promotions/ops changes.  

So the outer handshake is:

**TrainBuildRequest (control-plane request)** includes:

* `dataset_manifest_refs[]` (by-ref, immutable; no scanning) 
* `training_config_ref` (+ policy/profile revision identifiers) 
* `requester_principal` / trigger provenance (who/what caused it) 
* optional “intent”: `{baseline_train | backfill_retrain | candidate_eval | regression_check}` (important for audit) 

MF may also emit **optional governance facts** back to `fp.bus.control.v1` for visibility (“training started”, “completed”, “bundle published”, etc.).  

## Edge C — MF → Model/Policy Registry (J16)

**What crosses the join:** deployable **Bundles + promotion evidence**. 

Pinned truths here:

* Bundle must carry identity + immutable refs/digests to artifacts + training provenance (which manifests) + evaluation evidence + PASS/FAIL receipts where required. 
* Registry is the **only ACTIVE authority**; promotion/rollback is governed and auditable.  
* Access/control overlay: promotion/rollback is controlled at Registry (choke point), and those operations emit governance facts. 

So MF’s outer responsibility is: **publish candidate bundles**, never “make them live.”

Registry, in turn, emits lifecycle events to the control bus and provides deterministic ACTIVE resolution to DF.  

## Edge D — MF → Observability/Governance (cross-cutting rail)

This is not optional in spirit:

**Any change that can affect outcomes or reproducibility must be explicit as auditable governance facts** (promotion, rollback, backfills, training runs that produce candidates). 

MF therefore must produce an auditable trail (even if you choose “objects only” rather than “events”):

* training run record(s) + evidence refs in `mf/...` 
* and/or governance facts on `fp.bus.control.v1` (optional but strongly aligned with your production truth table)  

---

# 3) MF’s operational story (how it operates in the network)

Treat MF as a deterministic “build step” with a strict admission discipline on *inputs* and a strict publish discipline on *outputs*.

## MF lifecycle (outer view)

1. **Triggered** by Run/Operate (schedule/manual/pipeline). 
2. **Resolves inputs**: DatasetManifest refs + config/profile revisions (all by-ref).  
3. **Builds**: trains + evaluates and writes evidence artifacts to `mf/...`. 
4. **Gates**: produces PASS/FAIL promotion evidence (gate receipt posture). 
5. **Publishes**: only eligible (PASS) bundles are published to Registry; Registry governs activation.  
6. **Emits auditability**: run record + (optional) governance facts so operators can answer “what ran, why, with what data, what changed.”  

## Two “must be true” properties at the boundary (authoritative)

### A) Reproducibility is determined at the **input boundary**

MF is reproducible **only if**:

* it is invoked with **exact manifest refs** (and their digests) and **exact config/profile revisions**.  
  If the trigger request doesn’t pin these, MF has to treat it as **invalid** (because it would create “mystery training runs” that drift across time).

### B) Deployability is determined at the **output boundary**

A model is “eligible for deployment” only when:

* MF produced the bundle + evidence
* gates say PASS
* Registry accepted it into lifecycle
* Registry (later) governs activation/rollback  

MF cannot “quietly deploy.”

---

# 4) What MF is allowed to *consume* (and what it must never do)

## Allowed consumption (by design)

MF can indirectly rely on:

* EB/Archive history and Label Store **only through OFS** (because OFS is pinned as the deterministic rebuild job producing manifests). 
* Feature definitions/versions only by referencing the singular authority (the rail forbids MF inventing versions). 
* Engine “truth_products” for supervision/eval only as **by-ref surfaced artifacts**, never as hot-path inputs (which is fine because MF is offline).  

## Forbidden behaviors (outer-law level)

* **No scanning / “latest dataset”** selection (manifests are mandatory). 
* **No activation** (Registry owns ACTIVE). 
* **No silent changes**: if MF produces something that could affect outcomes, there must be explicit evidence + governance visibility. 
* **No training/serving drift by construction**: MF bundles must declare feature version compatibility aligned to the platform’s single feature authority.  

---

# 5) The authoritative outer “contract” for MF (conceptual, not schema)

Even though we’re not writing a formal contract, MF’s black-box IO is now pinned as:

## Inputs

* `DatasetManifestRef[]` from `ofs/...` (immutable, digestable, reproducibility anchor) 
* `TrainingConfigRef` + `GovernanceProfileRev` (versioned, cited in outputs) 
* `TriggerProvenance` (who/what/when/why — for governed change) 

## Outputs

* `mf/...` training artifacts + evaluation evidence + run record (auditable) 
* `Bundle` published to Registry (if eligible) + evidence/receipts attached 
* optional governance facts to `fp.bus.control.v1` 

---

Yes — there are a few **MF-specific “design laws”** that are worth pinning *before* we even talk about joins, because they determine what MF is allowed to assume, what it must guarantee, and what “done” means for MF outputs.

Below are the **pins I’m locking for MF v0** (authoritative unless you override later). They’re consistent with the platform’s learning-loop joins and rails (J15/J16, “no hidden now”, compatibility-aware resolution, etc.).

---

## MF pins to lock now

### MF-P1 — Authority boundaries

MF is authoritative for **training runs, evaluation evidence, gate receipts, and produced bundles**.
MF is **not** authoritative for activation (Registry is), labels (Label Store is), or feature definitions (it consumes pinned versions).

### MF-P2 — Unit of work and “what MF produces”

* **Unit of work:** a *training run* (`train_run_id`).
* **Publishable output:** at most **one** new *bundle* per training run in v0 (evaluation-only runs may publish none).
  Reason: keeps auditability and idempotency clean; avoids “one run sprayed 6 candidates” ambiguity.

### MF-P3 — Training run identity (reproducibility + idempotency core)

MF must define “same run” deterministically via a **TrainRunKey** derived from:

* ordered `DatasetManifest` digests/refs,
* training config digest/ref,
* feature definition pack revision,
* MF code/runtime revision (or build id),
* governance profile revision (if applicable).

`train_run_id = f(TrainRunKey)` and **retries must resolve to the same `train_run_id`** (idempotent boundary). This matches the platform rail that idempotency recipes are local and explicit.

### MF-P4 — Input discipline: manifests only (no hidden “latest”)

MF only trains on **DatasetManifests** (not raw tables, not “latest snapshot”), and treats manifests as **immutable inputs**. If a manifest can’t be re-resolved later, the run is considered non-reproducible and is invalid.

### MF-P5 — Leakage/as-of policy is non-negotiable

MF training/eval must obey:

* labels queried with explicit **as-of** rules (observed vs effective time),
* features reconstructed **as-of the same cut**,
* explicit train/val/test windows (no implicit “now”).

### MF-P6 — Feature version authority is singular

MF does **not** define features. It consumes a **single authoritative Feature Definition Pack** (whatever substrate you choose), and:

* OFP records feature group versions used,
* OFS uses those exact versions to rebuild datasets,
* MF bundles declare the required feature versions.

(Where that authority “lives” can be decided later, but the **singularity** is pinned now.)

### MF-P7 — Bundle compatibility is explicit

Every MF-produced bundle must carry a **compatibility descriptor** sufficient for compatibility-aware ACTIVE resolution:

* required feature group versions (minimum),
* any declared input expectations needed for safe DF usage.

### MF-P8 — Gate posture and publish eligibility

MF produces an explicit **PASS/FAIL gate receipt** tied to the run + evidence refs.
Only **PASS** bundles are eligible to be published into Registry lifecycle. (MF may still write FAIL artifacts for forensics, but no “publish anyway.”)

### MF-P9 — Append-only truth, immutable artifacts

MF’s run records, evaluation reports, gate receipts, and bundles are **append-only / immutable**. Corrections happen by new runs/bundles + “supersedes” relationships (no silent overwrite).

### MF-P10 — MF is a job unit with real retry semantics

MF runs as **scheduled/on-demand job**. It must be safe under:

* retries (resume/continue),
* publish-retry without retrain,
* partial failure (training done, registry down).

---

## What can stay unpinned until we open the black box

These don’t need pinning to design joins cleanly:

* ML framework / algorithm family
* tuning strategy
* compute substrate (local batch vs managed)
* exact metric computation library
* artifact storage backend details
* orchestrator choice 

---

If we accept these pins, then the joins become straightforward because they’re *forced* by the laws above (manifests-only intake, explicit as-of, compatibility descriptor, PASS gating, registry-only activation).

---

Yes — and the key is: **MF as a vertex has only a few *direct* joins**, but it participates in **many paths/loops** because it sits in the **Learning ↔ Production feedback boundary**.

Below is the **full production-ready set** of joins/paths/loops that *touch MF*, while keeping MF opaque (black box). I’m separating **hard (pinned) joins** from **supporting joins** so you can see what’s mandatory vs operationally helpful.

---

## 1) All joins incident to MF (vertex-level adjacency)

### A) Hard joins (these are the “real” MF edges in the platform graph)

**J15 — Offline Feature Shadow → MF**

* What crosses: **DatasetManifests + evidence** (not raw dataframes).
* Meaning: MF’s only legitimate training-input boundary is *manifested, pinned datasets*.

**J16 — MF → Model/Policy Registry**

* What crosses: **Bundles + promotion evidence** (eval evidence + PASS/FAIL receipts where required + compatibility metadata).
* Meaning: MF produces deployables; **Registry governs activation + lifecycle**.

These two are the **core MF joins**. Everything else is control/ops scaffolding around those joins.

---

### B) Control-plane joins (job triggering + governed change)

**Run/Operate → MF (trigger)**

* Run/Operate triggers jobs; MF is a scheduled/on-demand job unit.

**MF → `fp.bus.control.v1` (optional gov facts)**

* MF may emit low-volume governance/control facts (start/end/fail/published) for operational traceability.

**Registry → `fp.bus.control.v1` (lifecycle events)**

* Registry emits lifecycle events; activation/rollback are governed actions and auditable facts.

---

### C) Substrate “joins” (not components, but real production edges MF must use)

These are unavoidable because they’re where pinned truth lives:

**MF ↔ Object Store (`ofs/`, `mf/`, `registry/bundles/`, `profiles/`, `gov/`)**

* MF reads `ofs/...` manifests/materializations; writes `mf/...` evidence; bundles live under `registry/bundles/...`; profiles in `profiles/...`; governance facts in `gov/...`.

**MF ↔ Profiles/Policy Artifacts (versioned configs)**

* MF consumes versioned policy/config artifacts (to make runs reproducible and attributable).

**MF ↔ Observability pipeline (OTLP)**

* MF emits traces/metrics/logs like any unit (important for “production-shaped” ops, even though it’s not domain truth).

---

## 2) All paths that traverse MF (production-ready “routes”)

Think of these as *ways reality flows through MF*.

### Path P1 — Standard learning→deploy path (the canonical one)

**EB/Archive + Label Store → Offline Shadow → MF → Registry → DF**

* Shadow builds deterministic datasets “as-of T” and emits manifests.
* MF trains/evals and publishes bundle+evidence.
* Registry activates (governed), DF resolves deterministically and records bundle ref.

### Path P2 — “What we knew then” evaluation (honest regression)

**Label correction today → Shadow rebuild “as-of decision time” → MF eval-only or retrain → Registry**
This is enabled by label timeline + as-of rules (late labels are normal).

### Path P3 — Compatibility-gated rollout path

**MF publishes bundle → Registry checks compatibility metadata → activation allowed/blocked → DF resolution enforces compatibility + degrade mask**

* Compatibility is enforced at promotion and at resolution (fail closed / safe fallback).

### Path P4 — Publish retry path (operational reality)

**MF run succeeded (artifacts exist) → Registry API temporarily fails → MF retries publish without retraining**
This is implied by MF being a job with real networking + durable dependencies.

### Path P5 — Promotion pipeline path across environments (local→dev→prod)

**MF produces bundle in dev → Registry lifecycle promotes → prod activation uses same immutable artifacts**
Promotion is artifact/profile selection, not semantic fork.

### Path P6 — “Golden flow” full-stack integration path (MF included)

The pinned integration flow explicitly exercises:
**Offline Shadow → MF → Registry**, alongside hot path components.

---

## 3) All loops (cycles) that include MF (production-ready feedback cycles)

These are the important “time passes / ops happens” cycles; they’re where drift usually sneaks in.

### Loop L1 — Continuous improvement loop (the main platform learning cycle)

**Traffic (EB) → Decisions (DF/AL) → Audit (DLA) → Cases/Labels → Shadow → MF → Registry → back to DF**

* Audit preserves decision-time provenance needed for faithful rebuild/parity.
* Labels evolve; Shadow + MF can reproduce “then vs now.”

### Loop L2 — Late-truth correction loop (labels arrive late)

**Case Workbench → Label Store (append-only) → Shadow rebuild → MF retrain/eval → Registry**
Late labels are normal; “as-of” makes it safe.

### Loop L3 — Backfill/rebuild loop (history changes *derived* state, not truth)

**Run/Operate declares backfill → Shadow rebuilds datasets (new basis) → MF retrains → Registry lifecycle event**
Backfill is explicit + auditable; outputs are new derived artifacts (no silent overwrite).

### Loop L4 — Feature-definition evolution loop (anti training/serving drift)

**Feature definitions/version set changes (governed) → Shadow rebuild with new versions → MF produces bundle declaring required versions → Registry/DF enforce compatibility**
This is the platform’s drift killer.

### Loop L5 — Incident / rollback loop (ops safety loop)

**Bad behavior observed → governed Registry rollback → DF starts resolving previous ACTIVE → postmortem leads to new MF run**
Registry is the chokepoint for production logic changes; rollback is lifecycle mutation with audit fields.

### Loop L6 — Governance/auditability loop (explainability of change)

**MF run produces evidence → Registry lifecycle emits event → Decisions cite bundle ref → Audit records provenance → later you can answer “what changed and why?”**
This loop is pinned as a core explainability property (DF records bundle ref; registry events are attributable).

---

## 4) MF’s “outer network picture” as an adjacency list (opaque vertex)

```
(Label Store + EB/Archive) ──J14──> Offline Shadow ──J15──> MF ──J16──> Registry ──J10──> DF
          ▲                         │                  │         │
          │                         │                  │         └─ emits lifecycle events → fp.bus.control.v1
          │                         │                  └─ optional gov facts → fp.bus.control.v1
          │                         └─ optional gov facts → fp.bus.control.v1
Case Workbench ──J13──> Label Store

Run/Operate ──triggers──> Offline Shadow / MF / backfills (declared + auditable)
```

Grounding: MF reads/writes the by-ref substrates (`ofs/…`, `mf/…`, `registry/bundles/…`, `profiles/…`, `gov/…`) and is a job unit in production shape.

---

### The “careful conclusion” (so you can sanity-check completeness)

If we keep MF opaque, then in a production-ready platform **every interaction MF has** falls into one of these buckets:

1. **Data/evidence in:** J15 manifests (from Shadow) 
2. **Deployables/evidence out:** J16 bundles (to Registry) 
3. **Control:** trigger + governance facts (Run/Operate + control bus)
4. **Substrate:** object store + profiles + observability

Everything else (models/metrics/algorithms) is inside the black box and **doesn’t change** the outer network.

---

Here’s the **order I’d expand the complete MF-touching production joins/paths/loops** (from *closest-to-MF edges* → *system-level routes* → *feedback cycles*), staying within the pinned platform network.

1. **J15 — OFS → MF** (DatasetManifest intake boundary) 

2. **J16 — MF → Registry** (bundle publish + evidence) 

3. **Run/Operate → MF** (trigger: train/eval request; retry/cancel semantics) 

4. **MF ↔ Object Store** (`ofs/...` reads; `mf/...` writes; bundle staging refs)

5. **MF ↔ Profile/Config artifacts** (versioned training/governance profiles) 

6. **MF → Observability pipeline** (metrics/logs/traces as a job unit) 

7. **MF → Control bus (optional)** (training run facts: started/ended/published)

8. **Registry → Control bus** (bundle lifecycle events MF must coexist with)

9. **P1 — Standard learning→deploy path**: EB/Archive + Labels → OFS → MF → Registry → DF 

10. **P4 — Publish-retry path**: PASS artifacts exist → Registry publish retries (no retrain)

11. **P3 — Compatibility-gated rollout path**: MF metadata → Registry gating → DF resolution 

12. **P2 — “What we knew then” eval path**: late labels → OFS as-of rebuild → MF eval/retrain 

13. **P5 — Cross-environment promotion path**: dev bundle → governed promotion → prod activation

14. **P6 — Golden-flow integration path** (end-to-end platform validation flow including MF)

15. **L1 — Continuous improvement loop** (traffic→labels→OFS→MF→Registry→DF) 

16. **L2 — Late-truth correction loop** (append-only labels → rebuild → retrain/eval) 

17. **L3 — Backfill/rebuild loop** (explicit backfill → new manifests → new bundles)

18. **L4 — Feature-definition evolution loop** (version changes → rebuild → compatibility enforcement) 

19. **L5 — Incident/rollback loop** (Registry rollback → DF resolves prior ACTIVE → postmortem → new MF run)

20. **L6 — Governance/explainability loop** (bundle provenance → decisions cite bundle → auditability)

---

Alright — expanding **1–4** with **MF kept opaque**. I’m going to pin the *outer* truths that MF and its neighbors must obey, and I’ll be explicit about failure dispositions and “what must be recorded” so nothing hides behind assumptions.

---

# 1) J15 — Offline Feature Shadow → Model Factory

**DatasetManifest intake boundary (MF’s only valid data-plane input)**

## Purpose of the join

J15 exists to ensure **MF never trains on ambiguous, drifting, or “latest” data**. The *only* admissible training inputs are **pinned dataset definitions** produced by Offline Shadow.

## What crosses the join (authoritative)

### A) DatasetManifest (the primary object)

Offline Shadow produces a **DatasetManifest** that pins (at minimum):

* dataset identity
* time window + **as-of boundaries**
* join keys + entity scoping
* feature group versions
* refs/digests to materializations
* provenance (sources + transformations) 

### B) Evidence (supporting objects)

Offline Shadow must also record its deterministic rebuild basis, including:

* input event window **by offsets** (or time window tied to offsets)
* as-of boundary
* feature definitions/versions used
* optional parity anchors (e.g., target snapshot hashes) 

**Pin:** This evidence may be embedded inside the DatasetManifest or referenced by it, but it must be **reachable by-ref** and must remain resolvable.

## The handshake semantics (how this works operationally)

J15 is **by-ref**, not streaming:

* Offline Shadow **writes** `ofs/...` materializations + manifest(s).
* MF **reads** the manifest(s) and materializations by ref + digest, then proceeds.

Optional (but production-helpful): Offline Shadow emits a low-volume control fact that a manifest is ready; *even if you do that*, MF must still treat the manifest content as the authority (not the event).

## MF’s non-negotiable obligations on J15 (pins)

MF must treat DatasetManifests as **immutable inputs** and enforce:

1. **Integrity**: manifest digest matches; referenced objects exist; materialization digests match.
2. **Completeness**: as-of boundary + offsets basis + feature versions are present (not implied).
3. **Re-resolvability**: MF may only declare a training run “reproducible” if the *exact* manifest(s) can be re-resolved later. 
4. **No “helpful fixes”**: if something is missing/invalid, MF fails the run (does not “guess”).

## Offline Shadow’s obligations (so MF can stay strict)

Offline Shadow must ensure the manifest pins **enough** that MF does not need to read EB/Archive or Label Store directly (that is Shadow’s job in the pinned graph).

## Failure dispositions (what happens when something is wrong)

This is important because “quarantine vs reject” is where drift hides.

**MF disposition for J15 failures (authoritative):**

* **Reject the training run** (no publish attempts) if:

  * manifest/evidence missing required fields,
  * digest mismatch,
  * referenced objects missing/unreadable,
  * feature version set unavailable/unresolvable.
* MF must still **persist an auditable failure record** (by-ref pointers to what it tried to read and why it refused).

## Minimal trace (J15 only)

1. Offline Shadow writes `ofs/<dataset_id>/...` materializations + `DatasetManifest` + basis evidence.
2. MF resolves the manifest, verifies digests, checks that basis/as-of/version pins are present.
3. MF proceeds or rejects (and records why).

---

# 2) J16 — Model Factory → Model/Policy Registry

**Bundle publish boundary (deployable artifacts + promotion evidence)**

## Purpose of the join

J16 exists to ensure “deployment readiness” is **evidence-based** and that **activation is governed** (Registry is the sole ACTIVE authority).

## What crosses the join (authoritative)

MF publishes **Bundles + evidence for promotion**, where a bundle must include:

* bundle identity
* immutable refs/digests to artifacts (weights/rules/thresholds/metadata)
* training run provenance (which DatasetManifests were used)
* evaluation evidence
* PASS/FAIL receipts where governance requires it
* **compatibility metadata** (expected feature versions/inputs) so DF can enforce safe resolution later

## The handshake semantics (how publish works in production shape)

From the deployment mapping:

* MF is a **job** that writes `mf/...` evidence artifacts and **publishes bundle to registry (API)**. 
* Registry is a **service** that persists lifecycle truth in `registry` DB and stores bundle blobs under `registry/bundles/...`; it also emits lifecycle events to `fp.bus.control.v1`.

### Pin: “who writes `registry/bundles/...`?”

To avoid truth drift:

* **Registry is the authoritative writer** for `registry/bundles/...`.
* MF may stage artifacts under `mf/...` and then publish by reference; Registry must ensure that once accepted, the bundle’s artifacts are durably resolvable (copy or link under registry control).

## Registry-side enforcement (so MF isn’t the only guardrail)

Even though MF should only publish PASS-eligible bundles, Registry must still enforce:

* required evidence present
* compatibility metadata present
* lifecycle/audit rules (promotion/rollback auditable, ACTIVE is registry-only)

## Idempotency + duplicates (production reality)

**Pin (authoritative):** J16 publish must be idempotent.

* If MF retries the same publish (network, crash, timeout), Registry must return the same bundle identity/state, not create duplicates.
* If MF attempts to publish “same bundle identity but different digest,” Registry must reject as conflict.

## Failure dispositions (what happens when publish fails)

* **Transient failure (Registry down / timeout):** MF records “publish pending/failed” and allows publish retry **without retraining**.
* **Validation failure (missing evidence / incompatible metadata):** Registry rejects; MF records rejection; no activation changes occur.

## Minimal trace (J16 only)

1. MF produces candidate bundle + evidence refs (by-ref, immutable).
2. MF calls Registry publish API with bundle metadata + refs/digests. 
3. Registry persists lifecycle, stores artifacts under `registry/bundles/...`, emits lifecycle event.

---

# 3) Run/Operate → MF

**Trigger + governed change boundary (why MF runs, with what intent)**

## Purpose of the join

MF must not be a “free-running trainer.” In the pinned deployment shape, MF is a **scheduled/on-demand job** invoked explicitly, and Run/Operate is the orchestrator layer that triggers jobs and writes governance facts.

## What crosses the join (pinned outer expectation)

A **TrainBuildRequest**-style trigger must be **by-ref** and must pin:

* **which DatasetManifest refs** to use (from `ofs/...`)
* which training/config profile revision to use (`profiles/...`)
* trigger provenance (who/what/why) for governance/auditability
* intent/class (scheduled retrain vs backfill retrain vs eval-only vs regression check)

### Pin: MF is not allowed to “choose data”

Run/Operate (or the upstream pipeline) chooses manifests; MF consumes what it is told, and rejects ambiguity. This preserves the “no scanning/latest” rail.

## Operational semantics that must exist (production-ready)

### A) Idempotent triggering

Run/Operate triggers will be retried. MF must be safe when:

* the same request arrives twice,
* the orchestrator restarts,
* “start” is sent again because status is unknown.

### B) Best-effort cancel (optional but realistic)

Run/Operate may request cancel; MF may comply if still running, but must record the outcome (canceled vs too-late). This is an ops convenience, not a correctness primitive.

### C) Governance facts for “outcome-affecting change”

Run/Operate writes governance facts (`gov/...` + optional control-bus facts) about deploys/config activations/backfills; MF runs must link to these facts so later you can answer “why did we retrain?”

---

# 4) MF ↔ Object Store

**The real data plane for MF (by-ref reads/writes, immutable artifacts)**

## Why this “join” matters

In this platform, the object store is where the **immutable evidence blobs** live (engine outputs, manifests, audit records, MF evidence, bundles). MF’s correctness depends on treating object refs as primary, not “whatever is on disk today.”

## Pinned storage topology (from your deployment map)

Single bucket `fraud-platform` with prefixes including:

* `ofs/` (offline shadow materializations + DatasetManifests)
* `mf/` (training run outputs + eval evidence)
* `registry/bundles/` (bundle artifacts)
* `gov/` (governance facts)
* `profiles/` (versioned profiles/configs)

MF’s mapping in that table is explicit:

* **Reads:** `ofs/...` DatasetManifests; config profiles
* **Writes:** `mf/...` training/eval evidence; publishes bundle to registry (API) 

## MF object-store laws (authoritative pins)

1. **Immutable writes**: once MF writes an artifact that it might reference again (or that Registry might ingest), it must never be overwritten silently. (New attempt = new object or versioned object.)
2. **Digest-first referencing**: MF must record digests for the objects it consumes and produces, so “same ref, different bytes” becomes detectable corruption, not hidden drift.
3. **Two-phase completion marker**: MF should treat a training run’s output directory as incomplete until a final “complete marker” object exists. This is how restarts don’t create half-truth runs. (No tool-lock-in; just the concept.)
4. **Clear namespace boundaries**: MF owns `mf/...`; Registry owns `registry/bundles/...`. MF doesn’t “become the registry” by writing into registry truth space.

## Minimal MF layout under `mf/` (conceptual, not a spec)

This is just to avoid chaos later; feel free to change exact names, but the *structure* matters:

* `mf/train_runs/<train_run_id>/inputs/` (snapshotted refs: dataset manifests + config refs + digests)
* `mf/train_runs/<train_run_id>/artifacts/` (model/policy artifacts)
* `mf/train_runs/<train_run_id>/eval/` (evaluation reports + metrics)
* `mf/train_runs/<train_run_id>/gate/` (PASS/FAIL receipt + reasons + thresholds)
* `mf/train_runs/<train_run_id>/bundle_candidate/` (the publishable bundle manifest before registry ingestion)
* `mf/train_runs/<train_run_id>/_COMPLETE` (completion marker)

This supports the required production behaviors in the deployment notes: retries, durable evidence, and later registry ingestion.

---

## What I’m pinning as “now authoritative” from this expansion

* **J15** is the *only* MF training input boundary: **DatasetManifests + deterministic basis evidence**, by-ref, immutable.
* **J16** is publish-by-evidence: **bundle includes provenance + eval + PASS posture + compatibility metadata**; Registry alone decides ACTIVE; publish is idempotent.
* **Run/Operate triggers MF**; MF does not self-select data or self-deploy; governance links must exist.
* **MF owns `mf/...` and reads `ofs/...`; Registry owns `registry/bundles/...`**; immutability + digests + completion markers prevent drift.

---

Alright — expanding **#5–#8**, still treating **MF as opaque** and keeping everything aligned to your pinned platform + deployment rails.

---

# 5) MF ↔ Profile/Config artifacts (`profiles/...`)

Your deployment map already pins that MF **reads config profiles** and that profiles are a **first-class substrate** for the platform.
And your config rails pin the critical split: **policy config** (outcome-affecting) vs **wiring config** (non-semantic).

## 5.1 What MF *needs* from “profiles” (outer expectation)

### A) MF Wiring Profile (non-semantic, but operationally necessary)

Examples:

* registry endpoint URL, object store endpoints, OTLP collector endpoint
* worker concurrency, memory limits, timeouts/retry knobs
* “where to write” prefixes (still must respect ownership: `mf/...` is MF; `registry/bundles/...` is Registry)

**Rule:** wiring config can differ local/dev/prod without claiming it changed decision semantics.

### B) MF Policy Profile (outcome-affecting: must be versioned + auditable)

Examples:

* leakage/as-of discipline requirements (what MF must enforce)
* minimum evaluation metrics required for a “valid candidate”
* gate thresholds / pass criteria (even if defined as “must supply GateReceipt”)
* any privacy constraints (e.g., “never export raw training rows”) — still enforced by MF as a platform law

**Rule:** policy config is a **versioned artifact** with stable id + digest + monotonic revision, and MF must cite the **policy revision used** in its run evidence.

### C) Training Recipe / Training Config (outcome-affecting)

This is the “what are we training?” artifact:

* model/policy family identifier
* feature group/version expectations (must align with the platform’s single feature-version authority rail)
* label family / target definition
* split policy / evaluation windows (explicit, no “latest”)
* hyperparams / thresholds (where applicable)

**Rule:** treat it as policy config: versioned, digestable, and referenced by-ref.

## 5.2 How profiles are promoted (and how MF must behave)

Your CI/CD lane pins three promotion lanes, and MF lives at the intersection of:

* **lane 2: policy/profile promotion**, and
* **lane 3: model/policy bundle promotion**.

### The pin that matters for MF

* **MF must never “pick whatever is active later.”**
  For reproducibility, **the TrainBuildRequest must pin exact profile/config revisions** (or Run/Operate must resolve “current active rev” at trigger time and pass the resolved refs).

This keeps you aligned with:

* “promotion is environment-profile selection, not code branching”
* “runtime components always report which policy rev they are using” (MF included)

## 5.3 Secrets posture (MF must not leak provenance)

MF will inevitably need secrets (registry auth tokens, object store creds, etc.). The rail is pinned:

* **Secrets are runtime-injected and never embedded in artifacts or provenance.**
  MF may record a **secret identity** if needed (e.g., “key_id”), but not secret material. 

## 5.4 Failure posture for profile/config joins (important)

MF must fail closed when:

* profile/config ref can’t be resolved
* digest mismatch / corrupted artifact
* requested revision not approved/allowed under environment policy

…and it must record an auditable failure outcome referencing the missing/invalid ref. (That’s the same “no silent drift” posture as the rest of the platform.)

✅ **Authoritative MF pin from #5:**
**Every MF run must be attributable as “code build X + policy/profile revs Y + dataset manifests Z.”**

---

# 6) MF → Observability pipeline (OTLP: metrics/logs/traces)

Your deployment stack pins:

* **OTLP everywhere** and
* observability is not domain truth, but it’s required for safe ops.
  And it pins an “observability baseline” that includes correlation keys and golden signals.

## 6.1 What MF must emit (even as a job)

MF is a **job unit**, but it still needs production-grade observability because:

* training runs are long,
* failures can be expensive,
* publish/registry interactions must be explainable.

### A) Correlation keys (must be carried everywhere)

MF telemetry must carry:

* `train_run_id`
* `request_id` (trigger id / idempotency key)
* dataset manifest digests/refs (at least a compact “input_fingerprint”)
* profile/policy revision ids used
* produced bundle id/ref (if any)
* code build id / commit SHA

This aligns with “universal correlation keys carried everywhere” in your baseline pin.

### B) Metrics: golden signals + MF-specific safety metrics

You already pinned golden signal thinking and platform-specific metrics philosophy; apply it to MF as:

**Golden signals (job-shaped):**

* throughput: runs started/completed per time
* latency: run duration (p50/p95) + stage durations
* error rate: by failure class (input resolution, train failure, eval failure, publish failure)
* saturation: queued runs, active workers, resource usage/backlog

**MF-specific minimums (drift killers):**

* dataset manifest resolve failures (by reason)
* gate FAIL rate vs PASS rate
* registry publish retries + publish conflict rate
* registry rejects due to missing compatibility metadata (should be near zero if MF is behaving)

### C) Traces (even offline)

Minimum viable: one trace per TrainBuildRequest, with spans for:

* resolve manifests/configs
* train
* evaluate
* gate decision
* package bundle
* publish to registry

Sampling can differ by environment, but propagation semantics must remain identical.

### D) Logs

MF logs should be structured and cite:

* policy revs used (CICD-5 posture)
* train_run_id / request_id
* outcome (PASS/FAIL) + reason codes
* bundle ref or “no bundle produced”
  This is how you avoid “it worked yesterday” mysteries.

---

# 7) MF → `fp.bus.control.v1` (optional control/governance facts)

Your deployment mapping explicitly allows:

* MF emits **optional gov facts → `fp.bus.control.v1`**.

## 7.1 Why emit MF facts on the control bus at all?

Because your governance rail is: **changes must be durable facts, not just logs**.
Publishing a candidate bundle is an outcome-affecting capability (even if activation is separate), so it’s useful to have a lightweight broadcast trail.

## 7.2 What MF control facts should be (and what they must NOT be)

### They should be:

* **low-volume**
* **by-ref pointers** to authoritative artifacts in `mf/...` and/or `gov/...` (not embedded datasets, not embedded model blobs)
* **idempotent** under retries (duplicates must not create contradictory stories)

### They must NOT be:

* the source of truth for MF runs (truth is in `mf/...` evidence)
* “activation signals” (Registry governs activation)

## 7.3 Minimal MF event set (v0)

If you emit anything, emit only these:

1. `mf.train_run.started`
2. `mf.train_run.completed` (includes PASS/FAIL posture)
3. `mf.bundle.published` (only when registry accepts publication)

Each event payload should primarily contain:

* `train_run_id`, `request_id`
* refs/digests: input manifests, config/profile revs
* `mf_run_record_ref` (pointer to `mf/...`)
* if applicable: `bundle_ref` / `registry_bundle_id`

## 7.4 Envelope posture on the control bus

Your bus boundary shape pins a canonical envelope with required `{event_id, event_type, ts_utc, manifest_fingerprint}`.
So, **if MF emits to the bus**, it should still wrap facts using the canonical envelope.

**Authoritative convention (to avoid ambiguity):**

* If the MF run is naturally scoped to a single world, use that `manifest_fingerprint`.
* If it is not world-scoped, use a **platform-global sentinel** (e.g., `manifest_fingerprint = 00…00` hex64) and carry MF scope (`train_run_id`, etc.) in payload.

That keeps schema validity without pretending every MF fact is about a single world.

## 7.5 Failure posture

If the control bus is unavailable:

* MF must still complete its durable writes (`mf/...`) and registry publish (if possible).
* MF control events are best-effort; they are not correctness-critical.

This matches the deployment notion: bus control facts are helpful signals, but primary truths are DB/object artifacts.

---

# 8) Registry → `fp.bus.control.v1` (registry lifecycle events)

This is pinned in both places:

* deployment map: registry emits lifecycle events to control bus
* platform blueprint: registry lifecycle mutations are privileged and must emit an append-only RegistryEvent with `actor` and `reason`.

## 8.1 What registry events represent (authoritative)

Registry events represent **deployable-truth changes**:

* publish accepted
* approve/promote/activate
* rollback
* retire

They are the auditable explanation for “why did decision logic change?”

## 8.2 Minimum contents of a RegistryEvent (outer expectation)

Your blueprint already pins the conceptual minimum shape: 

* `actor_principal`
* `governance_action` (publish|approve|promote|rollback|retire)
* `from_state -> to_state`
* `bundle_id` + immutable refs/digests
* `scope`
* `approval_policy_rev`
* `reason`
* evidence refs (eval + GateReceipt where required)

Also, compatibility must be present and enforced at promotion time, not merely “nice to have.” 

## 8.3 How other components should use registry events

### DF (hot path)

DF should not *need* the event stream to function; it resolves via Registry read API and records the resolved bundle ref in provenance (pinned). 
Registry events are still useful for dashboards and offline reasoning.

### Run/Operate / Governance tools

Registry events are primary inputs for:

* lineage views (“bundle X became ACTIVE at time T because reason R”)
* incident response (“rollback occurred”)

### MF

MF may *listen* for lifecycle events to learn what happened to its published bundle, but it must treat them as **notifications**, not as the authoritative publish receipt (MF’s authoritative receipt is the Registry publish API response + durable registry state).

## 8.4 Idempotency + ordering posture

Registry is authoritative in its DB; bus events are an emitted stream:

* events must be safe under retries (no duplicate “promote” that produces two conflicting states)
* “truth first, signal second”: DB commit happens, then event emission (and emission can be replayed if needed)

This matches the stateful substrate pin: registry DB is truth; bus events are a distribution mechanism.

## 8.5 Envelope posture on registry control events

Same as MF control facts: if emitted on `fp.bus.control.v1`, wrap as canonical envelope (so the bus boundary remains stable), and use world pins only when they truly apply.

---

## Net effect of #5–#8 (why these edges matter)

These four edges are what make MF/Registry **operable and explainable** in production:

* **Profiles** make behavior reproducible and “explainable as code X + profile rev Y.”
* **Observability** makes long offline jobs diagnosable and safe to run repeatedly.
* **MF control facts** (optional) let you see training/publish outcomes without crawling storage.
* **Registry lifecycle events** are the platform’s explicit record of decision-logic changes.

---

Alright — expanding **#9–#12** as **production paths** that traverse MF, while keeping MF itself **opaque** (we only talk about what must be true at the boundaries, and how the platform routes/loops around MF).

---

# 9) P1 — Standard learning → deploy path

**EB/Archive + Label Store → OFS → MF → Registry → DF**

## P1.1 What this path is “for”

This is the **canonical bridge** from *replayable reality* to *deployable decision logic*:

* Learning consumes **replayable facts** (EB/Archive) plus **label truth** (Label Store timelines).
* Offline Shadow produces **pinned training datasets** (DatasetManifests) so training cannot drift.
* MF turns manifests + profiles into **evidence-backed bundles**.
* Registry governs lifecycle + ACTIVE deterministically; DF consumes only Registry-resolved deployable truth and records the bundle ref used.

## P1.2 The end-to-end trace (outer-network view)

### Step 0 — “Rebuild targets” exist because RTDL leaves provenance behind

For learning to be faithful, the platform must be able to reconstruct what the system could have known:

* event basis (EB coords / watermarks),
* `graph_version`,
* `feature_snapshot_hash` + `input_basis`,
* degrade posture,
* resolved bundle ref.

(That’s why DLA/decision provenance is “glue” for learning.)

### Step 1 — Label truth is written (append-only timelines)

Case produces assertions; Label Store is the **only label truth** used for learning, with **effective_time vs observed_time** and append-only corrections.

### Step 2 — Offline Shadow rebuilds training datasets deterministically

Offline Shadow reads:

* admitted event history from EB (within retention) and Archive (beyond retention) as **one logical fact stream**, and
* labels via **explicit as-of** rules to prevent leakage.

It must record **replay basis explicitly** (offset ranges/checkpoints, or time windows anchored to offsets), and pin feature definition versions used.

### Step 3 — Offline Shadow emits DatasetManifests + materializations

Instead of “a dataframe,” it produces a **DatasetManifest** that pins:

* dataset identity,
* time/as-of boundaries,
* join keys + entity scope,
* feature group versions,
* refs/digests to materializations,
* provenance (sources + transformations).

### Step 4 — MF consumes manifests + profiles, produces evidence + candidate bundle

MF (opaque) is invoked with:

* DatasetManifest refs (from `ofs/...`),
* config/profile refs (from `profiles/...`),
  and writes evidence under `mf/...` (train/eval), then publishes a bundle to Registry via API.

### Step 5 — Registry accepts bundle, governs lifecycle, resolves ACTIVE deterministically

Registry persists lifecycle truth (`registry` DB), stores bundle blobs under `registry/bundles/...`, and emits lifecycle events to the control bus.
ACTIVE resolution is deterministic and not “latest by default.”

### Step 6 — DF uses Registry resolution and records provenance

DF resolves bundle from Registry, uses OFP snapshots + IEG context + DL posture, and must include the resolved bundle ref (and basis) in decision provenance for audit/replay.

## P1.3 The key “drift killers” in this path (what must never be violated)

* **DatasetManifests are the unit of reproducibility.** No manifest → no MF training.
* **Replay basis is explicit; watermarks don’t lie.** No “time travel”; rebuilds declare basis.
* **Feature versions are singular and must match across serving + shadow + bundles.**
* **Registry is the only deployable truth source; activation is governed.**

---

# 10) P4 — Publish-retry path

**PASS artifacts exist → Registry publish retries (no retrain)**

This path exists because production reality includes: timeouts, crashes, partial failures, and duplicate triggers. MF is a **job**; Registry is a **service**.

## P4.1 The minimal publish-retry story (what must be true)

1. MF has already produced durable artifacts under `mf/...`:

   * training/eval evidence,
   * a candidate bundle description (by-ref + digests).

2. MF attempts to publish to Registry and fails transiently (network/timeout/registry restart).

3. MF retries **publish only** using the same bundle identity/ref/digests — **no retrain required**.

## P4.2 Idempotency requirements (where retries stop becoming drift)

**Pin:** publish must be idempotent and conflict-detecting.

* If Registry already accepted the publish but MF didn’t get the response, the retry must return “already published” (same bundle id/state).
* If MF retries with “same bundle id but different digests,” Registry must reject as a conflict (prevents silent overwrites).

## P4.3 What gets recorded (so ops can explain the incident)

* MF should be able to leave a durable “publish attempted / publish failed / publish succeeded” trail tied to the training run evidence (object-store truth), and optionally emit a control fact when publish finally succeeds.
* Registry lifecycle events are the authoritative record of publication/promotion/rollback state changes.

---

# 11) P3 — Compatibility-gated rollout path

**MF metadata → Registry gating → DF resolution**

This is the platform’s *anti training/serving drift* and *safe rollout* mechanism.

## P3.1 What “compatibility-gated” means (authoritative)

* Bundles **declare compatibility**; DF never guesses.
* Registry resolution is **compatibility-aware**, not just “ACTIVE.”
* Compatibility must cover at least:

  * required FeatureGroups + versions,
  * required capabilities (so degrade can disable bundles safely),
  * an input contract version (even if implicit in v0, it becomes explicit as you evolve).

## P3.2 The rollout trace (outer-network)

1. MF publishes bundle + compatibility contract + evidence.
   Registry treats “missing compatibility metadata” as **not a valid deployable artifact**.

2. Registry lifecycle promotes bundle via governed action (approve/promote/activate), emitting a RegistryEvent with actor + reason + evidence refs as required.

3. At decision time, DF resolves bundle from Registry **with current context constraints**:

   * are required feature versions satisfiable (OFP/Shadow parity contract),
   * do required capabilities survive current degrade mask?

4. If incompatible, the system **fails closed or routes to an explicitly defined safe fallback**, never “half compatible.”

5. DF records the resolved bundle ref plus the compatibility basis in provenance:

   * resolved bundle ref,
   * feature group versions actually used (from OFP),
   * degrade posture in force.

## P3.3 Why this path matters operationally (concrete scenarios)

* **Feature pack upgrade lag:** MF publishes a bundle requiring FeatureGroup v7. If OFP/serving is still on v6, Registry must not resolve that bundle for DF. No silent drift.
* **Degrade mode:** DL masks out capabilities; Registry/DF must refuse bundles that require disabled capabilities (or fall back safely).

---

# 12) P2 — “What we knew then” evaluation path

**Late labels → OFS as-of rebuild → MF eval/retrain**

This path exists because your platform pins: **late labels are normal**, and **as-of makes them safe**.

## P2.1 What this path is “for”

It allows you to produce two distinct (non-confusable) dataset families:

* **“What we knew then”**: honest evaluation against the information available at the decision time.
* **“What we know now”**: improved training using later-arriving/corrected labels.

## P2.2 The “what we knew then” trace

1. Pick a decision-time target (or window) and its rebuild basis:

   * use explicit replay basis (offsets/checkpoints) and an as-of boundary,
   * don’t pretend the stream changed (watermarks remain monotonic).

2. Offline Shadow rebuilds events/features up to that as-of, using the same feature versions, and reads labels from Label Store using leakage-safe **as-of rules** (observed/effective posture).

3. Offline Shadow emits a DatasetManifest explicitly marked (conceptually) as “as-of decision time T” with pinned basis.

4. MF runs evaluation-only (or retrain + eval, depending on intent) using that manifest, producing evidence that can be compared apples-to-apples across time.

## P2.3 The “what we know now” trace (paired with the above)

Same event basis (or a refreshed declared basis), but:

* label as-of boundary is later (more labels observed),
* still leakage-safe and explicit,
* new manifests → new MF runs → new bundles with evidence.

## P2.4 The non-negotiable distinction (prevents self-deception)

Your pins force that “then” and “now” are never blended:

* labels are timelines (append-only) and queried **as-of**; you can reproduce either world.
* rebuild basis is explicit; “we trained on last 90 days” is meaningless without offsets/checkpoints.

---

## Quick recap of what we just “revealed” about MF from paths #9–#12 (without opening MF)

* MF’s **inputs are pinned** by Offline Shadow manifests; MF doesn’t decide what data “is.”
* MF’s **outputs become production-real only via Registry** (publish + governed activation + compatibility-safe resolution).
* The platform has a built-in honesty mechanism: **late labels + as-of rebuild** support “what we knew then” vs “what we know now,” without time-travel.
* Publish failures don’t force retraining: **publish-retry is a first-class path** (idempotent, conflict-detecting).

---

Alright — expanding **#13–#16** (P5, P6, L1, L2), with **MF kept opaque** and the expansion expressed purely as **outer-network behavior** (joins/paths/loops + what must be true, recorded, and governed).

---

## 13) P5 — Cross-environment promotion path

**dev bundle → governed promotion → prod activation**

### Why this path exists (in your platform)

You’ve pinned that promotion is **not “rewrite for prod”**; it’s selecting **immutable artifacts** under stricter profiles/policies as you move **local → dev → prod**, with the platform graph/rails staying identical.

### The three promotion lanes (the production shape)

This path is the **interlock** of your three immutable lanes:

1. **code artifacts** (build-once/run-anywhere),
2. **policy/profile revisions** (versioned + approved),
3. **model/policy bundles** (MF publishes; Registry governs activation).

### The actual route (outer-network trace)

1. **MF runs in dev** against dev-approved inputs

   * Inputs are **DatasetManifests** from OFS plus pinned profiles/configs.
   * Output is a candidate **bundle** + evidence (train/eval artifacts, digests, manifests) published to the **dev Registry**.

2. **Registry governs dev lifecycle** (publish → approve/promote → ACTIVE)

   * Activation is a separate governed step: MF does not activate.
   * Registry emits lifecycle facts (so “what changed?” is always answerable).

3. **Promotion to prod is artifact selection + governed activation**

   * Prod only promotes **immutable artifacts**: code build, config/profile revision, and bundle.
   * The promotion/activation itself must emit an auditable governance fact (“actor, scope, before/after refs, reason”).

4. **Prod DF starts resolving the new ACTIVE deterministically**

   * DF resolves from Registry and records the bundle ref used.

### What MF must guarantee so this works (even though MF is opaque)

* **Artifact drift prevention:** MF must publish bundles that are fully pinned by refs+digests (manifests, evidence, bundle blobs), so “dev-tested bundle” equals “prod-deployed bundle.”
* **Profile clarity:** “prod behavior” must be explainable as “code X + profile Y + bundle Z,” never “prod fork.”

### Rollback (part of production readiness)

Your pin is explicit: rollback exists for each lane (code rollback, config rollback, bundle rollback). For MF/Registry specifically, rollback is a **Registry lifecycle action** with governance facts (not “delete the bundle”).

---

## 14) P6 — Golden-flow integration path

**end-to-end platform validation flow including MF**

This path is literally pinned as “what a full integration run must touch” so the local stack is truly production-shaped.

### The golden flow (full route, with MF’s segment highlighted)

A single integration run should exercise:

1. **SR → Engine → SR (READY)** 
2. **Traffic through IG → EB** 
3. **IEG + OFP projections advance** (checkpoints/watermarks progress)
4. **DF → AL → outcomes** (hot loop) 
5. **DLA flight recorder** (audit/provenance by-ref, append-only)
6. **Case → Label Store** (append-only label timelines)
7. **Offline Shadow → MF → Registry** (learning → deployable truth bridge)

### What “passes” look like for the MF portion (still opaque)

When the golden flow hits step (7), you should be able to assert, in a production-shaped way:

* **OFS produced a DatasetManifest** (not just a table), and it pins replay basis + label as-of + feature versions + digests.
* **MF consumed the manifest by-ref** and produced durable evidence under `mf/...`.
* **Registry can resolve ACTIVE deterministically** (even if you keep activation trivial in local).

### The “golden-flow drift tests” you want baked in

A golden flow is only valuable if it fails on the same classes of issues prod would fail on. Dev is pinned to catch those.

So the minimal failure injections (still outer-network level) are:

* **Missing/invalid DatasetManifest pins → MF refuses** (no “best effort training”).
* **Registry publish retry works** (simulate a transient registry failure; publish is idempotent).
* **Incompatible bundle is rejected or not resolved** (compatibility-gated behavior should appear in dev).

---

## 15) L1 — Continuous improvement loop

**traffic → labels → OFS → MF → Registry → DF (repeat)**

This loop is the “platform learns and improves” cycle, but it’s constrained by your pinned rule: learning must be based on **replayable facts + decision-time provenance**, not on live caches/internal state.

### Phase-by-phase loop (outer-network)

1. **Production reality happens**
   Events arrive (admitted via IG/EB), DF makes decisions using OFP/IEG/DL and resolves a bundle from Registry.

2. **RTDL leaves rebuild targets behind**
   For every decision point, the platform must preserve enough provenance for offline rebuild: EB coordinates/watermarks, `graph_version`, feature snapshot hash + basis, degrade posture, and **bundle ref**.

3. **Human/external truth arrives as labels**
   Case produces label assertions; Label Store is the single label truth, append-only timelines with effective vs observed time.

4. **OFS reconstructs training reality deterministically**
   OFS reads EB/Archive as one logical stream and labels via explicit **as-of rules**, and records explicit replay basis + feature versions + parity anchors.

5. **MF produces candidate bundles + evidence**
   MF consumes the DatasetManifests (unit of reproducibility) and produces evidence-backed bundles, then publishes to Registry.

6. **Registry lifecycle changes what DF will use next**
   Activation/promotion/rollback are governed lifecycle actions; DF then resolves deterministically and records bundle refs in future decision provenance, closing the loop.

### What makes this loop “production ready” (the non-negotiables)

* **No drift across environments:** local/dev/prod share the same rails, meaning of READY/ADMITTED/ACTIVE, as-of semantics, and deterministic registry resolution.
* **Monotonic progress truth:** watermarks/offset basis doesn’t “time travel”; historical rebuilds are done via explicit replay basis.
* **DatasetManifests are the bridge artifact:** they pin what learning used, and that pin is what MF trains on and what Registry cites as evidence.

---

## 16) L2 — Late-truth correction loop

**append-only labels → rebuild → retrain/eval (“then” vs “now”)**

This is the “reality changed *in our knowledge*, not in the past” loop. Your pins make this first-class:

* labels are append-only timelines (corrections are new assertions),
* training joins are explicitly **as-of** so we can reproduce “what we knew then” vs “what we know now” without confusing them.

### The core loop (outer-network)

1. **Late label arrives or correction is written**
   A new LabelAssertion is appended with observed_time/effective_time and provenance.

2. **OFS rebuilds two dataset families (by explicit intent)**

   * **Then-dataset:** as-of boundary aligned to the decision point (honest evaluation).
   * **Now-dataset:** as-of boundary later (improved training with more truth).

3. **MF runs eval-only or retrain+eval depending on intent**

   * Eval-only is useful when you want to measure whether the current ACTIVE bundle would have performed under “truth we now have.”
   * Retrain+eval is the improvement step, producing a new candidate bundle + evidence.
     (MF remains opaque; the key is: the *intent* is explicit and the datasets are pinned.)

4. **Registry decides whether anything changes in production**
   A late-label correction doesn’t automatically imply “activate a new bundle.” It only changes production when a governed lifecycle action changes ACTIVE.

### The two “don’t fool yourself” rules (what keeps this loop honest)

* **Never collapse time semantics:** observed vs effective vs as-of must remain explicit (no hidden “now”).
* **Never pretend the stream changed:** late truth doesn’t rewrite history; it creates new knowledge and therefore new rebuilds/manifests.

---

Absolutely — expanding **#17–#20** as **production loops that touch MF**, while keeping **MF opaque** (we only define the *outer-network* behavior and the invariants that make the loop production-safe and non-drifting).

---

## 17) L3 — Backfill / rebuild loop

**Explicit backfill → new derived artifacts → new DatasetManifests → optional new bundles**

### What this loop is for

Backfill is how the platform **re-derives things that are allowed to change** (projections, features, datasets, parity outputs, indexes) *without pretending history changed*. It is **never silent** and must be **declared + auditable**.

### The outer-network loop (end-to-end trace)

1. **A backfill is declared (before any work runs)**
   Run/Operate creates a *declared* backfill operation with:

   * scope (streams/partitions, offset/time window),
   * purpose/reason,
   * replay basis (offset ranges/checkpoints),
   * outputs to regenerate,
   * and governance visibility.

2. **Backfill executes as a job lifecycle (same posture as other jobs)**
   Backfill runs under Run/Operate lifecycle with pinned inputs + completion receipt, so it’s traceable and repeatable.

3. **Only derived artifacts are regenerated (never primary truths)**
   Allowed targets include: IEG projections, OFP state, offline datasets/manifests, audit indexes, analytics views.
   Forbidden as “truth mutation”: EB admitted events, label timelines, registry lifecycle history, SR run ledgers, and engine outputs for a pinned identity.

4. **Offline Shadow rebuilds datasets with explicit basis and emits new DatasetManifests**
   Offline Shadow treats EB+Archive as one logical fact stream; rebuilds “as-of T” using explicit replay basis + label as-of rules and records the basis + feature versions used.
   It then emits new DatasetManifests (new IDs, new digests), never stealth-overwriting prior ones.

5. **MF may be triggered with the new manifests (optional, but common)**
   If the backfill affects training data validity (bug fix, new feature definitions, late data handling), MF consumes the new DatasetManifests and produces new evidence + candidate bundles; Registry governs whether anything becomes ACTIVE.

### The critical invariants (the drift killers)

* **Backfill is declared, scoped, and auditable; no stealth overwrites.**
* **Watermarks remain monotonic**: consumers don’t “go backward”; new derived versions advance; historical rebuilds use explicit basis instead of pretending the stream changed.
* **DatasetManifests pin the replay basis + label as-of + feature versions**, so training/eval remains reproducible even after retention changes.
* **Archive is the long-horizon continuation of EB** (same logical events), and rebuilds must record the basis used.

### Production edge cases worth planning for

* **EB retention changes**: rebuild beyond retention must use Archive “as if it were EB,” with explicit basis recording.
* **Partial backfills**: it’s normal to backfill only some partitions/windows; outputs must remain versioned so downstream knows which derived version it’s using (never “replace in place”).
* **Backfill that touches training parity**: treat “parity checks” as derived outputs too; re-run them and version them like anything else.

**Designer pin (authoritative):** A backfill always has a durable *declaration object* (governance fact) and produces new derived artifact versions; old versions remain addressable for audit/replay.

---

## 18) L4 — Feature-definition evolution loop

**Feature versions change → rebuild (online + offline) → bundles declare requirements → compatibility enforcement at Registry/DF**

### What this loop is for

It prevents **training/serving drift by construction**: the same feature definitions/versions must be used by:

* OFP (serving snapshots),
* Offline Shadow (rebuild datasets),
* MF bundles (declared requirements),
  and Registry/DF must refuse incompatibility.

### The outer-network loop (end-to-end trace)

1. **A new feature definition revision is proposed and approved (governed)**
   Feature definitions live as versioned policy/profile artifacts, promoted via the policy/config lane (propose → validate → activate with governance fact).

2. **Serving is upgraded to emit explicit feature-version provenance**
   OFP must record the feature group versions used in snapshots (so you can later reconstruct exactly what was served).

3. **Offline Shadow rebuilds using the *same* feature versions**
   Offline Shadow rebuild must pin: replay basis + as-of + **feature definitions/versions used** and can include parity anchors (e.g., target snapshot hashes) to prove “offline matches serving.”

4. **MF trains/evals on manifests pinned to that feature version set**
   MF consumes DatasetManifests (which include feature version pins) and produces bundles that declare the feature versions they require.

5. **Registry enforces compatibility at promotion and at resolution**

   * Bundles must ship compatibility metadata + evidence or they are **not valid deployables**.
   * Resolution is compatibility-aware: Registry must not return an ACTIVE-but-incompatible bundle; if incompatible, it fails closed or routes to a defined safe fallback.

6. **DF records the compatibility basis in decision provenance**
   DF must record:

   * resolved bundle ref,
   * feature group versions actually used (from OFP),
   * degrade posture in force,
     so decisions remain explainable and replayable after rollouts.

### The critical invariants

* **Feature definitions are singular and versioned** across serving, offline rebuild, and bundles.
* **Compatibility is mandatory** and enforced at promotion and resolution; DF never guesses.

### How this interacts with backfill (L3)

A “new feature definition” is explicitly called out as a common *purpose* for backfill. When features evolve, you typically need:

* OFP state rebuild (derived),
* Offline datasets/manifests rebuild (derived),
* MF retrain/eval,
  all as declared operations with governance facts.

**Designer pin (authoritative):** Feature evolution is never “deploy new code and hope.” It is: **versioned feature pack → deterministic rebuild → bundle declares requirements → registry/DF enforce compatibility**.

---

## 19) L5 — Incident / rollback loop

**Bad behavior observed → immediate safety posture → registry rollback → postmortem → new MF run**

### What this loop is for

It’s the platform’s operational safety cycle: when something goes wrong, you can:

* **constrain** behavior quickly (degrade),
* **rollback** decision logic deterministically (registry),
* **prove** what happened later (audit + provenance),
* and then **fix forward** (new MF output + governed activation).

### The outer-network loop (end-to-end trace)

1. **Detection**
   Triggers can be metrics/alerts, audit anomalies, case outcomes, drift checks, etc. (This is why your obs baseline is framed around: *what happened/why? healthy enough? what changed?*).

2. **Immediate containment: Degrade Ladder and/or safe fallback**
   Degrade posture is explicit, fail-toward-safety, and must be recorded in decision provenance.
   This can reduce impact even before a rollback completes.

3. **Rollback: a governed Registry lifecycle action**
   Rollouts/rollbacks are first-class auditable changes. Registry executes rollback and emits lifecycle events (publish/promote/rollback) with actor + before/after refs.

4. **DF behavior after rollback**
   Registry resolution is deterministic; DF resolves the now-active prior bundle and records the resolved bundle ref (and compatibility basis) in provenance going forward.

5. **Audit + explainability for the incident**
   The audit record must include: event basis, feature snapshot hash + input basis, graph_version (if used), degrade posture, resolved bundle ref, actions + idempotency keys, and supersedes on correction.

6. **Fix-forward**
   Postmortem typically triggers either:

   * evaluation-only on “what we knew then,” or
   * retrain using new manifests (possibly from backfill/feature evolution),
     leading to a new MF publish and a governed activation later.

### The critical invariants

* **Active bundle changes only via Registry lifecycle actions** (no shadow toggles).
* **DF always records which bundle was used**, so the incident blast radius is queryable (by bundle_id) later.
* **Registry lifecycle history is not mutable** (no “erase bad deploy”), consistent with “cannot backfill registry truth.”

**Designer pin (authoritative):** Incident response has *two levers* that must remain distinct: **(a) degrade constraints** (fast safety posture) and **(b) registry rollback** (decision-logic identity change). Both must be explicit and recorded.

---

## 20) L6 — Governance / explainability loop

**Bundles carry lineage → decisions cite bundle + basis → audit preserves joinable provenance → “what happened/why/what changed?” is answerable**

### What this loop is for

This is the loop that makes the platform **operable and provable**:

1. *What happened, and why?*
2. *Are we healthy enough to act?*
3. *What changed?*

### The outer-network loop (how explanation is guaranteed)

1. **Every boundary decision emits joinable facts**
   Minimum “must log” boundaries include IG admit/quarantine, SR READY, DF decision provenance (bundle ref, snapshot hash, graph_version, degrade), AL outcome, Registry publish/promote/rollback, Label assertions (append-only with effective vs observed time).

2. **Correlation keys are mandatory**
   Telemetry/events must carry the applicable subset of correlation IDs, including learning/deploy provenance keys:
   `train_run_id`, `dataset_manifest_id`, `bundle_id`, plus run/world pins and event/decision/action IDs.

3. **DLA is the canonical “decision-time provenance” store**
   Audit records must be by-ref / hashed pointers (not raw payload embedding), and DLA must quarantine incomplete provenance rather than recording half-truth. It is append-only with supersedes chains for corrections.

4. **Learning is anchored by the same provenance**
   Offline Shadow uses the replayable fact record plus decision-time provenance (snapshot hashes, watermarks, graph_version, degrade, bundle refs) to rebuild datasets that cannot drift from what serving actually did.

5. **Registry events explain “what changed”**
   DF deterministically resolves ACTIVE and records the bundle ref used, so “what changed?” is answerable as:
   “a registry event changed ACTIVE, and decisions cite the bundle ref.”

6. **Governance rules apply broadly**
   “No PASS → no read” isn’t engine-only; it applies to readiness, dataset builds, promotions, and other truth surfaces.

### What this enables in practice (the platform’s “audit join view”)

Because decisions, bundles, and datasets are all pinned and correlated, you can answer questions like:

* “Which decisions were made using bundle X?” (bundle_id in DF provenance / audit)
* “What data basis trained bundle X?” (bundle → DatasetManifest(s) → replay basis + as-of)
* “What changed at 14:03?” (registry promote/rollback event)
* “Could the system have known this at the time?” (input_basis/watermarks + as-of rules)

**Designer pin (authoritative):** If a change can affect outcomes (model rollouts, config changes, retention/backfill operations), it must be visible as a governance fact and joinable via correlation keys to the decisions it influenced.

---

Yes — the **environment ladder** is *the* lens that tells you which parts of those MF-touching joins/paths/loops must be **identical everywhere**, and which parts are allowed to vary **without changing platform meaning**. The pinned rule is: **local/dev/prod run the same platform graph + rails/join semantics**; only the **operational envelope** changes (scale, retention/archive, security strictness, reliability, observability).

Below is how that applies specifically to the MF joins/paths/loops we mapped (#1–#20).

---

## 1) What must never change across environments for MF-touching joins/paths/loops

These are the “no drift” invariants you already pinned; they apply directly to every MF path/loop:

* **Same authority boundaries and trust boundaries** (e.g., MF publishes bundles; Registry governs activation; IG is the trust boundary; Label Store is label truth).
* **Same rails/join semantics**: by-ref refs+digests, no-PASS-no-read, idempotency, append-only/supersedes, deterministic Registry resolution, explicit as-of semantics.
* **Same meaning of the words** across envs: “READY / ADMITTED / ACTIVE / LABEL AS-OF / BACKFILL” must mean the same thing locally as in prod.
* **Same reproducibility story**: any training run or bundle that exists in dev/prod must be explainable the same way as local: pinned inputs + evidence + refs.

**Implication:** none of the MF joins/paths/loops are allowed to “simplify away” these semantics in local just for convenience—local can be smaller/cheaper, but it can’t be a different platform.

---

## 2) What is allowed to differ (and how that shows up in MF paths/loops)

Allowed differences (operational envelope knobs) include: **scale, retention+archive enablement, security strictness, reliability posture, observability depth/cost**.

How that expresses in MF-land:

### A) Retention + archive differences reshape *which parts of P1/P2/L3 you can exercise*, not their meaning

* Retention windows differ by environment profile, but **offset/watermark semantics do not**.
* Archive may be absent in local (or “simulated”), but the rule remains: archive is the long-horizon extension of admitted canonical events and is accessed by pinned, by-ref bases.
* Backfills remain explicit, scoped, auditable in all envs; only *frequency/approval strictness* changes.

### B) Security strictness changes “who is allowed,” not “what happens”

Local can use permissive allowlists/credentials, but the **mechanisms must still exist** (authn/authz, quarantine access rules, registry lifecycle privileges). Dev must be “real enough” to catch unauthorized producers, incompatible bundles, missing PASS evidence. Prod is hardened + strict change control.

### C) Observability depth differs, but correlation semantics must be identical

Local can sample more; prod samples less. But trace propagation + correlation keys + boundary decision logging must remain the same; otherwise MF loops (especially L5/L6) stop being explainable.

---

## 3) Join-by-join: what the ladder changes for #1–#8

### J15 (OFS→MF) and J16 (MF→Registry)

These joins must behave identically across envs because they are the **reproducibility/deployability** boundary:

* Local/dev/prod must all enforce “MF consumes DatasetManifests (by-ref), not ‘latest data.’”
* Local/dev/prod must all enforce “Registry activation is separate; MF publishes bundles; Registry governs activation.”

**What changes by env:** dataset sizes and retention window realism, plus how strict permissions are around `ofs/…`, `mf/…`, and registry lifecycle APIs.

### Run/Operate→MF (trigger) and MF↔Object Store

* Local may trigger via CLI/job runner; dev/prod use a run launcher shape. But the trigger must still pin inputs and produce start/finish/fail lifecycle facts.
* Object store can be MinIO locally vs S3 in prod, but it must preserve the **S3-ish semantics** you pinned (by-ref addressing, digests verifiable, immutability posture).

### Profiles/config (#5)

This is the cleanest place where the ladder *intentionally* differs:

* Same binary everywhere; differences come from **profiles** (wiring + policy strictness), not code forks.
* Policy configs are versioned artifacts promoted with propose→approve→activate→rollback; MF runs must cite which policy/profile revisions were in force.

### Observability/control bus (#6–#8)

* Local can be “inspect-by-hand,” but should still run OTLP and preserve correlation keys and trace propagation (otherwise dev/prod behavior diverges).
* Control-bus emission is “helpful signal,” but correctness must rely on durable truths (DB/object store). That keeps local workable even if you downscale control-bus wiring, without changing meaning.

---

## 4) Path-by-path: what the ladder changes for #9–#14

### P1 (standard learning→deploy)

* **Local:** you still run the full path once, but with tiny windows; you prove the semantics (manifest pins, publish idempotency, deterministic resolution), not volume.
* **Dev:** must catch prod-class failures: incompatible bundles, missing PASS evidence, schema evolution issues, and backfill correctness under realistic retention.
* **Prod:** adds strict governance + retention/archive continuity + SLOs; the path is the same.

### P4 (publish retry)

This is specifically an “environment ladder honesty check”:

* If publish retry only works in prod, you’ve built two platforms.
  So local/dev must simulate failure (drop registry) and prove idempotent publish retry without retrain.

### P3 (compatibility-gated rollout)

Dev is the proving ground: it must reject incompatible bundles the same way prod would; local should include at least one “incompatible candidate” test in the golden flow.

### P5 (cross-environment promotion)

This is literally what the ladder is for:

* Promotion moves **three immutable things**: code artifacts, policy/profile revisions, and bundles.
* “Prod behavior” must be explainable as “code X + profile Y + bundle Z,” not a prod fork.

### P6 (golden-flow integration)

Pinned CI/CD says your integration test must include at least one full run that touches SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA **plus label + offline shadow + registry resolution at least once**. That is the environment ladder’s “semantic parity test.”

---

## 5) Loop-by-loop: what the ladder changes for #15–#20

### L1/L2 (continuous improvement + late-truth correction)

* Local: simulate the loop with small windows and a label correction so “then vs now” is exercised.
* Dev: runs these under realistic integration constraints (authn/authz, lifecycle privileges, policy rev reporting).
* Prod: adds strict change control and “no human memory” governance expectations.

### L3 (backfill/rebuild loop)

Environment ladder affects *how often and how strictly governed*, not semantics:

* Retention is a profile knob; backfill is explicit + scoped + auditable everywhere.
* Local: backfill is a drill; dev: backfill is a realism test; prod: backfill is a governed operation with approvals, receipts, and strict auditability.

### L4 (feature definition evolution)

This is “lane 2 + lane 3 interlock” in the ladder:

* Feature definition changes are policy/config artifacts (promoted with governance facts), and compatibility gating must prevent training/serving drift.

### L5 (incident/rollback loop)

Dev should *rehearse* rollback: registry rollback paths exist per lane, and degrade triggers should be meaningful enough to verify the mechanism. Prod is where SLOs/corridor checks matter.

### L6 (governance/explainability loop)

This is the ladder’s “proof you built one platform” test:

* In **every** environment, you must be able to answer: *what changed?* by pointing to a governance fact / registry event, and link it to decisions via correlation keys and recorded bundle refs.

---

## The practical takeaway

If you want a single rule that keeps all MF joins/paths/loops ladder-safe:

**Local must be “prod-shaped at the interface/semantics level,” dev must be “prod-failure-realistic,” and prod must be “strictly governed.”** The graph/rails/meanings stay identical; only the envelope changes.

---

Yes — here’s the **environment-profile knob set** (plus a few “deployment-shape” reminders) that will keep you pointed in the right direction **before** we crack MF open.

Everything below is consistent with your pinned ladder rule: **same graph + rails everywhere; only the operational envelope changes via profiles (wiring + policy strictness)**.

---

## 0) First anchor: what MF is in deployment shape

MF is a **scheduled/on-demand job unit** (not always-on), invoked by Run/Operate; it **reads** `ofs/` + `profiles/` and **writes** `mf/`, and it **publishes bundles to Registry** (Registry owns `registry/bundles/` + lifecycle).

That means your MF “environment profile” is basically: **how the job runs + how strict it is**.

---

## 1) The MF environment profile is two profiles

This is a pinned platform idea:

### A) Wiring profile (non-semantic)

Endpoints, resource limits, concurrency, timeouts, etc.

### B) Policy profile (outcome-affecting, versioned + auditable)

What MF is allowed to accept/publish, required gates, privacy rules, etc. Policy revisions must be recorded in provenance/logs/receipts.

---

## 2) MF wiring profile knobs (practical “how it runs”)

### Connectivity

* **Registry endpoint** + auth method (token injected at runtime; never embedded)
* **Object store endpoint + bucket** (single `fraud-platform`)
* **OTLP collector endpoint** (MF emits OTLP like everything else)
* Optional: **control bus endpoint** if you choose to emit `mf.*` control facts (not correctness-critical)

### Job runner / execution envelope

* **Schedule** (cron / manual trigger / pipeline trigger) 
* **Concurrency**: max parallel train runs; per-run worker threads
* **Resource limits**: CPU/mem, scratch disk, temp object prefixes
* **Timeouts + retry policy**: resolve-inputs timeout, publish timeout, backoff strategy 
* **Resume semantics**: whether a rerun can “resume” from existing `mf/…` artifacts (still idempotent)

### Substrate mapping (hard wiring expectations)

* **Reads**: `ofs/` manifests/materializations; `profiles/` policy+config artifacts
* **Writes**: `mf/` evidence; publishes to Registry (Registry writes `registry/bundles/`)

---

## 3) MF policy profile knobs (semantic strictness + governance)

These are outcome-affecting; they’re promoted like code (propose→approve→activate→rollback) and MF must report which revision it ran under.

### Input admissibility (J15 hardening knobs)

* **Manifest completeness requirements** (must include explicit basis/as-of/feature versions; otherwise refuse)
* **Digest enforcement** (must verify digests for manifest + referenced materializations) 
* **Max dataset window** (cap how wide a training window is allowed per run in prod; smaller in local/dev)

### Leakage / as-of discipline

* Required **label as-of basis** + **feature as-of basis** posture must be enforced (fail closed on ambiguity).

### Quality gate strictness (publish eligibility)

* **Required evaluation evidence** set (minimum metrics/report artifacts)
* **PASS/FAIL gate thresholds** (and whether “human approval required after PASS”)

### Compatibility requirements (anti drift)

* Required **compatibility descriptor** fields inside bundles (feature group versions, etc.) and “reject if missing.”

### Privacy / data handling

* “No raw sensitive rows in bundles/reports; by-ref only” style constraints; who can read `mf/` artifacts; whether artifacts are encrypted. (Outcome-affecting → policy.)

### Publish permissions + governance coupling

* Who is allowed to trigger MF and who is allowed to publish to Registry (separation of duties gets stricter up the ladder).

---

## 4) Operational-envelope knobs that matter specifically to MF paths/loops

### Retention + archive (affects what OFS can feed MF)

Retention is explicitly an **environment profile knob**; semantics don’t change.

* Local: short retention, maybe no real archive (but still by-ref semantics)
* Dev: medium retention + realistic upgrade/backfill rehearsal
* Prod: longer retention + archive continuity; archive must be verifiable for declared windows (so OFS trusts it)

### Backfill execution posture (feeds new manifests → MF retrain/eval)

Backfills are explicit, scoped, auditable; they regenerate only derived artifacts (including offline datasets/manifests).
The *knobs* are:

* how often backfills are allowed,
* approval strictness,
* resource ceilings,
* whether MF auto-triggers from a backfill declaration.

---

## 5) Observability knobs for MF (must exist everywhere, depth varies)

Your baseline says: correlation keys everywhere, golden signals + traces, and durable governance facts for outcome-affecting change.

MF-specific knobs:

* **Trace sampling rate** (high local, lower prod; semantics identical)
* **Log verbosity** (debug local, structured+bounded prod)
* **Metric cardinality limits** (prod needs guardrails)
* Required correlation IDs on every run: `train_run_id`, input manifest fingerprint/digests, `policy_rev`, and (if published) `bundle_id`.

---

## 6) Reasonable default posture across the ladder (MF-focused)

### Local (fast + inspectable)

* permissive policy strictness *but same mechanisms* (still refuses missing basis/as-of/versions)
* high observability, low volumes, frequent manual triggers
* simulate publish-retry at least once (to prove idempotency)

### Dev (prod-failure-realistic)

* real authz boundaries (who can trigger/publish/read artifacts)
* medium retention and rehearsed backfills/upgrades
* compatibility rejects must behave like prod

### Prod (strict governance)

* strict change control for policy rev activations + registry lifecycle + backfills
* longer retention + archive continuity
* strong observability tied into degrade/incident loops

---

## 7) “Before we enter MF” deployment facts you should keep in view

These are the things that will matter immediately when we illuminate MF’s inner network:

1. MF must be safe under **retries + partial failures** (publish-retry without retrain is first-class).
2. MF’s truth lives in `mf/…` artifacts; Registry owns `registry/bundles/…` and activation.
3. MF always runs under an explicit **policy_rev** (policy config is governed, versioned, and cited).
4. Retention/archive/backfill differences across envs must never change replay semantics; they only change what windows are feasible.
5. Local must remain “prod-shaped at interfaces” (Compose-style substrate is your friend), otherwise MF behaviors won’t survive dev/prod.

---

## USER: PAUSE FOR REFLECTION

Absolutely. Let’s do a **drift-check pause** and “re-freeze” the **outer network truth** for **MF (still opaque)**—so when we step inside, we’re designing *to satisfy these external obligations*, not accidentally re-inventing the platform.

# MF outer network freeze

## 1) MF’s declared role in the platform graph

**MF is an offline build authority** that turns **pinned datasets + pinned profiles** into **evidence-backed deployable bundles**, and **publishes** them into the Registry lifecycle.

MF is **not**:

* a streaming producer
* a label truth owner
* a feature-definition authority
* an activation authority
* a “direct EB/Archive reader” in v0 (that’s OFS)

That boundary is the core anti-drift constraint.

---

## 2) MF adjacency list (complete production-relevant edges)

### Mandatory edges (the two hard joins)

1. **J15: OFS → MF**
   **Payload:** `DatasetManifestRef[] (+ digests + basis/as-of + feature version pins)`
   **Meaning:** MF’s only legitimate data-plane training input is *manifested*, pinned datasets.

2. **J16: MF → Registry**
   **Payload:** `BundleCandidate (+ evidence refs + compatibility descriptor + PASS posture)`
   **Meaning:** MF can publish candidates; **Registry governs lifecycle + ACTIVE**.

### Control/ops edges (required in production readiness, even if minimal)

3. **Run/Operate → MF (trigger)**
   **Payload:** `TrainBuildRequest(intent + manifest refs + profile refs + request_id)`
   **Meaning:** MF doesn’t “decide to train”; it is invoked with pinned inputs.

4. **MF ↔ Object Store (substrate)**
   **Reads:** `ofs/…` + `profiles/…`
   **Writes:** `mf/…` (evidence + receipts + run records)
   **Non-negotiable boundary:** MF **does not write** into `registry/bundles/…` (Registry owns that namespace).

5. **MF ↔ Profiles/Configs (`profiles/…`)**
   Two logical profiles:

* **Wiring** (non-semantic): endpoints, timeouts, concurrency…
* **Policy** (semantic): admissibility rules, gate strictness, privacy constraints…
  **Rule:** policy revisions are versioned + cited in MF outputs.

6. **MF → Observability (OTLP)**
   Metrics/traces/logs with correlation keys (`train_run_id`, request_id, input fingerprint, policy_rev, bundle_id if published).

7. **MF → fp.bus.control.v1 (optional)**
   Low-volume “started/completed/published” facts **by-ref** only (never correctness-critical).

8. **Registry → fp.bus.control.v1 (lifecycle events)**
   Publish/promote/activate/rollback signals for governance visibility.
   **Rule:** DB/lifecycle truth first; event emission is distribution.

That’s the *full* outer surface area MF needs to be “production-ready.”

---

## 3) Path commitments (what MF participates in, without owning them)

### P1: Standard learning→deploy

`EB/Archive + Label Store → OFS → MF → Registry → DF`

* MF’s job is the **bridge** from “rebuildable datasets” to “deployable bundles.”

### P4: Publish retry (no retrain)

If MF has already produced durable evidence, it must be possible to retry **publish only** safely.

### P3: Compatibility-gated rollout

Bundle metadata must be sufficient for Registry/DF to refuse incompatible activation/resolution.

### P2: “Then vs now” evaluation

MF must support dataset manifests that represent “as-of decision-time” vs “as-of later truth.”

### P5: Cross-environment promotion

Promotion is **artifact selection + governed activation**, not “retrain in prod and hope.”

### P6: Golden-flow integration

A single end-to-end run must exercise `OFS→MF→Registry` at least once (even at tiny scale).

---

## 4) Loop commitments (how MF fits into time)

### L1: Continuous improvement loop

Traffic → decisions → labels → OFS → MF → registry lifecycle → DF behavior changes.

### L2: Late-truth correction loop

Label corrections are append-only; OFS rebuilds; MF produces new evidence/bundles; Registry decides if anything becomes ACTIVE.

### L3: Backfill/rebuild loop

Backfills are **declared + scoped + auditable**, generate **new derived versions** (including new manifests), never mutate primary truths.

### L4: Feature evolution loop

Feature version changes must force: rebuild/parity → MF bundle requires versions → compatibility enforcement.

### L5: Incident/rollback loop

Degrade posture (fast safety) + registry rollback (identity change) are distinct levers; MF is the “fix-forward” engine after the incident.

### L6: Governance/explainability loop

Decisions cite bundle refs; bundles cite dataset manifests; manifests cite replay basis/as-of; everything is joinable by correlation keys.

---

## 5) Non-negotiable outer invariants (the “don’t drift” laws)

These are the rules the inner MF design must satisfy:

1. **Manifests-only intake**
   MF must not train on “latest” or raw data without a DatasetManifest.

2. **By-ref + digests everywhere**
   MF consumes and produces artifacts that are addressable and verifiable; no hidden inputs.

3. **No PASS → no publish eligibility**
   MF may store FAIL evidence, but it doesn’t produce deployable candidates without explicit PASS posture.

4. **Append-only posture**
   MF outputs (run records, receipts, evidence, bundle candidates) are immutable; corrections are new artifacts with “supersedes.”

5. **Registry-only activation**
   MF publishes; Registry governs ACTIVE.

6. **Environment ladder = same semantics**
   Local/dev/prod differ in envelope (scale, retention, security strictness), not in meaning of joins.

---

## 6) Drift traps to watch for as we step inside MF

These are the most common “oops we drifted” failure modes:

* **MF starts selecting data** (“train on latest”) → violates manifests-only and breaks reproducibility.
* **MF becomes a shadow registry** (writes into registry namespace or decides ACTIVE) → breaks authority boundaries.
* **Publish and activate get conflated** → turns MF into a production switch.
* **Profiles become implicit** (“whatever config is current”) → destroys reproducibility; runs can’t be re-explained.
* **Compatibility metadata is treated as optional** → training/serving drift sneaks in.
* **Bus control events are treated as truth** → correctness depends on a signal stream instead of durable artifacts.

---

## 7) Tiny set of outer decisions we should keep consciously “locked” vs “open”

Locked (we build around):

* J15/J16 are the hard joins; MF is job-shaped; Registry owns lifecycle/ACTIVE; manifests are mandatory.

Still safely open (won’t cause drift yet):

* Whether MF emits optional control events (yes/no) and the minimal event set
* Whether Registry copies artifacts or links to MF staging (so long as Registry guarantees durability and remains authoritative)
* Where exactly “feature definition pack authority” lives (so long as it’s singular and versioned)

---

If this outer network freeze looks correct, we can now step inside MF with a clear mandate:

**Design MF’s internal nodes so that every external edge above is satisfied under retries, partial failures, and environment profile variation—without MF stealing authority from OFS/Registry/Label Store/DF.**

---

Yes — we can go **one level deeper** without drowning in detail by carving MF into a small set of **internal subnetworks** (each still opaque), chosen purely by **outer obligations** (J15/J16, idempotency, evidence, publish-retry, ladder profiles).

Below is the **first-layer internal network** I’m pinning for MF v0.

---

## MF internal subnetworks (all opaque boxes)

### MF-A) Run Intake and Idempotency Gate

**Why it exists:** MF is a job that will be retried/duplicated. This subnetwork ensures “same request / same inputs → same run identity,” and blocks duplicate concurrent work.

* **Inputs:** `TrainBuildRequest` (intent, DatasetManifestRefs, profile refs, request_id)
* **Outputs:** `train_run_id` claimed + “RUNNING/DONE” resolution + resume decision
* **Owns:** idempotency keying (TrainRunKey), concurrency locks, resume semantics

---

### MF-B) Context Resolver

**Why it exists:** MF behavior must be explainable as “code build X + policy rev Y + wiring profile Z”.

* **Inputs:** wiring profile ref, policy profile ref, training config ref
* **Outputs:** `MFContext` (resolved endpoints, resource envelope, admissibility rules, gate strictness, compatibility requirements)
* **Owns:** “fail closed” if refs/digests can’t be resolved

---

### MF-C) Input Resolver and Admissibility Gate (J15 enforcement)

**Why it exists:** MF must never “choose data” and must refuse ambiguous inputs.

* **Inputs:** DatasetManifestRefs (from OFS), MFContext policy rules
* **Outputs:** `InputFingerprint` + “ADMISSIBLE / REJECTED (reason codes)” + resolved materialization refs
* **Owns:** manifest integrity checks, digest verification, basis/as-of presence, feature version pin presence, re-resolvability

---

### MF-D) Build Orchestrator

**Why it exists:** MF is multi-stage and must survive partial failures and resume safely.

* **Inputs:** `train_run_id`, MFContext, resolved admissible inputs
* **Outputs:** an ordered stage plan + stage status transitions + checkpoint boundaries
* **Owns:** stage lifecycle, retry orchestration, workspace management, “publish-only retry” routing

---

### MF-E) Train and Evaluate Engine

**Why it exists:** this is the heavy compute, but we keep it opaque.

* **Inputs:** resolved materializations + training config + feature version pins
* **Outputs:** model/policy artifacts, evaluation reports, metrics summaries (all by-ref)
* **Owns:** none of the platform authority; it only produces evidence blobs

---

### MF-F) Evidence, Gating, and Bundle Assembly

**Why it exists:** MF must produce a *deployable candidate* only when evidence satisfies policy.

* **Inputs:** artifacts + eval evidence + MFContext gate policy
* **Outputs:** `GateReceipt(PASS/FAIL)` + `BundleCandidate` (with compatibility descriptor + provenance pointers)
* **Owns:** PASS/FAIL decision (for publish eligibility), bundle lineage assembly (manifests→bundle), supersedes linkage (append-only posture)

---

### MF-G) Registry Publisher and Lifecycle Adapter (J16)

**Why it exists:** publish must be idempotent and conflict-detecting; activation remains Registry-only.

* **Inputs:** `BundleCandidate`, GateReceipt, MFContext registry wiring/auth
* **Outputs:** “published / already published / rejected (conflict)” + registry identifiers/state
* **Owns:** publish retries, conflict detection, safe “publish-only” retry path

---

### MF-H) Evidence Ledger and Artifact I/O (substrate manager)

**Why it exists:** MF’s durable truth lives in `mf/...`, and every other subnetwork needs a safe place to record.

* **Inputs:** stage events from A–G, refs/digests, failure reasons
* **Outputs:** `mf/...` run records, stage receipts, completion markers, artifact locators
* **Owns:** append-only run record writing, completion markers, digest recording, namespace hygiene (`mf/...` only)

---

### MF-I) Observability and Control-Facts Emitter (cross-cutting)

**Why it exists:** production job needs traceability, and optional control facts help operators.

* **Inputs:** run/stage transitions + correlation keys (`train_run_id`, request_id, input_fingerprint, policy_rev, bundle_id)
* **Outputs:** OTLP metrics/logs/traces; optional `mf.*` control facts (by-ref pointers only)
* **Owns:** none of the correctness; signals only

---

## Internal edges between these subnetworks (still opaque inside)

1. `MF-A → MF-B` (accept request, resolve context)
2. `MF-B → MF-C` (policy rules + refs drive admissibility checks)
3. `MF-C → MF-D` (only admissible inputs become a runnable plan)
4. `MF-D → MF-E` (execute train/eval stages)
5. `MF-E → MF-F` (evidence goes to gates + bundle assembly)
6. `MF-F(PASS) → MF-G` (publish eligible candidates)
7. `MF-F(FAIL) → stop` (no publish; evidence remains)
8. `MF-A…MF-G → MF-H` (all stages append run ledger + artifact locators)
9. `MF-A…MF-G → MF-I` (telemetry + optional control facts)

---

## Simple “one-level-deeper” picture

```
TrainBuildRequest
      |
      v
 [MF-A Run Intake/Idempotency]
      |
      v
 [MF-B Context Resolver]
      |
      v
 [MF-C Input Resolver + Admissibility] ---reject--> (fail record)
      |
      v
 [MF-D Build Orchestrator]
      |
      v
 [MF-E Train+Eval Engine]
      |
      v
 [MF-F Gate + Bundle Assembly] --FAIL--> (no publish)
      |
     PASS
      v
 [MF-G Registry Publisher]

   (cross-cutting substrate)
 A..G ---> [MF-H Evidence Ledger + Artifact I/O]  (mf/...)
 A..G ---> [MF-I Observability + Control Facts]
```

---

Yep — we’ll stay **one level deep**: MF’s internal subnetworks are still **opaque boxes**, and we’ll now enumerate the **internal joins (edges), paths, and loops** that exist in a production-ready MF.

I’ll use the internal subnetworks we just pinned:

* **MF-A** Run Intake + Idempotency
* **MF-B** Context Resolver (profiles/config)
* **MF-C** Input Resolver + Admissibility (J15 enforcement)
* **MF-D** Build Orchestrator (stage control + resume)
* **MF-E** Train + Eval Engine (compute)
* **MF-F** Evidence + Gates + Bundle Assembly
* **MF-G** Registry Publisher (J16)
* **MF-H** Evidence Ledger + Artifact I/O (`mf/...`)
* **MF-I** Observability + optional Control-Facts

---

# 1) Internal joins (production edges inside the vertex)

## Core “dataflow spine” joins

These form the main DAG that produces a publishable bundle:

**IJ1: A → B (Request admitted → context resolution)**

* A passes a *resolved run identity intent* to B.

**IJ2: B → C (Context → admissibility rules)**

* B passes resolved policy/wiring + required revisions to C.

**IJ3: C → D (Admissible inputs → runnable plan)**

* C outputs “ADMISSIBLE + resolved refs/fingerprint” or “REJECT”.

**IJ4: D → E (Execute train/eval stage)**

* Orchestrator invokes compute engine with pinned inputs.

**IJ5: E → F (Evidence handoff)**

* E produces artifacts + eval evidence refs; F consumes them.

**IJ6: F → G (PASS-eligible candidate → publish)**

* Only if PASS (or “publish allowed under policy”) does it proceed.

## Cross-cutting substrate joins (these exist in prod no matter what)

These ensure durability, resumability, auditability.

**IJ7: {A..G} → H (Durable ledger + artifact I/O)**

* Every stage appends run/stage records, writes receipts, records digests, writes completion markers.

**IJ8: {A..G} → I (Telemetry + optional control facts)**

* Stage start/stop/fail, correlation keys, and optional `mf.*` control events.

## Internal joins that touch external surfaces (still “inside MF”)

These are “MF’s internal adapters to the world”:

**IJ9: B ↔ Profiles store (`profiles/...`)**

* Resolve wiring + policy + training recipe revisions (fail-closed if missing/mismatch).

**IJ10: C ↔ OFS artifacts (`ofs/...`)**

* Read DatasetManifests + referenced materializations (verify digests, basis/as-of pins).

**IJ11: G ↔ Registry API (publish, idempotent)**

* Publish bundle candidate; handle “already published”, “conflict”, “rejected”.

**IJ12: I → OTLP collector (metrics/logs/traces)**

* Not correctness-critical, but must exist in production.

**IJ13 (optional): I → control bus (`fp.bus.control.v1`)**

* Low-volume `mf.train_run.*` facts **by-ref pointers only**.

---

# 2) Internal paths (end-to-end routes through the internal graph)

These are the production “routes” that matter, keeping all boxes opaque.

## IP1 — Happy path: new run → PASS → publish

`A → B → C → D → E → F(PASS) → G`
with `{A..G} → H` and `{A..G} → I` happening throughout.

## IP2 — Input rejection path (manifest/config invalid)

`A → B → C(REJECT)`

* Stops before D/E/F/G, but **still writes failure evidence** via H and emits telemetry via I.

## IP3 — Gate fail path (trained/evaluated but not eligible)

`A → B → C → D → E → F(FAIL)`

* No publish attempt; H records FAIL receipt + evidence refs.

## IP4 — Publish-retry path (no retrain)

`A → (resume existing run) → D (skip E/F if complete) → G (retry publish)`

* This is the canonical “registry down / timeout” recovery route.

## IP5 — Duplicate trigger path (idempotent no-duplicate-work)

`A (duplicate request) → A (dedupe decision)`

* Either returns “RUNNING(train_run_id)” or “DONE(bundle_id)”.
* In production, this is one of the most common paths.

## IP6 — “Already published” path (idempotent publish)

`A → … → F(PASS) → G(already_published)`

* Treat as success; record linkage in H.

## IP7 — Conflict path (same bundle identity, different bytes)

`A → … → G(conflict_reject)`

* Hard stop + recorded evidence; indicates drift/bug upstream.

## IP8 — Controlled cancel path (optional, ops-friendly)

`Run/Operate cancel → A/D → D(stop)`

* Produces a “CANCELED” terminal record in H (not correctness-critical, but production realistic).

---

# 3) Internal loops (cycles) that must exist in production

Even though the spine is mostly DAG-shaped, **production MF is loop-shaped** because of retries, resume, and idempotency.

## IL1 — Request idempotency loop (dedupe)

`A ↔ H`

* A checks the ledger for an existing `train_run_id` / status and either:

  * returns immediately, or
  * claims/creates and proceeds.
    This loop is what prevents duplicate work.

## IL2 — Stage resume loop (crash/restart survivability)

`D ↔ H`

* D reads stage checkpoints and decides which stages are complete vs must re-run.
  This is the core “job is restart-safe” loop.

## IL3 — Stage retry loop (transient compute failures)

`D → E (fails) → D (retry/backoff) → E`

* Policy controls retry budget; H records attempts and failure reasons.

## IL4 — Evidence/gate loop (re-evaluate without retrain)

`D ↔ F ↔ H`

* If training artifacts exist but gating policy/eval step needs rerun (or was interrupted), D can re-run eval/gates without re-training.

## IL5 — Publish retry loop (registry transient failures)

`G (attempt) → registry fails → G (retry/backoff) …`
with each attempt recorded in `H` and optionally surfaced via `I`.

## IL6 — Supersedes / “new run replaces old” loop (cross-run but still MF-internal truth)

`(old run FAIL) → (new request with new inputs) → A → …`

* H records **supersedes relationships** so audit can tell “this newer run replaced that earlier failed candidate.”

## IL7 — Signal emission best-effort loop (non-correctness)

`I (emit) → (drop/fail) → I (retry or give up)`

* Important: this loop **must not** affect correctness; it’s pure observability.

---

# 4) The internal network as an adjacency map (opaque-node level)

```
IJ1  A -> B -> C -> D -> E -> F -> G
               \         \     \
                \         \     +--> (PASS/FAIL decision boundary)
                 \         \
                  +--> REJECT  +--> (resume/skip stages)

IJ7  {A,B,C,D,E,F,G} -> H   (durable ledger + artifact I/O)
IJ8  {A,B,C,D,E,F,G} -> I   (telemetry + optional control facts)

External adapters (still “inside MF”):
B <-> profiles/...
C <-> ofs/...
G <-> registry API
I -> OTLP (+ optional control bus)
H <-> mf/... object store
```

---

Great — we’ll **illuminate IJ1–IJ6** as *production joins between opaque internal subnetworks*, and I’ll **declare what is boundary-aligned vs boundary-violating** as we go.

I’m going to treat each join as a **handshake** that has:

* a **payload** (what’s passed),
* **pinned invariants** (must hold or we fail closed),
* a **receipt** (what MF-H ledger must be able to persist for audit/resume),
* and a clear **failure disposition**.

We are *not* opening any boxes yet.

---

# The MF spine we’re illuminating

```
IJ1      IJ2      IJ3      IJ4      IJ5      IJ6
A  --->  B  --->  C  --->  D  --->  E  --->  F  --->  G
```

Where:

* A = Run Intake + Idempotency
* B = Context Resolver (profiles/config)
* C = Input Resolver + Admissibility (J15 enforcement)
* D = Build Orchestrator
* E = Train/Eval Engine
* F = Evidence + Gates + Bundle Assembly
* G = Registry Publisher (J16)

---

# IJ1: A → B  (Request admitted → context resolution)

## Why IJ1 exists

**All downstream behavior must be explainable as**:
`(pinned inputs) + (pinned profile revisions) + (pinned MF build id)`.

So before we can even decide what “the run” is, we must resolve **profiles/config artifacts** into a stable **MFContext**.

## Payload (A → B)

A sends a **ContextResolveIntent**:

* `request_id` (or a canonicalized equivalent if absent)
* `intent` (train | eval-only | backfill-retrain | regression-check)
* `dataset_manifest_refs[]` (by-ref pointers only; no data)
* `profile_refs`:

  * `wiring_profile_ref`
  * `policy_profile_ref`
  * `training_recipe_ref` (or equivalent)
* `caller_principal` (for authorization attribution)
* `environment_id` (local/dev/prod)

## Return (B → A) — still part of IJ1 handshake

B returns an **MFContext**:

* resolved **digests/revisions** for every profile artifact
* resolved **policy knobs** (admissibility strictness, gate rules, compatibility requirements)
* resolved **wiring knobs** (endpoints, timeouts, concurrency ceilings)
* `mf_build_id` (container/image digest or build hash)
* an **authz verdict** (allowed/denied + reason)

## Pinned invariants (authority)

✅ **Boundary-aligned**

* MFContext must be **fully resolved** (no “use whatever is active later”).
* MFContext must include **digests** (not just names/versions).
* Missing/invalid profile refs → **fail closed** at IJ1.

❌ **Boundary-violating (I forbid these)**

* “Implicit profile selection” (e.g., B reads “current active profile” at runtime without pinning the revision).
* “Environment forks semantics” (local/dev/prod changing meaning, not just strictness).
* Any attempt to “peek data” here (B must not read datasets/EB).

## Receipt to ledger (what must be persistable)

`context_receipt`:

* request_id, caller_principal
* resolved profile refs + digests + policy_rev
* mf_build_id
* authz verdict

## Failure disposition

* **DENY**: stop immediately; write failure receipt.
* **RESOLVE_FAIL** (missing artifact, digest mismatch): stop; retry only after inputs fixed.

---

# IJ2: B → C  (Context → admissibility rules)

## Why IJ2 exists

C enforces the platform’s hardest boundary: **MF only trains on admissible, pinned, reproducible inputs** (J15 discipline). C cannot do that without the **policy knobs** from B.

## Payload (B → C)

B passes a **ResolvedRunContext**:

* `MFContext` (policy+wiring resolved, digests included)
* the original request’s **input refs** (dataset_manifest_refs, intent)
* `mf_build_id` (so C can stamp receipts consistently)

## Pinned invariants

✅ **Boundary-aligned**

* C must receive **policy knobs** as data (not re-derive).
* C must treat MFContext as **authoritative** for strictness (local may be “lighter,” prod stricter — same semantics).

❌ **Boundary-violating**

* C fetching “latest policy” itself.
* C downgrading strictness because “it’s inconvenient.”

## Receipt to ledger

`context_to_admissibility_receipt`:

* MFContext digest summary
* which policy knobs were applied (admissibility mode)
* environment_id

## Failure disposition

* If MFContext is missing required elements → **hard fail** (that’s an internal bug or profile corruption).

---

# IJ3: C → D  (Admissible inputs → runnable plan)

## Why IJ3 exists

D must build a **restart-safe plan** only when inputs are admissible. This join is the “go/no-go gate” between “input world” and “execution world.”

## Payload (C → D)

C outputs **either**:

### Case 1: REJECT

* `status=REJECT`
* `reject_reason_codes[]`
* `which_ref_failed` + expected/observed digests (where applicable)

### Case 2: ADMISSIBLE

* `status=ADMISSIBLE`
* `input_fingerprint` (deterministic hash over: manifest digests + policy/profile digests + training_recipe digest)
* `resolved_manifest_set[]`:

  * manifest refs + digests
  * materialization refs + digests
  * explicit replay basis + as-of boundaries (as carried by manifest)
  * feature-version pins
* `data_usage_constraints` (privacy rules, allowed exports, etc.)

## Pinned invariants

✅ **Boundary-aligned**

* “Admissible” must imply: **re-resolvable later** + **digest-verified** + **basis/as-of explicit**.
* `input_fingerprint` is mandatory (it underpins idempotency + resume).

❌ **Boundary-violating**

* D accepting inputs when C says REJECT.
* C emitting ADMISSIBLE without digests/basis/as-of pins.

## Receipt to ledger

`admissibility_receipt`:

* status (ADMISSIBLE/REJECT)
* input_fingerprint (if admissible)
* reject reasons (if rejected)
* the exact manifest/materialization digests used

## Failure disposition

* REJECT is terminal for this run attempt (no training).
* ADMISSIBLE proceeds.

---

# IJ4: D → E  (Execute train/eval stage)

## Why IJ4 exists

Production MF must survive:

* long runs,
* restarts,
* transient compute failures.

So D must invoke E **as a stage machine**, not as “one big opaque function.”

## Payload (D → E)

D sends an **ExecutionStageCall**:

* `train_run_id` (derived from request_id + input_fingerprint + policy/profile digests; see note below)
* `input_fingerprint`
* `stage_id` (TRAIN or EVAL or BOTH, depending on design)
* `attempt_no`
* `resolved_inputs` (refs + digests only)
* `training_recipe_ref+digest`
* `runtime_envelope` (resource ceilings from wiring profile)
* `stage_seed` (derived deterministically from train_run_id + stage_id)

### Note on run identity (authority)

I’m pinning this: **train_run_id must be deterministic** and must not depend on time-of-day. It must be reproducible from pinned inputs + pinned profiles + mf_build_id. Time can exist as metadata, not identity.

## Pinned invariants

✅ **Boundary-aligned**

* D never passes raw rows as “anonymous arrays”; everything is **by-ref** to materializations (even if those materializations are local temp files, they must be referenced via ledger and digests).
* Stage seeds are deterministic.

❌ **Boundary-violating**

* E choosing new inputs (“let me load newer data”).
* E emitting outputs without stage attempt attribution (breaks resume).

## Receipt to ledger

`stage_start_receipt` and `stage_end_receipt`:

* stage_id, attempt_no
* input_fingerprint
* stage_seed
* refs produced (if any)
* failure reason codes (if failed)

## Failure disposition

* **Transient failure**: D retries according to policy (attempt budget/backoff).
* **Deterministic failure** (bad inputs slipping through): treat as bug; stop.

---

# IJ5: E → F  (Evidence handoff)

## Why IJ5 exists

F is the **truth assembler**: it turns raw artifacts into:

* a gate decision (PASS/FAIL),
* a bundle candidate (if eligible),
* a provenance chain that’s joinable later.

E must therefore provide **evidence in a consumption-ready shape**.

## Payload (E → F)

E outputs a **TrainingEvidencePack** (by-ref):

* `artifact_refs[]` + digests (model/policy artifacts)
* `eval_report_ref` + digest (metrics, slices, comparisons)
* `training_metadata_ref` + digest (what ran, with what pinned inputs)
* `evidence_fingerprint` (hash over all the above)

## Pinned invariants

✅ **Boundary-aligned**

* Evidence is **immutable** once emitted (new attempt produces new evidence pack).
* Evidence must carry the **input_fingerprint** it was derived from.

❌ **Boundary-violating**

* F “recomputing” evidence by re-reading datasets independently (that would bypass the stage machine and break audit).
* E producing “metrics only” without artifact refs/digests (cannot support later re-verification).

## Receipt to ledger

`evidence_receipt`:

* evidence_fingerprint
* artifact refs/digests
* eval report ref/digest

## Failure disposition

* If evidence pack is incomplete → treat as **internal failure**; either retry E stage or fail run.

---

# IJ6: F → G  (PASS-eligible candidate → publish)

## Why IJ6 exists

This join enforces the strongest external boundary: **MF may publish candidates; Registry alone governs activation**. IJ6 must also support **publish-retry without retrain**.

## Payload (F → G)

F emits either:

### Case 1: FAIL (no publish)

* `gate_receipt = FAIL`
* `reasons[]` + pointers to eval evidence

### Case 2: PASS (publish eligible)

* `gate_receipt = PASS` (with criteria + evidence refs)
* `bundle_candidate`:

  * `bundle_fingerprint` (hash of artifact refs + digests + compatibility descriptor + provenance refs)
  * `compatibility_descriptor` (required feature versions, required capabilities, etc.)
  * `provenance_refs`:

    * dataset manifests used
    * profile/policy revisions used
    * mf_build_id
    * evidence refs (eval report, gate receipt)

## Pinned invariants

✅ **Boundary-aligned**

* G must treat `bundle_fingerprint` as the idempotency anchor for publishing.
* Publishing is allowed **only** if policy says PASS is sufficient (default) — and *never* implies activation.

❌ **Boundary-violating**

* Publishing a FAIL candidate “for later”.
* Publishing without compatibility metadata (breaks compatibility-gated resolution).
* Any “activate now” behavior inside MF.

## Receipt to ledger

`publish_intent_receipt`:

* bundle_fingerprint
* PASS receipt ref/digest
* target scope (environment / registry namespace)
* publish attempt counter

## Failure disposition

* **Registry transient failure**: G retries publish (publish-retry loop) without re-running E/F.
* **Registry conflict** (same bundle id different bytes): hard fail; this indicates drift/bug.
* **Registry reject** (missing fields): hard fail; fix bundle assembly policy.

---

# The authority calls I’m locking right now (so we don’t drift)

1. **IJ1 must fully pin MFContext** (no implicit “active profile”).
2. **IJ3 is the only go/no-go into execution** (REJECT stops; ADMISSIBLE must include digests + basis/as-of + feature pins).
3. **IJ4 is stage-shaped, restart-safe, deterministic seeds** (D drives; E never chooses inputs).
4. **IJ6 publishes by bundle_fingerprint and never activates** (Registry owns ACTIVE).
5. Any join failing integrity/pinning → **fail closed**, with a durable receipt in MF-H.

---

Absolutely. **IJ7 and IJ8 are the two “cross-cutting rails” inside MF** that make the whole vertex production-real: durability/resume/audit (IJ7) and visibility/operability (IJ8). I’m going to treat them as **authoritative internal joins** and be explicit about what is *allowed*, *forbidden*, and *fail-closed vs best-effort*.

---

# IJ7 — `{A..G} → H`

## Durable ledger + artifact I/O (MF’s internal “truth plane”)

### What IJ7 *is*

IJ7 is the join where **every internal subnetwork (A–G)** commits its externally meaningful reality to **MF-H**, which is the **durable, append-only run ledger + artifact locator writer** anchored in `mf/...`.

If MF-H doesn’t exist (or isn’t strict), you lose:

* idempotency (duplicates create drift),
* resumability (crashes force “start over” or “unknown state”),
* publish safety (you can’t prove what you’re publishing),
* auditability (no evidence chain).

### IJ7 handshake (how the join behaves)

Each producer node (A–G) interacts with H via **two primitives**:

1. **AppendReceipt**
   “Record that this thing happened / was decided / started / ended.”

2. **WriteArtifact + RecordLocator**
   “Write a blob somewhere durable, compute/verify digest, then append a locator receipt that points to it.”

**Important:** Artifacts are not “the truth” until H has recorded the locator + digest.

### What crosses IJ7 (payload types)

IJ7 carries **receipts** and **artifact locators**, never raw bulk data.

#### Receipt classes (minimum set)

* **Run lifecycle receipts**

  * `run_claimed` (A)
  * `run_started` (D)
  * `run_terminal` (SUCCESS | FAIL | REJECT | CANCELED) (A/D/F/G)

* **Context receipts**

  * resolved wiring/profile digests, policy_rev, mf_build_id (B)

* **Admissibility receipts**

  * ADMISSIBLE/REJECT + reason codes
  * input_fingerprint + manifest/materialization digests (C)

* **Stage receipts**

  * `stage_started(stage_id, attempt_no)`
  * `stage_completed(stage_id, attempt_no)`
  * `stage_failed(stage_id, attempt_no, reason)` (D/E)

* **Evidence receipts**

  * evidence_fingerprint + refs/digests to eval report + artifacts (E→F)

* **Gate receipts**

  * PASS/FAIL + criteria refs + evidence refs (F)

* **Publish receipts**

  * publish_attempt + publish_result (published | already_published | rejected | conflict) (G)

#### Artifact locator classes (minimum set)

* manifest snapshots / resolved-ref bundles for the run (inputs pinned)
* training outputs (model/policy artifacts)
* eval reports
* gate receipts / gate evidence packs
* bundle candidate manifest (pre-registry)
* publish response snapshot (registry identifiers)

### IJ7 invariants (authoritative “musts”)

✅ **Aligned / required**

1. **Append-only posture**

   * H never mutates records in place.
   * Corrections are new receipts with `supersedes=<prior_receipt_id>`.

2. **Digest-anchored by-ref**

   * Every artifact locator has a digest.
   * Every receipt that references an artifact references the **locator id** (or locator digest), not “a path string”.

3. **Deterministic identity and dedupe**

   * Receipts have stable dedupe keys where it matters (e.g., `run_claimed` by `train_run_id`, `stage_started` by `(train_run_id, stage_id, attempt_no)`).
   * Duplicate appends must be safe (idempotent).

4. **Completion markers are explicit**

   * A stage is not “done” until there is a `stage_completed` receipt.
   * A run is not “done” until there is a terminal receipt + a run completion marker (conceptually; exact artifact can vary).

5. **Namespace authority**

   * H writes only under `mf/...`.
   * Anything under `registry/bundles/...` is Registry’s job (MF must not “become the registry” through H).

### IJ7 failure disposition (what happens when H can’t do its job)

This is where I’m declaring a hard line:

**MF-H is correctness-critical. If IJ7 can’t commit, MF must fail closed (or pause in a safe “cannot proceed” state).**

Concretely:

* If H cannot append the **context/admissibility receipts**, MF must stop (otherwise you can’t prove what you’re doing).
* If H cannot record **stage start/completion**, MF must stop (otherwise resume/idempotency breaks).
* If H cannot record **evidence/gate/publish receipts**, MF must not publish (ever).

**Allowed behavior:**
MF can treat some internal work as “ephemeral” only until it can durably record it; but once it crosses a correctness boundary (admissibility accepted, training artifacts produced, gate decided, publish attempted), the corresponding receipts must exist or MF stops.

### Boundary-violating patterns (forbidden)

❌ **Not allowed**

* “Train anyway, we’ll write receipts later.”
* “Publish to registry even if we can’t durably pin evidence.”
* “Overwrite `mf/...` artifacts in place without supersedes.”
* “Record only paths without digests.”
* “Let E/F/G write directly to object store without H recording locators.”

---

# IJ8 — `{A..G} → I`

## Observability + optional control facts (MF’s internal “signal plane”)

### What IJ8 *is*

IJ8 is the join where internal subnetworks emit **signals** to MF-I:

* OTLP metrics/logs/traces (always)
* optional low-volume control facts (`mf.*`) (nice to have)

**Key point:** IJ8 is *not* truth. It must never be required for correctness.

### IJ8 handshake (how it behaves)

Each node (A–G) emits:

* `SpanStart/SpanEnd` + attributes
* `MetricPoint`
* structured `LogEvent`
* optional `ControlFactIntent` (which MF-I may publish externally)

### What crosses IJ8 (payload types)

#### A) Correlation keys (must be present everywhere)

Minimum keys:

* `train_run_id`
* `request_id`
* `input_fingerprint`
* `policy_rev` and `mf_build_id`
* `bundle_fingerprint` / `bundle_id` (if reached)

This is the glue that makes MF operable in prod.

#### B) Stage signals

* started/completed/failed for: resolve, admissibility, train, eval, gate, publish
* include attempt_no and reason codes (no stack-dump required for the “outer” signal)

#### C) Safety/guardrail signals

* “manifest rejected due to missing basis/as-of”
* “digest mismatch”
* “registry conflict”
* “publish retry in progress”
  These are the signals that catch drift early.

### IJ8 invariants (authoritative “musts”)

✅ **Aligned / required**

1. **Best-effort only**

   * Telemetry failure must not change MF outcomes.
   * If I is down, MF still runs and records truth in H.

2. **No secrets, no raw data**

   * Never emit secrets.
   * Never emit raw training rows.
   * Prefer hashes/ids/digests and reason codes.

3. **Canonical correlation**

   * Every emitted event/span/log must carry the correlation keys above.
   * Without this, incident response and explainability loops break.

4. **Optional control facts are by-ref only**

   * If MF-I emits to a control bus, payloads must be pointers to `mf/...` receipts/artifacts, not embedded evidence.

### IJ8 failure disposition

* If OTLP export fails: drop/buffer/retry within resource limits, but **do not block MF**.
* If control bus emit fails: record it as a signal, but **never treat it as a correctness failure**.

### Boundary-violating patterns (forbidden)

❌ **Not allowed**

* “We use control bus emission as the authoritative record of a run.”
* “MF won’t publish unless telemetry succeeds.”
* Emitting high-cardinality payloads that explode in prod (e.g., full manifest contents; raw metrics tables).

---

# The big drift-prevention statement (locking this now)

**IJ7 is the MF internal truth plane (fail-closed).
IJ8 is the MF internal signal plane (best-effort).**

If we keep that separation crisp, MF remains production-safe under retries, partial failures, and the environment ladder.

---

Alright. IJ9–IJ13 are MF’s **world-facing adapters** — still “inside MF,” but they touch external substrates/services. I’ll illuminate each as a production join with: **purpose, payload, invariants, receipts, failure posture, and what’s forbidden** (design authority calls).

---

# IJ9 — **B ↔ Profiles store (`profiles/...`)**

## Purpose

B can’t produce a legitimate **MFContext** unless it can resolve:

* **wiring profile** (non-semantic)
* **policy profile** (semantic strictness + gate policy)
* **training recipe** (outcome-affecting training config)

This join is the platform’s “**no implicit config**” rail made concrete for MF.

## Handshake shape (conceptual)

**B issues ResolveProfileSet(profile_refs)** → returns **ResolvedProfileSet**

* `wiring_profile_ref` + `digest`
* `policy_profile_ref` + `digest` + `policy_rev`
* `training_recipe_ref` + `digest`
* optional: `feature_pack_ref` + `digest` (if that’s managed as a profile artifact)
* `resolved_at_ts` (metadata only, not identity)

## Pinned invariants (authoritative)

✅ **Required**

1. **Fail-closed on missing/mismatch**

   * missing ref, digest mismatch, unreadable artifact → IJ9 fails and MF stops (no “best effort”).
2. **Explicit revision pinning**

   * B must never resolve “active latest” implicitly unless that active rev is first resolved by Run/Operate *and passed in*; within MF, refs must already be pinned.
3. **Separation of wiring vs policy**

   * wiring differences across env are allowed; policy differences are allowed only as **versioned policy revs** and must be recorded.

❌ **Forbidden**

* B silently falling back to defaults if a profile is missing.
* B pulling “the current prod profile” based on environment name without a revision pin.
* Any secrets stored inside profile artifacts (secrets are runtime-injected; at most you record a key-id).

## Receipts to MF-H (truth plane)

* `profile_resolution_receipt`:

  * each ref + digest
  * `policy_rev`
  * `mf_build_id`
  * `resolver_verdict` (OK/FAIL + reason codes)

## Failure posture

* **Correctness-critical** → if IJ9 fails, the run cannot proceed past IJ1/IJ2.

---

# IJ10 — **C ↔ OFS artifacts (`ofs/...`)**

## Purpose

This is the MF enforcement point for J15: **manifests-only intake**.
C must prove that inputs are:

* **pinned** (manifest exists)
* **re-resolvable**
* **digest-verified**
* have explicit **basis/as-of** and **feature version pins**

## Handshake shape (conceptual)

**C issues ResolveManifestSet(manifest_refs[])** → returns **ResolvedManifestSet**
For each manifest:

* manifest ref + digest
* `basis` (offset/time basis recorded by OFS)
* `as_of` boundary
* `feature_version_pins`
* materialization refs + digests
* schema/shape summary (not data)

Then C may issue **VerifyMaterializations(refs+digests)** as a second step (or one combined operation).

## Pinned invariants (authoritative)

✅ **Required**

1. **Digest verification is mandatory**

   * If a manifest/materialization digest doesn’t match → REJECT.
2. **Basis/as-of must be present**

   * If absent/ambiguous → REJECT.
3. **Feature version pins must be present**

   * If missing → REJECT (prevents training/serving drift).
4. **No scanning**

   * MF never enumerates `ofs/` to “find latest dataset.” It only follows explicit refs.

❌ **Forbidden**

* Accepting a manifest without replay basis/as-of.
* “Soft accept” with warnings (this becomes prod drift).
* C reaching out to EB/Archive/Label Store to patch missing info (that’s OFS’s role).

## Receipts to MF-H

* `manifest_resolution_receipt`:

  * list of manifest refs + digests
  * list of materialization refs + digests
  * computed `input_fingerprint`
  * admissibility verdict + reason codes

## Failure posture

* **Correctness-critical**:

  * missing or invalid manifest/materialization → hard reject
  * transient object-store errors → retry bounded by policy, but never proceed without verification

---

# IJ11 — **G ↔ Registry API** (publish, idempotent)

## Purpose

This join turns “candidate bundle exists” into “Registry knows about it,” while enforcing:

* **idempotent publish**
* **conflict detection**
* **Registry-only activation**

It also supports the crucial production path: **publish retry without retrain**.

## Handshake shape (conceptual)

**PublishBundle(bundle_candidate, bundle_fingerprint, evidence_refs, auth_context)** → returns `PublishResult`

Possible results:

* `PUBLISHED(bundle_id, state, registry_receipt_ref)`
* `ALREADY_PUBLISHED(bundle_id, state)`
* `REJECTED(reason_codes[])` (e.g., missing compatibility metadata)
* `CONFLICT(existing_bundle_id, details)` (same id/fingerprint mismatch)

Separately, optional:
**GetBundleStatus(bundle_fingerprint or bundle_id)** → state (for recovery after timeouts)

## Pinned invariants (authoritative)

✅ **Required**

1. **Publish is idempotent by bundle_fingerprint**

   * G must include a stable idempotency key (bundle_fingerprint).
   * Duplicate publish attempts must converge to a single Registry truth.
2. **Conflict is a hard stop**

   * If Registry detects mismatch (same identity, different bytes) → treat as drift bug; stop.
3. **Publish ≠ activate**

   * G never requests activation; lifecycle actions belong to Registry + governance.

❌ **Forbidden**

* “Publish on FAIL” (unless a future policy explicitly adds a quarantined registry staging area — not in v0).
* Writing bundle blobs directly into `registry/bundles/...` from MF.
* Silent overwrite (“update bundle in place”).

## Receipts to MF-H

* `publish_attempt_receipt` (attempt_no, bundle_fingerprint, timestamp)
* `publish_result_receipt` (published/already_published/rejected/conflict + registry ids + reason codes)

## Failure posture

* Registry timeout / transient 5xx: **retry publish** (no retrain, no re-gate required)
* Registry reject: **hard fail** (fix candidate assembly/profile rules)
* Conflict: **hard fail** (investigate drift)

---

# IJ12 — **I → OTLP collector** (metrics/logs/traces)

## Purpose

This is MF’s **signal plane export**. It is required for production operability, but **never correctness-critical**.

## Handshake shape (conceptual)

I exports:

* traces (spans per stage + correlation keys)
* metrics (durations, error counters, retry counts)
* logs (structured stage events + reason codes)

## Pinned invariants (authoritative)

✅ **Required**

1. **Best-effort**

   * Telemetry failure must not block MF progress.
2. **Correlation keys everywhere**

   * `train_run_id`, `request_id`, `input_fingerprint`, `policy_rev`, `bundle_id/fingerprint (if any)`.
3. **No secrets / no raw rows**

   * Only ids/hashes/reason codes.

❌ **Forbidden**

* Making publish or gating depend on successful telemetry export.
* Emitting high-cardinality raw payloads (full manifest contents, row data).

## Receipts to MF-H?

Not required. IJ12 is signal-only.
(At most, H can record “telemetry exporter unhealthy” as an ops note, but not correctness).

## Failure posture

* Drop/buffer/retry within resource limits.
* If exporter is down, keep running.

---

# IJ13 — **I → `fp.bus.control.v1`** (optional MF control facts)

## Purpose

Optional convenience: make MF visible without crawling storage:

* `mf.train_run.started`
* `mf.train_run.completed` (PASS/FAIL posture)
* `mf.bundle.published`

These must remain **signals**, not truth.

## Handshake shape (conceptual)

I emits **Canonical Envelope events** whose payload is **by-ref pointers**:

* `mf_run_record_ref` (in `mf/...`)
* `bundle_id/fingerprint` (if published)
* `input_fingerprint` and policy_rev/build_id

## Pinned invariants (authoritative)

✅ **Required if enabled**

1. **By-ref only**

   * payload contains pointers/digests, not embedded evidence.
2. **Idempotent emission**

   * duplicates are allowed; consumers must tolerate.
3. **Never correctness-critical**

   * MF must not require control bus availability to proceed.

❌ **Forbidden**

* Treating `mf.*` events as the authoritative record of a run.
* Emitting anything that looks like “activate bundle now.”

## Receipts to MF-H

Optional. If you do record anything, record only:

* `control_fact_emit_attempt` + `emit_result`
  …but do not require it for correctness.

## Failure posture

* Best-effort only: drop/buffer/retry lightly; do not block MF.

---

# Authority decisions I’m locking (so we don’t drift later)

1. **IJ9 and IJ10 are correctness-critical** and must fail closed.
2. **IJ11 is correctness-critical** for publication; publish retries are first-class; conflict is hard stop.
3. **IJ12 and IJ13 are signal-only** (best-effort); MF correctness must not depend on them.
4. MF never performs **implicit “active config”** selection inside the vertex — triggers must pin refs, and MF records digests.

---

Absolutely — we’ll illuminate **IP1–IP4** as **production execution traces** through MF’s internal network, still keeping **all subnetworks opaque**. I’ll focus on:

* the **sequence of joins** (IJ1–IJ13 where relevant),
* the **mandatory receipts** written to MF-H (truth plane),
* the **go/no-go gates** (fail-closed boundaries),
* and what is **explicitly forbidden** (drift prevention).

I’ll also use the subnetwork letters (A–I) consistently.

---

# IP1 — Happy path: new run → PASS → publish

### Goal

A fresh TrainBuildRequest produces:

* a deterministic `train_run_id`,
* admissible inputs,
* evidence + PASS gate receipt,
* a bundle candidate,
* and a successful idempotent publish into Registry.

### Route (opaque boxes)

`A → B → C → D → E → F(PASS) → G`
with continuous `{A..G} → H` and `{A..G} → I`.

### Join-by-join trace (with invariants)

#### Step 0: Trigger arrives

* **Input:** `TrainBuildRequest` (request_id, intent, dataset_manifest_refs, profile_refs, training_recipe_ref)

**A (Run Intake + Idempotency)**

* Dedup boundary begins.
* Computes/claims `train_run_id` deterministically **only after** inputs are pinned (see next).

**H receipt (mandatory):**

* `request_received` (request_id, caller_principal, intent)

**I signal:**

* “mf.request.received” (correlation keys present)

---

#### Step 1: Context resolution (profiles/config)

**IJ1 / IJ9:** `A → B` then `B ↔ profiles/...`

**B (Context Resolver)**

* Resolves wiring+policy+recipe refs to digests/revs.
* Produces `MFContext` (policy knobs + wiring knobs + mf_build_id).

**Pinned invariant:** no implicit “active config”; digests must be pinned now.

**H receipt (mandatory):**

* `context_receipt`:

  * resolved profile refs + digests
  * policy_rev
  * mf_build_id
  * authz verdict = ALLOW

**Go/no-go:** if IJ9 fails → stop (not IP1).

---

#### Step 2: Input resolution + admissibility (J15 enforcement)

**IJ2 / IJ10 / IJ3:** `B → C`, then `C ↔ ofs/...`, then `C → D`

**C (Input Resolver + Admissibility)**

* Resolves manifests and materializations by-ref + digest verification.
* Ensures basis/as-of/feature pins are present.
* Computes `input_fingerprint`.

**H receipt (mandatory):**

* `admissibility_receipt`:

  * ADMISSIBLE
  * manifest/materialization digests
  * basis/as-of summary pointers
  * feature-version pins
  * `input_fingerprint`

**Go/no-go:** If reject → not IP1.

---

#### Step 3: Build orchestration (plan + stage machine)

**IJ4:** `C → D`, then `D → E`

**D (Build Orchestrator)**

* Constructs stage plan (TRAIN then EVAL, or combined) using policy rules.
* Creates stage seeds deterministically from `(train_run_id, stage_id)`.

**H receipt (mandatory):**

* `run_started` (train_run_id, input_fingerprint, policy_rev)
* `stage_started(TRAIN, attempt=1, stage_seed=...)`

---

#### Step 4: Train/Eval execution (opaque compute)

**E (Train+Eval Engine)**
Runs training, writes artifacts, runs eval (or produces separate eval pack).

**H receipts (mandatory):**

* `artifact_locator_receipts` for:

  * model/policy artifact refs + digests
  * eval report ref + digest
* `stage_completed(TRAIN, attempt=1)` (and EVAL if separate)

**I signals:**

* stage duration metrics + success counters

---

#### Step 5: Evidence, gating, bundle assembly

**IJ5:** `E → F`
**IJ6:** `F(PASS) → G`

**F (Evidence+Gates+Bundle Assembly)**

* Builds `TrainingEvidencePack` (evidence_fingerprint).
* Applies gate policy → PASS.
* Assembles `bundle_candidate` with:

  * `bundle_fingerprint` (idempotency anchor)
  * compatibility descriptor (required feature versions/capabilities)
  * provenance refs (manifests, policy_rev, mf_build_id, evidence refs)

**H receipts (mandatory):**

* `evidence_receipt` (evidence_fingerprint + refs/digests)
* `gate_receipt` = PASS (criteria + evidence refs)
* `bundle_candidate_receipt` (bundle_fingerprint + compatibility descriptor summary)

---

#### Step 6: Publish to Registry

**IJ11:** `G ↔ Registry API`

**G (Registry Publisher)**

* Calls publish with idempotency key = `bundle_fingerprint`.
* Receives `PUBLISHED(bundle_id, state=STAGED/APPROVED/..., registry_receipt_ref)`.

**H receipts (mandatory):**

* `publish_attempt(attempt=1)`
* `publish_result(PUBLISHED, bundle_id, registry_state, registry_receipt_ref)`

**Terminal state**

* `run_terminal(SUCCESS)` with pointers to bundle_id and key evidence receipts.

**I optional**

* OTLP spans completed; optional `mf.bundle.published` control fact (by-ref).

---

### What is forbidden inside IP1

* Training without a durable `admissibility_receipt`.
* Publishing without a PASS gate receipt + compatibility descriptor.
* Publishing into `registry/bundles/...` directly (Registry writes that).
* “Implicit config selection” at runtime after the run starts.

---

# IP2 — Input rejection path: manifest/config invalid

### Goal

Reject fast, reject loudly, reject reproducibly, and leave a durable trail.

### Route

`A → B → C(REJECT)` plus `{A..C} → H` and `{A..C} → I`.

### Trace

#### Step 0: Request arrives

Same as IP1.

#### Step 1: Context resolution

**If profiles/config invalid** (IJ9 fails):

* This is an **IJ1/IJ9 failure**, which we treat as IP2 class failure.

**H receipt:**

* `context_receipt` with authz/resolve failure reason codes
* `run_terminal(REJECTED_CONFIG)` (no train_run_id unless you mint one on failed resolve; I recommend **no**—keep `request_id` as the anchor in this case)

**Stop.**

#### Step 2: Manifest/admissibility rejection

If context resolves but manifests fail (IJ10):

* C resolves manifest refs but finds:

  * missing basis/as-of
  * digest mismatch
  * missing materializations
  * missing feature pins
  * unreadable object store objects

**H receipts (mandatory):**

* `admissibility_receipt` = REJECT

  * reject reasons + offending refs + expected/observed digests (where applicable)
* `run_terminal(REJECTED_INPUTS)`

**I signals:**

* structured reason codes (e.g., `manifest_missing_basis`, `digest_mismatch`)

**No D/E/F/G activity happens.**

### Boundary authority call (locked)

**IP2 is not a “soft fail.”**
MF must not attempt to “repair” missing basis/as-of/feature pins by reading EB/LabelStore directly. That’s OFS’s job.

---

# IP3 — Gate fail path: trained/evaluated but not eligible

### Goal

Allow training to complete, produce evidence, but produce **no publish attempt** unless explicitly allowed by policy (v0: not allowed).

### Route

`A → B → C → D → E → F(FAIL)` plus `{A..F} → H` and `{A..F} → I`.

### Trace highlights

Steps 0–4 match IP1 through evidence creation.

#### Gate decision FAIL (F)

F computes evaluation + applies gate criteria → FAIL.

**H receipts (mandatory):**

* `evidence_receipt` (still required!)
* `gate_receipt` = FAIL

  * reason codes + thresholds + evidence refs
* `run_terminal(FAILED_GATES)` (terminal state)

**No IJ6 publish intent. No IJ11 publish call.**

### Boundary authority call (locked)

* **No FAIL publish** in v0.
  If you want “publish-but-not-eligible” as a future workflow, it must be a separate registry staging/quarantine feature — not a quiet behavior in MF.

---

# IP4 — Publish-retry path (no retrain)

### Goal

Recover from registry failures without retraining or regating, using the durable evidence chain in `mf/...`.

### Route

`A → (resume existing run via H) → D (skip E/F if complete) → G (retry publish)`
and `{A,D,G} → H`, `{A,D,G} → I`.

### Preconditions (must already be true in H)

A prior run exists with:

* ADMISSIBLE input_fingerprint
* evidence receipt
* gate receipt = PASS
* bundle_candidate_receipt (bundle_fingerprint)
  but either:
* publish attempt missing, or
* publish attempt failed transiently, or
* publish attempt timed out (unknown outcome).

### Trace

#### Step 0: Trigger arrives again

Duplicate request or operator “retry publish”.

**A (Idempotency)**

* Checks H for `train_run_id` for this request/input_fingerprint.
* Finds existing run with PASS and bundle_fingerprint.
* Decides “resume path”.

**H receipt:**

* `resume_decision(resume_type=PUBLISH_ONLY, prior_train_run_id, bundle_fingerprint)`

#### Step 1: Orchestrator decides to skip compute

**D (Build Orchestrator)**

* Consults H:

  * confirms stage_completed for TRAIN/EVAL
  * confirms PASS + bundle_candidate exist
* Emits stage plan: “PUBLISH_ONLY”.

**H receipt:**

* `stage_started(PUBLISH, attempt=n)`

#### Step 2: Publish retry

**G (Registry Publisher)**

* Calls Registry publish with idempotency key = bundle_fingerprint.
* Registry returns:

  * `ALREADY_PUBLISHED` (if the first attempt succeeded but MF didn’t get the response), or
  * `PUBLISHED` (if it never succeeded), or
  * transient failure again (retry), or
  * conflict/reject (hard stop).

**H receipts:**

* `publish_attempt(attempt=n)`
* `publish_result(ALREADY_PUBLISHED|PUBLISHED|FAILED_TRANSIENT|CONFLICT|REJECTED)`

#### Terminal behavior

* If published/already published: `run_terminal(SUCCESS_PUBLISHED)`
* If transient failure persists: run remains `PUBLISH_PENDING` (not “failed training”)

### Boundary authority call (locked)

* **Publish retry must never trigger retraining.**
  If evidence/gates are intact, publish-only is legal and expected.

---

## A tiny “receipt ladder” across IP1–IP4 (so we don’t drift)

These are the minimum receipts that must exist before the next phase is allowed:

* Before leaving **B**: `context_receipt`
* Before entering **D**: `admissibility_receipt=ADMISSIBLE` + `input_fingerprint`
* Before entering **G**: `gate_receipt=PASS` + `bundle_candidate_receipt`
* Before declaring success: `publish_result(PUBLISHED|ALREADY_PUBLISHED)`

Everything else can be implementation detail later.

---

Absolutely — IP5–IP8 are the “production sharp-edge paths” that keep MF sane under duplicates, partial failures, and ops intervention. Still **opaque subnetworks**, but we’ll be very explicit about:

* **what triggers the path**
* **which internal joins are exercised**
* **what MF-H must record**
* **what MF returns outward**
* and the **design-authority boundary calls** (what is/ isn’t allowed).

I’ll keep the same notation: A..I + IJ*.

---

# IP5 — Duplicate trigger path

**Idempotent no-duplicate-work** (very common in production)

### What triggers IP5

* Run/Operate retries a TrainBuildRequest (timeout/unknown outcome).
* Scheduler overlaps (cron fired twice).
* Operator double-clicks “run”.
* Downstream pipeline replays “start training” control facts.

### Route (opaque boxes)

`A ↔ H` is the core.
Optionally, if “status is unknown”, A may consult deeper receipts in H, but it does **not** re-run B/C/D/E/F by default.

### The canonical IP5 behaviors (authoritative)

IP5 must have exactly one of three outcomes:

## IP5.a — Duplicate while run is RUNNING

**A** checks H and finds an existing `train_run_id` with terminal state absent and latest status RUNNING.

**MF outward response (conceptual):**

* `status=RUNNING`
* `train_run_id`
* `last_known_stage` (optional)
* `retry_after_hint` (optional)

**H receipt:**

* `duplicate_request_observed`

  * request_id
  * resolved to train_run_id
  * current run status

**I signals:**

* increment `mf.duplicate_request.count`
* log with correlation keys

✅ **Allowed:** return quickly without touching compute.

---

## IP5.b — Duplicate after run is DONE (published or not)

**A** checks H and finds terminal state exists.

Two terminal categories:

### DONE + Published (SUCCESS_PUBLISHED)

Return:

* `status=DONE`
* `train_run_id`
* `bundle_id` / `bundle_fingerprint`
* `registry_state` (if known)

### DONE + Not Published (e.g., FAILED_GATES, REJECTED_INPUTS)

Return:

* `status=DONE`
* `train_run_id`
* `outcome=FAIL/REJECT`
* `reason_codes[]`

**H receipt:**

* `duplicate_request_observed` (as above)

✅ **Allowed:** duplicates become a read-only “status query.”

---

## IP5.c — Duplicate after a crash (status ambiguous)

This is the only time A may ask D to **resume**, but only by consulting H.

**A** sees:

* `run_claimed` exists, but stage receipts are incomplete and no terminal receipt exists.

**A behavior:**

* returns either:

  * `status=RESUMING` (and triggers resume), or
  * `status=RUNNING` if another worker is already resuming.

**H receipt:**

* `resume_requested` (resume_type inferred: full resume vs publish-only)

✅ **Allowed:** resume is driven solely by H receipts.
❌ **Forbidden:** starting a second independent run because “we’re not sure.”

### Boundary authority call (locked)

* **Duplicate triggers must never create duplicate runs** for the same pinned inputs.
* “Same request / same input_fingerprint / same profile digests / same build id” must resolve to **the same `train_run_id`** or return existing terminal status.

---

# IP6 — “Already published” path

**Idempotent publish (Registry says it already has it)**

### What triggers IP6

* MF publish succeeded earlier but response was lost.
* Publish retry (IP4) is invoked and Registry returns `ALREADY_PUBLISHED`.
* Two MF instances race to publish the same bundle_fingerprint (rare, but possible if locking is imperfect).

### Route

`A → … → F(PASS) → G(ALREADY_PUBLISHED)`
Often it occurs in publish-only retry as well: `A → D(PUBLISH_ONLY) → G(ALREADY_PUBLISHED)`.

### Trace highlights

1. Preconditions: bundle_candidate exists with `bundle_fingerprint`, PASS gate receipt exists (or at least the publish intent is legitimate).
2. **G** calls Registry publish with idempotency key = `bundle_fingerprint`.
3. Registry returns `ALREADY_PUBLISHED(bundle_id, state)`.

**H receipts (mandatory):**

* `publish_attempt(attempt=n, bundle_fingerprint)`
* `publish_result(ALREADY_PUBLISHED, bundle_id, registry_state)`
* `run_terminal(SUCCESS_PUBLISHED)` (if not already terminal)

**MF outward response:**

* Treat as success:

  * `status=DONE`
  * `bundle_id`
  * `registry_state`

### Boundary authority call (locked)

* **ALREADY_PUBLISHED is success**, not an error.
* MF must not attempt to “republish under a new id” or regenerate bundle bytes to force a new publish.

---

# IP7 — Conflict path

**Same bundle identity, different bytes → Registry rejects/conflict**

### What triggers IP7

This is a drift/bug signal. Typical causes:

* Non-determinism inside MF-E/F (bundle assembled differently for same inputs).
* Policy/profile refs weren’t actually pinned (implicit config drift).
* Artifact digests were not correctly recorded/verified (corruption or overwrite).
* Two different MF builds created different bytes but tried to claim the same identity.

### Route

There are two common variants:

## IP7.a — Conflict at publish time

`A → … → F(PASS) → G(CONFLICT)`

G publishes with `bundle_fingerprint` / identity anchor. Registry detects mismatch and returns CONFLICT.

**H receipts (mandatory):**

* `publish_attempt`
* `publish_result(CONFLICT, details)`
* `run_terminal(FAILED_CONFLICT)`

**MF outward response:**

* `status=FAILED`
* `failure_class=CONFLICT`
* include a stable “incident handle” (e.g., train_run_id + conflict receipt id)

✅ **Allowed:** stop hard; preserve evidence.
❌ **Forbidden:** “fix by retrying until it works” or “publish a mutated candidate silently.”

## IP7.b — Conflict discovered earlier (internal consistency break)

If MF-H detects “same run id / same stage but different artifact digest,” we treat it as an internal conflict too:

* This should be surfaced before Registry call (still ends as FAILED_CONFLICT).

### Boundary authority call (locked)

* **Conflict is a hard stop** and must escalate to investigation.
* Conflict indicates the platform’s reproducibility contract is broken; continuing would poison Registry truth.

---

# IP8 — Controlled cancel path (ops-friendly)

### What triggers IP8

* Operator cancels a long-running job.
* Resource constraints (preemption) require stopping.
* Scheduled window ended.

This is not a correctness primitive, but a production reality feature.

### Route

`Run/Operate cancel → A/D → D(stop)`
E may be interrupted depending on stage.

### Authoritative semantics

Cancel must be **best-effort** and **explicitly recorded**. There are two meaningful outcomes:

## IP8.a — Cancel succeeds (run terminates as CANCELED)

* D stops scheduling new work.
* If E is running, D requests stop; if E can’t stop immediately, it will stop at the next checkpoint boundary.

**H receipts (mandatory):**

* `cancel_requested` (who/when/why)
* `run_terminal(CANCELED)` OR `run_terminal(CANCEL_PENDING)` then later `CANCELED`

**MF outward response:**

* `status=CANCELED` (or `CANCEL_PENDING` if still draining)

## IP8.b — Cancel is too late (run already terminal)

* A/D checks H and finds terminal receipt exists.

**H receipt:**

* `cancel_ignored_terminal` (optional)
  **Response:**
* Return the terminal status (DONE/FAILED/etc.)

### Boundary authority call (locked)

* Cancel must **not** leave MF in an ambiguous half-state with no durable marker.
* If artifacts were produced before cancel, they remain immutable and referenced by receipts; a later resume can decide whether to continue or start a new run (by policy).

---

# Quick summary table (IP5–IP8)

| Path | Primary purpose              | Primary join/loop  | Correctness critical?     | Typical outcome                     |
| ---- | ---------------------------- | ------------------ | ------------------------- | ----------------------------------- |
| IP5  | Handle duplicates            | A ↔ H              | Yes                       | RUNNING or DONE (no duplicate work) |
| IP6  | Publish idempotency          | G ↔ Registry       | Yes                       | Success with ALREADY_PUBLISHED      |
| IP7  | Detect drift/non-determinism | G ↔ Registry (+ H) | Yes                       | Hard fail, preserve evidence        |
| IP8  | Ops-friendly stop            | Run/Operate → A/D  | No (but must be recorded) | CANCELED / CANCEL_PENDING           |

---

Absolutely. IL1–IL4 are the **production “loops”** that make MF resilient under duplicates, restarts, flaky dependencies, and evolving gate policy — *without* breaking your outer-network pins (manifests-only, by-ref+digests, append-only truth, idempotent publish).

I’ll illuminate each loop as:

* **What it guarantees**
* **When it activates**
* **How the loop is driven** (reads/writes against MF-H ledger)
* **What must be recorded**
* **Hard boundary calls** (allowed vs forbidden)

We still treat **A/D/E/F/H** as opaque boxes; we’re only describing loop behavior between them.

---

# IL1 — Request idempotency loop (dedupe)

### `A ↔ H`

## What IL1 guarantees (authoritative)

For the same **pinned run key**, MF will:

* never do duplicate work,
* never create multiple train runs,
* and always return a stable answer: **RUNNING / DONE / REJECTED / FAILED**.

**IL1 is the backbone that makes IP5 real.**

## When it activates

* every TrainBuildRequest
* every retry of the same request
* every “unknown outcome” situation after a crash

## The loop behavior (conceptual)

Think of A repeatedly doing:

1. **Read**: “Do we already have a run for this request/run key?”
2. If not, **claim**: “Create/claim run atomically”
3. If yes, **resolve**: “Return existing state or resume”

### The canonical IL1 cycle

```
A: compute RunKey (from pinned refs)  ->  H: lookup(run_key)
      |                                        |
      |  not found                             | found
      v                                        v
A: claim(run_key) ------------------> H: append(run_claimed)
      |
      v
A: proceed to B/C/D...   OR   return RUNNING/DONE immediately
```

## The non-negotiable design choice (I’m pinning)

**RunKey must be derived ONLY from pinned inputs** (no time-of-day):

* ordered DatasetManifest digests/refs
* profile digests (policy + recipe + wiring rev)
* MF build id (so “same inputs different MF build” is a different RunKey *unless you explicitly choose otherwise*)
* intent (train vs eval-only vs publish-only)

This is the only way “same request, same pinned world” stays stable.

## What H must record (minimum receipts)

* `run_claimed(run_key, train_run_id, claimed_by, claim_ts, lease_token)`
* `run_status(train_run_id, status)` (RUNNING, DONE, FAILED, REJECTED, CANCELED…)
* `last_known_stage(train_run_id, stage_id, attempt_no)` (optional but very helpful)

### Concurrency/lease posture (still brainstorming, but production required)

I’m not forcing a storage tech, but I *am* forcing behavior:

* **Exactly one active claimant** for a RunKey at a time.
* A claim must have a **lease/heartbeat** concept so a dead worker doesn’t block forever.
* A second worker can only take over if the lease expires (and must record “takeover”).

## Fail posture

* If H is unavailable → **fail closed** (because idempotency is correctness-critical).
* If claim succeeds but downstream fails → IL1 ensures future requests reattach to the same train_run_id and resume.

## Forbidden patterns (hard no)

* “If we can’t tell, start a new run.” (creates drift)
* “Use current active profile at runtime.” (breaks reproducibility)
* “RunKey based on wall clock.” (breaks idempotency)

---

# IL2 — Stage resume loop (crash/restart survivability)

### `D ↔ H`

## What IL2 guarantees (authoritative)

MF can restart mid-run and **resume safely**:

* no redoing completed stages,
* no skipping incomplete stages,
* and no “half-truth success”.

This is what makes MF a real production job unit.

## When it activates

* worker crash/restart
* orchestrator restart
* “status ambiguous” from IL1 (claim exists but terminal state missing)
* explicit “resume” trigger

## The loop behavior

D repeatedly does:

1. **Read stage ledger**: Which stages are COMPLETE? Which are STARTED but not COMPLETE?
2. **Decide plan**:

   * skip completed stages
   * retry incomplete stages (possibly with new attempt_no)
3. **Append stage receipts** for the resumed attempt

### Canonical IL2 cycle

```
D -> H: read(stage_receipts for train_run_id)
D: compute resume_plan
D -> H: append(stage_started(stage_id, attempt_no, resume=true))
D -> E/F/...: execute stage
D -> H: append(stage_completed or stage_failed)
(repeat until terminal)
```

## What H must record (minimum receipts)

For every stage (TRAIN, EVAL, GATE, PACKAGE, PUBLISH):

* `stage_started(stage_id, attempt_no, stage_seed, started_by)`
* `stage_completed(stage_id, attempt_no, outputs_locators...)`
* `stage_failed(stage_id, attempt_no, reason_codes...)`

**Key invariant:** a stage is only complete if `stage_completed` exists.

### Resume rules (authoritative)

* If `stage_started` exists but no `stage_completed`, that stage is **incomplete** and must be retried or explicitly canceled.
* D may “promote” an incomplete stage into a new attempt number, but must record supersession:
  `stage_attempt_supersedes(attempt_no -> attempt_no+1)` (conceptually).

## Fail posture

* If H can’t be read/written → **fail closed**.
* Resume must be driven **only** by ledger truth, not by “what files look like on disk”.

## Forbidden patterns

* Inferring completion from presence of files without a completion receipt.
* Re-running a stage while claiming it’s still attempt 1 (attempt identity must be monotonic).

---

# IL3 — Stage retry loop (transient compute failures)

### `D → E (fails) → D (retry/backoff) → E`

## What IL3 guarantees (authoritative)

Transient failures in compute (E) do not corrupt run truth; retries are:

* bounded by policy,
* recorded as attempts,
* deterministic in identity (same stage, new attempt_no),
* and do not mutate previously successful evidence.

## When it activates

* E fails due to transient causes: timeouts, resource exhaustion, temporary IO errors, ephemeral infra issues.

## The loop behavior

```
D -> H: stage_started(TRAIN, attempt=k)
D -> E: execute
E fails
D -> H: stage_failed(TRAIN, attempt=k, reason=TRANSIENT_X)
D waits/backoff per policy
D -> H: stage_started(TRAIN, attempt=k+1)
D -> E: execute again
...
```

## Policy knobs that matter (environment ladder compatible)

Retry behavior is policy-driven (from MFContext policy profile):

* max attempts per stage
* which reason codes are retryable
* backoff schedule
* resource envelope escalation rules (optional)

These can be stricter in prod; semantics remain the same.

## What H must record

* every `stage_failed` with retryability classification (even if inferred later)
* attempt counters
* final exhaustion:

  * `run_terminal(FAILED_RETRY_EXHAUSTED)` with reason summary

## Critical deterministic rule (design authority)

* **Attempt number changes; stage identity does not.**
* If you want deterministic seeds: derive `stage_seed = f(train_run_id, stage_id, attempt_no)`.

## Forbidden patterns

* “Retry by rerunning without recording the failure”
* “Retry but overwrite prior attempt artifacts”
* “Retry forever” (must be bounded)

---

# IL4 — Evidence/gate loop (re-evaluate without retrain)

### `D ↔ F ↔ H`

## What IL4 guarantees (authoritative)

If training artifacts already exist, MF can:

* re-run **evaluation**, **gates**, and **bundle assembly**
* without retraining (E),
  so you can recover from interruptions or apply updated gate policy **without recomputing the expensive part**.

This supports:

* “eval step failed but training succeeded”
* “gate assembly interrupted”
* “policy requires re-eval/gate under new policy_rev” (careful: see below)

## When it activates

* E completed TRAIN stage, but:

  * EVAL failed or didn’t run,
  * gate decision missing,
  * packaging/publish interrupted,
  * or “publish-only retry” needs the bundle candidate reloaded.

## The loop behavior (conceptual)

```
D -> H: read existing TRAIN artifacts locators
D -> F: request eval/gate/package using those pinned artifact locators
F -> H: append evidence_receipt + gate_receipt + bundle_candidate_receipt
D decides next: publish or stop
```

## The subtle policy rule (I’m pinning it now to prevent drift)

**Re-gating under a new policy_rev must produce a new “gate receipt” that supersedes the prior one.**

Two safe versions of IL4 exist:

### IL4.a — Resume under the *same* policy_rev (pure recovery)

* Re-eval/gate/package is just completing missing work.
* It produces the same or compatible outputs (but always new receipts per attempt).

### IL4.b — Re-gate under a *different* policy_rev (governed change)

* Allowed only if explicitly invoked as intent (`re_gate_only` / `re_eval_only`)
* Must record:

  * old policy_rev, new policy_rev
  * supersedes linkage
* Must not pretend this is the same candidate unless the bundle_fingerprint is unchanged.

## What H must record

* `evidence_receipt(evidence_fingerprint, eval refs/digests)`
* `gate_receipt(PASS/FAIL, criteria refs, policy_rev)`
* `bundle_candidate_receipt(bundle_fingerprint, compatibility descriptor, policy_rev)`
* supersedes relationships if re-gating changed policy rev or criteria

## Forbidden patterns

* Changing gate policy and silently “updating” old receipts.
* Publishing a bundle candidate when the gate receipt is missing or ambiguous.
* Re-evaluating by re-reading datasets directly (must use pinned artifacts/locators created earlier).

---

# The shared “don’t drift” rule across IL1–IL4

**Every loop iteration must be ledger-driven and receipt-based.**
If it isn’t recorded in H, it’s not real. If it’s a signal only, it lives in I.

---

Absolutely — IL5–IL7 are the remaining production loops that make MF **operationally safe** under flaky Registry/bus/telemetry and ensure MF’s own history is **append-only and explainable**.

We’ll keep all subnetworks opaque; we only describe loop behavior and its invariants.

---

# IL5 — Publish retry loop (Registry transient failures)

### `G (attempt) → Registry fails → G (retry/backoff) …`  with `G ↔ H` anchoring truth

## What IL5 guarantees (authoritative)

* A bundle candidate that is **already PASS-eligible** can be published **eventually** without retraining.
* Publish behavior is **idempotent** and **conflict-detecting**.
* Transient Registry issues do not corrupt MF’s run truth.

This is the production counterpart to IP4.

## When IL5 activates

* Registry returns timeout/5xx/network failure.
* MF crashes after sending publish request and restarts with unknown outcome.
* Rate limiting / temporary auth failure (depending on policy classification).

## Loop behavior (conceptual)

G repeatedly does:

1. **Read** from H: do we already have a terminal publish result for this `bundle_fingerprint`?
2. If not, **attempt publish** with idempotency key.
3. Record attempt + outcome in H.
4. If transient fail, backoff and retry within policy budget.

### Canonical IL5 cycle

```
G -> H: read(publish_state for bundle_fingerprint)
   if PUBLISHED/ALREADY_PUBLISHED: stop (success)
   else:
      G -> H: append(publish_attempt(attempt_no))
      G -> Registry: Publish(bundle_fingerprint, candidate)
      outcome:
        - success: G -> H append(publish_result(PUBLISHED|ALREADY_PUBLISHED))
        - transient fail: G -> H append(publish_result(FAILED_TRANSIENT, reason))
        - reject/conflict: G -> H append(publish_result(REJECTED|CONFLICT)) and stop
      retry on transient (bounded)
```

## Pinned invariants (hard rules)

✅ **Required**

1. **Idempotency key is `bundle_fingerprint`** (or equivalent stable fingerprint).
2. **Publish attempts are monotonic**: `attempt_no` increments; previous attempts are never overwritten.
3. **Success is sticky**: once H records PUBLISHED/ALREADY_PUBLISHED, no further publish attempts are allowed for that same bundle_fingerprint.
4. **Conflict is terminal**: stop and escalate (drift detected).
5. **Retry is bounded** by policy (attempt budget / time budget). If exhausted, run becomes `PUBLISH_PENDING` or `FAILED_PUBLISH_EXHAUSTED` depending on policy (see below).

❌ **Forbidden**

* Retraining to “fix” a publish failure.
* Generating a new bundle identity just because publish failed.
* Treating “control bus publish event” as proof of publish (Registry state + H receipt is proof).

## Failure posture (authoritative)

* **Transient Registry failure**: retry with backoff; do not change candidate bytes.
* **Auth failure**: classify as transient or terminal by policy; in prod, usually terminal until credentials/policy fixed.
* **Reject (validation)**: terminal — candidate assembly is wrong.
* **Conflict**: terminal — determinism or pinning is broken.

## What H must record (minimum receipts)

* `publish_attempt(train_run_id, bundle_fingerprint, attempt_no, ts)`
* `publish_result(outcome, reason_codes, registry_bundle_id?, registry_state?, ts)`
* if exhausted: `run_status(PUBLISH_PENDING | FAILED_PUBLISH_EXHAUSTED)` + next retry schedule hint (optional)

## “Pending” vs “Failed” (design authority call)

I’m pinning this behavior for production sanity:

* If training/evidence/gates are complete and PASS, but publish fails transiently → **run is not “failed training.”**
  It is **PUBLISH_PENDING**, and it is legitimate to retry publish later without recomputing anything.

---

# IL6 — Supersedes loop (“new run replaces old”)

### Cross-run truth chain anchored in H

## What IL6 guarantees (authoritative)

MF’s history remains **append-only**, but you can still express:

* “this newer run/bundle is meant to replace that older run/bundle,”
  without mutating or deleting the older one.

This is how MF stays explainable and consistent with your platform’s supersedes posture.

## When IL6 activates

* A run ends in REJECTED/FAILED (inputs bad, gates fail, conflict) and a newer attempt is made.
* A model family is retrained due to backfill, feature evolution, late-truth correction, or policy changes.
* An incident causes rollback and then a fix-forward run is created.

## The loop behavior (conceptual)

IL6 isn’t a “retry loop” in place; it’s a **linkage loop** across independent runs:

1. A new TrainBuildRequest comes in with **different RunKey** (different manifests, different policy rev, different MF build id, etc.).
2. A creates a new train_run_id and proceeds normally.
3. H records a **supersedes relationship** from the new run/bundle to the prior run/bundle *if* the intent says “replace” and if the scopes match.

### Canonical IL6 chain

```
(old train_run_id) --terminal--> FAILED_GATES
          |
          | (new request: same scope, new manifests or new policy)
          v
(new train_run_id) --terminal--> SUCCESS_PUBLISHED
          |
          +--> H: supersedes(old_run_id, old_bundle_id?, reason, link_type)
```

## Pinned invariants (hard rules)

✅ **Required**

1. **Supersedes is explicit and append-only**: a new receipt links old→new; old receipts remain immutable.
2. **Supersedes is typed** (so you don’t conflate meanings):

   * `supersedes_failed_attempt`
   * `supersedes_previous_candidate`
   * `supersedes_active_bundle` (note: activation is Registry’s job; MF can only express intent)
3. **Supersedes is scope-checked**:

   * you cannot claim “replaces” if the scope differs (different model family / different decision surface / incompatible feature pack lineage).

❌ **Forbidden**

* Deleting or overwriting the old run/bundle artifacts.
* Silent “replacement” without a recorded reason and linkage.
* MF claiming “ACTIVE is replaced” — only Registry can change ACTIVE. MF can only say “this new bundle supersedes that old candidate in MF’s build lineage.”

## What H must record (minimum receipts)

* `supersedes_receipt`:

  * `new_train_run_id`
  * `old_train_run_id` (and/or `old_bundle_id`)
  * `link_type`
  * `reason` (backfill id / feature_pack_rev / incident id / policy_rev change)
  * optional: governance fact ref (if it came from a declared backfill/incident)

## Why IL6 matters for the platform loops

* It’s the MF-side backbone for L3/L4/L5/L6:

  * backfills create new manifests → new runs supersede old
  * feature evolution → new runs supersede old
  * incident fix-forward → new runs supersede old
* It allows audit queries like: “show me the lineage of bundles for model family X.”

---

# IL7 — Signal emission best-effort loop (non-correctness)

### `I (emit) → fail/drop → I (retry or give up)`  + optional `I ↔ H` note

## What IL7 guarantees (authoritative)

* MF remains operable and observable under transient telemetry/control-bus failures.
* **Correctness never depends on signals.**
* Signals can be retried, but retries are bounded and must not flood production.

## When IL7 activates

* OTLP collector unavailable.
* Control bus unavailable.
* Network partition.
* Throttling on telemetry pipelines.

## Loop behavior

I repeatedly does:

1. attempt export (OTLP or control fact)
2. if success: done
3. if fail: buffer briefly (bounded) and retry with backoff, or drop with a count

### Canonical IL7 cycle

```
I: emit(telemetry/control_fact)
  success -> done
  fail ->
     if buffer budget remains: backoff and retry
     else: drop and increment "dropped" counters
```

## Pinned invariants (hard rules)

✅ **Required**

1. **Best-effort**: telemetry/control-fact failure must not block MF (no correctness coupling).
2. **Bounded buffering**: avoid runaway memory/disk usage.
3. **Correlation keys preserved**: every emitted item carries train_run_id, request_id, input_fingerprint, policy_rev, bundle_id/fingerprint (if any).
4. **No secrets / no raw rows**: only ids/hashes/reason codes.

❌ **Forbidden**

* Treating a control fact as the authoritative run record.
* Blocking publish because OTLP export failed.
* Emitting large payloads (full manifests, evidence blobs) onto the control bus.

## Optional interaction with H

Not required, but allowed as *ops notes*:

* H may record `telemetry_export_unhealthy` as a non-correctness receipt (useful for debugging).
  But MF must not require it.

---

# Authority decisions locked from IL5–IL7 (so we don’t drift)

1. **Publish failure ≠ training failure** when evidence + PASS exist → use `PUBLISH_PENDING` and allow publish-only retries.
2. **Supersedes is append-only, typed, and scope-checked**; MF never mutates old truth and never claims activation authority.
3. **Signals are never correctness-critical**; bounded retries only; truth lives in H and Registry.

---

Yep — there’s **negative space** in this network that’s just as important as the joins: **non-joins** (forbidden edges) and **signal-only edges** (exist, but don’t carry correctness).

Below is the complete “MF non-joins + what-nots” set I’m locking as **boundary law** before we go deeper.

---

# A) External non-joins (MF must not connect to these as a data/authority path)

## A1) MF ↛ EB / Archive (direct read)

* **Forbidden:** MF reading EB/Archive directly to assemble training data.
* **Why:** OFS is the deterministic dataset builder; MF consumes **DatasetManifests only**.
* **Allowed alternative:** OFS builds manifests from EB/Archive; MF consumes manifests.

## A2) MF ↛ Label Store (direct read)

* **Forbidden:** MF querying Label Store directly for labels/targets.
* **Why:** as-of/leakage discipline belongs in OFS manifests; MF is a consumer of pinned datasets.

## A3) MF ↛ OFP / IEG / DL (direct dependency for training input)

* **Forbidden:** MF reaching into online projections or degrade state to form training datasets.
* **Why:** training must be anchored by replayable basis + manifests, not live caches/state.
* **Allowed:** MF may **consume** declared feature/version requirements (as metadata) via profiles/feature pack refs, not via live services.

## A4) MF ↛ DF/AL/DLA/Case Workbench (direct coupling)

* **Forbidden:** MF “calling DF”, “reading AL outcomes”, or “pulling cases” as training input.
* **Why:** these are downstream truth/ops systems; learning input is mediated through Label Store + OFS.
* **Allowed:** DLA exports and case outcomes can influence OFS dataset construction *upstream*, not MF directly.

## A5) MF ↛ Activation (ACTIVE switch)

* **Forbidden:** MF taking any action that changes what DF uses in production.
* **Why:** Registry is the sole lifecycle + ACTIVE authority.
* **Allowed:** MF publishes candidates; Registry governs activation/rollback.

---

# B) Substrate non-joins (namespace/ownership boundaries)

## B1) MF ↛ `registry/bundles/...` (direct write)

* **Forbidden:** MF writing bundle blobs into Registry’s object-store namespace.
* **Why:** prevents shadow-registry drift; Registry must own durability/acceptance semantics.
* **Allowed:** MF writes `mf/...` evidence and publishes by API; Registry stores under its namespace.

## B2) MF ↛ mutate `ofs/...` or `profiles/...` or `gov/...`

* **Forbidden:** MF “fixing” OFS manifests, editing profiles, or rewriting governance facts.
* **Why:** those are other authorities; MF is a consumer.
* **Allowed:** MF can *reference* them and emit its own `mf/...` receipts and artifacts.

## B3) MF ↛ overwrite-in-place (any MF truth)

* **Forbidden:** rewriting `mf/...` artifacts/receipts “in place.”
* **Why:** append-only + supersedes is your platform posture; overwrites destroy audit and resumability.
* **Allowed:** new artifacts + receipts that supersede older ones.

---

# C) Correctness non-joins (edges that exist but must never be “truth”)

These are the **signal-only edges**:

## C1) MF → OTLP (IJ12) is not correctness

* **Rule:** telemetry can fail without changing MF outcome.

## C2) MF → `fp.bus.control.v1` (IJ13) is not correctness

* **Rule:** control facts are notifications/by-ref pointers, never the authoritative run record.

**Translation:** if you deleted all telemetry/control-bus output, MF must still be fully correct as long as `mf/...` + Registry truth exists.

---

# D) Internal bypass non-joins (disallowed shortcuts inside MF)

These are the “no bypass” rules between opaque internal boxes:

## D1) E ↛ Registry (no direct publish)

* **Forbidden:** Train/Eval Engine calling Registry.
* **Why:** publishing must be gated and ledgered (F/G/H).

## D2) E ↛ object store “truth write” without H

* **Forbidden:** E writing artifacts and considering them real without MF-H recording locators/digests.
* **Why:** breaks resume/idempotency/audit chain.

## D3) F ↛ OFS (no re-reading datasets)

* **Forbidden:** Gates/Bundle assembly re-reading manifests/materializations independently to “double check.”
* **Why:** bypasses orchestrated stage receipts; creates hidden data dependencies.

## D4) B ↛ datasets (no data-plane reads)

* **Forbidden:** Context Resolver touching `ofs/...` or any training data.
* **Why:** B’s job is config/policy resolution only.

## D5) D ↛ “infer completion from files”

* **Forbidden:** Orchestrator deciding a stage is complete because a file exists.
* **Why:** only H receipts define completion.

---

# E) Path-level what-nots (illegal sequences)

These are **non-paths**—routes MF must never take:

1. **No ADMISSIBLE receipt → no training**
2. **No PASS gate receipt → no publish attempt**
3. **No durable bundle_candidate receipt → no publish attempt**
4. **Publish failure → never triggers retrain** (publish-only retry is the path)

---

## If you want it as a single “negative adjacency list”

* MF ↛ {EB, Archive, LabelStore, DF, AL, DLA, CaseWorkbench} (direct)
* MF ↛ {activate ACTIVE}
* MF ↛ {write registry/bundles, mutate ofs/profiles/gov, overwrite mf truth}
* MF correctness ↛ {OTLP, control-bus}
* Inside MF: B ↛ data-plane, C ↛ “scan latest”, E ↛ Registry, E ↛ truth without H, D ↛ file-inference

---

## USER: PAUSE FOR REFLECTION

Here’s the **anchored MF blueprint** we’ve established in this brainstorm — the “design constitution” for the vertex and its first-layer inner network (still opaque boxes). This is the set of constraints I will **hold constant** as we go deeper so we don’t drift.

---

# 1) MF’s place in the larger platform network

## MF’s role

**Model Factory (MF) is the offline build authority for deployable decision artifacts.**
It turns **pinned training datasets + pinned profiles** into **evidence-backed bundles**, then **publishes candidates** to Registry.

## Authority boundaries (hard)

MF is authoritative for:

* training run identity + run record
* evaluation evidence + gate receipts
* bundle candidate assembly + publish attempt history

MF is *not* authoritative for:

* **activation** (Registry alone decides ACTIVE)
* **labels** (Label Store is truth)
* **feature definitions** (MF consumes a singular versioned authority; it doesn’t invent)
* **training data construction** (Offline Shadow does; MF consumes manifests)

## MF’s outer adjacency (complete production edges)

**Mandatory hard joins**

1. **J15: OFS → MF**
   DatasetManifests only (by-ref + digests + replay basis + as-of + feature pins).

2. **J16: MF → Registry**
   Publish bundle candidate + evidence; Registry governs lifecycle and ACTIVE.

**Control/ops edges**

* Run/Operate → MF (trigger with pinned inputs + intent + request_id)
* MF ↔ object store (`ofs/` reads, `mf/` writes; Registry owns `registry/bundles/`)
* MF ↔ `profiles/` (wiring + policy profile revisions; versioned and cited)
* MF → OTLP (observability; correlation keys everywhere)
* MF → `fp.bus.control.v1` (optional, signal-only, by-ref pointers)
* Registry → `fp.bus.control.v1` (lifecycle events; also signal-only relative to DB truth)

---

# 2) The production paths MF must support (outer reality)

MF participates in these end-to-end routes (without owning their whole story):

* **P1** Standard learning→deploy: EB/Archive + LabelStore → OFS → MF → Registry → DF
* **P2** “Then vs now” evaluation: late labels → OFS as-of rebuild → MF eval/retrain
* **P3** Compatibility-gated rollout: bundle metadata → Registry/DF enforce compatibility (+ degrade mask)
* **P4** Publish retry (no retrain): PASS evidence exists → retry publish idempotently
* **P5** Cross-environment promotion: dev candidate → governed promotion → prod activation (same immutable artifacts)
* **P6** Golden-flow integration: at least one run exercises OFS→MF→Registry in a production-shaped way

---

# 3) The production loops MF must fit into (time passes)

* **L1** Continuous improvement: traffic→labels→OFS→MF→Registry→DF (repeat)
* **L2** Late-truth correction: append-only labels → rebuild → retrain/eval
* **L3** Backfill/rebuild: declared backfill → new derived artifacts/manifests → optional new bundles (no primary truth mutation)
* **L4** Feature evolution: versioned feature pack → rebuild/parity → bundles declare requirements → compatibility enforced
* **L5** Incident/rollback: degrade (fast safety) + registry rollback (identity change) → fix-forward via MF
* **L6** Governance/explainability: decisions cite bundle refs; bundles cite manifests; manifests cite replay basis/as-of → “what changed/why?” always answerable

---

# 4) Environment ladder alignment (how MF stays one platform)

**Invariant:** local/dev/prod share the same graph + semantics. Differences are **envelope-only** via profiles:

* scale, retention/archive availability, security strictness, reliability posture, observability depth

MF uses a **two-profile model**:

* **Wiring profile** (endpoints, timeouts, concurrency, resource ceilings)
* **Policy profile** (admissibility strictness, gate requirements, compatibility requirements, privacy constraints)

Policy/profile revisions must be **pinned and cited** in MF run evidence (no “whatever is active right now”).

---

# 5) MF’s first-layer inner network (subnetworks still opaque)

We partitioned MF into these opaque internal subnetworks (the minimum set that matches outer obligations):

* **MF-A** Run Intake + Idempotency Gate
* **MF-B** Context Resolver (profiles/config → MFContext)
* **MF-C** Input Resolver + Admissibility Gate (J15 enforcement)
* **MF-D** Build Orchestrator (stage machine, resume, retry routing)
* **MF-E** Train/Eval Engine (compute; evidence blobs)
* **MF-F** Evidence + Gates + Bundle Assembly
* **MF-G** Registry Publisher (J16, idempotent publish, conflict detection)
* **MF-H** Evidence Ledger + Artifact I/O (append-only truth plane in `mf/...`)
* **MF-I** Observability + optional Control-Facts (signal plane)

---

# 6) Internal joins we’ve illuminated (what flows between opaque boxes)

## The spine joins (IJ1–IJ6)

These are the main execution DAG:

* **IJ1 A→B**: request admitted → resolve MFContext (policy+wiring+recipe digests)
  *Fail closed if profiles/config can’t be pinned.*

* **IJ2 B→C**: MFContext → admissibility rules applied to input refs
  *No “implicit policy”; C consumes policy as data.*

* **IJ3 C→D**: REJECT or ADMISSIBLE (with input_fingerprint + manifest/materialization digests + basis/as-of + feature pins)
  *REJECT stops; ADMISSIBLE is the only gateway into execution.*

* **IJ4 D→E**: stage execution (TRAIN/EVAL/etc.), deterministic seeds, attempt numbers
  *Stage-shaped; restart-safe.*

* **IJ5 E→F**: evidence pack handoff (artifact refs/digests + eval report ref/digest + evidence_fingerprint)
  *Evidence must be immutable once emitted.*

* **IJ6 F→G**: PASS → publish eligible bundle_candidate (bundle_fingerprint + compatibility descriptor + provenance refs)
  *No PASS → no publish.*

## Cross-cutting rails (IJ7–IJ8)

* **IJ7 {A..G}→H**: **truth plane** (ledger + locators + digests + completion markers)
  *Correctness-critical, fail-closed.*

* **IJ8 {A..G}→I**: **signal plane** (OTLP, optional control facts)
  *Best-effort, never correctness-critical.*

## External adapters (IJ9–IJ13)

* **IJ9 B↔profiles/**: resolve pinned profile revisions/digests (fail-closed)
* **IJ10 C↔ofs/**: resolve/verify manifests and materializations (fail-closed)
* **IJ11 G↔Registry API**: idempotent publish by bundle_fingerprint; conflict hard-stop
* **IJ12 I→OTLP**: telemetry export (best-effort)
* **IJ13 I→control bus**: optional `mf.*` facts (by-ref pointers only; best-effort)

---

# 7) Internal paths we’ve illuminated (production traces)

* **IP1** Happy path: A→B→C→D→E→F(PASS)→G + receipts everywhere
* **IP2** Reject path: A→B→C(REJECT) (no training/publish; failure evidence recorded)
* **IP3** Gate fail path: train/eval completes → F(FAIL) (no publish)
* **IP4** Publish retry: resume → publish-only retry (no retrain)
* **IP5** Duplicate trigger: dedupe via A↔H → return RUNNING/DONE or resume safely
* **IP6** Already published: Registry says ALREADY_PUBLISHED → treat as success
* **IP7** Conflict: Registry returns conflict → hard stop + preserve evidence
* **IP8** Controlled cancel: best-effort cancel, must leave explicit terminal/cancel markers

---

# 8) Internal loops we’ve illuminated (production resilience cycles)

* **IL1 A↔H** request idempotency/dedupe with lease/heartbeat takeover semantics
* **IL2 D↔H** stage resume driven by receipts (never “file exists” inference)
* **IL3 D→E→D** bounded stage retries with attempt numbers recorded
* **IL4 D↔F↔H** re-evaluate/regate/package without retrain (with supersedes if policy rev changes)
* **IL5 G↔Registry (+H)** bounded publish retry; success sticky; conflict terminal; publish pending ≠ training failure
* **IL6 (cross-run via H)** explicit typed supersedes links (append-only lineage; MF never claims ACTIVE authority)
* **IL7 I loop** bounded best-effort telemetry/control-fact emission (never correctness-critical)

---

# 9) Non-joins and “what-nots” we locked (negative space)

## External non-joins (forbidden edges)

MF must not directly:

* read EB/Archive, Label Store, OFP/IEG/DL for training data
* couple to DF/AL/DLA/Case Workbench as a training input path
* activate/rollback (Registry only)

## Substrate/namespace non-joins

MF must not:

* write into `registry/bundles/...`
* mutate `ofs/...`, `profiles/...`, `gov/...`
* overwrite MF truth in place (append-only + supersedes only)

## Internal bypass non-joins

* E must not publish or decide eligibility
* E must not “make artifacts real” without H recording locators/digests
* D must not infer completion from files instead of receipts
* B must not touch data-plane inputs

## Signal-only edges are never truth

* OTLP and control bus emissions can fail without changing correctness.

---

# 10) The receipt chain that makes the whole thing coherent

Across all these joins/paths/loops, MF’s production correctness is anchored by a **receipt chain** in H:

`ContextReceipt → AdmissibilityReceipt → StageReceipts → EvidenceReceipt → GateReceipt → BundleCandidateReceipt → PublishReceipts → TerminalStatus (+ supersedes links)`

If any step can’t be recorded durably, MF must **fail closed** (truth plane rule).

---

## Open decisions we intentionally left open (safe to defer)

We deliberately did *not* pin implementation specifics like:

* exact schemas for receipts/events
* which storage tech implements H/leases
* whether Registry copies artifacts vs references them (so long as Registry remains authoritative)
* whether MF emits optional control facts (IJ13) in v0
* exact compatibility descriptor detail fields (we only pinned “must exist and be enforceable”)

---

This is the full “don’t drift” map we’ve built.
From here, when we go deeper, the rule is: **any internal node design must be justified by which join/path/loop/receipt it serves** — and if a proposed internal behavior violates the non-joins or authority boundaries above, I’ll treat it as out-of-bounds and replace it with a boundary-aligned alternative.

---

Yep — this is exactly the right moment to **pin deployment + environment-ladder laws** for MF’s *internal network* (A–I) **before** we open any boxes.

What follows is **authoritative design guidance** for deployment. It’s not a spec, but it *does* declare the properties Codex must preserve when implementing.

---

# 1) MF deployment shape pins

## D1 — MF is a job, not a service

* MF runs as **scheduled / on-demand jobs** triggered by Run/Operate.
* MF may run **many concurrent jobs** (bounded by profile), but each *run key* must be single-claimer (IL1).

## D2 — Separate truth plane vs signal plane

* **Truth plane (correctness-critical):** MF-H + Registry DB state.
* **Signal plane (best-effort):** OTLP + optional control-bus facts.
* MF must remain correct if OTLP/control-bus are down.

## D3 — Immutable artifact posture everywhere

* Outputs are **write-once**; “updates” happen via **new artifacts + supersedes** (IL6).
* All external interactions are by-ref; artifacts are addressed with **digests** and stored durably.

## D4 — Namespace authority is enforced by permissions

* MF can write only to `mf/...` (and read `ofs/...`, `profiles/...`).
* MF must **not** have permission to write `registry/bundles/...` (Registry owns it).

---

# 2) Minimum runtime components MF depends on (production-real but minimal)

Even though MF is “one component,” deployment needs a few foundational services/substrates:

## S1 — Object store

Used for:

* `ofs/...` (read)
* `mf/...` (write)
* `profiles/...` (read)
* (Registry writes `registry/bundles/...`)

**Required properties:** durable, versionable, supports large blobs, supports read-after-write enough for verification.

## S2 — A transactional “run ledger / lock substrate” for MF-H semantics

Because IL1/IL2 require **atomic claim + leases + stage state**, you need *some* substrate with:

* unique constraint / compare-and-swap semantics for `run_key → train_run_id`
* lease/heartbeat + takeover
* stage attempt recording that’s not vulnerable to concurrent writes

**Designer stance:** this can be implemented as:

* a small DB table, or
* a durable KV with CAS,
  but it must behave transactionally enough to make IL1/IL2 true.

> MF-H’s *artifacts* still live in `mf/...`; this substrate is the “index/coordination truth” that makes resumability and dedupe real.

## S3 — Registry API (external)

MF publishes by API; Registry governs lifecycle/ACTIVE. Publish must be idempotent by bundle fingerprint.

## S4 — OTLP collector (recommended everywhere; depth differs by env)

MF emits traces/metrics/logs with correlation keys.

## S5 — Optional control-bus producer (only if you enable IJ13)

Best-effort “mf.*” facts; never correctness-critical.

---

# 3) Environment ladder knobs you should carry (wiring vs policy)

MF runs under **two profiles** (pinned):

## 3.1 Wiring profile knobs (non-semantic)

These change by environment without changing meaning.

* Endpoints: object store, registry API, OTLP collector, (optional) control bus
* Job execution envelope: CPU/mem, scratch disk, GPU/accelerators if any
* Concurrency: max parallel train runs, worker threads
* Timeouts: manifest resolve, artifact upload, publish attempt
* Retry/backoff defaults (bounded)
* Queue/runner options: preemption behavior, max run duration

**Local:** permissive, high verbosity, small resources
**Dev:** realistic failures, realistic auth, medium resources
**Prod:** strict limits, stable SLOs, conservative retries

## 3.2 Policy profile knobs (semantic strictness; versioned + cited)

These are outcome-affecting and must be promoted with governance posture.

* Input admissibility strictness (manifest completeness, digest enforcement)
* Leakage/as-of requirements (fail closed on ambiguity)
* Gate requirements (mandatory evidence sets, thresholds, PASS criteria)
* Compatibility requirements (fields mandatory; reject if missing)
* Privacy controls (no raw rows in outputs, encryption requirements)
* Retry budgets and which failure classes are retryable vs terminal
* Publish eligibility rules (PASS-only in v0)

**Key pin:** Every MF run must record `policy_rev` (and the digests of all policy/profile artifacts it used).

---

# 4) Deployment implications per internal loop (IL1–IL7)

This is the “why we need those substrates” mapping:

## IL1 (idempotency/dedupe) ⇒ needs atomic claim + lease

* Requirement: only one active claimant for a `run_key`.
* Deployment implication: **lease store** + takeover semantics must exist (DB/KV/CAS).

## IL2 (resume) ⇒ needs stage receipts as authoritative completion

* Requirement: “file exists” is never proof; only receipts.
* Deployment implication: stage receipts must be durable and queryable cheaply (ledger substrate + artifact locators in object store).

## IL3 (retries) ⇒ needs attempt counters and bounded budgets

* Requirement: bounded retries; each attempt recorded.
* Deployment implication: run ledger must persist attempt numbers and retryability classification.

## IL4 (re-eval/regate without retrain) ⇒ needs decoupled stage outputs

* Requirement: training artifacts can exist even if gating/publish failed.
* Deployment implication: artifacts must be addressable independently; orchestrator must be able to schedule “GATE only” and “PUBLISH only.”

## IL5 (publish retry) ⇒ needs idempotent publish keys + durable candidate

* Requirement: publish retry never retrains; success is sticky.
* Deployment implication: bundle candidate + PASS receipt must be durable and reloadable; publish attempts recorded.

## IL6 (supersedes) ⇒ needs append-only lineage

* Requirement: new runs link to old runs without mutation.
* Deployment implication: ledger supports “supersedes edges” and reason references (backfill id / incident id / feature pack rev).

## IL7 (signals) ⇒ bounded buffering, never blocking

* Requirement: telemetry can fail without blocking MF.
* Deployment implication: OTLP exporter must be configured to drop/buffer within strict limits.

---

# 5) Security and governance deployment pins

## SEC1 — Principle of least privilege

* MF runtime identity can:

  * read `ofs/`, `profiles/`
  * write `mf/`
  * call Registry publish API
* It cannot:

  * write `registry/bundles/`
  * mutate `ofs/` or `profiles/` or `gov/`

## SEC2 — Secrets are runtime-injected

* No secrets in artifacts, receipts, logs, or profiles.
* At most, record a “credential id / key id” for audit.

## SEC3 — Promotion and activation remain governed

* MF publishes candidates.
* Activation/rollback is a Registry governance action (separation of duties gets stricter up the ladder).

---

# 6) Observability pins (what must exist before we open nodes)

These aren’t “nice to have” in prod; they’re how you prevent invisible drift.

## OBS1 — Correlation keys are mandatory in all telemetry

Always include:

* `train_run_id`, `request_id`, `input_fingerprint`, `policy_rev`, `mf_build_id`
* `bundle_fingerprint`/`bundle_id` if published

## OBS2 — Minimum metrics that must exist

* run counts (started/completed by outcome class)
* stage durations (train/eval/gate/publish)
* reject counts by reason code
* publish retries and publish conflict count
* “publish pending” backlog (if you allow deferred retries)

## OBS3 — Logs are structured

No giant blobs; use reason codes and refs/digests.

---

# 7) Local/dev/prod “parity tests” you should insist on

Before MF internals are considered “real,” each environment must demonstrate:

* **Local:** at least one full run touches `OFS → MF → Registry` and produces a candidate bundle; also simulate a registry failure and prove **publish-only retry** works.
* **Dev:** prove compatibility reject works (incompatible candidate never becomes resolvable); prove auth boundaries (MF can’t write registry namespace).
* **Prod:** prove governance posture (activation/rollback auditable; MF always cites policy_rev/build id).

---

# 8) The one deployment decision I want pinned before we open MF-A/MF-H

**MF-H needs transactional semantics for run claim + stage state.**

You can implement that with whatever substrate makes sense in your stack, but without it:

* IL1/IL2 become hand-wavy,
* duplicates create drift,
* resumes become unsafe.

So: **declare that MF-H has an atomic coordination layer** (DB/KV/CAS) plus the immutable artifact store (`mf/...`). That’s the cleanest production-ready posture.

---

Yes — illumination shouldn’t change the network; it should only reveal the machinery that *satisfies* the already-frozen joins/paths/loops/receipts. If we stick to that, we won’t get “node A suddenly needs X from node B” surprises — because every node’s IO is already constrained by IJ1–IJ13 and the receipt chain.

## MF nodes (first-layer subnetworks)

* **MF-A** Run Intake + Idempotency Gate
* **MF-B** Context Resolver (profiles/config → MFContext)
* **MF-C** Input Resolver + Admissibility (J15 enforcement)
* **MF-D** Build Orchestrator (stage machine, resume/retry routing)
* **MF-E** Train/Eval Engine (compute)
* **MF-F** Evidence + Gates + Bundle Assembly
* **MF-G** Registry Publisher (J16 publish, idempotent, conflict detection)
* **MF-H** Evidence Ledger + Artifact I/O (truth plane: run/stage receipts + locators + digests)
* **MF-I** Observability + optional Control-Facts (signal plane)

## My recommended illumination order (minimal drift, maximum leverage)

1. **MF-H** (Truth plane) — pins receipts, stage completion rules, append-only/supersedes, artifact locator discipline.
2. **MF-A** (Idempotency) — run_key/train_run_id derivation, claim/lease/takeover, duplicate handling (IL1).
3. **MF-D** (Orchestrator) — stage model + resume rules + retry budgets (IL2/IL3/IL4).
4. **MF-C** (Admissibility) — manifest verification rules and rejection taxonomy (J15; biggest drift risk).
5. **MF-G** (Publisher) — idempotent publish, publish-only retry, conflict handling (IL5, IP4/IP6/IP7).
6. **MF-F** (Gates + Bundle assembly) — evidence packing, PASS/FAIL semantics, bundle fingerprint + compatibility descriptor.
7. **MF-B** (Context resolver) — profile resolution details, policy vs wiring separation, authz decisions (IJ9).
8. **MF-I** (Observability) — correlation keys, minimal metrics/events, best-effort emission (IJ12/IJ13).
9. **MF-E** (Train/Eval engine) — leave last since it’s compute-heavy and least likely to affect network correctness; we just need its evidence contract.

That order builds the “skeleton” (H/A/D) first, then the two biggest external boundary risks (C/G), then the assembly/gating (F), and only then the supporting context/signals/compute.

---

Alright — **MF-H (Truth Plane)** is where we stop hand-waving and make MF *real* under duplicates, restarts, partial failures, and audit demands. This is the machinery that makes **IL1/IL2/IL6** possible and keeps **IJ1–IJ6** honest.

Below is the **internal network inside MF-H** (one level deeper than A–I). These are still “modules,” but now we’re actually exposing what MF-H *does*.

---

# MF-H in one sentence

**MF-H is the authoritative, append-only run ledger + artifact locator registry for MF, backed by a transactional coordination substrate and an immutable artifact store under `mf/...`.**

**Design law:** If MF-H can’t commit, MF must **fail closed** (correctness-critical). Signals live elsewhere.

---

# MF-H internal subnetworks (inside the Truth Plane)

## H1) Run Index and RunKey Resolver

**Role:** canonical mapping `run_key → train_run_id` (dedupe anchor).

* Ensures duplicates do not create new runs.
* Enforces “same pinned inputs → same identity”.

**Outputs:** `train_run_id`, “already exists” verdict, existing status pointer.

---

## H2) Claim, Lease, and Takeover Manager

**Role:** concurrency control for active work on a run.

* Single active claimant at a time (lease token + heartbeat).
* Supports takeover after lease expiry (must be recorded).

**Why it exists:** makes IL1 safe under crashes and multi-worker environments.

---

## H3) Receipt Log (Append-Only Event Store)

**Role:** the ground truth of “what happened” inside MF.

* Stores **typed receipts** (context/admissibility/stage/evidence/gate/publish/supersedes).
* Idempotent append (dedupe keys).

**Design law:** A thing is not “real” until its receipt exists.

---

## H4) State Deriver (Run/Stage View)

**Role:** derives “current state” from receipts.

* Computes run status: `CLAIMED → ADMISSIBLE/REJECTED → RUNNING(stage) → TERMINAL`.
* Computes stage attempt status: started/completed/failed + attempt numbers.

**Why:** avoids “mutable state” drift; state is always explainable from receipts.

---

## H5) Artifact Writer (Object Store Adapter)

**Role:** writes immutable blobs under `mf/...` (or to a staging area) and returns a handle.

* No artifact is considered committed until a locator receipt is appended (see H6).

---

## H6) Digest and Locator Registry

**Role:** content integrity + by-ref discipline.

* Computes/validates digests.
* Produces **ArtifactLocators** (path + digest + size + metadata).
* Appends locator receipts that bind artifacts to a run/stage/evidence pack.

**Design law:** MF-H must be able to prove “these bytes are what we referenced.”

---

## H7) Completion Markers and Commit Protocol

**Role:** makes “stage done” and “run done” unambiguous.

* Stage completion is **receipt-based** (`stage_completed`).
* Optional object-store “_COMPLETE” markers are allowed but **never authoritative without receipts**.

**Why:** prevents “file exists” inference (explicitly forbidden).

---

## H8) Supersedes/Lineage Linker

**Role:** append-only linkage across runs/bundles:

* “new run supersedes old run”
* “new candidate supersedes old candidate”
* typed links + reason refs (backfill id / policy rev change / incident id).

**Design law:** MF-H can express lineage, but **never claims activation authority**.

---

## H9) Query/Resume Interface (Read API for A/D/G)

**Role:** efficient reads for resume and idempotency:

* lookup by `run_key`
* get run summary
* list stage attempts
* fetch latest PASS gate receipt / bundle_candidate receipt
* fetch publish status for a bundle_fingerprint

**Why:** drives IL1/IL2/IL5 without scanning object store.

---

## H10) Orphan & Retention Manager (optional but production-real)

**Role:** handles inevitable orphan blobs (e.g., artifact written but locator receipt never committed).

* Orphans are safe by design (not referenced = not real).
* Cleanup can be TTL/lifecycle rules; MF-H can emit “orphan detected” notes.

---

# MF-H internal join map (how these modules connect)

```
                (transactional coordination substrate)
  +-----------------------------------------------------------+
  |  H1 RunIndex  <->  H2 LeaseMgr  <->  H3 ReceiptLog        |
  |                          |                |               |
  |                          v                v               |
  |                     takeover        H4 StateDeriver       |
  +-----------------------------------------------------------+

                 (object store under mf/...)
  +-----------------------------------------------------------+
  |  H5 ArtifactWriter --> H6 Digest+Locator --> H7 Commit    |
  |            |                    |              |          |
  |            +--------------------+--------------+          |
  +-----------------------------------------------------------+

  H8 SupersedesLinker reads/writes receipts (H3)
  H9 Query/Resume reads RunIndex/Receipts/Derived State (H1/H3/H4)
  H10 Orphan/Retention observes H5/H6/H3 and manages cleanup policy
```

---

# The “commit protocol” MF-H enforces (this is the core machinery)

## 1) Run claim protocol (IL1 foundation)

1. **A asks H9/H1**: “Does `run_key` exist?”
2. If not: **H1 creates mapping** `run_key → train_run_id`
3. **H2 issues lease_token** and records claimant identity
4. **H3 appends `run_claimed` receipt**

**Hard rule:** if any of these steps can’t be durably committed, MF must stop (fail closed).

---

## 2) Stage protocol (IL2/IL3 foundation)

To start a stage:

* **H3 append** `stage_started(stage_id, attempt_no, stage_seed, lease_token)`
  To complete a stage:
* **H3 append** `stage_completed(...)` with output locators (or pointers to evidence pack)
  To fail a stage:
* **H3 append** `stage_failed(...)` with retryability reason codes

**Hard rule:** stage completion is defined by receipts, not by files.

---

## 3) Artifact protocol (digest + locator discipline)

To commit an artifact safely (write-once semantics):

1. **H5 writes** artifact blob to object store (optionally to a staging path)
2. **H6 computes digest** and constructs `ArtifactLocator`
3. **H3 appends locator receipt** binding locator to `(train_run_id, stage_id, attempt_no, artifact_kind)`
4. Optional: **H7 finalizes** (e.g., write a small commit marker or move from staging → final path)

**Hard rule:** Artifacts not referenced by a locator receipt are **orphans** and must not affect correctness.

---

# What MF-H considers “truth” (receipt chain is the spine)

MF-H is the authoritative store for this chain:

`ContextReceipt → AdmissibilityReceipt → StageReceipts → EvidenceReceipt → GateReceipt → BundleCandidateReceipt → PublishReceipts → TerminalStatus (+ SupersedesLinks)`

This chain is what prevents internal nodes from “requiring something different later.” If a node needs something, it must come through **a receipt/locator that already exists**.

---

# What each other MF node is allowed to do with MF-H (boundary discipline)

* **MF-A**: uses H1/H2/H9 for `run_key` lookup + claim + lease + duplicate resolution.
* **MF-B**: appends *context receipts* (resolved digests/revs, policy_rev, build_id).
* **MF-C**: appends *admissibility receipts* (ADMISSIBLE/REJECT + reasons + input_fingerprint).
* **MF-D**: drives stage receipts via H3/H4/H9 (resume is ledger-driven).
* **MF-E**: may request H5/H6 for artifact writes, but **must not treat them as real** until locators are recorded.
* **MF-F**: appends evidence/gate/bundle_candidate receipts.
* **MF-G**: appends publish attempt/result receipts; consults H9 for publish-only retry.
* **MF-I**: does **not** feed MF-H for correctness (signals only).

---

# Deployment pins for MF-H (so Codex implements the right shape)

## MF-H must have two physical backends

1. **Transactional coordination substrate** (DB/KV with CAS/unique constraints)

   * run_key uniqueness
   * lease + takeover semantics
   * idempotent receipt append keys

2. **Object store** for immutable blobs under `mf/...`

   * large artifacts
   * evidence reports
   * bundle candidates (pre-registry)

**Local/dev/prod** can swap implementations, but these semantics must hold.

## Permissions are part of correctness

* MF identity can write `mf/...` only.
* MF identity cannot write `registry/bundles/...` (Registry owns that namespace).
* This prevents “shadow registry” drift by construction.

---

# Explicit non-joins inside MF-H (what it must not do)

* MF-H does **not** decide PASS/FAIL (records receipts only).
* MF-H does **not** publish to Registry (records publish receipts only).
* MF-H does **not** infer completion from files.
* MF-H does **not** read training datasets; it only handles manifests/locators/evidence blobs.

---

If you want the next illumination step, the natural follow-on is **MF-A (Run Intake/Idempotency)** because it directly exercises H1/H2/H9 and will force us to pin the exact **RunKey derivation**, lease rules, and duplicate semantics with zero ambiguity.

---

Got it — we’re now illuminating **MF-A (Run Intake + Idempotency Gate)** and exposing the machinery inside it (still as internal modules, but no longer hand-wavy).

MF-A is the **front door** that makes IL1 (dedupe) real and prevents every other node from drifting.

---

# MF-A in one sentence

**MF-A turns a TrainBuildRequest into a single, durable, uniquely-owned training run (or a stable answer about an existing one), using deterministic keys + MF-H claims/leases, without ever choosing data or mutating truth.**

---

# MF-A internal subnetworks (inside the Idempotency Gate)

## A1) Request Intake and Canonicalizer

**Role:** accept the trigger and normalize it into a canonical form.

* Validates required fields exist (intent, manifest refs, profile refs, caller principal).
* Canonicalizes ordering (e.g., sorts manifest refs, normalizes ref formats).
* Enforces “by-ref only” posture (no raw data payloads).

**Output:** `CanonicalTrainRequest`

---

## A2) Key Builder (TrainRunKey constructor)

**Role:** compute the deterministic identity of “this run” **from pinned inputs**.

### What it produces

* **TrainRunKey**: the canonical identity of the run
* **train_run_id = hash(TrainRunKey)**: the stable run identifier

### What TrainRunKey must include (authoritative)

* `intent` (train | eval-only | backfill-retrain | regression-check | publish-only)
* **dataset identity**: ordered set of `DatasetManifestRef` *with their digests* (or a digest of each manifest object)
* **profile identity**:

  * `policy_profile_digest`
  * `training_recipe_digest`
  * (optionally) `wiring_profile_digest` *only if it affects semantics* (default: no)
* `mf_build_id` (so “same data + same recipe, different MF build” is a distinct run)
* any explicit “scope key” (e.g., model_family_id / decision surface) if not already implied by training recipe

**Design law:** **train_run_id is never time-derived**.

**Output:** `TrainRunKey`, `train_run_id`

---

## A3) Claim and Lease Client (IL1 machinery)

**Role:** ensure only one worker “owns” the run at a time.

* Calls MF-H to:

  * lookup existing run by TrainRunKey,
  * create mapping if absent,
  * acquire a **lease_token** (with TTL + heartbeat),
  * record claimant identity.

**Output:** `RunClaimVerdict {NEW_CLAIM | EXISTING | TAKEOVER}` + `lease_token`

---

## A4) Duplicate Resolver (stable answers for retries)

**Role:** if the run already exists, decide what MF returns **without starting duplicate work**.

It reads derived state from MF-H and returns one of:

* `RUNNING(stage=..., last_attempt=...)`
* `DONE(success published | done fail | rejected)`
* `PUBLISH_PENDING` (PASS exists, publish not yet successful)
* `RESUMABLE` (claim exists but run not progressing; lease expired; takeover allowed)

**Output:** `IdempotencyResponse`

---

## A5) Resume / Dispatch Router

**Role:** decide the *next internal hop* after claim.

* If NEW_CLAIM: proceed into IJ1 (A→B) and the rest of the spine.
* If EXISTING and RUNNING: return status (do not proceed).
* If EXISTING and DONE: return outcome (do not proceed).
* If RESUMABLE/TAKEOVER: reacquire lease and proceed to resume via MF-D using ledger state.
* If PUBLISH_PENDING: route to publish-only path (MF-D → MF-G), not retrain.

**Output:** `NextAction {PROCEED, RETURN_STATUS, RESUME_FULL, RESUME_PUBLISH_ONLY}`

---

## A6) Request Alias Guard (request_id conflict detector)

**Role:** prevent the “same request_id means two different runs” disaster.

* Ensures **a request_id can only ever map to one train_run_id**.
* If the same request_id arrives with different TrainRunKey → **hard conflict**.

This is a small thing, but it prevents a nasty class of governance/audit confusion.

**Output:** `OK | CONFLICT(request_id_reused)`

---

## A7) Cancel / Control Hook (optional, ops-friendly)

**Role:** accept cancel intents (or priority changes) and record them.

* Cancel is best-effort and must be ledger-visible.
* Cancel never deletes anything; it just sets terminal/cancel-pending markers.

**Output:** `CancelReceiptWritten`

---

# MF-A internal join map (inside the node)

```
TrainBuildRequest
    |
    v
 [A1 Canonicalize] ---> [A2 Build TrainRunKey + train_run_id] ---> [A6 request_id guard]
                                                            |
                                                            v
                                                     [A3 Claim+Lease via MF-H]
                                                            |
                                                            v
                                                   [A4 Duplicate Resolver]
                                                            |
                                                            v
                                                   [A5 Dispatch Router]
                                                            |
                               +----------------------------+--------------------------+
                               |                            |                          |
                               v                            v                          v
                         PROCEED (IJ1)              RETURN_STATUS                RESUME (full/publish-only)
```

---

# The two key loops MF-A must satisfy (production reality)

## IL1 (Idempotency) is enforced by A3/A4 against MF-H

* **Lookup by TrainRunKey**
* **Claim/lease**
* **Duplicate resolution**
* **Takeover on lease expiry** (recorded)

## “Request retries” are safe regardless of why they occur

* If caller times out: repeat trigger returns RUNNING/DONE/PUBLISH_PENDING.
* If MF crashes: repeat trigger returns RESUMABLE and resumes from ledger.

---

# What MF-A is explicitly *not allowed* to do (non-joins, enforced here)

MF-A must never:

* choose training data (“latest dataset”, scan `ofs/…`, read EB/Archive/Label Store)
* infer identity from wall clock
* start a second run because status is unclear
* bypass MF-H and “just run it”
* mutate any existing receipts/artifacts (append-only only)

MF-A is a **gate**, not a builder.

---

# Receipts MF-A forces into MF-H (truth plane requirements)

MF-A must ensure the following are recorded durably (or fail closed):

1. `request_received(request_id, caller, intent, refs summary)`
2. `train_run_key_recorded(train_run_id, TrainRunKey digest)`
3. `run_claimed(train_run_id, claimant_id, lease_token, lease_ttl)`
4. On duplicates: `duplicate_request_observed(request_id → train_run_id)`
5. On takeover: `lease_takeover(old_claimant → new_claimant, reason)`
6. On conflict: `request_id_conflict(request_id, old_train_run_id, new_train_run_id)` (terminal)

These are the “spine receipts” that make every later path deterministic and auditable.

---

# Environment ladder knobs that matter specifically for MF-A

Same semantics everywhere; knobs vary by profile:

* **lease TTL + heartbeat interval** (short local, realistic dev, conservative prod)
* **takeover policy** (how long before takeover allowed)
* **max claim attempts** (to avoid thundering herds)
* **dedupe mode**:

  * default: dedupe by TrainRunKey (strong)
  * request_id guard always on (conflict detection)
* **response verbosity** (local can include more debug; prod returns reason codes + IDs)

---

# Three canonical MF-A traces (sanity anchors)

### Trace A: New request

A1→A2→A6 OK→A3 NEW_CLAIM→A5 PROCEED (into IJ1)

### Trace B: Duplicate while running

A1→A2→A6 OK→A3 EXISTING→A4 RUNNING→A5 RETURN_STATUS

### Trace C: Crash + takeover

A1→A2→A6 OK→A3 TAKEOVER→A4 RESUMABLE→A5 RESUME_FULL (MF-D consults ledger)

---

If you want the clean next illumination, we should open **MF-D (Build Orchestrator)** next, because MF-A’s outputs (“PROCEED vs RESUME_FULL vs RESUME_PUBLISH_ONLY”) force MF-D’s internal stage machine and resume logic.

---

Got it — we’re illuminating **MF-D (Build Orchestrator)** now. This is the machinery that makes:

* **IL2** stage resume safe,
* **IL3** retries bounded and recorded,
* **IL4** “re-eval/regate/package without retrain” possible,
* and it’s the piece that guarantees the MF spine (IJ4/IJ5/IJ6) stays **stage-shaped** rather than “one big blob”.

Everything here is still **inside MF-D**, but we are no longer hand-waving. We’re revealing MF-D’s internal modules and their interactions.

---

# MF-D in one sentence

**MF-D turns an admitted run (`train_run_id`, `input_fingerprint`, MFContext) into a deterministic stage plan, executes stages with restart-safe receipts, and routes to the correct continuation path (full run vs publish-only vs re-gate) based solely on MF-H ledger truth and policy.**

**Design law:** MF-D never infers completion from files; only MF-H receipts define truth.

---

# MF-D internal subnetworks (inside the Orchestrator)

## D1) Plan Constructor (Stage Graph Builder)

**Role:** decide which stages exist for this run based on `intent` and policy.
It builds a stage DAG like:

* `RESOLVE_CONTEXT` (already done by B, but may be represented for tracing)
* `ADMISSIBILITY` (already done by C, but can be reflected)
* `TRAIN`
* `EVAL`
* `GATE`
* `PACKAGE`
* `PUBLISH`
* `TERMINATE`

**Outputs:** `StagePlan` (ordered DAG) + stage invariants.

**Key:** StagePlan is **deterministic** given (intent + policy_rev).

---

## D2) Ledger Reader / State Sampler (Truth intake)

**Role:** read MF-H’s derived state and receipts for:

* run status,
* stage statuses,
* latest attempt numbers,
* existence of evidence/gate/bundle receipts,
* publish status for bundle_fingerprint.

This module is the “eyes” of resume logic.

---

## D3) Resume Planner (IL2 engine)

**Role:** compute the next runnable stage(s) from StagePlan + ledger truth.

It produces one of these **resume modes**:

* `FRESH_RUN` (nothing completed, run just claimed)
* `RESUME_FROM(stage=X)` (some stages complete)
* `PUBLISH_ONLY` (PASS + bundle_candidate exist; publish incomplete)
* `GATE_ONLY` (TRAIN artifacts exist; gate/bundle missing or superseded)
* `EVAL_ONLY` (TRAIN exists; eval missing/invalid)
* `TERMINAL` (already done; no further work)

**Output:** `ResumePlan` (next stage + skip list).

---

## D4) Stage Runner (Execution Dispatcher)

**Role:** execute one stage at a time by calling the appropriate downstream node:

* `TRAIN/EVAL` → MF-E
* `GATE/PACKAGE` → MF-F
* `PUBLISH` → MF-G

This is where IJ4/IJ5/IJ6 are scheduled, but still via receipts.

---

## D5) Retry Controller (IL3 engine)

**Role:** decide if a failed stage is retryable, and how.

* Consults policy retry budgets (per stage).
* Assigns next attempt number.
* Applies backoff and optional resource escalation rules (wiring profile).

**Output:** `RetryDecision {RETRY_NOW | RETRY_LATER | FAIL_RUN}`

---

## D6) Evidence Reuse Router (IL4 engine)

**Role:** enable “don’t retrain if you don’t have to.”
Given ledger truth, it decides when to:

* reuse TRAIN artifacts for EVAL/GATE,
* reuse EVAL evidence for GATE,
* reuse PASS + bundle_candidate for publish-only retries.

This module is what makes IP4 and IL4 legitimate and safe.

---

## D7) Deterministic Seed & Attempt Allocator

**Role:** derive deterministic seeds for stage invocations, and ensure attempt numbering is monotonic and recorded.

* `stage_seed = f(train_run_id, stage_id, attempt_no)`
* Ensures `attempt_no` is ledger-consistent (never reuse same attempt id).

---

## D8) Terminalizer (Outcome Classifier)

**Role:** decide and record terminal outcomes:

* `REJECTED_INPUTS`
* `FAILED_GATES`
* `FAILED_CONFLICT`
* `FAILED_RETRY_EXHAUSTED`
* `CANCELED`
* `SUCCESS_PUBLISHED`
* `PUBLISH_PENDING` (not terminal, but a stable state)

This module makes MF’s outward status stable and queryable.

---

## D9) Cancellation / Preemption Handler (optional ops realism)

**Role:** handle cancel requests and preemption:

* stop scheduling new stages,
* mark cancel pending,
* cooperate with MF-E if it supports interruption.

Never deletes artifacts; always records receipts.

---

# MF-D internal join map (inside the Orchestrator)

```
Inputs (from A/C/B/H):
  train_run_id + lease_token + MFContext + input_fingerprint

         +------------------+
         | D2 Ledger Reader |
         +------------------+
                   |
                   v
         +------------------+       +----------------------+
         | D1 Plan Builder  |-----> | D3 Resume Planner    |
         +------------------+       +----------------------+
                                            |
                                            v
     +------------------+     +------------------+     +------------------+
     | D4 Stage Runner  |<----| D5 Retry Ctrl    |<----| D7 Seed/Attempt  |
     +------------------+     +------------------+     +------------------+
            |   |   |
            |   |   +--> call MF-G (PUBLISH)
            |   +------> call MF-F (GATE/PACKAGE)
            +----------> call MF-E (TRAIN/EVAL)
                    |
                    v
              +------------------+
              | D8 Terminalizer  |
              +------------------+
                    ^
                    |
              +------------------+
              | D6 EvidenceReuse |
              +------------------+

(Cancel path)
  Run/Operate cancel -> D9 -> D8 + receipts in H
```

---

# The orchestrator’s “stage contract” (what MF-D assumes from other nodes)

MF-D does **not** need to know internals of E/F/G, only this:

## For MF-E (TRAIN/EVAL)

* accepts (train_run_id, stage_id, attempt_no, stage_seed, pinned input refs)
* returns by-ref artifact/eval refs with digests
* never chooses new inputs

## For MF-F (GATE/PACKAGE)

* accepts evidence packs (refs/digests) + policy context
* returns PASS/FAIL gate receipt + bundle_candidate receipt if PASS

## For MF-G (PUBLISH)

* accepts bundle_candidate + bundle_fingerprint
* returns publish result (PUBLISHED/ALREADY_PUBLISHED/REJECTED/CONFLICT/TRANSIENT_FAIL)

Everything else is internal.

---

# How MF-D implements the key loops (in plain mechanics)

## IL2: Resume loop (ledger-driven)

1. D2 reads receipts and derives stage statuses.
2. D3 chooses the earliest not-completed required stage per plan.
3. D4 runs that stage, recording `stage_started` / `stage_completed`.
4. Repeat until terminal or blocked.

**Hard rule:** no receipt → stage not done.

---

## IL3: Retry loop (bounded, reason-coded)

When a stage fails:

1. D5 classifies failure using reason codes (retryable vs terminal).
2. If retryable and budget remains:

   * increment attempt_no
   * apply backoff
   * re-run stage
3. Else:

   * D8 marks run FAILED_RETRY_EXHAUSTED (or stage-specific terminal)

**Hard rule:** retries must be recorded; attempt numbers monotonic.

---

## IL4: Evidence reuse loop (no retrain)

D6 checks H for reusable outputs:

* If TRAIN artifacts exist but EVAL missing → run EVAL only
* If EVAL exists but gate missing → run GATE/PACKAGE only
* If PASS + bundle_candidate exist but publish missing → PUBLISH only
* If policy_rev changed and re-gating is invoked → produce new gate receipt that **supersedes** prior

**Hard rule:** reuse is allowed only if the evidence chain is intact and ledger-pinned.

---

# The “resume mode table” (production-ready behaviors)

| Ledger truth found in H                            | Resume mode        | Next stage              |
| -------------------------------------------------- | ------------------ | ----------------------- |
| nothing beyond claim                               | FRESH_RUN          | TRAIN                   |
| TRAIN complete, EVAL missing                       | EVAL_ONLY          | EVAL                    |
| EVAL complete, gate missing                        | GATE_ONLY          | GATE/PACKAGE            |
| PASS + bundle_candidate exists, publish incomplete | PUBLISH_ONLY       | PUBLISH                 |
| published already recorded                         | TERMINAL           | none                    |
| stage_started exists but no stage_completed        | RESUME_FROM(stage) | same stage next attempt |

This table is what prevents surprises when we open E/F/G.

---

# Failure and terminal semantics MF-D owns (authoritative)

MF-D must distinguish:

* **FAILED_GATES** (valid run, not deployable)
* **PUBLISH_PENDING** (deployable candidate exists, publish not yet succeeded)
* **FAILED_PUBLISH_EXHAUSTED** (publish blocked beyond retry budget; candidate remains)
* **FAILED_TRANSIENT** is not a terminal class; it lives as stage_failed with retry plan
* **CANCELED** is explicit and receipt-backed

This keeps ops and automation clean.

---

# Environment ladder knobs that matter to MF-D

Same semantics everywhere; profiles adjust:

* per-stage retry budgets (local higher, prod conservative)
* backoff schedules
* resource escalation rules
* max concurrent stage runners
* cancellation behavior (more permissive locally)

---

# Non-joins MF-D must enforce (so it can’t drift)

MF-D must not:

* read `ofs/...` directly (that’s C’s role)
* infer stage completion from files
* “skip gates” or “publish without PASS”
* trigger retraining when publish failed (publish-only exists)

---

If you want the next node to illuminate, the natural continuation is **MF-C (Admissibility)** or **MF-G (Publisher)**.
My recommendation: **MF-C next** (it’s the biggest drift risk at the data boundary), then MF-G (publish correctness), then MF-F (gates/bundle assembly).

---

Understood — we’re illuminating **MF-C (Input Resolver + Admissibility Gate)** and exposing the machinery inside it. This is the **J15 enforcement core**: it decides whether MF is allowed to proceed past “pinned, reproducible inputs” or must stop.

MF-C stays **boundary-pure**: it **doesn’t choose data**, it **doesn’t scan**, it **doesn’t repair**, it **doesn’t reach into EB/LabelStore**, and it **fails closed** on anything that would introduce drift.

---

# MF-C in one sentence

**MF-C resolves the DatasetManifest set (by-ref), verifies integrity and completeness (basis/as-of/feature pins + digests), enforces policy admissibility, computes a deterministic `input_fingerprint`, and emits ADMISSIBLE or REJECTED with an explicit reason taxonomy — recording everything via MF-H.**

---

# MF-C internal subnetworks (the machinery inside)

## C1) Input Ref Canonicalizer

**Role:** normalize the “manifest set” into a canonical, deterministic list.

* Sort/normalize `DatasetManifestRef[]` (stable ordering).
* Remove duplicates (or flag duplicates if policy says “reject duplicates”).
* Validate ref syntax (no relative paths, no wildcards, no “latest”).

**Output:** `CanonicalManifestSet`

**Non-join enforced here:** MF-C **must not** enumerate `ofs/` to find alternatives.

---

## C2) Manifest Fetcher (bounded I/O retrier)

**Role:** fetch manifest objects from `ofs/...` by explicit ref.

* Performs bounded retries for transient object store failures.
* Distinguishes:

  * **Hard missing** (ref doesn’t exist)
  * **Transient unavailable** (timeout/5xx)
  * **Access denied** (policy/auth)

**Output:** `ManifestBytes[]` + fetch status per ref

> This is where we keep “transient” separate from “invalid.”

---

## C3) Manifest Integrity Verifier (digest + immutability)

**Role:** verify that the manifest is exactly what was referenced.

* If the request provides a manifest digest: verify it matches.
* Otherwise compute digest and **pin it** (it becomes part of admissibility receipt).
* Enforce “manifest objects are immutable”: if later reads disagree, that’s conflict.

**Output:** `ResolvedManifest {ref, digest, parsed}`

**Hard line:** digest mismatch is a **HARD REJECT** (drift/corruption).

---

## C4) Manifest Semantics Validator (the “no hidden time travel” checks)

**Role:** ensure the manifest is complete enough to be reproducible and leakage-safe.
MF-C requires (minimum, v0):

* **Replay basis is explicit** (offset/checkpoint basis, or time window anchored to offsets)
* **As-of boundary is explicit** (what truth was visible at build time)
* **Feature version pins are explicit** (single authoritative feature pack/version set)
* **Join keys + scope are explicit** (entity scope / dataset kind)
* **Materialization references exist** (the manifest must point to the actual dataset blobs by-ref)

**Output:** `ManifestSemanticsSummary` + pass/fail per manifest

**Hard line:** missing basis/as-of/feature pins is a **HARD REJECT** (no “warn and continue”).

---

## C5) Cross-Manifest Consistency Checker

**Role:** ensure the *set* of manifests can legitimately be used together.
Typical rules (policy-driven, but v0 defaults are strict):

* All manifests in the set agree on **feature version pins**.
* All manifests agree on **as-of posture** (or explicitly declare “train/val/test are separate cuts”).
* All manifests belong to the same **dataset family / training recipe scope** (e.g., same model_family_id if declared).
* No conflicting schema/shape declarations for the same dataset role.

**Output:** `ManifestSetConsistencyVerdict`

**Why this matters:** prevents subtle drift where train and eval were built under different feature definitions or time cuts.

---

## C6) Materialization Resolver + Integrity Checker

**Role:** resolve the blobs referenced by the manifest and verify integrity.

* For each materialization ref:

  * existence check
  * digest verification (or pin digest if the manifest includes it)
  * optional: lightweight sanity (size > 0, expected file type), **never** row inspection

**Output:** `MaterializationLocators[]` (ref + digest + size + metadata)

**Hard line:** missing referenced materialization or digest mismatch is a **HARD REJECT**.

---

## C7) Proof / Receipt Validator (No-PASS-No-Read for datasets)

**Role:** enforce that the dataset was produced/validated under an auditable posture.

* Require a dataset build receipt / PASS evidence from OFS (if policy requires — I’m pinning it as default for v0).
* Verify the receipt binds to:

  * manifest digest
  * policy/profile revision used by OFS (if present)
  * build id/backfill id (if applicable)

**Output:** `DatasetProofVerdict` + proof refs

**Hard line:** missing required PASS proof is a **HARD REJECT** (consistent with platform “no PASS → no read”).

---

## C8) Policy Admissibility Filter

**Role:** apply MF policy profile rules on top of “is it reproducible?”
Examples of admissibility rules (policy-knobs, not implementation):

* dataset kind allowed for this training recipe
* max window size / max age
* privacy classification allowed
* required fields present
* feature pack versions allowed/blocked

**Output:** `PolicyVerdict` (ALLOW/REJECT + reasons)

---

## C9) Input Fingerprint Builder (data identity anchor)

**Role:** compute a deterministic identity for “the input dataset set.”

* `input_fingerprint = H("mf_input_v1" + ordered(manifest_digest list) + optional role tags)`
* Optionally include a digest summary of materializations **only if** not already implied by manifest digest.

**Output:** `input_fingerprint`

**Design intent:** `input_fingerprint` is **data-set identity**, not “run identity” (run identity is MF-A’s domain).

---

## C10) Verdict Composer + Evidence Packager (IJ3 output)

**Role:** produce one of:

### ADMISSIBLE output (to MF-D)

* `input_fingerprint`
* `resolved_manifest_set` (refs + digests + semantics summary pointers)
* `materialization_locators` (refs + digests)
* `feature_version_pins`
* `basis/as_of summaries`
* `dataset_proof_refs` (PASS receipts)
* `constraints` (privacy/export limits)

### REJECTED output (to MF-D / upstream)

* `reject_class: HARD | TRANSIENT`
* `retryable: boolean`
* `reason_codes[]`
* `offending_refs[]` + expected/observed digests where relevant

This is where we avoid conflating “invalid inputs” with “store is down.”

---

# MF-C internal join map (inside the node)

```
DatasetManifestRefs + MFContext(policy)
        |
        v
 [C1 Canonicalize]
        |
        v
 [C2 Fetch] -> (transient?) -> REJECT(TRANSIENT)
        |
        v
 [C3 Digest Verify]
        |
        v
 [C4 Semantics Validate] ----> REJECT(HARD)
        |
        v
 [C5 Set Consistency]  ------> REJECT(HARD)
        |
        v
 [C6 Materialization Verify] -> REJECT(HARD/TRANSIENT)
        |
        v
 [C7 PASS Proof Validate] ----> REJECT(HARD)
        |
        v
 [C8 Policy Filter] ----------> REJECT(HARD)
        |
        v
 [C9 Build input_fingerprint]
        |
        v
 [C10 Emit ADMISSIBLE]  ---> MF-D
```

---

# The rejection taxonomy MF-C must emit (so nothing hides)

I’m pinning these **reason code families** as the minimum vocabulary:

### Reference / resolution

* `REF_INVALID_FORMAT`
* `REF_NOT_FOUND`
* `REF_ACCESS_DENIED`
* `RESOLVE_TIMEOUT_TRANSIENT`

### Digest / integrity

* `MANIFEST_DIGEST_MISMATCH`
* `MATERIALIZATION_DIGEST_MISMATCH`
* `IMMUTABILITY_CONFLICT` (same ref, different bytes)

### Semantics completeness

* `MISSING_REPLAY_BASIS`
* `MISSING_AS_OF_BOUNDARY`
* `MISSING_FEATURE_VERSION_PINS`
* `MISSING_JOIN_KEYS_OR_SCOPE`

### Cross-set consistency

* `FEATURE_PINS_INCONSISTENT_ACROSS_SET`
* `AS_OF_INCONSISTENT_ACROSS_SET`
* `SCHEMA_INCOMPATIBLE_WITH_RECIPE`

### Proof / governance

* `MISSING_DATASET_PASS_PROOF`
* `PASS_PROOF_DOES_NOT_BIND_MANIFEST`

### Policy constraints

* `POLICY_DISALLOWS_DATASET_KIND`
* `POLICY_WINDOW_TOO_LARGE`
* `POLICY_PRIVACY_CLASS_DISALLOWED`
* `POLICY_FEATURE_PACK_BLOCKED`

Each REJECT includes: `(class=HARD|TRANSIENT, retryable, codes[], offending_refs[])`.

---

# MF-C’s interaction with MF-H (truth plane obligations)

MF-C must ensure MF-H has durable receipts for:

1. `manifest_resolution_receipt`

   * ref + digest per manifest
   * fetch outcomes for transparency

2. `materialization_locator_receipts`

   * ref + digest + size per blob

3. `admissibility_receipt`

   * verdict (ADMISSIBLE/REJECTED)
   * input_fingerprint (if admissible)
   * reason codes (if rejected)
   * pointers to proof receipts (if required)

**Hard rule:** MF-D is not allowed to proceed unless MF-H contains `admissibility_receipt=ADMISSIBLE`.

---

# Environment ladder knobs for MF-C (what can vary without semantic drift)

Allowed to vary by policy/wiring profile:

* bounded retry parameters for **transient fetch failures** (timeouts/backoff)
* extra “deep” validations (e.g., schema conformance depth, optional row-count checks)
  **But not** the existence of basis/as-of/feature pins/digest verification

Not allowed to vary (semantic invariants):

* manifests-only intake
* no scanning/latest
* basis/as-of required
* feature pins required
* digest integrity required
* PASS proof required (default v0)

---

# Non-joins MF-C enforces (explicitly)

MF-C must never:

* read EB/Archive/LabelStore to fill missing manifest fields
* “repair” a manifest or synthesize basis/as-of/pins
* choose alternative manifests/materializations
* treat “file exists” as integrity proof without digest binding

---

If you want the next illumination in the sequence we planned, the best next node is **MF-G (Registry Publisher)** (because publish idempotency + conflict handling + publish-pending posture are the next biggest drift risk), then **MF-F** (gates/bundle assembly).

---

Understood — we’re illuminating **MF-G (Registry Publisher)** and exposing the machinery inside it.

MF-G is where we “touch the outside world” in the most dangerous way: if this is sloppy, you get **duplicate publishes, silent drift, or broken audit**. So MF-G is deliberately **narrow, deterministic, receipt-driven**, and **never an activation authority**.

---

# MF-G in one sentence

**MF-G takes a PASS-eligible `bundle_candidate` (anchored by `bundle_fingerprint`) and performs an idempotent, conflict-detecting publish to the Registry, recording every attempt and outcome in MF-H so publish-only retry (IL5/IP4) is safe and deterministic.**

**Design law:** MF-G can publish candidates; **Registry governs lifecycle + ACTIVE**. MF-G never activates.

---

# MF-G internal subnetworks (the machinery inside)

## G1) Publish Preflight Guard

**Role:** refuse illegal publishes before touching Registry.

* Requires: **GateReceipt = PASS** exists and matches the `bundle_candidate`.
* Requires: `bundle_fingerprint` exists and is stable.
* Requires: compatibility descriptor present (minimum required fields).
* Requires: provenance pointers present (manifests, policy_rev, mf_build_id, evidence refs).

**Hard fail** if any are missing.
This prevents “publish half-truth” drift.

---

## G2) Candidate Loader + Self-Consistency Validator

**Role:** load the publish payload and verify internal consistency.

* Loads bundle_candidate manifest (typically from `mf/...` via locator).
* Verifies:

  * `bundle_fingerprint == hash(bundle contents refs+digests+compat+provenance)`
  * GateReceipt points to the same evidence pack
  * The candidate references only immutable artifacts (digests included)

**Hard fail** on mismatch (that’s an internal determinism break).

---

## G3) Publish Session Lock (anti-thundering-herd)

**Role:** ensure only one publish loop is active per `(train_run_id, bundle_fingerprint)` from MF’s perspective.

* Uses MF-H stage receipts as the lock boundary:

  * `stage_started(PUBLISH, attempt_no, lease_token)` is the lock claim.
* If another worker sees publish in progress under an active lease, it returns RUNNING rather than spamming Registry.

**Note:** Registry idempotency still protects correctness, but this avoids unnecessary load and confusion.

---

## G4) Registry Client Adapter (IJ11 implementation)

**Role:** the only module that actually calls Registry.

* Calls **PublishBundle** with idempotency key = `bundle_fingerprint`.
* Payload is **by-ref + digests**, never bulk embedded artifacts.
* Never calls any “activate/promote/rollback” endpoints.

It also supports a **Status Probe** call (read-only):

* `GetBundleStatus(bundle_fingerprint or bundle_id)` used only for recovery after timeouts.

---

## G5) Outcome Normalizer (result classification)

**Role:** normalize Registry responses into MF’s canonical outcomes:

* `PUBLISHED(bundle_id, state, registry_receipt_ref)`
* `ALREADY_PUBLISHED(bundle_id, state)`
* `REJECTED(reason_codes[])` (validation/policy)
* `CONFLICT(details)` (identity mismatch)
* `TRANSIENT_FAIL(reason_codes[])` (timeouts/5xx/network)
* `UNKNOWN_OUTCOME` (client timed out; Registry may have accepted)

This is what makes IL5 bounded and deterministic.

---

## G6) Retry Scheduler (IL5 engine)

**Role:** decide whether and how to retry publishing.

* Reads retry budget rules from MFContext policy.
* Applies bounded backoff.
* Distinguishes:

  * **retryable**: transient failures, unknown outcome
  * **terminal**: reject, conflict

**Key pin:** retrying publish must **never** trigger retraining.

---

## G7) Conflict Escalator (hard stop path)

**Role:** handle the “this should never happen” outcomes.

* On `CONFLICT`, freezes the run as `FAILED_CONFLICT`.
* Produces an “incident handle” (receipt id) so ops can triage.
* Preserves all evidence and prevents further publish attempts.

---

## G8) Receipt & State Writer (MF-H adapter)

**Role:** write the publish attempt chain into MF-H (truth plane).

* Writes:

  * publish stage start/end
  * attempt receipts
  * result receipts
  * terminal status transitions (`SUCCESS_PUBLISHED` or `PUBLISH_PENDING`)

**Hard rule:** if MF-H cannot record, MF-G must fail closed (publish is correctness-critical).

---

## G9) Recovery Resolver (timeout / unknown outcome handler)

**Role:** resolve uncertainty safely.
If a publish call times out:

1. Record `UNKNOWN_OUTCOME` in MF-H.
2. Probe Registry status (if available).
3. If status says present → record `ALREADY_PUBLISHED/PUBLISHED`.
4. If status unknown → treat as retryable and re-publish idempotently using `bundle_fingerprint`.

This keeps “did it publish?” from becoming a human guessing game.

---

## G10) Telemetry/Signals Hook (to MF-I)

**Role:** emit best-effort signals:

* publish attempts
* retries
* conflicts
* timeouts
* eventual success

**Never correctness-critical.** Truth is in MF-H + Registry DB.

---

# MF-G internal join map (inside the node)

```
Inputs: bundle_candidate_ref + PASS gate receipt ref + MFContext + train_run_id

   [G1 Preflight Guard]
            |
            v
   [G2 Candidate Validator]---- mismatch ---> [G7 Conflict Escalator]
            |
            v
   [G3 Publish Session Lock]  (via MF-H stage_started)
            |
            v
   [G4 Registry Client] <--> Registry API (Publish / Status)
            |
            v
   [G5 Outcome Normalizer]
            |
            +---- terminal reject/conflict ---> [G7] ---> receipts ---> MF-H
            |
            +---- transient/unknown ---> [G6 Retry Scheduler] ---> (loop)
            |
            v
   success (PUBLISHED/ALREADY_PUBLISHED)
            |
            v
   [G8 Receipt Writer] ---> MF-H   +   [G10 Signals] ---> MF-I (best effort)
            ^
            |
        [G9 Recovery Resolver]  (used when outcome is UNKNOWN)
```

---

# The publish commit protocol (this is the “no drift” spine)

## Step 0 — Preconditions (must already exist)

MF-H must already have:

* `gate_receipt = PASS`
* `bundle_candidate_receipt` with `bundle_fingerprint`

If not: MF-G refuses to publish.

## Step 1 — Start publish stage (lock)

* Append in MF-H: `stage_started(PUBLISH, attempt_no, lease_token)`

## Step 2 — Record attempt intent

* Append: `publish_attempt(attempt_no, bundle_fingerprint)`

## Step 3 — Call Registry publish (idempotent)

* `PublishBundle(idempotency_key=bundle_fingerprint, payload=refs+digests+compat+provenance)`

## Step 4 — Record result (one of the canonical outcomes)

* Append: `publish_result(PUBLISHED|ALREADY_PUBLISHED|REJECTED|CONFLICT|TRANSIENT_FAIL|UNKNOWN_OUTCOME)`

## Step 5 — Terminalization

* If `PUBLISHED/ALREADY_PUBLISHED`: append `run_terminal(SUCCESS_PUBLISHED)` and `stage_completed(PUBLISH)`
* If transient/unknown and budget not exhausted: leave run as `PUBLISH_PENDING` (not “failed training”)
* If reject/conflict: append `run_terminal(FAILED_REJECTED|FAILED_CONFLICT)`

**Hard rule:** publish success is sticky; once recorded, no further attempts for that `bundle_fingerprint`.

---

# How MF-G supports the key production paths

## IP4 / IL5 — Publish-only retry (no retrain)

* If PASS + bundle_candidate exist, MF-D routes to `PUBLISH_ONLY`.
* MF-G reads MF-H: if already published → return success; else attempt publish with bounded retry.

## IP6 — ALREADY_PUBLISHED is success

* Treated as success, recorded as such, terminalized.

## IP7 — CONFLICT is terminal

* Hard stop; preserve evidence; escalate.

---

# Environment ladder knobs (deployment posture for MF-G)

These can vary by profile without changing semantics:

* retry budget and backoff schedule (local more generous, prod conservative)
* timeouts for publish and status probes
* whether status probe is enabled (recommended in dev/prod)
* auth mechanism (token injection), TLS strictness
* concurrency cap for simultaneous publish stages

What cannot vary:

* idempotency key = `bundle_fingerprint`
* conflict is terminal
* publish does not imply activation
* MF-H receipts are required for correctness

---

# Non-joins MF-G enforces (explicit)

MF-G must never:

* call activation/promote/rollback endpoints
* write to `registry/bundles/...` directly
* publish without PASS receipt + compatibility metadata
* treat telemetry or control-bus emission as proof of publish

---

If you want the next node illumination, the clean continuation is **MF-F (Evidence + Gates + Bundle Assembly)** — because MF-G assumes a stable `bundle_fingerprint`, a complete compatibility descriptor, and a PASS gate receipt, and MF-F is the machinery that produces those correctly.

---

Understood — we’re illuminating **MF-F (Evidence + Gates + Bundle Assembly)** and exposing the machinery inside it.

MF-F is the “truth assembler” inside MF: it turns **opaque compute outputs** (from MF-E) into **portable, auditable, deployable candidates** that MF-G can publish safely and idempotently.

---

# MF-F in one sentence

**MF-F ingests the TrainingEvidencePack (artifact refs/digests + eval report), enforces gate policy (PASS/FAIL) with explicit criteria and reason codes, assembles an immutable BundleCandidate with a required compatibility descriptor and full provenance pointers, and emits a stable `bundle_fingerprint` and `gate_receipt` recorded in MF-H.**

**Design law:** MF-F never activates anything; it produces *candidates* and *evidence* only.

---

# MF-F internal subnetworks (the machinery inside)

## F1) Evidence Intake + Validator

**Role:** ingest the evidence pack from MF-E and validate it’s complete and internally consistent.

Checks:

* required artifact locators exist (refs + digests)
* eval report locator exists (ref + digest)
* evidence pack binds to:

  * `train_run_id`
  * `input_fingerprint`
  * `policy_rev` / `training_recipe_digest` (as appropriate)

**Hard fail** if evidence is missing/incomplete or unbound to the run.

---

## F2) Evidence Normalizer + Provenance Extractor

**Role:** produce a canonical “evidence summary” used by gates and later audits.

Produces:

* `evidence_fingerprint = hash(sorted(artifact_digests) + eval_report_digest + input_fingerprint + mf_build_id)`
* `evidence_summary` (metric keys present, dataset ids used, feature pins used, etc.)
* references to:

  * DatasetManifest digests/refs
  * training recipe digest
  * policy profile digest/rev
  * mf_build_id

This is the “make it portable” step.

---

## F3) Metric Interpreter (Eval reader)

**Role:** interpret the evaluation report into a structured metric map used by gate policy.

* Parses metrics (overall, slices, fairness/coverage if present, stability checks)
* Ensures metric schema matches what policy expects (no missing required metrics)
* Produces a canonical metric map (ordered, typed, comparable)

**Hard fail** if required metrics aren’t present (because gates cannot be meaningfully applied).

---

## F4) Gate Policy Resolver (policy → executable criteria)

**Role:** resolve the gate criteria from MFContext policy profile.

* Which gate set applies for this intent? (train vs backfill retrain vs eval-only)
* Thresholds, minimum evidence requirements, prohibited conditions
* Which reason codes to emit on failure

**Key pin:** gate policy is **versioned and cited**; MF-F never “invents” criteria.

---

## F5) Gate Evaluator (PASS/FAIL engine)

**Role:** apply gate criteria to the canonical metric map + evidence summary.

Outputs:

* PASS/FAIL verdict
* `gate_reason_codes[]`
* `gate_details_ref` (optional detailed report artifact)
* explicit “why” fields:

  * which criteria passed/failed
  * observed values vs thresholds

**Hard rule:** FAIL is a normal outcome; it is not an error.

---

## F6) Compatibility Descriptor Builder (anti-drift contract)

**Role:** construct the bundle’s compatibility metadata — the minimum information Registry/DF need to enforce safe resolution.

At minimum it must declare:

* required **feature group/version pins** (from manifests / feature pack)
* required **capabilities** (e.g., “requires IEG context vX”, “requires OFP snapshot type Y”) — high level
* bundle “decision surface” scope (model_family_id / decision_kind)
* optional: minimum schema version(s) of inputs expected

**Hard rule:** compatibility descriptor is mandatory; missing it blocks publish eligibility.

---

## F7) Bundle Manifest Assembler

**Role:** assemble an immutable BundleCandidate “manifest” that contains only by-ref pointers + digests.

BundleCandidate includes:

* bundle metadata (name/id, created_ts metadata)
* `train_run_id`, `input_fingerprint`
* artifact locators (refs + digests)
* evaluation evidence locators (refs + digests)
* `gate_receipt_ref` (or embedded gate receipt digest)
* compatibility descriptor
* provenance pointers:

  * DatasetManifest refs/digests
  * policy_rev + policy digest
  * training recipe digest
  * mf_build_id
  * (optional) backfill declaration ref / incident ref

**Hard rule:** bundle is immutable; updates = new bundle candidate.

---

## F8) Bundle Fingerprint Calculator (idempotency anchor)

**Role:** compute `bundle_fingerprint` as the stable hash over the BundleCandidate content.

`bundle_fingerprint = H("bundle_v1" + canonical_json(bundle_candidate_manifest))`

* Canonicalization must be deterministic (stable ordering of keys and lists).
* Any change in artifact digests, compatibility descriptor, gate policy rev, or provenance changes the fingerprint.

This fingerprint is what MF-G uses as the **idempotency key** with Registry.

---

## F9) Receipt Writer (MF-H adapter)

**Role:** persist the truth chain into MF-H:

* `evidence_receipt` (evidence_fingerprint + refs/digests)
* `gate_receipt` (PASS/FAIL + criteria refs + reason codes)
* `bundle_candidate_receipt` (bundle_fingerprint + bundle manifest locator)
* `supersedes` receipts if this replaces a prior candidate under declared intent

**Hard rule:** if MF-H can’t record these, MF-F fails closed (cannot proceed to publish).

---

## F10) Optional Evidence Artifact Writer

**Role:** write additional by-ref artifacts to `mf/...`:

* gate evaluation report (human-readable)
* metric snapshots
* comparison reports (baseline vs candidate)
* compatibility explanation

These are helpful for ops/governance but are not strictly required for correctness if policy doesn’t demand them.

---

# MF-F internal join map (inside the node)

```
Input: TrainingEvidencePack (refs+digests) + MFContext(policy) + run pins

 [F1 Evidence Validate]
          |
          v
 [F2 Evidence Normalize + evidence_fingerprint]
          |
          v
 [F3 Metric Interpret] ----missing required metrics----> HARD FAIL (cannot gate)
          |
          v
 [F4 Gate Policy Resolve]
          |
          v
 [F5 Gate Evaluate] ---> gate verdict (PASS/FAIL + reasons)
          |
          +-------------------+
          |                   |
        FAIL                PASS
          |                   |
          v                   v
   [F9 Write gate_receipt]   [F6 Build Compatibility]
          |                   |
          v                   v
     terminal (no publish)  [F7 Assemble Bundle Manifest]
                              |
                              v
                        [F8 Compute bundle_fingerprint]
                              |
                              v
                        [F10 Write bundle artifact (mf/...)]
                              |
                              v
                        [F9 Write bundle_candidate_receipt]
                              |
                              v
                         output to MF-G (publish eligible)
```

---

# The explicit “truth products” MF-F produces (the receipts)

MF-F is responsible for emitting these portable truths (all by-ref, all digest-bound):

1. **EvidenceReceipt**

* `evidence_fingerprint`
* artifact refs/digests
* eval report ref/digest
* binds to `train_run_id` + `input_fingerprint`

2. **GateReceipt**

* `verdict: PASS|FAIL`
* `policy_rev` (and policy digest)
* `criteria_id`/ref (which gate set applied)
* `reason_codes[]` (especially on FAIL)
* pointers to evaluation evidence

3. **BundleCandidateReceipt** (PASS only)

* `bundle_fingerprint` (idempotency anchor)
* locator to the BundleCandidate manifest artifact
* compatibility descriptor summary
* provenance pointers

These are the minimum that enable MF-G to publish safely and enable L6 explainability later.

---

# Failure semantics (so MF-D can route correctly)

MF-F can end in:

* **FAIL (normal):** gate fails → no publish; MF-D terminalizes as `FAILED_GATES`.
* **HARD FAIL (error):** evidence incomplete, required metrics missing, policy ref missing → MF-D treats as stage failure (retryable or terminal based on reason).
* **PASS:** bundle candidate produced; MF-D routes to publish stage.

---

# Environment ladder knobs for MF-F (policy-driven strictness)

Allowed to vary by profile (policy rev):

* which gate criteria apply and thresholds
* required metric sets (local can be minimal, prod stricter)
* whether a human-approval step is required *after* PASS (still not MF activation)
* required compatibility descriptor fields (prod stricter)

Not allowed to vary (semantic invariants):

* PASS/FAIL must be explicit
* gate receipts must cite policy rev
* compatibility descriptor must exist for publish eligibility
* bundle_fingerprint must be deterministic

---

# Non-joins MF-F enforces (explicit)

MF-F must never:

* publish to Registry (that’s MF-G)
* decide ACTIVE (Registry only)
* re-read datasets from `ofs/...` or EB (it uses evidence refs only)
* mutate artifacts/receipts in place
* produce a publishable candidate without PASS

---

If you want the next illumination, the remaining “core” node is **MF-B (Context Resolver)** (profiles/authz and policy vs wiring discipline) and then **MF-I** (signals). **MF-E** we can leave last since it’s compute-heavy and mostly constrained by the evidence contract we’ve now pinned.

---

Understood — we’re illuminating **MF-B (Context Resolver)** and exposing the machinery inside it. This is the module that turns “refs” into a fully pinned **MFContext** (policy+wiring+recipe+build id) and produces the **authz verdict** that gates the entire run.

MF-B is the **config truth gateway**: if MF-B is sloppy, everything downstream drifts.

---

# MF-B in one sentence

**MF-B resolves all configuration/profile artifacts (wiring + policy + training recipe + optional feature-pack ref) into a fully pinned MFContext with digests/revisions, performs authorization checks, computes a deterministic context fingerprint, and writes a ContextReceipt to MF-H so no stage can proceed under implicit or changing config.**

---

# MF-B internal subnetworks (machinery inside)

## B1) Context Request Canonicalizer

**Role:** take the incoming “context intent” from MF-A and normalize it.

* Ensures required refs exist:

  * `wiring_profile_ref`
  * `policy_profile_ref`
  * `training_recipe_ref`
* Normalizes ref formats (canonical URIs / object-store pointers).
* Canonicalizes intent type (train/eval-only/backfill-retrain/publish-only).

**Output:** `CanonicalContextRequest`

---

## B2) Profile Resolver (IJ9 client)

**Role:** fetch the profile artifacts by explicit ref (by-ref only).

* Reads from `profiles/...` (and possibly `gov/...` if approval records are referenced).
* Bounded retries for transient errors.
* Distinguishes: missing vs denied vs transient.

**Outputs:**

* `wiring_profile_bytes`
* `policy_profile_bytes`
* `training_recipe_bytes`
* (optional) `feature_pack_bytes` if referenced

**Hard rule:** no “look up active profile” unless the request already contains that resolved ref.

---

## B3) Digest & Immutability Verifier

**Role:** compute/verify digests for each resolved artifact.

* If the request includes expected digests, verify them.
* Otherwise compute digests and pin them in the ContextReceipt.
* Detect immutability conflicts: “same ref, different bytes” → **hard fail**.

**Output:** `ResolvedArtifact(ref, digest, parsed)`

---

## B4) Schema/Shape Validator (profile sanity)

**Role:** validate that resolved artifacts are structurally valid.

* Wiring profile has required fields (endpoints, timeouts, resource ceilings).
* Policy profile has required fields (admissibility strictness, gate set refs, compatibility requirements).
* Training recipe is present and consistent (declares model_family/decision surface, expected dataset roles, expected feature pins posture).

**Hard fail** on invalid/missing required fields.

---

## B5) Policy vs Wiring Splitter (semantic boundary)

**Role:** produce two explicit objects:

* **MFContext.wiring** (non-semantic knobs)

  * endpoints (object store, registry, otlp, control bus)
  * concurrency limits, timeouts, retry defaults
  * runtime envelope (cpu/mem/scratch), scheduling hints

* **MFContext.policy** (semantic knobs, versioned)

  * admissibility rules (manifests required, proofs required, strictness)
  * gate policy set id/ref (criteria, thresholds)
  * compatibility requirements (required fields)
  * privacy/export constraints
  * retry budgets classification (retryable vs terminal categories)
  * publish eligibility rules (PASS-only v0)

**Design law:** MF-B must *never* leak wiring knobs into semantics. If a knob affects outcomes, it belongs in policy.

---

## B6) Authorization Evaluator (authz verdict)

**Role:** decide whether this caller is allowed to:

* trigger an MF run under this policy profile
* read the referenced profiles
* later publish to Registry (capability gating)

Inputs:

* `caller_principal` (from request)
* environment profile posture (local/dev/prod)
* policy profile requirements (separation of duties may differ by env)

Outputs:

* `authz_verdict = ALLOW | DENY`
* `denial_reason_codes[]`
* optional capability set:

  * `can_train`
  * `can_eval`
  * `can_publish_candidate`
  * `can_emit_control_facts` (optional)

**Hard rule:** DENY stops the run before any data-plane access.

---

## B7) MF Build Identity Resolver

**Role:** pin the executing code identity into MFContext.

* `mf_build_id` = container image digest / build hash / commit id (whatever you use)
* optional `runtime_fingerprint` (python version etc.) as metadata

**Design law:** MF runs must be explainable as “code build X + policy rev Y + data Z”.

---

## B8) Context Fingerprint Builder

**Role:** compute a deterministic `context_fingerprint` (idempotency/support for audits).

* `context_fingerprint = H("mf_context_v1" + policy_digest + recipe_digest + mf_build_id + (optional) wiring_digest)`
* Default: wiring digest is **not** included unless you decide wiring can affect semantics. (Strong preference: keep it out.)

Outputs:

* `context_fingerprint`
* `policy_rev` (from policy profile)
* `recipe_id` / `model_family_id` (from recipe)

---

## B9) Context Emitter (IJ2 payload builder)

**Role:** produce the payload for MF-C and MF-D:

* MFContext (policy+wiring objects)
* digests of all resolved artifacts
* policy_rev, recipe digest, mf_build_id
* capability set from authz evaluator
* context_fingerprint

---

## B10) Context Receipt Writer (MF-H adapter)

**Role:** write the authoritative ContextReceipt to MF-H (truth plane).
This receipt must contain:

* all refs + digests (policy, wiring, recipe, feature pack if any)
* policy_rev
* mf_build_id
* context_fingerprint
* authz verdict + capability set
* environment_id

**Hard rule:** if MF-H can’t record this, MF-B fails closed (nothing proceeds).

---

# MF-B internal join map

```
Input: ContextResolveIntent (refs + caller + env + intent)

 [B1 Canonicalize]
        |
        v
 [B2 Resolve profiles]  <--- IJ9 ---> profiles/...
        |
        v
 [B3 Digest verify + immutability]
        |
        v
 [B4 Validate shapes]
        |
        +---------------------------+
        |                           |
        v                           v
 [B5 Split policy/wiring]     [B6 Authz evaluate]
        |                           |
        +-------------+-------------+
                      |
                      v
             [B7 Resolve mf_build_id]
                      |
                      v
             [B8 context_fingerprint]
                      |
                      v
 [B10 Write ContextReceipt to MF-H]  +  [B9 Emit MFContext to MF-C/D]
```

---

# What MF-B guarantees to the rest of MF (the contract downstream relies on)

Downstream nodes can assume:

1. **No implicit config**: all profiles are pinned by ref+digest.
2. **Policy rev is explicit** and cited in receipts/gates/bundles.
3. **Authz is enforced early**: denied runs cannot access data-plane or Registry.
4. **MF build identity is pinned** (reproducibility and explainability).
5. The split between **policy** and **wiring** is clean.

---

# Environment ladder knobs (how MF-B differs across local/dev/prod)

Allowed to vary (wiring):

* endpoints, concurrency, timeouts, retry defaults, resource ceilings

Allowed to vary (policy, but only via versioned policy rev):

* strictness (more strict in prod)
* required gate sets/metrics (more strict in prod)
* separation-of-duties rules (more strict in prod)

Not allowed to vary:

* “profiles must be pinned”
* “authz verdict must exist”
* “ContextReceipt must be recorded before proceeding”

---

# Non-joins MF-B enforces

MF-B must never:

* resolve “current active policy” implicitly (unless passed in as an explicit ref)
* touch training datasets, OFS manifests, EB, labels
* embed secrets into MFContext or receipts/logs
* allow progress without a ContextReceipt committed to MF-H

---

If you want to keep the illumination momentum: next is **MF-I (Observability + Control Facts)** (lightweight), and then **MF-E (Train/Eval engine)** last, since it’s compute-heavy and now fully constrained by the evidence contract (IJ4/IJ5).

---

Understood — we’re illuminating **MF-I (Observability + optional Control-Facts)** and exposing the machinery inside it.

MF-I is the **signal plane**. It must be production-grade, but it is **never** allowed to influence correctness (truth lives in MF-H + Registry). The machinery here is about **correlation**, **bounded emission**, and **clean separation** between telemetry and optional control-bus facts.

---

# MF-I in one sentence

**MF-I collects stage/run signals from MF-A..G, enriches them with mandatory correlation keys, emits OTLP traces/metrics/logs, and (optionally) emits low-volume `mf.*` control facts as canonical-envelope events containing by-ref pointers — all best-effort and bounded.**

**Design law:** MF-I can fail without changing MF outcomes.

---

# MF-I internal subnetworks (machinery inside)

## I1) Signal Intake Router

**Role:** accept signal events from internal nodes A–G in a uniform way.

* Accepts:

  * `RunSignal` (request received, run claimed, run terminal, cancel requested)
  * `StageSignal` (stage started/completed/failed with attempt_no)
  * `PublishSignal` (attempt, retry, published/already_published/conflict)
  * `AdmissibilitySignal` (admissible/reject reason codes)
  * `GateSignal` (PASS/FAIL + reasons)
* Normalizes them into a single internal event type: `MFSignal`.

**Key:** No payload should include raw rows, secrets, or large blobs.

---

## I2) Correlation Enricher (mandatory keys)

**Role:** attach the correlation keys that make MF operable and joinable.
Every MFSignal must carry:

* `train_run_id`
* `request_id`
* `input_fingerprint` (if known yet)
* `policy_rev`
* `mf_build_id`
* `bundle_fingerprint` / `bundle_id` (if reached)
* `environment_id`

**Rule:** If a key isn’t known at the time (e.g., input_fingerprint before C completes), the signal still emits with the known subset; later signals must include the full set.

---

## I3) Signal Classifier (truth vs signal)

**Role:** enforce the “signal-only” posture:

* Tag signals as:

  * `telemetry_only`
  * `control_fact_candidate` (eligible to be emitted on control bus)
* Hard rule: *no signal becomes truth*.

This module prevents accidental “we used the control bus as the record”.

---

## I4) OTLP Trace Builder

**Role:** create traces/spans for the MF stage machine.

* One root trace per `train_run_id` (or per request_id if run_id not assigned yet).
* Spans per stage:

  * context resolve, admissibility, train, eval, gate, package, publish
* Each span includes correlation keys + attempt_no + outcome.

**Rule:** No PII/secrets; keep attributes bounded.

---

## I5) Metric Aggregator (golden signals + MF-specific)

**Role:** emit the minimum production metrics:

* Counts: runs started/completed by outcome class
* Reject counts by reason code family
* Stage durations (train/eval/gate/publish)
* Retry counts (stage retries, publish retries)
* Conflict count (should be near zero; alert-worthy)
* Publish pending backlog (if you run deferred publish retries)

**Rule:** control cardinality. Reason codes should be grouped (family + code), not unbounded strings.

---

## I6) Structured Log Emitter

**Role:** produce JSON logs for:

* run lifecycle transitions
* stage transitions
* failure reason codes
* publish results

**Rule:** Logs must always include correlation keys and must be safe to store (no secrets/raw data).

---

## I7) Exporter Manager (bounded, best-effort)

**Role:** actually ship OTLP signals to the collector.

* Supports:

  * batching
  * bounded buffering (memory/disk)
  * bounded retry/backoff
* Failure behavior:

  * drop with counters once buffer exhausted
  * never block MF correctness path

This is IL7 machinery for OTLP.

---

## I8) Control-Fact Assembler (optional IJ13)

**Role:** for a small subset of MFSignals, build control facts suitable for `fp.bus.control.v1`.

Minimal recommended event set:

* `mf.train_run.started`
* `mf.train_run.completed` (includes PASS/FAIL posture)
* `mf.bundle.published` (only when Registry accepts)

**Payload rule:** by-ref pointers only:

* `mf_run_record_ref` (in `mf/...`)
* `gate_receipt_ref`
* `bundle_candidate_ref` and/or `bundle_id`
* `train_run_id`, `input_fingerprint`, `policy_rev`, `mf_build_id`

No embedded evidence, no embedded metrics tables.

---

## I9) Control-Bus Envelope Wrapper

**Role:** wrap control facts into the **canonical event envelope**.

* Required envelope fields: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
* For MF facts (not world-scoped), use the platform convention:

  * `manifest_fingerprint = platform_sentinel` (a fixed value)
  * carry MF scope in payload (`train_run_id`, etc.)

**Rule:** duplicates are allowed; consumers must tolerate idempotency.

---

## I10) Control-Fact Exporter (bounded, best-effort)

**Role:** publish control facts to `fp.bus.control.v1` with bounded retry/backoff.

* Best-effort only; never blocks MF run.
* If it can’t publish, it increments dropped counters and logs locally.

---

## I11) Redaction & Safety Guard

**Role:** enforce “no secrets/no raw rows” at the last possible point.

* Blocks known secret patterns
* Blocks large payloads
* Ensures only refs/digests/reason codes pass through

This is the guardrail that keeps MF-I safe to run in prod.

---

# MF-I internal join map (inside the node)

```
Signals from A..G
   |
   v
[I1 Intake] -> [I2 Correlate] -> [I3 Classify]
                      |                 |
                      |                 +--> (optional) [I8 Control-Fact Assemble]
                      |                                   |
                      |                                   v
                      |                             [I9 Envelope Wrap]
                      |                                   |
                      |                                   v
                      |                             [I10 Control-Bus Export]  (best effort)
                      |
                      +--> [I4 Trace Builder] -> [I7 OTLP Export]
                      +--> [I5 Metrics] ------> [I7 OTLP Export]
                      +--> [I6 Logs] ---------> [I7 OTLP Export]

(guardrails)
             all paths pass through [I11 Redaction/Safety Guard]
```

---

# What MF-I must never do (non-joins, enforced here)

MF-I must never:

* gate MF progression on telemetry success
* treat control facts as authoritative run truth
* emit secrets or raw training data
* emit unbounded high-cardinality payloads that break prod (full manifests, giant metric tables)
* “backfill” missing truth by reading MF-H or Registry and inventing state
  (it can *attach pointers* if provided, but it doesn’t become a truth query engine)

---

# Environment ladder knobs for MF-I

Semantics identical everywhere; only envelope differs:

* **Sampling rate** (high local, lower prod)
* **Buffer limits** (small local, bounded prod)
* **Retry budgets** (dev/prod tuned)
* **Whether IJ13 is enabled** (optional; recommend enabled in dev/prod, optional in local)
* **Log verbosity** (debug local, structured concise prod)

---

# Minimal “production readiness” checks for MF-I

Before you trust MF in prod, MF-I should prove:

* every stage emits spans with correlation keys
* publish retries/conflicts are visible in metrics
* dropped telemetry/control-facts are counted (and do not block MF)
* control facts are by-ref only and canonical-envelope compliant if enabled

---

If you want to complete the illumination set, the last remaining core node is **MF-E (Train/Eval Engine)** — which we can keep relatively lean because it’s already constrained by the evidence contract we pinned (E emits artifact locators + eval report locators + evidence pack; nothing more).

---

Understood — we’re illuminating **MF-E (Train/Eval Engine)** and exposing the machinery inside it.

MF-E is intentionally **compute-opaque** in the platform sense, but it must be **contract-precise**: it must take only pinned inputs, run deterministically where required, and emit a **TrainingEvidencePack** that MF-F can gate and package without needing to “re-derive” anything.

---

# MF-E in one sentence

**MF-E executes the TRAIN and EVAL stages as a deterministic, stage-shaped compute engine driven by MF-D, producing immutable artifacts and evaluation evidence by-ref (with digests), bundled into a TrainingEvidencePack bound to `train_run_id` and `input_fingerprint`.**

**Design law:** MF-E never chooses inputs, never publishes, never decides eligibility; it only produces evidence blobs.

---

# MF-E internal subnetworks (machinery inside)

## E1) Stage Intake Adapter (from MF-D)

**Role:** accept stage calls in a uniform way.
Inputs always include:

* `train_run_id`
* `stage_id` (`TRAIN` or `EVAL`)
* `attempt_no`
* `stage_seed` (deterministic)
* `input_fingerprint`
* `resolved_input_locators` (materialization refs + digests, manifests refs + digests)
* `training_recipe_ref+digest`
* `runtime_envelope` (resource ceilings from wiring profile)

Outputs:

* `StageOutcome` (SUCCESS/FAIL + reason codes)
* locators to outputs (if any)

**Hard rule:** if any required pin is missing, E1 rejects the stage call (fail fast).

---

## E2) Workspace & Materialization Mount Manager

**Role:** materialize the by-ref inputs into a local working set without changing their meaning.

* Verifies input digests before use (or trusts MF-C’s digests but still validates presence/readability).
* Stages inputs into a scratch workspace.
* Enforces read-only posture for input materializations.

**Hard rule:** MF-E must not “fix” or mutate inputs. Any detected mismatch is a failure.

---

## E3) Determinism Controller (seed + RNG discipline)

**Role:** ensure reproducibility where required.

* Creates per-stage RNG streams from `stage_seed`.
* Ensures any stochastic procedures use only those RNG streams.
* Records RNG configuration in metadata (as evidence).

**Important nuance (authoritative):**

* We require **deterministic identity and evidence chain**, not necessarily bit-identical floating-point results across all hardware.
  To avoid making prod brittle, MF-E must **record enough** (build id, runtime fingerprint, library versions) so differences are explainable, and gating tolerances can account for minor numeric drift.
  Determinism is “as deterministic as the environment allows,” and the environment itself is pinned and reported.

---

## E4) Training Runner

**Role:** run the training recipe against pinned inputs.

* Consumes only `resolved_input_locators` (never reads EB/LabelStore).
* Produces primary model/policy artifacts.
* Produces training metadata (parameters used, feature pins observed, dataset ids, timestamps as metadata).

Outputs (by-ref):

* `model_artifact_ref(s)` + digest(s)
* `train_metadata_ref` + digest

**Hard rule:** any time/clock is metadata only and must never affect run identity.

---

## E5) Evaluation Runner

**Role:** run evaluation using the pinned evaluation dataset(s) in the manifest set.

* Produces an evaluation report artifact (metrics + slices).
* Produces an evaluation metadata artifact (what was evaluated, with what inputs).

Outputs (by-ref):

* `eval_report_ref` + digest
* `eval_metadata_ref` + digest

**Hard rule:** evaluation must bind to `input_fingerprint` and must declare which dataset roles were used (train vs eval manifests).

---

## E6) Artifact Packager (TrainingEvidencePack builder)

**Role:** assemble the portable evidence pack MF-F expects.
It builds:

### `TrainingEvidencePack`

* `train_run_id`
* `input_fingerprint`
* `attempt_binding` (stage attempt numbers used)
* `artifact_locators[]` (refs + digests)
* `eval_report_locator` (ref + digest)
* `train_metadata_locator` (ref + digest)
* `eval_metadata_locator` (ref + digest)
* `evidence_pack_fingerprint` (hash over all locators + input_fingerprint + mf_build_id)

**Hard rule:** evidence pack must be immutable and self-consistent.

---

## E7) Failure Classifier (reason codes)

**Role:** convert failures into stable reason codes that MF-D can use for retries.

* `TRANSIENT_IO`
* `RESOURCE_EXHAUSTED`
* `RUNTIME_CRASH`
* `INPUT_DIGEST_MISMATCH`
* `RECIPE_INVALID`
* `NONDETERMINISM_GUARD_TRIGGERED` (e.g., missing seed discipline)
* etc.

**Hard rule:** MF-E must not hide failures as “just failed.” It must classify them.

---

## E8) Artifact Writer Adapter (to MF-H/H5/H6)

**Role:** write outputs to `mf/...` (or stage area) via MF-H’s artifact protocol.

* Writes artifacts
* Computes/records digests
* Returns locators
* Ensures nothing is treated as committed until MF-H records locator receipts

**Hard rule:** MF-E cannot “commit” truth on its own; MF-H must record locators.

---

## E9) Telemetry Hook (to MF-I)

**Role:** emit stage spans/metrics/logs.

* Includes correlation keys: `train_run_id`, `input_fingerprint`, `attempt_no`, `policy_rev`, `mf_build_id`.

Best-effort only.

---

# MF-E internal join map (inside the node)

```
MF-D stage call
   |
   v
[E1 Stage Intake + validation]
   |
   v
[E2 Workspace/Mount inputs] ----input mismatch----> [E7 Fail classify]
   |
   v
[E3 Determinism controller]
   |
   +---------------------------+
   |                           |
   v                           v
[E4 Training Runner]      [E5 Evaluation Runner]
   |                           |
   +-------------+-------------+
                 |
                 v
        [E8 Artifact Writer via MF-H]
                 |
                 v
     [E6 Evidence Packager]
                 |
                 v
   output TrainingEvidencePack to MF-F
                 |
                 v
        [E9 Telemetry to MF-I]  (best effort)
```

---

# MF-E’s external “contracts” inside MF (what other nodes rely on)

## What MF-D assumes about MF-E

* MF-E is stage-shaped: it can run TRAIN and EVAL separately.
* It reports failures with retryable vs terminal reason codes.
* It produces outputs by-ref with digests and attempt binding.

## What MF-F assumes about MF-E

* Evidence pack is complete and self-consistent.
* It binds to `train_run_id` + `input_fingerprint`.
* It includes artifact locators + eval report locator and metadata locators.

MF-F must never need to “re-run eval” by reading datasets; it either re-invokes MF-E or uses the evidence pack.

---

# Environment ladder knobs for MF-E (deployment realism)

Allowed to differ by env (wiring profile):

* compute resources (cpu/mem/gpu)
* concurrency
* scratch space limits
* timeouts
* library build options (but mf_build_id/runtime fingerprint must be recorded)

Allowed to differ by env (policy profile):

* max training window sizes (enforced upstream, but E can sanity-check)
* maximum runtime
* whether to require strict determinism (e.g., force CPU-only in prod if you want bit-stability)

Not allowed to differ:

* pinned-input discipline (no EB/LabelStore reads)
* evidence pack structure (must always be produced or failure classified)
* by-ref + digest posture for outputs

---

# Non-joins MF-E must never violate

MF-E must never:

* select “latest data”
* read EB/Archive/LabelStore directly
* publish to Registry
* decide PASS/FAIL
* write into `registry/bundles/...`
* treat telemetry success as correctness

---

## What we’ve achieved by illuminating MF-E

We now have the full first-layer vertex illumination with **tight internal contracts**:

* A/H give idempotency + truth plane,
* D gives stage machine + resume/retry,
* C gives admissibility,
* E produces evidence packs,
* F gates + assembles bundle candidates,
* G publishes idempotently,
* B pins context/profile truth,
* I emits signal plane.

---

## USER: PAUSE FOR REFLECTION

Totally fair to pause here — what we’ve drawn is *intentionally* deep, because MF sits at a nasty intersection: **reproducibility + governance + deployable change**.

Here’s the “complexity snapshot” of what we now have.

## What we actually built (in layers)

1. **Outer platform graph** (unchanged): OFS → MF → Registry with the learning loops around it.
2. **MF as a vertex**: strict boundaries (manifests-only in, candidates-only out, never activate).
3. **MF inner network (A–I)**: nine opaque subnetworks with explicit joins/paths/loops.
4. **Second-layer illumination (inside A/B/C/D/E/F/G/H/I)**: each node now has its own internal machinery—still modular, but real.

That’s why it feels “big”: we didn’t just draw a box, we drew the **mechanics that make the box trustworthy**.

## Where the complexity is coming from

It’s not “ML complexity.” It’s *systems* complexity:

* **Idempotency under retries** (IL1/IP5): duplicates must not create alternate histories.
* **Resume safety** (IL2): stage completion must be ledger-truth, not file-guessing.
* **Evidence chain**: every step produces receipts so nothing is implied.
* **Publish correctness** (IL5/IP4/IP6/IP7): idempotent publish, conflict hard-stop, publish-only retry.
* **Append-only lineage** (IL6): supersedes without mutation, so audit stays intact.
* **Environment ladder**: same semantics everywhere; profiles only change strictness/envelope.
* **Negative space** (non-joins): preventing the “easy shortcuts” that silently reintroduce drift.

## The key simplifier we introduced (the spine)

Even though the network is complex, it’s governed by one spine:

**Receipt chain in MF-H**
`Context → Admissibility → Stage receipts → Evidence → Gate → BundleCandidate → Publish → Terminal (+ supersedes)`

That one backbone is what prevents contradictions later:
if a node “needs something,” it must be **a receipt/locator that already exists**.

## The big design move that keeps this production-shaped

We separated the world into:

* **Truth plane (fail-closed):** MF-H + Registry DB truth
* **Signal plane (best effort):** OTLP + optional control bus

That single split prevents whole classes of accidental coupling (“it didn’t publish because telemetry failed,” etc.).

## Where we can keep the design from getting *more* complex

As we go deeper, the discipline is:

* Don’t add new joins; only implement what the joins already require.
* Prefer **reason codes + receipts** over new state machines.
* Keep the stage graph minimal: TRAIN → EVAL → GATE/PACKAGE → PUBLISH.
* Treat policy as *data* (profiled), not branches in code.

## What’s “complex but necessary” vs “optional”

Necessary:

* MF-H coordination semantics (claim/lease/receipts/locators)
* deterministic keys (`run_key`, `input_fingerprint`, `bundle_fingerprint`)
* publish idempotency + conflict behavior

Optional (can be dialed later without breaking the design):

* control-bus `mf.*` facts
* richer gate artifacts
* richer compatibility descriptor fields (beyond the minimum)

If you want, next we can pick **one node** and go deeper *only where it reduces future complexity*. My bias is still: **MF-H → MF-A → MF-D** first (because they define the foundation that everything else must conform to).

---