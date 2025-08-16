# S5.1 — Universe, symbols, authority

## 1) Placement, scope, purpose

* **Where we are.** S5 follows S5.0 (which deterministically fixes each merchant’s settlement currency $\kappa_m$ and persists `merchant_currency`) and sits after S4 has exposed $K_m$ for eligible merchants. S5 itself does **no** sampling; it constructs **deterministic currency→country weights** that S6 will later combine with each merchant’s context to select foreign countries.
* **What this sub-state does.** S5.1 **does not persist** outputs. It ingests the authoritative reference tables, checks schema/keys/order, and prepares a validated, **ordered** per-currency map $\kappa \mapsto(\mathcal D(\kappa), \{y_i\}, Y, D)$ for S5.2–S5.3. (Persistence happens in S5.4.)

> Note: `merchant_currency` (from S5.0) is the only authority for $\kappa_m$ per merchant; S5.1 does **not** recompute currencies, it only prepares the **global** per-currency splits used for all merchants who carry a given $\kappa$.

---

## 2) Authoritative inputs (read-only) and their schemas

* **Currency→country splits (with counts)**: `ccy_country_shares_2024Q4`, schema `schemas.ingress.layer1.yaml#/ccy_country_shares`. Rows carry `(currency=κ, country_iso=i, obs_count=y_i)` and define the membership $\mathcal D(\kappa)$ and $y_i\ge 0$ used downstream to construct weights.
* **Settlement shares (currency-level)**: `settlement_shares_2024Q4`, schema `#/settlement_shares`. Used to govern the **wider 1A candidate assembly**, not the **intra-currency** normalisation in S5. (It helps ensure which currencies are in scope; S5.1 treats it as read-only context.)
* **ISO-3166 canonical**: FK authority + ordering authority for `country_iso` referenced by 1A schemas.
* **Smoothing policy (config)**: `ccy_smoothing_params` (e.g., $\alpha \approx 0.5$, thresholds used later). This is referenced in the artefact registry and fixed formally in S5.2.
* **Per-merchant currency (from S5.0)**: `merchant_currency` (parameter-scoped, schema `#/prep/merchant_currency`) consumed by S6 together with S5’s caches; listed here to ground the authority chain.

---

## 3) Authority over outputs (declared here for downstream)

S5 ultimately persists **two parameter-scoped caches** (S5.4). S5.1 doesn’t write them, but it **pins their contracts** so implementers validate toward the right targets throughout S5:

* **`ccy_country_weights_cache`** — expanded per-$(\kappa,i)$ weights, `schemas.1A.yaml#/prep/ccy_country_weights_cache`, **partitioned by `{parameter_hash}`**, with a **group_sum_equals_one** constraint per currency (tolerance $10^{-6}$).
* **`sparse_flag`** — per-$\kappa$ sparsity indicator, `schemas.1A.yaml#/prep/sparse_flag`, **partitioned by `{parameter_hash}`**. (True iff equal-split fallback fires; detailed in S5.3/S5.4.)

Schema authority and dictionary IDs/paths are governed centrally; S5 must adhere to those exact `schema_ref` and path patterns.

---

## 4) Universe & symbols fixed by S5.1 (notation)

For an ISO-4217 currency $\kappa$:

* **Membership**: $\mathcal{D}(\kappa) = \{ i_1,\dots,i_D \}\subset \mathcal I$, where $\mathcal I$ is the ISO-3166 alpha-2 set. $D = |\mathcal{D}(\kappa)|$. Derived from `ccy_country_shares_2024Q4`.
* **Counts**: $y_i \in \mathbb Z_{\ge 0}$ (ingress count per destination). Total $Y=\sum_{i\in \mathcal D(\kappa)} y_i$. These are prepared now and consumed by S5.2–S5.3 to construct $\hat w, \tilde w$ and decisions.
* **Ordering**: within a currency, rows are **sorted by `country_iso` (ASCII)**; this order is fixed **here** and carried forward to persistence to stabilise downstream selection.

---

## 5) Contracts S5.1 must enforce (inputs→context)

**No RNG.** S5 emits no RNG events and consumes no Philox counters; any RNG usage inside S5 is a protocol breach.

**Schema & FK discipline.**

* Every $(\kappa,i)$ read from `ccy_country_shares_2024Q4` must join the ISO canonical table via `country_iso`. **FK( country_iso )** is authoritative.
* `obs_count=y_i` must be integer, $y_i\ge 0$; duplicates $(\kappa,i)$ are not allowed.

**Partitioning discipline (for later persistence).**

* The two S5 caches are **parameter-scoped** and **must** be written under the dictionary’s paths with partition set = `{parameter_hash}` (no `seed`, no `run_id`). (Declared here to avoid drift when we reach S5.4.)

**Ordering contract.**

* For each $\kappa$, S5 maintains and later persists rows in **ASCII order of `country_iso`**. This is part of S5’s invariants, enabling reproducible joins and stable S6 Gumbel alignment.

---

## 6) Language-agnostic reference algorithm (“prepare S5 context”)

This is the **exact** procedure S5.1 must follow. It is implementation-neutral and deterministic.

```text
INPUTS:
  - A := ccy_country_shares_2024Q4   # (κ, country_iso=i, obs_count=y_i)
  - B := settlement_shares_2024Q4    # currency-level context (read-only here)
  - ISO := iso3166_canonical         # FK + ordering authority
  - Params := ccy_smoothing_params   # α, thresholds (to be used in S5.2/5.3)
  - (No RNG inputs)

OUTPUT (in-memory only; nothing persisted in S5.1):
  - Map M where for each currency κ:
      M[κ] = {
        D: integer ≥ 1,
        members: [i_1, ..., i_D]          # ASCII-sorted by `country_iso`
        counts:  [y_{i_1}, ..., y_{i_D}]  # integers, y_i ≥ 0
        Y: Σ y_i                           # 64-bit float or 64-bit int, used downstream
      }

ALGORITHM:

1  Load ISO; build set I := {valid country_iso} (primary-key domain).
2  Load A (ccy_country_shares_2024Q4) with schema checks:
   2.1 Assert types: currency is ISO-4217 string; country_iso ∈ STRING; obs_count integer.
   2.2 Assert obs_count ≥ 0 for all rows (ingress constraint).
   2.3 Assert FK: every country_iso ∈ I; on any miss → FAIL F-S5/INGRESS/ISO_FK.

3  Group A by currency κ to assemble provisional membership:
   3.1 For each κ: collect pairs (i, y_i). Assert no duplicate (κ, i); else → FAIL F-S5/INGRESS/DUP_KEY.
   3.2 If group is empty (D=0): → FAIL F-S5/INGRESS/MISSING_ROWS.

4  For each κ:
   4.1 Sort the list of members by `country_iso` in ASCII order → [i_1, ..., i_D].
   4.2 Build counts vector in that order → [y_{i_1}, ..., y_{i_D}].
   4.3 Compute Y := Σ_{j=1..D} y_{i_j}. (Use 64-bit integer or binary64; downstream smoothing uses binary64.)
   4.4 Record M[κ] := { D, members, counts, Y }.

5  Emit (in-memory) M to S5.2/S5.3. Do not persist any rows in S5.1.

FAILURE SEMANTICS (abort the run on any of the following):
  - F-S5/INGRESS/ISO_FK: a row’s country_iso not in ISO canonical.
  - F-S5/INGRESS/COUNTS_INVALID: any obs_count non-integer or < 0.
  - F-S5/INGRESS/MISSING_ROWS: κ present in the wider 1A scope but has no (κ,i) rows in A.
  - F-S5/INGRESS/DUP_KEY: duplicate (κ,i) encountered.
```

These checks, symbols, and ordering rules are the foundation S5.2–S5.4 rely on; they match the dictionary + schema authority and the expanded S5 invariants.

---

## 7) What **will** be persisted later (declared now, not executed here)

S5.4 will materialise (parameter-scoped, partition `{parameter_hash}`):

* `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/` with PK `[currency,country_iso]`, `group_sum_equals_one` per currency (tolerance $10^{-6}$), ISO FK enforced.
* `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/` with PK `[currency]` and semantics `is_sparse = (Y < T)`.

Persistence rules and numeric tolerances are fixed in S5.4; S5.1 simply **locks the targets** so construction stays aligned.

---

## 8) Determinism & replay

* **I-S5-B (no randomness):** S5 uses no RNG; no RNG event streams exist for S5; any such rows would be a protocol breach.
* **I-S5-C (bit-stability under fixed lineage):** For fixed inputs and `parameter_hash`, the **bytes** of the persisted caches (S5.4) are reproducible across replays; digests can be CI-checked per currency. (Lineage columns like `manifest_fingerprint` are expected to match within a fixed manifest.)

---

## 9) Cross-state authority chain (for consumers)

* **Per-merchant currency $\kappa_m$**: read from `merchant_currency` (S5.0), parameter-scoped; never recomputed in S5/S6.
* **Per-currency weights $w^{(\kappa)}$** + **sparse flag**: read from the two S5 caches (parameter-scoped) that S5.4 will write. S6 then removes the home ISO, renormalises as needed, and draws Gumbel keys to pick $K_m$ foreigns. (Inter-country order is persisted in `country_set` later; `outlet_catalogue` never encodes cross-country order.)

---

### One-line summary

**S5.1** deterministically builds the per-currency **membership+counts context** $\kappa \mapsto (\mathcal D(\kappa),\{y_i\},Y)$ with strict **FK**, **uniqueness**, and **ASCII ordering**; it persists nothing, sets no RNG lineage, and locks the exact **schema/path** authority for the caches S5 will write later.

---

# S5.2 — Symbols & fixed hyperparameters

## 1) Purpose & authority

S5.2 defines the **per-currency objects** and **constants** from which S5.3 deterministically builds weights and flags. The notation matches the locked S5 text and the combined state flow; constant values are fixed by the 1A subsegment assumptions for this vintage.

**Upstream inputs referenced (read-only):**

* `ccy_country_shares_2024Q4` (ingress): provides $(\kappa,i,y_i)$, the member set $\mathcal D(\kappa)$ and counts. Schema: `schemas.ingress.layer1.yaml#/ccy_country_shares`.
* ISO-3166 canonical (FK + ordering authority). (Used in S5.1 and enforced again at persistence.)
* Smoothing policy entry in the artefact registry (`ccy_smoothing_params`) documents the **α≈0.5** prior; values are pinned below.

---

## 2) Primary symbols (per currency $\kappa$)

For an ISO-4217 currency $\kappa$:

* **Member set and size**

  $$
  \boxed{\ \mathcal D(\kappa)=\{i_1,\dots,i_D\}\subset\mathcal I,\quad D=|\mathcal D(\kappa)|\ }.
  $$

  Built from `ccy_country_shares_2024Q4` (PK $(\kappa,i)$).
* **Observation counts and total**

  $$
  \boxed{\ y_i\in\mathbb Z_{\ge0}\ \text{for }i\in\mathcal D(\kappa),\qquad Y:=\sum_{i\in\mathcal D(\kappa)} y_i\ }.
  $$

  `obs_count=y_i` comes directly from ingress.

**Ordering contract.** Within each $\kappa$, the member list is **sorted by `country_iso` (ASCII)** and this order is **sticky** across all S5 steps and persistence. (This is already established in S5.1 and enforced again in S5.4.)

---

## 3) Fixed hyperparameters (governed; not tuned inside S5)

* **Additive Dirichlet smoothing constant (symmetric prior):**

  $$
  \boxed{\ \alpha := 0.5\ }.
  $$
* **Sparsity threshold (observations):**

  $$
  \boxed{\ T := 30\ }.
  $$

These are the values specified in the locked S5 text; they drive both **cell-level** smoothing choice and the **global** equal-split fallback gate used in S5.3.

---

## 4) Derived quantities (available for S5.3 decisions)

* **Cell minimum & indicator**

  $$
  y_{\min}=\min_{i\in\mathcal D(\kappa)} y_i,\qquad \mathbf 1_{\text{cell-sparse}}:=\mathbf 1\{\,y_{\min} < T\,\}.
  $$

  (Cell sparsity is a *local* trigger for choosing smoothed weights.)
* **Smoothed counts (additive Dirichlet) and total**

  $$
  \boxed{\ \tilde y_i:=y_i+\alpha,\quad \tilde Y:=\sum_i \tilde y_i = Y+\alpha D\ }.
  $$

  For any $D\ge1$ and $\alpha > 0$: $\tilde y_i > 0,\ \tilde Y > 0$.
* **Candidate weight vectors**

  $$
  \hat w_i:=\frac{y_i}{Y}\quad(\text{defined only if }Y > 0),\qquad
  \tilde w_i:=\frac{\tilde y_i}{\tilde Y}=\frac{y_i+\alpha}{Y+\alpha D}\quad(\text{always defined}).
  $$

  $\tilde w_i > 0$ for all $i$ (strictly positive). S5.3 will choose between $\hat w$, $\tilde w$, or equal split.

**Key identity (convex combination).** For $D\ge2$ and any $Y\ge0$,

$$
\boxed{\ \tilde w_i=\frac{Y}{Y+\alpha D}\,\hat w_i+\frac{\alpha D}{Y+\alpha D}\,\frac{1}{D}\ }\quad(\text{interpret }\hat w\text{ only if }Y > 0).
$$

Thus $\tilde w$ is a convex blend of **raw proportions** and **equal split**, with the **prior weight** $\frac{\alpha D}{Y+\alpha D}$ increasing as $Y\downarrow 0$.

**Global fallback equivalence.**

$$
\boxed{\ \tilde Y < T+\alpha D\ \Longleftrightarrow\ Y < T\ }.
$$

This is the condition under which S5.3 forces **exact equal-split** and sets `is_sparse = true`.

---

## 5) Domains, bounds, and edge-case guarantees

* **Domains.** $\alpha > 0$, $T\in\mathbb Z_{\ge0}$, $y_i\in\mathbb Z_{\ge0}$, $D\in\mathbb Z_{\ge1}$, $Y\in\mathbb Z_{\ge0}$. (Values $\alpha=0.5,\ T=30$ are fixed for this vintage.)
* **Positivity & normalisation.** If $Y > 0$ then $\sum_i \hat w_i=1$. Always: $\sum_i \tilde w_i=1$. (S5.3 still renormalises to 1 within $10^{-12}$ and S5.4 enforces $10^{-6}$ at schema.)
* **Continuity/limits (multi-country $D\ge2$).**

  * $Y\to\infty$ with fixed proportions $\Rightarrow \tilde w\to\hat w$.
  * $Y\to 0$ $\Rightarrow \tilde w\to$ equal split; S5.3 then **forces** equal split via the global gate $Y < T$.
* **$D=1$ (degenerate).** We set $w_{i_1}=1$ regardless of $y_{i_1}$ (even $0$); smoothing and fallback do **not** apply.
* **Well-posedness at $Y=0$.** $\hat w$ is undefined (not used); $\tilde w$ is well-defined (strictly positive) and S5.3’s global rule $Y < T$ switches to exact equal-split with `is_sparse=true`.

---

## 6) Numeric discipline (binary64; exact checks later)

* **Types.** Treat $y_i, Y, D, T$ as integers at load; convert to **binary64** only for division and sums when constructing $\hat w,\tilde w$. (Prevents integer overflow and keeps sums stable.) Tolerance at persistence: $|1-\sum_i w_i|\le 10^{-6}$.
* **Renormalisation guard.** Even though $\hat w,\tilde w$ sum to 1 algebraically, S5.3 re-scales by $s=\sum_i w_i$ if $|1-s| > 10^{-12}$ (accumulation/round-off), then S5.4 validates the $10^{-6}$ constraint.
* **Ordering stability.** Always carry vectors in **ISO ASCII order** to avoid non-determinism downstream.

---

## 7) Language-agnostic reference algorithm (S5.2 “symbol table”)

This produces the *pure* S5.2 context per currency. It **persists nothing**.

```text
INPUT:
  From S5.1 (validated, ISO-ordered):
    For each currency κ:
      members[1..D] = [i_1, ..., i_D]            # ASCII ISO order
      counts[1..D]  = [y_{i_1}, ..., y_{i_D}]    # int64, y_i ≥ 0
      Y = Σ y_i                                   # int64
  Constants (governed): α = 0.5, T = 30

OUTPUT (in-memory only; handed to S5.3):
  For each κ, a context record:
    {
      D: int ≥ 1,
      members[1..D]: ISO codes,
      counts[1..D]: int64,
      Y: int64,
      y_min: int64,
      # Derived (binary64):
      tilde_counts[1..D] = y_i + α,
      tilde_Y = Y + α·D,
      hat_w[1..D]      = (Y > 0 ? y_i / Y : NaN),
      tilde_w[1..D]    = (y_i + α) / (Y + α·D),
      # Decision aides for S5.3 (no branching yet):
      cell_sparse = (y_min < T),
      global_sparse_equiv = (Y < T)              # ⇔ (tilde_Y < T + α·D)
    }

ALGORITHM (per κ):
  1  D ← length(members); assert D ≥ 1
  2  Y ← Σ counts; y_min ← min(counts)
  3  tilde_counts[i] ← counts[i] + α      for i=1..D
  4  tilde_Y ← Y + α·D
  5  if Y > 0: hat_w[i] ← counts[i] / Y   else: hat_w[i] ← NaN (unused later if Y=0)
  6  tilde_w[i] ← tilde_counts[i] / tilde_Y
  7  cell_sparse ← (y_min < T)
  8  global_sparse_equiv ← (Y < T)        # note: equivalent to (tilde_Y < T + α·D)
  9  EMIT context record (no writes)
```

This table is **exactly** what S5.3 consumes to apply the decision surface: **Case A** $D{=}1$ → degenerate; **Case B** $D{\ge}2$ → choose raw $\hat w$, smoothed $\tilde w$, or **equal-split** on the global fallback $Y < T$, then renormalise and tag.

---

## 8) Minimal failure surface at S5.2 (deterministic)

S5.2 itself does not write data; it can still **abort the run** if the constants or inputs are invalid:

* **Bad constants** (config error): $\alpha\le0$ or $T < 0$ → `F-S5/PARAMS/OUT_OF_DOMAIN`. (Values are fixed for the vintage, so this guards misconfiguration.)
* **Upstream integrity breaches** (should already be caught in S5.1): non-finite counts, $D=0$, duplicate $(\kappa,i)$, FK failures. These are schema/ingress errors, not S5.2 math errors.

---

## 9) What S5.2 does **not** do

* It does **not** decide the final $w^{(\kappa)}$ (that’s S5.3), and it does **not** persist anything (that’s S5.4).
* It does **not** consume or emit RNG (S5 uses no randomness at all).

---

### One-line takeaway

S5.2 fixes the **objects** $(\mathcal D(\kappa),y_i,Y)$, the **deriveds** $(\tilde y_i,\tilde Y,\hat w,\tilde w)$, and the **constants** $(\alpha{=}0.5,\,T{=}30)$ with full domains and numerics, ready for S5.3’s deterministic decision surface and S5.4’s parameter-scoped caches.

---

# S5.3 — Deterministic expansion

## 1) Purpose & placement

Given the S5.2 context for each currency $\kappa$ — ordered members $\mathcal D(\kappa)=\{i_1,\dots,i_D\}$, counts $y_i\ge0$, total $Y=\sum_i y_i$, and constants $\alpha{=}0.5,\,T{=}30$ — produce a **final** ISO-ordered weight vector $w^{(\kappa)}$ that sums to 1, with **no RNG**. S5.4 will persist:

* `ccy_country_weights_cache` (per $(\kappa,i)$ rows with `weight` and a `smoothing` tag), and
* `sparse_flag` (per $\kappa$ row with `is_sparse = (Y < T)`).
  Both are **parameter-scoped** and pinned in the dataset dictionary.

---

## 2) Inputs (from S5.2) & constants (governed)

Per currency $\kappa$ (ASCII-sorted members):

* $D=|\mathcal D(\kappa)|\in\mathbb Z_{\ge1}$.
* $y_i\in\mathbb Z_{\ge0}$ for $i\in\mathcal D(\kappa)$; $Y=\sum_i y_i\in\mathbb Z_{\ge0}$.
* Smoothed counts: $\tilde y_i=y_i+\alpha$; $\tilde Y=Y+\alpha D$.
* Candidate vectors:
  $\hat w_i = \dfrac{y_i}{Y}$ (defined iff $Y > 0$),
  $\tilde w_i = \dfrac{y_i+\alpha}{Y+\alpha D}$ (always defined).

Governed constants for this vintage: $\alpha=0.5,\;T=30$.

**Ordering contract:** the member list $(i_1,\dots,i_D)$ is **fixed in ASCII ISO order** and must be preserved in all S5.3 outputs.

---

## 3) Decision surface (complete and unambiguous)

### Case A — Single-country currency ($D=1$)

Deterministic, degenerate outcome:

$$
w^{(\kappa)}_{i_1} \equiv 1,\quad \texttt{smoothing}=\texttt{null},\quad \texttt{is_sparse}=\texttt{false}.
$$

Counts $y_{i_1}$ may be 0; no smoothing or fallback applies.

### Case B — Multi-country currency ($D\ge2$)

Define:

* **Cell-sparse indicator:** $\mathbf 1_{\text{cell}}=\mathbf 1\{ \min_i y_i < T \}$.
* **Global-sparse indicator:** $ \mathbf 1_{\text{glob}}=\mathbf 1\{ Y < T \}$. (Equivalently $\tilde Y < T+\alpha D$.)

Then choose $w^{(\kappa)}$ and tag, in this exact priority:

1. **Global fallback (dominates everything):** if $\mathbf 1_{\text{glob}}=1$

   $$
   w^{(\kappa)}_i \leftarrow \frac{1}{D}\ \forall i,\qquad
   \texttt{smoothing}=\texttt{"equal_split_fallback"},\qquad
   \texttt{is_sparse}=\texttt{true}.
   $$

   Rationale: total evidence $Y$ is too small; discard profile. $\tilde Y < T+\alpha D\iff Y < T$ formalises the same gate.

2. **Otherwise, cell-driven choice (local smoothing):**

   * If $\mathbf 1_{\text{cell}}=1$: $w^{(\kappa)}\leftarrow\tilde w$, tag $\texttt{"alpha=0.5"}$.
   * Else: $w^{(\kappa)}\leftarrow\hat w$, tag $\texttt{null}$.
     In both cases, **is_sparse=false** (global fallback did not trigger).

**Semantics of the `sparse_flag`:** it reflects **only** the global fallback (equal-split) i.e., `is_sparse = (Y < T)`. Using $\tilde w$ alone does **not** set the flag.

---

## 4) Math properties (guarantees used by CI)

* **Convex decomposition of $\tilde w$** (for $D\ge2$):

  $$
  \tilde w_i \;=\; \underbrace{\frac{Y}{Y+\alpha D}}_{\text{data weight}}\hat w_i
  \;+\;
  \underbrace{\frac{\alpha D}{Y+\alpha D}}_{\text{prior weight}}\cdot \frac{1}{D},
  \quad\text{(interpret \(\hat w\) only if \(Y > 0\)).}
  $$

  Both coefficients are in $(0,1)$ and sum to 1; as $Y\downarrow0$, $\tilde w\to$ equal split; as $Y\uparrow\infty$, $\tilde w\to\hat w$.

* **Positivity and normalisation.** For all regimes selected above, $w^{(\kappa)}_i\in(0,1]$ and $\sum_i w^{(\kappa)}_i = 1$ analytically. S5.3 nevertheless **renormalises** in binary64 to remove rounding drift, then S5.4 enforces $|1-\sum_i w_i|\le 10^{-6}$ at read.

* **Edge-case safety.**

  * $Y=0, D\ge2$: $\mathbf 1_{\text{cell}}=1$ and $\mathbf 1_{\text{glob}}=1$ ⇒ equal-split path (no division by zero), `is_sparse=true`.
  * $D=1$: $w=1$ independent of $y_{i_1}$.
  * Mixed small/large cells with $Y\ge T$: smoothed $\tilde w$, `is_sparse=false`.

---

## 5) Language-agnostic reference algorithm (normative)

```text
INPUT (per currency κ, already ISO-ordered from S5.2):
  members[1..D] = [i_1,...,i_D]          # ASCII order
  counts[1..D]  = [y_{i_1},...,y_{i_D}]  # int64, y_i ≥ 0
  Y = Σ_i y_i                             # int64
  constants: α = 0.5, T = 30

OUTPUT (in-memory to S5.4 writers):
  rows_weights[1..D]: for each i_j → {currency=κ, country_iso=i_j,
                                      weight=w_j, obs_count=y_{i_j},
                                      smoothing ∈ {null,"alpha=0.5","equal_split_fallback"}}
  row_sparse: {currency=κ, is_sparse = (Y < T), obs_count=Y, threshold=T}

ALGORITHM:

0  assert D ≥ 1

A) if D == 1:
     w ← [1.0]
     smoothing ← [null]
     is_sparse ← false
     EMIT rows_weights, row_sparse
     STOP

B) # D ≥ 2
   # Compute candidate vectors (binary64)
   if Y > 0:
       hat_w[j] ← counts[j] / Y           for j=1..D
   else:
       hat_w[j] ← NaN                     for j=1..D  # unused if global fallback fires
   tilde_w[j] ← (counts[j] + α) / (Y + α·D)

   # Local sparsity:
   y_min ← min(counts)
   cell_sparse  ← (y_min < T)
   global_sparse ← (Y < T)                # ⇔ (Y + α·D) < (T + α·D)

   # Decision surface (priority: global > local)
   if global_sparse:
       w[j] ← 1.0 / D                     for j=1..D
       smoothing_tag[j] ← "equal_split_fallback"  for all j
       is_sparse ← true
   else if cell_sparse:
       w[j] ← tilde_w[j]                  for j=1..D
       smoothing_tag[j] ← "alpha=0.5"
       is_sparse ← false
   else:
       assert Y > 0                       # by construction of this branch
       w[j] ← hat_w[j]
       smoothing_tag[j] ← null
       is_sparse ← false

   # Renormalise to exact 1 (construction tolerance 1e-12)
   s ← Σ_j w[j]
   if |1 - s| > 1e-12:
       w[j] ← w[j] / s  for j=1..D

   # Emit (preserving the input ISO order)
   rows_weights ← [{κ, i_j, w[j], y_{i_j}, smoothing_tag[j]} for j=1..D]
   row_sparse   ← {κ, is_sparse, obs_count=Y, threshold=T}
   EMIT rows_weights, row_sparse
```

**Determinism:** No RNG; identical inputs and `parameter_hash` yield byte-identical outputs when S5.4 writes the caches pinned in the dictionary.

---

## 6) Tags, flags, and coherence rules (must hold downstream)

* **Weights cache tag (`smoothing`) per $(\kappa,i)$:**
  `null` for raw $\hat w$; `"alpha=0.5"` for smoothed $\tilde w$; `"equal_split_fallback"` *only* when $Y < T$.
* **Sparse flag dataset (`is_sparse`) per $\kappa$:**
  `true ⇔ (Y < T)`; must **agree** with tags (if `true`, *all* rows for that $\kappa$ must carry `"equal_split_fallback"`; if `false`, **none** may carry that tag). Violations are run-abort schema/semantic errors verified in S5.5/S5.6/S9.

---

## 7) Numerics & tolerances (binary64 discipline)

* **Renormalisation:** S5.3 rescales if $|1-\sum_i w_i| > 10^{-12}$; S5.4’s schema enforces $|1-\sum_i w_i|\le 10^{-6}$ on read.
* **Range & finiteness:** emit only finite $w_i\in[0,1]$. The global fallback ensures no division by zero; the raw branch asserts $Y > 0$.
* **Ordering:** preserve ASCII ISO order in all outputs to maintain downstream determinism.

---

## 8) Edge-case table (explicit outcomes)

| Situation                          | Decision    | Tag(s)                 | `is_sparse` |   |
| ---------------------------------- | ----------- | ---------------------- | ----------- | - |
| $D=1$, any $Y$                     | $w=[1]$     | `null`                 | `false`     |   |
| $D\ge2,\,Y=0$                      | Equal split | `equal_split_fallback` | `true`      |   |
| $D\ge2,\,Y < T$                      | Equal split | `equal_split_fallback` | `true`      |   |
| $D\ge2,\,Y\ge T,\,\min_i y_i < T$    | $\tilde w$  | `"alpha=0.5"`          | `false`     |   |
| $D\ge2,\,Y\ge T,\,\min_i y_i\ge T$ | $\hat w$    | `null`                 | `false`     |   |

---

## 9) What S5.4 will persist (declared targets)

S5.4 writes exactly two **parameter-scoped** caches with dictionary-pinned `schema_ref`/paths:

* `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/` with schema `schemas.1A.yaml#/prep/ccy_country_weights_cache` (PK `[currency,country_iso]`, ISO FK, **group_sum_equals_one**).
* `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/` with schema `schemas.1A.yaml#/prep/sparse_flag` (PK `[currency]`, `is_sparse=(Y < T)`).

---

## 10) Complexity

Per currency, O($D$) time and O($D$) memory; whole step linear in the number of $(\kappa,i)$ pairs. No network or RNG costs.

---

**Summary:** S5.3 turns $(\mathcal D(\kappa),\{y_i\},Y)$ into a **deterministic** $w^{(\kappa)}$ with a **single, prioritized decision surface** (global fallback $Y < T$ → equal split; else cell-driven $\tilde w$ vs $\hat w$); emits exact **tags** and **is_sparse** semantics; and preserves **ISO order** and **sum-to-1** numerics ready for S5.4 to persist under the dictionary contracts.

---

# S5.4 — Persistence (authoritative spec)

## 1) Purpose & placement

S5.3 already produced, per currency $\kappa$, the **final** ISO-ordered weights $w^{(\kappa)}$, their **smoothing tag** per destination, and the per-$\kappa$ **is_sparse** decision. S5.4 **materialises** these into two **parameter-scoped** caches, with no RNG anywhere in S5.

---

## 2) Datasets to write (and only these)

### A) `ccy_country_weights_cache` — per $(\kappa,i)$ weights

* **Dictionary entry:** `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/`
  **Partitioning:** `["parameter_hash"]` (no `seed`, no `run_id`).
  **Schema:** `schemas.1A.yaml#/prep/ccy_country_weights_cache`.
  **Role:** Deterministic currency→country weights; **group_sum_equals_one** per currency (tol $10^{-6}$).

**Row contract (one row per currency–country):**

```
manifest_fingerprint : hex64 (^[a-f0-9]{64}$)
currency            : ISO-4217 string (PK part 1)
country_iso         : ISO-3166 alpha-2 string (PK part 2; FK → ISO canonical)
weight              : pct01 ∈ [0,1] (finite)
obs_count           : int64 ≥ 0 (copied from ingress y_i)
smoothing           : enum {null, "alpha=0.5", "equal_split_fallback"}
```

**Primary key:** `["currency","country_iso"]`.
**Ordering within a currency:** strictly **ASCII sort by `country_iso`** (deterministic).

### B) `sparse_flag` — per-$\kappa$ sparsity decision

* **Dictionary entry:** `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/`
  **Partitioning:** `["parameter_hash"]`.
  **Schema:** `schemas.1A.yaml#/prep/sparse_flag`.
  **Semantics:** `is_sparse = (Y < T)`; *only* the **global equal-split fallback** sets this true.

**Row contract (one row per currency):**

```
manifest_fingerprint : hex64
currency             : ISO-4217 string (PK)
is_sparse            : boolean  (true ⇔ equal_split_fallback was taken)
obs_count            : int64 ≥ 0  (Y)
threshold            : int64 ≥ 0  (T)
```

**Primary key:** `["currency"]`.

**Lineage note.** Both tables store `manifest_fingerprint` as a **column** (run lineage), but only `parameter_hash` governs **partitioning/version**. For a fixed manifest + inputs, bytes are reproducible; across manifests, value columns are invariant while lineage may differ.

---

## 3) What must already hold coming from S5.3 (recap)

Per currency $\kappa$: members $(i_1,\dots,i_D)$ in ISO order; final $w^{(\kappa)}$ chosen by the S5.3 decision surface (global fallback if $Y < T$, else smoothed if $\min_i y_i < T$, else raw), with renormalisation to $\sum_i w=1$ to $10^{-12}$ tolerance, and tags consistent with the branch. `is_sparse = (Y < T)`.

---

## 4) Writer invariants & constraints (hard requirements)

* **Partition authority:** both datasets are **parameter-scoped**; paths must match dictionary patterns with *exactly* `{"parameter_hash"}` as partition keys. Any other partitioning is a breach.
* **Group sum constraint:** for each $\kappa$, stored weights must satisfy
  $\left|\sum_i w^{(\kappa)}_i-1\right|\le 10^{-6}$ (schema-checked). Writer should renormalise if $|1-\sum_i w| > 10^{-12}$ to leave headroom.
* **Ordering:** within each $\kappa$, rows are **ASCII-sorted by `country_iso`** on write. Readers must not sort; writers guarantee order.
* **Keys & FKs:** enforce PK uniqueness and FK to ISO canonical on `country_iso`.
* **No RNG:** S5 tables carry **no** RNG envelopes; presence would be a protocol failure.

---

## 5) Language-agnostic reference algorithm (normative writer)

This is the canonical, implementation-neutral procedure to write both caches atomically.

```text
ALGORITHM  S5_Write_CurrencyCaches  # language-agnostic, deterministic

INPUTS:
  - For each currency κ (from S5.3):
      members[1..D]   = [i_1,...,i_D]     # ASCII ISO order
      weights[1..D]   = [w_1,...,w_D]     # binary64, finite
      counts[1..D]    = [y_1,...,y_D]     # int64 ≥ 0
      Y               = Σ_j y_j           # int64 ≥ 0
      smoothing_tag[1..D] ∈ {null,"alpha=0.5","equal_split_fallback"} (homogeneous per κ)
      is_sparse       = (Y < T)
  - Constants (governed): α = 0.5, T = 30
  - Lineage: manifest_fingerprint (hex64), parameter_hash
  - Authorities: dataset dictionary & schema refs (paths below), ISO FK table

TARGETS (must match dictionary exactly):
  A_path := "data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/"
  B_path := "data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/"

PRE-OPEN VALIDATION:
  0. Assert partition key set == {"parameter_hash"} for both targets (dictionary authority).
  1. Prepare writers with Parquet + storage policy (e.g., ZSTD-3); compression does not affect semantics.

MAIN WRITE (streaming by currency κ):
  2. For each currency κ in any deterministic outer order:
     2.1 # Order & PK discipline
         assert members is ASCII-sorted and has no duplicate ISO; else FAIL F-S5/PERSIST/ORDERING or PK_DUP
     2.2 # Sum guard (binary64, fixed order)
         s ← Σ_j weights[j]   using fixed-order summation (e.g., Neumaier)
         if |1 - s| > 1e-12:
             weights[j] ← weights[j] / s     for all j
         s' ← Σ_j weights[j]; assert |1 - s'| ≤ 1e-6; else FAIL F-S5/PERSIST/SUM_CONSTRAINT
     2.3 # Coherence of tags & flag
         if is_sparse:
             assert all smoothing_tag[j] == "equal_split_fallback"
         else:
             assert not all smoothing_tag[j] == "equal_split_fallback"
         if violated → FAIL F-S5/PERSIST/SPARSE_FLAG_SEMANTICS
     2.4 # Emit weights rows (preserving ISO order)
         for j in 1..D:
            write A_row:
              { manifest_fingerprint,
                currency=κ, country_iso=members[j],
                weight=weights[j], obs_count=counts[j],
                smoothing=smoothing_tag[j] }
     2.5 # Emit per-κ sparse_flag row
         write B_row:
              { manifest_fingerprint, currency=κ,
                is_sparse=is_sparse, obs_count=Y, threshold=T }

POST-WRITE VALIDATION (schema/dictionary gates):
  3. Validate A (weights):
     - PK uniqueness on (currency,country_iso)
     - FK(country_iso) to ISO canonical
     - group_sum_equals_one per currency (≤ 1e-6)
     - weight is finite ∈ [0,1]; obs_count int64 ≥ 0; smoothing ∈ allowed set
     - manifest_fingerprint matches hex64 regex
  4. Validate B (sparse_flag):
     - PK uniqueness on (currency)
     - is_sparse boolean; obs_count, threshold int64 ≥ 0
  5. Validate partitions/paths against dictionary for both A and B
  6. If any step fails → ABORT run with the corresponding F-S5/PERSIST/* code; else SUCCESS

COMPLEXITY:
  - Time O(#(κ,i)) and memory streaming by κ; sum uses a single-thread, fixed-order reduction.
```

**Fixed-order sum (normative).** Use a single-thread compensated sum (e.g., Neumaier) over the ISO-ordered weights before renormalising; no BLAS/GPU/parallel reductions are allowed for this step to preserve determinism. Target $|\sum w - 1|\le 10^{-12}$ pre-persist; schema enforces $10^{-6}$.

---

## 6) Failure taxonomy (abort semantics; exhaustive)

* **F-S5/PERSIST/SUM_CONSTRAINT** — $|\sum_i w^{(\kappa)}_i - 1| > 10^{-6}$ for some $\kappa$ (schema group sum). **Action:** abort.
* **F-S5/PERSIST/PK_DUP** — duplicate PK in weights or sparse_flag. **Action:** abort.
* **F-S5/PERSIST/PARTITION_MISMATCH** — path/partition not exactly `{parameter_hash}` as per dictionary. **Action:** abort.
* **F-S5/PERSIST/ORDERING** — `country_iso` not ASCII-sorted within a currency. **Action:** abort.
* **F-S5/PERSIST/SPARSE_FLAG_SEMANTICS** — `is_sparse ≠ (Y < T)` **or** weights carry `"equal_split_fallback"` inconsistently with B. **Action:** abort.
* **Ingress/typing echoes (defensive):** FK failure on `country_iso`; non-integer/negative `obs_count`. (These should already be caught in S5.1/S5.2 but are repeated at persistence boundary.) **Action:** abort.

CI/validator will re-assert the same rules by reading the written partitions and cross-checking A↔B (sum, order, PK, flag semantics).

---

## 7) Storage & lineage details

* **Format:** Parquet; **compression:** e.g., ZSTD-3 per storage policy (value-transparent).
* **Versioning:** partitioned solely by `parameter_hash` (parameter-scoped caches).
* **Lineage fields:** persist `manifest_fingerprint` column in both tables (hex64). It does **not** affect partitions.

---

## 8) What S6 is entitled to assume

* For any merchant with settlement currency $\kappa_m$, S6 can load $\{(\kappa_m,i,w_i)\}$ in **ISO order**, sum $=1$ within $\le 10^{-6}$, and a single `sparse_flag` row with `is_sparse=(Y < T)`. It must then drop the home ISO, renormalise if needed, and draw Gumbel keys in that **stored ISO order**. Inter-country order is not encoded elsewhere.

---

## 9) Why this is complete & correct

This spec ties the **dictionary paths, partitions, schema refs, and constraints** directly to the writer’s steps, enforces **sum/order/flag** invariants exactly as S5.3 defines them, bans RNG and parallel reductions to preserve determinism, and provides a **single canonical algorithm** any implementation can follow to get CI-clean artefacts.

---

# S5.5 — Determinism & correctness invariants

## 1) What the validator sees (authoritative observables)

S5 persists exactly **two** parameter-scoped caches, both partitioned by `{parameter_hash}` and carrying a lineage column `manifest_fingerprint` (hex64):

1. **`ccy_country_weights_cache`** — one row per $(\kappa,i)$:
   `{manifest_fingerprint, currency=κ, country_iso=i, weight∈[0,1], obs_count=y_i≥0, smoothing∈{null,"alpha=0.5","equal_split_fallback"}}`,
   **schema** `schemas.1A.yaml#/prep/ccy_country_weights_cache`, **path** `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/…`. The schema enforces **group_sum_equals_one** per currency (tolerance $10^{-6}$).

2. **`sparse_flag`** — one row per $\kappa$:
   `{manifest_fingerprint, currency=κ, is_sparse∈{true,false}, obs_count=Y≥0, threshold=T≥0}`,
   **schema** `schemas.1A.yaml#/prep/sparse_flag`, **path** `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/…`. Semantics: `is_sparse ≡ (Y < T)` (global equal-split fallback).

Both paths/schemas are fixed by the **dataset dictionary** and the **artefact registry**; these caches are versioned by `parameter_hash` (parameter-scoped), *not* by seed/run.

---

## 2) Determinism & lineage invariants

### I-W1 — No RNG (protocol)

S5 performs **no random draws** and emits **no RNG event streams**. Neither table may contain RNG envelope fields; no S5 paths use `{seed}` or `{run_id}`. Any RNG presence is a protocol breach.

### I-W1.1 — Replay semantics

For **fixed** inputs and a **fixed** `manifest_fingerprint`, the persisted bytes are reproducible. Across different manifests (e.g., code/config updates), **value columns** (`weight`, `is_sparse`, `obs_count`, `threshold`) are invariant given the same inputs and `parameter_hash`; lineage columns may differ.

### I-W1.2 — Partition authority

Each table’s partition key set is **exactly** `{parameter_hash}` (no extra partition columns); the physical path prefix must equal the dictionary entry verbatim.

---

## 3) Schema, keys, FK & coverage invariants

### I-W2 — Schema conformance

Every stored row must pass the declared **schema_ref** (types, required fields, `manifest_fingerprint` hex64 regex), and **`country_iso`** must **FK**-join the ISO-3166 canonical table. Violations are run-stopping schema errors.

### I-W3 — Primary-key uniqueness

* `ccy_country_weights_cache`: unique **(currency, country_iso)**.
* `sparse_flag`: unique **(currency)**.
  Duplicates are fatal schema errors.

### I-W4 — Currency coverage & cross-table coherence

Let $\mathcal{K}$ be the set of currencies present in `ccy_country_shares_2024Q4`. Then:

* For each $\kappa\in\mathcal{K}$: **at least one** weights row exists and **exactly one** `sparse_flag` row exists.
* If weights exist for $\kappa$, then $\kappa \in \mathcal{K}$.
* The set of `country_iso` in weights for $\kappa$ equals the ingress member set $\mathcal{D}(\kappa)$.
* All weights rows for $\kappa$ are in **ASCII ISO order** by `country_iso` (see I-W6).

---

## 4) Numeric invariants (sums, ranges, construction discipline)

### I-W5 — Sum-to-one (per currency)

For each $\kappa$,

$$
\left|\sum_{i\in\mathcal{D}(\kappa)} w^{(\kappa)}_i - 1\right|\le 10^{-6}\quad\text{(schema-enforced)}.
$$

Writers must renormalise with a fixed-order compensated sum (e.g., Neumaier) to $\le 10^{-12}$ internally before persist; CI asserts the $10^{-6}$ gate on read. **No BLAS/GPU/parallel reductions** for this sum to preserve determinism.

### I-W5.1 — Range & finiteness

Each persisted `weight` is **finite** and in $[0,1]$. For $D{=}1$: the single row has `weight=1`. For equal-split fallback: every row has `weight=1/D` within numeric tolerance.

### I-W5.2 — Constructive definitions (for audit)

Weights must be realisations of the S5.3 decision surface:

$$
w^{(\kappa)}=
\begin{cases}
\text{equal}(D), & Y < T,\\
\tilde w, & Y\ge T\ \text{and}\ \min_i y_i < T,\\
\hat w, & Y\ge T\ \text{and}\ \min_i y_i \ge T,
\end{cases}
\quad
\tilde w_i=\dfrac{y_i+\alpha}{Y+\alpha D},\ \hat w_i=\dfrac{y_i}{Y},
$$

with $\alpha=0.5,\ T=30$. CI may recompute these from ingress to cross-check value-level determinism.

---

## 5) Ordering, tags & flag semantics

### I-W6 — ISO ordering (row order is part of the contract)

For a given $\kappa$, the weights rows must be **sorted by `country_iso` (ASCII)**. Readers and S6 rely on this order to align deterministic Gumbel keys to destinations. Out-of-order storage is a fatal ordering breach.

### I-W7 — Smoothing tag semantics (row-level)

Each weights row carries:

* `smoothing = null` **iff** branch used raw $\hat w$.
* `smoothing = "alpha=0.5"` **iff** branch used smoothed $\tilde w$ (cell-sparse condition $\min_i y_i < T$ and $Y\ge T$).
* `smoothing = "equal_split_fallback"` **iff** global fallback fired ($Y < T$).
  A currency’s rows must be **homogeneously** tagged (same tag for all rows of that $\kappa$).

### I-W8 — Sparse flag semantics (table-level)

`sparse_flag.is_sparse` is **true iff $Y < T$** (global fallback) and **false otherwise**. Using smoothed $\tilde w$ *alone* never sets `is_sparse=true`. Cross-table coherence must hold:

* If `is_sparse=true`, **all** weights rows for that $\kappa$ must have `smoothing="equal_split_fallback"`.
* If any weights row has `smoothing="equal_split_fallback"`, then `is_sparse=true`.

---

## 6) Validator procedure (language-agnostic, normative)

**Inputs:** the two S5 tables (current `{parameter_hash}` partition), ingress `ccy_country_shares_2024Q4` (for $\mathcal{D}(\kappa)$, $y_i$, $Y$), ISO canonical, constants $\alpha=0.5,\ T=30$. **Outputs:** pass/fail and failing codes (mapped in S5.6).

**Steps:**

1. **Dictionary/partition gate.** Confirm each table exists exactly under the dictionary path and partition key set `{parameter_hash}`; else **partition/layout** failure.

2. **Schema gate.** Enforce schema refs: required columns, types, `manifest_fingerprint` hex64, weight pct01, `obs_count` int64≥0, FK(country_iso) to ISO, PK uniqueness. Else **schema** failure.

3. **Group & order.** For each $\kappa$: collect weights rows; assert **strict ASCII ordering** by `country_iso`. Else **ordering** failure.

4. **Coverage coherence.** For each $\kappa$ present in ingress:

   * assert one `sparse_flag` row;
   * assert weights entries cover exactly $\mathcal{D}(\kappa)$ (no extras/missing);
   * assert `obs_count` on each row equals ingress $y_i$ (value equality).
     Else **coverage/FK** failure.

5. **Sum constraint.** For each $\kappa$: compute $S=\sum_i w_i$ (single-thread, fixed ISO order; compensated). Assert $|S-1|\le 10^{-6}$. Else **sum** failure.

6. **Range/finiteness.** Assert all `weight` finite in $[0,1]$. If $D{=}1$, assert `weight=1`. Else **range** failure.

7. **Tag coherence.** For each $\kappa$, assert **homogeneous** `smoothing` tag over its rows; value must be one of {null, "alpha=0.5", "equal_split_fallback"}. Else **tag** failure.

8. **Flag coherence.** Join with `sparse_flag` and assert I-W8. Else **flag semantics** failure.

9. **Value determinism (optional strength test).** Recompute $Y=\sum_i y_i$, $y_{\min}$, then the chosen branch and target vector ($\hat w,\tilde w$, or equal). Confirm each stored `weight` equals the target within $10^{-9}$ (or recompute then re-normalise to match the writer’s rule). Mismatches are **value drift** failures.

10. **Exit.** If all checks pass, mark S5 **valid** for this `{parameter_hash}`. Otherwise, emit deterministic error codes (enumerated in S5.6).

---

## 7) Why these invariants are sufficient (soundness)

* **No RNG, parameter-scoped partitioning** ensures S5 caches are **pure functions** of ingress + fixed $(\alpha,T)$ and replayable independent of run seed/state.
* **Schema/PK/FK/order** guarantees make the caches **join-safe** and **stable** for S6’s Gumbel alignment (ordering is explicit, not incidental).
* **Sum, range, and constructive definitions** guarantee weights are well-formed probability vectors and auditable back to ingress counts and the S5.3 decision surface.
* **Tag/flag semantics** tie row-level annotations to the mathematical branch taken and expose the global fallback explicitly to diagnostics and S6.

---

## 8) Edge-case matrix (validator is required to pass/fail accordingly)

| Situation                                                                    | Must hold / Validator action                                                                                       |
|------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| $D=1$ currency                                                               | Exactly one row with `weight=1`, `smoothing=null`; `sparse_flag.is_sparse=false`. Else **range/tag/flag** failure. |
| $D\ge2, Y=0$                                                                 | Weights equal-split, all `smoothing="equal_split_fallback"`, `is_sparse=true`. Else **flag/tag/value** failure.    |
| $D\ge2, Y\ge T, \min y_i < T$                                                | Weights = $\tilde w$, tags `"alpha=0.5"`, `is_sparse=false`. Else **tag/value** failure.                           |
| $D\ge2, Y\ge T, \min y_i\ge T$                                               | Weights = $\hat w$, tags `null`, `is_sparse=false`. Else **tag/value** failure.                                    |
| Any currency missing in `sparse_flag` but present in weights (or vice-versa) | **Coverage** failure (run abort).                                                                                  |
| Weights not sorted by ISO within $\kappa$                                    | **Ordering** failure (run abort).                                                                                  |
| $(\sum w - 1 > 10^{-6})$                                                     | **Sum** failure (run abort).                                                                                       |

---

# S5.6 — Failure taxonomy & CI error codes (authoritative)

## 1) Observables and authority surface

Validator reads (for a single `{parameter_hash}`):

* **Ingress references (read-only):**
  `ccy_country_shares_2024Q4` defining $(\kappa,i,y_i)$, total $Y=\sum_i y_i$, and the member set $\mathcal D(\kappa)$; FK authority is **ISO-3166 canonical**.
* **S5 outputs (parameter-scoped; must exist exactly at these paths):**
  `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/` with schema `schemas.1A.yaml#/prep/ccy_country_weights_cache` (**group_sum_equals_one** per currency, tol $10^{-6}$); and
  `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/` with schema `#/prep/sparse_flag`. Both tables carry `manifest_fingerprint` as a *column* but are **partitioned solely by `{parameter_hash}`**.
* **Governed constants:** $\alpha=0.5,\; T=30$. (Used by S5.3 decision surface and to interpret `is_sparse`.)

S5 contains **no RNG**; any RNG presence is a protocol breach.

---

## 2) Error code format

```
err_code := "E/1A/S5/<CLASS>/<DETAIL>"
```

Examples:
`E/1A/S5/INGRESS/ISO_FK`, `E/1A/S5/PARAMS/OUT_OF_DOMAIN`,
`E/1A/S5/DECISION/GLOBAL_FLAG_MISMATCH`, `E/1A/S5/PERSIST/SUM_CONSTRAINT`,
`E/1A/S5/PERSIST/PARTITION_MISMATCH`, `E/1A/S5/ORDER/ISO_ASCII`.
Codes are **stable** and appear in the run’s validation bundle with `{currency, country_iso?}` and minimal reproducer stats (e.g., $Y$, $\min y_i$, observed tag).

---

## 3) Failure classes (exhaustive)

### A) Ingress / reference integrity

| Code                             | Precise trigger                                                                                                                           | Scope   | Action  |
| -------------------------------- |-------------------------------------------------------------------------------------------------------------------------------------------| ------- | ------- |
| `E/1A/S5/INGRESS/ISO_FK`         | Any output row’s `country_iso` fails FK join to ISO canonical **or** ingress has a $(\kappa,i)$ not in ISO (CI checks both).              | **Run** | Abort.  |
| `E/1A/S5/INGRESS/DUP_KEY`        | Duplicate $(\kappa,i)$ in ingress `ccy_country_shares_2024Q4`.                                                                            | **Run** | Abort.  |
| `E/1A/S5/INGRESS/COUNTS_INVALID` | Any $y_i$ non-integer or $y_i < 0$.                                                                                                       | **Run** | Abort.  |
| `E/1A/S5/INGRESS/MISSING_ROWS`   | A currency $\kappa$ present in outputs has weights whose `country_iso` set differs from the ingress $\mathcal D(\kappa)$ (missing/extra). | **Run** | Abort.  |

### B) Parameter/config sanity

| Code                           | Precise trigger                                        | Scope   | Action  |
| ------------------------------ |--------------------------------------------------------| ------- | ------- |
| `E/1A/S5/PARAMS/OUT_OF_DOMAIN` | $\alpha\le0$ **or** $T < 0$ in `ccy_smoothing_params`. | **Run** | Abort.  |

### C) Decision-surface / construction coherence (math semantics)

These compare **stored outputs** to the *unique* S5.3 decision surface:

* Global fallback iff $Y < T$ (equiv. $\tilde Y < T+\alpha D$);
* Else smoothed $\tilde w$ iff $\min_i y_i < T$;
* Else raw $\hat w$;
* $D=1$ forces $w=1$, `smoothing=null`, `is_sparse=false`.

| Code                                     | Precise trigger                                                                                                                                                     | Scope   | Action |
|------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|--------|
| `E/1A/S5/DECISION/GLOBAL_FLAG_MISMATCH`  | `sparse_flag.is_sparse ≠ [Y<T]` for currency $\kappa$.                                                                                                              | **Run** | Abort. |
| `E/1A/S5/DECISION/TAG_GLOBAL_INCOHERENT` | Some weight rows for $\kappa$ carry `smoothing="equal_split_fallback"` but `is_sparse=false` **or** none carry that tag while `is_sparse=true`.                     | **Run** | Abort. |
| `E/1A/S5/DECISION/TAG_LOCAL_INCOHERENT`  | $Y\ge T$ and $\min_i y_i < T$ but `smoothing≠"alpha=0.5"`, **or** $Y\ge T$ and $\min_i y_i\ge T$ but `smoothing≠null`. (All rows for $\kappa$ must be homogeneous.) | **Run** | Abort. |
| `E/1A/S5/DECISION/D1_BREACH`             | $D=1$ currency not stored as a single row with `weight=1` and `smoothing=null`, or flag not `false`.                                                                | **Run** | Abort. |
| `E/1A/S5/DECISION/OBS_COUNT_MISMATCH`    | For any $(\kappa,i)$: stored `obs_count ≠ y_i` from ingress.                                                                                                        | **Run** | Abort. |

### D) Ordering / layout / persistence

| Code                                 | Precise trigger                                                                                                        | Scope   | Action |
|--------------------------------------|------------------------------------------------------------------------------------------------------------------------|---------|--------|
| `E/1A/S5/ORDER/ISO_ASCII`            | For some $\kappa$, `ccy_country_weights_cache` rows are not strictly **ASCII-sorted by `country_iso`**.                | **Run** | Abort. |
| `E/1A/S5/PERSIST/PARTITION_MISMATCH` | Output paths/partition keys differ from dictionary (must be **`{parameter_hash}`** only).                              | **Run** | Abort. |
| `E/1A/S5/PERSIST/PK_DUP`             | Duplicate PK in weights $(\kappa,i)$ **or** duplicate $\kappa$ in `sparse_flag`.                                       | **Run** | Abort. |
| `E/1A/S5/PERSIST/SUM_CONSTRAINT`     | For some $\kappa$, $(\sum_i w^{(\kappa)}_i - 1 > 10^{-6})$ (schema `group_sum_equals_one`).                          | **Run** | Abort. |
| `E/1A/S5/PERSIST/SCHEMA`             | Any schema field/type/regex violation (e.g., `manifest_fingerprint` not hex64; `weight` non-finite or out of $[0,1]$). | **Run** | Abort. |

### E) Protocol

| Code                           | Precise trigger                                                                                     | Scope   | Action |
|--------------------------------|-----------------------------------------------------------------------------------------------------|---------|--------|
| `E/1A/S5/PROTOCOL/RNG_PRESENT` | Any RNG envelope or event stream detected for S5 (S5 is deterministic and must not consume Philox). | **Run** | Abort. |

---

## 4) Cross-table coherence rules (must all hold)

For each $\kappa$:

1. **Coverage parity:** the set of `country_iso` in weights equals ingress $\mathcal D(\kappa)$; exactly one `sparse_flag` row exists.
2. **Tag ↔ flag:** `is_sparse = [Y<T]` and iff true then **all** weights rows have `"equal_split_fallback"`. If false, **none** may have that tag. Smoothed (`"alpha=0.5"`) never sets `is_sparse`.
3. **Ordering:** rows for $\kappa$ appear in ASCII order of ISO codes (writers must ensure; validators assert).

---

## 5) Language-agnostic validator (emits codes)

**Input:** current `{parameter_hash}` partitions of the two S5 tables, ingress `ccy_country_shares_2024Q4`, ISO canonical; constants $\alpha=0.5,\;T=30$.
**Output:** pass/fail + list of `E/1A/S5/...` codes with examples.

**Procedure (deterministic):**

1. **Dictionary/partition gate.** Paths/keys equal dictionary (**`{parameter_hash}`** only) → else `PERSIST/PARTITION_MISMATCH`.
2. **Schema+PK+FK gate.** Apply the two schemas; enforce PK uniqueness and FK(country_iso) to ISO; hex64 `manifest_fingerprint`; weight pct01 finite → else `PERSIST/SCHEMA` or `PERSIST/PK_DUP` or `INGRESS/ISO_FK`.
3. **Group by currency $\kappa$.**

   * **Coverage:** weights’ ISO set equals ingress $\mathcal D(\kappa)$, and exactly one `sparse_flag` row exists → else `INGRESS/MISSING_ROWS`.
   * **Order:** assert ASCII order in weights → else `ORDER/ISO_ASCII`.
   * **Sum constraint:** compensated sum $S=\sum_i w_i$; assert $|S-1|\le10^{-6}$ → else `PERSIST/SUM_CONSTRAINT`.
   * **Obs counts:** per-row `obs_count == y_i` from ingress → else `DECISION/OBS_COUNT_MISMATCH`.
   * **Branch maths:** compute $D, Y, y_{\min}$.
     *If $D=1$* → assert single row, `weight=1`, `smoothing=null`, `is_sparse=false` → else `DECISION/D1_BREACH`.
     *If $D\ge2$* → derive booleans: `global = [Y<T]`, `cell = [\min y_i<T]`.
     • Assert `is_sparse==global` → else `DECISION/GLOBAL_FLAG_MISMATCH`.
     • If `global` → all rows `smoothing="equal_split_fallback"` and weights equal-split (within $10^{-9}$) → else `DECISION/TAG_GLOBAL_INCOHERENT`.
     • If `!global && cell` → all rows `smoothing="alpha=0.5"` **and** weights equal $\tilde w_i=(y_i+\alpha)/(Y+\alpha D)$ (within $10^{-9}$) → else `DECISION/TAG_LOCAL_INCOHERENT`.
     • If `!global && !cell` → all rows `smoothing=null` **and** weights equal $\hat w_i=y_i/Y$ (within $10^{-9}$) → else `DECISION/TAG_LOCAL_INCOHERENT`.
4. **Protocol check:** assert **no RNG** artefacts exist for S5 (no event logs; no seed/run-scoped outputs) → else `PROTOCOL/RNG_PRESENT`.

On first violation, **abort** with the specific code; CI may optionally accumulate all codes for triage.

---

## 6) Canonical examples (deterministic reproducer)

* **Global fallback mis-tag:** $D=3,\;Y=0$. Expected: weights $=(1/3,1/3,1/3)$, all `smoothing="equal_split_fallback"`, `is_sparse=true`. If stored as smoothed $\tilde w$ with tag `"alpha=0.5"` → `DECISION/GLOBAL_FLAG_MISMATCH` **and** `DECISION/TAG_GLOBAL_INCOHERENT`.
* **Local smoothing mis-tag:** $D=4,\;Y=200,\;\min y_i=5 < T$. Expected tag `"alpha=0.5"` with $\tilde w$. If tag `null` or values match $\hat w$ → `DECISION/TAG_LOCAL_INCOHERENT`.
* **Ordering breach:** weights rows for $\kappa$ appear as `["ZA","AE","BE"]` instead of ASCII order `["AE","BE","ZA"]` → `ORDER/ISO_ASCII`.
* **Sum failure:** any $\kappa$ where stored weights sum $= 1.000002$ → `PERSIST/SUM_CONSTRAINT`.

---

## 7) Why this taxonomy is complete

It covers **all observable invariants**: dictionary paths & **parameter-scoped** partitioning, **schema/PK/FK**, **ordering**, **sum constraint**, and the **mathematical decision surface** (global fallback vs smoothed vs raw), plus degenerate $D=1$ and the protocol’s *no-RNG* rule. Each code maps to a *single falsifiable predicate* over the persisted caches and ingress, matching the locked S5/S5.4/S5.5 contracts.

---

# S5.7 — State boundary (authoritative)

## 1) Upstream prerequisites (must already hold)

* **Branch & count:** For merchant $m$, S3 fixed eligibility $e_m\in\{0,1\}$. If $e_m=1$ and the ZTP loop in **S4** accepted, S4 exposes the scalar $K_m\in\{1,2,\dots\}$. If S4 exhausted retries, either the merchant is aborted or downgraded to domestic-only (policy), and S5/S6 are skipped for that merchant.
* **Merchant currency:** S5.0 has already persisted `merchant_currency` (parameter-scoped), the *only* authority for $\kappa_m$ used by S6. S5 must not recompute currencies.

These gates are **preconditions**; S5 runs deterministically and produces parameter-scoped caches regardless of which merchants proceed in S6.

---

## 2) Inputs consumed by S5 (deterministic, read-only)

* `ccy_country_shares_2024Q4` (ingress; rows $(\kappa,i,y_i)$) — defines $\mathcal D(\kappa)$ and observation counts; FK $i$ → ISO canonical. Schema: `schemas.ingress.layer1.yaml#/ccy_country_shares`.
* **ISO-3166 canonical** — primary-key + ordering authority for `country_iso`. (Used to enforce FK and the ASCII sort order within each $\kappa$.)
* **Governed constants:** $\alpha=0.5,\;T=30$ (fixed hyperparameters used by S5.3 to choose between raw $\hat w$, smoothed $\tilde w$, or equal-split fallback).
* (Context only) `settlement_shares_2024Q4` at currency level; governs wider assembly, not intra-currency normalisation.

S5 ingests **no RNG** events; any such presence would be a protocol breach.

---

## 3) Outputs materialised by S5 (and only these)

S5 persists two **parameter-scoped** caches, partitioned solely by `{parameter_hash}`; `manifest_fingerprint` is lineage only (a column), not a partition key. Paths and schema refs are **dictionary-fixed**:

1. **Weights cache**
   `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/…`
   Schema: `schemas.1A.yaml#/prep/ccy_country_weights_cache`.
   Rows: one per $(\kappa,i)$ with `{currency=κ, country_iso=i, weight∈[0,1], obs_count=y_i, smoothing∈{null,"alpha=0.5","equal_split_fallback"}, manifest_fingerprint}`.
   Constraints: **PK** `(currency,country_iso)`; **FK** `country_iso` → ISO; **group_sum_equals_one** per $\kappa$ with tolerance $10^{-6}$; rows **sorted by `country_iso` (ASCII)** for each $\kappa$.

2. **Sparse flag**
   `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/…`
   Schema: `schemas.1A.yaml#/prep/sparse_flag`.
   One row per $\kappa$: `{currency=κ, is_sparse = (Y<T), obs_count=Y, threshold=T, manifest_fingerprint}`; **PK** `(currency)`.
   Semantics: `is_sparse` is **true iff** S5 used **equal-split fallback** because $Y < T$. Smoothing alone (`"alpha=0.5"`) does **not** set `is_sparse`.

S5 writes **no** seed/run-scoped artefacts and **no** RNG event streams.

---

## 4) Mathematical contract of what’s inside the weights cache

For each currency $\kappa$ with member set $\mathcal D(\kappa)=\{i_1,\dots,i_D\}$ and counts $y_i\ge0$, total $Y=\sum_i y_i$, S5.3 deterministically chooses:

$$
w^{(\kappa)} \;=\;
\begin{cases}
\text{equal split}\ (1/D,\dots,1/D), & Y < T,\\[2pt]
\tilde w\ \text{with}\ \tilde w_i=\dfrac{y_i+\alpha}{Y+\alpha D}, & Y\ge T\ \&\ \min_i y_i < T,\\[10pt]
\hat w\ \text{with}\ \hat w_i=\dfrac{y_i}{Y}, & Y\ge T\ \&\ \min_i y_i\ge T,
\end{cases}
\quad \alpha=0.5,\;T=30,
$$

then renormalises in binary64 to $\sum_i w^{(\kappa)}_i=1$ (tolerance $10^{-12}$ pre-persist; schema gate $10^{-6}$). Rows are persisted in **ISO ASCII order** by `country_iso`.

Downstream consumers must treat this cache as **authoritative** for $\kappa\mapsto\{(i,w_i)\}$.

---

## 5) Downstream contract to **S6** (precise usage)

Given a merchant $m$ that will enter S6 (i.e., did not get downgraded or aborted in S4):

1. **Resolve currency:** read $\kappa_m$ from `merchant_currency` (parameter-scoped). **Do not recompute.**
2. **Load prior weights:** read $\{(\kappa_m,i,w_i)\}$ from `ccy_country_weights_cache` for that `{parameter_hash}` in **stored ISO order**; validate $\sum_i w_i=1$ (schema already enforces).
3. **Form foreign candidate set:** let $c$ be the merchant’s home ISO; define $\mathcal F_m=\mathcal D(\kappa_m)\setminus\{c\}$ with **preserved order** (drop the home row if present). Compute $M_m=|\mathcal F_m|$.
4. **Cap the draw size for selection:** $K_m^\star=\min(K_m,M_m)$. If $M_m=0$, set $K_m^\star=0$ and **persist** `country_set` with only the home row (`rank=0`), emit **no** `gumbel_key`, then proceed to S7 (reason `"no_candidates"`).
5. **Renormalise on the foreign set (before sampling):**

    $$
    \tilde w_i \;=\; \frac{w_i}{\sum_{j\in\mathcal F_m} w_j}\quad \text{for } i\in\mathcal F_m,
    $$

    using a single-thread fixed-order sum in the cache’s ISO order; assert $\sum_{i\in\mathcal F_m}\tilde w_i=1$ (within $10^{-12}$). These $\tilde w$ drive the **Gumbel-top-$K_m^\star$** selection in S6.
6.  **RNG usage begins in S6:** S6 logs exactly $M_m$ `gumbel_key` events (one per candidate) and persists `country_set` (home `rank=0` + selected foreigns `rank=1..K_m^\star`) **in the same order** as the winners’ selection order. `country_set` is the **only** authority for cross-country order in later states.

---

## 6) Cross-table coherence required at the boundary

* For each currency $\kappa$ present in the weights cache, there is **exactly one** `sparse_flag` row, and the set of `country_iso` equals ingress $\mathcal D(\kappa)$. Weights rows are in ASCII ISO order.
* `is_sparse = (Y<T)` in `sparse_flag` **iff** all weights rows for $\kappa$ carry `smoothing="equal_split_fallback"`. Using `"alpha=0.5"` alone never sets `is_sparse`.
* S6 must fail fast if `ccy_country_weights_cache` has **no** rows for $\kappa_m$ (input precondition to selection).

---

## 7) Determinism, partitions, and lineage at the boundary

* **Determinism:** For fixed ingress + $(\alpha,T)$ and a fixed `parameter_hash`, S5 outputs are *pure functions*—byte-replayable across re-runs (lineage columns may differ only with manifest changes). No seed/run partitions exist in S5.
* **Partitions & schema authority:** Both caches are under dictionary-pinned paths, partitioned **only** by `{parameter_hash}`; schemas enforce PKs, FKs, group-sum, and field domains. Any deviation is a run-stopping persistence/layout error.

---

## 8) Minimal boundary APIs (language-agnostic)

These are the normative interfaces S6—and any validator—may assume exist over the S5 artefacts.

```text
FUNCTION S5_get_weights(parameter_hash, κ) -> OrderedList[(i, w_i, smoothing, y_i)]
  Pre: κ ∈ currencies present in weights_cache(parameter_hash)
  Post: returns rows in ASCII ISO order; Σ w_i = 1 within 1e-6; |rows| = |D(κ)|

FUNCTION S5_get_sparse_flag(parameter_hash, κ) -> (is_sparse: bool, Y: int64, T: int64)
  Post: is_sparse == (Y < T)

FUNCTION S5_boundary_for_merchant(parameter_hash, merchant_id, home_iso, κ_m, K_m)
  W := S5_get_weights(parameter_hash, κ_m)
  F := [ (i, w) ∈ W where i ≠ home_iso ]                # preserve order
  M := |F|
  K* := min(K_m, M)
  if M == 0:
      return {K_star=0, foreign_candidates=[], prior_weights=[], reason="no_candidates"}
  else:
      let S := Σ_{(i,w)∈F} w  (fixed-order sum)
      return {K_star=K*, foreign_candidates=[i for (i,_)∈F], prior_weights=[w/S for ( _,w)∈F]}
```

These APIs are *purely deterministic* and never read `seed` or `run_id`. S6 will use the returned `foreign_candidates` order and `prior_weights` to log `gumbel_key` and to emit the ordered `country_set`.

---

## 9) What S5 does **not** do at this boundary

* It does **not** use RNG or write any seed/run-scoped stream—RNG resumes in S6 with `gumbel_key`.
* It does **not** drop the home ISO itself; that exclusion happens as the **first step in S6** (pre-screen/cap).
* It does **not** persist `country_set`; that dataset is **authoritatively materialised by S6** for **all** merchants reaching S3 (home-only for domestic/downgraded, or home + $K_m^\star$ foreigns).

---

### One-line takeaway

S5’s state boundary is two **parameter-scoped, schema-governed** caches—`ccy_country_weights_cache` and `sparse_flag`—that deterministically map any currency $\kappa$ to an **ISO-ordered, sum-to-1** prior over destination countries and a **global-sparsity flag**. S6 reads $\kappa_m$ from `merchant_currency`, drops home, renormalises on the foreign set, caps by $K_m$, and then *begins* RNG with Gumbel-top-$K$, persisting the authoritative `country_set`.

---