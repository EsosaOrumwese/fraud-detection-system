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

---

## Entry: 2026-01-28 13:32:07 — Wire oracle_root into platform profiles (pre-change)

### Trigger
WSP Phase 1 implementation starts and requires `oracle_root` to be surfaced in platform profiles as a wiring value (no secrets).

### Live reasoning (notes)
- Oracle Store is a **boundary contract**, but it still needs a concrete **wiring hook** (`oracle_root`) to point at the current sealed world location.
- Defaulting `oracle_root` to `runs/local_full_run-5` aligns with the only fully materialized local run, while keeping it adjustable for the future `runs/data-engine` move.
- For dev/prod, the value should remain **wiring** (env or S3 URI) and must not embed credentials.

### Planned edit
- Update `config/platform/profiles/*.yaml` to include `wiring.oracle_root`.
- Update profiles README to document `oracle_root` semantics and the “no secrets” posture.

---

## Entry: 2026-01-28 13:38:37 — Applied: oracle_root wiring in profiles

### What changed
- Added `wiring.oracle_root` to all platform profiles.
- Updated `config/platform/profiles/README.md` to define Oracle Store wiring and its non‑secret posture.

### Notes
- Local/dev_local default to `runs/local_full_run-5` (temporary).
- Dev/prod use `${ORACLE_ROOT}` so the location can be swapped without code edits.

---

## Entry: 2026-01-28 14:37:34 — Applied: Oracle Store Phase‑1 checks (local by‑ref verification)

### What I changed
- Added an **Oracle Store checker** (`src/fraud_detection/oracle_store/`) with:
  - profile loader (wiring + policy; no secrets),
  - run_facts_view schema validation,
  - locator existence checks (local + S3),
  - required gate PASS validation (catalogue‑driven),
  - seal marker detection (soft in v0 unless `--strict-seal`).
- Added CLI entrypoint: `python -m fraud_detection.oracle_store.cli`.
- Added Make target `platform-oracle-check` with `ORACLE_RUN_FACTS_REF` input.
- Updated Oracle Store design authority with v0 transitional notes (pack‑root aliasing + no seal markers locally).

### Rationale (live)
- The checker provides a **green/red** readiness gate for the Oracle boundary before we harden WSP.
- It is **fail‑closed** on missing locators or required gate receipts, but **warn‑only** on missing seal markers in v0 local runs.
- Locators are validated without scanning for “latest”; only locator‑implied listing is allowed for `part-*`.

### Guardrails
- No secrets are stored or logged; all endpoints are wiring only.
- S3 checks are optional by virtue of the profile wiring; local is the default for v0.
