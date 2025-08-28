# S1.1 — Inputs, Preconditions, and Write Targets (normative)

## Purpose (what S1 does and does **not** do)

S1 evaluates a **logistic hurdle** per merchant and emits a **Bernoulli outcome** (“single vs multi”). Here we pin **inputs**, **context/lineage**, and **write targets** required to do that deterministically. The logistic, RNG use, and payload specifics are defined in **S1.2–S1.4**.
S1 does **not** specify downstream sampling (NB, ZTP, Dirichlet, etc.) nor CI/monitoring; those live in their respective state specs and the validation harness.

---

## Inputs (available at S1 entry)

### 1) Design vector $x_m$ (column-frozen from S0.5)

**Feature vector (logistic):**

* **Block order (fixed):** $[\,\text{intercept}\,] \;\Vert\; \text{onehot(MCC)} \;\Vert\; \text{onehot(channel)} \;\Vert\; \text{onehot(GDP_bucket)}$.
* **Channel encoder (dim=2):** labels/order exactly $[\,\mathrm{CP},\,\mathrm{CNP}\,]$ (from S0).
* **GDP bucket encoder (dim=5):** labels/order exactly $[\,1,2,3,4,5\,]$ (S0 Jenks-5).
* **MCC encoder (dim $=C_{\text{mcc}}$):** **column order is frozen by S0.5** (the fitting bundle). S1 never derives order from map iteration.
* **Shape invariant:** $|x_m| = 1 + C_{\text{mcc}} + 2 + 5$.

S1 **receives** $x_m$ (already constructed by S0.5) as

$$
x_m = \big[\,1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel}_m),\ \phi_{\text{dev}}(b_m)\,\big]^\top,
$$

with $b_m\in\{1,\dots,5\}$. These are the **only** hurdle features. (NB dispersion’s $\log g_c$ is **not** used here.)

> S0 guarantees domain validity and “one-hot sums to 1” for all encoder blocks. S1 relies on that; it does **not** re-validate domains.

### 2) Coefficient vector $\beta$ (single YAML, atomic load)

Load $\beta$ **atomically** from the hurdle coefficients bundle. The vector contains **all coefficients** aligned to $x_m$: intercept, MCC block, channel block, and the **five** GDP-bucket dummies. Enforce

$$
|\beta| \;=\; 1 + C_{\text{mcc}} + 2 + 5 \quad\text{else abort (design/coeff mismatch).}
$$

*(Design rule context from S0.5: hurdle uses bucket dummies; NB mean excludes them; NB dispersion uses $\log g_c$.)*

### 3) Lineage & RNG context (fixed before any draw)

S0 has already established the **run identifiers** and RNG environment S1 uses:

* `parameter_hash` (hex64) — partitions parameter-scoped artefacts.
* `manifest_fingerprint` (hex64) — lineage key; **not** a path partition here.
* `seed` (uint64) — master Philox seed.
* `run_id` (hex32) — logs-only partition key.
* An `rng_audit_log` exists for this `{seed, parameter_hash, run_id}`. S1 must **not** emit the first hurdle event if that audit row is absent.

**PRNG use model (order-invariant).** All RNG use in 1A is via **label-keyed substreams**. The **base counter** for a given label/merchant pair is derived by S0’s keyed-substream mapping from the tuple

$$
(\texttt{seed},\ \texttt{manifest_fingerprint},\ \texttt{substream_label},\ \texttt{merchant_id}),
$$

independent of execution order or other labels. There is **no** cross-label counter chaining in S1.

---

## Envelope contract (shared fields carried by every hurdle event)

Each hurdle record **must** include the layer envelope fields (names and types per the layer schema):

* `ts_utc` — RFC-3339 UTC with `Z` and **exactly 6 fractional digits** (microseconds).
* `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`.
* `module` — **literal** `"1A.hurdle_sampler"`.
* `substream_label` — **literal** `"hurdle_bernoulli"`.
* Counter words (uint64):
  `rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`.
  *(Producers MUST serialize in this **lo→hi** order; consumers bind by name.)*
* **`draws`** — **required** decimal u128 **string**: the number of uniforms consumed by **this** event.

**Budget identity (unsigned 128-bit):**

$$
\Delta \;\equiv\; \mathrm{u128}(\text{after_hi},\text{after_lo}) - \mathrm{u128}(\text{before_hi},\text{before_lo})
\;=\; \texttt{parse_u128(draws)}.
$$

For hurdle, $\texttt{draws} \in \{"0","1"\}$.
* Additionally, emit `blocks:uint64` as **required** by S0; for hurdle, `blocks ∈ {0,1}` and **must equal** `parse_u128(draws)`.*

---

## Preconditions (hard invariants at S1 entry)

1. **Shape & alignment:** $|\beta|=\dim(x_m)$ and encoder block orders match S0.5’s fitting bundle; else abort (design/coeff mismatch).
2. **Numeric environment:** S0’s math policy is in force: IEEE-754 **binary64**, RNE, **no FMA**, **no FTZ/DAZ**; fixed-order reductions. S1 uses the overflow-safe **two-branch logistic** (no ad-hoc clamp threshold) in S1.2.
3. **RNG audit present:** audit row for `{seed, parameter_hash, run_id}` exists **before** the first hurdle emission; else abort.

---

## Event stream target (authoritative id, partitions, schema)

S1 emits **exactly one** hurdle record per merchant to:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Partitions:** `["seed","parameter_hash","run_id"]` (no `module`/`substream_label`/`manifest_fingerprint` in the path).
* **Schema:** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli` (envelope + payload).

**Uniqueness & completeness (per run).** Within `{seed, parameter_hash, run_id}`, there is **exactly one** hurdle event per `merchant_id`, and the hurdle row count equals the merchant universe count for the run (from S0 ingress for the same `manifest_fingerprint`).

**Trace (totals; no merchant dimension).** The RNG **trace** is per `(module, substream_label)` and records cumulative totals keyed by `{seed, parameter_hash, run_id}`. `blocks_total` is the **normative** counter of cumulative consumption; `draws_total` (if recorded) is **diagnostic** (it must equal the saturating sum of per-event `draws`).

---

## Forward contracts S1 must satisfy (declared here so inputs are complete)

* **Probability (S1.2).** Compute $\eta_m=\beta^\top x_m$ (fixed-order dot in binary64) and $\pi_m$ via the **two-branch** logistic. $\pi_m \in [0,1]$; the row is **deterministic** iff $\pi_m$ equals exactly `0.0` or `1.0` in binary64 (extreme underflow/overflow of `exp`), otherwise $0<\pi_m<1$.
* **RNG substream & $u\in(0,1)$ (S1.3).** Use the keyed substream mapping from **S0**. If $0<\pi_m<1$, consume exactly one open-interval uniform via S0’s `u01` mapping (binary64): $u=((x+1)\times 2^{-64})$, then **if** $u==1.0$ set $u=\mathrm{nextafter}(1.0,\text{below})$; if $\pi_m\in\{0,1\}$, draw **zero**. Envelope counters must satisfy the budget identity.
* **Payload discipline (S1.4).** Payload is `{merchant_id, pi, is_multi, deterministic, u}` where `u` is **required** and **nullable**:

  * if $0<\pi<1$: `u ∈ (0,1)`, `deterministic=false`, `is_multi = 1{u<pi}`;
  * if $\pi\in\{0,1\}$: `u=null`, `deterministic=true`, `is_multi = (pi == 1.0)`.

---

## Failure semantics (at the S1.1 boundary)

Abort the run if any precondition fails: shape/alignment mismatch; missing audit; envelope/schema or path/partition mismatch. Detailed failure codes and validator behaviour are specified in S1.6 and S1.V.

---

## Why this matters (determinism & replay)

By fixing $x_m$, $\beta$, the run identifiers, the **order-invariant substream mapping**, and the envelope/budget law **before** any draw, S1’s Bernoulli outcomes and counters are **bit-replayable** under any sharding or scheduling. This gives the validator a single, unambiguous contract to reproduce S1 decisions.

---

**Bottom line:** S1 starts only when $x_m$, $\beta$, and the lineage/RNG context are immutable and schema-backed; it writes to the single authoritative hurdle stream with fixed envelope and partitions. With these inputs and preconditions, S1.2–S1.4 compute $\eta,\pi$, consume at most one uniform (as required), and emit an event that validators can reproduce exactly.

---

# S1.2 — Probability map (η → π), deterministic & overflow-safe (normative)

## Purpose

Given the frozen design vector $x_m$ and the single-YAML coefficient vector $\beta$ (from S1.1), compute

$$
\eta_m=\beta^\top x_m,\qquad
\pi_m=\sigma(\eta_m)\in[0,1],
$$

then pass $(\eta_m,\pi_m)$ forward to S1.3 (RNG) and S1.4 (event). All numeric environment rules come from **S0.8** (binary64, RN-even, no FMA/FTZ/DAZ, deterministic libm; fixed-order reductions).

---

## Inputs (recap; validated in S1.1)

* **Design vector** $x_m\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$, column order frozen by the fitting bundle (S0.5).
* **Coefficients** $\beta\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$ loaded atomically; shape/order equals $x_m$.

(Shape/order failures are handled at S1.1 / S0.9.)

---

## Canonical definitions (math)

### Linear predictor (fixed-order Neumaier reduction)

$$
\eta_m=\beta^\top x_m
$$

Compute in IEEE-754 **binary64** using the **frozen column order** and the **Neumaier compensated summation** mandated by S0.8. No BLAS reordering or parallel reduction is permitted on any ordering-critical path.

### Logistic map and **overflow-safe evaluation** (normative)

Baseline logistic:

$$
\sigma:\mathbb{R}\to(0,1),\qquad
\sigma(\eta)=\frac{1}{1+e^{-\eta}}.
$$

**Evaluation contract (binary64, deterministic):** Use the **two-branch, overflow-safe form**; do **not** introduce any ad-hoc clamp/threshold:

$$
\pi\;=\;
\begin{cases}
\dfrac{1}{1+e^{-\eta}}, & \eta \ge 0,\\[8pt]
\dfrac{e^{\eta}}{1+e^{\eta}}, & \eta < 0.
\end{cases}
$$

Under the S0.8 math profile, this keeps $\pi\in[0,1]$ in binary64 and avoids spurious overflow/underflow in intermediate terms. For **extreme** $|\eta|$, binary64 underflow/overflow of the exponentials may yield $\pi$ exactly `0.0` or `1.0`—this is the **only** source of exact saturation.

**Determinism flag (derived):**
`deterministic := (pi == 0.0 || pi == 1.0)` using **binary64 equality**. If `deterministic=true` then S1.3 will consume **zero** uniforms; else S1.3 consumes **exactly one** (see S1.3).

---

## Serialization & bounds (normative I/O rules)

* **Binary64 round-trip:** Producers **MUST** serialize `pi` as the **shortest round-trippable decimal** (≤17 significant digits; scientific notation allowed) so that parsing yields the **exact** original binary64. Consumers **MUST** parse as binary64.
* **Legal range:** Enforce `0.0 ≤ pi ≤ 1.0` (binary64). If $\pi$ is exactly `0.0` or `1.0`, it came from the two-branch evaluation under binary64; otherwise `0.0 < pi < 1.0`.
* **Diagnostics:** `eta` is **not** part of the normative hurdle event payload; if recorded, it belongs to a **diagnostic** dataset only (non-authoritative).

---

## Deterministic vs stochastic and consequences for S1.3

* **Stochastic case** $(0<\pi<1)$: S1.3 will draw **one** $u\in(0,1)$ from the keyed substream, then decide `is_multi = (u < pi)`; budget `draws=1`. (Open-interval mapping and substreaming per S0.3.)
* **Deterministic case** $(\pi\in\{0,1\})$: S1.3 performs **no draw**; budget `draws=0`; downstream decision is implied by $\pi$ (`is_multi=true` iff `pi==1.0`).

---

## Numeric policy (must hold; inherited)

S0.8 applies in full: **binary64**, RN-even, **no FMA**, **no FTZ/DAZ**, deterministic libm; fixed-order Neumaier reductions; any NaN/Inf in $\eta$ or $\pi$ is a **hard error** under S0.9.

---

**Bottom line:** S1.2 fixes a single, portable way to compute $(\eta,\pi)$: a **fixed-order Neumaier** dot product followed by a **two-branch logistic** with **no ad-hoc clamp**. Exact `0.0/1.0` arises only from binary64 behavior, and $\pi$ then cleanly determines whether S1.3 consumes **one** uniform or **zero**.

---

## Output of S1.2 (to S1.3/S1.4)

For each merchant $m$, S1.2 produces the numeric pair

$$
(\eta_m,\ \pi_m),\qquad \eta_m\in\mathbb{R}\ \text{(finite)},\ \ \pi_m\in[0,1]\ \text{(binary64)}.
$$

These values are **not persisted by S1.2**. They flow directly into:

* **S1.3 (RNG & decision):** determines whether **one** uniform is consumed $(0<\pi<1)$ or **zero** $(\pi\in\{0,1\})$, and—if stochastic—evaluates `is_multi = (u < pi)`.
* **S1.4 (event payload):** `pi` is a required payload field. `eta` is **not** a normative payload field; if recorded, it belongs to a diagnostic dataset (non-authoritative). S1.4 derives `deterministic` from `pi` and applies the `u` presence rule: `u=null` iff `pi∈{0,1}`, else `u∈(0,1)`.

---

## Failure semantics (abort S1 / run)

S1.2 must **abort the run** if any of the following hold:

1. **Numeric invalid:** either $\eta$ or $\pi$ is non-finite (NaN/±Inf) after evaluation.
2. **Out-of-range:** $\pi \notin [0,1]$ (should not occur with the two-branch logistic).
3. **Shape/order mismatch:** already handled at S1.1; if encountered here, treat as a hard precondition failure.

(Full failure taxonomy, codes, and CI handling live outside S1; this section defines only the operational abort triggers.)

---

## Validator hooks (what the S1 checklist asserts for S1.2)

The single S1 Validator Checklist (referenced once from S1) must be able to **reproduce** S1.2 exactly:

* **Recompute:** Rebuild $x_m$ (from S0’s frozen encoders) and re-evaluate $\eta,\pi$ using the fixed-order binary64 dot product and the **two-branch logistic**. Assert:

  * $\eta$ is finite;
  * $\pi \in [0,1]$;
  * the recomputed $\pi$ matches the emitted `pi` **bit-for-bit** (binary64).
* **Determinism equivalences:**
  $\pi\in\{0,1\} \iff \text{deterministic}=\text{true} \iff \text{draws}=0 \iff u=\text{null}$.
  Otherwise $0<\pi<1 \iff \text{deterministic}=\text{false} \iff \text{draws}=1 \iff u\in(0,1)$.
* **Budget prediction link (with S1.3):** From $\pi$, predict `draws` as above and reconcile with the event envelope and the cumulative trace totals for the hurdle substream.

---

## Reference algorithm (language-agnostic, ordering-stable)

1. **Dot product:** Compute $\eta=\beta^\top x$ in binary64 using the **frozen column order** and **Neumaier** compensation (no reordering/BLAS on ordering-critical paths).
2. **Logistic (two-branch):**

   * if $\eta \ge 0$ ⇒ $\pi = 1/(1+\exp(-\eta))$;
   * else ⇒ $\pi = \exp(\eta)/(1+\exp(\eta))$.
3. **Guards:** $\eta$ and $\pi$ must be finite; $\pi$ must satisfy $0.0 \le \pi \le 1.0$.
4. **Hand-off:** Emit $(\eta,\pi)$ to S1.3/S1.4. The RNG budget and `u` presence follow directly from $\pi$ as stated above.

*(This is a procedural specification, not implementation code; S0 remains the authority for the FP environment and PRNG primitives.)*

---

## How S1.2 interacts with adjacent sections

* **Feeds S1.3:** $\pi$ sets the **uniform budget**: exactly **one** uniform if $0<\pi<1$, else **zero**. If stochastic, S1.3 evaluates `is_multi = (u < pi)` using the open-interval mapping from S0.
* **Feeds S1.4:** `pi` is serialized with **binary64 round-trip** fidelity. `deterministic` is derived from `pi`; `u` is **required** and **nullable** (`null` iff $\pi\in\{0,1\}$, otherwise a number in $(0,1)$). `is_multi` is **boolean** only.

---

**Bottom line:** S1.2 defines a single, portable procedure for $(\eta,\pi)$: **fixed-order** binary64 dot product and a **two-branch logistic** with **no ad-hoc clamp**. That yields $\pi\in[0,1]$ deterministically, and $\pi$ cleanly drives the exact RNG budget and payload semantics required by S1.3–S1.4.

---

# S1.3 — RNG substream & Bernoulli trial (normative)

## Purpose

Given $\pi_m$ from S1.2, consume **at most one** uniform $u_m\in(0,1)$ from the merchant-keyed substream labeled `"hurdle_bernoulli"`, decide

$$
\text{is_multi}(m)\;=\;[\,u_m < \pi_m\,],
$$

and emit exactly one hurdle event (payload in S1.4). The keyed-substream mapping, lane policy, and open-interval $U(0,1)$ are owned by **S0.3** and are referenced here without redefinition.

---

## Inputs (available at S1.3 entry)

* $\pi_m\in [0,1]$ from S1.2.
* Run lineage identifiers: `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, and `module` (registry literal for this producer).
* `merchant_id` (type `$defs/id64`, carried as a JSON **integer** in events; treated as u64 by the S0 keying primitive).
* Dataset/registry anchors for hurdle events and RNG trace are established elsewhere (S1.1 / dictionary); S1.3 does **not** restate paths.

---

## Canonical substream (order-invariant; per merchant)

### Label

$$
\ell := \text{"hurdle_bernoulli"} \quad\text{(registry literal; appears verbatim in the event envelope).}
$$

### Base counter & independence (via S0 primitive)

The **base counter** for each $(\ell, m)$ and the **keyed substream** are obtained **only** through S0’s mapping (pure in $(\texttt{seed}, \texttt{manifest_fingerprint}, \ell, m)$) and therefore **order-invariant** across partitions/shards. S1.3 **does not** chain counters across labels or merchants.

---

## Envelope budgeting (counter law)

For every RNG event, the envelope must satisfy the S0 budgeting identity:

$$
(\texttt{after_hi},\texttt{after_lo}) - (\texttt{before_hi},\texttt{before_lo})
\;=\; \text{parse_u128(draws)},
$$

with unsigned 128-bit arithmetic on counters. In the hurdle stream, `draws ∈ {"0","1"}` (the number of uniforms consumed).
**`blocks` is required**; for hurdle (uint64) it **must** be `0` or `1` and **must equal** `parse_u128(draws)`.

> **Trace model (reconciliation):** The RNG trace is **cumulative** per `(module, substream_label)` within the run (no merchant dimension) and includes `rng_counter_before_{lo,hi}` and `rng_counter_after_{lo,hi}`. For the **final** row per key in a run:
> 
> * `draws_total:uint64` (saturating) equals **Σ parse_u128(draws)** over all hurdle events, and
> * the **u128** counter delta `u128(after)−u128(before)` **equals** `draws_total` (interpreting `draws_total` as u128).
> 
> S1.3 does **not** emit per-event trace rows.
  
**Field-order convention (names are authoritative):** JSON carries
`rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`. Parsers compose u128 as `(hi<<64) | lo`.

---

## Uniform $u\in(0,1)$ & lane policy

* **Engine:** Philox 2×64-10 (fixed in S0). Each block yields two 64-bit words; **single-uniform** events use the **low lane** (`x0`) and **discard** the high lane (`x1`). One counter increment ⇒ one uniform.
* **Mapping to $U(0,1)$:** Use S0’s **open-interval** `u01` mapping from a 64-bit unsigned word to binary64. Exact 0 and exact 1 are **never** produced. (S1.3 references this mapping; it does not redefine it.)

---

## Draw budget & decision

Let $\pi=\pi_m$.

* **Deterministic branch** ($\pi\in{0,1}$).
  `draws="0"`; **no** Philox call; envelope has `after == before`.
  Outcome is implied by $\pi$: `is_multi = true` iff `pi == 1.0`; else `false`.
  Payload rules (S1.4): `deterministic=true`, `u=null`. Set `blocks=0`.

* **Stochastic branch** ($0<\pi<1$).
  Draw **one** uniform $u\in(0,1)$ using the keyed substream and lane policy; `draws="1"`; envelope has `after = before + 1`.
  Decide `is_multi = (u < pi)`; payload: `deterministic=false` and `u` present and numeric. Set `blocks=1`.

All of the above are enforced by the S0/S1 budgeting invariants and the S1 validator checklist (determinism equivalences and gating).

---

**Bottom line:** S1.3 consumes **zero or one** uniform from the merchant-keyed `"hurdle_bernoulli"` substream, applies the **open-interval** mapping, decides with `u < pi`, and records a budget-correct envelope. No cross-label chaining and no per-event trace rows—everything is S0-aligned and replayable.

---

## Envelope & streams touched here (recap; S1.4 formalises payload)

Each hurdle event **must** carry the **complete** layer RNG envelope:

`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks }`

* `module` and `substream_label` are **registry literals** (closed enums).
* `draws` is a non-negative **u128 encoded as decimal string**; budget identity: `u128(after) − u128(before) = parse_u128(draws)`.
* `blocks` is a non-negative uint64; for hurdle, `blocks ∈ {0,1}` and **must equal** `parse_u128(draws)`.

S1.3 writes **one** hurdle event per merchant.  The RNG trace is **cumulative** per `(module, substream_label)` within the run (no merchant dimension). Its totals reconcile to the **sum of event budgets** and to the aggregate counter delta over the hurdle events. S1.3 does **not** emit per-event trace rows.

---

## Failure semantics (abort class bindings)

Abort the run on any of the following:

* **Envelope/label violation.** Missing required envelope fields; wrong `module`/`substream_label` literal; malformed counter fields (`*_hi/*_lo`).
* **Budget identity failure.** `u128(after) − u128(before) ≠ parse_u128(draws)`; or `blocks∉{0,1}` for hurdle.
* **Uniform out of range.** In a stochastic branch, `u ≤ 0` or `u ≥ 1` (violates open-interval `u01`).
* **Determinism inconsistency.** `π∈{0,1}` but `u` present or `deterministic=false`; or $0<\pi<1$ but `u` absent or `deterministic=true`.

(Shape/order and non-finite numeric faults are owned by S1.1–S1.2 preconditions.)

---

## Validator hooks (must pass)

For each hurdle record in the run, the validator performs:

1. **Rebuild base counter (order-invariant).** Using the S0 keyed-substream primitive with `(seed, manifest_fingerprint, substream_label="hurdle_bernoulli", merchant_id)`, recompute the **base counter** and assert envelope `before` equals it. (No cross-label chaining is permitted.)

2. **Branch-specific checks from $\pi$ (from S1.2):**

   * If `draws="0"`: assert $\pi\in{0.0,1.0}$, `u==null`, `deterministic=true`, and `after==before`.
   * If `draws="1"`: generate **one** 64-bit word from the keyed substream at `before` using S0’s lane policy (low lane), map via S0’s **open-interval** `u01`, assert `0<u<1`, assert `(u<pi) == is_multi`, and assert `after = before + 1`.

3. **Trace reconciliation (cumulative).** Let `H` be all hurdle events in the run. For the **final** trace row for `(module, substream_label)`:
   * Assert `trace.draws_total == Σ parse_u128(e.draws)` (diagnostic; saturating uint64),
   * Assert `trace.blocks_total == Σ e.blocks` (normative; saturating uint64),
   * Assert `u128(trace.after_hi,trace.after_lo) − u128(trace.before_hi,trace.before_lo) == trace.blocks_total`.

4. **Partition/embedding equality.** Path partitions `{seed, parameter_hash, run_id}` match the embedded envelope fields; `module` / `substream_label` match the registry literals exactly.

---

## Procedure (ordering-invariant, language-agnostic)

1. **Obtain base counter** for `(label="hurdle_bernoulli", merchant_id)` via the S0 keyed-substream primitive; set `before` accordingly.
2. **Branch on $\pi$:**

   * If $\pi\in{0,1}$: set `draws="0"`, `after=before`, `u=null`, `is_multi=(pi==1.0)`. (If emitting `blocks`, set `0`.)
   * If $0<\pi<1$: fetch **one** uniform $u\in(0,1)$ using the S0 lane policy and `u01`; set `draws="1"`, `after=before+1`, `is_multi=(u<pi)`. (If emitting `blocks`, set `1`.)
3. **Emit hurdle event** (S1.4): envelope includes all required fields above; payload includes `merchant_id`, `pi`, `u` (nullable), `is_multi` (boolean), `deterministic` (derived from `pi`).
4. **Update cumulative RNG trace totals** for `(module, substream_label)` by adding `parse_u128(draws)` (and `+1` to `events_total`); do **not** create per-event trace rows.

*(This is a procedural spec; S0 remains the authority for PRNG keying, counter arithmetic, lane policy, and `u01` mapping.)*

---

## Invariants (S1/H) guaranteed here

* **Bit-replay:** Fixing $(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, both the envelope counters and the pair $(u,\text{is_multi})$ are **bit-identical** under replay.
* **Consumption:** `draws="1"` **iff** $0<\pi<1$; else `"0"`.
* **Schema conformance:** `u` and `deterministic` comply with the hurdle event schema: `u=null` iff $\pi\in{0,1}$; `is_multi` is **boolean** only.
* **Order-invariance:** `before` equals the keyed **base counter** for `(label, merchant)`—never a prior label’s `after`.
* **Gating (forward contract):** Downstream 1A RNG streams appear **iff** `is_multi=true` (stream set obtained via the registry filter; S1 does not enumerate it).

---

**Bottom line:** S1.3 produces a single-uniform Bernoulli decision on a **merchant-keyed**, **label-stable** substream, with a budget-correct envelope and a **cumulative** (per-substream) trace model. Everything is S0-compatible, order-invariant, and validator-checkable without guesswork.

---

# S1.4 — Event emission (hurdle Bernoulli), with **exact** envelope/payload, partitioning, invariants, and validation

### 1) Where the records go (authoritative dataset id, partitions, schema)

Emit **one JSONL record per merchant** to the hurdle RNG dataset:

* **Dataset id:** registry entry for `rng_event_hurdle_bernoulli`.
* **Partitions (path):**

  ```
  logs/rng/events/hurdle_bernoulli/
    seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
  ```

  *(No `manifest_fingerprint`, `module`, or `substream_label` in the path; those are embedded in the envelope.)*
* **Schema:** layer schema anchor `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.

> **Partition keys are exactly** `{seed, parameter_hash, run_id}` as bound in the dictionary/registry.
> **Path ↔ embed equality:** for every row, the embedded `{seed, parameter_hash, run_id}` **must equal** the folder values byte-for-byte.

---

### 2) Envelope (shared; required for **all** RNG events)

Every hurdle record **must** carry the complete layer RNG envelope (single source of truth in the layer schema).

**Required fields**

* `ts_utc`, `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label`,
* `rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`,
* `draws` (required, u128 as a decimal string).

**Optional convenience**

* `blocks` (uint64) — if present for hurdle, it **must** be 0 or 1 and equal `parse_u128(draws)`.

**Semantics**

* `ts_utc` — RFC-3339 UTC with **exactly 6 fractional digits** and `Z` (microseconds).
* `module`, `substream_label` — **registry literals**; for this stream `substream_label == "hurdle_bernoulli"`.
* `rng_counter_*` — 128-bit counters represented as two u64 words; names define the pairing `(lo, hi)`. Object key **order is non-semantic**, but producers **must** use the field names shown (…`_lo`, then …`_hi`).
* `draws` — non-negative **u128 encoded as a base-10 string** (no sign; no leading zeros except `"0"`). It is the **authoritative** per-event uniform count.
* **Budget identity (must hold):**

  ```
  u128(after_hi,after_lo) − u128(before_hi,before_lo) = parse_u128(draws)
  ```

  For the hurdle stream specifically: `draws ∈ {"0","1"}`; `blocks ∈ {0,1}` and `blocks == parse_u128(draws)`.
* **Identifier serialization:** 64-bit identifiers in the envelope (e.g., `seed`) are **JSON integers** per the layer schema (not strings).

---

### 3) Payload (event-specific; minimal and authoritative)

Fields and types (per the hurdle schema):

* `merchant_id` — **id64 JSON integer** (canonical u64).
* `pi` — JSON number, **binary64 round-trip** to the exact value computed in S1.2; must satisfy `0.0 ≤ pi ≤ 1.0`.
* `is_multi` — **boolean** outcome.
* `deterministic` — **boolean**, **derived**: `true` iff `pi ∈ {0.0, 1.0}` (binary64 equality).
* `u` — **required** with type **number | null**:

  * `u = null` iff `pi ∈ {0.0, 1.0}` (deterministic).
  * `u ∈ (0,1)` iff `0 < pi < 1` (stochastic); `u` must also round-trip to the same binary64.

**Outcome semantics (canonical, predicate form)**

* If `0 < pi < 1`: `is_multi := (u < pi)`.
* If `pi ∈ {0.0, 1.0}`: `is_multi := (pi == 1.0)`.

**Branch invariants**

* Deterministic ⇒ `u == null` and **no uniform consumed** (`draws="0"`; if `blocks` present, `blocks=0`).
* Stochastic ⇒ `0 < u < 1`, `is_multi == (u < pi)`, and **exactly one uniform consumed** (`draws="1"`; `blocks=1`).

> The payload is **minimal** and authoritative for the decision; `eta` and any diagnostics are **not** part of this stream (they belong in non-authoritative diagnostic datasets, if present at all).

---

### 4) Canonical examples (normative JSON; object key order non-semantic)

**Stochastic example (`0 < pi < 1`)**

```json
{
  "ts_utc": "2025-08-15T10:03:12.345678Z",
  "run_id": "0123456789abcdef0123456789abcdef",
  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",

  "rng_counter_before_lo": 9876543210,
  "rng_counter_before_hi": 42,
  "rng_counter_after_lo": 9876543211,
  "rng_counter_after_hi": 42,

  "draws": "1",

  "merchant_id": 184467440737095,
  "pi": 0.3725,
  "is_multi": false,
  "deterministic": false,
  "u": 0.1049
}
```

**Deterministic example (`pi ∈ {0,1}`)**

```json
{
  "ts_utc": "2025-08-15T10:03:12.345678Z",
  "run_id": "0123456789abcdef0123456789abcdef",
  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",

  "rng_counter_before_lo": 9876543210,
  "rng_counter_before_hi": 42,
  "rng_counter_after_lo": 9876543210,
  "rng_counter_after_hi": 42,

  "draws": "0",

  "merchant_id": 184467440737095,
  "pi": 1.0,
  "is_multi": true,
  "deterministic": true,
  "u": null
}
```

---

**Bottom line:** This section pins the **single authoritative** hurdle event stream: **where it’s written**, the **complete envelope** (with budget identity), the **minimal payload** with **boolean** `is_multi` and **required** `u:number|null`, and the **branch invariants** that tie `pi`, `u`, `deterministic`, and the **uniform budget** together—no ambiguity, no order-dependence, and no drift from S0.

---

### 5) Write discipline, idempotency, and ordering

* **Exactly one hurdle row per merchant (per run).** Within `{seed, parameter_hash, run_id}` there is **at most one** hurdle event for each `merchant_id`, and the hurdle row count equals the merchant universe cardinality for that `{parameter_hash}` (from ingress). Writes are **append-only** to `part-*` shards.
* **Stable partitioning.** The hurdle event dataset is partitioned **only** by `{seed, parameter_hash, run_id}`; **do not** include `manifest_fingerprint`, `module`, or `substream_label` in the path (they are embedded in the envelope).
* **Module/label stability.** `module` and `substream_label` are **registry literals**. For this stream, `substream_label == "hurdle_bernoulli"`; `module` is the registered producer id (e.g., `"1A.hurdle_sampler"`).
* **Trace linkage (cumulative, substream-scoped).** Maintain a **cumulative** `rng_trace_log` per `(module, substream_label)` (no merchant dimension) within the run, including `rng_counter_before_{lo,hi}` and `rng_counter_after_{lo,hi}`. Totals are **saturating uint64** and equal the **sums** over all hurdle events in the run:

  * `draws_total == Σ parse_u128(draws)` (diagnostic; saturating uint64),
  * `blocks_total == Σ blocks` (normative; saturating uint64), 
  * `events_total ==` hurdle event count.
  * and the **u128** counter delta `u128(after)−u128(before)` **equals** `draws_total`.

---

### 6) Validation hooks (what replay must assert)

* **Schema conformance.** Every row validates against `#/rng/events/hurdle_bernoulli` (payload) and `$defs.rng_envelope` (envelope).
* **Budget identity & replay.** Let `d_m := 1` iff `0 < pi_m < 1`, else `0`. Assert:

  * `u128(after) − u128(before) = parse_u128(draws)`,
  * for hurdle: `parse_u128(draws) ∈ {0,1}` and, **if** `blocks` is present, `blocks = parse_u128(draws) = d_m`.
* **Decision predicate.**

  * If `d_m=0` (deterministic): `pi∈{0,1}`, `u==null`, `deterministic=true`, `after==before`, and `is_multi == (pi==1.0)`.
  * If `d_m=1` (stochastic): regenerate **one** uniform from the keyed substream at `before` (low-lane policy), map via open-interval `u01`, assert `0<u<1` and `(u<pi) == is_multi`; assert `after = before + 1`.
  * **Trace reconciliation (cumulative, substream-scoped).** For the run, aggregate hurdle events and assert on the **final** trace row:

  * `trace.draws_total == Σ parse_u128(draws)` (diagnostic; saturating uint64),
  * `trace.blocks_total == Σ blocks` (normative; saturating uint64),
  * `trace.events_total ==` hurdle event count,
  * `u128(trace.after) − u128(trace.before) == trace.blocks_total`.
* **Gating invariant.** Downstream **1A RNG streams** must appear for a merchant **iff** that merchant’s hurdle event has `is_multi=true`. The set of gated stream IDs is obtained via the **registry filter** (S1 does **not** enumerate names inline).
* **Cardinality & uniqueness.** Hurdle row count equals ingress merchant count for `{parameter_hash}`; uniqueness key is `merchant_id` scoped by `{seed, parameter_hash, run_id}`.

---

### 7) Failure semantics (surface at S1.4)

* **E_SCHEMA_HURDLE.** Record fails schema: missing required envelope fields; wrong types (e.g., `is_multi` not boolean, `u` not `number|null`); `u` violates open interval when stochastic; counters field names malformed.
* **E_COUNTER_MISMATCH.** Budget identity fails: `u128(after) − u128(before) ≠ parse_u128(draws)`; or hurdle emits values outside `{draws∈{"0","1"}}`; or, **if** `blocks` is present, `blocks ≠ parse_u128(draws)`.
* **E_GATING_VIOLATION.** Any downstream 1A RNG event exists for a merchant **without** a conformant hurdle event with `is_multi=true`. (Order is irrelevant; this is a **presence** invariant on the finalized datasets.)
* **E_PARTITION_MISMATCH.** Path partitions `{seed, parameter_hash, run_id}` differ from the same fields embedded in the envelope; or `module`/`substream_label` don’t match registry literals **exactly**.

(Shape/order and non-finite numeric faults are owned by S1.1–S1.2 preconditions.)

---

### 8) Reference emission procedure (ordering-invariant; language-agnostic)

1. **Base counter.** Obtain the **base counter** for `(label="hurdle_bernoulli", merchant_id)` using the S0 keyed-substream primitive; set `before`.
2. **Branch from `pi`.**

   * If `pi ∈ {0.0,1.0}`: set `draws="0"` (and, if emitting `blocks`, set `blocks=0`), `after=before`, `u=null`, `deterministic=true`, `is_multi=(pi==1.0)`.
   * If `0 < pi < 1`: draw **one** uniform `u∈(0,1)` (low-lane, open-interval `u01`); set `draws="1"` (and, if emitting `blocks`, set `blocks=1`), `after=before+1`, `deterministic=false`, `is_multi=(u<pi)`.
3. **Emit hurdle event.** Envelope includes all required fields (`*_lo` then `*_hi` naming); payload includes `merchant_id` (JSON integer), `pi` (binary64 round-trip), `u:number|null`, `is_multi:boolean`, `deterministic:boolean`.
4. **Update cumulative trace (substream-scoped).** Increase `draws_total` for `(module, substream_label)` by `parse_u128(draws)` (saturating uint64). If you emit `blocks` in events, also increase `blocks_total` by `blocks`. Increase `events_total` by 1. Ensure **exactly one** final cumulative record exists per `(module, substream_label)` at state completion.

*(Procedure is normative; S0 remains the authority for PRNG keying, counter arithmetic, lane policy, and `u01`.)*

---

**Bottom line:** S1.4 nails the **write discipline** (one row per merchant; stable `{seed, parameter_hash, run_id}` partitions), the **complete envelope** with an authoritative `draws` field and budget identity, the **minimal authoritative payload** (`is_multi` boolean; `u:number|null`), the **substream-scoped cumulative** trace model, and a validator-oriented hook set (budget, decision, gating, cardinality)—all order-invariant and S0-consistent.

---

# S1.5 — Determinism & Correctness Invariants (normative)

## Purpose

Freeze the invariants that must hold for every merchant’s hurdle decision so downstream states can **trust** and **replay** S1 exactly. The I-H invariants below are stated as precise predicates with the validator obligations that prove them.

---

## I-H0 — Environment & schema authority (precondition)

* **Numeric policy (S0):** IEEE-754 **binary64**, round-to-nearest-even, **no FMA**, **no FTZ/DAZ**; fixed-order reductions; deterministic `exp`.
* **Schema authority:** Every RNG record conforms to the **layer envelope** (single anchor) and its **event-specific schema**. The hurdle stream uses the registered dataset id and the schema anchor for `rng/events/hurdle_bernoulli`.

---

## I-H1 — Bit-replay (per merchant, per run)

**Statement.** For fixed inputs
$(x_m,\ \beta,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the pair $(u_m,\ \text{is_multi}(m))$ and the envelope counters $(C^{\text{pre}}_m,\ C^{\text{post}}_m)$ are **bit-identical** across replays and **independent of emission order** or sharding.

**Why it holds.** The keyed-substream primitive derives a **base counter** for $(\ell=\text{"hurdle_bernoulli"}, m)$ that depends only on the run keys and $(\ell,m)$. The draw budget is a pure function of $\pi_m$. The uniform $u_m$ is obtained by the S0 **open-interval** mapping from the substream (low-lane) and therefore deterministic.

**Validator.** Rebuild the base counter from `(seed, manifest_fingerprint, substream_label="hurdle_bernoulli", merchant_id)`; assert envelope `before` matches.
If `draws="1"`, regenerate $u$ and assert `(u < pi) == is_multi`. Assert counters match exactly.

---

## I-H2 — Consumption & budget (single-uniform law)

**Statement.** Let $d_m = \mathbf{1}\{0 < \pi_m < 1\}$. The hurdle consumes exactly `draws = d_m` uniforms and:

* If $0<\pi_m<1$: `after = before + 1`.
* If $\pi_m \in {0,1}$: `after = before`.

**Law.** Envelope budgeting must satisfy
`u128(after) − u128(before) = parse_u128(draws)` (unsigned 128-bit arithmetic). For the hurdle, `draws ∈ {"0","1"}`; if `blocks` is present it **must equal** `parse_u128(draws)` and therefore `blocks ∈ {0,1}`.

**Trace model (cumulative).** RNG trace is **cumulative per `(module, substream_label)`** within the run (no merchant dimension). Its totals equal the **sums across all hurdle events** for that substream.

**Validator.** Check the envelope identity above; aggregate event budgets over all hurdle rows for `(module, substream_label)` and assert equality with the trace totals.

---

## I-H3 — Schema-level payload discipline

**Statement.** The hurdle payload is **minimal and authoritative** with fields:
`merchant_id` (**id64 integer**), `pi` (binary64 round-trip), `is_multi` (**boolean**), `deterministic` (**boolean**), `u` (**number|null**, **required**).

**Equivalences (binary64 semantics).**

* `deterministic ⇔ (pi ∈ {0.0, 1.0}) ⇔ draws="0" ⇔ u == null`.
* `¬deterministic ⇔ (0 < pi < 1) ⇔ draws="1" ⇔ u ∈ (0,1)` and `is_multi == (u < pi)`.

`is_multi` is **boolean only** (never `{0,1}`); any other encoding is non-conformant.

---

## I-H4 — Branch purity (downstream gating)

**Statement.** Downstream **1A RNG streams** for a merchant appear **iff** that merchant’s hurdle event has `is_multi=true`.

**Authority.** The set of gated stream IDs is obtained via the **registry filter** (e.g., `owner_segment=1A`, `state>S1`, `gated_by_hurdle=true`); S1 does **not** enumerate stream names inline.

**Validator.** For each merchant, check presence/absence of all gated streams per the registry list against the merchant’s hurdle `is_multi` value.

---

**Bottom line:** S1.5 fixes the invariant surface: a deterministic, order-invariant substream; a single-uniform budget with a strict envelope law and **cumulative** trace; a minimal, typed payload with `u:number|null` and boolean `is_multi`; and a registry-driven gating rule. These invariants give downstream states and validators a single, unambiguous contract for replay and auditing.

---

## I-H5 — Cardinality & uniqueness (per run)

* Exactly **one** hurdle record per merchant within `{seed, parameter_hash, run_id}`. **No duplicates.**
* **Presence gate, not order:** downstream 1A RNG streams are validated **by presence** relative to the hurdle decision (see I-H4). Emission order is **unspecified** and not validated.

**Validator.** Count hurdle rows and assert equality with the ingress `merchant_ids` for the run; assert uniqueness of `merchant_id` within the hurdle partition.

---

## I-H6 — Envelope completeness & equality with path keys

* Every record contains the **full** RNG envelope required by `$defs.rng_envelope`. `draws` is **required**; `blocks` must equal `parse_u128(draws)` and for hurdle be `0` or `1`.
* Embedded `{seed, parameter_hash, run_id}` **equal** the same keys in the dataset path. `module` and `substream_label` are registry literals checked **in the envelope** (they do **not** appear in the path).

---

## I-H7 — Order-invariance & concurrency safety

* Emission **order is unspecified**; correctness depends only on per-row content. Replays with different shard orders yield byte-identical counters and decisions (I-H1).
* Writers may produce multiple `part-*` files; **set equivalence** of rows defines dataset equivalence.

---

## I-H8 — Independence across merchants & substreams

* Base counters are derived **per (label, merchant_id)** via the keyed mapping, so distinct pairs receive **disjoint** substreams under a fixed `{seed, manifest_fingerprint}`.
* `substream_label` in the envelope is **exactly** `"hurdle_bernoulli"`, preventing accidental reuse of counters intended for other labels.

---

## I-H9 — Optional diagnostics remain out of band

* If any diagnostic cache (e.g., `hurdle_pi_probs`) exists, it is **non-authoritative**. S1 decisions must match an **independent recomputation** of $(\eta,\pi)$ from $(x_m,\beta)$. Validators may compare for sanity; disagreements never override the event.

---

## I-H10 — Replay equations (what the validator recomputes)

For each hurdle row $r$ with merchant $m$:

1. **Recompute $\eta,\pi$.** Using S1.2 rules (fixed-order dot + two-branch logistic (no clamp)), assert `finite(η)` and `0.0 ≤ pi ≤ 1.0`.
2. **Rebuild base counter.** Using `(seed, manifest_fingerprint, substream_label="hurdle_bernoulli", merchant_id)`, assert `rng_counter_before == base_counter`.
3. **Budget identity.** From $\pi$, set `draws = "1"` iff $0<\pi<1$, else `"0"`. Assert
   `u128(after) − u128(before) = parse_u128(draws)` and, if `blocks` is present, `blocks == parse_u128(draws)` (and for hurdle `blocks ∈ {0,1}`, `draws ∈ {"0","1"}`).
   **Trace reconciliation:** join to the **cumulative** trace record for `(module, substream_label)` and assert its totals equal the **sum of hurdle event budgets**.
4. **Outcome consistency.**

   * If `draws="1"`: regenerate a single uniform via the S0 lane policy & open-interval mapping; assert `0<u<1` and `(u < pi) == is_multi`.
   * If `draws="0"`: assert `pi ∈ {0.0,1.0}`, `u == null`, `deterministic == true`, and `is_multi == (pi == 1.0)`.

---

## Failure bindings (S0.9 classes surfaced by these invariants)

* **Envelope/label/counter failures** → RNG envelope & accounting failure (**F4**) → **abort run**.
* **Partition mismatch (path vs embedded)** → lineage/partition failure (**F5**) → **abort run**.
* **Schema breach** (e.g., missing required envelope fields; `is_multi` not boolean; `u` not `number|null`; `u` out of (0,1) when stochastic) → schema failure (treated as **F4**).
* **Gating violation** (downstream event exists when hurdle `is_multi=false` or no hurdle event) → coverage/gating failure (validator; event-family coverage class, e.g., **F8**).

---

## What this guarantees downstream

* **Deterministic hand-off (by content, not cursor).** Each merchant has a single authoritative hurdle decision (`is_multi`) and a **self-contained** envelope. **Downstream states derive their own base counters** from the keyed mapping for their **own labels**; there is **no** requirement that `before(next) == after(hurdle)`.
* **Auditable lineage.** Hurdle events are partitioned by `{seed, parameter_hash, run_id}`; validation/egress bundles are fingerprint-scoped. Consumers can verify they are reading the intended parameterization using the embedded `manifest_fingerprint`.

---

**Bottom line:** S1.5 (complete) nails the invariants that make S1 reproducible and safe to build on: uniqueness/cardinality, full envelope with budget identity, order-invariance, cross-label independence, gated downstream presence, diagnostics out-of-band, and validator-ready replay equations—mapped to S0.9 failure classes for actionable aborts.

---

# S1.6 — Failure modes (normative, abort semantics)

**Scope.** Failures here are specific to S1 (hurdle): design/β misuse, numeric invalids, schema/envelope breaches, RNG counter/accounting errors, partition drift, and downstream gating. This section formalizes **all predicates, detection points, and run-abort semantics** that S1 may surface.

**Authoritative references:**
Layer schema (envelope anchor + hurdle event schema), dataset dictionary/registry (dataset id, partitions, enums), and S1 invariants (I-H1..I-H10).

---

## Family A — Design / coefficients misuse (compute-time hard abort)

**A1. `beta_length_mismatch`**
**Predicate.** `len(β) ≠ 1 + C_mcc + 2 + 5` when forming $\eta = \beta^\top x$.
**Detect at.** S1.1/S1.2 entry. **Abort run.**
**Forensics.** `{expected_len, observed_len, mcc_cols, channel_cols, bucket_cols}`.

**A2. `unknown_category`**
**Predicate.** `mcc_m` not in MCC dictionary, or `channel_m ∉ {CP,CNP}`, or `b_m ∉ {1..5}`.
**Detect at.** Precondition breach (inputs from S0). **Abort run.**
**Forensics.** `{merchant_id, field, value}`.

**A3. `column_order_mismatch`**
**Predicate.** Frozen encoder column order does **not** match β’s bundle order.
**Detect at.** S1.1 design load. **Abort run.**
**Forensics.** `{block:"mcc|channel|bucket", dict_digest, beta_digest}`.

---

## Family B — Numeric invalids (compute-time hard abort)

**B1. `hurdle_nonfinite_eta`**
**Predicate.** $\eta$ non-finite after fixed-order binary64 dot product.
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta}`.

**B2. `hurdle_nonfinite_or_oob_pi`**
**Predicate.** $\pi$ non-finite **or** $\pi \notin [0,1]$ after the two-branch logistic (no clamp).
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta, pi}`.

---

## Family C — Envelope & accounting (RNG/logging hard abort)

**C1. `rng_envelope_schema_violation`**
**Predicate.** Missing/mistyped **envelope** field required by the anchor:
`{ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks}`.
` for hurdle.)
**Detect at.** Writer + validator schema checks. **Abort run.**
**Forensics.** `{dataset_id, path, missing_or_bad:[...]}`.

**C2. `substream_label_mismatch`**
**Predicate.** Envelope `substream_label` ≠ registry literal `"hurdle_bernoulli"`.
**Detect at.** Writer assertion; validator. **Abort run.**

**C3. `rng_counter_mismatch`**
**Predicate.** `u128(after) − u128(before) ≠ parse_u128(draws)`; or `blocks ≠ parse_u128(draws)`. For hurdle, it must also satisfy `blocks ∈ {0,1}` and `draws ∈ {"0","1"}`.
**Detect at.** Writer (optional) and validator reconciliation. **Abort run.**
**Forensics.** `{before_hi, before_lo, after_hi, after_lo, blocks, draws}`.

**C4. `rng_trace_missing_or_totals_mismatch`**
**Predicate.** Missing **final cumulative** `rng_trace_log` record for `(module, substream_label)` within the run, **or** its totals ≠ **sum of event budgets** for that key, **or** its **u128** counter delta `u128(after)−u128(before)` ≠ `draws_total`.
**Detect at.** Validator aggregate. **Abort run.**

**C5. `u_out_of_range`**
**Predicate.** In a stochastic branch, payload `u` not in `(0,1)` (open-interval violation).
**Detect at.** Writer check; validator schema + re-derivation. **Abort run.**
**Forensics.** `{merchant_id, u, pi}`.

---

## Family D — Payload/schema discipline (hurdle event)

**D1. `hurdle_payload_violation`**
**Predicate.** Record fails the hurdle event schema: missing any of `{merchant_id, pi, is_multi, deterministic, u}`; `is_multi` not **boolean**; `u` not `number|null`; `pi` not binary64-round-trippable (or out of `[0,1]`).
**Detect at.** Writer schema validation; CI/validator. **Abort run.**

**D2. `deterministic_branch_inconsistent`**
**Predicate.** Payload contradicts branch rules:

* `0<pi<1` but `u` absent/`null` or `deterministic=true`, **or**
* `pi∈{0,1}` but `u` numeric or `deterministic=false`.
  **Detect at.** Writer; validator. **Abort run.**

---

## Family E — Partitioning & lineage coherence (paths vs embedded)

**E1. `partition_mismatch`**
**Predicate.** Path partitions `{seed, parameter_hash, run_id}` do **not** equal the same embedded envelope fields; or path includes unexpected partitions (e.g., `module`, `substream_label`, `manifest_fingerprint`).
**Detect at.** Writer; validator lint. **Abort run.**

**E2. `wrong_dataset_path`**
**Predicate.** Hurdle events written under a path that does not match the dictionary/registry binding (dataset id ↔ path template).
**Detect at.** Writer; validator path lint. **Abort run.**

---

## Family F — Coverage & gating (cross-stream structural)

**F1. `gating_violation_no_prior_hurdle_true`**
**Predicate.** Any downstream **1A RNG stream** appears for merchant $m$ **without** a conformant hurdle event with `is_multi=true` in the run. (Presence rule; emission order irrelevant.)
**Detect at.** Validator cross-stream join using the **registry-filtered** set of gated streams. **Run invalid (hard).**

**F2. `duplicate_hurdle_record`**
**Predicate.** More than one hurdle event for the same merchant within `{seed, parameter_hash, run_id}`.
**Detect at.** Validator uniqueness check. **Abort run.**

**F3. `cardinality_mismatch`**
**Predicate.** `count(hurdle_events) ≠ count(merchant_ids)` for the run.
**Detect at.** Validator count check. **Abort run.**

---

**Bottom line:** S1.6 enumerates **all abortable predicates** for the hurdle: design/β misuse, numeric invalids, complete envelope with strict **budget identity**, cumulative trace reconciliation, payload typing/branch rules, exact partition/embedding equality, and registry-driven gating. Each failure includes a precise detection point and forensics so the run can halt with actionable evidence.

---

## Error object (forensics payload; exact fields)

Every S1 failure MUST emit a JSON object (alongside the validation bundle / `_FAILED.json` sentinel) carrying lineage + precise forensics:

```json
{
  "failure_code": "rng_counter_mismatch",
  "state": "S1",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "dataset_id": "rng_event_hurdle_bernoulli",
  "path": "logs/rng/events/hurdle_bernoulli/seed=1234567890123456789/parameter_hash=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789/run_id=0123456789abcdef0123456789abcdef/part-0001.jsonl",
  "merchant_id": 184467440737095,
  "detail": {
    "before": {"hi": 42, "lo": 9876543210},
    "after":  {"hi": 42, "lo": 9876543211},
    "draws": "1",
    "expected_delta": "1",
    "blocks": 1,
    "trace_draws_total": 0
  },
  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "run_id": "0123456789abcdef0123456789abcdef",
  "ts_utc": "2025-08-15T10:12:03.123456Z"
}
```

* `dataset_id` is the **registry id**; `path` is the concrete file path (optional but helpful).
* Identifiers (`seed`, `merchant_id`) are **JSON integers** (schema-conformant). `blocks` may be absent in other failure objects; when present, it must equal `parse_u128(draws)` for hurdle.

---

## Where to detect (first line) & who double-checks

| Family / Code                  | First detector (runtime)         | Secondary (validator / CI)                               |
|--------------------------------|----------------------------------|----------------------------------------------------------|
| A1–A3 design/β                 | S1.1/S1.2 guards                 | (optional) build lints                                   |
| B1–B2 numeric invalid          | S1.2 evaluation guards           | Re-eval η, π                                             |
| C1 envelope schema             | Writer JSON-Schema check         | Validator schema pass                                    |
| C2 label mismatch              | Writer assertion                 | Validator                                                |
| C3 counter mismatch            | Writer (optional)                | Counter reconciliation (after−before vs draws\[/blocks]) |
| C4 trace missing/totals mis    | —                                | Trace aggregate vs Σ(event budgets) & counter delta      |
| C5 u out of range              | Writer check                     | `u01` + recompute                                        |
| D1 payload schema              | Writer JSON-Schema check         | Validator schema pass                                    |
| D2 deterministic inconsistency | Writer assertion                 | Recompute branch from π                                  |
| E1 partition mismatch          | Writer path/embed equality check | Path lint (only `{seed, parameter_hash, run_id}`)        |
| E2 wrong dataset path          | —                                | Dictionary/registry binding lint                         |
| F1 gating violation            | —                                | Cross-stream presence check via **registry filter**      |
| F2 duplicate record            | —                                | Uniqueness check                                         |
| F3 cardinality mismatch        | —                                | Row count vs ingress merchant set                        |

> **Gating note:** Enforcement is **presence-based**: downstream gated streams must exist **iff** hurdle `is_multi=true`. No temporal “prior” requirement.

---

## Validator assertions (executable checklist)

Using the dictionary/registry bindings and schema anchors:

1. **Schema:** validate hurdle events **and** cumulative trace against the layer anchors (envelope + event + trace).
2. **Counters & budget:** assert
   `u128(after) − u128(before) = parse_u128(draws)` and, for hurdle, `draws ∈ {"0","1"}`; if `blocks` is present, assert `blocks = parse_u128(draws)` and `blocks ∈ {0,1}`.
   **Trace reconciliation:** per `(module, substream_label)`, `blocks_total` equals **Σ(event blocks)** (saturating to uint64; normative) and `draws_total` (if present) equals **Σ(event draws)** (saturating to uint64; diagnostic).
3. **Decision:** recompute $\eta,\pi$ (S1.2 rules); if stochastic (`draws="1"`), regenerate one uniform from the keyed **base counter** (low-lane, open-interval `u01`) and assert `0<u<1` and `(u<pi) == is_multi`.
4. **Deterministic regime:** if `draws="0"`, assert `pi ∈ {0,1}`, `deterministic=true`, and `u == null`.
5. **Partition lint:** path partitions `{seed, parameter_hash, run_id}` equal the embedded envelope; path **must not** include `module`, `substream_label`, or `manifest_fingerprint`.
6. **Gating:** build the set of **gated 1A RNG streams** from the **registry filter**; for each merchant, presence/absence of those streams is **iff** hurdle `is_multi=true`.
7. **Uniqueness & cardinality:** within the run partition, **exactly one** hurdle row per `merchant_id`; hurdle row count equals the ingress merchant cardinality.

---

## Minimal examples (concrete)

* **Numeric invalid (B2).** `pi` is NaN after logistic ⇒ `hurdle_nonfinite_or_oob_pi` ⇒ **abort**.
* **Envelope gap (C1).** Missing `rng_counter_after_hi` ⇒ `rng_envelope_schema_violation` ⇒ **abort**.
* **Gating failure (F1).** A gated stream (from the **registry filter**) exists for merchant `m` while hurdle `is_multi=false` or no hurdle event exists ⇒ `gating_violation_no_prior_hurdle_true` ⇒ **run invalid**.

---

**Bottom line:** S1.6 (complete) specifies the **failure predicates**, **where they’re detected**, the **forensics object** (with registry ids, lineage, counters, and budgets), and the **validator checklist**—all consistent with S0 and the locked S1 contracts (nullable `u`, boolean `is_multi`, full envelope with required `draws`, stable `{seed, parameter_hash, run_id}` partitions, cumulative trace per substream, and registry-driven gating).

---

# S1.7 — Outputs of S1 (state boundary, normative)

## A) Authoritative event stream that S1 **must** persist

For every merchant $m\in\mathcal{M}$, S1 writes **exactly one** JSONL record to the hurdle RNG dataset:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Dataset id (registry):** `rng_event_hurdle_bernoulli`.
* **Partitions (path):** `{seed, parameter_hash, run_id}` only.
  *(Do **not** include `manifest_fingerprint`, `module`, or `substream_label` in the path; those live in the envelope.)*
* **Schema:** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.

**Envelope (shared; required for all RNG events):**
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks }

* `module`, `substream_label` are **registry literals** (closed enums). For this stream, `substream_label == "hurdle_bernoulli"`.
* **Budget identity (must hold):**
  `u128(after) − u128(before) = parse_u128(draws)` (unsigned 128-bit arithmetic).
  For the hurdle stream, `draws ∈ {"0","1"}` (unit = one 64-bit uniform). If `blocks` is present, it **must** equal `parse_u128(draws)` and hence `blocks ∈ {0,1}`.

**Identifier serialization:** fields typed as `uint64/id64` in the schema (e.g., `seed`, counter words, `merchant_id`) are emitted as **JSON integers** (not strings).

**Payload (authoritative, minimal):**
`{ merchant_id, pi, is_multi, deterministic, u }`

* `merchant_id` — **id64 integer**.
* `pi` — JSON number, **binary64 round-trip**, `0.0 ≤ pi ≤ 1.0`.
* `is_multi` — **boolean**.
* `deterministic` — **boolean**, derived: `true` iff `pi ∈ {0.0, 1.0}` (binary64).
* `u` — **required** `number|null`: `u=null` iff `pi ∈ {0,1}`, else `u∈(0,1)` (open interval).

> Diagnostic/context fields (e.g., `eta`, `mcc`, `channel`, `gdp_bucket_id`) are **not** part of this authoritative stream. If materialized, they live in diagnostic datasets only.

**Companion trace (cumulative; per-substream, no merchant dimension):**
Maintain a **cumulative** `rng_trace_log` row per `(module, substream_label)` within the run; its totals equal the **sum of event budgets** for that substream. *(No per-event trace rows; no merchant dimension in trace.)*

> The hurdle event is the **only authoritative source** of the decision and its **own** counter evolution.

---

## B) In-memory **handoff tuple** to downstream (typed, deterministic)

S1 does not persist a “state table”; it yields a **typed tuple** per merchant to the orchestrator:

$$
\boxed{\ \Xi_m \;=\; \big(\ \text{is_multi}:\mathbf{bool},\ N:\mathbb{N},\ K:\mathbb{N},\ \mathcal{C}:\text{set[ISO_3166-1 alpha-2]},\ C^{\star}:\text{u128}\ \big)\ }.
$$

**Field semantics (normative):**

* `is_multi` — hurdle outcome (**boolean**) from the event payload.
* `N` — **target outlet count** for S2 when `is_multi=true`; set `N:=1` on the single-site path.
* `K` — **non-home country budget**; initialize `K:=0` on the single-site path; multi-site assigns later.
* `𝓒` — **country set accumulator**; initialize `{ home_iso(m) }`, expand only in S2+/S3+.
* $C^{\star}$ — the hurdle event’s **post** counter as u128 (`{after_hi, after_lo}`), carried **only for audit**.

**Crucial counter rule:**
Downstream states **do not** chain from $C^{\star}$. Each downstream RNG stream derives its **own base counter** from S0’s keyed-substream mapping using its **own** `(module, substream_label, merchant_id)`; there is **no cross-label counter chaining**.

**Branch semantics:**

* If `is_multi == false`: set `N:=1`, `K:=0`, `𝓒 := { home_iso(m) }`, and route to **S7** (single-home placement). No NB/ZTP/Dirichlet/Gumbel streams may appear.
* If `is_multi == true`: route to **S2** (NB branch). `N`, `K` are assigned downstream; `𝓒` starts as `{ home_iso(m) }`.

---

## C) Downstream visibility (for validation & joins)

Validators discover **gated** 1A RNG streams via the **registry filter** (e.g., `owner_segment=1A`, `state>S1`, `gated_by_hurdle=true`) and expect those streams to be **present iff** `is_multi=true` for a merchant. S1 does **not** enumerate stream names inline.

---

## D) Optional diagnostic dataset (parameter-scoped; not consulted by samplers)

If enabled, a diagnostic table may be persisted (often produced in S0.7):

```
data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/…
```

**Schema:** `#/model/hurdle_pi_probs`. **Contents (per merchant):** `{manifest_fingerprint, merchant_id, logit:eta, pi}`.
This dataset is **read-only** and **non-authoritative**; samplers never consult it.

---

## E) Boundary invariants (must hold when S1 ends)

1. **Single emit:** exactly one hurdle record per merchant per `{seed, parameter_hash, run_id}` and exactly one $\Xi_m$.
2. **Cross-label independence:** downstream RNG events **derive** their base counters via S0’s keyed mapping for their **own** labels; there is **no** requirement that `before(next) == C^{\star}`.
3. **Branch purity (gating):** gated downstream 1A RNG streams are **present iff** `is_multi=true`.
4. **Lineage coherence:** dataset paths use `{seed, parameter_hash, run_id}`; embedded envelope keys equal the path keys; egress/validation later uses `fingerprint={manifest_fingerprint}`.
5. **Numeric consistency:** hurdle `pi` equals the S1.2 recomputed value (fixed-order dot + two-branch logistic (no clamp)).

---

## F) Minimal handoff construction (reference)

```text
INPUT:
  hurdle_event for merchant m (envelope + payload), home_iso(m)

OUTPUT:
  Xi_m = (is_multi, N, K, C_set, C_star)

1  is_multi := hurdle_event.payload.is_multi                 # boolean
2  C_star   := (envelope.rng_counter_after_hi, envelope.rng_counter_after_lo)  # audit only

3  if is_multi == false:
4      N := 1
5      K := 0
6      C_set := { home_iso(m) }
7      next_state := S7
8  else:
9      N := <unassigned>   # set in S2
10     K := <unassigned>   # set in cross-border/ranking
11     C_set := { home_iso(m) }
12     next_state := S2

13  return Xi_m, next_state
```

*(This is a handoff contract, not persisted state. Downstream states derive their **own** base counters; `C_star` is for audit.)*

---

**Bottom line:** S1 outputs **one** authoritative hurdle event per merchant (complete envelope + minimal payload) and a **typed, deterministic handoff tuple**. The boundary guarantees **gated presence**, **cross-label RNG independence** (no counter chaining), stable 3-key partitions, and numeric consistency—giving downstream states and validators a clean, replayable interface.

---

# S1.V — Validator & CI (normative)

## V0. Purpose & scope

Prove that every hurdle record is (a) **schema-valid**, (b) **numerically correct** under the pinned math policy, (c) **RNG-accounted** (counters ↔ uniform budget), (d) **partition-coherent**, and (e) **structurally consistent** with downstream streams via **presence-based gating**.
Validator logic is **order-invariant** (shard/emit order is irrelevant) and uses the **dataset dictionary/registry** plus S1 invariants.

---

## V1. Inputs the validator must read

1. **Locked specs:** the S1 state text (this document) and the combined journey spec (for cross-state joins).
2. **Event datasets (logs):**

   * **Hurdle events** — dataset id `rng_event_hurdle_bernoulli`, schema `#/rng/events/hurdle_bernoulli`, partitions

     ```
     logs/rng/events/hurdle_bernoulli/
       seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
     ```
   * **RNG trace (cumulative)** — per **(module, substream_label)** totals **and** `rng_counter_before/after` for the run (no merchant dimension; append-safe; take the **final** row per key).
   * **Downstream gated streams** — discovered via the **registry filter** (e.g., `owner_segment=1A`, `state>S1`, `gated_by_hurdle=true`). S1 does **not** enumerate names inline.
3. **Design/β artefacts:** frozen encoders/dictionaries and the single-YAML hurdle coefficients bundle (β).
4. **Lineage keys:** `{seed, parameter_hash, manifest_fingerprint, run_id}` from path + envelope; the **shared RNG envelope** is mandatory for each event.

---

## V2. Discovery & partition lint (dictionary-backed)

* **Locate** the hurdle partition for the run using the dictionary/registry binding.
* **Path ↔ embed equality:** for **every row**, the embedded envelope keys
  `{seed, parameter_hash, run_id}` **equal** the same path keys.
  `module` and `substream_label` are checked **in the envelope only** as registry literals (they do **not** appear in the path).
  `manifest_fingerprint` is **embedded only** (never a path partition).

* **Schema anchors** are fixed by the layer schema set. Payload keys are exactly
  `{merchant_id, pi, is_multi, deterministic, u}`; the envelope is the layer-wide anchor.

**Discovery checks:**

* **P-1:** partition exists; **P-2:** at least one `part-*` file;
* **P-3:** hurdle row count equals the ingress merchant count for the run;
* **P-4:** uniqueness of `merchant_id` within `{seed, parameter_hash, run_id}`.

---

## V3. Schema conformance (row-level)

Validate **every** hurdle record against:

* **Envelope (complete):**
  `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks`.
  (`module`/`substream_label` are **registry literals**; `draws` is **u128 as a decimal string**.)
* **Payload (minimal, authoritative):**
  `merchant_id` (**id64 JSON integer**), `pi` (**binary64 round-trip**, `0.0 ≤ pi ≤ 1.0`),
  `is_multi` (**boolean**), `deterministic` (**boolean**, derived from `pi`),
  `u` (**required** with type **number|null**: `null` iff `pi ∈ {0,1}`, else `u∈(0,1)`).

> No diagnostic/context fields (e.g., `eta`, `mcc`, `channel`, `gdp_bucket_id`) are allowed in this authoritative stream.

---

## V4. Recompute η and π (numeric truth)

For each merchant $m$:

1. Rebuild $x_m$ using the **frozen encoders** (one-hot sums = 1; column order equals the fitting bundle).
2. Load β atomically; assert $|β| = 1 + C_{\text{mcc}} + 2 + 5$ and **exact column alignment** with $x_m$.
3. Compute $\eta_m = β^\top x_m$ in binary64 (fixed-order Neumaier).
4. Compute $\pi_m$ with the **two-branch logistic (no clamp)**: assert finiteness and `0.0 ≤ pi ≤ 1.0`.

**Fail fast:** any non-finite $\eta$/$\pi$ or shape/order mismatch is a **hard abort**.

---

## V5. RNG replay & counter accounting (per row)

Let the label be the registry literal `substream_label="hurdle_bernoulli"`.

1. **Base counter reconstruction:** using `(seed, manifest_fingerprint, substream_label, merchant_id)` and the S0 keyed-substream primitive, recompute the **base counter** and assert it equals the envelope `rng_counter_before`.
2. **Budget from π:** set `draws_expected = 1` iff `0 < pi < 1`, else `0`.
3. **Budget identity:** compute `delta = u128(after) − u128(before)` and assert
   `delta == parse_u128(draws) == draws_expected`.
   Also assert `blocks == parse_u128(draws)` and `blocks ∈ {0,1}`.
4. **Lane policy:** assert `delta ∈ {0,1}`.
5. **Stochastic vs deterministic:**

   * If `draws_expected = 0`: assert `pi ∈ {0,1}`, `u == null`, `deterministic == true`, and `is_multi == (pi == 1.0)`.
   * If `draws_expected = 1`: regenerate **one** uniform from the keyed substream at `before` (low lane), map via **open-interval** `u01`, assert `0<u<1` and `(u < pi) == is_multi`.

**Trace reconciliation (cumulative):** For the **final** trace row per `(module, substream_label)`:
`draws_total == Σ parse_u128(draws)` (diagnostic; saturating `uint64`), and `blocks_total == Σ blocks` (normative; saturating `uint64`); **and** `u128(after) − u128(before) == blocks_total`.

> Naming: use `draws_expected` (from π), `blocks`/`draws` (from envelope), and `delta` for counter difference.

---

## V6. Cross-stream gating (branch purity)

Let $\mathcal{H}_1=\{m\mid \text{hurdle.is\_multi}(m)=\text{true}\}$.
Build the **set of gated 1A RNG streams** via the **registry filter**. For **every** row in any gated stream, assert `merchant_id ∈ 𝓗₁`. For merchants **not** in $𝓗_1$, assert **no** gated rows exist. *(Presence-based; no temporal ordering requirement.)*

---

## V7. Cardinality & uniqueness

* **Uniqueness:** exactly **one** hurdle record per `merchant_id` within `{seed, parameter_hash, run_id}`.
* **Coverage:** hurdle row count equals the ingress merchant count for the run.

---

**Bottom line:** This validator spec proves each hurdle event is schema-conformant, numerically correct, budget-conserving, partition-coherent, and correctly gates downstream streams—using **base-counter reconstruction**, **open-interval** replay, **cumulative per-substream trace totals** (grouped by (`module`, `substream_label`)), and registry-driven discovery.

---

## V8. Partition equality & path authority

For **every** hurdle row:

* **Path ↔ embed equality:** Embedded envelope keys
  `{seed, parameter_hash, run_id}` **must equal** the same keys in the dataset path.
  *(The hurdle dataset partitions by `{seed, parameter_hash, run_id}` only.)*
* **Literal checks (envelope):** `substream_label == "hurdle_bernoulli"` (registry literal) and `module` equals the registered producer id (e.g., `"1A.hurdle_sampler"`).
* **No fingerprint in path:** `manifest_fingerprint` is **embedded only** (lineage), never a path partition.

Mismatch is a lineage/partition failure.

---

## V9. Optional diagnostics (non-authoritative)

If the diagnostic table `…/hurdle_pi_probs/parameter_hash={parameter_hash}` exists, **do not** use it to verify decisions. At most, compare its `(eta, pi)` to recomputed values for sanity. Decisions are proven **only** by replaying S1.2 + S1.3.

---

## V10. Failure objects (forensics payload; exact keys)

Emit **one JSON object per failure** with envelope lineage and a precise code:

```json
{
  "state": "S1",
  "dataset_id": "rng_event_hurdle_bernoulli",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "failure_code": "rng_counter_mismatch",
  "merchant_id": 184467440737095,
  "detail": {
    "rng_counter_before": {"hi": 42, "lo": 9876543210},
    "rng_counter_after":  {"hi": 42, "lo": 9876543211},
    "blocks": 1,
    "draws": "1",
    "expected_delta": "1",
    "trace_totals_draws": "0",
    "pi": 0.37,
    "u": 0.55
  },
  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "run_id": "0123456789abcdef0123456789abcdef",
  "ts_utc": "2025-08-15T10:12:03.123456Z"
}
```

* `dataset_id` is the **registry id** (not a path).
* Identifiers typed as id64/uint64 in the schema (e.g., `seed`, `merchant_id`) are JSON integers.
* `failure_code` maps **1:1** to S1.6 predicates.

---

## V11. End-of-run verdict & artifact

* If **any** check fails ⇒ **RUN INVALID**. Emit a `_FAILED.json` sentinel with aggregated stats and the list of failure objects; CI blocks the merge.
* If all checks pass ⇒ **RUN VALID**. Optionally record summary metrics (row counts, draw histograms, min/max/mean `pi`, `u` bounds). *(Downstream layers may re-check gating; S1.V is the first hard gate.)*

---

## CI integration (blocking gate)

### CI-1. Job matrix

* All **changed parameter bundles** (distinct `parameter_hash`) and a **seed matrix** (e.g., 3 fixed seeds per PR).
* At least one **prior manifest fingerprint** (regression guard vs last known good).

### CI-2. Steps

1. **Schema:** validate hurdle + trace rows against schema anchors; fail fast.
2. **Partition:** path ↔ embedded equality on `{seed, parameter_hash, run_id}`; then check envelope literals (`module`, `substream_label`); ensure **no fingerprint in path**.
3. **Replay:** ... reconcile cumulative per-substream trace totals **and**
   check `u128(trace.after) − u128(trace.before) == trace.blocks_total` on the final trace row per (`module`, `substream_label`).
4. **Gating:** enforce **presence-based** rule: gated streams exist **iff** `is_multi=true`.
5. **Cardinality/uniqueness:** exactly one hurdle row per merchant; counts match ingress.

### CI-3. What blocks the merge

Any: schema violation, partition mismatch, counter/trace mismatch, non-finite numeric, deterministic-branch inconsistency, **gating presence failure**, or cardinality/uniqueness failure. (Codes per S1.6.)

### CI-4. Provenance in the validation bundle

Record a compact summary in the fingerprint-scoped validation payload: counts, pass/fail, and optional lint artifacts (`SCHEMA_LINT.txt`, `DICTIONARY_LINT.txt`) for human inspection. *(Bundles are fingerprint-scoped; logs remain log-scoped.)*

---

## Reference validator outline (language-agnostic)

```text
INPUT:
  paths from registry; encoders; beta; run keys (seed, parameter_hash, run_id)

LOAD:
  H := read_jsonl(hurdle partition)
  T := read_jsonl(trace partition)
  S := discover_gated_streams_via_registry()

# 1) schema
assert_all_schema(H, "#/rng/events/hurdle_bernoulli")
assert_all_schema(T, "#/rng/core/rng_trace_log")

# 2) partition equality
for e in H: assert path_keys(e) == embedded_keys(e)   # {seed, parameter_hash, run_id}
assert all(e.module == "1A.hurdle_sampler" && e.substream_label == "hurdle_bernoulli" for e in H)

# 3) recompute (η, π) and budget
beta := load_beta_once()
for e in H:
  x_m := rebuild_design(m)                 # frozen encoders; one-hot sums; column order
  eta, pi := fixed_order_dot_and_safe_logistic(x_m, beta)
  draws := 1 if 0 < pi < 1 else 0

  # 4) base counter + counters & trace
  before := reconstruct_base_counter(seed, manifest_fingerprint, "hurdle_bernoulli", m)
  assert e.rng_counter_before == before
  delta := u128(e.after) - u128(e.before)
  assert delta == parse_u128(e.draws) == draws
  if "blocks" in e: assert e.blocks == parse_u128(e.draws)

  # 5) branch checks
  if draws == 0:
     assert (pi == 0.0 && !e.is_multi) || (pi == 1.0 && e.is_multi)
     assert e.deterministic && e.u == null
  else:
     u := regenerate_u01(seed, before)     # (0,1), low-lane policy
     assert 0.0 < u && u < 1.0
     assert (u < pi) == e.is_multi

# 6) trace reconciliation (final per (module, substream_label))
for each key in final_rows(T):
  assert key.draws_total == sum(parse_u128(e.draws) for e in H  # diagnostic where e.module==key.module && e.substream_label==key.substream_label)   # saturating uint64
  if "blocks" in H: assert key.blocks_total == sum(e.blocks for e in H where same key)                                                # saturating uint64
  assert u128(key.after) - u128(key.before) == key.blocks_total   # and, for hurdle, also equals key.draws_total 

# 7) gating (presence-based)
H1 := { m | H[m].is_multi == true }
for each row in each gated stream s ∈ S:
  assert row.merchant_id in H1
for each m ∉ H1:
  assert no rows exist in any s ∈ S

# 8) uniqueness & cardinality
assert |H| == |ingress_merchant_ids|
assert unique(H.merchant_id)
```

---

**Bottom line:** This chunk locks the **partition/lineage checks**, the **forensics error object**, and the **CI gate** to the exact S1 contracts: complete envelope, base-counter reconstruction, budget identity + cumulative trace, presence-based gating via the registry, and strict uniqueness/cardinality—so any drift trips a named, actionable failure.

---