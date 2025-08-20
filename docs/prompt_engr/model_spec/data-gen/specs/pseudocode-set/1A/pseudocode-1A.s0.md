# L0 — Batch A primitives (Encoding, hashing, identifiers)

> All functions below are **pure** and side-effect free unless noted. Hashes are **raw 32-byte SHA-256**; `||` means byte concatenation of already-encoded fields. Hex encodings are lower-case, zero-left-padded, no `0x`. Strings use the **Universal Encoding Rule (UER)**: UTF-8 prefixed by **u32 little-endian** length. Integers are **LE64** unless a field specifies **LE32**. Arrays/sets are **sorted** (as specified) and concatenated—**no extra delimiters**.

---

## A1. Encoding helpers (UER + hex + byte picks)

```text
# UER encoders (normative)
function enc_str(s: string) -> bytes:
  b = utf8(s)
  return LE32(len(b)) || b                              # length prefix is u32 little-endian
  # No normalization, no path cleanup, case-sensitive.  # (spec)

function enc_u64(x: u64) -> bytes:
  return LE64(x)

# Hex helpers (32- and 16-byte digests)
function hex64(b32: bytes[32]) -> ascii[64]:
  return lower_hex_zero_left_padded(b32)                # 64 chars, no "0x" (spec)

function hex32(b16: bytes[16]) -> ascii[32]:
  return lower_hex_zero_left_padded(b16)                # 32 chars, no "0x" (spec)
```

*Notes (normative):* definition of SHA-256 digest as 32 raw bytes; hex rules; UER recap.

```text
# Basename guards + ordering
function all_ascii_unique_basenames(file_list: list[(basename, path)]) -> bool:
  # TRUE iff every basename is ASCII-only and there are no duplicates.
  # Abort on violation in callers with E_PARAM_* or E_ARTIFACT_* as appropriate. (spec)

function sort_by_basename_ascii(file_list) -> list[(basename, path)]:
  # Return list sorted by bytewise ASCII lexicographic order of basename. (spec)
```

*Notes (normative):* ASCII-only, unique basenames and ASCII sort are required for both parameter set 𝓟 and artefact set 𝓐.

```text
# Exact slice picks for counters/digests
function split64(b16: bytes[16]) -> (hi: u64, lo: u64):
  # Return big-endian words: hi = u64_be(b16[0:8]); lo = u64_be(b16[8:16]) (normative). 
  # Used wherever a 128-bit counter is obtained from SHA-256 bytes. (spec)
  # NB: Counters are handled as unsigned 128-bit arithmetic elsewhere.
```

*Note (normative):* `split64` definition and the “all counter math is unsigned 128-bit” rule.

```text
# merchant_id_text MUST be the exact UTF-8 byte sequence from ingress 'merchant_ids.merchant_id'.
function merchant_u64(merchant_id_text: string) -> u64:
  d = SHA256(utf8(merchant_id_text))             # 32 bytes
  return LOW64(d)                                # bytes 24..31, little-endian u64 (normative)
```

*Notes (normative):* Implements the S0.1 mapping. When used in SER(ids), encode the resulting u64 via **LE64**.
Endianness matters only in the `LOW64` slice; envelopes/log rows carry numeric values (no byte order).

---

## A2. Streaming file SHA-256 with race-guard (exact bytes)

```text
# Hash exact file bytes; protect against concurrent modification.
function sha256_stream(path: string, on_param: bool) -> bytes[32]:
  s1 = stat(path)                         # (size, mtime)
  H  = sha256_begin()
  for chunk in read_binary_stream(path):
      sha256_update(H, chunk)
  d  = sha256_finalize(H)                 # 32 bytes (raw)
  s2 = stat(path)
  if s1 != s2:
      # Deterministic handling per spec: re-read or fail. We choose fail to avoid drift.
      if on_param:
          abort(E_PARAM_RACE, {path, s1, s2})
      else:
          abort(E_ARTIFACT_RACE, {path, s1, s2})
  return d
```

*Notes (normative):* “Hash the **exact file bytes** in binary mode” and **race-guard**: `stat` before/after; if changed, re-read or fail with `E_PARAM_RACE` / `E_ARTIFACT_RACE`.

---

## A3. Lineage key constructors (parameter_hash, manifest_fingerprint, run_id)

### A3.1 `compute_parameter_hash` — canonical, tuple-hash, name-aware

```text
# Input: 𝓟 = governed parameter files (list of (basename, path))
# Output: (parameter_hash: hex64, parameter_hash_bytes: bytes[32])
function compute_parameter_hash(P_files):
  assert len(P_files) >= 1        else abort(E_PARAM_EMPTY)
  assert all_ascii_unique_basenames(P_files) else abort(E_PARAM_NONASCII_NAME or E_PARAM_DUP_BASENAME)
  files = sort_by_basename_ascii(P_files)

  tuples = []
  for (name, path) in files:
      d = sha256_stream(path, on_param=true)                 # 32 bytes
      t = SHA256( enc_str(name) || d )                       # 32 bytes (tuple includes name)
      tuples.append(t)

  C  = concat(tuples)                                        # 32·n bytes
  Hb = SHA256(C)                                             # parameter_hash_bytes (32)
  Hx = hex64(Hb)
  # (Callers emit param_digest_log + parameter_hash_resolved separately.)
  return (Hx, Hb)
```

*Notes (normative):* governed set 𝓟 basenames, tuple-hash including UER(name), ASCII sort, error codes, and storage effect (parameter-scoped partitioning).

---

### A3.2 `compute_manifest_fingerprint` — sorted tuple-hash over opened artefacts + commit + parameter bundle

```text
# Inputs:
#   artifacts = 𝓐 = all artefacts actually opened up to S0.2 (list of (basename, path))
#   git32     = 32 raw bytes of VCS commit (SHA-256 raw; or SHA-1 raw left-padded with 12 zero bytes)
#   param_b32 = parameter_hash_bytes (32 bytes)
# Output: (manifest_fingerprint: hex64, manifest_fingerprint_bytes: bytes[32])
function compute_manifest_fingerprint(artifacts, git32, param_b32):
  assert len(artifacts) >= 1        else abort(E_ARTIFACT_EMPTY)
  assert len(git32) == 32           else abort(E_GIT_BYTES)
  assert len(param_b32) == 32       else abort(E_PARAM_HASH_ABSENT)
  assert all_ascii_unique_basenames(artifacts) else abort(E_ARTIFACT_NONASCII_NAME or E_ARTIFACT_DUP_BASENAME)

  arts = sort_by_basename_ascii(artifacts)
  parts = []
  for (name, path) in arts:
      d = sha256_stream(path, on_param=false)                 # 32 bytes
      t = SHA256( enc_str(name) || d )                        # 32 bytes
      parts.append(t)

  U  = concat(parts) || git32 || param_b32
  Fb = SHA256(U)                                              # 32 bytes
  Fx = hex64(Fb)
  # (Callers emit manifest_fingerprint_resolved with git_commit_hex + counts.)
  return (Fx, Fb)
```

*Notes (normative):* **sorted tuple-hash (no XOR)**; artefact name+bytes via `T(a) = SHA256(UER(name)||D(a))`; `git_32` is raw (SHA-256 raw; or SHA-1 left-padded to 32 raw bytes); includes `parameter_hash_bytes`. Any change in bytes/basename/commit/param flips the fingerprint. Egress/validation **partition by** `fingerprint={manifest_fingerprint}` (often with `seed`).

---

### A3.3 `derive_run_id` — log-only, uniqueness-guarded

```text
# Inputs: manifest_fingerprint_bytes (32), seed (u64), start_time_ns (u64, UTC)
# Output: run_id (hex32)
# Scope: log partitions only {seed, parameter_hash, run_id}; must not influence modelling.
function derive_run_id(fp_bytes, seed_u64, t_ns_u64, exists: fn(hex32)->bool) -> hex32:
  attempts = 0
  while true:
      payload = enc_str("run:1A") || fp_bytes || LE64(seed_u64) || LE64(t_ns_u64)
      r16     = SHA256(payload)[0:16]            # first 16 bytes only
      rid     = hex32(r16)
      if not exists(rid):                         # check target log dir for {seed, parameter_hash}
          return rid
      t_ns_u64 = t_ns_u64 + 1                     # deterministic +1ns
      attempts = attempts + 1
      if attempts > 65536:
          abort(E_RUNID_COLLISION_EXHAUSTED, {seed_u64})
```

*Notes (normative):* UER payload; **bounded loop** (≤2¹⁶ attempts); **log-only** semantics; RNG seeding & outputs depend only on `(seed, parameter_hash, manifest_fingerprint)`.

---

## A4. Where these keys are used (for implementers wiring outputs)

* **Parameter-scoped** datasets (e.g., `crossborder_features`, `hurdle_pi_probs`) partition by `parameter_hash={parameter_hash}`.
* **Egress/validation** (e.g., `validation_bundle_1A`, `outlet_catalogue`) partition by `fingerprint={manifest_fingerprint}` (often alongside `seed`).
* **RNG logs** (`rng_audit_log`, `rng_trace_log`, `rng_event_*`) partition by `{ seed, parameter_hash, run_id }`.

*(Row-embedded lineage fields must equal their directory keys byte-for-byte; violations are F5 run-abort in validators.)*

---

## A5. Minimal failure surface (callers should use)

* From **parameter hash** path: `E_PARAM_EMPTY`, `E_PARAM_IO(name,errno)`, `E_PARAM_NONASCII_NAME`, `E_PARAM_DUP_BASENAME`, `E_PARAM_RACE`.
* From **fingerprint** path: `E_ARTIFACT_EMPTY`, `E_ARTIFACT_IO(name,errno)`, `E_ARTIFACT_NONASCII_NAME`, `E_ARTIFACT_DUP_BASENAME`, `E_GIT_BYTES`, `E_PARAM_HASH_ABSENT`, `E_ARTIFACT_RACE`.
* From **run_id**: `E_RUNID_COLLISION_EXHAUSTED` if uniqueness loop exceeds 2¹⁶.

---

Perfect—moving on to **Batch B**. I opened your frozen spec and translated only what it prescribes for the PRNG core & keyed substreams. This is a **single, self-contained L0 “Batch B” spec**: an implementer can transcribe it directly without guessing.

---

# L0 — Batch B primitives (PRNG core & keyed substreams)

> Scope: master material (audit-only), keyed substreams (order-invariant), Philox block semantics & lane policy, and the strict-open `(0,1)` uniform mapping. Counters are 128-bit `(hi, lo)`; envelopes serialize **numbers** (not byte slices).

## B1. Master material (audit-only; not used for draws)

```text
# Inputs: seed: u64 (from S0.2), manifest_fingerprint_bytes: bytes[32]
# Output: M: bytes[32], root_key: u64, root_ctr: (u64 hi, u64 lo)
function derive_master_material(seed_u64, manifest_fingerprint_bytes):
  M = SHA256( UER("mlr:1A.master") || manifest_fingerprint_bytes || LE64(seed_u64) )  # 32 bytes
  root_key = LOW64(M)                               # bytes 24..31 as LE u64
  root_ctr = ( BE64(M[16:24]), BE64(M[24:32]) )     # (hi, lo)
  return (M, root_key, root_ctr)
```

*Emit one **rng_audit_log** row with `(root_key, root_ctr)` **before any draw**; the root is **not** a draw source.*

## B2. Keyed, order-invariant substreams

```text
# Inputs:
#   M: bytes[32]        # from B1
#   ℓ: string           # event-family label, ASCII (e.g., "gumbel_key")
#   ids: tuple[...]     # ordered IDs, typed by schema:
#                       #   merchant_u64 → LE64
#                       #   iso (uppercase ISO-3166 alpha-2) → UER string
#                       #   indices i,j (0-based) → LE32
# Output:
#   Stream { key:u64, ctr:(u64 hi, u64 lo) }
function derive_substream(M, ℓ, ids) -> Stream:
  msg = UER("mlr:1A") || UER(ℓ) || SER(ids)   # no delimiters; ISO uppercased first
  H   = SHA256( M || msg )                     # 32 bytes
  key = LOW64(H)
  ctr = ( BE64(H[16:24]), BE64(H[24:32]) )
  return Stream{ key, ctr }
```

*Substreams are determined solely by `(seed, manifest_fingerprint, ℓ, ids)`, never by execution order/sharding.*

## B3. Philox block & lane policy

```text
struct Stream { key: u64, ctr: (u64 hi, u64 lo) }

# One Philox block; advances the 128-bit counter by +1 (unsigned add with carry)
function philox_block(s: Stream) -> (x0:u64, x1:u64, s':Stream):
  (x0, x1) = PHILOX_2x64_10(s.key, s.ctr)
  s.ctr = add_u128(s.ctr, 1)
  return (x0, x1, s)
```

**Lane policy (normative):**

* **Single-uniform events:** use **low lane** `x0`, **discard** `x1`; **advance 1 block**; `draws=1`.
* **Two-uniform events (e.g., Box–Muller):** use **both lanes of the same block**; **advance 1 block**; `draws=2`.
* **No caching** or reuse of lanes across events.

## B4. Strict-open `(0,1)` uniforms (binary64, RNE, no FMA)

```text
# Input: x : u64 (from a Philox lane)
# Output: u in (0,1) strictly
function u01(x: u64) -> f64:
  const TWO_NEG_64    = 0x1.0000000000000p-64     # exactly 2^-64
  const ONE_MINUS_EPS = 0x1.fffffffffffffp-1      # max < 1.0 (1 - 2^-53)
  u = ((as_f64(x) + 1.0) * TWO_NEG_64)
  return (u == 1.0) ? ONE_MINUS_EPS : u
```

*This mapping (plus the single-endpoint guard) enforces **strict** openness; do not compute reciprocals at runtime.*

## B5. One-uniform draw helper (encodes lane policy)

```text
# Single uniform draw per policy
function uniform1(s: Stream) -> (u:f64, s':Stream, draws:uint128):
  (x0, x1, s1) = philox_block(s)
  u = u01(x0)               # low lane only
  return (u, s1, 1)         # draws = 1; high lane discarded
```

*Envelope invariants later enforce `(blocks=1, draws=1)` for these families; counters/blocks are numeric fields in JSON.*

> **Serialization note (normative):** Envelope fields carry **numeric** values; byte-order (LE/BE) matters only during key/counter derivation. JSON writes the numbers themselves, never raw byte slices.

> **Authority note (normative):** Envelope `draws` is the single authoritative count of uniforms consumed. Only the families `gamma_component` and `dirichlet_gamma_vector` may include `payload.uniforms`, and if present it **must equal** `draws`. All other families MUST NOT include `payload.uniforms`.


---

### Why this is now airtight

* **Only** the frozen doc is referenced; every rule here (domain tags, encodings, lane policy, open-interval mapping, audit-before-draws) is pinned there.
* It keeps implementers from inventing: substreams are UER/SER with fixed types; blocks/lanes are unambiguous; `u01` cannot produce 0 or 1.

---

# L0 — Batch C primitives (Samplers & budgets)

> Scope: Box–Muller **normal**, Marsaglia–Tsang **gamma** (α≥1 and α<1 boosting), **Poisson** (inversion for λ<10; PTRS for λ≥10), **ZTP wrapper**, and the **Gumbel** key. All uniforms use the strict-open `u01` from Batch B; lane policy: one Philox **block** yields two lanes `(x0,x1)`; single-uniform families use **low** lane only and still advance **1 block**. Budgets below are **actual-use** uniforms—no padding.

> Numeric profile: binary64, round-to-nearest-ties-even, **FMA off**, no FTZ/DAZ; constants are hex-encoded; libm calls (log, sqrt, cos, lgamma, …) obey §S0.8.

---

## C0. Small helper (two uniforms from one block)

```text
# Draw two uniforms from a single Philox block (lane policy)
function uniform2(s: Stream) -> (u1: f64, u2: f64, s': Stream, draws: uint128):
  (x0, x1, s1) = philox_block(s)     # advance exactly 1 block
  return (u01(x0), u01(x1), s1, 2)   # two uniforms, same block
```

*Lane policy and block advance match §S0.3 PRNG notes; single-uniform families use low lane via `uniform1` (Batch B).*,

---

## C1. Standard normal $Z\sim\mathcal N(0,1)$ — Box–Muller (no cache)

**Constant (normative):** `TAU = 0x1.921fb54442d18p+2` (exact 2π in binary64). Computing `2*pi` at runtime is forbidden.

```text
function normal_box_muller(s: Stream) -> (Z: f64, s': Stream, draws: uint128):
  (u1, u2, s1, dU) = uniform2(s)                 # dU = 2 uniforms (1 block)
  r  = sqrt(-2.0 * ln(u1))
  th = TAU * u2
  Z  = r * cos(th)
  return (Z, s1, dU)                             # draws = 2 (no caching of the sine mate)
```

**Budget:** exactly **2 uniforms** per Z (1 block). **No caching**: the companion normal `r*sin(th)` is **discarded**. Envelope for any Box–Muller event MUST set `blocks=1` and `draws="2"`.

---

## C2. Gamma $\Gamma(\alpha,1)$ — Marsaglia–Tsang (exact actual-use)

> **Rule (normative):** Budgets record **exact** uniforms consumed—no padding. Normals come from C1 (two uniforms per normal). All uniforms use the open-interval map.

```text
function gamma_mt(alpha: f64, s: Stream) -> (G: f64, s': Stream, draws: uint128):
  if alpha >= 1.0:
      d = alpha - (1.0/3.0)
      c = 1.0 / sqrt(9.0 * d)
      total = 0
      s1 = s
      loop:
          (Z, s1, dZ) = normal_box_muller(s1)    # dZ = 2 uniforms; blocks += 1
          total += dZ
          v = (1.0 + c*Z); v = v*v*v
          if v <= 0.0:
              continue                           # no extra uniforms on this branch
          (U, s1, dU) = uniform1(s1)             # +1 uniform (low lane)
          total += dU
          if ln(U) < 0.5*Z*Z + d - d*v + d*ln(v):
              return (d*v, s1, total)            # exact actual-use count
  else:
      (Gp, s1, dY) = gamma_mt(alpha + 1.0, s)    # recurse to Case A
      (U,  s1, dU) = uniform1(s1)                # +1 uniform
      return (Gp * pow(U, 1.0/alpha), s1, dY + dU)
```

**Case A (α≥1) budget per accepted sample:** effectively `2A + B` uniforms, where `A` = # attempts (each attempt pays 2 uniforms for the normal) and `B` = # times step-2 passed (`v>0`, one on the accepted attempt). Implementation records **`total`** directly; there is **no fixed multiple**. **Case B (α<1):** budget = `draws(G') + 1`. **Dirichlet vectors:** sum component budgets; **no** extra uniforms to normalise.

---

## C3. Poisson $K\sim\text{Poisson}(\lambda)$ — inversion / PTRS split

**Threshold (normative):** $\lambda^\star = 10$. For $\lambda<10$ use **inversion**; for $\lambda\ge 10$ use **PTRS** (Hörmann transformed rejection).

### C3.a Inversion (λ < 10)

```text
function poisson_inversion(lambda: f64, s: Stream) -> (K: int, s': Stream, draws: uint128):
  L = exp(-lambda)
  k = 0; p = 1.0; total = 0; s1 = s
  loop:
      (u, s1, dU) = uniform1(s1)        # +1 uniform per iteration
      total += dU
      p = p * u
      if p <= L:
          return (k, s1, total)         # ≈ (K + 1) uniforms in expectation
      k = k + 1
```

**Budget:** variable; **log exact `total`** in the envelope’s `draws`.

### C3.b PTRS (λ ≥ 10)

**Constants (normative):**
$b = 0.931 + 2.53\sqrt{\lambda},\ \ a = -0.059 + 0.02483\,b,$
$\mathrm{inv}\,\alpha = 1.1239 + \frac{1.1328}{b-3.4},\ \ v_r = 0.9277 - \frac{3.6224}{b-2},\ \ u_{\text{cut}}=0.86.$

```text
function poisson_ptrs(lambda: f64, s: Stream) -> (K: int, s': Stream, draws: uint128):
  b  = 0.931 + 2.53*sqrt(lambda)
  a  = -0.059 + 0.02483*b
  inv_alpha = 1.1239 + (1.1328 / (b - 3.4))
  v_r = 0.9277 - (3.6224 / (b - 2))
  total = 0; s1 = s
  loop:
      (u, v, s1, dUV) = uniform2(s1)             # exactly 2 uniforms / attempt
      total += dUV                                # dUV = 2
      if (u <= 0.86) and (v <= v_r):
          k = floor((b*v)/u + lambda + 0.43)
          return (k, s1, total)
      u_s = 0.5 - abs(u - 0.5)
      k   = floor(((2.0*a)/u_s + b) * v + lambda + 0.43)
      if k < 0: continue
      lhs = ln( (v * inv_alpha) / (a/(u_s*u_s) + b) )
      rhs = -lambda + k*ln(lambda) - lgamma(k + 1.0)
      if lhs <= rhs:
          return (k, s1, total)                   # accepted
      # else repeat attempt
```

**Budget:** **exactly 2 uniforms per attempt**; repeat until acceptance. `ln`, `sqrt`, `lgamma` follow the pinned numeric profile (§S0.8).

### C3.c Dispatcher

```text
function poisson(lambda: f64, s: Stream) -> (K: int, s': Stream, draws: uint128):
  if lambda < 10.0:
      return poisson_inversion(lambda, s)
  else:
      return poisson_ptrs(lambda, s)
```

---

## C4. Zero-Truncated Poisson (ZTP) wrapper (sampler only)

```text
# Draw from Poisson(λ) conditioned on K > 0. Caller handles logging of
# non-consuming events; this helper only returns draws and an exhaustion flag.
function poisson_ztp(lambda: f64, s: Stream) -> (K: int, s': Stream, draws: uint128, exhausted: bool):
  total = 0; s1 = s
  for tries in 0..63:                               # hard cap: 64 zeros
      (k, s1, d) = poisson(lambda, s1)
      total += d
      if k > 0:
          return (k, s1, total, false)
      # else: continue (zero was rejected)
  # exhausted after 64 zeros
  return (0, s1, total, true)
```

**Spec notes:** ZTP **budgets are variable** and include **all uniforms across rejections**; `ztp_rejection`/`ztp_retry_exhausted` are **non-consuming** events (`blocks=0`, `draws="0"`), and exhaustion at 64 zeros branches per S4.

---

## C5. Gumbel key (for candidate ranking)

```text
function gumbel_key(s: Stream) -> (g: f64, s': Stream, draws: uint128):
  (u, s1, dU) = uniform1(s)                 # single-lane low; 1 block advanced
  g = -ln(-ln(u))
  return (g, s1, dU)                        # draws = 1
```

**Budget:** **1 uniform** per candidate. Ranking breaks ties by **(ISO, merchant_id)** in that order (sorted elsewhere).

---

### What this locks down (why implementers can’t “take initiative”)

* **Exact constants, domain tags, and lane usage** are pinned (no cached normals; PTRS always 2 uniforms/attempt).
* **Budgets are mechanical outputs** of these kernels (e.g., Gamma Case B = `draws(G′)+1`; Poisson PTRS = `2×attempts`). **No fixed multiples** are allowed when the spec says variable.
* **ZTP cap and non-consuming events** are explicit; this sampler returns an `exhausted` flag so callers can follow the S4 branch without inventing behavior.

---

# L0 / Batch D — RNG envelope, audit & trace (spec-true)

> Scope: audit row (run-scoped), per-event envelope writer, and the per-(module, substream) trace row. Counters are **Philox 2×64, 10 rounds**, with a **128-bit counter** exposed as `(hi, lo)` u64 words. “Blocks” = 128-bit counter delta; “draws” = **uniforms consumed** (decimal `uint128` string) per event. Trace aggregates **blocks** (uint64 practical bound).

## D0. Tiny helpers (128-bit arithmetic & encoding)

```text
const UINT64_MAX = 18446744073709551615  # schema width

fn ts_utc_now_rfc3339_nano() -> string
  # e.g. "2025-04-15T12:34:56.123456789Z" (UTC)
  # Implementation-defined; MUST be UTC with up to 9 fractional digits.

# Unsigned 128-bit delta: (after_hi,after_lo) - (before_hi,before_lo)
fn u128_delta(ahi:u64, alo:u64, bhi:u64, blo:u64) -> (carry:u64, lo:u64)
  if alo >= blo:
     lo = alo - blo
     hi = ahi - bhi
  else:
     lo = (alo + 2^64) - blo
     hi = (ahi - 1) - bhi
  return (hi, lo)  # 128-bit result split (hi, lo)

# Decimal encoder for a non-negative 128-bit integer (for event.draws)
fn u128_to_decimal_string(hi:u64, lo:u64) -> string
  # Repeated div/mod 10^n or base-1e19 chunks; deterministic, no locale.

# Cast 128-bit to uint64 with bound check (used for blocks / trace)
fn u128_to_uint64_or_abort(hi:u64, lo:u64)
  assert hi == 0 and lo <= UINT64_MAX, "F4d:rng_budget_violation"  # practical bound.
  return lo
```

## D1. Run-scoped RNG audit row (must be written **before any RNG event**)

**Schema & path:** `schemas.layer1.yaml#/rng/core/rng_audit_log` →
`logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`. Required fields include `{ts_utc, run_id, seed, manifest_fingerprint, parameter_hash, algorithm}` (value `"philox2x64-10"`), with optional platform notes. 

```text
fn emit_rng_audit_row(seed:u64,
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
    ts_utc:               ts_utc_now_rfc3339_nano(),
    run_id:               run_id,
    seed:                 seed,
    manifest_fingerprint: manifest_fingerprint,
    parameter_hash:       parameter_hash,
    algorithm:            "philox2x64-10",
    build_commit:         build_commit,
    code_digest:          code_digest,
    hostname:             hostname,
    platform:             platform,
    notes:                notes
    # If the schema variant includes key/counter exposure, include:
    # rng_key_hi: rng_key_hi, rng_key_lo: rng_key_lo,
    # rng_counter_hi: rng_counter_hi, rng_counter_lo: rng_counter_lo
  }
  write_jsonl("logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl", row)
```

*(The audit row is **run-scoped** and does not consume RNG. It establishes the algorithm, lineage, and—where present in the schema—the master key/counter exposure.)*

## D2. Per-event envelope writer (authoritative counters & budgets)

**Common envelope (normative fields):**

```
ts_utc, module, substream_label,
seed, parameter_hash, manifest_fingerprint, run_id,
rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo},
blocks:uint64, draws:string(uint128 decimal), payload:…
```

Field names/types come from `schemas.layer1.yaml#/rng_envelope` + each event’s schema; paths come from the dictionary (`logs/rng/events/{family}/seed=…/parameter_hash=…/run_id=…/part-*.jsonl`). 

```text
# Begin: capture 'before' from the substream (no IO)
fn begin_event(module:string, substream_label:string,
               seed:u64, parameter_hash:hex64, manifest_fingerprint:hex64, run_id:hex32,
               stream:Stream) -> EventCtx
  assert module ∈ VOCAB.modules and substream_label ∈ VOCAB.labels_for(module)  # per schemas catalog.
  return {
    ts_utc:  ts_utc_now_rfc3339_nano(),
    module, substream_label,
    seed, parameter_hash, manifest_fingerprint, run_id,
    before_hi: stream.ctr.hi, before_lo: stream.ctr.lo
  }

# End + emit: compute counters, blocks, encode draws as decimal uint128 string
fn end_event_emit(family:string, ctx:EventCtx, stream_after:Stream,
                  draws_u128_hi:u64, draws_u128_lo:u64,
                  payload:object):
  after_hi = stream_after.ctr.hi
  after_lo = stream_after.ctr.lo
  (dhi, dlo) = u128_delta(after_hi, after_lo, ctx.before_hi, ctx.before_lo)   # blocks = after - before (u128).
  blocks_u64 = u128_to_uint64_or_abort(dhi, dlo)                              # practical uint64 bound.
  draws_dec  = u128_to_decimal_string(draws_u128_hi, draws_u128_lo)           # decimal string (uniforms).

  # Non-consuming events must keep counters equal and blocks=0, draws="0".
  if draws_u128_hi==0 and draws_u128_lo==0:
     assert after_hi==ctx.before_hi and after_lo==ctx.before_lo, "non_consuming_counter_change"  # invariant.

  row = {
    ts_utc:                   ctx.ts_utc,
    module:                   ctx.module,
    substream_label:          ctx.substream_label,
    seed:                     ctx.seed,
    parameter_hash:           ctx.parameter_hash,
    manifest_fingerprint:     ctx.manifest_fingerprint,
    run_id:                   ctx.run_id,
    rng_counter_before_lo:    ctx.before_lo,
    rng_counter_before_hi:    ctx.before_hi,
    rng_counter_after_lo:     after_lo,
    rng_counter_after_hi:     after_hi,
    blocks:                   blocks_u64,
    draws:                    draws_dec,
    # Payload fields are flattened per-event schema; no name collisions allowed.
    ...payload
  }

  # Write to the event family’s JSONL stream (dictionary governs the exact path)
  path = dict_path_for_family(family, seed, ctx.parameter_hash, ctx.run_id)   # e.g., rng_event_gamma_component, rng_event_poisson_component…
  write_jsonl(path, row)
```

**Normative envelope rules encoded above:**

* `blocks = (after_hi,after_lo) − (before_hi,before_lo)` in **unsigned 128-bit arithmetic**; must fit `uint64` practical bound for a **single** event. 
* `draws` is **uniforms used** by that event, encoded as **decimal `uint128` string**; family budgets are checked against this.
* Single-uniform families: `(blocks=1, draws="1")`; Box–Muller: `(blocks=1, draws="2")`; **non-consuming**: `(blocks=0, draws="0")`.
* `module` and `substream_label` must come from the **event vocabulary** enumerated in the schema catalog; no free-text labels.

*(ZTP note: for `poisson_component(context="ztp")`, rejection bookkeeping events are **non-consuming** with `before==after`, `blocks=0`, `draws="0"`; the successful component event carries the actual sampler consumption. Hard cap 64 zero outcomes.)*

## D3. Per-(module, substream) RNG trace (cumulative **blocks**)

**Schema & path:** `schemas.layer1.yaml#/rng/core/rng_trace_log` →
`logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`. The **frozen spec** defines this as a **cumulative blocks** counter (uint64) reconciled against **sum of per-event `blocks`**. The practical bound is uint64; abort on overflow. 

```text
# Emit/refresh the cumulative trace for (module, substream_label)
# 'prev_blocks_total' is the last emitted total for this (module,label), or 0 if first.
fn update_rng_trace(module:string, substream_label:string,
                    seed:u64, parameter_hash:hex64, run_id:hex32,
                    before_hi:u64, before_lo:u64, after_hi:u64, after_lo:u64,
                    prev_blocks_total:u64) -> u64  # returns new total
  (dhi, dlo) = u128_delta(after_hi, after_lo, before_hi, before_lo)  # this-event blocks
  delta_u64  = u128_to_uint64_or_abort(dhi, dlo)                     # per-event bound
  new_total  = prev_blocks_total + delta_u64
  assert new_total >= prev_blocks_total, "trace_monotone_violation"   # monotone non-decreasing.

  row = {
    ts_utc:                  ts_utc_now_rfc3339_nano(),
    run_id:                  run_id,
    seed:                    seed,
    module:                  module,
    substream_label:         substream_label,
    # NOTE: The schema field name is 'draws:uint64'; per §S0.10.3 this row
    # aggregates **blocks**. Set it to 'new_total' for reconciliation.
    draws:                   new_total,                                 # cumulative blocks total (uint64).
    rng_counter_before_lo:   before_lo,
    rng_counter_before_hi:   before_hi,
    rng_counter_after_lo:    after_lo,
    rng_counter_after_hi:    after_hi
  }
  write_jsonl("logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl", row)
  return new_total
```

**Reconciliation contract (validators rely on this):**
For each `(module, substream_label)` within `{seed, parameter_hash, run_id}`, the **final** trace total must equal the **sum of per-event `blocks`** over the corresponding `rng_event_*` stream(s). Budget checks use **event `draws`**, not the trace.

---

## What implementers must *not* change

* Counter math is **unsigned 128-bit**; the two 64-bit words are just the serialization form.
* Event `draws` is a **decimal string** (not binary, not hex).
* Single-uniform events still advance **one whole block** and discard the high lane.
* Paths and partitions are **authoritative** in the dataset dictionary.

---

# L0 / Batch E — Numeric policy primitives (bit-stable math)

> **Environment (must hold for any decision/ordering math):** IEEE-754 **binary64**, **RNE** rounding, **FMA off**, **no FTZ/DAZ**, and a **deterministic libm profile** pinned in artefacts. Parallel reductions are **disallowed** for decision-critical paths. These rules are governed by `numeric_policy.json` and `math_profile_manifest.json`.

**Pinned libm functions (used by samplers & transforms):** `exp, log, log1p, expm1, sqrt, sin, cos, atan2, pow, tanh, erf (if used), lgamma` — all **bit-identical** under the selected profile; `sqrt` correctly rounded. (Ship vendored layer or pin exact build; record `math_profile_id`.)

---

## E1. Neumaier compensated sum (fixed order)

```text
# Sum over xs in their fixed iteration order using Neumaier compensation.
# Domain: binary64, RNE; must not parallelise.
function sum_neumaier(xs: iterable<f64>) -> f64:
  s = 0.0
  c = 0.0
  for x in xs:                  # fixed iteration order (spec-true)
      y = x - c
      t = s + y
      c = (t - s) - y
      s = t
  return s
```

*Exact kernel from §S0.8.10; mandated for any sum that feeds a decision or ordering.*

---

## E2. Dot product with Neumaier (fixed order)

```text
# Dot in fixed index order with Neumaier compensation.
# Domain: binary64, RNE; must not parallelise.
function dot_neumaier(a: f64[], b: f64[]) -> f64:
  assert len(a) == len(b)
  s = 0.0
  c = 0.0
  for i in 0 .. len(a)-1:       # fixed iteration order (spec-true)
      y = a[i]*b[i] - c
      t = s + y
      c = (t - s) - y
      s = t
  return s
```

*Exact kernel from §S0.8.10; BLAS/LAPACK **not** permitted on decision-critical paths.*

---

## E3. Total-order key for non-NaN floats

```text
# Monotone integer key for totalOrder on non-NaN binary64 floats.
# Guarantees: (-0.0) sorts before (+0.0); ties then break by 'secondary'.
function total_order_key(x: f64, secondary) -> (u64, any):
  assert not isNaN(x)                    # NaN forbidden (E_NUM_TOTORDER_NAN on violation)
  bits = u64_from_f64(x)                 # raw IEEE-754 bit pattern
  key  = (bits & 0x8000000000000000) ? (~bits) : (bits | 0x8000000000000000)
  return (key, secondary)                # use secondary (e.g., ISO then merchant_id)
```

*Bit mapping and tie-break rule are normative; this preserves numeric order and puts −0.0 before +0.0.*

---

## E4. Contracts these primitives rely on (no code to write)

* **Floating-point environment & flags:** binary64, RNE, **FMA off**, no FTZ/DAZ; compiler/interpreter flags pinned (e.g., `-ffp-contract=off`, `-fno-fast-math`). Violations abort with `E_NUM_*`.
* **Deterministic libm profile:** vendor/profile and digests are recorded in `math_profile_manifest.json` and included in S0.2’s artefact set (`math_profile_id` governs).
* **Tolerances & CI:** internal self-tests require **bit-exact** transcendentals under the profile and Neumaier audit success; external float32 reporting uses RN-even downcasts only where a state explicitly permits it.

---

### What this gives the implementer

* **One true** sum and dot kernels they must use anywhere results feed a branch/order.
* A **portable, total-order** key function for sorting floats with deterministic secondary tie-breakers (e.g., ISO → merchant_id).
* Clear dependence on the **pinned libm** and numeric environment; no opportunity to “take initiative.”

---

Perfect—here is **Batch F** as one self-contained, spec-true block drawn **only** from `3rd-updated-expansion.applied.vfinal.txt`. It defines the validation-gate hash, atomic publish, partition/lineage checks, and the deterministic abort routine—exactly as your frozen doc prescribes (no inventions).

---

# L0 / Batch F — Atomic publish, validation gate, lineage checks, abort

> Scope: helpers used by S0.10 (and writers generally) to (a) build and seal the **validation bundle** with a gate hash, (b) publish it atomically under the **fingerprint** partition, (c) verify **partition lineage** matches **embedded** lineage per the dictionary, and (d) perform a deterministic **run-abort** with the required artefacts.

---

## F0. Tiny utilities (normative behavior)

```text
# Return UTC epoch nanoseconds (unsigned 64-bit)
function now_ns() -> u64
  # Used for MANIFEST.created_utc_ns and failure.ts_utc.
  # Must be UTC, monotone within process.

# ASCII lexicographic directory listing (filenames only, no dirs)
function list_ascii_sorted(dir: path) -> list<string>
  # Deterministic bytewise ASCII order.

# Concatenate raw bytes of inputs and return SHA-256 (32 raw bytes)
function sha256_concat_bytes(files: list<path>) -> bytes[32]
  # Reads each file as raw bytes, in the given order.
```

---

## F1. Validation-gate hash (`_passed.flag`)

**Normative rule:** `_passed.flag` contains **one line**:
`sha256_hex = <hex64>`, where `<hex64>` is the SHA-256 over the **raw byte concatenation** of **all other bundle files** in **ASCII lexicographic filename order**. The flag itself is **excluded** from the hash. Downstream **must** verify this or treat the run as invalid (F10).

```text
function write_passed_flag(tmp_dir: path):
  files = list_ascii_sorted(tmp_dir)                    # ASCII lexicographic
  inputs = [ tmp_dir/f for f in files if f != "_passed.flag" ]
  H = sha256_concat_bytes(inputs)
  write_text(tmp_dir+"/_passed.flag", "sha256_hex = " + hex64(H) + "\n")
```

---

## F2. Atomic publish of the validation bundle (fingerprint-scoped)

**Normative path & behavior:** write bundle in a temp dir under `…/validation/_tmp.{uuid}`, compute `_passed.flag`, then a **single atomic `rename(2)`** into `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`. On failure, **delete** the temp directory.

```text
function publish_atomic(tmp_dir: path, final_dir: path):
  # Preconditions: tmp_dir contains the complete bundle incl. _passed.flag
  # final_dir = "data/layer1/1A/validation/fingerprint="+manifest_fingerprint
  mkdirs(parent(final_dir))
  atomic_rename(tmp_dir, final_dir)     # single rename(2); no partial visibility.
```

*Context:* The bundle directory shape and required files are defined in §S0.10.5 (`MANIFEST.json`, `*_resolved.json`, `param_digest_log.jsonl`, `fingerprint_artifacts.jsonl`, `numeric_policy_attest.json`, optional lints, `_passed.flag`).

---

## F3. Partition/lineage equivalence check (dictionary-backed)

**Normative partitions (S0.10.3):**

* **Parameter-scoped** datasets partition by `parameter_hash={parameter_hash}` and **embed the same** `parameter_hash` in every row.
* **Log-scoped (RNG)** streams partition by `{seed, parameter_hash, run_id}`.
* **Fingerprint-scoped** validation bundles partition by `fingerprint={manifest_fingerprint}` (column name remains `manifest_fingerprint`).

```text
# Verify the row's embedded lineage equals the path keys for this dataset.
# Abort with F5 'partition_mismatch' on any discrepancy.
function verify_partition_keys(dataset_id: string,
                               path_keys: map<string,string|u64>,
                               row_embedded: map<string,string|u64>):
  # Switch by dictionary authority (dataset_dictionary.layer1.1A.yaml)
  if dataset_id in PARAMETER_SCOPED:
      expect = { "parameter_hash": path_keys["parameter_hash"] }
      got    = { "parameter_hash": row_embedded["parameter_hash"] }
  elif dataset_id in RNG_LOG_SCOPED:
      expect = {
        "seed": path_keys["seed"],
        "parameter_hash": path_keys["parameter_hash"],
        "run_id": path_keys["run_id"]
      }
      got = {
        "seed": row_embedded["seed"],
        "parameter_hash": row_embedded["parameter_hash"],
        "run_id": row_embedded["run_id"]
      }
  elif dataset_id == "validation_bundle_1A":
      expect = { "manifest_fingerprint": path_keys["manifest_fingerprint"] }   # path segment name is 'fingerprint=…'
      got    = { "manifest_fingerprint": row_embedded["manifest_fingerprint"] }
  else:
      abort(F6, {"failure_code":"dictionary_path_violation",
                 "expected": schema_catalog_path(dataset_id),
                 "observed": observed_path(dataset_id)})                        # dictionary is authoritative.

  if expect != got:
      abort(F5, {"failure_code":"partition_mismatch",
                 "dataset_id": dataset_id,
                 "path_key":   stringify(expect),
                 "embedded_key": stringify(got)})                               # partition equivalence (F5).
```

*(Writers for parameter-scoped datasets must also use **overwrite-atomic** per partition: stage under `…/_tmp.{uuid}` then single `rename(2)`; **no partial contents** may become visible (F10).)*

---

## F4. Deterministic run-abort routine (S0.9)

**When to call:** on any F1…F10 violation (schema, lineage, counters/budgets, numeric policy, dictionary drift, atomics, etc.). The abort writes artefacts under a **fingerprint/seed/run_id** subdirectory and freezes RNG.

**Timestamp encodings (normative):**

* In **failure records**, `ts_utc` is **epoch-ns (u64)**.
* In **RNG envelopes**, `ts_utc` is RFC-3339 UTC (string).

```text
# Minimal contract for a run-abort (S0.9). Callers pass a typed 'detail' per table.
function abort_run(failure_class: string, failure_code: string,
                   seed: u64, parameter_hash: hex64, manifest_fingerprint: hex64, run_id: hex32,
                   detail: object,
                   partial_partitions: list<{dataset_id, partition_path, reason}>):
  # 1) Stop emitting new events/datasets immediately (callers enforce).

  # 2) Write failure record under fingerprint/seed/run_id
  base = "data/layer1/1A/validation/failures/" +
         "fingerprint="+manifest_fingerprint+"/seed="+seed+"/run_id="+run_id+"/"  
  mkdirs(base)
  hdr = {
    "failure_class": failure_class,            # "F1".."F10"
    "failure_code":  failure_code,             # canonical snake_case (see crosswalk)
    "ts_utc":        now_ns(),                 # epoch ns (u64)
    "seed":          seed,
    "parameter_hash": parameter_hash,
    "manifest_fingerprint": manifest_fingerprint,
    "run_id":        run_id,
    "detail":        detail                    # typed minima per spec (see below)
  }
  write_json(base+"failure.json", hdr)                                           # mandatory single file
  write_json(base+"_FAILED.SENTINEL.json", hdr)                                  # quick-scan duplicate

  # 3) Mark incomplete outputs (if any escaped temp)
  for p in partial_partitions:
      write_json(p.partition_path+"/_FAILED.json", {
        "dataset_id": p.dataset_id, "partition_keys": p.partition_path, "reason": p.reason
      })                                                                         

  # 4) Freeze RNG (no more events); last counters remain as in failing envelope. 
  # 5) Exit non-zero; orchestrator halts downstream.                             
```

**Typed `detail` minima (examples):**
`rng_counter_mismatch`, `partition_mismatch`, `ingress_schema_violation`, `artifact_unreadable`, `dictionary_path_violation`, `hurdle_nonfinite`—field shapes are normative in the frozen doc.

**Failure taxonomy & crosswalk:** use `failure_class=F1…F10` and a canonical `failure_code` (snake_case) e.g., `partition_mismatch`, `numeric_rounding_mode`, `fma_detected`, `dictionary_path_violation`, `incomplete_dataset_instance`, etc. (Crosswalk preserves legacy `E_*` for clarity.)

---

## F5. What validators/consumers check (so writers know the target)

* **Bundle integrity:** presence of all required files in the fingerprint dir and **`_passed.flag` hash matches**.
* **Partition lint:** parameter-scoped rows embed the same `parameter_hash` as their path; logs use `{seed,parameter_hash,run_id}`; bundle dir is `fingerprint=…`.
* **Idempotent equivalence:** bundles are equivalent iff `MANIFEST.json` matches **byte-for-byte** and all other files match byte-for-byte and **flag hashes** match.

---

### Why this is spec-true (and minimal)

* `_passed.flag` hashing, directory structure, and **atomic `rename(2)`** match §S0.10.5–.6 exactly.
* Partition/lineage rules and RNG log partitions come straight from §S0.10.3 and the dataset dictionary.
* Abort routine steps, timestamp domains, failure shapes and taxonomy are copied from S0.9 verbatim.

---