# Cluster 4 - Round 1 Answers

## Q1) What databases are in play (local_parity now, dev_min target), and what each is used for (state vs receipts vs checkpoints)?

The correct answer is: this platform uses a **datastore topology**, not one database.

I separate it into three truth classes because that is how I prevent audit confusion and replay bugs:

1. **State stores** (queryable operational truth for services)
2. **Receipt/evidence stores** (append-only run evidence and admission proofs)
3. **Checkpoint stores** (stream progress cursors for restart/replay safety)

### 1) `local_parity` (current) datastore surface

#### A) Relational state stores (Postgres-backed DSNs in profile wiring)

These hold component state that must be queryable and durable across process restarts:

- **IG admission state/index** (`IG_ADMISSION_DSN`): dedupe keys, admission outcomes, publish state ownership.
- **WSP checkpoint table** (`WSP_CHECKPOINT_DSN`): per-pack/per-output stream cursor (`wsp_checkpoint`).
- **RTDL projection stores**:
  - IEG projection store (`IEG_PROJECTION_DSN`)
  - OFP projection store + snapshot index (`OFP_PROJECTION_DSN`, `OFP_SNAPSHOT_INDEX_DSN`)
  - CSFB projection store (`CSFB_PROJECTION_DSN`)
- **Decision lane / action lane / case lane relational stores**:
  - DF replay/checkpoint DSNs
  - AL ledger/outcomes/replay/checkpoint DSNs
  - DLA index DSN
  - Case trigger replay/checkpoint/publish-store DSNs
  - Case management + label store locators
  - Archive writer ledger DSN

This is the plane I treat as **business-operational state**.

#### B) Receipt and evidence store (object store, not relational DB)

Ingress receipts and quarantine records are persisted as objects under run-scoped prefixes (for example `.../ig/receipts/*.json`, `.../ig/quarantine/*.json`), and run/obs/governance artifacts are also stored there.

In local parity, this is the S3-compatible object-store root (`s3://fraud-platform` backed by MinIO).  
This plane is **append-only evidence truth**, not mutable operational state.

#### C) Checkpoint stores (mixed implementation by component)

There are two checkpoint patterns in local parity:

- **Postgres checkpoints** where explicitly wired (e.g., WSP checkpoint table).
- **Run-scoped SQLite sidecar cursor files** for some long-running consumers (for example `*/consumer_checkpoints.sqlite`), used for restart continuation.

Critical boundary:
- These checkpoints are **transport progress truth** (where consumer resumes), not business/audit truth.
- Business truth stays in state stores + append-only receipts/evidence.

### 2) `dev_min` (target) datastore surface

The target keeps the same semantics and ownership boundaries, but swaps substrate:

- **Managed Postgres (AWS RDS)** is the runtime relational substrate for component state/checkpoint tables.
  - Endpoint and instance identity are materialized by Terraform.
  - Credentials are supplied via SSM parameter paths (`/fraud-platform/dev_min/db/user`, `/fraud-platform/dev_min/db/password`; optional DSN path).
- **Object-store evidence remains append-only** (AWS S3 in dev_min) for receipts, quarantine, and run evidence artifacts.
- **Event bus changes from local-parity stream emulation to managed Kafka/Confluent**, but offsets still appear as provenance in receipts/state rather than becoming a separate “database of record.”

So the migration posture is:
- **State/checkpoint relational truth** moves to managed Postgres substrate,
- **Receipt/evidence truth** remains object-store append-only,
- **Boundary law does not change** (only substrate changes).

### 3) Concise classification (what belongs where)

- **State**: mutable/queryable service truth (admission indices, projections, ledgers, replay/checkpoint gates, case/label state) -> relational DSN stores.
- **Receipts**: immutable admission and quarantine proofs + run evidence artifacts -> object store paths.
- **Checkpoints**: consumer cursor progression for replay/restart safety -> checkpoint tables/files, never treated as authoritative business truth.

That separation is deliberate. It is what lets me debug datastore incidents without conflating:
- “consumer resumed correctly,”
- “event was admitted correctly,” and
- “audit evidence is present and replayable.”

## Q2) Give one concrete incident (choose your strongest)

My strongest incident is the **platform-wide Postgres connection-lifecycle collapse** (the connection churn class), not a single-service bug.

### Incident I am choosing

I am choosing the **connection pooling/churn** class:
- repeated connect/disconnect pressure in long-running workers,
- resulting in runtime failures (`OperationalError`, address-in-use patterns),
- followed by multi-pack instability after a bounded run that should have stayed green.

### Why this is the strongest Cluster 4 incident

I consider this stronger than a single reserved-keyword or single-table issue because:
- it affected multiple packs at once (RTDL core, decision lane, case/labels),
- it appeared after a nominally successful stream gate (so it challenged operational truth, not just startup syntax),
- it required architectural datastore-lifecycle correction, not a one-line SQL patch.

### What made it a true datastore-hardening event (not “just infra noise”)

The contradiction was severe:
- the platform could produce bounded run success,
- but datastore interaction patterns then destabilized long-running services.

That means the bottleneck was not model logic or event production; it was **database lifecycle semantics under orchestration**:
- connection acquisition/reuse discipline,
- transaction boundary handling under persistent connections,
- transient error posture in daemon loops.

### Why I selected this for Q2 over the other candidates

I have credible incidents in all four categories (reserved identifier, connection churn, transaction/locks, and schema drift).  
For recruiter defense, this one is the best first anchor because it proves I can:
- identify a cross-service failure signature,
- classify it as a platform P0,
- fix the shared datastore runtime contract once,
- and then revalidate full-run stability instead of celebrating a narrow local fix.

I will pin exact components/run/error signatures in Q3, then root cause/change/verification/guardrail in Q4-Q7.

## Q3) Pin it: which component(s), which phase/run did it break, and what exactly failed (error class, symptom)?

This incident is pinned to a specific acceptance window and a specific run.

### Where in the lifecycle it broke

- **Lifecycle point:** post-stream liveness portion of the local-parity full-platform acceptance sequence (the stage where services must stay alive after bounded stream closure, not just emit events).
- **Run:** `platform_20260210T083021Z` (the 200-event bounded run that had already satisfied stream-budget metrics).

So the break was not “could not start streaming.”  
It was worse: **stream gate passed, then daemon runtime collapsed.**

### Components affected (by pack/lane)

The failure was cross-pack:

- **RTDL core** (IEG/OFP/CSFB paths)
- **Decision lane** (DL/AL/DLA-related DB call paths)
- **Case/labels lane** (CaseTrigger/CaseMgmt/LabelStore DB call paths)

At code-callsite level, failure signatures were observed in adapters such as:
- `identity_entity_graph/store.py`
- `online_feature_plane/store.py`
- `context_store_flow_binding/store.py`
- `degrade_ladder/emission.py`
- `action_layer/storage.py`
- `decision_log_audit/storage.py`
- `case_trigger/replay.py`
- `case_mgmt/observability.py`
- `label_store/observability.py`

### Exact failure signature

- **Error class:** `psycopg.OperationalError`
- **Connect target in failures:** `localhost:5434`
- **OS-level signal in message:** `Address already in use (10048 / 0x00002740)`
- **Repeated call pattern in failing paths:** fresh `psycopg.connect(...)` inside hot-loop style operations (`with self._connect() as conn` style pattern)

### Observable runtime symptoms

1. Immediately after the 200-event run, live packs that should have remained healthy dropped to `stopped` (obs/gov was the only lane that stayed up).
2. Run/operate parity status no longer reflected full-platform live closure even though stream emission gate had just succeeded.
3. Process-level failure logs across multiple components converged on the same DB connection failure class, proving this was not a single-component logic bug.

That pin is why I classified this as a datastore-hardening incident, not a feature bug: the common break surface was database connection lifecycle under orchestration pressure.

## Q4) What was the root cause (not the symptom)?

The root cause was a **database lifecycle design mismatch** between how the workers were written and how long-running orchestrated runtime behaves.

### Root cause (primary)

Across many services, hot-path DB operations used a pattern equivalent to:
- open a fresh Postgres connection for a small unit of work,
- do one read/write,
- close,
- repeat continuously in worker loops.

In isolation, that pattern can look harmless. Under multi-pack concurrent daemons, it creates connection churn pressure and unstable connect behavior.

So the root cause was not “Postgres down.”  
It was **application-level connection management policy**: per-call connect/disconnect at scale across multiple continuously running workers.

### Root cause (secondary amplifier)

The runtime error posture in worker loops was too brittle for transient DB connect faults:
- a connection establishment failure commonly propagated as process-fatal,
- so one transient connect fault became service drop,
- and because this happened across many workers with the same lifecycle pattern, pack-level collapse followed.

So the full root-cause chain was:
1. per-call connection churn in hot loops,
2. plus insufficient transient-fault containment at worker loop boundaries,
3. producing synchronized multi-service instability after stream completion.

### What it was *not*

It was not primarily:
- a schema bug,
- a single malformed SQL statement,
- event volume logic,
- or business-rule regression in IG/DF/AL.

Those were not the shared denominator across failing components.  
The shared denominator was DB lifecycle handling.

### Why this distinction mattered

If I had treated this as an isolated component bug, I would have patched symptoms and kept the platform fragile.  
Classifying it as a lifecycle root cause forced a cross-platform connector strategy and runtime posture change, which is exactly why the later reruns could stay green post-stream.

## Q5) What change did you make (schema, naming, migrations, connection pattern, retry discipline)?

I made a **connection-lifecycle remediation**, then a **transaction-lifecycle correction**.  
I did not “hide” this with schema rewrites.

### 1) Connection pattern change (primary remediation)

I introduced a shared runtime connector:
- `fraud_detection.postgres_runtime.postgres_threadlocal_connection(...)`

Behavior:
- thread-local connection reuse keyed by DSN + connect kwargs,
- avoids fresh `psycopg.connect(...)` for every small operation,
- drops cached connections when closed/broken.

Then I migrated live-pack adapters from per-call connect style to this shared connector across:
- RTDL stores (IEG/OFP/CSFB paths),
- decision-lane stores/checkpoints/replay paths (DF/AL/DLA/DL-related surfaces),
- case/label stores and observability surfaces,
- parity-adjacent runtime/reporter/checkpoint paths used by operate status and closure.

This directly removed the repeated connect/disconnect churn pattern that was killing daemons.

### 2) Retry discipline change

In the connector itself, I added bounded connect retry for transient establishment faults:
- retry class: `psycopg.OperationalError`,
- attempts: `3`,
- backoff: short exponential backoff (base `0.05s`).

This is intentionally bounded. It is resilience against brief connection turbulence, not infinite retry masking.

### 3) Transaction lifecycle correction (second remediation pass)

After first rollout, we detected `idle in transaction` / lock-wait side effects.  
So I corrected context-manager exit semantics to mirror safe psycopg behavior:

- on successful scope exit (non-autocommit): `commit()`,
- on exception: `rollback()`,
- if commit/rollback fails: drop cached connection.

That closed the lock-retention side effect without reverting the connector architecture.

### 4) What I did **not** change (important for defensibility)

For this incident, I did **not** rely on:
- schema redesign,
- naming-convention changes,
- or migration-driven table rewrites
as the primary fix.

Those were not the root-cause lane.  
The root-cause lane was connection + transaction lifecycle behavior under multi-service runtime load.

### 5) Why this change set was the right one

It solved the issue at the shared failure surface:
- one lifecycle policy for many components,
- bounded retry for transient connect faults,
- deterministic transaction closure to prevent lock accumulation,
- no semantic drift in domain contracts/idempotency rules while hardening runtime stability.

## Q6) How did you verify it (repeat run, targeted test, soak, “no regression” check)?

I verified in four layers, in order. I did not call it fixed after only unit tests.

### 1) Targeted correctness/regression tests on touched datastore paths

After the connector + transaction-lifecycle fixes, I ran focused suites on the exact lanes whose DB behavior changed:
- decision-fabric checkpoint/replay paths,
- case-trigger checkpoint paths,
- action-layer storage paths,
- DLA intake/storage paths,
- CSFB intake/storage paths.

Outcome:
- focused suite set passed (`30 passed`),
- proving no immediate functional regression in the updated DB lifecycle surface.

### 2) Full runtime repeat-run under strict bounded gates

I created a fresh run scope and re-executed the full acceptance sequence, not a partial smoke:
- run id: `platform_20260210T091951Z`
- gate order:
  - Gate-20 (`WSP_MAX_EVENTS_PER_OUTPUT=20`)
  - Gate-200 (`WSP_MAX_EVENTS_PER_OUTPUT=200`)

Expected vs observed:
- Gate-20 expected total: `80` (4 outputs x 20) -> observed `80`
- Gate-200 expected total: `800` (4 outputs x 200) -> observed `800`

Per-output stop markers matched bounded behavior for both gates (all required outputs reached cap and stopped by boundary).

### 3) Post-stream soak/liveness verification (the key closure check)

Because the original failure happened **after** stream completion, I explicitly validated post-run liveness:
- checked full operate status immediately post-stream,
- then checked again after idle hold.

Required condition:
- all packs remain `running ready` across:
  - control/ingress,
  - RTDL core,
  - decision lane,
  - case/labels,
  - obs/gov.

Observed:
- all packs stayed `running ready` in both checks.

### 4) No-regression signature check + conformance evidence

I ran a recurrence-signature check for the exact historical collapse markers:
- no recurrence of `psycopg.OperationalError` with address-in-use signature,
- no repeat of the post-stream daemon collapse pattern.

I also required run-scoped closure artifacts to be green:
- platform run report generated for the run,
- environment conformance status `PASS`.

### Why this verification is strong

It combines:
- component-level regression checks,
- end-to-end rerun under production-shaped bounded load,
- post-stream durability check (where the incident actually manifested),
- and explicit recurrence-signature absence.

That is why I consider the fix verified, not just “appears improved.”

## Q7) What new guardrail did you add so it doesn’t silently recur?

I added guardrails in two layers: **runtime code guardrails** and **acceptance/governance guardrails**.

### 1) Runtime code guardrails (prevents the same failure class in-process)

The shared Postgres runtime connector is itself a guardrail surface, not just a convenience wrapper:

- **No hot-loop fresh-connect pattern by default**:
  - services now use thread-local reused connections instead of repeated per-call `psycopg.connect(...)`.
- **Bounded transient fault policy**:
  - connection establishment retries are limited and explicit (`OperationalError` class, bounded attempts/backoff), so transient faults are absorbed but infinite masking is avoided.
- **Deterministic transaction closure**:
  - successful non-autocommit scopes are committed,
  - exception scopes are rolled back,
  - failed commit/rollback drops the cached connection.
- **Broken-connection eviction**:
  - closed/broken cached handles are discarded, preventing poisoned-connection reuse.

This directly blocks the exact churn + lifecycle drift pattern that caused the collapse.

### 2) Acceptance/governance guardrails (prevents false-green declarations)

I changed closure posture so we do not certify health from stream completion alone:

- **Mandatory post-stream liveness gate**:
  - after bounded run closure, all packs must still be `running ready`.
- **Idle-hold liveness recheck**:
  - same pack matrix must remain green after a hold window, not only immediately after stream stop.
- **Recurrence-signature scan**:
  - explicit check for prior collapse signatures (`OperationalError` / address-in-use pattern) must remain negative.
- **Conformance artifact requirement**:
  - environment conformance and run report must both close green for the active run.

This guardrail is crucial because the original incident happened after the stream gate had already looked good.

### 3) Why this is a real anti-recurrence control

Without these guardrails, this class of issue can pass “throughput tests” and still fail in live operation minutes later.

With these guardrails:
- code-level lifecycle behavior is constrained toward stable DB usage,
- and operational acceptance refuses to mark green unless post-stream durability is proven.

That combination is what turns the fix from “patched once” into “harder to regress silently.”
