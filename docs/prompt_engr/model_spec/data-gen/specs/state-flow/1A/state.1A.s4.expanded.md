# S4.1 — Universe, symbols, authority

## 1) Scope & entry gate (who can be here)

Evaluate S4 **only** for merchants $m$ that:

* were classified **multi-site** in S1 (so S2 ran and accepted a domestic count), and
* are **eligible for cross-border** per S3, i.e. $e_m=1$.

Ineligible merchants $e_m=0$ **must not** produce any S4 events; they keep $K_m:=0$ and skip S4–S6. This branch-coherence rule is asserted in S3 and re-checked here.

> **Contract.** If $e_m=0$ then the streams `poisson_component`, `ztp_rejection`, `ztp_retry_exhausted` are **absent** for that merchant. Presence is a run-stopping validation error.

## 2) Symbols & inputs available at S4 entry

Per merchant $m$:

* Identity & home: $(\texttt{merchant_id}=m,\ \texttt{home_country_iso}=c)$ from ingress/S0.
* S2 output: **accepted** domestic outlet count $N_m\in\{2,3,\dots\}$ (read-only in S4).
* S3 gate: eligibility flag $e_m\in\{0,1\}$ (deterministic).
* Hyperparameters: $\theta=(\theta_0,\theta_1,\theta_2)$ and governance metadata loaded from `crossborder_hyperparams.yaml` (Wald/drift constraints enforced at load/CI; S4 just consumes).
* Feature(s): openness scalar $X_m\in[0,1]$ from **approved** `crossborder_features` (parameter-scoped; keyed by `merchant_id`).

  * **Missing policy:** if `X_m` row is **absent** → **abort run** (configuration error).
  * **Range policy:** if $X_m<0$ or $X_m>1$ → **clamp** to $[0,1]$ deterministically before use.
* Lineage carried into *every* RNG event: `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, and the RNG envelope counters (see §4).
  *(Note: `manifest_fingerprint` is part of the envelope for audit; it is **not** a partition key.)*

Derived (for later S4.2): the canonical-scale predictor $\eta_m$ and mean $\lambda_{\text{extra},m}=\exp(\eta_m)>0$. **No draws occur in S4.1.**

> **Notation:** `log` denotes the **natural logarithm**.

## 3) Outputs S4 is allowed to produce (authority)

S4 persists **only RNG event streams** (plus the in-memory scalar $K_m$ once accepted). All S4 event datasets are **fixed by the dataset dictionary** and must partition exactly by `{seed, parameter_hash, run_id}`; no alternate partition layouts are permitted.

**Authoritative event streams used by S4:**

1. `logs/rng/events/poisson_component/...` with schema `#/rng/events/poisson_component`. Used in S2 **and** S4; **S4 rows must have `context="ztp"`** to disambiguate from S2 (`"nb"`).

   * **Producer vs module (normative note):** the dataset dictionary uses `produced_by: 1A.nb_poisson_component` (shared stream identity), while S4 writes rows with envelope `module="1A.ztp_sampler"`. This is **intentional**; do not conflate `produced_by` with the envelope `module`.
2. `logs/rng/events/ztp_rejection/...` with schema `#/rng/events/ztp_rejection`. One row per zero draw, attempt-indexed. **Counters must not advance**.
3. `logs/rng/events/ztp_retry_exhausted/...` with schema `#/rng/events/ztp_retry_exhausted`. Present iff 64 consecutive zeros occurred. **Counters must not advance**.

> S4 writes **no** parameter-scoped datasets and **no** egress tables; only these event streams. Downstream artefacts (candidate weights, ordered `country_set`) are produced in S5–S6 using $K_m$.

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
* `context` is a **closed, case-sensitive enum**: `{"nb","ztp"}`. S4 **must** use `context="ztp"`. Any other casing/value (e.g., `"ZTP"`, `"Ztp"`) is a context-contamination error and **aborts** the run.

**Counter discipline:**

* For each `poisson_component` row (a *draw*), `after > before` (lexicographic on the two 64-bit words) and the sequence of `before` counters is strictly increasing across attempts.
* For diagnostic streams `ztp_rejection` and `ztp_retry_exhausted`, **no RNG is consumed**: `after == before`.
* Violations → **abort run** (schema/counter/lineage failure).

**Uniforms & source of randomness:** Poisson draws in S4 use the keyed substream mapping from S0.3.3 and the **open-interval** $U(0,1)$ primitive per S0.3.4. S4 references the **Poisson(λ) regime selection** defined in S0.3.7. (Cross-referenced in the locked S4 text.)

## 5) Event payloads (exact fields, domains, invariants)

All three streams inherit the RNG envelope (above). The **payload fields** and **merchant-local invariants** for S4 are:

### 5.1 `poisson_component` (context="ztp")

Required payload per row $a=1,2,\dots$:

* `merchant_id` = $m$ (FK to ingress universe)
* `context` = `"ztp"` (string literal; see enum above)
* `lambda` = $\lambda_{\text{extra},m}$ (IEEE-754 binary64, **strictly positive**)
* `k` = drawn count $k_a\in\{0,1,2,\dots\}$ (integer)
* `attempt` = $a\in\mathbb{N}$ (1-based, strictly increasing)

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

* If **accepted**: ≥1 `poisson_component` row with `k≥1`; any preceding zero attempts must have matching `ztp_rejection` rows with attempts $1,\dots,r_m$.
* If **exhausted**: **exactly 64** `poisson_component` rows with `k=0`, **exactly 64** `ztp_rejection` rows (attempts 1..64), and **exactly one** `ztp_retry_exhausted`. Missing/extra ⇒ structural error.

## 6) Partitions, paths, and ownership (dictionary authority)

All three S4 event streams are governed by the dataset dictionary and **must** be written under these path/partition contracts:

* **Poisson**
  Path: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  Schema: `schemas.layer1.yaml#/rng/events/poisson_component`
  Dictionary: `produced_by: 1A.nb_poisson_component` *(shared stream id; S4 constrains `context="ztp"`)*.
  *(Reminder: `manifest_fingerprint` lives in the envelope only; it is not a partition key.)*

* **ZTP rejection**
  Path: `logs/rng/events/ztp_rejection/...`
  Schema: `schemas.layer1.yaml#/rng/events/ztp_rejection`
  Dictionary: `produced_by: 1A.ztp_sampler`.

* **ZTP retry exhausted**
  Path: `logs/rng/events/ztp_retry_exhausted/...`
  Schema: `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`
  Dictionary: `produced_by: 1A.ztp_sampler`.

The openness feature comes from:
`data/layer1/1A/crossborder_features/parameter_hash={parameter_hash}/`
Schema: `schemas.1A.yaml#/model/crossborder_features`
Role: “Deterministic per-merchant features for S4; currently the openness scalar $X_m \in [0,1]$ with **missing→abort** and **out-of-range→clamp**.”

## 7) Determinism & invariants the validator will assert

* **I-ZTP1 (bit-replay):** For fixed $(N_m,X_m,\theta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the attempt sequence $(K_1,K_2,\dots)$ and accepted $K_m$ are **bit-identical** across runs; envelope counters and payloads must match exactly.
* **I-ZTP2–3 (coverage & indexing):** Trace completeness and strict attempt numbering; exhaustion signature is unique.
* **I-ZTP4 (schema conformance):** Envelope present; `context="ztp"` from the closed enum; `lambda>0`; counters advance for draws and do **not** advance for diagnostics.
* **I-ZTP5 (population corridors):** mean rejections < 0.05 and empirical $p_{99.9}<3$. Breach ⇒ **abort run**.
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
  - theta0, theta1, theta2 from crossborder_hyperparams.yaml
  - X_m from crossborder_features (approved; missing->abort; out-of-range->clamp to [0,1])
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
6  load (theta0, theta1, theta2) from crossborder_hyperparams.yaml
7  load X_m from crossborder_features; if missing -> abort; else clamp X_m to [0,1]
8  # Defer numeric guards to S4.2; here we only stage using natural log:
9  eta_m := theta0 + theta1 * log(N_m) + theta2 * X_m   # IEEE-754 binary64 (not persisted here)
10 open_stream_writer("logs/rng/events/poisson_component", partitions={seed, parameter_hash, run_id})
11 open_stream_writer("logs/rng/events/ztp_rejection",     partitions={seed, parameter_hash, run_id})
12 open_stream_writer("logs/rng/events/ztp_retry_exhausted",partitions={seed, parameter_hash, run_id})
13 envelope_base := { run_id, seed, parameter_hash, manifest_fingerprint,
                      module="1A.ztp_sampler", substream_label="poisson_component" }
14 return PREPARED_CONTEXT(...)
```

---

# S4.2 — Link function & parameterisation

## 1) Purpose & scope

Map the merchant-level covariates available at S4 entry to a **strictly positive** Poisson mean $\lambda_{\text{extra},m}$ for the **zero-truncated Poisson** (ZTP) draw of foreign-country count $K_m$. This state performs **no RNG** and **persists nothing**; it deterministically computes $\eta_m$ and $\lambda_{\text{extra},m}$ for use by the S4 sampler. Positivity and numeric finiteness are enforced here; S4.5 uses $\lambda_{\text{extra},m}$ in every `poisson_component` attempt payload.

---

## 2) Inputs (per eligible merchant $m$) & preconditions

**Eligibility & size**

* $e_m = 1$ (merchant passed S3 cross-border gate). If $e_m=0$, S4 must not run; $K_m:=0$ is fixed upstream.
* $N_m \in \{2,3,\dots\}$ is the accepted **total outlet count** from S2; $N_m$ is read-only here. (The $\log N_m$ domain is valid.)

**Feature**

* $X_m \in [0,1]$ (**openness**) from the **parameter-scoped** `crossborder_features` table (partitioned by `{parameter_hash}`; FK on `merchant_id`, column `openness`).

  * Missing row → **abort run (config error)**.
  * Out-of-range → **clamp deterministically** to $[0,1]$ before use.

**Hyperparameters & governance**

* $\theta=(\theta_0,\theta_1,\theta_2)$ from `crossborder_hyperparams.yaml`.

  * **Normative constraint:** $0<\theta_1<1$ (sub-linear elasticity in $\log N$).
  * **Design intent for $\theta_2$:** **no sign constraint** (may be $>0$ or $\le 0$, e.g., positive for openness, negative for frictions).
    Violations are CI/config-time failures; S4.2 defensively re-checks.

**Numeric environment**

* All arithmetic is IEEE-754 **binary64** with the **natural** log/exp. Do **not** use fused multiply-add (avoid cross-platform drift).

**Governed numeric policy (clamps)**

* Read `lambda_min`, `lambda_max` from governance (e.g., `numeric_policy.s4.lambda_min`, `numeric_policy.s4.lambda_max`).

  * If absent, treat as **no-op defaults** (`lambda_min = 0`, `lambda_max = +∞`).
  * These are **design clamps**, not validation: they stabilise the sampler regime without introducing new artefacts.

---

## 3) Canonical definitions (boxed)

### 3.1 Linear predictor (canonical scale)

$$
\boxed{\ \eta_m \;=\; \theta_0 \;+\; \theta_1\,\log N_m \;+\; \theta_2\,X_m,\qquad 0<\theta_1<1\ }\tag{S4.2-A}
$$

### 3.2 Mean map (Poisson mean for ZTP)

$$
\boxed{\ \lambda_{\text{extra},m}^{\text{raw}} \;=\; \exp(\eta_m) \;>\; 0\ }\tag{S4.2-B}
$$

### 3.3 Governed clamp (design, not validation)

$$
\boxed{\ \lambda_{\text{extra},m} \;=\; \min\!\bigl(\max(\lambda_{\text{extra},m}^{\text{raw}},\ \lambda_{\min}),\ \lambda_{\max}\bigr)\ }\tag{S4.2-C}
$$

> The sampler (S4.5) and all logs must use **this clamped $\lambda_{\text{extra},m}$**.

---

## 4) Numeric guards (normative)

Evaluate $\eta_m$, $\lambda_{\text{extra},m}^{\text{raw}}$, then apply the clamp to get $\lambda_{\text{extra},m}$ (all in binary64). Then:

* **G1 — finiteness:** If either $\eta_m$, $\lambda_{\text{extra},m}^{\text{raw}}$, or $\lambda_{\text{extra},m}$ is not finite → **abort merchant** with `numeric_policy_error`. S4 must emit **no events** for this merchant.
* **G2 — positivity:** If $\lambda_{\text{extra},m} \le 0$ (theoretically impossible with clamp unless misconfigured) → **abort merchant** with `numeric_policy_error`.
* **Governance check:** If loaded $\theta_1\notin(0,1)$ (or documented drift violations) → **abort run in CI** (`config_governance_violation`); no merchants proceed.

---

## 5) Interpretation & comparative statics

Let $\lambda=\lambda_{\text{extra},m}$.

* **Elasticity w\.r.t. size:** $\displaystyle \frac{\partial \log\lambda}{\partial\log N}=\theta_1\in(0,1)$.
* **Marginal effect of openness:** $\displaystyle \frac{\partial \lambda}{\partial X}=\theta_2\,\lambda$ (sign/magnitude driven by $\theta_2$).
* **Acceptance rate intuition:** ZTP rejection step accepts with $1-e^{-\lambda}$ (used later for corridor expectations).

---

## 6) Contracts with S4 logging & validation

* Every `poisson_component` attempt **must carry** `lambda` equal to $\lambda_{\text{extra},m}$ **bit-for-bit** for that merchant.
* Diagnostics may expose the field as `lambda_extra`; **mapping note:** `poisson_component.lambda == lambda_extra` (bit-identical).
* The validator recomputes $\eta_m,\lambda_{\text{extra},m}$ from $(N_m,\theta,X_m)$ (including the same clamp) and asserts **binary64 equality** against every observed `lambda`.

---

## 7) Reference algorithm (language-agnostic; no RNG, no emission)

```text
INPUT:
  e_m ∈ {0,1}                         # S3; must be 1 to enter S4.2
  N_m ≥ 2                             # S2 (accepted outlet count)
  X_m ∈ [0,1]                         # from model/crossborder_features (schema: 'openness')
  θ = (θ0, θ1, θ2)                    # from crossborder_hyperparams.yaml (governed)
  lambda_min, lambda_max              # from governance (optional; defaults 0, +∞)

OUTPUT:
  (η_m, λ_extra_m)                    # scalars for S4.5; not persisted

1  assert e_m == 1
2  assert N_m ≥ 2
3  if not (0.0 < θ1 < 1.0): abort_run("config_governance_violation")
4  # Clamp X_m into [0,1] (missing would have been caught earlier)
5  X_m ← min(max(X_m, 0.0), 1.0)
6  # Canonical computations (natural log/exp; binary64; no FMA)
7  η_m ← θ0 + θ1 * log(N_m) + θ2 * X_m
8  λ_raw ← exp(η_m)
9  if (not isfinite(η_m)) or (not isfinite(λ_raw)): abort_merchant("numeric_policy_error")
10 λ_min_eff ← (lambda_min is set) ? max(lambda_min, 0.0) : 0.0
11 λ_max_eff ← (lambda_max is set) ? max(lambda_max, λ_min_eff) : +∞
12 λ_extra_m ← min(max(λ_raw, λ_min_eff), λ_max_eff)
13 if (not isfinite(λ_extra_m)) or (λ_extra_m <= 0.0): abort_merchant("numeric_policy_error")
14 return (η_m, λ_extra_m)
```

---

## 8) Invariants (checked at or implied by S4.2)

* **I-LINK1 (Domain):** $e_m=1$ and $N_m\ge2$ on entry.
* **I-LINK2 (Feature):** $X_m$ sourced from `crossborder_features`; out-of-range clamped to $[0,1]$.
* **I-LINK3 (Governed parameter):** $0<\theta_1<1$ (defensive re-check here).
* **I-LINK4 (Numeric):** $\lambda_{\text{extra},m}\in(0,\infty)$ (after clamp). Fail → merchant-scoped numeric policy error; **no S4 events** exist for $m$.
* **I-LINK5 (Payload constancy hook):** If any S4 events exist for $m$, every `poisson_component.lambda` equals the recomputed $\lambda_{\text{extra},m}$ **bit-exactly** (same clamp applied).

---

## 9) What S4.2 hands to the next sub-state

A pair $(\eta_m,\lambda_{\text{extra},m})$ **after clamp**, in memory only. S4.3 fixes the ZTP law; S4.5 performs the rejection sampler, emitting `poisson_component` / `ztp_*` streams with `lambda` set to this exact value.

---

# S4.3 — Target distribution (Zero-Truncated Poisson)

## 1) Purpose (what this sub-state fixes)

Pin the **exact law** S4.5 must sample from (and S9 must validate). No RNG, no persistence. All formulas use the **clamped** $\lambda\equiv\lambda_{\text{extra},m}>0$ computed in S4.2 (binary64).

---

## 2) Canonical ZTP on $\{1,2,\dots\}$ (baseline mode)

Let $Y\sim\text{Poisson}(\lambda)$ and define $K=Y\mid(Y\ge1)$. With $Z(\lambda)=1-e^{-\lambda}$,

$$
\Pr[K=k]=\frac{e^{-\lambda}\lambda^k}{k!\,Z(\lambda)},\quad k=1,2,\dots \tag{ZTP-pmf}
$$

$$
F_K(k)=\frac{F_Y(k)-e^{-\lambda}}{Z(\lambda)},\quad k\ge1 \tag{ZTP-cdf}
$$

$$
\mathbb{E}[K]=\frac{\lambda}{Z(\lambda)},\quad
\mathrm{Var}(K)=\frac{\lambda+\lambda^2}{Z(\lambda)}-\Big(\frac{\lambda}{Z(\lambda)}\Big)^2. \tag{ZTP-moments}
$$

Useful recurrence (exact, stable): $\Pr[K=k{+}1]/\Pr[K=k]=\lambda/(k{+}1)$.

---

## 3) Optional right-truncated ZTP on $\{1,\dots,M\}$ (if $M$ is known)

If the **candidate count** $M$ (from S5) is known **before** sampling, the bias-free target is the **right-truncated** ZTP:

$$
\Pr[K=k\mid1\le K\le M]=\frac{e^{-\lambda}\lambda^k/k!}{F_Y(M)-e^{-\lambda}},\quad k=1,\dots,M. \tag{rtZTP-pmf}
$$

$$
F_K^{(M)}(k)=\frac{F_Y(k)-e^{-\lambda}}{F_Y(M)-e^{-\lambda}},\quad k=1,\dots,M. \tag{rtZTP-cdf}
$$

If you **don’t** use this and instead do $K^\star=\min(K,M)$ later, that is a **deliberate design deviation** (downward bias when $M$ is small). See §6 “Contracts” for how to declare the mode.

---

## 4) Rejection identities (what S4.5 must implement)

**Baseline ZTP (no right truncation).** Draw $Y\sim\text{Poisson}(\lambda)$; **accept iff** $Y\ge1$; return $K=Y$.

* Per-attempt acceptance: $p_{\text{acc}}=Z(\lambda)=1-e^{-\lambda}$.
* Zeros-before-success $R\sim\text{Geom}(p_{\text{acc}})$ (failures-before-success):
  $\mathbb{E}[R]=\tfrac{e^{-\lambda}}{1-e^{-\lambda}}$, $\Pr(R\ge L)=e^{-L\lambda}$.

**Right-truncated ZTP (if chosen).** Draw $Y\sim\text{Poisson}(\lambda)$; **accept iff** $1\le Y\le M$; return $K=Y$.

* Per-attempt acceptance: $p_{\text{acc}}^{(M)}=F_Y(M)-e^{-\lambda}$.
* Then $R\sim\text{Geom}(p_{\text{acc}}^{(M)})$:
  $\mathbb{E}[R]=\tfrac{1-p_{\text{acc}}^{(M)}}{p_{\text{acc}}^{(M)}}$, $\Pr(R\ge L)=(1-p_{\text{acc}}^{(M)})^L$.

**Retry quantiles (both modes).** For $q\in(0,1)$,

$$
Q_R(q)=\Big\lceil \frac{\log(1/(1-q))}{p_{\text{acc}}}\Big\rceil-1
\quad\text{or}\quad
\Big\lceil \frac{\log(1/(1-q))}{p_{\text{acc}}^{(M)}}\Big\rceil-1.
$$

These are the **exact corridor targets** S9 uses for mean/high-quantile rejections and exhaustion rates (with $L=64$).

---

## 5) Numerically stable forms (binary64)

* $Z(\lambda)=1-e^{-\lambda} = -\mathrm{expm1}(-\lambda)$.
* $\log Z(\lambda)=\log1p(-e^{-\lambda})$.
* $\log \Pr[K=k]=-\lambda+k\log\lambda-\log(k!) - \log Z(\lambda)$ with `lgamma(k+1)`.
* For CDFs, prefer regularized-gamma routines; avoid naïve summation.
* Small-$\lambda$: $Z(\lambda)\approx \lambda-\lambda^2/2$; $p_{\text{acc}}\approx \lambda$; $\mathbb{E}[R]\approx 1/\lambda-1$.
* Large-$\lambda$: $Z(\lambda)\to 1$; $\Pr(\text{exhaust at }64)\approx e^{-64\lambda}$ (astronomically small for $\lambda\gtrsim 0.2$).

---

## 6) Contracts that bind S4.5/S9 to this law

* **Mode (normative, governed):**
  `s4.truncation_mode ∈ {"late_cap","right_truncated"}` (case-sensitive).

  * `"late_cap"` (default to match current design): S4.5 uses **baseline ZTP** (§2/§4 baseline). S6 later applies $K^\star=\min(K,M)$.
    – **Bias note:** This intentionally differs from rtZTP; S9 corridors must use $p_{\text{acc}}=1-e^{-\lambda}$.
  * `"right_truncated"`: S4.5 must know $M$ at draw time and use **rtZTP** (§3/§4 truncated). S9 corridors must use $p_{\text{acc}}^{(M)}$.
* **Log payload contract:** Every S4.5 `poisson_component` attempt includes `lambda == λ` (bit-identical to S4.2). No additional fields are required for the chosen mode; S9 infers the correct acceptance function from `s4.truncation_mode` and (if needed) `M` from S5.
* **Trace ↔ theory:** The count of `ztp_rejection` rows for merchant $m$ equals the realised $R$; the first `poisson_component.k≥1` occurs at attempt $R{+}1$ and yields $K_m$.

---

## 7) Invariants (no RNG consumed here)

* **I-LAW1 (domain):** $\lambda>0$ finite (from S4.2) is required; otherwise S4.5 does not run for $m$.
* **I-LAW2 (equivalence):** Conditional distribution of accepted `poisson_component.k` equals the chosen law (ZTP or rtZTP).
* **I-LAW3 (exhaustion math):** Observed exhaustion share at $L=64$ matches $e^{-64\lambda}$ (ZTP) **or** $(1-p_{\text{acc}}^{(M)})^{64}$ (rtZTP) when bucketed by similar $\lambda$ (and $M$ for rtZTP).

---

## 8) What S4.3 hands forward

A **pure mathematical contract** (pmf/cdf/moments, acceptance probability, and retry identities) plus the **governed mode** that S4.5 must implement and S9 must validate against. No datasets are written by S4.3.

---

# S4.4 — RNG protocol & event schemas

## 1) Substream & context (namespacing)

* **Substream label (required).** Every Poisson attempt in S4 uses

  $$
  \boxed{\ \texttt{substream_label} \equiv \text{"poisson_component"}\ }
  $$

  with **`context="ztp"`** to disambiguate from S2’s NB usage of the same stream. The keyed mapping from **S0.3.3** derives Philox state; validators prove replay using the envelope pre/post counters (§2).

* **Context enum (closed, case-sensitive).**
  `context ∈ {"nb","ztp"}`. S4 **must** use `context="ztp"` (exact casing). Any other value/casing (e.g. `"ZTP"`, `"Ztp"`) is a **context-contamination error**.

* **Module tag (envelope field).** For S4 emissions, `module` **must** be `"1A.ztp_sampler"`.
  *(Dataset dictionary lineage for the shared stream may say `produced_by: 1A.nb_poisson_component`; that identifies the **stream**, not the emitting **module**. This difference is intentional.)*

* **Uniform primitive.** All Poisson draws consume only iid **open-interval** uniforms $u\in(0,1)$ from the keyed substream (per S0.3).

---

## 2) Shared RNG envelope (must appear on **every** event row)

All S4 RNG JSONL events carry the **RNG envelope**:

```
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
  module, substream_label,
  rng_counter_before_lo, rng_counter_before_hi,
  rng_counter_after_lo,  rng_counter_after_hi,
  merchant_id, ...payload }
```

**Semantics & types (normative):**

* `ts_utc`: RFC3339 UTC timestamp with `Z`.
* `run_id`: run-scoped identifier (S0.2.4).
* `seed`: uint64 (master run seed).
* `parameter_hash`: 64-hex.
* `manifest_fingerprint`: 64-hex. *(In envelope for audit; **not** a partition key.)*
* `module`: string; **must** be `"1A.ztp_sampler"` for S4 events.
* `substream_label`: string; **must** be `"poisson_component"` in S4.
* `rng_counter_before_lo/hi`, `rng_counter_after_lo/hi`: uint64 words comprising the Philox **128-bit** counter immediately before / after **this event’s** RNG consumption. Validators compare **lexicographically on (hi, lo)**.
* `merchant_id`: FK to ingress universe.

**Draw-accounting (hard rules):**

* **Draw events** (`poisson_component`): `after > before`; the sequence of `before` counters is **strictly increasing** per merchant.
* **Diagnostics** (`ztp_rejection`, `ztp_retry_exhausted`): **non-consuming**; `after == before`.
* Any envelope/counter violation ⇒ **run-scoped** schema/lineage failure.

---

## 3) Authoritative event streams (paths, partitions, schema refs)

All three S4 streams are **logs** with the same partitions `{seed, parameter_hash, run_id}` and fixed paths pinned in the dataset dictionary.

1. **Poisson attempts** (draws; consuming)
   Path: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/poisson_component`
   Dictionary lineage: `produced_by: "1A.nb_poisson_component"` *(shared stream id; S4 distinguishes via `context="ztp"`)*

2. **ZTP rejections** (diagnostics; non-consuming)
   Path: `logs/rng/events/ztp_rejection/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/ztp_rejection`
   Dictionary lineage: `produced_by: "1A.ztp_sampler"`

3. **ZTP retry exhausted** (cap reached; non-consuming)
   Path: `logs/rng/events/ztp_retry_exhausted/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`
   Dictionary lineage: `produced_by: "1A.ztp_sampler"`

*(RNG core logs `rng_audit_log` / `rng_trace_log` are separate; see dictionary.)*

---

## 4) Event payloads (fields, types, domains, constraints)

All rows also include the **RNG envelope** (§2). All numeric math is binary64; equality checks use **bit-equality** to recomputed values.

### 4.1 `poisson_component` (attempt rows; consuming)

**Required payload:**

* `merchant_id` — FK (project id type).
* `context` — **must** equal `"ztp"` (closed enum).
* `lambda` — binary64; **strictly positive**; **must** equal the $\lambda_{\text{extra},m}$ computed in S4.2 for this merchant, **bit-for-bit**, across **every** attempt.
* `k` — integer $\in\{0,1,2,\dots\}$; the raw **untruncated** Poisson draw for this attempt.
* `attempt` — integer $\in\{1,2,\dots\}$; **strictly increasing** per merchant.

**Counter rule:** `after > before` (consuming). Envelope deltas may vary by attempt depending on Poisson regime (expected).

### 4.2 `ztp_rejection` (zero attempts; non-consuming)

**Required payload:**

* `merchant_id` — FK.
* `lambda_extra` — binary64; **strictly positive**; **bit-equal** to the merchant’s $\lambda_{\text{extra},m}$.
* `k` — integer; **must** equal `0`.
* `attempt` — integer $\in\{1,\dots,64\}$; **strictly increasing** per merchant.

**Counter rule:** `after == before` (non-consuming).

### 4.3 `ztp_retry_exhausted` (cap reached; non-consuming)

**Required payload:**

* `merchant_id` — FK.
* `lambda_extra` — binary64; **bit-equal** to $\lambda_{\text{extra},m}$.
* `attempts` — integer; **must** equal `64`.
* `aborted` — boolean; **must** be `true`.

**Cardinality:** at most **one** row per merchant; present **iff** 64 consecutive zero draws occurred.
**Counter rule:** `after == before`.

> **λ field mapping (normative).** `poisson_component.lambda` **equals** diagnostics `lambda_extra` **bit-for-bit** for a given merchant. Validators enforce this equality.

---

## 5) Presence/absence & cardinality (per merchant)

* **Eligible (`e_m=1`).**
  A finite sequence of `poisson_component` attempts with constant λ exists, ending either:
  **Accepted** — first row with `k ≥ 1` (stop; **no** `ztp_retry_exhausted`), with zero or more prior `ztp_rejection` rows whose `attempt` enumerate 1..R; **or**
  **Exhausted** — **exactly 64** `poisson_component` rows with `k=0`, **exactly 64** `ztp_rejection` rows (`attempt=1..64`), and **exactly one** `ztp_retry_exhausted`. Missing/extra rows ⇒ structural error.

* **Ineligible (`e_m=0`).**
  **No S4 events** may exist (branch-coherence). Presence ⇒ run-stopping validation failure.

---

## 6) Partitions, ordering, idempotency

* **Partitions.** All three streams **must** be partitioned by `{seed, parameter_hash, run_id}` exactly as in §3.
* **Ordering.** No file/row ordering guaranteed. Consumers **must** group by merchant and sort by `attempt`.
* **Idempotency / natural keys.**

  * `poisson_component`: key = `(merchant_id, attempt, context="ztp")`
  * `ztp_rejection`: key = `(merchant_id, attempt)`
  * `ztp_retry_exhausted`: key = `(merchant_id)`
    Duplicate keys ⇒ schema violation (run-scoped).

---

## 7) What validators assert from this protocol

* **I-ZTP1 (bit-replay).** With fixed $(N_m, X_m, \theta, \texttt{seed}, \texttt{parameter_hash}, \texttt{manifest_fingerprint})$, attempt sequences and accepted $K_m$ are reproducible; envelope counters and `lambda`/`lambda_extra` **match** recomputed values exactly.
* **I-ZTP2 (coverage).** Accepted merchants have ≥1 `poisson_component` and 0..R `ztp_rejection`; exhausted merchants have the **64/64/1** signature; ineligible have **no S4 events**.
* **I-ZTP3 (indexing).** `attempt` strictly increases from 1; `ztp_retry_exhausted.attempts == 64`.
* **I-ZTP4 (schema & counters).** Envelope present; `context="ztp"` for S4 draws; `lambda>0`; **draws advance counters**; diagnostics **do not**.

---

## 8) Failure taxonomy (scope → action)

* **Envelope/schema failure** — missing any of: `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_* / after_*, merchant_id`, or wrong partitions: **abort run**.
* **Context contamination** — `context ∉ {"nb","ztp"}` or `context!="ztp"` on S4 attempts: **abort run** (`E/1A/S4/CONTEXT/NOT_ZTP`).
* **Counter violation** — non-advancing draw or advancing diagnostic: **abort run**.
* **Numeric policy error** — non-finite/≤0 λ already caught in S4.2: merchant-scoped abort; **no S4 events**.
* **Branch incoherence** — any S4 event when `e_m=0`: **abort run** (contradicts S3).

---

# S4.5 — Sampling algorithm (ZTP via rejection from Poisson), deterministic & auditable

## 1) Purpose

For each **eligible** merchant $m$ ($e_m=1$), produce a **single** foreign-country count $K_m\in\{1,2,\dots\}$ by rejection sampling from $Y\sim\mathrm{Poisson}(\lambda_{\text{extra},m})$ with **truncation at 0** (ZTP baseline), while emitting an auditable attempt trace to the three S4 event streams using the **RNG envelope** and partitions pinned in the dictionary.

> **Truncation mode (governed, explicit here):** `s4.truncation_mode = "late_cap"`
> Under this mode, S4 samples baseline **ZTP on $\{1,2,\dots\}$**. S6 will later apply $K^{\star}=\min(K_m, M)$ once the candidate count $M$ is known. See **Bias note** in §3.

---

## 2) Preconditions & inputs (per eligible merchant $m$)

* **Eligibility & size:** $e_m=1$ (from S3), $N_m\ge2$ (from S2). Ineligible merchants **must not** emit S4 events.
* **Mean:** $\lambda\equiv\lambda_{\text{extra},m}$ from **S4.2**, already **binary64 finite & $>0$** after the governed clamp; this exact value **must** appear in every `poisson_component.lambda` for $m$.
* **RNG lane & protocol:** `substream_label="poisson_component"`, `context="ztp"`, open-interval $u\in(0,1)$; each attempt records **rng_counter_before/after**; diagnostics **do not** advance counters (per S4.4).
* **Streams & partitions:**
  `logs/rng/events/poisson_component/...`,
  `logs/rng/events/ztp_rejection/...`,
  `logs/rng/events/ztp_retry_exhausted/...`, all partitioned by `{seed, parameter_hash, run_id}` with schema refs in `schemas.layer1.yaml`.

---

## 3) Target & acceptance identity (recap + bias note)

We target $K=Y\mid(Y\ge1)$ where $Y\sim\mathrm{Poisson}(\lambda)$. Per-attempt acceptance is $p_{\text{acc}}=1-e^{-\lambda}$. Zeros-before-success $R\sim\mathrm{Geom}(p_{\text{acc}})$ (failures-before-success).

> **Bias note (mode = `"late_cap"`).** Since S4 samples baseline ZTP and S6 later sets $K^{\star}=\min(K,M)$, the resulting distribution differs from a right-truncated ZTP on $\{1,\dots,M\}$ when $M$ is small. This is **intentional**. S9 corridors for retries/acceptance **must** use $p_{\text{acc}}=1-e^{-\lambda}$ (baseline ZTP), not $p_{\text{acc}}^{(M)}$.

---

## 4) The attempt loop (normative)

**Index & cap.** Let the attempt index $a$ run from 1 up to a **hard cap** of 64. On acceptance ($k\ge1$), stop immediately; if 64 consecutive zeros occur, emit exhaustion and follow the governed policy.

**Per attempt $a$:**

1. **Draw Poisson (consuming).** Draw $k_a\sim\mathrm{Poisson}(\lambda)$ using the project regimes (S0.3.7) with open-interval uniforms; snapshot counters before/after; emit
   `poisson_component{ merchant_id=m, context="ztp", lambda=λ, k=k_a, attempt=a, envelope: before, after }`.
   – `lambda` **must** equal the S4.2 value **bit-for-bit** for $m$.
   – **Draw accounting:** `after > before`.

2. **Reject zero.** If $k_a=0$: emit non-consuming
   `ztp_rejection{ merchant_id=m, lambda_extra=λ, k=0, attempt=a, envelope: before=after, after=after }`,
   then continue with $a\leftarrow a+1$. **Counters must not advance.**

3. **Accept positive.** If $k_a\ge1$: set $K_m\leftarrow k_a$ and **stop**.

4. **Exhaustion at 64.** If $a=64$ and $k_a=0$: emit exactly one non-consuming
   `ztp_retry_exhausted{ merchant_id=m, lambda_extra=λ, attempts=64, aborted=true, envelope: before=after, after=after }`,
   then follow the **exhaustion policy** (§5).

All fields, partitions, and schema paths are fixed by the dictionary; any deviation is a **run-scoped schema/lineage failure**.

---

## 5) Exhaustion policy (governed, routes via S6)

Let `ztp_on_exhaustion_policy ∈ {"abort","downgrade_domestic"}` in `crossborder_hyperparams.yaml` (default `"abort"`):

* `"abort"`: **abort merchant** — no S5/S6/S7 artefacts for $m$.
* `"downgrade_domestic"`: set $K_m:=0$ and **proceed to S6 (not S7)** with **$K^{\star}=0$** so that **S6 persists the home-only `country_set`** (single source of truth). S7 must **not** synthesise `country_set` ad hoc.

In both cases the **`ztp_retry_exhausted`** diagnostic must be present (non-consuming).

---

## 6) What gets emitted (cardinalities & coverage)

**Accepted at attempt $a$ with $K_m=k\ge1$:**

* Exactly **$a$** rows in `poisson_component` (attempts $1..a$), constant `lambda=λ`, `context="ztp"`.
* Exactly **$a-1$** rows in `ztp_rejection` (attempts $1..a-1$).
* **No** `ztp_retry_exhausted`.

**Exhausted:**

* Exactly **64** rows in `poisson_component` with `k=0`.
* Exactly **64** rows in `ztp_rejection` (attempts $1..64$).
* Exactly **one** `ztp_retry_exhausted` row.

**Ineligible $e_m=0$:** **no S4 events of any type**. Presence is a branch-coherence failure.

---

## 7) Envelope & counter discipline (must-hold)

* Every `poisson_component` row **advances** counters; `ztp_rejection` and `ztp_retry_exhausted` **do not** (set `after==before`).
* `attempt` is **1-based** and strictly increasing per merchant; if attempt 64 occurs with `k=0`, `ztp_retry_exhausted.attempts==64` **must** exist.
* `context=="ztp"` in S4; **never** `"nb"`.
* For a fixed merchant, all attempts carry an **identical** binary64 `lambda` equal to the recomputed S4.2 value.

---

## 8) Idempotency & natural keys at the sink

* `poisson_component`: key `(merchant_id, attempt, context="ztp")`
* `ztp_rejection`: key `(merchant_id, attempt)`
* `ztp_retry_exhausted`: key `(merchant_id)`
  Duplicate keys ⇒ schema violation (run-scoped). Paths/partitions must match the dictionary exactly.

---

## 9) Validator hooks (what S9 will prove off these logs)

* **Bit-replay (I-ZTP1).** Recompute $\lambda$ from S4.2 inputs and re-run the Poisson sampler; assert equality of attempt count, each `k`, every `{before,after}`, and accepted $K_m$ or exhaustion outcome.
* **Coverage & indexing (I-ZTP2/3).** Cardinalities and attempt indexing follow §6/§7 (including the **64/64/1** signature).
* **Schema & counters (I-ZTP4).** Envelope present; `context="ztp"`; `lambda>0` bit-constant; **draws consume**, diagnostics **don’t**.
* **Corridors (I-ZTP5).** Using $p_{\text{acc}}(m)=1-e^{-\lambda_m}$, compare empirical mean rejections and high quantiles to geometric predictions; CI aborts on breach.

---

## 10) Minimal reference pseudocode (code-agnostic; matches schemas)

```text
INPUT:
  eligible merchant m (e_m = 1)
  λ = λ_extra,m > 0         # from S4.2 (clamped), binary64 finite
  substream_label = "poisson_component"
  envelope base: {seed, parameter_hash, manifest_fingerprint, run_id, module="1A.ztp_sampler"}

OUTPUT:
  either: accepted K_m ≥ 1 with a finite attempt trace; or exhaustion then policy

a ← 1
repeat:
    before ← snapshot_counter()
    k ← draw_poisson(λ)          # S0.3.7 regimes; iid u∈(0,1)
    after  ← snapshot_counter()

    emit poisson_component{merchant_id=m, context="ztp", lambda=λ, k=k, attempt=a,
                           envelope: before, after, substream_label}

    if k = 0 then
        emit ztp_rejection{merchant_id=m, lambda_extra=λ, k=0, attempt=a,
                           envelope: before=after, after=after}
        if a = 64 then
            emit ztp_retry_exhausted{merchant_id=m, lambda_extra=λ, attempts=64, aborted=true,
                                     envelope: before=after, after=after}
            if ztp_on_exhaustion_policy == "abort" then
                abort_merchant("ztp_exhausted")
            else  # "downgrade_domestic"
                K_m ← 0
                forward_to_S6_with(K_eff = 0)   # S6 persists home-only country_set
            end if
            STOP
        else
            a ← a + 1
            continue
    else
        K_m ← k
        STOP
```

---

## 11) Complexity & performance notes

* **Expected attempts** per merchant: $1+\mathbb{E}[R]=1+\dfrac{e^{-\lambda}}{1-e^{-\lambda}}$.
* **I/O upper bound** (exhausted): 64 draws + 64 rejections + 1 exhausted = **129** JSONL rows per merchant, partitioned by `{seed, parameter_hash, run_id}`.

---

## 12) State outputs / hand-off

* **Accepted path:** deliver in-memory $K_m\ge1$ to S5/S6; **S6** later sets $K^{\star}=\min(K_m,M)$ and persists `country_set`.
* **Exhausted path:** emit `ztp_retry_exhausted` and apply policy:
  – `"abort"` ⇒ merchant dropped from S5–S7;
  – `"downgrade_domestic"` ⇒ **route to S6 with $K^{\star}=0$** so **S6** writes the **home-only** `country_set`. S7 must **not** write `country_set`.

---

# S4.6 — Determinism & correctness invariants

## 1) Purpose & scope

S4.6 asserts the **truth conditions** for ZTP sampling and its logs. It defines: (a) determinism & schema/lineage invariants over the three S4 event streams, (b) per-merchant **coverage/cardinality** rules, (c) **bit-replay** checks, (d) mode-aware **corridor** tests (population diagnostics), and (e) a failure taxonomy with **deterministic error codes** and scopes.

**Authoritative inputs to the validator**

* Event streams (partitioned by `{seed, parameter_hash, run_id}`):
  `logs/rng/events/poisson_component/...` (S4 uses `context="ztp"`),
  `logs/rng/events/ztp_rejection/...`,
  `logs/rng/events/ztp_retry_exhausted/...`.
  Every row must carry the **RNG envelope** (§3.I-ZTP4).
* Deterministic inputs: $N_m$ (from S2), $X_m$ (from `crossborder_features`), $\theta$ (from `crossborder_hyperparams.yaml`), and **governed numeric policy** (`numeric_policy.s4.lambda_min`, `numeric_policy.s4.lambda_max`) to **recompute the clamped** $\lambda_{\text{extra},m}$.
* Truncation mode (governed): `s4.truncation_mode ∈ {"late_cap","right_truncated"}` (case-sensitive).
* Eligibility $e_m$ (from S3). Ineligible merchants **must** have **no S4 events**.

Locked invariants I-ZTP1…7 from the S4 spec are enforced here.

---

## 2) Per-merchant reconstruction (validator perspective)

For each merchant $m$ with $e_m\in\{0,1\}$:

* If $e_m=0$: assert **no** S4 rows exist (branch coherence). If any exist → **RUN-scoped** failure `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`. Skip remaining checks for $m$.

* If $e_m=1$: fetch $N_m\ge2$, $X_m$, $\theta$ and recompute

  $$
  \eta_m=\theta_0+\theta_1\log N_m+\theta_2 X_m,\quad
  \lambda^{\text{raw}}_m=\exp(\eta_m),\quad
  \lambda_m=\min(\max(\lambda^{\text{raw}}_m,\lambda_{\min}),\lambda_{\max})
  $$

  using the **same clamp** as S4.2 (binary64). If $\lambda_m$ is non-finite or $\le0$, then S4.2 should have aborted: **presence** of any S4 rows → **RUN-scoped** failure `E/1A/S4/NUMERIC/INCONSISTENT_ABORT`.

* Group S4 rows for $m$ into:
  $P$ = `poisson_component` (with `context="ztp"`), ordered by `attempt` (1,2,…)
  $R$ = `ztp_rejection`, ordered by `attempt` (1,2,…)
  $X$ = `ztp_retry_exhausted` (0 or 1 row)

All paths/partitions must exactly match the dataset dictionary.

---

## 3) Determinism & schema/lineage invariants (must-hold)

### I-ZTP1 — Bit-replay determinism (per merchant)

With fixed inputs $(N_m,X_m,\theta)$ and lineage $(\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the **attempt sequence** and acceptance/exhaustion outcome are **bit-identical** across runs.

* In $P$, `lambda` equals $\lambda_m$ **bit-for-bit** on **every** row; in $R\cup X$, `lambda_extra` equals $\lambda_m$ **bit-for-bit**.
* Re-running the project Poisson sampler (S0.3.7) on the `"poisson_component"` substream reproduces the exact `k` sequence and envelope counters (see I-ZTP4).

### I-ZTP2 — Event coverage & acceptance/exhaustion signature

Exactly one holds:

* **Accepted:** $|P|\ge1$; last row in $P$ has `k≥1`; all prior $P$ rows have `k=0`; and $R$ has **exactly** `attempt=1..(|P|-1)`. **No** `ztp_retry_exhausted`.
* **Exhausted:** $|P|=64$ **and** all `k=0`; $|R|=64$ with `attempt=1..64`; (|X|=1`with`attempts=64\`. (Merchant is then handled per policy downstream.)

Missing/extra rows ⇒ **RUN-scoped** structural failure.

### I-ZTP3 — Attempt indexing

* In $R$, `attempt` is **strictly increasing from 1** and $\le 64$.
* If $|X|=1$, then `X.attempts == 64`.

### I-ZTP4 — Schema, lineage & counter conformance

Every row in $P\cup R\cup X$ **must include** the envelope fields exactly:

`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, merchant_id }`

Additional payload fields per stream must match S4.4.

* `poisson_component.context == "ztp"` (closed enum `{"nb","ztp"}`; exact casing).
* **Counters advance** on draws (`after > before` in $P$; `before` strictly increases with `attempt`); diagnostics do **not** consume RNG (`after == before` in $R\cup X$).
* Paths/partitions match the dictionary exactly.
  Any violation ⇒ **RUN-scoped** failure (`E/1A/S4/SCHEMA/...`, `.../CONTEXT/NOT_ZTP`, `.../COUNTER/VIOLATION`).

### I-ZTP6 — Branch coherence (cross-state)

If $e_m=0$ then **no** S4 events may exist. Presence ⇒ **RUN-scoped** failure (see §2).

### I-ZTP7 — Idempotency keys

No duplicate natural keys at the sink:

* `poisson_component`: `(merchant_id, attempt, context="ztp")`
* `ztp_rejection`: `(merchant_id, attempt)`
* `ztp_retry_exhausted`: `(merchant_id)`

Duplicates ⇒ **RUN-scoped** schema violation.

---

## 4) Population diagnostics (corridor tests; mode-aware)

Define the per-merchant acceptance probability according to the governed mode:

* If `s4.truncation_mode == "late_cap"` (baseline ZTP):
  $p_{\text{acc}}(m)=1-e^{-\lambda_m}$.
* If `s4.truncation_mode == "right_truncated"` (needs $M$ from S5):
  $p_{\text{acc}}^{(M)}(m)=F_Y(M;\lambda_m)-e^{-\lambda_m}$ (Poisson CDF).

Let $R_m$ be the number of zeros before success inferred from logs: $|R|$ on acceptance; **64** on exhaustion.

**Metrics (governed thresholds; names are normative):**

* **Mean rejections**
  Compute $\bar{R}=\frac{1}{M}\sum_{m} R_m$.
  Compare against the model expectation
  $\frac{1}{M}\sum_m \frac{1-p_m}{p_m}$ with $p_m=p_{\text{acc}}(m)$ **or** $p_m=p_{\text{acc}}^{(M)}(m)$ by mode.
  Gate: $\bar{R} \le \texttt{validation.s4.mean_rejections_max}$ (default **0.05**).

* **High-quantile corridor**
  Empirical $Q_{0.999}(R)$ $\le \texttt{validation.s4.retry_p999_max}$ (default **3**).
  (Optionally also check $Q_{0.99}$ via `validation.s4.retry_p99_max`.)

* **Exhaustion rate**
  Within λ-buckets (or (λ,M) buckets for truncated mode), the share with `ztp_retry_exhausted` should match the predicted rate:
  $e^{-64\lambda}$ for **late_cap**, or $(1-p_{\text{acc}}^{(M)})^{64}$ for **right_truncated**.
  Tolerance set by `validation.s4.exhaustion_abs_tol` / `validation.s4.exhaustion_rel_tol`.

**Bucketing policy (normative):** use **equal-frequency** λ-bins of size `validation.s4.num_lambda_bins` (default 10). For `right_truncated`, stratify further by discrete $M$ when counts permit.

Breaches ⇒ **RUN-scoped** corridor failure (`E/1A/S4/CORRIDOR/...`).

---

## 5) Formal validator procedure (reference)

For each `{seed, parameter_hash, run_id}`:

1. **Branch coherence** (as in §2).
2. **Recompute $\lambda_m$** using S4.2 **with the same clamp**; if non-finite/≤0 and **any** S4 rows exist ⇒ `ABORT_RUN("E/1A/S4/NUMERIC/INCONSISTENT_ABORT")`.
3. **Schema & envelope** checks (I-ZTP4); enforce `context=="ztp"` on $P$.
4. **Lambda consistency**: in $P$, all `lambda` == $\lambda_m$ bit-exact; in $R\cup X$, all `lambda_extra` == $\lambda_m$ bit-exact; else `ABORT_RUN("E/1A/S4/PAYLOAD/LAMBDA_DRIFT")`.
5. **Counters**: draws advance; diagnostics don’t; `before` strictly increases with `attempt`; else `ABORT_RUN("E/1A/S4/COUNTER/VIOLATION")`.
6. **Coverage/signature**: enforce I-ZTP2/I-ZTP3; else `ABORT_RUN("E/1A/S4/COVERAGE/...")`.
7. **Bit-replay** (heavy): optional re-draw of Poisson(λ) along the S4 lane to reproduce `k`; mismatch ⇒ `ABORT_RUN("E/1A/S4/REPLAY/MISMATCH")`.
8. **Corridors**: compute metrics in §4 using governed thresholds; any breach ⇒ `ABORT_RUN("E/1A/S4/CORRIDOR/...")`.

---

## 6) Failure taxonomy (deterministic `err_code` → scope → action)

* **RUN-scoped (stop the run)**
  `E/1A/S4/SCHEMA/MISSING_ENVELOPE_FIELD`
  `E/1A/S4/SCHEMA/BAD_PARTITIONS`
  `E/1A/S4/CONTEXT/NOT_ZTP`
  `E/1A/S4/COUNTER/VIOLATION`
  `E/1A/S4/PAYLOAD/LAMBDA_DRIFT`
  `E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION`
  `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`
  `E/1A/S4/NUMERIC/INCONSISTENT_ABORT`
  `E/1A/S4/CORRIDOR/MEAN_REJECTIONS_EXCEEDED`
  `E/1A/S4/CORRIDOR/QUANTILE_EXCEEDED`
  `E/1A/S4/CORRIDOR/EXHAUSTION_RATE_DRIFT`

* **MERCHANT-scoped (skip merchant, continue run)**
  `E/1A/S4/RETRY/EXHAUSTED_64` (with downstream policy applied)
  `E/1A/S4/NUMERIC/NONFINITE_LAMBDA` (from S4.2; **no S4 rows** must exist)

All error records must include the **full envelope** and natural keys to enable byte-level triage.

---

## 7) Outputs of S4.6

* **Validation artefacts** added to the **1A validation bundle**: per-merchant verdicts (accepted $K_m$, exhausted, or aborted numeric), run-level corridor metrics and pass/fail, and a summary of any RUN-scoped failures. The bundle hash contributes to the 1A `_passed.flag`.
* **No new event rows** are written by S4.6 beyond structured diagnostics; the three S4 streams remain the only persisted logs for this state.

---

## 8) Why these invariants suffice

* I-ZTP1/4 guarantee **bit-replay** (same inputs ⇒ same `k` sequence, same counters), and envelope/partition integrity.
* I-ZTP2/3 make acceptance/exhaustion **finite and unambiguous** (unique 64/64/1 signature).
* Mode-aware corridors catch **distributional drift** even if rows pass schema checks.
* I-ZTP6/7 enforce cross-state branch coherence and **exactly-once** semantics for the logs.

---

# S4.7 — Failure taxonomy & scopes

## 1) Purpose & authority

S4.7 makes failure handling **deterministic and auditable**. It classifies failures, prescribes **what appears in logs** (or must not), defines **scope → action**, and binds everything to the dataset dictionary paths, envelopes, and invariants already locked. The run’s **validation bundle** must record outcomes (including the exhaustion policy applied).

---

## 2) Inputs & shared knobs

* **Per-merchant inputs:** eligibility $e_m$, $N_m$, openness $X_m$, $\theta$, and the **clamped** $\lambda_{\text{extra},m}$ from S4.2; S4.5 attempt logs (`poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`).
* **Governed policy:** `crossborder_hyperparams.ztp_on_exhaustion_policy ∈ {"abort","downgrade_domestic"}` (default `"abort"`). Policy only changes **post-exhaustion routing**; the diagnostic signature is identical.
* **Governed validation knobs (normative names):**
  `validation.s4.mean_rejections_max` (default **0.05**),
  `validation.s4.retry_p999_max` (default **3**),
  `validation.s4.exhaustion_abs_tol`, `validation.s4.exhaustion_rel_tol`,
  `validation.s4.num_lambda_bins` (default **10**).

---

## 3) Deterministic error identifiers (normative)

Emit stable, grep-friendly codes in diagnostics and the validation bundle:

```
err_code := "E/1A/S4/<CLASS>/<DETAIL>"
```

Examples used below (canonical):
`E/1A/S4/NUMERIC/NONFINITE_LAMBDA`, `E/1A/S4/NUMERIC/INCONSISTENT_ABORT`,
`E/1A/S4/RETRY/EXHAUSTED_64`,
`E/1A/S4/SCHEMA/MISSING_ENVELOPE_FIELD`, `E/1A/S4/SCHEMA/BAD_PARTITIONS`, `E/1A/S4/SCHEMA/MALFORMED_EVENT`,
`E/1A/S4/CONTEXT/NOT_ZTP`,
`E/1A/S4/COUNTER/VIOLATION`,
`E/1A/S4/PAYLOAD/LAMBDA_DRIFT`,
`E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION`, `E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION`,
`E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`,
`E/1A/S4/CORRIDOR/MEAN_REJECTIONS_EXCEEDED`, `E/1A/S4/CORRIDOR/QUANTILE_EXCEEDED`, `E/1A/S4/CORRIDOR/EXHAUSTION_RATE_DRIFT`.

**Every diagnostic record in the bundle must include:**
`{err_code, merchant_id?, context_if_applicable, lambda? (clamped), attempt? (if applicable), rng_counter_before_*, rng_counter_after_*, partition_path}`.

> **Context field (normative):** where applicable, include the **observed** `context` value; `poisson_component` **must** be `"ztp"` (exact casing).

---

## 4) Failure classes (canonical table)

| Class (err_code)                                                         | Condition (precise)                                                                                                                                    | What appears in logs (rows)                                                                                                                                                            | Scope        | Action                                                                                                                                                                |
| ------------------------------------------------------------------------- |--------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Numeric policy** (`E/1A/S4/NUMERIC/NONFINITE_LAMBDA`)                   | In S4.2, $\lambda_{\text{extra},m}$ after clamp is `!isfinite` **or** $\le 0$.                                                                         | **No S4 rows** at all for $m$.                                                                                                                                                         | **Merchant** | Abort merchant; S5–S6 not entered.                                                                                                                                    |
| **Inconsistent numeric abort** (`E/1A/S4/NUMERIC/INCONSISTENT_ABORT`)     | $\lambda$ would force numeric abort, **but** S4 rows exist for $m$.                                                                                    | As observed (invalid).                                                                                                                                                                 | **Run**      | Abort run.                                                                                                                                                            |
| **Retry exhaustion** (`E/1A/S4/RETRY/EXHAUSTED_64`)                       | S4.5 sees **64 consecutive zeros**.                                                                                                                    | Exactly **64** `poisson_component(k=0)`, **64** `ztp_rejection(attempt=1..64)`, and **one** `ztp_retry_exhausted{attempts=64,aborted=true}` (diagnostics **do not** advance counters). | **Merchant** | Apply governed policy: `"abort"` → drop merchant; `"downgrade_domestic"` → set $K_m:=0$ and **route to S6 with $K^{\star}=0$** (S6 persists home-only `country_set`). |
| **Schema/partition** (`E/1A/S4/SCHEMA/*`)                                 | Any S4 row missing envelope keys; wrong schema types; partitions not exactly `{seed, parameter_hash, run_id}`; missing required payload fields.        | N/A (invalid).                                                                                                                                                                         | **Run**      | Abort run.                                                                                                                                                            |
| **Context contamination** (`E/1A/S4/CONTEXT/NOT_ZTP`)                     | Any S4 `poisson_component` row has `context ∉ {"ztp"}` (case-sensitive).                                                                               | As observed (invalid context).                                                                                                                                                         | **Run**      | Abort run.                                                                                                                                                            |
| **Counter discipline** (`E/1A/S4/COUNTER/VIOLATION`)                      | Draws don’t advance counters **or** diagnostics advance; per-merchant `before` not strictly increasing.                                                | As observed.                                                                                                                                                                           | **Run**      | Abort run.                                                                                                                                                            |
| **Lambda drift** (`E/1A/S4/PAYLOAD/LAMBDA_DRIFT`)                         | In $P$, `lambda` not **bit-equal** across attempts **or** not equal to recomputed, **clamped** $\lambda$ from S4.2; in $R/X$, `lambda_extra` mismatch. | As observed.                                                                                                                                                                           | **Run**      | Abort run.                                                                                                                                                            |
| **Coverage missing** (`E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION`)    | Eligible merchant has S4 rows but neither an **accepted** signature nor the **64/64/1** exhaustion signature.                                          | Inconsistent mix (e.g., missing rejections).                                                                                                                                           | **Run**      | Abort run.                                                                                                                                                            |
| **Exhaustion inconsistency** (`E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION`) | `ztp_retry_exhausted` present but **any** of: `X.attempts ≠ 64` **or** (`P ≠ 64`**or** any `P.k ≠ 0` **or** (`R ≠ 64` **or** `R.attempts ≠ 1..64`)     | As observed.                                                                                                                                                                           | **Run**      | Abort run.                                                                                                                                                            |
| **Branch incoherence** (`E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`)           | $e_m=0$ but any S4 event exists for $m$.                                                                                                               | As observed (should be empty).                                                                                                                                                         | **Run**      | Abort run.                                                                                                                                                            |
| **Corridor breach** (`E/1A/S4/CORRIDOR/*`)                                | Cohort diagnostics from S4.6 (mean rejections, $p_{99.9}$, exhaustion rate) violate governed thresholds.                                               | As observed; rows themselves are valid.                                                                                                                                                | **Run**      | Abort run (CI).                                                                                                                                                       |

---

## 5) Emission policy per failure (no half-measures)

* **Numeric policy error:** **no S4 rows** may exist for $m$. Presence ⇒ `E/1A/S4/NUMERIC/INCONSISTENT_ABORT` (run-scoped).
* **Retry exhaustion:** the **exact 64/64/1** triple **must** appear; draws consume RNG, diagnostics do **not**. Downstream action per governed policy, but the **trace is identical**.
* **Schema/lineage/context/counter/coverage:** these are **run-scoped**; treat as **fatal** regardless of attempt content.

---

## 6) Validator detection order (deterministic)

Within `{seed, parameter_hash, run_id}`:

1. **Branch gate:** if $e_m=0$ then assert **no S4 rows** → else `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`.
2. **Recompute $\lambda$:** apply S4.2 **with clamp**. If non-finite/≤0 then assert **no S4 rows** → else `E/1A/S4/NUMERIC/INCONSISTENT_ABORT`.
3. **Schema/partitions & context:** envelope completeness; partitions exact; `context=="ztp"`. Violations → `E/1A/S4/SCHEMA/*` / `…/CONTEXT/NOT_ZTP`.
4. **Counters:** draws advance; diagnostics don’t; `before` strictly increases. Else `E/1A/S4/COUNTER/VIOLATION`.
5. **Lambda constancy:** `lambda` / `lambda_extra` **bit-equal** to recomputed $\lambda$. Else `E/1A/S4/PAYLOAD/LAMBDA_DRIFT`.
6. **Coverage/signature:** accept or **64/64/1** exactly. Else `E/1A/S4/COVERAGE/*`.
7. **Corridors:** compute per S4.6; breach → `E/1A/S4/CORRIDOR/*`.

**Envelope keys required (explicit list):**
`ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, merchant_id`.

---

## 7) Recording outcomes (validation bundle)

* **Per-merchant verdict:**
  `{merchant_id, status ∈ {accepted, exhausted, numeric_abort}, K_m? (if accepted), lambda, attempts, policy_applied? ("abort"|"downgrade_domestic" if exhausted), err_code?}`.
  *Include `context` where relevant; for `poisson_component` this must be `"ztp"`.*

* **Run summary:** corridor metrics, exhaustion counts, and any **RUN-scoped** failures (with counts by `err_code`).

* The bundle hash contributes to the 1A `_passed.flag`.

---

## 8) Idempotency & re-runs

* **Natural keys:** `poisson_component` → `(merchant_id, attempt, context="ztp")`; `ztp_rejection` → `(merchant_id, attempt)`; `ztp_retry_exhausted` → `(merchant_id)`. Duplicates ⇒ run-scoped schema violation.
* **Re-run determinism:** Given identical inputs and lineage, the **same failure class** and **identical artefact pattern** recur (e.g., numeric abort writes **no** rows; exhaustion re-emits the exact 64/64/1).

---

## 9) Worked edge cases (canonical outcomes)

* **Non-finite $\lambda$ but S4 rows found:** `E/1A/S4/NUMERIC/INCONSISTENT_ABORT` (run).
* **`ztp_retry_exhausted` present with <64 `ztp_rejection`:** `E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION` (run).
* **Eligible merchant with only `poisson_component(k=0)` and no diagnostics:** `E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION` (run).
* **Ineligible merchant (`e_m=0`) with any S4 row:** `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS` (run).
* **Counters advanced on `ztp_rejection`:** `E/1A/S4/COUNTER/VIOLATION` (run).

---

## 10) Why this taxonomy is sufficient

It aligns one-to-one with the locked S4 invariants, elevates **context**, **counters**, **coverage**, and **corridors** into first-class, mode-aware checks, and ties each failure to: **what is (or is not) in the logs**, **what the validator proves**, and **what downstream must do**. There are no “silent” failures: every path is either **merchant-scoped** with a deterministic trace (or none), or **run-scoped** and stops CI immediately.

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

> **Truncation mode (governed):** `s4.truncation_mode = "late_cap"` (baseline). S4 samples ZTP on $\{1,2,\dots\}$; **S6** later applies $K_m^\star=\min(K_m,M_m)$. See the **bias note** in §3.

---

## 2) Per-merchant outcomes (exhaustive)

### A) **Eligible & accepted** (no 64-cap)

S4 exposes the *scalar* $K_m\ge 1$ to S5/S6 (in memory), and leaves an attempt trace in the logs:

* `poisson_component` (consuming): attempts $1…a^*$, with last `k≥1`, `context="ztp"`, constant `lambda = λ_{extra,m} > 0`.
* `ztp_rejection` (non-consuming): attempts $1…a^*-1$ (one per zero).
* **No** `ztp_retry_exhausted`.

Validation uses these to prove I-ZTP2/3/4 and bit-replay.

### B) **Eligible but exhausted** (64 zeros)

Emit the exact **64/64/1** signature and **do not** expose $K_m$:

* 64 `poisson_component` rows with `k=0`,
* 64 `ztp_rejection` rows (`attempt=1..64`),
* 1 `ztp_retry_exhausted{attempts=64,aborted=true}` (non-consuming).

**Downstream routing (governed):**

* `"abort"` → merchant dropped; S5–S7 do not run for $m$.
* `"downgrade_domestic"` → set $K_m:=0$ and **route to S6 with $K_m^\star=0$** so that **S6** persists the **home-only** `country_set`. S7 must **not** synthesise `country_set` ad hoc.

The diagnostic trace is identical under either policy.

### C) **Ineligible** ($e_m=0$)

S4 emits **no** events; $K_m$ is already fixed to **0** by S3 and the merchant **bypasses S4–S6**. Any S4 event here is a branch-coherence failure (see S4.7).

---

## 3) What S4 **hands off** to S5–S6 (and what it doesn’t)

### Scalar interface

* If **A** (accepted): S4 provides $K_m$ in memory only. S5/S6 may assume $K_m\in\mathbb{Z}_{\ge1}$ but **must not** persist it; `country_set` remains the only authority later (S6).
* If **B** (exhausted) and policy is `"downgrade_domestic"`: **route to S6 with $K_m^\star=0$** so **S6** writes the home-only `country_set`. If policy is `"abort"`, skip S5–S7 for that merchant altogether.
* If **C** (ineligible): $K_m:=0$ from S3; no S4 events; the domestic-only path is handled outside S4/S6 per the combined flow.

### Downstream “size” contracts (how $K_m$ is consumed)

* **S6 pre-screen/cap (late-cap mode):**

  $$
  M_m=\bigl|\mathcal{D}(\kappa_m)\setminus\{\text{home}\}\bigr|,\qquad K_m^\star=\min(K_m,M_m).
  $$

  If $M_m=0$, S6 persists only the home row and emits **no** `gumbel_key` (reason `"no_candidates"`). If $M_m < K_m$, it proceeds with $K_m^\star$.

> **Bias note (late-cap vs right-truncated).** Because $K_m^\star$ is applied **after** sampling, the realised law differs from the right-truncated ZTP on $\{1,\dots,M_m\}$ when $M_m$ is small. This is **intentional** and should be reflected in S9’s corridors (which use $p_{\text{acc}}=1-e^{-\lambda}$).

---

## 4) Authoritative event streams (paths, partitions, schema refs)

S4 persists **only** these streams (JSONL, partitioned by `{seed, parameter_hash, run_id}`), pinned in the dataset dictionary:

| Stream                | Path prefix                               | Schema ref                                            | Produced by               |
| --------------------- | ----------------------------------------- | ----------------------------------------------------- | ------------------------- |
| `poisson_component`   | `logs/rng/events/poisson_component/...`   | `schemas.layer1.yaml#/rng/events/poisson_component`   | `1A.nb_poisson_component` |
| `ztp_rejection`       | `logs/rng/events/ztp_rejection/...`       | `schemas.layer1.yaml#/rng/events/ztp_rejection`       | `1A.ztp_sampler`          |
| `ztp_retry_exhausted` | `logs/rng/events/ztp_retry_exhausted/...` | `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` | `1A.ztp_sampler`          |

All rows **must** carry the RNG envelope
`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, merchant_id }`
and follow S4’s context/counter rules (draws consume; diagnostics don’t). *(Reminder: `manifest_fingerprint` is in the envelope for audit; it is **not** a partition key.)*

---

## 5) Cardinalities & payload invariants (downstream can rely on)

* **Attempt trace completeness:** Eligible merchants end in **acceptance** (last `k≥1`) or **exhaustion** (exact 64/64/1). Missing/extra rows are structural failures.
* **Lambda constancy:** In `poisson_component`, `lambda` is **bit-identical** across attempts and equals the recomputed $\lambda_{\text{extra},m}$ from S4.2 (after clamp). In diagnostics, `lambda_extra` is **bit-equal** to that same value.
* **Context discipline:** `poisson_component.context == "ztp"` (closed, case-sensitive enum).
* **Partitions are fixed:** all three streams are **exactly** partitioned by `{seed, parameter_hash, run_id}` as pinned in the dictionary.

---

## 6) How S6 turns $K_m$ into persisted order (for awareness)

S6 reads $K_m$ (effective $K_m^\star$), draws **one** uniform per candidate to form Gumbel keys, logs `gumbel_key`, selects the top $K_m^\star$, and then **persists** the authoritative `country_set` rows: rank 0 = home, ranks $1..K_m^\star$ = selected foreign ISOs in Gumbel order. Any mismatch between these ranks and `gumbel_key.selection_order` is a validation failure.

---

## 7) Validator hooks tied to this boundary

S9 (validation) consumes S4’s streams to assert:

* **I-ZTP2/3/4:** coverage (accept vs 64/64/1), attempt indexing, schema/envelope/counter discipline.
* **I-ZTP1:** deterministic bit-replay of each attempt sequence and accepted $K_m$ under fixed lineage.
* **I-ZTP5:** population corridors (mean rejections ≤ governed threshold; $p_{99.9}$ ≤ governed threshold); breaches are run-scoped.

No new datasets are written by S4 for validation; all checks run **over the three S4 logs**.

---

## 8) Minimal boundary algorithm (normative; read → decide → expose)

```
INPUT:
  e_m ∈ {0,1} (from S3), grouped S4 logs per merchant m
OUTPUT:
  Either: expose scalar K_m≥1 to S5/S6; or mark merchant as exhausted/aborted; or skip (e_m=0)

if e_m = 0:
    assert no S4 logs exist for m                       # branch coherence (S3)
    # downstream sees K_m := 0 from S3; bypasses S4–S6 per combined flow
    RETURN

P ← poisson_component(context="ztp") rows for m, ordered by attempt
R ← ztp_rejection rows for m, ordered by attempt
X ← ztp_retry_exhausted row for m (0 or 1)

assert partitions == {seed, parameter_hash, run_id} (dictionary)
assert lambda(P) is bit-constant and > 0
if X exists:
    assert |P|=64 and |R|=64 and all P.k=0             # exhaustion signature
    # downstream: apply governed policy
    #  - abort: drop merchant
    #  - downgrade: forward to S6 with K_m^* := 0 (S6 persists home-only country_set)
    RETURN
else:
    assert |P|≥1 and last(P).k ≥ 1 and all prior P.k = 0
    assert attempts(R) = {1..|P|-1}
    EXPOSE K_m := last(P).k to S5/S6                   # (in memory only)
    RETURN
```

---

## 9) Idempotency & determinism (re-runs)

Re-running the same `{seed, parameter_hash, manifest_fingerprint}` and inputs yields the **same** attempt trace and the **same** outcome class (accept with the same $K_m$, or the identical 64/64/1 exhaustion). S4 **never** mutates S2/S3 results or any allocation tables; it only gates entry to S5–S6.

---

## 10) Cross-state consistency reminders

* S4 owns **only** the sampling/logging for foreign-country *count*; **S6** owns `country_set` persistence for merchants that reach it (including **downgrade via S4 exhaustion** with $K_m^\star=0$).
* Ineligible merchants ($e_m=0$) follow the **domestic-only** path outside S4/S6 per the combined flow.

---

### One-line summary

**Accepted:** expose $K_m\ge1$ (in memory) + attempt logs.
**Exhausted:** emit 64/64/1; no $K_m$; **route via S6** on downgrade.
**Ineligible:** no S4 logs; $K_m:=0$ from S3.
No other outputs originate in S4.

---

# S4.9 — Validation bundle math, CI gates, and test vectors

## 1) Purpose

Specify *exactly* how the validator proves S4 correctness from the three S4 streams, computes **gates** (corridors), and writes the **validation bundle**. All arithmetic is IEEE-754 **binary64**; use `expm1`/`log1p` where noted; **no FMA**.

**Authoritative inputs**

* Streams (JSONL; partitions `{seed, parameter_hash, run_id}`; S4.4 schema + envelope):
  `logs/rng/events/poisson_component` (S4 rows have `context="ztp"`),
  `logs/rng/events/ztp_rejection`,
  `logs/rng/events/ztp_retry_exhausted`.
* Deterministic tables: S2’s $N_m$; S3’s $e_m$; parameter-scoped `crossborder_features` (openness `X_m`); `crossborder_hyperparams.yaml` ($\theta_0,\theta_1,\theta_2$, `s4.truncation_mode`, `ztp_on_exhaustion_policy`, and **numeric policy** `lambda_min`, `lambda_max`).
* (Only if `s4.truncation_mode="right_truncated"`) S5’s `candidate_count` table: $M_m$.

---

## 2) Deterministic reconstruction (per merchant)

Recompute with **the same policy as S4.2** (including clamps):

1. **Branch coherence.** If $e_m=0$: assert **no** S4 rows for $m$. Any presence ⇒ **RUN**: `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`.

2. **Recompute $\lambda_m$** (binary64):

   * Guard: $\theta_1\in(0,1)$ (governed). If violated ⇒ **RUN**: `E/1A/S4/CONFIG/GOVERNANCE_VIOLATION`.
   * Clamp feature: $X_m \leftarrow \min(\max(X_m,0),1)$. Missing `X_m` ⇒ **RUN**: `E/1A/S4/CONFIG/FEATURES_MISSING`.
   * $\eta_m=\theta_0+\theta_1\log N_m+\theta_2 X_m$; $\lambda^{\text{raw}}=\exp(\eta_m)$.
   * Clamp: $\lambda_m=\min(\max(\lambda^{\text{raw}},\lambda_{\min}),\lambda_{\max})$. (If knobs absent: $\lambda_{\min}=0$, $\lambda_{\max}=+\infty$.)
   * If $\lambda_m$ non-finite or $\le0$: this *must* have triggered an S4.2 numeric abort ⇒ **RUN** if any S4 rows exist: `E/1A/S4/NUMERIC/INCONSISTENT_ABORT`; else record merchant-scoped `E/1A/S4/NUMERIC/NONFINITE_LAMBDA` and skip $m$.

3. **Group & order rows.**
   $P$: `poisson_component` for $m$ with `context="ztp"`; sort by `attempt`.
   $R$: `ztp_rejection` for $m$; sort by `attempt`.
   $X$: `ztp_retry_exhausted` for $m$ (0/1 row).

4. **Envelope/schema/counters** (S4.4 hard rules).

   * Envelope keys present (exact list):
     `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, merchant_id`.
   * Partitions match dictionary.
   * `context=="ztp"` in all $P$.
   * **Counters**: draws advance (`after>before`); diagnostics don’t (`after==before`); per-merchant `before` strictly increases.
     Violations ⇒ **RUN** with the matching code (`…/SCHEMA/*`, `…/CONTEXT/NOT_ZTP`, `…/COUNTER/VIOLATION`).

5. **Lambda constancy (bit-equality).**
   All `P.lambda == λ_m` (bit-for-bit) and all `R/X.lambda_extra == λ_m`. Else ⇒ **RUN**: `E/1A/S4/PAYLOAD/LAMBDA_DRIFT`.

6. **Coverage signature (mutually exclusive).**

   * **Accepted**: $|P|\ge1$, last `k≥1`, all prior `k=0`; and $|R|=|P|-1$ with `attempt=1..|R|`; no $X$.
   * **Exhausted**: $|P|=64=|R|$, all `P.k=0`, $X$ exists with `attempts=64`.
     Otherwise ⇒ **RUN**: `E/1A/S4/COVERAGE/*`.

7. **Record per-merchant** (logical row):
   `{merchant_id, status ∈ {accepted, exhausted, numeric_abort}, K? (accepted only), attempts, r_m, lambda, err_code?}`, plus lineage `{seed, parameter_hash, run_id}`.
   $r_m = |R|$ if accepted; $r_m=64$ if exhausted.

> **Optional heavy check (bit-replay).** If enabled, re-draw Poisson($\lambda_m$) on the `"poisson_component"` substream and assert each `k` and counter pair. Mismatch ⇒ **RUN**: `E/1A/S4/REPLAY/MISMATCH`.

---

## 3) Corridor math (population gates)

### 3.1 Acceptance math (mode-aware)

* **late_cap (default):** $p_{\text{acc}}(m)=1-e^{-\lambda_m}$.
* **right_truncated:** require $M_m$ (from S5). $p_{\text{acc}}^{(M)}(m)=F_Y(M_m;\lambda_m)-e^{-\lambda_m}$ (Poisson CDF). Use `right_truncated` corridors only if the governed mode is selected.

The number of zeroes before success $R_m$ is Geometric with parameter $p_{\text{acc}}$ (or $p_{\text{acc}}^{(M)}$), so

$$
\mathbb{E}[R_m]=\frac{1-p}{p},\qquad \Pr(R_m\ge L)=(1-p)^L.
$$

### 3.2 Run-level metrics and targets (deterministic)

* **Mean rejections (target):** $\mu_R^\star=\frac{1}{|\mathcal{M}|}\sum_m \frac{1-p_m}{p_m}$.
  **Estimator:** $\widehat{\mu}_R = \text{mean}(r_m)$.
* **High quantile of rejections (gate):** 99.9-th of the integer multiset $\{r_m\}$.
  **Definition (deterministic):** **Nearest-rank / Hyndman-Fan Type-1** with rank $r=\lceil 0.999\cdot n\rceil$ (1-based). No interpolation; ties handled naturally.
* **Exhaustion rate:** per bucket: target $(1-p)^{64}$, estimator = share with $r_m=64$.

### 3.3 Binning policy (normative)

Governed key: `validation.s4.binning_mode ∈ {"equal_frequency","fixed_edges"}`.

* **Default**: `"equal_frequency"` with `validation.s4.num_lambda_bins` (default **10**). Compute λ-quantiles once (Type-7, default in most libs) to form edges; **edges must be serialized into the bundle** to ensure replay.
* **`"fixed_edges"`**: use governed `validation.s4.lambda_bin_edges` (strictly increasing). Edges must be echoed in the bundle.

Per bin $B_j$:
$\bar\lambda_j=\frac{1}{|B_j|}\sum_{m\in B_j}\lambda_m$,
$\widehat{\mu}_{R,j}=\frac{1}{|B_j|}\sum_{m\in B_j}r_m$,
$\mu^\star_{R,j}=\frac{e^{-\bar\lambda_j}}{1-e^{-\bar\lambda_j}}$ (late_cap), or use $p_{\text{acc}}^{(M)}$ when mode is `right_truncated`.
Exhaustion $\widehat{\rho}_{64,j}$ vs $\rho^\star_{64,j}=(1-p_j)^{64}$.

### 3.4 Gates (governed thresholds)

* `validation.s4.mean_rejections_max` (default **0.05**).
* `validation.s4.retry_p999_max` (default **3**).
* Optional exhaust tolerances: `validation.s4.exhaustion_abs_tol`, `validation.s4.exhaustion_rel_tol`.

Breaches ⇒ **RUN**: `E/1A/S4/CORRIDOR/*`.

---

## 4) Validation bundle — schema (logical)

**Header**
`{ bundle_version: "1A.S4.v1", seed, parameter_hash, run_id, manifest_fingerprint, truncation_mode }`

**PerMerchant** (array)
`{ merchant_id, status, K, attempts, r_m, lambda, err_code?, e_m, ts_checked_utc }`

**RunSummary**

```
{
  n_eligible, n_accepted, n_exhausted,
  mean_rejections, p99_9_rejections,
  corridors_pass: bool, corridor_failures: [code...],
  gating_config: {
    mean_rejections_max, retry_p999_max,
    binning_mode, num_lambda_bins?, lambda_bin_edges?
  },
  bins: [
    { edge_lo, edge_hi, n, lambda_bar,
      mu_R_hat, mu_R_star, exhaust_rate_hat, exhaust_rate_star }
  ],
  exhaustion_policy: "abort"|"downgrade_domestic"
}
```

**Failures** (array, truncated with examples)
`{ err_code, count, examples: [{ merchant_id, attempt?, observed_context?, lambda?, rng_before_hi/lo, rng_after_hi/lo, path }] }`

*(Where the bundle is stored is up to S9; this section fixes **content and math**.)*

---

## 5) Reference validator (language-agnostic)

I kept your structure but made it **policy-complete** and deterministic (percentiles, binning, clamps). See below; it is drop-in runnable logic for any stack.

```text
ALGORITHM  S4_Validate_ZTP_Run

INPUTS:
  seed, parameter_hash, run_id
  P_stream, R_stream, X_stream  # S4 logs; partitioned {seed, parameter_hash, run_id}
  S2_outlet_count[N_m], S3_eligibility[e_m]
  CrossborderFeatures[X_m], CrossborderHyperparams[θ0,θ1,θ2, lambda_min?, lambda_max?, s4.truncation_mode, ztp_on_exhaustion_policy]
  (optional) CandidateCount[M_m]  # required if s4.truncation_mode == "right_truncated"
  validation config: MEAN_REJ_MAX, P999_REJ_MAX, binning_mode, num_lambda_bins?, lambda_bin_edges?, exhaustion tolerances
  option: ENABLE_BIT_REPLAY ∈ {true,false}

DEFS:
  clamp(x,lo,hi) := min(max(x,lo),hi)
  RecomputeLambda(m):
      x ← clamp(X_m, 0, 1)
      η ← θ0 + θ1 * log(N_m) + θ2 * x
      λ_raw ← exp(η)
      λ_min_eff ← max(lambda_min or 0, 0)
      λ_max_eff ← (lambda_max or +∞)
      return clamp(λ_raw, λ_min_eff, λ_max_eff)

PRECHECKS:
  - Paths/partitions equal dictionary; envelope keys present (exact list); types valid.
  - Reject any P row with context != "ztp" → FailRun(E/1A/S4/CONTEXT/NOT_ZTP).

GROUP:
  - P[m] := rows for m (context="ztp") sorted by attempt
  - R[m] := rows for m sorted by attempt
  - X[m] := 0/1 rows for m
  - Enforce natural-key uniqueness (P: (m,attempt,"ztp"); R: (m,attempt); X: (m))

FOR EACH merchant m:
  if e_m == 0:
      assert |P[m]|=|R[m]|=|X[m]|=0 else FailRun(E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS)
      continue
  assert 0 < θ1 < 1 else FailRun(E/1A/S4/CONFIG/GOVERNANCE_VIOLATION)
  λ ← RecomputeLambda(m)
  if not isfinite(λ) or λ ≤ 0:
      if |P|+|R|+|X| > 0: FailRun(E/1A/S4/NUMERIC/INCONSISTENT_ABORT)
      record numeric_abort; continue
  # Counters
  for p in P[m]: assert p.after > p.before
  assert strictly_increasing([p.before for p in P[m]])
  for r in R[m] and x in X[m]: assert after == before
  # Lambda constancy
  for p in P[m]: assert p.lambda bit-equals λ
  for r in R[m], x in X[m]: assert r.lambda_extra bit-equals λ
  # Indexing + coverage
  assert R[m].attempts == {1..|R[m]|}
  if X[m] exists:
      assert X[m].attempts == 64 and |P|=64 and |R|=64 and all p.k == 0
      record exhausted; r_m := 64
  else:
      assert |P|≥1; all p.k == 0 for attempts < |P|; last p.k ≥ 1
      assert |R| == |P| - 1
      record accepted; K := last(p).k; r_m := |R|

CORRIDORS:
  E := merchants with status in {accepted, exhausted}
  mean_rejections := mean(r_m over E)
  p999 := nearest-rank 0.999 of the multiset {r_m over E}
  # Binning per config (echo edges into bundle)
  if binning_mode == "equal_frequency": compute λ-quantile edges (Type-7); else use fixed edges
  per-bin: lambda_bar, mu_R_hat; targets via late_cap or right_truncated (if chosen)

GATES:
  failures := []
  if mean_rejections ≥ MEAN_REJ_MAX: failures += ["E/1A/S4/CORRIDOR/MEAN_REJ_OVER_LIMIT"]
  if p999 ≥ P999_REJ_MAX: failures += ["E/1A/S4/CORRIDOR/P999_REJ_OVER_LIMIT"]
  # optional: compare exhaust_rate_hat to (1-p)^64 within tolerances; add EXHAUSTION_RATE_DRIFT on breach

BUNDLE:
  Emit {Header, PerMerchant, RunSummary(bins, failures, gating_config, exhaustion_policy)}.
  corridors_pass := failures == [].
  Any FailRun ⇒ abort run with that err_code.
```

---

## 6) Deterministic query templates (SQL-ish)

Replace `:seed/:parameter_hash/:run_id` with literals; these assume normalized views over the JSONL.

```sql
-- S4 draws for this partition (S4-only via context filter)
WITH P AS (
  SELECT merchant_id, attempt, k, lambda, ts_utc,
         rng_counter_before_hi, rng_counter_before_lo,
         rng_counter_after_hi,  rng_counter_after_lo
  FROM logs_rng_events_poisson_component
  WHERE seed=:seed AND parameter_hash=:parameter_hash AND run_id=:run_id
    AND context = 'ztp'
),
R AS (
  SELECT merchant_id, attempt, k, lambda_extra AS lambda
  FROM logs_rng_events_ztp_rejection
  WHERE seed=:seed AND parameter_hash=:parameter_hash AND run_id=:run_id
),
X AS (
  SELECT merchant_id, attempts, aborted, lambda_extra AS lambda
  FROM logs_rng_events_ztp_retry_exhausted
  WHERE seed=:seed AND parameter_hash=:parameter_hash AND run_id=:run_id
)

-- Per-merchant coverage signature
SELECT m.merchant_id,
       COUNT(p.*) AS p_rows,
       SUM(CASE WHEN p.k=0 THEN 1 ELSE 0 END) AS zeros,
       MAX(CASE WHEN p.k>=1 THEN attempt ELSE NULL END) AS accept_at,
       COUNT(r.*) AS r_rows,
       MAX(x.attempts) AS exhausted_attempts
FROM merchants m
LEFT JOIN P p ON p.merchant_id=m.merchant_id
LEFT JOIN R r ON r.merchant_id=m.merchant_id
LEFT JOIN X x ON x.merchant_id=m.merchant_id
WHERE m.seed=:seed AND m.parameter_hash=:parameter_hash AND m.run_id=:run_id
GROUP BY 1;
```

*(Spark/Pandas versions follow the same grouping by `merchant_id`, sorting by `attempt`, with deterministic aggregations.)*

---

## 7) Test vectors (replay-stable)

All vectors assume `s4.truncation_mode="late_cap"` unless noted; counters may be any lexicographically increasing sequence that matches consume/no-consume rules.

* **A — moderate λ; quick accept**
  $N=10,\ X=0.6,\ \theta=(-0.05,0.5,0.3)$ → $\lambda≈3.317$.
  P: `(k,attempt)={(0,1),(2,2)}`, R:`{1}`, X:∅.
  Expect: accepted $K=2$, $r_m=1$. `poisson_component.lambda` constant ≡ recomputed $\lambda$.

* **B — small λ; several rejections**
  $N=2,\ X=0.1,\ \theta=(-2,0.5,0.4)$ → $\lambda≈0.199$.
  P:`{(0,1),(0,2),(0,3),(1,4)}`, R:`{1,2,3}`, X:∅.
  Expect: accepted $K=1$, $r_m=3$.

* **C — exhaustion signature**
  Choose $\lambda\le 0.01$.
  P:`(0,a)` for $a=1..64$; R:`{1..64}`; X:`attempts=64, aborted=true`.
  Expect: exhausted; downstream routed per policy; **exact 64/64/1**.

* **D — right-truncated sanity (only if mode switched)**
  Set `s4.truncation_mode="right_truncated"`, provide $M=2$, and $\lambda=5$.
  P attempts are accepted only when $1\le k\le 2$; X absent; $p_{\text{acc}}^{(M)} = F_Y(2;5)-e^{-5}$.
  *Validator must read $M$ and use $p_{\text{acc}}^{(M)}$ in bin targets.*

For each vector, enforce:

* `context="ztp"` in P,
* draws advance counters; diagnostics don’t,
* partitions match dictionary,
* `lambda` / `lambda_extra` **bit-equal** to recomputed (clamped) $\lambda$.

---

## 8) Edge-case matrix (validator behavior)

| Situation                                                          | Expectation               | Action                                                  |
|--------------------------------------------------------------------|---------------------------|---------------------------------------------------------|
| P rows exist, some `k=0` before accept, **no** matching R rows     | Coverage violated         | **RUN** `E/1A/S4/COVERAGE/MISSING_REJECTIONS`           |
| X present but (P≠64) or any `P.k≠0` or (R≠64`or`R.attempts≠1..64`) | Inconsistent exhaustion   | **RUN** `E/1A/S4/COVERAGE/INCONSISTENT_EXHAUSTION`      |
| Any S4 P row with `context!="ztp"`                                 | Context contamination     | **RUN** `E/1A/S4/CONTEXT/NOT_ZTP`                       |
| Diagnostics consume RNG or draws don’t                             | Counter discipline broken | **RUN** `E/1A/S4/COUNTER/VIOLATION`                     |
| `lambda` drift vs recompute or across attempts                     | Payload drift             | **RUN** `E/1A/S4/PAYLOAD/LAMBDA_DRIFT`                  |
| Eligible merchant has **no** S4 rows and no X                      | Missing activity          | **RUN** `E/1A/S4/COVERAGE/MISSING_ACCEPT_OR_EXHAUSTION` |
| Ineligible merchant has any S4 row                                 | Branch incoherence        | **RUN** `E/1A/S4/BRANCH/INELIGIBLE_HAS_EVENTS`          |
| Governance: θ₁∉(0,1)                                               | Config violation          | **RUN** `E/1A/S4/CONFIG/GOVERNANCE_VIOLATION`           |
| Missing `crossborder_features` row                                 | Config/data gap           | **RUN** `E/1A/S4/CONFIG/FEATURES_MISSING`               |

---

## 9) Complexity & resource budget

* **Rows/merchant:** accepted → $2a-1$; exhausted → **129**.
* **Time:** $O(\#\text{rows})$ ingest + $O(\#\text{merchants})$ checks.
* **Memory:** streaming per partition; $O(1)$ per active merchant window.

---

## 10) What S4.9 does **not** change

No new streams, no change to S4 RNG/event protocol. This only fixes **math, gates, and bundle content** so multiple implementations produce identical outcomes.

---

**One-liner:** S4.9 makes the validator fully **policy-aware**, **bit-replayable**, and **deterministic**—same clamps, same bins, same percentile, same error codes—so any conforming engine yields the exact same pass/fail and bundle bytes.
