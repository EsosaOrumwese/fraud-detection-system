## Subsegment 2B: Routing transactions through sites
Below are the precise formulae, units, code cross‑references and domain notes for every core computation in “Routing transactions through sites.”

---

### A.1 Weight Normalization

**Purpose:** turn raw foot‑traffic scalars into a probability distribution.
**Code:** `router/io.py:load_weights`
Let

$$
F = [F_1, F_2, \dots, F_{N_m}],\quad F_i>0
$$

be the IEEE‑754 double scalars from `artefacts/catalogue/site_catalogue.parquet`. Define total weight

$$
W = \sum_{j=1}^{N_m} F_j\quad(\text{double}).
$$

Then the normalized weight for site $i$ is

$$
p_i = \frac{F_i}{W}
\quad(\text{unitless},\;\sum_i p_i = 1).
$$

> **Domain note:** if $W = 0$, code in `router/errors.py` raises `RoutingZeroWeightError`; see A.8.

---

### A.2 Alias‑Table Construction

**Purpose:** enable O(1) sampling from the discrete distribution $\{p_i\}$.
**Code:** `router/alias.py:build_alias_table`
Given $p$ of length $N_m$:

1. Initialize two stacks:
   $\mathcal{S} = \{i : p_i < 1/N_m\},\quad  
    \mathcal{L} = \{i : p_i \ge 1/N_m\}.$
2. While $\mathcal{S}$ non‑empty: pop $s$ from $\mathcal{S}$, $l$ from $\mathcal{L}$; set
   $\mathrm{prob}[s] = p_s \cdot N_m,\quad  
    \mathrm{alias}[s] = l.$
   Update
   $p_l := p_l - (1/N_m - p_s).$
   Reassign $l$ to $\mathcal{S}$ or $\mathcal{L}$ based on $p_l$.
3. Any remaining index $i$ gets
   $\mathrm{prob}[i] = 1,\;\mathrm{alias}[i]=i.$
   Arrays `prob` (uint32) and `alias` (uint32) of length $N_m$ are then saved to `<merchant_id>_alias.npz`.

> **Domain note:** this deterministic procedure uses only integer operations and the original `p` array.

---

### A.3 Corporate‑Day Random Effect

**Purpose:** introduce daily cross‑zone co‑movement.
**Code:**

* Seed derivation: `router/seed.py:derive_philox_seed`
* Uniform draw: `router/prng.py:get_uniform(counter)`
  Let
  $\mathrm{seed} = \mathrm{SHA1}(\mathtt{global\_seed}\,\|\,\texttt{"router"}\,\|\,\mathtt{merchant\_id})$
  produce a 128‑bit Philox key. For each UTC day $d$, the code draws

$$
u_d = \mathrm{Philox}(\text{key},\;\text{counter}=0)
\quad(\text{uniform in }[0,1)).
$$

Then

$$
\gamma_d = \exp\bigl(\mu_\gamma + \sigma_\gamma\,\Phi^{-1}(u_d)\bigr),
\quad
\mu_\gamma = -\tfrac12\,\sigma_\gamma^2
$$

with $\sigma_\gamma^2$ from `config/routing/routing_day_effect.yml`.

> **Domain note:** day‑effect uses counter 0; event draws start at counter 1 (see A.4).

---

### A.4 Outlet Sampling

**Purpose:** draw a single site from the customer’s alias table in O(1) time.
**Code:** `router/sampler.py:sample_site`
Given alias arrays `prob, alias` and a uniform draw

$$
u = \mathrm{Philox}(\text{key},\;\text{counter}=d+1+i)
\quad(\text{for site index }i),
$$

compute

$$
k = \lfloor u \times N_m\rfloor,\quad
f = u \times N_m - k.
$$

Select

$$
\text{site\_index} =
\begin{cases}
k, & f < \mathrm{prob}[k],\\
\mathrm{alias}[k], & \text{otherwise},
\end{cases}
$$

and map to `site_id`.

---

### A.5 CDN‑Country Sampling

**Purpose:** choose an edge‑node country for virtual merchants.
**Code:** `router/alias.py:build_alias_table` & `router/sampler.py:sample_cdn_country`
Identical to A.2–A.4, but on the vector

$$
Q = [q_1,\dots,q_K]\quad(\sum q_k = 1)
$$

from `config/routing/cdn_country_weights.yaml`, producing `<merchant_id>_cdn_alias.npz`.

---

### A.6 Audit Checksum

**Purpose:** validate reproducibility every batch.
**Code:** `router/audit.py:emit_checksum`
After each batch of $B=10^6$ events, let

$$
C = [c_1,\dots,c_{N_m}]\quad(c_i \in \mathbb{Z}_{\ge0})
$$

be the cumulative counts per site. Compute

$$
\mathrm{checksum} = \mathrm{SHA256}\bigl(\mathtt{merchant\_id}\,\|\,\mathtt{batch\_index}\,\|\,\mathrm{BE}(C)\bigr),
$$

where $\mathrm{BE}(C)$ is the big‑endian concatenation of 8‑byte `uint64` values. Append to `logs/routing/routing_audit.log` with ISO 8601 timestamp.

---

### A.7 Validation Metrics

**Purpose:** enforce long‑run share and correlation targets.
**Code:** `router/validation.py:run_checks`
Given empirical counts $C$ and normalized weights $p$, define

$$
\hat p_i = \frac{c_i}{\sum_j c_j},\quad
\rho_{\mathrm{emp}} = \mathrm{PearsonCorr}(\mathbf{h}^{(1)},\mathbf{h}^{(2)}),
$$

where $\mathbf{h}^{(1)},\mathbf{h}^{(2)}$ are hourly count vectors for the two most populous time‑zones. Assert

$$
|\hat p_i - p_i| < \epsilon_p,\quad
|\rho_{\mathrm{emp}} - \rho^*| < \epsilon_\rho,
$$

with $\epsilon_p$ and $\rho^*$ from `routing_validation.yml`.

---

### A.8 Zero‑Weight Edge Case

**Purpose:** handle degenerate weight distributions.
**Code:** `router/errors.py:check_zero_weight`
If

$$
W = \sum_{j=1}^{N_m} F_j = 0,
$$

raise
$\mathtt{RoutingZeroWeightError}(\mathtt{merchant\_id})$,
which aborts the routing build.

---

### A.9 Performance Metrics

**Purpose:** monitor throughput and memory.
**Code:** `router/metrics.py`
Throughput

$$
\mathrm{TP} = \frac{\text{bytes_routed}}{\text{elapsed_seconds}}
\quad(\text{MB/s}),
$$

Memory

$$
\mathrm{Mem} = \mathrm{RSS}\quad(\text{GB}).
$$

Thresholds ($\mathrm{TP}\ge200$, $\mathrm{Mem}\le2$) are loaded from `config/routing/performance.yml`.

---

With this appendix, every numerical operation, random‑seed decision, file format and validation formula is explicitly defined, leaving no room for interpretation.
