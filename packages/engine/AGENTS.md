# AGENTS.md - Data Engine Router (Layer-1 / Segments 1B & 2A)
_As of 2025-11-05_

This router tells you what is binding, what to read first, and which parts of the engine are in play. Segments **1A and 1B** are online and sealed—treat them as read-only authority surfaces. Segment **2A** (S0-S5) is the active build as we enter implementation.

---

## 0) Scope (you are here)
- Package: packages/engine
- Active build transition: Layer-1 / Segment **2A** / States **S0-S5** (implementation starting). Segment **1B** remains live and sealed.
- Sealed references: Segments 1A & 1B (authority surfaces for downstream inputs).
- Binding specs: 2A expanded state documents and contract artefacts are locked alongside the existing 1B set.
- Other segments (2B...4B) remain locked until explicitly opened.

**Environment posture.** We are intentionally deferring integration with the shared dev environment (full artefact replay and manifest hookups) until the **entire Data Engine**—all layers, segments, and states—is built and wired together. While we are still in that build-out phase, every new state must be treated as if the complete engine were already live: wire states together locally, exercise deterministic cross-state invariants, and extend regression tests so the chain remains ready to run end-to-end the moment we connect to real artefacts. No shortcuts.

---

## 1) Reading order (strict)
Read these in order before touching code so you align with the frozen specs.

**A. Conceptual references (repo-wide, non-binding)**
- docs/references/closed-world-enterprise-conceptual-design*.md
- docs/references/closed-world-synthetic-data-engine-with-realism*.md

**B. Layer-1 narratives (orientation)**
- docs/model_spec/data-engine/narrative/

**C. Segment 1B state design (binding)**
- docs/model_spec/data-engine/specs/state-flow/1B/state-flow-overview.1B.md
- docs/model_spec/data-engine/specs/state-flow/1B/s#*.expanded.md
  - No archived pseudocode-derive L0/L1/L2/L3 from the expanded spec.

**D. Segment 2A state design (binding; ready for impl)**
- docs/model_spec/data-engine/specs/state-flow/2A/state-flow-overview.2A.md
- docs/model_spec/data-engine/specs/state-flow/2A/s#*.expanded.md (S0-S5)
  - Contracts live in docs/model_spec/data-engine/specs/contracts/2A/

**E. Data-intake guidance (structure & intent)**
- No preview/data doc for 1B. Infer dataset posture straight from the state-flow specs and contract registry.

**F. Contract specs (blueprints for contracts/)
- docs/model_spec/data-engine/specs/contracts/1B/artefact_registry_1B.yaml
- docs/model_spec/data-engine/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml
- docs/model_spec/data-engine/specs/contracts/1B/schemas.1B.yaml

> Never promote narratives, previews, or samples to binding authority. Only the expanded specs and contract documents govern code.

---

## 2) Test-yourself policy
- Run targeted pytest jobs (python -m pytest ...) for the state you modify.
- When adding RNG or egress logic, layer in regression cases that exercise both happy-path and gate-fail scenarios (mirror the Segment 1A test harness).
- Document results when handing work off (logbook or PR notes).

---

## 3) Ignore list (keep these read-only)
- docs/**/overview/**
- Anything explicitly marked deprecated or combined
- Segment 1A code paths unless a migration is authorised

---

## 4) Segment 1A references (sealed authority)
1. Expanded specs (docs/model_spec/data-engine/specs/state-flow/1A/s#*.expanded.md)
2. Contract specs (docs/model_spec/data-engine/specs/contracts/1A/)
3. Data intake (docs/model_spec/data-engine/specs/data-intake/1A/preview|data/*.md)
4. Validation bundles (alidation_bundle/manifest_fingerprint=*/...)
5. Tests: python -m pytest tests/contracts/test_seg_1A_dictionary_schemas.py tests/engine/cli/test_segment1a_cli.py tests/engine/layers/l1/seg_1A

---

## 5) Segment 1B quick references (initial)
- **State overview:** docs/model_spec/data-engine/specs/state-flow/1B/state-flow-overview.1B.md
- **Contract artefacts:** docs/model_spec/data-engine/specs/contracts/1B/{artefact_registry_1B.yaml,dataset_dictionary.layer1.1B.yaml,schemas.1B.yaml}
- **State flow short labels:**
  - S0 Gate in (verify 1A _passed.flag, load outlet catalogue)
  - S1 Country tiling (eligible raster/polygon grid)
  - S2 Tile priors (deterministic weights)
  - S3 Site counts (derive N_i per merchant/country)
  - S4 Integerise shares (largest remainder / deterministic policy)
  - S5 Cell selection (RNG: aster_pick_cell)
  - S6 Point jitter (RNG: within-cell jitter, bounded resample)
  - S7 Site synthesis (attributes, 1:1 parity with 1A)
  - S8 Egress (site_locations partitioned by [seed, fingerprint])
  - S9 Validation bundle (alidation_bundle_1B/..., _passed.flag)
- **RNG envelope:** reuse the 1A Philox/open-interval contract (ngine.layers.l1.seg_1A.s9_validation is the reference implementation).
- **Validation hash rule:** _passed.flag remains sha256_hex = <digest> over bundle files in ASCII-lexicographic order (same as 1A).
- **Dataset preview:** intentionally omitted—derive expectations from the expanded specs and contract dictionary.

Extend this section with concrete CLIs, policy paths, and test commands as you implement each state.

---

## House style (soft guidance)
- Prefer clarity and determinism over cleverness.
- Preserve the L0/L1/L2/L3 separation inside each state package.
- Surface TODOs or questions when the spec leaves gaps; do not improvise contracts.
- Keep logging informative—mirror the Segment 1A CLI/orchestrator patterns so smoke tests stay readable.

---

## Implementation guardrails (must follow)
- **Specs state intent; code must deliver outcomes.** If the literal steps in a spec would break determinism, efficiency, or memory posture, design the implementation that hits the stated end-goal instead and document the rationale in the logbook. Contracts and public artefacts still govern what you emit.
- **Performance first.** Treat every state like a production data job: profile, stream, and vectorise. Target sub-15 minute executions for the heavy kernels (S1–S6) by default, and justify any regression.
- **No more manual hand-offs.** Ensure Segment 1A staging covers every reference that Segment 1B consumes. Within Segment 1B, publish receipts, manifests, and dataset dictionaries so dependent states locate what they need without operator intervention.
- **Memory-aware by design.** Use chunked IO, deterministic spill directories, and bounded concurrency to keep RSS under control. Loading entire rasters or catalogues into RAM without back-pressure is considered a bug.
- **Resumable orchestration.** The orchestrator must be able to read existing `_passed.flag` artefacts, receipts, and RNG logs to resume from the point of failure (or clearly instruct the operator when manual repair is required) instead of rerunning S0–S9 from scratch.
- **Operational visibility.** Instrument long-running steps with structured logging (progress counts, ETA-style checkpoints, RNG envelopes) so smoke tests and production monitors never look “stuck”.
- **Deterministic artefacts only.** All seeded outputs (parquet partitions, manifests, contract bundles) must hash identically across reruns. Any volatile metadata (timestamps, `run_id`, temp paths, live telemetry) should be isolated from validation surfaces or normalised by tooling.

_This router remains command-free by design. Execution strategy, test harness, and internal folder improvements stay up to you while respecting the governing specs._
