# S0 — Deterministic preparation of features, lineage and RNG

## S0.1 Universe, symbols, authority

* Seed merchants: a finite set $\mathcal{M}$. Each $m\in\mathcal{M}$ is a row of the normalised ingress table

  $$
  \texttt{merchant_ids} \subset \{(\texttt{merchant_id},\texttt{mcc},\texttt{channel},\texttt{home_country_iso})\},
  $$

  validated by `schemas.ingress.layer1.yaml#/merchant_ids`.&#x20;
* Canonical references (immutable for a run):

  * ISO-3166 country list $\mathcal{I}$ (alpha-2).&#x20;
  * GDP per-capita vintage $G:\mathcal{I}\to\mathbb{R}_{>0}$, pinned to **2025-04-15**.&#x20;
  * Jenks $K{=}5$ GDP bucket map $B:\mathcal{I}\to\{1,\dots,5\}$ (precomputed artefact).&#x20;
* Schema authority: authoritative contracts are `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, and shared RNG/event schemas in `schemas.layer1.yaml`. Avro (if any) is non-authoritative.&#x20;

## S0.2 Parameter set hash and manifest fingerprint (lineage)

### S0.2.1 Hash primitives

For any byte string $x$, let $\mathrm{SHA256}(x)\in\{0,1\}^{256}$ be the raw 32-byte digest.
Let $\oplus$ be **bytewise XOR** on $\{0,1\}^{256}$. Let $\|$ be byte concatenation.

### S0.2.2 Parameter hash (canonical)

Let $\mathcal{P}=\big\{$`hurdle_coefficients.yaml`, `nb_dispersion_coefficients.yaml`, `crossborder_hyperparams.yaml`$\big\}$.
Let $D(a)=\mathrm{SHA256}(\text{bytes}(a))$ for $a\in\mathcal{P}$. Sort by filename to $(p_1,p_2,p_3)$. Define

$$
\boxed{\ \text{parameter_hash_bytes}=\mathrm{SHA256}\!\big(D(p_1)\,\|\,D(p_2)\,\|\,D(p_3)\big)\ },
\qquad
\text{parameter_hash}=\text{hex64}(\text{parameter_hash_bytes}).
$$

This key versions *parameter-scoped* datasets (`hurdle_pi_probs`, `crossborder_eligibility_flags`, `country_set`, `ranking_residual_cache_1A`, etc.). Paths in the dictionary must include `parameter_hash={parameter_hash}` for these datasets.

### S0.2.3 Manifest fingerprint (run lineage)

Let $\mathcal{A}$ be the set of **all** artefacts the run opens (includes GDP map, ISO table, currency splits, plus the three YAMLs above). Let $D(a)$ be their digests; let $\text{git}_{32}$ be the repository commit hash zero-left-padded to 32 bytes (if needed). Define

$$
X \;=\; \bigoplus_{a\in\mathcal{A}} D(a) \;\oplus\; \text{git}_{32} \;\oplus\; \text{parameter_hash_bytes},\qquad
\boxed{\ \text{manifest_fingerprint_bytes}=\mathrm{SHA256}(X)\ },
\quad \text{manifest_fingerprint}=\text{hex64}(\text{manifest_fingerprint_bytes}).
$$

This fingerprint versions **egress** and **validation** (e.g., `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…`) and is embedded in rows.&#x20;

**Partitioning contract (from dictionary).**
Parameter-scoped datasets partition by `{parameter_hash}`; egress/validation lineage partitions by `{manifest_fingerprint}` (and often `{seed}`).&#x20;

## S0.3 RNG: master seed, counter, and sub-stream mapping

### S0.3.1 Algorithm and state

RNG engine is **Philox $2\times 64$-10**. All RNG JSONL events carry the shared **rng envelope**:

$$
\{\texttt{ts_utc},\texttt{run_id},\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint},\texttt{module},\texttt{substream_label},\texttt{rng_counter_before_{lo,hi}},\texttt{rng_counter_after_{lo,hi}}\}.
$$

Open-interval uniforms `u01` satisfy $u\in(0,1)$ (exclusive bounds).&#x20;

### S0.3.2 Master seed and initial counter (deterministic)

Given a run-supplied $s\in\{0,\dots,2^{64}\!-\!1\}$ (u64), and the 32-byte $\text{manifest_fingerprint_bytes}$:

* Seed:

  $$
  \boxed{\ S_{\text{master}} = \mathrm{LE64}\!\big(\mathrm{SHA256}(\text{“seed:1A”}\ \|\ \mathrm{LE64}(s)\ \|\ \text{manifest_fingerprint_bytes})[0{:}8]\big)\ }.
  $$
* Initial 128-bit counter:

  $$
  \boxed{\ (c_{\mathrm{hi}},c_{\mathrm{lo}}) = \mathrm{split64}\!\big(\mathrm{SHA256}(\text{“ctr:1A”}\ \|\ \text{manifest_fingerprint_bytes}\ \|\ \mathrm{LE64}(s))[0{:}16]\big)\ }.
  $$

Emit one `rng_audit_log` row with these values before any draws; every per-event record includes pre/post counters via the envelope.&#x20;

### S0.3.3 Sub-stream labelling (jump discipline)

For any logical event label $\ell\in\mathcal{L}$ (e.g., `"hurdle_bernoulli"`, `"gamma_component"`, `"poisson_component"`, `"gumbel_key"`) define the 64-bit stride

$$
\boxed{\ J(\ell) = \mathrm{LE64}\!\big(\mathrm{SHA256}(\ell)\big)\ }.
$$

Before consuming uniforms for label $\ell$ (for merchant $m$), update

$$
(c'_{\mathrm{hi}},c'_{\mathrm{lo}}) = (c_{\mathrm{hi}},\ c_{\mathrm{lo}} + J(\ell))\quad\text{with 64-bit carry},
$$

then draw. Envelope counters prove consumption; *strides are not duplicated in payloads*.&#x20;

## S0.4 Deterministic GDP bucket assignment

For $m$ with home ISO $c\in\mathcal{I}$:

$$
g_c \leftarrow G(c)\in\mathbb{R}_{>0},\qquad b_m := B(c)\in\{1,2,3,4,5\}.
$$

$B$ is a pinned lookup table (not recomputed online).&#x20;

## S0.5 Design matrices (hurdle and NB)

Let one-hot encoders be

$$
\phi_{\mathrm{mcc}}:\mathbb{N}\to\{0,1\}^{C_{\mathrm{mcc}}},\quad
\phi_{\mathrm{ch}}:\{\mathrm{CP},\mathrm{CNP}\}\to\{0,1\}^2,\quad
\phi_{\mathrm{dev}}:\{1,\dots,5\}\to\{0,1\}^5,
$$

with fixed column order frozen by the model-fitting bundle.

* **Hurdle (logit) design:**

$$
\boxed{\ x_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \phi_{\mathrm{dev}}(b_m)\big]^\top\ },\qquad
\pi_m=\sigma(\beta^\top x_m),\ \ \sigma(t)=\tfrac{1}{1+e^{-t}}.
$$

All hurdle coefficients (including GDP-bucket dummies) live in a single YAML vector $\beta$.&#x20;

* **Negative-Binomial designs (used later in S2):**

$$
\boxed{\ x^{(\mu)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m)\big]^\top\ },
\qquad
\boxed{\ x^{(\phi)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \log g_c\big]^\top\ }.
$$

Design rule: GDP bucket **excluded** from NB mean; $\log g_c$ **included** in dispersion with positive slope at fit time.&#x20;

**Numerical guard for $\sigma$.** Implement overflow-safe branches:

$$
\sigma(\eta)=
\begin{cases}
\frac{1}{1+e^{-\eta}},& \eta\ge 0,\\[4pt]
\frac{e^\eta}{1+e^\eta},& \eta<0,
\end{cases}
$$

and optionally clip only for function evaluation (not logging) at $|\eta|>40$ to avoid NaNs; $\pi\in\{0,1\}$ at saturation.

## S0.6 Cross-border eligibility (deterministic gate)

Define a rule family $\mathcal{E}\subseteq \mathbb{N}\times\{\mathrm{CP},\mathrm{CNP}\}\times\mathcal{I}$. For $m$:

$$
\boxed{\ \text{elig}_m=\mathbf{1}\big\{(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m)\in \mathcal{E}\big\}\ }.
$$

Persist to `crossborder_eligibility_flags` (partitioned by `{parameter_hash}`) per `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.&#x20;

## S0.7 Optional diagnostic cache (hurdle π)

Optionally cache $(\texttt{merchant_id},\eta_m,\pi_m)$ to `hurdle_pi_probs/parameter_hash={parameter_hash}/…` with schema `#/model/hurdle_pi_probs`. This table is **read-only** and never consulted during sampling.&#x20;

## S0.8 Numeric policy and determinism invariants

* **Numeric environment:** IEEE-754 binary64. Disable FMA for operations affecting residual ordering in later states; use deterministic serial reductions. (These toggles are part of the artefact set hashed into the fingerprint.)&#x20;
* **RNG envelope invariants:** Every RNG event (any state $>$ S0) must include the full envelope (seed, parameter_hash, manifest_fingerprint, pre/post counters, module, substream_label). Absence is a structural failure.&#x20;
* **Partitioning invariants (dictionary-backed):**

  $$
  \begin{aligned}
  &\text{Parameter-scoped: } \texttt{…/parameter_hash=\{parameter_hash\}/…} \\
  &\text{Egress/validation: } \texttt{…/fingerprint=\{manifest_fingerprint\}/…}
  \end{aligned}
  $$

  e.g., `country_set` and `ranking_residual_cache_1A` by `{seed,parameter_hash}`; `outlet_catalogue` by `{seed,manifest_fingerprint}`.&#x20;

## S0.9 Failure modes (all abort)

* Ingress schema violation for any row in `merchant_ids`.
* Missing artefact or digest mismatch during parameter/fingerprint formation.
* Non-finite values in $\eta_m$, $g_c$, or $b_m$ out of $\{1,\dots,5\}$.
* RNG audit record not written before first draw; or envelope fields missing in any subsequent event (caught by validators tied to the dictionary schemas).&#x20;

## S0.10 Outputs leaving S0 (deterministic state)

For each $m\in\mathcal{M}$, S0 produces:

* $x_m,\ x^{(\mu)}_m,\ x^{(\phi)}_m,\ b_m,\ g_c$ in memory (or a transient design-matrix artefact);
* one row in `crossborder_eligibility_flags` (and optional `hurdle_pi_probs`) **partitioned by `{parameter_hash}`**;
* run-level `parameter_hash`, `manifest_fingerprint`, `seed=S_{\text{master}}`, and initial $(c_{\mathrm{hi}},c_{\mathrm{lo}})$ logged in RNG audit/trace logs.&#x20;

---

