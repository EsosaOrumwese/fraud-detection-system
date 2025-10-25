# Engine Evolution Decision Record — Vanilla ➜ Current Build (Segment 1A/1B, Oct 2025)

## Baseline & Scope
- **Baseline commit:** `06725f6` (2025‑10‑21) — “Update AGENTS.md to reflect changes in active build scope…”. At this point Segment 1B only exposed sealed artefacts and the runbooks did not cover end-to-end execution. No state beyond S2 had deterministic orchestration, and Segment 1A used the original hurdle/NB coefficient bundle without corridor corrections or overflow guards.
- **Scope of record:** every change from `3822732` through `2e2cf0c` (2025‑10‑22 ➜ 2025‑10‑25). Each bullet below cites the commit, date, rationale, key artefacts, and validation/log outcome so the delta from vanilla is auditable.

## Change Catalogue (chronological)

### Segment 1B Gate + S1 Foundations — 2025‑10‑22
- `3822732` — Added the Segment 1B **S0 gate** orchestrator, schema anchors, dictionary entries, shared schema/dictionary helpers, failure taxonomy, and regression tests (`packages/engine/src/engine/layers/l1/seg_1B/s0_gate/**`, `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`, `tests/engine/l1/seg_1B/test_s0_gate.py`). This established gated receipts and PASS/FAIL enforcement for the new segment.
- `21632fb` — Implemented **S1 tile_index** loaders/kernels/predicates plus schema/dictionary wiring so routing tiles can be materialised deterministically.
- `819d654` — Introduced the **L2 runner and L3 validator** for S1, ensuring geometry/predicate outputs satisfy schema and surface perf metrics.
- `b285973` — Hooked S1 into the CLI (runner + validator) so operators can invoke the tile index via `engine.cli.segment1b`.
- `969f8fa` — Enhanced the S1 runner/validator with timing + determinism receipts, reducing blind spots during smoke tests.
- `9a2657a` — Relaxed the `pyarrow` version range (`pyproject.toml`) so the expanded geospatial pipeline (S1/S2) can use 21.x features without ABI drift.

### Segment 1B S2 Tile Weights — 2025‑10‑22
- `ec4a188` — Scaffolded the multi-layer **S2 tile_weights** module (L0 loaders, L1 mass computation, L2 runner, L3 validator) and registered datasets/schemas.
- `529a491` — Added mass computation, quantisation, and observability hooks inside S2 so RNG budgets and tile totals are auditable.
- `1a1432e` — Delivered the dedicated validator plus determinism receipts for S2, tightening governance.
- `29fd13a` — Wired S2 into the CLI, enabling materialisation + validation flow through the Segment 1B entry point.
- `5047840` — Authored the first **S2 tile_weights runbook** and refreshed CLI documentation so operators know how to run/validate the new state.

### Segment 1B Orchestration & Automation — 2025‑10‑22
- `dba46dc` — Created the **Segment 1B orchestrator + CLI verbs** (`engine.cli.segment1b run|validate`) to sequence S0→S2 (initially) with consistent logging.
- `177d352` — Added `scripts/run_segment1b.py` to execute YAML-driven runs, enabling nightly smoke/regression automation.
- `dbc8bd0` — Checked in `config/runs/segment1b_nightly.yaml` and updated the S2 runbook so scheduled jobs reuse deterministic parameter sets out of the box.

### Segment 1B S3 Requirements & Runbooks — 2025‑10‑22/23
- `ce62426` — Implemented **S3 requirements** generation (candidate countries/orderings) with schema contracts and loaders.
- `73047cb` — Updated the Segment 1B CLI/orchestrator to include the new S3 requirement stage, keeping the state machine contiguous.
- `2c35718` — Authored runbooks for **S3 requirements and S4 allocation plan** so operators understand prerequisites, artefact locations, and validation steps ahead of unsealing those stages.

### Segment 1B S4 Allocation Plan — 2025‑10‑23
- `c3f85ae` — Introduced scaffolding + error handling for **S4 allocation_plan**, setting up contracts and placeholder runner behaviour.
- `2a49347` — Filled in the allocation logic for S4 and its validation harness, connecting to upstream candidate inputs.
- `8ba10d0` — Completed the first production-ready S4 implementation (runner + validator) so downstream states can consume allocation results.
- `ce35f03` — Augmented S4 with resource metrics + merchant summaries for governance review.
- `e5a739e` — Finalised Phase 7 release prep (runbook, governance guidance) for S4 to move from dev → controlled release.
- `5f743cb` — Locked in final S4 release artefacts: deterministic integerisation, conservation checks, PAT instrumentation, schema/dictionary updates, and evidence bundle references.
- `82e7c52` — Normalised `AGENTS.md` formatting to reflect the new active scope (Segment 1B Layer‑1) and keep the router consistent with the work above.

### Segment 1B S5 Site→Tile Assignment — 2025‑10‑23
- `8fb3f6a` — Scaffolded S5 (datasets, runner, validator, configs) to map merchant sites onto tiles.
- `d53ae44` — Delivered the full S5 assignment kernels/loaders + validation logic, enforcing mass/coverage rules.
- `c11bea4` — Refactored the S5 module for clarity (shared helpers, error taxonomy), cutting duplication before integration.
- `a5c3649` — Integrated S5 into the Segment 1B orchestrator/CLI/validation path so runs now progress through tile assignment deterministically.

### Segment 1B S6 Site Jitter & Geospatial Surfaces — 2025‑10‑23
- `f8084bb` — Added the **S6 site_jitter** module with RNG scaffolding and schema hooks.
- `4053a13` — Implemented the jitter kernels plus validation logic, ensuring the synthetic perturbations respect spatial envelopes.
- `abfea23` — Enhanced S6 RNG logging/validation so every jitter draw is auditable (per‑event trace + audit log).
- `59468a0` — Reworked world‑country data prep to rely on GeoDataFrames, fixing topology precision for jitter + downstream synthesis.
- `9b3e1e1` — Updated schemas/validators for S6 outputs (tile IDs, manifest fingerprints) to align with the new data prep.
- `0a4a5f2` — Raised the allowed `pyarrow` ceiling to 22.0.0 so the large GeoDataFrame payloads stay compatible.

### Segment 1B S7 Site Synthesis → S9 Validation — 2025‑10‑23
- `4cb5437` — Initialised S7 site synthesis scaffolding (runners, contracts, placeholders).
- `8ecf348` — Completed S7: synthesis kernels, validation, CLI integration, and evidence logging.
- `4bd7c9d` — Implemented **S8 site_locations egress** end-to-end (runner, validator, CLI) so the final site table is materialised.
- `801e1dd` — Hardened S8 joins (full outer) and added dedicated regression tests for site location reconciliation.
- `ca0fc43` — Built the **S9 validation** module skeleton (validator, runner, schema) for the end-state governance gate.
- `ebdee68` — Added the S9 validation runner + associated logic so final outputs emit PASS/FAIL bundles.
- `a9f5a3c` — Expanded S9 RNG validation with new negative tests (stray events, mismatch detection), richer audit logs, and manifest artefacts to secure determinism evidence.

### Operator Runbooks & Execution Guidance — 2025‑10‑24
- `837abe5` — Authored `docs/runbooks/segment1a_1b_execution.md`, covering prerequisites, CLI invocations, artefact paths, and PASS-flag expectations for running Segment 1A through 1B.
- `3c36065` — Clarified the same runbook’s state coverage, corrected Segment 1A ranges, and added output confirmation steps.
- `255578d` — Further updated the runbook with precise artefact locations (catalogues, RNG logs) so future smoke tests do not struggle to locate in-repo datasets.

### Segment 1A Run Evidence & Cleanup — 2025‑10‑25
- `81fea2b` — Checked in the full artefact set from a Segment 1A end-to-end attempt (gamma=0 incident). Includes RNG trace/audit logs, manifests, PASS/FAIL sentinels, and parquet outputs under `runs/local_layer1_regen*`, providing raw evidence for debugging.
- `951042b` — Removed stray debug/audit files from the earlier seed=7 run to keep the repo lean and avoid confusing stale evidence with current runs.

### S2 Corridor Tuning & Parameter Experiments — 2025‑10‑25
- `4d881ef` — Reworked the hurdle-training helpers (`packages/engine/src/engine/training/hurdle/**`) so dispersion fits carry MCC×channel×GDP metadata, enforce the corridor during training, and export a fresh coefficient bundle under `config/models/hurdle/exports/version=2025-10-24/...`.
- `fd92f8e` — Added MCC×channel-specific NB mean tuning to the governed coefficients, targeting stubborn rejection hotspots observed after regen6.
- `e5def3f` — Recomputed acceptance deltas using the updated deterministic context and reflashed the governed `hurdle_coefficients.yaml`.
- `d7f5d9a` — Documented (and committed) the failed dispersion uplift (α≈0.96) that spiked rejections, capturing metrics for traceability prior to rolling back.
- `f428d46` — Performed the rollback to the regen6 dispersion baseline (bypassing git‑lfs limitations by restoring from HEAD) and logged the rationale so future tuning attempts know the reference state.
- `cbc48b3` — Introduced surgical MCC×channel tweaks across the mean and dispersion coefficients, then ran `runs/local_layer1_regen9`/`regen10`, capturing full RNG/manifests despite the eventual S3 timeout.

### Operational Logging & Run Tracking — 2025‑10‑25
- `7fbfd5c` — Updated `docs/logbook/10-2025/2025-10-25.md` with regen9 metrics (ρ=0, p99=0 after hyper-targeted NB tuning) and noted the pending S3 timeout.
- `d96aa87` — Added evidence from the 90‑minute Segment 1A run (regen10) that cleared S2 and failed with `ERR_S3_SITE_SEQUENCE_OVERFLOW`, including parameter hash `06544629…` for reproducibility.
- `9e90eab` — Logged subsequent work (Segment 1B logging uplift, overflow diagnostics) so the day’s chronology stays intact.
- `86ba2cb` — Synced the governed coefficients (back to regen6 baseline) **and** enhanced the Segment 1B scenario runner logging so every state S0→S9 now emits start/finish banners and artefact pointers.
- `e29c99f` — Added explicit logging around `_enforce_site_capacity` in S3, emitting merchant/country/count before the overflow exception to remove guesswork during triage.
- `2e0d8ff` — Archived RNG logs, metrics, manifests, and numeric attestations for run `7d46f5e30d82b3bdd63d34da693a5e54`, giving auditors concrete artefacts tied to parameter hash `dcf159f5…`.
- `2e2cf0c` — Introduced deterministic runtime **guards**: S2 now clamps `n_outlets` at 999 999 with validator parity; S3 redistributes overflow and logs offending merchants before raising if headroom still exhausted. Also ensured Segment 1B state logging matches Segment 1A detail. These guards directly address the `site_order` six-digit cap while keeping totals conserved.

## Outstanding Context & Follow‑ups
- Segment 1A still needs a full rerun so the new S3 redistribution can carry the pipeline through S9 and emit the `_passed.flag` for Segment 1B reads.
- Automated tests around the S2 clamp and `_enforce_site_capacity` redistribution remain TODO (see `packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder_universe/l1/kernels.py` and `.../s2_nb_outlets/l2/runner.py`).
- The runtime clamps should be replaced with policy‑level fixes once governed MCC×channel distributions are re‑trained; the current guardrails are safe defaults documented here for lineage.
