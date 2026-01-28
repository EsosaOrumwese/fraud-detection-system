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

---

## Entry: 2026-01-28 14:58:40 — Phase 2 hardening (reason codes + strict‑seal + S3 tests)

### Trigger
User requested Phase 2 hardening of Oracle Store (stable reason codes, strict‑seal for dev, and S3 validation tests).

### Live reasoning (notes)
- The checker already validates locators and gates, but **reason codes must be stable** so operators can classify failures deterministically.
- Dev/prod must **fail on unsealed packs**; local remains WARN‑only until a packer exists.
- We need **unit‑level S3 path validation tests** (no real S3) to ensure glob expansion and head/list logic are correct.

### Planned edits
1) Add stable reason codes to `OracleCheckReport` (codes + issue details).
2) Enforce strict‑seal default for `profile_id in {dev, prod}` in the CLI (override allowed).
3) Add S3 path validation tests using stubbed clients; add tests for oracle path resolution.

---

## Entry: 2026-01-28 14:51:51 — Applied: Phase 2 hardening (reason codes + strict‑seal + tests)

### What changed
- **Stable reason codes:** `OracleCheckReport` now emits `reason_codes` + structured `issues` with `code/detail/severity` (PACK_NOT_SEALED, LOCATOR_MISSING, DIGEST_MISSING, GATE_PASS_MISSING, RUN_FACTS_INVALID/UNREADABLE).
- **Strict‑seal default for dev/prod:** CLI now enforces strict seal markers for `profile_id in {dev, prod}` unless explicitly overridden.
- **S3 path validation tests:** added unit tests for S3 head + glob listing and oracle path resolution.

### Notes
- Local runs still WARN on missing seal markers (v0 transitional rule).
- Missing digest is treated as error when `require_digest` is true; use `--allow-missing-digest` to relax.

---

## Entry: 2026-01-28 15:02:20 — Phase 3 planning (seal + manifest tooling)

### Trigger
User asked to proceed to Phase 3 planning once Phase 2 hardening is done.

### Live reasoning (notes)
- Dev strict‑seal already fails without seal markers; Phase 3 must **introduce seal/manifest tooling** to make dev green.
- We cannot touch engine internals, so sealing must be done by a **separate packer/CLI** that writes only **new metadata objects** at the pack root.
- We must support the **v0 pack‑root alias** (existing `runs/local_full_run-*` roots) without moving data.
- The manifest must capture interpretation identity (engine release + catalogue/gate-map identifiers) to keep future reads reproducible.

### Decisions to lock
- OracleWorldKey is pinned as `{manifest_fingerprint, parameter_hash, scenario_id, seed}` (run_id excluded).
- Seal artifacts are **write‑once** and **idempotent** (create‑if‑absent; fail on mismatch).
- Pack manifest schema will live under `docs/model_spec/platform/contracts/oracle_store/` (versioned).

### Planned work (Phase 3)
1) Define manifest + seal schema (minimal fields, versioned).
2) Implement packer CLI:
   - Accept `run_facts_view` ref or explicit tokens.
   - Derive pack root from locators (or use explicit `--pack-root`).
   - Write `_oracle_pack_manifest.json` + `_SEALED.json` only if absent.
3) Update oracle checker to read and report manifest metadata when present.

---

## Entry: 2026-01-28 15:18:40 — Phase 3 implementation (packer + manifest + strict seal)

### Live reasoning (decisions made)
- **Manifest contents:** keep minimal but sufficient: `oracle_pack_id`, OracleWorldKey tokens, `engine_release`, `catalogue_digest`, `gate_map_digest`, `created_at_utc`. This anchors interpretation without dragging large payloads.
- **OracleWorldKey tokens:** `{manifest_fingerprint, parameter_hash, scenario_id, seed}` only; `run_id` excluded per design.
- **Pack id derivation:** sha256 over world key + engine_release + catalogue/gate_map digests to avoid collisions across engine versions.
- **Write‑once semantics:** manifest + seal are written with create‑if‑absent; if the file exists and content differs → fail (no overwrite).
- **Pack‑root alias support:** packer derives pack root from run_facts locators when not explicitly provided; if multiple roots → fail (ambiguity).
- **Local safety:** packer refuses to seal if the local pack root directory does not exist (avoid sealing a phantom root).
- **Strict‑seal posture:** dev/prod enforce seal markers by default; local allows unsealed until packer is in routine use.

### What I implemented
- Added Oracle packer (`src/fraud_detection/oracle_store/packer.py`) with:
  - OracleWorldKey + manifest models
  - pack root derivation from locators
  - write‑once manifest + seal creation (`_oracle_pack_manifest.json`, `_SEALED.json`)
- Added seal CLI (`src/fraud_detection/oracle_store/seal_cli.py`) that seals from `run_facts_view`.
- Updated checker to report manifest metadata when present and emit `PACK_MANIFEST_MISSING` warnings.
- Added Make target `platform-oracle-seal` with `ORACLE_ENGINE_RELEASE` + optional `ORACLE_PACK_ROOT`.
- Added unit tests for packer write‑once + mismatch detection.

---

## Entry: 2026-01-28 15:32:10 — Packer idempotency fix + sample seal validation

### What changed
- Adjusted packer idempotency: manifest/seal comparisons now ignore timestamp fields and compare only identity‑critical fields.
- Added local pack root existence check to avoid sealing non‑existent roots.

### Validation (local/dev)
- Sealed pack for `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92` using `run_facts_view` (engine release `engine-local-v0`).
- Strict‑seal check (dev_local) now passes with status **OK**.

---

## Entry: 2026-01-28 15:10:45 — Manifest schema + validation

### What changed
- Added Oracle Store contract schemas:
  - `docs/model_spec/platform/contracts/oracle_store/oracle_pack_manifest.schema.yaml`
  - `docs/model_spec/platform/contracts/oracle_store/oracle_pack_seal.schema.yaml`
- Checker now validates manifests when present and reports `PACK_MANIFEST_INVALID` on schema failure.

### Rationale
- Schemas make pack metadata auditable and enforceable without embedding logic in the engine.
- Validation keeps the seal/manifest tooling honest as we expand to dev/prod.

---

## Entry: 2026-01-28 14:45:50 — Expand Oracle Store build plan for implementation + hardening

### Trigger
User asked to update the Oracle Store build plan so we can start **implementation + hardening** (local then dev).

### Live reasoning (notes)
- Phase 1 (contract) is effectively complete; we now need **implementation steps** that make the Oracle boundary verifiable and “green.”
- Local must tolerate missing seal markers (v0 transitional rule), but **dev must be strict**.
- Sealing tooling should be **external to the engine** (black‑box rule) and must be **write‑once** to avoid mutation.
- S3 compatibility needs explicit validation (path expansion, head/list) before we declare dev‑readiness.

### Planned plan changes
- Mark Phase 1 complete and expand Phase 2 into concrete implementation steps (checker CLI, strict‑seal, S3 validation, failure taxonomy).
- Add a dedicated phase for **seal/manifest tooling** (packer CLI) with write‑once semantics.
- Add an ops/governance hardening phase (immutability enforcement, tombstone policy, least‑privilege reads).
