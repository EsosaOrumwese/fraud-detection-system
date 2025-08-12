# S1.1 — Inputs (from S0 + artefacts), under the hood

## A) Design vector $x_m$ (typed, column-frozen)

For each merchant $m$ with ingress fields $(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m)$ and GDP bucket $b_m\in\{1,\dots,5\}$ from the pinned 2025-04-15 vintage + Jenks-5 mapping, construct the **hurdle** design:

$$
\boxed{\;x_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \phi_{\mathrm{dev}}(b_m)\big]^\top\;}.
$$

* $\phi_{\mathrm{mcc}}:\mathbb{N}\to\{0,1\}^{C_{\mathrm{mcc}}}$ (exactly one “1”).
* $\phi_{\mathrm{ch}}:\{\mathrm{CP},\mathrm{CNP}\}\to\{0,1\}^{2}$ (exactly one “1”).
* $\phi_{\mathrm{dev}}:\{1,\dots,5\}\to\{0,1\}^{5}$ (exactly one “1”).
* **Column order is frozen** by the model-fitting bundle and may **not** be recomputed online; it must match the order expected by the coefficient vector (below).

**Dimension check.** $\dim(x_m)=1+C_{\mathrm{mcc}}+2+5$. Any encoder miss (unknown MCC/channel/bucket or wrong column order) is a **hard abort** before S1 proceeds.

## B) Coefficient vector $\beta$ (single YAML, atomic load)

Load $\beta$ **atomically** from `hurdle_coefficients.yaml`. $\beta$ already contains **all** coefficients required by $x_m$: intercept, MCC block, channel block, **all five** GDP-bucket dummies. Enforce the **shape invariant**

$$
|\beta| \;=\; 1 + C_{\mathrm{mcc}} + 2 + 5 .
$$

A mismatch (count or ordering) is a **hard abort**.

## C) Lineage & RNG context (must be present before any draw)

Before S1 emits any event, the following **must** already be fixed (from S0):

* `parameter_hash` (hex64) — partitions parameter-scoped artefacts.
* `manifest_fingerprint` (hex64) — partitions egress/validation and is embedded in events.
* `seed` = master Philox-2×64-10 key (u64) and the current **pre-event** counter $(\texttt{hi},\texttt{lo})$.
  All hurdle events **must** include the shared RNG **envelope** fields:
  `{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }`. Missing any field is a structural failure against the event schema.

## D) Event stream contract (where S1 writes)

Hurdle outcomes are written to the labelled stream:

```
logs/rng/events/hurdle_bernoulli/
    seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

with schema `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`. The **substream label** used in the envelope is exactly `"hurdle_bernoulli"`; validators rely on this when auditing counter jumps and draws.

---


# S1.2 — Probability map (logistic), under the hood

## 1) Objects, shapes, and exact dot-product semantics

You arrive in S1.2 with:

* a **column-frozen design vector** $x_m\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$ built in S0/S1.1, whose blocks are `[intercept | MCC one-hot | channel one-hot | GDP-bucket one-hot]`, and
* a single **coefficient vector** $\beta\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$ loaded atomically from `hurdle_coefficients.yaml`. The bundle guarantees $|\beta|=\dim x_m$ and that the **column order matches** the encoders. Any mismatch is a hard abort.

Because the predictor blocks are **one-hot**, the linear predictor reduces to a **four-term sum**; you do **not** need to materialise a long sparse dot product:

$$
\begin{aligned}
\eta_m
&= \beta^\top x_m \\
&= \beta_{\text{int}}
\;+\; \beta^{\text{(mcc)}}_{i(m)} 
\;+\; \beta^{\text{(ch)}}_{j(m)} 
\;+\; \beta^{\text{(dev)}}_{k(m)} ,
\end{aligned}
$$

where:

* $i(m)$ is the index of $\texttt{mcc}_m$ in the **frozen MCC dictionary**,
* $j(m)\in\{1,2\}$ is the index of $\texttt{channel}_m\in\{\mathrm{CP},\mathrm{CNP}\}$ in the **frozen channel order**,
* $k(m)\in\{1,\dots,5\}$ is the index of the **GDP bucket** $b_m$, in the **frozen dev order** $[1,2,3,4,5]$.
  All three indices are defined by the model-fitting bundle and checked earlier in S0/S1.1.

**Guard (shape & lookup).** Abort if any of the following occurs before evaluating $\eta_m$:

* $|\beta|\neq\dim x_m$;
* $\texttt{mcc}_m$ not in the MCC dictionary, or $\texttt{channel}_m\notin\{\mathrm{CP},\mathrm{CNP}\}$, or $b_m\notin\{1,\dots,5\}$.

---

## 2) Logistic map and evaluation policy

The logistic link $\sigma:\mathbb{R}\to(0,1)$ is

$$
\sigma(\eta)=\frac{1}{1+e^{-\eta}}\!,
$$

and we define

$$
\boxed{\ \eta_m=\beta^\top x_m,\qquad \pi_m=\sigma(\eta_m)\in(0,1)\ }.
$$

**Overflow-safe evaluation (obligatory).** Implement $\sigma$ with a two-branch form to avoid overflow/underflow and catastrophic cancellation:

$$
\sigma(\eta)=
\begin{cases}
\dfrac{1}{1+e^{-\eta}}, & \eta\ge 0,\\[6pt]
\dfrac{e^{\eta}}{1+e^{\eta}}, & \eta<0.
\end{cases}
$$

This keeps all intermediate exponentials bounded (at $|\eta|\gtrsim 40$, the value saturates to machine-precision 0/1 in binary64). If you **optionally clamp only the evaluation** (e.g., treat $|\eta|>40$ as $\pm 40$ when calling `exp`) you prevent spurious NaNs while keeping the **logged** $\eta_m$ as the true (unclamped) linear predictor. The single-YAML provenance for $\beta$ and the predictor set is part of the 1A design.

**Binary64, FMA-off.** The numeric policy from S0.8 applies here: compute the four-term sum for $\eta_m$ in **IEEE-754 binary64** with FMA **disabled** in ordering-sensitive paths (relevance is minor here because the sum has four addends, but the run-level policy is global). Determinism follows from fixed column order and serial evaluation.

---

## 3) Useful identities (audits & logs)

Although S1.2 only needs $\pi_m$, two stable log-prob identities are worth recording for audits or downstream diagnostics:

$$
\log \sigma(\eta) = -\mathrm{softplus}(-\eta),\qquad
\log\bigl(1-\sigma(\eta)\bigr) = -\mathrm{softplus}(\eta),
$$

with $\mathrm{softplus}(x)=\log(1+e^{x})$ evaluated via `log1p`/two-branch to stay finite for large $|x|$. These identities avoid subtractive cancellation when $\pi_m$ is near 0 or 1 and are fully consistent with the two-branch $\sigma$. (Optional; not required by the schema.)

---

## 4) Determinism & range invariants

* **D1 (bit replay).** For fixed $(x_m,\beta)$ and the run’s numeric toggles, $\eta_m$ and $\pi_m$ are **pure functions** with no RNG; they replay bit-identically across machines.
* **D2 (range).** $\pi_m\in(0,1)$ analytically; in floating-point, saturation may round to exactly 0 or 1 for $|\eta_m|\gg1$. This is acceptable: the hurdle trial in S1.3 then consumes **zero** uniforms and the outcome is deterministic (still logged).
* **D3 (schema consistency).** If you materialise diagnostics (`hurdle_pi_probs`), `pi` must satisfy the schema primitive `pct01` (i.e., $[0,1]$) and the table is **partitioned by `{parameter_hash}`** with a non-null `manifest_fingerprint` column in every row.

---

## 5) What S1.2 hands to S1.3

* The pair $(\eta_m,\pi_m)$ for each $m$.
* If $\pi_m\in\{0,1\}$, S1.3 will **not** consume a uniform (deterministic branch). Otherwise S1.3 consumes exactly one $u\sim U(0,1)$ on the **open interval** and sets `is_multi = 1{ u<π_m }`, logging the event to the `hurdle_bernoulli` stream with the shared RNG envelope.

---

## 6) Failure modes (S1.2-detectable)

* `beta_length_mismatch` or `column_order_mismatch` (detected before forming $\eta_m$).
* `nan_or_inf_logit(m)` if $\eta_m$ is non-finite; `nan_pi(m)` if $\pi_m$ is NaN despite two-branch evaluation (should be impossible).
* Any encoder lookup failure for MCC/channel/dev (should be caught in S1.1/S0.5).

---

## Minimal reference algorithm (numbered, language-agnostic)

```text
INPUT:
  beta               # vector, length = 1 + C_mcc + 2 + 5
  dicts              # frozen orders: mcc_cols[], ch_cols = ["CP","CNP"], dev_cols = [1..5]
  merchant row m     # fields: mcc, channel, b_m (GDP bucket in {1..5})

OUTPUT:
  (eta_m, pi_m)

1  assert len(beta) == 1 + C_mcc + 2 + 5
2  i := index_of(m.mcc    in mcc_cols); abort if NONE
3  j := index_of(m.channel in ch_cols); abort if NONE
4  k := index_of(m.b_m     in dev_cols); abort if NONE
5  eta := beta[0] + beta[1+i] + beta[1+C_mcc + j] + beta[1+C_mcc+2 + (k-1)]
6  # overflow-safe logistic
7  if eta >= 0:
8      pi := 1.0 / (1.0 + exp(-eta))
9  else:
10     t  := exp(eta)
11     pi := t / (1.0 + t)
12 return (eta, pi)
```
---

# S1.3 — RNG sub-stream and Bernoulli trial (deep dive)

## 1) Sub-stream label, stride, and pre-draw jump

We fix the **logical label** for this event stream to

$$
\ell := \text{``hurdle_bernoulli''}.
$$

From S0, each label $\ell$ induces a **64-bit stride** via its ASCII bytes:

$$
\boxed{\,J(\ell)=\mathrm{LE64}\!\big(\mathrm{SHA256}(\ell)[0{:}8]\big)\,}\in\{0,\dots,2^{64}\!-\!1\}.
$$

Before consuming any random numbers for the hurdle event of merchant $m$, we **jump** the Philox $2\times 64$ counter by adding the stride **to the low word with carry**:

$$
(c'_{\mathrm{hi}},c'_{\mathrm{lo}})=\Big(c_{\mathrm{hi}}+\mathbf{1}\{c_{\mathrm{lo}}+J(\ell)\ge 2^{64}\},\ (c_{\mathrm{lo}}+J(\ell))\bmod 2^{64}\Big),
$$

and we start the draw(s) for this event at the jumped counter $C'=(c'_{\mathrm{hi}},c'_{\mathrm{lo}})$. The stride definition and the jump discipline are fixed at S0.3.3 and are part of the replay contract.

**Envelope bookkeeping.** The jump itself is evidenced by the **RNG envelope counters** (`rng_counter_before_*`, `rng_counter_after_*`) and the event’s companion trace; envelope presence and typing are mandatory under the shared schema.

---

## 2) Uniform consumption plan (open interval, one deviate)

Given $\pi_m$ from S1.2:

* If $0<\pi_m<1$: consume **exactly one** uniform deviate $u_m$ on the **open interval** $(0,1)$.
* If $\pi_m\in\{0,1\}$: consume **zero** uniforms (deterministic branch); still log a trace row with `draws=0`.

**Open-interval requirement.** The `u` field must conform to the `u01` primitive (exclusive bounds). This is enforced by the event schema used for hurdle records.

**Block accounting.** Philox $2\times64$ yields **two** 64-bit words per block; for $d$ uniforms, the block count is $B=\lceil d/2\rceil$. Thus for $d=1$ we still advance **one block**. For $d=0$, $B=0$. The **after** counter must equal $\mathrm{advance}(C',B)$, and validators replay this equality from the trace.

**Integer→uniform mapping (u01).** A single block at $C'$ returns $(z_0,z_1)\in\{0,\dots,2^{64}\!-\!1\}^2$. Map the first word to $(0,1)$ (binary64-safe) by

$$
u_m \;=\; \frac{\left\lfloor z_0/2^{11}\right\rfloor + \tfrac{1}{2}}{2^{53}}\ \in\ \Big(\tfrac{1}{2^{54}},\, 1-\tfrac{1}{2^{54}}\Big),
$$

which satisfies the schema’s **exclusive** bounds and is independent of endianness. (The schema only constrains the range; this construction explains how we guarantee it.)

---

## 3) Bernoulli outcome and determinism

With $u_m$ in hand, define the outcome

$$
\boxed{\ \text{is_multi}(m)=\mathbf{1}\{\,u_m<\pi_m\,\}\ }.
$$

* If $\pi_m=0$: $\text{is_multi}(m)=0$ with **no** consumption; envelope shows no counter advance; a trace record logs `draws=0`.
* If $\pi_m=1$: $\text{is_multi}(m)=1$ with **no** consumption; same logging discipline.
* Otherwise: one uniform consumed; counters advance by **one block**.

Because (i) the sub-stream label is fixed, (ii) jumps are deterministic, and (iii) draw counts are fixed by $\pi_m$, the tuple $(u_m,\text{is_multi}(m))$ and the pre/post counters are **bit-replayable** given the same lineage keys and seed.

---

## 4) What must be written (paths, envelope, payload)

### 4.1 Event record (authoritative)

One JSONL record per merchant to the hurdle stream:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

Schema: `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`. The record **must** include the shared RNG **envelope** (`seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label="hurdle_bernoulli"`, counters before/after) and the payload

$$
\{\ \texttt{merchant_id},\ \texttt{pi}=\pi_m,\ \texttt{u}=u_m,\ \texttt{is_multi}=\mathbf{1}\{u_m<\pi_m\}\ \}.
$$

Optional, schema-permitted context (`gdp_bucket_id=b_m`, `mcc`, `channel`) may be included. Do **not** duplicate the stride in the payload: the envelope counters plus the trace prove replay.

### 4.2 Trace record (companion)

The **rng trace** stream logs per-event draw counts under:

```
logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl
```

Schema: `schemas.layer1.yaml#/rng/core/rng_trace_log`. For hurdle:

* `draws = 1` if $0<\pi_m<1$; else `draws = 0`.
* Envelope `after = advance(before, ceil(draws/2))` must hold exactly.

---

## 5) Invariants & validation hooks

* **I-H1 (Envelope completeness).** Every hurdle record has the full envelope; missing any required field is a schema failure.
* **I-H2 (Open interval).** `u` satisfies `u01` (strict inequalities). Event writers must not emit 0 or 1.
* **I-H3 (Counter conservation).** For each record:
  $C_{\text{after}}=\mathrm{advance}(C_{\text{before}},\lceil \texttt{draws}/2\rceil)$. Validators recompute this from the trace.
* **I-H4 (Branch purity).** Later RNG streams (NB/gamma/Poisson/Gumbel) are **only** permitted for merchants with a prior hurdle event where `is_multi=true`. Validators tie this to the dictionary’s stream ordering.

---

## 6) Failure modes (abort semantics)

* `rng_envelope_schema_violation`: envelope missing fields or wrong types/patterns (e.g., bad hex64), detected at write/validation time.
* `rng_counter_mismatch`: logged `after` not equal to $\mathrm{advance}(\text{before},\lceil d/2\rceil)$.
* `u_out_of_range`: `u` not in $(0,1)$ (violates `u01`).
* `missing_hurdle_gate`: downstream streams observed for a merchant with **no** prior hurdle event or with `is_multi=false`.

---

## 7) Minimal reference algorithm (numbered, supportive)

```text
INPUT:
  seed S_master; current counter C=(hi,lo);
  label = "hurdle_bernoulli";
  pi_m ∈ [0,1]; ctx = {ts_utc, run_id, parameter_hash, manifest_fingerprint, module}

OUTPUT:
  updated counter C_next; two JSONL records; is_multi(m)

1  # stride from label
2  h  := SHA256(ASCII("hurdle_bernoulli"))
3  J  := LE64(h[0:8])

4  # jump before consumption
5  C_before := C
6  lo' := (C.lo + J) mod 2^64
7  hi' := C.hi + ((C.lo + J) >= 2^64 ? 1 : 0)
8  C_jump := (hi', lo')

9  if pi_m == 0 or pi_m == 1:
10     draws := 0;  U := [];  C_after := C_jump
11     is_multi := (pi_m == 1)
12 else:
13     draws := 1;  B := 1
14     (z0, _) := Philox2x64_10(S_master, C_jump)
15     u := ((floor(z0 / 2^11) + 0.5) / 2^53)      # u01 open interval
16     is_multi := (u < pi_m)
17     C_after := advance(C_jump, 1)

18  # event record to logs/rng/events/hurdle_bernoulli/...
19  write_event_envelope(ctx + {seed: S_master, substream_label: "hurdle_bernoulli",
                                rng_counter_before_hi: C_jump.hi, rng_counter_before_lo: C_jump.lo,
                                rng_counter_after_hi:  C_after.hi, rng_counter_after_lo:  C_after.lo})
20  write_event_payload({merchant_id, pi: pi_m, u: (draws==1 ? u : null), is_multi})

21  # trace record to logs/rng/trace/...
22  write_trace({draws, label: "hurdle_bernoulli",
                rng_counter_before: C_jump, rng_counter_after: C_after})

23  C_next := C_after
24  return (C_next, is_multi)
```

---

### Where this ties into your artefacts

* Label, stride recipe, and jump discipline: S0.3.3.
* Event paths and schemas (hurdle stream and trace log): dataset dictionary + layer-wide schemas.
* Consumption discipline and payload keys for hurdle: S1 doc segments.

---



# S1.4 — Event emission (authoritative schema + optional context)

## 1) What one record must contain (payload semantics)

For each merchant $m$, emit **exactly one** hurdle event record with the shared RNG **envelope** and the following **payload**:

$$
\boxed{\ \texttt{payload}=\{\ \texttt{merchant_id},\ \texttt{pi}=\pi_m,\ \texttt{u}=u_m,\ \texttt{is_multi}=\mathbf{1}\{u_m<\pi_m\}\ \}\ }.
$$

**Field roles & types (as enforced by the schema):**

* `merchant_id` — opaque id64 (primary identifier for the event’s subject).
* `pi` — hurdle probability $\pi_m\in[0,1]$ (the logistic from S1.2). Persist the numeric value actually used to decide; no rounding beyond JSON number encoding.
* `u` — the *open-interval* uniform deviate $u_m\in(0,1)$ when a draw occurs (schema primitive `u01`).

  * **Deterministic branch**: when $\pi_m\in\{0,1\}$, no draw occurs. In this case, either **omit** `u` or set it to `null` **only if** the schema permits nullability; otherwise do not write the field. (Never fabricate `u`.)
* `is_multi` — 0/1 decision; **definition** is part of the payload: `is_multi = 1{ u < pi }`.

  * Deterministic branch: `is_multi = 0` if $\pi_m=0$; `is_multi = 1` if $\pi_m=1$.

Optional (schema-permitted) **context** fields:

* `gdp_bucket_id = b_m ∈ {1,…,5}`, `mcc`, `channel`.
  These are **for debugging only**; they must **not** be used for replay. (Replay is proven by the envelope counters and the trace log.)

**Never** duplicate or embed the sub-stream stride $J(\ell)$ in the payload; it is *implicit* via the label and proven by counters in the envelope.

---

## 2) Envelope, stream, and paths (authoritative)

Every record must carry the **shared RNG envelope**:

```
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
  module, substream_label, rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }
```

* `substream_label` **must be** `"hurdle_bernoulli"`.
* Counters reflect the **jumped** starting point (S1.3) and the **exact** block advance from consumption (`ceil(draws/2)`).
* Write to the fixed stream:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

A separate `stream_jump` record (S0.3.3 discipline) evidences the pre-draw jump; a `rng_trace_log` row records `draws` so validators can check counter conservation.

---

## 3) Emission rules by case (deterministic vs stochastic)

Let $\pi_m$ be computed in S1.2.

### Case A — Stochastic ($0<\pi_m<1$)

* Consume **one** uniform $u_m\in(0,1)$ on the open interval (u01 mapping).
* **Payload** contains `u = u_m`, `pi = π_m`, `is_multi = 1{u_m < π_m}`.
* **Counters** advance by **one block** (two 64-bit words produced; only the first is consumed).
* **Trace** row: `draws=1`, with the same before/after counters.

### Case B — Deterministic ($\pi_m=0$ or $\pi_m=1$)

* Consume **zero** uniforms.
* **Payload**: `pi = 0` with `is_multi = 0` (or `pi = 1` with `is_multi = 1`).

  * `u` is **absent** (or `null` if schema allows).
* **Counters**: `after == before` (no blocks consumed).
* **Trace** row: `draws=0`.

In both cases, **exactly one** hurdle event is emitted for the merchant.

---

## 4) Invariants (validators must assert)

1. **Envelope completeness & types.** All required envelope fields present; `seed`, `parameter_hash`, `manifest_fingerprint` equal the run keys; `substream_label == "hurdle_bernoulli"`.
2. **Open-interval constraint.** If `u` is present, it strictly satisfies $0 < u < 1$ (`u01`). No 0/1 values allowed.
3. **Block conservation.**
   $\texttt{after} = \mathrm{advance}(\texttt{before},\,\lceil \texttt{draws}/2\rceil)$ for the companion trace row.
4. **Decision correctness.**

   * Stochastic: `is_multi == 1{u < pi}`.
   * Deterministic: `is_multi == (pi == 1)`, and `u` is missing/null with `draws=0`.
5. **One-per-merchant.** Exactly one hurdle record per merchant $m$ per run/seed/parameter_hash.
6. **No stride leakage.** Payload does not contain $J(\ell)$ or counter pieces; replay must rely on envelope + trace.

---

## 5) Failure modes (hard abort)

* **Schema breach:** missing envelope field; wrong pattern (e.g., non-hex64); `u` present but $\notin(0,1)$.
* **Counter mismatch:** event `after` does not equal `advance(before, ceil(draws/2))`.
* **Duplicate event:** more than one hurdle record for $(m, seed, parameter_hash, run_id)$.
* **Deterministic misuse:** `pi ∈ {0,1}` but a `u` value is logged, or `draws>0`.
* **Replay drift:** `substream_label` not `"hurdle_bernoulli"` for the hurdle stream.

---

## Minimal reference algorithm (supportive, numbered)

```text
INPUT:
  merchant_id, pi_m,               # from S1.2
  u_opt, draws,                    # from S1.3 (u_opt is None when deterministic)
  env = {ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
         module, substream_label="hurdle_bernoulli",
         rng_counter_before, rng_counter_after}

OUTPUT:
  one JSONL event row to hurdle_bernoulli stream

1  # Validate envelope completeness and label
2  assert substream_label == "hurdle_bernoulli"

3  # Compose payload
4  if draws == 1:
5      assert 0.0 < u_opt < 1.0
6      is_multi := (u_opt < pi_m)
7      payload  := {merchant_id, pi: pi_m, u: u_opt, is_multi: is_multi}
8  else:  # draws == 0, deterministic
9      assert pi_m == 0.0 or pi_m == 1.0
10     is_multi := (pi_m == 1.0)
11     payload  := {merchant_id, pi: pi_m, is_multi: is_multi}   # no 'u' field

12 # Write event row with envelope + payload to logs/rng/events/hurdle_bernoulli/...
13 # Write companion trace row (label="hurdle_bernoulli", draws)
```

---

# S1.5 — Determinism & correctness invariants (deep dive)

We formalise four invariants for the hurdle stream $ \ell=$"hurdle_bernoulli", tying them to the authoritative schemas and dictionary paths. These invariants are **normative** for S1; violations are fatal.

---

## I-H1 — Bit-replay (deterministic re-execution)

### Statement

For fixed inputs

$$
(x_m,\ \beta,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint}),
$$

the tuple $(u_m,\ \text{is_multi}(m))$ **and** the envelope counters $(C_{\text{before}},C_{\text{after}})$ in the hurdle event for merchant $m$ are **bit-identical** across replays of the run.

### Why this holds (sketch)

1. **Deterministic probability.** $\eta_m=\beta^\top x_m$ and $\pi_m=\sigma(\eta_m)$ are pure functions of $(x_m,\beta)$ with global numeric policy fixed in S0.8. No RNG here.
2. **Deterministic jump.** Sub-stream stride $J(\ell)=\mathrm{LE64}(\mathrm{SHA256}(\ell)[0{:}8])$ is fixed for $\ell=$"hurdle_bernoulli". The jumped counter $C'=\mathrm{jump}(C,J)$ is a pure add-with-carry in $\mathbb{Z}_{2^{64}}\times\mathbb{Z}_{2^{64}}$.
3. **Deterministic consumption.** Draw count $d(m)=\mathbf{1}\{0<\pi_m<1\}$ is a pure predicate of $\pi_m$. Given $d$, block count $B=\lceil d/2\rceil\in\{0,1\}$. The **after** counter satisfies $C_{\text{after}}=\mathrm{advance}(C',B)$. Uniform $u_m$ (if drawn) is the first u01 variate derived from Philox$2\times64$-10 at $C'$, using a fixed int→u01 mapping on the **open interval**.
4. **Envelope identity.** Envelope fields `seed`, `parameter_hash`, `manifest_fingerprint`, `substream_label`, and counters are required by schema; equality across replays follows from (1)–(3) and the run’s fixed lineage keys.

**Consequence.** For any two compliant runs $R,R'$ with the same 5-tuple above, the emitted JSONL records for $m$ have byte-identical envelope counters and identical $(u_m,\text{is_multi}(m))$. (This is exactly what the state doc declares.)

---

## I-H2 — Consumption (exact draw count)

### Statement

The per-merchant uniform draw count is

$$
d(m)=\begin{cases}
1,& 0<\pi_m<1,\\
0,& \pi_m\in\{0,1\}.
\end{cases}
$$

A companion **rng trace** row must record `draws = d(m)` for this labelled event, and the event envelope must satisfy counter conservation:

$$
C_{\text{after}} = \mathrm{advance}\!\big(C_{\text{before}},\ \lceil d(m)/2\rceil\big)\in\{0,1\}\ \text{blocks}.
$$

Here, $\mathrm{advance}((h,\ell),B)$ adds $B$ to the low word $\ell$ (mod $2^{64}$) with carry into $h$.

### Auditable artefacts

* Event stream: `logs/rng/events/hurdle_bernoulli/...` (schema `#/rng/events/hurdle_bernoulli`).
* Trace log: `logs/rng/trace/.../rng_trace_log.jsonl` (schema `#/rng/core/rng_trace_log`).
  Validators check that for each hurdle event there is a matching trace row and that block conservation holds exactly.

---

## I-H3 — Schema conformance (payload + envelope)

### Statement

Every hurdle record **must** contain:

* the **shared RNG envelope** (including `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label="hurdle_bernoulli"`, and `rng_counter_{before,after}_{hi,lo}`), and
* the **payload keys** `{ merchant_id, pi, u, is_multi }`, where:

  * `pi` equals the evaluated $\pi_m\in[0,1]$;
  * `u` (when present) satisfies the schema primitive **`u01`**: $u\in(0,1)$ (strictly);
  * `is_multi` equals $\mathbf{1}\{u<\pi\}$ in the stochastic case, and equals $\mathbf{1}\{\pi=1\}$ in the deterministic case (with **no `u` field** or a `null` if and only if the schema allows nullability).
    Any omission or type/range violation is a schema failure against `schemas.layer1.yaml`.

### Notes

* Optional context (`gdp_bucket_id=b_m`, `mcc`, `channel`) may be included if permitted by the event schema, but are **non-authoritative** for replay (counters + trace are the authority).
* Dataset dictionary pins the exact path and schema ref for this stream.

---

## I-H4 — Branch purity (downstream gating)

### Statement

**No** downstream state may override the hurdle decision. Formally, let

$$
\mathcal{H}_1 = \{m : \exists \text{ hurdle record for } m \text{ with } \text{is_multi}=1\},
$$

and for each downstream labelled stream $S\in\{\texttt{gamma_component},\ \texttt{poisson_component},\ \texttt{nb_final},\ \texttt{residual_rank},\ \ldots\}$, let

$$
\mathcal{E}_S = \{ m : \exists \text{ event for } m \text{ in } S \}.
$$

Then the validator enforces

$$
\forall S,\quad \mathcal{E}_S \subseteq \mathcal{H}_1.
$$

If a merchant later emits NB/ZTP/Dirichlet/Gumbel events without a **prior** hurdle record with `is_multi=true`, the run fails validation. The dataset dictionary ties each event path to its schema, making this join test precise.

### Edge cases

* Deterministic branch with $\pi_m=1$ counts as membership in $\mathcal{H}_1$ (no uniform consumed, but a hurdle record is still emitted).
* If $\pi_m=0$, the merchant **must not** appear in any downstream RNG streams; presence indicates a gating breach.

---

## Additional cross-checks that make these invariants robust

* **Uniqueness per merchant.** Exactly one hurdle record per $(\texttt{merchant_id}, \texttt{seed}, \texttt{parameter_hash}, \texttt{run_id})$. Duplicates are validation errors. (The dictionary/scanner can enforce this cardinality.)
* **Label integrity.** `substream_label` in the envelope **must equal** `"hurdle_bernoulli"` for this stream; wrong labels break replay assumptions and are treated as structural failures.
* **Lineage coherence.** Embedded `parameter_hash` equals the directory key for parameter-scoped artefacts (e.g., diagnostic `hurdle_pi_probs`); hurdle events/logs are partitioned by `{seed, parameter_hash, run_id}` exactly as in the dictionary.

---

## Minimal validator (supportive, numbered)

This is just to show how a validator can assert I-H1..I-H4 with the dictionary paths.

```text
INPUT:
  H = hurdle events (logs/rng/events/hurdle_bernoulli/...)
  T = rng_trace_log (logs/rng/trace/.../rng_trace_log.jsonl)
  K = {seed, parameter_hash, run_id}
  Downstreams = {gamma_component, poisson_component, nb_final, ...} streams

OUTPUT:
  pass/fail with reasons

1  # I-H3: schema + envelope completeness is enforced by json-schema validator on H and T.
2  # Re-check u01 range when u present:
3  for e in H:
4      if 'u' in e.payload:
5          assert 0.0 < e.payload.u < 1.0
6      # decision correctness
7      if 'u' in e.payload:
8          assert e.payload.is_multi == (e.payload.u < e.payload.pi)
9      else:
10         assert e.payload.pi == 0.0 or e.payload.pi == 1.0
11         assert e.payload.is_multi == (e.payload.pi == 1.0)

12 # I-H2: draw counts and counter conservation
13 for e in H:
14     draws := (0 < e.payload.pi && e.payload.pi < 1.0) ? 1 : 0
15     t := find_matching_trace(T, e, label="hurdle_bernoulli")
16     assert t.draws == draws
17     assert e.after == advance(e.before, ceil(draws/2))

18 # I-H1: bit-replay (spot check)
19 # recompute the jumped counter from previous after + J("hurdle_bernoulli") and compare
20 # (full bit replay is guaranteed by construction; validator ensures no drift)

21 # I-H4: branch purity
22 H1 := {e.merchant_id : e in H and e.payload.is_multi == 1}
23 for S in Downstreams:
24     for e in S:
25         assert e.merchant_id in H1
```

---

### Where this is anchored in your artefacts

* The exact statement of **I-H1..I-H4** is captured in your S1 state file.
* Event and trace **paths & schema refs** are defined in the dataset dictionary; these give the validator its tables.
* **Schema authority** identifies `schemas.layer1.yaml` (RNG events) and `schemas.1A.yaml` (model artefacts) as the only sources of truth; Avro is non-authoritative.

---



# S1.6 — Failure modes (abort semantics)

We partition failures into three families matching your bullets. Let $x_m$ be the frozen hurdle design, $\beta$ the single YAML vector, $\eta_m=\beta^\top x_m$, $\pi_m=\sigma(\eta_m)$, and let the hurdle stream be `rng_event_hurdle_bernoulli` as pinned by the dataset dictionary.

---

## F-H1 — Design / coefficients mismatch (hard abort at compute time)

**What must hold (shape + ordering):**

$$
|\beta| \stackrel{!}{=} 1 + C_{\text{mcc}} + 2 + 5,
$$

with **block boundaries** $[0]$ (intercept), $[1{:}C_{\text{mcc}}]$ (MCC), $[C_{\text{mcc}}{+}1{:}C_{\text{mcc}}{+}2]$ (channel in the frozen order $[\mathrm{CP},\mathrm{CNP}]$), and $[C_{\text{mcc}}{+}3{:}C_{\text{mcc}}{+}7]$ (GDP-bucket dummies in the frozen order $[1,2,3,4,5]$). The model-fitting bundle and registry tie this order to the one-hot encoders; **no online reordering** is permitted.

**Failure predicates (any ⇒ abort):**

* **Length mismatch:** $|\beta|\neq 1+C_{\text{mcc}}+2+5$.
  Error: `beta_length_mismatch(expected, observed)`.
* **Unknown category:** $\texttt{mcc}_m$ not in MCC dictionary, or $\texttt{channel}_m\notin\{\mathrm{CP},\mathrm{CNP}\}$, or $b_m\notin\{1,\dots,5\}$.
  Error: `unknown_mcc(mcc) | unknown_channel(ch) | bucket_out_of_range(b)`.
* **Column-order drift:** the encoder dictionaries for MCC / channel / dev-bucket do not match the order assumed by $\beta$ (detected by comparing dictionary order with the bundle’s order metadata, or by sentinel lookups).
  Error: `column_order_mismatch(block, dict_digest, beta_digest)`.

**Rationale.** Your state spec/registry make the design matrix and hurdle coefficients a **coupled pair**; any drift breaks $\eta_m$ semantics and must fail closed.

---

## F-H2 — Numeric invalid (hard abort at compute time)

Evaluate $\eta_m$ and $\pi_m$ under the S0.8 numeric policy (binary64; overflow-safe two-branch logistic). The following are illegal:

**Failure predicates (any ⇒ abort):**

* **Non-finite logit:** $\neg\,\mathrm{isfinite}(\eta_m)$.
  Error: `nan_or_inf_logit(merchant_id, eta)`.
* **Non-finite probability:** $\neg\,\mathrm{isfinite}(\pi_m)$.
  Error: `nan_pi(merchant_id)`.
* **Out-of-range probability:** $\pi_m<0$ or $\pi_m>1$ after evaluation (should not occur with the prescribed $\sigma$).
  Error: `pi_out_of_range(merchant_id, pi)`.

**Notes.** Saturation at $|\eta_m|\gg 1$ may round $\pi_m$ to exactly 0 or 1; that is **allowed** and triggers the deterministic branch in S1.3 with `draws=0`.

---

## F-H3 — Logging gap (validator failure post-run)

**Policy.** The hurdle event is the **first** RNG stream for 1A; no downstream RNG stream may appear for a merchant lacking a prior hurdle record with `is_multi=true`. Define

$$
\mathcal{H}_1=\{m : \exists\ \text{hurdle record with } \text{is_multi}=1\},
$$

and for each downstream stream $S\in\{\texttt{gamma_component},\texttt{poisson_component},\texttt{nb_final},\ldots\}$,

$$
\mathcal{E}_S=\{m : \exists\ \text{event for $m$ in stream $S$}\}.
$$

**Validator rule:** $\forall S$, assert $\mathcal{E}_S\subseteq\mathcal{H}_1$. Otherwise:
Error: `logging_gap_no_prior_hurdle(stream=S, merchant_id)`.

**Where this comes from.** The dictionary pins the hurdle stream path/schema and the downstream streams (`gamma_component`, `poisson_component`, `nb_final`, …); your S1 state explicitly states this gating and that hurdle is first. The validator joins by `(seed, parameter_hash, run_id, merchant_id)` to enforce it.

---

## Minimal validator / guard (supportive, numbered)

```text
INPUT:
  beta, dicts, merchants;                # for F-H1 checks
  hurdle_events H;                       # logs/rng/events/hurdle_bernoulli/...
  downstream_streams {S_k};              # gamma_component, poisson_component, nb_final, ...
  # all paths/schemas per dataset_dictionary.layer1.1A.yaml

# F-H1: shape + ordering + vocab
1  assert len(beta) == 1 + C_mcc + 2 + 5                               # length
2  assert ch_dict == ["CP","CNP"] and dev_dict == [1,2,3,4,5]          # order
3  for m in merchants:
4      assert m.mcc in mcc_dict
5      assert m.channel in ch_dict
6      assert b_m in dev_dict

# F-H2: numeric validity under two-branch logistic
7  for m in merchants:
8      eta := dot(beta, x_m)         # binary64
9      assert isfinite(eta)
10     pi  := logistic_two_branch(eta)
11     assert isfinite(pi) and 0.0 <= pi <= 1.0

# F-H3: logging gap (post-run)
12 H1 := { e.merchant_id : e in H and e.payload.is_multi == 1 }
13 for each stream S in {S_k}:
14     for e in S:
15         assert e.merchant_id in H1, else raise logging_gap_no_prior_hurdle
```

* Hurdle and trace stream paths/schemas used above are pinned in the dictionary (versioned by `{run_id}`; partitioned by `{seed, parameter_hash, run_id}`), so the validator has deterministic places to look.
* Parameter-scoped diagnostics (`hurdle_pi_probs`) are **not** consulted for draw correctness (guarding against accidental dependence on caches).

---

# S1.7 — Outputs of S1 (state boundary)

## 1) Authoritative event stream (what S1 *must* persist)

For every merchant $m\in\mathcal{M}$, S1 emits **exactly one** JSONL record to the **hurdle stream** with the shared RNG envelope and the hurdle payload:

* **Path (fixed):**
  `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`

* **Schema (fixed):** `#/rng/events/hurdle_bernoulli` (from the layer-wide RNG schema set).

* **Envelope (mandatory fields):**
  `{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label="hurdle_bernoulli", rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }`.

* **Payload (authoritative):**
  `merchant_id`, `pi=π_m`, `u=u_m` (present iff a draw occurred; open interval (0,1)), `is_multi = 1{ u < π }` (or `1{π=1}` in deterministic branch).

* **Trace companion:** one `rng_trace_log` row recording `draws ∈ {0,1}` for this sub-stream and proving counter conservation (`after = advance(before, ceil(draws/2))`).

These records are the **only** authoritative source for the hurdle decision and the precise counter evolution into S2.

---

## 2) Branching state passed to S2+ (in-memory contract)

Downstream sampling states **must not** recompute the hurdle decision; they consume a small, typed hand-off per merchant:

### 2.1 Typed hand-off tuple

For each $m$, S1 produces an in-memory tuple

$$
\Xi_m \;:=\; \big(\text{is_multi}(m),\ N_m,\ K_m,\ \mathcal{C}_m,\ C^{\star}_m\big),
$$

where:

* $\text{is_multi}(m)\in\{0,1\}$ — the hurdle outcome from the event payload.
* $N_m\in\mathbb{N}$ — **target outlet count** to be generated by S2 (Negative Binomial branch) when $\text{is_multi}=1$; when $\text{is_multi}=0$ we set $N_m:=1$ by convention (the single home-site path).
* $K_m\in\mathbb{N}$ — **non-home country budget** carried forward (initially 0 on the single-site path; computed later for multi-site via cross-border / ranking states).
* $\mathcal{C}_m\subseteq\mathcal{I}$ — **country set accumulator**:
  $\mathcal{C}_m:=\{\text{home}(m)\}$ on the single-site path; on the multi-site path S2/S3 will extend this set according to eligibility/ranking.
* $C^{\star}_m\in\{0,\dots,2^{64}\!-\!1\}^2$ — **the RNG counter cursor** after the hurdle event for $m$: this is exactly the event’s `rng_counter_after_{hi,lo}` and is the **starting** Philox counter for the *next* labelled event for $m$.

### 2.2 Branch semantics (deterministic split)

* **If $\text{is_multi}(m)=0$:**

  $$
  \boxed{\ N_m\leftarrow 1,\quad K_m\leftarrow 0,\quad \mathcal{C}_m\leftarrow\{\text{home}(m)\}\ }
  $$

  No NB/Dirichlet/ZTP/Gumbel streams are permitted for $m$. Control transfers **directly to S7** (placement/finalization for the single home site), with RNG starting at $C^{\star}_m$ and the next appropriate sub-stream label for S7.

* **If $\text{is_multi}(m)=1$:**
  Proceed to **S2** to sample $N_m$ via the NB branch (using the designs $x^{(\mu)}_m, x^{(\phi)}_m$ and dispersion parameters). The **first** NB-labelled event for $m$ must use `rng_counter_before = C^{\star}_m`.

This establishes a **pure**, replayable control-flow boundary: downstream states consume $\Xi_m$ only; they never revisit S1 data except for validation.

---

## 3) Optional diagnostic dataset (parameter-scoped)

If enabled, S1 (or S0.7) persists diagnostics for inspection—not for sampling:

* **Path:**
  `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/…`

* **Schema:** `#/model/hurdle_pi_probs`.

* **Contents:** one row per $m$ with `manifest_fingerprint`, `merchant_id`, `logit=η_m`, `pi=π_m`.
  This table is **read-only** and **never** consulted by S2+ logic; it exists solely for debugging/QA and lineage.

---

## 4) Determinism & interface invariants at the boundary

1. **Single emit:** exactly one hurdle event per $m$ (per `{seed, parameter_hash, run_id}`), and exactly one $\Xi_m$ hand-off.
2. **Counter continuity:** for each $m$, the *next* event’s `rng_counter_before` must equal $C^{\star}_m$ carried out of S1.
3. **Branch purity:** downstream RNG streams appear **iff** $\text{is_multi}(m)=1$. The single-site path performs **no** NB/ZTP/Dirichlet/Gumbel draws.
4. **Parameter/lineage coherence:** all downstream artefacts obey the dictionary’s partitioning contract (`{parameter_hash}` for parameter-scoped intermediates; `{fingerprint}` for egress/validation), and every event row embeds the run’s `parameter_hash` and `manifest_fingerprint`.
5. **Numeric consistency:** the logistic probability $π_m$ used in the event payload equals the $π_m$ that would be recomputed from $x_m$ and $\beta$; any divergence is a hard failure in validation.

---

## 5) Minimal hand-off construction (supportive, numbered)

```text
INPUT:
  hurdle_event for m (envelope + payload),
  home_iso(m)

OUTPUT:
  Ξ_m = (is_multi, N_m, K_m, C_m, C*_m)

1  is_multi := hurdle_event.payload.is_multi           # 0 or 1
2  C*_m      := (hurdle_event.envelope.rng_counter_after_hi,
                 hurdle_event.envelope.rng_counter_after_lo)

3  if is_multi == 0:
4      N_m := 1
5      K_m := 0
6      C_m := { home_iso(m) }
7  else:
8      N_m := ⊥   # to be sampled in S2
9      K_m := ⊥   # to be derived by S3/S4 later
10     C_m := { home_iso(m) }   # seed with home; will be expanded

11 return Ξ_m
```

This nails the **state boundary**: the single authoritative event stream persisted by S1, the exact in-memory contract that unlocks S2/S7, and the invariants that guarantee replayable control flow and RNG continuity across the merchant’s journey.

---
