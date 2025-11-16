# Segment 1A – Production Orchestration Notes _(non-binding)_

> This note sketches how the Layer‑1 / Segment 1A states (pre-ingestion, S0‑S4) are expected to run inside the enterprise environment once the engine is promoted. It is **conceptual only** – all contracts remain in the authoritative spec folders.

---

## 1. Run Surfaces

- **Container image:** ships the engine code + Python dependencies. No governed data is baked in; the image exposes a bootstrap script that stages artefacts and executes `python -m engine.cli.segment1a` with deterministic flags.
- **Governed artefact pack:** versioned bundle in a private object store (e.g., `s3://cw-fraud-engine/artifacts/<version>/`). Contents:
  - Reference tables required by S0 (merchant snapshot, ISO canonical table, GDP slice, bucket map, timezone polygons, etc.).
  - Policy YAMLs / numeric manifests (`policy.s3.rule_ladder.yaml`, `policy.s3.base_weight.yaml`, `policy.s3.thresholds.yaml`, `policy.s4.hyperparams.yaml`, `numeric_policy.json`, `math_profile_manifest.json`, …).
  - Checksums + manifest index so the engine can assert integrity during sealing.
- **Execution stamp:** each run logs `(seed, parameter_hash inputs, manifest_fingerprint, git_commit, cli flags)` to ensure replay.

---

## 2. State-by-State View

### Pre-ingestion staging
1. Bootstrap script fetches the requested artefact version into the container (mirrors the dataset dictionary layout under `reference/` and parameter files under `config/`).
2. Validates digests against the supplied manifest before invoking the engine.

### S0 Foundations (pre-ingestion → sealing)
- Loads the staged tables, applies schema authority, and emits parameter-scoped datasets (`crossborder_eligibility_flags`, `hurdle_design_matrix`, optional diagnostics).
- S0.8 recomputes parameter hash / manifest fingerprint and confirms they match the operator-supplied inputs.
- Validation bundle is written under `validation/parameter_hash=*/` and later folded into the run-level bundle (fingerprint partition). Operators promote both the data and `_passed.flag` atomically.

### S1 Hurdle
- Consumes S0 outputs + governed model coefficients from the artefact pack.
- Emits RNG envelopes (`rng/events/hurdle_bernoulli`) and the hurdle catalogue. Production gating requires the artefacts to share the run’s seed/parameter hash for idempotence.
- Validation (L3) drops reason metrics and catalogue entries into the bundle – consumers check the PASS flag before reading any S1 surface.

### S2 NB Outlet Sampler
- Uses the Philox lineage from S1 and the governed corridor policy to sample `nb_final` events, landing RNG logs in `logs/rng/events/{gamma,poisson,nb_final}` and deterministic outputs under `parameter_hash=`.
- Validation writes dispersion metrics + corridor attestations to the bundle. Alerts fire if corridor breaches appear.

### S3 Cross-Border Universe
- Reads the S1/S2 context plus staged policy/config artefacts. Produces:
  - `s3_candidate_set.parquet` (always),
  - optional `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence` depending on CLI toggles.
- `validate_s3_outputs` replays the deterministic kernels, enforces JSON-Schema, and writes:
  - `validation_summary.json` with aggregated metrics (schema flag, priors/counts/sequence totals, floor/ceiling usage),
  - `integerisation_diagnostics.jsonl` (per-merchant floor/ceiling/residual telemetry).
- Bundle lives under `validation_bundle/manifest_fingerprint=*/s3_crossborder_universe/`; consumers must check `_passed.flag` before reading the datasets.

### S4 ZTP Target
- Runs only for merchants that passed S1 (`is_multi`) and the S3 eligibility gate.
- Consumes:
  - S2 `nb_final` envelopes for accepted outlet counts and lineage,
  - Admissible foreign count `A` derived from the S3 candidate set,
  - Governed ZTP hyperparameters (`policy.s4.hyperparams.yaml`) and optional feature inputs (`--s4-features`).
- Emits logs only:
  - Consuming attempts in `logs/rng/events/poisson_component` (context `ztp`),
  - Non-consuming markers in `logs/rng/events/ztp_rejection`, `logs/rng/events/ztp_retry_exhausted`, `logs/rng/events/ztp_final`,
  - Cumulative trace rows in `logs/rng/trace/rng_trace_log.jsonl` (`module="1A.ztp_sampler"`).
- `validate_s4_run` replays the RNG draws, checks trace/budget discipline, and writes metrics under `validation_bundle/manifest_fingerprint=*/s4_ztp_target/`; operators can override with `--no-validate-s4` in emergency replays.
- CLI flag `--s4-validation-output` lets the run emit resumable validation artefacts before they are copied into the sealed bundle.

---

## 3. Operational Checklist

| Stage | Inputs | Key outputs | Alerting / Ops notes |
|-------|--------|-------------|----------------------|
| Pre-ingestion | Artefact pack (`s3://...`) | Staged refs + configs in container | Fail early if any checksum mismatch |
| S0 | Staged refs | Parameter-scoped tables, S0 validation bundle | Monitor `_passed.flag`; any schema drift blocks run |
| S1 | S0 outputs, hurdle params | RNG envelopes, hurdle catalogue, validation metrics | Alert on validation failure or missing RNG traces |
| S2 | S1 context, corridor policy | `nb_final` events, integer metrics | Watch corridor breaches + RNG budgets |
| S3 | S2 context, cross-border policies | Candidate set + optional priors/counts/sequence, diagnostics bundle | Check schema validation, monitor floor/ceiling hits |
| S4 | S1/S3 gates, S2 `nb_final`, S3 admissible count, ZTP hyperparams | ZTP RNG logs (`poisson`, `ztp_*`) + trace, S4 validation metrics | Alert on validation failure, missing trace rows, or exhaustion spikes |

---

## 4. Promotion & Retention

1. After a successful run the operator copies the entire output tree (`parameter_scoped/`, `logs/`, `validation_bundle/`) plus the CLI JSON summary to a long-term bucket keyed by `manifest_fingerprint`.
2. Artefact versions used for the run are recorded alongside the output (audit trail for replay).
3. Downstream services load from the promoted location (`no PASS, no read` policy enforced at the bundle).

---

## 5. Local / CI Replays

For development or CI:

1. Fetch a smaller artefact slice (e.g., “dev” pack) to the local workspace.
2. Run `python -m engine.cli.segment1a ...` inside the repo; outputs land in `./runs/dev/{parameter_hash=...}`.
3. Validate using the same bundle checks; archive the run artefacts or discard after inspection.

This matches production behaviour and ensures that every state implementation can be exercised end-to-end once its inputs are available.
