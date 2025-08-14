# S7 — Allocate N outlets across the ordered `country_set` and integerise

## Purpose

Given a merchant’s **total outlet count** $N$ and its ordered **country set** $C$ (home + up to $K_m^\star$ foreign countries from S6), sample a **Dirichlet weight vector** $w$ over $C$ and convert the real‑valued allocations $Nw$ to **integers $\{n_i\}$** that sum exactly to $N$ using **largest‑remainder rounding** with deterministic tie‑breaks. Persist the rounding residual ranks and emit RNG events.

---

## Inputs (per merchant $m$)

* $N \in \mathbb{Z}_{\ge 1}$: final outlet count from **S2**.
* Ordered country set $C = (c_0,\dots,c_{K_m^\star})$, with `rank(c_0)=0` (home), `rank(c_j)=j` for foreigns in **Gumbel order** from S6. Length $|C| = K_m^\star+1$. `country_set` is the **only** authority for this order.
* Determinism context: `seed`, `parameter_hash`, `manifest_fingerprint`, Philox sub‑stream labels (S0/S1 conventions).

**Degenerate path (domestic‑only).** If $K_m^\star=0$ or merchant is ineligible for cross‑border (S3), set $C=(\text{home})$, **force** $w=(1)$, $n_0=N$. We still log a single residual event with residual $0.0$ and `residual_rank=1` to keep event counts consistent.

---

## Numeric environment (determinism)

* IEEE‑754 **binary64** for all stochastic arithmetic; serial reductions; **FMA disabled** for Dirichlet & residual ops.
* Residuals are **quantised to 8 dp** **before** sorting; sum-to-one checks use a tolerance of $10^{-12}$ for $w$.

---

## Algorithm

### S7.1 α‑vector lookup (governed)

Let $m = |C| = K_m^\star+1$ and $(c_0=\text{home}, c_1,\dots,c_{K_m^\star})$ be the `country_set` order. Resolve $\boldsymbol{\alpha}\in\mathbb{R}^{m}_{>0}$ via the **fallback ladder** (no schema changes; resolution may be recorded in the validation bundle for diagnostics):

1. **Exact:** $(\text{home}, \text{MCC}, \text{channel}, m)$  
2. **Back‑off A:** $(\text{home}, \text{channel}, m)$  
3. **Back‑off B:** $(\text{home}, m)$  
4. **Fallback (symmetric):** $\alpha_i = \tau/m$ with governed $\tau>0$ (default $\tau=2.0$)

Enforce $\min_i \alpha_i \ge 10^{-6}$ (abort if violated after loading).

### S7.2 Dirichlet weights over $C$  (skip if $|C|=1$)

1. Draw independent gamma components using the sampler from **S2** (Batch‑1 spec):  
   $$
   G_i \sim \mathrm{Gamma}(\alpha_i,\,1),\quad i=0,\dots,K_m^\star.
   $$
   Uniforms via **S0.3.4**; keyed mapping via **S0.3.3**; any normals via **S0.3.5**.  
   **Draw budgets:** for each $i$, $\alpha_i\ge1$ uses 3 uniforms/attempt; $\alpha_i < 1$ uses the same plus 1 uniform for the power transform.

2. **Deterministic normalisation (fixed order; compensated sum).**  
   Use a **Neumaier compensated sum** in **serial order = `country_set.rank` ascending** (ISO as secondary if needed):
   $$
   S=\texttt{sum_comp}(G_0,\dots,G_{K_m^\star}),\qquad w_i=\frac{G_i}{S}.
   $$
   If $|S-1|>10^{-12}$ after an initial normalise, recompute $S'=\texttt{sum_comp}(w)$ and assert $|S'-1|\le 10^{-12}$.  
   **Prohibitions:** no BLAS/parallel or GPU reductions for this step.

   **Algorithm (Neumaier variant, binary64; fixed order):**
   ```
   function sum_comp(xs[0..m-1]):
       s = 0.0
       c = 0.0
       for i in 0..m-1 in country_set.rank ascending (then ISO):
           x = xs[i]
           t = s + x
           if abs(s) >= abs(x):
               c += (s - t) + x
           else:
               c += (x - t) + s
           s = t
       return s + c
   ```
   Emit **one** `dirichlet_gamma_vector` event with aligned arrays `(country_isos, alpha, gamma_raw, weights)` (weights recorded post‑normalisation).  
   **Draw accounting (S0.3.6):** `draws = \sum_i \big(3\times \text{attempts}_i + \mathbf{1}[\alpha_i<1]\big)`; normalisation consumes **no** uniforms.

### S7.3 Real‑valued to integer counts via **largest‑remainder** (LRR)

Given $N \in \mathbb{Z}_{\ge 1}$ and $w\in\Delta^{m-1}$:

1. Real allocations: $a_i = N\,w_i$.
2. Floors: $f_i=\lfloor a_i \rfloor$.
3. Residuals (pre‑quantisation): $r_i^{\text{raw}} = a_i - f_i \in [0,1)$.
4. **Quantise** residuals: $r_i = \mathrm{round}(r_i^{\text{raw}}, 8\ \text{dp})$.
5. Compute deficit: $d = N - \sum_i f_i$. Because $\sum_i w_i = 1$, $0 \le d < m$.
6. **Stable sort** indices by the key **$(r_i\ \text{desc},\ \texttt{country_set.rank}\ \text{asc},\ \text{ISO}\ \text{asc})$**.  
   (This uses **Gumbel order**—`country_set.rank`—*before* ISO as the deterministic secondary key.)
7. Final integers:
   $$
   n_i=\begin{cases}
   f_i+1, & i\in T,\\[2pt]
   f_i, & \text{otherwise},
   \end{cases}
   $$
   where $T$ is the first $d$ indices from step 6.
8. Emit one `residual_rank` event **per** country with the quantised `residual` and its **1‑based** `residual_rank` in the sorted list. Envelope carries seed & counters.

**Error bound:** $|n_i - a_i|\le 1$ for all $i$; $\sum_i n_i=N$. Engine logs the deviations and aborts if any $|n_i-a_i|>1$.

---

## Invariants & tie‑break determinism

* **Mass conservation:** $\sum_i n_i=N$ (checked).
* **Non‑negativity:** $n_i\in\mathbb{Z}_{\ge 0}$.
* **Stable ordering:** residual sort key = $(r_i\ \downarrow,\ \texttt{country_set.rank}\ \uparrow,\ \text{ISO}\ \uparrow)$ with $r_i$ quantised to 8 dp; prevents platform‑dependent ties and preserves the S6 Gumbel order as the prior.
* **RNG lineage:** One `dirichlet_gamma_vector` event per merchant with $|C|>1$; $|C|$ `residual_rank` events always (including the $|C|=1$ case). Paths & schemas are fixed across runs.

---

## Outputs (persisted artefacts & logs)

1. **`ranking_residual_cache_1A`** (parameter‑scoped, seed‑partitioned):  
   Per $(\text{merchant_id},\ \text{country_iso})$, persist the **quantised residual** and its **`residual_rank`** (and any other fields already present in the **existing schema**). Produced by **`1A.integerise_allocations`**.

2. **RNG events** (JSONL):
   * `dirichlet_gamma_vector` at `logs/rng/events/dirichlet_gamma_vector/seed=…/parameter_hash=…/run_id=…/` with arrays `(country_isos, alpha, gamma_raw, weights)`. Producer: **`1A.dirichlet_allocator`**.
   * `residual_rank` at `logs/rng/events/residual_rank/…/` with `(merchant_id, country_iso, residual, residual_rank)`; one event per country. Producer: **`1A.integerisation`**.

3. **No changes to `country_set`** in S7 (it remains the sole authority for cross‑country order; inter‑country order is **not** encoded in `outlet_catalogue`). Consumers needing order must join to `country_set.rank`.

---

## Complexity

Per merchant: gamma sampling $O(m)$; sort by residuals $O(m\log m)$ with $m=K_m^\star+1$. Typical $m$ is small (tens). Deterministic serial ops throughout.

---

## Notes on correctness & governance

* Dirichlet event enforces array length equality and $\sum w_i = 1$ to $10^{-6}$; violations abort.
* The **α‑key resolution** (ladder & whether fallback used) may be logged in the **validation bundle** diagnostics; no new datasets are introduced.
* Naming alignment: `residual_rank` (integerisation order) is **distinct** from `site_order` (within‑country sequence used later for outlet IDs).

---

### Summary (one‑liner)

S7 transforms $N$ and the ordered set $C$ into exact integer per‑country counts $\{n_i\}$ via $\mathrm{Dirichlet}(\alpha)$ weights and a fully deterministic **largest‑remainder** scheme that prioritises **Gumbel order** in tie‑breaks and preserves full RNG lineage for reproducibility.
