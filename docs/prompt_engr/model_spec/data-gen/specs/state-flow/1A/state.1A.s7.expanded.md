# S7.1 — α-vector resolution (governed ladder)

## Scope & purpose

S7 needs a Dirichlet concentration vector $\alpha\in\mathbb{R}^{m}_{>0}$ whose **length** and **ordering** match the merchant’s ordered country set $C=(c_0,\dots,c_{m-1})$ (home at rank 0, then foreigns in the Gumbel order from S6). `country_set` is the **only** authority for this membership and order; S7 must not reorder or mutate it.

When $m=1$ (domestic-only path), S7 later forces $w=(1)$ and $n=(N)$; $\alpha$ is **not** used, but we still emit one `residual_rank` event to keep logging invariants. (This is specified elsewhere in S7, referenced here for completeness.)

---

## Definitions (normative)

* $C=(c_0,\dots,c_{m-1})$: ordered countries from `country_set` with `rank(c_i)=i`.
* Lookup **key cardinality** $m:=|C|\in\mathbb{Z}_{\ge 1}$.
* $\alpha=(\alpha_0,\dots,\alpha_{m-1})\in\mathbb{R}^m_{>0}$: Dirichlet concentrations aligned **index-for-index** with $C$ (i.e., $\alpha_i$ belongs to country $c_i$).

---

## Preconditions (MUST)

1. `country_set` exists for the merchant and is partition-consistent for this run (`seed`, `parameter_hash`). It is the **sole** authority for order.
2. $m=|C|\ge 1$; all `country_iso` values are valid ISO-2; no duplicates.
3. The α source (governed “cross-border hyperparameters”) is part of the parameter-scoped inputs (thus **versioned by** `parameter_hash`).

---

## Resolution algorithm (normative)

Let `home`, `MCC`, and `channel` be the merchant’s attributes; let $m=|C|$.

**Ladder (exact→fallback):**

1. **Exact:** $(\text{home},\text{MCC},\text{channel}, m)$
2. **Back-off A:** $(\text{home},\text{channel}, m)$
3. **Back-off B:** $(\text{home}, m)$
4. **Fallback (symmetric):** $\alpha_i=\tau/m$ for all $i$, with governed $\tau>0$ (default **$\tau=2.0$**).

**Post-lookup normalisation & guards:**

* **Dimension check:** the retrieved vector **must** have length $m$; else `ERR_S7_ALPHA_DIM_MISMATCH(m_expected=m, m_found=len(alpha))`.
* **Positivity floor:** enforce $\min_i \alpha_i \ge 10^{-6}$. If any component violates this after load, **abort** with `ERR_S7_ALPHA_NONPOSITIVE(i, value)`. (This avoids pathological Gamma shape parameters downstream.)
* **Ordering alignment:** map/produce $\alpha$ **in the exact order of `country_set.rank`** (0..$m{-}1$); order must be stable across runs.

**Determinism and provenance:**

* The α resolution uses only deterministic inputs (`home`, `MCC`, `channel`, $m$) and parameter-scoped artefacts governed by `parameter_hash`. Consumers and validators can therefore **recompute** the same $\alpha$ without additional RNG. (Optionally, record the ladder step used in the **validation bundle diagnostics**.)

---

## Numeric environment (must match S7 policy)

* IEEE-754 **binary64** throughout; **no FMA** in ordering-sensitive computations (S7 applies this during Dirichlet normalisation and rounding, but α loading itself is non-numeric).

---

## Error handling (abort semantics)

* `ERR_S7_ALPHA_KEY_MISSING(level, key)`: no match at the specified ladder level (informative if later levels succeed).
* `ERR_S7_ALPHA_DIM_MISMATCH(m_expected, m_found)`: returned vector length $\neq m$.
* `ERR_S7_ALPHA_NONPOSITIVE(index, value)`: any $\alpha_i < 10^{-6}$.
* `ERR_S7_COUNTRYSET_INVALID`: `country_set` failed preconditions (duplicates, missing home, or order missing).

---

## Invariants (MUST hold)

1. **Authority & order:** $\alpha$ is aligned one-to-one with `country_set` (rank order); S7 **never** mutates `country_set`.
2. **Determinism:** Given (`home`, `MCC`, `channel`, $m$, `parameter_hash`) the resolution is a **pure function** — identical across replays.
3. **Safety floor:** $\alpha_i\ge 10^{-6}\ \forall i$.
4. **Fallback soundness:** If only symmetric fallback is available, $\alpha=(\tfrac{\tau}{m},\dots,\tfrac{\tau}{m})$ with default $\tau=2.0$.

---

## Reference pseudocode (deterministic)

```pseudo
function resolve_alpha(home, mcc, channel, C: list[country_iso], param_store) -> array[float64]:
    # Preconditions
    assert is_country_set_valid(C)              # rank order, no dups, home at index 0
    m := len(C); assert m >= 1

    # Ladder lookups are pure reads against parameter-scoped store
    key_exact   := {home:home, mcc:mcc, channel:channel, m:m}
    key_backA   := {home:home, channel:channel, m:m}
    key_backB   := {home:home, m:m}

    alpha := param_store.get_alpha(key_exact)
    if alpha is None: alpha := param_store.get_alpha(key_backA)
    if alpha is None: alpha := param_store.get_alpha(key_backB)
    if alpha is None:
        tau := 2.0  # governed default
        alpha := [tau / m] * m

    # Dimension & ordering
    if len(alpha) != m:
        raise ERR_S7_ALPHA_DIM_MISMATCH(m, len(alpha))

    # Align to country_set order if source provided a mapping (else assume aligned)
    # (Implementation variant: sources should already be length-m vectors in order.)
    # Here we assert alignment is identity:
    assert len(alpha) == m

    # Positivity floor
    for i in 0..m-1:
        if alpha[i] < 1e-6:
            raise ERR_S7_ALPHA_NONPOSITIVE(i, alpha[i])

    return alpha
```

---

## Conformance tests (minimal suite)

1. **Exact hit:** Provide table entries at all ladder levels; ensure the **highest** (exact) level is chosen; verify α length $=m$, floor respected.
2. **Back-off A:** Remove exact key; ensure A is chosen and yields the same α as reference; determinism across replays.
3. **Back-off B:** Remove A as well; verify B is chosen and aligned in order.
4. **Fallback:** Remove all entries; verify $\alpha_i=\tau/m$ with default $\tau=2.0$.
5. **Dimension mismatch:** Supply a length $m{-}1$ vector for exact key; expect `ERR_S7_ALPHA_DIM_MISMATCH`.
6. **Non-positive component:** Supply an α with $\alpha_j=10^{-7}$ then $10^{-9}$; both should **pass** floor? (First passes, second fails.) Actually with floor $10^{-6}$: $10^{-7}$ < floor ⇒ **fail**; expect `ERR_S7_ALPHA_NONPOSITIVE` — confirm the guard works.
7. **Country-set integrity:** Corrupt `country_set` (duplicate ISO or wrong home at rank 0); expect `ERR_S7_COUNTRYSET_INVALID` **before** any α lookup.
8. **Parameter-scoped determinism:** Change a parameter-scoped artefact version (i.e., change `parameter_hash`) and confirm downstream replay produces a **different** α (as intended by lineage), while reruns with the **same** `parameter_hash` reproduce α bit-identically.

---

### Notes & cross-refs

* This section only **resolves** $\alpha$. The **sampling** of $G_i\sim\Gamma(\alpha_i,1)$, Neumaier normalisation to $w$, and the sum-to-one tolerance live in S7.2–S7.3 (and inherit S7’s numeric policy).
* `country_set` remains authoritative for order; inter-country order is **not** encoded in `outlet_catalogue` (1B must join `country_set.rank`; stated elsewhere, repeated here for clarity).

---

# S7.2 — RNG envelope & Dirichlet draw (Marsaglia–Tsang)

## Scope & purpose

Given the ordered country set $C=(c_0,\dots,c_{m-1})$ from `country_set` and the $\alpha$-vector from **S7.1**, sample $G_i\sim\mathrm{Gamma}(\alpha_i,1)$ independently, normalise to $w_i=G_i/\sum_j G_j$, and (iff $m>1$) emit a **single** RNG event `dirichlet_gamma_vector` with arrays aligned to $C$ and a replayable **envelope** (seed, substream label, pre/post counters, draws). For $m=1$ we **skip** sampling and do **not** emit this event (later integerisation still emits one `residual_rank`).

---

## Inputs (MUST)

* `country_set` for the merchant (authoritative membership + order; ranks 0..$m{-}1$).
* $\alpha=(\alpha_0,\dots,\alpha_{m-1})$ resolved in **S7.1**; length $m$; $\alpha_i>0$.
* Run lineage tuple: `(seed, parameter_hash, manifest_fingerprint)` (for keyed substreams & partitioning).

---

## RNG discipline (normative)

* **Keyed substreams.** All uniforms for this sub-state are under label $\ell=$"dirichlet_gamma_vector" and merchant $m_id$, using S0’s mapping
  $(c^{\text{base}}_{\text{hi}},c^{\text{base}}_{\text{lo}})=\text{SHA256}("ctr:1A"\,\|\,\texttt{fingerprint}\,\|\,\texttt{seed}\,\|\,\ell\,\|\,\texttt{merchant})[0{:}16]$; the $i$-th uniform uses counter $(c^{\text{base}}_{\text{hi}},c^{\text{base}}_{\text{lo}}+i)$ with 128-bit carry. **Order-invariant.**
* **Uniforms on (0,1).** From 64-bit lanes via $u=(x+1)/(2^{64}+1)\in(0,1)$. Each uniform consumes **one** lane; one counter increment ⇒ one uniform.
* **Normals.** Standard normal by Box–Muller with **no spare caching**; exactly **2 uniforms** per $Z$.
* **Envelope accounting.** Every RNG event carries `(before_hi, before_lo, after_hi, after_lo, draws)` with
  $(\texttt{after_hi},\texttt{after_lo})=(\texttt{before_hi},\texttt{before_lo})+\texttt{draws}$ in 128-bit unsigned arithmetic. A per-module `rng_trace_log` row records the **same** draws for audit.

---

## Algorithm (normative)

### A) Early exit for $m=1$

If $|C|=1$: set $w=[1.0]$ and **do not** emit `dirichlet_gamma_vector`. (S7 later emits one `residual_rank` with `draws=0`.)

### B) Sample gamma components (Marsaglia–Tsang MT1998)

For each $i\in\{0,\dots,m-1\}$ independently:

* **Case $\alpha_i\ge 1$:** Let $d=\alpha_i-\tfrac13$, $c=(9d)^{-1/2}$. Repeat attempts:

  1. draw $Z\sim\mathcal N(0,1)$ (2 uniforms); set $V=(1+cZ)^3$; if $V\le 0$, retry;
  2. draw $U\sim U(0,1)$ (1 uniform);
  3. accept iff $\ln U < \tfrac12 Z^2 + d - dV + d\ln V$; then return $G_i=dV$.
     **Budget:** **3 uniforms per attempt**.

* **Case $0<\alpha_i<1$:** Draw $G'\sim\Gamma(\alpha_i+1,1)$ via the branch above (variable attempts), then one extra $U\sim U(0,1)$ and set $G_i=G'\,U^{1/\alpha_i}$.
  **Budget:** **+1 uniform** beyond those consumed by $G'$.

### C) Normalise to Dirichlet weights (deterministic)

Compute $S=\sum_i G_i$ as a deterministic **serial** sum in the `country_set.rank` order; set $w_i=G_i/S$. For the event payload, enforce $\big|1-\sum_i w_i\big|\le 10^{-6}$ using the same serial reducer; violation ⇒ abort. (This matches the event-schema constraint; internally you may enforce a stricter target.)

### D) Emit **one** `dirichlet_gamma_vector` event (iff $m>1$)

Write a single JSONL record under:

```
logs/rng/events/dirichlet_gamma_vector/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
schema_ref: schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector
produced_by: 1A.dirichlet_allocator
```

Payload arrays must be **equal-length** and aligned to `country_set` order:
`country_isos=[c_0,…,c_{m-1}]`, `alpha=[α_0,…,α_{m-1}]`, `gamma_raw=[G_0,…,G_{m-1}]`, `weights=[w_0,…,w_{m-1}]`. The envelope reflects the exact draw count consumed by all $m$ components.

*(Optional but recommended)*: also emit a `stream_jump` record for this label the **first time** the module emits for the merchant.

---

## Draw-count formula (for validators)

Let $A_i$ be the number of **attempts** taken by the MT kernel for component $i$ under the $\alpha\ge1$ branch (if $\alpha_i<1$, this is for $\alpha_i{+}1$). Then the event’s `draws` equals:

$$
\texttt{draws} \;=\; 3\sum_{i=0}^{m-1} A_i \;+\; \sum_{i=0}^{m-1}\mathbf{1}[\alpha_i<1],
$$

and envelope counters must satisfy the 128-bit delta rule; the `rng_trace_log` aggregates must reconcile with this formula.

---

## Numeric policy

* All arithmetic in this sub-state uses IEEE-754 **binary64**; **no FMA** in ordering-sensitive steps (sums & divisions used for normalisation). Use deterministic serial reductions in `country_set.rank` order.

---

## Additions

**Authoritative path/partition/schema (normative):**

```
logs/rng/events/dirichlet_gamma_vector/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
schema_ref: schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector
partitioning: ["seed","parameter_hash","run_id"]
produced_by: "1A.dirichlet_allocator"
```

As catalogued in the data dictionary. Any deviation is a schema violation.

**Envelope fields (must exist):**

* `seed` (uint64 or decimal string per schema), `parameter_hash` (hex64 lowercase), `manifest_fingerprint` (hex64 lowercase), `run_id` (string),
* `module` (string; e.g., `"1A.dirichlet_allocator"`), `label` (exactly `"dirichlet_gamma_vector"`),
* `counter_before_hi` (uint64), `counter_before_lo` (uint64), `counter_after_hi` (uint64), `counter_after_lo` (uint64),
* `draws` (uint64; **must equal** the derived formula below), `ts` (ISO-8601, optional if schema requires).
  (Names must match the JSON-Schema; this list mirrors the shared RNG-event envelope family used across 1A.)

**Payload fields (must exist, equal length, `country_set` order):**

* `country_isos` (array\[string, ISO-2]), `alpha` (array\[number>0]), `gamma_raw` (array\[number>0]), `weights` (array\[number in (0,1)]).
  Arrays must be length $m=|C|$ and aligned index-for-index with `country_set` (rank 0..m-1).

**Draw-budget + counter advance (normative equality):**

$$
\texttt{draws} \;=\; 3\sum_{i=0}^{m-1}\!A_i \;+\; \sum_{i=0}^{m-1}\mathbf{1}[\alpha_i<1],
$$

with $A_i$ the number of Marsaglia–Tsang **attempts** for component $i$ (for $\alpha_i\ge1$; or for $\alpha_i+1$ when $\alpha_i<1$). The 128-bit Philox counter **must** satisfy:

$$
(\texttt{after_hi},\texttt{after_lo})=(\texttt{before_hi},\texttt{before_lo}) \oplus_{128} \texttt{draws}.
$$

A validator recomputes $A_i$ from the event payload and asserts both equalities.

**Minimal compliant JSONL example (illustrative but schema-valid):**

```json
{
  "envelope": {
    "seed": 42,
    "parameter_hash": "3f9c...8d1a",
    "manifest_fingerprint": "ab12...34cd",
    "run_id": "2025-08-15T11:00:00Z#001",
    "module": "1A.dirichlet_allocator",
    "label": "dirichlet_gamma_vector",
    "counter_before_hi": 0, "counter_before_lo": 128,
    "counter_after_hi": 0,  "counter_after_lo": 167,
    "draws": 39,
    "ts": "2025-08-15T11:00:12.345Z"
  },
  "payload": {
    "country_isos": ["GB","IE","FR"],
    "alpha": [0.6666666667,0.6666666667,0.6666666667],
    "gamma_raw": [0.8412,1.2311,0.5237],
    "weights": [0.3564,0.5216,0.1220]
  }
}
```

(Names/types must obey the schema ref above; partitions must be exactly `seed/parameter_hash/run_id`.)

**Event cardinality (per merchant, MUST hold):**

* Emit **exactly one** `dirichlet_gamma_vector` **iff** $|C|>1$; **none** if $m=1$. Validators enforce this by counting per merchant across that path.

**Hard errors (abort):**

* `E-S7.2-PAYLOAD-LEN-MISMATCH` (arrays unequal length),
* `E-S7.2-SUM-TOL` ( $|\sum w-1|>10^{-6}$ under the serial reducer),
* `E-S7.2-UNDERFLOW` ($\sum G=0$),
* `E-S7.2-COUNTER-DELTA` (envelope `after-before ≠ draws`).
  These are structural and trip S9 hard-fail; 1B cannot proceed (hand-off gate).

---

## Error handling (abort conditions)

* **Schema/tolerance:** arrays not equal-length or $|1-\sum w_i|>10^{-6}$ ⇒ abort (violates event schema).
* **Non-positive $\alpha$:** defensive abort (should be prevented by S7.1 floor & schema).
* **Zero sum:** if $S=\sum_i G_i=0$ due to pathological underflow, abort (`gamma_underflow_zero_sum`).

---

## Invariants (MUST hold)

1. **Event cardinality:** per merchant, emit **exactly one** `dirichlet_gamma_vector` iff $|C|>1$; emit **none** if $|C|=1$.
2. **Envelope correctness:** `after = before + draws` (128-bit); `draws` equals the formula above.
3. **Alignment:** payload arrays align index-for-index with `country_set` order (home rank 0; then S6’s Gumbel order).
4. **Partitions:** event path partitions by `{seed, parameter_hash, run_id}` exactly as in the dictionary.

---

## Reference pseudocode

```pseudo
function s7_2_dirichlet_draw(country_set C, alpha[0..m-1], lineage) -> (w[0..m-1], event?):
    assert len(C) == len(alpha) == m >= 1
    if m == 1:
        return ([1.0], None)                       # no event; S7 emits residual_rank later

    # Substream: all uniforms under label "dirichlet_gamma_vector"
    env_before := keyed_counter_before(lineage, label="dirichlet_gamma_vector")

    G := array<float64>(m)
    draws := 0
    for i in 0..m-1:
        a := alpha[i]
        if a >= 1:
            repeat:
                Z := box_muller_u01()              # uses 2 uniforms
                draws += 2
                V := (1 + (9*(a-1/3))^(-1/2) * Z)^3
                if V <= 0: continue
                U := u01()                         # +1 uniform
                draws += 1
                if log(U) < 0.5*Z*Z + (a-1/3) - (a-1/3)*V + (a-1/3)*log(V):
                    G[i] = (a-1/3)*V; break
        else:
            # α in (0,1): sample α+1 branch then power step
            Gp, d := gamma_mt_kernel(alpha=a+1)    # returns value and uniforms consumed (multiple of 3)
            draws += d
            U := u01()                             # +1 uniform
            draws += 1
            G[i] = Gp * U^(1/a)

    S := serial_sum(G)                              # deterministic order
    if S == 0: abort("gamma_underflow_zero_sum")

    w := [ Gi / S for Gi in G ]
    if abs(1.0 - serial_sum(w)) > 1e-6:
        abort("dirichlet_sum_mismatch")

    env_after := env_before + draws (u128)
    event := {
        envelope: { seed, parameter_hash, manifest_fingerprint,
                    label:"dirichlet_gamma_vector",
                    before:env_before, after:env_after, draws:draws },
        payload:  { country_isos: C, alpha: alpha, gamma_raw: G, weights: w }
    }
    write_event_jsonl(event, path=DIRICHLET_EVENT_PATH)  # per dictionary
    write_trace(label="dirichlet_gamma_vector", draws=draws)
    return (w, event)
```

---

## Conformance tests

1. **Event cardinality:** $m=1$ ⇒ **no** event; $m=2$ ⇒ **exactly one** event; validate paths/partitions.
2. **Array alignment:** shuffle `country_set` externally and re-run in audit mode — validator must fail due to misalignment (arrays must match `country_set` order).
3. **Draw accounting:** instrument a test run, count MT attempts per component, verify `draws = 3∑A_i + ∑1[α_i<1]` and envelope delta equality; reconcile with `rng_trace_log`.
4. **Sum-to-one:** perturb $G$ to force $|1-\sum w|>10^{-6}$; expect abort per schema guard.
5. **Determinism:** re-run with identical lineage — byte-compare payload arrays & counters; change `parameter_hash` — event persists but payload differs (different $\alpha$ universe).

That’s the complete, replay-proof spec for the Dirichlet sampling step: single labelled event with exact draw budgets, order-invariant keyed substreams, schema-bound payloads, and tight alignment to `country_set`.

---

# S7.3 — Deterministic normalisation & sum-to-one check

## Scope & purpose

Given the ordered country set $C=(c_0,\dots,c_{m-1})$ and the independent gamma components $G_i\sim\Gamma(\alpha_i,1)$ sampled in **S7.2**, compute weights $w_i = G_i/\sum_j G_j$ **deterministically** and enforce two tolerances:

* **Internal target (algorithmic):** $\big|\sum_i w_i - 1\big|\le 10^{-12}$ (binary64), else **abort**.
* **Event/schema guard (payload):** $\big|\sum_i w_i - 1\big|\le 10^{-6}$ (validator accepts at this looser bound).

Arrays must remain **aligned to `country_set.rank`** (home rank 0; then S6’s Gumbel order).

---

## Inputs (MUST)

* $G=(G_0,\dots,G_{m-1})\in\mathbb{R}^m_{>0}$ from S7.2; $m=|C|\ge 1$. (For $m=1$ S7.2 already short-circuits; S7.3 is vacuous.)
* The ordered `country_set` for membership and order (sole authority).

---

## Numeric environment (normative)

* IEEE-754 **binary64** everywhere; **FMA disabled** in ordering-sensitive paths.
* Reductions are **serial, deterministic** and occur in `country_set.rank` order (ISO as secondary only when explicitly stated).

---

## Method (normative): Neumaier compensated serial sum

Let $\texttt{sum_comp}(\cdot)$ be the **Neumaier** compensated reducer in fixed order:

```text
function sum_comp(x[0..m-1]):
  s = 0.0; c = 0.0
  for i in 0..m-1 in country_set.rank ascending (then ISO):
    t = s + x[i]
    if abs(s) >= abs(x[i]): c += (s - t) + x[i]
    else:                   c += (x[i] - t) + s
    s = t
  return s + c
```

* **Prohibitions:** no pairwise/parallel/Kahan, no BLAS/GPU — this normalisation is a **single-thread loop** (part of determinism).

---

## Additions

**Internal vs. schema tolerance (boxed, normative):**

* **Internal algorithmic target:** after Neumaier normalisation, compute $S'=\sum w$ with the same reducer; **abort S7** if $|S'-1|\!>\!10^{-12}$.
* **Event/schema guard:** the already-emitted `dirichlet_gamma_vector` payload must satisfy $|\sum w-1|\!\le\!10^{-6}$ under the same reducer; validators enforce this at read time.
  (Why two? The internal $10^{-12}$ guarantees integerisation determinism; $10^{-6}$ is the cross-system validation tolerance.)

**Reducer prohibition (explicit):**

* For this step, **pairwise/parallel/GPU/BLAS reductions are forbidden**; use the serial Neumaier loop in `country_set.rank` order (ISO only as a later tie-key elsewhere). Violations are flagged in the validation bundle (`numeric_determinism.json`).

**Validator-style recomputation (worked check):**
Given the event’s `weights` array, a validator recomputes

```text
s=0; c=0; for i in rank order: t=s+wi; c += (abs(s)>=abs(wi) ? (s-t)+wi : (wi-t)+s); s=t
assert abs((s+c) - 1.0) <= 1e-6
```

and fails the run otherwise. (This mirrors S7’s own reducer.)

**No-clamp policy hooked to S9/1B gate:**

* Breaching $10^{-12}$ is **hard fail**; S9 will refuse to write `_passed.flag`, and 1B’s **preflight** must then block reading `outlet_catalogue` for that fingerprint.

**Complexity & memory (informative, for implementers):**

* Time $O(m)$ to sum and normalise; memory $O(m)$. Typical $m$ is small (tens). This must run **single-threaded** by policy (determinism). (Large-$m$ is not expected in 1A.)

---

## Algorithm (normative)

1. **Early exit.** If $m=1$: set $w=[1.0]$ (already done in S7.2) and skip the rest.

2. **Compute the sum.**
   $S \leftarrow \texttt{sum_comp}(G_0,\dots,G_{m-1})$. Since each $G_i>0$, $S>0$; if $S=0$ by underflow, **abort** (`gamma_underflow_zero_sum`).

3. **Normalise.**
   For each $i$: $w_i \leftarrow G_i / S$ using binary64 division; store $w$ in the same order as $C$.

4. **Sum-to-one enforcement (two-stage).**
   (a) *Internal*: $S' \leftarrow \texttt{sum_comp}(w)$. Abort if $|S' - 1| > 10^{-12}$.
   (b) *Event/schema*: the `dirichlet_gamma_vector` payload (from S7.2) **must** also satisfy $|\sum w - 1|\le 10^{-6}$ when re-summed serially by validators.

5. **Emit / reconcile event.**
   S7.2 already emitted exactly **one** `dirichlet_gamma_vector` event (iff $m>1$) holding `gamma_raw` and `weights`. S7.3 does **not** emit new RNG events; it only guarantees the payload obeys the tolerance and alignment. Paths & schema: `logs/rng/events/dirichlet_gamma_vector/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with `schema_ref: schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector`.

---

## Properties & obligations

* **Determinism:** Given $G$ and `country_set.rank`, $w$ is a pure function of binary64 arithmetic with a fixed reducer and order. Any deviation (parallel reduction, different order, FMA) breaks replay.
* **No clamping:** If internal tolerance fails, **fail closed**; do not re-scale ad-hoc. This preserves auditability and keeps event payloads within the declared schema.
* **Alignment:** Arrays stay index-aligned to `country_set` order (home first, then Gumbel order).
* **Accounting:** Normalisation consumes **no** random draws; `draws` in the S7.2 event equals $3\sum A_i + \sum \mathbf{1}[\alpha_i<1]$.

---

## Reference pseudocode (deterministic)

```pseudo
function s7_3_normalise(G[0..m-1], C) -> w[0..m-1]:
    assert m == len(C) == len(G) and m >= 1
    if m == 1: return [1.0]

    # Serial compensated sum (fixed order)
    S = sum_comp(G)
    if S == 0.0: abort("gamma_underflow_zero_sum")

    w = array<float64>(m)
    for i in 0..m-1:
        w[i] = G[i] / S

    S1 = sum_comp(w)
    if abs(S1 - 1.0) > 1e-12:
        abort("dirichlet_sum_mismatch_internal")

    # (S7.2 has already emitted the event; we only guarantee schema compliance)
    # Validators will accept |sum(w)-1| <= 1e-6 per event schema.

    return w
```

---

## Invariants (MUST hold)

1. $S>0$; $w_i \in (0,1)$ and $\sum_i w_i = 1 \pm 10^{-12}$ internally.
2. Event payloads satisfy $\sum w = 1 \pm 10^{-6}$ under the same serial reducer.
3. Arrays align index-for-index with `country_set` order.
4. Normalisation uses **Neumaier** in fixed order; no BLAS/parallel/GPU for this step.

---

## Conformance tests

1. **Tolerance split:** Construct $G$ that yields $|\sum w - 1| \approx 10^{-10}$ → pass internal & event checks; perturb to exceed $10^{-12}$ but be $<10^{-6}$ → **abort internally** (as required); ensure validators would have accepted the payload bound.
2. **Order dependence check:** Recompute sums with a different order or pairwise tree — result must **differ** on crafted inputs; the reference reducer must pass. (Guards drift.)
3. **Underflow guard:** Force tiny $G_i$ and verify $S>0$; if not, abort with `gamma_underflow_zero_sum`.
4. **Event reconciliation:** For $m>1$, verify there is **exactly one** `dirichlet_gamma_vector` event, that arrays are aligned to `country_set`, and that recomputing $\sum w$ serially satisfies the schema bound.
5. **Determinism:** Re-run with identical lineage: byte-equal $w$ and no change in RNG counters (`draws` unchanged, since normalisation consumes none).

---

**Where this hands off:** $w$ now satisfies the numeric contract and is ready for **S7.4** (forming $a_i=Nw_i$, flooring, residual quantisation $Q_8$, and preparing for largest-remainder integerisation).

---

# S7.4 — Real allocations & residual quantisation

## Scope & purpose

Take the (ordered) country set $C=(c_0,\dots,c_{m-1})$, total outlets $N\in\mathbb{Z}_{\ge1}$, and the Dirichlet weights $w=(w_0,\dots,w_{m-1})$ from **S7.3** (already sum-to-one within internal tolerance) and produce:

* real allocations $a_i=N\,w_i$ (binary64),
* floors $f_i=\lfloor a_i\rfloor$ (int32),
* **quantised** residuals $r_i\in[0,1)$ at **exactly 8 decimal places** (ties-to-even), for deterministic tie-breaks in S7.5.

All arrays remain index-aligned to `country_set.rank` (home = 0, then S6 Gumbel order).

---

## Inputs (MUST)

* `country_set` for the merchant; membership & order are authoritative, with `rank(c_i)=i`. No duplicates; all ISO-2.
* $N=$ `raw_nb_outlet_draw` (int32, $N\ge1$).
* $w=(w_0,\dots,w_{m-1})$ from S7.3; $\sum_i w_i=1\pm 10^{-12}$ internally; $m=|C|\ge1$.

---

## Numeric environment (normative)

* IEEE-754 **binary64** arithmetic for all real operations; **FMA disabled** anywhere ordering or rounding affects branching or ranking (this whole sub-state).
* Deterministic **serial** loops in `country_set.rank` order (ISO used only where explicitly stated elsewhere). Parallel/pairwise reductions are forbidden here. (Sums needed were already handled in S7.3.)

---

## Definitions (normative)

* **Real allocations:** $a_i:=\mathrm{R}_{64}(N)\times \mathrm{R}_{64}(w_i)\in\mathbb{R}_{64}$, computed as a single binary64 multiply; **no FMA**.
* **Integer floors:** $f_i:=\lfloor a_i\rfloor\in\mathbb{Z}_{\ge0}$ (int32).
* **Raw residuals:** $u_i:=a_i-f_i\in[0,1)$.
* **8-dp quantiser $Q_8$:** for $u\in[0,1)$,

  $$
  q \;=\; \operatorname{roundToEven}(10^8 u)\ \in\ \{0,1,\dots,10^8\},\qquad
  r \;=\; \frac{\min(q,\,10^8-1)}{10^8}.
  $$

  Here `roundToEven` is nearest-integer with **ties-to-even**. The `min` enforces $r<1$ even at pathological half-ULP cases near 1.0. (Dataset & validator require $r\in[0,1)$.)

> Equivalent presentation (used elsewhere): $r = Q_8(u) = \mathrm{R}_{64}\!\big(\mathrm{R}_{64}(10^8\!\cdot\!u)/10^8\big)$ — but the **normative** rule for ranking is the integer rounding above (ties-to-even, then clamp to $10^8{-}1$).

---

## Algorithm (normative)

1. **Early case $m=1$ (domestic-only).**
   $a_0=N$, $f_0=N$, $u_0=0$, $r_0=0.00000000$. (Still one residual-rank event is emitted later in S7.5.)

2. **Compute real allocations.**
   For each $i=0,\dots,m-1$ (rank order):
   $a_i\leftarrow \mathrm{R}_{64}(N)\times w_i$. Store $a_i$ (binary64).

3. **Floors and raw residuals.**
   $f_i\leftarrow \lfloor a_i\rfloor$ (int32), $u_i\leftarrow a_i-f_i$.

4. **Quantise residuals (8 dp).**
   $q_i\leftarrow \operatorname{roundToEven}(10^8 u_i)$ (int64).
   If $q_i=10^8$, set $q_i\leftarrow 10^8-1$.
   $r_i\leftarrow q_i/10^8$ (binary64). Persist $r_i$ for S7.5/S7.6.

5. **Compute deficit (for S7.5).**
   $d\leftarrow N - \sum_i f_i$ (int32). **No clamping.**

   **Bound:** Because S7.3 guaranteed $\sum_i w_i = 1$ within $10^{-12}$, we have

   $$
   \sum_i a_i = N\quad\Rightarrow\quad
   0 \;\le\; d \;=\; \sum_i (a_i - f_i) \;=\; \sum_i u_i \;<\; m,
   $$

   hence $d\in\{0,1,\dots,m{-}1\}$. (If S7.3’s internal check had failed, S7.3 already aborted.)

**Outputs of S7.4 (in-memory, consumed by S7.5):** arrays $a,f,r$ and scalar $d$, all aligned to `country_set.rank`.

---

## Properties & error bounds (MUST hold)

* **Range & types:** $a_i\ge0$ (binary64), $f_i\in\mathbb{Z}_{\ge0}$ (int32), $r_i\in[0,1)$ (binary64 with 8-dp grid). `residual` in cache/events is constrained to $[0,1)$.
* **Quantisation error:** for $u\in[0,1)$,

  $$
  |\,r-u\,|\ \le\ 0.5\cdot 10^{-8}\ +\ O(\varepsilon_{64}),
  $$

  so distinct residuals within $\approx5\times10^{-9}$ may quantise to the same $r$ — intended; ties are broken deterministically in S7.5.
* **Mass conservation setup:** $d=N-\sum f_i$ with $0\le d < m$; S7.5’s “top-up first $d$” then ensures $\sum n_i=N$ and $|n_i-a_i|\le1$.

---

## Error handling (abort conditions)

* `ERR_S7_4_NEG_WEIGHT_OR_NAN`: any $w_i\notin[0,1]$ or NaN/Inf (should be impossible if S7.3 passed).
* `ERR_S7_4_ALLOC_NAN_INF`: any $a_i$ is NaN/Inf (binary64).
* `ERR_S7_4_FLOOR_RANGE`: $f_i<  0$ or $f_i > \texttt{INT32_MAX}$.
* `ERR_S7_4_DEFICIT_RANGE`: computed $d\notin[0,m-1]$ (should be impossible if S7.3 passed).
* `ERR_S7_4_RESIDUAL_RANGE`: some $r_i\notin[0,1)$ after quantisation (guarded by the `q_i==10^8` clamp).

Any such failure is **structural**; S9 MUST refuse `_passed.flag` and 1B cannot proceed.

---

## Invariants (MUST hold)

1. Arrays $a,f,r$ are **index-aligned** with `country_set.rank` (0..$m{-}1$).
2. $r_i$ is exactly an 8-dp decimal gridpoint; event/cache schemas constrain `residual∈[0,1)`.
3. No RNG is consumed in S7.4 (hence no envelope deltas here); `residual_rank` events are emitted later, each with `draws=0`.

---

## Reference pseudocode (deterministic; binary64; FMA-off)

```pseudo
function s7_4_alloc_and_residuals(N:int32, w[0..m-1]:float64, C:list[ISO2]) 
  -> (a[0..m-1]:float64, f[0..m-1]:int32, r[0..m-1]:float64, d:int32):

    assert m == len(C) == len(w) and m >= 1
    a := array<float64>(m)
    f := array<int32>(m)
    r := array<float64>(m)

    # 1) m=1 early case
    if m == 1:
        a[0] = float64(N); f[0] = N; r[0] = 0.0
        d = 0
        return (a,f,r,d)

    # 2–4) compute a, floors, quantised residuals (rank order)
    sum_f := 0
    for i in 0..m-1:
        ai := float64(N) * w[i]          # single multiply; no FMA
        fi := floor(ai)                   # int32
        ui := ai - float64(fi)           # in [0,1)
        qi := roundToEven(1e8 * ui)      # int64 nearest, ties-to-even
        if qi == 100000000:              # enforce residual < 1.0
            qi = 99999999
        ri := float64(qi) / 1e8

        a[i] = ai; f[i] = int32(fi); r[i] = ri
        sum_f += f[i]

    d := N - sum_f                        # 0 <= d < m   (proof above)
    if d < 0 or d >= m: abort("ERR_S7_4_DEFICIT_RANGE")

    return (a,f,r,d)
```

---

## Conformance tests

1. **m=1 path.** $N=17$, any $w=[1]$ → $a=[17], f=[17], r=[0], d=0$. Also expect exactly **one** `residual_rank` in S7.5 with `residual=0.0, residual_rank=1`.
2. **Near-integer $a_i$.** Choose $N,w$ with $a_j=3.0000000000001$ (bin64) → $f_j=3$, $u_j\approx1\text{e-}13$, $r_j=0.00000000$. (Will only top-up if needed by $d$ and earlier keys.)
3. **Half-ULP near 1.** Construct $u=0.999999995$ (or closest bin64) → $q=$ round-to-even $\approx 100000000$; clamp enforces $r=0.99999999\in[0,1)$.
4. **Quantisation tie.** Two residuals differ by $ < 5\times10^{-9}$ → identical $r$; S7.5 must then decide by `(country_set.rank, ISO)` stable keys.
5. **Deficit bound.** Random $w,N$ with $m\in\{2,\dots,20\}$; verify $0\le d < m$ and $d = N - \sum f_i$ equals $\sum r^{\text{raw}}_i$ rounded to nearest with ties-to-even at 0 dp (diagnostic only).
6. **Schema range.** Feed $r_i$ into `ranking_residual_cache_1A` mock schema; ensure $[0,1)$ holds; reject any $r_i=1.0$.

---

## Where this hands off

S7.5 will **rank** indices by the stable key
$(r_i\ \downarrow,\ \texttt{country_set.rank}\ \uparrow,\ \text{ISO}\ \uparrow)$, take the first $d$ to receive $+1$, emit **one** `residual_rank` event **per country** (`draws=0`), and thereby obtain final integers $n_i$ with $\sum n_i=N$ and $|n_i-a_i|\le1$. The quantised $r_i$ here are the **only** residuals used for that ordering and later persisted to `ranking_residual_cache_1A`.

---

# S7.5 — Largest-remainder integerisation & residual-rank events

## Scope & purpose

Given the arrays from **S7.4**—real allocations $a$, integer floors $f$, quantised residuals $r\in[0,1)$ at **exactly 8 dp**, and the deficit $d\in\{0,\dots,m{-}1\}$—deterministically select the $d$ countries to receive the top-up $+1$ using a **stable, schema-aligned order key**. Emit **one `residual_rank` RNG event per country** (with `draws=0`), and persist `residual` + `residual_rank` to **`ranking_residual_cache_1A`** (parameter-scoped). `country_set` remains the **only** authority for country membership & order; S7 never mutates it.

---

## Inputs (MUST)

* Ordered **country set** $C=(c_0,\dots,c_{m-1})$ with `country_set.rank(c_i)=i` (0 = home; foreigns in S6 Gumbel order). No duplicates; ISO-2 uppercase.
* From **S7.4** (aligned index-for-index with $C$):
  $a=(a_0,\dots,a_{m-1})\in\mathbb{R}_{64}^{m}$, $f=(f_0,\dots,f_{m-1})\in\mathbb{Z}^{m}_{\ge0}$, $r=(r_0,\dots,r_{m-1})\in[0,1)^m$ (each $r_i$ is **8-dp**), and $d=N-\sum_i f_i \in \{0,\dots,m{-}1\}$.
* Lineage tuple for event partitioning: `seed`, `parameter_hash`, `run_id`, plus `manifest_fingerprint` in the envelope.

---

## Numeric environment & determinism (normative)

* IEEE-754 **binary64**; **no FMA** anywhere ordering/rounding affects branching.
* Sorting is **stable** and performed over an explicit tuple key (below); no locale-dependent collation.
* No RNG is consumed in this sub-state; all `residual_rank` events must log `draws=0` with `after==before`.

---

## Ordering key (normative)

Let `ISO(c_i)` be the 2-letter code and `rank(c_i)` the integer rank from `country_set`. Define, for each index $i\in\{0,\dots,m-1\}$, the total order key:

$$
\mathbf{k}(i)\;=\;\big(-r_i,\ \texttt{rank}(c_i),\ \text{ISO}(c_i)\big),
$$

i.e., **descending** residual (using the **quantised 8-dp** $r_i$), then **ascending** `country_set.rank`, then **ascending** ISO. The second key **must** be `country_set.rank` (preserves S6’s Gumbel order as the prior); ISO is only the tertiary tie-break.

> Rationale in authority policy: `residual_rank` is *not* `site_order`; inter-country order is kept **only** in `country_set.rank` and must be used ahead of ISO when breaking ties.

---

## Algorithm (normative)

1. **Build permutation.**
   Compute a **stable sort** of indices $0..m{-}1$ by key $\mathbf{k}(i)$ to obtain the order vector $\pi=(\pi_1,\dots,\pi_m)$ where $\pi_1$ is the largest (by $r$, then `rank`, then ISO).

2. **Top-up set.**
   Let $T=\{\pi_1,\dots,\pi_d\}$ be the set of the first $d$ indices (empty if $d=0$).

3. **Final integers.**
   For each $i$, set

   $$
   n_i \;=\;
   \begin{cases}
   f_i+1, & i\in T,\\[2pt]
   f_i,   & i\notin T.
   \end{cases}
   $$

   Then $\sum_i n_i=N$, $n_i\in\mathbb{Z}_{\ge0}$, and $|n_i-a_i|\le 1$ for all $i$. The engine **must** assert these properties.

4. **Emit `residual_rank` events (exactly $m$).**
   For each position $t\in\{1,\dots,m\}$ with index $i=\pi_t$, emit one JSONL event under:

   ```
   logs/rng/events/residual_rank/
     seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
   schema_ref: schemas.layer1.yaml#/rng/events/residual_rank
   produced_by: 1A.integerisation
   ```

   **Envelope (must fields):** `{ seed, parameter_hash, manifest_fingerprint, run_id, module, label="residual_rank", counter_before_hi, counter_before_lo, counter_after_hi, counter_after_lo, draws=0, ts }`.
   **Payload (per country):** `{ merchant_id, country_iso=ISO(c_i), residual=r_i (8 dp), residual_rank=t }`.
   **Counters:** `after==before` (128-bit equality) since `draws=0`. A companion `rng_trace_log` row records the zero-draw emission.

   *Jump records.* If your engine writes explicit `stream_jump` records when switching sub-streams, the corresponding `logs/rng/events/stream_jump/...` entries **may** be written before the first residual-rank event; they do not consume draws and are validated separately.

5. **Persist residuals (hand-off to S7.6).**
   For each $i$, write one row to **`ranking_residual_cache_1A`**:

   ```
   data/layer1/1A/ranking_residual_cache_1A/
     seed={seed}/parameter_hash={parameter_hash}/
   schema_ref: schemas.1A.yaml#/alloc/ranking_residual_cache
   produced_by: 1A.integerise_allocations
   PK: (merchant_id, country_iso)  |  Columns: { manifest_fingerprint, merchant_id, country_iso, residual (8 dp), residual_rank (int32≥1), ... }
   ```

   This dataset is **parameter-scoped** (partitioned by `{seed, parameter_hash}`) and exists to **materialise** the tie-break outcomes so downstream processes and validators never have to re-derive floating-point minutiae.

---

## Error handling (abort semantics)

Abort S7 (structural failure) if any of the following occurs:

* `ERR_S7_5_DEFICIT_RANGE`: $d\notin[0,m-1]$ (should have been guaranteed by S7.4).
* `ERR_S7_5_SORT_STABILITY`: sort produced a permutation not of $0..m{-}1$ or is non-stable under equal keys.
* `ERR_S7_5_MASS_MISMATCH`: $\sum_i n_i\neq N$.
* `ERR_S7_5_BOUNDS`: some $n_i<0$ or $|n_i-a_i|>1$.
* `E-S7.5-RNG-COUNTERS`: any `residual_rank` event has `draws≠0` or `after≠before`.
* `E-S7.5-CACHE-SCHEMA`: cache row violates schema/range (e.g., `residual∉[0,1)`, `residual_rank<1`), or PK duplicates within `{seed, parameter_hash}`.

Any such failure **blocks** S9’s `_passed.flag`, and 1B **must not** read `outlet_catalogue` for that fingerprint (per the consumption gate).

---

## Invariants (MUST hold)

1. **Stable order key:** sort by $(r\downarrow,\ \texttt{country_set.rank}\uparrow,\ \text{ISO}\uparrow)$ with $r$ at **8 dp**.
2. **Event counts:** per merchant, **exactly** $|C|$ `residual_rank` events; plus the one `dirichlet_gamma_vector` event iff $|C|>1$. Paths and schema refs are fixed.
3. **No RNG consumption:** all residual-rank events have `draws=0` and `after==before`. A `rng_trace_log` record mirrors the zero-draw fact.
4. **Cache contract:** `ranking_residual_cache_1A` partitioned by `{seed, parameter_hash}`; PK `(merchant_id,country_iso)`; residual in $[0,1)$; rank in $\mathbb{Z}_{\ge1}$.
5. **Country-order authority:** `country_set` is not mutated; any consumer that needs inter-country order must join `country_set.rank`. Egress never encodes inter-country order.

---

## Reference pseudocode (deterministic; stable sort)

```pseudo
function s7_5_integerise(C, f[0..m-1], r[0..m-1], d:int32, lineage):
    # Preconditions: arrays aligned to country_set.rank; r are 8-dp; 0 <= d < m

    # 1) Build stable order by key (-r, rank, ISO)
    idx := [0,1,...,m-1]
    stable_sort(idx, key = (-r[i], country_set.rank(C[i]), ISO(C[i])))

    # 2) Top-up set
    T := set(idx[0:d])   # empty if d=0

    # 3) Final integers
    n := array<int32>(m)
    for i in 0..m-1:
        n[i] = f[i] + (i in T ? 1 : 0)

    assert sum(n) == N and min(n) >= 0
    for i in 0..m-1: assert abs(float64(n[i]) - a[i]) <= 1.0

    # 4) Emit exactly m residual_rank events (draws=0)
    for t in 1..m:
        i := idx[t-1]
        env_before := keyed_counter_before(lineage, label="residual_rank")  # same label for all, zero-draw
        env_after  := env_before                                           # draws = 0
        write_jsonl("logs/rng/events/residual_rank/seed=.../parameter_hash=.../run_id=...",
            envelope = { seed, parameter_hash, manifest_fingerprint, run_id,
                         module:"1A.integerisation", label:"residual_rank",
                         counter_before_hi, counter_before_lo,
                         counter_after_hi,  counter_after_lo,
                         draws:0, ts:now() },
            payload  = { merchant_id, country_iso: ISO(C[i]), residual: r[i], residual_rank: t })

    # 5) Persist residual cache rows (S7.6 handles I/O details)
    # (merchant_id, country_iso, residual, residual_rank, manifest_fingerprint)

    return n, idx  # n for S7.6->S8; idx encodes residual order for events/cache
```

---

## Conformance tests

1. **Tie cascade test.** Construct $r$ where multiple countries share the same 8-dp residual; verify sorting uses `rank` before ISO; then ISO breaks remaining ties; ensure the same order across platforms.
2. **Mass & bound checks.** Randomised $w$, $N$, $m\le 20$ → assert $\sum n=N$ and $|n_i-a_i|\le 1$; fail if any $n_i<0$.
3. **Event cardinality & counters.** For $m=1$: expect **one** `residual_rank` event with residual $0.0$, rank $1$, `draws=0`. For $m>1$: expect **exactly $m$** events, each `draws=0` and `after==before`; aggregate matches per-merchant counts in `rng_trace_log`.
4. **Cache schema & PK.** Write $m$ rows into `ranking_residual_cache_1A` under `{seed, parameter_hash}`; enforce PK `(merchant_id,country_iso)` and `residual∈[0,1)`, `residual_rank≥1`.
5. **Country-set authority.** Mutate order externally and re-run only S7.5: validator must fail because residual-rank events and cache rows must align with the original `country_set.rank`.
6. **Worked micro-example match.** Use the example $N=7$, $C=(\text{US},\text{GB},\text{DE})$, $w=(0.52,0.28,0.20)$ → verify $n=(4,2,1)$ and emitted ranks `(GB,1)`, `(US,2)`, `(DE,3)`.

---

## Notes & hand-off

* **What S7.6 persists:** the `ranking_residual_cache_1A` rows produced here (residuals + ranks), using the dictionary’s path and schema.
* **What S8 consumes:** only the **final integers $n_i$** and `country_set` order; S8 will *not* encode inter-country order in egress (that contract is enforced by schema & policy).

That fully pins the integerisation step: stable, platform-proof ordering; exact event & cache outputs; mass and error bounds enforced; and unambiguous contracts to S7.6/S8/S9.

---

# S7.6 — Persist `ranking_residual_cache_1A` (parameter-scoped)

## Scope & purpose

Take the outputs of S7.5 — for a fixed merchant with ordered `country_set` $C=(c_0,\dots,c_{m-1})$, the **quantised residuals** $r_i\in[0,1)$ at **8 dp** and their **residual ranks** $t_i\in\{1,\dots,m\}$ (where $t_i=1$ means largest by the S7.5 key) — and **materialise** one row per $(\texttt{merchant_id}, \texttt{country_iso})$ into the cache dataset **`ranking_residual_cache_1A`**.
This cache makes S7’s largest-remainder ordering reproducible without re-deriving floating-point minutiae. It is **parameter-scoped** (partitioned by `{seed, parameter_hash}`, not fingerprint-scoped).

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

This dataset version is `{parameter_hash}` and is seed-partitioned.

**Schema (JSON-Schema excerpt):**

* **Primary key:** `["merchant_id","country_iso"]`
* **Partition keys:** `["seed","parameter_hash"]`
* **Columns (required):**

  * `manifest_fingerprint: string` (hex64, lowercase)
  * `merchant_id: id64`
  * `country_iso: ISO-3166-1 alpha-2` (FK to canonical ISO dataset)
  * `residual: float64` with `minimum: 0.0`, `exclusiveMaximum: true` at `1.0`
  * `residual_rank: int32` (`1 = largest`)

**Authority policy (naming & semantics):**

* `residual_rank` is **integerisation order** (largest-remainder rank), **distinct** from `site_order`.
* Inter-country order is **not** encoded in egress; consumers must use `country_set.rank`.

---

## Inputs (MUST)

For each merchant $m$:

* `country_set` rows for $m$ (sole authority for membership and order; ISO must be unique).
* Arrays from S7.5 aligned to `country_set.rank`:
  $r=(r_0,\dots,r_{m-1})\in[0,1)^m$ (each at **8 dp** by S7.4) and $t=(t_0,\dots,t_{m-1})\in\{1,\dots,m\}^m$ (a **permutation**).
* Lineage tuple: `seed`, `parameter_hash`, `manifest_fingerprint`.

---

## Normative requirements (what MUST be written)

For every index $i$ (rank $i$ in `country_set`), write **exactly one** row:

```
{ manifest_fingerprint, merchant_id, country_iso = ISO(c_i),
  residual = r_i, residual_rank = t_i }
```

into:

```
data/layer1/1A/ranking_residual_cache_1A/
  seed={seed}/parameter_hash={parameter_hash}/part-*.parquet
```

Subject to the schema above (PK, FK, ranges).

---

## Numeric & determinism policy

* `residual` values **come from S7.4’s quantiser** $Q_8$ (computed as `roundToEven(1e8*u)/1e8` then clamped to `<1.0`), but are stored as **float64** per schema.
* For downstream reproducibility, **do not recompute** $r_i$ here; write the exact value produced in S7.4.
* No RNG is consumed in S7.6. File write order is unconstrained by schema, but a stable write order (e.g., `country_set.rank` asc) is recommended for byte-stable file diffs; **not** mandatory (schema `ordering: []`).

---

## Algorithm (normative)

```pseudo
function s7_6_persist_residual_cache(merchant_id, C:list[ISO2], r[0..m-1], t[0..m-1],
                                     seed, parameter_hash, manifest_fingerprint):

  # Preconditions
  assert len(C) == len(r) == len(t) == m and m >= 1
  assert is_unique(C) and is_valid_iso2(C)        # validated by country_set
  assert all(0.0 <= r[i] and r[i] < 1.0 for i)    # schema range
  assert sort(t) == [1..m]                        # ranks are a permutation

  # Optional gridpoint check (informative, not a schema requirement):
  # r_i should be the 8-dp quantised value from S7.4; validate using a reversible mapping
  for i in 0..m-1:
      q := min(roundToEven(r[i] * 1e8), 100000000-1)     # integer candidate
      r_chk := float64(q) / 1e8
      assert ulp_distance(r[i], r_chk) <= 1              # accept within 1 ULP

  # Write rows (partitioned by seed, parameter_hash)
  for i in 0..m-1:
      write_parquet_row(
        path = "data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/",
        row  = { manifest_fingerprint, merchant_id, country_iso=C[i],
                 residual=r[i], residual_rank=t[i] })

  # Enforce primary key uniqueness within the partition
  assert_no_duplicates_pk(partition=(seed,parameter_hash), pk=("merchant_id","country_iso"))
```

Notes:

* The **gridpoint check** ensures the stored float corresponds to an **8-dp quantised** residual (tolerated at ≤1 ULP). Not a schema rule, but a recommended guard to catch accidental re-quantisation.
* PK uniqueness and FK to canonical ISO are enforced by the schema validator.

---

## Error handling (abort semantics)

Abort S7 (structural failure) if any of the following occurs:

* `E-S7.6-PK-DUP`: duplicate `(merchant_id,country_iso)` in the `{seed,parameter_hash}` partition.
* `E-S7.6-RANGE-RESIDUAL`: some `residual ∉ [0,1)` or NaN/Inf.
* `E-S7.6-RANGE-RANK`: some `residual_rank < 1` or ranks not a permutation of `1..m`.
* `E-S7.6-FK-ISO`: `country_iso` not present in canonical ISO dataset (schema FK violation).
* `E-S7.6-LINEAGE-MISSING`: any of `{seed,parameter_hash,manifest_fingerprint}` missing from context/row metadata (the first two are partitions; the last is a required column).
  Any such failure **blocks** S9’s `_passed.flag`; 1B **must not** consume `outlet_catalogue` for that fingerprint.

---

## Invariants (MUST hold)

1. **Cardinality:** per merchant, the cache contains **exactly $m$** rows (one per country in `country_set`).
2. **Key integrity:** PK uniqueness on `(merchant_id,country_iso)` in each `{seed,parameter_hash}` partition.
3. **Range & domain:** `0 ≤ residual < 1`; `residual_rank ∈ {1,..,m}`; `country_iso` is valid ISO-2 (FK).
4. **Lineage consistency:** every row carries `manifest_fingerprint` (hex64) matching the run, even though the dataset is parameter-scoped; partitions **must** be `{seed,parameter_hash}` exactly.
5. **Authority separation:** This cache **does not** encode inter-country order; that remains solely in `country_set.rank`. Egress never encodes inter-country order.

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

Partition path:
`data/layer1/1A/ranking_residual_cache_1A/seed=42/parameter_hash=3f9c...8d1a/part-00001.parquet`
(Real partitions use the run’s `seed` and `parameter_hash`.)

---

## Conformance tests

1. **Schema & PK.** Write $m$ rows for a merchant; run the JSON-Schema validator for `#/alloc/ranking_residual_cache`; assert no PK duplicates, residual in $[0,1)$, rank ≥1.
2. **Cardinality match.** For random merchants, compare row count in cache to `|country_set|` — must be equal.
3. **Gridpoint sanity.** For each row, compute $q'=\min(\text{roundToEven}(1e8\cdot\text{residual}),10^8-1)$; recompute $r' = q'/1e8$; ensure `ulp_distance(residual,r') ≤ 1`. (Catches accidental re-quantisation.)
4. **Lineage & partitions.** Ensure files live under `seed={seed}/parameter_hash={parameter_hash}` and rows contain the same `manifest_fingerprint` used elsewhere in the run.
5. **FK to ISO.** Randomly sample `country_iso` values; join to `iso3166_canonical_2024` and assert 100% match. (Schema FK).
6. **End-to-end replay check.** Recompute S7.4→S7.5 in audit mode and compare the produced `(residual,residual_rank)` to rows — byte/bit equality.
7. **Negative tests.** Inject residual `1.0` → expect schema rejection (`exclusiveMaximum: true`). Inject duplicate `(merchant_id,country_iso)` → expect PK failure.

---

## Relationship to events & to S9

* S7.6 writes the **cache**; RNG events were already emitted in S7.2 (`dirichlet_gamma_vector`, iff $m>1$) and S7.5 (`residual_rank`, exactly $m$). Paths, partitions, and schemas for those events are fixed in the dictionary.
* S9 will validate this cache against the schema and use it (with `country_set`) to re-derive and check integerisation invariants before it issues `_passed.flag` for the run’s **fingerprint**, which is the 1A→1B hand-off gate.

---

# S7.7 — RNG event set (completeness & counts)

## Scope & purpose

For a merchant with ordered `country_set` $C=(c_0,\dots,c_{m-1})$, ensure the **RNG events** emitted in S7 are:

1. **Present in the right cardinalities** per merchant,
2. **Stored under the authoritative paths/partitions/schemas**, and
3. **Reconciled** with the run-scoped RNG trace (counters & draws).

Events in scope:

* `dirichlet_gamma_vector` — **exactly one** iff $m>1$ (none if $m=1$). Path partitioned by `{seed, parameter_hash, run_id}`; schema ref `schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector`. Produced by `1A.dirichlet_allocator`.
* `residual_rank` — **exactly $m$** (even when $m=1$). Same partitions; schema ref `schemas.layer1.yaml#/rng/events/residual_rank`. Produced by `1A.integerisation`.
* The run also contains the **RNG trace** (`rng_trace_log.jsonl`) partitioned by `{seed, parameter_hash, run_id}`, schema `#/rng/core/rng_trace_log`, used to reconcile draw counts and counter deltas.

S7 **never mutates** `country_set` (the sole authority for membership & order) — this is reiterated here because cardinatity checks depend on $|C|$.

---

## Authoritative paths & partitions (normative)

* `logs/rng/events/dirichlet_gamma_vector/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (schema `#/rng/events/dirichlet_gamma_vector`).
* `logs/rng/events/residual_rank/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (schema `#/rng/events/residual_rank`).
* `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl` (schema `#/rng/core/rng_trace_log`).

Partitions must be **exactly** `["seed","parameter_hash","run_id"]` for all event/trace datasets above. Any deviation is a schema failure.

---

## Inputs (MUST)

For each merchant $m$:

* `country_set` rows (authoritative membership & order; partitioned by `{seed, parameter_hash}`).
* The event streams for the same `{seed, parameter_hash, run_id}`.
* The RNG trace for `{seed, parameter_hash, run_id}`.

Let $m=\lvert C\rvert$.

---

## Event cardinality & envelope rules (normative)

### A) Cardinality equalities (per merchant)

Define counts:

$$
\#\text{dir}(m) \equiv \text{count of dirichlet_gamma_vector events for merchant } m,
$$

$$
\#\text{res}(m) \equiv \text{count of residual_rank events for merchant } m.
$$

Then:

$$
\#\text{dir}(m) = \mathbf{1}[\,|C|>1\,],\qquad \#\text{res}(m) = |C|.
$$

Violations are **hard errors** and abort S7.7. (This is restating the locked S7 contract.)

### B) Envelope invariants (per event)

All RNG events share the standard envelope fields; for our two events:

* **Required envelope fields:**
  `{ seed, parameter_hash, manifest_fingerprint, run_id, module, label, counter_before_hi, counter_before_lo, counter_after_hi, counter_after_lo, draws }` (+ optional `ts`), subject to the respective JSON Schemas.
* **Dirichlet:** `label == "dirichlet_gamma_vector"`. Counters must satisfy
  $(\texttt{after_hi},\texttt{after_lo})=(\texttt{before_hi},\texttt{before_lo}) \oplus_{128} \texttt{draws}$.
* **Residual-rank:** `label == "residual_rank"`. `draws == 0` and **128-bit equality** `after == before` must hold. (These are “jump-only” emissions.)

### C) Payload alignment (schema-enforced)

* **Dirichlet:** arrays `country_isos`, `alpha`, `gamma_raw`, `weights` are equal-length, aligned **index-for-index** to `country_set` order; validators also re-sum weights to $\sum w=1\pm 10^{-6}$.
* **Residual-rank:** payload has `{ merchant_id, country_iso, residual, residual_rank }`; there must be **exactly one** event per `country_iso` in $C$, and `residual_rank ∈ {1,…,|C|}` with no duplicates for a merchant.

---

## Reconciliation with RNG trace (normative)

Let `rng_trace_log` contain, per module/label/merchant, a `draws` field that records the **u01 count** consumed. The following **must** hold:

1. **Dirichlet draw equality:** For each merchant with $m>1$,

$$
\texttt{draws_dir_event} \;=\; \texttt{draws_dir_trace},
$$

and both equal the **post-facto measured** counter delta `after − before` (unsigned 128-bit).

2. **Residual-rank zero-draws:** For all merchants, the sum of `draws` across their $|C|$ `residual_rank` events is **0**, and every single event shows `after==before` in the envelope. Also the trace’s entry for this label shows **0** draws.

*(We do **not** attempt to reconstruct Marsaglia–Tsang attempt counts from payloads; we strictly reconcile “declared draws” ↔ “counter deltas” ↔ “trace rows”.)*

---

## Failure modes (abort semantics)

* `E-S7.7-CNT-DIRICHLET`: merchant has $\#\text{dir}(m)\neq \mathbf{1}[|C|>1]$.
* `E-S7.7-CNT-RESIDUAL`: merchant has $\#\text{res}(m)\neq |C|$ or duplicate `country_iso` among residual-rank events.
* `E-S7.7-ENV-DELTA`: any event violates its envelope rule (dirichlet delta ≠ draws; residual-rank `draws≠0` or `after≠before`).
* `E-S7.7-TRACE-MISMATCH`: event `draws` disagree with `rng_trace_log` for the same merchant/label.
* `E-S7.7-PARTITIONS`: event files not under `{seed, parameter_hash, run_id}` or schema ref mismatched to dictionary.

Any failure **blocks** S9 from issuing `_passed.flag` for the run’s fingerprint, which is the 1A→1B consumption gate.

---

## Reference checker (deterministic)

```pseudo
function s7_7_check_events(merchant_id, C, seed, parameter_hash, run_id):
    m := len(C)

    # 1) Load per-merchant events
    D := read_events("dirichlet_gamma_vector", seed, parameter_hash, run_id, merchant_id)
    R := read_events("residual_rank",          seed, parameter_hash, run_id, merchant_id)
    T := read_trace  ("rng_trace_log",         seed, parameter_hash, run_id, merchant_id)

    # 2) Cardinality
    if m > 1: assert len(D) == 1 else assert len(D) == 0
    assert len(R) == m

    # 3) Envelopes
    for e in D:
        assert e.label == "dirichlet_gamma_vector"
        assert u128_add(e.before_hi, e.before_lo, e.draws)
               == (e.after_hi, e.after_lo)
    for e in R:
        assert e.label == "residual_rank"
        assert e.draws == 0
        assert (e.before_hi == e.after_hi) and (e.before_lo == e.after_lo)

    # 4) Payload alignment
    if m > 1:
        E := D[0].payload
        assert arrays_equal_length(E.country_isos, E.alpha, E.gamma_raw, E.weights)
        assert aligns_to_country_set(E.country_isos, C)          # index-by-index
        assert abs(serial_sum(E.weights) - 1.0) <= 1e-6
    assert set(e.payload.country_iso for e in R) == set(C)
    ranks := [e.payload.residual_rank for e in R]
    assert sorted(ranks) == [1..m]

    # 5) Trace reconciliation
    # (Assume trace aggregates by merchant+label)
    tr_dir  := T.get(label="dirichlet_gamma_vector").draws or 0
    ev_dir  := sum(e.draws for e in D)
    assert ev_dir == tr_dir

    tr_res  := T.get(label="residual_rank").draws or 0
    ev_res  := sum(e.draws for e in R)
    assert ev_res == 0 and tr_res == 0

    return OK
```

Implementation notes: `aligns_to_country_set` checks identical ordering (rank 0..$m{-}1$); the serial sum is the same reducer as used in S7.3 to avoid order/parallel drift.

---

## Invariants (MUST hold)

1. **Per-merchant event counts:** `dirichlet_gamma_vector` = $\mathbf{1}[m>1]$; `residual_rank` = $m$.
2. **Envelope arithmetic:** dirichlet `after = before ⊕ draws` (128-bit); every residual-rank has `draws=0` and `after==before`.
3. **Payload alignment:** dirichlet arrays align to `country_set`; residual-rank covers every `country_iso` in $C$ exactly once, ranks $1..m$.
4. **Trace reconciliation:** event `draws` equal the trace’s `draws` for the same merchant/label; residual-rank totals 0.
5. **Partition/schema fidelity:** paths/partitions as per dictionary; schema refs must match.

---

## Conformance tests

1. **m=1 case:** No dirichlet event; **one** residual-rank event with `draws=0` & `after==before`; trace shows `dirichlet=0`, `residual_rank=0`.
2. **m=3 case:** Exactly one dirichlet event; exactly 3 residual-rank events; dirichlet arrays length 3; weights sum to $1\pm10^{-6}$.
3. **Counter mismatch:** Tamper an event to set `draws+before ≠ after` → checker raises `E-S7.7-ENV-DELTA`.
4. **Trace mismatch:** Tamper the trace `draws` for dirichlet; checker raises `E-S7.7-TRACE-MISMATCH`.
5. **Partition drift:** Move an event file to a non-conforming path (e.g., omit `run_id`) → dictionary/schema check fails.
6. **Residual-rank duplication:** Duplicate a `country_iso` event or ranks not a permutation $1..m$ → failure `E-S7.7-CNT-RESIDUAL`.

---

## Notes & hand-off

* S7.7 is **pure validation** of S7’s RNG lineage at the event/log layer; it produces no new artefacts. Its success is a prerequisite for S9’s bundle to carry a “RNG lineage OK” marker, which the **1A→1B gate** relies on alongside schema checks.
* Optional `stream_jump` events (if your engine emits them) are governed by their own dictionary entry and schema `#/rng/events/stream_jump`; they may exist but are **not required** by S7.7 and do not consume draws.

---

# S7.8 — Internal validations (must-pass before S8)

## Scope & purpose

For each merchant $m$ with ordered `country_set` $C=(c_0,\dots,c_{m-1})$, given:

* $N\in\mathbb{Z}_{\ge1}$ (the total outlets),
* $w=(w_i)$ from S7.3,
* $a=(a_i), f=(f_i), r=(r_i)$ and $d$ from S7.4,
* final integers $n=(n_i)$ and the residual-order permutation $\pi$ from S7.5,
* and the persisted cache rows written by S7.6,

S7.8 **must** verify, deterministically and without RNG, the invariants below. If any fails, S7 **aborts** the partition and **does not** invoke S8. (S9 will later run a superset of these checks inside `validation_bundle_1A` before authorising 1B.)

---

## Inputs (per merchant, MUST)

* `country_set` subset for this merchant, in **rank order** (0 = home), unique ISO-2 codes. `country_set` is the **only** authority for inter-country order.
* Scalars/arrays produced in S7.3–S7.5: $N, w_i, a_i, f_i, r_i$ (8-dp), $d$, $n_i$, and the sort order indices $\pi$.
* The `ranking_residual_cache_1A` rows **just written** by S7.6 for this merchant (read back or held in memory pre-flush).
* RNG events from S7.2/S7.5 for this `(seed, parameter_hash, run_id)` partition (local view or stream append handle):
  `dirichlet_gamma_vector` (if $m>1$) and exactly $m$ `residual_rank` events.

---

## Numeric environment (normative)

* IEEE-754 **binary64** everywhere.
* **No FMA** in any path that affects branching/ranking (Dirichlet sum, residual quantisation).
* Deterministic **serial** reductions in `country_set.rank` order (home→foreigns). These are the same policies S9 later enforces.

---

## Deterministic helpers (normative)

**Neumaier compensated sum** in fixed order (rank ascending; ISO only as specified elsewhere):

```
sum_comp(x[0..k-1]):
  s=0.0; c=0.0
  for i=0..k-1:
    t = s + x[i]
    if abs(s) >= abs(x[i]): c += (s - t) + x[i]
    else:                   c += (x[i] - t) + s
    s = t
  return s + c
```

**8-dp residual quantiser $Q_8$** (ties-to-even; clamp to keep `<1.0`):

$$
q=\operatorname{roundToEven}(10^8 u)\in\{0,\dots,10^8\},\quad
q\leftarrow \min(q,10^8-1),\quad
Q_8(u)=q/10^8.
$$

Use $u_i = a_i - \lfloor a_i\rfloor\in[0,1)$. The **integer** $q$ is the normative ranking surrogate; `r_i` stored/compared is $q/10^8$.

---

## Invariants (MUST hold)

We number the merchant-local checks **I-1…I-10** (all must pass).

**I-1 — Alignment & lengths.**
Arrays $w, a, f, r, n$ have equal length $m=|C|\ge1$; indices align to `country_set.rank`. ISO codes unique.

**I-2 — Dirichlet weight normalisation.**
With $S=\texttt{sum_comp}(G)$ from S7.2 and $w_i=G_i/S$, recomputed $\sum w$ (same serial reducer) satisfies **internal target** $|\sum w - 1|\le 10^{-12}$; and the **event/schema guard** (for the logged `dirichlet_gamma_vector`) is $|\sum w - 1|\le 10^{-6}$. (If $m=1$, there is no Dirichlet event and $w=[1]$.)

**I-3 — Real allocations & residual quantisation are coherent.**
Recompute $a'_i=\mathrm{R}_{64}(N)\times w_i$, $f'_i=\lfloor a'_i\rfloor$, $r'_i=Q_8(a'_i-f'_i)$. Assert bitwise equality with S7.4’s `a,f` (within binary64) and exact equality of `r` gridpoints (same integers $q$).

**I-4 — Deficit range.**
$d'=N-\sum_i f'_i$ satisfies $0\le d' < m$ (and equals S7.4’s $d$).

**I-5 — Largest-remainder reproducibility.**
Sort indices by the **stable key** $(r_i\downarrow,\ \texttt{country_set.rank}\uparrow,\ \text{ISO}\uparrow)$. Let $T$ be the first $d$ indices. Check

$$
n_i \stackrel{?}{=} f_i + \mathbf{1}[\,i\in T\,],\quad
\sum_i n_i = N,\quad
|n_i - a_i|\le 1\ \forall i.
$$

(The secondary key **must be** `country_set.rank`; ISO is tertiary.)

**I-6 — Cache round-trip.**
Load the $m$ rows for this merchant from `ranking_residual_cache_1A(seed,parameter_hash)` and assert: PK uniqueness; one row per ISO in $C$; `residual ∈ [0,1)`; `residual_rank ∈ {1..m}`; and the pair $(\texttt{residual},\texttt{residual_rank})$ matches the values implied by I-5. Path & schema must match the dictionary (`…/seed={seed}/parameter_hash={parameter_hash}/`, `#/alloc/ranking_residual_cache`).

**I-7 — Event set reconciliation (local).**
Cardinalities: `dirichlet_gamma_vector` = $1$ iff $m>1$; `residual_rank` = $m$. Envelopes: dirichlet `after = before ⊕ draws` (128-bit), residual-rank `draws=0` with `after==before`. (S7.7 already checked globally; S7.8 re-asserts per merchant.)

**I-8 — Country-order authority separation.**
No attempt to encode inter-country order in egress-bound arrays; any consumer must join `country_set.rank`. (This is policy; S7 only persists `residual_rank` in the cache.)

**I-9 — Schema/partition fidelity (written artefacts).**
Any artefact already materialised by S7 (cache, events) sits under **authoritative** paths/partitions and references the correct JSON-Schema ids as per dictionary.

**I-10 — m=1 degenerate path.**
If $m=1$: $w=[1]$, $a=[N]$, $f=[N]$, $r=[0.0]$, $d=0$; **no** dirichlet event; **one** residual-rank event with `residual=0.0, residual_rank=1`; one cache row with the same values.

---

## Error handling (abort semantics)

Abort the merchant (and mark the run partition failed) with the following **hard errors**:

* `E-S7.8-LEN-ALIGN`: I-1 failed (length/alignment/ISO duplicates).
* `E-S7.8-WEIGHT-SUM-INT`: internal Dirichlet sum $|\sum w -1|>1e-12$. (Note: schema/event check is at $10^{-6}$, but internal target is stricter.)
* `E-S7.8-RECOMP-MISMATCH`: I-3 failed (any of `a,f,r` mismatch; `r` not on 8-dp grid).
* `E-S7.8-DEFICIT-RANGE`: I-4 failed (deficit not in $[0,m-1]$).
* `E-S7.8-LRR-REPLAY`: I-5 failed (integerisation not reproducible or mass not conserved).
* `E-S7.8-CACHE-CFG`: I-6 failed (schema/PK/range/path or value mismatch against cache).
* `E-S7.8-RNG-SET`: I-7 failed (cardinality/envelope invariants).
* `E-S7.8-PATH-SCHEMA`: I-9 failed (paths or schema refs not per dictionary).

Any of these **blocks** S8 and will later appear in S9’s bundle as hard-fail diagnostics; `_passed.flag` is not eligible for emission.

---

## Reference checker (deterministic; implementation-ready)

```pseudo
function s7_8_validate(merchant_id, C, N, w, a, f, r, d, n,
                       cache_rows, dir_event?, res_events[0..m-1],
                       seed, parameter_hash, run_id):

  m := len(C)
  # I-1
  assert m >= 1 and len(w)==len(a)==len(f)==len(r)==len(n)==m
  assert is_unique(C.ISO) and aligns_to_rank(C)  # 0..m-1

  # I-2 (Dirichlet normalisation)
  if m == 1:
      assert abs(w[0] - 1.0) <= 0.0 + eps
  else:
      s1 := sum_comp(w)             # Neumaier; rank order
      assert abs(s1 - 1.0) <= 1e-12 # internal target
      # Optional: load dir_event and assert |sum(weights)-1| <= 1e-6

  # I-3 (recompute a,f,r)
  for i in 0..m-1:
      ai := float64(N) * w[i]
      fi := floor(ai)
      ui := ai - fi
      qi := roundToEven(1e8 * ui)
      if qi == 100000000: qi = 99999999
      ri := float64(qi) / 1e8
      assert ulp_eq(ai, a[i]) and fi == f[i] and ri == r[i]

  # I-4 deficit
  d2 := N - sum_i f[i]
  assert 0 <= d2 and d2 < m and d2 == d

  # I-5 largest-remainder replay
  idx := [0..m-1]
  # stable sort by (-r[i], rank(C[i]), ISO(C[i]))
  stable_sort(idx, key = (-r[i], rank(C[i]), ISO(C[i])))
  T := set(idx[0:d])
  sum_n := 0
  for i in 0..m-1:
      expect := f[i] + (i in T ? 1 : 0)
      assert n[i] == expect and abs(float64(n[i]) - a[i]) <= 1.0
      sum_n += n[i]
  assert sum_n == N

  # I-6 cache
  rows := cache_rows.for_merchant(merchant_id)  # from ranking_residual_cache_1A
  assert len(rows) == m
  assert pk_unique(rows, keys=("merchant_id","country_iso"))
  for each country c_i at rank i:
      row := rows.lookup(country_iso=ISO(C[i]))
      assert row.residual == r[i] and row.residual_rank == (index_of(i in idx) + 1)
      assert 0.0 <= row.residual and row.residual < 1.0 and row.residual_rank >= 1

  # I-7 events (cardinality + envelopes)
  if m > 1:
      D := require_one(dir_event)
      assert envelope_delta(D) == D.draws   # u128
      assert arrays_align_to_country_set(D.payload.country_isos, C)
      assert abs(sum_comp(D.payload.weights) - 1.0) <= 1e-6
  else:
      assert dir_event is None

  assert len(res_events) == m
  seen_iso := {}
  for t in 1..m:
      e := res_events[t-1]
      assert e.envelope.label == "residual_rank" and e.envelope.draws == 0
      assert e.envelope.before == e.envelope.after  # u128 equality
      assert e.payload.country_iso not in seen_iso
      seen_iso.add(e.payload.country_iso)
      assert e.payload.residual_rank in [1..m]

  # I-8 & I-9 are policy/path checks (dictionary-driven)
  assert dataset_paths_ok(per_dictionary=true)
  assert no_inter_country_order_in_egress_metadata()

  return OK
```

* `arrays_align_to_country_set` must compare **index-for-index** to the current `country_set` order.
* `dataset_paths_ok` checks **partition triplets** for events (`seed,parameter_hash,run_id`) and **{seed,parameter_hash}** for the cache, using the dictionary entries.

---

## Conformance tests (suite you can automate)

1. **m=1 happy path.** Build $N=17$, $C=[\text{GB}]$, produce $n=[17]$, `r=[0.0]`. Expect: no dirichlet event; 1 residual-rank event with `draws=0`; one cache row; checker passes.
2. **Dirichlet sum guard.** Craft $G$ that makes $|\sum w - 1|=5\cdot10^{-7}$. Internal check passes? **No** — internal is $10^{-12}$. Expect `E-S7.8-WEIGHT-SUM-INT`. (Validators later accept $10^{-6}$ at the **schema** level, but S7 must pass the stricter one.)
3. **Quantiser gridpoint.** Set a residual at half-ULP near 1: $u=0.999999995$. Verify $q=10^8$ is clamped to $10^8-1$ and `r=0.99999999`. Replay equality succeeds.
4. **Tie cascade.** Make two equal `r` to 8-dp; different ranks in `country_set`; confirm secondary key (`rank`) breaks the tie before ISO; integerisation reproducible.
5. **Cache mismatch.** Corrupt one cache row (`residual_rank` off by 1). Expect `E-S7.8-CACHE-CFG`.
6. **RNG events.** Remove dirichlet event for $m=3$ → `E-S7.8-RNG-SET`. Change a residual-rank envelope so `after ≠ before` → `E-S7.8-RNG-SET`.
7. **Path/schema fidelity.** Move cache rows under a partition missing `parameter_hash` → `E-S7.8-PATH-SCHEMA`.

---

## Complexity & side-effects

* Time $O(m\log m)$ (sorting for I-5); memory $O(m)$. Typical $m$ is small (tens). No RNG consumption.
* S7.8 **produces no new datasets**. Its only side-effect is to **gate S8**: failure prevents egress write; success allows S8 to build `outlet_catalogue`.

---

## Relationship to S9 (bundle validator)

S7.8 is a **local, fail-fast** mirror of validations S9 will package into `validation_bundle_1A` (with `rng_accounting.json`, diffs, metrics, etc.). Passing S7.8 **does not** substitute S9; 1B is still gated on `_passed.flag` that cryptographically commits to S9’s bundle for the **same** fingerprint.

That fully pins S7.8: deterministic checks, precise numeric guards, cache/event reconciliation, authoritative paths/schemas, and hard-fail semantics that block S8 unless the allocation is airtight.

---

# S7.9 — Complexity, capacity & governance

## Scope

Summarise and **formalise** the per-merchant and aggregate costs of S7 (Dirichlet allocation + largest-remainder integerisation), the **I/O artefacts** it writes, and the **governance** constraints that keep runs reproducible and auditable. This extends the concise complexity noted earlier with capacity formulas and the policy knobs that S9 enforces at hand-off.

---

## 1) Asymptotics & draw budgets (per merchant)

Let $m=|C|=K+1$ be the number of countries in `country_set` (home + $K$ foreign). Work units:

* **Gamma/Dirichlet:** draw $G_i\sim\Gamma(\alpha_i,1)$ independently and normalise.
  **Time:** $T_\gamma(m)=\Theta(m)$. **Space:** $S_\gamma(m)=\Theta(m)$ for arrays $(G,w)$.

* **Integerisation (LRR):** floors + residuals in $\Theta(m)$; sorting by key $(r_i\downarrow,\ \text{ISO}\uparrow)$ is $T_{\text{sort}}(m)=\Theta(m\log m)$. **Space:** $\Theta(m)$. The post-sort top-up of $d\in[0,m-1]$ entries is linear. **Overall per merchant:** $\Theta(m\log m)$ time, $\Theta(m)$ space. (Typical $m$ is “tens”, so sort dominates but is small.)

* **Uniform draw budget (Dirichlet only):** with Marsaglia–Tsang MT1998 and Box–Muller:

  $$
  \texttt{draws} \;=\; \sum_{i=1}^{m}\big(3\cdot\texttt{attempts}_i + \mathbf{1}[\alpha_i<1]\big),
  $$

  i.e., **3 uniforms per attempt** for $\alpha_i\ge 1$, plus **1** extra uniform for the power step when $\alpha_i<1$. This total is recorded in the `dirichlet_gamma_vector` event envelope and reconciled against `rng_trace_log` by S9.

**Determinism requirements that affect complexity:** all ordering-sensitive arithmetic (Dirichlet normalisation; residual quantisation & sort keys) is **binary64**, **serial** reductions, **FMA disabled** — this forbids BLAS/GPU parallel reductions on those paths. Parallelism is therefore by **merchant**, not within a merchant’s ordering-sensitive loops.

---

## 2) Aggregate capacity model (batch)

Let $\mathcal{M}$ be the merchant set and $m_j=|C_j|$. Then:

* **CPU time (dominant terms):**

  $$
  T_{\text{batch}}\;=\;\sum_{j\in\mathcal{M}}\Big(\Theta(m_j) + \Theta(m_j\log m_j)\Big)\;=\;\Theta\!\Big(\sum_j m_j\log m_j\Big).
  $$

  The gamma attempt counts only affect the constant factor on the $\Theta(m_j)$ term via `draws`.

* **Peak memory:** $\max_j \Theta(m_j)$ per worker (one merchant in-flight per worker is sufficient to respect the serial-reduction policy).

* **I/O record counts (exact):** per merchant,

  * `dirichlet_gamma_vector`: **1** event iff $m>1$, else **0**.
  * `residual_rank`: **$m$** events (always).
  * `ranking_residual_cache_1A`: **$m$** rows.
    Thus **$\mathbf{1}[m>1]+2m$** persisted records across logs+cache per merchant.

---

## 3) Artefacts, partitions, retention (authoritative)

### Parameter-scoped caches (reused across fingerprints)

* **`ranking_residual_cache_1A`**
  Path: `data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/`
  Partitioning: `["seed","parameter_hash"]` • Format: Parquet • Retention: **365 days** • PII: **false**.
  Primary key: `["merchant_id","country_iso"]`. Schema id: `schemas.1A.yaml#/alloc/ranking_residual_cache`.

### Run-scoped RNG logs (per run_id)

* **`dirichlet_gamma_vector`** events: JSONL at
  `logs/rng/events/dirichlet_gamma_vector/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` • Retention: **180 days**.
* **`residual_rank`** events: JSONL at
  `logs/rng/events/residual_rank/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` • Retention: **180 days**.
* **`rng_trace_log`** (draw counters) at
  `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`.
  All three share the common RNG envelope (`before/after` 128-bit counters, `draws`, labels).

*(Egress `outlet_catalogue` is fingerprint-scoped, parquet with an “ordering” clause, and consumed by 1B only after the proof gate; noted here for governance continuity.)*

---

## 4) Execution model & concurrency (deterministic)

1. **Within-merchant:**

   * Dirichlet normalisation and residual quantisation must run as **single-thread serial** loops in `country_set.rank` order (ISO only as tertiary tiebreak) with **binary64, FMA-off**. No GPU/BLAS reductions here.

2. **Across merchants:**

   * Safe to run in parallel: every merchant has its own labelled RNG substream and its own envelopes; determinism is preserved because events & trace reconcile by `(seed, parameter_hash, run_id, label)`.

3. **Idempotence & retries:**

   * Because cache partitions are keyed by `{seed, parameter_hash}` and PK is `(merchant_id, country_iso)`, re-writes are detectable as PK duplicates; recommended practice is “write-then-atomically-commit” per partition to keep idempotent retries simple. (Schema+PK are authoritative.)

---

## 5) Determinism toggles & numeric governance (artefact-backed)

* **IEEE-754 binary64** and **FMA disabled** are explicit environment artefacts (`ieee754_binary64`, `fma_disabled`) and part of the governed run context; violating them flips the fingerprint and is grounds for validation failure. Residual rounding policy is its own artefact (`residual_quantisation_policy`: 8-dp, ties-to-even, pre-sort).

* **RNG envelope & trace:** all event schemas require the common envelope; `rng_trace_log` carries per-label `draws` and the before/after counters. S9 proves `∑events draws = trace draws` per label and that each event’s counter delta equals its `draws` (128-bit arithmetic).

---

## 6) Must-hold governance invariants

**G-1 Partition & scope fidelity.**
Parameter-scoped cache under `{seed, parameter_hash}`; run-scoped events under `{seed, parameter_hash, run_id}`; egress (later) under `{seed, fingerprint}`. Any deviation is a schema/dictionary failure.

**G-2 Authority of country order.**
Inter-country order lives **only** in `country_set.rank`. Neither `ranking_residual_cache_1A` nor egress encode cross-country sequencing; consumers **must** join `country_set`.

**G-3 Event cardinalities & envelopes.**
Per merchant: `dirichlet_gamma_vector` $=\mathbf{1}[m>1]$ and exactly $m$ `residual_rank`. Envelopes: Dirichlet `after = before ⊕ draws`; residual-rank `draws = 0` and `after==before`.

**G-4 Numeric policy.**
Binary64; serial reductions; **FMA off**; residual quantised to **8 dp before sort**; internal Dirichlet sum guard $10^{-12}$; schema/event guard $10^{-6}$.

**G-5 Validation gate for consumption.**
1B may read `outlet_catalogue(seed,fingerprint)` **iff** the folder `data/layer1/1A/validation/fingerprint={fingerprint}/` contains `validation_bundle_1A` and `_passed.flag` whose **content hash equals** `SHA256(bundle)`. This is the cryptographic proof of successful validation for the **same fingerprint**.

**G-6 Retention & licensing.**
Retention: cache **365d**, RNG events **180d**. All listed datasets are `pii: false` and `licence: Proprietary-Internal`.

---

## 7) Monitoring & CI signals (what S9 certifies)

* **Schema/keys/FK** over `country_set`, `ranking_residual_cache_1A`, `outlet_catalogue`.
* **RNG accounting:** per-label presence counts, envelope deltas vs trace, plus budget spot-checks (`/3` attempt arithmetic for gamma and the `+1` for $\alpha<1$). Results land in `rng_accounting.json`.
* **Corridor metrics:** LRR max error, ZTP acceptance, sparsity rate, (optionally) hurdle calibration — all written into the bundle and must be within configured bounds for release.

*(The dictionary contains a commented “nightly CI metrics” artefact for drift tracking; if enabled in future, it would be keyed by `run_id` and sourced from post-write validation and RNG audit.)*

---

## 8) Practical scheduling recipe (reference)

* **Shard by merchant** across workers; ensure each worker processes a merchant **atomically** through S7.1–S7.8 to a commit point.
* Inside a worker, honour the **serial** loops for (a) Dirichlet normalisation and (b) residual quantisation & sort.
* Emit events with full envelopes first (Dirichlet if $m>1$, then residual-rank $m$ times).
* Persist `ranking_residual_cache_1A` rows for the merchant; enforce PK uniqueness per `{seed, parameter_hash}` partition.
* Run the **S7.8** local validator; only on success proceed to S8 (egress build). Failures are hard-abort and will be mirrored in S9’s bundle.

---

## 9) Conformance checklist (must pass before S8/S9)

1. Paths match dictionary partitions & formats for cache and events. ✔︎
2. Event cardinalities and envelopes obey G-3 (including `draws=0` for residual-rank). ✔︎
3. Cache rows equal $m$ with PK uniqueness; `residual∈[0,1)` and integer `residual_rank∈[1..m]`. ✔︎
4. Numeric policy asserted (binary64, 8-dp pre-sort, serial sums) and recorded as environment artefacts. ✔︎
5. RNG trace reconciliation (events vs trace) clean for labels used by S7. ✔︎
6. Gate material present at hand-off (`validation_bundle_1A` + `_passed.flag` = SHA256(bundle)). ✔︎

---

That’s the complete **S7.9**: exact cost model, concurrency rules that preserve determinism, authoritative I/O/retention/partition contracts, and the governance invariants that S9 certifies before 1B is allowed to read.

---