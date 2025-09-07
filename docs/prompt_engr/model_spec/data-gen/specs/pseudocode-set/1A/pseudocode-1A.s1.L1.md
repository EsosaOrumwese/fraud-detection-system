# L1 — State-1 Runtime Kernels (Merchant → Hurdle Decision)

## Purpose

L1 defines the state-specific kernels for S1: inputs/outputs, exact algorithms, and literals are fixed here. **Paths are dictionary-resolved via L0 (no path strings/templates in L1)**; primitives and general helpers live in L0, and host wiring lives in L2.

## Scope (what’s in / out)

* **In:** S1.1–S1.5 runtime kernels and their helper routines (no RNG in S1.1–S1.2; at-most-one uniform in S1.3; authoritative event emission and cumulative trace in S1.4; in-memory handoff in S1.5).
* **Out:** Failure taxonomy prose, CI wiring, and global validators—those live in **L3 (S1.V)**. We still enforce their **triggering predicates** inline where relevant.

## Run prerequisites (from S0; must already hold)

* Lineage keys are resolved: `seed:u64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`, `run_id:hex32`.
* Numeric policy attested: IEEE-754 **binary64**, **RNE**, **no FMA**, **no FTZ/DAZ**, fixed-order reductions.
* RNG bootstrap: **rng_audit_log** exists for `{seed, parameter_hash, run_id}`.
* Hurdle design vector $x_m$ is available (built by S0.5; column order frozen).

## Event family and schema anchors

* **Event dataset id:** `rng_event_hurdle_bernoulli`
* **Module literal:** `"1A.hurdle_sampler"`
* **Substream label literal:** `"hurdle_bernoulli"`
* **Event schema ref:** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`
*Source of truth:* these literals and anchors are **registry/dictionary-backed**; L1 does not re-enumerate allowed values beyond referencing them here.

## Trace (cumulative) schema (used in S1.4)

* **Trace dataset id:** `rng_trace_log`
* **Semantics:** one **cumulative** row per emission call, keyed by `(seed, parameter_hash, run_id)` and `(module, substream_label)`.
* **Final-row selection:** consumers select the **final** row per `(module, substream_label)` as defined by `schemas.layer1.yaml#/rng/core/rng_trace_log`.
* **Totals (saturating u64):** `draws_total`, `blocks_total`, `events_total`.
* **Counters:** `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}`.
* **Timestamp:** RFC-3339 UTC with **exactly 6 fractional digits** (microseconds).

## Budget & RNG invariants (hurdle stream)

* **Base counter** derived from `master = derive_master_material(seed, manifest_fingerprint_bytes)`; then
  compute `merchant_u64 = merchant_u64_from_id64(merchant_id)`, set
  `ids = [ { tag:"merchant_u64", value: merchant_u64 } ]` (SER **typed 1-tuple**), and call
  `base = derive_substream(master, label="hurdle_bernoulli", ids)`.
* **Deterministic case:** if `pi ∈ {0.0,1.0}` → **zero** uniforms; `before==after`; `draws="0"`, `blocks=0`.
* **Stochastic case:** if `0<pi<1` → consume **exactly one** uniform with **low lane**; `u∈(0,1)`; `draws="1"`, `blocks=1`.
* **Authoritative identity:** `u128(after) − u128(before) == decimal_string_to_u128(draws)`; and **for hurdle**: `blocks == u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`.
* **No counter chaining** across labels or states.

## L0 dependencies (to be called by L1 kernels)

* **Substreams/RNG:** `derive_master_material`, `derive_substream`, `merchant_u64_from_id64`, `uniform1` (low lane).
* **Envelope/trace:** `begin_event_micro`, `end_event_emit`, `update_rng_trace_totals`, `decimal_string_to_u128`, `u128_to_decimal_string`.
* **Numeric:** `dot_neumaier`, `logistic_branch_stable` *(two-branch, overflow-safe logistic; alias used only in prose)*, `u128_to_uint64_or_abort`, `u128_delta`.
* **Formatting:** `f64_to_json_shortest`, `ts_utc_now_rfc3339_micro`.
* **Predicates:** `is_binary64_extreme01`, `is_open_interval_01`.

## Types & common literals

```pseudocode
type Hex64 = string   # [0-9a-f]{64}
type Hex32 = string   # [0-9a-f]{32}

type Context = {
  seed:u64,
  parameter_hash:Hex64,
  manifest_fingerprint:Hex64,
  manifest_fingerprint_bytes: bytes[32],
  run_id:Hex32,
  module:string,                 # "1A.hurdle_sampler"
  substream_label:string,        # "hurdle_bernoulli"
  event_dataset_id:string,       # "rng_event_hurdle_bernoulli"
  event_schema_ref:string,       # schemas.layer1.yaml#/rng/events/hurdle_bernoulli
}

const MODULE            = "1A.hurdle_sampler"
const SUBSTREAM_LABEL   = "hurdle_bernoulli"
const EVENT_DATASET_ID  = "rng_event_hurdle_bernoulli"
const EVENT_SCHEMA_REF  = "schemas.layer1.yaml#/rng/events/hurdle_bernoulli"
```

## Kernel index (what follows in this doc)

* **S1.1 — Load & Guard (no RNG)**
  Fix inputs and preconditions; bind module/label literals and dataset id & schema ref (**no path formatting in L1**). *(attached next)*
* **S1.2 — Probability Map ($n\rightarrow\pi$) (no RNG)**
  `eta = dot_neumaier(β,x)`, `pi = logistic_branch_stable(eta)` (two-branch, overflow-safe logistic), guard finite/bounds.
* **S1.3 — RNG & Decision (≤1 draw)**
  Derive base counter; zero-draw if `pi∈{0,1}` else one uniform; compute `is_multi`.
* **S1.4 — Emit Event + Update Trace**
  Build envelope (microsecond ts, counters, `draws`, `blocks`), payload (`merchant_id, pi, is_multi, deterministic, u`), emit, then update cumulative trace (saturating totals).
* **S1.5 — Handoff Tuple (in-memory)**
  Build $\Xi_m$ and route (single-site → SingleHomePlacement (formerly S7), multi-site → NegativeBinomialS2 (formerly S2)). No counter chaining.

---

# S1.1 — Load & Guard (no RNG)

**Intent.** Fix all inputs and preconditions for the hurdle sampler **before any draw**: (a) obtain $x_m$ built by S0.5, (b) atomically load the single hurdle coefficient vector $\beta$, (c) assert strict shape/alignment, (d) assert the RNG audit row exists for `{seed, parameter_hash, run_id}`, (e) bind the **module/substream** literals and **event dataset id + schema ref** (no path strings in L1), and (f) hard-check frozen **block orders**.

---

## Interfaces

### Inputs

* `merchant_id : u64`, plus any attributes needed to **fetch $x_m$** from S0.5.
* `seed : u64`, `parameter_hash : hex64`, `manifest_fingerprint : hex64`, `run_id : hex32`.

### Outputs

* `beta : f64[D]` — single YAML vector (intercept + MCC + channel + **5** bucket dummies).
* `x_m : f64[D]` — hurdle design for merchant `m`, **exactly** $[1,\phi_{\text{mcc}},\phi_{\text{ch}},\phi_{\text{dev}}(b_m)]^\top$.
* `ctx : Context` — writer context with **literals & anchors** (no path strings in L1):

  * `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"`
  * `event_dataset_id="rng_event_hurdle_bernoulli"`, `event_schema_ref="schemas.layer1.yaml#/rng/events/hurdle_bernoulli"`

---

## Preconditions (abort if violated)

1. **Shape/alignment:** `len(beta) == len(x_m)`; blocks match S0.5’s frozen columns.
2. **Numeric policy in force:** IEEE-754 binary64, RNE, **no FMA**, **no FTZ/DAZ**; fixed-order reductions.
3. **RNG audit present:** `rng_audit_log` exists for `{seed, parameter_hash, run_id}` before any emission.

---

## Pseudocode

```pseudocode
function S1_1_load_and_guard(merchant_id:u64,
                              seed:u64, parameter_hash:hex64,
                              manifest_fingerprint:hex64, manifest_fingerprint_bytes: bytes[32], run_id:hex32)

  # 0) Bind registry literals & dataset anchors (no I/O yet)
  module            = MODULE
  substream_label   = SUBSTREAM_LABEL
  event_dataset_id  = EVENT_DATASET_ID
  event_schema_ref  = EVENT_SCHEMA_REF

  # 1) Obtain x_m built by S0.5 (preferred: in-memory handle; fallback: parameter-scoped cache)
  #    Exactly: [1, phi_mcc(mcc_m), phi_ch(channel_sym in ["CP","CNP"]), phi_dev(b_m in {1..5})]
  x_m = fetch_hurdle_design_vector_for(merchant_id, parameter_hash)
  assert x_m is not None, E_S1_INPUT_MISSING_XM

  # 2) Atomically load the SINGLE hurdle coefficient vector beta from the governed artefact
  beta = atomic_load_yaml_vector(registry.path("hurdle_coefficients"))

  # 3) Shape/alignment guard — MUST match S0.5 column order and dimension
  if length(beta) != length(x_m):
      abort(E_S1_DSGN_SHAPE_MISMATCH, exp=length(x_m), got=length(beta))

  # 3a) **NEW**: Frozen block-order assertions from the fitting bundle
  meta = load_hurdle_design_metadata()          # exposes frozen dict orders for the hurdle fit
  if meta.channel_order != ["CP","CNP"]:
      abort(E_S1_CHANNEL_ORDER_DRIFT, exp=["CP","CNP"], got=meta.channel_order)
  if meta.bucket_order  != [1,2,3,4,5]:
      abort(E_S1_BUCKET_ORDER_DRIFT, exp=[1,2,3,4,5],   got=meta.bucket_order)

  # 4) Require RNG audit row presence for this run BEFORE any hurdle emission
  if not exists_rng_audit_row(seed, parameter_hash, run_id):
      abort(E_S1_RNG_AUDIT_MISSING, seed, parameter_hash, run_id)

  # 5) Seal writer context (used by S1.3–S1.4)
  ctx = {
    seed: seed,
    parameter_hash: parameter_hash,
    manifest_fingerprint: manifest_fingerprint,
    manifest_fingerprint_bytes: manifest_fingerprint_bytes,
    run_id: run_id,
    module: module,
    substream_label: substream_label,
    event_dataset_id: event_dataset_id,
    event_schema_ref: event_schema_ref,
  }

  # (No path lint in L1 — path resolution & partition equality are enforced by dictionary/L0 at write time)

  return (beta, x_m, ctx)
```

**Helper contracts referenced (from L0 / registry)**

* `fetch_hurdle_design_vector_for(merchant_id, parameter_hash)` — returns frozen $x_m$ from S0.5 (or its parameter-scoped materialization).
* `atomic_load_yaml_vector(path)` — all-or-nothing load of the single β vector.
* `load_hurdle_design_metadata()` — returns `{channel_order:[…], bucket_order:[…]}` as pinned by the fitting bundle.
* `exists_rng_audit_row(seed, parameter_hash, run_id)` — discover audit presence by dictionary path.

---

## Determinism & side-effects

* **No RNG consumed.** Pure reads + assertions only.
* **Order-invariant.** `ctx` depends only on run lineage and registry literals.
* **No writes.** First emission occurs in **S1.4**.

---

## Failure semantics (precise aborts here)

* `E_S1_INPUT_MISSING_XM` — missing $x_m$ (S0.5 contract breach).
* `E_S1_DSGN_SHAPE_MISMATCH(exp_dim, got_dim)` — `|β| ≠ dim(x_m)`.
* `E_S1_CHANNEL_ORDER_DRIFT(exp, got)` — channel dict order drifted from `["CP","CNP"]`.
* `E_S1_BUCKET_ORDER_DRIFT(exp, got)` — bucket order drifted from `[1,2,3,4,5]`.
* `E_S1_RNG_AUDIT_MISSING(seed, parameter_hash, run_id)` — audit row absent.

---

**Return:** `(beta, x_m, ctx)` — ready for **S1.2 ($n\rightarrow\pi$)** with zero ambiguity.

---

# S1.2 — Probability Map (η → π) (no RNG)

**Intent.** For merchant `m`, compute the linear predictor $\eta=\beta^\top x_m$ in **binary64** with **fixed evaluation order**, then map to $\pi\in[0,1]$ via the **two-branch logistic** (no ad-hoc clamp). Abort on any non-finite or out-of-range result. `eta` is transient; `pi` will be serialized later in S1.4 with **binary64 round-trip**.

---

## Interfaces

### Inputs

* `beta : f64[D]` — single YAML coefficient vector loaded atomically in S1.1; shape/order equals `x_m`. (Prechecked.)
* `x_m  : f64[D]` — hurdle design vector from S1.1/S0.5, frozen column order. (Prechecked.)

### Outputs

* `eta : f64` — finite linear predictor (not persisted).
* `pi  : f64` — probability in **\[0,1]** (binary64). **Not** persisted here; passed to S1.3/S1.4.

---

## Preconditions (abort if violated)

1. **Numeric environment:** IEEE-754 **binary64**, RN-even, **no FMA**, **no FTZ/DAZ**, deterministic libm; fixed-order reductions. (Inherited from S0.8.)
2. **Shape/order:** `len(beta) == len(x_m)` and column order frozen. (Guarded in S1.1; treat any violation here as hard precondition failure.)

---

## Pseudocode

```pseudocode
# S1.2 entrypoint
function S1_2_probability_map(beta:f64[D], x_m:f64[D]) -> (eta:f64, pi:f64)

  # 1) Linear predictor in binary64 with fixed order (Neumaier compensation)
  eta = dot_neumaier(beta, x_m)                     # L0 primitive; fixed order

  # 2) Overflow-safe two-branch logistic (no ad-hoc clamp)
  #    if eta >= 0:  pi = 1 / (1 + exp(-eta))
  #    else:         pi = exp(eta) / (1 + exp(eta))
  pi = logistic_branch_stable(eta)                  # L0 primitive

  # 3) Guards (normative)
  if not is_finite(eta) or not is_finite(pi):
      abort(E_S1_NUMERIC_INVALID, {eta: eta, pi: pi})   # hard error

  # Two-branch evaluation under the S0.8 profile guarantees pi in [0,1]
  # (exact 0.0 or 1.0 may occur only from binary64 overflow/underflow of exp at extreme |eta|).
  if not (0.0 <= pi and pi <= 1.0):
      abort(E_S1_PI_OUT_OF_RANGE, {pi: pi})

  # 4) Hand-off (no persistence here)
  return (eta, pi)
```

**Notes bound to spec:**

* **Two-branch logistic** is mandatory; it’s the overflow-safe evaluation of $\sigma(\eta)$. **Do not clamp** results; exact `0.0` or `1.0` arises only from binary64 behavior at extreme $|\eta|$.
* `eta` is **transient/diagnostic** only; it is **not** a field in the authoritative event stream (S1.4). `pi` is later serialized with **binary64 round-trip** decimal.
* `pi` also determines **determinism** and S1.3’s **uniform budget**: `pi∈{0,1}` ⇒ draws=`0`; `0<pi<1` ⇒ draws=`1`. (Derived downstream; no RNG here.)

---

## Determinism & side-effects

* **No RNG consumed.** Pure FP compute; results depend only on `(beta, x_m)` and the fixed numeric policy.
* **No writes.** Outputs feed S1.3/S1.4 in memory only.

---

## Failure semantics (precise aborts here)

* `E_S1_NUMERIC_INVALID {eta, pi}` — either value non-finite.
* `E_S1_PI_OUT_OF_RANGE {pi}` — `pi ∉ [0,1]` (should not occur under two-branch).
* `E_S1_PRECOND_SHAPE_ORDER` — if a caller detects a late shape/order mismatch, treat as **hard precondition failure** (normally enforced in S1.1).

---

### L0 helpers used

* `dot_neumaier(beta, x)` — fixed-order compensated dot (binary64).
* `logistic_branch_stable(eta)` — overflow-safe two-branch logistic.

This S1.2 kernel exactly matches the frozen spec: fixed-order dot, two-branch logistic, strict guards, no over-engineering—and it hands a clean `(eta, pi)` to S1.3/S1.4 with zero ambiguity.

---

# S1.3 — RNG substream & Bernoulli decision (≤1 draw, no writes)

**Intent.** For merchant `m` with probability `pi` from S1.2, derive the order-invariant **base counter** for `(label="hurdle_bernoulli", m)`, decide whether a uniform is needed, possibly draw **one** `u∈(0,1)` using the **low lane** policy, decide `is_multi`, and produce the authoritative envelope elements (`before/after`, `draws`, `blocks`) for S1.4.

---

## Interfaces

### Inputs

* `pi : f64` — from S1.2; **finite** and `0.0 ≤ pi ≤ 1.0`. (Pre-guarded in S1.2.)
* `merchant_id : u64`.
* `ctx : Context` — from S1.1; includes `{seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label="hurdle_bernoulli"}`.

### Outputs (in-memory; passed to S1.4)

```pseudocode
Decision {
  deterministic: bool,           # (pi == 0.0 || pi == 1.0)
  is_multi: bool,                # (u < pi) when stochastic; else (pi == 1.0)
  u: f64|null,                   # null iff deterministic
  draws: string,                 # decimal u128: "0" or "1"
  blocks: u64,                   # 0 or 1; must equal u128_to_uint64_or_abort(decimal_string_to_u128(draws))
  before_hi: u64,
  before_lo: u64,
  after_hi: u64,
  after_lo: u64,
  stream_before: Stream,
  stream_after: Stream           # carry stream for S1.4 end_event_emit
}
```

(Budget identity `u128(after)-u128(before) == decimal_string_to_u128(draws)` must hold.)

---

## Preconditions (trusted from earlier sections)

* `pi` is finite and in `[0,1]`.
* Audit row exists for `{seed, parameter_hash, run_id}` (S1.1).

---

## Pseudocode

```pseudocode
function S1_3_rng_and_decision(pi:f64, merchant_id:u64, ctx:Context) -> Decision
  # 0) Derive order-invariant base counter for this (label, merchant)
  master = derive_master_material(ctx.seed, ctx.manifest_fingerprint_bytes)
  # Canonical typed id for SER(ids): merchant_u64 = LOW64(SHA256(LE64(merchant_id)))  (S0-L0)
  merchant_u64 = merchant_u64_from_id64(merchant_id)
  ids = [ { tag: "merchant_u64", value: merchant_u64 } ]    # explicit SER tag (typed 1-tuple)
  base = derive_substream(master, ctx.substream_label, ids)
  # Label must be exactly "hurdle_bernoulli" per registry/schema; ids uses tag "merchant_u64".

  before_hi = base.ctr.hi
  before_lo = base.ctr.lo

  deterministic = is_binary64_extreme01(pi)

  if deterministic:
      draws_str = "0"                 # decimal u128
      blocks    = 0
      u_val     = null
      is_multi  = (pi == 1.0)

      after_hi = before_hi
      after_lo = before_lo
      stream_after  = base
      stream_before = base

      # Budget identity: Δcounters == decimal_string_to_u128("0")
      (dhi, dlo) = u128_delta(after_hi, after_lo, before_hi, before_lo)
      assert (dhi == 0 and dlo == 0), E_S1_BUDGET_IDENTITY
      assert (blocks == 0), E_S1_BLOCKS_MISMATCH

  else:
      # One uniform, low lane, open interval
      (u_val, stream_after, draws_u128) = uniform1(base)          # consumes exactly 1 block
      assert is_open_interval_01(u_val), E_S1_U_OOB

      (dhi, dlo) = u128_delta(stream_after.ctr.hi, stream_after.ctr.lo, before_hi, before_lo)
      draws_str = u128_to_decimal_string(dhi, dlo)              # authoritative usage count
      after_hi  = stream_after.ctr.hi
      after_lo  = stream_after.ctr.lo
      stream_before = base

      # Normative blocks from counter delta
      (dhi, dlo) = u128_delta(after_hi, after_lo, before_hi, before_lo)
      blocks = u128_to_uint64_or_abort(dhi, dlo)
      # For hurdle, blocks must equal u128_to_uint64_or_abort(decimal_string_to_u128(draws))
      (p_hi, p_lo) = decimal_string_to_u128(draws_str)
      assert (blocks == u128_to_uint64_or_abort(p_hi, p_lo)), E_S1_BLOCKS_MISMATCH

      # Full budget identity (explicit)
      assert (dhi == p_hi and dlo == p_lo), E_S1_BUDGET_IDENTITY

      is_multi = (u_val < pi)

  return Decision{
    deterministic: deterministic,
    is_multi:      is_multi,
    u:             u_val,
    draws:         draws_str,
    blocks:        blocks,
    before_hi: before_hi,
    before_lo: before_lo,
    after_hi:  after_hi,
    after_lo:  after_lo,
    stream_before:         base,           # <— added for S1.4 begin_event_micro
    stream_after:          stream_after
  }
```

---

## Determinism & budgeting guarantees (why this matches the spec)

* **Keyed base counter.** `master = derive_master_material(seed, manifest_fingerprint_bytes); merchant_u64 = merchant_u64_from_id64(merchant_id); ids = [{tag:"merchant_u64", value: merchant_u64}]; base = derive_substream(master, label="hurdle_bernoulli", ids)` fixes the **order-invariant** starting counter for the merchant/label pair; no cross-label chaining.
* **Uniform policy.** Single-uniform events consume **one** Philox block and take the **low lane**; mapping to `U(0,1)` is strict-open, so `u` is never exactly `0` or `1`.
* **Branch law.** `pi∈{0,1}` ⇒ **zero** draw; `0<pi<1` ⇒ **exactly one** draw; outcome `is_multi = (u < pi)`; `u` is **null** iff deterministic.
* **Budget identity.** We compute `after` from the stream and check `u128(after)−u128(before) = decimal_string_to_u128(draws)`; for hurdle also `blocks == u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`. (S1.4 will persist these fields verbatim.)
* **No per-event trace write here.** Trace is **cumulative** and handled at S1.4; S1.3 only prepares envelope values.

---

## Failure semantics (raised here if violated)

* `E_S1_U_OOB` — stochastic branch produced `u ≤ 0` or `u ≥ 1` (violates open-interval mapping).
* `E_S1_BLOCKS_MISMATCH` — `blocks` not equal to `u128_to_uint64_or_abort(decimal_string_to_u128(draws))` or not in `{0,1}`.
* `E_S1_BUDGET_IDENTITY` — counter delta not equal to `decimal_string_to_u128(draws)`.

---

**Hand-off to S1.4.** Pass the returned `Decision` plus `(merchant_id, pi, ctx)` to S1.4 to: (a) build `envelope` (with **microsecond** `ts_utc`), (b) build minimal `payload` (`merchant_id, pi, is_multi, deterministic, u`), (c) **emit** the hurdle event, and (d) update the **cumulative** trace totals once.

---

# S1.4 — Emit event + update trace (authoritative stream)

**Intent.** Persist the single **hurdle_bernoulli** event for merchant `m` under the run lineage partitions, with a complete envelope and the minimal payload. Then update the per-(module, substream) **cumulative** RNG trace totals (`draws_total`, `blocks_total`, `events_total`). No decision logic lives here; we **verify** the S1.3 decision bundle and then write.
**Dataset anchors (fixed):**

* **Dataset id:** `rng_event_hurdle_bernoulli`
* **Schema:** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`
* **Path authority:** resolved at write-time by the dataset **dictionary** using
  `event_dataset_id` and lineage `{seed, parameter_hash, run_id}` (L0 helpers).
  *(No hard-coded templates in L1; partitions remain exactly `{seed, parameter_hash, run_id}`.)*

---

## Interfaces

### Inputs

* `merchant_id : u64`
* `pi : f64` — from S1.2 (finite, in `[0,1]`).
* `decision : Decision` — from S1.3:

  ```pseudocode
  Decision {
    deterministic: bool,
    is_multi: bool,
    u: f64|null,
    draws: string,                 # "0" or "1" (decimal u128)
    blocks: u64,                   # 0 or 1
    before_hi: u64,
    before_lo: u64,
    after_hi: u64,
    after_lo: u64,
    stream_before: Stream,         # from derive_substream(...); carries the same counters as {before_hi, before_lo}
    stream_after:  Stream          # after uniform1(base) or == base
  }
  ```

> Authority note: `before_*` / `after_*` counters are the single source of truth for budget identities.
> `stream_before` / `stream_after` are transport handles only; they must match the counters.
> If they disagree, the counters win and the kernel aborts.

* `ctx : Context` — from S1.1:

  ```pseudocode
  Context {
    seed:u64, parameter_hash:hex64, manifest_fingerprint:hex64, manifest_fingerprint_bytes: bytes[32], run_id:hex32,
    module:"1A.hurdle_sampler",
    substream_label:"hurdle_bernoulli",
    event_dataset_id:"rng_event_hurdle_bernoulli",
    event_schema_ref:"schemas.layer1.yaml#/rng/events/hurdle_bernoulli",
  }
  ```
> Note: `manifest_fingerprint_bytes` is in-memory only (derivation input). Logs always emit the hex64
> `manifest_fingerprint` in the envelope; never the raw bytes.

* `prev_totals : {draws_total:u64, blocks_total:u64, events_total:u64}` — running totals maintained by the orchestrator (L2) per `(module, substream_label)` for this run.

### Outputs

* **Side-effect:** one JSONL row appended to the **dictionary-resolved** hurdle event dataset (`event_dataset_id="rng_event_hurdle_bernoulli"`).
  *Note:* `module=="1A.hurdle_sampler"` and `substream_label=="hurdle_bernoulli"` are **envelope literals** (per registry); **path partitions** remain exactly `{seed, parameter_hash, run_id}`.
* **Side-effect:** one JSONL row appended to `rng_trace_log` — **one cumulative row per event**;
  totals are **saturating `uint64`**; **consumers select the final row per `(module, substream_label)`** as defined by `schemas.layer1.yaml#/rng/core/rng_trace_log`.
* `new_totals : {draws_total:u64, blocks_total:u64, events_total:u64}` — totals after this emission (return to L2).

**Serialization rules (explicit):**
* `pi` and (if non-deterministic) `u` are emitted as **JSON numbers** using `f64_to_json_shortest` (binary64 round-trip).
* **Lineage & counters:** `seed` is a **JSON integer**; `run_id`, `parameter_hash`, and `manifest_fingerprint` are **hex strings**. Counters are **JSON integers**.
  For `rng_trace_log`, only `seed` and `run_id` are embedded (and must equal the path keys); **`parameter_hash` is path-only**.

---

## Preconditions (abort if violated)

1. `decision.deterministic == (pi == 0.0 or pi == 1.0)`.
2. If `decision.deterministic` then `decision.u == null`; else `decision.u != null` and `0 < decision.u < 1`.
3. `decision.is_multi == ((decision.deterministic and pi==1.0) or (!decision.deterministic and decision.u < pi))`.
4. `decision.blocks ∈ {0,1}` and `decision.blocks == u128_to_uint64_or_abort(decimal_string_to_u128(decision.draws))`.
5. `u128(after) − u128(before) == decimal_string_to_u128(decision.draws)` using the provided counters.
6. **Embed-equality is ensured by construction in the writer:** the embedded `{seed, parameter_hash, run_id}` in the event envelope
   equals the dictionary partitions for the resolved path, byte-for-byte (driven by the same `ctx` in L0 `end_event_emit`).

---

## Pseudocode

```pseudocode
function S1_4_emit_event_and_update_trace(merchant_id:u64, pi:f64,
                                          decision:Decision, ctx:Context,
                                          prev_totals:{draws_total:u64, blocks_total:u64, events_total:u64})
  # --- 0) Verify S1.3 bundle (defensive, cheap) --------------------------------
  assert decision.deterministic == ((pi == 0.0) or (pi == 1.0)), E_S1_DTRM_INCONSISTENT

  if decision.deterministic:
      assert decision.u == null, E_S1_U_SHOULD_BE_NULL
      assert decision.is_multi == (pi == 1.0), E_S1_IS_MULTI_INCONSISTENT
  else:
      assert decision.u != null and is_open_interval_01(decision.u), E_S1_U_OOB
      assert decision.is_multi == (decision.u < pi), E_S1_IS_MULTI_INCONSISTENT

  # Budget checks (authoritative identities)
  (p_hi, p_lo) = decimal_string_to_u128(decision.draws)
  assert decision.blocks == u128_to_uint64_or_abort(p_hi, p_lo), E_S1_BLOCKS_MISMATCH

  (dhi, dlo) = u128_delta(decision.after_hi, decision.after_lo,
                          decision.before_hi, decision.before_lo)
  assert (dhi == p_hi and dlo == p_lo), E_S1_BUDGET_IDENTITY

  # --- 1) Begin event (envelope prelude; microsecond ts, 'before' counters) ----
  ev_ctx = begin_event_micro(ctx.module, ctx.substream_label,
                             ctx.seed, ctx.parameter_hash, ctx.manifest_fingerprint, ctx.run_id,
                             decision.stream_before)

  # Sanity: the 'before' we recorded must match decision
  assert ev_ctx.before_hi == decision.before_hi
  assert ev_ctx.before_lo == decision.before_lo

  # --- 2) Build minimal payload (binary64 round-trip for pi and nullable u) ----
  payload = {
    merchant_id: merchant_id,
    pi:          f64_to_json_shortest(pi),            # JSON number that round-trips to same binary64
    is_multi:    decision.is_multi,
    deterministic: decision.deterministic,
    u:          (decision.deterministic ? null : f64_to_json_shortest(decision.u))
  }

  # --- 3) Emit hurdle event (end_event computes blocks from counters & writes) --
  (draws_hi, draws_lo) = decimal_string_to_u128(decision.draws)

  end_event_emit(/*dataset_id*/ ctx.event_dataset_id,
                 /*ctx*/     ev_ctx,
                 /*stream_after*/ decision.stream_after,
                 /*draws_hi*/ draws_hi, /*draws_lo*/ draws_lo,
                 /*payload*/ payload)
  # Writer resolves dataset path from dictionary + lineage partitions (seed/parameter_hash/run_id)
  # and embeds the full envelope: ts_utc(μs), module, substream_label, lineage keys,
  # before/after counters, blocks (computed), draws (decimal u128), + payload.

  # --- 4) Update cumulative trace totals (saturating u64) -----------------------
  (new_blocks_total, new_draws_total, new_events_total) =
      update_rng_trace_totals(ctx.module, ctx.substream_label,
                              ctx.seed, ctx.parameter_hash, ctx.run_id,
                              decision.before_hi, decision.before_lo,
                              decision.after_hi,  decision.after_lo,
                              prev_totals.draws_total, prev_totals.blocks_total, prev_totals.events_total,
                              /*draws_str*/ decision.draws)
  # Reminder: trace totals are saturating u64. Per-event budget checks above use exact u128
  # arithmetic (with u128_to_uint64_or_abort) and do not saturate.    

  return { blocks_total:new_blocks_total, draws_total:new_draws_total, events_total:new_events_total }
```

---

## Determinism & budgeting guarantees

* **Single source of counters.** We use the exact `stream_before/stream_after` from S1.3; no recomputation.
* **Envelope identity.** `blocks` in the envelope is computed from counters; `draws` is the decimal u128 from S1.3; both satisfy
  `u128(after) − u128(before) = decimal_string_to_u128(draws)` and, for hurdle, `blocks == u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`.
* **Timestamp precision.** `begin_event_micro` stamps `ts_utc` with **exactly 6 fractional digits** (microseconds).
* **Float round-trip.** `pi` and (if present) `u` are serialized with `f64_to_json_shortest`, ensuring reparse → **bit-exact** binary64.
* **Trace semantics.** One cumulative row **per emission**; totals are **saturating** `uint64` and reconcile with event sums and counter deltas.
  Consumers select the **final** row per `(module, substream_label)` key per the trace schema.

---

## Failure semantics (raised here if violated)

* `E_S1_DTRM_INCONSISTENT` — `deterministic` flag doesn’t match `pi∈{0,1}`.
* `E_S1_U_SHOULD_BE_NULL` — deterministic branch carried a non-null `u`.
* `E_S1_U_OOB` — stochastic `u` not in the **open** interval `(0,1)`.
* `E_S1_IS_MULTI_INCONSISTENT` — `is_multi` not equal to `(u < pi)` in stochastic case (or `pi==1.0` in deterministic).
* `E_S1_BLOCKS_MISMATCH` — `blocks` not equal to `u128_to_uint64_or_abort(decimal_string_to_u128(draws))` or not in `{0,1}`.
* `E_S1_BUDGET_IDENTITY` — counter delta not equal to `decimal_string_to_u128(draws)`.

---

**Postcondition:** After this call, the run has **one** hurdle event row for the merchant and the **cumulative** trace totals are advanced by that event’s budgets. The return `new_totals` must be fed back to the orchestrator (L2) for the next iteration.

---

# S1.5 — Handoff tuple (in-memory only) & routing

**Intent.** From the hurdle event (the only authority for the decision and its own counters), build

$$
\Xi_m=(\text{is_multi}:\mathbf{bool},\,N:\mathbb{N},\,K:\mathbb{N},\,\mathcal C:\text{set[ISO]},\,C^\star:\text{u128})
$$

and select the next state: **SingleHomePlacement** (formerly S7) when single-site, **NegativeBinomialS2** (formerly S2) when multi-site; pass counters to downstream RNG; $C^\star$ is **audit-only**.

---

## Interfaces

### Inputs

* `hurdle_event : { envelope:{ after_hi:u64, after_lo:u64, … }, payload:{ merchant_id:u64, pi:f64, is_multi:bool, deterministic:bool, u:number|null } }`
  *(Authoritative single row produced in S1.4 for this merchant.)*
* `home_iso : string` — ISO-3166-1 alpha-2 for merchant `m` (from S0 universe).

### Outputs

```pseudocode
Xi {
  is_multi: bool,
  N: int,              # ≥0
  K: int,              # ≥0
  C_set: set[string],  # set of ISO alpha-2
  C_star: (hi:u64, lo:u64)  # u128 post-counter from hurdle (audit-only)
}
next_state: enum { SingleHomePlacement, NegativeBinomialS2 }
```

*(Exactly one $\Xi_m$ per merchant; no persistence.)*

---

## Preconditions (abort if violated)

1. `hurdle_event` exists for this merchant (S1 emitted exactly one).
2. `home_iso` is a valid ISO alpha-2 (present in the S0 universe).
3. `is_multi` is boolean, `u` follows the schema equivalences from S1.4 (already enforced there).

---

## Pseudocode

```pseudocode
function S1_5_build_handoff_and_route(hurdle_event, home_iso:string) -> (Xi, next_state)

  # 0) Read authoritative fields from the emitted event
  is_multi = hurdle_event.payload.is_multi            # boolean only
  C_star_hi = hurdle_event.envelope.rng_counter_after_hi
  C_star_lo = hurdle_event.envelope.rng_counter_after_lo

  # 1) Minimal construction per spec (no RNG, no I/O)
  if is_multi == false:
      N = 1
      K = 0
      C_set = { home_iso }
      next_state = SingleHomePlacement      # formerly S7
  else:
      N = UNASSIGNED         # set later in S2 (NB branch)
      K = UNASSIGNED         # set later in cross-border/ranking
      C_set = { home_iso }
      next_state = NegativeBinomialS2       # formerly S2 (multi-site)

  Xi = {
    is_multi: is_multi,
    N:        N,
    K:        K,
    C_set:    C_set,
    C_star:   (C_star_hi, C_star_lo)   # audit-only; do NOT chain counters
  }

  return (Xi, next_state)
```

---

## Determinism & side-effects

* **No writes.** Pure construction; returns in memory. One $\Xi_m$ per merchant.
* **No counter chaining.** Downstream RNG streams **derive their own base counters** with their own labels via S0’s keyed-substream mapping; $C^\star$ is **audit only**.
* **Gating surface.** Orchestrator/L3 will enforce "gated streams appear **iff** `is_multi=true`" using the registry filter (`owner_segment=1A`, `state>S1`, `gated_by_hurdle=true`). S1.5 does not enumerate stream names.

---

## Failure semantics (precise)

* `E_S1_MISSING_HURDLE_EVENT` — no hurdle event found for merchant (violates S1 single-emit invariant).
* `E_S1_HOME_ISO_INVALID` — `home_iso` missing or not an uppercase ISO alpha-2.

---

## Notes (implementation aids)

* The hurdle event is the **only authority** for both `is_multi` and its **own** counters; do **not** recompute from `pi`/`u` here.
* `N`/`K` are intentionally **unassigned** on the multi-site branch at S1; they are fixed downstream (S2+).
* Validators will check: (a) **presence gating** of downstream 1A streams vs. `is_multi`, and (b) **cross-label independence** (no counter chaining).

---

**Bottom line:** S1.5 returns a clean, typed $\Xi_m$ and a deterministic route with zero ambiguity, matching the frozen spec: **single emit**, **no counter chaining**, **registry-driven gating**, and **audit-only** $C^\star$.

---