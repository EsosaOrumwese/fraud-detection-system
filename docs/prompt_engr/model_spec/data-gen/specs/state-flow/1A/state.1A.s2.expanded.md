# S2.1 — Scope, Preconditions, and Inputs (final, implementation-ready)

## 1) Scope & intent

S2 samples the **home-country (domestic) multi-site outlet count** $N_m$ for merchants that cleared S1 as **multi-site**. S2 is stochastic (NB via Poisson–Gamma); **S2.1 itself is deterministic** — it gates eligibility and assembles the exact numeric inputs required by S2.2–S2.5. Single-site merchants **do not** enter S2.

**Terminology note.** “Domestic” here means the **home-country** total **pre-split** anchor used by S3/S4; foreign outlets (if any) are added later and logged under their own streams. The NB **final** event emitted by S2 is authoritative for domestic count and is never re-sampled downstream.

---

## 2) Entry preconditions (MUST)

For merchant $m$ to enter S2:

1. **Canonical hurdle record present & positive.** Exactly one hurdle event exists in
   `logs/rng/events/hurdle_bernoulli/...` with payload `is_multi=true` for $m$. Absence or `is_multi=false` ⇒ S2 MUST NOT run for $m$. This is the **only** gate.
2. **Branch-purity guarantee.** If `is_multi=false`, **no S2 events** for $m$ may exist; any presence is a structural failure (validator enforces).
3. **Lineage anchors available.** The process exposes `seed`, `parameter_hash`, and `manifest_fingerprint` for envelope joins later. (All S2 streams are partitioned by `{seed, parameter_hash, run_id}` per dictionary.)

**Abort codes (preflight):**

* `ERR_S2_ENTRY_MISSING_HURDLE` — no hurdle record for $m$.
* `ERR_S2_ENTRY_NOT_MULTI` — hurdle record exists but `is_multi=false`.

Either abort **skips S2** for $m$ and will surface under branch-purity checks in validation.

---

## 3) Mathematical inputs (MUST)

### 3.1 Fixed design vectors (prepared in S0; re-assembled here)

$$
\boxed{x^{(\mu)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m)\big]^\top},\quad
\boxed{x^{(\phi)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \log g_c\big]^\top}.
$$

Where $g_c>0$ is GDP-per-capita for the **home** ISO $c=\texttt{home_country_iso}_m$. NB **mean** excludes GDP; NB **dispersion** includes $\log g_c$. Column order and dummy encodings are frozen by the fitting bundle.

### 3.2 Coefficient vectors (governed artefacts; parameter-scoped)

* **NB mean coefficients $\beta_\mu$** are loaded from **`hurdle_coefficients.yaml`** (the **nb-mean** block lives alongside the logistic vector; one provenance point), keyed by `parameter_hash`.
* **NB dispersion coefficients $\beta_\phi$** are loaded from **`nb_dispersion_coefficients.yaml`**, also keyed by `parameter_hash`.

> Rationale: the assumptions explicitly state that logistic (hurdle) and **NB mean** coefficients co-reside in the same YAML, while dispersion lives in its own YAML. This removes the ambiguity around an “`hurdle_nb.beta_mu`” pseudo-source.

### 3.3 RNG discipline & authoritative streams (for later S2 steps)

Pin the contracts S2.3–S2.5 will use:

* **RNG:** Philox $2\times64$-10 with the **shared RNG envelope** (`seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_*, rng_counter_after_*`).
* **Authoritative event streams (JSONL):**

  * `gamma_component` (context=`"nb"`) → `schemas.layer1.yaml#/rng/events/gamma_component`. **Produced by** `1A.nb_and_dirichlet_sampler`.
  * `poisson_component` (context=`"nb"`) → `#/rng/events/poisson_component`. **Produced by** `1A.nb_poisson_component`.
  * `nb_final` (accepted NB outcome) → `#/rng/events/nb_final`. **Produced by** `1A.nb_sampler`.

All streams are partitioned by `{seed, parameter_hash, run_id}` as per the dataset dictionary. S2.1 **does not** write to any of them.

---

## 4) Numeric requirements (MUST)

* **Arithmetic:** Evaluate linear predictors in **IEEE-754 binary64** only. No mixed precision. (Numeric environment policy is part of the registry.)
* **Sanity guards (enforced in S2.2 but predeclared here):** After exponentiation, $\mu_m>0$ and $\phi_m>0$; non-finite or $\le 0$ → `ERR_S2_NUMERIC_INVALID`.

---

## 5) Pseudocode (normative preflight & assembly; RNG draws = 0)

```pseudo
function s2_1_prepare_inputs(m):
    # 1) Gate on the authoritative S1 event
    hb := read_event("logs/rng/events/hurdle_bernoulli", m)
    if hb is None:             raise ERR_S2_ENTRY_MISSING_HURDLE
    if hb.is_multi != true:    raise ERR_S2_ENTRY_NOT_MULTI

    # 2) Deterministic features (S0-prepared keys)
    c  := ingress.home_country_iso[m]
    g  := gdp_per_capita[c]             # > 0 guaranteed by S0 load
    xm := [1, phi_mcc(ingress.mcc[m]), phi_ch(ingress.channel[m])]
    xk := [1, phi_mcc(ingress.mcc[m]), phi_ch(ingress.channel[m]), log(g)]

    # Shape checks (deterministic)
    assert finite_all(xm) and finite_all(xk)

    # 3) Governed coefficients (scoped by parameter_hash)
    beta_mu  := load_yaml("hurdle_coefficients.yaml").nb_mean       # β_μ
    beta_phi := load_yaml("nb_dispersion_coefficients.yaml").coeffs # β_φ

    # 4) Final S2 context (immutable; consumed by S2.2+)
    return NBContext{
        merchant_id: m,
        x_mu: xm, x_phi: xk,
        beta_mu: beta_mu, beta_phi: beta_phi,
        lineage: {seed, parameter_hash, manifest_fingerprint},
        module_labels: {
            gamma_substream: "gamma_component",
            poisson_substream: "poisson_component",
            writer_module: "1A.nb_sampler"
        }
    }
```

*Emissions:* **None.** S2.1 consumes **no RNG** and writes **no** S2 events. Paths and schemas are pinned only for downstream use.

---

## 6) Invariants & MUST-NOTs

* **I-S2.1-A (Entry determinism).** Only merchants with `is_multi=true` hurdle records may run S2; any S2 stream row for `is_multi=false` is a structural failure.
* **I-S2.1-B (Inputs completeness).** $\phi_{\mathrm{mcc}}, \phi_{\mathrm{ch}}, g_c, \beta_\mu, \beta_\phi$ MUST be present and finite; else `ERR_S2_INPUTS_INCOMPLETE:{key}` (merchant-scoped abort).
* **I-S2.1-C (No persistence yet).** S2.1 MUST NOT write `gamma_component`, `poisson_component`, or `nb_final`; those are written only in S2.3–S2.5.

---

## 7) Errors & abort semantics (merchant-scoped)

* `ERR_S2_ENTRY_MISSING_HURDLE`
* `ERR_S2_ENTRY_NOT_MULTI`
* `ERR_S2_INPUTS_INCOMPLETE:{key}`
* `ERR_S2_NUMERIC_INVALID` (raised in S2.2 on non-finite/≤0 $\mu$ or $\phi$)

**Effect:** Abort S2 for $m$ with **no S2 events** written; validator separately enforces branch-purity and coverage.

---

## 8) Hand-off contract to S2.2+

On success, expose the immutable **NB context**:

$$
\left(x^{(\mu)}_m,\ x^{(\phi)}_m,\ \beta_\mu,\ \beta_\phi,\ \text{seed},\ \text{parameter_hash},\ \text{manifest_fingerprint}\right),
$$

which S2.2 uses to compute $\mu_m,\phi_m$ before sampling; later `nb_final` must **echo** $\mu$ and `dispersion_k` **byte-exactly** for the validator’s echo test.

---

## 9) Conformance spot-checks (writer & validator)

* **Gate correctness.** Pick a known `is_multi=0` merchant and confirm **no** S2 streams contain its key.
* **Inputs reproducibility.** Recompute $x^{(\mu)}, x^{(\phi)}$ and verify byte-exact equality with values that lead to `nb_final.mu` and `nb_final.dispersion_k`.
* **Lineage presence.** Ensure `(seed, parameter_hash, manifest_fingerprint)` are carried forward to enable exact envelope joins.

---

### What changed vs. your draft (quick diff in words)

* **Pinned coefficient sources** unambiguously: $\beta_\mu$ from `hurdle_coefficients.yaml` (**nb-mean** block), $\beta_\phi$ from `nb_dispersion_coefficients.yaml`. (Removes the informal `artefacts.hurdle_nb.*` reference.)
* **Fixed feature typo** $\phi_{\mathrm{ch}}$ (was `\phi_{\mathrm{ch)}`) and reiterated column-order freeze.
* **Bound module/substream labels** to dictionary `produced_by` for later S2 writers (`1A.nb_sampler`, `1A.nb_and_dirichlet_sampler`, `1A.nb_poisson_component`).
* **Explicit numeric policy** (binary64) tied to the numeric environment registry.
* **Clarified “domestic/pre-split”** to match the global S2/S3/S4 narrative and prevent downstream reinterpretation.

If this is good, I’m ready to apply the same standard to S2.2 next.

---

# S2.2 — NB2 parameterisation (final, deterministic)

## 1) Scope & intent

Given the S2.1 context for merchant $m$, compute the **Negative-Binomial (NB2)** parameters:

$$
\boxed{\mu_m=\exp(\beta_\mu^\top x^{(\mu)}_m)},\qquad
\boxed{\phi_m=\exp(\beta_\phi^\top x^{(\phi)}_m)}.
$$

This step is **deterministic** (no RNG). Its outputs $(\mu_m,\phi_m)$ are the **only** values S2.3–S2.5 may use and must be **binary64-stable**. NB2 moments: $\mathbb{E}[N_m]=\mu_m$, $\mathrm{Var}[N_m]=\mu_m+\mu_m^2/\phi_m$. (The $(r,p)$ form, $r=\phi_m,\ p=\phi_m/(\phi_m+\mu_m)$, is derivational; we don’t persist it here.)

---

## 2) Inputs (MUST)

From S2.1:

* **Design vectors**

  $$
  x^{(\mu)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m)\big]^\top,\quad
  x^{(\phi)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \log g_c\big]^\top,
  $$

  with $g_c>0$ (home-country GDP per capita). GDP appears **only** in dispersion.
* **Coefficient vectors**: $\beta_\mu,\ \beta_\phi$ from the governed coefficient artefacts bound by `parameter_hash`.
* **Lineage anchors**: `seed`, `parameter_hash`, `manifest_fingerprint` (for later echo/join).

**Preconditions (MUST)**

1. All elements of $x^{(\mu)}_m, x^{(\phi)}_m, \beta_\mu, \beta_\phi$ are finite binary64.
2. Dimensions match: $|x^{(\mu)}_m|=|\beta_\mu|$ and $|x^{(\phi)}_m|=|\beta_\phi|$.
3. $g_c > 0$ (so $\log g_c$ is defined).

---

## 3) Algorithm (normative; deterministic; no RNG)

Let $\eta^{(\mu)}_m=\beta_\mu^\top x^{(\mu)}_m$, $\eta^{(\phi)}_m=\beta_\phi^\top x^{(\phi)}_m$.

1. **Dot products (binary64; FMA disabled).**
   Compute $\eta$ using deterministic binary64 arithmetic with **FMA explicitly disabled** for these operations. Do not reorder summands or use non-deterministic BLAS paths. If a library is used, it must be configured for deterministic reductions.

2. **Exponentiate (binary64).**
   $\mu_m=\exp(\eta^{(\mu)}_m)$, $\phi_m=\exp(\eta^{(\phi)}_m)$.

3. **Numeric guards (MUST; no clamping).**

   * If either $\mu_m$ or $\phi_m$ is non-finite or $\le 0$ ⇒ `ERR_S2_NUMERIC_INVALID`.
   * **Representable ranges (planning defaults):**

     $$
     \mu_m \in (10^{-9},\,10^{9}],\qquad \phi_m \in (10^{-6},\,10^{6}].
     $$

     If outside range ⇒ `ERR_S2_NUMERIC_OUT_OF_RANGE`. (These are planning-phase bounds to avoid under/overflow in S2.3; tighten later if policy changes.)

**No emissions; no RNG draws.** Values are carried forward in memory and must be echoed byte-exactly in `nb_final` (S2.5).

---

## 4) Output contract (to S2.3–S2.5)

Expose the immutable NB2 context:

$$
\big(m,\ x^{(\mu)}_m,\ x^{(\phi)}_m,\ \beta_\mu,\ \beta_\phi,\ \mu_m,\ \phi_m,\ \text{seed},\ \text{parameter_hash},\ \text{manifest_fingerprint}\big).
$$

S2.3–S2.5 **must** use these exact binary64 values; **no recomputation** from source features is allowed downstream.

---

## 5) Invariants (MUST)

* **I-NB2-POS**: $\mu_m > 0$ and $\phi_m > 0$.
* **I-NB2-RANGE**: $\mu_m\in(10^{-9},10^{9}],\ \phi_m\in(10^{-6},10^{6}]$.
* **I-NB2-B64**: $\mu_m,\phi_m$ are IEEE-754 binary64 and round-trip unchanged through JSONL encoding/decoding.
* **I-NB2-ECHO**: `nb_final.mu == μ_m` and `nb_final.dispersion_k == φ_m` **bit-exactly**.

---

## 6) Downstream echo (binding reference)

When S2.5 emits the single `nb_final` event for $m$:

```json
{ "mu": <binary64>, "dispersion_k": <binary64>,
  "n_outlets": N_m, "nb_rejections": r_m, ... }
```

The `mu` and `dispersion_k` fields **must equal** the values computed here, byte-for-byte.

---

## 7) Errors & abort semantics (merchant-scoped)

* `ERR_S2_NUMERIC_INVALID` — any non-finite $\eta$, or non-finite/≤0 $\mu$ or $\phi$.
* `ERR_S2_NUMERIC_OUT_OF_RANGE` — $\mu$ or $\phi$ outside the representable ranges above.
  **Effect:** Skip S2 for $m$ (no S2 events); validator will also fail coverage if any downstream `nb_final` appears.

---

## 8) Reference pseudocode (deterministic; no RNG; no emissions)

```pseudo
function s2_2_eval_links(ctx: NBContext) -> NBContext:
    xm, xk   := ctx.x_mu, ctx.x_phi
    bmu, bph := ctx.beta_mu, ctx.beta_phi

    # 1) Deterministic dot products (binary64, FMA disabled)
    eta_mu  := dot64_no_fma(bmu,  xm)
    eta_phi := dot64_no_fma(bph,  xk)

    # 2) Exponentiate
    mu  := exp64(eta_mu)
    phi := exp64(eta_phi)

    # 3) Guards
    if not isfinite(mu) or mu <= 0:   raise ERR_S2_NUMERIC_INVALID
    if not isfinite(phi) or phi <= 0: raise ERR_S2_NUMERIC_INVALID
    if mu  <= 1e-9 or mu  > 1e9:      raise ERR_S2_NUMERIC_OUT_OF_RANGE
    if phi <= 1e-6 or phi > 1e6:      raise ERR_S2_NUMERIC_OUT_OF_RANGE

    # 4) Hand-off (no emissions)
    ctx.mu  = mu
    ctx.phi = phi
    return ctx
```

---

## 9) Conformance tests (KATs)

**Positive (round-trip & echo)**

* Compute $(\mu,\phi)$ and confirm they equal the `nb_final` echo bit-for-bit after JSONL round-trip.

**Negative (guards)**

* Force $\eta^{(\mu)}$ > 709.78 ⇒ `exp` overflow ⇒ `ERR_S2_NUMERIC_INVALID`.
* Force $\eta^{(\phi)}\ll 0$ ⇒ $\phi\to 0^+$ ⇒ `ERR_S2_NUMERIC_OUT_OF_RANGE`.
* Break dimensions (|β|≠|x|) ⇒ `ERR_S2_NUMERIC_INVALID`.

**Determinism**

* Evaluate on hosts with/without FMA; results must be identical. If not, the build flags aren’t honoring “FMA disabled”.

---

If you’re happy with this, send over **S2.3** and I’ll apply the same level of tightening (attempt indexing, gamma `scale:1.0`, substream labels, etc.).

---

# S2.3 — Poisson–Gamma construction (one attempt), samplers, substreams (final)

## 1) Scope & intent

Given $(\mu_m,\phi_m)$ from **S2.2**, perform **one** NB mixture attempt:

$$
G\sim\Gamma(\alpha=\phi_m,\ \text{scale}=1),\qquad
\lambda=\frac{\mu_m}{\phi_m}\,G,\qquad
K\sim\mathrm{Poisson}(\lambda).
$$

For this attempt, emit **exactly one** `gamma_component` and **exactly one** `poisson_component` event (context=`"nb"`). **Acceptance is decided in S2.4** (accept iff $K\ge2$).

---

## 2) Mathematical foundation (normative)

If $G\sim\Gamma(\phi_m,1)$ and $K\mid G\sim\text{Poisson}(\frac{\mu_m}{\phi_m}G)$, then $K\sim\text{NB2}(\mu_m,\phi_m)$ with $\mathbb{E}K=\mu_m$ and $\mathrm{Var}K=\mu_m+\mu_m^2/\phi_m$.

---

## 3) Samplers (normative and pinned)

### 3.1 Gamma $\Gamma(\alpha,1)$ — Marsaglia–Tsang (MT1998)

* **Uniforms**: open-interval $U(0,1)$ only.
* **Normals**: Box–Muller; **no caching** (each normal costs **2 uniforms**).
* **α ≥ 1**:
  Let $d=\alpha-\tfrac{1}{3}$, $c=(9d)^{-1/2}$. Repeat:

  1. $Z\sim\mathcal N(0,1)$ (2 uniforms), 2) $V=(1+cZ)^3$ (reject if $V\le 0$), 3) $U\sim U(0,1)$ (1 uniform), 4) accept if $\ln U<\tfrac12Z^2+d-dV+d\ln V$; return $G=dV$.
     **Uniform budget per MT iteration**: **3 uniforms**.
* **0 < α < 1**:

  1. Draw $G'\sim\Gamma(\alpha+1,1)$ via the branch above (variable MT iterations; 3 uniforms per iteration).
  2. Draw $U\sim U(0,1)$ (1 uniform).
  3. Return $G = G'\,U^{1/\alpha}$.
     **Extra uniform per variate**: **+1** (for the power step).

**Gamma event payload (this attempt).**

```json
{
  "merchant_id": "<m>",
  "context": "nb",
  "attempt": <t>,
  "alpha": <phi_m as binary64>,
  "scale": 1.0,
  "gamma_value": <G as binary64>,
  "...rng_envelope...": {
    "seed": "...", "parameter_hash": "...", "manifest_fingerprint": "...",
    "module": "1A.nb_sampler", "substream_label": "gamma_nb",
    "rng_counter_before_hi": "...", "rng_counter_before_lo": "...",
    "rng_counter_after_hi":  "...", "rng_counter_after_lo":  "...",
    "draws": "<after-before unsigned 128-bit>"
  }
}
```

Schema: `schemas.layer1.yaml#/rng/events/gamma_component`.
**Note**: only payload fields change (added `attempt`, `scale`, and NB-specific label); the schema anchor remains the same.

**Expected uniform draw count** (checked by envelope deltas, not by code paths):

* If $\alpha\ge1$: $3\times J_t$ for attempt $t$, where $J_t\ge1$ MT iterations.
* If $0<\alpha<1$: $3\times J_t + 1$.

---

### 3.2 Poisson $\text{Poisson}(\lambda)$ — regime split (S0.3.7)

* **Regimes (normative constants)**:

  * **Inversion** if $\lambda<10$.
  * **PTRS (Hörmann transformed-rejection)** if $\lambda\ge10$, with:
    $b=0.931+2.53\sqrt\lambda$, $a=-0.059+0.02483\,b$, $\mathrm{inv}\alpha=1.1239+1.1328/(b-3.4)$, $v_r=0.9277-3.6224/(b-2)$.
    Each PTRS *inner attempt* consumes 2 uniforms; attempts are geometric.
* **Poisson event payload (this attempt).**

```json
{
  "merchant_id": "<m>",
  "context": "nb",
  "attempt": <t>,
  "lambda": <lambda as binary64>,
  "k": <K as int64>,
  "...rng_envelope...": {
    "seed": "...", "parameter_hash": "...", "manifest_fingerprint": "...",
    "module": "1A.nb_sampler", "substream_label": "poisson_nb",
    "rng_counter_before_hi": "...", "rng_counter_before_lo": "...",
    "rng_counter_after_hi":  "...", "rng_counter_after_lo":  "...",
    "draws": "<after-before unsigned 128-bit>"
  }
}
```

Schema: `schemas.layer1.yaml#/rng/events/poisson_component` (payload extended with `attempt`; substream label is NB-specific).

---

## 4) RNG substreams & labels (MUST)

* **Module**: all S2 mixture emissions use `module="1A.nb_sampler"`.
* **NB-specific substreams** (disjoint from S4):

  * Gamma: `substream_label="gamma_nb"`
  * Poisson: `substream_label="poisson_nb"`
    (S4 will use, e.g., `poisson_ztp`; no label reuse.)
* **Keyed mapping rule** (restate here to avoid drift): counters are a pure function of
  `hash(module, substream_label, merchant_id, seed, parameter_hash, manifest_fingerprint)`.
  **No additive strides.** Attempt number `t` is **not** part of the key (it’s payload-only); draw sequences are determined solely by the key and sampler logic.

---

## 5) One-attempt construction & emission (normative)

1. **Gamma**: draw $G$ on `gamma_nb`; emit `gamma_component` (payload above).
2. **Poisson**: compute $\lambda=(\mu/\phi)\,G$ in binary64; if non-finite or $\le0$ ⇒ `ERR_S2_NUMERIC_INVALID`.
   Draw $K$ on `poisson_nb`; emit `poisson_component`.
3. Return $(G,\lambda,K)$ to S2.4 (which decides accept/resample).

**Emission order per attempt**: Gamma **then** Poisson.

---

## 6) Draw accounting & reconciliation (MUST)

For each event, `draws = (after_hi,after_lo) − (before_hi,before_lo)` (unsigned 128-bit).
Validators sum `draws` per $(m,\text{substream})$ and check:

* Gamma: $3\times J_t$ (+1 if $\alpha<1$) per attempt $t$.
* Poisson: **measured** by counters (inversion/PTRS vary).

---

## 7) Determinism & ordering (MUST)

* **Cardinality** per attempt: exactly **2 events** (Gamma → Poisson).
* **Attempt indexing**: `attempt=t` (0,1,2,…) is monotone and supplied by S2.4’s loop; it is **not** part of the RNG key.
* **Bit replay**: for fixed $(x,\beta,\text{seed},\text{parameter_hash},\text{manifest_fingerprint})$, the emitted $(G_t,K_t)$ sequence is bit-identical across replays and independent of other states.

---

## 8) Preconditions & guards (MUST)

* Inputs: $\mu>0,\ \phi>0$ from S2.2.
* Compute $\lambda$ in binary64; if `!isfinite(λ)` or `λ<=0` ⇒ `ERR_S2_NUMERIC_INVALID` (merchant-scoped abort of S2).
* All floating-point payload fields are **IEEE-754 binary64**; `k` is signed 64-bit and `k≥0`.

---

## 9) Reference pseudocode (one attempt; emissions included)

```pseudo
function s2_3_attempt_once(ctx: NBContext, t: int) -> AttemptRecord:
    mu  := ctx.mu      # >0
    phi := ctx.phi     # >0

    # --- Gamma on substream "gamma_nb"
    G := gamma_mt1998(alpha=phi)  # uses open-interval U and Box–Muller; no caching
    emit_gamma_component(
        merchant_id=ctx.merchant_id,
        context="nb",
        attempt=t,
        alpha=phi,
        scale=1.0,
        gamma_value=G,
        envelope=substream_envelope(module="1A.nb_sampler", label="gamma_nb")
    )

    # --- Poisson on substream "poisson_nb"
    lambda := (mu / phi) * G
    if not isfinite(lambda) or lambda <= 0: raise ERR_S2_NUMERIC_INVALID
    K := poisson_regime_split(lambda)       # inversion (<10) or PTRS (>=10)
    emit_poisson_component(
        merchant_id=ctx.merchant_id,
        context="nb",
        attempt=t,
        lambda=lambda,
        k=K,
        envelope=substream_envelope(module="1A.nb_sampler", label="poisson_nb")
    )

    return AttemptRecord{G: G, lambda: lambda, K: K}
```

---

## 10) Errors & abort semantics (merchant-scoped)

* `ERR_S2_NUMERIC_INVALID` — $\lambda$ non-finite or $\le 0$.
  **Effect**: abort S2 for $m$ with no further S2 emissions (validator will also enforce coverage).

---

## 11) Conformance tests (KATs)

* **Gamma budgets**: for $\phi\ge1$, `draws_gamma == 3*J_t`; for $\phi<1$, `3*J_t + 1`.
* **Poisson regimes**: pick $\lambda=5$ (inversion) and $\lambda=50$ (PTRS) and confirm bit replay and nonzero `draws`.
* **Ordering**: per attempt, exactly two events in Gamma→Poisson order; `attempt` increments by 1; later exactly one `nb_final` appears upon acceptance (S2.4).

---

### Label finalisation note

This sub-state **finalises** NB substream labels: `"gamma_nb"` and `"poisson_nb"`. If S2.1 listed `"gamma_component"`/`"poisson_component"` as placeholders, update them to these names to keep NB (S2) disjoint from ZTP (S4).

---

# S2.4 — Rejection rule (enforce multi-site $N \ge 2$) — final

## 1) Scope & intent

Turn the NB mixture **attempt stream** from S2.3 into a single **accepted** outlet count

$$
\boxed{\,N_m \in \{2,3,\dots\}\,}
$$

by **rejecting** any attempt whose Poisson draw is $K\in\{0,1\}$. Count deterministic retries

$$
\boxed{\,r_m \in \mathbb N_0\ \text{(number of rejections before acceptance)}\,}.
$$

* $N_m$ is the merchant’s **total pre-split multi-site outlet count** (not “domestic”).
* S2.4 **emits no events** and **consumes no RNG**; it controls the accept/retry loop.
* `nb_final` emission is done in S2.5 after acceptance.

---

## 2) Inputs (MUST)

From prior substates:

* **Deterministic parameters:** $(\mu_m,\phi_m)$ from S2.2 (validated $>0$).
* **Attempt generator:** S2.3 yields an i.i.d. sequence of attempts; each attempt $t$ returns $(G_t,\lambda_t,K_t)$ and **emits exactly two events** for that merchant, in order:

  1. `gamma_component` with `module="1A.nb_sampler"`, `substream_label="gamma_nb"`, `context="nb"`, and `attempt=t`;
  2. `poisson_component` with `module="1A.nb_sampler"`, `substream_label="poisson_nb"`, `context="nb"`, and `attempt=t`.
     Both carry authoritative RNG envelopes (before/after counters).
* **Lineage anchors:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`.

**Preconditions (MUST):** $\mu_m>0,\ \phi_m>0$. S2.3 must honor the **per-attempt cardinality** (exactly one Gamma then one Poisson) and the NB-specific labels above.

---

## 3) Acceptance process (normative)

Index attempts $t=0,1,2,\dots$. For each $t$:

$$
G_t\sim\Gamma(\phi_m,1),\quad \lambda_t=\tfrac{\mu_m}{\phi_m}G_t,\quad K_t\sim\mathrm{Poisson}(\lambda_t)\quad\text{(as produced & logged by S2.3).}
$$

Accept the **first** $t$ with $K_t\ge2$ and set

$$
\boxed{\,N_m := K_t,\quad r_m := t\,}.
$$

If $K_t\in\{0,1\}$, **reject** and continue with the same merchant’s NB substreams. There is **no hard cap** here (corridor monitoring is external to S2.4).

---

## 4) Acceptance probability & rejection distribution (binding math)

Let $r=\phi_m$, $p=\phi_m/(\mu_m+\phi_m)$. With NB2 pmf

$$
\Pr[K=k]=\binom{k+r-1}{k}(1-p)^k\,p^r,
$$

we have

$$
\Pr[K=0]=p^{\phi_m},\qquad
\Pr[K=1]=\phi_m\frac{\mu_m}{\mu_m+\phi_m}\,p^{\phi_m}.
$$

Define per-attempt **success probability**

$$
\boxed{\,\alpha_m = 1-\Pr[K=0]-\Pr[K=1]\,}.
$$

Then $r_m$ is geometric with success $\alpha_m$:

$$
\Pr[r_m=r]=(1-\alpha_m)^r\alpha_m,\quad
\mathbb E[r_m]=\frac{1-\alpha_m}{\alpha_m},\quad
r_{m,q}=\Bigl\lceil\frac{\ln(1-q)}{\ln(1-\alpha_m)}\Bigr\rceil-1.
$$

(These expressions are **for validator corridors**; S2.4 does not compute them.)

---

## 5) Evidence & ordering requirements (MUST)

Although S2.4 emits nothing, acceptance requires the following **to exist** for merchant $m$ (checked later):

* At least **one** `gamma_component` (NB) **and** at least **one** `poisson_component` (NB) **preceding** the single `nb_final`.
* **Per attempt $t$**: exactly **two** events **in order**: `gamma_component`(NB, `attempt=t`) → `poisson_component`(NB, `attempt=t`).
* `nb_final` (S2.5) is **non-consuming**: its envelope counters do **not** advance.

---

## 6) Determinism & invariants (MUST)

* **Bit replay.** For fixed inputs $(x,\beta,\mu,\phi)$ and lineage, the attempt sequence $\{(G_t,K_t)\}$, the acceptance pair $(N_m,r_m)$, and the component event set are **bit-reproducible** (counter-based RNG + fixed labels + fixed attempt cardinality).
* **Consumption discipline.** Within each NB substream (`gamma_nb`, `poisson_nb`), envelope counter intervals are **monotone, disjoint**, and match the sampler budgets; `nb_final` shows **before==after**.
* **Context correctness.** All S2 component events use `context="nb"` (S4 uses a different label set and `context="ztp"`).

---

## 7) Outputs (to S2.5 and to validation)

* **Hand-off to S2.5 (in-memory):** $(N_m,\ r_m)$ with $N_m\ge2$. S2.5 will emit the **single** `nb_final` row echoing $\mu_m,\phi_m$ and recording `n_outlets=N_m`, `nb_rejections=r_m`.
* **Evidence for validation:** the NB component events described above; validators compute overall rejection rate, p99 of $r_m$, and CUSUM traces (outside S2.4).

---

## 8) Failure semantics

* **Merchant-scoped numeric invalid**: if S2.3 reports $\lambda_t$ non-finite or $\le0$ (should already raise in S2.3), treat as `ERR_S2_NUMERIC_INVALID` and **skip** merchant $m$ (no `nb_final`).
* **Structural coverage (run-scoped)**: any `nb_final` without prior NB `gamma_component` **and** NB `poisson_component`; more than one `nb_final` for the same merchant; counter overlap/regression ⇒ validators **abort the run**.
* **Corridor breach (run-scoped)**: rejection-rate / p99 / CUSUM breaches ⇒ validators **abort** and persist metrics.
  (S2.4 itself writes **no** rows.)

---

## 9) Reference pseudocode (language-agnostic; no RNG; no emissions)

```pseudo
# Returns (N >= 2, r = #rejections). S2.3 performs draws & emits NB component events.

function s2_4_accept(ctx: NBContext) -> (int N, int r):
    mu  := ctx.mu
    phi := ctx.phi
    t   := 0

    loop:
        (G, lambda, K) := s2_3_attempt_once(ctx, t)   # emits gamma_nb then poisson_nb with attempt=t
        if K >= 2:
            return (K, t)                             # S2.5 will emit nb_final(mu, phi, N=K, r=t)
        t := t + 1
```

Notes: S2.4 **does not** include `attempt` in RNG keys (payload-only); ordering is enforced by the emission order and envelope counters.

---

## 10) Conformance tests (KATs)

1. **Coverage & ordering.** For a sample merchant, reconstruct attempts by pairing `gamma_component`(NB, `attempt=t`) with `poisson_component`(NB, `attempt=t`); ensure there are $r+1$ pairs followed by exactly **one** `nb_final`. Check `nb_final.nb_rejections == r`.
2. **Numeric consistency.** For each attempt $t$: verify `poisson_component.lambda == (mu/phi) * gamma_component.gamma_value` bit-exact; for the accepted attempt, verify `nb_final.n_outlets == k`.
3. **Corridors (external).** On a synthetic run, measure overall rejection rate and empirical p99; trigger a breach to confirm the validator aborts.

---

## 11) Complexity

Expected constant attempts (geometric). S2.4 adds control-flow only; all sampling cost is in S2.3. Memory $O(1)$.

---

### What changed vs. your draft (quick diff)

* Replaced “**domestic**” with **total pre-split** $N_m$.
* Bound **NB-specific** labels (`gamma_nb`, `poisson_nb`) and included `attempt` in both component payloads; kept `module="1A.nb_sampler"` and `context="nb"`.
* Tightened evidence requirements to those labels and `attempt` ordering.
* Clarified determinism rules (no attempt in RNG key; substreams disjoint and monotone).

---

# S2.5 — Finalisation event `nb_final` (non-consuming, authoritative) — final

## 1) Scope & intent

Emit **one and only one** authoritative JSONL event per accepted multi-site merchant $m$ that records the accepted **total pre-split** outlet count and its provenance:

$$
\boxed{\,\mu_m>0,\ \phi_m>0,\ N_m\in\{2,3,\dots\},\ r_m\in\mathbb N_0\,}
$$

* $(\mu_m,\phi_m)$ are **verbatim** from S2.2 (bit-exact).
* $(N_m,r_m)$ are **verbatim** from S2.4 (first $K_t\ge2$ and the number of rejections).
* This event is **non-consuming**: RNG counters **must not change**.

---

## 2) Inputs (MUST)

* From **S2.2**: `mu = μ_m` (binary64, >0), `dispersion_k = φ_m` (binary64, >0).
* From **S2.4**: `n_outlets = N_m` (int64, ≥2), `nb_rejections = r_m` (int64, ≥0).
* **RNG envelope**: `ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, rng_counter_before_* , rng_counter_after_*`. For `nb_final`, **before == after**.

---

## 3) Event stream & partitioning (normative)

Persist **exactly one row** per `(seed, parameter_hash, run_id, merchant_id)` into:

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Schema (authoritative):** `schemas.layer1.yaml#/rng/events/nb_final`
* **Partitions:** `["seed","parameter_hash","run_id"]` (only).
* **Module / label (fixed):** `module="1A.nb_sampler"`, `substream_label="nb_final"`.
* **Context:** **not present** on `nb_final`.

---

## 4) Payload (required fields & domains)

Event **must** carry (in addition to the common envelope):

```
{
  merchant_id,
  mu,              // == μ_m (binary64, >0)
  dispersion_k,    // == φ_m (binary64, >0)
  n_outlets,       // == N_m (int64, ≥2)
  nb_rejections    // == r_m (int64, ≥0)
}
```

**Optional but RECOMMENDED (derived, deterministic):**

```
nb_r = dispersion_k,                       // binary64 (duplicate for canonical NB)
nb_p = dispersion_k / (dispersion_k + mu)  // binary64, computed here from echoed μ,φ
```

(If present, these must be computed in **binary64** here; no RNG.)

**Non-consuming constraint:** `rng_counter_before == rng_counter_after` (both 128-bit words). Validator treats inequality as structural failure.

---

## 5) Wire-format example (normative shape)

```json
{
  "merchant_id": "M12345",
  "mu": 7.0,
  "dispersion_k": 2.25,
  "n_outlets": 5,
  "nb_rejections": 1,
  "nb_r": 2.25,
  "nb_p": 0.24324324324324326,

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
  "rng_counter_after_hi":  "00000000"
}
```

---

## 6) Determinism & invariants (MUST)

* **I-FINAL-ECHO**: `mu` and `dispersion_k` **bit-match** S2.2 outputs.
* **I-FINAL-ACCEPT**: `n_outlets` and `nb_rejections` **equal** S2.4’s $(N_m,r_m)$. Exactly **one** `nb_final` per `(seed, parameter_hash, run_id, merchant_id)`.
* **I-FINAL-NONCONSUME**: `rng_counter_before == rng_counter_after`.
* **I-FINAL-COVERAGE**: Presence of `nb_final` **implies** ≥1 prior NB `gamma_component` **and** ≥1 prior NB `poisson_component` for the same `(seed, parameter_hash, run_id, merchant_id)`; validator enforces coverage, ordering (Gamma→Poisson per attempt), and cardinality.

---

## 7) Failure semantics

* **Schema violation** (missing/wrong types/envelope) → row-level failure; run fails validation.
* **Coverage gap / duplicates / consumption drift** → **structural failure**; run aborts.
* **Echo mismatch (μ,φ)** → structural failure; run aborts.

---

## 8) Writer algorithm (normative; single emission; no RNG)

```pseudo
# Inputs: mu>0 (b64), phi>0 (b64), N>=2 (i64), r>=0 (i64), envelope
# Envelope must already carry equal before/after counters.

function s2_5_emit_nb_final(m, mu, phi, N, r, envelope):
    # 0) Domain checks
    if not (isfinite(mu) and mu > 0):   raise ERR_S2_NUMERIC_INVALID
    if not (isfinite(phi) and phi > 0): raise ERR_S2_NUMERIC_INVALID
    if not (is_int64(N) and N >= 2):    raise ERR_S2_FINAL_INVALID_N
    if not (is_int64(r) and r >= 0):    raise ERR_S2_FINAL_INVALID_R

    # 1) Non-consuming proof
    if not counters_equal(envelope.before, envelope.after):
        raise ERR_S2_FINAL_CONSUMPTION_DRIFT

    # 2) Construct payload (echo μ,φ exactly)
    payload := {
        merchant_id: m,
        mu: mu,
        dispersion_k: phi,
        n_outlets: N,
        nb_rejections: r,
        nb_r: phi,                                  # optional recommended
        nb_p: phi / (phi + mu)                      # optional recommended
    }

    # 3) Persist exactly one JSONL row
    emit_event(
        stream="nb_final",
        schema="#/rng/events/nb_final",
        partition_keys={seed, parameter_hash, run_id},
        module="1A.nb_sampler",
        substream_label="nb_final",
        envelope=envelope,
        payload=payload
    )
```

---

## 9) Validator joins & downstream usage (binding)

* **Joins:** Validator left-joins `nb_final` to NB **component** streams by `(seed, parameter_hash, run_id, merchant_id)` to (i) prove coverage & ordering, (ii) verify `lambda_t == (mu/dispersion_k) * gamma_value` for each attempt, and (iii) compute corridor metrics externally.
* **Downstream authority:** S3+ read `n_outlets` **from `nb_final`** as the merchant’s **total pre-split** outlet count; they **must not** recompute or reinterpret it.

---

## 10) Conformance tests (KATs)

1. **Echo**: recompute $(\mu,\phi)$ from S2.2 and assert `nb_final.mu`/`dispersion_k` **bit-match** after JSONL round-trip.
2. **Non-consuming**: assert `before==after` for every `nb_final`.
3. **Coverage & cardinality**: assert ≥1 NB `gamma_component` and ≥1 NB `poisson_component` precede exactly one `nb_final` per key.
4. **Dictionary path**: assert all rows live only under the mandated path and schema anchor.

---

## 11) Complexity

O(1) per merchant (field checks + single JSONL write). **No RNG**, no retries.

---

### What changed vs. your draft (quick diff)

* Clarified $N_m$ as **total pre-split** (aligns with S2.4/S4 scale).
* Fixed **module/label** to `1A.nb_sampler` / `nb_final`; `context` intentionally absent.
* Kept event **non-consuming** and made this a hard invariant.
* Added **optional canonical NB** fields (`nb_r`, `nb_p`) computed deterministically from echoed $\mu,\phi$.
* Stated S3+ must read `n_outlets` from **`nb_final`** (persisted authority).

---

# S2.6 — RNG sub-streams & consumption discipline

*(keyed mapping; budgeted/reconciled draws — final)*

## 1) Scope & intent

Guarantee **bit-replay** and **auditability** of the NB sampler by fixing (i) which Philox sub-streams are used for each NB component, (ii) how counters advance and are exposed, and (iii) what evidence is emitted so validators can prove replay and detect any consumption drift. **S2.6 emits no events and draws no RNG**; it governs S2.3/S2.4/S2.5.

---

## 2) Labels, modules, schemas, paths (MUST)

* **NB substreams (disjoint from S4):**

  * Gamma: `substream_label="gamma_nb"`
  * Poisson: `substream_label="poisson_nb"`
  * Final: `substream_label="nb_final"` (**non-consuming**)
* **Module (fixed):** all S2 emissions use `module="1A.nb_sampler"`.
* **Schemas:**

  * Gamma → `schemas.layer1.yaml#/rng/events/gamma_component`
  * Poisson → `schemas.layer1.yaml#/rng/events/poisson_component`
  * Final → `schemas.layer1.yaml#/rng/events/nb_final`
* **Dictionary paths / partitions:**

  * `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
  * `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
  * `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
    Partition keys are **exactly** `["seed","parameter_hash","run_id"]`.

> Notes: (1) We keep the **stream names** (`gamma_component`, `poisson_component`) while distinguishing NB via **substream labels** above; S4 will use e.g. `poisson_ztp`. (2) `context="nb"` is present on component events (not used for mapping); `nb_final` carries **no** `context`.

---

## 3) Deterministic keyed mapping (normative)

All sub-streams are derived with a pure function of lineage + module + substream label + merchant; **attempt index is payload-only** and **never** participates in the key.

1. **Key domain (bytes, no LE64 ambiguity):**

```
D = "ctr:1A"                // ASCII
  || manifest_fingerprint_bytes   // 32 bytes (hex-decoded)
  || seed_bytes                   // 16 bytes if UUID v4; else 8-byte LE if u64
  || parameter_hash_bytes         // 32 bytes (hex-decoded)
  || module                       // ASCII "1A.nb_sampler"
  || substream_label              // ASCII, e.g., "gamma_nb"
  || merchant_id_utf8             // ASCII/UTF-8
```

* **`seed_bytes` canonicalization**: if `seed` is RFC-4122 UUID text, parse to its 16 raw bytes; if numeric, encode as little-endian u64 (8 bytes).
* **All other textual fields** are **UTF-8** as written (no NUL terminators).

2. **Base counter:**
   Interpret `H = SHA256(D)` as a 32-byte digest. Let the **base 128-bit counter** be the first 16 bytes of `H` in **big-endian**:

```
(c_base_hi, c_base_lo) := split64_be( H[0:16] )
```

3. **Uniform i for that (module,label,merchant) substream:**

```
(c_hi, c_lo) = (c_base_hi, c_base_lo + i)   // 128-bit add with carry into hi
```

Mapping is **pure** in `(manifest_fingerprint, seed, parameter_hash, module, substream_label, merchant_id, i)` and independent of attempt order or file layout.

4. **Envelope arithmetic (per event):**

```
(after_hi, after_lo) = (before_hi, before_lo) + draws    // unsigned 128-bit
```

`draws` is the **count of uniforms** consumed by that event.

---

## 4) Uniform & normal primitives (normative)

* **Open-interval uniform (exclusive bounds):**

  $$
    u = \frac{x+1}{2^{64}+1}\in(0,1),\quad x\in\{0,\dots,2^{64}\!-\!1\}
  $$

  **One counter increment ⇒ one uniform.** Do **not** reuse Philox’s spare lane.
* **Standard normal** $Z$ via **Box–Muller**: exactly **2 uniforms per $Z$**; **no caching** of the sine deviate.

All uniforms/normals in **both** samplers (Gamma & Poisson) **must** come from these primitives.

---

## 5) Attempt-level cardinality & ordering (MUST)

For attempt index $t=0,1,2,\dots$ of merchant $m$:

1. Emit **exactly one** `gamma_component` on `gamma_nb`, then
2. **exactly one** `poisson_component` on `poisson_nb`.
   On acceptance (first $K_t\ge2$), emit **exactly one** `nb_final` (label `nb_final`) with **before==after**; **no other NB events** may follow for that merchant.

---

## 6) Draw budgets & reconciliation (normative)

Validators use envelope deltas to compute `draws` and reconcile against algorithmic budgets:

* **Gamma (`gamma_component`, `context="nb"`)**
  For attempt $t$ with shape $\alpha=\phi_m$:

  $$
    \mathrm{draws}^{(\gamma)}_t =
      \begin{cases}
        3 \times J_t, & \alpha \ge 1 \\
        3 \times J_t + 1, & 0 < \alpha < 1
      \end{cases}
  $$

  where $J_t\ge 1$ is the number of MT1998 internal iterations in that attempt.
  **Validator checks:** for $\alpha\ge1$, $\mathrm{draws}^{(\gamma)}_t \bmod 3 = 0$; for $\alpha < 1$, $\mathrm{draws}^{(\gamma)}_t \bmod 3 = 1$.

* **Poisson (`poisson_component`, `context="nb"`)**
  Variable (inversion for $\lambda<10$, PTRS otherwise). **Measured by counters** only; there is no closed-form budget.

* **Final (`nb_final`)**
  **Non-consuming**: `draws = 0` and `before == after`.

Optionally, a compact **`rng_trace_log`** may be emitted per `(module, substream_label)` with the per-stream total `draws` to speed validation; it must equal the sum of event deltas.

---

## 7) Counter discipline (interval semantics)

Within each $(m,\text{substream})$, event intervals are **non-overlapping** and **monotone**:

$$
[c^{(e)}_{\text{before}}, c^{(e)}_{\text{after}}) \cap
[c^{(e+1)}_{\text{before}}, c^{(e+1)}_{\text{after}}) = \varnothing,\quad
c^{(e+1)}_{\text{before}} \ge c^{(e)}_{\text{after}}.
$$

For `nb_final`, enforce **non-consumption** (`before == after`).

---

## 8) Validator contract (replay & discipline proof)

**Replay proof (per merchant):**

1. Collect all NB `gamma_component` and `poisson_component` rows for `(seed, parameter_hash, run_id, merchant_id)` and **enforce interval discipline** per substream.
2. Reconstruct attempts by pairing `attempt=t` (payload) and/or by counter order; enforce **Gamma→Poisson** per $t$.
3. Locate the first $t$ with $K_t\ge2$; join the single `nb_final`; assert:

   * `n_outlets == K_t` and `nb_rejections == t`;
   * `mu, dispersion_k` **echo** S2.2 (bit-exact).

**Discipline checks (hard):**

* **Cardinality:** per $t$, exactly one Gamma and one Poisson; exactly one `nb_final` per merchant key.
* **Budgets:** Gamma per-attempt mod rule above; Poisson totals measured; `nb_final` `draws=0`.
* **Coverage:** `nb_final` implies ≥1 prior NB Gamma **and** NB Poisson with matching lineage.

---

## 9) Failure semantics (run-scoped unless noted)

* **Structural/counter failures** (overlap, non-monotone, or `nb_final` consumption) ⇒ validator **aborts** the run.
* **Schema/coverage/cardinality failures** (missing envelope fields, missing components, duplicate finals) ⇒ **abort**.
* **Corridor breaches** (rejection-rate, p99, CUSUM defined elsewhere) ⇒ **abort** with metrics.

---

## 10) Reference implementation pattern (non-allocating; per merchant)

```pseudo
// Derived substream state (not persisted)
struct Substream { base_hi:u64, base_lo:u64, i:u128 }

// Build base counters once using S2.6 §3
s_gamma := Substream{ base_hi:..., base_lo:..., i:0 }   // label="gamma_nb"
s_pois  := Substream{ base_hi:..., base_lo:..., i:0 }   // label="poisson_nb"

// u01: one uniform, one increment
function u01(s: inout Substream) -> f64:
    (hi, lo) := add128((s.base_hi, s.base_lo), s.i)
    x := philox_lane64(hi, lo)           // 64-bit lane; do not reuse the spare lane
    s.i += 1
    return (x + 1) / (2^64 + 1)

// Writers stamp envelopes using deltas of s.i
function begin_envelope(s): return add128((s.base_hi, s.base_lo), s.i)
function end_envelope(s, draws): return add128((s.base_hi, s.base_lo), s.i + draws)
```

* **Gamma writer** computes `draws_used` = uniforms consumed by MT1998 (including the **+1** for $U^{1/\alpha}$ if $\alpha<1$) and stamps `before/after` with `begin_envelope(s_gamma)` / `end_envelope(s_gamma, draws_used)`, then advances `s_gamma.i += draws_used`.
* **Poisson writer** is analogous with `s_pois`.
* **Final writer** for `nb_final` uses the current counter twice (no increment).

---

## 11) Invariants (MUST)

* **I-NB-REPLAY**: Fixed inputs + mapping ⇒ attempt sequence $(G_t,K_t)$ and acceptance $(N_m,r_m)$ are **bit-identical** across replays.
* **I-NB-U01**: All uniforms satisfy $u\in(0,1)$; normals consume exactly two uniforms.
* **I-NB-CONSUME**: Exactly two component events per attempt; exactly one `nb_final`; counters match deltas; `nb_final` is non-consuming.

---

## 12) Conformance tests (KATs)

1. **Gamma mod rule**: For $\phi\ge1$ assert `draws_gamma_attempt_t % 3 == 0`; for $\phi < 1$ assert `== 1` for every attempt $t$.
2. **Poisson variability**: Use $\lambda=5$ (inversion) and $\lambda=50$ (PTRS); verify positive, non-fixed `draws` deltas and monotone intervals.
3. **Final non-consumption**: Every `nb_final` has `before == after` and `draws=0`.
4. **Interval discipline**: Per $(m,\ell)$, counters are non-overlapping, monotone; reconstruct attempts and join to `nb_final`; fail on any deviation.
5. **Substream disjointness**: Confirm NB labels (`gamma_nb`, `poisson_nb`, `nb_final`) do **not** collide with S4 labels (e.g., `poisson_ztp`) under the mapping.

---

## 13) Complexity

Negligible overhead beyond sampler draws: constant-time 128-bit arithmetic + one JSONL write per event. $O(1)$ memory per merchant (two NB substreams).

---

# S2.7 — Monitoring corridors & thresholds (run gate) — final

## 1) Scope & intent

Compute **run-level** health statistics for the S2 rejection process and **fail the run** if any corridor breaches. Corridors cover:

* overall **rejection rate** (attempt-weighted),
* the **99th percentile** of per-merchant rejections $r_m$,
* a **one-sided CUSUM** for upward drift vs. model-expected behaviour.

This step **consumes no RNG**, **emits no NB events**, and is executed by validation immediately after S2 completes (it may persist its own validation bundle/metrics per the validation spec).

---

## 2) Inclusion criteria (MUST)

Include **only** merchants with a valid S2 finalisation and full coverage:

$$
\mathcal M=\left\{\,m:\ \text{exactly one } \texttt{nb_final} \text{ exists for } m\ \wedge\ \text{coverage tests pass}\,\right\}.
$$

For each $m\in\mathcal M$ read from `nb_final`:

* $r_m=\texttt{nb_rejections}\in\mathbb N_0$,
* $N_m=\texttt{n_outlets}\in\{2,3,\dots\}$,
* $\mu_m=\texttt{mu}>0$, $\phi_m=\texttt{dispersion_k}>0$ (binary64 echo from S2.2).

Merchants without `nb_final` (e.g., numeric aborts in S2.2/2.3) are **excluded** from corridor statistics and tracked separately as health counters. Coverage must already have proved ≥1 NB `gamma_component` and ≥1 NB `poisson_component` for every `nb_final`.

---

## 3) Model acceptance parameter $\alpha_m$ (for CUSUM)

From $(\mu_m,\phi_m)$, compute $\alpha_m=\Pr[K\ge2]$ for an NB2($\mu_m,\phi_m$) attempt.

### 3.1 Stable evaluation (MUST, binary64)

Use algebra that avoids cancellation/overflow:

* Prefer ratios:

  * If $\mu_m \ge \phi_m$:
    $q_m = \frac{1}{1+\phi_m/\mu_m}$, $p_m = 1-q_m$.
  * Else:
    $p_m = \frac{1}{1+\mu_m/\phi_m}$, $q_m = 1-p_m$.
* Log domain:

  * $\log P_0 = \phi_m \cdot \log p_m$, $P_0=\exp(\log P_0)$.
  * $P_1 = P_0 \cdot \phi_m \cdot q_m$ (reuse $P_0$; no second $\exp$).
* Success prob:

  $$
  \boxed{\ \alpha_m = 1 - P_0 - P_1\ }.
  $$

**Guards:** if any intermediate is non-finite, or $\alpha_m \notin (0,1]$, flag `ERR_S2_CORRIDOR_ALPHA_INVALID:m` and **exclude** $m$ from corridors (still counted under health metrics). This should not occur if S2.2 guards held, but is stated to keep corridors well-posed.

---

## 4) Corridor metrics (normative)

Let $a_m=r_m+1$ be total attempts for $m$. Let $M=|\mathcal M|$, and define

$$
R=\sum_{m\in\mathcal M} r_m,\qquad
A=\sum_{m\in\mathcal M} a_m=\sum_{m\in\mathcal M}(r_m+1).
$$

### 4.1 Overall rejection rate $\widehat{\rho}_{\text{rej}}$

$$
\boxed{\,\widehat{\rho}_{\text{rej}}=\frac{R}{A}\,}\in[0,1).
$$

Equivalent form $= 1 - M/A$ is acceptable but **must** yield the same binary64 result for the given data.

### 4.2 99th percentile of rejections $Q_{0.99}$

Sort $r_m$ ascending; **nearest-rank** quantile:

$$
\boxed{\,Q_{0.99} = r_{(\lceil 0.99\,M\rceil)}\,}.
$$

Defined for all $M\ge1$. If $M=0$ ⇒ `ERR_S2_CORRIDOR_EMPTY` (fail run).

### 4.3 One-sided CUSUM (upward drift)

Order merchants by **bytewise ascending `merchant_id`** (deterministic). Standardise residuals of the geometric model:

$$
\mathbb E[r_m]=\frac{1-\alpha_m}{\alpha_m},\quad
\mathrm{Var}(r_m)=\frac{1-\alpha_m}{\alpha_m^2},\quad
z_m=\frac{r_m-\mathbb E[r_m]}{\sqrt{\mathrm{Var}(r_m)}}.
$$

CUSUM:

$$
S_0=0,\quad S_t=\max\{0,\ S_{t-1} + (z_{m_t} - k)\},\quad t=1,\dots,M.
$$

**Policy-driven gates (MUST):** thresholds are **not hard-coded**. Read from the **validation policy artefact**:

* `corridors.max_rejection_rate` (default `0.06`),
* `corridors.max_p99_rejections` (default `3`),
* `cusum.reference_k` (default `0.5`),
* `cusum.threshold_h` (default `8.0`).

If any required value is absent ⇒ **fail closed** with `ERR_S2_CORRIDOR_POLICY_MISSING`.

---

## 5) Pass/fail logic (normative)

The run **passes** S2 corridors iff **all** hold:

1. $\widehat{\rho}_{\text{rej}} \le \texttt{corridors.max_rejection_rate}$,
2. $Q_{0.99} \le \texttt{corridors.max_p99_rejections}$,
3. $\max_t S_t < \texttt{cusum.threshold_h}$.

Otherwise the run **fails**: do **not** write `_passed.flag` for the fingerprint; persist a metrics object enumerating breached gates.

---

## 6) Numerical & data requirements (MUST)

* All arithmetic in **IEEE-754 binary64**.
* Sorting by **merchant_id UTF-8 bytes** (deterministic).
* Duplicate `nb_final` per key or failed coverage ⇒ structural failure upstream; corridors are computed **only** once structure is clean.
* Exclusions (invalid $\alpha_m$) reduce $M$; proceed if $M>0$.

---

## 7) Invariants & evidence (MUST)

* **I-S2.7-ATTEMPT:**

  $$
  A=\sum_{m\in\mathcal M}(r_m+1)=\#\{\text{NB `poisson_component` rows across } \mathcal M\}.
  $$

  Validator **must** reconcile these tallies.
* **I-S2.7-ECHO:** `nb_final.mu`/`dispersion_k` **bit-match** S2.2; `n_outlets`/`nb_rejections` match S2.4 acceptance.
* **I-S2.7-ORDER:** The merchant order used for CUSUM is recorded in the bundle (merchant_id bytes asc.), making $S_{\max}$ reproducible.

---

## 8) Errors & abort semantics

* `ERR_S2_CORRIDOR_EMPTY` — $M=0$; corridors not evaluable ⇒ **fail run**.
* `ERR_S2_CORRIDOR_POLICY_MISSING` — any required policy key absent ⇒ **fail run**.
* `ERR_S2_CORRIDOR_ALPHA_INVALID:{merchant_id}` — $\alpha_m$ invalid; exclude merchant; continue if $M>0$.
* **Breach** of any corridor ⇒ **fail run** with `reason ∈ {"rho_rej","p99","cusum"}` (possibly multiple).

---

## 9) Validator algorithm (reference; no RNG; $O(M\log M)$)

```pseudo
function s2_7_corridors(nb_finals, policy) -> Result:
    # policy must provide: corridors.max_rejection_rate, corridors.max_p99_rejections,
    #                      cusum.reference_k, cusum.threshold_h
    if missing(policy.corridors.max_rejection_rate) or
       missing(policy.corridors.max_p99_rejections) or
       missing(policy.cusum.reference_k) or
       missing(policy.cusum.threshold_h):
        return FAIL(ERR_S2_CORRIDOR_POLICY_MISSING)

    # 1) Build inclusion set with stable alpha_m
    Mset := []
    for row in nb_finals:           # rows that passed structure & coverage
        m  := row.merchant_id
        r  := int64(row.nb_rejections)
        mu := f64(row.mu);  phi := f64(row.dispersion_k)

        # stable p,q
        if mu >= phi:
            q := 1.0 / (1.0 + phi/mu);    p := 1.0 - q
        else:
            p := 1.0 / (1.0 + mu/phi);    q := 1.0 - p

        logP0 := phi * log(p)             # p ∈ (0,1), phi > 0
        P0    := exp(logP0)
        P1    := P0 * phi * q
        alpha := 1.0 - P0 - P1

        if !isfinite(alpha) or alpha <= 0.0 or alpha > 1.0:
            record_warn(ERR_S2_CORRIDOR_ALPHA_INVALID, m)
            continue
        Mset.append({m, r, alpha})

    M := len(Mset)
    if M == 0: return FAIL(ERR_S2_CORRIDOR_EMPTY)

    # 2) Overall rejection rate (attempt-weighted)
    R := sum(each.r for each in Mset)
    A := sum(each.r + 1 for each in Mset)
    rho_hat := R / A

    # 3) p99 of r (nearest-rank)
    r_sorted := sort([each.r for each in Mset])      # asc
    idx := ceil(0.99 * M)            # 1-based rank
    p99 := r_sorted[idx - 1]         # 0-based index

    # 4) One-sided CUSUM
    k := policy.cusum.reference_k
    h := policy.cusum.threshold_h
    Ms := sort(Mset by merchant_id bytes ascending)
    S := 0.0; Smax := 0.0
    for each in Ms:
        Er := (1.0 - each.alpha) / each.alpha
        Vr := (1.0 - each.alpha) / (each.alpha * each.alpha)
        z  := (each.r - Er) / sqrt(Vr)
        S  := max(0.0, S + (z - k))
        Smax := max(Smax, S)

    breaches := []
    if rho_hat > policy.corridors.max_rejection_rate: breaches.append("rho_rej")
    if p99     > policy.corridors.max_p99_rejections: breaches.append("p99")
    if Smax   >= h:                                    breaches.append("cusum")

    if empty(breaches):
        return PASS({rho_hat, p99, Smax, M, R, A})
    else:
        return FAIL({rho_hat, p99, Smax, M, R, A, breaches})
```

**Complexity:** $O(M\log M)$ due to sorting; memory $O(M)$.

---

## 10) Conformance tests (KATs)

* **Determinism:** shuffle input rows; $\widehat{\rho}_{\text{rej}}$ and $Q_{0.99}$ unchanged; $S_{\max}$ unchanged **iff** ordering uses the specified merchant-key bytes asc.
* **Threshold triggers:**

  1. All $r_m=0$ ⇒ pass.
  2. Inject 7% extra rejections uniformly ⇒ expect `rho_rej` breach.
  3. Set 1% of merchants to $r_m=4$ with the rest ≤3 ⇒ expect `p99` breach.
  4. Late-sequence drift above $\mathbb E[r_m]$ ⇒ `cusum` breach once $S_{\max}\ge h$.
* **Numerical guard:** extreme $\mu,\phi$ producing $\alpha$ near 0 or 1 must still compute finite values or be excluded with `ERR_S2_CORRIDOR_ALPHA_INVALID`; proceed if $M>0$.

---

## 11) Outputs

* **Pass:** metrics `{rho_hat, p99, Smax, M, R, A}`; upstream validation may stamp `_passed.flag` (outside this section).
* **Fail:** same metrics + `breaches`; upstream validation **must not** stamp `_passed.flag` and must surface the reasons.

---

# S2.8 — Failure modes (abort semantics, evidence, actions) — final

## 1) Scope & intent

Define **all** conditions under which the S2 NB sampler (multi-site outlet count; **total pre-split** $N_m$) must **abort** (merchant-scoped) or **fail validation** (run-scoped), and the **exact evidence** required to prove/diagnose each failure.

**Authoritative streams & schema anchors (partitioned by `["seed","parameter_hash","run_id"]`):**

* `logs/rng/events/gamma_component/...`  → `#/rng/events/gamma_component`
* `logs/rng/events/poisson_component/...` → `#/rng/events/poisson_component`
* `logs/rng/events/nb_final/...`          → `#/rng/events/nb_final`

**Closed values (must):**

* `module` (all S2 emissions): `"1A.nb_sampler"`.
* `substream_label` (S2 only): `"gamma_nb"`, `"poisson_nb"`, `"nb_final"`.
* `context` (component streams only): `"nb"` (closed set is `{"nb","ztp"}`; `nb_final` has **no** `context`).

---

## 2) Error classes, codes, and actions (normative)

We group failures into **merchant-scoped aborts** (writer stops S2 for that merchant; no further S2 output) and **run-scoped validation fails** (validator **aborts the run** and omits `_passed.flag`).

### A) Merchant-scoped aborts (during S2 execution)

**F-S2.1 — Invalid NB2 parameters (non-finite / non-positive)**

* **Condition:** $\mu_m\le0$ or $\phi_m\le0$ or either predictor/exp is NaN/±Inf.
* **Code:** `ERR_S2_NUMERIC_INVALID`.
* **Action:** **Abort S2 for m**; **no S2.3 events** should be emitted for that merchant.
* **Evidence:** Validator recomputes $(\mu_m,\phi_m)$ from S2.1 inputs + governed artefacts (by `parameter_hash`) and flags `invalid_nb_parameters(m)`.

**F-S2.2 — Sampler numeric invalid**

* **Condition (caught pre-emit):** would produce `gamma_value ≤ 0`, `lambda ≤ 0`, or non-finite; writer must not emit.
* **Code:** `ERR_S2_SAMPLER_NUMERIC_INVALID`.
* **Action:** **Abort S2 for m**; if any bad row was nonetheless written, it will be caught as a run-scoped schema failure (C-S2.3).
* **Evidence:** Writer logs an internal error (out of band); validator sees absence of S2 rows for that merchant (OK) or a schema/domain violation (C-S2.3).

**F-S2.0 — Entry gate violations**

* **Condition:** Missing S1 hurdle record or `is_multi=false` trying to enter S2.
* **Code:** `ERR_S2_ENTRY_MISSING_HURDLE` / `ERR_S2_ENTRY_NOT_MULTI`.
* **Action:** **Skip S2** for merchant $m$.
* **Evidence:** Hurdle stream is authoritative.

---

### B) Run-scoped schema/structure/discipline failures (validator)

**C-S2.1 — Schema violation (any S2 row)**

* **Condition:** Missing envelope fields; wrong types; `context` missing/wrong (`"nb"` required for Gamma/Poisson; **no `context`** on `nb_final`); bad domains (`k<0`, non-finite payloads).
* **Code:** `schema_violation`.
* **Action:** **Abort run**.
* **Evidence:** Per-row schema checks.

**C-S2.2 — Module/label/context misuse**

* **Condition:** `module` ≠ `"1A.nb_sampler"`; or `substream_label` not in `{"gamma_nb","poisson_nb","nb_final"}` for S2; or component `context` ≠ `"nb"`; or any `context` present on `nb_final`.
* **Code:** `label_context_misuse`.
* **Action:** **Abort run**.
* **Evidence:** Envelope/payload inspection vs closed sets above.

**C-S2.3 — Coverage & cardinality gap**

* **Condition:** Any `nb_final` **without** ≥1 prior NB `gamma_component` **and** ≥1 prior NB `poisson_component`; or **duplicate** `nb_final` for the same `(seed, parameter_hash, run_id, merchant_id)`.
* **Code:** `event_coverage_gap`.
* **Action:** **Abort run**.
* **Evidence:** Coverage join across the three streams.

**C-S2.4 — Consumption discipline breach**

* **Condition:** `after < before`; overlapping intervals within a substream; per-attempt cardinality ≠ (exactly 1 Gamma **then** exactly 1 Poisson); `nb_final` advances counters (`before≠after`).
* **Code:** `rng_consumption_violation`.
* **Action:** **Abort run**.
* **Evidence:** Envelope counter scans (monotone, non-overlap, `nb_final` non-consuming).

**C-S2.5 — Attempt indexing violation**

* **Condition:** `attempt` missing on any component; or not starting at 0; or not strictly increasing by 1 up to acceptance $t=r_m$.
* **Code:** `attempt_sequence_violation`.
* **Action:** **Abort run**.
* **Evidence:** Per-merchant scan of component events (Gamma→Poisson pairs).

**C-S2.6 — Composition mismatch (Gamma→Poisson)**

* **Condition:** For any attempt $t$:

  $$
  \lambda_t \stackrel{!}{=} (\mu/\phi)\cdot \texttt{gamma_value}_t
  $$

  with `mu, dispersion_k` from `nb_final`. Equality is **binary64 bit-exact** (or **≤1 ULP** if policy `composition.ulps_tolerance` is provided).
* **Code:** `composition_mismatch`.
* **Action:** **Abort run**.
* **Evidence:** Pair attempts and compare.

**C-S2.7 — Final echo mismatch**

* **Condition:** `nb_final.mu` or `nb_final.dispersion_k` not **bit-exact** echoes of S2.2 outputs.
* **Code:** `final_echo_mismatch`.
* **Action:** **Abort run**.
* **Evidence:** Recompute from S2.1+artefacts and compare bit patterns.

**C-S2.8 — Partition/path misuse**

* **Condition:** Any S2 event written outside its dictionary path or missing required partitions.
* **Code:** `partition_misuse`.
* **Action:** **Abort run**.
* **Evidence:** Path/partition audit.

**C-S2.9 — Branch-purity breach**

* **Condition:** Any S2 NB event for `is_multi=0`.
* **Code:** `branch_purity_violation`.
* **Action:** **Abort run**.
* **Evidence:** Hurdle ↔ S2 cross-check.

---

### C) Run-scoped corridor failures (validator; S2.7)

**D-S2.7 — Corridor breach**

* **Condition:** Any corridor fails (rejection rate, p99, or CUSUM as per policy).
* **Code:** `corridor_breach:{rho_rej|p99|cusum}`.
* **Action:** **Abort run**; persist metrics/trace.
* **Evidence:** S2.7 bundle (`metrics.csv`, CUSUM trace).

---

## 3) Consolidated error code table (normative)

| Code                                      | Scope    | Trigger                                                           | Action    |
|-------------------------------------------|----------|-------------------------------------------------------------------|-----------|
| `ERR_S2_ENTRY_MISSING_HURDLE`             | merchant | no hurdle record                                                  | skip m    |
| `ERR_S2_ENTRY_NOT_MULTI`                  | merchant | hurdle `is_multi=false`                                           | skip m    |
| `ERR_S2_NUMERIC_INVALID`                  | merchant | $\mu\le0$ / $\phi\le0$ / NaN/Inf                                  | abort m   |
| `ERR_S2_SAMPLER_NUMERIC_INVALID`          | merchant | sampler would produce invalid `gamma_value`/`lambda`              | abort m   |
| `schema_violation`                        | run      | schema/domain failure on any row                                  | abort run |
| `label_context_misuse`                    | run      | wrong `module`/`substream_label`/`context` (closed sets violated) | abort run |
| `event_coverage_gap`                      | run      | `nb_final` w/o prior NB Gamma & NB Poisson; or duplicate finals   | abort run |
| `rng_consumption_violation`               | run      | counter overlap/regression; `nb_final` consumes                   | abort run |
| `attempt_sequence_violation`              | run      | `attempt` missing/non-contiguous/non-monotone                     | abort run |
| `composition_mismatch`                    | run      | $\lambda\neq(\mu/\phi)\cdot\gamma_value$                         | abort run |
| `final_echo_mismatch`                     | run      | `nb_final.mu/dispersion_k` not S2.2 echo                          | abort run |
| `partition_misuse`                        | run      | wrong path or missing partitions                                  | abort run |
| `branch_purity_violation`                 | run      | single-site merchant has any S2 events                            | abort run |
| `corridor_breach:{rho_rej, p99, cusum}` | run      | any corridor breach                                               | abort run |

---

## 4) Detection loci & evidence (binding)

1. **Writer (during S2)** — S2.2/2.3/2.5 **raise merchant errors** and **emit nothing further** for that merchant. No partial trails.
2. **Validator (after S2)** — Perform, in order: schema → path/partitions → branch purity → coverage/cardinality → counter discipline → attempt indexing → parameter echo & composition → corridors. **Any** failure ⇒ run fails; bundle is still written (without `_passed.flag`).

---

## 5) Validator reference checklist (O(N log N))

```pseudo
function validate_S2(nb_gamma, nb_pois, nb_final, hurdle, dictionary, policy):
    # 0) Schema & path/partitions
    schema_check_all(nb_gamma, "#/rng/events/gamma_component")
    schema_check_all(nb_pois,  "#/rng/events/poisson_component")
    schema_check_all(nb_final, "#/rng/events/nb_final")
    assert_dictionary_paths_partitions({nb_gamma, nb_pois, nb_final})

    # 1) Module/label/context closed sets
    assert_all(nb_gamma, row => row.module=="1A.nb_sampler" &&
                                row.substream_label=="gamma_nb" &&
                                row.context=="nb")
    assert_all(nb_pois,  row => row.module=="1A.nb_sampler" &&
                                row.substream_label=="poisson_nb" &&
                                row.context=="nb")
    assert_all(nb_final, row => row.module=="1A.nb_sampler" &&
                                row.substream_label=="nb_final" &&
                                !has(row,"context"))

    # 2) Branch purity
    assert_branch_purity(hurdle, {nb_gamma, nb_pois, nb_final})

    # 3) Per-merchant structure
    for key in keys(seed, parameter_hash, run_id, merchant_id):
        A := sort_by_counter(nb_gamma[key]);  B := sort_by_counter(nb_pois[key]);  F := nb_final[key]

        # coverage/cardinality
        assert (len(F) == 1) implies (len(A) >= 1 && len(B) >= 1)

        # counters & non-consumption
        assert_counters_monotone_nonoverlap(A);  assert_counters_monotone_nonoverlap(B)
        assert_final_nonconsuming(F[0])

        # attempt indexing & pairing
        assert_attempts_0_to_r_contiguous(A); assert_attempts_0_to_r_contiguous(B)
        pairwise_attempts(A, B, (a,b) => assert a.attempt == b.attempt)
        assert_pair_order(A,B)   # Gamma then Poisson per attempt

        # composition & final echo
        (mu,phi) := (F[0].mu, F[0].dispersion_k)
        for a in A: assert_ulps_equal(a.alpha, phi, 1)   # or bit-exact if policy=0
        for (a,b) in zip_by_attempt(A,B):
            assert_ulps_equal(b.lambda, (mu/phi)*a.gamma_value, policy.composition.ulps_tolerance or 0)
        t := first_attempt_with_k_ge_2(B)
        assert t exists && F[0].n_outlets == B[t].k && F[0].nb_rejections == t

    # 4) Corridors
    corridors_result := s2_7_corridors(nb_final, policy)
    assert corridors_result.passed
```

---

## 6) Invariants (validator obligations)

* **Echo:** `nb_final.mu/dispersion_k` **equal** S2.2 outputs (binary64).
* **Coverage:** If `nb_final` exists ⇒ ≥1 prior NB Gamma **and** NB Poisson with matching lineage.
* **Consumption:** Exactly two component events per attempt (Gamma→Poisson); counters monotone/ disjoint; `nb_final` non-consuming.
* **Attempting:** `attempt=t` exists for all $t\in\{0,\dots,r_m\}$ and is strictly increasing by 1.

---

## 7) Conformance tests (KATs)

1. **Parameter invalid:** force overflow/underflow in S2.2 so $\mu$ or $\phi$ invalid ⇒ writer aborts merchant; validator sees no S2 rows for that merchant.
2. **Schema:** drop `context` in a Gamma row ⇒ `schema_violation`.
3. **Label/context misuse:** write `substream_label="poisson_component"` or `context="ztp"` in S2 ⇒ `label_context_misuse`.
4. **Coverage:** emit `nb_final` without any Poisson ⇒ `event_coverage_gap`.
5. **Counters:** make `nb_final` advance counters ⇒ `rng_consumption_violation`.
6. **Attempts:** duplicate `attempt=1` or skip `attempt=2` ⇒ `attempt_sequence_violation`.
7. **Composition:** perturb `lambda` by 1+ULP over policy ⇒ `composition_mismatch`.
8. **Partitions:** wrong path or missing `parameter_hash` partition ⇒ `partition_misuse`.
9. **Branch purity:** produce S2 rows for `is_multi=0` ⇒ `branch_purity_violation`.
10. **Corridors:** push $\widehat{\rho}_{rej}> \text{policy.max_rejection_rate}$ ⇒ `corridor_breach:rho_rej`.

---

## 8) Run outcome & artefacts

**Any single hard failure** ⇒ S2 **fails validation**, and therefore **1A fails** for that `manifest_fingerprint`. The validator still writes a bundle to:

```
data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
```

containing `index.json`, `schema_checks.json`, `rng_accounting.json`, `metrics.csv`, diffs. `_passed.flag` is **omitted**. Hand-off to 1B is **blocked** until fixed.

---

**That locks S2.8.** If you want, I can now fold this into your combined stateflow doc so S2 is airtight end-to-end.

---

# S2.9 — Outputs (state boundary) & hand-off to S3 — final

## 1) Scope & intent (normative)

S2 closes by (i) **persisting only the authoritative RNG event streams** for the NB sampler and (ii) exposing the accepted **total pre-split** outlet count $N_m$ (and rejection tally $r_m$) to S3.
**No Parquet/Delta** is written by S2; persistence is **only** via three JSONL **event** streams validated against canonical schema anchors. S3 treats `nb_final` as the **authoritative** source of $N_m$.

---

## 2) Persisted outputs (authoritative RNG event streams)

Write **exactly** these streams, **partitioned** by `["seed","parameter_hash","run_id"]`, using the listed **schema refs**. **Module/labels are closed**; see below.

1. **Gamma components (NB mixture)**

   * **Path:** `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   * **Schema:** `schemas.layer1.yaml#/rng/events/gamma_component`
   * **Module/label/context:** `module="1A.nb_sampler"`, `substream_label="gamma_nb"`, `context="nb"`
   * **Cardinality per multi-site merchant:** **one row per attempt** (≥1 overall).

2. **Poisson components (NB mixture)**

   * **Path:** `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   * **Schema:** `schemas.layer1.yaml#/rng/events/poisson_component`
   * **Module/label/context:** `module="1A.nb_sampler"`, `substream_label="poisson_nb"`, `context="nb"`
   * **Cardinality:** **one row per attempt** (≥1 overall).
   * **Note:** S4 (ZTP) reuses this **stream name** but with **`substream_label="poisson_ztp"`** and `context="ztp"`. Labels keep S2/S4 substreams disjoint.

3. **NB final (accepted outcome)**

   * **Path:** `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   * **Schema:** `schemas.layer1.yaml#/rng/events/nb_final`
   * **Module/label:** `module="1A.nb_sampler"`, `substream_label="nb_final"`
   * **Context:** **none** on `nb_final`
   * **Cardinality:** **exactly 1** row per `(seed, parameter_hash, run_id, merchant_id)`.

**Envelope (MUST on every row):**
`ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}, merchant_id, draws`
(`nb_final` is **non-consuming**: `before == after` and `draws = 0`).

**Payload (MUST):**

* `gamma_component` (NB):
  `{ merchant_id, context: "nb", attempt: <int≥0>, alpha: φ_m, scale: 1.0, gamma_value: <binary64> }`
* `poisson_component` (NB):
  `{ merchant_id, context: "nb", attempt: <int≥0>, lambda: <binary64>, k: <int64≥0> }`
* `nb_final`:
  `{ merchant_id, mu: μ_m, dispersion_k: φ_m, n_outlets: N_m (≥2), nb_rejections: r_m (≥0) }`
  *(Optional, recommended):* `nb_r = dispersion_k`, `nb_p = dispersion_k / (dispersion_k + mu)` (binary64).

**Retention & lineage.** Streams are non-final (180-day retention) and produced by `1A.nb_sampler` (dictionary lineage).

---

## 3) Hand-off to S3 (contract)

For each merchant $m$ with a valid `nb_final`:

$$
\boxed{\,N_m\in\{2,3,\dots\}\,},\qquad \boxed{\,r_m\in\mathbb Z_{\ge0}\,}.
$$

* **Authority:** S3 **must** read $N_m$ from `nb_final.n_outlets`. An in-memory pass of $(N_m,r_m)$ is allowed for efficiency **but is not authoritative**.
* **Downstream use:**

  * **S3 (eligibility):** consumes $N_m$ with `crossborder_eligibility_flags(parameter_hash)` to decide cross-border branch.
  * **S4 (ZTP):** if eligible, may consume $\log N_m$ for foreign counts; it writes its own events (`poisson_ztp`, `context="ztp"`).

---

## 4) Boundary invariants (MUST at S2 exit)

1. **Coverage:** If `nb_final` exists, there are **≥1** NB `gamma_component` **and** **≥1** NB `poisson_component` for the same key; both have `context="nb"`.
2. **Consumption discipline:** Per merchant & label, counter intervals are **monotone, non-overlapping**; `nb_final` is **non-consuming** (`before==after`, `draws=0`).
3. **Composition identity:** For each attempt $t$:
   $\lambda_t = (\mu_m/\phi_m)\cdot \texttt{gamma_value}_t$ (ULP-tight), with $\mu_m,\phi_m$ taken from `nb_final`.
4. **Cardinality & attempts:** Exactly **one** `nb_final` per merchant key; for each attempt, **exactly one** Gamma **then** **exactly one** Poisson; `attempt` starts at 0 and increments by 1 up to $t=r_m$.
5. **Module/labels/contexts (closed sets):**
   `module="1A.nb_sampler"`; component `context ∈ {"nb"}` (no other), `nb_final` has **no** `context`; `substream_label ∈ {"gamma_nb","poisson_nb","nb_final"}`.
6. **Partitions & paths:** All rows live **only** under dictionary paths/partitions; deviation is a hard failure.

---

## 5) Writer reference (idempotent; per merchant)

```pseudo
# Preconditions: m is multi-site; (mu, phi) fixed (S2.2); NB substreams per S2.6.

# Attempt loop (S2.3/S2.4) — per attempt t:
#   emit gamma_component  (module="1A.nb_sampler", label="gamma_nb", context="nb", attempt=t)
#   emit poisson_component(module="1A.nb_sampler", label="poisson_nb", context="nb", attempt=t)

# On first K_t >= 2:
N := K_t      # accepted total pre-split outlet count
r := t        # number of rejections

# Emit final (non-consuming) event (authority for S3):
emit_event(
  stream="nb_final",
  schema="#/rng/events/nb_final",
  module="1A.nb_sampler",
  substream_label="nb_final",
  envelope={..., before==after, draws=0},
  payload={ merchant_id:m, mu:mu, dispersion_k:phi, n_outlets:N, nb_rejections:r,
            nb_r:phi, nb_p:phi/(phi+mu) }   # nb_r/nb_p optional but recommended
)

# Idempotency: enforce uniqueness on (seed, parameter_hash, run_id, merchant_id).
```

---

## 6) Validator obligations at the boundary

Before S3 consumes $N_m$:

* **Schema & path/partitions** pass for all three streams.
* **Coverage, cardinality, counter discipline, attempt indexing** verified.
* **Composition identity & final echo** (`mu`,`dispersion_k`) verified.
* **Corridor gates** (S2.7) pass; otherwise the run fails and S3 must not proceed.

---

## 7) Conformance tests (KATs for S2.9)

1. **Streams present & partitioned:** For every `nb_final`, matching NB `gamma_component`/`poisson_component` rows exist under the same `(seed, parameter_hash, run_id)`; none exist outside dictionary paths.
2. **Final echo & non-consumption:** `nb_final.mu/dispersion_k` bit-match S2.2; `before==after`, `draws=0`.
3. **Reconstruct $(N_m,r_m)$:** Pair attempts by `attempt` (Gamma→Poisson), find first `k>=2`; assert `nb_final.n_outlets==k` and `nb_final.nb_rejections==attempt`.
4. **S3 readiness:** For each multi-site merchant with `nb_final`, `crossborder_eligibility_flags(parameter_hash)` exists; single-site merchants have **no** S2 events.
5. **Label/context closure:** Assert NB component rows use `gamma_nb`/`poisson_nb` with `context="nb"`; `nb_final` carries no `context`; S4 rows (if present) use `poisson_ztp` with `context="ztp"` and do not collide.

---

## 8) Complexity & operational notes

* **I/O:** three append-only JSONL streams; per-merchant volume is $O(\#\text{attempts})$.
* **Memory:** $O(1)$ for finalisation; S3 ingests only $(N_m,r_m)$ but confirms via `nb_final`.
* **Interoperability:** Sharing the Poisson **stream name** between S2 and S4 is safe because **labels** and **contexts** are disjoint, keeping keyed RNG mapping and audits clean.

---

This locks S2.9. If you want, I can now stitch S2.1–S2.9 into your combined stateflow doc so your implementer can lift it straight into reference pseudocode.

---