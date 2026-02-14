# Cluster 2 - Round 1 Answers

## Q1) Define the ingress boundary and what `ADMITTED` means

The ingress boundary is a four-component contract, each with a strict ownership line:

1. `SR` (Scenario Runner) owns run authority.
- It mints run-scoped identity and readiness truth.
- It publishes READY only after run facts/evidence are committed.
- It does not perform admission decisions for traffic events.

2. `WSP` (World Streamer Producer) owns controlled event emission into ingress.
- It consumes READY, resolves the run world, and emits canonical traffic envelopes.
- It stamps run pins and sends envelopes to IG.
- It is a producer, not an admission authority.

3. `IG` (Ingestion Gate) is the admission authority.
- It validates envelope/payload contracts and required pins.
- It applies idempotency law and publish-state law.
- It decides `ADMIT`, `DUPLICATE`, or `QUARANTINE`.
- It writes receipt truth for every decision.

4. `EB` (Event Bus) is the durable transport substrate.
- It stores admitted records with partition/offset (or sequence) references.
- It does not decide contract validity or dedupe policy; IG does.

### What `ADMITTED` means in this system

`ADMITTED` is not "HTTP call succeeded." It is a commit-level condition with all of the following true:

1. Envelope/payload validation passed in IG.
2. Required run pins were present and coherent for the event class.
3. Dedupe/collision checks passed under IG’s identity law.
4. IG publish to EB succeeded and produced a concrete bus reference (`topic/partition/offset` or sequence-style equivalent).
5. IG durable admission state was recorded as `ADMITTED`.
6. IG wrote an admission receipt (`decision=ADMIT`) carrying run pins, dedupe key, and bus commit reference.

Durable admission state today is persisted in IG admission index storage (`admissions` table) and surfaced in run evidence via `basis.ig_admission_locator` in the run report (anchor run points to Postgres DSN).
Exact run-report JSON path for that locator is `basis.ig_admission_locator`.

If any of those fail, the event is not treated as admitted:
- semantic duplicate returns `DUPLICATE` with receipt truth,
- ambiguous/invalid/conflicting input returns `QUARANTINE` (fail-closed),
- unresolved publish ambiguity blocks closure claims.

### Why this boundary matters

This separation is what makes at-least-once safe:
- SR owns "when a run is ready",
- WSP owns "what gets emitted",
- IG owns "what is accepted as platform truth",
- EB owns "where admitted events are durably referenced".

That keeps correctness enforceable and auditable instead of relying on best-effort logs.

---

## Q2) Canonical IDs: what they are, who mints them, and where they are enforced

At this boundary, these are the canonical identities that matter:

1. `platform_run_id`
- Meaning:
  one platform execution scope (the run namespace all components must agree on).
- Mint authority:
  platform runtime run-scope resolver (active run context), then propagated by SR and carried end-to-end.
- Enforcement:
  - present in READY payload,
  - present in WSP-emitted envelopes,
  - required by IG pins,
  - embedded in IG receipt payloads and artifact prefixes.
- Why it matters:
  it prevents cross-run contamination. If this drifts, evidence is no longer trustworthy.

2. `scenario_run_id`
- Meaning:
  one SR scenario execution identity inside a platform run.
- Mint authority:
  SR run authority (`run_id` in SR lifecycle), then propagated into READY and WSP emission.
- Current project posture:
  SR currently sets `scenario_run_id = run_id` for READY commit flow (intentional alias in this baseline).
- Enforcement:
  - READY requires it,
  - WSP validates READY vs run-facts consistency,
  - IG carries it into receipts/pins.
- Why it matters:
  it binds event flow to a specific scenario execution, not just a platform shell.

Anchor evidence pin (alias behavior):
- anchor run `platform_20260212T085637Z` reports `scenario_run_ids=["fd17b1049bbce9df478c22ba1740e9ea"]`,
- same run ID appears in SR run-submit/session and SR READY publish log line for that run.
- READY object path pattern is run-scoped: `s3://fraud-platform/<platform_run_id>/sr/ready_signal/<run_id>.json` where `<run_id>` is the SR run ID (and equals `scenario_run_id` in this baseline).

3. `event_id`
- Meaning:
  semantic event identity for idempotency and replay safety.
- Mint authority:
  producer-side event construction (WSP stream runner).
- Deterministic derivation used in code:
  `sha256("|".join([output_id] + primary_key_values + [manifest_fingerprint, parameter_hash, seed, scenario_id]))`
  (present pins are appended in that order).
- Enforcement:
  IG uses `event_id` in dedupe identity and all decision receipts.
- Why it matters:
  duplicates and collisions are decided on this identity, not on transport retries.

4. `event_class`
- Meaning:
  policy class used by IG for routing/partitioning and class-specific pin rules.
- Mint authority:
  IG derives it from `event_type` using IG class-map policy.
- Mapping source used at runtime:
  `config/platform/ig/class_map_v0.yaml` (loaded through IG wiring `class_map_ref`).
- Important nuance:
  producer does not "declare" the final class as truth; IG computes it from authoritative mapping.
- Enforcement:
  IG dedupe key includes `event_class`.
- Why it matters:
  class drift changes dedupe semantics and can silently corrupt admission behavior.

5. READY `message_id`
- Meaning:
  idempotency key for READY publish/consume semantics.
- Mint authority:
  SR computes deterministic READY key from run identity plus bundle/plan hash context.
- Enforcement:
  - included in READY envelope,
  - WSP keeps per-message processing records and skips already-streamed READY messages.
- Why it matters:
  prevents repeated READY delivery from re-triggering duplicate stream executions.

### Concise ownership map

`SR` mints run identities (`platform_run_id` propagation surface, `scenario_run_id`) and READY `message_id`.

`WSP` mints traffic `event_id` for emitted envelopes.

`IG` mints authoritative `event_class` interpretation (from policy) and uses `(platform_run_id, event_class, event_id)` as admission dedupe identity.

### Why this ID model is strong

It separates identity concerns cleanly:
- run scope identity (`platform_run_id`),
- scenario execution identity (`scenario_run_id`),
- event semantic identity (`event_id`),
- policy class identity (`event_class`),
- control-plane idempotency identity (`READY message_id`).

That separation is what allows strict idempotency, safe replay, and auditable ingress decisions under at-least-once delivery.

---

## Q3) What exactly READY is: fields, guarantees, and duplicate-idempotency rules

READY is the control-plane handoff contract from `SR` to `WSP`.

It means:
- SR has completed run planning/evidence commit for a specific scenario run,
- a run-facts view exists,
- WSP can now attempt bounded stream activation for that run scope.

READY is not “platform fully complete.” It is “this run is eligible for stream consumption.”

### READY payload fields (contract shape)

Required READY fields in this project:
1. `run_id`
2. `platform_run_id`
3. `scenario_run_id`
4. `facts_view_ref`
5. `bundle_hash`
6. `message_id`
7. `run_config_digest`
8. `manifest_fingerprint`
9. `parameter_hash`
10. `scenario_id`

Common optional fields:
- `plan_hash`
- `service_release_id`
- `environment`
- `provenance`
- `emitted_at_utc`
- `oracle_pack_ref`

### READY guarantees (what a consumer can rely on)

When READY is accepted by consumer-side schema and cross-checks:
1. Identity guarantee:
   `platform_run_id` and `scenario_run_id` in READY must match run-facts identity.
2. Reference guarantee:
   `facts_view_ref` points to a readable run-facts artifact; invalid/missing facts fail the READY attempt.
3. Idempotency guarantee:
   READY has a deterministic `message_id` minted by SR, so repeated delivery can be recognized safely.
4. Run-scope guarantee:
   if READY run scope does not match active platform run scope, it is skipped out-of-scope instead of being streamed into the wrong run.
5. Dependency guarantee:
   WSP can defer READY when required downstream packs are not yet ready, rather than streaming into partial topology.

Authority order when READY and run-facts disagree:
1. `platform_run_id` and `scenario_run_id` must match between READY and run-facts, else fail (`*_MISMATCH`).
2. For world pins (`manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`), WSP uses run-facts pins as the execution source of truth after identity checks pass.
3. `run_config_digest` is carried for provenance/control-plane traceability; it is not used to override run-facts world identity.

### Duplicate READY behavior (exact rules)

Duplicate handling is status-aware, not naive “always drop.”

WSP keeps per-READY processing records keyed by `message_id`.

If an existing ready-run record has status:
1. `STREAMED`
   duplicate READY is skipped (`SKIPPED_DUPLICATE`).
2. `SKIPPED_OUT_OF_SCOPE`
   duplicate READY is also skipped (already terminally scoped out).

If previous status is non-terminal for idempotency, like:
- `FAILED`
- `DEFERRED_DOWNSTREAM_NOT_READY`

the READY is not permanently suppressed by duplicate logic; it can be processed again on later poll once conditions change.

That rule is intentional:
- terminal outcomes are idempotently closed,
- recoverable/transient outcomes remain retryable.

Where READY processing records are stored:
- run-scoped object-store path: `<platform_run_prefix>/wsp/ready_runs/<message_id>.jsonl`
- terminal statuses (`STREAMED`, `SKIPPED_OUT_OF_SCOPE`) are read from this record to enforce duplicate skip semantics.

### Why this READY design is strong

It gives you:
- deterministic control-plane identity,
- strict run-scope protection,
- bounded retry behavior without duplicate stream storms,
- and clean separation between “eligibility to stream” (READY) and “admission truth” (IG receipts).

---

## Q4) IG dedupe law: duplicate vs collision and action taken

IG dedupe law is anchored on a semantic identity tuple:

`(platform_run_id, event_class, event_id)`

IG hashes that tuple into `dedupe_key` and uses it as the admission identity key.

Important detail:
- `event_class` is not arbitrary producer text; IG derives it from class-map policy using `event_type`.

### How IG decides duplicate vs collision

Before deciding, IG computes a canonical payload hash from:
- `event_type`
- `schema_version`
- `payload`
- Canonicalization and hash algorithm:
  JSON canonical string with `sort_keys=true`, ASCII-safe compact separators, then `sha256`.

Then it checks existing admission state for the same `dedupe_key`.

1. Duplicate (safe idempotent replay)
- Condition:
  same dedupe identity, same payload hash, and existing state is already admitted/committable.
- Action:
  - do not republish to EB,
  - return decision `DUPLICATE`,
  - emit a receipt with prior commit reference (`eb_ref`) and evidence linkage.
- Operational meaning:
  duplicate is absorbed safely; side effects are not replayed blindly.

2. Collision (same identity, different payload)
- Condition:
  same dedupe identity but payload hash differs.
- Action:
  - fail closed as `QUARANTINE`,
  - reason includes `PAYLOAD_HASH_MISMATCH`,
  - write quarantine record plus receipt evidence.
- Operational meaning:
  this is treated as data-integrity contradiction, not a recoverable duplicate.

3. Ambiguous/invalid in-flight identity state (also fail-closed)
- If existing state is `PUBLISH_IN_FLIGHT` or `PUBLISH_AMBIGUOUS`, IG does not treat new arrival as harmless duplicate.
- It quarantines to avoid double-commit risk under uncertain publish truth.

### Drop vs quarantine, explicitly

- Duplicate path = idempotent drop of new publish attempt, with `DUPLICATE` receipt truth.
- Collision/ambiguity path = quarantine, with machine-readable reason code and evidence record.

So IG never “best-effort accepts” identity contradictions. It either converges deterministically (`DUPLICATE`) or isolates (`QUARANTINE`).

Where dedupe state lives:
- IG admission index `admissions` storage (SQLite or Postgres backend).
- In parity/dev posture this is typically Postgres; run evidence exposes locator via `basis.ig_admission_locator`.

---

## Q5) Publish/admission state machine: `PUBLISH_IN_FLIGHT` -> `ADMITTED` / `PUBLISH_AMBIGUOUS`

IG admission uses an explicit publish-state machine per dedupe identity.

State key is the dedupe identity:
`(platform_run_id, event_class, event_id)` -> `dedupe_key`.

### State transitions

1. New identity arrives (no existing dedupe row)
- IG inserts admission row as `PUBLISH_IN_FLIGHT`.
- This means: validation passed and publish is being attempted, but commit truth is not established yet.

2. Publish succeeds
- Trigger:
  event bus publish returns concrete bus ref (`eb_ref`).
- Transition:
  `PUBLISH_IN_FLIGHT` -> `ADMITTED`.
- Commit side effects:
  - IG stores `eb_ref`, admitted timestamp, and payload hash in admission index.
  - IG writes `ADMIT` receipt carrying run pins + dedupe key + bus ref.

3. Publish result is uncertain/fails during publish call
- Trigger:
  bus publish raises exception (timeout, transport fault, unknown commit outcome).
- Transition:
  `PUBLISH_IN_FLIGHT` -> `PUBLISH_AMBIGUOUS`.
- Commit side effects:
  - IG records ambiguous state in index,
  - IG returns fail-closed decision path (`QUARANTINE` with reason `PUBLISH_AMBIGUOUS`),
  - IG writes quarantine artifact + receipt evidence.

Where `PUBLISH_AMBIGUOUS` is recorded:
1. admission index row state (`admissions.state = PUBLISH_AMBIGUOUS`),
2. per-event QUARANTINE receipt/quarantine artifacts (reason code includes `PUBLISH_AMBIGUOUS`),
3. run-level aggregate counter (`ingress.publish_ambiguous`) in run report.

### Behavior on subsequent arrivals with existing state

If dedupe row already exists:
1. Existing state `ADMITTED` + same payload hash:
   return `DUPLICATE` (idempotent convergence, no republish).
2. Existing state `PUBLISH_IN_FLIGHT`:
   quarantine (to avoid double-commit while prior publish is unresolved).
3. Existing state `PUBLISH_AMBIGUOUS`:
   quarantine (sticky fail-closed posture for that identity).
4. Existing payload hash mismatch:
   quarantine as `PAYLOAD_HASH_MISMATCH`.

### What exactly triggers ambiguity

Ambiguity is not “bad payload.” It is publish-truth uncertainty:
- IG cannot prove whether EB commit happened for the in-flight identity.
- In this case, IG must not republish automatically because that can create duplicate side effects.

### How ambiguity gets resolved in practice

There is intentionally no automatic transition from `PUBLISH_AMBIGUOUS` to `ADMITTED` inside the same identity lane.

Resolution is operational:
1. quarantine/receipt evidence is reviewed,
2. run is replayed under controlled rerun posture (typically fresh run scope for clean closure claims),
3. closure proceeds only when admission evidence is unambiguous (`publish_ambiguous=0` in run-level closure posture).

That design is deliberate: when publish truth is uncertain, IG prefers audit-safe halt over speculative forward progress.

---

## Q6) Receipt truth at this boundary: commit evidence and required fields

Receipt truth is two-layered:
1. per-event commit truth (did this exact event get admitted/duplicated/quarantined?),
2. run-level aggregate truth (how many were admitted, duplicated, quarantined, ambiguous?).

If you mix those two, you get weak audit answers. We keep them explicit.

### A) Per-event commit evidence (authoritative for one event)

Primary commit artifact:
- `ingestion_receipt` record (decision receipt written by IG).

For quarantine decisions, paired artifact:
- `quarantine_record` (referenced by receipt evidence refs).

For `ADMIT` / `DUPLICATE`, commit evidence is not complete unless receipt includes bus commit reference:
- `eb_ref.topic`
- `eb_ref.partition`
- `eb_ref.offset`
- `eb_ref.offset_kind`
- optional `eb_ref.published_at_utc`

This is what proves event-bus commit identity for replay/audit.

### B) Required receipt fields (minimum truth contract)

Core receipt fields required across decisions:
1. `receipt_id`
2. `decision` (`ADMIT` | `DUPLICATE` | `QUARANTINE`)
3. `event_id`
4. `event_type`
5. `event_class`
6. `ts_utc`
7. `manifest_fingerprint`
8. `platform_run_id`
9. `run_config_digest`
10. `policy_rev` (policy identity/revision, optional digest subfield)

Identity + provenance-critical fields expected on receipt:
- `dedupe_key`
- `pins` (at minimum run/manifest scope, with optional scenario pins)
- `service_release_id` / `environment` / `provenance` block

Decision-specific required fields:
1. `ADMIT` and `DUPLICATE` must carry:
   - `eb_ref`
   - `scenario_run_id`
   - `payload_hash`
   - `admitted_at_utc`
2. `QUARANTINE` must carry:
   - `evidence_refs` (including quarantine artifact reference),
   - reason codes for failure class.

### B.1) Observed-now vs target clarification (anchor-run posture)

Observed directly from anchor-run materialized artifacts:
1. `decision_receipt_ref` pointers exist and are run-scoped under `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/...` (via run report + DF reconciliation).
2. Bus reference shape in live flow is visible as:
   - `topic`
   - `partition`
   - `offset` (string)
   - `offset_kind` = `kinesis_sequence`
   - `published_at_utc`
   (visible in decision-fabric reconciliation `source_eb_ref` for anchor run).

What is enforced by IG contract/runtime (even when raw receipt blobs are not locally materialized):
1. `ingestion_receipt.schema.yaml` requires core fields (`receipt_id`, `decision`, `event_id`, `event_type`, `event_class`, `ts_utc`, `manifest_fingerprint`, `platform_run_id`, `run_config_digest`, `policy_rev`).
2. For `ADMIT`/`DUPLICATE`, schema requires `eb_ref`, `scenario_run_id`, `payload_hash`, `admitted_at_utc`.
3. For `QUARANTINE`, schema requires `evidence_refs`.

### B.2) Literal anchor receipt pin (keys + `eb_ref` shape)

Anchor receipt object reference:
- `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/00965821d94105a3d88ad6085b3c5b37.json`

Literal top-level key surface for current `ADMIT` receipts (generated by IG `_receipt_payload` and contract-validated):
- `receipt_id`
- `decision`
- `event_id`
- `event_type`
- `event_class`
- `ts_utc`
- `manifest_fingerprint`
- `platform_run_id`
- `scenario_run_id`
- `run_config_digest`
- `policy_rev`
- `dedupe_key`
- `pins`
- `payload_hash`
- `admitted_at_utc`
- `partitioning_profile_id`
- `partition_key`
- `eb_ref`
- `service_release_id`
- `environment`
- `provenance`

Literal `eb_ref` shape:
- `topic`
- `partition`
- `offset`
- `offset_kind`
- `published_at_utc`

Schema authority path used for this boundary:
- `docs/model_spec/platform/contracts/ingestion_gate/ingestion_receipt.schema.yaml`

### C) Where run IDs and hashes are carried

Run IDs:
- top-level `platform_run_id`
- top-level `scenario_run_id` (for admit/duplicate)
- mirrored in `pins` for cross-component provenance continuity

Hashes:
- `payload_hash` (semantic collision control)
- `manifest_fingerprint` (world identity)
- `run_config_digest` (runtime config/procedure identity)
- optional policy content digest under `policy_rev`

### D) Count truth (where counts come from)

Counts are not encoded in one receipt.

Count truth is produced by aggregating receipt/admission evidence and surfaced at run level, e.g. ingress counters such as:
- `received`
- `admit`
- `duplicate`
- `quarantine`
- `publish_ambiguous`
- `receipt_write_failed`

So:
- per-event receipt proves single-event decision truth,
- run report proves aggregate boundary behavior for the run.

### E) Why this is defensible

With this model, you can answer both audit questions cleanly:
1. “Prove this one event was admitted” -> show receipt + `eb_ref`.
2. “Prove the boundary behaved correctly for the whole run” -> show aggregated ingress counters derived from receipt/admission truth.

---

## Q7) Anchor run for Control/Ingress boundary

For this cluster, my anchor run is:

1. `platform_run_id`
- `platform_20260212T085637Z`

2. Root evidence path
- local run root: `runs/fraud-platform/platform_20260212T085637Z/`
- object-store run root: `s3://fraud-platform/platform_20260212T085637Z/`

3. IG receipts prefix (commit evidence surface)
- `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/`
- sample receipt file:
  `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/00965821d94105a3d88ad6085b3c5b37.json`

### Why this is the right anchor for Cluster 2

This run gives a clean boundary story:
- ingress counters closed with non-zero admits and zero ambiguity/quarantine at run level,
- receipt references are present under the run-scoped IG prefix,
- run-scoped report/conformance artifacts exist under the same `platform_run_id`.

So for any Control/Ingress challenge question, this run is the one I can defend end-to-end without switching contexts.

---

## Q8) One real correctness-saved incident

### Incident
`IG receipt provenance drift across run scopes`

### What happened

I hit a boundary contradiction that looks small but is actually severe for auditability:
- receipt payload pins said one `platform_run_id`,
- but the receipt artifact path (`receipt_ref`) was written under a different run scope.

Root cause was scope source mismatch:
- receipt path prefix was being derived from service/runtime environment state,
- while envelope pins were derived from the incoming event for the active run.

So the same receipt carried two conflicting run truths.

### Evidence that recorded the failure

The failure was visible as provenance split:
1. receipt metadata (`pins.platform_run_id`) pointed to active run,
2. receipt object path prefix pointed to stale/other run scope.

Concrete run evidence used during remediation:
- observed in parity window around `platform_20260206T052035Z` where receipt metadata carried `pins_json.platform_run_id=platform_20260206T052035Z` while stored `receipt_ref` used older prefix `s3://fraud-platform/platform_20260206T042550Z/...`.
- this is the exact contradiction class documented in IG implementation notes for the fix.

Concrete bad receipt path form from the incident window:
- `s3://fraud-platform/platform_20260206T042550Z/ig/receipts/<receipt_id>.json` (wrong run scope prefix)

Where the conflicting run id was read:
- ops-index `receipts.pins_json` (JSON column), field path `pins_json.platform_run_id`
- receipt payload path is `pins.platform_run_id` (with top-level `platform_run_id` also present)

At run-operations level, this showed up as “everything looks admitted” but evidence lineage was not single-run consistent, which means replay/audit trust was compromised.

### What I changed

I fixed it at the write boundary, not by operator convention:
1. made envelope `platform_run_id` the authoritative source for receipt/quarantine artifact prefix,
2. added per-write prefix override in receipt writer path,
3. updated all IG decision paths (`ADMIT`, `DUPLICATE`, `QUARANTINE`) to use envelope-scoped prefix,
4. applied store-aware prefix behavior:
   - S3-style: `<platform_run_id>/ig/...`
   - local object root: `fraud-platform/<platform_run_id>/ig/...` (with root-aware normalization),
5. added regression tests for mismatched env-vs-envelope scope; envelope scope must win.
   - targeted in `tests/services/ingestion_gate/test_admission.py`.

### Proof it is fixed

On anchor run `platform_20260212T085637Z`:
1. IG receipt sample refs are all under:
   `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/...`
2. run-level ingress closure is consistent in the same run scope:
   - non-zero admits,
   - `publish_ambiguous = 0`,
   - `quarantine = 0`.
3. The boundary now has one run truth for both metadata and artifact location.

So this was not a cosmetic cleanup. It removed a replay/audit integrity defect at the exact control-ingress boundary.

---

## Q9) Provenance recorded at this boundary, and where it lives

At Control/Ingress boundary, provenance is captured at three levels:
1. run/control-plane provenance,
2. event/admission provenance,
3. aggregated run evidence provenance.

### 1) Run/control-plane provenance

Recorded fields:
- `platform_run_id`
- `scenario_run_id`
- `manifest_fingerprint`
- `parameter_hash`
- `scenario_id`
- `run_config_digest`
- `service_release_id`
- `environment`
- `provenance` object (`service_release_id`, `environment`, optional `config_revision`, optional `run_config_digest`)

Where it lives:
- READY payload and run-facts artifacts for the run.
- In practice for this project, these are under the run-scoped SR artifacts and consumed by WSP before streaming.

### 2) Event/admission provenance (IG boundary truth)

Recorded fields in receipts/quarantine:
- run identity:
  `platform_run_id`, `scenario_run_id`, plus pinned run fields under `pins`
- world/config identity:
  `manifest_fingerprint`, `parameter_hash`, `run_config_digest`
- policy identity:
  `policy_rev.policy_id`, `policy_rev.revision`, optional `policy_rev.content_digest`
- runtime provenance:
  `service_release_id`, `environment`, `provenance` block
- commit identity:
  `dedupe_key`, `eb_ref` (for admit/duplicate), and quarantine evidence refs where applicable

Where it lives:
- IG receipt objects under run-scoped prefix:
  `s3://fraud-platform/<platform_run_id>/ig/receipts/...`
- IG quarantine objects under:
  `s3://fraud-platform/<platform_run_id>/ig/quarantine/...`
- IG admission/ops stores (durable indexes) that back receipt lookup and counters.

### 3) Aggregated run evidence provenance

Recorded fields:
- basis-level provenance summary:
  `service_release_id`, `environment`, `config_revision`
- run scope summary:
  `run_prefix` / `platform_run_id`
- ingress aggregate behavior:
  `admit`, `duplicate`, `quarantine`, `publish_ambiguous`, etc.

Where it lives:
- run report artifact:
  `runs/fraud-platform/<platform_run_id>/obs/platform_run_report.json`

For anchor run `platform_20260212T085637Z`, this report explicitly contains basis provenance with:
- `service_release_id = dev-local`
- `environment = local_parity`
- `config_revision = local-parity-v0`

JSON paths in run report:
- `basis.provenance.service_release_id`
- `basis.provenance.environment`
- `basis.provenance.config_revision`
- `basis.run_prefix`

### About `image digest` and `git sha` specifically

Current truth:
- They are not first-class mandatory fields in Control/Ingress receipts/READY schema in this baseline.
- The boundary currently standardizes on `service_release_id` + `environment` + `config_revision`/`run_config_digest` as release/config provenance.

So if a recruiter asks “do you stamp immutable image digest/git SHA at ingress receipt level today?” the honest answer is:
- not as a mandatory contract field yet in this lane,
- but we do carry stable release/config provenance and run/world pins needed for replay and audit.

---

## Q10) Invariants that must stay identical from `local_parity` -> `dev_min` (and what may change)

For Control/Ingress migration, the rule is:
**change substrate and operations, not semantics.**

### A) Non-negotiable invariants (must remain identical)

1. Envelope contract invariants
- Required canonical envelope fields and meaning stay the same.
- `platform_run_id`, `scenario_run_id`, `event_id`, `event_type`, pins, and timestamp contract must not change meaning between environments.

2. Identity ownership invariants
- SR remains authority for READY/run identities.
- WSP remains producer of emitted traffic event envelopes.
- IG remains admission authority.
- EB remains transport substrate, not semantic decision maker.

3. Dedupe law invariants
- IG semantic dedupe identity remains:
  `(platform_run_id, event_class, event_id)`.
- payload hash mismatch for same dedupe identity remains fail-closed anomaly/quarantine.

4. Publish-state machine invariants
- IG publish lifecycle remains:
  `PUBLISH_IN_FLIGHT -> ADMITTED | PUBLISH_AMBIGUOUS`.
- Ambiguous publish remains fail-closed; no silent auto-admit behavior.

5. Receipt truth invariants
- IG receipts remain the commit evidence surface.
- Decision-specific required fields remain intact (`eb_ref` for admit/duplicate, evidence refs for quarantine, run pins/provenance fields).
- Receipt/quarantine artifact path must remain run-scoped to the same `platform_run_id` carried in pins.

6. READY contract invariants
- READY schema fields and semantics remain unchanged.
- READY `message_id` stays deterministic and dedupe-safe.
- Duplicate READY handling remains status-aware (terminally closed statuses skip; retryable statuses remain re-processable).

7. Run-scope guard invariants
- Out-of-scope run messages must not leak into active run processing.
- Active run scope still gates streaming/admission surfaces.

8. Fail-closed behavior invariants
- Contract violations do not downgrade to warning-only success.
- Collision/ambiguity/schema mismatches still block boundary truth claims.

### B) What is allowed to change (operational envelope only)

1. Transport/storage substrate
- MinIO -> AWS S3 (or equivalent) is allowed.
- LocalStack Kinesis -> managed Kafka/Kinesis is allowed.
- Local Postgres -> managed Postgres is allowed.
- These are infrastructure swaps, not semantic swaps.

2. Security mechanism
- API-key allowlist in local parity can become service-token/mTLS posture in dev.
- Auth strength can increase, but acceptance semantics must remain the same.

3. Capacity/performance knobs
- partition counts, retention windows, concurrency, retry timing, polling intervals can change.
- Throughput tuning is allowed as long as correctness laws remain unchanged.

4. Packaging/deployment form
- local process/compose -> managed tasks/services is allowed.
- orchestration mechanics can change (CLI wiring, managed run control), but phase/gate meaning must remain equivalent.

5. Observability implementation
- metric/tracing backends and sampling levels can change.
- required run-scoped counters/evidence semantics must remain.

### C) What is explicitly not allowed

1. Rewriting identity semantics during migration
- e.g., changing dedupe tuple to include/remove fields for convenience.

2. Loosening IG ambiguity/collision behavior to “keep flow moving”
- e.g., treating `PUBLISH_AMBIGUOUS` as admitted without hard proof.

3. Silent schema drift
- removing required READY/receipt fields or changing field meaning between envs.

4. Breaking run-scope provenance linkage
- pins say one run while artifact paths or counters resolve to another.

5. Replacing receipt truth with log-only assertions
- boundary correctness must remain artifact-backed, not narrative-backed.

### D) Practical migration parity check (what I use)

Before calling Control/Ingress “dev-min equivalent,” I verify:
1. same READY contract accepted/rejected for same inputs,
2. same dedupe/collision outcomes for replayed duplicates and payload mismatches,
3. same publish ambiguity fail-closed behavior,
4. same receipt schema and run-scoped receipt prefix behavior,
5. same run-scope mismatch protection (no cross-run leakage),
6. same aggregate ingress truth dimensions (`admit/duplicate/quarantine/publish_ambiguous`).

If all six are true, migration changed infrastructure but preserved boundary semantics, which is the correct definition of parity for this cluster.

---

## Q11) Checkpointing + replay safety

Checkpointing for this boundary is anchored in WSP, then protected by IG idempotency:

1. WSP checkpoint store
- backend in local parity today: **Postgres** (`wsp_checkpoint.backend=postgres` in `config/platform/profiles/local_parity.yaml`),
- logical table/file model: `wsp_checkpoint` cursor per `(pack_key, output_id)`,
- checkpoint scope key in stream-view mode is run-bound:
  `checkpoint_pack_key = sha256(pack_key|platform_run_id|scenario_run_id)`.
- this is what prevents a new run from silently resuming an old run’s offsets.

2. What is truth if checkpoint and receipts disagree
- receipt truth wins for admission semantics (IG is admission authority).
- checkpoint is consumption progress state, not admission truth.
- if checkpoint advances but IG shows ambiguity/quarantine contradictions, closure is blocked and replay is controlled.

3. Real replay-safety example
- Duplicate READY delivery occurs naturally in control-bus polling.
- WSP first checks run-scoped READY record (`.../wsp/ready_runs/<message_id>.jsonl`):
  - terminal status (`STREAMED`, `SKIPPED_OUT_OF_SCOPE`) => skip duplicate.
- if a duplicate event still reaches IG, IG dedupe law converges it via `(platform_run_id,event_class,event_id)` + payload hash.
- net effect: no double-commit side effect.

---

## Q12) Backpressure / bounded safety knobs at ingress

Safety-critical knobs (change correctness envelope if misused):
1. `WSP_MAX_EVENTS_PER_OUTPUT` (bounded gate cap: smoke/baseline acceptance).
2. `WSP_READY_MAX_MESSAGES` and READY poll loop controls (how much control-plane work is admitted per cycle).
3. WSP->IG retry budget:
   - `ig_retry_max_attempts`
   - `ig_retry_base_delay_ms`
   - `ig_retry_max_delay_ms`
4. WSP checkpoint flush cadence (`checkpoint_every`) because it defines replay-loss window on interruption.

Performance-oriented knobs (tune throughput/latency, not semantics):
1. poll intervals (`--poll-seconds`, component poll sleep),
2. stream-view batch size (`WSP_STREAM_VIEW_BATCH_SIZE`),
3. component concurrency/parallelism controls.

Where knob values are captured for a run:
1. operator command/runpack env (for example `local_parity_control_ingress` pack env and make target args),
2. session/platform logs (`session.jsonl`, `platform.log`, `wsp_ready_consumer.log`),
3. run report counters (to verify bounded outcomes actually happened).

---

## Q13) Writer/ownership enforcement (who is allowed to write what)

Writer map (hard boundary ownership):
1. SR writes: `run_plan`, `run_record`, `run_status`, `run_facts_view`, `ready_signal`.
2. WSP writes: emitted envelopes to IG and WSP checkpoint/READY-run records.
3. IG writes: admission/quarantine decisions + receipt/quarantine artifacts + admission index state.
4. EB writes: transport offsets/sequences only.

Concrete enforcement mechanisms:
1. SR write-once guards:
- `write_json_if_absent` + drift errors (`PLAN_DRIFT`, `FACTS_VIEW_DRIFT`, `READY_SIGNAL_DRIFT`).
2. IG scope enforcement at writer:
- receipt/quarantine prefix derived from `envelope.platform_run_id` per call (not stale service env).
3. Contract enforcement:
- IG validates receipt/quarantine payloads against schemas before write.
4. Runtime authority split:
- WSP cannot produce IG admission truth; only IG decides and writes `ADMIT`/`DUPLICATE`/`QUARANTINE`.
