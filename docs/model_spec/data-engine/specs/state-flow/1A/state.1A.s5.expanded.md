# S5.1 — Universe, symbols, authority

## 1) Placement, scope, purpose

* **Where we are.** S5 follows S5.0 (which deterministically fixes each merchant’s settlement currency $\kappa\_m$ and persists `merchant_currency`). **S5 is parameter-scoped and merchant-agnostic:** it runs once per build to construct deterministic currency→country weights that S6 later combines with each merchant’s context (including $K\_m$). S5 performs **no sampling**.
* **What this sub-state does.** S5.1 **does not persist** outputs. It ingests the authoritative reference tables, enforces schema/keys/order, and prepares a validated, **ASCII-ordered** per-currency map $\kappa \mapsto\big(\mathcal D(\kappa), {y\_i}, Y, D\big)$ for S5.2–S5.3. (Persistence happens in S5.4.)

> Note: `merchant_currency` (from S5.0) is the sole authority for $\kappa\_m$ per merchant. S5.1 prepares **global** per-currency splits used for **all** merchants that carry a given $\kappa$.

---

## 2) Authoritative inputs (read-only) and their schemas

* **Currency→country splits (with counts)**: `ccy_country_shares_2024Q4`, schema `schemas.ingress.layer1.yaml#/ccy_country_shares`. Rows `(currency=κ, country_iso=i, obs_count=y_i)` define $\mathcal D(\kappa)$ and $y\_i!\ge!0$ used downstream to construct weights.
* **Settlement shares (currency-level)**: `settlement_shares_2024Q4`, schema `#/settlement_shares`. Context for layer-wide currency presence only; **not** used for S5 weighting or scope decisions in S5.1.
* **ISO-3166 canonical**: FK authority **and** ordering authority for `country_iso` referenced by 1A schemas.
* **Smoothing policy (config)**: `ccy_smoothing_params` (e.g., `α_smooth`, thresholds), referenced by S5.2.
* **Per-merchant currency (from S5.0)**: `merchant_currency` (parameter-scoped, schema `#/prep/merchant_currency`), consumed later by S6; listed here to close the authority chain.

---

## 3) Authority over outputs (declared here for downstream)

S5 ultimately persists **two parameter-scoped caches** in S5.4. S5.1 doesn’t write them, but it pins their contracts so implementers validate toward the right targets:

* **`ccy_country_weights_cache`** — per-$(\kappa,i)$ weights, `schemas.1A.yaml#/prep/ccy_country_weights_cache`, **partitioned by `{parameter_hash, shares_digest}`**, with a **group\_sum\_equals\_one** constraint per currency (tolerance $10^{-6}$).
* **`sparse_flag`** — per-$\kappa$ sparsity indicator, `schemas.1A.yaml#/prep/sparse_flag`, **partitioned by `{parameter_hash, shares_digest}`**. (`is_sparse` is defined in S5.3; persisted in S5.4.)

`shares_digest` is the **SHA-256** of the concrete `ccy_country_shares_2024Q4` snapshot used for the build. **Consumers (S6) must only read rows whose `shares_digest` equals their manifest’s reference digest.**

---

## 4) Universe & symbols fixed by S5.1 (notation)

For an ISO-4217 currency $\kappa$:

* **Membership**: $\mathcal{D}(\kappa)={i\_1,\dots,i\_D}\subset\mathcal I$, where $\mathcal I$ is the ISO-3166-1 alpha-2 set. $D=|\mathcal{D}(\kappa)|$. Derived **solely** from `ccy_country_shares_2024Q4`.
* **Counts**: $y\_i \in \mathbb{Z}*{\ge 0}$ (ingress count per destination). $Y=\sum*{i\in \mathcal D(\kappa)} y\_i$. These feed S5.2–S5.3 (construction of $\hat w,\tilde w$ and regime decisions).
* **Ordering**: within each $\kappa$, entries are **ASCII-sorted** by `country_iso` (uppercase A–Z byte order). This canonical order is fixed **here** and carried forward to persistence to stabilise downstream selection.

---

## 5) Contracts S5.1 must enforce (inputs→context)

**No RNG.** S5 emits no RNG events and consumes no Philox counters; any RNG usage inside S5 is a protocol breach.

**Schema & FK discipline.**

* Every $(\kappa,i)$ from `ccy_country_shares_2024Q4` must join ISO canonical by `country_iso`. **FK(country\_iso)** is authoritative.
* `obs_count=y_i` must be integer with $y\_i\ge 0$; duplicates of $(\kappa,i)$ are not allowed.

**Partitioning discipline (for later persistence).**

* The two S5 caches are **parameter-scoped** and **must** be written under the dictionary’s paths with partition set = `{parameter_hash, shares_digest}` (no `seed`, no `run_id`). This is declared here to prevent drift when we reach S5.4.

**Ordering contract.**

* For each $\kappa$, S5 maintains (and later persists) rows in the **canonical ASCII order** of `country_iso`. This is a **logical** ordering guarantee; writers **should** physically sort, but consumers may re-establish order by sorting on `country_iso` if the storage engine does not guarantee row order.

---

## 6) Language-agnostic reference algorithm (“prepare S5 context”)

This procedure is implementation-neutral and deterministic.

```text
INPUTS:
  - A := ccy_country_shares_2024Q4   # (κ, country_iso=i, obs_count=y_i)
  - B := settlement_shares_2024Q4    # currency-level context (read-only)
  - ISO := iso3166_canonical         # FK + ordering authority
  - Params := ccy_smoothing_params   # α_smooth, thresholds (used in S5.2/5.3)
  - (No RNG inputs)

OUTPUT (in-memory only; nothing persisted in S5.1):
  - Map M where for each currency κ:
      M[κ] = {
        D: integer ≥ 1,
        members: [i_1, ..., i_D]          # ASCII-sorted by country_iso
        counts:  [y_{i_1}, ..., y_{i_D}]  # integers, y_i ≥ 0
        Y: Σ y_i                           # 64-bit int preferred; binary64 ok for downstream use
      }
  - shares_digest := SHA256(A)            # retained for S5.4 partitioning

ALGORITHM:

1  Load ISO; build set I := {valid country_iso} (primary-key domain).

2  Load A with schema checks:
   2.1 Assert: currency is ISO-4217 string; country_iso is STRING; obs_count is INTEGER.
   2.2 Assert: obs_count ≥ 0 for all rows → else FAIL E/1A/S5/INGRESS/COUNTS_INVALID.
   2.3 Assert: every country_iso ∈ I → else FAIL E/1A/S5/INGRESS/ISO_FK.

3  Group A by currency κ:
   3.1 Assert: no duplicate (κ,i) within a group → else FAIL E/1A/S5/INGRESS/DUP_KEY.
   3.2 If A has zero rows overall → FAIL E/1A/S5/INGRESS/NO_DATA.

4  For each κ:
   4.1 Sort members by ASCII `country_iso` → [i_1, ..., i_D].
   4.2 Build counts vector in that order → [y_{i_1}, ..., y_{i_D}].
   4.3 Compute Y := Σ y_{i_j} (int64 preferred).
   4.4 Record M[κ] := { D, members, counts, Y }.

5  Emit M and shares_digest to S5.2–S5.4. Do not persist any rows in S5.1.

FAILURE SEMANTICS (abort build on any):
  - E/1A/S5/INGRESS/ISO_FK            # country_iso not in ISO canonical
  - E/1A/S5/INGRESS/COUNTS_INVALID    # obs_count non-integer or < 0
  - E/1A/S5/INGRESS/DUP_KEY           # duplicate (κ,i)
  - E/1A/S5/INGRESS/NO_DATA           # A has zero rows
```

---

## 7) What **will** be persisted later (declared now, not executed here)

S5.4 will materialise (parameter-scoped, partition `{parameter_hash, shares_digest}`):

* `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
  PK `[currency,country_iso]`; **group\_sum\_equals\_one** per currency (tolerance $10^{-6}$); ISO FK enforced; `weight` persisted as binary64; `smoothing` enum per S5.3.
* `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
  PK `[currency]`; `is_sparse` semantics from S5.3. (Optionally include `dest_sparse` for diagnostics.)

---

## 8) Determinism & replay

* **I-S5-B (no randomness):** S5 uses no RNG; any RNG event in S5 is a protocol breach.
* **I-S5-C (bit-stability under fixed lineage):** For fixed inputs and `parameter_hash`, the bytes of S5.4 caches are reproducible across replays. `shares_digest` binds caches to the exact reference snapshot.

---

## 9) Cross-state authority chain (for consumers)

* **Per-merchant currency $\kappa\_m$**: read from `merchant_currency` (S5.0), never recomputed in S5/S6.
* **Per-currency weights $w^{(\kappa)}$** + **sparse flag**: read from the S5 caches (S5.4). **S6 must verify `shares_digest`**, then remove the home ISO, renormalise foreigns, and proceed to Gumbel selection of $K\_m$ foreigns. (Inter-country order is persisted later in `country_set`; `outlet_catalogue` never encodes cross-country order.)

---

### One-line summary

**S5.1** deterministically fixes the per-currency **membership+counts context** $\kappa \mapsto (\mathcal D(\kappa),{y\_i},Y)$ with strict **FK**, **uniqueness**, and **ASCII ordering**; it persists nothing, uses no RNG, and pins the future caches’ **schema and partitioning** (including `shares_digest`) so S5.4 writes are unambiguous and S6 consumption is safely gated.

---

# S5.2 — Symbols & fixed hyperparameters

## 1) Purpose & authority

S5.2 defines the **per-currency objects** and **constants** that S5.3 uses to decide the final deterministic weights and sparsity flags. It is read-only over ingress and **persists nothing**. Values are fixed by the 1A assumptions for this vintage.

**Upstream inputs (read-only):**

* `ccy_country_shares_2024Q4` → $(\kappa,i,y\_i)$, membership $\mathcal D(\kappa)$, counts. Schema: `schemas.ingress.layer1.yaml#/ccy_country_shares`.

  * **Semantics:** `obs_count = y_i` is the number of **settlement transactions** observed for `(currency=κ, country_iso=i)` in the 2024Q4 window; integer ≥ 0; non-nullable.
* ISO-3166 canonical (FK + ordering authority). (Applied in S5.1; re-enforced at S5.4.)
* Smoothing policy config `ccy_smoothing_params` (contains `α_smooth` and thresholds; values pinned below).

> S5.2 has **no RNG**, makes **no** persistence decisions, and performs **no** weighting choice—that happens in S5.3.

---

## 2) Primary symbols (per currency $\kappa$)

For an ISO-4217 currency $\kappa$:

**Member set and size**

$$
\boxed{\ \mathcal D(\kappa)=\{i_1,\dots,i_D\}\subset\mathcal I,\quad D=|\mathcal D(\kappa)|\ }\quad
\text{(from `ccy_country_shares_2024Q4`, PK $(\kappa,i)$).}
$$

**Observation counts and total**

$$
\boxed{\ y_i\in\mathbb Z_{\ge0}\ \text{for } i\in\mathcal D(\kappa),\qquad
Y:=\sum_{i\in \mathcal D(\kappa)} y_i\ }.
$$

**Ordering contract.** Within each $\kappa$, members are kept in **ASCII byte order** by `country_iso` (uppercase A–Z). This order is **sticky** across S5 and at persistence.

---

## 3) Fixed hyperparameters (governed; not tuned in S5)

* **Additive smoothing constant (symmetric, Laplace-type):**

  $$
  \boxed{\ \alpha_{\text{smooth}} := 0.5\ }.
  $$
* **Global sparsity threshold (observations):**

  $$
  \boxed{\ T := 30\ }.
  $$

These constants *inform* S5.3’s decision surface (raw vs smoothed vs equal-split) but are **not** modified in S5.2.

---

## 4) Derived quantities (prepared for S5.3)

**Cell minimum & indicator**

$$
y_{\min}=\min_{i\in \mathcal D(\kappa)} y_i,\qquad
\mathbf 1_{\text{cell-sparse}}:=\mathbf 1\{y_{\min} < T\}.
$$

*(This flag is an aide for S5.3; S5.2 does not branch on it.)*

**Smoothed counts (additive) and total**

$$
\boxed{\ \tilde y_i:=y_i+\alpha_{\text{smooth}},\quad
\tilde Y:=\sum_i \tilde y_i = Y + \alpha_{\text{smooth}} D\ }.
$$

For any $D\ge 1$ and $\alpha\_{\text{smooth}}>0$: $\tilde y\_i>0,\ \tilde Y>0$.

**Candidate weight vectors**

$$
\hat w_i:=\frac{y_i}{Y}\quad(\text{only if } Y>0),\qquad
\tilde w_i:=\frac{y_i+\alpha_{\text{smooth}}}{\,Y+\alpha_{\text{smooth}} D\,}\quad(\text{always defined}).
$$

**Convex-blend identity (for $D\ge2$):**

$$
\boxed{\ \tilde w_i
=\frac{Y}{Y+\alpha_{\text{smooth}}D}\,\hat w_i
+\frac{\alpha_{\text{smooth}}D}{Y+\alpha_{\text{smooth}}D}\cdot\frac{1}{D}\ } \quad (Y>0).
$$

**Global fallback equivalence (for reference):**

$$
\boxed{\ \tilde Y < T+\alpha_{\text{smooth}} D\ \Longleftrightarrow\ Y < T\ }.
$$

S5.3 will use the simpler raw-count test `Y < T` to trigger **equal-split** with `is_sparse=true`.

---

## 5) Domains, bounds, and edge cases

* **Domains.** $\alpha\_{\text{smooth}}>0$, $T\in\mathbb Z\_{\ge0}$, $y\_i\in\mathbb Z\_{\ge0}$, $D\in\mathbb Z\_{\ge1}$, $Y\in\mathbb Z\_{\ge0}$.
* **Positivity & normalisation.** If $Y>0$ then $\sum\_i \hat w\_i=1$ (modulo FP error). Always $\sum\_i \tilde w\_i=1$.
* **Continuity/limits ($D\ge2$).** As $Y!\to!\infty$, $\tilde w!\to!\hat w$; as $Y!\to!0$, $\tilde w!\to$ equal-split; S5.3 then forces equal-split via `Y < T`.
* **$D=1$ (degenerate).** Output weight is exactly $1$, regardless of $y\_{i\_1}$; smoothing and fallback are irrelevant.
* **Well-posed at $Y=0$.** $\hat w$ undefined (unused); $\tilde w$ well-defined and strictly positive; S5.3 will take equal-split.

---

## 6) Numeric discipline (binary64; exact checks later)

* **Types.** Treat $y\_i, Y, D, T$ as integers; convert to **binary64** only for division/sums when forming $\hat w,\tilde w$.
* **Renormalisation guard (for S5.3).** Although $\hat w,\tilde w$ are algebraically normalised, S5.3 re-scales by $s=\sum\_i w\_i$ if $|1-s|>10^{-12}$ (Neumaier-summed), and S5.4 enforces $|1-\sum\_i w\_i|\le 10^{-6}$ at schema.
* **Ordering stability.** Vectors remain in **ASCII** order to avoid non-determinism.

---

## 7) Language-agnostic reference algorithm (S5.2 “symbol table”)

**Input** (from S5.1, already validated & ASCII-ordered):

* For each $\kappa$: `members[1..D] = [i_1,…,i_D]`, `counts[1..D] = [y_{i_1},…,y_{i_D}]`, `Y = Σ y_i`.
* Constants: `α_smooth = 0.5`, `T = 30`.

**Output** (in-memory only; handed to S5.3):

```
ctx[κ] = {
  D: int ≥ 1,
  members[1..D]: ISO codes (ASCII order),
  counts[1..D]: int64 ≥ 0,
  Y: int64 ≥ 0,
  y_min: int64 ≥ 0,
  # Derived (binary64):
  tilde_counts[1..D] = y_i + α_smooth,
  tilde_Y = Y + α_smooth · D,
  hat_w[1..D]   = (Y > 0 ? y_i / Y : NaN),
  tilde_w[1..D] = (y_i + α_smooth) / (Y + α_smooth · D),
  cell_sparse = (y_min < T),
  global_sparse = (Y < T)  # ⇔ (tilde_Y < T + α_smooth·D)
}
```

**Algorithm (per κ):**

1. `D ← len(members)`; assert `D ≥ 1`.
2. `Y ← Σ counts`; `y_min ← min(counts)`.
3. `tilde_counts[i] ← counts[i] + α_smooth` for all i.
4. `tilde_Y ← Y + α_smooth · D`.
5. If `Y > 0`: `hat_w[i] ← counts[i]/Y`; else `hat_w[i] ← NaN` (unused).
6. `tilde_w[i] ← tilde_counts[i] / tilde_Y`.
7. `cell_sparse ← (y_min < T)`; `global_sparse ← (Y < T)`.
8. Emit `ctx[κ]` to S5.3 (no writes).

---

## 8) Minimal failure surface at S5.2 (deterministic)

S5.2 can abort the build **only** on parameter misconfiguration (all ingress/FK checks are S5.1’s job):

* **Bad constants (config error):** if `α_smooth ≤ 0` or `T < 0` → `E/1A/S5/PARAMS/OUT_OF_DOMAIN`.

---

## 9) What S5.2 does **not** do

* No persistence; no RNG usage; no selection between $\hat w,\tilde w,$ or equal-split (all in S5.3).

---

### One-line takeaway

S5.2 assembles the **objects** $(\mathcal D(\kappa),y\_i,Y)$, **deriveds** $(\tilde y\_i,\tilde Y,\hat w,\tilde w)$, and **constants** $(\alpha\_{\text{smooth}}{=}0.5,\ T{=}30)$—all in ASCII order and binary64-ready—so S5.3 can deterministically choose weights and flags, and S5.4 can persist them.

---

# S5.3 — Deterministic expansion

## 1) Purpose & placement

Given the S5.2 context for each currency $\kappa$ — ordered members $\mathcal D(\kappa)={i\_1,\dots,i\_D}$, counts $y\_i\ge0$, total $Y=\sum\_i y\_i$, and constants $\alpha\_{\text{smooth}}{=}0.5,;T{=}30$ — produce a **final**, ISO-ordered weight vector $w^{(\kappa)}$ that sums to 1, with **no RNG**. S5.4 will persist:

* `ccy_country_weights_cache` (per $(\kappa,i)$ row with `weight`, `obs_count`, and **smoothing metadata**), and
* `sparse_flag` (per $\kappa$ row with `is_sparse = (Y < T)`).

Both caches are **parameter-scoped** and will be partitioned by `{parameter_hash, shares_digest}`.

---

## 2) Inputs (from S5.2) & constants (governed)

Per currency $\kappa$ (ASCII-sorted members):

* $D=|\mathcal D(\kappa)|\in\mathbb Z\_{\ge1}$.
* $y\_i\in\mathbb Z\_{\ge0}$ for $i\in\mathcal D(\kappa)$; $Y=\sum\_i y\_i\in\mathbb Z\_{\ge0}$.
* Smoothed counts: $\tilde y\_i=y\_i+\alpha\_{\text{smooth}}$; $\tilde Y=Y+\alpha\_{\text{smooth}} D$.
* Candidate vectors:
  $\displaystyle \hat w\_i = \frac{y\_i}{Y}$ (defined iff $Y>0$),
  $\displaystyle \tilde w\_i = \frac{y\_i+\alpha\_{\text{smooth}}}{Y+\alpha\_{\text{smooth}} D}$ (always defined).

**Constants (this vintage):** $\alpha\_{\text{smooth}}=0.5,; T=30$.

**Ordering contract:** $(i\_1,\dots,i\_D)$ is **fixed in ASCII ISO order** and must be preserved in all S5.3 outputs.

---

## 3) Decision surface (complete and unambiguous)

### Case A — Single-country currency ($D=1$)

Deterministic, degenerate outcome:

$$
w^{(\kappa)}_{i_1}\equiv 1,\qquad
\texttt{smoothing\_kind}=\texttt{null},\qquad
\texttt{smoothing\_alpha\_value}=\texttt{null},\qquad
\texttt{is\_sparse}=\texttt{false}.
$$

Counts $y\_{i\_1}$ may be 0; no smoothing or fallback applies.

### Case B — Multi-country currency ($D\ge2$)

Define:

* **Cell-sparse indicator:** $\mathbf 1\_{\text{cell}}=\mathbf 1{\min\_i y\_i < T}$.
* **Global-sparse indicator:** $\mathbf 1\_{\text{glob}}=\mathbf 1{Y < T}$.

Priority and outcomes:

1. **Global fallback (dominates):** if $\mathbf 1\_{\text{glob}}=1$

   $$
   w^{(\kappa)}_i \leftarrow \frac{1}{D}\ \forall i;\quad
   \texttt{smoothing\_kind}=\texttt{"equal\_split\_fallback"};\quad
   \texttt{smoothing\_alpha\_value}=\texttt{null};\quad
   \texttt{is\_sparse}=\texttt{true}.
   $$

2. **Otherwise, cell-driven choice:**

   * If $\mathbf 1\_{\text{cell}}=1$: $w^{(\kappa)}!\leftarrow!\tilde w$;
     `smoothing_kind="alpha"`, `smoothing_alpha_value=0.5`; `is_sparse=false`.
   * Else: $w^{(\kappa)}!\leftarrow!\hat w$;
     `smoothing_kind=null`, `smoothing_alpha_value=null`; `is_sparse=false`.

**Semantics of `sparse_flag`:** it reflects **only** the global fallback i.e., `is_sparse = (Y < T)`. Using $\tilde w$ alone does **not** set the flag.

---

## 4) Math properties (guarantees)

* **Convex decomposition (for $D\ge2$):**

  $$
  \tilde w_i = \underbrace{\frac{Y}{Y+\alpha_{\text{smooth}} D}}_{\text{data weight}}\hat w_i
             + \underbrace{\frac{\alpha_{\text{smooth}} D}{Y+\alpha_{\text{smooth}} D}}_{\text{prior weight}}\!\cdot\frac{1}{D}\quad (Y>0).
  $$

  As $Y!\downarrow!0$, $\tilde w!\to$ equal-split; as $Y!\uparrow!\infty$, $\tilde w!\to!\hat w$.
* **Positivity & normalisation.** All branches yield $w^{(\kappa)}\_i\in(0,1]$ and $\sum\_i w^{(\kappa)}\_i=1$ analytically; we still renormalise numerically.
* **Edge-case safety.**

  * $Y=0, D\ge2$ ⇒ global fallback triggers (equal split); `is_sparse=true`.
  * $D=1$ ⇒ $w=1$ regardless of $y\_{i\_1}$.
  * Mixed small/large cells with $Y\ge T$ ⇒ smoothed $\tilde w$; `is_sparse=false`.

---

## 5) Language-agnostic reference algorithm (normative)

```text
INPUT (per currency κ, ISO-ordered from S5.2):
  members[1..D] = [i_1,...,i_D]           # ASCII order
  counts[1..D]  = [y_{i_1},...,y_{i_D}]   # int64, y_i ≥ 0
  Y = Σ_i y_i                              # int64
  constants: α_smooth = 0.5, T = 30

OUTPUT (in-memory to S5.4 writers):
  rows_weights[1..D]: for each j:
    {
      currency=κ,
      country_iso=i_j,
      weight=w_j,                # binary64
      obs_count=y_{i_j},         # int64 (as in ingress)
      smoothing_kind ∈ {null,"alpha","equal_split_fallback"},
      smoothing_alpha_value: binary64 or null
    }
  row_sparse:
    { currency=κ, is_sparse=(Y<T), obs_count=Y, threshold=T }

ALGORITHM:

0  assert D ≥ 1

A) if D == 1:
     w ← [1.0]
     smoothing_kind ← [null]
     smoothing_alpha_value ← [null]
     is_sparse ← false
     EMIT rows_weights, row_sparse
     STOP

B) # D ≥ 2
   # Candidate vectors (binary64)
   if Y > 0:
       hat_w[j] ← counts[j] / Y      for j=1..D
   else:
       hat_w[j] ← NaN                for j=1..D  # unused if fallback fires
   tilde_w[j] ← (counts[j] + α_smooth) / (Y + α_smooth·D)

   # Indicators
   y_min ← min(counts)
   cell_sparse   ← (y_min < T)
   global_sparse ← (Y < T)

   # Decision (priority: global > local)
   if global_sparse:
       w[j] ← 1.0 / D                for j=1..D
       smoothing_kind[j] ← "equal_split_fallback"
       smoothing_alpha_value[j] ← null
       is_sparse ← true
   else if cell_sparse:
       w[j] ← tilde_w[j]             for j=1..D
       smoothing_kind[j] ← "alpha"
       smoothing_alpha_value[j] ← 0.5
       is_sparse ← false
   else:
       assert Y > 0
       w[j] ← hat_w[j]
       smoothing_kind[j] ← null
       smoothing_alpha_value[j] ← null
       is_sparse ← false

   # Renormalise to exact 1 (construction tolerance 1e-12)
   s ← Σ_j w[j]
   if |1 - s| > 1e-12:
       w[j] ← w[j] / s  for j=1..D

   # Emit (preserving input ISO order)
   rows_weights ← [{κ, i_j, w[j], y_{i_j}, smoothing_kind[j], smoothing_alpha_value[j]} for j=1..D]
   row_sparse   ← {κ, is_sparse, obs_count=Y, threshold=T}
   EMIT rows_weights, row_sparse
```

**Determinism:** No RNG; identical inputs and `parameter_hash` produce byte-identical rows when S5.4 writes the caches (with the same `shares_digest`).

---

## 6) Tag/flag coherence rules (must hold downstream)

* **Weights cache metadata (per $(\kappa,i)$):**
  `smoothing_kind ∈ { null, "alpha", "equal_split_fallback" }`
  `smoothing_alpha_value ∈ { binary64, null }`
  Rules:

  * If `smoothing_kind = "alpha"`, then `smoothing_alpha_value = 0.5`.
  * If `smoothing_kind = "equal_split_fallback"` or `null`, then `smoothing_alpha_value = null`.
* **Sparse flag dataset (per $\kappa$):**
  `is_sparse ⇔ (Y < T)`.
  Consistency:

  * If `is_sparse = true`, **all** rows for that $\kappa$ in the weights cache **must** have `smoothing_kind = "equal_split_fallback"`.
  * If `is_sparse = false`, **no** row may have `smoothing_kind = "equal_split_fallback"`.

---

## 7) Numerics & tolerances (binary64 discipline)

* **Renormalisation:** rescale if $|1-\sum\_i w\_i| > 10^{-12}$ (Neumaier-summed); S5.4 enforces $|1-\sum\_i w\_i|\le 10^{-6}$ at schema.
* **Range & finiteness:** emit only finite $w\_i\in [0,1]$.
* **Ordering:** preserve **ASCII** ISO order in all outputs.

---

## 8) Edge-case table (explicit outcomes)

| Situation                             | Decision     | smoothing\_kind        | smoothing\_alpha\_value | `is_sparse` |
|---------------------------------------| ------------ | ---------------------- | ----------------------- | ----------- |
| $D=1$, any $Y$                    | $w=[1]$   | `null`                 | `null`                  | `false`     |
| $D\ge2,;Y=0$                        | equal split  | `equal_split_fallback` | `null`                  | `true`      |
| $D\ge2,;Y < T$                      | equal split  | `equal_split_fallback` | `null`                  | `true`      |
| $D\ge2,;Y\ge T,;\min\_i y\_i < T$   | $\tilde w$ | `alpha`                | `0.5`                   | `false`     |
| $D\ge2,;Y\ge T,;\min\_i y\_i \ge T$ | $\hat w$   | `null`                 | `null`                  | `false`     |

---

## 9) What S5.4 will persist (declared targets)

S5.4 writes two **parameter-scoped** caches with dictionary-pinned `schema_ref`/paths and partitioning:

* `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
  Schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`; PK `[currency,country_iso]`; ISO FK; `weight` **binary64**; metadata fields `obs_count`, `smoothing_kind`, `smoothing_alpha_value`; **group\_sum\_equals\_one** per currency (tolerance $10^{-6}$).

* `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
  Schema `schemas.1A.yaml#/prep/sparse_flag`; PK `[currency]`; fields `is_sparse`, `obs_count=Y`, `threshold=T`.

**Consumer contract (S6):** must verify `shares_digest` match before reading; then **exclude the home ISO and renormalise** over the foreign remainder.

---

## 10) Complexity

Per currency, O($D$) time and O($D$) memory; total linear in the number of $(\kappa,i)$ pairs. No network or RNG costs.

---

**Summary:** S5.3 deterministically selects between raw, smoothed, and equal-split weights using a single, prioritized decision surface; emits robust, schema-stable **smoothing metadata**; preserves **ASCII order** and strict **sum-to-1** numerics; and prepares rows for S5.4 to persist under `{parameter_hash, shares_digest}`.

---

# S5.4 — Persistence (authoritative spec)

## 1) Purpose & placement

S5.3 produced, per currency $\kappa$, the **final** ISO-ordered weights $w^{(\kappa)}$, **smoothing metadata** per destination, and the per-$\kappa$ **is\_sparse** decision. S5.4 **materialises** these into two **parameter-scoped** caches. S5 (incl. S5.4) uses **no RNG**.

---

## 2) Datasets to write (and only these)

### A) `ccy_country_weights_cache` — per $(\kappa,i)$ weights

* **Dictionary path template:**
  `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/shares_digest={shares_digest}/`
* **Partitioning keys:** `["parameter_hash", "shares_digest"]` (no `seed`, no `run_id`).
* **Schema:** `schemas.1A.yaml#/prep/ccy_country_weights_cache`.
* **Role:** Deterministic currency→country weights; **group\_sum\_equals\_one** per currency (tol $10^{-6}$).

**Row contract (one row per currency–country):**

```
manifest_fingerprint     : hex64 (^[a-f0-9]{64}$)
shares_digest            : hex64  # SHA-256 of the exact ccy_country_shares_2024Q4 snapshot
currency                 : ISO-4217 string (PK part 1)
country_iso              : ISO-3166-1 alpha-2 string (PK part 2; FK → ISO canonical)
weight                   : binary64 in [0,1] (finite)          # final w_i
obs_count                : int64 ≥ 0                           # ingress y_i
smoothing_kind           : enum {null, "alpha", "equal_split_fallback"}
smoothing_alpha_value    : binary64 or null                    # 0.5 iff smoothing_kind=="alpha"
```

**Primary key:** `["currency","country_iso"]`.
**Canonical order within a currency:** **ASCII sort by `country_iso`** (uppercase A–Z byte order).

---

### B) `sparse_flag` — per-$\kappa$ sparsity decision

* **Dictionary path template:**
  `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/shares_digest={shares_digest}/`
* **Partitioning keys:** `["parameter_hash", "shares_digest"]`.
* **Schema:** `schemas.1A.yaml#/prep/sparse_flag`.
* **Semantics:** `is_sparse = (Y < T)`; only the **global equal-split fallback** sets this true.

**Row contract (one row per currency):**

```
manifest_fingerprint  : hex64
shares_digest         : hex64
currency              : ISO-4217 string (PK)
is_sparse             : boolean       # true ⇔ equal_split_fallback taken
obs_count             : int64 ≥ 0     # Y
threshold             : int64 ≥ 0     # T (e.g., 30)
```

**Primary key:** `["currency"]`.

**Lineage note.** `shares_digest` binds caches to the exact reference snapshot; `manifest_fingerprint` records run lineage. `parameter_hash` + `shares_digest` define versioned partitions.

---

## 3) Preconditions from S5.3 (recap)

For each $\kappa$: members $(i\_1,\dots,i\_D)$ in **ASCII** order; final $w^{(\kappa)}$ chosen by the S5.3 surface (global fallback if $Y < T$, else smoothed if $\min\_i y\_i < T$, else raw); renormalised to $\sum\_i w=1$ within $10^{-12}$ construction tolerance; metadata coherent; `is_sparse=(Y<T)`.

---

## 4) Writer invariants & constraints (hard requirements)

* **Partition authority.** Paths **must** use exactly the keys `{"parameter_hash","shares_digest"}` as shown.
* **Group-sum constraint.** For each $\kappa$, stored weights must satisfy
  $\big|\sum\_i w^{(\kappa)}\_i - 1\big| \le 10^{-6}$ (schema-checked). Writer **should** renormalise if $|1-\sum\_i w|>10^{-12}$ to keep headroom.
* **Canonical ordering.** Within each $\kappa$, rows are written in **ASCII** order by `country_iso`. This is a **logical** guarantee; writers **should** physically sort, and readers **may** re-sort by `country_iso` to re-establish the canonical order if the engine does not preserve row order.
* **Keys & FKs.** Enforce PK uniqueness and FK to ISO canonical on `country_iso`.
* **No RNG.** S5 tables carry **no** RNG envelopes; presence is a protocol failure.
* **Metadata coherence.** If `is_sparse=true`, **all** A-rows for that $\kappa$ must have `smoothing_kind="equal_split_fallback"`; if `is_sparse=false`, **none** may.

---

## 5) Language-agnostic reference algorithm (normative writer)

```text
ALGORITHM  S5_Write_CurrencyCaches

INPUTS:
  For each currency κ (from S5.3):
    members[1..D]            = [i_1,...,i_D]             # ASCII ISO order
    weights[1..D]            = [w_1,...,w_D]             # binary64, finite
    counts[1..D]             = [y_1,...,y_D]             # int64 ≥ 0
    Y                        = Σ_j y_j                    # int64 ≥ 0
    smoothing_kind[1..D]     ∈ {null,"alpha","equal_split_fallback"}  # homogeneous per κ
    smoothing_alpha_value[1..D] ∈ {0.5, null}            # 0.5 iff kind=="alpha"
    is_sparse                = (Y < T)
  Constants:  α_smooth = 0.5,  T = 30
  Lineage:    manifest_fingerprint (hex64), parameter_hash
  Snapshot:   shares_digest = SHA256(ccy_country_shares_2024Q4)
  Authorities: dataset dictionary/schema refs, ISO FK table

TARGET PATHS (must match dictionary exactly):
  A_path := data/layer1/1A/ccy_country_weights_cache/
            parameter_hash={parameter_hash}/shares_digest={shares_digest}/
  B_path := data/layer1/1A/sparse_flag/
            parameter_hash={parameter_hash}/shares_digest={shares_digest}/

PRE-OPEN VALIDATION:
  0. Assert partition key set == {"parameter_hash","shares_digest"} for both targets.
  1. Prepare Parquet writers (e.g., ZSTD-3). Compression does not change semantics.

MAIN WRITE (streaming by κ):
  2. For each κ (any deterministic outer order):
     2.1 ORDER & PK:
         assert members are ASCII-ordered and unique → else FAIL E/1A/S5/PERSIST/ORDER_OR_PK
     2.2 SUM GUARD (fixed-order, deterministic):
         s ← Σ_j weights[j] using Neumaier over input order
         if |1 - s| > 1e-12:
             weights[j] ← weights[j] / s  for all j
         s' ← Σ_j weights[j] (Neumaier); assert |1 - s'| ≤ 1e-6
            → else FAIL E/1A/S5/PERSIST/SUM_CONSTRAINT
     2.3 TAG/FLAG COHERENCE:
         if is_sparse:
             assert all smoothing_kind[j] == "equal_split_fallback"
         else:
             assert none smoothing_kind[j] == "equal_split_fallback"
         if violated → FAIL E/1A/S5/PERSIST/SPARSE_FLAG_SEMANTICS
     2.4 EMIT WEIGHTS ROWS (preserve order):
         for j in 1..D:
           write A_row {
             manifest_fingerprint, shares_digest,
             currency=κ, country_iso=members[j],
             weight=weights[j], obs_count=counts[j],
             smoothing_kind=smoothing_kind[j],
             smoothing_alpha_value=smoothing_alpha_value[j]
           }
     2.5 EMIT SPARSE FLAG ROW:
         write B_row {
           manifest_fingerprint, shares_digest,
           currency=κ, is_sparse=is_sparse,
           obs_count=Y, threshold=T
         }

POST-WRITE VALIDATION (schema/dictionary gates):
  3. Validate A:
     - PK uniqueness on (currency,country_iso)
     - FK(country_iso) to ISO canonical
     - group_sum_equals_one per currency (≤1e-6)
     - weight finite ∈ [0,1]; obs_count int64 ≥ 0
     - smoothing_kind ∈ {null,"alpha","equal_split_fallback"}
       and smoothing_alpha_value = 0.5 iff kind=="alpha" else null
     - manifest_fingerprint, shares_digest match hex64 regex
  4. Validate B:
     - PK uniqueness on (currency)
     - is_sparse boolean; obs_count, threshold int64 ≥ 0
  5. Validate partitions/paths match dictionary for both A and B
  6. On any failure → ABORT with corresponding E/1A/S5/PERSIST/*

COMPLEXITY:
  Time O(#(κ,i)) and streaming memory. The only arithmetic is the fixed-order sum/renorm.
```

**Deterministic sum rule.** Any implementation (CPU/GPU/parallel) is allowed **iff** it reproduces the **fixed-order Neumaier sum over ASCII-sorted entries**, bit-for-bit in binary64, before the $10^{-12}$ renormalisation step. Parallel code **must** enforce the same per-currency order and a deterministic merge.

---

## 6) Failure taxonomy (abort semantics; exhaustive)

* **E/1A/S5/PERSIST/SUM\_CONSTRAINT** — a currency violates the $10^{-6}$ group sum gate.
* **E/1A/S5/PERSIST/ORDER\_OR\_PK** — non-ASCII order within a currency **or** duplicate PK.
* **E/1A/S5/PERSIST/SPARSE\_FLAG\_SEMANTICS** — `is_sparse ≠ (Y<T)` **or** inconsistent `"equal_split_fallback"` tagging.
* **E/1A/S5/PERSIST/PARTITION\_MISMATCH** — path/partitions differ from `{parameter_hash, shares_digest}`.
* **E/1A/S5/PERSIST/FK\_OR\_TYPES** — FK(country\_iso) failure or bad types/ranges (`obs_count`, `weight`, metadata).

(These codes align with S5.1–S5.3; CI will re-read and re-assert.)

---

## 7) Storage & lineage details

* **Format:** Parquet; **compression:** e.g., ZSTD-3 (value-transparent).
* **Versioning:** strictly by `parameter_hash` **and** `shares_digest`.
* **Lineage columns:** `manifest_fingerprint`, `shares_digest` persisted in both tables.

---

## 8) Consumer (S6) contract

* Must verify **`shares_digest`** equals its manifest’s reference snapshot before reading.
* May re-sort by `country_iso` (ASCII) to re-establish canonical order if needed.
* May assume: per-currency weights in ISO order, $\sum w=1$ within $10^{-6}$, consistent smoothing metadata, single `sparse_flag` row with `is_sparse=(Y<T)`.
* Must then **drop the home ISO** and **renormalise** over the foreign remainder before Gumbel selection.

---

## 9) Why this is complete & correct

This spec ties dictionary paths, partitions, and schema refs to a single normative writer; binds caches to the **exact reference snapshot** (`shares_digest`); enforces **sum/order/tag/flag** invariants; allows high-performance implementations **without** sacrificing bit-determinism; and matches the S5.1–S5.3 contracts exactly.

---

# S5.5 — Determinism & correctness invariants

## 1) What the validator sees (authoritative observables)

S5 persists exactly **two** parameter-scoped caches, both partitioned by `{parameter_hash, shares_digest}` and carrying lineage columns:

1. **`ccy_country_weights_cache`** — one row per $(\kappa,i)$
   Row:
   `{manifest_fingerprint, shares_digest, currency=κ, country_iso=i, weight∈[0,1], obs_count=y_i≥0, smoothing_kind∈{null,"alpha","equal_split_fallback"}, smoothing_alpha_value∈{0.5,null}}`
   **Schema**: `schemas.1A.yaml#/prep/ccy_country_weights_cache`
   **Path**: `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
   Schema enforces **group\_sum\_equals\_one** per currency (tolerance $10^{-6}$).

2. **`sparse_flag`** — one row per $\kappa$
   Row:
   `{manifest_fingerprint, shares_digest, currency=κ, is_sparse∈{true,false}, obs_count=Y≥0, threshold=T≥0}`
   **Schema**: `schemas.1A.yaml#/prep/sparse_flag`
   **Path**: `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
   Semantics: `is_sparse ≡ (Y < T)` (global equal-split fallback).

`shares_digest` is **SHA-256 of the exact `ccy_country_shares_2024Q4` snapshot used**. The dataset dictionary and artefact registry pin paths/schemas; these caches are versioned by `(parameter_hash, shares_digest)` (parameter-scoped), *not* by seed/run.

---

## 2) Determinism & lineage invariants

### I-W1 — No RNG (protocol)

S5 performs **no random draws** and emits **no RNG event streams**. Neither table may contain RNG envelope fields; no S5 paths use `{seed}` or `{run_id}`. Any RNG presence is a protocol breach.

### I-W1.1 — Replay semantics

For **fixed inputs** and a **fixed `shares_digest` + `parameter_hash`**, the persisted bytes are reproducible. Across different manifests (e.g., code/config updates), **value columns** (`weight`, `is_sparse`, `obs_count`, `threshold`) are invariant given identical inputs; lineage columns (`manifest_fingerprint`) may differ.

### I-W1.2 — Partition authority

Each table’s partition key set is **exactly** `{parameter_hash, shares_digest}`; the physical path prefix must equal the dictionary entry verbatim. Any deviation is `E/1A/S5/PERSIST/PARTITION_MISMATCH`.

---

## 3) Schema, keys, FK & coverage invariants

### I-W2 — Schema conformance

Every stored row must pass the declared **schema\_ref** (types, required fields, `manifest_fingerprint`/`shares_digest` hex64 regexes), and **`country_iso`** must **FK**-join the ISO-3166 canonical table. Violations are run-stopping schema errors `E/1A/S5/PERSIST/FK_OR_TYPES`.

### I-W3 — Primary-key uniqueness

* `ccy_country_weights_cache`: unique **(currency, country\_iso)**.
* `sparse_flag`: unique **(currency)**.
  Duplicates are fatal: `E/1A/S5/PERSIST/ORDER_OR_PK`.

### I-W4 — Currency coverage & cross-table coherence

Let $\mathcal{K}$ be the currencies present in `ccy_country_shares_2024Q4` (as identified by `shares_digest`). Then:

* For each $\kappa\in\mathcal{K}$: **at least one** weights row exists and **exactly one** `sparse_flag` row exists.
* If weights exist for $\kappa$, then $\kappa \in \mathcal{K}$.
* The set of `country_iso` in weights for $\kappa$ equals the ingress member set $\mathcal{D}(\kappa)\`.
* All weights rows for $\kappa$ are in **ASCII ISO order** by `country_iso` (see I-W6).

---

## 4) Numeric invariants (sums, ranges, construction discipline)

### I-W5 — Sum-to-one (per currency)

For each $\kappa$,

$$
\left|\sum_{i\in\mathcal{D}(\kappa)} w^{(\kappa)}_i - 1\right|\le 10^{-6}\quad\text{(schema-enforced).}
$$

The writer performs a **fixed-order compensated sum** (Neumaier) over ASCII-ordered entries and renormalises if $|1-\sum w|>10^{-12}$ before persist.
**Validator rule:** compute sums with the same fixed-order Neumaier loop; **parallel/BLAS/GPU** is allowed **iff** it reproduces that bit-pattern in binary64.

### I-W5.1 — Range & finiteness

Each persisted `weight` is **finite** and in $[0,1]$. For $D{=}1$: the single row has `weight=1`. For equal-split fallback: every row has `weight=1/D` within numeric tolerance.

### I-W5.2 — Constructive definitions (for audit)

Weights must be realisations of the S5.3 surface:

$$
w^{(\kappa)}=
\begin{cases}
\text{equal}(D), & Y < T,\[2pt]
\tilde w, & Y\ge T\ \text{and}\ \min_i y_i < T,\[2pt]
\hat w, & Y\ge T\ \text{and}\ \min_i y_i\ge T,
\end{cases}
\quad
\tilde w_i=\dfrac{y_i+\alpha_{\text{smooth}}}{Y+\alpha_{\text{smooth}} D},\
\hat w_i=\dfrac{y_i}{Y},
$$

with $\alpha\_{\text{smooth}}=0.5,\ T=30$. CI may recompute these from ingress to cross-check value-level determinism.

---

## 5) Ordering, tags & flag semantics

### I-W6 — ISO ordering (row order is part of the contract)

For a given $\kappa$, the weights rows must be **sorted by `country_iso` (ASCII byte order)**. S6 relies on this order to align deterministic Gumbel keys to destinations. Out-of-order storage is a fatal breach: `E/1A/S5/PERSIST/ORDER_OR_PK`.

### I-W7 — Smoothing metadata semantics (row-level)

Each weights row carries:

* `smoothing_kind = null` **iff** the branch used raw $\hat w$.
* `smoothing_kind = "alpha"` with `smoothing_alpha_value = 0.5` **iff** the branch used smoothed $\tilde w$ (cell-sparse $\min\_i y\_i < T$ with $Y\ge T$).
* `smoothing_kind = "equal_split_fallback"` (and `smoothing_alpha_value = null`) **iff** the global fallback fired ($Y < T$).
  A currency’s rows must be **homogeneously** tagged (same `smoothing_kind` for all $(\kappa,i)$ rows).

### I-W8 — Sparse flag semantics (table-level)

`sparse_flag.is_sparse` is **true iff $Y < T$** (global fallback) and **false otherwise**. Using smoothed $\tilde w$ never sets `is_sparse=true`. Cross-table coherence must hold:

* If `is_sparse=true`, **all** weights rows for that $\kappa$ must have `smoothing_kind="equal_split_fallback"`.
* If any weights row has `smoothing_kind="equal_split_fallback"`, then `is_sparse=true`.
  Violations: `E/1A/S5/PERSIST/SPARSE_FLAG_SEMANTICS`.

---

## 6) Validator procedure (language-agnostic, normative)

**Inputs:** S5 tables for the current `{parameter_hash, shares_digest}` partition, ingress `ccy_country_shares_2024Q4` (identified by the same `shares_digest`) for $\mathcal{D}(\kappa)$ and $y\_i$, ISO canonical, constants $\alpha\_{\text{smooth}}=0.5,\ T=30$.
**Outputs:** pass/fail and failing codes (enumerated in S5.6).

**Steps:**

1. **Dictionary/partition gate.** Paths and partition key sets **must** match exactly `{parameter_hash, shares_digest}` for both tables. Else `E/1A/S5/PERSIST/PARTITION_MISMATCH`.
2. **Schema gate.** Enforce schema refs: required columns; types; regex for `manifest_fingerprint`/`shares_digest`; FK(country\_iso) to ISO (weights only); PK uniqueness. Else `E/1A/S5/PERSIST/FK_OR_TYPES` or `E/1A/S5/PERSIST/ORDER_OR_PK`.
3. **Digest gate.** Compute `shares_digest* = SHA256(ccy_country_shares_2024Q4)` and assert **all** rows in both tables carry exactly this digest. Else `E/1A/S5/PERSIST/DIGEST_MISMATCH`.
4. **Group & order.** For each $\kappa$: collect weights rows; assert **strict ASCII ordering** by `country_iso`. Else `E/1A/S5/PERSIST/ORDER_OR_PK`.
5. **Coverage coherence.** For each $\kappa$ present in ingress by `shares_digest`:

   * assert exactly one `sparse_flag` row;
   * assert weights cover exactly $\mathcal{D}(\kappa)$ (no extras/missing);
   * assert each row’s `obs_count == y_i` from ingress.
     Else `E/1A/S5/PERSIST/COVERAGE`.
6. **Sum constraint.** For each $\kappa`: compute $S=\sum_i w_i$ (fixed-order Neumaier). Assert $|S-1|\le 10^{-6}$. Else `E/1A/S5/PERSIST/SUM\_CONSTRAINT\`.
7. **Range/finiteness.** Assert all `weight` finite in $[0,1]$; if $D{=}1$, assert `weight=1`. Else `E/1A/S5/PERSIST/RANGE`.
8. **Tag coherence.** For each $\kappa$, assert homogeneous `smoothing_kind` and valid `(kind, alpha_value)` pair:

   * if `kind="alpha"` then `alpha_value=0.5`; else `alpha_value=null`.
     Else `E/1A/S5/PERSIST/TAG`.
9. **Flag coherence.** Join with `sparse_flag` and assert I-W8. Else `E/1A/S5/PERSIST/SPARSE_FLAG_SEMANTICS`.
10. **Value determinism (strong check).** Recompute $Y=\sum\_i y\_i$, $y\_{\min}$, branch ($\hat w,\tilde w$, or equal), and target vector; re-normalise via Neumaier to compare with stored weights at tolerance $10^{-9}$. Mismatch → `E/1A/S5/PERSIST/VALUE_DRIFT`.
11. **Exit.** If all checks pass, mark S5 **valid** for this `{parameter_hash, shares_digest}`.

---

## 7) Why these invariants are sufficient (soundness)

* **No RNG + parameter-scoped versioning** makes S5 a pure function of ingress + $(\alpha\_{\text{smooth}},T)$, replayable across runs.
* **Schema/PK/FK/order** guarantee **join-safety** and a **stable** ordering for S6’s Gumbel alignment.
* **Sum/range + constructive semantics** ensure weights are true probability vectors and auditable to ingress via a single, deterministic surface.
* **Tag/flag coherence + digest binding** expose branch choices and enforce that consumers see weights derived from the **exact** reference snapshot.

---

## 8) Edge-case matrix (validator must behave accordingly)

| Situation                                   | Must hold / Validator action                                                                                                                  |
|---------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| $D=1$ currency                            | Exactly one row with `weight=1`, `smoothing_kind=null`, `smoothing_alpha_value=null`; `sparse_flag.is_sparse=false`. Else **RANGE/TAG/FLAG**. |
| $D\ge2, Y=0$                              | Equal-split weights; all `smoothing_kind="equal_split_fallback"`; `is_sparse=true`. Else **FLAG/TAG/VALUE\_DRIFT**.                           |
| $D\ge2, Y < T$                            | Equal-split weights; all `smoothing_kind="equal_split_fallback"`; `is_sparse=true`. Else **FLAG/TAG/VALUE\_DRIFT**.                           |
| $D\ge2, Y\ge T, \min y\_i < T$            | Weights $=\tilde w$; `smoothing_kind="alpha"`; `smoothing_alpha_value=0.5`; `is_sparse=false`. Else **TAG/VALUE\_DRIFT**.                   |
| $D\ge2, Y\ge T, \min y\_i \ge T$          | Weights $=\hat w$; `smoothing_kind=null`; `smoothing_alpha_value=null`; `is_sparse=false`. Else **TAG/VALUE\_DRIFT**.                       |
| Currency in weights not in snapshot         | **COVERAGE** failure.                                                                                                                         |
| Weights not ASCII-sorted within $\kappa$  | **ORDER\_OR\_PK** failure.                                                                                                                    |
| $\sum{w - 1} > 10^{-6}$                   | **SUM\_CONSTRAINT** failure.                                                                                                                  |
| `shares_digest` mismatch across tables/snap | **DIGEST\_MISMATCH** failure.                                                                                                                 |

---

**One-line takeaway:** S5.5 defines a deterministic validator that binds caches to the **exact** reference snapshot, enforces **ordering/sum/semantics** precisely, and guarantees the S5 artefacts are **byte-replayable** and **consumer-safe** for S6.

---

# S5.6 — Failure taxonomy & CI error codes (authoritative)

## 1) Observables and authority surface

Validator reads a **single build** identified by `{parameter_hash, shares_digest}`:

* **Ingress snapshot (read-only):**
  `ccy_country_shares_2024Q4` (identified by `shares_digest = SHA256(snapshot)`), defining $(\kappa,i,y\_i)$, $Y=\sum\_i y\_i$, and the member set $\mathcal D(\kappa)$. FK authority is **ISO-3166-1 canonical**.

* **S5 outputs (parameter-scoped; must exist exactly at these paths):**
  `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…` with schema `schemas.1A.yaml#/prep/ccy_country_weights_cache` (**group\_sum\_equals\_one** per currency, tol $10^{-6}$); and
  `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…` with schema `#/prep/sparse_flag`.
  Rows carry `manifest_fingerprint` and `shares_digest` as *columns*; **partitions are exactly** `{parameter_hash, shares_digest}`.

* **Governed constants:** $\alpha\_{\text{smooth}}=0.5,; T=30$.
  (Used by the S5.3 decision surface and to interpret `is_sparse`.)

S5 contains **no RNG**; any RNG presence is a protocol breach.

---

## 2) Error code format

```
err_code := "E/1A/S5/<CLASS>/<DETAIL>"
```

Examples:
`E/1A/S5/INGRESS/ISO_FK`, `E/1A/S5/PARAMS/OUT_OF_DOMAIN`,
`E/1A/S5/DECISION/GLOBAL_FLAG_MISMATCH`, `E/1A/S5/PERSIST/SUM_CONSTRAINT`,
`E/1A/S5/PERSIST/PARTITION_MISMATCH`, `E/1A/S5/PERSIST/DIGEST_MISMATCH`,
`E/1A/S5/PERSIST/ORDER_OR_PK`, `E/1A/S5/PERSIST/TAG_SCHEMA`.

Codes are **stable** and appear in the validation bundle with `{currency, country_iso?}` and small reproducer stats (e.g., $Y$, $\min y\_i$, observed tags).

---

## 3) Failure classes (exhaustive)

### A) Ingress / reference integrity

| Code                             | Precise trigger                                                                                        | Scope | Action |
| -------------------------------- | ------------------------------------------------------------------------------------------------------ | ----- | ------ |
| `E/1A/S5/INGRESS/ISO_FK`         | Any output row’s `country_iso` fails FK to ISO-3166 canonical **or** ingress has a `(κ,i)` not in ISO. | Run   | Abort. |
| `E/1A/S5/INGRESS/DUP_KEY`        | Duplicate `(κ,i)` in the ingress snapshot identified by `shares_digest`.                               | Run   | Abort. |
| `E/1A/S5/INGRESS/COUNTS_INVALID` | Any `y_i` non-integer or `y_i < 0`.                                                                    | Run   | Abort. |

### B) Parameter/config sanity

| Code                           | Precise trigger                                          | Scope | Action |
| ------------------------------ | -------------------------------------------------------- | ----- | ------ |
| `E/1A/S5/PARAMS/OUT_OF_DOMAIN` | `α_smooth ≤ 0` **or** `T < 0` in `ccy_smoothing_params`. | Run   | Abort. |

### C) Decision-surface / construction coherence (math semantics)

Compare **stored outputs** to the **unique** S5.3 surface:

* Global fallback iff `Y < T`;
* Else smoothed $\tilde w$ iff `min y_i < T`;
* Else raw $\hat w$;
* `D=1` forces `w=1`, raw tag, `is_sparse=false`.

| Code                                     | Precise trigger                                                                                                                                                   | Scope | Action |
|------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|--------|
| `E/1A/S5/DECISION/GLOBAL_FLAG_MISMATCH`  | `sparse_flag.is_sparse ≠ (Y < T)` for currency `κ`.                                                                                                               | Run   | Abort. |
| `E/1A/S5/DECISION/TAG_GLOBAL_INCOHERENT` | Some weight rows for `κ` have `"equal_split_fallback"` but `is_sparse=false`, **or** none have that tag while `is_sparse=true`.                                   | Run   | Abort. |
| `E/1A/S5/DECISION/TAG_LOCAL_INCOHERENT`  | `Y≥T` and `min y_i < T` but rows are not tagged as `smoothing_kind="alpha" & smoothing_alpha_value=0.5`, **or** `Y≥T` and `min y_i≥T` but rows not tagged `null`. | Run   | Abort. |
| `E/1A/S5/DECISION/D1_BREACH`             | `D=1` currency not persisted as a single row with `weight=1`, `smoothing_kind=null`, and `is_sparse=false`.                                                       | Run   | Abort. |
| `E/1A/S5/DECISION/OBS_COUNT_MISMATCH`    | For any `(κ,i)`: stored `obs_count ≠ y_i` from ingress.                                                                                                           | Run   | Abort. |
| `E/1A/S5/DECISION/VALUE_DRIFT`           | Given ingress counts and the chosen branch, recomputed weights (post Neumaier renorm) differ from stored weights by > `1e-9`.                                     | Run   | Abort. |

### D) Ordering / layout / persistence

| Code                                 | Precise trigger                                                                                                                                    | Scope | Action |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|-------|--------|
| `E/1A/S5/PERSIST/PARTITION_MISMATCH` | Any S5 table path/partition keys differ from **exactly** `{parameter_hash, shares_digest}` per dictionary.                                         | Run   | Abort. |
| `E/1A/S5/PERSIST/DIGEST_MISMATCH`    | Any row’s `shares_digest` ≠ the validator’s computed digest for the ingress snapshot in scope.                                                     | Run   | Abort. |
| `E/1A/S5/PERSIST/ORDER_OR_PK`        | For some `κ`, weights rows are not strictly **ASCII-sorted by `country_iso`** **or** PK duplicate exists (weights `(κ,i)` or sparse\_flag `κ`).    | Run   | Abort. |
| `E/1A/S5/PERSIST/SUM_CONSTRAINT`     | For some `κ`, $\bigl\|\sum_i w_i^{(\kappa)} - 1\bigr\| > 10^{-6}$ (group sum gate).                                                                     | Run   | Abort. |
| `E/1A/S5/PERSIST/RANGE`              | Any `weight` is non-finite or outside `[0,1]`; or `D=1` row not exactly `1.0` within tolerance.                                                    | Run   | Abort. |
| `E/1A/S5/PERSIST/FK_OR_TYPES`        | Any schema/type/regex breach (e.g., `manifest_fingerprint`/`shares_digest` not hex64) or FK failure to ISO.                                        | Run   | Abort. |
| `E/1A/S5/PERSIST/COVERAGE`           | Coverage parity broken: weights ISO set ≠ ingress $\mathcal D(κ)$, or missing/extra `sparse_flag` row for `κ`.                                   | Run   | Abort. |
| `E/1A/S5/PERSIST/TAG_SCHEMA`         | Metadata domain invalid: `smoothing_kind ∉ {null,"alpha","equal_split_fallback"}` **or** `smoothing_alpha_value` not `{0.5,null}` as per the kind. | Run   | Abort. |

### E) Protocol

| Code                           | Precise trigger                                                                           | Scope | Action |
|--------------------------------|-------------------------------------------------------------------------------------------|-------|--------|
| `E/1A/S5/PROTOCOL/RNG_PRESENT` | Any RNG envelope/event detected for S5 (S5 is deterministic and must not consume Philox). | Run   | Abort. |

---

## 4) Cross-table coherence rules (must all hold)

For each `κ`:

1. **Coverage parity:** weights’ `country_iso` set equals ingress $\mathcal D(κ)$; exactly one `sparse_flag` row exists.
2. **Tag ↔ flag:** `is_sparse = (Y < T)`; iff `true` then **all** weight rows have `smoothing_kind="equal_split_fallback"`. If `false`, **none** may. Smoothed (`"alpha" & 0.5`) never sets `is_sparse`.
3. **Ordering:** weights rows for `κ` are in **ASCII** order by `country_iso` (writers ensure; validator asserts).

---

## 5) Language-agnostic validator (emits codes)

**Input:** current `{parameter_hash, shares_digest}` partitions of the two S5 tables; ingress snapshot (same `shares_digest`); ISO canonical; constants `α_smooth=0.5`, `T=30`.
**Output:** pass/fail + list of `E/1A/S5/...` codes with examples.

**Procedure (deterministic):**

1. **Dictionary/partition gate** → else `PERSIST/PARTITION_MISMATCH`.
2. **Schema+PK+FK gate** (types, hex64 fields, FK ISO, PK uniqueness) → else `PERSIST/FK_OR_TYPES` or `PERSIST/ORDER_OR_PK`.
3. **Digest gate** (all rows share the validator’s `shares_digest`) → else `PERSIST/DIGEST_MISMATCH`.
4. **Per-κ loop:**

   * **Coverage** (weights’ ISO set == ingress $\mathcal D(κ)$; exactly one flag row) → else `PERSIST/COVERAGE`.
   * **Ordering** (ASCII) → else `PERSIST/ORDER_OR_PK`.
   * **Sum** (Neumaier; `|∑w − 1| ≤ 1e−6`) → else `PERSIST/SUM_CONSTRAINT`.
   * **Range** (`w ∈ [0,1]`; `D=1 ⇒ w=1`) → else `PERSIST/RANGE`.
   * **Obs counts** (`obs_count == y_i`) → else `DECISION/OBS_COUNT_MISMATCH`.
   * **Branch maths:** compute `D, Y, y_min`, booleans `global=(Y<T)`, `cell=(y_min<T)`.
     • `is_sparse==global` → else `DECISION/GLOBAL_FLAG_MISMATCH`.
     • If `global`: equal-split within `1e−9` & tag `"equal_split_fallback"` → else `DECISION/TAG_GLOBAL_INCOHERENT`.
     • If `!global && cell`: tag `"alpha"` with `0.5` & values match $\tilde w$ within `1e−9` → else `DECISION/TAG_LOCAL_INCOHERENT`.
     • If `!global && !cell`: tag `null` & values match $\hat w$ within `1e−9` → else `DECISION/TAG_LOCAL_INCOHERENT`.
5. **Protocol check:** no RNG artefacts → else `PROTOCOL/RNG_PRESENT`.

On first violation, **abort** with the specific code; CI may optionally accumulate all codes.

---

## 6) Canonical examples (deterministic reproducer)

* **Global fallback mis-tag:** `D=3, Y=0`. Expected: equal-split weights; all `smoothing_kind="equal_split_fallback"`; `is_sparse=true`. If stored as `"alpha"` with `0.5` → `DECISION/GLOBAL_FLAG_MISMATCH` **and** `DECISION/TAG_GLOBAL_INCOHERENT`.
* **Local smoothing mis-tag:** `D=4, Y=200, min y_i=5 < T`. Expected: tag `"alpha"` & $\tilde w$. If tag `null` or values match $\hat w$ → `DECISION/TAG_LOCAL_INCOHERENT`.
* **Ordering breach:** weights rows appear as `["ZA","AE","BE"]` instead of ASCII `["AE","BE","ZA"]` → `PERSIST/ORDER_OR_PK`.
* **Sum failure:** any `κ` with stored `∑w = 1.000002` → `PERSIST/SUM_CONSTRAINT`.
* **Digest mismatch:** outputs written under `shares_digest=A` while validator sees ingress digest `B` → `PERSIST/DIGEST_MISMATCH`.

---

## 7) Why this taxonomy is complete

It covers **all observable invariants**: dictionary paths & **parameter-scoped digest-bound** partitioning, **schema/PK/FK**, **ordering**, **sum/range**, and the **mathematical decision surface** (global fallback vs smoothed vs raw), including degenerate `D=1` and the **no-RNG protocol**. Each code maps to a single falsifiable predicate over the persisted caches and ingress, matching S5.1–S5.5 exactly.

---

# S5.7 — State boundary (authoritative)

## 1) Upstream prerequisites (must already hold)

* **Branch & count.** For merchant $m$, **S3** fixed eligibility $e_m\in\{0,1\}$. If $e_m=1$ and the ZTP loop in **S4** accepted, S4 exposes $K_m\in\{1,2,\dots\}$. If S4 exhausted retries, the merchant is either aborted or downgraded to domestic-only (policy). **S5/S6 are skipped** for that merchant.
* **Merchant currency.** **S5.0** has persisted `merchant_currency` (parameter-scoped). It is the **only** authority for $\kappa_m$ used by S6. S5 must not recompute currencies.

> These gates are **preconditions**. **S5 runs deterministically, merchant-agnostic, and parameter-scoped**; it produces caches regardless of which merchants proceed into S6.

---

## 2) Inputs consumed by S5 (deterministic, read-only)

* `ccy_country_shares_2024Q4` (ingress; rows $(\kappa,i,y_i)$) — defines $\mathcal D(\kappa)$ and observation counts; FK $i\rightarrow$ ISO canonical. Schema: `schemas.ingress.layer1.yaml#/ccy_country_shares`.
  **shares\_digest := SHA-256** of the exact snapshot used in the build.
* **ISO-3166-1 canonical** — PK + ordering authority for `country_iso` (enforces FK and ASCII order).
* **Governed constants:** $\alpha_{\text{smooth}}=0.5,\;T=30$ (used by S5.3 to choose raw $\hat w$, smoothed $\tilde w$, or equal-split).
* (Context only) `settlement_shares_2024Q4` at currency level; governs wider assembly, **not** intra-currency normalisation.

**S5 ingests no RNG**; any such presence is a protocol breach.

---

## 3) Outputs materialised by S5 (and only these)

S5 persists two **parameter-scoped, snapshot-bound** caches, **partitioned by `{parameter_hash, shares_digest}`**. `manifest_fingerprint` and `shares_digest` are **columns**; only `{parameter_hash, shares_digest}` are partition keys. Paths and schema refs are dictionary-fixed.

1. **Weights cache**
   `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
   Schema: `schemas.1A.yaml#/prep/ccy_country_weights_cache`.
   One row per $(\kappa,i)$:

   ```
   { manifest_fingerprint, shares_digest,
     currency=κ, country_iso=i,
     weight∈[0,1] (binary64), obs_count=y_i (int64 ≥ 0),
     smoothing_kind ∈ {null,"alpha","equal_split_fallback"},
     smoothing_alpha_value ∈ {0.5,null} }
   ```

   **PK:** `(currency, country_iso)`; **FK:** `country_iso` → ISO; **group\_sum\_equals\_one** per $\kappa$ (tol $10^{-6}$).
   **Canonical order within a currency:** **ASCII** by `country_iso`.

2. **Sparse flag**
   `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/shares_digest={shares_digest}/…`
   Schema: `schemas.1A.yaml#/prep/sparse_flag`.
   One row per $\kappa$:

   ```
   { manifest_fingerprint, shares_digest,
     currency=κ, is_sparse=(Y<T), obs_count=Y (int64), threshold=T (int64) }
   ```

   **PK:** `(currency)`.
   **Semantics:** `is_sparse` is **true iff** S5 used **equal-split fallback** because `Y < T`. Using smoothed (`"alpha"`) alone does **not** set `is_sparse`.

S5 writes **no** seed/run-scoped artefacts and **no** RNG event streams.

---

## 4) Mathematical contract of what’s inside the weights cache

For each currency $\kappa$ with member set $\mathcal D(\kappa)=\{i_1,\dots,i_D\}$, counts $y_i\ge 0$, total $Y=\sum_i y_i$, **S5.3** deterministically chooses:

$$
w^{(\kappa)}=
\begin{cases}
\text{equal split }(1/D,\dots,1/D), & Y < T, [2pt]
\tilde w \ \text{with}\ \tilde w_i=\dfrac{y_i+\alpha_{\text{smooth}}}{Y+\alpha_{\text{smooth}} D}, & Y\ge T\ \&\ \min_i y_i < T,\[10pt]
\hat w \ \text{with}\ \hat w_i=\dfrac{y_i}{Y}, & Y\ge T\ \&\ \min_i y_i\ge T,
\end{cases}
\quad \alpha_{\text{smooth}}=0.5,\;T=30.
$$

It then renormalises in binary64 to $\sum_i w^{(\kappa)}_i=1$ (tolerance $10^{-12}$ pre-persist; schema gate $10^{-6}$). Rows are persisted in **ISO ASCII order** by `country_iso`.

Downstream consumers must treat this cache as **authoritative** for $\kappa\mapsto\{(i,w_i)\}$.

---

## 5) Downstream contract to **S6** (precise usage)

Given a merchant $m$ admitted to S6:

1. **Verify snapshot & resolve currency.**
   Read $\kappa_m$ from `merchant_currency` (parameter-scoped). **Do not recompute.**
   **Verify** that the S5 partitions you’ll read match your manifest’s **`{parameter_hash, shares_digest}`**. If digests differ, **fail fast**.

2. **Load prior weights (in canonical order).**
   Read $\{(\kappa_m,i,w_i)\}$ from `ccy_country_weights_cache` (same `{parameter_hash, shares_digest}`), together with `smoothing_kind/alpha` and `obs_count`. Data are stored in **ASCII** `country_iso` order; **readers may re-sort by `country_iso`** to re-establish the canonical order if the engine doesn’t preserve row order. Schema already enforces $\sum_i w_i=1$ within $10^{-6}$.

3. **Form the foreign candidate set.**
   Let $c$ be the merchant’s **home ISO**. Define $\mathcal F_m=\mathcal D(\kappa_m)\setminus\{c\}$ in **preserved canonical order** (drop home if present; if not present, $\mathcal F_m=\mathcal D(\kappa_m)$). Let $M_m=|\mathcal F_m|$.

4. **Cap the draw size.**
   $K_m^\star=\min(K_m,M_m)$. If $M_m=0$, set $K_m^\star=0$, persist `country_set` with **only the home row** (`rank=0`), **no** `gumbel_key`, then continue the pipeline (reason `"no_candidates"`).

5. **Renormalise on the foreign set (before sampling).**
   Compute $S=\sum_{i\in\mathcal F_m} w_i$ using a **fixed-order** (ASCII) Neumaier sum, then set

   $$
   \tilde w_i=\frac{w_i}{S}\quad\text{for }i\in\mathcal F_m,
   $$

   and assert $\sum_{i\in\mathcal F_m}\tilde w_i=1$ within $10^{-12}$. These $\tilde w$ drive **Gumbel-top-$K_m^\star$** in S6.

6. **RNG usage begins in S6 only.**
   S6 logs exactly $M_m$ `gumbel_key` events (one per candidate) and persists `country_set` (home `rank=0` + selected foreigns `rank=1..K_m^\star`) **in the same order as the winners’ selection order**. `country_set` is the **only authority** for cross-country order thereafter.

---

## 6) Cross-table coherence required at the boundary

* For each $\kappa$ present in the weights cache, there is **exactly one** `sparse_flag` row, and the weights’ `country_iso` set equals ingress $\mathcal D(\kappa)$. Weights are in **ASCII** order.
* `sparse_flag.is_sparse = (Y<T)` **iff** all weights rows for $\kappa$ carry `smoothing_kind="equal_split_fallback"`. Smoothed (`"alpha"` with `0.5`) **never** sets `is_sparse`.
* S6 must fail fast if the weights cache has **no rows** for $\kappa_m$ (precondition to selection) or if `shares_digest` mismatches.

---

## 7) Determinism, partitions, and lineage at the boundary

* **Determinism.** For fixed ingress + $(\alpha_{\text{smooth}},T)$ and fixed `{parameter_hash, shares_digest}`, S5 outputs are **pure functions**—byte-replayable across re-runs (lineage columns like `manifest_fingerprint` may differ with manifest changes).
* **Partitions & schema authority.** Both caches live under dictionary-pinned paths, partitioned by **`{parameter_hash, shares_digest}`**; schemas enforce PKs, FKs, group-sum, and field domains. Any deviation is a run-stopping persistence/layout error.
* **Ordering.** Canonical order is **ASCII** by `country_iso`. Writers **should** physically sort; consumers **may** re-sort to re-establish canonical order before any ordered computation.

---

## 8) Minimal boundary APIs (language-agnostic)

Deterministic interfaces S6—and validators—may assume over S5 artefacts:

```text
FUNCTION S5_get_weights(parameter_hash, shares_digest, κ)
  -> OrderedList[(i, w_i, smoothing_kind, smoothing_alpha_value, y_i)]
  Pre: κ ∈ currencies present in weights_cache(parameter_hash, shares_digest)
  Post: returns rows in ASCII ISO order; Σ w_i = 1 within 1e-6; |rows| = |D(κ)|

FUNCTION S5_get_sparse_flag(parameter_hash, shares_digest, κ)
  -> (is_sparse: bool, Y: int64, T: int64)
  Post: is_sparse == (Y < T)

FUNCTION S5_boundary_for_merchant(parameter_hash, shares_digest, merchant_id, home_iso, κ_m, K_m)
  W := S5_get_weights(parameter_hash, shares_digest, κ_m)
  # ensure canonical order (defensive):
  W := sort_ASCII_by_country_iso(W)
  F := [ (i, w) ∈ W where i ≠ home_iso ]
  M := |F|
  K* := min(K_m, M)
  if M == 0:
      return {K_star=0, foreign_candidates=[], prior_weights=[], reason="no_candidates"}
  else:
      S := Σ_{(i,w)∈F} w  (fixed-order Neumaier)
      return {K_star=K*, foreign_candidates=[i for (i,_)∈F], prior_weights=[w/S for (_,w)∈F]}
```

These APIs are **purely deterministic** and never read `seed`/`run_id`. S6 uses `foreign_candidates` order and `prior_weights` to log `gumbel_key` and to emit the ordered `country_set`.

---

## 9) What S5 does **not** do at this boundary

* No RNG or seed/run-scoped streams—RNG begins in **S6** (with `gumbel_key`).
* Does **not** drop the home ISO itself; exclusion happens in **S6**.
* Does **not** persist `country_set`; that dataset is **authoritatively materialised by S6** (home-only for domestic/downgraded, or home + $K_m^\star$ foreigns).

---

### One-line takeaway

**S5** exposes two snapshot-bound, parameter-scoped caches—`ccy_country_weights_cache` and `sparse_flag`—that map any currency $\kappa$ to an **ASCII-ordered, sum-to-1** prior over destination countries plus a **global-sparsity flag**. **S6** verifies `shares_digest`, reads $\kappa_m$, drops home, renormalises on the foreign set, caps by $K_m$, and *then* begins RNG (Gumbel-top-$K$), persisting the authoritative `country_set`.

---