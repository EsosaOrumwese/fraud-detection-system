## IG1 — Charter & Boundaries: Section Header Plan

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (IG1)
0.2 Status, version, date (UTC)
0.3 Designer vs implementer roles (GPT-5.2 Thinking / coding agent) 
0.4 Reading order (README/CONCEPTUAL → IG1 → IG2…IG5 → contracts) 

---

### 1) Purpose and scope (Binding)

1.1 Why Ingestion Gate exists (platform trust boundary; “admit or quarantine—never maybe”)
1.2 What IG guarantees at the boundary (canonical, schema-valid, joinable, replay-safe, auditable)
1.3 In-scope responsibilities (high level)
1.4 Out-of-scope list (explicit non-goals)

---

### 2) Authority boundaries (Binding)

2.1 IG is system-of-record for: admission outcomes, quarantine decisions, dedupe outcomes, receipts, post-gate admitted record form
2.2 IG is **not** authoritative for: engine/world truth, business meaning, labels correctness, features/decisions, training
2.3 “Reference vs assert” rule (IG may consult registries/refs as evidence; must not rewrite upstream truth)

---

### 3) Core invariants (“IG laws”) (Binding)

3.1 Deterministic per-event outcome: **ADMITTED / QUARANTINED / DUPLICATE**
3.2 No silent fixing (invalid/unknown/missing → quarantine with reason)
3.3 Joinability required (pins must be present or enriched under explicit policy)
3.4 Schema authority enforced (unknown schema version → quarantine/reject; never guess)
3.5 Replay safety (dedupe + receipts make retries/duplicates non-destructive)
3.6 “Accepted implies durable” (no admitted receipt without durable admitted record)
3.7 Time semantics preserved (`event_time` ≠ `ingest_time`; no overwrite)
3.8 Quarantine must carry evidence pointers + raw input reference (by-ref preferred)
3.9 Overload posture is explicit and observable (buffer/fail/shed-load; never silent drop)

---

### 4) Placement in platform and boundary map (Binding)

4.1 Upstream producers are untrusted until validated (engine stream, decisions/actions, labels/case, others)
4.2 Downstream consumers treat admitted records as trustworthy inputs (because the gate applied)
4.3 Read-only dependencies IG may consult (schema registry, run facts surface, dedupe index)
4.4 SR relationship (IG may enrich only via `run_facts_view_ref` and only from READY runs if enrichment is allowed)

---

### 5) Minimal objects and terminology (Informative)

5.1 Canonical envelope (pins + schema ref/version + timestamps)
5.2 Receipt (system-of-record acknowledgement)
5.3 Quarantine record (reason + evidence + raw input ref)
5.4 Admitted event record (post-gate canonical form + ingestion stamp)
5.5 Dedupe key + dedupe scope (what “same event” means)
5.6 Reason codes / retryability flags (controlled vocabulary concept)

---

### 6) IG v1 posture (Binding-ish)

6.1 “Deep spec, few files” posture (IG1–IG5 + 2 schema files)
6.2 Trust boundary posture statement (what “admitted” means in v1 at a sentence level)
6.3 Local vs deployed semantics: same outcomes given same inputs + policies (mechanics may differ)

---

### 7) Assumptions and prerequisites (Binding)

7.1 Rails conventions assumed (identity pins + PASS/no-read discipline)
7.2 Scenario Runner provides run readiness + join surface *by-ref* (no SR internals assumed)
7.3 Repo/path conventions apply where relevant (e.g., `fingerprint={manifest_fingerprint}`)

---

### 8) Open decisions and closure plan (Informative)

8.1 Decision log mechanics (DEC-IG-###; OPEN→CLOSED; where canonical wording lives)
8.2 IG1 does **not** close envelope/enrichment/schema/dedupe/commit decisions; it assigns closure to IG2–IG5/contracts
8.3 Quick table: decision group → where it closes (IG2/IG3/IG4/IG5/contracts)

---

### 9) Implementation freedoms (Informative)

9.1 Transport (HTTP/queue/file), sync vs async
9.2 Concurrency/topology, batching mechanics, storage backends
9.3 Validation tooling choice, dedupe index backend, caching strategies

---

### Appendix A) One-page orientation diagram (Informative)

A.1 Minimal boundary ASCII: Producers → IG → (Admitted / Quarantine / Receipts) → Downstream

### Appendix B) “IG laws” reviewer checklist (Informative)

B.1 10–15 bullets (e.g., “unknown schema version never guessed”, “accepted never without durable record”, “no silent drop under overload”)

---

## IG2 — Interface & Canonical Envelope: Section Header Plan 

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (IG2)
0.2 Status, version, date (UTC)
0.3 Reading order (IG1 → IG2 → IG3 → IG4 → IG5 → contracts)
0.4 Terms relied on (pins, envelope, enrichment, receipt, quarantine)

---

### 1) Purpose and scope (Binding)

1.1 What IG2 pins (boundary contract semantics; canonical envelope; enrichment posture)
1.2 What IG2 explicitly does not pin (transport/protocol, internal pipeline design)
1.3 Relationship to contracts (IG2 defines *required fields + rules*; schema files enforce shape)

---

### 2) External surfaces and submission semantics (Binding)

2.1 Ingest submission surface (transport-agnostic: “submit events”)
2.2 Single-event vs batch submission posture — closes **DEC-IG-016** (IG2 side)
2.3 Per-event outcomes requirement (recommended: always emit per-event receipt)
2.4 Optional batch summary posture (if allowed, define what it means and what it never replaces)
2.5 Correlation primitives at the boundary (e.g., `batch_id`, `ingest_attempt_id`, requester identity field if any)

---

### 3) Canonical event envelope (Binding)

> This section closes **DEC-IG-001** (required pins) and pins the envelope categories.

3.1 Envelope purpose: “make every admitted event joinable + auditable”
3.2 **Required identity pins** for admission (scenario/run/world/window) — closes **DEC-IG-001**
3.3 **Producer/event identity** fields (MUST include `producer_id`, `event_type`, `event_id`; define `event_id` uniqueness scope)
3.4 **Schema targeting fields** (contract kind/version or schema ref) *(details in §4)*
3.5 **Time semantics** at the boundary

* `event_time` (producer time)
* `ingest_time` (gate time; stamped by IG)
* “IG must not overwrite `event_time`” rule
  3.6 Required correlation fields (if any): `trace_id` / `request_id` / `source_seq` (keep minimal)
  3.7 Minimal “payload carriage” rule (payload by-ref vs embedded; posture only—details deferred)

---

### 4) Contract targeting, versioning, and extension posture (Binding)

4.1 Validation targeting rule — closes **DEC-IG-021**

* choose: (`kind` + `contract_version`) **or** `schema_ref` **or** an explicit mapping rule
  4.2 Unknown contract/version posture (behaviour stated here; detailed handling in IG3)
  4.3 Extension posture — closes **DEC-IG-007** (IG2 side)
* do you allow `extensions{}`? where?
* “additional properties allowed?” posture (tight vs loose)
  4.4 Compatibility statement (what v1 promises; what is allowed to evolve)

---

### 5) Enrichment posture (Binding)

> This is where you close **DEC-IG-002** and **DEC-IG-004**, and pin the precedence/mismatch behaviour (**DEC-IG-003**).

5.1 Is enrichment allowed? (pins resolved via `run_facts_view_ref`) — closes **DEC-IG-002**
5.2 If enrichment is allowed: required `run_facts_view_ref` shape (by-ref)
5.3 Precedence rule: event pins vs run context pins — closes **DEC-IG-003** (policy wording)
5.4 Pin mismatch rule (mismatch → quarantine with `PIN_MISMATCH` + evidence pointers) — closes **DEC-IG-003** (behaviour; receipts detailed in IG4)
5.5 Readiness requirement for enrichment (run_ref must resolve to READY) — closes **DEC-IG-004**
5.6 Enrichment failure handling (run_ref missing/unresolvable/not READY → quarantine reason category)

---

### 6) Interface-level outcome objects (Binding-ish)

> Not the full receipt/quarantine spec (that’s IG4), but IG2 should pin the *types* and the minimum semantics.

6.1 Outcome types (at least): `ADMITTED`, `QUARANTINED`, `DUPLICATE`
6.2 Per-event receipt is mandatory (even in batch submissions)
6.3 Receipt must include: outcome, correlation keys, and pointers (admitted ref or quarantine ref)
6.4 Reason codes exist as a controlled vocabulary (final set closed in contracts + IG4)
6.5 Retryability flag posture (present on receipts; semantics pinned in IG4)

---

### 7) Security / privacy boundary notes (Binding-ish, minimal)

7.1 What IG must never accept/emit (e.g., secrets in cleartext; policy-dependent)
7.2 Tokenization posture (if any) is declared here but specified later (IG3/IG4 if relevant)

---

### 8) Open decisions and closure plan (Informative)

8.1 Decisions IG2 **closes**: DEC-IG-001, 002, 004, 021 (+ IG2 side of 003, 007, 016)
8.2 Decisions IG2 **defers**: validation scope/unknown schema handling (IG3), dedupe (IG4), commit/routing (IG5), reason code set (contracts + IG4)

---

### 9) Implementation freedoms (Informative)

9.1 Transport/protocol, sync/async, ordering guarantees
9.2 Batch sizing, concurrency, retry mechanics (internal)
9.3 Storage formats and backends (as long as boundary semantics hold)

---

### Appendix A) Minimal examples (Informative)

A.1 Minimal single-event ingest example (envelope-only)
A.2 Minimal batch ingest example (per-event receipts)
A.3 Example: enrichment allowed (run_ref present)
A.4 Example: pin mismatch → quarantine

### Appendix B) Contract map (v1) (Informative)

B.1 Mapping from IG2 objects → `$defs` names in `ig_public_contracts_v1.schema.json`
B.2 Required fields checklist (the short “must-have” list the implementer uses)

---

## IG3 — Validation & Normalisation Policy: Section Header Plan

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (IG3)
0.2 Status, version, date (UTC)
0.3 Reading order (IG1 → IG2 → IG3 → IG4 → IG5 → contracts)
0.4 Terms relied on (validation scope, schema authority, normalization, tokenization, evidence)

---

### 1) Purpose and scope (Binding)

1.1 What IG3 pins (validation posture + “never guess” rules + allowed transforms) 
1.2 What IG3 leaves flexible (validator library, caching, performance strategy) 
1.3 Relationship to other IG docs (IG2 defines envelope + targeting; IG3 defines validation rules; IG4 defines receipts/quarantine behaviour; IG5 defines commit semantics)

---

### 2) Decision closure list (Binding)

> IG3 is where these are **CLOSED** (canonical wording lives here; shape enforced in contracts). 

2.1 **DEC-IG-005 — Validation scope** (envelope-only vs envelope+payload) 
2.2 **DEC-IG-006 — Unknown schema version handling** (quarantine vs reject vs other; “never guess”) 
2.3 **DEC-IG-011 — Allowed normalization transformations** (explicit allowlist) 
2.4 **DEC-IG-012 — Tokenization/security posture at ingress** (what + how audited) 
2.5 **DEC-IG-007 — Extension/compatibility posture** (IG3 side: how extensions affect validation) 

---

### 3) Validation scope (Binding) — closes DEC-IG-005

3.1 Chosen posture (one sentence) 
3.2 What is validated in-scope:

* envelope fields (pins, schema targeting fields, timestamps)
* payload fields (if enabled)
  3.3 What is explicitly *not* validated in v1 (if any)
  3.4 Implication for “admitted means…” statement (what downstream may assume)

---

### 4) Schema authority and lookup posture (Binding-ish)

4.1 What IG considers the authoritative source of “known schema versions” (conceptual registry) 
4.2 Lookup rules (cache allowed; semantics unchanged) 
4.3 Failure modes of lookup (registry unavailable vs inconsistent vs stale) and how IG treats them (behaviour only; retry mechanics left to implementer)

---

### 5) Unknown schema/version handling (Binding) — closes DEC-IG-006

5.1 Chosen outcome: quarantine vs reject (and how the distinction is surfaced) 
5.2 “Never guess / never downgrade” rule (explicit) 
5.3 Required evidence fields when unknown (what must be recorded for audit) 

---

### 6) Extension and compatibility posture in validation (Binding) — closes DEC-IG-007 (IG3 side)

6.1 If `extensions{}` is allowed: where it is allowed and how it is validated (ignored vs structurally validated)
6.2 Additional-properties posture (strict vs permissive) and what it means for “schema-valid” claims
6.3 Forward/backward compatibility rule of thumb for v1 (what changes don’t break IG)

---

### 7) Normalisation / canonicalisation policy (Binding) — closes DEC-IG-011

7.1 Principle: **allowlist only** (everything else forbidden) 
7.2 Allowed transformations (explicit list; examples):

* whitespace trimming for specific string fields
* case normalization for enumerations (if allowed)
* numeric coercions (usually *forbidden* unless tightly defined)
* timestamp normalization rules (usually *forbidden* for `event_time` unless explicitly permitted)
  7.3 Forbidden transformations (explicit):
* changing pins
* overwriting `event_time` with `ingest_time` 
* “best-effort” filling missing required fields
  7.4 Audit requirement: how IG records which normalisations were applied (field name + transform id)

---

### 8) Security / tokenization posture (Binding-ish) — closes DEC-IG-012

8.1 Does IG tokenize/mask at ingress in v1? (yes/no)
8.2 If yes:

* which fields/classes of fields
* what tokenization method category (conceptual only)
* what must be recorded as evidence/audit (without leaking secrets)
  8.3 If no: explicit statement of deferral (e.g., handled by a centralized security layer) and what IG still must enforce (e.g., “no secrets in clear” posture)

---

### 9) Evidence recording requirements for validation failures (Binding)

9.1 Minimum evidence payload for:

* schema invalid (envelope)
* schema invalid (payload, if enabled)
* unknown schema version
* normalization forbidden / failed
* security violation (if applicable)
  9.2 Where evidence must appear (receipt pointer vs quarantine record content) — *behavioural expectation only; full receipt schema is IG4*
  9.3 “By-ref preferred” for raw input evidence pointers (no copying huge payloads) 

---

### 10) Local vs deployed semantic equivalence (Informative → Binding if you want)

10.1 Same inputs + same policies + same contract registry state ⇒ same outcomes 
10.2 What is allowed to differ (locator types, throughput, batching), without semantic drift

---

### 11) Implementation freedoms (Informative)

11.1 Validator library choice, error formatting, caching strategy 
11.2 Registry access mechanics (API vs local bundle), refresh cadence
11.3 Parallelism, batching, and performance optimizations (must not change outcomes)

---

### Appendix A) Examples (Informative)

A.1 Unknown schema version → quarantine evidence example 
A.2 Schema invalid (envelope) → evidence example
A.3 Schema invalid (payload) → evidence example (if payload validation enabled)
A.4 Normalisation applied list example (show `normalisation_applied: []`) 

### Appendix B) “Decision closure table” (Binding-ish)

B.1 DEC-IG-005/006/011/012/007: final CLOSED wording + pointer to the exact section that closes it 

---

## IG4 — Dedupe, Receipts, Quarantine: Section Header Plan 

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (IG4)
0.2 Status, version, date (UTC)
0.3 Reading order pointers (IG2 ⇄ IG3 ⇄ IG4; IG5 touchpoints)
0.4 Terms relied on (dedupe key, scope, receipt, quarantine, retryable)

---

### 1) Purpose and scope (Binding)

1.1 What IG4 pins (dedupe semantics; receipt semantics; quarantine taxonomy behaviour) 
1.2 What IG4 leaves flexible (dedupe backend, locking strategy, storage/query mechanics) 
1.3 Relationship to other IG docs

* IG2 defines envelope + targeting + enrichment posture
* IG3 defines validation/normalisation rules
* IG4 defines **outcomes + receipts + quarantine** and dedupe semantics
* IG5 defines commit/atomicity, routing keys, retention, overload policy

---

### 2) Decision closure list (Binding)

> IG4 is where these are **CLOSED** (with canonical wording). 

2.1 **DEC-IG-008 — Dedupe key definition (“same event”)** 
2.2 **DEC-IG-009 — Dedupe scope** 
2.3 **DEC-IG-010 — Duplicate behaviour** (pointer-to-original preferred) 
2.4 **DEC-IG-018 — Quarantine reason code set + retryability flags (behaviour)** *(shape finalized in contracts)* 
2.5 **DEC-IG-019 — Minimum audit fields (must log / must metric)** *(IG4 closes the per-event fields; IG5 may add storage/indexing specifics)* 

---

### 3) Outcome model (Binding)

3.1 Canonical per-event outcomes (exact enum): **ADMITTED / DUPLICATE / QUARANTINED** 
3.2 Determinism rule: for the same event under the same policies, outcome must be stable
3.3 Outcome precedence rules (if multiple issues apply): e.g., validation failure beats dedupe; pin mismatch beats dedupe (pin exact ordering)
3.4 What downstream is allowed to infer from each outcome (high-level)

---

### 4) Dedupe key definition (Binding) — closes DEC-IG-008

4.1 Chosen dedupe key components (field list; no ambiguity) 
4.2 Allowed alternative posture (if any): content-hash dedupe for specific producers (explicit allowlist) 
4.3 Dedupe key canonicalization rules (what normalization is applied **for the key only**, if any; must not contradict IG3)
4.4 Evidence recording: dedupe key must be present in receipts and/or admitted record stamp

---

### 5) Dedupe scope and retention window (Binding) — closes DEC-IG-009

5.1 Chosen scope (one): per-run vs global vs time-bounded vs per-producer 
5.2 If time-bounded: define the window in policy terms (not implementation)
5.3 Interaction with run pins: whether `run_id` is part of dedupe identity
5.4 Dedupe scope implications for replay and duplicates across runs

---

### 6) Duplicate behaviour (Binding) — closes DEC-IG-010

6.1 Canonical duplicate behaviour statement 
6.2 Required semantics on duplicate:

* no second admitted record write
* emit **DUPLICATE receipt**
  6.3 Pointer posture (preferred): duplicate receipt points to the original admitted record ref 
  6.4 What is recorded about the “first-seen” event (fields required to support reconciliation)
  6.5 Duplicate receipt idempotency (reprocessing the same duplicate yields the same pointer/outcome)

---

### 7) Receipt semantics (Binding)

7.1 Receipt is IG’s system-of-record for intake outcomes (definition) 
7.2 Receipt emission rule: **one receipt per event** (including in batches) 
7.3 Minimum receipt fields (must-have list), covering:

* outcome enum
* correlation keys (`ingest_attempt_id`, optional `batch_id`) 
* producer identity + event identity (`producer_id`, `event_type`, `event_id` or equivalent from IG2)
* dedupe key + dedupe scope identifier (or enough to reproduce it)
* pins (scenario/run/world/window)
* timestamps (`ingest_time`, optional latency)
* pointers: `admitted_record_ref` OR `quarantine_record_ref` (and `original_admitted_record_ref` for duplicates) 
* reason code + retryable flag when not admitted
  7.4 “Accepted implies durable” acknowledgement rule (semantic statement; mechanism deferred to IG5) 
  7.5 Receipt immutability posture (receipts are append-only facts; corrections create new receipts, not edits)

---

### 8) Quarantine semantics (Binding)

8.1 Quarantine record definition and purpose 
8.2 What must be stored “by-ref” (raw input payload ref; validation evidence; context refs) 
8.3 Minimum quarantine record fields:

* reason code(s)
* retryable flag
* evidence pointers (schema errors, pin mismatch evidence, enrichment failure evidence)
* correlation keys and pins
* raw input reference (and optionally a redacted preview) 
  8.4 Quarantine invariants:
* quarantine must never be silent
* quarantine must never block receipts (receipt still emitted)
* quarantine does not mutate the original input

---

### 9) Reason codes and retryability behaviour (Binding) — closes DEC-IG-018 (behaviour)

9.1 Controlled vocabulary concept (final enum set lives in contracts) 
9.2 Behavioural mapping: reason code → retryable? → terminal?
9.3 Required “top-level” categories (examples only here; final list in contracts):

* missing pins / pin mismatch
* schema invalid / unknown schema
* enrichment failure (if allowed)
* security/tokenization violation (if enabled)
* internal processing failure (distinguish from input invalid) 
  9.4 Multi-reason handling posture (single primary + optional secondary list)

---

### 10) Auditability minimums (Binding) — closes DEC-IG-019 (IG4 side)

10.1 Must-log fields per event (list) 
10.2 Must-metric aggregates (counts by outcome + reason; latency; per-producer health) 
10.3 Correlation rule: every log/metric line must be joinable to receipt via correlation keys
10.4 Privacy posture for audit data (avoid storing secrets; prefer refs; redaction if needed)

---

### 11) Interaction with enrichment / pin mismatch (Binding-ish)

11.1 If enrichment enabled: pin mismatch → quarantine with evidence pointers (rule restated here for outcome semantics) 
11.2 If enrichment disabled: missing required pins → quarantine reason category

---

### 12) Implementation freedoms (Informative)

12.1 Dedupe index backend choice (db/kv/log), locking strategy, caching 
12.2 Receipt transport/storage (event bus vs store vs both)
12.3 Evidence formatting and error message shapes (as long as reason codes + pointers exist)
12.4 Throughput optimizations (batching, parallelism) that must not change semantics

---

### Appendix A) Outcome/Receipt Map (v1) (Informative)

A.1 List of outcome objects (receipt types) and their minimum required fields 
A.2 Mapping to `ig_public_contracts_v1.schema.json` `$defs`

### Appendix B) Examples (Informative)

B.1 ADMITTED receipt example
B.2 DUPLICATE receipt example (with pointer-to-original) 
B.3 QUARANTINED receipt + quarantine record example (schema invalid)
B.4 QUARANTINED receipt + quarantine record example (pin mismatch / enrichment failure)

### Appendix C) Minimal ASCII sequences (Informative)

C.1 First-seen event → admit → receipt
C.2 Duplicate event → duplicate receipt pointing to original
C.3 Validation fail → quarantine record → quarantine receipt

### Appendix D) Decision closure table (Binding-ish)

D.1 DEC-IG-008/009/010/018/019: CLOSED wording + pointer to the section that closes each 

---

## IG5 — Commit, Routing, Ops & Acceptance: Section Header Plan 

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (IG5)
0.2 Status, version, date (UTC)
0.3 Reading order pointers (IG3/IG4 ⇄ IG5; contracts touchpoints)
0.4 Terms relied on (durable write, commit, routing, partition key, backpressure, retention)

---

### 1) Purpose and scope (Binding)

1.1 What IG5 pins (durability truth rules, routing/partition semantics, overload posture, acceptance scenarios) 
1.2 What IG5 leaves flexible (storage tech, exactly-once mechanisms, deployment topology) 
1.3 Relationship to other IG docs (IG5 consumes the outcomes/receipts model from IG4 and the validation posture from IG3)

---

### 2) Decision closure list (Binding)

> IG5 is where these are **CLOSED** (canonical wording lives here). 

2.1 **DEC-IG-013 — Commit semantics (accepted implies durable) details** 
2.2 **DEC-IG-014 - Receipt + record atomicity posture** 
2.3 **DEC-IG-015 - Partitioning/routing keys for admitted stream** 
2.4 **DEC-IG-020 - Backpressure/overload posture** 
2.5 **DEC-IG-017 - Receipt query surface (indexing/query posture)** 

---

### 3) Commit semantics (Binding) — closes DEC-IG-013

3.1 Definitions: “durable admitted record”, “durable receipt”, “durable quarantine record”
3.2 Core truth rule (restated): **never emit ADMITTED receipt unless admitted record is durably written** 
3.3 Allowed asymmetry (explicit): admitted record may exist without receipt (receipt can be regenerated)
3.4 Minimal atomicity posture (v1): what must be ordered/guarded even if storage isn't transactional - closes DEC-IG-014
3.5 Commit ordering rules per outcome:

* ADMITTED: write admitted → write receipt
* DUPLICATE: read pointer → write duplicate receipt (no admitted write)
* QUARANTINED: write quarantine → write receipt
  3.6 Idempotency rules at commit time (safe retries; no duplicate admitted record writes)
  3.7 What must be recorded for audit about commits (attempt counters, storage refs)

---

### 4) Routing and partition key policy (Binding) - closes DEC-IG-015
4.1 Purpose of routing policy (joinability, scaling, locality, replay)
4.2 Canonical partition key(s) for admitted records (must include enough pins to join; e.g., `run_id` and/or `manifest_fingerprint`) 
4.3 Canonical partition keys for receipts and quarantines (may differ; must remain joinable)
4.4 Ordering guarantees (if any) and explicit non-guarantees
4.5 Consumer guidance: “do not assume order unless stated”

---

### 5) Storage and reference posture (Binding-ish)

5.1 By-ref preference for large payloads and raw evidence (restated) 
5.2 Reference format requirements (ref + optional digest + schema version)
5.3 Addressing convention touchpoint: incorporate `fingerprint={manifest_fingerprint}` when stored under world roots
5.4 Immutability posture for stored objects (admitted/quarantine/receipt)
5.5 Indexing posture (optional): whether IG maintains a "receipt index" or "quarantine index" and what it means - closes DEC-IG-017
---

### 6) Backpressure / overload posture (Binding) - closes DEC-IG-020
6.1 Overload detection signals (queue depth, latency, error rates—conceptual)
6.2 Chosen posture under overload (one or more, explicitly ordered):

* buffer (bounded)
* fail-fast with retryable receipt
* shed-load with explicit “OVERLOADED” quarantine/reject category (never silent) 
  6.3 What must be emitted/logged under overload (reason code + counts)
  6.4 Interaction with upstream retry behaviour (how to avoid thundering herd—conceptual)

---

### 7) Operational posture (Informative → Binding if desired)

7.1 SLOs (latency/throughput) as targets (can be non-binding if you prefer)
7.2 Deployment modes (local/dev vs prod) and "policy equivalence" rule (must not change semantics)
7.3 Failure domains (what failures affect single producer vs whole gate)
7.4 Runbooks minimal set (what an operator must be able to answer from metrics/logs)

---

### 8) Retention and archival (Informative - Binding if desired)
8.1 Minimum retention for:

* admitted records
* receipts
* quarantine records
* dedupe index entries
  8.2 Archival posture (what can be compacted; what must remain queryable)
  8.3 Legal/compliance notes (if applicable; keep minimal and generic)

---

### 9) Acceptance scenarios (Binding)

> “Tests as intent” for the implementer.

9.1 Happy path: valid event → admitted record durable → ADMITTED receipt
9.2 Duplicate path: same dedupe key → no admitted rewrite → DUPLICATE receipt points to original
9.3 Quarantine path: schema invalid → quarantine record durable → QUARANTINED receipt with reason + evidence refs
9.4 Enrichment pin mismatch path (if enabled): mismatch → quarantine + evidence
9.5 Unknown schema version path: quarantine/reject per IG3 posture, with correct reason code
9.6 Overload path: explicit overload outcome; no silent drops; receipts emitted appropriately
9.7 Retry safety path: reprocessing same event after transient failure yields same final outcome and no duplicates
9.8 Auditability path: from receipt you can locate admitted/quarantine record and raw input ref

---

### 10) Mapping to contracts (Informative)

10.1 Which IG5 fields/behaviours are enforced by `ig_public_contracts_v1` and `ig_admitted_record_v1`
10.2 Any extension slots left intentionally open

---

### Appendix A) Reference templates (Informative)

A.1 Example admitted record ref
A.2 Example quarantine record ref
A.3 Example receipt ref
A.4 (Optional) Example of how `fingerprint={manifest_fingerprint}` appears in paths

### Appendix B) Minimal ASCII sequences (Informative)

B.1 ADMITTED commit ordering
B.2 QUARANTINED commit ordering
B.3 DUPLICATE handling sequence
B.4 Overload behaviour sequence

### Appendix C) Admitted Record Contract Map (v1) (Informative)

C.1 Mapping to `contracts/ig_admitted_record_v1.schema.json` (`$defs` names)
C.2 Object inventory (v1): `AdmittedEventRecord`, `IngestionStamp` (and any optional `PartitionKeys`)
C.3 Required fields only per object (pins + schema refs + ingest stamp minimums)
C.4 Payload posture (embedded vs by-ref pointer) and where it is pinned (IG3/IG5)
C.5 Immutability notes for admitted records and stamps (snapshot semantics)

### Appendix D) Decision closure table (Binding-ish)

D.1 DEC-IG-013/014/015/017/020: CLOSED wording + pointer to closing section

---