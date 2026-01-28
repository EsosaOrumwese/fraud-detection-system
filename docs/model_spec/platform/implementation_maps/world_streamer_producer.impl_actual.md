
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

