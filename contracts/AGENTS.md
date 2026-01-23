# AGENTS.md - Contracts (Model-Spec Mirror)
_As of 2026-01-10_

This folder is a **generated mirror** of the authoritative contracts in `docs/model_spec`.
Runtime code reads from `contracts/`, but **do not edit** these files by hand unless explicitly instructed.

**Authoritative sources (model_spec):**
- `docs/model_spec/data-engine/layer-*/specs/contracts/<segment>/*.yaml`
- These include dataset dictionaries, schemas, and artefact registries.

**Generated here:**
- Dataset dictionaries: `contracts/dataset_dictionary/l{layer}/seg_{SEG}/layer{layer}.{SEG}.yaml`
- Schemas: `contracts/schemas/layer{layer}/schemas.{SEG}.yaml` and `contracts/schemas/layer{layer}/schemas.layer{layer}.yaml`
- Artefact registries: `contracts/artefact_registry/artefact_registry_{SEG}.yaml`

**Policies:**
- Policy bundles are defined under `config/` per model_spec and are **not** mirrored into `contracts/`.
- Treat any files under `contracts/_stale/policies/` as legacy unless the model_spec contracts explicitly require them.

---

## Status
- Contracts mirror is **active** and should be kept in sync with model_spec.
- Legacy files may exist until explicit cleanup is approved.

---

## Reading order (for any change)
1. Read the relevant **contract-spec** under
   `docs/model_spec/data-engine/layer-*/specs/contracts/<segment>/...`
2. Read the matching state's **expanded** docs under
   `docs/model_spec/data-engine/layer-*/specs/state-flow/<segment>/...`
3. Update model_spec and re-sync `contracts/` using `make contracts-sync`.

---

> **Naming guidance:** keep the mirror mapping stable so runtime paths are deterministic.

---

## Do / Don't
- Do use `make contracts-sync` after editing model_spec contracts.
- Do not hand-edit mirrored files in `contracts/` unless explicitly directed.

---

## Packaging & snapshots (informational)
- The engine may embed a **read-only snapshot** of this mirror for offline/repro use.
  Source of truth remains `docs/model_spec`; embedded copies should match a pinned digest/version.
