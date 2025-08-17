# S1.1 — Inputs, Preconditions, and Write Targets (normative)

## Purpose (what S1 does and does **not** do yet)

S1 evaluates a **logistic hurdle** per merchant and produces a **Bernoulli outcome** “single vs multi”. In this subsection we only pin **inputs** and **context/lineage** required to do that **deterministically**; the probability map, RNG, and event body are specified in S1.2–S1.4.

---

## Inputs (must be present at S1 entry)

### 1) Design vector $x_m$ (column-frozen, from S0.5)

For each merchant $m$, S1 receives the hurdle design vector

$$
x_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel}_m),\ \phi_{\text{dev}}(b_m)\big]^\top,
$$

with dimension $1+C_{\text{mcc}}+2+5$ and one-hot blocks whose **column order is frozen by the fitting bundle** (not recomputed online). GDP bucket $b_m\in\{1,\dots,5\}$ comes from S0.4. These are the only features used by the hurdle in S1; $\log g_c$ is **not** used here (belongs to NB dispersion later).

**Design-index digest.** The fitting bundle exposes a `feature_index_map` and its `design_index_digest` (SHA-256 over the canonical JSON of that map). S1 MUST verify that its local feature wiring yields the **same** digest before proceeding.

### 2) Coefficient vector $\beta$ (single YAML, atomic load)

Load $\beta$ **atomically** from `hurdle_coefficients.yaml`. It contains **all** coefficients in the exact order required by $x_m$: intercept, MCC block, channel block, **all five** GDP-bucket dummies, **plus** the embedded `feature_index_map` and `design_index_digest`.

Enforce both invariants:

$$
|\beta| = 1+C_{\text{mcc}}+2+5 \quad\text{and}\quad \texttt{local_design_index_digest}=\texttt{design_index_digest (YAML)}.
$$

$\beta$ is interpreted in IEEE-754 **binary64**. If either check fails, abort (design/coeff mismatch).

> Design note (context only): hurdle uses bucket dummies; NB mean excludes them; NB dispersion uses $\log g_c$ (positive slope). Fixed in S0.5; S1 references it only for clarity.

### 3) Lineage & RNG context (fixed before any draw)

Before the **first** hurdle event, S0 must have established:

* `parameter_hash` (hex64) — partitions parameter-scoped artefacts.
* `manifest_fingerprint` (hex64) — partitions egress/validation; embedded in all events.

  * `manifest_fingerprint_bytes` = **32 raw bytes** from the **lowercase** hex string (big-endian).
* `seed` (u64) — master key for **Philox-2x64-10**; current **pre-event** counter $(\texttt{hi},\texttt{lo})$.
* `run_id` (hex32) — **logs-only** partition key.
* `rng_audit_log` row exists for this `{seed, parameter_hash, run_id}` (S0.3). S1 MUST NOT emit its first RNG event without this prior audit row.

All hurdle events include the **shared RNG envelope** fields (no more, no fewer):

```
{ ts_utc,
  module="1A.hurdle_sampler",
  substream_label="hurdle_bernoulli",
  seed, parameter_hash, manifest_fingerprint, run_id, design_index_digest,
  rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }
```

(`draws` is **not** an envelope field; it is reconciled via the per-module RNG trace, see “Companion stream” below.)

---

## Preconditions (hard invariants at S1 entry)

1. **Shape & order:** $|\beta|=\dim(x_m)$ **and** `design_index_digest` matches the YAML; otherwise abort (design/coeff mismatch).
2. **Domains:** `channel ∈ {CP,CNP}`; $b_m\in\{1,\dots,5\}$; GDP $g_c>0$ already enforced upstream (S0.4/S0.5).
3. **Numeric policy:** S0.8 environment in force — IEEE-754 binary64, round-to-nearest-even, **no FMA**, **no FTZ/DAZ**; dot-products use **fixed-order accumulation**.
4. **RNG audit present:** the audit envelope for this run/subsystem is present before S1 emits the first hurdle event; otherwise abort (S0.9/F4a).

---

## Event stream target (authoritative ID, path, schema)

S1 writes **exactly one** hurdle record per merchant to:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

with schema anchor `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`. The `substream_label` in the envelope is **exactly** `"hurdle_bernoulli"`, and `module` is **exactly** `"1A.hurdle_sampler"`. These identifiers and the partitioning triple are authoritative via the dataset dictionary and artefact registry.

*Companion stream.* S1 also emits one row per hurdle emission to:

```
logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl
```

(schema `#/rng/core/rng_trace_log`) containing the `draws` count and the envelope pointers; this is the sole authority for draw-accounting.

---

## Forward-looking contracts S1 must satisfy (pinned here so inputs are complete)

* **Probability & safe logistic (S1.2).** Compute $\eta_m=\beta^\top x_m$ and $\pi_m=\sigma(\eta_m)$ with the **two-branch** overflow-safe logistic. If either is non-finite, abort.

* **Deterministic threshold & u(0,1) (S1.3).** Use **binary64 thresholding**:

  * treat $\pi_m \le 2^{-53}$ as 0 and $\pi_m \ge 1-2^{-53}$ as 1 (**deterministic** case);
  * otherwise draw **exactly one** open-interval uniform $u\in(0,1)$ after jumping to substream `"hurdle_bernoulli"`.
    Counters advance exactly per S0.3 mapping and appear in the envelope.

* **Payload discipline (S1.4).** Payload uses the **nullable-u** contract with an explicit flag:

  * fields: `{merchant_id, pi, is_multi, u|null, deterministic}`;
  * when $2^{-53} < \pi_m < 1-2^{-53}$: `u∈(0,1)`, `deterministic=false`;
  * when thresholded: `u=null`, `deterministic=true`.
    (`eta` is not part of the event payload; if needed, it may appear in diagnostics tables only.)

---

## Failure semantics (at S1.1 boundary)

If any precondition fails, S1 **aborts the run** with S0.9 classes:

* shape/order or digest mismatch → **Design/coefficients mismatch** (S1 → S0.9/F6 or explicit code);
* missing audit/envelope keys → **RNG envelope violation** (S0.9/F4);
* wrong path/partition keys for logs → **Partition mismatch** (S0.9/F5).

---

## Why this matters (determinism & replay)

By pinning $x_m$, $\beta$, the **design-index digest**, lineage keys, event IDs/paths, and the envelope **before** any draw, S1’s later Bernoulli outcome and counters become **bit-replayable** under any sharding or scheduling, as required by S1 invariants (I-H1..H4) and the dictionary.

---

**Bottom line:** S1 starts only when $x_m$, $\beta$, the **matching `design_index_digest`**, and the lineage/RNG context are immutable and schema-backed; it writes to the single authoritative hurdle stream with a fixed envelope and partitioning. With these inputs and preconditions, S1.2–S1.4 can compute $\eta,\pi$, apply the binary64 threshold rule, draw $u$ (when needed), and emit an event the validator can reproduce byte-for-byte.

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

then classify the regime (deterministic vs stochastic) for RNG (S1.3) and provide `pi` for event emission (S1.4). This section fixes the **only admissible** evaluation of $\eta$ and $\pi$.

---

## Inputs (recap; must already be validated in S1.1)

* **Design vector** $x_m=[1,\ \phi_{\mathrm{mcc}},\ \phi_{\mathrm{ch}},\ \phi_{\mathrm{dev}}]^\top\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$, column order **frozen by the fitting bundle**; local wiring verified via `design_index_digest`.
* **Coefficients** $\beta\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$ loaded atomically from `hurdle_coefficients.yaml`; shape/order match $x_m$; same `design_index_digest`.

---

## Canonical definitions (math)

### Logistic map (normative)

$$
\sigma:\mathbb{R}\to(0,1),\quad \sigma(\eta)=\frac{1}{1+e^{-\eta}}.
$$

**Overflow-safe two-branch evaluation (binary64):**

$$
\sigma(\eta)=
\begin{cases}
\dfrac{1}{1+e^{-\eta}}, & \eta\ge 0,\\[6pt]
\dfrac{e^{\eta}}{1+e^{\eta}}, & \eta<0~.
\end{cases}
$$

This exact algorithm MUST be used; it prevents overflow/underflow in the wrong place and keeps $\pi\in[0,1]$ in binary64.

### Linear predictor (fixed-order dot product)

$$
\eta_m=\beta^\top x_m
$$

computed in IEEE-754 **binary64** with a **fixed iteration order** over the frozen columns. Neumaier/Kahan compensation **is allowed**; BLAS calls or any reordering on this ordering-critical path are **not allowed**.

---

## Deterministic classification (normative)

To make draw-consumption unambiguous, S1 classifies $\pi_m$ using a **binary64 threshold rule**:

* Let $\epsilon = 2^{-53}$.
* If $\pi_m \le \epsilon$ ⇒ **deterministic-zero** (treated as 0 for RNG).
* If $\pi_m \ge 1-\epsilon$ ⇒ **deterministic-one** (treated as 1 for RNG).
* Otherwise ⇒ **stochastic**.

**Consequences for S1.3.**

* **Stochastic:** S1.3 MUST consume exactly **one** $u\sim U(0,1)$ (open interval) and set `is_multi = 1{u < π}`.
* **Deterministic:** S1.3 MUST consume **zero** uniforms and set `is_multi` to the classified outcome (0 or 1).

> There is **no clamping** of $\eta$ or $\pi$. Saturation to exact 0/1 may occur numerically for extreme $\eta$; the threshold rule is normative and supersedes relying on incidental saturation.

---

## Numeric policy (must hold)

* IEEE-754 **binary64**, round-to-nearest-even; **no FMA**, **no FTZ/DAZ**; deterministic `libm`.
* Fixed-order accumulation for $\beta^\top x$ (e.g., Neumaier).
* Inputs already satisfy domain checks (S1.1/S0.5).

---

## Output of S1.2 (to S1.3/S1.4)

For each merchant $m$, produce:

* $\eta_m\in\mathbb{R}$ (finite), $\pi_m\in[0,1]$, and a **classification** `deterministic_class ∈ {zero, one, none}`.

These are **not** persisted by S1.2:

* S1.3 uses $\pi_m$ and the classification to decide draw-budget and outcome.
* S1.4 writes `pi` to the event payload; **`eta` is not emitted in the event payload** (it may appear only in separate diagnostic tables, if any).

---

## Failure semantics (abort S1 / run)

* **Shape/order/digest mismatch** during $\beta^\top x$ setup ⇒ `E_DSGN_SHAPE_MISMATCH` ⇒ **S0.9/F6**, run-abort.
* **Numeric invalid:** $\eta$ or $\pi$ non-finite ⇒ `hurdle_nonfinite(field)` ⇒ **S0.9/F3**, run-abort.
* **Out-of-range** $\pi\notin[0,1]$ (should be impossible with two-branch) ⇒ treat as **S0.9/F3**, run-abort with forensic payload.

---

## Validation hooks (minimal, for later)

* **Bit-replay:** Recompute $\eta,\pi$ independently under the pinned math profile; assert finiteness and $\pi\in[0,1]$ with bitwise equality.
* **Classification:** Assert `deterministic=true` in S1.4 iff $\pi \le 2^{-53}$ or $\pi \ge 1-2^{-53}$.
* **Budget linkage:** `draws = 1` iff classification is **none**; else `0` (cross-check with `rng_trace_log`).

---

## Reference algorithm (language-agnostic, ordering-stable)

```text
function S1_2_probability_map(x_m, beta):
  # Preconditions from S1.1:
  #  - len(beta) == len(x_m)
  #  - local design_index_digest == YAML design_index_digest

  # 1) Fixed-order dot product in binary64 (Neumaier compensation allowed)
  s = 0.0
  c = 0.0
  for i in 0..len(x_m)-1:                # exact frozen column order
      y = beta[i] * x_m[i] - c
      t = s + y
      c = (t - s) - y
      s = t
  eta = s

  # 2) Overflow-safe two-branch logistic in binary64
  if eta >= 0.0:
      z = exp(-eta)                      # may underflow to 0 for large eta
      pi = 1.0 / (1.0 + z)
  else:
      z = exp(eta)                       # may underflow to 0 for large -eta
      pi = z / (1.0 + z)

  if not is_finite(eta):  raise E_HURDLE_NONFINITE("eta")
  if not is_finite(pi):   raise E_HURDLE_NONFINITE("pi")
  if pi < 0.0 or pi > 1.0: raise E_HURDLE_OUT_OF_RANGE(pi)

  # 3) Deterministic classification (binary64 threshold rule)
  eps = 2^-53
  if pi <= eps:
      deterministic_class = "zero"
  elif pi >= 1.0 - eps:
      deterministic_class = "one"
  else:
      deterministic_class = "none"

  return (eta, pi, deterministic_class)
```

---

## Interaction with adjacent sections

* **Feeds S1.3:** The classification dictates **draw budget** (0 vs 1) and, if deterministic, the Bernoulli outcome directly.
* **Feeds S1.4:** `pi` is written to the payload; `deterministic=true` and `u=null` when classification ≠ `none`. `eta` remains diagnostic-only.

---

**Bottom line:** S1.2 prescribes a fixed-order binary64 dot product and an overflow-safe two-branch logistic, followed by a **binary64 threshold classification**. This makes the RNG budget and event semantics exact and portable, eliminating any room for divergent implementations.

---

# S1.3 — RNG substream & Bernoulli trial (normative)

## Purpose

Given $\pi_m$ (and the **classification** from S1.2), sample **at most one** uniform $u_m\in(0,1)$ from a **merchant-keyed** Philox substream labelled `"hurdle_bernoulli"`, compute

$$
\text{is_multi}(m)=\mathbf{1}\{u_m<\pi_m\},
$$

and emit **exactly one** hurdle event (payload formalised in S1.4). Substream mapping and open-interval uniforms are fixed and order-invariant.

---

## Inputs (available at S1.3 entry)

* $\pi_m\in[0,1]$ **and** `deterministic_class ∈ {zero, one, none}` from S1.2
  (If classification isn’t passed through the call boundary, the S1.2 rule MUST be re-applied here.)
* Run lineage: `seed` (u64), `manifest_fingerprint`/`manifest_fingerprint_bytes` (32 raw bytes from lowercase hex, big-endian), `parameter_hash`, `run_id`, `module="1A.hurdle_sampler"`, and `design_index_digest`.
* `merchant_id = m` (u64).
* Dictionary paths:
  `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` and
  `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`.

---

## Canonical substream (order-invariant; per merchant)

### Label

$$
\ell := \text{"hurdle_bernoulli"}.
$$

This **exact** string MUST appear in the event envelope as `substream_label`.

### Base counter (pure keyed mapping)

Define the base Philox counter for $(\ell,m)$:

$$
(c^{\text{base}}_{\mathrm{hi}},\,c^{\text{base}}_{\mathrm{lo}})
= \operatorname{split64}\!\big(\operatorname{SHA256}(
\text{"ctr:1A"}\ \|\ \texttt{manifest_fingerprint_bytes}\ \|\ \operatorname{LE64}(\texttt{seed})\ \|\ \ell\ \|\ \operatorname{LE64}(m)
)[0{:}16]\big).
$$

The $i$-th uniform for $(\ell,m)$ uses

$$
(c_{\mathrm{hi}},c_{\mathrm{lo}})=(c^{\text{base}}_{\mathrm{hi}},\ c^{\text{base}}_{\mathrm{lo}}+i)
$$

with 64-bit carry into $c_{\mathrm{hi}}$. This mapping is **pure** in $(\texttt{seed},\texttt{manifest_fingerprint},\ell,m,i)$ → **order-invariant across partitions**.

### Counter conservation (envelope law)

For hurdle events:

$$
(\texttt{after_hi},\texttt{after_lo})=(\texttt{before_hi},\texttt{before_lo})+\Delta,
$$

where $\Delta = 0$ if the classification is deterministic (`zero` or `one`), and $\Delta = 1$ if the classification is `none`. (The value of $\Delta$ is also written to `rng_trace_log.draws`; it is **not** an envelope field.)

> **No `stream_jump` record.** Under this keyed-counter scheme, `stream_jump` is unnecessary and MUST NOT be emitted (removes optional behaviour and divergence).

---

## Uniform $u\in(0,1)$ (open interval; lane policy)

**Generator.** Philox-2x64-10 with key `seed`. Evaluate at the event’s `before` counter; take the **lo64** word $x_0$ (we do **not** reuse hi64, and we do **not** draw a second lane). Map to $u$ via the layer-wide `u01` primitive:

$$
u=\frac{x_0+1}{2^{64}+1}\ \in\ (0,1).
$$

**Budget rule.** One uniform consumes **one** counter increment.

---

## Draw budget & decision logic (driven by S1.2 classification)

Let $\pi=\pi_m$ and `cls = deterministic_class`.

* **Deterministic (`cls ∈ {zero, one}`):**
  $\Delta=0$; do **not** call Philox; set

  $$
  \text{is_multi}=\begin{cases}
  0,& \text{cls = zero},\\
  1,& \text{cls = one}.
  \end{cases}
  $$

  Envelope counters satisfy `after == before`. Payload will use `u=null` and `deterministic=true` (S1.4).

* **Stochastic (`cls = none`):**
  $\Delta=1$; draw $u$ as above and set $\text{is_multi}=\mathbf{1}\{u<\pi\}$.
  Envelope counters satisfy `after = before + 1`. Payload includes `u∈(0,1)` and `deterministic=false`.

These rules are normative and tie exactly to S1.2’s **binary64 threshold** classification.

---

## Envelope & streams touched here (recap; S1.4 formalises payload)

Each hurdle event **must** carry the shared RNG envelope:

```
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, design_index_digest,
  module="1A.hurdle_sampler", substream_label="hurdle_bernoulli",
  rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }
```

and be written to `rng_event_hurdle_bernoulli`’s dictionary path.
S1 also emits one `rng_trace_log` row with `draws = Δ` (0 or 1).

---

## Failure semantics (abort class bindings)

* **Envelope/label mismatch.** Missing required envelope fields, or `substream_label` ≠ `"hurdle_bernoulli"` → **S0.9/F4** (RNG envelope violation).
* **Counter conservation failure.** `(after − before) ∉ {0,1}`, or it disagrees with the branch (`Δ`) → **S0.9/F4**.
* **Uniform out of range.** In a stochastic branch, observed `u ≤ 0` or `u ≥ 1` → **S0.9/F4** (u01 violation).
* **Determinism inconsistency.** Classification `none` but `u` absent, or classification `zero/one` but `u` present → **S0.9/F4**.

(Shape/order and non-finite errors originate in S1.1–S1.2, not here.)

---

## Validation hooks (must pass)

For each hurdle record:

1. **Rebuild the base counter.** From `(seed, manifest_fingerprint_bytes, label="hurdle_bernoulli", merchant_id)`, recompute the base counter and assert envelope `before` equals it.
2. **Recompute budget & decision.**
   Recompute `cls` from $\pi$ using the **S1.2 threshold rule** ($\epsilon=2^{-53}$):

   * If `cls ≠ none`: assert `u==null`, `deterministic=true`, and `after==before`.
   * If `cls = none`: regenerate $x_0$ via Philox at `before`, map to $u$, assert $u\in(0,1)$, `(u<π) == is_multi`, and `after = before + 1`.
3. **Trace reconciliation.** Join with `rng_trace_log`; assert `draws == (after − before)`.
4. **Partition/embedding equality.** Path keys `{seed, parameter_hash, run_id}` equal the same fields embedded in the envelope.

---

## Reference algorithm (ordering-invariant; language-agnostic)

```text
INPUT:
  m : merchant_id (u64)
  pi : float64 in [0,1]
  cls : {"zero","one","none"}  # from S1.2; if absent, re-derive using eps = 2^-53
  seed : u64
  mf_bytes : 32-byte manifest_fingerprint_bytes (from lowercase hex, big-endian)
  now_utc_ns : u64

# 1) Base counter for (label, merchant)
buf = sha256( ASCII("ctr:1A") || mf_bytes || LE64(seed) || ASCII("hurdle_bernoulli") || LE64(m) )
before_hi = LE64_to_u64(buf[0:8])
before_lo = LE64_to_u64(buf[8:16])

# 2) Branch on classification
if cls == "zero" or cls == "one":
    Δ = 0
    after_hi, after_lo = before_hi, before_lo
    u_val = null
    is_multi = (cls == "one")
else:
    Δ = 1
    x0 = philox2x64_10(seed, before_hi, before_lo).lo64
    u_val = (x0 + 1) / (2^64 + 1)  # (0,1)
    is_multi = (u_val < pi)
    (after_hi, after_lo) = add_u128((before_hi, before_lo), 1)

# 3) Emit hurdle event (payload per S1.4)
emit_hurdle_event(
  envelope = {
    ts_utc=now_utc_ns, run_id, seed, parameter_hash, manifest_fingerprint,
    design_index_digest, module="1A.hurdle_sampler", substream_label="hurdle_bernoulli",
    rng_counter_before_hi=before_hi, rng_counter_before_lo=before_lo,
    rng_counter_after_hi=after_hi,   rng_counter_after_lo=after_lo
  },
  payload = { merchant_id=m, pi=pi, u=u_val, is_multi=is_multi,
              deterministic=(Δ == 0) }
)

# 4) Emit rng_trace_log row
emit_rng_trace({
  ts_utc=now_utc_ns, run_id, seed, parameter_hash, manifest_fingerprint,
  module="1A.hurdle_sampler", substream_label="hurdle_bernoulli",
  rng_counter_before_hi=before_hi, rng_counter_before_lo=before_lo,
  rng_counter_after_hi=after_hi,   rng_counter_after_lo=after_lo,
  draws=Δ
})
```

---

## Invariants guaranteed by this section

* **I-H1 (bit-replay).** Fixing $(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the tuple $(u_m,\text{is_multi}(m))$ and counters are **bit-identical** across replays.
* **I-H2 (consumption).** `draws=1` iff classification is **none**; otherwise `0`.
* **I-H3 (schema conformance).** `u` and `deterministic` appear exactly per the classification and S1.4.
* **I-H4 (branch purity).** Hurdle decision feeds subsequent states; downstream MUST NOT override it.

---

**Bottom line:** S1.3 sets a deterministic, merchant-keyed Philox substream and a single-uniform Bernoulli decision controlled by S1.2’s threshold classification. No optional jumps, explicit lane policy, open-interval mapping, and counter conservation make the stream replayable, auditable, and unambiguous.

---

# S1.4 — Event emission (hurdle Bernoulli), with **exact** envelope/payload, partitioning, invariants, and validation

## 1) Where the records go (authoritative path + schema)

Emit **one JSONL record per merchant** to:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

The stream is approved in the dictionary and bound to the schema anchor:
`schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.

**Partition keys:** `{seed, parameter_hash, run_id}`.
**Do not** include `manifest_fingerprint` in the path (it belongs to egress/validation datasets, not logs).

---

## 2) Envelope (shared, required for **all** RNG events)

Every record MUST carry `$defs.rng_envelope` exactly:

* **Required envelope fields**
  `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, design_index_digest, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi`.

* **Semantics (normative)**

  * `ts_utc`: RFC 3339/ISO timestamp (UTC) at emit time.
  * `run_id`: log-only identifier (scopes logs; from S0).
  * `seed`: master Philox key (u64; run-constant).
  * `parameter_hash`, `manifest_fingerprint`: lineage keys (hex).

    * `manifest_fingerprint_bytes` = 32 raw bytes from the **lowercase** hex string (big-endian) used in counter derivation (S1.3).
  * `design_index_digest`: SHA-256 hex (lowercase) of the feature index map used to wire $x_m$ (must match S1.1).
  * `module`: **exactly** `"1A.hurdle_sampler"`.
  * `substream_label`: **exactly** `"hurdle_bernoulli"`.
  * `rng_counter_before_*`, `rng_counter_after_*`: Philox-2×64 counter **before** and **after** the event’s draws.

**Counter arithmetic (ties to S1.3).**
Let $\Delta\in\{0,1\}$ be the draw budget decided by S1.2’s classification (`none` → 1, `zero/one` → 0). Then:

```
after == before + Δ       # unsigned 128-bit addition
```

(There is **no** block grouping; each uniform uses one counter increment.)

---

## 3) Payload (event-specific, exact contract)

The hurdle payload is **minimal, branch-clean, and schema-anchored**:

* **Required**:
  `merchant_id` (u64), `pi` (float64 in \[0,1]), `is_multi` (boolean), `deterministic` (boolean).

* **Conditional**:
  `u` (float64 in (0,1)) is **required when** `deterministic=false` and **must be null** when `deterministic=true`.

* **Optional `context` object** (when enabled in schema):
  `{ "mcc": <int>, "channel": "CP"|"CNP", "gdp_bucket_id": 1..5 }`.
  (This keeps optional fields contained and avoids payload churn.)

**Branch semantics (normative):**

* If S1.2 classification is **none** (stochastic):
  draw $u\in(0,1)$, set `is_multi = (u < pi)`, set `deterministic=false`, **include** `u`, and ensure `after = before + 1`.
* If classification is **zero**:
  set `is_multi=false`, `deterministic=true`, **set** `u=null`, and ensure `after = before`.
* If classification is **one**:
  set `is_multi=true`, `deterministic=true`, **set** `u=null`, and ensure `after = before`.

**Not in payload:** `eta` MUST NOT be emitted in this event (diagnostics-only elsewhere, if any).

---

## 4) Canonical JSON examples

**(A) Stochastic example (`Δ=1`)**

```json
{
  "ts_utc": "2025-08-15T10:03:12.345678Z",
  "run_id": "8c7d2a4b0e3f1c9a2b4d6f8e0c1a3b5c",
  "seed": 1234567890123456789,
  "parameter_hash": "0f...c1",
  "manifest_fingerprint": "aa...33",
  "design_index_digest": "bb...55",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "rng_counter_before_lo": 9876543210,
  "rng_counter_before_hi": 42,
  "rng_counter_after_lo": 9876543211,
  "rng_counter_after_hi": 42,

  "merchant_id": 184467440737095,
  "pi": 0.3725,
  "u": 0.1049,
  "is_multi": false,
  "deterministic": false
}
```

**(B) Deterministic-one example (`Δ=0`)**

```json
{
  "ts_utc": "2025-08-15T10:03:12.789012Z",
  "run_id": "8c7d2a4b0e3f1c9a2b4d6f8e0c1a3b5c",
  "seed": 1234567890123456789,
  "parameter_hash": "0f...c1",
  "manifest_fingerprint": "aa...33",
  "design_index_digest": "bb...55",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "rng_counter_before_lo": 555,
  "rng_counter_before_hi": 7,
  "rng_counter_after_lo": 555,
  "rng_counter_after_hi": 7,

  "merchant_id": 184467440737096,
  "pi": 0.9999999999999,
  "u": null,
  "is_multi": true,
  "deterministic": true
}
```

---

## 5) Write discipline & linkage

* **Exactly one** hurdle record per merchant.
* Append-only `part-*` files; stable partitioning by `{seed, parameter_hash, run_id}`.
* Always `module="1A.hurdle_sampler"` and `substream_label="hurdle_bernoulli"`.
* Emit **one** `rng_trace_log` row per hurdle record with `draws = Δ` and matching envelope counters/keys.

---

## 6) Validation hooks (must pass)

For each record:

1. **Schema conformance.** Validate against `#/rng/events/hurdle_bernoulli` + `$defs.rng_envelope`.
2. **Counter proof.** Recompute $\Delta$ from `deterministic`:

   * `true` → $\Delta=0$ and `after==before`; `u==null`.
   * `false` → $\Delta=1$ and `after==before+1`; `u∈(0,1)`.
3. **RNG replay.** For $\Delta=1$, regenerate $u$ from Philox at `before` using S1.3 and assert `(u < pi) == is_multi`.
4. **Trace reconciliation.** Join `rng_trace_log` on envelope keys; assert `draws == (after − before)`.
5. **Cardinality & ordering.** Row count equals merchants in `merchant_ids` for the run; path keys equal embedded fields.

---

## 7) Failure semantics surfaced by S1.4

* **E_SCHEMA_HURDLE**: record fails `#/rng/events/hurdle_bernoulli` (missing envelope field, wrong types, `u` present with `deterministic=true`, etc.).
* **E_COUNTER_MISMATCH**: `after` ≠ `before + Δ`.
* **E_BRANCH_GAP** (checked later): any downstream RNG event for a merchant with **no** prior hurdle record or with `is_multi=false`.

---

## 8) Reference emission pseudocode (language-agnostic, exact fielding)

```text
function emit_hurdle_event(m, pi, cls, ctx):
  # cls ∈ {"zero","one","none"} from S1.2 (re-derive if absent)
  before = base_counter(label="hurdle_bernoulli", seed=ctx.seed,
                        mf_bytes=ctx.mf_bytes, merchant=m)
  if cls == "none":
      Δ = 1
      x0 = philox2x64_10(ctx.seed, before).lo64
      u  = (x0 + 1) / (2^64 + 1)
      is_multi = (u < pi)
      after = add_u128(before, 1)
      deterministic = false
  else:
      Δ = 0
      u = null
      is_multi = (cls == "one")
      after = before
      deterministic = true

  record = envelope(ctx, label="hurdle_bernoulli", before, after) + {
    "merchant_id": m, "pi": pi, "u": u,
    "is_multi": is_multi, "deterministic": deterministic
  }
  write_jsonl(path_for_hurdle(ctx), record)
  emit_rng_trace(ctx, label="hurdle_bernoulli", before, after, draws=Δ)
```

---

**Bottom line:** S1.4 now has a single, unambiguous contract: stable pathing, a precise envelope (including `design_index_digest`), and a **nullable-`u` + `deterministic`** payload that mirrors S1.2’s threshold classification. Counters prove consumption (`after = before + Δ`), making each hurdle decision independently replayable and audit-tight.

---

# S1.5 — Determinism & Correctness Invariants (normative)

## Purpose

Freeze the invariants that must hold for every merchant’s hurdle decision so downstream states (NB/ZTP/Dirichlet/Gumbel) can **trust** and **replay** S1 exactly. Each invariant includes the rationale and what the validator checks.

---

## I-H0 — Environment, schema & authority (precondition)

* **Numeric profile.** IEEE-754 **binary64**, round-to-nearest-even; **no FMA**, **no FTZ/DAZ**; fixed-order reductions; deterministic `exp` in the two-branch logistic. (Violations ⇒ S0.9/F3.)
* **Schema anchors.** All RNG records conform to `$defs.rng_envelope` and their event schema anchors. Hurdle is bound to `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.
* **Design wiring authority.** `design_index_digest` emitted in every hurdle envelope **equals** the digest embedded in `hurdle_coefficients.yaml` and the local feature wiring used in S1.1–S1.2. (Mismatch ⇒ S0.9/F6.)

**Validator.** Assert the math profile, envelope presence, and `design_index_digest` equality per record.

---

## I-H1 — Bit-replay (per merchant, per run)

**Statement.** For fixed inputs $(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the tuple $(u_m,\text{is_multi}(m))$ and envelope counters $(C^{\mathrm{pre}}_m,C^{\mathrm{post}}_m)$ are **bit-identical** across replays, independent of emission order.

**Why.** Base counter is a pure function of `(seed, manifest_fingerprint_bytes, "hurdle_bernoulli", merchant_id)`; draw budget is a pure function of $\pi_m$ via S1.2’s threshold rule; $u$ uses a single mapped 64-bit word (open interval).

**Validator.** Rebuild base counter; if draw budget is 1, regenerate $u$ and assert `(u < π) == is_multi`; counters match exactly.

---

## I-H2 — Consumption & budget (single-uniform law)

**Statement.** Let $\epsilon=2^{-53}$ and define the **classification** from S1.2:

* `none` if $\epsilon<\pi_m<1-\epsilon$ (stochastic),
* `zero` if $\pi_m\le\epsilon$, `one` if $\pi_m\ge 1-\epsilon$ (deterministic).

Then the draw budget $\Delta$ is:

* $\Delta=1$ if classification is `none`;
* $\Delta=0$ if classification is `zero` or `one`.

Envelope counters obey:

```
after == before + Δ      # unsigned 128-bit addition
```

**Validator.** Re-derive classification from `pi`; check `after − before == Δ` and `rng_trace_log.draws == Δ`.

---

## I-H3 — Schema-level payload discipline

**Statement (normative payload).** The hurdle payload contains `{merchant_id, pi, is_multi, deterministic}` and conditionally `u`:

* If `deterministic=false` (classification `none`): **must** include `u ∈ (0,1)`.
* If `deterministic=true` (classification `zero/one`): **must** have `u = null`.

`eta` is **not** part of the event payload. Any deviation is a schema failure.

**Validator.** Enforce the presence/nullability of `u` from `deterministic`; assert `pi ∈ [0,1]`.

---

## I-H4 — Branch purity (downstream gating)

**Statement.**

* If `is_multi = 1`, merchant $m$ **may** produce downstream event families (NB/ZTP/Dirichlet/Gumbel).
* If `is_multi = 0`, merchant $m$ **must not** produce any of those streams.

**Validator.** Left-join downstream streams to hurdle; flag any downstream event without a prior hurdle or with `is_multi=false`.

---

## I-H5 — Cardinality & uniqueness (per run)

* Exactly **one** hurdle record per `merchant_id` within each `{seed, parameter_hash, run_id}` partition.
* Hurdle is the **first** RNG stream in 1A for each merchant.

**Validator.** Count equals `merchant_ids` for the run; enforce uniqueness on `(merchant_id)` in the hurdle partition; enforce “downstream requires prior hurdle”.

---

## I-H6 — Envelope completeness & path equality

* Every record contains **all** envelope fields:
  `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, design_index_digest, module="1A.hurdle_sampler", substream_label="hurdle_bernoulli", rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo}`.
* Path keys `{seed, parameter_hash, run_id}` **equal** the same embedded fields.

**Validator.** JSON-schema conformance + equality of path vs embedded keys.

---

## I-H7 — Order-invariance & concurrency safety

* Emission order is **unspecified**; correctness derives from per-row content.
* Dataset equivalence is **set equality** of rows within the partition; multiple `part-*` files are permitted.

**Validator.** Replays on different shard orders yield identical envelopes/outcomes per I-H1.

---

## I-H8 — Independence across merchants & substreams

* Base counters are **disjoint** for distinct `(label, merchant_id)` pairs under the keyed mapping (fixed `seed`/`manifest_fingerprint`).
* `substream_label` is **exactly** `"hurdle_bernoulli"`.

**Validator.** Recompute base counters; assert label correctness; detect any collisions (should be impossible).

---

## I-H9 — Optional diagnostics are non-authoritative

If a diagnostic `hurdle_pi_probs` table exists, it is **parameter-scoped** and never consulted by samplers; S1 decisions must match recomputation from $(x_m,\beta)$.

**Validator.** If present, compare diagnostics to recomputed `pi` (tolerate diagnostic storage differences; decisioning uses recomputation only).

---

## I-H10 — Replay equations (validator recipe)

For each hurdle row $r$ with merchant $m$:

1. Recompute $(\eta_m,\pi_m)$ per S1.2 (fixed-order dot + two-branch logistic); assert finiteness and $\pi \in [0,1]$.
2. Rebuild **base counter** for $(\text{"hurdle_bernoulli"}, m)$ and assert `rng_counter_before` equals it.
3. Derive classification via $\epsilon=2^{-53}$; set $\Delta = 1$ iff `none`; assert `rng_counter_after = rng_counter_before + Δ`.
4. If $\Delta=1$: regenerate $u$ (open-interval mapping) and assert $u \in (0,1)$ and `(u < π) == is_multi`.
   If $\Delta=0$: assert `deterministic=true`, `u=null`, and `is_multi` matches the classification (`zero`→false, `one`→true).
5. Cross-check `rng_trace_log.draws == Δ`.

---

## Failure bindings (S0.9 classes surfaced)

* **F4 (RNG envelope/accounting).** Missing envelope fields, label drift, counter mismatch, `u` out of range, or `u` presence/nullability inconsistent with `deterministic`.
* **F5 (Partition/lineage).** Path keys differ from embedded `{seed, parameter_hash, run_id}`.
* **F6 (Design/coeff).** `design_index_digest` mismatch or shape/order mismatch detected upstream.
* **F8 (Coverage/gating).** Downstream event present without prior hurdle or with `is_multi=false`.

---

## What this guarantees downstream

* **Deterministic hand-off.** A single hurdle decision and an exact next-counter cursor; downstream must satisfy `before(next) == after(hurdle)`.
* **Audit-tight lineage.** Logs partitioned by `{seed, parameter_hash, run_id}`; egress/validation gated by `manifest_fingerprint`. Independent validators can reproduce and prove every Bernoulli outcome and its consumption.

---

**Bottom line:** With the binary64 threshold classification, single-uniform budget, exact envelope + counter law, nullable-`u` payload, and `design_index_digest` echoed, S1 is fully replayable and impossible to misinterpret—giving downstream states a clean, deterministic base to build on.

---

# S1.6 — Failure modes (normative, abort semantics)

**Scope.** Failures here are specific to S1 (hurdle): design/β misuse, numeric invalids, schema/envelope breaches, RNG counter/accounting errors, partition drift, and downstream gating. All predicates and bindings are **normative**.

**Authoritative references:**
Schemas in `schemas.layer1.yaml` (e.g., `$defs.rng_envelope`, `#/rng/events/hurdle_bernoulli`, `$defs.u01`), dictionary paths for hurdle events and RNG trace, and invariants **I-H0..I-H10**.

---

## Family A — Design / coefficients / wiring (compute-time hard abort)

**A1. `beta_length_mismatch`**
**Predicate.** `len(β) ≠ 1 + C_mcc + 2 + 5`.
**Detect at.** S1.1/S1.2 guard. **Abort run.**
**Forensics.** `{expected_len, observed_len, mcc_cols, channel_cols, bucket_cols}`.

**A2. `unknown_category`**
**Predicate.** `mcc_m` not in MCC dict, or `channel_m ∉ {CP,CNP}`, or `b_m ∉ {1..5}`.
**Detect at.** S1.1 guard. **Abort run.**
**Forensics.** `{merchant_id, field, value}`.

**A3. `design_index_digest_mismatch`**
**Predicate.** `design_index_digest (envelope)` ≠ digest embedded in `hurdle_coefficients.yaml` **or** ≠ digest of the local wiring used to build $x_m$.
**Detect at.** S1.1 guard; envelope echo at S1.4. **Abort run.**
**Forensics.** `{digest_yaml, digest_local, digest_envelope}`.

---

## Family B — Numeric invalids (compute-time hard abort)

**B1. `hurdle_nonfinite_eta`**
**Predicate.** $\eta_m$ non-finite after fixed-order dot (binary64).
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta}`.

**B2. `hurdle_nonfinite_or_oob_pi`**
**Predicate.** $\pi_m$ non-finite or $\pi_m \notin [0,1]$ after two-branch logistic.
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta, pi}`.

---

## Family C — Envelope & accounting (RNG/logging hard abort)

**C1. `rng_envelope_schema_violation`**
**Predicate.** Any missing/wrongly-typed **envelope** field required by `$defs.rng_envelope`:
`{ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, design_index_digest, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}}`.
**Detect at.** Writer + validator schema checks. **Abort run.**
**Forensics.** `{dataset_id, path, missing_or_bad:[...]}`.

**C2. `substream_label_mismatch`**
**Predicate.** `substream_label` ≠ `"hurdle_bernoulli"`.
**Detect at.** Writer assertion; validator. **Abort run.**

**C3. `rng_counter_mismatch`**
**Predicate.** `u128(after) − u128(before) ≠ Δ`, where **Δ** is the draw budget from S1.2’s **threshold classification** (`none→1`, `zero/one→0`).
**Detect at.** Writer + validator reconciliation. **Abort run.**
**Forensics.** `{before, after, delta_expected:Δ}`.

**C4. `rng_trace_missing_or_mismatch`**
**Predicate.** Missing `rng_trace_log` row for `(seed, parameter_hash, run_id, label="hurdle_bernoulli")`, or `trace.draws ≠ (after−before)`.
**Detect at.** Validator join. **Abort run.**

**C5. `u_out_of_range`**
**Predicate.** In a **stochastic** branch (`deterministic=false`), payload `u ∉ (0,1)`.
**Detect at.** Writer check; validator schema + replay. **Abort run.**

**C6. `module_label_mismatch`**
**Predicate.** `module` ≠ `"1A.hurdle_sampler"`.
**Detect at.** Writer assertion; validator. **Abort run.**

---

## Family D — Payload / schema discipline (hurdle event)

> **Normative payload (S1.4):** required `{merchant_id, pi, is_multi, deterministic}`, conditional `u`:
>
> * `deterministic=false` ⇒ **must** include `u ∈ (0,1)`
> * `deterministic=true`  ⇒ **must** have `u = null`

**D1. `hurdle_payload_schema_violation`**
**Predicate.** Record fails `#/rng/events/hurdle_bernoulli` (missing required keys, wrong types/ranges).
**Detect at.** Writer JSON-Schema; CI validator. **Abort run.**

**D2. `payload_branch_inconsistency`**
**Predicate.** `deterministic=false` but `u` absent/nullable, **or** `deterministic=true` but `u` present and non-null.
**Detect at.** Writer; validator. **Abort run.**

**D3. `decision_mismatch`**
**Predicate.** In a stochastic branch, `(u < pi) ≠ is_multi`.
**Detect at.** Validator replay. **Abort run.**

---

## Family E — Partitioning & lineage coherence

**E1. `partition_mismatch`**
**Predicate.** Path keys `{seed, parameter_hash, run_id}` do **not** equal the same embedded envelope fields.
**Detect at.** Writer; validator. **Abort run.**

**E2. `wrong_dataset_path`**
**Predicate.** Hurdle events written to a path not matching the dictionary template.
**Detect at.** Writer; validator path lint. **Abort run.**

---

## Family F — Coverage & gating (cross-stream structural)

**F1. `logging_gap_no_prior_hurdle`**
**Predicate.** Any downstream RNG event (Gamma/Poisson/NB final/Dirichlet/Gumbel) for merchant `m` **without** a prior hurdle record with `is_multi=true` in this run.
**Detect at.** Validator cross-stream join. **Run invalid** (hard failure).

**F2. `duplicate_hurdle_record`**
**Predicate.** >1 hurdle record for the same merchant within the same `{seed, parameter_hash, run_id}`.
**Detect at.** Validator uniqueness. **Abort run.**

**F3. `cardinality_mismatch`**
**Predicate.** `count(hurdle_records) ≠ count(merchant_ids)` for the run.
**Detect at.** Validator count. **Abort run.**

---

## Error object (forensics payload; exact fields)

Emit a JSON failure object with envelope lineage (written alongside the validation bundle / `_FAILED.json`):

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
    "delta_expected": 1
  },
  "seed": 1234567890,
  "parameter_hash": "<hex64>",
  "manifest_fingerprint": "<hex64>",
  "design_index_digest": "<hex64>",
  "run_id": "<hex32>",
  "ts_utc": "2025-08-15T10:12:03.123456Z"
}
```

---

## Where to detect & who double-checks

| Family / Code               | First detector (runtime)   | Secondary (validator / CI) |
| --------------------------- | -------------------------- | -------------------------- |
| A1–A3 design/wiring         | S1.1/S1.2 guards           | N/A (optional lints)       |
| B1–B2 numeric invalid       | S1.2 evaluation guards     | Re-eval η,π                |
| C1 envelope schema          | Writer JSON-Schema         | Validator schema pass      |
| C2/C6 label/module mismatch | Writer assertions          | Validator                  |
| C3 counter mismatch         | Writer + trace emission    | Counter reconciliation     |
| C4 trace missing/mismatch   | —                          | Trace join                 |
| C5 u out of range           | Writer check               | `u01` + replay             |
| D1 payload schema           | Writer JSON-Schema         | Validator schema pass      |
| D2 branch inconsistency     | Writer assertion           | Replay/branch recompute    |
| D3 decision mismatch        | —                          | Replay `(u<π) == is_multi` |
| E1 partition mismatch       | Writer path/embed equality | Path lint                  |
| E2 wrong dataset path       | —                          | Dictionary lint            |
| F1 logging gap              | —                          | Cross-stream gating        |
| F2 duplicate record         | —                          | Uniqueness                 |
| F3 cardinality mismatch     | —                          | Row count vs ingress       |

---

## Validator assertions (executable checklist)

1. **Schema:** validate hurdle events + trace rows against anchors (envelope + event).
2. **Recompute η,π:** S1.2 rules (fixed-order dot + two-branch logistic). Assert finiteness and $\pi \in [0,1]$.
3. **Classification & budget:** with $\epsilon=2^{-53}$, derive classification (`none/zero/one`) and $\Delta$. Assert `after = before + Δ` and `trace.draws == Δ`.
4. **Payload discipline:**

   * `deterministic=true` ⇒ `u==null`;
   * `deterministic=false` ⇒ regenerate $u$ at `before`, assert $u\in(0,1)$ and `(u<π) == is_multi`.
5. **Partition lint:** path keys `{seed, parameter_hash, run_id}` equal embedded values.
6. **Gating:** every downstream RNG event has prior hurdle with `is_multi=true`.
7. **Uniqueness & cardinality:** one hurdle row per merchant; total equals `merchant_ids`.

---

## Minimal examples (concrete)

* **B2 — numeric invalid.** `pi = NaN` after logistic → `hurdle_nonfinite_or_oob_pi` → abort.
* **C1 — envelope gap.** Missing `rng_counter_after_hi` → `rng_envelope_schema_violation` → abort.
* **D2 — branch inconsistency.** `deterministic=true` but `u=0.42` → `payload_branch_inconsistency` → abort.
* **F1 — gating failure.** `rng_event_nb_final` exists for `m` without prior hurdle `is_multi=true` → `logging_gap_no_prior_hurdle` → run invalid.

---

**Bottom line:** These failure predicates and bindings match the **final S1 contract**: binary64 thresholding, single-uniform budget, exact envelope + counter law, **nullable-`u` with `deterministic`**, `design_index_digest` echo, and strict path/envelope equality—so any divergence is caught fast, with precise forensic context.

---

# S1.7 — Outputs of S1 (state boundary, normative)

## A) Authoritative event stream S1 **must** persist

For every merchant $m\in\mathcal{M}$, S1 writes **exactly one** JSONL record to:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Schema anchor (fixed):** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`
* **Dictionary id (fixed):** `rng_event_hurdle_bernoulli` — partitioned by `{seed, parameter_hash, run_id}`, produced by `"1A.hurdle_sampler"`.

**Envelope (shared; required for all RNG events):**

```
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, design_index_digest,
  module="1A.hurdle_sampler", substream_label="hurdle_bernoulli",
  rng_counter_before_lo, rng_counter_before_hi,
  rng_counter_after_lo,  rng_counter_after_hi }
```

**Payload (authoritative, branch-clean):**

```
{ merchant_id (u64), pi (float64 in [0,1]),
  is_multi (bool), deterministic (bool),
  u: (float64 in (0,1)) | null }
```

* If `deterministic=false` → **must include** `u ∈ (0,1)` and set `is_multi = (u < pi)`.
* If `deterministic=true`  → **must set** `u = null`; `is_multi` is implied by S1.2’s classification (`zero`→false, `one`→true).
* **Not in payload:** `eta` (diagnostics-only if materialised elsewhere).
* **Optional `context` object** (if enabled in schema) for `{mcc, channel, gdp_bucket_id}`.

**Companion trace (draw accounting):**

```
logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl
```

One row per hurdle record with `draws = Δ` where:

* `Δ = 1` if S1.2 classification is `none` (stochastic), else `Δ = 0`.
* **Counter law (normative):** `after == before + Δ` (unsigned 128-bit).
  *(There is no “blocks” notion; each uniform increments by 1.)*

> These hurdle records are the **only authoritative source** for the decision and the exact counter cursor that S2+ must start from.

---

## B) In-memory **handoff tuple** to downstream (typed, deterministic)

S1 yields a typed tuple per merchant to the orchestrator:

$$
\boxed{\ \Xi_m \;=\; \big(\ \text{is_multi}(m),\ N_m,\ K_m,\ \mathcal{C}_m,\ C_m^{\star}\ \big)\ }.
$$

**Field semantics:**

* `is_multi(m) ∈ {0,1}` — from the hurdle payload.
* $N_m \in \mathbb{N}$ — target outlet count (**convention:** set $N_m:=1$ when `is_multi=0`; NB branch will sample $N_m$ when `is_multi=1`).
* $K_m \in \mathbb{N}$ — non-home country budget (**init:** $K_m:=0$; set later in cross-border/ranking).
* $\mathcal{C}_m\subseteq\mathcal{I}$ — country set accumulator (**init:** $\{\text{home}(m)\}$).
* $C_m^{\star}\in\{0,\dots,2^{64}\!-\!1\}^2$ — **RNG counter cursor after hurdle**: exactly the event’s `{rng_counter_after_hi, rng_counter_after_lo}`.
  **Next RNG event for $m$ must start with `rng_counter_before = C_m^{\star}`.**

**Branch semantics:**

* If `is_multi=0`:
  $\boxed{N_m\leftarrow 1,\;K_m\leftarrow 0,\;\mathcal{C}_m\leftarrow\{\text{home}(m)\}}$; **skip S2–S6** and jump to **S7** with RNG starting at $C_m^{\star}$. No NB/Dirichlet/Poisson/ZTP/Gumbel streams may appear for $m$.
* If `is_multi=1`:
  proceed to **S2** (NB branch); **the first NB-labelled event must use `rng_counter_before = C_m^{\star}`**.

---

## C) Downstream visibility (for validation & joins)

For merchants with `is_multi=1`, validators (and readers) discover downstream streams via the dictionary, all partitioned by `{seed, parameter_hash, run_id}`. Examples:

* `logs/rng/events/gamma_component/...` (`#/rng/events/gamma_component`)
* `logs/rng/events/poisson_component/...` (`#/rng/events/poisson_component`)
* `logs/rng/events/nb_final/...` (`#/rng/events/nb_final`)
* (later states) `logs/rng/events/dirichlet_gamma_vector/...`, `logs/rng/events/gumbel_key/...`

**Gating rule (normative):** these streams **must** be absent if there is no prior hurdle record with `is_multi=true` for that merchant.

---

## D) Optional diagnostic dataset (parameter-scoped; non-authoritative)

If enabled:

```
data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/…
```

* **Schema:** `#/model/hurdle_pi_probs`.
* **Fields (per merchant):** `{manifest_fingerprint, merchant_id, logit=eta, pi}` as **float64** diagnostics.
* **Contract:** never consulted by samplers; used only for QA/lineage.

---

## E) Boundary invariants (must hold when S1 ends)

1. **Single emit:** exactly one hurdle record per merchant per `{seed, parameter_hash, run_id}`, and exactly one $\Xi_m$.
2. **Counter continuity:** next RNG envelope for $m$ satisfies `rng_counter_before == C_m^{\star}`.
3. **Branch purity:** downstream RNG streams appear **iff** `is_multi=1`; single-site path performs **no** NB/ZTP/Dirichlet/Gumbel draws.
4. **Lineage coherence:** logs use `{seed, parameter_hash, run_id}`; egress/validation later uses `fingerprint={manifest_fingerprint}`. Embedded keys equal path keys.
5. **Numeric consistency:** payload `pi` equals recomputed $π_m$ from S1.2 (fixed-order dot + two-branch logistic); binary64 thresholding governs `deterministic` (S1.2).
6. **Design wiring coherence:** `design_index_digest` in the envelope equals the digest in `hurdle_coefficients.yaml` and the local wiring used to form $x_m$.

---

## F) Minimal handoff construction (reference)

```text
INPUT:
  hurdle_event (envelope + payload) for merchant m, home_iso(m)

OUTPUT:
  Xi_m = (is_multi, N_m, K_m, C_m, C_star_m), next_state

1  is_multi   := hurdle_event.is_multi
2  C_star_m   := (env.rng_counter_after_hi, env.rng_counter_after_lo)
3  C_m        := { home_iso(m) }

4  if is_multi == 0:
5      N_m := 1
6      K_m := 0
7      next_state := S7
8  else:
9      N_m := ⊥      # sampled in S2 (NB)
10     K_m := ⊥      # set later in cross-border/ranking
11     next_state := S2

12 return Xi_m, next_state
```

---

**Bottom line:** S1 produces **one** authoritative hurdle event (exact envelope + branch-clean payload) and a **precise** in-memory tuple $\Xi_m$ that fixes RNG continuity and the control-flow split. With the dictionary paths, envelope law `after = before + Δ`, and gating rule, downstream states can start deterministically from $C_m^{\star}$ and validators can replay every decision without ambiguity.

---

# S1.V — Validator & CI (normative)

## V0. Purpose & scope

Prove, for the whole run, that every hurdle record is:

* **Schema-valid,** with the exact envelope/payload contract.
* **Numerically correct** under the pinned math policy.
* **RNG-accounted,** i.e., counters match the single-uniform budget.
* **Partition-coherent,** i.e., path keys equal embedded keys.
* **Structurally consistent** with downstream streams (gating).

Hurdle is the **first** RNG event stream in 1A; this validator is a blocking gate.

---

## V1. Inputs the validator must read

1. **Locked specs:** the S1 state text (this document) and the combined journey spec (for downstream joins).
2. **Event datasets (logs):**

   * Hurdle events
     `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
     schema `#/rng/events/hurdle_bernoulli`.
   * RNG trace
     `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`.
   * Downstream streams for gating (appear **only** if `is_multi=true`): `gamma_component`, `poisson_component`, `nb_final` (and when present, `dirichlet_gamma_vector`, `gumbel_key`).
3. **Design/β artefacts:** frozen encoders/dictionaries + `hurdle_coefficients.yaml` (single-YAML β **and** `design_index_digest`).
4. **Run lineage:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id` (from path and embedded envelope); `manifest_fingerprint_bytes` = 32 raw bytes from the lowercase hex string (big-endian).

---

## V2. Discovery & partition lint (dictionary-backed)

* **Locate** the hurdle partition for the run via the dictionary path template.
* **Require** for every row: embedded `{seed, parameter_hash, run_id}` **equal** the path keys.
* **Envelope anchor** and **payload anchor** come from the layer schema set.

**Checks (discovery stage):**

* P-1: Hurdle path exists.
* P-2: At least one `part-*` file present.
* P-3: Hurdle row count **==** ingress merchant count for the run; uniqueness of `merchant_id` within the hurdle partition.

---

## V3. Schema conformance (row-level, exact contract)

Validate **every** hurdle record against:

**Envelope (must include, exactly):**

```
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, design_index_digest,
  module, substream_label, rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo} }
```

* `module` **must** be `"1A.hurdle_sampler"`.
* `substream_label` **must** be `"hurdle_bernoulli"`.

**Payload (branch-clean, no dual contract):**

```
required:  merchant_id (u64), pi (float64 in [0,1]), is_multi (bool), deterministic (bool)
conditional: u (float64 in (0,1)) present iff deterministic=false; u=null iff deterministic=true
optional:   context {mcc, channel, gdp_bucket_id} when enabled in schema
```

Fail on the first schema error.

---

## V4. Recompute $\eta$ and $\pi$ (numeric truth)

For each merchant $m$:

1. **Rebuild $x_m$** from encoders (intercept | MCC one-hot | channel one-hot | 5 GDP-bucket dummies). Enforce domains.
2. **Load β atomically** from `hurdle_coefficients.yaml`. Assert:

   * $|β| = 1 + C_{\mathrm{mcc}} + 2 + 5$,
   * local feature wiring digest **equals** `design_index_digest` in YAML.
3. **Compute** $\eta_m = β^\top x_m$ in binary64 with fixed-order accumulation; **compute** $\pi_m$ via the overflow-safe **two-branch logistic**.
4. Assert: $\eta_m$ finite; $\pi_m \in [0,1]$.

**Abort the run** on any non-finite or shape/digest mismatch.

---

## V5. Base counter, replay & counter accounting (per row)

Let $\ell =$ `"hurdle_bernoulli"`.

For each hurdle record:

1. **Rebuild the base counter** for $(\ell, m)$ from first principles:

   $$
   (c^{\text{base}}_{\mathrm{hi}},c^{\text{base}}_{\mathrm{lo}})=\operatorname{split64}\big(\operatorname{SHA256}(\text{"ctr:1A"}\ \|\ \texttt{manifest_fingerprint_bytes}\ \|\ \operatorname{LE64}(\texttt{seed})\ \|\ \ell\ \|\ \operatorname{LE64}(m))[0{:}16]\big)
   $$

   Assert `rng_counter_before == base_counter`. (Do **not** trust envelope blindly.)
2. **Classification & budget (S1.2 threshold rule).**

   * $\epsilon = 2^{-53}$
   * `cls = none` if $\epsilon < \pi < 1-\epsilon$; `zero` if $\pi \le \epsilon$; `one` if $\pi \ge 1-\epsilon$.
   * $\Delta = 1$ iff `cls = none`; else $\Delta = 0$.
3. **Counter conservation.** Assert:

   ```
   after == before + Δ       # unsigned 128-bit addition
   ```
4. **Trace join.** On `(seed, parameter_hash, run_id, label=ℓ, merchant_id)`, assert `rng_trace_log.draws == Δ`.
5. **Branch-specific replay.**

   * If `Δ=0` (deterministic): assert `deterministic=true`, `u=null`, and:

     * `cls=zero`  ⇒ `is_multi=false`
     * `cls=one`   ⇒ `is_multi=true`
   * If `Δ=1` (stochastic): regenerate the **lo64** word at `before`, map to $u=(x_0+1)/(2^{64}+1)$; assert $u\in(0,1)$ and `(u < pi) == is_multi`, and envelope `after = before + 1`.

---

## V6. Cross-stream gating (branch purity)

Build $\mathcal{H}_1=\{m: \text{hurdle.is_multi}(m)=1\}$.
For **every** downstream RNG event row in `{gamma_component, poisson_component, nb_final}` (and `dirichlet_gamma_vector`, `gumbel_key` when present), assert `merchant_id ∈ 𝓗₁`. Otherwise raise `logging_gap_no_prior_hurdle`.

---

## V7. Cardinality & uniqueness

* **Uniqueness:** exactly **one** hurdle record per `merchant_id` within `{seed, parameter_hash, run_id}`.
* **Coverage:** `count(hurdle_records) == count(merchant_ids)` for the run.

Any failure is run-blocking.

---

## V8. Partition equality & path authority

For each hurdle row:

* Embedded `{seed, parameter_hash, run_id}` **equal** the path keys.
* `module == "1A.hurdle_sampler"`, `substream_label == "hurdle_bernoulli"`.

Mismatch ⇒ lineage/partition failure.

---

## V9. Optional diagnostics (non-authoritative)

If `hurdle_pi_probs/parameter_hash={parameter_hash}` exists, it is **never** consulted by samplers. Compare its $(\eta,\pi)$ to recomputed values only for sanity.

---

## V10. Failure objects (forensics payload; exact keys)

Emit one JSON object per failure:

```json
{
  "state": "S1",
  "dataset_id": "logs/rng/events/hurdle_bernoulli",
  "failure_code": "rng_counter_mismatch",
  "merchant_id": "m_0065F3A2",
  "detail": {
    "rng_counter_before": {"hi": 42, "lo": 9876543210},
    "rng_counter_after":  {"hi": 42, "lo": 9876543211},
    "delta_expected": 1,
    "trace_draws": 0,
    "pi": 0.37,
    "u": 0.55
  },
  "seed": 1234567890,
  "parameter_hash": "<hex64>",
  "manifest_fingerprint": "<hex64>",
  "design_index_digest": "<hex64>",
  "run_id": "<hex32>",
  "ts_utc": "2025-08-15T10:12:03.123456Z"
}
```

**Failure codes (from S1.6):**
`beta_length_mismatch`, `unknown_category`, `design_index_digest_mismatch`,
`hurdle_nonfinite_eta`, `hurdle_nonfinite_or_oob_pi`,
`rng_envelope_schema_violation`, `substream_label_mismatch`, `module_label_mismatch`,
`rng_counter_mismatch`, `rng_trace_missing_or_mismatch`, `u_out_of_range`,
`hurdle_payload_schema_violation`, `payload_branch_inconsistency`, `decision_mismatch`,
`partition_mismatch`, `wrong_dataset_path`,
`logging_gap_no_prior_hurdle`, `duplicate_hurdle_record`, `cardinality_mismatch`.

---

## V11. End-of-run verdict & artifact

* **Any** failure ⇒ **RUN INVALID**. Write `_FAILED.json` with summary stats and all failure objects; CI blocks merge.
* **No** failures ⇒ **RUN VALID**. Optionally summarise metrics (row counts, draw histogram, min/mean/max `pi`, bounds on `u`).

---

## CI integration (blocking gate)

### CI-1. Job matrix

Run validator for:

* All changed **parameter bundles** (distinct `parameter_hash`) and a small **seed matrix** (e.g., 3 fixed seeds).
* At least one prior **manifest_fingerprint** (regression check vs last known good).

### CI-2. Steps

1. **Schema step:** hurdle + trace rows validate against anchors.
2. **Partition step:** path ↔ embedded equality; label/module equality.
3. **Replay step:** recompute $η,π$; derive `cls` by threshold; budget; rebuild base counter; regenerate $u$ when needed; check decision & counters; trace join.
4. **Gating step:** downstream only when `is_multi=true`.
5. **Cardinality/uniqueness:** one hurdle row per merchant; counts match ingress.

### CI-3. Merge blockers

Any schema violation, partition mismatch, **design_index_digest** mismatch, counter/trace mismatch, non-finite numeric, branch inconsistency, decision mismatch, gating failure, or cardinality/uniqueness failure.

### CI-4. Provenance in the validation bundle

Record fingerprint-scoped summary (pass/fail, counts, first-error samples) in the validation payload; logs remain log-scoped.

---

## Reference validator outline (language-agnostic)

```text
INPUT:
  dict paths; encoders; hurdle_coefficients.yaml; run keys (seed, parameter_hash, run_id)

LOAD:
  H := read_jsonl(hurdle partition)
  T := read_jsonl(trace partition)
  S := read downstream streams

# 1) schema
assert_all_schema(H, "#/rng/events/hurdle_bernoulli")
assert_all_schema(T, "#/rng/core/rng_trace_log")

# 2) partition & envelope constants
for e in H:
  assert path_keys(e) == embedded_keys(e)
  assert e.module == "1A.hurdle_sampler"
  assert e.substream_label == "hurdle_bernoulli"

# 3) recompute (η, π)
beta, digest_yaml := load_beta_and_digest_once()
for e in H:
  x_m, digest_local := rebuild_design_and_digest(e.merchant_id)
  assert digest_local == digest_yaml == e.design_index_digest
  eta, pi := fixed_order_dot_and_safe_logistic(x_m, beta)
  assert is_finite(eta) and is_finite(pi) and 0.0 <= pi <= 1.0

  # 4) classification and budget
  eps := 2^-53
  cls := (pi <= eps) ? "zero" : (pi >= 1.0 - eps) ? "one" : "none"
  Δ   := (cls == "none") ? 1 : 0

  # 5) base counter and counters
  before := base_counter(seed, manifest_fingerprint_bytes, "hurdle_bernoulli", e.merchant_id)
  assert (e.rng_counter_before_hi, e.rng_counter_before_lo) == before
  after  := add_u128(before, Δ)
  assert (e.rng_counter_after_hi, e.rng_counter_after_lo) == after

  # 6) trace reconciliation
  tr := T.match(seed, parameter_hash, run_id, "hurdle_bernoulli", e.merchant_id)
  assert tr.draws == Δ

  # 7) branch-specific checks
  if Δ == 0:
     assert e.deterministic == true and e.u == null
     assert (cls == "zero" and e.is_multi == false) or (cls == "one" and e.is_multi == true)
  else:
     u := regenerate_u01(seed, before)  # lo64 -> (x0+1)/(2^64+1)
     assert 0.0 < u and u < 1.0
     assert (u < pi) == e.is_multi
     assert e.deterministic == false and e.u ∈ (0,1)

# 8) gating
H1 := { e.merchant_id | e.is_multi == true }
for row in S:
  assert row.merchant_id in H1

# 9) uniqueness & cardinality
assert |H| == |ingress_merchant_ids|
assert unique(H.merchant_id)
```

---

**Bottom line:** This validator/CI spec enforces the **final S1 contract** end-to-end: binary64 thresholding, single-uniform budget, **exact** envelope + counter law, **nullable-`u` with `deterministic`**, `design_index_digest` coherence, base-counter reconstruction, and strict partition equality—so any deviation is caught quickly with precise, reproducible failures.

---