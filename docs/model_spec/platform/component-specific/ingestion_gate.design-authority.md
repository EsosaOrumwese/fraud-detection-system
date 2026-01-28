# Ingestion Gate Design Authority

This file is a rough collection of design or brainstorm notes for the Ingestion Gate. It views the whole platform as a network and expands open the ingestion gate's position in this network and illuminates it.

---

Here’s the **necessary IG overview** — the stuff that is *pinned / load-bearing* for the platform, and the minimum you must keep in your head **before** we start walking edges/paths.

I’m treating this as **designer-authoritative** (within your pinned platform network).

---

## 1) What IG is (its single job in the platform graph)

IG is the platform’s **trust boundary** for anything that can influence decisions, audit, labels, or learning.

That means: **no matter where an event comes from**, it only becomes “platform fact” after it crosses IG.

**Design update (WSP):** IG is **push‑only** in v0. The sealed world is streamed by **WSP** and delivered to IG via **push ingestion**. Legacy engine‑pull ingestion is **retired** and should not be considered part of the runtime path.

---

## 2) IG’s authority boundary (what IG owns vs what it must not own)

### IG owns (authoritative truth)

* The **admission decision** for each input item: **exactly one** of **ADMIT / DUPLICATE / QUARANTINE**.
* A durable **receipt/evidence trail** for that decision (no silent drop; no “best effort”).

### IG does *not* own

* “What the payload means” (business truth / semantics). EB and downstream interpret; IG only enforces boundary rules.
* “What world/run to use” — SR owns that via READY + oracle pack refs (IG does not pull run_facts_view in streaming‑only).

---

## 3) The boundary object IG enforces

Everything admitted to EB must be representable as the **Canonical Event Envelope** (envelope is pinned; payload is intentionally loose).

Minimum required envelope fields:

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`

Key meaning of `event_id` (important for later): it’s the **stable identifier** used for **idempotency/dedup at ingest/bus boundaries**. 

---

## 4) Run/world joinability is the core “safety latch”

If an event is meant to participate in the current run/world, IG enforces that it is joinable to a **valid run context** (and, in practice, a **READY** run). If not joinable → quarantine/hold, not “best effort.”

Also pinned: downstream components are **forbidden** from scanning engine outputs or inferring “latest run”; they must start from **SR READY + oracle pack refs** and follow by‑ref truth. IG follows that same rule for WSP‑driven ingestion.

**Streaming‑only pin:** IG does **not** read `run_facts_view` in v0 streaming mode. Any references to `run_facts_view` below are **legacy pull‑only** and should be ignored.

---

## 5) “No PASS → no read” is not optional (and IG is a verifier)

For engine-derived ingestion, consumers MUST verify readiness gates; gate verification is **gate-specific** and MUST follow `engine_gates.map.yaml`.

This isn’t abstract: gates explicitly list `required_by_components: ingestion_gate`.

Also pinned: **instance-scoped outputs require instance proof** (Rails HashGate receipt bound to an `engine_output_locator` + digest) whenever scope includes `seed`, `scenario_id`, `parameter_hash`, or `run_id`.

---

## 6) What counts as “traffic” (IG must enforce this)

Engine event-like outputs are explicitly typed by **role**, and IG must not blur them:

* `business_traffic` → eligible to be ingested to EB
* `truth_products` → labels/case truth, not traffic
* `audit_evidence` / `ops_telemetry` → monitoring/forensics only, **MUST NOT** be treated as traffic

And: anything emitted onto a bus as `business_traffic` must conform to the canonical envelope, natively or via **lossless wrapper/mapping at ingestion** (i.e., IG is allowed to frame, but not “reinterpret”).

---

## 7) The EB join (what “ADMITTED” must mean)

Pinned EB truth:

* EB is append/replay; **not a validator/transformer**.
* **“Admitted” must mean durably appended.** IG must not emit “ADMITTED” unless EB has acknowledged the append.
* EB is system-of-record for **partition+offset**; offsets become downstream replay tokens (watermarks).

**Partitioning posture is pinned too:** EB does not infer partitioning from domain logic — IG stamps/chooses a deterministic `partition_key` at the edge.

---

## 8) Duplicates are normal; receipts must make them tame

EB delivery is at-least-once, so duplicates/redelivery are normal. IG should aim to prevent duplicate appends, but downstream must still tolerate duplicates.

Practical consequence for the overview: IG must have a stable way to:

* decide **FIRST-SEEN vs DUPLICATE**
* and, when DUPLICATE, point to the original admitted fact (via EB coordinates / receipt linkage)

This is why `event_id` stability matters.

---

## 9) Quarantine is a first-class “truth surface”

Quarantine is not a trash can; it’s a **durable evidence surface**:

* input evidence blobs live under `ig/quarantine/…`
* receipts can also be stored as objects under `ig/receipts/…`
* an `ig` DB schema can index receipts/quarantine for search/ops

Pinned rule from the platform join: IG must not “silently fix” bad inputs into good ones; if it can’t validate/anchor under policy, it quarantines.

---

## 10) Ingestion mode (push‑only)

This is the production‑clean posture:

* **Push ingest (only):** producers (notably WSP) submit already‑framed envelopes to IG (J3). IG remains the trust boundary and verifies joinability + proofs.

**Important overview point:** even though intake is push‑only, **the outcome semantics are identical** (ADMIT/DUPLICATE/QUARANTINE + receipts + durability meaning).

**Design correction (v0):** The traffic path is **WSP → IG (push)**. Legacy engine‑pull ingestion is retired and should not be treated as part of the runtime path.

---

## 11) The “minimum mental model” of what IG must guarantee externally

Before edges/paths, you only need this compact black-box contract:

**IG takes** (canonical envelope) **+ policy + required PASS proof(s)**
→ **returns** one of:

* ADMIT (means EB append acknowledged)
* DUPLICATE (means “already admitted”; points to prior admission)
* QUARANTINE (means “not safe”; points to evidence + reason)

All without:

* scanning “latest” worlds
* guessing schema versions
* inventing meaning
* silently correcting inconsistent pins

---

If you’re happy with this “pinned overview,” the next step is clean: we can now enumerate the IG joins/paths and, for each, ask “what must cross this edge?” and “what must never cross?” without opening the inner network yet.

---

Below is the **complete set of production‑ready “joins / paths” that involve IG**, treating IG as an **opaque vertex** (so: only *who connects to IG*, *what crosses the edge*, and *what the path means*).

Everything here is constrained by your pinned joins J3/J4 + “only one front door” truth, canonical envelope boundary, “no PASS → no read”, and the deployment unit mapping (bus/object/db surfaces).

**Streaming‑only note:** any legacy engine‑pull path descriptions below are **deprecated** and should be ignored. They are retained only for historical context until Phase 8 removes them.

---

## 1) IG adjacency map (all edges that touch IG)

### Inbound edges into IG

1. **Producer traffic input (bus or HTTP ingress)**
   “Producers → IG” is a first-class join (J3). Producers MUST supply a canonical envelope at minimum.
   Deployment mapping explicitly allows **bus input or HTTP ingress**. 

2. **Policy profiles (config)**
   IG consumes policy profiles (explicitly called out in the deployment mapping). 

3. **Schema authority / contract catalogue (read-only dependency)**
   The conceptual IG doc (non-authoritative, but realistic) matches the platform pin: IG consults the schema authority; unknown versions are not guessed.

7. **AuthN/AuthZ / allowlists (security boundary)**
   Production notes pin that IG is in the set of services that must be hardened with strong authn/authz in prod.

---

### Outbound edges out of IG

8. **Admitted events → Event Bus traffic topic**
   J4: “admitted means durably appended”; EB is append/replay, not validation. IG must not emit “ADMITTED” unless EB acked append.

9. **IG receipts + quarantine index (DB)**
   IG is truth for admission outcomes; deployment mapping pins a DB `ig` for receipt/quarantine index.

10. **Quarantine evidence store (object)**
    Deployment mapping pins `ig/quarantine/...` evidence objects.

11. **Optional pointer events → audit bus**
    Deployment mapping allows IG to emit pointer events to `fp.bus.audit.v1`. 

12. **Telemetry → observability pipeline**
    IG emits operational telemetry (counts by outcome, latency, backlog etc.) and production notes pin observability as part of the environment ladder.

---

## 2) All production paths that include IG (vertex opaque)

### Path family A — Producer push → IG (J3) outcomes

A1) **ADMIT path (normal hot path entry)**
`Producer → IG → EB(fp.bus.traffic.v1) → (IEG/OFP/DF/AL/DLA consume from EB)`
Meaning: event becomes replayable fact; downstream only trusts EB as basis.

A2) **DUPLICATE path (idempotency / stable outcome)**
`Producer → IG → Receipt(DB/object) [DUPLICATE + pointer to original EB coords]`
Meaning: no new EB append; receipt deterministically answers “already admitted.” (J4 explicitly expects this posture.)

A3) **QUARANTINE path (fail-closed + evidence)**
`Producer → IG → QuarantineEvidence(object) + Receipt(DB/object) [QUARANTINED + reason + evidence refs]`
Meaning: no silent drops; debugging/audit preserved.

A4) **UNJOINABLE / UNREADY run context path (special case of quarantine/hold)**
`Producer → IG → QUARANTINE/HOLD` when event is meant to participate in a run/world but isn’t joinable to a valid (practically READY) run context.

---

### Path family B — WSP “business_traffic” push ingestion (SR entrypoint → WSP → IG → EB)

This is the **production‑clean** design you pinned: SR READY precedes ingestion, and WSP streams the sealed world into IG.

B1) **READY triggers streaming**
`SR → (fp.bus.control.v1 READY) → WSP` (trigger)

B2) **WSP resolves join surface**
`WSP → read sr/run_facts_view (object)` (the map)

B3) **WSP reads engine outputs by reference and enforces “no PASS → no read”**
`WSP → read engine outputs + required PASS evidence (object) → WSP`
Meaning: WSP doesn’t scan “latest”; it follows SR’s refs and treats PASS receipts as prerequisites.

B4) **IG admits canonical envelopes**
`WSP → IG(push) → EB(fp.bus.traffic.v1)`
Note: admitted events must conform to canonical envelope (required `event_id,event_type,ts_utc,manifest_fingerprint`).

B5) **Quarantine on invalid stream items** (gate/schema/pin mismatch, etc.)
`SR READY → WSP → IG → (gate fail / missing prereq / invalid envelope) → ig/quarantine + receipt`
Meaning: fail-closed; no “best effort” reading or fixing.

---

### Path family C — Internal platform producers still enter through IG (same J3 semantics)

These are just instances of family A, but it’s useful to name them because they’re common in production:

C1) **Decision Fabric emits decisions and action intents (as events)**
`DF → IG → EB(fp.bus.traffic.v1)`
(Deployment notes show DF writing to the traffic bus; the platform pin says “only one front door,” so in production we treat DF as a producer that routes through IG’s admission boundary.)

C2) **Actions Layer emits action outcomes (as events)**
`AL → IG → EB(fp.bus.traffic.v1)`

C3) **Case Workbench submits manual actions as ActionIntents**
`Case Workbench → (ActionIntent submission) → IG → EB → AL consumes`

*(Same three possible outcomes: ADMIT / DUPLICATE / QUARANTINE.)* 

---

### Path family D — IG truth → Decision Log/Audit (J12)

IG is explicitly a contributor to the flight recorder join.

D1) **Audit builder consumes EB facts and pulls IG evidence by-ref**
`DLA consumes EB(fp.bus.traffic.v1) + reads IG receipts/quarantine refs (object/DB) → writes immutable audit records (dla/audit/…)`

D2) **Optional audit pointer events from IG**
`IG → fp.bus.audit.v1 → governance / indexing consumers` 

---

### Path family E — Reconciliation / “what happened to my event?”

These are production-necessary “query paths” (not hot-path traffic) and are directly supported by the pinned IG truth surfaces.

E1) **Producer/operator receipt lookup**
`Producer/Operator → IG receipt lookup surface → ig DB/index (+ refs to object evidence)`
Meaning: deterministic answer without scanning “latest.”

E2) **Quarantine triage / inspection**
`Operator → ig/quarantine evidence (object) + receipt metadata (DB) → decide remediation`

---

### Path family F — Quarantine remediation → re-ingest

Production platforms need a way to “fix and retry” without losing audit.

F1) **Re-submit corrected event**
`Quarantined evidence → (human/tooling fixes payload/pins/proofs) → Producer → IG → EB`
Meaning: new attempt yields new receipt; original quarantine record remains immutable evidence.

F2) **Bulk remediation (batch)**
`Batch submit → IG → per-event outcomes + optional batch summary receipt`
(Per-event receipts remain non-negotiable.)

---

### Path family G — Observability and control feedback loops that include IG

G1) **IG telemetry into observability**
`IG → metrics/logs/traces → observability pipeline`

G2) **Degrade Ladder reads observability** (IG indirectly influences system posture)
`Obs pipeline (including IG signals) → DL evaluator → (optional) fp.bus.control.v1 degrade posture updates`

*(IG doesn’t “set degrade”; it feeds the evidence that control-plane uses.)*

---

### Path family H — Environment ladder invariants (same paths, different envelope)

All the above paths exist in **local/dev/prod** with identical meanings; only operational envelope changes (security strictness, retention, scale, observability depth).

---

## 3) The “join labels” that matter most around IG

To make sure we’re speaking precisely in later steps:

* **J3:** `Producers → IG` (envelope + joinability + duplicate/quarantine posture) 
* **J4:** `IG ↔ EB` (admitted means durably appended; receipts point to EB coordinates; IG stamps partition_key)
* **J2 support:** `SR → run_facts_view + READY` is the platform entrypoint (used by WSP/IG for push joinability and by legacy engine pull ingestion when enabled)
* **J12:** `(DF/AL/IG) → DLA` (audit flight recorder uses IG evidence by-ref)

---

Yep. I’ll “unblur” **each IG edge** as a *design-level interface* (not full spec): **why the edge exists, what crosses it, what MUST be true, and what failure looks like**.

I’m going to use the pinned join definitions (J2/J3/J4) + your deployment mapping + engine interface pack as the hard constraints.

---

# Inbound edges into IG

## 1) Producers → IG (traffic input: bus or HTTP)

**Why this edge exists:**
This is the platform’s *only front door* for anything that will influence decisions/audit/labels/learning (J3). 

**What crosses the edge (minimum):**
A **Canonical Event Envelope** with required fields: `event_id, event_type, ts_utc, manifest_fingerprint`.
Optional but common pins: `parameter_hash, seed, scenario_id, run_id` depending on joinability.
Plus `payload` (unconstrained at envelope level). 

**What IG MUST enforce (externally visible behavior):**

* **Exactly one outcome per input:** ADMIT / DUPLICATE / QUARANTINE, always with a receipt/evidence trail (no silent drop). 
* **Joinability check:** if event is meant to participate in the run/world, it must be joinable to a valid run context (practically: READY). 
* **No “silent fixups”:** IG must not “repair” malformed pins into good ones; if it can’t anchor it under policy → QUARANTINE. 

**What’s intentionally not fixed at this edge (v0):**

* Whether ingress is *bus* or *HTTP* is deployment choice, but meaning is identical. 
* Payload schema validation can be policy-driven (envelope validation is non-negotiable; payload validation is “profiled”).

**Failure modes you should expect:**

* Missing required envelope fields → QUARANTINE (reason: `ENVELOPE_INVALID`). 
* Missing required pins for a run-joinable event → QUARANTINE (`PINS_MISSING`).
* Unknown run / not READY → QUARANTINE or HOLD (still a quarantine-class outcome; the receipt explains “why”). 

---

## 2) IG → SR join surface (read `sr/run_facts_view`)

**Why this edge exists:**
J2 says downstream must start from SR’s **READY + run_facts_view** and must not scan engine outputs or infer “latest.” IG follows that too (for WSP-driven joinability and legacy engine pull-ingestion when enabled).

**What crosses the edge (conceptually):**

* `run_facts_view` is a **map**: pinned references to engine outputs + required PASS evidence to treat them as admissible. 

**What IG uses it for (design-level):**

* **Existence/authority of run context** (joinability): “Does this run exist? Is it READY? What pins define it?”
* **Engine ingestion plan inputs**: “Which engine outputs are eligible to be treated as traffic for this run, by reference?”

**Pinned “must nots”:**

* IG must not “discover” worlds by scanning storage; it follows the join surface. 

---

## 3) SR READY → IG (control trigger on `fp.bus.control.v1`)

**Why this edge exists:**
READY is the **trigger** (monotonic). run_facts_view is the **map**. 

**What crosses the edge (conceptually):**

* A READY signal that indicates “run context is now valid” and is meaningful only alongside the run ledger/join surface.

**What IG does with it (externally visible):**

* In the **pull model**, this is what starts engine business-traffic ingestion (SR does not become “the pipeline”).
* In push-ingest, it can be used as a fast gate: “if not READY, do not admit run-scoped traffic.”

**Pinned “must nots”:**

* IG must not treat READY as a replacement for run_facts_view; READY is not self-sufficient. 

---

## 4) IG ↔ Engine artifacts + gate receipts (object store reads)

**Why this edge exists:**
Engine produces event-like artifacts (often as parquet tables) and gate evidence; IG must enforce “no PASS → no read.”

**What crosses the edge (conceptually):**

* Engine outputs (surfaces/streams) by **locator/ref** (not “latest”).
* Gate artifacts: `_passed.flag`, validation bundles, and receipts.

**Pinned enforcement inside IG (shows up as outcomes):**

* IG must verify gates **gate-specifically** using `engine_gates.map.yaml` (verification_method differs by gate).
* Gates explicitly list `required_by_components: ingestion_gate` → IG is not allowed to “assume SR did it.” 
* IG must distinguish **business_traffic vs truth_products vs audit_evidence/ops_telemetry** and must not ingest audit/telemetry as traffic. 
* Any engine output emitted onto the bus as `business_traffic` must conform to the canonical envelope (natively or via lossless mapping at ingestion).

**Common failure outcomes:**

* Missing PASS evidence / FAIL gate → QUARANTINE (`GATE_MISSING` / `GATE_FAIL`).
* Output role is `audit_evidence`/`ops_telemetry` but attempted as traffic → QUARANTINE (`ROLE_NOT_TRAFFIC`). 
* Envelope framing impossible (no event_time equivalent for `ts_utc`, no stable row id for `event_id`) → QUARANTINE (`FRAME_FAIL`) unless policy provides a deterministic fallback. 

---

## 5) Policy profiles → IG (config)

**Why this edge exists:**
The deployment map explicitly calls out policy profiles as IG inputs. 

**What crosses the edge (conceptually):**
Policy profiles define the “guardrails knobs” for IG, e.g.:

* required pins per event_type
* which event_types are allowed from which producers
* payload schema strictness per event_type/schema_version
* quota/backpressure posture
* partition-key stamping strategy
* quarantine reason taxonomy

**Pinned behavior:**

* Policy changes may alter admission decisions, so policy profile identity/version should be recorded in receipts (as provenance), even if we don’t spec the exact field yet.

---

## 6) Schema authority / contract catalogue → IG (read-only)

**Why this edge exists:**
The envelope is pinned; payload schemas can be versioned; IG must not guess unknown schema versions.

**What crosses the edge (conceptually):**

* Canonical envelope schema (always enforced). 
* Optional per-event payload schema selected by `(event_type, schema_version)` if policy says payload validation is required. 

**Outcome semantics:**

* Unknown schema_version or schema validation failure → QUARANTINE (`SCHEMA_UNKNOWN` / `SCHEMA_FAIL`).

---

## 7) AuthN/AuthZ / allowlists → IG (security boundary)

**Why this edge exists:**
In production, IG is a hardened boundary—only approved producers can inject traffic. (This is implied by its “trust boundary” role and production posture.)

**What crosses the edge (conceptually):**

* Producer identity credentials (mTLS identity, API key, signed token, etc. — implementation choice).
* Authorization policy: which producer may submit which event types / which scopes.

**Pinned outcome mapping:**

* Auth failures still result in **a decision** (cannot be “silent drop”). In v0 we map to QUARANTINE (`AUTH_DENY`) with **minimal stored evidence** to avoid persisting potentially malicious payloads.

---

# Outbound edges out of IG

## 8) IG → Event Bus traffic (`fp.bus.traffic.v1`)

**Why this edge exists:**
This is J4: “admission becomes durable fact.” EB is append/replay; not a validator/transformer.

**What crosses the edge:**

* Canonical envelope events (payload included). 
* A deterministic partition routing decision (IG stamps/chooses partition key; EB should not infer it). 

**Pinned atomic meaning:**

* IG must not issue “ADMITTED” unless EB acknowledged the append. 
* EB’s return coordinates (partition/offset) become the universal replay token basis downstream uses.

**Duplicate posture:**

* EB is at-least-once; duplicates happen. IG should aim to prevent duplicate appends and instead emit DUPLICATE receipts pointing to the original. 

---

## 9) IG → receipts/quarantine index DB (`ig`)

**Why this edge exists:**
The deployment map pins a DB index as part of “Admission truth.”

**What crosses the edge (conceptually):**

* Receipt records keyed by a stable idempotency/dedupe key (at minimum tied to `event_id` and pins).
* For ADMIT: link to EB coordinates.
* For QUARANTINE: link to evidence objects + reason codes.
* For DUPLICATE: link to original receipt/EB coords.

**What this DB enables (outer meaning):**

* “What happened to my event?” queries without scanning bus/history.
* Operational triage dashboards (quarantine rate, top reasons).

---

## 10) IG → quarantine evidence store (`ig/quarantine/...`)

**Why this edge exists:**
Quarantine is a first-class evidence surface, explicitly pinned in deployment mapping.

**What crosses the edge (conceptually):**

* Raw input as received (or by-ref pointer if the raw input is already durable elsewhere).
* Validation/proof failure diagnostics (what was missing/invalid).
* A “quarantine bundle” that can be used for remediation and re-ingest.

**Pinned behavior:**

* Evidence is immutable; remediation produces a new ingest attempt and a new receipt (original evidence stays). This keeps audit clean.

---

## 11) IG → audit pointer events (`fp.bus.audit.v1`) [optional]

**Why this edge exists:**
Deployment map calls it optional. It’s not the admission truth; it’s a *notification/indexing* channel.

**What crosses the edge (conceptually):**

* **Pointers only**, not full payloads:

  * receipt_id / dedupe_key
  * outcome + reason code
  * EB coords (if admitted)
  * quarantine evidence refs (if quarantined)

**What it’s for:**

* Let DLA/governance/indexers react without polling the `ig` DB.

---

## 12) IG → observability pipeline (metrics/logs/traces)

**Why this edge exists:**
Production posture requires observability; IG’s rates/lag/errors matter and may influence control-plane decisions (e.g., Degrade Ladder reads obs pipeline).

**What crosses the edge (conceptually):**

* Counters: admitted/quarantined/duplicate per event_type/producer
* Latency histograms: ingest-to-ack, gate-verify time, EB-append time
* Backlog/lag signals (especially for legacy engine pull ingestion)
* Error reason taxonomy (top quarantine reasons)

**Pinned “must not”:**

* Telemetry must not masquerade as business traffic; it influences behavior only through explicit control surfaces (DL), not by “sneaking in” as events.

---

# Quick “composition” sanity

These edges compose into the main production paths you already listed (A/B/C/D/E/F/G), but the important thing is: **every path is just a composition of these edges**, and each edge has a crisp meaning now:

* J3 defines what producers must supply and what IG must decide. 
* J2 defines how IG is allowed to know “what run/world exists” (READY + run_facts_view, no scanning). 
* J4 defines what “ADMITTED” means (durably appended + offsets).

---

Alright — A1–A4 are the **four branches of the same Producer→IG push-ingest path**, where IG (as the trust boundary) must decide **exactly one** of **ADMIT / DUPLICATE / QUARANTINE** and leave a receipt/evidence trail.

I’ll expand them in a way that “unblurs” the edge, while keeping IG’s internals opaque.

---

## The shared prefix for A1–A4 (what happens before the branch)

Every producer push-ingest attempt has a common logical pipeline:

1. **Intake**
   IG accepts traffic via “producer traffic input (or HTTP ingress)” in deployed topology. 
   It binds the input to a *producer identity* (authn/authz is part of being a trust boundary; mechanics can vary). 

2. **Envelope boundary validation (non-negotiable)**
   Producers must supply a canonical envelope with required fields:
   `event_id, event_type, ts_utc, manifest_fingerprint`.
   Optional fields exist for run/world joinability and payload versioning (`parameter_hash, seed, scenario_id, run_id, schema_version, producer, payload…`).

3. **Joinability enforcement check**
   If the event *claims* to be run/world-joinable, IG must enforce that it is joinable to a **valid run context** (and in practice, a **READY** run). Otherwise → quarantine/hold, not “best effort.”
   IG is allowed to consult `sr/run_facts_view` “to enforce run joinability.”

4. **Idempotency/dedupe decision point**
   The platform assumes at-least-once; duplicates are normal. IG must behave deterministically under retries and should aim to prevent duplicate appends.
   Practically, IG evaluates a **dedupe key** (recipe is IG-local, but must be stable and receipt-backed).

5. **Partition routing stamp (pre-commit)**
   EB does not infer partitioning; IG must stamp/choose a deterministic partition routing key at the edge.

Then the path branches into A1/A2/A3/A4.

---

## A1) ADMIT path (valid + joinable + first-seen → durable fact)

**Path:**
`Producer → IG → EB(fp.bus.traffic.v1) → consumers`

### What “ADMIT” must mean (pinned)

* EB is append/replay, not validator/transformer.
* “Admitted” must mean **durably appended**: IG must not emit an ADMITTED outcome unless EB acknowledged the append.
* EB coordinates (partition+offset) are the universal replay/progress token used downstream.

### Design-level sequence (opaque internals, crisp external meaning)

1. **IG accepts the envelope** (required fields present; policy allows this producer/type).
2. **IG verifies joinability** (if run-scoped): the run exists and is READY (via SR join surface).
3. **IG confirms “first-seen”** for its dedupe key (no prior ADMIT/QUARANTINE outcome for the same key).
4. **IG stamps partition routing** (deterministic) and appends the event to `fp.bus.traffic.v1`.
5. **EB returns coordinates** (partition, offset). Those coordinates are the fact’s “address.” 
6. **IG persists the receipt** as admission truth (DB index `ig` + optional object receipt), and the receipt **must carry or reference EB coordinates**.

### What the producer gets back

* In HTTP ingest: it can get the receipt synchronously.
* In bus ingest: the durable receipt exists in the `ig` index / object store, and producers or operators can reconcile via lookup.

### What downstream can assume after A1

* The event is canonical-envelope-shaped (boundary check applied).
* The event is joinable (pins are trustworthy *as pins*).
* The event is replayable and addressable by EB coordinates. 

---

## A2) DUPLICATE path (same event resent → no new fact)

**Path:**
`Producer → IG → Receipt [DUPLICATE + pointer to original EB coords]`

### When A2 triggers

* Producer retries (network failures, timeouts, at-least-once bus delivery), and the input maps to the same IG dedupe key.

### What DUPLICATE must mean (pinned)

* IG should aim to prevent duplicate EB appends and instead emit DUPLICATE receipts pointing to the original.
* Outcome must be deterministic under replay: “same event resent” yields a stable idempotent outcome.

### Design-level behavior

1. IG receives the envelope and passes envelope validity + joinability checks (or it would become A3/A4).
2. IG computes the dedupe key and finds a prior **ADMITTED** outcome.
3. IG returns **DUPLICATE** with a pointer to the original admission:

   * either the original receipt id, or
   * the original EB coordinates (or both).
4. No EB append happens.

### The “hard” duplicate case: concurrent/in-flight duplicates

Production reality: two copies arrive before the first one finishes writing its receipt.

**Designer pin (v0):** IG must still avoid “double-admit.” That means internally it needs an “in-flight” idempotency guard keyed by the dedupe key (implementation detail), but externally the semantics remain:

* one copy will become A1 (ADMITTED),
* all others become A2 (DUPLICATE) once the first admission is known.

---

## A3) QUARANTINE path (fail-closed + evidence)

**Path:**
`Producer → IG → ig/quarantine evidence + receipt index`

### When A3 triggers (categories)

Anything that violates the pinned trust boundary rules:

* **Envelope invalid / missing required fields**
* **Schema version unknown / payload invalid under policy** (IG must not guess)
* **Pins missing or inconsistent** for a joinable event
* **Authorization failure / producer not allowed** (still must be traceable; no silent drop)
* **Policy denies** (e.g., event_type forbidden from this producer)

### What IG must produce (pinned)

* A durable quarantine evidence bundle under `ig/quarantine/...` (raw input + diagnostics).
* A receipt in the `ig` receipt/quarantine index indicating QUARANTINED, reason code(s), and evidence pointers.
* No EB append.

### Retryable vs terminal quarantines (important for ops)

Even without a full spec, production needs this conceptual split:

* **Retryable quarantine**: “missing schema registration”, “run not READY yet”, “transient dependency failure”.
* **Terminal quarantine**: “auth denied”, “malformed envelope”, “pin mismatch that indicates corruption”.

This is how you keep quarantine triage sane without mutating the trust boundary.

---

## A4) UNJOINABLE / UNREADY run context (quarantine/hold subtype)

**Path:**
`Producer → IG → QUARANTINE/HOLD (run context problem)`

This is explicitly called out in J3: if a run/world-joinable event isn’t joinable to a valid (READY) run, it’s **quarantine/hold**, not “best effort.”

### The three distinct A4 cases (don’t blur them)

1. **UNKNOWN_RUN**
   Event claims `(scenario_id, run_id, manifest_fingerprint, parameter_hash)` but IG can’t resolve that run context in SR’s join surfaces.

2. **RUN_NOT_READY**
   Run exists but is not READY (SR hasn’t published the join surface / required PASS posture).

3. **PIN_MISMATCH vs SR join surface**
   Run is READY, but the pins on the event contradict the pins for that run in SR’s authoritative join surface. This is a strong corruption indicator → quarantine (not hold).

### “Hold” meaning (how to include it without breaking the 3-outcome rule)

We keep the platform’s tri-state outcome intact by treating HOLD as:

* **QUARANTINE with reason RUN_NOT_READY**, marked retryable, stored in a distinct “hold bucket” internally.

**Optional production optimization:** a worker can auto-retry held events when READY appears, but outward truth stays append-only:

* original quarantine/hold receipt remains,
* a later ADMITTED receipt can reference “supersedes/rehydrates” that hold record (no silent mutation).

---

## A-family “done-ness” check (design-level)

After this expansion, A1–A4 are unblurred if you can answer, for any producer push-ingest:

* What does IG require at the boundary (envelope + pins)?
* What does “admitted” *prove* (durable EB append + coords)?
* How are duplicates reconciled without re-admit?
* What evidence exists for every rejection (and where)?
* How are unready/unjoinable run contexts handled without “best effort”?

---

Absolutely. Path family **B** is where the platform’s “join surface” story becomes *real*: SR publishes **READY + `run_facts_view`**, and IG turns *pinned engine artifacts* into *admitted EB facts*—without scanning, without guessing, and without bypassing gates.

Below I expand **B1–B5** as an authoritative *design-level* walkthrough (still not a full spec).

---

## The non-negotiable frame for B paths

Before we touch B1–B5, these are the pinned constraints that shape them:

* **READY is the trigger; `run_facts_view` is the map.** Downstream starts from READY → `run_facts_view` and follows refs; scanning “latest” engine directories is forbidden.
* **No PASS → no read, and gate verification is gate-specific** (must follow `engine_gates.map.yaml`).
* **Instance-scoped outputs require instance proof** bound to an `engine_output_locator` and digest; for those, `engine_output_locator.content_digest` must be present.
* Anything emitted onto EB as **business_traffic** must be (or be wrapped into) the **Canonical Event Envelope** with required `{event_id,event_type,ts_utc,manifest_fingerprint}`.
* **“Admitted” means durably appended to EB**; EB returns the authoritative `(partition, offset)`, and IG receipts should point to it.
* IG is deployed as an always-on service that **reads `sr/run_facts_view`**, writes admitted events to `fp.bus.traffic.v1`, and persists quarantine evidence + a receipt index.

---

# B1) READY triggers ingestion

`SR → (fp.bus.control.v1 READY) → IG`

### What READY *means to IG*

READY is **permission to start** ingestion work for that run. It is not “nice to know”; it’s the pinned entrypoint.

### What IG must do when READY arrives

Treat READY as spawning a **run-scoped ingestion job** keyed by the run context (ContextPins + seed). The job’s first act is to fetch `run_facts_view` (B2).

### What must be true / enforced at this edge

* **Idempotent under re-delivery:** multiple READY notifications for the same run must not create double ingestion (same run_id → same ingestion job/resume). This is required because the platform assumes at-least-once delivery.
* **READY without join surface is meaningless:** if READY arrives but `run_facts_view` can’t be fetched/validated, IG treats that as a quarantine-class failure of the ingestion attempt (B5), not as “best effort ingest anyway.”

### Designer pin for B1 (authoritative)

**IG begins legacy engine pull ingestion only after READY.** No “pre-ready buffering” in IG for legacy engine pull (that was the whole point of choosing Pull).

---

# B2) IG resolves join surface

`IG → read sr/run_facts_view (object)`

### What `run_facts_view` must provide (minimum, design-level)

Your platform already pins the meaning: **pins + refs/locators + PASS evidence**.
For IG to do B3/B4 correctly, the minimum content is:

1. **Run pins / identity**
   The world/run identity pins (ContextPins + seed) that define joinability.

2. **Traffic targets (explicit list)**
   A list of **engine outputs to be treated as business traffic** for *this run*—expressed as `engine_output_locator` objects (output_id + fully resolved path + identity tokens).

3. **Proofs that make those targets admissible**
   The relevant **gate receipts** (PASS/FAIL) in portable form (`gate_receipt`) + enough artifact pointers to verify gate-specific rules if needed.

4. **Instance proof hooks**
   For any target whose scope includes `seed/scenario_id/parameter_hash/run_id`, `run_facts_view` must include:

* `engine_output_locator.content_digest` (so instance proof can bind), and
* the Rails instance proof receipt (bound to that locator+digest).

### How IG uses `run_facts_view` (and what it must *not* do)

* IG **does not “discover” traffic** by scanning engine directories. It ingests only what the join surface references.
* IG still **verifies classification**: if SR mistakenly lists a truth product or audit evidence as traffic, IG must refuse (B5) because the engine interface explicitly forbids treating `audit_evidence`/`ops_telemetry` as traffic.

### Concrete examples of what SR might list as traffic targets

The engine interface explicitly calls out event-like *parquet tables* as possible business traffic (e.g., `arrival_events_5B`), and it distinguishes business traffic from truth products like `s4_event_labels_6B`.
Also, the catalogue shows that “event streams” can be `class: surface` with PKs like `(flow_id, event_seq)` (e.g., `s2_event_stream_baseline_6B`).

### Designer pin for B2 (authoritative)

**Traffic selection is SR’s job; traffic admissibility enforcement is IG’s job.**
SR lists traffic outputs in `run_facts_view`; IG refuses anything that violates the engine role taxonomy or lacks proofs.

---

# B3) IG reads engine outputs by reference and enforces “no PASS → no read”

`IG → read engine outputs + required PASS evidence (object) → IG`

Think of B3 as “prove the artifact is admissible *before* you touch it.”

### Step B3.1 — Determine authorising segment gate(s)

IG maps each `output_id` to a segment HashGate via `engine_gates.map.yaml` and verifies the gate’s declared method.

Example:

* `gate.layer2.5B.validation` authorizes `arrival_events_5B`.
* `gate.layer3.6B.validation` authorizes `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B` (among others).

### Step B3.2 — Verify gate PASS (gate-specific)

* Gate verification is **not universal**; IG must follow the gate’s declared hashing law (`sha256_bundle_digest`, `sha256_member_digest_concat`, etc.).
* Gate definitions also list **upstream dependencies**; in production posture, IG should require PASS evidence for the dependency closure (at least at the receipt level) to fail closed.

### Step B3.3 — Enforce instance proof where required

For traffic outputs whose scope includes seed/scenario/parameter/run (typical for traffic), IG must enforce the extra Rails instance proof binding to the locator + digest, and require `content_digest` to be present for binding.

### Step B3.4 — Read the artifact by locator (no scanning)

The `engine_output_locator` is the portable pin to “where the bytes live.” It must include `output_id` and resolved `path`, and the path must be consistent with the catalogue path template.

### Step B3.5 — Apply engine lineage invariants while reading

Even though we’re not writing a spec here, the design posture is:

* **File order is non-authoritative**; IG must treat declared keys/fields as truth.
* **Path-embed equality**: where lineage exists both in path tokens and row fields, they must match. (If mismatch, that’s B5 quarantine.)

### Designer pin for B3 (authoritative)

**IG may only read an engine traffic output if:**

1. the authorising segment gate is PASS (and dependency closure is satisfied), and
2. instance proof exists when required, and
3. the locator resolves cleanly and is internally consistent.

---

# B4) ADMIT engine traffic to EB (wrap rows → canonical envelope → append)

`IG → wrap rows → EB(fp.bus.traffic.v1)`

This is the “dataset → replayable fact log” conversion.

## B4.1 Row → CanonicalEventEnvelope mapping (design-level)

Every emitted event must satisfy the envelope schema (required fields + optional pins).

### Required envelope fields

* **manifest_fingerprint**: from the run context / locator.
* **ts_utc**: from the row’s domain-time field (for `arrival_events_5B`, `ts_utc` is explicitly part of the PK).
* **event_type**: chosen routing name.
  **Designer v0 pin:** for legacy engine-pull ingestion, set `event_type = output_id` unless an explicit mapping table exists. This avoids hidden translation drift and is still semantically stable.
* **event_id**: must be stable for idempotency/dedup at ingest/bus boundaries.

### Pins in the envelope (joinability)

Even if the engine output’s scope doesn’t include all pins, the platform join story expects ContextPins to be present for run-joinable traffic. So IG stamps:

* `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash` from the run context (`run_facts_view`).
* `seed` for seed-variant traffic outputs.

## B4.2 How IG mints `event_id` deterministically (critical)

Because many engine “traffic tables” won’t carry a UUID, IG must mint a stable id.

**Designer pin:** for legacy engine-pull ingestion, define
`event_id = H(output_id + PK_tuple + world pins)`
where `PK_tuple` comes from the engine output’s declared primary key.

Examples from your interface/catelogue:

* `arrival_events_5B`: PK includes `(scenario_id, merchant_id, ts_utc, arrival_seq)` (interface summary) and the catalogue includes `(seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq)` as the primary key.
* `s2_event_stream_baseline_6B`: PK includes `(flow_id, event_seq)` along with seed/manifest/scenario in the catalogue.

**Important subtlety (designer pin):** do **not** include `run_id` in the hash.
Run identity should separate dedupe scopes, but the same world row should keep the same `event_id` across reruns/reuse. (Downstream idempotency keys incorporate ContextPins anyway. )

## B4.3 Payload posture (fast path + traceability)

Envelope schema isolates payload under `payload`.
**Designer pin:** payload includes:

* the event’s business fields (whatever is needed downstream), **and**
* a **source pointer** (inside payload) back to engine origin, e.g. `{source_locator, row_pk}` for audit/replay explanation.

This satisfies the platform’s by-ref mindset while still making the bus usable for hot-path consumers.

## B4.4 Partition routing (IG stamps it)

EB expects a stable partition key at the edge; it does not invent it.

**Designer v0 recommendation:** partition by the “stream entity” that carries sequence:

* for arrival-style traffic: `merchant_id`
* for flow event streams: `flow_id`
  …salted with run/world pins so different runs don’t unintentionally co-locate.

(Exact hashing formula is implementer freedom, but the *intent* is pinned: entity locality + determinism.)

## B4.5 Commit rule (the atomic meaning of “ADMITTED”)

IG appends to EB and only then writes an “admitted” receipt:

* EB is append/replay (not validator); IG must not claim admitted until EB acknowledges append.
* IG receipts should carry or reference EB `(partition, offset)` as the event’s durable address.

---

# B5) Engine-pull quarantine (fail-closed, no “best effort”)

`SR READY → IG → (gate fail / missing prereq / invalid framing) → ig/quarantine + receipt`

B5 is “what happens when any prerequisite for admissible traffic is missing or inconsistent.”

## What gets quarantined (categories)

### A) Join-surface failures (SR published READY but map is unusable)

* `run_facts_view` missing/unreadable
* pins mismatch between READY and `run_facts_view`
  This is a **run-level ingestion failure**: stop ingestion for that run and record evidence.

### B) Proof failures (“no PASS → no read” violated)

* required gate receipt missing / FAIL
* gate verification fails under the gate-specific hashing law
* required upstream dependency receipts missing
* instance proof missing/mismatch (or content_digest missing when required)

### C) Traffic classification violations

* `run_facts_view` lists an output that is not allowed as business traffic (truth products like `s4_event_labels_6B` are explicitly not traffic).

### D) Framing failures (can’t make a valid envelope deterministically)

* missing/invalid domain time for `ts_utc` (can’t populate required envelope field)
* can’t mint a stable `event_id` because required PK fields are missing
* lineage mismatch (row pins contradict locator pins)

## Evidence posture (what B5 must leave behind)

Per deployment pins, IG quarantines by writing:

* evidence objects under `ig/quarantine/...`
* receipts/index rows in `ig` DB (so ops can ask “what happened?” without scanning)

**Designer pin:** B5 quarantines must record enough to reproduce the failure:

* run pins
* offending `engine_output_locator`
* the gate receipts / instance proof refs that were missing or failing
* and (if row-level) the row PK and framing notes

---

## One last designer pin: selection and “baseline vs fraud”

For 6B you have multiple candidate traffic streams (baseline vs with_fraud), and the 6B gate authorizes both alongside truth products.
**IG will not guess which one is “the” traffic stream.** SR must choose and list the intended traffic targets explicitly in `run_facts_view`; IG then enforces admissibility + classification.

---

Great — Path family **C** is where we prove the platform really means: **“IG is the single admission choke point, even for internal services.”**
Your authoritative platform view explicitly lists **DF outputs, AL outcomes, and case emissions** as producers that flow **→ IG → EB**.

Below I “unblur” **C1–C3** as **design-level edge contracts**: what crosses, what IG must enforce, what downstream assumes, and where responsibility *stops* (so we don’t drift into AL/DF semantics inside IG).

---

## Shared pins for C1–C3 (why internal producers still go through IG)

1. **IG still enforces publish/admit control**
   “No identity → no admission.” Producer identity comes from transport identity and must match the envelope’s declared `producer`; mismatch → quarantine. AuthZ is an allowlist over `(producer_principal, event_type, scope)`; unauthorized → quarantine + receipt; no silent drop.

2. **Outcomes are always explicit and receipted**
   Internal services don’t get “trusted bypass.” If DF/AL/Case emit malformed or unauthorized traffic, it becomes **QUARANTINE** with evidence/receipt (and that’s a good thing in prod: it catches drift early).

3. **Everything is “real traffic” on `fp.bus.traffic.v1`**
   Deployment wiring pins that DF emits **decision + action-intent events** on `fp.bus.traffic.v1`, AL consumes **action intents** from that bus and emits **outcomes** back to it, and DLA consumes **decisions + intents + outcomes** (plus IG receipts/quarantine refs) to build the flight recorder.

---

# C1) Decision Fabric emits decisions + action intents

**Path:** `DF → IG → EB(fp.bus.traffic.v1)` 

### What crosses this edge (two event families)

**(a) DecisionResponse events**
DF must carry provenance in what it emits (bundle ref, snapshot hash, graph_version, degrade posture) — this is explicitly called out as something DF must persist *in emitted events*.

**(b) ActionIntent events**
Your platform pins J11: DF declares intents; AL executes; every ActionIntent must carry a **deterministic `idempotency_key`** plus enough join identifiers to bind it to context.

### What IG must enforce at this edge (and what it must not)

**IG enforces:**

* DF producer identity/authz (service principal + allowlist by event_type + scope).
* Envelope-level correctness + required join pins (ContextPins where applicable).
* Version acceptance policy (unknown/unsupported versions don’t silently flow; they quarantine).

**IG must not:**

* Decide whether an ActionIntent is “allowed to execute.” That’s AL’s job. IG only admits a *request fact* into the platform.

### The key “design unblur”: what DF must include so IG can do its job

**For DecisionResponse:** include “decision was made under posture X, with snapshot Y, graph_version Z, bundle ref B” so DLA can reproduce/justify later.
**For ActionIntent:** include:

* `actor_principal` (DF’s service identity as the actor for automated intents)
* `origin=automated_decision`
* `idempotency_key` (deterministic)
* linkage back to the triggering decision/event identifiers (for audit + AL linkage)

### Failure behaviors (meaningful in prod)

* DF emits an event_type not on its allowlist → IG QUARANTINE + receipt.
* DF emits ActionIntent missing required execution linkage fields (e.g., no idempotency_key) → IG QUARANTINE (because AL can’t safely apply “effectively-once” without it).

---

# C2) Actions Layer emits ActionOutcomes

**Path:** `AL → IG → EB(fp.bus.traffic.v1)` 

### What crosses this edge

AL produces **ActionOutcome** events back onto the traffic bus, and AL also persists truth in its own `actions` DB (“idempotency + outcomes”).

### What is pinned about outcomes (this is the crux)

* **Only AL executes.** Everyone else (DF, Case UI, Ops) can only *request*.
* AL enforces effectively-once using **(ContextPins, idempotency_key)**; duplicate intents must never re-execute; they re-emit the canonical outcome.
* Outcomes are **immutable**, and they are **fully attributable**: ActionOutcome records the actor principal + policy version used to authorize + intent linkage.

### What IG must enforce here

* Producer identity/authz: AL is a producer too; it must be allowed to publish ActionOutcome event types.
* Envelope validity + join pins.
* Optional (policy-driven): that an ActionOutcome references an intent linkage (so it’s not a “free-floating side effect claim”). This isn’t “execution auth”; it’s structural sanity.

### The design unblur: what an ActionOutcome must carry (so the rest of the graph works)

At minimum (conceptually):

* `idempotency_key` (same as the intent)
* `decision=EXECUTED|DENIED|FAILED` and attempt metadata
* linkage back to the intent / triggering decision/event id
* `actor_principal` and the **authz policy version used**

That lets DLA stitch: **intent → executed/denied outcome**, without embedding raw payloads.

---

# C3) Case Workbench submits manual actions as ActionIntents

**Path:** `Case Workbench → (ActionIntent submission) → IG → EB → AL consumes`

### What crosses this edge

From deployment wiring: “Manual actions submitted as ActionIntents (via AL/IG path).”
From access/control overlay: “Manual action is just another ActionIntent with higher privilege, not a bypass.”

### The key separation of identities (this is where platforms usually drift)

* **Producer principal (IG cares):** the Case Workbench backend service identity submitting the event.
* **Actor principal (AL cares):** the human (investigator/ops) requesting the manual action, carried inside the ActionIntent.

**Designer pin:** IG must enforce producer identity + event_type allowlist, but AL enforces **actor-based allowlist** for execution.

### What the manual ActionIntent must carry (so “not a bypass” is actually true)

* `actor_principal` (human identity)
* `origin=human_case` (or similar)
* `action_type` + target scope
* deterministic `idempotency_key` (so double-click / retry doesn’t execute twice)

### Where denial happens (important)

* If the *human* isn’t allowed to do the action: **AL denies** and emits a **Denied ActionOutcome** (still immutable, still idempotent).
* If the *submission* is malformed/unauthorized at the platform boundary: **IG quarantines** (because it can’t safely become a platform fact).

---

## The “production-ready” mental picture (why C paths matter)

Because DF/AL/Case all flow through IG, you get a single consistent story:

* **IG controls what becomes a fact** (decisions, intents, outcomes are facts).
* **AL controls what becomes a side effect** (execute/deny/failed outcomes, effectively-once).
* **DLA can reconstruct everything** from bus facts plus IG receipts/quarantine refs.

---

Absolutely. I’ll unblur **D1/D2** (IG → Decision Log/Audit, J12) and **E1/E2** (reconciliation paths) as **production-grade edges**: what crosses, what each side can assume, and what must be true for the platform to stay “drift-proof”.

I’m anchoring on your pinned joins (J3/J4/J12) and the deployment substrate map (what’s written where).

---

## D1) DLA consumes EB facts + pulls IG evidence by-ref → writes immutable audit records

**Path:**
`DLA consumes fp.bus.traffic.v1 + reads IG receipts/quarantine refs (object/DB) → writes dla/audit/…`

### Why this path exists (what J12 is really saying)

J12 pins that the “flight recorder” must persist **by-ref evidence** for decisions/actions/ingestion, including things like **IG receipts**, hashes, bundle refs, degrade posture, plus a **correction/supersedes posture**. 

So DLA’s job is not “copy the whole bus.” It’s:
**turn the hot path into an auditable story** with stable pointers to the authoritative truth surfaces.

### What DLA reads (the join inputs)

1. **EB traffic facts** (decisions, intents, outcomes, traffic, etc.) from `fp.bus.traffic.v1`.
2. **IG truth surfaces by reference**:

   * receipts and quarantine references as object refs (and optionally the `ig` DB index for lookup).
3. **Optional EB coordinates** (partition/offset) when needed as immutable replay tokens (this is already a pinned idea in J4: receipts can point to EB coords).

### What DLA writes (the audit truth)

* Immutable audit records under `dla/audit/…` in object storage; optional `audit_index` DB to search them.

### The key unblur: what DLA *expects* IG to provide (without knowing IG internals)

To build a coherent audit story, DLA needs IG receipts to be **reconcilable** and **pointer-rich**:

**Minimum receipt “capability” (design-level):**

* outcome enum: `ADMITTED | QUARANTINED | DUPLICATE`
* stable keys: at least `event_id` + `producer` + `event_type` and/or a `dedupe_key`
* pointers:

  * for ADMITTED: an **EB ref** (topic/partition/offset) OR an equivalent admitted-record pointer
  * for QUARANTINED: a `quarantine_record_ref` (and ideally `raw_input_ref`)
  * for DUPLICATE: pointer to the original admission (original receipt ref and/or original EB ref)

This aligns with J4’s “receipts point to EB coordinates” and the deployment map that IG is truth for admission outcomes.

### How DLA stitches the story (the actual “join”)

DLA’s join key is the **event identity** carried in the canonical envelope:

* required: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
* plus optional pins (`parameter_hash`, `seed`, `scenario_id`, `run_id`) when the event is run/world-scoped. 

**Designer pin (authoritative for J12):**
DLA treats “an EB fact is fully auditable” only when it can attach:

* the EB fact itself (or pointer),
* the **IG admission receipt ref** for that fact (or for its dedupe/original),
* and any upstream provenance pointers already carried by DF/AL (bundle ref, snapshot hash, degrade posture, etc.).

### Correction / supersedes posture (what it means in practice)

DLA must be **append-only**, but it can represent “this story was corrected” by writing a new audit record that:

* references the prior audit record(s) it supersedes, and
* explains why (e.g., “late outcome”, “manual correction”, “re-ingest after quarantine”).

This is how the platform stays honest without mutating history.

---

## D2) Optional IG pointer events → fp.bus.audit.v1 → governance/indexing consumers

**Path:**
`IG → fp.bus.audit.v1 → governance / indexing consumers`

### Why this exists (and why it’s optional)

Polling the `ig` DB/object store for every outcome is operationally heavy. So IG may emit **lightweight pointer events** to an audit bus to fan out notifications (DLA, governance indexers, alerting).

### What crosses this edge (what a pointer event is allowed to contain)

**Pointer events are not business traffic.** They are **indexes/notifications** about admission truth.

**Minimum fields (design-level, authoritative):**

* receipt identity / receipt ref (object URI or DB key)
* outcome enum + reason code if not admitted
* event identity keys: `event_id`, `event_type`, `producer`
* run/world pins if present (`run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash`, `seed`)
* admitted EB ref **if admitted** (topic/partition/offset)
* quarantine ref **if quarantined** (evidence pointers)

### What consumers must assume

* A pointer event is **never the source of truth**.
  It is only a convenient “heads up”. The source of truth remains IG receipts + evidence.

### What happens if pointer events are dropped

Nothing breaks semantically:

* DLA can still build audit records by consuming EB and then resolving IG refs via object store / `ig` index. Pointer events just reduce latency and operational cost.

---

# Path family E — Reconciliation (“what happened to my event?”)

These are not “nice to have”. They’re how you keep the trust boundary from becoming a black hole in production.

## E1) Producer/operator receipt lookup

**Path:**
`Producer/Operator → IG receipt lookup surface → ig DB/index (+ refs to object evidence)`

### Why it exists (pinned goal)

Operators must be able to answer **deterministically**:

* Was it admitted?
* If duplicate, what was the original admission?
* If quarantined, why and where is the evidence?
  …without scanning “latest” or replaying topics to guess.

### What the lookup can be keyed by (authoritative set)

A production-ready lookup must support at least one stable key, and ideally several:

* **event identity**: `(event_id, producer, event_type)` (canonical envelope supports this)
* **dedupe key** (IG’s “same event” canonical key)
* **receipt id / ingest_attempt_id** (for traceability and retries)
* **run pins** for bulk queries (e.g., “show quarantines for run_id=…”)

### What the lookup returns (the minimum “receipt payload”)

* outcome enum + reason codes + retryable flag (if not admitted)
* pointers:

  * admitted → EB ref (topic/partition/offset)
  * duplicate → pointer to original receipt/admission
  * quarantined → quarantine record ref + raw input ref

This is exactly how you guarantee “reconcile without guessing”.

---

## E2) Quarantine triage / inspection

**Path:**
`Operator → ig/quarantine evidence (object) + receipt metadata (DB) → decide remediation`

### Why it exists

Quarantine is not a dead-end; it’s the **evidence surface** that lets you debug drift (schema drift, pin mismatch, auth issues, missing readiness, etc.) without corrupting history.

### What an operator must be able to see (minimum evidence bundle)

A production-useful quarantine record must include:

* the original raw input reference (by-ref preferred)
* reason code(s) + retryable flag
* “what failed” evidence (schema errors, missing pins, mismatch details, auth deny context, etc.)
* correlation keys (ingest_attempt_id, batch_id if applicable)
* the event identity keys / pins that were present (so you can search and group quarantines)

### What triage decisions look like (design-level)

Operators need to sort quarantines into:

* **Retryable**: missing schema registration, run not READY yet, transient dependency failure
* **Terminal**: malformed envelope, security violation, pin mismatch corruption

This split is what keeps remediation safe and prevents “silent normalization” from creeping into the trust boundary.

### Where remediation flows next (just the linkage, not the full design yet)

* remediation results in a **new ingest attempt**; the original quarantine evidence remains immutable.
* the new attempt yields a new receipt (maybe ADMITTED), and DLA can later record a **supersedes** relationship in the flight recorder story.

---

## The single “designer pin” that makes D and E click together

If you only pin one thing here, pin this:

**Receipts must be sufficient to answer reconciliation and to power audit joins**:

* They must point to durable evidence surfaces (EB coords or admitted ref; quarantine ref; raw input ref).
* They must be discoverable by stable keys (event_id/dedupe/receipt_id/run pins).
* They must never require “scan latest” behavior.

---

Got it. I’ll “unblur” **F** and **G** as *production-grade paths* that sit **outside the hot-path semantics**, but are still **pinned** by your rails:

* **R9** append-only truth + **supersedes** for corrections
* **R12** quarantine is first-class (no silent drops)
* **R10** degrade is explicit / enforced / recorded
* **R13** correlation is mandatory

And I’ll keep IG as a vertex: we define *what* must happen, not *how it’s implemented*.

---

# Path family F — Quarantine remediation → re-ingest

## Why this path exists (pinned purpose)

If IG is the trust boundary, then **quarantine can’t be a dead end**; it must be a reversible, auditable state, because “drop and forget” is banned.

Also: **corrections must not be silent mutations**. The platform’s correction posture is “append-only + supersedes chains.”

So “remediation” is: **new intake attempts** that (a) preserve evidence of what failed, and (b) produce a new outcome that explicitly supersedes the prior failure.

### IG surfaces involved (production shape)

Deployed IG writes:

* admitted events to `fp.bus.traffic.v1`
* quarantine evidence to `ig/quarantine/...`
* receipts/quarantine index to DB `ig`
* optional pointer events to `fp.bus.audit.v1`

---

## F1) Re-submit corrected event

**Path:**
`Quarantined evidence → (human/tooling fixes payload/pins/proofs) → Producer → IG → EB`

### What “fixing” actually means (design-level categories)

A quarantined item is fixable when the failure is about **boundary compliance**, not changing platform truth elsewhere:

1. **Envelope/pins repair**
   Missing required envelope fields or required run/world pins get added or corrected. (Still no silent fix inside IG.)

2. **Schema registration / version alignment**
   The event’s `schema_version` becomes known/allowed (or payload becomes compatible with the declared version).

3. **Readiness / joinability unblock**
   If it was quarantined due to run not READY or unknown run context, the “fix” is that SR publishes the join surface; then you re-attempt intake.

4. **Proof/gate evidence completion** (especially for engine-derived attempts)
   Missing PASS/instance proof is supplied (or SR fixes the `run_facts_view` refs).

### The non-negotiable remediation invariant

**The original quarantine evidence remains immutable.**
Remediation produces a *new* intake attempt + a *new* receipt. That new receipt may “supersede” the earlier quarantine, but it never edits it.

### How the supersedes link is represented (authoritative design choice)

We need an explicit linkage so ops/audit can answer “what fixed this quarantine?”

I’m pinning this as the v0 design posture:

* The **re-submitted event** SHOULD carry a causal pointer to the quarantined item:

  * use `parent_event_id` in the canonical envelope where possible, and/or
  * include a `quarantine_record_ref` in the payload or metadata (even if payload is loose).
    The envelope explicitly supports `parent_event_id`.

* The **new receipt** MUST reference what it supersedes:

  * `supersedes_receipt_ref` and/or `supersedes_quarantine_ref` (conceptual names; exact field name is later spec work).
    This is directly demanded by the platform’s append-only + supersedes rule.

### What happens to dedupe in remediation (critical)

To keep “duplicates are stable” **and** allow remediation:

* If the new submission is a **true resend** (same content, same event_id), IG should return **DUPLICATE** or **same QUARANTINE** outcome deterministically.
* If the new submission is **materially corrected**, IG is allowed to change outcome (e.g., QUARANTINE → ADMIT), but **only by issuing a new receipt that supersedes the prior one**.

That’s the cleanest way to satisfy *both* R7 (stable under replay) and R9 (corrections are explicit).

### What “done” looks like for F1

After remediation:

* the event is either admitted (and has EB coordinates), or
* it is quarantined again with a *new* reason/evidence, and a visible chain back to the original quarantine.

---

## F2) Bulk remediation (batch)

**Path:**
`Batch submit → IG → per-event outcomes + optional batch summary receipt`

### Why batch exists

In production, quarantines often happen in clusters (schema version drift, upstream outage, READY delay). Batch remediation keeps humans/tools from resubmitting one-by-one.

### Pinned semantics (authoritative)

* **Outcomes are per-event.**
* A **batch summary receipt is optional**, but it must never replace per-event receipts.

### What the batch edge must support (design-level)

* A stable `batch_id` that:

  * can be used to enumerate per-event receipts (for triage),
  * can be used for “retry only failures”, and
  * can be audited later.
* Batch must preserve correlation:

  * per-event: `event_id` (+ run pins where applicable)
  * per-batch: `batch_id` + actor/tool identity
    (Correlation is mandatory.)

### Batch safety invariant

Batch remediation must not create “silent partial success.”
Even if the batch submission itself fails mid-way, the system-of-record is still the **per-event receipts** in `ig`, not the transport response.

---

# Path family G — Observability and control feedback loops that include IG

This is about making the trust boundary **operable** without letting observability become a “shadow controller.”

## G1) IG telemetry into observability

**Path:**
`IG → metrics/logs/traces → observability pipeline`

### Why it is pinned

Observability/Governance defines “rules of safe operation” and requires correlation standards + golden signals; it must support ops safety without hidden coupling.

### What IG must emit (minimum “golden signals” set)

At a minimum, IG emits structured telemetry for:

1. **Outcome rates**

* counts of ADMIT / DUPLICATE / QUARANTINE
* broken down by `producer` + `event_type` + (optionally) run pins

2. **Reason taxonomy distribution**

* top quarantine reasons over time (so you can spot drift spikes)
* retryable vs terminal breakdown

3. **Latency**

* ingest→decision latency
* decision→EB-ack latency
* total ingest→receipt latency

4. **Backpressure/lag indicators**

* input backlog (queue depth / request rate)
* EB append failure rate / retry rate
* for legacy engine pull ingestion: per-run ingestion progress (job-level), not as platform truth

### Correlation requirements (non-negotiable)

IG telemetry/logs/traces must carry:

* `event_id` (when an event exists),
* run pins when run-scoped,
* `ingest_attempt_id` / `batch_id` for forensic grouping,
* and optionally `trace_id/span_id` (the envelope supports them).

---

## G2) Degrade Ladder reads observability → produces explicit constraints

**Path:**
`Obs pipeline (including IG signals) → DL evaluator → (optional) fp.bus.control.v1 degrade posture updates`

### What’s pinned here

* DL consumes health/lag/error signals and produces `{degrade_mode, capabilities_mask, provenance}`.
* DF treats the capabilities mask as **hard constraints**.
* The degrade posture used must be recorded in provenance/audit.

Deployment-wise:

* DL reads the obs pipeline and writes current posture to DB `dl`; it may emit control events to `fp.bus.control.v1`.

### How IG participates (without becoming a controller)

**IG does not set degrade.** It only supplies signals that DL uses.

Concretely, IG contributes:

* sustained EB append failures or timeouts
* sharp spikes in quarantine (especially `SCHEMA_UNKNOWN`, `SECURITY_VIOLATION`, `PIN_MISMATCH`)
* large ingestion backlog indicating the platform is falling behind

DL then may tighten DF’s action/feature capabilities (fail toward safety).

### The “no hidden coupling” rule

Observability must not change behavior by stealth. Any posture change must be expressed via explicit control surfaces (DL posture in `dl` DB and optional control events).

### Audit tie-in (why G matters for DLA)

Because degrade posture must be recorded in audit, DLA can later explain:
“Decision X happened under degrade mask Y because IG/EB health was Z.”

---

## Designer-pinned outcomes from F + G (so we don’t drift later)

1. **Remediation never mutates quarantine history**; it creates new receipts and uses **supersedes chains**.
2. **Remediation must be linkable**: re-ingest attempts should reference the quarantined predecessor (prefer `parent_event_id` + receipt/quarantine refs).
3. **Batch remediation is per-event truth**; batch summaries are optional convenience.
4. **IG emits golden signals**, DL turns them into explicit constraints, DF obeys them, DLA records them — no hidden coupling.

---

Yes — the environment ladder puts **very specific constraints** on how we interpret every IG path/join: **the graph + rails + words must mean the same thing everywhere**, and only the *operational envelope* is allowed to change.

Here’s what that implies for the IG paths/joins we just illuminated.

## What must stay identical across local / dev / prod for IG paths

These are the “if this drifts, you’ve built three platforms” items.

* **Same graph + trust boundary:** IG is always the front door; EB is always the fact log; SR is always readiness authority. No environment may introduce a bypass that changes meaning.
* **Same join semantics / rails:** ContextPins + seed taxonomy, canonical envelope boundary, no-PASS-no-read, by-ref locators, idempotency, append-only + supersedes, watermarks, degrade mask as hard constraint.
* **Same meanings of the key words:** “READY”, “ADMITTED”, “QUARANTINED”, “DUPLICATE”, and the “what happened to my event?” reconciliation story must mean the same thing.
* **Same deployment-unit roles even if collapsed:** local can run things in one process, but IG must still behave like “reads producer input + run_facts_view + policy; writes admitted events + quarantine evidence + receipt index.”
* **Observability semantics stay the same even if sampled differently:** trace propagation/correlation rules don’t change; only sampling/volume changes.

## What is allowed to differ (and how that touches IG paths)

The ladder explicitly allows differences in: **scale, retention/archive, security strictness, reliability posture, observability depth, cost knobs** — but these must not change event/pin/gate/provenance semantics.

### 1) Security strictness (biggest visible difference)

* **Local:** permissive allowlists/dev creds are fine, but IG must still *perform* the trust-boundary decision (admit/quarantine/duplicate) and keep receipts/evidence.
* **Dev:** “real enough to catch issues” — unauthorized producers, missing PASS evidence, schema/version drift must be rejected here, not discovered in prod.
* **Prod:** strict authn/authz on IG ingress + quarantine access + policy changes; no reliance on “human memory”.

### 2) Retention + archive (changes *operational feasibility*, not meaning)

* EB retention being short in local means you can’t rely on long replays, but **IG receipts/quarantine evidence still must exist** and DLA audit records should still be written if you want the same reconciliation story.
* Dev/prod may introduce archive continuity; that affects *how far back* you can replay, not what “ADMITTED” meant at the time.

### 3) Observability depth (volume changes; the “chain of causality” does not)

* Local: high verbosity is fine.
* Prod: sampling is fine.
  But: IG must still emit the platform-minimum signals (admit/quarantine/duplicate rates, schema/auth failures, EB append latency), because DL depends on these to compute safe posture.

---

## How the ladder constrains each IG path family you asked about

### A paths (Producer → IG → …)

Across all envs:

* **A1 ADMIT** must still mean “durably appended to EB” (even if EB is a tiny local Redpanda topic).
* **A3/A4 QUARANTINE/HOLD** must still write evidence + receipts; local can keep shorter retention, but must not skip the quarantine/evidence surfaces or you’ll create “works locally” illusions.

Environment differences: mainly *security strictness* and *scale*.

### B paths (SR READY → IG pulls engine business_traffic → EB)

Across all envs:

* **B1/B2:** READY is the trigger and `run_facts_view` is the map; no scanning “latest” engine outputs in any environment.
* **B3:** no-PASS-no-read holds everywhere; IG is explicitly part of the enforcement story. Dev must catch missing PASS evidence; prod must never allow it.

Environment differences: *scale/concurrency* of ingestion and *retention/archive* (which affects “how far back can we replay engine-traffic-to-bus events”, not the mapping semantics).

### C paths (DF/AL/Case → IG → EB)

Across all envs:

* These internal producers **still don’t bypass IG** (trust boundary semantics identical).
  Environment differences:
* Local may use relaxed authn/authz, but dev must be strict enough to catch “wrong event_type from wrong producer” before prod.

### D/E paths (IG truth → DLA audit; and “what happened?” reconciliation)

Across all envs:

* The *mechanism* must exist: IG writes receipts/quarantine evidence, DLA can join by refs, and operators can reconcile without “scan latest.”
  Environment differences:
* Local may keep a minimal index; prod will want durable searchable indexes and tighter access control for quarantine evidence.

### F/G paths (remediation + observability/degrade feedback)

Across all envs:

* **Remediation is append-only + supersedes** (no silent mutations) — even locally, otherwise you train people into unsafe habits.
* **DL consumes IG/EB health signals**; degrade posture is explicit and enforced (DF obeys) and recorded (audit).
  Environment differences:
* Local thresholds can be forgiving; prod thresholds are meaningful and tied to SLO corridor checks. But the posture computation and mask semantics must be identical.

---

## The practical “anti-drift” rule for the ladder

If local **ever** skips one of these (even “just for convenience”), you’ll bake in drift:

* skipping gate verification in B3
* skipping receipts/quarantine evidence
* allowing bypass around IG for internal producers
* treating READY as optional
  Those are exactly the kinds of “works locally, breaks in dev/prod” violations the ladder is designed to prevent.

---

Yep — before we “enter” IG, the right mental model is:

* **IG is an always-on service deployment unit** (even if local collapses it), with very specific read/write surfaces.
* **Local/dev/prod must keep the same graph + rails + meanings**; profiles only change the *operational envelope* (scale/retention/security/reliability/observability/cost).

Below are the **environment profile knobs** (plus a few “you should know this now” deployment truths) for IG.

---

## 0) IG’s production deployment surfaces (the fixed shape)

From your deployment-unit map, IG in any env must be able to:

* **Read**

  * producer traffic input (**bus input or HTTP ingress**)
  * `sr/run_facts_view` (for run joinability + legacy engine pull ingestion)
  * policy profiles
* **Write**

  * admitted events → `fp.bus.traffic.v1`
  * quarantine evidence → `ig/quarantine/...`
  * receipt + quarantine index → DB `ig`
  * optional pointer events → `fp.bus.audit.v1`
* **Persist as “truth”**

  * admission truth (receipts/decisions) + evidence pointers (so DLA and reconciliation work)

Keep this in mind: **these surfaces don’t disappear in local**; you can only *swap implementations* (e.g., FS vs S3, sqlite vs postgres, local broker vs Kafka).

---

## 1) Environment profile knobs for IG

### A) Endpoint & substrate knobs (wiring)

These are the “same semantics, different plumbing” knobs:

* **Ingress mode**: bus input vs HTTP ingress (or both enabled)
* **Bus endpoints**: traffic topic (`fp.bus.traffic.v1`), control topic (`fp.bus.control.v1`), optional audit topic (`fp.bus.audit.v1`)
* **Object store prefixes**: `sr/...`, `engine/...`, `ig/quarantine/...`
* **DB DSN**: `ig` index store backend/connection (local sqlite vs shared dev/prod DB, etc.)

### B) Security strictness knobs (ramps up along ladder)

The ladder explicitly says security posture is allowed to differ, but the *mechanism exists everywhere*.
IG profile knobs here:

* producer **authn mode** (dev creds vs prod identity)
* producer **authz allowlists** (which producer may emit which event_types/scopes)
* **quarantine access controls** (who can view evidence; tighter in dev/prod)
* **policy change permissions** (who can activate a new policy revision)

Local: minimal friction but still enforced; Dev: “real enough”; Prod: strict everywhere it matters (IG explicitly listed).

### C) Gate/proof enforcement knobs (should *not* get weaker locally)

Engine gate maps explicitly list IG as a required verifier (`required_by_components: ingestion_gate`).
So IG needs:

* gate verification enabled (always)
* gate verification concurrency/timeouts
* fail-closed posture (always)

Dev’s rule is explicitly “catch what prod would catch (missing PASS evidence, unauthorized producers)” — so don’t weaken this in local if you want the ladder to work.

### D) Scale/throughput knobs (allowed to differ)

The ladder allows throughput/concurrency differences.
IG knobs:

* max ingress RPS / queue depth
* worker concurrency (push intake and legacy engine-pull ingestion)
* batch sizes (for engine table scanning → envelope emit)
* retry budgets/timeouts (EB append, object reads, DB writes)
* backpressure posture (shed vs slow vs hard-fail; still must be receipted)

### E) Retention & evidence knobs (allowed to differ, but don’t break reconciliation)

Retention/archiving can differ by env.
IG knobs:

* quarantine evidence retention / TTL (shorter local, longer dev/prod)
* receipt retention (should generally be long; it’s admission truth)
* evidence blob size limits / compression
* whether to emit pointer events to audit bus (helps indexing, optional)

Rule of thumb: you can shorten retention locally, but you must not remove the ability to answer “what happened?” via receipts + evidence.

### F) Observability depth knobs (volume differs; correlation doesn’t)

Observability depth is an allowed difference; semantics aren’t.
IG knobs:

* log level (debug vs info)
* trace sampling rate
* metrics granularity (per event_type vs aggregated)
* alert thresholds (dev can be noisy; prod SLO/corridor-meaningful)

### G) “Control feedback” knobs (DL corridor checks)

DL is driven off the obs pipeline and policy thresholds profiles; prod corridor checks are “meaningful”.
IG knobs that affect this loop:

* which IG metrics feed DL (quarantine spikes, EB append failures, backlog)
* thresholds per environment (lenient local, realistic dev, strict prod)

---

## 2) One crucial deployment truth: profiles are promoted artifacts

Your CI/CD notes pin that promotion is:

* **build once/run anywhere** (same binary across envs), and
* **policy configs are versioned artifacts** promoted with approval; runtime components should report `policy_rev`.

For IG, that means you should expect *two* profile layers:

1. **Environment wiring** (endpoints/credentials/retention)
2. **Policy revision** (allowlists, schema acceptance rules, required gates, corridor thresholds)

…and IG should be able to cite “which policy rev was in force” in receipts/logs (so ops can answer “why did it quarantine?” instantly).

---

## 3) Minimal “profile sketch” (so you’re pointed correctly)

Not values, just direction:

* **local profile**

  * permissive allowlists + dev creds
  * short retention
  * debug observability
  * still enforces rails and gate checks

* **dev profile**

  * multi-service, realistic integration
  * authn/authz “real enough”
  * medium retention, representative volumes
  * dashboards/alerts; catches missing PASS evidence / unauthorized producers

* **prod profile**

  * strict authn/authz + change control
  * longer retention + archive continuity
  * SLOs/corridor checks are meaningful
  * “never relies on human memory” (everything attributable, auditable)

---

Got you. No ASCII, no deep internals yet.

### Canonical IG internal module graph (one level deeper, still opaque)

In a production-ready platform, **IG contains exactly these internal subnetworks**. Treat each as an opaque box for now; later we can open them one-by-one.

---

## 1) Producer Intake Gateway

**Role:** The single front door into IG (bus/HTTP), with producer identity bound at the boundary.

**Consumes:** incoming messages (bus or HTTP), transport-level identity.
**Emits:** `IntakeItem` (normalized “thing to evaluate”) + bound `producer_principal`.

**Hard guarantees:**

* Every item is attributed to a producer principal.
* Unauthorized producers are not “dropped”; they become **QUARANTINE** via the Quarantine Vault.

**Does not do:** schema/payload meaning, run/world anchoring, gate verification.

---

## 2) Envelope & Policy Gate

**Role:** Enforce the canonical envelope boundary + apply policy for what *must* be present.

**Consumes:** `IntakeItem`, policy profile(s), schema catalog (at least envelope schema).
**Emits:** `PolicyBoundEvent` (event + policy decisions) or a quarantine reason.

**Hard guarantees:**

* The canonical envelope is enforced (required fields must exist).
* Required pins for that `(producer, event_type)` are enforced (no “silent fixups”).
* Unknown schema versions are **never guessed**; they become **QUARANTINE**.

**Does not do:** talk to EB, decide duplicates, read engine outputs.

---

## 3) Run/World Anchor

**Role:** The only place IG learns “what run/world exists” and whether it’s admissible to join.

**Consumes:** `PolicyBoundEvent`, SR READY signals (as triggers), `sr/run_facts_view` (as authority).
**Emits:** `AnchoredEvent` (event + resolved run context) or “unjoinable/unready” outcome routing.

**Hard guarantees:**

* IG never “scans latest” to infer world/run.
* If an event claims run/world joinability but can’t be anchored to a valid (READY) run context, it routes to **A4-style QUARANTINE/HOLD**.

**Does not do:** engine gate math, framing engine rows, dedupe.

---

## 4) Engine Pull Orchestrator

**Role:** Turn SR READY + run_facts_view into an ingestion job that produces candidate traffic items (Pull model).

**Consumes:** SR READY, `sr/run_facts_view`.
**Emits:** a stream of `EngineTrafficCandidate` items (each tied to an engine output target and run context).

**Hard guarantees:**

* Only runs after READY.
* Only ingests targets explicitly listed in `run_facts_view` (no discovery).
* Produces resumable, run-scoped ingestion work (idempotent across repeated READY).

**Does not do:** final admit/receipt; it hands candidates forward.

---

## 5) Proof & Gate Enforcement Service

**Role:** Enforce “no PASS → no read” for engine-derived ingestion, gate-specific.

**Consumes:** `EngineTrafficCandidate`, engine gate map, gate receipts/evidence, instance-proof (when required).
**Emits:** `ProofedTrafficSource` or quarantine reasons.

**Hard guarantees:**

* Gate verification follows the declared verification method per gate.
* Instance-scoped outputs require instance proof bound to locator+digest.
* Anything lacking proof is **fail-closed → QUARANTINE**.

**Does not do:** decide event_type naming, event_id minting, EB append.

---

## 6) Traffic Framer & Canonicalizer

**Role:** Produce canonical envelope events from whatever the upstream source is (push payloads or engine rows).

**Consumes:** `AnchoredEvent` (push) or `ProofedTrafficSource` (pull).
**Emits:** `CanonicalEvent` ready for admission.

**Hard guarantees:**

* Engine rows become valid canonical envelopes.
* `event_type` is deterministic (for legacy engine pull: `event_type = output_id`).
* `event_id` is stable/deterministic when minting is required.
* `ts_utc` remains domain time; IG adds ingestion time only in receipts/metadata.

**Does not do:** dedupe ledger, EB commit.

---

## 7) Admission Ledger & Idempotency Core

**Role:** The system-of-record inside IG for “first-seen vs duplicate vs already quarantined,” and the crash-safe guardrail around admission.

**Consumes:** `CanonicalEvent`.
**Emits:** one of:

* `FirstSeenAdmission` (go commit)
* `DuplicateDecision` (point to prior outcome)
* `QuarantineDecision` (route to evidence vault)

**Hard guarantees:**

* Deterministic outcomes under retries (at-least-once reality).
* Prevents double-admit (concurrency-safe).
* Maintains an internal “pending” notion so crashes can’t produce “admitted but not appended” lies.

**Does not do:** write to EB directly, store evidence blobs.

---

## 8) Bus Commit & Receipt Publisher

**Role:** Perform the only action that makes an event “real”: durable append to EB, then finalize receipts.

**Consumes:** `FirstSeenAdmission`.
**Emits:** `ADMITTED` receipt (with EB coordinates), and optional audit pointer events.

**Hard guarantees:**

* **ADMITTED iff EB append acknowledged.**
* Partition routing is deterministic and stamped here (policy-driven).
* Receipt is written as durable admission truth (and discoverable for reconciliation).

**Does not do:** decide eligibility, run anchoring, gating.

---

## 9) Quarantine Vault & Remediation Surface

**Role:** Store quarantine evidence bundles and support safe re-ingest without mutating history.

**Consumes:** `QuarantineDecision` + raw input refs + diagnostics.
**Emits:** `QUARANTINED` receipt + evidence refs; optional remediation hooks.

**Hard guarantees:**

* Quarantine always produces durable evidence + receipt.
* Remediation is append-only: re-ingest creates a new attempt and can **supersede** prior quarantine via explicit linkage (never edits the past).

**Does not do:** “fix” inputs automatically into admission.

---

## 10) Ops Surfaces (Reconciliation + Health + Telemetry)

**Role:** Everything needed to operate IG without guessing.

**Consumes:** receipts/index, quarantine refs, internal metrics/traces.
**Emits:** E1/E2 answers (“what happened?”), health signals, metrics that feed the Degrade Ladder.

**Hard guarantees:**

* Reconciliation never requires scanning EB or “latest”; receipts/evidence are queryable by stable keys.
* Correlation is preserved (event_id/run pins/attempt ids).

**Does not do:** admission decisions.

---

### The internal shape, in one sentence

IG is a **pipeline of opaque subnetworks** that converge on a single truth engine (**Admission Ledger**) and a single “reality boundary” (**EB commit**), with quarantine/evidence and ops surfaces as first-class citizens.

If you pick one subnetwork to open next, the correct order (because it constrains everything else) is:

1. **Admission Ledger & Idempotency Core**, then
2. **Bus Commit & Receipt Publisher**, then
3. **Quarantine Vault**, then
4. **Run/World Anchor**, then
5. **Engine Pull Orchestrator + Proof Service**, then
6. **Framer/Canonicalizer + Policy Gate**.

---

Yep — here are the **joins (internal edges)** and the **internal path families** that exist **between the first-layer IG subnetworks** (all boxes stay opaque).

I’ll name the subnetworks as modules **M1–M10** (same set we agreed).

## The IG modules (opaque boxes)

* **M1** Producer Intake Gateway
* **M2** Envelope & Policy Gate
* **M3** Run/World Anchor
* **M4** Engine Pull Orchestrator
* **M5** Proof & Gate Enforcement
* **M6** Traffic Framer & Canonicalizer
* **M7** Admission Ledger & Idempotency Core
* **M8** Bus Commit & Receipt Publisher
* **M9** Quarantine Vault & Remediation Surface
* **M10** Ops Surfaces (Reconciliation + Health + Telemetry)

---

# A) Internal joins (edges) inside IG

### J1 — M1 → M2: Intake normalization

**Carries:** `IntakeItem = {producer_principal, transport_meta, envelope_candidate, raw_input_ref/bytes, received_at}`
**Why:** Everything becomes one normalized “thing to evaluate” with producer identity bound.

### J2 — M2 → M3: Policy-bound event

**Carries:** `PolicyBoundEvent = {canonical_envelope, policy_id, required_pins_check_result, schema_mode}`
**Why:** Run/world anchoring only happens after envelope + policy requirements are applied.

### J3 — M3 → M6: Anchored push event

**Carries:** `AnchoredEvent = {canonical_envelope, run_context_ref (READY-backed) | none, anchor_status}`
**Why:** Canonicalization uses resolved run context (or confirms non-run-scoped).

### J4 — M4 → M3: Run ingestion start + join-surface request

**Carries:** `RunIngestStart = {scenario_id, run_id}` (triggered by READY)
**Why:** M3 is the authority for “what run exists + where its `run_facts_view` is”.

### J5 — M3 → M4: Run ingestion plan

**Carries:** `RunIngestPlan = {run_context (pins), run_facts_view_ref, traffic_targets[]}`
**Why:** M4 is not allowed to discover; it must ingest exactly the SR-declared traffic targets.

### J6 — M4 → M5: Engine traffic candidate

**Carries:** `EngineTrafficCandidate = {run_context, engine_output_locator, target_partition/range hints}`
**Why:** Proof enforcement happens before any read/emit.

### J7 — M5 → M6: Proofed traffic source

**Carries:** `ProofedTrafficSource = {run_context, engine_output_locator, PASS_evidence_refs, instance_proof_refs, read_authorized=true}`
**Why:** Framer only acts on sources that are already admissible.

### J8 — M6 → M7: Canonical event for admission

**Carries:** `CanonicalEvent = {envelope (fully populated), partition_hint, provenance_pointers}`
**Why:** Every admissible thing converges to one admission truth engine.

### J9 — M7 → M8: First-seen admission ticket

**Carries:** `FirstSeenAdmission = {dedupe_key, canonical_event, partition_key}`
**Why:** Only first-seen items can attempt EB append.

### J10 — M8 → M7: Commit acknowledgment

**Carries:** `CommitAck = {dedupe_key, eb_topic, partition, offset}`
**Why:** Finalizes ADMITTED truth (ADMIT iff ack).

### J11 — M7 → M10: Receipt index feed

**Carries:** `ReceiptPointer = {dedupe_key, outcome, receipt_ref, eb_ref|quarantine_ref, reason_codes}`
**Why:** Makes “what happened?” answerable without scanning.

### J12 — M8 → M10: Commit telemetry + optional audit pointer

**Carries:** `CommitTelemetry` and (if enabled) `AuditPointerEvent`
**Why:** Ops visibility + optional fanout without changing truth ownership.

### J13 — Any of (M1..M8) → M9: Quarantine request

**Carries:** `QuarantineRequest = {reason_codes, raw_input_ref, diagnostics, anchor/proof context, related refs}`
**Why:** All failure paths converge to one evidence surface.

### J14 — M9 → M7: Quarantine finalization

**Carries:** `QuarantineFinal = {dedupe_key, quarantine_ref, receipt_ref}`
**Why:** Quarantine is recorded as durable admission truth (no silent drop).

### J15 — M9 → M10: Quarantine evidence ready

**Carries:** `EvidencePointer = {quarantine_ref, evidence_bundle_refs}`
**Why:** Enables triage/inspection flows.

### J16 — M10 → M7: Receipt lookup query

**Carries:** `LookupQuery = {event_id | dedupe_key | receipt_id | run pins}`
**Why:** Reconciliation reads the ledger; it never scans EB.

### J17 — M10 → M9: Quarantine fetch/triage query

**Carries:** `QuarantineFetch = {quarantine_ref}` / `TriageAction`
**Why:** E2 (“inspect quarantine”) is a first-class ops path.

### J18 — Config plane → (M2, M5, M8, M10): Profile updates (always-on)

**Carries:** `PolicyRevUpdate`, `SchemaCatalogUpdate`, `GateMapUpdate`, `ThresholdsUpdate`
**Why:** Profiles are inputs; modules must react without semantics drift.

### J19 — M10 → M1: Ingress throttling / circuit-break directives

**Carries:** `IngressControl = {rate_limit, shed_mode, backpressure_state}`
**Why:** Production stability: IG remains operable under EB/DB pressure *without changing outcome semantics*.

### J20 — (M10 or M9) → M1: Remediation re-ingest submission

**Carries:** `ReingestSubmission = {corrected_event, supersedes_ref}`
**Why:** Remediation must re-enter through the same front door (no bypass).

---

# B) Internal path families (end-to-end flows inside IG)

## P1 — Push ingest ADMIT (A1)

`M1 → M2 → M3 → M6 → M7 → M8 → M7 → M10`
Outcome: ADMITTED receipt with EB coordinates.

## P2 — Push ingest DUPLICATE (A2)

`M1 → M2 → M3 → M6 → M7 → M10`
Outcome: DUPLICATE receipt pointing to original EB ref (or original quarantine ref).

## P3 — Push ingest QUARANTINE (A3)

Failure at any of `M1/M2/M3/M6/M7/M8` routes:
`… → M9 → M7 → M10`
Outcome: QUARANTINED receipt + evidence refs.

## P4 — Push ingest UNREADY/UNJOINABLE (A4)

`M1 → M2 → M3 (anchor fails) → M9 → M7 → M10`
Outcome: QUARANTINE/HOLD-class receipt (retryable reason) + evidence.

## P5 — Engine pull ingest ADMIT (B1–B4)

`M4 (READY) → M3 → M4 → M5 → M6 → M7 → M8 → M7 → M10`
Outcome: ADMITTED receipts for framed engine traffic events.

## P6 — Engine pull ingest QUARANTINE (B5)

Failure at `M3/M5/M6/M8` routes:
`… → M9 → M7 → M10`
Outcome: QUARANTINED receipts tied to `{engine_output_locator, row_pk, proof refs}`.

## P7 — Quarantine remediation → re-ingest (F1/F2)

`M10/M9 (triage) → M1 (reingest) → (P1/P2/P3/P4)`
Outcome: new receipt that explicitly supersedes prior quarantine (no mutation).

## P8 — Reconciliation “what happened?” (E1/E2)

* E1: `Operator/Producer → M10 → M7 → M10`
* E2: `Operator → M10 → M9 → M10`
  Outcome: deterministic answers + evidence access without scanning.

## P9 — Observability/control feedback inside IG (G)

`(all modules) → M10 (telemetry aggregation) → external obs pipeline`
and
`M10 → M1` (throttle/circuit-break)
Outcome: stability + signals for DL, without IG becoming a controller.

---

Got it. We’ll illuminate **J1–J7** as **authoritative internal joins** between opaque subnetworks. For each join I’ll lock:

* **Purpose** (why the edge exists)
* **What crosses** (the conceptual payload)
* **Hard invariants** (what MUST be true after the join)
* **Reject routing** (what failures look like; they do **not** “continue anyway”)

I’m using the module IDs we already set:

* **M1** Producer Intake Gateway
* **M2** Envelope & Policy Gate
* **M3** Run/World Anchor
* **M4** Engine Pull Orchestrator
* **M5** Proof & Gate Enforcement
* **M6** Traffic Framer & Canonicalizer

---

# J1 — M1 → M2: Intake normalization join

### Purpose

Turn “whatever arrived” (bus/HTTP) into a **single normalized intake item** with **producer identity bound**, so downstream never deals with transport ambiguity.

### What crosses (payload)

`IntakeItem`:

* `intake_id` (unique per intake attempt)
* `source_kind` = `push_bus | push_http`
* `producer_principal` (transport-authenticated identity)
* `transport_meta` (received_at, headers/attrs, remote addr, topic/partition/offset if bus ingress)
* `raw_input_ref` (pointer to exact bytes as received; “evidence preservation”)
* `envelope_candidate` (best-effort parsed structure, if parse succeeded)
* `trace_context` (trace_id/span_id if present)

### Hard invariants

* **Producer identity is bound**: `producer_principal` is always present.
* **Evidence is preserved**: `raw_input_ref` exists for every intake attempt (even if parsing fails).
* **No semantic checks happen here**: M1 does not validate envelope, does not check run readiness, does not dedupe.

### Reject routing (what never passes J1)

* If bytes cannot be captured or referenced → **hard reject to Quarantine** (IG must never proceed without evidence preservation).
* If transport identity can’t be established → **reject to Quarantine** (`AUTHN_FAILED`).

---

# J2 — M2 → M3: Policy-bound event join

### Purpose

Convert an intake item into a **policy-bound, envelope-valid event candidate** that is safe to attempt anchoring to a run/world.

### What crosses (payload)

`PolicyBoundEvent`:

* `policy_rev` (the exact policy revision used)
* `canonical_envelope` (validated envelope fields; payload untouched)
* `producer_principal` + `declared_producer` (envelope producer field)
* `event_type` + `schema_version` (if applicable)
* `required_pin_class` = `non_run_scoped | run_scoped`
* `pin_set` (the pins present + whether they satisfy the policy’s required set)
* `payload_validation_mode` = `none | structural | strict` (policy decides)
* `partitioning_profile_id` (policy chooses the routing strategy later used by M8)

### Hard invariants

* Envelope is **valid** at the boundary: required envelope fields exist and are well-formed.
* Producer identity is **consistent**: `producer_principal` must match `declared_producer` (if mismatch → reject).
* Policy classification is **decided**: whether this event is run-scoped is no longer ambiguous.
* If policy says “run-scoped,” then required pins for run joinability are present; missing pins → reject.

### Reject routing

M2 does **not** “fix” anything. It rejects to Quarantine if:

* Envelope invalid / missing required envelope fields (`ENVELOPE_INVALID`)
* Producer mismatch (`PRODUCER_MISMATCH`)
* Policy denies this `(producer,event_type)` (`POLICY_DENY`)
* Unknown/unsupported schema_version when validation is required (`SCHEMA_UNKNOWN`)
* Missing required pins for the required pin class (`PINS_MISSING`)

---

# J3 — M3 → M6: Anchored push event join

### Purpose

Attach a **run/world anchor truth** (or explicitly declare non-run-scoped) so canonicalization has a stable context and never guesses.

### What crosses (payload)

`AnchoredEvent`:

* `canonical_envelope` (unchanged)
* `anchor_class` = `non_run_scoped | run_scoped`
* if `run_scoped`:

  * `run_context` = `{scenario_id, run_id, manifest_fingerprint, parameter_hash, seed}`
  * `run_facts_view_ref` (the authoritative join surface ref)
  * `anchor_state` = `READY` (only READY is allowed to proceed)
* `anchor_basis` (what was used: READY-triggered join surface)
* `anchor_provenance` (hash/ref of the run_facts_view used, so later reconciliation is deterministic)

### Hard invariants

* If `run_scoped`, then:

  * run exists and is **READY**
  * event pins **match** the run context (no mismatches tolerated)
  * anchoring references a concrete `run_facts_view_ref`
* If `non_run_scoped`, then:

  * event is explicitly declared not to require run anchoring (so it will not be blocked on READY)

### Reject routing

M3 routes to Quarantine/Hold (still a quarantine-class outcome) if:

* Run is unknown (`UNKNOWN_RUN`)
* Run exists but not READY (`RUN_NOT_READY`) → this is the **only** “retryable hold-style” reject
* Pins contradict the run context (`PIN_MISMATCH`)
* `run_facts_view_ref` missing/unreadable for a READY run (`JOIN_SURFACE_MISSING`) → quarantined because READY without a usable join surface is invalid

---

# J4 — M4 → M3: Run ingest start join

### Purpose

Turn READY into a **run-scoped ingestion start request** that the Run/World Anchor treats as authoritative and idempotent.

### What crosses (payload)

`RunIngestStart`:

* `scenario_id`, `run_id`
* `ready_signal_ref` (or equivalent stable identity of the READY trigger)
* `requested_by` = `engine_pull_orchestrator`
* `ingest_job_id` (stable per run; idempotent)

### Hard invariants

* Starts are **idempotent** per `(scenario_id, run_id)`:

  * multiple READY deliveries do not create multiple competing ingestion jobs.
* M4 never requests ingestion for a run that is not READY (this is a core reason we chose Pull).

### Reject routing

If M3 cannot resolve a valid READY run context from this request, the ingest start is rejected as:

* `UNKNOWN_RUN` or `RUN_NOT_READY` (and M4 treats that as “do not proceed; record run-level ingest failure evidence”).

---

# J5 — M3 → M4: Run ingest plan join

### Purpose

Give M4 the **only legal plan** for legacy engine pull ingestion: “here is the run context, here is the join surface, here are the traffic targets SR declared.”

### What crosses (payload)

`RunIngestPlan`:

* `run_context` (pins + READY confirmation)
* `run_facts_view_ref`
* `traffic_targets[]`, each target includes:

  * `engine_output_locator` (output_id + resolved path + identity tokens)
  * `declared_role` (must be `business_traffic` to be eligible)
  * `expected_gate_id` (authorising segment gate)
  * `proof_refs` (gate receipt refs; instance-proof refs if required)
  * `content_digest` (required when instance-proof binding is required)
  * `framing_hint` (the deterministic mapping key: **event_type = output_id**)

### Hard invariants

* **No discovery**: targets are exactly those declared by SR’s join surface.
* Targets are already attached to a READY run context (M4 never runs “floating ingestion”).
* The plan carries enough proof references to allow fail-closed verification downstream.

### Reject routing

If the join surface is internally inconsistent, M3 rejects the plan (and M4 will not ingest) with:

* `TARGET_LIST_INVALID` (missing locator/path)
* `ROLE_NOT_TRAFFIC` (non-business_traffic listed as traffic)
* `PROOF_REF_MISSING` (required proof ref absent)
* `DIGEST_REQUIRED_MISSING` (instance-proof-required target lacks content digest)

---

# J6 — M4 → M5: Engine traffic candidate join

### Purpose

Fan out the run ingest plan into **per-target candidates** for proof enforcement (and later reading/framing).

### What crosses (payload)

`EngineTrafficCandidate`:

* `run_context` (pins + run_facts_view_ref)
* `engine_output_locator`
* `declared_role` (must be `business_traffic`)
* `expected_gate_id`
* `proof_refs` (gate receipts; instance proof refs)
* `content_digest` (if required)
* `candidate_id` (unique per target per run)
* optional `read_window` (for chunked ingestion; purely operational)

### Hard invariants

* Candidates are produced **only** from a valid `RunIngestPlan` (no freeform targets).
* Candidates remain **opaque** about proof validity: M4 does not verify proofs; it only forwards the necessary references.
* Candidates carry stable correlation: candidate_id + run pins + output_id.

### Reject routing

If M4 cannot construct a candidate from a plan entry (missing locator fields, missing proof refs), it emits a **run-ingest quarantine record** (not a “skip”) and does not forward that candidate.

---

# J7 — M5 → M6: Proofed traffic source join

### Purpose

Only forward traffic sources that are **provably admissible to read** under “no PASS → no read” and instance-proof rules.

### What crosses (payload)

`ProofedTrafficSource`:

* `run_context` + `run_facts_view_ref`
* `engine_output_locator`
* `verified_gate`:

  * `gate_id`
  * `verification_method_used` (gate-specific)
  * `pass_evidence_ref`
* `verified_instance_proof` (present iff required)
* `content_digest` (bound to proof when required)
* `read_authorized = true`
* `framing_hint` (event_type = output_id; plus PK/row identity hints for deterministic event_id minting)

### Hard invariants

* Gate PASS is **verified** using the correct method for that gate.
* Dependency prerequisites for the gate are satisfied (fail-closed).
* If instance proof is required, it is **verified and bound** to the locator+digest.
* If any of the above is not true, **nothing crosses J7**.

### Reject routing

M5 rejects to Quarantine (with strong evidence pointers) for:

* `GATE_MAP_MISSING` (cannot map output_id to gate)
* `GATE_FAIL` / `PASS_MISSING`
* `VERIFICATION_MISMATCH` (proof doesn’t verify under the gate’s declared method)
* `INSTANCE_PROOF_MISSING` / `INSTANCE_PROOF_MISMATCH`
* `DIGEST_REQUIRED_MISSING`
* `ROLE_NOT_TRAFFIC` (belt-and-suspenders enforcement: even if upstream mislabels)

---

## One key designer lock across J1–J7

**Every join either produces a well-formed output object or routes to Quarantine/Hold. There is no “partial pass” onward.**
That single rule is what keeps the larger platform graph drift-proof and makes later deep dives manageable.

---

Cool — we’ll illuminate **J8–J14** as **authoritative internal joins** between the opaque IG subnetworks. Same pattern as before: **Purpose → What crosses → Hard invariants → Reject routing**.

Modules in play here:

* **M6** Traffic Framer & Canonicalizer
* **M7** Admission Ledger & Idempotency Core
* **M8** Bus Commit & Receipt Publisher
* **M9** Quarantine Vault & Remediation Surface
* **M10** Ops Surfaces (Reconciliation + Health + Telemetry)

---

## J8 — M6 → M7: Canonical event admission join

### Purpose

Hand off a **fully canonical, admission-ready event** (from either push or legacy engine-pull framing) to the **single truth engine** that decides first-seen vs duplicate vs quarantine.

### What crosses

`AdmissionCandidate`:

* `receipt_key` (the key IG will use to record an outcome)

  * if `event_id` exists → `receipt_key = dedupe_key_basis` (see below)
  * if `event_id` missing/invalid → `receipt_key = intake_id` (unique attempt key)
* `canonical_envelope` (all required envelope fields present & well-formed)
* `producer_principal`
* `run_context` (present iff run-scoped; includes run pins + READY anchor ref)
* `partitioning_profile_id` + `partition_hint_inputs` (the fields needed to compute partition_key deterministically)
* `provenance_pointers` (source refs; for legacy engine pull this includes `{engine_output_locator, row_pk}`)

### Hard invariants

* **If J8 fires, the envelope is final**: required envelope fields are present; M6 is done mutating the envelope.
* **A receipt_key always exists**:

  * With valid `event_id`: M7 can compute a stable dedupe key.
  * Without valid `event_id`: M7 must still be able to quarantine with a receipt keyed by `intake_id`.
* **Run-scoped candidates are already anchored** (READY-backed) — M7 does not “re-decide” readiness.

### Reject routing

If M6 cannot produce a canonical envelope (e.g., cannot derive `ts_utc`, cannot mint a stable `event_id` for engine rows), it does **not** emit J8; it emits **J13 → M9** with `FRAME_FAIL` evidence.

---

## J9 — M7 → M8: First-seen admission ticket join

### Purpose

Authorize **exactly one** attempt to append the event to EB by issuing a *first-seen ticket* only when the ledger has reserved the dedupe key.

### What crosses

`FirstSeenTicket`:

* `dedupe_key` (stable, deterministic)
* `ledger_record_id` (the reserved ledger row)
* `canonical_event_bytes_or_ref` (the exact bytes to append)
* `partition_key` (already computed deterministically)
* `commit_policy` (retry budget + timeout class; operational, not semantic)

### Hard invariants

* **J9 only exists for first-seen events**.
* Before J9 is emitted, **M7 has already persisted a PENDING admission record** for `dedupe_key` (write-ahead reservation).
  This is the “no double-admit, crash-safe truth” guardrail.
* **If the PENDING reservation can’t be written, J9 never happens.**

### Reject routing

* If `dedupe_key` already exists:

  * M7 emits **DUPLICATE** (no J9; the outcome is produced via M7→M10 and/or direct response).
* If the ledger store is unavailable:

  * The event is **not accepted** (no receipt is promised because the truth store is down).
  * Push ingress returns a retryable failure; bus ingress remains unacked; legacy engine pull pauses the run ingest.
  * Nothing moves forward into EB without ledger truth.

(That’s not “maybe” — that’s the rule: **no ledger write → no acceptance → no EB append**.)

---

## J10 — M8 → M7: Commit acknowledgment join

### Purpose

Close the “admit means durable append” law by finalizing the ledger record **only after** EB acknowledges the append.

### What crosses

`CommitAck`:

* `dedupe_key`, `ledger_record_id`
* `eb_ref` = `{topic, partition, offset}`
* `commit_time_utc`
* `append_checksum` (optional integrity marker; used for diagnostics, not meaning)

### Hard invariants

* **ADMITTED is written only on J10.**
  If J10 hasn’t arrived, the ledger record stays non-final (PENDING/RETRYING).
* **Commit is idempotent**: duplicate acks (or retries) must not create a second admission; they only reaffirm the same `eb_ref`.

### Reject routing (when EB append doesn’t ack cleanly)

EB append failures are **not** treated as “bad event” quarantines. They follow this rule:

* If EB append fails or ack is uncertain:

  * M8 emits `CommitFail` back to M7 (internal signal; not one of the external outcomes).
  * M7 keeps the record **PENDING** and schedules retry via M8.
* If retry budget is exhausted:

  * The record is finalized as **QUARANTINED** with reason `COMMIT_DEADLETTER`, and the original candidate + diagnostics are written via **J13/J14** (so the system still ends in an explicit, auditable outcome).

---

## J11 — M7 → M10: Receipt index feed join

### Purpose

Expose admission truth for reconciliation (“what happened to my event?”) without requiring anyone to scan EB.

### What crosses

`ReceiptPointer`:

* `receipt_key` + (if available) `dedupe_key`
* `outcome` = `ADMITTED | DUPLICATE | QUARANTINED`
* `primary_ref`:

  * admitted → `eb_ref`
  * quarantined → `quarantine_ref`
  * duplicate → `original_receipt_ref` (and/or original `eb_ref`)
* `reason_codes` (for quarantines)
* `policy_rev` (the policy in force for that decision)

### Hard invariants

* **Receipt truth lives in the ledger**; M10 is a view/query surface.
* J11 must be **idempotent** (same receipt pointer can be replayed safely).

### Reject routing

If M10 is degraded/unavailable, it does **not** block admissions. M10 can always reconstruct by reading the ledger directly; J11 is a propagation edge, not the source of truth.

---

## J12 — M8 → M10: Commit telemetry + optional audit pointer join

### Purpose

Provide:

* operational visibility (latency, retries, throughput), and
* optional pointer-only audit notifications (never truth).

### What crosses

Two payload types:

1. `CommitTelemetry`:

   * timings: `append_latency`, `retry_count`, `queue_depth`
   * failure codes if any
2. `AuditPointerEvent` (when enabled):

   * receipt ref / dedupe_key
   * outcome + primary_ref (eb_ref or quarantine_ref)

### Hard invariants

* **Audit pointers are never authoritative**; they only point to receipts/evidence.
* Telemetry must carry correlation keys (event_id/dedupe_key/run pins where available).

### Reject routing

If this join fails, nothing about admission truth changes. It’s safe to drop pointer events; receipts remain queryable.

---

## J13 — (any of M1..M8) → M9: Quarantine request join

### Purpose

Provide a single convergence edge for **all failure paths** to produce durable evidence + a quarantine receipt.

### What crosses

`QuarantineRequest`:

* `receipt_key` (dedupe_key if available, else intake_id)
* `reason_codes[]` (canonical taxonomy)
* `failure_stage` (which module/edge failed)
* `raw_input_ref` (always)
* `diagnostics` (schema errors, pin mismatches, authz denies, gate failures, etc.)
* optional context:

  * run_context_ref (if known)
  * engine context: `{engine_output_locator, row_pk, proof_refs}` (for legacy engine pull ingestion)
  * policy_rev

### Hard invariants

* **Quarantine always has evidence**: `raw_input_ref` + diagnostics must be present.
* **Quarantine is never silent**: every quarantine request must result in a durable receipt unless the quarantine store itself is unavailable.

### Reject routing

If M9 cannot persist evidence (object store down) **and** cannot persist a receipt (ledger down), then IG is **unavailable** for acceptance:

* push ingress gets a retryable failure,
* bus ingress remains unacked,
* legacy engine pull pauses.
  No fake receipts are issued.

---

## J14 — M9 → M7: Quarantine finalization join

### Purpose

Finalize the quarantine as admission truth: create/close the ledger record and make the receipt discoverable.

### What crosses

`QuarantineFinal`:

* `receipt_key` (+ `dedupe_key` if known)
* `quarantine_ref` (pointer to evidence bundle)
* `receipt_ref` (object ref if receipts are also written as objects)
* `final_reason_codes[]`
* `policy_rev`
* optional `supersedes_ref` (if this quarantine supersedes a prior pending or ties into a remediation chain)

### Hard invariants

* **QUARANTINED becomes durable truth** in the ledger and is queryable via M10.
* **Idempotent finalization**: if the same quarantine is finalized twice, it results in the same stored truth (no duplicate receipts).
* **No override of ADMITTED**: if a dedupe_key has already been finalized as ADMITTED, quarantine finalization for that same key is rejected and recorded as an internal inconsistency incident (this should not happen if the ledger reservation rules are followed).

### Reject routing

If the ledger is temporarily unavailable after evidence was written:

* M9 retries J14 until it can finalize the receipt (evidence exists; receipt completion is mandatory).
* During this window, ops can still see “evidence present but receipt pending” via M9, but the official admission truth is not complete until J14 lands.

---

## The big picture of J8–J14 (the production spine)

These joins form IG’s **truth spine**:

* **J8** converges everything into a canonical admission candidate
* **J9/J10** enforce “ADMIT iff durable EB append” with crash safety
* **J13/J14** enforce “QUARANTINE always leaves evidence + a receipt”
* **J11/J12** make the system operable/auditable without changing truth

---

Got it. Here are **J15–J20** — the joins that make IG **operable**, **reconcilable**, **profile-driven**, and **safe under overload**, while preserving the outer pinned meanings.

I’m keeping each internal subnetwork opaque and only defining the joins.

---

## J15 — M9 → M10: Quarantine evidence ready

### Purpose

Make quarantine **discoverable and triageable** without polling raw storage. This is the “E2 becomes possible” join.

### What crosses

`EvidencePointer`:

* `receipt_key` (dedupe_key if known, else intake_id)
* `quarantine_ref` (authoritative pointer to evidence bundle)
* `reason_codes[]` + `retryable_flag`
* `created_at_utc`
* `retention_expiry_utc` (if TTL applies)
* `access_class` (who is allowed to view evidence)

### Hard invariants

* If an item is quarantined, **a quarantine_ref exists** and **M10 can surface it**.
* Evidence is **immutable**; this join never represents “updated evidence,” only pointers to immutable bundles.

### Reject routing

* If M10 is unavailable, J15 does not block quarantine completion. Evidence still exists and can be fetched directly via `quarantine_ref`; discoverability is restored when M10 returns.

---

## J16 — M10 → M7: Receipt lookup query

### Purpose

Answer **E1 (“what happened to my event?”)** deterministically from the ledger—never from scanning the bus.

### What crosses

`LookupQuery` (one-of):

* `receipt_id`
* `dedupe_key`
* `event_id + producer + event_type`
* `run pins` (scenario_id/run_id/manifest_fingerprint/parameter_hash/seed) for scoped queries
* optional `time_window` for paging (operational only)

### Hard invariants

* Lookups are **read-only** and return **ledger truth** only: `ADMITTED | DUPLICATE | QUARANTINED` plus the authoritative pointer (`eb_ref` or `quarantine_ref` or `original_receipt_ref`).
* M10 does not “recompute outcomes.” It only queries M7.

### Reject routing

* If M7 is unavailable, M10 returns “unavailable; retry” (not a guessed answer, not a scan fallback).

---

## J17 — M10 → M9: Quarantine fetch / triage query

### Purpose

Drive **E2 triage**: fetch evidence, classify it, and initiate remediation—without mutating history.

### What crosses

`QuarantineQuery/TriageAction`:

* `quarantine_ref`
* `requestor_principal`
* `purpose` = `inspect | classify | remediate`
* optional `triage_tags` (e.g., `schema_drift`, `run_not_ready`, `auth_denied`)
* optional `remediation_plan_ref` (pointer to the intended fix plan/tool)

### Hard invariants

* Access control is enforced here: evidence is released only to authorized principals.
* Triage actions **never edit** evidence. Any “fix” results in a new re-ingest submission (J20).

### Reject routing

* Unauthorized principal → hard deny.
* Missing evidence → “not found” (and the receipt remains the source of truth).

---

## J18 — Config plane → (M2, M5, M8, M10): Profile update joins

### Purpose

Make IG **environment-ladder compliant**: same semantics everywhere, different *operational envelope* via versioned profiles.

### What crosses

`ProfileUpdate` (independently versioned, but activated together via an **ActiveProfilePointer**):

* `policy_rev` (M2)
* `schema_catalog_rev` (M2)
* `gate_map_rev` (M5)
* `commit_policy_rev` (M8: retry budgets/timeouts/backpressure posture)
* `ops_thresholds_rev` (M10: alerting/degrade trigger thresholds)

### Hard invariants

* **Activation is atomic at the “active pointer” level**: IG runs either the old active set or the new active set—never a half-applied mix.
* Every receipt/telemetry emission is stamped with the **active revisions in force** (at least `policy_rev`; and for legacy engine pull also `gate_map_rev`).
* Unknown revision state is fail-closed: if a module cannot load the active revision, that module becomes unavailable and IG refuses acceptance rather than silently weakening rules.

### Reject routing

* Bad/invalid profile artifact → activation rejected; IG stays on the previous active set.
* Missing artifact needed for activation → activation rejected; no partial.

---

## J19 — M10 → M1: Ingress throttling / circuit-break directives

### Purpose

Keep IG **correct under pressure**. When the truth surfaces (ledger/evidence/EB) are unhealthy, IG must stop accepting work rather than create lying receipts or silent drops.

### What crosses

`IngressControl`:

* `ingress_state` = `OPEN | THROTTLE | PAUSE`
* `rate_limit` and/or `max_inflight`
* `reject_mode` = `backpressure | fail_fast`
* `reason` = `EB_UNHEALTHY | LEDGER_UNHEALTHY | QUARANTINE_STORE_UNHEALTHY | OVERLOAD`

### Hard invariants

* IG never accepts an item it cannot bring to a **durable outcome** (ADMIT/DUPLICATE/QUARANTINE with receipt).
* Under PAUSE:

  * HTTP ingress fails fast with retryable error (no receipt promised).
  * Bus ingress is not acknowledged (so upstream redelivery semantics remain correct).
* Under THROTTLE:

  * work is admitted only up to safe inflight capacity; beyond that, it is backpressured/fail-fast (again: no fake receipts).

### Reject routing

* If M10 is down, M1 falls back to a conservative default: **PAUSE** when it cannot verify safety. (Fail safe, not “keep going.”)

---

## J20 — (M10 or M9) → M1: Remediation re-ingest submission

### Purpose

Make remediation **first-class and append-only**: fixes re-enter through the same front door; history is not mutated.

### What crosses

`ReingestSubmission`:

* `corrected_event` (full canonical envelope + payload)
* `supersedes_ref` (points to prior `receipt_id` and/or `quarantine_ref`)
* `remediator_principal` (who is submitting the fix)
* optional `parent_event_id` (if you choose to chain causality in the envelope)

### Hard invariants

* Remediation uses the **same ingestion semantics** as any producer: it goes through M1→M2… and yields a **new receipt**.
* The prior quarantine is never edited; the new receipt explicitly forms a **supersedes chain** to it.
* Remediation submitters are authenticated/authorized as producers (no “ops bypass”).

### Reject routing

* Missing supersedes linkage → remediation submission is rejected (because it would create “mystery fixes” that can’t be audited).
* Unauthorized remediator → rejected.

---

### The connective tissue these joins create

* **J15–J17** make D/E/F real: quarantine and receipts are queryable and triageable without scanning.
* **J18** is the environment ladder control surface: profiles change the envelope, not the graph.
* **J19** prevents semantic corruption under stress.
* **J20** guarantees “fixing” is append-only, receipted, and auditable.

---

Got it. **P1–P4 are the four internal path families for *push ingest*** (J3 semantics) — they differ only in where the decision branches and what durable truth gets written.

I’ll illuminate each path **purely as a composition of the joins (J1–J20)** and the **observable outcomes**. Subnetworks stay opaque.

---

## P1 — Push ingest ADMIT (maps to A1)

**Goal:** Take a producer-submitted event and make it a **durable, replayable platform fact** by appending it to EB, then issuing an **ADMITTED** receipt.

### Path shape (joins)

**J1 → J2 → J3 → J8 → J9 → J10 → J11 (+ J12)**

### What happens, decisively

1. **Normalize intake** (**J1 M1→M2**)
   The incoming item becomes an `IntakeItem` with a bound `producer_principal` and a `raw_input_ref`.

2. **Validate envelope + bind policy** (**J2 M2→M3**)
   M2 enforces canonical envelope + policy requirements and outputs a `PolicyBoundEvent`.
   If this step succeeds, the event is *structurally admissible* to attempt run anchoring.

3. **Anchor to run/world when run-scoped** (**J3 M3→M6**)

   * If run-scoped: M3 resolves the run via SR join surface and requires it to be **READY**.
   * If non-run-scoped: M3 marks it explicitly non-run-scoped.
     Output is an `AnchoredEvent`.

4. **Canonicalize into an admission-ready event** (**J8 M6→M7**)
   M6 produces the final canonical envelope (no more envelope mutation beyond this point), plus the provenance pointers needed for audit/reconciliation.

5. **Reserve admission truth (first-seen)** (**J9 M7→M8**)
   M7 computes `dedupe_key`, writes a **PENDING** ledger reservation, and only then emits a `FirstSeenTicket`.

6. **Durably append to EB** (inside M8)
   M8 appends to `fp.bus.traffic.v1` using the deterministic `partition_key` stamped for this event.

7. **Finalize ADMITTED only on ack** (**J10 M8→M7**)
   EB ack produces `(topic, partition, offset)`. M8 sends `CommitAck`.
   M7 finalizes the ledger record to **ADMITTED** with that EB ref.

8. **Make it operable & auditable**

   * **J11 (M7→M10):** Receipt pointer becomes queryable for “what happened?”
   * **J12 (M8→M10):** Commit telemetry + optional pointer notification.

### Hard outcome invariants

* **ADMITTED iff EB ack exists.** There is no ADMITTED receipt without `(partition, offset)`.
* The receipt is discoverable by stable keys (event identity / dedupe key) via M10.
* The upstream ingress is considered “handled” only after the ADMITTED receipt exists (for HTTP that’s the response; for bus ingest that’s when IG acks the message).

---

## P2 — Push ingest DUPLICATE (maps to A2)

**Goal:** When the same logical event is resent, produce **no new EB append** and return a stable **DUPLICATE** outcome pointing to the prior truth.

### Path shape (joins)

**J1 → J2 → J3 → J8 → (M7 decides duplicate) → J11**
*(No J9/J10 because no commit.)*

### What happens, decisively

1. **Same front steps as P1**: intake normalization (J1), policy/envelope enforcement (J2), run anchoring (J3), canonicalization (J8).

2. **Duplicate decision at the ledger (M7)**
   M7 computes `dedupe_key` and finds an existing ledger record. The outcome is **DUPLICATE** and the response is determined entirely by the existing record’s terminal state:

   * **Duplicate-of ADMITTED:** return DUPLICATE pointing to the **original EB ref** (topic/partition/offset) and/or original receipt ref.
   * **Duplicate-of QUARANTINED:** return DUPLICATE pointing to the **original quarantine_ref** (evidence bundle) and original receipt.
   * **Duplicate-of PENDING:** return DUPLICATE pointing to the **pending ledger record** (meaning: “already in flight; retry later if you need confirmation”).

3. **Expose via ops surface** (**J11 M7→M10**)
   M10 can answer the lookup without scanning EB.

### Hard outcome invariants

* No new append occurs on P2.
* DUPLICATE always points to an existing, authoritative outcome (admitted/quarantined/pending) — never a guess.

---

## P3 — Push ingest QUARANTINE (maps to A3)

**Goal:** If the event cannot be safely admitted, write **durable evidence + a QUARANTINED receipt** (no silent drop), and do **not** append to EB.

### Path shape (joins)

The prefix is always the same until the failure point; then it converges:

**J1 → [fails at M2 or M3 or M6 or M7 or M8] → J13 → J14 → J11 (+ J15)**

### What triggers P3 (canonical categories)

P3 is taken when any of these are true:

* Envelope invalid / required fields missing
* Producer identity mismatch / authz deny
* Policy denies `(producer,event_type)` or schema unknown/invalid under required validation
* Missing required pins for the event’s pin class
* Framing/canonicalization fails (cannot produce required envelope fields deterministically)
* Ledger cannot safely reserve or finalize truth **after evidence can be persisted**
* EB commit ultimately fails beyond retry budget (commit deadletter)

### What happens, decisively

1. **Failure is converted into a QuarantineRequest** (**J13 to M9**)
   The request includes:

   * `raw_input_ref` (always)
   * `reason_codes` (canonical taxonomy)
   * diagnostics (what failed, where, why)
   * context refs (run context if known; engine locator/row pk if relevant)

2. **Evidence bundle is persisted** (inside M9)
   M9 writes `ig/quarantine/...` evidence objects.

3. **Quarantine is finalized as durable admission truth** (**J14 M9→M7**)
   M7 writes/updates the ledger record to **QUARANTINED** with `quarantine_ref`.

4. **Ops surfaces updated**

   * **J11:** receipt becomes queryable (E1)
   * **J15:** evidence pointer becomes triageable (E2)

### Hard outcome invariants

* QUARANTINE always implies **evidence exists + receipt exists**.
* No EB append occurs on P3.
* If IG cannot persist **both** evidence and the quarantine receipt, it does not “pretend quarantine”; it fails the ingest attempt so upstream retries. (No lying outcomes.)

---

## P4 — Push ingest UNREADY / UNJOINABLE (maps to A4)

**Goal:** Handle run-scoped events that cannot be anchored to a valid run context **without admitting them**. This is a specialized form of quarantine/hold driven by the Run/World Anchor.

### Path shape (joins)

**J1 → J2 → (M3 anchor fails) → J13 → J14 → J11 (+ J15)**
*(It’s P3’s structure, but the failure source and reason taxonomy are specific.)*

### The three authoritative P4 cases

1. **RUN_NOT_READY**
   Run exists but is not READY → event becomes **HOLD-class QUARANTINE** with `retryable_flag=true`.

2. **UNKNOWN_RUN**
   Run context cannot be resolved at all → event becomes **HOLD-class QUARANTINE** with `retryable_flag=true`.

3. **PIN_MISMATCH**
   Run is READY, but event pins contradict the SR join surface → **terminal QUARANTINE** (`retryable_flag=false`).
   This is treated as corruption/drift, not a timing issue.

### What happens, decisively

* M3 does not “best effort” anchor.
* It emits a quarantine request with reason codes reflecting the case above.
* The event is stored in quarantine evidence + ledger receipt (same mechanics as P3).
* Because HOLD is represented as a quarantine-class receipt, ops can:

  * inspect it (E2),
  * and re-ingest later via the remediation path (P7) when READY exists.

### Hard outcome invariants

* No run-scoped event is admitted before it is anchorable to a READY run context.
* HOLD is **not** a fourth outcome. It is **QUARANTINED with retryable semantics** and durable evidence.

---

## Quick “how these four relate”

* **P1** makes a platform fact (EB append + ADMITTED receipt).
* **P2** refuses to make a second fact (DUPLICATE points to prior truth).
* **P3** refuses admission but leaves proof (QUARANTINE evidence + receipt).
* **P4** is P3 specialized for run-anchoring failures (UNKNOWN/NOT_READY vs MISMATCH).

---

## USER: PAUSE FOR REFLECTION

Done — I’ve re-grounded on everything we’ve declared so far. To prevent drift/contradictions going forward, here’s the **authoritative “design ledger” for this chat** (what I will treat as pinned unless you explicitly overrule it).

## Outer pins IG must never violate

* IG is the **trust boundary**: every intake attempt ends in exactly **one** outcome: **ADMIT / DUPLICATE / QUARANTINE** (no silent drops).
* **Canonical envelope** is the boundary object; admitted traffic must have required fields (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`).
* **ADMIT means durable EB append**: no EB ack ⇒ no ADMITTED receipt.
* **READY + `run_facts_view` is the only run/world join surface**: no scanning “latest”.
* **Engine pull is Pull-model**: SR READY triggers IG pull; ingestion starts only after READY.
* **No PASS → no read** for engine-derived ingestion, gate-specific verification; IG is a required verifier.
* Only **`business_traffic`** becomes EB traffic; `truth_products/audit_evidence/ops_telemetry` never do.
* Environment ladder: **same semantics** in local/dev/prod; only operational envelope varies.

## IG first-layer internal subnetworks (opaque modules)

M1 Intake, M2 Envelope+Policy, M3 Run/World Anchor, M4 Engine Pull Orchestrator, M5 Proof/Gate Enforcement, M6 Framer/Canonicalizer, M7 Admission Ledger/Idempotency, M8 EB Commit+Receipt Publisher, M9 Quarantine Vault+Remediation, M10 Ops Surfaces (recon/health/telemetry).

## Internal joins we’ve defined (high-level truth)

* **J1–J3 (push front-half):** normalize intake → policy/envelope gate → run/world anchor → canonicalization.
* **J4–J7 (legacy engine pull front-half):** READY start → run ingest plan from `run_facts_view` → per-target candidates → proofed sources only.
* **J8–J14 (truth spine):** canonical admission candidate → first-seen ticket (PENDING reservation) → EB ack → finalize ADMITTED; or quarantine request → evidence → finalize QUARANTINED; receipts always queryable.
* **J15–J20 (ops/control):** evidence pointers → receipt lookup → quarantine triage → atomic profile activation → ingress throttle/circuit-break → remediation re-ingest re-enters through intake (no bypass).

## Path families we’ve illuminated (P1–P4)

* **P1:** Push ADMIT (J1→J2→J3→J8→J9→J10→J11 [+J12]).
* **P2:** Push DUPLICATE (J1→J2→J3→J8→M7 duplicate decision→J11).
* **P3:** Push QUARANTINE (fail anywhere → J13→J14→J11 [+J15]).
* **P4:** Push UNREADY/UNJOINABLE is **not** a 4th outcome: it’s **QUARANTINE-class with retryable semantics**, except pin mismatch is terminal.

From here on, I’ll actively **check every new design statement against this ledger**. If something would conflict, I’ll stop and explicitly say: “this contradicts X; the authoritative choice is Y.”

---

Cool. **P5–P9** are the remaining IG path families (legacy engine pull ingestion + remediation + reconciliation + observability/control). I’ll keep every subnetwork opaque and describe each path as a **join-composition** with **hard outcomes**.

---

## P5 — Engine pull ingest ADMIT (maps to B1–B4)

**Goal:** SR READY triggers IG to pull **only** SR-declared engine `business_traffic`, prove it’s readable (PASS + instance proof), frame rows into canonical envelopes, then admit them to EB with receipts.

### Path shape (joins)

There are **two layers**: a **run-level orchestration spine** and a **per-event admission loop**.

#### Run-level orchestration spine

**J4 → J5 → (J6 → J7)***

* **J4 (M4→M3):** start ingestion for `(scenario_id, run_id)` on READY
* **J5 (M3→M4):** return `RunIngestPlan` (run pins + run_facts_view_ref + traffic_targets[])
* **J6 (M4→M5):** emit `EngineTrafficCandidate` per traffic target
* **J7 (M5→M6):** emit `ProofedTrafficSource` **only** if proofs pass

* J6→J7 repeats per target. If all targets pass proof preflight, we proceed to emission.

#### Per-event admission loop (for each row produced by M6)

**J8 → (J9 → J10) or DUPLICATE → J11 (+J12)**

* **J8 (M6→M7):** `AdmissionCandidate` (canonical envelope event)
* **M7 decision:** first-seen vs duplicate

  * first-seen → **J9 (M7→M8)** ticket → EB append → **J10 (M8→M7)** ack → **J11 (M7→M10)** receipt
  * duplicate → **J11** duplicate receipt (no append)
* **J12 (M8→M10)** commit telemetry / optional pointer notifications

### Hard invariants

* Ingestion begins **only after READY** (Pull model).
* M4 ingests **only targets listed in run_facts_view** (no discovery).
* M5 enforces **no PASS → no read** and instance-proof binding; nothing else is allowed to read.
* Every admitted event follows the same truth spine: **ADMIT iff EB ack**.
* **Re-running ingestion for the same run_id is safe**: M7 dedupe ensures events become DUPLICATE (no duplicate appends).
* **Event identity scope is run-safe:** consumers treat `(run_id, event_id)` as the uniqueness tuple (event_id may repeat across distinct run_id by design).

### What P5 produces

* EB receives the admitted business traffic events (canonical envelopes).
* M7 ledger contains receipts for each admitted/duplicate event.
* M10 can answer “what happened?” for any event emitted or attempted.

---

## P6 — Engine pull ingest QUARANTINE (maps to B5)

**Goal:** Fail closed when anything about the run join surface / target list / proofs / framing / commit makes ingestion unsafe, leaving durable evidence + receipts.

### Path shape (joins)

P6 splits into **preflight failure** (no events emitted) vs **emission-time failure** (some events may already have been admitted before the failure).

#### P6a — Preflight quarantine (run/plan/target invalid)

**J4 → J5 → (J6 fails OR J7 fails) → J13 → J14 → J11 (+J15)**

This is the decisive rule:

* If any declared traffic target cannot be proven readable, **the run ingestion job does not emit a single event**.
  Proof happens before read/emit, so we don’t create partial “facts” from an inadmissible run plan.

**Typical reasons:**

* join surface unreadable/inconsistent
* target not `business_traffic`
* PASS missing / FAIL / wrong verification method
* instance proof missing/mismatch
* digest required but absent

#### P6b — Emission-time quarantine (row-level issues during framing/commit)

Once preflight passes, M6 reads + frames. If a **row** cannot be framed into a valid canonical envelope:

**Row quarantine path:** `… → J13 → J14 → J11 (+J15)` (per-row evidence + receipt)

**Run continues** after row quarantine. This is the production posture:

* systemic issues are caught by preflight/schema checks;
* sporadic bad rows are quarantined without dropping the whole run.

If EB commit repeatedly fails beyond retry budget for a first-seen event:

* that event becomes **commit-deadletter quarantine** via **J13→J14** (event-level quarantine), and ingestion continues for later events.

### Hard invariants

* No scanning; no best-effort “read without proof.”
* Preflight proof failure yields **zero emitted events** for that run ingestion attempt.
* Every quarantine yields **evidence + receipt** (or the ingestion attempt fails and is retried; no fake outcomes).

---

## P7 — Quarantine remediation → re-ingest (maps to F1/F2)

**Goal:** Fix quarantined items without mutating history; all remediation re-enters IG through the same front door and yields new receipts.

### Path shape (joins)

#### Triage/inspection

**J17 (M10→M9)** to fetch evidence and decide remediation action.

#### Re-ingest submission (append-only correction)

**J20 (M10/M9→M1)** submit `ReingestSubmission {corrected_event, supersedes_ref}`

Then it follows one of the existing ingestion paths:

* corrected push event → **P1/P2/P3/P4**
* engine run remediation → fix join surface/proofs upstream, then SR re-emits READY and IG re-runs **P5/P6** idempotently

### Hard invariants

* Remediation never edits old receipts/evidence.
* New attempt produces a **new receipt** that explicitly links to what it supersedes (`supersedes_ref` + optional `parent_event_id`).
* No “ops bypass”: remediation still passes through M1→M2… like any producer input.

---

## P8 — Reconciliation (“what happened to my event?”) (maps to E1/E2)

**Goal:** Deterministic answers without scanning EB or “latest”; everything comes from receipts/evidence surfaces.

### Path shape (joins)

#### E1 — receipt lookup

**M10 → J16 → M7 → M10**

* Query by `receipt_id` / `dedupe_key` / `(event_id, producer, event_type)` / run pins
* Return: outcome + pointer (`eb_ref` or `quarantine_ref` or original receipt ref)

#### E2 — quarantine inspection

**M10 → J17 → M9 → M10**

* Fetch evidence bundle by `quarantine_ref`
* Return: diagnostics + raw_input_ref + reason codes + retryability

### Hard invariants

* M10 never guesses by reading the bus.
* If ledger/evidence stores are unavailable, the answer is “unavailable, retry”—not a scan fallback.

---

## P9 — Observability + internal control feedback (maps to G)

**Goal:** Keep IG correct and operable under real load/failure without changing semantic meaning.

### Path shape (joins)

#### Telemetry aggregation and export

* **J11 (M7→M10):** receipt index feed (outcome rates + reason codes)
* **J12 (M8→M10):** commit telemetry (latency/retries/backlog)
* **J15 (M9→M10):** quarantine evidence pointers (triage queues)

M10 exports metrics/logs/traces to the observability pipeline.

#### Local protective control loop (inside IG)

**J19 (M10→M1)** ingress control:

* `OPEN` normal
* `THROTTLE` when near capacity
* `PAUSE` when EB/ledger/quarantine store cannot guarantee durable outcomes

#### Profile-driven behavior (environment ladder compliance)

**J18 (Config→M2/M5/M8/M10)** atomic profile activation:

* policy rev, schema catalog rev, gate map rev, commit policy rev, thresholds rev
* receipts/telemetry are stamped with the active revisions

### Hard invariants

* Observability never becomes “shadow behavior change.” Any protective action is explicit (J19) and does not invent outcomes.
* Under PAUSE, IG fails fast / applies backpressure rather than issuing lying receipts.
* Profile changes are atomic and attributable; no half-applied policy state.

---

Yes — a production IG has **several intentional loops**. They’re the mechanisms that make “at-least-once” + “no silent drop” + “admit means durable” actually work without drift.

## Data-plane loops (make ingestion correct under retries)

### 1) Upstream redelivery loop → IG dedupe loop

**Cycle:** Producer/bus retries the *same* event → IG sees it again → **M7** returns **DUPLICATE** (or the already-final outcome).
**Ends when:** upstream stops retrying (because it got a receipt / learned the outcome).
**Why it exists:** at-least-once delivery is assumed; duplicates are normal.

### 2) Commit retry loop (PENDING → append → ack)

**Cycle:** **M7** reserves PENDING → **M8** attempts EB append → if no ack/timeout, retry append → once ack arrives, finalize ADMITTED.
**Ends when:** ack arrives OR retry budget exhausted.
**If budget exhausted:** it **terminates in QUARANTINE** (`COMMIT_DEADLETTER`) with evidence (no “lost limbo”).

### 3) Engine pull resume loop (run job checkpointing)

**Cycle:** READY triggers run ingestion job → reads targets → frames rows → admits events → if IG restarts or job is interrupted, it resumes from its checkpoint and may re-read/re-emit candidates → **M7 dedupe** prevents double-admits.
**Ends when:** all SR-declared traffic targets for the run are fully processed.

---

## Control-plane / readiness loops

### 4) READY redelivery loop (idempotent)

**Cycle:** SR may re-emit READY (or READY is redelivered) → **M4** receives it again → M4 requests plan again → job resumes or no-ops.
**Ends when:** job is already complete and further READY signals cause no work.

### 5) HOLD rehydration loop for run-not-ready push events

(For P4 cases: `RUN_NOT_READY` / `UNKNOWN_RUN` holds.)
**Cycle:** run-scoped push event arrives before READY → IG records **QUARANTINE(HOLD)** → later READY appears → IG’s hold-rehydrator re-submits that held item internally (with `supersedes_ref`) through normal intake → it becomes ADMIT/DUPLICATE/QUARANTINE.
**Ends when:** each held item reaches a terminal outcome under a READY run context.
**Key rule:** the original hold receipt is **not edited**; the new outcome **supersedes** it.

---

## Ops loops (humans/tools in the loop)

### 6) Quarantine remediation → re-ingest loop (P7)

**Cycle:** triage (E2) → fix payload/pins/proofs/policy → re-submit through intake (J20) → new receipt → possibly repeat.
**Ends when:** item is ADMITTED or deemed terminal quarantine.

### 7) Reconciliation loop (“what happened?”)

**Cycle:** producer/operator queries (E1/E2) → gets receipt/evidence pointers → decides retry/remediate → queries again.
**Ends when:** the operator is satisfied (and/or remediation is complete).

---

## Stability loops (keep IG operable without lying)

### 8) Backpressure/circuit-break loop (J19)

**Cycle:** M10 detects EB/ledger/quarantine-store pressure → sends `THROTTLE/PAUSE` to intake → load drops → health recovers → M10 re-opens intake.
**Ends when:** the platform returns to a steady state.
**Key rule:** under PAUSE, IG **does not** accept work it can’t finish with a durable outcome.

---

## Config/upgrade loops

### 9) Profile activation loop (J18)

**Cycle:** config plane publishes new active profile pointer → modules load/validate → if any required artifact can’t be loaded, activation is rejected and IG stays on the previous active set.
**Ends when:** a consistent active profile is loaded and stamped into receipts/telemetry.

---

## Loops that do **not** exist (explicitly banned by our outer pins)

* No “scan latest engine outputs until something looks right.”
* No silent auto-fix loop that mutates payload/pins and admits anyway.
* No bypass loop where internal producers (DF/AL/Case) publish straight to EB.

---

Yep — before we “open the inner nodes,” we should pin **what IG looks like as a deployment unit on the environment ladder**, and the **few deployment truths** that will otherwise cause drift later.

## 1) The pinned deployment shape of IG (what it reads/writes, everywhere)

IG is an **always-on service deployment unit** (not a job), and it has these fixed boundary surfaces:

* **Reads**

  * producer ingress: **bus input or HTTP ingress**
  * **`sr/run_facts_view`** (for run joinability + legacy engine pull)
  * policy profiles
* **Writes**

  * admitted events → **`fp.bus.traffic.v1`**
  * quarantine evidence → **`ig/quarantine/...`**
  * receipt/quarantine index → **DB `ig`**
  * optional pointer events → **`fp.bus.audit.v1`**
* **Must persist as truth**

  * “admission truth” (receipts + decisions) + quarantine evidence pointers (DB + object)

This *does not change* across local/dev/prod; only the substrate implementation changes (FS vs S3, sqlite vs postgres, local broker vs Kafka-compatible, etc.).

---

## 2) How the internal IG network maps to runtime in prod (the “final” deployment view)

We are **not** turning your internal modules into microservices. They remain internal modules, but **production runs IG in two runtime roles** (same codebase, shared truth stores), because push-ingest and legacy engine-pull have different load patterns:

### Role A — `ig-ingress` (front-door pool)

* handles producer HTTP ingress and/or producer bus input
* runs the P1–P4 push path families at high QPS
* serves the Ops surfaces (receipt lookup / health / minimal admin)

### Role B — `ig-enginepull` (worker pool)

* subscribes to SR READY / reads `run_facts_view`
* runs P5–P6 (legacy engine pull ingestion) with controlled concurrency

**Shared truth dependencies (both roles):**

* DB `ig` (receipts + dedupe truth)
* `ig/quarantine/...` evidence store
* `fp.bus.traffic.v1` writer permissions

This is the cleanest “production component” posture because it prevents legacy engine pull workloads from starving the real-time ingest boundary, while keeping one authoritative “IG truth.” (And it still respects the doc’s pinned stance that modules are conceptual, not separate deployables.)

---

## 3) Environment ladder mapping (what changes vs what must not)

Your ladder pin is explicit: **same platform graph + rails everywhere; only operational envelope changes**.

### Local (laptop)

* **Same semantics**: IG still admits/quarantines/duplicates; still writes receipts/evidence; still appends to EB.
* “Production-shaped local” substrate is encouraged:

  * Redpanda (EB), MinIO (artifact store), Postgres (DBs), OTel collector + Grafana stack.
* Differences allowed:

  * permissive allowlists/dev creds
  * short retention
  * debug observability

### Dev (shared integration)

* Same runtime roles (`ig-ingress` + `ig-enginepull`) but smaller scale.
* Security is “real enough” to catch prod failures: unauthorized producers, missing PASS evidence, etc.
* Medium retention, representative volumes, dashboards/alerts.

### Prod (hardened)

* Same runtime roles, scaled and HA’d.
* Strong authn/authz on the IG boundary + quarantine access, strict change control, longer retention + archive continuity, meaningful SLO corridor checks.

---

## 4) The other deployment angles we should pin now (before opening inner nodes)

### A) “Production-shaped local” is non-negotiable for IG correctness

Because IG’s semantics depend on **real** at-least-once delivery, offsets, and failure modes, local should run the same substrate shapes (Kafka-style bus + transactional DB + S3-style object store + OTel).
Otherwise you end up “testing a different platform” locally.

### B) Promotion model (how deployment evolves without drift)

Promotion is **not** “rewrite for prod.” It’s:

* same binaries/code
* same rails/contracts
* different environment profile (endpoints/credentials/retention thresholds)
* stronger policy configs (security + corridor checks)

### C) Versioning + migrations (so upgrades don’t break the trust boundary)

IG emits/version-controls contracts and breaking changes via explicit versions + migration plans.
So deployments need:

* schema migrations for DB `ig`
* controlled activation of new policy/schema/gate map revisions (no half-applied behavior)

### D) Backpressure posture must be explicit (deployment/SLO reality)

Under overload IG must choose a posture that never produces invisible loss:

* bounded buffer + backlog surfaced, **or**
* fail intake requests, **or**
* shed load only with traceable outcomes (receipts/telemetry) 

This directly affects deployment sizing and health checks (what “ready” means for IG pods).

### E) Observability is a required dependency, not a nice-to-have

Because DL corridor checks depend on real signals, local/dev/prod should all run OTel pipelines (sampling differences are fine).

---

### The “entering inner nodes” precondition

Once the above is pinned, we can safely open internal modules without drifting into fantasy implementations, because we know:

* what runs as a service,
* what it must read/write/persist,
* how it scales across local/dev/prod,
* and how upgrades and overload behave.

---

## USER: PAUSE FOR REFLECTION

([Past chat][1])([Past chat][2])([Past chat][2])([Past chat][3])([Past chat][2])

Done — I’ve re-anchored on **the exact network we’ve already defined** in this chat so we don’t accidentally invent new behavior when we start opening nodes.

What follows is the **“IG-as-a-component” complex network**, expressed as **opaque nodes + their joins + their path families + their loops + their deployment posture on the environment ladder**. Nothing here adds new semantics; it’s a consolidation of what we’ve already pinned.

---

## 1) IG in the larger platform network (IG as one opaque vertex)

### External nodes IG connects to

* **Producers (external + internal)**: external clients, DF, AL, Case Workbench backend, etc.
* **Scenario Runner (SR)**: provides **READY** and the **join surface** (`run_facts_view`)
* **Data Engine**: provides **business_traffic artifacts** + **gate evidence**
* **Event Bus (EB)**: durable append/replay spine for admitted events
* **IG truth stores**: `ig` receipt index DB + `ig/quarantine/...` evidence store
* **Audit/Decision Log (DLA)**: consumes EB and stitches evidence (by-ref) including IG truth
* **Observability + Degrade Ladder (DL)**: consumes IG telemetry to compute explicit control posture

### Pinned meanings at the platform boundary (unchanged)

* IG is the **single admission choke-point**: every intake attempt ends in **ADMIT / DUPLICATE / QUARANTINE** with a durable truth trail.
* **ADMIT means EB acked append** (no ack → no “admitted” truth).
* Engine “traffic” enters EB via **Pull model**: SR READY → IG pulls SR-declared `business_traffic` targets → wraps to canonical envelope → admits/quarantines.
* **No PASS → no read** for engine-derived ingestion; gate verification is gate-specific; IG is a required verifier.
* Environment ladder: **same semantics** local/dev/prod; only operational envelope changes.

This is the outer graph that constrains every inner node.

---

## 2) IG’s first-layer internal network (opaque nodes that make up the vertex)

These are the opaque nodes we agreed are “one level deeper” modules inside IG:

* **M1 Producer Intake Gateway** (front door: bus/HTTP; binds producer identity; preserves raw input ref)
* **M2 Envelope & Policy Gate** (canonical envelope enforcement + policy application; rejects are explicit)
* **M3 Run/World Anchor** (anchors run-scoped events to SR join surface; READY gating; pin mismatch is terminal)
* **M4 Engine Pull Orchestrator** (subscribes to READY; uses run_facts_view; schedules run ingestion jobs)
* **M5 Proof & Gate Enforcement** (no PASS → no read; gate-specific verification; instance proof)
* **M6 Traffic Framer & Canonicalizer** (push events finalization + engine row→envelope framing; deterministic IDs)
* **M7 Admission Ledger & Idempotency Core** (the internal truth engine: first-seen vs duplicate vs quarantine; pending reservations)
* **M8 Bus Commit & Receipt Publisher** (EB append; only then finalize ADMITTED; commit telemetry/pointers)
* **M9 Quarantine Vault & Remediation Surface** (evidence bundles; quarantine finalize; supports re-ingest with supersedes)
* **M10 Ops Surfaces** (receipt lookup, quarantine triage, health/telemetry, ingress control, profile activation)

These nodes are *still opaque*; we’re only using them to avoid losing the plot.

---

## 3) The internal join graph (how those opaque nodes connect)

We’ve defined joins **J1–J20** and grouped them by function:

### Push front-half joins (P1–P4 use these)

* **J1** M1→M2: normalized intake item (producer principal + raw input ref)
* **J2** M2→M3: policy-bound, envelope-valid event candidate
* **J3** M3→M6: anchored event (READY-backed if run-scoped)

### Engine pull front-half joins (P5–P6 use these)

* **J4** M4→M3: run ingest start (from READY)
* **J5** M3→M4: run ingest plan (pins + run_facts_view ref + traffic targets)
* **J6** M4→M5: per-target engine traffic candidate
* **J7** M5→M6: proofed traffic source (only if PASS + instance proof satisfied)

### Truth spine joins (all admits/quarantines/duplicates converge here)

* **J8** M6→M7: canonical admission candidate
* **J9** M7→M8: first-seen ticket (PENDING reservation already written)
* **J10** M8→M7: EB commit ack (topic/partition/offset) → finalize ADMITTED
* **J11** M7→M10: receipt pointer feed (reconciliation and audit join support)
* **J12** M8→M10: commit telemetry + optional audit pointer events
* **J13** (M1..M8)→M9: quarantine request (reason + evidence refs)
* **J14** M9→M7: quarantine finalization (ledger truth)

### Ops/control joins (operability + environment ladder compliance)

* **J15** M9→M10: evidence pointers for triage
* **J16** M10→M7: receipt lookup queries
* **J17** M10→M9: quarantine fetch/triage actions
* **J18** Config→(M2/M5/M8/M10): atomic profile activation (policy/gates/commit/thresholds)
* **J19** M10→M1: ingress throttle/pause controls (circuit-breaker semantics)
* **J20** (M10 or M9)→M1: remediation re-ingest submissions (no bypass)

That join graph is the structural truth for the IG vertex.

---

## 4) IG path families (end-to-end internal flows)

These are the internal path families we illuminated (composition of joins):

### Push ingest (producer-submitted)

* **P1 Push ADMIT**: J1→J2→J3→J8→J9→J10→J11 (+J12)
* **P2 Push DUPLICATE**: J1→J2→J3→J8→(M7 duplicate)→J11
* **P3 Push QUARANTINE**: fail anywhere → J13→J14→J11 (+J15)
* **P4 Push UNREADY/UNJOINABLE**: J1→J2→(anchor fails at M3)→J13→J14→J11 (+J15)
  (This is *not* a 4th outcome; it is quarantine-class with retryable semantics unless pin mismatch.)

### Engine pull ingest (SR entrypoint)

* **P5 Engine pull ADMIT**: J4→J5→(J6→J7)*→J8→(J9→J10 or duplicate)→J11 (+J12)
* **P6 Engine pull QUARANTINE**:

  * **preflight**: proof/plan failure → J13→J14→J11 (+J15) and emits **zero events**
  * **row-level**: framing/commit failures quarantine per-row via J13→J14 while run continues

### Operations and feedback

* **P7 Remediation**: J17 triage → J20 reingest → then P1/P2/P3/P4 (or fix upstream and rerun P5)
* **P8 Reconciliation**: E1 via J16→ledger; E2 via J17→evidence
* **P9 Observability/control**: J11/J12/J15 feed ops + telemetry; J19 throttles; J18 profile activation

These are the only path families we’re allowed to assume exist inside IG.

---

## 5) The loops that exist (and why they matter)

We pinned that IG contains intentional loops to handle at-least-once realities safely:

* **Upstream redelivery loop** → resolves via **M7 dedupe** (P2 behavior)
* **Commit retry loop**: PENDING reservation → EB append retry → finalize on ack; if exhausted, end in quarantine-class truth
* **Engine pull resume loop**: run ingestion job resumes and re-emits candidates; dedupe prevents double-admit
* **READY redelivery loop**: repeated READY triggers are idempotent (run job resumes/no-ops)
* **Hold rehydration loop**: RUN_NOT_READY quarantines can be reattempted after READY, via remediation or internal re-drive
* **Remediation loop**: triage → fix → re-ingest → new receipt supersedes old; no mutation
* **Backpressure loop**: M10 health drives J19 throttle/pause → recovery → reopen
* **Profile activation loop**: J18 activates configs atomically; failure keeps previous active set

These loops are part of the network; they’re not “implementation quirks.”

---

## 6) Deployment view on the environment ladder

### What IG looks like when deployed (the stable shape)

IG is an **always-on service** with the fixed surfaces we listed earlier: reads ingress + run_facts_view + policy; writes EB + receipt DB + quarantine evidence + optional audit pointers.

### The production runtime split we pinned

Same codebase, two runtime roles (not separate products):

* **ig-ingress**: runs push paths P1–P4 + ops surfaces
* **ig-enginepull**: runs legacy engine pull paths P5–P6

Both share the same authoritative truth stores (`ig` DB + quarantine evidence store) and the same EB writer.

### Local / Dev / Prod: what changes vs what must not

* **Must not change**: the join meanings, outcomes, receipts, gate enforcement posture, READY/run_facts_view posture, and “ADMIT means EB ack.”
* **Allowed to change**: scale, retention, security strictness, observability depth, cost knobs.
* **Critical ladder warning** (already pinned): local must be “production-shaped” enough (broker + object store + DB) so you don’t test a different graph.

---

## The reason we did this pause

When we now start “opening” internal nodes (say, M7 or M5), we will **only** be elaborating the internal logic needed to satisfy the already-defined joins and paths above. If a proposed inner detail would imply a new path, a new outcome, or a new join, we’ll call it out as **drift** immediately.

If you want to proceed, the safest next node to illuminate first is **M7 Admission Ledger & Idempotency Core** (because it is the convergence point that constrains correctness for every path).

---

Yes — illumination should **not** change the network; it only reveals the machinery needed to satisfy the already-pinned joins/paths.

### The opaque nodes (first-layer IG modules)

* **M1** Producer Intake Gateway
* **M2** Envelope & Policy Gate
* **M3** Run/World Anchor
* **M4** Engine Pull Orchestrator
* **M5** Proof & Gate Enforcement
* **M6** Traffic Framer & Canonicalizer
* **M7** Admission Ledger & Idempotency Core
* **M8** Bus Commit & Receipt Publisher
* **M9** Quarantine Vault & Remediation Surface
* **M10** Ops Surfaces (Reconciliation + Health + Telemetry)

### The order I want us to illuminate (designer-locked)

1. **M7 — Admission Ledger & Idempotency Core**
   Sets truth semantics for ADMIT/DUPLICATE/QUARANTINE and makes everything crash-safe.

2. **M8 — Bus Commit & Receipt Publisher**
   Locks “ADMIT iff EB ack” and how commit retry/deadletter is handled.

3. **M9 — Quarantine Vault & Remediation Surface**
   Locks evidence bundles, quarantine finalization, and supersedes/remediation chains.

4. **M3 — Run/World Anchor**
   Locks READY/run_facts_view anchoring, A4 hold semantics, and pin mismatch posture.

5. **M5 — Proof & Gate Enforcement**
   Locks “no PASS → no read”, gate-specific verification, instance proof binding.

6. **M4 — Engine Pull Orchestrator**
   Locks run job lifecycle, target enumeration from run_facts_view, resume behavior.

7. **M6 — Traffic Framer & Canonicalizer**
   Locks row→envelope mapping, deterministic event_id minting, event_type naming.

8. **M2 — Envelope & Policy Gate**
   Locks policy routing, required pins by event_type, schema posture.

9. **M1 — Producer Intake Gateway**
   Locks ingress modes, producer identity binding, raw input capture posture.

10. **M10 — Ops Surfaces**
    Locks lookup APIs, triage UX hooks, throttling signals, profile activation mechanics.

That ordering is intentional: we start with the **truth spine** (M7/M8/M9), then the **anchoring/proof plane** (M3/M5/M4), then the **framing/policy/ingress** (M6/M2/M1), and finish with **ops** (M10).

---

Yep. **M7 is the “truth engine” of IG**: it’s the only place inside IG that is allowed to decide (and durably remember) **FIRST-SEEN vs DUPLICATE vs QUARANTINED**, and it is the thing that makes “**ADMIT means EB ack**” and “**no silent drop**” actually true under retries, crashes, and concurrency.

Below is M7 **as a white box**: the **internal subnetworks that exist inside M7**, and the **machinery** each one must implement.

---

## M7 internal subnetworks

## 7.1 Key & Identity Derivation Core

**Job:** deterministically derive the identity keys that drive idempotency and lookup.

### Inputs

* `AdmissionCandidate` from **J8** (canonical envelope + producer_principal + optional run_context)

### Outputs

* `dedupe_key` (stable)
* `receipt_key` (always present; either dedupe_key or intake_id fallback)

### Design-locked rules

1. **Dedupe key formula (authoritative):**

   * Base tuple (always):
     `K0 = (producer_principal, event_type, event_id, manifest_fingerprint)`
   * If event is run-scoped (has `run_id`):
     `dedupe_key = K0 + (scenario_id, run_id)`
   * Else:
     `dedupe_key = K0`

2. **Receipt key always exists:**

   * If `event_id` is valid → receipt_key is `dedupe_key`
   * If `event_id` is missing/invalid (should be rare once M6 is correct) → receipt_key is `intake_id` (unique attempt identity), and the item is routed to quarantine.

This subnetwork is the reason M7 stays deterministic: given the same input, it produces the same keys, always.

---

## 7.2 Ledger Store & State Machine

**Job:** store the authoritative admission truth in DB `ig` and enforce the “only one terminal outcome per key” law.

### Data model (conceptual, but binding behavior)

There is one primary record per `dedupe_key`:

* `dedupe_key` (unique)
* `state` ∈ {`PENDING`, `ADMITTED`, `QUARANTINED`}
* `first_seen_at`
* `policy_rev_in_force`
* `event_identity` (event_id, event_type, producer_principal, manifest_fingerprint)
* optional `run_identity` (scenario_id, run_id, parameter_hash, seed)
* terminal pointers:

  * if ADMITTED → `eb_ref = (topic, partition, offset)`
  * if QUARANTINED → `quarantine_ref`
* optional: `supersedes_ref` (for remediation chains)

### State machine laws (non-negotiable)

1. **Monotonic terminality**

   * `PENDING → ADMITTED` is allowed
   * `PENDING → QUARANTINED` is allowed
   * `ADMITTED` is terminal and **cannot** become QUARANTINED
   * `QUARANTINED` is terminal and **cannot** become ADMITTED for the same `dedupe_key`

2. **Exactly one terminal outcome per dedupe_key**

   * enforced by a **unique constraint** on `dedupe_key`

This is what prevents “two nodes now require something different”: M7 is the single place that pins outcome truth.

---

## 7.3 First-Seen Reservation & Ticket Issuer

**Job:** decide FIRST-SEEN vs DUPLICATE at **J8**, and only issue a commit ticket when the ledger has reserved the key.

### Inputs

* `AdmissionCandidate` via **J8**

### Outputs

* FIRST-SEEN → `FirstSeenTicket` via **J9** to M8
* DUPLICATE → `ReceiptPointer` via **J11** to M10 (no EB write)
* QUARANTINE → `QuarantineRequest` via **J13** to M9 (when M7 is the deciding failure point)

### The decisive algorithm

When a candidate arrives:

1. Compute `dedupe_key`
2. Attempt **atomic insert** of `{dedupe_key, state=PENDING, …}`

   * If insert succeeds → FIRST-SEEN and emit **J9**
   * If insert fails due to existing key → DUPLICATE, and resolve based on existing state:

     * existing `ADMITTED` → DUPLICATE pointing to existing `eb_ref`
     * existing `QUARANTINED` → DUPLICATE pointing to existing `quarantine_ref`
     * existing `PENDING` → DUPLICATE pointing to the pending record (meaning “already in flight”)

**Key law:** no `FirstSeenTicket` is ever issued without a persisted PENDING reservation.

---

## 7.4 Commit Finalization Coordinator

**Job:** make “ADMIT means EB ack” true.

### Inputs

* `CommitAck` via **J10** from M8

### Outputs

* `ReceiptPointer(ADMITTED)` via **J11** to M10

### Rules

1. **Only J10 can create ADMITTED**

   * If record is `PENDING`, set `ADMITTED` and store `eb_ref`

2. **Idempotent finalization**

   * If record is already `ADMITTED`:

     * the `eb_ref` must match; otherwise this is an internal inconsistency incident (recorded as an ops event), but the stored admission truth is not rewritten.

3. **Commit uncertainty is not “quarantine”**

   * Timeouts / uncertain ack do **not** finalize QUARANTINED (because you cannot safely claim “not appended”).
   * Instead, the record remains `PENDING` and becomes **operationally visible** (health/telemetry) until M8 produces a definitive ack.

This is the production-safe posture that avoids “event is on EB but ledger says quarantined.”

---

## 7.5 Quarantine Finalization Coordinator

**Job:** finalize quarantine truth once evidence exists.

### Inputs

* `QuarantineFinal` via **J14** from M9

### Outputs

* `ReceiptPointer(QUARANTINED)` via **J11** to M10

### Rules

1. If no ledger record exists for the key → create `{state=QUARANTINED, quarantine_ref}`
2. If record exists and is `PENDING` → update to `QUARANTINED` with `quarantine_ref`
3. If record exists and is already `QUARANTINED` → idempotent (must match)
4. If record exists and is `ADMITTED` → quarantine finalization is **rejected** and logged as an internal inconsistency (cannot override admitted truth)

---

## 7.6 Receipt Projection & Query Surface (M7’s “read model”)

**Job:** power reconciliation (E1) and ops (health/telemetry), without scanning EB.

### Inputs

* state transitions inside M7 (PENDING/ADMITTED/QUARANTINED)
* lookup queries via **J16** from M10

### Outputs

* `ReceiptPointer` feed via **J11** to M10
* query responses for:

  * by `receipt_id` / `dedupe_key`
  * by `(event_id, producer, event_type)`
  * by run pins (for run-scoped browsing)

### Rule

M7 is the only source of truth; M10 is a view/UX surface. If J11 delivery is delayed, M10 can still read M7 directly.

---

## 7.7 Integrity Guard & Sweeper

**Job:** keep the ledger truthful and operable in real deployments.

This subnetwork does two things:

1. **Detect stuck PENDING records**

   * record becomes “commit-lagged” if it stays PENDING beyond a corridor
   * emits telemetry that drives **J19** throttling decisions (via M10), rather than inventing outcomes
2. **Detect illegal transitions / inconsistencies**

   * ADMITTED+quarantine_final attempted
   * ADMITTED with conflicting eb_ref
   * missing terminal pointers

This is what keeps M7 safe under restarts and partial failures.

---

# What M7 guarantees to the rest of IG (the contract it enforces)

* **Exactly one terminal outcome per `dedupe_key`**, forever.
* **FIRST-SEEN is concurrency-safe** (no double-admit).
* **ADMITTED iff EB ack is recorded** (no lies).
* **Duplicates are stable**: same event resent yields DUPLICATE pointing to the existing truth.
* **Quarantine is durable truth** once evidence exists, and never overwrites an admitted fact.
* **Reconciliation never needs bus scans**: the ledger is queryable by stable keys.

If you want the clean next step: we illuminate **M8 (Bus Commit & Receipt Publisher)**, because M8 + M7 together are the “two-part machine” that makes the admission boundary real.

---

Alright — **M8 is the “reality boundary” inside IG**: it is the only machinery that can turn a *first-seen ticket* into a **durably appended EB fact**, and it is the component that makes this pinned law true:

> **ADMITTED iff EB acknowledged append** (topic/partition/offset exists).

Below is **M8 as a white box**: the **internal subnetworks inside M8** and the **exact machinery each one performs**.

---

## M8 — Internal subnetworks and machinery

## 8.1 Ticket Intake & Durable Work Queue

**Job:** accept **FirstSeenTicket** work from **J9 (M7→M8)** in a way that survives restarts and prevents “lost pending”.

**Inputs (from J9):**
`FirstSeenTicket = {dedupe_key, ledger_record_id, canonical_event_bytes_or_ref, partition_key, commit_policy}`

**Machinery (design-locked):**

* Tickets are treated as **durable work items** (not “best effort in-memory calls”).
* A ticket is **owned** by exactly one M8 worker at a time (lease semantics).
* If an M8 worker dies mid-commit, the ticket becomes eligible for re-processing (so PENDING doesn’t strand forever).

**Output:** `InFlightCommit` (internal) or backpressure signals to M10 telemetry.

---

## 8.2 Record Builder & Integrity Stamp

**Job:** build the exact EB record that will be appended — without mutating the event semantics.

**Machinery:**

* **Resolve bytes**: if the ticket carries a ref, M8 dereferences it and obtains exact bytes.
* Compute `content_digest = sha256(event_bytes)` (integrity marker).
* Construct EB record with:

  * **value** = canonical event bytes (exact)
  * **key** = `partition_key` (authoritative from the ticket)
  * **headers** (always present; pointer-grade, not meaning-changing):

    * `dedupe_key`
    * `ledger_record_id`
    * `content_digest`
    * run pins if present (scenario_id/run_id/manifest_fingerprint/parameter_hash/seed) for correlation
    * `policy_rev` (so downstream/audit can attribute)

**Hard rule:** M8 does **not** change envelope/payload. It appends exactly what M6 finalized and M7 ticketed.

---

## 8.3 Partition & Topic Router

**Job:** ensure deterministic routing to the correct bus surface.

**Machinery (design-locked):**

* Topic is always **`fp.bus.traffic.v1`**.
* Partition routing is determined by the **record key = `partition_key`** passed in the ticket.
* M8 does not re-choose or “improve” partitioning — it **stamps** what IG already decided at the edge.

---

## 8.4 Producer Session Manager

**Job:** maintain a stable producer identity to EB and make retries safe.

**Machinery (design-locked):**

* Uses a single configured producer identity per IG role (`ig-ingress` and `ig-enginepull` may run separate producer identities for isolation).
* Enables producer-side idempotency where the EB substrate supports it (Kafka-compatible). This reduces duplicates from retry storms.
* Uses acks strict enough that an ack implies a real `(partition, offset)`.

**Hard rule:** M8 never claims success without a broker ack that includes the offset.

---

## 8.5 Commit Tracker (In-flight Concurrency Gate)

**Job:** prevent double-commit attempts for the same `dedupe_key` inside M8 and make retries well-defined.

**Machinery (design-locked):**

* Maintains an in-flight map: `dedupe_key → {attempt_count, last_error, lease_id, start_time}`.
* Ensures **at most one** active append attempt per `dedupe_key` at a time.
* Ensures tickets are processed in a controlled concurrency window (so EB pressure doesn’t avalanche the whole platform).

---

## 8.6 Retry Controller (Commit Loop Engine)

**Job:** implement the commit retry loop without lying.

**Machinery (design-locked):**

* Classifies errors into exactly two buckets:

### (A) Retriable / uncertain

Examples: network timeout, broker unavailable, transient leader changes.
**Action:** keep ticket **in-flight**, retry append under `commit_policy` (bounded attempts + bounded wall-clock).

### (B) Terminal / non-retriable

Examples: topic misconfiguration, authorization failure, record too large (after compression rules), serialization/ref resolution failure.
**Action:** immediately deadletter to quarantine (8.7).

**Hard rule:** while retries are ongoing, the ledger remains **PENDING**. No QUARANTINE is written purely because “it’s taking long”.

---

## 8.7 Commit Deadletter → Quarantine Emitter

**Job:** terminate a ticket into an explicit, auditable outcome when commit cannot succeed.

**Machinery (design-locked):**

* When retry budget is exhausted *or* terminal failure is detected, M8 emits **J13 → M9**:

  * `reason = COMMIT_DEADLETTER`
  * includes:

    * `dedupe_key`, `ledger_record_id`
    * `raw_input_ref` (or event_bytes_ref)
    * commit diagnostics (error codes, attempts, timestamps)
    * `content_digest` and partition_key
* M9 persists evidence and finalizes via **J14**, which transitions the ledger to **QUARANTINED**.

**Hard rule:** this is the only way a PENDING admission becomes “not admitted” in the face of EB failure: **explicit quarantine with evidence**, not silent drop.

---

## 8.8 Ack Publisher (Commit Success → J10)

**Job:** on a definitive broker ack, publish the only message that can create ADMITTED truth.

**Machinery (design-locked):**

* On broker ack, M8 emits **J10 → M7**:

  * `{dedupe_key, ledger_record_id, eb_ref(topic,partition,offset), commit_time_utc, content_digest}`
* M7 finalizes `PENDING → ADMITTED`.
* M8 then marks the work item complete in its durable queue (so it won’t be reprocessed).

**Hard rule:** J10 is only emitted when `(partition, offset)` is known.

---

## 8.9 Telemetry & Pointer Publisher (J12)

**Job:** make the commit process observable and optionally notify downstream indexers without changing truth ownership.

**Machinery (design-locked):**

* Emits **J12 → M10** `CommitTelemetry`:

  * append latency, retry counts, queue depth, failure classes
* Optionally emits pointer-only notifications (either to M10 or `fp.bus.audit.v1`) containing:

  * `dedupe_key`, `eb_ref`, `content_digest`, `receipt lookup key`
* Pointer events are **never** treated as truth; they only point to M7/M9 truth surfaces.

---

## 8.10 Health Signal Producer (feeds M10 + J19 decisions)

**Job:** provide crisp “can IG safely accept first-seen work?” signals.

**Machinery (design-locked):**
M8 continuously reports:

* EB connectivity health
* backlog depth + oldest in-flight age
* rate of commit deadletters
* whether ack latency exceeds corridor thresholds

This is what allows **M10 → J19** throttling/pausing to protect correctness (IG must not accept what it can’t finish with a durable outcome).

---

# What M8 guarantees to the rest of IG

* A ticket either becomes **ADMITTED** (via J10) or becomes **QUARANTINED with evidence** (via J13→J14). It never disappears.
* It never creates “phantom admits”: no ack ⇒ no J10 ⇒ no ADMITTED truth.
* It provides the observable signals needed to throttle intake before correctness breaks.

If you want the next node: **M9 (Quarantine Vault & Remediation Surface)**, because that completes the second half of the “truth spine” (the other terminal outcome besides ADMITTED).

---

Absolutely. **M9 is the “safe failure” engine of IG**: it makes “no silent drop” real by turning any reject into **durable evidence + a QUARANTINED receipt**, and it provides the only sanctioned path for **remediation → re-ingest** without mutating history.

Below is **M9 as a white box**: the internal subnetworks inside it and the exact machinery each performs.

---

## M9 — Internal subnetworks and machinery

## 9.1 Quarantine Intake Router

**Job:** accept quarantine requests from anywhere (J13) and normalize them into a single internal format.

### Inputs

`QuarantineRequest` via **J13** from any module (M1..M8), containing:

* `receipt_key` (dedupe_key if known; else intake_id)
* `reason_codes[]`
* `failure_stage`
* `raw_input_ref`
* `diagnostics`
* optional context:

  * `run_context_ref`
  * engine context: `{engine_output_locator, row_pk, proof_refs}`
  * `policy_rev`

### Machinery (design-locked)

* Validates the request has the **minimum evidence guarantees**:

  * `raw_input_ref` must exist (always)
  * at least one `reason_code` must exist
* Assigns a unique `quarantine_id`
* Classifies quarantine into one of three **quarantine classes**:

  1. **Event-level** (single intake item or single row)
  2. **Target-level** (a whole engine output target)
  3. **Run-level** (join surface invalid / preflight failure for a run ingestion job)

This classification does not change outcome semantics; it only determines evidence packaging and ops presentation.

---

## 9.2 Evidence Bundle Builder

**Job:** build an immutable “quarantine bundle” that is sufficient for triage and later remediation, without requiring rescans.

### Machinery (design-locked)

For every quarantine, construct an evidence bundle with these sections:

1. **Identity & correlation**

* `quarantine_id`
* `receipt_key` (dedupe_key or intake_id)
* `ingest_attempt_id` (from M1 if available)
* run pins if known (`scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`, `seed`)
* producer principal, event_type, event_id if available

2. **Raw input pointer**

* `raw_input_ref` (exact bytes pointer)
  *M9 never copies semantics; it stores pointers and minimal redundant context only.*

3. **Failure diagnostics**

* `failure_stage`
* `reason_codes[]`
* structured error payloads:

  * schema errors
  * pin mismatch diffs
  * authz deny details (minimal)
  * gate/proof verify failures
  * commit deadletter details (from M8)

4. **Upstream proof context** (legacy engine pull quarantines)

* `engine_output_locator`
* `row_pk` (if row-level)
* proof refs used/expected (gate receipts, instance proof refs)
* content digest if involved

5. **Remediation hints** (non-binding guidance)

* `retryable_flag` (true/false)
* recommended next action category:

  * “wait for READY”
  * “register schema”
  * “fix pins”
  * “supply missing proof”
  * “fix auth policy”
  * “replay commit after EB recovery” (rare; usually handled automatically)

**Important:** `retryable_flag` is determined purely from reason taxonomy:

* `RUN_NOT_READY`, `UNKNOWN_RUN`, `SCHEMA_UNKNOWN`, transient dependency failures → retryable
* `PIN_MISMATCH`, malformed envelope, auth violations → terminal

---

## 9.3 Evidence Store Writer

**Job:** persist the evidence bundle to durable object storage under `ig/quarantine/...`.

### Machinery (design-locked)

* Writes a deterministic object prefix layout:

  * by `quarantine_class` (run/target/event)
  * then by `run_id` if present (so ops can list quarantines for a run)
  * then `quarantine_id` as the unique leaf
* Stores:

  * `bundle.json` (the structured evidence bundle)
  * optionally `raw_snapshot.json` if the raw input was already JSON and small (never required; `raw_input_ref` is authoritative)
  * optionally additional attachments (validation logs, proof verification transcript hashes)

**Hard rule:** evidence objects are **immutable** once written.

---

## 9.4 Quarantine Finalizer (J14 emitter)

**Job:** turn evidence into **durable admission truth** by finalizing a QUARANTINED receipt in M7.

### Machinery (design-locked)

Once the evidence bundle is durably written:

* compute `quarantine_ref` (object reference to the bundle)
* emit **J14 → M7** with:

  * `receipt_key` (and `dedupe_key` if known)
  * `quarantine_ref`
  * `final_reason_codes[]`
  * `policy_rev`
  * optional `supersedes_ref` (see remediation)

**Hard rule:** M9 never claims “quarantined” without a stored evidence bundle.

---

## 9.5 Idempotency & De-dup inside Quarantine

**Job:** prevent duplicate evidence spam when the same failure is retried.

### Machinery (design-locked)

* For a given `receipt_key`, repeated identical quarantine requests map to:

  * the same `quarantine_ref` when possible, or
  * a bounded “attempt series” under the same quarantine_id root (not unbounded growth)
* If the request differs materially (new diagnostics, different reason codes), it creates a new quarantine bundle but links to prior attempts.

This keeps ops usable under retry storms.

---

## 9.6 Hold Bucket Manager (A4 semantics inside quarantine)

**Job:** represent “unready/unjoinable” as **quarantine-class truth** with retryable semantics (not a fourth outcome).

### Machinery (design-locked)

* `RUN_NOT_READY` and `UNKNOWN_RUN` quarantines are stored in a distinct “hold class” grouping:

  * still immutable evidence + receipt
  * marked retryable
* Pin mismatch is never “hold”; it is terminal quarantine (`PIN_MISMATCH`).

This preserves the platform law that outcomes are tri-state while still enabling later re-drive.

---

## 9.7 Remediation Planner & Re-ingest Gateway (J20 producer)

**Job:** enable safe “fix-and-retry” without mutating history.

### Machinery (design-locked)

Remediation is always a **new intake attempt** that:

* must carry a `supersedes_ref` pointing to:

  * the prior `quarantine_ref` and/or prior receipt id
* should carry `parent_event_id` when the corrected event is logically “the same story” (envelope supports parent linkage)

M9 does not “edit evidence” or “flip the old receipt to admitted.”
It only produces a **re-ingest submission** (via M10 or directly) that goes back through **M1** (J20).

---

## 9.8 Re-drive Coordinator for Hold Quarantines (optional internal helper)

**Job:** when a run becomes READY, optionally re-drive retryable holds automatically.

### Machinery (design-locked)

* Watches for READY/run context availability (via ops signals)
* Selects retryable holds (`RUN_NOT_READY`, `UNKNOWN_RUN`) that now have a valid run context
* Re-submits them through **J20** as re-ingest submissions with explicit `supersedes_ref`

Even when auto-re-drive is enabled, it never bypasses normal intake; it just automates what an operator could do.

---

## 9.9 Quarantine Exposure Join Producer (J15)

**Job:** make quarantines visible to ops surfaces.

### Machinery (design-locked)

* After evidence is written and J14 is emitted, emit **J15 → M10**:

  * `quarantine_ref`, `reason_codes`, `retryable_flag`, run pins, access class

This powers E2 triage without polling object storage.

---

## 9.10 Access Control & Redaction Guard

**Job:** ensure quarantines don’t become a privacy/security leak.

### Machinery (design-locked)

* Applies an evidence policy:

  * only store minimal authz-deny details
  * redact or avoid persisting sensitive payload fields when policy requires (still preserve raw_input_ref if it points to already-secured storage)
* Enforces access classes on retrieval (used via J17).

This is part of “production-ready” and cannot be deferred.

---

# What M9 guarantees to IG

* Any failure routed to quarantine becomes **durable evidence + a QUARANTINED receipt** (no silent drop).
* Quarantine evidence is **immutable**, and outcomes are **append-only**.
* Remediation is always **new intake**, linked by explicit **supersedes** chains; history is never rewritten.
* Holds are represented as retryable quarantines; pin mismatch is terminal.

If you want the next node to open, the clean one is **M3 (Run/World Anchor)**, because it defines the exact mechanics of READY/run_facts_view anchoring that drive both P4 holds and the entire legacy engine-pull path family.

---

Understood. **M3 (Run/World Anchor)** is the internal IG module that makes the platform’s “join surface” law real:

* **SR is the authority for run existence + readiness**
* **`sr/run_facts_view` is the only map**
* **No run-scoped event is admitted unless it anchors cleanly to a READY run**
* **Pin mismatch is terminal**

Below is M3 as a **white box**: the **subnetworks inside it** and the **machinery** each performs.

---

## M3 internal subnetworks

## 3.1 Run Context Registry

**Role:** Maintain IG’s authoritative in-memory view of “which runs exist and what they are,” sourced only from SR surfaces.

**Inputs**

* `RunIngestStart` from M4 (J4): `{scenario_id, run_id}`
* `PolicyBoundEvent` from M2 (J2): run-scoped candidate with pins

**Outputs**

* `RunContextRecord` (internal object): `{scenario_id, run_id, status=READY, run_facts_view_ref, pins, loaded_at}`

**Machinery (design-locked)**

* Keyed by `(scenario_id, run_id)` only.
* Records are created/updated **only** after successfully reading and validating `sr/run_facts_view`.
* “READY exists” is defined operationally as: *a valid `run_facts_view` is retrievable and internally consistent*. (READY without a usable join surface is treated as not-ready/invalid for anchoring.)

---

## 3.2 Join Surface Fetcher

**Role:** Fetch `sr/run_facts_view` by reference and parse it into structured facts.

**Inputs**

* `(scenario_id, run_id)` and a resolution rule (“where is that run’s join surface?”)

  * For legacy engine pull: triggered by J4 and resolved via SR conventions.
  * For push anchoring: may be triggered on-demand when anchoring requires it.

**Outputs**

* Parsed `RunFacts`: at minimum:

  * `run_pins` (the run’s authoritative pin tuple)
  * `traffic_targets[]` (engine output locators SR has declared as traffic)
  * `proof_refs[]` (gate receipts + instance proofs needed to justify those targets)

**Machinery (design-locked)**

* **No scanning**: it never lists buckets, never searches “latest”, never infers a run from storage patterns.
* Fetch is **by deterministic address** (derived from `(scenario_id, run_id)` under SR’s contract).
* If the object is missing/unreadable: this is not “partial readiness”; it is **RUN_NOT_READY** for anchoring purposes.

---

## 3.3 Join Surface Validator

**Role:** Fail-fast validation of the join surface so downstream modules never see ambiguous run context.

**Inputs**

* Parsed `RunFacts` from 3.2

**Outputs**

* `ValidatedRunFacts` or a run-level anchor failure reason

**Machinery (design-locked)**
This validator enforces four non-negotiable laws:

1. **Pin completeness**

   * `run_pins` must include the full run/world join tuple required by the platform:
     `{scenario_id, run_id, manifest_fingerprint, parameter_hash, seed}`

2. **Internal consistency**

   * Any pins embedded in locators/refs must match the top-level run pins.

3. **Traffic target hygiene**

   * `traffic_targets[]` must be present for legacy engine-pull runs, and each target must be well-formed (has `output_id`, resolved path, and identity tokens).
   * Targets must be declared as **business traffic** (M3 rejects a plan that attempts to treat truth/audit/telemetry as traffic; M5 will also enforce later, but M3 blocks it early).

4. **Proof completeness for declared targets**

   * If a traffic target is instance-scoped, the join surface must include what’s needed to bind instance proof (notably the digest/refs).
   * Missing proof hooks makes the plan invalid; legacy engine pull cannot proceed.

If any of these fail → M3 emits a **run-level quarantine request** (via J13) and produces **no ingest plan**.

---

## 3.4 Push Event Anchor Decision Engine

**Role:** Take a run-scoped event candidate and decide whether it is anchorable **right now**, without “fixing” it.

**Inputs**

* `PolicyBoundEvent` from M2 (J2), which already declares whether the event is run-scoped.
* Run context from 3.1/3.2 as needed.

**Outputs**

* `AnchoredEvent` to M6 (J3), OR an anchor failure routed to quarantine (J13).

**Machinery (design-locked)**

1. **Anchor classification**

   * If policy says `non_run_scoped` → output `AnchoredEvent(anchor_class=non_run_scoped)` immediately.
   * If policy says `run_scoped` → proceed to resolve run context.

2. **Run resolution**

   * Locate `RunContextRecord` for `(scenario_id, run_id)`; if absent, fetch and validate the join surface once.

3. **Readiness rule**

   * If no validated join surface exists → **UNKNOWN_RUN** or **RUN_NOT_READY** (both are retryable quarantine-class outcomes).

4. **Pin match rule (terminal)**

   * If the event’s pins contradict the run’s authoritative pins → **PIN_MISMATCH** (terminal quarantine).
   * M3 never chooses “which one to trust”; SR’s join surface wins, and mismatch is treated as corruption/drift.

5. **Anchor output**

   * If ready + pins match → emit `AnchoredEvent` containing:

     * run pins
     * `run_facts_view_ref` (the authoritative join surface pointer)
     * anchor basis metadata (so later reconciliation is deterministic)

**Important hard rule:** M3 does **not** enrich missing pins on push events. If required pins are missing, that was already rejected by M2; M3 only validates/anchors.

---

## 3.5 Engine Pull Plan Compiler

**Role:** Build the only legal ingestion plan for M4: “what to pull, from where, under what run context.”

**Inputs**

* `RunIngestStart` from M4 (J4)
* `ValidatedRunFacts` from 3.3

**Outputs**

* `RunIngestPlan` to M4 (J5), containing:

  * `run_context` (pins)
  * `run_facts_view_ref`
  * `traffic_targets[]` with:

    * `engine_output_locator`
    * declared role (must be business traffic)
    * expected gate id / proof refs
    * digest hooks if required
    * framing hint (event_type = output_id)

**Machinery (design-locked)**

* Plan creation is **idempotent**: the same `(scenario_id, run_id)` always yields the same plan (same targets, same refs).
* If validation fails or required parts are missing → emit run-level quarantine request and **do not** emit a plan.

This guarantees that M4 never becomes a discovery engine; it is a pure executor of SR’s declared map.

---

## 3.6 Anchor Failure Classifier (Reason Taxonomy Emitter)

**Role:** Make anchor failures operationally meaningful and consistent across the whole system.

**Inputs**

* Any anchor failure condition encountered in 3.4/3.5

**Outputs**

* A normalized failure reason + retryable flag for J13 quarantine requests

**Design-locked mapping**

* `UNKNOWN_RUN` → retryable
* `RUN_NOT_READY` → retryable
* `JOIN_SURFACE_MISSING/UNREADABLE` → retryable (treated as not-ready)
* `JOIN_SURFACE_INVALID` → terminal for the run ingestion attempt (requires SR fix)
* `PIN_MISMATCH` → terminal
* `TARGET_LIST_INVALID` / `ROLE_NOT_TRAFFIC` / `PROOF_HOOKS_MISSING` → terminal for the run ingestion attempt (requires SR fix)

This is how we keep P4 “hold semantics” clean without inventing a fourth outcome.

---

## 3.7 Cache & Refresh Discipline

**Role:** Ensure M3 stays fast without becoming “eventually correct in a dangerous way.”

**Machinery (design-locked)**

* Cache entries are keyed by `(scenario_id, run_id)` and are immutable once validated for that run.
* Refresh only happens if:

  * the cache is missing, or
  * a prior fetch failed (not-ready), or
  * SR publishes a new join surface version for the same run (rare; if it happens, it is treated as a new authoritative ref and invalidates the old one).

**Hard rule:** M3 never uses a “best effort stale anchor” to admit a run-scoped event. If it cannot confirm READY-backed anchoring, it routes to quarantine/hold.

---

## What M3 guarantees to the rest of IG

* **No run-scoped event reaches admission unless it anchors to a READY run context.**
* **Anchor truth is always backed by a concrete `run_facts_view_ref`.**
* **Pin mismatch is terminal** and never “fixed.”
* **Engine pull is plan-driven**: M4 only gets traffic targets explicitly declared by SR, already structured for downstream proof enforcement.

---

If you want the next node to open, the natural follow-on is **M5 (Proof & Gate Enforcement)**, because M3 hands off “what to ingest” and M5 is what makes “no PASS → no read” true for those declared targets.

---

Understood. **M5 (Proof & Gate Enforcement)** is the IG module that makes this pinned law real:

> **No PASS → no read** (and verification is gate-specific), with **instance proof** required for instance-scoped outputs.

M5 is the only internal machinery allowed to say “this engine output is admissible to read” for legacy engine pull ingestion. Everything else treats M5’s result as authoritative.

Below is **M5 as a white box**: the internal subnetworks inside it and the exact machinery each performs.

---

## M5 internal subnetworks

## 5.1 Gate Map Resolver

**Role:** Determine the authorising gate for a given engine output target.

### Inputs

* `EngineTrafficCandidate` via **J6**: includes `engine_output_locator.output_id`

### Outputs

* `GateBinding = {gate_id, verification_method, dependencies[], authorized_outputs[]}`

### Machinery (design-locked)

* Loads `engine_gates.map.yaml` as the single authority for gate bindings.
* Resolves `output_id → gate_id` by explicit membership in the gate map’s `authorized_outputs`.
* Rejects immediately if:

  * the output_id is not authorized by any gate (no implicit fallback)
  * multiple gates claim the same output_id (map corruption; fail closed)

**Failure → QUARANTINE** with reason `GATE_MAP_MISSING` or `GATE_MAP_AMBIGUOUS`.

---

## 5.2 Gate Evidence Locator

**Role:** Gather the exact proof artifacts needed to verify PASS.

### Inputs

* `EngineTrafficCandidate` includes:

  * `proof_refs` (from `run_facts_view`)
  * `engine_output_locator` (path + identity tokens)

### Outputs

* `GateEvidenceBundle` containing pointers to:

  * `_passed.flag` (or equivalent)
  * verification bundle(s) declared by the gate’s method
  * any required dependency receipts

### Machinery (design-locked)

* M5 does **not** discover proofs by scanning storage.
* It consumes proof refs from the join surface (`run_facts_view`) and resolves them to concrete object refs.
* If required proof refs are missing → fail closed.

**Failure → QUARANTINE** with reason `PASS_MISSING` / `PROOF_REF_MISSING`.

---

## 5.3 Gate Verifier (method-specific)

**Role:** Verify that PASS evidence is true under the gate’s declared verification method.

### Inputs

* `GateBinding.verification_method`
* `GateEvidenceBundle`
* gate dependencies (other gate PASS receipts if required)

### Outputs

* `VerifiedGatePass = {gate_id, pass_evidence_ref, verification_method_used, verified_at_utc}`

### Machinery (design-locked)

M5 implements **exactly** the methods listed in the gate map (no ad hoc hash rules). For each method, it:

* reads the required artifacts (as referenced)
* computes/verifies digests according to that method
* confirms `_passed.flag` exists and is consistent with verification bundle

It also enforces dependency closure:

* if the gate declares upstream dependencies, those must be PASS-verified as well (at least receipt-level), or verification fails closed.

**Failure → QUARANTINE** with reason:

* `GATE_FAIL` (flag missing)
* `VERIFICATION_MISMATCH` (digest/manifest mismatch)
* `DEPENDENCY_PASS_MISSING`

---

## 5.4 Instance Scope Classifier

**Role:** Determine whether instance proof is required (and what “instance” means).

### Inputs

* `engine_output_locator` identity tokens
* engine interface rule: outputs whose scope includes any of:
  `seed`, `scenario_id`, `parameter_hash`, `run_id` require instance proof binding.

### Outputs

* `InstanceScope = {requires_instance_proof: bool, scope_keys[], binding_keys[]}`

### Machinery (design-locked)

* If the target’s identity scope includes any of the instance keys above, set `requires_instance_proof=true`.
* Otherwise, instance proof is not required.

This prevents the classic drift where segment gates are treated as sufficient for run-scoped artifacts.

---

## 5.5 Instance Proof Binder & Verifier

**Role:** Verify the Rails instance-proof receipt bound to **(engine_output_locator + content_digest)**.

### Inputs

* `EngineTrafficCandidate` must carry:

  * `engine_output_locator`
  * `content_digest` (required when instance proof is required)
  * `instance_proof_refs` (from run_facts_view)

### Outputs

* `VerifiedInstanceProof = {proof_ref, bound_locator, bound_digest, verified_at_utc}`

### Machinery (design-locked)

* If `requires_instance_proof=true`:

  * `content_digest` is mandatory; missing digest is an immediate failure.
  * Resolve instance proof receipt ref and verify it binds to:

    * the same locator identity tuple (output_id + path + tokens)
    * the same digest
  * Fail closed on any mismatch.

* If `requires_instance_proof=false`:

  * skip this verifier entirely.

**Failure → QUARANTINE** with reason:

* `DIGEST_REQUIRED_MISSING`
* `INSTANCE_PROOF_MISSING`
* `INSTANCE_PROOF_MISMATCH`

---

## 5.6 Traffic Eligibility Enforcer (belt-and-suspenders)

**Role:** Ensure the candidate is actually allowed to be treated as traffic.

### Inputs

* target metadata from `run_facts_view` (declared role)
* engine output catalogue role taxonomy (`business_traffic` vs others)

### Outputs

* `EligibleTraffic=true` or reject

### Machinery (design-locked)

* If declared role ≠ `business_traffic` → reject.
* If the output_id is known to be non-traffic (truth/audit/telemetry) → reject even if misdeclared.

**Failure → QUARANTINE** with reason `ROLE_NOT_TRAFFIC`.

This prevents SR mistakes from leaking into EB.

---

## 5.7 Proofed Source Assembler (J7 emitter)

**Role:** Package the verified proofs into the single artifact M6 is allowed to read from.

### Inputs

* `VerifiedGatePass`
* `VerifiedInstanceProof` (if required)
* `engine_output_locator`
* run context pins

### Outputs

* `ProofedTrafficSource` via **J7**:

  * `engine_output_locator`
  * `verified_gate` (gate_id + method + evidence ref)
  * `verified_instance_proof` (if required)
  * `content_digest` (if required)
  * `read_authorized=true`
  * framing hint (event_type = output_id; plus PK hints if available)

### Hard invariants

* J7 is emitted **only** when:

  * gate PASS verified under correct method
  * dependency closure satisfied
  * instance proof verified when required
  * role is business_traffic

If any condition fails, **no J7** is emitted; the path goes to M9 via J13.

---

## 5.8 Proof Cache & Replay Discipline

**Role:** Reduce cost without changing semantics.

### Machinery (design-locked)

* Cache verified results keyed by:

  * `(gate_id, manifest_fingerprint)` for segment gate PASS
  * `(engine_output_locator, content_digest)` for instance proofs
* Cache is immutable per run and is safe across retries/resumes.
* Cache never “assumes PASS”; it only stores completed verifications.

---

## What M5 guarantees

* **Nothing is read from engine artifacts unless M5 says it’s admissible.**
* Verification is **gate-specific** and follows the gate map’s declared method.
* Instance-proof binding is enforced for instance-scoped outputs.
* Misclassified targets (non-traffic) are rejected even if SR tries to list them.

---

If you want to continue in the same cadence, the next node to open is **M4 (Engine Pull Orchestrator)**, because M5 assumes candidates are correctly enumerated and M4 is the machinery that turns READY + run_facts_view into those candidates and manages resumable ingestion jobs.

---

Got it. **M4 (Engine Pull Orchestrator)** is the machinery that turns:

**SR READY + `sr/run_facts_view` → a resumable run-ingestion job → per-target candidates → (after proof) row framing → admission**

…and it does this **without discovery**, **without scanning**, **without partial-run emission on preflight failure**, and **idempotently** under repeated READY / restarts.

Below is **M4 as a white box**: the internal subnetworks inside it and exactly what each does.

---

## M4 — Internal subnetworks and machinery

## 4.1 READY Intake & Run Trigger Normalizer

**Role:** Turn control-plane READY into a single run-scoped trigger.

**Machinery (design-locked):**

* Consumes READY events (at-least-once delivery assumed).
* Derives `run_key = (scenario_id, run_id)` from READY.
* Emits **exactly one logical** `RunIngestStart` per run_key to M3 via **J4** (duplicates collapse).

**Hard rule:** repeated READY is **idempotent**; it never spawns parallel competing ingestion jobs.

---

## 4.2 Run Job Registry & State Machine

**Role:** Keep authoritative orchestration state for each run ingestion job (inside IG).

**Job states (authoritative):**

* `NEW` (seen READY, not started)
* `PLANNING` (waiting on M3 plan)
* `PREFLIGHTING` (verifying all traffic targets, no emission allowed)
* `EMITTING` (proof passed; candidates are released for reading/framing)
* `COMPLETED` (all declared targets processed)
* `FAILED_RUN_QUARANTINE` (run-level failure; zero emission)
* `PAUSED` (paused due to backpressure / dependency health)

**Machinery (design-locked):**

* Registry is durable enough to survive restarts (same DB family as IG; no new external surface).
* A job is uniquely keyed by run_key; there is only one active state per run_key.
* State transitions are monotonic and auditable (especially failures).

---

## 4.3 Plan Requester (M3 client)

**Role:** Obtain the only legal ingestion plan from SR join surface authority.

**Machinery:**

* Calls **M3** with `RunIngestStart` (J4) and blocks until it receives **J5** `RunIngestPlan`.
* If M3 cannot produce a valid plan (join surface missing/invalid, target list invalid), M4 marks the run job `FAILED_RUN_QUARANTINE` and routes evidence to M9 (via J13 through the normal path initiated by M3/M4).

**Hard rule:** M4 never invents targets. No plan → no ingest.

---

## 4.4 Target Enumerator

**Role:** Expand the plan into per-target work units.

**Machinery (design-locked):**

* For each `traffic_target` in the plan, produce a `TargetWorkItem`:

  * `{run_key, target_id, engine_output_locator, proof_refs, digest_hooks, framing_hint}`
* Ordering is deterministic (stable sort by `output_id`), so runs behave predictably across environments.

---

## 4.5 Two-Phase Preflight Coordinator (the “zero emission on preflight failure” mechanism)

This is the **most important internal subnetwork in M4**.

**Role:** Guarantee that **if any traffic target fails proof**, the run emits **zero events**.

**Machinery (design-locked):**

* M4 executes **two phases** for every run:

### Phase 1 — PREFLIGHT (verify-only)

* For every target, M4 emits **J6** `EngineTrafficCandidate` with:

  * `phase = PREFLIGHT_ONLY`
* M5 verifies proofs.
* **M5 must not emit J7** for PREFLIGHT_ONLY candidates; it only records pass/fail (and can quarantine failures).

**If any target fails preflight:**

* M4 transitions job → `FAILED_RUN_QUARANTINE`
* M4 does **not** proceed to emission phase for any target
* Result: **zero J7**, thus M6 never reads, thus **zero events emitted**

### Phase 2 — EMIT (release for read/framing)

* Only if **all targets passed** preflight, M4 transitions job → `EMITTING`
* M4 re-emits **J6** candidates with:

  * `phase = EMIT_RELEASE`
* For EMIT_RELEASE candidates, M5 emits **J7 → M6** `ProofedTrafficSource` (read-authorized)

This uses only the joins we already defined (J6/J7) and locks the “no partial emission if preflight fails” rule without inventing new network edges.

---

## 4.6 Candidate Emitter (J6 producer)

**Role:** Produce the canonical `EngineTrafficCandidate` messages for M5.

**Machinery:**

* Emits candidates with:

  * `run_context` (pins + run_facts_view_ref)
  * `engine_output_locator`
  * `expected_gate_id`
  * `proof_refs` + `instance_proof_refs`
  * `content_digest` if required
  * `declared_role` (must be business_traffic)
  * `phase` (PREFLIGHT_ONLY or EMIT_RELEASE)
  * `candidate_id` (stable per run_key + target_id + phase)

**Hard rule:** M4 never emits EMIT_RELEASE until the job is in `EMITTING`.

---

## 4.7 Progress Checkpoint & Resume Manager

**Role:** Make legacy engine pull ingestion resumable across restarts and safe under at-least-once.

**Machinery (design-locked):**

* For each run job, store:

  * `phase` (preflight vs emitting)
  * `targets_completed[]`
  * per-target progress checkpoint (target-specific):

    * either “fully done”, or a resume cursor (e.g., row-group index / last PK tuple processed)
* On restart:

  * job resumes from last checkpoint
  * re-emitted candidates are safe because:

    * preflight is idempotent
    * emission is idempotent due to **M7 dedupe** (no double-admit)

**Hard rule:** resume never turns into “scan latest”; it resumes only within the declared locators in the plan.

---

## 4.8 Concurrency, Fairness, and Backpressure Interface

**Role:** Prevent legacy engine pull from starving the ingest boundary or overwhelming EB/DB/evidence stores.

**Machinery (design-locked):**

* Concurrency limits:

  * max concurrent runs in PREFLIGHT
  * max concurrent runs in EMITTING
  * max concurrent targets per run
* Fair scheduling:

  * round-robin across runs to avoid one huge run blocking others
* Backpressure reactions:

  * if M10 signals `PAUSE/THROTTLE` (via the already-pinned control loop), M4 transitions jobs to `PAUSED` and stops emitting new candidates until reopened.

**Hard rule:** when paused, M4 does not “continue reading anyway.” It preserves correctness over throughput.

---

## 4.9 Run-Level Failure Handler (Run Quarantine Initiator)

**Role:** Convert systemic failures into a run-level quarantine outcome that is visible and auditable.

**Machinery (design-locked):**

* If any of these occur, the run is failed as `FAILED_RUN_QUARANTINE` (zero emission):

  * join surface invalid/unreadable
  * any target fails preflight proof verification
  * plan inconsistencies (non-traffic listed as traffic, missing digest hooks where required)
* Produces a run-level quarantine bundle (via the standard quarantine path) containing:

  * run pins + run_facts_view_ref
  * target list and which target failed
  * proof failure diagnostics from M5 (refs + mismatch details)

**Hard rule:** run-level failures are explicit and never hidden inside logs.

---

## 4.10 Telemetry Producer (M4’s own observability)

**Role:** Provide run-ingestion-specific signals to ops without changing truth ownership.

**Machinery:**

* Emits run job metrics:

  * runs queued/running/paused
  * preflight pass/fail rates
  * time in each job phase
  * per-target throughput and lag
* Correlates telemetry by run_key and policy/gate-map revisions (so environment ladder debugging is straightforward).

---

# What M4 guarantees to the IG network

* **Pull model is enforced**: ingestion starts from READY and run_facts_view only.
* **No discovery**: it never scans buckets or infers runs/targets.
* **No partial-run emission on preflight failure**: if any target fails proof, the run emits **zero events**.
* **Resumable and idempotent**: repeated READY and restarts do not create double ingestion or double admits.
* **Engine pull load is controlled**: concurrency/backpressure are first-class.

If you want to continue, the next node to illuminate is **M6 (Traffic Framer & Canonicalizer)**, because once M4+M5 have produced proofed sources, M6 is the machine that turns engine rows into canonical envelope events (including deterministic `event_id` minting and the `event_type = output_id` rule).

---

Understood. **M6 (Traffic Framer & Canonicalizer)** is the internal IG module that produces the *final* canonical envelope events that M7 can safely treat as admission candidates.

It has one job: **given an anchored push event or a proofed engine traffic source, produce a canonical envelope event whose identity is stable and whose meaning time is correct**, without inventing semantics.

Below is **M6 as a white box**: the internal subnetworks inside it and the machinery each performs.

---

## M6 — Internal subnetworks and machinery

## 6.1 Input Harmonizer (Push vs Engine Pull)

**Role:** Normalize the two upstream input types into a single internal framing workflow.

### Inputs

* From **J3 (M3→M6)**: `AnchoredEvent` (push ingest)
* From **J7 (M5→M6)**: `ProofedTrafficSource` (legacy engine pull)

### Outputs

* `FrameWorkItem` with:

  * `mode = PUSH | ENGINE_PULL`
  * `run_context` (present iff run-scoped; always present for legacy engine pull)
  * `source_pointer` (raw input ref for push; engine locator + proof refs for pull)
  * `canonical_envelope_base` (push carries it; legacy engine pull starts empty except pins)

**Hard rule:** both modes must converge to the same downstream output shape.

---

## 6.2 Canonical Envelope Finalizer (Push mode)

**Role:** Ensure push events are “final” and safe before admission.

### Machinery (design-locked)

* The envelope that arrives from M3 is already validated for required fields by M2; M6 does not reinterpret it.
* M6 performs only **final sanity normalization**:

  * ensure `ts_utc` parses as UTC instant
  * ensure required fields are present and normalized types
  * ensure `manifest_fingerprint` is exactly the anchored manifest (if run-scoped, it must match run_context)
* It attaches provenance pointers (for audit) into a reserved payload sub-object:

  * `ingest_source = {source_kind, raw_input_ref}`

**Hard rule:** M6 never edits payload meaning; it only attaches provenance pointers.

---

## 6.3 Engine Row Reader (Engine Pull mode)

**Role:** Read the declared engine traffic dataset and yield rows in deterministic order.

### Inputs

* `ProofedTrafficSource` includes:

  * `engine_output_locator` (resolved path + tokens)
  * verified PASS + instance proof refs
  * framing hint `event_type = output_id`

### Machinery (design-locked)

* Reads the dataset **only via the locator path** (no discovery).
* Uses a deterministic read order:

  * rows are yielded ordered by the dataset’s declared primary key (PK) from the catalogue.
  * If the physical file order differs, M6 sorts logically by PK (at least within chunk windows).
* Emits a `RowWorkItem`:

  * `{output_id, locator, row_pk_tuple, row_data}`

This guarantees stable event_id minting and stable replay behavior across environments.

---

## 6.4 Event Type Resolver

**Role:** Produce a deterministic `event_type` without drift.

### Machinery (design-locked)

* **Engine pull:** `event_type = output_id` (exact string, no translation table in v0).
* **Push ingest:** `event_type` is whatever the producer declared (already validated by M2 policy allowlist).

This is pinned specifically to prevent hidden naming drift when multiple teams add traffic streams.

---

## 6.5 Domain Time Extractor (`ts_utc`)

**Role:** Populate the required envelope field `ts_utc` as the domain/meaning time.

### Machinery (design-locked)

* **Push ingest:** uses the `ts_utc` already present in the envelope (validated earlier).
* **Engine pull:** extracts `ts_utc` from the row:

  * preferred: a column literally named `ts_utc` if present (common in your engine traffic surfaces)
  * otherwise: a per-output configured “time column” mapping stored in IG policy (not in code logic)
* If time cannot be extracted deterministically → **FRAME_FAIL quarantine** (row-level).

**Hard rule:** M6 never replaces domain time with ingest time. Ingest time is only for receipts/telemetry.

---

## 6.6 Event ID Resolver (stable identity engine)

**Role:** Produce a stable `event_id` for every emitted event.

### Machinery (design-locked)

#### Push ingest

* If producer supplied `event_id`, it is preserved (already validated by M2).
* If missing/invalid (should be rare): M6 does **not** mint in push mode; it routes to quarantine (missing event_id is a boundary violation).

#### Engine pull

M6 mints `event_id` deterministically when the row doesn’t carry one:

**Authoritative minting recipe:**
`event_id = H( "engine", output_id, row_pk_tuple, manifest_fingerprint, parameter_hash, scenario_id, seed )`

* `row_pk_tuple` is the dataset’s declared primary key tuple (logical PK, not file row index).
* **run_id is not included** (run partitions attempts; it must not redefine world row identity).
* The hash output is encoded as a UUID-like or digest-like string that satisfies the envelope schema’s `event_id` type.

If the declared PK fields are missing from the row → **FRAME_FAIL quarantine** (row-level). No fallback to “row number”.

This makes legacy engine pull idempotent across retries and resumptions.

---

## 6.7 Pin Stamping & Consistency Enforcer

**Role:** Ensure run/world join pins are present and consistent.

### Machinery (design-locked)

* **Engine pull:** stamps pins from run_context onto every emitted envelope:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`, `seed`
* **Push ingest:** if run-scoped, pins must already be present and must match run_context; mismatch is a terminal quarantine reason (but the mismatch decision is made in M3—M6 re-checks only as an integrity guard).

This guarantees downstream can always join events to the correct run/world without guessing.

---

## 6.8 Payload Builder (by-value + by-ref provenance)

**Role:** Provide payload that is usable downstream while preserving the by-ref origin story.

### Machinery (design-locked)

* **Engine pull payload** includes:

  1. `payload.data` = selected row fields needed downstream (not necessarily the entire row; selection is policy-driven)
  2. `payload.source` = immutable by-ref pointers:

     * `engine_output_locator`
     * `row_pk_tuple`
     * `content_digest` (if present/required)
     * proof refs (gate receipt ref, instance proof ref)
* **Push ingest payload** is preserved; M6 only adds `payload.ingest_source` pointer metadata.

**Hard rule:** M6 never fabricates business meaning; it only packages row fields and provenance pointers.

---

## 6.9 Partition Hint Deriver

**Role:** Provide the inputs needed for deterministic partition_key stamping downstream (M7/M8 pipeline).

### Machinery (design-locked)

* For each event, M6 derives `partition_hint_inputs` based on policy:

  * typically a “stream entity” id such as `merchant_id` or `flow_id`
  * always combined with run_context so different runs don’t collide unintentionally
* M6 does **not** choose the final partition_key; it provides the determinism inputs. The final stamp is done by the admission/commit spine.

This keeps routing deterministic without embedding bus logic into framing.

---

## 6.10 Frame Integrity Guard & Row-Level Quarantine Emitter

**Role:** Detect framing violations and route to quarantine without breaking the run.

### Machinery (design-locked)

For any row/event, if any required envelope field cannot be produced deterministically:

* emit **J13 → M9** with reason `FRAME_FAIL` and context:

  * engine locator + row_pk_tuple (if available)
  * diagnostics: missing time column / missing PK fields / schema mismatch

Row-level quarantines do not abort the run job (the run continues unless preflight failed earlier).

---

## What M6 guarantees

* Every event handed to M7 via **J8** is a valid canonical envelope event with:

  * required fields present
  * correct domain time `ts_utc`
  * stable `event_id` (minted deterministically for legacy engine pull)
  * consistent run/world pins stamped for legacy engine pull
* Engine pull naming is drift-proof: **`event_type = output_id`**
* Any non-deterministic or ambiguous framing becomes a **row-level quarantine**, not a silent fix.

---

Next in the planned order would be **M2 (Envelope & Policy Gate)**, because M6 assumes upstream policy decisions exist (required pins, payload selection, time column mapping, partition strategy id).

---

Understood — **M2 (Envelope & Policy Gate)** is the internal IG module that turns “an intake attempt” into a **policy-bound, envelope-valid event candidate**, or rejects it into quarantine with explicit reasons. It’s where we enforce “don’t guess”, “don’t silently fix”, and “required pins by event type”.

Below is **M2 as a white box**: the internal subnetworks inside it and the exact machinery each performs.

---

## M2 — Internal subnetworks and machinery

## 2.1 Policy Profile Loader & Active Revision Pointer

**Role:** Load the currently active IG policy revision and expose it as read-only inputs to all checks.

### Machinery (design-locked)

* Maintains a single **active policy pointer** (`policy_rev`) (activated atomically via J18, but M2 owns the “use this rev” behavior).
* Refuses to operate in a half-loaded state:

  * If active policy revision cannot be loaded/validated, M2 fails closed (ingest attempts are rejected as retryable; no silent weakening).

### Outputs

* `ActivePolicy = {policy_rev, rulesets}`

---

## 2.2 Producer/Event Allowlist Gate

**Role:** Decide whether a producer is permitted to emit a given `event_type` (and under which scope).

### Inputs

* `IntakeItem.producer_principal` (from M1 via J1)
* `envelope_candidate.event_type` (if parse succeeded)

### Machinery (design-locked)

* Looks up `(producer_principal, event_type)` in the allowlist table.
* If not present → immediate rejection (`POLICY_DENY`).
* If present, also determines:

  * whether this event type is **run-scoped** or **non-run-scoped**
  * whether payload schema validation is required
  * which partition strategy profile to use later

**Hard rule:** no event type is “implicitly allowed”.

---

## 2.3 Envelope Parser & Canonical Field Normalizer

**Role:** Parse the incoming structure into the canonical envelope shape and normalize required fields.

### Inputs

* `IntakeItem.envelope_candidate` + `raw_input_ref`

### Machinery (design-locked)

* Parses JSON/object into an internal envelope struct.
* Normalizes and validates required fields:

  * `event_id` (must be present and format-valid)
  * `event_type` (must be present)
  * `ts_utc` (must parse to a UTC instant)
  * `manifest_fingerprint` (must be present)
* Preserves `payload` as opaque bytes/object; does not interpret.
* Preserves optional correlation fields (trace_id/span_id/parent_event_id) if present.

**Hard rule:** If any required envelope field is missing/invalid → reject (`ENVELOPE_INVALID`). M2 never “fills” these in push ingest.

---

## 2.4 Producer Identity Consistency Check

**Role:** Prevent spoofing/confusion between transport identity and claimed producer identity.

### Machinery (design-locked)

* If the envelope includes a `producer` field:

  * it must match `producer_principal` (or a policy-approved alias set for that principal).
* If mismatch → reject (`PRODUCER_MISMATCH`).

This makes internal producers (DF/AL/Case) unable to masquerade as each other.

---

## 2.5 Schema Mode Resolver (payload validation posture)

**Role:** Decide how strictly payload should be validated (envelope is always strict).

### Machinery (design-locked)

For each `(producer,event_type)` policy record, resolve:

* `payload_schema_mode` ∈ {`NONE`, `STRUCTURAL`, `STRICT`}
* expected `schema_version` policy:

  * `REQUIRED`, `OPTIONAL`, or `DISALLOWED`

Rules:

* If schema_version is required but missing → reject (`SCHEMA_VERSION_MISSING`)
* If schema_version is present but unknown (no schema registered for that version) and mode ≠ NONE → reject (`SCHEMA_UNKNOWN`)
* If mode is STRICT/STRUCTURAL:

  * validate payload against the registered schema at `(event_type, schema_version)`

**Hard rule:** M2 never guesses schema versions and never accepts unknown versions when validation is required.

---

## 2.6 Pin Classifier & Required Pins Enforcer

**Role:** Decide what identity pins must exist for this event type and enforce them.

### Machinery (design-locked)

Policy assigns each event type one of:

* **Non-run-scoped**: does not require run pins (still requires manifest_fingerprint by envelope law)
* **Run-scoped**: requires run/world pins

For run-scoped events, required pins are:

* `scenario_id`
* `run_id`
* `parameter_hash`
* (and for traffic classes) `seed`
* plus `manifest_fingerprint` (already required by envelope)

Rules:

* Missing any required pin → reject (`PINS_MISSING`)
* If pins are present but malformed → reject (`PINS_INVALID`)

**Hard rule:** M2 does not “enrich” missing pins. Missing pins are a boundary violation.

---

## 2.7 Event-Type Classifier (traffic vs non-traffic inside IG)

**Role:** Decide whether the event is “traffic-class” from IG’s perspective (affects required seed and later partition strategy).

### Machinery (design-locked)

Policy marks event types into coarse classes:

* `BUSINESS_TRAFFIC_CLASS` (requires seed; must be joinable)
* `CONTROL/AUDIT_CLASS` (still admitted to EB if allowed, but different partition strategy)
* `ACTION_INTENT_CLASS`, `ACTION_OUTCOME_CLASS` (special semantics for downstream but still just events to IG)

This classifier does **not** alter payload meaning; it only constrains required pins and routing profiles.

---

## 2.8 Partition Strategy Selector (routing profile decision)

**Role:** Choose the deterministic routing profile that will later produce a partition_key.

### Machinery (design-locked)

Policy maps `(producer,event_type,class)` → `partitioning_profile_id` with:

* which payload/pin field is the partition entity key (e.g., merchant_id/flow_id/account_id)
* fallback behavior if missing (reject vs use event_id)

**Hard rule:** M2 chooses the routing profile; it does not compute the final partition key.

---

## 2.9 PolicyBoundEvent Assembler (J2 producer)

**Role:** Produce the exact object M3 is allowed to anchor.

### Output (to J2)

`PolicyBoundEvent` contains:

* `canonical_envelope` (validated + normalized required fields)
* `producer_principal` (+ declared producer if present)
* `policy_rev` (stamped)
* `event_type`, optional `schema_version`
* `anchor_class` = run-scoped / non-run-scoped
* `pin_set` (present pins)
* `payload_validation_mode` result
* `partitioning_profile_id`
* provenance: `raw_input_ref` + intake metadata pointer

**Hard rule:** If M2 emits J2, then:

* envelope is valid,
* policy allows it,
* required pins for its anchor_class are present,
* schema posture (if required) is satisfied.

---

## 2.10 Rejection Router (to quarantine)

**Role:** Convert any failure into an explicit quarantine request with evidence pointers.

### Machinery (design-locked)

On any failure, M2 emits **J13 → M9** with:

* `reason_code` from a canonical taxonomy:

  * `ENVELOPE_INVALID`
  * `PRODUCER_MISMATCH`
  * `POLICY_DENY`
  * `SCHEMA_VERSION_MISSING`
  * `SCHEMA_UNKNOWN`
  * `SCHEMA_FAIL`
  * `PINS_MISSING`
  * `PINS_INVALID`
* `raw_input_ref` (always)
* `diagnostics` (structured error detail)
* `policy_rev` (the policy that rejected it)

No failure is “returned to caller silently”; it becomes an auditable quarantine outcome (or the ingest attempt fails retryably if quarantine storage is unavailable).

---

## What M2 guarantees

* Only policy-allowed event types proceed.
* Only envelope-valid events proceed.
* Required pins (run/world joinability) are enforced deterministically.
* Payload schema validation is policy-driven and never guessed.
* Any rejection produces explicit quarantine evidence and a receipt trail via M9/M7.

---

Got it — **M1 (Producer Intake Gateway)** is the **front door** of IG. Its job is not “validation” or “joinability” or “dedupe.” Its job is to **accept input safely**, bind **producer identity**, preserve **exact raw evidence**, and emit a normalized `IntakeItem` into the internal network (J1). Everything else flows from that.

Below is **M1 as a white box**: its internal subnetworks and the exact machinery each performs.

---

## M1 — Internal subnetworks and machinery

## 1.1 Ingress Multiplexer

**Role:** Provide the entrypoints IG supports without changing semantics.

### Entry modes (both can be enabled)

* **Bus Ingress**: consumes producer traffic from a configured ingress topic/stream.
* **HTTP Ingress**: accepts producer submissions over HTTPS.

**Machinery (design-locked):**

* Both modes produce the same downstream object: `IntakeItem`.
* M1 does not interpret event types differently by ingress mode; policy later decides.

---

## 1.2 Transport Authenticator (AuthN)

**Role:** Establish a strong, unforgeable producer principal at the boundary.

**Machinery (design-locked):**

* For every request/message, derive `producer_principal` from transport auth:

  * HTTP: mTLS identity or signed token identity
  * Bus: authenticated consumer group + message auth headers / producer credentials (platform-dependent)
* If identity cannot be established → immediate rejection into quarantine with `AUTHN_FAILED`.

**Hard rule:** no unauthenticated traffic becomes an `IntakeItem`.

---

## 1.3 Producer Principal Mapper (Identity Canonicalizer)

**Role:** Convert transport identity into a canonical principal name used everywhere inside IG.

**Machinery:**

* Maps raw identity to a normalized principal:

  * e.g., `svc:decision_fabric`, `svc:actions_layer`, `svc:case_workbench`, `ext:partner_X`
* Applies alias rules (allowed aliases only; prevents spoofing).

This is what later allows M2 to do strict allowlisting and “producer mismatch” checks safely.

---

## 1.4 Raw Input Capturer (Evidence Preservation Engine)

**Role:** Preserve the exact bytes received *before* any parsing/validation so quarantine is always evidence-backed.

**Machinery (design-locked):**

* For each intake attempt, produce a `raw_input_ref` that points to the immutable original bytes:

  * In prod/dev: write to object store under a staging prefix (e.g., `ig/intake_raw/...`)
  * In local: same concept (filesystem/minio)
* Record minimal metadata:

  * `received_at_utc`
  * ingress mode
  * source address / topic/partition/offset
  * content length and checksum

**Hard rules:**

* No raw ref → no continuation. If M1 cannot persist raw evidence, it **does not** pass the item downstream.
* Raw evidence is immutable and addressed by `raw_input_ref`.

This is why “no silent drop” remains true even under parsing failures.

---

## 1.5 Envelope Parser (Best-effort)

**Role:** Extract a structured envelope candidate **only as a convenience**, never as authority.

**Machinery (design-locked):**

* Attempts to parse the raw bytes into a JSON/object.
* If parse succeeds:

  * extract `event_type` early (for telemetry only)
  * extract declared `producer` field if present (for later mismatch checks)
  * store `envelope_candidate` (untrusted)
* If parse fails:

  * still emits an `IntakeItem` with `envelope_candidate = null`
  * parsing failure becomes a downstream rejection in M2 (`ENVELOPE_INVALID`) with the preserved `raw_input_ref`.

**Hard rule:** parsing success does not imply validity; only M2 validates.

---

## 1.6 Intake Attempt ID & Correlation Stamping

**Role:** Make every ingestion attempt traceable across retries and across modules.

**Machinery (design-locked):**

* Assign `intake_id` (globally unique per attempt).
* Attach correlation fields if present:

  * trace_id/span_id from headers (HTTP) or message headers (bus)
* Attach run hints if present in raw payload (only as hints; M2/M3 validate).

This enables later ops queries and evidence linking even when the event is quarantined early.

---

## 1.7 Ingress Acknowledger / Backpressure Adapter

**Role:** Correctly interact with upstream delivery semantics without lying.

### HTTP ingress behavior

* If M1 cannot persist raw evidence → respond with retryable failure (no receipt implied).
* If it can persist raw evidence → accept the request for processing and return either:

  * an immediate receipt if the pipeline is synchronous in that deployment, or
  * an accepted response with a lookup key (`intake_id`) if asynchronous.

### Bus ingress behavior

* M1 **does not acknowledge** the bus message until IG can guarantee it will result in a durable outcome downstream.
* At minimum, M1 requires:

  * raw input persisted (so evidence exists)
  * and the item successfully enqueued to the internal pipeline
* If IG is paused/throttled via **J19** (from M10), M1 respects it:

  * in PAUSE: stops consuming or does not ack messages, forcing redelivery later
  * in THROTTLE: reduces consumption rate

**Hard rule:** M1 never acks a bus message if it cannot ensure the attempt will end in a durable outcome path.

---

## 1.8 Intake Normalizer (J1 producer)

**Role:** Emit the canonical `IntakeItem` into the IG network.

### Output via **J1** to M2

`IntakeItem` contains:

* `intake_id`
* `source_kind = push_http | push_bus`
* `producer_principal`
* `transport_meta` (headers, topic/partition/offset, remote addr, received_at)
* `raw_input_ref`
* `envelope_candidate` (nullable)
* `trace_context` (if available)

**Hard invariant of J1:** if M1 emits an `IntakeItem`, it always includes `producer_principal` and `raw_input_ref`.

---

## 1.9 Abuse Guard (DoS / payload limits)

**Role:** Keep IG safe at the boundary without breaking semantic rules.

**Machinery (design-locked):**

* Enforces hard size limits and rate limits at ingress:

  * oversized payloads are rejected into quarantine with `PAYLOAD_TOO_LARGE` (or rejected pre-quarantine if even raw capture is unsafe, with explicit retry/deny).
* Applies basic content-type validation for HTTP.
* For bus ingress, applies consumer-side limits and pauses consumption under pressure (via J19).

**Hard rule:** protection never becomes silent dropping; outcomes remain explicit and traceable.

---

## What M1 guarantees

* Every intake attempt is attributed to a canonical `producer_principal`.
* The exact original bytes are preserved as `raw_input_ref` before any parsing/validation.
* Ingress semantics respect backpressure and at-least-once delivery (no lying acknowledgments).
* A normalized `IntakeItem` is emitted into the IG network via J1, or the attempt is rejected with explicit evidence.

---

If you want to finish the “inner node illumination set,” the remaining node is **M10 (Ops Surfaces)**, which is where receipt lookup, quarantine triage, profile activation, and throttling decisions live.

---

Understood — **M10 (Ops Surfaces)** is the “operability membrane” of IG. It does **not** create truth; it exposes and governs truth that lives in **M7 (ledger)** and **M9 (evidence)**, and it is the place where:

* “what happened to my event?” becomes answerable (E1/E2)
* throttling/pausing becomes explicit (J19)
* profile activation becomes atomic and attributable (J18)
* telemetry is aggregated in a way DL can consume (without hidden coupling)

Below is **M10 as a white box**: its internal subnetworks and the exact machinery each performs.

---

## M10 — Internal subnetworks and machinery

## 10.1 Receipt Index View & Query API (E1 surface)

**Role:** Provide deterministic “what happened?” answers without scanning EB.

### Inputs

* `ReceiptPointer` feed from **J11 (M7→M10)**
* Direct lookup queries from operators/producers
* Direct reads to M7 via **J16 (M10→M7)** when needed

### Machinery (design-locked)

* Maintains a materialized read model keyed by:

  * `receipt_id`
  * `dedupe_key`
  * `(event_id, producer_principal, event_type)`
  * run pins (scenario_id/run_id/manifest_fingerprint/parameter_hash/seed)
* The read model is a cache/view; **M7 remains authoritative**.
* For any query, M10 returns:

  * outcome: `ADMITTED | DUPLICATE | QUARANTINED`
  * primary pointer:

    * admitted → `eb_ref(topic,partition,offset)`
    * quarantined → `quarantine_ref`
    * duplicate → `original_receipt_ref` (and/or original `eb_ref/quarantine_ref`)
  * reason codes for quarantines
  * policy revision in force (`policy_rev`)
* If the cache is stale, it falls back to M7 via J16.

**Hard rule:** no scan of EB is ever used to answer E1.

---

## 10.2 Quarantine Triage Surface (E2 surface)

**Role:** Let authorized users/tools inspect quarantine evidence and decide remediation.

### Inputs

* `EvidencePointer` feed from **J15 (M9→M10)**
* Triage fetch/actions issued via **J17 (M10→M9)**

### Machinery (design-locked)

* Provides listing and filtering:

  * by run pins, producer, event_type, reason_code, retryable_flag
* Fetches immutable evidence bundles by `quarantine_ref` (via M9).
* Renders a “triage view” containing:

  * reason codes + retryable flag
  * diagnostics (schema errors, pin mismatch diffs, proof failures, commit deadletters)
  * raw input pointer (`raw_input_ref`)
  * correlation ids (`intake_id`, batch_id if any)

**Hard rule:** evidence is immutable; triage actions never edit evidence.

---

## 10.3 Remediation Orchestrator (re-ingest launcher)

**Role:** Turn triage decisions into safe re-ingest attempts.

### Inputs

* Operator/tool remediation intent (from triage)
* Optional “auto-redrive policy” for retryable holds

### Outputs

* `ReingestSubmission` via **J20 (M10/M9→M1)**:

  * `{corrected_event, supersedes_ref, remediator_principal, optional parent_event_id}`

### Machinery (design-locked)

* Enforces that every remediation attempt includes:

  * `supersedes_ref` pointing to the quarantine receipt/evidence
  * authenticated `remediator_principal`
* Submits remediation through the **same intake path** as any producer (no bypass).
* Optionally supports “auto-redrive” for retryable hold quarantines when READY becomes true:

  * generates a re-ingest submission that supersedes the hold record
  * still flows through M1→M2→… for full enforcement

**Hard rule:** remediation never mutates old receipts/evidence; it only produces new attempts.

---

## 10.4 Telemetry Aggregator & Exporter (G1 surface)

**Role:** Aggregate IG’s operational signals into metrics/logs/traces that are meaningful across the environment ladder.

### Inputs

* `ReceiptPointer` (J11): outcome rates, reason codes
* `CommitTelemetry` (J12): append latency, retry counts, backlog
* `EvidencePointer` (J15): quarantine queue depth, retryable vs terminal
* Direct module health pings (M1/M7/M8/M9) for dependency health

### Machinery (design-locked)

Produces golden signals:

* admission rate (admit/duplicate/quarantine) by producer/event_type
* quarantine reason distribution + retryable/terminal split
* EB append latency + retry rates + commit deadletters
* PENDING age histogram (how long admissions are waiting on commit)
* legacy engine pull job lag (if enabled, run-level)

Correlation propagation:

* tags metrics with run pins where available
* includes trace_id/span_id when present (for log/trace linking)
* stamps policy/gate-map/commit-policy revisions in telemetry

**Hard rule:** telemetry never becomes truth; it explains truth.

---

## 10.5 Health & Readiness Oracle

**Role:** Decide whether IG can safely accept more work without violating durability/evidence guarantees.

### Inputs

* dependency health:

  * M7 ledger write health
  * M8 EB connectivity and ack latency
  * M9 evidence store write health
* internal saturation:

  * queue depth, in-flight commits, oldest PENDING age

### Machinery (design-locked)

Computes `IG_HealthState`:

* `GREEN`: can accept work normally
* `AMBER`: accept with throttling
* `RED`: pause intake (to avoid lying receipts or silent loss)

This state is used internally to drive J19 (below) and exposed as a health endpoint for orchestration.

---

## 10.6 Ingress Control Emitter (J19 controller)

**Role:** Apply explicit throttling/pausing to ingress when correctness is at risk.

### Output

* `IngressControl` via **J19 (M10→M1)**:

  * `OPEN | THROTTLE | PAUSE`
  * rate limits / max inflight
  * reason code (`EB_UNHEALTHY`, `LEDGER_UNHEALTHY`, `EVIDENCE_STORE_UNHEALTHY`, `OVERLOAD`)

### Machinery (design-locked)

* If ledger cannot reserve PENDING safely → `PAUSE`
* If evidence store cannot write quarantines safely → `PAUSE`
* If EB ack latency/backlog breaches corridor → `THROTTLE` then `PAUSE` if worsening
* In PAUSE:

  * HTTP fails fast (retryable)
  * bus ingestion stops acking/consuming

**Hard rule:** better to pause than to accept and fail silently.

---

## 10.7 Profile Activation Controller (J18 orchestrator)

**Role:** Apply environment ladder knobs atomically and make them attributable.

### Inputs

* Profile artifacts (policy rev, schema catalog rev, gate map rev, commit policy rev, thresholds rev)

### Outputs

* Active pointers pushed to:

  * M2 (policy + schema)
  * M5 (gate map)
  * M8 (commit policy)
  * M10 (thresholds)

### Machinery (design-locked)

* Uses a single **ActiveProfilePointer** that references a consistent set of artifact versions.
* Activation is **all-or-nothing**:

  * validate each artifact is present and passes basic checks
  * only then flip the active pointer
* Ensures every receipt/telemetry record is stamped with:

  * at least `policy_rev`
  * and, for legacy engine pull, `gate_map_rev`
  * and commit policy revision for commit-related telemetry

**Hard rule:** no half-applied behavior across modules.

---

## 10.8 Access Control & Audit Guard (Ops boundary)

**Role:** Ensure ops surfaces don’t become a privilege escalation vector.

### Machinery (design-locked)

* Enforces authz for:

  * receipt lookup (broadly allowed, but may redact)
  * quarantine evidence access (restricted; sensitive)
  * remediation submission (restricted; highest privilege)
  * profile activation (restricted; change-controlled)
* Emits audit logs of ops actions (triage views, remediation submissions, profile activations).

---

## What M10 guarantees

* E1/E2 are always answerable from **receipts + evidence** (never EB scans).
* Quarantines can be triaged and remediated safely with append-only supersedes chains.
* IG can protect correctness under pressure via explicit throttle/pause.
* Profile changes are atomic and attributable (environment ladder safe).
* Observability signals are strong enough for DL corridor checks without hidden coupling.

---

