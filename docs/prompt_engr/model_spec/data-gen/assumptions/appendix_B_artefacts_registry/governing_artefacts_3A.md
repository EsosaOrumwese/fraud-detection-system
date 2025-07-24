## Subsegment 3A: Capturing cross‑zone merchants

| ID / Key                    | Path Pattern                                            | Role                                                        | Semver Field | Digest Field                   |
|-----------------------------|---------------------------------------------------------|-------------------------------------------------------------|--------------|--------------------------------|
| **zone\_mixture\_policy**   | `config/allocation/zone_mixture_policy.yml`             | Attention‑threshold θ for escalation queue                  | `semver`     | `theta_digest`                 |
| **country\_zone\_alphas**   | `config/allocation/country_zone_alphas.yaml`            | Dirichlet concentration parameters α per ISO country→TZID   | `semver`     | `zone_alpha_digest`            |
| **rounding\_spec**          | `docs/round_ints.md`                                    | Functional spec for largest‑remainder & bump rule           | n/a          | `rounding_spec_digest`         |
| **zone\_floor**             | `config/allocation/zone_floor.yml`                      | Minimum outlet counts φₙ for micro‑zones                    | `semver`     | `zone_floor_digest`            |
| **country\_major\_zone**    | `artefacts/allocation/country_major_zone.csv`           | Fallback mapping country→major TZID by land‑area            | n/a          | `major_zone_digest`            |
| **zone\_alloc\_parquet**    | `artefacts/allocation/<merchant_id>_zone_alloc.parquet` | Per‑merchant `(country_iso, tzid, N_outlets)` allocation    | n/a          | `zone_alloc_parquet_digest`    |
| **zone\_alloc\_index**      | `artefacts/allocation/zone_alloc_index.csv`             | Drift‑sentinel index mapping `<merchant_id>,<sha256>`       | n/a          | `zone_alloc_index_digest`      |
| **routing\_day\_effect**    | `config/routing/routing_day_effect.yml`                 | Corporate‑day log‑normal variance σ\_γ²                     | `semver`     | `gamma_variance_digest`        |
| **rng\_proof**              | `docs/rng_proof.md`                                     | Formal RNG‑isolation proof                                  | n/a          | `rng_proof_digest`             |
| **cross\_zone\_validation** | `config/validation/cross_zone_validation.yml`           | CI thresholds for offset‑barcode slope & share convergence  | `semver`     | `cross_zone_validation_digest` |
| **license\_files**          | `LICENSES/*.md`                                         | Licence texts for public data and analyst‑authored policies | n/a          | `licence_digests`              |

**Notes:**

* `n/a` in **Semver Field** indicates no inline semver; the file’s path and digest alone govern it.
* Replace `<merchant_id>` with the zero‑padded merchant code.
* All paths use Unix‑style forward slashes and are case‑sensitive.
* Any addition, removal, or version change of these artefacts must follow semver and manifest rules and will automatically refresh the overall manifest digest via CI.