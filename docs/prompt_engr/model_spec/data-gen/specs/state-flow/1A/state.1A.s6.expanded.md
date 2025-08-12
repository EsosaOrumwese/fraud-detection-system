# S6.1 — Universe, symbols, authority

## Domain (who enters S6)

Define the eligible merchant set

$$
\mathcal{D}\ :=\ \big\{\,m\ :\ \underbrace{\texttt{is_multi}(m)=1}_{\text{from S1}},\ \underbrace{\texttt{is_eligible}(m)=1}_{\text{from S3}},\ \underbrace{K_m\in\mathbb{Z}_{\ge 1}}_{\text{from S4}}\,\big\}.
$$

S6 is **evaluated only** for $m\in\mathcal{D}$. Its **ordered** result (home plus $K_m$ foreigns) is persisted to the authoritative allocation dataset **`country_set`** with `rank=0` for home and `rank=1..K_m` for the selected foreign countries.

## Authoritative schemas & streams (sources of truth)

* **Event stream:** `"gumbel_key"` — one record **per candidate country** for the merchant, always emitted, carrying the shared RNG envelope and payload (`country_iso`, prior/renormalised weight, uniform `u` on the **open** interval, computed key, selection flags). Schema: `schemas.layer1.yaml#/rng/events/gumbel_key`.
* **Allocation dataset:** `country_set` — the **only** store of inter-country order for 1A (rank carried as a column; PK `(merchant_id, country_iso)`), schema `schemas.1A.yaml#/alloc/country_set`. Consumers that need the order must **join to this rank**.
* **Dictionary governance:** the dataset dictionary pins the **paths/partitions** for both artefacts; S6 must obey these when writing (events by `{seed, parameter_hash, run_id}`, allocation by `{seed, parameter_hash}`).

## Selection mechanism (design choice, mathematically precise)

We perform **weighted sampling without replacement** using **Gumbel-top-$K$**.
Let $\mathcal{F}_m$ be the merchant’s **foreign candidate** ISO set (home excluded) with strictly positive **renormalised** weights $\tilde w_i$ satisfying $\sum_{i\in\mathcal{F}_m}\tilde w_i=1$. For each candidate $i\in\mathcal{F}_m$ draw **exactly one** uniform deviate

$$
u_i \sim U(0,1)\quad\text{on the open interval,}
$$

and compute the key

$$
\boxed{\ z_i \;=\; \log \tilde w_i\;-\;\log\!\bigl(-\log u_i\bigr)\ }.
$$

Then select the $K_m$ **largest** keys; ties (binary64 equality of $z_i$) are broken by **ISO ASCII lexicographic** order. This protocol consumes **one uniform per candidate** (so total draws per merchant $=|\mathcal{F}_m|$), is logged in the `"gumbel_key"` stream, and is fully **replayable** given the run lineage and fixed sub-stream label.

### Why these exact primitives?

* **Open-interval uniforms** guarantee $-\log(-\log u_i)$ is finite (no $u_i\in\{0,1\}$), removing corner-case infinities in $z_i$.
* **One-draw-per-candidate** keeps draw counts deterministic and simple to audit; the event envelope/trace proves counter conservation.
* **ISO ASCII tie-break** yields a **total order** even when floating-point keys collide, making selection deterministic across platforms.

## What S6 writes (at a glance; details in later substates)

* **Events:** `logs/rng/events/gumbel_key/...` — exactly $|\mathcal{F}_m|$ rows per merchant, with envelope + payload (`u` on (0,1), `key=z_i`, `selected`, `selection_order`).
* **Allocation:** `data/layer1/1A/country_set/...` — exactly $K_m{+}1$ rows (home rank 0 + foreign ranks 1..$K_m$) in **Gumbel order**; this dataset is the **authority** for cross-country order used by S7.

---

# S6.2 — Inputs (per merchant $m$)

## 1) Identity & home (authoritative)

* **Merchant key:** $\texttt{merchant_id}_m \in \mathbb{N}$ (id64).
* **Home ISO:** $c\in\mathcal{I}\subseteq \{\,\text{ISO2 uppercase}\,\}$.
  Both come from the **normalised ingress** seed (S0) validated by `schemas.ingress.layer1.yaml#/merchant_ids`. ISO shape is `"^[A-Z]{2}$"`.

## 2) Foreign count (from S4)

* **Target foreigns:** $K_m\in\{1,2,\dots\}$ (int). This is the **accepted** cross-border size coming out of S4 (lineage is visible in its RNG envelope and the S4 event stream per dictionary). S6 is *only* run when $K_m\ge1$.

## 3) Candidate prior weights (deterministic, from S5)

Let $\kappa_m\in\text{ISO4217}$ be the merchant’s **billing/settlement currency** (ISO-3, `"^[A-Z]{3}$"`). From S5 we read the **currency→country weights cache** `ccy_country_weights_cache`, keyed by $\kappa_m$, yielding a **currency expansion**:

$$
\big\{(\kappa_m,\ i,\ w_i^{(\kappa_m)})\ :\ i\in\mathcal{D}(\kappa_m)\subset \mathcal{I}\big\},
\qquad
\sum_{i\in\mathcal{D}(\kappa_m)} w_i^{(\kappa_m)} = 1,
$$

with $w_i^{(\kappa_m)}\in[0,1]$. S5 persisted these rows with a **group-sum-equals-1** constraint and schema checks (`iso2`, `iso4217`, `pct01`). (S5 also emits `sparse_flag` metadata where relevant, per dictionary.)

> **Interpretation.** $\mathcal{D}(\kappa_m)$ is the *raw* currency-driven candidate set; S6 will exclude the home ISO and **renormalise** on $\mathcal{F}_m=\mathcal{D}(\kappa_m)\setminus\{c\}$ in S6.3.

## 4) RNG lineage (shared envelope requirements)

Every S6 **`gumbel_key`** record must carry the shared RNG envelope from `schemas.layer1.yaml`:

$$
\{\texttt{ts_utc},\texttt{run_id},\texttt{seed}\in\texttt{uint64},\texttt{parameter_hash}\in\texttt{hex64},\texttt{manifest_fingerprint}\in\texttt{hex64},\texttt{module},\texttt{substream_label}=\text{``gumbel_key''},\texttt{rng_counter_before/after_{lo,hi}}\}.
$$

Substream discipline: one **open-interval** `u01` draw per candidate, counters advanced per the Philox $2\times64$ protocol in S0. (`u01` has exclusive bounds in the schema.) Paths/partitions are pinned in the data dictionary.

---

## Preconditions / guards S6 enforces before ranking

* **Presence:** have $(\texttt{merchant_id}_m, c, \kappa_m)$ and at least one cache row for $\kappa_m$. Missing cache ⇒ `missing_currency_weights(κ)` (abort).
* **ISO/ISO4217 shape:** `iso2`/`iso4217` regex per schema; any violation aborts upstream (ingress/S5).
* **Group sum:** verify $\sum_{i\in\mathcal{D}(\kappa_m)} w_i^{(\kappa_m)} = 1$ within serial-sum tolerance; else `bad_group_sum(κ)` (abort).
* **Feasibility hint:** after S6.3’s exclusion of home, S6 will require $K_m \le |\mathcal{F}_m|$; otherwise `insufficient_candidates` (abort).

---

## Minimal input check (supportive, numbered)

```text
INPUT: merchant_id, home_iso=c, currency=κ, K≥1, cache rows {(κ,i, w_i^(κ))}, lineage {seed, parameter_hash, manifest_fingerprint}
1  assert is_iso2(c) and is_iso4217(κ)                     # schema shapes
2  W := { (i, w_i) : rows where currency==κ }              # from S5 cache
3  assert |W| ≥ 1, else abort("missing_currency_weights", κ)
4  assert near_eq( serial_sum(w_i over W), 1.0, tol=1e-12 ) # deterministic left fold
5  assert K ≥ 1                                            # S6 domain
6  lineage := {seed, parameter_hash, manifest_fingerprint}; assert all present
7  set substream_label := "gumbel_key" for S6 event emissions
# (S6.3 will derive 𝔽 := {i in W : i ≠ c} and renormalise.)
```

---

# S6.3 — Candidate set and renormalisation (deep dive)

## 1) Construct the foreign candidate set

Start from the currency→country expansion emitted by **S5** for the merchant’s currency $\kappa_m$:
$\{(\kappa_m,i,w_i^{(\kappa_m)}) : i \in \mathcal{D}(\kappa_m)\subset\mathcal{I}\}$ with a **group-sum = 1** invariant. These rows live in `ccy_country_weights_cache` and are parameter-scoped per the dictionary.

Exclude the home ISO $c$ to form the **foreign** candidate index set:

$$
\boxed{ \ \mathcal{F}_m = \mathcal{D}(\kappa_m)\setminus\{c\},\quad M_m = |\mathcal{F}_m| \ }.
$$

If $M_m=0$, this contradicts entering S6 with $K_m\ge1$ → **abort** `no_foreign_candidates`. This guard is explicit in the S6 spec.

**Uniqueness & shapes.** `country_iso` must be unique within the cache key $\kappa_m$ and match the `iso2` pattern; duplicates or invalid ISO codes are structural failures (schema-enforced).

## 2) Renormalise to $\tilde w$ on the foreign set

Define the **foreign mass** (serial sum, binary64, left-fold):

$$
T_m \;=\; \sum_{j\in\mathcal{F}_m} w_j^{(\kappa_m)} .
$$

Then renormalise:

$$
\boxed{\ \tilde w_i \;=\; \frac{w_i^{(\kappa_m)}}{T_m}\quad \text{for } i\in\mathcal{F}_m \ },\qquad
\sum_{i\in\mathcal{F}_m} \tilde w_i = 1 \ \text{(up to tolerance)}.
$$

This is exactly the rule in your draft; S6 requires it because downstream **Gumbel-top-K** keys use $\log \tilde w_i$.

### Numeric policy (why these details matter)

* **Serial reduction.** Compute $T_m$ by a deterministic serial loop (no parallel reductions) to avoid cross-platform re-ordering drift. This is consistent with Layer-1 numeric policy.
* **Tolerance.** Assert $|\sum \tilde w_i - 1| \le 10^{-12}$ after renormalisation; if violated, abort `foreign_mass_sum_error`. (S7’s Dirichlet uses $10^{-6}$ but here weights are deterministic, so we can be stricter.)
* **Positivity.** Because S5 applies additive smoothing and has a fallback to equal splits in sparse cases, $w_i^{(\kappa_m)}\ge0$ and typically $>0$ on supported destinations. If **any** $\tilde w_i=0$ after excluding home, then `\(\log \tilde w_i\)` is undefined for S6.4; treat $\tilde w_i=0$ as a **schema/process violation of S5** and abort `zero_weight_in_foreign`. (The S5 spec’s smoothing/equal-split is designed precisely to avoid zeros.)

### Feasibility guard with $K_m$

Check $K_m \le M_m$. If $K_m>M_m$, **abort** `insufficient_candidates` (we **do not** silently reduce $K$; this maintains cross-branch consistency and matches the `country_set` contract that carries ranks $0..K_m$).

### Ordering canon (for later reproducibility)

Materialise a stable ISO-ascending order on $\mathcal{F}_m$ for any operations that need deterministic iteration before randomness (e.g., logging pre-draw context). The authoritative **inter-country** order, however, is established **after** Gumbel selection and persisted in `country_set.rank`; consumers must join there.

## 3) What is persisted/consumed at this point

S6.3 itself **does not** write datasets; it prepares $\mathcal{F}_m$ and $\tilde w$ in memory, to be consumed by S6.4’s Gumbel key draws (which will emit `gumbel_key` events and later `country_set`). The event schema in S6.4 will carry the **renormalised** `weight` field per candidate.

---

## Minimal reference algorithm (numbered, short)

```text
INPUT: home ISO c, currency κ, K≥1, cache rows W = { (i, w_i^(κ)) } for κ
OUTPUT: foreign candidate list F, renormalised weights {tilde_w_i}, M, K

1  # Build foreign set (exclude home)
2  F := [ (i, w) in W where i != c ]                 # stable ISO-asc iteration
3  M := |F|
4  if M == 0: abort("no_foreign_candidates", merchant_id, κ, c)

5  # Renormalise (serial, binary64)
6  T := 0.0
7  for (i, w) in F: T := T + w
8  if T <= 0.0: abort("zero_weight_in_foreign", merchant_id, κ)

9  tilde_w := { i -> (w/T) for (i, w) in F }         # binary64 division
10 s := 0.0; for i in F: s := s + tilde_w[i]
11 assert |s - 1.0| ≤ 1e-12, else abort("foreign_mass_sum_error", merchant_id)

12 if K > M: abort("insufficient_candidates", merchant_id, K, M)

13 return (F, tilde_w, M, K)
```

---

## Failure modes surfaced by S6.3 (all abort)

* `no_foreign_candidates`: $\mathcal{F}_m=\varnothing$ despite $K_m\ge1$.
* `insufficient_candidates`: $K_m>M_m$.
* `zero_weight_in_foreign`: $T_m\le0$ or any $\tilde w_i=0$ (violates S5’s smoothing/equal-split promise).
* `foreign_mass_sum_error`: renormalised sum not within $10^{-12}$ (deterministic arithmetic invariant breach). (Numeric policy in S0 applies.)

---



# S6.4 — RNG protocol & event contract

## Sub-stream, stride, counters (how draws are carved)

* **Label.** $\ell =$ `"gumbel_key"`. The Philox $2\times64$ sub-stream **stride** is

  $$
  J(\ell)=\mathrm{LE64}\big(\mathrm{SHA256}(\texttt{"gumbel_key"})\big),
  $$

  as per S0. Apply **one jump per merchant** when entering this module (before any candidate draw):
  $(c_{\text{hi}},c_{\text{lo}})\leftarrow(c_{\text{hi}},c_{\text{lo}})+J(\ell)$ with 64-bit carry. Optionally emit a `"stream_jump"` event with `reason="module_start"` and envelope counters to make the jump explicit.

* **Per-candidate consumption.** For each candidate $i\in\mathcal{F}_m$ we consume **exactly one** $u01$ deviate and, for envelope accounting simplicity, advance the Philox **counter by one block** (so `rng_counter_after = advance(before, 1)` for every event). This yields contiguous per-row counters and a trivial draw count (always 1) for `"gumbel_key"`. The `"gumbel_key"` event **must** carry the full RNG envelope schema `#/rng/core/rng_envelope`.

---

## Getting an open-interval $u\in(0,1)$ (bit-exact)

Let a Philox block yield two 64-bit unsigned integers $(R_0,R_1)$. For a single $u$:

$$
u \;=\; \frac{\big\lfloor R_0/2^{11}\big\rfloor + \tfrac{1}{2}}{2^{53}}
\in(0,1),
$$

i.e., keep the top 53 bits, add a half-ulp to stay **strictly inside** the interval, and scale. This satisfies the `u01` primitive in the schema (exclusive bounds). (We intentionally **discard** the second 64-bit word in this stream so each event advances by one counter block; the cost is negligible and simplifies envelope proofs.)

---

## Key computation (numerics & guards)

With renormalised $\tilde w_i\in(0,1]$ from S6.3 and $u_i\in(0,1)$:

$$
g_i \;=\; -\log\!\bigl(-\log u_i\bigr),\qquad
\boxed{\,z_i \;=\; \log \tilde w_i \;+\; g_i\,}.
$$

Implementation details:

* Precompute $\log\tilde w_i$ once; S6.3 guarantees $\tilde w_i>0$ (zero would have aborted earlier).
* Use binary64 math; check `isfinite(z_i)`; any `NaN/Inf` → abort `gumbel_key_invalid`.
* Persist both `u` and `key` in the event payload; `u` must satisfy the schema’s `u01`.

---

## Event payload (authoritative schema) & emission order

For **each** candidate $i\in\mathcal{F}_m$, emit one JSONL row at:

```
logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

with **exactly** these payload fields plus the shared envelope:
$\{\texttt{merchant_id},\ \texttt{country_iso}=i,\ \texttt{weight}=\tilde w_i,\ \texttt{u}=u_i,\ \texttt{key}=z_i,\ \texttt{selected},\ \texttt{selection_order}\}$.

* Types/constraints from `schemas.layer1.yaml#/rng/events/gumbel_key`:
  `merchant_id:id64`, `country_iso:iso2`, `weight:pct01`, `u:u01` (open interval), `key:number`, `selected:boolean`, `selection_order:int≥1, nullable`.
  Winners will set `selected=true` and `selection_order∈{1..K_m}`; losers set `selected=false`, `selection_order=null`. (Winners are determined by S6.5’s sort; you may buffer keys then write rows with the final flags in a single pass.)

* Partitioning and lineage are pinned by the dataset dictionary. **Every** row carries the RNG envelope (`seed`, `parameter_hash`, `manifest_fingerprint`, `substream_label="gumbel_key"`, and pre/post counters).

---

## Minimal reference algo (tight)

```text
INPUT: merchant m, foreign set 𝔽, renormalised weights {tilde_w_i}, K, envelope ctx
OUTPUT: JSONL events gumbel_key[ i ∈ 𝔽 ]

1  # enter substream once
2  (ctr_hi, ctr_lo) := add128((ctr_hi,ctr_lo), J("gumbel_key"))
3  emit stream_jump(reason="module_start", jump_stride=J("gumbel_key")), with envelope

4  # draw & compute keys
5  for i in 𝔽 (any deterministic iteration):
6      (before_hi, before_lo) := (ctr_hi, ctr_lo)
7      (R0, _) := philox2x64(ctr_hi, ctr_lo, seed)             # use first 64b, discard second
8      (ctr_hi, ctr_lo) := add128((ctr_hi,ctr_lo), 1)          # 1 block per event
9      u := ((floor(R0 / 2^11) + 0.5) / 2^53)                  # u01 open interval
10     key := log(tilde_w[i]) - log(-log(u))                   # == log w + Gumbel
11     store tmp[i] := {u, key}

12 # decide winners (S6.5): sort by (key desc, ISO asc), take top-K
13 let winners := topK( tmp, K )
14 # emit rows with flags & selection order
15 r := 0
16 for i in 𝔽 in any order:
17     if i in winners: r := r+1; selected := true; selection_order := r
18     else:            selected := false;        selection_order := null
19     emit gumbel_key{ merchant_id, country_iso=i, weight=tilde_w[i],
                       u=tmp[i].u, key=tmp[i].key, selected, selection_order },
                      with envelope {before, after=(ctr_hi,ctr_lo)}
```

---

## Contract checks (enforced here)

* One event per candidate, **always**; $M_m$ rows per merchant.
* Envelope present and consistent; `u∈(0,1)`, `weight∈(0,1]`, finite `key`.
* Selection flags consistent with the S6.5 ranking (top-$K_m$ true + 1..$K_m$; others false + null).
  Violations are hard aborts by the schema authority and dictionary policy.

---

# S6.5 — Selection rule (mathematical, under the hood)

## 1) Objects

* Foreign candidate index set $\mathcal{F}_m$ (home excluded), size $M_m\ge K_m$.
* For each $i\in\mathcal{F}_m$: renormalised weight $\tilde w_i\in(0,1]$ (from S6.3) and key

  $$
  z_i \;=\; \log \tilde w_i \;-\; \log\!\bigl(-\log u_i\bigr),\quad u_i\in(0,1)\ \text{(open interval; S6.4)}.
  $$

## 2) Total order (ties eliminated deterministically)

Define the **strict total order** $\succ$ on candidates:

$$
i \succ j \iff
\big(z_i > z_j\big)\ \text{or}\ \big(z_i=z_j\ \text{and}\ i<_{\mathrm{ASCII}} j\big).
$$

Why this is a **total** order:

* For any distinct $i\neq j$, either $z_i\neq z_j$ and one is larger, or $z_i=z_j$.
* If $z_i=z_j$, the ISO-2 codes are distinct (uniqueness is enforced upstream), and ASCII order is total, so exactly one of $i<_{\mathrm{ASCII}}j$ or $j<_{\mathrm{ASCII}}i$ holds.
* Antisymmetry and transitivity follow from real-number $>$ and lexicographic order properties.

**Implementation tip.** Sort by the composite key

$$
\kappa(i) := \big(-z_i,\ \mathrm{ISO}(i)\big),
$$

ascending in lexicographic order. This is equivalent to “$z$ descending, ISO ascending” and avoids depending on sort stability.

## 3) Selection and induced ranking

Let $\pi_m$ be the permutation of $\mathcal{F}_m$ that sorts by $\succ$:

$$
z_{\pi_m(1)} \ge z_{\pi_m(2)} \ge \dots \ge z_{\pi_m(M_m)},
$$

breaking equality by ISO as above. Define the **selected set** and **selection order**

$$
S_m \;=\; \{\pi_m(1),\dots,\pi_m(K_m)\},\qquad
\text{selection_order}(\pi_m(r)) := r,\quad r=1,\dots,K_m.
$$

Every $i\in S_m$ gets `selected=true`, `selection_order=r`; every $i\notin S_m$ gets `selected=false`, `selection_order=null`.

## 4) Probabilistic semantics (why this is the right sampler)

With $g_i:=-\log(-\log u_i)$ i.i.d. standard Gumbel, $z_i=\log\tilde w_i+g_i$. Then the order $\pi_m$ has the **Plackett–Luce** distribution with parameters $\tilde w$, hence the top-$K_m$ elements are a **weighted sample without replacement** from $\mathcal{F}_m$ with weights $\tilde w$. This matches the design goal: heavier $\tilde w_i$ are more likely to appear and to appear earlier, and no candidate can win twice.

## 5) Determinism & invariants (what validators assert)

* **D1 (uniqueness & coverage).** Exactly $K_m$ winners; each winner has a unique `selection_order ∈ {1..K_m}`; losers have `null`.
* **D2 (order reproducibility).** For fixed lineage (seed, parameter_hash, manifest_fingerprint), the vector $z$ is bit-replayable (S6.4), and the composite sort produces the **same** $\pi_m$ across replays and platforms (ASCII tie-break eliminates float-equality ambiguity).
* **D3 (consistency with events).** The `gumbel_key` event rows (one per candidate) must have `selected/selection_order` consistent with the top-$K_m$ of the **same** $z$ values logged in those rows.

## 6) Edge cases (explicit)

* **K equals pool size:** if $K_m=M_m$, all candidates are selected; `selection_order` is simply the $\succ$-rank $1..M_m$.
* **Equal keys in binary64:** measure-zero analytically, but can occur numerically; ISO tie-break resolves deterministically.
* **Zero or NaN keys:** impossible if S6.3 and S6.4 guards held ($\tilde w_i>0$, $u_i\in(0,1)$); if encountered, abort the merchant with `gumbel_key_invalid`.

---

## Minimal reference algorithm (tight)

```css
INPUT:  𝔽 = [i1..iM], keys z[i], K
OUTPUT: S = selected set, order = map(i → r or null)

1  idx := argsort_by( key(i) = (-z[i], ISO(i)) )     # z↓ then ISO↑
2  winners := take_first_K(idx, K)
3  order := { i: null for i in 𝔽 }
4  for r from 1..K: order[winners[r]] := r
5  S := set(winners)
6  return (S, order)
```

---



# S6.6 — Persistence (authoritative ordered set)

## 1) What you must write (row schema semantics)

For each merchant $m$ with Gumbel winners $(i_1,\dots,i_{K_m})$ and renormalised weights $\tilde w_{i_r}$ from S6.3, write **exactly $K_m+1$ rows** to **`country_set`** (partitioned by `{seed, parameter_hash}`):

* **Home row (rank 0).**

  ```
  { merchant_id=m,
    country_iso=c_home,
    is_home=true,
    rank=0,
    prior_weight=null }
  ```

* **Foreign rows (ranks 1..K_m) in Gumbel order.**
  For each r = 1..K_m with ISO i_r,

  ```
  { merchant_id=m,
    country_iso=i_r,
    is_home=false,
    rank=r,
    prior_weight=tilde_w[i_r] }      # binary64; ∈ (0,1), serially computed
  ```

**Keys & constraints (authoritative):**

* **PK:** `(merchant_id, country_iso)` — uniqueness within each `{seed, parameter_hash}` partition.
* **FK:** `country_iso` must be valid ISO-2.
* **Order carrier:** `rank` is the **only** persistent carrier of inter-country order (0 = home; 1..K = Gumbel order). **Consumers must join on this `rank`**; row/file order is irrelevant.
* **`prior_weight` typing:** `null` only for the home row; otherwise a `pct01` float in **(0,1)**. (These are the **foreign-renormalised** weights; their serial sum should equal 1 within tight tolerance.)

**Partition path (deterministic):**

```
data/layer1/1A/country_set/
  seed={seed}/parameter_hash={parameter_hash}/part-*.parquet
```

---

## 2) Determinism, idempotency, and write policy

* **Determinism.** Given fixed lineage (seed, parameter_hash, manifest_fingerprint), S6.4’s keys $z$ are bit-replayable, S6.5’s top-K is deterministic (ASCII tiebreak), so $(i_1,\dots,i_{K_m})$ is fixed; `country_set` rows are therefore **bit-replayable** (modulo file ordering).
* **Idempotency.** Use **merge-by-PK** semantics inside a `{seed, parameter_hash}` partition:

  * if `(merchant_id, country_iso)` exists, **replace** the entire row (rank/weight) with the newly computed values for this run;
  * otherwise **insert**.
    This ensures re-runs of the same lineage overwrite cleanly without duplicates.
* **No hidden order.** Never rely on implicit ordering (e.g., write sequence); **only** `rank` defines inter-country order across the platform.
* **Numeric policy.** Store `prior_weight` exactly as computed in binary64 (no decimal rounding); verify the **foreign** weights’ serial sum is $1\pm 10^{-12}$ before writing.

---

## 3) Invariants to check before/after write

**Row-level:**

* Exactly **one** home row: `is_home=true`, `rank=0`, `prior_weight=null`, `country_iso == home_iso(m)`.
* Exactly **K_m** foreign rows: `is_home=false`, `rank ∈ {1..K_m}`, `prior_weight∈(0,1)`.
* **No duplicates** of `country_iso` within the $K_m$ foreign rows; none equals the home ISO.

**Rank/order:**

* Ranks are **contiguous**: $\{0,1,\dots,K_m\}$ appear **once** each.
* The mapping `rank → country_iso` equals $(0→c,\ 1→i_1,\dots, K_m→i_{K_m})$.

**Weights:**

* For foreign rows: $\sum_{r=1}^{K_m}\tilde w_{i_r} = 1 \pm 10^{-12}$ (serial left-fold).
* Each $\tilde w_{i_r} > 0$ (S6.3 already ensured positivity).

**Cross-artefact coherence:**

* For each foreign ISO $i$, the corresponding `gumbel_key` event has `selected=true` and `selection_order=r` where this table has `rank=r`.
* For losers (not in `country_set`), `gumbel_key.selected=false` and `selection_order=null`.

Violations are **hard aborts** (schema + validator).

---

## 4) Failure modes (abort semantics)

* `missing_home_row` / `home_iso_mismatch`: no home row or wrong ISO at `rank=0`.
* `rank_set_incomplete`: ranks are not exactly `{0..K}` or contain duplicates.
* `duplicate_country_iso`: PK collision across foreign rows.
* `weight_sum_violation`: $\sum_{r=1}^K \tilde w_{i_r}$ not in $1\pm 10^{-12}$.
* `null_weight_foreign` or `nonnull_weight_home`.
* `event_sync_failure`: mismatch with `gumbel_key` selections (selected flags or `selection_order` don’t match ranks).

---

## 5) Minimal reference algorithm (tight, language-agnostic)

```text
INPUT:
  merchant_id m, home c, winners [i1..iK] in Gumbel order, tilde_w map, seed, parameter_hash

OUTPUT:
  write K+1 rows into country_set partition seed={seed}, parameter_hash={parameter_hash}

1  rows := []
2  # home row
3  rows.append({merchant_id:m, country_iso:c, is_home:true,  rank:0, prior_weight:null})

4  # foreign rows in order
5  for r in 1..K:
6      i := winners[r]
7      w := tilde_w[i]; assert w>0
8      rows.append({merchant_id:m, country_iso:i, is_home:false, rank:r, prior_weight:w})

9  # invariants
10 assert unique(country_iso over rows) and ranks(rows) == {0..K}
11 assert abs(serial_sum(prior_weight over rows where is_home==false) - 1.0) ≤ 1e-12

12 upsert rows into country_set using PK=(merchant_id,country_iso)
```

---

## 6) What this guarantees downstream

* **S7** (integerisation) can rely on `country_set.rank` as the definitive inter-country order (home rank 0; foreign ranks 1..K in Gumbel order).
* No other dataset encodes this order; `outlet_catalogue` will not. Any consumer that needs inter-country order must **join** back to `country_set` on `(merchant_id, country_iso)` and use `rank`.

---



# S6.7 — Determinism & correctness invariants (deep dive)

Let $\mathcal{F}_m$ be the foreign candidate set (size $M_m$), $\tilde w=(\tilde w_i)_{i\in\mathcal{F}_m}$ the *foreign-renormalised* weights, $K_m\ge 1$ the target winners, and $\ell=$"gumbel_key" the S6 sub-stream label. For each $i$, the event logs one open-interval uniform $u_i\in(0,1)$ and the key

$$
z_i=\log \tilde w_i - \log(-\log u_i).
$$

Winners are the top-$K_m$ by the strict total order “$z$ descending, ISO ascending”.

---

## I-G1 — Bit-replay (full determinism)

**Statement.** Fix $(\tilde w,\ K_m,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$. Then the vector of uniforms $(u_i)_{i\in\mathcal{F}_m}$, the keys $(z_i)$, the selected set $S_m$, and the induced selection orders $r=1..K_m$ are **bit-identical** across replays.

**Why.**

1. **Counter discipline.** We jump once by $J(\ell)$ and then consume **exactly one** Philox block per candidate (deterministic iteration over $\mathcal{F}_m$; e.g., ISO-ascending).
2. **u01 mapping.** Each block yields 64 bits $\to$ one $u=(\lfloor R/2^{11}\rfloor+\tfrac12)/2^{53}\in(0,1)$; this is a pure, platform-independent function of the block output.
3. **Pure transforms.** $z_i=\log \tilde w_i - \log(-\log u_i)$ is deterministic in binary64 for fixed inputs; ties are resolved by ASCII, a total order on two-letter codes.
   Hence $u$, $z$, and the top-$K$ are fixed functions of the lineage tuple.

**Audit hook.** Envelope counters satisfy `after = advance(before, 1)` (one block per event). Replaying the same lineage regenerates the same counters, $u$, and $z$.

---

## I-G2 — Event coverage (cardinality & shape)

**Statement.** Exactly **$M_m$** `gumbel_key` events per merchant: one per candidate $i\in\mathcal{F}_m$. Selected rows have `selected=true` and `selection_order∈{1..K_m}`; non-selected have `selected=false` and `selection_order=null`. Missing/extra rows or illegal `selection_order` is a structural failure.

**Why.** There is exactly one draw per candidate; the sort is over precisely those $M_m$ keys; winners are exactly $K_m$.

**Audit hook.** `rng_trace_log` shows `draws=1` for each row, and counters advance by +1 block row-wise.

---

## I-G3 — Weight & ISO constraints (domain validity)

**Statement.** Every row satisfies:

* `country_iso` is valid ISO-2 and unique per merchant;
* `weight = \tilde w_i ∈ (0,1]`; and $\sum_{i\in\mathcal{F}_m}\tilde w_i = 1$ within tight tolerance (serial sum);
* `u` conforms to open-interval `u01`.

**Why.** S6.3 enforces positivity and renormalisation; S5 prevents zero mass via smoothing; ISO shape & uniqueness are schema-guarded.

**Audit hook.** Re-sum the `weight` column per merchant and assert $|\sum\tilde w-1|\le 10^{-12}$; regex and FK checks for `country_iso`; `0<u<1`.

---

## I-G4 — Tie-break determinism (total order)

**Statement.** If $z_i=z_j$ at binary64, order by `ISO` (ASCII ascending). Thus selection order is a pure function of $(\tilde w, u)$—no dependence on sort stability or runtime vagaries.

**Why.** ASCII lexicographic is a total order on two uppercase letters; combined with $z$ gives a strict total order. This eliminates platform-dependent ties.

**Audit hook.** Verify `argsort_by((-z, ISO_ASC))` reproduces the winners and their ranks.

---

## I-G5 — `country_set` coherence (cross-artefact consistency)

**Statement.** Persist **exactly one** home row (`rank=0`) and **$K_m$** foreign rows with `rank=1..K_m` in the **same order** as the winners’ `selection_order`. Any mismatch between `country_set.rank` and the winners’ `selection_order` is a validation failure.

**Why.** `country_set` is the **only** authoritative carrier of inter-country order; it must reflect the Gumbel result exactly.

**Audit hook.** Join `country_set` to the merchant’s `gumbel_key` winners on `(merchant_id, country_iso)` and assert `rank == selection_order` (home checked separately).

---

### Derived checks (should hold; validators assert)

* **Counter conservation.** For each event: `after = advance(before, 1)`; for the module: per-merchant draw count equals $M_m$.
* **Winner uniqueness.** Exactly $K_m$ rows with `selected=true` and distinct `selection_order` $1..K_m$.
* **Rank contiguity in `country_set`.** Ranks are exactly $\{0,1,\dots,K_m\}$ with no gaps or duplicates; home has `prior_weight=null`, foreign rows have strictly positive `prior_weight` and serial sum $1\pm 10^{-12}$.

---

## Edge cases (explicit)

* **$K_m=M_m$.** All candidates selected; `selection_order` $=1..M_m$; `country_set` has ranks $1..M_m$ in that order.
* **Binary64 key collisions.** Resolved deterministically by ISO tie-break; extremely rare but fully specified.
* **Bad inputs (guarded upstream).** Zero or NaN weights; $M_m=0$ or $K_m>M_m$; invalid ISO—all trigger earlier aborts; encountering them in S6.7 implies a pipeline breach.

---

## Minimal validator (tight, numbered)

```text
INPUT:
  G = gumbel_key events for merchant m
  C = country_set rows for m
  K = target foreign count from S4
  F = |foreign candidates| from S6.3 (should equal |G|)

# Coverage & shape (I-G2, I-G3)
1  assert |G| == F >= K
2  assert all 0 < row.u < 1 and 0 < row.weight ≤ 1
3  assert abs(serial_sum(row.weight over G) - 1.0) ≤ 1e-12
4  assert ISO2 regex on all row.country_iso and unique per merchant

# Deterministic order (I-G4)
5  z := {i -> row.key}; iso := {i -> row.country_iso}
6  idx := argsort_by( (-z[i], iso[i]) )                  # z↓ then ISO↑
7  winners := take_first_K(idx, K)
8  # check flags & selection_order
9  seen := ∅
10 for t in 1..F:
11     i := idx[t]
12     if t ≤ K:
13         assert G[i].selected == true and G[i].selection_order == t
14         assert t ∉ seen; seen := seen ∪ {t}
15     else:
16         assert G[i].selected == false and G[i].selection_order is null

# country_set coherence (I-G5)
17 home := exactly_one_row(C where is_home==true, rank==0)
18 assert sum(!is_home over C) == K and ranks(C where !is_home) == {1..K}
19 map_cs := { row.country_iso -> row.rank for row in C where !row.is_home }
20 for r in 1..K:
21     i := winners[r]
22     assert map_cs[ G[i].country_iso ] == r

# Bit replay hooks (I-G1)
23 assert for each event e in G: e.after == advance(e.before, 1)
24 assert rng envelope fields (seed, parameter_hash, manifest_fingerprint, substream_label="gumbel_key") present in every row
```

---

# S6.8 — Failure modes (abort semantics)

We index foreign candidates by $\mathcal{F}_m$ (size $M_m$), target winners $K_m\ge1$, currency $\kappa_m$, renormalised weights $\tilde w$, and substream label $\ell=$"gumbel_key".

## F-G1 — Insufficient candidates (hard abort in S6.3)

**Predicate.**

$$
(M_m = 0)\ \ \text{or}\ \ (K_m > M_m).
$$

**Where it trips.** Immediately after forming $\mathcal{F}_m$ and before any RNG:

* `no_foreign_candidates(merchant_id, home_iso, κ)` if $M_m=0$.
* `insufficient_candidates(merchant_id, K_m, M_m)` if $K_m>M_m$.

**Rationale.** We do **not** collapse $K_m$; `country_set` requires ranks $0..K_m$ and downstream states assume the original $K_m$.

---

## F-G2 — Missing weights (hard abort at input load / renormalisation)

**Predicates.**

* No cache rows for $\kappa_m$: $|\mathcal{D}(\kappa_m)|=0$.
* Foreign mass non-positive or fails tight sum check:

  $$
  T_m=\sum_{i\in\mathcal{F}_m} w_i^{(\kappa_m)} \le 0
  \quad\text{or}\quad
  \left|\sum_{i\in\mathcal{F}_m} \tilde w_i - 1\right| > 10^{-12}.
  $$

**Errors.**

* `missing_currency_weights(merchant_id, κ)`.
* `zero_weight_in_foreign(merchant_id, κ)` (if $T_m\le 0$).
* `foreign_mass_sum_error(merchant_id, κ, observed_sum)` (post-renormalisation tolerance breach).

**Rationale.** S5 guarantees a well-formed prior by currency; failures imply upstream data integrity issues.

---

## F-G3 — Schema / envelope violation (hard abort during event emission)

**Per-event predicates** for each `gumbel_key` row:

* Envelope missing any required field (`seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label="gumbel_key"`, `rng_counter_{before,after}_{hi,lo}`).
* Counter conservation fails: `after ≠ advance(before, 1)` (exactly one Philox block per candidate).
* Payload violations:

  * `country_iso` fails ISO-2 shape or FK.
  * `weight = \tilde w_i ∉ (0,1]`.
  * `u ∉ (0,1)` (must be **open interval**).
  * `key` non-finite (`NaN`/`±Inf`).
  * `selected=true` with illegal `selection_order∉{1..K_m}`; or `selected=false` with non-null `selection_order`.

**Errors.**

* `rng_envelope_missing(field)` / `substream_label_mismatch(actual="...")`.
* `counter_conservation_failure(before, after)`.
* `payload_domain_violation(field, value)`.
* `selection_flag_inconsistent(merchant_id, country_iso)`.

**Rationale.** These guarantee replayability and correctness of the per-candidate randomness and classification.

---

## F-G4 — Order persistence gap (validation abort post-run)

**Predicates (join `gumbel_key` ↔ `country_set`).**

* At least one `gumbel_key.selected=true` for merchant $m$, but:

  * missing **home row** in `country_set` (rank $0$), **or**
  * foreign row count $\ne K_m$, **or**
  * some winner $(merchant_id, country_iso)$ absent in `country_set`, **or**
  * rank mismatch: `country_set.rank(country_iso) ≠ selection_order(country_iso)`.

**Errors.**

* `missing_home_row(merchant_id)` / `home_rank_invalid(rank)`.
* `country_set_cardinality_mismatch(merchant_id, expected=K_m, observed)`.
* `winner_missing_in_country_set(merchant_id, country_iso)`.
* `rank_selection_order_mismatch(merchant_id, country_iso, rank, selection_order)`.

**Rationale.** `country_set` is the sole authority for cross-country order; it must mirror the Gumbel winners exactly.

---

## (Optional, recommended) Additional fail-closed guards

These are natural adjuncts to the bullets above; add them if you want stricter safety:

* **Duplicate candidate rows for a merchant.** `duplicate_candidate_iso(merchant_id, country_iso)`.
* **Winner uniqueness.** Duplicated `selection_order` in `gumbel_key` → `duplicate_selection_order(merchant_id, r)`.
* **K==M sanity.** If $K_m=M_m$ and any `selected=false` exists → `unexpected_loser_when_K_eq_M(merchant_id)`.

---

## Minimal validator (tight, numbered)

```text
INPUT:
  G = all gumbel_key rows for merchant m
  C = all country_set rows for m
  K = target foreign count from S4
  F = |foreign candidates| from S6.3
  iso_home = home_iso(m)

# F-G1 / F-G2 (inputs & renormalisation)
1  assert F ≥ 1 and K ≥ 1
2  assert K ≤ F, else abort("insufficient_candidates", m, K, F)
3  assert near_eq( serial_sum(weight over G), 1.0, 1e-12 )

# F-G3 (schema/envelope/payload per row)
4  for e in G:
5      assert e.substream_label == "gumbel_key"
6      assert after(e) == advance(before(e), 1)
7      assert is_iso2(e.country_iso) and 0 < e.weight <= 1
8      assert 0 < e.u01 < 1 and isfinite(e.key)
9      if e.selected:  assert 1 <= e.selection_order <= K
10     else:           assert e.selection_order is null

# Selection consistency (derive winners from keys)
11 idx := argsort_by( (-e.key, e.country_iso) for e in G )
12 winners := take_first_K(idx, K)
13 seen := ∅
14 for t in 1..F:
15     i := idx[t]
16     if t ≤ K:
17         assert G[i].selected and G[i].selection_order == t
18         assert t ∉ seen; seen := seen ∪ {t}
19     else:
20         assert !G[i].selected and is_null(G[i].selection_order)

# F-G4 (country_set coherence)
21 home := exactly_one(C where is_home==true and rank==0 and country_iso==iso_home)
22 assert count(C where is_home==false) == K
23 map_cs := { row.country_iso -> row.rank for row in C where !row.is_home }
24 for t in 1..K:
25     i := winners[t]
26     assert map_cs[G[i].country_iso] == t

# If any assertion fails, raise the corresponding error code above.
```

This spells out *exactly* when S6 must fail closed, what error to raise, and how a validator proves it: candidate sufficiency, weight presence & sums, strict schema/envelope correctness for every `gumbel_key` event, and a perfect mirror of winners into `country_set`.

---

# S6.9 — Inputs → outputs (state boundary)

## Inputs (per merchant $m$)

Let $K_m\ge 1$ (from S4), home ISO $c\in\mathcal{I}$, currency $\kappa_m\in\mathrm{ISO4217}$.

* **Lineage/RNG:** `seed` (u64), `parameter_hash` (hex64), `manifest_fingerprint` (hex64).
* **Currency→country priors (from S5 cache):** $\{(\kappa_m,i,w_i^{(\kappa_m)}) : i\in\mathcal{D}(\kappa_m)\}$ with serial-sum $=1$.
* **Derived in S6.3:** foreign set $\mathcal{F}_m=\mathcal{D}(\kappa_m)\setminus\{c\}$, $M_m=|\mathcal{F}_m|$; foreign-renormalised weights $\tilde w_i = w_i^{(\kappa_m)}/\sum_{j\in\mathcal{F}_m}w_j^{(\kappa_m)}$ (serial-sum $=1$ within $10^{-12}$).

**Preconditions (already enforced in S6.2–S6.4):**

* $M_m\ge K_m$, all ISO valid/unique; each $\tilde w_i\in(0,1]$.

---

## Outputs (persisted artefacts)

1. **RNG event stream — `gumbel_key`**
   Path:

```
logs/rng/events/gumbel_key/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

Cardinality: **exactly $M_m$** rows for merchant $m$ (one per candidate $i\in\mathcal{F}_m$).
Each row carries the **shared RNG envelope** and payload:

```
{ merchant_id, country_iso=i, weight=tilde_w[i], u∈(0,1), key=z_i,
  selected∈{true,false}, selection_order∈{1..K_m} or null }
```

with `z_i = log(tilde_w[i]) - log(-log u)` and **counter conservation** `after = advance(before, 1)` (one block per row).

2. **Allocation dataset — `country_set`**
   Path:

```
data/layer1/1A/country_set/
  seed={seed}/parameter_hash={parameter_hash}/part-*.parquet
```

Cardinality: **$K_m+1$** rows:

* Home row: `(merchant_id=m, country_iso=c, is_home=true,  rank=0, prior_weight=null)`.
* Foreign rows $r=1..K_m$ in **Gumbel order** $(i_1,\dots,i_{K_m})$:
  `(merchant_id=m, country_iso=i_r, is_home=false, rank=r, prior_weight=tilde_w[i_r])`.

**Keys & invariants:** PK `(merchant_id,country_iso)`; ranks are exactly $\{0,1,\dots,K_m\}$; foreign `prior_weight` serial-sums to $1\pm 10^{-12}$. `country_set` is the **sole authority** for inter-country order.

---

## Hand-off to S7 (in-memory tuple)

Alongside writes, S6 yields a typed hand-off consumed by S7 for integerisation:

$$
\Xi^{(6\to7)}_m :=
\big(
C_m=(c,i_1,\dots,i_{K_m}),\
\tilde w_m=[\,\tilde w_{i_1},\dots,\tilde w_{i_{K_m}}\,],\
C^{\star}_m
\big),
$$

where:

* $C_m$ is the **ordered** country tuple (home, then Gumbel winners).
* $\tilde w_m$ are the aligned **foreign** prior weights (home has no prior weight).
* $C^{\star}_m$ is the **Philox counter cursor** after the **last** `gumbel_key` event for $m$ (exactly the final `rng_counter_after_{hi,lo}`); S7’s first event must start from this cursor, then jump to its own label (e.g., `"dirichlet_gamma_vector"`).

This guarantees **RNG continuity** and locks the order/weights S7 consumes to the persisted `country_set`.

---

## Boundary checks (must pass before leaving S6)

* **Event counts:** $|\text{gumbel_key rows for }m| = M_m$.
* **Winners/ranks:** exactly $K_m$ rows with `selected=true`, unique `selection_order=1..K_m`.
* **`country_set` coherence:** foreign rows count $=K_m$; for each winner $i_r$, `rank(i_r)=r`. Home row present and correct.
* **Weights:** foreign `prior_weight` $>0$ and serial-sum $=1\pm 10^{-12}$.
* **Counter continuity:** S7’s first envelope `rng_counter_before` equals $C^{\star}_m$.

---

## Minimal boundary recipe (10 lines)

```css
INPUT: c, κ, K; F=foreign ISOs; tilde_w[i]; gumbel rows (u, z, selected, sel_order); last_counter
OUTPUT: country_set rows; hand-off Ξ^(6→7)

1  assert |gumbel_rows|==|F| and exactly K winners with sel_order 1..K
2  winners := [i₁..i_K] sorted by (z desc, ISO asc)
3  write country_set row (m,c,true, 0, null)
4  for r=1..K: write country_set row (m, i_r, false, r, tilde_w[i_r])
5  assert ranks=={0..K} and sum(prior_weight over foreign)==1±1e-12
6  C* := last_counter_after(gumbel_rows)
7  Ξ := ( C=(c,i₁..i_K), tilde_w=[tilde_w[i₁]..tilde_w[i_K]], C* )
8  handoff_to_S7(Ξ)
```

That’s the whole **S6** boundary: what you must have on disk (events + ordered set) and what S7 must see in memory, with RNG counters stitched cleanly from one state to the next.

---