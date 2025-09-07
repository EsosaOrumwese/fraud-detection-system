# L0 — Shared primitives for 1A / State-1 (authoritative)

> **Importing note (name collision):** This file defines `update_rng_trace_totals` with **S1 semantics** (cumulative **saturating** `uint64` totals).
> S0 also provides a function named `update_rng_trace_totals` with **non-saturating** semantics and monotonicity asserts.
> When both modules are available, **import this module qualified** and call the S1 variant explicitly. Do **not** re-export or alias S0’s totals updater in S1 contexts.

## A) Reuse from S0-L0 (don’t redefine; call as-is)

**PRNG core & keyed substreams** (order-invariant)

* `derive_master_material(seed_u64, manifest_fingerprint_bytes) -> (M, root_key, root_ctr)` — audit-only master.
* `derive_substream(M, label:string, ids:tuple) -> Stream{ key:u64, ctr:(hi:u64,lo:u64) }`.
* `philox_block(s:Stream) -> (x0:u64, x1:u64, s':Stream)` — advances counter by +1.
* `u01(x:u64) -> f64` — strict-open (0,1) map; never 0.0 or 1.0.
* `uniform1(s) -> (u:f64, s':Stream, draws:uint128)` — **low lane** only, 1 block.
* `uniform2(s) -> (u1, u2, s', draws:uint128)` — both lanes, 1 block.

> **Normative input form:** `derive_master_material` consumes **manifest_fingerprint_bytes (32 raw bytes)**. If you hold the fingerprint as a hex string in higher layers, **decode it to bytes first**, derive the **master**, then call `derive_substream(M, …)`.
> Substreams are always **master-based** (per S0).

**Samplers (budgets = actual uniforms)**
`normal_box_muller`, `gamma_mt`, `poisson_{inversion,ptrs}`, `poisson_ztp`, `gumbel_key`. (S1 uses only `uniform1`, but the budget rules are shared.)

**Envelope & writers (authoritative counters/budgets)**

* `emit_rng_audit_row(...)` — S0 audit; **must exist** before S1’s first event.
* `begin_event_ctx(module, substream_label, seed, parameter_hash, manifest_fingerprint, run_id, stream) -> EventCtx` — captures `ts_utc` (nanoseconds in S0).
* `end_event_emit(family, ctx, stream_after, draws_hi, draws_lo, payload)` — writes envelope+payload; **internal** `blocks = after − before` (u128); **emitted** `blocks` field is `u64` per event (hurdle: `0` or `1`).

**Dictionary resolver (paths)**
`dict_path_for_family(family:string, seed:u64, parameter_hash:hex64, run_id:hex32) -> path` — reuse S0-L0 to resolve all RNG audit/trace/event paths from the dataset dictionary.

**Legacy trace updater (blocks only; S0) — DEPRECATED for S1 producers**
`update_rng_trace(...) -> new_blocks_total:uint64` — cumulative **blocks** (S0). S1 replaces this with a totals variant below.

**128-bit helpers & numeric kernels**
`add_u128`, `u128_delta`, `u128_to_uint64_or_abort`, `u128_to_decimal_string`; `dot_neumaier`, `logistic_branch_stable` (two-branch). Math policy: binary64, RNE, no FMA, no FTZ/DAZ.

**Additional primitives used by this file (reuse from S0-L0)**
Clock/formatting: `clock_utc_posix`, `format_utc_calendar`, `pad_left`, `to_decimal`.  
Shortest-decimal: `decompose_binary64`, `floor_log10_pow2`, `compute_roundtrip_interval`, `generate_shortest_decimal`, `format_decimal_with_exponent`.  
u128 math: `mul_u128_by_small`, `divmod_u128_by_small`.  
Dictionary paths: `dict_path_for_family`.

**Clock & timestamps**
`ts_utc_now_rfc3339_micro()` — **reuse S0-L0** F1 capsule (UTC, **exactly 6** fractional digits; **truncate, don’t round**; trailing `Z`).

> S1 envelope/payload invariants: **microsecond** `ts_utc`, decimal-string **u128 draws**, `blocks == parse_u128(draws)` for hurdle, one event per merchant, and keyed substreams with **no cross-label chaining**. Use the new helpers below where noted.

---

## B) New primitives for S1 (fully specified)

### B1. `ts_utc_now_rfc3339_micro() -> string`

**Intent:** RFC-3339 UTC with **exactly 6** fractional digits (`… .ffffffZ`) for S1 event `ts_utc`.

**Implementation:** **Alias to S0-L0** `ts_utc_now_rfc3339_micro()` (F1 capsule). S1 does **not** reimplement this; behavior is **truncate** from ns→µs (no rounding).

### B2. `f64_to_json_shortest(x:f64) -> string`

**Intent:** Shortest JSON decimal that **round-trips** to the same binary64 when parsed (used for `pi` and stochastic `u`). Inputs must be finite.

```pseudocode
function f64_to_json_shortest(x:f64) -> string
  assert is_finite(x)
  if x == 0.0: return "0"
  (sign, m, e2) = decompose_binary64(x)                   # x = sign * m * 2^e2
  k = floor_log10_pow2(e2) + floor_log10(m)
  (lo, hi) = compute_roundtrip_interval(m, e2)            # exact interval
  digits = generate_shortest_decimal(lo, hi)              # Schubfach/Dragonbox-class
  s = format_decimal_with_exponent(digits, k)             # plain/scientific per JSON
  return (sign < 0) ? ("-" + s) : s
```

### B3. `decimal_string_to_u128(s:string) -> (hi:u64, lo:u64)`

**Intent:** Parse non-negative base-10 string (no sign; `"0"` or no leading zeros) into u128; used by the **authoritative** budget identity `u128(after) − u128(before) = parse_u128(draws)`.

```pseudocode
function decimal_string_to_u128(s:string) -> (hi:u64, lo:u64)
  assert s != "" and all_digits(s)
  if length(s) > 1 and s[0]=='0': abort(E_U128_FORMAT)
  hi=0; lo=0
  for ch in s:
     d = ch - '0'
     (hi, lo) = mul_u128_by_small(hi, lo, 10)
     (hi, lo) = add_u128(hi, lo, d)
  return (hi, lo)
```

### B4. Tiny predicates used by S1 producers/validator

**Intent:** Encode S1’s branch rules and open-interval guard.

```pseudocode
function is_open_interval_01(u:f64) -> bool
  return (u > 0.0) and (u < 1.0)

function is_binary64_extreme01(pi:f64) -> bool
  return (pi == 0.0) or (pi == 1.0)    # exact binary64 equality
```

> Notes: `is_binary64_extreme01` uses **exact equality** by design (no epsilon); `is_open_interval_01` forbids endpoints. This mirrors S1’s deterministic/stochastic branch law and the strict-open `u01` map from S0.


### B5. `begin_event_micro(...) -> EventCtx`

**Intent:** Same as S0 `begin_event_ctx(...)`, but stamps **microsecond** `ts_utc` (S1 mandate). Pair with `end_event_emit(...)`.

```pseudocode
function begin_event_micro(module:string, substream_label:string,
                           seed:u64, parameter_hash:hex64, manifest_fingerprint:hex64, run_id:hex32,
                           stream:Stream) -> EventCtx
  return {
    ts_utc:               ts_utc_now_rfc3339_micro(),   # exactly 6 fractional digits (**truncate; no rounding**)
    module:               module,
    substream_label:      substream_label,
    seed:                 seed,
    parameter_hash:       parameter_hash,
    manifest_fingerprint: manifest_fingerprint,
    run_id:               run_id,
    before_lo:            stream.ctr.lo,
    before_hi:            stream.ctr.hi
  }
```

### B6. Saturating totals helpers (trace)

**Intent:** S1 trace uses **saturating** `uint64` totals.

```pseudocode
const UINT64_MAX = 18446744073709551615

function sat_add_u64(x:u64, y:u64) -> u64
  s = x + y
  if s < x: return UINT64_MAX
  return s

function u128_to_uint64_saturate(hi:u64, lo:u64) -> u64
  return (hi != 0) ? UINT64_MAX : lo
```

### B7. `update_rng_trace_totals(...) -> (draws_total:u64, blocks_total:u64, events_total:u64)`

**Intent:** Schema-accurate trace row with **microsecond** timestamp and **saturating u64 totals** (trace-only). Replaces the S0 “blocks-only” updater for S1 producers.  
**S1 contract:** totals **saturate** at `UINT64_MAX`; per-event deltas still use `u128_to_uint64_or_abort`. Do **not** use S0’s non-saturating totals updater here.

```pseudocode
# Schema anchor: schemas.layer1.yaml#/rng/core/rng_trace_log
# Partition keys: {seed, parameter_hash, run_id} (dictionary path). Embedded equality: row.seed == seed and row.run_id == run_id; **parameter_hash** is path-only.
# Payload literals: module, substream_label.
# Consumer selects the **final** row per (module, substream_label) as defined by the schema.

function update_rng_trace_totals(
    module:string, substream_label:string,
    seed:u64, parameter_hash:hex64, run_id:hex32,
    before_hi:u64, before_lo:u64, after_hi:u64, after_lo:u64,
    prev_draws_total:u64, prev_blocks_total:u64, prev_events_total:u64,
    draws_str:string) -> (u64, u64, u64)

  # 1) Counter delta → blocks (must fit u64 per single event)
  (dhi, dlo) = u128_delta(after_hi, after_lo, before_hi, before_lo)
  delta_blocks = u128_to_uint64_or_abort(dhi, dlo)

  # 2) Parse per-event draws (authoritative uniforms consumed)
  (draws_hi, draws_lo) = decimal_string_to_u128(draws_str)
  delta_draws = u128_to_uint64_or_abort(draws_hi, draws_lo)

  # 3) Saturating totals
  new_blocks_total = sat_add_u64(prev_blocks_total, delta_blocks)
  new_draws_total  = sat_add_u64(prev_draws_total,  delta_draws)
  new_events_total = sat_add_u64(prev_events_total, 1)

  # 4) Emit trace row (MICROsecond ts; **truncate**, exactly 6 digits; exact field names)
  row = {
    ts_utc:                  ts_utc_now_rfc3339_micro(),
    run_id:                  run_id,
    seed:                    seed,
    module:                  module,
    substream_label:         substream_label,
    draws_total:             new_draws_total,
    blocks_total:            new_blocks_total,
    events_total:            new_events_total,
    rng_counter_before_lo:   before_lo,
    rng_counter_before_hi:   before_hi,
    rng_counter_after_lo:    after_lo,
    rng_counter_after_hi:    after_hi,
    }
  
  path = dict_path_for_family("rng_trace_log", seed, parameter_hash, run_id)
  write_jsonl(path, row)

  return (new_draws_total, new_blocks_total, new_events_total)
```

---

## C) How S1 uses L0 (minimal guidance)

* **Event start:** use `begin_event_micro(...)` (not the nano variant) to satisfy S1’s **exactly 6 digits** rule.
* **Budget identity:** always compute `draws` as **decimal u128** via the existing encoder (or `"0"/"1"` for hurdle) and uphold
  `u128(after) − u128(before) = parse_u128(draws)` (with `decimal_string_to_u128`). For hurdle, also enforce `blocks == parse_u128(draws) ∈ {0,1}`.
* **Trace:** after `end_event_emit(...)`, call `update_rng_trace_totals(...)` once per event to reconcile **draws/blocks/events** totals (saturating).
* **Floats to JSON:** when building the **payload** (in L1), serialize `pi` and stochastic `u` with `f64_to_json_shortest` so they **round-trip** to the exact binary64.

---

### This L0 set is complete for S1

It reuses all S0-L0 primitives (Philox, substreams, open-interval uniforms, envelope writer, 128-bit math, Neumaier dot, two-branch logistic) and adds only the **minimal** helpers S1 mandates: microsecond timestamps, shortest round-trip float printer, u128 decimal parser, tiny predicates, and a schema-accurate saturating trace writer. All requirements come directly from the frozen S1 expansion (envelope, payload, budgeting, and trace semantics).
