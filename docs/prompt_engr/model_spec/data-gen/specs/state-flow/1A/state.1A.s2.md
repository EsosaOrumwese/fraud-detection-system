# S2 — domestic multi-site outlet count $N$ (Negative-Binomial via Poisson–Gamma), deterministic & auditable

## S2.1 inputs (from S0/S1 + artefacts)

for each merchant $m$ that left S1 with $\texttt{is_multi}(m)=1$, we require:

* **design vectors** (prepared in S0):

  $$
  \boxed{\,x^{(\mu)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m)\big]^\top\,},\quad
  \boxed{\,x^{(\phi)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \log g_c\big]^\top\,}.
  $$

  the NB **mean** excludes the GDP bucket; the **dispersion** includes $\log(\text{GDPpc})$ as a continuous term (positive slope at fit).

* **coefficient vectors** $\beta_\mu,\ \beta_\phi$ from the approved artefacts; S0 established parameter lineage via `parameter_hash`.

* **rng discipline & schemas**: philox $2{\times}64$-10 with the shared **rng envelope**; event streams and paths for:

  * `gamma_component` (NB mixture),
  * `poisson_component` (NB mixture),
  * `nb_final` (accepted NB result).
    paths/schema refs fixed by the dataset dictionary and `schemas.layer1.yaml`.

## S2.2 model parameterisation (NB2)

define the link functions

$$
\boxed{\,\mu_m=\exp(\beta_\mu^\top x^{(\mu)}_m) > 0\,},\qquad
\boxed{\,\phi_m=\exp(\beta_\phi^\top x^{(\phi)}_m) > 0\,}.
$$

this is the **NB2** (mean–dispersion) parameterisation with moments

$$
\mathbb{E}[N_m]=\mu_m,\qquad \operatorname{Var}[N_m]=\mu_m+\frac{\mu_m^2}{\phi_m}.
$$

equivalently (derivation-only, *not* persisted),
$r_m=\phi_m,\ p_m=\tfrac{\phi_m}{\phi_m+\mu_m}$.

**numeric guard.** evaluate the linear predictors in binary64; abort if $\mu_m\le 0$ or $\phi_m\le 0$ after exponentiation (non-finite or non-positive).

## S2.3 sampling theorem & construction (Poisson–Gamma mixture)

**theorem (composition).** let $G\sim\mathrm{Gamma}(\alpha=\phi_m,\ \text{scale}=1)$ and, conditional on $G$, $K\mid G\sim\mathrm{Poisson}(\lambda=(\mu_m/\phi_m)\,G)$. then $K\sim \mathrm{NB2}(\mu_m,\phi_m)$.

**construction (one attempt).**

1. **gamma step** (context=`"nb"`):

$$
G \sim \mathrm{Gamma}(\alpha=\phi_m,\ \text{scale}=1).
$$

log one record to `logs/rng/events/gamma_component/...` with the shared rng envelope and payload
$\{\texttt{merchant_id},\ \texttt{context}=\text{"nb"},\ \texttt{index}=0,\ \alpha=\phi_m,\ \texttt{gamma_value}=G\}$.
(schema requires `merchant_id, context, index, alpha, gamma_value`.)

2. **poisson step** (context=`"nb"`):

$$
\lambda := (\mu_m/\phi_m)\,G,\qquad K\sim\mathrm{Poisson}(\lambda).
$$

log one record to `logs/rng/events/poisson_component/...` with the rng envelope and payload
$\{\texttt{merchant_id},\ \texttt{context}=\text{"nb"},\ \lambda,\ k=K\}$.
(schema requires `merchant_id, context, lambda, k`.)

both events carry the **rng envelope** (`seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label`, `rng_counter_before_*`, `rng_counter_after_*`, …). open-interval uniforms $u\in(0,1)$ are implied by the `u01` primitive used inside samplers.

## S2.4 rejection rule (enforce multi-site: $N\ge 2$)

set $N_m\leftarrow K$. if $K\in\{0,1\}$ **reject** and resample using the same merchant’s sub-streams (counters advance deterministically). let $r_m$ be the count of rejections.

formally, with attempts $t=0,1,\dots$:

$$
\begin{aligned}
&G_t\sim\Gamma(\phi_m,1),\quad \lambda_t=(\mu_m/\phi_m)G_t,\quad K_t\sim\mathrm{Poisson}(\lambda_t),\\
&\text{if }K_t\ge 2:\ N_m=K_t,\ r_m=t\ \text{ and stop};\ \text{else continue}.
\end{aligned}
$$

**monitoring corridor (validation obligation):** overall NB rejection rate $\le 0.06$; p99 of per-merchant rejection counts $\le 3$; one-sided CUSUM gate against baseline. violations abort the run; metrics land in the validation bundle.

## S2.5 finalisation event

upon acceptance $N_m\ge 2$, emit exactly **one** `nb_final` record to

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

payload (per schema):

$$
\boxed{\,\{\texttt{merchant_id},\ \mu=\mu_m,\ \texttt{dispersion_k}=\phi_m,\ \texttt{n_outlets}=N_m,\ \texttt{nb_rejections}=r_m\}\,}.
$$

(schema requires `merchant_id, mu, dispersion_k, n_outlets, nb_rejections`.)

> **event coverage invariant.** for any merchant with `nb_final`, there must exist at least one preceding `gamma_component` and one `poisson_component` event (context=`"nb"`) with matching envelope keys; absence is a structural failure.

## S2.6 RNG substreams & consumption discipline

Substream labels:
- $\ell_\gamma=$ `"gamma_component"`
- $\ell_\pi=$ `"poisson_component"`

Each attempt **emits exactly one** `gamma_component` and **one** `poisson_component` record.  
`nb_final` appears **once** at acceptance.

Replay is proven by the envelope counters; counter state for each $(\ell,m)$ is derived from the keyed mapping of S0.3.3 and incremented locally for each uniform consumed. There is no additive stride; label→merchant→index fully determines the counter.
All uniforms consumed by the NB samplers (Gamma and Poisson) are drawn via the `u01` mapping in **S0.3.4** (open interval; one counter increment ⇒ one uniform).

## S2.7 determinism & correctness invariants

* **I-NB1 (bit replay).** for fixed $(x^{(\mu)}_m,x^{(\phi)}_m,\beta_\mu,\beta_\phi,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the event sequence $(G_t,K_t)_{t\ge 0}$ and the accepted pair $(N_m,r_m)$ are bit-identical across replays. (counter-based philox + fixed sub-stream labelling + fixed per-attempt event counts.)
* **I-NB2 (schema conformance).** each `gamma_component` row must include `merchant_id, context="nb", index=0, alpha=\phi_m, gamma_value`; each `poisson_component` row includes `merchant_id, context="nb", lambda, k`; `nb_final` includes `mu, dispersion_k, n_outlets, nb_rejections`.
* **I-NB3 (open-interval uniforms).** all uniforms in internal samplers satisfy $u\in(0,1)$ per `u01` (exclusive bounds).
* **I-NB4 (consumption discipline).** exactly two component events per attempt; zero or more attempts; one finalisation event. downstream counters must match the trace.

## S2.8 failure modes (abort semantics)

* **non-finite / non-positive parameters:** $\mu_m\le 0$ or $\phi_m\le 0$ after exponentiation.
* **schema violation:** any required rng envelope field missing; any event missing required payload fields; context not in {("nb"), …}.
* **corridor breach:** rejection corridor (overall or p99) violated; abort and write metrics to the validation bundle.

## S2.9 outputs (state boundary)

for each merchant $m$ with $\texttt{is_multi}(m)=1$, S2 produces:

* **authoritative rng event streams** (partitioned by `{seed, parameter_hash, run_id}`):

  * `logs/rng/events/gamma_component/...` (≥1 row), schema `#/rng/events/gamma_component`;
  * `logs/rng/events/poisson_component/...` (≥1 row), schema `#/rng/events/poisson_component`;
  * `logs/rng/events/nb_final/...` (exactly 1 row), schema `#/rng/events/nb_final`.

* **in-memory state handed to S3+:** the accepted domestic outlet count

  $$
  \boxed{\,N_m\in\{2,3,\dots\}\,}
  $$

  together with the rejection count $r_m$ for diagnostics.

---