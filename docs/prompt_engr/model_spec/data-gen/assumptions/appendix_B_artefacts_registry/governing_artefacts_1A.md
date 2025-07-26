## Subsegment 1A: From merchants to physical sites

### **Input Model and Parameter Artefacts**
- `hurdle_coefficients.yaml`
  Logistic (hurdle) **and NB-mean** regression coefficients (intercept, MCC, channel, GDP bucket), with version and SHA-256 digest.
- `nb_dispersion_coefficients.yaml`  
  Negative binomial dispersion coefficients (including GDP per-capita term η), with version and SHA-256 digest.
- `crossborder_hyperparams.yaml`  
  Hyperparameters for cross-border expansion (θ₀, θ₁), Dirichlet concentrations (α-vectors), and Wald statistics for ZTP model; versioned and digested.
- `artefacts/gdp/gdp_bucket_map_2024.parquet`  
  Jenks natural break GDP per-capita mapping table; versioned and digested.
- `artefacts/network_share_vectors/settlement_shares_2024Q4.parquet`  
  Currency-level settlement share vectors.
- `artefacts/currency_country_split/ccy_country_shares_2024Q4.parquet`  
  Intra-currency country split table (proportional weights, obs counts).
- `artefacts/diagnostics/hurdle_stationarity_tests_2024Q4.parquet`  
  Stationarity diagnostic output for hurdle model; referenced in parameter YAMLs.

### **Manifest and Lineage Artefacts**
- `_manifest.json`  
  Top-level manifest file: SHA-256 digest, full artefact list, parameter hash, version lineage. Embeds manifest fingerprint used throughout build.
- `manifest_fingerprint`  
  The 256-bit lineage fingerprint (hex64) embedded in every output row and output log, and used as Philox seed source.

### **Audit and Validation Logs**
- `rng_audit.log`  
  Structured log of all stochastic draws, counters, and rejections for reproducibility (see narrative/assumptions event schema).
- `diagnostic_metrics.parquet`  
  Metrics output: NB rejection rates, CUSUM status, rounding errors, parameter drift; referenced in CI/CD monitoring.
- `artefacts/diagnostics/hurdle_stationarity_tests_2024Q4.parquet`
  Rolling Wald-test diagnostics for the hurdle/NB-mean coefficients.

### **Output Artefacts**
- `outlet_catalogue/seed={seed}/fingerprint={fingerprint}/part-*.parquet`  
  The immutable outlet stub table; schema as per narrative/assumptions; path embeds lineage and master seed.

### **Schema and Contract Artefacts**
- `outlet_catalogue_schema.json`  
  (Optional, but recommended) Explicit schema descriptor for outlet stub output, versioned and referenced.
- `schema_version.txt`  
  Schema version file; increment triggers manifest fingerprint change.

---

**Note:**  
Any change to any artefact’s content, version, or path triggers a manifest fingerprint change and propagates new output lineage as required by the reproducibility contract.

---
