# Cluster 3 - Round 1 Answers

## Q1) What is the bounded-run mechanism (20/200), where is it enforced, and how do you know it really stopped?

The bounded-run mechanism is a deliberate acceptance gate, not an ad-hoc test flag.

### What 20/200 means

`20/200` means:
- set `WSP_MAX_EVENTS_PER_OUTPUT=20` for smoke gate, then
- set `WSP_MAX_EVENTS_PER_OUTPUT=200` for baseline bounded closure.

Important precision:
- the cap is **per output_id lane**, not a single global cap.
- with 4 streamed output lanes in local parity, expected total emitted is:
  - Gate-20: `4 * 20 = 80`
  - Gate-200: `4 * 200 = 800`

### Where the cap is enforced

Enforcement chain is explicit:
1. Operator/run target sets bounded knob (`WSP_MAX_EVENTS_PER_OUTPUT`).
2. Run/operate pack passes it to WSP READY consumer (`--max-events-per-output`).
3. WSP runner enforces the cap inside stream loop per output_id.
4. On cap hit, WSP persists checkpoint with `reason=max_events` and exits that output lane.

This is code-level enforcement, not convention:
- WSP runner emits `WSP stream stop ... emitted=<cap> reason=max_events`.
- WSP runner warns that max-events is per-output in concurrent mode and directs use of `WSP_MAX_EVENTS_PER_OUTPUT` for clarity.

### How I prove it really stopped (evidence posture)

I use three independent evidence surfaces:

1. Stop markers in platform narrative logs
- Anchor run (`platform_20260212T085637Z`) has explicit stop lines:
  - `... output_id=s3_event_stream_with_fraud_6B emitted=200 reason=max_events`
  - `... output_id=arrival_events_5B emitted=200 reason=max_events`
  - `... output_id=s1_arrival_entities_6B emitted=200 reason=max_events`
  - `... output_id=s3_flow_anchor_with_fraud_6B emitted=200 reason=max_events`

2. Session-level completion totals
- Same anchor run session shows `stream_complete` with `emitted=800`, matching `4 * 200`.

3. Checkpoint stop reason
- Session events include checkpoint writes with `reason=max_events`, proving lane termination was from cap boundary, not crash or external interruption.

### Gate-20 and Gate-200 certification examples

From recorded parity gate evidence:
- Gate-20 run: emitted `80` total (all four outputs reached `emitted=20` boundary).
- Gate-200 run: emitted `800` total (all four outputs reached `emitted=200` boundary).

So bounded acceptance is deterministic in this system: cap configured, cap enforced per lane, and cap closure proven by stop markers + totals + checkpoint reasons.

## Q2) What are your stream start-position policies (`trim_horizon` vs `latest`) and when do you use each?

I do not treat start position as a fixed global setting. I treat it as a correctness policy chosen per consumer role and per run objective.

### Policy 1: Control-bus READY intake (WSP) starts from `trim_horizon`, but with iterator progress memory

For the WSP READY control-bus reader, first read is from `TRIM_HORIZON` and then per-shard `NextShardIterator` is persisted in-memory for subsequent polls.

Why:
- `trim_horizon` on first attach prevents missing READY records that were published before consumer start/restart.
- iterator carry-forward prevents head-page replay starvation (the old failure mode where new READY never got reached).

So this policy is: **completeness first, then forward progress**.

### Policy 2: Live daemonized event consumers in bounded parity runs use `latest` by default

In local parity bounded acceptance runs, most long-running workers are started before SR publishes READY. For that posture, profile defaults are `event_bus_start_position: latest`.

Why:
- bounded 20/200 gates are intended to validate the active run window,
- replaying deep historical backlog (`trim_horizon`) can starve current-run flow and create false negatives inside the gate window.

This is why core live workers are wired to `latest` in local parity profile for acceptance-gate execution.

### Policy 3: Run-pinned consumers with no checkpoint get first-read safety override to `trim_horizon`

For decision-lane consumers where missing early records is unacceptable, there is an explicit first-read safeguard:
- if checkpoint is absent **and** `required_platform_run_id` is set,
- force first read to `trim_horizon`,
- then continue from checkpoint offsets.

This exists to prevent the startup race where `latest` can skip earliest records before first checkpoint is written.

### Policy 4: Repair/reconciliation runs use `trim_horizon` intentionally

When I am reconciling undercount or proving completeness, I use `trim_horizon` plus run-scope filtering and dedupe/checkpoint rails, so replay is deterministic and safe.

### Decision rule (what I actually follow)

I choose by objective:
- **Active-window bounded acceptance (20/200):** `latest` for pre-started live workers.
- **Completeness/recovery or no-checkpoint run-pinned intake:** `trim_horizon` on first read, then checkpoint progression.

### Evidence this policy came from real failures, not theory

- We observed `trim_horizon` backlog starvation in live parity gates, causing current-run decision flow to stall despite ingest movement. Moving live parity workers to `latest` restored bounded-run timeliness.
- We also observed start-position races where early records could be missed; for run-pinned consumers, first-read `trim_horizon` guard was added when checkpoint is absent.

So the policy is deliberately mixed because the failure modes are different: one side loses timeliness, the other loses completeness. The final posture protects both.

## Q3) Describe the consumer identity model: how do you ensure you don’t accidentally fork consumer groups or re-consume from the wrong position?

My model is explicit: **consumer identity is not “process name”; it is a persisted cursor namespace plus run scope.**

### The identity tuple

For each streaming worker, identity is effectively:
- `stream_id` (component stream namespace),
- `topic`,
- `partition_id`,
- plus run scope guard (`required_platform_run_id`).

Checkpoint rows are keyed by `(stream_id, topic, partition_id)`.  
So if identity is stable, the reader resumes exactly from the last committed offset/sequence; if identity changes, it intentionally creates a new cursor namespace.

### How I prevent accidental identity forks

I enforce deterministic stream naming:
- workers derive `stream_id` from profile defaults (for example `df.v0`, `al.v0`, `case_trigger.v0`, `case_mgmt.v0`, `dla.intake.v0`),
- then append run scope as `::<platform_run_id>` when active run id is present.

That means one acceptance run has one stream namespace per worker lane.  
I am not relying on ad-hoc operator-entered consumer-group strings.

### How I prevent wrong-position re-consume

1. Resume from checkpoint first
- If `(stream_id, topic, partition)` checkpoint exists, read from stored `next_offset` / `next_sequence` (not from head/tail guesswork).

2. First-read safety when run pin is required
- If checkpoint is absent and `required_platform_run_id` is set, first read is forced to `trim_horizon` for protected consumers (so we do not miss earliest in-run records before first checkpoint lands).

3. Side effects are run-scoped
- Even when records are seen, workers enforce `required_platform_run_id` against envelope pins and skip out-of-scope records.
- That prevents cross-run contamination while still allowing checkpoint progression through non-target backlog.

### Scenario-level lock (anti-mix guard)

For core decision lanes, once first valid `scenario_run_id` is accepted, worker state locks to that scenario for the run loop.  
If later records carry another scenario id, they are not processed as in-scope flow for that worker cycle.

This prevents accidental mixing of two scenarios into one reconciliation/health narrative.

### WSP READY consumer identity guard (control-plane side)

Control-plane has a separate anti-fork guard:
- READY message must have matching `platform_run_id` and `scenario_run_id` against run facts,
- READY is compared to active platform run id; out-of-scope READY becomes `SKIPPED_OUT_OF_SCOPE` (`PLATFORM_RUN_SCOPE_MISMATCH`),
- dedupe record per message id is persisted in `wsp/ready_runs/...` so historical control-bus replay does not retrigger streaming for already-terminal messages.

### Practical failure mode this model fixed

We hit both sides in real runs:
- backlog starvation from replay posture,
- early-record misses from `latest` startup with no checkpoint.

The current identity model fixed that by combining:
- stable checkpoint namespace (`stream_id`),
- strict run pin (`required_platform_run_id`),
- first-read safety override,
- and scenario lock.

That is why we can now run bounded 20/200 repeatedly without silent forked cursors or random replay position drift.

## Q4) One concrete incident: what failed, how it was proven, what changed, and what proved recovery?

I’ll use the control-plane starvation incident because it was a real streaming correctness failure that looked healthy at process level.

### What went wrong

Run `platform_20260210T042030Z` had all orchestrated services shown as running/ready, but flow did not move:
- ingress counters stayed at zero,
- decision/outcome counters stayed at zero,
- bounded-run progress never started for the active run.

The actual fault was in READY consumption over Kinesis:
- the reader reacquired a `TRIM_HORIZON` iterator every poll,
- read one page only,
- then returned.

With historical control messages larger than one page, the consumer kept replaying the head forever and never advanced to newly published READY for the active run.

### How I detected and proved it

I did not trust process liveness alone. I checked three layers:
- flow metrics: run report showed flat zero movement across lanes,
- runtime behavior: READY consumer kept cycling old records and logging stale-reference misses (`NoSuchKey` pattern),
- code path: iterator logic in control-bus reader confirmed one-page replay behavior with no durable per-shard progress between polls.

That combination proved this was not “slow stream”; it was starvation caused by iterator semantics.

### What I changed

I changed control-bus Kinesis read behavior to be progression-safe:
- keep per-shard `NextShardIterator` in memory across polls,
- drain pages until catch-up / empty page, not single-page only,
- continue using existing READY dedupe semantics (did not loosen dedupe correctness).

So the fix attacked root cause (iterator progression), not symptoms.

### What proved recovery

Recovery proof came from bounded gates after the fix chain:
- `platform_20260210T082746Z` passed Gate-20 with total emitted `80` (4 outputs x 20),
- `platform_20260210T083021Z` passed Gate-200 with total emitted `800` (4 outputs x 200),
- run status returned running/ready across packs with conformance PASS on the 200 gate run.

The key signal is that READY now activated the intended current run, bounded streaming executed, and end-to-end flow closure resumed under strict gates.

## Q5) What are your retry rules, and how do you prevent duplicate publish during transient errors?

I split this into two planes on purpose:
- **WSP -> IG push retry policy** (transport resilience),
- **IG admission state machine** (duplicate/ambiguity safety).

That separation is how I avoid “retry == duplicate side effects.”

### Retry rules (WSP -> IG)

WSP applies bounded exponential backoff with jitter when pushing envelopes to IG.

Configured knobs:
- `ig_retry_max_attempts`
- `ig_retry_base_delay_ms`
- `ig_retry_max_delay_ms`

Retryable conditions:
- request timeout,
- request-level transport exceptions,
- HTTP `408`, `429`, and all `5xx`.

Non-retryable conditions:
- other `4xx` (schema/policy/client rejection path).
- those fail immediately as `IG_PUSH_REJECTED` (no loop).

Exhaustion behavior:
- if retryable failures continue to attempt limit, WSP raises `IG_PUSH_RETRY_EXHAUSTED` and stops that stream path fail-closed.

### How duplicate publish is prevented (core law)

Retries are safe because the event identity is deterministic and IG enforces idempotent admission:

1. Deterministic event identity at source
- WSP derives `event_id` deterministically from output identity + primary key + run pins.
- A retried push keeps the same `event_id` for the same logical event.

2. Deterministic dedupe key at IG boundary
- IG computes dedupe key from `(platform_run_id, event_class, event_id)`.

3. Admission state machine prevents unsafe republish
- On first sighting, IG records `PUBLISH_IN_FLIGHT`.
- On publish success, state moves to `ADMITTED` with `eb_ref`.
- On publish exception, IG marks `PUBLISH_AMBIGUOUS` and quarantines (no automatic republish).

4. Duplicate requests converge safely
- If same dedupe key arrives again and prior state is `ADMITTED`, IG returns `DUPLICATE` and does not publish again.
- If state is `PUBLISH_IN_FLIGHT` or `PUBLISH_AMBIGUOUS`, IG fail-closes and quarantines rather than guessing.

This is intentional: after ambiguity, the system prefers explicit reconciliation over speculative republish.

### Why this handles real transient failure risk

The hardest real-world case is “producer didn’t get a clean ack, but downstream may already have received it.”  
Our posture handles that:
- WSP may retry same envelope,
- IG dedupe key collapses repeats,
- only one publish is accepted as authoritative,
- ambiguous states are held and surfaced, not auto-replayed blindly.

### Validation coverage that backs this

- WSP retry test proves `429` retries to success within bounds.
- WSP retry test proves non-retryable `400` fails immediately (no repeated push).
- IG duplicate test proves second admission does not republish to bus.
- IG ambiguity test proves publish failure is recorded as `PUBLISH_AMBIGUOUS` and quarantined with anomaly evidence.

## Q6) What is your “stream health vs flow health” lesson: what looked healthy but wasn’t, and how did you prove the truth?

The core lesson was:
- **stream/process health is necessary but not sufficient**,
- only **flow closure evidence** tells the truth.

### What looked healthy but was actually broken

In a failure run (`platform_20260210T042030Z`), orchestration showed services as running/ready, so the platform looked green at a glance.  
But business flow was effectively dead:
- ingress movement was zero,
- decision/outcome movement was zero,
- bounded run never actually advanced for the active run.

So we had a classic false-green: processes alive, value path stalled.

### How I proved the real state

I stopped using single-surface health and used cross-plane checks:

1. Runtime liveness plane
- are workers up and reporting ready?

2. Stream progression plane
- did READY get consumed for the active run?
- did WSP produce bounded stop markers for required outputs?

3. Business-flow plane
- did IG admissions/receipts move?
- did decision lane counters move?
- did outcomes/case/label counters move?

The contradiction across those planes exposed truth:
- liveness was green,
- flow planes were red/flat.

### The second reinforcement of the same lesson

Even after control-bus starvation was fixed, we saw another false confidence pattern:
- IG showed activity,
- but decision lane stayed empty in gate window because consumers were replaying historical backlog.

That proved a stronger point:
- **“ingress moving” is still not enough**; you must prove end-to-end active-run progression.

### What changed operationally after this lesson

I changed the acceptance posture from “process matrix green” to “flow-closure green.”

Now I only claim green when all are true:
- bounded WSP stop achieved on required outputs,
- IG receipts/admissions match expected bounded counts,
- decision lane and downstream lanes show non-zero in-scope movement,
- no unresolved ambiguity/blocker states open.

That shift is one of the biggest platform maturity upgrades we made: it removed silent false-green and made run claims defensible.

## Q7) Anchor run: run id, stream start→stop evidence, and IG/EB evidence

Anchor run:
- `platform_run_id`: `platform_20260212T085637Z`
- `run_root`: `runs/fraud-platform/platform_20260212T085637Z/`
- `s3_root`: `s3://fraud-platform/platform_20260212T085637Z/`

### Stream start -> bounded stop evidence

1. Start/stop in narrative log
- `runs/fraud-platform/platform_20260212T085637Z/platform.log`
- shows stream starts for required outputs, then bounded stops with `reason=max_events` and `emitted=200` for:
  - `arrival_events_5B`
  - `s3_event_stream_with_fraud_6B`
  - `s1_arrival_entities_6B`
  - `s3_flow_anchor_with_fraud_6B`

2. Session completion tally
- `runs/fraud-platform/platform_20260212T085637Z/session.jsonl`
- contains `stream_complete` with `emitted=800` (4 outputs x 200).

### IG/EB evidence that admitted offsets matched bounded expectation

1. Run report ingress summary
- `runs/fraud-platform/platform_20260212T085637Z/obs/platform_run_report.json`
- confirms:
  - `ingress.sent = 800` (matches bounded WSP total),
  - `publish_ambiguous = 0`,
  - `duplicate = 0` for ingress summary.

2. Receipt refs proving IG commit path to EB
- same run report includes `receipt_refs_sample` under:
  - `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/...`
- sample from that list:
  - `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/00965821d94105a3d88ad6085b3c5b37.json`

3. Offset truth ownership note
- IG persists admission state with EB coordinates (`topic/partition/offset`) as part of admitted state and receipt model.
- for this run, the bounded total (`800`) and zero ambiguity posture provide the acceptance-grade evidence that stream-to-admission offset progression closed as intended.

