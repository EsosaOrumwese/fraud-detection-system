# Segment 1A → 1B End-to-End Execution Runbook

This runbook documents every step required to reproduce a full Layer‑1 execution from Segment 1A through Segment 1B (States S0–S9). It assumes you are operating locally with direct access to the repository.

---

## 1. Environment Preparation

1. **Python toolchain**
   - Ensure Python 3.12+ is available.
   - Install project dependencies: `poetry install` (preferred) or `pip install -r requirements.txt` if the project’s package manager differs.

2. **Repository sanity checks**
   - `git status` should be clean or only contain intentional changes.
   - Optional smoke: `python3 -m pytest tests/engine/layers/l1/seg_1B/s9_validation/test_runner.py`.

3. **Working directories**
   - Choose a data root (e.g. `runs/local_layer1`); the CLI tools will create the 1A and 1B partitions beneath it.
   - Create `runs/local_layer1` if it does not exist.

4. **Artefact locations**
   - Identify the governed inputs for Segment 1A:
     - Merchant ingress parquet: `reference/layer1/transaction_schema_merchant_ids/v2025-10-09/transaction_schema_merchant_ids.parquet` (prior snapshots available in the same directory if you need to align with older manifests).
    - ISO canonical table: `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`.
     - GDP tables: `reference/economic/world_bank_gdp_per_capita/2025-10-07/gdp.parquet`.
     - GDP bucket map: `reference/economic/gdp_bucket_map/2025-10-08/gdp_bucket_map.parquet`.
     - Policy YAMLs: `contracts/policies/l1/seg_1A/policy.s3.rule_ladder.yaml`, `contracts/policies/l1/seg_1A/policy.s3.base_weight.yaml`, `contracts/policies/l1/seg_1A/policy.s3.thresholds.yaml`.
     - Bounds policy: `contracts/policies/l1/seg_1A/policy.s3.bounds.yaml` (per-country caps feeding the bounded Hamilton redistribution).
     - Hurdle/NB-mean coefficients (sealed): `config/models/hurdle/exports/version=2025-10-09/20251009T120000Z/hurdle_coefficients.yaml`.
     - NB dispersion coefficients (regenerated corridor-safe fit): `config/models/hurdle/exports/version=2025-10-24/20251024T234923Z/nb_dispersion_coefficients.yaml`.
     - Validation policy: `contracts/policies/l1/seg_1A/s2_validation_policy.yaml`.
     - Numeric policy attestations from the latest S0 run: `artefacts/s0_runs/2025-10-09_synthetic/validation_bundle/manifest_fingerprint=991c57a380d81d7ab9ba4901efb0d0db3eb7a82af59249d7cc71017126622709/numeric_policy_attest.json`.
   - Confirm Segment 1B shared artefacts (spatial priors, jitter policy) exist under the paths referenced by `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`, notably:
     - Dataset dictionary: `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`.
     - Spatial priors: `artefacts/spatial/population_raster/2025/raw/global_2020_1km_UNadj_uncounstrained.tif` and `artefacts/spatial/world_countries/raw/countries.geojson`.
     - Latest S0 validation bundle PASS flag: `artefacts/s0_runs/2025-10-09_synthetic/validation_bundle/manifest_fingerprint=991c57a380d81d7ab9ba4901efb0d0db3eb7a82af59249d7cc71017126622709/_passed.flag`.

---

## 2. Segment 1A Execution (States S0–S8 + S9 Validation)

1. **Select identities**
   - Decide on a Philox seed (unsigned 64-bit integer).
   - Record the git commit SHA representing the code artefacts.

2. **Run the CLI**
   - Command template:
     ```bash
     python -m engine.cli.segment1a \
       --output-dir runs/local_layer1 \
       --merchant-table <path_to_merchant_parquet> \
       --iso-table <path_to_iso_parquet> \
       --gdp-table <path_to_gdp_parquet> \
       --bucket-table <path_to_bucket_parquet> \
       --param policy.s3.rule_ladder.yaml=<path> \
       --param ... (repeat per governed artefact) \
       --git-commit <commit_sha> \
       --seed <seed_uint64> \
       --validation-policy contracts/policies/l1/seg_1A/s2_validation_policy.yaml \
       [--numeric-policy <path>] \
       [--math-profile <path>] \
       [--extra-manifest <path> ...] \
       [--s3-priors] [--s3-integerisation] [--s3-sequencing] (as required)
     ```

3. **Capture outputs**
   - The CLI prints the `parameter_hash` and `manifest_fingerprint`; copy these values, they are required by Segment 1B.
   - Confirm State S8 egress and S9 validation artefacts:
     - S8 `outlet_catalogue`: `data/layer1/1A/outlet_catalogue/seed=<seed>/fingerprint=<fingerprint>/...`
     - S9 validation bundle: `data/layer1/1A/validation/fingerprint=<fingerprint>/_passed.flag`

4. **Sanity verification**
   - Optional: run `python3 -m pytest tests/contracts/test_seg_1A_dictionary_schemas.py` to ensure 1A outputs meet contract shape expectations.

---

## 3. Segment 1B Execution (States S0–S9)

1. **Ensure gate prerequisites**
   - The `_passed.flag` from Segment 1A must be present; do not skip S0 unless you plan to re-compute the check manually.

2. **Prepare command**
   - Use the `parameter_hash`, `manifest_fingerprint`, and `seed` identified in Segment 1A.
   - Command template:
     ```bash
     python -m engine.cli.segment1b run \
       --data-root runs/local_layer1 \
       --parameter-hash <parameter_hash_from_1A> \
       --manifest-fingerprint <manifest_fingerprint_from_1A> \
       --seed <seed_uint64> \
       [--dictionary contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml] \
       [--basis population|area_m2|uniform] \
       [--dp <int>] \
       [--skip-s0] (only with verified PASS flag)
     ```

3. **Result inspection**
   - Capture the CLI summary; it reports the S9 bundle, stage logs, and any failure codes.
   - Verify presence of `data/layer1/1B/validation/fingerprint=<fingerprint>/_passed.flag`.

4. **Manual validation (optional)**
   - ```bash
     python -m engine.cli.segment1b validate-s9 \
       --data-root runs/local_layer1 \
       --parameter-hash <parameter_hash> \
       --manifest-fingerprint <manifest_fingerprint> \
       --seed <seed_uint64> \
       --run-id <s6_run_id>
     ```
   - The command re-runs S9 and returns a JSON payload; expect `"passed": true`.

---

## 4. Post-run Checks and Artefact Recording

1. **Bundle hashes**
   - Record the `_passed.flag` digest for auditing.

2. **Stage logs**
   - Segment 1B writes a log at `logs/stages/s9_validation/segment_1B/S9_STAGES.jsonl`; review for timing and status diagnostics.

3. **Contract sanity**
   - Optional targeted tests:
     ```bash
     python3 -m pytest tests/engine/layers/l1/seg_1B/s9_validation/test_runner.py
     ```

4. **Archival**
   - If the run is canonical, archive `validation/`, `site_locations/`, and RNG logs according to governance policy.

---

## 5. Troubleshooting Notes

| Symptom | Action |
| --- | --- |
| S0 fails with `No PASS → no read` | Check 1A `_passed.flag`, recompute Segment 1A or update `--validation-bundle` path. |
| S9 fails with `E904` | Schema mismatch in `site_locations`; re-run Segment 1B states or inspect intermediate outputs `s7_site_synthesis`. |
| S9 fails with `E907_RNG_BUDGET_OR_COUNTERS` | Inspect RNG events/trace/audit logs under `logs/rng/...`; run `segment1b validate-s9` for detailed failure context. |
| Bundle missing | confirm the CLI command included the correct `--parameter-hash`/`--manifest-fingerprint` and that S8 ran successfully. |

---

## 6. Execution Log (this session)

- Prepared runbook describing environment requirements, command templates, and validation steps for Segment 1A through Segment 1B.
- No orchestration commands were executed; this document serves as the authoritative procedure for operators to follow when running the pipeline locally.
