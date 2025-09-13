# S2.1 — Scope, Preconditions, and Inputs (implementation-ready)

## 1) Scope & intent

S2 generates the **total pre-split multi-site outlet count** $N_m$ for merchants that passed the hurdle as **multi-site** in S1. It is a *stochastic* state (NB via Poisson–Gamma), but **S2.1 itself** is deterministic: it gates who enters S2 and assembles the numeric inputs needed for S2.2–S2.5. Only merchants with `is_multi=1` (per S1’s authoritative event) may enter S2; single-site merchants bypass S2 entirely.

---

## 2) Entry preconditions (MUST)

For a merchant $m$ to enter S2:

1. **Hurdle provenance.** There exists exactly one S1 event record under
   `logs/rng/events/hurdle_bernoulli/…` with the merchant key and payload containing `is_multi=true`. This is the canonical gate from S1. **Absence** or `is_multi=false` ⇒ S2 MUST NOT run for $m$. (Branch purity.)
2. **Branch purity guarantee.** For `is_multi=0`, **no S2 events** may exist for $m$ in any stream; any presence constitutes a structural failure detected by validation.
3. **Lineage anchors available.** The run exposes `run_id`, `seed`, `parameter_hash`, and `manifest_fingerprint` (used in RNG envelopes and joins). S2.1 **does not** recompute any lineage keys.

**Abort codes (preflight):**

* `ERR_S2_ENTRY_NOT_MULTI` — hurdle present but `is_multi=false`.
* `ERR_S2_ENTRY_MISSING_HURDLE` — no S1 hurdle record for $m$.
* On either, S2 is **skipped** for $m$ (no S2 emission); the global validator will also enforce branch purity.

---

## 3) Mathematical inputs (MUST)

For each $m$ that satisfies the preconditions:

### 3.1 Design vectors (from S0/S1 encoders; column order frozen)

Form the **fixed** design vectors using the frozen one-hot encoders and column dictionaries established in S0/S1 (no re-definition here):

$$
\boxed{x^{(\mu)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m)\big]^\top},\quad
\boxed{x^{(\phi)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m),\ \ln g_c\big]^\top}.
$$

* $g_c$ is the GDP-per-capita scalar for the **home country** $c=\texttt{home_country_iso}_m$; the GDP term is **excluded** from the mean and **included** in the dispersion. Its sign and magnitude are exactly those encoded in the governed $\beta_\phi$ (§3.2).

**Domain & shapes:** $\Phi_{\mathrm{mcc}},\ \Phi_{\mathrm{ch}}$ are fixed-length **one-hot blocks** (sum to 1; column order frozen by the fitting bundle). $g_c>0$ so that $\ln g_c$ is defined. *(Here and below, $\ln$ denotes the natural log.)*

**FKs (deterministic):**
`mcc_m` and `channel_sym_m` come from ingress/S0 feature prep; $g_c$ is keyed by `home_country_iso`. (S0 established these and the parameter lineage via `parameter_hash`.)

### 3.2 Coefficient vectors (governed artefacts)

Load the **approved** coefficient vectors $\beta_\mu$ and $\beta_\phi$ from governed artefacts referenced by the run’s `parameter_hash`. Concretely: NB-mean coefficients from `hurdle_coefficients.yaml` (**key:** `beta_mu`), and NB-dispersion coefficients from `nb_dispersion_coefficients.yaml` (**key:** `beta_phi`). These are the only sources used to compute $\mu_m,\phi_m$ in S2.2.

### 3.3 RNG discipline & authoritative schemas (for later S2 steps)

Pin the RNG/stream contracts that S2.3–S2.5 will rely on:

* **RNG:** Philox $2\times 64$-10 with the **shared RNG envelope** (`run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, `substream_label`, counters). Open-interval uniforms $U(0,1)$ and normals follow S0 primitives.
  The **full envelope** (including `module`, `substream_label`, `rng_counter_before_*`, `rng_counter_after_*`, `draws` as decimal u128, and `blocks` as u64) is governed by the layer schema and is the one S2.3–S2.5 will use when writing events.
  For S2 streams in 1A, the `module` literal MUST be `"1A.nb_sampler"`.

* **Event streams (authoritative, JSONL):**
  `gamma_component` (context=`"nb"`), `poisson_component` (context=`"nb"`), and `nb_final` — each with schema refs in `schemas.layer1.yaml#/rng/events/...` and paths partitioned by `{seed, parameter_hash, run_id}`. These will be **written later** (S2.3–S2.5), not in S2.1.

---

## 4) Numeric evaluation requirements (MUST)

* **Policy:** Numeric policy is **exactly S0’s** (binary64, RNE, FMA-OFF, fixed-order Neumaier dot; deterministic libm surface).
* **Sanity guards:** After exponentiation in S2.2, $\mu_m>0,\ \phi_m>0$. If either is non-finite or $\le 0$, abort for $m$ with `ERR_S2_NUMERIC_INVALID`. (S2.2 will restate this as part of the link spec; S2.1 ensures the inputs exist to compute them.)

---

## 5) Pseudocode (normative preflight & assembly)

```pseudo
# Preflight gate + input assembly; emits no RNG events (draws=0)

function s2_1_prepare_inputs(m):
    # 1) Entry gate from S1
    hb := read_hurdle_event(m)                     # select within {seed, parameter_hash, run_id}, then merchant_id=m
                                                   # and verify the in-row envelope `manifest_fingerprint`
                                                   # equals the current run's `manifest_fingerprint` (explicit lineage check).
    if hb is None:           raise ERR_S2_ENTRY_MISSING_HURDLE
    if hb.is_multi != true:  raise ERR_S2_ENTRY_NOT_MULTI   # branch purity

    # 2) Load deterministic features
    c  := ingress.home_country_iso[m]
    g  := gdp_per_capita[c]                        # > 0 (checked when loaded in S0)
    xm := [1, enc_mcc(ingress.mcc[m]), enc_ch(ingress.channel_sym[m])]   # channel_sym ∈ {CP,CNP}
    xk := [1, enc_mcc(ingress.mcc[m]), enc_ch(ingress.channel_sym[m]), ln(g)]  # ln = natural log

    # 3) Load governed coefficients (parameter-scoped by parameter_hash)
    beta_mu  := artefacts.hurdle_coefficients.beta_mu           # from hurdle_coefficients.yaml
    beta_phi := artefacts.nb_dispersion_coefficients.beta_phi   # from nb_dispersion_coefficients.yaml

    # 4) Produce the S2 context (consumed by S2.2+)
    return NBContext{
        merchant_id: m,
        x_mu: xm, x_phi: xk,
        beta_mu: beta_mu, beta_phi: beta_phi,
        lineage: {seed, parameter_hash, manifest_fingerprint, run_id}
    }
```

**Emissions:** S2.1 emits **no** event records and consumes **no** RNG draws (draws=0).

---

## 6) Invariants & MUST-NOTs (checked locally, and again by the validator)

* **I-S2.1-A (Entry determinism).** S2 only runs for merchants with an S1 hurdle record where `is_multi=true`. Any S2 event for `is_multi=false` is a **structural failure**.
* **I-S2.1-B (Inputs completeness).** $x_m^{(\mu)},\ x_m^{(\phi)},\ \beta_\mu,\ \beta_\phi$ MUST all be available (encoders used to form $x$ are the frozen S0/S1 one-hots). Missing → abort for $m$ with `ERR_S2_INPUTS_INCOMPLETE`. (The expanded doc’s validator also enforces this via schema/path checks downstream.)
* **I-S2.1-C (No persistence yet).** S2.1 MUST NOT write any of the S2 event streams nor any sidecar tables; persistence happens only in S2.3–S2.5 (events) and the state boundary in S2.9.

---

## 7) Errors & abort semantics (merchant-scoped)

* `ERR_S2_ENTRY_MISSING_HURDLE` — no S1 hurdle record for $m$.
* `ERR_S2_ENTRY_NOT_MULTI` — S1 shows `is_multi=false`.
* `ERR_S2_INPUTS_INCOMPLETE:{key}` — missing design feature or coefficient.
* `ERR_S2_NUMERIC_INVALID` — later, if $\mu$ or $\phi$ evaluate non-finite/≤0 (S2.2).
  **Effect:** For any of the above, **skip S2** for $m$ (no S2 events written). The run-level validator will additionally fail branch-purity or coverage if contradictions appear.

---

## 8) Hand-off contract to S2.2+

If S2.1 succeeds for $m$, the engine must expose an **NB context** containing:

$$
(x^{(\mu)}_m,\ x^{(\phi)}_m,\ \beta_\mu,\ \beta_\phi,\ \text{seed},\ \text{parameter_hash},\ \text{manifest_fingerprint},\ \text{run_id})
$$

for use in S2.2 (NB link evaluation), S2.3 (Gamma/Poisson samplers), and S2.4 (rejection loop). **No additional mutable state** may be consulted when sampling.

---

## 9) Conformance spot-checks (writer & validator)

* **Gate correctness:** pick a known single-site merchant (`is_multi=0`); confirm **no** S2 streams contain its key. (Structural fail otherwise.)
* **Inputs reproducibility:** recompute $x^{(\mu)},x^{(\phi)}$ for a sample of merchants and verify byte-exact equality with the values used to compute `nb_final.mu` / `nb_final.dispersion_k` later.
* **Lineage presence:** ensure the S2 context carries `(seed, parameter_hash, manifest_fingerprint, run_id)` so later events can include a consistent envelope.

# S2.2 — NB2 parameterisation (links, domains, guards)

## 1) Scope & intent

Compute the **Negative-Binomial (NB2)** parameters for merchant $m$ that passed S2.1 preflight:

$$
\boxed{\ \mu_m=\exp(\beta_\mu^\top x^{(\mu)}_m)\;>\;0\ },\qquad
\boxed{\ \phi_m=\exp(\beta_\phi^\top x^{(\phi)}_m)\;>\;0\ }.
$$

This step is **deterministic** (no RNG), yields the **mean** $\mu_m$ and **dispersion** $\phi_m$ used by S2.3–S2.5, and must be **binary64-stable** and auditable. The NB2 moments are $\mathbb{E}[N_m]=\mu_m$ and $\operatorname{Var}[N_m]=\mu_m+\mu_m^2/\phi_m$. (The $r,p$ parametrisation $r=\phi_m,\ p=\phi_m/(\phi_m+\mu_m)$ is derivational only, not persisted.)

---

## 2) Inputs (MUST)

Provided by **S2.1** and artefacts keyed by `parameter_hash`:

* **Design vectors** (from S0/S2.1):

  $$
  x^{(\mu)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m)\big]^\top,\quad
  x^{(\phi)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m),\ \ln g_c\big]^\top,
  $$

  where $g_c > 0$ is the GDP-per-capita scalar for the home ISO $c$. (NB mean **excludes** GDP; dispersion **includes** $\ln g_c$.)  
  *Notation:* $\Phi_{\mathrm{mcc}}(\cdot)$ and $\Phi_{\mathrm{ch}}(\cdot)$ denote **frozen one-hot encoder functions** from S0/S1; they are **not** the NB dispersion $\phi_m$ used below.
* **Coefficient vectors:** $\beta_\mu,\ \beta_\phi$ from governed artefacts **keyed by `parameter_hash`**:
  * `hurdle_coefficients.yaml` → key **`beta_mu`** (maps to $\beta_\mu$),
  * `nb_dispersion_coefficients.yaml` → key **`beta_phi`** (maps to $\beta_\phi$).
* **Lineage:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id` (for later event joins and partition equality).

**Preconditions (MUST):**

1. All elements of $x^{(\mu)}_m$, $x^{(\phi)}_m$, $\beta_\mu$, $\beta_\phi$ are **finite** binary64 numbers.
2. $g_c > 0$ so that $\ln g_c$ is defined.  (Here and below, $\ln$ denotes the natural log.)
3. Vector lengths match (inner products defined).

---

## 3) Algorithm (normative, deterministic)

Let $\eta^{(\mu)}_m=\beta_\mu^\top x^{(\mu)}_m$ and $\eta^{(\phi)}_m=\beta_\phi^\top x^{(\phi)}_m$.

1. **Evaluate linear predictors** in **binary64** with **FMA disabled** and **fixed-order, serial Neumaier accumulation** for dot products. Do **not** reorder summands or use non-deterministic BLAS paths; this mirrors S0’s numeric contract (binary64, RNE, FMA-OFF; deterministic libm).
2. **Exponentiate** safely in binary64:

   $$
   \mu_m=\exp\!\big(\eta^{(\mu)}_m\big),\qquad \phi_m=\exp\!\big(\eta^{(\phi)}_m\big).
   $$
3. **Numeric guards (MUST):** if either exponentiation yields **non-finite** (NaN/±Inf) or $\le 0$, raise `ERR_S2_NUMERIC_INVALID` (merchant-scoped abort). No clamping; failure is explicit.

**Notes.**
• This step **does not** create or consume RNG draws and emits **no** S2 events. $\mu_m,\phi_m$ are *handed forward* in-memory; they will be echoed byte-exactly later in `nb_final` (see §6).

---

## 4) Output contract (to S2.3–S2.5)

On success, expose the immutable NB2 context:

$$
\big(m,\ x^{(\mu)}_m,\ x^{(\phi)}_m,\ \beta_\mu,\ \beta_\phi,\ \mu_m,\ \phi_m,\ \text{seed},\ \text{parameter_hash},\ \text{manifest_fingerprint},\ \text{run_id}\big).
$$

S2.3 (Gamma/Poisson attempt), S2.4 (rejection rule), and S2.5 (finalisation) **must** use **exactly** these $\mu_m,\phi_m$ values (binary64 bit-pattern) without re-computation from different inputs.

---

## 5) Invariants (MUST)

* **I-NB2-POS:** $\mu_m > 0$ and $\phi_m > 0$.
* **I-NB2-B64:** $\mu_m,\phi_m$ are representable as IEEE-754 binary64 and remain unchanged when round-tripped through the eventual JSONL `nb_final` record. (Validator re-parses numbers and compares the binary64 bit pattern.)
* **I-NB2-SER (binding):** Producers **MUST** serialize `mu` and `dispersion_k` using the **shortest round-trip decimal for binary64** (same rule as S1; L0 helper `f64_to_json_shortest`), so that parsing yields the **exact** original bit pattern.
* **I-NB2-ECHO:** The `nb_final` payload **must echo** these exact values in fields `mu` and `dispersion_k`. Any mismatch is a structural failure at validation.

---

## 6) Downstream echo (binding reference)

When S2.5 emits the single `nb_final` event for $m$, it **MUST** include:

```
{ mu: <binary64>, dispersion_k: <binary64>, n_outlets: N_m, nb_rejections: R_m, ... }
```

with `mu == μ_m` and `dispersion_k == φ_m` as produced here. Here **$R_m$** denotes the integer **rejection tally** (number of rejected attempts), distinct from the dispersion/shape $\phi_m$. (Event schema: `schemas.layer1.yaml#/rng/events/nb_final`; partitioning `{seed, parameter_hash, run_id}` per dictionary.)

---

## 7) Errors & abort semantics (merchant-scoped)

* `ERR_S2_NUMERIC_INVALID` — any of: non-finite $\eta$; non-finite or $\le 0$ $\mu_m$ or $\phi_m$; missing/mismatched vector sizes.
  **Effect:** skip S2 for $m$ (no S2 events written); validator also checks coverage so no `nb_final` may appear for this merchant.

---

## 8) Reference pseudocode (deterministic; no RNG; no emissions)

```pseudo
function s2_2_eval_links(ctx: NBContext) -> NBContext:
    # Inputs from S2.1
    xm   := ctx.x_mu          # vector
    xk   := ctx.x_phi         # vector includes ln(gdp_pc)
    bmu  := ctx.beta_mu       # vector
    bphi := ctx.beta_phi      # vector

    # 1) Linear predictors in binary64 (fixed-order Neumaier; FMA disabled)
    eta_mu  := dot64_no_fma(bmu,  xm)      # deterministic Neumaier reduction
    eta_phi := dot64_no_fma(bphi, xk)      # deterministic Neumaier reduction

    # 2) Exponentiate safely (no clamping on overflow)
    mu  := exp64(eta_mu)
    phi := exp64(eta_phi)

    # 3) Guards
    if not isfinite(mu) or mu <= 0:   raise ERR_S2_NUMERIC_INVALID
    if not isfinite(phi) or phi <= 0: raise ERR_S2_NUMERIC_INVALID

    # 4) Hand-off; no RNG draws, no event persistence here
    ctx.mu  = mu
    ctx.phi = phi
    return ctx
```

---

## 9) Conformance tests (KATs)

**Positive (round-trip & echo).**

1. Select $m$, compute $\mu_m,\phi_m$ with high-precision reference; confirm the engine’s binary64 exactly matches and later `nb_final.mu`/`dispersion_k` numerically round-trip to the same binary64.

**Negative (guard trips).**

1. Force $\eta^{(\mu)}$ above \~709.78 (binary64 overflow threshold for `exp`) → `ERR_S2_NUMERIC_INVALID`.
2. Force $\eta^{(\phi)}\to -\infty$ via extreme negative coefficients → $\phi\to 0^+$ underflow; if non-finite or $\le 0$, error.
3. Remove GDP $g_c$ (so $\ln g_c$ undefined) or set $g_c\le 0$ in features → `ERR_S2_NUMERIC_INVALID`.

**Structural.**

1. Deliberately change coefficients between S2.2 and S2.5 echo → validator should fail `I-NB2-ECHO`.

---

## 10) Complexity

* Time: $O(d_\mu + d_\phi)$ per merchant (vector dot products).
* Memory: $O(1)$.
* This step is embarrassingly parallel across merchants.

---

# S2.3 — Poisson–Gamma construction (one attempt), samplers, substreams

## 1) Scope & intent

Given deterministic $(\mu_m,\phi_m)$ from **S2.2**, perform **one attempt** of the NB mixture:

$$
G\sim\mathrm{Gamma}(\alpha{=}\phi_m,1),\quad \lambda=(\mu_m/\phi_m)\,G,\quad K\sim\mathrm{Poisson}(\lambda).
$$

Emit exactly **one** `gamma_component` and **one** `poisson_component` event (context=`"nb"`) for this attempt, with **authoritative RNG envelope** and draw accounting.  
**Envelope must include:** `seed`, `parameter_hash`, `run_id`, `manifest_fingerprint`, `module`, `substream_label`, `ts_utc`, `rng_counter_before_hi/lo`, `rng_counter_after_hi/lo`, and per-event `blocks` (u64) and `draws` (decimal u128). Acceptance of the attempt is decided in **S2.4** (accept if $K\ge2$).

**Index semantics:** For `gamma_component`, set `index=0` for the NB mixture; for Dirichlet (elsewhere in 1A) `index=i≥1` denotes the i-th category component.

---

## 2) Mathematical foundation (normative)

**Theorem (composition).** If $G\sim\Gamma(\alpha{=}\phi_m,\text{scale}=1)$ and $K\mid G\sim\mathrm{Poisson}(\lambda{=}\tfrac{\mu_m}{\phi_m}G)$, then marginally $K\sim\mathrm{NB2}(\mu_m,\phi_m)$ with $\mathbb{E}[K]=\mu_m$, $\mathrm{Var}(K)=\mu_m+\mu_m^2/\phi_m$. (Parametrisation used in S2.2.)

---

## 3) Samplers (normative, pinned)

### 3.1 Gamma $\Gamma(\alpha,1)$ — Marsaglia–Tsang MT1998

Use the **MT1998** algorithm with **open-interval uniforms** (S0.3.4) and **Box–Muller** normals (S0.3.5). **No normal caching**. Draw budgets are **variable per attempt** (actual-use; see counters).

* **Case $\alpha\ge 1$**
  Let $d=\alpha-\frac{1}{3}$, $c=(9d)^{-1/2}$. Repeat:

  1. $Z\sim\mathcal{N}(0,1)$ (Box–Muller → **2 uniforms**).
  2. $V=(1+cZ)^3$; if $V\le0$ reject.
  3. $U\sim U(0,1)$ (**1 uniform**).
  4. Accept if $\ln U < \tfrac{1}{2}Z^2 + d - dV + d\ln V$; return $G=dV$.
     Uniform consumption (one Gamma variate): **2×J + A**, where **J≥1** is the number of MT98 iterations and **A** is the count of iterations with $V>0$ (only those iterations draw the accept-$U$).  
     If $0<\alpha<1$, add **+1** uniform for the power step $U^{1/\alpha}$.

* **Case $0 < \alpha < 1$**

  1. Draw $G'\sim\Gamma(\alpha+1,1)$ via the $\alpha\ge1$ branch (variable MT98 iterations; 2 uniforms per iteration; accept-$U$ only when $V>0$).
  2. Draw $U\sim U(0,1)$ (**1 uniform**).
  3. Return $G = G'\, U^{1/\alpha}$.
     **Additional uniform:** **+1 per variate** for the power step U^{1/α}

* **Eventing (Gamma):** emit **one** `gamma_component` with `context="nb"`; payload includes `alpha=φ_m` and `gamma_value=G`.
* **Draw accounting (per event):** for attempt $t$, $\mathrm{draws}_\gamma(t)=2J_t + A_t + \mathbf{1}[\phi_m<1]$, where $J_t\ge1$ is the number of MT1998 iterations and $A_t$ is the count of iterations with $V>0$ (only those iterations draw the accept-$U$).

### 3.2 Poisson $\mathrm{Poisson}(\lambda)$ — S0.3.7 (deterministic regimes)

Use **S0.3.7** regime split: **inversion** for $\lambda<10$; **PTRS** (Hörmann transformed-rejection) for $\lambda\ge 10$. Constants in PTRS are **normative**; they are *not* tunables. Uniform consumption is **variable** and is measured by the envelope counters. Emit `poisson_component` with `context="nb"`.

* **Inversion ($\lambda<10$)**: multiplicative $p$ until $p\le e^{-\lambda}$.
* **PTRS ($\lambda\ge10$)**: use $b=0.931+2.53\sqrt\lambda$, $a=-0.059+0.02483\,b$, $\text{inv}\alpha=1.1239+1.1328/(b-3.4)$, $v_r=0.9277-3.6224/(b-2)$; draw $u,v\sim U(0,1)$; apply the squeeze/acceptance tests from S0.3.7. 
* **Uniforms:** **variable** — each PTRS **iteration** uses 2 uniforms; the number of iterations is geometric; total per event is measured by envelope counters. 
* **Logging:** `poisson_component` with `context="nb"`.

---

## 4) RNG substreams & labels (MUST)

* **Module:** all S2 mixture emissions use `module="1A.nb_sampler"`.
* **NB substreams (disjoint from ZTP):**
  * Gamma: `substream_label="gamma_nb"`
  * Poisson: `substream_label="poisson_nb"`
* **Order per attempt:** emit exactly two component events: `gamma_component` → `poisson_component`.  
Counters advance deterministically within each `(merchant, substream_label)` stream; there is **no cross-label counter chaining**. All uniforms use S0.3.4 `u01`; all normals use Box–Muller.

---

## 5) Construction (one attempt) & event emission (normative)

Given merchant $m$ with $(\mu_m,\phi_m)$ from S2.2:

1. **Gamma step (context=`"nb"`)**
   Draw $G\sim\Gamma(\alpha{=}\phi_m,1)$ via **3.1** on `substream_label="gamma_nb"`.
   Emit:

   ```json
   {
     "merchant_id": "<m>",
     "index": 0,
     "context": "nb",
     "alpha": <phi_m as binary64>,
     "gamma_value": <G as binary64>,
     "seed": "...",
     "parameter_hash": "...",
     "run_id": "...",
     "manifest_fingerprint": "...",
     "ts_utc": "2025-01-01T00:00:00.000000Z",
     "module": "1A.nb_sampler",
     "substream_label": "gamma_nb",
     "rng_counter_before_hi": "...",
     "rng_counter_before_lo": "...",
     "rng_counter_after_hi":  "...",
     "rng_counter_after_lo":  "...",
     "blocks": 1,
     "draws": "2"
   }
   ```

   Schema (authoritative): `schemas.layer1.yaml#/rng/events/gamma_component`. **Partition:** `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...`. **Draws:** per §3.1 above.

2. **Poisson step (context=`"nb"`)**
   Compute $\lambda=\frac{\mu_m}{\phi_m}\,G$ in binary64. Draw $K\sim\mathrm{Poisson}(\lambda)$ via **3.2** on `substream_label="poisson_nb"`.
   Emit:

   ```json
   {
     "merchant_id": "<m>",
     "context": "nb",
     "lambda": <lambda as binary64>,
     "k": <K as int64>,
     "seed": "...",
     "parameter_hash": "...",
     "run_id": "...",
     "manifest_fingerprint": "...",
     "ts_utc": "2025-01-01T00:00:00.000000Z",
     "module": "1A.nb_sampler",
     "substream_label": "poisson_nb",
     "rng_counter_before_hi": "...",
     "rng_counter_before_lo": "...",
     "rng_counter_after_hi":  "...",
     "rng_counter_after_lo":  "...",
     "blocks": 1,
     "draws": "1"
   }
   ```

   Schema (authoritative): `schemas.layer1.yaml#/rng/events/poisson_component`. **Partition:** `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...`. **Draws:** variable; reconciled by envelope counters.

> **Note (types).** All floating-point payloads are **IEEE-754 binary64** and must round-trip exactly. Integers are signed 64-bit (`k≥0`).

---

## 6) Draw accounting & reconciliation (MUST)

**Trace rule (cumulative).** Persist one **trace** row per `(module, substream_label)` carrying
`blocks_total = Σ blocks_event` and `draws_total = Σ draws_event`. The stream’s 128-bit
counter span **must** satisfy `u128(last_after) − u128(first_before) = blocks_total`.
There is **no** identity deriving `draws` (or `draws_total`) from counter deltas.
Validators compare `draws_total` to the sampler budgets (Gamma/Poisson as specified),
and verify the counter-span equality for `blocks_total`. `nb_final` is non-consuming.
---

## 7) Determinism & ordering (MUST)

* **Emission cardinality:** Emit exactly one `gamma_component` (with `substream_label="gamma_nb"`, `context="nb"`) then one `poisson_component` (with `substream_label="poisson_nb"`, `context="nb"`) per attempt for the merchant (no parallelization per merchant). Both events must carry the same lineage and the authoritative RNG envelope (before/after counters; `draws` computed).
* **Label order:** Gamma **precedes** Poisson; ordering is determined solely by each event’s **envelope counter interval** (`rng_counter_before_*` → `rng_counter_after_*`). There is **no `attempt` field in the payload** for these streams.
* **Bit-replay:** For fixed $(x_m^{(\mu)},x_m^{(\phi)},\beta_\mu,\beta_\phi,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the entire $(G_t,K_t)$ attempt stream is **bit-identical** across replays. (Counter-based Philox + fixed labels + variable, actual-use budgets)
* *(Reminder)* NB substream **labels are closed**: `gamma_nb` / `poisson_nb` under `module="1A.nb_sampler"` with `context="nb"`.

---

## 8) Preconditions & guards (MUST)

* Inputs $\mu_m>0,\ \phi_m>0$ (from S2.2).
* Compute $\lambda$ in binary64; if $\lambda$ is **non-finite** or $\le0$ due to numeric error, raise `ERR_S2_NUMERIC_INVALID` (merchant-scoped abort of S2). (This is rare given $\mu,\phi>0$, but it is pinned.)

---

## 9) Reference pseudocode (one attempt; emissions included)

```pseudo
function s2_3_attempt_once(ctx: NBContext, t: int) -> AttemptRecord:
    # Inputs
    mu  := ctx.mu      # >0, binary64
    phi := ctx.phi     # >0, binary64

    # --- Gamma step on substream "gamma_nb"
    G := gamma_mt1998(alpha=phi)              # uses S0.3.4/5; variable attempts internally
    emit_gamma_component(
        merchant_id=ctx.merchant_id,
        context="nb", index=0, alpha=phi, gamma_value=G,
        envelope=substream_envelope(module="1A.nb_sampler", label="gamma_nb")
    )

    # --- Poisson step on substream "poisson_nb"
    lambda := (mu / phi) * G                  # binary64
    if not isfinite(lambda) or lambda <= 0: raise ERR_S2_NUMERIC_INVALID
    K := poisson_s0_3_7(lambda)               # regimes per S0.3.7
    emit_poisson_component(
        merchant_id=ctx.merchant_id,
        context="nb", lambda=lambda, k=K,
        envelope=substream_envelope(module="1A.nb_sampler", label="poisson_nb")
    )

    return AttemptRecord{G: G, lambda: lambda, K: K}
```

* `gamma_mt1998` implements §3.1 including α<1 power-step and **draw budgets**.
* `poisson_s0_3_7` implements §3.2 (inversion / PTRS; **normative constants**).
* `emit_*` attach the **rng envelope** with `blocks = u128(after)−u128(before)` and`draws` equal to the **actual uniforms consumed** by that event (decimal uint128 string).

---

## 10) Errors & abort semantics (merchant-scoped)

* `ERR_S2_NUMERIC_INVALID` — non-finite or $\le0$ $\lambda$.
  **Effect:** abort S2 for $m$; **no further** S2 events are emitted for that merchant (validator will also enforce coverage).

---

## 11) Conformance tests (KATs)

* **Gamma budgets.** Let `attempts` be the number of Gamma variates emitted for the merchant. For $\phi\ge1$, assert the **sum of `draws` across all `gamma_component` events for the merchant** equals $\sum_{t=1}^{\text{attempts}} \big(2 J_t + A_t\big)$; for $0<\phi<1$, assert the **sum of `draws` across all `gamma_component` events** equals $\sum_{t=1}^{\text{attempts}} \big(2 J_t + A_t + 1\big)$.
  Here $J_t$ is the number of Box–Muller iterations for attempt $t$, and $A_t$ is the number of those iterations with $V>0$ (i.e., the iterations that consume the accept-$U$). The validator recomputes $J_t$ and $A_t$ by bit-replay and compares them to the **sum of per-event `draws`** reported by `gamma_component`.
* **Poisson regimes.** Choose $\lambda=5$ (inversion) and $\lambda=50$ (PTRS); confirm `poisson_component` bit-replays and that the counters advance with variable consumption.
* **Ordering.** Verify each attempt produces **two** events in the `gamma`→`poisson` order for the same merchant and that `nb_final` (later) appears once at acceptance.

---

## 12) Complexity

* Gamma MT1998: expected constant iterations (depends on $\alpha$); per-attempt uniforms are **variable**: Box–Muller uses 2 uniforms per iteration; accept-$U$ is drawn only when $V>0$; add **+1** if $0<\alpha<1$.
* Poisson S0.3.7: inversion costs $\approx \lambda$ uniforms; PTRS has constant expected attempts but **variable** uniform consumption; budgets are measured by envelope counters.
* One attempt is $O(1)$ expected time and $O(1)$ memory.

---

## 13) Interactions (binding where stated)

* Draw budgets and counters must follow **S0.3.6**; `nb_final` (S2.5) will be **non-consuming** (`draws=0`).
* The **rejection rule** ($K\in\{0,1\}\Rightarrow$ resample) and corridor monitoring are specified in **S2.4** (do not duplicate here).

---

# S2.4 — Rejection rule (enforce multi-site $N\ge 2$)

## 1) Scope & intent

Turn the stream of NB mixture **attempts** from S2.3 into a single **accepted** domestic outlet count

$$
\boxed{\,N_m\in\{2,3,\dots\}\,}
$$

by **rejecting** any attempt whose Poisson draw is $K\in\{0,1\}$. Count deterministic retries

$$
\boxed{\,r_m\in\mathbb{N}_0\ \text{ = #rejections before acceptance}\,}.
$$

S2.4 **emits no events**; it controls acceptance and the loop. Finalisation (`nb_final`) is S2.5. Corridor checks on rejection behaviour are enforced by the validator (not here).

---

## 2) Inputs (MUST)

From prior substates:

* **Deterministic parameters:** $(\mu_m,\phi_m)$ from S2.2, already validated $(>0)$.
* **Attempt generator:** S2.3 provides an i.i.d. attempt stream; each attempt yields $(G_t,\lambda_t,K_t)$ and **logs exactly one** `gamma_component` (context=`"nb"`) **then** **one** `poisson_component` (context=`"nb"`), with the authoritative RNG envelope. S2.4 itself consumes **no RNG**.
* **Lineage envelope:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, `substream_label`, counters (for coverage checks later).

**Preconditions (MUST):** $\mu_m>0$, $\phi_m>0$; S2.3 must adhere to per-attempt cardinality (1 Gamma + 1 Poisson).

---

## 3) Acceptance process (formal, normative)

Let attempts be indexed $t=0,1,2,\dots$. For each $t$:

$$
G_t\sim\Gamma(\phi_m,1),\quad
\lambda_t=\tfrac{\mu_m}{\phi_m}G_t,\quad
K_t\sim\mathrm{Poisson}(\lambda_t)
$$

(as produced/logged by S2.3). Accept the **first** $t$ with $K_t\ge 2$, and set

$$
\boxed{\,N_m:=K_t,\quad r_m:=t\,}.
$$

If $K_t\in\{0,1\}$, **reject** and continue with the same merchant’s substreams; envelope counters advance deterministically per attempt. **No hard cap** is imposed here; drift/instability is policed by the corridor gates in validation.

---

## 4) Per-attempt acceptance probability & distribution of rejections (binding math)

Each attempt is an NB2 draw with mean $\mu_m$ and dispersion $\phi_m$. With $r=\phi_m,\,p=\frac{\phi_m}{\mu_m+\phi_m}$ (derivational), the pmf is

$$
\Pr[K=k]=\binom{k+r-1}{k}(1-p)^k\,p^r.
$$

Hence

$$
\Pr[K=0]=p^{\phi_m}=\Bigl(\tfrac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m},\quad
\Pr[K=1]=\phi_m\cdot(1-p)\,p^{\phi_m}=\phi_m\frac{\mu_m}{\mu_m+\phi_m}\Bigl(\tfrac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m}.
$$

Define the **success** (acceptance) probability per attempt

$$
\boxed{\,\alpha_m=1-\Pr[K=0]-\Pr[K=1]\,}.
$$

Then $r_m$ (the number of rejections before acceptance) is **geometric** with success probability $\alpha_m$:

$$
\Pr[r_m=r]=(1-\alpha_m)^r\alpha_m,\qquad
\mathbb{E}[r_m]=\frac{1-\alpha_m}{\alpha_m},\qquad
r_{m,q}=\Bigl\lceil\frac{\ln(1-q)}{\ln(1-\alpha_m)}\Bigr\rceil-1.
$$

(These expressions underpin the validator’s corridor metrics; they are not computed in S2.4.)

---

## 5) Event coverage & ordering (binding evidence requirements)

Although S2.4 emits nothing, acceptance **requires** the following to exist for merchant $m$ (evidence checked later):

* $\ge 1$ `gamma_component` (context=`"nb"`) **and** $\ge 1$ `poisson_component` (context=`"nb"`) with matching envelope keys **preceding** the single `nb_final` (S2.5).
* Per attempt, exactly **two** component events in order: Gamma → Poisson.
* `nb_final` is **non-consuming** (its envelope counters do **not** advance).

---

## 6) Determinism & invariants (MUST)

* **I-NB-A (bit replay).** For fixed inputs and lineage, the attempt sequence $(G_t,K_t)_{t\ge0}$, acceptance $(N_m,r_m)$, and the component event set are **bit-reproducible** across replays (Philox counters + fixed per-attempt cardinality + label-scoped substreams).
* **I-NB-B (consumption discipline).** Within each substream, envelope counter intervals are **non-overlapping** and **monotone**; `nb_final` later shows **before == after**. Exactly two component events per attempt; exactly one finalisation at acceptance.
* **I-NB-C (context correctness).** All S2 component events carry `context="nb"` (S4 uses `"ztp"`).

---

## 7) Outputs (to S2.5 and to the validator)

* **Hand-off to S2.5 (in-memory):** $(N_m,\ r_m)$ with $N_m\ge 2$. S2.5 will emit the **single** `nb_final` row echoing $\mu_m,\phi_m$ and recording `n_outlets=N_m`, `nb_rejections=r_m`.
* **Evidence for validation:** Component events as above; validator computes $\widehat{\rho}_{\text{rej}}$ (overall rejection rate), $\widehat{Q}_{0.99}$ (p99 of $r_m$), and a one-sided CUSUM trace. Breaches **abort the run** (no `_passed.flag`).

---

## 8) Failure semantics (merchant-scoped vs run-scoped)

* **Merchant-scoped numeric invalid** (should not arise here if S2.2/2.3 passed): non-finite or $\le0$ $\lambda_t$ ⇒ `ERR_S2_NUMERIC_INVALID` (skip merchant).
* **Structural/coverage failure** (run-scoped): Any `nb_final` without at least one prior `gamma_component` **and** one prior `poisson_component` with matching envelope keys; more than one `nb_final` for the same key; counter overlap/regression. Validators **abort** the run.
* **Corridor breach** (run-scoped): If overall rejection rate $>0.06$, or $p99(r_m)>3$, or the configured one-sided CUSUM gate trips, validators **abort** the run and persist metrics.

---

## 9) Reference pseudocode (language-agnostic; no RNG; no emissions)

```pseudo
# S2.4 rejection loop; S2.3 performs the draws and emits events.
# Returns (N >= 2, r = #rejections)

function s2_4_accept(mu, phi, merchant_id, lineage) -> (N, r):
    t := 0
    loop:
        # One attempt (S2.3): emits gamma_component then poisson_component
        (G, lambda, K) := s2_3_attempt_once(mu, phi, merchant_id, lineage)

        if K >= 2:
            N := K
            r := t
            return (N, r)                # S2.5 will emit nb_final(N, r, mu, phi)
        else:
            t := t + 1                   # rejection; continue loop
```

**Notes.** Attempt indices are implicit (reconstructed by alternating Gamma/Poisson events per merchant). S2.4 itself **consumes 0 RNG**, writes **no** rows.

---

## 10) Conformance tests (KATs)

1. **Coverage & ordering.** For a sample merchant, ensure the file order (or envelope counters) shows $a$ pairs of `gamma_component`→`poisson_component` followed by **one** `nb_final`; reconstruct $r_m=a-1$; verify `nb_final.nb_rejections == r_m`.
2. **Numeric consistency.** For each attempt $t$, confirm `poisson_component.lambda == (μ/φ)*gamma_value` as binary64; for the accepted attempt, confirm `nb_final.n_outlets == k` from the corresponding Poisson event.
3. **Corridor metrics.** On a synthetic run, compute overall rejection rate and empirical p99; intentionally increase low-μ merchants to trigger a breach and verify the validator aborts.

---

## 11) Complexity

Expected constant attempts (geometric). S2.4 adds **no** compute beyond control-flow; all cost is in S2.3’s samplers. Memory $O(1)$.

---

# S2.5 — Finalisation event `nb_final` (non-consuming, authoritative)

## 1) Scope & intent

Emit **one and only one** authoritative JSONL event per accepted multi-site merchant $m$ that records:

$$
\boxed{\,\mu_m>0,\ \phi_m>0,\ N_m\in\{2,3,\dots\},\ r_m\in\mathbb{N}_0\,}
$$

where $(\mu_m,\phi_m)$ come **verbatim** from S2.2 and $(N_m,r_m)$ from S2.4’s acceptance. This event is **non-consuming** (RNG counters unchanged) and is the sole persisted echo of S2’s accepted NB draw. 

---

## 2) Inputs (MUST)

* From **S2.2**: $\mu_m$, $\phi_m$ as IEEE-754 binary64, both $>0$.
* From **S2.4**: $N_m \ge 2$, $r_m \ge 0$ (integers). S2.4 has already ensured acceptance $K\ge2$.
* **RNG envelope** (from S0 infra): `ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}, blocks, draws`.  
Types: `blocks` is **uint64**; `draws` is **"uint128-dec"** (decimal string).  
For `nb_final`, **before == after** (non-consuming) ⇒ `blocks = 0`, `draws = "0"`.

---

## 3) Event stream & partitioning (normative)

Persist **exactly one row** per $(\texttt{seed},\texttt{parameter_hash},\texttt{run_id},\texttt{merchant_id})$ to:

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Schema (authoritative):** `schemas.layer1.yaml#/rng/events/nb_final`.
* **Partitions:** `["seed","parameter_hash","run_id"]` (no other partition keys).
* **Stream status:** approved, retention 180 days, consumed by `validation`. 

---

## 4) Payload (required fields & domains)

The event **MUST** carry the following payload (beyond the common envelope):

$$
\boxed{\ \{\ \texttt{merchant_id},\ \mu=\mu_m,\ \texttt{dispersion_k}=\phi_m,\ \texttt{n_outlets}=N_m,\ \texttt{nb_rejections}=r_m\ \}\ }.
$$

* `mu`, `dispersion_k`: **positive** binary64 scalars; must bit-match S2.2 outputs.
* `n_outlets`: signed 64-bit integer, **$\ge 2$**.
* `nb_rejections`: signed 64-bit integer, **$\ge 0$**.
* `context` is **not** present here (it exists on component streams); `module`/`substream_label` remain in the envelope for consistency, with **no** RNG consumption.

**Envelope constraint (non-consuming):** `rng_counter_before == rng_counter_after` (both 128-bit fields treated as a pair). The validator asserts this equality for **every** `nb_final` row.

---

## 5) Wire-format example (normative shape)

```json
{
  "merchant_id": "M12345",
  "mu": 7.0,
  "dispersion_k": 2.25,
  "n_outlets": 5,
  "nb_rejections": 1,

  "ts_utc": "2025-08-15T13:22:19.481Z",
  "seed": "00000000-0000-0000-0000-000000000042",
  "parameter_hash": "3aa1f3…c0de",
  "manifest_fingerprint": "a9c6…6f",
  "run_id": "2025-08-15T13-20-00Z",
  "module": "1A.nb_sampler",
  "substream_label": "nb_final",

  "rng_counter_before_lo": "00000002",
  "rng_counter_before_hi": "00000000",
  "rng_counter_after_lo":  "00000002",
  "rng_counter_after_hi":  "00000000",
  "blocks": 0,
  "draws": "0"
}
```

* Schema anchor: `#/rng/events/nb_final`.
* Counters unchanged → **non-consuming** evidence. 

---

## 6) Determinism & invariants (MUST)

* **I-FINAL-ECHO.** `mu` and `dispersion_k` **exactly equal** the S2.2 values (binary64). Any mismatch is a structural consistency failure.
* **I-FINAL-ACCEPT.** `n_outlets == N_m` and `nb_rejections == r_m` from S2.4; there is **exactly one** `nb_final` per merchant key; no other NB events after finalisation.
* **I-FINAL-NONCONSUME.** `rng_counter_before == rng_counter_after` (non-consuming event).
* **I-FINAL-COVERAGE.** Presence of `nb_final` **implies** ≥1 prior `gamma_component` **and** ≥1 prior `poisson_component` with matching envelope keys and `context="nb"`; validator enforces coverage & cardinality.

---

## 7) Failure semantics

* **Schema violation** (missing/typed wrong fields, absent envelope) ⇒ `schema_violation` (row-level), run fails validation.
* **Coverage gap** (final with no prior NB components) ⇒ **structural failure**, run aborts.
* **Duplicate finals** for same key ⇒ **structural failure**; validator reports duplicates and aborts.
* **Non-consumption breach** (counters differ) ⇒ **structural failure**; nb_final must not advance Philox.

---

## 8) Writer algorithm (normative; no RNG; single emission)

```pseudo
# Inputs from S2.2 and S2.4:
#   mu>0 (binary64), phi>0 (binary64), N>=2 (int64), r>=0 (int64)
#   envelope with counters and lineage; counters must already be equal.

function s2_5_emit_nb_final(m, mu, phi, N, r, envelope):
    # 0) Domain checks
    if not (isfinite(mu) and mu > 0):        raise ERR_S2_NUMERIC_INVALID
    if not (isfinite(phi) and phi > 0):      raise ERR_S2_NUMERIC_INVALID
    if not (is_integer(N) and N >= 2):       raise ERR_S2_FINAL_INVALID_N
    if not (is_integer(r) and r >= 0):       raise ERR_S2_FINAL_INVALID_R

    # 1) Non-consuming proof
    if not counters_equal(envelope.before, envelope.after):
        raise ERR_S2_FINAL_CONSUMPTION_DRIFT

    # 2) Construct payload (echo μ, φ exactly; attach in-memory N, r)
    payload := {
        merchant_id: m,
        mu: mu, dispersion_k: phi,
        n_outlets: N, nb_rejections: r
    }

    # 3) Persist one JSONL row to the nb_final stream (dictionary path/partitions)
    emit_event(
        stream="nb_final", schema="#/rng/events/nb_final",
        partition_keys={seed, parameter_hash, run_id},
        envelope=envelope, payload=payload
    )

    # 4) Return (no further S2 emissions)
    return
```

* Emission count: **exactly one** per merchant; **no RNG draws** consumed.

---

## 9) Validator joins & downstream usage (binding)

* **Joins:** Validator left-joins `nb_final` to NB **component** streams by $(\texttt{seed},\texttt{parameter_hash},\texttt{run_id},\texttt{merchant_id})$ to (i) prove coverage/cardinality, (ii) verify $\lambda_t = (\mu/\phi)\cdot\texttt{gamma_value}$ per attempt, and (iii) compute corridors (overall rejection rate, $p_{99}(r_m)$, CUSUM). On any hard failure, the validation bundle is written **without** `_passed.flag`.
* **Hand-off:** $N_m,r_m$ continue **in-memory** to S3+; S2 writes **no** Parquet/Delta tables. 

---

## 10) Conformance tests (KATs)

1. **Echo test.** For sampled merchants, recompute $\mu,\phi$ from S2.2 and assert `nb_final.mu` and `nb_final.dispersion_k` **bit-match**; fail run on mismatch.
2. **Non-consuming test.** Assert `rng_counter_before == rng_counter_after` in every `nb_final` row.
3. **Coverage & cardinality.** For every `nb_final`, assert ≥1 prior `gamma_component` and ≥1 prior `poisson_component` (`context="nb"`), and assert **exactly one** `nb_final` per key.
4. **Dictionary path test.** Ensure all `nb_final` rows appear **only** under the dictionary path/partitions & schema anchor.
5. **No side-effects.** Confirm S2 does **not** emit any Parquet data products; only the three JSONL streams exist (Gamma, Poisson, Final).

---

## 11) Complexity

O(1) time and memory per merchant (field checks + single JSONL write). No RNG, no retries.

---

# S2.6 — RNG sub-streams & consumption discipline (keyed mapping; budgeted/reconciled draws)

## 1) Scope & intent

Guarantee **bit-replay** and **auditability** of the NB sampler by fixing (i) which **Philox** sub-streams are used for each NB attempt component, (ii) how **counters** advance and are exposed, and (iii) what **evidence** is emitted so the validator can prove replay and detect any consumption drift. S2.6 itself draws **no** randomness; it **governs** how S2.3/S2.4/S2.5 consume and log it.

---

## 2) Inputs & label set (must)

* **Labels (NB):** $\ell_\gamma=$ `"gamma_component"`, $\ell_\pi=$ `"poisson_component"`. Exactly these two sub-streams are used by S2 attempts; `nb_final` is **non-consuming**.
* **Schemas (authoritative):** `schemas.layer1.yaml#/rng/events/gamma_component`, `#/rng/events/poisson_component`, `#/rng/events/nb_final`. Each includes the **rng envelope** with pre/post 128-bit counters.
* **Dictionary paths/partitions:**

  * `logs/rng/events/poisson_component/...` (approved; `["seed","parameter_hash","run_id"]`),
  * `logs/rng/events/nb_final/...` (approved; same partitions).
    (Gamma stream path is pinned similarly; consumers/partitions mirror Poisson.)

---

## 3) Deterministic keyed mapping (normative)

All sub-streams are derived by the **S0.3.3 keyed mapping** from run lineage + label + merchant, order-invariant across partitions:

1. **Base counter for a (label, merchant)**

    $$
    (c^{\mathrm{base}}_{\mathrm{hi}},c^{\mathrm{base}}_{\mathrm{lo}})
    =\mathrm{split64}\!\Big(\mathrm{SHA256}\big(\text{"ctr:1A"}\,\|\,\texttt{manifest_fingerprint_bytes}\,\|\,\mathrm{LE64}(\texttt{seed})\,\|\,\ell\,\|\,\mathrm{LE64}(m)\big)[0{:}16]\Big).
    $$

2. **b-th block** for that pair uses

    $$
    (c_{\mathrm{hi}},c_{\mathrm{lo}})=(c^{\mathrm{base}}_{\mathrm{hi}},\,c^{\mathrm{base}}_{\mathrm{lo}}+b),
    $$
    
    with 64-bit carry into $c_{\mathrm{hi}}$; this block yields two lanes $(x_0,x_1)$.
    **Single-uniform events** consume $x_0$ and **discard** $x_1$ ($\texttt{blocks}=1$, $\texttt{draws}="1"$);
    **two-uniform events** (e.g., Box–Muller) consume **both** $x_0,x_1$ from the **same** block
    ($\texttt{blocks}=1$, $\texttt{draws}="2"$). Mapping is **pure** in $(\texttt{seed},\texttt{fingerprint},\ell,m,b)$.

**Envelope arithmetic (per event):**

$$
\boxed{\texttt{blocks}\;:=\;u128(\texttt{after})-u128(\texttt{before})}
$$

in **unsigned 128-bit** arithmetic. The envelope **must** carry both:
`blocks` (**uint64**) and `draws` (decimal **uint128** string).
Here `draws` records the **actual count of U(0,1)** uniforms consumed by
the event’s sampler(s) and is **independent** of the counter delta.

Examples: Box–Muller → `blocks=1`, `draws="2"`; single-uniform → `blocks=1`,
`draws="1"`; non-consuming finaliser → `blocks=0`, `draws="0"`.
---

## 4) Uniform & normal primitives (normative)

* **Open-interval uniform** (exclusive bounds):

$$
\boxed{\,u = ((x+1)\times 0x1.0000000000000p-64)\ \in (0,1)\,},\quad x\in\{0,\dots,2^{64}\!-\!1\}.
$$

The multiplier **must** be written as the **binary64 hex literal** `0x1.0000000000000p-64`
(no decimal substitutes).
**Clamp to strict open interval.** After computing `u`, perform:
`if u == 1.0: u := 0x1.fffffffffffffp-1` (i.e., \(1-2^{-53}\)).
This does not affect `blocks`/`draws`; it guarantees \(u\in(0,1)\) in binary64.

**Lane policy.** A Philox **block** yields two 64-bit lanes `(x0,x1)` then advances by **1**.
* **Single-uniform events:** use `x0`, **discard** `x1` → `blocks=1`, `draws="1"`.
* **Two-uniform events (e.g., Box–Muller):** use **both** `x0,x1` from the **same** block
→ `blocks=1`, `draws="2"`; **no caching** across events.

* **Standard normal** $Z$ via Box–Muller: exactly **2 uniforms per $Z$**; **no caching** of the sine deviate.

> **Scope rule:** All uniforms in S2 (Gamma & Poisson) **must** use this `u01`. Validators don’t log uniforms but prove discipline via counters.

---

## 5) Event cardinality & ordering (attempt-level)

For attempt index $t=0,1,2,\dots$ of merchant $m$:

* Emit **exactly one** `gamma_component` on $\ell_\gamma$ **then** **exactly one** `poisson_component` on $\ell_\pi$.
* On acceptance (first $K_t\ge2$), emit **exactly one** `nb_final` (non-consuming).
  No other NB events are allowed for that merchant.

---

## 6) Draw budgets & reconciliation (normative)

For each `(module, substream_label)`, validators reconcile **two independent totals**:
`blocks_total = Σ blocks_event` (which equals the stream’s 128-bit counter span) and
`draws_total = Σ draws_event` (which equals the uniforms implied by the sampler budgets).
No identity ties `draws` to the counter delta.
* **`gamma_component` (context="nb")**

  $$
  \text{draws} = \sum_t \left( 3 \times J_t + \mathbf{1}[\phi_m < 1] \right)
  $$
  where the sum is over NB attempts $t$ (one Gamma variate per attempt) and $J_t≥1$ is the number of MT98 internal iterations for that variate.
    
  Rationale: each MT98 iteration uses **2 uniforms** for the Box–Muller normal and **1 uniform** for the accept-$U$; when $\phi_m < 1$, add **+1 uniform per variate** for the power step $U^{1/\alpha}$.
* **`poisson_component` (context="nb")**
  **Variable** (inversion for $\lambda<10$; PTRS otherwise). Envelope counters measure actual consumption; there is **no fixed budget**.
* **`nb_final`**
  **Non-consuming**: `before == after`; `draws = 0`. (Validator enforces.)

Additionally, a run may emit **`rng_trace_log`** rows (per `(module, substream_label)`) carrying `draws` for fast aggregation; these are used by validation for reconciliation.

---

## 7) Counter discipline (interval semantics)

Within each $(m,\ell)$ stream, event intervals must be **non-overlapping and monotone**:

$$
[c^{(e)}_{\text{before}},c^{(e)}_{\text{after}}) \cap [c^{(e+1)}_{\text{before}},c^{(e+1)}_{\text{after}})=\varnothing,\quad
c^{(e+1)}_{\text{before}}\ge c^{(e)}_{\text{after}}.
$$

For `nb_final`, enforce **non-consumption** (`before == after`).

---

## 8) Validator contract (replay & discipline proof)

**Replay proof (per merchant):**

1. Collect all `gamma_component` and `poisson_component` rows for the key $(\texttt{seed},\texttt{parameter_hash},\texttt{run_id},\texttt{merchant_id})$. Enforce **monotone, non-overlapping** intervals per sub-stream.
2. Interleave by time/counter to reconstruct attempt pairs (Gamma→Poisson) and derive the first $t$ with $K_t\ge2$.
3. Join to the single `nb_final`; assert `n_outlets` and `nb_rejections` match the reconstruction; assert `mu, dispersion_k` **echo** S2.2. **Pass iff identical.**

**Discipline checks (hard):**

* **Cardinality:** exactly 1 Gamma and 1 Poisson per attempt; exactly 1 `nb_final` per merchant key.
* **Budgets:** Gamma draw totals equal $3\times$attempts $+\mathbf{1}[\phi_m<1]$; Poisson totals reconcile by counters; `nb_final` has `draws=0`.
* **Coverage:** if `nb_final` exists, there is ≥1 `gamma_component` **and** ≥1 `poisson_component` with `context="nb"` and matching envelopes.

---

## 9) Failure semantics (run-scoped unless noted)

* **Structural/counter failure** (overlap, non-monotone, or `nb_final` consumption) ⇒ validator **aborts** the run; bundle is written without `_passed.flag`.
* **Schema/coverage/cardinality failure** (missing envelope fields; missing component event; duplicate `nb_final`) ⇒ **abort**.
* **Corridor breach** (overall NB rejection rate or p99 gate tripped—defined in S2.4/S2.7) ⇒ **abort** with metrics; out of scope of S2.6 but enforced in the same validation pass.

---

## 10) Reference implementation pattern (non-allocating; per merchant)

```pseudo
# Substream state (derived, not stored):
# base_gamma, base_pois: (hi, lo) from S0.3.3; i_gamma, i_pois: u64 counters (block index)
struct Substream {
  base_hi: u64; base_lo: u64; i: u128
}

function substream_begin(s: Substream) -> (before_hi, before_lo):
    return add128((s.base_hi, s.base_lo), s.i)   # 128-bit

function substream_end(s: Substream, blocks: u128) -> (after_hi, after_lo):
    return add128((s.base_hi, s.base_lo), s.i + blocks)

# Each Philox block yields two 64-bit lanes (x0,x1); s.i advances by **1 block** per call.
# Single-uniform events use the **low lane** and **discard** the high lane; two-uniform families use **both lanes from one block**.
struct Substream { base_hi:u64; base_lo:u64; i:u128 }

# Map lane to u in (0,1) using the hex-float multiplier (Crit #5). Clamp (Crit #6) is added elsewhere.
function u01_map(x: u64) -> f64:
    u = ((x + 1) * 0x1.0000000000000p-64)
    if u == 1.0:
        u = 0x1.fffffffffffffp-1
    return u

# Advance by **one block**, return both lanes.
function philox_block(s: inout Substream) -> (x0:u64, x1:u64):
    ctr = add128((s.base_hi, s.base_lo), s.i)
    (x0, x1) = philox64x2(ctr)
    s.i += 1
    return (x0, x1)

# Two uniforms from **one** block (e.g., Box–Muller).
function u01_pair(s: inout Substream) -> (u0:f64, u1:f64, blocks_used:u128, draws_used:u128):
    (x0, x1) = philox_block(s)                   # consumes 1 block
    return (u01_map(x0), u01_map(x1), 1, 2)     # blocks=1, draws=2

# Single uniform: use **low lane** from a fresh block; **discard** the high lane.
function u01_single(s: inout Substream) -> (u:f64, blocks_used:u128, draws_used:u128):
    (x0, _x1) = philox_block(s)                  # consumes 1 block; high lane discarded
    return (u01_map(x0), 1, 1)                   # blocks=1, draws=1

# Event emission for Gamma component (per attempt):
# The sampler returns actual budgets; the emitter stamps counters independently.
function emit_gamma_component(ctx, s_gamma: inout Substream, alpha_phi: f64):
    (before_hi, before_lo) = substream_begin(s_gamma)
    (G, blocks_used, draws_used) = gamma_mt98_with_budget(alpha_phi, s_gamma)  # uses u01_single/u01_pair internally
    (after_hi,  after_lo)  = substream_end(s_gamma, blocks_used)
    assert u128((after_hi,after_lo)) - u128((before_hi,before_lo)) == blocks_used
    write_jsonl("gamma_component",
        envelope={
          ...,
          "rng_counter_before_lo": before_lo, "rng_counter_before_hi": before_hi,
          "rng_counter_after_lo":  after_lo,  "rng_counter_after_hi":  after_hi,
          "blocks": blocks_used, "draws": stringify_u128(draws_used),
          "substream_label": "gamma_component"
        },
        payload={ merchant_id, context:"nb", index:0, alpha:alpha_phi, gamma_value:G }
    )

# Poisson component is analogous, using its sampler’s (blocks_used, draws_used) and payload {lambda, k}.
# nb_final is non-consuming: before == after, blocks=0, draws="0".
```

**Notes.**
- The samplers do **not** see counters; they only call `u01(s)`; the event writer collects `draws_used` and stamps the envelope.
- For Gamma with $\phi_m < 1$, add **one** `u01(s_gamma)` for the $U^{1/\alpha}$ power step **per variate (i.e., per attempt)**, not once per merchant. Hence the total budget aggregates as **$\sum_t \left( 3 \times J_t + \mathbf{1}[\phi_m < 1] \right)$**.

---

## 11) Invariants (MUST)

* **I-NB1 (bit replay).** Fixed inputs + S0 mapping ⇒ the sequence $(G_t,K_t)_{t\ge0}$ and the accepted pair $(N_m,r_m)$ are **bit-identical** across replays.
* **I-NB3 (open-interval).** All uniforms satisfy $u\in(0,1)$.
* **I-NB4 (consumption).** Exactly two component events per attempt; one `nb_final`; downstream counters match the trace; `nb_final` non-consuming.

---

## 12) Conformance tests (KATs)

1. **Budget check (Gamma).** For a case with $\phi\ge1$ and $a$ attempts, assert `Σ draws(gamma_component) == 3a`; with $\phi<1$, assert `== 3a+1`.
2. **Variable Poisson.** Choose $\lambda=5$ (inversion) and $\lambda=50$ (PTRS); verify envelope deltas are positive, monotone, and **not** fixed.
3. **Non-consumption final.** Every `nb_final` has `before == after`.
4. **Interval discipline.** Per $(m,\ell)$, counters are **non-overlapping** and **monotone**; reconstruct attempts (Gamma→Poisson) then join to `nb_final`; fail on any deviation.
5. **Coverage.** If a `nb_final` exists, assert presence of ≥1 prior Gamma and ≥1 prior Poisson with `context="nb"`.

---

## 13) Complexity

* **Runtime:** negligible overhead beyond sampler draws (constant-time arithmetic + one JSONL write per event).
* **Memory:** $O(1)$ per merchant (two sub-streams with 128-bit indices).

---

# S2.7 — Monitoring corridors & thresholds (run gate)

## 1) Scope & intent

Compute run-level statistics of the S2 rejection process and **abort the run** if any corridor is breached. Corridors cover:

* the **overall rejection rate** across all attempts,
* the **99th percentile** of per-merchant rejections $r_m$,
* a **one-sided CUSUM** detector for upward drift in rejections relative to model-expected behaviour.

**This step consumes no RNG, writes no NB events, and is evaluated by validation** immediately after S2 completes (it may persist its own validation bundle/metrics as per your validation harness; persistence details live in the validation spec).

---

## 2) Inclusion criteria (MUST)

Only merchants with a **valid S2 finalisation** are included. Formally, define the set

$$
\mathcal{M}=\{\,m:\ \text{exactly one } \texttt{nb_final}\ \text{exists for }m\ \text{and coverage tests pass}\,\}.
$$

For each $m\in\mathcal{M}$, read from `nb_final`:

* $r_m = \texttt{nb_rejections}\in\mathbb{N}_0$,
* $N_m=\texttt{n_outlets}\in\{2,3,\dots\}$.

Merchants without `nb_final` (e.g., numeric aborts in S2.2/2.3) are **excluded** from corridor statistics but counted under separate health metrics (not part of the corridors). Coverage must already have verified ≥1 `gamma_component` and ≥1 `poisson_component` (context=`"nb"`) for each `nb_final`.

---

## 3) Per-merchant acceptance parameter $\alpha_m$ (used by CUSUM)

For each $m\in\mathcal{M}$, compute the **model-predicted** attempt acceptance probability $\alpha_m$ from the S2.2 parameters $(\mu_m,\phi_m)$ (binary64):

Let

$$
p_m=\frac{\phi_m}{\mu_m+\phi_m},\quad
q_m=1-p_m=\frac{\mu_m}{\mu_m+\phi_m}.
$$

Then the NB2 probabilities for $K=0$ and $K=1$ are

$$
P_0 = p_m^{\phi_m},\qquad
P_1 = \phi_m\,q_m\,p_m^{\phi_m}.
$$

Define

$$
\boxed{\ \alpha_m=1-P_0-P_1\ } \quad\text{(success = accept on an attempt)}.
$$

### 3.1 Numerically stable evaluation (MUST)

Evaluate in **binary64** with log-domain guards:

* $\log p_m=\log\phi_m-\log(\mu_m+\phi_m)$.
* $\log P_0=\phi_m\log p_m$; $P_0=\exp(\log P_0)$.
* $P_1 = P_0 \cdot \phi_m \cdot q_m$ (re-use $P_0$ to avoid an extra exponentiation).
* $\alpha_m = 1 - P_0 - P_1$.

**Guards:**

* If any intermediate is non-finite, or if $\alpha_m\notin(0,1]$, the merchant is flagged `ERR_S2_CORRIDOR_ALPHA_INVALID` and **excluded** from corridor statistics (still recorded under health metrics). This should not occur if S2.2 guards held; making it explicit keeps the corridor math well-posed.

---

## 4) Corridor metrics (normative)

Let $a_m = r_m+1$ be the total attempts for merchant $m$. Define $M=|\mathcal{M}|$ and totals

$$
R=\sum_{m\in\mathcal{M}} r_m,\qquad
A=\sum_{m\in\mathcal{M}} a_m = \sum_{m\in\mathcal{M}} (r_m+1).
$$

### 4.1 Overall rejection rate $\widehat{\rho}_{\text{rej}}$

$$
\boxed{\ \widehat{\rho}_{\text{rej}} = \frac{R}{A}\ } \in [0,1).
$$

Equivalently, $\widehat{\rho}_{\text{rej}} = 1 - M/A$. **MUST** be computed exactly as above (attempt-weighted).

**Threshold (hard):** $\widehat{\rho}_{\text{rej}} \le 0.06$. Exceedance ⇒ run fails.

### 4.2 99th percentile of rejections $Q_{0.99}$

Let $r_{(1)}\le \dots \le r_{(M)}$ be the ascending order. Use **nearest-rank** quantile (normative):

$$
\boxed{\ Q_{0.99} = r_{(\lceil 0.99\,M\rceil)}\ }.
$$

**Threshold (hard):** $Q_{0.99} \le 3$. Exceedance ⇒ run fails.

**Notes:**

* If $M=0$ (no merchants reached S2 final), corridors are **not evaluable**: return `ERR_S2_CORRIDOR_EMPTY` and fail the run (no evidence to assert health).
* For $M<100$, nearest-rank is still well-defined; this is intentional for determinism.

### 4.3 One-sided CUSUM for upward drift (standardised residuals)

We monitor the sequence $\{r_m\}_{m\in\mathcal{M}}$ ordered by **merchant key** (deterministic total order; e.g., ascending `merchant_id`). For each $m$, form a standardised residual against the geometric expectation implied by $\alpha_m$:

$$
\mathbb{E}[r_m] = \frac{1-\alpha_m}{\alpha_m},\qquad
\mathrm{Var}(r_m) = \frac{1-\alpha_m}{\alpha_m^2}.
$$

Define

$$
z_m = \frac{r_m - \mathbb{E}[r_m]}{\sqrt{\mathrm{Var}(r_m)}}.
$$

Let the **one-sided positive CUSUM** be

$$
S_0=0,\qquad S_t=\max\{0,\ S_{t-1} + (z_{m_t} - k)\},\quad t=1,\dots,M,
$$

with **reference value** $k>0$ and **threshold** $h>0$.

**Gate (hard):** If $\max_{1\le t\le M} S_t \ge h$ ⇒ run fails.

**Governance of $k,h$:** These are **policy parameters** (not algorithmic constants). They MUST be supplied by the validation policy artefact for the run (e.g., `validation_policy.yaml`):
`cusum.reference_k` (default 0.5), `cusum.threshold_h` (default 8.0). If absent, validation must **fail closed** (`ERR_S2_CORRIDOR_POLICY_MISSING`).

**Notes:**

* Using standardised $z_m$ accounts for heterogeneity in $\alpha_m$ across merchants.
* CUSUM is computed **once** per run over the ordered merchant sequence; there is no windowing in this spec.

---

## 5) Pass/fail logic (normative)

Compute the three statistics. The run **passes the S2 corridors** iff **all** hold:

1. $\widehat{\rho}_{\text{rej}} \le 0.06$,
2. $Q_{0.99} \le 3$,
3. $\max S_t < h$.

Else, the run **fails**: the validator **must not** write `_passed.flag` for this fingerprint; it must persist a metrics object (see §8) documenting the breach(es).

---

## 6) Numerical & data handling requirements (MUST)

* All computations are **binary64**; no integer overflow risks since $r_m$ are small.
* Sorting uses **bytewise ascending** on the merchant key (deterministic).
* Duplicate `nb_final` rows for the same key ⇒ structural failure upstream; corridors are not computed until structure is clean.
* Exclusions: merchants with invalid $\alpha_m$ (see §3.1) are **not** in $\mathcal{M}$ for corridor stats; they are reported separately.

---

## 7) Errors & abort semantics

* `ERR_S2_CORRIDOR_EMPTY` — $M=0$; corridors not evaluable. ⇒ **Fail run**.
* `ERR_S2_CORRIDOR_POLICY_MISSING` — missing $k,h$ in policy. ⇒ **Fail run**.
* `ERR_S2_CORRIDOR_ALPHA_INVALID:{m}` — bad $\alpha_m$ for merchant `m`; merchant is excluded; proceed if $M>0$.
* **Breach** of any corridor ⇒ **Fail run** with `reason ∈ {"rho_rej","p99","cusum"}` (multi-reason allowed).

---

## 8) Validator algorithm (reference; no RNG; O(M log M))

```pseudo
function s2_7_corridors(nb_finals, policy) -> Result:
    # nb_finals: iterable of records with {merchant_id, mu, phi, n_outlets, nb_rejections}
    # policy: { cusum: { reference_k: f64, threshold_h: f64 } }

    if policy.cusum is None: return FAIL(ERR_S2_CORRIDOR_POLICY_MISSING)

    # 1) Construct inclusion set with α_m
    Mset := []
    for row in nb_finals:
        m  := row.merchant_id
        r  := int64(row.nb_rejections)
        mu := f64(row.mu);  phi := f64(row.dispersion_k)
        # α_m from μ, φ (binary64), numerically stable
        p  := phi / (mu + phi)
        logP0 := phi * log(p)         # phi>0, p∈(0,1)
        P0 := exp(logP0)
        q  := 1.0 - p
        P1 := P0 * phi * q
        alpha := 1.0 - P0 - P1
        if not isfinite(alpha) or alpha <= 0.0 or alpha > 1.0:
            record_warn(ERR_S2_CORRIDOR_ALPHA_INVALID, m)
            continue
        Mset.append({m, r, alpha})

    M := len(Mset)
    if M == 0: return FAIL(ERR_S2_CORRIDOR_EMPTY)

    # 2) Overall rejection rate
    R := sum(r for each in Mset)
    A := sum(r + 1 for each in Mset)
    rho_hat := R / A

    # 3) p99 of r_m (nearest-rank)
    r_sorted := sort([r for each in Mset])           # ascending
    idx := ceil(0.99 * M)
    p99 := r_sorted[idx - 1]                         # 1-based to 0-based

    # 4) One-sided CUSUM over standardised residuals
    k := policy.cusum.reference_k     # e.g., 0.5
    h := policy.cusum.threshold_h     # e.g., 8.0
    Ms := sort(Mset by merchant_id bytes ascending)
    S := 0.0; Smax := 0.0
    for each in Ms:
        alpha := each.alpha; r := each.r
        Er := (1.0 - alpha) / alpha
        Vr := (1.0 - alpha) / (alpha * alpha)
        z  := (r - Er) / sqrt(Vr)
        S  := max(0.0, S + (z - k))
        Smax := max(Smax, S)

    # 5) Decide
    breaches := []
    if rho_hat > 0.06: breaches.append("rho_rej")
    if p99 > 3:        breaches.append("p99")
    if Smax >= h:      breaches.append("cusum")

    if breaches is empty:
        return PASS({rho_hat, p99, Smax, M, R, A})
    else:
        return FAIL({rho_hat, p99, Smax, M, R, A, breaches})
```

**Complexity:** $O(M\log M)$ due to sorting; memory $O(M)$.

---

## 9) Invariants & evidence (MUST)

* **I-S2.7-ATTEMPT:** $A=\sum_m (r_m+1)$ equals the **total count of Poisson component events** across all S2 merchants; validator **must** reconcile these tallies (attempt-weighted rate correctness).
* **I-S2.7-ECHO:** For every $m$, the `nb_final`’s `mu`/`dispersion_k` match S2.2; `n_outlets` matches acceptance in S2.4; these are preconditions for inclusion.
* **I-S2.7-ORDER:** CUSUM ordering uses a deterministic total order on merchant keys (bytewise asc.); the order MUST be recorded in the bundle to ensure reproducibility of $S_{\max}$.

---

## 10) Conformance tests (KATs)

**Determinism.**

1. Shuffle the input `nb_final` rows: $\widehat{\rho}_{\text{rej}}$ and $Q_{0.99}$ unchanged; $S_{\max}$ unchanged **iff** the order reconstruction is the same — hence the order is explicitly defined as merchant key bytes ascending.

**Threshold triggers.**
2\) Synthetic dataset with $r_m=0$ for all $m$: expect $\widehat{\rho}_{\text{rej}}=0$, $Q_{0.99}=0$, $S_{\max}=0$ ⇒ **pass**.
3\) Inject 7% of attempts as rejections uniformly (increase many $r_m$ by 1): expect $\widehat{\rho}_{\text{rej}}>0.06$ ⇒ **fail** with breach `rho_rej`.
4\) Make $1\%$ of merchants have $r_m=4$ and the rest ≤3: expect $Q_{0.99}=4$ ⇒ **fail** with breach `p99`.
5\) Create a drift scenario: progressively inflate $r_m$ above $\mathbb{E}[r_m]$ late in the ordered sequence so that $S_{\max}\ge h$ ⇒ **fail** with breach `cusum`.

**Numerical guard.**
6\) Force extreme $\mu$/$\phi$ to yield $\alpha$ near 0 or 1; verify computation remains finite; if not, those merchants are excluded and flagged `ERR_S2_CORRIDOR_ALPHA_INVALID`, but run proceeds if $M>0$.

---

## 11) Outputs

* **Pass:** Return metrics `{rho_hat, p99, Smax, M, R, A}`; the overall validation may then stamp `_passed.flag` (outside this section).
* **Fail:** Return metrics + `breaches`; the overall validation **must not** stamp `_passed.flag` and must surface the reasons.

---

# S2.8 — Failure modes (abort semantics, evidence, actions)

## 1) Scope & intent

Define **all** conditions under which the S2 NB sampler (multi-site outlet count) must **abort** (merchant-scoped) or **fail validation** (run-scoped), and the **exact evidence** required to prove and diagnose each failure. This section binds to:

* S2.1 (entry gate, inputs), S2.2 (NB2 links), S2.3 (Gamma/Poisson samplers), S2.4 (rejection loop), S2.5 (finalisation), S2.6 (RNG discipline), S2.7 (corridors).

**Authoritative streams & schema anchors** (must be used by validator):
`logs/rng/events/gamma_component/…  #/rng/events/gamma_component`
`logs/rng/events/poisson_component/…  #/rng/events/poisson_component`
`logs/rng/events/nb_final/…  #/rng/events/nb_final`  (all partitioned by `["seed","parameter_hash","run_id"]`).

---

## 2) Error classes, codes, and actions (normative)

We categorize failures as **merchant-scoped aborts** (S2 stops for that merchant; no further S2 output) and **run-scoped validation fails** (the validator **aborts the run** and does not write `_passed.flag`).

### A) Merchant-scoped aborts (during S2 execution)

**F-S2.1 — Non-finite / non-positive NB2 parameters** (S2.2)
**Condition.** $\mu_m\le 0$ or $\phi_m\le 0$, or either linear predictor/exponential is NaN/Inf in binary64.
**Code.** `ERR_S2_NUMERIC_INVALID`.
**Action.** **Abort S2 for m**; **no** S2.3 events should be emitted for that merchant.
**Evidence.** Validator recomputes $(\mu_m,\phi_m)$ from S2.1 inputs + governed artefacts (by `parameter_hash`) and flags `invalid_nb_parameters(m)`. 

**F-S2.2 — Sampler numeric invalid** (S2.3)
**Condition.** `gamma_component.alpha ≤ 0` or `gamma_value ≤ 0`, or `poisson_component.lambda ≤ 0` / non-finite. (Should not occur if S2.2 passed.)
**Code.** `ERR_S2_SAMPLER_NUMERIC_INVALID`.
**Action.** **Row-level schema failure** → merchant effectively fails; validator will abort the run (see C-class).
**Evidence.** Offending JSONL row fails `schemas.layer1.yaml` numeric/domain checks.

**F-S2.0 — Entry gate violations** (S2.1)
**Condition.** Missing S1 hurdle record or `is_multi=false` attempting to enter S2.
**Code.** `ERR_S2_ENTRY_MISSING_HURDLE` / `ERR_S2_ENTRY_NOT_MULTI`.
**Action.** **Skip S2** for the merchant; any S2 events later will be caught as structural (D-class).
**Evidence.** Hurdle stream is authoritative gate for S2.

### B) Run-scoped schema/structure/discipline failures (validator)

**C-S2.3 — Schema violation (any S2 event)**
**Condition.** Missing envelope fields; missing required payload keys; wrong `context` (`"nb"` required for Gamma/Poisson; `nb_final` has **no** `context` field); bad domains (e.g., `k<0`).
**Action.** **Hard schema failure** → **abort run**.
**Evidence.** Per-row schema checks on the three streams.

**C-S2.4 — Coverage & cardinality gap**
**Condition.** Any `nb_final` **without** at least one prior `gamma_component` **and** one prior `poisson_component` (both with `context="nb"`), or **duplicate** `nb_final` for the same `(seed, parameter_hash, run_id, merchant_id)`.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Coverage join across the three streams indicates absence/duplication. 

**C-S2.5 — Consumption discipline breach** (S2.6 invariants)
**Condition.** Any of: `after < before`; overlapping intervals within a sub-stream; `nb_final` advances counters (`before≠after`); per-attempt cardinality differs from **exactly one** Gamma + **exactly one** Poisson.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Envelope counter scans on Gamma/Poisson/Final prove the violation. 

**C-S2.6 — Composition mismatch (Gamma→Poisson)**
**Condition.** For attempt $t$:

$$
\lambda_t \stackrel{!}{=} (\mu/\phi)\cdot \texttt{gamma_value}_t
$$

with `mu, dispersion_k` taken from `nb_final`; mismatch under strict binary64 equality (or 1-ULP, per policy).
**Action.** **Consistency failure** → **abort run**.
**Evidence.** Validator pairs attempts by counters/time and checks equality.

**C-S2.8 — Partition/path misuse**
**Condition.** Any S2 event written outside its dictionary path or missing required partitions `["seed","parameter_hash","run_id"]`.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Dictionary path/partition check.

**C-S2.9 — Single-site hygiene breach (branch purity)**
**Condition.** A merchant with S1 `is_multi=0` has **any** S2 NB event.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Cross-check hurdle stream vs S2 streams; hurdle is authoritative first RNG stream. 

### C) Run-scoped corridor failures (validator, S2.7)

**D-S2.7 — Corridor breach**
**Condition.** Any of: overall rejection rate $\widehat{\rho}_{\text{rej}}>0.06$; p99 of $r_m$ exceeds 3; one-sided CUSUM exceeds threshold $h$ (policy).
**Action.** **Validation abort** → **no** `_passed.flag`; metrics & plots in bundle.
**Evidence.** `metrics.csv` + CUSUM trace in the validation bundle.

---

## 3) Consolidated error code table (normative)

| Code                              | Scope     | Trigger                                                     | Detection locus               | Action          |
|-----------------------------------|-----------|-------------------------------------------------------------|-------------------------------|-----------------|
| `ERR_S2_ENTRY_MISSING_HURDLE`     | merchant  | no hurdle record for $m$                                    | S2.1                          | skip S2 for $m$ |
| `ERR_S2_ENTRY_NOT_MULTI`          | merchant  | hurdle `is_multi=false`                                     | S2.1                          | skip S2 for $m$ |
| `ERR_S2_NUMERIC_INVALID`          | merchant  | $\mu\le0$ or $\phi\le0$ or NaN/Inf                          | S2.2 (+defensive in S2.3/2.5) | abort $m$       |
| `ERR_S2_SAMPLER_NUMERIC_INVALID`  | run (row) | gamma/poisson numeric domains violated                      | Validator (schema)            | abort run       |
| `schema_violation`                | run (row) | envelope/payload/context missing/invalid                    | Validator                     | abort run       |
| `event_coverage_gap`              | run       | `nb_final` lacks prior Gamma & Poisson; or duplicate finals | Validator                     | abort run       |
| `rng_consumption_violation`       | run       | counter overlap/regression; `nb_final` consumes             | Validator                     | abort run       |
| `composition_mismatch`            | run       | $\lambda\neq (\mu/\phi)\cdot \texttt{gamma_value}$         | Validator                     | abort run       |
| `partition_misuse`                | run       | wrong path/partitions                                       | Validator                     | abort run       |
| `branch_purity_violation`         | run       | single-site merchant has S2 events                          | Validator                     | abort run       |
| `corridor_breach:{rho,p99,cusum}` | run       | corridor thresholds trip                                    | Validator                     | abort run       |

---

## 4) Detection loci and evidence (binding)

1. **During S2** (writer-side, merchant-scoped): S2.2/S2.3/S2.5 must **raise** their errors and **avoid emitting** downstream S2 events for the merchant. (No partial S2 trails.)
2. **After S2** (validator): perform, at minimum, the following checks in order—schema, coverage/cardinality, counter discipline, composition, corridors, path partitions, branch purity. A failure in **any** step ⇒ run fails; bundle still written without `_passed.flag`. 

---

## 5) Validator reference algorithm (S2 failure screening; O(N log N))

A minimal but normative checklist appears below (expands your draft into an enforceable pass/fail).

```pseudo
function validate_S2(nb_gamma, nb_pois, nb_final, hurdle, dictionary, policy):
    # 0) Schema & path/partition checks for all three S2 streams
    for row in nb_gamma: schema_check(row, "#/rng/events/gamma_component")
    for row in nb_pois:  schema_check(row, "#/rng/events/poisson_component")
    for row in nb_final: schema_check(row, "#/rng/events/nb_final")
    assert_dictionary_paths_partitions({nb_gamma, nb_pois, nb_final})
    # 1) Branch purity: any S2 event for is_multi=0 => branch_purity_violation
    assert_branch_purity(hurdle, {nb_gamma, nb_pois, nb_final})
    # 2) By (seed, parameter_hash, run_id, merchant_id):
    for key in keys:
        A := nb_gamma[key]; B := nb_pois[key]; F := nb_final[key]
        # coverage/cardinality
        assert ((len(A)>=1 && len(B)>=1 && len(F)==1) or merchant_is_not_multi(key))
        # counters: monotone intervals; nb_final non-consuming
        assert_counters_monotone(A); assert_counters_monotone(B); assert_final_nonconsuming(F)
        # parameter echo & composition
        (mu,phi) := (F[0].mu, F[0].dispersion_k)
        for a in A: assert_ulps_equal(a.alpha, phi, 1)
        pairwise_by_time_or_counter(A, B, (a, b) => assert_ulps_equal(b.lambda, (mu/phi)*a.gamma_value, 1))
        # acceptance reconstruction
        t := first i with B[i].k >= 2
        assert t exists && F[0].n_outlets == B[t].k && F[0].nb_rejections == t
    # 3) Corridors (S2.7)
    (rho_hat, p99, Smax) := corridors(nb_final, policy)
    assert rho_hat <= 0.06 && p99 <= 3 && Smax < policy.cusum.threshold_h
```

**Fail fast:** Any violated assertion returns a typed failure with the corresponding code in §3. 

---

## 6) Invariants (re-stated as validator obligations)

* **I-NB2 echo.** `nb_final.mu`/`dispersion_k` must **equal** S2.2 outputs (binary64).
* **Coverage invariant.** If `nb_final` exists, there must be ≥1 prior Gamma and ≥1 prior Poisson (`context="nb"`) with matching envelope keys.
* **Consumption discipline.** Exactly two component events/attempt; `nb_final` non-consuming; counters monotone, non-overlapping.

---

## 7) Conformance tests (KATs)

1. **Parameter invalid KAT.** Force $\eta$ to overflow/underflow so $\mu$ or $\phi$ becomes non-finite or $\le0$ ⇒ writer raises `ERR_S2_NUMERIC_INVALID`; validator shows **no** S2 events for that merchant and flags `invalid_nb_parameters`.
2. **Schema KAT.** Drop `context` in a Gamma row ⇒ schema failure; run aborts with `schema_violation`.
3. **Coverage KAT.** Emit `nb_final` without a Poisson component ⇒ `event_coverage_gap` and abort.
4. **Counters KAT.** Make `nb_final` advance counters ⇒ `rng_consumption_violation` and abort.
5. **Composition KAT.** Perturb `lambda` by 1 ULP ⇒ `composition_mismatch` and abort.
6. **Partitions KAT.** Write Poisson to a wrong path or missing `parameter_hash` partition ⇒ `partition_misuse` and abort.
7. **Branch purity KAT.** Create S2 events for a known `is_multi=0` merchant ⇒ `branch_purity_violation`.
8. **Corridors KAT.** Inflate low-$\mu$ merchants to push $\widehat{\rho}_{\text{rej}}>0.06$ ⇒ `corridor_breach:rho`.

---

## 8) Run outcome & artifacts

* **Any single hard failure** causes the S2 block to **fail validation**, so **1A fails** for that `manifest_fingerprint`. The validator still writes a **bundle** to
  `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
  containing: `index.json`, `schema_checks.json`, `rng_accounting.json`, `metrics.csv`, diffs; `_passed.flag` is **omitted**. 1A→1B hand-off is **disallowed** until fixed.

---

## 9) Practical guidance (non-normative but recommended)

* Treat schema failures and counter violations as **CI blockers**—catch them on small test shards.
* Keep a **golden KAT suite** exercising each failure class (§7) with tiny fixtures.
* When corridor breaches occur, surface **α-diagnostics** (expected attempts from $\alpha_m$) to highlight modelling drift vs. data shift.

---

# S2.9 — Outputs (state boundary) & hand-off to S3

## 1) Scope & intent (normative)

S2 closes by (i) **persisting only the authoritative RNG event streams** for the NB sampler and (ii) exporting the accepted domestic outlet count $N_m$ (and rejection tally $r_m$) **in-memory** to S3. **No Parquet data product** is written by S2. All persistence is via three JSONL **event** streams defined in the dictionary and validated against canonical schema anchors. 

---

## 2) Persisted outputs (authoritative RNG event streams)

Write **exactly** these streams, **partitioned** by `["seed","parameter_hash","run_id"]`, with the indicated **schema refs**. Cardinalities are **hard** contracts:

1. **Gamma components (NB mixture)**
   Path: `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/gamma_component`
   Cardinality per multi-site merchant: **≥ 1** (one row **per attempt**). 

2. **Poisson components (NB mixture)**
   Path: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/poisson_component`
   Cardinality: **≥ 1** (one row **per attempt**). (This stream id is **reused by S4** with a different `context`, hence the dictionary description “NB composition / ZTP”.) 

3. **NB final (accepted outcome)**
   Path: `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/nb_final`
   Cardinality: **exactly 1** row **per merchant** (echoes `mu`, `dispersion_k`, `n_outlets`, `nb_rejections`). 

**Envelope (must on every row).** `ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, blocks (uint64), draws ("uint128-dec")`. (`nb_final` is **non-consuming**: `before == after`, so `blocks=0`, `draws="0"`.)

**Payload (must).**

* `gamma_component`: `{ merchant_id, context="nb", index=0, alpha=φ_m, gamma_value }`.
* `poisson_component`: `{ merchant_id, context="nb", lambda, k }`.
* `nb_final`: `{ merchant_id, mu=μ_m, dispersion_k=φ_m, n_outlets=N_m, nb_rejections=r_m }`.
  Types & domains per schema (positivity for `mu`,`dispersion_k`; `n_outlets≥2`; `nb_rejections≥0`).  

**Retention & lineage.** These streams are **not final in layer**, carry 180-day retention, and are produced by `1A.nb_*` modules (dictionary lineage).

---

## 3) In-memory export to S3 (contract)

For each merchant $m$ that **finalised** in S2:

$$
\boxed{\,N_m\in\{2,3,\dots\}\,}\quad\text{and}\quad \boxed{\,r_m\in\mathbb{Z}_{\ge 0}\,}.
$$

* $N_m$ = **authoritative** domestic outlet count for downstream branches; it **must not be re-sampled** downstream.
* $r_m$ = diagnostic only (corridor metrics); no modelling effect beyond validation. 

**Downstream use.**

* **S3 (eligibility gate)** consumes $N_m$ to determine if the merchant may attempt cross-border (policy flags live in `crossborder_eligibility_flags`). S3 runs **only** for multi-site merchants that left S2.
* **S4 (ZTP)**, if eligible, will typically inject $\log N_m$ into its intensity for foreign count; S4 writes its **own** events but reuses the **Poisson component stream id** with `context="ztp"`.

---

## 4) Boundary invariants (must-hold at S2 exit)

1. **Coverage invariant.** If a merchant has an `nb_final`, there exist **≥1** `gamma_component` **and** **≥1** `poisson_component` rows (both with `context="nb"`) under the same envelope keys. Absence is a **structural failure**.

2. **Consumption discipline.** Per merchant and label, event counter intervals are **monotone & non-overlapping**; `nb_final` is **non-consuming** (`before==after`). (Checked in S2.6 and by the validator.)

3. **Composition identity.** For each attempt $t$: $\lambda_t = (\mu_m/\phi_m)\cdot \texttt{gamma_value}_t$ (ULP-tight). The `nb_final`’s `mu, dispersion_k` **equal** the S2.2 values.

4. **Cardinality.** Exactly **one** `nb_final` per `(seed, parameter_hash, run_id, merchant_id)`. **≥1** component rows per attempt; exactly **one** Gamma + **one** Poisson per attempt.

5. **Partitions & paths.** All three streams are written **only** under their dictionary paths and partitions; any deviation is a hard failure (`partition_misuse`).

---

## 5) Hand-off to S3 (operational)

**Eligibility of a merchant to enter S3:**

* Must have `is_multi=1` from S1 and a valid S2 `nb_final`. (Branch purity is enforced globally; single-site merchants must have **no** S2/S4–S6 events.) 
* S3 receives $(N_m,r_m)$ **in-memory** and reads `crossborder_eligibility_flags(parameter_hash)` to determine the branch. **S3 persists nothing**; it fixes the policy branch that later must be reflected when `country_set` is materialised.

> **Note.** The **1A→1B hand-off** (egress consumption) is governed later by S9: `_passed.flag` must match `SHA256(validation_bundle_1A)` for the same fingerprint before 1B can read `outlet_catalogue`. S2 does not write egress and therefore cannot authorise 1B directly.

---

## 6) Writer reference pattern (idempotent; per merchant)

```pseudo
# Preconditions: merchant m is multi-site from S1; (mu, phi) evaluated in S2.2; RNG substreams established per S2.6.

# Attempt loop (S2.3/2.4) emits gamma_component then poisson_component per attempt (not repeated here).

# On acceptance:
N := accepted K_t   # K_t >= 2
r := t              # number of rejections

# Emit final (non-consuming) event:
envelope := current_envelope_with_counters()   # before == after (no extra draws here)
row := {
  merchant_id: m,
  mu: mu, dispersion_k: phi,
  n_outlets: N, nb_rejections: r
}
write_jsonl(
  path="logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl",
  envelope=envelope, payload=row
)

# Idempotency: the (seed, parameter_hash, run_id, merchant_id) key must not appear twice.
# Writers must dedupe on that composite key; validators hard-fail duplicate finals.
```

**Why non-consuming?** S2.5 records the acceptance and echoes parameters; all randomness was consumed in the attempts. Envelope equality proves it.

---

## 7) Validator obligations (S2-specific at boundary)

Before S3 consumes $(N_m,r_m)$ in-memory, the S2 validator must have already:

* **Schema-validated** all three streams.
* Checked **coverage & cardinality** and **consumption discipline**; verified **composition** identity per attempt. 
* Computed **corridor metrics** $\widehat{\rho}_{\text{rej}}$, $p_{99}(r_m)$, and **CUSUM**; **hard-fail** on any breach.

---

## 8) Conformance tests (KATs for S2.9)

1. **Streams present & partitioned.** For a shard, assert that for every merchant with `nb_final`, there exist matching `gamma_component` and `poisson_component` rows under the same `(seed, parameter_hash, run_id)` partitions; no rows exist under any other path.

2. **Final echo & non-consumption.** For a sample of merchants, check `nb_final.mu == S2.2.mu` and `nb_final.dispersion_k == S2.2.phi`, and envelope counters are equal (`before==after`). 

3. **Reconstruction of $(N_m,r_m)$.** Rebuild attempts by interleaving component events; find the first Poisson with `k>=2`; assert its `k` equals `nb_final.n_outlets` and the attempt index equals `nb_final.nb_rejections`.

4. **S3 readiness.** Ensure all `is_multi=1` merchants with `nb_final` also have a row in `crossborder_eligibility_flags(parameter_hash)`; single-site merchants have **no** S2 events. 

---

## 9) Complexity & operational notes

* **I/O:** three append-only JSONL streams; per-merchant output is O(#attempts).
* **Memory:** O(1) for the writer at finalisation; S3 consumes only $(N_m,r_m)$.
* **Reuse:** The Poisson component stream id is deliberately shared with S4 (ZTP) via `context`, simplifying audit tooling.