# S4.1 — Universe, symbols, authority

## Goal

Pin exactly **who enters S4**, what **symbols/inputs** exist at entry, and the **authoritative outputs & logs** S4 will produce or guarantee for later states (S5–S6) and for validation. S4.1 itself draws nothing; it establishes the **contract**—schemas, lineage, counter discipline, and absence/presence rules that S4.2–S4.8 must obey.

---

## Domain (who is allowed in)

Evaluate S4 **only** for merchants $m$ that:

1. are **multi-site** (hurdle success in S1), and
2. are **eligible for cross-border** (gate in S3 gives $e_m=1$).

If $e_m=0$ the merchant **skips S4–S6** and remains $K_m:=0$ (domestic-only branch fixed by S3); S4 must emit **no** ZTP-related RNG events for such merchants (this absence is validated).

---

## Symbols & fixed notation at S4 entry

* $m$: merchant id (PK `merchant_id`).
* $c \in \mathcal{I}$: home country ISO-3166-1 alpha-2; $\mathcal{I}$ is the canonical ISO set (FK upstream).
* $H_m \in\{0,1\}$: hurdle outcome (1=multi-site).
* $e_m \in\{0,1\}$: S3 **eligibility** flag (gate).
* $N_m\in\{2,3,\dots\}$: **accepted** multi-site outlet count from S2 (read-only for S4).
* $\theta=(\theta_0,\theta_1,\theta_2)$: **hyperparameters** from `crossborder_hyperparams.yaml`, keyed by $(\text{home},\text{MCC},\text{channel})$, with governance (Wald stats, drift gates) recorded alongside.
* $X_m\in\mathbb{R}$: **openness** scalar (looked up with $\theta$).
* $\eta_m$: linear predictor (defined in S4.2).
* $\lambda_{\text{extra},m}=\exp(\eta_m)>0$: Poisson mean for the **zero-truncated** target (defined in S4.2).
* $K_m\in\{1,2,\dots\}$: foreign-country count drawn in S4 (or $0$ if $e_m=0$ by S3).

**Lineage carried into every RNG event**: `seed`, `parameter_hash`, `manifest_fingerprint`, plus the standard RNG envelope fields below.

---

## Authoritative schemas & event streams (what S4 outputs)

S4 produces **only RNG event streams** and an **in-memory scalar** $K_m$ (for S5–S6). Nothing else is persisted by S4 itself. All events must include the **RNG envelope** (layer-wide authority):

* **RNG envelope** (required on every event):
  `{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo/hi, rng_counter_after_lo/hi, merchant_id }`.
  This pins **lineage** and **counter discipline** for replay and CI.

* **Event record types used by S4** (partitioned by `{seed, parameter_hash, run_id}`):

  1. `poisson_component` — raw Poisson attempts for ZTP
     **Required payload:** `{ merchant_id, context="ztp", lambda, k }` where `lambda = λ_{extra,m} > 0` and `k ∈ {0,1,2,…}` is the **untruncated** draw.
  2. `ztp_rejection` — rejection of zero outcomes
     **Required payload:** `{ merchant_id, lambda_extra, k=0, attempt }` with `attempt ∈ {1,…,64}` strictly increasing per $m$.
  3. `ztp_retry_exhausted` — hard cap reached (64 zeros)
     **Required payload:** `{ merchant_id, lambda_extra, attempts=64, aborted=true }`. Exactly one at most, implies merchant abort.

**Partitioning & naming.** Paths are fixed in the dictionary to `logs/rng/events/<event_name>/...` with partitions `{seed, parameter_hash, run_id}`. CI validates presence/absence and schema conformance, and treats wrong `context` values or missing envelope fields as **schema violations**.

---

## Presence/absence contracts (outputs seen by validators)

* **Eligible $e_m=1$:**
  Must see **≥1** `poisson_component`(context="ztp") attempts; if acceptance occurs, zero or more `ztp_rejection` records precede it; if acceptance never occurs within 64 attempts, there **must** be exactly one `ztp_retry_exhausted` and the merchant is **aborted** (no downstream S5–S6 for that merchant).
* **Ineligible $e_m=0$:**
  Must see **no** S4 events (`poisson_component` with `context="ztp"`, `ztp_*`) for this merchant; presence is a **branch-coherence** failure.

---

## What S4 “exports” for downstream (beyond logs)

* **Scalar to S5/S6:** on acceptance, the **foreign count** $K_m \in \{1,2,\dots\}$. This determines the required length of the later **country set** and of the **Dirichlet $\alpha$ vector** in S7 (must equal $K_m+1$ including home). This scalar is **read-only** downstream.
* **Implied size constraints:** since $K_m\ge 1$ in this branch, S5 must produce at least $K_m$ eligible foreign candidates, and S6 must sample exactly $K_m$ ordered foreign ISO codes (Gumbel-top-k).
* **Validation inlet:** S9 (validation) ingests the **event streams** from S4 to compute corridor statistics (mean rejections < 0.05 and $p_{99.9}<3$); failures **abort the run**. No extra S4 datasets are written for this—validators operate over the S4 logs.

---

## Determinism & correctness invariants (checked across S4)

* **I-S4-A (bit-replay).** With fixed $(N_m, X_m, \theta, \texttt{seed}, \texttt{parameter_hash}, \texttt{manifest_fingerprint})$ and fixed substream label, the Poisson attempt sequence and accepted $K_m$ are **bit-reproducible** (counter-based Philox; envelope counters prove consumption).
* **I-S4-B (strict attempt indexing).** `ztp_rejection.attempt` increases $1,2,\dots$ per merchant; `ztp_retry_exhausted.attempts` is **exactly 64**.
* **I-S4-C (schema authority).** Every event row must pass the RNG envelope schema and its event-specific required fields/constraints (`lambda>0`, integer `k`, fixed `context="ztp"`).
* **I-S4-D (branch coherence).** Presence of any S4 events for $e_m=0$ is an error; absence of S4 events for $e_m=1$ (without `ztp_retry_exhausted`) is an error.

---

## Failure modes (abort semantics hooked to outputs)

* **Numeric policy error:** non-finite or $\le 0$ $\lambda_{\text{extra},m}$ (computed in S4.2) → **abort merchant**; no S4 events must be written for that merchant. Logged at validation as numeric policy breach.
* **Retry exhaustion:** 64 consecutive `k=0` attempts → emit `ztp_retry_exhausted` and **abort merchant**; S5–S6 must **not** run for this $m$.
* **Schema/lineage violation:** missing envelope fields, wrong `context`, missing `ztp_rejection` given zero attempts, or missing `ztp_retry_exhausted` at cap → **abort run** in CI.

---

## Minimal reference algorithm (language-agnostic; S4.1 scope)

This routine **does not draw** $K$; it prepares and validates S4 inputs, opens event writers with correct partitions, and enforces presence/absence at the boundaries.

```
INPUT:
  merchant m with (merchant_id, home_country_iso=c, mcc, channel)
  N_m >= 2 from S2
  eligibility flag e_m in {0,1} from crossborder_eligibility_flags
  crossborder_hyperparams.yaml keyed by (c, mcc, channel) -> (theta0, theta1, theta2, openness X_m, governance meta)
  lineage: seed, parameter_hash, manifest_fingerprint
OUTPUT:
  prepared S4 context for m (or a no-op if ineligible)
  open writers for S4 RNG streams partitioned by {seed, parameter_hash, run_id}
  (no draws; acceptance of K_m happens in S4.5)

1  assert is_multi(m) == true                        # from S1
2  if e_m == 0:
3      # Domestic-only branch: S4 must emit NOTHING for m
4      register_absence_contract(m, streams = {poisson_component, ztp_rejection, ztp_retry_exhausted})
5      return NO_OP                                  # K_m already fixed to 0 by S3
6  # Eligible branch:
7  load (theta0, theta1, theta2, X_m, governance_meta) from crossborder_hyperparams.yaml keyed by (c, mcc, channel)
8  assert 0 < theta1 < 1                             # governance constraint (sub-linearity)
9  # Pre-compute predictor (evaluated formally in S4.2):
10 eta_m := theta0 + theta1 * log(N_m) + theta2 * X_m
11 # Do NOT exponentiate or sample here; S4.2/S4.5 will.
12 # Prepare RNG event writers with the required envelope & partitions:
13 open_stream_writer("logs/rng/events/poisson_component", partitions={seed, parameter_hash, run_id})
14 open_stream_writer("logs/rng/events/ztp_rejection", partitions={seed, parameter_hash, run_id})
15 open_stream_writer("logs/rng/events/ztp_retry_exhausted", partitions={seed, parameter_hash, run_id})
16 # Bind constant envelope fields for this module:
17 envelope_base := {
       run_id, seed, parameter_hash, manifest_fingerprint,
       module="1A.ztp_sampler", substream_label="poisson_component"
   }
18 # Record a readiness trace (optional in rng_trace_log) to aid CI diagnostics.
19 return PREPARED_CONTEXT(m, c, N_m, theta=(theta0,theta1,theta2), X_m, envelope_base)
```

**Notes on this algorithm.**

* It enforces the **absence contract** for $e_m=0$ and **does not** consume RNG for such merchants. Validators will assert **no** S4 events exist for them.
* It binds the **substream label** once (`"poisson_component"`) for S4; S4.5 will actually draw and emit events with this label.
* It keeps **exponentiation and sampling** out of S4.1 by design; $\eta_m$ is staged for S4.2, which defines $\lambda_{\text{extra},m}=\exp(\eta_m)$ with numeric guards.

---

# S4.2 — Link function and parameterisation

## Goal

Map merchant-level covariates at S4 entry to a **strictly positive** Poisson mean $\lambda_{\text{extra},m}$ for the ZTP foreign-country count, using a governed **log-link GLM** with sub-linear size elasticity and an openness term. This replaces an earlier identity-link draft, and its governance (Wald tests, drift gates) is recorded alongside the hyperparameters.

---

## Inputs (for each eligible merchant $m$)

* **Size (from S2):** $N_m\in\{2,3,\dots\}$ (the accepted domestic outlet count; *read-only* in S4). Natural log is base-$e$.
* **Openness scalar:** $X_m\in\mathbb{R}$ (loaded with $\theta$ from `crossborder_hyperparams.yaml`).
* **Hyperparameters:** $\theta=(\theta_0,\theta_1,\theta_2)$ from the same YAML, keyed by $(\text{home},\text{MCC},\text{channel})$. Governance metadata (e.g., Wald $p<10^{-5}$; quarterly drift gates) live beside $\theta$.

**Preconditions.** Verified upstream in S4.1: $e_m=1$ (eligible), $N_m\ge 2$; non-eligible merchants skip S4 entirely and keep $K_m=0$.

---

## Construction (canonical)

### Linear predictor (canonical scale)

$$
\boxed{\ \eta_m \;=\; \theta_0 \;+\; \theta_1 \log N_m \;+\; \theta_2 X_m\ ,\qquad 0<\theta_1<1\ }
$$

### Mean map (mean scale)

$$
\boxed{\ \lambda_{\text{extra},m} \;=\; \exp(\eta_m) \;>\; 0\ } \quad\text{(Poisson mean for ZTP).}
$$

* The **log-link** guarantees positivity; the sub-linearity constraint $0<\theta_1<1$ is enforced by governance (Wald tests + drift gates) and stored in the YAML (`theta_stats`).
* This specification supersedes an earlier **identity-link** draft; adopting the log-link aligns with the ZTP support and avoids ad-hoc clamping while preserving the downstream PMF and rejection sampler.

**Numeric guard.** Evaluate $\eta_m$ and $\lambda_{\text{extra},m}$ in IEEE-754 **binary64**; if $\lambda_{\text{extra},m}$ is **non-finite** (Inf/NaN), raise **numeric policy error** (abort this merchant; do not emit any S4 events).

---

## Interpretability & comparative statics (why this form)

* **Elasticity w\.r.t. size $N$.**
  $\displaystyle \frac{\partial \eta_m}{\partial N_m}=\frac{\theta_1}{N_m}$, hence
  $\displaystyle \frac{\partial \lambda_{\text{extra},m}}{\partial N_m}=\frac{\theta_1}{N_m}\,\lambda_{\text{extra},m}$ and the **elasticity**

  $$
  \boxed{\ \mathcal{E}_{N} \equiv \frac{\partial \lambda}{\partial N}\frac{N}{\lambda}=\theta_1\in(0,1)\ },
  $$

  i.e., **sub-linear** sprawl response as chains grow: each proportional increase in $N$ raises $\lambda$ by a smaller proportion. Governance explicitly confirms $0<\theta_1<1$.

* **Openness effect $X$.**
  $\displaystyle \frac{\partial \lambda_{\text{extra},m}}{\partial X_m}=\theta_2\,\lambda_{\text{extra},m}$, so a unit increase in $X$ scales $\lambda$ by $\exp(\theta_2)$. Governance notes require $\theta_2>0$ (positive openness effect) and gate quarterly drift.

* **Monotonicity.**
  If $\theta_1>0$, then $\lambda$ is strictly increasing in $N$; if $\theta_2>0$, $\lambda$ increases in $X$. With $N_m\ge 2$, $\log N_m$ is well-defined without special casing.

---

## Outputs (what S4.2 makes available downstream)

S4.2 itself **persists no datasets**; it exposes read-only scalars to S4.3–S4.5 (and to S9 validators through recomputation):

$$
\boxed{\,\eta_m\in\mathbb{R},\qquad \lambda_{\text{extra},m}=\exp(\eta_m)>0\,}
$$

These feed the **ZTP target** (S4.3) and the **attempt loop** (S4.5). Validators recompute $\eta_m$ and $\lambda_{\text{extra},m}$ from $(N_m,\theta,X_m)$ and compare against event payloads (`poisson_component.lambda`) in S4 logs.

---

## Invariants & guards (checked at S4.2)

* **Parameter sanity (governed):** require $0<\theta_1<1$ and documented $\theta_2>0$; otherwise **config violation** (abort run in CI).
* **Domain consistency:** must have $N_m\ge 2$ (guaranteed by S2) and $e_m=1$ (S3). Entering S4.2 when $e_m=0$ or $N_m<2$ is a **branch-coherence** bug.
* **Numerical finiteness:** $\eta_m\in\mathbb{R}$ and $\lambda_{\text{extra},m}\in(0,\infty)$. If $\exp(\eta_m)$ overflows or is NaN, **abort merchant**; S4 must not emit any RNG events for that $m$.

---

## Failure semantics (observable to validation)

* **`numeric_policy_error` (merchant-scoped):** non-finite $\lambda_{\text{extra},m}$ → merchant is dropped before S4.3–S4.5; absence of S4 events for that $m$ is **expected** and documented.
* **`config_governance_violation` (run-scoped):** loaded $\theta$ fail governance constraints (e.g., $\theta_1\le 0$ or $\ge 1$, or drift gates fail) → **abort run** in CI; no merchants proceed in S4.

---

## Minimal reference algorithm (language-agnostic; no RNG)

```
INPUT:
  N_m >= 2                 # from S2 (accepted)
  X_m                      # openness scalar from hyperparam bundle
  (theta0, theta1, theta2) # from crossborder_hyperparams.yaml, with governance meta
  eligibility e_m          # from S3; here must be 1 (eligible)

OUTPUT:
  eta_m, lambda_extra_m    # scalars for S4.3–S4.5 (not persisted here)

1  assert e_m == 1                                    # S3 gate already enforced
2  assert N_m >= 2                                    # S2 guarantee
3  # Governance / config sanity:
4  if not (0.0 < theta1 < 1.0): abort_run("config_governance_violation")
5  # Compute canonical-scale predictor:
6  eta_m := theta0 + theta1 * log(N_m) + theta2 * X_m   # natural log, IEEE-754 binary64
7  # Mean-scale map:
8  lambda_extra_m := exp(eta_m)                          # IEEE-754 binary64
9  if not isfinite(lambda_extra_m) or lambda_extra_m <= 0.0:
10     abort_merchant("numeric_policy_error")            # no S4 events will be written
11 return (eta_m, lambda_extra_m)
```

**Notes.**

* We **do not** emit events in S4.2; events start with the Poisson attempts in S4.5, which will carry `lambda = lambda_extra_m` in each `poisson_component` payload.
* All governance signals (Wald $p<10^{-5}$, drift gates) come from the YAML bundle and are enforced at load time—S4.2 just consumes them.

---


# S4.3 — Target distribution (ZTP)

## Goal

Fix the **probability law** we’re targeting for the foreign-country count $K_m$ and the derived quantities we’ll need for validation corridors and reasoning about retries. The sampler in S4.5 must produce samples exactly from this law.

---

## Construction (law on $\{1,2,\dots\}$)

Let $Y\sim\mathrm{Poisson}(\lambda)$ with $\lambda=\lambda_{\text{extra},m}>0$ from S4.2, and define the **zero-truncated Poisson**

$$
K\;=\;Y\mid(Y\ge 1).
$$

Then the pmf, cdf and normaliser are:

$$
\boxed{\;P(K=k)\;=\;\frac{e^{-\lambda}\lambda^k}{k!\,(1-e^{-\lambda})},\quad k=1,2,\dots\;}
$$

$$
F(k)=P(K\le k)=\frac{P(Y\le k)-P(Y=0)}{1-P(Y=0)}=\frac{e^{-\lambda}\sum_{j=1}^k \lambda^j/j!}{1-e^{-\lambda}}.
$$

Mean and variance:

$$
\boxed{\ \mathbb{E}[K]=\frac{\lambda}{1-e^{-\lambda}},\qquad
\mathrm{Var}[K]=\frac{\lambda+\lambda^2}{1-e^{-\lambda}}-\Big(\frac{\lambda}{1-e^{-\lambda}}\Big)^2\ }.
$$

(Recalled from the state text; these guide corridor checks but are not logged themselves.)

**Acceptance probability of rejection sampling.** If we sample $Y\sim\mathrm{Poisson}(\lambda)$ and accept when $Y\ge1$, the success probability per attempt is

$$
\boxed{\,p_{\text{acc}}=1-e^{-\lambda}\,}.
$$

This is the probability an attempt ends the loop in S4.5.

---

## Retry statistics (what validators expect)

Let $R$ be the **number of zero draws before acceptance**, i.e., the count of rejections. Then

$$
R\sim\mathrm{Geometric}(p_{\text{acc}})\ \text{(failures-before-first-success parameterisation)},
\quad P(R=r)=(1-p_{\text{acc}})^r\,p_{\text{acc}}=e^{-\lambda r}(1-e^{-\lambda}),\ r=0,1,2,\dots
$$

and

$$
\mathbb{E}[R]=\frac{1-p_{\text{acc}}}{p_{\text{acc}}}=\frac{e^{-\lambda}}{1-e^{-\lambda}},
\qquad
\mathrm{median}(R)=\left\lceil\frac{\log 2}{\lambda}-1\right\rceil^{+},
\qquad
r_{q}\ (\text{q-quantile})=\left\lceil\frac{\log\!\left(\frac{1}{1-q}\right)}{\lambda}-1\right\rceil^{+}.
$$

These closed forms let S9 compute corridor checks directly from $\lambda$ (or compare empirical rejection counts in S4 logs to the theoretical distribution). Your design targets “mean rejection < 0.05; $p_{99.9}<3$” as run-level corridors; the formulae above are the reference.

*Sanity with the corridor:* $p_{99.9}(R)\le 3\iff \lambda\ge \tfrac{\log 1000}{4}\approx1.73$. Mean rejection $<0.05$ corresponds to $\lambda \gtrsim 3.04$. These aren’t per-merchant requirements; they give intuition for expected operating ranges of $\lambda$.

---

## Numerically stable evaluation (implementation guidance for S4.5 & S9)

All formulas must be computed in **IEEE-754 binary64**:

* **Normaliser:** $1-e^{-\lambda}$ should be computed as $-\mathrm{expm1}(-\lambda)$ to avoid catastrophic cancellation when $\lambda$ is small.
  Define $d := -\mathrm{expm1}(-\lambda)$ (so $d\in (0,1)$). Then use $d$ everywhere.
* **Log-pmf:**

  $$
  \log P(K=k)= -\lambda + k\log\lambda - \log\Gamma(k{+}1) - \log d,
  $$

  using `gammaln(k+1)` for $\log k!$. This is stable for large $k$ and large $\lambda$.
* **Moments:**
  $\mathbb{E}[K]=\lambda/d$,
  $\mathrm{Var}[K]=(\lambda+\lambda^2)/d - (\lambda/d)^2$.
* **Acceptance:** $p_{\text{acc}}=d$; expected **attempts** $=1/d$; expected **rejections** $=(1-d)/d$.
* **Edge regimes:**

  * Small $\lambda$: $d\simeq \lambda-\lambda^2/2+\cdots$, so $\mathbb{E}[K]\simeq 1+\lambda/2+\lambda^2/12+\cdots$.
  * Large $\lambda$: $d\to 1$, so $\mathbb{E}[K]\approx \lambda$, $\mathrm{Var}[K]\approx \lambda$.

These rules match the RNG/event schema you already set for S4 (no new fields).

---

## Outputs (what S4.3 exports to the rest of S4)

S4.3 persists nothing; it provides **read-only functions of $\lambda$** for S4.4–S4.6 and for S9 validation:

* $p_{\text{acc}} = 1-e^{-\lambda}$ (**success per attempt**) to interpret retry metrics.
* Moment functions $\mathbb{E}[K], \mathrm{Var}[K]$ used only by validators (not logged).
* Stable evaluators for `logpmf(k; λ)` used in testing and any diagnostic summaries.

Validators check that the **observed** rejection counts and acceptance frequencies from the S4 logs lie within your corridors implied by these formulas, and that the payload `lambda` in `poisson_component` is consistent with S4.2.

---

## Invariants & guards

* **I-ZTP-law.** $\sum_{k=1}^\infty P(K=k)=1$ (normalisation via $d=-\mathrm{expm1}(-\lambda)$).
* **I-ZTP-monotonicity.** $p_{\text{acc}}$ increases strictly with $\lambda$; expected retries $\mathbb{E}[R]$ decreases strictly with $\lambda$.
* **I-payload-consistency.** Every `poisson_component` (context="ztp") must carry the same $\lambda$ for a given merchant (S4.5). Any drift implies a logic error.

---

## Minimal reference algorithm (no RNG; numerically stable)

```
# Inputs: lambda > 0 (from S4.2)
# Outputs: functions for pmf/cdf/logpmf; acceptance prob; retry stats

function ztp_prepare(lambda):
    assert isfinite(lambda) and lambda > 0

    # Normaliser with cancellation-safe arithmetic
    d = -expm1(-lambda)                  # = 1 - exp(-lambda) in stable form

    # Exported closures (or plain functions)
    pmf(k):
        assert k >= 1 and is_integer(k)
        return exp( -lambda + k*log(lambda) - gammaln(k+1) - log(d) )

    logpmf(k):
        assert k >= 1 and is_integer(k)
        return -lambda + k*log(lambda) - gammaln(k+1) - log(d)

    cdf(k):
        # Use regularised incomplete gamma or Poisson CDF for Y, then truncate
        # F_K(k) = (P(Y <= k) - P(Y = 0)) / (1 - P(Y = 0))
        PY_le_k = poisson_cdf(k, lambda)           # stable library call
        PY_eq_0 = exp(-lambda)
        return (PY_le_k - PY_eq_0) / d

    acceptance_prob():
        return d                                   # 1 - exp(-lambda)

    expected_K():
        return lambda / d

    var_K():
        return (lambda + lambda*lambda)/d - (lambda/d)**2

    expected_rejections():
        return (1 - d) / d                         # e^{-lambda} / (1 - e^{-lambda})

    quantile_rejections(q):
        # Small increment above q to avoid boundary when q -> 1
        return ceil( log(1.0/(1.0 - q)) / lambda - 1.0 )

    return {pmf, logpmf, cdf, acceptance_prob, expected_K, var_K,
            expected_rejections, quantile_rejections}
```

This “prep” returns everything S4.5/S9 need: a stable normaliser, evaluators, and corridor-relevant summaries. It aligns with your S4 schema/event design and does not introduce new persisted artefacts.

---



# S4.4 — RNG protocol (sub-streams, counters, schema)

## Purpose

Specify the **randomness geometry** for S4 attempts: which Philox sub-stream label is used, how the **128-bit counter** evolves during attempts, what **must** appear in each event’s envelope/payload, and the exact **presence/absence** semantics that validation enforces. This state defines *how* randomness is consumed and evidenced; **acceptance** is handled in S4.5.

---

## Sub-stream & jump discipline (label space)

Let the Philox engine be **Philox $2\times 64$-10** (counter-based). Every logical RNG operation is assigned a **sub-stream label** $\ell$ with a fixed 64-bit **jump stride**

$$
\boxed{J(\ell)=\mathrm{LE64}\big(\mathrm{SHA256}(\ell)\big)}\!,
$$

established in S0.3. For S4 Poisson attempts we use the *single* label

$$
\boxed{\ \ell \equiv \text{“poisson_component”}\ }.
$$

Before consuming randomness under label $\ell$, the engine advances the 128-bit counter by $J(\ell)$ (add to low word with carry to high word). This creates label-local lanes and gives **replay under re-ordering** of other labels. The **merchant traversal order** is deterministic in 1A, so per-merchant schedule-independence isn’t required; if that changes, adopt $J(\ell,m)$ as noted in S0.3.

---

## Counters, uniforms and Poisson draws (what the envelope proves)

Let $(c_{\text{hi}},c_{\text{lo}})\in\{0,1\}^{64}\times\{0,1\}^{64}$ be the **Philox 128-bit counter**. Each event records the **counter immediately before** and **immediately after** the RNG consumption:

* `rng_counter_before_{lo,hi}` = $(c_{\text{lo}},c_{\text{hi}})$ **prior** to draws,
* `rng_counter_after_{lo,hi}` = the counter **after** the sampler finishes.

The Poisson sampler itself is unconstrained in form (table lookup, transformed rejection, $\Gamma$–Poisson mixture, etc.) provided it:

1. consumes **only** iid **open-interval** uniforms $u\in(0,1)$, and
2. returns an integer $k\sim\mathrm{Poisson}(\lambda)$ with $\lambda=\lambda_{\text{extra},m}$ **fixed** for the merchant in S4.2.

Because the sampler’s **uniform usage can depend on $k$**, the **difference** between `after` and `before` may vary across attempts; the envelope makes this consumption **auditable** attempt-by-attempt. (All open-interval uniforms satisfy the shared schema primitive `u01`.)

---

## Event record contracts (authoritative payloads + shared envelope)

All RNG JSONL events must include the **RNG envelope**:

$$
\{\texttt{ts_utc},\ \texttt{run_id},\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint},\ \texttt{module},\ \texttt{substream_label},\ \texttt{rng_counter_before_*},\ \texttt{rng_counter_after_*}\},
$$

and the **event-specific payload** below. Paths/partitions come from the dataset dictionary and are fixed as shown.

1. **`poisson_component`** — *every attempt (draw) is one row*
   Payload (required):
   $\{\texttt{merchant_id},\ \texttt{context}=\text{"ztp"},\ \texttt{lambda}>0,\ \texttt{k}\in\{0,1,2,\dots\}\}$.
   Partition: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` (schema: `#/rng/events/poisson_component`). For S4, `context` **must** be `"ztp"` (NB re-uses the same stream with `"nb"`).

2. **`ztp_rejection`** — *diagnostic; zero draw observed*
   Payload (required):
   $\{\texttt{merchant_id},\ \texttt{lambda_extra}=\lambda,\ \texttt{k}=0,\ \texttt{attempt}\in[1,64]\}$.
   Partition: `logs/rng/events/ztp_rejection/...` (schema: `#/rng/events/ztp_rejection`). **No randomness is consumed here**: set `after == before`.

3. **`ztp_retry_exhausted`** — *hard cap reached (merchant abort)*
   Payload (required):
   $\{\texttt{merchant_id},\ \texttt{lambda_extra}=\lambda,\ \texttt{attempts}=64,\ \texttt{aborted}=true\}$.
   Partition: `logs/rng/events/ztp_retry_exhausted/...` (schema: `#/rng/events/ztp_retry_exhausted`). **No randomness consumed**: `after == before`.

All three streams are partitioned by `{seed, parameter_hash, run_id}` exactly as specified in the dictionary.

---

## Presence/absence semantics (validator-visible)

* **Eligible merchants ($e_m=1$).** Must produce a **finite sequence** of `poisson_component` rows (attempts $a=1,2,\dots$) with a **constant** $\lambda$ for the merchant (bit-equal double). If any zero attempts occur, there is a corresponding `ztp_rejection` with strictly increasing `attempt∈\{1,\dots\}`. If and only if **64** zeros occur consecutively, emit exactly one `ztp_retry_exhausted` and **abort** the merchant.
* **Ineligible merchants ($e_m=0$).** Must have **no** S4 events of any type; their $K_m$ was fixed to 0 in S3. Presence is a branch-coherence failure.

---

## Counter discipline (hard invariants)

For any fixed merchant $m$ in S4:

* **Label invariant:** `substream_label == "poisson_component"` for all S4 attempts. Any other label is a protocol breach.
* **Context invariant:** `poisson_component.context == "ztp"` (never `"nb"`).
* **Monotone progress on draws:** For each `poisson_component`, the **after** counter is strictly greater than **before** (lexicographic on $(\text{hi},\text{lo})$), and the sequence of **before** counters across attempts is strictly increasing.
* **Zero-consumption diagnostics:** `ztp_rejection` and `ztp_retry_exhausted` **must not** advance counters: `after == before`. This yields a one-to-one mapping between random consumption and `poisson_component` rows.
* **Payload constancy:** For a given merchant, all attempts carry the **same** `lambda` (= $\lambda_{\text{extra},m}$ from S4.2). Any drift implies state corruption.
* **Attempt indexing:** If emitted, `ztp_rejection.attempt` enumerates the observed zeros $1,2,\dots$ and never exceeds 64; `ztp_retry_exhausted.attempts` is **exactly 64**.

---

## Failure semantics (what triggers aborts)

* **Schema/lineage violation** (missing envelope fields; wrong `context`; bad partitions) → **abort run** in CI.
* **Counter drift** (non-monotone draws; diagnostics advancing counters) → **abort run**.
* **Payload inconsistency** (`lambda≤0`, non-finite; or merchant-local `lambda` mismatch across attempts) → **abort run**.
* **Branch incoherence** (any S4 events for $e_m=0$) → **abort run**.

---

## Outputs (what S4.4 guarantees downstream)

* A **trace-complete** attempt history for each eligible merchant, sufficient to prove reproducibility and to compute rejection-rate corridors in S9 (using `poisson_component` + `ztp_rejection` rows).
* Deterministic **partitions** and **schemas** for the three streams under `{seed, parameter_hash, run_id}`, consumed by validation.

---

## Minimal reference algorithm (code-agnostic)

**Inputs:** merchant $m$ with eligibility $e_m{=}1$; fixed $\lambda=\lambda_{\text{extra},m}>0$ from S4.2; Philox engine with sub-stream jump $J(\text{“poisson_component”})$; run envelope fields.
**Outputs:** a finite sequence of rows in the three event streams; no acceptance decision here.

1. **Enter label lane.** Apply the sub-stream jump for $\ell=$ “poisson_component”; snapshot the 128-bit counter.
2. **Attempt $a\gets 1$.**
3. **Draw once:** generate a Poisson deviate $k\sim\mathrm{Poisson}(\lambda)$ using iid $u\in(0,1)$ uniforms; record **before/after** counters and emit one `poisson_component` row with `context="ztp"`, `lambda=\lambda`, `k`.
4. **If $k=0$:** emit one `ztp_rejection` row with `attempt=a` **without advancing** counters (repeat **before** values in the envelope). Increment $a\gets a+1$.
5. **Stop condition:** this state stops after step 3. (S4.5 inspects $k$ and either accepts $K_m=k$ or continues the loop up to 64.)
6. **Exhaustion case (handled in S4.5):** after the 64th zero, emit exactly one `ztp_retry_exhausted` row **without** counter advance and mark the merchant aborted.

This locks the *RNG contract*—how randomness is isolated, consumed, and evidenced—independent of any particular Poisson algorithm, while staying consistent with your schemas, partitions, and validation plan.

---



# S4.5 — Sampling algorithm (formal)

## Goal

Generate a **single** foreign-country count $K_m$ for each **eligible** merchant $m$ (i.e., $e_m{=}1$), by rejection sampling from a Poisson law with mean $\lambda_{\text{extra},m}$ and **truncation at 0**. Emissions must make the random consumption and control flow **auditable** via the RNG envelope, using the S4 event schemas and partitions defined earlier.

---

## Inputs & preconditions (per eligible merchant $m$)

* $\lambda\equiv\lambda_{\text{extra},m}=\exp(\theta_0+\theta_1\log N_m+\theta_2X_m)>0$ from S4.2; evaluate in binary64 and reject non-finite values (numeric policy).
* **RNG lane:** sub-stream label $\ell=$ “poisson_component” with counters recorded before/after each Poisson attempt; for S4, `context="ztp"`.
* **Event contracts + partitions:** `poisson_component` (attempts), `ztp_rejection` (zeros, attempt-indexed), `ztp_retry_exhausted` (cap at 64); all partitioned by `{seed, parameter_hash, run_id}`.

---

## Construction (attempt loop; target = ZTP)

Let $Y\sim\mathrm{Poisson}(\lambda)$, $K=Y\mid(Y\ge1)$ (pmf from S4.3). We realise $K$ via **rejection from Poisson**:

1. **Attempt index.** Initialise $a\gets 1$.
2. **Draw.** Produce a single **untruncated** Poisson deviate $K_a\in\{0,1,2,\dots\}$ at mean $\lambda$. Emit one `poisson_component` with payload `{merchant_id, context="ztp", lambda=λ, k=K_a}` plus the shared RNG envelope whose `before/after` counters **prove** the exact amount of randomness consumed for this attempt. **For a fixed merchant, `lambda` must be bit-identical across all attempts.**
3. **Branch on $K_a$.**

   * If $K_a=0$: emit `ztp_rejection` with payload `{merchant_id, lambda_extra=λ, k=0, attempt=a}` **without** advancing counters (diagnostic; no randomness). Increment $a\gets a+1$ and continue.
   * If $K_a\ge 1$: **accept** and set $K_m\leftarrow K_a$; **stop**.
4. **Hard cap.** If after emitting the $a{=}64$-th rejection we still have $K_{64}=0$: emit a single `ztp_retry_exhausted` with `{merchant_id, lambda_extra=λ, attempts=64, aborted=true}` (no counter advance) and **abort** this merchant; downstream S5–S6 must not execute for $m$.

All uniforms used inside the Poisson deviate generator are **open-interval** $u\in(0,1)$ (`u01` primitive); the envelope counters are the audit trail of consumption.

---

## Emissions (what appears in each stream)

If accepted at attempt $a$ with $K_a=k\ge1$:

* Exactly **$a$** rows in `poisson_component` (attempts 1…$a$), `context="ztp"`, constant `lambda=λ`.
* Exactly **$a{-}1$** rows in `ztp_rejection` with `attempt=1,…,a-1`.
* **No** `ztp_retry_exhausted`.

If exhausted (64 zeros):

* Exactly **64** rows in `poisson_component` (all with `k=0`, constant `lambda=λ`).
* Exactly **64** rows in `ztp_rejection` with `attempt=1,…,64`.
* Exactly **one** `ztp_retry_exhausted` row; merchant is **aborted**.

Partitions and schema refs are those pinned in the dataset dictionary (no deviations permitted).

---

## Probabilistic diagnostics (for corridor checks; not logged)

* **Acceptance per attempt:** $p_{\text{acc}}=1-e^{-\lambda}$.
* **Rejections before success:** $R\sim\mathrm{Geom}(p_{\text{acc}})$ (failures-before-success), with $\mathbb{E}[R]=\tfrac{e^{-\lambda}}{1-e^{-\lambda}}$.
* **Exhaustion probability:** $P(\text{abort at 64})=P(R\ge 64)=e^{-64\lambda}$.
  These close-forms back S9’s corridors (e.g., empirical mean rejections $<0.05$, $p_{99.9}<3$); violations abort the run in CI.

---

## Outputs (state boundary)

* **In-memory:** a single integer $\boxed{K_m\in\{1,2,\dots\}}$ for accepted merchants; **no value** (merchant aborted) on exhaustion. This $K_m$ fixes the required length of the later `country_set` and of the Dirichlet vector in S7.
* **Authoritative logs:** the three RNG streams with their envelopes, partitions, and payload constraints as above.

---

## Invariants & guards (checked for each eligible merchant)

* **I-lambda-constancy:** all `poisson_component` rows for $m$ carry the **same** `lambda=λ` (bit-equal).
* **I-context:** `poisson_component.context=="ztp"` for S4; never `"nb"`.
* **I-counters:** `after > before` for each `poisson_component`; `after == before` for `ztp_rejection` and `ztp_retry_exhausted`. Monotone **before** counters across attempts.
* **I-attempt indexing:** `ztp_rejection.attempt` strictly $1…$ and $\le 64$; if 64 rejections occur, there must be **exactly one** `ztp_retry_exhausted`.
* **I-branch-coherence:** no S4 events for $e_m{=}0$ (caught earlier, re-checked here).

---

## Minimal reference algorithm (code-agnostic; matches the spec)

```text
INPUT:
  eligible merchant m
  λ = λ_extra,m > 0 (from S4.2, binary64, finite)
  Philox sub-stream label ℓ = "poisson_component"
  RNG envelope fields (seed, parameter_hash, manifest_fingerprint, run_id, ...)

OUTPUT:
  Either: accepted integer K_m ≥ 1 and a finite attempt trace; or merchant abort after 64 zeros.

1  a ← 1
2  repeat:
3      # One Poisson attempt at mean λ (consumes open-interval uniforms u ∈ (0,1))
4      (c_before) ← snapshot Philox counter
5      k ← draw_poisson(λ)            # any correct Poisson algorithm using iid u ∈ (0,1)
6      (c_after)  ← snapshot Philox counter
7      emit poisson_component{ merchant_id=m, context="ztp", lambda=λ, k=k,
                               envelope: substream_label=ℓ, before=c_before, after=c_after }
8      if k = 0 then
9          # Diagnostic event; no RNG consumption
10         emit ztp_rejection{ merchant_id=m, lambda_extra=λ, k=0, attempt=a,
                               envelope: before=c_after, after=c_after }
11         if a = 64 then
12             emit ztp_retry_exhausted{ merchant_id=m, lambda_extra=λ, attempts=64, aborted=true,
                                        envelope: before=c_after, after=c_after }
13             ABORT merchant m
14         else
15             a ← a + 1
16             continue  # next attempt
17     else  # k ≥ 1
18         ACCEPT: set K_m ← k
19         STOP
```

This stays exactly within your schemas and dictionary (payloads, partitions, envelope), and produces a **trace-complete** audit that S9 can verify against the ZTP law and corridor checks.

---



# S4.6 — Determinism & correctness invariants

## Observables (what S4 produces that we can test)

For each **eligible** merchant $m$ with $\lambda=\lambda_{\text{extra},m}>0$ (from S4.2), S4 emits:

* A finite sequence of **attempt** records in `poisson_component` with `context="ztp"`, each carrying the **same** `lambda=λ` (bit-equal double) and an untruncated Poisson draw `k∈{0,1,2,…}`. Each row has the **RNG envelope** with pre/post 128-bit Philox counters.
* Zero or more `ztp_rejection` rows (one per attempt with `k=0`), with an **attempt index** $a=1,2,\dots$ and **no counter advance** (`after==before`).
* At most one `ztp_retry_exhausted` row if 64 zeros occur; also with **no counter advance**.

Ineligible merchants $e_m=0$ have **no** S4 events by design (branch coherence from S3).

---

## I-ZTP1 — Bit-replay (determinism of the attempt sequence)

**Statement.** For fixed inputs $(N_m,X_m,\boldsymbol\theta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the internal uniforms are a **deterministic function** of the Philox 128-bit counter under sub-stream label $\ell=$"poisson_component". Therefore the **attempt sequence** $(K_1,K_2,\dots)$ and the **accepted** $K_m$ are **bit-identical across replays**. Evidence is the equality of all envelope counters and payloads across runs.

**Validator check.** For a sample of merchants, re-run the Poisson sampler from stored inputs and **assert exact equality** of: (a) the attempt count, (b) each `k`, (c) each pair of `{before, after}` counters, and (d) the final $K_m$ (or exhaustion). Any mismatch ⇒ **RNG replay failure**.

---

## I-ZTP2 — Event coverage (trace completeness)

**Statement.**
If $K_m\ge 1$: there exists **≥1** `poisson_component` (with `context="ztp"`) and **0..(a−1)** `ztp_rejection` rows preceding acceptance at attempt $a$.
If 64 zeros were observed: there exist **exactly 64** `poisson_component` rows with `k=0`, **exactly 64** `ztp_rejection` rows with attempts 1..64, and **exactly one** `ztp_retry_exhausted`; merchant is **aborted**. Missing or extra required events ⇒ **structural failure**.

**Validator check.** Group events by merchant; check cardinalities and the acceptance/exhaustion branching rules above. Absent S4 events for an eligible merchant (without `retry_exhausted`) ⇒ failure. Any S4 events for $e_m=0$ ⇒ **branch-coherence** failure.

---

## I-ZTP3 — Attempt indexing (ordering & bounds)

**Statement.** In the rejection branch, `ztp_rejection.attempt` is **strictly increasing** from 1 and **never exceeds 64**; if 64 occurs, `ztp_retry_exhausted.attempts` is **exactly 64**.

**Validator check.** For each merchant, compute $r_m=\#\{\text{rejections}\}$. Assert the observed attempt indices are exactly $\{1,\dots,r_m\}$, and if $r_m=64$ then a single `retry_exhausted` is present. Otherwise fail.

---

## I-ZTP4 — Schema, context & payload constancy

**Statement.** Every S4 event row conforms to the **RNG envelope** schema; `poisson_component.context=="ztp"` (never `"nb"`), `lambda>0` is **bit-constant** per merchant, and `k` is integer. `ztp_*` diagnostics **do not** advance counters: `after==before`.

**Validator check.** Schema validation + three hard asserts: (i) **context** correctness; (ii) **lambda constancy** across attempts for a merchant; (iii) **counter discipline** (`after>before` for draws, equality for diagnostics). Violations ⇒ **abort run**.

---

## I-ZTP5 — Corridor checks (population-level behavior)

**Statement.** Over the set $\mathcal{M}$ of **eligible** merchants entering S4, let $R_m$ be the **rejection count** (zeros) per merchant. Compute:

$$
\widehat{\mu}_R \;=\; \frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}} R_m,
\qquad
\widehat{Q}_{0.999} \;=\; \text{empirical 99.9th percentile of } \{R_m\}_{m\in\mathcal{M}}.
$$

Require the **run-level corridor**:

$$
\boxed{\ \widehat{\mu}_R < 0.05 \quad\text{and}\quad \widehat{Q}_{0.999} < 3\ }.
$$

These are **mixture-of-Geometric** diagnostics implied by ZTP acceptance $p_{\text{acc}}=1-e^{-\lambda}$ (S4.3); violations indicate drift in $\lambda$ across merchants or implementation error and **abort the run** (recorded by validation). Aborted merchants contribute $R_m{=}64$ to these summaries.

**Estimator details.**

* $\widehat{\mu}_R$ is the **plain average** over all eligible merchants (including exhaustions).
* $\widehat{Q}_{0.999}$ is the **order statistic** at rank $\lceil 0.999\,|\mathcal{M}|\rceil$ on the multiset $\{R_m\}$; for small $|\mathcal{M}|$, interpolation is disallowed (conservative, integer-valued). Both figures are written into the validation bundle.

---

## I-ZTP6 — Acceptance-law coherence (per-merchant)

**Statement.** For each merchant, the **attempts until success** satisfy $A_m=R_m+1$ if accepted, or $A_m=64$ if exhausted. Moreover, for accepted merchants the acceptance happened at the **first** attempt with `k≥1`. (No skipped or duplicated attempts.)

**Validator check.** Reconstruct $A_m$ from the attempt trace and compare against `ztp_rejection` counts; assert **exact equality** with these formulas. Any mismatch ⇒ trace corruption.

---

## I-ZTP7 — Absence for ineligible

**Statement.** If $e_m=0$, **no** S4 events of any type may exist for $m$ (enforced already in S3; re-checked here). Presence is a **branch-coherence** failure.

---

## Failure semantics (recap)

* **RNG/Schema violation** (envelope missing fields; wrong context; counter rules broken) ⇒ **abort run**.
* **Corridor breach** (I-ZTP5) ⇒ **abort run**, metrics written to the validation bundle.
* **Numeric policy error** from S4.2 ($\lambda$ non-finite or $\le 0$) ⇒ **abort merchant** (no S4 events).

---

## Minimal reference algorithm (code-agnostic; validator view)

```text
INPUT:
  Events grouped by merchant m:
    E_pc(m) = ordered 'poisson_component' rows with context="ztp"
    E_rj(m) = 'ztp_rejection' rows
    E_rx(m) = 'ztp_retry_exhausted' row (0 or 1)
  Eligibility flags e_m from S3
OUTPUT:
  Pass/Fail for I-ZTP1..I-ZTP7; metrics (μ̂_R, Q̂_0.999)

1  for each merchant m:
2      if e_m = 0:
3          assert |E_pc(m)| = |E_rj(m)| = |E_rx(m)| = 0      # I-ZTP7
4          continue
5      # Context, schema, lambda constancy, counters
6      assert every row in E_pc(m) has context="ztp" and valid envelope  # I-ZTP4
7      assert lambda is bit-identical across E_pc(m)                     # I-ZTP4
8      assert counters advance: after>before for E_pc(m); equality for E_rj/E_rx  # I-ZTP4
9      # Attempt indexing and coverage
10     let r_m := |E_rj(m)|
11     assert attempts(E_rj(m)) = {1,...,r_m} and r_m ≤ 64              # I-ZTP3
12     if |E_rx(m)| = 1:
13         assert r_m = 64 and |E_pc(m)| = 64 and all k=0                # I-ZTP2
14         mark merchant m as aborted
15     else:
16         assert |E_pc(m)| ≥ 1 and last k ≥ 1 and earlier ks = 0        # I-ZTP2 & I-ZTP6
17         set K_m := last k
18  # Population corridors
19  let M := {eligible merchants}
20  compute μ̂_R := mean over m∈M of r_m (use r_m=64 for aborted)        # I-ZTP5
21  compute Q̂_0.999 := order statistic at ceil(0.999 * |M|) of {r_m}    # I-ZTP5
22  assert μ̂_R < 0.05 and Q̂_0.999 < 3                                  # I-ZTP5
23  PASS if all assertions hold; else FAIL with exact invariant id(s)
```

---



# S4.7 — Failure modes (abort semantics)

## Goal

Define the **exhaustive set of failure conditions** for S4 (the ZTP foreign-country count), the **precise triggers** (math/logic), the **observable artefacts** in the RNG event streams, and the exact **abort action** (merchant-scoped vs run-scoped). This guarantees deterministic, auditable behaviour and clean handoff (or clean stop) to S5–S6.

---

## Scope & notation (recap)

* Eligible merchant $m$: $e_m=1$; size $N_m\ge2$; $\lambda\equiv\lambda_{\text{extra},m}=\exp(\theta_0+\theta_1\log N_m+\theta_2 X_m)>0$ computed in S4.2.
* Attempt draws: $K_a\sim\mathrm{Poisson}(\lambda)$, accept on $K_a\ge1$; truncate zero.
* Event streams: `poisson_component` (attempts, consumes RNG), `ztp_rejection` (zero draws, **no** RNG), `ztp_retry_exhausted` (cap at 64, **no** RNG).
* Envelope: every row carries `{seed, parameter_hash, manifest_fingerprint, substream_label, rng_counter_before/after, ...}`.

---

## Failure taxonomy (what can go wrong and how it’s seen)

### A. Merchant-scoped aborts (drop the merchant; run continues)

**F-S4.2-NUM: Numeric invalid**

* **Trigger (math):** $\lambda=\exp(\eta_m)$ is **non-finite** or $\le 0$ (overflow/NaN/negative) when computed in binary64.
* **Observables:** **No** S4 events for $m$ (by design); an error record in the validation bundle may reference the merchant and cause.
* **Action:** **Abort merchant.** S5–S6 **must not** execute for $m$.
* **Determinism:** Replays with the same inputs fail identically.

**F-S4.5-RETRY: Retry exhaustion**

* **Trigger (probabilistic):** 64 consecutive zero draws $K_1=\cdots=K_{64}=0$.
* **Observables:**

  * Exactly **64** `poisson_component` rows (`k=0`, constant `lambda`),
  * Exactly **64** `ztp_rejection` rows with `attempt=1..64`,
  * Exactly **one** `ztp_retry_exhausted` row (no counter advance).
* **Action:** **Abort merchant.** No S5–S6 for $m$.
* **Note:** $P(\text{exhaustion})=e^{-64\lambda}$; the *existence* of the three bullet points above is the proof of correct handling.

**F-S4.5-CTX: Context mismatch (merchant-local)**

* **Trigger (logic):** Any `poisson_component` for $m$ with `context!="ztp"` in S4.
* **Observables:** One or more bad rows for $m$; envelope present.
* **Action:** Treat as **run-scoped** (see below) if systemic; if the framework supports quarantining a single merchant’s rows, you may **abort run** (preferred) rather than silently drop. (Policy: fail closed.)

**F-S4.5-LAMBDA-DRIFT: Per-merchant lambda not bit-constant**

* **Trigger (logic):** For a fixed $m$, `lambda` payload differs across attempts (not bit-identical to the S4.2 value).
* **Observables:** ≥1 `poisson_component` row with `lambda≠λ` compared against the first row.
* **Action:** **Abort run** (see below). Rationale: indicates state corruption, not a local anomaly.

> In practice, we treat CTX and LAMBDA-DRIFT as **run-scoped** because they indicate systemic schema or state errors. They’re listed here for completeness with their per-merchant manifestations.

---

### B. Run-scoped aborts (kill the entire run)

**F-S4.4-SCHEMA: Schema/lineage violation**

* **Trigger (contract):** Any required **RNG envelope field missing**; invalid types; wrong partitions; or an event missing required payload fields (`merchant_id`, `lambda`/`lambda_extra`, integer `k`, valid `attempt`).
* **Observables:** Offending rows anywhere in the S4 streams.
* **Action:** **Abort run immediately.** (No partial egress.)

**F-S4.4-COUNTER: Counter discipline violation**

* **Trigger (contract):**

  * a `poisson_component` row where `after≤before`, or
  * a `ztp_*` row where `after≠before`, or
  * non-monotone `before` counters across attempts for a merchant.
* **Observables:** Envelope counters contradict rules.
* **Action:** **Abort run.**

**F-S4.5-COVERAGE: Event coverage inconsistency**

* **Trigger (logic):**

  * Accepted $K_m\ge1$ but missing prior `poisson_component`, or
  * Rejections present without matching `poisson_component` zero attempts, or
  * 64 rejections without a `ztp_retry_exhausted`.
* **Observables:** Cardinality/indexing contradictions.
* **Action:** **Abort run.**

**F-S4.6-CORRIDOR: Corridor check failure (population-level)**

* **Trigger (stats):** Over eligible merchants, the empirical mean rejections $\widehat{\mu}_R\ge0.05$ **or** empirical $p_{99.9}\ge3$.
* **Observables:** Validation bundle metrics exceed thresholds.
* **Action:** **Abort run** (drift or implementation error).

**F-S4.3-CTX-MIX: Stream context contamination**

* **Trigger (contract):** Presence in S4 of any `poisson_component` with `context="nb"` (belongs to S2) or any other non-"ztp" tag.
* **Action:** **Abort run.**

**F-S4.1-BRANCH: Branch incoherence**

* **Trigger (control-flow):** Any S4 events exist for an **ineligible** merchant $(e_m=0)$.
* **Observables:** Non-empty S4 streams for such merchants.
* **Action:** **Abort run.**

---

## What is emitted (and what is not), per failure

| Failure code    |     Emits `poisson_component` | Emits `ztp_rejection` | Emits `ztp_retry_exhausted` | Downstream (S5–S6) | Abort scope |
| --------------- | ----------------------------: | --------------------: | --------------------------: | -----------------: | ----------- |
| F-S4.2-NUM      |                        **No** |                **No** |                      **No** |  **Skip merchant** | Merchant    |
| F-S4.5-RETRY    |            **Yes (64 zeros)** |     **Yes (64 rows)** |             **Yes (1 row)** |  **Skip merchant** | Merchant    |
| F-S4.4-SCHEMA   |                 N/A (invalid) |                   N/A |                         N/A |                N/A | **Run**     |
| F-S4.4-COUNTER  |                 N/A (invalid) |                   N/A |                         N/A |                N/A | **Run**     |
| F-S4.5-COVERAGE |                  Inconsistent |          Inconsistent |               Missing/extra |                N/A | **Run**     |
| F-S4.6-CORRIDOR |                   As observed |           As observed |                 As observed |                N/A | **Run**     |
| F-S4.3-CTX-MIX  |   As observed (wrong context) |                     — |                           — |                N/A | **Run**     |
| F-S4.1-BRANCH   | As observed (should be empty) |                     — |                           — |                N/A | **Run**     |

(**N/A** = CI stops on detection; downstream never runs.)

---

## Deterministic error identifiers (recommended)

To make diagnostics grep-friendly and stable across systems, emit structured identifiers alongside human text:

* `err_code`: `E/1A/S4/<CLASS>/<DETAIL>`

  * Examples:

    * `E/1A/S4/NUMERIC/NONFINITE_LAMBDA` (F-S4.2-NUM),
    * `E/1A/S4/RETRY/EXHAUSTED_64` (F-S4.5-RETRY),
    * `E/1A/S4/SCHEMA/MISSING_ENVELOPE_FIELD` (F-S4.4-SCHEMA),
    * `E/1A/S4/COUNTER/ADVANCE_ON_DIAGNOSTIC` (F-S4.4-COUNTER),
    * `E/1A/S4/COVERAGE/MISSING_RETRY_EXHAUSTED` (F-S4.5-COVERAGE),
    * `E/1A/S4/CORRIDOR/MEAN_REJ_OVER_0p05` (F-S4.6-CORRIDOR),
    * `E/1A/S4/CONTEXT/NOT_ZTP`, `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`.

Include `{merchant_id, lambda, attempt_if_applicable, counters_before/after, partition_path}` in the diagnostic payload for reproducible triage.

---

## Invariants reasserted at failure boundaries

* **No half-emissions:** Merchant-scoped numeric failure **must not** write any S4 event rows; retry-exhausted **must** write the exact triple (64 attempt rows, 64 rejections, 1 exhausted).
* **Counter discipline preserved:** Diagnostics never advance counters—even in failure paths.
* **Immutability of earlier states:** S4 failures **cannot** alter $N_m$, $K_m$ (unset on abort), `country_set`, or any 1A egress; they only gate entry to S5–S6 for that merchant.
* **Idempotence:** Re-running the same inputs reproduces the same failure class and artefact pattern bit-for-bit.

---

## Minimal reference algorithm (code-agnostic; failure classification)

```text
INPUT:
  For a merchant m: eligibility e_m, λ from S4.2 (may be invalid), and the S4 event streams grouped by m
OUTPUT:
  One of: {ACCEPT(K_m≥1)}, {ABORT_MERCHANT with code}, or {ABORT_RUN with code}

1  if e_m = 0 then
2      if any S4 events exist for m: ABORT_RUN("E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS")
3      else: return SKIP_MERCHANT  # not a failure; branch coherence holds
4
5  # Numeric validity first
6  if not isfinite(λ) or λ ≤ 0:
7      return ABORT_MERCHANT("E/1A/S4/NUMERIC/NONFINITE_LAMBDA")
8
9  # Schema / lineage / counter / context checks
10 if schema_or_partition_invalid(events(m)):
11     ABORT_RUN("E/1A/S4/SCHEMA/MALFORMED_EVENT")
12 if any poisson_component.context != "ztp":
13     ABORT_RUN("E/1A/S4/CONTEXT/NOT_ZTP")
14 if counters_violate_rules(events(m)):
15     ABORT_RUN("E/1A/S4/COUNTER/VIOLATION")
16 if lambda_not_bitconstant_across_attempts(events(m), λ):
17     ABORT_RUN("E/1A/S4/PAYLOAD/LAMBDA_DRIFT")
18
19  # Coverage & acceptance
20 r ← number of ztp_rejection rows for m
21 if has_retry_exhausted(m):
22     if r = 64 and exactly 64 poisson_component with k=0:
23         return ABORT_MERCHANT("E/1A/S4/RETRY/EXHAUSTED_64")
24     else:
25         ABORT_RUN("E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION")
26 else:
27     if last poisson_component has k ≥ 1 and prior attempts (if any) have k = 0
28         return ACCEPT( K_m ← last k )
29     else:
30         ABORT_RUN("E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION")
```

This pins **what fails, how we see it, and what happens next**—without dropping into implementation details—so S4 remains deterministic, auditable, and safe to wire into S5–S6 or to abort cleanly.

---



# S4.8 — Outputs (state boundary)

## What S4 hands to downstream (per merchant)

### 1) In-memory state (only for **eligible** merchants that **did not** exhaust retries)

For each merchant $m$ with $e_m=1$ that accepted before the 64-retry cap, S4 exposes the single scalar:

$$
\boxed{\ K_m \in \{1,2,\dots\}\ }\quad\text{(foreign-country count)}.
$$

This value is **read-only** for S5–S6 and fixes the required length of the later **ordered country set** (home at rank 0 plus $K_m$ foreigns) and the **Dirichlet vector** used in S7 (dimension $K_m{+}1$).

### 2) Authoritative RNG event streams (always partitioned by $\{\texttt{seed},\texttt{parameter_hash},\texttt{run_id}\}$)

S4 persists **only** event streams (no parameter-scoped data). These are the canonical audit trail and are used by validation to recompute corridors and replay deterministically:

* `logs/rng/events/poisson_component/...` — **≥1 row** per eligible merchant entering S4; payload includes `context="ztp"`, `lambda=λ_{extra,m}>0`, `k∈{0,1,2,…}`, plus the shared RNG envelope (pre/post 128-bit counters). Schema ref `#/rng/events/poisson_component`.
* `logs/rng/events/ztp_rejection/...` — **0..64 rows** (one per zero draw) with `attempt=1…` in strict order; **counters do not advance** for this diagnostic stream. Schema ref `#/rng/events/ztp_rejection`.
* `logs/rng/events/ztp_retry_exhausted/...` — **≤1 row**; present **only** when 64 consecutive zeros occurred; **counters do not advance**. Schema ref `#/rng/events/ztp_retry_exhausted`.

All three streams use the layer-wide RNG envelope and fixed dictionary paths; validators assert partitioning exactly equals `{seed, parameter_hash, run_id}`.

### 3) Ineligible branch (no outputs from S4)

For merchants with $e_m=0$ (decision fixed by S3), S4 produces **no** ZTP events; their state remains $K_m:=0$ and they **bypass** S4–S6 to the later deterministic steps. Presence of any S4 events for such merchants is a **branch-coherence** failure surfaced by validation.

---

## Cardinality & payload invariants (what downstream/validation may rely on)

* **Attempt trace completeness.** For every eligible merchant, the union of the three streams encodes a **finite** attempt trace ending either in acceptance (some `poisson_component` with `k≥1`) or in exhaustion (exactly one `ztp_retry_exhausted` after 64 `ztp_rejection`s). Missing any required row is a structural error.
* **Lambda constancy.** Within a merchant’s `poisson_component` rows, the payload `lambda` is **bit-identical** to the $\lambda_{\text{extra},m}$ computed in S4.2, and **constant across attempts**. This is rechecked by validation.
* **Envelope discipline.** Every row in all three streams carries the shared RNG envelope; for draws, counters **advance**; for diagnostics (`ztp_*`), `after == before`. These rules enable exact replay and consumption accounting.
* **Partitions are governed.** Paths are fixed by the dataset dictionary and **must** partition by `{seed, parameter_hash, run_id}`—no alternative layouts are permitted.

---

## What S4 does **not** produce

S4 writes **no** new parameter-scoped datasets and **no** egress tables. Its sole persisted artefacts are the RNG event streams above; everything else (e.g., candidate weights, ordered country sets) is produced in S5–S6 using $K_m$ and the governed reference inputs.

---

## Minimal reference algorithm (code-agnostic; boundary view)

```text
INPUT (per merchant m):
  eligibility e_m from S3; ZTP attempt streams grouped by m
OUTPUT:
  Boundary state for downstream + audit artefacts

1  if e_m = 0:
2      # S3 fixed domestic-only branch
3      assert no S4 streams exist for m                   # branch coherence
4      expose K_m := 0 to downstream gate (skip S4–S6)   # S3 responsibility
5      RETURN

6  # Eligible branch: infer boundary from attempt trace
7  let P := poisson_component rows for m (context="ztp")
8  let R := ztp_rejection rows for m (attempt 1..)
9  let X := ztp_retry_exhausted row for m (0 or 1)

10 assert |P| ≥ 1, partitions = {seed, parameter_hash, run_id}  # dictionary contract
11 assert lambda is bit-constant across P and > 0                # payload invariant
12 if |X| = 1:
13     assert |R| = 64 and |P| = 64 and all P.k = 0              # exhaustion signature
14     mark merchant m as ABORTED; do not expose K_m
15 else:
16     let k* := last(P).k
17     assert k* ≥ 1 and all prior P.k = 0 and attempts(R) = {1..|R|}
18     expose K_m := k* to S5–S6                                 # state hand-off
19 RETURN
```

This pins the **state boundary** precisely: a single in-memory scalar $K_m$ when accepted; or a clean abort signature on disk when exhausted; and **no outputs** at all for ineligible merchants—exactly as your state flow specifies.
