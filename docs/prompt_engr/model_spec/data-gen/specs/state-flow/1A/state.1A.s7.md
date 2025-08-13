# S7 — Allocate N outlets across the ordered `country_set` and integerise

## Purpose

Given a merchant’s **total outlet count** $N$ and its ordered **country set** $C$ (home + up to $K$ foreign countries from S6), sample a **Dirichlet weight vector** $w$ over $C$ and convert the real-valued allocations $Nw$ to **integers $\{n_i\}$** that sum exactly to $N$ using **largest-remainder rounding** with deterministic tie-breaks. Persist the rounding residual ranks and emit RNG events.

---

## Inputs (per merchant $m$)

* $N \in \mathbb{Z}_{\ge 1}$: final outlet count from S2 (post ZTP).
* Ordered country set $C = (c_0,\dots,c_{K})$, with `rank(c_0)=0` (home), `rank(c_j)=j` for foreigns in **Gumbel order** from S6. Length $|C| = K+1$. `country_set` is the **only** authority for this order.
* Dirichlet concentration parameters $\alpha \in \mathbb{R}^{K+1}_{>0}$: looked up by $(\text{home_country},\ \text{MCC},\ \text{channel},\ m=K{+}1)$ from cross-border hyperparameters used by the 1A allocator. (See `crossborder_allocation` → dependency on `crossborder_hyperparams`.)
* Determinism context: `seed`, `parameter_hash`, `manifest_fingerprint`, Philox sub-stream labels (S0/S1 conventions).

**Degenerate path (domestic-only):** If $K=0$ or merchant is ineligible for cross-border (S3), set $C=(\text{home})$, $\alpha=(\alpha_0)$ not used, **force** $w=(1)$, $n_0=N$. We still log a single residual event with residual $0.0$ and `residual_rank=1` to keep event counts consistent.

---

## Numeric environment (determinism)

* IEEE-754 **binary64** for all stochastic arithmetic; serial reductions; **FMA disabled** for Dirichlet & residual ops.
* Residuals are **quantised to 8 dp** **before** sorting; sum-to-one checks use a tolerance of $10^{-6}$ for $w$.

---

## Algorithm

### A) Dirichlet weights over $C$  (skip if $|C|=1$)

1. Let $m = |C| = K+1$. Retrieve $\alpha = (\alpha_1,\dots,\alpha_m)$ with $\alpha_i>0$.
2. Draw independent gamma components using the sampler in **S2.x**; any uniforms required by the sampler are drawn via the `u01` mapping in **S0.3.4**, and any standard normals via **S0.3.5**.  
For budgets, see **S2.x**: α≥1 = 3 uniforms per attempt; α<1 = above plus 1 uniform for the power transform.

   $$
   G_i \sim \mathrm{Gamma}(\alpha_i,\,1),\quad i=1,\dots,m.
   $$

   Emit **one** `dirichlet_gamma_vector` RNG event containing the aligned arrays `(country_isos, alpha, gamma_raw, weights)` (weights recorded after step 3). Envelope carries seed & Philox counters. Constraints: equal length arrays; $\sum_i w_i=1 \pm 10^{-6}$.
   **Draw accounting (S0.3.6).** Event `draws` equals $\sum_i \big( 3 \times \text{attempts}_i \;+\; \mathbf{1}[\alpha_i<1] \big)$; normalisation consumes **no** uniforms.

3. Serial normalisation (deterministic summation order):

   $$
   S=\sum_{i=1}^{m} G_i,\qquad w_i=\frac{G_i}{S},\quad \sum_i w_i = 1.
   $$

   Validate schema constraints before proceeding.

### B) Real-valued to integer counts via **largest-remainder**

Given $N \in \mathbb{Z}_{\ge 1}$ and $w\in\Delta^{m-1}$:

1. Real allocations: $a_i = N\,w_i$.
2. Floors: $f_i=\lfloor a_i \rfloor$.
3. Residuals (pre-quantisation): $r_i^{\text{raw}} = a_i - f_i \in [0,1)$.
4. **Quantise** residuals: $r_i = \mathrm{round}(r_i^{\text{raw}}, 8\ \text{dp})$.
5. Compute deficit: $d = N - \sum_i f_i$. Because $\sum_i w_i = 1$, $0 \le d < m$.
6. **Stable sort** indices by $r_i$ **descending**; **break ties** by `country_iso` ASCII lexicographic order (deterministic secondary key). Take the first $d$ indices $T$.
7. Final integers:

   $$
   n_i=\begin{cases}
   f_i+1, & i\in T,\\[2pt]
   f_i, & \text{otherwise}.
   \end{cases}
   $$
8. Emit one `residual_rank` event **per** country with the quantised `residual` and its **1-based** `residual_rank` in the sorted list. Envelope carries seed & counters.

**Error bound:** $|n_i - a_i|\le 1$ for all $i$; $\sum_i n_i=N$. Engine logs the deviations and aborts if any $|n_i-a_i|>1$.

---

## Invariants & tie-break determinism

* **Mass conservation:** $\sum_i n_i=N$ (checked).
* **Non-negativity:** $n_i\in\mathbb{Z}_{\ge 0}$.
* **Stable ordering:** residual sort key = $(r_i,\ \text{ISO})$ with $r_i$ quantised to 8 dp; prevents platform-dependent ties.
* **RNG lineage:** One `dirichlet_gamma_vector` event per merchant with $|C|>1$; $|C|$ `residual_rank` events always (including the $|C|=1$ case). Paths & schemas are fixed across runs.

---

## Outputs (persisted artefacts & logs)

1. **`ranking_residual_cache_1A`** (parameter-scoped, seed-partitioned):
   For each $(\text{merchant_id},\ \text{country_iso})$: the **quantised residual**, its **`residual_rank`**, and any auxiliary fields needed to reconstruct $n_i$ (e.g., $N$, $w_i$, floor $f_i$). Partitioning: `seed`, `parameter_hash`. Produced by **`1A.integerise_allocations`**.

2. **RNG events** (JSONL):

   * `dirichlet_gamma_vector` at `logs/rng/events/dirichlet_gamma_vector/seed=…/parameter_hash=…/run_id=…/` with arrays `(country_isos, alpha, gamma_raw, weights)`. Producer: **`1A.dirichlet_allocator`**.
   * `residual_rank` at `logs/rng/events/residual_rank/…/` with `(merchant_id, country_iso, residual, residual_rank)`; one event per country. Producer: **`1A.integerisation`**.

3. **No changes to `country_set`** in S7 (it remains the sole authority for cross-country order; inter-country order is **not** encoded in `outlet_catalogue`). Consumers needing order must join to `country_set.rank`.

---

## Complexity

Per merchant: gamma sampling $O(m)$; sort by residuals $O(m\log m)$ with $m=K{+}1$. Typical $m$ is small (tens). Deterministic serial ops throughout.

---

## Notes on correctness & governance

* Dirichlet event schema enforces array length equality and $\sum w_i = 1$ to $10^{-6}$; violations abort.
* The **proof of determinism** for largest-remainder rounding (with the quantisation + ISO tiebreak) is tracked as a controlled doc and digested into the manifest.
* Naming alignment: `residual_rank` (integerisation order) is **distinct** from `site_order` (within-country sequence used later for outlet IDs).

---

### Summary (one-liner)

S7 transforms $N$ and the ordered set $C$ into exact integer per-country counts $\{n_i\}$ via $\mathrm{Dirichlet}(\alpha)$ weights and a fully deterministic **largest-remainder** scheme, while persisting the **residual rankings** and full RNG lineage to guarantee reproducibility.
