# Scenario Runner - SR1..SR5 Section Header Plans
#
# Authoring workflow notes (informative)
# - Designer/spec authoring model: GPT-5.2 Thinking
# - Implementer (coding agent): GPT-5.2-Codex
# - No separate "contracts plan" doc: SR2 Appendix C (Contract Map v1) + SR5 Appendix C (Ledger Contract Map v1) serve as the plan.
# - Recommended authoring order (fast): SR1 -> SR2 + SR5 -> SR3 + SR4 -> generate `contracts/*.schema.json`.
# - Once SR2+SR5 Contract Maps are stable, formalize schemas immediately to avoid prose->schema drift.

## SR1 - Charter & Boundaries: Section Header Plan

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (SR1)
0.2 Status, version, date (UTC), owner, implementer
0.3 Reading order (SR1 → SR2 → SR3 → SR4 → SR5 → contracts)
0.4 Related authoritative materials (Rails conventions, Engine interface pack)

---

### 1) Purpose and scope (Binding)

1.1 Why Scenario Runner exists (run-orchestrator + run-ledger)
1.2 What SR produces as a black box (ledger + readiness truth)
1.3 In-scope responsibilities (named, concise)
1.4 Non-goals / explicit out-of-scope list (to prevent “SR does everything” creep)

---

### 2) Authority boundaries (Binding)

2.1 SR is system-of-record for: run identity, readiness, join surfaces, lifecycle status
2.2 SR is **not** authoritative for: engine content, feature computation, decisioning, labels, training
2.3 What SR is allowed to *reference* vs what it may *assert*
2.4 Boundary rule: SR must not re-derive upstream truths (engine remains a black box)

---

### 3) Core invariants (Binding)

> These are the “laws” SR must never break.

3.1 Identity pins carried everywhere (scenario_id/run_id + world pins + explicit window key if present)
3.2 SR never lies about readiness (no READY without required evidence/gates)
3.3 Readiness monotonicity (READY never revoked; corrections = new run)
3.4 Ledger is audit-safe (plan vs record vs facts vs status; mutation rules)
3.5 Idempotency under duplicates/retries (no duplicate side effects for same logical run)
3.6 No hidden time dependence (“now” must be converted to explicit window key and recorded)
3.7 Deterministic selection rule if SR is allowed to “choose” (and must be recorded)
3.8 Contract/version discipline (no ambiguous shapes; consumers never guess)

---

### 4) Placement in platform and boundary map (Binding)

4.1 Upstream callers (who can trigger SR; what SR expects of them)
4.2 Engine boundary (SR ↔ Data Engine: invoke or reuse; completion evidence concept)
4.3 Downstream consumers (who relies on SR as the source of truth)
4.4 Storage/transport surfaces (conceptual only: artifact store + optional event bus)
4.5 “SR is not the pipeline”: SR conducts + records; others compute

---

### 5) Minimal objects and terminology (Informative)

5.1 Scenario (intent)
5.2 Run (execution instance + ledger)
5.3 World and world pins (`manifest_fingerprint`, `parameter_hash`)
5.4 Run identity pins (`scenario_id`, `run_id`)
5.5 READY, PASS artifacts, gates, quarantine
5.6 Idempotency key (interface-level meaning only; details deferred)

---

### 6) SR v1 posture (Binding-ish)

6.1 Local vs deployed semantic equivalence (mechanics may differ, meaning must not)
6.2 Minimal lifecycle states SR will recognize (names only; detailed transitions deferred to SR4/SR5)
6.3 What SR guarantees to downstream in v1 (joinability + readiness truth + audit trail)

---

### 7) Assumptions and prerequisites (Binding)

7.1 Rails conventions assumed (identity + “no PASS → no read”)
7.2 Engine treated as black box; SR depends only on engine interface boundary
7.3 Artifact addressing convention (refer to platform convention; do not invent “latest by timestamp”)

---

### 8) Open decisions (Informative)

8.1 Decision list SR1 does **not** close (e.g., exact run equivalence rule, exact READY gate set)
8.2 Where each decision will be closed (SR3/SR4/SR5 or contract schema)

---

### Appendix A) One-page orientation diagram (Informative)

A.1 Minimal boundary ASCII diagram (Caller → SR → Engine → SR → Downstream)
A.2 Legend (pins, gates, ledger artifacts)

---

### Appendix B) Example “SR laws” checklist (Informative)

B.1 10–15 bullet checklist a reviewer can use to catch violations quickly

---

## SR2 — Interface Contract: Section Header Plan

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (SR2)
0.2 Status, version, date (UTC), owner, implementer
0.3 Reading order (SR1 → SR2 → SR3 → SR4 → SR5 → contracts)
0.4 Terminology pointer (SR1 §5) and shared rails assumptions

---

### 1) Interface overview (Binding)

1.1 What SR exposes (submit run / query status / consume readiness)
1.2 What SR must emit (ledger artifacts + readiness truth)
1.3 Stability promise: what downstream can rely on in v1

---

### 2) External surfaces (Binding)

2.1 **Invocation surface**: how a run is requested (conceptual; transport-agnostic)
2.2 **Observation surface**: how callers read run status / run ledger refs
2.3 **Notification surface**: how downstream learns “READY” (signal/event/artifact)
2.4 Surface invariants: every surface must carry identity pins

---

### 3) Input contract: `RunRequest` (Binding)

3.1 Required fields (minimum viable request)
3.2 Optional fields (allowed extensions)
3.3 Identity pins included at request time (who supplies vs SR mints)
3.4 World selection pins (explicit vs selection rule)
3.5 Window fields + minimal validation (shape only); meaning pinned in SR3 (DEC-SR-004/005)
3.6 Mode hints (if any): reuse/realise/rebuild/resume (names can be abstract; semantics only)
3.7 Validation rules (what makes a request invalid)
3.8 Defaulting rules (if a field is omitted, what SR does-must be recorded)

---

### 4) Output contracts: what SR produces (Binding)

4.1 Canonical ledger artifacts (names + purposes):

* `run_plan`
* `run_record`
* `run_facts_view`
* `run_status`
  4.2 Readiness notification payload (`run_ready` or equivalent); READY meaning pinned in SR4
  4.3 Output invariants (identity pins present; joinability; monotonic readiness)
  4.4 Completion evidence pointers (refs only); verification standard pinned in SR4

---

### 5) Addressing and referencing rules (Binding)

5.1 Artifact addressing model (how downstream locates SR outputs)
5.2 Required path tokens / keys (including `fingerprint={manifest_fingerprint}` convention)
5.3 Reference types: "by-ref" vs "embedded" (SR should prefer refs)
5.4 Discoverability interface (locate status/facts); indexing semantics pinned in SR5

---

### 6) Error model and retryability (Binding)

6.1 Error taxonomy (categories SR will emit)
6.2 Retryability flags (retriable vs non-retriable)
6.3 Quarantine semantics (what it means and what must be recorded)
6.4 Caller-visible failure surfaces (how failures are observed)

---

### 7) Idempotency & duplicate handling (Binding)

7.1 Idempotency inputs (request_id/idempotency_key); run equivalence pinned in SR3
7.2 Duplicate submission behavior (no duplicate side effects; return existing run refs)
7.3 Concurrency rules (two callers racing; lease/lock concept at interface level)
7.4 Replay request surface (fields/options); replay meaning pinned in SR3

---

### 8) Versioning & compatibility (Binding)

8.1 Contract version fields (where version lives)
8.2 Backward/forward compatibility rules
8.3 Deprecation posture (how SR evolves without breaking downstream)
8.4 Validation targeting rule (pin here; referenced elsewhere)
    - preferred: self-describing `kind` + `contract_version`
    - alternative: binding path -> `$defs` mapping

---

### 9) Security / permissions (Binding-ish, keep minimal)

9.1 Who is allowed to request runs (role-level statement)
9.2 What SR records about the requester (audit fields)
9.3 No secret-dependent semantics (requests must be reproducible from recorded pins)

---

## Appendices (kept inside SR2, not separate folders)

### Appendix A) Example payloads (Informative)

A.1 Minimal `RunRequest` example
A.2 Example `run_facts_view` (the downstream join surface)
A.3 Example `run_ready` signal

### Appendix B) Minimal sequence sketches (Informative)

B.1 “Submit → Plan → Execute → READY” (happy path)
B.2 “Duplicate submit” (idempotency behavior)
B.3 “Invalid request” vs “dependency failure” distinction

### Appendix C) Contract Map (v1) (Informative)

C.1 Object inventory (v1): `RunRequest`, `RunReadySignal`, `FailureTaxonomy`, `ArtifactRef/Locator`, etc.
C.2 Required fields only per object (no optional narrative)
C.3 Enums referenced + where they are defined (SR3/SR4/SR5 vs local)
C.4 Compatibility / extension rules (e.g., `extensions{}` posture; additional properties posture)
C.5 Mapping from SR2 objects -> `$defs` names in `sr_public_contracts_v1.schema.json`
C.6 What SR2 intentionally defers to SR3/SR4/SR5 (normative meaning)

---

## SR3 — Identity, Pinning, Reuse, Replay: Section Header Plan

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (SR3)
0.2 Status, version, date (UTC), owner, implementer
0.3 Reading order pointers (SR2 ⇄ SR3; SR4/SR5 touchpoints)
0.4 Definitions relied on (scenario/run/world pins/window key) 

---

### 1) Purpose and scope (Binding)

1.1 What SR3 pins (determinism-critical choices) 
1.2 What SR3 explicitly does **not** pin (implementation freedoms) 
1.3 Inputs assumed from SR2 (RunRequest semantics) and rails

---

### 2) Decision closure list (Binding)

> SR3 is where these are CLOSED (referencing the decision IDs you listed). 

2.1 **DEC-SR-001** Run equivalence rule (“same run” definition)
2.2 **DEC-SR-002** ID minting posture (`scenario_id`, `run_id`)
2.3 **DEC-SR-004** Window key representation (e.g., `window_id` vs `{start,end,tz}` vs both)
2.4 **DEC-SR-005** “No hidden now” policy (who resolves “today”, how recorded)
2.5 **DEC-SR-006** World pins explicit vs SR-selection allowed
2.6 **DEC-SR-007** Deterministic selection rule (if selection allowed; tie-breakers; evidence)
2.7 **DEC-SR-008** Supported run modes in v1 (subset)
2.8 **DEC-SR-009** Evidence required for reuse (high level; SR4 defines READY gate set)
2.9 **DEC-SR-010** Replay semantics (what replay does + never does)

---

### 3) Run equivalence and idempotency posture (Binding)

3.1 Canonical definition of “same logical run” (equivalence keys)
3.2 How SR treats *field changes* (what forces a new run)
3.3 Interface idempotency posture choice (caller-keyed vs SR-derived vs persisted minting) 
3.4 Concurrency semantics at the identity level (two submits racing → same run resolution)

---

### 4) ID minting posture (Binding)

4.1 Source of `scenario_id` (caller-provided vs SR-derived vs registry lookup)
4.2 Source of `run_id` (caller-provided vs SR-minted vs derived)
4.3 Uniqueness scope and collision handling (what SR must guarantee)
4.4 What is recorded in the ledger about minting/derivation choices

---

### 5) Time/window semantics (Binding)

5.1 Window key: chosen representation (and why) 
5.2 “No hidden now” rule: resolution responsibility + required recording 
5.3 Ordering/comparability rule (needed for deterministic “latest by window”, if ever used) 

---

### 6) World pin posture (Binding)

6.1 Required pins: `parameter_hash`, `manifest_fingerprint` (required vs optional)
6.2 If SR may select `manifest_fingerprint`:

* deterministic selection rule
* tie-break rules
* what “evidence” must be recorded so selection is auditable
  6.3 Pin immutability for the run (when pins are “frozen”)

---

### 7) Run modes in v1 (Binding)

7.1 Supported modes list (subset for deadline)
7.2 Semantics per mode (short, behavioural definitions):

* REBUILD (force engine invocation)
* REUSE (reuse only with evidence)
* REPLAY (re-materialize outcomes from ledger)
* RESUME (if supported; otherwise explicitly out-of-scope) 
  7.3 Mode recording requirement (mode must be written to ledger)

---

### 8) Reuse rules (Binding)

8.1 Evidence-based reuse criteria (pins match + evidence exists)
8.2 What counts as “sufficient completion evidence” at SR3 level (SR4 pins READY gate set)
8.3 Reuse failure behaviour at the identity level (reuse → rebuild vs reuse → fail/quarantine depends on mode/policy)

---

### 9) Replay semantics (Binding)

9.1 One-sentence definition of replay (ledger-driven outcome re-materialization) 
9.2 Replay does (choose and pin): re-emit signal / re-register facts / re-verify (subset)
9.3 Replay never does (pin explicitly): no engine mutation, no “reinterpret latest”, no retroactive status flip
9.4 Replay determinism rules (same ledger → same outward result)

---

### 10) Mandatory recording in SR ledger (Binding)

10.1 What SR must record so SR3 choices are auditable:

* resolved equivalence key / idempotency posture
* minted/derived IDs
* resolved window key
* resolved/selected world pins (+ selection evidence if used)
* chosen run mode
* reuse vs rebuild decision + evidence pointers
  10.2 Where each item lives (run_record vs run_facts_view vs run_plan) (just mapping, no format)

---

### 11) Implementation freedoms (Informative)

11.1 Lookup mechanics (how existence/evidence is checked) 
11.2 Caching strategy
11.3 Replay scheduling mechanism
11.4 Storage backend differences (local vs deployed) — semantics must not change 

---

### 12) Deferred items and handoff to SR4/SR5 (Informative)

12.1 SR4 closes: READY gate set + verification standard + retry/quarantine posture
12.2 SR5 closes: addressing/discoverability/indexing details if needed

---

## Appendices (inline, per your deadline posture)

### Appendix A) Examples (Informative)

A.1 “Same request twice” examples (what changes / what doesn’t)
A.2 Example: SR-selected `manifest_fingerprint` + recorded evidence
A.3 Example: REUSE vs REBUILD decision recorded in ledger

### Appendix B) Minimal ASCII sequences (Informative)

B.1 Duplicate submit → same run resolution
B.2 REUSE path (no engine invoke)
B.3 REPLAY path (ledger → ready signal)

### Appendix C) Decision closure table (Binding-ish)

C.1 DEC-SR-001..010: CLOSED wording + pointer to the exact section that closes it

---

## SR4 — Gates, Verification, Retries, Failures: Section Header Plan

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (SR4)
0.2 Status, version, date (UTC), owner, implementer
0.3 Reading order pointers (SR3 ⇄ SR4; SR5 touchpoints)
0.4 Terms relied on (READY, PASS, quarantine, retryable, side-effect)

---

### 1) Purpose and scope (Binding)

1.1 What SR4 *must* pin for correctness/safety (READY truth, retry/quarantine posture)
1.2 What SR4 intentionally leaves flexible (retry mechanism, scheduling backend, polling vs callbacks)
1.3 Interfaces touched (SR2 outputs; engine receipt; downstream readiness consumption)

---

### 2) Decision closure list (Binding)

> SR4 **closes** these decisions (using your DEC IDs):

2.1 **DEC-SR-011 — Required PASS gate set for READY**
2.2 **DEC-SR-012 — Minimum verification standard**
2.3 **DEC-SR-013 — Partial readiness posture**
2.4 **DEC-SR-014 — Retry budget + classification**
2.5 **DEC-SR-015 — Quarantine vs fail-fast rules**
2.6 **DEC-SR-016 — Failure taxonomy categories (behaviour)** *(shape lives in contracts)*
2.7 **DEC-SR-003 — Side-effect idempotency keys (per effect kind)** *(behaviour; fields if needed)*
2.8 **DEC-SR-017 — Lifecycle state model + monotonic transitions** *(at least the run-status FSM; artifact immutability deferred to SR5)*

---

### 3) READY definition (Binding)

3.1 Canonical meaning of **READY** (single sentence)
3.2 **Required PASS artifacts set** (enumerated list; source = engine and/or SR-produced) — closes DEC-SR-011
3.3 “No READY without evidence” rule (what SR must point to when claiming READY)
3.4 Monotonicity rule: READY is final; corrections create new runs (tie to SR1 invariants)

---

### 4) Verification standard (Binding)

4.1 What SR verifies for each required gate — closes DEC-SR-012

* existence-only vs PASS-flag presence vs digest verification (pick v1 minimum)
  4.2 Verification inputs (where SR reads PASS evidence from)
  4.3 What happens when verification is inconclusive (treat as NOT READY; retry vs fail vs quarantine depends on DEC-SR-014/015)
  4.4 Verification audit requirements (what is recorded about checks performed + results)

---

### 5) Partial readiness posture (Binding)

5.1 Chosen posture — closes DEC-SR-013

* all-or-nothing READY **or** explicitly defined partial statuses
  5.2 If partial is allowed: allowed partial states + what downstream may do with them
  5.3 If partial is disallowed: enforce that only READY emits readiness signal; everything else blocks dispatch

---

### 6) Failure taxonomy and classification (Binding)

6.1 Final **failure categories** used by SR behaviour — closes DEC-SR-016 (behaviour)
(e.g., invalid request, missing prereq, dependency failure, internal failure, verification failure, conflict/lease)
6.2 Mapping: category → retryable? → quarantine? → fail-fast?
6.3 Minimum failure payload requirements in ledger/status (short message, category, retryable flag, causal dependency pointer)

---

### 7) Retry posture (Binding)

7.1 Retriable classes + non-retriable classes — closes DEC-SR-014
7.2 Retry budget (attempt counts) + backoff posture (coarse is fine)
7.3 Stop conditions (when SR must stop retrying and finalize FAILED/QUARANTINED)
7.4 Interaction with verification (re-verify gates after retry; never “assume READY”)

---

### 8) Quarantine vs fail-fast (Binding)

8.1 Quarantine definition (what it means operationally + for downstream) — closes DEC-SR-015
8.2 Quarantine triggers (e.g., repeated verification failures, inconsistent pins, corrupted evidence)
8.3 Quarantine outputs (what must be recorded; what signals must/ must not be emitted)
8.4 Unquarantine policy (likely “new run only”; avoid mutable flip-flops)

---

### 9) Side-effects and idempotency keys (Binding)

> This is where you prevent retries from duplicating effects — closes DEC-SR-003 (behaviour).

9.1 Enumerate SR side-effects (v1 list), e.g.:

* create/append `run_record`
* write/update `run_status`
* publish `run_ready_signal`
* trigger downstream dispatch (if SR does that)
* acquire/release run lease
  9.2 For each side-effect:
* **idempotency key** definition (what key makes it “the same effect”)
* dedupe rule (“at-most-once” vs “at-least-once with dedupe”)
* what is safe to repeat vs must be guarded
  9.3 Required ledger notes for each effect (so later audit can prove dedupe/guard happened)

---

### 10) Lifecycle state model (Binding)

10.1 Run status states (minimal enum) — closes DEC-SR-017 (run FSM)
10.2 Allowed transitions (monotonic, no flip-flops)
10.3 Terminal states and their meaning (READY / FAILED / QUARANTINED / CLOSED)
10.4 Who is allowed to transition state (SR only) and under what evidence

---

### 11) Dispatch gating (Binding-ish)

11.1 What SR is allowed to dispatch/trigger (if any)
11.2 Hard rule: **no dispatch unless READY** (or explicit partial-state rules if you chose partial readiness)
11.3 What SR must include in dispatch (pointer to `run_facts_view`)

---

### 12) Observability minimums (Informative → Binding if you prefer)

12.1 Required log fields (must include pins + run_id + attempt counters)
12.2 Required metrics (counts of READY/FAILED/QUARANTINED, retries, verification failures)
12.3 Trace correlation (run_id as the primary correlation key)

---

### 13) Deferred items / handoff to SR5 (Informative)

13.1 SR5 will pin: artifact immutability per artifact, addressing templates, “latest READY” indexing, retention
13.2 Contract schema alignment notes (FailureTaxonomy shape; RunStatus fields)

---

## Appendices (inline)

### Appendix A) Tables (Informative)

A.1 Gate list table: gate name → producer → evidence ref → verification method
A.2 Failure category table: category → retryable → quarantine? → terminal state

### Appendix B) Example sequences (Informative)

B.1 Happy path: verify gates → READY → emit readiness
B.2 Retry path: transient dependency failure → retries → READY
B.3 Quarantine path: inconsistent evidence → QUARANTINED → no dispatch
B.4 Duplicate invocation: same run → no duplicated side-effects

### Appendix C) “SR4 reviewer checklist” (Informative)

C.1 10–15 bullets to catch violations quickly (e.g., “READY without evidence pointer” is an automatic fail)

---

## SR5 — Ledger, Addressing, Discoverability, Acceptance: Section Header Plan

### 0) Document metadata (Informative)

0.1 Title, component path, doc type (SR5)
0.2 Status, version, date (UTC), owner, implementer
0.3 Reading order pointers (SR2/SR3/SR4 dependencies)
0.4 Terms relied on (ledger, artifact ref, digest, index, retention)

---

### 1) Purpose and scope (Binding)

1.1 What SR5 pins (joinability + auditability + “where do I find it?”)
1.2 What SR5 leaves flexible (storage backend, file formats, indexing implementation)
1.3 SR5 artifacts are the platform’s control-plane truth (not engine content)

---

### 2) Canonical SR ledger artifacts (Binding)

> This section answers: **what exists** and **what each artifact is for**.

2.1 `run_plan` — intended execution (what SR planned to do)
2.2 `run_record` — append-only execution log (what happened)
2.3 `run_facts_view` — **downstream join surface** (pins + refs + digests)
2.4 `run_status` — lifecycle state + timestamps + failure summary
2.5 `run_ready_signal` — notification payload (refers to `run_facts_view`)
2.6 Optional v1 artifacts (explicitly optional): attempt logs, dependency receipts, dispatch receipts

---

### 3) Minimum schema per artifact (Binding)

> Not full JSON Schema here (that lives in the single `contracts/` file), but the **minimum fields** SR guarantees.

3.1 Identity pins required on every artifact (scenario/run/world/window)
3.2 Required fields for `run_plan` (window, requested mode, intended steps, submission metadata)
3.3 Required fields for `run_record` (append-only entries, attempt counters, event timestamps, causal pointers)
3.4 Required fields for `run_facts_view` (**most strict**)

* resolved pins
* canonical “root refs” (engine outputs root + SR ledger root)
* required PASS evidence list (name/ref/digest/schema_version)
* produced artifact index (name/ref/digest/schema_version)
  3.5 Required fields for `run_status` (state enum, timestamps, retryable/failure_category)
  3.6 Required fields for `run_ready_signal` (pins + `run_facts_view_ref` + emitted_at)

---

### 4) Immutability and update rules (Binding)

4.1 Which artifacts are **immutable** once written (recommended: `run_plan`, `run_facts_view`, readiness signal)
4.2 Which artifacts may update and how (recommended: `run_status` updates; `run_record` append-only)
4.3 Monotonicity rules (READY never revoked; FAILED/QUARANTINED terminal)
4.4 Corrections policy (new run, never mutation of prior “truth”)

---

### 5) Addressing model (Binding)

> Answers: “Given pins, where do I find SR artifacts?”

5.1 Addressing principles (stable, deterministic, pin-keyed; no “search by timestamp” as primary)
5.2 Required path tokens / key structure

* MUST include `fingerprint={manifest_fingerprint}` (your convention)
* MUST include `run_id` (or equivalent)
* window key placement (if used)
  5.3 Artifact locations relative to an SR ledger root
  5.4 Reference format (URI/path + optional digest + schema version)
  5.5 Cross-store portability rule (paths may vary; refs must remain resolvable under the platform’s storage abstraction)

---

### 6) Discoverability & indexing (Binding-ish)

> Only pin this if you need “find latest READY run” quickly.

6.1 Is “latest READY” a supported concept in v1? (yes/no)
6.2 If yes: deterministic selection rule (order by window key, then run_id tie-break)
6.3 Minimal index artifact (e.g., `ready_index.json`) and its semantics
6.4 Index consistency rules (index updates are idempotent; index never points to non-READY)
6.5 If no: consumers must use explicit `run_id`/pins provided by the caller or scenario plan

---

### 7) Retention, archival, and reproducibility (Binding-ish)

7.1 Retention minimums for SR ledger artifacts (how long must they exist)
7.2 Archival posture (what can be compacted vs must remain)
7.3 Reproducibility guarantee statement (what the ledger must preserve to reproduce outward behaviour)
7.4 Privacy/security considerations (minimal—just what fields must be redacted/avoided)

---

### 8) Downstream consumption rules (Binding)

8.1 “How downstream should use SR outputs” (simple rules)

* always join via `run_facts_view`
* never guess artifact paths
* never proceed without READY (READY meaning + gate set pinned in SR4)
  8.2 Contract between SR and Ingestion Gate (what Ingestion reads from `run_facts_view`)
  8.3 Contract between SR and Observability (what must be logged/metric'd based on ledger)

---

### 9) Acceptance scenarios (Binding)

> This is your “tests as intent” section for the coding agent.

9.1 Happy path: submit → READY → downstream sees correct pins + refs
9.2 Duplicate submit: same logical run → same run_id (or same outcome) → no duplicate side effects
9.3 Retry path: transient failure → retries recorded → READY eventually emitted once
9.4 Failure path: engine fails → SR records FAILED/QUARANTINED → no READY emitted
9.5 Reuse path: evidence exists → SR does not rebuild → ledger shows reuse decision
9.6 Replay path: ledger-driven re-emit (if supported) → same outward pins/refs
9.7 Corruption/inconsistency: evidence mismatch → QUARANTINED and recorded clearly

---

### 10) Mapping to `contracts/` schemas (Informative)

10.1 Which SR5 fields are enforced by `sr_public_contracts_v1.schema.json`
10.2 Any fields intentionally left “open” (extension slots)

---

## Appendices (inline)

### Appendix A) Example artifact payloads (Informative)

A.1 Minimal `run_facts_view` example (the most important one)
A.2 Example `run_record` with retries
A.3 Example `run_status` progression
A.4 Example readiness signal

### Appendix B) Addressing templates (Informative)

B.1 Example path templates showing `fingerprint={manifest_fingerprint}` + `run_id`
B.2 Example refs for engine outputs vs SR ledger outputs

### Appendix C) Ledger Contract Map (v1) (Informative)

C.1 Artifact inventory (v1): `run_plan`, `run_record`, `run_facts_view`, `run_status` (+ persisted signals if applicable)
C.2 Minimum fields per artifact (required only; no optional narrative)
C.3 Immutability / update rules per artifact (append-only vs monotonic vs snapshot)
C.4 Addressing + ref conventions (by-ref fields; ArtifactRef/Locator reuse)
C.5 Mapping from ledger artifacts -> `$defs` names in `sr_public_contracts_v1.schema.json`

### Appendix D) Reviewer checklist (Informative)

D.1 "If any of these are missing, SR is not shippable" quick list

---
