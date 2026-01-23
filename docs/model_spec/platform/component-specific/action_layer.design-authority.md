# Action Layer Design Authority

This file is a rough collection of design or brainstorm notes for the action layer. It views the whole platform as a network and expands open the action layer's position in this network and illuminates it.

---

Alright—back on **Actions Layer (AL)**, and we’ll do this exactly the way you want: **treat AL’s inner network as opaque**, and pin a **clear, drift-resistant outer role** (edges/handshakes/guarantees) inside the already-pinned platform network. Everything below is **designer-authoritative for this brainstorm** unless it violates a platform pin (it won’t). 

---

## 1) AL’s job in the platform graph (what AL *is*, externally)

### AL is the platform’s **only side-effect executor**

* DF (and humans) can only **request** actions.
* Only AL can **execute** them, and AL is the **system-of-record for outcomes + attempt history**. 

### AL’s single sentence “outer truth”

**Consume ActionIntents, authorize them, execute them effectively-once, and publish immutable ActionOutcomes that are joinable to decisions and auditable under replay.** 

This is not “nice to have”—it’s the platform’s safety choke point (overlay A3) and replay-safety rail (R7). 

---

## 2) Where AL sits (edges that are pinned, and must not drift)

### AL does not get special transport privileges

ActionIntents and ActionOutcomes are **real traffic**, so they flow through **IG → EB**, same as everything else. AL does **not** bypass the trust boundary. 

**Pinned transport shape for “traffic”** is the **Canonical Event Envelope**.

So the outer routing is:

```
DF / Case / Ops  ->  IG  ->  EB  ->  AL
AL               ->  IG  ->  EB  ->  DLA (+ Case timelines, projections, etc.)
```

---

## 3) The AL “outer interface” (inputs, outputs, and who they serve)

### 3.1 Inbound to AL: **ActionIntent events**

**AL consumes ActionIntent as an enveloped event**, delivered at-least-once from EB, already admitted by IG.

**Sources of ActionIntent (pinned posture):**

1. **Decision Fabric (DF)** — automated actions that follow from a decision. 
2. **Case Workbench / human workflow** — manual actions (higher privilege), but *not a bypass*. 
3. **Ops / Run-Operate** — operational actions (rare; still must be attributable + authorized). 

> Designer pin: There is **one** concept of “ActionIntent” regardless of source. The only difference is `origin` + actor principal + required authorization.

### 3.2 Outbound from AL: **ActionOutcome events**

AL’s public output is **ActionOutcome history**: immutable outcomes per intent, with attempt history, join keys, and attribution. 

**Primary consumers of ActionOutcome:**

* **DLA** (flight recorder closure: intent vs executed / denied / failed). 
* **Case Workbench** (timelines, evidence pointers, “what actually happened”). 
* **Observability/Governance** (SLOs, retries, executor health, policy enforcement evidence). 
* Potentially **IEG/OFP** as ordinary “admitted events” (if you want actions to update state). 

---

## 4) What AL *expects* at its boundary (so the inner network can be designed correctly)

### 4.1 Every ActionIntent is a CanonicalEventEnvelope

At minimum, AL can rely on envelope required fields:

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` 
  …and for run/world joinability, ActionIntents should carry **ContextPins** (`manifest_fingerprint`, `parameter_hash`, `scenario_id`, `run_id`) as envelope fields (not buried).

### 4.2 ActionIntent must carry **two different “keys”**

Designer pin (important distinction):

* `event_id` (envelope) is for **IG/EB idempotency/dedupe**.
* `idempotency_key` (payload) is for **AL semantic effectively-once execution** (uniqueness scope: `(ContextPins, idempotency_key)`). 

AL does **not** treat envelope `event_id` as the semantic action key. The semantic action key is pinned explicitly as `(ContextPins, idempotency_key)`. 

### 4.3 ActionIntent must be attributable (authz cannot be a vibe)

Each ActionIntent must include (conceptually) these “who/why” facts:

* **actor_principal** (who is requesting the action)
* **origin** (DF automated vs Case/Human vs Ops)
* **reason / rationale ref** (free text is fine; better is a pointer/ref to evidence like decision_id or case_id)

Because AL is the choke point for side effects and must enforce allowlists by `(actor_principal, action_type, scope)`—and denied actions must still produce a joinable outcome. 

---

## 5) What AL *promises* to the rest of the platform (non-negotiable behaviour)

These are the “outer guarantees” that define AL and constrain its inner design.

### 5.1 **Authorization is enforced at AL**

Even if DF or a UI emits an ActionIntent, AL independently checks:

* allowed action types
* allowed scope (ContextPins + target scope)
* policy revision used must be **recorded** in the outcome

If unauthorized:

* **no execution occurs**
* AL emits an **ActionOutcome with decision = DENIED** (immutable, idempotent, joinable). 

> Designer pin: “manual action” is just a higher-privilege intent, never a bypass. 

### 5.2 **Effectively-once execution under at-least-once delivery**

AL enforces:

* uniqueness scope: **`(ContextPins, idempotency_key)`**
* duplicates must never re-execute; they **re-emit the canonical outcome**. 

This implies AL must have a **durable idempotency ledger** (internal), surviving restarts, otherwise replay would re-execute side effects (platform-breaking). (That durability requirement is an outer guarantee even though the storage is “inner design”.) 

### 5.3 **Immutable outcomes + append-only attempt history**

* Every *real attempt* produces one outcome record.
* Outcomes are immutable once emitted.
* Duplicate intents re-emit the already-known canonical outcome payload (byte-identical). 

### 5.4 **No silent drops**

AL must never “eat” an intent. It produces one of:

* **EXECUTED**
* **DENIED**
* **FAILED** (with stable error category + retry posture)

…and publishes that as ActionOutcome through IG→EB. 

### 5.5 **Outcomes are joinable and auditable**

ActionOutcome must carry enough to let DLA and Case join it deterministically:

* ContextPins
* linkage to the intent (`parent_event_id` or explicit intent_ref)
* linkage to decision / case when applicable
* actor_principal + authz_policy_rev
* attempt number + timestamps

---

## 6) AL’s handshakes with its neighbours (what each edge “means”)

### 6.1 DF → AL (semantic handshake)

**DF declares**: “this action should be attempted,” with deterministic keys and provenance. 
**AL responds**: “this is what actually happened (or why it didn’t).” 

**Pinned division of labour:**

* DF owns *intent semantics* and decision provenance.
* AL owns *execution truth* and attempt history.
* DF must not assume execution happened; it can only observe outcomes later via EB/DLA. 

### 6.2 Case Workbench / Human → AL (manual handshake)

Humans do not “click execute” directly on some backend.
They emit an ActionIntent:

* actor = human principal
* origin = case_workbench
* link = case_id (and optionally the triggering event/decision)

AL applies stricter authz, then executes/denies/fails like any other intent. 

### 6.3 AL ↔ IG (trust boundary handshake)

AL is just another producer:

* It must set `producer` in the envelope and expect IG to validate it against transport identity (mismatch → quarantine).
* If IG returns **DUPLICATE**, AL treats it as success of publication (because the outcome already exists on the bus).
* If IG returns **QUARANTINE** for an AL outcome, that is an operationally critical violation (it means AL is producing inadmissible traffic); AL must surface that immediately to ops/governance. 

### 6.4 AL → EB → DLA (audit closure handshake)

DLA is append-only flight recorder and will join:

* DF’s decision record (primary)
* AL’s outcomes (closure, “intent vs executed”) 

So AL’s obligation is simple: publish outcomes that are **joinable by stable IDs + ContextPins**, and never mutate them.

### 6.5 AL outcomes as “business traffic”

Because EB admitted events feed the hot path broadly, AL outcomes can be treated as facts:

* “this transaction was declined”
* “this entity was blocked”
* “this case was queued”

If you want IEG/OFP to use them, then ActionOutcome (or a companion “ActionEffect” event) must carry whatever minimal identifiers your envelope-driven projections require. That’s a design choice we can pin next—but the outer rule is: **if it influences decisions later, it must be admitted traffic and envelope-conformant.**

---

## 7) Two canonical sequences (so there are no hidden assumptions)

### 7.1 Automated decision → action execution

```
(1) EB -> DF consumes transaction_event
(2) DF decides + emits ActionIntent (enveloped) -> IG -> EB
(3) AL consumes ActionIntent from EB
(4) AL authz-checks (DF principal allowed? action_type allowed? scope allowed?)
(5) AL idempotency-checks (ContextPins, idempotency_key)
      - if duplicate: re-emit canonical ActionOutcome -> IG -> EB
      - else: execute side-effect (once)
(6) AL emits ActionOutcome (EXECUTED / DENIED / FAILED) -> IG -> EB
(7) DLA ingests DF decision record + AL outcomes (join by ids/pins)
(8) Case timelines can reference outcomes by-ref
```

(All transport is via IG/EB; at-least-once is assumed; idempotency prevents double side effects.) 

### 7.2 Manual case action (same rails)

```
(1) Case Workbench emits ActionIntent (origin=case, actor=human) -> IG -> EB
(2) AL consumes, authz-checks human principal, executes/denies/fails
(3) Outcome -> IG -> EB -> DLA + Case timeline
```

No bypass, same auditability, same replay safety. 

---

## 8) One designer decision to lock now (prevents a ton of drift)

### ActionIntent is a **first-class event type** on EB

AL should not have to parse “DecisionResponse blobs” to find actions.

So we lock:

* DF emits **ActionIntent events** (even if DF also emits a DecisionResponse that references them).
* AL subscribes to ActionIntent event types only.
* Outcomes are separate ActionOutcome event types.

This keeps the network clean and keeps IG schema-gating obvious (event_type + schema_version).

---

Yes — there are a handful of **foundation pins** about AL that are worth locking *before* we even touch joins, because they determine what every join is allowed to assume.

Below are the ones I’d pin now (designer-authoritative for this brainstorm).

## Pins to lock now

### 1) AL’s authority boundary

**Pin:** AL is the **only** executor of side effects; everyone else only **requests**. AL is system-of-record for **ActionOutcome + attempt history**. 
**Why it matters:** prevents “hidden execution” creeping into DF/UIs/ops.

### 2) “Traffic rules” apply to AL too

**Pin:** ActionIntents and ActionOutcomes are **real traffic** and therefore flow through **IG → EB** (no bypass). 
**Pin:** Any bus-visible intent/outcome is **canonical-envelope first** (event_id/type/ts_utc/manifest_fingerprint at minimum).
**Why:** keeps AL aligned with the platform trust boundary and replay model.

### 3) The identity scope AL uses (ContextPins)

**Pin:** AL’s semantic identity scope is **(ContextPins, idempotency_key)** for “same intent.” 
**Pin:** `scope` is a first-class idea in AL (used for authz + idempotency scoping), and it binds to ContextPins / target entity / environment. 
**Why:** without a pinned scope notion, “same action” and “who can do what where” will drift.

### 4) Actor model + authorization is mandatory (and produces DENIED outcomes)

**Pin:** Every ActionIntent carries **actor_principal** + **origin** (DF vs human/case vs ops). AL enforces an allowlist `(actor_principal, action_type, scope)` and records **authz_policy_rev** in the outcome. 
**Pin:** If unauthorized → **DENIED ActionOutcome** (still idempotent, still immutable), and **nothing executes**. 
**Why:** this is a platform choke point (safety + audit); it can’t be “implied.”

### 5) Outcome decision space + terminality

**Pin:** ActionOutcome must express at least: **EXECUTED | DENIED | FAILED** (+ attempt). 
**Pin:** “No silent drops”: every handled intent yields an observable outcome path (including denied/failure). 
**Why:** downstream (DLA, case timelines) needs a mechanically complete story.

### 6) Attempt history rules (append-only) and what duplicates “see”

**Pin:** Outcomes are **immutable**, and history is **append-only** per semantic key. 
**Pin:** Duplicates must **never** re-execute; they “return” the canonical outcome for that semantic key. 
**Designer pin (needed to remove ambiguity):** “canonical outcome” = **latest known terminal attempt** for that `(ContextPins, idempotency_key)` (deterministic selection rule).
**Why:** otherwise duplicates under retries become inconsistent (“which outcome is *the* outcome?”).

### 7) Fail-closed stance when idempotency can’t be proven

**Designer pin:** If AL cannot consult its idempotency/ledger state, AL **must not execute blind** (it produces FAILED with a stable category like `IDEMPOTENCY_STATE_UNAVAILABLE`, retryable=true).
**Why:** executing without idempotency proof violates “effectively-once” by construction.

### 8) External execution must accept an idempotency token (or be restricted)

**Designer pin:** Every executor adapter must be given an **external idempotency token** derived from the semantic key, *when the target supports it*.
If a target **cannot** be made idempotent, that action type is classified as **unsafe** and can be restricted to higher-privilege/manual origin or forced through an additional control posture.
**Why:** AL can’t honestly promise effectively-once side effects if the external sink can’t dedupe.

### 9) Bounded execution model (so “no PENDING” is viable)

**Designer pin:** v0 AL is for **bounded-time actions** (approve/decline/step-up/queue-case style). Long-running workflows are out-of-scope for AL v0 and must be modeled as separate action types with explicit completion events (later), not hidden “pending forever.”
**Why:** otherwise we’ll be forced into multi-phase outcomes and extra joins immediately.

### 10) Safety switches are first-class

**Designer pin:** AL must honor an explicit **kill switch / capability disable** posture (from ops/governance), turning execution into DENIED or FAILED safely-with-reason, while still emitting outcomes for audit. 
**Why:** lets you stop side effects without breaking replay/audit semantics.

---

## Things we can *leave loose* until after joins (safe to defer)

* Exact executor topology (workers, queues, threads)
* Storage backend choice for the idempotency/outcome ledger
* Exact action_type vocabulary beyond the initial set
* Detailed error taxonomy (beyond a small stable set)
* Topic/stream naming conventions

If you’re happy with these pins, then when we *do* move to joins, we’ll be able to define each handshake without ambiguity because the “meaning” of action identity, authorization, retries, and outcomes is already nailed down.

---

Yes. If we keep **AL opaque** and only reason about its **production-grade connectivity** inside your already-pinned platform graph, then the “complete set” is:

1. **Direct joins (edges touching AL)**
2. **Composite paths (multi-hop routes where AL is on the path)**
3. **Closed loops (feedback cycles that *must* exist or commonly exist in production)**
4. **Explicit non-joins (edges that must *not* exist, to prevent drift)**

Everything below is consistent with your pinned platform blueprint + deployment posture.

---

## 1) Direct joins touching AL (production edges)

### J1 — EB → AL (Intent delivery edge)

**Meaning:** AL consumes **ActionIntent** events from EB (at-least-once; duplicates possible).
**Where intents originate (upstream writers):**

* DF (automated)
* Case Workbench (manual)
* Ops/Run-Operate surfaces (operational)

**Boundary shape:** every intent is carried in the **Canonical Event Envelope** (required `event_id, event_type, ts_utc, manifest_fingerprint`, optional ContextPins).

---

### J2 — DF → AL (semantic authority edge)

**Meaning:** DF **declares** actions; AL **executes** them effectively-once. This is the join where “what counts as the same intent” is pinned as **(ContextPins, idempotency_key)**. 
**Important:** transport still flows DF → IG → EB → AL; this join is about *authority boundaries*, not transport. 

---

### J3 — Case Workbench → AL (manual action edge)

**Meaning:** humans can *request* actions, but **must not bypass** AL; manual action is just higher-privilege ActionIntent.
**Transport:** Case → IG → EB → AL (same as DF). 

---

### J4 — Ops/Run-Operate → AL (operational action edge)

**Meaning:** ops can request emergency/administrative actions (if you allow it), but they still must flow as ActionIntent with actor principal + scope, and remain auditable.
This edge also covers **control knobs** that affect execution behavior (kill switches, drains), because those are outcome-affecting operational actions and must be explicit/governed.

---

### J5 — AL → External Effectors (side-effect edge)

**Meaning:** AL is the **only** component that actually performs side effects (approve/decline/step-up/case queue/notify/etc.).
These “effectors” are outside the platform graph (or simulated inside your closed world), but in production they are real dependencies.

*Optional but common:* External effectors emit callbacks/acks that re-enter the platform via IG/EB (see J10). (This doesn’t violate any pins because IG remains the front door.)

---

### J6 — AL → IG (publish outcome edge)

**Meaning:** AL publishes **ActionOutcome** as “real traffic” through the **trust boundary**. IG decides ADMIT/DUPLICATE/QUARANTINE and emits receipts.
**Boundary shape:** outcomes are canonical-envelope events.

---

### J7 — IG ↔ EB (durable append edge for outcomes)

**Meaning:** admitted ActionOutcome becomes an immutable fact at some (stream, partition, offset). EB is the truth for replay position.

---

### J8 — EB → DLA (audit closure edge)

**Meaning:** DLA ingests DF’s DecisionResponse and (optionally/commonly) AL outcomes to close “intent vs executed/denied/failed” in the flight recorder.
AL’s obligation here is not a direct call—it’s to ensure outcomes are **joinable** (ContextPins + ids + idempotency_key + provenance). 

---

### J9 — AL ↔ Observability/Governance (operability edge)

**Meaning:** AL emits the signals needed to operate safely (success/failure rates, retry pressure, lag, dependency health, policy revision used), and must be subject to governed controls (corridor checks / kill switch posture).
This is required for “production-ready” because outcome-affecting operational actions must be explicit and traceable.

---

### J10 — External callbacks → IG → EB → AL (optional async completion edge)

**Meaning:** if any action is asynchronous (e.g., “step-up initiated then later completed”), external systems can emit callback events back into the platform through IG/EB.
AL may consume those events as part of completing/closing an action lifecycle *if you decide to support async actions*. (Not required for v0; but it’s a real production join.)

---

### J11 — AL outcomes → Case plane (consumer edge)

**Meaning:** Case Workbench consumes DF/AL/DLA pointers to build immutable timelines; outcomes are part of that evidence trail.
**Mechanically:** Case can read via EB subscription, via DLA query/export, or via an evidence API—your platform pin is *by-ref evidence consumption*, not a specific transport. 

---

### J12 — AL outcomes → IEG/OFP/DF (optional “actions become facts” edge)

**Meaning:** if you want actions to influence future decisions (they usually should), then ActionOutcome (or a derived “ActionEffect” event) is consumed like any other admitted event by IEG/OFP and therefore changes future DF context.
This is a *major* production feedback edge (see loops below).

---

## 2) Production paths that include AL (multi-hop)

### P1 — Automated hot path (the canonical one)

EB (business event) → IEG/OFP/DL → DF → **IG → EB → AL** → **IG → EB** → DLA (and evidence consumers).

### P2 — Manual action path (same rails, different origin)

Case Workbench → **IG → EB → AL** → **IG → EB** → DLA + Case timeline.

### P3 — Operational intervention path (rare, but production-real)

Run/Operate/Admin → **IG → EB → AL** → **IG → EB** → DLA + Governance trail.

### P4 — Quarantine/remediation path involving AL

AL publishes Outcome → IG quarantines (schema/authz/joinability failure) → privileged quarantine access/release → reprocess → admitted → DLA.

### P5 — Replay/backfill path

Run/Operate triggers replay/backfill → EB re-delivers intents/outcomes → AL must remain effectively-once (duplicates re-emit canonical outcome) → DLA remains consistent.

---

## 3) The closed loops (production feedback cycles) involving AL

These are the loops you *actually* get in a production-ready platform—i.e., cycles that drive behavior over time.

### L1 — Decision → Action → Audit closure loop

DF emits intents → AL executes/denies/fails → outcomes land on EB → DLA records “what was intended vs what happened.”

### L2 — Action outcomes feed future decision context loop (the “system changes itself” loop)

AL outcomes become admitted facts → IEG/OFP update projections/snapshots → DF sees new context and may emit new intents → AL executes again.
This is how “block”, “step-up”, “queue case”, “release” actually affects subsequent traffic.

### L3 — Human truth loop (cases/labels drive future actions)

DF/AL/DLA evidence → Case timelines → Label assertions → Label Store → offline shadow → Model Factory → Registry → DF (new policy) → AL (new actions).

### L4 — Governed change / safety loop (ops makes execution safer over time)

AL health/errors/lag → Obs/Gov corridor checks → Run/Operate actions (kill switch, drain, policy update) → AL behavior changes → governance facts recorded for auditability.

### L5 — Quarantine triage loop (quality control)

Bad/unauthorized/malformed action traffic → quarantine with evidence → privileged review → release/reprocess or reject → corrected traffic re-enters via IG/EB.

### L6 — Replay determinism loop (prove the system is stable under replay)

EB replays duplicates → AL must not double-execute → outcomes remain consistent → DLA remains consistent → parity can be checked later (including offline rebuilds).

---

## 4) Explicit non-joins (edges that must NOT exist)

To keep the vertex “clean” and prevent drift, these edges are **forbidden** in the production graph:

1. **AL ↔ Data Engine (direct)** — AL must not read engine outputs or gates directly. (Engine truth is upstream via SR/IG and by-ref joins elsewhere.) 
2. **AL ↔ SR (world selection/readiness)** — AL must not decide what run/world is “current.” It only acts on ContextPins carried by intents/outcomes. 
3. **AL → EB bypassing IG** — AL is a producer like any other; IG remains the front door. 
4. **AL becomes decision authority** — AL doesn’t decide; DF decides. AL only executes and reports. 
5. **AL writes labels / edits cases directly** — label truth is Label Store; case truth is Case Mgmt timelines. AL may emit outcomes that those planes consume, but it doesn’t own their truth.

---

### One compact “map view” (AL-centered)

```text
                 (Obs/Gov) <----metrics/traces----> (AL) <----control knobs----> (Run/Operate)
                                            |
                                            | executes side effects
                                            v
                                      [External Effectors]
                                            ^
                                            | (optional callbacks)
                                            |
(DF) / (Case UI) / (Ops UI)  -> IG -> EB -> (AL) -> IG -> EB -> (DLA) -> (Case timelines/exports)
                                     |
                                     | (optional: outcomes as facts)
                                     v
                                   (IEG/OFP) -> DF -> ...
```

This diagram is just a visual summary of the joins/loops listed above.

---

Here’s the **recommended expansion order** for the **complete AL outer-network joins/paths/loops** (AL treated as opaque), aligned to the pinned platform network + envelope rails.

1. **P1 — Canonical automated hot path (end-to-end)**: EB → DF → (IG→EB) → AL → (IG→EB) → DLA

2. **J2 — DF → AL (semantic authority join)**: intent meaning + `(ContextPins, idempotency_key)`

3. **J1 — EB → AL (delivery join)**: at-least-once intake of ActionIntent

4. **J5 — AL → External Effectors (execution join)**: the actual side-effect boundary

5. **J6 — AL → IG (publish join)**: ActionOutcome emission to trust boundary

6. **J7 — IG ↔ EB (append/replay join)**: offsets/watermarks become truth

7. **J8 — EB → DLA (audit closure join)**: outcomes join into flight recorder

8. **L1 — Decision → Action → Audit closure loop**

9. **J12 — AL outcomes → IEG/OFP/DF (actions-as-facts join, if enabled)**

10. **L2 — Action outcomes feed future decision context loop**

11. **P2 — Manual case action path (end-to-end)**: Case → (IG→EB) → AL → (IG→EB) → DLA/Case

12. **J3 — Case Workbench → AL (manual intent join)**

13. **J11 — AL outcomes → Case plane (timeline/evidence consumption join)**

14. **L3 — Human truth loop**: outcomes → cases/labels → models/policy → DF → actions

15. **P3 — Operational intervention path (end-to-end)**: Ops/Run-Operate → (IG→EB) → AL → (IG→EB) → DLA

16. **J4 — Ops/Run-Operate → AL (operational intent/control join)**

17. **J9 — AL ↔ Observability/Governance (operability + controls join)**

18. **L4 — Governed change / safety loop**

19. **P4 — Quarantine/remediation path**: (IG quarantine) → review/release → reprocess

20. **L5 — Quarantine triage loop**

21. **P5 — Replay/backfill path**: EB redelivery → AL dedupe → outcomes stable

22. **L6 — Replay determinism loop**

23. **J10 — External callbacks → (IG→EB) → AL (optional async completion join)**

24. **Forbidden edges (explicit non-joins list)**: AL↔Engine, AL↔SR, AL→EB bypassing IG, AL as decision authority, AL writing labels/cases directly. 

---

Cool — expanding **1 → 5** in-order, keeping **AL opaque** (we’re defining the *outer expectations* that AL must satisfy inside the pinned platform network). Everything here is **designer-authoritative for this brainstorm** and must remain consistent with the platform pins. 

---

## 1) P1 — Canonical automated hot path (end-to-end)

**Path:** `EB → DF → (IG→EB) → AL → (IG→EB) → DLA` 

### P1.0 What this path *is*

It’s the platform’s “decision becomes reality” pipeline.

* **EB** provides the admitted domain event (at-least-once; replayable). 
* **DF** converts “facts” into a **DecisionResponse + ActionIntent(s)** (requests). 
* **IG→EB** makes those intents durable, replayable traffic (trust boundary). 
* **AL** is the **only** executor: it authorizes + executes effectively-once and emits **ActionOutcome** truth. 
* **IG→EB** admits outcomes as durable facts. 
* **DLA** records the “flight recorder” story: decision context + intent + outcome closure. 

### P1.1 Step-by-step narrative (with the minimum “facts that must exist”)

1. **EB delivers an admitted business event** to DF

   * Delivered in a **Canonical Event Envelope** (required `event_id, event_type, ts_utc, manifest_fingerprint`; optional ContextPins).
   * EB delivery is at-least-once; duplicates are normal. 

2. **DF decides** and produces two outputs

   * **DecisionResponse** (what DF decided, with provenance). 
   * **ActionIntent(s)** (what should be executed), each carrying an `idempotency_key` and ContextPins. 

3. **DF publishes ActionIntent(s) as traffic** via IG→EB

   * Must be envelope-conformant at the boundary.
   * IG is authoritative for admit/duplicate/quarantine receipts; EB is authoritative for offsets. 

4. **AL consumes ActionIntent(s) from EB**

   * AL may see duplicates/out-of-order across partitions; it must be safe. 
   * AL applies its **two mandatory gates**: (a) AuthZ, (b) idempotency. (AuthZ is a platform safety choke point; idempotency is pinned as `(ContextPins, idempotency_key)`.) 

5. **AL executes the side effect (or refuses)**

   * If unauthorized → do **not** execute; emit **DENIED** outcome.
   * If duplicate semantic intent → do **not** execute; re-emit canonical outcome. 
   * If authorized + not duplicate → execute once, then emit outcome. 

6. **AL publishes ActionOutcome as traffic** via IG→EB

   * Outcome is immutable and joinable; becomes a durable fact.

7. **DLA ingests and closes the story**

   * DLA is the immutable audit flight recorder; it should be able to join: *what was decided* + *what was intended* + *what actually happened* (including deny/fail). 

### P1.2 What must be true for P1 to be “production-ready”

* **No hidden execution:** DF never “does” actions; it only requests. 
* **No silent drops:** every intent yields an outcome path (EXECUTED / DENIED / FAILED). 
* **Replay-stable:** replays cannot cause duplicate side effects; duplicates must converge to the same outcome for the same semantic key. 
* **Time semantics don’t collapse:** `ts_utc` is domain time; ingest time and apply time stay separate.

---

## 2) J2 — DF → AL (semantic authority join)

This join is **not transport** (transport is via IG/EB). It’s the contract of meaning: *what DF promises when it emits an intent* and *what AL promises in return*. 

### J2.1 The “division of truth” (pinned)

* **DF is authoritative for:**

  * decision logic and decision provenance
  * that an action **should be attempted**
  * the **semantic identity recipe** for intents (`idempotency_key`) 

* **AL is authoritative for:**

  * whether it was executed/denied/failed
  * attempt history
  * any external interaction evidence it has (refs/ids) 

### J2.2 What DF must put in an ActionIntent (minimum meaning, not a full schema)

At the *semantic* level, every ActionIntent must provide:

1. **ContextPins** (so the action is joinable to the correct run/world)
2. **`idempotency_key`** (semantic uniqueness key) 
3. **`action_type`** (what kind of thing is being requested)
4. **`target_ref` / `target_scope`** (what the action applies to: entity, transaction, account, case, etc.)
5. **`actor_principal` + `origin`** (who requested it, and from where)
6. **`rationale_ref`** (pointer to decision id / evidence / case id — by-ref posture) 

**Designer pin (removes drift):**
`event_id` (envelope) is for **boundary dedupe**; `idempotency_key` (payload) is for **semantic execution identity**. They are not the same thing.

### J2.3 “Same intent” definition (the one that governs effectively-once)

**Same intent ⇔ same `(ContextPins, idempotency_key)`**. 

Consequences:

* DF must generate the idempotency_key **deterministically** from decision context (so retries/replays don’t mint “new” actions).
* AL must treat duplicates as non-executable and converge to the canonical outcome. 

### J2.4 What AL owes DF (and everyone else) in response

AL returns **truth as events**:

* **ActionOutcome** must be joinable back to the intent + the decision/case evidence pointer. 
* Outcomes must be immutable and replay-stable. 

---

## 3) J1 — EB → AL (delivery join)

This is the **operational reality join**: how intent traffic reaches AL under at-least-once semantics. 

### J1.1 What AL can assume (and what it cannot)

AL can assume:

* The message is **admitted traffic** (IG already applied boundary validation/admission decision). 
* The envelope has required fields (`event_id, event_type, ts_utc, manifest_fingerprint`). 

AL cannot assume:

* exactly-once delivery (duplicates happen) 
* global ordering (only within partition) 
* that every admitted intent is *semantically* valid for AL (e.g., unknown action_type) — AL must handle via a FAILED outcome, not by crashing.

### J1.2 AL’s subscription posture (outer behaviour)

* AL subscribes to **ActionIntent event types** only (it should not parse DF decision blobs to “discover actions”). 
* AL uses EB offsets/checkpoints as the replay-progress truth (exclusive-next offsets). 

### J1.3 The two “duplicate domains” AL must handle

1. **Boundary duplicates** (same envelope `event_id` delivered multiple times)
2. **Semantic duplicates** (different envelope `event_id`s but same `(ContextPins, idempotency_key)`)

AL must be safe under both; that’s why the uniqueness scope is semantic, not transport.

### J1.4 Recommended partitioning posture (so production behaves sanely)

EB requires a partition key and doesn’t infer it; IG stamps/chooses it. 
For ActionIntent traffic, the most drift-resistant partition key is one that keeps “same semantic key” close together (reduces concurrency races), e.g. deterministic from `(ContextPins, idempotency_key)` (exact derivation flexible).
This is not an AL internal detail; it’s an *outer-network expectation* that makes the whole pipeline stable at scale.

---

## 4) J5 — AL → External Effectors (execution join)

This is the **only place** side effects happen. Everything else is compute + logs. 

### J5.1 What counts as an “external effector” in your closed world

An effector is anything where “doing it twice” is dangerous, costly, or changes the world:

* payment authorizer / decline gate
* step-up / challenge trigger
* entity blocklist update
* case queueing / notification systems
* (in your closed world) simulated versions of the above

### J5.2 The execution handshake AL must enforce (outer semantics)

For any action execution attempt, AL must have:

* **Effector selection**: map `action_type` → effector adapter
* **Idempotency token**: derived from the semantic key (so the effector can dedupe)
* **Commit semantics**: what constitutes “EXECUTED” vs “FAILED” must be explicit

**Designer pin:**
If an effector cannot honor an idempotency token (or equivalent “dedupe key”), that action type is **unsafe** and must be restricted (e.g., manual-only, extra confirmation loop, or disallowed in v0). Otherwise AL cannot honestly maintain “effectively-once under replay.” 

### J5.3 Execution result categories AL must map to outcomes

* **EXECUTED**: AL has high confidence the side effect is committed (or the effector declares it idempotently committed).
* **FAILED**: AL could not complete safely (includes timeouts, dependency down, invalid params, unknown action_type).
* **DENIED**: AL refused (not authorized / kill switch / policy).

(These are the external, network-visible meanings; AL’s internal retry logic can be more nuanced later, but these meanings must remain stable.) 

### J5.4 Evidence posture (by-ref, not payload dumping)

AL should produce *joinable* evidence pointers in outcomes:

* effector name
* effector request id / reference
* result code category
* (optional) response ref / digest
  This supports DLA and case timelines without AL leaking internals or duplicating big payloads. 

---

## 5) J6 — AL → IG (publish outcome join)

This is how AL’s execution truth becomes **platform truth**. AL is “just another producer” at the front door. 

### J6.1 What AL publishes

AL publishes **ActionOutcome** as canonical-envelope events.

Minimum envelope + join fields:

* required envelope (`event_id, event_type, ts_utc, manifest_fingerprint`) 
* ContextPins where applicable (scenario_id/run_id/parameter_hash/seed)
* `parent_event_id` pointing to the intent’s event_id (causal link) 
* payload must include: `(ContextPins, idempotency_key)`, outcome decision (EXECUTED/DENIED/FAILED), actor/origin, and evidence refs 

**Time pin (important):**

* For outcomes, `ts_utc` is the **domain time of the outcome** (i.e., when the execution/denial happened), not the original business event time. Distinct from ingest time and apply time.

### J6.2 IG’s decision outcomes and AL’s required reaction

IG returns exactly one of: **ADMIT / DUPLICATE / QUARANTINE** with receipts. 

* **ADMIT**: outcome is now durable fact (AL can proceed).
* **DUPLICATE**: outcome already admitted (AL treats publish as success; do not republish endlessly).
* **QUARANTINE**: this is a **serious violation** for AL outcomes (it means AL produced inadmissible traffic). AL must surface it as an operational incident signal and stop assuming outcomes are reaching the bus. 

### J6.3 Outcome “history” posture (the minimum we pin now)

Platform pin says AL emits **immutable ActionOutcome history** and duplicates re-emit canonical outcome. 

**Designer pin (cleanest v0 interpretation):**

* Each semantic key has a **canonical terminal outcome** once it reaches EXECUTED or DENIED (terminal).
* FAILED may be terminal *or* retryable (but if AL later retries and changes the terminal state, that becomes a *new* immutable outcome record; no mutation).
* On duplicate intent, AL re-emits the **canonical terminal outcome if it exists**, otherwise the **latest known outcome record** (still immutable). 

This gives DLA and Case a coherent story without requiring “update-in-place,” which is forbidden by immutability.

---

If you want to continue right after this: the natural next question (still within 1→5) is **what DF is allowed to assume about execution latency and failure** (i.e., whether DF ever waits for outcomes or always observes them asynchronously). But I won’t jump there unless you tell me to—this should give you a solid, pinned expansion of items 1–5.

---

Absolutely — here’s the **production-grade expansion of #6–#10**, still treating **AL as opaque** (we’re pinning outer-network expectations and the realities those edges/loops must satisfy).

---

## 6) J7 — IG ↔ EB: durable append + replay (offsets/watermarks become truth)

This join is the **platform spine**: it’s where “candidate events” become **admitted facts** and gain **replay coordinates**. Your pins already state:

* **IG is the trust boundary**: admit/quarantine/duplicate + receipts. 
* **EB is the durable append + replay plane**: at-least-once delivery, no validation/transform, and **truth for partition/offset**.
* **Authoritative writer to EB is IG** (directly or as the acknowledged admission step). 

### J7.1 What “ADMIT” *means* (pin this)

**Designer pin:** IG must never return “ADMIT” unless the event is **durably appended** to EB (or to EB+Archive under the same logical stream). Anything less breaks replay determinism and auditing.

So “ADMIT” semantically implies:

* the event has a **canonical bus coordinate** `(topic, partition, offset)` (or equivalent) within EB retention
* the event is now part of the **replayable admitted history** (“what happened”) 

### J7.2 What IG receipts must be able to point to

Your platform pins “receipts + evidence pointers” as a first-class concept.
To make that real and drift-resistant:

**Designer pin:** an IG admission receipt must be able to reference (by-ref) the admitted fact in EB:

* either directly via **bus coordinate** `(topic, partition, offset)`
* or via an **immutable receipt object** that includes that coordinate

This matters because downstream correctness anchors (DLA, audits, replay parity checks) need a stable pointer to “the admitted fact,” not just “some message we saw.”

### J7.3 Two distinct duplicate domains (and why they’re both real)

* **Boundary duplicate**: same envelope `event_id` is submitted again (producer retry). IG returns DUPLICATE and should point to the previously admitted coordinate.
* **Bus duplicate**: EB delivers the same admitted message more than once (at-least-once). Consumers dedupe using envelope `event_id` (and their own idempotency recipes).

**Designer pin:** IG’s DUPLICATE must be *semantics-preserving*: it must never create a second admitted fact for the same boundary idempotency key (otherwise offsets/watermarks lie).

### J7.4 Partitioning posture (the watermark foundation)

You’ve pinned that the shared replay determinism hook is watermark vectors derived from per-partition offsets, and that **IG stamps a deterministic partition_key**.

**Designer pin:** IG owns partitioning; EB merely enforces partition+offset semantics. 
That means:

* IG must choose a **stable partition_key** for each admitted event type (so replays/retries route consistently)
* consumers’ “next_offset_to_apply” becomes the shared basis for:

  * IEG `graph_version` watermark vector 
  * OFP `input_basis` watermark vector 
  * DF provenance (“what I had applied/seen”) 

### J7.5 Retention vs archive (production reality)

You’ve pinned EB retention and the possibility of an archive as a long-horizon extension; archive must be treated as the **same logical fact stream**.

**Designer pin:** if a consumer needs history beyond EB retention, it replays from **archive** but still uses **the same identity + ordering basis per partition** (no “archive is a different universe”). 

---

## 7) J8 — EB → DLA: audit closure join (outcomes join into the flight recorder)

Your platform pins DLA as:

* **immutable flight recorder**
* **append-only audit record**
* corrections via **supersedes chain**, not overwrite
* **idempotent ingest**
* **quarantine on incomplete provenance**
* by-ref + hashes posture
* primary ingest = DF DecisionResponse, with optional AL outcomes to “close the loop” 

### J8.1 What DLA consumes (from EB)

**Pinned minimum**:

* DF’s **DecisionResponse** (decision + action intents + provenance) 
  **Optional but strongly production-useful**:
* AL **ActionOutcome** events (to close “intent vs executed”) 
* IG evidence pointers/receipts (where helpful)

### J8.2 What DLA must persist (by-ref)

From the pinned join list: audit must include by-ref/hashes for:

* event reference basis (what was decided on)
* `feature_snapshot_hash` + `input_basis`
* `graph_version` (if used)
* degrade posture (mode + identify mask)
* resolved active bundle ref
* actions (including idempotency keys)
* audit metadata (ingested_at, supersedes link) 

### J8.3 The closure design choice we should pin now (so it doesn’t drift)

If DLA only stores DecisionResponse and relies on “join outcomes from EB later,” you lose closure when EB retention expires. But DLA is explicitly the **flight recorder** and lives beyond retention (object store).

**Designer pin (authoritative):** DLA must persist **action closure by-ref** (at least pointers to outcomes), so audit remains complete beyond EB retention.

Concretely (still brainstorm-level):

* DLA writes an **AuditDecisionRecord** at decision ingest time (append-only).
* As ActionOutcome events arrive later, DLA writes **AuditActionClosure records** (append-only) that link:

  * `(ContextPins, audit_record_id, idempotency_key)` → outcome_ref(s) + terminal state
* This avoids mutating prior records and avoids abusing “supersedes” for normal closure. It also makes closure idempotent and replay-safe.

### J8.4 Quarantine posture (critical)

**Pinned:** if provenance is incomplete, DLA quarantines rather than writing a half-truth. 
That means in production:

* missing snapshot hash / missing bundle ref / missing degrade posture → quarantine the audit record
* later “repair” happens via a new record (supersedes chain) or release workflow

---

## 8) L1 — Decision → Action → Audit closure loop (the “did we actually do it?” loop)

This loop exists so the platform can always answer (later, under replay, under investigation):

> “What did we decide, what did we intend to do, what actually happened, and why?”

### L1.1 The loop in events (high level)

1. EB delivers business event → DF decides
2. DF emits DecisionResponse + ActionIntent(s) (traffic)
3. AL executes (or denies/fails) and emits ActionOutcome(s) (traffic)
4. DLA writes:

   * AuditDecisionRecord (decision + intents + provenance)
   * AuditActionClosure records (intent ↔ outcome) 

### L1.2 The closure invariant (pin this)

**Designer pin:** For every ActionIntent referenced by an audit decision record, there is eventually exactly one **terminal closure** in audit:

* EXECUTED or DENIED or FAILED-final (terminal)
* retries may produce multiple attempt facts, but closure converges to one terminal resolution per semantic key `(ContextPins, idempotency_key)` 

### L1.3 Production edge cases the loop must handle (explicitly)

* **Outcome arrives before audit decision record** (ordering differences across partitions/consumers): DLA must hold “unmatched closure” and reconcile later, or quarantine-orphan outcomes for audit review (but never silently drop). 
* **Decision record exists but no outcomes arrive**: DLA records “pending closure” and ops/governance can alarm on “closure lag / stuck actions.” (This is an observability join, but the loop demands it for production).
* **Duplicates everywhere**: DLA closure ingest must be idempotent (same closure record can be replayed without multiplying). 

### L1.4 What this loop gives you operationally

* You can compute **action closure lag** (decision time → outcome time) per action_type.
* You can prove “no silent execution / no silent drop.”
* You can do forensic replay after retention, because closure lives in DLA’s long-lived record set.

---

## 9) J12 — AL outcomes → IEG/OFP/DF (actions-as-facts join, if enabled)

This is optional in principle, but it’s extremely common in a production-ready platform because actions often change the world state DF should consider next.

### J12.1 What it means

**ActionOutcome becomes an admitted fact** on EB, so it can be consumed like any other event by:

* **IEG** (projection updates)
* **OFP** (feature snapshot updates)
* **DF** (future decisions)

### J12.2 Designer pin: not all outcomes are “state facts”

We avoid drift by classifying outcomes:

* **State-changing outcomes** (should feed projections): e.g., “entity blocked,” “step-up initiated,” “case opened/queued,” “limit reduced.”
* **Non-state outcomes** (may still feed features, but not projection): e.g., “notification sent,” “webhook attempted.”

**Designer pin:** if an action is expected to influence future decisions, its outcome must produce a projection-friendly fact, either:

* directly via ActionOutcome payload (preferred minimal), or
* via a small derived “ActionEffect” event emitted alongside the outcome (only if needed)

### J12.3 Projection-friendly “effect descriptors” (to keep IEG/OFP sane)

Because you’ve pinned an envelope-first boundary and a desire for envelope-driven projection discipline, we need a stable way for IEG/OFP to extract “what changed” without parsing arbitrary blobs.

**Designer pin:** ActionOutcome (for state-changing action types) carries a minimal, stable `effects[]` structure inside payload:

* effect_type (blocked/unblocked/queued/stepup/etc.)
* target identifiers (the entity/subject)
* effective_time (usually aligns to outcome `ts_utc`)
* optional TTL (if it expires)

IEG/OFP treat `effects[]` as the only part they need to parse for action outcomes.

### J12.4 Time + watermark alignment (crucial)

If outcomes feed features/projections, then:

* outcome `ts_utc` becomes the **domain time** the effect becomes true
* the fact becomes included/excluded in OFP snapshots via `as_of_time_utc` boundaries
* and the applied offsets contribute to `graph_version` / `input_basis` provenance 

This is what makes “actions as facts” replay-deterministic.

---

## 10) L2 — Action outcomes feed future decision context loop (the “closed world actually changes” loop)

This is the core feedback cycle that turns the platform from “decide in a vacuum” into “decide in a changing world.”

### L2.1 The loop

1. DF observes event + context → emits ActionIntent
2. AL executes → emits ActionOutcome
3. IEG/OFP incorporate outcome effects (state/feature changes)
4. Next events arrive → DF sees updated context → decisions/actions change

### L2.2 The stability requirement (pin this)

To prevent runaway loops (“keep blocking the already-blocked card”):

**Designer pin:** every state-changing action type must have a clear **stop condition fact** that DF can observe via projections/features.

Examples:

* block action → “entity_blocked=true” fact exists → DF does not request block again
* queue case → “case_open=true / case_queued=true” fact exists → DF does not re-queue
* step-up → “stepup_required=true” fact exists → DF doesn’t re-trigger until it’s cleared/expired

This is the difference between a stable feedback loop and an infinite action spam machine.

### L2.3 Hysteresis/TTL (production realism)

Some action effects naturally expire (blocks, step-ups, velocity limits).
So the loop must support **TTL / expiry semantics** (in IEG/OFP) so DF can re-enable actions only when appropriate, not via “magic reset.” 

### L2.4 Degrade + safety interacts with this loop

Because degrade is explicit and must be recorded:

* DL can disable action capabilities → DF must not emit those intents 
* AL can still deny (policy/kill switch) and that denial is itself a fact (useful for audit and for understanding “why didn’t we act?”)

### L2.5 Replay determinism guarantee

This loop only remains reproducible if DF records the provenance anchors you’ve pinned:

* OFP snapshot hash + input_basis
* IEG graph_version
* degrade posture
* active bundle ref 

That way, on replay, “what DF knew” is reconstructible even though actions changed the world.

---

If you want, the next natural move (still outer-network, still AL opaque) is to take **#9 and #10** and enumerate the **minimal set of “state-changing action families”** your platform must support (block/step-up/queue-case/notify/etc.) and for each, pin: *effect fact*, *stop condition*, *TTL/hysteresis*, and *who consumes it (IEG vs OFP vs DF)* — that’s where L2 becomes rock-solid and drift-resistant.

---

Perfect — let’s expand **#11–#15** (AL still **opaque**) by pinning what each join/path/loop must *mean* in a production-ready platform.

---

## 11) P2 — Manual case action path (end-to-end)

**Path:** `Case Workbench → (IG→EB) → AL → (IG→EB) → DLA/Case`

### What P2 exists to guarantee

Manual actions are **not** a “special escape hatch.” They are the human-in-the-loop way to *request* outcomes while keeping:

* **the same trust boundary (IG)**
* **the same replay safety (EB at-least-once)**
* **the same execution choke point (AL)**
* **the same audit closure (DLA)**

### P2 step-by-step (production story)

1. **Case Workbench operator initiates a manual action** (e.g., “block entity”, “release”, “queue escalation”, “force step-up”).

   * This is a *request*, not execution.

2. **Case Workbench emits an ActionIntent event** (origin=`case_workbench`, actor_principal=`human principal`) and submits it **through IG**.

   * IG performs producer authz at the front door (no identity → no admission; event_type allowlist, scope).

3. **EB delivers the admitted ActionIntent to AL** (at-least-once).

4. **AL authorizes execution** using the actor_principal + scope + action_type allowlist (manual action is “higher privilege,” not bypass). If unauthorized → AL must emit **Denied ActionOutcome** (idempotent, immutable).

5. **AL executes effectively-once** using uniqueness scope `(ContextPins, idempotency_key)` and publishes **ActionOutcome** through IG→EB.

6. **DLA ingests outcomes for closure**, and **Case** consumes outcomes/evidence to update case timelines.

### Production pins for P2 (so it can’t drift)

* **No direct “call AL” from UI**: UI submits ActionIntent only via IG/EB.
* **Manual actions must be attributable** (actor_principal + provenance) and **auditable** end-to-end.
* **Manual actions obey the same idempotency law** as automated actions: duplicates do not re-execute.

---

## 12) J3 — Case Workbench → AL (manual intent join)

This “join” is **semantic**: it defines what Case promises when it requests an action, and what AL must do with it. Transport still flows via IG→EB.

### What crosses J3 (minimum facts)

A manual ActionIntent must carry:

* **actor_principal** (human identity) and **origin=case_workbench**
* **case_ref** (stable case identifier) so timelines can join intent/outcome to the case
* **rationale_ref** (pointer to evidence: DLA record id, or the event/decision refs)
* **action_type + target_ref + scope** (what is being acted upon, and in what scope)
* **idempotency_key** (semantic key; stability across retries)

### The non-negotiable control posture on J3

This is pinned explicitly as part of the access/control overlay:

* **Case Workbench can request, but only AL executes**.
* AL must enforce allowlists by `(actor_principal, action_type, scope)`.
* If not authorized → **Denied ActionOutcome** (still immutable, still idempotent).

### A production-grade “two-stage meaning” (important)

Manual actions are often **decision overrides**, so we pin how they relate to DF:

* **Case does not replace DF truth**; it creates **human intervention facts**.
* Those facts should surface as either:

  1. an ActionOutcome that becomes a fact (if it changed state), and/or
  2. a LabelAssertion later (ground truth adjudication).

This prevents “humans stealth-edit the world” without leaving trail.

---

## 13) J11 — AL outcomes → Case plane (timeline/evidence consumption join)

Case is the human truth/workflow surface with **immutable timelines**; it must be able to show “what we intended” and “what actually happened.”

### What Case consumes (and from where)

Pinned production posture is “by-ref evidence,” not payload duplication:

* **Primary evidence**: DLA audit records in object store (`dla/audit/...`)
* **Live updates** (optional): EB subscriptions for new outcomes (useful for UI freshness), but EB is not the long-term evidence store.

### What Case needs from ActionOutcome (joinability requirements)

To render a coherent case timeline, Case must be able to join:

* case_ref (when action is case-driven or case-relevant)
* intent_ref (parent event id / idempotency key)
* decision_ref (when action came from DF)
* actor_principal + origin
* outcome decision (EXECUTED / DENIED / FAILED)
* evidence pointers (effector refs / audit refs), by-ref posture

### Production pin: Case timeline truth stays in Case DB

Case is authoritative for case timeline state (`case_mgmt`), not AL, not DLA. But it **references** DLA/AL evidence by-ref.

So:

* AL does **not** “update cases”
* DLA does **not** “own case workflow”
* Case Workbench **records** a timeline entry referencing the outcome (and optionally referencing the audit record id)

### Critical production edge-case (pin now)

**Outcome-first vs Audit-first ordering** happens (different consumers/partitions). Therefore:

* Case must tolerate “Outcome observed, audit record not yet indexed/available” by showing a placeholder evidence pointer and resolving later.
* Conversely, Case may see audit record first and later see outcomes.
  No silent drops; just eventual joinability.

---

## 14) L3 — Human truth loop (cases/labels drive future system behaviour)

Pinned loop (your blueprint):
`DF/AL/DLA pointers → Case Workbench → Label Store → (Offline Shadow → Model Factory → Registry → DF) → Actions`

### What L3 exists to guarantee

* Humans produce **ground truth** (labels) and **interventions** (manual actions).
* The platform evolves safely: labels inform offline rebuild/training; registry controls what becomes active; DF changes future intents; AL executes outcomes — all traceable.

### The “human truth” pin that makes this loop safe

**Label Store** is the single truth writer for labels, and labels are append-only timelines with **effective_time vs observed_time** to prevent leakage and preserve causality.

That means:

* Case can *produce* assertions, but label truth exists only once written to Label Store.
* Corrections are new assertions, not destructive edits.

### How AL participates in L3 (AL’s outward responsibility)

AL doesn’t write labels. AL contributes:

* **ActionOutcome facts** (what actually happened)
* Joinable references so cases/labels can attribute “why this label was applied” (decision ref / evidence refs)

A clean L3 story in practice:

1. DF emits intent, AL executes, DLA records.
2. Case investigator reviews DLA evidence + outcomes and writes labels (effective/observed).
3. Offline Shadow uses EB/Archive + Label Store **as-of** to rebuild training datasets deterministically.
4. Model Factory produces bundles + evidence + PASS posture; Registry controls ACTIVE; DF resolves active bundle deterministically.
5. DF changes future intents; AL executes them — completing the evolution loop.

### Production stability pin (prevents “human loop drift”)

This loop only works if **correlation conventions are mandatory** (run pins, event ids, decision ids, action ids) so every label can be traced to the evidence that motivated it.

---

## 15) P3 — Operational intervention path (end-to-end)

**Path:** `Ops/Run-Operate → (IG→EB) → AL → (IG→EB) → DLA`

### What P3 is (and what it must NOT become)

Pinned: **Run/Operate is substrate, not a shadow truth source**. It can initiate controlled operations, but it must not invent domain truths.

So P3 is for operationally necessary, outcome-affecting interventions that still remain:

* explicit
* attributable
* auditable
* deterministic in scope/meaning

### Two types of “ops interventions” (pin this split)

1. **Ops-as-actor requests a domain action** (goes through AL as ActionIntent)
   Examples: “force block this entity,” “force step-up,” “revoke a permission,” “queue a case.”

   * origin=`ops`, actor_principal=`operator/service principal`
   * still goes IG→EB→AL → outcomes back to DLA

2. **Ops changes platform posture** (governance/control facts, not ActionIntents)
   Examples: kill switch, drain, backfill window changes, retention changes.

   * must emit explicit governance facts and be traceable

P3 is specifically category (1). Category (2) is the Run/Operate ↔ Obs/Gov loop (we’ll expand later when we reach #16–#18).

### P3 step-by-step (ops domain action)

1. Operator/admin surface issues an operational ActionIntent (origin=`ops`).
2. IG authenticates/authorizes the producer principal and admits/quarantines accordingly.
3. EB delivers to AL; AL enforces **its own** allowlist `(actor_principal, action_type, scope)` (ops is not “god mode” by default).
4. AL executes effectively-once and emits ActionOutcome; DLA records it for audit.

### Production pins for P3 (so ops can’t silently change behaviour)

* Any ops action that can affect outcomes must be **auditable governance-visible fact** (who/why/when/scope).
* No hidden nondeterminism (“silent retries that change meaning,” implicit now, environment-dependent behaviour) in ops triggers.
* Emergency controls are explicit and traceable (kill switch/drain/forced-degrade are governance facts).

---

Alright — expanding **#16–#20** (AL still **opaque**). I’ll stay strictly inside your pinned platform rails: **IG is the front door**, **EB is replay truth**, **AL is the only executor**, **Obs/Gov + Run/Operate are the safe-change loop**, and **quarantine is first-class** (never silent drops).

---

## 16) J4 — Ops/Run-Operate → AL (operational intent/control join)

This join is about **how ops can influence execution** without becoming a shadow truth source. The pin is clear: **Run/Operate is the operational substrate, not a domain truth source**, and any outcome-affecting operational act must be **explicit + auditable**.

### J4.1 There are two legitimate “ops → AL” surfaces (pin this split)

#### (A) Ops requests a *domain action* (same as DF/Case, just different principal)

* Ops emits an **ActionIntent** with `origin=ops` and an `actor_principal` that represents the operator / automation identity.
* Transport must still be **Ops → IG → EB → AL** (no direct calls).
* AL enforces allowlist `(actor_principal, action_type, scope)` and idempotency `(ContextPins, idempotency_key)` the same way it would for DF/Case.

**Why this matters:** ops can intervene, but it’s still *request → execute → outcome*, never bypass.

#### (B) Ops changes *AL’s execution posture* (controls, not “actions”)

This includes:

* **Kill switch / forced deny** (by scope/action_type)
* **Drain / pause consumption** (stop taking new intents, finish in-flight)
* **Rate/concurrency caps** (reduce harm during incidents)
* **Policy revision activation** (new allowlist rules)

These are **outcome-affecting operational changes**, therefore they must:

* be **governed facts** (actor, scope, before/after, reason), and
* be visible to Obs/Gov (no silent toggles).

> **Designer pin:** “Ops controls” are not ad-hoc runtime flags. They are **profile/policy revisions** or **explicit control events** whose activation is recorded as a governance fact.

### J4.2 What AL must do with ops inputs (outer expectations)

* If ops sends a domain ActionIntent, AL must produce a normal **ActionOutcome** (EXECUTED/DENIED/FAILED) with `actor_principal` and `authz_policy_rev`.
* If ops changes execution posture (kill/drain), AL must:

  * make the change take effect **deterministically** (same inputs → same behavior), and
  * ensure future outcomes reflect that posture (e.g., DENIED with reason “kill_switch_active”).

---

## 17) J9 — AL ↔ Observability/Governance (operability + controls join)

This join exists because **Obs/Gov is not “a side system”** in your platform — it defines safe operation rules, correlation conventions, and “no silent mutation.”

### J9.1 AL → Observability: what AL must emit (minimum viable, production-shaped)

**A) Golden signals + AL-specific metrics**
AL is an always-on hot-path unit; it must emit:

* throughput (intents processed/sec)
* latency (p95 end-to-end intent→outcome emission)
* error rate (by class)
* saturation (queue depth/backlog/worker utilization)

Platform-specific “must haves” for AL:

* outcome counts by status (EXECUTED/DENIED/FAILED)
* denied-by-policy rate (by action_type/scope)
* retry rate (and “in-flight” count)
* external dependency latency (if any)
* consumer lag per EB partition (AL is an EB consumer)

**B) End-to-end trace propagation**
If an incoming intent has `trace_id/span_id`, AL must preserve it and create an “AL execution span” so you can reconstruct:
**event → decision → action → audit**.

**C) Correlation keys everywhere**
AL telemetry (logs/metrics/traces) must carry the applicable subset of:

* ContextPins (`run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash`, …)
* `event_id` (intent event)
* `idempotency_key` (semantic action identity)
* outcome ids / attempt number
* actor_principal
* policy revision used

### J9.2 AL → Governance: “changes and execution must be observable facts”

Two different “facts” must exist:

1. **Execution facts**: ActionOutcome events already fulfill “we did/didn’t do it,” but they must be fully attributable + policy-versioned.
2. **Change facts**: if AL behavior is changed (new allowlist policy rev, kill switch, drain), that activation must emit a governance fact (actor, scope, before/after refs, reason).

### J9.3 Governance/Obs → AL: what AL must accept as “control inputs”

AL should accept controls only via **explicit control surfaces**, never via hidden coupling.

Minimum control inputs for production:

* **policy profile revision** for action allowlists (versioned artifact; AL outcomes cite the revision used)
* **emergency controls**: kill switch / drain / safe-mode posture (explicit, scoped, governed)

> **Designer pin:** AL should *fail closed* if it cannot determine the active policy/control posture (e.g., can’t load policy rev). It must not execute “blind” in a policy vacuum. This matches your “safety toward fail-closed” posture across rails.

---

## 18) L4 — Governed change / safety loop

This is the production loop that keeps the platform safe **while still being operable**:

**Observability detects** → **Governance constrains** → **Run/Operate enacts** → **Everything records the change**.

### L4.1 The loop, concretely (what happens in production)

1. **Signals accumulate**

* AL metrics show rising failures/latency/backlog, or dependency latency spikes. 

2. **Obs/Gov evaluates corridor checks**

* “Are we healthy enough to act?”
* “Is lineage/PASS compliance intact?”
* “Are we within error budgets?”

3. **Constraints are made explicit**
   Two ways this can become “actionable constraints”:

* **Degrade Ladder** (capabilities mask / safe constraints posture) informs what DF is allowed to do, and must be recorded in provenance.
* **Run/Operate controls** enact kill/drain/policy rev changes (explicit governance facts).

4. **AL behavior changes without drift**

* If action types are disabled, AL returns **DENIED** with a stable reason (policy/kill/degrade), not silent drops.
* If drain is activated, AL stops taking new intents and finishes in-flight work, while still emitting outcomes for anything it handled.

5. **Governance fact trail exists**
   Every step that can affect outcomes is recorded as a durable governance fact: “policy rev X active,” “kill switch activated for scope S,” “drain started,” “rollback executed,” etc.

### L4.2 Why this loop is “drift killer”

* No one changes behavior by stealth (pinned rule).
* Changes are versioned artifacts (policy profiles), not random runtime state.
* You can reconstruct “what was in force” later because AL outcomes cite policy rev and Run/Operate preserved the artifacts.

---

## 19) P4 — Quarantine/remediation path (IG quarantine → review/release → reprocess)

Quarantine is explicitly **first-class**: anything rejected must produce a quarantine outcome with evidence pointers; no silent drops.

### P4.1 What can be quarantined in an AL-centric world

1. **ActionIntent quarantined at IG** (common)

* unjoinable (missing ContextPins / unknown run / run not READY)
* unauthorized producer/event_type/scope
* schema/version not admissible
* malformed envelope

2. **ActionOutcome quarantined at IG** (rare, severe)
   If AL outcomes get quarantined, it usually indicates:

* AL is producing non-canonical traffic
* AL’s producer identity mismatch
* policy profile inconsistency
  This should trigger L4 safety responses (drain/kill) because it breaks the audit story.

3. **Audit quarantine at DLA** (separate but related)
   DLA quarantines when provenance is incomplete; remediation is similar in spirit (inspect, correct via supersedes, never mutate).

### P4.2 The quarantine artifact trail (by-ref posture)

When IG quarantines, it must produce:

* a receipt with decision=QUARANTINE, reason taxonomy, policy rev
* evidence pointers to quarantined payload/evidence blob(s)
* optionally a digest of the candidate

Storage posture is already pinned in your deployment notes (object-store prefixes + optional indexes).

### P4.3 Release/reprocess is privileged and auditable (non-negotiable)

**Pinned:** reading quarantined payloads and releasing/reprocessing them is privileged and must emit an auditable governance fact.

So remediation is always:

1. **Inspect** (privileged read of evidence)
2. **Decide** (release, reject permanently, or reprocess with correction)
3. **Emit governance fact** (who/why/scope/what changed)
4. **Reprocess** through IG (never bypass)
5. **Obtain a new receipt** (ADMIT/DUPLICATE/QUARANTINE again)

### P4.4 The critical pin: what happens to event identity on reprocess?

To avoid drift, we pin this rule:

* If reprocessing **does not change bytes/meaning** (e.g., run became READY; policy updated to allow existing version), then **re-submit the same event** (same `event_id`) and IG will ADMIT/DUPLICATE deterministically.
* If remediation requires **any transformation** (schema fix, corrected fields, changed scope), then you admit a **new event_id**, and you must keep a traceable linkage (e.g., `parent_event_id` to the quarantined candidate + governance fact referencing both).

That’s how you preserve “no silent mutation” and keep audit coherent.

---

## 20) L5 — Quarantine triage loop

This is the ongoing operational loop that prevents quarantine from becoming a trash pile.

### L5.1 The loop (production narrative)

1. **Detect**: quarantine rate spikes (by producer/event_type/reason) — this is an Obs/Gov signal.
2. **Classify**: is it

   * policy misconfig (allowlist too strict)
   * schema/version evolution mismatch
   * run joinability issue (SR readiness/pins)
   * producer identity/auth mismatch (security)
   * malformed payload bug
3. **Choose remedy** (must be governed):

   * activate new policy rev (propose→approve→active; rollback path)
   * patch producer / redeploy (code promotion)
   * declare a reprocess/backfill window (explicit, scoped, auditable)
4. **Execute reprocess**:

   * release/reprocess quarantined items under controlled workflow
   * ensure receipts point to EB coordinates for admitted facts
5. **Validate**:

   * quarantine rate returns to baseline
   * DLA closure remains intact (no missing outcomes)
   * derived stores still obey monotonic watermark semantics (no lying about offsets)

### L5.2 AL-specific triage severity rules (worth pinning)

* **Quarantined ActionIntent**: usually routine triage (policy/joinability/schema).
* **Quarantined ActionOutcome**: **P0 incident** because it can break the platform’s “what actually happened” record; triggers L4 controls (drain/kill) until corrected.

### L5.3 What “done” looks like for quarantine triage

* Every quarantined item has an eventual resolution:

  * admitted as-is
  * admitted as corrected successor (with lineage)
  * rejected with explicit reason and governance record
* No “mystery disappearances.”

---

If you want to keep the expansion sequence tight: next we should expand **#19 and #20 specifically for AL’s two traffic types** (ActionIntent vs ActionOutcome) and pin the top 6 quarantine reason codes + the exact remediation choices that are allowed for each. That’s where production reality usually gets messy, and pinning it now prevents drift later.

---

Alright — expanding **#21–#24**, still keeping **AL opaque** and staying inside the pinned rails: **IG front door**, **EB replay truth**, **idempotency end-to-end**, **watermarks as the determinism hook**, **append-only audit**, **archive = continuation of facts**, and **“backfills are declared” via Run/Operate**. 

---

## 21) P5 — Replay/backfill path

**EB redelivery → AL dedupe → outcomes stable**

This path is about **operational reality**: consumers restart, offsets move, retention ends, archive continues, backfills happen — and none of that is allowed to create *new side effects* for the same semantic intent. 

### P5.1 Three kinds of “replay/backfill” AL must survive

1. **Normal redelivery** (at-least-once): same EB fact delivered again to AL. 
2. **Operational replay** (offset reset / new consumer group): AL is asked to “re-walk history” inside retention. 
3. **Long-horizon backfill** (beyond retention): replay from **archive**, which is pinned as the **continuation of the admitted fact stream**, not a different dataset. 

### P5.2 The invariant that makes P5 safe

**Designer pin:** Under any of the above, *the same semantic intent* must not produce a second side effect.
“Same semantic intent” is already pinned as **`(ContextPins, idempotency_key)`**. 

So AL must do two things **every time it sees an intent**:

* **Check the semantic ledger** for `(ContextPins, idempotency_key)`
* **Converge** to the existing canonical outcome if one exists (don’t re-execute) 

### P5.3 What “outcomes stable” means in practice

Because replay/backfill is common, “stable” must mean more than “we eventually got *an* outcome”:

**Designer pin:** Once AL emits an outcome for a semantic intent, AL must be able to **re-emit the canonical outcome byte-identically** on future duplicates/replays (including the original `ts_utc` it recorded).
That is implied by “immutable ActionOutcome history” + “duplicates re-emit canonical outcome.”

### P5.4 The “crash window” that P5 must close (the classic failure)

The dangerous window is:

> side effect executed ✅
> outcome not yet admitted to EB ❌
> AL restarts → sees intent again → must not execute twice

**Outer expectation (pin for AL’s design):** AL must have a durable record that it executed (or denied), *independent of whether EB publish succeeded*, so that replay causes **republish** not **re-execute**. This is exactly why AL is system-of-record for outcomes/attempt history. 

### P5.5 “Backfill must be declared” (and why that matters to AL)

Backfills/replays are not informal “developer resets”; they’re pinned as **operational acts** done via Run/Operate so they’re auditable and consistent. 

**Designer pin:** Any backfill that would cause AL to revisit old intents must be:

* explicitly declared (scope + time window + streams)
* executed under a controlled posture (often with kill/drain or capability masks)
* audited as a change event

This prevents accidental “re-drive actions” incidents. 

### P5.6 If you ever *intend* to re-execute, it must be explicit

Sometimes you really do want “do it again” (e.g., resend notification). In this platform, that must be explicit:

**Designer pin:** Re-execution requires minting a **new semantic intent identity**, i.e., a new `idempotency_key` (and/or a new intended scope) — otherwise it will (correctly) dedupe as the same action. 

---

## 22) L6 — Replay determinism loop

(the platform proves it is stable under replay)

This loop is the **proof obligation** your whole design is built around:

* **EB** is the replayable fact log (within retention; archive continues it). 
* **Watermark vectors** derived from EB offsets are the universal progress token (IEG graph_version / OFP input_basis). 
* **DLA** records “what we knew and why we acted” with by-ref provenance + hashes, and quarantines incomplete provenance. 
* **AL** ensures side effects don’t multiply under replay and outcomes remain stable. 

### L6.1 The loop, end-to-end

1. A set of admitted facts exists (EB + archive continuation). 
2. Consumers replay them (duplicates normal). 
3. IEG/OFP deterministically rebuild context and expose provenance tokens (`graph_version`, `input_basis`, snapshot hash). 
4. DF records decision provenance (bundle ref, degrade posture, feature snapshot hash, watermarks). 
5. AL receives the same ActionIntents again and **does not re-execute**; it re-emits canonical outcomes. 
6. DLA ingests idempotently and ends up with the *same* closure story for the same basis. 

### L6.2 The two replay modes you must not confuse

Production systems usually fail when they blur these:

**Mode A — “Audit/Training replay” (no side effects):**
Used by Offline Shadow / Model Factory / forensic replay; it must never cause actions. This mode consumes facts + provenance and rebuilds datasets/parity evidence. 

**Mode B — “Operational replay/backfill” (may touch AL):**
Used to recover from outages, missed offsets, schema fixes, quarantine releases. Here AL will see old intents again, and *must remain safe*. 

**Designer pin:** Run/Operate must make the mode explicit when initiating a replay/backfill window, and AL must be safe in Mode B by idempotency. 

### L6.3 What determinism means for AL specifically

For AL, determinism doesn’t mean “same wall clock time”; it means:

* Same semantic intent → **same terminal meaning** (EXECUTED/DENIED/FAILED-final)
* Same semantic intent → **no duplicate side effect**
* Same semantic intent → canonical outcome can be re-emitted consistently 

That’s the AL piece of “deterministic outcomes under replay in an at-least-once world.” 

---

## 23) J10 — External callbacks → (IG→EB) → AL

(optional async completion join)

This join exists only if you choose to support **asynchronous actions** where completion happens later (or is confirmed later) by an external system. It’s optional for v0, but production-ready platforms often need it. 

### J10.1 What J10 is *for*

Examples:

* AL initiates a step-up challenge; later receives “challenge passed/failed”
* AL initiates “block placed”; later receives “block confirmed” (or rejected)
* AL triggers a notification; later receives delivery receipts

### J10.2 How callbacks enter (non-negotiable boundary)

Callbacks are just **producer traffic**:

* They must enter via **IG** (authn/authz + admit/quarantine/duplicate + receipts)
* They must be **canonical-envelope conformant** when they’re bus-visible

### J10.3 Correlation is the whole join (what must be in the callback)

To be usable, a callback must correlate to the action it refers to, using at least one of:

* **`parent_event_id` = intent event_id**, *or*
* `(ContextPins, idempotency_key)` for the action, *or*
* an **effector_request_id** that AL emitted earlier and recorded in its attempt history

**Designer pin:** J10 is only safe if correlation is stable and deterministic; “search by time” is banned.

### J10.4 What AL does with callbacks (outer behaviour)

If you enable async actions, AL’s outward behaviour must remain append-only/immutable:

* AL does **not mutate** old outcomes.
* AL **appends** a new “closure outcome record” for the same semantic intent when the callback arrives (e.g., CONFIRMED / COMPLETED / REJECTED).
* Duplicates in callbacks are handled idempotently (same callback event_id → no double-apply).

> This keeps the platform consistent with “append-only + supersedes chains” style thinking, without turning normal async closure into “overwrite.” 

### J10.5 Orphan/malicious callbacks (production reality)

Sometimes callbacks arrive with no matching action (bad producer, wrong key, late events).

**Designer pin:** Orphan callbacks must **not** silently change state. Options that remain consistent with your rails:

* record an **orphan callback fact** for ops/governance investigation (telemetry / governance event), and/or
* quarantine upstream at IG via producer allowlist and schema/version controls (preferred)

But AL must never “guess the match.” 

### J10.6 v0 stance (keeps things tight)

**Designer pin:** v0 AL supports **bounded-time actions only**, so J10 can be disabled initially. When you later enable J10, you do it by explicitly declaring which action_types are async and what callback types correlate to them.

---

## 24) Forbidden edges

(explicit non-joins that are banned to prevent drift)

These are **hard bans** because they break truth ownership and replay safety. 

### F1 — AL ↔ Data Engine (direct)

AL must not read engine outputs, gates, or storage directly. Engine truth enters the platform via SR’s join surface and admitted traffic paths — AL acts only on intents/outcomes. 

### F2 — AL ↔ Scenario Runner (SR)

AL must not pick “current world/run,” check READY, or consult SR directly. That would create hidden coupling and violate the pinned “SR is readiness + join surface” rule. 

### F3 — AL → EB bypassing IG

AL is a producer like any other. If AL bypasses IG, you break the trust boundary, receipts, quarantine semantics, and audit determinism. 

### F4 — AL becomes decision authority

AL executes; DF decides. AL must not “decide to block anyway” or “change severity.” If AL needs to refuse, it does so only via **policy/authorization controls** and emits DENIED/FAILED outcomes. 

### F5 — AL writes labels or edits cases directly

Case Mgmt owns case timelines; Label Store owns labels (append-only, as-of). AL may emit outcomes that those planes consume, but AL never becomes their writer of truth. 

### Two additional “anti-drift” non-joins I’d also ban (designer pins)

* **AL ↔ OFP/IEG for “decisioning context”**: AL must not query feature/projection planes to decide whether to execute; DF already did that. (Otherwise AL becomes a second decision engine and replay determinism gets messy.) 
* **AL ↔ Registry for “what policy is active”**: AL should use a governed, deployed **action policy profile** (versioned) supplied via Run/Operate/Gov, not resolve registry bundles dynamically like DF. (Keeps truth ownership clean.) 

---

If you want to continue in the same structured way, the next useful move is: take **P5 + L6** and pin the **minimum retention horizon** for AL’s idempotency/outcome ledger (so you can safely replay from EB+archive without ever re-executing old intents). That one decision removes a lot of future ambiguity.

---

Yes — the **environment ladder** is *exactly* where these joins/paths/loops either stay clean… or drift into “it worked locally” fantasy.

Your ladder pin is explicit: **local/dev/prod must run the same platform graph and the same rails/join semantics; only the operational envelope may differ** (scale, retention/archive, security strictness, reliability, observability).
So what I have to say is: **every AL join/loop we listed must be “production-shaped” even in local**, with differences implemented via **profiles/policy revs**, not semantic shortcuts.

Below is how the ladder constrains each cluster of AL paths/joins/loops.

---

## 1) What must NOT change across environments for AL (non-drift invariants)

These must be identical in **meaning** everywhere:

* **Graph + trust boundaries:** intents/outcomes go through **IG→EB**, and AL is “only executor.”
* **Rails/join semantics:** canonical envelope, ContextPins discipline, idempotency `(ContextPins, idempotency_key)`, append-only history, quarantine posture, and replay/watermark truth remain the same.
* **Words mean the same thing:** “ADMITTED,” “READY,” “BACKFILL,” “ACTIVE,” etc. No “local-only meaning.”
* **No silent mutation:** environment differences must not be implemented as hidden behavior changes; changes must be explicit facts via control surfaces.

**Practical AL consequence:** even on a laptop, you still want AL behaving like an **always-on service consuming EB**, not a function call from DF. Local can *collapse deployment units* for convenience, but the unit roles and semantics stay.

---

## 2) What *is allowed* to differ (and how it touches AL joins/loops)

### A) Security strictness (biggest difference across ladder)

This affects J3/J4/J9 (manual + ops + governance controls) most.

* **Local:** permissive allowlists and dev credentials are OK, **but the mechanism must exist** (IG admission policy, AL allowlist policy, quarantine access controls).
* **Dev:** “real enough” authn/authz to catch issues (unauthorized producers, quarantine access, registry privileges). 
* **Prod:** strict access control + governed activation of policy changes.

**Pin for AL:** action allowlists are **policy config**, therefore versioned artifacts; AL outcomes/telemetry must cite the **policy revision used** (“what rules were in force?”).

---

### B) Retention + archive (directly hits P5 + L6)

* **Local:** short EB retention is fine.
* **Dev:** medium retention (integration realism).
* **Prod:** longer retention + **archive continuity** for long-horizon replay/investigation/training.

**But:** retention length can vary; **offset/watermark semantics may not.** 

**AL-specific implication:** AL’s idempotency/outcome truth must survive beyond “EB delivered it once.” In the mapping you pinned, AL persists idempotency+outcome history in an authoritative store (e.g., Postgres `actions`). That’s what makes P5/L6 safe in every env.

---

### C) Observability depth + corridor checks (hits J9 + L4)

* **Local:** “debug observability,” but still run the pipeline so the semantics match prod.
* **Dev:** dashboards/alerts closer to prod. 
* **Prod:** SLOs + corridor checks are meaningful and can gate proceed/degrade/halt.

**AL-specific:** local must still emit the **same golden signals** and AL-specific metrics (outcomes by status, retry rate, denied-by-policy rate, external dependency latency) because those feed Degrade/corridor checks and safe-change.

---

### D) Reliability posture (HA/backups) + scale (concurrency)

This changes *quantities*, not meaning.

* More partitions/consumers in dev/prod increases duplicate/race pressure. That’s good: it forces your **semantic idempotency** story to be real, not theoretical.
* Local can be single-broker; dev can be multi-broker; prod can be managed Kafka equivalents — but **IG↔EB “ADMITTED means durably appended”** must remain true.

---

## 3) Environment-ladder view of the specific AL joins/paths/loops

### P1 (automated hot path) + J2/J1/J5/J6/J7

* **Local:** run the whole path SR→Engine→IG/EB→DF→AL→DLA at small volume; effectors can be simulated, but still must accept an idempotency token and produce stable outcomes.
* **Dev:** validate concurrency/partitioning and schema evolution policies; ensure unauthorized producers/actions get quarantined/denied.
* **Prod:** strict allowlists + change control; outcomes must be auditable “facts,” not logs.

### P2 + J3 + J11 (manual case path + case timeline join)

* **Local:** you can use a thin UI/CLI, but it still emits ActionIntent through IG/EB and results show up as outcomes; don’t short-circuit.
* **Dev/Prod:** stronger principal identity and permission boundaries; quarantine access is privileged.

### P3 + J4 (ops intervention)

* **Local:** “ops controls” can be a CLI that emits governed control facts / profile activation, but still explicit.
* **Prod:** every outcome-affecting operational act must emit governance facts; no “SSH into box and toggle flag.”

### L4 (safe-change loop)

* **Local:** thresholds can be loose; sampling can be high; but degrade/control must be via explicit surfaces (DL mask, governed activations).
* **Prod:** corridor checks are hard gates for proceed/degrade/halt.

### P4/L5 (quarantine/remediation loop)

* **Local:** easier inspection and faster release, but still must create evidence pointers and record the release/reprocess as an explicit act (governance-style), not a silent mutation.
* **Dev/Prod:** stricter privileges and formal remediation; quarantine is a “real” operational process.

### P5/L6 (replay/backfill + determinism loop)

* **Local:** short retention means you’ll replay smaller windows; that’s fine — but you must still exercise duplicates/replays to prove idempotency is real.
* **Dev:** validate controlled backfills and schema changes end-to-end.
* **Prod:** archive + declared backfill operations; never silent overwrites of truth.

---

## 4) The “one-liner” rule for keeping AL honest across the ladder

If you implement **any** of these joins/loops differently in local than in prod, you’ve violated the ladder pin and built “three different platforms.”

So the correct pattern is:

* same code + same rails
* environment differences expressed via **profiles + versioned policy config revs** (not “if prod”)
* and every outcome-affecting change is a **governance fact** (especially in dev/prod).

---

If you want, I’ll now translate this into an **AL-focused environment ladder checklist**: “what must exist in local/dev/prod for each join/loop (P1–P5, L1–L6)”

---

Yep — before we “open” AL, you want two things in your head:

1. **AL’s deployment shape is fixed (always-on hot-path service)**, even if local collapses units.
2. **Environment differences are profiles** (operational envelope), not semantic forks.

Below are the **environment profile knobs** I want you to have ready for AL, plus a few “deployment-direction” pins that prevent drift.

---

## A. The profile model you should assume for AL

### 1) Split config into two buckets (this is key)

* **Wiring config (non-semantic):** endpoints, ports, resource limits, timeouts.
* **Policy config (outcome-affecting):** admission/allowlists, action allowlists, corridor thresholds, required gates, retention/backfill rules.

Policy config must be **versioned**, activated via governed change, and every runtime unit should report which **policy rev** it used.

### 2) Environment ladder = profile strictness, not platform meaning

Local/dev/prod keep identical rails/join semantics; they differ only in scale/security/retention/reliability/observability depth.

---

## B. AL environment knobs (what you’ll actually “turn”)

### 1) AL Policy Profile knobs (outcome-affecting)

These are the knobs that **change what AL is allowed to do** and therefore must be governed + auditable.

* **Action allowlists**
  `(actor_principal, origin, action_type, scope)` allow/deny rules; default deny.
* **Execution safety posture**
  kill switch (global or scoped), “drain” mode, and per-action “enabled/disabled” toggles (as policy revs).
* **Async actions enablement** (if/when you allow callbacks)
  which `action_type`s are async; which callback event_types/producers are acceptable (otherwise quarantine).
* **Quarantine thresholds + reason taxonomy**
  when to quarantine vs fail/deny, and which reasons are “P0” (e.g., quarantined outcomes).
* **Required correlation / provenance minima**
  what AL refuses if missing (ContextPins discipline, trace propagation, decision/case refs).

### 2) AL Wiring Profile knobs (non-semantic)

These are the knobs you can tune per env without changing meaning.

* **Connectivity**: EB brokers, IG endpoint, DB endpoint, object store endpoint, OTel collector endpoint.
* **Consumer posture**: consumer group id, topic names, commit/checkpoint cadence, batch sizes.
* **Concurrency/throughput**: worker counts, max in-flight, per-action rate limits (rate limit *can* be wiring if it’s purely resource protection; if it changes “allowed to execute,” treat it as policy).
* **External effector wiring**: effector endpoints, timeouts, retry/backoff, circuit breakers.
* **DB tuning**: pool sizes, transaction timeouts.

### 3) Observability knobs (depth differs by env; semantics don’t)

* **Metrics/trace/log export on/off and sampling rate** (local high, prod sampled), but **propagation semantics identical**.
* **AL required metrics** (must exist in all envs): outcome counts by status, denied-by-policy rate, retry rate, external dependency latency, consumer lag. 

### 4) Retention / archive / backfill knobs (mostly global, but AL must respect them)

* EB retention length differs by env; semantics of offsets/watermarks/replay do not.
* Backfills are **declared operations**; never silent overwrites of truth.

---

## C. Environment defaults you should expect for AL

### Local

* permissive policy revs (dev principals), short retention, debug observability, but **same IG/EB semantics** and AL still behaves as an always-on consumer.

### Dev

* “real enough” authn/authz + quarantine privileges, medium retention, dashboards/alerts, end-to-end flows exercised (including backfills and schema evolution).

### Prod

* strict allowlists + change control, longer retention + archive continuity, corridor checks meaningful, every outcome-affecting change emits governance facts.

---

## D. Extra deployment-direction pins for AL (so “opening the box” doesn’t surprise you)

These are the “don’t forget this later” items that fall out of your deployment notes:

1. **AL is a pinned always-on service unit** (hot path). Local may collapse units, but roles don’t change.
2. **Run/Operate owns lifecycle ops** (start/stop/drain/backfill/retention) and must not introduce hidden nondeterminism; any outcome-affecting operational act must be auditable.
3. **“Production-shaped local” is expected**: EB + object store + DB + OTel stack, so AL is tested under real at-least-once + durable dependencies from day one.
4. **Policy/config promotion is a first-class lane** (like code and bundles): propose → validate → activate, and components report policy revs in receipts/outcomes.

---

If you keep just one mental model: **AL is “code artifact X + wiring profile Y + policy rev Z,” and promotion is choosing new Y/Z, not rewriting behavior.**

---

Absolutely. Here’s the **outer-network anchor** for **Actions Layer (AL)** as we’ve exposed it in this chat — the set of **non-negotiable boundaries, edges, and loop meanings** we must preserve while we start illuminating AL’s internals.

Everything below is constrained by (a) your **platform blueprint pins**, (b) the **canonical event envelope boundary**, and (c) the **environment ladder** rule (“same graph + semantics everywhere; only operational envelope differs”).   

---

## AL’s outer truth and authority boundary

**Pinned role:** AL is the platform’s **only side-effect executor**. Everyone else (DF, Case, Ops) only **requests** actions; AL alone produces the **system-of-record** truth of what happened via **immutable ActionOutcome history**. 

**Pinned execution safety:** AL must be **effectively-once** under at-least-once delivery using uniqueness scope **`(ContextPins, idempotency_key)`**; duplicates must never re-execute. 

---

## The mandatory edges touching AL (no drift allowed)

### Ingress (who can request actions)

All action requests enter as **ActionIntent traffic** through **IG → EB → AL** (no bypass). 

* **DF → IG → EB → AL** (automated) 
* **Case Workbench → IG → EB → AL** (manual) 
* **Ops/Run-Operate → IG → EB → AL** (operational) 

**Boundary shape:** any bus-visible intent is a **Canonical Event Envelope** event (required `event_id, event_type, ts_utc, manifest_fingerprint`, plus ContextPins when applicable). 

### Egress (what AL emits)

AL emits **ActionOutcome traffic** through **AL → IG → EB**, and outcomes are the durable facts used by audit and other consumers. 

* **AL → IG → EB → DLA** (audit closure) 
* **AL outcomes → Case timelines** (evidence consumption; by-ref posture) 
* **Optional:** **AL outcomes → IEG/OFP/DF** as “actions-as-facts” (feedback into context) 

### Side-effect boundary

**AL → External Effectors** is the only place side effects occur. 
Optional completion path (only if/when we enable async actions): **Effectors → IG → EB → AL** callbacks. 

---

## The required “meaning” of each join (so internals don’t accidentally change semantics)

### IG is always the trust boundary

* Every intent/outcome is subject to **ADMIT / DUPLICATE / QUARANTINE** decisions (with receipts). 
* EB remains **append/replay truth** (partition/offset basis); no validation transforms in EB. 

### Two identity domains must remain distinct

* `event_id` (envelope): transport/boundary dedupe, correlation. 
* `(ContextPins, idempotency_key)` (payload semantics): AL’s execution identity and effectively-once guarantee. 

### Outcomes must never be silent or mutable

For every intent AL handles, it must yield a visible outcome path (at minimum EXECUTED / DENIED / FAILED). Outcomes are **immutable**, history is append-only. 

### Audit closure is a first-class loop

DLA is the flight recorder: it must be able to join “decision → intent → outcome” into an immutable narrative under replay. 

---

## The production loops involving AL (these must remain true)

### L1 Decision → Action → Audit closure

DF produces intents; AL executes/denies/fails; DLA records closure. 

### L2 Action outcomes feed future context (optional but production-common)

If enabled, outcomes become admitted facts that update IEG/OFP and therefore shape future DF decisions. 

### L3 Human truth loop

Outcomes/evidence → Case → Label Store → Offline Shadow/Model Factory/Registry → DF → new intents/actions. 

### L4 Governed change / safety loop

AL emits observability; Run/Operate/Gov activates explicit controls (policy revs, kill/drain, etc.); effects on outcomes are auditable facts, not hidden toggles.  

### L5 Quarantine triage loop

Quarantined intents/outcomes are remediated via privileged, auditable release/reprocess — never silent mutation. 

### L6 Replay determinism loop

Replays/backfills/redeliveries must not produce duplicate side effects; duplicates converge to canonical outcomes for the same semantic key. 

---

## The explicit “do not create these edges” bans

These are **forbidden** as we illuminate internals:

* **AL ↔ Data Engine** direct reads / gate checks (AL must not become an engine consumer). 
* **AL ↔ SR** for readiness/world selection (AL acts only on pins carried by intents). 
* **AL → EB bypassing IG** (breaks trust boundary + receipts). 
* **AL as a decider** (decision authority stays in DF; AL only executes/refuses via policy). 
* **AL writes labels or cases** (Label Store and Case Mgmt retain truth ownership). 

---

## Environment ladder drift guardrail for AL

**Pinned rule:** local/dev/prod must preserve the **same graph and semantics**; only operational envelope differs (scale, security strictness, retention/archive, observability depth). 

So: **no “local shortcuts”** like DF calling AL directly, skipping IG, disabling idempotency, or mutating outcomes “because it’s dev.”

---

## Drift check before we go inside

As we start illuminating AL internals, we reject any internal design move that would:

1. Change the ingress/egress edges (must remain IG→EB mediated). 
2. Alter identity semantics (must preserve `(ContextPins, idempotency_key)` uniqueness). 
3. Permit silent drop or mutable outcomes (must remain immutable, append-only). 
4. Introduce a forbidden dependency edge (Engine/SR/EB-bypass/decisioning/labels/cases). 
5. Create an environment-specific semantic fork. 

---

Yes — one level deeper, **AL’s internal network** naturally splits into a small set of **internal subnetworks** (logical modules) that collectively implement the *outer pins* we just anchored (IG/EB mediated ingress/egress, semantic idempotency, authz choke point, immutable outcomes, audit joinability, replay safety).

Below are the **first-layer opaque boxes** I’d pin for AL. Keep them opaque for now; each is a “subnetwork” we’ll later open only when we’re ready.

---

## AL internal subnetworks (v0 set)

### 1) Intake and Normalization

**Purpose:** Turn “admitted ActionIntent traffic from EB” into a normalized internal intent unit.
**Inputs:** EB-delivered ActionIntent events (enveloped).
**Outputs:** `NormalizedIntent` (validated envelope fields present, required join keys extracted, payload parsed).
**Also owns:** basic sanity classification (unknown event_type → route to “handled failure outcome” path, not crash).

---

### 2) Policy and Control Plane Adapter

**Purpose:** Provide *current, explicit* execution posture and authorization rules to the rest of AL.
**Inputs:** policy profile revision activations, kill/drain signals, scope controls (from Run/Operate / Gov surfaces).
**Outputs:** `ActivePolicySnapshot` used by authz + safety checks, plus “execution posture” flags (normal / drain / kill-by-scope).
**Key point:** This box is how we ensure environment ladder differences are **profiles**, not semantic forks.

---

### 3) Authorization Gate

**Purpose:** The platform’s **side-effect permission choke point**.
**Inputs:** `NormalizedIntent` + `ActivePolicySnapshot`.
**Outputs:** either `AuthorizedIntent` *or* a terminal decision to produce a **DENIED** outcome (no execution).
**Owns:** allowlists keyed by `(actor_principal, origin, action_type, scope)` and policy revision stamping.

---

### 4) Idempotency and Outcome Ledger

**Purpose:** Enforce **effectively-once** semantics under at-least-once delivery and crashes.
**Inputs:** `AuthorizedIntent` (semantic key = `(ContextPins, idempotency_key)`), plus callback correlations if enabled later.
**Outputs:** one of:

* `ExecutePermit` (first time / safe to attempt)
* `DuplicateHit` (canonical outcome already known; re-emit it)
* `InFlightState` (already being attempted; decide how to respond deterministically)

**Owns:** durable attempt history + canonical-outcome selection rules + crash-window safety.

---

### 5) Execution Orchestrator

**Purpose:** Run the action attempt lifecycle without leaking side-effect hazards.
**Inputs:** `ExecutePermit` + intent details + policy posture.
**Outputs:** `ExecutionResult` (executed / failed + structured reason / evidence refs).
**Owns:** retry posture (if any), timeouts, circuit-breaking posture, attempt numbering, and safe coordination with the ledger (so “executed but not published” never causes double execution).

---

### 6) Effector Adapters

**Purpose:** The boundary to “the world” (your closed-world effectors or real integrations later).
**Inputs:** executor commands from the orchestrator, plus **external idempotency token** derived from the semantic key.
**Outputs:** effector acknowledgements / error categories / reference ids (by-ref evidence).

**Key point:** This box is where “execute twice is dangerous” is managed—so it must accept idempotency tokens and return stable references.

---

### 7) Outcome Assembly and Publisher

**Purpose:** Convert ledger/orchestrator results into immutable **ActionOutcome traffic** and get it admitted.
**Inputs:** `DuplicateHit` (canonical outcome), or `ExecutionResult`, plus envelope/context pins.
**Outputs:** ActionOutcome → IG submission, plus IG receipt handling (ADMIT / DUPLICATE / QUARANTINE).
**Owns:** canonical envelope formation, immutability discipline, publish retries that **never re-execute**.

---

### 8) Observability and Governance Hooks

**Purpose:** Make AL operable and auditable without changing semantics.
**Inputs:** events and state transitions from all other subnetworks.
**Outputs:** metrics/traces/logs with correlation keys, and governance-visible “change facts” for policy/control activations.
**Owns:** consistent correlation IDs (`event_id`, semantic key, actor_principal, policy_rev, attempt_no) on every signal.

---

## Optional subnetworks (enable later if/when needed)

### 9) Async Callback Intake and Correlator (J10 support)

**Purpose:** If some actions complete later, ingest callback events, correlate them to the semantic key, and append closure outcomes without mutation.
**Inputs:** callback events admitted via IG/EB.
**Outputs:** appended closure outcomes + audit-friendly linkage.

### 10) Quarantine/Remediation Surface (narrow, but production-real)

**Purpose:** Provide a controlled way to observe and remediate:

* quarantined ActionIntents (upstream)
* quarantined ActionOutcomes (rare, severe)
* orphan callbacks
  **Outputs:** governance-tracked release/reprocess directives (still routed through IG).

---

## Internal wiring (opaque-box graph)

```text
[1 Intake/Normalize]
        |
        v
[2 Policy/Control] ---> (feeds) ---> [3 AuthZ Gate]
                                |
                                v
                      [4 Idempotency + Ledger]
                         |             \
              DuplicateHit|              \ ExecutePermit
                         v               v
                [7 Outcome Publish]   [5 Orchestrator] ---> [6 Effector Adapters]
                         ^                 |
                         |                 v
                         +--------- [7 Outcome Publish]  (outcome from result)
                         
(8 Observability/Gov hooks tap every box)
(9 Async callbacks optionally feed into 1/4/7)
(10 Quarantine surface interacts with 1/7 + governance)
```

---

## Why this is the right “first layer”

* It’s **minimal** (enough to cover every pinned outer obligation) without exploding into dozens of micro-modules.
* Each box corresponds to a **non-negotiable platform concern**: intake correctness, explicit control posture, authz choke point, semantic idempotency, safe execution, immutable publication, audit-grade observability.
* It preserves the outer network: **all ingress/egress stays IG/EB mediated**, and AL stays the only executor.

---

Yep. With AL’s **internal subnetworks still opaque**, the production-ready **internal network** is basically a set of **joins (edges)** between those boxes, plus a handful of **canonical internal paths** and **feedback loops** that make AL safe under at-least-once delivery, retries, crashes, and governed change (all required by the outer pins). 

I’ll use this legend (the opaque internal nodes we already named):

* **N1** Intake & Normalize
* **N2** Policy & Control Plane Adapter
* **N3** Authorization Gate
* **N4** Idempotency & Outcome Ledger
* **N5** Execution Orchestrator
* **N6** Effector Adapters
* **N7** Outcome Assembly & Publisher
* **N8** Observability & Governance Hooks
* **N9** Async Callback Intake & Correlator (optional)
* **N10** Quarantine/Remediation Surface (optional)

---

## A) Internal joins (edges) inside AL

### Core data-plane joins (hot path)

**J1 — N1 → N3 (NormalizedIntent feed)**
What crosses: `NormalizedIntent` (envelope fields + extracted ContextPins + parsed payload + correlation keys).

**J2 — N2 → N3 (AuthZ policy snapshot feed)**
What crosses: `ActivePolicySnapshot` (allowlists, kill/drain posture, policy_rev).

**J3 — N2 → N5 (Execution posture feed)**
What crosses: `ExecutionPosture` (enabled/disabled action types, caps, drain/kill scopes).

**J4 — N3 → N4 (AuthorizedIntent feed)**
What crosses: `AuthorizedIntent` (plus stamped `policy_rev`).

**J5 — N3 → N7 (Denied short-circuit)**
What crosses: `DeniedDecision` (reason category + `policy_rev`) → used to construct a DENIED ActionOutcome.

**J6 — N4 → N5 (ExecutePermit)**
What crosses: `ExecutePermit` (attempt number + “safe to attempt” token).

**J7 — N4 → N7 (DuplicateHit / CanonicalOutcome)**
What crosses: either `CanonicalOutcome` (already known terminal/most-recent outcome) or “no-op duplicate” decision.

> **Designer pin for duplicates at internal level:** AL produces **one** canonical outcome history per semantic key; duplicate envelope events do **not** obligate AL to emit additional outcomes if a canonical one already exists (it may re-emit it, but it won’t create “more truth”). 

**J8 — N5 → N6 (ExecutionCommand)**
What crosses: `ExecutionCommand` + **external idempotency token** derived from `(ContextPins, idempotency_key)`.

**J9 — N6 → N5 (ExecutionReceipt)**
What crosses: `ExecutionReceipt` (success/failure category + effector refs/digests).

**J10 — N5 → N4 (AttemptRecord append)**
What crosses: `AttemptRecord` (attempt start/finish, retryability, evidence refs).

**J11 — N5 → N7 (OutcomeDraft)**
What crosses: `OutcomeDraft` (EXECUTED/FAILED + reasons + evidence refs + intent linkage).

**J12 — N7 ↔ N4 (Outbox/Publish-state join)**
What crosses:

* `OutcomeToPublish` (from ledger/orchestrator)
* `PublishReceipt` (IG ADMIT/DUPLICATE/QUARANTINE + bus coordinates when available)
  Recorded back into the ledger so “executed-but-not-published” never causes re-execution. 

### Cross-cutting observability joins

**J13 — (N1..N7) → N8 (Telemetry tap)**
What crosses: `TelemetryEvent` (metrics/traces/logs) with correlation keys (`event_id`, semantic key, actor_principal, policy_rev, attempt_no).

> **Anti-drift pin:** N8 is a **tap**, not a control input. Controls come through N2, not by “observability reaching in.” 

### Optional joins (only if enabled)

**J14 — N9 → N1 (Callback normalize) OR N9 → N4 (Direct correlate)**
What crosses: `NormalizedCallback` / `CorrelationKey` (intent linkage by semantic key or effector_request_id).

**J15 — N9 → N7 (Closure outcome append)**
What crosses: `ClosureOutcomeDraft` (append-only closure record; no mutation). 

**J16 — N10 ↔ (N1/N7/N2) (Remediation interactions)**
What crosses: quarantine inspection directives, release/reprocess triggers, and policy-change requests (all governed externally, but N10 is the internal “surface” to interact with that workflow).

---

## B) Internal paths (end-to-end sequences inside AL)

### P1 — “New intent, execute successfully” (canonical hot path)

`N1 → N3 → N4 → N5 → N6 → N5 → N4 → N7 → (publish)`

### P2 — “Denied by policy” (no execution)

`N1 → N3 → N7 → (publish DENIED)`
(N4/N5/N6 are bypassed.)

### P3 — “Duplicate intent, canonical outcome already known”

`N1 → N3 → N4 → N7 → (re-emit canonical outcome OR no-op)`
(never executes again)

### P4 — “Duplicate arrives while an attempt is in-flight”

`N1 → N3 → N4 → (in-flight handling)`
Production-valid options the ledger can choose (we’ll pick one later when we open N4):

* **P4a:** do nothing (original attempt will emit the outcome)
* **P4b:** re-emit the latest known non-terminal record (if you allow such records)
* **P4c:** re-emit canonical terminal if already determined
  The key is: **no second execution attempt** is started.

### P5 — “Execution fails (retryable)”

`N1 → N3 → N4 → N5 → N6 → N5 → N4 (record retryable failure) → (later) N5 retries → … → N7 publishes final outcome`

### P6 — “Outcome publish fails, but execution already happened” (outbox path)

`N5/N4 create stable outcome → N7 publish attempt fails → N7 ↔ N4 persists “needs republish” → N7 retries publish`
Crucial property: publish retry never calls back into N5/N6 to re-execute. 

### P7 — “Drain/kill posture active”

`N2 posture update → affects N3 and N5`

* new intents may route to DENIED (kill) or be paused (drain) while in-flight completes, but outcomes remain emitted for anything AL handles.

### P8 — “Crash/restart recovery”

On startup:
`N2 loads active policy posture → N4 loads in-flight/outbox state → N7 republishes any pending outcomes → N5 resumes/cleans up in-flight attempts safely`
(Ensures replay doesn’t create double side effects.) 

### P9 — “Async completion via callback” (optional)

`N9 → N4 correlate → N7 append closure outcome → publish`
Append-only closure; no mutation of prior outcomes. 

### P10 — “Quarantine remediation touchpoint” (optional)

`N10 inspects quarantine evidence → triggers governed release/reprocess externally → re-enters AL through normal intake paths`
(AL never bypasses IG/EB even for remediation.)

---

## C) Internal loops (production feedback cycles)

### L1 — Execution retry loop (bounded)

`N5 ↔ N6 ↔ N4`
Attempt → failure classified retryable → retry scheduling → next attempt.
(Guardrails: caps, backoff, terminalization rules.)

### L2 — Publish retry / outbox loop

`N7 ↔ N4`
Outcome exists → publish attempt → receipt captured → if not admitted, retry publish until ADMIT/DUPLICATE or terminal QUARANTINE incident.

### L3 — Duplicate suppression loop (at-least-once reality)

Repeated deliveries cause repeated passes through:
`N1 → N3 → N4 → (N7 optional)`
But semantic ledger prevents re-execution.

### L4 — Governed change loop (inside AL boundary)

`(control inputs) → N2 → (updates) N3/N5`
Policy revs / kill/drain change the behavior of authorization/execution *without changing code semantics* across environments. 

### L5 — Backpressure / lag safety loop

`N8 observes lag/errors → external Run/Operate/Gov acts → N2 posture updates → N5 caps/drain`
(Internal part is N2 driving posture; the “decision” to change is outside AL, per pinned governance loop.) 

### L6 — Async closure loop (optional)

`N6 emits callback → (via IG/EB) → N9 → N4/N7`
Closure events append the action history safely.

### L7 — Quarantine triage loop (optional)

`N7 sees QUARANTINE (esp. outcomes) → N8 flags incident → external triage → policy/producer fixes → reprocess → intake`
(AL’s internal portion is detection + surfacing; remediation is governed outside.)

---

## D) Internal non-joins (useful drift guards)

These are “don’t accidentally wire it this way” constraints *inside* AL:

* **N7 never triggers N5/N6** (publisher must not cause execution).
* **N8 never controls N3/N5 directly** (observability is not a control plane).
* **N1 does not decide; N3 decides authorization; N4 decides idempotency; N5 executes.**
  Keeps authority boundaries crisp.

---

Locked. We’ll illuminate **internal joins J1–J4** in a way that **cannot drift** from the outer network boundary we pinned (IG/EB mediated traffic, AL as sole executor, semantic idempotency, immutable outcomes, governed controls). I’m going to **declare** what each join *means*, what is allowed to cross it, and what is explicitly *out of bounds* for that join.

I’ll keep subnetworks opaque (N1..N4), but the **join surfaces and invariants** below are now designer-authoritative.

---

# J1 — N1 → N3

## NormalizedIntent feed

### What J1 is (purpose)

J1 is the **“make intents safe to reason about”** edge. N1 takes an admitted ActionIntent event delivered from EB and emits a **normalized internal unit** to the AuthZ gate (N3).

### What J1 is NOT allowed to do (boundary enforcement)

J1 is **not** allowed to:

* make authorization decisions (no allow/deny here)
* make idempotency decisions (no “duplicate” logic here)
* consult external systems (no policy store, no ledger, no effectors)

J1 may only **parse, normalize, classify**, and attach correlation.

### What crosses J1: `NormalizedIntent`

Think of `NormalizedIntent` as: *“everything we need to evaluate policy and later dedupe/execute — but with no decisions applied.”*

Minimum fields carried:

**A) Envelope identity + correlation**

* `intent_event_id` (envelope `event_id`)
* `event_type` (must be ActionIntent class)
* `ts_utc` (intent emission time)
* `producer` / `origin_producer` (if present)
* `manifest_fingerprint` (required)
* `trace_id` / `span_id` (if present)

**B) Join pins (ContextPins)**

* `run_id`, `scenario_id`, `parameter_hash`, `seed` (when present)
* plus any environment pin you’ve standardized (if any)

**C) Semantic intent payload (what the action *is*)**

* `idempotency_key` (the semantic action key component)
* `action_type`
* `target_ref` (what it applies to)
* `scope` / `target_scope` (where/what domain scope it affects)
* `actor_principal`
* `origin` (df | case_workbench | ops)
* `rationale_ref` (decision_id / case_id / evidence pointer)

**D) Derived, deterministic helpers (no decisions)**

* `semantic_key = (ContextPins, idempotency_key)` if computable
* `intent_fingerprint` (digest of canonicalized intent payload fields)
* `delivery_basis` (optional but useful): `(stream, partition, offset)` for observability/debug only

### J1 classification outcomes (how errors are handled)

J1 must *not* drop events. But it also must not send garbage into AuthZ.

So J1 has exactly two “internal routing results”:

1. **`NormalizedIntent` → N3** (J1 proper)
2. **`NormalizationFailure` → (not J1; goes to N7 later)**

   * reason examples: missing required fields, unserializable payload, unknown/invalid schema version

**Designer decision:**
If `actor_principal` or `idempotency_key` is missing, that’s a **NormalizationFailure** (fail closed). We do *not* “guess,” and we do *not* attempt execution. The failure path later produces a FAILED outcome (no side effect).

---

# J2 — N2 → N3

## AuthZ policy snapshot feed

### What J2 is (purpose)

J2 provides N3 with an **explicit policy snapshot** so authorization is:

* deterministic at evaluation time
* attributable (you can say *which* policy revision produced the decision)
* safe under policy refreshes

### What J2 is NOT allowed to do

* It does not depend on DF/IEG/OFP features (“AL must not become a second decider”).
* It does not depend on SR/Engine.
* It does not make per-intent decisions; it only supplies the **policy state**.

### What crosses J2: `ActivePolicySnapshot`

Minimum contents:

**A) Policy identity**

* `policy_id`
* `policy_rev`
* `policy_digest` (hash of policy content)
* `effective_from_utc` (optional) and `loaded_at_utc`

**B) Authorization rules**

* allow/deny rules keyed by `(actor_principal, origin, action_type, scope)`
* optionally rule metadata: `rule_id`, `rule_priority`, `match_explain` flags

**C) Safety controls that behave like authorization**

* **kill switch** scopes/action_types (hard deny)
* “capabilities mask” / disabled actions (hard deny or forced-fail, but must be explicit)

**D) Required intent minima**

* which fields must be present to even evaluate (usually: actor_principal, action_type, scope, semantic_key)

### Fail-closed behavior when policy is unavailable

**Designer decision (authoritative):**
If N3 cannot obtain an `ActivePolicySnapshot`, N3 must **not authorize**. The action must not execute. The handling is:

* produce a **FAILED** outcome with reason category `POLICY_STATE_UNAVAILABLE`, **retryable=true**
* (never DENIED, because denial implies a stable policy decision; this is an operational inability)

This preserves safety and avoids “permanent denial” due to transient config store issues.

---

# J3 — N2 → N5

## Execution posture feed

### What J3 is (purpose)

J3 supplies the Execution Orchestrator (N5) with the **current execution posture**: *how to execute safely* and *what execution is currently permitted operationally* (drain, caps, etc.).

### What J3 is NOT allowed to do

* It does not authorize *who* may do what (that’s J2+N3).
* It does not decide idempotency (that’s N4).
* It does not bypass governance; posture changes must be traceable as governed activations.

### What crosses J3: `ExecutionPostureSnapshot`

Minimum contents:

**A) Snapshot identity**

* `exec_profile_id`
* `exec_profile_rev`
* `exec_profile_digest`
* `loaded_at_utc`

**B) Global posture flags**

* `drain_mode` (do not start new execution attempts)
* `safe_mode` (tight caps, conservative retries)
* per-scope or per-action `disabled` flags (if you centralize them here)

**C) Per-action execution constraints**
For each `action_type` (or action family):

* `enabled` boolean (operational enablement)
* `max_attempts`, `retry_backoff_policy`, `retryable_error_categories`
* `timeout_ms`
* `max_concurrency` / `rate_limit`
* `effector_adapter_id` (which adapter to use)
* `requires_external_idempotency` (must supply token to effector)

### Inconsistency rule between J2 and J3 (drift guard)

Sometimes policy says “allowed” but posture says “disabled” (maintenance, outage).

**Designer decision:** fail closed and be explicit:

* If **J2 allows** but **J3 disables**, N5 must not execute and the system must produce a **FAILED** outcome with reason `EXECUTION_DISABLED_BY_POSTURE`, retryable per posture.
* We do *not* silently “treat as denied,” because it’s operational, not authorization.

This keeps “who is allowed” separate from “can we safely do it right now.”

---

# J4 — N3 → N4

## AuthorizedIntent feed

### What J4 is (purpose)

J4 hands the idempotency ledger (N4) an intent that is:

* normalized (J1)
* authorized (J2 + N3 decision)
* stamped with policy provenance

N4 uses J4 to enforce: **same semantic key ⇒ no re-execution**.

### What J4 is NOT allowed to do

* It must not call effectors.
* It must not “start attempts.”
* It must not alter the semantic identity (no rewriting idempotency_key or ContextPins).

### What crosses J4: `AuthorizedIntent`

Minimum contents:

**A) Semantic identity**

* `semantic_key = (ContextPins, idempotency_key)` **(mandatory for J4)**
* `intent_fingerprint` (digest of canonical intent details)

**B) Intent details needed to produce outcomes deterministically**

* `action_type`
* `target_ref`
* `scope`
* `actor_principal`
* `origin`
* `rationale_ref` (+ decision_ref/case_ref when present)

**C) Correlation**

* `intent_event_id` (envelope event_id)
* optional `delivery_basis` (partition/offset) for debugging

**D) Authorization provenance**

* `authz_decision = ALLOW`
* `policy_id`, `policy_rev`, `policy_digest`
* optional: `matched_rule_id` / explain metadata

### Collision detection (critical production safeguard)

**Designer decision:** N4 must treat `(semantic_key, intent_fingerprint)` as a consistency check.

* If N4 has never seen `semantic_key`: store `intent_fingerprint` as the canonical fingerprint.
* If N4 sees the same `semantic_key` again:

  * if fingerprint matches → it’s a true duplicate
  * if fingerprint differs → **KEY_COLLISION / CONFLICT** (this is unsafe)

Conflict handling must be fail-closed:

* **do not execute**
* produce a FAILED outcome with reason `IDEMPOTENCY_KEY_CONFLICT`
* elevate to ops/governance signal (because it indicates DF/UI minted a bad idempotency key)

This prevents “two different actions accidentally dedupe into one.”

---

## Summary: the four joins in one line each (to prevent drift)

* **J1:** parse + normalize ActionIntent into `NormalizedIntent` (no decisions)
* **J2:** supply `ActivePolicySnapshot` to make authz deterministic + attributable
* **J3:** supply `ExecutionPostureSnapshot` to constrain safe execution operationally
* **J4:** send `AuthorizedIntent` (with semantic_key + policy stamps + fingerprint) into the idempotency ledger

---

## What we should illuminate next (naturally follows J1–J4)

Once J1–J4 are pinned, the next “danger triangle” is **N4 ↔ N5 ↔ N7** (execute-permit, attempt recording, publish/outbox) because that’s where double-exec and “executed-but-not-published” failures live.

But we’re good: J1–J4 are now nailed down in meaning, boundaries, and failure posture.

---

Great — we’ll illuminate **internal joins J5–J8** with the same discipline as J1–J4: **what the join means, what may cross, what’s forbidden, and the fail-closed rules**. I’ll also use design authority to **correct anything that would drift** from the outer boundary pins (effectively-once, immutable outcomes, IG/EB mediation, governance). 

I’m keeping the subnetworks opaque:

* **N3** AuthZ Gate
* **N4** Idempotency & Outcome Ledger
* **N5** Execution Orchestrator
* **N6** Effector Adapters
* **N7** Outcome Assembly & Publisher

---

# J5 — N3 → N7

## Denied short-circuit (bypass execution, not truth)

### What J5 is (purpose)

J5 is the “**no side-effect**” path: AuthZ concludes *execution must not happen*, and we immediately move to producing a **DENIED** outcome.

### What J5 is NOT allowed to do (boundary enforcement)

J5 must not:

* trigger N5/N6 (no execution)
* “decide idempotency” (that remains ledger-owned)
* invent a new outcome identity per duplicate delivery

**Designer correction (important):**
“Denied short-circuit” does **not** mean “bypass the ledger.” It only bypasses **execution**. Denials must still be **canonicalized** under the semantic key so duplicates don’t mint multiple denied outcomes. 

### What crosses J5: `DeniedDecision`

Minimum contents:

**A) Semantic identity**

* `semantic_key = (ContextPins, idempotency_key)` (mandatory)
* `intent_fingerprint` (canonical digest of intent fields)

**B) Correlation**

* `intent_event_id` (envelope event_id)
* optional delivery/debug basis for telemetry

**C) Denial meaning**

* `deny_reason_code` (stable taxonomy; e.g., `NOT_AUTHORIZED`, `KILL_SWITCH`, `ACTION_DISABLED_BY_POLICY`)
* `deny_reason_detail` (optional human-readable / explain pointer)
* `deny_terminal = true`

**D) Authorization provenance**

* `policy_id`, `policy_rev`, `policy_digest`
* optional `matched_rule_id`

### How J5 results become outcomes (canonicalization rule)

N7 must treat a DeniedDecision as:

* “create-or-load canonical denied outcome for `semantic_key`”
* publish that outcome (idempotently)

So the denied outcome has a **stable** outcome identity (stored in ledger/outbox and reused). Duplicates must converge to the same canonical denied outcome. 

### DENIED vs FAILED (line in the sand)

**DENIED** = “a stable policy decision under a known policy revision.”
**FAILED** = “we could not safely decide/execute” (e.g., policy unavailable, ledger unavailable, effector down).

So:

* missing policy snapshot → **FAILED** (`POLICY_STATE_UNAVAILABLE`, retryable)
* policy says disallow → **DENIED** (not retryable unless policy changes)

---

# J6 — N4 → N5

## ExecutePermit (exclusive attempt permission)

### What J6 is (purpose)

J6 is the ledger granting N5 permission to attempt execution **exactly once per attempt**, ensuring:

* no concurrent double-execution for the same semantic key
* crash safety (we can prove whether an attempt was already started/finished)

### What J6 is NOT allowed to do

J6 must not:

* contain effector-specific wiring (that’s N5/N6)
* contain policy rules (that’s N2/N3)
* allow N5 to “execute blind” without a ledger-issued permit

### What crosses J6: `ExecutePermit`

Minimum contents:

**A) Attempt identity + exclusivity**

* `semantic_key`
* `attempt_no` (monotonic per semantic_key; starts at 1)
* `attempt_id` (unique identifier)
* `permit_token` (ledger-issued token proving N5 owns this attempt)
* `permit_ttl` / `expires_at` (to recover from crashed workers)

**B) Intent execution bundle (enough to act without re-querying)**

* `action_type`, `target_ref`, `scope`
* `actor_principal`, `origin`
* `rationale_ref` (decision/case ref)
* `intent_event_id`
* `intent_fingerprint`

**C) Ledger provenance**

* `ledger_record_id` (pointer to the canonical intent/outcome record)

### Concurrency safety rule (non-negotiable)

**Designer pin:** N5 must present `permit_token` when writing attempt results back to the ledger. If it cannot, the ledger must reject the write (prevents two workers “both thinking they ran the attempt”).

### Fail-closed rule

If N5 cannot obtain a valid ExecutePermit (ledger unreachable / permit expired before start), it must not execute. It yields a FAILED path later (retryable) because “executing without idempotency proof” violates the platform law. 

---

# J7 — N4 → N7

## DuplicateHit / CanonicalOutcome (converge duplicates to one truth)

### What J7 is (purpose)

J7 is how N7 gets a **canonical outcome** to publish when:

* the intent is a semantic duplicate, or
* an outcome already exists (executed/denied/failed), or
* we’re republishing after a crash/outbox recovery

It is the “**convergence**” join: many deliveries → one outcome truth. 

### What J7 is NOT allowed to do

J7 must not:

* start execution (no N5/N6)
* mint a new outcome identity per duplicate
* mutate prior outcomes (append-only history only)

### What crosses J7: one of three ledger answers

#### (A) `CanonicalOutcomeRecord`

Used when an outcome exists (terminal or latest-known):

* `outcome_event_id` (stable, original)
* full outcome payload (EXECUTED/DENIED/FAILED + reasons + evidence refs)
* `policy_rev` used (for DENIED / policy-driven outcomes)
* `attempt_no` and timestamps (as recorded)
* `publish_state` (e.g., admitted bus coordinate if known)

#### (B) `DuplicateDecisionNoOutcomeYet` (in-flight)

Used when the semantic key is in-flight and no canonical terminal outcome exists yet:

* `semantic_key`
* `in_flight_attempt_id`
* `recommended_handling = NO_OP` (default)
* optional `retry_after_hint`

**Designer decision:** for v0 (bounded actions), the correct handling is **NO-OP**: do not emit “pending outcomes” just because duplicates arrived; the first attempt will publish the outcome.

#### (C) `KeyConflict`

Used when `semantic_key` exists but intent_fingerprint differs:

* `reason = IDEMPOTENCY_KEY_CONFLICT`
* conflict evidence (stored fingerprints / refs)

Handling is fail-closed:

* do not execute
* route to FAILED outcome path (no side effect)
* elevate incident signal (this is a producer bug / idempotency misuse)

### Publication rule for duplicates (the “no new truth” rule)

**Designer pin:** When N7 publishes due to J7, it must publish using the **original `outcome_event_id`** from the canonical record. That way:

* if already admitted, IG returns DUPLICATE (no new bus fact)
* if not admitted yet, publish completes the missing step

This gives deterministic behavior without bus spam. 

---

# J8 — N5 → N6

## ExecutionCommand (the side-effect boundary)

### What J8 is (purpose)

J8 is the only internal join that crosses into the “world-changing boundary” (effectors). It must be designed so that:

* side effects are **idempotent** when possible
* retries don’t multiply harm
* evidence refs are returned for audit/case closure

### What J8 is NOT allowed to do

J8 must not:

* carry DB handles, ledger tokens beyond what’s needed for correlation
* carry policy rule logic (effectors are not decision engines)
* allow effectors to publish to EB/IG (all outcomes still go through N7)

### What crosses J8: `ExecutionCommand`

Minimum contents:

**A) Semantic identity + attempt identity**

* `semantic_key`
* `attempt_id`, `attempt_no`

**B) External idempotency token**

* `external_idempotency_token` derived deterministically from `(semantic_key, action_type)`

  * must be stable across retries/restarts
  * must be safe to share (avoid leaking raw ids; typically derived via a digest/HMAC approach — exact method left to implementation, but determinism + non-leakage is required)

**C) Action execution details**

* `action_type`
* `target_ref`
* `scope`
* `action_params` (only what is needed to execute)
* `actor_principal` (if the effector needs attribution)
* `deadline_utc` / `timeout_ms`

**D) Correlation for observability**

* `intent_event_id`
* `trace_context` (trace_id/span_id propagation)

### Effector capability requirement (hard safety pin)

If an effector **cannot** honor idempotency (or provide an equivalent dedupe key), then that action type is **unsafe** and must be blocked by policy / not enabled in v0. Otherwise AL cannot guarantee effectively-once execution under replay. 

---

## Quick drift-check: what J5–J8 collectively guarantee

* **J5** ensures “deny = no execution” *and* denial outcomes are still canonical under semantic identity.
* **J6** ensures only one worker may attempt execution per semantic key attempt.
* **J7** ensures duplicates converge to one stable outcome (no new truth minted).
* **J8** ensures side effects are executed with an external idempotency token and clean evidence return.

If you’re ready for the next illumination step, the next tight cluster is **J9–J12** (effector receipt → attempt record → outcome draft → publish/outbox), because that’s where the “executed-but-not-published” and “publish retry without re-execute” guarantees are enforced.

---

On it. **J9–J12 is the “danger triangle”** where production systems usually drift into double-execution, missing outcomes, or “it executed but we can’t prove it.” So I’m going to **pin these joins tightly** to keep us inside the outer boundary laws (effectively-once, immutable outcomes, IG/EB mediated traffic, governed controls).  

I’ll keep subnetworks opaque:

* **N4** Idempotency & Outcome Ledger
* **N5** Execution Orchestrator
* **N6** Effector Adapters
* **N7** Outcome Assembly & Publisher

---

# J9 — N6 → N5

## ExecutionReceipt (effector result returns to orchestrator)

### What J9 is

The effector adapter returns a **structured receipt** that lets N5:

* decide whether the side effect is **committed / not committed / unknown**, and
* capture **evidence refs** needed for audit/case closure,
* do so without turning N6 into a decision engine.

### What J9 must NOT do

* **No publishing** (N6 never talks to IG/EB; only N7 does).
* **No policy decisions** (N6 does not decide “deny”).
* **No idempotency decisions** (N6 does not decide “duplicate”).
* **No mutation semantics** (“update the world”) beyond the effector call.

### What crosses J9: `ExecutionReceipt`

Minimum contents I’m pinning:

**A) Correlation / identity**

* `semantic_key` (echo)
* `attempt_id`, `attempt_no` (echo)
* `external_idempotency_token` (echo; confirms we used the correct token)
* `effector_adapter_id`, `effector_name`

**B) Commitment state (the crucial bit)**
One of:

* `COMMITTED` (high confidence the side effect is now true)
* `NOT_COMMITTED` (high confidence it did not happen; safe to retry or fail)
* `UNKNOWN` (timeout/ambiguous; cannot assert happened or not)

**C) Outcome classification**

* `result_code` (stable category, not vendor strings)
* `error_category` (if failed/unknown): e.g. `TIMEOUT`, `DEPENDENCY_DOWN`, `RATE_LIMIT`, `INVALID_PARAMS`, `PERMISSION_DENIED`, `CONFLICT`, `UNKNOWN`
* `retry_advice`: `{retryable: bool, suggested_backoff_ms, resolution_hint}`
  (resolution_hint can say: “safe to retry with same token” or “must query status endpoint first”)

**D) Evidence (by-ref posture)**

* `effector_request_id` (or equivalent correlation id)
* optional `effector_status_ref` (where status can be checked later)
* optional `response_digest` / `evidence_refs[]` (small, joinable pointers)

**E) Timing**

* `started_at_utc`, `finished_at_utc` (or duration)
* optional `effector_observed_at_utc`

### Designer pin for `UNKNOWN`

If `commitment_state=UNKNOWN`, the *only* safe stance under “effectively-once” is:

* **never start a second, different side effect**, and
* only attempt resolution via **idempotent replay using the same external token** *or* a status query.

This works because we already pinned: *effectors must honor an idempotency token (or the action type is unsafe/unavailable in v0).* 

---

# J10 — N5 → N4

## AttemptRecord append (durable attempt history + crash safety)

### What J10 is

J10 is N5 telling the ledger: “this attempt happened (or is happening), here’s the proof and classification.”
This is what closes the classic crash window:

> side effect executed ✅
> outcome publish failed ❌
> restart → must republish, not re-execute

### What J10 must NOT do

* It must not be optional. **No “best effort logging.”**
* It must not be replace/update semantics in a way that loses history.
* It must not allow writes without a ledger-issued authority token (prevents split-brain workers).

### What crosses J10: `AttemptRecord`

I’m pinning the AttemptRecord as **append-only** (internally the ledger may also maintain a derived “current state” row, but the source history is append-only).

Minimum fields:

**A) Authorization to write**

* `permit_token` (from J6), or `attempt_id` plus a ledger-verified token
* `semantic_key`, `attempt_id`, `attempt_no`

**B) Attempt lifecycle**

* `phase`: `STARTED` | `RECEIPT_RECORDED` | `FINALIZED`

  * (You can implement it as one record per phase, or one record that includes both start/end; but the semantics must be representable.)
* timestamps: `attempt_started_at_utc`, `attempt_finished_at_utc` (when known)

**C) Effector outcome summary (from J9)**

* `commitment_state` (COMMITTED/NOT_COMMITTED/UNKNOWN)
* `error_category`, `result_code`
* `retryable`, `next_retry_at_utc` (if applicable)

**D) Evidence refs**

* `effector_adapter_id`, `effector_request_id`
* `evidence_refs[]` / digests

**E) Intent consistency**

* `intent_fingerprint` (to detect collisions)
* `policy_rev` used for this attempt (so later you can prove what rules were in force)

### Two critical ledger rules (designer-authoritative)

1. **Permit enforcement:** the ledger must reject attempt writes that don’t present the matching permit authority.
2. **Collision protection:** if `(semantic_key)` exists with a different `intent_fingerprint`, ledger must:

   * refuse execution progression,
   * mark conflict,
   * force a FAIL-closed outcome (`IDEMPOTENCY_KEY_CONFLICT`).

(We already pinned the collision check at J4; J10 is where it becomes enforceable over time.)

---

# J11 — N5 → N7

## OutcomeDraft (candidate outcome to publish)

### What J11 is

N5 turns “what happened in the attempt” into an **outcome draft** that N7 can publish as immutable ActionOutcome traffic.

### What J11 must NOT do

* **No outcome identity minting.** N5 must not invent `outcome_event_id` on the fly. That must be ledger-owned for stability across restarts and duplicate deliveries. 
* **No publishing.** N5 never submits to IG/EB.
* **No mutation of prior outcomes.** This is append-only history.

### What crosses J11: `OutcomeDraft`

Minimum contents:

**A) Links / identity handles**

* `semantic_key`
* `intent_event_id` (parent causal link)
* `attempt_id`, `attempt_no`
* `outcome_handle` (ledger reference) **or** `outcome_event_id` provided by ledger/outbox (preferred)

**B) Outcome decision (for J11 specifically)**
J11 covers *execution attempts*, so the decision set here is:

* `EXECUTED`
* `FAILED`
  (“DENIED” comes via J5 / policy path.)

**C) Failure semantics**
If FAILED:

* `failure_category` (stable taxonomy)
* `retryable` boolean
* `recommended_next_action`: `RETRY_IDEMPOTENT` | `WAIT_DEPENDENCY` | `MANUAL_INTERVENTION` | `TERMINAL`

**D) Evidence / attribution**

* `actor_principal`, `origin`
* `policy_rev` used (important even for EXECUTED, so the audit can show which policy allowed it)
* `effector_request_id`, evidence refs/digests

**E) Timestamps**

* `outcome_ts_utc` = when execution/decision happened (domain time for the outcome)

### Designer pin for `UNKNOWN` commitment state

If J9 returns `UNKNOWN`, J11 must **not** claim EXECUTED. The safe drafting rule is:

* draft `FAILED` with `failure_category=UNCERTAIN_COMMIT`
* `retryable=true`
* `recommended_next_action=RETRY_IDEMPOTENT` (same token) or `QUERY_STATUS_THEN_RESOLVE`

Because the external idempotency token ensures any retry is a **resolution attempt**, not “do it twice.” 

---

# J12 — N7 ↔ N4

## Outbox + publish-state join (the “never executed twice” guarantee keeper)

This is the join that makes the system robust to:

* publish failures,
* restarts,
* duplicate intents,
* replay/backfill.

### What J12 is

A bidirectional handshake:

**(a) N4 → N7:** provide stable outcomes that need publishing (`OutcomeToPublish`).
**(b) N7 → N4:** report publish results (`PublishReceipt`) so the ledger can mark outcomes as “admitted” (or “incident/quarantine”).

### What J12 must NOT do

* N7 must **never** publish an outcome that is not present in the ledger/outbox.
* N7 must **never** trigger execution (no call into N5/N6).
* N4 must not let “publish succeeded” rewrite outcome meaning; it only records publish state and bus coordinates.

### What crosses J12 (a): `OutcomeToPublish`

Minimum fields:

**A) Stable event identity**

* `outcome_event_id` (stable for the semantic key + attempt/outcome record)
* `event_type=ActionOutcome`
* `manifest_fingerprint` (+ ContextPins where applicable)

**B) Payload (immutable)**

* decision: EXECUTED/DENIED/FAILED
* semantic_key, intent link, attempt_no
* actor/origin, policy_rev
* evidence refs

**C) Publish metadata**

* `publish_partition_key_hint` (optional; usually derived from semantic_key)
* `publish_attempt_count`
* `last_publish_error` (if any)
* `priority` / `due_at_utc` (optional scheduling hints)

### What crosses J12 (b): `PublishReceipt`

Minimum fields:

* `outcome_event_id`
* IG decision: `ADMIT` | `DUPLICATE` | `QUARANTINE`
* `ig_receipt_id` (or ref)
* if admitted/duplicate: bus coordinate `(topic, partition, offset)` when available
* `published_at_utc`
* if quarantine: `quarantine_reason_code` + evidence pointers

### Hard production rule for outcomes

**Designer pin:** If IG returns **QUARANTINE** for an ActionOutcome, treat it as **P0**:

* mark the outcome publish state as `QUARANTINED`
* surface an incident via N8 immediately
* AL should enter a controlled posture (often drain/kill for new executions) until corrected

Because quarantined outcomes break the platform’s “what actually happened” truth and audit closure loop. 

### Canonical re-publish rule (prevents bus spam)

When publishing due to duplicates or recovery:

* N7 must always publish using the **original `outcome_event_id`** (stable)
* If already admitted, IG returns DUPLICATE → ledger marks “published” and stops retrying

This is exactly how you get deterministic convergence in at-least-once systems. 

---

## Mini end-to-end (how J9–J12 fit together)

**Success case:**
J9 receipt(COMMITTED) → J10 append attempt → J11 draft EXECUTED → J12 outbox publish → receipt ADMIT/DUPLICATE recorded

**Fail + retry:**
J9 receipt(NOT_COMMITTED, retryable) → J10 append failure → J11 draft FAILED(retryable) → (later) new J6 permit → retry → eventual publish

**Ambiguous timeout:**
J9 receipt(UNKNOWN) → J10 append uncertain → J11 draft FAILED(UNCERTAIN_COMMIT, retryable) → resolution retry with same token (safe) → eventual committed/not-committed → publish

**Publish failure after commit:**
J10 + J11 complete → J12 publish fails transiently → N4 keeps outbox entry → N7 retries publish (never re-executes)

---

## Drift bans (explicit, so we don’t “accidentally simplify” later)

* **Banned:** “If publish fails, just re-run execution.”
* **Banned:** “Orchestrator publishes outcomes directly.”
* **Banned:** “Effector publishes callbacks directly to EB.”
* **Banned:** “Mint outcome IDs on the fly in N5.”
* **Banned:** “Treat UNKNOWN as EXECUTED.”

These would all violate the outer network safety pins. 

---

If you want to keep momentum, the next illumination is **J13 telemetry tap + the internal loop rules (retry loop, outbox loop, duplicate loop)**, because now that the join surfaces are pinned, we can define the *internal loop behaviors* without exploding into implementation detail.

---

Locked. **J13–J16** are the “cross-cutting + optional + remediation” joins. I’ll illuminate them with **hard anti-drift boundaries** so they can’t quietly turn into control paths or bypass IG/EB, and so they preserve replay safety + immutability.  

I’ll keep nodes opaque:

* **N8** Observability & Governance Hooks
* **N9** Async Callback Intake & Correlator (optional)
* **N10** Quarantine/Remediation Surface (optional)

---

# J13 — (N1..N7) → N8

## Telemetry tap join

### What J13 **is**

A **one-way tap**: internal state transitions and key facts from N1..N7 stream into N8 so you can operate AL and reconstruct “what happened” operationally.

### What J13 **is not** (non-negotiable)

* **Not a control input.** N8 cannot change outcomes, authorize, dedupe, execute, or publish. Controls come via N2 only. 
* **Not an audit truth source.** Audit truth remains ActionOutcome events + DLA, not logs. Telemetry can fail without corrupting correctness. 

### What crosses J13: `TelemetryEvent`

Every telemetry event must carry **correlation keys** so joins are deterministic:

**A) Correlation keys (always include what you have)**

* `intent_event_id` (envelope `event_id`) 
* `semantic_key` = `(ContextPins, idempotency_key)` when available 
* `attempt_id`, `attempt_no` (if any)
* `outcome_event_id` (if any)
* `actor_principal`, `origin`
* `policy_rev` (the one used for the decision/attempt)
* `effector_adapter_id`, `effector_request_id` (if any)

**B) Stage / state transition (what happened inside AL)**
Examples:

* `INTAKE_NORMALIZED`, `AUTHZ_ALLOWED`, `AUTHZ_DENIED`
* `LEDGER_DUPLICATE_HIT`, `LEDGER_PERMIT_GRANTED`, `LEDGER_CONFLICT`
* `EXEC_ATTEMPT_STARTED`, `EXEC_RECEIPT_COMMITTED`, `EXEC_RECEIPT_UNKNOWN`
* `OUTCOME_ENQUEUED`, `PUBLISH_ADMITTED`, `PUBLISH_DUPLICATE`, `PUBLISH_QUARANTINED`

**C) Minimal payload discipline**
Telemetry must be **by-ref / digests**, not full intent payloads (avoid leaking sensitive content and avoid turning logs into truth). 

### Reliability posture (pin this)

* J13 is **non-blocking**: telemetry backpressure must not block execution/publish.
* Critical “correctness facts” are already durable in ledger/outbox + outcomes; telemetry loss is an ops issue, not a correctness hole.

---

# J14 — N9 → N4 (preferred)

## Callback normalize/correlate join (optional)

(We previously said “N9→N1 OR N9→N4”. **Designer decision:** in production, the cleanest non-drift design is **N9 → N4**; callbacks are not ActionIntents and shouldn’t share N1’s path. N9 may *reuse* the same normalization library internally, but the join target is N4.)

### What J14 **is**

When async actions are enabled, AL ingests **callback events** (arriving via IG→EB, envelope conformant) and turns them into a **correlation request** for the ledger.  

### What J14 **is not**

* Not a path that can create side effects.
* Not a path that can mutate prior outcomes.
* Not a path that “guesses” correlations.

### What crosses J14: `NormalizedCallbackCorrelation`

Minimum fields:

**A) Callback identity**

* `callback_event_id` (envelope `event_id`) 
* `callback_type`
* `callback_ts_utc`
* `callback_producer_principal` (who sent it; must be allowlisted)

**B) Correlation basis (one of these must be present)**
Correlation precedence (designer-pinned):

1. **Explicit `semantic_key`** present in callback payload
2. **`effector_request_id`** present (mapped by N4 from prior attempts)
3. **`parent_intent_event_id`** present (mapped by N4 to semantic_key)

If none of these exist → it’s an **OrphanCallback** (route to N10, do not change action state).

**C) Evidence refs**

* `effector_status_ref` / `evidence_refs[]` / digests

### Callback auth posture (pin this)

Callbacks must be **fail-closed**:

* if producer not allowlisted for that callback_type → treat as untrusted/orphan (and/or rely on IG quarantine upstream) 

---

# J15 — “Closure outcome append” (callback → closure)

## N9 → N4 to create closure, then N4 → N7 publishes via J12

We previously sketched J15 as “N9→N7 closure draft”. **Designer correction:** N9 must not bypass the ledger/outbox; otherwise you lose stability under restart/duplicate delivery. So:

* **J15a (authoritative): N9 → N4 `ClosureAppendRequest`**
* **J15b:** closure is enqueued in the outbox and published by N7 using the existing **J12** machinery.

This keeps **all outcomes ledger-owned** and ensures replay safety. 

### What J15 **is**

A callback causes AL to **append** a new closure record to the action’s outcome history (immutably), then publish it as ActionOutcome traffic.

### What J15 **is not**

* Not a mutation of the earlier outcome (“no update-in-place”).
* Not “complete by editing the previous event.”
* Not “publish a closure outcome without ledger state.”

### What crosses J15a: `ClosureAppendRequest`

Minimum contents:

* `callback_event_id` (dedupe key) 
* `semantic_key` (resolved via J14 correlation)
* `closure_state` (e.g., `CONFIRMED`, `REJECTED`, `COMPLETED`, `FAILED_FINAL`)
* `evidence_refs[]` / `effector_status_ref`
* optional `predecessor_outcome_event_id` (link to the earlier “initiated/attempted” outcome)

### Idempotent closure rule (pin this)

* Same `callback_event_id` (or same correlation+status) must not append multiple closures. N4 dedupes closure ingestion and returns “already applied”.

---

# J16 — N10 ↔ (N1 / N7 / N2)

## Remediation interactions join (optional but production-real)

N10 is the internal “surface” that makes quarantine/triage **possible** without turning AL into a chaos cockpit. It’s **read-mostly** and any “action” it triggers must still go through governed control paths or safe republish paths. 

### What J16 **is**

A set of narrow joins that:

* collect **triage items** (what went wrong, where, with refs), and
* allow **privileged, auditable remediation requests**.

### What J16 **is not** (hard bans)

* Not a bypass of IG/EB.
* Not a “mutate outcomes” interface.
* Not a stealth control plane (no hidden toggles).
* Not a place to “fix” intents/outcomes by editing payloads.

### J16 inbound triggers (what feeds N10)

**From N1 → N10 (internal intake rejects)**

* `NormalizationFailure` / “unexpected schema” / missing required keys
  These should be rare because IG should enforce schemas; treat them as misconfig/attack signals.

**From N7 → N10 (publish anomalies)**

* `OutcomePublishQuarantined` (P0) with IG receipt + evidence pointers
* repeated publish failures beyond threshold (stuck outbox)

**From N4/N9 (optional) → N10**

* `IDEMPOTENCY_KEY_CONFLICT`
* `OrphanCallback` / untrusted callback

### J16 outbound actions (what N10 is allowed to request)

Only three classes are allowed:

1. **Inspection / export (read-only)**

* fetch triage item metadata + by-ref evidence pointers (no payload rewriting)

2. **Safe republish request**

* “re-enqueue this existing outcome_event_id for publish”
  This is allowed because it cannot re-execute; it only nudges the outbox/publisher to retry J12.

3. **Governed change proposals**

* “request a policy/profile change” (e.g., disable an action_type, allow a callback producer)
  But activation remains a governance/run-operate act that N2 later consumes as an **ActivePolicySnapshot / ExecutionPostureSnapshot**. 

### Privilege + audit posture (pin this)

Access to N10 and any action requests must be **privileged and auditable** (especially dev/prod), consistent with your environment ladder. 

---

## Drift guard summary for J13–J16

* **J13:** observability is a **tap**, never a control path.
* **J14/J15:** callbacks can only **append closure** via the ledger/outbox; never mutate, never guess correlations.
* **J16:** remediation is **read-mostly + safe republish + governed change requests**; no bypasses, no silent edits.

If you want the next illumination step, the natural continuation is: pin the **loop behaviors** that these joins enable (publish retry loop, retry/backoff loop, orphan callback loop, quarantine triage loop) without opening the boxes yet.

---

Got it. We’ll **illuminate internal paths P1–P4** (still keeping N1..N7 opaque), but we’ll pin the **production meaning, sequencing, and invariants** so we can’t drift when we open boxes later.

I’ll reference the internal nodes/joins we’ve already pinned:

* **N1** Intake/Normalize → **J1** → **N3** AuthZ
* **N2** Policy/Control → **J2/J3** → N3/N5
* **N3** AuthZ → **J4** → **N4** Ledger
* **N3** Deny → **J5** → **N7** Publisher
* **N4** Permit → **J6** → **N5** Orchestrator
* **N4** Duplicate/canonical → **J7** → **N7**
* **N5** → **J8** → **N6** Effector
* **N6** → **J9** → **N5** Receipt
* **N5** → **J10** → **N4** AttemptRecord
* **N5** → **J11** → **N7** OutcomeDraft
* **N7** ↔ **J12** ↔ **N4** Outbox/Publish-state

One **designer correction upfront** (authoritative):
Even when we “bypass” N4/N5/N6 for **DENIED**, we do **not** bypass the **ledger/outbox canonicalization**. Denials must still converge under `(semantic_key)` so duplicates don’t mint new denied outcomes. So P2 includes N7↔N4 via **J12**.

---

## P1 — New intent, execute successfully (canonical hot path)

**Trigger:** AL receives an ActionIntent that is (a) parseable, (b) authorized, and (c) not a semantic duplicate.

**Goal:** exactly one side effect, one immutable outcome, reliably published (even across crashes).

### P1 step sequence (production)

1. **Normalize**

   * N1 parses envelope+payload, extracts `semantic_key=(ContextPins,idempotency_key)` and `intent_fingerprint`.
   * If missing required minima → this path is not eligible (goes to failure outcome path, not P1).

2. **Authorize**

   * N3 evaluates against `ActivePolicySnapshot` (J2).
   * Decision = ALLOW → produce `AuthorizedIntent` (J4) stamped with `policy_rev` + `intent_fingerprint`.

3. **Ledger grants exclusive attempt**

   * N4 checks `semantic_key`: no canonical terminal outcome exists, not in conflict, not currently in-flight.
   * N4 emits `ExecutePermit(attempt_no, attempt_id, permit_token)` (J6).
     **Pinned invariant:** without ExecutePermit, N5 must not execute.

4. **Start attempt (orchestrate)**

   * N5 begins attempt under permit ownership (attempt_id/permit_token).
   * N5 forms `ExecutionCommand` with deterministic **external_idempotency_token** (J8) and calls N6.

5. **Effector executes, returns receipt**

   * N6 performs side effect using the idempotency token.
   * N6 returns `ExecutionReceipt` with `commitment_state=COMMITTED` + evidence refs (J9).

6. **Attempt history becomes durable truth**

   * N5 writes `AttemptRecord` to N4 (J10), using `permit_token` (ledger must enforce this).
   * This record is the “crash-window seal”: after this, restarts must republish, never re-execute.

7. **Draft outcome**

   * N5 emits `OutcomeDraft(decision=EXECUTED, attempt_no, evidence_refs, policy_rev, outcome_ts_utc)` to N7 (J11).
     **Pinned invariant:** N5 does not mint outcome IDs; N7/ledger owns stable `outcome_event_id`.

8. **Outbox publish (durable → admitted)**

   * N7 obtains `OutcomeToPublish(outcome_event_id, immutable payload)` from N4 via J12 and submits to IG.
   * N7 returns `PublishReceipt(ADMIT/DUPLICATE, bus coords if available)` back to N4 (J12).

9. **Completion**

   * Ledger marks publish_state for that `outcome_event_id` as admitted/complete.
   * Any duplicate future deliveries converge (P3/P4), never re-execute.

### P1 hard guarantees (we will not break later)

* **Exactly one attempt executes** per semantic intent (ledger-issued permit).
* **Side effect cannot be repeated** under replay because execution requires ledger permit and uses external idempotency token.
* **Executed-but-not-published** results in **republish**, not re-execute (outbox).
* Outcome is immutable; publish is retryable; execution is not.

---

## P2 — Denied by policy (no execution)

**Trigger:** ActionIntent is parseable but is not permitted by policy (or kill-switch / policy disables).

**Goal:** **no side effect**, but a **canonical DENIED outcome** exists and is publishable/replay-safe.

### P2 step sequence (production)

1. **Normalize** (same as P1 step 1)

2. **Authorize → DENY**

   * N3 decides DENY using `ActivePolicySnapshot` (J2).
   * N3 emits `DeniedDecision(semantic_key, deny_reason_code, policy_rev, intent_fingerprint)` (J5) to N7.

3. **Canonicalize + publish via ledger/outbox**

   * N7 uses J12 with N4 to **create-or-load** the canonical denied outcome for `semantic_key` (stable `outcome_event_id`).
   * N7 publishes that outcome through IG and records the receipt back to N4 (J12).

### P2 hard guarantees

* **DENIED is terminal and policy-attributable** (includes policy_rev).
* **Duplicates don’t mint new DENIED outcomes** (canonical outcome ID is reused).
* **No execution path is reachable** (N5/N6 never invoked).

**DENIED vs FAILED line stays sharp:**

* “Policy says no” → DENIED.
* “We can’t load policy / can’t prove idempotency” → FAILED (retryable).

---

## P3 — Duplicate intent, canonical outcome already known

**Trigger:** AL receives an ActionIntent whose **semantic_key already has a canonical outcome** (EXECUTED / DENIED / FAILED-final), or at least an outcome record that is definitive for this key.

**Goal:** **no execution**, no new truth; ensure publish convergence if needed.

### P3 step sequence (production)

1. **Normalize**

2. **Authorize**

   * N3 may still evaluate authz for observability/consistency, but **must not change outcome truth** for an already-completed semantic key.
   * (If you want strictness: we can later choose to skip authz for true duplicates; but that’s an internal optimization, not a semantic change.)

3. **Ledger duplicate hit**

   * N4 receives `AuthorizedIntent` (J4) and detects semantic key already resolved.
   * N4 emits via J7 either:

     * `CanonicalOutcomeRecord(outcome_event_id, payload, publish_state)` **or**
     * `KeyConflict` (if fingerprint differs → fail-closed).

4. **Publisher convergence behavior (designer pin)**

   * If `publish_state=ADMITTED` → **NO-OP** (do not republish; just complete processing).
   * If `publish_state` indicates pending/unknown/not-admitted → N7 triggers **outbox publish** using the same `outcome_event_id` (J12).
   * Under no circumstances does this path call N5/N6.

### P3 hard guarantees

* **Duplicates cannot cause side effects** (no permit granted).
* **No bus spam** when already admitted (default NO-OP).
* **If an outcome exists but wasn’t published**, duplicates help convergence by nudging outbox publish.

---

## P4 — Duplicate arrives while an attempt is in-flight

**Trigger:** AL receives a duplicate semantic intent while the first attempt is **already in-flight** (permit granted to another worker/earlier processing).

**Goal:** **never start a second attempt**, keep behavior deterministic and low-noise.

### P4 step sequence (production)

1. **Normalize**
2. **Authorize** (same note as P3: authz here is optional for performance later, but safe to keep for now)
3. **Ledger in-flight detection**

   * N4 receives `AuthorizedIntent` (J4), sees `semantic_key` has `in_flight_attempt_id` with no terminal canonical outcome yet.
   * N4 returns via J7: `DuplicateDecisionNoOutcomeYet(recommended_handling=NO_OP, in_flight_attempt_id)`.

### P4 authoritative handling choice (v0 decision)

We choose **P4a = NO-OP** as the authoritative v0 behavior:

* AL does **not publish** any “pending” or “duplicate-in-flight” event.
* AL does **not start** a new attempt.
* The original attempt will produce the outcome, and outbox ensures it will be published even if publishing initially fails.

Why: it preserves immutability discipline, avoids event spam, and keeps semantics clean under at-least-once delivery.

### P4 hard guarantees

* **At most one in-flight attempt** per semantic key (enforced by N4 permits).
* **Duplicates do not create new outcomes**; they just get absorbed.
* Observability (J13) can still count/trace duplicates-in-flight for ops.

---

## Cross-path drift guard (applies to P1–P4)

These are banned across all four paths:

* Starting execution without an **ExecutePermit**.
* Publishing from N5/N6 (only N7 publishes).
* Minting outcome IDs in N5 (ledger/outbox owns them).
* Treating a semantic duplicate as a new semantic intent.
* Producing “silent drops” (every terminal disposition must have an outcome fact eventually: EXECUTED/DENIED/FAILED-final).

---

Alright — **P5–P7 illuminated** at the *path semantics* level (nodes still opaque), with the **designer pins** that keep us inside the boundary: *effectively-once*, *immutable outcomes*, *IG/EB mediated traffic*, *no silent drops*, *governed controls*. 

I’ll keep using our internal node shorthand (N1..N7) and the joins we already pinned (J1–J12).

---

# P5 — Execution fails (retryable)

**Trigger:** An ActionIntent is normalized + authorized + permitted, but the execution attempt cannot be completed successfully **and is classified retryable** (dependency down, timeout/UNKNOWN, rate-limit, transient errors, etc.).

**Goal:** Never double-execute, preserve attempt history, and either (a) succeed on a later attempt or (b) terminate deterministically with a final FAILED outcome.

## P5 canonical sequence

1. **N1 → N3 → N4 → N5 (same front as P1)**

   * Intent normalized (J1), authorized (J4), and ledger grants `ExecutePermit(attempt_no, attempt_id, permit_token)` (J6).
   * **Pinned invariant:** no permit ⇒ no execution. 

2. **N5 → N6 (J8) execution attempt begins**

   * N5 issues `ExecutionCommand` with **external_idempotency_token** derived deterministically from the semantic key.
   * **Pinned invariant:** retries must reuse the same external token (resolution, not duplication). 

3. **N6 → N5 (J9) receipt comes back as “not successful but retryable”**
   Two common subcases:

   * **NOT_COMMITTED + retryable** (safe to retry)
   * **UNKNOWN + retryable** (ambiguous timeout; retry is allowed only because idempotency token makes it safe)

4. **N5 → N4 (J10) append AttemptRecord (durable)**
   N5 writes an append-only attempt record capturing:

   * attempt id/no, commitment state, error category, retryable, evidence refs
   * **and** the scheduling hint: `next_retry_at_utc` (or equivalent)
     This record is what prevents crash-induced double execution. 

5. **N5 → N7 (J11) emit OutcomeDraft = FAILED (retryable=true)**

   * The draft must *not* claim EXECUTED if commitment is UNKNOWN.
   * It must carry stable failure taxonomy + retryability.

6. **N7 ↔ N4 (J12) outbox publish the FAILED(attempt_no) outcome**

   * Outcome gets a stable `outcome_event_id` (ledger/outbox owned).
   * Publisher tries IG submission; records ADMIT/DUPLICATE/QUARANTINE back to the ledger.

7. **Later: retry happens as a new attempt**

   * When retry is due and posture allows, the ledger issues a **new ExecutePermit** with `attempt_no+1` (J6).
   * N5 repeats steps 2–6.
   * Eventually one of two things happens:

     * **Success**: a later attempt yields EXECUTED outcome (terminal)
     * **Terminal failure**: max_attempts reached or non-retryable failure ⇒ FAILED (retryable=false, terminal=true)

## P5 designer pins (to prevent drift)

* **P5.1 One semantic key, sequential attempts only**
  At most one in-flight attempt per semantic key; retries create **new attempt_no** under new permits (never parallel “races”). 
* **P5.2 Publish attempt outcomes (append-only history) is allowed and preferred**
  Each completed attempt may emit an immutable ActionOutcome with `attempt_no` and `retryable`. The **canonical** outcome for duplicates is the latest **terminal** one; otherwise the latest known attempt outcome (but recommended handling for duplicates while waiting is still NO-OP unless publish is pending). 
* **P5.3 Retry does not change semantic identity**
  Retries reuse the same semantic key and external idempotency token; re-execution is “resolution,” not “new action.”
* **P5.4 Duplicates during backoff**
  If the latest known outcome is FAILED(retryable) and a retry is scheduled:

  * duplicates must **not** trigger early retry
  * they may NO-OP or re-emit the latest known canonical record only if it wasn’t successfully published (outbox convergence).

---

# P6 — Outcome publish fails, but execution already happened (outbox path)

**Trigger:** Execution has reached a state that is durably recorded (attempt record + outcome exists), but **publishing the outcome** to IG/EB fails or is uncertain.

**Goal:** Publish is retried until ADMIT/DUPLICATE (or escalated on QUARANTINE), **without ever re-executing**.

## P6 canonical sequence

1. **Execution already sealed in the ledger**
   The “seal” is: attempt record appended (J10) and an outcome exists in the ledger/outbox (via J11→J12).
   **Pinned invariant:** after this seal, the correct recovery action is *republish*, never re-execute. 

2. **N7 attempts publish; publish fails transiently**
   Examples:

   * IG unreachable / timeout
   * EB append uncertainty
   * network partitions

3. **N7 → N4 (via J12) records publish failure state**

   * `publish_state = PENDING_RETRY`
   * `last_publish_error`, `publish_attempt_count`, `next_publish_attempt_at`

4. **N7 retries publish (outbox loop)**

   * Always using the **same `outcome_event_id`**.
   * If the earlier publish actually succeeded but receipt was lost, the retry yields IG **DUPLICATE**, which is treated as success and closes the loop.

5. **If IG returns QUARANTINE (rare, severe)**

   * Mark `publish_state = QUARANTINED`
   * Raise P0 incident signal (via N8)
   * AL should shift into a controlled posture (typically drain/kill new executions) until corrected
     Because quarantined outcomes break the platform’s “what actually happened” chain. 

## P6 designer pins (to prevent drift)

* **P6.1 Publisher never calls orchestrator**
  Publish retry must never route back into N5/N6. Outbox retries are pure publish attempts.
* **P6.2 Stable outcome_event_id is mandatory**
  It is the mechanism that makes “unknown publish result” safe (IG DUPLICATE closes the loop).
* **P6.3 Execution progress is never gated on telemetry**
  Publish failures are handled via ledger/outbox state, not by “did we see the log line.”

---

# P7 — Drain / Kill posture active

**Trigger:** N2 activates a governed execution posture change (drain, kill switch, action-type disable, safe-mode caps). This affects N3 (authz) via J2 and N5 (execution) via J3.

**Goal:** Stop harm safely **without breaking immutability, replay safety, or auditability**.

I’ll pin the two primary postures:

## P7a — DRAIN mode (quiesce without spamming outcomes)

**Designer decision (authoritative v0):** *Drain is implemented primarily by pausing intake / stopping new attempts*, not by emitting a FAILED outcome for every arriving intent.

### Sequence

1. **N2 → N5 (J3) sets `drain_mode=true`**
2. **AL stops starting new executions**

   * N5 stops requesting new ExecutePermits for new intents and scheduled retries.
   * In-flight attempts are allowed to finish.
3. **Outbox publish continues**

   * N7 continues republishing pending outcomes (P6 still runs).
4. **No new truth minted just because we’re draining**

   * Intents not yet handled remain in EB (or remain uncommitted if already fetched), preserving “no silent drops” without generating noise outcomes.

### Drain invariants

* No new effector calls start after drain is active.
* In-flight attempts complete and publish outcomes.
* Outbox flush continues.
* When drain is lifted, normal processing resumes.

## P7b — KILL switch / policy hard-deny (visible refusal)

**Designer decision:** Kill is a **policy-level hard deny** (attributable and visible), so new intents should produce **DENIED** outcomes rather than being silently paused.

### Sequence

1. **N2 → N3 (J2) provides policy snapshot with kill scopes/action_types**
2. **N3 denies → J5 to N7**

   * DENIED outcomes are canonicalized under semantic key and published via outbox (J12).
3. **In-flight attempt handling under kill**

   * If an effector call is already in progress or committed: finish and publish truth (you can’t “uncommit”).
   * If an attempt has started but hasn’t called the effector yet: abort execution and finalize as a terminal outcome with explicit reason (I pin: **FAILED with `CANCELLED_BY_POSTURE`**, not DENIED, because execution lifecycle had begun).
   * If kill activates while retries are scheduled: stop further retries and append a terminal outcome: **FAILED-final with `STOPPED_BY_KILL`**.

### Kill invariants

* New actions in killed scope never execute.
* Refusal is explicit and attributable (`policy_rev`, deny_reason).
* History remains append-only and joinable.

---

## The “don’t drift” summary for P5–P7

* **P5:** retry is a *ledger-permitted, sequential attempt loop*; outcomes can represent attempt history; no parallelism; safe resolution under UNKNOWN relies on external idempotency.
* **P6:** publish failures are solved by outbox republish with stable outcome IDs; never by re-executing.
* **P7:** drain = quiesce (pause new work), kill = explicit deny (visible outcomes), both preserve in-flight completion + outbox flush.

If you want the next illumination, we go to **P8 (crash/restart recovery)** next, because it stitches P5 and P6 together into a restart-safe story.

---

Locked — illuminating **P8–P10** as **production internal paths** (subnetworks still opaque), but pinning the *sequencing + invariants* so we don’t drift when we open the boxes. 

---

# P8 — Crash / restart recovery path

**Purpose:** after a crash/restart, AL must **republish outcomes, not re-execute**, and must return to a safe steady state under at-least-once delivery. This is required by your pins: *effectively-once execution* + *immutable outcomes* + *replay safety*. 

## P8.0 Recovery ordering (designer-pinned)

On startup, AL must perform recovery in this order:

1. **Load control posture first (N2)**
2. **Load ledger/outbox state (N4)**
3. **Republish pending outcomes (N7 via J12)**
4. **Reconcile in-flight attempts safely (N5 with N4/N6)**
5. **Only then resume normal consumption** (new intents, new attempts)

This ordering prevents the most dangerous drift: “start executing new work while the system still hasn’t published what it already did.” 

## P8.1 Step sequence (production)

### Step 1 — Control posture bootstrap (N2)

* N2 loads **ActivePolicySnapshot** + **ExecutionPostureSnapshot** (policy revs, kill/drain, caps).
* **Fail-closed rule:** if N2 cannot load policy/control posture, AL must not execute. It either drains or produces retryable FAILED outcomes (never “execute blind”). 

### Step 2 — Ledger/outbox scan (N4)

N4 enumerates durable state buckets:

* **Outbox pending**: outcomes that exist but are not confirmed admitted.
* **In-flight attempts**: semantic keys with a granted permit/attempt started but not finalized.
* **Scheduled retries**: retryable failures waiting for next attempt time.
* **Conflicts**: idempotency key collisions / invalid states (must remain fail-closed).

### Step 3 — Outbox re-drive (N7 ↔ N4 via J12)

* N7 republish loop runs first: publish every pending `outcome_event_id` using the **same stable outcome_event_id**.
* If prior publish actually succeeded, IG returns **DUPLICATE**, which closes the loop safely.
* If IG returns **QUARANTINE** for an ActionOutcome → **P0 incident** posture (surface immediately; likely drain/kill new execution until corrected). 

### Step 4 — In-flight attempt reconciliation (N5 + N4, optionally N6)

For each in-flight attempt, N5 must decide safely without duplicating side effects:

* **Case A: attempt record indicates COMMITTED**
  → do **not** execute; ensure terminal outcome exists; if publish pending, outbox will republish (Step 3).

* **Case B: attempt record indicates NOT_COMMITTED and retryable**
  → schedule/permit a new attempt later (normal retry loop), but only via N4 granting a new ExecutePermit.

* **Case C: attempt is “unknown/ambiguous” (e.g., crash mid-call, timeout)**
  → do not claim EXECUTED. Mark state as needing **resolution**.
  Resolution attempts must be **idempotent**: re-drive using the same external idempotency token and/or an effector status probe (if supported), never a “fresh” side effect.

* **Case D: permit TTL expired with no receipt**
  → treat as ambiguous; same as Case C (resolution), never “just run again.”

### Step 5 — Resume steady state safely

Only after Steps 1–4 succeed:

* N1 resumes intake of new intents
* N5 resumes issuing new attempts (subject to posture)
* Outbox republish continues as a background loop

## P8 drift bans

* **Banned:** “restart → re-execute because we’re not sure.”
* **Banned:** “commit progress/ack intake before ledger/outbox durability exists.”
* **Banned:** “publish new outcome IDs on restart.”
  All violate the pinned replay/effectively-once story. 

---

# P9 — Async completion via callback (optional)

**Purpose:** support actions whose completion is confirmed later (callbacks), without mutating history.

**Pinned rule:** closure must be **append-only**; no mutation of prior outcomes. 

## P9.1 Step sequence (production)

1. **Callback event arrives via IG→EB** (canonical envelope boundary applies). 
2. **N9 normalizes callback and resolves correlation** to a semantic key via N4 (preferred correlation precedence we pinned):

   * semantic_key in callback, else
   * effector_request_id, else
   * parent_intent_event_id
     If none → orphan/untrusted callback path (goes to remediation surface).
3. **N4 dedupes callback ingestion** (using callback_event_id) and appends a **closure record** for that semantic key:

   * closure_state (e.g., CONFIRMED/REJECTED/COMPLETED)
   * evidence refs/status refs
4. **N7 publishes the closure outcome** via the normal outbox/publisher path (J12):

   * stable `outcome_event_id` for the closure record
   * immutable payload
5. Duplicates of the callback safely no-op because N4 dedupes callback_event_id.

## P9 drift bans

* **Banned:** callback “updates” the previous outcome event.
* **Banned:** callback triggers execution.
* **Banned:** guessing correlation by time or scanning.
  All violate append-only + determinism. 

---

# P10 — Quarantine remediation touchpoint (optional)

**Purpose:** make quarantine/triage **possible** without turning AL into a bypass or an editor of truth.

**Pinned rule:** remediation is privileged and auditable; re-entry must occur through **normal intake paths** (IG→EB), and truth is never silently mutated. 

## P10.1 What triggers P10

Typical triage items:

* ActionIntent quarantined at IG (schema/auth/joinability)
* ActionOutcome quarantined at IG (**P0**)
* idempotency key conflicts
* orphan/untrusted callbacks
* persistent outbox publish failures

## P10.2 What P10 is allowed to do (designer-pinned)

N10 supports only three remediation actions:

1. **Inspect (read-only)**
   Provide refs to receipts/evidence blobs/digests and correlation keys.

2. **Safe republish request**
   “Re-enqueue this existing `outcome_event_id` for publish.”
   (This cannot cause re-execution and is therefore safe.)

3. **Governed change request**
   Propose policy/profile changes (e.g., disable action_type, adjust allowlist).
   Activation still happens via governance/run-operate surfaces and is consumed through N2 snapshots.

## P10.3 How “release/reprocess” must work (no bypass)

If something is to be reprocessed:

* It is resubmitted through **IG** (not injected into N1 directly).
* Identity rule we pinned holds:

  * if bytes/meaning unchanged → same event_id resubmitted
  * if corrected/transformed → new event_id with lineage link to the quarantined candidate

## P10 drift bans

* **Banned:** “fix the quarantined payload inside AL and continue.”
* **Banned:** “override IG by force-admitting inside AL.”
* **Banned:** “edit prior outcomes.”
  All violate trust boundary + immutability. 

---

If you want the clean next step: we pin **internal loop behaviours** that P5–P10 rely on (retry loop, outbox loop, posture loop, quarantine triage loop) as explicit state transitions—still without opening the boxes.

---

Locked — illuminating **internal loops L1–L4** (still keeping the subnetworks opaque), but pinning the **loop laws**, **state transitions**, and **stop conditions** so we don’t drift when we later open N2/N4/N5/N7.  

I’ll reference the same opaque nodes:

* **N1** Intake/Normalize
* **N2** Policy/Control
* **N3** AuthZ
* **N4** Ledger/Idempotency/Outbox
* **N5** Orchestrator
* **N6** Effector
* **N7** Publisher

---

# L1 — Execution retry loop (bounded)

`N5 ↔ N6 ↔ N4`

## What L1 exists to guarantee

* Transient failures do **not** cause duplicate side effects.
* Retries are **sequential**, **bounded**, and **explainable**.
* The ledger remains the sole grantor of “you may attempt execution now.”

## Loop mechanics (authoritative)

### L1.1 Retry cycle steps

1. **Permit-gated attempt begins**

   * N4 issues `ExecutePermit(attempt_no, attempt_id, permit_token)` → N5 (J6).
   * **No permit ⇒ no attempt** (hard law). 

2. **Effector call uses stable external idempotency token**

   * N5 → N6 (J8) always includes the same deterministic token derived from the semantic key.
   * This is what makes retry safe even under timeouts/UNKNOWN. 

3. **Receipt is classified into (COMMITTED / NOT_COMMITTED / UNKNOWN)**

   * N6 → N5 (J9) returns `ExecutionReceipt(commitment_state, error_category, retry_advice)`.

4. **AttemptRecord appended (durable truth)**

   * N5 → N4 (J10) appends AttemptRecord with classification, evidence, and retryability.

5. **Retry scheduling decision is derived, not improvised**
   **Designer pin:** retry scheduling is decided by **ExecutionPostureSnapshot + error_category + attempt_no**:

   * `max_attempts` per action_type
   * backoff curve (e.g., exponential with jitter)
   * retryable categories allowlist
   * “stop now” categories (caps, policy)

6. **Next attempt starts only when ledger re-issues a new permit**

   * N4 grants new `ExecutePermit(attempt_no+1)` once `next_retry_at_utc` is reached and posture still allows execution.

## Boundedness rules (non-negotiable)

### L1.2 “At most one in-flight attempt”

For any `(semantic_key)`, N4 enforces:

* either **no in-flight attempt**
* or exactly **one** in-flight attempt owner (`attempt_id`, `permit_token`)

No parallel retries. Ever. 

### L1.3 Terminalization (how L1 stops)

L1 must end in one of these terminal conditions for the semantic key:

* **EXECUTED** (COMMITTED) → terminal success
* **DENIED** (policy hard deny; not a retry outcome)
* **FAILED-final** (retryable=false or max_attempts reached or posture prohibits further attempts)

**Designer pin:** `UNKNOWN` commitment state cannot become EXECUTED without a resolving receipt (either idempotent retry confirms COMMITTED, or status probe confirms). Until then, it remains retryable failure. 

### L1.4 Posture interaction (L4 feeds L1)

If N2 switches to drain/kill/disable during L1:

* **Drain:** no new permits issued; in-flight attempt may finish; scheduled retries pause.
* **Kill/Disable:** no new permits issued; pending retries are terminalized as FAILED-final with explicit reason `STOPPED_BY_POSTURE` (append-only).
  No silent disappearance. 

---

# L2 — Publish retry / outbox loop

`N7 ↔ N4`

## What L2 exists to guarantee

* Once an outcome exists, it becomes an admitted bus fact **eventually** (or is escalated explicitly), even if IG/EB is down temporarily.
* Publish retries do **not** cause re-execution.
* The same outcome is always published under the same `outcome_event_id` (convergence).

## Loop mechanics (authoritative)

### L2.1 Publish cycle steps

1. **Outcome exists in ledger/outbox**

* Created from execution (J11) or denial (J5) or duplicate canonical (J7).

2. **N7 fetches `OutcomeToPublish(outcome_event_id, immutable payload)` from N4** (J12)

3. **N7 submits to IG**

* Ig returns `ADMIT | DUPLICATE | QUARANTINE` with receipt.

4. **N7 reports `PublishReceipt` back to N4** (J12)

* If ADMIT/DUPLICATE: ledger marks `publish_state=ADMITTED` and stores bus coordinates when available.
* If transient failure (no receipt): ledger marks `publish_state=PENDING_RETRY`, increments attempt count, schedules next publish attempt.

## Stop conditions (how L2 ends)

* **Success:** ADMIT or DUPLICATE (both are terminal success for publish). 
* **Hard stop:** QUARANTINE → terminal incident state.

## Hard rules (non-negotiable)

### L2.2 Stable outcome identity

**Designer pin:** outbox retry always uses the **same `outcome_event_id`**. Never mint a new ID just because publish is retried. 

### L2.3 QUARANTINE is a P0

If IG returns QUARANTINE for an ActionOutcome:

* set `publish_state=QUARANTINED`
* surface incident immediately (via N8)
* AL shifts to controlled posture (often drain/kill new executions) until corrected
  Because quarantine of outcomes breaks audit closure. 

### L2.4 Publish loop cannot trigger execution

Publisher never calls orchestrator. Ever.

---

# L3 — Duplicate suppression loop (at-least-once reality)

`N1 → N3 → N4 → (N7 optional)`

## What L3 exists to guarantee

* At-least-once delivery and replay/backfill never multiply side effects.
* Reprocessing the same semantic intent converges to the same canonical outcome.

## Loop mechanics (authoritative)

### L3.1 Duplicate classes (both must be handled)

* **Boundary duplicate:** same envelope `event_id` delivered again.
* **Semantic duplicate:** different `event_id`, same `(semantic_key)`.

N1 normalizes both; N4 is the authority that suppresses semantic duplicates. 

### L3.2 Duplicate handling outcomes from N4

After N3 ALLOW → N4 receives the semantic key and returns one of:

* **CanonicalOutcomeRecord** (terminal exists) → N7 may republish only if not admitted; otherwise NO-OP
* **InFlightNoOutcomeYet** (attempt running) → authoritative v0 handling = **NO-OP**
* **ExecutePermit** (not a duplicate; normal processing continues)
* **KeyConflict** (fingerprint mismatch) → fail-closed failure outcome, no execution

### L3.3 “No new truth” rule

**Designer pin:** duplicates do not create additional semantic outcome history. At most, they can help converge publishing if the canonical outcome exists but isn’t admitted yet (L2). 

---

# L4 — Governed change loop (inside AL boundary)

`(control inputs) → N2 → (updates) N3/N5`

## What L4 exists to guarantee

* AL behavior changes (allowlists, kill/drain, caps) happen **explicitly**, are **attributable**, and don’t require code changes.
* Environment ladder compliance: local/dev/prod differ by profile strictness, not semantics. 

## Loop mechanics (authoritative)

### L4.1 Control inputs are explicit snapshots, not ad-hoc flags

N2 maintains:

* `ActivePolicySnapshot` (J2) for N3 authz decisions
* `ExecutionPostureSnapshot` (J3) for N5 execution constraints

Each has:

* id/rev
* digest
* loaded_at
* effective scope

### L4.2 Atomicity + traceability rule

**Designer pin:** N2 must change snapshots in a way that downstream can attribute decisions:

* Every DENIED includes `policy_rev` used.
* Every attempt/outcome includes the `policy_rev` and `exec_profile_rev` that were in force.
* If a change occurs mid-flight, it affects **new permits** and **new authorizations** going forward, but does not rewrite history.

### L4.3 Posture semantics (what changes do)

* **Kill switch / policy deny:** N3 routes to DENIED outcomes (via J5), no execution.
* **Drain:** N5 stops requesting new permits; in-flight completes; outbox continues.
* **Caps:** N5 reduces concurrency/rate; retries may be delayed but remain explicit.

### L4.4 Fail-closed default

If N2 cannot load policy/control posture reliably:

* AL must not execute (fail closed)
* outcomes for incoming intents become FAILED(retryable) with explicit reason (not silent drop). 

---

## One-page “loop invariants” to carry forward

* **L1:** permits gate attempts; retries sequential + bounded; UNKNOWN never becomes EXECUTED without resolution.
* **L2:** outbox republish with stable outcome_event_id until ADMIT/DUPLICATE; QUARANTINE is P0.
* **L3:** duplicates converge; no re-execution; no new truth; in-flight duplicates NO-OP.
* **L4:** governed, versioned snapshots drive behavior; fail-closed; changes are attributable and don’t rewrite history.  

---

Locked — illuminating **L5–L7** with clear **boundary discipline**: these loops *touch* AL internally, but the “decide to change” part lives outside AL (Run/Operate + Obs/Gov), per your platform pins. AL’s internal responsibility is to (a) surface the right signals, (b) accept explicit posture snapshots, and (c) behave deterministically once posture changes.  

I’ll cover each loop as: **purpose → mechanics → stop conditions → drift bans**.

---

# L5 — Backpressure / lag safety loop

`N8 observes lag/errors → external Run/Operate/Gov acts → N2 posture updates → N5 caps/drain`

## What L5 exists to guarantee

When AL is unhealthy (lagging, erroring, downstream dependencies failing), the platform can **reduce harm and regain stability** without:

* changing semantics,
* silently dropping work,
* or violating effectively-once execution.

This is the “operability loop” that makes AL production-safe.

## Loop mechanics (authoritative)

### L5.1 Detection (inside AL: N8 tap)

N8 continuously observes *at least* these signals (the “trigger set”):

* **consumer lag** (EB partitions / offsets behind)
* **outbox backlog** (pending outcomes to publish)
* **publish failures** (IG unreachable, repeated retries)
* **execution failures** (retryable rate spikes, UNKNOWN rate spikes)
* **dependency health** (effector timeouts, dependency down)
* **denied-by-policy spikes** (indicates misconfig or attack)

All are emitted as telemetry with correlation keys (event_id, semantic_key, policy_rev, attempt_no). 

### L5.2 Decision (outside AL)

**Designer pin:** N8 does *not* decide “drain” or “kill.” That decision is made by:

* **Observability/Governance corridor checks** and/or
* **Run/Operate operator actions**
  because outcome-affecting changes must be governed and auditable.

### L5.3 Actuation (inside AL via N2 → N5/N3)

The external decision results in explicit posture snapshots:

* `ExecutionPostureSnapshot` (J3) to N5: caps/drain/safe-mode
* possibly updated `ActivePolicySnapshot` (J2) to N3: kill scopes, disabled action types

N5 then:

* **caps** concurrency/rate for new attempts
* **pauses** issuing new permits (drain)
* **halts** new execution for killed scopes (policy deny path via N3)

Outbox publish (N7↔N4) continues regardless (you want to flush truth even when execution is reduced). 

## Stop conditions (how L5 ends)

* Health returns within corridor thresholds → external plane lifts caps/drain → N2 updates posture snapshots back toward normal.
* Or in severe incidents → kill switch remains until fixed, then rolled back.

## Drift bans (non-negotiable)

* **Banned:** N8 directly throttling N5 (telemetry is not control).
* **Banned:** auto-drain/auto-kill inside AL without a governed control signal.
* **Banned:** “fix lag by dropping intents.”
  Dropping violates “no silent drops” + replay safety.

---

# L6 — Async closure loop (optional)

`N6 emits callback → (via IG/EB) → N9 → N4/N7`

## What L6 exists to guarantee

If some actions have delayed completion/confirmation, the platform can:

* ingest callback facts safely,
* correlate them deterministically to the action,
* and append closure outcomes **immutably** without rewriting history.

## Loop mechanics (authoritative)

### L6.1 Callback ingress (outside AL boundary, but required)

Callbacks are just producer traffic:

* must enter through **IG → EB**
* must be **canonical envelope** conformant
* must be producer-allowlisted (preferably enforced at IG; AL still fail-closes)

### L6.2 Normalize + correlate (N9 → N4)

N9 extracts a correlation basis and asks N4 to resolve to a semantic key using the precedence we pinned:

1. semantic_key in callback
2. effector_request_id
3. parent_intent_event_id
   No “search by time,” no guessing.

If correlation fails → **OrphanCallback** (routes to triage loop L7 / N10; does not change action state).

### L6.3 Append closure (N4) and publish (N7 via J12)

* N4 dedupes callback ingestion (callback_event_id as a dedupe key)
* N4 appends a closure record (append-only)
* N7 publishes the closure ActionOutcome using the outbox mechanism (stable outcome_event_id for the closure record)

**Designer pin:** closure is always an appended record; no mutation of earlier outcomes. 

## Stop conditions

* Callback applied once (idempotent).
* Terminal closure recorded (e.g., CONFIRMED / REJECTED / COMPLETED).

## Drift bans

* **Banned:** callback directly triggering execution.
* **Banned:** callback mutating prior outcomes.
* **Banned:** correlation by scanning storage or “latest request.”
  All violate determinism + append-only posture.

---

# L7 — Quarantine triage loop (optional but production-real)

`N7 sees QUARANTINE → N8 flags incident → external triage → fixes → reprocess → intake`

## What L7 exists to guarantee

Quarantine is first-class: when something cannot be admitted safely (especially **ActionOutcomes**), the system:

* doesn’t silently drop,
* preserves evidence for diagnosis,
* and supports controlled remediation and reprocessing.

This is essential for production readiness. 

## Loop mechanics (authoritative)

### L7.1 Detection inside AL

There are two main quarantine “entry points” relevant to AL:

1. **Outcome quarantined** (IG returns QUARANTINE on ActionOutcome publish)
   This is **P0**: it threatens audit closure. N7 reports QUARANTINE receipt + reasons to N4 and emits an incident telemetry event to N8 immediately.

2. **Callback/orphan quarantine** (optional)
   Untrusted/orphan callbacks are surfaced for triage; typically they should be quarantined upstream at IG if producer allowlist is correct.

### L7.2 External triage (outside AL)

Triage actions are privileged and governed:

* inspect quarantine receipts/evidence
* classify root cause: schema evolution, producer identity mismatch, policy misconfig, joinability problems, bug
* apply fix: policy rev change, producer fix/redeploy, schema allowlist update, reprocess declaration

### L7.3 Remediation re-entry (must follow IG)

Reprocess/release always re-enters through **IG**:

* if bytes/meaning unchanged → same event_id resubmitted → IG ADMIT/DUPLICATE deterministically
* if corrected/transformed → new event_id with lineage link to the quarantined candidate

### L7.4 AL internal cooperation

AL’s internal responsibilities are:

* preserve publish/outbox state (`publish_state=QUARANTINED`)
* surface the incident strongly (N8)
* optionally shift to controlled posture (drain/kill) until outcomes can be admitted again
* allow safe republish of existing outcome_event_id after fixes (no re-execution)

## Stop conditions

* Quarantined item is either:

  * admitted (as-is or corrected successor) and closure completed, or
  * rejected permanently with explicit reason and governance record

## Drift bans

* **Banned:** “force admit” inside AL (bypassing IG).
* **Banned:** editing quarantined payload/outcome in place.
* **Banned:** continuing execution while outcomes are being quarantined at scale (must trigger L5/L4 posture responses).
  All violate trust boundary + audit integrity.

---

## One-line “loop contract” to carry forward

* **L5:** N8 detects; external plane decides; N2 applies posture; N5 caps/drains safely.
* **L6:** callbacks are ingested via IG/EB, correlated deterministically, and closure is appended + published via outbox.
* **L7:** quarantine triggers incident + governed triage; remediation re-enters through IG; no bypasses, no edits.

If you want the next deepening step: we can now define the **minimal internal state variables** each loop requires (e.g., `in_flight`, `next_retry_at`, `publish_state`, `posture_rev`, `callback_dedupe_set`) without opening full implementations.

---

Yes — let’s pin the **non-joins (forbidden edges)** now, both **inside AL** and **across AL’s boundary**, so we don’t accidentally “simplify” into drift later.

## A) Internal non-joins inside AL (between subnetworks)

1. **N1 Intake → N5 Orchestrator (direct execute) is forbidden**
   *Why:* execution must be gated by AuthZ + Ledger permit.
   *Allowed:* `N1 → N3 → N4 → N5`. 

2. **N3 AuthZ → N5 (execute without ledger) is forbidden**
   *Why:* “allowed” ≠ “safe to execute”; idempotency permit is mandatory.
   *Allowed:* `N3 → N4 → N5`. 

3. **N7 Publisher → N5/N6 (publish triggers execution) is forbidden**
   *Why:* publish retries must never create side effects.
   *Allowed:* publish retries are `N7 ↔ N4` outbox only. 

4. **N6 Effector → IG/EB (effectors publishing “truth”) is forbidden**
   *Why:* IG is the front door; AL publishes outcomes as canonical traffic.
   *Allowed:* `N6 → N5 → N7 → IG → EB`.

5. **N8 Observability → N3/N4/N5 (telemetry as a control path) is forbidden**
   *Why:* Obs/Gov must not change behavior “by stealth”; only explicit control surfaces.
   *Allowed:* governance decisions activate explicit posture/policy snapshots via N2.

6. **N10 Remediation → N1 “inject fixed payload” is forbidden**
   *Why:* would bypass IG’s trust boundary and audit the wrong thing.
   *Allowed:* remediation re-enters through **IG** (release/reprocess), not via internal injection.

7. **N9 Callbacks → N5 “start/redo execution” is forbidden**
   *Why:* callbacks append closure; they don’t cause new side effects.
   *Allowed:* `N9 → N4 (correlate+append) → N7 (publish closure)`. 

8. **N4 Ledger ↔ “use EB as the ledger” is forbidden**
   *Why:* EB retention/replay is not an idempotency database; AL must have durable `actions` truth.
   *Allowed:* N4 is backed by the Actions DB; EB is transport + replay.

9. **Any subnetwork mutating prior outcomes is forbidden**
   *Why:* outcomes are immutable; history is append-only (including closure).
   *Allowed:* append a new record; never edit/overwrite.

## B) Boundary non-joins (AL must NOT connect to these external planes)

1. **AL ↔ Data Engine (direct reads/gates/outputs) is forbidden**
   *Why:* engine truth flows via SR + IG; AL acts on ActionIntents only.

2. **AL ↔ Scenario Runner (world selection/readiness) is forbidden**
   *Why:* SR is readiness authority; AL must not “pick the run.” 

3. **AL → EB bypassing IG is forbidden**
   *Why:* IG is the trust boundary for all traffic (including AL outcomes).

4. **AL querying OFP/IEG to “decide” whether to execute is forbidden**
   *Why:* DF decides; AL executes/refuses via policy only (don’t create a second decision engine).

5. **AL writing Case timelines or Labels directly is forbidden**
   *Why:* Case Mgmt + Label Store own those truths. AL emits outcomes; others consume by-ref.

6. **AL using DLA as a coordination store is forbidden**
   *Why:* DLA is the flight recorder, not an execution ledger.

## C) Environment-ladder non-joins (local “shortcuts” are banned)

These are forbidden even in local/dev:

* DF/UI calling AL directly (must still be IG→EB mediated).
* Disabling idempotency/ledger “because it’s local.”
* Using “latest”/time-based discovery instead of pinned IDs/refs.
* Allowing silent mutation or silent drops in local.

If you want, next we can pin a **single-page “Allowed edges inside AL”** (the complement of this list) so implementers have a crisp internal wiring guardrail.

---

## USER: PAUSE FOR REFLECTION

Yep. Here’s the **designer reflection / drift-guard recap** of what we’ve established so far for **Actions Layer (AL)**—as a vertex in the larger platform graph **and** as its own internal network with **opaque** internal nodes.

I’m going to restate this as a set of **pinned anchors** + **what’s inside the vertex (still opaque)** + **the internal joins/paths/loops we’ve now illuminated** + **non-joins**. This is the “carry-forward mental model” so we don’t drift.   

---

## 1) What is design-authoritative in this chat

* **Platform blueprint pins** are hard law: truth ownership, trust boundary (IG), replay truth (EB offsets), audit flight recorder (DLA), “no PASS → no read”, by-ref posture, explicit degrade and governed change. 
* **Canonical Event Envelope** is the boundary shape for bus-visible traffic (required header fields, pins). 
* **Environment ladder** is a hard law: same graph + semantics in local/dev/prod; differences only in operational envelope (security strictness, retention, HA, obs depth). 

Everything we designed for AL is constrained by those.

---

## 2) AL as a vertex in the platform graph (outer boundary anchor)

### AL’s role (pinned)

* **AL is the only side-effect executor.** DF/Case/Ops only request actions. 
* AL is the system-of-record for **ActionOutcome + attempt history**, and must be **effectively-once** under at-least-once delivery using uniqueness scope:
  **`(ContextPins, idempotency_key)`**. 

### AL’s ingress/egress (pinned edges)

* **Ingress:** ActionIntent arrives as traffic via **IG → EB → AL** (no bypass). 
* **Egress:** ActionOutcome leaves as traffic via **AL → IG → EB** (no bypass). 
* Everything bus-visible is **canonical-envelope conformant**. 

### The platform loops AL participates in (outer meaning)

* **L1 (platform):** decision → intent → outcome → DLA closure. 
* **L2 (platform, optional but common):** outcomes become facts feeding future context (IEG/OFP/DF). 
* **L3 (platform):** outcomes/evidence → cases → labels → offline learning → registry → DF → new actions. 
* **L4 (platform):** governed change / safety (Run/Operate + Obs/Gov) affects AL via explicit posture snapshots. 

---

## 3) Environment ladder constraint (deployment direction anchor)

* **No semantic forks** across envs: no “local shortcuts” like DF calling AL directly, skipping IG, disabling idempotency, or mutating outcomes. 
* We pinned **profile knobs** into two buckets:

  * **Policy knobs (outcome-affecting):** allowlists, kill/drain, action enablement, quarantine posture, minimum provenance requirements (must be versioned + attributable).
  * **Wiring knobs (non-semantic):** endpoints, timeouts, concurrency, infra. 

This stays true while we open internals.

---

## 4) Inside AL: first-layer internal subnetworks (still opaque boxes)

We split AL into a small, drift-resistant set of internal subnetworks:

* **N1** Intake & Normalize
* **N2** Policy & Control Plane Adapter
* **N3** Authorization Gate
* **N4** Idempotency & Outcome Ledger (incl. outbox publish state)
* **N5** Execution Orchestrator
* **N6** Effector Adapters
* **N7** Outcome Assembly & Publisher
* **N8** Observability & Governance Hooks (tap)
* **N9** Async Callback Intake & Correlator (optional)
* **N10** Quarantine/Remediation Surface (optional)

Key point: these boxes are **not implementation mandates**, but the network responsibilities are pinned.

---

## 5) Internal joins J1–J16 (now illuminated meanings)

We illuminated internal joins as **allowed information handshakes** with explicit bans.

### J1–J4 (front of AL)

* **J1 N1→N3:** `NormalizedIntent` (parse + canonicalize fields, no decisions).
* **J2 N2→N3:** `ActivePolicySnapshot` (authz rules + policy_rev identity).
* **J3 N2→N5:** `ExecutionPostureSnapshot` (drain/caps/disabled action types, etc.).
* **J4 N3→N4:** `AuthorizedIntent` with **semantic_key** + **intent_fingerprint** + policy stamps.

### J5–J8 (deny/permit/duplicate/execute boundary)

* **J5 N3→N7:** `DeniedDecision`, but **designer-corrected**: denial must still be **canonicalized via ledger/outbox** so duplicates don’t mint new denied outcomes.
* **J6 N4→N5:** `ExecutePermit` (exclusive attempt grant + permit_token).
* **J7 N4→N7:** duplicate/canonical outcome record or in-flight no-op; includes conflict signalling.
* **J8 N5→N6:** `ExecutionCommand` with **external idempotency token** derived from semantic_key.

### J9–J12 (danger triangle: receipt → ledger → outcome → publish)

* **J9 N6→N5:** `ExecutionReceipt` with commitment state (COMMITTED / NOT_COMMITTED / UNKNOWN) + evidence refs.
* **J10 N5→N4:** `AttemptRecord` append-only (durable attempt truth, crash-window seal).
* **J11 N5→N7:** `OutcomeDraft` (no outcome-id minting in N5).
* **J12 N7↔N4:** outbox publish handshake: `OutcomeToPublish` ↔ `PublishReceipt(ADMIT/DUPLICATE/QUARANTINE)`; QUARANTINE of outcomes is **P0**.

### J13–J16 (cross-cutting, optional, remediation)

* **J13 (N1..N7)→N8:** telemetry tap only (**never** a control path).
* **J14 N9→N4:** callback correlation (designer-chosen target) with strict correlation precedence; no guessing.
* **J15 N9→N4→N7:** closure is **append-only** via ledger/outbox (no mutation; no bypass).
* **J16 N10↔(N1/N7/N2):** remediation is read-mostly + safe republish + governed change requests; never injection/bypass.

---

## 6) Internal paths P1–P10 (now illuminated semantics)

We pinned the “canonical sequences” AL must follow:

* **P1:** new intent executes successfully: normalize → authz allow → ledger permit → effector call → attempt recorded → outcome drafted → outbox publish → receipt stored.
* **P2:** denied by policy: normalize → authz deny → canonical denied outcome via ledger/outbox → publish.
* **P3:** semantic duplicate with canonical outcome: ledger returns canonical outcome; publish only if not admitted; otherwise no-op.
* **P4:** duplicate while in-flight: authoritative v0 behavior = **NO-OP** (never start another attempt, don’t spam “pending”).
* **P5:** retryable execution failure: sequential attempts only; attempt history appended; FAILED(retryable) outcomes allowed; terminalize at bounds.
* **P6:** publish failure after execution: outbox republish with same outcome_event_id; never re-execute.
* **P7:** drain/kill posture:

  * drain = stop starting new attempts, allow in-flight + outbox flush;
  * kill/disable = explicit deny (or terminalize retries) with attributable reason.
* **P8:** crash/restart recovery ordering pinned: load posture → load ledger/outbox → republish pending outcomes → reconcile in-flight safely → resume.
* **P9:** async callback closure (optional): correlate → append closure record → publish via outbox.
* **P10:** quarantine remediation touchpoint (optional): inspect → safe republish or governed change → re-entry through IG.

---

## 7) Internal loops L1–L7 (now illuminated laws)

* **L1 Retry loop:** sequential, permit-gated, bounded; UNKNOWN never becomes EXECUTED without resolution.
* **L2 Outbox publish loop:** stable outcome_event_id, retry until ADMIT/DUPLICATE; QUARANTINE=P0.
* **L3 Duplicate suppression loop:** duplicates converge; in-flight duplicates NO-OP; conflicts fail closed.
* **L4 Governed change loop:** N2 supplies versioned snapshots; fail-closed if posture unknown; decisions attributable.
* **L5 Lag/backpressure safety loop:** N8 detects; external plane decides; N2 applies; N5 caps/drains; no drops.
* **L6 Async closure loop (optional):** append-only closure via ledger/outbox; strict correlation; no execution triggered.
* **L7 Quarantine triage loop (optional):** quarantine triggers incident + governed triage; remediation re-enters via IG; no bypass.

---

## 8) Non-joins (forbidden edges) we pinned

### Inside AL

* Publisher must **never** trigger execution.
* Observability must **never** be a control path.
* Callbacks must **never** trigger execution; only append closure.
* Remediation must **never** inject fixed payloads into intake; must re-enter via IG.
* Ledger must **never** be “implemented by EB” (EB ≠ idempotency DB).

### Outside AL

* No AL↔Engine, no AL↔SR, no AL→EB bypassing IG. 
* AL must not become a decision engine (no OFP/IEG queries to decide execution).
* AL must not write Case timelines or labels directly (truth ownership stays put). 

### Environment ladder bans

* No local/dev semantic shortcuts; profiles only. 

---

## 9) The “don’t drift” checklist we carry into deeper illumination

When we open any internal box next, it must **not** violate these invariants:

1. **Execution only under ledger permit** (no permit → no side effect).
2. **Semantic identity = (ContextPins, idempotency_key)** governs effectively-once.
3. **Outcomes immutable, history append-only** (including closure).
4. **Outbox republish solves publish failures; never re-execute.**
5. **IG is always the front door for traffic** (intents + outcomes).
6. **Governed change comes only through explicit posture snapshots** (no stealth toggles).
7. **Same semantics across env ladder** (differences = profile strictness, not meaning). 

---

Yep — this is the right moment to **pin the deployment + environment-ladder posture for AL’s inner network**, so Codex can implement without accidentally inventing “local-only semantics” or breaking the outbox/idempotency story.

Below are the **designer pins** I want locked *before* we open N1–N10.

---

## 1) Deployment unit shape for AL

### AL is an always-on hot-path service

AL runs continuously (dev/prod), consuming ActionIntents and emitting ActionOutcomes.

### Internal nodes are logical — but if you split processes, the boundary rules must hold

Default (v0): **single AL service binary** containing N1–N8, with optional N9/N10 disabled until needed.

Allowed later (scale/ops): split into **two cooperating runtime roles** *sharing the same `actions` DB*:

* **AL-Executor role:** N1–N6 (+ writes to outbox in N4), never publishes to IG/EB directly.
* **AL-Publisher role:** N7 (+ reads outbox from N4), never calls effectors or starts attempts.

**Hard pin:** Publisher must never trigger execution; execution must never depend on publisher being up (outbox handles it). This preserves P6/P8 recovery semantics.

---

## 2) Stateful substrate map for AL (what must exist and persist)

### Authoritative DB truth: `actions` schema

AL must persist **idempotency + outcome history** in Postgres under an `actions` schema (authoritative truth).
This is the keystone that makes:

* duplicates safe,
* publish retry safe,
* restart recovery safe.

### Optional object store evidence blobs

If you store larger execution evidence, it goes by-ref into the object store (not the bus payload). The platform already pins the object store prefixes and includes `profiles/` and `gov/` as first-class areas. 

**Designer pin:** evidence blobs are optional; **idempotency + outcomes are not**.

---

## 3) Environment ladder pins (AL-specific)

### What must be identical across local/dev/prod

Local/dev/prod must run the **same graph + rails/join semantics**; only operational envelope differs.

For AL this means (non-negotiable everywhere):

* Intents/outcomes still flow through **IG/EB** (no direct calls).
* Canonical envelope semantics remain (required `event_id,event_type,ts_utc,manifest_fingerprint`).
* Idempotency is enforced by `(ContextPins, idempotency_key)`; duplicates never re-execute.
* Outcomes are immutable + append-only history.

### What’s allowed to differ (the “knobs”)

These are allowed to vary by environment profile (same semantics, different strictness/scale): scale, retention/archive, security strictness, reliability posture, observability depth.

---

## 4) The AL environment profile knobs you should expect

### A) Policy/profile artifacts (outcome-affecting, must be versioned)

These should live as versioned “policy/profile revisions” (promoted like code), and AL should always report which rev it used.

**Minimum AL policy knobs:**

* Action allowlists: `(actor_principal, origin, action_type, scope)`
* Kill switch scope rules / action disablement
* Retry budgets + retryable error categories per action_type
* Quarantine severity rules (esp. “Outcome quarantined = P0”)
* Minimum required intent fields (fail-closed stance)

### B) Execution posture knobs (operational envelope)

* max concurrency / rate limits per action_type
* drain mode toggle (pause new attempts)
* safe mode (tight caps + conservative retries)
* effector timeouts/circuit breaker settings (wiring, but may be constrained by posture)

### C) Wiring knobs (non-semantic)

* EB endpoints / consumer group IDs
* IG endpoint
* Postgres endpoint
* object store endpoint (if evidence enabled)
* OTel exporter endpoint

---

## 5) Startup/readiness pins (deployment-critical)

**Designer pin:** AL must boot in a restart-safe order consistent with our P8 recovery:

1. load policy/control posture (N2)
2. connect to `actions` DB (N4)
3. run outbox republish loop (N7 via J12)
4. reconcile in-flight attempts safely (N5 with N4)
5. only then start/continue consuming new intents

This keeps “executed-but-not-published” from turning into “re-executed after restart.”

**Readiness pin:** AL must not declare itself “ready to execute” unless:

* policy snapshot is loaded (or fail-closed posture is active),
* `actions` DB is reachable,
* outbox loop is alive (or explicitly disabled only in local *with semantics preserved*—not recommended).

---

## 6) Scaling pins (how AL scales without breaking semantics)

* Horizontal scaling is allowed (multiple AL replicas in one consumer group), but **exclusivity is enforced by the ledger permit**, not by “hoping partitions don’t collide.”
* Prefer partitioning action intents by semantic identity to reduce contention; IG already stamps deterministic partition keys for admitted events. 

---

## 7) “Production-shaped local” is mandatory for AL correctness

Local should run a real substrate (Kafka-ish EB, S3-ish object store, SQL DB, OTel-ish obs) so AL’s semantics are exercised under real at-least-once and durable dependencies.

And operationally, Codex needs exactly what your deployment notes call out:

* one “bring up infra” command (Compose),
* a local profile with endpoints + policy revs,
* an end-to-end golden-flow script that includes DF→AL→DLA.

---

## 8) Promotion lanes (prevents drift later)

Pin this now: promotion is *artifact selection*, not behavior forks:

* **Code artifacts** are immutable build-once/run-anywhere
* **Policy/profile revisions** are versioned, approved, activated via governance facts
* Runtime units report which policy rev they’re using

---

Yes — illumination should **only reveal internal machinery** that satisfies the already-pinned joins/paths/loops; it must not change the network.

### Nodes (subnetworks) we’ve pinned

1. **N1** Intake & Normalize
2. **N2** Policy & Control Plane Adapter
3. **N3** Authorization Gate
4. **N4** Idempotency & Outcome Ledger (incl. outbox publish state)
5. **N5** Execution Orchestrator
6. **N6** Effector Adapters
7. **N7** Outcome Assembly & Publisher
8. **N8** Observability & Governance Hooks
9. **N9** Async Callback Intake & Correlator *(optional)*
10. **N10** Quarantine/Remediation Surface *(optional)*

### Recommended illumination order (drift-resistant)

1. **N4 — Ledger/Idempotency/Outbox** (keystone for permits, duplicates, crash safety, publish retry)
2. **N7 — Outcome Assembly & Publisher** (outbox mechanics, publish receipts, QUARANTINE=P0 handling)
3. **N5 — Execution Orchestrator** (attempt lifecycle, retry semantics, UNKNOWN handling, posture interaction)
4. **N6 — Effector Adapters** (external idempotency token use, receipt taxonomy, evidence refs)
5. **N3 — Authorization Gate** (deny vs fail, policy attribution, explainability boundaries)
6. **N2 — Policy & Control Adapter** (profile rev loading, kill/drain/caps semantics, fail-closed posture)
7. **N1 — Intake & Normalize** (schema/version handling, normalization failures → outcome paths)
8. **N8 — Observability & Gov Hooks** (correlation keys, golden signals, non-blocking tap rules)
9. **N9 — Async Callback Intake** *(only if enabling async actions soon)*
10. **N10 — Quarantine/Remediation Surface** *(only if you want a first-class triage UI/workflow now)*

If you want the tightest path to a buildable v0, we start with **N4** next.

---

Absolutely. We’ll **open N4 (Idempotency + Outcome Ledger + Outbox)** and expose the machinery that makes **J4/J6/J7/J10/J12** (and optionally **J14/J15**) possible—**without changing any network semantics** we already pinned: semantic identity = `(ContextPins, idempotency_key)`, permit-gated execution, append-only outcome history, outbox publish retry, crash-safe replay, and IG/EB mediation.  

---

# N4 mission and authority

## What N4 is authoritative for

N4 is AL’s **system-of-record** for:

* **semantic idempotency**: one execution lineage per `(ContextPins, idempotency_key)`
* **attempt history**: append-only attempt facts
* **canonical outcome history**: append-only outcomes, with a deterministic “canonical outcome” selection rule
* **publish state** (outbox): whether each outcome has been admitted to the bus (ADMIT/DUPLICATE), and bus coordinates if known

This is what makes:

* duplicates safe (L3),
* retries safe (L1),
* publish failures safe (L2),
* restarts safe (P8),
* and backfills safe (P5/L6). 

## What N4 is NOT

* Not a decision engine (DF decides)
* Not an authorization engine (N3 decides)
* Not a publisher (N7 publishes)
* Not an effector client (N6 executes)

---

# N4 internal subnetworks (inside N4)

Think of N4 as a *mini-network* of sub-boxes (still internal, but now we reveal them):

1. **K1 Semantic Key Registry**
   Owns the canonical row for each `semantic_key` and stores the “first-seen” intent fingerprint.

2. **K2 Conflict Detector**
   Detects `semantic_key` collisions (same key, different intent fingerprint) and fail-closes.

3. **K3 Permit & Lease Manager**
   Grants **exclusive ExecutePermits** with TTL and prevents parallel attempts.

4. **K4 Attempt Journal**
   Append-only attempt records (COMMITTED/NOT_COMMITTED/UNKNOWN + evidence refs).

5. **K5 Outcome Registry & Canonicalizer**
   Append-only outcomes (DENIED / FAILED / EXECUTED / closure), with deterministic canonical selection.

6. **K6 Outbox Scheduler**
   Tracks publish_state per outcome, retries publish, stores IG receipts and bus coordinates.

7. **K7 Correlation Index** *(optional but cheap and high value)*
   Maps `effector_request_id` and `intent_event_id` to `semantic_key` (for callbacks and debugging).

8. **K8 Callback Dedupe + Closure Appender** *(only if async enabled)*
   Dedupes callbacks and appends closure outcomes (append-only, no mutation).

9. **K9 Recovery Scanner**
   Startup/resume views: pending outbox, expired leases, retry-due actions.

All of this is typically backed by a single **Postgres “actions” schema** (or equivalent durable store). 

---

# N4 core data model (conceptual tables)

Not a full schema spec—just the “must exist” records and keys.

## 1) `action_keys` (one row per semantic key)

**Primary key:** `semantic_key_hash` (stable digest of `(ContextPins, idempotency_key)`)

Stores:

* `semantic_key_json` (canonicalized pins + idempotency_key, for debug)
* `manifest_fingerprint` (first-class column; common partition/filter) 
* `intent_fingerprint` (digest of canonical intent fields)
* `first_intent_event_id` (optional)
* **derived state fields** (convenience only; truth remains append-only logs):

  * `state`: `ACTIVE | IN_FLIGHT | TERMINAL | CONFLICT`
  * `in_flight_attempt_id`, `lease_expires_at`
  * `terminal_outcome_id` (if terminal exists)
  * `latest_outcome_id` (for convenience)
  * `next_retry_at` (if scheduled)

> **Designer pin:** `semantic_key_hash` is the indexing handle; `semantic_key_json` is the human/audit handle.

## 2) `attempts` (append-only journal)

Keyed by:

* `attempt_id` (uuid)
* `semantic_key_hash`
* `attempt_no` (monotonic per semantic key)

Stores:

* `permit_token_hash` (to enforce exclusive writer)
* `commitment_state`: `COMMITTED | NOT_COMMITTED | UNKNOWN`
* `error_category`, `result_code`, `retryable`, `next_retry_at`
* `effector_adapter_id`, `effector_request_id`, `evidence_refs[]`
* timestamps (`started_at`, `finished_at`)

## 3) `outcomes` (append-only immutable outcomes)

Keyed by:

* `outcome_id` (uuid)
* `semantic_key_hash`
* `outcome_seq_no` (monotonic or time-ordered per key)

Stores:

* `outcome_event_id` (stable envelope event_id for publishing)
* `decision`: `DENIED | FAILED | EXECUTED | CLOSURE_*`
* `attempt_id` / `attempt_no` (nullable for DENIED)
* `payload_json` (immutable; by-ref evidence)
* `payload_digest`
* `policy_rev` + optional `exec_profile_rev`
* timestamps (`outcome_ts_utc`)

## 4) `outbox` (publish scheduler, one row per outcome)

Keyed by:

* `outcome_id` (FK to outcomes)

Stores:

* `publish_state`: `PENDING | ADMITTED | QUARANTINED`
* `publish_attempts`, `next_publish_at`, `last_publish_error`
* `ig_receipt_ref` (or receipt id)
* optional bus coordinate: `(topic, partition, offset)` when known

## 5) `intent_event_map` *(optional but recommended)*

Maps observed `intent_event_id` → `semantic_key_hash`.

## 6) `effector_request_map` *(optional but recommended)*

Maps `effector_request_id` → `semantic_key_hash` (+ attempt_id).

## 7) `callback_dedupe` *(only if async)*

Maps `callback_event_id` → `semantic_key_hash` (ensures closure append is idempotent).

## 8) `conflicts` *(optional but useful)*

Records key conflicts (`semantic_key_hash`, old fingerprint, new fingerprint, first_seen, last_seen).

---

# N4 state machine for a single semantic key

This is the **behavioral core** of N4 (what we’ll rely on when opening N5/N7 later).

```
NEW (no row)
  |
  | on AuthorizedIntent (J4)
  v
ACTIVE (registered; no in-flight)
  |
  | grant permit (J6)
  v
IN_FLIGHT (lease held by attempt_id; expires_at set)
  |
  | attempt recorded (J10) -> outcome appended (via N7/N4)
  v
ACTIVE (if retryable and more attempts allowed; next_retry_at set)
  |
  | terminal outcome appended
  v
TERMINAL (terminal_outcome_id set)
```

**CONFLICT** is a trap state: if `semantic_key` maps to different `intent_fingerprint`, we fail closed:

* never grant permits,
* emit a terminal FAILED outcome (`IDEMPOTENCY_KEY_CONFLICT`),
* require producer fix. 

---

# How N4 implements the illuminated joins (the machinery)

## J4 (N3 → N4) AuthorizedIntent ingestion

**N4 responsibilities:**

1. **Upsert `action_keys`** for `semantic_key_hash` if missing
2. **Fingerprint check**:

   * if no fingerprint stored: store this intent_fingerprint
   * if fingerprint differs: mark CONFLICT and return KeyConflict (fail closed)
3. **Route decision** (inside N4):

   * if TERMINAL outcome exists → return **CanonicalOutcomeRecord** (J7)
   * else if IN_FLIGHT lease active → return **InFlightNoOutcomeYet (NO-OP)** (J7)
   * else → proceed to permit grant path (J6)

> Key point: N4 is where “duplicate vs new” becomes *authoritative*.

## J6 (N4 → N5) ExecutePermit grant

**Permit & lease machinery:**

* Acquire row lock on `action_keys[semantic_key_hash]`
* Ensure no active in-flight lease (or lease expired)
* Create a new `attempt_id`, increment `attempt_no`
* Generate `permit_token` (store hash in attempts table)
* Set `in_flight_attempt_id` + `lease_expires_at = now + lease_ttl`
* Return `ExecutePermit(semantic_key, attempt_id, attempt_no, permit_token, expires_at)`

**Non-negotiable pin:** without a valid permit/lease, N5 must not execute.

## J7 (N4 → N7) DuplicateHit / CanonicalOutcome retrieval

**Canonicalization machinery:**

* If terminal outcome exists: return the **terminal outcome** (and its publish_state from outbox)
* Else if in-flight exists: return **InFlightNoOutcomeYet** with recommended handling = NO-OP (v0)
* Else (should not happen if J4 routing correct): treat as “no canonical, go to permit grant”

**Canonical outcome selection rule (pinned):**

* Prefer **terminal** (DENIED, EXECUTED, FAILED-final)
* If no terminal exists and you need a non-terminal view: latest appended outcome by seq_no (but v0 duplicates-in-flight are NO-OP)

## J10 (N5 → N4) AttemptRecord append

**Attempt journal machinery:**

* Validate `permit_token` matches the attempt’s stored hash (prevents split-brain writers)
* Append attempt record update (or append a new row per phase; either is fine as long as history is representable)
* Update `action_keys` derived fields:

  * clear `in_flight_attempt_id` if attempt finalized
  * set `next_retry_at` if retryable
  * set `state` back to ACTIVE or TERMINAL depending on terminalization rules

**Pinned safety rule:** recording attempt outcome is what seals the “executed-but-not-published” crash window. Publish may fail later; execution must not repeat.

## J12 (N7 ↔ N4) Outbox publish-state handshake

### N4 → N7: fetch outcomes due to publish

* Query `outbox where publish_state=PENDING and next_publish_at<=now`
* Return stable `OutcomeToPublish(outcome_event_id, immutable payload_json, digest, partition_key_hint)`

### N7 → N4: record PublishReceipt

* On ADMIT/DUPLICATE:

  * set `publish_state=ADMITTED`
  * store bus coordinates if provided
* On transient failure:

  * keep PENDING
  * increment attempts, set next_publish_at with backoff
* On QUARANTINE:

  * set `publish_state=QUARANTINED`
  * mark incident flag; this is P0 because it breaks audit closure 

---

# Optional machinery (only if you enable async actions)

## J14 (N9 → N4) callback correlation

N4 uses correlation indices:

1. if callback includes semantic_key_hash → direct
2. else if callback includes effector_request_id → lookup `effector_request_map`
3. else if callback includes parent_intent_event_id → lookup `intent_event_map`
   Else → orphan callback (triage path; no state change)

## J15 closure append

* Dedup callback_event_id in `callback_dedupe` (idempotent)
* Append a **closure outcome** in `outcomes` (new outcome_seq_no, new outcome_event_id)
* Enqueue in outbox for publish

**Pinned:** closure is append-only; never mutate prior outcomes.

---

# Recovery machinery (how N4 supports P8 without drift)

N4 exposes (or internally drives) three “views” used during startup/recovery:

1. **Pending outbox view**: outcomes needing publish retry
2. **Expired lease view**: in-flight attempts whose lease_expires_at < now

   * these become “needs resolution” (safe retry with same idempotency token)
3. **Retry-due view**: keys whose next_retry_at <= now and posture allows permits

This is how AL restarts safely: publish first, reconcile in-flight second, then resume normal flow. 

---

# N4 environment ladder and deployment pins (N4-specific)

These are the knobs Codex can tune per env without changing semantics:

* **lease_ttl** (shorter in local, longer in prod; semantics same)
* **outbox_publish_backoff** (profiled)
* **retention policy**:

  * **must retain semantic-key terminal state** long enough to cover your maximum replay/backfill horizon (otherwise old duplicates could re-execute)
  * may compact deep attempt history if needed, but keep terminal decision + terminal outcome digest/refs
* **indexes/partitioning**:

  * always index `semantic_key_hash`, and commonly `manifest_fingerprint`
  * optional maps (`intent_event_map`, `effector_request_map`) are worth it in dev/prod for triage

**Hard ladder pin:** local must still run a real DB-backed N4; no “in-memory ledger for local” if you want semantics parity. 

---

# Drift bans (N4 edition)

* **Banned:** “Use EB as the idempotency ledger.” (EB is replay truth, not a coordination DB.)
* **Banned:** “Grant permits without durable writes.”
* **Banned:** “Publisher mints new outcome_event_id on retry.”
* **Banned:** “Resolve idempotency key collisions by choosing one.” (Must fail closed.)
* **Banned:** “Delete terminal semantic keys while replays/backfills are still possible.”

---

If you want the clean continuation, next we illuminate **N7 (Outcome Assembly & Publisher)** immediately, because it is the other half of the **N4↔N7 outbox contract**, and it’s where QUARANTINE handling and ADMIT/DUPLICATE semantics must remain razor-sharp.

---

Absolutely. We’ll open **N7 — Outcome Assembly & Publisher** and expose the internal machinery that makes **J5/J7/J11/J12** and the publish-related paths/loops (**P2/P3/P6/P8**, **L2/L7**) actually work — **without changing any semantics** we already pinned.

I’ll keep this as *designer-level machinery*, not an implementation spec.

---

# N7 mission and authority boundary

## What N7 is authoritative for

N7 is authoritative for the **mechanics of turning ledger-truth into admitted bus facts**:

* Constructing the **canonical-envelope** ActionOutcome event from an immutable outcome record
* Publishing that event through **IG** (never bypass)
* Recording publish results back into N4 (outbox state + receipts + bus coordinates)
* Retrying publish safely (outbox loop), **without ever re-executing**

## What N7 is not allowed to do

Hard bans (non-joins inside AL):

* **No execution:** N7 must never call N5/N6 or trigger effectors
* **No decisioning:** N7 does not authorize, dedupe, or decide semantics
* **No outcome mutation:** N7 must not edit/“fix” outcomes; outcomes are immutable
* **No ID minting:** N7 must not mint `outcome_event_id` ad-hoc; identity is ledger-owned
* **No publishing arbitrary traffic:** N7 only publishes what N4 says exists and is due

This is what keeps “publish retry” from turning into “execute again.”

---

# N7 internal subnetworks (inside N7)

Think of N7 as a small internal network of sub-boxes:

1. **P1 Outcome Intake Router**
   Accepts “an outcome needs to exist” signals (DeniedDecision, OutcomeDraft, DuplicateHit) and ensures the outcome is **materialized in N4** + enqueued into the outbox.

2. **P2 Envelope Builder**
   Builds the **CanonicalEventEnvelope + ActionOutcome payload** from an immutable outcome record, ensuring stable serialization / digests.

3. **P3 Outbox Scanner & Lease Manager**
   Pulls “due to publish” outcomes from N4, optionally leases them to avoid publish stampedes when multiple N7 instances run.

4. **P4 IG Submitter**
   The only place that talks to IG. Submits a single event (or batch) and interprets IG’s decision.

5. **P5 Receipt Committer**
   Writes publish receipts/state back to N4 (ADMIT/DUPLICATE/QUARANTINE + bus coordinate).

6. **P6 Backoff & Retry Planner**
   Computes `next_publish_at` and handles ambiguous publish outcomes (timeouts) safely by retrying with the same `outcome_event_id`.

7. **P7 Quarantine Escalator**
   Handles QUARANTINE as a **P0**: marks state, emits incident telemetry, and triggers the “stop the bleeding” posture externally.

8. **P8 Telemetry Emitter (tap)**
   Emits publish metrics/traces/logs with full correlation keys, but never controls behavior directly.

---

# N7’s conceptual state machine (per outcome)

N7’s core is the publish lifecycle for a single immutable outcome:

```
OUTCOME_EXISTS (in N4) + OUTBOX=PENDING
          |
          | (picked by P3)
          v
PUBLISH_ATTEMPT
   |      |        \
   |      |         \ timeout/uncertain
   |      |          \
   |      v           v
   |   ADMIT        NO_RECEIPT
   |      |           |
   |      v           v
   |  OUTBOX=ADMITTED OUTBOX=PENDING (retry with backoff; same outcome_event_id)
   |
   v
DUPLICATE  --> OUTBOX=ADMITTED (already there; stop retrying)
   |
   v
QUARANTINE --> OUTBOX=QUARANTINED (P0 escalation; stop automatic attempts)
```

**Designer pin:** “No receipt” (timeout) is treated as **unknown**, not failure; the only safe move is to retry publish using the **same stable event_id**, letting IG return DUPLICATE if the earlier publish actually succeeded.

---

# N7’s inputs and what it does with them

N7 has *two kinds* of inputs:

## A) Outcome creation triggers (make sure an outcome exists + is queued)

These are not “publish this raw thing”; they are “ensure an immutable outcome exists in N4, then publish.”

### 1) J5: `DeniedDecision` (from N3)

**N7 action:** `ensure_denied_outcome(semantic_key, intent_fingerprint, deny_reason, policy_rev…)`

* Ask N4 to **create-or-load** the canonical DENIED outcome for this semantic key (stable `outcome_event_id`)
* Ensure it is in outbox PENDING
* Optionally publish immediately or let the outbox loop pick it up

### 2) J11: `OutcomeDraft` (from N5)

**N7 action:** `append_outcome_from_draft(semantic_key, attempt_no, evidence_refs, policy_rev…)`

* Ask N4 to append a new immutable outcome record (e.g., EXECUTED or FAILED attempt outcome)
* Ensure outbox has a row for it (PENDING)

### 3) J7: `CanonicalOutcomeRecord` / `DuplicateHit` (from N4)

This is the “duplicate convergence” path:

* If canonical outcome exists and outbox says ADMITTED → **NO-OP**
* If canonical outcome exists but publish state isn’t ADMITTED → **enqueue for publish** (or publish immediately)

> **Key design stance:** N7 is allowed to be “lazy.” It can rely on the outbox scanner to publish, as long as outbox correctness is maintained. That keeps the design simple and restart-safe.

## B) Outbox publish work (the actual publisher loop)

### J12: `OutcomeToPublish` (from N4)

N7 fetches immutable outcomes due for publish. It must publish **exactly what N4 stored**, not regenerate meaning.

---

# Envelope + payload assembly (P2 Envelope Builder)

This is where we enforce “canonical envelope first” and immutability.

## Envelope rules (pinned)

For every ActionOutcome event:

* `event_id = outcome_event_id` (stable)
* `event_type = ActionOutcome` (or versioned variant)
* `ts_utc = outcome_ts_utc` (domain time of outcome)
* `manifest_fingerprint` required
* include ContextPins when available
* include `parent_event_id = intent_event_id` (causal link)

## Payload rules (pinned)

Payload must include enough for DLA/case joins and replay stability:

* `semantic_key` (or its components: ContextPins + idempotency_key)
* `decision = EXECUTED | DENIED | FAILED | (closure variants if enabled)`
* `attempt_no/attempt_id` when applicable
* `actor_principal`, `origin`
* `policy_rev` (and exec_profile_rev if you choose)
* evidence refs (effector_request_id, digests, status refs)

## Immutability enforcement

**Designer pin:** N7 must publish the payload in a **stable canonical form**:

* N4 stores `payload_json_canonical` + `payload_digest`
* N7 publishes that canonical bytes (or a deterministic re-serialization that yields the same digest)
* On retry/republish, N7 uses the same canonical bytes

That is how we make “re-emit canonical outcome” literal.

---

# Publishing to IG (P4 IG Submitter)

## The only allowed publish path

N7 submits to **IG**, not EB, and never bypasses IG.

IG returns: `ADMIT | DUPLICATE | QUARANTINE` (+ receipts).

### Interpretation (pinned)

* **ADMIT** = success; outcome is now an admitted fact
* **DUPLICATE** = success; outcome already admitted; stop retrying
* **QUARANTINE** = **P0 incident** for outcomes

### Ambiguous publish (timeouts)

If N7 gets no definitive IG response:

* treat as unknown
* schedule retry with backoff
* retry uses same `outcome_event_id`
* if it was already admitted, IG returns DUPLICATE later and closes the loop cleanly

---

# Receipt committing (P5 Receipt Committer)

N7 always reports results back to N4:

* `PublishReceipt(outcome_event_id, decision, ig_receipt_ref, bus_coords?, published_at)`
* N4 records:

  * `publish_state=ADMITTED` on ADMIT/DUPLICATE (+ coords if available)
  * `publish_state=PENDING` + next_publish_at on transient failure
  * `publish_state=QUARANTINED` on QUARANTINE

**Designer pin:** N7 must never “mark admitted” without an ADMIT/DUPLICATE receipt (or a deterministic IG receipt object).

---

# Backoff & retry planning (P6 Backoff Planner)

N7 (or N4, depending on where you compute schedules) uses deterministic backoff rules:

* exponential backoff with jitter bounds
* max publish attempts (soft cap)
* escalation threshold (e.g., after N tries or T minutes, raise an incident even if still retrying)

**But:** outbox retry must remain indefinite enough to preserve audit closure under transient outages; you can cap automatic retries only if you have a governed remediation path (N10) that can re-enqueue.

---

# QUARANTINE escalation (P7 Quarantine Escalator)

This is where we enforce **“Outcome quarantined = P0”**.

When IG quarantines an ActionOutcome:

1. Mark outbox as QUARANTINED (no further automatic publish attempts)
2. Emit a high-severity incident telemetry event (with correlation keys + IG receipt refs)
3. Trigger “stop the bleeding” posture externally:

   * typically request drain/kill of new executions until publish pipeline is corrected

**Important:** N7 doesn’t *itself* control N2; it surfaces the event so Run/Operate + Gov can act (consistent with the governed change loop).

---

# Concurrency and scaling posture (production-safe)

N7 can run with multiple replicas. To avoid stampedes:

* P3 Outbox Scanner should **lease** outbox rows (or select with `SKIP LOCKED`) so two publishers don’t hammer IG unnecessarily.
* Even if two publishers race, correctness is still preserved because:

  * event_id is stable
  * IG DUPLICATE closes the loop
    But we still want to reduce waste.

---

# N7 environment ladder knobs (deployment-safe)

Allowed to vary by env (no semantic drift):

* publish batch size (1 in local, larger in prod)
* publish concurrency
* backoff parameters
* IG endpoint + timeouts
* telemetry sampling

Not allowed to vary by env:

* stable outcome_event_id reuse
* ADMIT/DUPLICATE semantics
* QUARANTINE=P0 treatment
* no bypass of IG

---

# N7 drift bans (final guardrails)

* Publishing anything not present in N4 outbox
* Minting new event IDs on retries
* “Fixing” payloads in N7
* Calling N5/N6 from publisher
* Treating timeout as failure that triggers re-execution
* Downplaying QUARANTINE for outcomes

---

If you’re happy with this, the next node to open is **N5 (Execution Orchestrator)**, because now we have both sides of the keystone pair (**N4 ledger/outbox** and **N7 publisher**) pinned tightly, and N5 can be designed to write durable attempt truth *before* publish, which is what keeps your whole “effectively-once under replay” promise real.

---

Absolutely. We’ll open **N5 — Execution Orchestrator** and expose the machinery that makes the **attempt lifecycle, retries, UNKNOWN handling, and posture interaction** actually work — **without changing** any of the already-pinned network semantics (permit-gated execution, append-only history, outbox publish, IG/EB mediation, governed controls).

I’ll keep it designer-level, but concrete.

---

# N5 mission and boundary

## What N5 is authoritative for

N5 is the **runtime conductor** for one semantic action line (`semantic_key = (ContextPins, idempotency_key)`):

* starting an attempt **only when** it holds an **ExecutePermit** (J6)
* issuing the **ExecutionCommand** (J8) to the correct effector adapter (N6)
* classifying the result into a stable execution result taxonomy (based on J9)
* writing the attempt truth to the ledger (J10) and producing an outcome draft (J11)
* coordinating retries/resolution *as a policy-driven schedule*, never as ad-hoc “try again”

## What N5 must never do

Hard bans (anti-drift):

* **No permit ⇒ no effector call** (ever).
* **No publishing** (never talks to IG/EB; that’s N7).
* **No mutation** of prior attempts/outcomes (append-only via ledger).
* **No “execute again because publish failed”** (publish is outbox-only, never drives execution).
* **No decisioning** (DF decides; N5 only executes/refuses via posture constraints).

---

# N5 internal subnetworks (inside N5)

Think of N5 as this internal network of “mini-boxes”:

1. **E1 Work Intake & Attempt Router**

   * accepts `ExecutePermit`s from N4
   * routes to per-action-type execution lanes (or a unified lane with constraints)

2. **E2 Posture Gate**

   * consumes `ExecutionPostureSnapshot` (J3) continuously
   * decides if *new* attempts may start, and under what caps (drain/safe-mode/disabled action types)

3. **E3 Attempt Lifecycle Manager**

   * maintains the state machine for each attempt_id
   * enforces sequencing and timeouts
   * owns cancellation semantics (drain/kill interaction)

4. **E4 Command Builder**

   * builds `ExecutionCommand` for N6:

     * derives **external_idempotency_token** deterministically from semantic_key (+ action_type)
     * injects timeouts/deadlines and minimal action parameters
     * propagates trace context

5. **E5 Effector Invocation Controller**

   * calls N6, enforces timeout/circuit breaker posture
   * supports “resolution probes” if an effector supports status queries (optional)

6. **E6 Receipt Classifier**

   * maps `ExecutionReceipt` (COMMITTED/NOT_COMMITTED/UNKNOWN + categories) into:

     * `ExecutionResult` (executed/failed, retryability, evidence refs)
     * `RetryPlan` (next_retry_at, backoff policy, terminalization)

7. **E7 Ledger Writer**

   * writes append-only `AttemptRecord` to N4 (J10) with **permit_token enforcement**
   * ensures crash-window seal (execution truth recorded even if publish later fails)

8. **E8 Outcome Draft Builder**

   * produces `OutcomeDraft` (J11) from the attempt result
   * does **not mint outcome_event_id** (ledger/outbox owns stable identity)

9. **E9 Recovery/Reconciliation Worker**

   * on startup or when leases expire, resolves “in-flight/uncertain” attempts safely:

     * idempotent retry using the same token, or
     * status query if available, or
     * terminalize after policy says stop

---

# N5 state machine (per attempt)

This is the orchestration core. For one `attempt_id`:

```
PERMIT_RECEIVED
   |
   | (optional but recommended) record STARTED in ledger
   v
PRECHECK (posture + action enablement + params sanity)
   |
   | if posture forbids start -> ABORT_NO_EXEC (terminal FAILED w/ reason)
   v
INVOKE_EFFECTOR (J8 -> N6)
   |
   v
RECEIPT_OBSERVED (J9 from N6)
   |
   v
CLASSIFY (COMMITTED / NOT_COMMITTED / UNKNOWN -> result + retry plan)
   |
   v
RECORD_ATTEMPT (J10 append AttemptRecord; must validate permit_token)
   |
   v
DRAFT_OUTCOME (J11 -> N7)
   |
   v
DONE (execution path finished; publish handled by outbox)
```

### “Optional but recommended” STARTED record

I recommend N5 writes a **STARTED phase** AttemptRecord immediately after permit and before the effector call. Why:

* improves triage (“stuck in invoke” vs “never started”)
* gives recovery logic more signal
* doesn’t change semantics; still append-only

(If you don’t want phases, you can write a single record at completion; the core safety is still the permit + lease + TTL. But phases make ops much cleaner.)

---

# How N5 handles execution outcomes (the heart of it)

N6 returns `ExecutionReceipt` with `commitment_state` and error categories. N5 must translate that into **safe, deterministic behavior**.

## 1) COMMITTED

Meaning: “side effect is now true (or idempotently already true).”

N5 must:

* record AttemptRecord as COMMITTED
* draft `OutcomeDraft(decision=EXECUTED, retryable=false)` with evidence refs
* ensure the action key becomes terminal **from an execution standpoint**
* never attempt again for this semantic key

## 2) NOT_COMMITTED

Meaning: “we are confident the side effect did NOT happen.”

N5 must:

* classify failure category
* decide retryable vs terminal using **ExecutionPostureSnapshot** rules (not ad-hoc)
* record AttemptRecord (NOT_COMMITTED + retryability)
* draft `OutcomeDraft(decision=FAILED, retryable={true|false}, category=…)`
* if retryable: schedule `next_retry_at` (through ledger fields via AttemptRecord / derived state)
* if terminal: end the line (no further permits issued)

## 3) UNKNOWN (ambiguous timeout / uncertain commit)

Meaning: “we cannot safely assert whether it happened.”

This is the most important production case.

**Pinned safe stance:** UNKNOWN must not become EXECUTED just because we “feel like it.”
N5 must:

* record AttemptRecord with `commitment_state=UNKNOWN`
* draft `OutcomeDraft(decision=FAILED, category=UNCERTAIN_COMMIT, retryable=true)`
* schedule a **resolution attempt**, not a “fresh” execution:

  * resolution = retry with the **same external_idempotency_token** and/or query status
* apply bounded resolution rules (max attempts/time window), then terminalize as FAILED-final if it cannot be resolved

This works only because we already pinned: unsafe effectors/actions (no idempotency token support) must be disabled in v0.

---

# Retry & resolution planning (how N5 chooses “what next”)

N5 does **not** invent retry behavior. It applies a deterministic policy:

Inputs:

* action_type profile from `ExecutionPostureSnapshot` (max_attempts, backoff curve, retryable categories)
* receipt classification (commitment_state + error_category)
* attempt_no

Outputs:

* `retryable` bool
* `next_retry_at`
* `stop_reason` if terminalizing

### Boundedness pins

* retries are **sequential**: at most one in-flight attempt per semantic key
* retries reuse the same semantic key and external token
* max_attempts (or max_duration) must be enforced per action_type
* posture changes can stop retries explicitly (see below)

---

# Posture interaction (drain/kill/caps) inside N5

N5 consumes `ExecutionPostureSnapshot` continuously. Here’s the designer-pinned behavior:

## Drain mode

* do **not** start new attempts (don’t request/consume new permits for new work)
* allow in-flight attempt to complete
* allow outbox publish to continue (N7/N4 loop)
* scheduled retries pause (they remain scheduled; they don’t disappear)

## Kill / disabled action types

This can arrive either as:

* policy deny (handled at N3), or
* execution posture disable (handled at N5 before effector call)

Pinned handling:

* if disable is observed **before** effector invocation: abort attempt and finalize as **FAILED terminal** with reason `CANCELLED_BY_POSTURE` (no side effect happened)
* if disable is observed **after** effector invocation began: you cannot “un-execute”; finish classification truthfully, then stop further retries if posture demands

## Caps / safe-mode

* reduce concurrency and/or rate limits
* prefer delaying retries rather than dropping
* never change semantic meaning; only pacing

---

# Crash/restart duties (N5’s part of P8)

N4 provides views (expired leases, in-flight attempts, retry-due). N5’s recovery worker (E9) does:

1. **Never re-execute without a fresh permit**

   * recovery uses N4 coordination (lease expiration, new permits) to avoid split-brain

2. **Resolve ambiguous in-flight attempts**

   * if attempt ended COMMITTED → ensure terminal outcome exists (publish handled by outbox)
   * if UNKNOWN → run resolution strategy (idempotent retry or status query)
   * if NOT_COMMITTED + retryable → schedule/attempt retry when posture allows

3. **Don’t block on publishing**

   * N5 recovery can complete attempt truth independent of N7 being up; outbox covers publish.

---

# Concurrency model (production realism without overspec)

N5 should implement execution lanes in a way that:

* respects `max_concurrency` per action_type (from posture snapshot)
* avoids head-of-line blocking (a slow action_type doesn’t stall all)
* supports fairness (optional)

But *the correctness boundary is still N4 permits*. Concurrency controls are for stability, not correctness.

---

# Evidence and correlation discipline (for audit/cases)

For every attempt, N5 must preserve enough evidence refs for DLA/Case joins (without dumping payloads):

* effector_request_id
* evidence_refs/digests (small pointers)
* attempt_no and timestamps
* policy_rev + exec_profile_rev used

And it must propagate trace context to N6 and back into telemetry.

---

# N5 “don’t drift” checklist (keystone rules)

* **Never call N6 without ExecutePermit.**
* **Never treat publish failure as a reason to re-execute.**
* **UNKNOWN ⇒ resolve safely (same token) or fail-final; never pretend EXECUTED.**
* **Retries are sequential and bounded; permits gate each attempt.**
* **Posture changes affect future attempts, not past truth; no mutation.**

---

If you want to keep the illumination sequence tight, the next node to open after N5 is **N6 (Effector Adapters)**, because N5’s safety story depends on the effector contract: idempotency token behavior, commitment-state classification, and evidence refs.

---

Absolutely. We’ll open **N6 — Effector Adapters** and expose the machinery that makes the **side-effect boundary** safe and replay-stable: external idempotency token usage, commitment classification, evidence refs, and (optionally) status probing — all **without changing** the network semantics already pinned (permit-gated attempts, append-only history, outbox publish, IG front door). 

---

# N6 mission and boundary

## What N6 is authoritative for

N6 is authoritative for **how AL talks to “the world”** (your closed-world effectors now, real integrations later):

* Mapping `action_type` → effector implementation
* Executing the side effect **using the external idempotency token**
* Returning a structured **ExecutionReceipt** that lets N5 classify outcomes safely
* Producing **evidence refs** (request ids, status refs, digests) for audit/case closure
* Optionally supporting a **status probe** / “resolve ambiguity” operation (for UNKNOWN cases)

## What N6 must not do

Hard bans (anti-drift):

* **No publishing** to IG/EB (only N7 publishes)
* **No policy decisions** (no deny/allow logic)
* **No idempotency decisions** (it uses the token; ledger decides duplicates)
* **No cross-action coordination** (no shared mutable state that becomes a shadow ledger)
* **No scanning** or “find latest” to correlate requests

N6 is an adapter boundary: execute or query status, return structured receipt.

---

# N6 internal subnetworks (inside N6)

Think of N6 as a small adapter framework:

1. **A1 Adapter Registry**

   * maps `action_type` (or action family) → `adapter_id`
   * supplies required capabilities metadata per adapter

2. **A2 Request Canonicalizer**

   * canonicalizes the minimal request payload
   * ensures stable hashing/digest for evidence (optional but helpful)

3. **A3 Idempotency Token Manager**

   * receives `external_idempotency_token` from N5 (already derived deterministically)
   * enforces correct placement/usage of the token for that adapter
   * validates “token required” constraints

4. **A4 Transport Client**

   * handles HTTP/gRPC/local call to the effector
   * timeouts, retries-at-transport level (strictly constrained), circuit breaker hooks

5. **A5 Receipt Normalizer**

   * maps effector response into the platform’s stable `ExecutionReceipt`
   * classifies `commitment_state` reliably

6. **A6 Evidence Extractor**

   * extracts `effector_request_id`, `status_ref`, and small evidence pointers/digests

7. **A7 Status Probe Handler** *(optional per adapter)*

   * given a status_ref or request_id + idempotency token, queries whether the effect is committed
   * returns a receipt as if from an execution attempt (but flagged as a probe)

8. **A8 Simulation Harness (closed-world mode)**

   * deterministic simulated effectors for your closed world
   * still honors idempotency token and returns stable receipts/evidence refs

---

# N6 adapter capability contract (pinned)

Every adapter declares capabilities; N5 uses this to enforce safety:

* `supports_idempotency_token: bool` **(must be true for v0 enabled action types)**
* `supports_status_probe: bool`
* `commitment_semantics: STRONG | EVENTUAL | UNKNOWNABLE`
* `provides_request_id: bool` (must be true)
* `error_taxonomy_map` (how raw errors map to stable categories)

**Designer pin:** If `supports_idempotency_token=false`, that `action_type` is **unsafe** and must be disabled by policy in v0 (or restricted to a special manual-only workflow with extra safeguards). 

---

# N6’s two public operations

N6 exposes two “verbs” to N5:

## 1) `execute(command: ExecutionCommand) -> ExecutionReceipt`

Used for normal attempts.

## 2) `probe_status(ref) -> ExecutionReceipt` *(optional)*

Used to resolve UNKNOWN ambiguity without “doing it twice.”

---

# The ExecutionCommand contract (what N6 expects)

N5 sends:

* `semantic_key`, `attempt_id`, `attempt_no`
* `action_type`, `target_ref`, `scope`, `action_params` (minimal)
* **`external_idempotency_token`** (mandatory for enabled actions)
* `deadline_utc` / `timeout_ms`
* trace context

**N6 must validate**:

* token present if required
* action_params satisfy adapter preconditions (else return NOT_COMMITTED + INVALID_PARAMS)

---

# The ExecutionReceipt contract (what N6 returns)

This is critical because N5 + N4 rely on it.

### Required fields (pinned)

**Identity/correlation**

* `semantic_key`, `attempt_id`, `attempt_no`
* `external_idempotency_token` (echo)
* `effector_adapter_id`, `effector_name`
* `effector_request_id` (must exist)

**Commitment**

* `commitment_state ∈ {COMMITTED, NOT_COMMITTED, UNKNOWN}`

**Classification**

* `result_code` (stable category)
* `error_category` (if not committed or unknown)
* `retry_advice {retryable, suggested_backoff_ms, resolution_hint}`

**Evidence**

* `status_ref` (if available)
* `evidence_refs[]` / `response_digest` (optional)
* timestamps (`started_at_utc`, `finished_at_utc`)

---

# Commitment classification machinery (the hardest part)

N6 must correctly decide COMMITTED vs NOT_COMMITTED vs UNKNOWN.

## COMMITTED

Return COMMITTED when:

* effector confirms the change is applied, or
* effector returns “already applied” for the same idempotency token, or
* effector returns a definitive success + request id.

**Designer pin:** “Already applied” counts as COMMITTED. That’s exactly what makes idempotency tokens safe.

## NOT_COMMITTED

Return NOT_COMMITTED when:

* input is invalid (`INVALID_PARAMS`)
* explicit rejection from effector (permissions, constraint violation)
* known safe failure before any side effect is applied

## UNKNOWN

Return UNKNOWN when:

* timeout with no confirmation
* network partition after request send
* ambiguous partial failure
* effector returns a non-definitive state (“queued”, “processing”) and you can’t treat it as committed

**Designer pin:** UNKNOWN must be used liberally to avoid false EXECUTED. Resolution is handled by idempotent retry/status probe, not by guessing.

---

# Transport retry rules (important anti-drift pin)

N6 may do *transport-level retries* only under strict rules:

* It may retry **only** if it can guarantee the request is still safe and idempotent (same idempotency token), and only for transient transport errors.
* If it retries and still can’t confirm, it must return UNKNOWN (not COMMITTED).

**Designer pin:** Do not implement “hidden aggressive retries” in N6 that mask outages. Retries must remain visible at attempt level (N5/N4 should record attempts and outcomes).

---

# Evidence refs (by-ref posture)

N6 must provide *joinable evidence* without bloating payloads:

* `effector_request_id`: stable id returned by the effector or generated deterministically at adapter boundary
* `status_ref`: something you can query later (URL/ref token)
* optional `response_digest`: digest of the response payload (not the payload itself)
* optional `evidence_refs[]`: pointers to object store blobs if needed (rare)

**Designer pin:** N6 returns references; N5/N4 store those refs; N7 publishes those refs. This preserves by-ref posture and auditability.

---

# Status probe machinery (optional but extremely useful)

For UNKNOWN cases, if the adapter supports status probes:

* `probe_status(status_ref or effector_request_id, external_idempotency_token)` returns:

  * COMMITTED (confirmed), or
  * NOT_COMMITTED (confirmed not applied), or
  * UNKNOWN (still uncertain)

This lets N5 resolve ambiguity without “re-trying execution blindly.”

**Designer pin:** probe must be idempotent and must not create side effects.

---

# Closed-world simulation harness (your platform realism)

Because you’re in a closed-world platform, N6 can host deterministic simulated effectors:

* simulation must still consume the external idempotency token
* must return stable `effector_request_id` and consistent commitment outcomes
* should be deterministic under `(semantic_key, action_type)` plus controlled randomness pinned by scenario/run seeds if you choose

This gives you production-shaped semantics in local/dev without real external integrations.

---

# N6 environment ladder knobs (allowed variance)

Allowed to vary by env (wiring/operational envelope):

* endpoint URLs / credentials
* timeout values
* circuit breaker thresholds
* whether status probe is enabled (dev/prod) or stubbed (local)

Not allowed to vary by env:

* use of idempotency token for enabled action types
* commitment_state taxonomy
* evidence ref availability (at least request_id must always exist)
* “UNKNOWN vs COMMITTED” correctness posture (never pretend)

---

# N6 drift bans (final guardrails)

* **Banned:** adapters that ignore idempotency tokens for enabled actions
* **Banned:** treating timeouts as NOT_COMMITTED (unless you can prove it)
* **Banned:** returning COMMITTED without evidence/confirmation
* **Banned:** publishing from adapters
* **Banned:** hidden long retry loops that hide outages and break attempt visibility
* **Banned:** adapter-internal “shadow ledgers” used to dedupe across semantic keys

---

If you want to continue in the recommended order, the next node to illuminate is **N3 (Authorization Gate)** *or* **N2 (Policy/Control Adapter)**—depending on whether you want to pin authz semantics first (DENIED vs FAILED vs posture-disabled) or the policy/posture artifact management first.

---

Got it — we’re opening **N3: Authorization Gate** and exposing the internal machinery that makes **J2 + J1 → (ALLOW via J4) / (DENY via J5)** work *safely, deterministically, and attributable*, without changing any of the already-pinned network semantics.  

---

# N3 mission and boundary

## What N3 is authoritative for

N3 is the **side-effect permission choke point**:

* It decides **ALLOW vs DENY vs FAIL-CLOSED** for a *single* `NormalizedIntent`
* It stamps decisions with **policy provenance** (`policy_id/rev/digest`, matched rule id)
* It emits only two kinds of downstream artifacts:

  * **AuthorizedIntent → N4** (J4)
  * **DeniedDecision / AuthzFailure → N7** (J5)

## What N3 must never do

Hard bans (anti-drift):

* **No idempotency decisions** (no “duplicate” logic) — that’s N4.
* **No execution** — that’s N5/N6.
* **No publishing** — that’s N7.
* **No calls to SR/Engine/OFP/IEG/DF** — N3 is not a decision engine and must not pull features.
* **No “allow by default”** if policy is missing/unavailable (fail closed).

These keep N3 inside the platform’s truth boundaries and replay safety. 

---

# N3 internal subnetworks (inside N3)

Think of N3 as a mini-network of opaque submodules:

1. **A1 Snapshot Latch**

   * Holds the current `ActivePolicySnapshot` from N2 (J2)
   * Provides atomic “use this snapshot for this evaluation” semantics

2. **A2 Intent Preconditions**

   * Validates that required fields exist (actor, origin, action_type, scope, semantic_key)
   * Validates actor assertion / delegation rules (see below)

3. **A3 Scope & Target Matcher**

   * Deterministic matcher for `scope` / `target_scope` (exact/prefix/wildcard rules)
   * Normalizes to a matchable form (but does not rewrite meaning)

4. **A4 Rule Evaluator**

   * Applies policy rules in a strict precedence order (kill/deny/allow/default-deny)
   * Produces `AuthzDecision`

5. **A5 Decision Composer**

   * Builds either:

     * `AuthorizedIntent` (for J4), or
     * `DeniedDecision` / `AuthzFailureDecision` (for J5)

6. **A6 Explain Builder**

   * Optional “why” payload (matched rule id, deny reason code)
   * Must remain small/by-ref friendly

7. **A7 Telemetry Tap**

   * Emits allow/deny/fail counts, by reason, by action_type/scope/policy_rev
   * Never controls behavior (tap only)

---

# Inputs to N3 (what it consumes)

## From N1 via J1: `NormalizedIntent`

N3 expects:

* `semantic_key = (ContextPins, idempotency_key)` (required for N3 outputs)
* `intent_fingerprint` (digest of canonical intent fields)
* `action_type`, `target_ref`, `scope` / `target_scope`
* `actor_principal`, `origin`
* `intent_event_id` (envelope event_id) 
* optional trace context

**Fail-closed pin:** if `actor_principal` or `idempotency_key` is missing, we treat it as *not safe to authorize* (should have been caught by N1). Outcome becomes FAILED (not executed).

## From N2 via J2: `ActivePolicySnapshot`

Must include:

* `policy_id`, `policy_rev`, `policy_digest`
* allow/deny rules keyed at least by `(actor_principal, origin, action_type, scope)`
* kill switch / disabled actions (policy-level denies)
* required-minima definition (so N3 can fail closed consistently)

---

# Outputs from N3 (what it emits)

## J4: `AuthorizedIntent` → N4

Must contain:

* `semantic_key`, `intent_fingerprint`
* `intent_event_id`
* `action_type`, `target_ref`, `scope`
* `actor_principal`, `origin`, `rationale_ref`
* **policy stamps**: `policy_id`, `policy_rev`, `policy_digest`
* optional `matched_rule_id` (for explainability)

## J5: `DeniedDecision` → N7

Must contain:

* `semantic_key`, `intent_fingerprint`, `intent_event_id`
* `deny_reason_code` (stable taxonomy)
* policy stamps (`policy_rev` etc.)
* optional `matched_rule_id` / explain payload

**Designer pin reminder:** DENY bypasses execution, but **does not bypass canonicalization** — N7 still uses N4/outbox to publish a canonical DENIED outcome for the semantic key (so duplicates converge). 

## J5 variant: `AuthzFailureDecision` → N7

Used when N3 cannot safely evaluate (policy unavailable, snapshot corrupt):

* produces **FAILED** outcome later (retryable=true for policy-unavailable)

---

# N3 decision taxonomy (pinned)

N3 returns exactly one of:

### 1) **ALLOW**

Means: “under `policy_rev`, this principal/origin/action/scope is permitted.”
It does **not** mean “it will execute” (N4 may dedupe; N5 posture may stop).

### 2) **DENY**

Means: “under `policy_rev`, execution is forbidden.”
Produces a DENIED outcome (terminal) — no execution.

### 3) **FAIL-CLOSED**

Means: “cannot determine policy safely.”
Produces a FAILED outcome with stable reason, usually retryable.

**Pinned line:**

* Policy says no → **DENIED**
* Policy can’t be loaded/validated → **FAILED (POLICY_STATE_UNAVAILABLE, retryable=true)**

---

# N3 rule evaluation algorithm (authoritative order)

For each `NormalizedIntent`, N3 evaluates in this strict order:

## Step 0 — Preconditions (A2)

* required fields present
* actor assertion valid (see next section)
* scope format valid

If not, **FAIL-CLOSED** with reason `INTENT_INVALID_OR_INCOMPLETE` (retryable=false).

## Step 1 — Snapshot latch (A1)

* capture a single immutable view: `snapshot = ActivePolicySnapshot@policy_rev`
* all subsequent evaluation uses that snapshot

If snapshot missing/unavailable → **FAIL-CLOSED** `POLICY_STATE_UNAVAILABLE` (retryable=true).

## Step 2 — Hard kill switches / global disables (A4)

If snapshot has a matching kill switch for `(origin, action_type, scope)`:

* **DENY** with reason `KILL_SWITCH_ACTIVE`

## Step 3 — Explicit deny rules (A4)

If a deny rule matches:

* **DENY** with reason `EXPLICITLY_DENIED_BY_POLICY`

## Step 4 — Allow rules (A4)

Find best allow match (see “specificity” below):

* **ALLOW** with matched_rule_id

## Step 5 — Default deny (A4)

If no allow rule matches:

* **DENY** with reason `DEFAULT_DENY`

This matches “fail closed” and keeps policy safe by default.

---

# Actor assertion / delegation (production realism pin)

Because ActionIntents are produced by services (DF/Case/Ops) **on behalf of** actors, N3 must avoid trusting a spoofed `actor_principal`.

**Designer refinement (safety pin):** N3 authorization key is effectively:

> **(asserting_producer, actor_principal, origin, action_type, scope)**

Where:

* `asserting_producer` is the authenticated producer identity (as admitted by IG / envelope metadata)
* `actor_principal` is the claimed effective actor

Policy must include rules for which producers are allowed to assert which actor domains:

* DF service may assert `actor_principal=df-service` (or a fixed service principal)
* Case service may assert a human principal only if it carries a valid delegation/identity token
* Ops service may assert ops principals only

If assertion is invalid → **DENY** with reason `INVALID_ACTOR_ASSERTION` (or FAIL-CLOSED if you treat it as malformed).

This keeps the security story realistic without making N3 a full identity system.

---

# Scope matching and rule specificity

## Scope matching modes (deterministic)

Allow rules can match scope via:

* exact match
* prefix match (hierarchical scopes)
* wildcard group match

**Pinned requirement:** matching must be deterministic and independent of runtime order (no “first rule in file wins” unless explicitly stated).

## Specificity precedence (authoritative)

When multiple allow rules match, pick the “most specific” by:

1. exact scope > prefix > wildcard
2. exact actor_principal > actor group/role
3. exact action_type > action family
4. higher explicit priority value (only if ties)

N3 returns the chosen `matched_rule_id` so the outcome is explainable.

---

# Explainability boundaries (what N3 records)

N3 should produce a *minimal* explain payload (don’t bloat events):

* `policy_rev`, `matched_rule_id`
* `decision`: ALLOW/DENY/FAIL
* `reason_code`: stable enum
* optional `reason_detail_ref` (by-ref pointer if you want deeper trace)

This is enough for governance and audit correlation without making ActionOutcome enormous. 

---

# Interaction with posture (J3) without drift

We already pinned the distinction:

* **N3 (policy) decides who is allowed** → DENY is policy-level, stamped with policy_rev.
* **N5 (posture) decides whether execution is currently safe** → posture disable produces **FAILED** (operational), not DENIED.

So if policy ALLOW but posture disables:

* N3 emits AuthorizedIntent
* N5 aborts before effector call and produces FAILED outcome `EXECUTION_DISABLED_BY_POSTURE`

This preserves “authorization vs operability” separation and keeps audit meaning clean. 

---

# Caching and update semantics (A1 Snapshot Latch)

N3 must be able to evaluate at high throughput without reloading policy per intent.

**Pinned behavior:**

* N3 keeps the latest `ActivePolicySnapshot` in memory (provided by N2).
* For each intent, it captures the snapshot pointer at evaluation start.
* Policy updates take effect for subsequent evaluations, but **do not rewrite history**.

If policy snapshot changes, duplicates of already-terminal semantic keys are still suppressed by N4 (not N3), which is correct.

---

# Environment ladder knobs (N3-specific)

Allowed per environment profile:

* strictness of actor assertion checks (local can use dev principals, prod strict)
* policy content (more permissive in local, strict in prod)
* explain verbosity (local may emit more debug detail)

Not allowed to differ:

* default deny stance
* fail-closed on policy unavailability
* decision provenance stamping (policy_rev must exist everywhere)
* denial canonicalization (DENIED outcomes must converge under semantic key)

This keeps semantics identical across local/dev/prod. 

---

# N3 drift bans (final guardrails)

* **Banned:** allow-by-default if no rule matches
* **Banned:** execute or publish from N3
* **Banned:** querying ledger/feature planes to “decide”
* **Banned:** treating policy-load failure as DENY (it’s FAILED retryable)
* **Banned:** ignoring actor assertion / allowing spoofed principals
* **Banned:** embedding large payloads in explain (use refs/digests)

---

If you want to keep the momentum: the next node to illuminate that pairs with N3 is **N2 (Policy & Control Adapter)**, because it defines how policy revs are loaded/activated, how kill switches/drain are delivered as snapshots, and how “governed change” stays explicit.

---

Absolutely. We’ll open **N2 — Policy & Control Plane Adapter** and expose the machinery that makes **policy snapshots (J2)** and **execution posture snapshots (J3)** *explicit, versioned, attributable, fail-closed, and environment-ladder compliant*—without introducing stealth controls or semantic forks.  

---

# N2 mission and authority boundary

## What N2 is authoritative for

N2 is AL’s **only internal control-plane ingress**. It is authoritative for:

* Producing the current **ActivePolicySnapshot** used by N3 for authorization (J2)
* Producing the current **ExecutionPostureSnapshot** used by N5 for safe execution (J3)
* Ensuring both snapshots are:

  * **explicit** (no hidden flags)
  * **versioned** (rev + digest)
  * **auditable/attributable** (who/why/when, via surrounding governance)
  * **fail-closed** (if state can’t be trusted, AL must not execute)

## What N2 must never do

Hard bans (anti-drift):

* **No implicit decisioning:** N2 doesn’t decide per-intent; it only supplies snapshots.
* **No stealth toggles:** no “if prod then…” branches that change meaning.
* **No direct effect on ledger/outcomes:** N2 doesn’t write actions/outcomes; it influences future behavior via snapshots only.
* **No bypass of governance:** N2 consumes governed artifacts/controls; it doesn’t invent them.

---

# N2 internal subnetworks (inside N2)

1. **C1 Profile Resolver**

   * Chooses which **environment profile** is active (local/dev/prod)
   * Determines where to load policy/posture artifacts from (paths/endpoints)
   * This is purely wiring; does not change semantics.

2. **C2 Policy Artifact Loader**

   * Loads the **Action Authorization Policy** (allow/deny rules, kill switches)
   * Validates schema + signatures/digests (if you use them)
   * Produces `ActivePolicySnapshot(policy_id, rev, digest, ruleset…)`

3. **C3 Execution Posture Loader**

   * Loads the **Execution Posture Profile** (drain/caps/retry budgets/disabled actions)
   * Produces `ExecutionPostureSnapshot(exec_profile_id, rev, digest, constraints…)`

4. **C4 Control Event Ingestor** *(optional but production-real)*

   * Subscribes to a control stream (via IG/EB) or reads a control store
   * Applies explicit control events (activate rev X, set drain on/off, kill scope S)
   * Converts events into “active revision pointers” used by loaders

5. **C5 Snapshot Latch + Atomic Switch**

   * Maintains current snapshots in memory
   * Supports atomic swap (so a single evaluation uses one consistent snapshot)
   * Exposes read-only handles to N3 (J2) and N5 (J3)

6. **C6 Health/Validity Monitor**

   * Tracks last successful load time, staleness, validation failures
   * Emits “policy unavailable” / “posture unavailable” conditions
   * Drives **fail-closed posture** recommendation

7. **C7 Provenance/Telemetry Emitter (tap)**

   * Emits which `policy_rev` and `exec_profile_rev` are active
   * Emits every activation/change as an observable event (for ops)
   * But does not itself constitute governance; it’s evidence.

---

# N2’s two snapshot products (the core outputs)

## 1) ActivePolicySnapshot (J2 → N3)

Minimum fields N2 must produce (we pinned earlier):

* `policy_id`
* `policy_rev`
* `policy_digest`
* `loaded_at_utc`
* `effective_scope` (optional but useful)
* `ruleset`:

  * allow/deny rules keyed by `(actor_principal, origin, action_type, scope)`
  * kill switches / global denies keyed by `(origin, action_type, scope)`
  * required minima (fields required to evaluate)
  * actor-assertion rules (which producers may assert which principals)

**Fail-closed signal:** if policy snapshot cannot be loaded/validated, N2 must advertise `policy_state=UNAVAILABLE`.

## 2) ExecutionPostureSnapshot (J3 → N5)

Minimum fields:

* `exec_profile_id`
* `exec_profile_rev`
* `exec_profile_digest`
* `loaded_at_utc`
* global posture flags:

  * `drain_mode` (pause starting new attempts)
  * `safe_mode` (tight caps, conservative retries)
* per action_type / action family constraints:

  * enabled/disabled
  * max_attempts
  * retryable_error_categories
  * backoff curve parameters
  * timeout_ms
  * concurrency caps / rate caps
  * requires_external_idempotency (must be true for enabled actions)

**Fail-closed signal:** if posture snapshot cannot be loaded/validated, N2 must advertise `exec_state=UNAVAILABLE`.

---

# Where do the snapshots come from (deployment + ladder posture)

N2 must support **two sourcing patterns**, both consistent with your platform:

### Pattern A — “Active revision pointers” (recommended for prod)

* A governed plane (Run/Operate/Gov) activates `policy_rev=X` and `exec_rev=Y` explicitly.
* N2 reads these active pointers from:

  * a control topic (via EB) **or**
  * a small control store (DB/object store ref)
* N2 then loads the referenced artifacts from the artifact store.

This keeps changes auditable and explicit. 

### Pattern B — “Static profile files” (okay for local)

* Local profile points at fixed “dev policy rev” and “dev exec rev”
* N2 loads them at startup and on file change

**Important ladder pin:** even in local, it’s still **rev-based artifacts**, just with permissive contents. No semantic shortcut.

---

# Artifact validation and “trust model”

To avoid “mystery behavior,” N2 must validate that loaded artifacts are the ones intended.

**Validation steps (designer-level, not implementation binding):**

1. parse + schema validate
2. compute digest and compare to expected digest (if the pointer includes one)
3. ensure `rev` and `policy_id/exec_profile_id` match expected
4. enforce “monotonic activation” rules if desired (optional)

If any validation fails:

* mark the snapshot as unavailable
* fail closed (see below)

---

# Fail-closed behavior (the most important N2 pin)

## Policy unavailable

If ActivePolicySnapshot is unavailable:

* N3 must not authorize.
* The system must output **FAILED** outcomes for affected intents with reason `POLICY_STATE_UNAVAILABLE`, retryable=true.
* AL must not execute “blind.” 

## Execution posture unavailable

If ExecutionPostureSnapshot is unavailable:

* N5 must not start new attempts.
* Either:

  * AL enters implicit drain mode (safe), or
  * N5 aborts pre-effector with FAILED `EXECUTION_POSTURE_UNAVAILABLE` (retryable=true)

**Designer stance:** prefer **drain-by-default** when posture is unknown, because it avoids spamming failure outcomes while still preserving “no execution without safety posture.”

---

# Atomicity and attribution pins

## Atomic switch

N2 must switch snapshots atomically:

* N3 evaluation uses one consistent `policy_rev`.
* N5 attempt planning uses one consistent `exec_profile_rev`.

No “half-updated” state.

## Attribution propagation

Every downstream decision/outcome must be attributable:

* N3 stamps DENIED with `policy_rev`.
* N5 stamps attempt/outcome with `policy_rev` and `exec_profile_rev`.

This is what lets DLA later say “these rules were in force.”

---

# How kill/drain/caps are modeled (avoids drift)

We pinned the difference:

* **DENY** = policy-level prohibition (N3) → produces DENIED outcomes
* **DISABLE/CAPS/DRAIN** = operational posture (N5) → produces FAILED or pauses new work, but is not “authorization”

So N2 must model controls as:

* Policy controls (kill switches / allowlists) in the **policy artifact**
* Operational controls (drain/caps/retry budgets) in the **exec posture artifact**

If a “control event” wants to stop harm quickly, it activates one (or both) artifacts explicitly:

* Activate a kill-switch policy rev (fast deny)
* Activate drain mode in exec posture rev (pause execution)

---

# Control events (optional C4) — how they map to snapshots

If you implement control events:

* Events should be minimal: “activate policy_rev=X”, “activate exec_rev=Y”, “set drain=true”, “disable action_type=T”
* N2 converts them into updated “active rev pointers” and reloads artifacts
* N2 emits telemetry: “policy_rev switched A→B; exec_rev switched C→D”

**Hard ban:** control events must not directly flip hidden internal flags that bypass versioned artifacts. They must be reflected as snapshot changes.

---

# N2 observability requirements (so ops can trust it)

N2 must emit:

* current `policy_rev`, `exec_profile_rev` (heartbeat)
* last load success timestamp
* validation failures
* staleness warning (if pointers refer to missing artifacts)

But N2 observability is a **tap**; it doesn’t decide to change policy—that remains governed externally.

---

# N2 environment ladder knobs (allowed differences)

Allowed to vary per environment profile:

* where artifacts live (local filesystem vs object store)
* how active rev pointers are sourced (static vs control stream)
* strictness of validation (local can skip signature checks, prod strict)
* refresh intervals (local fast, prod stable)

Not allowed to vary:

* snapshot concept (rev+digest always exists)
* fail-closed stance (unknown policy/posture never executes)
* attribution stamping requirement

---

# Drift bans (N2 edition)

* **Banned:** “if prod then deny more” implemented in code branches (must be policy artifact content)
* **Banned:** hidden runtime toggles not represented as snapshot revs
* **Banned:** allowing execution when policy/posture is unknown
* **Banned:** per-intent policy fetch (creates nondeterminism and performance hazards)
* **Banned:** mixing policy denies and operational disables into one ambiguous control channel

---

If you want to continue the illumination sequence, the remaining core nodes are **N1 (Intake & Normalize)** and **N8 (Observability & Gov Hooks)**. N1 is where “invalid/missing fields” become explicit FAILED outcomes (not silent drops), and N8 is where correlation discipline becomes enforceable across the whole vertex.

---

Absolutely — opening **N1: Intake & Normalize**.

N1 is where AL turns “admitted ActionIntent traffic delivered from EB” into a **safe, canonical internal unit** (`NormalizedIntent`) that downstream gates (N3/N4/N5) can reason about **without hidden assumptions**. N1 must be strict enough to prevent garbage from entering the machinery, but **never** silent-drop anything (invalid inputs must deterministically become outcomes later).  

---

# N1 mission and boundary

## What N1 is authoritative for

* **Ingestion from EB** (consumer mechanics) for ActionIntent (and optionally callback types if you later choose, though we pinned callbacks to N9 for clarity)
* **Parsing and normalization**:

  * canonical envelope extraction
  * canonical payload extraction
  * computation of `semantic_key = (ContextPins, idempotency_key)`
  * computation of `intent_fingerprint` (digest of canonical intent fields)
* **Early classification**:

  * route valid intents to N3 (AuthZ)
  * route invalid/unparseable intents to a **NormalizationFailure** path that still produces a **FAILED** outcome (via N7/N4 outbox)

## What N1 must never do

Hard bans:

* **No authorization** decisions (N3 only)
* **No idempotency** decisions (N4 only)
* **No execution** (N5/N6 only)
* **No publishing** directly (N7 only)
* **No “fixing”** malformed payloads (must fail closed, not guess)

---

# N1 internal subnetworks (inside N1)

1. **I1 EB Consumer Adapter**

   * subscribes to ActionIntent event types
   * handles at-least-once redelivery
   * extracts `(topic, partition, offset)` for telemetry/debug only

2. **I2 Envelope Decoder**

   * parses CanonicalEventEnvelope fields
   * validates required envelope minima:

     * `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` 

3. **I3 Schema/Version Router**

   * selects the payload parser based on `(event_type, schema_version)`
   * enforces “known schema only” (unknown version is a failure)

4. **I4 Payload Decoder**

   * parses ActionIntent payload into a structured internal shape
   * validates presence/type of required payload fields

5. **I5 Canonicalizer**

   * normalizes values into canonical forms:

     * stable ordering of pins
     * consistent serialization of target refs/scopes
     * canonical whitespace/normal forms where relevant
   * **does not** change meaning; it only stabilizes representation

6. **I6 Semantic Key Builder**

   * builds `semantic_key = (ContextPins, idempotency_key)`
   * if missing pins/keys → classify as failure (fail closed)

7. **I7 Intent Fingerprinter**

   * computes `intent_fingerprint = hash(canonicalized intent fields)`
   * this is what enables N4 to detect idempotency-key collisions

8. **I8 Routing & Failure Emitter**

   * outputs either:

     * `NormalizedIntent` → N3 (J1), or
     * `NormalizationFailure` → N7 (failure outcome path)
   * ensures no silent drops

9. **I9 Telemetry Tap**

   * emits parse success/failure, schema mismatch counts, and correlation keys
   * never controls behavior (tap only)

---

# N1’s two outputs (the only things it’s allowed to emit)

## 1) `NormalizedIntent` (to N3 via J1)

Must contain:

### A) Envelope fields (canonical)

* `intent_event_id` (envelope `event_id`)
* `event_type` (must be ActionIntent)
* `ts_utc`
* `manifest_fingerprint` 
* optional: `run_id`, `scenario_id`, `parameter_hash`, `seed` (ContextPins)
* optional: `producer` / `origin_producer` (if present in envelope)
* trace context if present

### B) Payload fields (canonical)

* `idempotency_key` (required)
* `action_type` (required)
* `target_ref` (required)
* `scope` / `target_scope` (required)
* `actor_principal` (required)
* `origin` (required: df | case_workbench | ops)
* `rationale_ref` (required or strongly recommended; if missing we can still fail closed depending on policy minima)

### C) Derived fields

* `semantic_key = (ContextPins, idempotency_key)` (required)
* `intent_fingerprint` (required)
* `delivery_basis = (topic, partition, offset)` (optional; debug only)

## 2) `NormalizationFailure` (to N7 via I8)

Must contain enough to build a **FAILED** outcome (no execution) that is still joinable:

* `intent_event_id` (if envelope parsed)
* `manifest_fingerprint` (if parsed)
* `ts_utc` (if parsed)
* `failure_reason_code` (stable taxonomy)
* `failure_detail` (small string; no big payloads)
* `raw_event_ref` (optional pointer/digest to the raw bytes for triage)
* best-effort extracted ContextPins (if any)
* best-effort `actor_principal`/`origin` (if any)

**Designer pin:** if semantic_key cannot be constructed, the failure outcome must still carry **event_id + manifest_fingerprint** so it’s traceable. It simply won’t be dedupe-able at semantic level, which is acceptable because it will not execute anything.

---

# N1 failure taxonomy (stable, drift-resistant)

N1 must classify failures into a small stable set (so governance and triage are sane):

1. `ENVELOPE_PARSE_FAILED`
2. `ENVELOPE_MISSING_REQUIRED_FIELD`
3. `UNSUPPORTED_EVENT_TYPE`
4. `UNSUPPORTED_SCHEMA_VERSION`
5. `PAYLOAD_PARSE_FAILED`
6. `PAYLOAD_MISSING_REQUIRED_FIELD`
7. `PAYLOAD_TYPE_INVALID`
8. `SEMANTIC_KEY_INCOMPLETE` (missing ContextPins or idempotency_key)
9. `ACTOR_PRINCIPAL_MISSING_OR_INVALID`
10. `SCOPE_INVALID`
11. `TARGET_REF_INVALID`

**Fail-closed rule:** Anything that prevents safe authorization/idempotency must not proceed to N3/N4/N5.

---

# N1 routing logic (authoritative)

For each EB-delivered message:

1. **Decode envelope** (I2)

   * If fails → emit `NormalizationFailure(ENVELOPE_PARSE_FAILED)`
2. **Validate required envelope minima**

   * If missing required → failure
3. **Check event_type**

   * If not ActionIntent → either ignore (if not subscribed) or failure if it arrives unexpectedly
4. **Parse payload using schema_version router** (I3/I4)

   * Unknown version → failure
5. **Canonicalize fields** (I5)
6. **Build semantic_key** (I6)

   * Missing idempotency_key or required pins → failure
7. **Compute intent_fingerprint** (I7)
8. **Emit NormalizedIntent to N3** (I8 → J1)

---

# “No silent drop” guarantee (how N1 enforces it)

N1 must always produce one of:

* `NormalizedIntent` → N3, or
* `NormalizationFailure` → N7 (leading to a FAILED outcome)

Even if the message is garbage, N1 should emit a failure fact with as much correlation as possible.

This is vital for auditability and for avoiding “mysterious missing intents.”

---

# Interaction with at-least-once delivery

N1 is not responsible for semantic dedupe. It must assume:

* duplicates will arrive
* ordering may vary by partition

N1 should be idempotent in its own processing (parsing the same bytes yields the same `NormalizedIntent` and the same `intent_fingerprint`), but it should not try to suppress duplicates — that’s N4’s job.

---

# N1 environment ladder + deployment knobs

Allowed to vary per environment profile:

* consumer batch size
* commit/checkpoint cadence
* logging verbosity
* schema registry source (local file vs artifact store)

Not allowed to vary:

* envelope required minima
* fail-closed stance for missing actor/idempotency/scope
* no silent drop discipline
* deterministic canonicalization/fingerprinting

**Designer pin:** local must still use real EB delivery semantics (at-least-once) so duplicates are exercised early. 

---

# N1 drift bans (final guardrails)

* **Banned:** “best-effort execute even if actor/idempotency missing”
* **Banned:** “auto-correct” or “default” missing identity fields
* **Banned:** silently dropping unknown schema versions
* **Banned:** mixing callback events into ActionIntent parsing path (keep callbacks in N9 as designed)
* **Banned:** N1 deciding duplicates or authorization

---

If you want to keep the illumination sequence consistent, the last core node to open is **N8 (Observability & Governance Hooks)** — because once N1–N7 are illuminated, N8 is what makes the whole inner network operable and debuggable without becoming a control plane.

---

Absolutely — opening **N8: Observability & Governance Hooks**.

N8 is the **cross-cutting, non-blocking tap layer** that makes the AL inner network operable and auditable **without ever becoming a control path** (no stealth toggles, no “telemetry decides execution”). It’s where we pin the correlation discipline that keeps this complex vertex debuggable end-to-end.  

---

# N8 mission and boundary

## What N8 is authoritative for

* Emitting **metrics / traces / logs** for AL with consistent correlation keys
* Emitting **governance-visible change evidence** (e.g., “policy_rev switched to X”, “exec profile switched to Y”)
* Providing **incident signals** for critical conditions (especially outcome QUARANTINE)
* Supporting **SLO / corridor check inputs** (lag, failure rates, outbox backlog, dependency health)

## What N8 must never do

Hard bans (anti-drift):

* **No control plane:** N8 must not change policy, posture, execution, publishing, or ledger state.
* **No backpressure into correctness:** telemetry must not block execution or publishing.
* **No truth substitution:** telemetry is not the audit record (DLA + outcomes are).
* **No payload dumping:** do not log sensitive/full payloads; use refs/digests.

N8 is a tap, not a lever. 

---

# N8 internal subnetworks (inside N8)

1. **O1 Correlation Context Builder**

   * Normalizes and attaches correlation keys to every telemetry event/span/log line
   * Creates a “context object” used across metrics/traces/logs

2. **O2 Metrics Emitter**

   * Exports counters/gauges/histograms (golden signals + AL-specific)
   * Ensures cardinality safety (avoid exploding label space)

3. **O3 Tracing Adapter**

   * Creates spans around key internal stages (intake, authz, ledger permit, effector call, publish)
   * Propagates trace context to N6 and back

4. **O4 Structured Logging Adapter**

   * Emits structured logs with correlation context and stable reason codes
   * Avoids full payload logging; uses digests/refs

5. **O5 Health & SLO Evaluator (read-only)**

   * Computes health summaries used by external corridor checks
   * Emits “health snapshot” telemetry (does not enforce)

6. **O6 Incident Signaler**

   * Emits high-severity signals for:

     * outcome publish QUARANTINE (P0)
     * idempotency key conflicts
     * sustained outbox backlog growth
     * high UNKNOWN/timeout rates
   * Includes evidence pointers (IG receipt refs, outcome_event_id, semantic_key hash)

7. **O7 Change Evidence Reporter**

   * Emits “policy_rev active” and “exec_profile_rev active”
   * Emits every switch as a change event with `(old_rev, new_rev, loaded_at)`
   * (It doesn’t perform governance, it records evidence.)

8. **O8 Export Pipeline**

   * Ships telemetry to the configured backend (OTel collector, logs sink)
   * Must be non-blocking; spools/drops under pressure

---

# Correlation keys (the single most important N8 pin)

Every telemetry event/span/log line should carry as many of these as are available:

### Core correlation (always try to include)

* `manifest_fingerprint` 
* `intent_event_id` (envelope event_id) 
* `event_type`
* `ts_utc` (domain time of the event/outcome)

### Semantic execution identity (when available)

* `semantic_key_hash` (or components: ContextPins + idempotency_key)
* `idempotency_key` (careful: may be sensitive; prefer hash in logs/metrics)
* `run_id`, `scenario_id`, `parameter_hash` (ContextPins)

### Attempt identity (when applicable)

* `attempt_id`, `attempt_no`
* `permit_id` (or a safe hash)

### Outcome identity (when applicable)

* `outcome_event_id`
* `outcome_id` (internal)
* `publish_state` (pending/admitted/quarantined)

### Policy/posture attribution (always when known)

* `policy_id`, `policy_rev`
* `exec_profile_id`, `exec_profile_rev`
* `origin`, `actor_principal` (again: careful; can hash in logs/metrics)

### External boundary correlation (when applicable)

* `effector_adapter_id`
* `effector_request_id`
* `ig_receipt_ref`
* bus coordinate (topic/partition/offset) if known

**Designer pin:** Metrics labels should use *hashed/low-cardinality* variants (e.g., `action_type`, `status`, `reason_code`, `policy_rev`) and avoid raw actor ids or raw idempotency keys (cardinality explosion).

---

# Golden signals + AL-specific telemetry (what must exist)

## 1) Golden signals

* **Throughput:** intents/sec, outcomes/sec
* **Latency:** end-to-end intent→outcome publish (histogram)
* **Errors:** failure rate by category
* **Saturation:** consumer lag, queue depth, worker utilization

## 2) AL-specific must-haves

* **Outcome counts by decision:** EXECUTED / DENIED / FAILED
* **Denied-by-policy rate:** by action_type + deny_reason_code + policy_rev
* **Retry pressure:** retryable failures/sec, retry backlog size, next_retry_at distribution
* **UNKNOWN rate:** count of `UNCERTAIN_COMMIT` outcomes and ambiguous receipts
* **Outbox backlog:** pending publish count + oldest pending age
* **Publish results:** ADMIT/DUPLICATE/QUARANTINE counts + publish latency
* **Effector health:** timeout rate, dependency-down rate, p95 effector call latency
* **Idempotency conflicts:** count + severity signals

These are required to operate L5/L7 loops safely (even though N8 doesn’t enforce them). 

---

# Stage spans (trace topology)

N8 should create spans around these internal stages (names illustrative):

* `al.intake.normalize` (N1)
* `al.authz.evaluate` (N3)
* `al.ledger.permit_grant` (N4)
* `al.exec.attempt` (N5)
* `al.effector.call` (N6)
* `al.ledger.attempt_record` (N4)
* `al.outcome.enqueue` (N7/N4)
* `al.publish.ig_submit` (N7)
* `al.publish.receipt_commit` (N4)

**Trace propagation pin:** If the incoming intent has trace context, N8 must preserve it and create child spans; N6 calls should carry the trace context too.

---

# Non-blocking export (the “never break correctness” pin)

N8 must be **non-blocking**:

* If telemetry backend is down or slow:

  * drop or spool telemetry (bounded) **without blocking** execution/publish
  * emit a local health indicator (“telemetry degraded”) if useful

**Designer pin:** correctness is carried by ledger + outcomes + DLA, not by telemetry. Telemetry loss is an ops issue, not a correctness issue.

---

# Incident signalling (what triggers P0/P1)

## P0 triggers (must be loud)

* **ActionOutcome quarantined by IG** (publish QUARANTINE)
  Include: `outcome_event_id`, `semantic_key_hash`, `ig_receipt_ref`, reason code.
  This threatens audit closure.

## P1 triggers (still urgent)

* sustained outbox backlog growth
* idempotency key conflicts
* sustained UNKNOWN/timeout spikes
* sustained effector dependency-down
* policy/posture unavailable (fail-closed state)

N8 emits these as structured incident telemetry (and possibly a dedicated “incident stream” if you later want it).

---

# Governance “change evidence” (N8’s governance hook role)

N8 must emit a **change evidence event** whenever N2 switches:

* `policy_rev old→new`
* `exec_profile_rev old→new`
  with:
* loaded_at time
* digest
* environment profile
* who/what triggered it if that info is available (by-ref)

This does not replace governance records, but provides the operational trace that “these rules were active when these outcomes happened.”

---

# Environment ladder posture (N8-specific)

Allowed differences by env:

* sampling rate (local high, prod sampled)
* verbosity of logs (local more detail, prod more strict)
* which backends are used (local console vs prod OTel stack)

Not allowed differences:

* correlation keys presence (must still exist)
* “tap-only” rule (never a control path)
* P0 signal for outcome QUARANTINE

This ensures local exercises the same operational semantics (just scaled down). 

---

# N8 drift bans (final guardrails)

* **Banned:** N8 toggling drain/kill directly
* **Banned:** execution/publish awaiting telemetry flush
* **Banned:** logging full payloads / secrets
* **Banned:** metrics labels that include raw actor ids or raw idempotency keys
* **Banned:** treating telemetry as audit truth

---

That’s N8: a strict **observability + governance evidence tap** that keeps the whole AL inner network operable, attributable, and safe—without ever becoming a hidden controller.

If you want, next we can illuminate the *optional* nodes **N9 (callbacks)** and **N10 (remediation surface)** only if you plan to enable async actions or first-class triage in v0; otherwise we can stop here with a clean v0 inner network fully revealed.

---

Absolutely — opening **N9: Async Callback Intake & Correlator**.

N9 exists **only if you enable async actions** (where completion/confirmation arrives later). Its entire job is to turn **callback traffic** into **append-only closure facts** for the *correct* semantic action line, without ever triggering execution or mutating history.

---

## N9 role and hard boundary

### N9 is responsible for

* Consuming **Callback events** delivered from EB (already admitted by IG)
* Validating/normalizing callback envelopes + payloads
* Enforcing a **callback allowlist** (producer/type/scope) using explicit policy inputs (via N2)
* **Deduping callbacks** under at-least-once delivery
* **Correlating** the callback to a single `semantic_key`
* Requesting N4 to **append a closure outcome** (append-only)
* Letting N7 publish that closure via the outbox (N9 never publishes)

### N9 must never do

* **Never start execution** (no calls to N5/N6, no effectors)
* **Never mutate** existing outcomes/attempts (closure is appended)
* **Never “guess” correlations** (no time-based matching, no scanning)
* **Never bypass IG/EB** (callbacks enter the platform only through the trust boundary)

---

## N9 internal subnetworks (opaque boxes inside N9)

1. **C1 Callback Consumer**

   * Subscribes to callback event types
   * Extracts `topic/partition/offset` for telemetry only

2. **C2 Envelope + Schema Decoder**

   * Parses canonical envelope (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`, optional ContextPins)
   * Routes by `(event_type, schema_version)` to the correct callback payload parser

3. **C3 Callback Policy Gate**

   * Uses a **CallbackPolicySnapshot** (sourced via N2) to decide if a callback is trusted/processable
   * Enforces:

     * allowed callback producers
     * allowed callback types
     * allowed scopes/targets (if applicable)
   * If untrusted ⇒ **fail-closed** (record + triage), do not apply closure

4. **C4 Correlation Builder**

   * Extracts correlation candidates from the callback payload:

     * `semantic_key` (best)
     * `effector_request_id` (next)
     * `parent_intent_event_id` (next)
   * Produces a `CorrelationRequest`

5. **C5 Correlation Resolver**

   * Resolves `CorrelationRequest → semantic_key_hash` via N4’s indices:

     * direct semantic key
     * lookup `effector_request_map`
     * lookup `intent_event_map`
   * If ambiguous (multiple matches) ⇒ **fail-closed** conflict

6. **C6 Callback Dedupe Gate**

   * Ensures **one callback event produces at most one closure append**
   * Dedupe key: `callback_event_id` (envelope `event_id`)
   * Implemented via N4 (`callback_dedupe`) so restarts are safe

7. **C7 Closure Translator**

   * Maps `(callback_type, payload)` → a stable `closure_state` and evidence refs
   * Example closure states (names flexible):

     * `CONFIRMED`
     * `REJECTED`
     * `COMPLETED`
     * `FAILED_FINAL`
   * Produces a `ClosureAppendRequest`

8. **C8 Pending Callback Stash + Resolver Loop**

   * Handles “callback arrived before we can correlate” (out-of-order reality)
   * Stores unresolved callbacks with backoff + TTL, then retries correlation
   * If still unresolved after TTL ⇒ orphan

9. **C9 Orphan / Conflict Handler**

   * For orphan/untrusted/ambiguous callbacks:

     * records a triage record (by-ref evidence pointers)
     * emits a high-signal telemetry event
     * optionally hands off to N10 remediation surface (if enabled)

10. **C10 Telemetry Tap**

* Emits: callback rates, dedupe hits, correlation success rate, orphan rate, conflict rate
* Always includes correlation keys when known

---

## Callback correlation rules (pinned, deterministic)

### Correlation precedence (authoritative)

1. **`semantic_key` present in callback**
2. else **`effector_request_id`**
3. else **`parent_intent_event_id`**
4. else ⇒ **Orphan**

### Fail-closed constraints

* If correlation yields **0 matches** ⇒ pending stash → orphan after TTL
* If correlation yields **>1 match** ⇒ **Conflict** (never apply closure)

No “best effort” matching.

---

## N9 state machine (per callback event)

```
RECEIVE
  -> VALIDATE (envelope + schema)
  -> POLICY_GATE (trusted producer/type?)
  -> DEDUPE (callback_event_id)
  -> CORRELATE (resolve to semantic_key_hash)
        | success -> TRANSLATE -> APPEND_CLOSURE (via N4) -> DONE
        | none    -> PENDING_STASH -> (retry loop) -> ORPHAN
        | many    -> CONFLICT -> TRIAGE -> DONE
```

Key point: **APPEND_CLOSURE** is the only “state-changing” act, and it is performed by **N4** (append-only + idempotent).

---

## What N9 sends to N4 (the two critical requests)

### 1) `CorrelationLookupRequest`

Contains one of:

* `semantic_key_hash` (direct)
* `effector_request_id`
* `parent_intent_event_id`

N4 returns:

* `semantic_key_hash` (resolved), or
* not found, or
* conflict (multiple)

### 2) `ClosureAppendRequest` (J15a in practice)

Minimum contents:

* `callback_event_id` (dedupe key)
* `semantic_key_hash` (resolved)
* `closure_state` (stable enum)
* `closure_ts_utc` (domain time of callback)
* `evidence_refs[]` / `status_ref` / `response_digest`
* optional `predecessor_outcome_event_id` (linkage)

N4 responsibilities (not N9):

* dedupe callback_event_id
* append closure outcome immutably
* enqueue in outbox for N7 to publish

---

## Handling “callback before action exists” (out-of-order reality)

This will happen in production. N9 must not treat it as an error immediately.

**Pinned behavior:**

* Put in **pending stash** with backoff (e.g., retry after 5s, 30s, 2m…)
* Stop after a TTL window (e.g., 24h or profile-based), then mark **orphan**
* Orphan is triage-only; it must not alter action state

---

## Callback policy (how N9 stays secure without becoming an auth engine)

N9 should consume a **CallbackPolicySnapshot** from N2 (same philosophy as N3/N5 snapshots):

* allowed producers per callback_type
* allowed callback types
* optionally allowed scopes/targets
* policy rev + digest + loaded_at

If policy snapshot is unavailable:

* N9 should **fail-closed**: stash callbacks as “unprocessed due to policy unavailable” (retryable), not apply closure.

---

## Environment ladder knobs (N9-specific)

Allowed differences by environment profile:

* whether async actions are enabled at all
* which callback types are enabled
* pending stash TTL/backoff
* strictness of producer allowlist checks (local permissive, prod strict)

Not allowed to differ:

* correlation precedence
* dedupe-by-callback_event_id
* append-only closure (no mutation)
* no execution triggered

---

## N9 non-joins (explicit drift bans)

* N9 must not call N5/N6 or initiate new attempts
* N9 must not publish to IG/EB
* N9 must not mutate prior outcomes
* N9 must not “resolve” by scanning storage or using timestamps
* N9 must not accept untrusted producers silently

---

If you want the clean next step: decide whether **async actions are v0** or **v1**. If v0, we keep N9 disabled and treat all enabled action types as bounded-time. If v1, we’ll pin (1) which action types are async, (2) which callback types correspond to which closure states, and (3) the required correlation basis per callback type so no one can ship “uncorrelatable callbacks” into the system.

---

Absolutely — opening **N10: Quarantine / Remediation Surface**.

N10 is the **internal-facing triage surface** for “things that went wrong” related to AL (quarantine, conflicts, orphans, stuck outbox), and the **only** place inside AL where we *expose* those issues in a structured way for operators/tools — **without bypassing IG/EB, without mutating truth, and without becoming a shadow control plane**.

---

## N10 mission and boundary

### What N10 is responsible for

* Providing a **read-mostly** view of triage items affecting AL:

  * quarantined ActionOutcomes (P0)
  * quarantined ActionIntents (upstream, if surfaced)
  * idempotency key conflicts
  * orphan/untrusted callbacks (if N9 enabled)
  * stuck outbox / repeated publish failures
  * repeated UNKNOWN / resolution failures
* Exposing **evidence pointers** (IG receipt refs, payload digests, object-store evidence refs)
* Supporting **only three** safe operator actions:

  1. **Inspect** (read-only)
  2. **Safe republish request** (re-enqueue an existing `outcome_event_id` for publish)
  3. **Governed change request** (propose policy/profile revisions; activation occurs outside AL)

### What N10 must never do

Hard bans (anti-drift):

* **No bypass** of IG/EB (no internal “force admit”)
* **No payload editing** (no “fix it in place”)
* **No outcome mutation** (append-only truth remains sacred)
* **No execution triggers** (cannot call N5/N6)
* **No stealth toggles** (cannot directly change N2 snapshots; only propose)
* **No “release quarantined event into AL intake”** (re-entry must be via IG)

---

## N10 internal subnetworks (inside N10)

1. **R1 Triage Index Builder**

   * Consumes signals from N4/N7/N9/N1 (and optionally IG quarantine feed)
   * Builds a queryable index of triage items with stable IDs

2. **R2 Evidence Resolver**

   * Given a triage item, resolves by-ref pointers:

     * IG receipt refs
     * outbox state refs
     * payload digests
     * evidence blob refs in object store (if present)
   * Does not “open” payloads unless privileged (access controlled)

3. **R3 Query API**

   * Supports filterable queries:

     * by severity (P0/P1/P2)
     * by category (QUARANTINE_OUTCOME, KEY_CONFLICT, ORPHAN_CALLBACK, OUTBOX_STUCK)
     * by time window
     * by action_type / origin / policy_rev
     * by semantic_key_hash / outcome_event_id / attempt_id

4. **R4 Action Request API**

   * Allows only:

     * `RequestRepublish(outcome_event_id)`
     * `RequestPolicyChange(proposal_ref)`
     * `RequestExecProfileChange(proposal_ref)`
   * Returns an auditable request id and emits a telemetry event

5. **R5 Privilege & Audit Guard**

   * Enforces that:

     * inspection of quarantined payload evidence is privileged
     * republish requests are privileged
     * change requests are privileged
   * Emits an audit log entry for every operator interaction (by-ref pointers, not payload)

6. **R6 Incident Escalation Adapter**

   * For P0 items (especially outcome quarantines), emits a “page me” signal (via N8 telemetry or dedicated incident channel)

7. **R7 Remediation State Tracker**

   * Tracks lifecycle of remediation requests:

     * requested → acknowledged → executed (republished) → resolved/failed
   * This is tracking metadata, not truth mutation

---

## What N10 indexes (triage item types)

### 1) **Outcome Publish QUARANTINE** (P0)

Source: N7 publish receives IG QUARANTINE; N4 outbox marks `QUARANTINED`.

Triage item includes:

* `triage_id`
* `outcome_event_id`, `outcome_id`
* `semantic_key_hash`
* IG receipt ref + quarantine reason code
* payload digest (immutable)
* timestamps + publish attempt count
* current posture snapshot refs (policy_rev, exec_profile_rev)

**Pinned:** This is P0 because audit closure is threatened.

### 2) **Stuck Outbox / Repeated Publish Failures** (P1)

Source: N4 outbox pending too long; repeated publish failures.

Includes:

* oldest pending age
* last error category
* publish attempts
* counts by action_type

### 3) **Idempotency Key Conflict** (P1/P0 depending on volume)

Source: N4 detects `semantic_key` collision with different `intent_fingerprint`.

Includes:

* semantic_key_hash
* stored fingerprint vs new fingerprint
* first/last seen intent_event_ids
* affected action_type/origin/actor hashes
* recommended action: producer fix; block by policy if abusive

### 4) **Orphan / Untrusted Callback** (if N9 enabled)

Source: N9 cannot correlate or policy gate fails.

Includes:

* callback_event_id
* producer principal
* callback_type
* reason (untrusted, no correlation, ambiguous correlation)
* evidence refs/digests
* pending-stash expiry time (if applicable)

### 5) **Execution Uncertainty Hotspots** (P1)

Source: high UNKNOWN rates, repeated UNCERTAIN_COMMIT outcomes.

Includes:

* effector adapter id
* action_type
* time window counts
* suggested mitigation: safe-mode caps/drain; enable status probe; adjust timeouts

### 6) **Normalization Failures (unexpected)** (P2 but important for attacks/misconfig)

Source: N1 emits NormalizationFailure.

Includes:

* failure reason code
* envelope fields if parsed
* raw_event_ref (digest/pointer)

---

## N10 “safe actions” (the only allowed outputs)

### A) Inspect (read-only)

* returns triage item metadata and evidence pointers
* optionally fetches evidence blobs (privileged)
* never edits anything

### B) Safe republish request

`RequestRepublish(outcome_event_id)`:

What it does:

* asks N4/N7 to **re-enqueue** the existing immutable outcome for publish
* does **not** create a new outcome
* does **not** execute anything
* publish still goes through IG and is recorded via receipts

This is safe because the event_id is stable and IG will DUPLICATE if already admitted.

### C) Governed change request (proposal)

`RequestPolicyChange(proposal_ref)` or `RequestExecProfileChange(proposal_ref)`:

What it does:

* creates a **proposal artifact reference** that Run/Operate/Gov can review/activate
* N10 does not activate it
* activation is visible as snapshot rev change via N2 later

---

## N10 lifecycle for a P0 outcome quarantine (example)

1. N7 publishes → IG returns QUARANTINE → N4 marks outbox QUARANTINED
2. N8 emits P0 incident telemetry
3. Operator opens N10:

   * inspects triage item (receipt reason + payload digest + policy_rev)
4. Operator chooses remedy outside AL:

   * fix producer identity, schema allowlist, or policy, etc.
5. Operator uses N10 to `RequestRepublish(outcome_event_id)`
6. N7 republishes the exact same event_id
7. IG returns ADMIT/DUPLICATE
8. N4 marks ADMITTED; triage item resolved; DLA closure is restored

---

## N10 environment ladder posture

Allowed differences by env:

* local may have a simpler UI/CLI and permissive privileges
* dev/prod require strong access control and audit logging

Not allowed differences:

* safe action set (inspect/republish/propose only)
* no bypass / no mutation rules
* outcome quarantine remains P0 everywhere (severity can route differently, but it’s still “critical”)

---

## N10 drift bans (final guardrails)

* **Banned:** “force admit” or bypassing IG
* **Banned:** editing quarantined payloads/outcomes in place
* **Banned:** directly changing active policy/posture inside N10
* **Banned:** triggering execution to “repair” an issue
* **Banned:** reprocessing by injecting into N1 (must go through IG)

---

If you want, the next step is to decide **whether N10 is v0** (first-class triage UI/workflow now) or **v1** (start with telemetry-only and add N10 later). The core AL correctness does *not* require N10, but production operations and audit integrity get dramatically easier with it.

---

## USER: PAUSE FOR REFLECTION

Absolutely — and it’s worth doing, because what we’ve built is a **two-level graph**:

1. **AL as a vertex** in the platform network (IG/EB/DLA/DF/Case/Ops/etc.)
2. **AL as its own internal network** of subnetworks (N1–N10), with joins/paths/loops that mirror production realities (at-least-once, retries, publish uncertainty, governance).

Here’s the “depth + complexity” in a way that’s useful and stabilizing (not overwhelming).

---

## 1) What makes this design “deep” (and why it had to be)

### The platform forces three hard realities

* **At-least-once delivery + replay/backfill** (duplicates are normal, not exceptional)
* **Side effects are dangerous** (double execution is catastrophic)
* **Auditability is non-negotiable** (DLA closure must be possible forever)

Those three realities force AL to be more than “consume intent → call API → emit outcome.”
They force **permits + durable ledger + outbox + append-only history + governed controls**.

---

## 2) The keystone triangle that creates most of the complexity

The internal network has a “keystone triangle”:

* **N4 (Ledger/Idempotency/Outbox)** = truth + permits + crash safety
* **N5 (Orchestrator)** = attempt lifecycle + retry/resolution + posture handling
* **N7 (Publisher)** = IG submission + ADMIT/DUPLICATE/QUARANTINE + retry publish

This triangle exists to solve the classic failure mode:

> side effect happened ✅
> but publishing failed ❌
> restart/replay happens 🔁
> …and we must republish, not re-execute.

That’s why the design feels “deep”: it closes the crash window and makes replay safe.

---

## 3) Why the network is still *manageable* (not arbitrary complexity)

Even though there are many joins/paths/loops, the design is modular because:

### Each node has exclusive truth/authority

* N3 decides **allow/deny/fail-closed**
* N4 decides **duplicate vs permit vs conflict**, and is truth for history
* N5 decides **attempt sequencing** and maps receipts to retry/terminal
* N6 is the **adapter boundary** (execute/probe; no publish)
* N7 publishes **only ledger-truth**, never executes
* N8 is **tap-only** (never control)
* N9/N10 are optional and bounded (closure + triage)

That separation is the main reason this complexity doesn’t “explode.”

### Non-joins are doing a lot of work

We banned entire classes of drift:

* publisher triggering execution
* telemetry controlling behavior
* remediation bypassing IG
* callbacks triggering execution
* AL talking to SR/Engine/OFP/IEG to decide
  These bans keep the network from degenerating into spaghetti.

---

## 4) The “minimum complexity” for production-readiness

If you strip this to the minimum that still satisfies the pins, v0 AL is basically:

* **N1 + N3 + N4 + N5 + N6 + N7 + N8**
* with **N9/N10 optional**

And inside that, the truly essential mechanisms are:

* semantic key `(ContextPins, idempotency_key)`
* permit/lease
* attempt journal (append-only)
* immutable outcomes
* outbox publish retry with stable `outcome_event_id`

Everything else is scaffolding around those pillars.

---

## 5) What this buys you (the payoff)

Because of the structure we’ve pinned, you get:

* **Effectively-once side effects under replay** (the hardest promise)
* **Deterministic convergence under duplicates** (no new truth minted)
* **Crash-safe recovery** (republish, don’t re-execute)
* **Audit closure** that survives retention and outages (DLA gets joinable facts)
* **Governed change** without stealth behavior (policy/posture revs)
* **Environment ladder parity** (local/dev/prod differ by profile strictness only)

That’s the reason the graph is as deep as it is.

---

## 6) How we prevent ourselves from drowning in it

We already did the most important thing: **we made the complexity legible** by:

* naming the nodes
* pinning the join contracts
* pinning canonical paths P1–P10
* pinning loops L1–L7
* pinning non-joins

So even though it’s a big network, it’s not ambiguous.

---