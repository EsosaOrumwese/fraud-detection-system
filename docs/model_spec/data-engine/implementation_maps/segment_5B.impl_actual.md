# Segment 5B Implementation Map (Actual)

Append-only implementation planning log for Segment 5B. Each entry documents
the design element, a short summary, and the detailed decision path. Do not
delete or rewrite prior entries.

---

### Entry: 2026-01-20 02:12

5B.S0 gate & sealed inputs review (initial plan).

Design problem summary:
- Implement 5B.S0 as the closed-world gate for the arrival realisation segment:
  verify upstream PASS for 1A-3B + 5A, seal all permitted inputs into
  `sealed_inputs_5B`, and emit `s0_gate_receipt_5B` with run identity,
  upstream status map, `scenario_set`, and `sealed_inputs_digest`.
- The state must be metadata-only, deterministic, and re-runnable, while
  complying with the catalogue-only resolution rules and the 5B hashing laws.

Decision path and options considered:
1) **Contract source & catalogue layout**
   - Option A: hard-code model_spec paths for 5B dictionaries/schemas.
   - Option B: use `ContractSource` (as in 5A.S0) so dev uses model_spec, and
     production can switch to root without code changes.
   - Decision: use `ContractSource` and `EngineConfig` (same pattern as 5A.S0).

2) **Scenario-set authority**
   - Option A: derive scenario_set solely from `scenario_manifest_5A`.
   - Option B: use `scenario_id` from run receipt and treat it as the sole set.
   - Option C: prefer `scenario_manifest_5A`, but allow a run-specified subset
     if the orchestrator explicitly requests it.
   - Decision: pending confirmation. Spec emphasises consistency with
     `scenario_manifest_5A`; default will be full manifest list unless a
     run-scoped subset is explicitly approved.

3) **Seed vs sealed_inputs identity**
   - Option A: render `{seed}` placeholders into concrete paths in
     `sealed_inputs_5B` and compute digests for those specific seed outputs.
   - Option B: keep `{seed}` placeholders in `path_template` so
     `sealed_inputs_5B` is identical across seeds and compute digests using
     upstream sealed manifests where available.
   - Decision: pending confirmation. The spec says `sealed_inputs_5B` must
     depend only on `(parameter_hash, manifest_fingerprint)`.

4) **Digest resolution strategy**
   - Option A: always hash on-disk artefacts, even large datasets.
   - Option B: reuse upstream `sealed_inputs_*` digests when available and
     fall back to hashing only for configs/policies and small artefacts.
   - Decision: prefer Option B for performance, with safe fallbacks when
     upstream sealed manifests are absent.

5) **Optional vs required config conflict**
   - Spec lists `bundle_layout_policy_5B` as required, but dataset dictionary
     marks it optional and no config file exists in `config/layer2/5B/`.
   - Decision: pending confirmation on whether to treat it as optional (current
     repo posture) or require a new config file to satisfy S0.

Planned implementation outline (stepwise):
1) Create `packages/engine/src/engine/layers/l2/seg_5B/s0_gate/runner.py`
   mirroring the 5A.S0 structure (logging helpers, `_StepTimer`, `_abort`,
   `_schema_from_pack`, `_resolve_dataset_path`, `_render_catalog_path`).
2) Resolve run identity using run receipts (seed/parameter_hash/mf/run_id),
   log a story header, and enforce preconditions (scenario binding).
3) Load schema packs + dictionaries + registries for 1A-3B, 5A, 5B and
   validate schema anchors referenced by 5B dictionaries.
4) Verify upstream PASS bundles for 1A,1B,2A,2B,3A,3B,5A using the correct
   hashing law per segment (reuse or port 5A.S0 helpers for 2B/3A/3B/5A).
5) Build `sealed_inputs_5B` rows by iterating the 5B dataset dictionary /
   registry entries for the required input set, applying roles/status/read_scope
   rules from the spec. Use upstream `sealed_inputs_*` digests when present.
6) Write `sealed_inputs_5B` (sorted per spec), recompute digest, and emit
   `s0_gate_receipt_5B` with upstream map + `scenario_set` + `sealed_inputs_digest`.
7) Add CLI entrypoint + makefile target (segment5b-s0) and ensure run-report
   emission matches layer-2 conventions.

Logging/observability plan:
- Emit a story header with objective + gated inputs + outputs.
- Log each upstream segment gate result (bundle path, flag path, digest law).
- Log sealed inputs counts by status/role and the computed digest.
- Use structured progress logs where loops exceed a few dozen artefacts.

Open questions for confirmation:
- Should `scenario_set` in `s0_gate_receipt_5B` always include **all**
  scenarios from `scenario_manifest_5A`, or can it be a run-scoped subset?
- Should `sealed_inputs_5B` keep `{seed}` placeholders (seed-invariant) or
  embed concrete seed paths/digests (seed-specific)?
- Is `bundle_layout_policy_5B` truly required (create a config) or should it
  remain optional per the dataset dictionary?

### Entry: 2026-01-20 03:30

5B.S0 gate & sealed inputs (decisions locked before coding).

Design problem summary:
- Build a 5B.S0 gate that enforces upstream PASS for 1A-3B + 5A, seals a
  deterministic input universe for 5B, and emits `sealed_inputs_5B` plus
  `s0_gate_receipt_5B` with upstream status and sealed-inputs digest. The
  solution must obey catalogue-only resolution and remain lightweight
  (metadata-only), while producing seed-invariant outputs per spec.

Decision path and options considered:
1) **Scenario-set authority**
   - Option A: derive scenario_set from `scenario_manifest_5A` (full list).
   - Option B: use a run-scoped scenario binding if provided in run receipt.
   - Decision: use `scenario_manifest_5A` as the canonical source of scenarios
     and default to **all** scenario_ids in that manifest. If a run-scoped
     subset is ever provided (future run receipt or CLI extension), we will
     enforce subset-of-manifest and record it in the receipt; but the current
     implementation assumes full-manifest because run receipts do not carry a
     scenario binding today.

2) **Seed-invariant sealed_inputs_5B**
   - Option A: resolve `{seed}` placeholders to concrete paths and hash those
     datasets, making sealed_inputs depend on seed.
   - Option B: keep `{seed}` placeholders in `path_template` and avoid reading
     seed-scoped data-plane outputs so `sealed_inputs_5B` is invariant across
     seeds.
   - Decision: adopt Option B to satisfy the spec requirement that
     `sealed_inputs_5B` is keyed only by `(parameter_hash, manifest_fingerprint)`.
     This means we will not read or hash bulk seed-scoped outputs (site locations,
     alias tables, edge catalogues, etc.) in S0.

3) **Digest strategy for large seed-scoped outputs**
   - Option A: hash large artefacts anyway (violates metadata-only and blows up
     runtime for S0).
   - Option B: use a structural digest (stable hash of catalogue metadata such
     as manifest_key + schema_ref + path_template + partition_keys) and annotate
     the sealed_inputs rows with a note that the digest is structural.
   - Decision: Option B. We will compute real SHA-256 digests only for small
     configs/policies and for upstream validation bundles/flags (via their own
     hashing law). For data-plane outputs, we will use a structural digest and
     include a `notes` marker (e.g., `seed_scoped_structural_digest`) so later
     validation states can treat these as metadata-only. This is a spec-aligned
     performance choice; it will be called out in the logbook as an approved
     deviation from content hashing for bulk data-plane artefacts.

4) **bundle_layout_policy_5B optionality**
   - Spec text lists it as required, but the dataset dictionary marks it
     `optional` and the repo has no config file for it.
   - Decision: follow the dataset dictionary and treat it as OPTIONAL. If the
     file exists, seal it; if not, log it as an optional missing input. This
     avoids forcing a placeholder config and keeps S0 in sync with repo posture.

Planned implementation outline (stepwise):
1) Create `packages/engine/src/engine/layers/l2/seg_5B/s0_gate/runner.py` by
   mirroring 5A.S0 structure: logging helpers, step timer, `_abort`, schema
   anchor validation, dataset path resolution, and sealed-input digest.
2) Resolve run identity from `run_receipt.json` and initialise run logs; load
   dictionaries, registries, and schema packs for 1A-3B, 5A, 5B, and layer-level
   schema packs required for validation.
3) Verify upstream PASS bundles for 1A,1B,2A,2B,3A,3B,5A using segment-specific
   hashing laws (reuse the 5A.S0 logic for 2B/3A/3B bundle hashing).
4) Load `scenario_manifest_5A` (parquet) to compute `scenario_set` and validate
   that it is non-empty; record it in `s0_gate_receipt_5B`.
5) Build `sealed_inputs_5B` rows from the 5B dataset dictionary and registry:
   classify `status` (REQUIRED/OPTIONAL), `role`, `read_scope`; compute digests
   for configs/policies and bundle/flag entries; use structural digests for
   seed-scoped data-plane outputs; include `notes` for structural digest rows.
6) Validate `sealed_inputs_5B` and `s0_gate_receipt_5B` against `schemas.5B.yaml`,
   compute `sealed_inputs_digest`, and publish outputs atomically.
7) Emit a segment state run-report record (segment_state_runs jsonl) including
   upstream counts and sealed-inputs counts by status/role per spec.
8) Add CLI entrypoint `s0_gate_5b.py` and wire `segment5b-s0` into the makefile.

Logging/observability plan:
- Story header: objective, required upstream segments, and outputs.
- Log upstream gate verification per segment with bundle+flag paths and digest.
- Log scenario_set size and IDs (bounded) once loaded from scenario_manifest.
- Log sealed_inputs counts by status/role and emit the sealed_inputs_digest.
- For loops over dictionary entries, use a progress tracker if rows are large
  (>50) to keep the console alive without noisy spam.
