## Subsegment 4A: Reproducibility and configurability
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
