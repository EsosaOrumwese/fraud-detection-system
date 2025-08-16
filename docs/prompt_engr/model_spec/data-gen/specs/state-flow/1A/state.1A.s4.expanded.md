# S4.1 — Universe, symbols, authority

## 1) Scope & entry gate (who can be here)

Evaluate S4 **only** for merchants $m$ that:

* were classified **multi-site** in S1 (so S2 ran and accepted a domestic count), and
* are **eligible for cross-border** per S3, i.e. $e_m=1$. Ineligible merchants $e_m=0$ **must not** produce any S4 events; they keep $K_m:=0$ and skip S4–S6. This branch-coherence rule is already asserted in S3 and re-checked here.

> Contract: If $e_m=0$ then the streams `poisson_component`, `ztp_rejection`, `ztp_retry_exhausted` are **absent** for that merchant. Presence is a run-stopping validation error.

## 2) Symbols & inputs available at S4 entry

Per merchant $m$:

* Identity & home: $(\texttt{merchant_id}=m,\ \texttt{home_country_iso}=c)$ from ingress/S0.
* S2 output: **accepted** domestic outlet count $N_m\in\{2,3,\dots\}$ (read-only in S4).
* S3 gate: eligibility flag $e_m\in\{0,1\}$ (deterministic).
* Hyperparameters: $\theta=(\theta_0,\theta_1,\theta_2)$ and governance metadata loaded from `crossborder_hyperparams.yaml`. (Wald/drift constraints are enforced at load or CI; S4 just consumes.)
* Feature(s): openness scalar $X_m\in[0,1]$ from `crossborder_features` (parameter-scoped; keyed by `merchant_id`).
* Lineage carried into *every* RNG event: `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, and the RNG envelope counters (see §4).

Derived (for later S4.2): the canonical-scale predictor $\eta_m$ and mean $\lambda_{\text{extra},m}=\exp(\eta_m)>0$. **No draws occur in S4.1.**

## 3) Outputs S4 is allowed to produce (authority)

S4 persists **only RNG event streams** (plus the in-memory scalar $K_m$ once accepted). All S4 event datasets are **fixed by the dataset dictionary** and must partition exactly by `{seed, parameter_hash, run_id}`; no alternate partition layouts are permitted.

**Authoritative event streams used by S4:**

1. `logs/rng/events/poisson_component/...` with schema `#/rng/events/poisson_component`. Used in S2 and S4; **S4 rows must have `context="ztp"`** to disambiguate from S2 (`"nb"`).
2. `logs/rng/events/ztp_rejection/...` with schema `#/rng/events/ztp_rejection`. One row per zero draw, attempt-indexed. **Counters must not advance**.
3. `logs/rng/events/ztp_retry_exhausted/...` with schema `#/rng/events/ztp_retry_exhausted`. Present iff 64 consecutive zeros occurred. **Counters must not advance**.

> S4 writes **no** parameter-scoped datasets and **no** egress tables; only these event streams. Downstream artifacts (candidate weights, ordered `country_set`) are produced in S5–S6 using $K_m$.

## 4) RNG envelope, substreams, counters (hard protocol)

Every S4 event row **must** carry the layer-wide RNG envelope:

```
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
  module, substream_label, rng_counter_before_lo, rng_counter_before_hi,
  rng_counter_after_lo,  rng_counter_after_hi, merchant_id, ...payload... }
```

Purpose: enable **bit-replay** and consumption accounting across runs and modules.

**Substream label & context (S4):**

* `substream_label = "poisson_component"` for S4 attempts.
* `poisson_component.context = "ztp"` (never `"nb"` in S4). Mixing `"nb"` here is a run-stopping context contamination error.

**Counter discipline:**

* For each `poisson_component` row (a *draw*), `after > before` (lexicographic on the two 64-bit words) and the sequence of `before` counters is strictly increasing across attempts.
* For diagnostic streams `ztp_rejection` and `ztp_retry_exhausted`, **no RNG is consumed**: `after == before`.
* Violations → **abort run** (schema/counter/lineage failure).

**Uniforms & source of randomness:** Poisson draws in S4 use the keyed substream mapping from S0.3.3 and the **open-interval** $U(0,1)$ primitive per S0.3.4. S4 references the **Poisson(λ) regime selection** defined in S0.3.7. (Cross-referenced in the locked S4 text.)

## 5) Event payloads (exact fields, domains, invariants)

All three streams inherit the RNG envelope (above). The **payload fields** and **merchant-local invariants** for S4 are:

### 5.1 `poisson_component` (context="ztp")

Required payload per row $a=1,2,\dots$:

* `merchant_id` = $m$ (FK to ingress universe).
* `context` = `"ztp"` (string literal).
* `lambda` = $\lambda_{\text{extra},m}$ (IEEE-754 binary64, **strictly positive**).
* `k` = drawn count $k_a\in\{0,1,2,\dots\}$ (integer).
* `attempt` = $a\in\mathbb{N}$ (1-based, strictly increasing).

**Lambda constancy:** For a fixed $m$, `lambda` is **bit-identical** across all attempts and equals the S4.2 value recomputed from $(N_m,\theta,X_m)$. Drift → **abort run**.

### 5.2 `ztp_rejection` (diagnostic; zero consumption)

Required payload per rejection $r=1,2,\dots$:

* `merchant_id` = $m$
* `lambda` = $\lambda_{\text{extra},m}$ (binary64, same constancy rule)
* `attempt` = $r$ (matches the attempt index of the corresponding zero draw)

**Counters:** `after == before` (no RNG consumed by the diagnostic write).

### 5.3 `ztp_retry_exhausted` (diagnostic; zero consumption)

Required payload (at most one row per $m$):

* `merchant_id` = $m$
* `lambda` = $\lambda_{\text{extra},m}$
* `attempts` = `64` (integer literal)
* `aborted` = `true` (boolean)

Present **iff** 64 consecutive `k=0` were observed. `after == before`.

### 5.4 Cardinality & coverage (per merchant)

* If accepted: ≥1 `poisson_component` row with `k≥1`; any preceding zero attempts must have matching `ztp_rejection` rows with attempts $1,\dots,r_m$.
* If exhausted: **exactly 64** `poisson_component` rows with `k=0`, **exactly 64** `ztp_rejection` rows (attempts 1..64), and **exactly one** `ztp_retry_exhausted`. Missing/extra ⇒ structural error.

## 6) Partitions, paths, and ownership (dictionary authority)

All three S4 event streams are governed by the dataset dictionary and **must** be written under these path/partition contracts:

* **Poisson**: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  `schema_ref: schemas.layer1.yaml#/rng/events/poisson_component`
  `produced_by: 1A.nb_poisson_component` *(shared stream id; S4 constrains `context="ztp"`)*.

* **ZTP rejection**: `logs/rng/events/ztp_rejection/...`
  `schema_ref: schemas.layer1.yaml#/rng/events/ztp_rejection`
  `produced_by: 1A.ztp_sampler`.

* **ZTP retry exhausted**: `logs/rng/events/ztp_retry_exhausted/...`
  `schema_ref: schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`
  `produced_by: 1A.ztp_sampler`.

The openness feature comes from:
`data/layer1/1A/crossborder_features/parameter_hash={parameter_hash}/` with schema `schemas.1A.yaml#/model/crossborder_features`. Role: “Deterministic per-merchant features for S4; currently the openness scalar $X_m \in [0,1]$.”

## 7) Determinism & invariants the validator will assert

* **I-ZTP1 (bit-replay):** For fixed $(N_m,X_m,\theta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the attempt sequence $(K_1,K_2,\dots)$ and accepted $K_m$ are **bit-identical** across runs; envelope counters and payloads must match exactly.
* **I-ZTP2–3 (coverage & indexing):** Trace completeness and strict attempt numbering; exhaustion signature is unique.
* **I-ZTP4 (schema conformance):** Envelope present; `context="ztp"`; `lambda>0`; counters advance for draws and do **not** advance for diagnostics.
* **I-ZTP5 (population corridors):** mean rejections $<0.05$ and empirical $p_{99.9}<3$. Breach ⇒ **abort run**.
* **I-ZTP7 (absence for ineligible):** No S4 events when $e_m=0$.

## 8) Failure classes visible at the S4.1 boundary

S4.1 itself performs **no sampling**; it **prepares** the context and asserts contracts. Failures here:

* **Branch incoherence:** any S4 event exists for $e_m=0$ ⇒ **abort run** (`E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`).
* **Schema/lineage/counter prep errors:** missing envelope fields or bad partitions for any S4 event ⇒ **abort run**.
* **Config/governance violation** on $\theta$ (e.g., $\theta_1\notin(0,1)$) is caught when loading for S4.2 and treated as **run-scoped** CI failure.

## 9) Reference routine for S4.1 (no RNG; open writers & bind envelope)

This routine stages inputs, enforces absence rules for ineligible merchants, and opens the event writers with the governed partitions and envelope. **Do not exponentiate or draw here.**

```
INPUT (per merchant m):
  - merchant_id=m, home_country_iso=c, mcc, channel
  - N_m >= 2 from S2 (accepted)
  - e_m in {0,1} from crossborder_eligibility_flags (S3)
  - (theta0, theta1, theta2, X_m, governance_meta) from hyperparam bundle
  - lineage: seed, parameter_hash, manifest_fingerprint, run_id

OUTPUT:
  - PREPARED_CONTEXT(m, c, N_m, theta, X_m, envelope_base)
  - open writers for {poisson_component, ztp_rejection, ztp_retry_exhausted}
    partitioned by {seed, parameter_hash, run_id}
  - NO RNG consumed; NO events written yet

Algorithm:
1  assert is_multi(m) == true           # from S1/S2 boundary
2  if e_m == 0:
3      register_absence_contract(m, streams={poisson_component, ztp_rejection, ztp_retry_exhausted})
4      return NO_OP                     # K_m := 0 fixed by S3; S4 must emit nothing
5  # Eligible branch:
6  load (theta0, theta1, theta2, X_m, governance_meta) from crossborder_hyperparams.yaml
7  # Defer numeric guards to S4.2; here we only stage:
8  eta_m := theta0 + theta1 * log(N_m) + theta2 * X_m   # IEEE-754 binary64 (not persisted here)
9  # Open writers with dictionary partitions (no rows written yet):
10 open_stream_writer("logs/rng/events/poisson_component", partitions={seed, parameter_hash, run_id})
11 open_stream_writer("logs/rng/events/ztp_rejection",     partitions={seed, parameter_hash, run_id})
12 open_stream_writer("logs/rng/events/ztp_retry_exhausted",partitions={seed, parameter_hash, run_id})
13 envelope_base := { run_id, seed, parameter_hash, manifest_fingerprint,
                      module="1A.ztp_sampler", substream_label="poisson_component" }
14 return PREPARED_CONTEXT(...)
```

This mirrors your expanded draft while keeping S4.1 **draw-free**, binding the **label** and **partitions** once, and leaving $\lambda_{\text{extra},m}=\exp(\eta_m)$ and all attempt logic to S4.2–S4.5.

---

### Cross-references you’ll see downstream

* **S4.2** defines the GLM link and numeric guards (compute $\eta_m$, $\lambda_{\text{extra},m}$; assert finiteness and $>0$).
* **S4.3–S4.5** sample with ZTP via rejection from Poisson(λ) using S0.3.7 regimes, substreams per S0.3.3, and open-interval uniforms S0.3.4; hard cap at 64 zeros; exhaustion policy governed (`abort` vs `downgrade_domestic`).
* **S4.6–S4.8** assert determinism, corridors, and define the state boundary $K_m\in\{1,2,\dots\}$ (accepted) or exhaustion diagnostics (skip S5–S6).

---

# S4.2 — Link function & parameterisation

## 1) Purpose & scope

Map the merchant-level covariates available at the S4 entry to a **strictly positive** Poisson mean $\lambda_{\text{extra},m}$ for the **zero-truncated Poisson** (ZTP) draw of foreign-country count $K_m$. This state performs **no RNG** and **persists nothing**; it deterministically computes $\eta_m$ and $\lambda_{\text{extra},m}$ for use by the S4 sampler. Positivity and numeric finiteness are enforced here; S4.5 uses $\lambda_{\text{extra},m}$ in every `poisson_component` attempt payload.

---

## 2) Inputs (per eligible merchant $m$) & preconditions

**Eligibility & size**

* $e_m = 1$ (merchant passed S3 cross-border gate). If $e_m=0$, S4 must not run; $K_m:=0$ is fixed upstream.
* $N_m \in \{2,3,\dots\}$ is the accepted **total outlet count** from S2; $N_m$ is read-only here. (The $\log N_m$ domain is thus valid.)

**Features**

* $X_m \in [0,1]$ (**openness** scalar) loaded from the **parameter-scoped** `crossborder_features` table (partitioned by `{parameter_hash}`; FK on `merchant_id`). Column name in schema: `openness`.

**Hyperparameters & governance**

* $\theta=(\theta_0,\theta_1,\theta_2)$ read from `crossborder_hyperparams.yaml` (governed artefact with recorded Wald stats/drift gates). The **locked constraint** is $0<\theta_1<1$ (sub-linear elasticity in $\log N$); no hard sign is imposed on $\theta_2$ in the locked spec.

**Numeric environment**

* All arithmetic is IEEE-754 **binary64** (natural log/exponential). S4.2 raises a merchant-scoped numeric policy error if $\lambda_{\text{extra},m}$ is non-finite or $\le 0$.

---

## 3) Canonical definitions (boxed)

### 3.1 Linear predictor (canonical scale)

$$
\boxed{\ \eta_m \;=\; \theta_0 \;+\; \theta_1\,\log N_m \;+\; \theta_2\,X_m,\qquad 0<\theta_1<1\ }\tag{S4.2-A}
$$

### 3.2 Mean map (Poisson mean for ZTP)

$$
\boxed{\ \lambda_{\text{extra},m} \;=\; \exp(\eta_m) \;>\; 0\ }\tag{S4.2-B}
$$

These replace an earlier identity-link draft in order to guarantee positivity; governance metadata for $\theta$ are recorded alongside the hyperparameters.

---

## 4) Numeric guards & error handling (normative)

Evaluate $\eta_m$ and $\lambda_{\text{extra},m}$ in binary64. Then:

* **Guard G1 (finiteness):** If `!isfinite(λ)` → **abort merchant** with `numeric_policy_error`. S4 must emit **no events** for this merchant; validators treat absence as expected given this error.
* **Guard G2 (positivity):** If $\lambda_{\text{extra},m}\le 0$ (theoretically impossible under exp, but defensively checked) → **abort merchant** with `numeric_policy_error`.
* **Governance check (config-time):** If loaded $\theta_1\notin(0,1)$ (or other documented drift violations) → **abort run in CI** (`config_governance_violation`); no merchants proceed.

---

## 5) Interpretation & comparative statics (for implementers and validators)

Let $\lambda=\lambda_{\text{extra},m}$. Then

* **Elasticity w\.r.t. $N$:** $\displaystyle \frac{\partial \log\lambda}{\partial\log N}=\theta_1\in(0,1)$ (sub-linear scaling as merchant size grows).
* **Marginal effect of openness:** $\displaystyle \frac{\partial \lambda}{\partial X}=\theta_2\,\lambda$ (sign/magnitude driven by $\theta_2$; no hard sign constraint in the locked spec).
* **Monotonicity:** $\lambda$ increases in $N$ and (if $\theta_2>0$) in $X$; this informs corridor expectations for acceptance rates $1-e^{-\lambda}$ used later (S4.3/S9).

---

## 6) Contracts with S4 logging & validation (what will be cross-checked later)

S4.5 emits a `poisson_component` row **per attempt** with payload field `lambda` that must equal $\lambda_{\text{extra},m}$ **bit-for-bit** across all attempts for that merchant. The validator recomputes $\eta_m,\lambda_{\text{extra},m}$ from $(N_m,\theta,X_m)$ and asserts **binary64 equality** against every observed `lambda`. Any drift implies state corruption and aborts the run.

---

## 7) Reference algorithm (language-agnostic; no RNG, no emission)

```text
INPUT:
  e_m ∈ {0,1}     # S3; must be 1 to enter S4.2
  N_m ≥ 2         # S2 (accepted outlet count)
  X_m ∈ [0,1]     # from model/crossborder_features (schema: 'openness')
  θ = (θ0, θ1, θ2)# from crossborder_hyperparams.yaml (governed)

OUTPUT:
  (η_m, λ_extra_m)  # scalars for S4.5; not persisted

1  assert e_m == 1
2  assert N_m ≥ 2
3  # Governance sanity (config-time guarantee; asserted here defensively)
4  if not (0.0 < θ1 < 1.0): abort_run("config_governance_violation")
5  # Canonical computations (binary64)
6  η_m ← θ0 + θ1 * log(N_m) + θ2 * X_m
7  λ_extra_m ← exp(η_m)
8  if (not isfinite(λ_extra_m)) or (λ_extra_m ≤ 0.0):
9      abort_merchant("numeric_policy_error")   # S4 emits no RNG events for m
10 return (η_m, λ_extra_m)
```

Notes:

* $X_m$ source and range are governed by `schemas.1A.yaml#/model/crossborder_features`; the dataset dictionary pins its path/partitioning for parameter-scoped reproducibility.
* The **only** downstream dependency of S4.5 on this state is the scalar $\lambda_{\text{extra},m}$, which will be repeated verbatim in all S4 `poisson_component` attempts for that merchant.

---

## 8) Invariants (checked at or implied by S4.2)

* **I-LINK1 (Domain):** $e_m=1$ and $N_m\ge2$ on entry. (Branch-coherence to S3/S2.)
* **I-LINK2 (Schema-sourced feature):** $X_m\in[0,1]$ per `crossborder_features` schema; FK on `merchant_id` holds.
* **I-LINK3 (Governed parameter):** $0<\theta_1<1$ (asserted in governance; defensive check here).
* **I-LINK4 (Numeric):** $\lambda_{\text{extra},m}\in(0,\infty)$ (binary64 finite). Fail → merchant-scoped numeric policy error; **no S4 events** exist for $m$.
* **I-LINK5 (Payload constancy hook):** If any S4 events exist for $m$, every `poisson_component.lambda` equals the recomputed $\lambda_{\text{extra},m}$ **bit-exactly**.

---

## 9) What S4.2 hands to the next sub-state

A pair $(\eta_m,\lambda_{\text{extra},m})$ in memory. S4.3 fixes the ZTP law; S4.5 performs the rejection sampler, emitting auditable `poisson_component`/`ztp_*` event streams with `lambda` set to this exact value.

---

# S4.3 — Target distribution (Zero-Truncated Poisson)

## 1) Purpose (what this sub-state fixes)

This sub-state **pins the law** that S4.5 must sample from and that S9 must validate against. It introduces **no RNG** and **persists nothing**; it defines the pmf/cdf, normaliser, expectations, and retry/acceptance identities that drive corridor tests and event-trace interpretation.

---

## 2) Canonical law on $\{1,2,\dots\}$

Let $Y\sim\mathrm{Poisson}(\lambda)$ with $\lambda\equiv\lambda_{\text{extra},m}>0$ computed in S4.2, and define the **zero-truncated Poisson** as the conditional law:

$$
\boxed{\,K \;=\; Y\ \big|\ (Y\ge 1)\,} \quad\text{with } \lambda>0 \text{ from S4.2.}
$$

**Normaliser and pmf.** With $Z(\lambda)=1-e^{-\lambda}$,

$$
\boxed{\,\Pr[K=k]\;=\;\frac{e^{-\lambda}\lambda^k}{k!\,Z(\lambda)},\quad k=1,2,\dots\,}\tag{ZTP-pmf}
$$

**CDF** (via Poisson CDF $F_Y$):

$$
F_K(k)\;=\;\Pr[K\le k]\;=\;\frac{F_Y(k)-\Pr(Y=0)}{1-\Pr(Y=0)}\;=\;\frac{F_Y(k)-e^{-\lambda}}{1-e^{-\lambda}}\;,\quad k\ge1. \tag{ZTP-cdf}
$$

**Moments** (locked spec):

$$
\boxed{\,\mathbb{E}[K]=\frac{\lambda}{1-e^{-\lambda}},\qquad
\mathrm{Var}(K)=\frac{\lambda+\lambda^2}{1-e^{-\lambda}}-\Big(\frac{\lambda}{1-e^{-\lambda}}\Big)^2\,}. \tag{ZTP-moments}
$$

These exact formulas are the **reference** for S9 corridor checks; they are **not** persisted by S4.

---

## 3) Rejection identity (why we can use Poisson draws)

Realising $K$ by **rejection from Poisson**: draw $Y\sim\mathrm{Poisson}(\lambda)$ and **accept iff** $Y\ge1$. The **per-attempt success probability** is

$$
\boxed{\,p_{\text{acc}} = \Pr(Y\ge 1) = 1 - e^{-\lambda} = Z(\lambda)\,}. \tag{acc}
$$

This identity (a) proves that the S4.5 rejection sampler targets the ZTP exactly, and (b) yields closed-form diagnostics for retry statistics below.

---

## 4) Retry statistics (what validation expects in the logs)

Let $R$ be the number of **zero draws before success** (failures-before-first-success). Under rejection sampling:

$$
\boxed{\,R\sim \mathrm{Geom}\!\left(p_{\text{acc}}\right)\ \text{(failures-before-success)},\quad \Pr(R=r)=(1-p_{\text{acc}})^r p_{\text{acc}},\ r=0,1,2,\dots\,}.
$$

Hence

$$
\mathbb{E}[R]=\frac{1-p_{\text{acc}}}{p_{\text{acc}}}=\frac{e^{-\lambda}}{1-e^{-\lambda}},\qquad
\Pr(R\ge L)= (1-p_{\text{acc}})^L = e^{-L\lambda}.
$$

With the hard cap $L=64$, the **exhaustion probability** is $\Pr(\text{64 zeros})=e^{-64\lambda}$. These close-forms directly support your S9 corridors (e.g., empirical mean rejections $<0.05$, $p_{99.9}<3$ over the cohort), and they are what S9 compares against the **event traces** emitted by S4.5.

---

## 5) Numerically stable forms (binary64, no surprises)

All arithmetic is IEEE-754 **binary64** (per 1A numeric policy). To avoid loss of significance:

* **Normaliser** $Z(\lambda)=1-e^{-\lambda}$: compute as `expm1(-λ)` with a negation, i.e. $Z(\lambda)= -\mathrm{expm1}(-\lambda)$.
* **Log-normaliser** $\log Z(\lambda)$: compute as `log1p(-exp(-λ))`.
* **Log-pmf** for $k\ge1$:

  $$
  \boxed{\,\log \Pr[K=k] = -\lambda + k\log\lambda - \log(k!) - \log Z(\lambda)\,}.
  $$
* **Small-$\lambda$ guard** ($\lambda\ll 1$): use series $Z(\lambda)=\lambda - \tfrac{\lambda^2}{2} + O(\lambda^3)$; then
  $\mathbb{E}[K] \approx 1 + \tfrac{\lambda}{2} + O(\lambda^2)$ and $p_{\text{acc}}\approx \lambda$.
* **Large-$\lambda$ guard** ($\lambda\gtrsim 20$): $Z(\lambda)\to 1$; treat $\log Z(\lambda)\approx 0$ and avoid subtractive cancellation via the `log1p` path above.

These rules are **for implementers and validators**; S4.3 itself emits nothing. The sampler in S4.5 still uses **Poisson attempts** and does **not** need the ZTP log-pmf explicitly.

---

## 6) Contracts that bind S4.5/S9 to this law

* **Sampler correctness.** S4.5 **must** implement the acceptance set $\{Y\ge1\}$ with per-attempt acceptance $p_{\text{acc}}=1-e^{-\lambda}$; accepted value is $K=Y$. Any deviation would break the ZTP target. (Your locked state text already mandates rejection from Poisson with hard cap 64.)
* **Trace ↔ theory link.** In S4.5 logs:
  – The count of `ztp_rejection` rows for merchant $m$ equals the realised $R$.
  – The attempt where a `poisson_component` has `k≥1` equals $R{+}1$ and yields $K_m$.
  S9 reads these and compares their cohort distribution to the Geometric predictions implied by $p_{\text{acc}}(m)$.
* **Corridor hooks.** Your design cites run-level corridors on mean and upper quantiles of $R$; these are evaluated against the `ztp_*` event streams partitioned by `{seed, parameter_hash, run_id}` as defined in the dataset dictionary.

---

## 7) Invariants (no RNG consumed here; validator math)

* **I-ZTP-LAW1 (domain):** $\lambda>0$ finite (from S4.2) is a **precondition** for using this law. If violated, S4.5 must not run and the merchant is aborted under numeric policy.
* **I-ZTP-LAW2 (equivalence):** The distribution of accepted `poisson_component.k` (conditional on `k≥1`) across merchants equals the ZTP pmf above; the observed rejection counts equal $R\sim \mathrm{Geom}(1-e^{-\lambda})$. (Checked by S9 using logs.)
* **I-ZTP-LAW3 (exhaustion math):** The observed share of merchants with `ztp_retry_exhausted` should match $e^{-64\lambda}$ when bucketed by similar $\lambda$; large deviations trigger CI alerts.

---

## 8) What S4.3 hands forward

A **pure mathematical contract** consisting of (ZTP-pmf), (ZTP-cdf), (ZTP-moments), and (acc) that S4.5 must realise via rejection and that S9 uses for analytical checks against the event streams registered in the dataset dictionary (`poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`). No rows are written by S4.3 itself.

---

Great nudge — I kept everything you liked and drilled deeper into the math where it actually buys clarity. This is an **addendum to S4.3 (Target distribution)**, so S4.1/4.2 remain exactly as locked.

## S4.3 — Math drill (zero-truncated Poisson)

### 1) Definition recap (anchor)

Let $Y\sim\text{Poisson}(\lambda)$ with $\lambda\equiv \lambda_{\text{extra},m}>0$ from S4.2, and define $K=Y\mid(Y\ge1)$. Then, with $Z(\lambda)=1-e^{-\lambda}$,

$$
\Pr[K=k]=\frac{e^{-\lambda}\lambda^k}{k!\,Z(\lambda)},\quad k=1,2,\dots,
$$

$$
\mathbb{E}[K]=\frac{\lambda}{Z(\lambda)},\qquad
\mathrm{Var}(K)=\frac{\lambda+\lambda^2}{Z(\lambda)}-\Big(\frac{\lambda}{Z(\lambda)}\Big)^2,\quad Z(\lambda)=1-e^{-\lambda}.
$$

(These are the laws S4 targets and S9 validates.)

---

### 2) Normalisation, CDF and stable numerics

**Normaliser.** $Z(\lambda)=\Pr(Y\ge1)=1-\Pr(Y=0)=1-e^{-\lambda}$. Use the **stable** form $Z(\lambda)=-\mathrm{expm1}(-\lambda)$ in binary64.

**CDF.** With $F_Y(k;\lambda)=\Pr(Y\le k)=e^{-\lambda}\sum_{j=0}^k\lambda^j/j!$ (equivalently $F_Y(k)=\gamma(k{+}1,\lambda)/k!$), the ZTP CDF is

$$
F_K(k)=\frac{F_Y(k;\lambda)-e^{-\lambda}}{Z(\lambda)},\quad k\ge1.
$$

For stable evaluation use `log1p`/`expm1` or regularized gamma routines (no custom series needed).

**Log-pmf (for exact audit and corridor math).**

$$
\log \Pr[K=k]=-\lambda+k\log\lambda-\log(k!) - \log Z(\lambda),\quad k\ge1,
$$

with $\log(k!)=\log\Gamma(k{+}1)$ via `lgamma`.

**Ratio / recurrence (fast & exact).**

$$
\frac{\Pr[K=k{+}1]}{\Pr[K=k]}=\frac{\lambda}{k{+}1}\quad(\text{same as Poisson; normaliser cancels}).
$$

This is the numerically safest way to step pmf values across $k$.

---

### 3) Rejection sampler identities (what the logs imply)

S4.5 samples $Y\sim\text{Poisson}(\lambda)$ and **accepts iff** $Y\ge1$. The per-attempt success probability is

$$
p_{\text{acc}}=\Pr(Y\ge1)=Z(\lambda)=1-e^{-\lambda}.
$$

Let $R$ be the number of zeros **before** success. Then $R\sim \text{Geom}(p_{\text{acc}})$ (failures-before-success):

$$
\mathbb{E}[R]=\frac{1-p_{\text{acc}}}{p_{\text{acc}}}=\frac{e^{-\lambda}}{1-e^{-\lambda}},\qquad
\Pr(R\ge L)=e^{-L\lambda}.
$$

With the hard cap $L=64$, $\Pr(\texttt{retry_exhausted})=e^{-64\lambda}$. These equalities are **exact** and are what S9 checks against the `ztp_*` traces (mean, high-quantile, and exhaustion-rate corridors).

**Quantiles of rejections (closed-form).** For $q\in(0,1)$,

$$
Q_R(q)=\min\big\{r\in\mathbb{Z}_{\ge0}\!:\ 1-e^{-(r+1)\lambda}\ge q\big\}
=\Big\lceil \frac{\log\!\big(\tfrac{1}{1-q}\big)}{\lambda}-1\Big\rceil.
$$

S9 can compare empirical $Q_{0.99},Q_{0.999}$ to these predictions per $\lambda$-bucket.

---

### 4) PGF/MGF and moment derivations (audit-ready)

**PGF of ZTP.** For $|s|\le1$,

$$
G_K(s)=\mathbb{E}[s^K]=\frac{\mathbb{E}[s^Y]-\Pr(Y=0)}{Z(\lambda)}
=\frac{e^{\lambda(s-1)}-e^{-\lambda}}{1-e^{-\lambda}}.
$$

**MGF.** $M_K(t)=G_K(e^t)=\dfrac{\exp\!\big(\lambda(e^t-1)\big)-e^{-\lambda}}{1-e^{-\lambda}}$ (finite $\forall t\in\mathbb{R}$).
Differentiate $G_K$ at $s=1$ to recover moments used in S9:

$$
G_K'(1)=\frac{\lambda}{Z(\lambda)}=\mathbb{E}[K],\qquad
G_K''(1)+G_K'(1)-\big(G_K'(1)\big)^2=\mathrm{Var}(K).
$$

These derivations match the locked formulas and provide an **independent validator path** (no reliance on Poisson tables).

---

### 5) Sensitivities (for gradient checks and corridor design)

**Derivatives w\.r.t. $\lambda$.** For any observed $k\ge1$,

$$
\ell(\lambda;k)=\log \Pr[K=k]=-\lambda+k\log\lambda-\log(k!) - \log Z(\lambda).
$$

Score and curvature:

$$
\frac{\partial \ell}{\partial\lambda}=-1+\frac{k}{\lambda}-\frac{e^{-\lambda}}{Z(\lambda)},\qquad
\frac{\partial^2 \ell}{\partial\lambda^2}=-\frac{k}{\lambda^2}+\frac{e^{-\lambda}}{Z(\lambda)^2}.
$$

These are useful for **unit tests** (finite-diff vs analytic) even though S4 does not fit $\lambda$.

**Monotonicity.** $p_{\text{acc}}(\lambda)=1-e^{-\lambda}$ and $\mathbb{E}[R]=e^{-\lambda}/Z(\lambda)$ are strictly **increasing** and **decreasing** in $\lambda$, respectively. This underpins the **direction** of S9’s corridor breaches.

---

### 6) Asymptotics (guides numeric thresholds)

* **Small $\lambda\ll1$:** $Z(\lambda)=\lambda-\tfrac{\lambda^2}{2}+O(\lambda^3)$. Hence

  $$
  p_{\text{acc}}\approx \lambda,\qquad \mathbb{E}[K]\approx 1+\frac{\lambda}{2},\qquad \mathbb{E}[R]\approx \frac{1}{\lambda}-1.
  $$

  Expect many rejections; `ztp_retry_exhausted` risk is material if $\lambda\lesssim 0.05$.
* **Large $\lambda\gtrsim 20$:** $Z(\lambda)\to 1$, so ZTP $\approx$ Poisson; $\mathbb{E}[K]\approx\lambda$, $\Pr(\text{exhaust})\approx e^{-64\lambda}$ is astronomically small.

These guide sensible **alerting thresholds** for the validation bundle (e.g., bucket $\lambda<0.1$ for special attention).

---

### 7) Cohort-level expectations (how S9 aggregates)

Given merchant-specific $\lambda_m$, the cohort means are **simple averages**:

$$
\mathbb{E}_{\text{cohort}}[R]=\frac{1}{M}\sum_m \frac{e^{-\lambda_m}}{1-e^{-\lambda_m}},\qquad
\mathbb{E}_{\text{cohort}}[K]=\frac{1}{M}\sum_m \frac{\lambda_m}{1-e^{-\lambda_m}}.
$$

In practice, S9 bins merchants by $\lambda$ (or by features $(N,X)$) and checks each bin’s empirical rejections $r$ and acceptance quantiles against the formulas above. (Those bins come straight from the **S4 event streams** and the dictionary’s partitions `{seed, parameter_hash, run_id}`.)

---

### 8) Numerics crib (exactly what to code/use)

* Use **binary64** throughout; `expm1`/`log1p` for $Z(\lambda)$ and $\log Z(\lambda)$.
* Use `lgamma(k+1)` for $\log(k!)$, and the **pmf ratio** $\lambda/(k{+}1)$ to avoid overflow when stepping pmf.
* For CDFs, prefer the **regularized gamma** routines instead of partial sums; or compute Poisson CDF then transform via $F_K$.
* For high-$k$ tail checks, bound with **Chernoff** on Poisson and then renormalise by $Z(\lambda)$ if needed (not strictly required for S4, useful in S9 for guardrails).
* **No RNG** is consumed in S4.3; these formulas drive S4.5 implementation and S9 validation.

---

### 9) What stays exactly as before

* The **accept/reject loop** and the **64-attempt cap** remain unchanged; this section only furnishes the math S4.5 and S9 rely on.
* The **event schema & partitions** live in the dataset dictionary and S4.4; nothing here adds or removes persisted artefacts.

---

# S4.4 — RNG protocol & event schemas

## 1) Substream & context (namespacing)

* **Substream label (required):**
  Every Poisson attempt in S4 uses the substream label

  $$
  \boxed{\ \texttt{substream_label} \equiv \text{"poisson_component"}\ }
  $$

  with **`context="ztp"`** to disambiguate from S2’s NB usage of the same stream. The keyed mapping from **S0.3.3** is used to derive Philox state; validators prove replay using the envelope’s pre/post counters (below).

* **Module tag (envelope field):**
  For S4 emissions, `module` **must** identify this sampler; use `"1A.ztp_sampler"`. (This is carried in the envelope; the dataset dictionary’s lineage metadata for the stream id may be broader because the stream is shared across subsegments.)

* **Uniform primitive:**
  All Poisson draws consume only iid **open-interval** uniforms $u\in(0,1)$ from the keyed substream (per S0.3).

---

## 2) Shared RNG envelope (must appear on **every** event row)

All S4 RNG JSONL events carry the **RNG envelope** fields:

```
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
  module, substream_label,
  rng_counter_before_lo, rng_counter_before_hi,
  rng_counter_after_lo,  rng_counter_after_hi,
  merchant_id, ...payload }
```

**Semantics & types (normative):**

* `ts_utc`: emission timestamp in UTC (RFC3339 with `Z`).
* `run_id`: run-scoped identifier per S0.2.4; used only to version logs/partitions.
* `seed`: 64-bit unsigned integer (master run seed) carried verbatim.
* `parameter_hash`: 64-hex string; partitions parameter-scoped inputs/outputs.
* `manifest_fingerprint`: 64-hex string; versions egress/validation and is embedded in rows.
* `module`: string; **must** be `"1A.ztp_sampler"` for S4 events.
* `substream_label`: string; **must** be `"poisson_component"` in S4.
* `rng_counter_before_lo/hi`, `rng_counter_after_lo/hi`: unsigned 64-bit words comprising the Philox **128-bit** counter immediately before / after the RNG consumption for this event. (Validators compare lexicographically on `(hi, lo)`.)
* `merchant_id`: FK to ingress universe.

**Draw-accounting contract (hard rules):**

* **Draw events:** `poisson_component` **must** advance the counter (`after > before`) and the sequence of `before` counters across attempts must be **strictly increasing**.
* **Diagnostics:** `ztp_rejection` and `ztp_retry_exhausted` are **non-consuming** (they do not draw RNG); set `after == before`. These rows exist to make rejection counts and the 64-cap auditable without affecting the RNG stream.

Any envelope or counter violation is a **run-scoped schema/lineage failure**.

---

## 3) Authoritative event streams (paths, partitions, schema refs)

All three S4 streams are **logs** with the same partitions `{seed, parameter_hash, run_id}` and fixed paths pinned in the dataset dictionary:

1. **Poisson attempts** (draws; consuming)
   Path: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   `schema_ref: schemas.layer1.yaml#/rng/events/poisson_component`
   `lineage.produced_by: "1A.nb_poisson_component"` (stream id is shared; S4 rows are distinguished by `context="ztp"`).

2. **ZTP rejections** (diagnostics; non-consuming)
   Path: `logs/rng/events/ztp_rejection/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   `schema_ref: schemas.layer1.yaml#/rng/events/ztp_rejection`
   `lineage.produced_by: "1A.ztp_sampler"`.

3. **ZTP retry exhausted** (cap reached; non-consuming)
   Path: `logs/rng/events/ztp_retry_exhausted/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   `schema_ref: schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`
   `lineage.produced_by: "1A.ztp_sampler"`.

(The **RNG core** logs `rng_audit_log`/`rng_trace_log` are separate; see dictionary for their paths and schema refs.)

---

## 4) Event payloads (fields, types, domains, constraints)

Below, all rows also include the **RNG envelope** (§2). All numeric math is binary64; equality checks use **bit-equality** against recomputed values.

### 4.1 `poisson_component` (attempt rows; consuming)

**Required payload fields:**

* `merchant_id`: string / integer (project-wide id type), FK.
* `context`: string; **must** equal `"ztp"` for S4 (S2 uses `"nb"`).
* `lambda`: IEEE-754 binary64; **strictly positive**; **must** equal the $\lambda_{\text{extra},m}$ computed in S4.2 for this merchant, **bit-for-bit**, across every attempt.
* `k`: integer $\in\{0,1,2,\dots\}$; the raw **untruncated** Poisson draw for this attempt.
* `attempt`: integer $\in\{1,2,\dots\}$; **strictly increasing** per merchant, equals the draw index in the ZTP loop.

**Counter rule:** `after > before` (consuming). (Envelope deltas may vary by attempt depending on the Poisson regime used; that’s expected and is the point of the envelope.)

### 4.2 `ztp_rejection` (zero attempts; non-consuming)

**Required payload fields:**

* `merchant_id` (FK).
* `lambda_extra`: IEEE-754 binary64; **strictly positive**; **must** equal $\lambda_{\text{extra},m}$ for this merchant **bit-for-bit**.
* `k`: integer; **must equal** `0` on this stream.
* `attempt`: integer $\in\{1,\dots,64\}$; **strictly increasing** per merchant.

**Counter rule:** `after == before` (non-consuming).

### 4.3 `ztp_retry_exhausted` (cap reached; non-consuming)

**Required payload fields:**

* `merchant_id` (FK).
* `lambda_extra`: IEEE-754 binary64; **strictly positive**; **bit-equal** to $\lambda_{\text{extra},m}$.
* `attempts`: integer; **must equal** `64`.
* `aborted`: boolean; **must** be `true`.

**Cardinality:** at most **one** row per merchant; present **iff** 64 consecutive zero draws occurred.
**Counter rule:** `after == before` (non-consuming).

> **Note on field names.** The locked S4 text uses `lambda` in `poisson_component` and `lambda_extra` in the ZTP diagnostics; this spec keeps that naming for compatibility.

---

## 5) Presence/absence & cardinality rules (per merchant)

* **If eligible (`e_m=1`):**
  A finite sequence of `poisson_component` attempts with constant `lambda` exists, ending either:
  (a) **Accepted** — first row with `k ≥ 1` (then **stop**; **no** `ztp_retry_exhausted`), with **zero or more** prior `ztp_rejection` rows whose `attempt` enumerate 1..R; or
  (b) **Exhausted** — **exactly 64** `poisson_component` rows with `k=0`, **exactly 64** `ztp_rejection` rows (`attempt=1..64`), and **exactly one** `ztp_retry_exhausted` row. Missing/extra rows are structural errors.

* **If ineligible (`e_m=0`):**
  **No S4 events of any type** may exist (branch-coherence). Presence is a run-stopping validation failure.

---

## 6) Partitions, ordering, idempotency

* **Partitions:** All three streams **must** be partitioned by `{seed, parameter_hash, run_id}` exactly as pinned in the dataset dictionary (paths in §3). The partition keys are mandatory and validated.
* **File ordering:** No ordering is guaranteed within/among files. Consumers **must** use the `attempt` field and per-merchant grouping to reconstruct order.
* **Idempotency / exactly-once at sink:**
  Upserts are idempotent on the following natural keys:

  * `poisson_component`: `(merchant_id, attempt, context="ztp")`
  * `ztp_rejection`: `(merchant_id, attempt)`
  * `ztp_retry_exhausted`: `(merchant_id)`
    Duplicate rows after keying are schema violations (run-scoped).

---

## 7) What validators assert from this protocol

* **I-ZTP1 (bit-replay):** With fixed $(N_m, X_m, \theta, \texttt{seed}, \texttt{parameter_hash}, \texttt{manifest_fingerprint})$, the attempt sequence and accepted $K_m$ are bit-reproducible; envelope counters and payload `lambda`/`lambda_extra` **exactly match** recomputed values.
* **I-ZTP2 (coverage):** Accepted merchants have ≥1 `poisson_component` and 0..R `ztp_rejection`; exhausted merchants have the exact **64/64/1** signature; ineligible have **no S4 events**.
* **I-ZTP3 (indexing):** `attempt` strictly increases from 1; `ztp_retry_exhausted.attempts == 64`.
* **I-ZTP4 (schema & counters):** Envelope present; `context="ztp"` for S4 draws; `lambda>0`; **draws advance counters**; diagnostics **don’t**.

---

## 8) Failure taxonomy (scope → action)

* **Schema/lineage violations** (missing envelope fields; wrong partitions; `context!="ztp"`; counter rules broken): **abort run** (CI stops).
* **Numeric policy errors** (non-finite/≤0 `lambda` already caught in S4.2): merchant-scoped abort; **no S4 events**.
* **Branch incoherence** (any S4 event when `e_m=0`): **abort run** (contradicts S3).

---

# S4.5 — Sampling algorithm (ZTP via rejection from Poisson), deterministic & auditable

## 1) Purpose

For each **eligible** merchant $m$ (i.e., $e_m=1$), produce a **single** foreign-country count $K_m\in\{1,2,\dots\}$ by rejection sampling from $Y\sim\mathrm{Poisson}(\lambda_{\text{extra},m})$ with **truncation at 0**, while emitting an auditable attempt trace to the three S4 event streams with the **RNG envelope** and partitions pinned in the dictionary.

---

## 2) Preconditions & inputs (per eligible merchant $m$)

* **Eligibility & size:** $e_m=1$ (from S3), $N_m\ge2$ (from S2). Ineligible merchants **must not** emit S4 events.
* **Mean:** $\lambda\equiv\lambda_{\text{extra},m}=\exp(\theta_0+\theta_1\log N_m+\theta_2 X_m)$, computed in S4.2, **binary64 finite & $>0$** (or merchant is aborted in S4.2 with **no** S4 events).
* **RNG lane & protocol:** substream label `"poisson_component"`, `context="ztp"`, open-interval $u\in(0,1)$; every attempt records **rng_counter_before/after**; diagnostics **do not** advance counters.
* **Streams & partitions:**
  `logs/rng/events/poisson_component/...`,
  `logs/rng/events/ztp_rejection/...`,
  `logs/rng/events/ztp_retry_exhausted/...`, all partitioned by `{seed, parameter_hash, run_id}` with schema refs in `schemas.layer1.yaml`.

---

## 3) Target & acceptance identity (recap for correctness)

We target $K=Y\mid(Y\ge1)$ where $Y\sim\mathrm{Poisson}(\lambda)$; per-attempt acceptance probability is $p_{\text{acc}}=1-e^{-\lambda}$. The number of zero draws before success $R$ is $\mathrm{Geom}(p_{\text{acc}})$ (failures-before-success). These equalities are **what the S9 corridors test** against the emitted attempt traces.

---

## 4) The attempt loop (normative)

**Index & cap.** Let the attempt index $a$ run from 1 up to a **hard cap** of 64. On acceptance ($k\ge1$), the loop stops immediately; if 64 consecutive zeros occur, the loop emits an exhaustion record and continues to the configured policy.

**Per attempt $a$:**

1. **Draw a Poisson deviate (consuming).** Generate a single **untruncated** $k_a\in\{0,1,2,\dots\}\sim\mathrm{Poisson}(\lambda)$ using the project’s Poisson regimes (cf. S0.3.7), with open-interval uniforms from the keyed substream. Snapshot counters **before** and **after** the sampler; emit:
   `poisson_component{ merchant_id=m, context="ztp", lambda=λ, k=k_a, attempt=a, envelope: before, after }`.
   – `lambda` **must** be the S4.2 value for $m$, **bit-identical across all attempts**.
   – **Draw accounting:** `after > before`.

2. **If $k_a=0$ (reject):** emit the diagnostic (non-consuming) row
   `ztp_rejection{ merchant_id=m, lambda_extra=λ, k=0, attempt=a, envelope: before=after, after=after }`,
   then **continue** with $a\leftarrow a+1$. **Counters must not advance.**

3. **If $k_a\ge1$ (accept):** set $K_m\leftarrow k_a$ and **stop** the loop.

4. **If $a=64$ and still $k_a=0$ (exhaustion):** emit exactly one non-consuming row
   `ztp_retry_exhausted{ merchant_id=m, lambda_extra=λ, attempts=64, aborted=true, envelope: before=after, after=after }`,
   then follow the **exhaustion policy** (§5).

All fields, partitions, and schema paths are fixed by the dictionary; any deviation is a **run-scoped schema/lineage failure**.

---

## 5) Exhaustion policy (governed)

Let `ztp_on_exhaustion_policy ∈ {"abort","downgrade_domestic"}` in `crossborder_hyperparams.yaml` (default `"abort"`):

* `"abort"`: **abort merchant** — no S5/S6/S7 artefacts for $m$.
* `"downgrade_domestic"`: set $K_m:=0$, **skip S5–S6**, and proceed to S7 with $\mathcal{C}_m=\{\text{home}\}$; record reason `"ztp_exhausted"` in validation bundle.

In both cases the **`ztp_retry_exhausted`** diagnostic must be present (non-consuming).

---

## 6) What gets emitted (cardinalities & coverage)

If accepted at attempt $a$ with $K_m=k\ge1$:

* Exactly **$a$** rows in `poisson_component` (attempts 1…$a$), constant `lambda=λ`, `context="ztp"`.
* Exactly **$a{-}1$** rows in `ztp_rejection` (attempts 1…$a{-}1$).
* **No** `ztp_retry_exhausted`.

If exhausted:

* Exactly **64** rows in `poisson_component` with `k=0`.
* Exactly **64** rows in `ztp_rejection` (attempts 1…64).
* Exactly **one** `ztp_retry_exhausted` row.

If ineligible $e_m=0$: **no S4 events of any type**. Presence is a branch-coherence failure.

---

## 7) Envelope & counter discipline (must-hold)

* Every `poisson_component` row **advances** counters; `ztp_rejection` and `ztp_retry_exhausted` **do not** (set `after==before`).
* `attempt` is **1-based** and strictly increasing per merchant; if attempt 64 occurs with `k=0`, `ztp_retry_exhausted.attempts==64` **must** exist.
* `context=="ztp"` in S4; **never** `"nb"` here.
* For a fixed merchant, all attempts carry an **identical** binary64 `lambda` equal to the recomputed S4.2 value.

---

## 8) Idempotency & natural keys at the sink

* `poisson_component`: natural key `(merchant_id, attempt, context="ztp")`.
* `ztp_rejection`: `(merchant_id, attempt)`.
* `ztp_retry_exhausted`: `(merchant_id)`.
  Duplicate keys → schema violation (run-scoped). Paths/partitions must match the dictionary exactly.

---

## 9) Validator hooks (what S9 will prove off these logs)

* **Bit-replay (I-ZTP1).** Recompute $\lambda$ from S4.2 inputs and re-run the Poisson sampler; assert exact equality of: attempt count; each `k`; every `{before,after}`; and accepted $K_m$ or exhaustion outcome.
* **Coverage & indexing (I-ZTP2/3).** Cardinalities and attempt indexing follow §6/§7 (including the 64/64/1 exhaustion signature).
* **Schema & counters (I-ZTP4).** Envelope present; `context="ztp"`; `lambda>0` bit-constant; **draws consume**, diagnostics **don’t**.
* **Corridors (I-ZTP5).** Using the cohort $p_{\text{acc}}(m)=1-e^{-\lambda_m}$, compare empirical mean rejections and high quantiles to the geometric predictions; CI aborts on breach.

---

## 10) Minimal reference pseudocode (code-agnostic; matches schemas)

```text
INPUT:
  eligible merchant m (e_m = 1)
  λ = λ_extra,m > 0  # from S4.2, binary64 finite
  substream_label = "poisson_component"
  envelope base: {seed, parameter_hash, manifest_fingerprint, run_id, module="1A.ztp_sampler"}

OUTPUT:
  either: accepted K_m ≥ 1 with a finite attempt trace; or merchant abort after 64 zeros per policy

a ← 1
repeat:
    # Attempt: draw Poisson(λ) using open-interval uniforms u∈(0,1)
    before ← snapshot_counter()
    k ← draw_poisson(λ)         # S0.3.7 regimes; iid u01 only
    after  ← snapshot_counter()

    emit poisson_component{merchant_id=m, context="ztp", lambda=λ, k=k, attempt=a,
                           envelope: before, after, substream_label}

    if k = 0 then
        # Diagnostic, non-consuming
        emit ztp_rejection{merchant_id=m, lambda_extra=λ, k=0, attempt=a,
                           envelope: before=after, after=after}
        if a = 64 then
            emit ztp_retry_exhausted{merchant_id=m, lambda_extra=λ, attempts=64, aborted=true,
                                     envelope: before=after, after=after}
            apply exhaustion policy (abort | downgrade_domestic)
            STOP
        else
            a ← a + 1
            continue
    else
        K_m ← k
        STOP
```

This is exactly the **formal** S4.5 in your locked state and combined flow, with the RNG/event contracts already pinned.

---

## 11) Complexity & performance notes (for implementers)

* **Expected attempts** per merchant: $1+\mathbb{E}[R]=1+\dfrac{e^{-\lambda}}{1-e^{-\lambda}}$. For $\lambda\gtrsim 0.5$, acceptance is fast; for $\lambda\ll1$, expect retries and occasionally the 64-cap.
* **I/O:** at most 129 rows per exhausted merchant (64 draws + 64 rejections + 1 exhausted); one JSONL write per attempt; all partitioned by `{seed, parameter_hash, run_id}`.

---

## 12) State outputs / hand-off

* **Accepted path:** deliver in-memory scalar $K_m\ge1$ to S5/S6 (no persisted dataset from S4 besides logs).
* **Exhausted path:** emit `ztp_retry_exhausted` and follow policy (abort or `K_m:=0` & skip S5–S6, go to S7 with home-only set).

Everything above stays within your **locked S4 text** and **dataset dictionary**: same streams, same partitions, same RNG envelope, with precise acceptance/rejection semantics and governed exhaustion handling.

---

# S4.6 — Determinism & correctness invariants

## 1) Purpose & scope

S4.6 asserts the **truth conditions** for ZTP sampling and its logs. It (a) defines determinism and schema/lineage invariants over the three S4 event streams, (b) pins per-merchant **coverage/cardinality** rules, (c) specifies **bit-replay** checks, (d) defines **corridor** tests (population diagnostics), and (e) maps each violation to **merchant-scoped** or **run-scoped** failure classes with deterministic `err_code`s.

**Authoritative inputs used by the validator**

* Event streams (partitioned by `{seed, parameter_hash, run_id}`):
  `logs/rng/events/poisson_component/...` (S4 uses `context="ztp"`),
  `logs/rng/events/ztp_rejection/...`,
  `logs/rng/events/ztp_retry_exhausted/...`. Each row has the **RNG envelope** and event payloads pinned in the dataset dictionary.
* Per-merchant deterministic inputs: $N_m$ (from S2), $X_m$ openness (from `crossborder_features`), and $\theta$ (from `crossborder_hyperparams.yaml`) to recompute $\lambda_{\text{extra},m}$.
* S3 eligibility $e_m$. Ineligible merchants **must** have **no S4 events**.

**Locked invariants referenced**

* I-ZTP1…5 as captured in the **locked S4** and combined state-flow.

---

## 2) Per-merchant reconstruction & symbol table (validator perspective)

For each merchant $m$ with $e_m\in\{0,1\}$:

* Read S3’s $e_m$. If $e_m=0$, assert **no** S4 rows exist for $m$ (branch coherence), and **skip** the rest (not an error).
* If $e_m=1$, fetch:

  * $N_m\ge2$ from S2; $X_m\in[0,1]$; $\theta=(\theta_0,\theta_1,\theta_2)$. Compute

    $$
    \eta_m=\theta_0+\theta_1\log N_m+\theta_2 X_m,\qquad
    \lambda_m\equiv\lambda_{\text{extra},m}=\exp(\eta_m) \in (0,\infty).
    $$

    If $\lambda_m$ is non-finite or $\le0$, this merchant should have been **aborted earlier** (S4.2); **presence** of S4 rows here is a run-stopping numeric-policy violation.
  * Group S4 rows for $m$ into:

    * $P=${`poisson_component` rows with `context="ztp"`}, ordered by `attempt` (strictly 1..).
    * $R=${`ztp_rejection` rows}, ordered by `attempt` (strictly 1..).
    * $X=${`ztp_retry_exhausted` row} (0 or 1).
      All are loaded from dictionary-pinned paths and partitions `{seed, parameter_hash, run_id}`.

---

## 3) Determinism & schema/lineage invariants (must-hold)

### I-ZTP1 — **Bit-replay determinism** (per merchant)

With fixed inputs $(N_m, X_m, \theta)$ and lineage $(\texttt{seed}, \texttt{parameter_hash}, \texttt{manifest_fingerprint})$, the **attempt sequence** and accepted value are **bit-identical** across runs. Concretely:

* The per-attempt payload `lambda` in **every** `poisson_component` row equals the recomputed $\lambda_m$ **bit-for-bit** (binary64).
* The sequence of `k` values in `poisson_component` equals the engine’s Poisson draws (replay uses the Philox substream `"poisson_component"` and the envelope counters for audit).
* If a success occurs at attempt $a^*$, then $K_m=k_{a^*}\ge1$; otherwise the exhaustion signature (below) holds.

**Validator proof sketch:** Recompute $\lambda_m$. Confirm **constancy** of `lambda` across $P$. Re-run the Poisson sampler using the project’s RNG lane and assert equality of each `k`. Envelope `{before,after}` counters must strictly advance on draws (no shape is assumed, only **monotone consumption**).

### I-ZTP2 — **Event coverage & acceptance/exhaustion signature**

Exactly one of the following must hold:

* **Accepted:** $|P|\ge1$, the **last** row in $P$ has `k≥1`, all prior $P$ rows have `k=0`, and $R$ has **exactly** `attempt=1..(|P|-1)` rows. No `ztp_retry_exhausted`.
* **Exhausted:** $|P|=64$ and **all** `k=0`, $|R|=64$ with `attempt=1..64`, and (|X|=1`with`attempts=64\`. Merchant is aborted (or downgraded per policy) downstream. Missing/extra rows is a structural error.

### I-ZTP3 — **Attempt indexing discipline**

* In $R$, `attempt` is **strictly increasing from 1** and $\le64$.
* If $|X|=1$, then `X.attempts == 64`.

### I-ZTP4 — **Schema, lineage & counter conformance**

* Every row in $P\cup R\cup X$ has the **RNG envelope**: `{ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_*, rng_counter_after_*, merchant_id}`.
* `poisson_component.context == "ztp"` (never `"nb"` in S4).
* **Counters advance** on draws: for each row in $P$, `after > before` and the sequence of `before` is **strictly increasing** per merchant; **diagnostics do not** consume RNG: for $R\cup X$, `after == before`.
* Paths & partitions **exactly** equal the dictionary entries for each stream (no alternate layouts).

### I-ZTP6 — **Branch coherence** (cross-state invariant)

If $e_m=0$ then **no** S4 events of any kind may exist for $m$. Presence is a run-stopping failure. (This mirrors S3’s I-EL3.)

### I-ZTP7 — **Idempotency keys**

No duplicate natural keys may exist at the sink:

* `poisson_component`: unique `(merchant_id, attempt, context="ztp")`;
* `ztp_rejection`: unique `(merchant_id, attempt)`;
* `ztp_retry_exhausted`: unique `(merchant_id)`.
  Duplicates are schema violations. (The dictionary pins partitions; the keys ensure **exactly-once** semantics.)

---

## 4) Population diagnostics (corridor tests) — what S9 must compute

Let $p_{\text{acc}}(m)=1-e^{-\lambda_m}$. Under the rejection identity (S4.3), the number of **zero draws before success** $R_m$ is $\mathrm{Geom}(p_{\text{acc}}(m))$ (failures-before-success). From the logs, $R_m=|R|$ on acceptance, or $R_m=64$ on exhaustion. Compute:

* **Mean rejections (cohort):**
  $\displaystyle \bar{R}=\frac{1}{M}\sum_{m\in\mathcal{M}}\!R_m$, and compare to $\frac{1}{M}\sum_m \frac{e^{-\lambda_m}}{1-e^{-\lambda_m}}$. Gate: $\bar{R}<0.05$.
* **Upper quantile corridor:** empirical $p_{99.9}(R)$ $<3$ (or governed value).
* **Exhaustion rate:** among eligible merchants, empirical rate of `ztp_retry_exhausted` in a $\lambda$-bucket $B$ matches $e^{-64\lambda}$ at bucket mean (or better, per-merchant average of $e^{-64\lambda_m}$).

Breaches are **run-scoped** corridor failures (deterministic error). Thresholds live in governed validation config; S4.6 references them as **I-ZTP5**.

---

## 5) Formal validator procedure (reference)

For each `{seed, parameter_hash, run_id}` partition:

1. **Branch coherence.** For every $m$ with $e_m=0$, assert $P=R=X=\varnothing$. If not, `ABORT_RUN("E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS")`.
2. **Recompute $\lambda_m$.** For $e_m=1$, compute $\lambda_m$. If non-finite or $\le0$, assert **no S4 rows exist**; otherwise `ABORT_RUN("E/1A/S4/NUMERIC/INCONSISTENT_ABORT")`.
3. **Schema & envelope.** Check every row has the envelope; check partitions match dictionary; check `poisson_component.context=="ztp"`. Else `ABORT_RUN("E/1A/S4/SCHEMA/...")`.
4. **Lambda constancy.** In $P$, all `lambda` fields equal $\lambda_m$ **bit-exactly**; in $R\cup X$, `lambda_extra` equals $\lambda_m$. Else `ABORT_RUN("E/1A/S4/PAYLOAD/LAMBDA_DRIFT")`.
5. **Counters.** For each $p\in P$: `after > before`; `before` strictly increases with `attempt`. For $r\in R$ and $X$: `after == before`. Else `ABORT_RUN("E/1A/S4/COUNTER/VIOLATION")`.
6. **Coverage/signature.**

   * If $|X|=1$: assert $|P|=|R|=64$, all $P.k=0$, `X.attempts==64`; then **merchant-scoped abort** (or downgrade per policy).
   * Else: assert $|P|\ge1$, last `k≥1`, all prior $P.k=0$, and $R$ attempts are exactly `1..(|P|-1)`. Else `ABORT_RUN("E/1A/S4/COVERAGE/...")`.
7. **Bit-replay (optional heavy check).** Re-draw Poisson(λ) along the S4 lane to reproduce `k`. Mismatches imply hidden nondeterminism → `ABORT_RUN("E/1A/S4/REPLAY/MISMATCH")`.
8. **Corridor tests.** Compute cohort metrics from §4; compare with governed thresholds; on breach, `ABORT_RUN("E/1A/S4/CORRIDOR/…")`.

---

## 6) Failure taxonomy (deterministic `err_code` → scope → action)

* **RUN-scoped (stop the run):**
  Schema/partition violations; missing envelope fields; wrong `context`; counter discipline broken; lambda drift vs recompute; coverage signature inconsistent; branch incoherence for $e_m=0$; corridor breaches. (Use codes like `E/1A/S4/SCHEMA/...`, `E/1A/S4/CONTEXT/NOT_ZTP`, `E/1A/S4/COUNTER/VIOLATION`, `E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION`, `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`, `E/1A/S4/CORRIDOR/...`.)
* **MERCHANT-scoped (skip merchant, continue run):**
  Numeric policy error from S4.2 (non-finite/≤0 $\lambda$, **with no S4 rows**), or **retry exhaustion** (exact 64/64/1 triple): `E/1A/S4/NUMERIC/NONFINITE_LAMBDA`, `E/1A/S4/RETRY/EXHAUSTED_64`. Exhaustion then follows governed policy (`abort` vs `downgrade_domestic`).

All errors **must** emit structured diagnostics with the natural keys and envelope counters to allow byte-level triage.

---

## 7) Outputs of S4.6

* **Validation artefacts:** S4 contributes to the **validation bundle** for 1A with (a) per-merchant verdicts (accepted $K_m$, exhausted, or aborted numeric), (b) run-level corridor metrics and pass/fail, and (c) a summary of any run-scoped failures. (Bundle content hashed and surfaced as part of the 1A validation flag.)
* **No new data rows in S4:** S4.6 writes **no** new logs beyond error diagnostics; it evaluates the existing S4 streams and emits a validation result. (The three S4 streams remain the only persists for this state.)

---

## 8) Why these invariants suffice (soundness)

* I-ZTP1–4 ensure **bit-replayability** (same inputs ⇒ same attempt trace and payloads) and **schema/lineage** integrity for audit.
* I-ZTP2–3 enforce the **finite-state** acceptance/exhaustion semantics and make the 64-cap observable and unique.
* I-ZTP5 adds **population-level** drift detection (acceptance geometry), catching silent regressions even when per-row schema is fine.
* I-ZTP6–7 maintain **cross-state coherence** and **exactly-once** log semantics.

---

This S4.6 spec matches the locked invariants and the dictionary-pinned streams, and removes ambiguity about **what to check**, **how to check it**, **what fails**, and **who must stop** when it fails. It’s ready to wire into your S9 validator and CI gates.

---

# S4.7 — Failure taxonomy & scopes

## 1) Purpose & authority

S4.7 makes failure handling **deterministic and auditable**. It completes S4.1–S4.6 by (a) classifying failures, (b) prescribing **what to emit** (exact rows or none), (c) defining **scope → action**, and (d) binding everything to the dataset dictionary paths, envelopes, and invariants already locked. The run’s validation bundle must record the outcome (including exhaustion policy).

---

## 2) Inputs & shared knobs

* **Per-merchant inputs:** eligibility $e_m$, $N_m$, openness $X_m$, $\theta$, and the computed $\lambda_{\text{extra},m}$ from S4.2; ZTP attempt logs from S4.5 (`poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`).
* **Governed knob:** `crossborder_hyperparams.ztp_on_exhaustion_policy ∈ {"abort","downgrade_domestic"}` (default `"abort"`). Policy affects only the **post-exhaustion** downstream path; the **diagnostic signature is identical** either way. This decision must be **echoed in the validation bundle**.
* **Corridor thresholds** (mean rejections; high-quantile): governed in validation config and enforced as **run-scoped** checks.

---

## 3) Deterministic error identifiers

Emit stable, grep-friendly codes in diagnostics and the validation bundle:

```
err_code := "E/1A/S4/<CLASS>/<DETAIL>"
```

Examples (normative names used below):
`E/1A/S4/NUMERIC/NONFINITE_LAMBDA`, `E/1A/S4/RETRY/EXHAUSTED_64`, `E/1A/S4/SCHEMA/MALFORMED_EVENT`, `E/1A/S4/COUNTER/VIOLATION`, `E/1A/S4/COVERAGE/MISSING_RETRY_EXHAUSTED`, `E/1A/S4/CONTEXT/NOT_ZTP`, `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`, `E/1A/S4/CORRIDOR/MEAN_REJ_OVER_0p05`. Include `{merchant_id, lambda (if defined), attempt_if_applicable, counters_before/after, partition_path}` for reproducible triage.

---

## 4) Failure classes (canonical table)

| Class (err_code)                                                            | Condition (precise)                                                                                                                                                                      | What to emit (rows)                                                                                                                                                                          | Scope                | Action                                                                                                                                         | Validator trigger                                                                     |              |         |            |                 |
| ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------ | ------- | ---------- | --------------- |
| **Numeric policy** (`E/1A/S4/NUMERIC/NONFINITE_LAMBDA`)                      | In S4.2, $\lambda_{\text{extra},m}$ is `!isfinite` **or** $\le 0$ (binary64).                                                                                                            | **Emit nothing** in S4 (no `poisson_component`, no `ztp_*`).                                                                                                                                 | **Merchant**         | Abort merchant; S5–S6 not entered.                                                                                                             | S4.2 check; if any S4 rows exist for such $m$, **run** abort (`INCONSISTENT_ABORT`).  |              |         |            |                 |
| **Retry exhaustion** (`E/1A/S4/RETRY/EXHAUSTED_64`)                          | S4.5 reaches 64 consecutive Poisson zeros.                                                                                                                                               | **Exactly**: 64 `poisson_component` (`k=0`), 64 `ztp_rejection` (`attempt=1…64`), and **one** `ztp_retry_exhausted{attempts=64,aborted=true}` (diagnostic rows do **not** advance counters). | **Merchant**         | Apply governed policy: `"abort"` → abort merchant; `"downgrade_domestic"` → set $K_m:=0$, skip S5–S6, proceed to S7 home-only (record reason). | Coverage signature + envelopes checked in S4.6/S9.                                    |              |         |            |                 |
| **Schema/partition** (`E/1A/S4/SCHEMA/MALFORMED_EVENT`)                      | Any S4 row missing RNG envelope fields; wrong schema types; path/partitions not exactly `{seed, parameter_hash, run_id}`; missing required payload fields.                               | N/A (invalid).                                                                                                                                                                               | **Run**              | Abort run.                                                                                                                                     | Dictionary conformance checks.                                                        |              |         |            |                 |
| **Context contamination** (`E/1A/S4/CONTEXT/NOT_ZTP`)                        | Any `poisson_component` row for S4 has `context!="ztp"` (e.g., `"nb"`).                                                                                                                  | As observed (invalid context).                                                                                                                                                               | **Run**              | Abort run.                                                                                                                                     | Envelope/payload check (S4.4).                                                        |              |         |            |                 |
| **Counter discipline** (`E/1A/S4/COUNTER/VIOLATION`)                         | Draw rows (`poisson_component`) don’t advance counters **or** diagnostic rows (`ztp_*`) advance counters; or per-merchant `before` counters are not strictly increasing across attempts. | As observed.                                                                                                                                                                                 | **Run**              | Abort run.                                                                                                                                     | Envelope counters check (S4.4/S4.6).                                                  |              |         |            |                 |
| **Lambda drift** (`E/1A/S4/PAYLOAD/LAMBDA_DRIFT`)                            | For a merchant, `poisson_component.lambda` not **bit-equal** across attempts **or** not equal to recomputed $\lambda_{\text{extra},m}$.                                                  | As observed.                                                                                                                                                                                 | **Run**              | Abort run.                                                                                                                                     | Payload equality vs S4.2 recompute.                                                   |              |         |            |                 |
| **Coverage inconsistency** (`E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION`) | Eligible merchant has S4 rows but neither: accepted signature (last `k≥1` with preceding zeros matched by `ztp_rejection`), nor: exhaustion signature (64/64/1).                         | “Inconsistent” mix; typically missing/extra rows.                                                                                                                                            | **Run**              | Abort run.                                                                                                                                     | S4.6 I-ZTP2/3.                                                                        |              |         |            |                 |
| **Exhaustion inconsistency** (`E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION`)    | `ztp_retry_exhausted` present but \`                                                                                                                                                     | P                                                                                                                                                                                            | ≠64`or any`P.k≠0`or` | R                                                                                                                                              | ≠64\`.                                                                                | As observed. | **Run** | Abort run. | S4.6 coverage.  |
| **Branch incoherence** (`E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`)              | $e_m=0$ but S4 events exist for $m$.                                                                                                                                                     | As observed (should be empty).                                                                                                                                                               | **Run**              | Abort run.                                                                                                                                     | S3↔S4 coherence rule.                                                                 |              |         |            |                 |
| **Corridor breach** (`E/1A/S4/CORRIDOR/*`)                                   | Cohort diagnostics from S4.6 (e.g., mean rejections, $p_{99.9}$) violate governed thresholds.                                                                                            | As observed; logs are valid.                                                                                                                                                                 | **Run**              | Abort run (CI).                                                                                                                                | S4.6 population tests; thresholds governed.                                           |              |         |            |                 |

**Notes.** The **exhaustion probability** is $e^{-64\lambda}$; this underpins both corridor expectations and the rarity of merchant-scoped exhaustions at moderate $\lambda$.

---

## 5) Emission policy per failure (no half-measures)

S4 never writes “partial” artefacts outside these rules:

* **Numeric policy error:** **no S4 rows at all** for that merchant. Any presence is an **inconsistent abort → run failure**.
* **Retry exhaustion:** the **exact triple** 64/64/1 must appear (draws consume RNG; diagnostics don’t). Downstream action depends on the governed policy but the **trace is identical**.
* **Schema/lineage/counter/context/c overage**: they are **run-scoped** problems—treat as fatal regardless of the attempt content; downstream never runs.

A concise matrix (deterministic) for what appears in the logs per failure class is provided in your draft and remains authoritative (reproduced conceptually here).

---

## 6) Validator procedure (failure detection sequence)

Within `{seed, parameter_hash, run_id}`:

1. **Branch gate:** if $e_m=0$ then **assert no S4 rows** for $m$; else proceed. Violation → `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS` (**run-scoped**).
2. **Recompute $\lambda$:** from S4.2 inputs. If non-finite/≤0 then **assert no S4 rows**; else `E/1A/S4/NUMERIC/INCONSISTENT_ABORT` (**run-scoped**).
3. **Schema/partitions & context:** check dictionary paths, partitions `{seed, parameter_hash, run_id}`, RNG envelope completeness, and `context="ztp"`. Violations → `E/1A/S4/SCHEMA/*` or `…/CONTEXT/NOT_ZTP` (**run-scoped**).
4. **Counters:** draws advance; diagnostics don’t; `before` strictly increases per merchant. Else `E/1A/S4/COUNTER/VIOLATION` (**run-scoped**).
5. **Lambda constancy:** `poisson_component.lambda` is **bit-equal** across attempts and equals recomputed $\lambda$. Else `E/1A/S4/PAYLOAD/LAMBDA_DRIFT`. (**run-scoped**).
6. **Coverage signature:** either **accept** (last `k≥1`, prior zeros consistent with `ztp_rejection`) **or** **exhausted** (64/64/1). Else `E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION` (**run-scoped**).
7. **Corridors:** compute cohort metrics (mean rejections, $p_{99.9}$) per S4.6; breach → `E/1A/S4/CORRIDOR/*` (**run-scoped**).

---

## 7) Recording outcomes (validation bundle)

* **Per-merchant verdict:** `{merchant_id, status ∈ {accepted, exhausted, numeric_abort}, K_m (if accepted), lambda, attempts, err_code?}`.
* **Run summary:** corridor metrics, exhaustion counts, and any **run-scoped** failure list.
* **Exhaustion policy echo:** when exhaustion occurs, include `{policy_applied ∈ {"abort","downgrade_domestic"}}`. All of this is part of the 1A validation flag surface at the end of the layer.

---

## 8) Idempotency & re-runs

* **Idempotency keys:** `(merchant_id, attempt, context="ztp")` for draws; `(merchant_id, attempt)` for rejections; `(merchant_id)` for exhausted. Duplicates are schema violations (run-scoped).
* **Re-run determinism:** Given identical inputs and lineage, the **same failure class** and **identical artefact pattern** recur (e.g., numeric abort writes **no** rows; retry exhaustion re-emits the exact 64/64/1).

---

## 9) Worked edge cases (canonical outcomes)

* **λ computed non-finite, but S4 rows found:** This is **state incoherence**; raise `E/1A/S4/NUMERIC/INCONSISTENT_ABORT` (run-scoped). The only consistent outcomes for non-finite λ are **no S4 rows**.
* **`ztp_retry_exhausted` present with <64 `ztp_rejection`:** `E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION` (run-scoped).
* **Eligible merchant with only `poisson_component`(k=0) and no diagnostic rows:** `E/1A/S4/COVERAGE/MISSING_RETRY_EXHAUSTED` (run-scoped).
* **Ineligible merchant (`e_m=0`) with any S4 row:** `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS` (run-scoped).
* **Counters advanced on `ztp_rejection`:** `E/1A/S4/COUNTER/VIOLATION` (run-scoped).

---

## 10) Why this taxonomy is sufficient

It aligns one-to-one with the **locked S4** failure bullets (numeric invalid; retry exhaustion; schema/lineage), expands schema/lineage into **context**, **counters**, **coverage**, and **corridors**, and ties each to: **what is observed in logs**, **what the validator proves**, and **what downstream may do**. There are no “silent” failures: every path is either **merchant-scoped** with a deterministic trace (or none), or **run-scoped** and stops CI immediately.

---

**Hand-off note:** S4.8 (next) will summarise outputs: accepted $K_m$ (and nothing else) for S5–S6; or the exhaustion/numeric-abort paths which preclude S5–S6 for that merchant—exactly as your state flow specifies.

---

# S4.8 — Outputs (state boundary)

## 1) Purpose & scope (what “exits” S4)

S4 produces:

* A **single in-memory scalar per merchant** on the accepted path,

  $$
  \boxed{K_m\in\{1,2,\dots\}}
  $$

  used *read-only* by S5–S6. There is **no S4 table** that persists $K_m$.
* An **audit trail only** (three JSONL event streams, partitioned by `{seed, parameter_hash, run_id}`), used by validation to replay and gate corridors. **No parameter-scoped or egress datasets** are produced by S4.

S4’s outputs *deterministically* drive S5→S6→S7 as specified in the combined flow.

---

## 2) Per-merchant outcomes (exhaustive)

### A) **Eligible & accepted** (no 64-cap)

S4 exposes the *scalar* $K_m\ge 1$ to S5/S6 (in memory), and leaves an attempt trace in the logs:

* `poisson_component` (consuming): attempts 1…$a^*$, with last `k≥1`, `context="ztp"`, constant `lambda=λ_{extra,m}>0`.
* `ztp_rejection` (non-consuming): attempts 1…$a^*-1$ (one per zero).
* **No** `ztp_retry_exhausted`.
  Validation uses these to prove I-ZTP2/3/4 and bit-replay.

### B) **Eligible but exhausted** (64 zeros)

Emit the exact **64/64/1** signature and **do not** expose $K_m$:

* 64 `poisson_component` rows with `k=0`,
* 64 `ztp_rejection` rows (`attempt=1..64`),
* 1 `ztp_retry_exhausted{attempts=64,aborted=true}` (non-consuming).
  Downstream action is governed (abort vs domestic downgrade) but the diagnostic trace is identical.

### C) **Ineligible** ($e_m=0$)

S4 emits **no** events; $K_m$ is already fixed to **0** by S3 and the merchant **bypasses S4–S6**. Any S4 event here is a branch-coherence failure.

---

## 3) What S4 **hands off** to S5–S6 (and what it doesn’t)

### Scalar interface

* If A) accepted: S4 provides $K_m$ in memory only. S5/S6 may assume $K_m\in\mathbb{Z}_{\ge1}$ but **must not** persist it; `country_set` remains the only authority for cross-country order later (S6).
* If B) exhausted with `ztp_on_exhaustion_policy="downgrade_domestic"`: **set $K_m:=0$**, **skip S5–S6**, and proceed to S7 with home-only, carrying `"ztp_exhausted"` in the validation bundle. If the policy is `"abort"`, skip S5–S7 for that merchant altogether.
* If C) ineligible: $K_m:=0$ from S3; no S4 events.

### Downstream “size” contracts (how $K_m$ is consumed)

* **S6 pre-screen/cap:** S6 computes

  $$
  M_m=\lvert\mathcal{D}(\kappa_m)\setminus\{\text{home}\}\rvert,\quad K_m^\star=\min(K_m,M_m).
  $$

  If $M_m=0$, it persists only the home row and emits **no** `gumbel_key` (reason `"no_candidates"`). If $M_m < K_m$, it proceeds with the cap $K_m^\star$. These rules are *owned by S6*, not S4.

---

## 4) Authoritative event streams (paths, partitions, schema refs)

S4 persists **only** these streams (JSONL, partitioned by `{seed, parameter_hash, run_id}`), pinned in the dictionary:

| Stream                | Path prefix                               | Schema ref                                          | Produced by               |
|-----------------------|-------------------------------------------|-----------------------------------------------------|---------------------------|
| `poisson_component`   | `logs/rng/events/poisson_component/...`   | `schemas.layer1.yaml#/rng/events/poisson_component` | `1A.nb_poisson_component` |
| `ztp_rejection`       | `logs/rng/events/ztp_rejection/...`       | `#/rng/events/ztp_rejection`                        | `1A.ztp_sampler`          |
| `ztp_retry_exhausted` | `logs/rng/events/ztp_retry_exhausted/...` | `#/rng/events/ztp_retry_exhausted`                  | `1A.ztp_sampler`          |

All rows **must** carry the RNG envelope (`{ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_*, rng_counter_after_*, merchant_id}`) and follow S4’s context/counter rules (draws consume; diagnostics don’t).

---

## 5) Cardinalities & payload invariants (downstream can rely on)

* **Attempt trace completeness:** Eligible merchants have a finite trace ending in **acceptance** (last `k≥1`) or **exhaustion** (exact 64/64/1). Missing/extra rows are structural failures caught in validation.
* **Lambda constancy:** In `poisson_component`, `lambda` is **bit-identical** across attempts and equals the recomputed $\lambda_{\text{extra},m}$ from S4.2.
* **Context discipline:** `poisson_component.context=="ztp"` in S4; never `"nb"` here.
* **Partitions are fixed:** all three streams are *exactly* partitioned by `{seed, parameter_hash, run_id}` as pinned in the dictionary.

---

## 6) How S6 will turn $K_m$ into persisted order (for awareness)

* S6 reads $K_m$ (effective $K_m^\star$), draws **one** uniform per candidate to form Gumbel keys, logs `gumbel_key`, selects the top $K_m^\star$, and then **persists** the authoritative `country_set` rows: rank 0 = home, ranks $1..K_m^\star$ = selected foreign ISOs in Gumbel order. Any mismatch between these ranks and `gumbel_key.selection_order` is a validation failure.

---

## 7) Validator hooks tied to this boundary

S9 (validation) consumes S4’s streams to assert:

* **I-ZTP2/3/4:** coverage (accept vs 64/64/1), attempt indexing, schema/envelope/counter discipline.
* **I-ZTP1:** deterministic bit-replay of each attempt sequence and accepted $K_m$ under fixed lineage.
* **I-ZTP5:** population corridors (mean rejections < 0.05; $p_{99.9}<3$); breaches are run-scoped.

No new datasets are written by S4 for validation; all checks run **over the three S4 logs**.

---

## 8) Minimal boundary algorithm (normative; read → decide → expose)

```
INPUT:
  e_m ∈ {0,1} (from S3), grouped S4 logs per merchant m
OUTPUT:
  Either: expose scalar K_m≥1 to S5/S6; or mark merchant as exhausted/aborted; or skip (e_m=0)

if e_m = 0:
    assert no S4 logs exist for m                     # branch coherence (S3)
    # downstream sees K_m := 0 (S3), skips S4–S6
    RETURN

P ← poisson_component(context="ztp") rows for m, ordered by attempt
R ← ztp_rejection rows for m, ordered by attempt
X ← ztp_retry_exhausted row for m (0 or 1)

assert partitions == {seed, parameter_hash, run_id} (dictionary)
assert lambda(P) is bit-constant and > 0
if X exists:
    assert |P|=64 and |R|=64 and all P.k=0           # exhaustion signature
    # downstream: apply governed exhaustion policy
    RETURN
else:
    assert |P|≥1 and last(P).k ≥ 1 and all prior P.k = 0
    assert attempts(R) = {1..|P|-1}
    EXPOSE K_m := last(P).k to S5/S6                 # (in memory only)
    RETURN
```

This is the precise “what-exits-S4” logic the validators also mirror.

---

## 9) Idempotency & determinism (re-runs)

Re-running the same `{seed, parameter_hash, manifest_fingerprint}` and inputs yields the **same** attempt trace and the **same** outcome class (accept with the same $K_m$, or the identical 64/64/1 exhaustion). S4 **never** mutates S2/S3 results or any allocation tables; it only gates entry to S5–S6.

---

## 10) Cross-state consistency reminders

* S3’s **I-EL3** forbids any ZTP/Gumbel/Dirichlet events for $e_m=0$; S6 later persists `country_set` for *all* merchants reaching S3 (home-only for domestic/downgraded, home + foreigns for eligible). S4’s boundary aligns exactly with that contract.

---

### One-line summary

**Accepted path:** expose $K_m\ge1$ (in memory), plus attempt logs.
**Exhausted path:** emit 64/64/1 signature, no $K_m$; downstream policy decides.
**Ineligible:** no S4 logs; $K_m:=0$ from S3.
No other outputs originate in S4.

---

Yes—S4.1 → S4.8 as we’ve written is internally consistent and matches the locked S4 spec and the combined state-flow: domains, invariants, envelope/partition rules, failure semantics, and the 64-cap signature all line up; the few naming wrinkles (`lambda` vs `lambda_extra`) are handled explicitly and remain consistent with the expanded draft’s schema refs. No contradictions found relative to the locked text; downstream assumptions (S5–S6) are respected.

Alright—moving on.

---

# S4.9 — Validation bundle math, CI gates, and test vectors (100% detail)

## 1) Purpose

S4.9 specifies **exactly** how the run’s validator/CI proves S4 is correct using the three S4 event streams, how it computes **gates** (corridors) from first principles, and what **artifacts** are recorded in the validation bundle. It also provides **deterministic test vectors** and **query templates** so implementers can reproduce the checks byte-for-byte. (S4 still emits no datasets beyond the three RNG streams; the “bundle” is a validator output.)

**Inputs (authoritative):**
`logs/rng/events/poisson_component`, `logs/rng/events/ztp_rejection`, `logs/rng/events/ztp_retry_exhausted`, all partitioned by `{seed, parameter_hash, run_id}` and carrying the RNG envelope; S3’s eligibility flag; S2’s $N_m$; `crossborder_hyperparams.yaml` & `crossborder_features` to recompute $\lambda_m$.

---

## 2) Deterministic reconstruction (per merchant)

For each merchant $m$:

1. **Branch coherence:** If $e_m=0$, assert **no** S4 rows exist; skip $m$. If any exist → run abort `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`.
2. **Recompute $\lambda_m$:** $\eta_m=\theta_0+\theta_1\log N_m+\theta_2 X_m$; $\lambda_m=\exp(\eta_m)$. If non-finite or $\le0$, assert **no** S4 rows; otherwise run abort (`INCONSISTENT_ABORT`).
3. **Group & order rows:** $P=$ all `poisson_component(context="ztp")` by `attempt`; $R=$ `ztp_rejection` by `attempt`; $X\in\{∅,\{\text{row}\}\}$ from `ztp_retry_exhausted`. Partitions must match `{seed, parameter_hash, run_id}`.
4. **Envelope & counters:** Draws: `after>before` & `before` strictly increases; Diagnostics: `after==before`; wrong → run abort.
5. **Lambda constancy:** All `P.lambda` equal $\lambda_m$ **bit-for-bit**; all `R/X.lambda_extra` equal $\lambda_m$. Else run abort.
6. **Coverage signature:**

   * **Accept:** $|P|\ge1$, last `k≥1`, prior `k=0`, and $|R|=|P|-1$.
   * **Exhaust:** $|P|=|R|=64$ with all `k=0`, and `X.attempts=64`.
     Otherwise run abort.

The validator stores for each eligible $m$: `status ∈ {accepted, exhausted, numeric_abort}`, `K_m` if accepted, `attempts`, `lambda`, and any `err_code`.

---

## 3) Corridor math (population gates) — exact formulas & estimators

Let $p_{\text{acc}}(m)=1-e^{-\lambda_m}$. From S4.3, the number of **zero** draws before success $R_m$ is Geometric$(p_{\text{acc}}(m))$ (failures-before-success), hence

$$
\mathbb{E}[R_m]=\frac{e^{-\lambda_m}}{1-e^{-\lambda_m}},\qquad
\Pr(R_m\ge L)=e^{-L\lambda_m}.
$$

### 3.1 Run-level targets (deterministic given $\{\lambda_m\}$)

For the cohort $\mathcal{M}_\text{elig}$ of eligible merchants:

* **Mean rejections (target):**

  $$
  \mu_R^\star=\frac{1}{|\mathcal{M}_\text{elig}|}\sum_{m}\frac{e^{-\lambda_m}}{1-e^{-\lambda_m}}.
  $$
* **p-quantile of rejections (target, upper envelope):** Using inverse CDF on the mixture is exact but expensive; the validator gates via **binning** (below). For a bucket with mean $\bar\lambda$, the model quantile is

  $$
  Q_R^\star(q\mid\bar\lambda)=\Big\lceil \frac{\log\!\big(\tfrac{1}{1-q}\big)}{\bar\lambda}-1\Big\rceil.
  $$
* **Exhaustion rate (target, per bucket):**

  $$
  \rho^\star_{64}(\bar\lambda)=e^{-64\bar\lambda}.
  $$

### 3.2 Estimators from logs (observed)

* **Per-merchant rejections:** $r_m=
  \begin{cases}
  |R| & \text{if accepted}\\
  64 & \text{if exhausted}
  \end{cases}$.
* **Run mean:** $\widehat{\mu}_R=\frac{1}{|\mathcal{M}_\text{elig}|}\sum_m r_m$.
* **Empirical $p$-quantile:** the $p$-th order statistic of $\{r_m\}$.
* **Exhaustion rate:** share with `ztp_retry_exhausted`.

### 3.3 Binning (to compare apples-to-apples)

Partition $\mathcal{M}_\text{elig}$ into buckets $B_j$ by $\lambda_m$ (e.g., log-spaced edges $[0.02,0.05,0.1,0.2,0.5,1,2,5,\infty)$); for each $B_j$ compute:

$$
\bar\lambda_j=\frac{1}{|B_j|}\sum_{m\in B_j}\lambda_m,\quad
\widehat{\mu}_{R,j}=\frac{1}{|B_j|}\sum_{m\in B_j}r_m,\quad
\widehat{\rho}_{64,j}=\frac{1}{|B_j|}\sum_{m\in B_j}\mathbf{1}\{r_m=64\}.
$$

Gate with $\widehat{\mu}_{R,j}$ vs $\mu^\star_{R}(\bar\lambda_j)$ and $\widehat{\rho}_{64,j}$ vs $e^{-64\bar\lambda_j}$. (Edges are governed; the math is fixed.)

### 3.4 CI/alerting (optional but recommended)

Use Wilson intervals for proportions (exhaustion) and a normal approximation for the mean (large $n$). This does **not** change pass/fail thresholds (those are governed), but supports dashboards.

**Gates (from locked text/draft):** mean rejections < **0.05**; empirical $p_{99.9}<3$. Store governed thresholds in the validation config; S4.9 references them but does not hard-code them in code.

---

## 4) Validation bundle — structure of what gets recorded

**Per-merchant table (logical schema):**
`{merchant_id, status ∈ {accepted, exhausted, numeric_abort}, K, attempts, lambda, err_code?}` plus lineage keys `{seed, parameter_hash, run_id}` to make joins deterministic. (K null when exhausted/abort.)

**Run summary (logical schema):**
`{seed, parameter_hash, run_id, n_eligible, n_accepted, n_exhausted, mean_rejections, p99_9_rejections, bins:[{edge_lo,edge_hi,n,lambda_bar,mu_R_hat,mu_R_star,exhaust_rate_hat,exhaust_rate_star}], corridors_pass:bool, corridor_failures:[code...]}`. Thresholds and edges are echoed verbatim for audit.

**Failure list (logical schema):** array of `{err_code, count, examples:[{merchant_id, attempt?, counters_before_after, path}...]}`. Codes follow S4.7.

(Where this bundle is persisted is part of S9; S4.9 defines **content and math** so it’s implementation-agnostic.)

---

## 5) Language-Agnostic Reference Algorithm

This is the canonical, implementation-neutral procedure that consumes the three S4 event streams + deterministic inputs and emits a validation bundle with pass/fail. It assumes the **authoritative paths/partitions/schemas** for the S4 streams and the **S4 invariants & coverage signatures** already locked in S4.1–S4.8.

> **Authoritative inputs this algorithm expects** (all partitioned by `{seed, parameter_hash, run_id}`):
> `logs/rng/events/poisson_component` (S4 uses `context="ztp"`), `logs/rng/events/ztp_rejection`, `logs/rng/events/ztp_retry_exhausted`; plus S2’s `N_m`, S3’s eligibility `e_m`, S4.2’s hyperparams/features to recompute $\lambda_m$. Presence/absence, context, counters, and acceptance/exhaustion **signatures** are as specified in S4.4–S4.8.

---

```text
ALGORITHM  S4_Validate_ZTP_Run   # language-agnostic, deterministic

INPUT:
  seed, parameter_hash, run_id
  Streams (JSONL or equivalent), partitioned by {seed, parameter_hash, run_id}:
    P_stream := logs/rng/events/poisson_component
    R_stream := logs/rng/events/ztp_rejection
    X_stream := logs/rng/events/ztp_retry_exhausted
  Tables:
    S2_outlet_count[N_m by merchant_id]
    S3_eligibility[e_m by merchant_id]
    CrossborderFeatures[X_m by merchant_id]       # openness ∈ [0,1]
    CrossborderHyperparams[θ0, θ1, θ2, ztp_on_exhaustion_policy]
  Thresholds (governed):
    MEAN_REJ_MAX    # e.g., 0.05
    P999_REJ_MAX    # e.g., 3
    LAMBDA_BIN_EDGES := monotonically increasing vector (for binning)
  Options:
    ENABLE_BIT_REPLAY ∈ {true,false}  # heavy optional check

OUTPUT:
  ValidationBundle:
    PerMerchant: {merchant_id, status ∈ {accepted, exhausted, numeric_abort},
                  K (nullable), attempts, r_m, lambda, err_code?}
    RunSummary:  {n_eligible, n_accepted, n_exhausted,
                  mean_rejections, p99_9_rejections,
                  bins: [{edge_lo, edge_hi, n, lambda_bar,
                          mu_R_hat, mu_R_star, exhaust_rate_hat, exhaust_rate_star}],
                  corridors_pass: bool, corridor_failures: [codes...]}

CONSTANTS & DEFINITIONS:
  # Invariants to assert (names align with S4.6):
  I-ZTP1: bit-replay determinism (optional heavy check)
  I-ZTP2: coverage signature (accept or exact 64/64/1 exhaustion)
  I-ZTP3: strict attempt indexing (1.., max 64; exhausted.attempts == 64)
  I-ZTP4: schema/context/envelope/counter discipline
  I-ZTP6: branch coherence (no S4 rows for e_m = 0)
  I-ZTP7: idempotency keys (no duplicate natural keys)

  # Natural keys (idempotency):
  KEY_P(m,a) := (merchant_id=m, attempt=a, context="ztp")
  KEY_R(m,a) := (merchant_id=m, attempt=a)
  KEY_X(m)   := (merchant_id=m)

  # Recompute λ per merchant (binary64):
  RecomputeLambda(m):
      η ← θ0 + θ1 * log(N_m) + θ2 * X_m          # θ1 ∈ (0,1) is governed
      λ ← exp(η)
      return λ

  # Binning helper for λ:
  BinIndex(λ):
      return smallest j with LAMBDA_BIN_EDGES[j] ≤ λ < LAMBDA_BIN_EDGES[j+1]

  # Error emission helper:
  FailRun(code, details)      # aborts the run
  FailMerchant(m, code)       # marks merchant as aborted (no run abort)

PRE-INGEST CHECKS (partition & schema authority):
  0. Assert P/R/X stream paths and partitions match dataset dictionary exactly.
  1. For every row in P/R/X:
       - Envelope present: {ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
                            module, substream_label,
                            rng_counter_before_lo/hi, rng_counter_after_lo/hi, merchant_id}
       - Types/domains per schema.
     If any violation → FailRun("E/1A/S4/SCHEMA/MALFORMED_EVENT").

INGEST & GROUPING:
  2. Read P_stream, R_stream, X_stream (for this partition) into per-merchant groups:
       P[m] := all P_stream rows with merchant_id=m AND context == "ztp"
       R[m] := all R_stream rows with merchant_id=m
       X[m] := the single X_stream row with merchant_id=m (or ∅)
     Reject any P row with context != "ztp" → FailRun("E/1A/S4/CONTEXT/NOT_ZTP").

  3. Enforce idempotency (no duplicate keys):
       - P: KEY_P(m,a) unique; R: KEY_R(m,a) unique; X: KEY_X(m) unique.
     Else → FailRun("E/1A/S4/SCHEMA/DUPLICATE_KEY").

  4. Order attempts:
       sort P[m] by attempt ASC; sort R[m] by attempt ASC.

MAIN LOOP (per merchant m):
  5. e ← S3_eligibility[m] (default 0 if missing)
     if e == 0:
         # I-ZTP6: ineligible merchants must have no S4 rows
         if |P[m]|>0 or |R[m]|>0 or |X[m]|>0:
             FailRun("E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS", m)
         record PerMerchant[m] := {status="numeric_abort" if λ non-finite upstream else "accepted"? N/A}
         continue

  6. Load N_m, X_m, (θ0,θ1,θ2). Compute λ := RecomputeLambda(m).
     if λ is not finite or λ ≤ 0:
         # Numeric policy: this merchant should not have S4 rows
         if |P[m]|>0 or |R[m]|>0 or |X[m]|>0:
             FailRun("E/1A/S4/NUMERIC/INCONSISTENT_ABORT", m)
         PerMerchant[m] := {status="numeric_abort", K=null, attempts=0, r_m=0, lambda=null,
                            err_code="E/1A/S4/NUMERIC/NONFINITE_LAMBDA"}
         continue

  7. I-ZTP4 — envelope & counter discipline:
       For each row p in P[m]:
         assert p.rng_counter_after > p.rng_counter_before           # lexicographic on (hi,lo)
       assert sequence of p.rng_counter_before is strictly increasing
       For each row r in R[m] and row x in X[m]:
         assert rng_counter_after == rng_counter_before              # diagnostics do NOT consume RNG
       if any fails → FailRun("E/1A/S4/COUNTER/VIOLATION", m)

  8. I-ZTP4 — payload constancy & positivity:
       # For S4, every P row must carry lambda (binary64) bit-equal to recomputed λ
       if any p.lambda != λ (bit-equal) → FailRun("E/1A/S4/PAYLOAD/LAMBDA_DRIFT", m)
       if any r.lambda_extra != λ (bit-equal) → FailRun("E/1A/S4/PAYLOAD/LAMBDA_DRIFT", m)

  9. I-ZTP3 — attempt indexing:
       assert R[m].attempts == {1,2,...,|R[m]|}
       if X[m] exists: assert X[m].attempts == 64
       else: assert (|R[m]| ≤ 63)                                     # no '64' unless exhausted
       if any fails → FailRun("E/1A/S4/COVERAGE/BAD_INDEXING", m)

 10. I-ZTP2 — coverage signature & acceptance:
       if X[m] exists:          # exhaustion branch must have exact 64/64/1
          assert |P[m]| == 64 AND |R[m]| == 64 AND (∀p∈P[m], p.k == 0)
          if not → FailRun("E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION", m)
          PerMerchant[m] := {status="exhausted", K=null, attempts=64, r_m=64, lambda=λ}
       else:
          # acceptance branch: last P must have k≥1; all prior P have k=0
          assert |P[m]| ≥ 1
          for i in 1..(|P[m]|-1): assert P[m][i].k == 0
          assert P[m][|P[m]|].k ≥ 1
          assert |R[m]| == |P[m]| - 1
          if any fails → FailRun("E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION", m)
          K ← P[m][|P[m]|].k
          PerMerchant[m] := {status="accepted", K=K, attempts=|P[m]|, r_m=|R[m]|, lambda=λ}

 11. (Optional) I-ZTP1 — bit-replay determinism (heavy check):
       if ENABLE_BIT_REPLAY:
          # Re-draw Poisson(λ) along the S4 RNG lane and assert equality of every p.k and counters.
          # This uses the same substream label and open-interval uniforms; details are engine-specific.
          if mismatch detected → FailRun("E/1A/S4/REPLAY/MISMATCH", m)

RUN-LEVEL CORRIDORS (population diagnostics):
 12. Compute cohort over eligible merchants:
       E := { m | PerMerchant[m].status ∈ {accepted, exhausted} }
       n_eligible := |E|
       r_list := [ PerMerchant[m].r_m for m in E ]
       mean_rejections := average(r_list)
       p99_9_rejections := 99.9th empirical percentile of r_list (integer order statistic)

 13. Compare to governed gates:
       corridor_failures := []
       if mean_rejections ≥ MEAN_REJ_MAX:
           corridor_failures.append("E/1A/S4/CORRIDOR/MEAN_REJ_OVER_LIMIT")
       if p99_9_rejections ≥ P999_REJ_MAX:
           corridor_failures.append("E/1A/S4/CORRIDOR/P999_REJ_OVER_LIMIT")

 14. Bin-by-λ analysis (deterministic buckets):
       Initialise bins[j] for j = 1..(|LAMBDA_BIN_EDGES|-1)
       For each m ∈ E:
           j := BinIndex(PerMerchant[m].lambda)
           bins[j].n += 1
           bins[j].lambda_sum += PerMerchant[m].lambda
           bins[j].r_sum += PerMerchant[m].r_m
           if PerMerchant[m].status == "exhausted": bins[j].exhaust_count += 1
       For each bin j with n>0:
           lambda_bar := bins[j].lambda_sum / bins[j].n
           mu_R_hat   := bins[j].r_sum / bins[j].n
           mu_R_star  := exp(-lambda_bar) / (1 - exp(-lambda_bar))
           exhaust_rate_hat  := bins[j].exhaust_count / bins[j].n
           exhaust_rate_star := exp(-64 * lambda_bar)
           bins[j] := {edge_lo, edge_hi, n, lambda_bar,
                       mu_R_hat, mu_R_star, exhaust_rate_hat, exhaust_rate_star}

BUNDLE & EXIT:
 15. Build ValidationBundle.RunSummary:
       RunSummary := { n_eligible, n_accepted = count status==accepted,
                       n_exhausted = count status==exhausted,
                       mean_rejections, p99_9_rejections,
                       bins: materialise(bins),
                       corridors_pass := (corridor_failures == []),
                       corridor_failures }

 16. Return { PerMerchant, RunSummary }.
       If any FailRun was raised, the run must be aborted with the associated err_code.

COMPLEXITY:
  - Time: O(#rows) for ingest/group + O(#merchants) for checks and metrics.
  - Memory: streaming-friendly; at most O(active merchants) state when reading pre-sorted partitions.
```


## 6) Test vectors (deterministic, replay-stable)

These vectors let you verify the validator **without** relying on a particular RNG library. Each vector defines $(N,X,\theta)\Rightarrow \lambda$, and a **synthetic** attempt trace that **by construction** obeys S4’s schema and counters. The validator should accept these as green; any deviation is a bug in ingestion, grouping, counters, or coverage logic.

> **Vector A (moderate $\lambda$, quick accept)**
> Inputs: $N=10,\ X=0.6,\ \theta=(\theta_0,\theta_1,\theta_2)=(-0.05,0.5,0.3)$.
> $\eta=-0.05+0.5\log 10+0.3\cdot0.6\approx 0.5\log10+0.13-0.05\approx 1.19897$.
> $\lambda=\exp(\eta)\approx 3.317$.
> Expected: very high $p_{\text{acc}}=1-e^{-3.317}\approx0.964$.
> **Trace:** `P(k,attempt)={(0,1),(2,2)}`, `R(attempt)={1}`, no `X`.
> **Outcome:** accepted $K=2$, `r_m=1`.

> **Vector B (small $\lambda$, several rejections)**
> Inputs: $N=2,\ X=0.1,\ \theta=(-2,0.5,0.4)$.
> $\eta=-2+0.5\log2+0.4\cdot0.1\approx -2+0.3466+0.04=-1.6134$.
> $\lambda\approx 0.199$; $p_{\text{acc}}\approx 0.181$.
> **Trace:** `P={(0,1),(0,2),(0,3),(1,4)}`, `R={1,2,3}`, no `X`.
> **Outcome:** accepted $K=1$, `r_m=3`.

> **Vector C (exhaustion signature)**
> Inputs: choose any $\lambda\le 0.01$ (e.g., $N=2,X=0,\theta=(-5,0.3,0.1)\Rightarrow\lambda\approx0.010$).
> **Trace:** `P={(0,a) for a=1..64}`, `R={1..64}`, `X.attempts=64`.
> **Outcome:** exhausted, policy-dependent downstream; validator expects exact **64/64/1**.

For each vector, the validator must also check:

* `poisson_component.lambda` is **bit-equal** across attempts to the recomputed $\lambda$;
* `context="ztp"` on `poisson_component`;
* Draw rows advance counters; diagnostic rows **don’t**;
* Partitions `{seed, parameter_hash, run_id}` are correct.

---

## 7) Complexity & resource budget (validator)

* **Row volume per merchant:** Accepted with $a$ attempts → $a+(a-1)$ rows; exhausted → **129** rows (64 draws + 64 rejections + 1 exhausted).
* **Time:** O(#rows) grouping by merchant, then O(#merchants) checks.
* **Memory:** stream per partition; accumulate per-merchant state (attempt counter, last `k`, flags) — $O(1)$ per active merchant window.

---

## 8) Edge-case matrix (what the validator must do)

| Situation                                                                                            | Expectation               | Action                                                                            |
|------------------------------------------------------------------------------------------------------|---------------------------|-----------------------------------------------------------------------------------|
| `poisson_component` rows exist but **no** `ztp_rejection` rows while finals show `k=0` before accept | Coverage violated         | Run abort `E/1A/S4/COVERAGE/MISSING_RETRY_EXHAUSTED` (or “…/MISSING_REJECTIONS”) |
| `ztp_retry_exhausted` present with (P\ne64) or any `P.k≠0`                                           | Inconsistent exhaustion   | Run abort `E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION`                              |
| `context != "ztp"` in any S4 draw                                                                    | Context contamination     | Run abort `E/1A/S4/CONTEXT/NOT_ZTP`                                               |
| Counters advance on diagnostics or don’t on draws                                                    | Counter discipline broken | Run abort `E/1A/S4/COUNTER/VIOLATION`                                             |
| `lambda` drift across attempts vs recompute                                                          | Payload drift             | Run abort `E/1A/S4/PAYLOAD/LAMBDA_DRIFT`                                          |
| Eligible merchant with **no** S4 rows and **no** exhausted row                                       | Missing activity          | Run abort (coverage)                                                              |
| Ineligible merchant with any S4 row                                                                  | Branch incoherence        | Run abort `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`                                  |

---

## 9) What S4.9 does **not** change

It introduces **no new persisted streams** and no changes to S4’s RNG/event protocol. It simply formalises the **math, aggregation, and outputs** of the validator/CI for S4, consistent with the locked state text and the expanded draft.

---