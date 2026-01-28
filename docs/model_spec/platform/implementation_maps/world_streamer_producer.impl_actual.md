
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

