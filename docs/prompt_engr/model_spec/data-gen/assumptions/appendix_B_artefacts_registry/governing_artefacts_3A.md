# 3A · Capturing cross‑zone merchants — governing artefacts

This lists only the governed artefacts and rules needed to audit and reproduce sub‑segment 3A. It mirrors the current registry and does not redefine cross‑layer items.

## A) Cross‑layer references consumed in 3A (not defined here)

* **routing\_day\_effect.yml** → `gamma_variance_digest`
  Variance σγ² for the corporate‑day multiplier used by barcode checks.
* **rng\_policy.yml** → `gamma_day_key_digest`
  SHA‑256 keyed Philox policy for the γ\_d day stream.
* **gamma\_draw\.jsonl** (log)
  Per‑merchant, per‑UTC‑day γ\_d value and stream info for replay.
* **spatial\_manifest.json** → `tz_polygon_digest`
  tz‑world vintage that `country_major_zone.csv` depends on.

> 3A must reference these digests so outputs and CI checks align with the same RNG and spatial vintage used elsewhere.

## B) Parameters and policies owned by 3A

* **zone\_mixture\_policy.yml** → `theta_digest`
  Threshold (θ\_mix) for entering multi‑zone allocation by country.
* **country\_zone\_alphas.yaml** → `zone_alpha_digest`
  Dirichlet α parameters by (country, tzid).
* **round\_ints.md** → `rounding_spec_digest`
  Largest‑remainder rounding with a deterministic bump rule.
* **zone\_floor.yml** → `zone_floor_digest`
  Minimum outlets per protected micro‑zone.
* **universe\_hash\_policy.md** → `universe_hash_policy_digest`
  Canonical concatenation order used to compute the universe hash validated downstream.
* **rng\_proof.md** → `rng_proof_digest`
  Proof that the γ\_d stream follows the SHA‑256 policy and is independent of routing draws.

## C) Derived reference (spatial provenance)

* **country\_major\_zone.csv** → `major_zone_digest`
  Per‑country largest‑area TZID for fallback allocations. **Depends on** the cross‑layer `spatial_manifest.json` to pin vintage.

## D) Outputs and schema (allocation result)

* **zone\_alloc.schema.json** → `zone_alloc_schema_digest`
  Pins layout and types: `(country_iso STRING, tzid STRING, N_outlets UINT16)`; sorted by `(country_iso, tzid)`.
* **{merchant\_id}\_zone\_alloc.parquet** → `zone_alloc_parquet_digest`
  Final per‑merchant triples after floors and bump rule. **Must validate against** the schema.
* **zone\_alloc\_index.csv** → `zone_alloc_index_digest`
  Index: `(merchant_id, country_iso, tzid) → row_offset` in the Parquet.

## E) Per‑run manifest (single place auditors look)

* **allocation\_manifest.json** → `allocation_manifest_digest`
  Must include **all** of the following keys reflecting the exact digests used this run:
  `theta_digest, zone_alpha_digest, zone_floor_digest, major_zone_digest, zone_alloc_parquet_digest, zone_alloc_index_digest, cross_zone_validation_digest, gamma_variance_digest, gamma_day_key_digest`.

> CI: if any referenced digest changes without this manifest changing, **fail** the run.

## F) Validation and diagnostics

* **cross\_zone\_validation.yml** → `cross_zone_validation_digest`
  Tolerances for share convergence and barcode slope.
* **CI tests**

  * `test_mix_threshold.py` — θ\_mix gating and escalation queue.
  * `test_rounding_conservation.py` — sum floors + bumps equals the country total deterministically.
  * `test_zone_floor.py` — protected micro‑zones meet configured floors.
  * `replay_zone_alloc.py` — determinism of Parquet and index integrity.
* **Diagnostics (on failure)**

  * `barcode_heatmap.png` — saved per merchant under `ci/diagnostics/{merchant_id}/`.

## G) Licences and provenance

* **LICENSES/visa\_mcx.md** → `visa_mcx_license_digest`
  Licence text for Visa/Mastercard index used during parameter estimation.
* **allocation\_licences\_manifest.json** → `allocation_licences_digest`
  Roll‑up of licence digests for this sub‑segment.

## H) CI and audit rules

1. **Schema lock** — `zone_alloc.parquet` must validate against `zone_alloc.schema.json`. Any column/type/order change requires a schema update.
2. **Determinism** — Replaying allocation must reproduce identical `zone_alloc.parquet` bytes and `zone_alloc_index.csv`; otherwise raise `ZoneAllocDriftError`.
3. **Manifest completeness** — `allocation_manifest.json` must contain all keys in section E and digests must match sources for the run.
4. **RNG and spatial alignment** — `gamma_variance_digest`, `gamma_day_key_digest`, and `tz_polygon_digest` must match the cross‑layer references from the same build window.
5. **Diagnostics on breach** — On barcode slope or convergence breach, emit `barcode_heatmap.png` and fail CI.


| Governing artefact ID         | Path / pattern                                                                | Role (one‑liner)                                         | Provenance field             |
|-------------------------------|-------------------------------------------------------------------------------|----------------------------------------------------------|------------------------------|
| site_catalogue                | data/outputs/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/ | Cross‑layer input: outlet stubs with tzid & foot‑traffic | site_catalogue_digest        |
| zone_mixture_policy           | config/zone/zone_mixture_policy.yml                                           | θ_mix threshold between single‑ and multi‑zone merchants | theta_digest                 |
| country_zone_alphas           | config/zone/country_zone_alphas.yaml                                          | Dirichlet α per country+channel                          | zone_alpha_digest            |
| zone_floor                    | config/zone/zone_floor.yml                                                    | Sparse minimum‑share list                                | zone_floor_digest            |
| country_major_zone            | data/reference/geo/country_major_zone.csv                                     | ISO → major TZID mapping (external, CC‑BY 4.0)           | major_zone_digest            |
| routing_day_effect            | config/routing/routing_day_effect.yml                                         | σ² for daily γ_d multiplier (shared with 2B)             | gamma_variance_digest        |
| rng_policy                    | config/routing/rng_policy.yml                                                 | Philox sub‑stream derivation keys                        | rng_policy_digest            |
| tz_grouping_policy            | config/zone/tz_grouping_policy.yml                                            | Defines zone renormalisation groups                      | tz_group_policy_digest       |
| routing_validation_policy     | config/validation/cross_zone_validation.yml                                   | Share & barcode‑slope validation thresholds              | cross_zone_validation_digest |
| zone_alloc_schema             | schema/zone_alloc.schema.json                                                 | JSON‑Schema for zone‑alloc parquet                       | zone_alloc_schema_digest     |
| merchant_zone_alloc*          | artefacts/zone_alloc/output/{merchant_id}_zone_alloc.parquet                  | Dirichlet‑rounded zone shares per merchant               | (per‑file SHA‑256)           |
| zone_alloc_index              | artefacts/zone_alloc/index/zone_alloc_index.csv                               | Merchant→parquet+hash lookup table                       | zone_alloc_index_digest      |
| allocation_manifest           | artefacts/manifests/allocation_manifest.json                                  | Digest bundle of all parquet & index files               | allocation_manifest_digest   |
| allocation_licences_manifest  | artefacts/manifests/allocation_licences_manifest.json                         | Licence provenance bundle                                | allocation_licences_digest   |
| universe_hash_policy_doc      | docs/universe_hash_policy.md                                                  | Definition of universe_hash lineage guard                | universe_hash_policy_digest  |
| gamma_draw_log                | logs/zone_alloc/{run_id}/gamma_draw.jsonl                                     | γ_d draw audit stream                                    | (run‑specific)               |
| rng_audit_2B                  | logs/routing/{run_id}/rng_audit_2B.log                                        | Philox counter audit (inherited from 2B)                 | (run‑specific)               |
| make_zone_alphas.py           | src/zone/make_zone_alphas.py                                                  | Generates α YAML from JPM data                           | git_tree_hash                |
| replay_zone_alloc.py          | tools/replay_zone_alloc.py                                                    | Deterministic replay / diff tool                         | git_tree_hash                |
| test_mix_threshold.py         | ci/tests/test_mix_threshold.py                                                | CI test for θ_mix drift                                  | git_tree_hash                |
| test_zone_floor.py            | ci/tests/test_zone_floor.py                                                   | CI test enforcing zone_floor floors                      | git_tree_hash                |
| test_rounding_conservation.py | ci/tests/test_rounding_conservation.py                                        | CI test for rounding‑sum conservation                    | git_tree_hash                |
| test_cross_zone_validation.py | ci/tests/test_cross_zone_validation.py                                        | CI test for barcode‑slope + share thresholds             | git_tree_hash                |
| barcode_heatmap_png           | artefacts/metrics/barcode_heatmap_{run_id}.png                                | Diagnostic heat‑map saved on validation failure          | (run‑specific)               |
| throughput_metrics            | artefacts/metrics/throughput_{run_id}.parquet                                 | Events/s & RSS samples for perf budget                   | (run‑specific)               |
| round_ints_doc                | docs/round_ints.md                                                            | Proof of deterministic integer rounding                  | round_ints_doc_digest        |
| alias_determinism_proof       | docs/alias_determinism_proof.md                                               | RNG‑free alias build proof (links to 2B)                 | alias_proof_digest           |
| rng_proof_doc                 | docs/rng_proof.md                                                             | Proof zone draws don’t leak into other streams           | rng_proof_digest             |
| visa_mcx_md                   | docs/visa_mcx.md                                                              | Licence memo for Visa‑MCX data                           | visa_mcx_digest              |
| UniverseHashError             | exception (contract)                                                          | Triggered when manifest universe_hash mismatch           | n/a                          |
| ZoneAllocDriftError           | exception (contract)                                                          | Triggered when parquet hash ≠ index hash                 | n/a                          |
| performance_ci_script         | ci/tests/performance_budget_check.sh                                          | CI perf budget guard (shared with 2B)                    | git_tree_hash                |

---

*Notes*

* Artefact IDs ending in “\*” (merchant\_zone\_alloc\*) denote one artefact
  per merchant; their individual digests are rolled into
  **`allocation_manifest.json`**.
* External reference assets (`country_major_zone.csv`) are frozen CC‑BY
  snapshots; internal configs are semver‑governed YAML/JSON.
* All placeholders (`{run_id}`, `{sha256}`, `{semver}` …) mirror those in
  the registry; no empty cells remain.
* Licence digests roll up under `allocation_licences_manifest`.

