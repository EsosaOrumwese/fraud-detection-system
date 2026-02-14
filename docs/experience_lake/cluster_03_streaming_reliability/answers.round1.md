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
- In `runs/fraud-platform/platform_20260212T085637Z/session.jsonl`, the checkpoint event is `event_kind=checkpoint_saved` and cap-stop is recorded at `details.reason=max_events`.
- That proves termination happened at bounded cap, not from crash or manual kill.

### Gate-20 and Gate-200 certification examples

From recorded parity gate evidence:
- Gate-20 run: emitted `80` total (all four outputs reached `emitted=20` boundary).
- Gate-200 run: emitted `800` total (all four outputs reached `emitted=200` boundary).

So bounded acceptance is deterministic in this system: cap configured, cap enforced per lane, and cap closure proven by stop markers + totals + checkpoint reasons.

## Q2) What are your stream start-position policies (`trim_horizon` vs `latest`) and when do you use each?

I treat start position as a per-consumer correctness control, not one global default.

### Current local_parity map (what is actually configured)

| Consumer lane | Default start position | Where configured | First-read safety override |
|---|---|---|---|
| WSP READY control-bus reader | `trim_horizon` on initial shard iterator, then `NextShardIterator` carry-forward | hardcoded in `src/fraud_detection/world_streamer_producer/control_bus.py` (`KinesisControlBusReader`) | Not needed; progression is maintained by persisted in-memory shard iterators during process lifetime |
| IEG projector | `latest` | `config/platform/profiles/local_parity.yaml` -> `ieg.wiring.event_bus.start_position` | No |
| OFP projector | `latest` | `config/platform/profiles/local_parity.yaml` -> `ofp.wiring.event_bus.start_position` | No |
| CSFB intake | `latest` | `config/platform/profiles/local_parity.yaml` -> `context_store_flow_binding.wiring.event_bus.start_position` | No |
| DF worker | `latest` | `config/platform/profiles/local_parity.yaml` -> `df.wiring.event_bus_start_position` | No |
| AL worker | `latest` | `config/platform/profiles/local_parity.yaml` -> `al.wiring.event_bus_start_position` | Yes: if checkpoint is missing and `required_platform_run_id` is set, AL forces `trim_horizon` for first read |
| DLA intake | `latest` | `config/platform/profiles/local_parity.yaml` -> `dla.wiring.event_bus_start_position` | Yes: if checkpoint is missing and `required_platform_run_id` is set, DLA forces `trim_horizon` for first read |
| Case Trigger | `latest` | `config/platform/profiles/local_parity.yaml` -> `case_trigger.wiring.event_bus_start_position` | No |
| Case Mgmt | `latest` | `config/platform/profiles/local_parity.yaml` -> `case_mgmt.wiring.event_bus_start_position` | No |
| Archive Writer | `latest` | `config/platform/profiles/local_parity.yaml` -> `archive_writer.wiring.event_bus_start_position` | No |

### Why the policy is mixed

- Active-window acceptance gates (`20/200`) are time-bounded; if live workers start before READY, `latest` prevents historical backlog from starving the current window.
- For run-pinned lanes where missing first in-run records is unacceptable (AL and DLA), missing-checkpoint first-read override to `trim_horizon` protects completeness.
- Control-plane READY has its own safety pattern: first attach from `trim_horizon`, then iterator carry-forward so it does not re-read head forever.

### Historical evidence behind this policy

- `platform_20260210T042533Z`: ingress moved, decision lane stayed flat; root cause was backlog starvation under replay-heavy posture.
- After policy hardening + iterator fix, Gate-20 and Gate-200 closures were restored (`platform_20260210T082746Z`, `platform_20260210T083021Z`).

## Q3) Describe the consumer identity model: how do you ensure you don’t accidentally fork consumer groups or re-consume from the wrong position?

My model is explicit: **consumer identity is a persisted checkpoint namespace plus run scope, not a process name.**

### Identity tuple and persisted checkpoint key

For kinesis consumers, the checkpoint identity is:
- `stream_id` (lane namespace),
- `topic`,
- `partition_id`.

The persisted cursor is stored as `next_offset` + `offset_kind`.
That means re-read position is deterministic and auditable.

Concrete example from the anchor run checkpoint database:
- DB: `runs/fraud-platform/platform_20260212T085637Z/decision_fabric/consumer_checkpoints.sqlite`
- Table: `df_worker_consumer_checkpoints`
- Key columns: `stream_id, topic, partition_id`
- Cursor columns: `next_offset, offset_kind`
- Stored row example: `stream_id=df.v0::platform_20260212T085637Z`, `topic=fp.bus.traffic.fraud.v1`, `offset_kind=kinesis_sequence`

### How stream_id is minted (not conceptual, literal)

Run-scoped suffixing is literal code, not documentation intent:
- `stream_id = _with_scope(base_stream, platform_run_id)`
- Result shape: `<base_stream>::<platform_run_id>`
- Implemented in workers like:
  - `src/fraud_detection/decision_fabric/worker.py`
  - `src/fraud_detection/action_layer/worker.py`
  - `src/fraud_detection/case_trigger/worker.py`
  - `src/fraud_detection/case_mgmt/worker.py`

So consumer-group fork risk is reduced by construction: one run => one scoped stream namespace per lane.

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

### WSP control-plane identity and duplicate guard

Control-plane has a separate anti-fork guard:
- READY message must have matching `platform_run_id` and `scenario_run_id` against run facts,
- READY is compared to active platform run id; out-of-scope READY becomes `SKIPPED_OUT_OF_SCOPE` (`PLATFORM_RUN_SCOPE_MISMATCH`),
- dedupe record per message id is persisted under `.../wsp/ready_runs/<message_id>.jsonl` so historical control-bus replay does not retrigger already-terminal READY messages.

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
- flow metrics: historical run report path for that run was `runs/fraud-platform/platform_20260210T042030Z/obs/platform_run_report.json` (all critical counters flat),
- runtime behavior: READY consumer loop evidence from `runs/fraud-platform/operate/local_parity_control_ingress_v0/logs/wsp_ready_consumer.log`,
- code path: `src/fraud_detection/world_streamer_producer/control_bus.py` confirmed shard iterators were re-created from `TRIM_HORIZON` and only one page was read per poll.

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

Concrete recovery log surfaces:
- `runs/fraud-platform/operate/local_parity_control_ingress_v0/logs/wsp_ready_consumer.log` (contains 20/200 stop markers with `reason=max_events`)
- `runs/fraud-platform/platform_20260212T085637Z/platform.log` (anchor bounded-stop evidence surface with the same stop semantics)

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

- WSP retryable success path: `tests/services/ingestion_gate/test_phase5_retries.py::test_with_retry_succeeds_after_failures`
- WSP non-retryable 4xx fail-fast: `tests/services/world_streamer_producer/test_push_retry.py::test_push_rejects_non_retryable_4xx`
- IG duplicate no-republish: `tests/services/ingestion_gate/test_admission.py::test_duplicate_does_not_republish`
- IG publish ambiguity quarantine: `tests/services/ingestion_gate/test_admission.py::test_publish_ambiguous_quarantines_and_marks_state`

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

Historical artifact note:
- The run-specific report file for that run is not retained in the current workspace, but the original path and conclusion were recorded during implementation: `runs/fraud-platform/platform_20260210T042030Z/obs/platform_run_report.json`.

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

Even after control-bus starvation was fixed, we saw another false confidence pattern in `platform_20260210T042533Z`:
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
  - `ingress.sent = 800` (bounded WSP output total),
  - `ingress.admit = 1577`,
  - `ingress.duplicate = 0`,
  - `ingress.quarantine = 0`,
  - `ingress.publish_ambiguous = 0`.

Counter-semantics clarification (why `admit` can exceed `sent`):
- `WSP emitted=200` is producer-side bounded sends per required `output_id` lane.
- `ingress.sent` is the WSP bounded-output total for the gate window (`4 * 200 = 800` in this run).
- `ingress.admit` is IG-wide admit volume for the run scope across event families/producers, so it is not constrained to the bounded WSP producer count and can be higher.
- Clean ingress posture for this run is still validated by `ingress.duplicate=0`, `ingress.quarantine=0`, and `ingress.publish_ambiguous=0`.

JSON paths used:
- `ingress.sent`
- `ingress.admit`
- `ingress.duplicate`
- `ingress.quarantine`
- `ingress.publish_ambiguous`

2. Receipt refs proving IG commit path to EB
- same run report includes `receipt_refs_sample` under:
  - `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/...`
- sample from that list:
  - `s3://fraud-platform/platform_20260212T085637Z/ig/receipts/00965821d94105a3d88ad6085b3c5b37.json`

JSON path used:
- `evidence_refs.receipt_refs_sample`

3. Offset truth ownership note
- IG persists admission state with EB coordinates (`topic/partition/offset`) as part of admitted state and receipt model.
- for this run, the bounded total (`800`) and zero ambiguity posture provide the acceptance-grade evidence that stream-to-admission offset progression closed as intended.

