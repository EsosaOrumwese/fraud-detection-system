# S4 — Foreign-country count $K$ via zero-truncated Poisson (ZTP), deterministic & auditable

## S4.1 Universe, symbols, authority

* **Domain.** This state is evaluated **only** for merchants $m$ that:

  * were classified **multi-site** in S1, and
  * are **eligible for cross-border** per S3 ($e_m{=}1$).
    (Ineligible merchants skip S4–S6 and keep $K_m{:=}0$.)
* **Inputs (per $m$).**

  * $N_m$ from S2 (only if multi-site), eligibility flags from S3.
  * Hyperparameters $\theta=(\theta_0,\theta_1,\theta_2)$ from `crossborder_hyperparams.yaml` (Wald stats recorded).
  * Openness scalar $X_m \in [0,1]$ from `crossborder_features` (parameter-scoped), keyed by `merchant_id`.
  * RNG lineage from S0: `seed`, `parameter_hash`, `manifest_fingerprint`; events use the shared RNG envelope.
* **Authoritative schemas & event streams.**

  * `poisson_component` (context ∈ {`"nb"`, `"ztp"`}) for raw Poisson draws.
  * `ztp_rejection` for zero draws (attempt index 1..64).
  * `ztp_retry_exhausted` for the hard cap at 64 rejections.
    Dataset dictionary pins paths/partitions for all three streams.

* Don't know where to put this but here it is:
  * **Sampler.** True ZTP via rejection from $\text{Poisson}(\lambda_\text{extra})$ (see **S0.3.7** for Poisson regimes) where $\lambda_\text{extra}=\exp(\theta_0+\theta_1\log N_m+\theta_2 X_m)$; cap 64 rejections then apply the configured branch policy.


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

1. Compute $\lambda := \lambda_{\text{extra},m} = \exp(\theta_0 + \theta_1 \log N_m + \theta_2 X_m)$.
2. **Attempt loop** for $a=1,2,\dots$:
   a) Draw $K_a \sim \mathrm{Poisson}(\lambda)$ **using the Poisson(λ) regimes in S0.3.7**, with sub-stream per S0.3.3 and open-interval uniforms per S0.3.4. Emit `poisson_component{..., context="ztp", attempt=a}`.  
   b) If $K_a = 0$: emit `ztp_rejection{..., attempt=a}` and continue.  
   c) If $K_a \ge 1$: accept $K_m \leftarrow K_a$ and stop.  
   d) If $a = 64$ and still $K_a = 0$: emit `ztp_retry_exhausted{...}` and proceed to **(e)**.
3. **(e) Exhaustion policy (governed).** Let `policy = crossborder_hyperparams.ztp_on_exhaustion_policy ∈ {"abort","downgrade_domestic"}` (default `"abort"`):
   * `"abort"`: **abort merchant** — emit no S5/S6/S7 artefacts for $m$.
   * `"downgrade_domestic"`: set $K_m := 0$ and **skip S5–S6**. Proceed directly to S7 with $\mathcal{C}_m = \{\text{home}\}$ and `reason="ztp_exhausted"`.
   Record the effective action in `validation_bundle_1A`. No schema changes are required.

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

* **In-memory state to next steps:**
  * **Normal** (no exhaustion): 
    $$\boxed{\,K_m \in \{1,2,\dots\}\,} \quad \text{(foreign-country count)} \quad \rightarrow \text{S5/S6}.$$
  * **Exhaustion with `policy="downgrade_domestic"`:** set $K_m := 0$ and **skip S5–S6**; proceed to S7 with $\mathcal{C}_m = \{\text{home}\}$. The reason `"ztp_exhausted"` is recorded in the validation bundle.
  * **Exhaustion with `policy="abort"`:** merchant is **aborted**; no S5/S6/S7 emission.

* **Authoritative event streams (partitioned by `{seed, parameter_hash, run_id}`):**
  * `logs/rng/events/poisson_component/...` (≥1 row, `context="ztp"`).
  * `logs/rng/events/ztp_rejection/...` (0..64 rows).
  * `logs/rng/events/ztp_retry_exhausted/...` (≤1 row; **emitted on exhaustion** regardless of policy).

For **ineligible** $e_m = 0$: S3 already fixed $K_m := 0$; S4 emits **no** ZTP events for such merchants.

---