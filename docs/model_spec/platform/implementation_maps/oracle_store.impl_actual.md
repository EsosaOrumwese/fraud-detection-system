# Oracle Store Implementation Map
_As of 2026-01-28_

---

## Entry: 2026-01-28 13:16:54 — Oracle Store component initiation (sealed world boundary)

### Trigger
User approved building **Oracle Store** as a **separate platform component** alongside WSP, with a configurable `oracle_root` (use `runs/local_full_run-5` now; migrate to `runs/data-engine` later) and no secrets in plans/logs.

### Authorities / inputs (binding)
- Root `AGENTS.md` (progressive elaboration, append‑only decision trail, no secrets).
- Platform blueprint + deployment tooling notes (engine outputs are sealed by‑ref world artifacts).
- Engine interface pack (locator schema, digest posture, receipts).
- WSP design authority (streams only from SR join surface; no scanning).

### Live decision trail (notes as I think)
- Oracle Store is **not** a service that transforms data; it is a **boundary contract** that defines how the sealed world is stored, referenced, and verified.
- This boundary must be **explicit** so multiple components (SR verifier, WSP, legacy pull/backfill) can use the same invariant without hidden drift.
- `oracle_root` must be **configurable** because:
  - local data already exists under `runs/local_full_run-5`
  - the long‑term target is `runs/data-engine/` (or S3 in dev/prod)
  - hard‑coding would force code edits for environment changes
- Oracle Store must enforce **immutability + by‑ref access**:
  - sealed runs are write‑once
  - consumers read by locator + digest only
  - no “latest” discovery; SR’s `run_facts_view` is the entrypoint
- Keep Oracle Store **vendor‑neutral** (filesystem vs S3); adapters are wiring, not policy.

### Alternatives considered (and why rejected)
- **Fold Oracle Store into WSP only**: rejected; boundary must be shared and explicit across the platform.
- **Treat `oracle_root` as a policy constant**: rejected; it is wiring/environmental, not a semantic policy.
- **Allow scanning for “latest run”**: rejected; violates SR join‑surface law and risks provenance drift.

### Planned steps (before coding)
1) Create Oracle Store design authority doc:
   - `docs/model_spec/platform/component-specific/oracle_store.design-authority.md`
2) Create Oracle Store build plan:
   - `docs/model_spec/platform/implementation_maps/oracle_store.build_plan.md`
3) Define v0 contract:
   - `oracle_root` config (default `runs/local_full_run-5`)
   - path conventions (run_id‑scoped, immutable)
   - locator/digest checks (by‑ref only)
4) Wire references in WSP plan to the Oracle Store contract (no code until plans are recorded).

