# S6.0 — Pre-screen / cap with candidate size $M_m$

## 1) Purpose & placement

S6.0 sits at the front of S6. Its sole job is to:

1. compute the **foreign candidate count** $M_m$ for merchant $m$ (home excluded),
2. set the **effective selection size** $K_m^\star=\min(K_m,M_m)$, and
3. short-circuit to a **home-only** allocation if there is no selectable foreign mass (details below), then hand off to S7.

It **does not** draw randomness, score keys, or persist foreign winners; that happens in later S6 steps. `country_set` is the *only* authority for cross-country order, and **S6 authors it** (including the home-only row in this sub-state).

---

## 2) Inputs (deterministic, read-only)

Per merchant $m$:

* **Foreign target from S4:** $K_{\text{raw}} \equiv K_m \in \{1,2,\dots\}$ (accepted ZTP count). S4 may also downgrade/abort merchants, which skip S6 entirely.
* **Home ISO:** $c \in \mathcal I$ (ISO-3166 alpha-2, **UPPER-CASE ASCII**), from normalised ingress.
* **Settlement currency:** $\kappa_m\in\mathrm{ISO4217}$ (read from `merchant_currency`, fixed in S5.0).
* **Currency→country prior weights (from S5 cache; ISO-sorted):** rows $\{(\kappa_m,i,w_i^{(\kappa_m)}): i \in \mathcal D(\kappa_m)\}$ with $\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}=1$ by construction.

> S6.0 only *reads* the S5 cache to know which destinations exist for $\kappa_m$ and to check foreign mass availability. Normalisation and RNG happen after S6.0.

---

## 3) Mathematical definitions

Using the ISO-ordered S5 expansion $\mathcal D(\kappa_m)\subset\mathcal I$:

1. **Foreign candidate set (home excluded):**

$$
\boxed{\, \mathcal F_m \;=\; \mathcal D(\kappa_m)\setminus\{c\}\, } \quad\text{(ISO order preserved)}
$$

2. **Available candidate count:**

$$
\boxed{\, M_m \;=\; |\mathcal F_m| \,}
$$

3. **Foreign-mass availability (guard):**
   Let $T_m := \sum_{j\in\mathcal F_m} w^{(\kappa_m)}_j$.

* If $M_m=0$ **or** $T_m=0$ (all foreign weights are zero), there is **no selectable foreign mass**.

4. **Effective selection size (cap):**

$$
\boxed{\, K_m^\star \;=\; \min\!\big(K_{\text{raw}},\;M_m\big)\, }
$$

**Branch rule.**

* If $M_m=0$ **or** $T_m=0$: set $K_m^\star=0$, write **home-only** `country_set` (`rank=0`), **emit no `gumbel_key`**, record reason `"no_candidates"`, then jump to S7.
* Else: proceed with $K_m^\star$ (validators assert $0\le K_m^\star\le M_m$).

*Corner notes (for later S6 steps):* if $K_m^\star=M_m$ then **all** candidates will be selected downstream (still ordered 1..$M_m$); if $M_m=1$ the downstream will emit exactly one `gumbel_key` and the sole foreign receives `rank=1`.

---

## 4) What is (and isn’t) persisted in S6.0

### Home-only short-circuit (when $M_m=0$ **or** $T_m=0$)

Persist exactly one row to **`country_set`** and **no RNG events**:

**Dataset & partitions (dictionary-pinned):**

```
data/layer1/1A/country_set/
  seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/part-*.parquet
```

*(Partitioned by `{seed, parameter_hash, fingerprint}`. `run_id` applies to event logs, not allocations.)*

**Row (authoritative schema semantics):**

```
merchant_id   = m
country_iso   = c           # home ISO (UPPER-CASE ASCII)
is_home       = true
rank          = 0
prior_weight  = null        # home has no prior weight
manifest_fingerprint = {manifest_fingerprint}   # carried as a column
```

**PK** = `(merchant_id, country_iso)`. `country_set` is the *sole* authority for cross-country order (**S6 authors it**).

> *Optional telemetry (no RNG):* emit a single `gumbel_header` with
> `{merchant_id, K_raw, M=M_m, K_eff=0, reason="no_candidates"}`.

### Non-short-circuit case (when $M_m\ge1$ **and** $T_m>0$)

S6.0 **persists nothing** else here. It only computes and exposes $(\mathcal F_m, K_m^\star)$ to S6.3–S6.6 (which will later log `gumbel_key` and persist the full `country_set`).

---

## 5) Contracts & invariants established by S6.0

* **C-1 (cap correctness):** $0 \le K_m^\star \le M_m$ and $K_m^\star=\min(K_{\text{raw}},M_m)$ for every merchant reaching S6.0.
* **C-2 (home-only correctness):** $(M_m=0\ \text{or}\ T_m=0)\ \iff$ exactly one `country_set` row exists with `(is_home=true, rank=0, prior_weight=null)` and **no `gumbel_key` events** for $m$.
* **C-3 (no RNG):** S6.0 consumes and emits **no** randomness. RNG begins only if $K_m^\star\ge1$ (later S6 steps).
* **C-4 (authority flow):** `country_set` remains the **only** authority for cross-country order; even when home-only, rank semantics are enforced (`rank=0` only).

---

## 6) Edge cases & notes

* **Home not in $\mathcal D(\kappa_m)$:** Then $\mathcal F_m = \mathcal D(\kappa_m)$ and $M_m = |\mathcal D(\kappa_m)|$. This is allowed; guard on $T_m$ still applies.
* **Currency with one member equal to home:** $\mathcal D(\kappa_m)=\{c\}\Rightarrow M_m=0$ → home-only branch.
* **Sparse equal-split case (from S5):** If `sparse_flag(κ_m)=true` then all foreign weights are equal **when they exist**; the guard still requires $T_m>0$ to proceed.
* **$K_{\text{raw}}=0$ merchants:** By design, these skip S6 entirely via S3/S4; S6.0 is not entered.

---

## 7) Language-agnostic reference algorithm (normative)

```text
FUNCTION S6_0_prescreen_and_cap(m):
  INPUT:
    merchant_id m
    K_raw := K_m from S4                # integer ≥1 (by S4 acceptance)
    c     := home ISO for m             # ISO2 (UPPER-CASE ASCII), validated earlier
    κ     := kappa_m for m              # ISO4217, from S5.0 merchant_currency
    Wκ    := [(i, w_i)] for currency=κ  # from S5 weights cache (ISO-ordered, Σ over D(κ)=1)

  PRECHECKS (structural):
    assert K_raw ≥ 1
    assert |Wκ| ≥ 1                     # missing currency weights → failure (below)

  STEP 1: Build foreign candidate set (home excluded; preserves ISO order)
    F := [ i for (i, _) in Wκ if i != c ]
    M := length(F)

  STEP 2: Foreign mass guard (sum on foreign set only)
    T := sum( w_i for (i, w_i) in Wκ if i != c )

  STEP 3: Effective selection size (cap)
    K_eff := min(K_raw, M)

  STEP 4: Branch on availability
    if (M == 0) or (T == 0):
        # Home-only short-circuit (no RNG, no gumbel_key)
        write country_set row:
          { merchant_id=m, country_iso=c, is_home=true, rank=0,
            prior_weight=null, manifest_fingerprint={manifest_fingerprint} }
          to data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/...
        emit optional gumbel_header {merchant_id, K_raw, M, K_eff=0, reason="no_candidates"}
        RETURN {K_eff=0, status="home_only_persisted"}
    else:
        RETURN {K_eff=K_eff, F=F, status="proceed_to_S6.3"}
```

**Determinism.** The procedure is pure and contains no RNG; given fixed inputs, outputs are identical across replays.

---

## 8) Failures attributable to S6.0 (scope-limited)

* **E/1A/S6/INPUT/MISSING_WEIGHTS** — `ccy_country_weights_cache` has **no rows** for $\kappa_m$. **Action:** abort merchant.
* **E/1A/S6/SCHEMA/COUNTRY_SET_HOME_ROW** — when short-circuiting, the writer fails PK/shape for the home row (e.g., bad ISO or wrong partitions). **Action:** abort run (persistence/layout error).

> All other math/schema failures (renormalisation, event envelope, selection order, country_set/winners coherence) are owned by later S6 sub-states.

---

## 9) Complexity & numerics

* **Time:** $O(|\mathcal D(\kappa_m)|)$ to filter out `home` and sum foreign mass.
* **Memory:** $O(|\mathcal F_m|)$ to carry the ISO list $F$ (if proceeding).
* **Numerics:** S6.0 performs a single scalar sum $T$ over foreign weights; no RNG.

---

## 10) Acceptance checks (what “done” means for S6.0)

For each merchant $m$ entering S6:

* If $M_m=0$ **or** $T_m=0$: exactly **one** `country_set` row (home) persisted under `seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}`, no `gumbel_key` events for $m$, and $K_m^\star=0$.
* If $M_m\ge1$ **and** $T_m>0$: S6.0 emits no data, exposes $K_m^\star=\min(K_{\text{raw}},M_m)$, and passes $(\mathcal F_m, K_m^\star)$ to S6.3.

---

### One-line takeaway

S6.0 deterministically computes $(\mathcal F_m,M_m)$, checks that **foreign mass exists** ($T_m>0$), caps $K_{\text{raw}}$ to $K_m^\star$, and—when no foreign candidates or mass exist—**writes the home-only `country_set` row (rank=0) and emits no RNG**, ending S6 for that merchant; otherwise it hands $(\mathcal F_m, K_m^\star)$ to S6.3.

---

# S6.1 — Universe, symbols, authority

## 1) Placement & purpose

S6 consumes the deterministic **currency→country priors** from S5, removes the merchant’s home ISO, **renormalises over the foreign set**, and performs **weighted sampling without replacement** via **Gumbel-top-$K$** to select the ordered foreign countries. S6 emits **one RNG event per foreign candidate** (`gumbel_key`) and persists the ordered winners to `country_set`, which is the **only** authority for cross-country order. **S6 writes `country_set` (including the home-only row when applicable).**

---

## 2) Domain: who runs S6

Evaluate S6 **only** for merchants $m$ that:

1. are multi-site (`is_multi=1`, S1);
2. passed cross-border eligibility (`is_eligible=1`, S3); and
3. have **effective foreign count** $K_m^\star \ge 1$ after S6.0’s cap $K_m^\star=\min(K_m,M_m)$, where $M_m$ is the number of foreign candidates (home excluded).

When $M_m=0$ **or** the foreign mass is zero, S6.0 has already **written only the home row** (`rank=0`) and S6 emits **no** `gumbel_key` events (short-circuit).

**Authority for the ordered result.** For $K_m^\star\ge 1$, S6 persists **home + $K_m^\star$ foreigns** to `country_set` with `rank=0` for home and `rank=1..K_m^\star` for winners **in Gumbel order**. `country_set` is explicitly the **only** authority for cross-country order in 1A.

---

## 3) Symbols & notation (fixed for all of S6)

Per merchant $m$:

* $c\in\mathcal I$: home ISO-3166 alpha-2 (**UPPER-CASE ASCII**).
* $\kappa_m\in\text{ISO4217}$: settlement currency (from S5.0 `merchant_currency`; S6 never recomputes $\kappa_m$).
* $\mathcal D(\kappa_m)\subset\mathcal I$: currency member set from S5 cache `ccy_country_weights_cache`, with weights $w_i^{(\kappa_m)}$ satisfying $\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}=1$, stored in **ISO-ascending** order.
* **Foreign candidate set:** $\mathcal F_m=\mathcal D(\kappa_m)\setminus\{c\}$ (order preserved).
* **Count & cap:** $M_m=|\mathcal F_m|$, $K_m^\star=\min(K_m,M_m)$. (If $M_m=0$ ⇒ S6.0 home-only branch.)
* **Foreign-renormalised weights** (defined/used in S6.3): $\tilde w_i=\dfrac{w_i^{(\kappa_m)}}{\sum_{j\in\mathcal F_m} w_j^{(\kappa_m)}}$ for $i\in\mathcal F_m$, with serial binary64 sums and tolerance $10^{-12}$.

---

## 4) Selection mechanism (mathematical statement)

S6 performs **weighted sampling without replacement** using **Gumbel-top-$K$**. For each foreign candidate $i\in\mathcal F_m$, draw **exactly one** open-interval uniform $u_i\in(0,1)$ (RNG mapping is specified in S6.4; clamps there ensure **finite** keys), then compute

$$
\boxed{\,z_i = \log \tilde w_i - \log\!\bigl(-\log u_i\bigr)\,}.
$$

Let the strict total order $\succ$ be “**key descending**, then **ISO ASCII ascending**” (tie-break if keys are bit-equal). The winners are the **top $K_m^\star$** elements under $\succ$; their **selection order** $r=1,\dots,K_m^\star$ is induced by the sort. Exactly **one** uniform is consumed per foreign candidate ($|\mathcal F_m|=M_m$); the run is fully replayable from the RNG envelope.

---

## 5) Authoritative artefacts (schemas, paths, partitions)

### RNG event stream — `gumbel_key` (emitted iff $M_m\ge 1$)

* **Path (dictionary-pinned):**
  `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
* **Emission order:** **ISO-ascending** by `country_iso` (stabilises JSONL concatenation).
* **Schema:** `schemas.layer1.yaml#/rng/events/gumbel_key` (envelope + payload).
  Envelope includes `{ts_utc, run_id, seed:uint64, parameter_hash:hex64, manifest_fingerprint:hex64, module, substream_label="gumbel_key", rng_counter_before/after_{lo,hi}}`.
  **Payload (minimal, deliberate):**
  `{merchant_id, country_iso, weight = tilde_w_i (binary64), key = z_i (finite), selected: bool, selection_order: int? (1..K* if selected, else null), K_raw, M, K_eff}`.
  *(We intentionally **do not** log `u`; `key` is sufficient and is reproducible from the envelope.)*
* **Coverage:** validators assert $|\text{events}_m|=M_m$; winners have `selected=true` with `selection_order∈{1..K_m^\star}`; losers have `selected=false`, `selection_order=null`.

### Allocation dataset — `country_set` (single authority for order)

* **Path (dictionary-pinned):**
  `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/`
* **Schema:** `schemas.1A.yaml#/alloc/country_set`.
  **PK** `(merchant_id, country_iso)`.
  **Rows per merchant:** exactly $K_m^\star+1$:
  `(m,c,is_home=true, rank=0, prior_weight=null)` and, for winners $(i_1,\dots,i_{K_m^\star})$ in **Gumbel order**,
  `(m,i_r,is_home=false, rank=r, prior_weight=tilde_w_{i_r}^{(rounded)})`, $r=1..K_m^\star$.
* **Weight representation policy:**
  – In **events**, `weight` is the renormalised $\tilde w_i$ in **binary64** (no decimal rounding).
  – In **country_set**, `prior_weight` is the same $\tilde w_i$ but **rounded to 8 decimal places at write** (computations remain binary64). Validators accept $|\sum \tilde w_i - 1| \le 10^{-6}$ on read to accommodate decimal rounding.
  – For the home row, `prior_weight=null`.
* **Coherence with events:** any `gumbel_key.selected=true` must have a matching `country_set` row with `rank = selection_order`. Domestic/home-only merchants have **only** the home row (`rank=0`) and **no** `gumbel_key` events.

**Upstream authority reminder.** S6 reads S5’s deterministic caches (partitioned by `{parameter_hash}`), especially `ccy_country_weights_cache`, as the sole source for $\mathcal D(\kappa)$ and priors $w^{(\kappa)}$. S5 caches are FK-clean and ISO-ordered.

---

## 6) Determinism & invariants (established at the S6 level)

* **I-G1 (bit-replay).** For fixed $(\tilde w,\ K_m^\star,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the uniforms $(u_i)$, keys $(z_i)$, winner set $S_m$, and ranks are **bit-identical** across replays.
* **I-G2 (event coverage).** Exactly $M_m$ `gumbel_key` events per merchant when $M_m\ge1$; winners `selected=true` with `selection_order∈{1..K_m^\star}`; others `selected=false`.
* **I-G3 (weight & ISO constraints).** Every event row has `country_iso` passing ISO FK and `weight∈(0,1]` with serial sum $\sum_{i\in\mathcal F_m}\tilde w_i=1$ within $10^{-12}$.
* **I-G4 (tie-break determinism).** If $z_i=z_j$ at binary64, order by **ISO ASCII** (UPPER-CASE) ascending; selection order is a pure function of $(\tilde w,u)$.
* **I-G5 (country-set coherence).** Persist exactly one home row (`rank=0`) plus $K_m^\star$ foreign rows in **the same order** as winners’ `selection_order`.
* **I-G6 (event emission order).** `gumbel_key` events **must** be emitted **ISO-ascending** to stabilise log concatenation.

---

## 7) Out-of-scope here (covered in later sub-states)

* **S6.2** pins exact inputs & lineage checks (presence/shape of S5 weights; envelope).
* **S6.3** defines the renormalisation on $\mathcal F_m$ (serial sums; positivity; sparse equal-split).
* **S6.4** specifies the RNG protocol: **per-candidate counter base** or ISO-index mapping, open-interval $u$ clamp to ensure finite keys, and one Philox draw per candidate.
* **S6.5–S6.6** codify the total-order sort and `country_set` writer (including rounding policy and partitions).

---

### One-line takeaway

S6.1 fixes the universe and the rules: who runs, what objects exist $(\mathcal F_m,M_m,K_m^\star,\tilde w,z)$, **how** events are emitted (ISO-ascending; one per candidate; `key` not `u`), and **where** the single source of truth for order lives (`country_set` with `rank`), with explicit partitions and weight-representation policy to keep implementation deterministic and audit-tight.

---

# S6.2 — Inputs & lineage checks

## 1) Scope & purpose

S6.2 assembles the **deterministic context** needed by S6.3–S6.6 and blocks progress if anything is missing or malformed:

* Merchant identity + **home ISO** $c$ (**UPPER-CASE ASCII**).
* S4’s accepted foreign-count $K_m$ and S6.0’s **effective cap** $K_m^\star$.
* Merchant currency $\kappa_m$ (from S5.0 cache; **never recomputed**).
* Currency→country **weights cache** (S5) for $\kappa_m$: the ISO-ordered set $\mathcal D(\kappa_m)$ and base weights $w_i^{(\kappa_m)}$.
* **Lineage envelope**: `seed`, `parameter_hash`, `manifest_fingerprint`, and `run_id` (events).

If any preconditions fail, **S6 must not proceed** to renormalisation/RNG/persistence.

---

## 2) Authoritative sources (what we read, where, and why)

* **Merchant currency $\kappa_m$ (S5.0 cache).**
  Dataset: `merchant_currency`, partitioned by `{parameter_hash}`, schema `schemas.1A.yaml#/prep/merchant_currency`. **Read only.**

* **Currency→country weights (S5 cache).**
  Dataset: `ccy_country_weights_cache`, partitioned by `{parameter_hash}`, schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`. This defines $\mathcal D(\kappa)$ and $w_i^{(\kappa)}$; rows are **strict ISO ASCII ascending** and sum to 1 (S5 guarantees; S6 re-checks defensively).

* **Allocation dataset target (egress surface).**
  `country_set`, partitioned by `{seed, parameter_hash, fingerprint}`, schema `schemas.1A.yaml#/alloc/country_set`. **S6 writes this later;** S6.2 pins lineage and partition expectations. `country_set` is the **only** authority for cross-country order (`rank`).

* **RNG event stream target.**
  `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`, schema `schemas.layer1.yaml#/rng/events/gumbel_key`. Exactly **one event per foreign candidate** when $K_m^\star\ge1$. (Emitted in S6.4; S6.2 asserts the lineage & shapes exist.)

---

## 3) Inputs per merchant $m$ (deterministic tuple)

$$
I_m=\big(m,\ c,\ K_m,\ K_m^\star,\ \kappa_m,\ \mathcal D(\kappa_m),\ \{w_i^{(\kappa_m)}\}_{i\in\mathcal D(\kappa_m)},\ E\big)
$$

Where:

* $m=\texttt{merchant_id}$ (id64) and $c\in\mathcal I$ (ISO-3166 alpha-2, **UPPER-CASE ASCII**).
* $K_m\in\{1,2,\dots\}$ from S4; $K_m^\star=\min(K_m,M_m)$ from S6.0 with $M_m=|\mathcal D(\kappa_m)\setminus\{c\}|$. **If $M_m=0$, S6.0 already wrote home-only and S6.2–S6.6 are skipped.**
* $\kappa_m$ from `merchant_currency` (parameter-scoped). **Do not recompute.**
* $\mathcal D(\kappa_m)$ and $w_i^{(\kappa_m)}$ from `ccy_country_weights_cache` (parameter-scoped, ISO-ordered, sum to 1).
* **Lineage envelope $E$:** `seed:uint64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`, `run_id`.

---

## 4) Preconditions & structural checks (must pass before S6.3)

Any failure here **aborts** (merchant or run) and prevents RNG emission later.

### C-1 Currency presence & shape

* A row exists for $\kappa_m$ in `merchant_currency/parameter_hash={parameter_hash}/…`. Else **fail** `E/1A/S6/INPUT/MISSING_KAPPA` (abort merchant).
* Weights exist for $\kappa_m$ in `ccy_country_weights_cache/parameter_hash={parameter_hash}/…`. Else **fail** `E/1A/S6/INPUT/MISSING_WEIGHTS` (abort merchant).

### C-2 ISO ordering & coverage

* Load all rows for $\kappa_m$; assert **strict ASCII order** by `country_iso` (**UPPER-CASE ASCII**). Else **fail** `E/1A/S6/INPUT/WEIGHTS_ORDER` (abort run).
* Let $\mathcal D(\kappa_m)$ be exactly that ISO set; $D=|\mathcal D(\kappa_m)|\ge1$.

### C-3 Sum & range sanity (defensive echoes of S5)

* Compute $S=\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}$ **serially in ISO order** (binary64); assert $|S-1|\le 10^{-6}$. Else **fail** `E/1A/S6/INPUT/WEIGHTS_SUM` (abort run).
* Assert each $w_i^{(\kappa_m)}\in[0,1]$ and **finite**. Else **fail** `E/1A/S6/INPUT/WEIGHTS_RANGE` (abort run).

### C-4 Eligibility & cap coherence

* Compute $F_m=\mathcal D(\kappa_m)\setminus\{c\}$ (order preserved) and $M_m=|F_m|$.
* If $M_m=0$: **do not proceed** (S6.0 already persisted home-only).
* Else assert $K_m^\star\in[1,M_m]$. If not, **fail** `E/1A/S6/INPUT/BAD_CAP` (abort run).

### C-5 Lineage envelope readiness (before any events)

* Assert the presence of `seed`, `parameter_hash`, `manifest_fingerprint`, and `run_id`.
* Assert **partition semantics** match the dictionary:

  * `gumbel_key` → partitions `{seed, parameter_hash, run_id}`.
  * `country_set` → partitions `{seed, parameter_hash, fingerprint}` (**no `run_id`**).
    If absent/mismatched: **fail** `E/1A/S6/LINEAGE/PARTITIONS` (abort run).

> Notes: RNG counter mapping and the **open-interval** $u$ clamp are specified in S6.4. S6.2 only asserts the **presence** of envelope keys and partition shapes.

---

## 5) What S6.2 does **not** do

* **No renormalisation** on the foreign set (S6.3 owns that).
* **No RNG**: does not open streams, draw uniforms, or emit events (S6.4).
* **No persistence** to `country_set` (S6.6 writes; S6.0 may have written home-only).

It is a pure **gatekeeper** ensuring S6.3–S6.6 receive **valid, auditable inputs**.

---

## 6) Language-agnostic reference algorithm (normative)

```text
FUNCTION S6_2_inputs_and_lineage_check(m):
  INPUT:
    merchant_id m
    home_iso c                                # ISO2, UPPER-CASE ASCII
    K_raw from S4 (int ≥ 1)
    K_eff from S6.0 (int ≥ 0)                 # = min(K_raw, M_m) computed in S6.0
    parameter_hash (hex64)
    manifest_fingerprint (hex64)
    seed (uint64), run_id
  READ:
    κ  := merchant_currency[parameter_hash].lookup(m).kappa
    Wκ := SELECT country_iso, weight
          FROM ccy_country_weights_cache[parameter_hash]
          WHERE currency = κ
          ORDER BY country_iso ASC  # expected strict ASCII order
  DERIVE / CHECK:
    assert κ is present                            # C-1
    assert |Wκ| ≥ 1                                # C-1
    ISO_list := [row.country_iso for row in Wκ]
    assert ISO_list is strictly ASCII-ascending    # C-2
    S := Σ(row.weight for row in Wκ) (serial, binary64)
    assert |S - 1| ≤ 1e-6 and all weights ∈ [0,1] and finite   # C-3
    F := [iso for iso in ISO_list if iso != c]     # preserves order
    M := length(F)
    if M == 0:
        return SKIP_MERCHANT("home_only_written_in_S6.0")
    assert (1 ≤ K_eff ≤ M)                         # C-4
    # Partition lineage keys present and match dictionary:
    assert gumbel_key partitions == {seed, parameter_hash, run_id}
    assert country_set partitions == {seed, parameter_hash, fingerprint}  # C-5
  OUTPUT to S6.3:
    ctx := {
      merchant_id: m,
      home: c,
      kappa: κ,
      candidates: F,                  # ISO order
      base_weights: [w_i for i in F], # aligned to F order, not yet renormalised
      K_star: K_eff,
      lineage: {seed, parameter_hash, run_id, manifest_fingerprint}
    }
  RETURN ctx
```

**Determinism:** pure function; no RNG or persistence side-effects. Given fixed inputs, the context record is byte-identical across replays.

---

## 7) Failure taxonomy (owned by S6.2)

* `E/1A/S6/INPUT/MISSING_KAPPA` — no `merchant_currency` row for $m$. **Abort merchant.**
* `E/1A/S6/INPUT/MISSING_WEIGHTS` — no weights for $\kappa_m$. **Abort merchant.**
* `E/1A/S6/INPUT/WEIGHTS_ORDER` — weights not in strict ASCII ISO order. **Abort run.**
* `E/1A/S6/INPUT/WEIGHTS_SUM` — sum≠1 (tol) or `E/1A/S6/INPUT/WEIGHTS_RANGE` — non-finite/out-of-range weight. **Abort run.**
* `E/1A/S6/INPUT/BAD_CAP` — $K_m^\star$ missing or not in $[1,M_m]$ when $M_m\ge1$. **Abort run.**
* `E/1A/S6/LINEAGE/PARTITIONS` — partition keys for `gumbel_key`/`country_set` not as per dictionary. **Abort run.**

---

## 8) Acceptance checks (what “done” means for S6.2)

For every merchant that reaches S6.2:

* A context record exists with `{m, c, κ, F (ISO order), base_weights aligned to F, K_m^\star ≥ 1, lineage}`.
* All C-1…C-5 predicates hold.
* **No events written**, **no RNG consumed**, **no `country_set` rows** written here.
* If $M_m=0$, the merchant **did not** enter S6.2 (handled by S6.0).

---

### One-liner

S6.2 is the **gatekeeper**: it proves the currency and ISO-ordered weights are valid, the cap $K_m^\star$ is coherent, and lineage/partitions are correct—so S6.3 can renormalise and S6.4 can safely open the RNG stream.

---

# S6.3 — Candidate set & renormalisation

## 1) Purpose & placement

Given the S6.2 context for merchant $m$ — home ISO $c$, currency $\kappa_m$, S5 weights $w^{(\kappa_m)}$ over $\mathcal D(\kappa_m)$, and the effective cap $K_m^\star$ from S6.0 — build the **foreign** candidate set $\mathcal F_m$ by excluding the home, then renormalise the weights on $\mathcal F_m$ to obtain a probability vector $\tilde w$ that sums to 1 (binary64, serial). This $\tilde w$ is the **only** weight used to compute Gumbel keys in S6.4–S6.5.

---

## 2) Inputs (from S6.2; read-only)

* $m$ (merchant id), $c\in\mathcal I$ (**UPPER-CASE ASCII** home ISO-2).
* $\kappa_m\in\mathrm{ISO4217}$ from `merchant_currency` (parameter-scoped; **never recomputed**).
* ISO-ordered S5 rows for $\kappa_m$: $\{(i, w_i^{(\kappa_m)}) : i\in\mathcal D(\kappa_m)\}$ with $\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}=1$ (schema-checked), each `country_iso` ISO-valid and **sorted ASCII-ascending**.
* $K_m^\star=\min(K_m,M_m)$ from S6.0 (**do not** use raw $K_m$ after S6.0).
* (Optional context) `sparse_flag(κ_m)` from S5; see §9.

Guards from S6.2 already ensured currency presence, ISO ordering, group-sum $=1$ (tol $10^{-6}$) and lineage readiness; S6.3 assumes those passed.

---

## 3) Mathematical construction (canonical)

### 3.1 Foreign candidate set (home excluded)

$$
\boxed{\, \mathcal F_m \;=\; \mathcal D(\kappa_m)\setminus\{c\},\quad M_m = |\mathcal F_m| \,}
$$

Use the **stored ISO order** from S5 for the iteration order of $\mathcal F_m$. If $M_m=0$, S6.0 has already short-circuited to home-only and S6.3 **does not run** for this merchant.

### 3.2 Foreign mass (serial sum, binary64)

$$
T_m \;=\; \sum_{j\in\mathcal F_m} w^{(\kappa_m)}_j
\quad\text{(single-thread serial left-fold in ISO order).}
$$

No parallel reductions or reordering; this preserves determinism across platforms.

### 3.3 Renormalisation to $\tilde w$ on $\mathcal F_m$

$$
\boxed{\, \tilde w_i \;=\; \frac{w^{(\kappa_m)}_i}{T_m}\quad \text{for } i\in\mathcal F_m\, },\qquad
\sum_{i\in\mathcal F_m}\tilde w_i \;=\; 1\ \ (\text{within }10^{-12}).
$$

S6 enforces **strict positivity** $\tilde w_i>0$ and finiteness for all $i\in\mathcal F_m$ so $\log \tilde w_i$ is defined and keys are finite downstream.

> **Design note (cap vs abort):** any legacy text that aborted when $K_m>M_m$ is superseded by S6.0’s **cap** $K_m^\star=\min(K_m,M_m)$. From S6.3 onward we use $K_m^\star$ only.

---

## 4) Numeric policy & tolerances (strict)

* **Arithmetic:** IEEE-754 binary64.
* **Reductions:** single-thread serial left-fold in the S5 ISO order (no parallel, no re-order).
* **Foreign mass positivity:** require $T_m>0$. (Guaranteed by S5/S6.0; checked defensively here.)
* **Normalisation tolerance:** after forming $\tilde w$, compute $S=\sum_{i\in\mathcal F_m}\tilde w_i$ in the same serial order and assert $|S-1|\le 10^{-12}$.
* **Range:** each $\tilde w_i\in(0,1]$ and `isfinite`; any non-finite/negative is a hard failure.
* **Representation:** $\tilde w$ remains **binary64** in memory. Rounding (8 dp) applies only when S6.6 writes `country_set` (not here).

---

## 5) Outputs (in-memory; consumed by S6.4–S6.6)

* Ordered foreign ISO list $\mathcal F_m = (i_1,\dots,i_{M_m})$ (ISO-ascending from S5).
* Vector $\tilde w = (\tilde w_{i_1},\dots,\tilde w_{i_{M_m}})$ aligned to $\mathcal F_m$.
* The integer $K_m^\star$ (already computed; $1\le K_m^\star\le M_m$).

S6.3 **does not** write `gumbel_key` or `country_set`. Those are written by S6.4–S6.6.

---

## 6) Language-agnostic reference algorithm (normative)

```text
FUNCTION S6_3_build_and_renormalise(ctx):
  INPUT (from S6.2):
    m            # merchant_id
    c            # home ISO2 (UPPER-CASE ASCII)
    κ            # merchant currency (ISO4217)
    Wκ           # ISO-ordered list [(i, w_i^(κ)) for i ∈ D(κ)], Σ w_i^(κ) = 1 (tol 1e-6)
    K_star ≥ 1   # from S6.0 cap
  OUTPUT (to S6.4):
    F            # ordered foreign ISO list
    tilde_w      # aligned foreign-renormalised weights (Σ=1 within 1e-12)
    K_star       # unchanged

  # 1) Build foreign candidate list (preserve ISO order)
  F ← [ i for (i, w) in Wκ if i ≠ c ]
  M ← |F|
  assert M ≥ 1                    # S6.0 would have short-circuited otherwise
  assert 1 ≤ K_star ≤ M           # defensive echo of S6.0/S6.2

  # 2) Serial foreign-mass sum (binary64)
  T ← 0.0
  for (i, w) in Wκ:
      if i ≠ c:
          T ← T + w
  if not (T > 0.0 and isfinite(T)):
      FAIL "E/1A/S6/RENORM/ZERO_FOREIGN_MASS"

  # 3) Renormalise (strict positivity & finiteness)
  tilde_map ← {}
  for (i, w) in Wκ:
      if i ≠ c:
          t ← w / T
          if not (isfinite(t) and t > 0.0 and t ≤ 1.0):
              FAIL "E/1A/S6/RENORM/WEIGHT_RANGE"
          tilde_map[i] ← t

  # 4) Sum-to-one check (serial, same order)
  S ← 0.0
  for i in F:
      S ← S + tilde_map[i]
  if |S - 1.0| > 1e-12:
      FAIL "E/1A/S6/RENORM/SUM_TOL"

  RETURN (F, [tilde_map[i] for i in F], K_star)
```

**Determinism:** pure function of $(W_\kappa, c)$; given the same inputs and dictionary, outputs are byte-replayable.

---

## 7) Acceptance checks (what “done” means for S6.3)

1. $\mathcal F_m = \mathcal D(\kappa_m)\setminus\{c\}$ in **S5 ISO order**; $M_m\ge 1$.
2. $K_m^\star$ satisfies $1\le K_m^\star\le M_m$.
3. $T_m>0$; each $\tilde w_i\in(0,1]$ and finite; $\sum\tilde w_i=1$ within $10^{-12}$ (serial).
4. No datasets written; context passed forward to S6.4 to open the RNG stream and emit **one** `gumbel_key` per candidate.

---

## 8) Failure taxonomy owned by S6.3 (precise triggers)

* `E/1A/S6/RENORM/ZERO_FOREIGN_MASS` — $T_m\le 0$ or non-finite. *(Should be unreachable if S6.0/S5 held; treat as upstream corruption.)*
* `E/1A/S6/RENORM/WEIGHT_RANGE` — some $\tilde w_i$ non-finite, $\le 0$, or $>1$.
* `E/1A/S6/RENORM/SUM_TOL` — $|\sum_{i\in\mathcal F_m}\tilde w_i - 1|>10^{-12}$ after renormalising.
* `E/1A/S6/INPUT/BAD_CAP` — $K_m^\star\notin[1,M_m]$ when $M_m\ge1$. *(Defensive echo; indicates a flow breach upstream.)*

---

## 9) Notes & edge cases

* **Home not in $\mathcal D(\kappa_m)$:** allowed — then $\mathcal F_m=\mathcal D(\kappa_m)$, $M_m=|\mathcal D|$; logic unchanged.
* **Single-member currency:** if $\mathcal D(\kappa_m)=\{c\}$ then $M_m=0$ and S6.0 wrote the home-only row; S6.3 is skipped.
* **Sparse equal-split semantics:** if `sparse_flag(κ_m)=true` (from S5), the **pre-renorm** foreign weights are equal; after renorm, each $\tilde w_i$ is **exactly $1/M_m$** in binary64 (modulo later 8-dp rounding at `country_set` write in S6.6).

---

### One-liner

S6.3 deterministically turns the S5 currency expansion into an **ISO-ordered foreign list** and a **probability vector $\tilde w$** (serial, tol $10^{-12}$), ready for one-uniform-per-candidate **Gumbel-top-$K_m^\star$** selection in S6.4–S6.5.

---

# S6.4 — RNG protocol & event contract

## 1) Purpose & placement

Given the S6.3 context $(\mathcal F_m,\ \tilde w,\ K_m^\star)$, S6.4:

1. draws **exactly one** open-interval uniform per foreign candidate (order-free addressing),
2. computes Gumbel keys $z_i=\log\tilde w_i-\log(-\log u_i)$ in binary64,
3. **buffers** $\{i\mapsto (u_i,z_i,\texttt{counters})\}$ in memory, and
4. **after S6.5 decides winners**, emits **one `gumbel_key` event per candidate** with final flags (`selected`, `selection_order`) in **ISO-ascending** order.

> We **do not** mutate/update log rows later. S6.4 emits once, post-selection, with final flags.

---

## 2) Substream discipline (authoritative, order-free)

**Engine.** Philox $2\times 64$-10. All RNG events include the **rng envelope**
$\{\texttt{ts_utc},\texttt{run_id},\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint},\texttt{module},\texttt{substream_label},\texttt{rng_counter_before_{lo,hi}},\texttt{rng_counter_after_{lo,hi}}\}$.

**Label.** `substream_label="gumbel_key"`.

**Per-candidate, order-free counter base (no stride, no index dependence).**
For merchant $m$ and foreign candidate ISO $i\in\mathcal F_m$,

$$
\texttt{ctr_base}(m,i)\ :=\ \operatorname{split64}\!\Big(\textsf{SHA256}\big("gumbel_key"\,\|\,m\,\|\,i\,\|\,\texttt{parameter_hash}\,\|\,\texttt{manifest_fingerprint}\big)\Big).
$$

The event’s **before** counter is `ctr_base(m,i)`; the **after** counter is `before + 1` (128-bit add with carry). This mapping is **partition/order invariant** and replaces any “jump/stride” scheme.

**Per-event draw.** Each `gumbel_key` event consumes **exactly one** Philox block (one uniform); envelope counters must satisfy `after = before + 1`.

---

## 3) Open-interval uniform $u\in(0,1)$ — bit-exact transform

From a single 64-bit lane $x$ of the Philox output (we **discard** the other lane):

$$
\boxed{\,u=\frac{x+1}{2^{64}+1}\in(0,1)\,}.
$$

This `u01` map guarantees $u$ is **strictly** inside $(0,1)$, so $g=-\log(-\log u)$ is always **finite**. This is the **only** uniform mapping used in 1A.

---

## 4) Key computation & numeric guards

For each candidate $i\in\mathcal F_m$ (with $\tilde w_i>0$ from S6.3):

$$
g_i=-\log\!\bigl(-\log u_i\bigr),\qquad
\boxed{\,z_i=\log \tilde w_i+g_i\,}.
$$

* Binary64 throughout; precompute $\log\tilde w_i$ once.
* Assert `isfinite(z_i)`; any NaN/Inf is a hard failure for this merchant.

---

## 5) Event stream — path, partitions, envelope, payload

**Path & partitions (dictionary-pinned):**
`logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
(partitioned by `["seed","parameter_hash","run_id"]`).

**Emission order:** **ISO-ascending** by `country_iso` (stabilises JSONL concatenation).

**Envelope (every row):** rng envelope from §2 with `substream_label="gumbel_key"`. Counters must show **delta = 1**.

**Payload (minimal, deliberate):**

```json
{
  "merchant_id": id64,
  "country_iso": iso2,                 // UPPER-CASE ASCII
  "weight": pct01,                     // foreign-renormalised tilde_w_i (binary64)
  "key": number,                       // z_i (finite)
  "selected": boolean,                 // final
  "selection_order": integer|null,     // 1..K* if selected, else null
  "K_raw": integer,
  "M": integer,
  "K_eff": integer                     // = K*
}
```

> We **do not** log `u`. `key` is fully reproducible from the envelope and context.

**Coverage invariant.** Emit **exactly $M_m$** `gumbel_key` rows for merchant $m$ (one per foreign candidate).

---

## 6) Determinism & draw-accounting invariants

* **Bit replay.** For fixed $(\tilde w,\ K_m^\star,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the vectors $(u_i,z_i)$, the winner set, and event flags are **bit-identical** across replays.
* **Per-event draws.** Every event has `after = before + 1`; per-merchant draw count equals $M_m$.
* **Schema & ranges.** `weight ∈ (0,1]` and finite; `country_iso` ISO-valid; `key` finite.

---

## 7) Language-agnostic reference algorithm (normative)

```text
ALGORITHM S6_4_rng_and_emit

INPUT:
  m                 # merchant
  F = [i1..iM]      # ISO-ascending foreign ISOs (from S6.3)
  tilde_w[ i ]      # Σ tilde_w = 1 within 1e-12 (binary64)
  lineage = {seed, parameter_hash, manifest_fingerprint, run_id}
  module_name := "1A.foreign_country_selector"
OUTPUT:
  exactly M JSONL rows at logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...

PHASE A — DRAW & BUFFER (order-free addressing, no emit yet):
  K := empty map
  C := empty map
  for each i in F:                        # any deterministic loop is fine
      before := ctr_base("gumbel_key", m, i, parameter_hash, manifest_fingerprint)
      (R0, R1) := philox2x64(before, seed)       # discard R1
      u := (R0 + 1) / (2^64 + 1)                 # open-interval u01
      g := -log(-log(u))
      z := log(tilde_w[i]) + g
      assert isfinite(z)
      after := before + 1                        # 128-bit add with carry
      K[i] := z
      C[i] := {before, after}

PHASE B — SELECTION (delegated to S6.5):
  winners := TOP_K_BY( K, primary = key desc, secondary = ISO asc, K = K_eff )
  rank[i] := 1..K_eff for i ∈ winners; absent otherwise

PHASE C — EMIT (single-shot, with final flags; ISO-ascending emission):
  for each i in F (ISO-ascending):
      write_event(
        envelope = {
          ts_utc=now(), run_id, seed, parameter_hash, manifest_fingerprint,
          module=module_name, substream_label="gumbel_key",
          rng_counter_before_hi, rng_counter_before_lo = C[i].before,
          rng_counter_after_hi,  rng_counter_after_lo  = C[i].after
        },
        payload = {
          merchant_id=m, country_iso=i,
          weight=tilde_w[i], key=K[i],
          selected = (i ∈ winners),
          selection_order = rank.get(i, null),
          K_raw, M=|F|, K_eff
        }
      )
```

---

## 8) Failure taxonomy owned by S6.4 (precise triggers)

* `E/1A/S6/RNG/ENVELOPE` — missing envelope fields (seed/parameter_hash/manifest_fingerprint/run_id/substream_label/counters). **Abort run.**
* `E/1A/S6/RNG/COUNTER_DELTA` — `after != before + 1`. **Abort run.**
* `E/1A/S6/RNG/U01_BREACH` — $u\notin(0,1)$ or non-finite (should be unreachable). **Abort merchant.**
* `E/1A/S6/RNG/KEY_NANINF` — `key` not finite. **Abort merchant.**
* `E/1A/S6/RNG/COVERAGE` — number of `gumbel_key` rows $\neq M_m$. **Abort run.**
* `E/1A/S6/RNG/EMIT_ORDER` — emission not ISO-ascending. **Abort run.**

(Selection/order mismatches against `country_set` are caught later in S6.6 coherence checks.)

---

## 9) Cross-artefact coherence (validators assert)

* Per merchant: $|\text{gumbel_key}|=M_m$ and every row has `after = before + 1`.
* Event `weight` equals the S6.3 $\tilde w_i$ (binary64), `country_iso` matches $\mathcal F_m$ in ISO set, and `key` is finite.
* After S6.6: winners’ `selection_order` equals `country_set.rank` for the same ISO; losers’ events have `selection_order=null`.

---

## 10) Edge notes

* **Extremes of $x$.** The `u01` mapping yields finite $g$ even when $x=0$ or $2^{64}-1$.
* **Tiny $\tilde w_i$.** Allowed (strictly $>0$); `key` remains finite.
* **Optional telemetry.** A single non-consuming `stream_jump` diagnostic may be emitted when first touching `"gumbel_key"` for a merchant; it **must not** alter counters.

---

### One-line takeaway

S6.4 makes RNG **bulletproof and replayable**: **per-candidate order-free counters**, a **bit-exact open-interval** uniform, **one draw per candidate**, **ISO-ascending single-shot emission** with final flags—producing `gumbel_key` events that S6.6 will map 1:1 into `country_set` ranks.

---

# S6.5 — Selection rule & induced order

## 1) Inputs & objective

Inputs for merchant $m$:

* **Candidates:** foreign ISO list $\mathcal F_m=(i_1,\dots,i_{M_m})$ from S6.3 (home excluded; **ISO-ascending**).
* For each $i\in\mathcal F_m$:
  – **foreign-renormalised weight** $\tilde w_i\in(0,1]$ (S6.3; $\sum \tilde w=1$);
  – **key** $z_i=\log \tilde w_i - \log(-\log u_i)$ from S6.4 (binary64; **finite**). *(S6.4 computed $u_i$ but we do **not** use or log it here.)*
* **Effective winners count:** $K_m^\star\in[1,M_m]$ from S6.0 (cap already applied).

**Goal:** pick the **top $K_m^\star$** under a **strict total order**, then set final `selected/selection_order` flags that S6.4 uses when emitting `gumbel_key` events.

---

## 2) Strict total order (mathematical definition)

Define $i \succ j$ (“$i$ outranks $j$”) iff

$$
i \succ j \iff \big(z_i > z_j\big)\ \text{or}\ \big(z_i=z_j\ \text{and}\ \text{ISO}(i) < \text{ISO}(j)\big),
$$

where `ISO(·)` compares **UPPER-CASE ASCII** country codes lexicographically.

**Sorter key (implementation-equivalent):** sort by

$$
\kappa(i):=\big(-z_i,\ \text{ISO}(i)\big)\quad\text{in lexicographic ascending order.}
$$

This is identical to “$z$ descending, ISO ascending” and does **not** rely on sort stability.

---

## 3) Winners, induced order, and flags

Let $\pi_m$ be the permutation of $\mathcal F_m$ sorted by $\succ$:

$$
z_{\pi_m(1)} \ge \dots \ge z_{\pi_m(M_m)}\quad(\text{tie-break by ISO}).
$$

* **Winners:** $S_m=\{\pi_m(1),\dots,\pi_m(K_m^\star)\}$.
* **Selection order:** $i_r=\pi_m(r)$ for $r=1,\dots,K_m^\star$.

**Final flags for each candidate (consumed by S6.4’s emitter):**

* Winners: `selected=true`, `selection_order=r`.
* Non-winners: `selected=false`, `selection_order=null`.

Flags **must** be consistent with the `key` recorded on each event; any mismatch is a validation failure.

---

## 4) Probabilistic semantics (why this is correct)

With $g_i:=-\log(-\log u_i)$ i.i.d. standard Gumbel and $z_i=\log\tilde w_i+g_i$, the permutation $\pi_m$ has the **Plackett–Luce** distribution with parameters $\tilde w$. The top-$K_m^\star$ are therefore a **weighted sample without replacement** from $\mathcal F_m$ with weights $\tilde w$ — exactly the intended sampler.

---

## 5) Artefact-level contracts & invariants

**Event stream (`gumbel_key`, emitted by S6.4 after this step):**

* Exactly **$M_m$** rows for $m$ (one per foreign candidate), **emitted ISO-ascending**.
* Winners carry `selected=true` and `selection_order∈{1..K_m^\star}`; losers `selected=false`, `selection_order=null`.
* Payload includes `key=z_i` (finite) and `weight=tilde_w_i` (binary64). `u` is not logged.

**Allocation dataset (`country_set`, written in S6.6):**

* Persist **home + $K_m^\star$** foreign rows; `rank=0` for home, and `rank=r` for winner $i_r$ **in Gumbel order**.
* **Coherence:** `country_set.rank == selection_order` for every winner; `country_set` remains the **only** authority for cross-country order.

---

## 6) Language-agnostic reference algorithm (normative)

```text
ALGORITHM S6_5_select_and_flag

INPUT:
  F = [i1..iM]                 # ISO-ascending foreign ISOs (from S6.3)
  z[i] for i in F              # finite keys (from S6.4)
  K_star (1..M)                # effective winners count (from S6.0)
OUTPUT (to S6.4 emitter and S6.6 writer):
  winners = [i_1..i_K_star]    # in Gumbel order
  flags[i] = {selected, selection_order}

STEPS:
1) assert all isfinite(z[i]) for i in F
2) idx := argsort_by( key(i) = (-z[i], ISO(i)) )   # z↓ then ISO↑
3) winners := take_first_K(idx, K_star)
4) # initialise flags as losers
   for i in F: flags[i] := {selected:false, selection_order:null}
5) # assign winner flags in induced order
   r := 1
   for i in winners:
       flags[i] := {selected:true, selection_order:r}
       r := r + 1
6) # postconditions
   assert |winners| == K_star
   assert { flags[i].selection_order | flags[i].selected } == {1..K_star}
RETURN winners, flags
```

**Emission strategy.** S6.4 performs Phase B **selection** via this algorithm, then **emits** `gumbel_key` with final flags in a single shot (ISO-ascending). No event updates occur afterward.

---

## 7) Validator hooks (deterministic predicates)

Given all `gumbel_key` rows for $m$:

1. **Coverage:** row count $=M_m$.
2. **Order reconstruction:** `idx := argsort_by((-key, ISO))`; winners are indices `idx[1..K_m^\star]`.
3. **Flags:** for `t ≤ K_m^\star`: row at `idx[t]` has `selected=true` and `selection_order=t`; for `t > K_m^\star`: `selected=false`, `selection_order=null`.
4. **Coherence to `country_set`:** join winners on `(merchant_id,country_iso)` and assert `rank == selection_order`.

---

## 8) Edge cases & guarantees

* **$K_m^\star=M_m$:** all candidates selected; orders and ranks are $1..M_m$.
* **$M_m=1$:** exactly one event; `selected=true`; `selection_order=1`; `rank=1`.
* **Key ties:** resolved deterministically by **ISO ASCII ascending**.
* **Non-finite keys:** disallowed (guarded earlier in S6.4); if encountered here, abort merchant.

---

## 9) Complexity & determinism

* **Time:** $O(M_m\log M_m)$ for the sort.
* **Memory:** $O(M_m)$ for keys and indices.
* **Determinism:** With fixed $(\tilde w,u)$ and lineage, `argsort_by((-z,ISO))` yields a unique $\pi_m$; winners and flags are **bit-replayable**.

---

### One-liner

S6.5 deterministically turns Gumbel keys into the **top-$K$** in **key↓, ISO↑** order, sets final flags `selected/selection_order=1..K`, and locks the order that `country_set` must persist — no black boxes, no ambiguity.

---

# S6.6 — Persistence (authoritative ordered set)

## 1) Purpose & placement

S6.6 takes the **winners & order** from S6.5 and the **foreign-renormalised weights** $\tilde w$ from S6.3, and materialises the per-merchant ordered set to **`country_set`**, which is explicitly the **only** authority for inter-country order in 1A. The dataset is **partitioned by `{seed, parameter_hash, fingerprint}`**, *not* by `run_id`.

---

## 2) Inputs (deterministic, read-only)

For a merchant $m$ admitted to S6 with $K_m^\star\ge 1$:

* Home ISO $c$.
* Winners $(i_1,\dots,i_{K_m^\star})$ in **Gumbel order** from S6.5, with `selection_order=r` for $i_r$.
* Foreign-renormalised weights $\tilde w_{i_r}\in(0,1]$ aligned to $(i_r)$, $\sum \tilde w = 1$ within $10^{-12}$ (serial; binary64).
* Lineage: `seed:uint64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64` (persisted as a column).
* Event stream `gumbel_key` (from S6.4, emitted post-S6.5) for cross-artefact coherence.

(If $M_m=0$, S6.0 already wrote the **home-only** row and S6.6 does nothing for $m$.)

---

## 3) Authoritative path, partitions, schema

* **Path (dictionary-pinned):**
  `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/part-*.parquet`
  **Partitions:** `["seed","parameter_hash","fingerprint"]`. **No `run_id`** here.

* **Schema (source of truth):** `schemas.1A.yaml#/alloc/country_set`.
  **PK:** `["merchant_id","country_iso"]` (unique within a `{seed,parameter_hash,fingerprint}` partition).
  **FK:** `country_iso` → ISO canonical (`schemas.ingress.layer1.yaml#/iso3166_canonical_2024`).
  **Order carrier:** `rank` (0 = home; 1..K in **Gumbel order**). Row/file order is irrelevant.
  **Columns & domains (semantics):**

  * `manifest_fingerprint: hex64` (required).
  * `merchant_id: id64` (required).
  * `country_iso: iso2` (required, **UPPER-CASE ASCII**, FK).
  * `is_home: boolean` (required).
  * `rank: int32, minimum 0` (required).
  * `prior_weight: float64, nullable` — **null for home**, otherwise $(0,1]$ for foreigns (diagnostic prior = $\tilde w$ **rounded to 8 dp at write**).

**Schema-authority policy:** `schemas.1A.yaml` is the sole source of truth; any Avro is generated later and **non-authoritative**.

---

## 4) Row semantics (what you *must* write)

Write exactly **$K_m^\star+1$** rows (home + winners) to the partition `{seed, parameter_hash, fingerprint}`:

### Home row (rank 0)

```
{ manifest_fingerprint, merchant_id=m, country_iso=c,
  is_home=true, rank=0, prior_weight=null }
```

### Foreign rows (ranks 1..K in Gumbel order)

For each $r=1..K_m^\star$, ISO $i_r$:

```
{ manifest_fingerprint, merchant_id=m, country_iso=i_r,
  is_home=false, rank=r, prior_weight=round8(tilde_w[i_r]) }
```

`country_set` is the **only** authority for order (via `rank`); all consumers must join on `rank`.

---

## 5) Numeric policy (strict, deterministic)

* **Arithmetic:** IEEE-754 binary64; **roundTiesToEven**; **no FMA**; no extended precision; no reordering of operations.
* **Reductions:** serial left-fold in **rank order** (1..K) when checking the foreign sum.
* **Pre-write sum (exactness gate):** require $\sum_{r=1}^{K} \tilde w_{i_r} = 1 \pm 10^{-12}$ (binary64, serial).
* **Emit rounding (deterministic):** store `prior_weight = round8( \tilde w )`, where

  ```
  round8(x):
      t := x * 1e8
      u := nearbyint(t)            # IEEE 754 ties-to-even
      y := u / 1e8
      return y                     # all operations in binary64; no FMA
  ```

  *(This yields a value exactly representable in binary64 for many cases; regardless, it is deterministic across platforms under the numeric policy above.)*
* **Post-write acceptance:** stored foreign `prior_weight` values must be finite in $(0,1]$; **read-sum tolerance** $|\sum_{r=1}^{K} \texttt{prior_weight}_r - 1| \le 10^{-6}$ (to accommodate 8-dp rounding).
* **Home row:** `prior_weight = null`.

---

## 6) Determinism & idempotency

* **Determinism.** With fixed lineage $(\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, S6.4 keys and S6.5 order are bit-replayable; thus the set $(c,i_1,\dots,i_K)$ and the stored `prior_weight` after `round8` are fixed.
* **Idempotent writer (merge-by-PK).** Within a `{seed, parameter_hash, fingerprint}` partition:

  * If `(merchant_id, country_iso)` exists, **replace** the row (rank/weight).
  * Else **insert**.
    Never rely on write sequence as an ordering mechanism.

---

## 7) Cross-artefact coherence (hard requirements)

* **Event ↔ table (winners):** Every winner `(merchant_id=m, country_iso=i_r)` **must** have a `gumbel_key` event with `selected=true` and `selection_order=r`, and the table **must** store `rank=r` for that ISO.
* **Coverage:** A merchant with any `gumbel_key.selected=true` **must** have the corresponding foreign rows in `country_set`. Conversely, losers (`selected=false`) must **not** appear in `country_set`.
* **Rank/source of truth:** Downstream components must **only** use `country_set.rank` for inter-country order (never `outlet_catalogue`).

---

## 8) Writer pre/post checks (must be enforced)

**Before write (construct rows):**

1. **Cardinality:** exactly $K_m^\star$ winners with unique `selection_order=1..K_m^\star`.
2. **Weights:** all $\tilde w_{i_r}$ finite in $(0,1]$; serial foreign **pre-write** sum $=1\pm 10^{-12}$.
3. **No duplicates:** winner ISOs unique and none equals home ISO.
4. **Lineage present:** `manifest_fingerprint` set; partitions `{seed, parameter_hash, fingerprint}` match dictionary.

**After write (persisted view):**

1. Exactly **one** home row: `(is_home=true, rank=0, prior_weight=null, country_iso=c)`.
2. Exactly **K** foreign rows with `rank∈{1..K}` **once each** (contiguous ranks).
3. `PK` uniqueness holds; all `country_iso` pass ISO FK.
4. **Event coherence:** join winners to `country_set` and assert `rank==selection_order`.
5. **Stored-sum tolerance:** read foreign `prior_weight` and assert $|\sum - 1| \le 10^{-6}$.

---

## 9) Failure predicates owned by S6.6 (names indicative)

* `E/1A/S6/PERSIST/COUNTRY_SET_SCHEMA` — any schema violation (missing/typed columns, FK fail, non-hex fingerprint, out-of-range weight, negative rank). **Abort run.**
* `E/1A/S6/PERSIST/MISSING_HOME_ROW` — no `(m,c,rank=0,is_home=true,prior_weight=null)` row. **Abort merchant.**
* `E/1A/S6/PERSIST/RANK_GAP_OR_DUP` — ranks not exactly `{0..K}` or duplicates. **Abort merchant.**
* `E/1A/S6/PERSIST/PK_DUP` — duplicate `(merchant_id,country_iso)` in the target partition. **Abort run.**
* `E/1A/S6/PERSIST/WEIGHT_SUM_PREWRITE` — pre-write $\sum \tilde w$ not in $1\pm 10^{-12}$. **Abort merchant.**
* `E/1A/S6/PERSIST/WEIGHT_SUM_STORED` — stored foreign `prior_weight` read-sum breaches $1\text{e-}6$. **Abort merchant.**
* `E/1A/S6/PERSIST/HOME_WEIGHT_NONNULL` or `/FOREIGN_WEIGHT_NULL` — home has non-null weight or a foreign has null. **Abort merchant.**
* `E/1A/S6/PERSIST/EVENT_COHERENCE` — any mismatch to `gumbel_key.selected/selection_order`. **Abort run.**
* `E/1A/S6/PERSIST/PARTITION_KEYS` — path not partitioned by `{seed, parameter_hash, fingerprint}`. **Abort run.**

---

## 10) Language-agnostic reference writer (normative)

```text
ALGORITHM S6_6_write_country_set

INPUT:
  m                # merchant_id
  c                # home ISO2 (UPPER-CASE ASCII)
  winners = [i1..iK]            # Gumbel order from S6.5 (K = K_m^*)
  tilde_w: map ISO→float64      # aligned to winners; Σ tilde_w[winners] = 1 ± 1e-12
  lineage = {seed, parameter_hash, manifest_fingerprint}

TARGET PARTITION:
  path := data/layer1/1A/country_set/
          seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/...

PRECHECKS:
  assert K ≥ 1
  assert winners are unique; none equals c
  assert all tilde_w[i] finite in (0,1]
  assert serial_sum(tilde_w[i] for i in winners) ≈ 1 within 1e-12

BUILD (apply deterministic 8dp rounding at write):
  rows := [
    {manifest_fingerprint, merchant_id:m, country_iso:c,
     is_home:true, rank:0, prior_weight:null}
  ]
  for r in 1..K:
    i := winners[r]
    w8 := round8(tilde_w[i])        # see §5 for numeric policy
    rows.append({manifest_fingerprint, merchant_id:m, country_iso:i,
                 is_home:false, rank:r, prior_weight:w8})

WRITE (idempotent merge-by-PK within {seed,parameter_hash,fingerprint}):
  for row in rows:
    upsert_into_country_set_PK((merchant_id,row.country_iso), row)

POSTCHECKS (persisted view for m):
  assert exactly one (is_home=true, rank=0, country_iso=c, prior_weight=null)
  assert for r in 1..K exactly one row with rank=r and is_home=false
  assert | Σ_{r=1..K} prior_weight(rank=r) - 1 | ≤ 1e-6
  # Event coherence:
  join winners with gumbel_key where selected=true:
     assert rank == selection_order for every winner

RETURN success
```

---

## 11) Notes & edge cases

* **$K_m^\star=M_m$:** all candidates become foreign rows; still exactly one home row + $M_m$ foreign rows.
* **Home-only merchants (S6.0):** already persisted in S6.0; S6.6 **must not** write again.
* **Downstream:** `outlet_catalogue` does **not** encode inter-country order; all consumers (incl. 1B) **must** use `country_set.rank`.

---

### One-line takeaway

S6.6 writes the **single source of truth** for cross-country order under `{seed, parameter_hash, fingerprint}`: **home rank 0**, **foreign ranks 1..K** in Gumbel order, with **deterministically rounded (8-dp) prior weights**, plus hard schema/PK/FK and **event↔table** coherence checks. Deterministic, idempotent, and audit-tight.

---

# S6.7 — Determinism & correctness invariants

## 1) Scope (what S6.7 governs)

S6.7 concerns merchants that reach S6 with effective $K_m^\star \ge 1$ (after S6.0’s cap/short-circuit). It asserts:

* **Bit replay:** with fixed lineage, the uniforms $u$, keys $z$, winner set $S_m$, and the persisted order are uniquely determined.
* **Event coverage & schema discipline:** **exactly one** `gumbel_key` event per foreign candidate, each with a full RNG envelope and **ISO-ascending emission order**.
* **Coherent persistence:** `country_set` (partitioned by `{seed, parameter_hash, fingerprint}`) materialises home rank 0 plus the foreign winners in **Gumbel order**; it is the **only** authority for inter-country order.
* **Branch edge cases:** when $M_m{=}0$, S6 persists **home-only** and emits **no** `gumbel_key`; S3-ineligible merchants have **no** S4–S6 RNG events at all.

---

## 2) Normative invariants (I-G1 … I-G11)

### I-G1 — Bit-replay determinism

For fixed $(\tilde w,\ K_m^\star,\ \texttt{seed}, \texttt{parameter_hash}, \texttt{manifest_fingerprint})$, the vector $u\in(0,1)^{M_m}$, the keys $z$, the winner set $S_m$ and the **selection order** are **bit-identical** across replays. (Counter-based Philox + per-candidate counter base + open-interval uniform + one draw per candidate + deterministic tie-break.)

### I-G2 — Event coverage (one per candidate)

For merchant $m$, if the foreign candidate size is $M_m$ then the `gumbel_key` stream **must** contain **exactly $M_m$** rows for $m$; no more, no less. Winners have `selected=true` and `selection_order∈{1..K_m^\star}`; losers have `selected=false`, `selection_order=null`.

### I-G3 — Envelope, counters, emission order, payload

Every `gumbel_key` row must:

* carry the RNG envelope `{ts_utc, run_id, seed:uint64, parameter_hash:hex64, manifest_fingerprint:hex64, module, substream_label="gumbel_key", rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo}}`;
* satisfy **counter discipline**: `after = before + 1` (128-bit add);
* be emitted in **ISO-ascending order** of `country_iso` for stable JSONL concatenation;
* meet payload domains: `merchant_id:id64`, `country_iso:iso2 (UPPER-CASE ASCII)`, `weight:pct01 (0,1]` (the **foreign-renormalised** $\tilde w_i$ from S6.3, binary64), `key:number` (finite), plus `{K_raw:int, M:int, K_eff:int}`.

> Note: `u` is **not** logged by design; `key` is replayable from the envelope and S6.3 context.

**Partitions.** Events live at
`logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with partitions `["seed","parameter_hash","run_id"]`.

### I-G4 — Deterministic order & tie-break

Sort by **key descending** with **ISO ASCII ascending** as tie-break. The first $K_m^\star$ are winners in positions $1..K_m^\star$.

### I-G5 — Coherence to `country_set` (the order carrier)

Persist **exactly one** home row `(is_home=true, rank=0, prior_weight=null)` and **$K_m^\star$** foreign rows `(is_home=false, rank=r, prior_weight∈(0,1])` **in the same order** as `gumbel_key.selection_order=r`. Any mismatch between `country_set.rank` and winners’ `selection_order` is a **validation failure**.

**Path/partitions/schema.**
`data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/…`, partitions `["seed","parameter_hash","fingerprint"]`, schema `schemas.1A.yaml#/alloc/country_set`. `country_set` is the **only authority** for cross-country order.

### I-G6 — Weight integrity (events vs table)

* **Events:** weights are $\tilde w_i$ for **all** $M_m$ candidates; each is in $(0,1]$. The **serial sum** in ISO order equals $1$ within $10^{-12}$.
* **Table (`country_set`):** winners’ `prior_weight` equals $\tilde w_i$ **rounded to 8 dp at write** (see S6.6). The read-sum tolerance on stored `prior_weight` is $\le 10^{-6}$. Home `prior_weight` is **null**.

### I-G7 — Keys finite

Every event `key` is finite (no NaN/Inf). Open-interval `u` ensures $g=-\log(-\log u)$ is finite.

### I-G8 — Branch/edge-case coherence

* **No candidates:** If $M_m=0$, S6 **persists home-only** (`rank=0`) and emits **no** `gumbel_key` for $m$. Reason `"no_candidates"` is recorded by validation; proceed to S7.
* **Ineligible merchants:** If S3 decided $e_m=0$, there must be **no** S4/S6 events; later `country_set` has **only** the home row.

### I-G9 — Partition & schema authority

All paths/partitions must match the **data dictionary** and authoritative JSON-Schemas. Any deviation (wrong partitions; referencing Avro; missing FK to canonical ISO) is a structural error.

### I-G10 — Idempotent persistence

Within `{seed, parameter_hash, fingerprint}`, `(merchant_id,country_iso)` is a PK; re-runs **upsert** rows (no duplicates), and ranks for a merchant are exactly $\{0,1,\dots,K_m^\star\}$ with no gaps.

### I-G11 — Counter mapping (order-free addressing)

For each event, the **before** counter equals the per-candidate base
`ctr_base = split64(SHA256("gumbel_key" ∥ merchant_id ∥ country_iso ∥ parameter_hash ∥ manifest_fingerprint))`, and `after = before + 1`. A validator **may** recompute and enforce this equality.

---

## 3) Numeric policy & tolerances

* **Arithmetic:** IEEE-754 binary64 for all logs, keys, sums.
* **Serial reductions:** deterministic order (ISO order for event-side mass; `rank` order for `country_set` checks).
* **Tolerances:**
  – Events: $|\sum \tilde w - 1| \le 10^{-12}$ (binary64, serial).
  – Table (stored 8-dp): $|\sum \texttt{prior_weight} - 1| \le 10^{-6}$.
* **Uniform mapping:** open-interval $u=(x+1)/(2^{64}+1)$ (S6.4), ensuring finite keys.

---

## 4) Cross-artefact contracts (summarised)

1. **Events ↔ Table:** winners’ `(merchant_id, country_iso)` **must** appear in `country_set` with `rank == selection_order`. Losers must **not** appear as foreign rows.
2. **Authority:** consumers needing inter-country sequence **must** join `country_set.rank` (egress like `outlet_catalogue` does **not** encode this order).
3. **Run lineage:** `country_set` partitions do **not** include `run_id`; `gumbel_key` does. Validators join with `{seed, parameter_hash, manifest_fingerprint}`.

---

## 5) Language-agnostic **reference validator** (normative)

```text
FUNCTION validate_S6_for_merchant(m):

INPUT:
  G = gumbel_key rows for m (logs/rng/events/gumbel_key/seed=…/parameter_hash=…/run_id=…)
  C = country_set rows for m (data/layer1/1A/country_set/seed=…/parameter_hash=…/fingerprint=…)
  F = |G|                  # expected candidate count
  K_star = effective winners from S6.0
  c_home = home ISO for m
  lineage = {seed, parameter_hash, manifest_fingerprint, run_id}

# Coverage
1  assert F >= K_star
2  assert count(G) == F                               # I-G2

# Envelope, counters, emission order, payload
3  prev_iso := null
4  for e in G in file order:
5      assert has_fields(e.envelope, [..., 'rng_counter_before_*','rng_counter_after_*'])
6      assert e.substream_label == "gumbel_key"
7      assert advance128(e.before) == e.after         # delta = 1   (I-G3)
8      # Optional: recompute base counter and check equality (I-G11)
9      assert e.key is finite and 0 < e.weight ≤ 1
10     assert is_iso2_upper(e.country_iso)
11     if prev_iso != null: assert prev_iso < e.country_iso   # ISO-ascending emit
12     prev_iso := e.country_iso

# Event-side mass conservation (ISO order)
13 S := 0.0
14 for e in G in ISO_ASCENDING: S := S + e.weight
15 assert |S - 1.0| ≤ 1e-12                               # I-G6 (events)

# Reconstruct order and check flags
16 idx := argsort_by( key(i) = (-G[i].key, G[i].country_iso) )
17 winners := take_first_K(idx, K_star)
18 for t in 1..F:
19     is_win := (t in winners)
20     if is_win:
21         r := position(t in winners)                    # 1-based
22         assert G[t].selected == true and G[t].selection_order == r
23     else:
24         assert G[t].selected == false and is_null(G[t].selection_order)

# country_set structure and coherence
25 assert partitions(G) == ["seed","parameter_hash","run_id"]
26 assert partitions(C) == ["seed","parameter_hash","fingerprint"]
27 assert exactly_one row in C where is_home=true and rank=0 and country_iso==c_home and prior_weight is null
28 assert count(C where is_home=false) == K_star
29 map_rank := { row.country_iso -> row.rank for row in C where is_home=false }
30 Sfw := 0.0
31 for row in C where is_home=false:
32     assert isfinite(row.prior_weight) and 0 < row.prior_weight ≤ 1
33     Sfw := Sfw + row.prior_weight
34 assert |Sfw - 1.0| ≤ 1e-6                              # I-G6 (table, 8dp)
35 for r in 1..K_star:
36     i := winners[r]
37     assert map_rank[ G[i].country_iso ] == r           # I-G5

RETURN PASS
```

*Failure mapping:* envelope/counters → `RNG/ENVELOPE` or `RNG/COUNTER_DELTA`; emission order → `RNG/EMIT_ORDER`; event coverage → `RNG/COVERAGE`; non-finite key → `RNG/KEY_NANINF`; weights sum (events) → `INPUT/WEIGHTS_SUM`; table sum → `PERSIST/WEIGHT_SUM_STORED`; event↔table mismatch → `PERSIST/EVENT_COHERENCE`; partition drift → `LINEAGE/PARTITIONS`.

---

## 6) Edge cases & sanity checks

* **$K_m^\star=M_m$:** all candidates are winners; exactly $M_m$ `selected=true` with `selection_order=1..M_m`; table has ranks $1..M_m$.
* **No candidates $M_m=0$:** only the home row is written; `gumbel_key` must be **absent** for $m$.
* **Ineligible $e_m=0$:** no S4/S6 events; table has only `rank=0` home.

---

## 7) Why this is sufficient

These invariants guarantee: (a) **replayability** with order-free counter bases (I-G1/I-G11), (b) **auditable RNG accounting** and strict schema/ordering (I-G2/I-G3/I-G4), (c) a **single source of truth** for order in `country_set` (I-G5), and (d) **mass conservation** from events into the persisted set while acknowledging 8-dp storage (I-G6)—all under dictionary-pinned paths and partitions.

---

### One-liner

S6.7 makes the run provably reproducible and auditable: **ISO-ascending single-shot events**, **per-candidate counter bases**, **exact event mass (1e-12)**, **8-dp table mass (1e-6)**, and a **rank==selection_order** lock between events and `country_set`.

---

# S6.8 — Failure taxonomy & CI error codes (authoritative)

## 1) Scope & artefacts under test

S6 produces/uses two authoritative artefacts:

1. **RNG events**: `gumbel_key` — one row **per foreign candidate**.
   **Path & partitions (dictionary):**
   `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   **Schema:** `schemas.layer1.yaml#/rng/events/gumbel_key` (envelope + payload).

2. **Allocation table**: `country_set` — ordered winners (home rank 0; foreign ranks 1..K).
   **Path & partitions (dictionary):**
   `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/part-*.parquet`
   **Schema:** `schemas.1A.yaml#/alloc/country_set`. `country_set` is the **only** authority for inter-country order.

S6 relies on parameter-scoped inputs from S5 (weights cache, etc.) governed by the **Schema Authority Policy**. **Only JSON-Schema is authoritative** (AVSC is non-authoritative).

---

## 2) Error code format & severity

```
E/1A/S6/<CLASS>/<DETAIL>
```

* **Abort run**: structural/systemic breach (schemas, partitions, counter discipline, coverage, coherence).
* **Abort merchant**: local pathology for a specific merchant (zero foreign mass, non-finite key, etc.).

Validators log `{code, merchant_id? (optional), reason, artefact_path, partition_keys, offending_rows_sample}` into the run’s `validation_bundle_1A` (under the run’s fingerprint).

---

## 3) Taxonomy (classes, precise triggers, action, locus)

### A. INPUT — parameter/currency/weights presence & shape

* **E/1A/S6/INPUT/MISSING_KAPPA** — No `merchant_currency` row for merchant $m$ at `{parameter_hash}`.
  **Action:** Abort merchant. **Where:** S6.2 (C-1).

* **E/1A/S6/INPUT/MISSING_WEIGHTS** — No `ccy_country_weights_cache` rows for $\kappa_m$ at `{parameter_hash}`.
  **Action:** Abort merchant. **Where:** S6.2 (C-1).

* **E/1A/S6/INPUT/WEIGHTS_ORDER** — Weights for $\kappa_m$ not in **strict ASCII ISO** order.
  **Action:** Abort run. **Where:** S6.2 (C-2).

* **E/1A/S6/INPUT/WEIGHTS_SUM** — Serial sum over $\mathcal D(\kappa_m)$ $\notin 1\pm 10^{-6}$.
  **Action:** Abort run. **Where:** S6.2 (C-3).

* **E/1A/S6/INPUT/WEIGHTS_RANGE** — Some $w_i^{(\kappa)}$ non-finite or $\notin[0,1]$.
  **Action:** Abort run. **Where:** S6.2 (C-3).

* **E/1A/S6/INPUT/BAD_CAP** — With $M_m\ge1$, effective $K_m^\star\notin[1,M_m]$.
  **Action:** Abort run. **Where:** S6.2 (C-4), echoed in S6.3.

### B. LINEAGE — partitions/authority

* **E/1A/S6/LINEAGE/PARTITIONS** — Partitions don’t match dictionary:
  `gumbel_key` must be `["seed","parameter_hash","run_id"]`;
  `country_set` must be `["seed","parameter_hash","fingerprint"]`.
  **Action:** Abort run. **Where:** S6.2 & S6.6.

* **E/1A/S6/LINEAGE/SCHEMA_AUTHORITY** — Referencing a non-authoritative schema or wrong JSON-Schema pointer.
  **Action:** Abort run. **Where:** CI schema audit.

### C. RENORM — foreign mass & normalisation

* **E/1A/S6/RENORM/ZERO_FOREIGN_MASS** — $T_m=\sum_{i\in\mathcal F_m} w_i^{(\kappa)}\le0$ or non-finite.
  **Action:** Abort merchant. **Where:** S6.3.

* **E/1A/S6/RENORM/WEIGHT_RANGE** — Some $\tilde w_i$ non-finite or $\notin(0,1]$.
  **Action:** Abort merchant. **Where:** S6.3.

* **E/1A/S6/RENORM/SUM_TOL** — Serial sum $\sum_{i\in\mathcal F_m}\tilde w_i\notin 1\pm 10^{-12}$.
  **Action:** Abort merchant. **Where:** S6.3.

### D. RNG — envelope, counters, uniforms, keys (`gumbel_key`)

* **E/1A/S6/RNG/ENVELOPE** — Missing envelope field(s) (`ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before/after_{hi,lo}`) or `substream_label!="gumbel_key"`.
  **Action:** Abort run. **Where:** S6.4 emit.

* **E/1A/S6/RNG/COUNTER_DELTA** — For any row, `after != before + 1`.
  **Action:** Abort run. **Where:** S6.4 emit.

* **E/1A/S6/RNG/EMIT_ORDER** — Events for a merchant not emitted in **ISO-ascending** `country_iso`.
  **Action:** Abort run. **Where:** S6.4 emit.

* **E/1A/S6/RNG/U01_BREACH** — Replayed uniform (from envelope counters + seed) not strictly in $(0,1)$ or non-finite.
  **Action:** Abort merchant. **Where:** Validator (replay of S6.4 mapping).

* **E/1A/S6/RNG/KEY_NANINF** — `key` non-finite.
  **Action:** Abort merchant. **Where:** S6.4 emit.

* **E/1A/S6/RNG/COVERAGE** — $|\text{gumbel_key}_m| \neq M_m$ (must be **exactly one per candidate**).
  **Action:** Abort run. **Where:** S6.4 / S6.7.

### E. SELECTION — sorting, flags

* **E/1A/S6/SELECT/ORDER_MISMATCH** — Sorting by $(\text{key}↓,\ \text{ISO}↑)$ does not reproduce `selected=true` with `selection_order=1..K_m^\star`.
  **Action:** Abort run. **Where:** S6.5 / S6.7.

* **E/1A/S6/SELECT/FLAGS_DOMAIN** — Winner missing `selection_order∈{1..K_m^\star}` or loser with non-null `selection_order`.
  **Action:** Abort run. **Where:** S6.5 / S6.7.

### F. PERSIST — `country_set` write, schema & numeric policy

* **E/1A/S6/PERSIST/COUNTRY_SET_SCHEMA** — Any schema breach (PK/FK/typed columns; `rank<0`; home `prior_weight` not null; foreign `prior_weight` out of $(0,1]$).
  **Action:** Abort run. **Where:** S6.6 writer.

* **E/1A/S6/PERSIST/MISSING_HOME_ROW** — No `(is_home=true, rank=0, prior_weight=null, country_iso=c)` row.
  **Action:** Abort merchant. **Where:** S6.6.

* **E/1A/S6/PERSIST/RANK_GAP_OR_DUP** — Foreign ranks not exactly `{1..K_m^\star}` or duplicated.
  **Action:** Abort merchant. **Where:** S6.6.

* **E/1A/S6/PERSIST/PK_DUP** — Duplicate `(merchant_id,country_iso)` within `{seed,parameter_hash,fingerprint}`.
  **Action:** Abort run. **Where:** S6.6.

* **E/1A/S6/PERSIST/WEIGHT_SUM_PREWRITE** — Pre-write serial sum of winners’ $\tilde w$ $\notin 1\pm 10^{-12}$.
  **Action:** Abort merchant. **Where:** S6.6 pre-check.

* **E/1A/S6/PERSIST/WEIGHT_SUM_STORED** — Read-sum of stored foreign `prior_weight` (8-dp) $\notin 1\pm 10^{-6}$.
  **Action:** Abort merchant. **Where:** S6.6 post-check.

* **E/1A/S6/PERSIST/PARTITIONS** — `country_set` not partitioned by `{seed, parameter_hash, fingerprint}`.
  **Action:** Abort run. **Where:** S6.6 writer.

* **E/1A/S6/PERSIST/EVENT_COHERENCE** — Winners’ `selection_order` not matched by `country_set.rank`.
  **Action:** Abort run. **Where:** S6.6 post-check.

### G. COHERENCE — events ↔ table (validator)

* **E/1A/S6/COHERENCE/EVENT_TO_TABLE** — Any winner’s `(merchant_id, country_iso, selection_order=r)` missing or mismatched to a `country_set.rank=r`.
  **Action:** Abort run. **Where:** S6.7 validator.

* **E/1A/S6/COHERENCE/LOSER_IN_TABLE** — A loser (`selected=false`) appears as foreign in `country_set`.
  **Action:** Abort run. **Where:** S6.7 validator.

### H. BRANCH — edge cases

* **E/1A/S6/BRANCH/NO_CANDIDATES_WITH_EVENTS** — $M_m=0$ but `gumbel_key` events exist.
  **Action:** Abort run. **Where:** S6.0/S6.4 guard.

* **E/1A/S6/BRANCH/INELIGIBLE_HAS_EVENTS** — From S3: `is_eligible=false` but S6 events exist.
  **Action:** Abort run. **Where:** cross-state validator (S3↔S6).

---

## 4) Where each failure is detected (map to substates)

| Substate | Primary checks that **raise** codes                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------------------------ |
| **S6.0** | Branch $M_m=0$ → **no** events. (H)                                                                                      |
| **S6.2** | Presence/shape of `merchant_currency` / `weights_cache`; ISO order; sum=1; cap; partitions known. (A,B)                  |
| **S6.3** | $T_m>0$, $\tilde w$ domain & sum tolerance. (C)                                                                          |
| **S6.4** | Envelope; `after=before+1`; ISO-ascending emit; finite key; exact **M** events. (D)                                      |
| **S6.5** | Reconstruct order by (key↓, ISO↑); flags domain. (E)                                                                     |
| **S6.6** | Schema/PK/FK; `{seed,parameter_hash,fingerprint}` partitions; ranks; pre-write & stored sums; event↔table coherence. (F) |
| **S6.7** | End-to-end invariants across artefacts; branch coherence with S3/S6.0; replayed-uniform checks. (D,E,F,G,H)              |

---

## 5) Normative validator snippets (detection patterns)

> The validator **replays** uniforms from the envelope; events do **not** carry `u`.

```text
# A — INPUT
if not has_row(merchant_currency[parameter_hash], m):        FAIL "E/1A/S6/INPUT/MISSING_KAPPA"
Wκ := weights_cache[parameter_hash][κ_m]
if |Wκ| == 0:                                                FAIL "E/1A/S6/INPUT/MISSING_WEIGHTS"
assert_ascii_iso_order(Wκ) else                              FAIL "E/1A/S6/INPUT/WEIGHTS_ORDER"
if |Σ_w(Wκ) - 1| > 1e-6:                                     FAIL "E/1A/S6/INPUT/WEIGHTS_SUM"
if ∃w∈Wκ with !finite(w) or w∉[0,1]:                         FAIL "E/1A/S6/INPUT/WEIGHTS_RANGE"
if M≥1 and (K_star < 1 or K_star > M):                       FAIL "E/1A/S6/INPUT/BAD_CAP"

# B — LINEAGE
if partitions(gumbel_key) != ["seed","parameter_hash","run_id"]:            FAIL "E/1A/S6/LINEAGE/PARTITIONS"
if partitions(country_set) != ["seed","parameter_hash","fingerprint"]:      FAIL "E/1A/S6/LINEAGE/PARTITIONS"

# D — RNG (replay-based)
for e in gumbel_key_rows(m) in FILE_ORDER:
    assert e.substream_label == "gumbel_key" else             FAIL "E/1A/S6/RNG/ENVELOPE"
    assert advance128(e.before) == e.after else               FAIL "E/1A/S6/RNG/COUNTER_DELTA"
    u := u01_from_counter(seed, e.before)                     # (x+1)/(2^64+1)
    if !(0 < u && u < 1):                                     FAIL "E/1A/S6/RNG/U01_BREACH"
    if !finite(e.key):                                        FAIL "E/1A/S6/RNG/KEY_NANINF"
    # ISO-ascending emit:
    assert_nondecreasing_iso(file_order_country_isos) else    FAIL "E/1A/S6/RNG/EMIT_ORDER"
if |gumbel_key_rows(m)| != M:                                 FAIL "E/1A/S6/RNG/COVERAGE"

# E — SELECTION
idx := argsort_by((-key, ISO))
winners := idx[1..K_star]
assert flags_match(idx, winners) else                         FAIL "E/1A/S6/SELECT/ORDER_MISMATCH" or "/FLAGS_DOMAIN"

# F — PERSIST
C := country_set_rows(m)
assert has_home_row(C, c, rank=0, weight_null=True) else      FAIL "E/1A/S6/PERSIST/MISSING_HOME_ROW"
assert ranks_exact(C_foreign, 1..K_star) else                 FAIL "E/1A/S6/PERSIST/RANK_GAP_OR_DUP"
assert !pk_duplicate(C) else                                  FAIL "E/1A/S6/PERSIST/PK_DUP"
S_pre := Σ(tilde_w[winner])  # from S6.3 ctx used at write
if |S_pre - 1| > 1e-12:                                       FAIL "E/1A/S6/PERSIST/WEIGHT_SUM_PREWRITE"
S_stored := Σ(row.prior_weight for row in C_foreign)
if |S_stored - 1| > 1e-6:                                     FAIL "E/1A/S6/PERSIST/WEIGHT_SUM_STORED"
assert partitions(C) == ["seed","parameter_hash","fingerprint"] else
                                                             FAIL "E/1A/S6/PERSIST/PARTITIONS"
# G — COHERENCE
for r in 1..K_star:
    e := winner_event_with_selection_order(r)
    row := country_set_row_with_rank(r)
    if e.country_iso != row.country_iso:                      FAIL "E/1A/S6/COHERENCE/EVENT_TO_TABLE"
if ∃ loser_iso in country_set_foreign:                        FAIL "E/1A/S6/COHERENCE/LOSER_IN_TABLE"
```

---

## 6) Reporting & gating (CI pass/fail)

* **Abort-merchant** codes: list `{code, merchant_id, reason, sample}`; continue run; record counts in the bundle.
* **Abort-run** codes: terminate S6 validation; write the bundle (with first hard error & diff context); block hand-off to 1B by withholding `_passed.flag`.

Always include `{seed, parameter_hash, manifest_fingerprint, run_id?}` in reports (events include `run_id`; `country_set` does not).

---

## 7) Why this taxonomy is complete & aligned

* Paths/partitions and schemas match the **dictionary** and the **Schema Authority Policy**.
* Mechanics reflect the locked S6 design: **one event per candidate**, **ISO-ascending emission**, **order-free per-candidate counters**, **cap $K^*$**, strict sort $(\text{key}↓,\ \text{ISO}↑)$, and `country_set` as the **sole order carrier**.
* Numeric policy mirrors earlier sub-states: **1e-12** for binary64 event-side sums; **8-dp stored** with **1e-6** tolerance in `country_set`.

---

### One-liner

S6.8 gives you a **single, unambiguous error map**—updated for **ISO-ascending, no-`u` events** and **fingerprint-partitioned `country_set`**—so CI can fail fast, precisely, and reproducibly on any drift from the locked S6 design.

---

# S6.9 — Inputs → Outputs (state boundary)

## 1) What S6 *consumes* (per merchant $m$)

**From earlier states (deterministic):**

* **Eligibility & home:** $e_m\in\{0,1\}$ and home ISO $c$ from S3. Only $e_m=1$ merchants enter S4–S6. Ineligible $e_m=0$ merchants **skip S4–S6** and later have only the `rank=0` home row.
* **Accepted foreign count:** $K_m\ge 1$ from S4 (ZTP accepted). If S4 exhausted retries, the merchant never reaches S6.
* **Merchant currency:** $\kappa_m$ from S5.0 cache `merchant_currency` (parameter-scoped; **never recomputed**).
* **Currency→country priors** for $\kappa_m$: ISO-ordered rows $\{(i,w_i^{(\kappa_m)})\}$ from S5 cache `ccy_country_weights_cache`.
* **RNG lineage:** `seed:uint64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`, plus a `run_id` for event logs.

**From S6.0:** the **effective** winners count $K_m^\star=\min(K_m, M_m)$ with $M_m=|\mathcal D(\kappa_m)\setminus\{c\}|$. If $M_m=0$ S6.0 has already persisted **home-only** and there are **no** S6 RNG events for $m$.

---

## 2) What S6 *produces* (authoritative artefacts on disk)

When S6 completes (for any merchant that reached it), **exactly one** of these branch outcomes exists on disk:

### A) Eligible merchant with $K_m^\star \ge 1$

1. **RNG event stream — per-candidate Gumbel keys**
   **Path & partitions (dictionary-pinned):**

   ```
   logs/rng/events/gumbel_key/
     seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
   ```

   **Schema:** `schemas.layer1.yaml#/rng/events/gumbel_key`.
   **Exactly $M_m$ rows** for merchant $m$, **one per foreign candidate**, **emitted ISO-ascending** by `country_iso`. Every row carries the full RNG envelope (`ts_utc`, `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label="gumbel_key"`, and pre/post Philox counters) with **counter delta = 1**.
   **Payload:** `weight` (foreign-renormalised $\tilde w_i$, binary64), `key` $= \log \tilde w_i - \log(-\log u_i)$ (finite), `selected` (bool), `selection_order` (1..$K_m^\star$ or `null`), plus `{K_raw, M, K_eff}`. *(Events do **not** log `u`; validators replay it from the envelope.)*

2. **Allocation dataset — ordered winners (the sole order authority)**
   **Path & partitions (dictionary-pinned):**

   ```
   data/layer1/1A/country_set/
     seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/part-*.parquet
   ```

   **Schema:** `schemas.1A.yaml#/alloc/country_set`.
   **Exactly $K_m^\star+1$ rows** for $m$: the home row `(is_home=true, rank=0, prior_weight=null)` and $K_m^\star$ foreign rows in **Gumbel order** `(is_home=false, rank=r, prior_weight=round8(\tilde w_{i_r}))`, $r=1..K_m^\star$. `country_set` is the **only** authoritative store for inter-country order.

**Cross-artefact coherence (must hold on disk).** For each winner with `selection_order=r` in `gumbel_key`, there exists **exactly one** `country_set` row with the same `(merchant_id, country_iso)` and `rank=r`. Any mismatch is a validation failure.

---

### B) Eligible merchant with **no foreign candidates** $(M_m=0)$

S6.0 persisted **home-only** to `country_set` (`rank=0`, `prior_weight=null`) and **emitted no `gumbel_key` events** for $m$. This short-circuit is complete; hand off to S7.

---

### C) Ineligible merchant $(e_m=0)$

S6 does not run for $m$. Later persistence shows only the home row (`rank=0`). Presence of S4–S6 events for $e_m=0$ is a branch-coherence failure validated elsewhere.

---

## 3) Determinism, idempotence, and replay guarantees at the boundary

* **Bit-replay.** With fixed $(\tilde w,\ K_m^\star,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the uniforms $u$, keys $z$, winner set, and `country_set.rank` are **bit-identical** (counter-based Philox, open-interval $u$, one-draw-per-candidate, deterministic tie-break).
* **Idempotent write.** `country_set` is partitioned by `{seed, parameter_hash, fingerprint}` and keyed by `(merchant_id,country_iso)`; re-runs **upsert** rows (no duplicate PKs; ranks remain $\{0..K^*\}$).
* **Schema authority.** Only JSON-Schema (`schemas.1A.yaml`, `schemas.layer1.yaml`) is authoritative; AVSC is non-authoritative in 1A.
* **Numeric policy.** Event-side sums use binary64 with $|\sum \tilde w - 1|\le 10^{-12}$ (serial). Stored `country_set.prior_weight` values are rounded to **8 dp** at write; read-sum tolerance $\le 10^{-6}$.

---

## 4) Minimal **handoff record** (normative, language-agnostic)

Downstream (S7) may treat S6’s outcome for merchant $m$ as:

```text
S6_OUTCOME(m) =
{
  lineage: {
    seed:uint64,
    parameter_hash:hex64,
    manifest_fingerprint:hex64,
    run_id   # events only; not present in country_set partitions
  },
  home_iso: c,
  K_star: K_m^*,                    # 0 means home-only
  candidates: {
    # Present iff K_star ≥ 1
    events_path:
      "logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/",
    rows: M_m,                       # one per foreign candidate
    key_sort: "(-key, ISO)",         # S6.5 ordering key
    winners: [                       # Gumbel order (r = 1..K*)
      {iso: i_1, rank: 1, prior_weight: round8(tilde_w[i_1])},
      ...,
      {iso: i_K*, rank: K*, prior_weight: round8(tilde_w[i_K*])}
    ]
  },
  country_set_path:
    "data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/fingerprint={manifest_fingerprint}/"
}
```

**Order consumption rule.** S7 (and any downstream) **must** obtain the ordered foreign list from `country_set.rank` (0 = home; 1..$K^*$ foreigns). Egress artefacts (e.g., `outlet_catalogue`) do **not** encode inter-country order; they must join on `country_set`.

---

## 5) What S7 can **assume** (hard contracts)

1. If $K_m^\star=0$: `country_set` has **exactly one** row for $m$ — `(is_home=true, rank=0, prior_weight=null)` — and there are **no** `gumbel_key` events.
2. If $K_m^\star\ge 1$:

   * `country_set` has **exactly $K_m^\star+1$** rows with contiguous ranks $0..K_m^\star$.
   * Foreign `prior_weight` values are finite, in $(0,1]$, and **read-sum to 1 within $10^{-6}$** (8-dp storage); the corresponding event-side $\tilde w$s read-sum to 1 within $10^{-12}$.
   * The winners’ ISO sequence equals the first $K_m^\star$ elements of `argsort_by((-key, ISO))` reconstructed from `gumbel_key`.
3. **Partitioning:** S7 finds `country_set` under `{seed, parameter_hash, fingerprint}`; `gumbel_key` under `{seed, parameter_hash, run_id}`.
4. **Lineage:** `manifest_fingerprint` is persisted as a column in `country_set` and used in joins/audits.

---

## 6) Acceptance checklist (CI must assert before hand-off)

For every merchant that reached S6:

* **Files present & partitioned** exactly as above; schemas validate against JSON-Schema.
* **Coverage:** $|\text{gumbel_key}_m| = M_m$ (or **0** if $K_m^\star=0$). Each event has `after = before + 1`; events are **ISO-ascending**.
* **Order coherence:** winners’ `selection_order=r` ↔ `country_set.rank=r`; losers absent from `country_set`.
* **Weights:**
  – Events: $|\sum \tilde w - 1| \le 10^{-12}$ (serial).
  – Table: $|\sum \texttt{prior_weight} - 1| \le 10^{-6}$ (8-dp storage).
* **Home row:** exactly one `(is_home=true, rank=0, prior_weight=null)`.

Only when this checklist passes does S6 expose a clean boundary to S7 (and contribute to the `_passed.flag` gate used by 1B).

---

### One-liner

**S6 in → S6 out:** given $(K_m,\ \kappa_m,\ \text{weights},\ \text{lineage})$, S6 leaves a deterministic pair — **ISO-ascending `gumbel_key` (one row per candidate, replayable keys)** and **`country_set` (the sole carrier of order under `{seed, parameter_hash, fingerprint}`)** — so S7 can just **join on `rank`** and proceed.

---