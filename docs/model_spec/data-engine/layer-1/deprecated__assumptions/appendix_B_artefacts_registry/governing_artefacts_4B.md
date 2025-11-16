Here’s the consolidated **governing artefacts** note for **4B – Validation without bullet points**, inline and in plain ASCII. It mirrors the updated 4B registry you pasted and the 4B narrative/assumptions, and it only covers governance, wiring, and checks (no re‑definitions of upstream data).

---

## Scope

Lists the governed artefacts and rules needed to audit and reproduce 4B. Cross‑layer items are referenced explicitly and not redefined.

---

## A) Cross‑layer references consumed in 4B

* **spatial\_manifest.json** → `tz_polygon_digest`
  Pins the tz‑world polygon vintage used by structural and DST checks.
* **zoneinfo\_version.yml** → `zoneinfo_digest`
  Declares the ZoneInfo build used for local‑time reconstruction and DST validation.
* **artefact\_registry.yaml**
  Active registry instance used for licence concordance.
* **validate\_licences.py** (CI)
  Licence digests are recomputed and checked against the registry mapping.
* **upload\_to\_hashgate.py** and **.github/workflows/block\_merge.yml** (CI)
  Release gate and PR block until validation\_passed is recorded for this parameter hash.
* **rng\_logging.yml**
  Rotation and retention policy for RNG traces used by 4B runs.

---

## B) Schemas and validation configs

* **transaction\_schema.json** → `mlr.4B.schema.transaction`
  Structural schema for field presence/type checks.
* **site\_catalogue.avsc** → `mlr.4B.schema.site_catalogue`
  Avro schema used to validate the site‑catalog snapshot consumed by semantic checks.
* **schemas/** (directory) → `mlr.4B.dir.schemas`
  Bundle of JSON/Avro schemas referenced by validators.
* **validation\_conf.yml** → `mlr.4B.config.validation_conf`
  Thresholds for structural, semantic, barcode, and adversarial checks.
* **barcode\_bounds.yml** → `mlr.4B.config.barcode_bounds`
  Allowable barcode slope band for offset‑barcode validation.
* **country\_zone\_alphas.yaml** → `mlr.4A.config.country_zone_alphas` (cross‑layer)
  Dirichlet hyper‑parameters for zone‑share audits, referenced by 4B where needed.
* **footfall\_coefficients.yaml** → `mlr.4A.config.footfall_coefficients` (cross‑layer)
  Parameters and dispersion targets for footfall GLM checks.

---

## C) Validation runners and models

* **semantic\_glm.py** → `mlr.4B.script.semantic_glm`
  GLM implementation for semantic congruence on footfall‑based features.
* **barcode.py** → `mlr.4B.script.barcode`
  Builds the UTC‑hour vs offset matrix and evaluates slope against bounds.
* **adv\_embed.embed\_6d** → `mlr.4B.model.adv_embed`
  Trained 6‑D embedder used by adversarial tests.
* **adversarial\_xgb.py** (CI) → `mlr.4B.ci.adversarial_xgb`
  Single‑round classifier runner with fixed seed and hyper‑parameters.
* **real\_reference\_slice.parquet** → `mlr.4B.data.real_reference_slice`
  GDPR‑sanitised reference slice for adversarial comparisons.

---

## D) Validation inputs and outputs

* **site\_catalog.parquet** → `mlr.4B.data.site_catalog`
  Snapshot used for end‑to‑end semantic checks; validated against site\_catalogue.avsc.
* **structural\_failure\_{parameter\_hash}.parquet** → `mlr.4B.data.structural_failure`
  Rows failing structural/schema checks; includes repro context.
* **barcode\_failure\_{merchant\_id}.png** → `mlr.4B.img.barcode_failure`
  Heat‑map with overlay when barcode slope breaches bounds.
* **auroc\_failure\_{parameter\_hash}.png** → `mlr.4B.img.auroc_failure`
  Plot emitted when adversarial AUROC exceeds the configured cut.
* **rng\_trace.log** → `mlr.4B.log.rng_trace`
  Trace of sub‑stream jumps during validation runs (rotation/retention governed by rng\_logging.yml).
* **validation/{parameter\_hash}/** → `mlr.4B.dir.validation_bundle`
  Directory bundling all 4B validation outputs for the run.

---

## E) Infra and registry governance

* **datasets.sql** → `mlr.4B.schema.dataset_catalog`
  DDL for the registry that enforces uniqueness of (parameter\_hash, seed, path).
* **nfs\_read\_only.yml** → `mlr.4B.config.nfs_read_only_mount`
  Read‑only mount policy for published validation outputs (immutability).

---

## F) CI and audit rules (make these explicit)

1. **Schema lock**

   * All structural checks use `transaction_schema.json`.
   * `site_catalog.parquet` must validate against `site_catalogue.avsc`.
     Changes require schema digest update.
2. **Spatial/time provenance**

   * tz‑world vintage must match `spatial_manifest.json` (`tz_polygon_digest`).
   * Local time and DST checks must match `zoneinfo_version.yml` (`zoneinfo_digest`).
3. **Barcode slope gate**

   * `barcode.py` must use `barcode_bounds.yml`; breach emits `barcode_failure_*.png` and fails CI.
4. **Semantic congruence gate**

   * `semantic_glm.py` must use `footfall_coefficients.yaml`; dispersion or fit breaches fail CI and produce diagnostics.
5. **Adversarial AUROC gate**

   * `adversarial_xgb.py` must use `adv_embed.embed_6d`, `validation_conf.yml`, and `real_reference_slice.parquet`.
   * AUROC above the configured cut fails CI and emits `auroc_failure_*.png`.
6. **RNG observability**

   * `rng_trace.log` is emitted under the 4B run; rotation/retention per `rng_logging.yml`.
7. **Licence concordance**

   * `validate_licences.py` must succeed against the active `artefact_registry.yaml` before release.
8. **Release gating**

   * `upload_to_hashgate.py` posts the bundle and validation\_passed flag;
     `.github/workflows/block_merge.yml` blocks merge until the gate reports success.
9. **Immutability**

   * Validation bundle path is mounted read‑only via `nfs_read_only.yml`; attempts to mutate must fail.

---

## Table

| Governing artefact ID       | Path / pattern                                           | Role (one‑liner)                                        | Provenance / digest key         |
|-----------------------------|----------------------------------------------------------|---------------------------------------------------------|---------------------------------|
| synthetic_partition_pattern | output/transactions/partition_date=*/batch_*.parquet     | Pattern for all synthetic txn partitions to validate    | partition_pattern_digest        |
| real_reference_slice        | data/reference/real_reference_slice.parquet              | GDPR‑sanitised real txn slice for adversarial AUROC     | real_reference_slice_digest     |
| tz_polygon_digest           | artefacts/manifests/tz_polygon_digest.txt                | Vintage hash of tz‑world polygons for coord legality    | tz_polygon_digest               |
| zoneinfo_digest             | artefacts/manifests/zoneinfo_digest.txt                  | ZoneInfo build hash for DST legality checks             | zoneinfo_digest                 |
| transaction_schema_json     | schema/transaction_schema.json                           | JSON Schema for structural validation                   | transaction_schema_digest       |
| validation_conf_yml         | config/validation/validation_conf.yml                    | AUROC cut‑line & general validator thresholds           | validation_conf_digest          |
| barcode_bounds_yml          | config/validation/barcode_bounds.yml                     | Acceptable slope corridor for barcode test              | barcode_bounds_digest           |
| adv_embed_py                | src/validation/adv_embed.py                              | 6‑D embedder for adversarial validation                 | git_tree_hash                   |
| validator_runner_py         | src/validation/validator_runner.py                       | Orchestrates all 4B validation checks                   | git_tree_hash                   |
| validation_report_parquet   | artefacts/validation/validation_report_{run_id}.parquet  | Row‑per‑metric table (slope, AUROC, null‑share, ...)    | validation_report_digest        |
| barcode_slope_metrics_json  | artefacts/validation/barcode_slope_metrics_{run_id}.json | JSON metrics for barcode slope test                     | barcode_slope_digest            |
| adv_auroc_metrics_json      | artefacts/validation/adv_auroc_metrics_{run_id}.json     | JSON metrics for adversarial AUROC                      | auroc_metrics_digest            |
| barcode_heatmap_png         | artefacts/validation/barcode_heatmap_{run_id}.png        | QC heat‑map of barcode slope band                       | barcode_heatmap_digest          |
| validator_manifest          | artefacts/manifests/validator_manifest_{run_id}.json     | Digest bundle of inputs, configs, metrics               | validator_manifest_digest       |
| validator_audit_log         | logs/validation/{run_id}/validator_audit.log             | Structured log of per‑check pass/fail                   | (run‑specific)                  |
| validation_ci_test_py       | ci/tests/validation_ci_test.py                           | CI guard: metrics must match expected corridor          | git_tree_hash                   |
| expected_metrics_yaml       | config/validation/expected_metrics.yaml                 | Target values & tolerances for CI regression            | expected_metrics_digest         |
| snap_diff_py                | tools/snap_diff.py                                       | Diffs current metrics vs previous snapshot              | git_tree_hash                   |
| validator_dockerfile_lock   | Dockerfile.validator.lock                                | Locks validator container base & layer digests          | validator_dockerfile_digest     |
| validator_build_manifest    | artefacts/manifests/validator_build.manifest             | Roll‑up of validator code, configs, container hash      | validator_build_manifest_digest |
| validator_rng_trace_log     | logs/validation/{run_id}/validator_rng_trace.log         | Philox key+counter trace for 4B run                     | (run‑specific)                  |
| rng_logging_policy          | config/rng/rng_logging.yml                              | Cross‑layer policy enabling RNG traces (shared with 4A) | rng_logging_digest              |
| ValidationDriftError        | exception (contract)                                     | Thrown when any metric exceeds tolerance corridor       | n/a                             |
| BarcodeSlopeError           | exception (contract)                                     | Thrown when barcode slope falls outside bounds          | n/a                             |
| AUROCThresholdError         | exception (contract)                                     | Thrown when adversarial AUROC exceeds cut‑line          | n/a                             |
