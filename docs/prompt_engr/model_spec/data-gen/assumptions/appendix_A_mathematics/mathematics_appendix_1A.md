## Subsegment 1A: From merchants to physical sites
### **A.1 Hurdle Logistic (Single vs Multi‑site)**
Feature vector $\mathbf x$ contains: intercept, MCC dummies, channel dummies, developmental (GDP bucket) dummies.

$$
\pi = \sigma(\mathbf x^{\top}\beta)
      = \frac{1}{1 + \exp\!\big[-(\beta_0 + \beta_{\text{mcc}} + \beta_{\text{channel}} + \beta_{\text{dev}}\cdot \text{Bucket})\big]}
$$

Decision: draw $u \sim \text{Uniform}(0,1)$; multi‑site iff $u < \pi$. If single‑site, set $N=1$ and skip all multi‑site steps.

### **A.2 Negative Binomial (Multi‑site Merchants Only)**
Mean and dispersion links (developmental bucket intentionally *omitted* from mean):

$$
\log \mu = \alpha_0 + \alpha_{\text{mcc}} + \alpha_{\text{channel}}, \qquad
\log \phi = \delta_0 + \delta_{\text{mcc}} + \delta_{\text{channel}} + \eta \log(\text{GDPpc})
$$

with $\eta > 0$, GDPpc in constant USD (2015 base), natural log.
Parameter mappings (all logged):

$$
r = \phi,\qquad
p = \frac{\phi}{\phi + \mu},\qquad
\mathbb E[N]=\mu,\quad
\mathrm{Var}[N]=\mu + \frac{\mu^{2}}{\phi}
$$

Sampling via Poisson–Gamma mixture:

$$
G \sim \text{Gamma}(r=\phi,\ \text{scale}=\mu/\phi),\qquad
N \mid G \sim \text{Poisson}(G)
$$

Reject $N \in \{0,1\}$; repeat until $N \ge 2$.

### **A.3 Zero‑Truncated Poisson for Foreign Country Count $K$**

$$
\lambda_{\text{extra}} = \theta_0 + \theta_1 \log N,\qquad \theta_1 < 1
$$

Raw (untruncated) Poisson PMF: $P(K=k)= e^{-\lambda} \lambda^{k}/k!,\ k=0,1,\dots$
Zero‑truncated PMF (support $k\ge 1$):

$$
P_{\text{ZTP}}(K = k) = \frac{e^{-\lambda}\lambda^{k} / k!}{1 - e^{-\lambda}},\qquad k\ge 1
$$

Expected value under truncation (used for monitoring / sanity checks):

$$
\mathbb E[K] = \frac{\lambda}{1 - e^{-\lambda}} - 1
$$

Sampling is rejection of k=0 from standard Poisson until $k\ge 1$; cap = 64 attempts.

> *Implementation note:* In the production build we parameterise
> $\lambda_{\text{extra}} = \exp(\theta_0 + \theta_1 X)$
> where $X$ is the smoothed openness index.
> This log-link GLM replaces the earlier identity-link draft (λ = θ₀ + θ₁ log N) and guarantees λ > 0 while leaving the ZTP PMF and sampling logic unchanged.


### **A.4 Currency→Country Expansion**
Let currency‑level settlement weights be $s^{(\text{ccy})}_j$, $\sum_j s^{(\text{ccy})}_j = 1$. For a multi‑country currency with member country set $C$ and proportional intra‑currency country weights $q_c$ (smoothed), define:

$$
\tilde w_c = s^{(\text{ccy})}\, q_c,\qquad
w_c = \frac{\tilde w_c}{\sum_{c' \in C}\tilde w_{c'}}
$$

If sparse fallback triggers, set $q_c = 1/|C|$ (equal split) before renormalisation.

### **A.5 Gumbel–Top‑k Weighted Sampling (Foreign Countries)**
For candidate country $i$ with weight $w_i$, draw $u_i \sim \text{Uniform}(0,1)$, form key

$$
\kappa_i = \log w_i - \log(-\log u_i),
$$

select $K$ countries with largest $\kappa_i$; tie‑break lexicographically by ISO code. Order of selected $\kappa_i$ defines foreign ordering.

### **A.6 Dirichlet Allocation of Outlets Across Countries**
Country set size $K+1$ (home + K foreign in selection order). Concentrations $\alpha_i > 0$.
Sampling:

$$
G_i \sim \text{Gamma}(\alpha_i, 1)\ \text{i.i.d.},\qquad
S = \sum_{i=1}^{K+1} G_i,\qquad
w_i = \frac{G_i}{S},\quad \sum_i w_i = 1
$$

Integer allocation target totals: $w_i N$.

### **A.7 Deterministic Largest‑Remainder Rounding**
Let

$$
n_i^{\text{floor}} = \big\lfloor w_i N \big\rfloor,\qquad
r_i = w_i N - n_i^{\text{floor}}
$$

Deficit:

$$
d = N - \sum_{i} n_i^{\text{floor}},\quad 0 \le d < K+1
$$

Sort indices by $r_i$ (desc), tie‑break by ISO code; add $+1$ to first $d$ indices:

$$
n_i = n_i^{\text{floor}} + \mathbf 1\{i \text{ among top } d\}
$$

Guarantees $\sum_i n_i = N$. Error bound:

$$
|n_i - w_i N| \le 1,\qquad
\max_i \frac{|n_i - w_i N|}{N} \le \frac{1}{N}
$$

### **A.8 Site ID Sequencing**
Within each $(\text{merchant}, \text{country})$ block, sequence:

$$
\text{site_seq} = 1,2,\dots, M_{c};\quad \text{site_id} = \text{merchant_id} \Vert \text{format}_{06d}(\text{site_seq})
$$

### **A.9 Manifest & Parameter Hash Construction**
Let $\mathcal D = \{d_1,\dots,d_m\}$ be the set of SHA‑256 digests (as 256‑bit integers) for governed artefacts and git commit hash digest $d_{\text{git}}$. Parameter hash $h_p = \text{SHA256}(\text{concat}(d_{\text{YAML}}))$. Manifest fingerprint:

$$
f = \text{SHA256}\Big( \text{XOR}\big( d_{\text{git}}, h_p, d_1,\dots,d_m \big) \Big)
$$

### **A.10 Reproducibility Mapping**
Given $(f, \text{global_seed})$, the master Philox counter start $C_0 = \text{SHA256}_{64}(f \Vert \text{global_seed})$ (first 128 bits folded) and each sub‑stream stride $s_k = \text{lower}_{64}(\text{SHA256}(\text{key}_k))$; counter advance: $C_{k+1} = C_k + s_k$. All draws record $(\text{pre_counter}, \text{post_counter})$ so replay is an injective mapping.

### **A.11 Output/Log Lineage and Immutability Mapping**

Given $f$ and run seed, all downstream stochasticity is reproducible; any change in artefact byte content, version, or manifest entry propagates a new $f$ and thus creates a new, non-overlapping output lineage.
*Any mutation of upstream artefacts or outputs triggers an abort in downstream pipeline stages unless $f$ matches manifest lineage.*

### **A.12 Audit Log Event Schema (Structured Table)**

Let $\mathcal{E}$ be the set of all stochastic or structural audit log events, each recorded with these fields:

| Field                    | Type     | Description                                |
| ------------------------ | -------- | ------------------------------------------ |
| timestamp_utc           | datetime | Event wall-clock timestamp (UTC, ISO-8601) |
| event_type              | string   | One of mandatory events below              |
| merchant_id             | int64    | Merchant involved                          |
| pre_counter             | uint128  | Philox counter before event                |
| post_counter            | uint128  | Philox counter after event                 |
| parameter_hash          | hex64    | Parameter hash at event                    |
| draw_sequence_index    | int32    | Monotonic sequence index                   |
| rejection_flag          | bool     | True if event triggered rejection/redraw   |
| [event-specific fields] | varies   | Detailed below                             |

**Mandatory event types** (with event-specific fields):

* `hurdle_bernoulli`: uniform_u, pi, outcome, substream_stride
* `gamma_component`: gamma_shape, gamma_scale, gamma_value
* `poisson_component`: lambda, draw_value
* `nb_final`: nb_mu, nb_phi, nb_r, nb_p, draw_value, rejection_count_prior
* `ztp_rejection`: lambda_extra, rejected_value, cumulative_rejections
* `ztp_retry_exhausted`: lambda_extra, rejection_count
* `gumbel_key`: country_iso, weight, uniform_u, key_value
* `dirichlet_gamma_vector`: alpha_digest, gamma_values[], summed_gamma, w_vector[]
* `stream_jump`: module, hash_source, stride_uint64
* `sequence_finalize`: merchant_id, country_iso, site_count, start_sequence, end_sequence

**Absence of any required event for a merchant is a validation failure.**


### **A.13 Monitoring, Metrics, and CI/CD Controls**

Let:

* $R_{NB}$ = overall NB rejection rate, target corridor $[0, 0.06]$
* $Q_{99, NB}$ = 99th percentile NB per-merchant rejections, threshold $\leq 3$
* $Q_{99.9, ZTP}$ = 99.9th percentile ZTP rejections, threshold $< 3$
* $M_{LRR}$ = largest-remainder rounding deviations $\max |n_i - w_i N|$ and $p_{99.9}$
* $\theta_1$ (from ZTP): Wald $p$-value must be $<0.001$

**CI/CD Procedures:**

* Compute CUSUM on NB rejection rate drift post-baseline ($h=5\sigma$)
* Any metric outside corridor or failed stationarity triggers hard abort and full rebuild.
* Stationarity diagnostics must show no rejection at $\alpha=0.01$ over the simulation horizon.

---

### **A.14 Output Schema and Immutability Contract**

**Outlet Stub Schema** (enforced, non-nullable):

| Column                        | Type          | Description                                        |
| ----------------------------- | ------------- | -------------------------------------------------- |
| merchant_id                  | int64         | Original merchant identifier                       |
| site_id                      | string `%06d` | Per-merchant+country sequence (6 digits)           |
| home_country_iso            | char(2)       | Onboarding country (source for GDP bucket)         |
| legal_country_iso           | char(2)       | Country of this outlet (home or foreign)           |
| single_vs_multi_flag       | bool          | 0=single-site, 1=multi-site                        |
| raw_nb_outlet_draw         | int32         | Raw NB draw N (≥2 if multi-site; 1 else)           |
| final_country_outlet_count | int32         | $n_i$ for this country                          |
| tie_break_rank              | int32         | Position after residual sort (for forensic replay) |
| manifest_fingerprint         | char(64)      | Catalogue lineage identifier                       |
| global_seed                  | uint64        | Master seed (derivable from manifest)              |

**Encoding:**
Integers are little-endian, ISO codes dictionary-encoded, compression is ZSTD level 3, and codec choice is hashed.
*Any change to column set, order, or type triggers a schema version bump and manifest fingerprint change.*

**Immutability contract:**
Downstream modules must treat these output fields as read-only; mutation requires artefact change and propagates new lineage ($f$), ensuring separation and reproducibility.


### **A.15 Validation Procedures**

* **Post-write validation:** After the Parquet catalogue is written, recompute $\mu, \phi, K$, Dirichlet weights, residual ordering, integer allocations, $tie_break_rank$, and $site_id$ sequence from persisted inputs.
* **Structural validation:** For each merchant, mandatory audit log events must be present and unique; any absence aborts build.
* **Reproducibility assertion:** Given manifest fingerprint, master seed, and output catalogue, an auditor can reconstruct all stochastic decisions, ensuring no hidden state.


### **A.16 Monitoring Output Artefacts**

* Output metrics (rejection rates, CUSUM status, rounding deviations, etc.) are stored as governed artefacts (see Artefacts Appendix).
* Stationarity diagnostics and Wald test outputs are persisted as Parquet or YAML with manifest digests and are required for compliance checking and CI audit.

---

### Notes / Domain Constraints

1. All logs & computations use IEEE‑754 binary64; residuals $r_i$ quantised to 8 decimal places prior to sorting—guaranteeing stable ordering across platforms within deterministic tolerance.
2. $\eta > 0$ ensures heteroskedastic variance scaling monotonic in GDPpc.
3. Zero‑truncation normalization constant $1 - e^{-\lambda}$ is **not** approximated; exact double precision computation required.
4. Gumbel keys require $u_i \in (0,1)$; values of 0 or 1 are rejected and redrawn (probability negligible) to avoid $\log(0)$.
5. All $\alpha_i > 0$; Dirichlet degeneracy disallowed.

---

### Quick Reference Summary (Variables & Domains)

| Symbol                   | Meaning                     | Domain / Constraint                 |
|--------------------------|-----------------------------|-------------------------------------|
| $\pi$                    | Multi‑site probability      | $(0,1)$                             |
| $\mu$                    | NB mean                     | $>0$                                |
| $\phi$                   | NB dispersion (size)        | $>0$                                |
| $r$                      | NB size (=φ)                | $>0$                                |
| $p$                      | NB prob                     | $(0,1)$                             |
| $N$                      | Outlet count                | Integer ≥1 (multi‑site enforced ≥2) |
| $K$                      | # foreign countries         | Integer ≥1 (cross‑border branch)    |
| $\lambda_{\text{extra}}$ | ZTP mean param              | $>0$                                |
| $w_i$                    | Country weight              | $\sum w_i = 1,\ w_i ≥ 0$            |
| $n_i$                    | Integer outlets per country | Integer ≥0, $\sum n_i = N$          |
| $d$                      | Remainder deficit           | $0 \le d < K+1$                     |
| $\alpha_i$               | Dirichlet concentration     | $>0$                                |
| $\eta$                   | GDP dispersion coefficient  | $>0$                                |
| $\theta_0, \theta_1$     | ZTP linear params           | $\theta_1 < 1$                      |

---