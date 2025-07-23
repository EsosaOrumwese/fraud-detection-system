## Assumptions

The validation layer rests on a lattice of explicit premises, each tied to a concrete artefact, a deterministic code path, a manifest fingerprint, and an automated alarm in CI. The lattice begins with structural integrity. The validator opens every Parquet partition in round‑robin order and, for each row, feeds the geographic coordinates—`latitude, longitude` for physical merchants or the `ip_latitude, ip_longitude` pair for virtual ones—into the same tz‑world spatial index whose shapefile digest (`tz_polygon_digest`) was sealed earlier in the manifest. The point‑in‑polygon query must echo back the row’s `tzid_operational`; disagreement triggers `StructuralError`, writes the offending row plus its Philox jump offset to `structural_failure_<parameter_hash>.parquet`, and stops the build. Because the index digest is fixed, the validator cannot accidentally consult a different map.

Immediately after the coordinate round‑trip, the timestamp legality check recomputes local civil time as $\texttt{event_time_utc} + 60 * \texttt{local_time_offset}$ converts it through the zoneinfo release pinned by `zoneinfo_digest`, and demands bit‑level equality with the original local time stored in the row buffer. A mismatch raises `DstIllegalTimeError` and emits a reproducer script. Daylight‑saving consistency is verified by comparing each candidate local epoch second to the zone’s DST transition table; any second that lies in a spring gap or fails to carry a correct `fold` bit in the autumn fold also raises `DstIllegalTimeError`. Concurrently, the schema firewall asserts that nullable columns obey the merchant’s `is_virtual` flag and that every required field is finite under Fastavro’s runtime schema compiled from `transaction_schema.json`—the schema’s digest (`schema_digest`) prevents silent swaps.

Provided every row survives structural scrutiny, the validator shifts into adversarial indistinguishability mode. Every transaction streams through `adv_embed.embed_6d` (source digest `adv_embed_digest`), projecting it into a six‑dimensional vector of sine/cosine of local hour, sine/cosine of day‑of‑week, and Mercator‑projected latitude/longitude. A window of 200 000 such vectors—half synthetic, half drawn from the GDPR‑sanitised real reference slice—is fed into the XGBoost classifier whose hyper‑parameters (`adv_conf_digest`) are locked in `validation_conf.yml`. The validator computes AUROC every `auroc_interval` rows (configured in `validation_conf.yml`); if AUROC exceeds the cut‑line (`auroc_cut = 0.55`), it halts, dumps model artefacts and misclassified indices to `/tmp/auroc_failure`, and raises `DistributionDriftDetected`, ensuring reproducibility via the recorded RNG jump in `rng_trace.log`.

With adversarial drift defeated, the narrative moves to semantic congruence. Hourly legitimate transaction counts per site are joined to the immutable foot‑traffic scalars in `site_catalog.parquet`; the Poisson GLM in `semantic_glm.py` regresses counts on a cubic spline for hour‑of‑day plus merchant‑day random intercepts. The dispersion estimate θ must reside within the corridor specified in `footfall_coefficients.yaml`—1 to 2 for card‑present channels, 2 to 4 for CNP. If θ escapes this corridor, the validator labels the YAML with a Git attribute `needs_recalibration`, emits `glm_theta_violation.pdf`, and raises `ThetaOutOfRange`, preventing silent variance drift.

The fourth strand is the offset‑barcode examination. Transactions are binned into a matrix of UTC hour versus `local_time_offset`, and a Hough transform in `barcode.py` (digest pinned) extracts the dominant line, translating accumulator space back into a slope in minutes per hour. The allowable band, recorded in `barcode_bounds.yml`, is \[–1,–0.5]. A slope outside this range triggers `BarcodeSlopeError`, draws a red overlay on the heat‑map stored as `barcode_failure_<merchant_id>.png`, and archives it in CI.

Every artefact used above maps to a licence file defined in `artefact_registry.yaml`. During validation `validate_licences.py` recomputes SHA‑1 digests for each licence and compares them to the `licence_digests` field in the manifest; any mismatch raises `LicenceMismatchError`, preventing datasets whose legal pedigree has drifted.

When all structural, adversarial, semantic, and barcode passes return clean, the validator appends `validation_passed=true` to the manifest, hashes the entire `validation/<parameter_hash>/` directory (storing section‑level digests `structural_sha256`, `adv_sha256`, `semantic_sha256`, `barcode_sha256`), and uploads the bundle to HashGate at `/hashgate/<parameter_hash>/<master_seed>`. The GitHub pull‑request action then polls this URI, retrieves the manifest, recomputes its SHA‑256, and blocks merge on any byte mismatch. Once merge proceeds, the dataset directory—its name containing the `parameter_hash`—mounts read‑only on NFS, and the Postgres registry enforces uniqueness of `(parameter_hash, seed, path)`, forbidding any silent regeneration with altered contents.

Because every premise—coordinate validity against tz‑world, civil‑time reconstruction via zoneinfo, adversarial hyper‑parameters, dispersion corridors, physical‑laws‑based barcode slopes, and licence integrity—resolves to a manifest digest and an automated CI guard, any deviation surfaces immediately. The validator thus fulfills the contract begun in the reproducibility layer, delivering a synthetic ledger whose provenance, correctness, and configurability are exhaustively documented and machine‑verified.

## Appendix A–Mathematical Definitions & Conventions

### **A.1 Parameter‑Set Hash & Manifest Fingerprint**
For each artefact file $f_i$, let

$$
D_i = \mathrm{SHA256}\bigl(\texttt{read\_bytes}(f_i)\bigr)
$$

be its 256‑bit digest (hex‑encoded).  Order the files by lexicographic path and form the concatenation

$$
\mathit{concat} = D_1 \parallel D_2 \parallel \dots \parallel D_n.
$$

The **parameter‑set hash** $P$ is then

$$
P = \mathrm{SHA256}(\mathit{concat}).
$$

Concurrently, an XOR‑reducer computes

$$
X = D_1 \oplus D_2 \oplus \cdots \oplus D_n,\quad
\text{then}\quad P = \mathrm{SHA256}(X).
$$

### **A.2 Master Seed Construction**
Let $t_{\mathrm{ns}}$ denote the monotonic clock reading in nanoseconds (`time_ns()`).  Define

$$
T = t_{\mathrm{ns}} \ll 64,\quad
L = P \bmod 2^{128},\quad
\mathit{master\_seed} = T \oplus L,
$$

where $\ll$ is a 64‑bit left shift and $\oplus$ is bitwise XOR on 128‑bit values.

### **A.3 Philox Counter Jump**
Each module declares a string `STREAM_NAME`.  Compute its 128‑bit stride

$$
h = \mathrm{SHA1}(\mathrm{STREAM\_NAME}) \bmod 2^{128}.
$$

Given the current Philox counter $c\in[0,2^{128}-1]$, the new counter is

$$
c' = (c + h)\bmod 2^{128}.
$$

All random draws use Philox 2¹²⁸ with AES‑round mixing; each call to `_jump(h)` advances the counter accordingly.

### **A.4 Truncated‑Normal Bootstrap for YAML Parameters**
For each coefficient with reported mean $\mu$, lower CI $\ell$, upper CI $u$ (90 %), set

$$
\sigma = \frac{u - \ell}{2\,z_{0.95}},\quad z_{0.95}\approx1.645.
$$

Draw bootstrap replicates

$$
X_j\sim \mathcal{N}(\mu,\sigma^2)\quad\text{truncated to }[\ell,u],\quad j=1\ldots100,
$$

i.i.d., and regenerate synthetic outputs for envelope validation.

### **A.5 Conjugate Beta‑Posterior Intervals**
Let $\alpha_i$ be the prior for zone $i$ from `country_zone_alphas.yaml`, and $k_i$ the observed outlet count out of total $N$.  The posterior for the true share $\theta_i$ is

$$
\theta_i \sim \mathrm{Beta}\bigl(\alpha_i + k_i,\;\sum_j\alpha_j + N - k_i\bigr),
$$

and the 95 % credible interval is

$$
\bigl[F^{-1}_{\theta_i}(0.025),\,F^{-1}_{\theta_i}(0.975)\bigr],
$$

where $F^{-1}$ is the Beta quantile.

### **A.6 Poisson GLM Over‑dispersion Parameter**
For the footfall–throughput Poisson GLM with link $\log$, fitted values $\hat y_i$ and observations $y_i$, dispersion is estimated as

$$
\hat\phi = \frac{\sum_{i=1}^n \frac{(y_i - \hat y_i)^2}{\hat y_i}}{\,n - p\,},
$$

with $n$ samples and $p$ predictors.  Acceptable $\hat\phi\in[1,2]$ for CP and $[2,4]$ for CNP.

### **A.7 DST Gap & Fold Enumeration**
Let $\tau_s,\tau_e$ be the local epoch seconds bracketing a DST spring gap; the gap interval is $[\tau_s,\tau_e)$.  Define the fold interval at autumn likewise.  For each minute $m$ in a 48 h window, the validator asserts

$$
m\notin[\tau_s,\tau_e),\quad\text{and}\quad
\bigl|\#\{m\}\bigr|=2\quad\text{if }m\in[\tau_f,\tau_f+3600).
$$

### Variable Definitions
Here is a complete glossary of every symbol and variable used in Appendix A:

| Symbol                  | Definition                                                                                                                  |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| $f_i$                   | The $i$th artefact file path, exactly as listed in `artefact_registry.yaml`.                                                |
| $D_i$                   | The 256‑bit SHA‑256 digest of $f_i$: $\mathrm{SHA256}(\texttt{read\_bytes}(f_i))$.                                          |
| $\mathit{concat}$       | The byte string $D_1\parallel D_2\parallel\cdots\parallel D_n$, with digests ordered by lexicographic file path.            |
| $X$                     | The XOR‑reduced 256‑bit accumulator: $X = D_1\oplus D_2\oplus\cdots\oplus D_n$.                                             |
| $P$                     | The **parameter‑set hash**, a 256‑bit value: $P = \mathrm{SHA256}(\mathit{concat})$ (or equivalently $\mathrm{SHA256}(X)$). |
| $t_{\mathrm{ns}}$       | The monotonic clock reading in nanoseconds, as returned by `time_ns()`.                                                     |
| $T$                     | The high‑64‑bits of the master seed: $T = t_{\mathrm{ns}} \ll 64$.                                                          |
| $L$                     | The low‑128‑bits of $P$: $L = P \bmod 2^{128}$.                                                                             |
| $\mathit{master\_seed}$ | The 128‑bit PRNG seed: $\mathit{master\_seed} = T \oplus L$.                                                                |
| $\mathrm{STREAM\_NAME}$ | The canonical identifier string for a Philox sub‑stream (e.g. `"multi_site_hurdle"`).                                       |
| $h$                     | The 128‑bit jump offset: $h = \mathrm{SHA1}(\mathrm{STREAM\_NAME}) \bmod 2^{128}$.                                          |
| $c, c'$                 | The Philox counter before and after jump: $c' = (c + h)\bmod 2^{128}$.                                                      |
| $\mu$                   | The reported mean of a statistical coefficient (YAML `mean` field).                                                         |
| $\ell$                  | The lower bound of its 90 % CI (YAML `ci_lower`).                                                                           |
| $u$                     | The upper bound of its 90 % CI (YAML `ci_upper`).                                                                           |
| $\sigma$                | Standard deviation for bootstrap: $\sigma = (u-\ell)/(2\,z_{0.95})$, with $z_{0.95}\approx1.645$.                           |
| $X_j$                   | One truncated‑normal bootstrap draw: $X_j\sim\mathcal{N}(\mu,\sigma^2)$ truncated to $[\ell,u]$.                            |
| $\alpha_i$              | Prior concentration for zone $i$ from `country_zone_alphas.yaml`.                                                           |
| $k_i$                   | Observed outlet count in zone $i$.                                                                                          |
| $N$                     | Total outlet count across all zones ($\sum_i k_i$).                                                                         |
| $\theta_i$              | True (latent) share of outlets in zone $i$; posterior $\mathrm{Beta}(\alpha_i+k_i,\sum_j\alpha_j+N-k_i)$.                   |
| $F^{-1}$                | Quantile (inverse CDF) function of a Beta distribution.                                                                     |
| $y_i$                   | Observed count in the $i$th hour for the Poisson GLM.                                                                       |
| $\hat y_i$              | Model‑predicted mean for the $i$th hour in that GLM.                                                                        |
| $n$                     | Number of observations (hours) in the GLM.                                                                                  |
| $p$                     | Number of predictors (including intercept) in the GLM.                                                                      |
| $\hat\phi$              | Estimated over‑dispersion: $\hat\phi = \frac{\sum (y_i-\hat y_i)^2/\hat y_i}{\,n-p\,}$.                                     |
| $\tau_s,\tau_e$         | Local epoch seconds marking the start/end of a DST spring gap.                                                              |
| $\tau_f$                | Epoch second at the start of the DST autumn fold interval.                                                                  |
| $m$                     | A minute‑resolution timestamp in the 48 h window tested by the DST edge‑passer.                                             |

This glossary covers all variables and symbols used in the mathematical definitions.

## Appendix B – Governing Artefact Registry

| Artefact Class                | Path Pattern                              | SemVer Field | Digest Field             |
| ----------------------------- | ----------------------------------------- | ------------ | ------------------------ |
| Artefact Registry YAML        | `artefact_registry.yaml`                  | N/A          | N/A                      |
| Validation Configuration      | `config/validation_conf.yml`              | `version`    | `validation_conf_digest` |
| Footfall Coefficients         | `config/footfall_coefficients.yaml`       | `version`    | `footfall_coeff_digest`  |
| Barcode Bounds                | `config/barcode_bounds.yml`               | `version`    | `barcode_bounds_digest`  |
| Transaction Schema JSON       | `schemas/transaction_schema.json`         | N/A          | `schema_digest`          |
| Zoneinfo Version YAML         | `config/zoneinfo_version.yml`             | N/A          | `zoneinfo_digest`        |
| Time‑Zone Shapefile           | `tz_world_2025a.shp`                      | N/A          | `tz_polygon_digest`      |
| Site Catalogue Parquet        | `{dataset_root}/site_catalogue/*.parquet` | N/A          | `creator_param_hash`     |
| Transaction Catalogue Parquet | `{dataset_root}/transactions/*.parquet`   | N/A          | `creator_param_hash`     |
| RNG Audit Log                 | `{dataset_root}/logs/rng_trace.log`       | N/A          | `rng_trace_digest`       |



