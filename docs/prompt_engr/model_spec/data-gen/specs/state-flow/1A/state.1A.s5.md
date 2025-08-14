# S5 — Currency → Country expansion & deterministic weights (no RNG)
**Preamble.** For each merchant $m$, the currency $\kappa_m$ is read from the `merchant_currency` cache produced by **S5.0**; S5 does not infer or override $\kappa_m$.

## S5.0 — Merchant currency κₘ (deterministic, no RNG)

**Purpose.** Fix the merchant’s settlement currency κₘ exactly once, with stable tie‑breaks, and persist a tiny cache for downstream S5/S6 consumers.

**Inputs (per merchant m).**
* Optional per‑merchant **currency share vector** `s^(ccy)_m` from ingress (schema `schemas.ingress.layer1.yaml#/settlement_shares`), keyed by ISO‑4217 currency.
* Merchant **home ISO** `c = home_country_iso_m` and a pinned table of **primary legal tender** per ISO (ingress canon).
* Lineage: `parameter_hash`, `manifest_fingerprint`.

**Algorithm (purely deterministic).**

1) If ingress provides a per‑merchant currency share vector `s^(ccy)_m`:
$$
\kappa_m \;:=\; \arg\max_{\kappa} s^{(\mathrm{ccy})}_{m,\kappa}
$$
Break ties by **ISO‑4217** ASCII lexicographic order on the currency code.

2) Else (no per‑merchant vector), set $\kappa_m$ to the **primary legal tender** of the merchant’s **home** ISO using the pinned lookup. If multiple legal tenders are marked “primary”, break ties lexicographically by ISO‑4217 code.

3) Persist one row to `merchant_currency/parameter_hash={parameter_hash}/…` with `{ merchant_id, kappa, source, tie_break_used, manifest_fingerprint }`
where `source ∈ {"ingress_share_vector","home_primary_legal_tender"}` and `tie_break_used ∈ {true,false}`.

**Outputs.**
* Dataset: `merchant_currency` (schema `schemas.1A.yaml#/prep/merchant_currency`), partitioned by `{parameter_hash}`.

**Determinism & failures.**
* No RNG. Any missing FK for ISO/currency, or an empty legal‑tender mapping for `home`, is a hard abort.

**Downstream contract.** S5/S6 **must** read $\kappa_m$ from `merchant_currency` and *not* recompute it.



## S5.1 Universe, symbols, authority

* **Domain.** This state is evaluated **only** for merchants that (a) are multi-site (S1) and (b) reached/cleared S4 (i.e., $K_m\ge1$ was drawn). S5 itself is **deterministic** and produces the *candidate weight system over countries* that S6 will sample from.
* **Authoritative reference inputs.**

  * **Currency→country splits (with observation counts):** dataset `ccy_country_shares_2024Q4` (ingress reference). Schema: `schemas.ingress.layer1.yaml#/ccy_country_shares`.
  * **Settlement shares at currency level:** `settlement_shares_2024Q4` (ingress reference). Schema: `schemas.ingress.layer1.yaml#/settlement_shares`. (Not needed to *compute* the intra-currency weights but governs the wider candidate assembly in 1A.)
  * **ISO-3166 canonical list:** used for FK / ordering. (Via schema FK for `country_iso`.);
* **Authoritative outputs and schemas.**
  * `merchant_currency` (per‑merchant κₘ), schema `schemas.1A.yaml#/prep/merchant_currency`, partitioned by `{parameter_hash}`.  ← produced by S5.0
  * `ccy_country_weights_cache` (deterministic expanded weights), schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`, partitioned by `{parameter_hash}`.
  * `sparse_flag` (per-currency sparsity decision), schema `schemas.1A.yaml#/prep/sparse_flag`, partitioned by `{parameter_hash}`.

---

## S5.2 Symbols and fixed hyperparameters

For an ISO-4217 currency $\kappa$, define the **member-country set**:

$$
\mathcal{D}(\kappa) = \{i_1, \dots, i_D\} \subset \mathcal{I}, \quad D = |\mathcal{D}(\kappa)|.
$$

From `ccy_country_shares_2024Q4`, let $y_i \in \mathbb{Z}_{\ge 0}$ be the **observation count** for destination $i \in \mathcal{D}(\kappa)$. Let

$$
Y := \sum_{i \in \mathcal{D}(\kappa)} y_i
$$

be the **total observation count** for $\kappa$.

**Fixed hyperparameters** (from subsegment assumptions):

* Additive Dirichlet smoothing constant: $\alpha := 0.5$.
* Sparsity threshold: $T := 30$ observations — used both for *destination-level* sparsity and the *global* total-mass test.

Define **smoothed counts**:

$$
\tilde{y}_i := y_i + \alpha, \qquad
\tilde{Y} := Y + \alpha D.
$$

---

## S5.3 Deterministic expansion (math, per currency $\kappa$)

**Case A — Single-country currency ($D = 1$).**  
Degenerate weights:
$$
w_{i_1}^{(\kappa)} := 1.
$$
Persist with `obs_count = y_{i_1}`, `smoothing = null`. Mark `is_sparse = false` in `sparse_flag`.

**Case B — Multi-country currency ($D \ge 2$).**

1. **Destination-level sparsity flag.**  
   $\text{dest_sparse} := \big[ \min_{i} y_i < T \big]$

2. **Global sparsity flag.**  
   $\text{is_sparse}(\kappa) := \big[ Y < T + \alpha D \big]$

3. **Weight vector.**
   * If `is_sparse(κ) = true` (global sparse):  
     $$w_i \leftarrow \frac{1}{D} \quad\forall i$$  
     `smoothing = "equal_split_fallback"`.
   * Else if `dest_sparse = true`:  
     $$w_i \leftarrow \frac{\tilde{y}_i}{\tilde{Y}}$$  
     `smoothing = "alpha=0.5"`.
   * Else (no sparsity):  
     $$w_i \leftarrow \frac{y_i}{Y}$$  
     `smoothing = null`.

4. **Guards.**  
   Require $w_i > 0$ for all emitted $i$. If any $w_i \le 0$ after smoothing, abort as artefact error.

5. **Renormalise & order.**  
   Compute the sum with a **fixed-order compensated sum (Neumaier, binary64)** over **ISO-lexicographic** indices, then renormalise if needed:
   $$
   S=\texttt{sum_comp}(w);\quad \text{if }|S-1|>10^{-12}\text{ then }w_i\leftarrow \frac{w_i}{S},\;S'=\texttt{sum_comp}(w),\;\;|S'-1|\le 10^{-12}.
   $$
   **Prohibitions:** no BLAS/parallel reductions; no vectorised reductions for this step.

   **Algorithm (Neumaier variant, binary64; fixed ISO order):**
   ```
   function sum_comp(xs[0..m-1]):
       s = 0.0    // binary64
       c = 0.0    // compensation (binary64)
       for i in 0..m-1 in ISO-lexicographic order:
           x = xs[i]
           t = s + x
           if abs(s) >= abs(x):
               c += (s - t) + x
           else:
               c += (x - t) + s
           s = t
       return s + c
   ```
6. **Emit.**  
   For each $(\kappa, i)$ persist:
   * `weight = w_i`  
   * `obs_count = y_i`  
   * `smoothing` as per step 3.  

   For each $\kappa$ persist one `sparse_flag` row:
   * `is_sparse = is_sparse(κ)`  
   * `obs_count = Y`, `threshold = T`

**Summary (multi-country).**

$$
w^{(\kappa)}=
\begin{cases}
\text{equal}(D), & \tilde Y < T+\alpha D,\\[4pt]
\tilde w, & \tilde Y \ge T+\alpha D \text{ and }\min_i y_i < T,\\[4pt]
\hat w, & \tilde Y \ge T+\alpha D \text{ and }\min_i y_i \ge T.
\end{cases}
$$

---

## S5.4 Persistence: tables, keys, and partitioning
No schema changes in Batch 2.C; persistence maps directly to the existing `ccy_country_weights_cache` and `sparse_flag` tables.

**A) `ccy_country_weights_cache`** (deterministic).
For each $(\kappa, i)$ pair we persist:

$$
(\texttt{manifest_fingerprint},\ \texttt{currency}=\kappa,\ \texttt{country_iso}=i,\ \texttt{weight}=w^{(\kappa)}_i,\ \texttt{obs_count}=y_i,\ \texttt{smoothing}\in\{\texttt{null},\ \text{"alpha=0.5"},\ \text{"equal_split_fallback"}\}),
$$

partitioned by `{parameter_hash}` under the schema `#/prep/ccy_country_weights_cache`. The schema enforces **group_sum_equals_one** per currency.

**B) `sparse_flag`** (per currency).
One row per $\kappa$:

$$
(\texttt{manifest_fingerprint},\ \texttt{currency}=\kappa,\ \texttt{is_sparse}=\mathbf{1}\{\tilde Y < T+\alpha D\},\ \texttt{obs_count}=Y,\ \texttt{threshold}=T),
$$

partitioned by `{parameter_hash}`, schema `#/prep/sparse_flag`.

Both datasets’ **paths/lineage** are fixed by the data dictionary and are versioned by **`{parameter_hash}`** (parameter-scoped caches).

---
## S5.5 Determinism & correctness invariants

* **I-W1 (no RNG).** S5 is **purely deterministic** given the reference inputs; no Philox usage and no event streams in this state. (RNG will be used in S6 Gumbel keys.)
* **I-W2 (sum constraint).** For each currency $\kappa$, persisted weights satisfy $\sum_i w^{(\kappa)}_i = 1$ within the schema tolerance $10^{-6}$. (Hard-checked by the schema constraint.)
* **I-W3 (ordering).** Rows for a given $\kappa$ are **sorted by `country_iso` (ASCII)** to ensure reproducible joins and stable downstream key order. (Assumptions specify deterministic ISO ordering.)
* **I-W4 (fallback semantics).** `is_sparse=true` **iff** the equal-split fallback was used (post-smoothing mass insufficient). Using $\tilde{w}$ due to any $y_i < T$ **does not** alone set `is_sparse=true`.
---

## S5.6 Failure modes (abort semantics)

* **Missing reference rows.** Currency $\kappa$ absent from `ccy_country_shares_2024Q4` or a member ISO not in the canonical ISO table → abort (FK breach).
* **Invalid counts.** Any $y_i<0$ or non-integer (violates ingress schema expectations) → abort.
* **Constraint violation.** Persisted group sum deviates by more than $10^{-6}$, or duplicated PK $(\kappa,i)$ → abort as a schema error.

---

## S5.7 Inputs → outputs (state boundary)

* **Inputs (deterministic):**
  `ccy_country_shares_2024Q4` with per-destination counts $y_i$; hyperparams $\alpha=0.5$, $T=30$; lineage (`parameter_hash`, `manifest_fingerprint`); ISO canonical FK.

* **Outputs:**

  * `ccy_country_weights_cache/parameter_hash={parameter_hash}/…` with rows $(\kappa,i,w^{(\kappa)}_i,y_i,\text{smoothing})$ obeying the group-sum constraint.
  * `sparse_flag/parameter_hash={parameter_hash}/…` with one row per currency recording whether equal-split fallback was used (and the total $Y$ vs. $T$).

