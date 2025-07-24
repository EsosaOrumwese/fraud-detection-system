## Subsegment 2B: Routing transactions through sites

| ID / Key                     | Path Pattern                                 | Role                                                            | Semver Field   | Digest Field               |
| ---------------------------- | -------------------------------------------- | --------------------------------------------------------------- | -------------- | -------------------------- |
| **site\_catalogue\_parquet** | `artefacts/catalogue/site_catalogue.parquet` | Foot‑traffic weights for all sites                              | `semver`       | `site_catalogue_digest`    |
| **routing\_manifest**        | `artefacts/routing/routing_manifest.json`    | Manifest of all routing artefacts and their digests             | `semver`       | `routing_manifest_digest`  |
| **routing\_day\_effect**     | `config/routing/routing_day_effect.yml`      | Corporate‑day variance parameter σ²                             | `semver`       | `gamma_variance_digest`    |
| **cdn\_country\_weights**    | `config/routing/cdn_country_weights.yaml`    | Edge‑node country weight vector for virtual merchants           | `semver`       | `cdn_alias_digest`         |
| **routing\_validation**      | `config/routing/routing_validation.yml`      | Validation thresholds (`tolerance_share`, `target_correlation`) | `semver`       | `validation_config_digest` |
| **logging\_config**          | `config/routing/logging.yml`                 | Audit‑log path, rotation and retention policy                   | `semver`       | `audit_log_config_digest`  |
| **rng\_policy**              | `config/routing/rng_policy.yml`              | RNG seed derivation policy (SHA‑1 usage)                        | `semver`       | `rng_policy_digest`        |
| **rng\_proof**               | `docs/rng_proof.md`                          | Formal proof of RNG stream isolation                            | Git commit ref | `rng_proof_digest`         |
| **pweights\_bin**            | `<merchant_id>_pweights.bin`                 | Little‑endian `float64` weight vectors per merchant             | n/a            | `weight_digest`            |
| **alias\_npz**               | `<merchant_id>_alias.npz`                    | Uncompressed NumPy arrays (`prob`, `alias`) for alias sampling  | n/a            | `alias_digest`             |
| **cdn\_alias\_npz**          | `<merchant_id>_cdn_alias.npz`                | Uncompressed NumPy arrays (`prob`, `alias`) for CDN sampling    | n/a            | `cdn_alias_digest`         |
| **errors\_config**           | `config/routing/errors.yml`                  | Exception definitions (`RoutingZeroWeightError`, etc.)          | `semver`       | `errors_config_digest`     |
| **performance\_config**      | `config/routing/performance.yml`             | Throughput and memory SLA thresholds                            | `semver`       | `perf_config_digest`       |

**Notes:**

* The binary files (`.bin`, `.npz`) do not carry semver in sidecars; their paths and digest keys are sufficient for build‑time governance.
* Replace `<merchant_id>` with the zero‑padded site code for each merchant.
* Any addition, removal, or version change of these artefacts must follow semver rules and will automatically refresh the manifest digest via CI.
* All paths use Unix‑style forward slashes and are case‑sensitive.
