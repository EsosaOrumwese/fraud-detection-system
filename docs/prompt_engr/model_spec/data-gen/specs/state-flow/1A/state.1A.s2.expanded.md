# S2.1 — Inputs (from S0/S1 + artefacts)

## Goal

Materialise all **deterministic, non-random inputs** needed to parameterise the Negative–Binomial (NB2) model for the domestic **multi-site outlet count** $N_m$ for each merchant $m$ that left S1 with $\texttt{is_multi}(m)=1$. This state constructs the **design vectors**, binds the **coefficient vectors** under the parameter lineage, and fixes the **RNG discipline & event schemas** that S2.3–S2.5 will use. The NB **mean** excludes GDP; the **dispersion** includes $\log(\mathrm{GDPpc})$ as a continuous covariate.

---

## Inputs

For each eligible merchant $m$:

1. **Design vectors** (prepared in S0; re-derived or loaded here for clarity)

$$
\boxed{\,x^{(\mu)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m)\big]^\top\,},\qquad
\boxed{\,x^{(\phi)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \log g_c\big]^\top\,}.
$$

* $\phi_{\mathrm{mcc}}$ and $\phi_{\mathrm{ch}}$ are **fixed categorical encodings** agreed in S0 (e.g., baseline-coded one-hot or effect coding). Whatever basis S0 chose, its dimension and ordering are **frozen** here and must match the coefficient vectors’ layout.
* $g_c>0$ is the **GDP-per-capita** for the merchant’s **home country** $c$, from the pinned WDI vintage specified in S0; S0 guarantees sourcing and versioning. **No GDP enters the mean**, only the dispersion via $\log g_c$.

2. **Coefficient vectors** (from approved artefacts, under `parameter_hash`)

$$
\beta_\mu\in\mathbb{R}^{\dim x^{(\mu)}},\qquad \beta_\phi\in\mathbb{R}^{\dim x^{(\phi)}}.
$$

* Loaded from the vetted YAMLs established in S0; `parameter_hash` is the lineage key for these parameters (distinct from the run fingerprint).

3. **RNG discipline & event schemas** (declared now; consumed later)

* **Generator:** Philox $2{\times}64$-10, with the shared **RNG envelope** (seed, parameter_hash, manifest_fingerprint, module, substream_label, counter_before/after, …).
* **Event streams (schemas & paths fixed by the data dictionary):**

  * `gamma_component` — Gamma draw in the NB mixture,
  * `poisson_component` — Poisson draw given the Gamma,
  * `nb_final` — the accepted NB outcome (after rejection rule).
    All three are **required** for multi-site merchants and will be partitioned per your standard keys.

4. **Numeric policy** (applies to 2.2–2.7 as well)

* IEEE-754 **binary64** evaluation,
* FMA **disabled** where relevant,
* $\log g_c$ defined only if $g_c>0$ (otherwise abort),
* internal uniforms are in the **open interval** $u\in(0,1)$.

---

## Canonical construction (deterministic)

For each merchant $m$ with $\texttt{is_multi}=1$:

1. **Resolve encodings.** Compute $\phi_{\mathrm{mcc}}(\texttt{mcc}_m)$ and $\phi_{\mathrm{ch}}(\texttt{channel}_m)$ using the **exact basis** frozen in S0 (dimension/order must match $\beta$).

2. **Fetch GDPpc.** Look up $g_c$ for home country $c$ from the pinned GDP source. Validate $g_c>0$; else raise `gdp_nonpositive`. Compute $\log g_c$ in binary64.

3. **Assemble design vectors.** Concatenate to form $x^{(\mu)}_m$ and $x^{(\phi)}_m$ exactly as boxed above. **Do not** include GDP (or buckets) in $x^{(\mu)}$.

4. **Bind coefficients.** Load $\beta_\mu,\beta_\phi$ under the active `parameter_hash`; assert **shape equality** with the constructed $x$-vectors.

5. **Record lineage context.** Keep `(merchant_id, parameter_hash, manifest_fingerprint)` attached in memory to these vectors so downstream events can be validated against the same context. (No event is emitted in S2.1; this is **pre-randomisation**.)

---

## Properties & invariants

* **I-S2.1-1 (shape invariance).** $\dim\beta_\mu=\dim x^{(\mu)}_m$ and $\dim\beta_\phi=\dim x^{(\phi)}_m$; violations abort with `design_dim_mismatch`.
* **I-S2.1-2 (GDP legality).** $g_c>0$ must hold; else `gdp_nonpositive` (or `gdp_missing` if not found). $\log g_c$ is evaluated in binary64.
* **I-S2.1-3 (basis immutability).** The categorical bases $\phi_{\mathrm{mcc}},\phi_{\mathrm{ch}}$ are **fixed** by S0; any change triggers a **new** `parameter_hash`.
* **I-S2.1-4 (no RNG yet).** S2.1 **does not consume RNG**; first consumption occurs in S2.3 under declared substreams.

---

## Failure semantics (abort with diagnostics)

* `unknown_mcc(mcc)` or `unknown_channel(channel)` if the encoding basis lacks the key.
* `design_dim_mismatch(expected, got)` if $\beta$ and $x$-vector shapes differ.
* `gdp_missing(country)` or `gdp_nonpositive(value)` if $g_c\le 0$ or absent.
* `invalid_coefficients(nan_or_inf)` if any element of $\beta_\mu$ or $\beta_\phi$ is NaN/Inf.

---

## Determinism & replay

Given fixed S0 artefacts and `parameter_hash`, the mappings $\phi_{\mathrm{mcc}}$, $\phi_{\mathrm{ch}}$ and the series $g_c$ are **byte-stable**, so $x^{(\mu)}_m$ and $x^{(\phi)}_m$ are **deterministic** functions of ingress (`merchant_ids`) and the artefact set. There is **no** RNG dependence in S2.1; the role of S2.1 is to ensure that when S2.3 samples, both parameterisation and lineage are already fixed and auditable.

---

## Minimal reference algorithm (language-agnostic)

```
INPUT:
  merchant_id, mcc, channel, home_country
  basis_mcc, basis_channel   # fixed encoders from S0
  gdp_series                 # pinned to S0 vintage
  beta_mu, beta_phi          # under parameter_hash

OUTPUT:
  x_mu, x_phi                # design vectors for S2.2+

1  v_mcc  := encode(basis_mcc, mcc)          # deterministic; may be sparse
2  v_ch   := encode(basis_channel, channel)  # deterministic
3  g_c    := lookup(gdp_series, home_country)
4  if g_c is None: abort("gdp_missing", home_country)
5  if g_c <= 0:    abort("gdp_nonpositive", g_c)
6  x_mu   := concat([1], v_mcc, v_ch)
7  x_phi  := concat([1], v_mcc, v_ch, [log(g_c)])   # binary64 log
8  if len(x_mu)  != len(beta_mu):  abort("design_dim_mismatch", "mu")
9  if len(x_phi) != len(beta_phi): abort("design_dim_mismatch", "phi")
10 if any_nan_or_inf(beta_mu) or any_nan_or_inf(beta_phi):
       abort("invalid_coefficients")
11 return x_mu, x_phi
```

## Exports (to S2.2+)

* The **design vectors** $x^{(\mu)}_m, x^{(\phi)}_m$ and the bound coefficient vectors $\beta_\mu, \beta_\phi$ (under the active `parameter_hash`) for each multi-site merchant.
* The **lineage triple** `(seed, parameter_hash, manifest_fingerprint)` attached in memory to ensure the RNG events in S2.3–S2.5 can be validated against the same context.

---

# S2.2 — Model parameterisation (NB2)

## Goal

For every merchant $m$ with $\texttt{is_multi}=1$, compute **deterministic** NB2 parameters $(\mu_m,\phi_m)$ from the S2.1 design vectors and coefficient artefacts. These parameters feed the Poisson–Gamma sampler in S2.3 and must be reproducible bit-for-bit under the run’s lineage. The **mean** excludes GDP; the **dispersion** includes $\log(\mathrm{GDPpc})$ as a continuous covariate (fitted with positive slope).

---

## Inputs (from S2.1)

* $x^{(\mu)}_m,\ x^{(\phi)}_m$ — fixed encodings of MCC, channel (and $\log g_c$ for dispersion).
* $\beta_\mu,\ \beta_\phi$ — coefficient vectors under the active `parameter_hash`.
* Numeric policy: IEEE-754 binary64; FMA disabled; no RNG consumed in S2.2.

---

## Canonical construction (log-links, binary64)

Let the linear predictors be

$$
\eta^{(\mu)}_m=\beta_\mu^\top x^{(\mu)}_m,\qquad
\eta^{(\phi)}_m=\beta_\phi^\top x^{(\phi)}_m \quad\text{(binary64 dot products)}.
$$

Apply **log links**:

$$
\boxed{\mu_m=\exp(\eta^{(\mu)}_m)>0},\qquad
\boxed{\phi_m=\exp(\eta^{(\phi)}_m)>0}.
$$

Abort if either exponential underflows/overflows or yields a non-finite number. (This enforces that the NB2 mean/dispersion are strictly positive and well-defined.)

### Equivalent NB(r,p) mapping (derivation only)

It is often convenient to refer to the $(r,p)$ form:

$$
r_m=\phi_m,\qquad p_m=\frac{\phi_m}{\phi_m+\mu_m}.
$$

Under $\mathrm{NB}(r_m,p_m)$, for $k\in\{0,1,2,\dots\}$,

$$
\Pr[N_m=k]
=\binom{k+r_m-1}{k}\,(1-p_m)^k\,p_m^{r_m}
=\binom{k+\phi_m-1}{k}\,\Bigl(\tfrac{\mu_m}{\mu_m+\phi_m}\Bigr)^k\Bigl(\tfrac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m}.
$$

This mapping is used **internally** in S2.3 to justify the Poisson–Gamma construction; S2.2 itself persists nothing.

### Moments and interpretation

$$
\mathbb{E}[N_m]=\mu_m,\qquad
\operatorname{Var}[N_m]=\mu_m+\frac{\mu_m^2}{\phi_m}=\mu_m\Bigl(1+\frac{\mu_m}{\phi_m}\Bigr).
$$

* As $\phi_m\to\infty$, the variance tends to $\mu_m$ (Poisson-like).
* Smaller $\phi_m$ yields heavier tails (more large-$N$ outcomes).
* $\log \phi_m=\beta_\phi^\top x^{(\phi)}_m$ includes $+\eta\log(\mathrm{GDPpc})$ (fitted $\eta>0$), giving a principled way to control dispersion by macro signal while keeping the mean parsimonious.

---

## Numerical guards and stability (hard aborts, no silent clipping)

Evaluate $\eta$ and $\exp(\eta)$ in **binary64**. Abort S2.2 for merchant $m$ with:

* `invalid_nb_parameters` if $\eta$ is NaN/Inf *or* $\exp(\eta)$ over/under-flows (i.e., becomes 0 or Inf in binary64).
* `nonpositive_nb_parameters` if $\mu_m\le 0$ or $\phi_m\le 0$ (should be impossible with the log link unless overflow/underflow occurred).
* `design_dim_mismatch` if shapes of $\beta$ and $x$ differ (enforced already by S2.1).

*Rationale:* determinism + auditability. We do **not** clip $\eta$ to “safe” bands; we fail loudly so the validation bundle can capture the offending rows and artefact versions. (Downstream NB events must therefore never appear for a merchant that failed S2.2.)

---

## Determinism & lineage

Given fixed ingress, encoders, GDP series and the parameter artefacts under a specific `parameter_hash`, $(\mu_m,\phi_m)$ are **pure functions** of S2.1 inputs and contain **no** RNG. They must be the same across replays and are later echoed inside `nb_final` event payloads to bind stochastic draws to their parameterisation.

---

## Outputs (expanded, explicit)

S2.2 itself is a **pure parameter stage**; it emits **no datasets**. However, to make downstream behaviour unambiguous and easy to validate, S2.2 yields—**in memory**—the following **export tuple** per merchant $m$, which S2.3–S2.5 must consume and (partially) echo:

### O-1. Parameter tuple (mandatory, in-memory)

$$
\boxed{\ (\mu_m,\ \phi_m,\ \eta^{(\mu)}_m,\ \eta^{(\phi)}_m)\ }.
$$

* $\mu_m$ and $\phi_m$ are required sampler inputs in S2.3.
* $\eta$-values are retained for **debug diagnostics** (not persisted by default) to enable post-hoc sanity checks (e.g., range checks in the validation bundle).

### O-2. Derived NB(r,p) terms (derivation-only, optional in-memory)

$$
\boxed{\ r_m=\phi_m,\quad p_m=\phi_m/(\phi_m+\mu_m)\ }.
$$

These are **not persisted** by S2.2 but may be computed by S2.3 for logging clarity (e.g., when reconciling sampler internals).

### O-3. Context lineage (mandatory, in-memory)

Attach the **lineage triple** to O-1/O-2:

$$
\boxed{(\texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})},
$$

plus immutable IDs (merchant_id) and model identifiers (module/substream labels) so that any event later **unambiguously** maps back to these parameters. The same keys appear in the RNG envelope for S2.3–S2.5 events.

### O-4. Downstream echo requirements (authoritative event payload fields)

S2.3–S2.5 must **echo** the S2.2 parameters in the final acceptance event:

* `nb_final` event **must** include:

  * `mu = μ_m`,
  * `dispersion_k = φ_m`,
  * as well as `n_outlets` (the accepted $N_m$) and `nb_rejections` (attempt count).
    These fields are **required** by the schema and are validated during replay.

### O-5. Validation-bundle probes (computed later but sourced here)

The validator (post-egress) derives health metrics that implicitly depend on S2.2 outputs—e.g., histograms/quantiles of $\eta^{(\mu)}$, $\eta^{(\phi)}$, $\log \mu$, $\log \phi$, and dispersion index $(1+\mu/\phi)$—and writes them into the **validation bundle** keyed by `fingerprint`. Including $\mu$ and $\phi$ inside `nb_final` allows the validator to recompute moments and compare against empirical $N$ draws merchant-by-merchant.

### O-6. Schema touchpoints (where S2.2 values appear)

* **RNG events (JSONL):**

  * `nb_final` includes `mu` and `dispersion_k`.
  * `gamma_component` / `poisson_component` do **not** echo $\mu$ or $\phi$ directly; they log the sampled values (`gamma_value`, `lambda`, `k`) under context `"nb"`, and the validator binds them to $(\mu,\phi)$ via the shared envelope keys.
* **Datasets:** S2.2 does not persist parameters to Parquet; only later egress (`outlet_catalogue`) and parameter-scoped artefacts appear on disk. (Keeping S2.2 ephemeral reduces I/O and eliminates version-skew risk.)

### O-7. Explicit invariants to assert before sampling

Before S2.3 consumes O-1, assert:

1. $\mu_m>0$ and $\phi_m>0$ (strict).
2. $\operatorname{Var}[N_m]=\mu_m+\mu_m^2/\phi_m \ge \mu_m$ (implied by positivity; can be checked to catch sign/scale regressions).
3. **Dimension lock:** $\dim \beta_\mu=\dim x^{(\mu)}_m$, $\dim \beta_\phi=\dim x^{(\phi)}_m$ (already enforced in S2.1).
4. **No RNG consumed** so far for $m$; the first RNG events must be the S2.3 component draws (`gamma_component`, `poisson_component`).

---

## Minimal reference algorithm (unchanged, now with explicit outputs)

```
INPUT:
  x_mu, x_phi          # from S2.1
  beta_mu, beta_phi    # under parameter_hash
  seed, parameter_hash, manifest_fingerprint, merchant_id
OUTPUT (in-memory, per-merchant):
  mu, phi              # NB2 parameters (mandatory)
  eta_mu, eta_phi      # linear predictors (for diagnostics)
  # optional (derivation-only):
  r = phi
  p = phi / (phi + mu)
  # lineage context retained with the tuple

1  eta_mu  := dot(beta_mu,  x_mu)            # binary64, FMA off
2  eta_phi := dot(beta_phi, x_phi)           # binary64, FMA off
3  mu  := exp(eta_mu)
4  phi := exp(eta_phi)
5  if not isfinite(mu) or mu <= 0:   abort("invalid_nb_parameters")
6  if not isfinite(phi) or phi <= 0: abort("invalid_nb_parameters")
7  # Optional: compute r, p for downstream clarity (not persisted here)
8  return (mu, phi, eta_mu, eta_phi)  # plus attached lineage & IDs
```

Downstream, **S2.5 `nb_final` must echo `mu` and `dispersion_k=phi`** alongside the realised $N$ and the rejection count to complete the audit chain. The event schemas and dataset dictionary already enforce these fields and their partitioning/lineage.

---

## Why this structure works

* **Auditability:** Embedding $(\mu,\phi)$ in `nb_final` makes it trivial for validation to recompute the NB pmf and verify that the `gamma_component` + `poisson_component` draws were coherent under the same parameters.
* **Determinism:** No RNG is touched here; any change in $(\mu,\phi)$ across runs must trace back to artefacts (`parameter_hash`) or ingress—picked up by your lineage system (`manifest_fingerprint` vs `parameter_hash`).
* **Tight interfaces:** S2.2 exports just enough to parameterise sampling, and nothing more—avoiding “dual sources of truth” between parameters and events. The only persisted echoes are where the schemas require them.

---



# S2.3 — Sampling theorem & construction (Poisson–Gamma)

## Goal

Generate a **single NB2 attempt** for merchant $m$ with parameters $(\mu_m,\phi_m)$ from S2.2 by composing one **Gamma** draw and one **Poisson** draw, and **log both** as authoritative RNG events with the shared envelope. These component events are required upstream of the final acceptance record (`nb_final`) and are partitioned/validated exactly as specified in the dataset dictionary and layer schemas.

---

## Inputs (from S2.2, S0)

* NB2 parameters $(\mu_m>0,\ \phi_m>0)$.
* Lineage triple: `(seed, parameter_hash, manifest_fingerprint)` and module/substream labels.
* **Event schemas & paths** (authoritative):
  `logs/rng/events/gamma_component/...`, schema `#/rng/events/gamma_component`;
  `logs/rng/events/poisson_component/...`, schema `#/rng/events/poisson_component`.

---

## Theorem (composition ⇒ NB2)

Let $G\sim\mathrm{Gamma}(\alpha=\phi_m,\mathrm{scale}=1)$ and, conditional on $G$, let

$$
K\mid G \sim \mathrm{Poisson}\!\left(\lambda=\frac{\mu_m}{\phi_m}\,G\right).
$$

Then the **marginal** distribution of $K$ is Negative–Binomial with mean $\mu_m$ and dispersion $\phi_m$ (NB2): $\mathbb{E}[K]=\mu_m$, $\mathrm{Var}[K]=\mu_m+\mu_m^2/\phi_m$. This is the canonical Poisson–Gamma mixture construction underlying our sampler.

**Proof sketch (for the record).**
Using the Gamma pdf $f_G(g)=\frac{1}{\Gamma(\phi_m)}g^{\phi_m-1}e^{-g}$ and Poisson pmf, integrate:

$$
\Pr(K=k)
=\int_0^\infty e^{-(\mu/\phi)g}\frac{[(\mu/\phi)g]^k}{k!}\cdot \frac{g^{\phi-1}e^{-g}}{\Gamma(\phi)}\,dg
=\frac{\Gamma(k+\phi)}{k!\,\Gamma(\phi)}\left(\frac{\mu}{\mu+\phi}\right)^k
\left(\frac{\phi}{\mu+\phi}\right)^\phi,
$$

the NB(r, p) pmf with $r=\phi$, $p=\phi/(\mu+\phi)$, which is equivalent to NB2. (We do **not** persist $(r,p)$; they are derivational.)

---

## Construction (one attempt) — events and payloads

### 1) Gamma step (context = `"nb"`)

Draw

$$
G \sim \mathrm{Gamma}\big(\alpha=\phi_m,\ \mathrm{scale}=1\big),\quad G>0.
$$

Emit **one** JSONL record to
`logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
with the **shared RNG envelope** (ts/seed/parameter_hash/manifest_fingerprint/module/substream + counters) and payload:

$$
\{\ \texttt{merchant_id},\ \texttt{context}=\text{"nb"},\ \texttt{index}=0,\ \alpha=\phi_m,\ \texttt{gamma_value}=G\ \}.
$$

Schema `#/rng/events/gamma_component` **requires** `merchant_id, context, index, alpha, gamma_value`; `alpha` and `gamma_value` must be strictly positive.

### 2) Poisson step (context = `"nb"`)

Form $\lambda=(\mu_m/\phi_m)\,G$ in binary64, $\lambda>0$, then draw

$$
K \sim \mathrm{Poisson}(\lambda),\quad K\in\{0,1,2,\dots\}.
$$

Emit **one** JSONL record to
`logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
with the same envelope and payload:

$$
\{\ \texttt{merchant_id},\ \texttt{context}=\text{"nb"},\ \lambda,\ \ k=K\ \}.
$$

Schema `#/rng/events/poisson_component` **requires** `merchant_id, context, lambda, k` with $\lambda>0$.

**Uniform policy & counters.**
All uniforms used inside the Gamma/Poisson samplers are on the **open interval** $u\in(0,1)$ per primitive `u01`. Exact consumption is evidenced by the **pre/post counter** fields in the envelope; these are mandatory and identical across all RNG events.

---

## RNG substreams & labels (attempt discipline)

* Substream labels for this state:
  $\ell_\gamma=$"gamma_component", $\ell_\pi=$"poisson_component".
  **Per attempt**: emit **exactly one** `gamma_component` and **exactly one** `poisson_component`; `nb_final` appears **once** on acceptance (S2.5).
* The envelope’s counter fields (`rng_counter_before_*`, `rng_counter_after_*`) prove replay and bound consumption. Substream strides are defined by S0 and not duplicated in payloads.

---

## Numerical policy (guards; no silent clipping)

* Evaluate $\lambda=(\mu/\phi)\,G$ in **binary64**. Abort the attempt if $\lambda$ is non-finite or $\le 0$ (should not occur with positive inputs), raising `invalid_poisson_rate`.
* `gamma_value` must be $>0$; `alpha=\phi_m>0` by construction from S2.2.
* All uniforms used internally satisfy `u01` (exclusive bounds). Schema enforcement + envelope counters make this auditable.

---

## Determinism & invariants (specific to S2.3)

* **I-NB1 (bit-replay).** For fixed $(x^{(\mu)},x^{(\phi)},\beta_\mu,\beta_\phi,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the sequence $(G_t,K_t)$ across attempts and the accepted pair are **bit-identical** on replay (counter-based Philox + fixed labels + fixed one-gamma/one-poisson per attempt).
* **I-NB2 (schema conformance).** Every `gamma_component` has the required fields with `context="nb"`, `index=0`; every `poisson_component` has `context="nb"`, `lambda>0`, `k∈ℕ`. `nb_final` (S2.5) must echo `mu` and `dispersion_k` in addition to the realised $N$ and rejection count. Missing any required event is a **structural failure**.
* **I-NB3 (open-interval uniforms).** All underlying uniforms are $u\in(0,1)$ per `u01`; envelope counters expose consumption.
* **I-NB4 (event coverage).** A merchant with `nb_final` **must** have at least one preceding `gamma_component` and one `poisson_component` with matching envelope keys. Validation enforces this join.

---

## Failure semantics (abort with diagnostics)

* `invalid_nb_parameters` if S2.2 delivered non-finite or non-positive $(\mu,\phi)$ (caught earlier but rechecked defensively).
* `invalid_poisson_rate` if $\lambda$ non-finite or $\le 0$.
* `schema_violation` if any required envelope field or payload key is missing / out of bounds (e.g., `gamma_value≤0`, `context∉{"nb","dirichlet"}` for gamma; `context∉{"nb","ztp"}` for Poisson).
* `event_coverage_gap` if a `nb_final` event is later observed without at least one gamma & one Poisson component for the same envelope keys.

---

## Minimal reference algorithm (one attempt; language-agnostic)

```
INPUT:
  mu > 0, phi > 0        # from S2.2
  merchant_id
  seed, parameter_hash, manifest_fingerprint, run_id
  substreams: "gamma_component", "poisson_component"

OUTPUT (per attempt):
  G, lambda, K           # plus two JSONL event rows (gamma, poisson)

# 1) Gamma component (context="nb")
1  G := sample_gamma(shape=phi, scale=1)     # binary64; u01 uniforms internally
2  assert isfinite(G) and G > 0
3  emit_event("gamma_component",
       envelope=...,                         # rng envelope with counters
       payload={merchant_id, context="nb", index=0, alpha=phi, gamma_value=G})

# 2) Poisson component (context="nb")
4  lambda := (mu/phi) * G                    # binary64
5  assert isfinite(lambda) and lambda > 0
6  K := sample_poisson(lambda)               # u01 uniforms internally (open interval)
7  emit_event("poisson_component",
       envelope=...,
       payload={merchant_id, context="nb", lambda=lambda, k=K})

8  return (G, lambda, K)
```

Notes: a **single** attempt always produces exactly **two** component events (gamma + poisson). If S2.4 accepts $K\ge 2$, S2.5 will emit exactly one `nb_final` with `mu`, `dispersion_k`, `n_outlets`, `nb_rejections`.

---

## Outputs (expanded & explicit)

### O-1. Authoritative component event streams (required)

* `gamma_component` (≥1 row per merchant across attempts; exactly 1 per attempt), schema `#/rng/events/gamma_component`.
  Required payload: `merchant_id`, `context="nb"`, `index=0`, `alpha=φ_m>0`, `gamma_value=G>0`.
  Partitions: `seed`, `parameter_hash`, `run_id`.
* `poisson_component` (≥1 row per merchant across attempts; exactly 1 per attempt), schema `#/rng/events/poisson_component`.
  Required payload: `merchant_id`, `context="nb"`, `lambda>0`, `k∈ℕ`.
  Partitions: `seed`, `parameter_hash`, `run_id`.

### O-2. Envelope keys (must be present and consistent)

Every event record carries the **RNG envelope** fields:
`ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}, merchant_id`. These are **required** by `schemas.layer1.yaml` and bind component events to the run lineage and counter state.

### O-3. In-memory attempt tuple (for S2.4)

For each attempt, we hand S2.4 the tuple $(G,\lambda,K)$ along with an **attempt index** $t\in\{0,1,2,\dots\}$ (internal; not logged in payloads for NB) so S2.4 can enforce the rejection rule and count rejections deterministically. On acceptance ( $K\ge 2$ ), S2.5 emits the **single** `nb_final` row that **echoes** `mu` and `dispersion_k` from S2.2.

---

## Where S2.3 sits in the larger contract

* S2.3 **only** performs “one-attempt” component draws and logging. Acceptance/retries belong to **S2.4**, and finalisation to **S2.5**.
* Validation later checks: (i) presence of at least one gamma & one poisson event for each merchant with `nb_final`; (ii) schema conformance; (iii) counters’ monotone advance; and (iv) corridor metrics for rejections.

---

# S2.4 — Rejection rule (multi-site constraint $N\ge 2$)

## Goal

Convert a **single NB attempt** from S2.3 into an **accepted** domestic outlet count $N_m\in\{2,3,\dots\}$ by **rejecting** outcomes $K\in\{0,1\}$. Count deterministic retries $r_m$ (number of rejected attempts before the first success). Corridor checks (overall rejection ≤ 0.06; per-merchant p99 of $r_m$ ≤ 3; plus a one-sided CUSUM against baseline) are enforced by validation; violations abort the run with metrics written to the bundle.

---

## Inputs (from S2.2–S2.3 + lineage)

* $(\mu_m,\phi_m)$ from S2.2 (positivity already enforced).
* The **attempt generator** of S2.3: each attempt yields $(G_t,\lambda_t,K_t)$ via the Gamma→Poisson composition (and logs exactly one `gamma_component` and one `poisson_component`). No extra RNG is consumed in S2.4 itself.
* Lineage keys carried in the shared RNG envelope (seed, parameter_hash, manifest_fingerprint, module, substream, pre/post counters).

---

## Acceptance process (formal)

For attempts $t=0,1,2,\dots$:

$$
G_t\sim\Gamma(\phi_m,1),\quad 
\lambda_t=\tfrac{\mu_m}{\phi_m}G_t,\quad 
K_t\sim\mathrm{Poisson}(\lambda_t).
$$

Accept the **first** $t$ with $K_t\ge 2$. Set

$$
\boxed{\,N_m=K_t,\qquad r_m=t\,}.
$$

If $K_t\in\{0,1\}$, **reject** and continue with the same merchant’s substreams (envelope counters advance deterministically per attempt).

**Independence & geometry.** Each attempt samples an i.i.d. NB2 variate via the same $(\mu_m,\phi_m)$. Let the **per-attempt acceptance probability** be

$$
\alpha_m\;=\;\Pr[K\ge 2]
\;=\;1-\Pr[K=0]-\Pr[K=1],
$$

with NB2 pmf

$$
\Pr[K=k]=\binom{k+\phi_m-1}{k}
\Bigl(\frac{\mu_m}{\mu_m+\phi_m}\Bigr)^k\!
\Bigl(\frac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m}.
$$

Hence

$$
\Pr[K=0]=\Bigl(\tfrac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m},\quad
\Pr[K=1]=
\phi_m\cdot\frac{\mu_m}{\mu_m+\phi_m}\cdot
\Bigl(\tfrac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m}.
$$

Then the **rejection count** $r_m$ is geometric (failures before first success) with success probability $\alpha_m$:

$$
\Pr[r_m=r]=(1-\alpha_m)^{r}\alpha_m,\quad
\mathbb{E}[r_m]=\frac{1-\alpha_m}{\alpha_m},\quad
r_{m,\;q}=\Bigl\lceil \frac{\ln(1-q)}{\ln(1-\alpha_m)}\Bigr\rceil-1.
$$

These relations are *not* persisted; they justify corridor tuning and validator expectations.

---

## Attempt loop (canonical construction)

1. **Pull one attempt from S2.3.** Consume **exactly one** `gamma_component` and **one** `poisson_component` (context="nb"); both have already been emitted with the RNG envelope.
2. **Check acceptance.**

   * If $K\ge 2$: **accept** with $N_m\leftarrow K$; set $r_m$ to the number of prior rejections.
   * Else ($K\in\{0,1\}$): **reject** and iterate (advancing counters deterministically per attempt).
3. **No hard cap in S2.4.** Progress is guaranteed almost surely because $\alpha_m>0$ for finite $\mu_m>0,\phi_m>0$; release safety is provided by the **corridor gates** (see below).

> **Consumption discipline.** Per attempt: **two** component events (Gamma, Poisson). At acceptance: later **one** `nb_final` event in S2.5. Envelope counters and label names prove replay.

---

## Monitoring corridors (validation obligations)

All corridor metrics are computed **post-run** by the validator and written into `validation_bundle_1A(fingerprint)/metrics.csv`; failures abort the run and suppress `_passed.flag`.

### C-1. Overall NB rejection rate

Let attempts for merchant $m$ equal $T_m=r_m+1$. Define

$$
\widehat{\rho}_{\text{rej}}
=\frac{\sum_m r_m}{\sum_m T_m}
=\frac{\sum_m r_m}{\sum_m (r_m+1)}.
$$

**Requirement:** $\widehat{\rho}_{\text{rej}}\le 0.06$. (Averaged over all NB attempts in the run.)

### C-2. Per-merchant p99 of rejections

Let $\{r_m\}$ be the multiset of rejection counts over multi-site merchants. Define the **empirical** 0.99-quantile:

$$
\widehat{Q}_{0.99}=\inf\{x:\tfrac{1}{|\mathcal{M}_{\text{multi}}|}\sum_m \mathbf{1}(r_m\le x)\ge 0.99\}.
$$

**Requirement:** $\widehat{Q}_{0.99}\le 3$. (I.e., at least 99% of multi-site merchants accept within ≤3 rejections.)

### C-3. One-sided CUSUM gate (drift early-warning)

Form a time-ordered sequence of **attempt-level indicators** $Z_t=\mathbf{1}\{\text{rejection}\}$ across all NB attempts (the validator uses event emission time / file order). Given a **baseline** rejection probability $b$ (from prior approved runs or config), run the one-sided CUSUM:

$$
S_0=0,\quad S_t=\max\bigl\{0,\ S_{t-1}+ (Z_t - b)-k\bigr\}.
$$

Trip the gate if $S_t\ge h$. Here $k$ (reference value) and $h$ (decision limit) are configured in the validation policy and recorded in the bundle index; they set the targeted ARL and detectable shift $\Delta$. **Violation:** abort with metrics & plots embedded in the bundle.

---

## Outputs (from S2.4 to S2.5 and the validator)

### O-1. In-memory acceptance tuple (to S2.5)

$$
\boxed{\, (N_m,\ r_m)\ \text{ with } N_m\in\{2,3,\dots\}\, }.
$$

This is the **only** stateful export of S2.4. S2.5 will emit `nb_final` echoing $\mu_m,\phi_m$ and recording `n_outlets=N_m`, `nb_rejections=r_m`.

### O-2. Authoritative event coverage (evidence)

S2.4 itself writes **no** new event rows; it **requires**:

* For the accepted merchant, **≥1** `gamma_component` and **≥1** `poisson_component` (context="nb") preceding the single `nb_final` of S2.5 under matching envelopes. Missing any of these is a structural failure.

### O-3. Corridor metrics (validator outputs)

The validator computes $\widehat{\rho}_{\text{rej}}$, $\widehat{Q}_{0.99}$, and the CUSUM trace, and persists them in `validation_bundle_1A(fingerprint)`; failure ⇒ no `_passed.flag`.

---

## Determinism & invariants (S2.4-specific)

* **I-NB-A (bit replay).** Fixed inputs and Philox counters imply that the sequence $(G_t,K_t)_{t\ge 0}$, the accepted pair $(N_m,r_m)$, and the set of component events are **bit-reproducible**. Exactly two component events per attempt; exactly one `nb_final` at acceptance.
* **I-NB-B (schema conformance across S2).** Component events conform to `gamma_component` / `poisson_component` schemas; `nb_final` (S2.5) must include `mu`, `dispersion_k`, `n_outlets`, `nb_rejections`.
* **I-NB-C (open-interval uniforms).** All uniforms used by the underlying samplers satisfy $u\in(0,1)$ and are evidenced by pre/post counters in the envelope.

---

## Failure semantics (abort with diagnostics)

* **Corridor breach:** If either $\widehat{\rho}_{\text{rej}}>0.06$ or $\widehat{Q}_{0.99}>3$, or the CUSUM gate trips, the validator aborts the run and writes metrics/plots to the bundle.
* **Schema violation / coverage gap:** Presence of `nb_final` without the required component events (or envelope mismatch) ⇒ structural failure.
* **Numeric/pathological:** Defensive re-checks from S2.2/2.3 (e.g., non-finite $\mu,\phi,\lambda$)—should not arise here, but any such event triggers `invalid_nb_parameters`/`invalid_poisson_rate` upstream and is caught by schema & replay checks.

---

## Minimal reference algorithm (attempt loop; language-agnostic)

```
INPUT:
  mu > 0, phi > 0                 # from S2.2
  merchant_id
  seed, parameter_hash, manifest_fingerprint, run_id
  substreams: "gamma_component", "poisson_component"

OUTPUT:
  N, r                             # accepted N>=2 and rejection count

t := 0
while true:
    # -- S2.3 emits both events with full RNG envelope --
    (G, lambda, K) := one_nb_attempt_via_poisson_gamma(mu, phi, merchant_id, envelope)

    if K >= 2:
        N := K
        r := t
        break
    else:
        t := t + 1                 # reject and continue

return (N, r)                      # S2.5 will emit nb_final with (mu, phi, N, r)
```

* **Per attempt**: exactly **one** `gamma_component` + **one** `poisson_component`.
* **At acceptance**: S2.5 emits exactly **one** `nb_final` with required fields (`mu`, `dispersion_k`, `n_outlets`, `nb_rejections`).

## Why this design is robust

* It enforces the **business constraint** (“multi-site ⇒ at least 2 outlets”) without biasing the NB tail—simple truncation by rejection.
* The **geometric** structure makes corridor setting transparent: for most merchants, $\alpha_m$ is high, so $r_m$ concentrates on $\{0,1,2,3\}$, matching the p99≤3 design target.
* Full **auditability**: every attempt leaves two component events; acceptance leaves one final event echoing parameters. The validator can account counters, recompute pmfs, and flag drift instantly in the bundle.

---

# S2.5 — Finalisation event (`nb_final`)

## Goal

When S2.4 accepts a draw $N_m\ge 2$ (with $r_m$ rejections), emit **exactly one** authoritative event row that *binds* the realised count to its NB2 parameters $(\mu_m,\phi_m)$. This closes the NB trail (Gamma → Poisson → acceptance) and gives the validator a single place to read the outcome and the parameters that produced it. The dataset dictionary fixes the output path, partitions, and schema reference.

---

## Inputs (from earlier states)

* Parameters from **S2.2**: $\mu_m>0,\ \phi_m>0$.
* Accepted outcome from **S2.4**: $N_m\in\{2,3,\dots\}$, rejection count $r_m\in\{0,1,2,\dots\}$.
* Lineage & RNG envelope (S0): `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, `module`, `substream_label`, and Philox **pre/post counters**. (S2.5 does **not** consume RNG; counters remain unchanged across this emission.)

---

## Canonical construction (one merchant, one row)

**Emission target (fixed by the dictionary):**

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

Schema reference: `schemas.layer1.yaml#/rng/events/nb_final`. Partition keys: `["seed","parameter_hash","run_id"]`.

**Payload (required fields):**

$$
\boxed{\ \{\ \texttt{merchant_id},\ \mu=\mu_m,\ \texttt{dispersion_k}=\phi_m,\ \texttt{n_outlets}=N_m,\ \texttt{nb_rejections}=r_m\ \}\ }.
$$

The schema **requires** all five fields above. Types/constraints:

* `mu`, `dispersion_k` are positive binary64 scalars;
* `n_outlets` is an integer $\ge 2$;
* `nb_rejections` is an integer $\ge 0$.

**Envelope (required on every event row):**
`ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}, merchant_id`. (Counters prove *no* extra RNG was consumed here: `before == after`.)

---

## Event coverage & ordering rules

* **Coverage invariant (hard):** if a merchant emits `nb_final`, there must exist **≥1** prior `gamma_component` and **≥1** prior `poisson_component` entries (context `"nb"`) with matching envelope keys `(seed, parameter_hash, run_id, merchant_id)`. Missing either is a **structural failure**.
* **Cardinality invariant (hard):** **exactly one** `nb_final` per `(seed, parameter_hash, run_id, merchant_id)`. The validator rejects duplicates. (By design, S2.4 accepts once, and S2.5 emits once.)
* **Ordering note:** JSONL files are append-only; strict temporal ordering is not required, but the validator can sort by `ts_utc` and/or compare RNG counters to confirm “Gamma → Poisson → Final” consistency.

---

## Determinism & invariants (S2.5-specific)

* **No RNG consumption.** S2.5 never advances Philox; envelope counters should be unchanged from the last consumed value in S2.4. (The validator checks `before == after` here.)
* **Echo-of-parameters.** `mu` and `dispersion_k` **must** equal the S2.2 values used to produce the component draws; mismatches are a schema/consistency failure during validation joins.
* **Domain checks.** Enforce `n_outlets ≥ 2`, `nb_rejections ≥ 0`, and positivity of `mu`, `dispersion_k`. (Non-positive values imply upstream failure and must not pass schema.)

---

## Failure semantics (abort with diagnostics)

* **Schema violation:** missing any required payload key, wrong type/domain, or missing envelope fields ⇒ `schema_violation`.
* **Coverage gap:** presence of `nb_final` without matching `gamma_component` **and** `poisson_component` (context `"nb"`) ⇒ structural failure.
* **Duplicate finals:** more than one `nb_final` for a `(seed, parameter_hash, run_id, merchant_id)` key ⇒ structural failure; validator reports the duplicates and aborts.

---

## Outputs (what S2.5 “exports”)

### O-1. Authoritative final event stream (persisted)

A single JSONL row per accepted merchant in:

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

Schema: `#/rng/events/nb_final`. This stream is consumed by the **validation bundle** generator and is part of S2’s state boundary.

### O-2. Downstream state (in-memory to S3+)

* $N_m$ and $r_m$ are carried forward for cross-border gating and later allocation steps; no additional writes occur here. The next persisted datasets (e.g., `country_set`, `ranking_residual_cache`, `outlet_catalogue`) live in subsequent states and have their own partition contracts.

### O-3. Validator joins (how this is used)

* The validator joins `nb_final` to `gamma_component` and `poisson_component` via the envelope keys to recompute NB likelihoods and to populate the **S2 corridor metrics** that are ultimately stored under `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`.

---

## Minimal reference algorithm (language-agnostic)

```
INPUT:
  merchant_id
  mu > 0, phi > 0               # from S2.2
  N >= 2, r >= 0                # from S2.4 (accepted count and rejection tally)
  envelope = {
     ts_utc, seed, parameter_hash, manifest_fingerprint, run_id,
     module="1A.nb_sampler", substream_label="nb_final",
     rng_counter_before_lo, rng_counter_before_hi,
     rng_counter_after_lo,  rng_counter_after_hi
  }
  # Note: counters must be equal here (no RNG consumption).

OUTPUT:
  one JSONL row to logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...

1  assert isfinite(mu)    and mu  > 0
2  assert isfinite(phi)   and phi > 0
3  assert isinteger(N)    and N   >= 2
4  assert isinteger(r)    and r   >= 0
5  assert counters_equal(envelope)    # before == after
6  payload := {
       merchant_id: merchant_id,
       mu: mu,
       dispersion_k: phi,
       n_outlets: N,
       nb_rejections: r
   }
7  emit_event(stream="nb_final", envelope=envelope, payload=payload)
```

## Why this design works

* **Single source of truth:** the realised $N_m$ and its generating $(\mu_m,\phi_m)$ travel together in `nb_final`, so replay/validation needs no “side channels.”
* **Audit-tight:** coverage (Gamma+Poisson present), cardinality (exactly one final), and no RNG consumption in S2.5 are all machine-checkable via schemas and counters; violations fail fast in the **validation bundle**.

---

# S2.6 — RNG sub-streams & consumption discipline

## Goal

Guarantee **bit-replay** across machines/threads by fixing (i) which **Philox sub-streams** are used for each NB attempt component, (ii) how **counters** advance, and (iii) what evidence is emitted so validation can prove replay and detect any consumption drift. This state does **not** draw randomness itself; it **governs** how S2.3/S2.4/S2.5 consume and log it.

---

## Inputs (contractual)

* **Sub-stream label set for NB:** $\ell_\gamma=$"gamma_component", $\ell_\pi=$"poisson_component". These labels are mapped to Philox jumps by the **label-hashing plan from S0** (the mapping is global and *not* repeated in payloads).
* **Event schemas** (carry the envelope & counters): `#/rng/events/gamma_component`, `#/rng/events/poisson_component`, `#/rng/events/nb_final`. Each extends the common **rng envelope** with `rng_counter_before_*` and `rng_counter_after_*`.
* **Dataset dictionary paths & partitions** (authoritative):
  `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`,
  `logs/rng/events/poisson_component/…`,
  `logs/rng/events/nb_final/…`. All three partition by `["seed","parameter_hash","run_id"]`.
* **RNG audit/trace channels** (S0 infrastructure): `rng_audit_log`, `rng_trace_log`, and `stream_jump` events for explicit stream/sub-stream jumps.

---

## Canonical discipline (per merchant $m$)

1. **Sub-stream allocation.** For NB attempts of merchant $m$:

   * Use sub-stream $\ell_\gamma$ for the Gamma step (S2.3).
   * Use sub-stream $\ell_\pi$ for the Poisson step (S2.3).
     Jumps to these sub-streams are implied by the S0 label→jump mapping and may be materialised by `stream_jump` records; **payloads never restate jumps**.

2. **Per-attempt event cardinality.** For attempt index $t=0,1,2,\dots$: emit **exactly one** `gamma_component` *and* **exactly one** `poisson_component`. On acceptance (first $K_t\ge 2$), emit **exactly one** `nb_final`. No additional NB events are allowed for the merchant.

3. **Envelope counters (evidence of consumption).** Every event row carries:

   $$
   (\texttt{rng_counter_before_lo, hi},\ \texttt{rng_counter_after_lo, hi})
   $$

   defining a half-open interval $[c_{\text{before}},\,c_{\text{after}})$ of Philox **32-bit steps** for that sub-stream. The validator asserts:

   * **Monotone advance:** $c^{(e+1)}_{\text{before}}\ge c^{(e)}_{\text{after}}$ for events on the same `(seed, parameter_hash, run_id, substream_label, merchant_id)`.
   * **Non-overlap:** intervals for distinct events in the same sub-stream do not overlap.
   * **No RNG in `nb_final`:** `before == after`.

4. **Context tagging.** `gamma_component` always has `context="nb"` and `index=0`; `poisson_component` has `context="nb"`. (The same Poisson stream will be reused later with `context="ztp"` for S4—this context disambiguates uses.)

5. **Thread safety & determinism.** Because counters live in the envelope and sub-streams are label-scoped, **interleaving** across merchants/threads does not affect outcomes. Replay reads the same envelopes and reproduces draws exactly. `rng_trace_log` provides a linearised view per module to aid forensics.

---

## Invariants (checked by validation)

* **I-NB-Sub1 (cardinality):** per attempt, **exactly two** component events; **one** `nb_final` at acceptance.
* **I-NB-Sub2 (envelope coherence):** all three event types share the same `(seed, parameter_hash, run_id, merchant_id)`; `substream_label` matches the event stream (`gamma_component` vs `poisson_component` vs `nb_final`).
* **I-NB-Sub3 (counters):** counters **strictly** advance within each sub-stream; `nb_final` shows **no** advance (administrative emission).
* **I-NB-Sub4 (coverage):** if `nb_final` exists, there must be ≥1 `gamma_component` **and** ≥1 `poisson_component` with matching envelope keys (coverage join).

---

## Failure semantics

* `counter_regression` if any event has `after < before`, or if a later event’s `before < previous after` in the same sub-stream.
* `substream_mismatch` if a Gamma/Poisson event’s `substream_label` does not match its path/stream type.
* `coverage_gap` if `nb_final` lacks preceding Gamma or Poisson components (matching keys).
* `context_mismatch` if `gamma_component.context ≠ "nb"` or `poisson_component.context ≠ "nb"` in S2. (Reserved `"ztp"` is for S4 only.)

---

## Minimal reference algorithm (discipline only)

```
# Called by the NB sampler harness for merchant m
substream_gamma  := "gamma_component"   # jump per S0 mapping
substream_poisson:= "poisson_component" # jump per S0 mapping
t := 0
while true:
    # ---- Gamma attempt (S2.3) ----
    c0 := philox_counter(substream_gamma)
    G  := sample_gamma(shape=phi, scale=1)   # u01 uniforms (open interval)
    c1 := philox_counter(substream_gamma)
    emit_event("gamma_component", envelope={..., substream_label=substream_gamma,
                 rng_counter_before=c0, rng_counter_after=c1},
               payload={merchant_id, context="nb", index=0, alpha=phi, gamma_value=G})

    # ---- Poisson attempt (S2.3) ----
    c2 := philox_counter(substream_poisson)
    lambda := (mu/phi) * G
    K  := sample_poisson(lambda)             # u01 uniforms (open interval)
    c3 := philox_counter(substream_poisson)
    emit_event("poisson_component", envelope={..., substream_label=substream_poisson,
                 rng_counter_before=c2, rng_counter_after=c3},
               payload={merchant_id, context="nb", lambda=lambda, k=K})

    if K >= 2:    # S2.4 acceptance
        # S2.5: finalisation event WITHOUT RNG consumption
        c4 := philox_counter(substream_poisson)   # unchanged pre/post
        emit_event("nb_final", envelope={..., substream_label="nb_final",
                     rng_counter_before=c4, rng_counter_after=c4},
                   payload={merchant_id, mu=mu, dispersion_k=phi,
                            n_outlets=K, nb_rejections=t})
        break
    else:
        t := t + 1
```

* The validator checks **cardinality**, **coverage**, and **counter monotonicity** across `gamma_component`, `poisson_component`, and `nb_final` for each merchant. Paths and schema refs come from the dictionary; counters and label coherence come from the shared envelope spec.

## What S2.6 “exports”

S2.6 exports **no new datasets**; it cements the **discipline** that S2.3–S2.5 must follow and the **evidence** validators will use. The authoritative references remain the dictionary entries for the three event streams and the rng-core schemas with counter fields.

---

# S2.7 — Determinism & correctness invariants (expanded)

## I-NB1 — Bit-replay of the attempt sequence and acceptance

**Claim.** For fixed $(x^{(\mu)}_m,x^{(\phi)}_m,\beta_\mu,\beta_\phi,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the entire attempt process is **bit-identical** across replays:

$$
(G_t,K_t)_{t\ge 0}\text{ and }(N_m,r_m)\ \text{are identical on every replay.}
$$

**Why it holds.**

* **Counter-based Philox** (no global state), **fixed sub-stream labels** for Gamma/Poisson, and **one Gamma + one Poisson draw per attempt** ensure the same counters are consumed in the same order regardless of thread interleavings. Envelope counters make this observable and verifiable.
* The **schema & dictionary** pin the event streams, partitions, and required envelope fields used for replay checks.

**Validator algorithm (replay proof, per merchant).**

1. Collect all `gamma_component` and `poisson_component` rows for `(seed, parameter_hash, run_id, merchant_id)`; sort by `(substream_label, rng_counter_before_lo, rng_counter_before_hi)`. Enforce **monotone, non-overlapping** counter intervals per sub-stream.
2. Interleave per-attempt pairs in time order (Gamma, then Poisson), reconstruct $(G_t,\lambda_t,K_t)$ and the **first** $t$ with $K_t\ge2$ → derive $N_m, r_m$.
3. Join to the single `nb_final` row; assert `n_outlets == N_m` and `nb_rejections == r_m`. **Pass iff identical.**

---

## I-NB2 — Schema conformance (fields + cross-event consistency)

**Required payload fields (and domains):**

* `gamma_component`: `merchant_id`, `context="nb"`, `index=0`, `alpha = φ_m > 0`, `gamma_value = G > 0`.
* `poisson_component`: `merchant_id`, `context="nb"`, `lambda > 0`, `k ∈ ℕ`.
* `nb_final`: `merchant_id`, `mu = μ_m > 0`, `dispersion_k = φ_m > 0`, `n_outlets = N_m ≥ 2`, `nb_rejections = r_m ≥ 0`.

**Cross-event consistency checks (numeric equalities):**

* **Echo of parameters:** `nb_final.mu == μ_m` and `nb_final.dispersion_k == φ_m` used for the attempts. (S2.2 computed these; they must match bit-for-bit or within 1 ulp if your writer reserializes.)
* **Composition check:** for each attempt,

  $$
  \lambda_t \stackrel{?}{=} (\mu/\phi)\cdot \texttt{gamma_value}_t
  $$

  where `mu=μ`, `phi=φ` taken from the paired `nb_final` row; equality asserted within a strict binary64 tolerance (e.g., `<= 0.5 ulp`).

**Validator algorithm (schema & joins).**

* Enforce **presence** of all required keys per `schemas.layer1.yaml#/rng/events/*` and common **rng_envelope** (ts, run_id, seed, parameter_hash, manifest_fingerprint, substream_label, before/after counters).
* Enforce **coverage invariant:** if `nb_final` exists, there is ≥1 `gamma_component` **and** ≥1 `poisson_component` (context `"nb"`) with matching envelope keys. Fail fast otherwise.

---

## I-NB3 — Open-interval uniforms in samplers

**Rule.** Every uniform $u$ consumed by Gamma and Poisson samplers obeys $u\in(0,1)$; this is the `u01` primitive with **exclusive** bounds.

**Auditable evidence.**

* NB events don’t log the uniforms themselves, but **envelope counters** prove the number of draws taken from each sub-stream; the samplers are **specified** to consume `u01`. The validator asserts the **discipline**, and unit/integration tests for the RNG core separately verify that all draws emitted under `u01` never hit 0 or 1.

**Cross-check (optional).**

* In test runs, enable an **RNG trace** (`rng_trace_log`) at low sampling rate to record sample `u` values with redaction; assert exclusivity $0 < u < 1$. Not used in production bundles but available to QA.

---

## I-NB4 — Consumption discipline (cardinality + counters)

**Cardinality.**

* **Per attempt:** exactly **one** `gamma_component` **and** **one** `poisson_component`.
* **Attempts:** zero or more rejections; **first** $K_t\ge2$ is accepted.
* **Finalisation:** exactly **one** `nb_final` at acceptance.

**Counters.**

* Within a sub-stream, counters **advance monotonically** without overlap:

  $$
  [c^{(e)}_{\text{before}},\,c^{(e)}_{\text{after}})\ \cap\ [c^{(e+1)}_{\text{before}},\,c^{(e+1)}_{\text{after}})=\varnothing,\quad
  c^{(e+1)}_{\text{before}}\ge c^{(e)}_{\text{after}}.
  $$
* For `nb_final`, **no RNG consumption**: `before == after`.

**Validator algorithm (discipline).**

1. Group by `(seed, parameter_hash, run_id, merchant_id, substream_label)` and check **interval non-overlap** & **monotonicity** across all events.
2. Count events per attempt: reconstruct attempt indices by alternating Gamma/Poisson; any deviation (missing Gamma or Poisson, double Poisson, etc.) ⇒ structural failure.
3. Verify single `nb_final` per merchant key.

---

## Additional invariants that make S2 airtight

* **Single-site hygiene.** Merchants with `is_multi=0` (from S1) must have **no** NB events in their keyspace. The validator scans for stray `gamma_component`/`poisson_component`/`nb_final` in those keys and aborts if found.
* **Partition correctness.** All three NB streams must live under the dictionary-pinned paths and partitions (`seed`, `parameter_hash`, `run_id`), nothing else. Cross-partition writes ⇒ failure.
* **Parameter echo integrity.** For every `gamma_component` row, `alpha == nb_final.dispersion_k`; for every `poisson_component`, `lambda` matches `mu/phi * gamma_value` (tolerance as above). This binds the **exact** parameters used to sample to the final event.

---

## Minimal validator pseudo-algo (end-to-end for S2 invariants)

```
INPUT: all rng JSONL for {gamma_component, poisson_component, nb_final},
       merchant metadata incl. is_multi, and S2.2 parameter reconstructor
OUTPUT: pass/fail + metrics

for each key = (seed, parameter_hash, run_id, merchant_id):

  A := rows(gamma_component where key)   # expect >=1 iff merchant is_multi=1
  B := rows(poisson_component where key) # expect >=1 iff merchant is_multi=1
  F := rows(nb_final where key)          # expect ==1 iff merchant is_multi=1

  # (1) Single-site hygiene
  if is_multi==0 and (A or B or F not empty): fail("stray_nb_events")

  # (2) Cardinality & coverage
  if is_multi==1 and (len(A)<1 or len(B)<1 or len(F)!=1): fail("coverage/cardinality")

  # (3) Counters: monotone & non-overlap per substream; nb_final has before==after
  assert_counters_ok(A); assert_counters_ok(B); assert_counters_equal(F)

  # (4) Schema fields present & domains (context="nb", index=0 for gamma)
  schema_check(A, "#/rng/events/gamma_component")
  schema_check(B, "#/rng/events/poisson_component")
  schema_check(F, "#/rng/events/nb_final")

  # (5) Parameter echo & composition
  (mu, phi) := (F[0].mu, F[0].dispersion_k)
  for each a in A: assert_equal_ulps(a.alpha, phi, 1)
  # Rebuild attempts: pair A[i] with B[i] by time, check lambda
  for i in 0..min(len(A),len(B))-1:
      assert_equal_ulps(B[i].lambda, (mu/phi)*A[i].gamma_value, 1)

  # (6) Reconstruct acceptance and rejections
  t := first i where B[i].k >= 2
  assert t exists; assert F[0].n_outlets == B[t].k; assert F[0].nb_rejections == t

# (7) Global corridors computed elsewhere (S2.4), but NB invariants above must pass.
return PASS
```

Citations for streams/paths/schemas and envelope fields come from the **dataset dictionary** and **layer schemas**.

---


# S2.8 — Failure modes (abort semantics, evidence, and actions)

## Goal

Define **all** conditions under which S2 (NB for domestic outlet count) must **hard-fail** or **validation-fail**, and exactly what evidence is written so the validator can prove the failure and halt the run. This extends your three bullets (parameters, schema, corridors) into precise, testable cases tied to the dictionary paths and schemas.

---

## Failure classes (conditions → action → evidence)

### F-S2.1 — Non-finite / non-positive NB parameters (from S2.2)

**Condition.** Any merchant $m$ yields $\mu_m\le 0$ or $\phi_m\le 0$, or either linear predictor/exponential is **NaN/Inf** under binary64.
**Action.** **Immediate abort of S2** for that merchant; no S2.3 events are emitted; run fails validation.
**Evidence.** Validator reports `invalid_nb_parameters(m)` by recomputing $(\mu_m,\phi_m)$ deterministically from S2.1 + artefacts under `parameter_hash`.

---

### F-S2.2 — Sampler numeric invalid (S2.3)

**Condition.** `gamma_component.alpha ≤ 0` or `gamma_value ≤ 0`; or `poisson_component.lambda ≤ 0` / non-finite (shouldn’t happen if S2.2 passed).
**Action.** **Hard schema failure** on the offending event row.
**Evidence.** The offending JSONL row in `logs/rng/events/{gamma_component|poisson_component}/…` fails `schemas.layer1.yaml` checks during validation.

---

### F-S2.3 — Schema violation (any S2 event)

**Condition.** Missing **rng envelope** fields; missing **required payload** keys; `context` not in the allowed set (`"nb"` for S2 Gamma/Poisson; `"nb_final"` has no context field).
**Action.** **Hard schema failure**; validation aborts the run.
**Evidence.** Dictionary-pinned validators check the three streams and their schema refs:

* `gamma_component` and `poisson_component` must include `merchant_id`, `context="nb"`, and required numeric fields;
* `nb_final` must include `merchant_id, mu, dispersion_k, n_outlets, nb_rejections`; all rows carry the envelope with counters.

---

### F-S2.4 — Coverage & cardinality gaps

**Condition.**

* `nb_final` exists **without** at least one prior `gamma_component` **and** one prior `poisson_component` (context `"nb"`); or
* more than **one** `nb_final` for the same `(seed, parameter_hash, run_id, merchant_id)`.
  **Action.** **Structural failure**; abort.
  **Evidence.** Coverage join over the three event streams (dictionary paths + schema) fails; duplicates are listed by key.

---

### F-S2.5 — Counter/consumption discipline breach (S2.6 invariants)

**Condition.** Any of:

* `rng_counter_after < rng_counter_before`;
* overlapping counter intervals within a sub-stream;
* `nb_final` shows counter **advance** (`before ≠ after`);
* per-attempt cardinality differs from “exactly one Gamma + one Poisson”.
  **Action.** **Structural failure**; abort.
  **Evidence.** Envelope counter scans across `gamma_component`, `poisson_component`, `nb_final`.

---

### F-S2.6 — Composition mismatch (Gamma→Poisson)

**Condition.** For attempt $t$, `poisson_component.lambda` is not equal (within strict binary64 tolerance) to

$$
\lambda_t \stackrel{!}{=} (\mu/\phi)\cdot \texttt{gamma_value}_t
$$

where `mu`, `dispersion_k` are taken from the paired `nb_final`.
**Action.** **Consistency failure**; abort.
**Evidence.** Validator pairs attempts by counters/time and checks equality; mismatches are enumerated.

---

### F-S2.7 — Rejection corridor breach (S2.4 obligations)

**Condition.** Either global rejection rate

$$
\widehat{\rho}_{\text{rej}}=\tfrac{\sum_m r_m}{\sum_m (r_m+1)} > 0.06
$$

or empirical $p_{99}(r_m) > 3$, or the **one-sided CUSUM** trips against baseline.
**Action.** **Validation abort** of the run; write metrics & plots into the bundle; `_passed.flag` is **not** written.
**Evidence.** Metrics in `validation_bundle_1A(fingerprint)/metrics.csv` + CUSUM trace in the bundle.

---

### F-S2.8 — Partition/path misuse

**Condition.** Any S2 event stream written outside its dictionary path or missing required partition keys `["seed","parameter_hash","run_id"]`.
**Action.** **Structural failure**; abort.
**Evidence.** Dataset dictionary enumerates legal paths/partitions for `gamma_component`, `poisson_component`, `nb_final`.

---

### F-S2.9 — Single-site hygiene breach

**Condition.** A merchant with `is_multi=0` (from S1) has **any** S2 NB event.
**Action.** **Structural failure** (branch purity); abort.
**Evidence.** Validator cross-checks hurdle stream vs NB streams; S1 is the first RNG stream per dictionary.

---

## Abort semantics (what exactly happens)

1. **Detection locus.**

   * F-S2.1 / F-S2.2 are detected **during** S2.2/S2.3 and prevent further S2 emission for that merchant.
   * F-S2.3..F-S2.9 are detected by the **validator** after S2 finishes emitting events.
2. **Run outcome.** Any single **hard** failure causes the **S2 block to fail validation**, and therefore **1A** fails for the run’s `manifest_fingerprint`.
3. **Bundle contents.** The validator still emits a **bundle** under
   `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
   with `index.json`, `schema_checks.json`, `rng_accounting.json`, `metrics.csv`, and diffs; `_passed.flag` is omitted on failure.

---

## Minimal validator checklist (S2-specific)

* Recompute $(\mu,\phi)$ from S2.1/S2.2; **abort** if non-finite/non-positive (F-S2.1).
* Schema-validate all three streams; **abort** on any row failure (F-S2.3).
* Ensure **coverage & cardinality** for every merchant with `nb_final` (F-S2.4).
* Verify **counters** and **per-attempt cardinality** (F-S2.5).
* Check **composition** $\lambda = (\mu/\phi)\cdot \texttt{gamma_value}$ per attempt (F-S2.6).
* Compute corridors: $\widehat{\rho}_{\text{rej}}$, $p_{99}(r_m)$, CUSUM; **abort** if any gate trips (F-S2.7).
* Assert **partition/path** correctness (F-S2.8).
* Enforce **single-site hygiene** (F-S2.9).


## Notes on scope

These S2 failure modes sit within the layer-wide validation contract: any **schema** violation, **PK/UK/FK** breach, **RNG replay** mismatch, or **corridor** failure is a **hard fail**, bundle still written, `_passed.flag` not written, and **1A→1B hand-off is disallowed** until fixed.

---

# S2.9 — Outputs (state boundary)

## Goal

Close the S2 block by (a) persisting the **authoritative RNG event streams** for the NB sampler and (b) handing the accepted domestic outlet count $N_m$ (and rejection count $r_m$) forward **in-memory** to S3+. No Parquet “data product” is written in S2; the only persisted artefacts are the three JSONL **event streams** fixed by the dataset dictionary and schemas.

---

## Persisted outputs (authoritative event streams)

Write exactly the following streams, all **partitioned by** `["seed","parameter_hash","run_id"]` and validated against the indicated **schema refs**:

1. **Gamma components (NB mixture)**
   Path: `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/gamma_component`
   Cardinality per merchant with `is_multi=1`: **≥ 1** row (one per attempt).

2. **Poisson components (NB mixture)**
   Path: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/poisson_component`
   Cardinality: **≥ 1** row (one per attempt). Note: the **same stream id** is reused later by S4 (ZTP) with a different `context`, which is why the dictionary describes it as “used in NB composition / ZTP.”

3. **NB final (accepted outcome)**
   Path: `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/nb_final`
   Cardinality: **exactly 1** row per merchant (echoing `mu`, `dispersion_k`, realised `n_outlets`, and `nb_rejections`).

Each event carries the **shared RNG envelope** (seed/parameter_hash/manifest_fingerprint/run_id/module/substream + Philox counters), as established in S0 and used throughout validation and replay.

**Retention**: the dictionary marks these streams with a 180-day retention (administrative), consumed by the validator and not “final in layer.”

---

## In-memory exports to S3+

For each merchant $m$ with `is_multi=1`, S2 hands forward:

$$
\boxed{\ N_m \in \{2,3,\dots\}\ },\qquad
\boxed{\ r_m \in \{0,1,2,\dots\}\ \text{(diagnostic)} }.
$$

* $N_m$ is the **authoritative domestic outlet count** used by downstream branches. It is **not** re-sampled and must **not** be re-interpreted later.
* $r_m$ is passed for corridor diagnostics and may be surfaced in the validation bundle; it has no modelling effect downstream.

**Downstream use:**

* **S3 (eligibility gate):** reads policy flags and decides whether the merchant can attempt cross-border; S3 is evaluated **only** for multi-site merchants that just left S2.
* **S4 (ZTP foreign count):** when eligible, $N_m$ typically enters $\lambda_{\text{extra}}$ (e.g., via $\log N$) according to governed hyper-parameters; S4 logs its own events but reuses the **Poisson component stream id** with `context="ztp"`.

---

## Boundary invariants (validator obligations at S2→S3)

* **Coverage & cardinality:** For every merchant key `(seed, parameter_hash, run_id, merchant_id)` with `is_multi=1`, **≥1** `gamma_component`, **≥1** `poisson_component`, and **exactly 1** `nb_final` exist under the dictionary paths. For `is_multi=0`, **no** S2 events may exist (branch purity).
* **Envelope coherence:** All three streams carry the required RNG envelope fields; counters advance monotonically per substream, and `nb_final` shows **no** counter advance (`before == after`).
* **Echo-of-parameters:** `nb_final.mu` and `nb_final.dispersion_k` equal the S2.2 values; attempt-level `lambda` equals ((\mu/\phi)\cdot\texttt{gamma_value}\` within strict binary64 tolerance.
* **Partitions & paths:** Streams are **only** written under the dictionary-approved paths/partitions; violations are structural failures.

---

## What is **not** persisted by S2

* No Parquet/Delta tables (e.g., counts per merchant) are authored here. The tangible artefacts for S2 are **only** the JSONL event streams—everything else remains in memory until later states produce their own persisted datasets (`country_set`, `ranking_residual_cache`, `outlet_catalogue`, and the validation bundle for the run).

---

## Relationship to the validation bundle

The validator consumes these three streams to reconstruct attempts, verify counters/coverage, compute rejection corridors, and then writes the **bundle** at
`data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` (zip, keyed by `fingerprint`). Passing S2 is necessary for the bundle to emit `_passed.flag`.

---

## Minimal writer checklist (to close S2)

* Ensure **at least one** Gamma and Poisson record were emitted for each multi-site merchant, then write **exactly one** `nb_final`. Paths, partitions, and schema refs must match the dictionary.
* Keep $N_m, r_m$ **in memory** for S3; do **not** persist them as a sidecar table.
* Do not emit any S2 events for single-site merchants (S1 said `is_multi=0`).

---