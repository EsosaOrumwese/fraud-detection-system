Below is a consolidated, paste‑ready **governing artefacts** note for **3B – Special treatment for purely virtual merchants**. It mirrors your current 3B registry and the 3B narrative/assumptions, uses plain ASCII, and keeps scope tight.

---

## Scope

This section lists only the governed artefacts and rules needed to audit and reproduce sub‑segment 3B. It references cross‑layer inputs but does not redefine them.

---

## A) Inputs and per‑run manifest

* **virtual\_manifest.json** — the auditor entry point. It must include the digests for everything 3B claims to use:

  * `virtual_rules_digest`
  * `settlement_coord_digest`
  * `pelias_digest`
  * `cdn_country_weights_digest`
  * `hrsl_digest`
  * `edge_catalogue_index_digest`
  * `cdn_key_digest`
  * plus schema digests you enforce (edge catalogue, transaction schema)

  CI rule: if any referenced digest changes without this manifest changing, fail the run.

* **merchant\_master.parquet** — cross‑layer input with the `is_virtual` flag that downstream checks compare against. Marked cross\_layer in the registry.

---

## B) Virtual‑merchant classification

* **mcc\_channel\_rules.yaml** → `virtual_rules_digest`
  Mapping from MCC to `online_only` (optionally by channel). Governs how `is_virtual` is derived.

* **derive\_is\_virtual.py** and **ci/test\_virtual\_rules.py**
  Script sets `is_virtual` in the master; CI re‑derives and byte‑compares to the parquet. Both must reference the YAML above.

---

## C) Settlement node

* **virtual\_settlement\_coords.csv** → `settlement_coord_digest`
  One row per merchant: `merchant_id, lat, lon, evidence_url`. Used to anchor the single settlement node.

* **pelias\_cached.sqlite** → `pelias_digest` and **ci/test\_geocoder\_bundle.py**
  Offline geocoder bundle must hash‑match before runs. CI also samples URLs from the coords CSV and asserts small geocode error.

---

## D) CDN edge weights and catalogue

* **cdn\_country\_weights.yaml** → `cdn_country_weights_digest`
  Stationary weights by country. Includes an integer `edge_scale` that controls rounding granularity for edges per merchant.

* **hrsl\_100m.tif** → `hrsl_digest`
  HRSL population raster used to place edges within countries.

* **build\_edge\_catalogue.py**
  Multiplies weights by `edge_scale`, applies largest‑remainder rounding, then samples coordinates against HRSL.

* **edge\_catalogue.schema.json** → `edge_catalogue_schema_digest`
  Pins columns and types: `edge_id STRING, country_iso STRING, tzid STRING, lat DOUBLE, lon DOUBLE, edge_weight FLOAT`. All parquet files must validate against this.

* **edge\_catalogue/\<merchant\_id>.parquet** → `edge_catalogue_digest`
  One file per merchant. Indexed by:
  **edge\_catalogue\_index.csv** → `edge_catalogue_index_digest`.

---

## E) RNG policy and alias tables

* **rng\_policy.yml** (cross‑layer) → `cdn_key_digest`
  SHA‑256 keyed Philox policy for the CDN alias stream. 3B references this, it does not redefine it.

* **universe\_hash\_policy.md** (cross‑layer reference)
  Freezes the concatenation order for the alias file’s embedded universe hash. 3B uses this policy when embedding or checking the hash.

* **\<merchant\_id>\_cdn\_alias.npz** → `cdn_alias_digest`
  Alias table for edge selection. Must embed the universe hash that combines the governing digests (weights, edge catalogue, rules) as defined by the policy above.
  **VirtualUniverseMismatchError** is raised if the stored universe hash does not match the recomputed value at load.

---

## F) Transaction schema extensions

* **transaction\_schema.avsc** → `transaction_schema_digest`
  Adds fields: `tzid_settlement`, `tzid_operational`, `ip_latitude`, `ip_longitude`, `ip_country`.
  **ci/test\_schema\_registry.py** enforces registry consistency.

---

## G) Validation and diagnostics

* **virtual\_validation.yml** → `virtual_validation_digest`
  Tolerances for ip\_country shares and settlement cut‑off checks.

* **test\_virtual\_validation.py** and **validate\_virtual.py**
  Compute empirical ip\_country proportions over a 30‑day synthetic window and enforce the time cut‑off rule. Fail CI on breach.

* **edge\_progress.log** with **virtual\_logging.yml**
  Append‑only progress log for crash recovery. Rotation and retention are governed by the logging config and should be referenced by the log.

---

## H) Licences and roll‑up

* **LICENSES/akamai\_soti.md** and **LICENSES/facebook\_hrsl.md**
  Licence texts for the external inputs.

* **virtual\_licences\_manifest.json** → `virtual_licences_digest`
  Roll‑up manifest listing the licence digests that apply to 3B.

---

## I) CI and audit rules

1. **Manifest completeness**. `virtual_manifest.json` must contain every key listed in section A and the values must match the sources in the run.
2. **Schema lock**. All edge catalogue parquet files validate against `edge_catalogue.schema.json`. Any column/type/order change requires a schema update.
3. **Alias determinism**. Rebuilding `*_cdn_alias.npz` from the same inputs must produce the same bytes. The embedded universe hash must match recomputation.
4. **Validation gates**. ip\_country share tolerance and settlement cut‑off rules from `virtual_validation.yml` must pass.
5. **Geocoder provenance**. The Pelias bundle digest must match before the run; otherwise block.
6. **Logging governance**. `edge_progress.log` must reference `virtual_logging.yml` and respect rotation/retention.

---

## Additions

| Governing artefact ID           | Path / pattern                                                                    | Role (one‑liner)                                               | Provenance / digest key      |
|---------------------------------|-----------------------------------------------------------------------------------|----------------------------------------------------------------|------------------------------|
| site_catalogue                  | data/outputs/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/     | Cross‑layer input: outlet stubs with `is_virtual` flag         | site_catalogue_digest        |
| mcc_channel_rules               | config/virtual/mcc_channel_rules.yaml                                             | MCC + channel rules deriving `is_virtual`                      | virtual_rules_digest         |
| cdn_country_weights             | config/virtual/cdn_country_weights.yaml                                           | Country → weight YAML (edge_scale = 500)                       | cdn_country_weights_digest   |
| hrsl_raster                     | artefacts/rasters/hrsl_100m.tif                                                   | HRSL 100 m population raster (external CC‑BY)                  | hrsl_digest                  |
| virtual_settlement_coords       | artefacts/virtual/virtual_settlement_coords.csv                                   | Merchant settlement lat/lon + evidence URL                     | settlement_coord_digest      |
| pelias_cached_sqlite            | artefacts/geocode/pelias_cached.sqlite                                            | Offline Pelias bundle for evidence‑URL QC                      | pelias_digest                |
| virtual_validation_policy       | config/virtual/virtual_validation.yml                                             | Tolerances for ip‑country share & cut‑off checks               | virtual_validation_digest    |
| virtual_logging_policy          | config/logging/virtual_logging.yml                                                | Rotation/retention rules for `edge_progress.log`               | virtual_logging_digest       |
| routing_day_effect              | config/routing/routing_day_effect.yml                                             | σ² for daily γ_d multiplier (cross‑layer)                      | gamma_variance_digest        |
| rng_policy                      | config/routing/rng_policy.yml                                                     | Philox sub‑stream derivation keys (cross‑layer)                | rng_policy_digest            |
| performance_config              | config/routing/performance.yml                                                    | Throughput & memory SLA thresholds (cross‑layer)               | perf_config_digest           |
| edge_catalogue_schema           | schema/edge_catalogue.schema.json                                                 | JSON‑Schema for edge catalogue parquet                         | edge_catalogue_schema_digest |
| edge_catalogue*                 | artefacts/virtual/edge_catalogue/{merchant_id}_edges.parquet                      | Deterministically sampled edge nodes per merchant              | (per‑file SHA‑256)           |
| edge_catalogue_index            | artefacts/virtual/edge_catalogue_index.csv                                        | Merchant → edge‑parquet path + hash lookup                     | edge_catalogue_index_digest  |
| cdn_alias*                      | artefacts/virtual/cdn_alias/{merchant_id}_cdn_alias.npz                           | Alias tables embedding `virtual_universe_hash`                 | (per‑file SHA‑256)           |
| virtual_manifest                | artefacts/manifests/virtual_manifest.json                                         | Digest roll‑up of edges, aliases & configs                     | virtual_manifest_digest      |
| build_fingerprint_3B            | artefacts/manifests/build_fingerprint_3B.txt                                      | Composite SHA‑256 tying 3B to upstream artefacts               | build_fp_3B_digest           |
| edge_progress_log               | logs/virtual/{run_id}/edge_progress.log                                           | Crash‑recovery progress log                                    | (run‑specific)               |
| virtual_audit_log               | logs/virtual/{run_id}/virtual_audit.log                                           | Batch checksum audit stream                                    | (run‑specific)               |
| gamma_draw_log                  | logs/virtual/{run_id}/gamma_draw.jsonl                                            | γ_d audit (uniform + log‑normal)                               | (run‑specific)               |
| edge_sampler_metrics            | artefacts/metrics/edge_sampler_{run_id}.parquet                                   | Events/s & RSS for edge sampler perf budget                    | (run‑specific)               |
| derive_is_virtual_py            | src/virtual/derive_is_virtual.py                                                  | Sets/updates `is_virtual` flag                                 | git_tree_hash                |
| edge_sampler_py                 | src/virtual/edge_sampler.py                                                       | Builds edge catalogue                                          | git_tree_hash                |
| alias_builder_py                | src/virtual/alias_builder.py                                                      | Builds NPZ CDN alias tables                                    | git_tree_hash                |
| validate_virtual_py             | tests/validate_virtual.py                                                         | End‑to‑end validation harness                                  | git_tree_hash                |
| test_virtual_rules_py           | ci/tests/test_virtual_rules.py                                                    | CI test: MCC rules drift                                       | git_tree_hash                |
| test_geocoder_bundle_py         | ci/tests/test_geocoder_bundle.py                                                  | CI test: geocode within 5 km                                   | git_tree_hash                |
| test_virtual_validation_py      | ci/tests/test_virtual_validation.py                                               | CI test: validation thresholds                                 | git_tree_hash                |
| licences_akamai_md              | LICENSES/akamai_soti.md                                                           | Licence text for Akamai SOTI                                   | licences_akamai_digest       |
| licences_hrsl_md                | LICENSES/facebook_hrsl.md                                                         | Licence text for HRSL raster                                   | licences_hrsl_digest         |
| universe_hash_policy_doc        | docs/universe_hash_policy.md                                                      | Definition of `virtual_universe_hash`                          | universe_hash_policy_digest  |
| VirtualUniverseMismatchError    | exception (contract)                                                              | Raised on universe hash mismatch                               | n/a                          |
| VirtualEdgeSamplingError        | exception (contract)                                                              | Raised on HRSL sampling failure                                | n/a                          |

*Notes*

* IDs with “*” (edge\_catalogue*, cdn\_alias\*) denote one artefact per **virtual merchant**; their individual digests are rolled into **`virtual_manifest.json`**.
* Cross‑layer configs (`routing_day_effect.yml`, `rng_policy.yml`, `performance.yml`) are referenced, not duplicated, ensuring no circular dependencies.
* Every artefact listed in the 3B registry is present; no extras, no omissions, no empty columns.

