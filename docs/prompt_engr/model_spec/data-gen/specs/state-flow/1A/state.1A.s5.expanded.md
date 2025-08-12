# S5.1 — Universe, symbols, authority

## Goal

Freeze the **scope** and **contracts** for S5: this state **deterministically** constructs the **currency→country candidate weight system** that S6 will sample from (Gumbel-top-k). No RNG is used anywhere in S5; all outputs are **parameter-scoped caches** with reproducible partitions and schema-enforced constraints.

---

## Domain (who/what enters S5)

Evaluate S5 only in runs where a merchant $m$ has **cleared S4** (i.e., an accepted $K_m\ge1$ exists). S5’s computations themselves are **merchant-agnostic**: they build a **global**, deterministic cache keyed by currency and consumed by *all* S6 selections in the run. (If a run has zero eligible merchants, S5 may still materialise caches to satisfy CI.)

---

## Symbols & notation (fixed for S5)

* $\mathcal{I}$: **ISO-3166-1 alpha-2** canonical country set (FK authority, ordering).
* $\kappa$: **ISO-4217 currency** code.
* $\mathcal{D}(\kappa)\subset\mathcal{I}$: member-country set for currency $\kappa$; $D=|\mathcal{D}(\kappa)|$. (Built from the reference split table below.)
* $y_i\in\mathbb{Z}_{\ge0}$: observation count for destination country $i\in\mathcal{D}(\kappa)$ in the **intra-currency splits** reference; $Y=\sum_{i\in\mathcal{D}(\kappa)}y_i$. These are **not** merchant counts.

(Choice of smoothing constants and thresholds is formalised in S5.2; listed here only to pin provenance.)

---

## Authoritative **reference inputs** (read-only)

* **Currency→country splits (with counts)**: `ccy_country_shares_2024Q4`
  Schema: `schemas.ingress.layer1.yaml#/ccy_country_shares`. Carries $(\kappa,i,y_i)$ rows that define $\mathcal{D}(\kappa)$ and the per-destination observation counts used to construct weights.
* **Settlement shares (currency level)**: `settlement_shares_2024Q4`
  Schema: `schemas.ingress.layer1.yaml#/settlement_shares`. Governs the **wider candidate assembly** in 1A (e.g., which currencies are in scope), but **not** the *intra-currency* normalisation in S5.
* **ISO-3166 canonical list**: primary key + ordering authority for `country_iso`. Used for FK checks and to define the deterministic row order.
* **Smoothing policy (config)**: `ccy_smoothing_params` (e.g., $\alpha\approx0.5$, cell/total thresholds), referenced in the artefact registry. Exact values are locked in S5.2.

---

## Authoritative **outputs** (deterministic caches; no RNG)

Both datasets are **parameter-scoped** (partitioned by `{parameter_hash}`) and validated by the dictionary.

1. `ccy_country_weights_cache` — **expanded weights** per $(\kappa,i)$:
   Schema: `schemas.1A.yaml#/prep/ccy_country_weights_cache`.
   Path: `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/`.
   Enforced constraint: **group_sum_equals_one** by currency (weights sum to 1 within tolerance).

2. `sparse_flag` — **per-currency sparsity decision** used by validation and S6 diagnostics:
   Schema: `schemas.1A.yaml#/prep/sparse_flag`.
   Path: `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/`.

Dictionary entries fix ids→paths→schema refs; CI verifies partitions, FKs, and the sum constraint.

---

## Presence/absence & partitioning contracts

* **No RNG, no event streams** in S5. Everything produced is deterministic and partitioned by **`{parameter_hash}`**; **`manifest_fingerprint`** may be persisted as lineage columns but does not govern partitioning for these caches.
* **FK coherence:** every `country_iso` row in outputs must join to the canonical ISO table; every currency in outputs must appear in `ccy_country_shares_2024Q4`. Violations are **schema errors** (abort run).
* **Ordering:** within a currency $\kappa$, output rows must be **sorted by `country_iso` (ASCII)** to stabilise downstream joins and Gumbel key alignment. (Schema + S5.3/5.4 assert this.)

---

## Interfaces (what S5 consumes / exposes)

* **Consumes:** `ccy_country_shares_2024Q4`, `settlement_shares_2024Q4`, ISO canonical, and smoothing policy config.
* **Exposes to S6:** a **deterministic weight vector** $w^{(\kappa)}$ for each currency $\kappa$ (materialised in `ccy_country_weights_cache`) and an **is_sparse** flag per $\kappa$ (materialised in `sparse_flag`). S6 will combine these weights with the merchant’s **home currency/country** context to form candidate sets and draw Gumbel keys.

---

## Invariants & pre-checks at S5 entry

* **I-S5-A (schema authority).** All inputs are validated against their **ingress** schemas; outputs against their **1A** schemas and the dictionary’s partitioning rules.
* **I-S5-B (no randomness).** S5 must not emit RNG envelopes or consume Philox counters; any presence of RNG events in S5 is a protocol breach.
* **I-S5-C (deterministic equality).** For fixed inputs and `parameter_hash`, the byte content of both outputs is **bit-reproducible** across replays. (CI compares digests for selected currencies.)

---

## Minimal reference algorithm (code-agnostic; “prepare S5 context”)

```text
INPUTS:
  - ccy_country_shares_2024Q4 (rows: currency κ, country_iso i, obs_count y_i)
  - settlement_shares_2024Q4 (rows at currency level; read-only here)
  - iso3166_canonical (authoritative FK + order)
  - ccy_smoothing_params (to be used in S5.2)

OUTPUTS (this sub-state):
  - A validated in-memory map κ ↦ D(κ) = {i_1,…,i_D} and counts {y_i}, ready for S5.2
  - No persisted datasets yet (persistence happens in S5.4)

ALGORITHM:
1  Load iso3166_canonical; build set I of valid ISO-3166 alpha-2 codes.
2  Load ccy_country_shares_2024Q4.
3  Referential integrity:
   3.1 Assert every row’s country_iso ∈ I (FK check).
   3.2 Assert κ,country_iso pairs are unique (no duplicate (κ,i) keys).
   3.3 Assert obs_count y_i are integers and y_i ≥ 0.
4  Build per-currency membership and counts:
   4.1 For each κ, collect D(κ) = {i : (κ,i) appears} and the vector {y_i}.
   4.2 Compute Y(κ) = Σ_{i∈D(κ)} y_i (store for diagnostics).
   4.3 Record D = |D(κ)|.
5  Ordering contract:
   5.1 For each κ, sort D(κ) by country_iso (ASCII); store this order for all later steps.
6  Emit readiness (in-memory only): the map κ ↦ (ordered D(κ), y_i, Y, D).
   (S5.2 will apply smoothing/thresholds to construct weights; S5.4 persists.)
```

This pins S5’s **authority surface**: exactly which inputs are trusted, the **deterministic** nature of the step, the **partitioning and schema contracts** for its outputs, and the FK/ordering rules that make S6’s stochastic selection reproducible and auditable.

---

# S5.2 — Symbols and fixed hyperparameters

## Goal

Freeze the **notation and constants** that govern currency→country expansion. Nothing is persisted yet; S5.2 just defines the objects S5.3 will transform into **deterministic country weight vectors** (no RNG anywhere in S5).

---

## Domain & primary symbols (per currency $\kappa$)

* $\mathcal{I}$: canonical ISO-3166 alpha-2 country set (FK authority).
* $\kappa$: ISO-4217 currency code.
* **Member set**:

  $$
  \boxed{\,\mathcal{D}(\kappa)=\{i_1,\dots,i_D\}\subset\mathcal{I},\quad D=|\mathcal{D}(\kappa)|\,}
  $$

  derived from the ingress table `ccy_country_shares_2024Q4` (PK $(\kappa,i)$).
* **Observation counts** (ingress): for each $i\in\mathcal{D}(\kappa)$,

  $$
  \boxed{\,y_i\in\mathbb{Z}_{\ge 0}\,},\qquad Y=\sum_{i\in\mathcal{D}(\kappa)} y_i .
  $$

  `obs_count` lives alongside proportional `share` in the ingress schema; both are validated on load.

**Upstream guarantees.** FK to canonical ISO holds; $(\kappa,i)$ are unique; $y_i$ are 64-bit integers with $y_i\ge 0$. Any breach is an ingress/schema error (not an S5.2 concern).

---

## Fixed hyperparameters (from subsegment assumptions)

* **Additive Dirichlet smoothing constant** (symmetric prior):

  $$
  \boxed{\,\alpha := 0.5\,}
  $$

  (Engages light shrinkage; removes zero-mass cells when needed.)
* **Policy threshold for sparsity/fallback**:

  $$
  \boxed{\,T := 30\,}
  $$

  used (i) as a **cell-level** trigger for smoothing choice, and (ii) as a **global** test for equal-split fallback.

These values are fixed by the 1A subsegment assumptions for this vintage; they are not tuned inside S5.

---

## Derived quantities (always available to S5.3)

* **Cell-level minimum mass**: $y_{\min}=\min_{i\in\mathcal{D}(\kappa)} y_i$.
  Indicator for cell sparsity: $\mathbf{1}\{y_{\min} < T\}$.
* **Smoothed counts** (additive Dirichlet):

  $$
  \boxed{\,\tilde y_i := y_i+\alpha,\qquad \tilde Y := \sum_i \tilde y_i = Y + \alpha D\,}.
  $$

  Note $\tilde y_i > 0$ and $\tilde Y > 0$ whenever $D\ge1$ and $\alpha > 0$.
* **Candidate weight vectors** (defined for use in S5.3):

  $$
  \hat w_i :=
  \begin{cases}
    \dfrac{y_i}{Y}, & Y > 0,\\[2pt]
    \text{undefined}, & Y=0,
  \end{cases}
  \qquad
  \tilde w_i := \dfrac{\tilde y_i}{\tilde Y}=\dfrac{y_i+\alpha}{Y+\alpha D}.
  $$

  The raw vector $\hat w$ is only meaningful when $Y > 0$; the smoothed $\tilde w$ is always well-defined and strictly positive. (S5.3 specifies *which* one becomes $w^{(\kappa)}$.)

---

## Numerical discipline & invariants (checked now, used later)

* **I-Params.** $\alpha > 0$ and $T\in\mathbb{Z}_{\ge 0}$ are constants for the run; $\alpha=0.5,\ T=30$.
* **I-Domain.** $D\ge1$. If $D=1$, S5.3 will set $w^{(\kappa)}=\text{degenerate}(1)$. If $D\ge2$, both $\hat w$ (when $Y > 0$) and $\tilde w$ are properly normalised in binary64.
* **I-Normalisation.** $\sum_i \tilde w_i=1$ exactly in real arithmetic; implementations must evaluate in IEEE-754 binary64 and may re-normalise in S5.3 to enforce the schema tolerance (e.g., $10^{-12}$ at construction, $10^{-6}$ at persistence).
* **I-No RNG.** S5.2 computes only deterministic functions of ingress counts and constants; no RNG envelopes appear in S5.

---

## Interpretability (why $\alpha=0.5$, why $T=30$)

* $\alpha=0.5$ is a **symmetric Dirichlet** prior that supplies **gentle** shrinkage (Jeffreys-style) to avoid zero probabilities while not overwhelming well-supported cells. It is only *activated* downstream when any $y_i < T$.
* $T=30$ plays two roles:

  * **Cell threshold**: if any cell has $y_i < T$, prefer $\tilde w$ over $\hat w$ (use smoothing).
  * **Global fallback**: if $Y < T$ (equivalently $\tilde Y < T+\alpha D$), S5.3 will **equal-split** and set `sparse_flag=true`.

---

## What S5.2 exports to S5.3 (no persistence yet)

$$
\boxed{\,\big(\mathcal{D}(\kappa),\ D,\ \{y_i\}_{i\in\mathcal{D}(\kappa)},\ Y,\ y_{\min},\ \{\tilde y_i\},\ \tilde Y,\ \hat w,\ \tilde w,\ \alpha,\ T\big)\,}
$$

All quantities are **deterministic** functions of ingress and fixed hyperparameters; S5.3 consumes them to choose the **final** $w^{(\kappa)}$ and to decide whether to set `sparse_flag`.

---

## Minimal reference algorithm (code-agnostic; per currency $\kappa$)

```text
INPUT:
  - Ingress rows for a fixed currency κ: {(i, y_i)} with i ∈ I (FK-checked), y_i ∈ ℤ_{\ge 0}
  - Constants: α = 0.5, T = 30

OUTPUT (to S5.3; not persisted here):
  - D(κ) ordered by country_iso (ASCII), D = |D(κ)|
  - Scalars: Y = Σ_i y_i, y_min = min_i y_i
  - Smoothed counts: {tilde_y_i = y_i + α},  tilde_Y = Y + α D
  - Candidate weight vectors: raw hat_w (if Y > 0), smoothed tilde_w

ALGO:
1  Collect member set D(κ) = {i} from ingress; assert D ≥ 1; sort i by ISO (ASCII).
2  For each i in D(κ): read integer y_i ≥ 0.
3  Compute Y := Σ_i y_i and y_min := min_i y_i.
4  Compute smoothed counts: tilde_y_i := y_i + α and tilde_Y := Y + α·D.
5  If Y > 0: define hat_w_i := y_i / Y for all i; else mark hat_w undefined.
6  Define tilde_w_i := tilde_y_i / tilde_Y for all i.   # strictly positive; sums to 1
7  Export {D(κ), Y, y_min, {tilde_y_i}, tilde_Y, hat_w (maybe undefined), tilde_w, α, T}.
```

This closes S5.2 with everything S5.3 needs to implement your **smoothing rule** (“use $\tilde w$ if any $y_i < T$; else $\hat w$; fallback equal split if $Y < T$”) and to persist the caches with the correct **partitioning and constraints** later in S5.4.

---

# S5.3 — Deterministic expansion (per currency $\kappa$)

## Goal

For each ISO-4217 currency $\kappa$, construct a **deterministic** country weight vector

$$
w^{(\kappa)}=\{w^{(\kappa)}_i\}_{i\in\mathcal{D}(\kappa)},\qquad \sum_i w^{(\kappa)}_i=1,
$$

from **ingress counts** $y_i$ and **fixed hyperparameters** $\alpha=0.5,\ T=30$. No RNG is used anywhere in S5. Outputs are later persisted to `ccy_country_weights_cache` (and `sparse_flag`) under `{parameter_hash}` with schema constraints (group sum equals one).

---

## Inputs and notation (per currency $\kappa$)

* Member set $\mathcal{D}(\kappa)=\{i_1,\dots,i_D\}$, $D=|\mathcal{D}(\kappa)|$ (from `ccy_country_shares_2024Q4`; ISO FK enforced).
* Counts $y_i\in\mathbb{Z}_{\ge0}$ and total $Y=\sum_i y_i$.
* Hyperparameters (fixed for the run): $\alpha=0.5$, $T=30$.
* Smoothed counts and total:

  $$
  \tilde y_i=y_i+\alpha,\qquad \tilde Y=Y+\alpha D.
  $$

  Define **raw** $\hat w_i:=y_i/Y$ (only if $Y > 0$) and **smoothed** $\tilde w_i:=(y_i+\alpha)/(Y+\alpha D)$.

All arithmetic is **IEEE-754 binary64**; final vectors are **re-normalised** to unit sum within $10^{-12}$ (construction) and must satisfy the schema’s $10^{-6}$ tolerance at persistence.

---

## Case A — Single-country currency ($D=1$)

The weight vector is **degenerate**:

$$
\boxed{w^{(\kappa)}_{i_1}=1.}
$$

This is invariant to $y_{i_1}$ (including $y_{i_1}=0$). Persist with `smoothing=null`, `sparse_flag=false`. Rationale: there is no intra-currency ambiguity when only one member exists.

---

## Case B — Multi-country currency ($D\ge 2$)

### Step B1 — Compute candidate vectors

$$
\hat w_i=\frac{y_i}{Y}\ \ (\text{defined iff }Y > 0),\qquad
\tilde w_i=\frac{y_i+\alpha}{Y+\alpha D}\ \ (\text{always defined, strictly positive}).
$$

Properties:

* $\hat w$ is **scale-invariant** in $y$ and has zeros where $y_i=0$.
* $\tilde w$ is **proper** (all components $ > 0$) and contracts toward equal-split as $Y\downarrow 0$ (magnitude of the shrink $\propto \alpha/Y$).

### Step B2 — Cell-level sparsity rule (raw vs smoothed)

Define $y_{\min}=\min_i y_i$. Use:

$$
\boxed{\
\text{if }y_{\min} < T\text{ then }w^{(\kappa)}\leftarrow\tilde w\ \ (\text{record } \texttt{smoothing}="alpha=0.5");\quad
\text{else }w^{(\kappa)}\leftarrow\hat w\ \ (\texttt{smoothing}=null).
}
$$

This implements: “apply additive Dirichlet smoothing $\alpha=0.5$ **iff** any destination is sparse.” When all cells are well-supported ($\min_i y_i\ge T$ and $Y > 0$), prefer raw empirical proportions. If $Y=0$, the premise $y_{\min} < T$ is automatically true (since $T > 0$), so we safely fall to $\tilde w$.

**Interpretation.** The smoothed vector equals

$$
\tilde w_i=\underbrace{\frac{Y}{Y+\alpha D}}_{\text{data weight}}\hat w_i+\underbrace{\frac{\alpha D}{Y+\alpha D}}_{\text{prior weight}}\cdot \frac{1}{D}.
$$

So $\tilde w$ is a convex combination of $\hat w$ and **equal split**, with prior weight increasing as $Y$ decreases—exactly the intended stabilisation. (This identity follows by adding and subtracting $\tfrac{\alpha}{Y+\alpha D}$ appropriately; the convexity weights are positive and sum to 1.)

### Step B3 — Global sparsity / fallback (per currency)

Even after B2, if overall support is too small, **force equal split**:

$$
\boxed{\ \tilde Y < T+\alpha D\quad\Longleftrightarrow\quad Y < T\ \ \Rightarrow\ \ w^{(\kappa)}_i\leftarrow\frac{1}{D}\ \forall i,\ \ \texttt{sparse_flag}=\texttt{true}\ }.
$$

Equivalence proof: $\tilde Y=Y+\alpha D < T+\alpha D\iff Y < T$. We annotate this branch with `smoothing="equal_split_fallback"` at persistence. If $Y\ge T$, set `sparse_flag=false`.

**Why this two-tier rule?**

* B2 guards **cell** sparsity (holes or small cells) by moving some mass to neighbours via $\alpha$.
* B3 guards **global** sparsity (total evidence too low) by discarding the (noisy) profile entirely; equal split avoids over-interpreting a tiny $Y$.  The `sparse_flag` is a **diagnostic**: `true` **iff** B3 fired (not merely because B2 used smoothing).

### Step B4 — Renormalise and order

Compute $s=\sum_i w^{(\kappa)}_i$ in binary64 and **renormalise** $w^{(\kappa)}_i\leftarrow w^{(\kappa)}_i/s$ to enforce $\sum_i w^{(\kappa)}_i=1$ within $10^{-12}$. Persist **rows sorted by `country_iso` (ASCII)** to stabilise joins and S6 key alignment; the cache schema enforces *group_sum_equals_one* at tolerance $10^{-6}$.

---

## Edge cases & guarantees (removing ambiguity)

* **All zeros, multi-country.** If $Y=0$ then $y_{\min}=0 < T$ ⇒ choose $\tilde w$; since $Y < T$ also, B3 **overrides** to **equal split** with `sparse_flag=true`. Deterministic, no division by zero.
* **One tiny cell, big others.** If $\min_i y_i < T$ but $Y\ge T$, we **use $\tilde w$** (smooth locally) and keep `sparse_flag=false` (B3 not triggered). This matches the “cell-sparse but globally supported” regime.
* **All cells ≥T.** Use **raw** $\hat w$ (if $Y > 0$); `smoothing=null`, `sparse_flag=false`. If in that regime $\hat w$ happens to be uniform already, we still record `smoothing=null` (it was a data fact, not a fallback).
* **$D=1$ with $y_{i_1}=0$.** Remains $w=1$ (Case A), `smoothing=null`, `sparse_flag=false`. The fallback logic is **not** applied when $D=1$.

**Monotonicity / continuity.**

* As $Y\to\infty$ with fixed proportions, $\tilde w\to\hat w$.
* As $Y\to 0$ (multi-country), $\tilde w\to$ equal-split; B3 then forces exact equal-split with an explicit flag.

---

## What S5.3 “exports” to S5.4 (persistence)

For each $(\kappa,i)$ in ISO order, provide the **final** $w^{(\kappa)}_i$, the original $y_i$, and a **smoothing tag**:

$$
\texttt{smoothing}\in\{\texttt{null},\texttt{"alpha=0.5"},\texttt{"equal_split_fallback"}\}.
$$

S5.4 will persist to `ccy_country_weights_cache` under `{parameter_hash}`, and write one row per $\kappa$ to `sparse_flag` (`is_sparse = (Y < T)`). Both datasets/paths/schemas are fixed by the data dictionary and schema authority policy.

---

## Determinism & validation hooks

* **No RNG** anywhere in S5 (replay is byte-for-byte under fixed inputs).
* **Group sum**: $\sum_i w^{(\kappa)}_i=1$ (schema-enforced).
* **Ordering**: rows sorted by ISO; any other order is a schema/pipeline breach.
* **Flag semantics**: `is_sparse=true` **iff** equal-split fallback was taken (i.e., $Y < T$). Using $\tilde w$ alone does **not** assert sparsity.

---

## Minimal reference algorithm (code-agnostic; per currency $\kappa$)

```text
INPUT:
  - Ordered member list D(κ) = {i1,...,iD} (ASCII ISO order), D ≥ 1
  - Counts {y_i ∈ ℤ_{≥0}}, total Y = Σ_i y_i
  - Constants: α = 0.5, T = 30

OUTPUT (to S5.4):
  - Final weights {w_i} summing to 1
  - Per-(κ,i): obs_count = y_i, smoothing tag
  - Per-κ: sparse_flag = (Y < T)

ALGO:
A) If D = 1:
   w_{i1} ← 1.0
   smoothing ← null
   sparse_flag ← false
   EXPORT and STOP

B) (D ≥ 2):
   # Candidate vectors
   if Y > 0: hat_w_i ← y_i / Y  for all i
   tilde_w_i ← (y_i + α) / (Y + α·D)  for all i      # strictly positive

   # Cell-level decision (raw vs smoothed)
   if min_i y_i < T:
       w_i ← tilde_w_i                   # smoothing engaged
       smoothing ← "alpha=0.5"
   else:
       assert Y > 0
       w_i ← hat_w_i
       smoothing ← null

   # Global fallback (insufficient total support)
   if Y < T:                             # ⇔ (Y + α·D) < (T + α·D)
       w_i ← 1/D for all i
       smoothing ← "equal_split_fallback"
       sparse_flag ← true
   else:
       sparse_flag ← false

   # Renormalise & finish
   s ← Σ_i w_i      # binary64
   w_i ← w_i / s    # enforce Σ_i w_i = 1 within 1e-12 (schema allows 1e-6 at persistence)
   EXPORT { (i, w_i, y_i, smoothing) for i in ISO order } and sparse_flag
```

This nails the **full decision surface** (raw vs smoothed vs equal-split), the **edge-case behaviour** ($Y=0$, $D=1$), the **exact flags/smoothing tags** you persist, and the **schema/partition contracts** your validators rely on.

---

# S5.4 — Persistence: tables, keys, and partitioning

## Goal

Materialise the **deterministic** outputs of S5.3 into two **parameter-scoped caches** with fixed schemas and paths, so S6 can consume them without ambiguity and S9 can assert invariants. No RNG appears in S5; these are **pure functions** of ingress + fixed hyperparameters.

---

## What gets written (row contracts)

### A) `ccy_country_weights_cache` (expanded weights; per $(\kappa,i)$)

Persist one row per currency–country pair:

$$
(\texttt{manifest_fingerprint},\ \texttt{currency}{=}\kappa,\ \texttt{country_iso}{=}i,\ \texttt{weight}{=}w^{(\kappa)}_i,\ \texttt{obs_count}{=}y_i,\ \texttt{smoothing}\in\{\texttt{null},\texttt{"alpha=0.5"},\texttt{"equal_split_fallback"}\}).
$$

This table is governed by `schemas.1A.yaml#/prep/ccy_country_weights_cache` and **partitioned by `{parameter_hash}`**. The schema enforces **`group_sum_equals_one`** per currency with tolerance $10^{-6}$. Columns: PK = $[\texttt{currency},\texttt{country_iso}]$; `weight` is `pct01`; `obs_count` is `int64 ≥ 0`; `manifest_fingerprint` matches `^[a-f0-9]{64}$`; `country_iso` FK joins ISO canonical.

**Ordering.** Rows for a given $\kappa$ **must** be sorted by `country_iso` (ASCII) to stabilise joins and downstream key alignment.

### B) `sparse_flag` (per currency)

Persist one row per currency:

$$
(\texttt{manifest_fingerprint},\ \texttt{currency}{=}\kappa,\ \texttt{is_sparse}{=}\mathbf{1}\{Y{ < }T\},\ \texttt{obs_count}{=}Y,\ \texttt{threshold}{=}T).
$$

Schema `schemas.1A.yaml#/prep/sparse_flag`; **partitioned by `{parameter_hash}`**. Note the indicator uses the **global fallback condition** $Y < T$ (equivalently $\tilde Y < T+\alpha D$); using smoothed $\tilde w$ alone does **not** set this flag. Columns are typed: `is_sparse` boolean, `obs_count` and `threshold` `int64 ≥ 0`.

**Paths & scope.** Both datasets are **parameter-scoped caches** (versioned by `{parameter_hash}`) with fixed dictionary paths:

* `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/…`
* `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/…`

Each row carries `manifest_fingerprint` for lineage, but **partitioning** is by `{parameter_hash}` only.

---

## Determinism, numerics, and ordering (how to get bit-stable output)

* **No RNG anywhere in S5.** These tables are deterministic functions of ingress + $(\alpha{=}0.5,\,T{=}30)$. CI can compare digests across replays.
* **Sum-to-1 enforcement.** Before writing each currency group, compute $s=\sum_i w^{(\kappa)}_i$ in binary64 and **renormalise** $w_i\leftarrow w_i/s$ if $|1-s| > 10^{-12}$. The schema then checks $|\sum_i w_i - 1|\le 10^{-6}$ on read.
* **Ordering discipline.** Emit per-currency rows **sorted** by `country_iso` (ASCII). This is part of S5’s invariants and avoids nondeterminism in downstream Gumbel key alignment.
* **Lineage fields.** `manifest_fingerprint` is the run-level lineage (hex64) from S0; it travels with every row. Partitioning/versioning is by `{parameter_hash}` per dictionary.
* **Storage policy.** Parquet, parameter-scoped partition, internal retention; compression policy (e.g., ZSTD-3) may be applied as per storage config but does not affect semantics.

---

## Validation hooks (what CI asserts)

* **Schema conformance** on both tables (types, required columns, FK on `country_iso`, regex on fingerprint).
* **Group sums** per currency satisfy the 1e-6 tolerance; duplicate PKs are disallowed.
* **Flag semantics.** `is_sparse=true` **iff** equal-split fallback fired in S5.3 (i.e., $Y < T$); smoothed-only branches must have `is_sparse=false`.
* **Partition paths** match dictionary entries exactly (both use `{parameter_hash}`).

---

## Failure semantics (abort conditions)

* **Schema/constraint violation:** group sum fails, PK duplicates, missing columns, wrong types, bad FK, or bad `manifest_fingerprint` pattern ⇒ **abort run** as schema error.
* **Partition/layout violation:** write paths not equal to dictionary patterns (or wrong partition column set) ⇒ **abort run**.

---

## Minimal reference algorithm (code-agnostic; “write both caches”)

```text
INPUTS:
  - For every currency κ: ordered countries {i1,…,iD}, final weights {w_i}, counts {y_i}, total Y, tags from S5.3
  - Lineage: manifest_fingerprint (hex64), parameter_hash
OUTPUTS:
  - Two parquet tables partitioned by {parameter_hash} with schemas:
      #/prep/ccy_country_weights_cache, #/prep/sparse_flag

ALGO:
1  open writer for ccy_country_weights_cache at data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/
2  open writer for sparse_flag              at data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/

3  for each currency κ:
4      # (A) Weights cache rows
5      # enforce ordering and sum-to-1 numerics
6      ensure countries are in ASCII ISO order
7      s ← Σ_i w_i  (binary64)
8      if |1 - s| > 1e-12: w_i ← w_i / s  for all i
9      assert Σ_i w_i within 1 ± 1e-6  (pre-commit guard; schema will also enforce)
10     for each i in order:
11         write row to ccy_country_weights_cache:
12             { manifest_fingerprint, currency=κ, country_iso=i,
13               weight=w_i, obs_count=y_i,
14               smoothing ∈ {null, "alpha=0.5", "equal_split_fallback"} }

15     # (B) Per-currency sparse_flag row
16     is_sparse ← (Y < T)   # ⇔ (tilde_Y < T + α·D)
17     write row to sparse_flag:
18         { manifest_fingerprint, currency=κ, is_sparse, obs_count=Y, threshold=T }

19 close both writers
20 run schema validation on both outputs:
21     - PK uniqueness; FK(country_iso) to ISO canonical
22     - group_sum_equals_one by currency (weights cache)
23     - column types and regex(pattern for manifest_fingerprint)
24 verify partitions == {parameter_hash} per dictionary
25 SUCCESS
```

This pins **exactly** what S5 persists, how it’s keyed and partitioned, the numeric/ordering rules that make it bit-replayable, and the checks that keep the cache trustworthy for S6 (Gumbel-top-$K$).

---

# S5.5 — Determinism & correctness invariants

## Observables (what S5 persists and what validation reads)

* **`ccy_country_weights_cache`**: one row per $(\kappa,i)$ with
  `manifest_fingerprint, currency, country_iso, weight, obs_count, smoothing`, **partitioned by `{parameter_hash}`**, schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`. The schema enforces a **group_sum_equals_one** constraint per currency with tolerance $10^{-6}$.
* **`sparse_flag`**: one row per $\kappa$ with
  `manifest_fingerprint, currency, is_sparse, obs_count=Y, threshold=T`, **partitioned by `{parameter_hash}`**, schema `schemas.1A.yaml#/prep/sparse_flag`.
* Both tables’ **paths/partitions/schemas** are fixed by the data dictionary (parameter-scoped caches):
  `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/…` and
  `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/…`.

---

## I-W1 — No RNG (pure determinism)

**Statement.** S5 performs **no random draws** and emits **no RNG event streams**. The outputs in A and B are **pure functions** of the ingress rows (`ccy_country_shares_2024Q4`), the fixed hyperparameters $\alpha=0.5,\,T=30$, the ISO FK, and the deterministic rules in S5.3; they do **not** depend on `seed` and do **not** vary with Philox counters.

**Replay nuance.** Rows include `manifest_fingerprint` (run lineage). So “bit-for-bit” identity across *different* code/artefact manifests is **not** expected. For **fixed** manifest + inputs, the bytes are reproducible; across different manifests, **value columns** (`weight`, flags) remain the same and only lineage may differ. (Partitioning stays by `{parameter_hash}`.)

**Validator check.** Assert **absence** of any S5 RNG event ids in the dictionary (there are none) and ensure neither S5 table carries RNG envelopes; also assert the partition key set equals `{"parameter_hash"}` exactly.

---

## I-W2 — Sum constraint (per currency)

**Statement.** For each currency $\kappa$, the persisted weights satisfy

$$
\left|\sum_{i\in\mathcal{D}(\kappa)} w^{(\kappa)}_i - 1\right|\le 10^{-6}.
$$

This is **hard-checked** by the schema’s `group_sum_equals_one` constraint. Implementations must compute in IEEE-754 binary64 and may (should) re-normalise within $10^{-12}$ pre-persist to leave headroom for the $10^{-6}$ schema tolerance.

**Edge cases guaranteed by S5.3.**

* $D=1$ ⇒ the group is exactly $\{1\}$.
* $D\ge2$, fallback ⇒ equal split sums to 1 by construction.
* Raw and smoothed branches are explicitly re-normalised before write (construction-time tolerance), then schema enforces at read.

---

## I-W3 — Deterministic ordering

**Statement.** Within each $\kappa$, rows in the weights cache are **sorted by `country_iso` (ASCII)**. This stabilises downstream joins and the **S6 key alignment** (Gumbel-top-$K$ reads weights in this order). The ordering rule is part of S5’s contract and is implied by the ISO FK authority.

**Validator check.** For each $\kappa$, extract the `country_iso` sequence and assert it is **strictly non-decreasing** under ASCII collation; any deviation is a schema/pipeline error (ordering is not left to readers).

---

## I-W4 — Fallback semantics (flag meaning)

**Statement.** `sparse_flag.is_sparse` is **true if and only if** the **equal-split fallback** was taken in S5.3:

$$
\text{is_sparse} = \mathbf{1}\{Y < T\}\quad \text{(equivalently }\mathbf{1}\{\tilde Y < T+\alpha D\}\text{)}.
$$

Using the **smoothed** vector $\tilde{w}$ because some cell $y_i < T$ (but $Y\ge T$) does **not** set `is_sparse=true`. This matches the definition in S5.3 and the persistence spec in S5.4.

**Validator check.** Group by currency; recompute $Y=\sum_i \texttt{obs_count}$; assert `is_sparse == (Y < threshold)` and that `threshold` equals the configured $T$. Also assert that `smoothing="equal_split_fallback"` appears on **every** $(\kappa,i)$ row **iff** `is_sparse=true`.

---

## Failure semantics (what breaks which invariant)

* **Break I-W1:** RNG events present or wrong partitions (anything other than `{parameter_hash}`) ⇒ **schema/protocol failure** (abort run).
* **Break I-W2:** group sum outside $10^{-6}$ or NaN/Inf weights ⇒ **schema failure** (abort run).
* **Break I-W3:** unsorted `country_iso` per $\kappa$ ⇒ **ordering breach** (abort run; S6 reliance on order makes this correctness-critical).
* **Break I-W4:** `is_sparse` not equal to $\mathbf{1}\{Y < T\}$ or inconsistent smoothing tags ⇒ **semantic breach** (abort run).

---

## Minimal reference algorithm (code-agnostic; validator view)

```text
INPUT:
  A = ccy_country_weights_cache partition for {parameter_hash}
  B = sparse_flag partition for {parameter_hash}
  (Both with schemas from schemas.1A.yaml)

OUTPUT:
  Pass/Fail for I-W1..I-W4 with exact offending currencies/rows

1  # I-W1: No RNG, right partitions
2  assert partition_keys(A) == {"parameter_hash"} and partition_keys(B) == {"parameter_hash"}
3  assert no RNG-envelope fields exist in A or B

4  # Pre-indexing by currency
5  for each currency κ in B:
6      rowsκ ← all rows in A where currency == κ, ordered as stored
7      (is_sparse, Y, T) ← row in B for κ

8      # I-W3: Ordering
9      assert country_iso(rowsκ) is ASCII-sorted non-decreasing

10     # I-W2: Sum-to-one
11     s ← Σ weight(rowsκ)  (binary64, serial reduction)
12     assert |1 - s| ≤ 1e-6 and all weights finite and in [0,1]

13     # I-W4: Fallback semantics
14     Ŷ ← Σ obs_count(rowsκ)
15     assert Ŷ == Y           # internal consistency A↔B
16     assert is_sparse == (Y < T)
17     if is_sparse:
18         assert all smoothing(rowsκ) == "equal_split_fallback"
19     else:
20         assert exists smoothing ∈ {null, "alpha=0.5"} and not(all == "equal_split_fallback")

21 # I-W1 recap: ensure no RNG datasets exist under {parameter_hash} for S5
22 assert only {ccy_country_weights_cache, sparse_flag} are produced by S5 in dictionary

23 PASS
```

This nails how S5’s determinism and semantics are *proven from the data itself*: no RNG anywhere, per-currency weights that **sum to one** under a schema guard, a **stable ISO ordering** that downstream relies on, and a **flag** that *only* encodes the equal-split fallback (not merely the use of smoothing).

---

# S5.6 — Failure modes (abort semantics)

## Goal

Define the exhaustive set of errors that can occur while constructing/persisting the **deterministic** currency→country caches in S5, together with the *evidence on disk* and the abort scope. Schemas and the data dictionary are the authorities for types, keys, constraints and partitions.

---

## Failure taxonomy (triggers → observables → action)

### A) Ingress coverage / FK failures

**F-S5/INGRESS/MISSING_ROWS**

* **Trigger.** Currency $\kappa$ required by the run’s universe (e.g., appears in candidate assembly) has **no rows** in `ccy_country_shares_2024Q4`. This leaves $\mathcal{D}(\kappa)$ undefined.
* **Observable.** Absence of any $(\kappa, i)$ in the ingress table; S5 cannot build weights for $\kappa$.
* **Action.** **Abort run (schema/coverage).** Currency-level gaps violate the documented dependency on the ingress split table.

**F-S5/INGRESS/ISO_FK**

* **Trigger.** Any member $i$ for $\kappa$ fails the **ISO-3166 FK** check (not in the canonical ISO table).
* **Observable.** `country_iso` not joinable to ISO canonical during S5.1/S5.2 prechecks.
* **Action.** **Abort run (FK breach).**

### B) Ingress value failures

**F-S5/INGRESS/COUNTS_INVALID**

* **Trigger.** Any `y_i` is **negative** or **non-integer**; ingress schema expectations for counts are violated.
* **Observable.** Type/range check fails when reading `ccy_country_shares_2024Q4`.
* **Action.** **Abort run (schema/ingress).**

### C) Construction / rule-application failures

**F-S5/CONSTRUCT/D≤0**

* **Trigger.** Computed membership size $D=|\mathcal{D}(\kappa)|\le 0$. (Implies previous missing-rows/ISO problems.)
* **Observable.** Empty set per currency during S5.2.
* **Action.** **Abort run (consistency).**

**F-S5/CONSTRUCT/NAN_INF**

* **Trigger.** Any intermediate or final weight is **NaN/Inf** (e.g., numerics mishandled when $Y=0$).
* **Observable.** Non-finite `weight` pre-persistence.
* **Action.** **Abort run (numeric policy).** (Schema requires `weight` to be a finite pct01.)

### D) Persistence / schema-contract failures

**F-S5/PERSIST/SUM_CONSTRAINT**

* **Trigger.** For some $\kappa$, $\left|\sum_i w^{(\kappa)}_i-1\right| > 10^{-6}$.
* **Observable.** Schema `group_sum_equals_one` constraint fails for `ccy_country_weights_cache`.
* **Action.** **Abort run (schema error).**

**F-S5/PERSIST/PK_DUP**

* **Trigger.** Duplicate PK $(\kappa,i)$ in `ccy_country_weights_cache` **or** duplicate $\kappa$ in `sparse_flag`.
* **Observable.** Primary-key uniqueness violation at write/validate time.
* **Action.** **Abort run (schema error).**

**F-S5/PERSIST/PARTITION_MISMATCH**

* **Trigger.** Output paths/partitions differ from the dictionary (must be **`{parameter_hash}`** for both caches).
* **Observable.** Files written outside the governed paths.
* **Action.** **Abort run (dictionary breach).**

**F-S5/PERSIST/ORDERING**

* **Trigger.** Rows for a currency not **sorted by `country_iso` (ASCII)**.
* **Observable.** Stored order fails the monotone ASCII check; jeopardises S6 alignment.
* **Action.** **Abort run (ordering contract).**

**F-S5/PERSIST/SPARSE_FLAG_SEMANTICS**

* **Trigger.** `is_sparse` not equal to $\mathbf{1}\{Y < T\}$ (equal-split fallback); or smoothing tags in the weights cache are inconsistent with the flag.
* **Observable.** Mismatch between `sparse_flag` and per-row `smoothing` tags.
* **Action.** **Abort run (semantic contract).**

 >  The three bullets you listed map directly to **F-S5/INGRESS/ISO_FK**, **F-S5/INGRESS/COUNTS_INVALID**, and **F-S5/PERSIST/SUM_CONSTRAINT**/**PK_DUP** above. The dictionary/schemas are the sources of truth for these checks.

---

## What CI/validation will *see* (per table)

* **`ccy_country_weights_cache`** must exist under
  `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/…`, keyed by `["currency","country_iso"]`, with **group_sum_equals_one** per currency and ISO FK on `country_iso`.
* **`sparse_flag`** must exist under
  `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/…`, keyed by `["currency"]`, with `is_sparse = (Y < T)` and non-negative integer `obs_count`, `threshold`.

---

## Minimal reference algorithm (code-agnostic; validator view)

```text
INPUT:
  A = ccy_country_weights_cache (partition {parameter_hash})
  B = sparse_flag               (partition {parameter_hash})
  Ingress = ccy_country_shares_2024Q4 (read-only), ISO canonical

OUTPUT:
  Pass/Fail with failure code(s) E/1A/S5/…

1  # Ingress checks
2  assert every (κ,i) in Ingress has country_iso ∈ ISO  → else FAIL F-S5/INGRESS/ISO_FK
3  assert every obs_count y_i is integer and y_i ≥ 0     → else FAIL F-S5/INGRESS/COUNTS_INVALID
4  assert required currencies appear in Ingress          → else FAIL F-S5/INGRESS/MISSING_ROWS

5  # Partition/layout checks
6  assert partition_keys(A) = {"parameter_hash"} and path matches dictionary
7  assert partition_keys(B) = {"parameter_hash"} and path matches dictionary
8  if not: FAIL F-S5/PERSIST/PARTITION_MISMATCH

9  # Per-currency table checks
10 for each currency κ in B:
11     rows ← A[κ] ordered as stored
12     # Ordering
13     assert country_iso(rows) is ASCII-sorted           → else FAIL F-S5/PERSIST/ORDERING
14     # Sum constraint
15     s ← Σ weight(rows); assert |1 - s| ≤ 1e-6 and all weights finite ∈ [0,1]
16     if not: FAIL F-S5/PERSIST/SUM_CONSTRAINT
17     # PK duplicates (also check at writer)
18     assert unique (κ,i) keys                           → else FAIL F-S5/PERSIST/PK_DUP
19     # Sparse-flag semantics
20     Ŷ ← Σ obs_count(rows); (is_sparse, Y, T) ← B[κ]
21     assert Ŷ = Y and is_sparse = (Y < T)
22     if is_sparse: assert all smoothing(rows) = "equal_split_fallback"
23     else: assert not all smoothing(rows) = "equal_split_fallback"
24     if any fail: FAIL F-S5/PERSIST/SPARSE_FLAG_SEMANTICS

25 PASS
```

This locks S5’s **abort semantics** to the concrete contracts set by the dictionary and schemas: **ingress integrity**, **proper numeric construction**, and **persistence that obeys keys/partitions/constraints**. Any breach is deterministically detectable and results in a clean, explainable failure.

---

# S5.7 — Inputs → outputs (state boundary)

## Purpose

Seal the contract from **reference ingress + fixed hyperparams** to the **parameter-scoped caches** that S6 will consume. No RNG is used anywhere in S5; outputs are pure functions of ingress counts and constants.

---

## Inputs (deterministic, read-only)

* **Intra-currency splits (with counts).**
  `ccy_country_shares_2024Q4` (long form, PK = `["currency","country_iso"]`, ISO FK, counts `obs_count=y_i≥0`; also carries a proportional `share` column). This reference defines, for each currency $\kappa$, the member set $\mathcal{D}(\kappa)$ and the observation counts $\{y_i\}$; $Y=\sum_i y_i$. Schema: `schemas.ingress.layer1.yaml#/ccy_country_shares` (with group-sum-equals-1 on `share` as an ingress property).

* **Fixed hyperparameters.** $\alpha = 0.5,\; T = 30$ from the subsegment assumptions (used as in S5.2/S5.3).

* **Lineage & authority.**
  `parameter_hash` (partitions caches), `manifest_fingerprint` (run-level lineage column), and the **ISO-3166 canonical** table for FK/ordering (`country_iso`). Paths and schema refs are pinned by the data dictionary.

*(S5 is merchant-agnostic; it prepares a global cache keyed by currency, gated by the fact that S4 produced some $K_m\ge1$ merchants in the run. Even if none, CI may still materialise the caches.)*

---

## Deterministic mapping (what S5 computes)

Per currency $\kappa$ with members $\mathcal{D}(\kappa)=\{i_1,\dots,i_D\}$:

1. Build candidate vectors from counts (S5.2):
   $\hat w_i = y_i / Y$ (if $Y > 0$); $\tilde w_i = (y_i+\alpha)/(Y+\alpha D)$.

2. Choose **smoothed vs raw** by **cell** sparsity:
   use $\tilde w$ iff $\min_i y_i < T$; else $\hat w$ (with $Y > 0$).

3. Apply **global** fallback if evidence is too small:
   if $Y < T$ (equivalently $\tilde Y < T+\alpha D$), force **equal split** $w^{(\kappa)}_i = 1/D$ and set `is_sparse=true`. Otherwise `is_sparse=false`.

4. **Renormalise** in binary64 to enforce $\sum_i w^{(\kappa)}_i = 1$ (≤ $10^{-12}$ construction tolerance; schema enforces $10^{-6}$ at read), and **order rows by ISO (ASCII)**.

This yields the **final** per-currency weight vector $w^{(\kappa)}$ and the boolean `is_sparse`.

---

## Outputs (authoritative, parameter-scoped caches)

* **`ccy_country_weights_cache/parameter_hash={parameter_hash}/…`**
  One row per $(\kappa,i)$:
  $(\texttt{manifest_fingerprint},\ \texttt{currency}=\kappa,\ \texttt{country_iso}=i,\ \texttt{weight}=w^{(\kappa)}_i,\ \texttt{obs_count}=y_i,\ \texttt{smoothing}\in\{\texttt{null},\texttt{"alpha=0.5"},\texttt{"equal_split_fallback"}\})$.
  Schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`; **group_sum_equals_one** per currency (tol $10^{-6}$); **partitioned solely by `{parameter_hash}`** (ordering within currency by ISO).

* **`sparse_flag/parameter_hash={parameter_hash}/…`**
  One row per $\kappa$:
  $(\texttt{manifest_fingerprint},\ \texttt{currency}=\kappa,\ \texttt{is_sparse}=\mathbf{1}\{Y < T\},\ \texttt{obs_count}=Y,\ \texttt{threshold}=T)$.
  Schema `schemas.1A.yaml#/prep/sparse_flag`; partitioned by `{parameter_hash}`. **Flag semantics:** true iff equal-split fallback fired (not merely because smoothing was used).

**Paths & authority:** Both paths and schema refs are fixed by the dataset dictionary; `manifest_fingerprint` is *stored* in every row but does **not** control partitioning (which is only `{parameter_hash}`).

---

## What S6 may assume from this boundary

* For the merchant’s currency $\kappa_m$, S6 can load the **ISO-ordered** vector
  $\{(\kappa_m,i,w_i^{(\kappa_m)}) : i\in\mathcal{D}(\kappa_m)\}$ with $\sum_i w_i=1$, then exclude the home ISO and renormalise before drawing **Gumbel keys** (exactly one uniform per candidate). `country_set` (in S6) becomes the sole authority for ordered foreigns.

---

## Minimal reference algorithm (code-agnostic; boundary view)

```text
INPUTS:
  - Ingress: ccy_country_shares_2024Q4 (κ,i,y_i; ISO FK)
  - Constants: α = 0.5, T = 30
  - Lineage: parameter_hash, manifest_fingerprint

OUTPUTS:
  - A: ccy_country_weights_cache/parameter_hash={parameter_hash}/… (schema #/prep/ccy_country_weights_cache)
  - B: sparse_flag/parameter_hash={parameter_hash}/…               (schema #/prep/sparse_flag)

ALGO:
1  For each currency κ:
2      D(κ) ← ordered ISO list of member countries from ingress
3      {y_i} ← obs_count per i; Y ← Σ_i y_i
4      if |D(κ)| = 1:
5          emit A row (κ,i1, weight=1, y_i1, smoothing=null)
6          emit B row (κ, is_sparse=false, Y, T)
7          continue
8      # Candidate vectors and decisions (S5.3)
9      hat_w defined iff Y > 0; tilde_w_i ← (y_i + α)/(Y + α·D)
10     if min_i y_i < T: w ← tilde_w, smoothing="alpha=0.5"
11     else:             w ← hat_w   , smoothing=null   (require Y > 0)
12     if Y < T:
13         w_i ← 1/D for all i; smoothing="equal_split_fallback"; is_sparse ← true
14     else:
15         is_sparse ← false
16     # Renormalise and order
17     s ← Σ_i w_i; if |1-s| > 1e-12 then w_i ← w_i/s
18     emit A rows for all i in ASCII ISO order:
19         (manifest_fingerprint, κ, i, weight=w_i, obs_count=y_i, smoothing)
20     emit B row: (manifest_fingerprint, κ, is_sparse, Y, T)
21 Validate both outputs per schemas/dictionary (PKs, FK, partitions, group_sum_equals_one).
```

That’s the boundary, unambiguous: **what goes in**, **what exactly comes out**, **how it’s partitioned and validated**, and **what S6 can rely on**, all tied back to your schemas and dictionary.
