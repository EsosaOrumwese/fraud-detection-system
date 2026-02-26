# Replay-Safe Streaming Ingestion with Fail-Closed Correctness and Transport/Durable Truth Separation

## 1) Claim Statement

### Primary claim
I built a streaming ingestion boundary that is idempotent, replay-safe, and fail-closed by enforcing canonical deduplication identity at admission time, treating same-identity payload mismatches as anomalies instead of overwrite candidates, and separating transport behavior from durable truth so the message broker remains an execution rail while durable evidence/state live outside broker retention.

### Why this claim is technically distinct
This claim is not only "we used Kafka" or "we added dedupe."
It is a correctness-and-ownership claim across two coupled planes:
- ingestion correctness plane: how events are admitted, deduplicated, quarantined, and replayed safely,
- truth-ownership plane: where durable state/evidence are authored and which system is explicitly not allowed to become canonical storage.

Most streaming systems fail when these planes are blurred. This claim closes both planes with explicit behavior under duplicate, replay, and mismatch conditions.

### Definitions (to avoid ambiguous interpretation)
1. Canonical deduplication identity
- A deterministic identity tuple is used as the admission boundary key for each ingest candidate.
- If the same identity arrives again with the same payload hash, admission converges idempotently.
- If the same identity arrives with a different payload hash, the event is treated as an anomaly and moved to fail-closed handling.

2. Replay-safe ingestion
- Reprocessing or broker replay does not create duplicate durable side effects.
- Admission decisions remain stable under at-least-once delivery behavior.
- Cursor/checkpoint progression is treated as progress metadata, while durable admission/evidence state remains the correctness authority.

3. Fail-closed mismatch handling
- Identity collision with payload mismatch is not auto-corrected, not silently overwritten, and not silently admitted.
- The mismatch is persisted with explicit anomaly posture (for example quarantine or ambiguity state) and must be remediated through controlled rerun/reconciliation.

4. Transport versus durable truth separation
- The broker is a delivery mechanism with retention and partition semantics optimized for streaming flow, not a long-term source of record.
- Durable truth (admission receipts, reconciliation evidence, and persistent state) is owned by durable stores with explicit write ownership and auditability.

5. Topic semantics
- Topic map, keying, and partitioning rules are intentionally designed to preserve ordering/affinity where required and to control fan-out behavior.
- Retention policy is treated as operational replay window configuration, not as durability policy.

### In-scope boundary
This claim covers:
- streaming admission boundary behavior for duplicates, replay, and identity collisions,
- canonical deduplication identity and payload-hash mismatch posture,
- fail-closed anomaly handling that blocks silent overwrite behavior,
- intentional broker topic semantics (keying, partitioning, retention posture),
- explicit durable-truth ownership outside broker retention for admission/evidence/state surfaces,
- operational recovery posture where replay/retry does not violate correctness contracts.

### Non-claim boundary
This claim does not assert:
- exactly-once semantics for every downstream side effect in every component,
- multi-region disaster recovery architecture or global broker failover design,
- organization-wide streaming governance beyond this platform ingestion boundary,
- elimination of all runtime incidents unrelated to streaming admission correctness and truth ownership.

### Expected reviewer interpretation
A correct reviewer interpretation is:
- "The engineer designed a production-grade ingestion boundary that remains correct under replay and duplicate delivery, enforces anomaly-safe behavior under identity collision, and prevents the broker from becoming accidental canonical storage."

An incorrect interpretation is:
- "The engineer mainly configured Kafka topics and added basic duplicate checks."

## 2) Outcome Target

### 2.1 Operational outcome this claim must deliver
The target outcome is to make streaming ingestion behave as a controlled correctness boundary under at-least-once delivery conditions.
In practice, the platform must prove all of the following together:
- duplicate and replayed transport messages do not create duplicate durable effects,
- same-identity payload mismatches are not silently overwritten or auto-admitted,
- admission decisions remain deterministic under replay and rerun conditions,
- broker retention loss does not erase durable truth because canonical state/evidence are stored outside the broker.

This means "messages flowed" is not success.
Success requires correctness closure across identity, admission, replay, anomaly handling, and truth ownership.

### 2.2 Engineering success definition
Success for this claim is defined by five coupled properties:

1. Idempotent admission convergence
- Same canonical identity plus same payload hash converges to a stable decision path.
- Re-delivery does not produce duplicate durable writes.

2. Collision safety
- Same canonical identity plus different payload hash is treated as a contradiction.
- Contradictions are persisted as anomalies and block silent progression.

3. Replay stability
- Reprocessing from retained transport history does not change prior durable truth for already-admitted equivalent events.
- Checkpoint recovery restores progress without violating admission correctness.

4. Transport and truth separation
- Broker topics are used for delivery/replay windows, not as canonical long-term truth.
- Durable stores hold admission evidence, reconciliation posture, and persistent state needed for audit/recovery.

5. Fail-closed closure discipline
- Any unresolved ambiguity/anomaly state prevents "green" closure claims until remediated and rerun.
- Closure is artifact-driven, not operator-opinion driven.

### 2.3 Measurable success criteria (all must be true)
Outcome is achieved only when all criteria below are satisfied for a bounded acceptance run and its recovery checks:

1. Deduplication law closure
- Canonical identity fields are present and deterministic for all admitted events in scope.
- Duplicate replays resolve as idempotent convergence, not additional durable admissions.

2. Mismatch handling closure
- Identity collisions with payload mismatch are detectable and recorded.
- Mismatch paths result in explicit anomaly posture (for example quarantine or ambiguity) with no overwrite.

3. Replay/recovery closure
- Replay tests or restart/recovery runs produce no correctness drift in admission outcomes for equivalent inputs.
- Recovery posture demonstrates durable truth winning over transient transport position.

4. Durable-evidence closure
- Admission evidence and reconciliation artifacts are available in durable storage for the run scope.
- Evidence is sufficient to explain admit, duplicate, and anomaly outcomes without relying on broker message retention alone.

5. Transport semantics closure
- Topic map, keying, and partitioning rules are explicit and aligned to required ordering/affinity behavior.
- Retention is explicitly treated as replay window control, not durable canonical storage.

### 2.4 Explicit failure conditions (non-success states)
This claim is treated as not achieved if any of the following occurs:
- duplicates can produce multiple durable admissions for the same canonical identity and equivalent payload,
- payload mismatch under same canonical identity is silently overwritten, silently admitted, or dropped without anomaly record,
- replay/restart changes previously stable admission outcomes for equivalent inputs without explicit versioned reason,
- broker retention is implicitly required to reconstruct canonical admission truth,
- closure is declared while unresolved anomaly/ambiguity blockers remain open.

### 2.5 Risk reduction objective (why this matters to senior platform roles)
This outcome reduces high-impact platform risks that recruiters and hiring managers care about:
- data integrity risk: replay/duplicate traffic no longer corrupts durable admission truth,
- audit risk: anomaly and admission decisions remain explainable from durable evidence surfaces,
- reliability risk: restart/recovery behavior remains stable under at-least-once delivery reality,
- architecture risk: broker retention policy changes cannot silently erase canonical business truth,
- operations risk: fail-closed blockers prevent false-green closure claims.

### 2.6 Evidence expectation for this section
This section defines target behavior and pass criteria.
Proof is provided later in:
- controls and guardrails (how rules are enforced),
- validation strategy (how replay/idempotency/anomaly behavior is tested),
- results and operational outcome (what actually passed),
- proof hooks (where failure-to-fix-to-pass artifacts are pinned).

## 3) System Context

### 3.1 System purpose in the platform architecture
This claim lives at the ingestion boundary where externalized event production becomes platform-owned truth.
Its purpose is to enforce two guarantees at the same time:
- delivery resilience: stream transport can replay, retry, and redeliver without corrupting outcomes,
- truth integrity: canonical admission truth is written to durable stores with explicit ownership, not inferred from broker retention.

Without this boundary, a streaming system can appear operational while silently accumulating duplicate side effects, hidden payload contradictions, or non-reproducible audit state after retention windows expire.

### 3.2 Main components and role boundaries
The active path is composed of five role-separated components:

1. Event producer boundary
- emits canonical event envelopes with run-scope pins and deterministic event identity inputs.
- owns event production intent, not admission truth.

2. Ingestion boundary service
- validates envelope and payload contract posture,
- derives canonical deduplication key from run scope plus event class plus event identifier,
- enforces admission state transitions and mismatch policy,
- publishes admitted events to stream transport,
- emits durable admission artifacts (receipts and anomaly records).

3. Stream transport layer (Kafka)
- provides partitioned delivery and replay window behavior,
- carries ordered stream traffic for downstream consumers,
- does not own canonical admission truth.

4. Durable admission and evidence stores
- admission index persists state machine progression (`PUBLISH_IN_FLIGHT`, `ADMITTED`, `PUBLISH_AMBIGUOUS`),
- receipt and quarantine artifacts persist decision evidence under run-scoped object prefixes,
- operational query index supports challenge/replay diagnostics.

5. Downstream consumers
- consume admitted transport records with checkpointed progress,
- rely on ingestion artifacts for correctness interpretation under replay or restart.

### 3.3 Flow contract (request to durable truth)
At a high level, the request-to-truth flow is:

1. Envelope arrives at ingestion boundary.
2. Contract and class rules are validated.
3. Canonical dedupe key is derived from `(platform_run_id, event_class, event_id)` and hashed.
4. Existing admission state is checked:
- same key plus same payload hash -> duplicate convergence path,
- same key plus different payload hash -> fail-closed anomaly path.
5. New admissible record enters `PUBLISH_IN_FLIGHT`.
6. Publish to Kafka stream using partition profile for the event class.
7. On publish success:
- state advances to `ADMITTED`,
- event-bus reference is pinned (topic, partition, offset, offset kind, publish timestamp),
- receipt is persisted durably under run-scoped prefix.
8. On publish uncertainty/failure:
- state advances to `PUBLISH_AMBIGUOUS`,
- anomaly path is persisted (quarantine plus receipt with reason codes),
- closure remains blocked until ambiguity is resolved by controlled rerun/reconciliation.

### 3.4 Topic and partition semantics (intentional transport design)
Topic and partition behavior is explicit configuration, not implicit defaults.
Partitioning profiles define:
- target topic per event family,
- deterministic key-precedence fields,
- fixed hash algorithm for key derivation.

Representative design intent:
- traffic families partition by flow or entity affinity fields to preserve localized order,
- context families partition by merchant and arrival sequence affinity,
- control families partition by run-scoped identifiers,
- decision/action families partition by idempotency and decision lineage fields.

This design reduces accidental cross-entity ordering drift and keeps replay behavior predictable at consumer boundaries.

### 3.5 Durable truth surfaces versus transport surfaces
This boundary intentionally separates "how data moves" from "what is true."

Transport surfaces (ephemeral by policy):
- Kafka topics and offsets,
- retention-based replay windows,
- consumer cursor/checkpoint progress metadata.

Durable truth surfaces (canonical for audit and recovery):
- admission state table keyed by dedupe identity,
- durable admission receipts under run-scoped object-store prefixes,
- durable quarantine records and reason codes for fail-closed outcomes,
- run-scoped operational index for receipt and anomaly lookup.

This separation is the core guardrail against using "Kafka as the database."

### 3.6 Recovery model and replay posture
The runtime model assumes at-least-once delivery and restart events are normal.
Correctness is preserved by combining:
- deterministic dedupe identity,
- payload-hash contradiction detection,
- durable admission state tracking before and after publish attempts,
- explicit ambiguity states that block false closure,
- replay-aware consumers that can re-read transport history without rewriting canonical truth.

In this model, checkpoint state accelerates progress but does not redefine truth; durable admission artifacts remain the source of correctness decisions.

### 3.7 Why this context matters for senior-role evaluation
Recruiters evaluating senior platform capability look for explicit ownership and failure semantics, not only message throughput.
This system context demonstrates:
- boundary-first design (who owns truth and who does not),
- deterministic behavior under replay and duplicate pressure,
- explicit contradiction handling instead of silent overwrite,
- transport/durable separation that remains auditable when broker retention rotates.

## 4) Problem and Risk

### 4.1 Core problem statement
The core problem was not broker connectivity or throughput alone.
The real engineering problem was correctness under replay and partial failure:
- transport layers redeliver and reorder within partition constraints,
- producers and consumers restart with imperfect timing,
- publish attempts can fail after uncertain side effects,
- retention windows expire and remove transport history.

If admission logic is weak at this boundary, the platform can produce duplicate durable state, lose contradiction visibility, or declare false closure from incomplete evidence.

### 4.2 High-risk failure classes this claim had to close
This work was designed to eliminate five concrete failure classes:

1. Silent duplicate side effects
- same logical event admitted multiple times under replay/retry conditions,
- downstream systems observe inflated counts and non-deterministic histories.

2. Silent overwrite on identity collision
- same canonical identity arrives with changed payload,
- system overwrites prior truth instead of recording a contradiction.

3. Publish uncertainty drift
- broker publish path fails at ambiguous points,
- system cannot prove whether transport side effects occurred,
- closure is still claimed without explicit ambiguity state and remediation.

4. Transport-as-truth drift
- broker retention is treated as canonical history,
- once retention rotates, prior decision evidence becomes unrecoverable.

5. Topic-contract drift
- runtime topic names or routing assumptions diverge from pinned contract,
- ingestion appears active while required downstream lanes receive nothing or receive invalid streams.

### 4.3 Why these risks are severe in production-like streaming systems
These are not cosmetic defects.
Each one directly threatens reliability and auditability:
- integrity impact: duplicate or overwritten admissions corrupt business truth,
- governance impact: missing contradiction records remove forensic explainability,
- recovery impact: replay or restart can amplify damage instead of converging safely,
- operational impact: teams chase phantom incidents because transport counters and durable truth disagree.

For senior platform roles, this is a primary screening signal: whether the engineer can design for at-least-once reality and still preserve deterministic truth.

### 4.4 Observed runtime signals that confirmed the risk model
The risk model was validated by real runtime behavior during managed environment promotion:
- duplicate-heavy windows appeared when replay/checkpoint posture and run scope were not tightly controlled,
- publish-side uncertainty required explicit ambiguity handling to avoid false admission claims,
- topic alignment drift created apparent system health while intended semantic flow was incomplete.

These were treated as boundary defects, not tuning noise.
Remediation was accepted only when the same failure class no longer violated correctness gates under rerun.

### 4.5 Design requirement derived from the risk profile
From this risk profile, the boundary had to satisfy one non-negotiable law:
- no event can cross from transport into durable truth without deterministic identity checks, contradiction-safe handling, and auditable decision evidence.

Anything weaker would allow throughput to mask correctness loss.
