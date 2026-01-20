# Decision Log & Audit Design Authority

This file is a rough collection of design or brainstorm notes for the Decision Log & Audit. It views the whole platform as a network and expands open the decision log and audit's position in this network and illuminates it.

---

Cool — we’ll do exactly that: treat **DLA’s inner network as a black box**, and pin **what the rest of the platform expects from DLA** (inputs, outputs, authority boundaries, and handshakes). Whatever we pin here becomes the **outer-law** that the inner design must later satisfy.

Everything below is constrained by the platform pins: **IG→EB is the only front door**, **Canonical Event Envelope at the bus boundary**, **ContextPins everywhere**, **by-ref over copying**, **no PASS → no read**, **watermark determinism**, **explicit degrade recorded**, **at-least-once duplicates are real**.

---

## 1) DLA’s role in the larger network (what it *is*)

**DLA is the loop’s immutable flight recorder.** It exists so you can reconstruct, later, **what we knew, why we acted, and what we did**, without turning the audit store into a raw data lake.

### What DLA is authoritative for

DLA is the **system-of-record** for:

* the **append-only audit record** of a decision context (decision-time truth bundle),
* the **supersedes/correction history** (never overwriting),
* the audit’s **deterministic queryability** (no “scan latest” semantics).

### What DLA is *not* authoritative for

DLA does **not** decide, execute, validate, or compute. Those authorities remain with:

* **IG** for admit/quarantine/duplicate & receipts (trust boundary),
* **EB** for durable append + replay,
* **DF** for decision truth + provenance emission,
* **AL** for effectively-once execution + immutable outcomes,
* **OFP/IEG/DL/Registry** for their respective truths.

---

## 2) DLA’s position in the flow (outer edges only)

### Upstream → DLA (how facts reach it)

**DLA does not accept “direct writes” from DF/AL in production semantics.**
Decisions and outcomes are **real traffic** and therefore must enter via **IG → EB**, and DLA is an always-on **consumer** of that replayable log.

Concretely, the deployment map pins DLA as reading:

* decisions / intents / outcomes from `fp.bus.traffic.v1`,
  and writing immutable audit records to `dla/audit/...` (object store), with an optional `audit_index` DB for query.

### DLA → downstream consumers (who uses it)

DLA is read by:

* **Case Workbench** (investigation UI/workflow) as **by-ref evidence** into case timelines, 
* **Governance / audit tooling** (explainability, compliance review, incident reconstruction), 
* **Offline assembly** as deterministic exports/slices (when needed).

Optional: DLA may emit **pointer events** to `fp.bus.audit.v1` (not mandatory, but allowed as a convenience distribution plane for “audit pointers”).

---

## 3) The black-box contract: what DLA consumes and produces

### Inputs DLA consumes (from EB)

DLA consumes **Canonical Event Envelope** messages (required `{event_id, event_type, ts_utc, manifest_fingerprint}` + optional pins and payload).

But not “all events.” DLA only cares about the **decisioning lineage** events:

1. **DecisionResponse** (emitted by DF, admitted by IG, stored in EB)
2. **ActionOutcome** (emitted by AL, admitted by IG, stored in EB)

### Outputs DLA produces (to durable substrates)

DLA produces **two append-only families**:

1. **Canonical Audit Decision Records** (immutable; correction via supersedes chain)
2. **Audit Quarantine Records** (immutable evidence of “couldn’t accept as canonical”)

And it produces **query/export surfaces** that are deterministic and key-driven (never “latest by scan”).

---

## 4) The key outer handshake: what must be inside the “audit truth bundle”

This is the single most important join in the platform for DLA:

### J12 (DF + optional AL/IG evidence) → DLA

**What crosses is the minimum immutable facts** needed to reproduce/justify the decision later, **by-ref + hashes**, not raw payload embedding.

So the platform expects every canonical audit record to include *pointers/hashes* for:

#### A) What was decided on (stimulus basis)

* an **event reference basis** (a by-ref pointer, typically EB position/locator)
  This is where the Canonical Envelope matters:
* `ts_utc` is the domain time; ingestion time is separate IG metadata and must not overwrite domain meaning.

#### B) What context was used (replay determinism hook)

DLA must record **the same determinism tokens** that make replay parity possible:

* **OFP provenance**: `feature_snapshot_hash` + `input_basis` watermark vector (+ freshness + group versions),
* **IEG provenance** (when used): `graph_version`, whose meaning is “applied offsets watermark vector + stream identity,”
* and critically: watermarks are monotonic; backfills don’t “time travel,” they create new offsets/watermark states.

#### C) What constraints applied

* **Degrade posture**: DL outputs mode + mask; DF must obey; **DLA must record** that posture.

#### D) What policy/model version was used

* **Registry active bundle resolution** must be recorded so the decision is reproducible/explainable later.

#### E) What the system did

* **Decision outcome** and **ActionIntents** (with idempotency keys), plus (optionally) ActionOutcomes to close “intent vs executed.”

That’s the outer “must-record” set. The inner network of DLA later exists mainly to enforce that this set is always present (or quarantined).

---

## 5) DLA’s operational behavior as a networked service (outer expectations)

### 5.1 Append-only truth + correction semantics

* Canonical audit records are **immutable**.
* Corrections happen by **appending a new canonical record** and linking it to the prior one via a **supersedes chain** (never overwrite).

### 5.2 Idempotent under at-least-once delivery

The platform explicitly pins end-to-end at-least-once + local idempotency recipes:

* IG dedupe + receipts,
* AL uniqueness `(ContextPins, idempotency_key)`,
* **DLA uniqueness `(ContextPins, audit_record_id)`**.

Meaning: replay, retries, duplicates **must not create multiple audit truths**.

### 5.3 Quarantine is first-class inside DLA

Even if an event is admitted to EB, it may be **not auditable** (missing provenance).
Platform expectation: **DLA quarantines incomplete provenance** rather than writing a “half truth,” and quarantine remains inspectable (no silent drop).

### 5.4 By-ref posture is mandatory

DLA must not become a second data lake:

* store refs/hashes/metadata,
* not raw event payloads,
* not full feature vectors.

This aligns with the platform-wide by-ref primitive (“scan latest and hope” is disallowed; refs/locators are the join mechanism).

---

## 6) DLA’s interactions with neighboring components (explicitly, no hidden assumptions)

### DLA ↔ EB / IG

* DLA trusts EB for **durable ordering & replay coordinates** (partition/offset semantics).
* DLA does **not** re-validate admission policy; IG is the trust boundary.
* DLA may use **EB coordinates as the canonical `event_ref`**, and optionally store/ref IG receipts if they are provided by-ref (but must not require “scanning IG storage” to find them). This is consistent with by-ref/no-scanning law.

### DLA ↔ DF (the primary producer relationship)

* DF is responsible for emitting DecisionResponse with the full provenance required by J8/J9/J10; DLA enforces completeness.
* DF must obey degrade mask; DLA must record the posture used (including fail-closed fallback).

### DLA ↔ OFP / IEG / DL / Registry

DLA does **not** call these systems at decision time (no synchronous dependency in the audit recorder).
Instead, DLA records the provenance tokens DF already records:

* OFP `feature_snapshot_hash` + `input_basis`, 
* IEG `graph_version` (when used), 
* DL degrade mode+mask, 
* Registry ActiveBundleRef. 

This keeps DLA from becoming a “recompute engine” and preserves the black-box join discipline.

### DLA ↔ Case Workbench / Label Store

* Case Workbench consumes DLA audit records **by ref** as evidence in case timelines. 
* Labels remain authored/true in Label Store; DLA is evidence, not label truth.

### DLA ↔ Data Engine (indirect, but important)

Engine “audit_evidence” outputs exist and are routed to audit/governance planes, but **never as traffic**.
If DLA references engine audit evidence, it must do so:

* **by locator/ref**, and
* only with the required PASS evidence (no PASS → no read; no scanning).

---

## 7) The outer “shape” of DLA operations (a few canonical sequences)

### Normal decision recording

```
EB(admitted business traffic) -> DF decides (using OFP/IEG/DL/Registry)
DF emits DecisionResponse -> IG admits -> EB appends
DLA consumes DecisionResponse -> writes immutable AuditDecisionRecord
```

This is exactly the platform hot-path placement.

### Closing the loop with outcomes

```
DF emits ActionIntents -> AL executes (effectively-once) -> emits ActionOutcome -> IG admits -> EB
DLA consumes ActionOutcome -> links outcome evidence to the decision’s audit lineage
```

(AL’s outcome immutability + idempotency is pinned; DLA records, doesn’t execute.)

### Incomplete provenance handling

```
DLA consumes DecisionResponse (missing required provenance) -> DOES NOT write canonical audit truth
DLA writes audit_quarantine record (append-only) so operators can see failures
Upstream fixes (DF emits corrected DecisionResponse) -> DLA ingests successfully
```

Quarantine is required to prevent “half-truth audit.”

---

## The one outer pin I’m adding now (designer authority)

To keep DLA from drifting into an accidental “recompute service”:

**DLA is a recorder, not a resolver.**
It **never** fetches OFP features, never reconstructs IEG state, never resolves registry bundles “as-of,” and never interprets raw event payloads. It records the provenance tokens DF provides (hashes/refs/watermarks) and enforces completeness/quarantine.

That’s the clean separation that makes the inner network implementable without breaking the platform’s join rules.

---

If you’re happy with this outer-network role, the next step is: we keep the inner network black box **but** we now derive its required internal modules *only* from these outer obligations (ingest from EB safely, compute stable ids, enforce completeness/quarantine, append-only persistence, corrections linking, deterministic query/export).

---

Yes — there’s a **small set of “DLA nature” pins** that are worth locking **before** we talk joins, because they determine what any join *can* look like without drift.

Below are the pins I’m **declaring authoritative for this brainstorm** (most are already implied by platform law; a couple are “designer choices” to prevent ambiguity).

---

## Hard pins to lock now

### PIN-DLA-1 — DLA is a recorder, not a resolver

DLA **never recomputes** features/identity/policy, never “looks up” context from OFP/IEG/Registry at ingest time. It records the provenance tokens already present in DF outputs and enforces completeness/quarantine. (By-ref posture; no data-lake creep.)

### PIN-DLA-2 — DLA ingests from the replayable log plane (EB), not direct writes

DLA is a **consumer** of admitted events (DecisionResponse, later ActionOutcome). No “DF writes straight into DLA” in production semantics; everything goes through the IG→EB front door first.

### PIN-DLA-3 — Two canonical output families, both append-only

DLA produces:

1. **Canonical AuditDecisionRecord** (immutable; corrections are new records)
2. **AuditQuarantineRecord** (immutable; inspectable evidence of non-canonical ingests)

Indices/query views are **derivative** (rebuildable) and must not be treated as truth.

### PIN-DLA-4 — Identity posture: “anchor id” vs “record id” are different

* **Decision anchor**: `(ContextPins, decision_id)` groups the lifecycle (original + corrections + linked outcomes).
* **Audit record identity**: `audit_record_id = deterministic hash of canonicalized audit content`
* **Idempotent ingest key**: `(ContextPins, audit_record_id)` with duplicate ingest as **NO-OP**.

(And bus events themselves carry a stable `event_id` for ingest/bus dedupe; DLA doesn’t redefine that, but benefits from it.) 

### PIN-DLA-5 — Corrections are only via explicit supersedes linkage

No in-place updates. A second canonical record for the same decision anchor is only acceptable if it includes a valid `supersedes_audit_record_id` **within the same ContextPins**. Otherwise: quarantine.

### PIN-DLA-6 — Completeness gate is mandatory and fail-closed

If required provenance is missing, DLA must **not** write canonical truth; it writes quarantine with reason codes (at minimum: incomplete provenance + supersedes issues).

### PIN-DLA-7 — Privacy posture is strict by-ref (and enforced)

Canonical record must not embed raw event payloads or full feature vectors: store `event_ref`, hashes (e.g., `feature_snapshot_hash`), and metadata only.

**Designer choice (lock now):** If forbidden embedded fields appear, **reject-and-quarantine** (do not “strip” silently). This matches the platform’s “quarantine, don’t hide problems” posture.

### PIN-DLA-8 — Deterministic query and export semantics exist (no “latest by scan”)

DLA must support deterministic query by required axes (ids, ContextPins, time window, degrade mode, entity keys) and deterministic export slices.
It must conceptually support:

* **Historical view** (all records)
* **Current view** (follow supersedes chain)

### PIN-DLA-9 — Evidence pointers must be resolvable without scanning

Any reference DLA stores must be resolvable via explicit locators/refs (EB coords, Engine locators, etc.). No directory scanning / “discover latest.”

### PIN-DLA-10 — Deployment substrate posture (truth vs index)

Canonical audit truth lands in object store under `dla/audit/`. An `audit_index` DB is optional/practical but non-authoritative. 

---

## Soft pins we can defer (won’t block join design yet)

These don’t change *what* the joins must mean, only how they’re implemented:

* **Exact canonical serialization rules** for hashing inputs (we’ve pinned determinism + exclusion of ephemeral fields; encoding details can come later).
* **How “current view” is materialized** (computed vs materialized view) as long as semantics are deterministic.
* **Retention durations** (but we *do* pin the constraint: refs/hashes must remain resolvable for at least the retention window).
* **Export format/transport** (shape is pinned; parquet/json/etc is free).
* **Final enum spellings** for quarantine reason codes (concepts are pinned).

---

Absolutely — here’s the **full “outer-network” map** of the **Decision Log & Audit Store (DLA)** as an **opaque vertex** in a **production-ready** platform: **all joins (direct edges), all meaningful paths (multi-hop sequences), and the real loops (cycles)** that include or depend on DLA.

I’m basing this on your pinned platform picture + deployment wiring (topics/prefixes) and the explicit **J12** flight-recorder join.

---

## 1) DLA’s join inventory (direct edges), treating DLA as opaque

I’ll group joins into **Required (must exist for “production-ready”)** and **Optional (allowed, but not necessary)**.

### 1.1 Required joins (must exist)

#### J-DLA-1 — Event Bus → DLA (primary ingest)

**Direction:** `EB(fp.bus.traffic.v1) → DLA`
**What crosses:** **admitted** canonical-envelope events representing:

* DF’s **DecisionResponse / decision + action intents + provenance**
* AL’s **ActionOutcome** (to close intent vs executed)
* (and in the deployment notes: intents may appear independently too)

**Why it’s required:** DLA is pinned as an **always-on consumer/writer** in the hot path and its inputs are *from the replayable log plane*.

---

#### J-DLA-2 — DLA → Object Store (canonical audit truth)

**Direction:** `DLA → object://dla/audit/...`
**What crosses:** **immutable, append-only** audit records (canonical + quarantine), plus (if you support it) export slices.

**Why it’s required:** deployment wiring pins DLA’s truth to `dla/audit/…` immutable records.

---

#### J-DLA-3 — DLA → Audit Index DB (search/query acceleration, non-truth)

**Direction:** `DLA → db://audit_index` *(optional as a DB, but **some query surface** is required)*
**What crosses:** derived indices for deterministic query axes (ids, pins, entity keys, time, degrade_mode).

**Why it’s required (semantically):** DLA must support deterministic discovery that **doesn’t require scanning**. Whether that’s a DB index or another query mechanism is implementation freedom — but the join exists at the platform level as “DLA provides queryability.”

---

#### J-DLA-4 — Case Workbench → DLA (read evidence by-ref)

**Direction:** `Case Workbench → object://dla/audit/...`
**What crosses:** **evidence refs** (audit records) used to build case timelines and investigations.

**Why it’s required:** the platform pins: “Case work consumes evidence by reference,” and DLA is the canonical flight recorder for those evidence facts.

---

#### J-DLA-5 — Observability pipeline ↔ DLA (operational truth, not domain truth)

**Direction:** `DLA → OTel pipeline`
**What crosses:** metrics/traces/logs for ingest lag, quarantine rates, write failures, query latency.

**Why it’s required:** production-ready means consumer lag and failures are observable (your deployment notes pin OTLP everywhere and the “production-shaped” substrate assumption).

---

### 1.2 Optional joins (allowed in a production platform)

#### J-DLA-6 — DLA → Audit Pointer Topic (distribution of “audit record written” pointers)

**Direction:** `DLA → EB(fp.bus.audit.v1)`
**What crosses:** **pointer events only** (no payload embedding): “audit record written at ref X” etc.

**Why it exists:** it’s an optional convenience plane to let other systems subscribe to audit pointers without polling object storage.

---

#### J-DLA-7 — IG receipts/quarantine refs → DLA (evidence augmentation)

**Direction:** `object://ig/receipts/... and ig/quarantine/... → DLA` *(by-ref only)*
**What crosses:** receipts/quarantine evidence **refs** (and/or receipt ids) that DLA can include as part of the audit evidence chain.

**Important nuance:** DLA must not “scan IG storage.” Any receipt it uses must be referenced deterministically (e.g., included by DF/AL in their emitted provenance, or resolvable from an explicit receipt id). This follows the platform’s “no scanning / by-ref” posture.

---

#### J-DLA-8 — Engine audit_evidence → DLA (forensics-only evidence pointers)

**Direction:** `engine audit_evidence (by locator + PASS) → DLA`
**What crosses:** **refs/digests** to engine “audit_evidence” artifacts for forensic replay (never business traffic).

This join exists because the blueprint pins audit_evidence as routed to DLA/governance planes and consumed by-ref with PASS discipline.

---

#### J-DLA-9 — Run/Operate → DLA (retention, reindex, backfill orchestration)

**Direction:** `Run/Operate → DLA`
**What crosses:** operational commands: retention windows, reindex triggers, controlled backfills/replays (never silent).

This is “production reality”: DLA must survive retention/backfill operations, even though domain truth remains append-only.

---

#### J-DLA-10 — Offline/Governance tools → DLA (deterministic exports/slices)

**Direction:** `Offline tooling → DLA(export)`
**What crosses:** deterministic export requests; output goes to object store (or a governed sink).

This is explicitly listed as what DLA must enable (governed exports).

---

## 2) Paths (multi-hop sequences) involving DLA in a production-ready platform

Here are the **canonical paths** where DLA participates. Think of these as the “routes” traffic/evidence can take through the overall network.

### P1 — Hot path: decision recorded as immutable audit truth

```
Producer event → IG → EB(fp.bus.traffic.v1)
EB → DF (uses OFP/IEG/DL/Registry) → IG → EB (DecisionResponse)
EB → DLA → object://dla/audit/... (+ audit_index)
```

This is the core “flight recorder” path.

---

### P2 — Hot path closure: “intent vs executed” recorded

```
EB → DF emits ActionIntents → IG → EB
EB → AL executes → IG → EB (ActionOutcome)
EB → DLA links Outcome evidence to the decision’s audit lineage
```

This is explicitly pinned: AL outcomes are optional-but-supported ingestion into DLA to close the loop.

---

### P3 — Evidence augmentation path: admission receipts included in audit

```
IG writes ingestion_receipt + (eb_partition, eb_offset) OR quarantine_ref
DF/AL include receipt_id or receipt_ref in their emitted provenance
EB → DLA → stores receipt_ref(s) inside audit record (by-ref)
```

This matches the “minimum audit policy facts” idea and the “optional IG evidence” in J12.

---

### P4 — Quarantine path: DLA refuses canonical storage but preserves evidence

```
EB → DLA receives DecisionResponse
DLA detects incomplete provenance OR invalid supersedes linkage
DLA → object://dla/audit/.../quarantine/... (append-only quarantine)
```

Quarantine is mandatory and inspectable; it’s a first-class path.

---

### P5 — Correction path: supersedes chain, current vs historical views

```
DF emits corrected DecisionResponse (same decision_id, includes supersedes_audit_record_id)
IG → EB → DLA
DLA appends new canonical record (no mutation), links supersedes chain
Queries: historical shows all, current follows chain
```

This is the correction mechanism path.

---

### P6 — Case investigation path: DLA evidence becomes case timeline inputs

```
DLA audit record refs → Case Workbench reads by-ref
Case Workbench builds immutable case timeline
Case Workbench may request manual actions → (AL via IG/EB path)
```

Case work consumes evidence by reference; DLA is the canonical evidence recorder.

---

### P7 — Human truth path (labels): evidence → case → Label Store

```
Case Workbench (using DLA evidence) → Label Store (append-only assertions)
```

This is a platform boundary: DLA provides evidence; Label Store provides truth.

---

### P8 — Optional distribution path: DLA pointer events

```
DLA writes audit record → emits pointer event → fp.bus.audit.v1
Consumers (Case tooling / governance automation) subscribe to pointers
```

Useful when you want “new audit record arrived” triggers without polling.

---

### P9 — Forensics path: engine audit evidence referenced in DLA (by-ref)

```
SR run_facts_view includes engine audit_evidence locators + PASS receipts
DLA record may include refs to those audit_evidence artifacts (by locator+digest)
Investigators/governance use those refs for forensic replay
```

This path exists because audit_evidence is explicitly routed to DLA/governance planes and must obey “no PASS → no read.”

---

### P10 — Replay/backfill path: EB replay rehydrates (idempotent) without duplicating truth

```
Run/Operate triggers replay/backfill OR DLA restarts
EB replays → DLA re-consumes
DLA idempotency prevents duplicate canonical records
Indices can be rebuilt deterministically
```

This is a production readiness path: at-least-once + restart + replay must be safe.

---

## 3) Loops (true cycles) that exist in a production-ready platform

Here are the loops where **outputs eventually feed back into upstream behavior**, with DLA as part of the cycle.

### L1 — Quarantine remediation loop (audit correctness feedback)

```
DF emits DecisionResponse → DLA quarantines (missing provenance)
Operators/devs fix DF emission contract
DF emits corrected DecisionResponse → DLA accepts canonical
```

This loop is explicitly expected: quarantine doesn’t “fix”; upstream must correct and re-emit.

---

### L2 — Human-in-the-loop enforcement loop (evidence → case → manual action → outcome → evidence)

```
DLA evidence → Case Workbench decision → manual action requested
→ ActionIntent → AL executes → ActionOutcome → DLA records outcome evidence
→ Case Workbench consumes updated evidence
```

That’s a real operational loop: humans act based on evidence, generating new evidence.

---

### L3 — Learning + deployment feedback loop (evidence supports governance, models change decisions)

```
DLA evidence + Label Store truth → Offline Shadow → Model Factory → Registry rollout
→ DF uses new ActiveBundleRef → new decisions → DLA records new provenance
```

DLA isn’t the training input authority, but it’s part of the governed story: decisions are auditable across model/policy generations.

---

### L4 — Replay / backfill loop (operational continuity)

```
Retention/backfill declared by Run/Operate → EB replay / archive read
→ DLA re-consumes and reindexes (idempotent; append-only truth unchanged)
```

This is the “production-shaped” continuity loop (restarts + replays don’t corrupt truth).

---

### L5 — Degrade loop (audit makes posture visible; ops changes posture; decisions change)

```
Obs pipeline → DL computes degrade posture → DF constrained decisions
→ DLA records posture used → governance/ops reviews → policy/threshold changes → DL posture changes
```

DLA is not the control plane, but it is the “proof layer” that makes degrade behavior reviewable and therefore adjustable without guessing.

---

## 4) The complete adjacency list (quick “graph view”)

**Inbound to DLA**

* `fp.bus.traffic.v1` (DecisionResponse, intents, outcomes)
* `ig/receipts/*` + `ig/quarantine/*` (refs only; optional)
* `engine audit_evidence` (refs only + PASS; optional)
* `Run/Operate` (retention/reindex/backfill triggers; optional but realistic)

**Outbound from DLA**

* `dla/audit/*` (canonical + quarantine immutable records)
* `db://audit_index` (optional derived indices)
* `fp.bus.audit.v1` pointer events (optional)
* `OTel pipeline` (metrics/traces/logs)

**Primary readers**

* Case Workbench reads `dla/audit/*` by-ref
* Governance/forensics/offline tools read `dla/audit/*` and/or `fp.bus.audit.v1` pointers

---

If you want to “lock” this as authoritative before we zoom into joins: the next clean move is to take **each join above** and pin:

* **what must be present** on that edge (minimal payload),
* **what DLA is allowed to assume** vs must verify,
* and **what failure means** (noop vs quarantine vs “retry later”).

---

Here’s the **complete production set**, ordered as the **agenda** I’d expand in (from “foundation/entry” → “audit truth” → “consumers” → “ops loops” → “optional enrichments”).

1. **[JOIN]** EB (`fp.bus.traffic.v1`) → **DLA** (DecisionResponse / ActionOutcome ingest)

2. **[JOIN]** **DLA** → `object://dla/audit/...` (canonical + quarantine append-only truth)

3. **[JOIN]** **DLA** → `db://audit_index` (non-truth query/index surface)

4. **[PATH]** P1 Hot path: decision recorded as immutable audit truth

5. **[PATH]** P4 DLA quarantine path (non-auditable ingests)

6. **[LOOP]** L1 Quarantine remediation loop (fix upstream → corrected re-emit → accept)

7. **[PATH]** P5 Corrections path: supersedes chain + current vs historical view semantics

8. **[PATH]** P2 Closure path: ActionOutcome linked back to the decision lineage

9. **[JOIN]** Case Workbench → **DLA** (read evidence by-ref)

10. **[PATH]** P6 Case investigation path (audit evidence → timeline)

11. **[PATH]** P7 Human truth path (case outcome → Label Store assertions)

12. **[LOOP]** L2 Human-in-the-loop action loop (evidence → action → outcome → evidence)

13. **[JOIN]** **DLA** → Observability pipeline (lag, failures, quarantine rates, SLOs)

14. **[JOIN]** Run/Operate → **DLA** (retention / reindex / controlled replay orchestration)

15. **[PATH]** P10 Replay/backfill path (EB replay → idempotent re-consume → reindex)

16. **[LOOP]** L4 Operational continuity loop (restart/replay doesn’t corrupt truth)

17. **[JOIN]** Offline/Governance tools → **DLA** (deterministic exports/slices)

18. **[OPTIONAL JOIN]** **DLA** → `fp.bus.audit.v1` (audit-pointer events)

19. **[OPTIONAL PATH]** P8 Pointer distribution path (subscribers react without polling)

20. **[OPTIONAL JOIN]** IG receipts/quarantine refs → **DLA** (evidence augmentation, by-ref only)

21. **[OPTIONAL PATH]** P3 Evidence augmentation path (receipt refs attached to audit lineage)

22. **[OPTIONAL JOIN]** Engine `audit_evidence` → **DLA** (forensics-only, by locator + PASS)

23. **[OPTIONAL PATH]** P9 Forensics path (engine evidence refs used in investigations)

24. **[LOOP]** L3 Learning/model rollout loop (evidence+labels → offline → registry rollout → new decisions → new audit provenance)

25. **[LOOP]** L5 Degrade loop (posture visible in audit → governance/ops adjust → posture changes → decisions change)

If you start expanding from **#1 onward**, we’ll lock the joins in the same order the platform depends on them.

---

Great — here are **#1–#5 expanded** as **production joins/paths** with **DLA treated as opaque** (i.e., we define only *what crosses the boundary*, *what DLA must guarantee externally*, and *what failure means*).

---

## 1) JOIN — Event Bus `fp.bus.traffic.v1` → DLA (primary ingest)

### What this join *is*

A **replayable, at-least-once** fact stream where the only universally meaningful position token is **(stream_name, partition_id, offset)**, with ordering only within a partition and **exclusive-next** checkpoint semantics. 

DLA is pinned as an **always-on consumer/writer** that ingests “decisions + intents + outcomes” from `fp.bus.traffic.v1`.

### What crosses the join (minimum)

**Every admitted message is a Canonical Event Envelope** with required fields:

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
  …and optional pins/tracing/payload.

If the message is **run/world joinable**, it must carry **ContextPins**:
`{manifest_fingerprint, parameter_hash, scenario_id, run_id}`.
`seed` is **separate** and becomes required when the record/event is **seed-variant** (RNG-realisation dependent).

### Which events DLA must process vs ignore

DLA subscribes to the traffic stream but only *acts* on the decision-lineage event types:

* **DecisionResponse** (DF output) — the non-negotiable base for audit truth.
* **ActionOutcome** (AL output) — optional in v0, but supported to “close the loop” (“intent vs executed”).

Everything else on `fp.bus.traffic.v1` is **not DLA’s canonical ingest** (DLA may log/metric it, but it doesn’t become “audit truth” unless referenced by a DecisionResponse via `event_ref`).

### What DLA is allowed to assume (because the platform pins it)

* **EB is not a validator**; admission/shape enforcement is IG’s job. DLA should generally see only “admitted” envelopes.
* Delivery is **at-least-once** and duplicates are normal; DLA must be idempotent.

### What DLA must verify at this boundary (even though DLA is opaque)

DLA must enforce *audit* admissibility (not *bus* admissibility):

**Envelope-level checks**

* Envelope is valid (has required fields; no envelope field collisions; payload stays under `payload`). 
* If event claims run/world joinability (DecisionResponse / Outcome), it carries **ContextPins**; if it is seed-variant, it carries `seed` (or an explicit seed-bearing ref).

**DecisionResponse audit completeness checks** (J12 law)
To be eligible for canonical audit truth, the DecisionResponse payload must include (by-ref/hashes, not embedded raw payloads):

* event reference basis (what was decided on),
* OFP: `feature_snapshot_hash` + `input_basis` watermark vector,
* IEG: `graph_version` if used,
* DL: degrade posture (mode + enough to identify mask used),
* Registry: resolved ActiveBundleRef,
* actions (including idempotency keys),
* audit metadata (ingested_at + supersedes link on correction).

**Duplicate / replay safety**

* DLA’s idempotent ingest key is pinned as **(ContextPins, audit_record_id)**.
  So duplicates/redelivery/replay must become **NO-OP after first canonical write**.

### Failure meaning on this join

Because DLA can’t “un-admit” traffic, it responds by **where it writes**:

* If DecisionResponse is *audit-admissible* → it will later appear in `dla/audit/...` as canonical truth (see #2).
* If DecisionResponse is *not audit-admissible* → it will later appear in `dla/audit/.../quarantine/...` as an inspectable quarantine record (see #5).

---

## 2) JOIN — DLA → Object Store `dla/audit/...` (canonical + quarantine truth)

### What this join *is*

This is DLA’s **system-of-record write**: immutable, append-only audit truth written under `dla/audit/…` (object store), plus optional export materializations.

Platform truth-ownership explicitly assigns:

* **DLA** = truth for **canonical audit decision record** (append-only + supersedes chains) + audit quarantine. 

### What crosses the join (two families)

**A) Canonical AuditDecisionRecord (append-only)**
Must contain the J12 must-record set (by-ref/hashes) and must be **immutable**. Corrections are represented by **new records + supersedes link**, never overwrites.

**B) AuditQuarantineRecord (append-only)**
Must preserve evidence that an audit payload existed but was not admissible as canonical (e.g., missing provenance).

### Non-negotiable write semantics (what the rest of the platform can rely on)

* **Append-only**: canonical and quarantine are never mutated; history is preserved.
* **Idempotent persistence**: if DLA reprocesses the same DecisionResponse, it does not create a second canonical audit record (same `(ContextPins, audit_record_id)` resolves to NO-OP). 
* **By-ref posture**: canonical records store `event_ref` and digests/hashes (`feature_snapshot_hash`, watermark vectors, bundle refs), not raw payloads or full feature vectors.

### “Shape” expectations (not spec, but pinned posture)

Without locking storage tech, the platform expects object keys/records to be naturally retrievable by:

* ContextPins scope,
* time window,
* decision identity (`decision_id` / `event_id`),
* quarantine reason (for quarantine family).

---

## 3) JOIN — DLA → DB `audit_index` (non-truth query surface)

### What this join *is*

A **derived**, rebuildable query acceleration surface. Deployment notes explicitly allow an optional `audit_index` DB, but the truth remains in `dla/audit/...`.

### What crosses the join

Minimal index rows that point *back* to canonical object records, typically containing:

* primary lookup keys: `(ContextPins, decision_id/event_id)`
* pointers: object key / locator for the canonical audit record and/or quarantine record
* query axes needed for operational and investigator queries:

  * `ts_utc` windows,
  * degrade_mode / mask id,
  * ActiveBundleRef,
  * action types + idempotency keys,
  * quarantine reason codes (for quarantine view).

### Non-negotiable semantics

* **DB is not truth**: it can be rebuilt from the object store (and/or EB replay) without changing audit meaning.
* Must support two conceptual views:

  * **Historical** (all canonical + superseded records)
  * **Current** (follow supersedes chain to the latest)

---

## 4) PATH — P1 Hot path: decision recorded as immutable audit truth

Here’s the full production route, focusing on what DLA must be able to do at the end.

### Sequence (outer network)

1. **SR publishes READY + run_facts_view** (downstream must start here; no scanning).
2. **IG admits business traffic into EB** (Canonical Event Envelope; joinability enforced; admit/dup/quarantine with evidence).
3. **DF consumes EB + uses OFP/IEG/DL/Registry**, then emits **DecisionResponse + ActionIntents** back into `fp.bus.traffic.v1` (as envelope events) via IG→EB.
4. **DLA consumes DecisionResponse from EB** and produces the immutable audit record:

   * writes canonical record to `dla/audit/...`
   * updates `audit_index` for deterministic queries
   * duplicates/replays are NO-OP due to idempotent ingest key.

### The hot-path “must hold” invariants

* DecisionResponse must carry the J12 must-record set (refs/hashes/provenance). 
* Degrade posture is explicitly recorded and fail-closed behavior is auditable.
* Replay does not change audit truth: at-least-once delivery cannot create duplicate canonical audit records.

---

## 5) PATH — P4 DLA quarantine path (non-auditable ingests)

This is the “production safety valve”: **never write half-truth audit**, never silently drop.

### Sequence (outer network)

1. DLA consumes a DecisionResponse from `fp.bus.traffic.v1` (admitted, replayable).
2. DLA determines the payload is **not audit-admissible** (fails completeness / consistency / correction rules).
3. DLA writes an **append-only quarantine record** to `dla/audit/.../quarantine/...` and (optionally) indexes it in `audit_index`.
4. No canonical audit record is written for that ingest attempt. 

### What triggers quarantine (the production-minimum set)

At minimum, quarantine must happen when:

* **Incomplete provenance** for the J12 must-record set (missing event_ref, missing feature snapshot hash/input basis, missing degrade posture, missing bundle ref, missing actions/idempotency keys, etc.). 
* **Correction ambiguity**: a “different” record arrives for the same decision anchor without an explicit supersedes chain (because DLA is append-only and cannot guess overwrites).
* **Identity/pins violation**: run-joinable decision event missing ContextPins, or seed discipline violated when the decision is seed-variant.
* **By-ref/privacy posture violated**: embedded raw payload/full feature vectors where only refs/hashes are permitted (fail-closed; don’t “strip silently”).

### What the quarantine record must preserve (so it’s usable)

Even as opaque, the platform expectation is that quarantine is:

* **inspectable and searchable** by ids + time window + reason, and
* includes enough correlation (`event_id`, ContextPins if present, EB position ref if available) to debug upstream compliance.

---

If you want, for each of #1–#3 next we can also pin the **exact “assumption boundary”** in one line each (what DLA trusts vs what it verifies), because that’s usually where drift sneaks in.

---

Absolutely — here are **#6–#10 expanded** (still treating **DLA as opaque**: we define **what the platform expects at the boundary**, the **meaning of the join/path/loop**, and **failure semantics**).

---

## 6) LOOP — L1 Quarantine remediation loop (fix upstream → corrected re-emit → accept)

### What this loop exists to guarantee

A production platform must be able to **detect audit incompleteness**, **surface it**, and **force compliance** *without* corrupting canonical audit truth. This is explicitly pinned: *DLA quarantines rather than writing a “half-truth,” and quarantine is inspectable/countable; remediation is upstream.*

### Participants (opaque DLA)

* **DF** emits DecisionResponse + provenance (semantic authority for decision truth).
* **IG→EB** delivers admitted events at-least-once.
* **DLA** enforces audit completeness and writes either canonical audit or quarantine.
* **Observability / ops** sees quarantine spikes and drives remediation.

### Loop sequence (external behavior)

```
DF emits DecisionResponse → IG admits → EB appends → DLA consumes
    ↳ if incomplete/non-canonical → DLA writes AuditQuarantineRecord (append-only)
Ops/dev triage → fix DF emission / config / provenance → DF re-emits corrected DecisionResponse
    ↳ DLA consumes corrected record → writes canonical AuditDecisionRecord (append-only)
Quarantine remains as historical evidence of the earlier failure.
```

Pins:

* “Quarantine does not fix; upstream must correct and re-emit.”
* DLA must remain append-only for both canonical and quarantine.

### What must be true for remediation to work (production expectations)

* **Quarantine must be queryable** by `decision_id/event_id`, `reason_code`, and time window, so humans can act.
* The quarantine record must preserve **correlation** (ContextPins when available, event_ref if present, and payload evidence by-ref).
* The re-emitted DecisionResponse must be a **full canonical record** (not a delta), so acceptance doesn’t require joining across versions.

### Failure semantics (what DLA does)

* If the corrected DecisionResponse is still incomplete → it **quarantines again** (possibly repeatedly; optional dedupe is implementer freedom, but “inspectable” is mandatory).
* If a canonical already exists for the decision anchor and the new payload differs without supersedes linkage → it’s **quarantined** (see #7).

---

## 7) PATH — P5 Corrections path (supersedes chain + current vs historical semantics)

### What this path exists to guarantee

You can correct audit truth **without overwriting history**, and you can query deterministically for either:

* **Historical truth** (“show me everything that was recorded”), or
* **Current truth** (“show me the latest canonical version per decision anchor”).

This is explicitly pinned in the platform: *DLA is append-only; corrections happen via a supersedes chain, not overwrites; idempotent ingest; quarantine on ambiguity.*

### The correction mechanism (boundary rule)

A “second record for the same decision_id but different payload” is only canonical if it includes:

* `supersedes_audit_record_id` pointing to an existing canonical record it replaces.

If the supersedes link is missing/invalid:

* route to quarantine with a supersedes-related reason.

### Scope safety (drift killer)

Supersession **must not cross ContextPins** (prevents cross-run overwrites):

* supersedes target must be within the same run/world scope.

### Path sequence (external)

```
(Existing canonical record exists for decision_id)
DF emits corrected DecisionResponse with supersedes_audit_record_id
→ IG → EB → DLA consumes
→ DLA appends new canonical AuditDecisionRecord (no overwrite)
→ DLA updates “current view” pointer; “historical view” keeps both
```

Pinned semantics: **current vs historical** views must exist conceptually; implementation can vary.

### What “current” and “historical” mean (platform-level semantics)

* **Historical view:** returns all canonical records (including superseded) in append-only order.
* **Current view:** returns the latest canonical record per `decision_id`, following supersedes chains.

### Failure semantics (what happens if things go wrong)

* **Missing supersedes link** for a conflicting duplicate → quarantine.
* **Invalid supersedes link** (non-existent record, or ContextPins mismatch) → quarantine.
* **Infinite/abusive chains:** DLA may enforce a max chain length operationally (but must preserve append-only history).

---

## 8) PATH — P2 Closure path: ActionOutcome linked back to the decision lineage

### What this path exists to guarantee

DLA can answer: **“What did we intend to do?” vs “What actually happened?”**
Platform pins this explicitly:

* DF emits **ActionIntents** with deterministic `idempotency_key`.
* AL enforces effectively-once using `(ContextPins, idempotency_key)` and emits immutable **ActionOutcome** history; duplicates are byte-identical.
* DLA may ingest outcomes to close the loop (“intent vs executed”).

### Path sequence (outer network)

```
DF decision → DecisionResponse contains actions[] (incl idempotency_key)
→ IG → EB
AL executes intent(s) → emits ActionOutcome (immutable) → IG → EB
DLA consumes ActionOutcome → links it to the decision’s audit lineage
```

### The key join requirement (so DLA can link without lookups)

Because DLA is “recorder, not resolver,” it must link outcomes **using only what is carried in the traffic**.

So, production expectation for ActionOutcome events (at the semantic level) is that they carry:

* **ContextPins**, and
* the **same `idempotency_key`** (and action_type), and
* enough decision correlation (decision_id / event_id / request_id) to anchor to the audit lineage.

### Out-of-order reality (production readiness)

EB ordering is only guaranteed **within a partition**, so DLA must tolerate:

* Outcome arrives **before** the canonical decision audit record is written, or
* Outcome arrives with missing correlation.

**Pinned outer behavior expectation:**

* DLA must not silently drop outcomes; it must either:

  * hold/link later (if linkable), or
  * quarantine as “orphan/unlinkable outcome evidence” (same philosophy as audit completeness).
    (The platform pins the quarantine posture; we extend it here as designer authority for outcomes.)

### Failure semantics

* Duplicate ActionOutcomes (re-emits) must not create duplicate outcome links in the audit lineage (idempotent linking). This is consistent with AL immutability + DLA idempotency posture.

---

## 9) JOIN — Case Workbench → DLA (read evidence by-ref)

### What this join *is*

A **read-by-reference** evidence join:

* Case Workbench reads **immutable audit evidence** from `dla/audit/...` (object store), optionally using `audit_index` for lookup.

This is pinned: “Case work consumes evidence by reference and builds an immutable case story.”

### Inputs to this join (how Case Workbench finds the evidence)

Production-ready options (all compatible with your pins):

1. **Evidence refs / pointers** provided to the Case Workbench from DF/AL/DLA pointer mechanisms (e.g., audit-pointer events).
2. **Deterministic query** against DLA using keys like `(ContextPins, decision_id/event_id)` + time windows; no scanning.

### What must be true about DLA for this join to work

* DLA must expose a way to fetch:

  * the **current** canonical audit record for a decision, and
  * the **historical** record set if an investigator needs to see corrections.
* DLA must preserve **by-ref privacy posture** (case tooling shouldn’t rely on embedded raw payloads).

### Failure semantics (what Case Workbench must tolerate)

* **Eventual availability**: case system may be triggered before the audit record is written; it must handle “evidence pending” and later resolve via pointer/query (no guesswork). This follows the platform’s distributed at-least-once reality.
* **Quarantine visibility**: if only a quarantine record exists, the case system may show “audit incomplete” as part of the case context (still evidence, but flagged).

---

## 10) PATH — P6 Case investigation path (audit evidence → timeline)

### What this path exists to guarantee

Humans can build an **immutable, reviewable story** of what happened, using platform evidence, without confusing “system evidence” with “ground truth labels.”

### Path sequence (outer network)

```
(Triggers arrive) DF/AL/DLA pointers
→ Case Workbench creates/updates case object
→ Case Workbench attaches DLA audit record refs into an append-only case timeline
→ Investigators review: decision, provenance, degrade posture, actions, outcomes (when present)
```

Pinned:

* “Case Mgmt / Workbench maintains case object + append-only case timeline.”
* “RTDL outputs are evidence, not ground truth; DLA is the canonical flight recorder for evidence.”

### What the case timeline must be able to include (evidence categories)

At minimum, the timeline can reference:

* **Decision evidence**: AuditDecisionRecord ref (current + historical when needed).
* **Action evidence**: ActionIntents (from decision provenance) and ActionOutcomes (when ingested/linked).
* **Posture evidence**: degrade mode/mask used and whether any fail-closed fallback happened.

### Failure semantics (production reality)

* If outcomes aren’t linked yet, timeline shows **intent without outcome** until the outcome evidence arrives (no backfilling by mutation; the timeline is append-only).
* If a decision audit is quarantined, timeline can still include the quarantine ref as “evidence of missing provenance” (and ops can remediate via loop #6).

---

If you want the next step after #6–#10, the natural continuation is **#11–#12** (Label Store join + the human-action loop), because it completes the “evidence → adjudication → truth” lifecycle that your blueprint explicitly pins.

---

Absolutely — here are **#11–#15 expanded** (still treating **DLA as opaque**: we define *boundary expectations*, *what crosses*, *what must hold*, and *what failure means*).

---

## 11) PATH — P7 Human truth path (case outcome → Label Store assertions)

### What this path exists to guarantee

The platform cleanly separates:

* **RTDL outputs = evidence** (decisions / intents / outcomes + provenance, recorded in DLA),
* **Ground truth = labels**, and labels become truth **only when written to Label Store** as an append-only timeline with **as-of** semantics (effective vs observed time).

### External sequence (opaque DLA)

```
DF/AL/DLA pointers (evidence refs)
  → Case Workbench builds immutable case timeline (by-ref evidence)
      → Investigator/external adjudication produces LabelAssertion(s)
          → Label Store appends to label timeline (truth)
```

This is explicitly pinned as the “Case + labels (human truth loop).”

### What must be true about the bridge (to avoid drift)

**A) Case consumes evidence by reference (no payload copying).**
Case timeline should carry *refs* to:

* DLA audit record(s),
* EB coordinates / event_id(s),
* action ids / idempotency keys (when relevant),
  not big duplicated payload bodies.

**B) LabelAssertions must carry the minimum label truth fields.**
Pinned minimum fields for every assertion:

* subject (event/entity/flow),
* value (+ optional confidence),
* provenance (who/what process),
* **effective_time** (when true in the world),
* **observed_time** (when learned).

**C) Corrections are new assertions; history remains.**
Label truth evolves append-only; no destructive updates.

### Failure semantics (production reality)

* If evidence is incomplete (e.g., DLA record quarantined), Case can still proceed but should be able to attach the quarantine ref as “audit incomplete evidence.” (This preserves the “never hide failures” posture.)
* If Label Store write fails, **no label becomes truth**; the assertion remains only a case artifact until persisted in Label Store.

---

## 12) LOOP — L2 Human-in-the-loop action loop (evidence → action → outcome → evidence)

### What this loop exists to guarantee

Manual interventions produce side effects **the exact same way** automated actions do, so they’re:

* dedupe-safe,
* fully auditable,
* and outcomes are immutable history.

### The loop (end-to-end)

```
(1) Evidence appears:
    DF decisions / AL outcomes / DLA audit records → pointers → Case Workbench
(2) Human decides to act:
    Case Workbench submits a Manual ActionIntent (not “do it directly”)
(3) Action executes through normal rails:
    Manual ActionIntent → (IG → EB traffic) → AL executes (effectively-once) → ActionOutcome → (IG → EB)
(4) Evidence closes the loop:
    DLA consumes ActionOutcome → links to decision lineage → new audit evidence pointer
(5) Case timeline updates:
    Case Workbench attaches new outcome evidence by-ref; may later create LabelAssertions
```

This is pinned explicitly: “manual interventions must go through the same action pathway as automated ones,” and RTDL outputs remain evidence, not truth.

### Boundary expectations (what must cross so the loop can join cleanly)

Because we don’t allow DLA (or Case) to “resolve” by querying hidden state, the join must be carried in identifiers:

* Manual ActionIntent must include ContextPins + a deterministic `idempotency_key` and bind back to decision/event identifiers.
* AL enforces effectively-once with `(ContextPins, idempotency_key)` and outcomes are immutable / re-emits byte-identical.
* DLA can link outcome evidence using only those carried ids/refs (it’s a recorder, not a resolver).

### Failure semantics

* Duplicate human submissions (double-click, retries) must not cause double execution — AL’s idempotency recipe prevents it; DLA must also be idempotent when recording the same outcome evidence repeatedly.
* If an outcome arrives before the associated audit decision record is visible, DLA must still preserve the outcome evidence and link later (or quarantine as “orphan/unlinkable outcome evidence” — same philosophy as audit completeness).

---

## 13) JOIN — DLA → Observability pipeline (lag, failures, quarantine rates, SLOs)

### What this join is

DLA is an **always-on consumer/writer** and must emit OTLP telemetry (traces/metrics/logs) so the platform can answer:

1. what happened/why,
2. are we healthy enough to act (degrade inputs),
3. what changed (governed ops).

### What DLA must emit (minimum production set)

**A) Metrics (automation / SLOs)**

* Golden signals: throughput, latency, error rate, saturation.
* Consumer specifics: **consumer lag per partition** + “watermark age” (how stale applied offsets are). (Pinned for EB consumers, including DLA.)
* Audit health specifics:

  * canonical write rate vs quarantine write rate,
  * quarantine reason distribution,
  * idempotent NO-OP rate (duplicate/replay pressure),
  * supersedes-chain anomalies (invalid/missing link counts),
  * object-store write latency/failures,
  * index DB write latency/failures (if used).

**B) Traces (end-to-end causality)**
Minimum chain: **IG admission span → DF decision span → AL execution span → DLA write span**, with trace propagation if present in the envelope.

**C) Logs (human debugging, by-ref safe)**
Only boundary decisions as structured facts; by-ref friendly; no raw payload dumps; no secrets. DLA’s key boundary decisions are:

* wrote canonical audit record (with ids/refs),
* quarantined audit record (reason + correlation),
* supersedes accepted/rejected (with refs),
* replay/reindex operations started/finished (if Run/Operate triggered).

---

## 14) JOIN — Run/Operate → DLA (retention / reindex / controlled replay orchestration)

### What this join is

Run/Operate is the platform’s **operational substrate**:

* it can start/stop/drain/backfill/retention-change,
* it persists by-ref artifacts/evidence,
* but it is **not** a domain truth source and must not introduce hidden nondeterminism.

So the Run/Operate→DLA join is: **lifecycle + governance-controlled ops commands** that affect DLA’s ability to ingest/replay/index, without changing the meaning of facts.

### What kinds of operational acts are “in-scope” (production-ready)

**A) Controlled drain / restart**

* Stop consuming, flush writes, persist checkpoints, resume deterministically. (Matches “at-least-once is real; lag is observable.”)

**B) Retention profile changes**

* EB retention and archive policy changes are outcome-affecting and must emit governance facts.

**C) Reindex / view rebuild**

* Rebuild *derived* surfaces (audit_index/search/materialized views) from canonical truth, without mutating canonical audit records.

**D) Declared replay/backfill operations**

* Any backfill that changes derived outputs must be explicit, scoped, auditable, and must not “time travel” offsets/watermarks.

### Governance requirement on this join (non-negotiable)

Any operational act that can affect outcomes or reproducibility must produce a durable governance fact (actor, scope, before/after refs, reason). Retention and backfills are explicitly called out.

---

## 15) PATH — P10 Replay/backfill path (EB replay → idempotent re-consume → reindex)

### What this path exists to guarantee

When time passes, retention expires, late facts arrive, or you need to recompute: the platform remains **reproducible and auditable**:

* Archive extends EB facts (same logical events),
* replay basis is always explicit,
* watermarks remain monotonic,
* backfills are declared and never silently overwrite primary truths.

### The path (two cases)

#### Case A: Normal replay / catch-up (DLA outage or consumer lag)

```
DLA resumes consumption from last checkpoint
→ consumes EB within retention (or archive beyond retention)
→ writes missing canonical/quarantine records (append-only)
→ idempotency ensures duplicates become NO-OP
→ updates/rebuilds audit_index as needed
```

This relies on: at-least-once is real; consumer lag exists and is observable; archive is the long-horizon extension of admitted facts.

#### Case B: Declared reindex/backfill (derived surfaces only)

```
Run/Operate declares backfill job with:
  scope + purpose + replay basis (offset ranges/checkpoints) + outputs
→ DLA (or a DLA-index job) rebuilds derived indexes/views from canonical audit truth
→ emits completion receipt + governance fact
```

Pinned rule: **audit indexes are backfillable (derived)**; primary truths are not silently mutated.

### Critical invariants (drift killers)

* **Replay basis must be explicit** (offset ranges/checkpoints; or time windows anchored to offsets).
* **Watermarks don’t lie**: applied offsets move monotonically; backfills don’t redefine what an offset meant.
* **No silent backfills**: everything that can change derived outputs must be declared and auditable.

### Failure semantics

* If replay basis is not provided (e.g., “rebuild everything”), the operation is **not valid** in production posture; it must be converted into an explicit scope/basis or rejected.
* If archive completeness for a declared window cannot be verified, offline/long-horizon replay must fail closed (do not pretend it’s complete).

---

If you want the clean continuation after #15, the next expansions naturally are **#16–#19** (the operational continuity loop + audit pointer topic), but I’ll stop here since you asked #11–#15.

---

Perfect — here are **#16–#20 expanded** (still treating **DLA as opaque**: we define the **outer joins/paths/loops**, what the rest of the platform can rely on, and what “failure” means).

---

## 16) LOOP — L4 Operational continuity loop

**“Restart/replay doesn’t corrupt truth”**

### What this loop exists to guarantee (production-ready meaning)

DLA is an **always-on consumer/writer**. In production, it *will* restart, lag, reprocess partitions, and occasionally replay from earlier offsets. The loop guarantees:

* **No lost audit truth** under crashes/restarts
* **No duplicate canonical audit truth** under at-least-once delivery
* **No silent mutation** (append-only record of what happened remains)
* **Deterministic recovery basis** (offset checkpoints / archive basis are explicit)   

### The loop (outer behavior)

```
DLA runs (consumes fp.bus.traffic.v1) → writes audit truth → persists checkpoint
↳ crash / deploy / restart happens
DLA restarts → resumes from last persisted checkpoint → re-consumes some events
↳ duplicates occur (expected) → DLA idempotency makes them NO-OP
DLA catches up → checkpoint advances again
```

### The two “must-pin” invariants that make this safe

1. **Checkpoint meaning is exclusive-next offset**
   Consumer progress is stored as “next offset to read/apply” (exclusive-next). That meaning is what makes replay deterministic platform-wide.

2. **Idempotency recipe is local and binding for DLA**
   DLA’s idempotent ingest key is **`(ContextPins, audit_record_id)`**; duplicates must be NO-OP.

### The production-grade crash window (the only one that matters)

To be safe, DLA must behave like this (outer expectation, not implementation detail):

* **Durable write first** (canonical/quarantine record is appended to `dla/audit/...`)
* **Checkpoint commit second** (so a crash replays, not loses)
* If crash happens between the two, replay causes duplicates — which are safely NO-OP due to idempotency.

### Retention/archive reality (continuity beyond EB retention)

If DLA is down long enough to exceed EB retention, continuity must still be possible via **archive**:

* Archive is the **long-horizon extension of admitted facts** (canonical envelopes preserved)
* Archive addressing is **by-ref and pinned** (no vague search)
* Replay/backfill must declare a **basis** (offset/time windows/checkpoints)

**Failure semantics:** if the declared replay basis cannot be satisfied (missing archive coverage), DLA (or the orchestrated replay job) must **fail closed** — never pretend completeness.

---

## 17) JOIN — Offline/Governance tools → DLA

**“Deterministic exports / slices”**

### What this join is (outer expectation)

A controlled way for non-hot-path consumers (governance, investigators, reporting, offline assembly) to obtain **deterministic subsets** of DLA truth **without scanning** and without turning DLA into a data lake.

This join sits naturally in the **Run/Operate + Obs/Gov planes**: it’s *read-only domain-wise*, but it’s still a governed action.

### What crosses the join (conceptual)

**ExportRequest** (from a tool/job) must be pinned by:

* **ContextPins scope** (always)
* **time window** (domain time, not ingestion time)
* optional filters (degrade mode, decision outcome, entity keys, etc.)
* **view selector**: `historical` vs `current` (supersedes-following)

DLA returns:

* **ExportReceipt** with by-ref pointers to export artifacts + digests (and the exact selection basis echoed back).

Everything stays consistent with “by-ref is default truth transport” and “no scan latest and hope.”

### The deterministic rule (non-negotiable)

For the same `(pins, window, filters, view)`, export selection must be deterministic.
If the retention horizon changes what is available, that must be explicit (the receipt must say what basis was actually satisfied).

### Where exports land (outer posture)

Not pinned to a specific prefix, but must be:

* **by-ref addressable** (object store style)
* **digest verifiable**
* **immutable once published**

(Consistent with your general artifact posture in the reference stack.)

### Failure semantics

* If a request implies “scan all history” → **invalid** in production posture (must be translated to explicit pins + basis).
* If export requires beyond retention and archive is not verifiably complete → **fail closed** (or produce an explicit partial receipt — but never silently partial).

---

## 18) OPTIONAL JOIN — DLA → `fp.bus.audit.v1`

**“Audit pointer events”**

### What this join is

A convenience distribution plane: instead of consumers polling `dla/audit/...`, DLA can emit **pointer events** whenever it appends:

* a canonical audit record, and/or
* a quarantine record.

This is explicitly allowed in your deployment wiring: DLA may emit optional pointer events to `fp.bus.audit.v1`.

### What crosses (must stay minimal and by-ref)

A pointer event must carry:

* correlation: ContextPins + decision_id/event_id (as available)
* record identity: `audit_record_id` (or quarantine_record_id)
* **object ref(s)** to the immutable record in `dla/audit/...` (+ optional digest)
* optional: EB position ref that triggered the write (for provenance)

And **must not** embed raw payload bodies (same privacy/by-ref posture as the platform).

### The key safety property (so this never breaks platform law)

Pointer events are **derivative**: they *cannot introduce new truth*.
They only point to immutable truth already written (or being made durable). That’s why they’re allowed as an optional join without reopening the IG trust boundary debate for decisionable traffic.

### Failure semantics

* If pointer publish fails, **audit truth still exists** in object store; consumers fall back to query/index/poll.
* Pointer duplicates are acceptable; consumers must dedupe by `(ContextPins, audit_record_id)` or pointer event_id.

---

## 19) OPTIONAL PATH — P8 Pointer distribution path

**“Subscribers react without polling”**

### The path

```
DLA appends record → (optional) emits pointer event on fp.bus.audit.v1
→ subscribers consume pointer
   → fetch immutable audit record by ref
   → update their own derived state (cases, dashboards, governance views)
```

### Typical subscribers (production-realistic)

* **Case Workbench backend**: create/update case timelines when “new decision audit” arrives (without polling).
* **Governance/Obs tooling**: drive “audit join view” pipelines and compliance dashboards.
* **Offline assembly triggers**: kick off governed exports or dataset manifests (still under Run/Operate governance).

### The “emit-after-durable” rule (the only rule that matters here)

For this path to be clean:

* Pointer should be emitted **after** the referenced object record is durable (or consumers must handle short “eventual” gaps with retry).
  This preserves the by-ref discipline: pointers don’t lie.

### Failure semantics

* If subscriber can’t fetch the referenced object, it retries (bounded), and may emit an ops alert; it must not “invent” missing evidence.
* If pointers are missed (subscriber downtime), subscriber can recover by replaying `fp.bus.audit.v1` or falling back to deterministic queries against `audit_index` / object store within a pinned basis.

---

## 20) OPTIONAL JOIN — IG receipts/quarantine refs → DLA

**“Evidence augmentation (by-ref only)”**

### What this join is

DLA may enrich its audit truth with **IG’s admission evidence**, because IG is authoritative for:

* ADMIT / DUPLICATE / QUARANTINE outcomes
* receipts and evidence pointers.

Deployment wiring explicitly allows DLA to read:

* `ig/receipts/...` and `ig/quarantine/...` refs (object store), as optional inputs.

### Standing truth to prevent drift (important)

**DLA must not scan IG storage.**
It may only use IG evidence in one of these deterministic ways:

1. the DF/AL event payload includes an explicit `ig_receipt_ref` / `receipt_id`, or
2. the receipt is derivable by a stable, deterministic mapping from a known receipt_id → object key, or
3. IG emits a pointer event (to `fp.bus.audit.v1`) that contains the receipt/quarantine object ref.

### What DLA gains from this evidence (why it’s worth having)

* **Stronger provenance chain**: “this decision was based on an admitted fact at EB coords X, and IG produced receipt Y under policy rev Z.”
* **Duplicate clarity**: if the stimulus was a duplicate admission, the receipt points to the original EB coords (audit story remains clean).
* **Quarantine-forensics**: if something relevant was quarantined upstream, DLA can link to the quarantine evidence pointer (without treating it as decisionable input).

### Failure semantics

* Missing IG evidence must **not** block canonical audit truth *unless* your completeness policy says it’s required.
  My designer stance for v0: **IG receipt refs are “nice-to-have” evidence**, not mandatory for canonical audit (because EB coords already provide replay basis), but if a receipt ref *is present* and not resolvable, DLA should quarantine that audit attempt as “broken evidence pointer” (don’t silently drop). This aligns with “quarantine is first-class; drop on floor is disallowed.”

---

If you want to keep going in the same expansion cadence, the next natural chunk is **#21–#23** (evidence augmentation path + engine audit_evidence join + forensics path), because they complete the “audit evidence beyond the hot path” story without touching model-learning loops yet.

---

Got it — here are **#21–#25 expanded** (still treating **DLA as opaque**: only the **outer joins/paths/loops**, what crosses, and what “failure” means).

---

## 21) OPTIONAL PATH — P3 Evidence augmentation path

**IG receipts/quarantine refs attached to audit lineage**

### What this path is for

It strengthens the audit chain by letting a canonical audit record say not just “this stimulus was at EB coords X”, but also “IG admitted it under policy rev Y, schema version Z, with decision ADMIT/DUP/QUAR and evidence pointers.” This makes later investigations and schema evolution operable.

### Outer flow (one clean, production-safe sequence)

```
Producer event → IG validates (envelope + schema + policy + joinability)
  → IG emits ingestion_receipt (and stores evidence by-ref)
  → IG appends admitted fact to EB (or emits DUPLICATE receipt; or QUARANTINE receipt)

DF consumes admitted facts → emits DecisionResponse (as traffic via IG→EB)
AL consumes intents → emits ActionOutcome (as traffic via IG→EB)

DLA consumes DecisionResponse/Outcome from EB → writes canonical audit record
  + (optional) attaches IG receipt refs for:
      - stimulus event admission
      - DecisionResponse admission
      - ActionOutcome admission
```

IG’s receipt content is pinned to include (at minimum) schema facts + policy revision + decision (ADMIT|DUPLICATE|QUARANTINE) + evidence pointers.

### What must cross (conceptual payload, not a spec)

**A) Receipt reference mechanism (by-ref, no scanning):**
DLA may only attach IG receipts if it has a **deterministic handle**:

* `receipt_id`, and/or
* `receipt_ref` (object locator), and/or
* an IG “receipt lookup” keyed by `(event_id, ContextPins)` (explicit query, not storage scan).

**B) What the receipt itself must capture (platform pin):**
At minimum:

* `event_type`, `schema_version`, validation outcome, and acceptance `policy_rev` (so schema evolution is explainable).
  And the “minimum policy facts” posture for IG receipts includes: `receipt_id`, principals, policy rev, event identity, ContextPins if joinable, decision=ADMIT|DUP|QUAR, reason codes, and evidence refs to EB coords or quarantine record ref.

### Designer v0 stance (to prevent drift)

* **Receipt linkage is “evidence augmentation”, not required for canonical audit truth.**
  Canonical audit truth can be produced from EB replay coords + DF provenance alone (J12), but if a receipt ref is provided, DLA should keep it.
* **If a receipt ref is present but broken/unresolvable → quarantine (don’t silently drop the claim).**
  This matches “by-ref + digest posture” and “drop on floor is disallowed.”

---

## 22) OPTIONAL JOIN — Engine `audit_evidence` → DLA

**Forensics-only, by locator + PASS**

### What this join is for

Engine `audit_evidence` (RNG trace logs, draw logs, selection logs, etc.) is *not traffic*; it exists to support forensic replay and governance-grade reconstruction. DLA is an allowed consumer plane for that evidence — but only **by-ref** and only **with PASS proofs**, never by discovery/scanning.

### Hard boundary rules (pinned)

* Engine outputs are role-separated: **only `business_traffic` enters the hot path**; `audit_evidence` is **not traffic**.
* Engine surfaces (including audit evidence) are consumed **by reference**; nothing downstream “copies them into a new truth plane.”
* **No PASS → no read** applies platform-wide for engine material:
  an artifact is admissible only when explicitly referenced **and** the required PASS evidence exists for that exact pinned scope (and **never via scanning**).
* Engine outputs are immutable once written for a pinned identity (identity = partition tokens; `run_id` partitions logs/events but doesn’t mutate sealed-world outputs).

### What crosses the join (minimum, portable evidence package)

To attach engine audit evidence into the DLA universe, the platform needs:

1. an **EngineOutputLocator** for the artifact (output_id + fully resolved path + identity pins + optional content_digest).
2. **GateReceipt(s)** proving PASS for the relevant scope (segment gate and, when required, instance proof).
3. (optionally) pointers to the underlying on-disk gate artifacts/digests (gate receipts support this).
4. the verification method is gate-specific (engine_gates.map.yaml defines how to verify).

### How DLA treats it (opaque behavior, externally visible)

* DLA **stores references + proofs**, not the full evidence content.
* If the locator/proofs are missing, DLA must not pretend the evidence is valid. It may:

  * omit the attachment (if DLA is adding it as optional enrichment), or
  * quarantine the audit record (if the DecisionResponse explicitly claims that evidence as part of its must-record set).

**Standing v0 pin (designer choice):**
DLA may attach engine audit evidence at **run/world scope**, not per-decision granularity (because the evidence typically proves generation lineage and RNG realization, not a single decision). Decisions can join to it via ContextPins.

---

## 23) OPTIONAL PATH — P9 Forensics path

**Engine evidence refs used in investigations**

### What this path is for

It’s the “deep replay” route: investigators/governance can reconstruct *why a synthetic world behaved as it did* and validate that the evidence was produced under a gated, immutable engine identity — without letting truth products leak into the hot path.

### Outer flow (production narrative)

```
Case trigger → Case Workbench pulls DLA audit record refs (by-ref)
  → audit record provides ContextPins + decision provenance + (optional) engine_evidence_refset

Investigator requests forensic package:
  → fetch EngineOutputLocator(s) from DLA-attached evidence set
  → verify PASS using GateReceipt(s) + gate map rules
  → read engine audit_evidence artifacts by-ref (no scanning)
  → (optional) run a replay/backfill job using explicit EB/archive basis + these evidence refs
```

Key pins that make it safe:

* Engine evidence is only admissible if referenced + PASS proven; no scanning/discovery.
* Archive is a continuation of EB for long-horizon replay; any replay must record its basis.
* Gate verification is gate-specific (don’t assume one digest law).

### Failure semantics

* **Missing PASS / invalid digest / mismatched scope → inadmissible evidence** (fail closed for forensic claims).
* **Evidence refs exist but can’t be resolved within retention/availability windows** → investigation can proceed with “audit record only,” but the missing evidence must be explicit (not silently ignored). This aligns with “drop on the floor is disallowed.”

---

## 24) LOOP — L3 Learning/model rollout loop

**(evidence + labels) → offline → model factory → registry → new decisions → new audit provenance**

### What this loop guarantees

Learning can influence production **only** through the Registry, and every change is explainable later because DF records the resolved bundle + compatibility basis in decision provenance, which DLA then preserves.

### Full loop (outer network)

```
A) Evidence + truth inputs accumulate:
   EB/admitted facts (+ archive beyond retention) + Label Store as-of truth

B) Offline Shadow rebuild:
   Offline Shadow reads EB/archive + Label Store (as-of)
   → produces DatasetManifests that pin replay basis + as-of boundaries + feature versions

C) Model Factory:
   Model Factory consumes DatasetManifests → trains/evals
   → produces bundle artifacts + digests + eval evidence

D) Registry lifecycle:
   Registry promotes/activates bundles via governed change (compatibility-aware; fail closed if incompatible)

E) Production decisioning changes:
   DF resolves ACTIVE bundle deterministically + records bundle ref + feature versions + degrade posture
   → emits DecisionResponse

F) Audit closes the accountability loop:
   DLA records that provenance, so later you can answer:
   “Which bundle + which feature versions + which degrade posture produced this decision?”
```

Pins that matter here:

* Offline Shadow must pin **replay basis** and **as-of boundaries**; archive is EB’s long-horizon extension; backfills are explicit/auditable; watermarks are monotonic.
* Registry is compatibility-aware and promotion requires evidence; DF must record the resolved bundle and compatibility basis in provenance.
* Deployment wiring confirms the operational path: `ofs/...` manifests → `mf/...` evidence → registry activation → DF consumption.

### DLA’s specific role in the loop (as an opaque vertex)

DLA is not a training input source-of-truth — EB/archive + Label Store + DatasetManifests are. DLA’s job is to preserve the **decision-side provenance** so learning/rollouts are auditable and debuggable after the fact.

### Failure semantics

* If a bundle lacks compatibility metadata/evidence → Registry promotion is invalid (fail closed).
* If DF cannot resolve a compatible bundle under current degrade/feature versions → fail closed or defined safe fallback, and DLA must be able to record that posture in audit provenance.

---

## 25) LOOP — L5 Degrade loop

**(audit makes posture visible) → ops/governance adjusts → posture changes → decisions change**

### What this loop guarantees

The platform stays safe under partial outages and lag by ensuring:

* Observability produces signals,
* Degrade Ladder turns signals into an explicit constraints mask,
* DF obeys constraints,
* and DLA records which constraints were in force — so behavior never changes “by stealth.”

### Loop (outer behavior)

```
Obs pipeline detects lag/errors/corridor breaches
→ Degrade Ladder computes current posture (mode + mask) (optionally emits control facts)
→ DF consumes posture + obeys constraints in decisioning
→ DF emits DecisionResponse carrying degrade posture in provenance
→ DLA records posture used in canonical audit truth
→ Governance reviews posture + outcomes + policy revs
→ Adjust thresholds/policies → Degrade Ladder posture changes → decisions change
```

Pins:

* DL is an always-on unit that computes degrade posture from obs signals; posture may be emitted as explicit control facts.
* J12 requires degrade posture be present in the canonical audit record; missing provenance triggers quarantine rather than half-truth.
* Observability/Governance can only influence behavior through explicit control surfaces (degrade, promotions/rollbacks); no silent mutation.

### Failure semantics

* If DF emits a decision without degrade posture (or with an unclassifiable posture), DLA treats it as incomplete provenance → **quarantine** (because degrade posture is part of the must-record set).
* If degrade policy revisions change, those changes must remain visible via governance facts/policy revs (so “what rules were in force?” is answerable).

---

If you want to keep going in the same structured way, the next natural move is to take **#21–#25** and extract the **exact boundary “must-carry” fields** per join (still not a spec) so DF/AL/IG can’t accidentally under-emit provenance and force quarantine storms.

---

Yes — the **environment ladder** puts some *very specific constraints* on how all those DLA joins/paths/loops must behave (and what is allowed to vary).

## The core ladder rule applied to DLA

Across **local / dev / prod**, you must have the **same platform graph + the same rails/join semantics**; environments differ only in the **operational envelope** (scale, retention+archive, security strictness, reliability posture, observability depth), and “promotion” is **profile selection**, not code forks.

That immediately implies for DLA:

* **All the joins/paths/loops we mapped are “real” in every environment** (even if local collapses processes).
* Local must still obey the rails; otherwise you’re testing a *different* platform.

---

## What must be identical for DLA joins/paths/loops in every environment

### 1) Trust-boundary and plane meaning must not change

* DLA is an **always-on EB consumer/writer** in the platform meaning (even if local runs it as a single process).
* DLA consumes from the **admitted fact stream** and produces an **append-only flight recorder**; it does not become a “direct-write sink” that bypasses IG/EB in local.
* “Append-only + supersedes” and “quarantine is first-class” must mean the same thing everywhere.

### 2) Replay determinism semantics are the same everywhere

* **Offsets/watermarks are monotonic** and remain the universal progress token; backfills never “time travel.”
* Any replay/backfill story that affects derived state must be **explicit, scoped, auditable**, and record an explicit **replay basis**.

This applies directly to:

* L4 operational continuity loop (#16),
* P10 replay/backfill path (#15),
* any “reindex audit_index” action (derived) vs “mutate audit truth” (forbidden).

### 3) Config must not fork semantics

* Environments differ by **profiles** (wiring + policy strictness), not by “if prod do X else do Y” code behavior.
* Outcome-affecting policy configs are **versioned artifacts** and their revision should be observable (and ideally recorded in provenance/receipts).

This matters for DLA because otherwise you’ll get “local accepts incomplete provenance” while prod quarantines — which is exactly the “three platforms” failure mode.

---

## What is allowed to differ across environments for those joins/paths/loops

### 1) Retention + archive (big one)

* Retention length can differ (local short, dev medium, prod longer + archive), but **replay semantics don’t change**.
* Archive may be **disabled in local** for speed, but the design must still treat archive as the **long-horizon continuation of EB** (same envelope semantics, same event identity) so that dev/prod investigations and training horizons work.

**Practical implication for #15–#17:**
Local can test “replay within retention,” dev should test “replay across restarts + medium retention,” and prod must support “replay beyond retention via archive” with explicit basis.

### 2) Security strictness (who can read quarantine / who can export)

* Local can be permissive, but the **mechanism** must exist and semantics must be the same: quarantine access, export permissions, action permissions, label writes.
* Dev must be “real enough” to catch unauthorized producers / missing evidence / incompatible changes (so the DLA quarantine loop is exercised properly).
* Prod is hardened: strong auth and strict change control, and “prod never relies on human memory.”

This directly affects:

* #17 exports/slices (governed),
* #20–#23 evidence augmentation (receipt/evidence access),
* #11–#12 human loops (manual actions + labels).

### 3) Reliability posture + observability depth

* Local can rely on inspect-by-hand, but must still emit OTLP and preserve the same correlation keys/telemetry meaning.
* Prod must have real dashboards/alerts and corridor checks because degrade depends on them.

This matters for #13 and also for L5 degrade loop (#25): if local doesn’t run the observability baseline, you won’t exercise the degrade→DF→DLA recording chain.

### 4) Implementation of query/index

* `audit_index` can be thin/temporary in local, more realistic in dev, hardened in prod — **as long as it’s always derivative** and rebuildable from immutable truth.

---

## Environment-ladder gotchas specific to DLA (places people accidentally create “three platforms”)

1. **Local bypasses IG/EB** (“just write audit directly”)
   This breaks the pinned trust-boundary graph. Local must still route decision/outcome facts via the same path, even if everything runs on one machine.

2. **Local “forgives” missing provenance instead of quarantining**
   That’s a semantics fork. If you want leniency, it must be via a **policy profile revision** that is versioned and visible — not an ad-hoc debug behavior.

3. **Backfill mutates “truth” in one environment**
   Only **derived** things can be backfilled (audit indexes yes; canonical audit truth no).

4. **Archive treated as a different dataset type**
   Pinned: archive is a continuation of EB admitted facts, preserving identity and envelope semantics.

---

## A clean ladder mapping for DLA (one paragraph per env)

* **Local:** you can collapse units, shorten retention, and use a lightweight stack — but DLA must still behave like the same always-on EB consumer/writer, using the same append-only + quarantine + idempotency semantics and emitting OTLP telemetry.
* **Dev:** run the graph as in prod and deliberately test schema evolution, quarantine storms, corrections/supersedes, replay/reindex, and controlled backfills under more realistic auth/policy.
* **Prod:** hardened authz, long retention + archive, SLOs/alerts, governed change control; every outcome-affecting change is an auditable fact, and DLA’s role as the flight recorder becomes a compliance-grade guarantee.

If you want, the next high-leverage thing to pin (still brainstorming, not spec) is: **which DLA behaviors are “policy-profile knobs”** (e.g., “receipt refs required vs optional”, “which provenance fields are mandatory”) so local/dev/prod stay *semantically aligned* while still letting dev/prod be stricter.

---

Yes — at the **opaque vertex** stage, you mainly want (a) the **profile knobs** you’ll expose for DLA, and (b) the **deployment truths** that must stay invariant across the environment ladder so you don’t accidentally create “three different platforms.”

## 1) What is NOT a knob (must stay identical across local/dev/prod)

These are the “no drift” invariants for DLA:

* **Same graph + trust boundaries:** DLA remains an **EB consumer/writer**; it doesn’t become a direct-write sink in local.
* **Replay semantics are EB coordinates:** progress is `(stream, partition, offset)` with **exclusive-next** checkpoint meaning. 
* **At-least-once is assumed:** DLA must be **idempotent under replay/duplicates**. 
* **Append-only + supersedes:** canonical audit truth is immutable; corrections are new records only. 
* **Quarantine is first-class:** no silent drops; rejections produce quarantine outcomes with evidence pointers.
* **Degrade is explicit + recorded:** degrade mode/mask used must be part of audit provenance (or it’s incomplete). 
* **Promotion is profile selection, not code forks:** same binaries/contracts; different environment profile.

These are the rails you should *not* make “optional” as you step inside the vertex.

---

## 2) The profile split you should maintain

Your deployment notes pin a crucial distinction:

### Wiring config (non-semantic)

Endpoints/ports, resource limits, timeouts, thread counts, etc. These can vary freely by environment.

### Policy config (outcome-affecting)

Anything that changes “what is accepted / recorded / exported / considered complete” must be:

* **versioned**, **auditable**, **promoted like code**, and
* components should **report which policy revision** they are using.

That framing is your “knobs boundary.”

---

## 3) DLA environment profile knobs

### A) DLA policy knobs (outcome-affecting, versioned + auditable)

These are the ones worth naming now so the inner-network later has clear “switch points”:

1. **Audit completeness policy revision**
   Defines what fields/provenance are required for a record to be canonical vs quarantined. Recommendation: keep this **the same across local/dev/prod** (drift killer), and evolve it via promoted revisions.

2. **Evidence augmentation policy (IG receipts)**
   Whether IG receipts/quarantine refs are:

* optional enrichment (v0-friendly), or
* required for canonical audit (stricter).
  If you vary this by env, do it only as a promoted policy rev (not a code path).

3. **Supersedes/corrections policy**
   Rules for accepting a correction (must carry supersedes link), max chain length guardrails, and what counts as “conflict → quarantine.” This is typically **constant across env** (it’s audit meaning).

4. **Pointer emission policy** (`fp.bus.audit.v1`)
   Enable/disable emitting audit-pointer events. This can vary by env (it’s a convenience join), as long as the canonical truth remains `dla/audit/...`.

5. **Export policy (governed slices)**
   Who can request deterministic exports, what scopes are allowed, and whether export operations must emit governance facts. This is **very likely stricter in dev/prod** than local.

6. **Retention/backfill policy for audit artifacts**
   Retention windows, archive use, and which backfills are allowed (derived indexes yes; canonical truth no). This is an environment knob (short local, longer prod), but must preserve the same replay/“basis is explicit” semantics.

7. **Access policy (audit + quarantine visibility)**
   Quarantine access, export permissions, investigator visibility. This can vary by env in strictness, but the mechanism must exist everywhere.

### B) DLA wiring knobs (non-semantic, freely per environment)

These are operational and should live in the wiring profile:

* EB connection + consumer group id, partition concurrency, batch size, poll/flush intervals.
* Object store bucket/prefix (canonical: `dla/audit/...`), write parallelism, retry/backoff timeouts.
* Optional DB DSN for `audit_index`, pool sizes, migrations toggles.
* OTLP endpoint, sampling rates, log verbosity.

---

## 4) Deployment “what to keep in mind” before you step inside the vertex

### DLA’s deployment unit shape (pinned)

DLA is an **always-on consumer/writer** in the production shape; local can collapse processes, but the **role stays the same**.

### DLA’s external reads/writes (pinned wiring map)

* **Reads:** decisions/intents/outcomes from `fp.bus.traffic.v1`; optionally IG receipt/quarantine objects.
* **Writes:** immutable audit records to `dla/audit/...`; optional `audit_index` DB; optional pointers to `fp.bus.audit.v1`.

### What must be durable for continuity

* **Canonical audit truth** in `dla/audit/...` is the system-of-record.
* DLA must treat EB offsets with **exclusive-next** meaning and persist checkpoints such that restart/replay is safe (paired with idempotency).
* `audit_index` is rebuildable/derivative (nice to have for query), not truth.

### Observability baseline you should expect to be “real” even locally

You’ve pinned OTLP everywhere + consumer lag/watermark visibility. For DLA, the “must exist” signals are: consumer lag, canonical write rate, quarantine rate by reason, and error rates to object store / db.

### Promotion reality (what will bite you later if you don’t design for it now)

* DLA should be able to say: **code artifact X + policy rev Y + wiring profile Z** explains its behavior (no “prod fork”).
* Policy/config revisions are first-class and should appear in provenance/receipts/logging (so “what rules were in force?” is answerable).

### The one “golden flow” deployment test that anchors DLA early

Your integration lane explicitly includes DLA in the end-to-end flow (SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA). When you go inside the vertex, keep that as the minimal acceptance path.

---

If you want one clean takeaway before we “illuminate” DLA: **decide which of the policy knobs above you want to be invariant across env (recommended: completeness/corrections), and which are allowed to vary (retention, access strictness, pointer emission, export permissions).** That will prevent your inner-network design from accidentally baking environment differences into behavior.

---

## USER: PAUSE FOR REFLECTION

Yep — let’s do a **drift-check checkpoint** on the **outer network** for DLA (still treating DLA as opaque), and lock what is *platform-law* vs what is *optional/knob* before we step inside.

---

## Outer network checkpoint for DLA

### 1) DLA’s fixed position in the platform graph

**DLA is an always-on consumer/writer** whose primary input plane is **`fp.bus.traffic.v1`** and whose truth output is **immutable audit records under `dla/audit/...`**, with an optional derived `audit_index` and optional pointer events to `fp.bus.audit.v1`.

This placement is consistent with the platform primitives:

* **Canonical Event Envelope is the bus boundary** (required fields stay stable; payload is versioned behind it).
* **ContextPins** are the join pins for run/world joinability; seed is separate and only required where RNG/run-scoped.
* **Idempotency is end-to-end** and DLA’s local key recipe is explicitly `(ContextPins, audit_record_id)` in the platform map.

### 2) Authority boundaries (what DLA must never “take over”)

The platform’s “choke point” mental model is explicit: **IG controls facts**, **AL controls side effects**, **Registry controls deployable logic changes**. DLA is the recorder that makes those things explainable later, not a validator/executor/decider.

So drift-avoidance rule:

* DLA **does not** validate admission policy (IG does), **does not** compute features/graph (OFP/IEG do), **does not** execute (AL does), **does not** resolve bundles (Registry does). DLA only records what those components claim they used/did (plus completeness/quarantine enforcement).

---

## The outer joins we’ve exposed (and whether they’re mandatory)

### Mandatory joins (production-ready minimum)

1. **EB `fp.bus.traffic.v1` → DLA** (consume decision/action lineage events)
2. **DLA → `object://dla/audit/...`** (immutable canonical + quarantine records)
3. **DLA → optional `db://audit_index`** (derived query surface; rebuildable)
4. **Case Workbench → `dla/audit/...` by-ref** (investigation evidence consumption)
5. **DLA → OTLP/observability** (because it’s always-on + consumer-lag matters)

### Optional joins (allowed, but must not change semantics)

6. **DLA → `fp.bus.audit.v1` pointer events** (distribution convenience)
7. **IG receipts/quarantine refs → DLA (by-ref)** (evidence augmentation)
8. **Engine `audit_evidence` → DLA (by locator + PASS only)** (forensics) — and never treated as traffic.

Drift warning: optional joins can exist, but **they must never become alternative sources of truth** that bypass the “facts plane” (IG→EB) or “no-PASS-no-read” rules.

---

## The outer paths/loops we’ve exposed (sanity check)

### “Hot path truth” (must work in every env)

* **DecisionResponse path:** DF emits decision/action-intent events onto the traffic bus; DLA consumes and writes immutable audit truth.
* **Outcome closure path:** AL emits immutable ActionOutcome events (still idempotent/attributable); DLA may record them as evidence linkage.

### Quarantine and correction (must be the same semantics everywhere)

* **Quarantine remediation loop:** if DLA can’t accept a canonical audit record (incomplete provenance), it writes quarantine; upstream fixes and re-emits; quarantine remains as history.
* **Corrections path (supersedes):** append-only; correction is a new record with explicit supersedes link; “current vs historical view” is semantic, not storage-tech.

### Operational continuity (must be safe under restarts/replay)

* **Restart/replay loop:** EB is at-least-once; consumers checkpoint offsets; DLA must be idempotent and safe under replay.
* **Replay/backfill path:** only **derived** things can be backfilled (audit indexes yes; primary facts no); backfills must declare basis and preserve monotonic offset meaning.

### Human + governance loops (outer network alignment)

* **Case → Label truth path:** evidence (DLA) informs casework; labels become truth only in Label Store (append-only).
* **Degrade loop:** degrade posture is explicit, enforced, and must be recorded in audit provenance.
* **Learning/rollout loop:** registry lifecycle changes are auditable; DF records bundle refs used; DLA preserves that provenance.

---

## Environment ladder drift check for DLA (quick but strict)

**Non-negotiable:** local/dev/prod run the *same platform graph + rails*; only the operational envelope differs.

So, for DLA specifically:

* In **local**, you may collapse deployment units, but DLA must still behave as “EB consumer → immutable audit truth writer” (no local shortcuts like “DF writes directly to DLA”).
* **Retention differs by profile**, but offset/watermark meaning and replay semantics do not; archive is the long-horizon extension of admitted facts and must be addressed by pinned bases.
* Backfills must be declared and only regenerate derived state (audit_index is allowed; canonical truth is not).

---

## Drift checklist to carry into the “inside DLA” phase

When we start illuminating the inner network, **every internal module** must be explainable as serving one of these outer obligations (and must not violate the rails):

1. **Consume only from the facts plane** (`fp.bus.traffic.v1`) and assume at-least-once.
2. **Emit immutable audit truth** to `dla/audit/...` (canonical + quarantine).
3. **Idempotent under replay** using DLA’s local key recipe.
4. **Append-only corrections** via supersedes linkage; never overwrite.
5. **By-ref posture**: no raw payload/feature embedding; references + hashes only.
6. **Degrade posture recorded** as part of the audit story.
7. **Deterministic queryability** without “scan latest and hope” (index may vary; semantics must not).
8. If we use **IG receipts** or **engine audit_evidence**, they must be **by-ref**, **non-scanned**, and (for engine material) **PASS-verified**.

If we keep those eight “outer obligations” in view, the inside design won’t drift.

---

## One small “open decisions” note (safe to defer)

At the outer network level, it’s fine that these remain open until we design internals:

* exact canonicalization rules for computing `audit_record_id`,
* how “current view” is materialized,
* export format/landing zone,
* final quarantine reason enum vocabulary.
  Those don’t change the graph; they change internals and contract details later.

If you’re happy with this checkpoint, we can now step inside DLA and design the inner network as “modules that satisfy the eight outer obligations,” one obligation at a time.

---

Yes — understood. We’re going **one level deeper**: we’ll name the **internal subnetworks (modules)** inside **DLA**, but we’ll keep each of those **opaque** for now.

Below is the **L1 internal decomposition** I’m pinning as the default “production-shaped” DLA module map. It is driven directly by the outer obligations we already locked (EB consumer → append-only truth; idempotent; quarantine; supersedes; deterministic query/export; optional pointer events; OTLP).

---

## DLA internal subnetworks (L1), still opaque

### Core pipeline subnetworks (must exist)

1. **Ingest & Replay Control**

* **Role:** Consume `fp.bus.traffic.v1`, track partition/offset progress (exclusive-next), handle at-least-once duplicates safely.
* **Outputs:** “decoded event + event_ref + replay coordinates” into the next subnetwork; durable checkpoints outward.

2. **Envelope & Type Router**

* **Role:** Enforce **Canonical Event Envelope** minimums, extract ContextPins, and route only the decision-lineage event families to audit processing (everything else is ignored/observed, not made audit truth). 
* **Outputs:** typed “DecisionResponse candidate” / “ActionOutcome candidate” into audit processing.

3. **Audit Admissibility Gate**

* **Role:** Decide **canonical vs quarantine** at the boundary of “audit truth” (completeness checks, by-ref constraints, required provenance tokens, “no silent stripping”).
* **Outputs:** either a “canonical audit candidate” or a “quarantine candidate + reason”.

4. **Identity, Idempotency & Corrections Manager**

* **Role:** Canonicalize (stable) → compute `audit_record_id` → enforce NO-OP under duplicates; manage **supersedes** linkage rules and “current vs historical” semantics.
* **Outputs:** a “write plan” (what record to append, and what index/view transitions are implied).

5. **Append-Only Persistence Writer**

* **Role:** The truth writer: append immutable records into `dla/audit/...` (canonical + quarantine), with “write-then-checkpoint” safety.
* **Outputs:** durable record locators/digests for indexing/pointers.

6. **Query & View Builder**

* **Role:** Maintain the derived **audit_index** + “current/historical” views (rebuildable), and expose deterministic query primitives (no scanning).
* **Outputs:** queryable surfaces + stable record refs.

---

### Operations / governance subnetworks (production-realistic)

7. **Ops, Retention & Export Orchestrator**

* **Role:** Controlled ops actions (reindex, rebuild views, retention policy application, deterministic exports/slices) driven by Run/Operate/governance—without mutating canonical truth.
* **Outputs:** export artifacts + export receipts; reindex receipts; governance facts (as needed by your ops rails).

---

### Optional-but-supported subnetworks (allowed, not required)

8. **Pointer Publisher**

* **Role:** Emit “audit record written” pointer events to `fp.bus.audit.v1` after durable commit (distribution convenience, not truth).
* **Outputs:** pointer events carrying record refs/digests (no payload embedding).

9. **Evidence Attachment Verifier**

* **Role:** When DLA includes IG receipt refs or engine audit_evidence refs, this module checks **ref integrity** (resolvable, digest/PASS proofs if required) *without scanning*.
* **Outputs:** “verified ref set” or quarantine escalation (“broken evidence pointer”).

---

### Cross-cutting rails inside DLA (always present, not “one pipeline step”)

10. **Policy/Profile & Schema Lens**

* **Role:** Load the “environment profile knobs” and audit completeness policy revision; keep “policy changes are visible” discipline.

11. **Observability & Telemetry**

* **Role:** OTLP spans/metrics/logs for consumer lag, canonical vs quarantine rates, write failures, supersedes anomalies, export/reindex operations.

---

## One-layer-deep internal topology (still opaque boxes)

```
fp.bus.traffic.v1
      |
      v
[1 Ingest&Replay] -> [2 Envelope/Router] -> [3 Admissibility Gate] -> [4 Idempotency+Corrections]
                                                           |                     |
                                                           | (quarantine)         v
                                                           +----------------> [5 Append-only Writer] -> object://dla/audit/...
                                                                                      |
                                                                                      v
                                                                            [6 Query & Views] -> db://audit_index

Run/Operate/Gov -> [7 Ops/Exports] -------------------------------------> (reindex/export receipts)

(optional) [8 Pointer Publisher] -> fp.bus.audit.v1
(optional) [9 Evidence Verifier] feeds into [3]/[4] decisions

(cross-cut) [10 Policy/Profile] and [11 Telemetry] touch all modules
```

---

## Pin (so we don’t drift as we go deeper)

This L1 breakdown is now the **authoritative “first illumination layer”** for DLA in this chat. When we step inside next, we’ll pick **one subnetwork at a time** (still staying disciplined), and only reveal the next layer of nodes/handshakes inside that chosen box.

If you want the cleanest order for the next stage: **(1) Ingest&Replay → (3) Admissibility → (4) Idempotency+Corrections → (5) Writer → (6) Views**, because that’s the minimal spine that makes the outer network true.

---

Understood. We’re still **treating each internal subnetwork as an opaque box**, but we’ll now map the **joins (edges), paths (multi-hop flows), and loops (cycles)** that make up **DLA’s internal production network**.

I’ll use the L1 modules we pinned:

**[1] Ingest&Replay**, **[2] Envelope/Router**, **[3] Admissibility Gate**, **[4] Idempotency+Corrections**, **[5] Append-only Writer**, **[6] Query&Views**, **[7] Ops/Retention/Export**, *(optional)* **[8] Pointer Publisher**, *(optional)* **[9] Evidence Verifier**, plus cross-cutting **[10] Policy/Profile Lens** and **[11] Telemetry**.

---

## A. Internal join inventory (direct edges)

### A1) Data-plane joins (the “spine”)

**J1. `1 → 2` Ingest frame handoff**
Transfers: `(event_ref + EB coords + raw envelope bytes)`.

**J2. `2 → 3` Typed routing**
Transfers: `(DecisionResponse candidate | ActionOutcome candidate | ignore/observe)` + extracted pins.

**J3. `3 → 4` Canonical candidate admit**
Transfers: “audit-admissible candidate” + completeness verdict context (what was checked).

**J4. `3 → 4` Quarantine candidate route**
Transfers: “not audit-admissible” + reason bundle (missing/invalid items).
*(Reason to still pass through [4]: you still want idempotency/canonical ids for quarantine artifacts, and you want to unify “write plan” creation.)*

**J5. `4 → 5` Write-plan handoff**
Transfers: immutable “write plan” = `{record_type, record_ids, object_keys, supersedes links, index intents}`.

**J6. `5 → 6` Commit receipt to views**
Transfers: `{durable_record_ref(s) + digests + anchor keys + “current view delta” hints}`.

**J7. `5 → 1` Checkpoint/ack gate**
Transfers: “safe-to-advance offsets for (partition → next_offset)” after durable write (or safe NO-OP).

> J1–J7 are the minimum internal graph that makes DLA a real production vertex.

---

### A2) Lookup/control joins (still internal, but not the hot spine)

**J8. `4 ↔ 6` “Does it exist?” + supersedes resolution**
Purpose: [4] may need a deterministic way to:

* detect conflicting duplicates,
* validate `supersedes` targets,
* resolve “current vs historical” semantics.
  This is a *logical join*; implementation may be “object-key existence checks” or “index lookups,” but the edge exists conceptually.

**J9. `7 ↔ 6` Reindex/rebuild/extract**
Ops asks Views for selection sets, and Views can be rebuilt under Ops control.

**J10. `7 ↔ 5` Export + rebuild reads**
Ops reads canonical truth (by explicit basis) and may write export artifacts/receipts.

**J11. `7 ↔ 1` Replay/backfill control**
Ops can instruct “reconsume from basis,” “pause/drain,” “resume,” or “bounded replay window.”

---

### A3) Optional joins (production-common, but feature-flagged)

**J12. `5 → 8` Pointer emission trigger**
Transfers: “record committed” (refs/digests only) so [8] can emit pointer events.

**J13. `8 → (retry/self)` Pointer publish retry loop**
[8] must be idempotent/retirable; it can’t corrupt truth if it fails.

**J14. `2/3/4 → 9` Evidence verification request**
Transfers: “evidence refs” found in payload (IG receipts, engine evidence locators, etc.).

**J15. `9 → 3/4` Verified ref-set / verdict**
Transfers: `{verified | unverifiable-now | invalid}` + reason details.

---

### A4) Cross-cutting joins (always-on rails)

**J16. `10 → {1..9}` Policy/Profile distribution**
Everything consults the profile knobs and audit completeness rules.

**J17. `{1..9} → 11` Telemetry emission**
Lag, rates, quarantine reasons, write failures, retries, export/reindex operations, etc.

---

## B. Internal path inventory (multi-hop flows)

### P1) Canonical audit write path (DecisionResponse)

`1 → 2 → 3(pass) → 4 → 5 → 6 (+optional 8) → 1(checkpoint)`

This is the “normal” production path: durable truth written, views updated (eventually), checkpoint advances.

### P2) Quarantine path (DecisionResponse not audit-admissible)

`1 → 2 → 3(fail) → 4 → 5(quarantine write) → 6(index quarantine) → 1(checkpoint)`

Key property: **no half-truth**; you still get durable quarantine evidence.

### P3) Duplicate/replay NO-OP path (idempotent ingest)

`1 → 2 → 3 → 4(dedupe hit) → 1(checkpoint)`
(Optionally `→11` emits “NO-OP” metrics.)

### P4) Corrections/supersedes path (new canonical record replaces prior)

`1 → 2 → 3(pass) → 4(resolve supersedes via 6) → 5(append new canonical) → 6(update “current”) → 1`

### P5) Outcome linkage path (ActionOutcome)

`1 → 2(route Outcome) → 3(pass/fail) → 4(link-to-anchor via 6) → 5(append outcome-link record) → 6 → 1`

*(Even if you later choose “store outcomes as separate record family,” the boundary path still looks like this.)*

### P6) Evidence-gated canonical path (when evidence attachments are enabled)

`1 → 2 → (extract refs) → 9 → 3/4 → … → 5 …`
Where [9] can be a gating step: verified refs become part of the canonical candidate; broken refs trigger quarantine.

### P7) Pointer distribution path (optional convenience)

`5(commit) → 8(publish pointer) → (external subscribers)`
Internally: pointer publish happens **after** durable commit (or must tolerate eventual fetch gaps).

### P8) Reindex/rebuild path (derived surfaces)

`7(trigger) → 6(rebuild plan) → 5(read canonical truth under explicit basis) → 6(write rebuilt views/index)`

### P9) Deterministic export/slice path

`7(request) → 6(selection set) → 5(read canonical under basis) → 7(write export artifacts + receipt)`
(Optional: `7 → 8` pointer about export completion.)

### P10) Controlled replay/backfill path (consumer basis reset)

`7(declare basis) → 1(reset/seek) → P1/P2/P3 re-run deterministically → 6 rebuild as needed`

---

## C. Internal loop inventory (cycles that exist in production)

### L1) Crash/restart continuity loop (the fundamental one)

`1 consume → 5 durable write → 1 checkpoint advance → (crash) → 1 replay → 4 idempotency NO-OP → …`
This is the reason **J7 (writer→checkpoint)** and **P3 (NO-OP)** must exist.

### L2) Evidence verification retry loop (eventual consistency loop)

`2/3/4 → 9 verify → (unverifiable-now) → 9 retry/backoff → 3/4`
Ends in either “verified” (canonical path) or “invalid/timeout” (quarantine path).
This is *the* loop that stops pointer/receipt/object-store eventuality from causing silent corruption.

### L3) Pointer publish retry loop (optional)

`5 → 8 publish → (fail) → 8 retry → (success)`
Must be idempotent; cannot affect truth, only distribution.

### L4) Corrections/current-view stabilization loop

Not a runtime spin-loop, but a **semantic cycle**:

* new record appends → current view changes → future reads follow new head.
  This loop is realized through `4↔6` and `5→6`.

### L5) Ops governance loop (reindex/export/backfill)

`7 declares operation → 6/1/5 execute → 11 emits observability → 7 may adjust/pause/resume`
This is the internal “operate the vertex” control cycle.

### L6) Policy/profile update loop

`10 policy rev changes → modules adapt → 11 records “rev in force” → ops validates`
Important: policy changes are *visible* and don’t silently fork semantics.

---

## One-page internal network sketch (still opaque boxes)

```
                 [10 Policy/Profile]
                        |
fp.bus.traffic.v1 -> [1 Ingest&Replay] -> [2 Router] -> [3 Admissibility] -> [4 Idempotency+Corrections] -> [5 Writer] -> dla/audit/*
                                                           ^      |                 |        |
                                                           |      |                 v        v
                                                     [9 Evidence Verifier]        [6 Views] [8 PointerPub] -> fp.bus.audit.v1
                                                                    ^               ^   |
Run/Operate/Gov -> [7 Ops/Exports] ---------------------------------+---+-----------+   +-> audit_index (derived)
(all modules) -> [11 Telemetry]
```

---

If you want the cleanest “next deep dive later” ordering (still staying disciplined):
**(P1/P2 spine)** first, then **L1 continuity**, then **P4 corrections**, then **P5 outcomes**, then optional **P6/P7 evidence+pointer**, then ops **P8–P10**.

---

Alright — we’ll start “opening” DLA by illuminating **internal joins J1–J4** (still keeping the *nodes* opaque, but making the *handshakes* between them explicit and drift-resistant).

I’m going to **declare a few boundary-truths** up front (designer authority) because they determine whether J1–J4 stays aligned with the platform’s pinned outer network.

---

## Standing truths for J1–J4 (so we don’t drift)

1. **DLA must never wedge a partition on a bad message.**
   If an admitted EB message is malformed/unparseable for DLA, DLA records a *quarantine* outcome and continues (advances checkpoint after durable quarantine evidence exists). This preserves “no silent drop” without turning DLA into a single-point-of-stall.

2. **All “audit meaning” is derived from the envelope + DF/AL payload, not from lookups.**
   No fetching from OFP/IEG/Registry/IG during these joins. That’s consistent with the platform authority map (DLA records; it does not resolve).

3. **Canonical envelope is the minimum parse contract at J2.**
   Required `{event_id, event_type, ts_utc, manifest_fingerprint}`; optional pins + trace fields + producer + schema_version + payload.

4. **Idempotency key recipe is fixed at the component boundary.**
   Downstream idempotency is **(ContextPins, audit_record_id)**. So J3/J4 must output candidates that allow [4] to deterministically compute `audit_record_id` without touching anything external.

5. **Hash inputs must not depend on ephemeral transport coordinates.**
   We will **not** make `audit_record_id` depend on EB partition/offset (those differ across environments and replays). We will allow storing EB coords as evidence, but the hash must be driven by stable identifiers + provenance blocks. (This is my “environment ladder drift killer” choice.)

---

# J1 — `1 → 2` Ingest frame handoff

**[1 Ingest & Replay Control] → [2 Envelope & Type Router]**

### Purpose

Separate “bus mechanics” (partitions/offsets/checkpointing) from “event meaning” (envelope parsing and routing). EB is truth for **stream position**, not payload meaning.

### What crosses (the payload of the handshake)

**IngestFrame** (conceptually):

* **bus_coord**: `(stream_name, partition, offset)`
* **raw_message_bytes** (or already decoded bytes if the bus client does that)
* **received_at_utc** (local time; *ephemeral*)
* **bus_headers** (if any; may include trace propagation metadata)

> Important: J1 carries raw bytes forward so J2 can do a single authoritative parse of the canonical envelope.

### Invariants J1 must maintain

* **Ordering**: within a partition, frames must preserve bus order. (Concurrency across partitions is fine.)
* **Non-mutation**: raw bytes are passed through unchanged.
* **No “meaning” added**: J1 does not interpret payload fields. It only packages delivery + coordinates.

### Failure semantics (J1-level)

If the consumer cannot deliver a frame (transient bus errors), J1 retries without advancing checkpoints.
If the frame is deliverable but later turns out malformed, that’s handled in J2/J3/J4 via quarantine — **not by stalling J1**.

### Boundary alignment (what is NOT allowed in J1)

* No schema decisions.
* No “peek into payload” to decide audit logic.
* No external lookups.

---

# J2 — `2 → 3` Typed routing

**[2 Envelope & Type Router] → [3 Audit Admissibility Gate]**

### Purpose

Apply the **platform boundary contract**: parse the **Canonical Event Envelope**, extract pins, and route only relevant event families to the audit pipeline.

The envelope contract is explicit and minimal; payload is intentionally unconstrained at this boundary.

### What crosses (the payload of the handshake)

**RoutedEvent** (conceptually):

* **envelope**: parsed header fields:

  * required: `event_id, event_type, ts_utc, manifest_fingerprint` 
  * optional pins: `parameter_hash, seed, scenario_id, run_id` (ContextPins + seed taxonomy) 
  * optional: `schema_version, producer, trace_id/span_id, parent_event_id, emitted_at_utc` 
* **bus_coord**: the original `(stream, partition, offset)` (evidence only; not part of audit meaning)
* **payload_obj**: the parsed payload object (still opaque at this stage; no semantic validation here)
* **route_kind**: one of:

  * `DECISION_RESPONSE`
  * `ACTION_OUTCOME`
  * `NON_AUDIT_TRAFFIC` (ignore/observe)
  * `MALFORMED_ENVELOPE` (cannot parse envelope or missing required envelope fields)

### Router “interest classifier” (designer pin)

To avoid silent drift:

* If `event_type` matches the allowlist for **audit-lineage families**, route to `DECISION_RESPONSE` or `ACTION_OUTCOME`.
* If it’s clearly “not audit lineage”, route to `NON_AUDIT_TRAFFIC` (consume-and-forget; metrics only).
* If it *looks like audit lineage but is unsupported* (e.g., schema_version unsupported), route to `MALFORMED/UNSUPPORTED` (treated as quarantine downstream, not ignored).

This aligns with the platform’s version-evolution posture: unknown/unsupported shapes must not silently flow where they matter.

### Invariants J2 must maintain

* **Fail closed for envelope validity**: missing required envelope fields → `MALFORMED_ENVELOPE`. 
* **ContextPins extraction is purely mechanical** (no interpretation). ContextPins definition is pinned: `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`; seed is separate. 
* **No payload “meaning” decisions**: J2 does not decide “complete provenance”; it only routes.

### Failure semantics (J2-level)

* If parse fails → produce a `MALFORMED_ENVELOPE` RoutedEvent and forward it (so it can become quarantine evidence rather than a drop).

---

# J3 — `3 → 4` Canonical candidate admit

**[3 Audit Admissibility Gate] → [4 Idempotency & Corrections Manager]**

### Purpose

Convert a routed audit-lineage event into an **audit-admissible canonical candidate** whose content is:

* **complete enough** to become canonical audit truth,
* **policy-compliant** (by-ref posture),
* and **self-contained** so [4] can compute `audit_record_id` deterministically.

Platform pins that DLA is truth for canonical audit record + quarantine, and DLA must record degrade posture and determinism tokens.

### What crosses (the payload of the handshake)

**CanonicalAuditCandidate** (conceptually; no implementation shape pinned yet):

* **audit_kind**: decision vs outcome
* **context_pins**: full set required for joinable decisioning records 
* **identity block**:

  * v0 posture (designer adopting): `decision_id = request_id = event_id` for decision records (stable join anchor)
* **stimulus summary**:

  * `event_ref` (opaque by-ref pointer) + stimulus `event_type` + `event_time_utc` summary (as provided; DLA doesn’t fetch)
* **provenance blocks required for audit truth** (high-level categories):

  * **DL block** (mode + mask; always present; record FAIL_CLOSED if DL unavailable)
  * **OFP block** (`feature_snapshot_hash`, group versions, freshness, `input_basis` watermark vector)
  * **IEG block**: either `{used:true, graph_version}` or `{used:false, reason}` (no ambiguity)
  * **DF outputs**: decision outcome + actions[] with idempotency keys
  * **DF provenance essentials**: policy ref, stage summary, timings
* **correction intent** (optional):

  * `supersedes_audit_record_id` when this is a correction attempt (but link validation happens in [4])
* **evidence attachments (optional)**:

  * IG receipt refs / engine evidence refs are allowed *only as by-ref pointers* (verification can be deferred/optional).

### Admissibility Gate “must enforce” rules (designer pin)

To be considered canonical-admissible at J3:

* Envelope must be valid (already checked by J2). 
* **Must include ContextPins** (decision/outcome are run/world-joinable). 
* Must include the **required provenance blocks** (DL/OFP/IEG + DF outputs + DF provenance).
* Must respect **by-ref privacy posture**: *no embedded raw event payload* and *no full feature vectors* inside the audit candidate.

If any of these fail → it is not eligible for J3 and must go to J4.

---

# J4 — `3 → 4` Quarantine candidate route

**[3 Audit Admissibility Gate] → [4 Idempotency & Corrections Manager]**

### Purpose

Ensure DLA never pollutes canonical truth, but also never loses evidence of failure. Quarantine is a first-class truth family owned by DLA.

### What crosses (the payload of the handshake)

**QuarantineCandidate** (conceptually):

* **reason_code** (concept family; exact enum can be finalized later):

  * `INCOMPLETE_PROVENANCE`
  * `MISSING_SUPERSEDES_LINK`
  * `INVALID_SUPERSEDES_LINK`
  * plus: `MALFORMED_ENVELOPE` / `UNSUPPORTED_VERSION` (router-level issues)
* **missing_fields[]** where applicable (to force upstream compliance) 
* **correlation** (as much as can be extracted safely):

  * `event_id` (if parseable), `event_type`, `ts_utc`
  * ContextPins if present/partial
  * bus_coord (stream/partition/offset) as evidence pointer
* **payload_evidence_ref** (by-ref pointer to the original payload blob if you choose to persist it in a restricted evidence area; no raw embedding in the quarantine record itself)

### Why J4 still flows through [4]

Even quarantine needs:

* deterministic IDs (so repeated failures are inspectable and optionally dedupe-able),
* consistent write planning,
* consistent “checkpoint only after durable evidence.”

### Quarantine policy pin (designer authority)

* **Reject-and-quarantine** on forbidden embedded fields. We do not “strip and pretend canonical.”
  This preserves “no hidden mutation” and forces explicit governance if you ever want to store raw payloads.

---

## Quick “shape of the internal spine” (J1–J4 only)

```
[1 Ingest&Replay]
   | J1: (bus_coord + raw bytes)
   v
[2 Envelope&Router]
   | J2: RoutedEvent (DecisionResponse | Outcome | NonAudit | Malformed)
   v
[3 Admissibility Gate]
   | J3: CanonicalAuditCandidate  -----> [4 Idempotency+Corrections]
   | J4: QuarantineCandidate      -----> [4 Idempotency+Corrections]
```

---

If you’re happy with these join meanings, the next natural illumination is **within [4]** to define how it treats J3 vs J4 (idempotent no-op, correction vs quarantine, “current vs historical” hooks) — but we’ll stay disciplined and only go one join at a time.

---

Absolutely. We’ll illuminate **J5–J7** as **production-grade internal handshakes** (modules still opaque, but the *edges* become explicit and drift-resistant).

I’m going to pin one critical boundary truth first:

**PIN:** **Checkpoint advancement (J7) is gated only by “durable audit evidence exists”** — i.e., canonical/quarantine truth has been safely written. **Checkpointing must not depend on indexing/pointer publishing.**
Reason: otherwise a DB outage or pointer-bus hiccup would stall the whole audit recorder and violate “always-on consumer/writer” posture.

---

# J5 — `4 → 5` Write-plan handoff

**[4 Idempotency & Corrections] → [5 Append-only Writer]**

### Purpose

Turn “candidate + policy decisions” into an **immutable write intent** that:

* is **append-only** (canonical or quarantine),
* is **idempotent** under replay/duplicates,
* expresses **corrections (supersedes)** explicitly,
* and tells the Writer exactly *what* to persist **without** further interpretation.

### What crosses J5

A **WritePlan** (conceptually) with *everything Writer needs*:

**A) Classification**

* `record_family`: `CANONICAL_DECISION | CANONICAL_OUTCOME_LINK | QUARANTINE | (optional) OTHER_AUDIT_ARTIFACT`
* `plan_kind`: `WRITE | NOOP`

  * **NOOP** is how we unify duplicate handling while still flowing through J7 consistently.

**B) Identity + join keys**

* `context_pins`
* `decision_anchor` (e.g., `(ContextPins, decision_id)`), if applicable
* `audit_record_id` (deterministic hash of canonicalized content or canonicalized failure capsule)
* (optional) `supersedes_audit_record_id` (already validated by [4] as acceptable or rejected into quarantine)

**C) Storage intents**

* `object_keys[]`: one or more immutable object keys to write
* `root_commit_key`: the **single “root” object** whose existence denotes “commit complete” (see invariants below)
* `content_digests[]`: digests expected for the written objects (or at least for the root commit object)

**D) Derived-surface intents**

* `index_intents`: “what [6] should reflect” (e.g., upsert current-head pointer, add historical row, add quarantine row)
* `pointer_intent`: “emit pointer event?” (only describes intent; Writer may hand this to [8] later)

**E) Provenance/evidence refs**

* `event_ref` (EB coords + envelope ids) stored as evidence
* any optional verified evidence refs (IG receipt refs, engine evidence locators) already reduced to by-ref form

### Invariants J5 must maintain (drift killers)

1. **Writer does not re-decide anything.**
   If it’s in the WritePlan, it’s authoritative; if it’s not, Writer cannot invent it.

2. **WritePlan is replay-safe.**
   Re-sending the same WritePlan must be safe; if the root object already exists, the write is a NOOP at the persistence layer.

3. **Atomicity via “root commit object.”**
   Object stores don’t give atomic multi-object transactions. So we pin this production semantic:

   * Writer may write multiple blobs, but **the audit record is only “durable” when the root commit object is written last**.
   * Everything else is considered “staging” until the root exists.

4. **Environment stability.**
   `audit_record_id` and object key derivations must not depend on transport coordinates (partition/offset) or local timestamps. (Those can be recorded *inside* the record, but they mustn’t drive identity.)

### Failure semantics at J5

* If [4] cannot form a valid write plan (e.g., correction ambiguity), it must route to a **quarantine WritePlan** (not “drop”).
* If [4] detects a duplicate, it issues a **NOOP WritePlan** (still flows through [5] so that J7 can advance checkpoints uniformly).

---

# J6 — `5 → 6` Commit receipt to views

**[5 Append-only Writer] → [6 Query & Views]**

### Purpose

Communicate: **“a durable immutable audit fact now exists at ref X”** so derived query surfaces can update deterministically.

### What crosses J6

A **CommitReceipt** (conceptually):

**A) Commit proof**

* `root_commit_ref` (object key / locator)
* `root_commit_digest`
* `record_family`
* `audit_record_id`
* (optional) `supersedes_audit_record_id` if this commit is a correction

**B) Query keys**

* `context_pins`
* `decision_anchor` (if applicable)
* `ts_utc` (domain time for indexing windows)
* a minimal set of “index axes” (degrade mode, bundle ref hash, action types, etc.) **as already present** (no recompute)

**C) Index delta intent**

* `index_delta`: what should change in derived view space:

  * add historical row
  * update current-head pointer
  * add quarantine entry (if quarantine family)
  * link outcome to decision anchor (if outcome-link)

### Invariants J6 must maintain

1. **Receipts are idempotent and reorder-tolerant.**
   [6] must handle receiving the same CommitReceipt multiple times (retries/replay) without duplicating index rows, and must tolerate out-of-order receipts across partitions.

2. **Views are derivative, truth is in object store.**
   Even if indexing fails, the canonical record remains durable and addressable by ref.

3. **Checkpointing is not coupled to indexing.**
   Index failure should not prevent DLA from recording truth and progressing offsets (though it should raise telemetry + may trigger ops backpressure policies).

### Failure semantics at J6

* If [6] cannot apply the receipt (DB down, transient error), it queues/retries (or marks “needs reindex”)—but it must never request Writer to “undo” a commit (append-only world).
* Operationally, sustained failure raises an alert and may trigger an ops-driven reindex/rebuild path, but it does not invalidate written truth.

---

# J7 — `5 → 1` Checkpoint / ack gate

**[5 Append-only Writer] → [1 Ingest & Replay Control]**

### Purpose

This is the **safety latch** that makes DLA restart/replay correct:

> **Only advance EB offsets when you can prove the corresponding audit outcome (canonical or quarantine or noop) is safe and durable.**

### What crosses J7

An **AckTicket** (conceptually):

**A) Consumption coordinates**

* `stream_name`
* `partition_id`
* `offset_consumed`
* `next_offset` (exclusive-next)

**B) Apply outcome**

* `apply_status`: `COMMITTED_CANONICAL | COMMITTED_QUARANTINE | NOOP_DUPLICATE`
* `audit_record_ref` (if committed; optional but helpful)
* `audit_record_id` (for correlation/telemetry)

**C) Ordering guard**

* `sequence_hint` or “expected next offset” (optional) to help [1] enforce contiguous advancement in presence of concurrency

### Invariants J7 must maintain (non-negotiable)

1. **Write-then-checkpoint order.**
   AckTicket is emitted **only after**:

   * the root commit object exists (canonical/quarantine), or
   * [5] has deterministically concluded “NOOP duplicate” (and thus no write is needed).

2. **No gaps per partition.**
   [1] must only move a partition checkpoint forward when it has AckTickets for a contiguous range up to `next_offset`.

3. **Crash-safe semantics.**
   If DLA crashes after commit but before checkpoint, replay will reprocess → [4]/[5] will NOOP safely → then checkpoint advances. This is the intended loop.

### Failure semantics at J7

* If Writer cannot commit (object store outage), it **must not** emit AckTicket; [1] will not advance offsets; consumer lag grows (observable), and ops/degrade can respond.
* If a message is malformed, the correct behavior is: **commit quarantine** → emit AckTicket → continue. (Never wedge a partition on a poison message.)

---

## Mini internal sketch (J5–J7 only)

```
[4 Idempotency+Corrections]
   | J5: WritePlan (WRITE or NOOP; canonical/quarantine; root_commit_key)
   v
[5 Append-only Writer]
   | J6: CommitReceipt -> [6 Views] (derived; retryable; not gating)
   |
   | J7: AckTicket -> [1 Ingest] (exclusive-next offsets; contiguous per partition)
   v
object://dla/audit/... (truth)
```

---

If you want the next logical illumination after J5–J7, it’s **the “commit model” inside [5]** (still a box, but we’d decide whether we use a single-root object vs “manifest + shards” and how NOOP is detected). That choice is what makes these joins mechanically implementable without drift.

---

Yep. We’re now illuminating **A2 lookup/control joins** — **J8–J11** — still keeping the modules opaque, but making the **internal boundary handshakes** crisp enough that the *inner* deep dive won’t drift.

I’m going to treat these as **production-critical control surfaces**: they’re how DLA stays correct under replay, corrections, ops, and rebuilds.

---

## J8 — `4 ↔ 6` Existence + supersedes + current/historical resolution

**[4 Idempotency & Corrections] ↔ [6 Query & Views]**

### Why this join exists

[4] needs answers to three questions without “scanning” or external lookups:

1. **Duplicate vs new:** “Does this `audit_record_id` already exist?”
2. **Correction validity:** “Does `supersedes_audit_record_id` exist, and is it in-scope (same ContextPins)?”
3. **Conflict detection / head resolution:** “Is there already a canonical head for this `decision_anchor`, and if so what is it?” (to prevent ambiguous overwrite behavior)

### What crosses J8

Think of J8 as two tiny request/response families:

#### J8.a — Deterministic Lookup Requests (from [4] → [6])

* `LookupAuditRecord(audit_record_id, context_pins)`
* `LookupHead(decision_anchor)`  *(current view head id/ref)*
* `LookupSupersedesTarget(supersedes_audit_record_id, context_pins)`
* `LookupOutcomeLink(anchor, idempotency_key)` *(if you treat outcomes as link records)*

#### J8.b — Deterministic Lookup Responses (from [6] → [4])

* `EXISTS {record_ref, family, digest}`
* `NOT_FOUND`
* `CONFLICT {reason}` (e.g., “head exists but you didn’t provide supersedes link”)
* `UNAVAILABLE {reason}` (views/index temporarily unreachable)

### Non-negotiable invariants (designer pins)

1. **Keyed lookups only (no “search”).**
   J8 is always keyed by `audit_record_id` or `decision_anchor`. No scans, no “latest”.

2. **Correctness must not depend on index freshness.**
   [6] may use an index internally, but J8’s answers must be *correct* even if indices are lagging.
   Practical consequence: [6] must be able to answer existence/head questions from a **truth-backed source** (e.g., commit-key existence / head pointer truth), not only “whatever is in the DB right now”.

3. **Fail-closed on corrections when validation is impossible.**
   If [4] can’t confirm the supersedes target exists (J8 returns UNAVAILABLE), we do **not stall ingestion**. We route that candidate into **quarantine** as “supersedes_unverifiable_now” (or equivalent) so we keep progressing and the failure is visible.

4. **Duplicates are NOOP-safe even if [6] is down.**
   If [4] can deterministically conclude it’s a duplicate (same `audit_record_id` for same pins), it can emit a NOOP write plan without requiring [6] to be available.

### Failure semantics

* `UNAVAILABLE` never wedges partitions: it converts “would-be canonical” into **quarantine** (not drop), or into **NOOP** only when safe.
* If [6] says “head exists” and candidate lacks a supersedes link → **quarantine** (ambiguity is forbidden in an append-only recorder).

---

## J9 — `7 ↔ 6` Reindex / rebuild / extract planning

**[7 Ops/Retention/Export] ↔ [6 Query & Views]**

### Why this join exists

Ops needs deterministic ways to:

* rebuild derived surfaces (`audit_index`, “current view”),
* produce deterministic selection sets for export,
* assess index/view health,
  without mutating canonical truth.

### What crosses J9

Treat J9 as “planning + receipts”:

#### J9.a — Ops → Views requests

* `PlanReindex(scope, basis)`

  * scope: `{context_pins?, time_window?, families?}`
  * basis: explicit replay basis (offset ranges/checkpoints) or explicit object-manifest basis
* `PlanExportSelection(filters, view=historical|current, basis)`
* `GetViewHealth()` (lag, divergence indicators, last applied basis)
* `GetSelectionManifest(manifest_id)` *(if selection is staged as a manifest)*

#### J9.b — Views → Ops responses

* `SelectionPlan {deterministic ordering, selection_manifest_ref}`
* `ReindexPlan {work units, required basis, expected outputs}`
* `HealthReport {freshness, backlog, error corridors}`

### Non-negotiable invariants

1. **Every operation is basis-driven.**
   No “rebuild everything because vibes.” Even “full rebuild” must declare an explicit basis (“all keys under partitioned prefixes X for dates Y..Z” is acceptable as an explicit basis).

2. **Views remain derivative.**
   J9 can never imply mutation of canonical audit truth; it only governs derived surfaces and exports.

3. **Deterministic selection order is part of the plan.**
   Exports and rebuilds must be reproducible for the same basis/filters.

### Failure semantics

* If basis is missing/ambiguous → reject request (ops must restate it with an explicit basis).
* If views are degraded/unhealthy → plans can still be produced, but must be explicit about partial coverage and must emit “incomplete basis” warnings (never silently partial).

---

## J10 — `7 ↔ 5` Export + rebuild reads/writes

**[7 Ops/Retention/Export] ↔ [5 Append-only Persistence I/O]**

### Why this join exists

Once Ops has a **selection plan** (J9), it needs a deterministic way to:

* **read canonical audit truth by reference**, and
* **write export artifacts + receipts** (and potentially index rebuild artifacts),
  without abusing “scan object store” behavior.

### What crosses J10

#### J10.a — Ops → Persistence requests

* `ReadRecords(selection_manifest_ref)` *(by explicit list of record refs/keys)*
* `WriteExportArtifacts(export_manifest, artifacts[])`
* `WriteExportReceipt(export_receipt)`
* `WriteReindexArtifacts(reindex_run_id, artifacts[])` *(optional)*
* `ApplyRetentionPolicy(policy_rev, scope, basis)` *(only if you support deletion/archival operations)*

#### J10.b — Persistence → Ops responses

* `ReadResults {record_refs_read, missing_refs, digests}`
* `WriteResults {artifact_refs, digests}`
* `RetentionReceipt {what was expired/archived, basis, policy_rev}`

### Non-negotiable invariants

1. **Read by ref; never “discover.”**
   J10 reads are driven by explicit manifests/refs produced by J9, not by listing arbitrary prefixes.

2. **Exports are immutable once published.**
   Export artifacts and receipts are write-once/append-only (same posture as other artifacts).

3. **Retention is governed and explicit.**
   If you apply retention, it must be scoped, basis-driven, and produce a receipt. (Canonical truth remains append-only; retention is an operational lifecycle, not a rewrite.)

### Failure semantics

* Missing refs during reads → export/rebuild either fails closed or produces an explicit partial receipt (your governance choice), but never silently omits.
* Write failures produce no “success” receipt; retries are allowed and must be idempotent (by export_run_id / artifact digest).

---

## J11 — `7 ↔ 1` Replay / backfill / pause-drain-resume control

**[7 Ops/Retention/Export] ↔ [1 Ingest & Replay Control]**

### Why this join exists

This is the “operate the consumer safely” join. It’s how you:

* pause/drain (safe deploy),
* resume,
* reset to a declared replay basis,
* run bounded replays/backfills without corrupting audit truth.

### What crosses J11

#### J11.a — Ops → Ingest control commands

* `Pause(partitions|all)`
* `Drain(partitions|all, until_offset_vector)` *(stop after processing up to a specific point)*
* `Resume(partitions|all)`
* `SeekToBasis(basis)`

  * basis = explicit offset vector per partition, or checkpoint set, or a time-to-offset mapping *already resolved elsewhere*
* `BoundedReplay(basis_start, basis_end, mode)`

  * mode: “reconsume + noop-safe” vs “reconsume + rebuild views” (still no mutation of canonical truth)

#### J11.b — Ingest → Ops status

* `ConsumerState {current_offset_vector, lag, paused_partitions}`
* `DrainReceipt {reached_offset_vector}`
* `ReplayReceipt {basis_applied, coverage, any gaps}`

### Non-negotiable invariants

1. **Offsets are exclusive-next and monotonic.**
   All seek/drain semantics are based on explicit offsets and contiguous processing per partition.

2. **Replays never mutate canonical truth.**
   They rely on idempotency: duplicates become NOOP; derived surfaces can be rebuilt.

3. **Basis must be explicit.**
   No “replay last week” unless that has already been translated into a concrete offset basis.

### Failure semantics

* If the requested basis is outside retention and archive coverage is unknown → reject or fail closed (never pretend completeness).
* If drain can’t reach target due to persistence failures (writer down), drain must not claim completion.

---

## Mini internal control-plane sketch (J8–J11 only)

```
           [4 Idempotency+Corrections] <----J8----> [6 Query&Views]
                    ^
                    |
                    |
[7 Ops/Exports] ----J9----> [6 Query&Views]
      |
      +----J10----> [5 Persistence I/O]
      |
      +----J11----> [1 Ingest&Replay]
```

---

## One final pin (designer authority) to prevent future drift

**Ops actions (J9–J11) are *never* allowed to require “quietly scanning” production truth.**
If you need enumeration, it must be expressed as an **explicit basis** (manifest, offset window, partitioned prefix window) with a receipt. That keeps your environment ladder aligned and keeps governance sane.

If you want, next we can illuminate **A3 optional joins** (J12–J15) or go straight to a deeper pass inside **[4]** (since J8 leans heavily on how [4] defines “conflict” vs “correction”).

---

Absolutely — we’ll illuminate **A3 optional joins J12–J15** (feature-flagged, production-common). As before: modules stay opaque, but the **handshakes** become explicit and bounded so these options don’t drift into “new truth planes” or block the spine.

I’m pinning one rule first because it governs all four joins:

**PIN:** Optional joins **must not gate canonical truth** unless explicitly enabled by policy revision — and even then they must fail into **quarantine**, not stall ingestion.
(Reason: DLA is always-on; optional enrichments must not turn into a partition-wedger.)

---

# J12 — `5 → 8` Pointer emission trigger

**[5 Append-only Writer] → [8 Pointer Publisher]**

### Purpose

Emit **audit-pointer events** (to `fp.bus.audit.v1`) *after* a durable audit record exists. This is a **distribution convenience** plane: it does not create truth; it points to truth.

### What crosses J12

A **PointerTrigger** message (conceptually):

* **commit_ref**: object locator of the durable root commit record (canonical or quarantine)
* **commit_digest**: digest of the root commit record
* **record_family**: `CANONICAL | QUARANTINE` (and optionally outcome-link)
* **audit_record_id**
* **decision_anchor** (if applicable)
* **context_pins**
* **source_event_ref**: EB coords + envelope ids (evidence only)
* **emit_policy_tag**: which pointer policy rev enabled this (so behavior is visible)

> No payload embedding. Only refs/digests + correlation keys.

### Invariants (designer pins)

1. **Emit-after-durable:** J12 is triggered only after the root commit object exists.
2. **Idempotent trigger:** replaying the same PointerTrigger must be safe.
3. **No truth mutation:** pointer plane must never be consumed as if it were the audit record itself.

### Failure semantics

* If pointer emission is disabled, J12 simply never happens.
* If [8] is unavailable, the trigger can queue/retry, but **audit truth is already durable**.

---

# J13 — `8 → (retry/self)` Pointer publish retry loop

**[8 Pointer Publisher] ↔ itself (retries)**

### Purpose

Pointers are “nice-to-have.” Publishing them must be **retriable, idempotent**, and must never affect truth.

### What crosses J13

Internally, [8] maintains a **PublishAttempt** state machine (conceptually):

* **pointer_event_id** (deterministic)
* **target_topic**: `fp.bus.audit.v1`
* **payload**: minimal pointer payload (refs/digests only)
* **attempt_count / backoff_state**
* **last_error**

**Deterministic pointer_event_id pin (important):**
I’m declaring that pointer events use a stable id derived from `(context_pins, audit_record_id, record_family)` so duplicates are naturally dedupable by subscribers. This prevents “pointer spam” under retries/replays.

### Invariants

1. **Idempotent publish:** multiple publishes of the same pointer_event_id are acceptable.
2. **At-least-once semantics:** subscribers must tolerate duplicates.
3. **No coupling to checkpointing:** pointer publishing must not gate J7 (offset ack).

### Failure semantics

* If publication fails, [8] retries with backoff.
* Persistent failure surfaces via telemetry but does not halt ingest/write.

---

# J14 — `2/3/4 → 9` Evidence verification request

**[2 Router] / [3 Admissibility] / [4 Idempotency+Corrections] → [9 Evidence Attachment Verifier]**

### Purpose

When DLA chooses to include **evidence attachments** (IG receipt refs, engine audit_evidence locators, etc.), [9] verifies that those refs are:

* **well-formed**
* **resolvable without scanning**
* and, where required, **cryptographically admissible** (engine PASS discipline).

Crucially, this is an **attachment verifier**, not a “data fetcher.” It verifies *pointers + proofs*, not payload meaning.

### What crosses J14

An **EvidenceVerifyRequest** (conceptually):

* **request_id** (deterministic)
* **evidence_items[]**, each item has:

  * `evidence_kind`: `IG_RECEIPT_REF | IG_QUAR_REF | ENGINE_LOCATOR | GATE_RECEIPT | OTHER_REF`
  * `ref`: locator (object ref, receipt_id, EngineOutputLocator, etc.)
  * `required_level`: `OPTIONAL_ENRICHMENT | REQUIRED_FOR_CANONICAL`
  * `scope`: context pins / output identity pins relevant to the evidence
  * `proofs[]` if already present (e.g., GateReceipt for engine)
* **candidate_correlation**:

  * `context_pins`, `audit_record_id` (if known), `decision_anchor`, `event_id`

### Who calls [9] and when (designer boundary)

* [2] may call it only for **structural verification** (e.g., “this looks like an EngineOutputLocator shape”) — not required.
* [3] calls it when admissibility policy says “attachments are required” or when it wants to optionally enrich.
* [4] calls it when correction linking requires verifying that a referenced prior record or receipt ref actually exists (but [4] should prefer J8 for internal audit record existence; [9] is for *external evidence refs*).

### Invariants

1. **No scanning allowed:** verification must be keyed by explicit refs/ids.
2. **Gate-specific PASS verification for engine evidence:** must use the gate map rules; do not assume one hashing scheme.
3. **Verifier never changes truth:** it only returns verdicts.

### Failure semantics at the request level

If [9] is unavailable:

* If `required_level=OPTIONAL_ENRICHMENT` → proceed without the attachment (but emit telemetry).
* If `required_level=REQUIRED_FOR_CANONICAL` → the candidate must become **quarantine** (not stall).

---

# J15 — `9 → 3/4` Verified ref-set / verdict

**[9 Evidence Verifier] → [3 Admissibility] and/or [4 Idempotency+Corrections]**

### Purpose

Return a **verdict per evidence item** so upstream stages can decide:

* canonical vs quarantine,
* attach vs omit,
* retry later vs fail closed.

### What crosses J15

An **EvidenceVerifyResult** (conceptually):

* **request_id**
* **results[]**, each with:

  * `evidence_item_id`
  * `verdict`: `VERIFIED | UNVERIFIABLE_NOW | INVALID`
  * `reason_code` (e.g., `MISSING_REF`, `DIGEST_MISMATCH`, `PASS_MISSING`, `UNSUPPORTED_GATE_RULE`, `ACCESS_DENIED`)
  * `resolved_ref` (normalized locator if applicable)
  * `verified_digest` (if computed/confirmed)
  * `verified_scope` (pins confirmed)
* **overall_recommendation**:

  * `OK_TO_ATTACH`
  * `OMIT_OPTIONAL_ATTACHMENTS`
  * `MUST_QUARANTINE` (because required evidence failed)

### How [3] uses J15 (admissibility)

* If required evidence is `INVALID` or stays `UNVERIFIABLE_NOW` past a policy-defined window → **quarantine** (“broken required evidence pointer”).
* If optional evidence fails → omit attachment, proceed canonical.

### How [4] uses J15 (corrections/idempotency)

* If a correction references external receipts/evidence that must be present for the corrected record to be meaningful, [4] can choose:

  * treat failure as canonical-without-attachment (if optional), or
  * quarantine (if required by policy).

### Invariants

1. **Three-valued verdict matters:** `UNVERIFIABLE_NOW` is distinct from `INVALID`.
   It supports eventual-consistency environments (object store replication lag) without inventing truth.
2. **No automatic retries in [3]/[4]:** retries/backoff belong inside [9] (or orchestration), not scattered across the pipeline.
3. **Verdicts are recordable:** verdicts can be included as part of the quarantine reason bundle or attached metadata (by-ref) for transparency.

---

## The optional subgraph (J12–J15) in one view

```
                 (after durable commit)
[5 Writer] ----J12----> [8 Pointer Publisher] --J13(retry)--> fp.bus.audit.v1

[2 Router]/[3 Gate]/[4 Corrections] ----J14----> [9 Evidence Verifier]
                                          <----J15----  (VERIFIED | UNVERIFIABLE_NOW | INVALID)
```

---

## Drift guardrails (designer declarations)

* **Pointer path never gates ingest checkpointing.** (J7 is independent of J12/J13.)
* **Evidence verification never implies scanning.** It must always be keyed by explicit refs/ids.
* **Optional evidence is optional unless policy says otherwise.** If policy upgrades it to required, failure becomes quarantine — never stall.

If you want, next we can illuminate the **cross-cut rails** (A4 J16–J17) briefly, or we can start opening the first internal box (I recommend starting with **[4] Idempotency+Corrections**, because it’s the “semantic heart” that drives correctness under replay and supersedes).

---

Locked. Here’s **J16–J17** as the **two cross-cutting rails** inside DLA, with **designer-authority semantics** (modules still opaque; we’re illuminating the *joins*).

---

## J16 — `10 → {1..9}` Policy/Profile distribution

**[10 Policy/Profile & Schema Lens] feeds every internal module**

### What J16 is

A **single source of configuration truth inside DLA**, delivering a **ConfigSnapshot** to all modules so they behave consistently and the environment ladder doesn’t create “three different DLAs”.

### What crosses J16

A **ConfigSnapshot** (conceptually one object, versioned), containing two clearly separated halves:

1. **Wiring profile (non-semantic)**

* endpoints (EB, object store, DB, OTLP)
* concurrency limits, batch sizes, timeouts, retry knobs
* credentials/secrets handles

2. **Policy profile (semantic, outcome-affecting)**

* audit completeness requirements (what makes canonical vs quarantine)
* supersedes/corrections rules (what is accepted vs quarantined)
* evidence attachment rules (optional vs required; verification requirements)
* pointer emission enablement (on/off)
* export permissions + scope limits
* retention/backfill posture (what ops actions are permitted)

Each snapshot has:

* `policy_rev` (must be recorded/observable)
* `wiring_rev` (also observable)
* `profile_name` (local/dev/prod)
* `build_id` (so “code + policy + profile” is always knowable)

### How modules consume J16 (the “no drift” rule)

**PIN:** Every processing unit (single event, small batch, export job, reindex run) must run under **one immutable ConfigSnapshot** captured at the start of that unit.

* Policy updates apply **between** events/batches/jobs — never “mid-event”.
* This prevents “half of a decision record was checked under rev A, the other half under rev B”.

### Hot reload semantics (production-friendly)

* If a new snapshot is available: lens swaps `current_snapshot` atomically.
* If refresh fails: lens keeps **last-known-good snapshot** and emits telemetry (see J17).
  It never silently falls back to “defaults”.

### Failure semantics (important)

* **Startup:** if no valid snapshot exists, DLA does **not** start (fail closed).
* **Runtime:** if refresh fails, DLA continues on last-known-good, but:

  * emits a “config_stale” health signal,
  * and ops can choose to drain/restart via J11 rather than allow indefinite drift.

### Why J16 matters for the environment ladder

This is what makes “promotion = profile selection” real:

* Local/dev/prod can differ in wiring and strictness knobs,
* but the *mechanism* and *meaning* stay identical, because every decision inside DLA is explicitly tied to a `policy_rev`.

---

## J17 — `{1..9} → 11` Telemetry emission

**All internal modules emit into [11 Observability & Telemetry]**

### What J17 is

A **non-blocking, always-on telemetry bus** that turns DLA into an operable production unit without coupling correctness to observability availability.

### What crosses J17

Three families, all **structured** and **correlatable**:

1. **Metrics**
   Minimum set (production-grade):

* **consumer lag** per partition + “age” indicators
* throughput: events/sec in, records/sec written
* canonical vs quarantine counts + quarantine reason breakdown
* dedupe/NOOP rate (replay pressure)
* writer error rate + commit latency
* index apply error rate + index lag (if index exists)
* pointer publish success/fail rate (if enabled)
* evidence verification verdict counts (VERIFIED/UNVERIFIABLE/INVALID) (if enabled)
* ops job metrics: export runs, reindex runs, replay ops

2. **Traces**

* If envelope contains trace context, propagate it.
* At minimum, create spans for: ingest → route → admissibility → idempotency → commit → index update → checkpoint ack.
* Attach stable tags: `event_id`, `audit_record_id`, `decision_anchor`, `policy_rev`, `profile_name`, plus `bus_coord` (as evidence).

3. **Logs**

* Structured boundary logs only (no payload dumps), such as:

  * “canonical_commit” (ref + ids)
  * “quarantine_commit” (reason + missing fields + correlation)
  * “supersedes_accept/reject”
  * “index_apply_failed”
  * “pointer_publish_failed”
  * “config_refresh_failed / config_rev_changed”
  * “export_started/finished” + basis

### Non-negotiable invariants for J17

**PIN:** Telemetry must never gate correctness.

* If OTLP is down, DLA still consumes/writes/checkpoints.
* Telemetry drops or buffers, but it does not stall J7.

**PIN:** Telemetry must be “enough to reconstruct why.”
Every emitted metric/log/trace must carry:

* `policy_rev`, `profile_name`, `build_id`
  so you can always answer “what rules were in force?” (critical for audit systems).

### Environment ladder knobs for J17

Allowed to vary per profile (without changing meaning):

* sampling rates (traces), log verbosity, dashboard/alert thresholds
* retention of telemetry data
  But the **same signals exist** everywhere (local might show them in stdout; prod in dashboards).

---

## One small visual (how these rails overlay everything)

```
            [10 Policy/Profile Lens]  --J16-->  (1..9 modules)
                         |
                         v
          (policy_rev, profile_name, build_id everywhere)

(1..9 modules) --J17--> [11 Telemetry] ---> OTLP / dashboards / alerts
```

---

If you’re happy with J16–J17, the next clean “step inside” (without overwhelming) is to open **one box**: either **[3 Admissibility Gate]** (policy-heavy) or **[4 Idempotency+Corrections]** (correctness-heavy).

---

Yep — let’s **illuminate internal paths P1–P5** as **production sequences** across the already-lit joins (J1–J7, J8, J12 optional), while keeping each module opaque.

I’ll present each path with:

* **Intent**
* **Step sequence (module-by-module)**
* **What’s guaranteed at the boundary**
* **Failure semantics (how we keep forward progress + no drift)**

I’ll use the module IDs we pinned:

`[1] Ingest&Replay  →  [2] Router  →  [3] Admissibility  →  [4] Idempotency+Corrections  →  [5] Writer  →  [6] Views`
(optional) `[8] Pointer Publisher`
Cross-cutting: `[10] Policy Lens`, `[11] Telemetry`

---

## P1 — Canonical audit write path (DecisionResponse)

**Shape:** `1 → 2 → 3(pass) → 4 → 5 → 6 (+optional 8) → 1(checkpoint)`

### Intent

Turn a **valid, audit-complete DecisionResponse** into an **immutable canonical audit record**, update derived views/index, and **advance offsets safely**.

### Step sequence (what happens, in order)

1. **[1] consumes** the next message from `fp.bus.traffic.v1` and emits an **IngestFrame** to [2] (J1).

   * Carries `bus_coord + raw_bytes` (and headers).

2. **[2] parses canonical envelope**, extracts ContextPins, classifies type = `DECISION_RESPONSE`, and emits **RoutedEvent** to [3] (J2).

   * If it’s not an audit-lineage type, it routes to “ignore/observe” (not this path).

3. **[3] runs audit admissibility checks** under a single ConfigSnapshot from [10].

   * DecisionResponse contains required provenance blocks (degrade posture, feature snapshot hash + input_basis, registry bundle ref, etc.)
   * By-ref posture is respected (no raw payload embedding, no full feature vectors).
   * If all checks pass: emit **CanonicalAuditCandidate** to [4] (J3).

4. **[4] canonicalizes + computes deterministic identity** and determines whether this is:

   * **NEW canonical** (normal case), or
   * **DUPLICATE** (then P3), or
   * **CORRECTION** (then P4).
     For P1 normal case: produce **WritePlan{WRITE, CANONICAL}** to [5] (J5).

5. **[5] appends immutable truth** to `object://dla/audit/...` using the WritePlan.

   * Writes any sub-objects first, writes the **root commit object last** (our pinned “commit boundary”).
   * Produces **CommitReceipt** to [6] (J6).

6. **[6] updates derived surfaces** (audit_index + current/historical view semantics).

   * Must be **idempotent** under duplicate receipts.
   * Failures here do *not* block checkpointing (see failure semantics below).

7. *(optional)* **[8] publishes pointer event** to `fp.bus.audit.v1` if enabled, triggered by [5] (J12/J13).

   * Pure by-ref pointer + digest; no payload embedding.

8. **[5] emits AckTicket** back to [1] (J7) indicating the record is durable and it’s safe to advance offsets.

   * [1] advances the **exclusive-next checkpoint** contiguously per partition.

### What the platform can rely on after P1 completes

* Canonical audit truth exists immutably in `dla/audit/...`.
* Derived query/index will *eventually* reflect it (or can be rebuilt).
* Offsets have advanced safely: replay won’t duplicate truth due to idempotency.

### Failure semantics (production posture)

* If **[6] index/view update fails**: record is still durable; offsets still advance; [11] emits alerts; [7] ops can reindex later.
* If **pointer publishing fails**: truth still exists; subscribers can poll/index or replay pointer topic later.
* If **[5] cannot commit**: no AckTicket; offsets do not advance; consumer lag grows (observable), and degrade/ops can respond.

---

## P2 — Quarantine path (DecisionResponse not audit-admissible)

**Shape:** `1 → 2 → 3(fail) → 4 → 5(quarantine write) → 6(index quarantine) → 1(checkpoint)`

### Intent

Never write “half-truth audit.” Instead: **persist inspectable quarantine evidence** and keep consuming (no wedging).

### Step sequence

1. **[1]→[2]→[3]** same as P1 until admissibility.
2. **[3] fails admissibility** (missing provenance, forbidden embedded fields, unsupported version, etc.) and emits a **QuarantineCandidate** (J4) to [4].
3. **[4] produces WritePlan{WRITE, QUARANTINE}** (J5).

   * Still deterministic IDs and correlation keys.
4. **[5] writes quarantine record** to `dla/audit/.../quarantine/...` and emits CommitReceipt (J6) to [6].
5. **[6] indexes quarantine** (reason codes, correlation keys). Non-blocking.
6. **[5] emits AckTicket** (J7), allowing [1] to advance offsets.

### Guarantees after P2 completes

* There is durable, queryable evidence of *why* the record was rejected.
* The consumer never wedges on a “poison” decision message.
* Upstream remediation can occur without losing the failure history.

### Failure semantics

* Same as P1: indexing/pointers can fail without blocking checkpointing.
* If quarantine write fails, offsets do not advance (correctness-first), but telemetry makes it visible.

---

## P3 — Duplicate/replay NO-OP path (idempotent ingest)

**Shape:** `1 → 2 → 3 → 4(dedupe hit) → 1(checkpoint)`
(optionally: still emit telemetry)

### Intent

Make at-least-once delivery and replay safe: **duplicate processing produces no new truth** but still advances offsets safely.

### Step sequence

1. **[1]→[2]→[3]** same initial phases (router/admissibility still happen under a ConfigSnapshot).
2. **[4] determines duplicate**: candidate yields the same `(ContextPins, audit_record_id)` that already exists (or is deterministically known to exist).

   * [4] emits **WritePlan{NOOP}** or directly emits an AckTicket path (implementation choice, semantics fixed).
3. **AckTicket to [1]**: [1] advances exclusive-next offsets contiguously.

### Guarantees

* No duplicate canonical/quarantine records are created.
* Replay pressure is visible (NOOP metrics) but harmless.
* Offsets advance, preventing infinite reprocessing loops.

### Failure semantics (important subtlety)

* If dedupe determination requires J8 lookups and [6] is unavailable, [4] must **choose safety**:

  * If it can’t prove duplicate, it should treat it as **a normal candidate** and let [5] enforce idempotency by root-commit existence (or, worst-case, quarantine on ambiguity).
    We do **not** stall ingestion for dedupe uncertainty.

---

## P4 — Corrections/supersedes path (new canonical record replaces prior)

**Shape:** `1 → 2 → 3(pass) → 4(resolve supersedes via 6) → 5(append new canonical) → 6(update “current”) → 1`

### Intent

Allow corrections **without overwriting history**:

* Append a new canonical record
* Link it to the prior via **supersedes**
* Update “current head” view deterministically

### Step sequence

1. **[1]→[2]→[3(pass)]** same as P1; [3] outputs CanonicalAuditCandidate that includes a `supersedes_audit_record_id`.
2. **[4] validates correction semantics** using J8:

   * supersedes target exists
   * same ContextPins scope
   * no “conflict overwrite” ambiguity (if there’s an existing head and you didn’t supersede it → quarantine)
3. If valid: **[4] emits WritePlan{WRITE, CANONICAL, supersedes_link}** to [5] (J5).
4. **[5] appends new canonical record** (never mutates old) and emits CommitReceipt (J6).
5. **[6] applies “current head” update** (derived) and keeps historical intact.
6. **[5] emits AckTicket** (J7) to advance offsets.

### Guarantees

* Historical truth is preserved.
* “Current view” can be computed by following supersedes chain.
* Corrections cannot silently rewrite the past; ambiguity becomes quarantine.

### Failure semantics

* If [4] cannot validate supersedes because [6] is unavailable: **fail closed into quarantine**, not stall.
* If [6] can’t update current view: the new record still exists; current view will lag until reindex/rebuild.

---

## P5 — Outcome linkage path (ActionOutcome)

**Shape:** `1 → 2(route Outcome) → 3(pass/fail) → 4(link-to-anchor via 6) → 5(append outcome-link record) → 6 → 1`

### Intent

Close the accountability loop:

* “We intended X” (from decision)
* “X actually happened” (from AL outcome)
  …and store this **as immutable evidence linkage**, not as mutation of the decision record.

### Step sequence

1. **[1] consumes** an event; **[2] routes** it as `ACTION_OUTCOME` (J2).
2. **[3] checks admissibility** for outcome evidence:

   * envelope valid, ContextPins present, correlation identifiers present (e.g., idempotency_key / decision_id / request_id as per your action semantics)
   * by-ref posture maintained
3. **[4] attempts to link** the outcome to a decision anchor using J8:

   * find decision anchor/head by correlation keys
   * ensure scope matches ContextPins
4. **Two production-valid branches:**

   * **Linked:** [4] emits WritePlan{WRITE, OUTCOME_LINK} → [5] appends outcome-link record → [6] updates views → AckTicket.
   * **Orphan (out-of-order or missing correlation):** [4] emits WritePlan{WRITE, QUARANTINE(or ORPHAN_OUTCOME family)} → [5] writes durable orphan evidence → [6] indexes it → AckTicket.

### Guarantees

* Outcomes are never dropped.
* Linking is deterministic and by-ref.
* Out-of-order arrival does not wedge the pipeline.

### Failure semantics (key production reality)

* If decision record doesn’t exist *yet* (outcome arrives first), we do **not** block consumption:

  * write orphan outcome evidence (quarantine/orphan family)
  * later, an ops/reconciliation pass can create a link record when the decision arrives (still append-only; no mutation)
* If [6] is down, linking might degrade to orphan evidence (fail closed but progress).

---

## One compact view of P1–P5

```
P1 Canonical:  1→2→3(pass)→4→5→6→1   (+8 optional)
P2 Quarantine: 1→2→3(fail)→4→5→6→1
P3 NOOP dup:   1→2→3→4(noop)→1
P4 Correction: 1→2→3(pass)→4(J8)→5→6→1
P5 Outcome:    1→2(outcome)→3→4(J8)→5→6→1   (or orphan→quarantine→…→1)
```

If you want the *next* illumination step after P1–P5, the highest-leverage box to open is **[4] Idempotency+Corrections**, because it’s where P3/P4/P5 branch decisions are made (duplicate vs correction vs orphan), and where the “no drift” semantics are enforced.

---

Locked. Here are **internal paths P6–P10** as **production sequences** across the joins we’ve illuminated — still keeping the *modules* opaque, but making the *flows* + *branch conditions* explicit enough to prevent drift.

I’ll use the same module IDs:

`[1] Ingest&Replay → [2] Router → [3] Admissibility → [4] Idempotency+Corrections → [5] Writer → [6] Views`
Optional: `[8] PointerPub`, `[9] EvidenceVerifier`
Ops: `[7] Ops/Exports`
Rails: `[10] PolicyLens`, `[11] Telemetry`

---

## P6 — Evidence-gated canonical path (when attachments are enabled)

**Shape:** `1 → 2 → (extract refs) → 9 → 3/4 → 5 → 6 → 1`
*(with “optional vs required” branching)*

### Intent

Allow DLA to **attach extra evidence refs** (IG receipts, engine audit_evidence locators, gate receipts) **without scanning** and without turning optional enrichments into a partition wedge.

### Sequence (production)

1. **[1]→[2]**: ingest + parse envelope; router extracts ContextPins and **collects evidence refs** present in payload (receipt_ref/receipt_id, EngineOutputLocator, GateReceipt refs, etc.).
2. **[2]→[9] (J14)**: send **EvidenceVerifyRequest** containing those refs with `required_level = OPTIONAL` or `REQUIRED` as declared by policy snapshot from [10].
3. **[9]** verifies *only*:

   * ref well-formedness + resolvability **by key** (no listing)
   * for engine material: PASS proof admissibility (gate-specific verification)
     and returns `VERIFIED | UNVERIFIABLE_NOW | INVALID` per item (J15).
4. **[2]/[3] incorporate results**:

   * **Optional evidence**:

     * VERIFIED → attach
     * UNVERIFIABLE_NOW/INVALID → omit + record verdict metadata (for transparency)
   * **Required evidence**:

     * VERIFIED → proceed
     * UNVERIFIABLE_NOW/INVALID → route to **quarantine** (never stall)
5. **[3]** runs the normal admissibility checks (completeness/by-ref posture) with the verified attachment set, then emits either J3 (canonical candidate) or J4 (quarantine candidate).
6. **[4]→[5]→[6]→[1]**: same as P1/P2 spine: write durable record, update views/index, checkpoint.

### Invariants (designer pins)

* **Attachments never change truth meaning** — they’re pointers/proofs, not payloads.
* **No scanning**: [9] can only verify what it’s explicitly given (receipt_id/ref, locator, digest, gate receipt).
* **Optional evidence can never block offsets**; required evidence failure becomes quarantine, not stall.

### Failure semantics

* If [9] is down:

  * optional attachments → proceed without attachments + emit telemetry
  * required attachments → quarantine (explicit reason)
* If verification is “eventually consistent” (UNVERIFIABLE_NOW), we still make forward progress; remediation happens via re-emit/correction paths, not by waiting inside a partition.

---

## P7 — Pointer distribution path (optional convenience)

**Shape:** `5(commit) → 8(publish pointer w/ retry) → external subscribers`

### Intent

Let downstream tools react to “audit record written” **without polling** `dla/audit/...`, while keeping pointers strictly **derivative**.

### Sequence

1. **[5] commits** a canonical/quarantine record (root commit object exists).
2. **[5]→[8] (J12)** emits a **PointerTrigger** containing only:

   * record ref + digest
   * `(ContextPins, audit_record_id, record_family)`
   * correlation ids (decision_anchor/event_id)
3. **[8] publishes** a pointer event (idempotent, deterministic `pointer_event_id`) to `fp.bus.audit.v1`.
4. **[8] retries** on failure (J13) with backoff; duplicates are acceptable and dedupable.

### Invariants

* **Emit-after-durable**: pointer never points to non-existent truth.
* **Never gates checkpointing**: P7 cannot block J7.

### Failure semantics

* Pointer bus down → truth still exists; consumers can later replay pointer topic or fall back to deterministic query/index.

---

## P8 — Reindex/rebuild path (derived surfaces only)

**Shape:** `7(trigger) → 6(plan) → 5(read truth under explicit basis) → 6(apply rebuild)`

### Intent

Rebuild `audit_index` and any “current/historical” derived views **without mutating canonical truth**.

### Two production-valid bases (explicitly declared)

* **Truth-basis rebuild** (preferred): rebuild from `dla/audit/...` canonical/quarantine records by explicit manifest / bounded scope.
* **Replay-basis rebuild**: rebuild by replaying EB offsets through the normal pipeline and regenerating derived surfaces (still no truth mutation due to idempotency).

### Sequence (truth-basis version)

1. **[7] starts ReindexRun** with explicit basis:

   * context scope + time window + record families, *and* an explicit enumeration method (manifest or bounded partitioned prefixes).
2. **[7]→[6] (J9)**: request `PlanReindex(basis, scope)`.
3. **[6] returns ReindexPlan**: deterministic work units + **SelectionManifest** (explicit list of record refs or bounded key ranges) + stable ordering rules.
4. **[7]→[5] (J10)**: `ReadRecords(selection_manifest_ref)` — reads only by explicit refs.
5. **[6] applies rebuild** idempotently: upsert index rows, rebuild current-head pointers, rebuild quarantine indices.
6. **[7] writes a ReindexReceipt** (basis echoed, coverage, policy_rev, outputs) + emits telemetry.

### Invariants

* **Derived only**: canonical truth never rewritten.
* **Basis must be explicit** (no silent “scan everything”).
* **Idempotent**: repeat rebuild yields same derived view for same basis.

### Failure semantics

* Missing refs / incomplete basis → fail closed or produce explicit partial receipt (never silently partial).
* DB down → rebuild can be deferred; truth is still intact.

---

## P9 — Deterministic export/slice path

**Shape:** `7(request) → 6(selection plan) → 5(read truth under basis) → 7(write export + receipt)`

### Intent

Create governed, reproducible exports for investigations/offline/governance without turning DLA into a data lake.

### Sequence

1. **[7] receives ExportRequest** with:

   * ContextPins scope
   * time window
   * filters (optional)
   * view selector: `historical` vs `current`
   * explicit basis (retention vs archive; or truth-basis manifest)
2. **[7]→[6] (J9)**: request `PlanExportSelection(filters, view, basis)`.
3. **[6] returns SelectionPlan**:

   * explicit **SelectionManifest** of record refs (or bounded key ranges)
   * deterministic ordering
4. **[7]→[5] (J10)**: `ReadRecords(selection_manifest_ref)` by ref only.
5. **[7] writes export artifacts + ExportReceipt**:

   * artifact refs + digests
   * selection manifest digest
   * policy_rev/profile/build_id
   * exact basis echoed
6. *(optional)* **[7]→[8]**: publish “export complete” pointer event (same derivative rules).

### Invariants

* Same `(pins, window, filters, view, basis)` ⇒ same output selection + ordering.
* Export outputs are immutable once published.

### Failure semantics

* If selection implies unbounded scan → reject; require explicit basis.
* If basis incomplete (retention gap / archive gap) → fail closed or explicitly partial with flagged receipt.

---

## P10 — Controlled replay/backfill path (consumer basis reset)

**Shape:** `7(declare basis) → 1(seek/reset) → run P1/P2/P3 deterministically → 6 rebuild as needed`

### Intent

Support restart, backfill, or replay operations safely:

* reconsume from a declared offset basis
* rely on idempotency to avoid duplicating truth
* optionally rebuild derived surfaces

### Sequence

1. **[7] declares ReplayJob** with:

   * explicit offset vector per partition *(or a time window already resolved into offsets)*
   * mode: `RECONSUME_ONLY` vs `RECONSUME_PLUS_REINDEX`
   * expected coverage (retention vs archive)
2. **[7]→[1] (J11)**: `Pause/Drain` (optional) then `SeekToBasis(basis)`.
3. **[1] replays** events; each event runs through:

   * **P1** (canonical), **P2** (quarantine), or **P3** (NOOP)
     with checkpoint advancement gated by durable commit (J7).
4. If mode includes reindex:

   * **[7] triggers P8** rebuild steps (or [6] applies incremental updates from CommitReceipts).
5. **[7] writes ReplayReceipt**:

   * basis used, coverage achieved, any gaps, policy_rev in force.

### Invariants

* Replay never mutates canonical truth (duplicates become NOOP).
* Basis is explicit and auditable.
* Offsets remain exclusive-next and monotonic in meaning.

### Failure semantics

* Basis outside retention + archive coverage unknown → reject/fail closed (no pretending completeness).
* Writer outages halt checkpointing (correctness first); lag becomes observable and can feed degrade/ops decisions.

---

## Tiny “at-a-glance” map

```
P6 Evidence-gated:  1→2→9→3/4→5→6→1
P7 Pointers:        5→8(retry)→audit topic
P8 Reindex:         7→6(plan)→5(read truth)→6(apply)
P9 Export:          7→6(select)→5(read)→7(write export+receipt)
P10 Replay:         7→1(seek)→(P1/P2/P3)*→(P8 optional)
```

If you want the next “step inside” after these paths, the most leverage comes from opening **[7 Ops/Exports]** (because P8–P10 depend on how you express/record a “basis” cleanly without drifting into implicit scans).

---

Yep — we’ll illuminate **internal loops L1–L3** as **production cycles** (why they exist, what edges they traverse, what invariants they enforce, and how they fail safely). Modules remain opaque; the loop semantics become authoritative.

---

## L1 — Crash / restart continuity loop (the fundamental loop)

### What this loop guarantees

In production, DLA can crash/restart at any moment and still preserve:

* **no lost audit truth** (canonical or quarantine),
* **no duplicated audit truth**, and
* **deterministic recovery** based on EB offsets.

### The loop (cycle narrative)

```
[1] consumes from EB (partition/offset)
  → [2]/[3]/[4] classify + decide canonical vs quarantine vs noop
  → [5] writes durable truth (root commit object)
  → [5] emits AckTicket (J7) so [1] advances exclusive-next checkpoint

(crash can occur anywhere)

Restart:
[1] resumes from last persisted checkpoint
  → re-consumes some already-processed events (at-least-once)
  → [4]/[5] dedupe causes NO-OP (P3) or commit-key already exists
  → [5] re-emits AckTicket
  → checkpoint catches up and progresses
```

### Two “crash windows” that matter (designer authoritative)

1. **Crash after durable commit but before checkpoint**

* On restart: event is reprocessed
* Outcome: NO-OP (because truth already exists)
* Then checkpoint advances.
  ✅ Safe and expected.

2. **Crash before durable commit**

* On restart: event is reprocessed
* Outcome: commit occurs then checkpoint advances.
  ✅ Safe and expected.

### Non-negotiable invariants (why this loop works)

* **Write-then-checkpoint:** J7 must only fire after a durable commit (or proven NO-OP).
* **Exclusive-next offsets:** checkpoint semantics are “next offset to read.”
* **Idempotency:** duplicates/replays must produce NO-OP (keyed by `(ContextPins, audit_record_id)`), not duplicate records.

### Failure semantics

* If the writer/object store is down, **AckTicket cannot be produced** → offsets do not advance → lag grows → telemetry alerts → ops can drain/pause/replay later.
* If indexing/view update fails, it **does not** block checkpointing (truth already durable); ops can reindex (P8).

---

## L2 — Evidence verification retry loop (eventual consistency loop)

### What this loop guarantees

Optional (or policy-required) evidence attachments — IG receipts, engine audit_evidence locators, gate receipts — can be **verified without scanning** and without turning “not yet available” into either:

* silent corruption (“pretend it’s valid”), or
* pipeline wedging (“wait forever”).

### The loop (cycle narrative)

```
[2]/[3]/[4] extract evidence refs → [9] verification request (J14)
[9] attempts verification:
   - if VERIFIED → return to [3]/[4] (J15) and proceed canonical path
   - if INVALID → return to [3]/[4] and quarantine (required) or omit (optional)
   - if UNVERIFIABLE_NOW → [9] schedules retry/backoff and loops
```

### The key “third truth value” (designer pin)

`UNVERIFIABLE_NOW` is distinct from `INVALID`.

* **UNVERIFIABLE_NOW** means: *evidence might become verifiable later* (object store replication lag, transient auth issue, delayed receipt write).
* **INVALID** means: *it will never be admissible* (digest mismatch, PASS missing, wrong scope, malformed locator, forbidden access).

### How this loop terminates (production-safe endings)

* **Verified path:** evidence becomes VERIFIED → canonical candidate proceeds (P6 → P1).
* **Timeout/expiry path:** after a policy-defined retry budget/window, if evidence is still UNVERIFIABLE_NOW:

  * if evidence is **required** → quarantine (“required evidence not verifiable within window”)
  * if evidence is **optional** → proceed without attachment but record verdict metadata.

### Non-negotiable invariants

* **No scanning:** retries operate on the same explicit refs/ids.
* **No checkpoint coupling:** evidence verification must not gate offset advancement indefinitely. It resolves by either attach/omit/quarantine within a bounded policy window.
* **Gate-specific engine proof:** engine evidence requires PASS verification using the gate map; no “generic sha256 guess.”

### Failure semantics

* If verifier is down: optional evidence is omitted; required evidence forces quarantine (never stall).
* If a required evidence ref is present but broken: quarantine (do not silently drop the claim).

---

## L3 — Pointer publish retry loop (optional distribution loop)

### What this loop guarantees

Pointer events are a **convenience distribution plane** that must be:

* **retriable**,
* **idempotent**, and
* **never able to corrupt or gate audit truth**.

### The loop (cycle narrative)

```
[5] commits durable truth → triggers [8] (J12)
[8] attempts publish pointer event to fp.bus.audit.v1:
   - success → done
   - failure → retry/backoff (J13) → attempt again
```

### Deterministic pointer identity (designer pin)

Pointer events have a deterministic `pointer_event_id` derived from:
`(ContextPins, audit_record_id, record_family)`
So retries and replays don’t create “new pointers,” just duplicates of the same logical pointer.

### Non-negotiable invariants

* **Emit-after-durable:** pointers only reference durable truth.
* **Never gates checkpointing:** pointer failures do not affect J7.
* **Subscribers must tolerate duplicates:** at-least-once semantics apply.

### Failure semantics

* If pointer topic is down: pointers are delayed or absent, but the record is still readable from `dla/audit/...` or discoverable via query/index; ops sees pointer failures via telemetry and can recover by replaying pointer topic once back up.

---

## Quick “why these loops matter” summary

* **L1** makes DLA *safe under reality* (crashes, replays, duplicates).
* **L2** makes optional/required evidence attachments *safe under eventual consistency* (no lying, no wedging).
* **L3** makes distribution *nice-to-have, never truth*.

If you want, the next internal loops to illuminate are **L4–L6** (current-view stabilization, ops governance cycle, policy update cycle), but L1–L3 are the “minimum production survival loops.”

---

Yep — **L4–L6** are the “non-survival” loops that make DLA **stable, operable, and governable** in production (beyond crash safety, evidence retry, and pointer retries).

I’ll keep **modules opaque**, and I’ll express each loop as: **why it exists → the cycle → invariants → failure semantics**.

---

## L4 — Current-view stabilization loop (supersedes → head → future reads)

**What this loop guarantees:** “current” is well-defined and converges, while **history remains append-only**.

### The loop (cycle narrative)

```
(1) A new canonical record arrives that changes lineage (correction / outcome link)
    [1]→[2]→[3]→[4]

(2) [4] resolves lineage state via [6] (J8):
    - does target exist?
    - what is current head for this decision_anchor?
    - is this correction well-formed (explicit supersedes)?

(3) Commit happens:
    [4]→[5] append new immutable record (J5)
    [5]→[6] commit receipt (J6)

(4) [6] advances “current view”:
    - head pointer / derived current view is updated (idempotent)
    - historical view retains everything

(5) Future J8 lookups now return the updated head
    [4]↔[6] (J8) for later events
```

### Invariants (designer pins)

1. **Single-head semantics per decision_anchor (linear history, not branching).**
   If a candidate *does not* explicitly supersede the **current head**, it is **not** allowed to become the new head (it becomes quarantine for ambiguity/conflict).
   This prevents “forked current truth,” which is a drift magnet.

2. **Emit new truth, never rewrite old truth.**
   Head changes are derived from the supersedes chain; the prior canonical record remains immutable.

3. **“Current” must remain computable from canonical truth even if indices lag.**
   Index/view failure can delay “current” surfaces, but it cannot create a different truth.

4. **Fail-closed on unverifiable supersedes, but don’t wedge.**
   If J8 can’t validate a supersedes target (unavailable), we quarantine the would-be correction rather than stall ingestion.

### Failure semantics (how it behaves under reality)

* **Index lag / DB down:** canonical record still commits; “current view” may lag until reindex/rebuild (P8).
* **Race between two corrections:** first one that validly supersedes the then-current head can commit; any later correction that doesn’t supersede the new head is quarantined as a conflict (linearization).
* **Out-of-order outcomes:** outcome-link may initially land as orphan/quarantine; later reconciliation can append a link record (still append-only).

---

## L5 — Ops governance loop (run/operate controls → actions → telemetry → adjustment)

**What this loop guarantees:** DLA can be *run like a production service* without hidden scans, silent backfills, or truth mutation.

### The loop (cycle narrative)

```
(1) Ops/Gov initiates an action under policy:
    [7 Ops] (export | reindex | retention | replay | drain)

(2) [7] asks [6] for deterministic plans (J9):
    - selection manifests
    - rebuild plans
    - explicit ordering
    - explicit basis

(3) [7] executes via:
    - [1] for pause/drain/seek/replay (J11), and/or
    - [5] for read-by-ref + write export artifacts/receipts (J10), and/or
    - [6] apply derived view rebuilds

(4) [11 Telemetry] reports:
    - progress, coverage, failures, lag, partiality

(5) Ops adjusts:
    - refine basis/scope
    - retry/rollback
    - schedule follow-up reindex
    - tighten/loosen knobs via policy revision (L6)
```

### Invariants (designer pins)

1. **Every ops action is basis-driven (explicit).**
   No “scan everything.” Even “full rebuild” must specify an explicit enumeration basis (manifest / bounded window / declared scope).

2. **Canonical truth is never rewritten by ops.**
   Ops may rebuild **derived** surfaces and write **new** export artifacts + receipts, but cannot mutate canonical audit records.

3. **Receipts are first-class.**
   Every export/reindex/replay/retention action produces a durable receipt that echoes: basis, scope, policy_rev/profile/build_id, and coverage.

4. **Ops does not bypass the ingest correctness latch.**
   Replays rely on idempotency + write-then-checkpoint semantics (L1), not on “manual corrections.”

### Failure semantics

* **DB/index unavailable:** ops can still read canonical truth and produce exports; view rebuild may be deferred.
* **Partial coverage (retention gap / archive gap):** ops action must fail closed or explicitly produce a “partial” receipt—never silently partial.
* **Writer outage:** ops drain/replay cannot claim completion; telemetry must show “stuck before durable commit.”

---

## L6 — Policy/profile update loop (new rev → consistent application → visible effects)

**What this loop guarantees:** outcome-affecting rules change *cleanly*, *visibly*, and *without mixed semantics inside a single record*.

### The loop (cycle narrative)

```
(1) A new policy/profile snapshot is published
    [10 PolicyLens] fetches and validates it

(2) [10] distributes the new ConfigSnapshot to modules (J16)
    - swap is atomic
    - each processing unit (event/batch/job) uses exactly one snapshot

(3) Processing continues under the new rev:
    - admissibility decisions
    - quarantine thresholds
    - attachment requirements
    - pointer enablement
    - export permissions

(4) [11 Telemetry] makes the change visible (J17)
    - policy_rev tags on all key signals
    - quarantine reason distribution changes are observable

(5) Ops/governance reacts:
    - accept (promote)
    - adjust thresholds/rules (new rev)
    - rollback (previous rev)
```

### Invariants (designer pins)

1. **Single-snapshot per unit of work.**
   No event is evaluated half under rev A and half under rev B.

2. **Last-known-good on refresh failure.**
   Runtime refresh failure does not silently fall back to defaults; it holds last-known-good and emits “config stale” telemetry.

3. **Policy rev is always recordable/observable.**
   Every canonical/quarantine record and every pointer/receipt must carry the policy_rev/profile/build_id context (so “what rules were in force?” is always answerable).

4. **Policy changes never become hidden semantic forks across environments.**
   Local/dev/prod differences are expressed as different *profiles/revs*, not code branches; the mechanism is identical.

### Failure semantics

* **No valid snapshot at startup:** DLA fails closed (does not run).
* **Refresh failure:** continue on last-known-good; raise alerts; ops may drain/restart if staleness exceeds tolerance.
* **Bad policy rev causes quarantine storm:** that is exactly what this loop is for—telemetry shows it, and ops rolls back/promotes a fix.

---

### Quick “loop adjacency” map

```
L4: [4]↔[6] → [5] → [6] → [4]   (supersedes/head stabilization)
L5: [7]→[6]/[1]/[5] → [11] → [7] (operate/rebuild/export/replay governance)
L6: [10]→(all) → [11] → [7]/[10] (policy rev change → visible effects → adjustment)
```

If you want to keep the illumination disciplined: the clean next “open a box” target is **[4] Idempotency+Corrections**, because L4 depends on its exact conflict rules; then **[7] Ops/Exports**, because L5 depends on how you represent “basis + receipts” without scanning.

---

Yep — we should **pin the non-joins** now. These are the *forbidden edges / anti-paths* that must **not** appear (even accidentally) as we go deeper, because they violate the platform boundary rules or create drift.

I’m going to declare the following as **authoritative “NO edges”** for DLA.

---

## 1) Platform-level non-joins around DLA

### N1 — No bypass of IG→EB into DLA

There is **no direct producer→DLA write path** for decisionable events.
If it can influence decisions/audit/labels/training facts, it enters **only through IG→EB** (“one front door”).

**So forbidden:** `DF → DLA (direct)`, `AL → DLA (direct)`, `Engine → DLA (direct traffic)`.
**Allowed instead:** those produce/emit into `fp.bus.traffic.v1` via IG, and DLA consumes from EB.

---

### N2 — DLA does not call OFP / IEG / Registry / DL at ingest time

DLA is a **flight recorder**; it records provenance tokens that DF already emits.
DF is the component that calls OFP/IEG/DL/Registry; DLA must not re-resolve or recompute.

**Forbidden:** `DLA → OFP snapshots`, `DLA → IEG query`, `DLA → Registry “active bundle”`, `DLA → DL posture`.
**Allowed instead:** DLA stores `feature_snapshot_hash`, `input_basis`, `graph_version`, degrade posture, bundle ref that DF included.

---

### N3 — DLA does not execute actions

AL is the **only executor**.

**Forbidden:** `DLA → AL (execute)` or any “audit-triggered side effect” path.
**Allowed instead:** Case/DF produce ActionIntents → AL executes → ActionOutcomes; DLA records evidence.

---

### N4 — DLA does not write labels / become truth source for labels

Label Store is the **single truth writer** for labels; DLA is evidence.

**Forbidden:** `DLA → Label Store (write truth)` or “audit implies truth”.
**Allowed instead:** Case Workbench uses DLA evidence → writes LabelAssertions to Label Store.

---

### N5 — DLA never treats engine surfaces as traffic, and never “discovers” engine artifacts

Only `business_traffic` is traffic. `truth_products/audit_evidence/ops_telemetry` are **not traffic**, and engine artifacts are **not discoverable by scanning**; they must be referenced + PASS-proven.

**Forbidden:** “read engine truth_products as hot-path input”, “ingest audit_evidence into EB as if it were traffic”, “scan engine/… for latest”.
**Allowed instead:** DLA can store **by-ref pointers** to engine audit evidence *only when explicitly referenced with PASS proof*.

---

### N6 — DLA does not patch/correct engine facts

Engine outputs are immutable per pinned identity; corrections happen as new artifacts/identities or new runs/join surfaces.

**Forbidden:** “DLA fixes engine world” or “patch audit evidence in place.”
**Allowed instead:** corrections are new DLA records via **supersedes chain** (for audit), and new engine artifacts/runs (for world).

---

## 2) Internal non-joins inside DLA (between L1 modules)

### N7 — Derived views/index never gate the truth spine

Indexing/view updates must **not** block checkpoint advancement. Truth is `dla/audit/...`; `audit_index` is derivative/rebuildable.

**Forbidden internal dependency:** `[6 Views] must succeed before [1] can checkpoint.`
**Allowed:** `[5 Writer] durable commit → checkpoint; [6] may lag and be rebuilt (P8).

---

### N8 — Pointer publishing never gates checkpointing or truth

Pointers are optional convenience; failure to publish must not stall the consumer.

**Forbidden:** `[8 PointerPub] failure → block [1]/[5] progress.`
**Allowed:** pointer retry loop is isolated; truth remains readable by-ref.

---

### N9 — Evidence verification is not a scanner and not a hard dependency unless policy says so

Engine artifacts must not be “found”; only verified from explicit refs + PASS.

**Forbidden:** `[9 EvidenceVerifier] lists buckets / discovers refs / blocks indefinitely.`
**Allowed:** keyed verification only; if required evidence can’t be verified, route to quarantine (don’t wedge).

---

### N10 — Telemetry never becomes a control input inside DLA

Telemetry is output; DLA does not run its own degrade logic. Degrade posture comes from DL and is recorded.

**Forbidden:** `[11 Telemetry] drives admissibility or checkpoint policy.`
**Allowed:** telemetry reports lag/quarantine/write failures; ops responds outside the data-plane spine.

---

### N11 — Ops cannot mutate canonical audit truth

DLA canonical records are immutable; ops can rebuild derived surfaces, export, replay—never overwrite canonical.

**Forbidden:** `[7 Ops] → delete/overwrite/patch existing canonical record.`
**Allowed:** new records (supersedes), rebuild index, write export artifacts + receipts.

---

### N12 — audit_record_id must not depend on ephemeral transport fields

Canonicalization excludes ephemeral fields (e.g., ingestion attempt ids); audit identity must be stable under replay and across environments.

**Forbidden:** hashing includes partition/offset or ingest attempt ids.
**Allowed:** store EB coords as evidence, but don’t let them drive identity.

---

## 3) A few “anti-paths” to keep in mind (common drift traps)

* **“Index is down → stop consuming EB”** (forbidden; truth spine must continue).
* **“Pointer topic is down → treat audit as unavailable”** (forbidden; pointers are convenience).
* **“Need engine evidence → scan engine/… outputs”** (forbidden; explicit refs + PASS only).
* **“Use truth_products to make decisions”** (forbidden unless explicitly re-designated; default is never).

---

If you want, next we can take these non-joins and stamp them into a compact **“DLA boundary ruleset”** (10–15 lines) that we keep at the top of the next deep-dive section so every inner-module decision is checked against it.

---

## USER: PAUSE FOR REFLECTION

Here’s the “design anchor” for **Decision Log & Audit Store (DLA)** as we’ve established it in this brainstorm — so we can carry the shape forward without drift when we step inside the boxes.

---

## 1) Where DLA sits in the platform network

**DLA’s role (authoritative):** the platform’s **immutable flight recorder** for decisioning lineage — it makes the system reconstructable (“what we knew, why we acted, what we did”), without becoming a second data lake.

**Planes & trust boundaries (pinned):**

* **IG → EB is the only front door** for decisionable traffic.
* **DLA consumes from EB** (replayable facts), **never direct writes** from DF/AL/Engine.
* DLA writes **append-only truth** to `dla/audit/...` and (optionally) derived `audit_index` + pointer events.

**Authority boundaries (pinned):**

* **IG** = admission truth (admit/dup/quarantine + receipts)
* **EB** = durable append + replay coords
* **DF** = decisions + provenance emission
* **AL** = side-effect execution + immutable outcomes
* **Registry/OFP/IEG/DL** = their own truths
* **DLA** = audit truth (canonical + quarantine), not a resolver/validator/executor

---

## 2) Outer joins/paths/loops we locked (production-ready set)

### Mandatory joins

1. `EB(fp.bus.traffic.v1) → DLA` ingest DecisionResponse + ActionOutcome
2. `DLA → object://dla/audit/...` canonical + quarantine append-only truth
3. `DLA → db://audit_index` derived query surface (rebuildable, non-truth)
4. `Case Workbench → DLA` read evidence by-ref
5. `DLA → Observability` OTLP metrics/traces/logs

### Optional joins (allowed, never redefining truth)

* `DLA → fp.bus.audit.v1` pointer events (derivative convenience)
* `IG receipts/quarantine refs → DLA` evidence augmentation (by-ref only; no scanning)
* `Engine audit_evidence → DLA` forensics refs (by locator + PASS only)

### Core paths/loops

* **Hot path:** DecisionResponse → DLA canonical audit record
* **Quarantine path:** incomplete/invalid provenance → quarantine record (no half-truth)
* **Corrections path:** append-only **supersedes chain**; “current vs historical” semantics
* **Outcome closure path:** ActionOutcome linked into lineage (or orphan evidence)
* **Operational continuity:** replay/restart safe via idempotency + checkpoint gating
* **Ops/gov:** reindex/export/replay are **basis-driven**, receipted, never silent scans
* **Human loop:** evidence → case timeline → manual actions → outcomes → more evidence → labels become truth only in Label Store
* **Learning/rollout loop:** evidence+labels → offline → MF → Registry → new DF provenance → DLA records it
* **Degrade loop:** degrade posture is explicit, enforced, and recorded in audit provenance

---

## 3) Environment ladder implications (what can/can’t vary)

**Invariant across local/dev/prod:** same graph + same semantics.

* DLA remains “EB consumer → append-only truth writer” even if collapsed into one process locally.
* Replay semantics stay offset/watermark driven (exclusive-next meaning).
* Append-only + supersedes + quarantine + idempotency mean the same everywhere.
* Promotion = **profile selection**, not code forks.

**Allowed knobs (profile differences):**

* retention/archival horizon, access strictness, pointer enablement, export permissions, evidence-attachment strictness (but only via versioned policy revs), throughput sizing, telemetry sampling/verbosity.

---

## 4) First illumination layer inside DLA: internal subnetworks (still opaque)

We pinned these L1 internal boxes (production-shaped):

**Core spine**

1. **Ingest & Replay Control**
2. **Envelope & Type Router**
3. **Audit Admissibility Gate**
4. **Idempotency & Corrections Manager**
5. **Append-only Persistence Writer**
6. **Query & View Builder**

**Ops/governance**
7) **Ops / Retention / Export Orchestrator**

**Optional**
8) **Pointer Publisher**
9) **Evidence Attachment Verifier**

**Cross-cut**
10) **Policy/Profile & Schema Lens**
11) **Observability & Telemetry**

---

## 5) Internal joins/paths/loops we illuminated (the inner network shape)

### Internal joins (high-level)

* **J1–J4:** ingest → parse/route → admissibility → canonical-vs-quarantine candidates
* **J5–J7:** write-plan → durable commit → views receipt → checkpoint ack gating
* **J8–J11:** lookup/control plane (existence/head/supersedes; reindex/export plans; ops replay controls)
* **J12–J15 (optional):** pointer emission & retries; evidence verification requests/verdicts
* **J16–J17:** config snapshot distribution + telemetry emission (never gates correctness)

### Internal paths P1–P10 (production flows)

* P1 canonical write, P2 quarantine write, P3 dedupe NOOP
* P4 correction/supersedes, P5 outcome linkage
* P6 evidence-gated (optional/required), P7 pointers
* P8 reindex, P9 deterministic export, P10 controlled replay/backfill

### Internal loops L1–L6 (why the system survives reality)

* **L1** crash/restart continuity (write-then-checkpoint + idempotency)
* **L2** evidence verification retry (VERIFIED/UNVERIFIABLE_NOW/INVALID with bounded policy)
* **L3** pointer publish retry (never gates truth)
* **L4** current-head stabilization (no ambiguous forks)
* **L5** ops governance cycle (basis-driven actions + receipts + telemetry feedback)
* **L6** policy rev update loop (single-snapshot per unit of work; visible changes)

---

## 6) “Non-joins” we explicitly forbade (drift killers)

These are now hard constraints as we go deeper:

* No **producer → DLA direct writes** (no bypass of IG→EB).
* No DLA “resolver” behavior (no calling OFP/IEG/Registry/DL during ingest).
* No DLA execution or label writing (AL executes; Label Store is truth for labels).
* No treating engine `truth_products/audit_evidence` as traffic; no scanning engine artifacts.
* No coupling checkpointing to index updates or pointer publishing.
* No scanning for ops actions: reindex/export/replay must be **basis-driven** with receipts.
* `audit_record_id` must not depend on ephemeral transport fields (partition/offset/time).

---

## 7) What we intentionally left open (safe to decide inside the boxes)

We deliberately didn’t over-bind:

* exact canonicalization/serialization for `audit_record_id`
* how “current view” is materialized (computed vs materialized)
* final quarantine reason vocabulary
* export formats/landing details
* detailed retention durations and archive wiring mechanics

These don’t change the network; they’re implementation-shaped choices once we open each box.

---

If we carry only one mental model forward: **DLA is a replay-safe, append-only recorder whose correctness is anchored on (a) write-then-checkpoint, (b) idempotency, (c) explicit supersedes, (d) quarantine-not-half-truth, and (e) basis-driven ops — with all optional enrichments never allowed to redefine truth or stall the spine.**

---

Yep — this *is* the right moment to pin the **deployment / environment-ladder posture** for DLA *before* we open any of the inner boxes. I’ll keep it “production-shaped but not over-binding,” and I’ll separate **non-negotiable invariants** from **profile knobs**.

---

## 1) Deployment-unit shape for the DLA inner network

### DU-1: **DLA Writer (always-on consumer/writer)**

This is the core runtime unit in dev/prod (local can collapse, but the role stays the same). It owns the hot spine modules: ingest/replay → route → admissibility → idempotency/corrections → append-only writes → derived views/index.

**Pin:** DU-1 must be able to keep writing canonical/quarantine truth even if “nice-to-have” surfaces (index/pointers) are degraded. (Truth first; derived surfaces can be rebuilt.)

### DU-2: **DLA Ops Jobs (on-demand / scheduled)**

A separate entrypoint/runtime shape for:

* deterministic **reindex/rebuild** of derived surfaces,
* deterministic **exports/slices**,
* controlled **replay/backfill** operations (basis-driven, receipted).

**Pin:** Ops jobs never mutate canonical audit truth; they only (a) read immutable truth by explicit basis and (b) write new export/reindex artifacts + receipts.

### Optional DU-3: **Pointer Publisher (either inside DU-1 or as a small sidecar)**

Pointer emission to `fp.bus.audit.v1` is allowed as a convenience, but must never gate the writer.

### Optional DU-4: **Evidence Verifier (library inside DU-1, or separate helper)**

If you enable IG receipt refs / engine audit_evidence attachments, verification must remain **keyed** (no scanning) and must fail into **quarantine/omit**, not stall ingestion.

---

## 2) Stateful substrate posture (what DLA must persist, and where)

### Primary truth (must persist)

* **Object store:** `dla/audit/...` immutable audit records (canonical + quarantine). This is the DLA “flight recorder” truth.

### Derived / rebuildable (nice-to-have, but practical)

* **DB:** optional `audit_index` (search/index/current-head pointers). Treat as **derived** and rebuildable from immutable truth and/or EB replay basis.

### Operational continuity state (must persist for smooth ops)

* **Consumer checkpoints:** DLA must persist its applied offsets (exclusive-next semantics) somewhere durable (DB or object-store receipts). Losing checkpoints isn’t “data loss” (replay is safe), but it becomes an explicit ops event (replay basis is declared).

**Pin:** `audit_record_id` / canonical identity must not depend on ephemeral transport coordinates (partition/offset) — those are evidence, not identity.

---

## 3) Environment ladder invariants for DLA (must not change across local/dev/prod)

These are the “no three platforms” rules applied to DLA:

* **Same graph and trust boundaries:** DLA consumes from the admitted fact plane (EB), not direct writes.
* **Same rails/join semantics:** canonical envelope boundary, ContextPins discipline, append-only + supersedes, quarantine-first, idempotency under at-least-once.
* **Same meaning of time:** domain time = `ts_utc`; ingestion time belongs to IG receipts; DLA must not collapse these.
* **Promotion = profile selection + policy revision, not code forks.**

---

## 4) The profile knobs you *do* want (per environment)

These are the knobs Codex should implement as config/profile, not code forks:

### Policy knobs (outcome-affecting; versioned + auditable)

* **Audit completeness strictness** (what makes canonical vs quarantine).
* **Evidence attachment requirement** (IG receipts optional vs required; engine evidence optional vs required).
* **Supersedes/correction acceptance rules** (still append-only; just strictness/guards).
* **Export permission & allowed scopes** (who can export, what windows, what filters).
* **Pointer emission enablement** (on/off).

### Wiring knobs (non-semantic)

* consumer concurrency, batch sizes, retry/backoff,
* object store endpoints/prefixes,
* DB DSN/connection pool,
* OTLP endpoint + sampling, log verbosity.

**Pin:** Every record/receipt/telemetry should carry `policy_rev + profile_name + build_id` so “what rules were in force?” is always answerable.

---

## 5) Operational readiness expectations for DLA (what “production-shaped” means)

### What must keep the spine safe

* **Write-then-checkpoint:** only advance offsets after durable canonical/quarantine commit exists.
* **Index/pointer failure must not stall truth writing** (it triggers telemetry + later reindex).
* **Replay/backfill is always basis-driven and receipted** (never silent).

### Observability baseline (must exist even locally, just lower scale)

At minimum: consumer lag per partition, canonical vs quarantine rates (by reason), writer failure rate/latency, index backlog, pointer publish failures (if enabled).

---

## 6) “Golden flow” deployment check (the anchor test)

Before opening nodes, we should keep one acceptance mental model: the local “prod-shaped” stack must run the end-to-end golden flow **SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA** (plus at least one label loop and one registry resolution).

That’s the deployment reality check that prevents designing an inner DLA network that only works in isolation.

---

Yes — once we start illuminating nodes, we **must not change** the network we’ve pinned; we’re only revealing the machinery that makes the already-defined joins/paths/loops possible.

## The nodes (internal subnetworks) we pinned

Core spine:

1. **[1] Ingest & Replay Control**
2. **[2] Envelope & Type Router**
3. **[3] Audit Admissibility Gate**
4. **[4] Idempotency & Corrections Manager**
5. **[5] Append-only Persistence Writer**
6. **[6] Query & View Builder**

Ops / governance:
7) **[7] Ops / Retention / Export Orchestrator**

Optional:
8) **[8] Pointer Publisher**
9) **[9] Evidence Attachment Verifier**

Cross-cut rails (we can touch as needed, but they’re not “pipeline nodes”):
10) **[10] Policy/Profile & Schema Lens**
11) **[11] Observability & Telemetry**

## The order I want us to illuminate (to minimize drift)

1. **[5] Append-only Persistence Writer**
   Sets the “durable commit boundary” (root commit object, write-then-checkpoint), which everything else depends on.

2. **[1] Ingest & Replay Control**
   Locks exclusive-next checkpoint semantics and crash/replay behavior around the writer.

3. **[4] Idempotency & Corrections Manager**
   Defines duplicate NO-OP, conflict vs supersedes, and the “current head” semantics that drive J8/L4.

4. **[3] Audit Admissibility Gate**
   Formalizes canonical vs quarantine decisions and completeness policy enforcement (without becoming a resolver).

5. **[2] Envelope & Type Router**
   Keeps envelope parsing/versioning and event family routing clean and fail-closed.

6. **[6] Query & View Builder**
   Derived surfaces, rebuildability, and the keyed lookup semantics supporting J8/J9.

7. **[7] Ops / Retention / Export Orchestrator**
   Basis-driven reindex/export/replay controls + receipts (P8–P10, L5).

8. **[9] Evidence Attachment Verifier** *(optional)*
   Keyed verification + PASS discipline for engine/receipt attachments (P6, L2).

9. **[8] Pointer Publisher** *(optional)*
   Derivative distribution plane (P7, L3).

10. **[10] Policy/Profile Lens** and **[11] Telemetry**
    We’ll weave these in as we illuminate each node (they touch everything), but we don’t need to “open” them first.

If you want, we can start immediately with **[5] Writer** and treat it as an opaque box one level deeper (internal subnodes still opaque) exactly like we did for the vertex.

---

Alright — we’re **opening node [5] (Append-only Persistence Writer)** and exposing the **machinery inside it**. We’ll keep it *design-level* (not a binding spec), but I’ll be concrete enough that Codex can implement without inventing semantics.

Below, **[5] is no longer opaque**; its *internal subnetworks* are still “boxes,” but we’ll fully define how they interact and what they guarantee.

---

## [5] Writer’s mission in one sentence

**Turn a WritePlan into durable, immutable audit truth** (canonical or quarantine) with a **single commit boundary** (“root commit object”), then emit:

* **CommitReceipt → [6]** (derived views may lag),
* **AckTicket → [1]** (checkpoint advances only after durable truth),
* *(optional)* **PointerTrigger → [8]** (distribution convenience, never gating).

---

## [5] Internal subnetworks (machinery)

### 5A) Plan Intake & Validation

* Validates the incoming **WritePlan** from [4].
* Ensures the plan is self-contained (Writer must not “decide” anything).
* Classifies plan_kind: `WRITE | NOOP`.

### 5B) Deterministic Key Resolver

* Produces the exact immutable object keys for:

  * the **root commit object** (the commit boundary),
  * any **sub-objects** (record bodies, evidence capsules, attachments).
* Keys are derived from stable identifiers (ContextPins, audit_record_id, record_family, etc.), **never from ephemeral transport fields** (partition/offset, ingest timestamps).

### 5C) Idempotency Guard (Commit Existence Gate)

* Determines if the plan is already committed:

  * “Does the root commit object exist?”
* This is the writer’s primary idempotency latch.
* For NOOP plans, it **verifies** the root exists before allowing ack.

### 5D) Staging Writer (Sub-object Materializer)

* Writes all non-root objects first (if the plan includes them).
* Examples:

  * canonical record body object(s),
  * quarantine capsule object(s),
  * attachment pointer bundles (by-ref only),
  * optional “evidence payload blob” (only if policy permits; otherwise never).
* Writes are **idempotent** (same key => same bytes).

### 5E) Digest & Integrity Engine

* Computes digests for everything written (or verifies provided digests).
* Ensures the root commit object can include a complete “what was committed” manifest.

### 5F) Root Commit Builder & Finalizer

* Builds the **root commit object** that references all sub-objects + digests + metadata.
* Writes the root object **last** and **conditionally** (no overwrite).
* **Root commit existence = durability truth** for that audit record.

### 5G) Receipt & Fan-out Emitter

After root commit success:

* emits **CommitReceipt → [6]**
* emits **AckTicket → [1]**
* optionally emits **PointerTrigger → [8]**
* always emits telemetry signals to [11]

### 5H) Retry / Backoff & Failure Classifier

* Central place for retry policy (object store transient faults, timeouts).
* Distinguishes:

  * **transient** (retryable),
  * **permanent** (plan invalid),
  * **integrity** (corruption / digest mismatch) = fail-closed.

### 5I) Staging Garbage Collector (optional, but realistic)

* Cleans up orphaned staging objects (written before a crash, never got a root commit).
* Must be **basis-driven** (bounded by staging prefix + time partitions), and **must never touch committed truth**.

---

## Internal joins inside [5] (edges)

```
[5A Plan Intake]
    -> [5B Key Resolver]
    -> [5C Idempotency Guard] --(already committed?)--> [5G Fan-out]   (NOOP or replay)
    -> [5D Staging Writer] -> [5E Digest Engine]
    -> [5F Root Finalizer] --(root committed)--> [5G Fan-out]
                          --(failed)----------> [5H Retry/Fail]
```

---

## The commit protocol (the core “machinery law”)

### The one law we pin

**A record is committed iff the root commit object exists.**
Everything else is staging until the root exists.

### Path W-WRITE (canonical or quarantine)

1. **Validate plan** (5A)
2. **Resolve keys** (5B)
3. **Check root existence**

   * if root exists → treat as already committed (skip to fan-out)
4. **Write sub-objects** (5D)
5. **Compute/verify digests** (5E)
6. **Write root commit object LAST** (5F)

   * must be a conditional write (“create if absent”)
7. **Emit outputs** (5G)

   * CommitReceipt → [6] (non-gating)
   * AckTicket → [1] (gating)
   * PointerTrigger → [8] (optional)

### Path W-NOOP (duplicate)

1. **Validate plan** (5A)
2. **Resolve root key** (5B)
3. **Verify root exists** (5C)

   * if root exists → AckTicket to [1] + (optional) emit receipt/pointer for idempotent recovery
   * if root missing → **integrity/plan violation** (fail-closed; do not ack; alert)

> This makes duplicates safe **even if [6] is down**, and ensures NOOP isn’t used to “skip work” incorrectly.

---

## What the root commit object contains (conceptual, not a spec)

The root commit is the durable, immutable “receipt of truth.” It should include:

* identifiers: `context_pins`, `audit_record_id`, `record_family`
* correlation keys: `decision_anchor`, `event_id` (if present)
* policy context: `policy_rev`, `profile_name`, `build_id`
* a manifest of sub-objects:

  * `object_ref` + `digest` + `role` (canonical_body, quarantine_capsule, attachment_bundle, etc.)
* evidence pointers:

  * EB coords as evidence (`stream, partition, offset`) are allowed *inside* the record
* optional: commit timestamp (fine to include, **but never used to derive audit_record_id**)

---

## [5]’s outward contracts (what it guarantees to other nodes)

### To [1] via J7 AckTicket (hard guarantee)

* **Ack only after root commit exists** (or verified NOOP).
* **Per-partition contiguity:** writer emits acks that allow [1] to advance offsets contiguously.

### To [6] via J6 CommitReceipt (soft guarantee)

* A committed record exists at `root_commit_ref` with digest.
* [6] may lag/fail; writer must not block the spine on index health.

### To [8] via J12 PointerTrigger (optional)

* Pointer is derivative: it references durable truth only.

---

## Failure semantics (production reality, pinned)

### 1) Object store transient failures

* Retry inside [5H] with backoff.
* No AckTicket until root commit succeeds.
* Telemetry spikes; consumer lag grows; the platform can degrade accordingly.

### 2) Partial writes (sub-objects written, crash before root)

* Safe by design: without root commit, nothing is “committed.”
* On replay, writer will attempt again; sub-object writes are idempotent.
* Optional GC cleans staging later.

### 3) Root exists but digest mismatch / corruption signal

* **Fail closed** (this is a storage integrity incident).
* Do not ack. Emit critical telemetry. Requires ops intervention.
* (We do not “paper over” integrity problems with quarantine—because truth would become untrustworthy.)

### 4) Index DB down / pointer bus down

* Never blocks AckTicket.
* CommitReceipt/pointer emission can retry or be rebuilt from canonical truth later.

---

## Concurrency posture (so Codex doesn’t drift)

* Concurrency is allowed across partitions and across independent records.
* The only hard serialization needed is:

  * **per (root_commit_key)** because conditional “create-if-absent” is the commit latch.
* Checkpoint safety remains with [1]; writer simply emits per-event ack tickets.

---

## Environment ladder notes for [5]

Local/dev/prod can change the substrate (filesystem vs object store), but **the commit law is identical**:

* Same deterministic keys
* Same “root commit exists = committed”
* Same retry/backoff classes
* Same “index/pointer don’t gate checkpoint”
* Same receipt semantics

---

If you want the next step inside [5] (still controlled): we can open **just one internal box next**, and I recommend **5F Root Commit Finalizer**, because that’s where atomicity/idempotency is actually enforced.

---

Absolutely. We’ll now **open node [1] Ingest & Replay Control** and expose the **machinery inside it**.

This node is the *other half* of the correctness latch you already saw in [5] Writer:
**[5] makes truth durable → [1] makes replay/offset progression correct.**

Below, **[1] is no longer opaque**. Its internal parts are still grouped as small boxes, but we’ll make the behavior and invariants crystal clear so nothing drifts later.

---

## [1] Ingest & Replay Control: mission

**Consume EB (`fp.bus.traffic.v1`) safely under at-least-once delivery, preserve per-partition ordering, and only advance checkpoints when Writer proves the event is “applied” (canonical/quarantine/NOOP).**

Key rule: **write-then-checkpoint** (no ack without durable audit evidence).

---

## [1] Internal subnetworks (machinery)

### 1A) Consumer Adapter

* Talks to the event bus client (poll/fetch).
* Receives raw message bytes + bus headers + `(stream, partition, offset)`.

### 1B) Partition Assignment & Lease Manager

* Tracks which partitions this instance owns (consumer group / lease model).
* Handles rebalances and safe handoff (pause/drain/release).

### 1C) Frame Buffer & Dispatch

* Bounded queues for in-flight frames.
* Preserves per-partition order at the dispatch boundary (even if downstream processing is concurrent).

### 1D) In-flight Tracker (per-partition)

* Tracks frames that have been dispatched but not yet “applied”.
* Holds correlation: `bus_coord → in-flight token`.

### 1E) Ack Aggregator & Gap Tracker

* Receives **AckTickets** from Writer ([5] via J7).
* Allows out-of-order completion, but only advances checkpoints **contiguously** per partition.
* Computes “safe next_offset” (exclusive-next semantics).

### 1F) Checkpoint Store

* Persists the **offset vector**: `partition → next_offset` (exclusive-next).
* Must be durable across restarts.
* “Commit” of checkpoint happens only when contiguity is satisfied.

### 1G) Flow Control & Backpressure

* Prevents memory blowups: throttle/stop polling if:

  * in-flight is too large,
  * writer is slow/unavailable,
  * checkpoint lag exceeds thresholds.
* Produces health signals for degrade decisions (but does not compute degrade itself).

### 1H) Drain / Pause / Resume Controller (Ops surface)

* Implements J11 controls: pause, drain-to-offset, resume.
* Ensures “stop the world” operations do not corrupt checkpoint meaning.

### 1I) Seek / Replay Basis Controller (Ops surface)

* Implements J11 replay/backfill semantics: seek to explicit offset basis, bounded replay windows.
* Ensures basis is explicit and receipted.

### 1J) Telemetry Hooks

* Emits consumer lag, in-flight depth, ack latency, commit latency, rebalance events, and stalls.

---

## Internal joins inside [1] (edges)

```
[1A Consumer Adapter]
   -> [1B Partition Lease]
   -> [1C Frame Buffer & Dispatch]
   -> (J1 outward) to [2 Router]  (raw frame handoff)

Writer AckTickets (J7 inward from [5])
   -> [1E Ack Aggregator]
   -> [1F Checkpoint Store]
   -> [1G Flow Control] (signals)

Ops controls (J11 inward from [7])
   -> [1H Pause/Drain]
   -> [1I Seek/Replay]
   -> [1B Lease] (rebalance coordination)
```

---

## The core protocol: what [1] *does* and *does not* do

### What [1] does

* **Fetches frames** and hands them off to [2] (via J1) **without interpreting meaning**.
* **Waits for AckTickets** from [5] to consider a frame “applied.”
* **Advances checkpoints** only when it has contiguous applied coverage.
* Supports **pause/drain/seek** controls for operations.

### What [1] does *not* do (important non-drift pins)

* Does **not** parse the canonical envelope (that’s [2]).
* Does **not** decide canonical vs quarantine (that’s [3]/[4]/[5]).
* Does **not** advance offsets based on “we saw the message” — only based on **Writer proof**.

---

## The checkpoint law (authoritative)

### Exclusive-next checkpoint semantics

For each partition `p`, [1] stores:

* `checkpoint[p] = next_offset_to_read`

Meaning:

* “All offsets **< checkpoint[p]** are applied (canonical/quarantine/NOOP).”
* On restart, consumption resumes at `checkpoint[p]`.

### AckTickets are the only authority to advance

[5] emits `AckTicket{partition, offset_consumed, next_offset, apply_status}`.
[1] uses these to advance `checkpoint[p]` **only when contiguous**.

---

## The Gap Tracker (how [1] stays correct under concurrency)

Production reality: downstream work can finish out of order (especially across threads).
So [1] must tolerate:

* offset 102 finishes before 101 (Ack arrives out of order)
* duplicates/replays produce NOOP acks

### Mechanism (conceptual)

Per partition:

* `expected = checkpoint[p]` (the next offset that must be applied)
* `done_set` = set of offsets that have AckTickets

When an AckTicket arrives for offset `o`:

1. add `o` to `done_set`
2. while `expected` is in `done_set`:

   * remove `expected`
   * `expected = expected + 1` *(or use `next_offset` carried by the consumer/ack if you abstract gaps)*
3. persist new checkpoint = `expected`

**Pin:** [1] never “skips” an offset in checkpoint progression unless the bus semantics explicitly define the next offset (we keep it simple: assume increment; the bus adapter can translate if needed).

---

## Poison / malformed message posture (how we never wedge)

We pinned earlier: **DLA must never wedge a partition on a bad message.**

In [1] terms:

* [1] must still dispatch the raw frame to [2].
* [2]/[3]/[4]/[5] will turn malformed/unsupported messages into **quarantine truth**.
* Only after quarantine commit will [5] emit AckTicket → [1] advances.

So [1] never needs special “drop” handling. It just enforces: **no ack without durable evidence**.

---

## Backpressure & “always-on” reality

[1G] controls how hard [1A] polls, based on:

* in-flight queue sizes
* writer ack latency
* object store availability signals (indirectly from [5] telemetry)
* checkpoint lag thresholds

**Pin:** Backpressure can pause fetching; it must **not** fabricate progress.
If [5] can’t commit, [1] doesn’t advance, and lag becomes visible (and degrade ladder can act).

---

## Ops surface (J11) inside [1]

### Pause / Resume

* **Pause**: stop fetching new frames (keep assignments).
* **Resume**: continue fetching from current checkpoints.

### Drain-to-basis (safe deploy)

* Stop fetching new frames.
* Continue processing in-flight until checkpoint reaches a target offset vector.
* Emit a **DrainReceipt** when complete (basis echoed).

### Seek / Replay

* Requires an explicit offset basis vector: `partition → next_offset`.
* Apply only after pause/drain to avoid mixed-state confusion.
* Emit a **ReplayReceipt**: basis applied, coverage, any gaps beyond retention.

**Pin:** No “replay last week” unless already resolved into explicit offsets elsewhere.

---

## Failure semantics (production-grade)

1. **Writer down / object store outage**

* AckTickets stop.
* [1] stops advancing checkpoints.
* Backpressure reduces/halts polling.
* Telemetry shows lag growth and stall reason.

2. **Checkpoint store unavailable**

* [1] can keep processing in memory, but it must treat itself as “unsafe for restart.”
  Practical posture: escalate, attempt to restore checkpoint store, and consider pausing to avoid massive replay on crash.
* Never claim committed progress if it isn’t durable.

3. **Rebalance events**

* [1B] must coordinate a safe handoff:

  * either drain (preferred) or at least ensure checkpoints are persisted before releasing partitions.

---

## Environment ladder notes for [1]

Local/dev/prod can change the bus implementation (embedded vs real broker), but **these semantics must not change**:

* exclusive-next checkpoints
* write-then-checkpoint gating on Writer AckTickets
* contiguity per partition
* basis-driven replay/drain controls

That’s what prevents “local works but prod doesn’t.”

---

## Quick internal sketch (inside [1])

```
EB poll
  |
  v
[1A Consumer] -> [1B Lease] -> [1C Buffer/Dispatch] --J1--> [2 Router...]
                            |
                            | AckTickets (J7) from [5 Writer]
                            v
                     [1E Ack+Gap] -> [1F Checkpoint Store]
                            |
                            v
                     [1G Backpressure]

Ops (J11) -> [1H Pause/Drain] + [1I Seek/Replay] -> [1A/1B/1F]
Telemetry -> [1J] -> OTLP
```

---

If you want the clean next step (still disciplined): open **[4] Idempotency & Corrections** next, because [1] assumes that every consumed frame will eventually produce exactly one of: **commit canonical / commit quarantine / NOOP** — and [4] is where those branches are decided consistently.

---

Locked — we’re now opening **[4] Idempotency & Corrections Manager** and exposing the machinery inside it.

As a reminder (and a drift guard): **[4] does not change the network**. It is the internal “semantic engine” that makes these already-pinned paths work:

* P1 canonical write
* P2 quarantine write
* P3 duplicate NO-OP
* P4 corrections via supersedes
* P5 outcome linkage / orphan handling

It sits **between**:

* **Inputs:** J3/J4 from **[3] Admissibility Gate**
* **Lookups:** J8 to **[6] Views** (keyed existence/head checks)
* **Outputs:** J5 to **[5] Writer** (WritePlan or NOOP)

---

# [4] Mission

**Given an audit candidate (canonical or quarantine), produce exactly one of:**

1. **WRITE (canonical)**
2. **WRITE (quarantine)**
3. **WRITE (outcome-link / orphan evidence)**
4. **NOOP (provable duplicate)**

…and do it in a way that is:

* deterministic across environments,
* safe under replay/at-least-once,
* append-only (no overwrite),
* correction-safe (explicit supersedes, no forks),
* and never requires scanning or external system calls.

---

# [4] Internal subnetworks (machinery)

## 4A) Candidate Normalizer

* Accepts **CanonicalAuditCandidate** (J3) or **QuarantineCandidate** (J4).
* Produces a **NormalizedCandidate** with:

  * stable field ordering,
  * explicit “presence flags” (`used_ie_graph=true/false` etc.),
  * consistent representation of missing/unknown fields.
* **Excludes ephemerals** from the normalized representation used for identity (e.g., ingest timestamps, bus coords). Those can be preserved as *evidence*, not identity drivers.

## 4B) Identity & Anchor Engine

Computes the stable identity primitives:

* **decision_anchor**

  * **Pinned stance:** `decision_anchor = (ContextPins, decision_id)`
  * **Pinned v0 choice:** `decision_id = envelope.event_id` for DecisionResponse (unless DF later introduces a separate decision_instance_id)

* **audit_record_id**

  * Deterministic digest of the **canonicalized normalized candidate** (not including bus coords / local timestamps).

* **quarantine_record_id** (when applicable)

  * Deterministic digest of a canonicalized “failure capsule” (reason + missing_fields + safe correlation), not raw payload.

* **outcome_link_id** (for ActionOutcome linkage)

  * Deterministic digest of `(ContextPins, idempotency_key, action_type, outcome_event_id)` (exact tuple can be chosen later, but must be stable and replay-safe).

> This subnetwork is where “environment ladder safety” is enforced: identity **must not** depend on offset/partition or ingestion attempt ids.

## 4C) Existence & Dedupe Resolver

Decides whether this candidate is **already committed** or requires a write.

Key principle (pinned): **Correctness does not depend on the index being fresh.**
So [4] uses a *two-tier posture*:

* **Tier 1 (fast path, if available):** ask **[6] via J8**:

  * `LookupAuditRecord(audit_record_id, ContextPins)`
  * `LookupHead(decision_anchor)` (for corrections/outcomes)

* **Tier 2 (always safe):** if lookups are unavailable or uncertain, **emit a WRITE plan anyway** and let **[5] enforce idempotency** via “root commit exists = committed”.

**Designer pin:**
[4] is allowed to emit **NOOP** only when it can *prove* the record already exists (via reliable J8 response). Otherwise it emits **WRITE** and relies on [5] to turn it into a commit-or-noop safely.

## 4D) Correction & Conflict Arbiter

Enforces append-only correction rules:

* If a candidate would create a second canonical record for the same **decision_anchor**, it must carry an explicit **supersedes_audit_record_id**.
* The supersedes target must:

  * exist,
  * be in the same ContextPins scope,
  * and (strong pin) supersede the **current head** (linear history; no branching).

**If any of these are not satisfied → do not guess → quarantine**.

This is the subnetwork that prevents “forked truth” and keeps “current view” meaningful.

## 4E) Outcome Linker & Orphan Handler

For ActionOutcome candidates:

* Attempts to link outcome evidence to the decision lineage using only carried identifiers:

  * ContextPins
  * action idempotency key (and any decision correlation fields present)

* Uses **J8** to find:

  * the decision anchor/head (if possible)
  * whether a link already exists (idempotency)

Branches:

* **Linked:** produce an outcome-link write plan
* **Orphan:** produce a quarantine/orphan-evidence write plan (never drop, never stall)

**Pinned stance:** out-of-order outcomes never wedge ingestion. They become **durable orphan evidence** until reconciled (by later ops job or later linkage event), still append-only.

## 4F) WritePlan Builder

Converts the final decision into a **WritePlan** for [5]:

* plan_kind: `WRITE | NOOP`
* record_family: `CANONICAL | QUARANTINE | OUTCOME_LINK | ORPHAN_EVIDENCE`
* keys: **root_commit_key** + sub-object keys (deterministic)
* index_intents: what [6] should reflect (historical row, current-head update, quarantine index, outcome link index)
* pointer_intent: whether to trigger [8] pointer emission after commit
* correlation bundle: ContextPins, decision_anchor, audit_record_id, event_id, etc.

## 4G) Policy Snapshot Guard

Binds every decision in [4] to **one policy snapshot**:

* `policy_rev`, `profile_name`, `build_id`

This prevents mixed semantics inside a single candidate and makes behavior explainable later.

## 4H) Telemetry Hooks

Emits structured facts for:

* dedupe/NOOP rate
* correction acceptance vs conflict quarantine
* orphan outcome rate
* J8 availability issues
* write-plan kinds and latency budgets

(Still: telemetry never gates correctness.)

---

# Internal joins inside [4] (how the machinery connects)

```
J3/J4 in
  -> [4A Candidate Normalizer]
  -> [4B Identity & Anchor Engine]
  -> [4C Existence & Dedupe Resolver] <----J8----> [6 Views]  (keyed lookups)
  -> [4D Correction & Conflict Arbiter] (if decision record)
  -> [4E Outcome Linker]               (if outcome record)
  -> [4F WritePlan Builder]
  -> J5 out to [5 Writer]
```

---

# The decision logic [4] applies (by candidate type)

## Case 1: CanonicalAuditCandidate (DecisionResponse)

1. Normalize → compute `decision_anchor` + `audit_record_id`
2. Dedupe check:

   * if proven exists → **NOOP**
   * else continue
3. Correction/conflict handling:

   * if no head exists → **WRITE canonical**
   * if head exists:

     * if candidate includes valid `supersedes_audit_record_id` that supersedes current head → **WRITE canonical (correction)**
     * else → **WRITE quarantine** (“conflict/no supersedes”)

## Case 2: QuarantineCandidate (from admissibility failures)

1. Normalize failure capsule → compute `quarantine_record_id`
2. Dedupe: same two-tier posture (prove existence → NOOP, else WRITE)
3. Output: **WRITE quarantine**

## Case 3: ActionOutcome candidate

1. Normalize → compute outcome_link_id (or orphan_id)
2. Attempt link via J8:

   * linkable → **WRITE outcome-link**
   * not linkable / J8 unavailable → **WRITE orphan evidence** (quarantine family)
3. Dedupe: avoid duplicate outcome links using either J8 or writer idempotency.

---

# J8 usage rules (how [4] is allowed to “ask questions”)

**Pinned constraints:**

* J8 calls are **keyed only** (audit_record_id, decision_anchor, supersedes target id).
* No scans, no “latest”.
* If J8 is **UNAVAILABLE**, [4] must not stall ingestion.

**Safe fallbacks (authoritative):**

* For **dedupe**: if J8 unavailable → prefer **WRITE** and let [5] enforce idempotency.
* For **corrections**: if J8 unavailable and supersedes can’t be validated → **quarantine** (fail closed, no overwrite guessing).
* For **outcome linking**: if J8 unavailable → **orphan evidence** (record now, link later).

---

# What [4] guarantees outward (to keep the network consistent)

### To [5] Writer

Every candidate yields a deterministic **WritePlan** that is:

* self-contained (Writer doesn’t decide),
* idempotent-safe (same plan can be replayed),
* includes a clear **root commit key** to serve as commit boundary.

### To [6] Views

[4] never assumes views are truth. It supplies:

* stable keys and “index intents”
* but correctness is anchored in immutable truth + writer commit existence.

### To the environment ladder

Because identities exclude ephemerals and all outcomes are append-only, replay/restart behavior stays consistent across local/dev/prod.

---

# Failure semantics (production reality, pinned)

* **J8 down** never wedges partitions.
* **Ambiguous correction** never becomes canonical: it becomes quarantine.
* **Duplicate** becomes NOOP only when provable; otherwise “WRITE and let writer NOOP by commit existence.”
* **Outcome before decision** becomes orphan evidence (append-only), not dropped and not blocked.

---

If you want the most useful next node to open after [4], it’s **[3] Audit Admissibility Gate**, because [4] assumes it receives “canonical-ready vs quarantine-ready” candidates with the provenance blocks already normalized into by-ref form.

---

Absolutely — we’ll now open **[3] Audit Admissibility Gate** and expose the machinery inside it.

This node is the **“border checkpoint”** between:

* “events that arrived from EB and are shaped like decision/outcome lineage”
  and
* “events that are admissible to become DLA’s immutable audit truth.”

It **does not resolve** anything from other components. It **only** inspects what’s already in the envelope/payload and enforces the audit policy.

---

## [3] Mission

**Given a RoutedEvent from [2], decide (deterministically, under one policy snapshot) whether it becomes:**

* a **CanonicalAuditCandidate** (J3) → [4], or
* a **QuarantineCandidate** (J4) → [4],

…and do so without scanning, without external lookups, and without wedging partitions.

---

## [3] Internal subnetworks (machinery)

### 3A) Policy Snapshot Binder

* Pulls a single immutable **ConfigSnapshot** from [10] at the start of processing.
* Extracts the **audit completeness policy** for:

  * DecisionResponse admissibility
  * ActionOutcome admissibility
  * attachment strictness (optional vs required)
  * “forbidden embedded content” rules (by-ref posture)

> Pin: one event = one policy snapshot. No mid-event policy mixing.

---

### 3B) RoutedEvent Interpreter

* Accepts `RoutedEvent` from [2] with `route_kind`:

  * `DECISION_RESPONSE`
  * `ACTION_OUTCOME`
  * `NON_AUDIT_TRAFFIC`
  * `MALFORMED_ENVELOPE`
* Handles each route kind deterministically:

  * **NON_AUDIT_TRAFFIC** → “ignore/observe” (telemetry only; no audit output)
  * **MALFORMED_ENVELOPE** → immediate **QuarantineCandidate** (reason: MALFORMED_ENVELOPE)

> Pin: DLA must never wedge on malformed events. Malformed becomes quarantine evidence, then we move on.

---

### 3C) Schema/Version & Structural Validator

* Validates minimal structural expectations **without** interpreting meaning:

  * required envelope fields already present (but re-check if needed)
  * `event_type` recognized for lineage families
  * payload is parseable JSON/object
  * optional `schema_version` is supported for this event family (DecisionResponse/Outcome)

If unsupported:

* quarantine with reason `UNSUPPORTED_VERSION` or `UNKNOWN_EVENT_FAMILY`.

---

### 3D) Provenance Completeness Evaluator

This is the “heart” of admissibility: it enforces that the payload contains the minimum **audit truth bundle** fields required for canonical storage.

It applies **family-specific completeness templates**:

#### DecisionResponse completeness (v0 pinned set)

Must carry **by-ref/hashes**, not embedded raw data:

1. **Joinability pins**

* Full ContextPins: `manifest_fingerprint, parameter_hash, scenario_id, run_id`
* `seed` if this decision is seed-variant (policy defines when)

2. **Stimulus basis**

* A **stimulus reference** (by-ref): at minimum `stimulus_event_id` and/or EB coordinate ref; plus `stimulus_event_type`, `stimulus_ts_utc`

3. **Degrade posture**

* `degrade_mode` and enough to identify the mask used (or explicit `FAIL_CLOSED` posture)

4. **Feature provenance (OFP)**

* `feature_snapshot_hash`
* `input_basis` watermark vector (and the minimal freshness/group version summary)

5. **Graph provenance (IEG)**

* Either `{used:true, graph_version}` OR `{used:false, reason}`
  (No ambiguity: it must be explicit.)

6. **Policy/model provenance**

* `active_bundle_ref` (or equivalent registry resolution token)

7. **Decision outputs**

* decision result summary
* `actions[]` each with at least: `action_type`, `idempotency_key`

If any required item is missing → quarantine with `INCOMPLETE_PROVENANCE` + `missing_fields[]`.

#### ActionOutcome completeness (v0 pinned set)

Must be linkable **without lookups** beyond J8:

1. **Joinability pins**

* ContextPins present

2. **Action identity**

* `idempotency_key`
* `action_type`
* outcome status (`SUCCEEDED/FAILED/...`) + an outcome summary (no raw sensitive payload)

3. **Correlation (minimum)**

* Either explicit `decision_id/request_id` OR the pair `(ContextPins, idempotency_key)` must be sufficient to correlate via [4]/J8.

If not linkable → quarantine as `ORPHAN_OUTCOME_MISSING_CORRELATION`.

> Pin: outcomes are never dropped; if they can’t be linked, they become durable orphan evidence (via quarantine family).

---

### 3E) By-Ref & Privacy Guard

Enforces the platform’s by-ref posture:

* Reject-and-quarantine if payload includes forbidden embedded content such as:

  * raw stimulus payload bodies
  * full feature vectors (instead of hashes)
  * large unbounded blobs
* **No silent stripping.** If it’s forbidden, it becomes an explicit quarantine reason:

  * `FORBIDDEN_EMBEDDED_CONTENT`.

This prevents “audit truth” from becoming a hidden data lake.

---

### 3F) Evidence Attachment Coordinator (optional, policy-driven)

If the policy says attachments are enabled:

* Extract declared attachment refs (IG receipt refs, engine evidence locators, gate receipts).
* If **required_for_canonical**, send `EvidenceVerifyRequest` to [9] (J14) and wait for verdict (J15), **bounded** by policy.
* If **optional**, either:

  * verify opportunistically (best effort), or
  * attach as “unverified ref” metadata (if policy allows), or
  * omit and record a verdict.

**Decision rule (pinned):**

* Required attachments failing verification → quarantine (never stall).
* Optional attachments failing verification → omit + record verdict metadata.

---

### 3G) Candidate Builder (Canonical path)

When admissible:

* Constructs a **CanonicalAuditCandidate** that is **self-contained** for [4]:

  * includes explicit presence flags
  * includes normalized provenance blocks (DL/OFP/IEG/Registry/Actions)
  * includes optional attachments in a strictly by-ref form
  * includes correction intent fields (e.g., `supersedes_audit_record_id`) if present
    *(but does not validate correction chain — that’s [4].)*

Outputs via **J3 → [4]**.

---

### 3H) Quarantine Builder (Fail-closed path)

When not admissible:

* Constructs **QuarantineCandidate** with:

  * `reason_code`
  * `missing_fields[]` (when applicable)
  * safe correlation: `event_id`, `event_type`, `ts_utc`, partial pins
  * bus evidence pointer (stream/partition/offset) as evidence
  * optional payload evidence ref (only if policy permits storing a restricted evidence blob; otherwise do not embed)

Outputs via **J4 → [4]**.

---

### 3I) Telemetry Hooks

Emits structured signals:

* canonical vs quarantine counts by reason
* missing-field distributions (drives remediation)
* attachment verification outcomes
* unsupported schema/version occurrences

Telemetry never gates the decision.

---

## Internal joins inside [3]

```
[3A Policy Snapshot]
   -> [3B RoutedEvent Interpreter]
   -> [3C Structural Validator]
   -> [3D Completeness Evaluator]
   -> [3E By-Ref Guard]
   -> (optional) [3F Attachment Coordinator] <-> [9 Evidence Verifier]
   -> [3G Canonical Builder]  --J3--> [4]
   -> [3H Quarantine Builder] --J4--> [4]
```

---

## What [3] is explicitly NOT allowed to do (non-joins, restated for this node)

* No calls to OFP/IEG/Registry/DL to “fill in missing provenance.”
* No scanning to “find receipts” or “discover engine evidence.”
* No “wait indefinitely” for attachments — bounded, then either omit (optional) or quarantine (required).
* No mutation or “fixing” of payloads — only accept or quarantine.

---

## How [3] prevents contradictions with [4] and [5]

The handshake contract is simple:

* If [3] emits **CanonicalAuditCandidate**, it guarantees:

  * required provenance blocks exist
  * by-ref posture is respected
  * candidate is self-contained so [4] can compute stable ids and decide duplicate/correction/linking without external lookups.

* If [3] emits **QuarantineCandidate**, it guarantees:

  * the failure is explicit and inspectable (reason + missing fields + correlation)
  * [4] can still compute deterministic ids and produce a write plan for [5].

So [3] never forces [4] to “guess” or “re-resolve.” It just gives [4] clean, explicit inputs.

---

If you want the next node to open after [3], it should be **[2] Envelope & Type Router** (because it defines how route_kind and schema_version discovery work) — or **[6] Query & View Builder** if you want to finish the “semantic spine” that [4] relies on for J8.

---

Alright — we’re opening **[2] Envelope & Type Router** and exposing the machinery inside it.

This node is the **“meaning boundary interpreter”** between:

* **[1]** (bus mechanics: partitions/offsets/bytes)
* **[3]** (audit admissibility: canonical vs quarantine)

It owns **exactly one job**: take raw bytes + bus coords, interpret them as a **Canonical Event Envelope**, extract pins, and route deterministically. It does **not** decide audit truth.

---

## [2] Mission

**Given an IngestFrame `{bus_coord, raw_bytes}`, emit a RoutedEvent that is:**

* envelope-validated (or explicitly malformed),
* pinned with extracted ContextPins (if present),
* classified into a small set of route kinds:

  * `DECISION_RESPONSE`
  * `ACTION_OUTCOME`
  * `NON_AUDIT_TRAFFIC`
  * `MALFORMED_ENVELOPE`

…and do it in a way that is **fail-closed**, **non-wedging**, and **policy-visible**. 

---

## [2] Internal subnetworks (machinery)

### 2A) Frame Intake Adapter

* Accepts **IngestFrame** from [1] (J1): `(stream, partition, offset) + raw bytes + headers`.
* Enforces basic safety bounds (max size, decode limits) so a single huge frame can’t blow memory.

### 2B) Decoder & Parse Guard

* Decodes raw bytes into a JSON object (or equivalent).
* If decode/parse fails: does **not** throw upstream; it yields a **MALFORMED_ENVELOPE** RoutedEvent with an error capsule.

### 2C) Envelope Validator (Canonical Envelope Contract)

Validates the object against the **Canonical Event Envelope** contract:

* **Required fields:** `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` 
* **Optional pins:** `parameter_hash`, `seed`, `scenario_id`, `run_id` 
* **Optional routing/trace:** `schema_version`, `producer`, `trace_id`, `span_id`, `parent_event_id`, `emitted_at_utc` 
* Payload is isolated under `payload` (object). 

**Pin (strict boundary):** if the envelope violates the schema shape (missing required fields, wrong types, unexpected top-level fields), [2] emits **MALFORMED_ENVELOPE** (fail-closed). 

### 2D) Pin Extractor

Builds a **PinsBundle** without enforcing completeness:

* `manifest_fingerprint` (always present if envelope valid)
* `parameter_hash`, `scenario_id`, `run_id` (ContextPins candidates)
* `seed` (separate; present for run-realisation events)

**Pin:** [2] *extracts* pins; it does not decide whether they’re “required” for a given event family (that’s [3]).

### 2E) Type Classifier (Event Family Router)

Classifies the event into one of the four route kinds using a **table-driven mapping** from the policy lens ([10]):

* If `event_type` matches the configured **DecisionResponse** types → `DECISION_RESPONSE`
* If it matches configured **ActionOutcome** types → `ACTION_OUTCOME`
* Else → `NON_AUDIT_TRAFFIC`

**Drift guard:** `NON_AUDIT_TRAFFIC` still produces telemetry (so “unexpected event types” are visible), but it does not become audit truth.

### 2F) Payload Extractor (Opaque Payload Handling)

* Extracts `payload` as an object (or treats missing payload as `{}`/None, as-sent).
* Does **no semantic validation** of payload fields here.
* Preserves:

  * parsed `payload_obj` for downstream checks,
  * and (optionally) a bounded “raw payload digest” for diagnostics (not identity).

### 2G) RoutedEvent Builder

Builds the standardized handoff to [3], always including:

* `bus_coord` (stream/partition/offset) as evidence
* `envelope_fields` (parsed header)
* `pins_bundle` (extracted pins)
* `payload_obj` (opaque)
* `route_kind`
* `route_meta` (why/how it matched: exact match / unmapped / unsupported schema_version)
* `parse_error` capsule if malformed

### 2H) Telemetry Hooks

Emits structured counters/timers:

* parse failures
* malformed envelopes (by reason)
* route_kind counts
* unknown/unmapped event_type counts
* schema_version distribution
* payload-size buckets

All tagged with `policy_rev/profile/build_id` (from [10]) so you can explain behavior later.

---

## Internal joins inside [2]

```
J1 in from [1]: IngestFrame(bus_coord, raw_bytes)
   -> [2B Decode/Parse]
   -> [2C Envelope Validate]
   -> [2D Pin Extract]
   -> [2E Type Classify]
   -> [2F Payload Extract]
   -> [2G RoutedEvent Build]
J2 out to [3]: RoutedEvent(route_kind, envelope, pins, payload, bus_coord, meta)
```

---

## What [2] guarantees to [3] (the J2 handshake contract)

If `route_kind != MALFORMED_ENVELOPE`:

* envelope has the required fields and conforms to the canonical envelope shape 
* pins are extracted (may be partial; [3] decides requirements)
* payload is isolated under `payload` and delivered as an object 

If `route_kind == MALFORMED_ENVELOPE`:

* [2] provides the best-available correlation:

  * bus coords always
  * any extracted fragments if parse partially succeeded
  * a reason capsule (decode error / missing field / type mismatch / unknown top-level fields)
* [3] can deterministically quarantine without wedging a partition.

---

## What [2] explicitly does NOT do (non-joins inside this node)

* Does **not** decide canonical vs quarantine (that’s [3]/[4]/[5]).
* Does **not** enforce “provenance completeness” (that’s [3]).
* Does **not** call external systems or scan storage.
* Does **not** “fix up” payloads or strip forbidden content silently.

---

## Environment ladder posture for [2]

Across local/dev/prod:

* **same envelope contract** (same required fields, same payload isolation) 
* **same fail-closed routing** (malformed is explicit, not silently ignored)
* only operational knobs vary (timeouts, max message size, telemetry sampling)

---

### Quick mental model

**[2] is the deterministic gatekeeper for “what did the message say at the boundary?”**
It produces a clean, typed handoff so **[3] can enforce audit admissibility** without guessing, and **[1] never wedges** on poison messages.

If you want the next node to open, the clean continuation is **[6] Query & View Builder**, because it’s the other side of J8 that [4] relies on for “existence/head” semantics.

---

Absolutely — we’ll now open **[6] Query & View Builder** and expose the machinery inside it.

This node is **not truth** (truth is immutable objects under `dla/audit/...`). Its job is to make DLA **queryable and operable** without scanning, and to support the keyed lookups and planning calls needed by **J8/J9** — while staying rebuildable from canonical truth and/or replay basis.

---

## [6] Mission

Provide deterministic, keyed access to DLA audit truth (by-ref), with two semantic views:

* **Historical view:** everything (canonical + superseded + quarantine)
* **Current view:** latest canonical head per decision anchor (following supersedes chain)

…and support:

* **J8**: existence/head/supersedes checks for [4]
* **J9**: reindex/export selection planning for [7]
* idempotent application of commit receipts from [5] (J6)

**Pin:** [6] must never gate the truth spine. Index/view failures don’t block checkpointing; [7] can rebuild. Derived state may lag; canonical truth remains authoritative.

---

## [6] Internal subnetworks (machinery)

### 6A) CommitReceipt Intake & Dedup

* Accepts **CommitReceipt** from [5] (J6).
* Dedupes receipts idempotently (same `(ContextPins, audit_record_id, record_family)`).
* Enforces “apply-at-least-once but effect-once” updates into derived stores.

### 6B) Index Writer (Historical Index)

Maintains the **historical index**, append-only in meaning:

* One row per canonical record (including superseded ones)
* One row per quarantine record
* Optional rows for outcome-link / orphan evidence

Keys include:

* `context_pins`, `audit_record_id`, `record_family`, `ts_utc`
* correlation axes: `decision_anchor`, `event_id`, `action_idempotency_key` (if applicable)
* policy context: `policy_rev`, `build_id`

**Pin:** Historical index must support time-window + key queries without scanning.

### 6C) Head Resolver (Current View Engine)

Maintains the **current head** per `decision_anchor`.

This is the semantic heart of “current vs historical.”

* On first canonical decision record for an anchor → head = that record
* On correction record with valid `supersedes_audit_record_id`:

  * head updates only if it supersedes the current head (linear history)
* Head updates are idempotent and order-tolerant

**Pin:** No branching heads. Ambiguity is quarantined upstream in [4], so [6] can keep “current head” simple.

### 6D) Supersedes Graph Store (Lineage Map)

Stores the supersedes links:

* `child_audit_record_id -> parent_audit_record_id`
* per anchor, optional chain metadata (depth, latest head)

This supports:

* current view computation
* “show lineage” queries
* validation / debugging

### 6E) Outcome Link Index

Indexes ActionOutcome evidence:

* link outcomes by `(ContextPins, idempotency_key)` and/or decision_anchor
* supports queries like “show outcomes for this decision” and “find orphan outcomes”
* preserves append-only meaning

### 6F) Keyed Lookup Service (J8 implementation)

Serves the keyed lookups [4] needs:

* `LookupAuditRecord(audit_record_id, context_pins)`
* `LookupHead(decision_anchor)`
* `LookupSupersedesTarget(supersedes_audit_record_id, context_pins)`
* `LookupOutcomeLink(anchor or (pins,idempotency_key))`

**Pin:** Only keyed lookups. No scans. If the derived store is down, return `UNAVAILABLE`, not guesses.

### 6G) Selection Planner (J9 implementation)

Generates deterministic plans/manifests for [7]:

* `PlanReindex(scope, basis)`
* `PlanExportSelection(filters, view, basis)`
* produces:

  * **SelectionManifest**: explicit refs (or explicit bounded key ranges)
  * deterministic ordering rules
  * expected coverage metadata

**Pin:** Plans must be basis-driven and reproducible.

### 6H) Rebuild Engine (reindex/recompute derived state)

Given an explicit basis (from [7]):

* rebuild historical index
* rebuild current heads
* rebuild supersedes graph summaries
* rebuild outcome-link indices

Rebuild can be driven by:

* reading immutable `dla/audit/...` records by explicit manifest or bounded partitioned key basis
* or by consuming CommitReceipts (if stored/retained)

### 6I) Integrity & Drift Monitor

Detects derived vs truth divergence signals:

* missing index rows for committed records (when basis says they should exist)
* head pointer inconsistencies (broken chain)
* orphan rates
* delayed apply lag

Emits telemetry and supports ops decisions (“reindex needed”).

### 6J) Query API Surface

Provides the outward query semantics for:

* Case Workbench
* Governance tools
* internal ops jobs

Supports:

* fetch canonical record ref by decision_anchor (current view)
* fetch history for anchor (historical view)
* fetch by time window + filters
* fetch quarantines by reason + window

Always returns **by-ref locators** to immutable truth objects.

---

## Internal joins inside [6] (edges)

```
J6 in from [5]: CommitReceipt
   -> [6A Receipt Dedup]
   -> [6B Historical Index Writer]
   -> [6D Supersedes Graph Store]
   -> [6C Head Resolver]
   -> [6E Outcome Link Index]
   -> [6I Drift Monitor] -> telemetry

J8 queries from [4] -> [6F Keyed Lookup Service] -> responses
J9 planning from [7] -> [6G Selection Planner] -> selection manifests/plans
Rebuild inputs from [7]/[5] -> [6H Rebuild Engine] -> rehydrate [6B/6C/6D/6E]
```

---

## The key semantics [6] must preserve

### 1) “Truth by reference”

Every index row ultimately points to:

* `root_commit_ref` in `dla/audit/...`
* `root_commit_digest`

So consumers never treat the index as truth; they fetch the immutable record by ref.

### 2) Historical vs Current

* **Historical:** return all canonical + quarantine records for an anchor (including superseded)
* **Current:** return the head canonical record for an anchor (and optionally its lineage)

### 3) J8 correctness posture

[4] may use [6] to validate corrections and detect conflicts, but:

**Pin:** [6] must not lie. If it can’t answer because stores are down or stale, it returns `UNAVAILABLE`, and [4] chooses safe fallbacks (quarantine for corrections, write-and-let-writer-idempotency for dedupe).

### 4) Idempotent application

CommitReceipts may be duplicated (replays/retries). [6] must apply them safely multiple times.

---

## Failure semantics (production-ready)

### Index DB down

* [6] may be partially unavailable:

  * J8 returns `UNAVAILABLE`
  * queries may fail or degrade
* But **truth writing continues** in [5] and checkpoints continue in [1].
* Ops later triggers rebuild (P8).

### CommitReceipt loss

If a receipt wasn’t applied (or lost), [6H] rebuild exists precisely to rehydrate derived state from truth objects by explicit basis.

### Out-of-order receipts

[6] must tolerate out-of-order receipts (across partitions) and still converge to the same historical index and current head.

---

## Environment ladder notes for [6]

Local/dev/prod may implement [6] differently (in-memory vs DB), but semantics must remain:

* keyed lookup semantics (no scan)
* historical/current view meaning
* rebuildability from canonical truth
* non-gating posture (truth spine continues without [6])

---

## One compact sketch (inside [6])

```
          CommitReceipt (from [5])
                   |
                   v
           [6A Receipt Dedup]
             /   |     |    \
            v    v     v     v
        [6B Hist] [6D Graph] [6C Head] [6E Outcomes]
                   |
                   v
            [6F Keyed Lookups] <---- J8 ---- [4]
            [6G Planner]       <---- J9 ---- [7]
            [6H Rebuild Engine] <--- basis --- [7]
            [6J Query API]  -> returns refs to object://dla/audit/...
```

---

If you want the clean next node to open: **[7 Ops/Retention/Export Orchestrator]**, since it’s the primary consumer of [6]’s selection planner and rebuild engine, and it’s where “basis-driven + receipted operations” become concrete.

---

Absolutely — we’re now opening **[7] Ops / Retention / Export Orchestrator** and exposing the machinery inside it.

This node is the **governed control plane** for DLA. It is where you make “production reality” true without violating the pinned rails:

* **No silent scans** (everything is basis-driven)
* **No mutation of canonical truth**
* **Receipts are first-class**
* **Replay/backfill is explicit and auditable**
* **Same semantics across env ladder** (local/dev/prod differ by profile strictness and retention/scale)

---

# [7] Mission

Execute **governed operational workflows** for DLA:

1. **Reindex / rebuild derived surfaces** (P8)
2. **Deterministic exports / slices** (P9)
3. **Controlled replay/backfill / drain/seek** (P10)
4. **Retention & lifecycle management** (explicit, receipted)
5. **Health + drift remediation** (trigger reindex when views diverge)

…and do it while treating:

* `dla/audit/...` as **immutable truth**
* `audit_index` as **derived**
* offsets/archives as **explicit bases**, not “latest” discovery.

---

# [7] Internal subnetworks (machinery)

## 7A) Request Intake & Governance Gate

Accepts operational requests from Run/Operate / governance tooling:

* `ExportRequest`
* `ReindexRequest`
* `ReplayRequest`
* `DrainRequest`
* `RetentionChangeRequest`
* `IntegrityRemediationRequest`

Enforces:

* caller authorization / role
* environment profile policies (local/dev/prod strictness)
* request must include **explicit basis** (or be convertible to one)

**Pin:** If a request can’t be expressed with an explicit basis, it’s invalid in production posture.

---

## 7B) Basis Resolver

Normalizes the request’s “what data are we operating on?” into a **BasisSpec**.

BasisSpec types (all explicit):

* **EB offset basis:** `{stream, consumer_group?, partition→next_offset}`
* **Truth-object basis:** `{record_family, ContextPins scope, time window, bounded key partition ranges or manifest}`
* **Archive basis:** explicit archive segment IDs / manifests (no “find all archives”)

**Pin:** time windows are not bases until they’ve been tied to explicit enumerations (offset vectors or explicit object-key partitions/manifests).

---

## 7C) Plan Negotiator (with [6])

This is where [7] asks [6] to generate deterministic, reproducible plans:

* J9 `PlanReindex(scope, basis)`
* J9 `PlanExportSelection(filters, view, basis)`
* J9 `GetViewHealth()` / `HealthReport`

Outputs:

* **SelectionPlan** with deterministic ordering
* **SelectionManifestRef** (explicit list of record refs or bounded key ranges)
* **WorkUnitPlan** (chunking for parallel execution; still deterministic)

**Pin:** Plans are receipts-in-waiting: they must be stable given the same inputs.

---

## 7D) Execution Orchestrator

Runs the actual work by driving the right downstream joins:

### For exports/reindex reads and artifact writes:

* J10 to **[5]**: `ReadRecords(selection_manifest_ref)` (by-ref)
* J10 to **[5]**: `WriteExportArtifacts` + `WriteExportReceipt`
* J10 to **[5]**: optionally write “reindex artifacts” / “rebuild receipts”

### For replay/drain/pause/seek:

* J11 to **[1]**: `Pause/Drain/Resume/SeekToBasis/BoundedReplay`

**Pin:** Orchestrator never touches canonical truth except by reading it by-ref; it never overwrites.

---

## 7E) Receipt Writer & Evidence Binder

Every ops operation produces a durable receipt that includes:

* operation type (`EXPORT`, `REINDEX`, `REPLAY`, `DRAIN`, `RETENTION_APPLY`)
* who/what initiated it (actor identity)
* **basis used** (explicit basis spec)
* scope/filters/view selector
* deterministic plan digest (hash of SelectionPlan + policy_rev)
* outputs produced (artifact refs + digests, index outputs, etc.)
* coverage summary (complete/partial + explicit gaps)
* policy context (`policy_rev`, `profile_name`, `build_id`)
* timestamps (ops-time, not identity)

Receipts are written to durable storage (object store under an ops prefix, or another governed store).
They are what makes ops **auditable** and prevents hidden backfills.

---

## 7F) Partial Coverage Handler (Fail-Closed Discipline)

Decides what to do if basis cannot be satisfied fully:

* archive gaps,
* missing truth objects,
* read failures,
* inconsistent manifests.

Policy-driven outcomes:

* **Fail closed** (default posture for governance-critical ops)
* Or produce a **partial receipt** that explicitly lists missing segments/refs (never silent)

---

## 7G) Concurrency & Determinism Scheduler

Ops jobs can be parallel, but must remain deterministic:

* deterministic ordering within a SelectionManifest
* deterministic partitioning of work units (e.g., stable chunking)
* idempotent artifact keys (export_run_id + manifest_digest)

This prevents “same export request produces different artifacts” drift.

---

## 7H) Retention & Lifecycle Manager

Handles retention actions for:

* derived DB surfaces (`audit_index` pruning/rebuild)
* ops artifacts/receipts retention
* canonical truth lifecycle if you ever do archival/expiry (must be explicitly governed)

**Pinned guardrail:** canonical audit truth is append-only in meaning.
Retention actions must be:

* explicitly scoped
* basis-driven
* receipted
  …and cannot “rewrite history.”

---

## 7I) Health & Drift Monitor (Ops-side)

Consumes:

* [6] Drift/Health reports
* [11] telemetry signals (index lag, quarantine spikes, writer errors)

Can trigger:

* reindex jobs
* pause/drain
* replay basis operations
* policy rollback recommendations

**Pin:** [7] responds to signals; it does not generate degrade posture itself.

---

## 7J) Telemetry Hooks

Emits:

* ops job start/finish
* basis applied
* manifests/digests
* success/partial/failure states
* durations and resource usage

---

# Internal joins inside [7] (how the machinery connects)

```
Requests -> [7A Governance Gate]
          -> [7B Basis Resolver]
          -> [7C Plan Negotiator] ----J9----> [6 Planner/Views]
          -> [7D Execution Orchestrator]
              |----J10----> [5 Persistence] (read truth by-ref; write export artifacts/receipts)
              |----J11----> [1 Ingest]      (pause/drain/seek/replay)
          -> [7E Receipt Writer]
          -> [7F Partial Coverage Handler]
          -> [7J Telemetry]
```

---

# The three main ops workflows (inside [7])

## Workflow W1: Reindex / rebuild (P8)

1. Receive ReindexRequest → validate + require BasisSpec
2. Ask [6] for ReindexPlan + SelectionManifest (J9)
3. Read immutable truth records by explicit manifest (J10)
4. Apply rebuild through [6] rebuild engine (can be invoked via [6H] under [7] control)
5. Write ReindexReceipt (basis + coverage + outputs)

**Never changes canonical truth.**

---

## Workflow W2: Deterministic export (P9)

1. Receive ExportRequest → validate permissions + basis
2. Ask [6] for ExportSelectionPlan (J9)
3. Read records by explicit manifest (J10)
4. Write export artifacts + ExportReceipt (J10)
5. Optional pointer about export completion (still derivative)

**Determinism pin:** same request + basis + policy_rev => same manifest + same export ordering.

---

## Workflow W3: Controlled replay/backfill/drain (P10)

1. Receive ReplayRequest/DrainRequest → must include explicit offset basis (or resolved-to-offset basis)
2. Pause/Drain (optional) to a stable boundary (J11)
3. SeekToBasis / bounded replay (J11)
4. Allow [1] to re-consume; idempotency prevents duplicate truth
5. If requested, trigger reindex (W1)
6. Write ReplayReceipt/DrainReceipt (basis + coverage)

**Pin:** replay is always explicit and receipted; no silent “just rerun it.”

---

# Failure semantics (production posture)

* **Missing/ambiguous basis:** reject request (ops must restate with explicit basis).
* **Archive/retention gaps:** fail closed or produce explicit partial receipt (policy decides; never silent).
* **DB down:** exports can still run off truth objects; view rebuild may defer; receipts still written.
* **Writer/object store down:** ops jobs fail with receipts that capture failure mode; drain/replay cannot claim completion.
* **Retry logic:** ops operations must be idempotent by run_id/manifests; retries must not create duplicate artifacts.

---

# Environment ladder guidance for [7]

Local/dev/prod differences should be **profile knobs**, not semantics changes:

* local: smaller retention, fewer permissions checks, shorter manifests, but still explicit basis + receipts
* dev: strict basis discipline + forced partial-coverage tests
* prod: hardened governance, long retention + archive use, SLOs, and mandatory receipts for every operation

---

## Quick sketch (inside [7])

```
           Run/Operate / Gov Tools
                    |
                    v
        [7A Gate] -> [7B Basis] -> [7C Plan w/6]
                                   |
                    +--------------+--------------+
                    |                             |
              [J10] v                       [J11] v
                 [5 Persistence]              [1 Ingest]
                    |                             |
                    +--------------+--------------+
                                   v
                          [7E Receipts]
                                   |
                                   v
                            ops artifacts store
```

---

If you want to keep the illumination order tight, the only major node left to open is **[9 Evidence Attachment Verifier]** and **[8 Pointer Publisher]** (optional), plus the cross-cut rails if you want them concretely implemented.

---

Got it — we’re opening **[9] Evidence Attachment Verifier** and exposing the machinery inside it.

This node is **optional** and must stay strictly within our pinned rules:

* **No scanning**
* **Keyed verification only**
* **Engine evidence must obey “No PASS → no read” with gate-specific verification**
* **Never wedges ingestion** (optional evidence can be omitted; required evidence failure becomes quarantine)

---

# [9] Mission

Given an **EvidenceVerifyRequest** (J14) containing explicit evidence refs (receipt refs/ids, engine locators, gate receipts, etc.), return an **EvidenceVerifyResult** (J15) with per-item verdicts:

* `VERIFIED`
* `UNVERIFIABLE_NOW` (transient / eventual consistency / retryable)
* `INVALID` (permanent / inadmissible / wrong scope / digest mismatch)

…and do it **without scanning storage** and without turning verification into a blocking dependency.

---

# [9] Internal subnetworks (machinery)

## 9A) Request Intake & Policy Binder

* Accepts `EvidenceVerifyRequest` from [2]/[3]/[4] (J14).
* Binds a single **policy snapshot** (from [10]) to the request:

  * verification strictness
  * timeouts / retry budgets
  * which evidence kinds are recognized
  * whether “unverified optional refs” may be passed through (usually *no*; we prefer omit + record verdict)

> Pin: one request = one policy snapshot.

---

## 9B) Evidence Item Normalizer

Converts each evidence item into a canonical internal shape:

* `evidence_kind`
* `normalized_ref` (canonical locator form)
* `expected_scope` (ContextPins / output identity pins)
* `required_level` (`OPTIONAL_ENRICHMENT | REQUIRED_FOR_CANONICAL`)
* `proofs[]` already provided (e.g., GateReceipt, digest)

Also computes a deterministic `evidence_item_id` (stable hash of kind+ref+scope) to support dedupe.

---

## 9C) Dispatch Router (Kind-based verifier selection)

Routes each normalized evidence item to a specific verifier pipeline:

* **IG Receipt Verifier**
* **IG Quarantine Ref Verifier**
* **Engine Output Locator Verifier**
* **GateReceipt Verifier**
* **Generic Object Ref Verifier** (fallback, strict)

Each sub-verifier is keyed and must not list directories.

---

## 9D) Keyed Resolver (No-scan object access)

A small internal service that can do only:

* `GET metadata for exact object key`
* `GET exact object content (bounded)`
* `HEAD exact object key`
* `GET by explicit id → deterministic key mapping` (if receipt_id maps to a known path template)

**Forbidden:** list prefixes, search, “latest”, wildcard enumeration.

This resolver is the “enforcer” of the no-scan rule.

---

## 9E) IG Receipt / Quarantine Evidence Verifier

Verifies IG evidence refs in a by-ref safe way.

Inputs may be:

* `receipt_ref` (object locator), or
* `receipt_id` (must map deterministically to a key), or
* an explicit “receipt lookup API” (if you later implement one — still keyed)

Verification checks:

1. Object exists (HEAD/GET by key)
2. Receipt schema minimally valid (not full semantic validation)
3. Receipt’s correlation matches expected scope (ContextPins, event_id, etc.)
4. Optional: receipt includes policy rev / schema version fields (useful for audit)

Verdicts:

* Missing object due to eventual consistency → `UNVERIFIABLE_NOW`
* Not found with confidence / forbidden access → `INVALID`
* Exists and matches scope → `VERIFIED`

---

## 9F) Engine Locator + PASS Proof Verifier (the strict one)

This handles engine `audit_evidence` attachments and is the most sensitive subnetwork.

**Inputs:**

* `EngineOutputLocator` (output_id + path + identity pins + optional content_digest)
* `GateReceipt(s)` for the relevant gate scope
* `engine_gates.map` knowledge (how to verify PASS artifacts)

Verification checks (in strict order):

1. Locator well-formed and identity pins present as required
2. Locator path exists (HEAD/GET keyed)
3. Required gate receipts present and indicate `PASS`
4. Gate verification method is selected by `gate_id` from `engine_gates.map.yaml`

   * e.g., sha256 bundle digest vs member digest concat, ordering rules, exclusions
5. Compute/verify the correct digest(s) per gate rule
6. Confirm locator scope matches receipt scope (no scope mismatch)

Verdicts:

* Missing receipts / FAIL → `INVALID` (No PASS → no read)
* Gate rule unknown/unsupported → `INVALID` (fail closed)
* Objects temporarily not visible → `UNVERIFIABLE_NOW`
* Digests match and PASS proven → `VERIFIED`

> Pin: [9] never “tries a different hashing guess.” Gate rules are authoritative.

---

## 9G) Digest & Integrity Engine

A shared utility used by verifiers:

* computes digests for retrieved objects
* verifies provided digests
* supports “bounded reads” and streaming hashing where possible
* includes strict maximum sizes (to avoid turning verification into a heavy IO sink)

---

## 9H) Retry Budget & Backoff Manager (for UNVERIFIABLE_NOW)

Implements the L2 loop safely:

* Tracks retry state per evidence_item_id:

  * attempt count
  * last error
  * next retry time
* Enforces a bounded retry window from policy snapshot
* After budget expiry:

  * if item is required → recommendation becomes `MUST_QUARANTINE`
  * if optional → recommendation becomes `OMIT_OPTIONAL_ATTACHMENTS`

**Pin:** retries are keyed and bounded; no indefinite waiting.

---

## 9I) Result Aggregator & Recommendation Builder

Builds the final `EvidenceVerifyResult` (J15):

* per-item verdicts + proof notes (verified_digest, normalized refs)
* overall recommendation:

  * `OK_TO_ATTACH`
  * `OMIT_OPTIONAL_ATTACHMENTS`
  * `MUST_QUARANTINE`

Also includes reason codes that upstream can store in canonical/quarantine records for transparency.

---

## 9J) Telemetry Hooks

Emits:

* counts by kind + verdict (VERIFIED / UNVERIFIABLE_NOW / INVALID)
* common failure reasons (missing ref, digest mismatch, scope mismatch, access denied)
* verification latency distributions
* retry budget exhaustion counts

Tagged with `policy_rev/profile/build_id`.

---

# Internal joins inside [9] (edges)

```
J14 in: EvidenceVerifyRequest
   -> [9A Policy Binder]
   -> [9B Normalizer]
   -> [9C Dispatch Router]
       -> [9E IG Receipt Verifier] ----\
       -> [9F Engine+PASS Verifier] ----+--> [9I Result Aggregator] -> J15 out
       -> [9G Digest Engine] -----------/
   -> [9H Retry Manager] (for UNVERIFIABLE_NOW cases)
   -> [9J Telemetry]
```

---

# What [9] guarantees outward

### To [3] Admissibility

* Required evidence that is not VERIFIED within policy budget yields `MUST_QUARANTINE`.
* Optional evidence that fails verification yields “omit” (with verdict metadata), not “attach anyway.”

### To [4] Corrections

* Evidence verification never substitutes for J8 (internal audit record existence).
* It provides reliable verdicts for external refs so [4] can build correct write plans.

### To the platform rails

* No scanning
* No truth creation
* No blocking ingestion indefinitely

---

# Failure semantics (production-safe)

* **Object store temporarily inconsistent / delayed:** `UNVERIFIABLE_NOW` → retry bounded
* **Access denied:** `INVALID` (fail closed)
* **Digest mismatch / PASS missing:** `INVALID`
* **Verifier down:** upstream treats optional evidence as omitted; required evidence triggers quarantine (never stall)
* **Oversize evidence object:** treated as `INVALID` (or “unverifiable under policy”) to prevent abuse

---

# Environment ladder posture for [9]

Local/dev/prod may differ in:

* whether engine evidence attachments are enabled
* retry budgets/timeouts
* access controls

But must keep:

* keyed-only verification
* PASS discipline and gate-specific verification
* bounded retry semantics (no indefinite waits)

---

Absolutely — we’ll now open **[8] Pointer Publisher** and expose the machinery inside it.

This node is intentionally **small** and **strictly derivative**: it never creates truth, it only publishes **pointers to truth** that already exists in `dla/audit/...`.

---

# [8] Mission

Publish **audit pointer events** to `fp.bus.audit.v1` that tell subscribers:

> “A canonical/quarantine audit record was committed; here is the immutable ref + digest + correlation keys.”

And do it:

* **after durable commit**
* **idempotently**
* **with retries/backoff**
* **without gating the spine** (never blocks checkpoints/truth)

---

# [8] Internal subnetworks (machinery)

## 8A) Trigger Intake & Normalizer

* Accepts **PointerTrigger** from [5] (J12).
* Normalizes it into a canonical internal form and computes:

  * deterministic `pointer_event_id`
  * normalized correlation keys
  * minimal payload shape

**Pin:** the trigger must already refer to a **durable root commit object** (emit-after-durable).

---

## 8B) Deterministic Event ID & Dedupe Guard

Ensures idempotency under retries/replays.

**Pinned recipe:**
`pointer_event_id = hash(context_pins + record_family + audit_record_id)`

* If the same trigger reappears (replay/retry), it maps to the **same** pointer_event_id.
* Prevents pointer storms and makes subscriber dedupe trivial.

---

## 8C) Payload Builder (Derivative Pointer Envelope)

Builds the outgoing pointer event, which is itself a **Canonical Event Envelope** (so it can traverse EB cleanly), with a minimal payload:

Envelope:

* `event_id = pointer_event_id`
* `event_type = AUDIT_POINTER` (or similar)
* `ts_utc = now_utc` (domain time here is “publish time”; not decision time)
* `manifest_fingerprint` and ContextPins (copied for joinability)

Payload (strictly by-ref):

* `record_family` (canonical/quarantine/outcome-link)
* `audit_record_id`
* `root_commit_ref` (object locator into `dla/audit/...`)
* `root_commit_digest`
* `decision_anchor` (if applicable)
* `source_event_ref` (optional evidence: EB coords/event_id of source lineage event)
* `policy_rev/profile/build_id` (visibility of rules in force)

**Pin:** no raw payload bodies, no embedded audit record contents.

---

## 8D) Publisher Adapter (Bus Client)

* Publishes pointer events to `fp.bus.audit.v1`.
* Uses at-least-once semantics; duplicates are okay.

This adapter is configured by wiring profile (endpoints, retries), not semantics.

---

## 8E) Retry / Backoff Manager (L3 loop)

Handles publish failures safely:

* transient errors → retry with exponential backoff
* persistent errors → keep retrying within policy budget or mark as “stuck” for ops visibility

**Pin:** failure to publish pointers must never affect [5] truth commits or [1] checkpoints.

---

## 8F) Outbox / Pending Queue (optional but production-realistic)

To avoid losing pointer triggers across restarts:

* store pending pointer triggers (or built pointer events) in a small durable outbox
* on restart, resume publishing unsent pointers

This outbox is **not** truth and can be pruned idempotently because pointer_event_id is deterministic.

(If you don’t want an outbox initially, you can accept that pointers are best-effort and rely on polling/index; but prod usually benefits from an outbox.)

---

## 8G) Telemetry Hooks

Emits:

* publish success/failure counts
* retry counts
* queue depth (if outbox used)
* per-error-class breakdown

Always tagged with policy_rev/profile/build_id.

---

# Internal joins inside [8]

```
J12 in from [5]: PointerTrigger
   -> [8A Normalize]
   -> [8B Deterministic ID + Dedupe]
   -> [8C Payload Builder]
   -> [8D Publish Adapter] --to fp.bus.audit.v1-->
       ↳ [8E Retry/Backoff] (on failure)
       ↳ [8F Outbox] (optional durability)
   -> [8G Telemetry]
```

---

# What [8] guarantees outward

### To subscribers

* Pointer events are **derivative**: they always reference a durable root commit ref + digest.
* Pointer events are **idempotent**: duplicates may occur, but they share the same `pointer_event_id` and payload identity keys.

### To DLA’s correctness spine

* [8] cannot block:

  * [5] committing truth
  * [5] emitting AckTickets to [1]
  * [1] advancing offsets

If [8] is down, the platform still functions; pointers are a convenience.

---

# Failure semantics (production-safe)

* Pointer publish fails → retries/backoff; truth remains readable by-ref.
* Outbox (if enabled) ensures eventual delivery after restarts.
* If pointers are missed entirely, subscribers can fall back to:

  * deterministic queries via `audit_index`, or
  * polling `dla/audit/...` by explicit scope (never “scan latest” in prod posture).

---

# Environment ladder posture for [8]

* Local may disable pointers entirely.
* Dev/prod can enable pointers.
* Semantics stay the same: deterministic id, derivative refs, no gating.

---

Got it — you mean the **cross-cut rails** we intentionally didn’t “open” earlier:

* **[10] Policy/Profile & Schema Lens**
* **[11] Observability & Telemetry**

We’ll open both now and expose the machinery inside them.

---

# [10] Policy/Profile & Schema Lens

## Mission

Provide a **single, auditable source of configuration truth** for DLA that:

* keeps **environment ladder** behavior aligned (same semantics; different profile knobs),
* ensures **one immutable snapshot per unit of work** (no mid-event rule changes),
* makes “what rules were in force?” always answerable.

## Internal subnetworks (machinery)

### 10A) Config Source Reader

Pulls configuration from defined sources (in a deterministic precedence order):

* **Wiring profile** (endpoints, timeouts, concurrency, OTLP exporter targets)
* **Policy profile** (audit completeness, attachments required/optional, export permissions, pointer enablement)
* **Schema bundle** (known event families + supported schema_version ranges, validator rules)
* **Secrets handles** (references only; actual secret retrieval is separate and bounded)

> Pin: sources are explicit (no “discover latest config”).

### 10B) Snapshot Assembler

Constructs a single immutable **ConfigSnapshot** with:

* `policy_rev`
* `wiring_rev`
* `profile_name` (local/dev/prod)
* `build_id` (the DLA binary identity)
* normalized policy objects (canonical ordering so it can be hashed)
* explicit feature flags (pointer enabled, attachments enabled, etc.)

### 10C) Validator & Compatibility Gate

Validates every snapshot before it can be used:

* schema validation of the snapshot itself
* required fields present (no “defaults that hide missing config”)
* semantic checks like:

  * event family mappings exist (`DecisionResponse`, `ActionOutcome`)
  * audit completeness template is internally consistent (no impossible requirements)
  * attachment policy doesn’t violate “no scanning” constraints
* optional: signature/digest verification if you treat policy bundles as signed artifacts

**Fail-closed rule:** if the snapshot can’t be validated, it is rejected.

### 10D) Last-Known-Good Cache

Stores the most recent **valid** snapshot:

* in memory (fast)
* optionally on local disk (survive restarts)
* optionally in a small “config state” record (for audit)

**Runtime rule:** if refresh fails, keep last-known-good; never fall back to silent defaults.

### 10E) Atomic Snapshot Switcher

Implements the “single snapshot per unit of work” discipline:

* exposes `get_current_snapshot()` (for new units of work)
* returns an immutable handle that modules hold for the lifetime of:

  * one event processing
  * one ops job plan/execution
  * one reindex/export run

**Pin:** an event cannot observe half of rev A and half of rev B.

### 10F) Distribution Interface (J16)

A lightweight interface used by all nodes:

* nodes request a snapshot at the start of processing
* nodes never read raw configs directly
* nodes include snapshot metadata (`policy_rev/profile/build_id`) in their outputs (records/receipts/telemetry)

### 10G) Change Journal (optional but useful)

Records snapshot transitions as an internal “config change fact”:

* “rev changed from A → B at time T”
* reason/source
* validation outcome

This is *not* a new truth plane—just a visibility rail.

## Failure semantics (pinned)

* **Startup:** if no valid snapshot exists → DLA should not run (fail closed).
* **Runtime refresh fails:** continue on last-known-good + emit “config_stale” telemetry; ops may drain/restart if staleness breaches policy.
* **Bad new snapshot:** reject it, keep last-known-good, alert.

## Environment ladder knobs (what changes per env)

* profile selection (`local|dev|prod`)
* policy strictness (e.g., optional vs required evidence attachments)
* export permission gates
* retention/backfill allowances
* pointer enablement

But the *mechanism* stays identical everywhere: snapshot → validate → atomic switch → recorded rev.

---

# [11] Observability & Telemetry

## Mission

Emit **non-blocking, production-grade telemetry** (metrics, traces, logs) so DLA is operable and auditable, while guaranteeing:

* **telemetry never gates correctness**
* correlation is always possible (“why did this happen?”)
* signals are consistent across environments (only volume/sampling differs)

## Internal subnetworks (machinery)

### 11A) Context & Correlation Manager

Maintains a structured context object for each unit of work:

* `policy_rev/profile/build_id` (from [10])
* `context_pins` (when present)
* `audit_record_id` (once computed)
* `decision_anchor` (when applicable)
* `bus_coord` evidence (stream/partition/offset)
* trace propagation fields (if present)

> Pin: **event_id is high-cardinality** — use it in traces/logs, not as a metric label.

### 11B) Metrics Registry

Defines a stable set of counters/histograms/gauges, including minimum “must-have”s:

* consumer lag per partition
* ingest throughput
* canonical write rate vs quarantine write rate (by reason)
* NOOP/dedupe rate
* writer commit latency + failures
* index apply latency + failures (if enabled)
* pointer publish failures (if enabled)
* evidence verification verdicts (if enabled)
* ops job start/finish + durations (exports/reindex/replay)

Includes cardinality controls (bucketed reason codes, bounded label sets).

### 11C) Trace Instrumentation Layer

Creates spans across the internal spine:

* ingest → route → admissibility → idempotency → commit → index → checkpoint ack
  Propagates any incoming trace context; otherwise creates a new trace.

### 11D) Structured Logging Layer

Outputs JSON/structured logs for boundary decisions:

* canonical_commit (record ref + ids)
* quarantine_commit (reason + missing_fields + correlation)
* supersedes_accept/reject
* index_apply_failed
* pointer_publish_failed
* config_rev_changed / config_refresh_failed
* ops job receipts (export/reindex/replay)

**Pin:** no raw payload dumps; logs must remain by-ref safe.

### 11E) Exporter & Transport

Routes telemetry out:

* OTLP exporter (dev/prod)
* stdout/stderr (local)
* optional buffering queue

### 11F) Sampling, Rate Limiting, and Drop Policy

Ensures telemetry failures never stall the pipeline:

* bounded buffers
* drop on overflow (with a counter)
* adaptive sampling for traces
* log throttling for repeated errors

### 11G) Health Signal Synthesizer (output only)

Produces health summaries for dashboards/alerts:

* “writer unhealthy”
* “index lagging”
* “quarantine storm”
* “config stale”

**Pin:** DLA does not *consume* its own telemetry as a control input (no hidden feedback loop).

## Failure semantics (pinned)

* OTLP down → buffer (bounded) then drop; never block ingest/commit/checkpoint.
* Telemetry overload → rate limit + drop with counters; never block.
* Missing correlation fields → still emit what’s available; don’t invent.

## Environment ladder knobs

* sampling rates (traces)
* verbosity levels (logs)
* exporter destinations (OTLP vs local)
* alert thresholds/SLOs
  But the same signal names/meaning remain consistent.

---

# The coupling between [10] and [11] (important)

**[11] tags everything with [10]’s snapshot identity** (`policy_rev/profile/build_id`).
That is what makes the platform’s governance question answerable:

> “Which rules were in force when this audit record was accepted/quarantined?”

---

If you want the clean next step: we can do a **consistency pass** where we walk node-by-node and confirm that every one of them (1–9) consumes [10] snapshots correctly and emits [11] telemetry without creating any “hidden gating” dependencies.

---

## USER: PAUSE FOR REFLECTION

Totally fair pause. Here’s the “mental compression” of what we just illuminated — so you (and I) keep the shape in our heads without drifting.

## The real complexity isn’t “many boxes”

It’s that DLA is **two networks at once**:

1. **The truth spine** (must be correct under replay/crash)
2. **The operability planes** (must be useful, but never allowed to break truth)

Everything we designed is basically a disciplined separation of those two.

---

## The minimal spine (the part that *must* work)

If you delete every optional feature and every nice-to-have surface, DLA still stands as:

**EB → [1] → [2] → [3] → [4] → [5] → checkpoints**

* **[5] Writer** creates durable truth using a single commit boundary (root commit object).
* **[1] Ingest** advances offsets only after Writer proof (AckTicket).
* **[3] Admissibility** ensures we never write half-truth audit: canonical or quarantine.
* **[4] Idempotency/Corrections** enforces: NOOP duplicates, explicit supersedes, no forks, orphan outcomes don’t block.
* **[2] Router** is the canonical-envelope boundary interpreter.

That’s the “engine room.” Everything else exists to make that engine room usable in production.

---

## Why the network feels “complex”

Because it deliberately handles production reality:

* **At-least-once delivery + crashes** ⇒ L1 loop (write-then-checkpoint + idempotency)
* **Schema drift / malformed events** ⇒ quarantine without wedging partitions
* **Corrections without overwriting** ⇒ supersedes chain + current/head stabilization (L4)
* **Out-of-order outcomes** ⇒ orphan evidence + later reconciliation (still append-only)
* **Index/pointer failures** ⇒ must not stall truth (non-joins N7/N8)
* **Governed ops** ⇒ basis-driven reindex/export/replay with receipts (L5)
* **Policy changes** ⇒ single snapshot per unit of work; visible revs (L6)
* **Optional evidence attachments** ⇒ keyed verification with PASS discipline, bounded retries (L2)
* **Optional pointer distribution** ⇒ derivative plane with deterministic event IDs (L3)

So the complexity is basically “we refused to hand-wave production.”

---

## The two major “drift-killer ideas” we pinned

If you remember only these, you won’t drift:

1. **Truth is immutable, and commit is binary**
   Root commit object exists ⇒ record is committed.
   Anything else is staging/noise. No overwrites, only supersedes.

2. **Progress is only allowed after truth**
   Offsets advance only after durable canonical/quarantine/NOOP evidence exists.
   Everything else (indexing, pointers, verification) is non-gating.

Those two ideas are why the network stays coherent even as it scales.

---

## The “complexity budget” is controlled

We kept it bounded by doing this:

* **Opaque boxes first** (outer network, then inner nodes)
* **Joins/paths/loops before internals**
* **Non-joins explicitly listed** (so we never accidentally invent backchannels)
* **Optional subsystems clearly isolated** ([8], [9]) so they can’t infect the spine
* **Environment ladder discipline** via [10] snapshots and [11] non-blocking telemetry

So even though it’s a large network, it’s not “spaghetti” — it’s layered.

---

If you want, I can also give you a single sentence that defines “done” for DLA design at this stage:

**We have a DLA whose truth spine is replay-safe and append-only, whose derived planes are rebuildable and non-gating, whose ops actions are basis-driven and receipted, and whose optional enrichments are keyed and bounded — all consistent across the environment ladder.**

---