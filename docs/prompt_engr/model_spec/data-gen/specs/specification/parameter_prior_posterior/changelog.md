## [1A.1.1] - 2025-07-25
### Added
- Exhaustive Parameter Catalogue (PP blocks) for Sub‑segment 1A, extracting every stochastic prior, constant and threshold from narrative, assumptions and Appendix A.
- Full Parameter Spec (PP‑FIX blocks) for PP IDs 1–7, completing PRIOR, CALIBRATION_RECIPE, POSTERIOR_VALIDATION, PROVENANCE_TAG, INTERFACE_CONSUMER and TEST_PATHWAY for each.
### Fixed
- Clarified default policies and units for parameters that were previously implicit.

## [1B.1.1] - 2025-07-25
### Added
- Exhaustive Parameter Catalogue (PP blocks) for Sub‑segment 1B, covering all outlet‑placement variables.
- Parameter Spec (PP‑FIX blocks) for PP IDs 1–15, with complete prior types, hyperparameters, calibration recipes, validation metrics and provenance tags.
### Fixed
- Specified interface_consumer modules for all geospatial and alias sampling parameters.

## [2A.1.1] - 2025-07-25
### Added
- Parameter Catalogue and Spec for Sub‑segment 2A (“Deriving the civil time zone”) covering PP 1–5 (ε, simulation horizon, forward‑gap Δ, SHA‑256 fold bit, tz_cache_bytes).
- Completeness checks: all CALIBRATION_RECIPE and POSTERIOR_VALIDATION entries explicitly marked N/A or populated.

## [2B.1.1] - 2025-07-25
### Added
- Parameter Catalogue (PP 1–10) and Spec for Sub‑segment 2B (“Routing transactions through sites”), including deterministic site‑weight and alias‑table functions, corporate‑day LogNormal (μ_γ & σ_γ²), Uniform(0,1) deviates, CDN country weights, validation thresholds, audit checks, RNG policy, performance SLAs.
### Fixed
- Added missing μ_γ and Uniform(0,1) parameters that were previously un‑catalogued.

## [3A.1.1] - 2025-07-25
### Added
- Parameter Catalogue (PP 1–16) and Spec for Sub‑segment 3A (“Capturing cross‑zone merchants”), covering θ_mix, τ smoothing, Dirichlet α_z, Gamma draws, bump‑rule ε_bump, zone–floor φ_z, fallback mapping, universe hash, Parquet & index digests, barcode slope & share tolerances.
  
## [3B.1.1] - 2025-07-25
### Added
- Parameter Catalogue (PP 1–8) and Spec for Sub‑segment 3B (“Special treatment for purely virtual merchants”), covering is_virtual flag, settlement‑node SHA1, geocode evidence (n_geo, d_max, R), edge scale E, edge‑catalogue bounds, discrete Uniform draws, CDN alias‑key policy, virtual‑universe hash, country‑share & time tolerances, log retention, schema & crash‑recovery policies.

## [4A.1.1] - 2025-07-25
### Added
- Parameter Catalogue (PP 1–17) and Spec for Sub‑segment 4A (“Reproducibility and configurability”), covering Docker & source hashes, parameter‑set hash, master seed, RNG spot‑checks, bootstrap replicates & z‑score, Beta posterior level, geospatial margin, over‑dispersion bounds, adversarial sample size & AUROC threshold, firewall batch/check counts, seconds‑per‑minute constant, DST edge‑pass window.
  
## [4B.1.1] - 2025-07-25
### Added
- Parameter Catalogue (PP 1–12) and Spec for Sub‑segment 4B (“Validation without bullet points”), covering structural failure Parquet, sliding window & AUROC intervals and thresholds, semantic‑GLM dispersion corridor & violation PDF, barcode slope & failure PNG, licence‑mismatch guard, validation_passed flag, HashGate upload URI, CI merge‑block condition.