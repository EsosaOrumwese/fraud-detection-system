## Subsegment 3A: Capturing cross-zone merchants (Integrated Registry)

| ID / Key                       | Path Pattern                                                  | Role                                                                      | Semver Field    | Digest Field                   |
|--------------------------------|---------------------------------------------------------------|---------------------------------------------------------------------------|-----------------|--------------------------------|
| **zone_mixture_policy**        | `config/allocation/zone_mixture_policy.yml`                   | Attention-threshold θ for escalation queue                                | `semver`        | `theta_digest`                 |
| **country_zone_alphas**        | `config/allocation/country_zone_alphas.yaml`                  | Dirichlet concentration parameters α per ISO country→TZID                 | `semver`        | `zone_alpha_digest`            |
| **rounding_spec**              | `docs/round_ints.md`                                          | Functional spec for largest-remainder & bump rule                         | n/a             | `rounding_spec_digest`         |
| **zone_floor**                 | `config/allocation/zone_floor.yml`                            | Minimum outlet counts φₙ for micro-zones                                  | `semver`        | `zone_floor_digest`            |
| **country_major_zone**         | `artefacts/allocation/country_major_zone.csv`                 | Fallback mapping country→major TZID by land-area                          | n/a             | `major_zone_digest`            |
| **zone_alloc_parquet**         | `artefacts/allocation/<merchant_id>_zone_alloc.parquet`       | Per-merchant (country_iso, tzid, N_outlets) allocation                    | n/a             | `zone_alloc_parquet_digest`    |
| **zone_alloc_index**           | `artefacts/allocation/zone_alloc_index.csv`                   | Drift-sentinel index mapping \<merchant_id>,<sha256>                      | n/a             | `zone_alloc_index_digest`      |
| **zone_alloc_schema**          | `artefacts/allocation/zone_alloc_schema.json`                 | Parquet schema for allocation outputs                                     | schema_version  | `zone_alloc_schema_digest`     |
| **barcode_slope_log**          | `logs/barcode_slope_validation.log`                           | Numeric log of offset-barcode slope per merchant                          | Manifest semver | (run-specific)                 |
| **barcode_slope_heatmap**      | `logs/barcode_slope_heatmap.png`                              | Visual diagnostic of barcode slope convergence                            | Manifest semver | (run-specific)                 |
| **cross_zone_validation**      | `config/validation/cross_zone_validation.yml`                 | CI thresholds for barcode/zone-share convergence                          | `semver`        | `cross_zone_validation_digest` |
| **test_rounding_conservation** | `logs/test_rounding_conservation.log`                         | Property-based test log from CI on conservation, replay, and monotonicity | Manifest semver | (run-specific)                 |
| **error_log**                  | `logs/zone_alloc_error.log`                                   | All drift/error events (ZoneAllocDriftError, UniverseHashError, etc.)     | Manifest semver | (run-specific)                 |
| **rng_proof**                  | `docs/rng_proof.md`                                           | Formal RNG-isolation proof                                                | n/a             | `rng_proof_digest`             |
| **license_files**              | `LICENSES/*.md`                                               | Licence texts for public data and analyst-authored policies               | n/a             | `licence_digests`              |
| **universe_hash_digest**       | `artefacts/allocation/universe_hash_digest.txt`               | Allocation integrity sentinel                                             | Manifest semver | <run-specific>                 |
| **gamma_day_effect**           | `artefacts/allocation/<merchant_id>_gamma_day_effect.parquet` | Daily corporate-day γ values                                              | Manifest semver | <run-specific>                 |
| **barcode_slope_validation**   | `logs/barcode_slope_validation.log`                           | Nightly barcode-slope validation results                                  | Manifest semver | <run-specific>                 |
| **share_convergence_log**      | `logs/share_convergence.log`                                  | Zone-share convergence diagnostics                                        | Manifest semver | <run-specific>                 |

---

### Enforcement and Contract Notes

* **Any addition, removal, or semver/digest change in the artefact set triggers a manifest refresh and CI build.**
* **All Parquet allocation outputs must conform to the schema in `zone_alloc_schema.json`—column names, types, order, and sortedness contractually enforced.**
* **All validation, diagnostic, and test logs must be retained and referenced in the build manifest; missing logs are a build failure.**
* **Any output row or log with a mismatched `universe_hash` is considered invalid; drift triggers a hard abort and error log event.**
* **Each YAML/CSV/config artefact must have a mapped licence file in `LICENSES/` and matching digest.**
* **Drift sentinel errors and property-based test failures must be logged and are blocking for build completion.**
