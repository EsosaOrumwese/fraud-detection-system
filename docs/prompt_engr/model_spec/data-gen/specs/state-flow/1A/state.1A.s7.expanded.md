# S7.1 — Purpose (deepened)

We define a deterministic map that, for each merchant $m$, takes:

* a **total outlet count** $N \in \mathbb{Z}_{\ge 1}$, and
* an **ordered** country set $C=(c_0,\dots,c_K)$ (home first, then up to $K$ foreign countries carried forward from S6),

and returns:

1. a **Dirichlet weight vector** $w=(w_0,\dots,w_K)\in[0,1]^{K+1}$ with $\sum_{i=0}^{K} w_i = 1$, sampled once using the merchant-specific Dirichlet concentration parameters $\alpha$ (dimension $K+1$), and

2. a **deterministic integer allocation** $n=(n_0,\dots,n_K)\in\mathbb{Z}_{\ge 0}^{K+1}$ produced from the real allocations $a_i=N\,w_i$ by **largest-remainder rounding** together with **deterministic tie-breaks**, such that

$$
\sum_{i=0}^{K} n_i \;=\; N.
$$

The **ordering of $C$** is authoritative (home at rank 0, then the foreigns in the **Gumbel order** produced in S6). All stochastic draws and rounding decisions are logged as RNG events so that the allocation is **bit-replayable** given the run lineage (seed, parameter hash, manifest fingerprint).

Special (domestic-only) case: when $K=0$ (or cross-border was ruled out upstream), we force $w=(1)$ and $n=(N)$. Even then, we emit a **single** residual/rounding event with residual $0.0$ and rank $1$ so event counts remain consistent.

---

# S7.2 — Inputs (per merchant $m$, deepened)

## 1) Final outlet count

* $N \in \mathbb{Z}_{\ge 1}$ — the **final** count from S2 after zero-truncation.
  **Preconditions:** integer type, $N\ge 1$.

## 2) Ordered country set

* $C=(c_0,\dots,c_K)$ with:

  * $c_0=\text{home_country}(m)$,
  * for $j\ge 1$, $c_j$ are the candidate foreign countries,
  * **rank constraint:** $\mathrm{rank}(c_j)=j$ (home has rank 0; foreigns retain the **Gumbel order** from S6),
  * **length:** $|C|=K+1$.
* **Authority:** the dataset `country_set` is the **sole** source of truth for both membership and order; S7 must not reorder or mutate $C$.
  **Preconditions:** all entries are valid ISO-2 codes; no duplicates; $c_0$ equals merchant’s home ISO.

## 3) Dirichlet concentration parameters

* $\alpha=(\alpha_0,\dots,\alpha_K) \in \mathbb{R}^{K+1}_{>0}$.
* **Lookup key:** $(\text{home_country}(m),\ \text{MCC}(m),\ \text{channel}(m),\ m=K{+}1)$ into the **cross-border hyperparameters** used by the 1A allocator. This ensures the $\alpha$ **dimension matches** $|C|$.
  **Preconditions:** every $\alpha_i>0$; the returned vector length is exactly $K+1$. If $K=0$, $\alpha$ is not used (we force $w=(1)$).

> Intuition: larger $\alpha_i$ nudges more expected mass toward country $c_i$. The shape $(K{+}1)$ binds the stochastic object to the exact cardinality and order of $C$.

## 4) Determinism context (lineage + RNG)

* `seed` — the Philox $2\times 64$-10 master key for the run (from S0.3.2).
* `parameter_hash` — 256-bit key that versions the **parameter-scoped** artefacts (hyperparameters, etc.).
* `manifest_fingerprint` — 256-bit run lineage key that versions **egress/validation** artefacts and is embedded in all RNG envelopes.
* **Sub-stream labels** — the fixed strings used in S7’s RNG events (e.g., `"dirichlet_gamma_vector"`, `"residual_rank"`); they determine the deterministic **jump** offsets applied to the counter before each labelled draw (per S0 conventions).
  **Preconditions:** these values are present and fixed before S7 begins; every event S7 emits must carry the shared RNG envelope with these fields.

## 5) Degenerate (domestic-only) path

If **either**:

* $K=0$ (i.e., $C=(\text{home})$), **or**
* S3 previously marked the merchant as cross-border ineligible,

then S7 does **no** Dirichlet sampling:

$$
C=(\text{home}),\quad w=(1),\quad n_0=N.
$$

Nonetheless, S7 **still logs** exactly **one** residual/rounding event with `residual = 0.0` and `residual_rank = 1`, preserving event-count invariants across all merchants.

---

## Input sanity checklist (quick, explicit)

* $N \in \mathbb{Z}_{\ge 1}$.
* $C$ non-empty, rank-consistent: $|C|=K{+}1$, $c_0=\text{home}$, no duplicates, ISO-2 valid.
* If $K\ge 1$: $\alpha \in \mathbb{R}^{K+1}_{>0}$ (right length, strictly positive).
* Lineage/RNG fields present and stable: `seed`, `parameter_hash`, `manifest_fingerprint`; sub-stream labels known.
* If $K=0$ or ineligible: skip Dirichlet; force $w=(1)$, $n_0=N$; emit one residual record.

---

# S7.3 — Numeric environment (determinism)

## 1) Arithmetic model

All stochastic arithmetic in S7 is done in IEEE-754 **binary64** with round-to-nearest ties-to-even. We denote the correctly-rounded binary64 of a real expression $\psi$ by

$$
\mathrm{R}_{64}[\psi].
$$

Products and sums that can influence ordering (Dirichlet normalisation and residual ranking) are computed as **serial two-step** operations with **FMA disabled**:

$$
\text{mul}(a,b) := \mathrm{R}_{64}[a\cdot b],\qquad
\text{add}(x,y) := \mathrm{R}_{64}[x+y],\qquad
\text{fma_off}(a,b,c) := \mathrm{R}_{64}\!\big(\mathrm{R}_{64}[a\cdot b] + c\big).
$$

No fused-multiply-add is permitted in these paths. This mirrors the state-level policy and is part of the fingerprinted environment.

## 2) Deterministic serial reductions

For any finite sequence $v_1,\dots,v_m$ whose sum affects branching or ranking, use a **left fold** in **ascending country rank**:

$$
S_0:=0,\qquad S_i:=\text{add}(S_{i-1},\,v_i)\ \ (i=1,\dots,m).
$$

This reducer is used for the Dirichlet normaliser $S=\sum_i G_i$ and for subsequent checks; no pairwise/parallel/Kahan sums are allowed in these ordering-sensitive paths.

## 3) Residual quantisation (8 dp, before sorting)

Define the 8-decimal **quantiser** $Q_8:[0,1)\to[0,1)$ by

$$
Q_8(x)\;:=\;\mathrm{R}_{64}\!\Big(\mathrm{R}_{64}\!\big(x\cdot 10^8\big)\,/\,10^8\Big).
$$

This is “round to nearest, ties-to-even” at **exactly eight** decimal places, implemented with binary64 operations only. The quantised residual used for ranking is

$$
r_i \;:=\; Q_8\big(a_i-\lfloor a_i\rfloor\big),\qquad a_i:=\mathrm{R}_{64}[N\cdot w_i].
$$

Residual **sorting** later consumes $\{r_i\}$ (not the raw fractions); ties are then broken deterministically by ISO code. Quantising before sort eliminates platform drift due to tiny last-bit differences.

**Quantisation error bound.** For $x\in[0,1)$,

$$
\big|Q_8(x)-x\big| \;\le\; 5\times10^{-9}\;+\;O(\varepsilon_{64}),
$$

where $\varepsilon_{64}=2^{-53}$ is machine epsilon. Hence two residuals closer than $\approx 5\cdot 10^{-9}$ may quantise to the same value—exactly the case we resolve with the ISO tie-break.

## 4) Sum-to-one check for Dirichlet weights

After serial normalisation $w_i=G_i/S$ with $S=\sum_i G_i$, enforce the schema-level constraint

$$
\delta \;:=\; \Big|\;1 - \sum_{i=1}^m w_i\;\Big|
\;\le\; 10^{-6},
$$

with the inner sum evaluated by the **same serial reducer** in rank order. Violations **abort** the run (this tolerance matches the event-schema constraint for the Dirichlet payload).

## 5) Implementation obligations (concise)

* Use **binary64** everywhere in S7’s stochastic math; disable FMA in Dirichlet normalisation and residual operations.
* Perform all sums via the **serial left fold** in country-rank order.
* Compute residuals, then apply **$Q_8$** **before** sorting. Store and emit the quantised residuals.
* Enforce $\sum w_i = 1 \pm 10^{-6}$ using serial summation; mismatch ⇒ abort per schema.

That’s the whole numeric contract for S7: binary64 + FMA-off, deterministic serial sums, 8-dp residual quantisation **pre-sort**, and a hard $10^{-6}$ tolerance on the Dirichlet weights’ sum-to-one check.

---

# S7.4.1 — Algorithm (Dirichlet weights over $C$; skip when $|C|=1$)

Let $C=(c_1,\dots,c_m)$ in the **country_set order** (home first, then Gumbel-ordered foreigns), with $m=|C|=K{+}1$. Look up $\alpha=(\alpha_1,\dots,\alpha_m)\in\mathbb{R}^m_{>0}$ from the cross-border hyperparameters keyed by $(\text{home},\text{MCC},\text{channel},m)$. If $m=1$ we **skip** the sampler and force $w=(1)$ (handled elsewhere).

## A) RNG label and counter jump (once per merchant)

Use the sub-stream label $\ell_1=$"dirichlet_gamma_vector". Compute the 64-bit stride $J(\ell_1)$ and **jump** the Philox $2\times64$ counter by add-with-carry on the low word **before** any consumption for this merchant’s Dirichlet draw. All draws for this section occur under $\ell_1$ and are evidenced by the shared RNG envelope in the single emitted event and by the `rng_trace_log` draw count; counters must satisfy block conservation.

## B) Gamma components via Marsaglia–Tsang (independent across $i$)

We draw independent $G_i\sim\mathrm{Gamma}(\alpha_i,1)$ for $i=1,\dots,m$, then normalise to Dirichlet. For numerical determinism, all arithmetic is IEEE-754 binary64 with **serial** operations (no FMA in ordering-sensitive paths).

### B.1 Standard normal from u01 pairs (fixed transform)

Define a deterministic generator for $Z\sim\mathcal{N}(0,1)$ using **Box–Muller** with **no spare caching** (keeps consumption accounting simple and reproducible):

* Draw $(U_1,U_2)\in(0,1)^2$ as open-interval uniforms (`u01`), each from a Philox 64-bit word $z$ via
  $U=\big(\lfloor z/2^{11}\rfloor+\tfrac{1}{2}\big)/2^{53}\in\big(\tfrac{1}{2^{54}},1-\tfrac{1}{2^{54}}\big)$.
* Set $Z=\sqrt{-2\ln U_1}\,\cos(2\pi U_2)$.
  This costs **two** u01 per $Z$.

### B.2 Marsaglia–Tsang kernel (shape $\alpha\ge1$)

For $\alpha\ge1$, set $d=\alpha-\tfrac{1}{3}$, $c=(9d)^{-1/2}$. Repeat:

1. $Z\leftarrow\mathcal{N}(0,1)$ (two u01), $V=(1+cZ)^3$. If $V\le0$, restart.
2. Draw $U\sim(0,1)$ (one u01).
3. Accept if $U<1-0.0331\,Z^4$; otherwise accept if

$$
\ln U \;<\; \tfrac{1}{2}Z^2 + d\,(1 - V + \ln V).
$$

On acceptance, return $G=d\,V$.

**Consumption accounting:** each *iteration* consumes 3 uniforms (2 for $Z$ + 1 for $U$); iterations are i.i.d. until acceptance. The `rng_trace_log` records the **total** u01 drawn under $\ell_1$ for this merchant; the event envelope’s counters must advance by $\lceil\texttt{draws}/2\rceil$ Philox blocks.

### B.3 Shape $\alpha\in(0,1)$ (Johnk/M–T reduction)

For $\alpha\in(0,1)$, draw $G'\sim\mathrm{Gamma}(\alpha+1,1)$ using **B.2** with parameter $\alpha+1$, then an additional $U\sim(0,1)$, and set

$$
G \;=\; G'\,U^{1/\alpha} \;=\; G'\,\exp\!\big((1/\alpha)\,\ln U\big).
$$

This uses **one extra** u01 beyond those consumed by $G'$. (Note $U\in(0,1)\Rightarrow \ln U<0$; evaluate with binary64 `log/exp`.)

### B.4 Guards (fail closed)

* Abort if any $\alpha_i\le 0$ (schema/contracts guarantee positivity but we guard anyway).
* If a pathologically tiny $\alpha_i$ would underflow $G_i$ to 0 in binary64 across many attempts, the serial normaliser below would see $S=0$ — **abort** (`gamma_underflow_zero_sum`). (Empirically improbable with sensible hyperparameters.)

## C) Serial normalisation to Dirichlet (deterministic)

Accumulating in **country rank order**:

$$
S \;=\; \sum_{i=1}^m G_i \quad(\text{serial left fold}),\qquad
w_i \;=\; G_i/S,\quad i=1,\dots,m.
$$

Enforce $\big|1-\sum_i w_i\big|\le 10^{-6}$ using the **same serial** reducer; otherwise **abort**. (This tolerance matches the event schema.)

## D) Emit the **single** Dirichlet event (arrays aligned with $C$)

Write **one** JSONL record to:

```
logs/rng/events/dirichlet_gamma_vector/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

with the shared RNG **envelope** (showing the jump and the post-consumption counter) and payload arrays:

* `country_isos = [c_1,…,c_m]` (must match the **country_set** order),
* `alpha       = [α_1,…,α_m]`,
* `gamma_raw   = [G_1,…,G_m]`,
* `weights     = [w_1,…,w_m]`,

which **must** be equal-length and satisfy $\sum_i w_i = 1 \pm 10^{-6}$. The `rng_trace_log` row for $\ell_1$ must report the **exact** u01 count consumed; the envelope counters must satisfy `after = advance(before, ceil(draws/2))`.

### What this section guarantees

* $w\sim\mathrm{Dirichlet}(\alpha)$ with arrays aligned to the authoritative country order; arithmetic is binary64 with deterministic serial reductions.
* All RNG is attributable to a **single** labelled event per merchant; replay is proven by the envelope counters and trace, not by duplicating strides in payloads.

### Minimal Reference Algorithm
```css
INPUT:  C=[c1..cm], alpha=[a1..am], env, C0               # ordered country_set; all αi>0
OUTPUT: w=[w1..wm], G=[G1..Gm], C_next, event?            # if m==1: no event

1  assert m=len(C)=len(alpha)≥1
2  if m==1: return ([1.0], [], C0, None)

3  Cb := jump(C0, J("dirichlet_gamma_vector"))             # pre-draw counter jump
4  draws := 0; G := []

5  for i=1..m:
6      if αi ≥ 1: Gi := MT_gamma(αi)                       # Marsaglia–Tsang; uses u01
7      else      : Gi := MT_gamma(αi+1) * U^(1/αi)         # extra U~(0,1)
8      G.append(Gi); draws += u_consumed_this_i

9  S := serial_sum(G)                                      # rank order; binary64
10 w := [Gi/S for Gi in G]; assert abs(1 - sum_serial(w)) ≤ 1e-6

11 Ca := advance(Cb, ceil(draws/2))
12 emit_event("dirichlet_gamma_vector", before=Cb, after=Ca,
             payload={country_isos:C, alpha:alpha, gamma_raw:G, weights:w})
13 return (w, G, Ca, last_event)
```

---



# S7.4.2 — Integerisation by largest-remainder (full detail)

## Objects and typing

* $N\in\mathbb{Z}_{\ge1}$ (exact integer).
* $m=|C|\ge1$. Countries $C=(c_1,\dots,c_m)$ are **ISO-2 uppercase ASCII** and **already ordered** (home first, then the S6 Gumbel order). No duplicates.
* Weights $w=(w_1,\dots,w_m)\in[0,1]^m$ with $\sum_i w_i=1\pm10^{-6}$ (serial sum, rank order).
* All arithmetic is IEEE-754 **binary64**; **serial** operations; **FMA off** (per S7.3).

---

## Step-by-step math (exact semantics)

### 1) Real allocations (binary64 discipline)

Compute

$$
a_i \;:=\; \mathrm{R}_{64}[N\cdot w_i], \qquad i=1,\dots,m.
$$

$\mathrm{R}_{64}[\cdot]$ means “round to binary64”. Using the *same* evaluation order (scalar multiply per component) makes $a_i$ bit-replayable.

### 2) Integer floors

$$
f_i \;:=\; \big\lfloor a_i \big\rfloor \in \mathbb{Z}_{\ge0}.
$$

Binary64 $\to$ integer conversion uses standard floor; because $a_i\ge0$, no sign ambiguity.

### 3) Raw residuals

$$
r_i^{\text{raw}} := a_i - f_i \;\in\; [0,1).
$$

By definition of floor.

### 4) **Quantise** residuals **before** sorting

We fix the 8-decimal quantiser

$$
Q_8(x) := \mathrm{R}_{64}\!\Big(\frac{\mathrm{R}_{64}(x\cdot 10^8)}{10^8}\Big),
$$

and set

$$
r_i := Q_8(r_i^{\text{raw}}) \in [0,1).
$$

This collapses last-bit noise across platforms; max deviation $|r_i-r_i^{\text{raw}}|\le 5\cdot10^{-9}+O(2^{-53})$.

### 5) Deficit (how many top-ups you need)

$$
d \;:=\; N - \sum_{i=1}^{m} f_i\ \in\ \{0,1,\dots,m-1\}.
$$

**Why $d < m$:** write $a_i=f_i+r_i^{\text{raw}}$. Then

$$
\sum_i a_i = N\sum_i w_i \approx N,\quad
d = \sum_i (a_i-f_i) = \sum_i r_i^{\text{raw}} \in [0,m),
$$

so $d$ is an integer in $[0,m-1]$. (Use the exact integer $N$ and integer $\sum f_i$; do **not** recompute $N\sum w_i$ to avoid tolerance issues.)

### 6) Stable, total ordering key

Build a **total** order by the pair

$$
\kappa_i \;:=\; \big(r_i,\ \mathrm{ISO}(c_i)\big),
$$

and sort **descending** by $r_i$; ties broken by **ascending ASCII** of the ISO-2 code. Implementation trick: map `ISO` to a 16-bit integer $k_i = 256\cdot \mathrm{ord}(s_1) + \mathrm{ord}(s_2)$ (both `A`–`Z`), then sort by $(-r_i,\ k_i)$. This guarantees:

* deterministic tie-breaks (no locale/collation surprises),
* $O(m\log m)$ complexity with tiny constants.

### 7) Top-ups and final integers

Let $T$ be the indices of the first $d$ countries in that order. Then

$$
n_i \;=\;
\begin{cases}
f_i+1, & i\in T,\\
f_i,   & i\notin T,
\end{cases}
\qquad\Rightarrow\qquad
\sum_i n_i = \sum_i f_i + d = N,\ \ n_i\in\mathbb{Z}_{\ge0}.
$$

### 8) Error bounds (per-component accuracy)

Since $a_i=f_i+r_i^{\text{raw}}\in[f_i,f_i+1)$ and $n_i\in\{f_i,f_i+1\}$,

$$
|n_i - a_i| \le 1 \quad \text{for all } i.
$$

We **log** $|n_i-a_i|$ for diagnostics and **abort** if any exceeds 1 (should be impossible with this construction).

---

## Edge cases & guards

* **$m=1$ (domestic-only):** $a_1=N,\ f_1=N,\ d=0,\ n_1=N,\ r_1=0.0$. Still emit one residual-rank event with `residual=0.0`, `residual_rank=1`.
* **Residual ties across many countries:** Quantisation to 8 dp intentionally produces ties when differences are $<5\cdot10^{-9}$. The ISO secondary key resolves them deterministically.
* **Near-integer $a_i$:** If $a_i$ is within machine epsilon of an integer, floor still yields the intended integer; the quantised residual becomes `0.00000000` and the item will only be topped up if required by deficit and its ISO comes early among all zero residuals.
* **Sanity assertions:**
  (i) $d\in[0,m-1]$, (ii) $\sum_i n_i=N$, (iii) all `ISO` are 2 ASCII uppercase letters, (iv) no duplicate `ISO` in $C$.

---

## RNG logging for residual rankings

* **Label:** `"residual_rank"`.
* **Jump discipline:** before **each** residual-rank event, add the stride $J(\ell)$ to the low counter with carry (per S0.3.3) and log a `stream_jump` row; these events consume **zero** uniforms, so `after == before`.
* **Payload per country:** `{ merchant_id, country_iso=c_i, residual=r_i (8 dp), residual_rank=t }` where $t$ is the 1-based position of $i$ in the sorted order.
* **Trace:** a companion `rng_trace_log` row with `draws=0` (useful to assert the “jump with no consumption” pattern).

---

## Worked micro-example (to see the gears)

Let $N=7$, $C=(\text{US},\text{GB},\text{DE})$, $w=(0.52,0.28,0.20)$.

1. $a = Nw = (3.64,\ 1.96,\ 1.40)$ (binary64).
2. $f=(3,1,1)$, $r^{\text{raw}}=(0.64,0.96,0.40)$.
3. Quantise: $r=(0.64000000,\ 0.96000000,\ 0.40000000)$.
4. $d = 7 - (3+1+1) = 2$.
5. Sort by $r\downarrow$, ISO$\uparrow$: ranks → GB (0.96), US (0.64), DE (0.40).
6. $T=\{\text{GB},\text{US}\}$.
7. $n=(4,2,1)$. Check: $\sum n_i=7$; errors $|n-a|=(0.36,0.04,0.40)\le 1$.

We emit 3 residual-rank events with `(GB,0.96000000,1)`, `(US,0.64000000,2)`, `(DE,0.40000000,3)`; each has `draws=0`, `after==before`.

---

## Minimal reference algorithm (compact but explicit)

```css
INPUT: N≥1; C=[c1..cm] ISO-2 uppercase; w=[w1..wm] with sum≈1 (serial); env,counter
OUTPUT: n=[n1..nm]; residual_rank events (m rows; draws=0)

1  a := [ R64(N*wi) for wi in w ]                 # componentwise multiply, binary64
2  f := [ floor(ai)      for ai in a ]
3  r_raw := [ ai - fi    for (ai,fi) in zip(a,f) ]
4  r := [ R64(R64(x*1e8)/1e8) for x in r_raw ]    # Q8 quantisation
5  d := N - sum(f)                                # integer deficit, must satisfy 0 ≤ d < m
6  key(i) := ( -r[i], 256*ord(C[i][0]) + ord(C[i][1]) )  # sort by r↓ then ISO↑
7  order := argsort_by( key(i) for i=1..m )
8  T := set(first d indices of order)
9  n := [ fi + (i∈T ? 1 : 0) for i=1..m ]
10 assert sum(n)==N and max_i abs(n[i]-a[i]) ≤ 1
11 for t=1..m:                                    # emit m residual_rank events
12     i := order[t]
13     jump("residual_rank");                      # stream_jump; no uniforms consumed
14     emit_event(label="residual_rank", draws=0,
15                payload={merchant_id, country_iso=C[i], residual=r[i], residual_rank=t})
16 return n
```

That’s the full engine: precise rounding, quantisation, deterministic ordering, airtight mass conservation, and zero-draw RNG logging for residual order.

---



# S7.5 — Invariants & tie-break determinism (deep dive)

## I-1 Mass conservation (must hold)

**Statement.** With $a_i = Nw_i$, $f_i=\lfloor a_i\rfloor$, $d=N-\sum_i f_i\in\{0,\dots,m-1\}$, and

$$
n_i=\begin{cases}f_i+1,& i\in T\\ f_i,& i\notin T\end{cases}
$$

for any index set $T\subset\{1,\dots,m\}$ with $|T|=d$, we have $\sum_i n_i=N$.

**Reason.** $\sum_i n_i=\sum_i f_i + |T|=\sum_i f_i + d = N$. This is algebraic—independent of floating point.

**Validator predicate.** `sum(n) == N` (exact integer equality). Fail closed if false.

---

## I-2 Non-negativity (must hold)

**Statement.** $n_i\in\mathbb{Z}_{\ge0}$.

**Reason.** $a_i\ge0\Rightarrow f_i\ge0\Rightarrow n_i\in\{f_i,f_i+1\}\ge0$.

**Validator predicate.** `min(n) ≥ 0` and `all(is_integer(n_i))`.

---

## I-3 Stable ordering key (must hold)

**Residual definition.**
Raw residual $r_i^{\mathrm{raw}} = a_i - f_i \in [0,1)$; **quantised** residual

$$
r_i = Q_8(r_i^{\mathrm{raw}}) = \mathrm{round}(r_i^{\mathrm{raw}}, \text{8 dp in binary64}).
$$

**Ordering key.**
$\kappa_i = (r_i,\ \mathrm{ISO}(c_i))$ with **primary** order $r_i$ **descending**, **secondary** tie-break on `ISO` **ascending ASCII**. This imposes a **total order** over indices $1..m$ even if many residuals quantise equal.

**Why this is deterministic.**

* Quantising to exactly 8 dp eliminates last-bit platform drift in $r_i$.
* ASCII comparison is locale-free and reproducible; recommend materialising `ISO` to a 16-bit integer $k_i = 256\,\text{ord}(s_1)+\text{ord}(s_2)$ for an explicit numeric tie-break.
* The sort is **purely data-dependent**; no RNG and no iteration-order dependence.

**Validator predicates.**

* Recompute $r_i$ with the same $Q_8$.
* Check the produced order equals `argsort_by((-r_i, ISO_ASC))`.

---

## I-4 RNG lineage & event counts (must hold)

**Streams and counts.**

* Exactly **one** `dirichlet_gamma_vector` event **iff** $|C|>1$.
* Exactly **$|C|$** `residual_rank` events **always** (even when $|C|=1$, where residual $=0.0$, rank $=1$).

**Envelope/counter rules.**

* Each event carries the shared RNG envelope (`seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label`, `rng_counter_before/after`).
* For `dirichlet_gamma_vector`: `draws =` total u01 consumed by the Gamma sampler; envelope must satisfy `after = advance(before, ceil(draws/2))`.
* For each `residual_rank`: **zero** consumption (`draws=0`), thus `after == before` (jump-only).

**Paths & schemas.**
Paths and schema refs are pinned (dataset dictionary). Event presence/shape is verified against those refs; **no drift is permitted across runs** with identical lineage keys.

**Validator predicates.**

* Count events per merchant: `1{m>1}` gamma + `m` residuals.
* JSON-schema validation for every row.
* Counter conservation against the trace log.

---

## I-5 Per-component error bound (should hold; guard)

**Statement.** $|n_i - a_i|\le 1\ \ \forall i$.

**Reason.** $a_i\in[f_i,f_i+1)$ and $n_i\in\{f_i,f_i+1\}$.

**Validator predicate.** Compute $|n_i-a_i|$ in binary64 and assert `≤ 1`. Abort if any `> 1` (indicates implementation bug).

---

## I-6 Cross-run determinism (given fixed lineage)

**Statement.** For fixed $(N,C,\alpha)$ and run lineage $(\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$:

* If $|C|>1$, the tuple $(G,w)$ and the `dirichlet_gamma_vector` envelope counters are **bit-replayable** (counter-based Philox + fixed jump + serial arithmetic).
* The integer vector $n$, the quantised residuals $(r_i)$, and the residual ranking are **bit-replayable** (binary64 + $Q_8$ + ASCII tie-break).
* Event **counts** and **paths** are identical across replays.

**Validator predicate.** Re-run the sampler/rounder in audit mode and byte-compare payloads and counters.

---

## Edge cases to pin down

* **$|C|=1$.** Force $w=(1)$, $n=(N)$, emit **one** `residual_rank` with residual `0.0`, rank `1`, `draws=0`.
* **All residuals quantise to 0.00000000.** Then $T$ comprises the first $d$ countries in **ISO ascending** order.
* **Duplicated ISO in `C`.** Illegal (contradicts `country_set` uniqueness). Treat as structural failure.
* **Tolerance mismatch.** If $|\sum w_i - 1|>10^{-6}$ after serial normalisation, abort **before** integerisation (this is enforced at 7.4.1).

---

## Tiny validator (numbered, minimal)

```text
INPUT: N, C=[c1..cm], w=[w1..wm], n=[n1..nm], residual_events E, gamma_event G?
OUTPUT: pass/fail

1  assert m == len(C) == len(w) == len(n) and N ≥ 1
2  # I-1 + I-2
3  assert sum(n) == N and min(n) ≥ 0 and all_integer(n)
4  # recompute residuals and order (I-3)
5  a := [ R64(N*wi) ]
6  f := [ floor(ai) ]
7  r := [ R64(R64((ai-fi)*1e8)/1e8) ]          # Q8
8  order := argsort_by( (-r[i], ISO_ASC(C[i])) )
9  d := N - sum(f); T := set(first d indices of order)
10 assert n[i] == f[i] + (i∈T ? 1 : 0) for all i
11 assert max_i abs(n[i]-a[i]) ≤ 1            # I-5
12 # I-4 counts + envelopes
13 if m>1: assert exactly one gamma_event for merchant
14 assert |E| == m and each residual_event has draws=0 and after==before
15 # schema + path checks delegated to JSON-schema + dictionary
```

That’s the whole determinism story for S7: conserved mass, non-negativity, platform-proof ranking via $Q_8$+ASCII, and airtight RNG lineage with exact event counts.

---



# S7.6 — Outputs (persisted artefacts & logs)

## 1) `ranking_residual_cache_1A` (parameter-scoped, seed-partitioned)

**What it stores.** One row per $(\texttt{merchant_id},\ \texttt{country_iso})$ with the **quantised** residual (8 dp), its **`residual_rank`** (1..m), and optional auxiliaries sufficient to reconstruct $n_i$ (e.g., $N$, $w_i$, $f_i$). Primary key is `(merchant_id, country_iso)`; partition keys are `seed` and `parameter_hash`. The schema constrains `residual` to $[0,1)$ (float64), and `residual_rank` to positive int32.

**Authoritative path & ref.**

```
data/layer1/1A/ranking_residual_cache/seed={seed}/parameter_hash={parameter_hash}/
  schema_ref: schemas.1A.yaml#/alloc/ranking_residual_cache
  produced_by: 1A.integerise_allocations
```

This dataset is **parameter-scoped** (uses `{parameter_hash}`) and not fingerprint-scoped; it’s intended to stabilise lineage/tie-breaks across replays with the same parameter bundle.

**Why it exists.** It makes the largest-remainder tie-breaks and residual ordering *material*, so later states and validators don’t have to re-derive floating-point minutiae to explain $n_i$. (The authority policy maps this dataset explicitly.)

---

## 2) RNG events (JSONL)

### a) `dirichlet_gamma_vector` (one per merchant **iff** $|C|>1$)

* **Path & schema:**

  ```
  logs/rng/events/dirichlet_gamma_vector/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
  schema_ref: schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector
  produced_by: 1A.dirichlet_allocator
  ```

  Payload arrays `(country_isos, alpha, gamma_raw, weights)` must be equal-length and satisfy $\sum w = 1 \pm 10^{-6}$. Envelope carries seed, parameter_hash, manifest_fingerprint, substream label, and Philox counters; a companion trace row records the u01 **draw count**.

### b) `residual_rank` (**always** $|C|$ events, including $|C|=1$)

* **Path & schema:**

  ```
  logs/rng/events/residual_rank/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
  schema_ref: schemas.layer1.yaml#/rng/events/residual_rank
  produced_by: 1A.integerisation
  ```

  Payload per country: `(merchant_id, country_iso, residual, residual_rank)`, where `residual` is the **8-dp** quantised fraction and `residual_rank` is the 1-based position after sorting by `(residual desc, ISO asc)`. These events consume **zero** uniforms (`draws=0`), so `rng_counter_after == rng_counter_before` (jump-only).

**Event-count invariant.** Per merchant: `1{ |C|>1 }` dirichlet event + `|C|` residual-rank events. Paths/schemas are pinned in the data dictionary and validated post-run.

---

## 3) No changes to `country_set` in S7

S7 **never mutates** `country_set`. That table remains the **only** authority for cross-country order (`rank`: 0=home; 1..K are S6’s Gumbel order). Any consumer (including 1B) that needs inter-country order must **join** to `country_set.rank`. `outlet_catalogue` intentionally does **not** encode cross-country order—it’s keyed/ordered within **country** only (`site_order`).

---

## Quick persistence recipe (minimal)

```text
INPUT:
  merchant_id, C=[c1..cm], residuals r[i] (8 dp), residual_rank[i],  # from S7.4.2
  (optional N, w[i], f[i]), seed, parameter_hash, manifest_fingerprint

# write cache rows (parameter-scoped; seed-partitioned)
for i=1..m:
  write row -> ranking_residual_cache:
    { manifest_fingerprint, merchant_id, country_iso=ci,
      residual=r[i], residual_rank=residual_rank[i] }
    partition_keys={seed, parameter_hash}

# emit RNG events already produced in S7.4.1 and S7.4.2:
#  - at most one dirichlet_gamma_vector (m>1)
#  - exactly m residual_rank (draws=0), each with full envelope
```

The partitioning and schema refs above come straight from the dictionary and schema set; S0’s policy separates **parameter-scoped** caches (like `ranking_residual_cache_1A`) from **egress** (fingerprint-scoped).

---

## Sanity checks the validator will assert

* **Cache schema:** residual $\in [0,1)$ (exclusive max), rank $\ge1$; PK uniqueness on `(merchant_id,country_iso)` within each `{seed,parameter_hash}`.
* **Event presence:** `dirichlet_gamma_vector` present iff $|C|>1$; exactly $|C|$ `residual_rank` rows; JSON-schema conformance.
* **Lineage:** envelope fields present and counters consistent with the trace; correct partition keys (`seed, parameter_hash, run_id`) on event paths.

That’s the full contract for S7’s outputs: cache rows that make rounding decisions auditable and event logs that make all randomness replayable—without ever smuggling cross-country order into egress.

---

# 7.7 - Complexity

Let $m=|C|=K{+}1$.

* **Gamma/Dirichlet sampling.** We draw $m$ independent $G_i\sim\mathrm{Gamma}(\alpha_i,1)$ via Marsaglia–Tsang, then normalise serially. Each $G_i$ costs **$O(1)$ expected** u01 draws and constant arithmetic; the normaliser is a left-fold and $m$ divides.
  **Time:** $T_{\gamma}(m)=\Theta(m)$. **Space:** $S_{\gamma}(m)=\Theta(m)$ for arrays $(G,w)$.
* **Integerisation by largest-remainder.** Floors and residuals are linear; ranking requires one comparison sort.
  **Time:** $T_{\text{int}}(m)=\Theta(m\log m)$ using key $(r_i,\mathrm{ISO})$. **Space:** $\Theta(m)$. Residual quantisation and the $d$-top-up pass are linear.
* **Events & cache.** Per merchant, **at most** 1 `dirichlet_gamma_vector` $+$ **exactly** $m$ `residual_rank` rows, and $m$ cache rows in `ranking_residual_cache_1A`. **I/O:** $\Theta(m)$ records.

**Overall per merchant:** $\Theta(m\log m)$ time, $\Theta(m)$ space. Typical $m$ is small (tens), so sort dominates but remains cheap; all ops are deterministic serial arithmetic (binary64, FMA-off).

---

# 7.8 - Notes on correctness & governance

* **Schema-level guards (abort on violation).**
  `dirichlet_gamma_vector` enforces equal-length arrays and $\sum_i w_i=1\pm 10^{-6}$ (serial sum). `ranking_residual_cache` constrains `residual∈[0,1)` and `residual_rank≥1`. `residual_rank` events must appear **once per country** (total $m$). These are pinned by the dictionary’s `schema_ref` pointers.
* **Determinism proof artifacts.**
  The **numeric policy** (binary64, serial reductions, FMA-disabled) and the **tie-break contract** (8-dp residual quantisation + ISO ASCII) are part of the controlled documentation and are **digested into the manifest** via the run’s artefact set; changing them requires a doc update + semver bump and produces a new manifest fingerprint.
* **Naming alignment & responsibilities.**
  `residual_rank` = **inter-country** largest-remainder order used to turn $Nw$ into $n$. `site_order` = **within-country** outlet sequencing used later by `outlet_catalogue`. **Inter-country order is not encoded** in `outlet_catalogue`; any consumer that needs it **must join** to `country_set.rank` (the sole authority). These meanings are fixed by the schema authority policy and the dictionary.
* **Lineage & partitioning governance.**
  Parameter-scoped caches (e.g., `ranking_residual_cache_1A`) partition by `{seed, parameter_hash}`; RNG events by `{seed, parameter_hash, run_id}`. `country_set` remains authoritative for order and is likewise `{seed, parameter_hash}` partitioned. This separation is deliberate and validated.

---

### Summary (one-liner)

S7 takes $N$ and the ordered $C$, samples $w\sim\mathrm{Dirichlet}(\alpha)$, then applies a **deterministic** largest-remainder integerisation (8-dp residuals + ISO tie-break) to produce $\{n_i\}$ with $\sum n_i=N$, while persisting **residual rankings** and full RNG lineage for replay and audit.
