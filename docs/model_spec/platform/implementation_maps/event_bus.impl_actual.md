# Event Bus (EB) Implementation Map (Actual)
_Living decision trail and execution log_

---

## Entry: 2026-01-29 02:23:10 — EB v0 build plan drafted (streaming‑only alignment)

### Why now
- WSP → IG streaming path is green for local smoke; next vertex is EB.
- Legacy pull is retired; EB must be planned for **IG‑only ingress** and **canonical envelope** semantics.

### Thinking trail (live reasoning)
- EB is opaque but its **join semantics** are the platform’s spine: IG must only emit admitted facts and EB must ACK only after durable append.
- We need a **connected v0**: local file‑bus should be correct and replayable before any dev/prod adapter (Kinesis).
- Local smoke must be bounded (cap events) but still prove “append + offsets + replay”.
- EB v0 can ship without full retention/archival machinery; those belong in v1+.

### Decisions captured in the plan
- **Phased approach**: contracts → local file‑bus durability → replay utilities → IG publish hardening → dev adapter parity.
- **Environment ladder**: local = file‑bus smoke; dev = Kinesis/LocalStack; prod = managed streaming (future).
- **Offsets**: file‑bus offsets are integers; Kinesis offsets may be strings (sequence numbers).

### Artifact created
- New build plan: `docs/model_spec/platform/implementation_maps/event_bus.build_plan.md`

### Next actions (when implementation begins)
- Implement Phase 1/2 components with explicit ACK semantics.
- Add local tail/replay tooling and smoke tests.
- Wire IG publish receipts to include EB refs.

## Entry: 2026-01-29 02:28:20 — v0 EB decisions locked

### What was open
- Partitioning profile, offset type, checkpoint store.

### Decisions locked (v0)
- **Partitioning:** local uses a single partition; dev uses IG‑chosen deterministic key (merchant_id → event_id fallback).
- **Offset type:** store `offset` as string with `offset_kind` to support file‑bus and Kinesis without changing receipt shape.
- **Checkpoint store:** local file checkpoints; dev Postgres.

### Update applied
- `docs/model_spec/platform/implementation_maps/event_bus.build_plan.md` updated to replace “open decisions” with locked v0 choices.

---

## Entry: 2026-01-29 02:36:40 — Phase 1 detailed plan (EB contracts + interface)

### Problem framing (what Phase 1 must solve)
We need a **stable EB boundary contract** and an **EB adapter interface** so IG can publish admitted facts without binding to a specific backend. This is the foundation for v0 local file‑bus and later dev Kinesis parity.

### Live reasoning trail
- EB is opaque, but **its boundary contract is not**: IG receipts must encode the EB position returned on append. That position becomes the replay token for all downstream consumers.
- Existing `ingestion_receipt.schema.yaml` already has `eb_ref`, but it assumes integer offsets (file‑bus only). We need a shape that can carry Kinesis sequence numbers without breaking receipt schema later.
- If EB interface code lives inside IG, EB becomes “owned by IG” in the codebase, which conflicts with the graph view. Better to move the interface to a shared `event_bus` module and have IG depend on it.

### Decisions to lock in Phase 1
1) **Receipt shape update (offset as string)**
   - Keep `partition_id` as integer.
   - Store `offset` as string and add `offset_kind` to distinguish `file_line` vs `kinesis_sequence`.
   - Reason: avoid a future breaking schema change when adding Kinesis.

2) **EB interface location**
   - Recommended: create `src/fraud_detection/event_bus/` module and move `EbRef` + `EventBusPublisher` there.
   - IG should import EB interface from this shared module; file‑bus stays as a local adapter implementation.
   - Alternative: keep in IG; rejected because it blurs component ownership and will be harder to share with future consumers.

### Exact Phase 1 steps (intended edits)
1) **Contracts**
   - Update `docs/model_spec/platform/contracts/ingestion_gate/ingestion_receipt.schema.yaml`:
     - `eb_ref.offset` → string
     - add `eb_ref.offset_kind` enum: `file_line | kinesis_sequence`
   - Add EB contracts folder `docs/model_spec/platform/contracts/event_bus/` with at least:
     - `eb_ref.schema.yaml` (optional re‑usable EB ref schema for other contracts)
   - Update `docs/model_spec/platform/contracts/README.md` to list EB contracts.

2) **Code interface**
   - New module `src/fraud_detection/event_bus/publisher.py` (or similar): `EbRef`, `EventBusPublisher` protocol.
   - Move file‑bus implementation out of IG (`FileEventBusPublisher`), or re‑export it from EB module for local use.
   - Update IG imports to use the new EB module.

3) **Receipt writing**
   - When EB returns a ref, IG receipts should include `offset_kind`.
   - Default for file‑bus: `offset_kind=file_line` and `offset` = stringified line index.

4) **Tests / validation**
   - Update IG receipt schema validation tests (if any) to accept string offset + offset_kind.
   - Add unit test for `EbRef` serialization if needed.

### Invariants to enforce in Phase 1
- EB ACK always includes `topic`, `partition_id`, `offset`, `offset_kind`.
- IG never returns `ADMIT` without an EB ACK.
- Receipt schema change is backward compatible for local file‑bus and forward compatible for Kinesis.

### Open questions (confirmation needed)
- Confirm moving EB interface to `src/fraud_detection/event_bus/` is acceptable.
- Confirm `offset` stored as string with `offset_kind` (v0 lock).

### Validation plan (Phase 1)
- Schema validation of `ingestion_receipt` passes with new `eb_ref` shape.
- IG smoke path still writes receipts after EB ACK.

---

## Entry: 2026-01-29 05:18:25 — Phase 1 implementation start (contracts + interface)

### Pre‑implementation notes (decision trail)
- Proceeding only after explicit approval to: (a) move EB interface to `src/fraud_detection/event_bus/`, (b) change EB receipt offsets to string with `offset_kind`.
- This change is intentionally **schema‑first** to preserve forward compatibility with Kinesis; local file‑bus remains fully supported.
- EB remains opaque; Phase 1 only addresses **contract shape** and **interface placement**, not retention/consumer responsibilities.

### Planned execution steps (before code)
1) **Schema update** — `ingestion_receipt.schema.yaml`:
   - `eb_ref.offset` becomes string.
   - add `eb_ref.offset_kind` enum (`file_line`, `kinesis_sequence`).
2) **EB contracts folder** — create `docs/model_spec/platform/contracts/event_bus/eb_ref.schema.yaml`.
3) **EB interface relocation** — new `src/fraud_detection/event_bus/` module; move `EbRef`, `EventBusPublisher`, `FileEventBusPublisher` there.
4) **IG wiring update** — update imports and receipt assembly to include `offset_kind`.
5) **SQLite indices** — adjust IG admission/ops index tables to store offset as TEXT + offset_kind; add lightweight migration for existing DBs.
6) **Tests** — update IG ops/index tests expecting `eb_ref` to include `offset_kind` and string offsets.
7) **Validation** — run targeted tests to confirm receipt schema accepts new EB ref shape.

### Constraints
- Do **not** expand EB responsibilities beyond publish + receipt shape.
- Do **not** touch engine or SR/WSP flow semantics.

## Entry: 2026-01-29 05:23:43 — Phase 1 implementation (contracts + interface)

### What was implemented
- **Receipt schema updated**: `eb_ref.offset` is now a string and `offset_kind` is required (`file_line`, `kinesis_sequence`).
- **EB contract added**: new `docs/model_spec/platform/contracts/event_bus/eb_ref.schema.yaml` and README index entry.
- **EB interface relocated**: created `src/fraud_detection/event_bus/` with `EbRef`, `EventBusPublisher`, and `FileEventBusPublisher`; IG now imports from this shared module.
- **Receipt assembly updated**: IG now emits `offset_kind` and string offsets; duplicates are normalized to include `offset_kind`.
- **SQLite indexes migrated**: admission and ops DBs now store `eb_offset` as TEXT and include `eb_offset_kind`, with `ALTER TABLE` guards for existing DBs.

### Rationale captured during build
- Offset shape must be forward‑compatible with Kinesis sequence numbers.
- EB interface must be shared (not IG‑owned) to avoid coupling as we add other EB adapters.
- Nullable/legacy receipts are normalized to avoid breaking duplicate flow.

### Tests executed
- `.\.venv\Scripts\python.exe -m pytest tests/services/ingestion_gate/test_ops_index.py tests/services/ingestion_gate/test_phase3_replay_load_recovery.py tests/services/ingestion_gate/test_health_governance.py -q`
- Result: **8 passed**

### Notes
- Phase 1 stays strictly at contract + interface layer (no EB backend behavior changes beyond receipt shape).

## Entry: 2026-01-29 05:34:17 — Phase 2 planning (local file‑bus durability)

### Phase intent
Deliver a **correct local EB implementation** with durable append semantics, stable offsets, and explicit ACK behavior so IG can treat EB as the fact log in v0. This phase is still local‑only; no Kinesis yet.

### Live reasoning (decision trail)
- Our EB interface is now shared and receipt shapes are forward‑compatible; Phase 2 must make the **local EB durable and deterministic**, not “just a stub.”
- File‑bus offsets must be stable and monotonic even with retries; at‑least‑once means duplicates may exist, so **offsets are for position only**, not dedupe.
- IG’s “admitted” decision must be tied to EB ACK, so EB publish must be **atomic enough**: if it returns an EbRef, the record is definitely appended.
- We should avoid implementing consumer coordination; Phase 2 focuses purely on **append + ACK + minimal tail proof**.

### Proposed plan (detailed)
1) **File‑bus write hardening**
   - Ensure append is atomic at the file level: open → write → flush → fsync (best‑effort on Windows).
   - Offset = line index (0‑based). Compute without reading full file if possible (seek + count or stored sidecar). For v0, a single read count is acceptable but we should cap it to avoid O(n) on every append.
   - Record structure includes `partition_key`, `payload`, and `published_at_utc`.

2) **Offset source of truth**
   - Option A (v0): store a per‑topic `head.json` containing next offset. Update it atomically after append.
   - Option B: compute count on append (simpler but slower). For v0 we can start with a head file to avoid O(n).
   - Decision criterion: correctness + local speed. (Will lock before implementation.)

3) **Receipt integration**
   - EB returns `EbRef(offset=str, offset_kind=file_line, published_at_utc=now)`.
   - IG receipts include this `eb_ref` and validate against schema.

4) **Health probe alignment**
   - Health check should treat file‑bus root as required and check writeability.

5) **Tests (must be green)**
   - Publish N records and assert offsets `0..N-1`.
   - Duplicate publish yields a new offset (no dedupe by EB).
   - Crash simulation: if head file exists but log missing (or vice‑versa), EB should recover (prefer log truth).

### Decisions needing confirmation
- **Offset source**: do we adopt a `head.json` per topic for O(1) offsets (recommended), or keep line‑counting in v0 for simplicity?

### Exit criteria (Phase 2 DoD)
- File‑bus returns stable offsets and published_at.
- IG receipts carry EB ref and pass schema validation.
- Unit tests cover monotonic offsets and crash recovery.


## Entry: 2026-01-29 05:35:43 — Phase 2 implementation start (local file‑bus durability)

### Pre‑implementation decision (locked)
- **Offset source:** per‑topic `head.json` storing `next_offset` (O(1) append). 
- Rationale: avoids O(n) line counts on each publish and keeps append deterministic for smoke runs. 
- Recovery rule: if `head.json` missing or inconsistent, derive next offset from log line count and rewrite head.

### Implementation plan (stepwise)
1) Extend FileEventBusPublisher:
   - Add per‑topic head file: `runs/fraud-platform/<platform_run_id>/event_bus/<topic>/head.json`.
   - On publish: read head (or compute from log), append record, flush, fsync, update head.
   - Emit `published_at_utc` in EbRef.

2) Add recovery logic:
   - If log exists but head is missing/corrupt → rebuild head from line count.
   - If head exists but log missing → treat log as empty and reset head to 0.

3) Update health probe (if needed):
   - Ensure file‑bus root is writeable and head directory is creatable.

4) Tests:
   - Monotonic offsets with head tracking.
   - Head recovery from missing head.
   - Head recovery from missing log.

### Constraints
- Do not add consumer coordination or retention logic.
- Keep EB as append‑only and opaque to payload semantics.

## Entry: 2026-01-29 05:39:10 — Phase 2 implementation (file‑bus head + durability)

### What changed
- **File‑bus now maintains per‑topic `head.json`** with `next_offset` to avoid O(n) counts.
- **Publish is hardened**: append → flush → fsync; head is written atomically via temp file swap.
- **Published timestamp** captured in EB ref (`published_at_utc`).
- **Recovery logic**:
  - Missing/corrupt head → rebuild from log line count.
  - Head present but log missing → reset to 0 (log is source of truth).

### Why this design
- Deterministic offsets with minimal overhead for local smoke runs.
- Clear recovery rule prevents silent offset drift.
- Still append‑only; no consumer coordination or retention logic added.

### Tests added
- `tests/services/event_bus/test_file_bus.py`:
  - Monotonic offsets
  - Head missing recovery
  - Log missing recovery

### Next validation
- Run EB unit tests + targeted IG tests (receipt includes published_at and offset_kind).

## Entry: 2026-01-29 05:41:50 — Phase 2 fix (head vs log precedence)

### Issue discovered
- Test showed `head.json` could override a missing log, causing offsets to resume at a stale value.

### Decision
- Treat the **log as source of truth**; if the log is missing, reset offset to 0 regardless of head.

### Change
- `_load_next_offset` now checks log existence before reading head.

### Outcome
- This prevents stale head state from resurrecting non‑existent offsets.

## Entry: 2026-01-29 05:37:33 — Phase 2 tests green

### Test run
- `.\.venv\Scripts\python.exe -m pytest tests/services/event_bus/test_file_bus.py -q`
- Result: **3 passed**

### Notes
- Offset recovery logic now prefers log truth; stale head values no longer resurrect missing offsets.

## Entry: 2026-01-29 06:07:06 — Phase 3 planning (replay/tail utilities)

### Phase intent
Provide **minimal replay/tail utilities** for the local EB file‑bus so we can verify durability and offsets without building consumer coordination. This is explicitly **verification tooling**, not a new platform component.

### Reasoning trail
- EB’s contract is based on `(topic, partition, offset)` positions. Phase 3 should let operators and tests **read back events by offset** to prove append correctness.
- We don’t want to introduce consumer groups or leases yet; Phase 3 keeps it simple: **read from an offset, return N records**.
- This tooling also allows us to validate that IG publishes to EB and that the file‑bus is replayable for smoke tests.

### Proposed plan
1) **Reader utility (local file‑bus)**
   - Implement `EventBusReader` with `read(topic, partition, from_offset, max_records)`.
   - Return records with their offsets and payloads.

2) **CLI for tail/replay**
   - `python -m fraud_detection.event_bus.cli tail --topic ... --from-offset ... --max ...`
   - Default: `partition=0`, `from_offset=0`, `max=20`.

3) **Smoke validation**
   - After `platform-smoke`, run tail and ensure records exist and offsets are contiguous.

4) **Tests**
   - Publish N records, read from offset 0, assert offsets/payloads.
   - Read from offset >0, assert subset returned.

### Constraints
- No consumer coordination, no retention/archival logic.
- Strictly read‑only verification tooling.

### Decision needed
- None (Phase 3 is bounded local‑only).

## Entry: 2026-01-29 06:08:42 — Phase 3 implementation start (local replay/tail utilities)

### Pre‑implementation intent
Deliver a **minimal EB replay/tail reader** for the local file‑bus so we can verify offsets and durability without introducing consumer coordination. This is strictly read‑only tooling.

### Decisions (with reasoning)
- **Reader is local‑only** in v0. Reason: avoid premature abstractions (Kinesis reader belongs to Phase 5/6).
- **CLI prints JSON lines** with `topic`, `partition`, `offset`, and the stored record. Reason: easy to pipe/inspect without imposing formatting opinions.
- **Default bus root**: `runs/fraud-platform/<platform_run_id>/event_bus` (same as file‑bus writer). Reason: keep local tooling zero‑config.

### Planned steps
1) Add `EventBusReader` to `src/fraud_detection/event_bus/reader.py`.
2) Add CLI `src/fraud_detection/event_bus/cli.py` with `tail` command.
3) Update `event_bus.__init__` to export reader.
4) Tests: publish via FileEventBusPublisher, then read by offset.

### Constraints
- No consumer groups, leases, or retention logic.
- Keep the reader side‑effect‑free.

## Entry: 2026-01-29 06:09:53 — Phase 3 implementation (replay/tail utilities)

### What was implemented
- **EventBusReader** (`src/fraud_detection/event_bus/reader.py`): local file‑bus reader with `read(topic, partition, from_offset, max_records)` returning typed records and offsets.
- **CLI tail utility** (`src/fraud_detection/event_bus/cli.py`): prints JSON lines containing `{topic, partition, offset, record}` for inspection and piping.
- **Exports updated** in `event_bus.__init__` for the reader types.

### Design choices made (and why)
- Reader is **local‑only** and read‑only: avoids premature coordination/consumer group design.
- CLI output is raw JSON lines to keep it tool‑friendly and not impose formatting opinions.
- Defaults align with file‑bus layout and local smoke expectations.

### Tests executed
- `.\.venv\Scripts\python.exe -m pytest tests/services/event_bus/test_reader.py -q`
- Result: **2 passed**

### Scope discipline
- No retention, no leases, no coordination; this is purely replay/tail verification for v0.

## Entry: 2026-01-29 06:11:45 — Phase 4 implementation start (IG→EB publish hardening)

### Intent
Harden the **IG→EB publish boundary** so that “admitted” only happens after a durable EB ACK, and receipts capture the EB position consistently. Phase 4 stays within v0 scope (file‑bus).

### Decisions (with reasoning)
- **Add EB publish timestamp to receipts** using `published_at_utc` from EB ACK to make ACK time explicit.
- **Record publish failures in health** on both handled `IngestionError` and unexpected exceptions so health can degrade on repeated EB issues.
- **Do not add retries at EB layer** yet; retry policy belongs to IG/producer (avoid hiding failure modes).

### Planned steps
1) Ensure IG receipt includes `eb_ref.published_at_utc` when available.
2) Record bus publish failures consistently in health (even for explicit EB errors).
3) Extend unit tests to assert EB ref fields are fully captured (offset_kind + published_at_utc).
4) Run targeted IG + EB tests.

### Constraints
- No consumer coordination, no retention, no Kinesis.
- Only adjust IG publish boundary semantics and receipts.

## Entry: 2026-01-29 06:13:17 — Phase 4 implementation (IG→EB publish hardening)

### What was implemented
- **Publish failure accounting**: IG now records bus publish failures for both explicit `IngestionError` and unexpected exceptions.
- **EB publish timestamp preserved**: duplicates now retain `published_at_utc` by persisting it in the admission index.
- **Admission index schema** now stores `eb_published_at_utc` and returns it for duplicate decisions.

### Why this matters
- Health probe can degrade on repeated EB failures (not just unhandled exceptions).
- Duplicate receipts stay **byte‑stable** with the original EB position and timestamp, preserving deterministic replay semantics.

### Tests executed
- `.\.venv\Scripts\python.exe -m pytest tests/services/ingestion_gate/test_phase3_replay_load_recovery.py -q`
- Result: **3 passed**

### Scope discipline
- No retries or consumer coordination added; EB remains an append‑only log with explicit ACK semantics.

## Entry: 2026-01-29 06:14:55 — Phase 5 planning (dev adapter parity: Kinesis/LocalStack)

### Phase intent
Provide a **dev‑parity EB adapter** so IG can publish to a real stream backend (LocalStack Kinesis or AWS) without changing semantics. This is still v0 scope; it focuses on publish only.

### Reasoning trail
- Local file‑bus proves append + offsets. Dev must validate we can publish into a real streaming system while preserving receipt shape and ACK semantics.
- We already use LocalStack for SR/IG experimentation; Kinesis is a pragmatic v0 dev target (Kafka can come later).
- We must **not** add consumer coordination or retention; only publishing and receipts are in scope.

### Proposed plan
1) **Kinesis adapter (publish‑only)**
   - Implement `KinesisEventBusPublisher` in `src/fraud_detection/event_bus/kinesis.py`.
   - Input: topic, partition_key, payload → `PutRecord`.
   - Output: `EbRef` with `offset_kind = kinesis_sequence`, `offset = SequenceNumber`, `published_at_utc` set at publish time.

2) **Config wiring**
   - Extend IG wiring to accept `event_bus_kind: kinesis` plus endpoint/region/credentials.
   - Use existing localstack envs for endpoint.

3) **Smoke validation (dev)**
   - Publish N records to LocalStack Kinesis; assert EB refs contain sequence numbers.
   - Keep smoke capped (N=5) and isolated in a dev profile.

4) **Tests**
   - Unit test with boto3 stubber (optional). Integration test gated by envs (LocalStack).

### Decisions needing confirmation
- Do we standardize on **LocalStack Kinesis** for dev EB parity, or do you want a different backend for v0 dev?

### Exit criteria
- IG can publish to Kinesis and receipts include `offset_kind=kinesis_sequence`.
- Local smoke still passes (file‑bus unaffected).


## Entry: 2026-01-29 06:16:14 — Phase 5 implementation start (Kinesis dev adapter)

### Pre‑implementation notes
- Scope: **publish‑only** Kinesis adapter for dev parity using LocalStack or AWS.
- No consumer coordination or retention logic; we only need EB ACK semantics and receipt shape.

### Decisions (with reasoning)
- **Use boto3** (already a dependency in the repo for S3). Minimizes new deps.
- **Expose endpoint/region via env**: reuse LocalStack vars to avoid secrets in code/docs.
- **Receipt offset**: Kinesis SequenceNumber stored as string with `offset_kind=kinesis_sequence`.

### Planned steps
1) Implement `KinesisEventBusPublisher` in `src/fraud_detection/event_bus/kinesis.py`.
2) Extend IG bus builder to recognize `event_bus_kind: kinesis` and build the adapter.
3) Add dev profile wiring (if not already) for event bus kind + endpoint.
4) Add env‑gated integration test (skips when LocalStack not running).

### Constraints
- No changes to EB contracts; only adapter and wiring.
- No credentials stored in docs or code.

## Entry: 2026-01-29 06:20:40 — Phase 5 implementation (Kinesis publish adapter)

### What was implemented
- **KinesisEventBusPublisher** (`src/fraud_detection/event_bus/kinesis.py`) using boto3 `PutRecord`.
- **IG wiring support** for `event_bus_kind: kinesis` and `event_bus.stream` in profile.
- **Dev profile wiring** updated to point to Kinesis (`config/platform/profiles/dev_local.yaml`).
- **Env‑gated smoke test** for Kinesis publish (LocalStack) with skip if endpoint not set.

### Design choices made (and why)
- Publish‑only adapter: keeps v0 scope tight and avoids consumer coordination.
- Use `KINESIS_ENDPOINT_URL`/`AWS_*` envs for LocalStack; no credentials in repo.
- SequenceNumber stored as `offset` with `offset_kind=kinesis_sequence`.

### Tests executed
- `.\.venv\Scripts\python.exe -m pytest tests/services/event_bus/test_kinesis_publisher.py -q`
- Result: **skipped** (no LocalStack endpoint set in env during this run).

### Notes
- Local file‑bus remains default for local profile; dev profile now targets Kinesis by default.

## Entry: 2026-01-29 06:21:48 — Decision: v0 dev EB uses Kinesis, Kafka deferred

### Decision
- **v0 dev parity remains Kinesis** (LocalStack/AWS).
- **Kafka deferred to v1** when full retention/replay semantics and broker ops are planned.

### Why
- LocalStack + boto3 are already in use, making Kinesis publish validation low‑lift.
- Kafka introduces additional operational surface better handled after v0 stabilization.

### Impact
- Phase 5 stays Kinesis publish‑only.
- Kafka noted as a v1+ adapter in the EB build plan.

## Entry: 2026-01-29 06:27:36 — Local EB root alignment for smoke run

### Observation
- Local IG file‑bus default was `runs/local_bus` (implicit), which splits EB artifacts from the platform runtime root.

### Decision
- Align local file‑bus root to `runs/fraud-platform/<platform_run_id>/event_bus` to keep all platform runtime artifacts under the same root and meet earlier platform layout requirements.

### Change
- Update `config/platform/profiles/local.yaml` to set `wiring.event_bus.root: runs/fraud-platform/<platform_run_id>/event_bus`.

## Entry: 2026-01-29 06:28:50 — Smoke runner fix (Windows bash quoting)

### Issue
- `make platform-smoke` failed under Git Bash due to nested quotes in the Python command that generates a run_equivalence_key.

### Fix
- Escaped the inner quotes in the Python one‑liner so bash parses it correctly on Windows.

### Change
- `makefile`: adjusted `platform-smoke` run_equivalence_key generator.

## Entry: 2026-01-29 06:29:29 — Smoke runner fix (use date instead of python)

### Issue
- Quoting in `platform-smoke` kept failing under `/usr/bin/bash` on Windows.

### Fix
- Replaced Python one‑liner with `date +%Y%m%dT%H%M%SZ` to generate the run_equivalence_key in bash.

### Change
- `makefile`: `SR_RUN_EQUIVALENCE_KEY=local_smoke_$$(date +%Y%m%dT%H%M%SZ)`.

## Entry: 2026-01-29 06:33:45 — Smoke run verification (SR → WSP → IG → EB)

### Goal
- Confirm end‑to‑end local chain publishes to the file‑bus with stable offsets and no fresh errors in platform logging.

### Run context
- Platform run id: `platform_20260129T062946Z`.
- Engine root: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`.
- Event bus root: `runs/fraud-platform/<platform_run_id>/event_bus`.

### Evidence gathered
- SR run log: `runs/fraud-platform/platform_20260129T062946Z/platform.log` shows READY committed for run_id `a26b2312a84f851b4a7d7e559fc5c122`.
- EB file‑bus state:
  - `runs/fraud-platform/<platform_run_id>/event_bus/fp.bus.traffic.v1/head.json` → `{"next_offset":20}`.
  - `runs/fraud-platform/<platform_run_id>/event_bus/fp.bus.traffic.v1/partition=0.jsonl` contains the last events published at `2026-01-29T06:30:50Z`–`06:30:52Z`.
- IG admissions recorded in `runs/fraud-platform/platform.log` show offsets 1–19 for the same time window.

### Outcome
- Smoke run is green for the local chain; EB offsets advanced to 20 and no fresh ERROR/SCHEMA_FAIL lines appeared in the tail of `runs/fraud-platform/platform.log` during the 06:29–06:31 window.
- Older SCHEMA_FAIL records remain in the global platform log from earlier experiments (pre‑run); they are not from this smoke run.

---

## Entry: 2026-01-29 19:04:05 — Plan: parity EB via Kinesis in local mode

### Trigger
Platform parity work requires the local event bus to match dev/prod semantics; file‑bus is a ladder‑friction source.

### Decision trail (live)
- Local parity should use **Kinesis (LocalStack)** to mirror dev/prod behavior.
- File‑bus remains for fast smoke in `local.yaml`, but parity profile will switch to Kinesis explicitly.
- EB already has a publish‑only Kinesis adapter; parity work is primarily **profile + infra** wiring.

### Planned changes
- Add `event_bus_kind: kinesis` and `event_bus.stream` in `local_parity.yaml`.
- Align `dev.yaml`/`prod.yaml` to explicitly set `event_bus_kind: kinesis` and stream name.
- Provide LocalStack stream bootstrap in parity compose/make targets.

## Entry: 2026-01-29 19:10:40 — Implement parity EB wiring (Kinesis)

### What changed
- Added `local_parity.yaml` profile with Kinesis event bus wiring.
- Aligned `dev.yaml`/`prod.yaml` to explicitly declare Kinesis event bus + stream.
- Updated `dev_local.yaml` to use a dedicated traffic stream (`fp-traffic-bus`).

### Files updated
- `config/platform/profiles/local_parity.yaml`
- `config/platform/profiles/dev_local.yaml`
- `config/platform/profiles/dev.yaml`
- `config/platform/profiles/prod.yaml`

---

## Entry: 2026-01-30 00:27:05 — Run-first EB folder rename (`event_bus` → `eb`)

### Trigger
Run-first layout requires component folders under `runs/fraud-platform/<platform_run_id>/...` and the EB folder should align with the `eb` component name.

### Decision trail (live)
- The EB on-disk bus is a component artifact and should sit under the run root (`.../<run_id>/eb/...`), not a shared `event_bus/` root.
- To avoid breaking Kinesis wiring semantics, only the local file‑bus path is renamed; stream names are unchanged.
- Earlier entries that mention `event_bus` paths are now superseded by the `eb` folder naming but kept as historical context.

### Implementation notes
- IG wiring now rewrites file‑bus roots to `.../<run_id>/eb` via `resolve_run_scoped_path(..., suffix="eb")`.
- EB CLI default tail root updated to `runs/fraud-platform/<platform_run_id>/eb`.
- Local profile `event_bus.root` updated to `runs/fraud-platform/eb` (auto‑rewritten into the run root).
- IG file‑bus fallback now defaults to `runs/fraud-platform/eb` for local smoke.

### Files touched
- `src/fraud_detection/ingestion_gate/config.py`
- `src/fraud_detection/ingestion_gate/admission.py`
- `src/fraud_detection/event_bus/cli.py`
- `config/platform/profiles/local.yaml`
- `README.md`
- `docs/model_spec/platform/implementation_maps/event_bus.build_plan.md`

---

## Entry: 2026-01-30 00:38:45 — Correction: dev_local profile removed (parity = local_parity)

### Why this correction
EB notes referenced `dev_local.yaml` for parity publish tests. That profile has been removed to avoid mixed substrate semantics.

### Current authoritative posture
- **Parity gate:** `config/platform/profiles/local_parity.yaml` (Kinesis/LocalStack).
- **Smoke only:** `config/platform/profiles/local.yaml` (file bus).

### Impact
Prior references to `dev_local` are historical; use `local_parity` for parity validation.

---

## Entry: 2026-01-31 07:08:10 — EB v0 green (Kinesis parity)

### Problem / goal
Confirm EB v0 is **green** for local_parity: IG publishes to Kinesis (LocalStack) and records are readable with offsets.

### Evidence (local parity)
- LocalStack stream `fp-traffic-bus` contains records after WSP→IG push (Kinesis read returns records).
- IG receipts written under the active run id; EB refs present (sequence offsets).

### v0 green definition (EB)
- Kinesis‑compatible adapter is the parity default.
- Offsets captured in receipts as `offset_kind=kinesis_sequence`.
- Local smoke proves publish + read from EB without schema drift.

---

## Entry: 2026-01-31 07:14:05 — EB diagnostics log (run‑scoped)

### Trigger
User requested explicit EB logs and platform‑log visibility of EB activity.

### Decision
Route EB publish diagnostics to a **run‑scoped log** (`runs/fraud-platform/<run_id>/event_bus/event_bus.log`) and emit a narrative line in `platform.log` from IG.

### Result
EB publish activity is visible in both narrative and diagnostic logs without adding a separate EB service.

---

## Entry: 2026-01-31 20:12:00 — Kinesis publisher topic‑based routing

### Trigger
Dual EB channels require publishing to different Kinesis streams per topic.

### Planned change
- Allow Kinesis publisher to use `topic` as the stream name when a default stream is not configured.
- IG will pass `None`/auto for event_bus_stream in parity so each topic maps to its own stream.

---

## Entry: 2026-01-31 20:20:00 — Dual traffic streams (baseline + fraud)

### Trigger
Platform traffic policy changed to dual behavioural streams with distinct EB channels.

### Decision
- EB uses two traffic streams:
  - `fp.bus.traffic.baseline.v1`
  - `fp.bus.traffic.fraud.v1`
- Kinesis publisher uses **topic‑named streams** when `EVENT_BUS_STREAM=auto`.

### Implementation notes
- LocalStack bootstrap creates both streams.
- IG publishes to stream = partitioning profile `stream`.
