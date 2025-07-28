## Subsegment 1A: From merchants to physical sites
Below is a comprehensive registry of **all artefacts** mentioned in Sub‑segment 1A (Merchants → Physical Sites), grouped by category. Each bullet gives the artefact’s name (in **bold**) and a brief note on its role. I’ve cross‑checked both the assumptions and narrative documents to ensure nothing is omitted.

---

### 1. Artefact Bundles & Provenance

* **`hurdle_coefficients.yaml`** – YAML bundle holding the full vector of hurdle‐logistic coefficients (intercept, MCC dummies, channel dummies, GDP‑bucket dummies) and NB mean coefficients .
* **`nb_dispersion_coefficients.yaml`** – YAML bundle with NB dispersion (φ) coefficients including the GDP‑per‑capita term η .
* **`crossborder_hyperparams.yaml`** – YAML containing θ₀, θ₁ for λ\_extra and Dirichlet concentration vectors α (keyed by (home\_country, MCC, channel)); includes Wald‐test stats under `theta1_stats` .
* **`spatial_prior_bundle/…`** – Directory of spatial‑prior artefacts (digests included in manifest to freeze downstream behaviour) .

### 2. GDP & Stationarity Artefacts

* **World Bank GDP CSV (2025‑04‑15)** – “World Development Indicators” vintage for GDP per capita; its SHA‑256 digest is recorded .
* **`artefacts/gdp/gdp_bucket_map_2024.parquet`** – Jenks natural‐break mapping of GDP per capita into buckets 1–5; entries `gdp_bucket_map_semver` and `gdp_bucket_map_digest` captured in manifest .
* **`artefacts/diagnostics/hurdle_stationarity_tests_2024Q4.parquet`** – Rolling‐window Wald‐test outputs for coefficient stationarity (α = 0.01); SHA‑256 digest logged .

### 3. Settlement & Currency Split Artefacts

* **`artefacts/network_share_vectors/settlement_shares_2024Q4.parquet`** – Currency‑level settlement‑share vectors; semver and SHA‑256 digest tracked .
* **`artefacts/currency_country_split/ccy_country_shares_2024Q4.parquet`** – Intra‑currency country‐split weights with per‑cell observation counts .

### 4. Manifest & Seed Artefacts

* **Git commit hash** – Repository snapshot tag; XOR‑reduced with all file digests .
* **`parameter_hash`** – SHA‑256 of concatenated (lexicographically ordered) YAML digests .
* **`manifest_fingerprint`** – Hex64 SHA‑256 of XOR of all artefact digests + commit + `parameter_hash`; embedded in `_manifest.json`, Parquet comments, and each stub row .
* **Philox 2¹²⁸ master counter** – RNG stream seeded by H(manifest\_fingerprint ∥ run\_seed) .

### 5. RNG Audit & Event‑Log Artefacts

* **`rng_audit.log`** (structured rows) – Records each random draw with fields:

  * `timestamp_utc, event_type, merchant_id, pre_counter, post_counter, parameter_hash, draw_sequence_index, rejection_flag, …` .
* **Event types** (mandatory per merchant):

  * `hurdle_bernoulli`
  * `gamma_component`
  * `poisson_component`
  * `nb_final`
  * `ztp_rejection`
  * `ztp_retry_exhausted`
  * `gumbel_key`
  * `dirichlet_gamma_vector`
  * `stream_jump`
  * `sequence_finalize` .
* **`stream_jump` entries** – Logged strides for sub‑stream jumps (module name, hash\_source, stride\_uint64) .

### 6. Merchant Design & Hurdle Artefacts

* **`transaction_schema.merchant_id` rows** – Input symbolic IDs transformed into outlet stubs .
* **Design matrix row** – Computed per‐merchant predictors: intercept + MCC + channel + GDP bucket .
* **`π` probability** – Logistic output stored as part of the `hurdle_bernoulli` event .
* **`single_vs_multi_flag`** – Persisted 0/1 outcome of hurdle decision .

### 7. Negative‐Binomial Artefacts

* **NB mean log‑link** – Predictors: intercept + MCC + channel (explicitly excludes GDP bucket) .
* **NB dispersion log‑link** – Predictors: intercept + MCC + channel + η·log(GDPpc) (η > 0 enforced) .
* **Poisson–Gamma mixture** – Intermediate draws (`gamma_component`, `poisson_component`) logged; final NB draw under `nb_final` .
* **NB rejection loop** – Rejections when N∈{0,1} (max 99th‑percentile ≤ 3); counters logged .

### 8. Cross‑Border & ZTP Artefacts

* **λ\_extra formula** – θ₀ + θ₁·log N (θ₁<1, p‑value<1e‑5 in `theta1_stats`) .
* **`ztp_rejection` & `ztp_retry_exhausted`** – Events for zero‑truncation sampling up to 64 attempts .
* **`sparse_flag`** – Set when fallback to equal‐split is used due to low obs (< 30 total) in ccy\_country\_shares .

### 9. Gumbel‑Top‑k Artefacts

* **`gumbel_key`** – For each candidate country: logs (country\_iso, w\_i, u\_i, key\_i); K largest selected .
* **Ordered `country_set`** – Length K+1 list: home first, then selected foreign ISOs in chosen order .

### 10. Dirichlet Allocation Artefacts

* **`dirichlet_gamma_vector`** – Logs raw G\_i draws, summed Gamma, and normalized w\_i (8‐dp) .
* **`tie_break_rank`** – Position after residual sort, used in largest‑remainder rounding .
* **`docs/derivations/dirichlet_lrr_proof.md`** – Formal proof of bound and determinism; its digest is manifest‑logged .

### 11. Outlet‑Stub Schema Artefacts

Non‑nullable Parquet columns for each stub row (with types):

| Column                            | Type     | Role                                     |
| --------------------------------- | -------- | ---------------------------------------- |
| **merchant\_id**                  | int64    | Original merchant identifier             |
| **site\_id**                      | string   | 6‑digit zero‑padded per‑country sequence |
| **home\_country\_iso**            | char(2)  | Merchant’s onboarding country            |
| **legal\_country\_iso**           | char(2)  | Outlet’s trading country                 |
| **single\_vs\_multi\_flag**       | bool     | Hurdle outcome                           |
| **raw\_nb\_outlet\_draw**         | int32    | NB draw N (≥2 if multi, else 1)          |
| **final\_country\_outlet\_count** | int32    | nᵢ allocated to this country             |
| **tie\_break\_rank**              | int32    | Forensic replay order                    |
| **manifest\_fingerprint**         | char(64) | Catalogue lineage ID                     |
| **global\_seed**                  | uint64   | Derived Philox seed                      |

* **Compression**: ZSTD level 3 (codec choice hashed)
* **Storage path** embeds `seed=` and `fingerprint=` for deterministic partitioning .

### 12. Validation & Monitoring Artefacts

* **Post‑write validation routine** – Recomputes μ, φ, K, Dirichlet weights, sorting, allocations, tie\_break\_rank, site\_ids; mismatches abort the build .
* **Stream‑jump audit** – Additional `stream_jump` events for modules like “cross-border-allocation” .
* **Nightly CI metrics** – nb\_rejection\_rate\_overall, nb\_rejections\_p99; ZTP mean/p99.9; rounding deviations; sparse\_flag rate; event\_type counts; parameter‑drift checks; θ₁ significance (p < 0.001) .

### 13. Numeric Environment Artefacts

* **IEEE‑754 binary64** arithmetic for all stochastic & residual ops .
* **Fused‑multiply‑add disabled** for Dirichlet and residual computations .
* **Residual quantisation** to 8 decimal places before sorting .

---


On a second, line‑by‑line pass through the actual Sub‑segment 1A files, I found three artefacts that weren’t in the first registry. Here they are, each with its role and a citation to the precise snippet:

1. **`run_seed`**
   *Role:* The user‑provided randomness seed that’s concatenated with the `manifest_fingerprint` to derive the Philox master seed (via H(manifest\_fingerprint ∥ run\_seed)).


2. **`rng_trace.log`**
   *Role:* Records every Philox sub‑stream jump for modules that need multiple streams (e.g. one per merchant). Each row is `(module_name, merchant_id, jump_offset)`, allowing an auditor to recreate any sub‑stream position exactly.


3. **Internal dataset registry (`datasets` table)**
   *Role:* A Postgres catalog table (`datasets(id, parameter_hash, seed, path)`) queried in the “collision audit” to ensure you never accidentally rebuild under the same `(seed, parameter_hash)` but with different outputs.


With those added, the registry for Sub‑segment 1A is now rock‑solid. Let me know if you’d like another sweep or want to move on to the next sub‑segment.
