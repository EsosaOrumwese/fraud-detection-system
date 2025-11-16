Here’s the consolidated **governing artefacts** note for **4A – Reproducibility and configurability**, inline and in plain ASCII. It mirrors your 4A registry you just linted and your 4A narrative/assumptions, and it sticks to scope (governance, wiring, and checks only).

---

## Scope

Lists only the governed artefacts and rules needed to audit and reproduce sub‑segment 4A. No cross‑layer producers are introduced; items are internal to 4A unless marked otherwise.

---

## A) Container and build provenance

* **Dockerfile.lock** -> pins the base image digest for reproducible builds.
* **pipeline\_launcher.sh** -> initializes the run, writes the first lines of the per‑run build manifest (container digest, hostname, UTC start).
* **validate\_container\_hash.yml** (CI) -> verifies the built image matches Dockerfile.lock before any data generation.
* **build.manifest** -> per‑run manifest that accumulates all digests (git tree, container, configs, schemas) so auditors have a single entry point.

---

## B) Registry, schema, loader, and diff

* **artefact\_registry.schema.json** -> JSON Schema that defines the shape of registry files.
* **artefact\_registry.yaml** -> live registry instance the loader uses; every path and its manifest\_key are governed.
* **artefact\_loader.py** -> reads artefact\_registry.yaml, computes SHA‑256 for each file, and appends entries to build.manifest.
* **compare\_registry.py** (CI) -> re‑enumerates the registry and byte‑compares against build.manifest to detect path or ordering drift.
* **schemas/** (directory) -> bundle of JSON/Avro schemas referenced by downstream checks.

---

## C) Source code immutability

* **git tree hash** -> exported to build.manifest (source\_sha1 or equivalent).
* **code hash embed** (e.g., **codehash** in package init) -> must equal the git tree hash at runtime.
* **SourceHashMismatchError** (exception) -> raised if embedded code hash and manifest code hash differ.

---

## D) RNG governance and replay

* **rng\_logging.yml** -> logging policy (rotation, retention) for RNG traces.
* **rng\_trace.log** -> audit trail of Philox jumps; records module, identifier, and counter offset for exact replay.
* **replay\_rng.py** (CI/runtime) -> reconstructs RNG state from rng\_trace.log and spot‑checks draws for determinism.

---

## E) Time and timezone provenance

* **zoneinfo\_version.yml** -> declares the IANA/zoneinfo build version used by checks and by DST tests.
* **firewall.py** -> structural and semantic invariant checks over generated datasets; depends on build.manifest and zoneinfo\_version.yml.
* **failure\_reproducer.py** -> emits a local reproducer with the failing row and RNG offset when the firewall trips.

---

## F) Validation harnesses (statistical and structural)

* **country\_zone\_alphas.yaml** -> Dirichlet alpha inputs for share audits.
* **geo\_audit.py** (CI) -> posterior share checks by country and tzid using country\_zone\_alphas.yaml.
* **hurdle\_coefficients.yaml** -> parameters for outlet‑count bootstrap.
* **outlet\_bootstrap\_harness.py** (CI) -> bootstrap envelopes for outlet counts; emits diagnostics on breach.
* **footfall\_coefficients.yaml** -> parameters and dispersion thresholds for footfall intensity checks.
* **footfall\_glm\_harness.py** (CI) -> Poisson GLM dispersion band checks for hourly intensity.
* **adversarial\_xgb.py** (CI) -> indistinguishability test; AUROC gate over a fixed sample and seed.
* **dst\_edge\_passer.py** (CI) -> minute‑wise DST transition checks against zoneinfo version.
* **dst\_failures.csv** -> failure table written by dst\_edge\_passer for post‑mortem.

---

## G) Dataset registry and collision prevention

* **dataset\_catalog.ddl.sql** -> catalog DDL with uniqueness constraints on (parameter\_hash, seed).
* **register\_dataset.py** (CI) -> writes (parameter\_hash, seed, path) to the catalog; uniqueness violation blocks publish.

---

## H) Licensing and immutability

* **LICENSES/** (directory) -> SPDX texts referenced by the registry’s license mapping.
* **validate\_licences.py** (CI) -> verifies mapped artefacts have the expected licence texts and digests.
* **nfs\_export\_policy.md** -> read‑only export/mount policy that locks published datasets against mutation.

---

## I) Release gating

* **upload\_to\_hashgate.py** -> posts build.manifest, validation\_passed flag, and bundle URL to the internal gate.
* **.github/workflows/block\_merge.yml** -> blocks merge until the gate reports validation\_passed=true for the parameter hash.

---

## J) CI and audit rules (make these explicit)

1. **Manifest completeness**: build.manifest must include the digests for all items enumerated in artefact\_registry.yaml during the run.
2. **Registry vs manifest**: compare\_registry.py must pass; any mismatch in ordering, path set, or digest fails CI.
3. **Schema lock**: data files validated in this sub‑segment must use schemas from schemas/ or those referenced by registry entries; schema changes require a schema digest change.
4. **RNG replayability**: rng\_trace.log is mandatory in runs that generate randomness; replay\_rng.py must reproduce spot‑check draws.
5. **Time and tz provenance**: firewall.py must validate tzid membership and DST behavior using zoneinfo\_version.yml; any failure produces failure\_reproducer.py and fails CI.
6. **Statistical gates**: geo\_audit, outlet\_bootstrap\_harness, footfall\_glm\_harness, dst\_edge\_passer, and adversarial\_xgb must pass with their configured thresholds.
7. **Licensing**: validate\_licences.py must succeed against LICENSES/ and the license\_map in artefact\_registry.yaml.
8. **Immutability**: published dataset paths are mounted read‑only; attempts to overwrite must error and require a version bump.
9. **Release**: block\_merge.yml must observe validation\_passed=true from upload\_to\_hashgate.py before merge.

---

## New in this revision

* Split of registry into schema (artefact\_registry.schema.json) and instance (artefact\_registry.yaml).
* rng\_trace.log with rng\_logging.yml and replay\_rng.py wired to CI.
* zoneinfo\_version.yml dependency added to firewall.py and DST checks.
* Registration of validation harnesses and their coefficient/config inputs.
* Dataset catalog DDL registered; register\_dataset wired to it.
* Licence directory and CI licence validation scripted.
* Upload and gate workflow registered end‑to‑end.

## Table
The table keeps the same four‑column convention you use for 1A → 3B.


| Governing artefact ID        | Path / pattern                                        | Role (one‑liner)                                           | Provenance / digest key        |
|------------------------------|-------------------------------------------------------|------------------------------------------------------------|--------------------------------|
| Dockerfile.lock              | Dockerfile.lock                                       | Pins base‑image & layer digests for reproducible container | dockerfile_lock_digest         |
| pipeline_launcher.sh         | ci/pipeline_launcher.sh                               | Kicks off run & writes initial build.manifest              | git_tree_hash                  |
| validate_container_hash CI   | config/ci/validate_container_hash.yml                | Asserts built image digest == Dockerfile.lock              | validate_container_hash_digest |
| build.manifest               | artefacts/manifests/build.manifest                    | Per‑run roll‑up of all digests (code, configs, outputs)    | build_manifest_digest          |
| artefact_registry_schema     | config/registry/artefact_registry.schema.json        | JSON Schema for registry files                             | registry_schema_digest         |
| artefact_registry.yaml       | config/registry/artefact_registry.yaml               | Live registry instance (validated at runtime)              | registry_yaml_digest           |
| schemas/ bundle              | schemas/                                              | All domain schemas (transaction, outlet, etc.)             | schemas_dir_digest             |
| artefact_loader.py           | src/registry/artefact_loader.py                       | Loads registry, validates & hashes artefacts               | git_tree_hash                  |
| compare_registry.py          | src/registry/compare_registry.py                      | Diffs registry vs build.manifest in CI                     | git_tree_hash                  |
| register_dataset.sh          | scripts/register_dataset.sh                           | Helper to append dataset entries & re‑hash registry        | git_tree_hash                  |
| dataset_catalog_ddl.sql      | db/dataset_catalog.ddl.sql                            | Postgres DDL mapping manifest_key → storage_uri            | dataset_catalog_digest         |
| rng_logging_policy           | config/rng/rng_logging.yml                           | Enables Philox counter dumps (size budget)                 | rng_logging_digest             |
| global_rng_trace.log         | logs/rng/{run_id}/global_rng_trace.log                | Full Philox key+counter trace                              | (run‑specific)                 |
| replay_rng.py                | tools/replay_rng.py                                   | Replays RNG trace for determinism audit                    | git_tree_hash                  |
| zoneinfo_version.yml         | config/runtime/zoneinfo_version.yml                  | Pins IANA tzdata/ICU build                                 | zoneinfo_version_digest        |
| firewall_rules               | config/infra/firewall.yml                            | Ingress allow / egress deny list for workers               | firewall_digest                |
| nfs_export_policy.md         | docs/infra/nfs_export_policy.md                       | Human contract for read‑only NFS exports                   | nfs_export_policy_digest       |
| failure_reproducer.py        | tools/failure_reproducer.py                           | Generates local reproducer from failing RNG/state          | git_tree_hash                  |
| geo_audit.py                 | tools/geo_audit.py                                    | Scans outputs for impossible lat/lon coordinates           | git_tree_hash                  |
| hurdle_coefficients.yaml     | config/models/hurdle_coefficients.yaml                | θ & dispersion for hurdle NB (cross‑layer)                 | hurdle_coeff_digest            |
| footfall_coefficients.yaml   | config/models/footfall_coefficients.yaml              | GLM footfall coefficients (cross‑layer)                    | footfall_coeff_digest          |
| footfall_glm_harness.py      | src/ds/footfall_glm_harness.py                        | Predicts F_i for QC using footfall GLM                     | git_tree_hash                  |
| adversarial_xgb.pkl          | artefacts/models/adversarial_xgb.pkl                  | XGBoost model for indistinguishability audit               | adversarial_xgb_digest         |
| dst_edge_passer.py           | tests/dst_edge_passer.py                              | Replays DST folds/gaps → asserts no TZ lookup error        | git_tree_hash                  |
| dst_failures.csv             | artefacts/fixtures/dst_failures.csv                   | Historical DST failure cases for regression                | dst_failures_digest            |
| licences/ directory          | LICENSES/                                             | All third‑party licence texts                              | licences_dir_digest            |
| validate_licences.py         | ci/tests/validate_licences.py                         | CI check: every external artefact has licence & digest     | git_tree_hash                  |
| upload_to_hashgate.sh        | scripts/deploy/upload_to_hashgate.sh                  | Uploads build.manifest to notarisation service             | git_tree_hash                  |
| block_merge.yaml             | config/ci/block_merge.yaml                           | GH action blocking merge until Hashgate receipt            | block_merge_digest             |
| edge_sampler_metrics         | artefacts/metrics/edge_sampler_{run_id}.parquet       | Perf budget metrics for edge sampler (cross‑segment)       | (run‑specific)                 |
| performance_config           | config/routing/performance.yml                       | Throughput & memory SLA thresholds (cross‑layer)           | perf_config_digest             |
| site_catalogue (ref)         | artefacts/catalogue/site_catalogue.parquet            | Cross‑layer site catalogue for GLM harness                 | site_catalogue_digest          |
| allocation_licences_manifest | artefacts/manifests/allocation_licences_manifest.json | Licence roll‑up from segment 3A                            | allocation_licences_digest     |
| VirtualUniverseMismatchError | exception (contract)                                  | Thrown when universe hash ≠ replay hash                    | n/a                            |
| VirtualEdgeSamplingError     | exception (contract)                                  | Thrown when HRSL sampling fails threshold                  | n/a                            |
| SourceHashMismatchError      | exception (contract)                                  | Thrown when embedded code hash ≠ git tree hash             | n/a                            |
