# S4 — Foreign-country count $K$ via zero-truncated Poisson (ZTP), deterministic & auditable

## S4.1 Universe, symbols, authority

* **Domain.** This state is evaluated **only** for merchants $m$ that:

  * were classified **multi-site** in S1, and
  * are **eligible for cross-border** per S3 ($e_m{=}1$).
    (Ineligible merchants skip S4–S6 and keep $K_m{:=}0$.)
* **Inputs (per $m$).**

  * $N_m\in\{2,3,\dots\}$: accepted domestic count from S2.
  * Hyperparameters $\theta=(\theta_0,\theta_1,\theta_2)$ and **openness** scalar $X_m$, from `crossborder_hyperparams.yaml`, keyed by $(\text{home_country},\text{MCC},\text{channel})$. Governance notes (Wald tests, drift gates) accompany $\theta$ in the YAML.
  * RNG lineage from S0: `seed`, `parameter_hash`, `manifest_fingerprint`; events use the shared RNG envelope.
* **Authoritative schemas & event streams.**

  * `poisson_component` (context ∈ {`"nb"`, `"ztp"`}) for raw Poisson draws.
  * `ztp_rejection` for zero draws (attempt index 1..64).
  * `ztp_retry_exhausted` for the hard cap at 64 rejections.
    Dataset dictionary pins paths/partitions for all three streams.

## S4.2 Link function and parameterisation

Define the linear predictor

$$
\eta_m \;=\; \theta_0 \;+\; \theta_1 \log N_m \;+\; \theta_2 X_m,\qquad 0<\theta_1<1,
$$

and the Poisson mean via a **log-link**

$$
\boxed{\ \lambda_{\text{extra},m} \;=\; \exp(\eta_m) \;>\; 0\ }.
$$

This replaces an earlier identity-link draft; positivity and model governance (Wald $p<10^{-5}$, quarterly drift gates) are recorded with the hyperparams.

**Numerical guard.** Compute $\eta_m$ and $\lambda_{\text{extra},m}$ in IEEE-754 binary64; if $\lambda_{\text{extra},m}$ is non-finite, treat as a **numeric policy error** (abort merchant).

## S4.3 Target distribution (ZTP)

Let $Y\sim\mathrm{Poisson}(\lambda)$, $K=Y\mid(Y\ge1)$. Then

$$
\Pr[K=k] \;=\; \frac{e^{-\lambda}\lambda^k}{k!\,\bigl(1-e^{-\lambda}\bigr)},\quad k=1,2,\dots,
$$

$$
\mathbb{E}[K]=\frac{\lambda}{1-e^{-\lambda}},\qquad
\mathrm{Var}[K]=\frac{\lambda+\lambda^2}{1-e^{-\lambda}}-\Big(\frac{\lambda}{1-e^{-\lambda}}\Big)^2.
$$

Rejection sampling from $\mathrm{Poisson}(\lambda)$ has acceptance probability $1-e^{-\lambda}$. (These facts guide corridor checks but are not logged themselves.)

## S4.4 RNG protocol (substreams, counters, schema)

**Substream label.** Use $\ell=$ `"poisson_component"` for every Poisson attempt in S4 with `context="ztp"`. The keyed mapping of S0.3.3 is used to derive the Philox counter state for $(\ell,m)$; increment the local index for each uniform consumed. Replay is proven via the envelope’s pre/post counters.

**Event contracts**
- `poisson_component`: required `{merchant_id, context="ztp", lambda, k}` + RNG envelope. `lambda` is $\lambda_{\text{extra},m}$; `k` is the raw (untruncated) Poisson draw.
- `ztp_rejection`: required `{merchant_id, lambda_extra, k=0, attempt}` + envelope.
- `ztp_retry_exhausted`: required `{merchant_id, lambda_extra, attempts=64, aborted=true}` + envelope.
**Draw accounting (S0.3.6).** `poisson_component`(context="ztp") has **variable** draw counts whose value is the envelope delta; `ztp_rejection` and `ztp_retry_exhausted` are **non‑consuming** (draws $=0$). Validators reconcile totals from the envelopes.

## S4.5 Sampling algorithm (formal)

For each eligible merchant $m$:

1. Compute $\lambda := \lambda_{\text{extra},m} = \exp(\theta_0+\theta_1\log N_m+\theta_2 X_m)$.
2. **Attempt loop** for $a=1,2,\dots$:
   a) Draw $K_a \sim \mathrm{Poisson}(\lambda)$ using substream $(\ell_\pi,m)$ via S0.3.3/S0.3.4. Emit `poisson_component{..., attempt=a}`.  
   b) If $K_a=0$: emit `ztp_rejection{..., attempt=a}` and continue.  
   c) If $K_a\ge 1$: accept $K_m\leftarrow K_a$ and stop.  
   d) If $a=64$ and still $K_a=0$: emit `ztp_retry_exhausted{...}` and abort this merchant.

All uniforms used by the Poisson sampler come from the keyed substream mapping and the open-interval `u01` primitive.

## S4.6 Determinism & correctness invariants

* **I-ZTP1 (bit-replay).** For fixed $(N_m,X_m,\boldsymbol\theta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the Poisson attempt sequence $(K_1,K_2,\dots)$ and the accepted $K_m$ are bit-identical across runs (counter-based Philox + fixed label + fixed attempt count semantics).
* **I-ZTP2 (event coverage).** If $K_m\ge1$: there must exist ≥1 `poisson_component` (context="ztp") and **zero or more** `ztp_rejection` events preceding acceptance; if the cap is hit, `ztp_retry_exhausted` **must** be present and the merchant aborted. Missing required events is a structural failure.
* **I-ZTP3 (attempt indexing).** `ztp_rejection.attempt` is strictly increasing from 1; max is 64. `ztp_retry_exhausted.attempts` is exactly 64.
* **I-ZTP4 (schema conformance).** Every event row carries the RNG envelope and the required payload fields/constraints (e.g., `k` integer, `lambda`$>0$).
* **I-ZTP5 (corridor checks).** The empirical mean of `ztp_rejection` counts per merchant < 0.05 and the empirical $p_{99.9}<3$; CI violations abort the run (recorded by validation).

## S4.7 Failure modes (abort semantics)

* **Numeric invalid.** $\lambda_{\text{extra},m}$ is non-finite or $\le 0$ after exponentiation → abort merchant (numeric policy).
* **Retry exhaustion.** 64 consecutive zeros → emit `ztp_retry_exhausted` and abort merchant.
* **Schema/lineage violation.** Any required RNG envelope field missing; wrong `context`; or missing `ztp_rejection`/`ztp_retry_exhausted` when implied by the attempt sequence. Paths/partitions must match the dictionary.

## S4.8 Outputs (state boundary)

For each **eligible** $m$:

* **In-memory state to S5/S6:**

  $$
  \boxed{\ K_m \in \{1,2,\dots\}\ } \quad\text{(foreign-country count)}
  $$
* **Authoritative event streams (partitioned by `{seed, parameter_hash, run_id}`):**

  * `logs/rng/events/poisson_component/...` (≥1 row, context="ztp").
  * `logs/rng/events/ztp_rejection/...` (0..64 rows).
  * `logs/rng/events/ztp_retry_exhausted/...` (≤1 row; only on abort).

For **ineligible** $e_m{=}0$: S3 already fixed $K_m{:=}0$; S4 emits **no** ZTP events for such merchants.

---