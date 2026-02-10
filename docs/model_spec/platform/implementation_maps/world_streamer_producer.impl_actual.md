
## Entry: 2026-01-28 09:52:10 — Oracle storage + interface boundary pinned in WSP authority

### Trigger
User asked to append guidance on where the engine “oracle” outputs live per environment, and whether WSP replaces the engine interface pack.

### Decision
- Oracle outputs live in immutable object storage per environment (local filesystem/MinIO, dev S3‑compatible, prod S3).
- WSP does **not** replace the engine interface pack; it is downstream and consumes SR’s join surface only.

### Change
- Added a new section “Oracle storage + engine interface boundary (environment ladder)” to the WSP design authority.

---

## Entry: 2026-01-28 13:16:23 — WSP build plan + Oracle Store sequencing (Phase 2 start)

### Trigger
User approved: Oracle Store as a **separate component**, `oracle_root` as a configurable variable (use `runs/local_full_run-5` for now, move to `runs/data-engine` later), and a **speedup factor available in all environments**. User asked to proceed with WSP + Oracle Store build, and requested the platform build plan to reflect this sequencing (done).

### Authorities / inputs (binding)
- Root `AGENTS.md` (progressive elaboration; append‑only decision trail; no secrets).
- Platform blueprint + deployment tooling notes (WSP as primary producer; sealed world boundary).
- Engine interface pack (canonical envelope, locator/receipt schemas).
- SR/IG design authority docs (READY + run_facts_view entrypoint; IG trust boundary).
- WSP design authority (streaming invariants, no future leakage, canonical envelope framing).

### Live decision trail (notes as I think)
- WSP is the **primary runtime producer**; it must be wired to READY + `run_facts_view` and never scan for “latest.”
- Oracle Store is its own **boundary component** (immutability + by‑ref), so WSP does not redefine storage semantics.
- `oracle_root` should be **wiring/config**, not hard‑coded policy; default to the existing materialized data (`runs/local_full_run-5`) but keep it adjustable to `runs/data-engine` and S3 later.
- The **speedup factor** must be an **env‑agnostic policy knob** (local/dev/prod) so the temporal semantics remain identical at different speeds.
- WSP must always **push to IG** (never EB) and keep event IDs compatible with legacy pull framing so downstream doesn’t fork schemas.

### Alternatives considered (and why rejected)
- **Hard‑code `oracle_root` to runs/local_full_run‑5**: rejected; we need to move to `runs/data-engine` and S3 without code changes.
- **Treat Oracle Store as WSP‑internal only**: rejected; boundary must be explicit and reusable by SR/IG/backfill tooling.
- **Speedup factor only for local**: rejected; user wants it available everywhere (policy knob, not code branch).

### Planned steps (before coding)
1) Create **Oracle Store** component docs:
   - `docs/model_spec/platform/component-specific/oracle_store.design-authority.md`
   - `docs/model_spec/platform/implementation_maps/oracle_store.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/oracle_store.impl_actual.md`
2) Create **WSP build plan**:
   - `docs/model_spec/platform/implementation_maps/world_streamer_producer.build_plan.md`
3) Define initial wiring/policy keys (no secrets) for:
   - `oracle_root` (default: `runs/local_full_run-5`)
   - `stream_speedup` (policy knob across envs)
4) Begin WSP skeleton implementation only after the above plans are recorded.

---

## Entry: 2026-01-28 13:31:37 — Phase 1 implementation start (profiles + WSP skeleton + smoke path)

### Trigger
User said “Proceed with all 3”: (1) add Oracle/WSP fields to platform profiles + README, (2) scaffold WSP package, (3) add a minimal local smoke path (READY → WSP → IG push).

### Live decision trail (notes as I go)
- **Profiles as the primary surface:** we already use platform profiles for IG; adding WSP/Oracle keys there keeps one canonical profile without introducing new ad‑hoc config files.

---

## Entry: 2026-01-28 13:38:12 — Applied: profiles + WSP scaffold + smoke runner

### What I changed
- **Profiles:** added `policy.stream_speedup` and wiring keys `oracle_root` + `ig_ingest_url` to all platform profiles.
  - Local/dev_local default to `runs/local_full_run-5` + `http://localhost:8081`.
  - Dev/prod use env placeholders (`${ORACLE_ROOT}`, `${IG_INGEST_URL}`).
- **Profiles README:** documented `stream_speedup`, `oracle_root`, and `ig_ingest_url` semantics (no secrets).
- **WSP scaffold:** added `world_streamer_producer` package with:
  - config loader (env interpolation + defaults)
  - file‑bus READY reader
  - runner that loads `run_facts_view`, resolves oracle paths, enforces gate‑pass when required, and pushes envelopes to IG
  - CLI for one‑shot READY processing
- **Makefile:** added `platform-wsp-ready-once` target with `WSP_PROFILE` + `WSP_MAX_EVENTS` guards.
- **.env.example:** added non‑secret placeholders for `ORACLE_ROOT` and `IG_INGEST_URL`.

### Rationale (live)
- Keeping `oracle_root` and `ig_ingest_url` in profiles keeps wiring consistent across components and avoids ad‑hoc WSP config.
- Reusing IG’s engine‑pull framing logic via `EnginePuller` prevents schema drift and keeps event_id stable.
- Smoke‑mode `--max-events` bounds local runs without altering policy semantics.

### Open follow‑ups
- Decide whether WSP should persist a checkpoint (Phase 2) or remain stateless for now.
- Add a small validation test (local smoke) to assert at least one envelope is admitted by IG.

---

## Entry: 2026-01-28 15:46:33 — **IMPORTANT** WSP reads an external Oracle Store (not a platform vertex)

### Clarified boundary (non‑negotiable)
The WSP treats the Oracle Store as **external truth**. It is **not** a platform vertex and is **not** expected to live inside the platform runtime graph. WSP must **never** rely on `runs/fraud-platform` (platform outputs) for its oracle data source.

### Consequences for implementation
- `oracle_root` is a pointer to **engine‑materialized truth** (local path or object store), not a platform output folder.
- `runs/fraud-platform` remains a **platform runtime** location (logs/ledgers/session metadata only).
- If `runs/fraud-platform` is deleted, WSP **must still function** as long as the Oracle Store (engine world) is present.

### v0 local alignment
- For local dev we may set `oracle_root` to `runs/local_full_run-5` as a practical engine‑world location, but this does **not** make it part of the platform runtime; it is still outside the platform boundary.

---

## Entry: 2026-01-28 16:36:19 — Planning WSP rewire for engine‑rooted Oracle Store (pre‑implementation)

### Trigger (why we’re planning now)
User confirmed Oracle Store is **engine‑rooted** and must **not** be coupled to SR runtime artifacts. WSP must be wired to read the **engine world** directly via Oracle Store, so we need a concrete plan before touching code.

### Problem I’m solving (plain language)
WSP currently expects SR’s `run_facts_view` as the authoritative map of what to stream. That makes WSP transitively dependent on platform runtime state (`runs/fraud-platform`). We must invert this: WSP should stream from **engine‑materialized truth** and only use SR if/when it acts as an external scheduler/attester—not as an oracle index.

### Options I considered (and why I’m choosing one)
1) **Keep SR READY as the trigger** and reuse `run_facts_view` for output selection.
   - **Rejected** because it violates the new boundary and keeps Oracle Store coupled to SR artifacts.
2) **Make WSP fully oracle‑rooted** with explicit world identity (engine run root + scenario id).
   - **Chosen** because it enforces the correct dependency chain: engine → oracle store → WSP → IG.
3) **Introduce a new “world registry” service** that emits READY events for WSP.
   - **Deferred** for later; adds a new component before we have the oracle‑rooted WSP path working.

### Decision (what we will build)
WSP will be **oracle‑rooted** and **engine‑world aware**:
- It reads the **oracle pack manifest** (or `run_receipt.json` if manifest missing) to obtain **world identity**.
- It uses the engine **output catalogue** + **stream class policy** to decide **which outputs** become traffic.
- It verifies **gate receipts** directly against the engine world (no SR join surface).
- It emits canonical envelopes to IG using the selected outputs and world key.

### Key invariants (must hold)
- WSP must not depend on `runs/fraud-platform` or SR `run_facts_view`.
- `oracle_root` is a pointer to **engine truth** (local or S3).
- No discovery‑by‑scanning: WSP must be pointed at a specific world (engine run root or oracle pack id).
- Gate checks remain **fail‑closed** (no PASS → no read).

### Inputs + authorities
- **Engine outputs catalogue**: `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`
- **Engine gate map**: `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
- **Oracle pack manifest + seal** at engine run root.
- **Policy stream class mapping** (IG policy note) to tag outputs as `business_traffic` vs `control` vs `audit`.

### Planned wiring (concrete)
1) **WSP config additions**
   - `oracle.engine_run_root` (explicit world root).
   - `oracle.scenario_id` (required if ambiguous).
   - `stream.output_ids` optional override for local smoke.
2) **Oracle pack resolution**
   - Read `_oracle_pack_manifest.json` if present.
   - Fallback to `run_receipt.json` + scenario_id.
3) **Output selection**
   - Default: select outputs where policy tags them `business_traffic`.
   - Optional: `stream.output_ids` for local test runs.
4) **Gate verification**
   - Use `engine_gates.map.yaml` to resolve `passed_flag_path_template`.
   - Require gate pass for any output requiring gates in the catalogue.
5) **Envelope emit**
   - Use existing canonical envelope framing in WSP/IG.
   - Ensure `event_id` stability from locator + world key.

### Test plan (local/dev)
- **Unit**: parse manifest + receipt, output selection, gate pass lookup.
- **Integration**: point at `runs/local_full_run-5/<run_id>` and confirm a bounded number of envelopes are admitted by IG.

### What I’m not doing yet
- I am **not** replacing SR or adding a new scheduler component; this is purely WSP oracle‑rooted wiring.
- I am **not** introducing a streaming cursor/offset store until the oracle‑rooted path is verified.

---

## Entry: 2026-01-28 16:42:30 — Phase 1 implementation start (engine‑rooted WSP wiring)

### Immediate intent (before touching code)
I am implementing Phase 1 as **engine‑rooted WSP** with no SR `run_facts_view` dependency. The runner will read an **explicit engine run root**, resolve world identity from `run_receipt.json` and/or `_oracle_pack_manifest.json`, select `business_traffic` outputs from a **WSP policy list**, verify gate receipts from engine gate map, and then stream envelopes to IG using the existing canonical envelope framing.

### Decisions I’m locking now (and why)
- **Explicit engine root required**: I will require `engine_run_root` (CLI or config) and will **not** scan for “latest.” This enforces the no‑discovery rule.
- **Policy list for output selection**: since there is no machine‑readable role mapping in the interface pack, I will introduce a **WSP traffic outputs list** (policy file) and treat it as the source of truth for `business_traffic` selection.
- **Gate verification uses passed flags**: I will reuse `engine_gates.map.yaml` passed‑flag templates to check gate PASS by file existence (local or S3).
- **Seal check is environment‑sensitive**: local can allow missing seals; dev/prod will fail if `_SEALED.*` is missing (same posture as Oracle Store).

### Safety checks I will add
- Fail if `run_receipt.json` missing or invalid.
- Fail if scenario_id cannot be resolved unambiguously.
- Fail if required gates are missing when `require_gate_pass` is true.
- Fail if no traffic outputs are selected (to avoid silent no‑ops).

---

## Entry: 2026-01-28 17:07:04 — Phase 1 implemented (engine‑rooted streaming + gate checks)

### What I implemented (with reasoning as I went)
1) **WSP policy allowlist (traffic outputs)**
   - Added `config/platform/wsp/traffic_outputs_v0.yaml` with the v0 traffic output_ids.
   - Updated all platform profiles to reference it via `policy.traffic_output_ids_ref`.
   - Loader resolves the ref **relative to the profile path** to avoid CWD ambiguity.
   - Reason: there is no machine‑readable “business_traffic” map in the interface pack; a policy file is the cleanest explicit authority and avoids accidental streaming of non‑traffic outputs.

2) **WSP config wiring for explicit world selection**
   - Added optional `oracle_engine_run_root` + `oracle_scenario_id` wiring fields to profiles (env‑driven).
   - Reason: WSP must be pinned to a **specific** engine world; no “latest” scanning allowed.

3) **Engine‑rooted runner (no SR dependency)**
   - Rebuilt `world_streamer_producer/runner.py` to:
     - resolve engine run root (explicit input or profile default),
     - read `run_receipt.json`,
     - resolve/validate `scenario_id`,
     - validate `_oracle_pack_manifest.json` (if present) and `_SEALED.*` (strict in dev/prod),
     - select traffic outputs from policy allowlist,
     - verify gate PASS using `engine_gates.map.yaml` `passed_flag_path_template`,
     - build locators directly from catalogue `path_template` + world tokens,
     - stream via existing `EnginePuller` (canonical envelope framing).
   - Reason: reuse the canonical envelope framing logic and keep the WSP boundary minimal; no new event schema drift.

4) **CLI + Makefile rewiring**
   - Updated WSP CLI to accept `--engine-run-root`, `--scenario-id`, and optional `--output-ids`.
   - Updated Makefile `platform-wsp-ready-once` to require engine‑rooted inputs (renamed semantics).
   - Reason: make the engine‑rooted flow the default and remove SR‑based usage.

5) **Edge‑case hardening**
   - Failure on missing run receipt, ambiguous scenario_id, missing gates, missing traffic outputs.
   - Trimmed path templates before formatting to handle newline‑wrapped YAML templates.
   - Reason: prevent silent “no‑ops” and common catalogue formatting pitfalls.

### Tests run (local)
- Added unit tests for engine‑rooted WSP streaming and gate‑missing failure.
- `pytest tests/services/world_streamer_producer/test_runner.py -q` → 2 passed.

---

## Entry: 2026-01-28 18:38:35 — Phase 2 planning (checkpointing + resume, no role conflation)

### Trigger
User asked to move into **Phase 2 planning** and explicitly warned not to conflate validation (Phase 4) with checkpointing (Phase 2).

### What Phase 2 is *and is not*
- **Phase 2 = checkpointing + resume** to make WSP operationally safe under restarts and at‑least‑once delivery.
- **Phase 4 = validation** (smoke + dev completion). Phase 2 does **not** replace or duplicate Phase 4.
- Phase 2 will **not** add new validation logic beyond what Phase 1 already enforces (gates/manifest/inputs).

### Problems Phase 2 must solve (explicit)
1) **Resume semantics** after crash/restart without re‑emitting already pushed events.
2) **Deterministic progress cursor** per engine world + output_id (and optionally per partition).
3) **At‑least‑once reality**: WSP may re‑emit during failure → IG must remain idempotent, but WSP should still minimize duplicates.
4) **Local/dev parity**: local can persist to file; dev/prod use external store.

### Options considered (with reasoning)
**A) File‑based checkpoint (local only)**  
- Pros: trivial to implement for local smoke.  
- Cons: unusable for multi‑instance dev/prod; not enough alone.

**B) Object‑store checkpoint (S3/MinIO)**  
- Pros: environment‑consistent, cheap.  
- Cons: concurrency control is weak; needs conditional writes/ETags.

**C) Postgres checkpoint (recommended for dev/prod)**  
- Pros: strong concurrency; easy lease + resume semantics.  
- Cons: more infra, but already used for IG READY leases.

**Decision (provisional):**  
- Local: file‑based checkpoint under `runs/fraud-platform/<platform_run_id>/wsp_checkpoints/`.  
- Dev/Prod: Postgres table keyed by `{oracle_pack_id, output_id}` (or `{engine_run_root, output_id}` if no manifest).

### Proposed checkpoint model (concrete)
- **Checkpoint key:** `{oracle_pack_id, output_id}`  
- **Cursor payload:** `{last_file, last_row_index, last_ts_utc}`  
- **Write discipline:** append‑only JSONL log + current cursor (write‑once per update; atomic rename for local).
- **Resume policy:**  
  - if cursor exists → skip rows prior to cursor, continue from next row.  
  - if cursor missing → start at beginning.

### Pending decisions to lock before implementation
1) **Primary identity:** `oracle_pack_id` vs `engine_run_root` (if manifest missing).  
2) **Cursor granularity:** per output_id only vs output_id + file + row index.  
3) **Storage backend:** Postgres (dev/prod) vs object store (if we want infra symmetry).  
4) **Concurrency rule:** single WSP per pack vs multi‑worker partitions (not in Phase 2).

### Planned steps (Phase 2 implementation outline)
1) Add checkpoint interface + local file backend.  
2) Add Postgres backend + migrations (if chosen).  
3) Wire checkpoint load/save into streaming loop (after emit, before advance).  
4) Add tests: resume from cursor, duplicate suppression, crash‑resume behavior.  
5) Update operator docs + make targets.

---

## Entry: 2026-01-28 18:49:04 — Phase 2 implemented (checkpointing + resume)

### Step‑by‑step decisions and changes
1) **Checkpoint backends (local + dev/prod)**
   - Implemented `world_streamer_producer/checkpoints.py` with:
     - `FileCheckpointStore` (local): JSON cursor + JSONL append log (atomic rename).
     - `PostgresCheckpointStore` (dev/prod): `wsp_checkpoint` table with upsert.
   - Reason: local smoke needs a file backend; dev/prod needs concurrency‑safe persistence.

2) **Checkpoint identity + fallback**
   - Primary key is `{oracle_pack_id, output_id}` from `_oracle_pack_manifest.json`.
   - If manifest missing, fallback key is a **hash of engine_run_root** (stable, opaque).
   - Reason: keep resume stable even when manifest is absent in local.

3) **Resume logic (no new validation)**
   - WSP loads a cursor per output and skips rows **≤ last_row_index** within the last_file.
   - Cursor advances **after successful emit** to IG.
   - Reason: minimize duplicates without adding validation or scanning responsibilities.

4) **Cursor granularity**
   - Cursor = `{last_file, last_row_index, last_ts_utc}`.
   - Reason: allows precise resume within a Parquet part without re‑emitting earlier rows.

5) **EnginePuller extension (metadata only)**
   - Added `iter_events_for_paths_with_positions` to expose `(envelope, file_path, row_index)` while reusing canonical envelope framing.
   - Reason: avoid duplicating event framing logic in WSP and keep consistency with IG.

6) **Profile wiring**
   - Added `wsp_checkpoint` wiring in profiles (local/dev_local=file; dev/prod=postgres) with `flush_every`.
   - Reason: operational tuning without changing policy semantics.

7) **Tests**
   - Added WSP checkpoint resume test to ensure re‑runs do not re‑emit prior rows.

### Tests run (local)
- `pytest tests/services/world_streamer_producer/test_runner.py -q` → 3 passed.

---

## Entry: 2026-01-28 18:57:40 — Mark Phase 1 + Phase 2 complete

### Confirmation
- Phase 1 (engine‑rooted streaming + gate checks) is **complete** and tested.
- Phase 2 (checkpointing + resume) is **complete** and tested.

### Evidence
- WSP unit + resume tests green (`tests/services/world_streamer_producer/test_runner.py`).
- Local resume smoke run verified (second run emits remaining events only).


## Entry: 2026-01-28 19:05:41 — Phase 3 planning (producer identity + provenance + audit)

### Trigger
User requested Phase 3 implementation (security/governance hardening) with detailed decision trail and tests.

### Problem framing (what Phase 3 must add)
Phase 1/2 already stream engine events with checkpointing. Phase 3 must harden **governance** without changing roles:
- **Producer identity control** (who is allowed to emit to IG).
- **Provenance stamping** of the oracle world (pack identity + engine release).
- **Audit hooks** for stream start/stop and cursor commits.

Phase 3 must **not** add new validation that belongs in Phase 4 (smoke + dev completion). It must also respect the canonical envelope schema (no additional properties) and keep WSP as the traffic producer only (no EB writes).

### Constraints and authorities
- Canonical envelope schema is strict (`additionalProperties: false`) in `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`.
- Oracle pack manifest schema provides `oracle_pack_id` + `engine_release`.
- Governance rules: fail closed when compatibility/identity is unknown.

### Options considered (and why)
1) **Add new custom fields (e.g., oracle_pack_id) to the envelope.**
   - Rejected: schema is strict; adding fields would break validation and violate boundary contract.

2) **Reuse existing tracing fields for provenance (trace_id/span_id).**
   - Accepted: conforms to schema and keeps provenance attached to each event without schema changes.

3) **Producer allowlist enforced in IG instead of WSP.**
   - Partial: IG should also be able to enforce, but WSP must fail‑closed if its producer identity is invalid or not in the allowlist to prevent accidental emission.

### Decisions (locked)
1) **Producer identity stamping**
   - WSP sets `producer` on every envelope to the configured `producer_id`.
   - WSP **fails closed** if `producer_id` is missing or not on the allowlist.
   - Allowlist is an explicit file ref in wiring; provide a default file with the WSP service id.

2) **Provenance stamping within allowed fields**
   - `trace_id` = `oracle_pack_id` (preferred), fallback to `pack_key` when manifest is absent.
   - `span_id` = `engine_release` (if present) to tie events back to the engine build.
   - If those fields are already set, WSP will not clobber them (defensive).

3) **Audit hooks (append‑only)**
   - Use `append_session_event` for:
     - `stream_start` (engine root, scenario, output_ids, pack key)
     - `stream_complete` (emitted count)
     - `checkpoint_saved` (pack key, output_id, cursor)
   - Log only on checkpoint flush (not every event) to avoid excessive audit noise.

### Implementation plan (before coding)
1) Add a producer allowlist file under `config/platform/wsp/producer_allowlist_v0.txt`.
2) Extend platform profiles + README to include `wsp_producer` block (producer_id + allowlist_ref).
3) Update WSP runner to:
   - load/validate allowlist;
   - stamp producer + provenance in envelopes;
   - emit audit events for stream start/stop and cursor saves.
4) Update tests to cover:
   - producer allowlist failure;
   - provenance stamping (trace_id/span_id presence);
   - no break to existing resume tests.
5) Run WSP test subset.

### Risks + mitigations
- **Risk:** provenance can’t be added without schema change. → Mitigation: use trace/span fields.
- **Risk:** allowlist missing in profile. → Mitigation: add default allowlist file + fail‑closed with clear reason code.
- **Risk:** audit spam. → Mitigation: only log on checkpoint flush.

### Test plan (local)
- `pytest tests/services/world_streamer_producer/test_runner.py -q`

---

## Entry: 2026-01-28 19:14:10 — Phase 3 implemented (producer allowlist + provenance + audit)

### Step‑by‑step decisions and changes
1) **Producer identity allowlist (fail‑closed)**
   - Added `wsp_producer` wiring block in all platform profiles with a stable `producer_id` and explicit allowlist ref.
   - Created a versioned allowlist file at `config/platform/wsp/producer_allowlist_v0.txt` containing the WSP service id.
   - WSP now validates producer identity **before any streaming**:
     - Missing producer id → `PRODUCER_ID_MISSING`.
     - Missing/empty/unreadable allowlist → `PRODUCER_ALLOWLIST_*` reason codes.
     - Producer not in allowlist → `PRODUCER_NOT_ALLOWED`.
   - Reason: governance requires explicit identity control; fail‑closed when identity is unknown.

2) **Provenance stamping without schema violations**
   - Canonical envelope is strict (`additionalProperties: false`), so we cannot add custom fields.
   - Decision: use existing tracing fields for provenance:
     - `trace_id` = `oracle_pack_id` (preferred) or fallback pack key when manifest is absent.
     - `span_id` = `engine_release` when available in the pack manifest.
   - WSP stamps these **only if not already set** to avoid clobbering upstream instrumentation.
   - Reason: keeps provenance attached to each event while staying schema‑safe.

3) **Audit hooks (append‑only)**
   - Added `append_session_event` hooks for:
     - `stream_start` (engine root, scenario, outputs, pack key, producer id)
     - `stream_complete` (emitted count)
     - `checkpoint_saved` (pack key/output/cursor + reason)
   - Checkpoint audit happens on flush boundaries (controlled by `flush_every`) to avoid noisy logs.
   - Reason: ensure observable lifecycle without turning the audit log into per‑event spam.

4) **Path resolution hardening (allowlist + output ids)**
   - Updated WSP config loader to resolve refs in this order:
     - If the path exists as‑is (relative to current working dir), use it.
     - Otherwise, resolve relative to the profile directory.
   - Reason: profiles currently use repo‑root style paths; this prevents accidental double‑prefixing.

5) **Tests**
   - Added a producer allowlist failure test to confirm fail‑closed behavior.
   - Extended stream test to assert producer + provenance stamping (`producer`, `trace_id`).

### Tests run (local)
- `.\.venv\Scripts\python.exe -m pytest tests/services/world_streamer_producer/test_runner.py -q` → 4 passed.

---

## Entry: 2026-01-28 19:19:37 — Phase 4 planning (WSP validation: local smoke + dev completion)

### Trigger
User requested Phase 4 planning after confirming Phase 3 completion.

### Phase 4 intent (validation only)
Phase 4 is **not new capability**; it validates that Phases 1–3 work end‑to‑end under two operational modes:
- **Local smoke** (bounded, fast feedback).
- **Dev completion** (uncapped, true completion semantics).

### Constraints and boundaries
- WSP remains engine/oracle‑rooted (explicit run root), no scanning.
- WSP pushes only to IG, never to EB.
- Validation must not mutate engine outputs; it may write **platform runtime** artifacts under `runs/fraud-platform/` only.
- Gate PASS enforcement and producer allowlist must be exercised (fail‑closed on missing/invalid identity).

### Decisions to lock (planning)
1) **Local smoke** will validate:
   - Oracle pack is sealed (strict_seal false in local, but report if missing).
   - Gate PASS presence for traffic outputs.
   - Envelope stamping (producer + trace_id/span_id) is visible in IG ingest.
   - WSP resume works (max_events + checkpoint resume) and does not re‑emit already streamed events.

2) **Dev completion** will validate:
   - Strict seal enabled (pack must be sealed).
   - All traffic outputs in policy are streamed to IG without missing gates.
   - Checkpoint persistence backend works (Postgres in dev/prod profiles).

3) **Run identity and log expectations**
   - Platform run log is written via `platform_runtime` paths.
   - Validation steps should surface run ids for traceability (platform run + engine run root).

### Planned validation steps (Phase 4 outline)
**4.1 Local smoke (fast loop)**
- Preflight: ensure engine run root + scenario_id resolve.
- Run WSP with `max_events` bound to 10 (or config) and verify:
  - events accepted by IG;
  - audit hooks emit `stream_start/stream_complete/checkpoint_saved`.
- Re‑run with `max_events=1` to validate resume from checkpoint.

**4.2 Dev completion (uncapped)**
- Ensure strict seal (dev profile) and Postgres checkpoint DSN set.
- Run WSP without `max_events` to stream all policy outputs.
- Confirm WSP completes with `STREAMED` status and IG produces `PULL_COMPLETED` (or equivalent) for the run.

**4.3 Failure‑path spot checks**
- Producer allowlist failure (invalid producer id) should fail before streaming.
- Gate missing should fail closed and report `GATE_PASS_MISSING`.

### Artifacts + outputs
- Use existing Make targets (or add a `wsp-validate-*` target if missing) to ensure reproducible runs.
- Validation should record output pointers in platform logs (not new artifacts).

### Test plan (to execute during Phase 4)
- WSP subset tests already exist; Phase 4 adds **integration‑style** validation using local run data + IG endpoint.

---

## Entry: 2026-01-28 19:29:10 — Phase 4 implemented (validation harness + make targets)

### Step‑by‑step decisions and changes
1) **Add a dedicated validation CLI (not reuse WSP CLI)**
   - Implemented `fraud_detection.world_streamer_producer.validate_cli` to run Phase 4 checks as a sequence.
   - Reason: Phase 4 needs a multi‑step validation flow (smoke + resume + negative checks), which doesn’t fit a single WSP emit command.

2) **Local smoke validation design (bounded, deterministic)**
   - First pass runs WSP with `max_events` (default 10) to ensure end‑to‑end IG ingestion works.
   - Resume check runs WSP again with `resume_events` (default 1) and verifies the checkpoint cursor advanced.
   - Cursor advance is verified by reading the file checkpoint store; no engine mutation required.
   - Reason: provides a strict, observable signal that resume is working without needing IG internals.

3) **Checkpoint cursor resolution strategy**
   - Pack key is derived from the file checkpoint root by locating the newest cursor for the chosen output_id.
   - Reason: avoids re‑implementing pack identity resolution logic (manifest + fallback) in validation.

4) **Failure‑path validation (producer allowlist)**
   - Implemented a negative check by running WSP with a **different producer_id** (`svc:invalid`) while keeping the same allowlist.
   - This fails before streaming and confirms `PRODUCER_NOT_ALLOWED` without changing profile files.
   - Reason: fail‑closed governance can be verified without editing allowlist contents or engine data.

5) **Dev completion validation (uncapped)**
   - Added dev mode to run WSP with `max_events=None` (full completion) and warn if checkpoint backend is not Postgres.
   - Reason: this maps to the dev environment expectation without adding new validation logic.

6) **Makefile targets for reproducibility**
   - Added `platform-wsp-validate-local` and `platform-wsp-validate-dev` targets to standardize runs.
   - Added tuning variables (`WSP_VALIDATE_MAX_EVENTS`, `WSP_RESUME_EVENTS`, `WSP_VALIDATE_CHECK_FAILURES`, `WSP_VALIDATE_SKIP_RESUME`).
   - Reason: avoid ad‑hoc CLI usage and keep validation steps consistent across operators.

### Files changed
- `src/fraud_detection/world_streamer_producer/validate_cli.py` (new)
- `makefile` (new targets + variables)

### Tests run (local)
- `.\.venv\Scripts\python.exe -m pytest tests/services/world_streamer_producer/test_runner.py -q` → 4 passed.

---

## Entry: 2026-01-29 01:08:16 — WSP READY consumer runner (design + plan)

### Trigger
User requested a READY consumer runner so SR can drive WSP automatically for a full SR→WSP→IG run.

### Core design intent (re‑stated)
- SR remains the **selector** of which run should stream by emitting READY.
- WSP remains the **producer** that streams the Oracle world to IG.
- IG remains **push‑only** and does not read SR artifacts.

### Decision trail (live reasoning)
1) **Consumer should read READY messages from control bus (file bus for local).**
   - WSP already has `control_bus.py` with a file‑bus reader and schema validation for READY messages.
   - We will build the runner on top of that reader for local parity; any non‑file bus will fail closed for now.
   - This avoids inventing a second READY format and keeps SR → WSP contract consistent.

2) **WSP must resolve scenario_id + engine_run_root from SR‑authored facts.**
   - READY payload does not always include scenario_id; run_facts_view always includes pins.
   - Decision: load `run_facts_view` and take `pins.scenario_id` as the authoritative scenario_id.
   - Engine root should come from `oracle_pack_ref.engine_run_root` (or READY payload’s oracle_pack_ref), not from IG or SR internals.

3) **Idempotency should be append‑only, not overwrite.**
   - To avoid “silent resets”, we will write an append‑only JSONL record per READY message.
   - If a prior record shows `STREAMED`, the consumer will skip reprocessing (safe under duplicates).
   - If prior attempts failed, we will allow retries (append new record) rather than overwriting.

4) **Keep IG responsibilities clean.**
   - The runner will only call `WorldStreamProducer.stream_engine_world(...)` and IG remains a push recipient.
   - No SR gating or engine validation is introduced inside IG.

### Planned implementation steps (before coding)
1) Add `src/fraud_detection/world_streamer_producer/ready_consumer.py` with:
   - `ReadyConsumerRunner` (poll once / loop).
   - Append‑only READY processing records under `fraud-platform/<platform_run_id>/wsp/ready_runs/<message_id>.jsonl`.
   - Schema validation for run_facts_view.
   - Fail‑closed errors for missing oracle pack ref, missing scenario_id, or missing engine root.

2) Add a simple object‑store builder for WSP to read run_facts_view + write READY run records:
   - Use SR ObjectStore (`scenario_runner.storage`) to keep local + S3 parity.

3) Add a CLI entrypoint to run the READY consumer:
   - `--profile`, `--once`, `--poll-seconds`, `--max-messages`, `--max-events`.

4) Add a Make target for the new runner (`platform-wsp-ready-consumer` + optional `-once`).

5) Tests:
   - Unit test that a READY message invokes WSP with engine_run_root from `oracle_pack_ref` and scenario_id from run_facts_view.
   - Test that duplicate READY with a previous STREAMED record is skipped.

### Non‑goals (explicit)
- No Kinesis READY consumer in this phase (file bus only; fail closed otherwise).
- No changes to IG or SR in this phase.
- No new engine behavior; Oracle Store remains a black‑box source.

## Entry: 2026-01-29 01:11:37 — WSP READY consumer runner implemented (SR‑driven streaming)

### Implementation steps + decisions (as executed)
1) **Built a READY consumer runner (file‑bus only, fail‑closed otherwise)**
   - Added `src/fraud_detection/world_streamer_producer/ready_consumer.py`.
   - The runner uses the existing `FileControlBusReader` and validates READY payloads against `run_ready_signal.schema.yaml`.
   - Non‑file control bus kinds now hard‑fail with `CONTROL_BUS_KIND_UNSUPPORTED` to avoid silent mis‑wiring.

2) **Resolved scenario_id + engine_run_root from SR facts (authoritative)**
   - On each READY, the runner reads `run_facts_view` and validates it against `run_facts_view.schema.yaml`.
   - `scenario_id` comes from `pins.scenario_id` (SR‑authored).
   - `engine_run_root` is taken from `oracle_pack_ref.engine_run_root` (from READY payload or run_facts_view).
   - `oracle_root` is respected if present in `oracle_pack_ref` and used to resolve the engine root.
   - Reasoning: SR is the run selector; WSP should not invent scenario selection or scan for “latest”.

3) **Append‑only READY processing records for idempotency**
   - Each READY message writes an append‑only JSONL record at:
     `fraud-platform/<platform_run_id>/wsp/ready_runs/<message_id>.jsonl`.
   - If any previous record has status `STREAMED`, the message is skipped (`SKIPPED_DUPLICATE`).
   - Failed attempts do **not** block retries (new record appended).
   - Reasoning: matches “append‑only truths” and safe under at‑least‑once delivery.

4) **Store access unified via platform object store**
   - Implemented a small object‑store builder using SR’s store abstractions (local + S3).
   - Used for both reading SR facts and writing READY run records.
   - Reasoning: avoids custom filesystem code; keeps local/dev/prod parity.

5) **CLI entrypoint + Make targets for operator use**
   - `python -m fraud_detection.world_streamer_producer.ready_consumer` supports:
     `--once`, `--poll-seconds`, `--max-messages`, `--max-events`.
   - Added `make platform-wsp-ready-consumer` and `make platform-wsp-ready-consumer-once` for repeatable ops.

6) **Unit tests for READY runner behavior**
   - Added `tests/services/world_streamer_producer/test_ready_consumer.py`:
     - Ensures READY triggers WSP with engine_run_root from oracle_pack_ref and scenario_id from run_facts.
     - Ensures a prior STREAMED record results in `SKIPPED_DUPLICATE` and no re‑stream.

### Files changed
- `src/fraud_detection/world_streamer_producer/ready_consumer.py` (new)
- `tests/services/world_streamer_producer/test_ready_consumer.py` (new)
- `makefile` (new READY consumer targets + variables)

### Tests to run (after this change)
- `pytest tests/services/world_streamer_producer/test_ready_consumer.py -q`
- `pytest tests/services/world_streamer_producer/test_runner.py -q`

### Notes
- This runner wires SR → WSP; IG remains push‑only and unchanged.
- Kinesis control bus is still unimplemented for WSP and will explicitly fail closed if configured.

## Entry: 2026-01-29 01:12:51 — READY consumer test fix + validation

### Issue found
- Initial READY consumer tests failed because the temporary object store root (`store_root`) was not created before writing the allowlist file.

### Fix applied
- Ensured `store_root.mkdir(parents=True, exist_ok=True)` in `_profile(...)` within `tests/services/world_streamer_producer/test_ready_consumer.py`.
- Rationale: local object store paths are filesystem paths; tests must create the root before writing allowlist/config artifacts.

### Tests re‑run
- `pytest tests/services/world_streamer_producer/test_ready_consumer.py tests/services/world_streamer_producer/test_runner.py -q`
  - Result: **6 passed**.

## Entry: 2026-01-29 01:43:15 — Local speedup for WSP smoke runs

### Context
The READY‑driven WSP run was taking too long for a local smoke test. The profile `stream_speedup` governs the wall‑clock delay between `ts_utc` events during streaming.

### Decision
- Increase **local** `stream_speedup` from 60 → 600 to compress time gaps in local smoke runs.
- Keep this scoped to `config/platform/profiles/local.yaml` so dev/prod remain unaffected.

### Why this is safe for v0
- The speedup factor only affects local pacing; it does not alter event ordering or payload content.
- WSP still preserves monotonic `ts_utc` ordering and checkpoint consistency.

### Change
- `config/platform/profiles/local.yaml`: `policy.stream_speedup: 600.0`

---

## Entry: 2026-01-29 19:03:20 — Plan: Kinesis control‑bus reader for parity mode

### Trigger
Maximum‑parity local stack requires READY control‑bus to match dev/prod (Kinesis) rather than file‑bus.

### Decision trail (live)
- SR already supports Kinesis control‑bus publishing; WSP must read the same stream for parity.
- We want **no ladder friction**: local parity should use the same Kinesis path as dev/prod.
- File control bus remains for smoke‑only local profile; parity profile will switch to Kinesis.

### Planned mechanics
- Add a `KinesisControlBusReader` that reads READY envelopes from a Kinesis stream.
- Keep schema validation (same `run_ready_signal.schema.yaml`) and use existing dedupe logic.
- Wiring: `control_bus.kind: kinesis`, `control_bus.stream`, `control_bus.region`, `control_bus.endpoint_url` (LocalStack in local parity).

### Files (to change)
- `src/fraud_detection/world_streamer_producer/control_bus.py` (new reader)
- `src/fraud_detection/world_streamer_producer/ready_consumer.py` (reader selection)
- `src/fraud_detection/world_streamer_producer/config.py` (stream/region/endpoint wiring)
- `config/platform/profiles/local_parity.yaml` + `config/platform/profiles/dev.yaml`/`prod.yaml` (control bus wiring)

## Entry: 2026-01-29 19:10:05 — Implement Kinesis control‑bus reader (parity mode)

### What changed
- Added a Kinesis reader for READY envelopes and wired WSP to select it when `control_bus.kind: kinesis`.
- Extended WSP profile wiring to include `control_bus.stream/region/endpoint_url`.

### Mechanics implemented
- Kinesis reader scans shards from `TRIM_HORIZON` and decodes JSON envelopes.
- Schema validation remains enforced (`run_ready_signal.schema.yaml`).
- READY dedupe remains unchanged (store‑backed).

### Files updated
- `src/fraud_detection/world_streamer_producer/control_bus.py`
- `src/fraud_detection/world_streamer_producer/ready_consumer.py`
- `src/fraud_detection/world_streamer_producer/config.py`

---

## Entry: 2026-01-30 00:26:10 — Run-first WSP artifacts (checkpoints + READY records)

### Trigger
User required a run-first layout (`runs/fraud-platform/<platform_run_id>/...`) with component folders and per-run logs.

### Decision trail (live)
- WSP state should not live at a global repo root (`runs/fraud-platform/wsp_checkpoints`) because it flattens runs and breaks auditability.
- READY dedupe records must be scoped to the platform run, not a shared global namespace.
- Keep the storage abstraction intact (file vs S3) by relying on `platform_run_prefix` + `resolve_run_scoped_path` for run scoping.

### Implementation notes
- Default checkpoint root updated to `runs/fraud-platform/wsp/checkpoints`; `resolve_run_scoped_path(..., suffix="wsp/checkpoints")` rewrites it into the active run.
- READY records now live under `fraud-platform/<platform_run_id>/wsp/ready_runs/...` via `platform_run_prefix`.
- WSP tests now set `PLATFORM_RUN_ID` and assert run-prefixed SR facts refs; checkpoint paths updated to `wsp/checkpoints`.

### Files touched
- `src/fraud_detection/world_streamer_producer/config.py`
- `src/fraud_detection/world_streamer_producer/ready_consumer.py`
- `config/platform/profiles/local.yaml`
- `tests/services/world_streamer_producer/test_ready_consumer.py`
- `tests/services/world_streamer_producer/test_runner.py`
- `README.md`
- `docs/model_spec/platform/implementation_maps/world_streamer_producer.build_plan.md`

---

## Entry: 2026-01-30 00:37:30 — Correction: dev_local profile removed (parity gate = local_parity)

### Why this correction
Earlier notes referenced `dev_local.yaml` as a completion/parity profile. That profile has now been removed to eliminate local→dev ladder friction caused by mixed filesystem + Kinesis semantics.

### Current authoritative posture
- **Parity gate:** `config/platform/profiles/local_parity.yaml` (MinIO/S3 + LocalStack/Kinesis + Postgres).
- **Smoke only:** `config/platform/profiles/local.yaml` (file‑bus + filesystem).
- **No `dev_local.yaml`** going forward.

### Impact
References to `dev_local` in prior entries should be treated as historical only; use `local_parity` where parity validation is required.

---

## Entry: 2026-01-30 03:11:12 — Live progress logging for WSP streams

### Trigger
User requested real-time visibility into WSP streaming progress during parity runs.

### Decision trail (live)
- Progress logging should be configurable per run via env, not code edits.
- Emit periodic progress with output id, emitted count, last file/row, and timestamp.
- Keep defaults conservative to avoid log spam (every 1000 events or 30 seconds).

### Implementation notes
- Added progress logging in `_stream_events` with env controls:
  - `WSP_PROGRESS_EVERY` (default 1000)
  - `WSP_PROGRESS_SECONDS` (default 30)
- Added `stream start` and `output complete` markers per output id.
- Documented the envs in the parity runbook.
- Fixed missing `import os` needed for env access in progress logging.

### Files touched
- `src/fraud_detection/world_streamer_producer/runner.py`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 10:24:24 — WSP stream_view mode (global ts_utc source)

### Trigger
Oracle Store Option C was locked: provide **time‑sorted stream views** derived from engine outputs. WSP must consume these views (not raw engine parts) for v0 parity.

### Decision trail (live)
- WSP must remain **oracle‑rooted** and never rely on SR artifacts for its source.
- The stream view is **derived** under the engine run root and must be treated as **another oracle asset**, not a platform artifact.
- WSP needs a **mode switch** so we can keep the legacy engine‑pull path for local smoke while making parity/dev/prod use the stream view.

### Changes I’m making
- Add `policy.stream_mode` (default `engine`) and `wiring.oracle_stream_view_root` to WSP profiles.
- Implement **stream_view mode** in the runner:
  - Compute `stream_view_id` **per output_id** from world identity + output_id + sort keys.
  - Resolve stream view root (`<engine_run_root>/stream_view/ts_utc/output_id=<output_id>/<stream_view_id>`).
  - Read `_stream_view_manifest.json` + `_stream_sort_receipt.json` per output and fail closed if missing or mismatched.
  - Stream events per output in **time order** (no union).
- Keep existing engine‑pull mode for `local` profile (smoke) only.

### Invariants enforced
- If `stream_mode=stream_view` and view/receipt missing → **FAIL** (no implicit fallback in parity/dev/prod).
- Output IDs in the manifest must match the requested output_id.
- Checkpoints remain **per‑output** (consistent with WSP v0 cursor model).

---

## Entry: 2026-01-30 14:06:21 — Correction: stream view root is per‑output (no stream_view_id path)

### Trigger
Oracle Store stream view path was corrected to **exclude** `stream_view_id` and to use
`bucket_index` partitions.

### Decision trail (live)
- `stream_view_id` remains valuable for integrity checks, but embedding it in the path makes
  runbook usage and local discovery harder.
- WSP should treat the stream view root as:
  `.../stream_view/ts_utc/output_id=<output_id>/` and read all parquet under bucket partitions.

### Implementation notes
- WSP now resolves the stream view root **per output_id** (no stream_view_id path segment).
- WSP still computes `stream_view_id` and validates it against the manifest when present.
- Sorting keys remain `ts_utc`, `filename`, `file_row_number`; partitioning is `bucket`.

---

## Entry: 2026-01-30 18:05:12 — Correction: flat stream view layout (no bucket directories)

### Trigger
Oracle stream view layout was simplified to **flat per output_id** (no `bucket_index` dirs).

### Implementation notes
- WSP continues to read **all parquet** under:
  `.../stream_view/ts_utc/output_id=<output_id>/`.
- No change to envelope formation or ordering semantics.

### Impact
- Simplifies operator workflows (no extra path segment).
- Keeps integrity validation intact (manifest/receipt).

---

## Entry: 2026-01-30 23:57 — WSP READY uses explicit oracle engine root (stream view id consistency)

### Trigger
`STREAM_VIEW_ID_MISMATCH` during WSP READY consumption after building MinIO stream views. Expected id was derived from a **local** `engine_run_root` provided by SR, while the manifest was built with the **S3 oracle root**.

### Live decision trail (notes as I think)
- SR still operates against **local engine artifacts** for evidence/gate checks, so its READY payload carries `engine_run_root=runs/...`.
- WSP must stream from the **Oracle Store in S3** for parity and should not derive stream view identity from local paths.
- The stream view id is a deterministic hash of `engine_run_root` + `scenario_id` + `output_id` + sort keys. If WSP uses local roots, it **must** mismatch.
- The safest parity rule is: when an explicit `ORACLE_ENGINE_RUN_ROOT` is provided in the WSP profile (env), treat it as authoritative and ignore SR’s local root for stream‑view identity and reads.

### Decision
- **WSP READY prefers explicit oracle wiring** (`ORACLE_ENGINE_RUN_ROOT`, `ORACLE_ROOT`) over SR’s local `engine_run_root` when present.
- Update Make targets to **export oracle wiring** into WSP READY runner so the profile consistently sees the S3 root.

### Changes
- `src/fraud_detection/world_streamer_producer/ready_consumer.py`: prefer `profile.wiring.oracle_engine_run_root`/`oracle_root` when set.
- `makefile`: export `ORACLE_ENGINE_RUN_ROOT`, `ORACLE_ROOT`, `ORACLE_SCENARIO_ID` into WSP READY targets.
- Runbook note added for `STREAM_VIEW_ID_MISMATCH` (ensure `ORACLE_ENGINE_RUN_ROOT` points to S3 path used for sorting).

### Invariants enforced
- WSP uses **oracle S3 root** for stream view identity in parity mode.
- SR can continue validating against **local engine outputs** without breaking WSP streaming.

### Validation plan
- Re‑run `platform-wsp-ready-consumer-once` after SR READY; expect no `STREAM_VIEW_ID_MISMATCH` and successful streaming.

---

## Entry: 2026-01-31 04:05 — Fix MinIO path-style handling in WSP stream reader

### Trigger
WSP READY failed with `__init__() got an unexpected keyword argument 'path_style_access'` when constructing `pyarrow.fs.S3FileSystem`.

### Reasoning (live)
- PyArrow 19 uses `force_virtual_addressing` rather than `path_style_access`.
- For MinIO (path-style), we should **avoid virtual addressing**; with `endpoint_override` set, PyArrow already uses path-style by default unless `force_virtual_addressing=True`.

### Decision
Remove `path_style_access` and use `force_virtual_addressing=False` when `path_style` is true.

### Change
- `src/fraud_detection/world_streamer_producer/runner.py`: replace `path_style_access` with `force_virtual_addressing=False`.

### Validation plan
Re-run `make platform-wsp-ready-consumer-once WSP_PROFILE=config/platform/profiles/local_parity.yaml` and confirm stream starts (no `path_style_access` error).

---

## Entry: 2026-01-31 05:10 — WSP ts_utc normalization to canonical RFC3339 micros

### Trigger
IG quarantined WSP events with `ENVELOPE_INVALID`. The canonical envelope requires `ts_utc` as RFC3339 with **exactly 6 fractional digits** and trailing `Z`. WSP was using `datetime.isoformat()` which emits `+00:00` and can omit fractional seconds.

### Decision
Normalize all WSP `ts_utc` to `YYYY-MM-DDTHH:MM:SS.ffffffZ` before pushing to IG.

### Change
- `src/fraud_detection/world_streamer_producer/runner.py`: `_normalize_ts` now formats UTC with fixed microseconds and trailing `Z`.

### Validation plan
Re-run WSP READY once and confirm IG no longer quarantines for `ENVELOPE_INVALID`.

---

## Entry: 2026-01-31 07:06:25 — WSP v0 green (stream‑view parity)

### Problem / goal
Confirm WSP v0 is **green** for local_parity: READY → stream view → IG push, capped runs for smoke.

### Evidence (local parity)
- WSP READY consumed Kinesis `sr-control-bus` and streamed capped events (`max_events=20`) from MinIO stream views.
- Stream view root used: `s3://oracle-store/.../stream_view/ts_utc/output_id=<output_id>/part-*.parquet`.
- WSP emitted narrative logs (`stream start/stop`) and respected `max_events`.

### v0 green definition (WSP)
- Stream‑view only mode (no raw engine streaming).
- Canonical envelope (`ts_utc` RFC3339 micros + `Z`) and provenance fields stamped.
- READY consumption via Kinesis in parity; local smoke via capped runs; checkpoints persisted in Postgres.

---

## Entry: 2026-01-31 18:41:00 — Traffic stream alignment (behavioural streams only)

### Trigger
`docs/model_spec/data-engine/interface_pack/data_engine_interface.md` clarifies engine output roles and the **dual behavioural stream policy**.

### Reasoning (WSP-specific)
- WSP is the **traffic producer**, so its allowlist must reflect **behavioural streams**, not join surfaces.
- `arrival_events_5B` is explicitly a **traffic primitive** (join surface) and must remain oracle‑only.
- `s2_flow_anchor_baseline_6B` / `s3_flow_anchor_with_fraud_6B` are **behavioural context**, not traffic.
- The correct traffic feeds are:
  - `s2_event_stream_baseline_6B` (clean baseline channel)
  - `s3_event_stream_with_fraud_6B` (post‑overlay channel)

### Decision (binding for WSP v0)
- Default WSP output allowlist is **exactly the two behavioural event streams**.
- WSP never emits `arrival_events_5B` unless an explicit future policy adds it.

### Planned edits
- Update `config/platform/wsp/traffic_outputs_v0.yaml` to list the two event streams only.
- Ensure the runbook points WSP stream view to those outputs.


## Entry: 2026-01-31 18:50:30 — Chronology correction (entry placement)

### Note
A prior traffic‑alignment entry was inserted above older entries due to patch placement. This note preserves chronology by timestamp without rewriting history. Future entries will be appended only.

---

## Entry: 2026-02-01 04:35:20 — Dual-stream concurrency + per-output caps (READY path)

### Trigger
User requested a **200‑record run** that demonstrates **dual‑stream concurrency** (baseline + fraud channels) without interleaving, and observed that WSP currently processes `traffic_output_ids` sequentially with `max_events` applying across outputs. This fails the “two channels concurrently” expectation and can stop after the first output.

### Authorities / inputs (binding)
- WSP build plan: “two concurrent behavioural channels; not interleaved.”
- Engine interface pack update: primary streams are `s2_event_stream_baseline_6B` + `s3_event_stream_with_fraud_6B`.
- Platform doctrine: WSP produces, IG admits, EB owns replay offsets (WSP should not shortcut).

### Live decision trail (notes as I think)
- The current READY consumer is **single‑threaded** and streams outputs sequentially in one loop.
- Running **two WSP processes** (one per output) would satisfy concurrency, but READY dedupe is **message‑level**, so the second worker gets skipped after the first writes a `STREAMED` record. This makes parallel workers brittle without changing dedupe semantics.
- The cleanest v0 fix is to make WSP **parallelize output_ids within a single READY run**, so concurrency happens under one READY message, and dedupe semantics remain intact.
- A per‑output cap is needed to make a 200‑record diagnostic run meaningful for **both** streams. A single global cap would stop after the first output and would not validate the second stream.
- Concurrency should be **on by default** when multiple outputs exist (to match “dual‑stream” semantics), but still overridable for debugging or resource constraints.

### Decision
- Implement **output‑level concurrency** inside WSP’s stream‑view path.
- Add **per‑output max‑events** support (cap each output independently) for READY runs.
- Keep READY dedupe semantics unchanged (still message‑level), avoiding split workers.

### Planned edits (before code)
1) Refactor `_stream_from_stream_view` to stream **per‑output** via a helper and support **ThreadPoolExecutor** across output_ids.
2) Add `WSP_OUTPUT_CONCURRENCY` (env) to control parallelism; default to `len(output_ids)` when >1.
3) Add `WSP_MAX_EVENTS_PER_OUTPUT` (env / ready consumer) to cap each output independently.
4) Update runbook + WSP build plan to make this behavior explicit for local‑parity runs.

---

## Entry: 2026-02-01 05:00:47 — Implement dual-stream concurrency + per-output caps (local parity)

### What changed (mechanics)
- Added **parallel output streaming** in WSP stream‑view path (per‑output worker threads; default concurrency = number of traffic outputs when >1).
- Added **per‑output max events** support (`WSP_MAX_EVENTS_PER_OUTPUT`) and passed it through READY consumer → WSP runner.
- Updated Make targets to pass `--max-events-per-output` when set.
- Updated WSP build plan + parity runbook to explain dual‑stream concurrency and per‑output caps.

### Why this matches the design intent
- The design calls for **two concurrent behavioural channels** (baseline + fraud) without interleaving.
- Prior sequential streaming could exhaust the cap on the first output and never validate the second.
- Parallel per‑output streaming keeps each channel ordered by `ts_utc` **within its own stream** while allowing simultaneous flow across channels.

### Test / validation (local‑parity)
- Cleared LocalStack control bus to avoid duplicate READY messages, created a fresh platform run id, restarted IG, then ran SR → WSP.
- WSP run: `WSP_OUTPUT_CONCURRENCY=2`, `WSP_MAX_EVENTS_PER_OUTPUT=200`, `WSP_READY_MAX_MESSAGES=1`.
- Observed:
  - WSP logs show **simultaneous stream start** for `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B`.
  - WSP stops at **200 per output** (total emitted=400).
  - IG logs show **admitted** events for both output_ids, **quarantine=0**.
  - EB logs show publish lines for **both** `fp.bus.traffic.baseline.v1` and `fp.bus.traffic.fraud.v1`.

---

## Entry: 2026-02-01 12:06:00 — Default traffic output = fraud (override via env)

### Trigger
User clarified v0 should run a **single traffic stream** by default (fraud) and keep baseline optional.

### Decision trail (live)
- Keep the dual stream views sorted to allow fast switching.
- Default policy should emit **fraud only**.
- Provide runtime override to avoid editing files during experiments.

### Implementation notes
- `traffic_outputs_v0.yaml` now contains only `s3_event_stream_with_fraud_6B`.
- Added WSP env overrides:
  - `WSP_TRAFFIC_OUTPUT_IDS`
  - `WSP_TRAFFIC_OUTPUT_IDS_REF`

---

## Entry: 2026-02-02 19:30:00 — WSP context streams (traffic + behavioural_context outputs)

### Trigger
Control & ingress plane now requires **context join surfaces** to be published as EB topics (no Context Preloader). WSP must emit context outputs alongside traffic, while keeping traffic **single‑mode per run** (baseline OR fraud).

### Authorities / inputs
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md` (roles + join map + time‑safe surfaces).
- WSP design authority (stream‑view only, no EB writes).
- Platform decision: traffic + context topics exposed at EB; RTDL storage/retention deferred.

### Live decision trail (notes as I think)
- WSP must stay **engine‑rooted** and **stream‑view only**; we add context outputs to the WSP plan without changing that boundary.
- Traffic output list remains a **policy allowlist** (default fraud). Context output list is **policy‑scoped** and auto‑switches to baseline when traffic mode is baseline.
- Keep channels **separate** (no interleaving at WSP); IG owns topic routing.
- Output selection must fail closed on unknown outputs (catalogue is the authority).

### Implementation details (what changed)
- Added policy keys:
  - `context_output_ids_ref` (default fraud context list)
  - `context_output_ids_baseline_ref` (baseline mode context list)
- WSP now merges **traffic outputs + context outputs** into a single stream plan (deduped).
- Output roles are stamped as `business_traffic` or `behavioural_context` in WSP facts payload.
- Gate‑PASS checks are enforced across **all** selected outputs.

### Files touched (no secrets)
- `src/fraud_detection/world_streamer_producer/config.py` (context allowlist resolution).
- `src/fraud_detection/world_streamer_producer/runner.py` (traffic+context selection + role tagging).
- `config/platform/profiles/*.yaml` (context output refs wired into profiles).
- `config/platform/wsp/context_fraud_outputs_v0.yaml`
- `config/platform/wsp/context_baseline_outputs_v0.yaml`

### Invariants enforced
- **Single‑mode traffic** per run (baseline OR fraud).
- Context outputs are **always** emitted (arrival events, arrival entities, and the mode‑aligned flow anchor).
- WSP continues to **push only to IG**; EB remains IG‑only.
- **No secrets in profiles:** `oracle_root` and `ig_ingest_url` are wiring only; they can be literals or env placeholders, but never credentials.
- **WSP should reuse legacy engine‑pull framing** to avoid downstream schema drift. The simplest safe path is to reuse IG’s `EnginePuller` + `OutputCatalogue` for event framing and payload structure, but keep WSP’s control flow separate (push to IG, never EB).
- **Oracle root resolution:** locators may already be absolute (e.g., `runs/local_full_run-5/...`); WSP must not blindly prefix and double‑nest. Resolve only when locator path is relative and does not already include the oracle root.
- **Smoke path must be bounded:** local runs cannot stream full data. Add a CLI `--max-events` guard for WSP; default to a small number for smoke only. This is an operator tool, not a policy rule.
- **Speedup factor lives in policy** and is available across envs, but it does not change correctness—only pacing.

### Planned edits (before code)
1) **Profiles + README**
   - Add `policy.stream_speedup` and `wiring.oracle_root` (and `wiring.ig_ingest_url`) to `config/platform/profiles/*.yaml`.
   - Update `config/platform/profiles/README.md` to document these fields and their intent.
2) **WSP package scaffold**
   - `src/fraud_detection/world_streamer_producer/{__init__,config,control_bus,runner,cli}.py`
   - Implement config loader (profile + env interpolation).
   - Implement READY polling (file bus v0) + run_facts_view load/validate.
3) **Local smoke path**
   - WSP CLI command that processes READY once and pushes a bounded number of events to IG (`/v1/ingest/push`).
   - Makefile target `platform-wsp-ready-once` for repeatable local runs.

---

## Entry: 2026-02-02 19:55:44 — WSP traffic‑only default (context streams deferred)

### Trigger
Control & ingress scope was narrowed to **traffic‑only** streaming. Context/truth products are deferred to RTDL Phase 4.

### Decision trail (live)
- We keep the **ability** to stream context outputs in code (behind explicit config), but **disable it by default** to keep v0 parity runs simple and aligned to the “single traffic stream per run” policy.
- The stream‑sort list remains traffic‑only by default; a helper target sorts both baseline + fraud so switching modes does not require re‑sorting.

### Implementation notes
- Removed `context_output_ids_ref` and `context_output_ids_baseline_ref` from parity/dev/prod profiles so WSP emits **traffic only** unless explicitly overridden.
- Runbook updated to focus on traffic stream sorting and WSP traffic‑only runs.

---

## Entry: 2026-02-02 20:05:51 — Correction: WSP streams traffic + context (EB exposes both)

### Trigger
User clarified that **context streams and business streams are both streamed** from WSP → IG → EB and must be exposed on EB in v0.

### Decision trail (live)
- Re‑enable context output refs in parity/dev/prod profiles so WSP includes context outputs by default.
- Restore parity bootstrap and runbook steps for context streams.

### Implementation notes
- WSP continues to stream **one traffic mode per run** (baseline OR fraud) plus **context join surfaces** aligned to that mode.
- Context output sorting targets remain in Make (`platform-oracle-stream-sort-context-fraud|baseline`).


---

## Entry: 2026-02-05 14:05:51 — WSP alignment: run ids + retry posture

### Problem / goal
Bring WSP behavior in line with Control & Ingress P0 pins: carry both `platform_run_id` and `scenario_run_id` in envelopes, validate READY → facts_view identity, and implement bounded retries on 429/5xx/timeouts (same event_id) while treating schema/policy 4xx as non-retryable.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`.
- WSP build plan + design authority.

### Decisions (locked)
- Envelopes always carry both run ids when run-scoped.
- Retry only for 429/5xx/timeouts, exponential backoff with jitter, max attempts 5, cap delay 5s, same event_id.
- 4xx schema/policy errors are terminal for that output stream.

### Planned implementation steps
- Ensure READY consumer loads run_facts_view and validates scenario_run_id against READY (fail-closed on mismatch).
- Include `platform_run_id` + `scenario_run_id` in envelope pins for all outputs.
- Implement bounded retry/backoff in push path with explicit reasons for terminal 4xx.
- Expose retry knobs in WSP config (max_attempts, base_delay_ms, max_delay_ms).
- Add tests for retry on 429/5xx and stop on 4xx.

### Invariants
- Same event_id across retries; no payload mutation.
- No EB writes from WSP.

---

## Entry: 2026-02-05 14:39:18 — WSP Phase 3 implementation (READY validation + retry/backoff + run ids)

### Problem / goal
Implement the WSP Phase 3 alignment to Control & Ingress pins: validate READY scenario_run_id vs facts_view, emit platform_run_id + scenario_run_id on envelopes, and add bounded retry/backoff on IG pushes (same event_id) with 4xx as terminal.

### Decisions / constraints
- Use run_config policy defaults: max_attempts=5, base_delay_ms=250, max_delay_ms=5000 (as pinned in WSP impl_actual).
- Retry only for 429/5xx/timeouts; treat other 4xx as non-retryable and stop the stream.
- platform_run_id sourced from PLATFORM_RUN_ID (resolve_platform_run_id) and carried in every envelope; scenario_run_id remains the SR run_id.
- READY validation fails closed if scenario_run_id or platform_run_id mismatch vs run_facts_view.

### Implementation plan
- Extend WSP wiring config to accept retry knobs (wsp_retry) with defaults if omitted.
- Update READY consumer to compare READY payload vs run_facts_view for scenario_run_id (+ platform_run_id) and fail with explicit reason.
- Update stream_view envelope construction to include platform_run_id + scenario_run_id.
- Implement retry/backoff with jitter in _push_to_ig and surface terminal 4xx reason.
- Update tests/fixtures to include new fields and validate retry posture.

---

## Entry: 2026-02-05 14:56:14 — WSP Phase 3 implementation complete

### Implemented changes
- READY consumer now validates `platform_run_id` and `scenario_run_id` against run_facts_view and fails closed on mismatch.
- WSP envelopes now carry `platform_run_id` + `scenario_run_id` (run_id remains scenario_run_id) for stream_view and legacy stream paths.
- Added bounded retry/backoff for IG pushes (429/5xx/timeouts) with jitter; non‑retryable 4xx now stop the stream with `IG_PUSH_REJECTED`.
- Added retry knobs to WSP wiring (`wsp_retry`), defaulting to max_attempts=5, base_delay_ms=250, max_delay_ms=5000.

### Files touched
- `src/fraud_detection/world_streamer_producer/ready_consumer.py`
- `src/fraud_detection/world_streamer_producer/runner.py`
- `src/fraud_detection/world_streamer_producer/config.py`
- `config/platform/profiles/{local,dev,prod,local_parity}.yaml`
- `tests/services/world_streamer_producer/test_ready_consumer.py`
- `tests/services/world_streamer_producer/test_runner.py`
- `tests/services/world_streamer_producer/test_push_retry.py`

### Validation notes
- Added unit coverage for retry posture (429 retries, 4xx rejection).

---

## Entry: 2026-02-05 16:07:45 — Phase 5 validation harness updates (stream_view fixtures)

### Problem / goal
WSP stream‑view mode requires `_stream_view_manifest.json` and `_stream_sort_receipt.json`. The existing tests created engine parquet parts but did not emit stream‑view artifacts, so stream‑view validation failed in tests.

### Decision trail (live)
- Keep runtime behavior unchanged; fix **test harness only** so tests represent the stream‑view contract.
- Build minimal stream‑view artifacts per output (`part‑000.parquet`, manifest, receipt) and reuse the same rows written by arrival‑event fixtures.

### Changes applied (test harness only)
- `tests/services/world_streamer_producer/test_runner.py`:
  - `_write_arrival_events` now returns the rows it writes.
  - Added `_write_stream_view(...)` to create the stream‑view parquet + manifest/receipt.
  - Tests now call `_write_stream_view` for `arrival_events_5B` before streaming.

### Tests run
- `python -m pytest tests/services/world_streamer_producer/test_runner.py tests/services/world_streamer_producer/test_push_retry.py -q`
- Result: **tests passed**.

### Notes
- No WSP runtime code changes; stream‑view fixture alignment only.

---

---

## Entry: 2026-02-05 16:35:40 — Parity validation finding: scenario_run_id sourced from engine receipt

### Observation
During Control & Ingress parity run (200 events/output), IG receipts show `scenario_run_id` equal to the **engine receipt run_id** (`c25a…`) rather than the SR scenario_run_id (`2afa…`). Example receipt: `platform_20260205T162018Z/ig/receipts/010e4053...json`.

### Root cause (current behavior)
`WorldStreamProducer.stream_engine_world(...)` sets `run_id = receipt.get("run_id")` (engine receipt) and uses that value for both `run_id` and `scenario_run_id` in the envelope. READY consumer validates SR scenario_run_id against run_facts_view, but does **not** pass it into the stream runner.

### Implications
- Violates the Control & Ingress pin that `scenario_run_id` in envelopes must match SR scenario_run_id.
- Downstream receipts carry an engine identifier in place of the scenario run id, breaking replay join assumptions.

### Proposed fix (pending confirmation)
- Pass `scenario_run_id` from READY/run_facts_view into `stream_engine_world(...)` (and/or set on producer state).
- Set envelope `scenario_run_id` from SR scenario_run_id, while preserving engine receipt `run_id` as a separate field (e.g., keep `run_id` as engine run id or introduce `engine_run_id` in payload/pins if needed).

### Next action
Await confirmation on how to retain engine run identity while correcting `scenario_run_id` before implementing.

---

## Entry: 2026-02-05 16:42:10 — Decision: scenario_run_id from SR; engine run_id preserved

### Problem
Parity run revealed envelopes/receipts using engine receipt `run_id` as `scenario_run_id`, violating Control & Ingress pins (SR scenario_run_id must be carried end‑to‑end).

### Decision
- **Set envelope `scenario_run_id` from SR (READY/run_facts_view).**
- **Preserve engine receipt `run_id` in envelope `run_id`** to keep engine provenance intact.

### Rationale
- Aligns with pinned control/ingress semantics while avoiding a schema change or payload expansion.
- Canonical envelope already allows `run_id` as a generic correlation id; using it for engine run id is valid.
- `event_id` derivation does not depend on `run_id`, so idempotency remains stable.

### Plan (immediate)
- Pass SR scenario_run_id from READY consumer into `WorldStreamProducer.stream_engine_world(...)`.
- Propagate a `scenario_run_id` argument into stream_view + legacy envelope paths.
- Force envelope `scenario_run_id` from that argument when provided; fall back to receipt run_id when not.
- Add/extend unit test to assert `scenario_run_id` override works and engine `run_id` is preserved.

### Files to update
- `src/fraud_detection/world_streamer_producer/ready_consumer.py`
- `src/fraud_detection/world_streamer_producer/runner.py`
- `tests/services/world_streamer_producer/test_runner.py`

---

## Entry: 2026-02-05 16:47:20 — Implemented SR scenario_run_id propagation

### Changes applied
- READY consumer now passes SR `scenario_run_id` into WSP stream runner.
- Stream‑view envelopes set `scenario_run_id` from SR while preserving engine receipt `run_id`.
- Legacy envelope path (`_stream_events`) now prefers explicit `scenario_run_id` when provided and falls back to `run_id`.

### Invariants
- `event_id` derivation unchanged (still from output_id + primary keys + manifest/param/seed/scenario_id).
- Engine provenance retained via envelope `run_id`.

### Files touched
- `src/fraud_detection/world_streamer_producer/ready_consumer.py`
- `src/fraud_detection/world_streamer_producer/runner.py`
- `tests/services/world_streamer_producer/test_runner.py`

### Tests
- `python -m pytest tests/services/world_streamer_producer/test_runner.py -q` (4 passed)

## Entry: 2026-02-08 12:36:14 - Pre-change decision: guarantee schema_version on WSP-emitted traffic envelopes

### Problem
Runtime DF service pass required schema normalization (`schema_version -> v1`) on upstream traffic records. This indicates WSP did not guarantee `schema_version` on all emitted envelopes.

### Options considered
1. Keep runtime normalizer downstream.
- Rejected: violates fail-closed schema discipline and hides producer contract drift.
2. Set default schema at IG/DF inlet when missing.
- Rejected: weakens source contract and can mask mixed producer behavior.
3. Guarantee schema_version at WSP emission source (selected).
- Selected: upstream contract correctness, deterministic downstream behavior, no hidden adaptation.

### Decision
- Ensure all WSP emission paths stamp canonical `schema_version` (v1) when absent.
- Add/adjust tests to assert emitted envelopes include schema_version on stream-view path.

### Planned files
- `src/fraud_detection/world_streamer_producer/runner.py`
- `tests/services/world_streamer_producer/test_runner.py`

---

## Entry: 2026-02-08 12:41:48 - Applied schema_version source guarantee for emitted envelopes

### Change details
1. Stream-view emission path now stamps `schema_version: v1` directly when constructing each envelope.
2. Final send path (`_push_to_ig`) now enforces a defensive fallback:
   - if upstream envelope arrives without `schema_version`, set it to `v1` before publish.

### Why both layers were kept
- Build-time stamp on stream-view path preserves explicit producer contract shape.
- Send-time guard protects legacy/non-stream-view envelope paths and prevents regressions from future emitter changes.

### File edits
- `src/fraud_detection/world_streamer_producer/runner.py`
- `tests/services/world_streamer_producer/test_runner.py`

### Validation
- `python -m pytest tests/services/world_streamer_producer/test_runner.py tests/services/world_streamer_producer/test_push_retry.py -q`
- Result: `6 passed`.

### Closure statement
The runtime normalization requirement for missing `schema_version` is now removed at source for WSP-emitted traffic envelopes.

---

## Entry: 2026-02-09 12:46PM - WSP READY dependency gate + orchestration run-scope hardening

### Trigger
Parity sequencing could start WSP streaming before RTDL downstream packs were fully alive, creating race-prone first-window behavior.

### Implemented decisions
1. Added READY dependency gate in `ready_consumer`:
- `WSP_READY_REQUIRED_PACKS` defines required run/operate pack specs.
- For each pack, WSP checks pack state presence, expected process liveness, and active run match (configurable).
- If not ready, WSP returns `DEFERRED_DOWNSTREAM_NOT_READY` and does not mark the READY message as streamed.
2. Added run-scope drift guard in run/operate orchestrator:
- pack `state.json` now persists `active_platform_run_id`,
- `up` fails closed when active run changes while prior processes remain alive (`ACTIVE_PLATFORM_RUN_ID_MISMATCH_RESTART_REQUIRED`).
3. Updated parity lifecycle ordering in `Makefile`:
- start RTDL packs before control/ingress,
- stop control/ingress before RTDL packs on shutdown.

### Files changed
- `src/fraud_detection/world_streamer_producer/ready_consumer.py`
- `src/fraud_detection/run_operate/orchestrator.py`
- `config/platform/run_operate/packs/local_parity_control_ingress.v0.yaml`
- `Makefile`
- `tests/services/world_streamer_producer/test_ready_consumer.py`
- `tests/services/run_operate/test_orchestrator.py`

### Validation
- Targeted impact tests included in green runs:
  - targeted matrix: `23 passed`
  - broader impacted suites: `98 passed`
