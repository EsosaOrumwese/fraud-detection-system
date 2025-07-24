## Subsegment 1A: From merchants to physical sites
**A.1 Hurdle Logistic (Single vs Multi‑site)**
Feature vector $\mathbf x$ contains: intercept, MCC dummies, channel dummies, developmental (GDP bucket) dummies.

$$
\pi = \sigma(\mathbf x^{\top}\beta)
      = \frac{1}{1 + \exp\!\big[-(\beta_0 + \beta_{\text{mcc}} + \beta_{\text{channel}} + \beta_{\text{dev}}\cdot \text{Bucket})\big]}
$$

Decision: draw $u \sim \text{Uniform}(0,1)$; multi‑site iff $u < \pi$. If single‑site, set $N=1$ and skip all multi‑site steps.

**A.2 Negative Binomial (Multi‑site Merchants Only)**
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

**A.3 Zero‑Truncated Poisson for Foreign Country Count $K$**

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

**A.4 Currency→Country Expansion**
Let currency‑level settlement weights be $s^{(\text{ccy})}_j$, $\sum_j s^{(\text{ccy})}_j = 1$. For a multi‑country currency with member country set $C$ and proportional intra‑currency country weights $q_c$ (smoothed), define:

$$
\tilde w_c = s^{(\text{ccy})}\, q_c,\qquad
w_c = \frac{\tilde w_c}{\sum_{c' \in C}\tilde w_{c'}}
$$

If sparse fallback triggers, set $q_c = 1/|C|$ (equal split) before renormalisation.

**A.5 Gumbel–Top‑k Weighted Sampling (Foreign Countries)**
For candidate country $i$ with weight $w_i$, draw $u_i \sim \text{Uniform}(0,1)$, form key

$$
\kappa_i = \log w_i - \log(-\log u_i),
$$

select $K$ countries with largest $\kappa_i$; tie‑break lexicographically by ISO code. Order of selected $\kappa_i$ defines foreign ordering.

**A.6 Dirichlet Allocation of Outlets Across Countries**
Country set size $K+1$ (home + K foreign in selection order). Concentrations $\alpha_i > 0$.
Sampling:

$$
G_i \sim \text{Gamma}(\alpha_i, 1)\ \text{i.i.d.},\qquad
S = \sum_{i=1}^{K+1} G_i,\qquad
w_i = \frac{G_i}{S},\quad \sum_i w_i = 1
$$

Integer allocation target totals: $w_i N$.

**A.7 Deterministic Largest‑Remainder Rounding**
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

**A.8 Site ID Sequencing**
Within each $(\text{merchant}, \text{country})$ block, sequence:

$$
\text{site\_seq} = 1,2,\dots, M_{c};\quad \text{site\_id} = \text{merchant\_id} \Vert \text{format}_{06d}(\text{site\_seq})
$$

**A.9 Manifest & Parameter Hash Construction**
Let $\mathcal D = \{d_1,\dots,d_m\}$ be the set of SHA‑256 digests (as 256‑bit integers) for governed artefacts and git commit hash digest $d_{\text{git}}$. Parameter hash $h_p = \text{SHA256}(\text{concat}(d_{\text{YAML}}))$. Manifest fingerprint:

$$
f = \text{SHA256}\Big( \text{XOR}\big( d_{\text{git}}, h_p, d_1,\dots,d_m \big) \Big)
$$

**A.10 Reproducibility Mapping**
Given $(f, \text{global\_seed})$, the master Philox counter start $C_0 = \text{SHA256}_{64}(f \Vert \text{global\_seed})$ (first 128 bits folded) and each sub‑stream stride $s_k = \text{lower}_{64}(\text{SHA256}(\text{key}_k))$; counter advance: $C_{k+1} = C_k + s_k$. All draws record $(\text{pre\_counter}, \text{post\_counter})$ so replay is an injective mapping.

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