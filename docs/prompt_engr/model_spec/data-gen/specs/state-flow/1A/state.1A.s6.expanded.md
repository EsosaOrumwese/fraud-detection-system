# S6.0 — Pre-screen / cap with candidate size $M_m$

## 1) Purpose & placement

S6.0 sits at the front of S6. Its sole job is to:

1. compute the **foreign candidate count** $M_m$ for merchant $m$ (home excluded),
2. set the **effective selection size** $K_m^\star=\min(K_m,M_m)$, and
3. short-circuit to a **home-only** allocation if $M_m=0$ (no RNG, no `gumbel_key`), then hand off to S7.

It **does not** draw randomness, score keys, or persist winners; that happens in later S6 steps. `country_set` is the *only* authority for cross-country order (S6 writes it).

---

## 2) Inputs (deterministic, read-only)

Per merchant $m$:

* **Foreign target from S4:** $K_m\in\{1,2,\dots\}$ (accepted ZTP count). S4 may also downgrade/abort merchants, which skip S6 entirely.
* **Home ISO:** $c \in \mathcal I$ (ISO-3166 alpha-2), from normalised ingress.
* **Settlement currency:** $\kappa_m\in\mathrm{ISO4217}$ (read from `merchant_currency`, fixed in S5.0).
* **Currency→country prior weights (from S5 cache):** rows $\{(\kappa_m,i,w_i^{(\kappa_m)}) : i \in \mathcal D(\kappa_m)\}$ with $\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}=1$. (These are ordered by ISO and schema-validated in S5.)

> S6.0 only *reads* the S5 cache to know which destinations exist for $\kappa_m$. Normalisation and RNG happen after S6.0.

---

## 3) Mathematical definitions

Given the ISO-ordered S5 expansion $\mathcal D(\kappa_m)\subset\mathcal I$:

1. **Foreign candidate set (home excluded):**

$$
\boxed{\ \mathcal F_m \;=\; \mathcal D(\kappa_m)\setminus\{c\}\ }.
$$

2. **Available candidate count:**

$$
\boxed{\ M_m \;=\; |\mathcal F_m|\ }.
$$

3. **Effective selection size (cap):**

$$
\boxed{\ K_m^\star \;=\; \min\!\big(K_m,\;M_m\big)\ }.
$$

**Branch rule.**

* If $M_m=0$: set $K_m^\star=0$, write **home-only** `country_set` (`rank=0`), **emit no `gumbel_key`**, record reason `"no_candidates"` for validation, then jump to S7.
* If $M_m < K_m$: proceed with the **cap** $K_m^\star$ (validators assert $0\le K_m^\star\le M_m$).

---

## 4) What is (and isn’t) persisted in S6.0

### Home-only short-circuit (when $M_m=0$)

Persist exactly one row to **`country_set`** and **no RNG events**:

* **Dataset & partitions (dictionary-pinned):**

  ```
  data/layer1/1A/country_set/
    seed={seed}/parameter_hash={parameter_hash}/part-*.parquet
  ```

  *(Partitioned by `{seed, parameter_hash}`; `run_id` is for event logs, not allocations.)*

* **Row (authoritative schema semantics):**

  ```
  merchant_id = m
  country_iso = c            # home ISO
  is_home     = true
  rank        = 0
  prior_weight = null        # home has no prior weight
  ```

  **PK** = `(merchant_id, country_iso)`. `country_set` is the *sole* authority for cross-country order.

* **No `gumbel_key`** events are emitted in S6.0’s home-only branch. The validator may record `"no_candidates"` as the reason in its bundle (non-dataset telemetry).

### Non-short-circuit case (when $M_m\ge 1$)

S6.0 **persists nothing** here. It only computes and exposes $K_m^\star$ to S6.3–S6.6 (which will later log `gumbel_key` and persist the full `country_set`).

---

## 5) Contracts & invariants established by S6.0

* **C-1 (cap correctness):** $0 \le K_m^\star \le M_m$ and $K_m^\star=\min(K_m,M_m)$ for *every* merchant reaching S6.0.
* **C-2 (home-only correctness):** $M_m=0 \iff$ exactly one `country_set` row exists with `(is_home=true, rank=0, prior_weight=null)`, and **no `gumbel_key` events** for $m$.
* **C-3 (no RNG):** S6.0 consumes and emits **no** randomness. RNG begins only if $K_m^\star\ge1$ (later S6 steps).
* **C-4 (authority flow):** `country_set` remains the **only** authority for cross-country order; even when home-only, rank semantics are enforced (`rank=0` only).

---

## 6) Edge cases & notes

* **Home not in $\mathcal D(\kappa_m)$:** Then $\mathcal F_m = \mathcal D(\kappa_m)$, so $M_m = |\mathcal D(\kappa_m)|$. This is allowed; S6.3 will still renormalise on $\mathcal F_m$. S6.0 logic is unchanged. (S5 FK/order rules already guarantee unique ISO members.)
* **Currency with one member equal to home:** $\mathcal D(\kappa_m)=\{c\}\Rightarrow M_m=0$. S6.0 writes the home-only row and ends S6 for $m$.
* **Foreign mass equals zero (but $M_m > 0$):** S6.0 does not examine weights; S6.3 will detect zero foreign mass during renormalisation and fail accordingly (that failure belongs to S6.3/S6.8).
* **$K_m=0$ merchants:** By design, these skip S5–S6 entirely via S3/S4 branching; S6.0 is not entered.

---

## 7) Language-agnostic reference algorithm (normative)

```text
FUNCTION S6_0_prescreen_and_cap(m):
  INPUT:
    merchant_id m
    K_raw := K_m from S4           # integer ≥1 (by S4 acceptance)
    c     := home ISO for m        # ISO2, validated in S0
    κ     := kappa_m for m         # ISO4217, from S5.0 merchant_currency
    Wκ    := { (i, w_i) rows for currency=κ }  # from S5 weights cache (ISO-ordered)

  PRECHECKS (defensive; may also be asserted in S6.2):
    assert K_raw ≥ 1
    assert |Wκ| ≥ 1                             # missing currency weights → S6.8 failure
    # (Do not check sums/positivity here; S6.3 will.)

  STEP 1: Build foreign candidate set (home excluded)
    F := [ i for (i, _) in Wκ if i != c ]      # preserves ISO order from Wκ
    M := length(F)

  STEP 2: Effective selection size (cap)
    K_eff := min(K_raw, M)

  STEP 3: Branch on availability
    if M == 0:
        # Home-only short-circuit (no RNG, no gumbel_key)
        write country_set row:
           { merchant_id=m, country_iso=c, is_home=true, rank=0, prior_weight=null }
           to path data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/...
        record validator_reason[m] := "no_candidates"
        RETURN {K_eff=0, status="home_only_persisted"}
    else:
        RETURN {K_eff=K_eff, F=F, status="proceed_to_S6.3"}
```

**Determinism.** The procedure is pure and contains no RNG; given fixed inputs, outputs are identical across replays.

---

## 8) Failures attributable to S6.0 (scope-limited)

S6.0 itself will **abort** only on structural preconditions necessary to compute $M_m$:

* **E/1A/S6/INPUT/MISSING_WEIGHTS** — `ccy_country_weights_cache` has **no rows** for $\kappa_m$. (Input precondition to S6; this is also listed in S6.8.) **Action:** abort merchant.
* **E/1A/S6/SCHEMA/COUNTRY_SET_HOME_ROW** — when $M_m=0$, the writer fails PK/shape for the home row (e.g., bad ISO or wrong partitions). **Action:** abort run (persistence/layout error).

All other math/schema failures (renormalisation, event envelope, selection order, country_set/winners coherence) are owned by S6.2–S6.8.

---

## 9) Complexity & numerics

* **Time:** $O(|\mathcal D(\kappa_m)|)$ to filter out `home`.
* **Memory:** $O(|\mathcal F_m|)$ to carry the ISO list $F$ (if proceeding).
* **Numerics:** S6.0 performs no floating-point computations and no sums.

---

## 10) Acceptance checks (what “done” means for S6.0)

For each merchant $m$ entering S6:

* If $M_m=0$: exactly **one** `country_set` row (home) persisted under `seed={seed}/parameter_hash={parameter_hash}`, no `gumbel_key` events for $m$, and $K_m^\star=0$.
* If $M_m\ge1$: S6.0 emits no data, exposes $K_m^\star=\min(K_m,M_m)$, and passes $\mathcal F_m$ to S6.3. Validator later asserts $0\le K_m^\star\le M_m$.

---

### One-line takeaway

S6.0 deterministically computes $M_m$, caps $K_m$ to $K_m^\star$, and—when no foreign candidates exist—**writes the home-only `country_set` row and emits no RNG**, ending S6 for that merchant. Otherwise, it hands $(\mathcal F_m, K_m^\star)$ forward to S6.3 for renormalisation and Gumbel selection.

# S6.1 — Universe, symbols, authority

## 1) Placement & purpose

S6 takes the deterministic **currency→country priors** from S5, drops the merchant’s home ISO, renormalises over the foreign set, and performs **weighted sampling without replacement** via **Gumbel-top-$K$** to select the ordered foreign countries. S6 also emits one RNG event **per candidate** (`gumbel_key`) and persists the ordered winners to `country_set`, which becomes the **only** authority for cross-country order.

---

## 2) Domain: who enters S6

Evaluate S6 **only** for merchants $m$ that:

1. are multi-site (`is_multi=1`, S1),
2. passed cross-border eligibility (`is_eligible=1`, S3), and
3. have **effective foreign count** $K_m^\star \ge 1$ after S6.0’s cap $K_m^\star=\min(K_m,M_m)$, where $M_m$ is the number of foreign candidates (home excluded). When $M_m=0$, S6 writes only the home row (rank 0) and **does not** emit `gumbel_key` events (S6.0 short-circuit).

**Authority for the ordered result.** For $K_m^\star\ge 1$, S6 persists **home + $K_m^\star$ foreigns** to `country_set` with `rank=0` for home and `rank=1..K_m^\star` for winners **in Gumbel order**. `country_set` is explicitly the **only** authority for cross-country order in 1A.

---

## 3) Symbols & notation (fixed for all of S6)

Per merchant $m$:

* $c\in\mathcal I$: home ISO-3166 alpha-2.
* $\kappa_m\in\text{ISO4217}$: settlement currency (read from S5.0 `merchant_currency`; S6 never recomputes $\kappa_m$).
* $\mathcal D(\kappa_m)\subset\mathcal I$: currency member set from S5 cache `ccy_country_weights_cache`, with weights $w_i^{(\kappa_m)}$ satisfying $\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}=1$ and stored **in ISO ASCII order**.
* **Foreign candidate set**: $\mathcal F_m=\mathcal D(\kappa_m)\setminus\{c\}$.
* **Count & cap**: $M_m=|\mathcal F_m|,\quad K_m^\star=\min(K_m,M_m)$. (If $M_m=0$ → S6.0 home-only branch.)
* **Foreign-renormalised weights** (defined/used later in S6.3): $\tilde w_i=\dfrac{w_i^{(\kappa_m)}}{\sum_{j\in\mathcal F_m} w_j^{(\kappa_m)}}$ for $i\in\mathcal F_m$, so $\sum_{i\in\mathcal F_m}\tilde w_i=1$. (S6 uses **serial** binary64 sums; tolerance $10^{-12}$.)

---

## 4) Selection mechanism (mathematical statement)

S6 performs **weighted sampling without replacement** using **Gumbel-top-$K$**. For each foreign candidate $i\in\mathcal F_m$, draw **exactly one** open-interval uniform $u_i\in(0,1)$ (RNG details and the bit-exact mapping are specified in S6.4), compute the key

$$
\boxed{\,z_i = \log \tilde w_i - \log\!\bigl(-\log u_i\bigr)\,}.
$$

Let the strict total order $\succ$ be “**key descending**, then **ISO ASCII ascending**” (lexicographic tie-break if keys are bit-equal). The winners are the **top $K_m^\star$** elements under $\succ$; their **selection order** $r=1,\dots,K_m^\star$ is induced by the sort. This consumes **one** uniform per candidate ($|\mathcal F_m|=M_m$) and is fully replayable from the RNG envelope.

---

## 5) Authoritative artefacts (schemas, paths, partitions)

### RNG event stream — `gumbel_key` (always emitted when $M_m\ge 1$)

* **Path pattern (dictionary-pinned):**
  `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (one **event per candidate**, so exactly $M_m$ rows for merchant $m$).
* **Schema:** `schemas.layer1.yaml#/rng/events/gumbel_key` (envelope + payload). Envelope includes `{ts_utc, run_id, seed:uint64, parameter_hash:hex64, manifest_fingerprint:hex64, module, substream_label="gumbel_key", rng_counter_before/after_{lo,hi}}`. Payload includes `{merchant_id, country_iso=i, weight=tilde_w_i, u, key=z_i, selected, selection_order}`. **Exactly one** Philox draw per event.
* **Determinism & coverage:** validators assert $|\text{events}_m|=M_m$; selected rows have `selected=true` with `selection_order∈{1..K_m^\star}`; non-selected rows carry `selected=false`, `selection_order=null`.

### Allocation dataset — `country_set` (the only authority for order)

* **Path pattern (dictionary-pinned):**
  `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/` (partitioned by `{seed, parameter_hash}`; **no `run_id`** in the allocation dataset).
* **Schema:** `schemas.1A.yaml#/alloc/country_set`.
  **PK** `(merchant_id, country_iso)`.
  **Rows per merchant:** exactly $K_m^\star+1$:
  `(m,c,is_home=true, rank=0, prior_weight=null)` and, for winners $(i_1,\dots,i_{K_m^\star})$ in Gumbel order,
  `(m,i_r,is_home=false, rank=r, prior_weight=\tilde w_{i_r}), r=1..K_m^\star`.
  The dataset **stores** inter-country order via `rank`; all downstream consumers **must** join on `rank`.
* **Coherence with events:** any merchant having a `gumbel_key.selected=true` must have matching `country_set` rows with `rank = selection_order`. Any mismatch is a validation failure; domestic/downgraded merchants still have **only** the home row (`rank=0`).

**Upstream authority reminder.** S6 reads S5’s parameter-scoped caches (partitioned by `{parameter_hash}`), especially `ccy_country_weights_cache`, as the sole source for the currency expansion $\mathcal D(\kappa)$ and priors $w^{(\kappa)}$. S5’s caches are deterministic, FK-clean, and ISO-ordered.

---

## 6) Determinism & invariants (established at the S6 level)

* **Bit-replay (I-G1).** For fixed $(\tilde w,\ K_m^\star,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the vector of uniforms $(u_i)$, keys $(z_i)$, winner set $S_m$, and persisted ranks are **bit-identical** across replays.
* **Event coverage (I-G2).** Exactly $M_m$ `gumbel_key` events per merchant; winners have `selected=true` and `selection_order∈{1..K_m^\star}`; others are marked as losers.
* **Weight & ISO constraints (I-G3).** Each event row has `country_iso` passing ISO FK and `weight∈(0,1]` with serial sum $\sum_{i\in\mathcal F_m}\tilde w_i=1$ within $10^{-12}$.
* **Tie-break determinism (I-G4).** If $z_i=z_j$ at binary64, order by **ISO ASCII**; the selection order is a pure function of $(\tilde w,u)$.
* **Country-set coherence (I-G5).** Persist exactly one home row (`rank=0`) plus $K_m^\star$ foreign rows in the **same order** as the winners’ `selection_order`; any mismatch is a failure.

---

## 7) Out-of-scope here (covered in later substates)

* **S6.2** pins the exact inputs and lineage checks (presence of S5 weights; schema shapes; envelope).
* **S6.3** defines the renormalisation on $\mathcal F_m$ (serial sums; positivity).
* **S6.4** specifies the RNG protocol: keyed substream mapping, **open-interval** $u$ mapping, and event counters (one Philox block per candidate).
* **S6.5–S6.6** codify the total-order sort and the `country_set` writer.

---

### One-line takeaway

S6.1 locks the playing field: who runs, the math objects $(\mathcal F_m, M_m, K_m^\star, \tilde w, z)$, and the **only** two authorities—`gumbel_key` (one event per candidate) and `country_set` (ranked winners; the sole source of country order)—with dictionary-pinned paths, partitions, and deterministic invariants.

---

# S6.2 — Inputs & lineage checks

## 1) Scope & purpose

S6.2 assembles the **deterministic context** needed by S6.3–S6.6:

* Merchant identity + home ISO $c$.
* S4’s accepted foreign-count $K_m$ and S6.0’s **effective** cap $K_m^\star$.
* Merchant currency $\kappa_m$ (from S5.0 cache).
* Currency→country **weights cache** (S5) for $\kappa_m$, giving the ISO-ordered candidate set $\mathcal D(\kappa_m)$ and base weights $w_i^{(\kappa_m)}$.
* **Lineage envelope** fields: `seed`, `parameter_hash`, `manifest_fingerprint`, and a `run_id` for event logs.

If any of these are missing or malformed, **S6 must not proceed** to RNG or persistence.

---

## 2) Authoritative sources (what we read, where, and why)

* **Merchant currency $\kappa_m$ (S5.0 cache).**
  Dataset `merchant_currency`, partitioned by `{parameter_hash}`, schema `schemas.1A.yaml#/prep/merchant_currency`. **S6 must read, not recompute, $\kappa_m$.**

* **Currency→country weights (S5 cache).**
  Dataset `ccy_country_weights_cache`, partitioned by `{parameter_hash}`, schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`. This cache deterministically defines $\mathcal D(\kappa)$ and $w_i^{(\kappa)}$; rows are **ASCII-sorted by `country_iso`** per currency and sum to 1 (tol $10^{-6}$).

* **Allocation dataset target.**
  `country_set`, partitioned by `{seed, parameter_hash}`, schema `schemas.1A.yaml#/alloc/country_set`. **S6 will write** this later; we reference it here to tie lineage and partition expectations. `country_set` is the **only** authority for cross-country order (via `rank`).

* **RNG event stream target.**
  `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`, schema `schemas.layer1.yaml#/rng/events/gumbel_key`. One **event per candidate** when $K_m^\star\ge 1$. (S6.4 will emit; S6.2 asserts the lineage & shapes exist.)

---

## 3) Inputs per merchant $m$ (deterministic)

Let the (read-only) input tuple be:

$$
I_m=\big(m,\ c,\ K_m,\ K_m^\star,\ \kappa_m,\ \mathcal D(\kappa_m),\ \{w_i^{(\kappa_m)}:i\in\mathcal D(\kappa_m)\},\ E\big),
$$

where:

* $m=\texttt{merchant_id}$ (id64) and $c\in\mathcal I$ (ISO-3166 alpha-2), from the normalised merchant snapshot (S0/S1 lineage).
* $K_m\in\{1,2,\dots\}$ from S4 acceptance; $K_m^\star=\min(K_m,M_m)$ from S6.0 (with $M_m=|\mathcal D(\kappa_m)\setminus\{c\}|$). **If $M_m=0$ then S6.0 already wrote the home-only `country_set` and we skip S6.2–S6.6 for $m$.**
* $\kappa_m$ from `merchant_currency` cache (parameter-scoped). **Do not recompute**.
* $\mathcal D(\kappa_m)$ and $w_i^{(\kappa_m)}$ from `ccy_country_weights_cache` (parameter-scoped, ISO-ordered rows that sum to 1).
* **Lineage envelope $E$:**
  `seed:uint64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`, and `run_id` (events-scoped). These keys define partitions for `gumbel_key` and `country_set` as per the dictionary.

---

## 4) Preconditions & structural checks (must pass before S6.3)

S6.2 enforces these **deterministic** conditions; any failure aborts (merchant or run), preventing RNG emission later.

### C-1 Currency presence & shape

* A row exists for $\kappa_m$ in `merchant_currency/parameter_hash={parameter_hash}/…`. Else: **fail** `E/1A/S6/INPUT/MISSING_KAPPA`.
* Weights exist for $\kappa_m$ in `ccy_country_weights_cache/parameter_hash={parameter_hash}/…`. Else: **fail** `E/1A/S6/INPUT/MISSING_WEIGHTS`. (This is also listed as a locked S6 failure.)

### C-2 ISO ordering & coverage (trust-but-verify)

* Collect rows for $\kappa_m$ and assert **strict ASCII order** by `country_iso`. Else: **ordering breach** `E/1A/S6/INPUT/WEIGHTS_ORDER`. (S5 writers already enforce this; S6 verifies before using).
* Let $\mathcal D(\kappa_m)$ be exactly the set of `country_iso` for that currency; $D=|\mathcal D(\kappa_m)|\ge 1$. (If $D=1$ and the sole member equals $c$, S6.0 already short-circuited.)

### C-3 Sum & range sanity (defensive echoes of S5 invariants)

* Compute $S=\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}$ serially (ISO order) in binary64; assert $|S-1|\le 10^{-6}$. Else: **fail** `E/1A/S6/INPUT/WEIGHTS_SUM`. (S5 schema enforces this; we double-check to avoid propagating corruption.)
* Assert each $w_i^{(\kappa_m)}\in[0,1]$ and is **finite**. Else: **fail** `E/1A/S6/INPUT/WEIGHTS_RANGE`.

### C-4 Eligibility & cap coherence

* Ensure $K_m^\star$ is present from S6.0 and satisfies $0\le K_m^\star\le M_m$ with $M_m=|\mathcal D(\kappa_m)\setminus\{c\}|$. If $M_m=0$, **S6.0 already persisted home-only** and S6.2 must **skip** this merchant. Else if $K_m^\star<1$ but $M_m\ge1$: **fail** `E/1A/S6/INPUT/BAD_CAP`.

### C-5 Lineage envelope readiness (before any events)

* The process has a concrete `{seed, parameter_hash, run_id}` and a `manifest_fingerprint` for this run; these **must** match the dictionary’s partition patterns:

  * `gumbel_key` → partitioned by `{seed, parameter_hash, run_id}`.
  * `country_set` → partitioned by `{seed, parameter_hash}` (**no `run_id`**).
    If absent/mismatched: **fail** `E/1A/S6/LINEAGE/PARTITIONS`.

> Note: Counter mapping and the **open-interval** $u$ construction are specified in S6.4. S6.2 only asserts the **presence** of envelope keys and partition semantics.

---

## 5) What S6.2 does **not** do

* It does **not** renormalise weights on the foreign set (S6.3).
* It does **not** open the RNG stream, draw uniforms, or emit events (S6.4).
* It does **not** persist `country_set` rows (S6.6).
  It is a pure **gatekeeper** step ensuring that later stages run with **valid, auditable inputs**.

---

## 6) Language-agnostic reference algorithm (normative)

```text
FUNCTION S6_2_inputs_and_lineage_check(m):
  INPUT:
    merchant_id m
    home_iso c                       # ISO2
    K_raw from S4 (int ≥ 1)
    K_eff from S6.0 (int ≥ 0)        # = min(K_raw, M_m); S6.0 set it
    parameter_hash (hex64)
    manifest_fingerprint (hex64)
    seed (uint64), run_id
  READ:
    κ := merchant_currency[parameter_hash].lookup(m).kappa
    Wκ := rows from ccy_country_weights_cache[parameter_hash] where currency = κ
         # expect |Wκ| ≥ 1; ISO-ordered; sum of weight = 1
  DERIVE:
    D := length(Wκ)
    ISO_list := [country_iso of each row in Wκ]            # in stored order
    assert ISO_list is strictly ASCII-ascending            # C-2
    S := Σ weight over Wκ (serial, binary64)
    assert |S - 1| ≤ 1e-6 and all weights finite ∈ [0,1]   # C-3
    F := [i in ISO_list where i != c]                      # preserves order
    M := length(F)
    if M == 0:
        # S6.0 should have short-circuited; do not proceed here
        return SKIP_MERCHANT("home_only_already_written_by_S6.0")
    assert 0 ≤ K_eff ≤ M and K_eff ≥ 1                     # C-4
    # Partition lineage present and consistent with dictionary:
    assert country_set partitions == {seed, parameter_hash}
    assert gumbel_key partitions == {seed, parameter_hash, run_id}   # C-5
  OUTPUT (to S6.3):
    Context record:
      { merchant_id=m, home=c, kappa=κ,
        candidates=F (ISO order),
        base_weights=[w_i of i∈F in the same order],
        K_star=K_eff,
        lineage={seed, parameter_hash, run_id, manifest_fingerprint} }
```

Determinism: this function is **pure** and emits no RNG or persistence side-effects. Given fixed inputs, the context record is byte-identical across replays.

---

## 7) Failure taxonomy (owned by S6.2)

These error codes are raised **here** (S6.8 will enumerate them again):

* `E/1A/S6/INPUT/MISSING_KAPPA` — no `merchant_currency` row for $m$. **Abort merchant.**
* `E/1A/S6/INPUT/MISSING_WEIGHTS` — no weights for $\kappa_m$. **Abort merchant.**
* `E/1A/S6/INPUT/WEIGHTS_ORDER` — weights not in ASCII ISO order. **Abort run** (cache corruption).
* `E/1A/S6/INPUT/WEIGHTS_SUM` or `/WEIGHTS_RANGE` — sum≠1 (tol) or non-finite/out-of-range weight. **Abort run**.
* `E/1A/S6/INPUT/BAD_CAP` — $K_m^\star$ missing or not in $[1,M_m]$ when $M_m\ge1$. **Abort run.**
* `E/1A/S6/LINEAGE/PARTITIONS` — partition keys for `gumbel_key`/`country_set` not as per dictionary. **Abort run.**

---

## 8) Acceptance checks (what “done” means for S6.2)

For every merchant that reaches S6.2:

* We have a context record with `{m, c, κ, F (ISO order), base_weights on F, K_m^\star ≥ 1, lineage}`.
* All C-1…C-5 predicates hold.
* No events written, no RNG consumed, no `country_set` rows written yet.
* If $M_m=0$, merchant **did not** enter S6.2 (S6.0 already persisted home-only).

---

### One-liner

S6.2 is the **gatekeeper**: it proves we have the right currency, the right ISO-ordered weights, a valid cap $K_m^\star$, and correct lineage partitions—so S6.3 can renormalise and S6.4 can safely open the RNG stream.

---

# S6.3 — Candidate set & renormalisation

## 1) Purpose & placement

Given the S6.2 context for merchant $m$ — home ISO $c$, currency $\kappa_m$, S5 weights $w^{(\kappa_m)}$ over $\mathcal D(\kappa_m)$, and the effective cap $K_m^\star$ from S6.0 — build the **foreign** candidate set $\mathcal F_m$ by excluding the home, then renormalise the weights on $\mathcal F_m$ to obtain a probability vector $\tilde w$ that sums to 1 (binary64, serial). This $\tilde w$ is the **only** weight used to compute Gumbel keys in S6.4–S6.5.

---

## 2) Inputs (from S6.2; read-only)

* $m$ (merchant id), $c\in\mathcal I$ (home ISO).
* $\kappa_m\in\mathrm{ISO4217}$ from `merchant_currency` (parameter-scoped).
* ISO-ordered S5 rows for $\kappa_m$: $\{(i, w_i^{(\kappa_m)}) : i\in\mathcal D(\kappa_m)\}$ with $\sum_{i\in\mathcal D(\kappa_m)} w_i^{(\kappa_m)}=1$ (schema-checked), and each `country_iso` ISO-valid.
* $K_m^\star=\min(K_m,M_m)$ from S6.0 (already computed; **do not** use raw $K_m$ after S6.0).

Guards from S6.2 already ensured currency presence, ISO ordering, group-sum $=1$ (tol $10^{-6}$) and basic lineage readiness; S6.3 assumes those passed.

---

## 3) Mathematical construction (canonical)

### 3.1 Foreign candidate set (home excluded)

$$
\boxed{\ \mathcal F_m \;=\; \mathcal D(\kappa_m)\setminus\{c\},\quad M_m = |\mathcal F_m| \ }.
$$

Use the **stored ISO order** from S5 for the iteration order of $\mathcal F_m$. If $M_m=0$, S6.0 has already short-circuited to home-only and S6.3 **does not run** for this merchant.

### 3.2 Foreign mass (serial sum, binary64)

$$
T_m \;=\; \sum_{j\in\mathcal F_m} w^{(\kappa_m)}_j\quad\text{(single-thread serial left-fold in ISO order).}
$$

No parallel reductions or reordering; this preserves determinism across platforms.

### 3.3 Renormalisation to $\tilde w$ on $\mathcal F_m$

$$
\boxed{\ \tilde w_i \;=\; \frac{w^{(\kappa_m)}_i}{T_m}\quad \text{for } i\in\mathcal F_m\ },\qquad
\sum_{i\in\mathcal F_m}\tilde w_i \;=\; 1\ \ (\text{within }10^{-12}).
$$

S6 enforces $\tilde w_i>0$ for all $i\in\mathcal F_m$. This holds given S5’s decision surface (equal-split, smoothed, or raw with $\min y_i\ge T$). Violations are treated as upstream corruption.

> **Note on the expanded draft:** it suggested aborting if $K_m > M_m$. The **locked** S6 caps to $K_m^\star=\min(K_m,M_m)$ in S6.0; S6.3 therefore **never** aborts on $K_m > M_m$. We use $K_m^\star$ from now on.

---

## 4) Numeric policy & tolerances (strict)

* **Arithmetic:** IEEE-754 binary64.
* **Reductions:** single-thread serial left-fold in the S5 ISO order (no parallel, no re-order).
* **Foreign mass positivity:** require $T_m>0$. (Guaranteed by S5; check defensively.)
* **Normalisation tolerance:** after forming $\tilde w$, compute $S=\sum_{i\in\mathcal F_m}\tilde w_i$ in the same serial order and assert $|S-1|\le 10^{-12}$.
* **Range:** each $\tilde w_i\in(0,1]$ and finite; any non-finite/negative is a hard failure.

---

## 5) Outputs (in-memory; consumed by S6.4–S6.6)

* Ordered foreign ISO list $\mathcal F_m = (i_1,\dots,i_{M_m})$ (ISO-ascending from S5).
* Vector $\tilde w = (\tilde w_{i_1},\dots,\tilde w_{i_{M_m}})$ aligned to $\mathcal F_m$.
* The integer $K_m^\star$ (already computed; $1\le K_m^\star\le M_m$).
  S6.3 **does not** write `gumbel_key` or `country_set`. Those are written by S6.4–S6.6.

---

## 6) Language-agnostic reference algorithm (normative)

```text
FUNCTION S6_3_build_and_renormalise(context):
  INPUT (from S6.2):
    m            # merchant_id
    c            # home ISO2
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
  assert M ≥ 1                               # S6.0 would have short-circuited otherwise
  assert 1 ≤ K_star ≤ M                      # cap coherence is enforced here defensively

  # 2) Serial foreign-mass sum (binary64)
  T ← 0.0
  for (i, w) in Wκ:
      if i ≠ c: T ← T + w
  if not (T > 0.0 and isfinite(T)):
      FAIL "E/1A/S6/RENORM/ZERO_FOREIGN_MASS"

  # 3) Renormalise
  tilde_w ← empty map
  for (i, w) in Wκ:
      if i ≠ c:
          t ← w / T
          if not (isfinite(t) and t > 0.0 and t ≤ 1.0):
              FAIL "E/1A/S6/RENORM/WEIGHT_RANGE"
          tilde_w[i] ← t

  # 4) Sum-to-one check (serial, same order)
  S ← 0.0
  for i in F: S ← S + tilde_w[i]
  if |S - 1.0| > 1e-12:
      FAIL "E/1A/S6/RENORM/SUM_TOL"

  RETURN (F, [tilde_w[i] for i in F], K_star)
```

Determinism: a pure function of the S5 rows and $c$; given the same inputs and dictionary, outputs are byte-replayable.

---

## 7) Acceptance checks (what “done” means for S6.3)

For every merchant that reaches S6.3:

1. $\mathcal F_m$ equals $\mathcal D(\kappa_m)\setminus\{c\}$ in **S5 ISO order**; $M_m\ge 1$.
2. $K_m^\star$ satisfies $1\le K_m^\star\le M_m$ (cap already applied in S6.0).
3. $T_m>0$; $\tilde w_i\in(0,1]$ and finite; $\sum_{i\in\mathcal F_m}\tilde w_i=1$ within $10^{-12}$ (serial).
4. No datasets written; context passed forward to S6.4 to open the RNG stream and emit **one** `gumbel_key` per candidate.

---

## 8) Failure taxonomy owned by S6.3 (precise triggers)

* `E/1A/S6/RENORM/ZERO_FOREIGN_MASS` — $T_m\le 0$ or non-finite. (Should not happen if S5 invariants held; treated as upstream corruption.)
* `E/1A/S6/RENORM/WEIGHT_RANGE` — some $\tilde w_i$ non-finite, $\le 0$, or $>1$.
* `E/1A/S6/RENORM/SUM_TOL` — $|\sum_{i\in\mathcal F_m}\tilde w_i - 1|>10^{-12}$ after renormalising.
* `E/1A/S6/INPUT/BAD_CAP` — $K_m^\star\notin[1,M_m]$ when $M_m\ge 1$ (defensive echo of S6.0/S6.2).
  These errors abort the merchant (or run, if systemic), before any RNG is consumed.

---

## 9) Notes & edge cases

* **Home not in $\mathcal D(\kappa_m)$**: allowed — then $\mathcal F_m=\mathcal D(\kappa_m)$, $M_m=|\mathcal D|$. S6.3 logic unchanged. (S5 already guarantees uniqueness and ISO shape.)
* **Single-member currency**: if $\mathcal D(\kappa_m)=\{c\}$ then $M_m=0$ and S6.0 wrote the home-only row; S6.3 is skipped.
* **Cap vs abort**: any reference to aborting when $K_m>M_m$ in the *expanded* text is superseded by the locked **cap** rule in S6.0; S6.3 relies on $K_m^\star$.

---

### One-liner

S6.3 deterministically turns the S5 currency expansion into an **ISO-ordered foreign list** and a **probability vector $\tilde w$** that sums to 1 (serial, tol $10^{-12}$), ready for one-uniform-per-candidate **Gumbel-top-$K_m^\star$** selection in S6.4–S6.5.

# S6.4 — RNG protocol & event contract

## 1) Purpose & placement

Given the S6.3 context $(\mathcal F_m,\ \tilde w,\ K_m^\star)$, S6.4:

1. opens the Philox substream for label **"gumbel_key"** at merchant scope;
2. draws **exactly one** open-interval uniform $u_i\in(0,1)$ per candidate $i\in\mathcal F_m$;
3. computes the Gumbel keys $z_i=\log\tilde w_i-\log(-\log u_i)$ (binary64);
4. emits one **`gumbel_key` event** per candidate with the RNG envelope + payload, ready for S6.5 to decide winners and flags.

---

## 2) Substream discipline (authoritative)

**Engine.** Philox $2\times 64$-10; all RNG JSONL events carry the **rng envelope**
$\{\texttt{ts_utc},\texttt{run_id},\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint},\texttt{module},\texttt{substream_label},\texttt{rng_counter_before_{lo,hi}},\texttt{rng_counter_after_{lo,hi}}\}$.

**Keyed substream mapping (no stride).** For label $\ell=$"gumbel_key" and merchant $m$, define the **base counter** deterministically from $(\texttt{seed},\ \texttt{manifest_fingerprint},\ \ell,\ m)$; the $i$-th uniform for that $(\ell,m)$ uses `base + i` (128-bit add with carry). This mapping is **order-invariant** across partitions and replaces any old additive “stride” idea.

**Per-event draw accounting.** Each `gumbel_key` event consumes **one** uniform; envelope counters must satisfy
$(\texttt{after_hi},\texttt{after_lo})=(\texttt{before_hi},\texttt{before_lo})+1$. Per merchant, the sum of `draws` over all events equals $M_m=|\mathcal F_m|$.

> **Deviation fixed:** The expanded draft’s per-label jump $J(\ell)$ is **not used**; S6 follows the S0 **keyed mapping** exactly. (You may still log an optional `stream_jump` telemetry row when first emitting for $(\ell,m)$; it must not alter counters.)

---

## 3) Open-interval uniform $u\in(0,1)$ — bit-exact transform

Given one 64-bit unsigned integer $x$ from a Philox block (we **discard** the other lane), define

$$
\boxed{\,u=\frac{x+1}{2^{64}+1}\in(0,1)\,}.
$$

This is the **sole** `u01` mapping used in 1A (open interval; one counter increment ⇒ one uniform; one 64-bit lane ⇒ one uniform). **Do not** use the 53-bit “top-bits+half-ulp” variant from the expanded text.

---

## 4) Key computation & numeric guards

For each candidate $i\in\mathcal F_m$, with $\tilde w_i>0$ from S6.3:

$$
g_i=-\log\!\bigl(-\log u_i\bigr),\qquad
\boxed{\,z_i=\log \tilde w_i+g_i\,}.
$$

**Binary64** throughout; precompute $\log\tilde w_i$ once; assert `isfinite(z_i)`. Any NaN/Inf is a hard failure for this merchant (S6.8 code to be defined there).

---

## 5) Event stream: path, partitions, envelope, payload (authoritative)

**Dataset path & partitions (dictionary-pinned):**
`logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`, partitioned by `["seed","parameter_hash","run_id"]`.

**Envelope (required on every row):** the rng envelope from §2; set `substream_label="gumbel_key"`. Counters respect “one uniform per event” (delta = 1).

**Payload (schema `schemas.layer1.yaml#/rng/events/gumbel_key`):**
`\{ merchant_id:id64,\ country_iso:iso2,\ weight:pct01,\ u:u01,\ key:number,\ selected:boolean,\ selection_order:int≥1|null \}`. Winners get `selected=true` and `selection_order∈{1..K_m^\star}`; losers: `selected=false`, `selection_order=null`.

**Coverage invariant.** Emit **exactly $M_m$** `gumbel_key` rows for merchant $m$ (one per candidate).

---

## 6) Determinism & draw-accounting invariants

* **Bit replay.** For fixed $(\tilde w,\ K_m^\star,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the vector $(u_i,z_i)$ and the later winner set are **bit-identical** across replays (counter-based RNG + keyed substream + fixed one-draw budget).
* **Per-event draws.** `draws = 1` for every `gumbel_key` event; merchant-level sum equals $M_m$. Validators reconcile via envelope counters per S0.3.6.
* **Schema & ranges.** `u` must pass `u01` (strictly inside (0,1)); `weight` is the **foreign-renormalised** $\tilde w_i$ and must be finite in $(0,1]$. `country_iso` must pass ISO FK.

---

## 7) Language-agnostic reference algorithm (normative emitter)

```text
ALGORITHM S6_4_emit_gumbel_key_events

INPUT:
  - merchant m; foreign list F = [i1..iM] (ISO order from S6.3)
  - tilde_w[ i ] for i ∈ F  (Σ tilde_w = 1 within 1e-12)
  - lineage: {seed, parameter_hash, manifest_fingerprint, run_id}
  - module_name := "1A.foreign_country_selector"

OUTPUT:
  - exactly M JSONL rows to logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...

SETUP:
  0. set substream_label := "gumbel_key"
  1. for each i in 1..M:
       # keyed substream mapping (S0.3.3):
       # counter_before := base_counter(seed, manifest_fingerprint, substream_label, m) + i
       # draw exactly one uniform; counter_after = counter_before + 1
       counter_before := keyed_counter(seed, manifest_fingerprint, substream_label, m, i)
       (R0, R1) := philox2x64(counter_before, seed)     # discard R1
       u := (R0 + 1) / (2^64 + 1)                       # S0.3.4 open-interval
       g := -log(-log(u))
       z := log(tilde_w[i]) + g
       assert isfinite(z); assert u ∈ (0,1)

       counter_after := counter_before + 1               # 128-bit add with carry

       # Emit event row with envelope + payload
       write_event(
         envelope={
           ts_utc=now(), run_id, seed, parameter_hash, manifest_fingerprint,
           module=module_name, substream_label,
           rng_counter_before_hi, rng_counter_before_lo,
           rng_counter_after_hi,  rng_counter_after_lo
         },
         payload={
           merchant_id=m, country_iso=i,
           weight=tilde_w[i], u=u, key=z,
           selected=null or false, selection_order=null  # flags filled after S6.5
         }
       )

POST:
  2. buffer {i → z} for S6.5 (deterministic total-order sort to set flags).
```

Notes:

* **Iteration order** for event emission may be any deterministic order; using the S5 ISO order keeps alignment simple.
* Implementations may compute **all** $(u,z)$ first, run S6.5, then **emit** with final `selected/selection_order` in one pass. If you emit earlier, you must **update** flags later (only if your log store allows updates; otherwise buffer before writing).

---

## 8) Failure taxonomy owned by S6.4 (precise triggers)

* `E/1A/S6/RNG/ENVELOPE` — any required envelope field missing (seed/param_hash/manifest_fingerprint/run_id/substream_label/counters). **Abort run.**
* `E/1A/S6/RNG/COUNTER_DELTA` — `after != before + 1` for a `gumbel_key` row. **Abort run.**
* `E/1A/S6/RNG/U01_BREACH` — $u\notin(0,1)$ (inclusive bound or non-finite). **Abort merchant.**
* `E/1A/S6/RNG/KEY_NANINF` — computed `key` not finite. **Abort merchant.**
* `E/1A/S6/RNG/COVERAGE` — number of `gumbel_key` rows $\neq M_m$. **Abort run.**

(Additional selection/order failures are raised in S6.5/S6.6 when mapping winners to `selected`/`selection_order` and to `country_set.rank`.)

---

## 9) Cross-artefact coherence (what validators assert)

* For each merchant, $|\text{gumbel_key rows}|=M_m$; per-event `draws=1`; sum of draws equals $M_m$.
* Payload `weight` equals $\tilde w_i$ from S6.3 (value equality within machine rounding); `country_iso` is ISO-valid.
* After S6.5–S6.6: winners’ events have `selected=true` and `selection_order=r`; `country_set.rank=r` for the same ISO; losers’ rows carry `selected=false`, `selection_order=null`.

---

## 10) Edge cases

* **Extreme uniforms.** The S0.3.4 map guarantees $u\in(0,1)$ even when $x=0$ or $x=2^{64}-1$; $g=-\log(-\log u)$ remains finite.
* **Tiny $\tilde w_i$.** Allowed as long as $\tilde w_i > 0$ (S6.3 guarantees); use binary64 logs; guard `isfinite(z)`.
* **Optional telemetry.** You may emit a diagnostic `stream_jump` record on first emission for $(\ell,m)$ (label `"gumbel_key"`), but it must not change counter mapping. Artefact registry lists the `stream_jump` log.

---

### One-line takeaway

S6.4 is **bit-replayable RNG**: keyed substream mapping, **one 64-bit lane ⇒ one open-interval uniform**, **one uniform per candidate ⇒ one event**, and an auditable envelope with pre/post counters—emitting `gumbel_key` rows that S6.5 will deterministically sort into the winners used to persist `country_set`.

---

# S6.5 — Selection rule & induced order

## 1) Inputs & objective

* Candidates: foreign ISO list $\mathcal F_m=(i_1,\dots,i_{M_m})$ from S6.3 (home excluded; ISO order).
* For each $i\in\mathcal F_m$:

  * foreign-renormalised weight $\tilde w_i\in(0,1]$ (S6.3, sums to 1),
  * uniform $u_i\in(0,1)$ (open interval) and key $z_i=\log \tilde w_i - \log(-\log u_i)$ from S6.4.
* Effective winners count: $K_m^\star=\min(K_m,M_m)$ from S6.0 (never use raw $K_m$ after the cap).

**Goal:** pick the **top $K_m^\star$** candidates under a **strict total order**, and set `selected/selection_order` on the `gumbel_key` events accordingly.

---

## 2) Strict total order (mathematical definition)

Define $i \succ j$ (“$i$ outranks $j$”) iff

$$
i \succ j \iff \big(z_i > z_j\big)\ \text{or}\ \big(z_i=z_j\ \text{and}\ i<_{\text{ASCII}} j\big).
$$

* Primary key: **higher** $z$ wins.
* Deterministic tie-break: **ISO ASCII ascending**.

This is a **strict total order** on $\mathcal F_m$: real-number $>$ is total on distinct values; if $z_i=z_j$ in binary64, ISO ASCII is a total order on distinct two-letter codes, so exactly one of $i<_{\text{ASCII}}j$ or $j<_{\text{ASCII}}i$ holds.

**Sorter key (implementation-equivalent):** sort by the composite key

$$
\kappa(i):=\big(-z_i,\ \mathrm{ISO}(i)\big)
$$

in **lexicographic ascending** order. This is identical to “$z$ descending, ISO ascending” and avoids reliance on sort stability.

---

## 3) Winners, selection order, and event flags

Let $\pi_m$ be the permutation of $\mathcal F_m$ that sorts by $\succ$:

$$
z_{\pi_m(1)} \ge \dots \ge z_{\pi_m(M_m)}\quad\text{(with ISO tie-break).}
$$

* **Winners:** $S_m=\{\pi_m(1),\dots,\pi_m(K_m^\star)\}$.
* **Selection order:** for $r=1,\dots,K_m^\star$, the $r$-th winner is $i_r=\pi_m(r)$.
* **Flags to set in `gumbel_key` events:**

  * For winners: `selected=true`, `selection_order=r`.
  * For non-winners: `selected=false`, `selection_order=null`.

These flags must be consistent with the same $z_i$ recorded on each event. Any mismatch is a validation failure.

---

## 4) Probabilistic semantics (why this is the right sampler)

With $g_i:=-\log(-\log u_i)$ i.i.d. standard Gumbel and $z_i=\log\tilde w_i+g_i$, the permutation $\pi_m$ has the **Plackett–Luce** distribution with parameters $\tilde w$. Therefore the top-$K_m^\star$ form a **weighted sample without replacement** from $\mathcal F_m$ with weights $\tilde w$. This matches the design: heavier $\tilde w_i$ appear more often and earlier; no duplicate winners.

---

## 5) Artefact-level contracts & invariants

**Event stream (`gumbel_key`):**

* Exactly **$M_m$** rows for merchant $m$ (one per candidate).
* Winners have `selected=true` and `selection_order∈{1..K_m^\star}`; others `selected=false`, `selection_order=null`.
* Payload already carries $\tilde w_i,u_i,z_i$ and the RNG envelope.

**Allocation dataset (`country_set`):**

* Persist **home + $K_m^\star$** foreign rows in **Gumbel order** with ranks $0,1,\dots,K_m^\star$.
* `country_set.rank` **must equal** winners’ `selection_order`.
* `country_set` is the **only authority** for inter-country order.

---

## 6) Language-agnostic reference algorithm (normative)

```text
ALGORITHM S6_5_select_and_flag

INPUT:
  F = [i1..iM]                 # foreign ISOs (order arbitrary here)
  z[i] for i in F              # keys from S6.4
  K_star (1..M)                # effective winners count from S6.0
  events[i]                    # mutable event records or buffered rows for i∈F

OUTPUT:
  winners = [i_1..i_K_star]    # in Gumbel order
  flags applied to events[i]: (selected, selection_order)

STEPS:
1. idx := argsort_by( key(i) = (-z[i], ISO(i)) )   # z↓ then ISO↑
2. winners := take_first_K(idx, K_star)
3. # initialise all flags as losers (defensive)
   for i in F: events[i].selected := false; events[i].selection_order := null
4. # assign winner flags in induced order
   r := 1
   for i in winners:
       events[i].selected := true
       events[i].selection_order := r
       r := r + 1
5. # postconditions (assert deterministically)
   assert |winners| == K_star
   assert {events[i].selection_order | events[i].selected} == {1..K_star}
   return winners
```

**Emission strategy.** Preferred: compute $z$, run S6.5, **then emit** `gumbel_key` events already containing final flags. If your emitter wrote events in S6.4 without flags, you must **update** those rows consistently after S6.5 (only if your log store allows updates). The **normative** state has events persisted with final flags.

---

## 7) Validator hooks (deterministic predicates)

Given all `gumbel_key` rows for $m$:

1. **Coverage:** $|\text{rows}|=M_m$.
2. **Reconstruct order:** `idx := argsort_by((-key, ISO))`; winners are first $K_m^\star$.
3. **Flags:** for $t\le K_m^\star$: row at `idx[t]` has `selected=true` and `selection_order=t`; for $t > K_m^\star$: `selected=false`, `selection_order=null`.
4. **Coherence to `country_set`:** join winners to `country_set` on `(merchant_id,country_iso)` and assert `rank == selection_order`. Any mismatch is a failure.

---

## 8) Edge cases & guarantees

* **$K_m^\star=M_m$:** all candidates selected; selection orders $1..M_m$; ranks $1..M_m$ in `country_set`.
* **Binary64 key collisions:** resolved by ISO ASCII; deterministic across platforms.
* **Key invalidity (NaN/Inf):** cannot occur if S6.3 positivity and S6.4 open-interval $u$ held; if observed, abort merchant as invalid.

---

## 9) Complexity & determinism

* **Time:** $O(M_m\log M_m)$ for the sort.
* **Memory:** $O(M_m)$ for keys and indices.
* **Determinism:** With fixed $(\tilde w,u)$ and lineage, `argsort_by((-z,ISO))` yields a unique order $\pi_m$; winners and flags are **bit-replayable**.

---

### One-liner

S6.5 sorts candidates by **key descending then ISO ascending**, marks the first $K_m^\star$ as winners with `selection_order=1..K_m^\star`, and guarantees those orders exactly match the persisted `country_set.rank`. That’s the entire contract—mathematically precise, deterministic, and validator-auditable.

# S6.6 — Persistence (authoritative ordered set)

## 1) Purpose & placement

S6.6 takes the **winners & order** from S6.5 and the **foreign-renormalised weights** $\tilde w$ from S6.3, and materialises the per-merchant ordered set to **`country_set`**, which is explicitly the **only** authority for inter-country order in 1A. The dataset is **partitioned by `{seed, parameter_hash}`**, *not* by `run_id`.

---

## 2) Inputs (deterministic, read-only)

For a merchant $m$ admitted to S6 with $K_m^\star\ge 1$:

* Home ISO $c$.
* Winners $(i_1,\dots,i_{K_m^\star})$ in **Gumbel order** from S6.5, with `selection_order=r` for $i_r$.
* Foreign-renormalised weights $\tilde w_{i_r}\in(0,1]$ aligned to $(i_r)$, summing to 1 within $10^{-12}$ (serial).
* Lineage: `seed:uint64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64` (to persist as a column).
* Event stream `gumbel_key` for cross-artefact coherence (winners/flags).

(If $M_m=0$, S6.0 already wrote the **home-only** row and S6.6 does nothing for $m$.)

---

## 3) Authoritative path, partitions, schema

* **Path (dictionary-pinned):**
  `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/part-*.parquet`
  **Partitions:** `["seed","parameter_hash"]`. **No `run_id`** here.

* **Schema (source of truth):** `schemas.1A.yaml#/alloc/country_set`.
  **PK:** `["merchant_id","country_iso"]` (uniqueness within a `{seed,parameter_hash}` partition).
  **FK:** `country_iso` → ISO canonical (`schemas.ingress.layer1.yaml#/iso3166_canonical_2024`).
  **Order carrier:** `rank` (0 = home; 1..K in **Gumbel order**). Row/file order is irrelevant.
  **Columns & domains (semantics):**

  * `manifest_fingerprint: hex64` (required lineage).
  * `merchant_id: id64` (required).
  * `country_iso: iso2` (required, FK).
  * `is_home: boolean` (required).
  * `rank: int32, minimum 0` (required).
  * `prior_weight: float64, nullable` — **null for home**, otherwise $(0,1]$ for foreigns (diagnostic “prior”, i.e., $\tilde w$).

**Schema authority policy:** `schemas.1A.yaml` is the sole source of truth; any Avro is generated downstream and **not** referenced by 1A.

---

## 4) Row semantics (what you *must* write)

Write exactly **$K_m^\star+1$** rows (home + winners) to the partition `{seed, parameter_hash}`:

### Home row (rank 0)

```
{ manifest_fingerprint, merchant_id=m, country_iso=c,
  is_home=true, rank=0, prior_weight=null }
```

### Foreign rows (ranks 1..K in Gumbel order)

For each $r=1..K_m^\star$, ISO $i_r$:

```
{ manifest_fingerprint, merchant_id=m, country_iso=i_r,
  is_home=false, rank=r, prior_weight=tilde_w[i_r] }  # binary64; ∈(0,1]
```

`country_set` is the **only** authority for the order (via `rank`); all consumers must join on `rank`.

---

## 5) Numeric policy (strict, deterministic)

* **Arithmetic:** IEEE-754 binary64.
* **Reductions:** serial left-fold in **rank order** (1..K) when checking the foreign sum.
* **Foreign sum:** $\sum_{r=1}^{K} \tilde w_{i_r} = 1 \pm 10^{-12}$.
* **Ranges:** each foreign `prior_weight` is finite and in $(0,1]$; home row has `prior_weight = null`.
* **Persistence:** write `prior_weight` exactly as computed (no decimal rounding).

---

## 6) Determinism & idempotency

* **Determinism.** With fixed lineage $(\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, S6.4 keys and S6.5 order are bit-replayable; thus the set $(c,i_1,\dots,i_K)$ and `prior_weight` values are fixed.
* **Idempotent writer (merge-by-PK).** Within a `{seed, parameter_hash}` partition:

  * If `(merchant_id, country_iso)` exists, **replace** the row (rank/weight).
  * Else **insert**.
    This guarantees clean re-runs without duplicates. **Never** rely on write sequence as an ordering mechanism.

---

## 7) Cross-artefact coherence (hard requirements)

* **Event ↔ table:** Every winner `(merchant_id=m, country_iso=i_r)` **must** have a `gumbel_key` event with `selected=true` and `selection_order=r`, and **the table must store `rank=r`** for that ISO. Any mismatch is a validation failure.
* **Coverage:** A merchant with any `gumbel_key.selected=true` **must** have the corresponding foreign rows in `country_set`. Conversely, losers (selected=false) must **not** appear in `country_set`.

---

## 8) Writer pre/post checks (must be enforced)

**Before write (construct rows):**

1. **Cardinality:** have exactly $K_m^\star$ winners with unique `selection_order=1..K_m^\star`.
2. **Weights:** all $\tilde w_{i_r}$ finite in $(0,1]$; serial foreign sum $=1\pm10^{-12}$.
3. **No duplicates:** winner ISOs unique and none equals home ISO.
4. **Lineage present:** `manifest_fingerprint` set; partitions `{seed, parameter_hash}` known (match dictionary).

**After write (validate persisted view):**

1. Exactly **one** home row: `(is_home=true, rank=0, prior_weight=null, country_iso=c)`.
2. Exactly **K** foreign rows with `rank∈{1..K}` **once each** (contiguous ranks).
3. `PK` uniqueness holds; all `country_iso` pass ISO FK.
4. **Coherence to events:** join winners to `country_set` and assert `rank==selection_order`.

---

## 9) Failure predicates owned by S6.6 (names indicative)

(Full S6.8 catalog will restate these codes; below are the precise triggers.)

* `E/1A/S6/PERSIST/COUNTRY_SET_SCHEMA` — any schema violation (missing/typed columns, FK fail, non-hex `manifest_fingerprint`, out-of-range `prior_weight`, negative `rank`). **Abort run.**
* `E/1A/S6/PERSIST/MISSING_HOME_ROW` — no `(m,c,rank=0,is_home=true,prior_weight=null)` row. **Abort merchant.**
* `E/1A/S6/PERSIST/RANK_GAP_OR_DUP` — ranks are not exactly `{0..K}` or duplicates exist. **Abort merchant.**
* `E/1A/S6/PERSIST/PK_DUP` — duplicate `(merchant_id,country_iso)` in the target partition. **Abort run.** (PK breach.)
* `E/1A/S6/PERSIST/WEIGHT_SUM` — $\sum_{r=1}^K \tilde w_{i_r}$ not in $1\pm 10^{-12}$ (serial). **Abort merchant.**
* `E/1A/S6/PERSIST/HOME_WEIGHT_NONNULL` or `/FOREIGN_WEIGHT_NULL` — home has non-null weight, or a foreign has null. **Abort merchant.**
* `E/1A/S6/PERSIST/EVENT_COHERENCE` — any mismatch to `gumbel_key.selected/selection_order`. **Abort run.**
* `E/1A/S6/PERSIST/PARTITION_KEYS` — path not partitioned by `{seed, parameter_hash}` as per dictionary. **Abort run.**

---

## 10) Language-agnostic reference writer (normative)

```text
ALGORITHM S6_6_write_country_set

INPUT:
  m                # merchant_id
  c                # home ISO2
  winners = [i1..iK]            # Gumbel order from S6.5 (K = K_m^*)
  tilde_w: map ISO→float64      # aligned to winners; Σ tilde_w[winners] = 1 ± 1e-12
  lineage = {seed, parameter_hash, manifest_fingerprint}

TARGET PARTITION:
  path := data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/...

PRECHECKS:
  assert K ≥ 1
  assert winners are unique; none equals c
  assert all tilde_w[i] finite in (0,1]
  assert serial_sum(tilde_w[i] for i in winners) ≈ 1 within 1e-12

BUILD:
  rows := [
    {manifest_fingerprint, merchant_id:m, country_iso:c,  is_home:true,  rank:0, prior_weight:null}
  ]
  for r in 1..K:
    i := winners[r]
    rows.append({manifest_fingerprint, merchant_id:m, country_iso:i, is_home:false,
                 rank:r, prior_weight:tilde_w[i]})

WRITE (idempotent merge-by-PK within {seed,parameter_hash}):
  for row in rows:
    upsert_into_country_set_PK((merchant_id,row.country_iso), row)

POSTCHECKS (persisted view for m):
  # Rank set is contiguous and unique
  assert exactly one (is_home=true, rank=0, country_iso=c, prior_weight=null)
  assert for r in 1..K there exists exactly one row with rank=r and is_home=false
  # Event coherence
  join winners with gumbel_key where selected=true:
     assert rank == selection_order for every winner

RETURN success
```

---

## 11) Notes & edge cases

* **$K_m^\star=M_m$:** all candidates become foreign rows; still exactly one home row + $M_m$ foreign rows.
* **Home-only merchants (S6.0):** already persisted in S6.0; S6.6 **must not** write again.
* **Downstream dependency:** `outlet_catalogue` does **not** encode inter-country order; all consumers (including 1B) MUST join `country_set.rank`.

---

### One-line takeaway

S6.6 writes the **single source of truth** for cross-country order: `country_set` under `{seed, parameter_hash}`. You must persist **home rank 0** and **foreign ranks 1..K** in Gumbel order with exact $\tilde w$ as `prior_weight`, enforce schema/PK/FK and numeric tolerances, and prove **event ↔ table** coherence with `gumbel_key`. That’s the whole contract—deterministic, idempotent, and validator-auditable.

---

# S6.7 — Determinism & correctness invariants

## 1) Scope (what S6.7 governs)

S6.7 concerns merchants that reach S6 with effective $K_m^\star \ge 1$ (after S6.0’s cap/short-circuit). It asserts:

* **Bit replay:** with fixed lineage, the uniforms $u$, keys $z$, winner set $S_m$, and the persisted order are uniquely determined.
* **Event coverage & schema discipline:** exactly one `gumbel_key` event per foreign candidate; each row carries the full RNG envelope (`seed`, `parameter_hash`, `manifest_fingerprint`, pre/post counters, label, etc.).
* **Coherent persistence:** `country_set` (partitioned by `{seed, parameter_hash}`) materialises home rank 0 plus the foreign winners in **Gumbel order**; it is the **only** authority for inter-country order.
* **Branch edge cases:** when $M_m{=}0$, S6 persists **home-only** and emits **no** `gumbel_key`; S3 ineligible merchants have **no** S4–S6 RNG events at all.

---

## 2) Normative invariants (I-G1 … I-G10)

### I-G1 — Bit-replay determinism

For fixed $(\tilde w,\ K_m^\star,\ \texttt{seed}, \texttt{parameter_hash}, \texttt{manifest_fingerprint})$, the vector $u\in(0,1)^{M_m}$, the keys $z$, the winner set $S_m$ and the **selection order** are **bit-identical** across replays. (Counter-based Philox + open-interval uniform + one draw per candidate + deterministic tie-break.)

### I-G2 — Event coverage (one per candidate)

For merchant $m$, if the foreign candidate size is $M_m$ then the `gumbel_key` event stream **must** contain **exactly $M_m$** rows for $m$; no more, no less. Winners have `selected=true` and `selection_order∈{1..K_m^\star}`; losers have `selected=false`, `selection_order=null`.

### I-G3 — Envelope & payload validity

Every `gumbel_key` row must:

* carry the layer-wide RNG envelope (`ts_utc`, `run_id`, `seed:uint64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`, `module`, `substream_label`, `rng_counter_before_{hi,lo}`, `rng_counter_after_{hi,lo}`); and
* satisfy payload domains: `merchant_id:id64`, `country_iso:iso2`, `u:u01` (**open interval**), `weight:pct01`, `key:number`.

**Counter discipline.** For each event: `after = before + 1` (128-bit add); per merchant, the **sum of draws** equals $M_m$.

**Partitioning.** Events live at
`logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with partitions `["seed","parameter_hash","run_id"]`.

### I-G4 — Deterministic order & tie-break

Sort candidates by **key descending** with **ISO ASCII ascending** as tie-break. This induces a strict total order; the first $K_m^\star$ are the winners in positions $1..K_m^\star$.

### I-G5 — Coherence to `country_set` (the order carrier)

Persist **exactly one** home row `(is_home=true, rank=0, prior_weight=null)` and **$K_m^\star$** foreign rows `(is_home=false, rank=r, prior_weight∈(0,1])` **in the same order** as `gumbel_key.selection_order=r`. Any mismatch between `country_set.rank` and the winners’ `selection_order` is a **validation failure**.

**Path/partitions/schema.**
`data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/…`, partitions `["seed","parameter_hash"]`, schema `schemas.1A.yaml#/alloc/country_set`. `country_set` is the **only authority** for cross-country order.

### I-G6 — Weight integrity

Event weights are the **foreign-renormalised** $\tilde w$ from S6.3: each weight is in $(0,1]$, and the **serial sum** across the $M_m$ candidates equals $1$ within tolerance $10^{-12}$. In `country_set`, foreign `prior_weight` values match $\tilde w$ of the winners and serial-sum to $1\pm10^{-12}$; home’s `prior_weight` is **null**.

### I-G7 — Keys finite

Every event `key` is finite (no NaN/Inf). Open-interval `u` ensures $g=-\log(-\log u)$ is finite. Any non-finite key is a hard failure.

### I-G8 — Branch/edge-case coherence

* **No candidates:** If $M_m=0$, S6 **persists home-only** (`rank=0`) and emits **no** `gumbel_key` for $m$. Reason “no_candidates” is recorded by validation; proceed to S7.
* **Ineligible merchants:** If S3 decided $e_m=0$, there must be **no** `gumbel_key` (or S4) events for $m$ at all; later `country_set` must have **only** the home row.

### I-G9 — Partition & schema authority

All paths/partitions must match the **data dictionary** and schemas the **Schema Authority Policy** points to (JSON-Schema only). Any deviation (wrong partitions; referencing Avro; missing FK to canonical ISO) is a structural error.

### I-G10 — Idempotent persistence

Within a `{seed, parameter_hash}` partition, `(merchant_id,country_iso)` is a PK; re-runs **upsert** rows (no duplicates), and ranks for a merchant are exactly $\{0,1,\dots,K_m^\star\}$ with no gaps.

---

## 3) Numeric policy & tolerances

* **Arithmetic:** IEEE-754 binary64 for all $u$, logs, keys, sums.
* **Serial reductions:** left-fold in deterministic order (ISO order for candidate-mass sum in events; `rank` order for foreign-weight sum in `country_set`).
* **Tolerances:** $|\sum \tilde w - 1| \le 10^{-12}$ (serial). `u` strictly in `(0,1)` by schema.

---

## 4) Cross-artefact contracts (summarised)

1. **Events ↔ Table:** winners’ `(merchant_id, country_iso)` must appear in `country_set` with `rank == selection_order`. Losers must **not** appear as foreign rows.
2. **Authority:** consumers needing inter-country sequence **must** join `country_set.rank` (egress like `outlet_catalogue` does **not** encode this order).
3. **Run lineage:** `country_set` partitions do **not** include `run_id`; `gumbel_key` does. Validators join using `seed`, `parameter_hash`, and `manifest_fingerprint`.

---

## 5) Language-agnostic **reference validator** (normative)

```text
FUNCTION validate_S6_for_merchant(m):

INPUT:
  G = all gumbel_key rows for merchant m (from logs/rng/events/gumbel_key/seed=…/parameter_hash=…/run_id=…)
  C = all country_set rows for merchant m (from data/layer1/1A/country_set/seed=…/parameter_hash=…)
  F = size of foreign candidate set from S6.3 (or |G| if S6.3 view unavailable)
  K_star = effective winners count from S6.0
  c_home = home ISO for m (ingress/S0)
  lineage fields: seed, parameter_hash, manifest_fingerprint

# I-G2: coverage
1  assert |G| == F                               # exactly one event per candidate
2  assert F >= K_star

# I-G3: envelope & payload per row
3  for e in G:
4      assert has_fields(e.envelope, ["ts_utc","run_id","seed","parameter_hash",
                                      "manifest_fingerprint","module","substream_label",
                                      "rng_counter_before_lo","rng_counter_before_hi",
                                      "rng_counter_after_lo","rng_counter_after_hi"])
5      assert e.substream_label == "gumbel_key"
6      assert advance128(e.before) == e.after    # per-event delta = 1
7      assert is_iso2(e.country_iso) and 0 < e.u < 1
8      assert 0 < e.weight <= 1 and isfinite(e.key)

# I-G6: weights sum to 1 (serial, deterministic order)
9  S := 0.0
10 for e in G in ISO_ASCENDING: S := S + e.weight
11 assert |S - 1.0| <= 1e-12

# I-G4: reconstruct total order; I-G2 flags/ordering
12 idx := argsort_by( key(i) = (-G[i].key, G[i].country_iso) )
13 winners := take_first_K(idx, K_star)
14 # losers default
15 for i in 1..F:
16     if i in winners:
17         r := position(i in winners)           # 1-based
18         assert G[i].selected == true and G[i].selection_order == r
19     else:
20         assert G[i].selected == false and is_null(G[i].selection_order)

# I-G5: table coherence & structure
21 assert exactly_one row in C where is_home=true and rank=0 and country_iso==c_home and prior_weight is null
22 assert count(C where is_home=false) == K_star
23 map_rank := { row.country_iso -> row.rank for row in C where is_home=false }
24 # foreign prior_weight domain & sum
25 Sfw := 0.0
26 for row in C where is_home=false:
27     assert isfinite(row.prior_weight) and 0 < row.prior_weight <= 1
28     Sfw := Sfw + row.prior_weight
29 assert |Sfw - 1.0| <= 1e-12
30 # rank == selection_order for winners
31 for r in 1..K_star:
32     i := winners[r]
33     assert map_rank[ G[i].country_iso ] == r

# I-G9: partitions governance
34 assert partitions(G) == ["seed","parameter_hash","run_id"]
35 assert partitions(C) == ["seed","parameter_hash"]

RETURN PASS
```

* **Failure classification:** Map each assertion to S6.8 codes (e.g., schema/envelope → `SCHEMA/ENVELOPE`; coverage mismatch → `COVERAGE`; non-finite key → `KEY_NANINF`; event↔table mismatch → `EVENT_COHERENCE`; partition drift → `PARTITION_KEYS`).

---

## 6) Edge cases & sanity checks

* **$K_m^\star=M_m$**: all candidates are winners; exactly $M_m$ `selected=true` with `selection_order=1..M_m`; table has ranks $1..M_m$.
* **No candidates $M_m=0$**: only the home row is written; `gumbel_key` must be **absent** for $m$.
* **Ineligible $e_m=0$**: no `gumbel_key` (or S4) events; table has only `rank=0` home. Validators assert “absence” rules per S3.

---

## 7) Why this is sufficient

These invariants collectively guarantee: (a) **replayability** (I-G1), (b) **auditable RNG accounting** and schema correctness (I-G2–I-G3), (c) a **unique deterministic order** (I-G4), (d) **single source of truth** for order in `country_set` (I-G5), (e) **mass conservation** from S6.3 into persistence (I-G6), and (f) **branch coherence** with S3/S6.0 edge paths (I-G8)—all pinned to the **authoritative schemas and dictionary paths**.

---

### One-liner

S6.7 nails down what **must** be true—bit-replayable keys and winners, one event per candidate with strict schema/envelope and counter discipline, and a `country_set` that mirrors winners’ order exactly—under the exact paths and tolerances the registry and schema authority prescribe. If any piece deviates, validators have an explicit, reproducible way to fail the run.

---

# S6.8 — Failure taxonomy & CI error codes (authoritative)

## 1) Scope & artefacts under test

S6 produces/uses two authoritative artefacts:

1. **RNG events**: `gumbel_key` — one row **per candidate** foreign country.
   Path & partitions (dictionary):
   `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/gumbel_key` (envelope + payload).

2. **Allocation table**: `country_set` — ordered winners (home rank 0, foreign ranks 1..K).
   Path & partitions (dictionary):
   `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/`
   Schema: `schemas.1A.yaml#/alloc/country_set`. `country_set` is the **only** authority for inter-country order.

S6 relies on parameter-scoped inputs from S5 (weights cache etc.), governed by the schema authority. **Only JSON-Schema is authoritative** (no AVSC in 1A).

---

## 2) Error code format & severity

Codes are structured as:

```
E/1A/S6/<CLASS>/<DETAIL>
```

* **Abort run**: systemic or structural breach (schemas, partitions, counter discipline, coverage).
* **Abort merchant**: local data/pathology for a specific merchant (non-finite key, zero foreign mass, etc.).

Validators must log: `{code, merchant_id? (optional), reason, artefact_path, partition_keys, offending_rows_sample}` into `validation_bundle_1A` for the run’s fingerprint. (The bundle & gate are specified at the layer boundary.)

---

## 3) Taxonomy (classes, precise triggers, action, detection locus)

### A. INPUT (parameter/currency/weights presence & shape)

* **E/1A/S6/INPUT/MISSING_KAPPA** — No `merchant_currency` row for merchant $m$ at `{parameter_hash}`.
  **Action:** Abort merchant. **Where:** S6.2 preflight (C-1).

* **E/1A/S6/INPUT/MISSING_WEIGHTS** — No `ccy_country_weights_cache` rows for $\kappa_m$ at `{parameter_hash}`.
  **Action:** Abort merchant. **Where:** S6.2 preflight (C-1).

* **E/1A/S6/INPUT/WEIGHTS_ORDER** — Weights for $\kappa_m$ not in **ASCII ISO** order.
  **Action:** Abort run (cache corruption). **Where:** S6.2 preflight (C-2).

* **E/1A/S6/INPUT/WEIGHTS_SUM** — Serial sum over $\mathcal D(\kappa_m)$ $\notin 1\pm 10^{-6}$.
  **Action:** Abort run. **Where:** S6.2 preflight (C-3).

* **E/1A/S6/INPUT/WEIGHTS_RANGE** — Any $w_i^{(\kappa)}$ non-finite or $\notin[0,1]$.
  **Action:** Abort run. **Where:** S6.2 preflight (C-3).

* **E/1A/S6/INPUT/BAD_CAP** — With $M_m\ge1$, effective $K_m^\star\notin[1,M_m]$ (cap missing/wrong).
  **Action:** Abort run. **Where:** S6.2 & echoed in S6.3.

### B. LINEAGE (partitions/authority)

* **E/1A/S6/LINEAGE/PARTITION_KEYS** — Partitions don’t match dictionary:
  `gumbel_key` must be `["seed","parameter_hash","run_id"]`; `country_set` must be `["seed","parameter_hash"]`.
  **Action:** Abort run. **Where:** S6.2 & S6.6.

* **E/1A/S6/LINEAGE/SCHEMA_AUTHORITY** — Referencing a non-authoritative schema (e.g., AVSC) or wrong JSON-Schema pointer in artefact registry/dictionary.
  **Action:** Abort run. **Where:** CI schema audit.

### C. RENORM (foreign mass & normalisation)

* **E/1A/S6/RENORM/ZERO_FOREIGN_MASS** — $T_m=\sum_{i\in\mathcal F_m} w_i^{(\kappa)}\le0$ or non-finite.
  **Action:** Abort merchant. **Where:** S6.3 (strict).

* **E/1A/S6/RENORM/WEIGHT_RANGE** — Some $\tilde w_i$ non-finite or $\notin(0,1]$.
  **Action:** Abort merchant. **Where:** S6.3.

* **E/1A/S6/RENORM/SUM_TOL** — Serial sum $\sum_{i\in\mathcal F_m}\tilde w_i\notin 1\pm 10^{-12}$.
  **Action:** Abort merchant. **Where:** S6.3.

### D. RNG (envelope, counters, uniforms, keys) — `gumbel_key` events

* **E/1A/S6/RNG/ENVELOPE** — Missing any envelope field (`ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before/after_{hi,lo}`) or wrong `substream_label!="gumbel_key"`.
  **Action:** Abort run. **Where:** S6.4 emit. **Schema:** `schemas.layer1.yaml#/rng_envelope`.

* **E/1A/S6/RNG/COUNTER_DELTA** — For any row, `after != before + 1` (we must consume **one** Philox block per event).
  **Action:** Abort run. **Where:** S6.4 emit.

* **E/1A/S6/RNG/U01_BREACH** — `u` not strictly in `(0,1)` or non-finite (schema primitive `u01`).
  **Action:** Abort merchant. **Where:** S6.4 emit. **Schema:** `#/u01`.

* **E/1A/S6/RNG/KEY_NANINF** — Computed `key` (Gumbel or `log tilde_w + Gumbel`) non-finite.
  **Action:** Abort merchant. **Where:** S6.4 emit.

* **E/1A/S6/RNG/COVERAGE** — Number of `gumbel_key` events $|G_m|\neq M_m$ (must be **exactly one per candidate**).
  **Action:** Abort run. **Where:** S6.4 emit / S6.7 validation.

### E. SELECTION (sorting, flags)

* **E/1A/S6/SELECT/ORDER_MISMATCH** — Sorting by **(key↓, ISO↑)** does not reproduce the emitted winners’ `selected=true` / `selection_order=1..K_m^\star`.
  **Action:** Abort run. **Where:** S6.5 / S6.7 validator.

* **E/1A/S6/SELECT/FLAGS_DOMAIN** — A winner missing `selection_order∈{1..K_m^\star}` or a loser with non-null `selection_order`.
  **Action:** Abort run. **Where:** S6.5 / S6.7.

### F. PERSIST (country_set write, schema & numeric policy)

* **E/1A/S6/PERSIST/COUNTRY_SET_SCHEMA** — Any schema breach in `country_set` (PK, FK to ISO, domain: `rank>=0`, `prior_weight=null` for home / $(0,1]$ for foreign).
  **Action:** Abort run. **Where:** S6.6 writer. **Schema:** `schemas.1A.yaml#/alloc/country_set`.

* **E/1A/S6/PERSIST/MISSING_HOME_ROW** — No home row `(is_home=true, rank=0, prior_weight=null, country_iso=c)`.
  **Action:** Abort merchant. **Where:** S6.6 post-write check.

* **E/1A/S6/PERSIST/RANK_GAP_OR_DUP** — Foreign ranks not exactly `{1..K_m^\star}` or duplicated.
  **Action:** Abort merchant. **Where:** S6.6 post-write check.

* **E/1A/S6/PERSIST/PK_DUP** — Duplicate `(merchant_id,country_iso)` within a `{seed,parameter_hash}` partition.
  **Action:** Abort run. **Where:** S6.6 post-write check.

* **E/1A/S6/PERSIST/WEIGHT_SUM** — Serial sum of `prior_weight` over foreign rows $\notin 1\pm 10^{-12}$.
  **Action:** Abort merchant. **Where:** S6.6 post-write check.

* **E/1A/S6/PERSIST/HOME_WEIGHT_NONNULL** (or **/FOREIGN_WEIGHT_NULL**) — Home `prior_weight` not null, or a foreign row has null.
  **Action:** Abort merchant. **Where:** S6.6 post-write check.

* **E/1A/S6/PERSIST/PARTITION_KEYS** — `country_set` path not partitioned by `{seed, parameter_hash}`.
  **Action:** Abort run. **Where:** S6.6 writer.

### G. COHERENCE (events ↔ table)

* **E/1A/S6/COHERENCE/EVENT_TO_TABLE** — Any winner’s `selection_order=r` not matched by a `country_set` row with `rank=r` for the same `(merchant_id,country_iso)`.
  **Action:** Abort run. **Where:** S6.6 post-write / S6.7 validator.

* **E/1A/S6/COHERENCE/LOSER_IN_TABLE** — A loser (`selected=false`) appears as foreign in `country_set`.
  **Action:** Abort run. **Where:** S6.6 post-write / S6.7 validator.

### H. BRANCH EDGE CASES

* **E/1A/S6/BRANCH/NO_CANDIDATES_WITH_EVENTS** — $M_m=0$ but `gumbel_key` events exist for $m$.
  **Action:** Abort run. **Where:** S6.0/S6.4 guard. (Home-only branch must emit **no** events.)

* **E/1A/S6/BRANCH/INELIGIBLE_HAS_EVENTS** — From S3: merchant `is_eligible=false` but S6 events exist.
  **Action:** Abort run (branch coherence). **Where:** cross-state validator (S3↔S6).

---

## 4) Where each failure is detected (map to substates)

| Substate | Primary checks that *raise* codes                                                                                                              |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **S6.0** | Branch `M_m=0` → **no** events; else nothing persisted. If `country_set` home-only isn’t written there, later phases must not add events. (H)  |
| **S6.2** | Presence/shape of `merchant_currency`, `weights_cache`; ISO ordering; sum=1; cap coherence; partitions known. (A,B)                            |
| **S6.3** | Foreign mass $T_m>0$, $\tilde w$ range & sum tolerance. (C)                                                                                    |
| **S6.4** | Envelope completeness; counter delta=1; `u∈(0,1)`; finite key; exact **M** events. (D)                                                         |
| **S6.5** | Reconstruct order by (key↓, ISO↑); set flags; flags domain. (E)                                                                                |
| **S6.6** | Schema, PK/FK, partitioning; ranks; prior_weight sums; home row; event↔table coherence. (F,G,B)                                               |
| **S6.7** | End-to-end invariants across artefacts; branch coherence with S3/S6.0. (D,E,F,G,H)                                                             |

---

## 5) Normative validator snippets (detection patterns)

Below are minimal, language-agnostic checks that *directly* trigger codes. They extend the S6.7 validator with explicit mappings to **S6.8** codes.

```text
# A — INPUT (presence/shape)
if not has_row(merchant_currency[parameter_hash], m): FAIL "E/1A/S6/INPUT/MISSING_KAPPA"
Wκ := weights_cache[parameter_hash][κ_m]
if |Wκ| == 0:                                          FAIL "E/1A/S6/INPUT/MISSING_WEIGHTS"
assert_ascii_iso_order(Wκ) else                        FAIL "E/1A/S6/INPUT/WEIGHTS_ORDER"
if |Σ_w(Wκ) - 1| > 1e-6:                               FAIL "E/1A/S6/INPUT/WEIGHTS_SUM"
if ∃w∈Wκ with not finite or w∉[0,1]:                   FAIL "E/1A/S6/INPUT/WEIGHTS_RANGE"
if M≥1 and (K_star < 1 or K_star > M):                 FAIL "E/1A/S6/INPUT/BAD_CAP"

# B — LINEAGE
if partitions(gumbel_key) != ["seed","parameter_hash","run_id"]: FAIL "E/1A/S6/LINEAGE/PARTITION_KEYS"
if partitions(country_set) != ["seed","parameter_hash"]:         FAIL "E/1A/S6/LINEAGE/PARTITION_KEYS"

# C — RENORM
if not (T>0 and finite):                                FAIL "E/1A/S6/RENORM/ZERO_FOREIGN_MASS"
if ∃tilde_w nonfinite or ≤0 or >1:                      FAIL "E/1A/S6/RENORM/WEIGHT_RANGE"
if |Σ_tilde_w - 1| > 1e-12:                             FAIL "E/1A/S6/RENORM/SUM_TOL"

# D — RNG
for e in gumbel_key_rows(m):
    if missing_envelope_fields(e):                      FAIL "E/1A/S6/RNG/ENVELOPE"
    if e.after != advance128(e.before, 1):              FAIL "E/1A/S6/RNG/COUNTER_DELTA"
    if not (0 < e.u < 1):                               FAIL "E/1A/S6/RNG/U01_BREACH"
    if not isfinite(e.key):                             FAIL "E/1A/S6/RNG/KEY_NANINF"
if |gumbel_key_rows(m)| != M:                           FAIL "E/1A/S6/RNG/COVERAGE"

# E — SELECTION
idx := argsort_by((-key, ISO)); winners := idx[1..K_star]
if not flags_match(idx, winners):                       FAIL "E/1A/S6/SELECT/ORDER_MISMATCH" or "/FLAGS_DOMAIN"

# F — PERSIST
C := country_set_rows(m)
if not has_home_row(C, c, rank=0, weight_null=True):    FAIL "E/1A/S6/PERSIST/MISSING_HOME_ROW"
if not ranks_exact(C_foreign, 1..K_star):               FAIL "E/1A/S6/PERSIST/RANK_GAP_OR_DUP"
if pk_duplicate(C):                                     FAIL "E/1A/S6/PERSIST/PK_DUP"
if |Σ prior_weight(C_foreign) - 1| > 1e-12:             FAIL "E/1A/S6/PERSIST/WEIGHT_SUM"
if home_weight_not_null(C) or foreign_weight_null(C):   FAIL "E/1A/S6/PERSIST/HOME_WEIGHT_NONNULL" or "/FOREIGN_WEIGHT_NULL"

# G — COHERENCE
for r in 1..K_star:
    e := winner_event_with_selection_order(r); row := country_set_row_with_rank(r)
    if e.country_iso != row.country_iso:                FAIL "E/1A/S6/COHERENCE/EVENT_TO_TABLE"
if ∃ loser_iso in country_set_foreign:                  FAIL "E/1A/S6/COHERENCE/LOSER_IN_TABLE"

# H — BRANCH
if M == 0 and |gumbel_key_rows(m)| > 0:                 FAIL "E/1A/S6/BRANCH/NO_CANDIDATES_WITH_EVENTS"
if S3.is_eligible(m) == false and |gumbel_key_rows(m)|>0: FAIL "E/1A/S6/BRANCH/INELIGIBLE_HAS_EVENTS"
```

All schema/partition checks use the **dictionary & schema authority** refs listed above; the validator must verify JSON-Schema conformance, not local ad-hoc types.

---

## 6) Reporting & gating (how CI decides pass/fail)

* **Per-merchant** failures (Abort merchant): list the code and merchant id; the run may continue, but the final **validation bundle** must record counts and samples (up to N rows) per code.
* **Run-level** failures (Abort run): terminate S6 validation; write the bundle with the first hard error and its diff context; block hand-off to 1B by withholding `_passed.flag`. (Gate described in the layer’s validation/egress section.)

**Always include** `{seed, parameter_hash, run_id?, manifest_fingerprint}` in the failure report so lineage can be re-played precisely. (Events include `run_id`; `country_set` does not.)

---

## 7) Why these codes are complete & aligned

* They align to the **authoritative dictionary paths/partitions** for `gumbel_key` and `country_set`.
* They reference **only** JSON-Schema defined in `schemas.layer1.yaml` and `schemas.1A.yaml`, per the **Schema Authority Policy**.
* They reflect the locked S6 mechanics: one event **per candidate**, cap to $K_m^\star$, strict sort `(key↓, ISO↑)`, and `country_set` as the **sole order carrier**.

---

### One-liner

S6.8 gives you a **zero-ambiguity error map**: every possible S6 failure has a unique code, a precise trigger tied to the **authoritative** schema/paths, a clear Abort-run vs Abort-merchant action, and minimal reference checks your CI validator can implement byte-for-byte.

---

# S6.9 — Inputs → Outputs (state boundary)

## 1) What S6 *consumes* (per merchant $m$)

**From earlier states (all deterministic):**

* **Eligibility & home:** $e_m\in\{0,1\}$ and home ISO $c$ from S3; only $e_m=1$ merchants enter S4–S6. Domestic $e_m=0$ merchants **skip S4–S6** and later have only `rank=0` home persisted.
* **Accepted foreign count:** $K_m\ge 1$ from S4 (ZTP accepted). If S4 exhausted retries, the merchant is aborted earlier and **does not** reach S6.
* **Merchant currency:** $\kappa_m$ from the S5.0 cache `merchant_currency` (parameter-scoped; do **not** recompute).
* **Currency→country candidate prior weights** for $\kappa_m$: ordered rows $\{(i,w_i^{(\kappa_m)})\}$ from S5 cache `ccy_country_weights_cache`.
* **RNG lineage:** `seed:uint64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`, plus a `run_id` for event logs.

**From S6.0:** the **effective** winners count $K_m^\star=\min(K_m, M_m)$ where $M_m=|\mathcal D(\kappa_m)\setminus\{c\}|$; if $M_m=0$ S6 already wrote **home-only** and emits **no** RNG events for $m$.

---

## 2) What S6 *produces* (authoritative artefacts on disk)

When S6 completes (for any merchant that reached it), **exactly one** of these branch outcomes exists on disk:

### A) Eligible merchant with $K_m^\star \ge 1$

1. **RNG event stream — per-candidate keys**
   Path & partitions (dictionary-pinned):

   ```
   logs/rng/events/gumbel_key/
     seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
   ```

   Schema: `schemas.layer1.yaml#/rng/events/gumbel_key`.
   **Exactly $M_m$ rows** for merchant $m$, one per foreign candidate; every row carries the full RNG envelope (`ts_utc`, `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label="gumbel_key"`, and pre/post Philox counters). **Counter delta = 1** per row. Payload includes `weight` (foreign-renormalised), `u∈(0,1)`, and `key=z`. Winners have `selected=true`, `selection_order∈{1..K_m^\star}`; losers `selected=false`, `selection_order=null`.

2. **Allocation dataset — ordered set (the sole order authority)**
   Path & partitions (dictionary-pinned):

   ```
   data/layer1/1A/country_set/
     seed={seed}/parameter_hash={parameter_hash}/part-*.parquet
   ```

   Schema: `schemas.1A.yaml#/alloc/country_set`.
   **Exactly $K_m^\star+1$ rows** for merchant $m$:
   the home row `(is_home=true, rank=0, prior_weight=null)` **and** $K_m^\star$ foreign rows in **Gumbel order** `(is_home=false, rank=r, prior_weight=\tilde w_{i_r})`, $r=1..K_m^\star$. `country_set` is the **only** authoritative store for cross-country order.

**Cross-artefact coherence (must hold on disk):** For each winner with `selection_order=r` in `gumbel_key`, there exists **exactly one** `country_set` row with the same `(merchant_id, country_iso)` and `rank=r`. Any mismatch is a validation failure.

---

### B) Eligible merchant with **no foreign candidates** $(M_m=0)$

* S6 persisted **home-only** to `country_set` (rank 0; null `prior_weight`) and **emitted no `gumbel_key` events** for $m$. This short-circuit is complete and hands off to S7.

---

### C) Ineligible merchant $(e_m=0)$

* S6 does not run for $m$. Later persistence must show only the home row (rank 0). Presence of S4–S6 events for $e_m=0$ is a branch-coherence failure validated elsewhere.

---

## 3) Determinism, idempotence, and replay guarantees at the boundary

* **Bit-replay:** With fixed $(\tilde w,\ K_m^\star,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the vector of uniforms $u$, keys $z$, winners, and `country_set.rank` are **bit-identical** across replays (counter-based RNG + open-interval $u$ + one-draw-per-event + deterministic tie-break).
* **Idempotent write:** `country_set` is partitioned by `{seed, parameter_hash}` and keyed by `(merchant_id,country_iso)`; re-runs **upsert** rows, never duplicating ranks or PKs.
* **Schema authority:** Only JSON-Schema references (`schemas.1A.yaml`, `schemas.layer1.yaml`) are authoritative for these artefacts; Avro is non-authoritative in 1A by policy.

---

## 4) Minimal **handoff record** (normative, language-agnostic)

Downstream (S7) can treat the outcome of S6 for merchant $m$ as the immutable record:

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
  K_star: K_m^*,                       # 0 means home-only
  candidates: {
    # Present if K_star ≥ 1
    events_path:
      "logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/",
    rows: M_m,                          # one per foreign candidate
    key_sort: "(-key, ISO)",            # S6.5 ordering key
    winners: [                          # Gumbel order (r = 1..K*)
      {iso: i_1, rank: 1, prior_weight: \tilde w_{i_1}},
      ...,
      {iso: i_K*, rank: K*, prior_weight: \tilde w_{i_K*}}
    ]
  },
  country_set_path:
    "data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/"
}
```

S7 MUST obtain the **ordered foreign list** from `country_set.rank` (0=home; 1..K\* foreigns). Inter-country order is **not** encoded in any egress like `outlet_catalogue`; consumers must join `country_set`.

---

## 5) What S7 can **assume** (hard contracts)

1. If $K_m^\star=0$: `country_set` has **exactly one** row for $m$: `(is_home=true, rank=0, prior_weight=null)`; there are **no** `gumbel_key` events for $m$.
2. If $K_m^\star\ge 1$:

   * `country_set` has **exactly $K_m^\star+1$** rows with contiguous ranks $0..K_m^\star$.
   * Foreign rows’ `prior_weight` values are finite, in $(0,1]$, and **serial-sum to 1** within $10^{-12}$.
   * The winners’ ISO sequence equals the first $K_m^\star$ rows of `argsort_by((-key, ISO))` reconstructed from the `gumbel_key` stream.
3. **Partitioning:** S7 will find `country_set` under `{seed, parameter_hash}`; `gumbel_key` under `{seed, parameter_hash, run_id}` (events only).
4. **Downstream dependencies:** Later 1A steps (integerisation/residuals; egress stubs) refer to `ranking_residual_cache_1A` and `outlet_catalogue`; neither encodes inter-country order. They **must** join `country_set.rank` when they need the cross-country sequence.

---

## 6) Acceptance checklist (CI can assert these and *only then* hand off)

For every merchant that reached S6:

* **Files present & well-partitioned** exactly as above; schemas validate against JSON-Schema.
* **Coverage:** $|\text{gumbel_key}_m| = M_m$ (or **0** if $K_m^\star=0$). Each event has `after=before+1`.
* **Order coherence:** winners’ `selection_order=r` ↔ `country_set.rank=r`. Losers absent from `country_set`.
* **Weights:** foreign `prior_weight` in `country_set` serial-sum to 1 within $10^{-12}$; home `prior_weight=null`.

Only when this checklist passes does S6 expose a clean boundary to S7 (and eventually contribute to the `_passed.flag` gate used by 1B).

---

### One-liner

**S6 in, S6 out:** given $(K_m, \kappa_m, \text{weights}, \text{lineage})$, S6 leaves behind a **complete, deterministic** pair—`gumbel_key` (one row per candidate; auditable RNG) and `country_set` (the *only* source of cross-country order)—such that S7 can just **join on `country_set.rank`** and move on.

---