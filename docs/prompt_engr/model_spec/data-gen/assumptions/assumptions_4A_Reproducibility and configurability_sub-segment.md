## Main
The very first premise is that the build always executes inside the Docker image whose **content‑hash lives in `Dockerfile.lock`**. `pipeline_launcher.sh` reads the lock file’s `IMAGE_SHA256=` line, passes the digest to `docker run --pull=never`, then writes three items—container hash, container hostname, UTC start time—to the first three fields of a run‑local manifest at `/tmp/build.manifest`. CI job `validate_container_hash.yml` starts a sibling container from the same digest and hashes the root file system; any mismatch halts the workflow before a single artefact is touched.

Source code immutability follows. `git rev-parse --verify HEAD` exports the exact tree hash of the checked‑out repository; that forty‑character SHA‑1 becomes `source_sha1` on line 4 of the manifest. The generator’s internal version string is pulled from `fraudsim/__init__.py`; the file is decorated with `__codehash__ = "<TREE_SHA1>"`. At runtime `importlib.metadata.version` emits that same string, and a guard inside `main.py` raises `SourceHashMismatchError` if the embedded SHA‑1 differs from the manifest entry. Thus hot‑patching any Python file between container start and dataset write is impossible without detection.

No artefact may influence sampling unless it appears in **`artefact_registry.yaml`**. This registry’s top level is an ordered list of absolute POSIX paths. Additionally, the registry includes a `license_map` section whose keys are the artefact paths listed above and whose values are the corresponding licence file names under the `LICENSES/` directory. `artefact_loader.py` loops in lexical order, opens each path in binary mode, streams it into `sha256sum` and appends `digest  path` to the manifest. Simultaneously a `hashlib.sha256()` accumulator ingests `digest\n` bytes for every artefact. Once enumeration ends the accumulator’s hex digest becomes the **parameter‑set hash**—the 256‑bit signature of all configuration. The parameter‑set hash is also inserted as a comment field `creator_param_hash=<hash>` in every Parquet schema and supplied as the argument to the random‑seed constructor in the form `master_seed_hex=<hash>`. `dataset_root = f"synthetic_v1_{param_hash}"` ensures that two runs differing by even one artefact byte land in different directories. CI step `compare_registry.py` regenerates the enumeration under a fresh interpreter and asserts that the manifest’s artefact list and the re‑enumeration are byte‑identical.

Randomness revolves around that parameter hash. The **master seed** is produced by taking the high‑resolution monotonic clock `time_ns()`, left‑shifting by 64 bits, then XOR‑ing with the low 128 bits of `param_hash`. The seed is printed onto line 5 of the manifest (`master_seed_hex=`) and passed to NumPy’s `Philox` constructor. Every module defines a static string `STREAM_NAME`, hashed with SHA‑1 to 128 bits; at module entry, code calls `rng._jump(int.from_bytes(stream_hash, 'big'))`. Because `_jump` is additive modulo 2¹²⁸, streams remain non‑overlapping. The *jump offset* is recorded per invocation in `logs/rng_trace.log` as `module,identifier,offset`. `replay_rng.py` in CI parses the trace, reproduces the counter state, draws the first three random numbers for spot‑check, and fails if any differ.

Configurability is confined to YAMLs validated by JSON Schema. Each YAML begins with a header:

```yaml
schema: "jp.fraudsim.<domain>@<major>"
version: "<semver>"
released: "<YYYY‑MM‑DD>"
```

The loader maps the `<domain>` identifier to a local `schemas/<domain>.json`, checks the `major` matches, and raises `SchemaVersionError` if the YAML’s major exceeds the generator’s expectation. Numeric entries meant to be statistical estimators must include `mean, ci_lower, ci_upper`. After loading, `bootstrap_validator.py` draws one hundred truncated‑normal replicates from each triplet, re‑runs the generator on a 50 000‑row dry slice, and checks that synthetic histograms lie within the 90 % predictive envelope. If any bucket fails, the YAML gains a Git label “needs‑tune” and CI refuses merge.

Collision prevention is anchored in Postgres catalog **`datasets(id, parameter_hash, seed, path)`**. `register_dataset.py` inserts the triple and declares `parameter_hash, seed` unique. If an attempt is made to write a different `path` under the same `(parameter_hash, seed)`, Postgres throws `UNIQUE_VIOLATION`; the CLI surfaces the error as “parameter collision—increment YAML versions.” This rule guarantees that no two semantic parameter sets ever masquerade behind the same seed.

The **structural firewall** is coded in `firewall.py`. It streams generated records in batches of 50 000. Each batch undergoes five vectorized checks: (1) either `latitude` or `ip_latitude` is finite; (2) `tzid` belongs to the zoneinfo build `zoneinfo_version.yml`; (3) `event_time_utc + 60*local_time_offset` converts to the stated `tzid` via `zoneinfo.ZoneInfo`; (4) no illegal time stamps in DST gaps; (5) `fold` flag equals 0/1 only on repeated local hours. On first violation a reproducer file is written with the offending row and RNG offset; CI fails citing the reproducer path.

**Geospatial conformance** relies on conjugate beta bounds. `country_zone_alphas.yaml` yields for each `(country_iso, tzid)` the alpha vector. When generation ends `geo_audit.py` tallies outlets, forms beta posterior intervals at 95 %, and asserts synthetic share sits inside. If not, the script prints `(country, tzid, posterior_interval, observed_share)` and CI fails.

The **outlet‑count bootstrap** re‑inverts the hurdle coefficients. From `hurdle_coefficients.yaml` it reconstructs the logit and NB regressions; draws 10 000 bootstrap coefficient vectors; simulates chain‑size histograms; and overlays synthetic counts. If the synthetic count in any size bucket falls outside the bootstrap’s 95 % envelope, the histogram is saved as PNG, the YAML gains label “retune‑hurdle,” merge is blocked.

The **footfall model check** fits a Poisson GLM with spline basis to hourly counts versus `log_footfall`. Dispersion parameter θ must land in `[1,2]` for card‑present and `[2,4]` for CNP. If θ drifts outside, `footfall_coefficients.yaml` gets flagged.

For **multivariate indistinguishability** the harness samples 200 000 rows (split real vs. synthetic), embeds each into ℝ⁶ (sin/cos hour, sin/cos day‑of‑week, latitude, longitude) and trains XGBoost with fixed depth and learning rate. The XGBoost seed is the Philox counter after `bootstraps`, guaranteeing deterministic AUROC. If AUROC≥0.55, CI fails.

**DST edge passer** iterates every DST‑observing `tzid`. For each simulation year it builds a 48‑h schedule around both transitions, checks: no timestamps in gaps, all repeated minutes appear twice, offsets flip by exactly ±60 min. Failure produces a CSV `dst_failures.csv` and blocks merge.

All validation outputs—CSV, PNG, GLM tables—are written under `validation/{parameter_hash}/`. `upload_to_hashgate.py` posts the manifest, validation flag, and artefact URL to HashGate. Pull‑request lint rule `.github/workflows/block_merge.yml` polls HashGate; merge gates on `validation_passed=true`.

Licences must accompany artefacts. `artefact_registry.yaml` maps each artefact path to a licence path. CI job `validate_licences.py` verifies every artefact has a licence and that the licence text’s SHA‑1 is listed in `manifest.licence_digests`. Replacing an artefact without updating its licence digest stalls the pipeline.

Finally, dataset immutability: the dataset directory name embeds `parameter_hash`. NFS exports it read‑only. Any attempt to regenerate with the same hash but different contents throws `OSError: read‑only file system`, forcing version bump.


## Appendix A – Mathematical Definitions & Conventions

**A.1 Parameter‑Set Hash & Manifest Fingerprint**
For each artefact file $f_i$, let

$$
D_i = \mathrm{SHA256}\bigl(\texttt{read\_bytes}(f_i)\bigr)
$$

be its 256‑bit digest (hex‑encoded).  These digests are concatenated in lexicographic order of file paths to form the byte string
$\mathit{concat} = D_1 \parallel D_2 \parallel \dots \parallel D_n$.  The **parameter‑set hash** $P$ is then

$$
P = \mathrm{SHA256}(\mathit{concat})\,.
$$

Simultaneously, an intermediate accumulator applies bitwise XOR across the raw digest bytes:

$$
X = D_1 \oplus D_2 \oplus \cdots \oplus D_n,\quad 
P = \mathrm{SHA256}(X).
$$

**A.2 Master Seed Construction**
Let $t_{\mathrm{ns}}$ be the high‑resolution monotonic clock in nanoseconds.  Define

$$
T = t_{\mathrm{ns}} \ll 64,\quad
L = P \bmod 2^{128},\quad
\mathit{master\_seed} = T \;\oplus\; L,
$$

where $\ll$ is the 64‑bit left shift and $\oplus$ is bitwise XOR on 128‑bit values.

**A.3 Philox Counter Jump**
Each module declares a canonical identifier $\mathrm{STREAM\_NAME}$.  Compute

$$
h = \mathrm{SHA1}(\mathrm{STREAM\_NAME}) \bmod 2^{128}.
$$

Given the current counter $c\in[0,2^{128}-1]$, the new counter is

$$
c' = (c + h)\bmod 2^{128}.
$$

All RNG draws use Philox 2¹²⁸ with AES‑round mixing; every call to `_jump(h)` advances the counter accordingly.

**A.4 Truncated‑Normal Bootstrap for Yaml Parameters**
For each statistical parameter block with reported
$\mu$ (mean), $\ell$ (ci\_lower), and $u$ (ci\_upper) from a 90% CI, define

$$
\sigma = \frac{u - \ell}{2\,z_{0.95}},\quad
X \sim \mathcal{N}(\mu,\sigma^2)\quad\text{truncated to }[\,\ell,\,u\,],
$$

where $z_{0.95}\approx1.645$.  Bootstrap replicates $\{X_j\}_{j=1}^{100}$ are drawn i.i.d. and used to regenerate synthetic outputs for validation.

**A.5 Conjugate Beta‑Posterior Intervals**
For geospatial conformance, let $\alpha_i$ be the prior weight for zone $i$ from `country_zone_alphas.yaml`, and let $k_i$ be the observed outlet count in that zone out of total $N$.  The posterior on the true share $\theta_i$ is

$$
\theta_i \sim \mathrm{Beta}\bigl(\alpha_i + k_i,\;\sum_j\alpha_j + N - k_i\bigr).
$$

The 95% credible interval is taken as
$\bigl[\,F^{-1}_{\theta_i}(0.025),\,F^{-1}_{\theta_i}(0.975)\bigr]$,
where $F^{-1}$ is the Beta quantile function.

**A.6 Poisson GLM Over‑dispersion Parameter**
In the footfall–throughput regression, we fit
$\mathrm{E}[Y]=\exp(\mathbf{x}^\top\beta)$ for counts $Y$.  The dispersion parameter $\phi$ is estimated by

$$
\hat\phi = \frac{\sum (y_i - \hat y_i)^2 / \hat y_i}{n - p},
$$

where $n$ is the sample size and $p$ the number of predictors.  Acceptable bounds are $\phi\in[1,2]$ for card‑present, $\phi\in[2,4]$ for CNP.

**A.7 DST Gap & Fold Enumeration**
For each zone observing DST: let
$\tau_s$ and $\tau_e$ be the local timestamps at spring gap start and end.  The **gap interval** is $[\tau_s,\tau_e)$.  The **fold interval** at autumn is likewise the repeated hour.  Validation enumerates every minute $m$ in a 48‑h window around each transition, asserting:

$$
m\notin[\tau_s,\tau_e),\quad \text{and}\quad m\text{ appears twice if }m\in[\tau_f,\tau_f+60\mathrm{m}).
$$

### Variable Definitions
Below is a complete glossary of every symbol and variable used in Appendix A, with precise definitions drawn from those formulas.

| Variable                | Definition                                                                                                                                     |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| $f_i$                   | The $i$th artefact file path, as declared in `artefact_registry.yaml`.                                                                         |
| $D_i$                   | 256‑bit SHA‑256 digest of the bytes of file $f_i$: $\mathrm{SHA256}(\texttt{read\_bytes}(f_i))$.                                               |
| $\mathrm{concat}$       | Byte string formed by concatenating $D_1\parallel D_2\parallel\cdots\parallel D_n$ in lexicographic order of $f_i$.                            |
| $X$                     | Intermediate 256‑bit accumulator: $X = D_1 \oplus D_2 \oplus \cdots \oplus D_n$ (bitwise XOR).                                                 |
| $P$                     | **Parameter‑set hash**, the final 256‑bit manifest fingerprint: $P = \mathrm{SHA256}(\mathrm{concat})$ (or equivalently $\mathrm{SHA256}(X)$). |
| $t_{\mathrm{ns}}$       | High‑resolution monotonic clock reading in nanoseconds (from `time_ns()`).                                                                     |
| $T$                     | The left‑shifted timestamp: $T = t_{\mathrm{ns}} \ll 64$ (shifted into the high 64 bits of a 128‑bit value).                                   |
| $L$                     | The low 128 bits of the parameter‑set hash: $L = P \bmod 2^{128}$.                                                                             |
| $\mathit{master\_seed}$ | 128‑bit PRNG seed: $\mathit{master\_seed} = T \oplus L$.                                                                                       |
| $\mathrm{STREAM\_NAME}$ | Canonical module identifier string (e.g. `"multi_site_hurdle"`).                                                                               |
| $h$                     | 128‑bit integer: $h = \mathrm{SHA1}(\mathrm{STREAM\_NAME}) \bmod 2^{128}$, used as the Philox jump stride.                                     |
| $c$, $c'$               | Philox counter state before and after applying `_jump(h)`:  $c' = (c + h)\bmod 2^{128}$.                                                       |
| $\mu$                   | Reported mean of a statistical coefficient (from YAML’s `mean` field).                                                                         |
| $\ell$                  | Lower bound of the 90 % confidence interval (`ci_lower`).                                                                                      |
| $u$                     | Upper bound of the 90 % confidence interval (`ci_upper`).                                                                                      |
| $\sigma$                | Implied standard deviation for truncated‑normal bootstrap: $\sigma = \tfrac{u-\ell}{2\,z_{0.95}}$, with $z_{0.95}\approx1.645$.                |
| $X_j$                   | One bootstrap replicate drawn from $\mathcal{N}(\mu,\sigma^2)$ truncated to $[\ell,u]$, for $j=1\ldots100$.                                    |
| $\alpha_i$              | Prior concentration weight for zone $i$ (from `country_zone_alphas.yaml`).                                                                     |
| $k_i$                   | Number of synthetic outlets observed in zone $i$.                                                                                              |
| $N$                     | Total number of synthetic outlets across all zones (sum of all $k_i$).                                                                         |
| $\theta_i$              | True (latent) share of outlets in zone $i$, with posterior $\mathrm{Beta}(\alpha_i+k_i,\sum_j\alpha_j+N-k_i)$.                                 |
| $Y$                     | Hourly transaction count in the footfall–throughput Poisson GLM.                                                                               |
| $y_i$                   | Observed count for the $i$th hour in the regression.                                                                                           |
| $\hat y_i$              | Model‑predicted mean for the $i$th hour.                                                                                                       |
| $n$                     | Sample size (number of hourly observations).                                                                                                   |
| $p$                     | Number of predictors (including intercept) in the Poisson GLM.                                                                                 |
| $\hat\phi$              | Estimated over‑dispersion: $\hat\phi = \frac{\sum (y_i-\hat y_i)^2/\hat y_i}{\,n-p}$.                                                          |
| $\tau_s$, $\tau_e$      | Local timestamps marking the start ($\tau_s$) and end ($\tau_e$) of a DST gap.                                                                 |
| $m$                     | A minute‑resolution timestamp in the 48 h window tested by the DST edge passer.                                                                |

These definitions exhaustively cover every symbol in Appendix A.

## Appendix B – Governing Artefact Registry

| Artefact Class                     | Path Pattern                                                    | SemVer Field | Digest Field                |
| ---------------------------------- | --------------------------------------------------------------- | ------------ | --------------------------- |
| Docker Lockfile                    | `Dockerfile.lock`                                               | N/A          | N/A                         |
| Artefact Registry YAML             | `artefact_registry.yaml`                                        | N/A          | N/A                         |
| Hurdle Coefficients                | `config/hurdle_coefficients.yaml`                               | `version`    | `hurdle_coeff_digest`       |
| NB Coefficients                    | `config/nb_coefficients.yaml`                                   | `version`    | `nb_coeff_digest`           |
| Cross‑Border Hyperparams           | `config/crossborder_hyperparams.yaml`                           | `version`    | `crossborder_hyp_digest`    |
| Footfall Coefficients              | `config/footfall_coefficients.yaml`                             | `version`    | `footfall_coeff_digest`     |
| Routing Day Effect                 | `config/routing_day_effect.yml`                                 | `version`    | `gamma_variance_digest`     |
| Winsorisation Policy               | `config/winsor.yml`                                             | `version`    | `winsor_digest`             |
| Fallback Policy                    | `config/fallback_policy.yml`                                    | `version`    | `fallback_policy_digest`    |
| Zone Floor Constraints             | `config/zone_floor.yml`                                         | `version`    | `zone_floor_digest`         |
| Country‑Zone Alphas                | `config/country_zone_alphas.yaml`                               | `version`    | `zone_alpha_digest`         |
| Calibration Slice Config           | `config/calibration_slice_config.yml`                           | `version`    | `calibration_slice_digest`  |
| Cross‑Zone Validation              | `config/cross_zone_validation.yml`                              | `version`    | `cross_zone_val_digest`     |
| CDN Country Weights                | `config/cdn_country_weights.yaml`                               | `version`    | `cdn_weights_digest`        |
| Validation Configuration           | `config/validation_conf.yml`                                    | `version`    | `validation_conf_digest`    |
| Transaction Schema AVSC            | `schemas/transaction_schema.avsc`                               | N/A          | `schema_digest`             |
| Domain JSON Schemas                | `schemas/<domain>.json`                                         | N/A          | `schema_<domain>_digest`    |
| Spatial Blend Config               | `spatial_blend.yaml`                                            | `version`    | `spatial_blend_digest`      |
| HRSL Population Rasters            | `artefacts/priors/hrsl_pop_100m_{ISO}.tif`                      | N/A          | `hrsl_pop_digest`           |
| OSM Roads                          | `artefacts/priors/osm_primary_roads_*.pbf`                      | N/A          | `osm_roads_digest`          |
| Airport Boundaries                 | `artefacts/priors/iata_airport_boundaries_*.geojson`            | N/A          | `airport_boundaries_digest` |
| WorldPop Fallback                  | `artefacts/priors/worldpop_fallback_{ISO}.tif`                  | N/A          | `worldpop_fallback_digest`  |
| Spatial Manifest JSON              | `spatial_manifest.json`                                         | N/A          | `spatial_manifest_digest`   |
| Timezone Shapefile                 | `tz_world_2025a.shp`                                            | N/A          | `tz_polygon_digest`         |
| Timezone Data Archive              | `tzdata2025a.tar.gz`                                            | N/A          | `tzdata_digest`             |
| Timezone Overrides YAML            | `tz_overrides.yaml`                                             | `version`    | `tz_overrides_digest`       |
| Timezone Nudge Config              | `tz_nudge.yml`                                                  | `version`    | `tz_nudge_digest`           |
| Zoneinfo Version YAML              | `zoneinfo_version.yml`                                          | N/A          | `zoneinfo_version_digest`   |
| Network‑Share Vectors              | `artefacts/network_share_vectors/settlement_shares_*.parquet`   | N/A          | `settlement_share_digest`   |
| Currency‑Country Shares            | `artefacts/currency_country_split/ccy_country_shares_*.parquet` | N/A          | `currency_country_digest`   |
| MCC Channel Rules YAML             | `config/mcc_channel_rules.yaml`                                 | `version`    | `virtual_rules_digest`      |
| Virtual Settlement Coordinates CSV | `virtual_settlement_coords.csv`                                 | N/A          | `settlement_coord_digest`   |
| CDN Edge Weights YAML              | `config/virtual/cdn_country_weights.yaml`                       | `version`    | `cdn_weights_digest`        |
| Alias Tables NPZ                   | `alias/*.npz`                                                   | N/A          | `alias_digest`              |
| Edge Catalogue Parquet             | `edge_catalogue/*.parquet`                                      | N/A          | `edge_catalogue_digest`     |


