# S1 — Hurdle decision (Bernoulli with logistic link), deterministic & auditable

## S1.1 Inputs (from S0 + artefacts)

For each merchant $m$ we require:

* **Design vector (hurdle):**

  $$
  \boxed{\ x_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \phi_{\mathrm{dev}}(b_m)\big]^\top\ }
  $$

  where $b_m\in\{1,\dots,5\}$ is the GDP-bucket derived from the pinned 2025-04-15 vintage and Jenks-5 mapping.

* **Coefficient vector (hurdle):** a single YAML vector $\beta$ that already contains coefficients for **all** predictors in $x_m$, including all five GDP-bucket dummies; it is loaded atomically from `hurdle_coefficients.yaml`.

* **Lineage & RNG envelope fields:** `parameter_hash`, `manifest_fingerprint`, `seed` (Philox 2×64-10), and initial pre-event counters (hi, lo). Event logs must include the shared RNG envelope (seed, manifest_fingerprint, parameter_hash, module, substream_label, pre/post counters).

* **Event stream contract:** hurdle events are written to

  ```
  logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
  ```

  with schema `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.

## S1.2 Probability map (logistic)

Define the logistic map $\sigma:\mathbb{R}\to(0,1)$ by

$$
\sigma(\eta)=\frac{1}{1+e^{-\eta}} .
$$

Compute the linear predictor and probability:

$$
\boxed{\ \eta_m=\beta^\top x_m,\qquad \pi_m=\sigma(\eta_m)\in(0,1)\ }.
$$

**Numerical guard (implementation obligation).** Evaluate $\sigma$ with the overflow-safe two-branch form:

$$
\sigma(\eta)=
\begin{cases}
\frac{1}{1+e^{-\eta}},& \eta\ge 0,\\[4pt]
\frac{e^{\eta}}{1+e^{\eta}},& \eta<0,
\end{cases}
$$

and (optionally) clamp only the *evaluation* at $|\eta|>40$ for stability—values logged should remain the unclamped $\eta_m$. The narrative confirms the single-YAML provenance for $\beta$ and the predictor set.

## S1.3 RNG substream and Bernoulli trial

Let the **substream label** be
$$
\ell := \text{"hurdle_bernoulli"}.
$$

The keyed substream mapping of S0.3.3 is used to derive the Philox 2×64 counter state for $(\ell,m)$. Advance the **local index** for $(\ell,m)$ by one for each uniform consumed; the RNG envelope records pre/post counters.

Draw **one** uniform deviate on the open interval (exclusive bounds by schema):

$$
u_m \sim U(0,1) \quad\text{via `u01` (S0.3.4)}.
$$

The outcome is
$$
\text{is_multi}(m) = \mathbf{1}\{u_m < \pi_m\}.
$$

**Consumption discipline**
- If $0 < \pi_m < 1$: consume exactly one uniform.
- If $\pi_m \in \{0,1\}$: consume zero uniforms (deterministic outcome); still emit a trace with `draws=0` in `rng_trace_log`. In this case the `u` field in the hurdle event is `null` and `deterministic=true` per schema.

## S1.4 Event emission (authoritative schema + optional context)

For each merchant, emit **one** record to the hurdle event stream with the shared RNG envelope and the payload required by the schema:

$$
\boxed{\ \texttt{payload}=\{\ \texttt{merchant_id},\ \texttt{pi}=\pi_m,\ \texttt{u}=u_m,\ \texttt{is_multi}=\mathbf{1}\{u_m<\pi_m\}\ \}\ }.
$$

Optional (good practice) context fields permitted by schema: `gdp_bucket_id=b_m`, `mcc`, `channel`. **Do not** duplicate the sub-stream stride inside this record; replay is proven by the envelope counters and (separately) by trace logs. Path and schema are fixed by the dataset dictionary and `schemas.layer1.yaml`.

## S1.5 Determinism & correctness invariants

* **I-H1 (bit‑replay).** For fixed $(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the tuple $(u_m,\text{is_multi}(m))$ and the envelope counters are **bit‑identical** across replays. (Counter‑based Philox + **keyed substream mapping** + fixed draw budget per branch.)
* **I-H2 (consumption).** Draw accounting follows **S0.3.6**: the hurdle consumes **1** uniform iff $0<\pi_m<1$, else **0**. An `rng_trace_log` row must record the `draws` for this substream.
* **I-H3 (schema conformance).** The hurdle record must contain the envelope fields and **payload keys** `merchant_id`, `pi`, `is_multi`, and `u` which is **either** in $(0,1)$ when $0<\pi_m<1$ with `deterministic=false`, **or** `null` when $\pi_m\in\{0,1\}$ with `deterministic=true`. Any omission violates `schemas.layer1.yaml`.
* **I-H4 (branch purity).** No downstream state may override the hurdle decision. Validation enforces that merchants producing NB/ZTP/Dirichlet/Gumbel events **must** have a prior hurdle record with `is_multi=true`. (The dataset dictionary ties event paths to validation.)

## S1.6 Failure modes (abort semantics)

* **Design/coefficients mismatch:** shape or column order drift when forming $\eta_m=\beta^\top x_m$ → abort. (Registry & schema tie the design matrix and hurdle coefficients.)
* **Numeric invalid:** non-finite $\eta_m$ or $\pi_m$ after safe evaluation → abort.
* **Logging gap:** any merchant that later has NB/ZTP/Dirichlet/Gumbel events without a preceding hurdle event with `is_multi=true` → validation failure. (Per dictionary, hurdle is the first RNG event stream.)

## S1.7 Outputs of S1 (state boundary)

For each $m$, S1 emits:

* **Event stream (authoritative):**

  $$
  \texttt{logs/rng/events/hurdle_bernoulli/…},\quad
  \text{schema } \#/\text{rng/events/hurdle_bernoulli}.
  $$

  Payload includes `pi`, `u`, `is_multi`, with the required RNG envelope.

* **Branching state handed to S2+ (in-memory):**

  $$
  \boxed{\ \text{if } \text{is_multi}(m)=0:\ N_m\leftarrow 1,\ K_m\leftarrow 0,\ \mathcal{C}_m\leftarrow\{\text{home}\}\ \ (\text{skip S2–S6}\to\text{S7})\ }
  $$

  $$
  \boxed{\ \text{if } \text{is_multi}(m)=1:\ \text{proceed to S2 (NB for }N_m)\ }.
  $$

* **Optional diagnostic dataset (parameter-scoped):**

  $$
  \texttt{data/layer1/1A/hurdle_pi_probs/parameter_hash=\{parameter_hash\}/}
  $$

  keyed by `parameter_hash`, schema `#/model/hurdle_pi_probs`. (Diagnostic only; not used for the draw.)

---
