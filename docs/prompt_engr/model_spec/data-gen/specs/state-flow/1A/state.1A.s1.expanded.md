# S1.1 — Inputs, Preconditions, and Write Targets (normative)

## Purpose (what S1 does and does **not** do)

S1 evaluates a **logistic hurdle** per merchant and emits a **Bernoulli outcome** (“single vs multi”). Here we pin **inputs**, **context/lineage**, and **write targets** required to do that deterministically. The logistic, RNG use, and payload specifics are defined in **S1.2–S1.4**.
S1 does **not** specify downstream sampling (NB, ZTP, Dirichlet, etc.) nor CI/monitoring; those live in their respective state specs and the validation harness.

---

## Inputs (available at S1 entry)

### 1) Design vector $x_m$ (column-frozen from S0.5)

**Feature vector (logistic):**

* **Block order (fixed):** $[\,\text{intercept}\,] \,\Vert\, \text{onehot(MCC)} \,\Vert\, \text{onehot(channel)} \,\Vert\, \text{onehot(GDP\_bucket)}$.
* **Channel encoder (dim=2):** labels and order are exactly $[\,\mathrm{CP},\,\mathrm{CNP}\,]$ as defined in S0.
* **GDP bucket encoder (dim=5):** labels and order are exactly $[\,1,2,3,4,5\,]$ from S0’s Jenks-5 bundle.
* **MCC encoder (dim $=C_{\text{mcc}}$):** column order is **the frozen order from S0.5** (the fitting bundle); S1 **does not** derive order from map/dictionary iteration.
* **Shape invariant:** $|x_m| \;=\; 1 + C_{\text{mcc}} + 2 + 5$.

S1 **receives** $x_m$ (already constructed by S0.5) as:

$$
x_m=\big[\,1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel}_m),\ \phi_{\text{dev}}(b_m)\,\big]^\top,
$$

with $b_m\in\{1,\dots,5\}$. These are the **only** hurdle features. (NB dispersion’s $\log g_c$ is **not** used here.)

> **Note:** S0 enforces domain validity for MCC, channel, and GDP buckets and guarantees that each one-hot block sums to 1. S1 relies on that; it does **not** re-validate domain membership.

### 2) Coefficient vector $\beta$ (single YAML, atomic load)

Load $\beta$ **atomically** from the hurdle coefficients bundle. The vector already contains **all coefficients** in the exact order aligned to $x_m$: intercept, MCC block, channel block, and the **five** GDP-bucket dummies. Enforce the shape invariant

$$
|\beta| \;=\; 1 + C_{\text{mcc}} + 2 + 5 \quad (\text{else: abort as design/coeff mismatch}).
$$

(Design rule context from S0.5: hurdle uses bucket dummies; NB mean excludes them; NB dispersion uses $\log g_c$.)

### 3) Lineage & RNG context (fixed before any draw)

S0 has already established the **run identifiers** and RNG environment S1 uses:

* `parameter_hash` (hex64) — partitions parameter-scoped artefacts.
* `manifest_fingerprint` (hex64) — embedded for lineage; not a path partition here.
* `seed` (u64) — run master seed (used by S0’s keyed-substream primitive).
* `run_id` (hex32) — logs-only partition key.
* An `rng_audit_log` exists for this `{seed, parameter_hash, run_id}` (S0). S1 must **not** emit the first hurdle event if the audit row is absent.

**PRNG use model (order-invariant):** Every RNG event in 1A uses **label-keyed substreams**. The **base counter** for a given `(module, substream_label, merchant_id)` is derived **only** by S0’s keyed-substream mapping; it does **not** depend on execution order or on other labels’ counters. There is **no** cross-label counter chaining in S1.

---

## Envelope contract (shared fields carried by every hurdle event)

Each hurdle event **must** include the layer envelope fields:

* `ts_utc` — RFC-3339 UTC **per S0’s timestamp policy** (S1 adds no precision rule).
* `module` — registry literal for this stream (enumeration; see registry).
* `substream_label` — registry literal `"hurdle_bernoulli"`.
* `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`.
* `rng_counter_before_hi`, `rng_counter_before_lo`, `rng_counter_after_hi`, `rng_counter_after_lo` (128-bit counter words; names define `(hi,lo)` pairing).
* `blocks` (non-negative int; unit = **one 64-bit uniform**).
* `draws` (non-negative **u128** encoded as a decimal string).

**Envelope law (budget identity):**

$$
(\text{after}_{hi},\text{after}_{lo}) - (\text{before}_{hi},\text{before}_{lo}) \;=\; \text{parse\_u128(draws)} \;=\; \text{blocks}.
$$

For the hurdle stream specifically, `blocks ∈ {0,1}` and `draws ∈ {"0","1"}`.

> **Key-order note:** JSON object **key order is non-semantic**. The `_hi/_lo` suffixes define the high/low words; parsers must bind by name.

---

## Preconditions (hard invariants at S1 entry)

1. **Shape & alignment:** $|\beta|=\dim(x_m)$ and the block orders match S0.5’s fitting bundle; else abort as design/coeff mismatch.
2. **Numeric environment:** S0’s numeric policy is in force (IEEE-754 binary64, RN-even, no FMA/FTZ/DAZ). S1 will use the overflow-safe two-branch logistic with a fixed saturation threshold (see S1.2).
3. **RNG audit present:** the audit record for `{seed, parameter_hash, run_id}` exists before the first hurdle emission; else abort.

---

## Event stream target (authoritative id, partitions, schema)

S1 emits **exactly one** hurdle record per merchant into the hurdle RNG dataset:

* **Dataset id:** registry entry for the hurdle RNG stream.
* **Partitions (path):** `{seed, parameter_hash, run_id, module, substream_label}` (no `manifest_fingerprint` in the path).
* **Schema:** layer schema anchor for `rng/events/hurdle_bernoulli` (payload + envelope).

**Uniqueness & completeness (per run):** Within `{seed, parameter_hash, run_id}`, there is **at most one** hurdle event per `merchant_id`, and the count of hurdle events equals the merchant universe count for that `{parameter_hash}` from S0.

**Trace (cumulative, not per-event):** For each `(module, substream_label="hurdle_bernoulli", merchant_id)` within the run, S1 maintains a **cumulative** `rng_trace_log` record whose totals (`blocks_total`, `draws_total`) equal the **sum of event budgets** for that key. The **event** is authoritative for the decision and budget; the trace totals exist for reconciliation.

---

## Forward contracts S1 must satisfy (declared here so inputs are complete)

* **Probability (S1.2):** compute $\eta_m=\beta^\top x_m$ and $\pi_m=\sigma(\eta_m)$ using the overflow-safe **two-branch logistic** with a **fixed binary64 threshold** $T$ such that $\pi_m\in\{0.0,1.0\}$ iff $|\eta_m|\ge T$; otherwise $0<\pi_m<1$.
* **RNG substream & $u\in(0,1)$ (S1.3):** use the keyed substream for `substream_label="hurdle_bernoulli"`; consume **one** open-interval uniform **iff** $0<\pi_m<1$; otherwise consume zero. Envelope counters and budgets must satisfy the law above.
* **Payload discipline (S1.4):** payload contains the minimal fields needed to decide/audit the hurdle, with types:
  `is_multi` **boolean**; `u` **required** and **nullable** (`null` iff deterministic); other fields as per the hurdle event schema anchor.

---

## Failure semantics (at the S1.1 boundary)

Abort the run if any precondition fails (shape/alignment mismatch; missing audit; envelope/schema violation; path partition mismatch). CI/monitoring policies and detailed failure catalogs live outside S1.

---

## Why this matters (determinism & replay)

By fixing $x_m$, $\beta$, the run identifiers, the **order-invariant substreaming model**, and the envelope/budget law **before** any draw, S1’s Bernoulli outcomes and counters are **bit-replayable** under any sharding or scheduling. This gives the validator a single, unambiguous contract to reproduce S1 decisions.

---

**Bottom line:** S1 starts only when $x_m$, $\beta$, and the lineage/RNG context are immutable and schema-backed; it writes to the single authoritative hurdle stream with a fixed envelope and partitioning. With these inputs and preconditions, S1.2–S1.4 compute $\eta,\pi$, consume at most one uniform (as required), and emit an event that validators can reproduce exactly.

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

Compute in IEEE-754 **binary64** using the **frozen column order** and the **Neumaier compensated summation** mandated by S0.8. No BLAS reordering or parallel reduction is permitted on any ordering-critical path.&#x20;

### Logistic map and **explicit saturation regime** (normative)

Baseline logistic:

$$
\sigma:\mathbb{R}\to(0,1),\qquad
\sigma(\eta)=\frac{1}{1+e^{-\eta}}.
$$

**Evaluation contract (binary64, deterministic):**

We define a **piecewise, overflow-safe evaluation** that is portable across libm profiles (no reliance on incidental under/overflow):

* Fix a **binary64 saturation threshold** $T = 37.5$.
* Compute $\pi=\sigma(\eta)$ as:

$$
\pi\;=\;
\begin{cases}
1.0 & \text{if } \eta \ge +T,\\[4pt]
\dfrac{1}{1+e^{-\eta}} & \text{if } 0 \le \eta < +T,\\[10pt]
\dfrac{e^{\eta}}{1+e^{\eta}} & \text{if } -T < \eta < 0,\\[10pt]
0.0 & \text{if } \eta \le -T.
\end{cases}
$$

This guarantees $\pi\in[0,1]$ in **binary64**, and it makes the **deterministic regime** explicit and platform-independent (exact `0.0` or `1.0` only via this saturation). S0.8 governs the math profile for `exp` and the FP environment used in the middle branches.&#x20;

**Determinism flag (derived):**
`deterministic := (pi == 0.0 || pi == 1.0)` using **binary64 equality**. If `deterministic=true` then S1.3 will consume **zero** uniforms; else S1.3 consumes **exactly one**. (See S1.3; validator equalities come from our Batch-1/2 decisions.)

---

## Serialization & bounds (normative I/O rules)

* **Binary64 round-trip:** Producers MUST serialize $\pi$ as a decimal that **round-trips bit-exactly** to the original binary64 (e.g., shortest round-trippable or fixed 17 digits). Consumers MUST parse as binary64 and MUST NOT depend on a fixed digit count.&#x20;
* **Legal range:** Enforce `0.0 ≤ pi ≤ 1.0` (binary64). If $|\eta|\ge T$, emitted $\pi$ is exactly `0.0` or `1.0`; otherwise `0.0 < pi < 1.0`.&#x20;
* **Diagnostics:** $\eta$ is **not** part of the normative hurdle event payload; if recorded, it belongs to a **diagnostic** dataset only (non-authoritative).&#x20;

---

## Deterministic vs stochastic and consequences for S1.3

* **Stochastic case** $(0<\pi<1)$: S1.3 will draw **one** $u\in(0,1)$ from the keyed substream, then decide `is_multi = (u < pi)`; budget `draws=1`. (Open-interval mapping and substreaming per S0.3.)&#x20;
* **Deterministic case** $(\pi\in\{0,1\})$: S1.3 performs **no draw**; budget `draws=0`; downstream decision is implied by $\pi$ (`is_multi=true` iff $\pi==1.0$).&#x20;

---

## Numeric policy (must hold; inherited)

S0.8 applies in full: **binary64**, RN-even, **no FMA**, **no FTZ/DAZ**, deterministic libm; fixed-order Neumaier reductions; any NaN/Inf in $\eta$ or $\pi$ is a **hard error** under S0.9.

---

**Bottom line:** S1.2 fixes a single, portable way to compute $\eta$ and $\pi$: a **fixed-order Neumaier** dot product followed by a **two-branch logistic** with **explicit saturation at $T=37.5$**. This yields exact `0.0/1.0` only by spec (not by accidental under/overflow), and it cleanly determines whether S1.3 consumes **one** uniform or **zero**.&#x20;

---

## Output of S1.2 (to S1.3/S1.4)

For each merchant $m$, S1.2 produces the numeric pair

$$
(\eta_m,\ \pi_m),\qquad \eta_m\in\mathbb{R}\ \text{(finite)},\ \ \pi_m\in[0,1]\ \text{(binary64)}.
$$

These values are **not persisted by S1.2**. They flow directly into:

* **S1.3 (RNG & decision):** determines whether **one** uniform is consumed $(0<\pi<1)$ or **zero** $(\pi\in\{0,1\})$, and if stochastic, evaluates the predicate `is_multi = (u < pi)`.
* **S1.4 (event payload):** `pi` is a required payload field. `eta` is **not** a normative payload field; if recorded, it belongs to a diagnostic dataset (non-authoritative). S1.4 derives `deterministic` from `pi` and applies the `u` presence rule: `u=null` iff `pi∈{0,1}`, else `u∈(0,1)`.

---

## Failure semantics (abort S1 / run)

S1.2 must **abort the run** if any of the following hold:

1. **Numeric invalid:** either $\eta$ or $\pi$ is non-finite (NaN/±Inf) after evaluation.
2. **Out-of-range:** $\pi \notin [0,1]$ (should not occur under the thresholded two-branch logistic).
3. **Shape/order mismatch:** already handled at S1.1; if encountered here, treat as a hard precondition failure.

(Full failure taxonomy, codes, and CI handling live outside S1; this section defines only the operational abort triggers.)

---

## Validator hooks (what the S1 checklist asserts for S1.2)

The single S1 Validator Checklist (referenced once from S1) must be able to **reproduce** S1.2 exactly:

* **Recompute:** Rebuild $x_m$ (from S0’s frozen encoders) and re-evaluate $\eta,\pi$ using the fixed-order binary64 dot product and the **thresholded two-branch logistic** with the pinned saturation threshold $T$. Assert:

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
2. **Logistic with explicit saturation:** Using the fixed threshold $T$, set:

   * if $\eta \ge +T$ ⇒ $\pi = 1.0$;
   * else if $-T \le \eta < +T$ ⇒ evaluate the two-branch logistic in binary64;
   * else if $\eta \le -T$ ⇒ $\pi = 0.0$.
3. **Guards:** $\eta$ and $\pi$ must be finite; $\pi$ must satisfy $0.0 \le \pi \le 1.0$.
4. **Hand-off:** Emit $(\eta,\pi)$ to S1.3/S1.4. The RNG budget and `u` presence follow directly from $\pi$ as stated above.

*(This is a procedural specification, not implementation code; S0 remains the authority for the FP environment and PRNG primitives.)*

---

## How S1.2 interacts with adjacent sections

* **Feeds S1.3:** $\pi$ sets the **uniform budget**: exactly **one** uniform if $0<\pi<1$, else **zero**. If stochastic, S1.3 evaluates `is_multi = (u < pi)` using the open-interval mapping from S0.
* **Feeds S1.4:** `pi` is serialized with **binary64 round-trip** fidelity. `deterministic` is derived from `pi`; `u` is **required** and **nullable** (`null` iff $\pi\in\{0,1\}$, otherwise a number in $(0,1)$). `is_multi` is **boolean** only.

---

**Bottom line:** S1.2 defines a single, portable procedure for $(\eta,\pi)$: **fixed-order** binary64 dot product and a **thresholded two-branch logistic** with explicit saturation. That yields $\pi\in[0,1]$ deterministically, makes the deterministic regime platform-independent, and drives the exact RNG budget and payload semantics required by S1.3–S1.4.

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

* $\pi_m\in[0,1]$ from S1.2.
* Run lineage identifiers: `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, and `module` (registry literal for this producer).
* `merchant_id` (serialized as decimal string in events; treated as u64 by the S0 keying primitive).
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
\;=\; \text{parse_u128(draws)} \;=\; \texttt{blocks},
$$

with unsigned 128-bit arithmetic on counters. In the hurdle stream, `blocks ∈ {0,1}` and `draws ∈ {"0","1"}`. (Unit of account = **one 64-bit uniform**.)

> **Trace model (clarification):** The RNG trace is **cumulative** per `(module, substream_label, merchant)` within the run; its totals reconcile to the **sum of event budgets** and the counter deltas—S1.3 does **not** emit per-event trace rows.

---

## Uniform $u\in(0,1)$ & lane policy

* **Engine:** Philox 2×64-10 (fixed in S0). Each block yields two 64-bit words; **single-uniform** events use the **low lane** (`x0`) and **discard** the high lane (`x1`). One counter increment ⇒ one uniform.
* **Mapping to $U(0,1)$:** Use S0’s **open-interval** `u01` mapping from a 64-bit unsigned word to binary64. Exact 0 and exact 1 are **never** produced. (S1.3 references this mapping; it does not redefine it.)

---

## Draw budget & decision

Let $\pi=\pi_m$.

* **Deterministic branch** ($\pi\in\{0,1\}$).
  `draws="0"`, `blocks=0`; **no** Philox call; envelope has `after == before`.
  Outcome is implied by $\pi$: `is_multi = true` iff $\pi == 1.0$; else `false`.
  Payload rules (S1.4): `deterministic=true`, `u=null`.

* **Stochastic branch** ($0<\pi<1$).
  Draw **one** uniform $u\in(0,1)$ using the keyed substream and lane policy; `draws="1"`, `blocks=1`; envelope has `after = before + 1`.
  Decide `is_multi = (u < pi)`; payload: `deterministic=false`, `u` present and numeric.

All of the above are enforced by the S0/S1 budgeting invariants and the S1 validator checklist (determinism equivalences and gating).

---

**Bottom line:** S1.3 consumes **zero or one** uniform from the merchant-keyed `"hurdle_bernoulli"` substream, applies the **open-interval** mapping, decides with `u < pi`, and records a budget-correct envelope. No cross-label chaining, no alternative keying, no per-event trace rows—everything is S0-aligned and replayable.

---

## Envelope & streams touched here (recap; S1.4 formalises payload)

Each hurdle event **must** carry the **complete** layer RNG envelope:

`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label="hurdle_bernoulli", rng_counter_before_hi, rng_counter_before_lo, rng_counter_after_hi, rng_counter_after_lo, blocks, draws }`

* `module` and `substream_label` are **registry literals** (closed enums).
* `blocks` is a non-negative integer; **unit = one 64-bit uniform**.
* `draws` is a non-negative **u128 encoded as decimal string**; `parse_u128(draws)` **must equal** `blocks`.
* **Budget identity (must hold):** `u128(after) − u128(before) = parse_u128(draws) = blocks`.

S1.3 writes **one** hurdle event per merchant. The RNG trace is a **cumulative** dataset keyed by `(module, substream_label, merchant_id)` within the run; its totals equal the **sum of event budgets**. S1.3 does **not** emit per-event trace rows.

---

## Failure semantics (abort class bindings)

Abort the run on any of the following:

* **Envelope/label violation.** Missing required envelope fields; wrong `module`/`substream_label` literal; malformed counter fields (`*_hi/*_lo`).
* **Budget identity failure.** `after − before` (u128) ≠ `blocks` ≠ `parse_u128(draws)`; or `blocks∉{0,1}` / `draws∉{"0","1"}` for hurdle.
* **Uniform out of range.** In a stochastic branch, `u ≤ 0` or `u ≥ 1` (violates open-interval `u01`).
* **Determinism inconsistency.** `π∈{0,1}` but `u` present or `deterministic=false`; or `0<π<1` but `u` absent or `deterministic=true`.

(Shape/order and non-finite numeric faults are owned by S1.1–S1.2 preconditions.)

---

## Validator hooks (must pass)

For each hurdle record in the run, the validator performs:

1. **Rebuild base counter (order-invariant).** Using the S0 keyed-substream primitive with `(seed, manifest_fingerprint, substream_label="hurdle_bernoulli", merchant_id)`, recompute the **base counter** and assert envelope `before` equals it. (No cross-label chaining is permitted.)

2. **Branch-specific checks from $\pi$ (from S1.2):**

   * If `draws="0"`/`blocks=0`: assert $\pi\in\{0.0,1.0\}$, `u==null`, `deterministic=true`, and `after==before`.
   * If `draws="1"`/`blocks=1`: generate **one** 64-bit word from the keyed substream at `before` using S0’s lane policy (low lane), map via S0’s **open-interval** `u01`, assert `0<u<1`, assert `(u<pi) == is_multi`, and assert `after = before + 1`.

3. **Trace reconciliation (cumulative).** Aggregate `blocks` over all hurdle events for the same `(module, substream_label, merchant_id)`; assert the **trace totals** equal that sum and equal the counter delta between the earliest `before` and latest `after` for that key.

4. **Partition/embedding equality.** Path partitions `{seed, parameter_hash, run_id}` match the embedded envelope fields; `module` / `substream_label` match the registry literals exactly.

---

## Procedure (ordering-invariant, language-agnostic)

1. **Obtain base counter** for `(label="hurdle_bernoulli", merchant_id)` via the S0 keyed-substream primitive; set `before` accordingly.
2. **Branch on $\pi$:**

   * If $\pi\in\{0,1\}$: set `draws="0"`, `blocks=0`, `after=before`, `u=null`, `is_multi=(pi==1.0)`.
   * If $0<\pi<1$: fetch **one** uniform $u\in(0,1)$ using the S0 lane policy and `u01`; set `draws="1"`, `blocks=1`, `after=before+1`, `is_multi=(u<pi)`.
3. **Emit hurdle event** (S1.4): envelope includes all required fields above; payload includes `merchant_id`, `pi`, `u` (nullable), `is_multi` (boolean), `deterministic` (derived from `pi`).
4. **Update cumulative RNG trace totals** for this `(module, substream_label, merchant_id)` by `+blocks`.

*(This is a procedural spec; S0 remains the authority for PRNG keying, counter arithmetic, lane policy, and `u01` mapping.)*

---

## Invariants (S1/H) guaranteed here

* **Bit-replay:** Fixing $(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, both the envelope counters and the pair $(u,\text{is_multi})$ are **bit-identical** under replay.
* **Consumption:** `draws="1"` (and `blocks=1`) **iff** $0<\pi<1$; else `"0"`/`0`.
* **Schema conformance:** `u` and `deterministic` comply with the hurdle event schema: `u=null` iff $\pi\in\{0,1\}$; `is_multi` is **boolean** only.
* **Order-invariance:** `before` equals the keyed **base counter** for `(label, merchant)`—never a prior label’s `after`.
* **Gating (forward contract):** Downstream 1A RNG streams appear **iff** `is_multi=true` (stream set obtained via the registry filter; S1 does not enumerate it).

---

**Bottom line:** S1.3 produces a single-uniform Bernoulli decision on a **merchant-keyed**, **label-stable** substream, with a **complete** envelope and a **cumulative** trace model. Everything is S0-compatible, order-invariant, and validator-checkable without guesswork.

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
* `pi` (Bernoulli parameter on $[0,1]$, **JSON number**, binary64 round-trip),
* `is_multi` (Bernoulli outcome),
* `deterministic` (boolean; **true** iff $\\pi\\in\\{0,1\\}$),
* `u` **conditional** on the branch: present and in $(0,1)$ **only** when `deterministic=false`; **null** when `deterministic=true`.

> The dictionary binds this stream to `#/rng/events/hurdle_bernoulli`; the layer schema defines `u` via `$defs.u01` (exclusive bounds).
 
**Outcome semantics (canonical).**
- If `0<pi<1`: `is_multi := 1{ u < pi }`.
- If `pi ∈ {0.0,1.0}`: `is_multi := 1{ pi == 1.0 }` (i.e., `is_multi = pi`).
Types: `is_multi ∈ {0,1}`.
Branch invariants:
`deterministic==true ⇒ u==null ∧ is_multi==pi`;
`deterministic==false ⇒ 0<u<1 ∧ (u<pi) == (is_multi==1)`.

**Deterministic vs stochastic cases (branch-clean):**

* If $0<\pi_m<1$: draw $u_m\sim\mathrm{U}(0,1)$ (**open interval**), **emit** `u` as a JSON number (binary64 round-trip) and require **strict bounds** `0 < u < 1`; set `deterministic=false` and `is_multi=\mathbf{1}\{u_m<\pi_m\}`; **consume 1 uniform**.
* If $\pi_m=0$: set `deterministic=true`, `u=null`, `is_multi=0`; **consume 0 uniforms**.
* If $\pi_m=1$: set `deterministic=true`, `u=null`, `is_multi=1`; **consume 0 uniforms**.

**Schema & branch contract (authoritative).** The field `u` is **required** with type `number|null`.
- If `deterministic=true` (i.e., `pi ∈ {0.0,1.0}` in binary64): **emit** `u:null`.
- If `deterministic=false` (i.e., `0<pi<1`): **emit** `u` as a JSON number that **round-trips to binary64** and **must** satisfy `0<u<1`.
Any deviation is a schema/validator failure.
 

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
  "u": 0.1049,                        // always present; null when deterministic
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

    deterministic = (draws == 0)

    if draws == 1:
        u = next_u01()                         # consumes one block; open interval (0,1)
        is_multi = (u < pi_m)
        after_hi, after_lo = advance((before_hi, before_lo), 1)
    else:
        u = None
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
        "deterministic": deterministic,
        "u": u,   
        "is_multi": is_multi
    }
    write_jsonl("logs/rng/events/hurdle_bernoulli/"
                f"seed={ctx.seed}/parameter_hash={ctx.parameter_hash}/run_id={ctx.run_id}/part-*.jsonl",
                record)
    # trace row with draws for the same substream
    emit_trace_row(label="hurdle_bernoulli", draws=draws, before=(before_hi,before_lo), after=(after_hi,after_lo))
```


**Normative contract (authoritative).** Hurdle payload keys are `{merchant_id, pi, is_multi, deterministic, u}`. `u` is **required** with type `number|null`: emit `u:null` when `deterministic=true` (`pi ∈ {0.0,1.0}` in binary64) and emit a JSON number that round-trips to binary64 with **strict bounds** `0<u<1` when `deterministic=false` (`0<pi<1`). Any deviation is a schema/validator failure; this state text and `schemas.layer1.yaml` anchors are the sole authority.


Pseudocode aligns to: dictionary path & partitioning; shared envelope; hurdle payload; counter arithmetic; and trace linkage.

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

* If $0<\pi_m<1$: `draws=1`; `after = before + 1` (u128; implied by **Counter conservation (envelope law)**).
* If $\pi_m\in\{0,1\}$: `draws=0`; `after = before` (implied by **Counter conservation (envelope law)**).

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
**Predicate.** Record fails `#/rng/events/hurdle_bernoulli` required payload keys: `merchant_id`, `pi`, `is_multi`, `deterministic`, `u`, or types/ranges violate `$defs` (`pct01`, `u01`).
**Detect at.** Writer schema validation; CI validator. **Abort run.**

**D2. `deterministic_branch_inconsistent`**
**Contract (authoritative).** If $0<\pi<1$: payload must have `u∈(0,1)` and `deterministic=false`. If $\pi\in\{0,1\}$: payload must have `u=null` and `deterministic=true`.  
**Predicate.** Event violates the contract above.  
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

1. Rebuild the frozen design vector $x_m$ using **Feature vector construction (logistic)** above; check one-hot sums and column order.
2. Load $\beta$ atomically; assert $|\beta| = 1 + C_{mcc} + 2 + 5$ and **exact** column order equality with the encoders.
3. Compute $\eta_m=\beta^\top x_m$ in binary64 (fixed order); compute $\pi_m$ via the **two-branch** logistic. Assert finiteness and `0.0 ≤ pi ≤ 1.0`.

**Fail fast:** any non-finite $\eta,\pi$ or shape/order mismatch is a **hard abort** (S1 failure class).

---

## V5. RNG replay & counter accounting (per row)

Let the hurdle label be `substream_label = "hurdle_bernoulli"` (must match exactly).

For each hurdle record:

1. **Budget from $\pi$:** set `draws_expected = 1` iff $0<\pi<1$; else `0`. See **Counter conservation (envelope law)** for the equality chain that must hold across counters, envelope `blocks/draws`, and trace.
2. **Counter conservation:** compute `delta = u128(after) − u128(before)` and assert `delta == blocks`.
3. **Lane policy check (S1):** assert `u128(after) − u128(before) ∈ {0,1}`; any delta > 1 is a lane policy violation.
4. **Trace and envelope reconciliation:** find the companion `rng_trace_log` row (join on `{seed, parameter_hash, run_id, substream_label, merchant_id}`) and assert:
   - `trace_draws == draws_expected`,
   - `u128(after) − u128(before) == draws_expected`,
   - `blocks == draws_expected`, and
   - `parse_u128(draws) == draws_expected`.
5. **Deterministic vs stochastic branch:** (unchanged)
   * If `draws_expected = 0`: assert the payload follows the deterministic contract — `pi ∈ {0.0,1.0}`, `u:null`, and `is_multi == pi`.
   * If `draws_expected = 1`: regenerate the uniform $u$ (open interval) and assert `0<u<1` and `(u<π) == (is_multi == 1)`.

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