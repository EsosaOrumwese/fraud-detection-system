
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

