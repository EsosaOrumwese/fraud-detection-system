# L1 — 1A.S0 State Kernels (S0.1–S0.10)

> Source of truth: `state.1A.s0.expanded.md`. This file is a **faithful, code‑agnostic transcription** of S0’s per‑section routines. It preserves your algorithms exactly, but imposes consistent **placement and formatting** so implementers can read in order without guesswork.  
> Dependencies: uses only pinned L0 helpers from `pseudocode-1A.s0.L0.txt` (no undeclared helpers).
> Helper policy: If a function isn’t strictly state-local glue, **do not define it here** — call the canonical implementation in **L0** instead.

> **Helper policy.** This file defines **state-specific kernels** and wiring for S0.  
> It **does not** redefine cross-state helpers. Use L0 for:
> - Math/bytes/parsing/RNG/gate hash → L0 Capsules.  
> - Failure/abort payloads and paths → L0 Batch-F.  
> - RNG events & trace glue → L0 Batch-D.  
> Local helpers are allowed **only** if they’re strictly S0-specific and not useful elsewhere; otherwise **promote to L0**.

**Conventions (read first):**
- Never hard-code widths, vocabularies, or domain sets — derive `|MCC|`, `|channel|`, `|dev|`, etc. from the governed dictionaries opened in S0.1; keep the normative assertions, not magic numbers.
- Do not add new helpers or RNG behavior here; reuse L0 names exactly (S0 is audit-only for RNG).
- Partition scope comes from the dataset dictionary; embed lineage keys and rely on L0’s `verify_partition_keys` for path==row equivalence.
- No late governance opens after S0.2 fingerprinting; any change must flow via `parameter_hash` / `manifest_fingerprint`.

---
# S0.1 — Universe, Symbols, Authority (L1 routines)

> **Goal:** fix $\mathcal U=(\mathcal M,\mathcal I,G,B,\text{SchemaAuthority})$ for the run; **no RNG**; all outputs are pure functions of loaded bytes and schemas. Abort on any violation listed under S0.1 failure semantics.

## 1) `load_and_validate_merchants() → M`

**Inputs:** none (reads authoritative ingress table `merchant_ids`).
**Outputs:** `M` (in-memory table with columns: `merchant_id` (id64), `mcc` (4-digit), `channel` (string), `home_country_iso` (ISO-2 uppercase)).
**Failure:** `E_INGRESS_SCHEMA` if table fails JSON-Schema validation.

```text
function load_and_validate_merchants():
  M = read_table("merchant_ids")
  assert schema_ok(M, "schemas.ingress.layer1.yaml#/merchant_ids"), "E_INGRESS_SCHEMA"
  return M
```

*(This only validates the ingress contract; domain checks and mapping happen below.)*

---

## 2) `load_canonical_refs() → (I, G, B)`

**Inputs:** none (reads pinned artefacts; read-only).
**Outputs:**

* `I` = ISO-3166 alpha-2 set (uppercase ASCII),
* `G` = GDP map $c↦\text{GDPpc}_{c,2024}^{\text{const2015USD}}$ (vintage **2025-04-15**, observation year **2024**),
* `B` = Jenks **K=5** bucket map $c↦\{1..5\}$ precomputed over that same $G$.
  **Failure:** `E_REF_MISSING` if any reference is missing/unreadable.

```text
function load_canonical_refs():
  I = read_ref("iso3166_canonical_2024")                 # uppercase ISO-2 set
  G = read_ref("world_bank_gdp_per_capita_20250415")     # total function at year=2024 (const 2015 USD)
  B = read_ref("gdp_bucket_map_2024")                    # precomputed Jenks K=5 over G
  assert I != null and G != null and B != null, "E_REF_MISSING"
  return (I, G, B)
```

*(S0.1 only loads them; S0.4 later does the lookups. Both artefacts are included in the manifest fingerprint via S0.2.)*

---

## 3) `authority_preflight(registry, dictionary) → authority`

**Purpose:** enforce that **JSON-Schema** is the sole contract authority for 1A; record the “country order is never encoded outside `country_set`” rule.
**Outputs:** `authority` object with the three authoritative schema anchors and the country-order rule.
**Failure:** `E_AUTHORITY_BREACH` if any 1A dataset/event points to a non-JSON-Schema contract (e.g., `.avsc`).

```text
function authority_preflight(registry, dictionary):
  anchors = [
    "schemas.ingress.layer1.yaml#/merchant_ids",
    "schemas.1A.yaml#",
    "schemas.layer1.yaml#/rng/events"  # family anchors
  ]
  # Scan dictionary: every 1A dataset schema_ref must begin with 'schemas.' (JSON-Schema), not an Avro file.
  for ds in dictionary.datasets_owned_by("1A"):
      assert L0.is_jsonschema_anchor(ds.schema_ref), "E_AUTHORITY_BREACH"    # predicate lives in L0

  # Sanity: dictionary carries the explicit note that country order authority is 'country_set'
  entry = dictionary.lookup("country_set")
  assert L0.contains_text(entry.description, "ONLY authoritative"), "E_AUTHORITY_BREACH"  # micro-helper in L0
  # (Dictionary indeed describes country_set as the ONLY authority for cross-country order.)

  return {
    "ingress_anchor": anchors[0],
    "layer1_anchor":  anchors[1],
    "rng_anchor":     anchors[2],
    "country_order_authority": "country_set"
  }
```

*(S0.1 records this policy so downstream never encodes cross-country order elsewhere.)*

---

## 4) `enforce_domains_and_map_channel(M, I) → M′`

**Purpose:** enforce **ISO FK**, **MCC domain**, and map ingress `channel` strings to internal symbols `{CP,CNP}`.
**Outputs:** `M′` with columns: `merchant_id` (id64), `mcc` (4-digit in 𝕂), `channel_sym ∈ {CP,CNP}`, `home_country_iso ∈ I`.
**Failure:**

* `E_FK_HOME_ISO` if `home_country_iso ∉ I`,
* `E_MCC_OUT_OF_DOMAIN` if `mcc ∉ 𝕂`,
* `E_CHANNEL_VALUE` if `channel ∉ {"card_present","card_not_present"}`.

```text
function enforce_domains_and_map_channel(M, I):
  M1 = []
  for row in M:
      c = row.home_country_iso
      k = row.mcc
      ch_in = row.channel
      # ISO FK
      assert c ∈ I, "E_FK_HOME_ISO"
      # MCC domain (authority = ingress schema enum)
      assert mcc_in_domain(k), "E_MCC_OUT_OF_DOMAIN"     # per schemas.ingress.layer1.yaml#/merchant_ids/properties/mcc
      # Channel mapping (normative)
      if ch_in == "card_present":     ch = "CP"
      elif ch_in == "card_not_present": ch = "CNP"
      else:                             fail_F2("E_CHANNEL_VALUE", {})
      M1.append({ merchant_id: row.merchant_id,
                  mcc: k, channel_sym: ch, home_country_iso: c })
  return M1
```

*(The internal channel vocabulary is exactly `["CP","CNP"]`—this is the only mapping.)*

---

## 5) `derive_merchant_u64(M′) → M″`

**Purpose:** produce the canonical 64-bit key for any place that needs a u64 (e.g., RNG substreams).
**Mapping (normative):**  
`merchant_u64 = LOW64( SHA256( LE64(merchant_id) ) )` where we pick bytes 24..31 and interpret as **little-endian u64**. **No string formatting** is ever used.

```text
function derive_merchant_u64(M1):
  M2 = []
  for row in M1:
      u = L0.merchant_u64_from_id64(row.merchant_id)    # single scalar in L0
      M2.append(row ∪ { merchant_u64: u })
  return M2
```

---

## 6) `freeze_run_context(M″, I, G, B, authority) → U`

**Purpose:** construct and freeze $\mathcal U$ for the run and assert the **runtime invariants**.
**Outputs:** `U = (M, I, G, B, authority)`; cached read-only for the run.
**Failure:** abort on any invariant breach listed below.

```text
function freeze_run_context(M2, I, G, B, authority):
  # Invariants (normative for S0.1)
  # 1) Immutability: treat refs as read-only handles for lifetime of run (enforced by caller/orchestrator).
  # 2) Coverage & domains already enforced by 'enforce_domains_and_map_channel'.
  # 3) Determinism: no RNG; this function performs no draws.
  # 4) Authority compliance: downstream must use JSON-Schema anchors recorded in 'authority'.

  U = { M: M2, I: I, G: G, B: B, authority: authority }
  return U
```

---

### Abort & validation hooks bound to S0.1

* **Abort codes:** `E_INGRESS_SCHEMA`, `E_REF_MISSING`, `E_AUTHORITY_BREACH`, `E_FK_HOME_ISO`, `E_MCC_OUT_OF_DOMAIN`, `E_CHANNEL_VALUE`.
* **Runtime/CI checks:** schema-check `merchant_ids`; assert references load and remain read-only; authority audit over dictionary; ISO FK; MCC & channel domain and mapping.

---

# S0.2 — Hashes & Identifiers (L1 routines)

> **Goal:** produce the three lineage keys (`parameter_hash`, `manifest_fingerprint`, `run_id`) exactly as specified; build the two S0.2 audit records for later bundling; no RNG is consumed in this state.

## 1) `hash_stream_with_race_guard(path, on_param) → digest32`

**Definition:** Use the L0 helper exactly (binary read, stat-before/after, fail on change). L1 **does not** re-implement it; call-through only. *(We’ll stat independently when we need size/mtime for logs.)*

```text
function hash_stream_with_race_guard(path, on_param):
  return sha256_stream(path, on_param)   # L0 exact-bytes hashing with race-guard
```

---

## 2) `compute_parameter_hash(P_files) → (parameter_hash, parameter_hash_bytes, param_digest_log_rows, parameter_hash_resolved_row)`

**Inputs:** `P_files: list[(basename, path)]` = governed set 𝓟 (must be ASCII basenames, unique, non-empty).
**Outputs:**

* `parameter_hash: hex64`, `parameter_hash_bytes: bytes[32]`,
* `param_digest_log_rows: list[{filename,size_bytes,sha256_hex,mtime_ns}]`,
* `parameter_hash_resolved_row: {parameter_hash, filenames_sorted}`.
  **Failure:** `E_PARAM_EMPTY`, `E_PARAM_NONASCII_NAME`, `E_PARAM_DUP_BASENAME`, `E_PARAM_IO`, `E_PARAM_RACE`.

```text
function compute_parameter_hash(P_files):
  assert len(P_files) >= 1, "E_PARAM_EMPTY"
  assert all_ascii_unique_basenames(P_files), "E_PARAM_NONASCII_NAME or E_PARAM_DUP_BASENAME"

  files = sort_by_basename_ascii(P_files)            # bytewise ASCII order of basenames
  tuples = []
  digest_rows = []
  for (name, path) in files:
      s0 = stat(path)                                # capture size + mtime for logging
      d  = hash_stream_with_race_guard(path, on_param=true)   # 32 raw bytes
      t  = SHA256( UER(name) || d )              # tuple-hash includes UER(name)
      tuples.append(t)
      digest_rows.append({
         filename: name,
         size_bytes: s0.size_bytes,
         sha256_hex: hex64(d),
         mtime_ns: s0.mtime_ns
      })

  C  = concat(tuples)                                # 32·n bytes
  Hb = SHA256(C)                                     # parameter_hash_bytes (32)
  Hx = hex64(Hb)

  resolved = { parameter_hash: Hx,
               filenames_sorted: [ name for (name,_) in files ] }

  return (Hx, Hb, digest_rows, resolved)
```

*This is the spec’s **tuple-hash** (names included, ASCII-sorted), plus the exact S0.2 audit rows for later bundling.*

---

## 3) `compute_manifest_fingerprint(artifacts, git32, param_b32) → (manifest_fingerprint, manifest_fingerprint_bytes, mf_resolved_row, fingerprint_artifacts_rows)`

**Inputs:**

* `artifacts: list[(basename, path)]` = set 𝓐 of **all artefacts actually opened** up to S0.2 (parameters, ISO, GDP, bucket map, schema files read, numeric policy, math profile, etc.),
* `git32: bytes[32]` **raw commit bytes** (SHA-256 raw; or SHA-1 raw left-padded with 12 zeros),
* `param_b32: bytes[32]` from S0.2.2.
  **Outputs:**
* `manifest_fingerprint: hex64`, `manifest_fingerprint_bytes: bytes[32]`,
* `mf_resolved_row: {manifest_fingerprint, artifact_count, git_commit_hex, parameter_hash}`,
* `fingerprint_artifacts_rows: list[{artifact_basename, sha256_hex}]` (for later `fingerprint_artifacts.jsonl`).
  **Failure:** `E_ARTIFACT_EMPTY`, `E_ARTIFACT_NONASCII_NAME`, `E_ARTIFACT_DUP_BASENAME`, `E_GIT_BYTES`, `E_PARAM_HASH_ABSENT`, `E_ARTIFACT_IO`, `E_ARTIFACT_RACE`.

```text
function compute_manifest_fingerprint(artifacts, git32, param_b32):
  assert len(artifacts) >= 1, "E_ARTIFACT_EMPTY"
  assert len(git32) == 32,   "E_GIT_BYTES"
  assert len(param_b32) == 32, "E_PARAM_HASH_ABSENT"
  assert all_ascii_unique_basenames(artifacts), "E_ARTIFACT_NONASCII_NAME or E_ARTIFACT_DUP_BASENAME"

  arts = sort_by_basename_ascii(artifacts)
  parts = []
  fa_rows = []
  for (name, path) in arts:
      d = hash_stream_with_race_guard(path, on_param=false)  # 32 raw bytes
      t = SHA256( UER(name) || d )                       # name-aware tuple-hash
      parts.append(t)
      fa_rows.append({ artifact_basename: name, sha256_hex: hex64(d) })

  U  = concat(parts) || git32 || param_b32
  Fb = SHA256(U)
  Fx = hex64(Fb)

  mf_resolved = {
    manifest_fingerprint: Fx,
    artifact_count: len(arts),
    git_commit_hex: hex64(git32),
    parameter_hash: hex64(param_b32)
  }
  return (Fx, Fb, mf_resolved, fa_rows)
```

*This is the spec’s **sorted tuple-hash (no XOR)** over 𝓐 plus **raw** commit bytes and the parameter bundle. Any change flips the fingerprint. The resolved rows are the exact S0.2 audit lines the validator will later recompute and compare.*

---

## 4) `derive_run_id(fp_bytes, seed_u64, start_time_ns, exists_fn) → run_id`

**Purpose:** log partitioner only; **never** influences RNG or outputs.
**Uniqueness:** if `exists_fn(run_id)` is true within the `{seed, parameter_hash}` scope, add **+1 ns** deterministically and retry; cap at **2^16** attempts then hard-fail.
**Output:** `run_id: hex32` (lower-case hex of first 16 digest bytes).

```text
function derive_run_id(fp_bytes, seed_u64, t_ns, exists_fn):
  attempts = 0
  while true:
      payload = UER("run:1A") || fp_bytes || LE64(seed_u64) || LE64(t_ns)
      r16 = SHA256(payload)[0:16]
      rid = hex32(r16)
      if not exists_fn(rid): return rid
      t_ns = t_ns + 1
      attempts = attempts + 1
      if attempts >= 65536:
          fail_F2("E_RUNID_COLLISION_EXHAUSTED", {seed:seed_u64})
```

*Exactly the spec’s UER payload + bounded loop; S0.2 consumes **no RNG**.*

---

## 5) (Tiny) convenience wrappers for S0.10 bundling

S0.2 itself returns the audit rows; S0.10 will write them into the **validation bundle** under `fingerprint={manifest_fingerprint}`:

* `param_digest_log.jsonl` (rows from §2),
* `parameter_hash_resolved.json`,
* `manifest_fingerprint_resolved.json`,
* `fingerprint_artifacts.jsonl`. *(S0.10 computes `_passed.flag` and publishes atomically.)*

---

### Invariants & wiring (for implementers)

* **Hashing domain:** always the **exact file bytes** (binary mode); use the race-guarded stream.
* **Encoding:** UER for strings; LE64 for integers; **ASCII sort**; name-aware tuple-hash (no delimiters beyond UER).
* **Partitioning contract:** parameter-scoped datasets partition by `parameter_hash`; egress/validation by `fingerprint`; RNG logs by `{seed, parameter_hash, run_id}`. *(Validators will recompute S0.2 keys and compare to the resolved rows.)*

---

# S0.3 — RNG Engine & Draw Accounting (L1 routines)

> **Scope:** derive master/audit, key **order-invariant** substreams, draw via the pinned samplers, and emit **event envelopes** plus the **per-(module,label) trace**. Counters are Philox **2×64-10**, **128-bit** `(hi,lo)`; **blocks = after − before**; **draws = uniforms consumed** (decimal uint128 string). JSON fields are numeric; endianness applies only to derivations.

## 1) Bootstrap — write the *single* RNG audit row (pre-draw)

```text
function rng_bootstrap_audit(seed:u64,
                             parameter_hash:hex64,
                             manifest_fingerprint:hex64,
                             manifest_fingerprint_bytes:bytes[32],
                             run_id:hex32,
                             build_commit:string,
                             code_digest:hex64|null,
                             hostname:string|null,
                             platform:string|null,
                             notes:string|null) -> Master:

  # Derive audit-only master material (root key/counter) per L0.B
  (M, root_key, root_ctr) = derive_master_material(seed, manifest_fingerprint_bytes)
    emit_rng_audit_row(seed, parameter_hash, manifest_fingerprint, run_id,
                       0, root_key, root_ctr.hi, root_ctr.lo,
                       build_commit, code_digest, hostname, platform, notes)
  # NOTE: rng_audit_log uses its own schema; it is not an event and must precede the first event.
  # Algorithm string is "philox2x64-10" per schema. 

  return Master{ M, k_star = root_key, c_star = (root_ctr.hi, root_ctr.lo) }
```

*Norms: audit-before-any-draws; root `(k⋆,c⋆)` is **not** used directly for sampling.*

---

## 2) Substreams — order-invariant, message-keyed

```text
# Deterministic substream for an event family 'ℓ' and ordered 'ids' tuple.
# Types/encodings for ids are fixed by schema (e.g., merchant_u64=LE64, iso=UER uppercase, i/j=LE32).
function derive_substream(master: Master, label: string, ids: tuple) -> Stream:
  ids_norm = SER(ids)                 # per schema: LE32 indices, LE64 u64 keys; ISO uppercased then UER.
  msg = UER("mlr:1A") || UER(label) || ids_norm
  H   = SHA256( master.M || msg )     # 32 bytes
  key = LOW64(H)
  ctr = ( BE64(H[16:24]), BE64(H[24:32]) )
  return Stream{ key, ctr }
```

*Substreams are determined by `(seed, fingerprint, ℓ, ids)`—**never** by execution order.*

---

## 3) Event wrappers — draw, envelope, trace (one pattern)

```text
# Begin an RNG event: capture 'before' from the stream's counter.
function begin_event_ctx(module, substream_label, seed, parameter_hash, manifest_fingerprint, run_id, stream) -> Ctx:
  return L0.begin_event_ctx(module, substream_label, seed, parameter_hash, manifest_fingerprint, run_id, stream)  # L0 D2

# Trace state carries cumulative totals; **use the canonical L0 type** to avoid divergence.
type TraceState = L0.TraceState

# Finalise + trace has a single canonical definition in L0.D2b.
# Use L0.end_event_and_trace at call sites (no local variant in L1).

function event_gumbel_key(master, ids, module:string, trace:TraceState, meta) -> (g:f64, stream:Stream, new_trace:TraceState):
  return L0.event_gumbel_key(master, ids, module, trace, meta)
```

*Budget: **1 uniform**; envelope must show `(blocks=1, draws="1")`. Ties later break by `(ISO, merchant_id)` per spec.*

---

### 4.b `gamma_mt` (Marsaglia–Tsang; **actual-use** budgeting)

```text
function event_gamma_component(master, ids, module:string, alpha:f64, trace:TraceState, meta) -> (G:f64, stream:Stream, new_trace:TraceState):
  return L0.event_gamma_component(master, ids, module, alpha, trace, meta)
```

*Budget: **exact uniforms consumed**; **no padding**; Box–Muller inside uses exactly 2 uniforms (one block). Envelope `draws` logs the **actual** total.*

---

### 4.c `poisson` (inversion / PTRS split)

```text
function event_poisson_component(master, ids, module:string, lambda:f64, context:string, trace:TraceState, meta) -> (K:int, stream:Stream, new_trace:TraceState):
  return L0.event_poisson_component(master, ids, module, lambda, context, trace, meta)
```

*Normative constants for PTRS (`0.931`, `2.53`, `-0.059`, `0.02483`, `1.1239`, `1.1328`, `3.4`, `0.9277`, `3.6224`, `0.86`) are **algorithmic**, not configurable; split threshold λ★=10.*

---

### 4.d ZTP “rejection/exhaustion” (non-consuming) and success
> **Payload contract (normative):** The payloads for the following ZTP markers **MUST** conform exactly to the
> dictionary/schema entries:
> 
> - `rng_event_ztp_rejection` → `schemas.layer1.yaml#/rng/events/ztp_rejection`  
> - `rng_event_ztp_retry_exhausted` → `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`
> 
> This file (L1) does not redefine those fields; implementers **must** serialize precisely the fields/types named in the
> schema refs above. These events are **non-consuming** (`blocks=0`, `draws="0"`) and only carry ZTP control metadata.
> The subsequent successful `poisson_component(context="ztp")` event carries the actual budget.

```text
# moved to L0.RNG (events capsule) — non-consuming marker
function event_ztp_rejection(master, ids, module:string, trace:TraceState, meta, before:Stream, after:Stream) -> TraceState:
  return L0.event_ztp_rejection(master, ids, module, trace, meta, before, after)

# moved to L0.RNG (events capsule) — non-consuming exhaustion marker
function event_ztp_retry_exhausted(master, ids, module:string, trace:TraceState, meta, before:Stream, after:Stream) -> TraceState:
  return L0.event_ztp_retry_exhausted(master, ids, module, trace, meta, before, after)
```

*ZTP note: rejections/exhaustion are **non-consuming** (`blocks=0`, `draws="0"`); the successful component event carries the budget. Hard cap **64** zeros.*

---

## 5) Box–Muller convenience wrapper (when needed by higher states)

> **Scope:** These RNG event helpers are **library code** for later states; **S0 orchestration never calls them**.
> S0 produces only the RNG **audit row** (no RNG events in S0).

```text
# moved to L0.RNG (events capsule) — budget (blocks=1, draws="2")
function event_normal_box_muller(master, ids, module:string, trace:TraceState, meta) -> (Z:f64, stream:Stream, new_trace:TraceState):
  return L0.event_normal_box_muller(master, ids, module, trace, meta)
```

*Budget: exactly **2 uniforms** (1 block); **discard** the sine mate; envelope must set `(blocks=1, draws="2")`.*

---

## 6) Reconciliation hook (end-of-state spot check)

```text
# Optional producer-side check mirroring validator logic: ensure per-(module,label)
# cumulative **blocks** and **draws** equal the sums in this state slice.
# moved to L0.RNG (events capsule) — producer-side spot-check
function reconcile_trace_vs_events(module, substream_label,
                                   events_blocks_sum:uint64, last_trace_blocks_total:uint64,
                                   events_draws_sum:uint64,  last_trace_draws_total:uint64):
  return L0.reconcile_trace_vs_events(module, substream_label,
                                      events_blocks_sum, last_trace_blocks_total,
                                      events_draws_sum, last_trace_draws_total)
```

---

### Norms these routines rely on (already pinned)

* **Open-interval U(0,1)** map with the endpoint guard; **never** compute `1/(2^64+1)` at runtime.
* **Box–Muller** constant `TAU=0x1.921fb54442d18p+2`; **no caching**; 2 uniforms → `(blocks=1, draws="2")`.
* **Gamma** (MT): **actual-use** uniforms; **Case B** = `draws(G′)+1`.
* **Poisson**: inversion for λ<10; **PTRS** for λ≥10 with **2 uniforms/attempt**; constants are algorithmic, not config.
* **Envelope**: `before/after` are numeric `(hi,lo)`; `blocks` is **u64** from the 128-bit delta; `draws` is **decimal uint128 string**. Non-consuming events: `before==after`, `blocks=0`, `draws="0"`.
* **Audit vs events**: audit row is **not** an event; must be written **before** the first event.

> **Field spellings & budgeting semantics are normative per L0 Capsule §§H4–H6, J, K.**
> (e.g., `blocks` is `u64`, `draws` is a **decimal u128 string**; master/substream message and budget authority are pinned there.)

This gives implementers unambiguous, state-accurate L1 routines for S0.3—plug-and-play on top of your L0 kernels and log writers, zero room for initiative.

---

# S0.4 — Deterministic GDP Bucket Attachment (L1)

**Purpose.** For each merchant $m$ with home ISO $c$, attach:

* $g_c = G(c)$ (GDP-per-capita, **obs-year 2024**, **constant 2015 USD**), and
* $b_m = B(c) \in \{1..5\}$ (precomputed **Jenks K=5** bucket). **No thresholds are computed at runtime.**

**Inputs (read-only; pinned by S0.1–S0.2):**

* `M`: `merchant_ids` with `merchant_id`, `mcc`, `channel`, `home_country_iso` (ISO-2 **uppercase**, FK-validated in S0.1).
* `I`: ISO set $\mathcal I$.
* `G`: total function $c \mapsto \text{GDPpc}_{\text{c,2024}}^{\text{const2015USD}} > 0$.
* `B`: total function $c \mapsto \{1..5\}$ from `gdp_bucket_map_2024` (**precomputed** over the same $G$).

## Pseudocode (language-agnostic)

```text
function S0_4_attach_gdp_features(M, I, G, B):
  # Output: stream/iterator of (merchant_id, g_c, b_m)

  for row in M:
      m = row.merchant_id
      c = row.home_country_iso

      # ISO FK (defensive: S0.1 already enforces)
      if c not in I:
          fail_F2("E_HOME_ISO_FK", {merchant_id:m, iso:c})

      # GDP lookup (must exist, strictly > 0)
      g = G.get(c)
      if g is None:
          fail_F2("E_GDP_MISSING", {iso:c})
      if not (g > 0.0):
          fail_F2("E_GDP_NONPOS", {iso:c, value:g})

      # Bucket lookup (must exist, 1..5)
      b = B.get(c)
      if b is None:
          fail_F2("E_BUCKET_MISSING", {iso:c})
      if not (1 <= b <= 5):
          fail_F2("E_BUCKET_RANGE", {iso:c, value:b})

      yield (m, g, b)  # passed forward to S0.5; optionally materialised (see partitions note)
```

**Determinism & numeric policy.** Pure lookups; **no randomness**. Any derived transforms later (e.g., $\log g_c$ in S0.5) follow the binary64 numeric policy (RNE, FMA-off) per S0.8.

**Failure semantics (abort).** Zero-tolerance on: `E_HOME_ISO_FK`, `E_GDP_MISSING`, `E_GDP_NONPOS`, `E_BUCKET_MISSING`, `E_BUCKET_RANGE` (each with clear PK/ISO context).

**Semantics & downstream usage.**
$b_m$ is used **only** in the **hurdle** design (five one-hot dummies, order \[1..5]); $\log g_c$ is used **only** in NB **dispersion** (never in NB mean). This division is **normative** and must be asserted by the design builder.

**Partitions & lineage.**
If you materialise these features, write them as **parameter-scoped** artefacts under `…/parameter_hash={parameter_hash}/` (do **not** embed `manifest_fingerprint` in parameter-scoped tables). Both GDP and bucket artefacts are part of the **manifest fingerprint**; any byte change flips egress lineage.

**Complexity & parallelism.**
Time $O(|\mathcal M|)$ hash lookups; space $O(1)$ per streamed row; **embarrassingly parallel** and reproducible.

**CI-only (not runtime) context.**
If `B` is ever rebuilt, Jenks K=5 is defined via a deterministic DP with **right-closed** classes; the **authoritative** truth at runtime remains the shipped `gdp_bucket_map_2024`.

---

# S0.5 — Design Matrices (L1 routines)
```text
# API contract note (normative): all one-hot widths and column order (MCC, channel, dict_dev vocabulary)
# come **only** from the frozen fitting-bundle artefacts loaded here; they are **never**
# derived from batch-observed categories.
# Local helper: deterministic one-hot encoder (index within [0, length-1])
function one_hot(index:int, length:int) -> int[]:
  v = [0] * length
  v[index] = 1
  return v
```

> **Scope:** deterministically build column-aligned design vectors for each merchant $m$: hurdle $x_m$, NB-mean $x^{(\mu)}_m$, and NB-dispersion $x^{(\phi)}_m$. **Column dictionaries and their order come from the fitting bundle and are never computed at runtime.**

## 1) `build_dicts_and_assert_shapes(bundle) → (dict_mcc, dict_ch, dict_dev, beta_hurdle, nb_dispersion_coef)`

**Inputs:** parameter-scoped fitting bundle artefacts (bytes affect `parameter_hash`).
**Outputs:** frozen dictionaries and coefficient vectors.
**Failure:** `E_DSGN_UNKNOWN_CHANNEL`, `E_DSGN_SHAPE_MISMATCH`.

```text
function build_dicts_and_assert_shapes(bundle):
  dict_mcc   = bundle.load("dict_mcc")        # authoritative order for MCC dummies
  dict_ch    = bundle.load("dict_channel")    # MUST be exactly ["CP","CNP"]
  dict_dev  = bundle.load("dict_dev")       # MUST be exactly [1,2,3,4,5]
  # Authoritative source: these dictionaries are part of the fitting bundle (parameter-scoped lineage),
  # and are NOT derived from the current batch input.

  beta_hurdle        = bundle.load("hurdle_coefficients")      # single vector aligned to dicts
  nb_dispersion_coef = bundle.load("nb_dispersion_coeffs")     # aligned; includes ln(g) slope

  assert dict_ch   == ["CP","CNP"], E_DSGN_UNKNOWN_CHANNEL                  # channel vocab is normative
  assert dict_dev == [1,2,3,4,5],  E_DSGN_SHAPE_MISMATCH                   # bucket order is fixed

  C_mcc = len(dict_mcc)
  C_ch  = len(dict_ch)
  C_dev = len(dict_dev)
  assert C_ch  >= 1, E_DSGN_SHAPE_MISMATCH     # non-empty governed vocabularies
  assert C_dev >= 1, E_DSGN_SHAPE_MISMATCH
  assert len(beta_hurdle)        == 1 + C_mcc + C_ch + C_dev, E_DSGN_SHAPE_MISMATCH
  assert len(nb_dispersion_coef) == 1 + C_mcc + C_ch + 1,     E_DSGN_SHAPE_MISMATCH

  return (dict_mcc, dict_ch, dict_dev, beta_hurdle, nb_dispersion_coef)
```

*Why:* dictionaries and shapes are frozen by the fitting artefacts; the hurdle vector **includes all five bucket dummies**; NB-dispersion includes the slope on $\ln g_c$.

---

## 2) `encode_onehots(m, dict_mcc, dict_ch, dict_dev, G, B) → (h_mcc, h_ch, h_dev, g, b)`

**Inputs:** merchant row with `{mcc, channel_sym, home_country_iso}`; dictionaries; S0.4 maps $G, B$.
**Outputs:** one-hot blocks and the required S0.4 features.
**Failure:** `E_DSGN_UNKNOWN_MCC`, `E_DSGN_UNKNOWN_CHANNEL`, `E_DSGN_DOMAIN_GDP`, `E_DSGN_DOMAIN_BUCKET`.

```text
function encode_onehots(m, dict_mcc, dict_ch, dict_dev, G, B):
  # Pull domains from S0.4 (strict coverage)
  c = m.home_country_iso
  g = G[c];    if not (g > 0):              fail_F2("E_DSGN_DOMAIN_GDP",    {iso:c, g:g})
  b = B[c];    if b not in set(dict_dev):  fail_F2("E_DSGN_DOMAIN_BUCKET", {iso:c, b:b})
  # Indices come strictly from the frozen dicts above; do NOT infer widths or order from batch categories.
  # (Prevents drift/leakage and preserves parameter-scoped determinism.)

  # Dictionary lookups -> positions
  i_mcc = dict_mcc.index_of(m.mcc)          # throws -> E_DSGN_UNKNOWN_MCC if absent
  i_ch  = dict_ch.index_of(m.channel_sym)   # channel_sym must be CP/CNP from S0.1
  i_dev = dict_dev.index_of(b)

  # Deterministic one-hots (exactly one "1" each)
  h_mcc = one_hot(i_mcc, len(dict_mcc))
  h_ch  = one_hot(i_ch, len(dict_ch))
  h_dev = one_hot(i_dev, len(dict_dev))

  return (h_mcc, h_ch, h_dev, g, b)
```

*Notes:* channel vocabulary is **exactly** `["CP","CNP"]`; dev is `[1..5]` by construction.

---

## 3) `build_design_vectors(m, dicts, G, B) → (x_hurdle, x_nb_mu, x_nb_phi)`

**Inputs:** merchant row; dictionaries; S0.4 maps.
**Outputs:** three column-aligned design vectors.
**Failure:** same as above; plus structural assertions to enforce the leakage rule.

```text
function build_design_vectors(m, dicts, G, B):
  (dict_mcc, dict_ch, dict_dev) = dicts
  (h_mcc, h_ch, h_dev, g, b) = encode_onehots(m, dict_mcc, dict_ch, dict_dev, G, B)

  # Intercept-first convention (normative)
  x_hurdle = [1] + h_mcc + h_ch + h_dev                  # ℝ^{1 + C_mcc + |ch| + |dev|}
  x_nb_mu  = [1] + h_mcc + h_ch                          # ℝ^{1 + C_mcc + |ch|}
  x_nb_phi = [1] + h_mcc + h_ch + [ln(g)]                # ℝ^{1 + C_mcc + |ch| + 1}

  # Machine-check the leakage guard (redundant but explicit)
  C_ch  = len(dict_ch)
  assert len(x_nb_mu)  == 1 + len(dict_mcc) + C_ch
  assert len(x_nb_phi) == 1 + len(dict_mcc) + C_ch + 1

  return (x_hurdle, x_nb_mu, x_nb_phi)
```

*Design rules (normative):* GDP **bucket** appears **only** in the **hurdle**; $\ln g_c$ appears **only** in **NB-dispersion**. The dictionaries’ column order is authoritative.

---

## 4) (Optional) `S0_5_build_designs_stream(M, dicts, coefs, G, B) → iterator`

A thin orchestrator for streaming all merchants. Emits tuples `(merchant_id, x_hurdle, x_nb_mu, x_nb_phi)`; **no RNG**; $O(|\mathcal M|)$ time, $O(1)$ space. If materialised, write under `…/parameter_hash={parameter_hash}/…` with the dictionary-backed schema; **do not** embed `manifest_fingerprint` in parameter-scoped outputs.

```text
function S0_5_build_designs_stream(M, dicts, coefs, G, B):
  (dict_mcc, dict_ch, dict_dev, beta_hurdle, nb_dispersion_coef) = coefs
  # Shapes already asserted by 'build_dicts_and_assert_shapes'
  for r in M:
      (x_hurdle, x_nb_mu, x_nb_phi) = build_design_vectors(r, (dict_mcc, dict_ch, dict_dev), G, B)
      yield (r.merchant_id, x_hurdle, x_nb_mu, x_nb_phi)
```

---

## Failure semantics (precise aborts)

`E_DSGN_UNKNOWN_MCC`, `E_DSGN_UNKNOWN_CHANNEL`, `E_DSGN_SHAPE_MISMATCH`, `E_DSGN_DOMAIN_GDP`, `E_DSGN_DOMAIN_BUCKET`, and (if persisted) `E_PARTITION_MISMATCH` for parameter-scoped writes.

---

## Determinism & numeric policy

No randomness; outputs are functions of frozen dictionaries and S0.4 lookups. Evaluate $\ln g_c$ in **binary64**, policy pinned by S0.8; any change flips the numeric-policy artefact.

---

**This exactly matches the frozen S0.5 text**: intercept-first layout, CP/CNP canonical order, dev-5 mapping `[1..5]`, strict column shapes, and a machine-checked **leakage guard** preventing GDP features from leaking across the hurdle/NB boundaries. Ready for S1 to consume $(x_m,\beta)$ and for S2 to consume $(x^{(\mu)}_m,x^{(\phi)}_m)$.

---

# S0.6 — Cross-border Eligibility (L1 routines)
```
# Local helpers for rule parsing/ordering (self-contained per spec)
function min_lex(pairs: list[(int priority, string id)]) -> (int,string):
  best = pairs[0]
  for p in pairs[1:]:
    if (p.priority < best.priority) or (p.priority == best.priority and p.id < best.id):
      best = p
  return best

function expand_mcc(spec: string) -> set[int]:
  # supports "*" (all), "NNNN", or "NNNN-MMMM" inclusive; 4-digit ASCII
  if spec == "*": return ALL_MCC_CODES
  if "-" in spec:
    lo, hi = spec.split("-", 1)
    assert len(lo)==4 and len(hi)==4 and lo.isdigit() and hi.isdigit() and int(lo) <= int(hi)
    return { i for i in range(int(lo), int(hi)+1) }
  assert len(spec)==4 and spec.isdigit()
  return { int(spec) }

function ranges_well_formed(specs: list[string]) -> bool:
  for s in specs:
    if s == "*": continue
    if "-" in s:
      lo, hi = s.split("-", 1)
      if not (len(lo)==4 and len(hi)==4 and lo.isdigit() and hi.isdigit() and int(lo)<=int(hi)):
        return false
    else:
      if not (len(s)==4 and s.isdigit()):
        return false
  return true

function ALL_UPPER_ASCII(S: list[string]) -> bool:
  for x in S:
    if x != x.upper(): return false
    for ch in x:
      if not ("A" <= ch <= "Z"): return false
  return true
```

> **Goal:** Decide, *without randomness*, whether each merchant may attempt cross-border later. Persist **exactly one** row per merchant to **`crossborder_eligibility_flags`** (parameter-scoped, partitioned by `parameter_hash`; optional `produced_by_fingerprint` is informational only).

## 1) `load_and_validate_rules(params, I, K) → (rule_set_id, default_allow, rules_expanded)`

**Inputs:** parameter bundle (`crossborder_hyperparams.yaml`), ISO set `I`, MCC set `K`.
**Output:** `rule_set_id: nonempty ASCII`, `default_allow: bool`, and a **validated, expanded** list of rules where each rule has:

```
{id, decision∈{allow,deny}, priority∈[0,2^31-1],
 S_ch ⊆ {CP,CNP}, S_iso ⊆ I, S_mcc ⊆ K}
```

**Failure at load:** `E_ELIG_RULESET_ID_EMPTY`, `E_ELIG_DEFAULT_INVALID`, `E_ELIG_RULE_DUP_ID(id)`, `E_ELIG_RULE_BAD_CHANNEL(id,ch)`, `E_ELIG_RULE_BAD_ISO(id,iso)`, `E_ELIG_RULE_BAD_MCC(id,mcc_or_range)`.

```text
function load_and_validate_rules(params, I, K):
  cfg = params["eligibility"]

  rsid = cfg["rule_set_id"]
  assert rsid is nonempty ASCII, E_ELIG_RULESET_ID_EMPTY

  dd = cfg["default_decision"]
  assert dd in {"allow","deny"}, E_ELIG_DEFAULT_INVALID
  default_allow = (dd == "allow")

  seen_ids = {}
  rules_out = []
  for r in cfg["rules"]:
      id  = r["id"];  dec = r["decision"];  pri = r["priority"]
      ch  = r["channel"]; iso = r["iso"];   mcc = r["mcc"]

      # id unique, vocab/priority valid
      assert id is ASCII and id not in seen_ids, E_ELIG_RULE_DUP_ID(id)
      seen_ids[id] = 1
      assert dec in {"allow","deny"} and 0 <= pri <= 2_147_483_647

      # expand sets: "*" or subsets
      S_ch  = {"CP","CNP"}         if ch  == "*" else set(ch)
      S_iso = set(I)               if iso == "*" else set(iso)
      S_mcc = expand_mcc(mcc)      # 4-digit elems and inclusive ranges "NNNN-MMMM"

      # domain checks
      assert S_ch  ⊆ {"CP","CNP"},             E_ELIG_RULE_BAD_CHANNEL(id, ch)
      assert S_iso ⊆ I and ALL_UPPER_ASCII(S_iso), E_ELIG_RULE_BAD_ISO(id, bad_iso)
      assert S_mcc ⊆ K and ranges_well_formed(mcc), E_ELIG_RULE_BAD_MCC(id, bad_mcc)

      rules_out.append({ id, decision:dec, priority:pri,
                         S_ch, S_iso, S_mcc })
  return (rsid, default_allow, rules_out)
```

*Range semantics:* `"5000-5999"` expands to all integer MCCs with **inclusive** bounds; comparisons are numeric on parsed 4-digit codes.

---

## 2) `index_rules(rules_expanded) → (deny_idx, allow_idx)`

**Purpose:** speed up matching; **not** visible externally.
**Indexing:** by `(channel_sym, home_iso)` → **MCC interval set**.
*(Naive $O(|\mathcal R|)$ scan is allowed; index is just a performance aid.)*

```text
function index_rules(rules):
  deny_idx  = new_index()   # (ch, iso) -> MCC interval set with (priority, id)
  allow_idx = new_index()
  for r in rules:
      for ch in r.S_ch:
        for iso in r.S_iso:
          target = deny_idx if r.decision=="deny" else allow_idx
          target.insert(ch, iso, r.S_mcc, (r.priority, r.id))
  return (deny_idx, allow_idx)
```

---

## 3) `decide_eligibility(m, deny_idx, allow_idx, default_allow) → (is_eligible, reason)`

**Inputs:** `m` has `(mcc, channel_sym∈{CP,CNP}, home_country_iso)` fixed in S0.1.
**Conflict resolution (total order):** **deny** tier outranks **allow**; then **priority asc**; then **ASCII `id`**.

```text
function decide_eligibility(m, deny_idx, allow_idx, default_allow):
  key = (m.channel_sym, m.home_country_iso, m.mcc)

  D = deny_idx.match(key)   # -> list of (priority, id) for matching MCC intervals
  A = allow_idx.match(key)

  if not empty(D):
      (p, id) = min_lex(D)                  # (priority asc, id ASCII asc)
      return (false, id)
  if not empty(A):
      (p, id) = min_lex(A)
      return (true, id)

  return (default_allow, "default_allow" if default_allow else "default_deny")
```

Formal decision function $e_m$ and `reason` mirror the spec’s equations exactly.

---

## 4) `write_eligibility_flags(rows, parameter_hash, produced_by_fp?)`

**Contract:** write **one** row per merchant to
`…/crossborder_eligibility_flags/parameter_hash={parameter_hash}/part-*.parquet`
embedding **the same `parameter_hash`** as a column; `produced_by_fingerprint` (hex64) is **optional** and **informational only** (never a partition key or equality key). Schema: `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.

```text
function write_eligibility_flags(rows, parameter_hash, produced_by_fp=None):
  w = open_partitioned_writer("crossborder_eligibility_flags",
                              partition={"parameter_hash": parameter_hash})
  for (m_id, is_ok, reason, rule_set_id) in rows:
      row = {
        "parameter_hash": parameter_hash,
        "merchant_id": m_id,
        "is_eligible": is_ok,
        "reason": reason,
        "rule_set": rule_set_id
      }
      if produced_by_fp is not None:
          row["produced_by_fingerprint"] = produced_by_fp

      ok = w.write(row)
      assert ok, E_ELIG_WRITE_FAIL(w.path, w.errno)

  w.close()
```

**Validation & CI hooks (spec-mandated):** schema conformance; **exactly one** row per `merchant_id`; determinism (byte-identical given the same inputs); partition lint (embedded `parameter_hash` equals path key; ignore `produced_by_fingerprint`).

---

## 5) Orchestrator (exact algorithm; streaming-safe)

```text
function S0_6_apply_eligibility_rules(merchants, params, I, K, parameter_hash, produced_by_fp=None):
  (rsid, default_allow, rules) = load_and_validate_rules(params, I, K)
  (deny_idx, allow_idx) = index_rules(rules)

  out_rows = []
  for m in merchants:
      assert has_fields(m, ["mcc","channel_sym","home_country_iso","merchant_id"]),
             E_ELIG_MISSING_MERCHANT(m.merchant_id)

      (is_ok, why) = decide_eligibility(m, deny_idx, allow_idx, default_allow)
      out_rows.append( (m.merchant_id, is_ok, why, rsid) )

  write_eligibility_flags(out_rows, parameter_hash, produced_by_fp)
```

This is **order-invariant** and embarrassingly parallel; outputs depend only on $t(m)$ and the versioned rules.

---

## Determinism, domains, and failures (bound to S0.6)

* **No RNG.** Pure function of merchant tuple + parameter bundle.
* **Domains:** channels `{CP,CNP}`; ISO in $\mathcal I$; MCC in $\mathcal K$.
* **Abort semantics:** load-time errors above; eval/persist errors `E_ELIG_MISSING_MERCHANT`, `E_ELIG_WRITE_FAIL(path, errno)`, `E_PARTITION_MISMATCH(path_key, embedded_key)`. **On any error, abort S0; no partial output.**

This exactly matches the frozen S0.6 text: the rule grammar, expansion, domains, conflict-resolution order, dataset contract, and failure handling—no over-engineering and zero drift.

---

# S0.7 — Hurdle π Diagnostic Cache (L1)

> **Purpose.** Materialise a **read-only** table with per-merchant $(\eta_m,\pi_m)$ so monitoring can inspect the hurdle surface **without** recomputation on the hot path. This artefact is **optional**, **parameter-scoped**, and **never** read by samplers. Schema: `schemas.1A.yaml#/model/hurdle_pi_probs`.

## Inputs (frozen by S0.1–S0.5)

* `merchants` (stream of rows providing `merchant_id`, `mcc`, `channel_sym`, `home_country_iso`),
* `beta` (single hurdle coefficient vector aligned to `x_m`),
* `dicts` (the frozen dictionaries from S0.5),
* `parameter_hash` (partition key), optional `produced_by_fingerprint` (informational only).
  **No RNG** is consumed.

## Output (parameter-scoped dataset)

Write **one row per merchant** to
`…/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/part-*.parquet` with columns:
`parameter_hash` (== path key), `produced_by_fingerprint` (optional), `merchant_id`, `logit` (f32), `pi` (f32 in \[0,1]).

---

## Pseudocode (language-agnostic)

```text
function S0_7_build_hurdle_pi_probs(merchants, beta, dicts, G, B, parameter_hash, produced_by_fp=None):
  # Open parameter-scoped writer
  w = open_partitioned_writer("hurdle_pi_probs",
        partition={"parameter_hash": parameter_hash})      # schema #/model/hurdle_pi_probs

  # Optional: constant-time guard — beta length must match the hurdle design width (S0.5)
  C_ch  = len(dicts.ch)
  C_dev = len(dicts.dev)
  expected = 1 + len(dicts.mcc) + C_ch + C_dev               # intercept + MCC + channel + dev
  if len(beta) != expected:
      fail_F2("E_PI_SHAPE_MISMATCH", {expected: expected, got: len(beta)})

  
  # Stream merchants and materialize one row each
  for m in merchants:
      # Rebuild deterministic hurdle design vector x_hurdle via S0.5
      (x_hurdle, _, _) = build_design_vectors(m, dicts, G, B)
      # Binary64 dot; fixed evaluation order; FMA off (S0.8 policy)
      eta64 = dot_neumaier(beta, x_hurdle)
      # Branch-stable logistic (spec-true)
      pi64 = logistic_branch_stable(eta64)
      # Abort on non-finite values as per failure semantics
      if not is_finite(eta64) or not is_finite(pi64):
          fail_F2("E_PI_NAN_OR_INF", {merchant_id: m.merchant_id, eta: eta64, pi: pi64})

      row = {
        "parameter_hash": parameter_hash,
        "merchant_id":    m.merchant_id,
        "logit":          f32(eta64),
        "pi":             f32(pi64)
      }
      if produced_by_fp is not None:
          row["produced_by_fingerprint"] = produced_by_fp               # informational only

      ok = w.write(row)
      if not ok:
          fail_F2("E_PI_WRITE", {path: w.path, errno: w.errno})

  w.close()
```

**Notes bound to spec:**

* `build_design_vectors (hurdle vector via dicts, G, B)` uses the **exact** column order frozen by the fitting bundle; channel dict is **\["CP","CNP"]**, dev-5 is **\[1..5]**. Bucket dummies appear **only** in the hurdle design.
* `logistic_branch_stable(η)` is the overflow-stable definition:

  $$
  \sigma(\eta)=\begin{cases}1/(1+e^{-\eta}),&\eta\ge0\\ e^\eta/(1+e^\eta),&\eta<0\end{cases}
  $$

  Extremes $\pi\in\{0,1\}$ are **allowed** and persisted.
* Storage is **float32** only; compute is **binary64** under S0.8’s numeric policy (RNE, FMA-off, fixed evaluation order).

---

## Failure semantics (abort S0; precise)

* `E_PI_SHAPE_MISMATCH(exp_dim, got_dim)` — $|\beta|\neq\dim(x_m)$.
* `E_PI_NAN_OR_INF(m)` — non-finite $\eta_m$ or $\pi_m$.
* `E_PI_WRITE(path, errno)` — writer failure.
* Partition lint is validated externally; if enforced here, abort as `E_PI_PARTITION(path_key, embedded_key)` on mismatch.

---

## Validation & CI hooks (for S0.10/validators)

1. Schema conformance; 2) **Coverage = |M|** rows; 3) **Recompute check**: rebuild $x_m$ and recompute $\eta_m,\pi_m$, assert **bit-for-bit** equality to stored **float32**; 4) Partition lint (`parameter_hash` in path == embedded); 5) **Downstream isolation**: S1–S9 **must not** read this dataset.

**All of the above matches the frozen S0.7 text verbatim:** optional, parameter-scoped, diagnostic-only; binary64 compute, branch-stable logistic, deterministic f32 narrowing; strict shapes; precise failure codes; and no coupling to RNG or egress beyond parameter lineage.

---

# S0.8 — Numeric Policy & Self-tests (L1)

> **Purpose (normative):** pin IEEE-754 **binary64**, **RNE**, **FMA off**, **no FTZ/DAZ**, deterministic libm, fixed-order reductions/sorts; then run self-tests and emit `numeric_policy_attest.json` for the validation bundle. Changing `numeric_policy.json` or `math_profile_manifest.json` flips the **manifest fingerprint**.

## 1) `set_numeric_env_and_verify() → env`

**Inputs:** none (reads nothing; sets process/thread FP state).
**Outputs:** `env` summary `{rounding:"rne", fma:false, ftz:false, daz:false}`.
**Abort:** `E_NUM_RNDMODE`, `E_NUM_FTZ_ON`. (FMA contraction is detected in §S0.8.9 test 2.)

```text
function set_numeric_env_and_verify():
  # Set & verify IEEE-754 binary64, RNE; ensure FTZ/DAZ disabled.
  fp_set_rounding("rne")
  if fp_get_rounding() != "rne": fail_F2("E_NUM_RNDMODE", {})

  fp_set_flush_to_zero(false)
  fp_set_denormals_are_zero(false)
  if fp_get_flush_to_zero() or fp_get_denormals_are_zero():
      fail_F2("E_NUM_FTZ_ON", {})

  # We do not trust compiler flags for FMA; actual detection is in self-tests (S0.8.9.2).
  return {rounding:"rne", fma:false, ftz:false, daz:false}
```

*Matches **S0.8.1** environment: binary64, RNE, honour subnormals; FTZ/DAZ off. Build flags are separately recorded in the validation MANIFEST.*

---

## 2) `attest_libm_profile(paths) → (math_profile_id, digests)`

**Inputs:** paths to `numeric_policy.json` and `math_profile_manifest.json`.
**Outputs:** `math_profile_id` string and `digests` = SHA-256 hex for both files (for attestation).
**Abort:** `E_NUM_PROFILE_ARTIFACT_MISSING(name)`, `E_NUM_LIBM_PROFILE` (coverage mismatch).

```text
function attest_libm_profile(paths):
  np_path  = paths.numeric_policy_json
  mp_path  = paths.math_profile_manifest_json

  if not exists(np_path): fail_F2("E_NUM_PROFILE_ARTIFACT_MISSING", {"name":"numeric_policy.json"})
  if not exists(mp_path): fail_F2("E_NUM_PROFILE_ARTIFACT_MISSING", {"name":"math_profile_manifest.json"})

  np_bytes = read_bytes(np_path)
  mp       = parse_json(read_bytes(mp_path))

  math_profile_id = mp["math_profile_id"]
  funcs = set(mp["functions"])

  # Required deterministic libm surface (spec scope includes lgamma).
  required = {"exp","log","log1p","expm1","sqrt","sin","cos","atan2","pow","tanh","erf","lgamma"}
  if not required ⊆ funcs:
      fail_F2("E_NUM_LIBM_PROFILE", {"missing": list(required - funcs)})

  dig_np = hex64( SHA256(np_bytes) )
  dig_mp = hex64( SHA256(encode_utf8(json_canonical(mp))) )
  return (math_profile_id, [{"name":"numeric_policy.json","sha256":dig_np},
                            {"name":"math_profile_manifest.json","sha256":dig_mp}])
```

*Scope/requirements for deterministic libm and inclusion of **`lgamma`** are normative in **S0.8.2**.*

---

## 3) `run_self_tests_and_emit_attestation(env, math_profile_id, digests, platform) → attestation_json`

**Inputs:** `env` from §1; `math_profile_id` & `digests` from §2; `platform` descriptor (OS/libc/compiler).
**Output:** JSON object conforming to **`numeric_policy_attest.json`**; S0.10 will place it under `validation/fingerprint=…/`.
**Abort:** on any failed test with the exact **S0.8.8** error codes.

```text
function run_self_tests_and_emit_attestation(env, math_profile_id, digests, platform):
  # 1) Rounding & FTZ (S0.8.9.1)
  assert fp_get_rounding() == "rne", "E_NUM_RNDMODE"
  x = make_subnormal()                       # e.g., 2^-1075 as binary64
  if (x * 1.0 == 0.0): fail_F2("E_NUM_FTZ_ON", {})

  # 2) FMA contraction detection (S0.8.9.2)
  # Use a pinned triple (a,b,c) from the vendored test corpus with known fused vs. non-fused outcomes.
  # Evaluate y = (a*b) + c in standard evaluation order and assert it matches the non-fused expected bits.
  y = (a*b) + c
  if bits(y) != expected_nonfused_bits: fail_F2("E_NUM_FMA_ON", {})

  # 3) libm regression (S0.8.9.3)
  # Run the fixed suite for exp/log/log1p/expm1/sqrt/sin/cos/atan2/pow/tanh/(erf)/lgamma.
  for (fn, inputs, expected_bits) in vendored_libm_suite():
      for i in 0..len(inputs)-1:
          r = call_deterministic_libm(fn, inputs[i])   # from the pinned math profile
          if bits(r) != expected_bits[i]:
              fail_F2("E_NUM_LIBM_PROFILE", {"func":fn, "i":i})

  # 4) Neumaier audited sum (S0.8.9.4)
  (s, c) = neumaier_audit_sequence()         # adversarial sequence & expected (s*, c*)
  if (bits(s) != bits_expected or bits(c) != bits_expected_c):
      fail_F2("E_NUM_ULP_MISMATCH", {"func":"neumaier"})

  # 5) TotalOrder sanity (S0.8.9.5)
  arr = crafted_float_array_with_signed_zero_and_extremes()
  sorted = sort_by_key(arr, total_order_key) # from §S0.8.10 reference kernel
  if not total_order_layout_ok(sorted):
      fail_F2("E_NUM_TOTORDER_NAN", {})

  attest = {
    "numeric_policy_version": "1.0",
    "math_profile_id": math_profile_id,
    "platform": platform,  # {"os":...,"libc":...,"compiler":...}
    "flags": {"ffast-math": false, "fp_contract":"off", "rounding":"rne", "ftz": false, "daz": false},
    "self_tests": {"rounding":"pass","ftz":"pass","fma":"pass","libm":"pass","neumaier":"pass","total_order":"pass"},
    "digests": digests
  }
  # S0.10 will write this as validation/numeric_policy_attest.json and include it in the gate hash.
  return attest
```

*The five tests, the attestation shape, and inclusion in the validation bundle are exactly **S0.8.9**; failure codes are listed in **S0.8.8**. The validation bundle lists `numeric_policy_attest.json` and records `math_profile_id` & flags in `MANIFEST.json`.*

---

## Notes the implementer must follow (normative)

* **No BLAS/LAPACK** or parallel reductions on decision-critical paths; use the **reference Neumaier kernels** and **total-order key** (§S0.8.10).
* The two numeric artefacts **must exist** and are part of S0.2’s artefact set; their digests appear again inside the **attestation**.
* S0.10 **must** place `numeric_policy_attest.json` into the validation bundle and include it in the `_passed.flag` gate.

This L1 set directly mirrors the frozen S0.8 text: environment guarantees (§S0.8.1), deterministic libm profile with **`lgamma`** (§S0.8.2), fixed-order reductions and kernels (§S0.8.10), explicit failure codes (§S0.8.8), the five self-tests and **attestation** (§S0.8.9), and the bundle contract (§S0.10.5). No over-engineering, no drift.

---

# S0.9 — Failure / Abort (L1)

## 1) `build_failure_payload(class, code, ctx) → failure_json`

```text
# moved to L0.Batch-F (canonical envelope, single source of truth)
function build_failure_payload(failure_class, failure_code, ctx):
  return L0.build_failure_payload(failure_class, failure_code, ctx)   # L0 Batch-F
```

*Fields, required set, and **timestamp domain (epoch-ns)** are normative; `detail`’s minimal shapes are fixed for codes like `rng_counter_mismatch`, `partition_mismatch`, `ingress_schema_violation`, `artifact_unreadable`, `dictionary_path_violation`, `hurdle_nonfinite`.*

---

## 2) `abort_run_atomic(payload, partial_partitions[])`

```text
# moved to L0.Batch-F (single canonical abort path for all states)
function abort_run_atomic(payload, partial_partitions):
  return L0.abort_run_atomic(payload, partial_partitions)              # L0 Batch-F
```

*Failure artefacts live under `…/validation/failures/fingerprint={manifest_fingerprint}/seed={seed}/run_id={run_id}/` and are committed **atomically** (temp → rename). Re-runs hitting the **same** failure with the **same** lineage never overwrite an existing committed `failure.json`. On abort: stop emitters, seal the failure dir, write optional `_FAILED.json` sentinels inside any leaked partitions, freeze RNG, and exit non-zero.*

---

## 3) `merchant_abort_log_write(rows, parameter_hash)`

```text
# moved to L0.Batch-F (parameter-scoped soft-fallback log writer)
function merchant_abort_log_write(rows, parameter_hash):
  return L0.merchant_abort_log_write(rows, parameter_hash)            # L0 Batch-F
```

*This **never** replaces a run-abort; it only records permitted soft fallbacks. It is **parameter-scoped** at `…/prep/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet`.*

---

### Notes & invariants (normative, minimal)

* **Fingerprint vs. parameter scope.** Failure bundles are **fingerprint-scoped**; parameter-scoped datasets (incl. merchant-abort log) must embed a `parameter_hash` equal to the path key. Egress/validation datasets must partition by `fingerprint={manifest_fingerprint}`.
* **Failure taxonomy & crosswalk.** Always include both `failure_class` (F1–F10) and specific `failure_code` (snake_case). Examples and class mapping are fixed.
* **Abort procedure ordering is fixed:** stop → seal failure bundle → mark partials → freeze RNG → exit non-zero.
* **Writers remain overwrite-atomic** elsewhere; validators later check partition equivalence and instance completeness (F5/F10).

This is a straight transcription of S0.9’s contract—nothing added, nothing omitted—so implementers can wire failures identically across the state.

---

# S0.10 — Outputs & Validation Bundle (L1)

## 1) `preflight_partitions_exist(parameter_hash, emit_hurdle_pi_probs)`

```text
function preflight_partitions_exist(parameter_hash, emit_hurdle_pi_probs):
  assert partition_exists("crossborder_eligibility_flags", parameter_hash),
         "E_PRE_S010:missing_crossborder_eligibility_flags"

  if emit_hurdle_pi_probs:
      assert partition_exists("hurdle_pi_probs", parameter_hash),
             "E_PRE_S010:missing_hurdle_pi_probs"

  # Immutability/idempotence context (spec): concrete partition dirs are immutable; re-runs
  # with same keys must be byte-identical or no-op. (Retention policy is out-of-band.)
  return true
```

*Why:* S0.10 must not proceed unless the **parameter-scoped** partitions produced earlier exist. This exactly mirrors §S0.10.8’s preamble and the immutability/idempotence contract.

---

## 2) `assemble_validation_bundle(ctx) → tmp_dir`

**Inputs (from earlier S0 steps):**
`ctx = { fingerprint: hex64, parameter_hash: hex64, git_commit_hex: hex40|hex64, artifacts: list, param_filenames_sorted: list, param_digests: jsonl rows, artifact_digests: jsonl rows, numeric_attest: object, math_profile_id: str, compiler_flags: map }`.

```text
function assemble_validation_bundle(ctx):
  tmp = mktempdir()   # under validation/_tmp.{uuid}

  # MANIFEST.json (normative fields)
  write_json(tmp+"/MANIFEST.json", {
    "version": "1A.validation.v1",
    "manifest_fingerprint": ctx.fingerprint,
    "parameter_hash": ctx.parameter_hash,
    "git_commit_hex": ctx.git_commit_hex,
    "artifact_count": len(ctx.artifacts),
    "math_profile_id": ctx.math_profile_id,
    "compiler_flags": ctx.compiler_flags,
    "created_utc_ns": now_ns()
  })

  # Resolutions + logs (normative file set)
  write_json(tmp+"/parameter_hash_resolved.json", {
    "parameter_hash": ctx.parameter_hash,
    "filenames_sorted": ctx.param_filenames_sorted
  })
  write_json(tmp+"/manifest_fingerprint_resolved.json", {
    "manifest_fingerprint": ctx.fingerprint,
    "git_commit_hex": ctx.git_commit_hex,
    "parameter_hash": ctx.parameter_hash,
    "artifact_count": len(ctx.artifacts)
  })
  write_jsonl(tmp+"/param_digest_log.jsonl", ctx.param_digests)
  write_jsonl(tmp+"/fingerprint_artifacts.jsonl", ctx.artifact_digests)
  write_json(tmp+"/numeric_policy_attest.json", ctx.numeric_attest)

  # Optional lints (if produced). By default they participate in the gate hash.
  if ctx.dictionary_lint is not None:
      write_text(tmp+"/DICTIONARY_LINT.txt", ctx.dictionary_lint)
  if ctx.schema_lint is not None:
      write_text(tmp+"/SCHEMA_LINT.txt", ctx.schema_lint)

  return tmp
```

*Why:* This file list and the exact field shapes are the **normative** bundle contents. Do not add/remove files unless the spec changes.

---

## 3) `compute_gate_hash_and_publish_atomically(tmp_dir, fingerprint)`

```text
function compute_gate_hash_and_publish_atomically(tmp_dir, fingerprint):
  # Gate hash over raw bytes of all files except the flag, in ASCII filename order
  files = list_ascii_sorted(tmp_dir)                            # filenames only
  H = sha256_concat_bytes([ tmp_dir+"/"+f for f in files if f != "_passed.flag" ])
  write_text(tmp_dir+"/_passed.flag", "sha256_hex = " + hex64(H) + "\n")

  # Atomic publish into fingerprint-scoped partition
  final_dir = "data/layer1/1A/validation/fingerprint="+fingerprint
  publish_atomic(tmp_dir, final_dir)
```

*Why:* `_passed.flag` is **mandatory** and must be computed exactly as specified; the bundle is then published with a **single atomic rename** under `fingerprint={manifest_fingerprint}`.

---

## Notes (normative, minimal)

* **Partitioning recap:** parameter-scoped datasets use `parameter_hash={…}`; RNG logs are `{seed, parameter_hash, run_id}`; **validation bundle** uses `fingerprint={manifest_fingerprint}` (path label `fingerprint=…`, column name `manifest_fingerprint`). Validators will enforce row/path equivalence.
* **Validation expectations (downstream/CI):** presence of every required file; `_passed.flag` must match; lineage recomputation must reproduce the two `*_resolved.json`; numeric attestation must indicate **all S0.8 tests passed**.
* **Idempotent reruns:** bundles are equivalent iff `MANIFEST.json` matches byte-for-byte and all other files (and the flag’s hash) match byte-for-byte.

This is a direct transcription of S0.10’s contract—**preflight**, **assemble**, **gate & publish**—and nothing else.

---