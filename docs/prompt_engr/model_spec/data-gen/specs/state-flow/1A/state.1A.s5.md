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

For an ISO-4217 currency $\kappa$, let its member-country set be

$$
\mathcal{D}(\kappa)=\{i_1,\dots,i_D\}\subset\mathcal{I},\quad D=|\mathcal{D}(\kappa)|.
$$

From `ccy_country_shares_2024Q4`, let $y_i\in\mathbb{Z}_{\ge0}$ denote the **observation count** for destination country $i\in\mathcal{D}(\kappa)$; define

$$
Y=\sum_{i\in\mathcal{D}(\kappa)} y_i .
$$

Define the **additive Dirichlet smoothing constant**

$$
\alpha:=0.5.
$$

Policy threshold for sparsity/fallback:

$$
T:=30.
$$

These values come from the subsegment assumptions.

We also define **smoothed counts**

$$
\tilde y_i = y_i + \alpha,\qquad \tilde Y = \sum_i \tilde y_i = Y + \alpha D .
$$

---

## S5.3 Deterministic expansion (math, per currency $\kappa$)

**Case A — Single-country currency $(D=1)$.**
Weights are degenerate:

$$
w_{i_1}^{(\kappa)} := 1.
$$

Emit one row in `ccy_country_weights_cache` with `weight=1`, `obs_count=y_{i_1}`, `smoothing=null`, and `sparse_flag=false` for this currency (see persistence below).

**Case B — Multi-country currency $(D\ge2)$.**

1. **Compute candidate weight vectors**

$$
\hat w_i := 
\begin{cases}
\frac{y_i}{Y}, & Y>0,\\[2pt]
\text{undefined}, & Y=0,
\end{cases}
\qquad
\tilde w_i := \frac{\tilde y_i}{\tilde Y} = \frac{y_i+\alpha}{Y+\alpha D}.
$$

2. **Choose smoothing vs. raw.**
   Use the *smoothed* vector $\tilde w$ **iff** any destination is sparse at the cell level:

$$
\min_{i} y_i < T \ \ \Rightarrow\ \ w^{(\kappa)} \leftarrow \tilde w\ \text{ and record `smoothing="alpha=0.5"`};
$$

otherwise (all $y_i\ge T$ and $Y>0$), use the *raw* vector $w^{(\kappa)} \leftarrow \hat w$ with `smoothing=null`. (This is the “apply additive Dirichlet smoothing $\alpha=0.5$” rule—engaged **when** any destination count is below threshold.)

3. **Global sparsity/fallback test (per currency).**
   If the **post-smoothing mass is still insufficient**,

$$
\tilde Y < T + \alpha D \quad\Longleftrightarrow\quad Y < T,
$$

then **fallback to equal split**

$$
w^{(\kappa)}_i \leftarrow \frac{1}{D}\quad\text{for all }i,
$$

and set the per-currency `sparse_flag` to **true** (obs_count $=Y$, threshold $=T$). Otherwise, `sparse_flag=false`. (This matches: “if total post-smoothing mass insufficient … fall back to equal split (flag `sparse_flag=true`).”)

4. **Renormalise and order.**
   Numerically enforce

$$
\sum_{i} w^{(\kappa)}_i = 1\quad\text{(binary64; renormalise if needed within }10^{-12}\text{),}
$$

and **order deterministically by ISO (ASCII)** when persisting rows. (The cache schema also enforces a *group_sum_equals_one* constraint per currency.)

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

