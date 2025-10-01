## Subsegment 4B: Validation without bullet points

### A.1 Parameter‑Set Hash & Manifest Fingerprint
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

### A.2 Master Seed Construction
Let $t_{\mathrm{ns}}$ denote the monotonic clock reading in nanoseconds (`time_ns()`).  Define

$$
T = t_{\mathrm{ns}} \ll 64,\quad
L = P \bmod 2^{128},\quad
\mathit{master\_seed} = T \oplus L,
$$

where $\ll$ is a 64‑bit left shift and $\oplus$ is bitwise XOR on 128‑bit values.

### A.3 Philox Counter Jump
Each module declares a string `STREAM_NAME`.  Compute its 128‑bit stride

$$
h = \mathrm{SHA1}(\mathrm{STREAM\_NAME}) \bmod 2^{128}.
$$

Given the current Philox counter $c\in[0,2^{128}-1]$, the new counter is

$$
c' = (c + h)\bmod 2^{128}.
$$

All random draws use Philox 2¹²⁸ with AES‑round mixing; each call to `_jump(h)` advances the counter accordingly.

### A.4 Truncated‑Normal Bootstrap for YAML Parameters
For each coefficient with reported mean $\mu$, lower CI $\ell$, upper CI $u$ (90 %), set

$$
\sigma = \frac{u - \ell}{2\,z_{0.95}},\quad z_{0.95}\approx1.645.
$$

Draw bootstrap replicates

$$
X_j\sim \mathcal{N}(\mu,\sigma^2)\quad\text{truncated to }[\ell,u],\quad j=1\ldots100,
$$

i.i.d., and regenerate synthetic outputs for envelope validation.

### A.5 Conjugate Beta‑Posterior Intervals
Let $\alpha_i$ be the prior for zone $i$ from `country_zone_alphas.yaml`, and $k_i$ the observed outlet count out of total $N$.  The posterior for the true share $\theta_i$ is

$$
\theta_i \sim \mathrm{Beta}\bigl(\alpha_i + k_i,\;\sum_j\alpha_j + N - k_i\bigr),
$$

and the 95 % credible interval is

$$
\bigl[F^{-1}_{\theta_i}(0.025),\,F^{-1}_{\theta_i}(0.975)\bigr],
$$

where $F^{-1}$ is the Beta quantile.

### A.6 Poisson GLM Over‑dispersion Parameter
For the footfall–throughput Poisson GLM with link $\log$, fitted values $\hat y_i$ and observations $y_i$, dispersion is estimated as

$$
\hat\phi = \frac{\sum_{i=1}^n \frac{(y_i - \hat y_i)^2}{\hat y_i}}{\,n - p\,},
$$

with $n$ samples and $p$ predictors.  Acceptable $\hat\phi\in[1,2]$ for CP and $[2,4]$ for CNP.

### A.7 DST Gap & Fold Enumeration
Let $\tau_s,\tau_e$ be the local epoch seconds bracketing a DST spring gap; the gap interval is $[\tau_s,\tau_e)$.  Define the fold interval at autumn likewise.  For each minute $m$ in a 48 h window, the validator asserts

$$
m\notin[\tau_s,\tau_e),\quad\text{and}\quad
\bigl|\#\{m\}\bigr|=2\quad\text{if }m\in[\tau_f,\tau_f+3600).
$$

### A.8 Global Output Logging, Manifest, and Provenance Enforcement

* **Validation Artefact and Log Requirement:**
  Every validation output, defect log, AUROC model dump, misclassification index, θ-violation PDF, barcode failure overlay, and all error/validator logs *must* be written as artefacts, tracked by parameter hash $P$ and referenced by digest in the manifest.
* **End-to-end Provenance:**
  All validation artefacts and logs must embed $P$, build timestamp, manifest digest, and (if applicable) HashGate audit URI in their schema or metadata.


### A.9 Pass/Fail and Merge-blocking Contracts

* **Blocking Conditions:**
  Any occurrence of the following must block merge, trigger dataset quarantine, and be logged as a governed artefact:

  * `StructuralError` (structural failures, nulls, type mismatches)
  * `DstIllegalTimeError` (illegal or ambiguous local times)
  * `DistributionDriftDetected` (distributional drift in output)
  * `ThetaOutOfRange` (θ‑violation, e.g., parameter or model outside confidence region)
  * `BarcodeSlopeError` (barcode slope outside acceptance envelope)
  * `LicenceMismatchError` (missing or incorrect licence mapping)
  * Any CI, validator, or audit script failure

* **Manifest/CI Enforcement:**
  All validation pass/fail events and logs must be recorded in the manifest, and their hash referenced in every pipeline output.
  *No output may be merged or exported if any pass/fail artefact or error log is missing, incomplete, or fails validation.*


### A.10 HashGate/Audit Trail and Audit URI Contract

* **Audit URI Requirement:**
  Every build must register a HashGate/Audit URI (`/hashgate/<P>/<master_seed>`) and record this in the manifest, PR, and all output logs.
* **CI Polling and Approval:**
  CI scripts must poll the HashGate/Audit URI and require immutable approval before merging or releasing the dataset.

### A.11 Licence Mapping and Enforcement

* **Explicit Licence Contract:**
  Every governed artefact (config, code, schema, output, validation log, PNG/PDF, etc.) must have an explicit licence file mapped in the artefact registry and checked by SHA-256.
* **Merge-block on Licence Error:**
  Any missing or mismatched licence, or registry omission, blocks CI, merge, and downstream use.

### A.12 Directory Immutability and Collision Handling

* **Export Directory Contract:**
  The exported dataset directory for parameter hash $P$ and master seed must be set read-only after build.
  Any attempt to regenerate, overwrite, or export with the same $P$ and seed triggers a fatal collision error and must abort.


### A.13 Glossary and End-to-End Invariant

* **Pipeline Invariant:**
  Every formula, contract, or validation step in this appendix is globally binding for the full pipeline, and must be referenced in the pipeline configuration, registry, and all documentation.
* **No Escape Clause:**
  No artefact, log, or output referenced in 1A–4B or their appendices may escape governance or validation by omission or loophole.


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
