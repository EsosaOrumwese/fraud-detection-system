# S2·L0 — Shared primitives for 1A / State-2 (authoritative)

# §1 Conventions & Scope

## 1.1 Purpose (what L0 is / isn’t)

**L0 = helper/capsule library for S2 only.** It exposes *pure numeric shims*, *PRNG primitives*, *one-attempt sampler capsules* (Gamma/Poisson **per attempt**, no loops), and *three thin event emitters* (Gamma, Poisson, Final). It **reuses** S0/S1 helpers (writer, dictionary path resolver, trace) instead of re-implementing them. **No orchestration, no business rules, no validators** live here; those belong to L1/L2/L3.

## 1.2 Sources of truth (authoritative references)

* **Schemas.** RNG event shapes—envelope + payload—are defined in `schemas.layer1.yaml#/rng/events/{gamma_component|poisson_component|nb_final}`.
* **Dictionary & paths.** RNG logs are JSONL under `logs/rng/events/{family}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; partitions are exactly `["seed","parameter_hash","run_id"]` (trace/audit conform likewise). **Resolve paths via the dictionary—no hard-coding.**
* **S2 literals (labels/modules).** Closed set is pinned later in §2; `nb_final` is **non-consuming**.
* **Numeric policy.** IEEE-754 **binary64**, **RNE**, **FMA off**, **no FTZ/DAZ**; fixed evaluation order.

## 1.3 Typing, naming, and JSON encoding

* **Scalars.** `u64` (unsigned 64-bit), `i64` (signed 64-bit), `f64` (binary64), `hex64`/`hex32` (lowercase fixed-length hex **strings**; in type declarations we write `Hex64`/`Hex32`). Payload floats **must round-trip** as binary64 (emit shortest round-trip decimals).
* **`draws` (decimal u128).** Event-level `draws` is a **decimal string** in the **dec_u128** domain: **no sign**, **no leading zeros** (except `"0"`), **≤39 digits**; regex `^(0|[1-9][0-9]{0,38})$`. **Never** infer `draws` from counters; use the S1 parser/formatter.
* **Timestamps.** `ts_utc` is **RFC 3339 UTC** with **exactly 6 fractional digits** and a trailing **`Z`**; *truncate, don’t round*. Pattern:
  `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{6}Z$` (writer `begin_event_micro`).
* **Names.** Labels and modules are **pinned constants** (see §2); **no hand-typed strings** elsewhere.

## 1.4 RNG & budgeting invariants (MUST)

* **Counters vs draws (independent identities).**
  `blocks := u128(after) − u128(before)` (unsigned-128); `draws := actual uniforms consumed`. Validators reconcile **both**; **no identity** ties `draws` to the counter delta.
* **Lane policy & `U(0,1)`.** Single-uniform **events** use the **low lane** only (`blocks=1`, `draws="1"`). Box–Muller consumes **both lanes from one block** (`blocks=1`, `draws="2"`). The `u01` map is **strict-open (0,1)**:
  `u=((as_f64(x)+1.0)*0x1.0000000000000p-64); if u==1.0 → 0x1.fffffffffffffp-1`.
* **Gamma budgets (MT98, exact actual-use).** Case A (α≥1): per iteration **+2 uniforms** (BM) then **+1** for accept-U; Case B (α<1): boost Γ(α+1) then **+1** for power step; **no padding/dummies**.
* **Poisson budgets.** **Inversion** for λ<10, **PTRS** otherwise; budgets vary per attempt and are recorded as `draws`.
* **Non-consuming events.** Keep `before == after`, set `blocks=0`, `draws="0"` (applies to `nb_final`).
* **No counter chaining.** **Never** derive a substream from a prior event’s `after`. Each `(module, label)` derives its **own** base counter via the keyed mapping; **no cross-label chaining**.

## 1.5 Imports & the single I/O surface (reuse, don’t re-invent)

* **Writers & trace.** Use **S1**: `begin_event_micro → end_event_emit → update_rng_trace_totals` (trace totals are **saturating**). Do **not** re-plumb envelope fields or totals in S2.
* **Dictionary paths.** Resolve via the shared dictionary resolver (S0/S1); **no embedded paths** in L0 code.
* **PRNG core.** Reuse `derive_substream`, `philox_block`, strict-open `u01`, and `normal_box_muller` (two uniforms, **no cache**), plus sampler kernels from S0/S1.

---

### Acceptance for §1

* One paragraph fixes L0’s scope & exclusions (**helpers-only**; no loops/validators/business rules).
* Cites **schemas**, **dictionary partitions**, **labels/modules** as authorities.
* Pins **numeric policy**, **strict-open `u01`**, **budgeting**, **non-consuming** semantics.
* Requires reuse of **S1 writer/trace** and the **dictionary resolver** (no re-implementation in S2).
* States float **round-trip** rule and `draws` **decimal-u128** encoding domain (regex).

---

# §2 Reuse Index (authoritative imports)

> Exactly which helpers we **import** from prior L0s. No redefinitions here. If a name exists in both S0 and S1, we **qualify S1** explicitly when S1 semantics are required (trace totals).

### PRNG core & substreams

* `derive_master_material(seed_u64, manifest_fingerprint_bytes)` — **S0.L0**. Audit-only master; input is **raw 32 bytes** of the fingerprint (**imported, unused in S2·L0**).
* `derive_substream(M, label, ids)` — **S0.L0**. Typed IDs via **SER**; order-invariant message `UER("mlr:1A") || UER(label) || SER(ids)`.
* `philox_block(stream) -> (x0, x1, next)` — **S0.L0**. Advances counter by **+1 block** per call.
* `u01(x:u64) -> f64` — **S0.L0**. **Strict-open (0,1)**; never 0.0 / 1.0.
* `uniform1(stream)` / `uniform2(stream)` — **S0.L0**. **Low-lane single** / **both lanes** from one block; **no caching**; budgets are actual uniforms.

### Samplers (actual-use budgets)

* `normal_box_muller(stream)` — **S0.L0**. **2 uniforms** per Z from one block; **no cache**.
* `gamma_mt(alpha, stream)` — **S0.L0**. MT1998; α≥1 uses BM+accept-U; α<1 boosts Γ(α+1) then **+1 uniform** (power step).
* `poisson(lambda, stream)` — **S0.L0**. Chooses **inversion** (λ<10) or **PTRS** (λ≥10) with the pinned constants.

### Envelope writers, paths & trace (single I/O surface)

* `begin_event_micro(module, substream_label, seed, parameter_hash, manifest_fingerprint, run_id, stream)` — **S1.L0** microsecond prelude (exactly 6 fractional digits; truncate).
* `end_event_emit(family, ctx, stream_after, draws_hi, draws_lo, payload)` — **S0.L0** event write (**computes `blocks` from counters**).
* `dict_path_for_family(family, seed, parameter_hash, run_id)` — **S0.L0** dictionary resolver (**no hard-coded paths**).
* `update_rng_trace_totals(...)` — **S1.L0** **saturating** cumulative totals for `rng_trace_log` (**import qualified** to avoid the S0 variant).

### 128-bit, counters & formatting

* `decimal_string_to_u128(str) -> (hi,lo)` — **S1.L0** authoritative parser for `draws` (dec-u128).
* `u128_to_decimal_string(hi,lo) -> string` — **S0.L0** partner encoder (source of truth).
* `u128_delta(after_hi,after_lo,before_hi,before_lo)`; `u128_to_uint64_or_abort(hi,lo)` — **S1.L0** helpers used by the S1 totals updater and envelope checks.
* `f64_to_json_shortest(x)` — **S1.L0** shortest round-trip JSON number (for payload `f64`).
* `ts_utc_now_rfc3339_micro()` — **S0.L0** clock (**aliased in S1.L0**); RFC-3339 UTC with **exactly 6** fractional digits, trailing `Z`.

### Typed IDs

* `merchant_u64_from_id64(id64) -> u64` — **S0.L0** canonical typed scalar for SER (`LOW64(SHA256(LE64(id64)))`).

---

### Notes & scope fences

* We **do not** reuse S0’s `event_gamma_component`/`event_poisson_component` wrappers because S2 payloads require `context:"nb"` and (for Gamma) `index:0` per the **S2 spec & schema**. S2 will provide **state-specific thin emitters** in §10 that call the shared writer.
* Numeric shims for §8 (`dot_neumaier` reuse; `exp64/lgamma64` as wrappers) are **attested** under the numeric policy from S0/S1; values for `(μ,φ)` must be **bit-identical** to those later echoed in `nb_final`.

**Acceptance for §2**

* Every name above is **imported** (no local re-definitions).
* **Qualified import** is used for **S1’s** `update_rng_trace_totals`.
* No other helpers are introduced in §2 (this section is an import map only).

---

# §3 S2 Literals (single source)

## 3.1 Purpose

Freeze all S2-specific **labels**, **modules**, **schema refs**, and **partitions** in one place. No other section may hand-type these strings.

## 3.2 Substream labels (closed set)

* `LABEL_GAMMA   = "gamma_nb"` — NB Gamma attempts substream.
* `LABEL_POISSON = "poisson_nb"` — NB Poisson attempts substream.
* `LABEL_FINAL   = "nb_final"` — NB finaliser (**non-consuming** event).

## 3.3 Producer modules (registry-closed per stream)

* `MODULE_GAMMA   = "1A.nb_and_dirichlet_sampler"` → for `gamma_component`.
* `MODULE_POISSON = "1A.nb_poisson_component"`     → for `poisson_component`.
* `MODULE_FINAL   = "1A.nb_sampler"`               → for `nb_final`.

## 3.4 Schema refs (authoritative)

* `SCHEMA_GAMMA   = "schemas.layer1.yaml#/rng/events/gamma_component"`
* `SCHEMA_POISSON = "schemas.layer1.yaml#/rng/events/poisson_component"`
* `SCHEMA_FINAL   = "schemas.layer1.yaml#/rng/events/nb_final"`

## 3.5 Dictionary ids, paths & partitions (no hard-coding elsewhere)

* **Gamma component**
  id: `rng_event_gamma_component`
  path: `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` *(example; resolved via dictionary)*
  partitions: `["seed","parameter_hash","run_id"]`
  produced_by: `1A.nb_and_dirichlet_sampler`
  gated by: `rng_event_hurdle_bernoulli` with `is_multi == true`.
* **Poisson component**
  id: `rng_event_poisson_component`
  path: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` *(example; resolved via dictionary)*
  partitions: `["seed","parameter_hash","run_id"]`
  produced_by: `1A.nb_poisson_component`
  gated by: `rng_event_hurdle_bernoulli` with `is_multi == true`.
* **Finaliser**
  id: `rng_event_nb_final`
  path: `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` *(example; resolved via dictionary)*
  partitions: `["seed","parameter_hash","run_id"]`
  produced_by: `1A.nb_sampler`
  gated by: `rng_event_hurdle_bernoulli` with `is_multi == true`.

**Embedded-only note.** `manifest_fingerprint` is **embedded in the envelope** for events but is **not** a path partition for RNG streams; path↔embed equality applies only to `{seed, parameter_hash, run_id}`.

## 3.6 Payload literals (must-carry fields)

* **Gamma events** carry `context:"nb"` and **`index:0` (fixed component id)**; payload fields: `alpha` = φ (binary64), `gamma_value` = G (binary64).
* **Poisson events** carry `context:"nb"`, with `lambda` (binary64) and `k` (int64).
* **Finaliser** carries `{mu, dispersion_k, n_outlets, nb_rejections}` and is **non-consuming** (`before==after`, `blocks=0`, `draws:"0"`).

## 3.7 Non-consumption rule (finaliser)

`LABEL_FINAL` events are **non-consuming** by design and must encode zero consumption in the envelope.

---

### Acceptance for §3

* All literals above appear **only here**; other sections reference them symbolically.
* Labels, modules, schema refs, and partitions match the **S2 legend + dictionary** exactly.
* Gamma/Poisson payloads include `context:"nb"` (and Gamma `index:0`); `nb_final` is non-consuming.

---

# §4 Core Types

## 4.1 Primitive aliases (shared across L0)

* `u64` / `i64` / `f64` — 64-bit unsigned / signed / IEEE-754 binary64. Floats must round-trip in JSON (shortest representation).
* `Hex64` — lowercase hex string of length 64 (32 bytes). Used for `parameter_hash`, `manifest_fingerprint`.
* `Hex32` — lowercase hex string of length 32. Used for `run_id`.
* `DecU128` — **decimal** string encoding an unsigned 128-bit integer (schema `dec_u128` domain). Used for event-level `draws`.

**Acceptance.** Names and string domains match the RNG envelope/trace schemas; floats are serialized shortest round-trip.

---

## 4.2 Substream handle (Philox stream)

```text
type Stream = { key:u64, ctr:{ hi:u64, lo:u64 } }
```

Single Philox-2×64 keyed stream with unsigned 128-bit counter `(hi,lo)`. One call to `philox_block` consumes **exactly one block** and advances the counter by `+1`. Lane policy: `uniform1` uses **low lane**; Box–Muller uses **both lanes of the same block**.

**Acceptance.** Struct fields and semantics match S0.L0; no extra fields.

---

## 4.3 Ids & SER tuple (for keyed substreams)

```text
# Only these tags are valid in SER v1:
enum SerTag = { iso, merchant_u64, i, j }

# Typed ids tuple used by derive_substream
type Ids = list[ { tag:SerTag, value:u64|string } ]
```

**Contract.** `derive_substream(M, label, Ids)` expects a **typed** tuple (no delimiters), with ISO codes uppercased before UER; indices `i/j` are LE32, 0-based. Any other tag is a hard error (`ser_unsupported_id`).

**Acceptance.** Tag set is closed; any new tag must be added upstream (S0) first.

---

## 4.4 Event prelude context (writer input)

```text
type EventCtx = {
  ts_utc:string,                 # RFC 3339, exactly 6 fractional digits (microseconds, truncate)
  module:string,                 # e.g., "1A.nb_sampler"
  substream_label:string,        # e.g., "gamma_nb"
  seed:u64,
  parameter_hash:Hex64,
  manifest_fingerprint:Hex64,
  run_id:Hex32,
  before_hi:u64, before_lo:u64   # counter BEFORE draws
}
```

Produced by `begin_event_micro(…)`; paired with `end_event_emit(…)` which computes `blocks` from counters and writes the full envelope row. **Microsecond** precision is *truncate, not round*.

**Acceptance.** Field names and precision match S1.L0 and the RNG envelope schema.

---

## 4.5 Envelope (logical shape; serialization handled by writer)

```text
# Logical (for reference only; actual serialization is done by end_event_emit)
type RngEnvelope = {
  ts_utc:string, run_id:Hex32, seed:u64,
  parameter_hash:Hex64, manifest_fingerprint:Hex64,
  module:string, substream_label:string,
  rng_counter_before_lo:u64, rng_counter_before_hi:u64,
  rng_counter_after_lo:u64,  rng_counter_after_hi:u64,
  blocks:u64,                # MUST equal u128(after)−u128(before)
  draws:DecU128              # actual uniforms consumed by THIS event
}
```

The RNG envelope is identical across RNG event families. `blocks` is checked by counters; `draws` is checked by **family budgets** and is **independent** of the counter delta. Non-consuming events (e.g., `nb_final`) keep `before==after`, set `blocks=0`, `draws="0"`.

**Acceptance.** **Field names** match the schema; the writer emits a consistent key order. Counters are spelled `rng_counter_{before,after}_{lo,hi}`.

---

## 4.6 Trace totals (cumulative)

```text
type TraceTotals = {
  draws_total:u64, blocks_total:u64, events_total:u64
}
```

Used only for `rng_trace_log` via S1’s **saturating** updater after each event emission; partitions remain `{seed, parameter_hash, run_id}`.

**Acceptance.** Totals are **saturating u64**; selection of the **final** row per `(module, substream_label)` follows the trace schema.

---

## 4.7 NB parameter pair (deterministic echo)

```text
type NbParams = { mu:f64, dispersion_k:f64 }  # φ stored as 'dispersion_k'
```

Values come from S2 links and must be **echoed bit-exactly** in `nb_final`.

**Acceptance.** Names/echo rule match S2’s finaliser obligations.

---

## 4.8 Attempt budget capsule (helper return)

```text
type AttemptBudget = { blocks:u64, draws_hi:u64, draws_lo:u64 }  # draws encoded as u128 pair
```

Returned alongside sampler outputs from the **pure** attempt helpers (Gamma/Poisson) so emitters can pass exact budgets to the writer and update trace totals. (Conversion to `DecU128` for the envelope is handled by shared helpers.)

**Acceptance.** No I/O; only carries counts required by the writer & trace updater.

---

### Section §4 Acceptance

* Only **types** are defined; **no loops, branching, or file I/O** here.
* `Stream`, `EventCtx`, envelope fields, and trace totals precisely match S0/S1 schemas & writers.
* `NbParams` echoes S2 values; `AttemptBudget` supports exact budget propagation without inferring `draws` from counters.

---

# §5 Numeric Policy Shims

## 5.1 Purpose

Deterministic numeric utilities used in S2·L0 (no RNG, no I/O): rounding policy, stable reductions, sealed libm usage, and float JSON printing. We **import** helpers from S0/L0 and S1/L0; only a tiny guard is defined locally.

---

## 5.2 Policy invariants (must hold everywhere)

* IEEE-754 **binary64**, **RNE** (ties-to-even), **FMA OFF**, **no FTZ/DAZ**, and **fixed evaluation order** exactly as written in pseudocode. Decision-critical reductions must **not** be parallelised or re-ordered (no topology-dependent BLAS). Mixed-precision contraction is forbidden. Violations (e.g., FMA enabled, FTZ/DAZ, non-deterministic libm) are run-abort conditions in S0.
* All accumulations use **serial Neumaier** (fixed order) for sums/dots.
* **Sealed libm surface** (`exp`, `log`, `log1p`, `expm1`, `sqrt`, `sin`, `cos`, `atan2`, `pow`, `tanh`, `erf` if used, `lgamma`) comes from the pinned **math profile** attested in S0 (bit-pattern checks). We do **not** re-wrap these here.
* All `f64` payloads are serialized by the **writer** as **shortest round-trip** JSON and parse back to identical binary64. (S1 printer.)

---

## 5.3 Imported helpers (authoritative names & sources)

* From **S0/L0**
  • `sum_neumaier(xs: iterable<f64>) -> f64` — serial Neumaier sum (fixed order).
  • `dot_neumaier(a: f64[], b: f64[]) -> f64` — Neumaier dot (multiply then compensated accumulate).
* From **S1/L0**
  • `f64_to_json_shortest(x:f64) -> string` — shortest round-trip JSON for floats.

> **Note.** Sealed libm (`exp`, `lgamma`, …) is provided by S0’s pinned math profile; we call it directly (no `exp64` aliases).

---

## 5.4 Minimal shim defined here (new)

```pseudocode
function assert_finite_positive(x:f64, name:string):
  # hard-error if NaN/±Inf or non-positive (used for μ, φ)
  if (not is_finite(x)) or (x <= 0.0):
      abort("ERR_S2_NUMERIC_INVALID:" + name)
```

*Rationale.* S2 requires **μ>0** and **φ>0** after exponentiation; any non-finite or ≤0 result is a merchant-scoped abort (`ERR_S2_NUMERIC_INVALID`).

---

## 5.5 Usage within S2

* **Links (→ §8 NB2 Parameter Transform).**
  `eta_mu = dot_neumaier(β_mu, x_mu)`; `eta_phi = dot_neumaier(β_phi, x_phi)`; then `mu = exp(eta_mu)`, `phi = exp(eta_phi)`; guard each with `assert_finite_positive`.
* **Emitters (→ §10).**
  Pass payload floats as **numbers**; the writer emits **shortest round-trip** decimals. **Do not** pre-serialize with `f64_to_json_shortest`.
* **Attempt capsules (→ §9).**
  Sampler kernels internally use sealed libm (`log`, `sqrt`, optional `lgamma`) via the reused S0 routines—no wrappers here.

---

## 5.6 Acceptance (for §5)

* **No RNG, no file I/O, no orchestration/validation logic.**
* Only **S0/S1-named** helpers are reused; the **sole** new helper is `assert_finite_positive`.
* Summations/dots are **serial Neumaier** with **fixed order** and **no FMA/FTZ/DAZ**; libm is the sealed S0 profile.
* Floats emitted later by L0 **round-trip** to the same binary64 (S1 printer).

---

# §6 RNG Primitives

## 6.1 What this section provides

Pure, reusable primitives for **keyed Philox streams**, **strict-open U(0,1)** mapping, **lane policy**, and **Box–Muller Z**. We **import** these from prior L0s; we do **not** redefine them here.

## 6.2 Imported names & exact behavior

* `derive_substream(M, label:string, ids:tuple) -> Stream{ key:u64, ctr:{hi:u64,lo:u64} }`
  Order-invariant keyed substream. Message is exactly
  `UER("mlr:1A") || UER(label) || SER(ids)`; `SER` tag set is `{iso, merchant_u64, i, j}` only. Counter is **unsigned 128-bit**. **Master `M` is derived upstream; do not re-derive here.**

* `philox_block(s:Stream) -> (x0:u64, x1:u64, s':Stream)`
  **PHILOX-2×64-10**; advances `ctr += 1` (**one block per call**), returns two 64-bit lanes.

* `u01(x:u64) -> f64` (**strict-open (0,1)**)
  Binary64 mapping: `u=((as_f64(x)+1.0)*0x1.0000000000000p-64)`; if `u==1.0`, remap to `0x1.fffffffffffffp-1`. Can **never** yield 0.0 or 1.0.

* `uniform1(s:Stream) -> (u:f64, s':Stream, draws:u128)`
  Uses **low lane only** from **one block**; budgets **`draws=1`** (actual uniforms). High lane is discarded.

* `uniform2(s:Stream) -> (u1:f64, u2:f64, s':Stream, draws:u128)`
  **Maps both lanes from a single `philox_block`** via `u01`; budgets **`draws=2`**. **No caching** beyond the return values. *(Not an alias to Box–Muller; Box–Muller consumes this.)*

* `normal_box_muller(s:Stream) -> (z:f64, s':Stream, draws:u128)`
  Standard normal via Box–Muller; consumes **exactly one Philox block** and **two uniforms** (budget **`draws=2`**). Returns the **cosine branch**; the sine mate is **discarded** (no cache). Use binary64 hex-literal `TAU = 0x1.921fb54442d18p+2` to avoid lib drift.

> **Budgets & lanes (must).** Single-uniform **events** always use the **low lane**; Box–Muller consumes **both lanes from one block**. Budgets are **actual uniforms consumed**, independent of the counter delta; counters advance **one block per `philox_block`**.

## 6.3 Developer-mode assertions (optional; no-op in prod)

Add these as **self-check hooks** if enabled, to make failures loud during tests:

* After `u01`, assert `0.0 < u && u < 1.0` (strict open).
* After `uniform1`, assert `draws==1` and `u == u01(low_lane)`; after `uniform2`, assert `draws==2` and lanes came from the **same** block.
* After `normal_box_muller`, assert `draws==2` and the stream counter advanced by **exactly one** block.

## 6.4 Explicit non-goals

No Gamma/Poisson math (see §9 “Attempt Capsules”). No writers (`begin_event_micro`/`end_event_emit`) or trace calls (see §7 / §10). No `stream_jump` emissions.

## 6.5 Acceptance for §6

* Names match prior L0/S0; **no re-definitions** here.
* `u01` is strict-open; `uniform1` = **1 block / 1 uniform**; `uniform2` = **1 block / 2 uniforms**; `normal_box_muller` = **1 block / 2 uniforms (no cache; cos branch)**; `TAU` is the binary64 hex literal.
* Lane/counter rules match S0; budgets are **actual uniforms**, not inferred from counter deltas.

---

# §7 I/O Surface (REUSE writer/trace)

## 7.1 What this section provides (one surface, three calls)

We **reuse exactly** these S0/S1 writer/trace APIs—no local re-plumbing:

* `begin_event_micro(...) -> EventCtx` — stamps **microsecond** `ts_utc` (exactly 6 digits, truncated), captures lineage and **before** counters.
* `end_event_emit(family, ctx, stream_after, draws_hi, draws_lo, payload)` — writes a single **event row** (envelope + payload), computes `blocks = u128(after) − u128(before)` and serializes `draws` as **decimal u128**. If `draws=="0"`, the writer **asserts** `after==before` (non-consuming).
* `update_rng_trace_totals(...)` — appends **one cumulative trace row per event** with **saturating u64** totals; path resolved from the dictionary (`rng_trace_log`). **Use the S1 variant (qualified import).**

> **Authoritative schemas/paths.** RNG **event families** and **trace** rows are defined in the layer schema set and dictionary. Event/trace partitions are **exactly** `{seed, parameter_hash, run_id}`; `rng_trace_log` embeds only `{seed, run_id}` (parameter_hash is path-only), per schema. **No hard-coded paths.**

---

## 7.2 Call pattern (used by S2 emitters in §10)

For **each** event we emit (Gamma / Poisson / Final):

1. **Prelude — build `ctx`.**
   `ctx = begin_event_micro(MODULE_*, LABEL_*, seed, parameter_hash, manifest_fingerprint, run_id, stream_before)`
   Captures `ts_utc` (**6 fractional digits, truncated**) and `before_{hi,lo}` counters.

2. **Write the event — envelope + payload.**
   `end_event_emit(DATASET_ID, ctx, stream_after, draws_hi, draws_lo, payload)`

* Computes `blocks` from counters (authoritative) and encodes `draws` using `u128_to_decimal_string(draws_hi,draws_lo)` (authoritative uniforms).
* If `draws=="0"`, **requires** `after==before` (non-consuming proof).
* Resolves the **dataset path from the dictionary** using `family` + `{seed, parameter_hash, run_id}`; **embed-equals-path** is enforced by construction (same `ctx`).

3. **Update cumulative trace — once per event.**
   `update_rng_trace_totals(MODULE_*, LABEL_*, seed, parameter_hash, run_id, before_hi, before_lo, after_hi, after_lo, prev_draws_total, prev_blocks_total, prev_events_total, draws_str)`

* **S1 semantics:** totals **saturate** at `UINT64_MAX`; per-event deltas still use `u128_to_uint64_or_abort`. The **trace row** embeds only `{seed, run_id}`; `parameter_hash` is **path-only**. Consumers select the **final** row per `(module, substream_label)`.

> **Single serialization point.** Emission + trace update is the **only** serialization point. The orchestrator ensures no parallel double-writes.

---

## 7.3 Family bindings (IDs, schema refs, partitions)

Emitters in §10 reference these **symbolically** (no literals elsewhere):

* **Gamma component**
  id `rng_event_gamma_component`, schema `schemas.layer1.yaml#/rng/events/gamma_component`, path `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`, partitions `["seed","parameter_hash","run_id"]`, produced_by `"1A.nb_and_dirichlet_sampler"`, gated by hurdle `is_multi==true`.
* **Poisson component**
  id `rng_event_poisson_component`, schema `schemas.layer1.yaml#/rng/events/poisson_component`, path `logs/rng/events/poisson_component/...`, module `"1A.nb_poisson_component"`, gated by hurdle `is_multi==true`.
* **Finaliser**
  id `rng_event_nb_final`, schema `schemas.layer1.yaml#/rng/events/nb_final`, path `logs/rng/events/nb_final/...`, module `"1A.nb_sampler"`, **non-consuming** (`blocks=0`, `draws:"0"`).
* **Trace (cumulative)**
  id `rng_trace_log`, schema `schemas.layer1.yaml#/rng/core/rng_trace_log`, partitions `["seed","parameter_hash","run_id"]`; **embedded** fields include only `{seed, run_id}`.

---

## 7.4 Invariants the writer/trace enforce (no re-checks in L0)

* **Embed ↔ path equality** for `{seed, parameter_hash, run_id}` is guaranteed by using the same `ctx` for `end_event_emit(...)`. For **trace**, only `{seed, run_id}` embed; `parameter_hash` is path-only.
* **Blocks from counters** (unsigned-128 delta); **draws = uniforms used** (decimal u128). **No identity** ties them together (except hurdle’s special-case law in S1).
* **Microsecond `ts_utc`** (exact 6 digits) on **events** and **trace** rows.
* **Trace totals are saturating `u64`**; consumers **select the final row** per `(module, substream_label)`.

---

## 7.5 Payload bindings for S2 families (what emitters must pass)

* **Gamma (`gamma_component`)**: payload `{merchant_id, context:"nb", index:0, alpha:φ, gamma_value:G}`.
* **Poisson (`poisson_component`)**: payload `{merchant_id, context:"nb", lambda, k}`.
* **Finaliser (`nb_final`)**: payload `{merchant_id, mu, dispersion_k, n_outlets, nb_rejections}` and **must be non-consuming** (`before==after`, `blocks=0`, `draws="0"`).

---

## 7.6 What §7 explicitly does **not** do

* No sampler math (Gamma/Poisson) — lives in §9 (**Attempt Capsules**).
* No business rules / attempt loops / rejection logic — lives in **L1/L2**.
* No schema definitions or path strings outside this section — **dictionary + schema are the authorities**.

---

### Acceptance for §7

* **Only** `begin_event_micro`, `end_event_emit`, and **S1’s** `update_rng_trace_totals` are used; **no** local writer/trace re-implementations.
* Event paths resolve via the **dictionary**; partitions are exactly `{seed, parameter_hash, run_id}`; trace embeds only `{seed, run_id}`.
* `nb_final` is **non-consuming**; the writer asserts `before==after` when `draws=="0"`.
* Trace rows are **cumulative, saturating** u64 and conform to `#/rng/core/rng_trace_log`; consumers select the **final** row per `(module, substream_label)`.

---

# §8 NB2 Parameter Transform

## 8.1 Purpose

Pure helper (no RNG, no I/O) that deterministically computes **NB2** parameters

*Symbols used in §8–§10:*  
`μ` (NB mean), `φ` (NB dispersion), `λ` (Poisson mean),  
`G` (Gamma draw), `N` (accepted outlets), `r` (rejections).

$$
\mu=\exp(\beta_\mu^\top x^{(\mu)}),\qquad \phi=\exp(\beta_\phi^\top x^{(\phi)})
$$

in **binary64** using fixed-order Neumaier dots. These exact floats are later **echoed bit-for-bit** in `nb_final` as `mu` and `dispersion_k`.

---

## 8.2 Inputs (preconditions)

* `x_mu : f64[Dμ]`, `x_phi : f64[Dφ]` — frozen design vectors:
  $x^{(\mu)}=[1,\Phi_{\mathrm{mcc}}(mcc),\Phi_{\mathrm{ch}}(channel)]$;
  $x^{(\phi)}=[1,\Phi_{\mathrm{mcc}}(mcc),\Phi_{\mathrm{ch}}(channel),\ln g_c]$ with **home** $g_c>0$. **Mean excludes GDP; dispersion includes $\ln g_c$**. Elements must be **finite**. Shapes are fixed by the encoders.
* `beta_mu : f64[Dμ]`, `beta_phi : f64[Dφ]` — governed coefficients keyed by `parameter_hash` (fitting bundle). **Finite**; shapes match their design vectors.
* Numeric policy everywhere: **binary64**, **RNE**, **FMA-OFF**, **no FTZ/DAZ**, **fixed evaluation order**. (From the state’s numeric gate.)

**If any precondition fails** (non-finite inputs, $g_c\le 0$, or shape mismatch upstream), the caller raises `ERR_S2_NUMERIC_INVALID` (merchant-scoped) and **no S2 events** are written.

---

## 8.3 Helper (pure)

```pseudocode
/// §8 nb2_params_from_design
@origin: S2/new
@maps_to: S2.2 links (deterministic)

function nb2_params_from_design(
    x_mu:   f64[],  # shape Dμ, finite
    x_phi:  f64[],  # shape Dφ, finite; last element is ln(g_c) with g_c>0
    beta_mu:f64[],  # shape Dμ, finite
    beta_phi:f64[]  # shape Dφ, finite
) -> NbParams
  # 1) Linear predictors (binary64, fixed order; no FMA)
  eta_mu  = dot_neumaier(beta_mu,  x_mu)    # REUSE §5
  eta_phi = dot_neumaier(beta_phi, x_phi)   # REUSE §5

  # 2) Exponentiate with sealed libm (no clamps)
  mu  = exp(eta_mu)
  phi = exp(eta_phi)

  # 3) Guards (MUST): non-finite or ≤0 => merchant-scoped abort upstream
  assert_finite_positive(mu,  "mu")            # REUSE §5
  assert_finite_positive(phi, "dispersion_k")  # REUSE §5

  # 4) Return (no RNG, no I/O)
  return NbParams{ mu: mu, dispersion_k: phi }
```

* Dots are **serial Neumaier** (multiply then compensated accumulate) in fixed order; no BLAS / no parallel re-ordering.
* `exp` comes from the **pinned math profile**; if it over/underflows, the guard trips (no clamping).

---

## 8.4 Invariants & downstream obligations

* **I-NB2-POS:** $\mu>0$, $\phi>0$. **I-NB2-B64:** both are binary64 and **round-trip** via shortest JSON decimals.
* **Echo binding (I-NB2-ECHO):** `nb_final.mu == μ` and `nb_final.dispersion_k == φ` at **bit equality**; any mismatch is structural failure.
* **No recompute drift:** S2.3–S2.5 **must** use these exact floats (not re-derived) when forming $\lambda=(\mu/\phi)G$ and when emitting `nb_final`.

---

## 8.5 Acceptance (for §8)

* Uses **only** deterministic FP ops (binary64, RNE, **FMA-OFF**, fixed order); **no RNG, no I/O**.
* Guards enforce **finite & positive** outputs; numeric violations map to `ERR_S2_NUMERIC_INVALID` (merchant-scoped).
* Returned values are suitable to be **echoed byte-for-byte** in `nb_final` (schema `schemas.layer1.yaml#/rng/events/nb_final`).

*(Optionally, in DEV_ASSERTS builds only: assert equal lengths of vectors and finiteness of all inputs to surface upstream encoding errors early. No-ops in prod, responsibility for shape checks remains with S2.1.)*

---

# §9 Attempt Capsules (pure; no I/O)

## 9.1 Purpose

Provide **single-attempt** samplers for the NB2 mixture that return the variate, the **updated substream**, and the **actual-use budgets** required by the emitters in §10. No writers, no loops, no acceptance policy here.

---

## 9.2 Gamma attempt — Marsaglia–Tsang (MT1998), strict budgets

```pseudocode
/// §9 gamma_attempt_with_budget
@origin: S2/new
@maps_to: S2.3 Γ(α=φ, 1) sampler; budgets per S2 spec

function gamma_attempt_with_budget(phi:f64, s_gamma:Stream)
  # Preconditions (φ from §8):
  assert_finite_positive(phi, "dispersion_k")                  # φ > 0, finite (numeric gate)

  # Snapshot before
  before_hi = s_gamma.ctr.hi
  before_lo = s_gamma.ctr.lo

  # Delegate to pinned kernel (MT1998 + Box–Muller; strict-open U(0,1); no cache)
  (G:f64, s1:Stream, draws_u128:uint128) = gamma_mt(phi, s_gamma)   # actual-use uniforms (no padding)

  # Compute blocks from counters (authoritative)
  (dhi, dlo) = u128_delta(s1.ctr.hi, s1.ctr.lo, before_hi, before_lo)
  blocks_u64 = u128_to_uint64_or_abort(dhi, dlo)

  # DEV_ASSERTS (no-op in prod)
  #   Case A (φ≥1): draws ≥ 3; Case B (φ<1): draws ≥ 4 (adds +1 for power step)

  return (G, s1, AttemptBudget{ blocks: blocks_u64,
                                draws_hi: HI(draws_u128), draws_lo: LO(draws_u128) })
```

**Budget law (normative, for validators):** For attempt $t$,
$\mathrm{draws}_\gamma(t)=2J_t + A_t + \mathbf{1}[\phi<1]$, where $J_t\ge1$ is the number of MT98 iterations and $A_t$ counts iterations with $V>0$ (only those draw the accept-$U$). **Blocks** equal the number of Philox **blocks** consumed internally and are derived from the counter delta above (no inference from `draws`).

**Lane policy:** Box–Muller consumes **both lanes from one block**; single-uniform draws use the **low lane** only. **Strict-open** `u01` ensures $u\in(0,1)$.

---

## 9.3 Poisson attempt — inversion / PTRS (regime-split), variable budgets

```pseudocode
/// §9 poisson_attempt_with_budget
@origin: S2/new
@maps_to: S2.3 Π(λ) sampler; regimes S0.3.7

function poisson_attempt_with_budget(lambda:f64, s_pois:Stream)
  assert_finite_positive(lambda, "lambda")                       # λ > 0, finite

  # Snapshot before
  before_hi = s_pois.ctr.hi
  before_lo = s_pois.ctr.lo

  # Delegate to pinned kernel (inversion if λ<10; PTRS otherwise; normative constants)
  (K:i64, s1:Stream, draws_u128:uint128) = poisson(lambda, s_pois)   # actual-use uniforms (variable)

  # Compute blocks from counters (authoritative)
  (dhi, dlo) = u128_delta(s1.ctr.hi, s1.ctr.lo, before_hi, before_lo)
  blocks_u64 = u128_to_uint64_or_abort(dhi, dlo)

  # DEV_ASSERTS (no-op in prod)
  #   λ<10 (inversion): draws ≥ 1; λ≥10 (PTRS): draws ≥ 2 (two uniforms per iteration)

  return (K, s1, AttemptBudget{ blocks: blocks_u64,
                                draws_hi: HI(draws_u128), draws_lo: LO(draws_u128) })
```

**Regimes (normative):** threshold $\lambda^\star=10$ (fixed). PTRS uses constants $b=0.931+2.53\sqrt\lambda$, $a=-0.059+0.02483\,b$, $\text{inv}\alpha=1.1239+\frac{1.1328}{b-3.4}$, $v_r=0.9277-\frac{3.6224}{b-2}$. **Two uniforms per PTRS iteration**; the number of iterations is geometric. Budgets are **measured**, not inferred.

---

## 9.4 Composition boundary (capsule contract)

L1 computes $\lambda = (\mu/\phi)\,G$ in **binary64** (fixed order) using §8 outputs, then calls `poisson_attempt_with_budget(λ, s_pois)`. If $\lambda$ is non-finite or $\le 0$, the caller must raise `ERR_S2_NUMERIC_INVALID` (merchant-scoped) and **not** emit S2 events.

---

## 9.5 Acceptance for §9

* **Pure helpers only:** no writers, no trace, no attempt loops or acceptance logic.
* **Gamma capsule:** MT1998 with **strict-open** uniforms and Box–Muller normals; returns **actual-use** `draws` and **counter-derived** `blocks`.
* **Poisson capsule:** S0.3.7 regime split (inversion/PTRS with **normative constants**); budgets are **variable** and measured.
* **Lane/counter rules:** match §6; budgets are **actual uniforms consumed**, independent of the counter delta (which determines `blocks`).

This keeps §9 strictly helper-level, returns everything §10 needs to stamp schema-correct events, and aligns exactly with your S2 expanded spec and the S0 sampler contracts.

---

# §10 Event Emitters

## 10.1 What these do

Turn **one attempt** (Gamma or Poisson) into a single JSONL **event row** and then append the **cumulative trace**. Emit these explicitly; there is **no separate wrapper** in L0.*

---

## 10.2 `event_gamma_nb(...)` — component event (context `"nb"`)

**Schema/Path/Lineage.** dataset id **`rng_event_gamma_component`**, schema `schemas.layer1.yaml#/rng/events/gamma_component`, path `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`. Envelope: microsecond `ts_utc`, `{seed, parameter_hash, manifest_fingerprint, run_id}`, `module="1A.nb_and_dirichlet_sampler"`, `substream_label="gamma_nb"`.

**Payload (must):** `{ merchant_id, context:"nb", index:0, alpha:φ, gamma_value:G }`.

```pseudocode
function event_gamma_nb(
  merchant_id:u64,
  seed:u64, parameter_hash:Hex64, manifest_fingerprint:Hex64, run_id:Hex32,
  s_before:Stream,          # gamma_nb stream BEFORE attempt
  phi:f64,                  # > 0 (finite)
  prev:TraceTotals          # cumulative (saturating) totals
) -> (G:f64, s_after:Stream, next:TraceTotals)

  # 0) Prelude (microsecond ts + 'before' counters)
  ctx = begin_event_micro(MODULE_GAMMA, LABEL_GAMMA,
                          seed, parameter_hash, manifest_fingerprint, run_id, s_before)        # writer prelude

  # 1) One attempt (pure capsule: value + budgets + updated stream)
  (G, s_after, bud) = gamma_attempt_with_budget(phi, s_before)                                  # MT1998, strict budgets

  # 2) Payload (pass numbers; writer emits shortest-decimal JSON)
  payload = {
    merchant_id: merchant_id,
    context: "nb",
    index: 0,
    alpha: phi,
    gamma_value: G
  }                                                                                            # pass numbers; writer prints shortest-decimal

  # 3) Emit event row (writer computes blocks from counters; 'draws' from budgets)
  end_event_emit(/*family*/ "rng_event_gamma_component",
                 /*ctx*/ ctx,
                 /*stream_after*/ s_after,
                 /*draws_hi*/ bud.draws_hi, /*draws_lo*/ bud.draws_lo,
                 /*payload*/ payload)                                                          # envelope+payload write

  # 4) Update cumulative trace (S1 semantics: saturating)
  draws_str = u128_to_decimal_string(bud.draws_hi, bud.draws_lo)
  (blk, drw, evt) =
    update_rng_trace_totals(ctx.module, ctx.substream_label,
                            seed, parameter_hash, run_id,
                            ctx.before_hi, ctx.before_lo, s_after.ctr.hi, s_after.ctr.lo,
                            prev.draws_total, prev.blocks_total, prev.events_total,
                            /*draws_str*/ draws_str)                                           # saturating totals

  next = TraceTotals{ blocks_total:blk, draws_total:drw, events_total:evt }
  return (G, s_after, next)
```

**Acceptance.** Budgets are **actual-use**; **do not** assert `blocks==1` (Gamma may span multiple iterations/blocks). Path partitions are exactly `{seed, parameter_hash, run_id}`; payload includes `context:"nb"` and `index:0`.

---

## 10.3 `event_poisson_nb(...)` — component event (context `"nb"`)

**Schema/Path/Lineage.** dataset id **`rng_event_poisson_component`**, schema `schemas.layer1.yaml#/rng/events/poisson_component`; partitions `{seed,parameter_hash,run_id}`; set `module="1A.nb_poisson_component"`, `substream_label="poisson_nb"`.

**Payload (must):** `{ merchant_id, context:"nb", lambda, k }`. **Compute** `lambda=(mu/phi)*G` **in the caller** (binary64), then this emitter samples and emits.

```pseudocode
function event_poisson_nb(
  merchant_id:u64,
  seed:u64, parameter_hash:Hex64, manifest_fingerprint:Hex64, run_id:Hex32,
  s_before:Stream,          # poisson_nb stream BEFORE attempt
  lambda:f64,               # > 0 (finite)
  prev:TraceTotals
) -> (k:i64, s_after:Stream, next:TraceTotals)

  ctx = begin_event_micro(MODULE_POISSON, LABEL_POISSON,
                          seed, parameter_hash, manifest_fingerprint, run_id, s_before)        # microsecond prelude

  # One attempt (pure capsule)
  (k, s_after, bud) = poisson_attempt_with_budget(lambda, s_before)                             # inversion/PTRS, variable budgets

  payload = {
    merchant_id: merchant_id,
    context: "nb",
    lambda: lambda,
    k: k
  }                                                                                            # pass numbers; writer prints shortest-decimal

  end_event_emit("rng_event_poisson_component", ctx, s_after,
                 bud.draws_hi, bud.draws_lo, payload)                                          # writer computes blocks

  draws_str = u128_to_decimal_string(bud.draws_hi, bud.draws_lo)
  (blk, drw, evt) =
    update_rng_trace_totals(ctx.module, ctx.substream_label,
                            seed, parameter_hash, run_id,
                            ctx.before_hi, ctx.before_lo, s_after.ctr.hi, s_after.ctr.lo,
                            prev.draws_total, prev.blocks_total, prev.events_total,
                            draws_str)                                                          # saturating totals

  next = TraceTotals{ blocks_total:blk, draws_total:drw, events_total:evt }
  return (k, s_after, next)
```

**Acceptance.** Budget is **variable** (inversion vs PTRS). Partitions and schema anchor match dictionary; payload includes `context:"nb"`.

---

## 10.4 `emit_nb_final_nonconsuming(...)` — finaliser (no RNG)

**Schema/Path/Lineage.** dataset id **`rng_event_nb_final`**, schema `schemas.layer1.yaml#/rng/events/nb_final`; partitions `{seed,parameter_hash,run_id}`; set `module="1A.nb_sampler"`, `substream_label="nb_final"`. **Non-consuming**: `before==after`, `blocks=0`, `draws:"0"`.

**Payload (must):** `{ merchant_id, mu, dispersion_k, n_outlets, nb_rejections }` where `mu, dispersion_k` **bit-match** §8 outputs; `n_outlets≥2`, `nb_rejections≥0`.

```pseudocode
function emit_nb_final_nonconsuming(
  merchant_id:u64,
  seed:u64, parameter_hash:Hex64, manifest_fingerprint:Hex64, run_id:Hex32,
  s_final:Stream,           # nb_final substream; NO draws are consumed
  mu:f64, dispersion_k:f64, n_outlets:i64, nb_rejections:i64,
  prev:TraceTotals
) -> TraceTotals

  ctx = begin_event_micro(MODULE_FINAL, LABEL_FINAL,
                          seed, parameter_hash, manifest_fingerprint, run_id, s_final)         # microsecond prelude

  payload = {
    merchant_id: merchant_id,
    mu: mu,
    dispersion_k: dispersion_k,
    n_outlets: n_outlets,
    nb_rejections: nb_rejections
  }                                                                                            # echo μ,φ exactly

  # Non-consuming: draws=="0" and counters unchanged; writer asserts equality
  end_event_emit("rng_event_nb_final", ctx, s_final,
                 /*draws_hi*/ 0, /*draws_lo*/ 0, payload)                                      # non-consuming event

  (blk, drw, evt) =
    update_rng_trace_totals(ctx.module, ctx.substream_label,
                            seed, parameter_hash, run_id,
                            ctx.before_hi, ctx.before_lo, s_final.ctr.hi, s_final.ctr.lo,
                            prev.draws_total, prev.blocks_total, prev.events_total,
                            /*draws_str*/ "0")                                                 # saturating totals; trace embed seed/run_id only

  return TraceTotals{ blocks_total:blk, draws_total:drw, events_total:evt }
```

**Acceptance.** Writer enforces **non-consumption** when `draws=="0"` (counters equal). **Exactly one** final per merchant; coverage implies ≥1 prior Gamma **and** ≥1 prior Poisson (`context:"nb"`).

---

## 10.5 Gating & partitions (for orchestrators)

All three streams are **gated** by the hurdle result: only merchants with `is_multi==true` have NB events; partitions are exactly `["seed","parameter_hash","run_id"]` (dictionary). L0 emitters don’t check gating; L2 ensures it.

---

### §10 Acceptance

* Exactly **three** emitters; **no loops**, **no sampler math beyond §9 calls**, **no schema redefinitions**.
* Gamma/Poisson payloads include `context:"nb"` (Gamma also `index:0`); Final is **non-consuming** and **echoes** §8 values.
* IDs, schema refs, modules, labels, and partitions match the dictionary/spec; paths are resolved by the writer; **trace totals are saturating**.

---

# §11 Failure Payload Builders

## 11.1 Purpose

Expose the **single, canonical** failure/abort interface for 1A so S2 surfaces errors in the exact forensic format defined in **S0.9**. We **import** the Batch-F helpers from S0/L0—**no local variants, no new classes, no shape tweaks**—so every state aborts identically.

---

## 11.2 Imported helpers (authoritative names & behavior)

* `build_failure_payload(failure_class, failure_code, ctx) -> object`
  Returns the normative **failure JSON** envelope. Timestamp domain is **epoch-ns** (`now_ns()`), not RFC-3339. Required fields are fixed (see §11.3).

* `abort_run(failure_class, failure_code, seed, parameter_hash, manifest_fingerprint, run_id, detail, partial_partitions[])`
  **Atomically** commits the run-scoped failure bundle and terminates the run non-zero; writes optional `_FAILED.json` sentinels in any leaked partitions. (Legacy alias `abort(...)` forwards to `abort_run`.)

* `abort_run_atomic(payload, partial_partitions[])`
  Convenience wrapper that takes a prebuilt payload (e.g., from `build_failure_payload`) and delegates to `abort_run`.

* `merchant_abort_log_write(rows, parameter_hash)`
  **Parameter-scoped** soft-abort log writer (only for states that explicitly allow merchant-abort). S2 uses **run-abort** for structural/discipline/corridor failures; merchant-abort never replaces a run-abort.

> These are the **only** ways S2 should build/commit failure records. L2 (or L3) calls them directly; S2·L0 **does not** wrap or modify their behavior.

---

## 11.3 Canonical failure JSON (shape & fields)

`build_failure_payload(...)` yields this uniform envelope (required unless noted optional):

```json
{
  "failure_class": "F1"…"F10",
  "failure_code":  "snake_case",
  "state":         "Sx.y",
  "module":        "…",
  "dataset_id":    "…"        /* optional */,
  "merchant_id":   "…" | null /* optional */,
  "parameter_hash":"<hex64>",
  "manifest_fingerprint":"<hex64>",
  "seed":          <u64>,
  "run_id":        "<hex32>",
  "ts_utc":        <u64 epoch-ns>,
  "detail":        { /* typed minima per code */ }
}
```

This schema (including **epoch-ns** `ts_utc`) is fixed by S0; **do not** add ad-hoc fields in S2. Every failure record must carry **both** `failure_class` and `failure_code`.

---

## 11.4 Where failures live (paths, partitions, atomics)

Run-scoped failure bundles are **fingerprint-scoped** and committed atomically at:
`data/layer1/1A/validation/failures/fingerprint={manifest_fingerprint}/seed={seed}/run_id={run_id}/`
with at least:

* `failure.json` (mandatory, single file)
* `_FAILED.SENTINEL.json` (duplicate header for quick scans)

Re-runs with identical lineage **must not** overwrite the committed `failure.json` (temp dir → atomic rename).

For states that permit **merchant-abort**, the soft-abort log is **parameter-scoped**:
`.../prep/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet` (never a substitute for a run-abort).

Validation bundles themselves are under
`data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` (dictionary).

---

## 11.5 Failure taxonomy to use from S2

Use **S0.9 classes F1–F10** with **S2 concrete codes**. Examples grounded in the spec & validator crosswalk:

* Merchant-scoped numeric invalids: `ERR_S2_NUMERIC_INVALID` (F3/F4 as appropriate).
* Schema/structure/discipline: `schema_violation`, `event_coverage_gap`, `rng_consumption_violation`, `composition_mismatch`, `partition_misuse`, `branch_purity_violation`.
* Corridor breaches (validator): `corridor_breach:{rho|p99|cusum}`.

> Typed minima for `detail` (what fields must appear per code) are defined in S0.9/S1/S2 specs and validators; the builder **only** provides the envelope.

---

## 11.6 Usage in S2 (call sites)

* **L1/L2:** On an S2 error, assemble `ctx` (state/module + lineage + `detail`) →
  `payload = build_failure_payload(failure_class, failure_code, ctx)` →
  `abort_run_atomic(payload, partial_partitions)` (if any). S2·L0 **never** invokes aborts itself.

---

### §11 Acceptance

* Only the **four** helpers above are exposed; **no** local variants/tweaks.
* Failure JSON uses **epoch-ns** `ts_utc`, includes **both** `failure_class` and `failure_code`, and carries the required lineage keys.
* Failure bundles are **fingerprint-scoped** and **atomically** committed at the S0 path; validation bundle path remains dictionary-backed.
* S2 uses S2-specific codes from the frozen spec; L0 **does not** invent new codes or shapes.

All checks out against your S0/L0 Batch-F definitions, S0.9 expanded spec, and the dictionary/registry.

---

# §12 Public API Index

## 12.1 Constants (single source; no hand-typing elsewhere)

* `LABEL_GAMMA = "gamma_nb"`; `LABEL_POISSON = "poisson_nb"`; `LABEL_FINAL = "nb_final"`.
* `MODULE_GAMMA = "1A.nb_and_dirichlet_sampler"`; `MODULE_POISSON = "1A.nb_poisson_component"`; `MODULE_FINAL = "1A.nb_sampler"`.
* `SCHEMA_GAMMA = "schemas.layer1.yaml#/rng/events/gamma_component"`; `SCHEMA_POISSON = "schemas.layer1.yaml#/rng/events/poisson_component"`; `SCHEMA_FINAL = "schemas.layer1.yaml#/rng/events/nb_final"`.
* Dictionary paths/partitions for RNG events & trace: `["seed","parameter_hash","run_id"]`.

---

## 12.2 Types (records only; no logic)

* `Stream { key:u64, ctr:{hi:u64, lo:u64} }` — Philox-2×64 stream (one **block** per `philox_block`).
* `Ids = list[{tag∈{iso,merchant_u64,i,j}, value:u64|string}]` — typed tuple for `derive_substream`.
* `EventCtx { ts_utc, module, substream_label, seed, parameter_hash, manifest_fingerprint, run_id, before_hi, before_lo }` — from `begin_event_micro`.
* `TraceTotals { draws_total:u64, blocks_total:u64, events_total:u64 }` — **saturating** u64 totals.
* `NbParams { mu:f64, dispersion_k:f64 }` — must be **echoed bit-exactly** in `nb_final`.
* `AttemptBudget { blocks:u64, draws_hi:u64, draws_lo:u64 }` — per-event actual-use budgets.

---

## 12.3 Numeric shims (REUSE unless noted)

| Helper                           | Inputs       | Output             | Side-effects | Used by | Origin |
|----------------------------------|--------------|--------------------|--------------|---------|--------|
| `sum_neumaier(xs)`               | f64[]        | f64                | —            | §8      | S0.L0  |
| `dot_neumaier(a,b)`              | f64[], f64[] | f64                | —            | §8      | S0.L0  |
| `f64_to_json_shortest(x)`        | f64          | string             | —            | -       | S1.L0  |
| `assert_finite_positive(x,name)` | f64, string  | — (throws on fail) | —            | §8/§9   | NEW    |

(Shortest-round-trip printer & saturating discipline per S1.)

---

## 12.4 PRNG primitives (REUSE)

| Helper                          | Inputs              | Output                        | Side-effects                  | Used by | Origin |
|---------------------------------|---------------------|-------------------------------|-------------------------------|---------|--------|
| `derive_substream(M,label,Ids)` | master, string, Ids | Stream                        | —                             | §10     | S0.L0  |
| `philox_block(s)`               | Stream              | (x0:u64, x1:u64, s’)          | advances counter **+1 block** | §6/§9   | S0.L0  |
| `u01(x)`                        | u64                 | f64 **strict-open (0,1)**     | —                             | §6/§9   | S0.L0  |
| `uniform1(s)`                   | Stream              | (u:f64, s’, draws=1)          | +1 block; **low lane**        | §9      | S0.L0  |
| `uniform2(s)`                   | Stream              | (u1:f64, u2:f64, s’, draws=2) | +1 block; **both lanes**      | §9      | S0.L0  |
| `normal_box_muller(s)`          | Stream              | (z:f64, s’, draws=2)          | +1 block; **no cache**        | §9      | S0.L0  |

(Strict-open map & lane policy per S0.)

---

## 12.5 I/O surface (REUSE writer/trace)

| Helper                                                                   | Inputs                                                                    | Output                                                  | Side-effects                                                                | Used by | Origin |
|--------------------------------------------------------------------------|---------------------------------------------------------------------------|---------------------------------------------------------|-----------------------------------------------------------------------------|---------|--------|
| `begin_event_micro(...)`                                                 | module, label, seed, parameter_hash, manifest_fingerprint, run_id, stream | `EventCtx`                                              | stamps **microsecond** `ts_utc` (6 digits; truncate)                        | §10     | S1.L0  |
| `end_event_emit(family, ctx, stream_after, draws_hi, draws_lo, payload)` | —                                                                         | —                                                       | writes **one** JSONL event; computes `blocks=after−before`; encodes `draws` | §10     | S0/S1  |
| `update_rng_trace_totals(...)`                                           | lineage + counters + `draws_str`                                          | (blocks_total, draws_total, events_total)               | appends **saturating** trace row; trace embed `{seed,run_id}` only          | §10     | S1.L0  |
| `dict_path_for_family(family, seed, parameter_hash, run_id)`             | ids                                                                       | path                                                    | resolves dictionary path (no hard-coding)                                   | §7/§10  | S0/S1  |

(Trace schema/path & partitions per dictionary.)

---

## 12.6 NB2 math (NEW)

| Helper                                                   | Inputs     | Output                       | Side-effects | Used by              | Origin |
|----------------------------------------------------------|------------|------------------------------|--------------|----------------------|--------|
| `nb2_params_from_design(x_mu, x_phi, beta_mu, beta_phi)` | f64\[] × 4 | `NbParams{mu, dispersion_k}` | —            | §10 (final echo), L1 | NEW    |

(Values **echoed bit-exactly** in `nb_final`.)

---

## 12.7 Attempt capsules (pure; no I/O)

| Helper                                        | Inputs      | Output                      | Side-effects                            | Used by | Origin              |
|-----------------------------------------------|-------------|-----------------------------|-----------------------------------------|---------|---------------------|
| `gamma_attempt_with_budget(phi, s_gamma)`     | φ>0, Stream | (G\:f64, s’, AttemptBudget) | advances stream; **actual-use** budgets | §10     | wraps S0 `gamma_mt` |
| `poisson_attempt_with_budget(lambda, s_pois)` | λ>0, Stream | (k\:i64, s’, AttemptBudget) | advances stream; **actual-use** budgets | §10     | wraps S0 Poisson    |

(Regimes & budgets per S0/S2.)

---

## 12.8 Event emitters (NEW, thin wrappers)

| Helper                            | Inputs                                                     | Output                   | Side-effects                                                                                                                  | Used by | Schema/Dict                                         |
|-----------------------------------|------------------------------------------------------------|--------------------------|-------------------------------------------------------------------------------------------------------------------------------|---------|-----------------------------------------------------|
| `event_gamma_nb(...)`             | merchant_id, lineage, `s_before`, φ, `prev_totals`         | (G, s_after, new_totals) | writes **`rng_event_gamma_component`** row; updates trace; payload `{merchant_id, context:"nb", index:0, alpha, gamma_value}` | L1/L2   | `schemas.layer1.yaml#/rng/events/gamma_component`   |
| `event_poisson_nb(...)`           | merchant_id, lineage, `s_before`, λ, `prev_totals`         | (k, s_after, new_totals) | samples; writes **`rng_event_poisson_component`**; payload `{merchant_id, context:"nb", lambda, k}`; updates trace            | L1/L2   | `schemas.layer1.yaml#/rng/events/poisson_component` |
| `emit_nb_final_nonconsuming(...)` | merchant_id, lineage, `s_final`, μ, φ, N, r, `prev_totals` | new_totals               | writes **`rng_event_nb_final`**; **non-consuming** (`blocks=0`, `draws:"0"`); echoes μ,φ bit-exactly                          | L1/L2   | `schemas.layer1.yaml#/rng/events/nb_final`          |

(IDs/paths/partitions and payload literals per S2 spec & dictionary.)

---

## 12.9 Utilities (REUSE + tiny glue)

| Helper                                                        | Inputs            | Output           | Side-effects         | Used by    | Origin  |
|---------------------------------------------------------------|-------------------|------------------|----------------------|------------|---------|
| `u128_to_decimal_string(hi,lo)` / `decimal_string_to_u128`    | (hi,lo) / string  | string / (hi,lo) | —                    | §7/§10     | S0 / S1 |
| `u128_to_uint64_or_abort(hi,lo)` / `u128_delta(...)`          | (hi,lo) / (4×u64) | u64 / u128       | —                    | §7         | S1      |

(Decimal-u128 & saturating trace per S1.)

---

## 12.10 Failure payloads (REUSE; no new shapes)

| Helper                                           | Inputs            | Output      | Side-effects                                   | Used by  | Origin |
|--------------------------------------------------|-------------------|-------------|------------------------------------------------|----------|--------|
| `build_failure_payload(class, code, ctx)`        | enums + context   | JSON object | —                                              | L1/L2/L3 | S0     |
| `abort_run(...)` / `abort_run_atomic(...)`       | lineage + payload | —           | **atomic** commit of run-scoped failure bundle | L2/L3    | S0     |
| `merchant_abort_log_write(rows, parameter_hash)` | rows, hash        | —           | parameter-scoped soft-abort log                | L1/L3    | S0     |

(Atomic failure bundle & fingerprint-scoped paths per S0.)

---

### §12 Acceptance

* Every callable exposed by S2·L0 appears **exactly once** with inputs/outputs/side-effects & provenance (REUSE vs NEW).
* Schemas/paths/partitions for RNG events match the **frozen S2 legend + dataset dictionary**; no hand-typed paths elsewhere.
* Writer/trace helpers are the **S1** variants (microsecond `ts_utc`; **saturating** totals).
* PRNG primitives & samplers reuse **S0** semantics (strict-open `u01`, lane policy, **actual-use** budgets).
