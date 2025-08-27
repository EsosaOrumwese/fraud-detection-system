# S1.1 — Inputs, Preconditions, and Write Targets (normative)

## Purpose (what S1 does and does **not** do yet)

S1 evaluates a **logistic hurdle** per merchant and produces a **Bernoulli outcome** “single vs multi”. In this subsection we only pin **inputs** and **context/lineage** required to do that deterministically; the actual probability map, RNG and event body are specified in S1.2–S1.4.

---

## Inputs (must be present at S1 entry)

### 1) Design vector $x_m$ (column-frozen, from S0.5)

For each merchant $m$, S1 receives the hurdle design vector

$$
x_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel}_m),\ \phi_{\text{dev}}(b_m)\big]^\top,
$$

with dimension $1+C_{\text{mcc}}+2+5$ and one-hot blocks whose **column order is frozen by the fitting bundle** (not recomputed online). GDP bucket $b_m\in\{1,\dots,5\}$ comes from S0.4. These are the only features used by the hurdle in S1; $\log g_c$ is **not** used here (belongs to NB dispersion later).

### 2) Coefficient vector $\beta$ (single YAML, atomic load)

Load $\beta$ **atomically** from `hurdle_coefficients.yaml`. It already contains **all** coefficients in the exact order required by $x_m$: intercept, MCC block, channel block, **all five** GDP-bucket dummies. Enforce the shape invariant

$$
|\beta| = 1+C_{\text{mcc}}+2+5,
$$

else abort (shape/order mismatch).

> Design rule (context): hurdle uses bucket dummies; NB mean excludes them; NB dispersion uses $\log g_c$ (positive fitted slope). This is enforced in S0.5 and referenced by S1 only for clarity.

### 3) Lineage & RNG context (must be fixed before any draw)

Before the **first** hurdle draw, S1 must run under a context where S0 has already established:

* `parameter_hash` (hex64) — partitions parameter-scoped artefacts.
* `manifest_fingerprint` (hex64) — partitions egress/validation; also embedded in all events.
* `seed` (u64) — master Philox-2×64-10 key, with current **pre-event** counter $(\texttt{hi},\texttt{lo})$.
* `run_id` (hex32) — **logs-only** partition key.
* `rng_audit_log` exists for this `{seed, parameter_hash, run_id}` (S0.3); S1 is not allowed to emit its first RNG event without a prior audit row.

All hurdle events will include the **shared RNG envelope** fields:
`{ ts_utc, module="1A.hurdle_sampler", substream_label="hurdle_bernoulli", seed, parameter_hash, manifest_fingerprint, run_id, rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }`. Missing any of these is a schema/envelope failure. (The exact event body is in S1.4.)

**Envelope timestamp format.** `ts_utc` MUST be RFC-3339 with `Z` and **exactly 6 fractional digits** (microseconds), e.g., `2025-08-15T10:03:12.345678Z`.

**Counter fields.** JSON field order is **low then high**: `rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`. The mnemonic `(hi,lo)` used in formulas refers to the same values in tuple order; field names always write **_lo** before **_hi**.

---

## Preconditions (hard invariants at S1 entry)

1. **Shape & order:** $|\beta|=\dim(x_m)$ and the block orders (MCC, channel, dev-5) match the fitting dictionaries; otherwise S1 aborts (design/coeff mismatch).
2. **Domains:** channel $\in\{\mathrm{CP},\mathrm{CNP}\}$; $b_m\in\{1,\dots,5\}$; GDP $g_c>0$ already enforced upstream (S0.4/S0.5).
3. **Numeric policy:** S0.8’s environment is in force: IEEE-754 binary64, round-to-nearest-even, **no FMA**, **no FTZ/DAZ**; dot-products use fixed-order accumulation. S1 will rely on the overflow-safe logistic in S1.2.
4. **RNG audit present:** the audit envelope for this run/subsystem is present before S1 emits the first hurdle event; otherwise abort (S0.9/F4a).

---

## Event stream target (authoritative ID, path, schema)

S1 writes **exactly one** hurdle record per merchant to:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

with schema anchor `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`. The `substream_label` in the envelope is **exactly** `"hurdle_bernoulli"`. These identifiers and the partitioning triple are authoritative via the dataset dictionary and artefact registry.

**Trace rule (S1).** For **each** hurdle event row, emit **exactly one** `rng_trace_log` row with the same `{seed, parameter_hash, run_id, substream_label="hurdle_bernoulli", merchant_id}` and fields `{rng_counter_before_*, rng_counter_after_*, draws}`. This row is the **only** authoritative source for `draws` for this substream.

---

## Forward-looking contracts S1 must satisfy (tied here so inputs are complete)

* **Probability & safe logistic (S1.2):** compute $\eta_m=\beta^\top x_m$ and $\pi_m=\sigma(\eta_m)$ with the **two-branch** overflow-safe logistic; non-finite $\eta$ or $\pi$ ⇒ abort.
* **RNG substream & u(0,1) (S1.3):** jump by label `"hurdle_bernoulli"` then draw **one** open-interval uniform $u\in(0,1)$ **iff** $0<\pi_m<1$; otherwise `draws=0`. Counters advance exactly as per S0.3 mapping and show up in the envelope.
* **Payload discipline (S1.4):** payload contains `{merchant_id, eta, pi, is_multi, u|null, deterministic}` where:

  * when $0<\pi_m<1$: `u∈(0,1)`, `deterministic=false`;
  * when $\pi_m\in\{0,1\}$: `u=null`, `deterministic=true`.
    This is **schema-level** and validated downstream.

---

## Failure semantics (at S1.1 boundary)

If any precondition above fails, S1 must **abort the run** with S0.9 classes:

* shape/order mismatch → **Design/coefficients mismatch** (S1 failure mapped to S0.9/F6 or explicit code),
* missing audit/envelope keys → **RNG envelope violation** (S0.9/F4),
* wrong path/partition keys for logs → **Partition mismatch** (S0.9/F5).

---

## Why this matters (determinism & replay)

By pinning $x_m$, $\beta$, lineage keys, event IDs/paths, and the envelope **before** any draw, S1’s later Bernoulli outcome and counters become **bit-replayable** under any sharding or scheduling, as required by S1’s invariants (I-H1..H4) and the dictionary.

---

**Bottom line:** S1 starts only when $x_m$, $\beta$, and the lineage/RNG context are immutable and schema-backed; it writes to the single authoritative hurdle stream with a fixed envelope and partitioning. With these inputs and preconditions, S1.2–S1.4 can compute $\eta,\pi$, draw $u$ (when needed), and emit an event that the validator can reproduce byte-for-byte.

---

# S1.2 — Probability map (η → π), deterministic & overflow-safe (normative)

## Purpose

Given the frozen hurdle design vector $x_m$ and the single-YAML coefficient vector $\beta$ (from S1.1), compute the linear predictor

$$
\eta_m=\beta^\top x_m
$$

and the hurdle probability

$$
\pi_m=\sigma(\eta_m)\in[0,1],
$$

then pass $(\eta_m,\pi_m)$ forward to RNG (S1.3) and event emission (S1.4). The logistic definition and safe evaluation are fixed by the locked S1 text/combined doc.

---

## Inputs (recap; must already be validated in S1.1)

* **Design vector** $x_m=[1,\ \phi_{\mathrm{mcc}},\ \phi_{\mathrm{ch}},\ \phi_{\mathrm{dev}}]^\top\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$, column order frozen by the fitting bundle.
* **Coefficients** $\beta\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$ loaded atomically from `hurdle_coefficients.yaml`; shape/order **must** match $x_m$.

(Shape/order failures are handled at S1.1/S1.6; see failure semantics below.)

---

## Canonical definitions (math)

### Logistic map (normative)

$$
\sigma:\mathbb{R}\to(0,1),\qquad
\sigma(\eta)=\frac{1}{1+e^{-\eta}}.
$$

**Safe evaluation (two-branch form):**

$$
\sigma(\eta)=
\begin{cases}
\dfrac{1}{1+e^{-\eta}}, & \eta\ge 0,\\[6pt]
\dfrac{e^{\eta}}{1+e^{\eta}}, & \eta<0.
\end{cases}
$$

This is the exact algorithm the locked S1 prescribes. It prevents overflow/underflow in the numerator and keeps $\pi\in[0,1]$ in binary64.

### Linear predictor (fixed‐order dot product)

$$
\eta_m=\beta^\top x_m
$$

computed in IEEE-754 binary64 with a **fixed iteration order** over the frozen columns (Neumaier/Kahan compensation permitted). No reordering or BLAS is allowed on an ordering-critical path. (Policy from S0.8.)

---

## Deterministic regimes & consequences for S1.3

* **Typical case** $0<\pi_m<1$: RNG **will** consume exactly one $U(0,1)$ deviate for merchant $m$.
* **Saturated case** $\pi_m\in\{0,1\}$: this arises when the two-branch evaluation underflows to exactly 0 or 1 in binary64 for extreme $\eta_m$. In this regime **no draw occurs**; `u` is absent/null and the event is flagged deterministic at emission. The locked S1 schema & invariants explicitly allow/require this behaviour.

> Implementation note: do **not** clamp $\eta$ for computation. The earlier texts mention optional clipping only for *display*; the normative computation uses the two-branch logistic above and lets binary64 decide whether $\pi$ saturates.

---

## Numeric policy (must hold)

* **Format:** IEEE-754 **binary64**, RNE rounding; **no FMA**, **no FTZ/DAZ**; deterministic libm. (S0.8.)
* **Reduction:** fixed-order accumulation for $\beta^\top x$ (e.g., Neumaier).
* **Domains:** inputs must already satisfy channel ∈ {CP,CNP}, $b_m\in\{1,\dots,5\}$. (From S1.1/S0.5.)

---

## Output of S1.2 (to S1.3/S1.4)

For each merchant $m$, produce the pair

$$
(\eta_m,\ \pi_m),\quad \eta_m\in\mathbb{R}\ \text{finite},\ \ \pi_m\in[0,1].
$$

These are **not** persisted here; they feed S1.3 (Bernoulli) and S1.4 (event payload fields `eta`/`pi`). The locked event schema requires `pi` and (by I-H3) constrains `u/deterministic` based on whether $0<\pi<1$ or $\pi\in\{0,1\}$.

---

## Failure semantics (abort S1 / run)

Tie each predicate to S0.9 classes.

1. **Shape/order mismatch** when forming $\eta=\beta^\top x$
   → `E_DSGN_SHAPE_MISMATCH` (schema/authority) → **S0.9/F6** (or explicit S1 code), **run-abort**.
2. **Numeric invalid**: $\eta$ or $\pi$ non-finite after evaluation
   → `hurdle_nonfinite(merchant_id, field)` → **S0.9/F3**, **run-abort**.
3. **Out-of-range** (should be impossible with the two-branch): $\pi\notin[0,1]$
   → treat as **S0.9/F3**, **run-abort** with forensic payload ($\beta$ slice, $x$ indices).

---

## Validation & CI hooks (prove S1.2 is correct)

* **Recompute check:** In the validator, independently rebuild $x_m$ (S0.5 dictionaries) and re-evaluate $\eta,\pi$ in binary64; assert

  * $\eta$ is finite and
  * $\pi\in[0,1]$ with **bitwise** equality under the pinned math profile. (Numeric policy from S0.8.)
* **Deterministic regime linkage:** When later S1.4 records have `deterministic=true`/`u=null`, assert the recomputed $\pi$ is exactly 0 or 1 in binary64 (saturation), matching the locked invariant I-H3.
* **Budget linkage (S1.3):** Use $\pi$ to predict draw budget: `draws = 1` iff $0<\pi<1$; else `0`. Validator cross-checks against the `rng_trace_log`.

---

## Reference algorithm (language-agnostic, ordering-stable)

```text
function S1_2_probability_map(x_m, beta):
  # Preconditions (S1.1):
  #   len(beta) == len(x_m) and column order frozen/validated.

  # 1) Fixed-order dot product in binary64 (Neumaier compensation allowed)
  s = 0.0
  c = 0.0
  for i in 0..len(x_m)-1:         # exact column order from dictionaries
      y = beta[i] * x_m[i] - c
      t = s + y
      c = (t - s) - y
      s = t
  eta = s                         # finite float64 required

  # 2) Branch-stable logistic in binary64
  if eta >= 0.0:
      z = exp(-eta)               # finite; may underflow to 0 for huge eta
      pi = 1.0 / (1.0 + z)        # in [0,1]
  else:
      z = exp(eta)                # may underflow to 0 for large negative eta
      pi = z / (1.0 + z)          # in [0,1]

  # 3) Guards
  if not is_finite(eta): raise E_HURDLE_NONFINITE("eta")
  if not is_finite(pi):  raise E_HURDLE_NONFINITE("pi")
  if pi < 0.0 or pi > 1.0: raise E_HURDLE_OUT_OF_RANGE(pi)

  return (eta, pi)
```

* `exp` is the deterministic libm implementation pinned by the math profile; no FMA contraction on the divisions. (S0.8.)

---

## How S1.2 interacts with adjacent sections

* **Feeds S1.3:** $\pi_m$ determines the draw budget: exactly one $U(0,1)$ if $0<\pi<1$, else **zero**; the Bernoulli outcome is $\mathbf{1}\{u<\pi\}$.
* **Feeds S1.4:** `pi` is written in the payload; when $\pi\in\{0,1\}$, S1.4 **must** emit `deterministic=true` and `u=null/absent` per the hurdle schema and I-H3.

---

**Bottom line:** S1.2 fixes the only admissible way to compute $\eta$ and $\pi$: a fixed-order binary64 dot product followed by an overflow-safe two-branch logistic. This produces $\pi\in[0,1]$ deterministically, saturates to exactly 0 or 1 only via binary64 underflow (no ad-hoc clipping), and drives the precise draw budget and payload semantics required by S1.3–S1.4.

---

# S1.3 — RNG substream & Bernoulli trial (normative)

## Purpose

Given $\pi_m$ from S1.2, sample **at most one** uniform $u_m\in(0,1)$ from a **merchant-keyed** Philox substream labelled `"hurdle_bernoulli"`, decide

$$
\text{is_multi}(m)=\mathbf{1}\{u_m<\pi_m\},
$$

and emit exactly one hurdle event (payload formalised in S1.4). Substream mapping and open-interval uniforms are fixed by S0.3.3–S0.3.4.

---

## Inputs (already available at S1.3 entry)

* $\pi_m\in[0,1]$ and (optionally logged) $\eta_m$ from S1.2.
* Run lineage: `seed` (u64), `manifest_fingerprint`/`…_bytes`, `parameter_hash`, `run_id`, `module="1A.hurdle_sampler"`.
* Merchant identifier `merchant_id=m`.
* Dictionary-anchored stream id & path for hurdle events and RNG trace (S1.4 will write to these):
  `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` and
  `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`.

---

## Canonical substream (order-invariant; per merchant)

### Label

$$
\ell := \text{"hurdle_bernoulli"}.
$$

This **exact** string must also appear in the event envelope as `substream_label`.

### Base counter (keyed mapping)

Define the base Philox counter for the pair $(\ell,m)$ by S0.3.3:

$$
(c^{\text{base}}_{\mathrm{hi}},\,c^{\text{base}}_{\mathrm{lo}})\;
=\;\mathrm{split64}\!\Big(\mathrm{SHA256}\big(\text{"ctr:1A"}\ \|\ \texttt{manifest_fingerprint_bytes}\ \|\ \mathrm{LE64}(\texttt{seed})\ \|\ \ell\ \|\ \mathrm{LE64}(m)\big)[0{:}16]\Big).
$$

The $i$-th uniform for $(\ell,m)$ uses

$$
(c_{\mathrm{hi}},c_{\mathrm{lo}})=(c^{\text{base}}_{\mathrm{hi}},\ c^{\text{base}}_{\mathrm{lo}}+i)
\quad\text{with 64-bit carry into }c_{\mathrm{hi}}.
$$

This mapping is **pure** in $(\texttt{seed},\texttt{manifest_fingerprint},\ell,m,i)$ → **order-invariant across partitions**.

### Counter conservation (envelope law)

Every RNG event envelope must satisfy

$$
(\texttt{after_hi},\texttt{after_lo})=(\texttt{before_hi},\texttt{before_lo})+\texttt{draws}
$$

in unsigned 128-bit arithmetic, where “draws” denotes the **number of uniforms consumed** by the event. For hurdle, draws $\in\{0,1\}$ (see budget below). 

**Note:** the envelope **carries** both `blocks` and `draws`.
* `blocks`: integer count of counter increments (the u128 delta); for S1 (hurdle) `blocks ∈ {0,1}`.
* `draws`: **JSON string** carrying a base-10 uint128; `parse_u128(draws)` **must equal** `blocks`.
The companion `rng_trace_log` row also records the per-event draw count as an integer (`draws ∈ {0,1}` for S1).
Validators must enforce the equalities:
`u128(after) − u128(before) == blocks == parse_u128(draws)` and `trace_draws == blocks`.

---

## Uniform $u\in(0,1)$ (open interval; lane policy)

### Generator

RNG engine is Philox $2\times 64$-10 with key `seed`. Evaluate Philox at the event’s `before` counter and take a **single 64-bit word** $x$ (we do **not** reuse the second lane for a second uniform). Map it to $u$ via the layer-wide `u01` primitive:

$$
u\;=\;\frac{x+1}{2^{64}+1}\ \in\ (0,1).
$$

**Budget rule:** one uniform consumes **one** counter increment.

---

## Draw budget & decision logic

Let $\pi=\pi_m$.

* **Deterministic branch** ($\pi\in\{0,1\}$):
  `draws = 0`; set

  $$
  \text{is_multi} = 
  \begin{cases}
  0,& \pi=0,\\
  1,& \pi=1.
  \end{cases}
  $$

  No Philox call; envelope counters satisfy `after == before`. Event payload marks `u=null` and `deterministic=true` (per S1.4/I-H3).

* **Stochastic branch** ($0<\pi<1$):
  `draws = 1`; compute

  $$
  u = \frac{x+1}{2^{64}+1}\ \in\ (0,1),\qquad
  \text{is_multi}=\mathbf{1}\{u<\pi\}.
  $$

  Envelope counters satisfy `after = before + 1`. `u` must be present in payload and `deterministic=false`.

These rules are the locked S1 invariants (I-H2/I-H3) and S0.3.6 per-event expectations.

---

## Envelope & streams touched here (recap; S1.4 formalises payload)

Each hurdle event **must** carry the shared RNG envelope
`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module="1A.hurdle_sampler", substream_label="hurdle_bernoulli", rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }`
and be written to the dictionary path for `rng_event_hurdle_bernoulli`. S1 also emits one `rng_trace_log` row with the computed `draws`.

---

## Failure semantics (abort class bindings)

* **Envelope mismatch / label drift.** `substream_label` ≠ `"hurdle_bernoulli"` in the event, or missing required envelope fields
  → RNG envelope violation (**S0.9/F4**).
* **Counter conservation failure.**
  `after − before` (u128) ≠ `draws` (0 or 1 for hurdle)
  → draw-accounting failure (**S0.9/F4**).
* **Uniform out of range.** Observed `u` ≤ 0 or ≥ 1 in a stochastic branch
  → u01 violation (**S0.9/F4**, numeric/logging).
* **Determinism flag inconsistency.** `π∈{0,1}` but `u` present or `deterministic=false`; or $0<\pi<1$ but `u` absent
  → schema/invariant failure (**S0.9/F4**).

(Shape/order and non-finite errors are handled in S1.1–S1.2; they do not originate here.)

---

## Validation & CI hooks (must pass)

For each hurdle record:

1. **Rebuild the substream counter.** From `(seed, manifest_fingerprint_bytes, label="hurdle_bernoulli", merchant_id)`, recompute the base counter via subsection *Base counter (keyed mapping)* (identical to S0.3.3) and assert envelope `before` equals it.
2. **Recompute budget & decision.** Using $\pi$ from S1.2 and the envelope branch:

   * If `draws=0`: assert $\pi\in\{0,1\}$, `u==null`, `deterministic=true`, and `after==before`.
   * If `draws=1`: regenerate $x$ from Philox at `before`, map to $u$ via `u01`, assert $u\in(0,1)$ and `(u<π) == is_multi`, and `after = before + 1`.
3. **Trace reconciliation.** Join with `rng_trace_log` for the same row key and assert the `draws` field equals the envelope delta.
4. **Partition/embedding equality.** Path keys `{seed, parameter_hash, run_id}` equal the same fields embedded in the event.

---

## Reference algorithm (ordering-invariant; language-agnostic)

```text
INPUT:
  m : merchant_id (u64)
  pi : float64 in [0,1]
  seed : u64
  mf_bytes : 32-byte manifest_fingerprint_bytes
  now_utc_ns : u64
  ctx_envelope := {ts_utc, run_id, parameter_hash, manifest_fingerprint, module="1A.hurdle_sampler",
                   substream_label="hurdle_bernoulli"}

# 1) Base counter for (label, merchant)
buf = sha256( ASCII("ctr:1A") || mf_bytes || LE64(seed) || ASCII("hurdle_bernoulli") || LE64(m) )
before_hi = LE64_to_u64(buf[0:8])
before_lo = LE64_to_u64(buf[8:16])

# 2) Branch on pi
if (pi == 0.0) or (pi == 1.0):
    draws = 0
    after_hi, after_lo = before_hi, before_lo
    u_val = null
    is_multi = (pi == 1.0)
else:
    draws = 1
    # Philox2x64_10(seed, (before_hi, before_lo)) -> (x0, x1)
    x0 = philox2x64_10(seed, before_hi, before_lo).lo64
    u_val = (x0 + 1) / (2^64 + 1)    # open interval (0,1)
    is_multi = (u_val < pi)
    (after_hi, after_lo) = add_u128((before_hi, before_lo), 1)

# 3) Emit hurdle event (S1.4 defines payload)
emit_hurdle_event(
  envelope = ctx_envelope + {
      seed, rng_counter_before_hi=before_hi, rng_counter_before_lo=before_lo,
            rng_counter_after_hi=after_hi,   rng_counter_after_lo=after_lo
  },
  payload  = { merchant_id=m, pi=pi, u=u_val, is_multi=is_multi,
               deterministic = (draws == 0) }
)

# 4) Emit rng_trace_log row
emit_rng_trace(
  { ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
    module="1A.hurdle_sampler", substream_label="hurdle_bernoulli",
    rng_counter_before_hi=before_hi, rng_counter_before_lo=before_lo,
    rng_counter_after_hi=after_hi,   rng_counter_after_lo=after_lo,
    draws=draws }
)
```

All writes use the dictionary paths/partitions (events and trace), which are keyed by `{seed, parameter_hash, run_id}`.

---

## Invariants (S1/H) guaranteed by this section

* **I-H1 (bit-replay).** Fixing $(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the tuple $(u_m,\text{is_multi}(m))$ and the envelope counters are **bit-identical** across replays (keyed substream + open-interval `u01`).
* **I-H2 (consumption).** `draws=1` iff $0<\pi<1$; otherwise `draws=0`.
* **I-H3 (schema conformance).** `u` and `deterministic` are present/absent exactly as required by the hurdle schema (detailed in S1.4).
* **I-H4 (branch purity).** Hurdle decision feeds S2+; downstream must not override it.

---

**Bottom line:** S1.3 defines a **merchant-keyed**, **label-stable** Philox substream and a **single-uniform** Bernoulli decision that is order-invariant and fully auditable by counters. The counters, label, and dictionary paths make the event stream replayable and independently checkable by validation.

---

# S1.4 — Event emission (hurdle Bernoulli), with **exact** envelope/payload, partitioning, invariants, and validation

### 1) Where the records go (authoritative path + schema)

Emit one **JSONL** record per merchant to the hurdle event stream:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

The stream is **approved** in the dictionary and bound to the shared schema
`schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.

> Partition keys are `{seed, parameter_hash, run_id}` (dictionary-scoped).

### 2) Envelope (shared, required for **all** RNG events)

Every record must carry the **RNG envelope** defined once in the layer-wide schema:

* Required fields:
  `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi`.
  These names and types are fixed by `$defs.rng_envelope` and referenced by each RNG event schema.

* Semantics:

  * `ts_utc`: RFC-3339 timestamp (UTC) with `Z` and **exactly 6 fractional digits** (microseconds) at emit time.
  * `run_id`: log-only identifier from S0.2.4; partitions logs. (Dictionary and S0 establish scope.)
  * `seed`: the master Philox u64 seed (constant within a run).
  * `parameter_hash`, `manifest_fingerprint`: lineage keys bound at S0; they must match the run’s resolved values. (S0 and dictionary enforce this across logs/datasets.)
  * `module`: emitting module label (e.g., `"1A.hurdle_sampler"`).
  * `substream_label`: **must** be `"hurdle_bernoulli"`. (S1 fixes the sub-stream label; dictionary ties this event to S1.)
  * `rng_counter_before_*`, `rng_counter_after_*`: the Philox **2×64** counter **before** and **after** the draw(s), proving consumption. (Shared schema requires both.)

**Counter arithmetic for S1.4** (recap from S1.3):
Let $d_m=\mathbf{1}\{0<\pi_m<1\}$ be the **uniform draw count** per merchant. One Philox block yields two 64-bit words; For S1, the lane policy (single-use) implies **one uniform ⇒ one counter increment**. Let $d_m=\mathbf{1}\{0<\pi_m<1\}$. If $C^{\text{pre}}=(\text{hi},\text{lo})$ then $$C^{\text{post}}=(\text{hi},\text{lo})+d_m\quad\text{(u128)}.$$ Write these counters to the envelope exactly. If $C^\text{pre}=(\text{hi},\text{lo})$ then $C^\text{post}=\mathrm{advance}(C^\text{pre},d_m)$. These counters must be written to the envelope exactly. (S1.3 defines stride/jumps; envelope encodes the proof.)

### 3) Payload (event-specific)

The **payload** of `rng/events/hurdle_bernoulli` contains the merchant outcome and context. The stream’s dictionary entry and state text require:

* `merchant_id` (row key),
* `pi` (Bernoulli parameter on $[0,1]$),
* `is_multi` (Bernoulli outcome),
* `deterministic` (boolean; **true** iff $\\pi\\in\\{0,1\\}$),
* `u` **conditional** on the branch: present and in $(0,1)$ **only** when `deterministic=false`; **null** when `deterministic=true`.

> The dictionary binds this stream to `#/rng/events/hurdle_bernoulli`; the layer schema defines `u` via `$defs.u01` (exclusive bounds).
 
**Deterministic vs stochastic cases (branch-clean):**

**Deterministic vs stochastic cases (branch-clean):**

* If $0<\pi_m<1$: draw $u_m\sim\mathrm{U}(0,1)$ (*open interval*, schema `$defs.u01`), set
`is_multi=\mathbf{1}\{u_m<\pi_m\}`, `deterministic=false`, **consume 1 uniform** .
* If $\pi_m=0$: set `is_multi=0`, `deterministic=true`, `u=null`, **consume 0 uniforms** .
* If $\pi_m=1$: set `is_multi=1`, `deterministic=true`, `u=null`, **consume 0 uniforms**.
 
**Schema note (authoritative).**
The hurdle schema **requires** a `deterministic` boolean and enforces `u` **conditional** on the branch:
`u` is present in $(0,1)$ when `deterministic=false`, and `u` is `null` when `deterministic=true`. Any deviation is a schema failure.
 
1. **Schema-as-written (strict):** Always include `u` in $(0,1)$. For $\pi\in\{0,1\}$, you **do not** consume a block (counters unchanged) but you still set a conventional dummy `u` **only** if the hurdle schema explicitly allows it; otherwise **omit** `u` and make it optional in the event schema. *(If you keep `u` required & non-nullable, you cannot write a deterministic record without breaking the semantics.)*

2. **State-as-written:** Make `u` **nullable or optional** in the hurdle event schema and add a boolean `deterministic` flag; set `u=null, deterministic=true` when $\pi\in\{0,1\}$. *(This aligns the text; requires a tiny schema PR for the hurdle event type.)*

> The dataset dictionary already fixes **where** the stream lives and the envelope partitioning; only the hurdle event’s **payload schema** needs the final pick between (1) and (2).

### 4) Exact record layout (canonical JSON object)

Let `E` be the **envelope** and `P` the **payload**:

```json
{
  "ts_utc": "2025-08-15T10:03:12.345678Z",
  "run_id": "<hex32>",
  "seed": 1234567890123456789,
  "parameter_hash": "<hex64>",
  "manifest_fingerprint": "<hex64>",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "rng_counter_before_lo": 9876543210,
  "rng_counter_before_hi": 42,
  "rng_counter_after_lo": 9876543211,
  "rng_counter_after_hi": 42,

  "merchant_id": 184467440737095,     // payload begins
  "pi": 0.3725,
  "is_multi": false,
  "deterministic": false,
  "u": 0.1049,                        // present iff 0<pi<1 per schema choice
}
```

**Deterministic example (π ∈ {0,1}):**

```json
{
  "ts_utc": "2025-08-15T10:03:12.345678Z",
  "run_id": "<hex32>",
  "seed": 1234567890123456789,
  "parameter_hash": "<hex64>",
  "manifest_fingerprint": "<hex64>",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "rng_counter_before_lo": 9876543210, "rng_counter_before_hi": 42,
  "rng_counter_after_lo":  9876543210, "rng_counter_after_hi": 42,
  "merchant_id": 184467440737095, "pi": 1.0, "is_multi": true, "deterministic": true, "u": null
}
```


* The **top block** conforms to `$defs.rng_envelope`.
* The **payload keys** match the S1 state contract and dictionary binding.

> For deterministic records under option (2), set `"u": null, "is_multi": (pi==1)`, and add `"deterministic": true` **once** the hurdle event schema carries that field. *(Until then, keep option (1) and the schema as-is.)*

### 5) Write discipline, idempotency, and ordering

* **One row per merchant** $|\mathcal{M}|$ written to the stream (no duplicates). The dictionary scopes the stream to the run via `{seed, parameter_hash, run_id}`; write new `part-*` files to preserve append-only semantics.
* **Stable partitioning:** never include `manifest_fingerprint` in the hurdle event path (that key is for egress/validation datasets like `outlet_catalogue`).
* **Module/label stability:** always `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"`. (State & dictionary place the hurdle stream first; later streams depend on it.)
* **Trace linkage:** for each merchant, emit **exactly one** `rng_trace_log` row for sub-stream `"hurdle_bernoulli"` with `draws=d_m∈{0,1}` and the same `(seed, parameter_hash, run_id)` partition.

### 6) Validation hooks (what CI/replay must assert)

* **Schema conformance:** every record conforms to `#/rng/events/hurdle_bernoulli` + `$defs.rng_envelope`. (CI validates JSONL rows.)
* **Replay equality:** for each row, recompute $d_m, d_m$ from $\pi_m$, check `rng_counter_after = advance(rng_counter_before, d_m)`. (Trace gives independent proof via `draws`.)
* **Branch purity:** downstream RNG streams (`gamma_component`, `poisson_component`, `nb_final`, `dirichlet_gamma_vector`, `gumbel_key`, etc.) must **only** appear for merchants with a prior hurdle record where `is_multi=true`. (Dictionary lists all downstream streams used for validation joins.)
* **Cardinality:** hurdle stream row count == number of merchants in `merchant_ids` for the run. (Ingress authoritative schema + S1 contract.)

### 7) Failure semantics (abort classes surfaced by S1.4)

* **E_SCHEMA_HURDLE**: JSONL record fails `#/rng/events/hurdle_bernoulli` (missing envelope field; `u` violates open interval; type mismatch).
* **E_COUNTER_MISMATCH**: envelope `after` ≠ `before + d_m` (consumption proof fails).
* **E_BRANCH_GAP** (deferred to validation): any downstream RNG event for a merchant with **no** prior hurdle record or with `is_multi=false`. (S1 marks hurdle as the **first** RNG stream.)

### 8) Reference emission pseudocode (language-agnostic, exact fielding)

```python
def emit_hurdle_event(m, pi_m, ctx):
    # ctx carries: seed, parameter_hash, manifest_fingerprint, run_id,
    #              module="1A.hurdle_sampler",
    #              substream_label="hurdle_bernoulli",
    #              counter_before=(hi, lo), and time source ts_utc()
    draws = 1 if 0.0 < pi_m < 1.0 else 0
    before_hi, before_lo = ctx.counter_before

    if draws == 1:
        u = next_u01()                         # consumes one block; open interval (0,1)
        is_multi = (u < pi_m)
        after_hi, after_lo = advance((before_hi, before_lo), 1)
    else:
        u = None                               # if schema option (2); else omit or handle per option (1)
        is_multi = (pi_m == 1.0)
        after_hi, after_lo = (before_hi, before_lo)

    record = {
        "ts_utc": ts_utc(),
        "run_id": ctx.run_id,
        "seed": ctx.seed,
        "parameter_hash": ctx.parameter_hash,
        "manifest_fingerprint": ctx.manifest_fingerprint,
        "module": ctx.module,
        "substream_label": ctx.substream_label,
        "rng_counter_before_lo": before_lo,
        "rng_counter_before_hi": before_hi,
        "rng_counter_after_lo":  after_lo,
        "rng_counter_after_hi":  after_hi,

        "merchant_id": m,
        "pi": pi_m,
        # "u": u,   # include per final schema decision (see note in §3)
        "is_multi": is_multi
    }
    write_jsonl("logs/rng/events/hurdle_bernoulli/"
                f"seed={ctx.seed}/parameter_hash={ctx.parameter_hash}/run_id={ctx.run_id}/part-*.jsonl",
                record)
    # trace row with draws for the same substream
    emit_trace_row(label="hurdle_bernoulli", draws=draws, before=(before_hi,before_lo), after=(after_hi,after_lo))
```

Pseudocode aligns to: dictionary path & partitioning; shared envelope; hurdle payload; counter arithmetic; and trace linkage.

---

## Practical reconciliation (one-liner decision you need to make)

* **Pick one**:
  **(A)** keep **schema-as-is** and make `u` **required** for all records (which implies you **must** also keep the stochastic-only semantics purely in counters/trace, not in `u`’s nullability), **or**
  **(B)** apply a **tiny schema PR** to the hurdle event type to allow `u: null` and add `deterministic: boolean`, matching the S1 text exactly.

Either choice keeps the path/partitioning and envelope **unchanged** and remains compatible with the dataset dictionary and registry.

**Bottom line:** S1.4 produces a *provable* per-merchant record tying `(seed, parameter_hash, run_id)` to the hurdle decision with exact pre/post counters, and—subject to the small `u`/determinism schema choice—no ambiguity remains for replay or validation across the rest of 1A.

---

# S1.5 — Determinism & Correctness Invariants (normative)

## Purpose

Freeze the invariants that must hold for every merchant’s hurdle decision so that downstream states (NB/ZTP/Dirichlet/Gumbel) can **trust** and **replay** S1 exactly. The locked state explicitly enumerates the I-H invariants; below we expand them into precise predicates, proofs, and validations.

---

## I-H0 — Environment & schema authority (precondition)

* Numeric policy from S0.8 is in force: IEEE-754 **binary64**, RNE, **no FMA**, **no FTZ/DAZ**, serial fixed-order reductions; deterministic `exp` used by the two-branch logistic. Violations are S0.9 failures. (Referenced by S1.2/S0.8 and required here for bit stability.)
* All RNG records conform to the **shared envelope** in `schemas.layer1.yaml` and to their event-specific schema anchors. The hurdle stream is bound to `#/rng/events/hurdle_bernoulli`.

---

## I-H1 — Bit-replay (per merchant, per run)

**Statement.** For fixed inputs
$(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the tuple
$(u_m,\ \text{is_multi}(m))$ **and** the envelope counters $(C^{\text{pre}}_m,C^{\text{post}}_m)$ are **bit-identical** across replays and independent of emission order or sharding.

**Why it holds.** The keyed substream mapping pins the **base counter** for $(\ell=\text{"hurdle_bernoulli"}, m)$ from $(\texttt{seed},\texttt{manifest_fingerprint})$; draw budget is a pure function of $\pi_m$. Therefore `before`/`after` counters and the single uniform $u_m$ are deterministic functions of those keys.

**Validator.** Rebuild the base counter from the envelope keys and recompute $u_m$ when `draws=1`; assert exact equality of counters and the decision `(u<π) == is_multi`.

---

## I-H2 — Consumption & budget (single-uniform law)

**Statement.** Define $d_m=\mathbf{1}\{0<\pi_m<1\}$. Then the hurdle consumes **`draws = d_m`** uniforms:

* If $0<\pi_m<1$: `draws=1`; `after = before + 1` (u128).
* If $\pi_m\in\{0,1\}$: `draws=0`; `after = before`.

A companion `rng_trace_log` row records `draws` for this substream.

**Why it holds.** S1.2 defines $\pi_m$ and the **saturated branch**; S1.3 maps one Philox 64-bit word to $u\in(0,1)$; S1 uses **no** second lane.

**Validator.** Check `after − before == draws` and that the trace row’s `draws` matches this delta.

---

## I-H3 — Schema-level payload discipline

**Statement (state-as-written).** The hurdle record includes payload keys `{merchant_id, pi, is_multi, u}` with:

* If $0<\pi<1$: `u ∈ (0,1)` (schema `$defs.u01`), `deterministic=false`.
* If $\pi\in\{0,1\}$: `u=null`, `deterministic=true`.
  Any deviation is a schema failure. (This is how the locked S1 describes deterministic rows.)

> Note: The dataset dictionary pins the stream and envelope; if the concrete JSON-Schema for the hurdle event remains **non-nullable** for `u`, a tiny schema PR is needed so the state and schema align (you already flagged this in S1.4). The invariants above are the **intended** contract.

---

## I-H4 — Branch purity (downstream gating)

**Statement.** Downstream RNG streams may **only** appear when the hurdle decided **multi**:

$$
\text{is_multi}(m)=1 \implies \text{merchant } m \text{ may produce NB/ZTP/Dirichlet/Gumbel events;}
$$

$$
\text{is_multi}(m)=0 \implies \text{no such events appear for } m.
$$

Validators join on merchant_id across streams declared in the dictionary to enforce this gate.

---

## I-H5 — Cardinality & uniqueness (per run)

* Exactly **one** hurdle record per merchant per $(\texttt{seed},\texttt{parameter_hash},\texttt{run_id})$ partition. No duplicates.
* Hurdle is the **first** RNG event stream in 1A; later event families must find a prior hurdle record for the merchant (enforced by validation rules).

**Validator.** Count hurdle rows and assert equality with `merchant_ids` for the run; assert uniqueness of `(merchant_id)` within the hurdle partition.

---

## I-H6 — Envelope completeness & equality with path keys

* Every record contains the **full** RNG envelope fields required by `$defs.rng_envelope`. Missing any field is a hard schema failure.
* The embedded `{seed, parameter_hash, run_id}` in the record **equal** the same keys in the path
  `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`. Mismatch is a partitioning failure.

---

## I-H7 — Order-invariance & concurrency safety

* Emission **order is unspecified**; correctness depends only on per-row content. Replays reproduced on a different shard order must yield byte-identical envelope counters and outcomes (I-H1).
* Writers may produce multiple `part-*` files; set equivalence of rows defines dataset equivalence. (Dictionary leaves ordering unconstrained.)

---

## I-H8 — Independence across merchants & substreams

* Base counters are **disjoint** across distinct `(label, merchant_id)` pairs under the keyed mapping, making collisions impossible given fixed `seed` and `manifest_fingerprint`. Hence no cross-merchant interference.
* The `substream_label` in the envelope is **exactly** `"hurdle_bernoulli"`, preventing accidental reuse of counters intended for other labels.

---

## I-H9 — Optional diagnostics remain out of band

* If `hurdle_pi_probs` is materialised (S0.7), it is **parameter-scoped** and **never** consulted by samplers; S1’s decisions must match an independent recomputation of $(\eta,\pi)$ from $x_m,\beta$. Validators can cross-check for sanity but the cache is not authoritative.

---

## I-H10 — Replay equations (what the validator recomputes)

For each hurdle row $r$ with merchant $m$:

1. Recompute $(\eta_m,\pi_m)$ from S1.2 rules (fixed-order dot + safe logistic). Assert finiteness and $\pi\in[0,1]$.
2. Rebuild the **base counter** for $(\ell,m)$ and assert `rng_counter_before == base_counter`.
3. From $\pi$, get `draws = 1{(0<π<1)}` and `after = before + draws`. Assert envelope equality and match to the trace row.
4. If `draws=1`, regenerate $u$ via u01 and assert $u\in(0,1)$ and `(u < π) == is_multi`. If `draws=0`, assert the payload follows the deterministic branch rules (I-H3).

---

## Failure bindings (S0.9 classes surfaced by these invariants)

* **Envelope missing/label drift/counter mismatch** → RNG envelope & accounting failure **F4** (abort run).
* **Partition mismatch (path vs embedded keys)** → lineage/partition failure **F5** (abort run).
* **Schema breach (`u` not in (0,1) when required; absent fields)** → schema failure (treated as **F4** because it breaks RNG event contract).
* **Downstream without prior hurdle** → coverage/gating failure (validator), classified under event-family coverage (**F8**).

---

## What this guarantees downstream

* **Deterministic hand-off**: every merchant carries a single hurdle decision and a next counter cursor that downstream states must use; RNG continuity is mechanical (`before(next) == after(hurdle)`).
* **Auditable lineage**: the dictionary partitions hurdle events by `{seed, parameter_hash, run_id}` and validation bundles by `{fingerprint}`; consumers can verify the correct bundle with the fingerprint before reading egress.

---

**Bottom line:** S1.5 nails the **ten invariants** that make S1 reproducible: keyed substreams + single-uniform budget, envelope & path equality, payload discipline (including the deterministic branch), uniqueness/cardinality, and downstream gating. Each is backed by a concrete validator check and mapped to S0.9 failure classes, so violations halt the run with an actionable forensic trail.

---

# S1.6 — Failure modes (normative, abort semantics)

**Scope.** Failures here are specific to S1 (hurdle): design/$\beta$ misuse, numeric invalids, schema/envelope breaches, RNG counter/accounting errors, partition drift, and downstream gating. The locked S1 already lists the three headline bullets; below we fully formalize them and extend to all places S1 can break.

**Authoritative references (used below):**

* Event schema & shared envelope in `schemas.layer1.yaml` (e.g., `$defs.rng_envelope`, `#/rng/events/hurdle_bernoulli`, `$defs.u01`).
* Dataset dictionary paths/partitions for hurdle events and RNG trace.
* Locked S1 invariants I-H1..I-H4 and the “failure modes” bullets.

---

## Family A — Design / coefficients misuse (compute-time hard abort)

**A1. `beta_length_mismatch`**
**Predicate.** `len(β) ≠ 1 + C_mcc + 2 + 5` when forming $\eta_m=\beta^\top x_m$.
**Detect at.** S1.2 entry (or earlier guard in S1.1). **Abort run.**
**Forensics.** `{expected_len, observed_len, mcc_cols, channel_cols, bucket_cols}`.
**Why.** Locked S1 calls out *design/coefficients mismatch* as abort.

**A2. `unknown_category`**
**Predicate.** `mcc_m` not in the MCC dictionary, or `channel_m` ∉ {CP, CNP}, or `b_m` ∉ {1..5}.
**Detect at.** S1.1/S1.2 preprocessing. **Abort run.**
**Forensics.** `{merchant_id, field, value}`.

**A3. `column_order_mismatch`**
**Predicate.** Encoder dictionary orders do not match the order implied by `β`’s bundle metadata (frozen column order).
**Detect at.** S1.1 design load. **Abort run.**
**Forensics.** `{block: "mcc|channel|bucket", dict_digest, beta_digest}`.

---

## Family B — Numeric invalids (compute-time hard abort)

**B1. `hurdle_nonfinite_eta`**
**Predicate.** $\eta_m$ non-finite after fixed-order dot product (binary64).
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta}`.
**Why.** Locked S1 lists *numeric invalid* as abort.

**B2. `hurdle_nonfinite_pi`**
**Predicate.** $\pi_m$ non-finite (or $\pi\notin[0,1]$) after the two-branch logistic.
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta, pi}`.
**Notes.** With the safe logistic, $\pi\notin[0,1]$ should be impossible; treat as hard error.

---

## Family C — Envelope & accounting (RNG/logging hard abort)

**C1. `rng_envelope_schema_violation`**
**Predicate.** Any missing/wrongly-typed **envelope** field required by `$defs.rng_envelope`:
`{ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}}`.
**Detect at.** Writer and validator schema checks. **Abort run.**
**Forensics.** `{dataset_id, path, missing_or_bad: [...]}`.

**C2. `substream_label_mismatch`**
**Predicate.** Envelope `substream_label` ≠ `"hurdle_bernoulli"`.
**Detect at.** Writer assertion; validator. **Abort run.**
**Why.** Label is fixed by S1 and schema/dictionary binding.

**C3. `rng_counter_mismatch`**
**Predicate.** `u128(after) − u128(before) ≠ draws`, where hurdle `draws ∈ {0,1}`.
**Detect at.** Writer (when emitting trace) and validator reconciliation. **Abort run.**
**Why.** S1 invariants require exact counter conservation; dictionary gives the trace stream to verify.

**C4. `rng_trace_missing_or_mismatch`**
**Predicate.** Missing companion `rng_trace_log` row for the same `(seed, parameter_hash, run_id, label="hurdle_bernoulli")`, or `trace.draws ≠ delta_counters`.
**Detect at.** Validator join. **Abort run.**

**C5. `u_out_of_range`**
**Predicate.** In a stochastic branch (`0<π<1`), payload `u` not in `(0,1)` (violates `$defs.u01`).
**Detect at.** Writer check; validator schema + re-derivation. **Abort run.**

---

## Family D — Payload/schema discipline (hurdle event)

**D1. `hurdle_payload_violation`**
**Predicate.** Record fails `#/rng/events/hurdle_bernoulli` required payload keys: `merchant_id`, `pi`, `u`, `is_multi` (per the current schema), or types/ranges violate `$defs` (`pct01`, `u01`).
**Detect at.** Writer schema validation; CI validator. **Abort run.**

**D2. `deterministic_branch_inconsistent`**
**Two equivalent contracts exist; choose one and enforce consistently:**

* **State-as-written** (locked S1 narrative): if $\pi\in\{0,1\}$ then `u=null` and `deterministic=true`; else `u∈(0,1)` and `deterministic=false`.
* **Schema-as-written** (current hurdle schema): `u` is **required** and must be in `(0,1)`; to permit `u=null` add a tiny schema PR.
  **Predicate.** Event violates the chosen contract.
  **Detect at.** Writer; validator. **Abort run.**

---

## Family E — Partitioning & lineage coherence (paths vs embedded)

**E1. `partition_mismatch`**
**Predicate.** Path keys for the hurdle stream (dictionary-pinned)
`logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
do **not** equal the same embedded envelope fields.
**Detect at.** Writer; validator lint. **Abort run.**

**E2. `wrong_dataset_path`**
**Predicate.** Hurdle events written under a path that does not match the dictionary `schema_ref` + `path` template.
**Detect at.** Writer; validator path lint. **Abort run.**

---

## Family F — Coverage & gating (cross-stream structural)

**F1. `logging_gap_no_prior_hurdle`**
**Predicate.** Any downstream RNG event (Gamma/Poisson/NB final/…) observed for merchant `m` **without** a prior hurdle record with `is_multi=true` in this run.
**Detect at.** Validator cross-stream join. **Run invalid** (treat as hard failure).

**F2. `duplicate_hurdle_record`**
**Predicate.** More than one hurdle record for the same merchant in the same `{seed, parameter_hash, run_id}` partition.
**Detect at.** Validator uniqueness check. **Abort run.**
**Why.** Locked S1 requires one record per merchant.

**F3. `cardinality_mismatch`**
**Predicate.** `count(hurdle_records) ≠ count(merchant_ids)` for the run.
**Detect at.** Validator count check. **Abort run.**

---

## Error object (forensics payload; exact fields)

Every S1 failure MUST be emitted as a JSON object alongside the validation bundle (and/or `_FAILED.json` sentinel) with the envelope lineage:

```json
{
  "failure_code": "rng_counter_mismatch",
  "state": "S1",
  "module": "1A.hurdle_sampler",
  "dataset_id": "logs/rng/events/hurdle_bernoulli",
  "merchant_id": "m_0065F3A2",
  "detail": {
    "before": {"hi": 42, "lo": 9876543210},
    "after":  {"hi": 42, "lo": 9876543211},
    "draws_expected": 1,
    "trace_draws": 0
  },
  "seed": 1234567890,
  "parameter_hash": "<hex64>",
  "manifest_fingerprint": "<hex64>",
  "run_id": "<hex32>",
  "ts_utc": "2025-08-15T10:12:03.123456Z"
}
```

This mirrors the envelope fields and the dictionary dataset id for unambiguous triage. (Envelope fields and dataset ids are authoritative in schema/dictionary.)

---

## Where to detect (first line) & who double-checks

| Family / Code                  | First detector (runtime)         | Secondary (validator / CI)       |
|--------------------------------|----------------------------------|----------------------------------|
| A1–A3 design/$\beta$                 | S1.1/S1.2 guards                 | N/A (build lints, optional)      |
| B1–B2 numeric invalid          | S1.2 evaluation guards           | Validator re-eval $\eta,\pi$     |
| C1 envelope schema             | Writer JSON-Schema check         | Validator schema pass            |
| C2 label mismatch              | Writer assertion                 | Validator                        |
| C3 counter mismatch            | Writer + trace emission          | Validator counter reconciliation |
| C4 trace missing/mismatch      | —                                | Validator trace join             |
| C5 u out of range              | Writer check                     | Validator (`u01` + recompute)    |
| D1 payload schema              | Writer JSON-Schema check         | Validator schema pass            |
| D2 deterministic inconsistency | Writer assertion                 | Validator recompute branch       |
| E1 partition mismatch          | Writer path/embed equality check | Validator path lint              |
| E2 wrong dataset path          | —                                | Validator dictionary lint        |
| F1 logging gap                 | —                                | Validator cross-stream gating    |
| F2 duplicate record            | —                                | Validator uniqueness             |
| F3 cardinality mismatch        | —                                | Validator row count vs ingress   |

(“Writer” = the hurdle sampler emitter; “Validator” = the harness reading dictionary paths & schemas.)

---

## Validator assertions (executable checklist)

Using the dictionary’s paths and schema refs:

1. **Schema:** validate hurdle events and trace rows against `schemas.layer1.yaml` anchors (envelope + event).
2. **Counters:** assert `after = before + draws` (u128) and `trace.draws == draws`.
3. **Decision:** recompute $\eta,\pi$ (S1.2 rules) and, for stochastic rows, regenerate $u$ from the keyed counter; assert `(u<π) == is_multi` and `u ∈ (0,1)`.
4. **Deterministic regime:** if `draws=0`, assert `π ∈ {0,1}` and the payload follows the chosen contract (nullable-u or required-u).
5. **Partition lint:** path keys `{seed, parameter_hash, run_id}` equal the same embedded envelope values.
6. **Gating:** ensure every downstream RNG event for a merchant has a prior hurdle record with `is_multi=true`.
7. **Uniqueness & cardinality:** one hurdle row per merchant; count equals `merchant_ids`.

---

## Minimal examples (concrete)

* **Numeric invalid (B2).** `pi` equals `NaN` after logistic → `hurdle_nonfinite_pi` → abort. (Locked S1: *numeric invalid → abort*.)
* **Envelope gap (C1).** Missing `rng_counter_after_hi` → `rng_envelope_schema_violation` → abort. (Envelope fields required by schema.)
* **Gating failure (F1).** `rng_event_nb_final` exists for merchant `m` without prior hurdle `is_multi=true` → `logging_gap_no_prior_hurdle` → run invalid. (Dictionary binds streams; hurdle is first.)

---

**Bottom line:** S1 fails **fast** and **loud** when designs don’t match, numbers go non-finite, envelopes drift, counters don’t conserve, partitions lie, or downstream streams appear without the hurdle gate. The predicates, error codes, forensics payloads, and validator steps above are sufficient to implement production-grade checks that are perfectly aligned with your locked S1, schemas, and dictionary.

---

# S1.7 — Outputs of S1 (state boundary, normative)

## A) Authoritative event stream that S1 **must** persist

For every merchant $m\in\mathcal{M}$, S1 writes **exactly one** JSONL record to the hurdle event stream:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

**Schema (fixed):** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.
**Dictionary binding (fixed):** `id: rng_event_hurdle_bernoulli`, partitioned by `{seed, parameter_hash, run_id}`, produced by `1A.hurdle_sampler`.

**Envelope (shared; required for all RNG events):**
`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label="hurdle_bernoulli", rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi }`. (From the layer-wide `$defs.rng_envelope`.)

**Payload (authoritative):**
`{ merchant_id, pi=π_m, is_multi, deterministic, u }`, where `u` is present (and in `(0,1)`) iff `deterministic=false`, and `u=null` when `deterministic=true`. (Optional context permitted by schema: `eta`, `gdp_bucket_id=b_m`, `mcc`, `channel`.)
 
**Companion trace:** one row in `rng_trace_log` for the same substream/partition proving draw accounting (`after = advance(before, d_m)`, with `draws∈{0,1}` for hurdle). The dictionary pins its path and schema.

> These hurdle records are the **only authoritative source** for the decision and the exact counter evolution that S2 must start from.

---

## B) In-memory **handoff tuple** to downstream (typed, deterministic)

S1 does not persist a “state table”; instead, it yields a typed tuple per merchant to the orchestrator:

$$
\boxed{\ \Xi_m \;=\; \big(\ \text{is_multi}(m),\ N_m,\ K_m,\ \mathcal{C}_m,\ C_m^{\star}\ \big)\ }.
$$

**Field semantics (normative):**

* $\text{is_multi}(m)\in\{0,1\}$ — the hurdle outcome (from the event payload).
* $N_m\in\mathbb{N}$ — **target outlet count** used by S2 (NB branch) when $\text{is_multi}=1$; for the single-site path set $N_m:=1$ by convention.
* $K_m\in\mathbb{N}$ — **non-home country budget**; initialise $K_m:=0$ on the single-site path; multi-site assigns later in cross-border/ranking.
* $\mathcal{C}_m\subseteq\mathcal{I}$ — **country set accumulator**; initialise $\{\text{home}(m)\}$, expand only in S2+/S3+.
* $C_m^{\star}\in\{0,\dots,2^{64}\!-\!1\}^2$ — **RNG counter cursor after hurdle** for $m$: **exactly** the event’s `{rng_counter_after_hi, rng_counter_after_lo}`. **The very next labelled RNG event for $m$ must start with `rng_counter_before = C_m^{\star}`.**

**Branch semantics (deterministic split):**

* If $\text{is_multi}(m)=0$:
  $\boxed{N_m\leftarrow1,\;K_m\leftarrow0,\;\mathcal{C}_m\leftarrow\{\text{home}(m)\}}$,
  **skip S2–S6** and jump to **S7** (single-home placement) with RNG starting at $C_m^{\star}$. No NB/Dirichlet/Poisson/ZTP/Gumbel streams may appear for $m$.
* If $\text{is_multi}(m)=1$:
  proceed to **S2** (NB branch) and **the first NB-labelled event must use `rng_counter_before = C_m^{\star}`**.

This defines a **pure, replayable** control-flow boundary: downstream states consume $\Xi_m$ only; they never “re-decide” the hurdle.

---

## C) Downstream visibility (for validation & joins)

Validators and downstream readers use the dictionary to discover the next streams for merchants with $\text{is_multi}=1$, all partitioned by `{seed, parameter_hash, run_id}`:

* `logs/rng/events/gamma_component/...` (`#/rng/events/gamma_component`),
* `logs/rng/events/poisson_component/...` (`#/rng/events/poisson_component`),
* `logs/rng/events/nb_final/...` (`#/rng/events/nb_final`).

The **gating rule** is enforced: these streams **must** be absent for merchants without a prior hurdle `is_multi=true`.

---

## D) Optional diagnostic dataset (parameter-scoped; not consulted by samplers)

If enabled (often produced in S0.7), S1/S0 may persist a diagnostic:

```
data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/…
```

**Schema:** `#/model/hurdle_pi_probs`. **Contents (per merchant):** `{manifest_fingerprint, merchant_id, logit=η_m, pi=π_m}`.
This table is **read-only** and **never** consulted by S2+; it exists for debugging/QA and lineage checks.

---

## E) Boundary invariants (must hold when S1 ends)

1. **Single emit:** exactly one hurdle record per merchant per `{seed, parameter_hash, run_id}`, and exactly one $\Xi_m$.
2. **Counter continuity:** the **next** event’s envelope for $m$ must satisfy `rng_counter_before == C_m^{\star}`.
3. **Branch purity:** downstream RNG streams appear **iff** $\text{is_multi}=1$; single-site path performs **no** NB/ZTP/Dirichlet/Gumbel draws.
4. **Lineage coherence:** logs use `{seed, parameter_hash, run_id}`; any egress/validation later uses `fingerprint={manifest_fingerprint}` (recall S0.10). Embedded keys equal path keys.
5. **Numeric consistency:** the `pi` in the hurdle payload equals the recomputed $π_m$ from S1.2 (fixed-order dot + safe logistic).

---

## F) Minimal handoff construction (reference)

```text
INPUT:
  hurdle_event for merchant m (envelope + payload), home_iso(m)

OUTPUT:
  Xi_m = (is_multi, N_m, K_m, C_m, C_star_m)

1  is_multi := hurdle_event.payload.is_multi                # 0 or 1
2  C_star_m := (envelope.rng_counter_after_hi, envelope.rng_counter_after_lo)

3  if is_multi == 0:
4      N_m := 1
5      K_m := 0
6      C_m := { home_iso(m) }
7      next_state := S7
8  else:
9      N_m := ⊥   # to be sampled in S2 (NB)
10     K_m := ⊥   # will be set in cross-border/ranking
11     C_m := { home_iso(m) }
12     next_state := S2

13  return Xi_m, next_state
```

This mirrors the locked S1 boundary and is sufficient for an orchestrator to route merchants deterministically into S2 or S7.

---

**Bottom line:** S1 outputs **one** persisted hurdle event (with envelope + payload) and a **precise** in-memory tuple $\Xi_m$ that pins RNG continuity and the branching path. The dictionary paths and schemas make discovery and validation deterministic; downstream streams for multi-site merchants can be verified and replayed starting from $C_m^{\star}$, while single-site merchants bypass S2–S6 to S7.

---

# S1.V — Validator & CI (normative)

## V0. Purpose & scope

Prove that every hurdle record is (a) schema-valid, (b) numerically correct under the pinned math policy, (c) RNG-accounted (counters ↔ draw budget), (d) partition-coherent, and (e) structurally consistent with downstream streams (gating). Hurdle is the **first** RNG event stream in 1A; validator uses the dataset dictionary paths and S1 invariants to check the run.

---

## V1. Inputs the validator must read

1. **Locked state specs:** `state.1A.s1.txt` (source of truth for S1 rules) and the combined journey spec (for joins to later streams).
2. **Event datasets (logs):**

   * Hurdle events:
     `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (schema `#/rng/events/hurdle_bernoulli`).
   * RNG trace:
     `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`. (Trace proves `draws` per substream.)
   * Downstream streams used for gating (appear **only** if `is_multi=true`):
     `gamma_component`, `poisson_component`, `nb_final`.
3. **Design/$\beta$ artefacts:** frozen encoders/dictionaries and `hurdle_coefficients.yaml` (single-YAML $\beta$).
4. **Lineage keys & run context:** `(seed, parameter_hash, manifest_fingerprint, run_id)` are read from the records and path partitions; RNG envelope is required by the layer.

---

## V2. Discovery & partition lint (dictionary-backed)

* **Locate** the hurdle event partition for the run via the path template above. The **embedded** envelope keys `{seed, parameter_hash, run_id}` **must equal** the path keys for every row; mismatch is a partition failure.
* **Schema anchors** for hurdle and trace are fixed by the layer schema set. The hurdle payload keys are `{merchant_id, pi, is_multi, deterministic, u}`; envelope per `$defs.rng_envelope`. 

**Checks (discovery stage):**

* P-1: path exists for hurdle; P-2: at least one `part-*`; P-3: hurdle row count equals the ingress merchant count for the run; uniqueness of `merchant_id` within the hurdle partition. (Hurdle emits exactly one row per merchant.)

---

## V3. Schema conformance (row-level)

Validate **every** hurdle record against:

* **Envelope:** `{ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo}}`. Missing any is a hard schema failure. 
* **Payload:** `{merchant_id, pi, is_multi, deterministic, u}`, with `u` **required** (and `0<u<1`) when `deterministic=false`, and `u` **null** when `deterministic=true`.
 
> The locked hurdle schema and this state text both require `deterministic` and conditional `u` as above; deterministic rows **must** carry `u:null`, stochastic rows **must** carry `0<u<1`.

---

## V4. Recompute η and π (numeric truth)

For each merchant $m$:

1. Rebuild the frozen design vector $x_m$ from the encoders (intercept | MCC one-hot | channel one-hot | 5 GDP-bucket dummies). Enforce domain: MCC known, channel ∈ {CP,CNP}, bucket ∈ {1..5}.
2. Load $\beta$ atomically from `hurdle_coefficients.yaml`; assert $|\beta|=1+C_{mcc}+2+5$ and column order equality with encoders.
3. Compute $\eta_m=\beta^\top x_m$ in binary64, fixed order; compute $\pi_m$ with the overflow-safe two-branch logistic. Assert finiteness and $\pi\in[0,1]$.

**Fail fast:** any non-finite $\eta,\pi$ or shape/order mismatch is a **hard abort** (S1 failure class).

---

## V5. RNG replay & counter accounting (per row)

Let the hurdle label be `substream_label = "hurdle_bernoulli"` (must match exactly).

For each hurdle record:

1. **Budget from π:** `draws_expected = 1` iff $0<\pi<1$; else `0`. (Hurdle is single-uniform.)
2. **Counter conservation:** compute `delta = u128(after) − u128(before)` and assert `delta == blocks`.
3. **Lane policy check (S1):** assert `u128(after) − u128(before) ∈ {0,1}`; any delta > 1 is a lane policy violation.
4. **Trace and envelope reconciliation:** find the companion `rng_trace_log` row (join on `{seed, parameter_hash, run_id, substream_label, merchant_id}`) and assert:
   - `trace_draws == draws_expected`,
   - `u128(after) − u128(before) == draws_expected`,
   - `blocks == draws_expected`, and
   - `parse_u128(draws) == draws_expected`.
5. **Deterministic vs stochastic branch:** (unchanged)
   * If `draws_expected = 0`: assert the payload follows the deterministic contract: `is_multi = 0` when $\pi=0$, `is_multi=1` when $\pi=1$; and either `u=null, deterministic=true` (state contract) **or** `u` omitted per the chosen schema contract.
   * If `draws_expected = 1`: regenerate the uniform $u$ from the keyed Philox at `before` using the layer’s `u01` (exclusive bounds) and assert `(u<π) == is_multi` and `0<u<1`.

*(The keyed mapping and label come from S0/S1; validator doesn’t need to re-derive the base counter formula beyond using the envelope `before` counter and label to generate $u$ deterministically.)*

---
**Naming (S1):** use `draws_expected` (from π), `trace_draws` (from trace), and (optionally) `delta_counters = u128(after) − u128(before)`; avoid `draws_observed`.


## V6. Cross-stream gating (branch purity)

Build the **set of allowed multi merchants**
$\mathcal{H}_1=\{m:\ \text{hurdle.is_multi}(m)=1\}$.
For **every** downstream RNG event row from `{gamma_component, poisson_component, nb_final}`, assert `merchant_id ∈ 𝓗₁`; else raise `logging_gap_no_prior_hurdle`. Hurdle is first; downstream may not appear without it.

---

## V7. Cardinality & uniqueness

* **Uniqueness:** exactly **one** hurdle record per `merchant_id` within the partition `{seed, parameter_hash, run_id}`.
* **Coverage:** `count(hurdle_records) == count(merchant_ids)` for the run.
  Failures are run-blocking.

---

## V8. Partition equality & path authority

For each hurdle row, assert:

* Embedded `{seed, parameter_hash, run_id}` equal the **path** keys.
* `substream_label == "hurdle_bernoulli"`; `module` is the expected S1 module name.
  Mismatch is a lineage/partition failure.

---

## V9. Optional diagnostics (non-authoritative)

If `hurdle_pi_probs/parameter_hash={parameter_hash}` exists, **do not** use it to verify decisions; at most, compare its `(η,π)` against recomputed values for sanity. Decisions are proven only by replaying S1.2 + S1.3.

---

## V10. Failure objects (forensics payload; exact keys)

Emit one JSON object per failure with envelope lineage and a precise code:

```json
{
  "state": "S1",
  "dataset_id": "logs/rng/events/hurdle_bernoulli",
  "failure_code": "rng_counter_mismatch",
  "merchant_id": "m_0065F3A2",
  "detail": {
    "rng_counter_before": {"hi": 42, "lo": 9876543210},
    "rng_counter_after":  {"hi": 42, "lo": 9876543211},
    "draws_expected": 1,
    "trace_draws": 0,
    "pi": 0.37,
    "u": 0.55
  },
  "seed": 1234567890,
  "parameter_hash": "<hex64>",
  "manifest_fingerprint": "<hex64>",
  "run_id": "<hex32>",
  "ts_utc": "2025-08-15T10:12:03.123456Z"
}
```

Codes map 1:1 to S1.6 families (`beta_length_mismatch`, `hurdle_nonfinite_pi`, `rng_envelope_schema_violation`, `substream_label_mismatch`, `rng_counter_mismatch`, `rng_trace_missing_or_mismatch`, `u_out_of_range`, `hurdle_payload_violation`, `deterministic_branch_inconsistent`, `partition_mismatch`, `wrong_dataset_path`, `logging_gap_no_prior_hurdle`, `duplicate_hurdle_record`, `cardinality_mismatch`).

---

## V11. End-of-run verdict & artifact

* If **any** check fails ⇒ **RUN INVALID**. Emit a `_FAILED.json` sentinel with aggregated stats and the list of failure objects; CI blocks the merge.
* If all checks pass ⇒ **RUN VALID**. Optionally record summary metrics (row counts, draw histograms, min/max/mean π, u-bounds). (Downstream gating still re-checked later, but S1.V provides the first hard gate.)

---

## CI integration (blocking gate)

### CI-1. Job matrix

Run the validator across:

* **All changed parameter bundles** (distinct `parameter_hash`) and a **seed matrix** (e.g., 3 fixed seeds per PR).
* At least one **prior manifest fingerprint** (to catch regressions vs the last known good).

### CI-2. Steps

1. **Schema step:** validate JSONL rows in hurdle + trace against the anchors; fail on first error.
2. **Partition step:** path ↔ embedded equality; ensure stream IDs & labels match exactly.
3. **Replay step:** recompute $η,π$ and the budget; regenerate $u$ when needed; check decision & counters; join to trace.
4. **Gating step:** enforce “downstream only after `is_multi=true`”.
5. **Cardinality/uniqueness:** one hurdle row per merchant; counts match ingress.

### CI-3. What blocks the merge

* Any schema violation, partition mismatch, counter/trace mismatch, non-finite numeric, deterministic-branch inconsistency, gating failure, or cardinality/uniqueness failure. (Exact codes from S1.6.)

### CI-4. Provenance in the validation bundle

Record a compact summary of S1.V in the run’s validation payload (fingerprint-scoped): counts, pass/fail status, and—if you choose—diagnostic text files (`SCHEMA_LINT.txt` / `DICTIONARY_LINT.txt`) for human inspection. (Bundle scoping is fingerprint-based per S0; logs remain log-scoped.)

---

## Reference validator outline (language-agnostic)

```text
INPUT:
  paths from dictionary; encoders; beta; run keys (seed, parameter_hash, run_id)

LOAD:
  H := read_jsonl(hurdle partition)
  T := read_jsonl(trace partition)
  S := {read downstream streams}

# 1) schema
assert_all_schema(H, "#/rng/events/hurdle_bernoulli")
assert_all_schema(T, "#/rng/core/rng_trace_log")

# 2) partition equality
for e in H: assert path_keys(e) == embedded_keys(e)

# 3) recompute (η, π) and budget
for e in H:
  x_m := rebuild_design(m)                   # domain checks
  beta := load_beta_once()
  eta, pi := fixed_order_dot_and_safe_logistic(x_m, beta)
  draws := 1 if 0 < pi < 1 else 0

  # 4) counters & trace
  assert u128(e.after) - u128(e.before) == draws
  assert T.match(e).draws == draws

  # 5) branch-specific checks
  if draws == 0:
     assert (pi == 0 and !e.is_multi) or (pi == 1 and e.is_multi)
     assert deterministic_contract_ok(e)  # according to chosen schema/text
  else:
     u := regenerate_u01(seed, e.before)  # (0,1)
     assert 0.0 < u && u < 1.0
     assert (u < pi) == e.is_multi

# 6) gating
H1 := {m | H[m].is_multi == true}
for each row in downstream_streams:
  assert row.merchant_id in H1

# 7) uniqueness & cardinality
assert |H| == |ingress_merchant_ids|
assert unique(H.merchant_id)
```

All predicates above are the formalisation of S1.1–S1.7 and the combined journey’s invariants.

---

**Bottom line:** S1.V gives you a **deterministic replay harness** and a **CI gate**: schema → partition → numeric replay → counter/trace reconciliation → gating → cardinality. It uses only the authoritative hurdles stream, the trace stream, $\beta$ + encoders, and the layer’s RNG envelope. Any deviation from the locked S1 rules trips a named failure that blocks the run and the merge.

---