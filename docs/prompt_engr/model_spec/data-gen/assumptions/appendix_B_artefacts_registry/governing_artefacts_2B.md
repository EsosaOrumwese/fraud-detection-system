## Subsegment 2B: Routing transactions through sites

| ID / Key                   | Path Pattern                                                   | Role                                                            | Semver Field    | Digest Field               |
|----------------------------|----------------------------------------------------------------|-----------------------------------------------------------------|-----------------|----------------------------|
| **site_catalogue_parquet** | `artefacts/catalogue/site_catalogue.parquet`                   | Foot‑traffic weights for all sites                              | `semver`        | `site_catalogue_digest`    |
| **routing_manifest**       | `artefacts/routing/routing_manifest.json`                      | Manifest of all routing artefacts and their digests             | `semver`        | `routing_manifest_digest`  |
| **routing_day_effect**     | `config/routing/routing_day_effect.yml`                        | Corporate‑day variance parameter σ²                             | `semver`        | `gamma_variance_digest`    |
| **cdn_country_weights**    | `config/routing/cdn_country_weights.yaml`                      | Edge‑node country weight vector for virtual merchants           | `semver`        | `cdn_alias_digest`         |
| **routing_validation**     | `config/routing/routing_validation.yml`                        | Validation thresholds (`tolerance_share`, `target_correlation`) | `semver`        | `validation_config_digest` |
| **logging_config**         | `config/routing/logging.yml`                                   | Audit‑log path, rotation and retention policy                   | `semver`        | `audit_log_config_digest`  |
| **rng_policy**             | `config/routing/rng_policy.yml`                                | RNG seed derivation policy (SHA‑1 usage)                        | `semver`        | `rng_policy_digest`        |
| **rng_proof**              | `docs/rng_proof.md`                                            | Formal proof of RNG stream isolation                            | Git commit ref  | `rng_proof_digest`         |
| **pweights_bin**           | `<merchant_id>_pweights.bin`                                   | Little‑endian `float64` weight vectors per merchant             | n/a             | `weight_digest`            |
| **alias_npz**              | `<merchant_id>_alias.npz`                                      | Uncompressed NumPy arrays (`prob`, `alias`) for alias sampling  | n/a             | `alias_digest`             |
| **cdn_alias_npz**          | `<merchant_id>_cdn_alias.npz`                                  | Uncompressed NumPy arrays (`prob`, `alias`) for CDN sampling    | n/a             | `cdn_alias_digest`         |
| **errors_config**          | `config/routing/errors.yml`                                    | Exception definitions (`RoutingZeroWeightError`, etc.)          | `semver`        | `errors_config_digest`     |
| **performance_config**     | `config/routing/performance.yml`                               | Throughput and memory SLA thresholds                            | `semver`        | `perf_config_digest`       |
| **routing_audit_log**      | `logs/routing/routing_audit.log`                               | Batch-level audit checksums & errors                            | `semver`        | (run-specific)             |
| **routing_validation_log** | `logs/routing/validation.log`                                  | Nightly share & correlation validation results                  | `semver`        | (run-specific)             |
| **output_buffer**          | `output/buffer/partition_date=*/merchant_id=*/batch_*.parquet` | Per-batch routed-txn buffer incl. γ-fields                      | `semver`        | `routing_manifest_digest`    |


**Notes:**

* The binary files (`.bin`, `.npz`) do not carry semver in sidecars; their paths and digest keys are sufficient for build‑time governance.
* Replace `<merchant_id>` with the zero‑padded site code for each merchant.
* Any addition, removal, or version change of these artefacts must follow semver rules and will automatically refresh the manifest digest via CI.
* All paths use Unix‑style forward slashes and are case‑sensitive.

---
Here is the **fully expanded integration for the Governing Artefacts Appendix (2B)**, closing all governance, output, and contract gaps identified from your narrative/assumptions.
You can **add these rows and enforcement notes directly below your current table and notes**.

---

### Additional Governed Artefacts and Enforcement for Subsegment 2B

#### A. Output, Audit, and Validation Artefacts

| ID / Key                      | Path Pattern                                                   | Role                                                                                                                      | Semver Field    | Digest Field              |
|-------------------------------|----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|-----------------|---------------------------|
| **routing_audit_log**       | `logs/routing/routing_audit.log`                               | Batch-by-batch audit log (checksum, counts, errors, manifest lineage)                                                     | Manifest semver | (run-specific)            |
| **routing_validation_log**  | `logs/routing/validation.log`                                  | Nightly validation results, assertion outcomes, correlation and share checks                                              | Manifest semver | (run-specific)            |
| **routing_error_log**       | `logs/routing/errors.log`                                      | Structured error log for runtime failures, zero-weight, OOM, assertion breaches, manifest drift                           | Manifest semver | (run-specific)            |
| **output_buffer**            | `output/buffer/partition_date=*/merchant_id=*/batch_*.parquet` | Site-level/txn-level buffer, includes hidden columns (`gamma_id`, `gamma_value`, `ip_country_code` for virtual merchants) | Manifest semver | routing_manifest_digest |
| **output_catalogue_schema** | `output/catalogue_schema.json`                                 | JSON schema for all outputs (buffer, catalogue), all governed fields/columns                                              | schema_version | sha256_digest            |
| **LICENSES**                  | `LICENSES/`                                                    | All licences for YAML/data files; each with SHA-256, referenced in routing_manifest                                      | Manifest semver | per-file sha256           |

#### B. Manifest and Build Contracts

* **Manifest Enforcement:**
  `routing_manifest.json` must include every governed artefact above (inputs, configs, logs, outputs, schemas, licences).

  * Any addition, removal, or semver/digest drift aborts the build and triggers manifest refresh.
  * All outputs and logs must record `routing_manifest_digest`.

* **Audit/Validation Log Enforcement:**

  * Every batch must append an audit event with the fields in A.13 (mathematics appendix).
  * Validation log must show assertion results; failures abort the build.

* **Error Log and Exception Handling:**

  * All runtime errors, assertion failures, and CI aborts must be captured in `routing_error_log`.
  * Error logs must be unique and ordered per batch or event.

* **Output Buffer and Schema Contract:**

  * All per-site, per-batch output buffers must be governed artefacts, must carry full schema, and must be explicitly versioned.
  * Hidden columns required by the router (e.g., `gamma_id`, `gamma_value`, `ip_country_code`) must be listed in `output_catalogue_schema`.

* **Licencing:**

  * Every YAML/config/data file must have a tracked, digest-verified licence in `LICENSES/`, referenced in the manifest.

---
