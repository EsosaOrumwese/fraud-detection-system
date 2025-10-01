# S7.1 — α-vector resolution (governed ladder)

## Scope & purpose

S7 needs a Dirichlet concentration vector $\alpha\in\mathbb{R}^{M}*{>0}$ whose **length** and **ordering** match the merchant’s ordered country set $C=(c_0,\dots,c*{M-1})$ (home at rank 0, then foreigns in the Gumbel order from S6). `country_set` is the **only** authority for this membership and order; S7 **MUST NOT** reorder or mutate it.

When $M=1$ (domestic-only path), later steps force $w=(1)$ and $n=(N)$; $\alpha$ is **not** used, but one `residual_rank` event is still emitted to keep logging invariants. (Declared here for completeness; sampling/normalisation live in S7.2–S7.3.)

---

## Definitions (normative)

* $C=(c_0,\dots,c_{M-1})$: ordered countries from `country_set` with `rank(c_i)=i`.
* Lookup **key cardinality** $M:=|C|\in\mathbb{Z}_{\ge 1}$.
* $\alpha=(\alpha_0,\dots,\alpha_{M-1})\in\mathbb{R}^M_{>0}$: Dirichlet concentrations aligned **index-for-index** with $C$ (i.e., $\alpha_i$ is for country $c_i$).
* **Position-based α semantics:** index 0 corresponds to **home**; indices 1..$K_m^*$ correspond to foreign positions **in `country_set.rank` order**. Foreign positions are **exchangeable** unless the policy provides distinct values per position.

---

## Preconditions (MUST)

1. `country_set` exists for the merchant, is partition-consistent for this run (`seed`, `parameter_hash`), and is valid: home at rank 0; all ISO-2 codes valid; no duplicates.
2. $M=|C|\ge 1$.
3. The α policy artefact **`dirichlet_alpha_policy.yaml`** is present in the parameter-scoped inputs (versioned by `parameter_hash`).

---

## Resolution algorithm (normative)

Let `home`, `MCC`, `channel` be the merchant attributes; let $M=|C|$.

**Ladder (exact → fallback):**

1. **Exact:** `(home, MCC, channel, M)`
2. **Back-off A:** `(home, channel, M)`
3. **Back-off B:** `(home, M)`
4. **Fallback (symmetric):** $\alpha_i=\tau/M$ for all $i$, with governed $\tau > 0$ (default **$\tau=2.0$** in `dirichlet_alpha_policy.yaml`).

**Post-lookup checks (pure, deterministic):**

* **Dimension check:** require `len(alpha) == M`; else raise `ERR_S7_ALPHA_DIM_MISMATCH(m_expected=M, m_found=len(alpha))`.
* **Positivity floor:** require $\min_i \alpha_i \ge 10^{-6}$; else raise `ERR_S7_ALPHA_NONPOSITIVE(i, value)`.
* **Ordering alignment:** $\alpha$ **must** already be aligned to `country_set.rank` (0..$M{-}1$). If a keyed source returns a mapping, re-order into rank order deterministically.

**Determinism & provenance:**

* Resolution uses only deterministic inputs (`home`, `MCC`, `channel`, `M`) and the parameter-scoped policy artefact, so it is a **pure function** of (`home`,`MCC`,`channel`,`M`,`parameter_hash`).
* Record the ladder step chosen as `alpha_key_used ∈ {exact, backoffA, backoffB, symmetric}` for inclusion in the S7.2 `dirichlet_gamma_vector` event payload (optional, recommended).

---

## Outputs

* **α vector:** `alpha[0..M-1]` aligned to `country_set.rank`.
* **alpha_key_used (string, optional):** one of `exact | backoffA | backoffB | symmetric` for downstream event payloads and audits.

---

## Numeric environment (must match S7 policy)

* IEEE-754 **binary64** throughout; **no FMA** in ordering-sensitive computations. (S7.1 itself is a pure lookup; numeric policy matters in S7.2–S7.3.)

---

## Error handling (abort semantics)

* `ERR_S7_ALPHA_KEY_MISSING(level, key)`: informative when a ladder level lookup misses (resolution continues to lower levels).
* `ERR_S7_ALPHA_DIM_MISMATCH(m_expected, m_found)`: returned vector length $\neq M$.
* `ERR_S7_ALPHA_NONPOSITIVE(index, value)`: any $\alpha_i < 10^{-6}$.
* `ERR_S7_COUNTRYSET_INVALID`: `country_set` failed preconditions (duplicates, invalid ISO, missing home at rank 0, or wrong order).

---

## Invariants (MUST hold)

1. **Authority & order:** $\alpha$ aligns one-to-one with `country_set` (rank order); S7 **MUST NOT** mutate `country_set`.
2. **Determinism:** Given (`home`,`MCC`,`channel`, $M$, `parameter_hash`) the resolution is identical across replays.
3. **Safety floor:** $\alpha_i\ge 10^{-6}\ \forall i$.
4. **Fallback soundness:** If only symmetric fallback is available, $\alpha=(\tfrac{\tau}{M},\dots,\tfrac{\tau}{M})$ with default $\tau=2.0$.

---

## Reference pseudocode (deterministic)

```pseudo
function resolve_alpha(home, mcc, channel, C: list[country_iso], param_store) -> (array[float64], string):
    # Preconditions
    assert is_country_set_valid(C)          # rank order, no dups, home at index 0
    M := len(C); assert M >= 1

    # Ladder lookups: pure reads against parameter-scoped store
    key_exact :=   (home, mcc, channel, M)
    key_backA :=   (home, channel, M)
    key_backB :=   (home, M)

    alpha := param_store.alpha_get(key_exact)
    alpha_key_used := "exact"
    if alpha is None:
        alpha := param_store.alpha_get(key_backA); alpha_key_used := "backoffA"
    if alpha is None:
        alpha := param_store.alpha_get(key_backB); alpha_key_used := "backoffB"
    if alpha is None:
        tau := param_store.alpha_tau_default_or(2.0)
        alpha := [tau / M] * M; alpha_key_used := "symmetric"

    # Dimension & ordering
    if len(alpha) != M:
        raise ERR_S7_ALPHA_DIM_MISMATCH(M, len(alpha))

    # If source returns a mapping, re-order deterministically to match rank(C)
    # (Most sources should already return length-M arrays in rank order.)
    alpha := align_to_rank_order(alpha, C)  # no-op if already aligned

    # Positivity floor
    for i in 0..M-1:
        if alpha[i] < 1e-6:
            raise ERR_S7_ALPHA_NONPOSITIVE(i, alpha[i])

    return (alpha, alpha_key_used)
```

---

## Conformance tests (minimal suite)

1. **Exact hit:** Entries exist at all ladder levels; **exact** key wins. Verify `len(alpha)=M`, floor respected, `alpha_key_used="exact"`.
2. **Back-off A:** Remove exact; A wins. Deterministic across replays; `alpha_key_used="backoffA"`.
3. **Back-off B:** Remove A; B wins; ordering aligned; `alpha_key_used="backoffB"`.
4. **Fallback:** Remove all; verify $\alpha_i=\tau/M$ with default $\tau=2.0$; `alpha_key_used="symmetric"`.
5. **Dimension mismatch:** Provide length $M{-}1$ for exact key; expect `ERR_S7_ALPHA_DIM_MISMATCH`.
6. **Non-positive component:** Provide α with any $\alpha_j < 10^{-6}$ (e.g., $10^{-7}$); expect `ERR_S7_ALPHA_NONPOSITIVE`.
7. **Country-set integrity:** Corrupt `country_set` (dup ISO or non-home at rank 0); expect `ERR_S7_COUNTRYSET_INVALID` **before** any α lookup.
8. **Parameter-scoped determinism:** Changing `parameter_hash` (by altering `dirichlet_alpha_policy.yaml`) changes resolved α; replays with the same `parameter_hash` reproduce α bit-identically.

---

### Notes & cross-refs

* S7.1 only **resolves** α. Gamma sampling, normalisation to $w$, and sum-to-one tolerances are defined in S7.2–S7.3 and inherit the same numeric policy.
* `country_set` remains authoritative for inter-country order; egress `outlet_catalogue` does **not** encode this order (consumers join `country_set.rank`).

---

# S7.2 — RNG envelope & Dirichlet draw (Marsaglia–Tsang)

## Scope & purpose

Given the ordered country set $C=(c_0,\dots,c_{M-1})$ from `country_set` and the $\alpha$ vector from **S7.1**, sample $G_i\sim\mathrm{Gamma}(\alpha_i,1)$ independently. For $M>1$, compute preliminary weights $w_i=G_i/\sum_j G_j$ **using the same deterministic reducer as S7.3** (see below), and emit **one** RNG event `dirichlet_gamma_vector` whose arrays are aligned to $C$ and whose envelope (seed, substream label, counters, draws) is replayable.
For $M=1$, **skip** sampling and **do not** emit this event (S7.5 still emits one `residual_rank` with `draws=0`).

> **Authority note:** The **normative** normalisation used for allocation lives in **S7.3**. S7.2 must compute `weights` for the event payload **using S7.3’s reducer**, and validators will re-derive weights from `gamma_raw` in S7.3 and compare.

---

## Inputs (MUST)

* `country_set` (authoritative membership + order; ranks 0..$M{-}1$).
* $\alpha=(\alpha_0,\dots,\alpha_{M-1})$ from **S7.1**; length $M$; all $\alpha_i>0$.
* Run lineage `(seed, parameter_hash, manifest_fingerprint)`.

---

## RNG discipline (normative)

* **Keyed substream.** All uniforms for this sub-state use the label **`"dirichlet_gamma_vector"`** under the merchant’s stream. Base 128-bit counter is derived deterministically from (`fingerprint`, `seed`, label, `merchant_id`). The $i$-th uniform uses counter `(base_hi, base_lo + i)` with 128-bit carry. **Order-invariant.**
* **Open-interval uniforms.** From 64-bit lanes: $u=(x+1)/(2^{64}+1)\in(0,1)$ (never 0 or 1).
* **Normals.** Box–Muller, **no spare caching**; exactly **2 uniforms per** $Z$.
* **Envelope accounting.** Event stores `(before_hi, before_lo, after_hi, after_lo, draws)` with 128-bit equality: `after = before + draws`. A per-module `rng_trace_log` row records the **same** `draws`.

---

## Algorithm (normative)

### A) Early exit for $M=1$

If $|C|=1$: set `weights = [1.0]` and **do not** emit `dirichlet_gamma_vector`. (S7.5 will still emit one `residual_rank` event with `draws=0`.)

### B) Sample Gamma components (Marsaglia–Tsang, MT1998)

For each $i\in{0,\dots,M-1}$ independently:

* **If $\alpha_i\ge 1$** (MT “shape ≥1” branch). Let $d=\alpha_i-\tfrac13$, $c=(9d)^{-1/2}$. Repeat:

  1. draw $Z\sim\mathcal N(0,1)$ (consumes **2 uniforms**); set $V=(1+cZ)^3$; if $V\le 0$, retry;
  2. draw $U\sim U(0,1)$ (consumes **1 uniform**);
  3. accept iff $\ln U < \tfrac12 Z^2 + d - dV + d\ln V$; then set $G_i=dV$.
     **Budget:** **3 uniforms per attempt**.

* **If $0<\alpha_i<1$** (shape <1 reduction). Draw $G'\sim\Gamma(\alpha_i+1,1)$ by the branch above, then draw $U\sim U(0,1)$ (consumes **+1 uniform**) and set
  $G_i = G'\,U^{1/\alpha_i}.$

### C) Compute event weights with the **S7.3 reducer**

Let $S=\sum_i G_i$ computed by **`sum_comp`** (Neumaier compensated **serial** sum) in **`country_set.rank` order**; set $w_i = G_i/S$.

* **Internal target:** $\big|1-\sum_i w_i\big|\le 10^{-12}$ using **`sum_comp`**.
* **Event/schema bound:** $\big|1-\sum_i w_i\big|\le 10^{-6}$ (the event is rejected otherwise).

> This mirrors S7.3. The **authoritative** weights for allocation are recomputed from `gamma_raw` in S7.3 using the same reducer; validators assert the S7.2 `weights` agree (see Errors).

### D) Emit **one** `dirichlet_gamma_vector` event (iff $M>1$)

Write one JSONL record under:

```
logs/rng/events/dirichlet_gamma_vector/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
schema_ref: schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector
partitioning: ["seed","parameter_hash","run_id"]
produced_by: "1A.dirichlet_allocator"
```

**Envelope (required):** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, `module`, `label="dirichlet_gamma_vector"`, `counter_before_hi/lo`, `counter_after_hi/lo`, `draws`, optional `ts`.

**Payload (required, equal length, `country_set` order):**

* `country_isos` : `array[str, ISO-2]`
* `alpha`        : `array[number > 0]`
* `gamma_raw`    : `array[number > 0]`
* `weights`      : `array[number in (0,1)]`, computed via **S7.3** reducer
* `alpha_key_used` (string, **optional**) : `exact | backoffA | backoffB | symmetric` (propagated from S7.1)

*(Optional, once per merchant per label):* emit a `stream_jump` record.

---

## Draw-count formula (for validators)

Let $A_i$ be the number of **attempts** taken by the MT kernel for component $i$ under the “$\alpha\ge1$” branch (for $\alpha_i<1$, $A_i$ corresponds to the $\alpha_i+1$ kernel). Then:

$$
\texttt{draws} \;=\; 3\sum_{i=0}^{M-1}\!A_i \;+\; \sum_{i=0}^{M-1}\mathbf{1}[\alpha_i<1].
$$

Validators recompute $A_i$ from `gamma_raw` (the accept/reject path is inferable) and assert both the draw formula and the 128-bit counter delta.

---

## Numeric policy (must match S7)

* IEEE-754 **binary64** everywhere; **no FMA** in ordering-sensitive operations.
* Deterministic **serial** reductions in `country_set.rank` order implemented as **`sum_comp`** (Neumaier).

---

## Error handling (abort conditions)

* **`ERR_S7_2_PAYLOAD_LEN_MISMATCH`** — payload arrays not all length $M$.
* **`ERR_S7_2_SUM_TOL_EVENT`** — $\big|1-\sum w\big|>10^{-6}$ using `sum_comp`.
* **`ERR_S7_2_UNDERFLOW_ZERO_SUM`** — $\sum G = 0$.
* **`ERR_S7_2_COUNTER_DELTA`** — envelope `after − before ≠ draws` (u128).
* **`ERR_S7_2_WEIGHTS_MISMATCH_INTERNAL`** — event `weights` differ from S7.3-recomputed weights from `gamma_raw` by more than $10^{-12}$ (componentwise or sum).

All are structural aborts; S9 fails and 1B must not proceed.

---

## Invariants (MUST hold)

1. **Event cardinality:** per merchant, emit **exactly one** `dirichlet_gamma_vector` iff $|C|>1$; **none** if $|C|=1$.
2. **Envelope correctness:** `after = before + draws` (128-bit); `draws` equals the formula above.
3. **Alignment:** all payload arrays align index-for-index with `country_set` order (home rank 0; then S6 Gumbel order).
4. **Partitions:** events are partitioned by `{seed, parameter_hash, run_id}` exactly as above.
5. **Determinism:** For fixed (`seed`,`parameter_hash`,`merchant_id`) the event is byte-stable.

---

## Reference pseudocode

```pseudo
function s7_2_dirichlet_draw(country_set C, alpha[0..M-1], lineage, alpha_key_used?) -> (w[0..M-1], event?):
    assert len(C) == len(alpha) == M >= 1
    if M == 1:
        return ([1.0], None)  # no event; S7.5 emits residual_rank later

    # Substream: all uniforms under "dirichlet_gamma_vector"
    env_before := keyed_counter_before(lineage, label="dirichlet_gamma_vector")

    G := array<float64>(M)
    draws := 0
    for i in 0..M-1:
        a := alpha[i]
        if a >= 1:
            repeat:
                Z := box_muller()       # 2 uniforms
                draws += 2
                d := a - 1.0/3.0
                c := (9.0*d)^(-0.5)
                V := (1.0 + c*Z)^3
                if V <= 0.0: continue
                U := u01()              # +1 uniform
                draws += 1
                if log(U) < 0.5*Z*Z + d - d*V + d*log(V):
                    G[i] = d*V; break
        else:
            Gp, k := gamma_mt_kernel(a+1.0)  # returns value and uniforms used (multiple of 3)
            draws += k
            U := u01()                        # +1 uniform
            draws += 1
            G[i] = Gp * U^(1.0/a)

    S := sum_comp(G)                           # Neumaier, rank order
    if S == 0.0: abort("ERR_S7_2_UNDERFLOW_ZERO_SUM")

    w := [ Gi / S for Gi in G ]
    if abs(1.0 - sum_comp(w)) > 1e-6:
        abort("ERR_S7_2_SUM_TOL_EVENT")

    env_after := u128_add(env_before, draws)
    event := {
      envelope: {
        seed, parameter_hash, manifest_fingerprint, run_id,
        module: "1A.dirichlet_allocator",
        label: "dirichlet_gamma_vector",
        counter_before_hi: env_before.hi, counter_before_lo: env_before.lo,
        counter_after_hi:  env_after.hi,  counter_after_lo:  env_after.lo,
        draws: draws
      },
      payload: {
        country_isos: [c.iso for c in C],
        alpha: alpha, gamma_raw: G, weights: w,
        alpha_key_used: alpha_key_used  # optional
      }
    }
    write_event_jsonl(event, DIRICHLET_EVENT_PATH)
    write_trace(label="dirichlet_gamma_vector", draws=draws)

    return (w, event)
```

---

## Conformance tests

1. **Cardinality:** $M=1$ ⇒ **no** event; $M=2$ ⇒ **exactly one** event.
2. **Alignment:** perturb external order and verify validator fails (payload must match `country_set` order).
3. **Draw accounting:** instrument MT attempts, verify `draws = 3∑A_i + ∑1[α_i<1]` and the envelope delta.
4. **Sum-to-one:** force $\big|1-\sum w\big| > 10^{-6}$ → expect `ERR_S7_2_SUM_TOL_EVENT`.
5. **Recompute check:** recompute weights from `gamma_raw` with **S7.3**; expect max diff ≤ `1e-12`; else `ERR_S7_2_WEIGHTS_MISMATCH_INTERNAL`.
6. **Determinism:** rerun with identical lineage → byte-identical event; change `parameter_hash` → event differs only due to α universe.

---

# S7.3 — Deterministic normalisation & sum-to-one check

## Scope & purpose

Given the ordered country set $C=(c_0,\dots,c_{M-1})$ and the independent gamma components $G_i\sim\Gamma(\alpha_i,1)$ sampled in **S7.2**, compute weights
$w_i \;=\; \frac{G_i}{\sum_j G_j}$
**deterministically** and enforce two tolerances:

* **Internal target (algorithmic):** $\big|\sum_i w_i - 1\big|\le 10^{-12}$ (binary64) → otherwise **abort**.
* **Event/schema guard (payload):** $\big|\sum_i w_i - 1\big|\le 10^{-6}$ (validators accept at this looser bound).

Arrays **must** remain index-aligned to `country_set.rank` (home rank 0; then S6’s Gumbel order).

---

## Inputs (MUST)

* $G=(G_0,\dots,G_{M-1})\in\mathbb{R}^M_{>0}$ from S7.2; $M=|C|\ge 1$. (For $M=1$ S7.2 already short-circuits; S7.3 is vacuous.)
* `country_set` (sole authority for membership and order).

---

## Numeric environment (normative)

* IEEE-754 **binary64** everywhere; **FMA disabled** in ordering-sensitive paths.
* Reductions are **serial, deterministic** in **`country_set.rank` order**.

---

## Method (normative): Neumaier compensated **serial** sum

Let `sum_comp(·)` be the **Neumaier** compensated reducer in fixed order:

```text
function sum_comp(x[0..M-1]):
  s = 0.0; c = 0.0
  for i in 0..M-1 in country_set.rank ascending:
    t = s + x[i]
    if abs(s) >= abs(x[i]): c += (s - t) + x[i]
    else:                   c += (x[i] - t) + s
    s = t
  return s + c
```

**Prohibitions:** no pairwise/parallel/Kahan, no BLAS/GPU — this normalisation is a **single-thread loop** (part of determinism).

---

## Algorithm (normative)

1. **Early exit (M=1).**
   If $M=1$: return `w=[1.0]` (already set in S7.2); skip the rest.

2. **Compute the sum.**
   $S \leftarrow \texttt{sum_comp}(G_0,\dots,G_{M-1})$.
   Since each $G_i>0$, $S>0$; if $S=0$ (pathological underflow), **abort** `ERR_S7_3_UNDERFLOW_ZERO_SUM`.

3. **Normalise.**
   For each $i$: set $w_i \leftarrow G_i / S$ (binary64 division). Store `w` in the same order as $C\`.

4. **Sum-to-one enforcement (two-stage).**
   (a) **Internal**: $S' \leftarrow \texttt{sum_comp}(w)$. Abort `ERR_S7_3_SUM_MISMATCH_INTERNAL` if $|S' - 1| > 10^{-12}$.
   (b) **Event/schema**: the already-emitted S7.2 `dirichlet_gamma_vector` payload **must** also satisfy $|\sum w - 1|\le 10^{-6}`under`sum_comp\`. Validators enforce this at read time.

5. **Reconciliation with S7.2 payload (deterministic).**
   Recompute `w` from S7.2’s `gamma_raw` with `sum_comp` and assert **componentwise** $|w_i^{(S7.3)} - w_i^{(event)}|\le 10^{-12}$. Otherwise **abort** `ERR_S7_3_WEIGHTS_MISMATCH_INTERNAL`.
   *(This guarantees the event’s `weights` were produced with the same reducer.)*

6. **Accounting.**
   Normalisation consumes **no** random draws; S7.2’s event `draws` equals $3\sum A_i + \sum\mathbf{1} [\alpha_i<1]$ and is unchanged here.

---

## Additions (boxed, normative)

**Internal vs. schema tolerance:**

* Internal algorithmic target: $\pm 10^{-12}$ (authoritative for allocation & integerisation).
* Event/schema acceptance: $\pm 10^{-6}$ (cross-system validation bound).

**Reducer prohibition:**

* **Pairwise/parallel/GPU/BLAS reducers are forbidden**; use the serial Neumaier loop in rank order. Violations are flagged in `numeric_determinism.json`.

**Authority & order:**

* `country_set` is the sole authority; arrays remain index-aligned to rank (0..$M{-}1$). S7.3 **MUST NOT** mutate `country_set`.

---

## Properties & obligations

* **Determinism:** Given $G$ and `country_set.rank`, $w$ is a pure function of binary64 arithmetic with a fixed reducer and order. Any deviation (parallel reduction, different order, FMA) breaks replay.
* **No clamp/re-scale:** If the internal tolerance fails, **fail closed**; do not re-scale to force a pass.
* **Alignment:** Arrays stay index-aligned to `country_set` order.

---

## Reference pseudocode (deterministic)

```pseudo
function s7_3_normalise(G[0..M-1], C) -> w[0..M-1]:
    assert M == len(C) == len(G) and M >= 1
    if M == 1: return [1.0]

    S = sum_comp(G)
    if S == 0.0:
        abort("ERR_S7_3_UNDERFLOW_ZERO_SUM")

    w = array<float64>(M)
    for i in 0..M-1:
        w[i] = G[i] / S

    S1 = sum_comp(w)
    if abs(S1 - 1.0) > 1e-12:
        abort("ERR_S7_3_SUM_MISMATCH_INTERNAL")

    # Reconcile with S7.2 payload (if present in context)
    w_event = read_event_weights_for_this_merchant_if_available()
    if w_event is not None:
        for i in 0..M-1:
            if abs(w[i] - w_event[i]) > 1e-12:
                abort("ERR_S7_3_WEIGHTS_MISMATCH_INTERNAL")

    return w
```

---

## Invariants (MUST hold)

1. If $M=1$: `w=[1.0]`. If $M > 1$: $w_i \in (0,1)$ and $\sum_i w_i = 1 \pm 10^{-12}$ internally.
2. S7.2 payload satisfies $\sum w = 1 \pm 10^{-6}$ under `sum_comp`.
3. Arrays align index-for-index with `country_set` rank order.
4. Normalisation uses **Neumaier** in fixed order; **no** BLAS/parallel/GPU/FMA for this step.

---

## Conformance tests

1. **Tolerance split:** choose $G$ to yield $|\sum w-1|\approx 10^{-10}$ → pass internal & event checks; perturb to exceed $10^{-12}$ but remain $<10^{-6}$ → **abort internally**; validator would have accepted the event bound.
2. **Order dependence:** compute sums with a different order or pairwise tree — result **must differ** on crafted inputs; reference reducer must pass.
3. **Underflow guard:** force tiny $G_i$; if `sum_comp(G)==0.0`, expect `ERR_S7_3_UNDERFLOW_ZERO_SUM`.
4. **Event reconciliation:** for $M > 1$, ensure **exactly one** `dirichlet_gamma_vector` exists; recompute `w` from `gamma_raw` and assert componentwise diff ≤ `1e-12`.
5. **Determinism:** rerun with identical lineage: byte-equal `w`; RNG counters unchanged (normalisation consumes none).

---

**Hand-off:** `w` now satisfies the numeric contract and is ready for **S7.4** (forming $a_i=N,w_i$, flooring, **decimal 1e8** residual quantisation in **integer space**, and preparing for largest-remainder integerisation).

---

# S7.4 — Real allocations & residual quantisation

## Scope & purpose

Take the ordered country set $C=(c_0,\dots,c_{M-1})$, total outlets $N\in\mathbb{Z}*{\ge1}$, and weights $w=(w_0,\dots,w*{M-1})$ from **S7.3** (already sum-to-one within the internal tolerance) and produce:

* real allocations $a_i=N,w_i$ (binary64),
* integer floors $f_i=\lfloor a_i\rfloor$,
* **quantised residuals** at **exactly 8 decimal places** for deterministic tie-breaks,
* the integer **deficit** $d:=N-\sum_i f_i$ to be distributed in **S7.5**.

All arrays are index-aligned to `country_set.rank` (home rank 0; then S6 Gumbel order).

---

## Inputs (MUST)

* `country_set` (sole authority for membership + order; `rank(c_i)=i`; ISO-2; no duplicates).
* **Provenance of `N`**:

  * **multi-site path:** `N = raw_nb_outlet_draw` from **S2**,
  * **single-site path:** `N := 1` from **S1** (S2–S6 are bypassed).
* $w=(w_0,\dots,w_{M-1})$ from **S7.3**; $M=|C|\ge1$; $\sum_i w_i = 1 \pm 10^{-12}$ (internal target).

---

## Numeric environment (normative)

* IEEE-754 **binary64** for all real operations; **FMA disabled** wherever ordering/rounding affects branching or ranking (i.e., this whole sub-state).
* Deterministic **serial** loops in `country_set.rank` order. No pairwise/parallel reductions here (sums already handled in S7.3).

---

## Definitions (normative)

* **Binary64 cast of `N`:** require $N < 2^{53}$ so $\mathrm{R}_{64}(N)$ is exact.
* **Real allocations:** $a_i:=\mathrm{R}*{64}(N)\times \mathrm{R}*{64}(w_i)$ (single multiply; **no FMA**).
* **Integer floors:** $f_i:=\lfloor a_i\rfloor \in \mathbb{Z}_{\ge0}$ (int32).
* **Raw residuals:** $u_i:= a_i - f_i \in  [0,1)$.
* **8-dp quantiser $Q_8$ (normative, **integer-space**):** for $u\in [0,1)$

  $$
  q \;=\; \operatorname{roundToEven}\!\big(\,\lfloor 10^8\cdot u \rceil\,\big)\ \in\ \{0,\dots,10^8\},\qquad
  r \;=\; \frac{\min(q,\,10^8{-}1)}{10^8}.
  $$

  * `roundToEven` = nearest integer with ties-to-even.
  * The `min` enforces **$r<1$** even in half-ULP edge cases.
  * **Ranking surrogate:** the **integer** `q` is the **only** normative key for ranking in S7.5; `r` is a decimal view for storage/display and round-trips exactly to `q` via `q = round(1e8 * r)`.

> Informal equivalence: $r = Q_8(u) = \mathrm{R}_{64}(\mathrm{int64}(10^8 u)/10^8)$ — but **ranking uses `q`**, not `r`.

---

## Algorithm (normative)

1. **Early case (M=1).**
   $a_0=N$, $f_0=N$, $u_0=0$, $q_0=0$, $r_0=0.00000000$, $d=0$.
   (S7.5 will still emit one `residual_rank` event with `draws=0`.)

2. **Compute real allocations.**
   For each $i=0,\dots,M-1$ (rank order): $a_i \leftarrow \mathrm{R}_{64}(N)\times w_i$. Store $a_i$ (binary64).

3. **Floors & raw residuals.**
   $f_i \leftarrow \lfloor a_i\rfloor$ (int32), $u_i \leftarrow a_i - f_i$.

4. **Quantise residuals (8 dp, integer-space).**
   $q_i \leftarrow \operatorname{roundToEven}(10^8 \cdot u_i)$ (int64);
   if $q_i = 10^8$, set $q_i \leftarrow 10^8-1$;
   $r_i \leftarrow q_i / 10^8$ (binary64). Persist **`r_i`**; **`q_i` is recomputed** as `int64(round(1e8 * r_i))` wherever needed.

5. **Compute deficit for S7.5.**
   $d \leftarrow N - \sum_i f_i$ (int32). **No clamping.**

   **Bound (ties to S7.3):** S7.3 ensures $\sum w = 1 \pm 10^{-12}$, hence $\sum a_i = N \pm \epsilon$ with $\epsilon \ll 1$. Since each $u_i!\in! [0,1)$, we have $0 \le d < M$ (and $d\in\mathbb{Z}$). If S7.3’s internal check failed, it already aborted.

**Outputs of S7.4 (consumed by S7.5):** arrays $a,f,r$ and scalar $d$, all aligned to `country_set.rank`. (The ranking key in S7.5 is `q_i = round(1e8*r_i)`.)

---

## Properties & error bounds (MUST hold)

* **Ranges/types:** $a_i\ge0$ (binary64), $f_i\in\mathbb{Z}_{\ge0}$ (int32), $r_i\in [0,1)$ (binary64 on **8-dp grid**); `q_i\in\{0,\dots,10^8-1\}`.
* **Quantisation error:** for $u\in [0,1)$,
  $|\,r-u\,| \le 0.5\cdot 10^{-8} + O(\varepsilon_{64}).$
  Distinct $u$ values within $\approx 5\times10^{-9}$ may quantise to the same `r`/`q` — intended; S7.5 breaks ties deterministically with stable secondary keys.
* **Mass-conservation setup:** $d=N-\sum f_i$ with $0\le d < M$. S7.5’s “top-up first $d$ by +1” ensures $\sum n_i=N$ and $|n_i-a_i|\le 1$.

---

## Error handling (abort conditions)

* `ERR_S7_4_NEG_WEIGHT_OR_NAN` — any $w_i\notin [0,1]$ or NaN/Inf (should be impossible if S7.3 passed).
* `ERR_S7_4_ALLOC_NAN_INF` — any $a_i$ is NaN/Inf.
* `ERR_S7_4_FLOOR_RANGE` — some $f_i<0$ or $f_i>\texttt{INT32_MAX}$.
* `ERR_S7_4_DEFICIT_RANGE` — computed $d\notin [0,M-1]$.
* `ERR_S7_4_RESIDUAL_RANGE` — some $r_i\notin [0,1)$ after quantisation (guarded by the `q_i==10^8` clamp).

Structural failures → S9 must refuse `_passed.flag`; 1B must not proceed.

---

## Invariants (MUST hold)

1. Arrays $a,f,r$ are index-aligned with `country_set.rank` (0..$M{-}1$).
2. `r_i` is exactly on the **decimal 8-dp grid**; `q_i = round(1e8 * r_i)` (integer) is the **normative** residual surrogate for ranking.
3. **No RNG** is consumed in S7.4 (no envelope deltas); `residual_rank` events in S7.5 have `draws=0`.

---

## Reference pseudocode (deterministic; binary64; FMA-off)

```pseudo
function s7_4_alloc_and_residuals(N:int32, w[0..M-1]:float64, C:list[ISO2])
  -> (a[0..M-1]:float64, f[0..M-1]:int32, r[0..M-1]:float64, d:int32):

    assert M == len(C) == len(w) and M >= 1
    assert N >= 1 and N < 2^53

    a := array<float64>(M)
    f := array<int32>(M)
    r := array<float64>(M)

    if M == 1:
        a[0] = float64(N); f[0] = N; r[0] = 0.0
        d = 0
        return (a,f,r,d)

    sum_f := 0
    for i in 0..M-1:
        ai := float64(N) * w[i]       # single multiply; NO FMA
        if isNaN(ai) or isInf(ai): abort("ERR_S7_4_ALLOC_NAN_INF")

        fi := floor(ai)
        if fi < 0 or fi > INT32_MAX: abort("ERR_S7_4_FLOOR_RANGE")

        ui := ai - float64(fi)        # [0,1)
        qi := roundToEven(1e8 * ui)   # int64
        if qi == 100000000:           # enforce residual < 1.0
            qi = 99999999
        ri := float64(qi) / 1e8

        a[i] = ai; f[i] = int32(fi); r[i] = ri
        sum_f += f[i]

    d := N - sum_f
    if d < 0 or d >= M: abort("ERR_S7_4_DEFICIT_RANGE")

    return (a,f,r,d)
```

---

## Conformance tests

1. **M=1 path.** `N=17`, `w=[1]` → `a=[17]`, `f=[17]`, `r=[0]`, `d=0`. S7.5 must still emit one `residual_rank` with `draws=0`.
2. **Near-integer allocation.** Choose `N,w` s.t. some $a_j=3.0000000000001$ → `f_j=3`, `u_j≈1e-13`, `q_j=0`, `r_j=0.00000000`.
3. **Half-ULP near 1.0.** Construct $u≈0.999999995$ → raw round hits `1e8`; clamp yields `q=99999999`, `r=0.99999999 ∈ [0,1)`.
4. **Quantisation tie.** Two `u` values within `<5e-9` quantise to identical `q`; S7.5 must break with stable secondary keys.
5. **Deficit bound.** For random $w,N$ with $M∈ [2,20]`, verify `0 ≤ d < M`and`d = N - ∑f_i\`.
6. **Binary64 exactness of N.** With `N ≥ 2^53`, assert precondition failure; with `N = 2^53−1`, pass and produce identical results across platforms.

---

## Hand-off to S7.5

S7.5 **ranks by** the stable key
**`(q_i ↓, country_set.rank ↑, ISO ↑)`**,
takes the first `d` indices to receive `+1`, emits **one** `residual_rank` event **per country** (`draws=0`), and obtains final integers $n_i$ with $\sum n_i=N$ and $|n_i-a_i|\le 1$.

> Note: `q_i` is derived from the persisted `r_i` as `q_i := int64(round(1e8 * r_i))`, so no extra persistence is needed.

---

# S7.5 — Largest-remainder integerisation & residual-rank events

## Scope & purpose

Given the arrays from **S7.4**—real allocations $a$, integer floors $f$, quantised residuals $r\in [0,1)$ at **exactly 8 dp**, and the deficit $d\in{0,\dots,M{-}1}$—deterministically select the $d$ indices to receive a **+1** top-up via a **stable, schema-aligned order key**, emit **one `residual_rank` RNG event per country** (with `draws=0`), and persist `residual` + `residual_rank` to **`ranking_residual_cache_1A`** (parameter-scoped). `country_set` remains the **only** authority for membership & order; S7 **MUST NOT** mutate it.

---

## Inputs (MUST)

* Ordered **country set** $C=(c_0,\dots,c_{M-1})$, `country_set.rank(c_i)=i` (0 = home; foreigns in S6 Gumbel order). No duplicates; ISO-2 uppercase.
* From **S7.4** (index-aligned with $C$):
  $a\in\mathbb{R}*{64}^M$, $f\in\mathbb{Z}*{\ge0}^M$, $r\in [0,1)^M$ (**8-dp**), and $d\in{0,\dots,M{-}1}$ with $d = \big(\sum_i a_i\big) - \big(\sum_i f_i\big)$ rounded implicitly by floors (see S7.4).
* Lineage tuple for event partitioning: `seed`, `parameter_hash`, `run_id` (plus `manifest_fingerprint` in the envelope).

---

## Numeric environment & determinism (normative)

* IEEE-754 **binary64**; **no FMA** anywhere ordering/rounding affects branching.
* All loops and sorts are **deterministic**. Sorting is **stable** over the explicit tuple key (below). No locale-dependent collation.
* No RNG is consumed in this sub-state; all `residual_rank` events **must** log `draws=0` with `after == before`.

---

## Ordering key (normative)

Use the **integer** residual surrogate
$q_i \;:=\; \operatorname{roundToEven}\!\big(10^8\cdot r_i\big)\ \in \{0,\dots,10^8-1\},$
derived from the persisted 8-dp `r_i`. (If a reader recomputes: `q_i = int64(round(1e8 * r_i))`.)

Let `ISO(c_i)` be the 2-letter code and `rank(c_i)` the integer rank from `country_set`. Define the total order key:

$$
\mathbf{k}(i)\;=\;\big(-q_i,\ \texttt{rank}(c_i),\ \text{ISO}(c_i)\big),
$$

i.e., **descending** integer residual (`q_i`), then **ascending** `country_set.rank`, then **ascending** ISO. The second key **must** be `country_set.rank` (preserves S6’s Gumbel order as the prior); ISO is only the tertiary tie-break.

> Why `q` not `r`? Using the integer surrogate avoids any binary64 re-rounding drift; `r` remains the stored value, but **ranking is defined on `q`**.

---

## Algorithm (normative)

1. **Build permutation.**
   Compute a **stable sort** of indices $0..M{-}1$ by key $\mathbf{k}(i)$ to obtain $\pi=(\pi_1,\dots,\pi_M)$ where $\pi_1$ is “largest” (by `q`, then `rank`, then ISO).

2. **Top-up set.**
   Let $T={\pi_1,\dots,\pi_d}$ (empty if $d=0$).

3. **Final integers.**
   For each $i$,

   $$
   n_i \;=\;
   \begin{cases}
   f_i+1, & i\in T,\ [2pt]
   f_i,   & i\notin T.
   \end{cases}
   $$

   Then $\sum_i n_i=\sum_i f_i + d$ (hence equals $N$) and $n_i\in\mathbb{Z}_{\ge0}$ with $|n_i-a_i|\le 1$ for all $i$.

4. **Emit `residual_rank` events (exactly $M$).**
   For each position $t\in{1,\dots,M}$ with index $i=\pi_t$, emit one JSONL event:

   ```
   logs/rng/events/residual_rank/
     seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
   schema_ref: schemas.layer1.yaml#/rng/events/residual_rank
   produced_by: 1A.integerise_allocations
   ```

   **Envelope (must fields):**
   `{ seed, parameter_hash, manifest_fingerprint, run_id, module="1A.integerise_allocations", label="residual_rank", counter_before_hi, counter_before_lo, counter_after_hi, counter_after_lo, draws=0, ts }`.

   **Payload (per country):**
   `{ merchant_id, country_iso=ISO(c_i), residual=r_i (8 dp), residual_rank=t }`.

   **Counters:** `after == before` (128-bit equality) since `draws=0`. A companion `rng_trace_log` row records the zero-draw emission.
   *(Optional once per label):* a `stream_jump` can precede the first emission; it does not consume draws.

5. **Persist residuals (hand-off to S7.6).**
   Write one row per country to **`ranking_residual_cache_1A`**:

   ```
   data/layer1/1A/ranking_residual_cache_1A/
     seed={seed}/parameter_hash={parameter_hash}/
   schema_ref: schemas.1A.yaml#/alloc/ranking_residual_cache
   produced_by: 1A.integerise_allocations
   PK: (merchant_id, country_iso)
   Columns: { manifest_fingerprint, merchant_id, country_iso, residual (8 dp), residual_rank (int32≥1), ... }
   ```

   This dataset is **parameter-scoped** (partitioned by `{seed, parameter_hash}`) and materialises the tie-break outcome so no downstream needs to re-derive floating-point minutiae.

---

## Error handling (abort semantics)

Abort S7 (structural failure) if any of:

* `ERR_S7_5_DEFICIT_RANGE` — $d\notin [0,M-1]$ (contradicts S7.4 guarantees).
* `ERR_S7_5_SORT_STABILITY` — permutation is not of $0..M{-}1$ **or** sort is non-stable when keys are equal.
* `ERR_S7_5_MASS_MISMATCH` — $\sum_i n_i \neq \sum_i f_i + d$.
* `ERR_S7_5_BOUNDS` — some $n_i<0$ or $|n_i-a_i|>1$.
* `E-S7.5-RNG-COUNTERS` — any `residual_rank` event has `draws≠0` or `after≠before`.
* `E-S7.5-CACHE-SCHEMA` — cache row violates schema/range (`residual∉[0,1)`, `residual_rank<1`) or PK duplicates within `{seed, parameter_hash}`.

Any such failure **blocks** S9’s `_passed.flag`; 1B’s preflight must refuse the read for that fingerprint.

---

## Invariants (MUST hold)

1. **Stable order key:** sort by **`(q ↓, rank ↑, ISO ↑)`** where `q = round(1e8·r)` from the persisted 8-dp residual.
2. **Event counts:** per merchant, **exactly** $|C|$ `residual_rank` events; additionally, **one** `dirichlet_gamma_vector` iff $|C|>1\`. Paths and schema refs are fixed.
3. **No RNG consumption:** each residual-rank event has `draws=0` and `after==before`.
4. **Cache contract:** `ranking_residual_cache_1A` partitioned by `{seed, parameter_hash}`; PK `(merchant_id, country_iso)`; `residual∈[0,1)`, `residual_rank∈\mathbb{Z}_{\ge1}`.
5. **Country-order authority:** `country_set` is not mutated; any consumer needing inter-country order must join `country_set.rank`. Egress never encodes inter-country order.

---

## Reference pseudocode (deterministic; stable sort)

```pseudo
function s7_5_integerise(C, a[0..M-1], f[0..M-1], r[0..M-1], d:int32, lineage):
    assert M == len(C) == len(f) == len(r) and 0 <= d and d < M

    # Build integer residual surrogates (from persisted 8-dp r)
    q := array<int64>(M)
    for i in 0..M-1:
        qi := roundToEven(1e8 * r[i])   # in {0..1e8-1}
        # r is already < 1.0 by schema; clamp should be unnecessary, but safe:
        if qi == 100000000: qi = 99999999
        q[i] = qi

    # 1) Stable order by key (-q, rank, ISO)
    idx := [0,1,...,M-1]
    stable_sort(idx, key = (-q[i], country_set.rank(C[i]), ISO(C[i])))

    # 2) Top-up set
    T := set(idx[0:d])  # empty if d == 0

    # 3) Final integers
    n := array<int32>(M)
    for i in 0..M-1:
        n[i] = f[i] + (i in T ? 1 : 0)

    # Mass/bounds checks (no external N needed)
    assert sum(n) == sum(f) + d
    for i in 0..M-1:
        assert n[i] >= 0
        assert abs(float64(n[i]) - a[i]) <= 1.0

    # 4) Emit exactly M residual_rank events (draws=0; counters unchanged)
    for t in 1..M:
        i := idx[t-1]
        env_before := keyed_counter_before(lineage, label="residual_rank")
        env_after  := env_before  # draws = 0
        write_event_jsonl(
          path="logs/rng/events/residual_rank/seed=.../parameter_hash=.../run_id=...",
          envelope={
            seed, parameter_hash, manifest_fingerprint, run_id,
            module:"1A.integerise_allocations", label:"residual_rank",
            counter_before_hi: env_before.hi, counter_before_lo: env_before.lo,
            counter_after_hi:  env_after.hi,  counter_after_lo:  env_after.lo,
            draws: 0, ts: now()
          },
          payload={
            merchant_id, country_iso: ISO(C[i]),
            residual: r[i], residual_rank: t
          })

    # 5) Persist cache rows (S7.6 handles I/O details)
    # (merchant_id, country_iso, residual, residual_rank, manifest_fingerprint)

    return n, idx
```

---

## Conformance tests

1. **Tie cascade (q ties).** Construct multiple countries with identical **q** (same 8-dp `r`) → verify sort uses `rank` before ISO; then ISO breaks remaining ties; byte-stable across platforms.
2. **Mass & bounds.** Randomised $w$, $N$, $M\le 20$ → assert `sum(n) == sum(f)+d` and `|n_i-a_i| ≤ 1`; fail on any `n_i < 0`.
3. **Event cardinality & counters.** For $M=1$: expect **one** `residual_rank` event with `residual=0.0`, `residual_rank=1`, `draws=0`. For $M>1$: expect **exactly M** events, each `draws=0` and `after==before`; `rng_trace_log` mirrors zero draws.
4. **Cache schema & PK.** Write $M$ rows into `ranking_residual_cache_1A` under `{seed, parameter_hash}`; enforce PK `(merchant_id,country_iso)` and value ranges (`residual∈[0,1)`, `residual_rank≥1`).
5. **Country-set authority.** If `country_set` order is externally altered, validation must fail since events/cache must align to the original rank order.
6. **Worked micro-example.** Example $N=7$, $C=(\text{US},\text{GB},\text{DE})$, $w=(0.52,0.28,0.20)$. From S7.4 get (say) `q=[20000000, 60000000, 0]` → order `GB, US, DE`, `d=1` → `n=(4,2,1)`; events ranks `(GB,1)`, `(US,2)`, `(DE,3)`.

---

## Notes & hand-off

* **S7.6 persists** the `ranking_residual_cache_1A` rows produced here.
* **S8 consumes** only the final integers $n_i$ and `country_set` (for grouping/order joins). Inter-country order remains solely in `country_set.rank` and is **not** encoded in egress.

---

# S7.6 — Persist `ranking_residual_cache_1A` (parameter-scoped)

## Scope & purpose

Take the outputs of **S7.5** — for a fixed merchant with ordered `country_set` $C=(c_0,\dots,c_{M-1})$, the **quantised residuals** $r_i\in [0,1)$ at **8 dp** and their **residual ranks** $t_i\in{1,\dots,M}$ (where $t_i=1$ is largest by the S7.5 key) — and **materialise** one row per `(merchant_id, country_iso)` into **`ranking_residual_cache_1A`**.

This cache makes S7’s largest-remainder ordering reproducible without re-deriving floating-point minutiae. It is **parameter-scoped** (partitioned by `{seed, parameter_hash}`; **not** fingerprint-scoped).

---

## Authoritative contract (path, schema, keys)

**Dataset id & path (dictionary):**

```
id: "ranking_residual_cache_1A"
path: "data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/"
partitioning: ["seed","parameter_hash"]
schema_ref: "schemas.1A.yaml#/alloc/ranking_residual_cache"
produced_by: "1A.integerise_allocations"
```

This dataset’s versioning key is `{parameter_hash}` and it is **seed-partitioned**.

**Schema (JSON-Schema excerpt):**

* **Primary key:** `["merchant_id","country_iso"]`
* **Partition keys:** `["seed","parameter_hash"]`
* **Columns (required):**

  * `manifest_fingerprint: string` (hex64 lowercase)
  * `merchant_id: id64`
  * `country_iso: ISO-3166-1 alpha-2` (FK to canonical ISO dataset)
  * `residual: float64` with `minimum: 0.0`, `exclusiveMaximum: true` at `1.0`  *(i.e., `[0,1)`)*
  * `residual_rank: int32` *(1 = largest)*

**Authority policy (semantics):**

* `residual_rank` is the **integerisation order** (largest-remainder rank), **distinct** from `site_order`.
* Inter-country order is **not** encoded in egress; consumers must use `country_set.rank`.

---

## Inputs (MUST)

For each merchant:

* `country_set` rows (sole authority for membership + order; ISO unique; home rank 0).
* Arrays from **S7.5** aligned to `country_set.rank`:

  * $r=(r_0,\dots,r_{M-1})\in [0,1)^M$ *(each exactly **8-dp** per S7.4)*,
  * $t=(t_0,\dots,t_{M-1})\in{1,\dots,M}^M$ *(a permutation)*.
* Lineage tuple: `seed`, `parameter_hash`, `manifest_fingerprint`.

---

## Normative requirements (what MUST be written)

For every index $i$ (rank $i$ in `country_set`), write **exactly one** row:

```
{ manifest_fingerprint, merchant_id, country_iso = ISO(c_i),
  residual = r_i, residual_rank = t_i }
```

to:

```
data/layer1/1A/ranking_residual_cache_1A/
  seed={seed}/parameter_hash={parameter_hash}/part-*.parquet
```

Subject to schema (PK, FK, ranges).

**Write mode (normative):** **overwrite** the partition `{seed, parameter_hash, merchant_id}` (or whole `{seed, parameter_hash}` if partitioning granularity requires) to guarantee idempotence across re-runs.

---

## Numeric & determinism policy

* `residual` values **come from S7.4’s quantiser** `Q8`; do **not** recompute or re-round here.
* Store as `float64` per schema; they represent exact **decimal 8-dp gridpoints** (`q/1e8`).
* No RNG is consumed in S7.6. File write order is not constrained by schema; a stable write order (e.g., `country_set.rank` asc) is **recommended** for byte-stable diffs but **not mandatory**.

---

## Algorithm (normative)

```pseudo
function s7_6_persist_residual_cache(merchant_id, C:list[ISO2],
                                     r[0..M-1], t[0..M-1],
                                     seed, parameter_hash, manifest_fingerprint):

  # Preconditions
  assert M == len(C) == len(r) == len(t) and M >= 1
  assert is_unique(C) and is_valid_iso2(C)          # guaranteed by country_set
  assert all(0.0 <= r[i] and r[i] < 1.0 for i)      # schema range
  assert sort(t) == [1..M]                          # permutation check

  # Optional gridpoint check (informative; not schema):
  # verify r is exactly an 8-dp gridpoint Q8(u) from S7.4
  for i in 0..M-1:
      qi := roundToEven(1e8 * r[i])                 # integer candidate
      if qi == 100000000: qi = 99999999             # enforce < 1.0
      r_chk := float64(qi) / 1e8
      assert ulp_distance(r[i], r_chk) <= 1

  # Idempotent write: overwrite partition for this merchant
  target_path := "data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/"
  begin_overwrite_partition(target_path, merchant_id)

  for i in 0..M-1:
      write_parquet_row(
        path = target_path,
        row  = { manifest_fingerprint, merchant_id,
                 country_iso = C[i], residual = r[i], residual_rank = t[i] })

  end_overwrite_partition(target_path, merchant_id)

  # Enforce PK uniqueness within the partition
  assert_no_duplicates_pk(partition=(seed,parameter_hash), pk=("merchant_id","country_iso"))
```

Notes:

* The **gridpoint check** catches accidental float recomputation; it is not a schema rule.
* PK uniqueness and FK to ISO are enforced by the validator.

---

## Error handling (abort semantics)

* `E-S7.6-PK-DUP` — duplicate `(merchant_id,country_iso)` within `{seed,parameter_hash}`.
* `E-S7.6-RANGE-RESIDUAL` — `residual ∉ [0,1)` or NaN/Inf.
* `E-S7.6-RANGE-RANK` — `residual_rank < 1` or ranks not a permutation of `1..M`.
* `E-S7.6-FK-ISO` — `country_iso` not present in the canonical ISO dataset (FK violation).
* `E-S7.6-LINEAGE-MISSING` — any of `{seed, parameter_hash, manifest_fingerprint}` missing.

Any such failure **blocks** S9’s `_passed.flag`; 1B must not consume `outlet_catalogue` for that fingerprint.

---

## Invariants (MUST hold)

1. **Cardinality:** per merchant, the cache contains **exactly $M$** rows (one per country in `country_set`).
2. **Key integrity:** PK uniqueness on `(merchant_id, country_iso)` in each `{seed, parameter_hash}` partition.
3. **Ranges/domains:** `0 ≤ residual < 1`; `residual_rank ∈ {1,..,M}`; `country_iso` is valid ISO-2 (FK).
4. **Lineage consistency:** every row carries the run’s `manifest_fingerprint`; partitions are exactly `{seed, parameter_hash}`.
5. **Authority separation:** cache does **not** encode inter-country order; that remains solely in `country_set.rank`.

---

## Worked row example (schema-valid, illustrative)

```json
{
  "manifest_fingerprint": "ab12cd34ef56...7890ab12cd34ef56",
  "merchant_id": 5813372149021,
  "country_iso": "GB",
  "residual": 0.12340000,
  "residual_rank": 2
}
```

Partition:

```
data/layer1/1A/ranking_residual_cache_1A/
  seed=42/parameter_hash=3f9c...8d1a/part-00001.parquet
```

---

## Conformance tests

1. **Schema & PK:** write $M$ rows; validate `#/alloc/ranking_residual_cache` → no PK dupes; residual in `[0,1)`; rank ≥ 1.
2. **Cardinality match:** for random merchants, row count equals `|country_set|`.
3. **Gridpoint sanity:** for each row, `q' = min(roundToEven(1e8*residual), 1e8-1)`; `r' = q'/1e8`; assert `ulp_distance(residual, r') ≤ 1`.
4. **Lineage & partitions:** files live under `seed={seed}/parameter_hash={parameter_hash}`; rows carry the correct `manifest_fingerprint`.
5. **FK to ISO:** sample and join `country_iso` to canonical ISO; 100% match.
6. **End-to-end replay:** recompute S7.4→S7.5 and compare `(residual, residual_rank)` to cache rows — equality within 1 ULP for residual and exact integer equality for rank.
7. **Negative tests:** inject `residual = 1.0` → schema rejection; inject duplicate `(merchant_id,country_iso)` → PK failure.

---

## Relationship to events & to S9

* S7.6 writes the **cache** only. RNG events were already emitted in **S7.2** (`dirichlet_gamma_vector`, iff $M>1$) and **S7.5** (`residual_rank`, exactly $M$). Their paths/partitions/schemas are fixed in the dictionary.
* **S9** validates this cache and, together with `country_set`, re-derives and checks integerisation invariants before issuing `_passed.flag` for the run’s **fingerprint** (the 1A→1B gate).

---

# S7.7 — RNG event set (completeness & counts)

## Scope & purpose

For a merchant with ordered `country_set` $C=(c_0,\dots,c_{M-1})$, ensure the **RNG events** emitted in S7 are:

1. **Present in the right cardinalities** per merchant,
2. **Stored under authoritative paths / partitions / schemas**, and
3. **Reconciled** with the run-scoped RNG trace (counters & draws).

Events in scope:

* **`dirichlet_gamma_vector`** — **exactly one** iff $M>1$ (none if $M=1$). Path partitioned by `{seed, parameter_hash, run_id}`; schema `schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector`; **produced_by:** `1A.dirichlet_allocator`.
* **`residual_rank`** — **exactly $M$** (even when $M=1$). Same partitions; schema `schemas.layer1.yaml#/rng/events/residual_rank`; **produced_by:** `1A.integerise_allocations`.
* **RNG trace** — `rng_trace_log.jsonl` partitioned by `{seed, parameter_hash, run_id}`, schema `#/rng/core/rng_trace_log`, used to reconcile draw counts and counter deltas.

S7 **never mutates** `country_set` (sole authority for membership & order) — restated here because cardinality checks depend on $|C|$.

---

## Authoritative paths & partitions (normative)

* `logs/rng/events/dirichlet_gamma_vector/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (schema `#/rng/events/dirichlet_gamma_vector`).
* `logs/rng/events/residual_rank/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (schema `#/rng/events/residual_rank`).
* `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl` (schema `#/rng/core/rng_trace_log`).

Partitions **must be exactly** `["seed","parameter_hash","run_id"]` for all three datasets.

---

## Inputs (MUST)

For each `merchant_id`:

* `country_set` rows (authoritative order; partitioned by `{seed, parameter_hash}`).
* The event streams under the same `{seed, parameter_hash, run_id}`.
* The RNG trace under the same `{seed, parameter_hash, run_id}`.

Let $M=\lvert C\rvert$.

---

## Event cardinality & envelope rules (normative)

### A) Cardinality equalities (per merchant)

Let

$$
\#\text{dir} \equiv \text{count of } \texttt{dirichlet_gamma_vector}\text{ events for the merchant},\quad
\#\text{res} \equiv \text{count of } \texttt{residual_rank}\text{ events}.
$$

Then

$$
\#\text{dir} = \mathbf{1}[M>1],\qquad \#\text{res} = M.
$$

Violations are **hard errors**.

### B) Envelope invariants (per event)

Required envelope fields for both events:
`{ seed, parameter_hash, manifest_fingerprint, run_id, module, label, counter_before_hi, counter_before_lo, counter_after_hi, counter_after_lo, draws }` (+ optional `ts`) — names/types per schema.

* **Dirichlet:** `label == "dirichlet_gamma_vector"`. Must satisfy
  `(after_hi, after_lo) = (before_hi, before_lo) ⊕₁₂₈ draws`.
* **Residual-rank:** `label == "residual_rank"`. Must satisfy `draws == 0` **and** 128-bit equality `after == before`.

### C) Payload alignment (schema-enforced)

* **Dirichlet:** `country_isos`, `alpha`, `gamma_raw`, `weights` are equal-length and index-aligned to `country_set` rank order; validators re-sum `weights` via **Neumaier** (see below) to $\sum w = 1 \pm 10^{-6}\`.
* **Residual-rank:** payload `{ merchant_id, country_iso, residual, residual_rank }` must contain **exactly one** event per `country_iso ∈ C` and the multiset of `residual_rank` must be `{1,…,M}`.

> **Residual gridpoint check (required here):** `residual` must be on the **8-dp decimal grid**: compute `q' = min(roundToEven(1e8*residual), 1e8-1)` and assert `abs(residual - q'/1e8) ≤ 1 ULP`. (Guards against accidental re-quantisation.)

---

## Reconciliation with RNG trace (normative)

Trace rows are keyed by **(module, label, merchant_id)** within `{seed, parameter_hash, run_id}` and carry a `draws` field (u01 count). Require:

1. **Dirichlet draw equality** (if $M>1$):
   `event.draws == trace.draws == u128_delta(envelope)`.

2. **Residual-rank zero-draws** (always):
   The per-merchant sum of `draws` across the $M$ `residual_rank` events is **0**, every event has `after==before`, and the trace row for `(module="1A.integerise_allocations", label="residual_rank")` reports **0**.

> **Optional extended check** (if enabled): recompute the **attempt-based** draw formula from the Dirichlet payload (`gamma_raw`, `alpha`) and assert `draws = 3∑A_i + ∑1[α_i<1]` (see S7.2). Not required for pass; recommended for deep audits.

---

## Deterministic reducer for validator sums (normative)

When re-summing `weights` (dirichlet payload) or any arrays for checks, validators **must** use the **Neumaier** compensated **serial** reducer in `country_set.rank` order (same as S7.3). Parallel/pairwise/BLAS/GPU reductions are forbidden for validation.

---

## Failure modes (abort semantics)

* `E-S7.7-CNT-DIRICHLET` — $\#\text{dir} \neq \mathbf{1}[M >1]$.
* `E-S7.7-CNT-RESIDUAL` — $\#\text{res} \neq M$ **or** duplicate `country_iso`.
* `E-S7.7-ENV-DELTA` — any event violates its envelope rule (dirichlet delta ≠ draws; residual-rank `draws ≠ 0` or `after ≠ before`).
* `E-S7.7-TRACE-MISMATCH` — event `draws` disagree with `rng_trace_log` for the same `(module,label,merchant_id)`.
* `E-S7.7-PARTITIONS` — event/trace not under `{seed, parameter_hash, run_id}` or schema ref mismatch.
* `E-S7.7-RES-GRID` — a `residual_rank` payload’s `residual` is **not** on the 8-dp grid.

Any failure **blocks** S9 from issuing `_passed.flag` for the run’s fingerprint (1A→1B gate).

---

## Reference checker (deterministic)

```pseudo
function s7_7_check_events(merchant_id, C, seed, parameter_hash, run_id):
    M := len(C)

    # 1) Load per-merchant events/trace under exact partitions
    D := read_events("dirichlet_gamma_vector", seed, parameter_hash, run_id, merchant_id)  # 0 or 1
    R := read_events("residual_rank",          seed, parameter_hash, run_id, merchant_id)  # M
    T := read_trace  (seed, parameter_hash, run_id, merchant_id)                           # by (module,label)

    # 2) Cardinality
    if M > 1: assert len(D) == 1 else: assert len(D) == 0
    assert len(R) == M

    # 3) Envelopes
    if M > 1:
        e := D[0]
        assert e.label == "dirichlet_gamma_vector" and e.module == "1A.dirichlet_allocator"
        assert u128_add(e.before_hi, e.before_lo, e.draws) == (e.after_hi, e.after_lo)
    for e in R:
        assert e.label == "residual_rank" and e.module == "1A.integerise_allocations"
        assert e.draws == 0
        assert (e.before_hi == e.after_hi) and (e.before_lo == e.after_lo)

    # 4) Payload alignment & residual grid
    if M > 1:
        P := D[0].payload
        assert eq_len(P.country_isos, P.alpha, P.gamma_raw, P.weights)
        assert aligns_to_country_set(P.country_isos, C)    # index-by-index
        assert abs(neumaier_sum(P.weights) - 1.0) <= 1e-6  # S7.3 reducer
    iso_set := set(ci for ci in C)
    assert set(e.payload.country_iso for e in R) == iso_set
    ranks := sorted(e.payload.residual_rank for e in R)
    assert ranks == [1..M]
    for e in R:
        r := e.payload.residual
        qp := roundToEven(1e8 * r); if qp == 100000000: qp = 99999999
        assert ulp_distance(r, qp/1e8) <= 1

    # 5) Trace reconciliation (by module+label)
    dir_trace := T.get(module="1A.dirichlet_allocator",     label="dirichlet_gamma_vector")?.draws or 0
    dir_ev    := sum(e.draws for e in D)
    assert dir_ev == dir_trace
    res_trace := T.get(module="1A.integerise_allocations",  label="residual_rank")?.draws or 0
    res_ev    := sum(e.draws for e in R)
    assert res_ev == 0 and res_trace == 0

    return OK
```

---

## Invariants (MUST hold)

1. **Per-merchant counts:** `dirichlet_gamma_vector` = $\mathbf{1} [M>1]$; `residual_rank` = $M$.
2. **Envelope arithmetic:** dirichlet `after = before ⊕₁₂₈ draws`; every residual-rank has `draws=0` and `after==before`.
3. **Payload alignment:** dirichlet arrays align to `country_set`; residual-rank covers each `country_iso ∈ C` once; ranks are `{1..M}`.
4. **Residual grid:** every residual in `residual_rank` lies on the **8-dp** grid (`q/1e8`, `q∈{0..1e8-1}`) within 1 ULP.
5. **Trace reconciliation:** event `draws` equal the trace’s `draws` for the same `(module,label,merchant_id)`; residual-rank totals 0.
6. **Partition/schema fidelity:** paths and schema refs exactly match the dictionary.

---

## Conformance tests

1. **M=1 case.** No dirichlet event; **one** residual-rank event with `draws=0` & `after==before`; trace shows `dirichlet=0`, `residual_rank=0`.
2. **M=3 case.** Exactly one dirichlet; exactly 3 residual-rank; dirichlet arrays length 3; `neumaier_sum(weights)` within `±1e-6`.
3. **Counter mismatch.** Tamper dirichlet `after` so `before ⊕ draws ≠ after` → `E-S7.7-ENV-DELTA`.
4. **Trace mismatch.** Tamper trace draws → `E-S7.7-TRACE-MISMATCH`.
5. **Partition drift.** Move an event outside `{seed, parameter_hash, run_id}` → `E-S7.7-PARTITIONS`.
6. **Residual duplication.** Duplicate a `country_iso` or make ranks not a permutation → `E-S7.7-CNT-RESIDUAL`.
7. **Residual grid fail.** Set a residual to 0.123456789 → `E-S7.7-RES-GRID`.

---

## Notes & hand-off

* S7.7 is **pure validation** of S7’s RNG lineage at the event/log layer; it produces no artefacts. Its success is a prerequisite for S9’s bundle to carry “RNG lineage OK,” which the **1A→1B gate** relies on alongside schema checks.
* Optional **`stream_jump`** events (if present) are governed by their own schema; they **do not consume draws** and are not required for pass.

---

# S7.8 — Internal validations (must-pass before S8)

## Scope & purpose

For each merchant with ordered `country_set` $C=(c_0,\dots,c_{M-1})$, given:

* $N\in\mathbb{Z}_{\ge1}$ (total outlets),
* $w$ from S7.3,
* $a,f,r,d$ from S7.4 (with `r` on the 8-dp grid),
* final integers $n$ and the residual order $\pi$ from S7.5,
* cache rows written by S7.6,
* RNG events from S7.2/S7.5,

S7.8 **must** verify the invariants below deterministically and without RNG. Any failure **aborts S7** (S8 is not invoked).

---

## Inputs (per merchant, MUST)

* `country_set` rows **in rank order** (0 = home); ISO-2 unique; authoritative for inter-country order.
* Scalars/arrays from S7.3–S7.5: `N`, `w`, `a`, `f`, `r` (8-dp), `d`, `n`, and residual order indices `π`.
* `ranking_residual_cache_1A` rows just written by S7.6.
* RNG events for this `{seed, parameter_hash, run_id}`:
  `dirichlet_gamma_vector` (iff $M>1$) and exactly $M$ `residual_rank`.
* **Provenance of `N`:**
  multi-site → `N = raw_nb_outlet_draw` from S2; single-site → `N := 1` from S1.
* **Binary64 exactness:** require `N < 2^53` so `float64(N)` is exact.

---

## Numeric environment (normative)

* IEEE-754 **binary64** everywhere; **FMA disabled** where ordering/rounding affects branching.
* Deterministic **serial** reductions in `country_set.rank` order (same reducer as S7.3).

---

## Deterministic helpers (normative)

**Neumaier compensated serial sum** (rank order):

```
sum_comp(x[0..K-1]):
  s=0.0; c=0.0
  for i=0..K-1:
    t = s + x[i]
    if abs(s) >= abs(x[i]): c += (s - t) + x[i]
    else:                   c += (x[i] - t) + s
    s = t
  return s + c
```

**8-dp residual quantiser `Q8` (integer-space):**

$$
q=\operatorname{roundToEven}(10^8 u)\in\{0,\dots,10^8\},\quad
q\leftarrow \min(q,10^8-1),\quad r = q/10^8.
$$

Use $u_i = a_i - \lfloor a_i\rfloor$.
**Normative ranking surrogate:** `q` (integer); `r` is the stored gridpoint.

---

## Invariants (MUST hold)

**I-1 — Alignment & lengths.**
Arrays `w,a,f,r,n` have equal length $M=|C|\ge 1`; indices align to `country_set.rank\`. ISO codes unique.

**I-2 — Dirichlet weight normalisation & event parity.**

* If $M=1$: assert `w=[1.0]` and **no** dirichlet event.
* If $M>1\`:

  * Recompute `S' = sum_comp(w)` and assert `|S' − 1| ≤ 1e−12` (internal target).
  * From the **dirichlet event payload**, re-sum `weights` with `sum_comp` and assert `|∑weights − 1| ≤ 1e−6`.
  * Recompute `w_event` from `gamma_raw` via S7.3’s reducer and assert `max_i |w_event[i] − weights[i]| ≤ 1e−12`.

**I-3 — Real allocations & residual quantisation are coherent.**
Recompute `a'_i = float64(N) * w[i]`, `f'_i = floor(a'_i)`, `r'_i = Q8(a'_i − f'_i)`; assert:

* `a'_i` equals `a_i` **exactly** in binary64,
* `f'_i == f_i`,
* `r'_i == r_i` (same gridpoint / same `q`).

**I-4 — Deficit range & identity.**
`d' = N − ∑ f_i` satisfies `0 ≤ d' < M` **and** `d' == d`.

**I-5 — Largest-remainder replay (on integer residuals).**
Let `q_i = roundToEven(1e8 * r_i)` (clamp `<1e8` → `1e8−1`).
Stable-sort indices by **`(−q_i, country_set.rank, ISO)`** to get order `π`.
Let `T = {π_1,…,π_d}`. Assert for all `i`:

* `n_i == f_i + 1[i ∈ T]`,
* `|n_i − a_i| ≤ 1`, and
* `∑ n_i == N`.
  *(Secondary key MUST be `country_set.rank`; ISO is tertiary.)*

**I-6 — Cache round-trip.**
Load the $M$ rows for this merchant from `ranking_residual_cache_1A(seed,parameter_hash)` and assert:

* PK uniqueness; exactly one row per `country_iso ∈ C`;
* `residual ∈ [0,1)`, `residual_rank ∈ {1..M}`;
* For each `c_i` at rank `i`: row `(residual,residual_rank) == (r_i, indexOf(i in π)+1)`;
* Path & schema match the dictionary (`…/seed={seed}/parameter_hash={parameter_hash}/`, `#/alloc/ranking_residual_cache`).

**I-7 — Event set reconciliation (local, per merchant).**

* **Cardinality:** `dirichlet_gamma_vector` = `1` iff `M>1`; `residual_rank` = `M`.
* **Envelopes:** dirichlet `after = before ⊕₁₂₈ draws`; each residual-rank has `draws = 0` and `after == before`.
* **Residual-rank payload parity:** for each residual-rank event, `(country_iso, residual, residual_rank)` equals `(C[i].ISO, r[i], indexOf(i in π)+1)`.

**I-8 — Country-order authority separation.**
No attempt to encode inter-country order in egress; consumers must join `country_set.rank`.

**I-9 — Partition/schema fidelity (written artefacts).**
All S7 artefacts (events, cache) sit under **authoritative** paths/partitions and reference the correct JSON-Schema IDs per the dictionary.
Modules: `1A.dirichlet_allocator` (dirichlet), `1A.integerise_allocations` (residual_rank/cache).

**I-10 — `M=1` degenerate path.**
`w=[1]`, `a=[N]`, `f=[N]`, `r=[0.0]`, `d=0`; **no** dirichlet event; **one** residual-rank event with `residual=0.0, residual_rank=1`; one cache row with same values.

---

## Error handling (abort semantics)

Hard-fail with:

* `E-S7.8-LEN-ALIGN` — I-1 failed.
* `E-S7.8-WEIGHT-SUM-INT` — I-2 internal sum fails (`>1e−12`).
* `E-S7.8-EVENT-WEIGHTS` — I-2 event/weights parity fails (`>1e−6` for sum or `>1e−12` compwise vs recompute).
* `E-S7.8-RECOMP-MISMATCH` — I-3 any mismatch (`a,f,r`).
* `E-S7.8-DEFICIT-RANGE` — I-4 failed.
* `E-S7.8-LRR-REPLAY` — I-5 failed (mass or order).
* `E-S7.8-CACHE-CFG` — I-6 failed (schema/path/PK/value mismatch).
* `E-S7.8-RNG-SET` — I-7 failed (counts/envelopes/payload parity).
* `E-S7.8-PATH-SCHEMA` — I-9 failed.

Any failure **blocks S8**; S9 will surface the diagnostics and `_passed.flag` is ineligible.

---

## Reference checker (deterministic; implementation-ready)

```pseudo
function s7_8_validate(merchant_id, C, N, w, a, f, r, d, n,
                       cache_rows, dir_event?, res_events[0..M-1],
                       seed, parameter_hash, run_id):

  M := len(C)
  assert N >= 1 and N < 2^53

  # I-1
  assert M >= 1 and len(w)==len(a)==len(f)==len(r)==len(n)==M
  assert is_unique(C.ISO) and aligns_to_rank(C)  # 0..M-1

  # I-2
  if M == 1:
      assert w[0] == 1.0 and dir_event is None
  else:
      s_int := sum_comp(w)
      assert abs(s_int - 1.0) <= 1e-12
      assert dir_event is not None
      W := dir_event.payload.weights
      assert abs(sum_comp(W) - 1.0) <= 1e-6
      G := dir_event.payload.gamma_raw
      W2 := normalise_with_sum_comp(G)  # S7.3 reducer
      for i in 0..M-1: assert abs(W2[i] - W[i]) <= 1e-12

  # I-3
  for i in 0..M-1:
      ai := float64(N) * w[i]
      fi := floor(ai)
      ui := ai - fi
      qi := roundToEven(1e8 * ui); if qi == 100000000: qi = 99999999
      ri := float64(qi) / 1e8
      assert ai == a[i] and fi == f[i] and ri == r[i]

  # I-4
  d2 := N - sum_i f[i]
  assert 0 <= d2 and d2 < M and d2 == d

  # I-5 (rank on q)
  idx := [0..M-1]
  q := [ min(roundToEven(1e8 * r[i]), 100000000-1) for i in 0..M-1 ]
  stable_sort(idx, key = (-q[i], country_set.rank(C[i]), ISO(C[i])))
  T := set(idx[0:d])
  sum_n := 0
  for i in 0..M-1:
      expect := f[i] + (i in T ? 1 : 0)
      assert n[i] == expect and abs(float64(n[i]) - a[i]) <= 1.0
      sum_n += n[i]
  assert sum_n == N

  # I-6 cache
  rows := cache_rows.for_merchant(merchant_id)
  assert len(rows) == M and pk_unique(rows, ("merchant_id","country_iso"))
  for i in 0..M-1:
      row := rows.lookup(country_iso=ISO(C[i]))
      assert row.residual == r[i] and row.residual_rank == (index_of(i in idx) + 1)
      assert 0.0 <= row.residual and row.residual < 1.0 and row.residual_rank >= 1

  # I-7 events
  if M > 1:
      D := require_one(dir_event)
      assert D.module == "1A.dirichlet_allocator" and D.label == "dirichlet_gamma_vector"
      assert u128_add(D.before_hi, D.before_lo, D.draws) == (D.after_hi, D.after_lo)
  else:
      assert dir_event is None

  assert len(res_events) == M
  seen_iso := {}
  for t in 1..M:
      e := res_events[t-1]
      assert e.module == "1A.integerise_allocations" and e.label == "residual_rank"
      assert e.draws == 0 and e.before == e.after
      assert e.payload.country_iso not in seen_iso
      seen_iso.add(e.payload.country_iso)
      i := rank_index_of_country(C, e.payload.country_iso)
      assert e.payload.residual == r[i]
      assert e.payload.residual_rank == (index_of(i in idx) + 1)

  # I-8 & I-9 (policy/path)
  assert dataset_paths_ok(per_dictionary=true)
  assert no_inter_country_order_in_egress_metadata()

  return OK
```

---

## Conformance tests (automatable)

1. **M=1 happy path:** `N=17`, `C=[GB]` → pass (no dirichlet; one residual-rank event; one cache row).
2. **Dirichlet sums:** craft weights so internal sum error `>1e−12` → `E-S7.8-WEIGHT-SUM-INT`.
3. **Quantiser gridpoint:** `u≈0.999999995` → clamp to `q=1e8−1`, `r=0.99999999`; replay equality succeeds.
4. **Tie cascade:** two equal `r` at 8-dp; different ranks → LRR uses `rank` before ISO; integerisation reproducible.
5. **Cache mismatch:** flip one `residual_rank` → `E-S7.8-CACHE-CFG`.
6. **RNG events:** remove dirichlet for `M=3` or alter a residual-rank envelope (`after≠before`) → `E-S7.8-RNG-SET`.
7. **Path/schema:** move cache rows outside `{seed,parameter_hash}` or wrong schema ref → `E-S7.8-PATH-SCHEMA`.

---

## Complexity & side-effects

Time $O(M\log M)$ (sorting in I-5); memory $O(M)$. Typical $M$ is small (tens). **No RNG** consumed. Produces **no new datasets**; only gates S8.

---

## Relationship to S9

S7.8 is a **local, fail-fast** mirror of S9’s bundle checks. Passing S7.8 doesn’t replace S9; 1B remains gated on `_passed.flag` emitted only after S9 validates the same fingerprint.

---

# S7.9 — Complexity, capacity & governance

## Scope

Summarise and **formalise** the per-merchant and aggregate costs of S7 (Dirichlet allocation + largest-remainder integerisation), the **I/O artefacts** it writes, and the **governance** constraints that keep runs reproducible and auditable. This extends earlier notes with capacity formulas and the policy knobs enforced by S9 at hand-off.

---

## 1) Asymptotics & draw budgets (per merchant)

Let $M=|C|=K+1$ be the number of countries in `country_set` (home + $K$ foreign).

* **Gamma / Dirichlet (S7.2–S7.3).**
  Draw $G_i\sim \Gamma(\alpha_i,1)$ independently; normalise with **Neumaier** in fixed order.
  **Time:** $T_\gamma(M)=\Theta(M)$ (attempt-dependent constant).
  **Space:** $S_\gamma(M)=\Theta(M)$ (arrays `G`, `w`).

* **Integerisation (S7.4–S7.5).**
  Floors + residuals in $\Theta(M)$; **stable** sort by key **`(−q_i, rank, ISO)`** where `q_i = roundToEven(1e8·r_i)` (clamped to `<1e8`).
  **Time:** $T_{\text{integerise}}(M)=\Theta(M\log M)$ (dominant).
  **Space:** $\Theta(M)$.

* **Uniform draw budget (Dirichlet only).** With Marsaglia–Tsang (MT1998) + Box–Muller:

  $$
  \texttt{draws} \;=\; \sum_{i=0}^{M-1}\Big(3\cdot \texttt{attempts}_i + \mathbf{1}[\alpha_i<1]\Big),
  $$

  i.e., **3 uniforms per attempt** for the shape-$\ge 1$ kernel, plus **1** extra uniform for the $0<\alpha<1$ power step. This is recorded in the `dirichlet_gamma_vector` envelope and reconciled against `rng_trace_log`.

**Determinism that constrains complexity:** All ordering-sensitive arithmetic (Dirichlet sum, residual quantisation, LRR sort keys) must be **binary64**, **serial**, **FMA-off**. No BLAS/GPU/pairwise reductions inside a merchant. Parallelism is **across merchants** only.

---

## 2) Aggregate capacity model (batch)

For merchant set $\mathcal{M}$ with $M_j=|C_j|$:

* **CPU time (dominant):**

  $$
  T_{\text{batch}}=\sum_{j\in\mathcal{M}}\!\Big(\Theta(M_j)+\Theta(M_j\log M_j)\Big)=\Theta\!\Big(\sum_j M_j\log M_j\Big).
  $$

  Marsaglia–Tsang attempts change only the constant of the $\Theta(M_j)$ term.

* **Peak memory per worker:** $\max_j \Theta(M_j)$ (process one merchant atomically to respect serial reducers).

* **Exact I/O record counts (per merchant):**

  * `dirichlet_gamma_vector`: **1** iff $M>1$, else **0**.
  * `residual_rank`: **$M$** (always, including $M=1$).
  * `ranking_residual_cache_1A`: **$M$** rows.
    ⇒ **$\mathbf{1} [M>1]+2M$** persisted records across logs + cache per merchant.

---

## 3) Artefacts, partitions, retention (authoritative)

### Parameter-scoped cache (reused across fingerprints)

* **`ranking_residual_cache_1A`**
  **Path:** `data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/`
  **Partitioning:** `["seed","parameter_hash"]` • **Format:** Parquet • **Retention:** **365 days** • **PII:** **false**
  **PK:** `["merchant_id","country_iso"]` • **Schema:** `schemas.1A.yaml#/alloc/ranking_residual_cache`
  **produced_by:** `"1A.integerise_allocations"`

### Run-scoped RNG logs (per `run_id`)

* **`dirichlet_gamma_vector`** (JSONL):
  `logs/rng/events/dirichlet_gamma_vector/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` • **Retention:** **180 days** • **produced_by:** `"1A.dirichlet_allocator"` • **Schema:** `#/rng/events/dirichlet_gamma_vector`
* **`residual_rank`** (JSONL):
  `logs/rng/events/residual_rank/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` • **Retention:** **180 days** • **produced_by:** `"1A.integerise_allocations"` • **Schema:** `#/rng/events/residual_rank`
* **`rng_trace_log`** (JSONL):
  `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl` • **Schema:** `#/rng/core/rng_trace_log`

*(Downstream egress `outlet_catalogue` is fingerprint-scoped and is gated by S9; included here for governance continuity.)*

---

## 4) Execution model & concurrency (deterministic)

1. **Within a merchant (S7.1–S7.8):**

   * Dirichlet normalisation (S7.3) and residual quantisation + LRR (S7.4–S7.5) **must** execute as **single-thread serial loops** in `country_set.rank` order, **binary64**, **FMA-off**.
   * Precondition: `N < 2^53` to keep `float64(N)` exact.

2. **Across merchants:**

   * Safe to run in parallel; each merchant has independent labelled substreams and envelopes. Determinism holds because reconciliation keys are `(seed, parameter_hash, run_id, module, label, merchant_id)`.

3. **Idempotence & retries:**

   * Cache partitions keyed by `{seed, parameter_hash}` with PK `(merchant_id, country_iso)`; use **overwrite-then-commit** per partition/merchant for idempotent retries.

---

## 5) Numeric governance (artefact-backed)

* **Environment artefacts:** `ieee754_binary64=true`, `fma_disabled=true`. Altering them **changes the fingerprint** and is a validation failure.
* **Residual policy artefact:** `residual_quantisation_policy = { scale: 1e8, rounding: ties_to_even, clamp_lt_1: true }`.
* **Reducer policy artefact:** `sum_reducer = "Neumaier_serial_rank_order"`.
* **Tolerance policy:** internal Dirichlet sum **1e−12**; event/schema guard **1e−6**.
* **RNG envelope & trace:** every event carries `(before, after, draws)`; S9 proves (a) `after − before = draws` per event and (b) `∑ events draws = trace draws` per `(module,label,merchant)`.

---

## 6) Must-hold governance invariants

**G-1 Partition & scope fidelity.**
Cache under `{seed, parameter_hash}`; events & trace under `{seed, parameter_hash, run_id}`; egress under `{seed, fingerprint}`. Any drift is a schema/dictionary failure.

**G-2 Authority of country order.**
Inter-country order lives **only** in `country_set.rank`. Neither cache nor egress encodes cross-country sequencing; consumers **must** join `country_set`.

**G-3 Event cardinalities & envelopes.**
Per merchant: `dirichlet_gamma_vector = 𝟙[M>1]`, `residual_rank = M`. Envelopes: Dirichlet `after = before ⊕₁₂₈ draws`; residual-rank `draws=0` and `after==before`.

**G-4 Numeric policy.**
Binary64; serial reducers; **FMA-off**; residuals quantised to **8 dp before sort**; **LRR key = (−q, rank, ISO)**; internal Dirichlet guard `1e−12`, schema guard `1e−6`.

**G-5 Validation gate (consumption).**
1B may read `outlet_catalogue(seed,fingerprint)` **iff** `data/layer1/1A/validation/fingerprint={fingerprint}/` contains `validation_bundle_1A` and `_passed.flag` where `SHA256(bundle) == contents(_passed.flag)`.

**G-6 Retention & licensing.**
Cache **365d**, RNG events **180d**; all listed datasets `pii:false`, `licence: Proprietary-Internal`.

---

## 7) Monitoring & CI signals (what S9 certifies)

* **Schema/keys/FK** for `country_set`, `ranking_residual_cache_1A`, and egress.
* **RNG accounting:** presence counts per label, envelope deltas vs trace, and attempt-budget spot checks (`draws = 3∑A_i + ∑1[α_i<1]`). Output: `rng_accounting.json`.
* **Corridor metrics:** LRR max error, zero-top-up rate, sparsity, (optional) hurdle calibration. These are compared to governed bounds; failures block `_passed.flag`.

*(Optional future: nightly CI drift artefact keyed by `run_id`; non-blocking.)*

---

## 8) Practical scheduling recipe (reference)

* **Shard by merchant** across workers; each worker processes a merchant **atomically** through S7.1→S7.8.
* **Inside a worker:** honour serial reducers (S7.3) and residual quantisation + LRR (S7.4–S7.5).
* **Emit events** with full envelopes first (`dirichlet_gamma_vector` iff $M>1$, then `residual_rank` × M).
* **Persist cache** rows (overwrite-then-commit; enforce PK).
* **Run S7.8** local validator; only on success proceed to S8 (egress). Fail closed otherwise.

---

## 9) Conformance checklist (must pass before S8/S9)

1. Paths & partitions match dictionary for cache and events. ✔︎
2. Event cardinalities and envelopes obey **G-3** (incl. `draws=0` for residual-rank). ✔︎
3. Cache has **M** rows with PK uniqueness; `residual∈[0,1)` and integer `residual_rank∈[1..M]`. ✔︎
4. Numeric policy asserted: **binary64**, **Neumaier**, **FMA-off**, **8-dp pre-sort**; recorded as environment artefacts. ✔︎
5. RNG trace reconciliation clean per label (events ↔ trace). ✔︎
6. Hand-off gate present (`validation_bundle_1A` + `_passed.flag` = SHA256(bundle)). ✔︎

---

That pins S7.9: exact cost model, deterministic concurrency rules, authoritative I/O/retention/partition contracts, and the governance invariants S9 certifies before 1B is allowed to read.

---