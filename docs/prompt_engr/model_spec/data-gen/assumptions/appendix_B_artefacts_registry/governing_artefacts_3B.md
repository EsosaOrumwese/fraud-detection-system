## Subsegment 3B: Special treatment for purely virtual merchants

| ID / Key                     | Path Pattern                                      | Role                                                     | Semver Field              | Digest Field                  |
| ---------------------------- | ------------------------------------------------- | -------------------------------------------------------- | ------------------------- | ----------------------------- |
| **virtual\_rules**           | `config/virtual/mcc_channel_rules.yaml`           | MCC→is\_virtual policy ledger                            | `semver`                  | `virtual_rules_digest`        |
| **settlement\_coords**       | `artefacts/virtual/virtual_settlement_coords.csv` | Settlement‑node coordinate & evidence URLs               | `settlement_coord_semver` | `settlement_coord_digest`     |
| **pelias\_bundle**           | `artefacts/geocode/pelias_cached.sqlite`          | Offline Pelias geocoder bundle                           | `semver`                  | `pelias_digest`               |
| **cdn\_weights**             | `config/virtual/cdn_country_weights.yaml`         | CDN edge‑weight policy                                   | `semver`                  | `cdn_weights_digest`          |
| **hrsl\_raster**             | `artefacts/rasters/hrsl_100m.tif`                 | Facebook HRSL 100 m population raster                    | `semver`                  | `hrsl_digest`                 |
| **edge\_catalogue\_parquet** | `edge_catalogue/<merchant_id>.parquet`            | Per‑merchant virtual edge node table                     | n/a                       | `edge_digest`                 |
| **edge\_catalogue\_index**   | `edge_catalogue_index.csv`                        | Drift‑sentinel index for all edge catalogues             | n/a                       | `edge_catalogue_index_digest` |
| **rng\_policy**              | `config/routing/rng_policy.yml`                   | Philox RNG key derivation policy                         | `semver`                  | `cdn_key_digest`              |
| **virtual\_validation**      | `config/virtual/virtual_validation.yml`           | CI thresholds for virtual‑merchant validation            | `semver`                  | `virtual_validation_digest`   |
| **transaction\_schema**      | `schema/transaction_schema.avsc`                  | AVSC schema defining virtual‑flow fields                 | `semver`                  | `transaction_schema_digest`   |
| **virtual\_logging**         | `config/logging/virtual_logging.yml`              | Logging rotation & retention policy for virtual builders | `semver`                  | `virtual_logging_digest`      |
| **licence\_files\_virtual**  | `LICENSES/*.md`                                   | Licence texts for virtual‑merchant artefacts             | n/a                       | `licence_digests_virtual`     |

**Notes:**

* Any entry marked **n/a** in the Semver column means the artefact has no inline version field; it is frozen purely by its digest.
* Replace `<merchant_id>` with the zero‑padded merchant identifier when resolving path patterns.
* All paths use Unix‑style forward slashes and are case‑sensitive.
* The manifest keys shown are the exact JSON fields in your `manifest*.json`; CI tests byte‑compare those against live artefacts.
* Adding, removing or changing any of these artefacts (path, semver or digest) will automatically bump the manifest digest and fail CI until revalidated.