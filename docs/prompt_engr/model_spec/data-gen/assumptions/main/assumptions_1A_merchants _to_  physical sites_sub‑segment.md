A merchant row in `transaction_schema` contains only four descriptive attributes—`merchant_id`, an MCC, the onboarding (home) country and a channel flag—yet by the end of the first sub‑segment the generator must have produced an immutable catalogue in which that merchant is represented by one or more **outlet stubs**. Each stub fixes the legal country in which the outlet trades; nothing downstream may reinterpret that decision. Because geospatial placement, timezone assignment and temporal intensity all build on this catalogue, the derivation of outlet counts and country spread must be reproducible, statistically defensible and hermetic. This document enumerates—explicitly—every assumption, parameterisation, artefact, and numeric environment constraint; any behaviour not written here is treated as a defect, not an implicit allowance.

---

### 1. Artefact Provenance & Manifest Construction

The generator ingests version‑tagged artefact bundles tracked under Git LFS:

* `hurdle_coefficients.yaml` – logistic (hurdle) coefficients and NB mean coefficients.
* `nb_dispersion_coefficients.yaml` – dispersion (φ) coefficients including GDP per‑capita term coefficient η.
* `crossborder_hyperparams.yaml` – (θ₀, θ₁) for λ\_extra and Dirichlet concentration vectors α keyed by (home\_country, MCC, channel); includes `theta1_stats` (wald\_p\_value, ci\_lower, ci\_upper).
* `artefacts/gdp/gdp_bucket_map_2024.parquet` – Jenks bucket mapping table.
* `artefacts/network_share_vectors/settlement_shares_2024Q4.parquet` – currency‑level settlement share vectors (semver, SHA‑256 digest).
* `artefacts/currency_country_split/ccy_country_shares_2024Q4.parquet` – intra‑currency proportional country splits (with per‑cell observation counts).
* Stationarity diagnostics: `artefacts/diagnostics/hurdle_stationarity_tests_2024Q4.parquet`.
* (Spatial priors digests are included in the manifest even though not consumed here to ensure downstream cannot silently alter upstream decisions.)

Each file’s SHA‑256 digest (hex64) is computed; coefficient and hyperparameter YAML digests are concatenated (ordered lexicographically by filename) and hashed (SHA‑256) to form a `parameter_hash`. All artefact digests, the git commit hash and the `parameter_hash` are XOR‑reduced then hashed (SHA‑256) to produce the **manifest fingerprint** (hex64). The fingerprint seeds the master Philox 2¹²⁸ counter and is embedded in every output row and in `_manifest.json`. Any byte change (including whitespace/comments) to a digested artefact yields a different fingerprint and therefore a distinct catalogue lineage.

### 2. GDP Buckets & Stationarity

GDP per capita (constant 2015 USD) values come from the World Bank “World Development Indicators” vintage published 2025‑04‑15; CSV digest recorded. Values are mapped into five Jenks natural break buckets (1–5); the mapping table path and digest are manifest entries (`gdp_bucket_map_digest`, `gdp_bucket_map_semver`). The developmental bucket is *only* used in the hurdle logistic; it is **intentionally excluded** from the NB mean to avoid collinearity with the dispersion GDP term and to maintain parsimony. Stationarity over 2020–2028 is supported by a rolling 12‑quarter Wald test suite (α=0.01); test outputs are digested (`stationarity_test_digest`) and referenced in the relevant YAMLs.

### 3. Design Matrices & Model Forms

**Hurdle Logistic:**
Predictors = intercept + MCC dummies + channel dummies + developmental (GDP) bucket dummies. **The full hurdle coefficient vector \(\beta = (\beta_{0}, \beta_{\text{mcc}}, \beta_{\text{channel}}, \beta_{\text{dev}})\) is stored wholesale inside `hurdle_coefficients.yaml`; there is no separate external parameter (e.g. `γ_{dev}`) — ensuring a single provenance point for all logistic terms.

$$
\pi = \sigma( \mathbf x^\top \beta)
$$

**Negative Binomial (multi‑site only):**
Mean log‑link (μ): intercept + MCC dummies + channel dummies.
Dispersion log‑link (φ): same categorical set + continuous log(GDPpc) (natural log, GDPpc in constant 2015 USD). η > 0 enforced (profile likelihood); typical fitted η ∈ \[0.15, 0.35].

$$
\log \mu = \alpha_0 + \alpha_{\text{mcc}} + \alpha_{\text{channel}},\quad
\log \phi = \delta_0 + \delta_{\text{mcc}} + \delta_{\text{channel}} + \eta \log(\text{GDPpc})
$$

**Parameter Mapping:**
NB(μ, φ) is equivalent to NB(r=φ, p=φ/(φ+μ)). Implementation uses Poisson–Gamma mixture: draw $G \sim \text{Gamma}(r=\phi, \text{scale}=\mu/\phi)$; then $N \sim \text{Poisson}(G)$. Both forms (μ, φ, r, p) and intermediate draws are logged.

### 4. Random Number Generation & Logging

Philox 2¹²⁸ master seed = H(manifest fingerprint || run seed). Each stochastic *event* logs a structured row:

`timestamp_utc, event_type, merchant_id, pre_counter, post_counter, parameter_hash, draw_sequence_index, rejection_flag (bool), [event-specific fields...]`.

Sub‑stream jump strides = first 64 little‑endian bits of SHA‑256 of a string key; logged as `event_type='stream_jump'` with `module`, `hash_source`, `stride_uint64`. Mandatory event types:

* `hurdle_bernoulli` (fields: uniform\_u, pi, outcome, substream\_stride)
* `gamma_component` (NB mixture: gamma\_shape, gamma\_scale, gamma\_value)
* `poisson_component` (lambda, draw\_value)
* `nb_final` (nb\_mu, nb\_phi, nb\_r, nb\_p, draw\_value, rejection\_count\_prior)
* `ztp_rejection` (lambda\_extra, rejected\_value, cumulative\_rejections)
* `ztp_retry_exhausted` (lambda\_extra, rejection\_count)
* `gumbel_key` (country\_iso, weight, uniform\_u, key\_value)
* `dirichlet_gamma_vector` (alpha\_digest, gamma\_values\[], summed\_gamma, w\_vector\[])
* `stream_jump` (module, hash\_source, stride\_uint64)
* `sequence_finalize` (merchant\_id, country\_iso, site\_count, start\_sequence, end\_sequence)

Absence of any required event for a merchant constitutes a validation failure.

### 5. Hurdle Decision

Sub‑stream key: `"hurdle_bernoulli"`. Draw $ u\sim U(0,1)$; if $u < \pi$ merchant is multi‑site, else single‑site with N=1. Logged as above with full parameters. Outcome persisted as `single_vs_multi_flag`.

### 6. Negative Binomial Outlet Count (Multi‑site)

Draws via Poisson–Gamma mixture. Rejection rule: if N ∈ {0,1} redraw until N ≥ 2. Monitoring corridor: overall NB rejection rate ∈ \[0, 0.06]; 99th percentile of per‑merchant rejection counts ≤ 3. Control chart: one‑sided CUSUM on deviation from baseline (initialised after first 500k merchants) with h=5σ abort threshold. Metrics are logged to diagnostic parquet each run.

### 7. Zero‑Truncated Poisson for Foreign Country Count

Only merchants that passed the hurdle and are designated to attempt cross‑border expansion enter this branch. K \~ ZTPoisson(λ\_extra) with λ\_extra = θ₀ + θ₁ log N (θ₁ < 1, Wald p-value < 1e−5; stored as `theta1_stats`). True zero‑truncation implemented by rejection sampling: draw from Poisson(λ\_extra) until k ≥1 (recording rejections). Hard cap: 64 rejections → abort (`ztp_retry_exhausted`). Targets: mean rejection count <0.05; p99.9 <3; violations abort.

### 8. Currency → Country Expansion & Weights

Settlement share vector s^(ccy) at currency level; multi‑country currency expansion:

1. Load intra‑currency proportional weights (and observation counts).
2. Apply additive Dirichlet smoothing α=0.5 to per‑destination counts.
3. If any destination count <30, smoothed value used; if *total* post-smoothing mass insufficient (total obs < 30 + 0.5\*D), fall back to equal split (flag `sparse_flag=true`).
4. Renormalise to produce country weight vector (ordered deterministically by ISO).
5. Cache expanded vector keyed by currency to avoid extra RNG consumption.

Single‑country currencies map 1:1.

### 9. Foreign Country Selection

Weighted sampling without replacement of K foreign countries uses **Gumbel‑top‑k**:

For country i with weight w\_i, draw uniform u\_i; compute key\_i = log w\_i − log(−log u\_i). Select K largest keys; ties broken by ISO lexicographic order. Logs: each (country\_iso, u\_i, w\_i, key\_i), selected order. This consumes exactly one uniform per candidate. Selected foreign ISO codes maintain the Gumbel order.

### 10. Dirichlet Allocation of Outlets Across Countries

Country set length = K+1 (home + K selected foreign in the sampled order). α vector looked up for (home\_country, MCC, channel); length must equal K+1. Dirichlet sampling:

* For each i: draw G\_i \~ Gamma(α\_i, 1) via Marsaglia–Tsang (IEEE‑754 binary64).
* Disable fused‑multiply‑add operations; deterministically sum S = Σ G\_i (serial order).
* Set w\_i = G\_i / S; record raw G\_i and w\_i (rounded to 8 dp).

Integer allocation (largest‑remainder):

1. Compute real allocations w\_i N.
2. Floor each: n\_i^floor = floor(w\_i N).
3. Residuals r\_i = w\_i N − n\_i^floor; quantise r\_i to 8 dp.
4. Sort residuals descending; break ties by ISO code (ASCII).
5. Let d = N − Σ n\_i^floor. Since Σ w\_i = 1, 0 ≤ d < (K+1); if d=0 no adjustments. Otherwise add +1 to first d indices in sorted list.
6. Persist ordering index as `tie_break_rank`.

Bound justification: worst‑case |n\_i − w\_i N| ≤ 1, so relative allocation error ≤ 1/N; validation records deviations and aborts if any |n\_i − w\_i N| >1. Empirical report includes max and p99.9 deviations; expected relative error <0.3% for small N (e.g., N=3, K=2).

Formal proof of d bound and determinism resides in `docs/derivations/dirichlet_lrr_proof.md` (digest logged).

### 11. Site ID Sequencing & Schema

Ordering: sort rows by `country_iso` ascending, then by `tie_break_rank`, then assign fixed 6‑digit zero‑padded sequence per (merchant\_id, country\_iso) block beginning at 000001. Overflow beyond 999999 outlets in a block aborts build (`site_sequence_overflow`, none expected). Event logged: `sequence_finalize`.

**Outlet stub schema (non‑nullable):**

| Column                        | Type          | Description                                        |
| ----------------------------- | ------------- | -------------------------------------------------- |
| merchant\_id                  | int64         | Original merchant identifier                       |
| site\_id                      | string `%06d` | Per-merchant+country sequence (6 digits)           |
| home\_country\_iso            | char(2)       | Onboarding country (source for GDP bucket)         |
| legal\_country\_iso           | char(2)       | Country of this outlet (home or foreign)           |
| single\_vs\_multi\_flag       | bool          | 0=single-site, 1=multi-site                        |
| raw\_nb\_outlet\_draw         | int32         | Raw NB draw N (≥2 if multi-site; 1 else)           |
| final\_country\_outlet\_count | int32         | n\_i for this country                              |
| tie\_break\_rank              | int32         | Position after residual sort (for forensic replay) |
| manifest\_fingerprint         | char(64)      | Catalogue lineage identifier                       |
| global\_seed                  | uint64        | Master seed (derivable from manifest)              |

Encoding: integers little‑endian; ISO codes dictionary‑encoded; compression ZSTD level 3; codec choice hashed. Schema version embedded; any column/order/type change → semver bump and fingerprint change.

### 12. Post‑Write Validation

After writing the Parquet catalogue, a validation routine recomputes μ, φ, K, Dirichlet weights, residual ordering, integer allocations, tie\_break\_rank, and site\_id sequence from persisted inputs; mismatch aborts build. Presence and uniqueness of mandatory RNG events per merchant are checked; missing events abort.

### 13. Monitoring & Metrics

Nightly CI collects:

* `nb_rejection_rate_overall`; `nb_rejections_p99`; CUSUM status.
* ZTP mean and p99.9 rejection counts.
* Rounding deviations (max |n\_i − w\_i N|, p99.9).
* Sparse expansion incidence (`sparse_flag` rate).
* Presence counts for each `event_type` (should equal merchant or candidate counts).
* Parameter drift: digest changes trigger full rebuild; stationarity test non‑rejection confirmed.
* θ₁ significance check (p < 0.001 enforced).

Metrics outside corridors cause build failure (not warning).

### 14. Numeric Environment & Determinism

All stochastic arithmetic uses IEEE‑754 binary64. Residual fractions quantised to 8 decimal places pre‑sort. Serial (non‑parallel) reductions ensure consistent sum order. Fused‑multiply‑add disabled for Dirichlet and residual operations. Any deviation from these numeric constraints requires a documentation update and semver bump.

### 15. Explicit Assumption Inventory

* Logistic coefficients and NB mean/dispersion coefficients are stationary over the simulation horizon (empirical Wald tests log).
* λ\_extra follows log‑linear form with sub‑linear elasticity (θ₁ < 1, statistically significant).
* Largest‑remainder rounding deviation ≤ 1 per country is acceptable; empirical bound logged each run.
* Currency → country proportional split plus smoothing accurately reflects relative cross‑border settlement; sparse fallback flagged.
* Sequence width 6 digits suffices for expected outlet counts; overflow aborts ensure no silent truncation.
* All randomness reproducible via logged pre/post counters and parameter snapshots; any missing log entry invalidates the build.
* Any unstated behaviour is *not* allowed; additions must be documented and digest‑tracked.

### 16. Closure / Immutability Guarantee

Outlet counts (N), foreign country count (K), per‑country allocations (n\_i), and schema fields become immutable inputs to downstream sub‑segments. Downstream code reading the catalogue must treat these as read‑only; any attempt to mutate them would change artefacts and produce a new manifest fingerprint, ensuring lineage separation.

---

**Reproducibility Assertion:** Given (a) master seed, (b) manifest fingerprint, and (c) catalogue Parquet, an auditor can reconstruct every stochastic decision path (hurdle, NB rejections, ZTP rejections, Gumbel keys, Dirichlet gamma draws, rounding order, site sequencing) without access to proprietary training data—verifying that no hidden state influenced the sub‑segment outputs.
