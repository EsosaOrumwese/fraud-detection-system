# L0 — Primitives for 1A.S0 (Batches A–F)

> Source of truth: `/mnt/data/3rd-updated-expansion.applied.vfinal.txt`. This file is a **faithful, code-agnostic transcription** of the S0 primitives, grouped as Batches A–F. It removes ambiguity, fixes placement, and avoids duplication. All constants, names, and rules are normative.

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
      case "iso":           out = out || UER(id.value)       # ISO uppercased upstream in S0.1
      case "merchant_u64":  out = out || LE64(id.value)
      case "i":             out = out || LE32(id.value)
      case "j":             out = out || LE32(id.value)
      default:              abort_run("F2","ser_unsupported_id",{ tag: id.tag })
  return out
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
      if on_param: abort(E_PARAM_RACE, {path, s1, s2})
      else:        abort(E_ARTIFACT_RACE, {path, s1, s2})
  return d
```

### A3. Lineage key constructors

```text
# Canonical, tuple-hash, name-aware
function compute_parameter_hash(P_files):
  assert len(P_files) >= 1                  else abort(E_PARAM_EMPTY)
  assert all_ascii_unique_basenames(P_files) else abort(E_PARAM_NONASCII_NAME or E_PARAM_DUP_BASENAME)
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
  assert len(artifacts) >= 1      else abort(E_ARTIFACT_EMPTY)
  assert len(git32) == 32         else abort(E_GIT_BYTES)
  assert len(param_b32) == 32     else abort(E_PARAM_HASH_ABSENT)
  assert all_ascii_unique_basenames(artifacts) else abort(E_ARTIFACT_NONASCII_NAME or E_ARTIFACT_DUP_BASENAME)
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
function derive_run_id(fp_bytes, seed_u64, t_ns_u64, exists: fn(hex32)->bool) -> hex32:
  attempts = 0
  while true:
      payload = UER("run:1A") || fp_bytes || LE64(seed_u64) || LE64(t_ns_u64)
      r16     = SHA256(payload)[0:16]
      rid     = hex32(r16)
      if not exists(rid): return rid
      t_ns_u64 = t_ns_u64 + 1
      attempts = attempts + 1
      if attempts > 65536: abort(E_RUNID_COLLISION_EXHAUSTED, {seed_u64})
```
---

## Batch B — PRNG core & keyed substreams

Scope: master material (audit‑only), keyed substreams (order‑invariant), Philox block semantics & lane policy, strict‑open `(0,1)` mapping.

```text
# Audit-only master material; not used directly for draws
function derive_master_material(seed_u64, manifest_fingerprint_bytes):
  M = SHA256( UER("mlr:1A.master") || manifest_fingerprint_bytes || LE64(seed_u64) )  # 32 bytes
  root_key = LOW64(M)
  root_ctr = ( BE64(M[16:24]), BE64(M[24:32]) )
  return (M, root_key, root_ctr)

# Order-invariant substreams
function derive_substream(M, label: string, ids: tuple) -> Stream:
  msg = UER("mlr:1A") || UER(label) || SER(ids)        # no delimiters
  H   = SHA256( M || msg )                              # 32 bytes
  key = LOW64(H)
  ctr = ( BE64(H[16:24]), BE64(H[24:32]) )
  return Stream{ key, ctr }

struct Stream { key: u64, ctr: (u64 hi, u64 lo) }

# One Philox block; advance counter by +1 (unsigned 128-bit)
function philox_block(s: Stream) -> (x0:u64, x1:u64, s':Stream):
  (x0, x1) = PHILOX_2x64_10(s.key, s.ctr)
  s.ctr = add_u128(s.ctr.hi, s.ctr.lo, 1)
  return (x0, x1, s)

# Strict-open U(0,1) map (binary64, RNE)
function u01(x: u64) -> f64:
  const TWO_NEG_64    = 0x1.0000000000000p-64
  const ONE_MINUS_EPS = 0x1.fffffffffffffp-1
  u = ((as_f64(x) + 1.0) * TWO_NEG_64)
  return (u == 1.0) ? ONE_MINUS_EPS : u

# Single-uniform draw (enforces lane policy)
function uniform1(s: Stream) -> (u:f64, s':Stream, draws:uint128):
  (x0, x1, s1) = philox_block(s)   # advance exactly 1 block
  return (u01(x0), s1, 1)          # use low lane; discard high lane
```
---

## Batch C — Samplers & budgets

Scope: Box–Muller normal; Marsaglia–Tsang gamma (α≥1 and α<1 boosting); Poisson (inversion for λ<10; PTRS for λ≥10); ZTP wrapper; Gumbel key. Budgets are **actual uniforms consumed**.

```text
# Two uniforms from the same block (lane policy)
function uniform2(s: Stream) -> (u1:f64, u2:f64, s':Stream, draws:uint128):
  (x0, x1, s1) = philox_block(s)
  return (u01(x0), u01(x1), s1, 2)

# Box–Muller (no cache)
const TAU = 0x1.921fb54442d18p+2
function normal_box_muller(s: Stream) -> (Z:f64, s':Stream, draws:uint128):
  (u1, u2, s1, dU) = uniform2(s)              # draws=2 (1 block)
  r  = sqrt(-2.0 * ln(u1))
  th = TAU * u2
  Z  = r * cos(th)
  return (Z, s1, dU)

# Gamma (Marsaglia–Tsang), exact actual-use
function gamma_mt(alpha:f64, s:Stream) -> (G:f64, s':Stream, draws:uint128):
  if alpha >= 1.0:
      d = alpha - (1.0/3.0); c = 1.0 / sqrt(9.0 * d)
      total = 0; s1 = s
      loop:
          (Z, s1, dZ) = normal_box_muller(s1)    # +2 uniforms
          total += dZ
          v = (1.0 + c*Z); v = v*v*v
          if v <= 0.0: continue
          (U, s1, dU) = uniform1(s1)             # +1 uniform
          total += dU
          if ln(U) < 0.5*Z*Z + d - d*v + d*ln(v):
              return (d*v, s1, total)
  else:
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
  assert hi == 0 and lo <= UINT64_MAX, "F4d:rng_budget_violation"
  return lo
```

### D1. Run-scoped RNG audit row (pre-draw)

```text
function emit_rng_audit_row(seed:u64,
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
    notes:                notes
  }
  write_jsonl("logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl", row)
```

### D2. Event envelope writer (authoritative counters & budgets)

```text
function begin_event(module:string, substream_label:string,
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
  draws_dec  = u128_to_decimal_string(draws_hi, draws_lo)

  if draws_hi==0 and draws_lo==0:
     assert after_hi==ctx.before_hi and after_lo==ctx.before_lo, "non_consuming_counter_change"

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

### D3. Per-(module,label) RNG trace (cumulative **blocks**) — **DEPRECATED**
> DEPRECATED: This writer is schema-mismatched and retained temporarily for compatibility.
> Use **D3b.update_rng_trace_totals(...)** instead (emits draws_total/blocks_total/events_total).

```text
function update_rng_trace(module:string, substream_label:string,
                          seed:u64, parameter_hash:hex64, run_id:hex32,
                          before_hi:u64, before_lo:u64, after_hi:u64, after_lo:u64,
                          prev_blocks_total:u64) -> u64:
  (dhi, dlo) = u128_delta(after_hi, after_lo, before_hi, before_lo)
  delta_u64  = u128_to_uint64_or_abort(dhi, dlo)
  new_total  = prev_blocks_total + delta_u64
  assert new_total >= prev_blocks_total, "trace_monotone_violation"
  row = {
    ts_utc:                  ts_utc_now_rfc3339_micro(),
    run_id:                  run_id,
    seed:                    seed,
    module:                  module,
    substream_label:         substream_label,
    # NOTE: DEPRECATED writer. Field name/type are NOT schema-compliant.
    #       Use D3b.update_rng_trace_totals(...) which emits draws_total/blocks_total/events_total.
    draws:                   new_total,
    rng_counter_before_lo:   before_lo, rng_counter_before_hi: before_hi,
    rng_counter_after_lo:    after_lo,  rng_counter_after_hi:  after_hi
  }
  write_jsonl("logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl", row)
  return new_total
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
  write_jsonl("logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl", row)
  return (new_blocks_total, new_draws_total, new_events_total)
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
  elif dataset_id == "validation_bundle_1A":
      expect = { "manifest_fingerprint": path_keys["manifest_fingerprint"] }
      got    = { "manifest_fingerprint": row_embedded["manifest_fingerprint"] }
  else:
      abort_run("F6","dictionary_path_violation", path_keys.seed, path_keys.parameter_hash, path_keys.manifest_fingerprint, path_keys.run_id, {dataset_id:dataset_id}, [])
  if expect != got:
      abort_run("F5","partition_mismatch", path_keys.seed, path_keys.parameter_hash, path_keys.manifest_fingerprint, path_keys.run_id, {dataset_id:dataset_id, expected:expect, embedded:got}, [])
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
  write_json(tmp + "failure.json", hdr)
  write_json(tmp + "_FAILED.SENTINEL.json", hdr)
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
---

## Z. I/O shims (utility; non-normative signatures)

```text
function write_jsonl(path_template: string, row: object):
  # Implementation-specific JSONL append or rotate.

function open_partitioned_writer(dataset_id: string, partition: map<string,string>) -> Writer:
  # Returns object with .write(row) and .close(); must enforce embedded lineage == path keys.

function dict_path_for_family(family:string, seed:u64, parameter_hash:hex64, run_id:hex32) -> path:
  spec = DICTIONARY.get(family)       # authoritative mapping from vocab → path template
  assert spec is not None, "E_DICT_FAMILY_UNKNOWN"
  return fill_template(spec.path_template, { seed: seed, parameter_hash: parameter_hash, run_id: run_id })
```

> **Serialization note (normative):** Envelope fields carry **numeric values**; byte order (LE/BE) applies only to **derivation** steps (hashing, key/counter construction), never to JSON serialization.