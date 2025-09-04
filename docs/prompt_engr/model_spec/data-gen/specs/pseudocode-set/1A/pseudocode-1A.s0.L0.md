# L0 — Primitives for 1A.S0 (Batches A–F)

> Source of truth: `state.1A.s0.expanded.md`. This file is a **faithful, code-agnostic transcription** of the S0 primitives, grouped as Batches A–F. It removes ambiguity, fixes placement, and avoids duplication. All constants, names, and rules are normative.

## S0–L0 Non-regression Invariants (MUST NOT CHANGE)

This header freezes invariants that MUST remain true. Any change requires an explicit version bump + re-validation.

H4 — run_id scope & loop bound
- run_id is a log partitioner ONLY; it MUST NOT influence RNG or model outputs.  
- Uniqueness domain is exactly {seed, parameter_hash}.  
- Bounded uniqueness loop MUST abort at attempts >= 65536 (i.e., ≤ 65,536 tries total).

H5 — SER typed-ID rules
- SER(ids) MUST uppercase ISO deterministically before UER and assert ASCII.  
- Indices i, j MUST be unsigned LE32 with 0 ≤ value ≤ 2^32−1; out-of-range aborts.

H6 — Event envelope “draws”
- draws MUST equal the sampler’s actual uniform count for that event (decimal uint128 string).  
- Non-consuming events (draws == 0) MUST NOT advance the counter (before == after).  
- blocks come ONLY from 128-bit counter deltas; no padding draws.

Carry-over criticals (already fixed; do not regress)
- Timestamps for audit/events/trace: RFC-3339 UTC with exactly 6 fractional digits (microseconds).  
- RNG audit row MUST include: algorithm="philox2x64-10", rng_key_{hi,lo}, rng_counter_{hi,lo}, and lineage keys.  
- Trace writer MUST emit integers: draws_total, blocks_total, events_total; legacy trace is DEPRECATED.

Change control
- Any edit touching these rules requires: (a) doc version bump, (b) updated schema if applicable, (c) L3 validation rerun.


---

## Batch A — Encoding, hashing, identifiers (pure bytes)

All functions below are **pure** and side-effect free unless noted. Hashes are **raw 32-byte SHA-256**; `||` is byte concatenation of already-encoded fields. Strings use the **Universal Encoding Rule (UER)**: UTF‑8 prefixed by **u32 little‑endian** length. Integers default to **LE64** unless a field specifies **LE32**. Arrays/sets are sorted as specified and concatenated—**no extra delimiters**.

### A1. Encoding helpers (UER + hex + typed-id serialization)

```text
# UER encoders (normative)
function enc_str(s: string) -> bytes:
  b = utf8(s)
  return LE32(len(b)) || b                       # length prefix is u32 little-endian

function enc_u64(x: u64) -> bytes:
  return LE64(x)

# Preferred alias
function UER(s: string) -> bytes:
  return enc_str(s)

# Hex helpers (32- and 16-byte digests)
function hex64(b32: bytes[32]) -> ascii[64]:
  return lower_hex_zero_left_padded(b32)         # 64 chars, no "0x"

function hex32(b16: bytes[16]) -> ascii[32]:
  return lower_hex_zero_left_padded(b16)         # 32 chars, no "0x"

# Basename guards & ordering
function all_ascii_unique_basenames(file_list: list[(basename, path)]) -> bool:
  # TRUE iff each basename is ASCII-only and there are no duplicates.

function sort_by_basename_ascii(file_list) -> list[(basename, path)]:
  # Return list sorted by bytewise ASCII lexicographic order of basename.

# Exact byte picks
function LOW64(b32: bytes[32]) -> u64:
  # Return bytes 24..31 of b32 interpreted as LE u64 (normative).
  return LE64(b32[24:32])

function BE64(s8: bytes[8]) -> u64:
  # Interpret 8-byte slice as big-endian u64 (normative).
  return u64_from_be_bytes(s8)

# Typed ID serializer for substreams (order-preserving; schema-driven)
# Allowed tags and encodings:
#   iso (uppercase ASCII)         -> UER(iso)
#   merchant_u64 (u64)            -> LE64(value)
#   i (u32), j (u32)              -> LE32(value)
function SER(ids: tuple) -> bytes:
  out = ""
  for id in ids:
    switch id.tag:
      case "iso":
        v = to_ascii_uppercase(id.value)                     # normalize deterministically
        assert is_ascii(v) else fail_F2("ser_iso_non_ascii",{ value: id.value })
        out = out || UER(v)  
      case "merchant_u64":  out = out || LE64(id.value)
      case "i":
        assert (id.value >= 0 and id.value <= 0xFFFFFFFF)
          else fail_F2("ser_index_out_of_range",{ tag:"i", value: id.value })
        out = out || LE32(id.value)
      case "j":
        assert (id.value >= 0 and id.value <= 0xFFFFFFFF)
          else fail_F2("ser_index_out_of_range",{ tag:"j", value: id.value })
        out = out || LE32(id.value)
      default:              fail_F2("ser_unsupported_id",{ tag: id.tag })
  return out
```

### A1b. Pure-L0 failure raiser (typed, no side-effects)

```text
# L0 pure helpers MUST NOT write failure bundles. They raise a typed Error that L2 catches
# and maps to abort_run(...). This keeps A2–A4 side-effect free.
struct Error { failure_class: string, failure_code: string, detail: any }

function fail_F2(code: string, detail: any) -> never:
  raise Error{ failure_class: "F2", failure_code: code, detail: detail }
```

### A2. Streaming file SHA-256 with race-guard (exact bytes)

```text
function sha256_stream(path: string, on_param: bool) -> bytes[32]:
  s1 = stat(path)                          # (size, mtime)
  H  = sha256_begin()
  for chunk in read_binary_stream(path):
      sha256_update(H, chunk)
  d  = sha256_finalize(H)                  # 32 bytes (raw)
  s2 = stat(path)
  if s1 != s2:
      if on_param: fail_F2("param_race",    { path: path, before: s1, after: s2 })
      else:        fail_F2("artifact_race", { path: path, before: s1, after: s2 })
  return d
```

### A3. Lineage key constructors

```text
# Canonical, tuple-hash, name-aware
function compute_parameter_hash(P_files):
  assert len(P_files) >= 1                  else fail_F2("param_empty", { files: len(P_files) })
  assert all_ascii_unique_basenames(P_files) else fail_F2("basenames_invalid_or_duplicate",
                                                          { where: "parameters" })
  
  # Invariant: ASCII-sort basenames; tuple = SHA256(UER(name)||digest); NO XOR; final = SHA256(concat tuples).
  files = sort_by_basename_ascii(P_files)
  tuples = []
  for (name, path) in files:
      d = sha256_stream(path, on_param=true)     # 32 bytes
      t = SHA256( UER(name) || d )               # 32 bytes
      tuples.append(t)
  C  = concat(tuples)                             # 32·n bytes
  Hb = SHA256(C)                                  # 32 bytes
  Hx = hex64(Hb)
  return (Hx, Hb)

# Sorted tuple-hash over opened artefacts + commit + parameter bundle
function compute_manifest_fingerprint(artifacts, git32, param_b32):
  assert len(artifacts) >= 1                  else fail_F2("artifact_empty", { count: 0 })
  assert len(git32) == 32                     else fail_F2("git32_invalid", { got_len: len(git32) })
  assert len(param_b32) == 32                 else fail_F2("param_hash_absent", { got_len: len(param_b32) })
  assert all_ascii_unique_basenames(artifacts) else fail_F2("basenames_invalid_or_duplicate",
                                                            { where: "artifacts" })
  # Invariant: artefacts are those opened pre-S0.2; ASCII sort basenames; U=concat(tuple-hashes)||git32||param_b32; final SHA256(U).
  arts = sort_by_basename_ascii(artifacts)
  parts = []
  for (name, path) in arts:
      d = sha256_stream(path, on_param=false)     # 32 bytes
      t = SHA256( UER(name) || d )               # 32 bytes
      parts.append(t)
  U  = concat(parts) || git32 || param_b32
  Fb = SHA256(U)                                  # 32 bytes
  Fx = hex64(Fb)
  return (Fx, Fb)

# Log-only run id (UER payload; bounded uniqueness loop)
# NOTE: run_id is a log partitioner only and MUST NOT influence RNG or outputs.
#       Uniqueness is within the {seed, parameter_hash} scope.
function derive_run_id(fp_bytes, seed_u64, t_ns_u64, exists: fn(hex32)->bool) -> hex32:
  attempts = 0
  while true:
      payload = UER("run:1A") || fp_bytes || LE64(seed_u64) || LE64(t_ns_u64)
      r16     = SHA256(payload)[0:16]
      rid     = hex32(r16)
      if not exists(rid): return rid
      t_ns_u64 = t_ns_u64 + 1
      attempts = attempts + 1
      if attempts >= 65536:
          fail_F2("runid_collision_exhausted", { seed: seed_u64, attempts: attempts })
```

### A4. Merchant scalar derivation (canonical)

```text
# Canonical scalar: LOW64(SHA256(LE64(id64))) — stable across languages.
function merchant_u64_from_id64(id64: u64) -> u64:
  b8  = LE64(id64)        # little-endian 8-byte encoding (normative)
  h32 = SHA256(b8)        # 32 raw bytes
  return LOW64(h32)       # bytes 24..31 as LE u64
```

### A5. Tiny string/anchor predicates (cross-state reuse)

```text
# ASCII substring predicate (bytewise).
function contains_text(haystack: string, needle: string) -> bool:
  return ascii_index_of(haystack, needle) >= 0

# JSON-Schema ref MUST be a local anchor like "schemas.X.yaml#/path"
function is_jsonschema_anchor(ref: string) -> bool:
  return contains_text(ref, "schemas.") and contains_text(ref, ".yaml#/")
```

---

## Batch B — PRNG core & keyed substreams

Scope: master material (audit‑only), keyed substreams (order‑invariant), Philox block semantics & lane policy, strict‑open `(0,1)` mapping.

```text
# Audit-only master material; not used directly for draws
function derive_master_material(seed_u64, manifest_fingerprint_bytes):
  # Invariant: domain UER("mlr:1A.master"); key=LOW64(M); ctr=(BE64(M[16:24]), BE64(M[24:32])).
  M = SHA256( UER("mlr:1A.master") || manifest_fingerprint_bytes || LE64(seed_u64) )  # 32 bytes
  root_key = LOW64(M)
  root_ctr = ( BE64(M[16:24]), BE64(M[24:32]) )
  return (M, root_key, root_ctr)

# Order-invariant substreams
function derive_substream(M, label: string, ids: tuple) -> Stream:
  # Invariant: msg = UER("mlr:1A") || UER(label) || SER(ids); no delimiters; LOW64/BE64 slices are fixed.
  # SER(ids) contract: indices are LE32, 0-based, unsigned; any ISO code in ids MUST be UPPERCASE ASCII before UER (§S0.3.3).
  # SER v1 accepts only tags {iso, merchant_u64, i, j}; any other tag MUST fail_F2("ser_unsupported_id").
  msg = UER("mlr:1A") || UER(label) || SER(ids)        # no delimiters
  H   = SHA256( M || msg )                              # 32 bytes
  key = LOW64(H)
  ctr = ( BE64(H[16:24]), BE64(H[24:32]) )
  return Stream{ key, ctr }

struct Stream { key: u64, ctr: (u64 hi, u64 lo) }

# One Philox block; advance counter by +1 (unsigned 128-bit)
function philox_block(s: Stream) -> (x0:u64, x1:u64, s':Stream):
  (x0, x1) = PHILOX_2x64_10(s.key, s.ctr)
  # Invariant: advance by exactly +1 block per call.
  s.ctr = add_u128(s.ctr.hi, s.ctr.lo, 1)
  return (x0, x1, s)

# Strict-open U(0,1) map (binary64, RNE)
function u01(x: u64) -> f64:
  const TWO_NEG_64    = 0x1.0000000000000p-64
  const ONE_MINUS_EPS = 0x1.fffffffffffffp-1
  # Invariant: u ∈ (0,1). Use binary64 hex-literal mapping u=((as_f64(x)+1.0)*0x1.0000000000000p-64); never compute 1/(2^64+1).
  # Binary64 note: if u rounds to 1.0, remap to 0x1.fffffffffffffp-1.
  u = ((as_f64(x) + 1.0) * TWO_NEG_64)
  return (u == 1.0) ? ONE_MINUS_EPS : u

# Single-uniform draw (enforces lane policy)
function uniform1(s: Stream) -> (u:f64, s':Stream, draws:uint128):
  (x0, x1, s1) = philox_block(s)   # advance exactly 1 block
  # Invariant: use LOW lane only; budget=1.
  return (u01(x0), s1, 1)          # use low lane; discard high lane
```
---

## Batch C — Samplers & budgets

Scope: Box–Muller normal; Marsaglia–Tsang gamma (α≥1 and α<1 boosting); Poisson (inversion for λ<10; PTRS for λ≥10); ZTP wrapper; Gumbel key. Budgets are **actual uniforms consumed**.

```text
# Two uniforms from the same block (lane policy)
function uniform2(s: Stream) -> (u1:f64, u2:f64, s':Stream, draws:uint128):
  (x0, x1, s1) = philox_block(s)
  # Invariant: consume both lanes from one block; budget=2.
  return (u01(x0), u01(x1), s1, 2)

# Box–Muller (no cache)
const TAU = 0x1.921fb54442d18p+2
function normal_box_muller(s: Stream) -> (Z:f64, s':Stream, draws:uint128):
  (u1, u2, s1, dU) = uniform2(s)              # draws=2 (1 block)
  # Invariant: exactly two uniforms; no cache/reuse; budget propagated verbatim.
  r  = sqrt(-2.0 * ln(u1))
  th = TAU * u2
  Z  = r * cos(th)
  return (Z, s1, dU)

# Gamma (Marsaglia–Tsang), exact actual-use
function gamma_mt(alpha:f64, s:Stream) -> (G:f64, s':Stream, draws:uint128):
  if alpha >= 1.0:
      # Invariant: per loop +2 (BM) then +1 (uniform) when accept; returns actual total.
      d = alpha - (1.0/3.0); c = 1.0 / sqrt(9.0 * d)
      total = 0; s1 = s
      loop:
          (Z, s1, dZ) = normal_box_muller(s1)    # +2 uniforms
          total += dZ
          v = (1.0 + c*Z); v = v*v*v
          if v <= 0.0: continue
          (U, s1, dU) = uniform1(s1)             # +1 uniform
          total += dU
          if ln(U) < 0.5*Z*Z + d - d*v + d*ln(v):  # spec choice: strict '<' (not '≤'); validators must match this L0 behavior.
              return (d*v, s1, total)
  else:
      # Invariant: Case-B uses Γ(α+1) then +1 uniform; returns actual total.
      (Gp, s1, dY) = gamma_mt(alpha + 1.0, s)
      (U,  s1, dU) = uniform1(s1)
      return (Gp * pow(U, 1.0/alpha), s1, dY + dU)

# Poisson: inversion (<10) / PTRS (>=10)
function poisson_inversion(lambda:f64, s:Stream) -> (K:int, s':Stream, draws:uint128):
  L = exp(-lambda); k = 0; p = 1.0; total = 0; s1 = s
  loop:
      (u, s1, dU) = uniform1(s1); total += dU
      p = p * u
      if p <= L: return (k, s1, total)
      k = k + 1

function poisson_ptrs(lambda:f64, s:Stream) -> (K:int, s':Stream, draws:uint128):
  b  = 0.931 + 2.53*sqrt(lambda)
  a  = -0.059 + 0.02483*b
  inv_alpha = 1.1239 + (1.1328 / (b - 3.4))
  v_r = 0.9277 - (3.6224 / (b - 2))
  # Invariant: consumes 2 uniforms per attempt via uniform2; constants are algorithmic, not configurable.
  total = 0; s1 = s
  loop:
      (u, v, s1, dUV) = uniform2(s1); total += dUV
      if (u <= 0.86) and (v <= v_r):
          k = floor((b*v)/u + lambda + 0.43); return (k, s1, total)
      u_s = 0.5 - abs(u - 0.5)
      k   = floor(((2.0*a)/u_s + b) * v + lambda + 0.43)
      if k < 0: continue
      lhs = ln( (v * inv_alpha) / (a/(u_s*u_s) + b) )
      rhs = -lambda + k*ln(lambda) - lgamma(k + 1.0)
      if lhs <= rhs: return (k, s1, total)

function poisson(lambda:f64, s:Stream) -> (K:int, s':Stream, draws:uint128):
  # Invariant: split threshold is λ★=10.0 (exact).
  if lambda < 10.0: return poisson_inversion(lambda, s)
  else:             return poisson_ptrs(lambda, s)

# ZTP wrapper (sampler only; caller logs non-consuming events)
function poisson_ztp(lambda:f64, s:Stream) -> (K:int, s':Stream, draws:uint128, exhausted:bool):
  total = 0; s1 = s
  for tries in 0..63:
      (k, s1, d) = poisson(lambda, s1); total += d
      if k > 0: return (k, s1, total, false)
  return (0, s1, total, true)

# Gumbel key
function gumbel_key(s:Stream) -> (g:f64, s':Stream, draws:uint128):
  (u, s1, dU) = uniform1(s)
  return (-ln(-ln(u)), s1, dU)
```
---

## Batch D — RNG envelope, audit & trace

Counters are **128‑bit** `(hi, lo)`; **blocks = after − before**; **draws = uniforms consumed** (decimal `uint128` string). JSON fields are numeric; endianness applies only to derivations.

### D0. 128-bit helpers & timestamp

```text
const UINT64_MAX = 18446744073709551615

function ts_utc_now_rfc3339_nano() -> string:
  # e.g., "2025-04-15T12:34:56.123456789Z" (UTC)

function ts_utc_now_rfc3339_micro() -> string:
  # RFC-3339 with exactly 6 fractional digits (UTC), e.g. "2025-04-15T12:34:56.123456Z"
  # Implementation note: round/truncate to microseconds; never emit 3/7/9 digits.
  # Used by RNG audit row, event envelopes, and trace rows in S0.

# Unsigned 128-bit delta: (after_hi,after_lo) - (before_hi,before_lo)
function u128_delta(ahi:u64, alo:u64, bhi:u64, blo:u64) -> (hi:u64, lo:u64):
  if alo >= blo:
     lo = alo - blo; hi = ahi - bhi
  else:
     lo = (alo + 2^64) - blo; hi = (ahi - 1) - bhi
  return (hi, lo)

# Increment 128-bit counter by small u64 increment (typically 1)
function add_u128(c_hi:u64, c_lo:u64, inc:u64) -> (u64 hi2, u64 lo2):
  lo2   = c_lo + inc
  carry = (lo2 < c_lo) ? 1 : 0
  hi2   = c_hi + carry
  return (hi2, lo2)

# Decimal encoder for non-negative 128-bit integer
function u128_to_decimal_string(hi:u64, lo:u64) -> string:
  # Deterministic base-1e19 chunking or repeated div/mod 10; no locale.

function u128_to_uint64_or_abort(hi:u64, lo:u64) -> u64:
  assert hi == 0 and lo <= UINT64_MAX, "F4c:rng_counter_mismatch"
  return lo
```

### D1. Run-scoped RNG audit row (pre-draw)

```text
function emit_rng_audit_row(seed:u64,
  # NOTE: S0 audit/trace/events MUST use ts_utc_now_rfc3339_micro(); failures use now_ns().
                            parameter_hash:hex64,
                            manifest_fingerprint:hex64,
                            run_id:hex32,
                            rng_key_hi:u64, rng_key_lo:u64,
                            rng_counter_hi:u64, rng_counter_lo:u64,
                            build_commit:string,
                            code_digest:hex64|null,
                            hostname:string|null,
                            platform:string|null,
                            notes:string|null):
  row = {
    ts_utc:               ts_utc_now_rfc3339_micro(),
    run_id:               run_id,
    seed:                 seed,
    manifest_fingerprint: manifest_fingerprint,
    parameter_hash:       parameter_hash,
    algorithm:            "philox2x64-10",
    rng_key_lo:           rng_key_lo,
    rng_key_hi:           rng_key_hi,
    rng_counter_lo:       rng_counter_lo,
    rng_counter_hi:       rng_counter_hi,
    build_commit:         build_commit,
    code_digest:          code_digest,
    hostname:             hostname,
    platform:             platform,
    # Invariant: follow schema field names strictly; do not emit any 'code_version' field.
    notes:                notes
  }
  path = dict_path_for_family("rng_audit_log", seed, parameter_hash, run_id)
  write_jsonl(path, row)
```

### D2. Event envelope writer (authoritative counters & budgets)

```text
function begin_event_ctx(module:string, substream_label:string,
                         seed:u64, parameter_hash:hex64, manifest_fingerprint:hex64, run_id:hex32,
                         stream:Stream) -> EventCtx:
  return {
    ts_utc:  ts_utc_now_rfc3339_micro(),
    module:  module,
    substream_label: substream_label,
    seed:    seed,
    parameter_hash:       parameter_hash,
    manifest_fingerprint: manifest_fingerprint,
    run_id:  run_id,
    before_hi: stream.ctr.hi, before_lo: stream.ctr.lo
  }

function end_event_emit(family:string, ctx:EventCtx, stream_after:Stream,
                        draws_hi:u64, draws_lo:u64, payload:object):
  after_hi = stream_after.ctr.hi
  after_lo = stream_after.ctr.lo
  (dhi, dlo) = u128_delta(after_hi, after_lo, ctx.before_hi, ctx.before_lo)
  blocks_u64 = u128_to_uint64_or_abort(dhi, dlo)
  # Guard MUST sit at emit-time: blocks must fit into uint64 or abort (F4d). Never cast elsewhere.
  # Normative: 'draws' MUST equal the sampler's actual uniform count for this event.
  # Producers (L1) must pass the exact count; this writer serializes it verbatim.
  draws_dec  = u128_to_decimal_string(draws_hi, draws_lo)

  if draws_hi==0 and draws_lo==0:
     assert after_hi==ctx.before_hi and after_lo==ctx.before_lo, "non_consuming_counter_change"
  # Optional sanity: zero-draw events must not advance the counter (covered above);
  # any further equality checks are enforced by the validator against family budgets.

  row = {
    ts_utc:                   ctx.ts_utc,
    module:                   ctx.module,
    substream_label:          ctx.substream_label,
    seed:                     ctx.seed,
    parameter_hash:           ctx.parameter_hash,
    manifest_fingerprint:     ctx.manifest_fingerprint,
    run_id:                   ctx.run_id,
    rng_counter_before_lo:    ctx.before_lo, rng_counter_before_hi: ctx.before_hi,
    rng_counter_after_lo:     after_lo,      rng_counter_after_hi:  after_hi,
    blocks:                   blocks_u64,
    draws:                    draws_dec,
    ...payload
  }
  path = dict_path_for_family(family, ctx.seed, ctx.parameter_hash, ctx.run_id)
  write_jsonl(path, row)
```

### D2b. Event+Trace glue (convenience)

```text
# Minimal cumulative trace state used by producers.
struct TraceState { blocks_total:u64, draws_total:u64, events_total:u64 }

# Emit the event row, then advance cumulative totals (schema-compliant).
function end_event_and_trace(family, ctx, stream_after, draws_hi:u64, draws_lo:u64, payload:object, trace:TraceState) -> TraceState:
  end_event_emit(family, ctx, stream_after, draws_hi, draws_lo, payload)   # D2
  (b,d,e) = update_rng_trace_totals(
              ctx.module, ctx.substream_label,
              ctx.seed, ctx.parameter_hash, ctx.run_id,
              ctx.before_hi, ctx.before_lo, stream_after.ctr.hi, stream_after.ctr.lo,
              draws_hi, draws_lo,
              trace.blocks_total, trace.draws_total, trace.events_total)   # D3b
  return TraceState{ blocks_total:b, draws_total:d, events_total:e }
```

### D3. Per-(module,label) RNG trace (cumulative **blocks**) — **REMOVED (use `D3b.update_rng_trace_totals`)**
> DEPRECATED: This writer is schema-mismatched and retained temporarily for compatibility.
> Use **D3b.update_rng_trace_totals(...)** instead (emits draws_total/blocks_total/events_total).

```text
function update_rng_trace(module:string, substream_label:string,
  # REMOVED: schema-mismatched; do not use this writer. Use D3b.update_rng_trace_totals(...) instead.
  fail_F2("deprecated_trace_writer_removed",{ module: module, substream_label: substream_label })
                          seed:u64, parameter_hash:hex64, run_id:hex32,
                          before_hi:u64, before_lo:u64, after_hi:u64, after_lo:u64,
                          prev_blocks_total:u64) -> u64:
```

### D3b. Per-(module,label) RNG trace — **schema-compliant totals** (blocks/draws/events)

```text
# New, spec-compliant writer. Does not replace D3 yet to avoid breaking existing L1 code paths.
# Emits cumulative integers: draws_total, blocks_total, events_total.
function update_rng_trace_totals(module:string, substream_label:string,
                                 seed:u64, parameter_hash:hex64, run_id:hex32,
                                 before_hi:u64, before_lo:u64, after_hi:u64, after_lo:u64,
                                 event_draws_hi:u64, event_draws_lo:u64,
                                 prev_blocks_total:u64, prev_draws_total:u64, prev_events_total:u64)
                                 -> (u64 new_blocks_total, u64 new_draws_total, u64 new_events_total):
  (dhi, dlo) = u128_delta(after_hi, after_lo, before_hi, before_lo)
  delta_blocks  = u128_to_uint64_or_abort(dhi, dlo)
  inc_draws_u64 = u128_to_uint64_or_abort(event_draws_hi, event_draws_lo)
  new_blocks_total = prev_blocks_total + delta_blocks
  new_draws_total  = prev_draws_total + inc_draws_u64
  new_events_total = prev_events_total + 1
  assert new_blocks_total >= prev_blocks_total, "trace_monotone_violation"
  assert new_draws_total  >= prev_draws_total, "trace_monotone_violation"
  row = {
    ts_utc:                  ts_utc_now_rfc3339_micro(),
    run_id:                  run_id,
    seed:                    seed,
    module:                  module,
    substream_label:         substream_label,
    draws_total:             new_draws_total,
    blocks_total:            new_blocks_total,
    events_total:            new_events_total,
    rng_counter_before_lo:   before_lo, rng_counter_before_hi: before_hi,
    rng_counter_after_lo:    after_lo,  rng_counter_after_hi:  after_hi
  }
  path = dict_path_for_family("rng_trace_log", seed, parameter_hash, run_id)
  write_jsonl(path, row)
  return (new_blocks_total, new_draws_total, new_events_total)
```

### D4. RNG event wrappers (library; S0 does not call these)

```text
# ZTP rejection (non-consuming): before==after, blocks=0, draws="0".
function event_ztp_rejection(module:string, trace:TraceState, meta, before:Stream, after:Stream) -> TraceState:
  ctx = begin_event_ctx(module, "ztp_rejection", meta.seed, meta.parameter_hash, meta.fingerprint, meta.run_id, before)
  return end_event_and_trace("rng_event_ztp_rejection", ctx, after, 0, 0, { context:"ztp_rejection" }, trace)

# ZTP retry exhausted after 64 zeros (non-consuming).
function event_ztp_retry_exhausted(module:string, trace:TraceState, meta, before:Stream, after:Stream) -> TraceState:
  ctx = begin_event_ctx(module, "ztp_retry_exhausted", meta.seed, meta.parameter_hash, meta.fingerprint, meta.run_id, before)
  return end_event_and_trace("rng_event_ztp_retry_exhausted", ctx, after, 0, 0, { context:"ztp_retry_exhausted", attempts:64 }, trace)

# Box–Muller event wrapper: consumes exactly 2 uniforms (1 block); discard sine mate.
function event_normal_box_muller(module:string, trace:TraceState, meta) -> (Z:f64, stream:Stream, new_trace:TraceState):
  s0  = derive_substream(meta.master, "normal_box_muller", meta.ids)   # L0 A2
  ctx = begin_event_ctx(module, "normal_box_muller", meta.seed, meta.parameter_hash, meta.fingerprint, meta.run_id, s0)
  (Z, s1, draws) = normal_box_muller(s0)                               # L0 C
  nt = end_event_and_trace("rng_event_normal_box_muller", ctx, s1, 0, draws, { z: Z }, trace)
  return (Z, s1, nt)
```

---

## Batch E — Numeric policy primitives (bit-stable math)

Pinned environment: IEEE‑754 **binary64**, **RNE**, **FMA off**, **no FTZ/DAZ**, deterministic libm (incl. `lgamma`).

```text
# Neumaier compensated sum (fixed order)
function sum_neumaier(xs: iterable<f64>) -> f64:
  s = 0.0; c = 0.0
  for x in xs:
      y = x - c
      t = s + y
      c = (t - s) - y
      s = t
  return s

# Dot with Neumaier (fixed index order)
function dot_neumaier(a: f64[], b: f64[]) -> f64:
  assert len(a) == len(b)
  s = 0.0; c = 0.0
  for i in 0 .. len(a)-1:
      y = a[i]*b[i] - c
      t = s + y
      c = (t - s) - y
      s = t
  return s

# Total-order key (non-NaN domain; -0.0 before +0.0)
function total_order_key(x: f64, secondary) -> (u64, any):
  assert not isNaN(x)
  bits = u64_from_f64(x)
  key  = (bits & 0x8000000000000000) ? (~bits) : (bits | 0x8000000000000000)
  return (key, secondary)

# Branch-stable logistic
function logistic_branch_stable(eta:f64) -> f64:
  if eta >= 0.0:
    z = exp(-eta); return 1.0 / (1.0 + z)
  else:
    z = exp(eta);  return z / (1.0 + z)
```
---

## Batch F — Validation gate, atomic publish, lineage checks, abort

These shims are used by S0.10 and failure handling. They also define **time** and **file** helpers used across L1.

### F0. Tiny utilities

```text
# UTC epoch nanoseconds (unsigned 64-bit). Implementation-defined; monotone within process.
function now_ns() -> u64:
  return system_epoch_utc_nanoseconds()

# ASCII lexicographic directory listing (filenames only)
function list_ascii_sorted(dir: path) -> list<string>:
  # Deterministic bytewise ASCII order.

# Concatenate raw bytes of inputs and return SHA-256 (32 raw bytes)
function sha256_concat_bytes(files: list<path>) -> bytes[32]:
  # Reads each file as raw bytes, in the given order.
```

### F1. Validation gate hash (`_passed.flag`)

```text
function write_passed_flag(tmp_dir: path):
  files = list_ascii_sorted(tmp_dir)
  inputs = [ tmp_dir+"/"+f for f in files if f != "_passed.flag" ]
  H = sha256_concat_bytes(inputs)
  write_text(tmp_dir+"/_passed.flag", "sha256_hex = " + hex64(H) + "\n")
```

### F2. Atomic publish (fingerprint-scoped)

```text
function publish_atomic(tmp_dir: path, final_dir: path):
  mkdirs(parent(final_dir))
  atomic_rename(tmp_dir, final_dir)   # single rename(2)
```

### F3. Partition/lineage equivalence check (dictionary-backed)

```text
# Dataset scope lists used to validate partition/row lineage equivalence.
# S0 (L0) has no parameter-scoped datasets; RNG log-scoped are the two below.
const PARAMETER_SCOPED = ["crossborder_eligibility_flags","hurdle_pi_probs"]
const RNG_LOG_SCOPED   = ["rng_audit_log","rng_trace_log"]
```

```text
function verify_partition_keys(dataset_id: string,
                               path_keys: map<string,string|u64>,
                               row_embedded: map<string,string|u64>):
  if dataset_id in PARAMETER_SCOPED:
      expect = { "parameter_hash": path_keys["parameter_hash"] }
      got    = { "parameter_hash": row_embedded["parameter_hash"] }
  elif dataset_id in RNG_LOG_SCOPED:
      expect = { "seed": path_keys["seed"],
                 "parameter_hash": path_keys["parameter_hash"],
                 "run_id": path_keys["run_id"] }
      got    = { "seed": row_embedded["seed"],
                 "parameter_hash": row_embedded["parameter_hash"],
                 "run_id": row_embedded["run_id"] }
  elif dataset_id.starts_with("rng_event_"):
      expect = { "seed": path_keys["seed"],
                 "parameter_hash": path_keys["parameter_hash"],
                 "run_id": path_keys["run_id"] }
      got    = { "seed": row_embedded["seed"],
                 "parameter_hash": row_embedded["parameter_hash"],
                 "run_id": row_embedded["run_id"] }
  elif dataset_id == "validation_bundle_1A":
      expect = { "manifest_fingerprint": path_keys["manifest_fingerprint"] }
      got    = { "manifest_fingerprint": row_embedded["manifest_fingerprint"] }
  else:
      abort_run("F6","dictionary_path_violation",
                row_embedded["seed"], row_embedded["parameter_hash"], row_embedded["manifest_fingerprint"], row_embedded["run_id"],
                { dataset_id: dataset_id, path_keys: path_keys, row_embedded: row_embedded }, [])
   if expect != got:
      abort_run("F5","partition_mismatch",
                row_embedded["seed"], row_embedded["parameter_hash"], row_embedded["manifest_fingerprint"], row_embedded["run_id"],
                { dataset_id: dataset_id, expected: expect, embedded: got, path_keys: path_keys }, [])
```

### F4. Deterministic run-abort

```text
function abort_run(failure_class: string, failure_code: string,
                   seed: u64, parameter_hash: hex64, manifest_fingerprint: hex64, run_id: hex32,
                   detail: object,
                   partial_partitions: list<{dataset_id, partition_path, reason}>):
  base = "data/layer1/1A/validation/failures/" +
         "fingerprint="+manifest_fingerprint+"/seed="+stringify(seed)+"/run_id="+run_id+"/"
  tmp = base + "_tmp." + uuid4()
  mkdirs(tmp)
  hdr = {
    "failure_class": failure_class,
    "failure_code":  failure_code,
    "ts_utc":        now_ns(),
    "seed":          seed,
    "parameter_hash": parameter_hash,
    "manifest_fingerprint": manifest_fingerprint,
    "run_id":        run_id,
    "detail":        detail
  }
  write_json(tmp + "/failure.json", hdr)
  write_json(tmp + "/_FAILED.SENTINEL.json", hdr)
  rename_atomic(tmp, base)    # atomic seal

  for p in partial_partitions:
      write_json(p.partition_path + "/_FAILED.json", {
        "dataset_id": p.dataset_id, "partition_keys": p.partition_path, "reason": p.reason })

  freeze_rng_for_run(seed, parameter_hash, run_id)
  terminate_process_nonzero()
```

### F5. Compatibility alias (for legacy call sites)

```text
function abort(...args):
  return abort_run(...args)
```

### F6. Failure payload builder (canonical shape)

```text
# ctx MUST supply: state, module, parameter_hash (hex64), manifest_fingerprint (hex64),
# seed (u64), run_id (hex32), and a typed 'detail' object per the spec tables.
function build_failure_payload(failure_class, failure_code, ctx):
  assert failure_class in {"F1","F2","F3","F4","F5","F6","F7","F8","F9","F10"}
  return {
    "failure_class":        failure_class,             # F1..F10
    "failure_code":         failure_code,              # snake_case
    "state":                ctx.state,                 # e.g., "S0.3"
    "module":               ctx.module,                # e.g., "1A.S0.rng"
    "dataset_id":           ctx.dataset_id or null,    # optional
    "merchant_id":          ctx.merchant_id or null,   # optional
    "parameter_hash":       ctx.parameter_hash,        # hex64
    "manifest_fingerprint": ctx.manifest_fingerprint,  # hex64
    "seed":                 ctx.seed,                  # u64
    "run_id":               ctx.run_id,                # hex32
    "ts_utc":               now_ns(),            # u64 epoch ns (normative)
    "detail":               ctx.detail                 # typed minima per spec
  }
```

### F7. Payload-based abort (compat wrapper)

```text
# Wrapper for sites that already assemble the payload; forwards to F4.abort_run.
function abort_run_atomic(payload, partial_partitions):
  return abort_run(payload.failure_class, payload.failure_code,
                   payload.seed, payload.parameter_hash, payload.manifest_fingerprint, payload.run_id,
                   payload.detail, partial_partitions)
```

### F8. Merchant soft-abort log (parameter-scoped)

```text
# Only call in states that explicitly allow "merchant-abort" (soft) in their spec.
# rows: iterable of {merchant_id, state, module, reason, ts_utc=epoch_ns()}
function merchant_abort_log_write(rows, parameter_hash):
  w = open_partitioned_writer("prep/merchant_abort_log", partition={"parameter_hash": parameter_hash})
  for r in rows:
    row = {
      "parameter_hash": parameter_hash,   # embed equals path key
      "merchant_id":    r.merchant_id,
      "state":          r.state,
      "module":         r.module,
      "reason":         r.reason,
      "ts_utc":         r.ts_utc          # epoch ns for consistency
    }
    assert w.write(row)
  w.close()
```

### F9. Reconciliation hook (end-of-state spot check)

```text
# Optional producer-side check mirroring validator logic: ensure per-(module,label)
# cumulative **blocks** and **draws** equal the sums in this state slice.
function reconcile_trace_vs_events(module, substream_label,
                                   events_blocks_sum:uint64, last_trace_blocks_total:uint64,
                                   events_draws_sum:uint64,  last_trace_draws_total:uint64):
  assert last_trace_blocks_total == events_blocks_sum, "rng_trace_reconcile_failed_blocks"
  assert last_trace_draws_total  == events_draws_sum,  "rng_trace_reconcile_failed_draws"
```

---

## Z. I/O shims (utility; non-normative signatures)

```text
# ---- Minimal dictionary of known families (authoritative names) ----
# Exact IDs come from the dataset_dictionary / registry for S0 (RNG audit/trace)
# and the generic events rule matches all rng_event_* families.  See:
#  - rng_audit_log, rng_trace_log (log-scoped) … per spec & dictionary.
#  - rng_event_* families route under logs/rng/events/{family}/… (generic rule).
const DICTIONARY = {
  "rng_audit_log": {
     path_template: "logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl"
  },
  "rng_trace_log": {
     path_template: "logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl"
  }
}

# ---- Template filler (deterministic token substitution; no normalization) ----
function fill_template(tmpl:string, vars: map<string,any>) -> string:
  out = tmpl
  for (k,v) in vars:
     out = out.replace("{"+k+"}", stringify(v))
  return out

# ---- Paths for RNG/event families ----
function dict_path_for_family(family:string, seed:u64, parameter_hash:hex64, run_id:hex32) -> path:
  spec = DICTIONARY.get(family)
  if spec is not None:
     return fill_template(spec.path_template, { seed: seed, parameter_hash: parameter_hash, run_id: run_id })
  # Generic mapping for *any* rng_event_* dataset id:
  if family.starts_with("rng_event_"):
     event = family.substring(len("rng_event_"))   # e.g., "hurdle_bernoulli"
     tmpl  = "logs/rng/events/{event}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl"
     return fill_template(tmpl.replace("{event}", event),
                          { seed: seed, parameter_hash: parameter_hash, run_id: run_id })
  # Pure helper: signal dictionary miss; the orchestrator will attach lineage via abort_run(...)
  fail_F2("dictionary_family_unknown", { family: family })

# ---- Writers (append/partition) — host-provided, no semantics beyond bytes ----
function write_jsonl(path_template: string, row: object):
  # Host appends a single JSON object as one line, choosing/rotating the concrete file
  # from the template if it contains 'part-*.jsonl'. No normalization of fields/keys.

function open_partitioned_writer(dataset_id: string, partition: map<string,string>) -> Writer:
  # Returns object with .write(row) and .close(); must enforce embedded lineage == path keys.
  # (L0/L1 verify equality via verify_partition_keys(...); host only provides the handle.)

# ---- Small file I/O helpers used by L0 (abort/publish) ----
function write_json(path: string, obj: object):
  # Host writes JSON atomically at 'path'. No key reordering, ASCII/UTF-8 only.

function write_text(path: string, text: string):
  # Host writes exact text bytes (UTF-8) atomically at 'path'.

function mkdirs(path: string):
  # Host creates all missing parent directories (idempotent).

function parent(path: string) -> string:
  # Host returns the parent directory of 'path'.

function uuid4() -> string:
  # Host returns a random UUID v4 string for temp directories/names.

function atomic_rename(src: string, dst: string):
  # Host must implement an atomic move (POSIX rename(2)-semantics).
  # On success, 'dst' becomes visible atomically; on failure, nothing is published.

function rename_atomic(src: string, dst: string):
  # Compatibility alias; some L0 sections call 'rename_atomic', others 'atomic_rename'.
  return atomic_rename(src, dst)

# ---- Deterministic bookkeeping hook (no effect on RNG semantics) ----
function freeze_rng_for_run(seed:u64, parameter_hash:hex64, run_id:hex32):
  # Optional, host-implemented; may persist a tiny note for forensics.
  # MUST NOT advance RNG or change any counters/keys; no-op is acceptable.
```

> **Serialization note (normative):** Envelope fields carry **numeric values**; byte order (LE/BE) applies only to **derivation** steps (hashing, key/counter construction), never to JSON serialization.

## L0 Capsule Appendix (Normative)

### A. Bytes, hex, and bit-casts (normative)

**A1. Encodings**

* **ASCII** = 7-bit US-ASCII. Reject bytes outside `[0x00..0x7F]` where ASCII is required.
* **UTF-8** for arbitrary strings.
* **Hex**: lowercase, even length, no prefix. Parse pairs into bytes; emit pairs per byte (00…ff).

**A2. Endianness primitives**

* `LE16/LE32/LE64(x)`: encode unsigned integer `x` as little-endian bytes of that width; on decode, interpret bytes as little-endian to an **unsigned** integer of that width; reject overflow.
* `BE64(x)`: same, big-endian 64-bit.
* **Casting vs encoding**:

  * *Encoding* produces/consumes a byte string and is endianness-defined (LE/BE).
  * *Bit-cast* preserves raw bit pattern across same-width scalar types (e.g., `u64_bits_to_f64`), **no arithmetic conversion**.

**A3. Bit-cast rules (IEEE-754)**

* `u64_bits_to_f64(b: uint64) -> float64`: reinterpret `b` as the IEEE-754 bit pattern of a `double` (no change). Inverse: `f64_bits_to_u64(d) -> uint64`. NaNs preserved bit-exactly. Denormals permitted.

**A4. Test vectors (must pass)**

1. `LE32(0x78563412) = 12 34 56 78` (bytes shown hex).
2. Decode `BE64("0000000000000001") = 1`.
3. `f64_bits_to_u64(u64_bits_to_f64(0x3ff0000000000000)) = 0x3ff0000000000000` (that pattern is `+1.0`).

---

### B. SHA-256 contracts (one-shot & stream)

**B1. One-shot**

* `sha256(bytes) -> 32 raw bytes`.
* Hex form is lowercase hex of those 32 bytes.

**B2. Streaming**

* `sha256_init()`, `sha256_update(ctx, bytes)`, `sha256_final(ctx)`.
* **Equivalence**: concatenating updates is exactly equivalent to hashing concatenated bytes once.

**B3. Test vectors (must pass)**

* `SHA256("") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. ([NIST Computer Security Resource Center][1], [di-mgt.com.au][2])
* `SHA256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`. ([NIST Computer Security Resource Center][1], [di-mgt.com.au][2])
* Stream equivalence: `update("ab"), update("c")` then `final` **==** one-shot `"abc"` (same digest above).

---

### C. Philox2×64-10 reference core (normative)

**C1. Purpose & domain**
We use **Philox 2×64 with 10 rounds** as a keyed bijection on two 64-bit words. Each call maps `(ctr0, ctr1, key0)` → `(out0, out1)`. Arithmetic is **unsigned modulo 2^64**; multiplications compute both low and high halves.

**C2. Constants**

* **Multiplier** `M0 = 0xD2B74407B1CE6E93` (64-bit).
* **Weyl** (round key increment) `W = 0x9E3779B97F4A7C15` (64-bit).
  These are the standard constants for Philox2x64; the round schedule is: `k_q = k_0 + q*W (mod 2^64)`, for rounds `q=0..9`. (The 4×64 constants listed in WG21 P2075 are different and not used here.) ([thesalmons.org][3])

**C3. Round function (one round `q`)**

```
# Inputs: (x0, x1) 64-bit words; round key k_q (64-bit)
hi, lo = mul128(x1, M0)          # hi = ⌊x1*M0 / 2^64⌋, lo = (x1*M0 mod 2^64)
x0', x1' = hi ^ x0 ^ k_q, lo     # XOR is bitwise on 64-bit words
```

Apply permutation for n=2: **identity** (no swap) per WG21 wording for n=2. Do this for `q=0..9` with `k_q = (k_0 + q*W) mod 2^64`. Final output is `(x0, x1)` after the 10th round. ([open-std.org][4])

**C4. Counter/key mapping from Stream**

* Given `Stream{key: u64, ctr: u128}`, map `ctr` → two 64-bit words **little-endian**:
  `ctr0 = low64(ctr)`, `ctr1 = high64(ctr)`. Key `k_0 = key`. (Matches L0 stream definition.)

**C5. 128-bit counter increment**
After consuming **one Philox block**, add `1` to the 128-bit counter (see Section D).

**C6. Known-Answer Tests (KATs)**
To prevent drift, implementations **MUST** match Random123’s *Known-Answer Tests* for **philox2x64-10**. Use the official `examples/kat_vectors` file from Random123; filter rows whose method is Philox2x64 with 10 rounds and verify the exact `(counter, key) → (answer)` tuples. These vectors are the industry reference and byte-order independent. ([thesalmons.org][5])

> **Example sources (citations; not runtime dependencies):** Random123 “Known Answer Tests” documentation and KAT files. ([thesalmons.org][5])

*Note:* We cite the KAT corpus rather than re-copying; the harness will load a small subset (2–3 tuples) into L3 to assert exact bit-for-bit agreement.

---

### D. 128-bit add (counter math)

**D1. Addition**
`add128((hi, lo), 1)` = `(hi', lo')` where `lo' = lo + 1 (mod 2^64)` and `hi' = hi + carry` with `carry = 1 if lo == 0xFFFFFFFFFFFFFFFF else 0`.

**D2. Test vectors**

1. `(0x0000...0000, 0xffffffffffffffff) + 1 = (0x0000...0001, 0x0000000000000000)`.
2. `(0xDEAD_BEEF_0000_0001, 0xFFFFFFFFFFFFFFFE) + 1 = (0xDEAD_BEEF_0000_0001, 0xFFFFFFFFFFFFFFFF)`.
3. Then `+1` again → `(0xDEAD_BEEF_0000_0002, 0x0000000000000000)`.

---

### E. Open-interval U(0,1) mapping (exact)

Given a 64-bit uniform `x` (low lane), compute:

```
u = ((as_f64(x) + 1.0) * 0x1.0000000000000p-64)    # binary64 hex-literal scale
```

This is strictly in `(0,1)` (never 0, never 1). If your FP unit rounds `u==1.0` by accident, clamp to `nextafter(1.0, -∞)` as a **defensive** guard (should be unreachable).

**Tests**

* `x=0 → u = 0x1.0000000000000p-64`.
* `x=2^64−1 → u == 1.0 → remapped to 0x1.fffffffffffffp-1`.

---

### F. Clock: `now_ns` contract

* Returns **monotonic** time since an arbitrary epoch, **nanoseconds**, `uint64` modulo wrap.
* Must not go backwards during a run. OK to differ from wall clock.
* `ts_utc_now_rfc3339_micro/nano`: Use UTC wall clock; format per RFC-3339; fractional part exactly 6 or 9 digits.

**Tests**

1. `ts_utc_now_rfc3339_micro()` matches regex: `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$`.
2. Two successive `now_ns()` calls are non-decreasing (allow equality).
3. `now_ns()` to RFC-3339 via wall-clock is **not** required; they are separate APIs.

---

#### F1. RFC-3339 microsecond formatting capsule (clarification; test-pinned)

**Scope.** Clarifies the exact steps for `ts_utc_now_rfc3339_micro()` used in audit/events/trace. This does **not** change behavior; it only removes latitude in host libraries.

**Algorithm (normative for this API):**
1) Read UTC wall-clock instant as `(secs:int64, nanos:int32)` where `secs` is seconds since Unix epoch and `0 ≤ nanos ≤ 999,999,999`.  
2) Derive calendar fields `(Y, M, D, h, m, s)` from `secs` using **UTC, proleptic Gregorian**; no locale/offsets.  
3) Compute `micro = floor(nanos / 1_000)` (i.e., **truncate** to microseconds; **no rounding**).  
4) Format exactly:
   - Year as 4+ ASCII digits (no sign for `Y ≥ 0000`).  
   - `-` separator, two-digit month/day; `T` between date/time.  
   - Two-digit hour/minute/second (00–59); leap seconds **not** represented.  
   - `.` followed by **exactly six** ASCII digits: `micro` **left-padded with zeros** to width 6.  
   - Literal `Z` suffix (no offsets permitted).  
5) The output is ASCII, e.g., `2025-09-03T14:07:59.123456Z`.

**Notes.**
- This capsule applies only to the **microsecond** variant used by S0. For any nano helper a host might carry, behavior is non-normative for S0; S0 does **not** require or consume 9-digit timestamps.

**Additional test (optional):**
- When `(secs, nanos) = (1_695_-example_, 123_456_789)`, output must be `… .123456Z` (truncated, not rounded).

---

### G. JSON & atomic rename contracts

**G1. JSON**

* Must be UTF-8, no BOM.
* Stable key ordering is **not required** unless specified in schema (L0 does not require sorting).
* Newlines: `\n`; indentation is not normative.

**G2. Atomic write-then-rename**

* Write to `tmp = "{dest}.tmp.{pid}.{random}"`.
* `fsync(tmp)`, then `rename(tmp, dest)` which must be **atomic** on target FS semantics.
* After rename, the final file is either the **old** or **new** version; never a torn mix.
* If `rename` cannot be atomic on platform, fall back to a durable **write to new inode** with `linkat+unlink` semantics to ensure atomic swap.

**Tests**

1. Crash between `fsync(tmp)` and `rename`: on restart, either old `dest` or intact `tmp` remains; recovery picks newest by mtime/size per your harness policy.
2. Concurrent writers serialized by your lock (outside L0 scope) produce one of the competing complete files, never partial JSON.

---

### H. Host Writer contract & row/partition invariants

**H1. Equality & partitioning invariants**

* **Row equality** = byte-for-byte equal **serialized** row payload.
* **Partitioning** keys: exactly the schema’s tuple (e.g., `{run_id, stream_label, counter_block}`) in the order specified. Two rows with the same partition key **must** land in the same shard/partition; different partition keys **must not** collide.

**H2. Flush & durability**

* `writer.append(row_bytes)` buffers; `writer.flush()` forces write+fsync (or equivalent) of all previously appended rows in that file segment.
* `writer.close()` implies `flush()`.

**H3. Idempotence**

* Re-appending the **same** row (same partition, same bytes) is tolerated and results in at most one visible copy in downstream dedupe (downstream policy), but the writer itself is allowed to emit duplicates—L0 only guarantees byte-stable rows and stable partitioning.

**Tests**

1. Two equal serialized rows appended in one session compare equal byte-wise (audit hash equal).
2. Partition key `(run_id="r", label="L", block=42)` maps to the same on-disk path on repeated runs with identical `run_id`.
3. `append`→crash→replay append of the same `row_bytes` does not change the bytes-on-disk for that row (dedupe downstream acceptable; writer idempotence by bytes).

---

### I. UER and SER (explicit byte layouts)

**I1. UER(domain: ASCII, label?: ASCII)**

* UER(dom) = `LE32(len(dom)) || dom_ascii_bytes`.
* UER(dom||label) = `LE32(len(dom))||dom||LE32(len(label))||label` (ASCII only; reject non-ASCII).

**I2. SER(ids)**

* Allowed tags and encodings (exactly these four; any other tag is unsupported):
  * **uint32 indices** (0-based): `LE32(i)` with assert `0 ≤ i ≤ 0xffffffff`.  
    Tags: `i`, `j`.
  * **ISO codes**: assert *uppercase ASCII*; then `LE32(len(bytes))||bytes`.  
    Tag: `iso`. (Normalization to uppercase occurs in A1.SER before UER.)
  * **Merchant identifier (u64)**: `LE64(value)`.  
    Tag: `merchant_u64`.
* Any other tag **MUST** raise `F2:ser_unsupported_id` (as in A1.SER).

**Tests**

1. `UER("mlr:1A") = 06 00 00 00 6d 6c 72 3a 31 41`.
2. `SER([i=0x00000005, iso="US"]) = 05 00 00 00 02 00 00 00 55 53`.
3. Lowercase ISO `"us"` → **normalized to "US"** (uppercased deterministically, then encoded).
4. `SER([{tag:"hex", value:"DEADBEEF"}])` ⇒ `F2:ser_unsupported_id`
---

### J. Master material & substream messages (hashing)

**J1. Master material**
`M = SHA256( UER("mlr:1A.master") || fingerprint_bytes || LE64(seed) )`. Keys via `LOW64(M or H)`, counters via `BE64(H[16:24]), BE64(H[24:32])`.
**Substream message** = `UER("mlr:1A") || UER(label) || SER(ids)` (exactly).

*This matches the spec and your L0 stream builder; keep the exact domain strings and byte slices.* ([thesalmons.org][6])

---

### K. Budget / counts agreement (reminder)

Event wrappers **must** pass the **actual** uniform counts (decimal u128 string) computed by kernels into the envelope’s `draws` field. L0 kernels already account precisely; ensure L1/L2 propagate the exact totals. (Authority for `blocks` is counter advancement; `draws` is uniform consumption.)

---

### L. Gamma accept inequality (pinning)

Gamma(MT) acceptance uses strict `<` in L0 (`ln U < …`). This is consistent with one branch of spec prose; we lock this choice to avoid ambiguity. (Measure-zero boundary; no effect on budgets.)

---

### M. Philox conformance harness (how to wire tests)

* L3 should include a tiny loader that reads **2–3** tuples from a **vendored** KAT file (checked-in) for each method (Philox, Threefry, ARS; the file contains all three families.) ([thesalmons.org][7])
* Keep these vectors separate from your own. Vendor a copy of the Random123 KAT file; treat it as the authoritative source (no network fetches). ([thesalmons.org][5])

---

### Why this closes the drift holes

* **Every primitive** used implicitly in L0 (encodings, endian, bit-casts, hashing, counter math, RNG core) now has unambiguous rules *and* a way to prove compliance (tests).
* **Philox** is specified down to constants, round math, and counter/key mapping, with a binding to the **Random123 KAT corpus** for numeric verification. That’s the industry’s reference set and avoids “home-made” vectors. ([thesalmons.org][5])
* **I/O semantics** (atomic rename, JSON constraints) and **writer invariants** are frozen, so host integration can’t pick incompatible defaults.

[1]: https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program/secure-hashing?utm_source=chatgpt.com "Secure Hashing - Cryptographic Algorithm Validation Program"
[2]: https://www.di-mgt.com.au/sha_testvectors.html?utm_source=chatgpt.com "Test vectors for SHA-1, SHA-2 and SHA-3"
[3]: https://www.thesalmons.org/john/random123/papers/random123sc11.pdf?utm_source=chatgpt.com "Parallel Random Numbers: As Easy as 1, 2, 3"
[4]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2075r3.pdf "P2075R3.docx"
[5]: https://www.thesalmons.org/john/random123/releases/latest/docs/ExamplesREADME.html "Random123-1.09: Examples, Tests and Benchmarks"
[6]: https://www.thesalmons.org/john/random123/releases/latest/docs/index.html "Random123-1.09: Random123: a Library of Counter-Based Random Number Generators"
[7]: https://www.thesalmons.org/john/random123/releases/1.04/docs/Release_01Notes.html?utm_source=chatgpt.com "Random123-1.04:"
