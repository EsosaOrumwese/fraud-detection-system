# S4·L0 — Helpers & Primitives (Zero-Truncated Poisson; logs-only)


# 0) Conventions & scope (what L0 is / isn’t)

**Purpose.** **S4·L0** is the state-local **helpers & primitives** library for the Zero-Truncated Poisson (ZTP) state. It provides: (a) pure λ/guard/regime helpers, (b) a single-attempt **Poisson adapter**, and (c) **event emitters** for the four S4 RNG event families—each followed by **exactly one** cumulative trace append. **L0 is logs-only**; it writes RNG **JSONL** logs, never Parquet egress.

**Scope (MUST).**

* **Helpers only.** No orchestration/loops (L2) and no validators (L3).
* **Logs-only producer.** S4 writes: `poisson_component(context:"ztp")` (**consuming**), `ztp_rejection` (**non-consuming**), `ztp_retry_exhausted` (**non-consuming**), `ztp_final` (**non-consuming**), plus the cumulative **`rng_trace_log`** stream. All RNG logs are partitioned by **`{seed, parameter_hash, run_id}`** (Dictionary authority).
* **Trace duty (writer responsibility).** After **each** S4 event append, the **same writer** appends **exactly one** cumulative `rng_trace_log` row for `(module, substream_label)` (saturating totals). No other sink may emit trace rows.
* **No path literals.** All paths are **Dictionary-resolved**; for **event streams** the embedded `{seed, parameter_hash, run_id}` **must byte-match** path tokens. **File order is non-authoritative**; replay/validation use counters from the envelope.
* **Numeric & RNG law.** Inherit S0: **binary64 (RNE), FMA-off, no FTZ/DAZ**; Philox substreams; **open-interval** $u∈(0,1)$; **`draws` = actual uniforms**, **`blocks` = `after−before`**. Budgets are **measured, not inferred**.

**Branch purity & universe awareness.**

* S4 is in scope **iff** **S1** marked `is_multi=true` **and** **S3** marked `is_eligible=true`. Let **`A := size(S3.candidate_set \ {home})`**. If **A=0**, **do not sample**; emit a **non-consuming** `ztp_final{K_target=0,…}` (optionally `reason:"no_admissible"` when present in the bound schema) and stop.

**Non-goals (MUST NOT).**

* No re-sampling or alteration of **`N`** (S2 fixed it).
* No country choice or order (S3/S6 own that; order authority is S3 `candidate_rank`).
* No egress or consumer gates here (they live downstream).

---

# 1) Authorities & contracts (single sources of truth)

**Single schema authority (MUST).** For 1A, **JSON-Schema** is the only schema authority; every S4 stream binds via a `schema_ref` (JSON-Pointer) into `schemas.*.yaml`. Avro is non-authoritative.

**What S4 writes (authoritative anchors & partitions).**
All RNG logs are written under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`. **Event** rows carry the full RNG envelope; **trace** rows carry only the fields defined by the trace schema (see below). For **event streams**, embedded `{seed, parameter_hash, run_id}` **must equal** the path tokens byte-for-byte. **File order is non-authoritative**; ordering comes from counters.

* **`schemas.layer1.yaml#/rng/events/poisson_component`** — **consuming** attempt rows with `context:"ztp"`.
  **Payload (min):** `{ merchant_id:int64, attempt:int≥1, k:int≥0, lambda_extra:float64, regime:"inversion"|"ptrs" }`
  **Envelope (min):** `{ ts_utc, module, substream_label, context, before, after, blocks, draws }`
  **Writer sort:** `(merchant_id, attempt)`.

* **`schemas.layer1.yaml#/rng/events/ztp_rejection`** — **non-consuming** zero marker (`k=0`); **Writer sort:** `(merchant_id, attempt)`.

* **`schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`** — **non-consuming** cap-hit marker; **Writer sort:** `(merchant_id, attempts)`.

* **`schemas.layer1.yaml#/rng/events/ztp_final`** — **non-consuming** finaliser fixing `{K_target:int≥0, lambda_extra, attempts:int≥0, regime, exhausted?:bool [, reason:"no_admissible"]?}` (emit `reason` **only** if present in the bound schema version); **Writer sort:** `(merchant_id)`.

* **`schemas.layer1.yaml#/rng/core/rng_trace_log`** — cumulative **trace** per `(module, substream_label)`; **append exactly one** row **after every** S4 event append. **Trace row fields (per schema):** `ts_utc, module, substream_label` + cumulative counters; **no `context`**, and embedded lineage is not required (lineage is enforced by the partition path).

**Label/stream registry (frozen identifiers).**
All S4 **events** use: `module = "1A.s4.ztp"`, `substream_label = "poisson_component"`, `context = "ztp"`. **Consuming vs non-consuming** is fixed: attempts consume (`draws>0` & `blocks=after−before`); markers/final are non-consuming (`draws:"0"`, `blocks=0`, `before==after`). After each append, **one** cumulative trace row is required.

**Dictionary authority (MUST).**
The **Data Dictionary** defines dataset IDs, **partitions** (`{seed, parameter_hash, run_id}`), writer sort keys, and JSONL format for RNG logs. L0 **never** hard-codes paths.

**Numeric & RNG policy (binding).**

* **binary64 (RNE), FMA-off, no FTZ/DAZ**; abort merchant if `λ` is non-finite or ≤ 0 (`NUMERIC_INVALID`).
* **Poisson regimes:** *Inversion* for `λ<10` (consumes exactly `K+1` uniforms), *PTRS* for `λ≥10` (variable ≥2). Threshold/constants are spec-fixed; budgets are **measured**.
* **Open-interval uniforms**; **timestamps are observational only**.

**Gates & upstream contracts (read-side).**

* **S1 hurdle** (presence gate): S4 in scope **only** if `is_multi=true`.
* **S2 `nb_final`** (non-consuming) fixes **`N`** (no alteration in S4).
* **S3 eligibility & admissible set:** `is_eligible=true`; **`A := size(S3.candidate_set \ {home})`** used only for the **A=0** short-circuit (no sampling; emit `K_target=0`). S4 never uses S3 order.

**Domain types (selected).**

* `merchant_id:int64` (ingress).
* `attempt:int≥1` on attempt/zero rows; `attempts:int≥0` on final/cap rows (`0` only on **A=0**).
* `regime ∈ {"inversion","ptrs"}` — chosen once per merchant; **no mid-loop switching**.

---

# 2) Reuse index (import map; do not re-implement)

**Intent.** This section names **exactly** what S4·L0 imports from earlier L0s and uses as-is. No re-plumbing, no alternative implementations. Where a helper exists in both S0 and S1 (e.g., trace totals), we **import S1’s variant qualified** and call it explicitly.

---

## 2.1 PRNG core & substreams — **S0·L0 (foundational)**

* `derive_master_material(seed_u64, manifest_fingerprint_bytes) → (M, root_key, root_ctr)` — audit-only master derivation (raw 32 bytes; referenced here only as provenance for substreams).
* `derive_substream(M, label:string, ids:Ids) → Stream{ key:u64, ctr:{hi:u64,lo:u64} }` — **order-invariant** keyed substream; message is exactly `UER("mlr:1A") || UER(label) || SER(ids)`. **SER tag set is closed**: `{iso, merchant_u64, i, j}`; **`iso` must be UPPERCASE ASCII before encoding**; any other tag → hard error.
* `philox_block(s) → (x0:u64, x1:u64, s')` — **PHILOX-2×64-10**; advances the 128-bit counter by **+1 block** per call.
* `u01(x:u64) → float64` — **strict-open** (0,1) mapping in binary64; never 0.0/1.0; endpoint remap is normative.
* `uniform1(s) → (u:float64, s', draws:u128)` — **low lane** from one block; **draws=1** (actual uniforms).
* `uniform2(s) → (u1:float64, u2:float64, s', draws:u128)` — both lanes from one block; **draws=2**; **no cache**.
* `normal_box_muller(s) → (z:float64, s', draws:u128)` — consumes **one** block; **draws=2**; cosine branch; hex-literal `TAU`.

> **Lane/budget law (MUST):** Single-uniform events use **low lane**; Box–Muller uses **both lanes** from one block. **Budgets are actual uniforms** (independent of counter delta); `blocks = after − before`.

---

## 2.2 Writer, trace & dictionary — **S1·L0 (authoritative I/O surface)**

* `begin_event_micro(module, substream_label, seed, parameter_hash, manifest_fingerprint, run_id, stream) → EventCtx` — microsecond `ts_utc` (exactly 6 digits; **truncate**); captures **before** counters and lineage.
* `end_event_emit(family, ctx, stream_after, draws_hi, draws_lo, payload)` — writes exactly **one** JSONL event row (envelope + payload); computes `blocks = u128(after) − u128(before)`; encodes **decimal-u128** `draws`. If `draws == "0"`, asserts `after == before` (**non-consuming**).
* `update_rng_trace_totals(draws_str, module, substream_label, seed, parameter_hash, run_id) → TraceTotals` — **S1 variant only (qualified import)**. **Consumes `draws_str` (decimal-u128)**, returns **saturating u64** totals, and appends **exactly one** cumulative `rng_trace_log` row per event; **same writer** must append the trace **immediately after** the event. **Trace rows do not carry the full event envelope**: they contain only `ts_utc, module, substream_label` and cumulative counters (**no `context`**; lineage via partition path). **Do not** use the S0 updater in S4.
* `dict_path_for_family(family, seed, parameter_hash, run_id) → path` — **only** way to resolve paths; **no embedded literals** anywhere in S4·L0. All RNG logs (events and trace) are **JSONL** under `{seed, parameter_hash, run_id}`.

> **Single serialization point.** Event writer + trace updater are the **only** serialization surface; orchestrators ensure no parallel double-writes. The **same writer** appends the trace **immediately after** the event for crash-safety.

---

## 2.3 Attempt capsules & guards — **S2·L0 (pure; no I/O)**

* `poisson_attempt_with_budget(lambda:float64, s_pois:Stream) → (k:i64, s':Stream, AttemptBudget)` — regime split **inversion** if `λ < 10`, **PTRS** otherwise; **budgets measured** (actual uniforms); `blocks` from counter delta. **Two uniforms per PTRS iteration**.
* `assert_finite_positive(x:float64, name:string)` — hard error if NaN/±Inf or `x ≤ 0`; used to guard `λ` before any emission.

> **PTRS constants & threshold are spec-fixed**; we inherit them unchanged.

---

## 2.4 128-bit & numeric utilities — **S1·L0 + S0·L0**

* `decimal_string_to_u128(s) → (hi:u64, lo:u64)` — authoritative parser for `draws`. **Domain:** non-negative base-10; **no leading zeros** (except `"0"`). Partner encoder below.
* `u128_to_decimal_string(hi,lo) → string` — writer’s encoder for `draws`.
* `u128_delta(after_hi,after_lo,before_hi,before_lo) → (hi,lo)`; `u128_to_uint64_or_abort(hi,lo) → u64` — used by writer & trace budget identities.

---

## 2.5 Types & tuple contracts (reused; defined upstream)

* `Stream { key:u64, ctr:{hi:u64,lo:u64} }` — Philox stream (one **block** per `philox_block`).
* `Ids = list[{ tag∈{iso, merchant_u64, i, j}, value:u64|string }]` — **typed** tuple for `derive_substream` (SER v1 only). **`iso` must be UPPERCASE ASCII**.
* `EventCtx` — from `begin_event_micro` (microsecond `ts_utc`; captures `before_{hi,lo}` and lineage).
* `TraceTotals { draws_total:u64, blocks_total:u64, events_total:u64 }` — **saturating** u64 totals for `rng_trace_log`.
* `AttemptBudget { blocks:u64, draws_hi:u64, draws_lo:u64 }` — per-event **actual-use** budgets.

---

## 2.6 Explicitly **not** imported (to prevent drift)

* Any **event wrappers** for ZTP from S0 (their modules/labels differ) — S4 defines **its own** ZTP emitters with `module="1A.s4.ztp"`, `substream_label="poisson_component"`, `context:"ztp"`.
* Any alternative **trace updaters** (S0 variant) — use **S1’s saturating** updater only (call `S1.update_rng_trace_totals` explicitly).
* Any **dictionary path literals** — all I/O must call `dict_path_for_family`.

---

## 2.7 Acceptance for §2 (checklist)

* **No re-definitions** of S0/S1/S2 helpers; imports are **qualified** where collisions exist (trace updater).
* **Budgets** are **actual uniforms used** (writer encodes decimal-u128; non-consuming events keep `before==after`, `blocks=0`, `draws="0"`).
* **Substreams** derived from `(M, label, Ids)` (order-invariant); **no cross-label chaining** or deriving from a prior event’s `after`.
* **Paths** resolved via **dictionary**; RNG partitions are exactly `{seed, parameter_hash, run_id}`; **same writer** appends **one** cumulative trace row **immediately after** each event.
* **PTRS/inversion** regime split and constants are inherited unchanged from upstream samplers.

This import map keeps S4·L0 **thin and deterministic**: we reuse PRNG/substream and writer/trace/dictionary surfaces from S0/S1 and the **Poisson attempt capsule** from S2, adding no new moving parts beyond the minimal S4 emitters that bind to S4’s schemas and labels.

---

# 3) Literals & enums (single source of identifiers)

**Goal.** Pin every **identifier** and **closed vocabulary** S4·L0 uses so emitters are unambiguous and replay-stable. These are **spec literals**—changing any is **breaking** and requires a spec revision.

## 3.1 Frozen label set (shared by all S4 events)

| Stream family                   | **module**  | **substream_label** | **context** |
|---------------------------------|-------------|---------------------|-------------|
| `rng_event_poisson_component`   | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_rejection`       | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_retry_exhausted` | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_final`           | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |

**Notes.** All S4 events share `substream_label="poisson_component"` to keep budgeting/trace under one domain; event type is distinguished by the **table/anchor** and `context:"ztp"`. After *each* event append, the **same writer** emits **exactly one** cumulative `rng_trace_log` row for this `(module, substream_label)`.

## 3.2 Stream anchors, partitions, and minima (authority binding)

**Authoritative schema anchors (JSON-Schema):**

* `schemas.layer1.yaml#/rng/events/poisson_component` — **consuming** attempt rows (`context:"ztp"`).
  **Payload (min):** `{ merchant_id:int64, attempt:int≥1, k:int≥0, lambda_extra:float64, regime:"inversion"|"ptrs" }`
  **Envelope (min):** `{ ts_utc, module, substream_label, context, before, after, blocks, draws }`
  **Writer sort:** `(merchant_id, attempt)`.
* `schemas.layer1.yaml#/rng/events/ztp_rejection` — **non-consuming** zero marker.
  **Payload (min):** `{ merchant_id:int64, attempt:int≥1, k:0, lambda_extra:float64 }`
  **Envelope (min):** as above
  **Writer sort:** `(merchant_id, attempt)`.
* `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` — **non-consuming** cap-hit marker **(abort-only)**.
  **Payload (min):** `{ merchant_id:int64, attempts:int≥1, lambda_extra:float64, aborted:true }`
  **Envelope (min):** as above
  **Writer sort:** `(merchant_id, attempts)`.
* `schemas.layer1.yaml#/rng/events/ztp_final` — **non-consuming** single acceptance record.
  **Payload (min):** `{ K_target:int≥0, lambda_extra:float64, attempts:int≥0, regime:"inversion"|"ptrs", exhausted?:bool [, reason:"no_admissible"]? }` *(emit `reason` only if the bound schema version defines it)*
  **Envelope (min):** as above
  **Writer sort:** `(merchant_id)`.
* `schemas.layer1.yaml#/rng/core/rng_trace_log` — cumulative **trace** per `(module, substream_label)`.
  **Trace row fields:** `ts_utc, module, substream_label` + cumulative counters (**no `context`**; lineage via partition path)
  **Writer sort:** `(module, substream_label, rng_counter_after_hi, rng_counter_after_lo)`.

**Partitions (path keys) — logs only.** All S4 streams are written under `{ seed, parameter_hash, run_id }` (Dictionary). For **event streams**, embedded `{seed, parameter_hash, run_id}` **must byte-match** path tokens. `rng_trace_log` omits embedded lineage; lineage is enforced by the partition path. **File order is non-authoritative**; order/replay use envelope counters.

**Budget identities.**

* **Consuming attempts** (`poisson_component`): `blocks == after − before` and `draws > 0` (decimal-u128).
* **Non-consuming** (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`): `before == after`, `blocks = 0`, `draws = "0"`.

## 3.3 Closed enums & constants (frozen vocabularies)

* `regime ∈ {"inversion","ptrs"}` — chosen by a **spec-fixed** threshold at **λ★ = 10**; fixed per merchant (no mid-loop switching).
* `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` — governed in cross-border config; participates in `parameter_hash`. Default cap **64** unless governance overrides.
* `reason ∈ {"no_admissible"}` (optional on `ztp_final`) — **present only** if the bound schema version defines it.
* **Numeric profile literals (binding):** **binary64, RNE, FMA-off, no FTZ/DAZ;** strict-open `u∈(0,1)`; budgets are **measured, not inferred**.

## 3.4 Dictionary roles (IDs, not paths)

All dataset IDs, partitions, and writer-sort keys are defined in the **Data Dictionary**; L0 must never embed path literals. All path resolution for S4 families uses the dictionary entries referenced above.

---

**Acceptance for §3.** Emitters **must** use the literals and enums above verbatim; any deviation (labels, context, enums, partitions) is a protocol violation. Counter/order semantics and the one-trace-per-event duty are part of these identifiers’ contract.

---

# 4) Types & records (records only; no logic)

> Goal: fix the exact record shapes S4·L0 reads/writes so implementers can code against **closed, testable** structures. JSON encoding follows the bound schema anchors. `draws` is always a **decimal-u128** string.

---

## 4.1 Lineage & partitions (logs-only)

**Lineage**

```text
type Lineage = {
  seed: u64,                   # logs partition
  parameter_hash: Hex64,       # logs partition
  manifest_fingerprint: Hex64, # embedded only (not a path key)
  run_id: Hex32                # logs partition; never enters seeding
}
```

**Partition keys (must match path tokens byte-for-byte):** `{ seed, parameter_hash, run_id }`. *File order is non-authoritative; counters provide order.*

---

## 4.2 PRNG substream & counters

**Stream (Philox 2×64)**

```text
type Stream = {
  key: u64,                    # derived from (M, label, Ids)
  ctr_hi: u64, ctr_lo: u64     # 128-bit counter split; +1 block per philox_block(...)
}
```

**Ids (substream key tuple; closed set)**

```text
type Ids = list[{ tag: "merchant_u64" | "iso" | "i" | "j", value: u64 | string }]
# iso must be UPPERCASE ASCII before encoding
```

*Block arithmetic:* `blocks := u128(after) − u128(before)`; **independent** of `draws`. Single-uniform events use the **low lane**; two-uniform events use **both lanes** from one block.

---

## 4.3 RNG envelope (all S4 **event** rows)

**Envelope (minimum)**

```text
type Envelope = {
  ts_utc: string,              # UTC timestamp, exactly 6 fractional digits (truncate)
  module: "1A.s4.ztp",
  substream_label: "poisson_component",
  context: "ztp",
  rng_counter_before_lo: u64,
  rng_counter_before_hi: u64,
  rng_counter_after_lo:  u64,
  rng_counter_after_hi:  u64,
  blocks: u64,                 # = u128(after) − u128(before)
  draws:  DecU128              # actual uniforms; "0" on non-consuming
}
```

**Decimal-u128 domain for `draws`:** non-negative base-10; **no leading zeros** (except `"0"`).

**Envelope identities**

* **Consuming** (`poisson_component`): `after > before`, `blocks = after − before`, `draws > "0"`.
* **Non-consuming** (`ztp_rejection` / `ztp_retry_exhausted` / `ztp_final`): `before == after`, `blocks = 0`, `draws = "0"`.

*Note:* `ts_utc` is observational only; ordering/replay use counters.

---

## 4.4 Trace (cumulative) rows

**TraceTotals (saturating)**

```text
type TraceTotals = {
  draws_total:  u64,           # saturating, cumulative
  blocks_total: u64,           # saturating, cumulative
  events_total: u64            # saturating, cumulative
}
```

**Trace row (minimum)**

```text
type Trace = {
  module: "1A.s4.ztp",
  substream_label: "poisson_component",
  totals: TraceTotals,         # cumulative totals (saturating u64)
  rng_counter_after_hi: u64,   # persisted for replay selection
  rng_counter_after_lo: u64,
  ts_utc: string               # UTC timestamp, exactly 6 fractional digits
}
```

*Partitions:* `{ seed, parameter_hash, run_id }`. *No embedded lineage; lineage is enforced by the partition path.* *Trace rows have no `context`.*
*Emission rule:* **after each event append, the same writer emits exactly one** cumulative trace row for `(module, substream_label)`; for non-consuming events only `events_total` increments.

---

## 4.5 Attempt budget (values-only)

```text
type AttemptBudget = {
  blocks:   u64,               # measured from counters (not inferred)
  draws_hi: u64,
  draws_lo: u64                # decimal-u128(draws) parsed to (hi, lo)
}
```

*Budgets are measured; counters vs draws independence holds.*

---

## 4.6 Payload minima (per S4 stream)

**Type aliases**

```text
type merchant_id = int64
type attempt    = int            # ≥1 on attempt / rejection
type attempts   = int            # ≥0 on final / cap; 0 only for A=0
type k          = int            # ≥0 Poisson draw
type K_target   = int            # ≥0 accepted/capped target
type regime     = "inversion" | "ptrs"
type exhausted  = bool
type reason     = "no_admissible"  # optional (schema-versioned)
```

### a) `rng_event_poisson_component` — **consuming attempt**

```text
type PoissonComponent = {
  merchant_id:  merchant_id,
  attempt:      attempt,        # 1-based, strictly increasing
  k:            k,              # ≥0
  lambda_extra: float64,
  regime:       regime
}
# Writer sort: (merchant_id, attempt) ; Envelope: consuming identities must hold
```

### b) `rng_event_ztp_rejection` — **non-consuming zero marker**

```text
type ZtpRejection = {
  merchant_id:  merchant_id,
  attempt:      attempt,        # ≥1
  k:            0,
  lambda_extra: float64
}
# Writer sort: (merchant_id, attempt) ; Envelope: non-consuming identities must hold
```

### c) `rng_event_ztp_retry_exhausted` — **non-consuming cap-hit**

```text
type ZtpRetryExhausted = {
  merchant_id:  merchant_id,
  attempts:     attempts,       # == last attempt index (≥1)
  lambda_extra: float64,
  aborted:      true
}
# Writer sort: (merchant_id, attempts) ; Envelope: non-consuming identities must hold
```

### d) `rng_event_ztp_final` — **non-consuming finaliser**

```text
type ZtpFinal = {
  merchant_id:   merchant_id,
  K_target:      K_target,      # 0 on A=0 short-circuit or downgrade policy
  lambda_extra:  float64,
  attempts:      attempts,      # == last attempt index (or 0 for A=0)
  regime:        regime,
  exhausted?:    exhausted,     # present only on cap path
  reason?:       reason         # present only if schema version defines it
}
# Writer sort: (merchant_id) ; Envelope: non-consuming identities must hold
```

*For A=0, emit exactly one `ztp_final{ K_target:0, attempts:0 }` and nothing else.*

---

## 4.7 Sorting, uniqueness & cardinality (writer-side contract)

* **Sort keys (stable):** attempts/rejections → `(merchant_id, attempt)`; cap marker → `(merchant_id, attempts)`; finaliser → `(merchant_id)`.
* **Uniqueness (per merchant):** ≤1 `poisson_component` per `(merchant_id, attempt)`; ≤1 `ztp_rejection` per `(merchant_id, attempt)`; ≤1 `ztp_retry_exhausted`; ≤1 `ztp_final` for a resolved merchant.
* **Attempt indices:** 1-based, strictly increasing; `ztp_final.attempts` equals the last attempt index (or `0` on A=0). **No regime switching** mid-merchant.

---

## 4.8 Domain/equality rules (local to types)

* **Exact equality:** integers, counters, regime enums, lineage tokens.
* **Float rule that affects control flow:** the **regime split** at `λ < 10` vs `≥ 10` (binary64; no epsilons).
* **Open-interval uniforms:** `u ∈ (0,1)` strictly; `draws` reflects **actual** uniforms.

---

# 5) Numeric & RNG invariants (must-have rules)

> These are the **binding math & RNG rules** S4·L0 must uphold on every row it emits. Violations are producer bugs and validation failures.

## 5.1 Floating-point profile & equality (binding)

* **IEEE-754 binary64**, **round-to-nearest-even**, **FMA-off**, **no FTZ/DAZ**; fixed operation order.
* `ts_utc` uses **microsecond** precision with **exactly 6 fractional digits** (truncate, no rounding).
* **No epsilons** / fuzzy checks in producer decisions.
* **Only one float comparison gates control flow:** regime split at $\lambda < 10$ vs $\lambda \ge 10$ (apply directly in binary64).
* $\lambda_{\text{extra}}$ and the chosen **regime** are **computed once and fixed per merchant** for all S4 rows.
* Non-finite or $\lambda_{\text{extra}} \le 0$ → hard `NUMERIC_INVALID`.

## 5.2 Uniforms & budgets (strict-open, measured)

* Uniform mapping is **strict-open** $u \in (0,1)$ via the normative `u01`; never produce `0.0` or `1.0`.
* **Budgets are measured, not inferred.** Every event carries:

  * `blocks = u128(after) - u128(before)` (uint64),
  * `draws` = **decimal-u128** string of **actual uniforms consumed**.
* **Decimal-u128 domain for `draws`:** non-negative base-10; **no leading zeros** (except `"0"`).
* Independence holds: `draws` reflects uniforms; `blocks` reflects counter delta.

## 5.3 Poisson regimes & sampler budgets (fixed & measurable)

* **Spec-fixed threshold:**

  * **Inversion** when $\lambda < 10$ → consumes **exactly $K+1$** uniforms for draw $K$.
  * **PTRS** when $\lambda \ge 10$ → consumes a **variable count (≥2)** per attempt.
* Constants are normative (pinned upstream). **Budgets come from the sampler**, not formulas.

## 5.4 Envelope identities (consuming vs non-consuming)

* **Consuming attempt** (`poisson_component`, `context:"ztp"`): `after > before`, `blocks == after - before`, `draws > "0"`.
* **Non-consuming** (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`): `before == after`, `blocks == 0`, `draws == "0"`.

## 5.5 Ordering & replay (counters are the total order)

* **File order is non-authoritative.** Ordering & replay use **counters only** (monotone, non-overlapping per merchant/substream).
* **Timestamps are observational**; they never determine order.
* Replays must reconstruct the same sequence and acceptance under these fixed literals.

## 5.6 Substreams, lanes & counters (discipline)

* Substreams are **order-invariant** keyed streams (fingerprint, seed, label, ids). **No cross-label chaining**; never derive from a prior event’s `after`.
* Single-uniform events use the **low lane**; two-uniform events use **both lanes from one block**.

## 5.7 Trace duty & budgets (writer responsibility)

* After **each S4 event append**, the **same writer immediately appends** **exactly one** cumulative `rng_trace_log` row for `(module, substream_label)` (saturating totals).
* **Non-consuming events**: increment **`events_total` only**; `draws_total` and `blocks_total` **do not change**.
* No other sink may emit trace rows.

## 5.8 Concurrency, serialism & idempotence

* **Serial per merchant:** the attempt loop is single-threaded with fixed iteration order; parallelise **across** merchants only.
* Merges are **stable** w\.r.t. writer sort keys.
* Re-runs on identical inputs are **byte-identical**.
* **Zero-row slices write nothing**.

---

# 6) Substream derivation map (order-invariant)

**Goal.** Fix *exactly* how S4 derives its keyed PRNG substream(s). This ensures **bit-replay** and lets validators reconstruct counters from lineage + label + ids with zero guesswork. The derivation uses the **S0 keyed mapping** and the **closed SER tag set**; **no chaining** from previous events is allowed.

---

## 6.1 One label, one domain (all S4 events share one substream)

* **Label (ℓ):** `"poisson_component"`
* **Module:** `"1A.s4.ztp"` (event/trace rows share this module; the **label** keys the PRNG)
* **Context:** `"ztp"` (payload/anchor only; **not** part of the PRNG key)
* **Domain rule:** All four S4 families (attempt, zero-marker, cap-marker, finaliser) **share** this `(module, substream_label)` so budgeting/trace live under one domain; event type is distinguished by the schema anchor and `context:"ztp"`.
* **Trace duty:** After **each** event append, the **same writer** appends the cumulative `rng_trace_log` row **immediately after** the event row (one-per-event).

**Dictionary & partitions.** All RNG logs (events and trace) are dictionary-resolved under partitions `{seed, parameter_hash, run_id}`. For **event streams**, embedded `{seed, parameter_hash, run_id}` **must byte-match** path tokens. `rng_trace_log` omits embedded lineage; lineage is enforced by the partition path. Trace rows have **no** `context`.

---

## 6.2 Typed IDs (SER v1) for S4

* **SER tag set (closed):** `{ iso, merchant_u64, i, j }` — any other tag → hard error (`ser_unsupported_id`).
* **S4 choice:** **merchant-scoped** substream:

  ```text
  Ids = [ { tag:"merchant_u64", value: merchant_u64 } ]
  ```

  `merchant_u64` is the canonical S0 scalar:

  ```text
  merchant_u64 = LOW64( SHA256( LE64(merchant_id:int64) ) )
  ```

  Use the S0 helper; do **not** re-implement. *(ISO, when used in other states, must be UPPERCASE ASCII before UER/SER; S4 doesn’t use `iso`.)*

---

## 6.3 Normative message layout (order-invariant)

All S4 substreams are derived by the **S0 keyed mapping**:

* **Master bytes:** `M = derive_master_material(seed, manifest_fingerprint_bytes)` (audit-only; upstream).
* **Message:**

  ```text
  msg = UER("mlr:1A") || UER(label) || SER(Ids)   # no delimiters
  ```
* **Stream key/counter:**

  ```text
  H   = SHA256(M || msg)
  key = LOW64(H)
  ctr = ( BE64(H[16:24]), BE64(H[24:32]) )
  ```
* **Block advance:** each `philox_block` call advances the unsigned 128-bit counter by **+1**.

**Strict rules.**

* **Order-invariant:** `SER(Ids)` is a typed tuple; do **not** sort or re-order fields.
* **No counter chaining:** never derive a substream from a prior event’s `after`. Each `(label, Ids)` defines its own base counter; subsequent counters evolve only by block steps.
* **Field names as emitted by writers:** `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}`.

---

## 6.4 S4 label → Ids map (authoritative)

| S4 stream family              | PRNG **label** used   | **Ids** (typed SER v1)                            |
|-------------------------------|-----------------------|---------------------------------------------------|
| `poisson_component` (attempt) | `"poisson_component"` | `[ { tag:"merchant_u64", value: merchant_u64 } ]` |
| `ztp_rejection` (zero)        | `"poisson_component"` | `[ { tag:"merchant_u64", value: merchant_u64 } ]` |
| `ztp_retry_exhausted` (cap)   | `"poisson_component"` | `[ { tag:"merchant_u64", value: merchant_u64 } ]` |
| `ztp_final` (finaliser)       | `"poisson_component"` | `[ { tag:"merchant_u64", value: merchant_u64 } ]` |

*Note.* All four families share the same PRNG domain and thus the same **trace** domain; after **each** event append, the **same writer** appends **exactly one** cumulative trace row **immediately after** writing the event.

---

## 6.5 Validator-replay recipe (for L3 & implementers)

Given one S4 row with `{seed, parameter_hash, manifest_fingerprint, run_id}` and `merchant_id`:

1. **Attempt index discipline.** Verify per-merchant `attempt` is **1-based, strictly increasing**.
2. **Merchant key.** Compute `merchant_u64 = LOW64(SHA256(LE64(merchant_id)))`.
3. **Master & substream.**

   * `M = derive_master_material(seed, hex_to_bytes(manifest_fingerprint))`
   * `s0 = derive_substream(M, "poisson_component", [ {tag:"merchant_u64", value: merchant_u64} ])`
     Let `base_ctr := s0.ctr`.
4. **Expected `before` counter.**

   * If `attempt == 1`: require `envelope.before == base_ctr`.
   * If `attempt > 1`: let `B_prev := Σ blocks` over all prior events for this merchant in this substream; require

     ```text
     expected_before = base_ctr + B_prev   # u128 addition modulo 2^128
     envelope.before == expected_before
     ```
5. **Envelope/budget checks.**

   * **Consuming attempts:** advance by Philox blocks and map lanes to uniforms per sampler; verify `after`, `blocks`, and that `draws` equals **actual uniforms consumed**.
   * **Non-consuming markers/final:** assert `before == after`, `blocks == 0`, `draws == "0"`.
6. **Trace duty.** Confirm exactly **one** cumulative trace row follows **immediately after** the event row in the same partition, for `(module, substream_label)`; non-consuming rows increment `events_total` only.

---

## 6.6 Acceptance for §6

* **Single substream domain** for all S4 events: `label="poisson_component"`, `Ids=[merchant_u64]`.
* **Mapping is S0-normative**: `UER("mlr:1A") || UER(label) || SER(Ids)`; **SER tag set is closed**.
* **No cross-label chaining**; **order-invariant** derivation; counters advance **one block per call**.
* **Dictionary partitions** `{seed, parameter_hash, run_id}`; **event** rows embed lineage that **byte-matches** path tokens; trace rows omit embedded lineage and `context`.
* **Trace duty:** after **every** event append, the **same writer** appends **one** cumulative trace row **immediately after** the event.

---

# 7) Regime helper & guards (pure, no I/O)

**Purpose.** Provide tiny, **pure** helpers that (a) validate the merchant’s $\lambda_{\text{extra}}$ and (b) deterministically label the Poisson **regime** (`"inversion"` or `"ptrs"`) from the spec-fixed threshold. **No I/O, no counters, no trace**—values only. These are called by L1 before any attempt (and on the **A=0** short-circuit path).

---

## 7.1 Inputs & outputs (closed contracts)

**Input**
`lambda_extra : float64` — computed once in S4 (binary64, fixed order, §9.3). **Must be finite and > 0**.

**Output**

```text
type LambdaRegime = {
  lambda_extra: float64,           # binary64; reused for all S4 rows of the merchant
  regime: "inversion" | "ptrs"     # fixed per merchant from the threshold rule
}
```

---

## 7.2 Guard: lambda must be finite and strictly positive (MUST)

**Reuse (from S2·L0):**
`assert_finite_positive(x: float64, name: string) -> float64 | NUMERIC_INVALID`

* Fails with **NUMERIC_INVALID** if `x` is NaN/±Inf or $x \le 0$.
* Producer uses binary64, RNE, FMA-off; **no epsilons**.

---

## 7.3 Regime selection: spec-fixed threshold at $\lambda^\star = 10$ (MUST)

**Helper (pure):**
`compute_poisson_regime(lambda_extra: float64) -> "inversion" | "ptrs"`

* Binary64 decision (no epsilons):

  * if $\lambda_{\text{extra}} < 10$ → `"inversion"`
  * else $(\lambda_{\text{extra}} \ge 10)$ → `"ptrs"`
* **Regime is fixed per merchant** (no mid-loop switching).

---

## 7.4 Freezing the pair (one-time evaluation)

**Helper (pure):**
`freeze_lambda_regime(lambda_extra_raw: float64) -> LambdaRegime | NUMERIC_INVALID`

**Steps**

1. $\lambda \leftarrow$ `assert_finite_positive(lambda_extra_raw, "lambda_extra")`; else **NUMERIC_INVALID**.
2. $r \leftarrow$ `compute_poisson_regime(λ)`.
3. Return `{ lambda_extra: λ, regime: r }`.
   **Invariant:** Use the returned `LambdaRegime` **verbatim** for all S4 rows (attempts, markers, finaliser) for that merchant.

---

## 7.5 A=0 short-circuit still derives regime (no attempts)

If admissible foreign set size **$A=0$**, **do not sample**. Still compute $\lambda_{\text{extra}}$ and derive **`regime` once**, then emit a **non-consuming** `ztp_final{ K_target=0, attempts:0, regime, lambda_extra, … }` and stop. *(Optional `reason:"no_admissible"` only if the bound schema version defines it.)*

---

## 7.6 What these helpers do **not** do

* Do **not** read/write streams, envelopes, or trace.
* Do **not** select countries or realise/cap $K$ (that is S6).
* Do **not** expose sampler internals; they only supply the **label** used by S2’s Poisson capsule.

---

## 7.7 Acceptance for §7 (producer-side checklist)

* $\lambda_{\text{extra}}$ validated **once** with `assert_finite_positive`; failure ⇒ **NUMERIC_INVALID**, **no events**.
* `regime` derived **once** by the $\lambda^\star = 10$ rule; held constant for the merchant.
* On **$A=0$**, emit only the short-circuit `ztp_final` after deriving $(\lambda, \text{regime})$; **no attempts**.
* No I/O in §7 helpers; L1/L2 perform emission and tracing.

---

# 8) Single-attempt capsule adapter (pure; no emission)

**Purpose.** Provide a **tiny, pure adapter** that performs **one** Poisson attempt at merchant scope and returns the **draw** $k$, the **updated stream**, and the **measured budgets**—with **no I/O, no envelopes, no trace**. The caller (L1) decides how to treat $k$ (zero ⇒ rejection marker; $\ge 1$ ⇒ acceptance) and handles ZTP retry/cap logic.

---

## 8.1 Inputs / outputs (closed contracts)

**Inputs (values only):**

* `lambda_extra : float64` — S4’s Poisson intensity, already computed once in binary64 and **guarded finite & > 0** (see §7).
* `regime : "inversion"|"ptrs"` — derived once from the **spec-fixed** threshold at $\lambda^\star=10$ (see §7); passed for **consistency checks** only.
* `s_before : Stream` — the merchant-scoped **poisson_component** substream (see §6). One attempt advances this stream by an integer number of **blocks**.
* **Precondition:** $A=0$ short-circuit **does not** call this adapter.

**Outputs:**

```text
(k: int≥0, s_after: Stream, bud: AttemptBudget)
# AttemptBudget = { blocks:u64, draws_hi:u64, draws_lo:u64 }  // measured
```

* `k` may be `0` (caller emits `ztp_rejection` then decides retry/cap).
* `bud` is **measured**: `blocks = u128(after) − u128(before)`; `draws` will be encoded by the caller via `u128_to_decimal_string(bud.draws_hi, bud.draws_lo)`.

---

## 8.2 Adapter behavior (pure)

**Helper:**
`poisson_attempt_once(lambda_extra: float64, regime: "inversion"|"ptrs", s_before: Stream) -> (k, s_after, AttemptBudget)`

1. **Re-guard (defensive):** `assert_finite_positive(lambda_extra, "lambda_extra")` → else **NUMERIC_INVALID** (propagate; no emission).
2. **Consistency invariant (no branching):**
   `assert compute_poisson_regime(lambda_extra) == regime`  // producer invariant
3. **Delegate to S2 capsule (one call):**
   `(k, s_after, bud) := poisson_attempt_with_budget(lambda_extra, s_before)`
   – **Inversion** for $\lambda < 10$ consumes **exactly $K+1$** uniforms for draw $K$;
   – **PTRS** for $\lambda \ge 10$ consumes a **variable count (≥2)**;
   – budgets are **measured** inside the capsule.
4. **Return** `(k, s_after, bud)`; **no** envelopes, **no** trace, **no** attempt indexing here (caller tracks `attempt = 1,2,…`).

---

## 8.3 Preconditions & non-goals

* **Preconditions:** `(λ, regime)` frozen once per merchant (§7); `s_before` is the merchant-scoped substream (§6); $A=0$ **must not** call this adapter.
* **Non-goals:** no ZTP loop or cap policy—**one attempt only**; caller decides retry/stop and emits the appropriate event (attempt/rejection/exhausted/final).

---

## 8.4 Invariants guaranteed to the caller

* **Counters & lanes (per S2 sampler):** `s_after` advances by an integer number of **blocks**; single-uniform steps use **low lane**; two-uniform steps use **both lanes** from one block.
* **Budgets:** `bud.blocks == u128(after) − u128(before)`; `bud.draws_hi/lo` encode **actual uniforms** (caller encodes `draws` as decimal-u128).
* **Regime measurability:** for $\lambda < 10$, sampler consumes **exactly $K+1$** uniforms; for $\lambda \ge 10$, **≥2 uniforms** per attempt.

---

## 8.5 Acceptance for §8 (checklist)

* Calls **S2** `poisson_attempt_with_budget` **exactly once**; **no** event writing, **no** trace append here.
* Does **not** compute attempt index or decide ZTP loop/cap; returns `k` (possibly 0) + `bud` + `s_after`.
* Upholds numeric guard and $\lambda^\star = 10$ regime consistency via `assert_finite_positive` / `compute_poisson_regime` **without** altering sampler behavior.
* Leaves all emission to §9 emitters, which will stamp schema-correct envelopes and append **exactly one** cumulative trace per event.

---

# 9) Event emitters (the only I/O in L0; **one event → one trace**)

### Shared literals

```pseudocode
const MODULE          = "1A.s4.ztp"
const SUBSTREAM_LABEL = "poisson_component"         # shared by all S4 events
const CONTEXT         = "ztp"                       # stamped in envelope by the writer

# Dictionary families (Data Dictionary resolves these IDs to paths)
const FAM_POISSON     = "rng_event_poisson_component"   # schema: schemas.layer1.yaml#/rng/events/poisson_component
const FAM_REJECTION   = "rng_event_ztp_rejection"       # schema: schemas.layer1.yaml#/rng/events/ztp_rejection
const FAM_EXHAUSTED   = "rng_event_ztp_retry_exhausted" # schema: schemas.layer1.yaml#/rng/events/ztp_retry_exhausted
const FAM_FINAL       = "rng_event_ztp_final"           # schema: schemas.layer1.yaml#/rng/events/ztp_final
const FAM_TRACE       = "rng_trace_log"                 # schema: schemas.layer1.yaml#/rng/core/rng_trace_log
```

*All four families share one trace domain `(MODULE, SUBSTREAM_LABEL)`. After **each** event append, the **same writer immediately appends** **exactly one** cumulative trace row (saturating totals). File order is non-authoritative; counters give total order. Budgets are **measured, not inferred**.*

### Shared types (by reference)

```pseudocode
type Lineage       = { seed:u64, parameter_hash:hex64, manifest_fingerprint:hex64, run_id:hex32 }
type Stream        = { key:u64, ctr:{hi:u64, lo:u64} }                     # §6
type LambdaRegime  = { lambda_extra:float64, regime: "inversion"|"ptrs" }  # §7
type AttemptBudget = { blocks:u64, draws_hi:u64, draws_lo:u64 }            # §8
type TraceTotals   = { blocks_total:u64, draws_total:u64, events_total:u64 }# saturating
```

*Writer/trace surfaces from S1·L0:* `begin_event_micro`, `end_event_emit`, `update_rng_trace_totals(draws_str, module, substream_label, seed, parameter_hash, run_id) -> TraceTotals`, `u128_delta`, `u128_to_uint64_or_abort`, `u128_to_decimal_string`.

---

## 9.1 `event_poisson_ztp` — **consuming attempt** → `poisson_component`

**When:** once per attempt index (1-based, strictly increasing) immediately after a **single** sampler step (§8). This row records draw $k \ge 0$ and the **measured budgets**.

```pseudocode
proc event_poisson_ztp(
    merchant_id : int64,
    lineage     : Lineage,              # {seed, parameter_hash, manifest_fingerprint, run_id}
    s_before    : Stream,               # substream BEFORE attempt
    s_after     : Stream,               # substream AFTER attempt (from sampler)
    lr          : LambdaRegime,         # {lambda_extra>0 finite, regime}
    attempt     : int,                  # ≥1, strictly increasing per merchant
    k           : int,                  # ≥0 (0 ⇒ caller will emit ztp_rejection)
    bud         : AttemptBudget,        # {blocks, draws_hi, draws_lo} — measured
) -> next: TraceTotals

  # Preconditions (MUST)
  assert attempt ≥ 1
  assert lr.lambda_extra > 0 and is_finite(lr.lambda_extra)

  # Writer prelude (captures ts_utc micro + 'before' counters; embeds lineage; stamps CONTEXT in envelope)
  ctx := begin_event_micro(MODULE, SUBSTREAM_LABEL,
                           lineage.seed, lineage.parameter_hash,
                           lineage.manifest_fingerprint, lineage.run_id,
                           s_before)

  # Envelope/stream alignment (MUST)
  assert ctx.before_hi == s_before.ctr.hi and ctx.before_lo == s_before.ctr.lo

  # Consuming attempt identities (MUST): blocks == after−before ; draws > "0"
  (d_hi, d_lo) := u128_delta(s_after.ctr.hi, s_after.ctr.lo, s_before.ctr.hi, s_before.ctr.lo)
  assert bud.blocks == u128_to_uint64_or_abort(d_hi, d_lo)
  assert (bud.draws_hi, bud.draws_lo) > 0_u128

  # Payload (schema minima; CONTEXT is envelope-only, not payload)
  payload := {
    merchant_id  : merchant_id,
    attempt      : attempt,
    k            : k,
    lambda_extra : lr.lambda_extra,
    regime       : lr.regime
  }

  # Emit event row (writer computes blocks = after−before; encodes decimal-u128 draws; stamps CONTEXT)
  end_event_emit(FAM_POISSON, ctx, s_after, bud.draws_hi, bud.draws_lo, payload)

  # One-event → one-trace (saturating totals). Draws_total adds this event’s draws.
  draws_str := u128_to_decimal_string(bud.draws_hi, bud.draws_lo)
  next := trace_after_event_s4(lineage,
                                  ctx.before_hi, ctx.before_lo,
                                  s_after.ctr.hi, s_after.ctr.lo,
                                  draws_str)

  # Writer-sort key respected: (merchant_id, attempt)
  return next
end
```

*Note.* If `k == 0`, the caller **must** immediately emit `ztp_rejection{attempt}` (non-consuming) with identical `lambda_extra`; counters unchanged.

---

## 9.2 `emit_ztp_rejection_nonconsuming` — **zero marker** → `ztp_rejection`

**When:** immediately after a consuming attempt whose draw `k==0`. Records the rejection; **does not** advance counters; `draws = "0"`.

```pseudocode
proc emit_ztp_rejection_nonconsuming(
    merchant_id : int64,
    lineage     : Lineage,
    s_current   : Stream,       # counters stay the same (before==after)
    lr          : LambdaRegime,
    attempt     : int,          # == attempt of the preceding consuming row
) -> next: TraceTotals

  assert attempt ≥ 1

  ctx := begin_event_micro(MODULE, SUBSTREAM_LABEL,
                           lineage.seed, lineage.parameter_hash,
                           lineage.manifest_fingerprint, lineage.run_id,
                           s_current)

  # Non-consuming identities are enforced by writer (before==after, blocks=0, draws="0")
  payload := {
    merchant_id  : merchant_id,
    attempt      : attempt,
    k            : 0,
    lambda_extra : lr.lambda_extra
  }

  end_event_emit(FAM_REJECTION, ctx, /*stream_after*/ s_current, /*draws_hi,draws_lo*/ 0, 0, payload)

  next := trace_after_event_s4(lineage,
                                  ctx.before_hi, ctx.before_lo,
                                  s_current.ctr.hi, s_current.ctr.lo,
                                  "0")

  # Writer-sort key: (merchant_id, attempt)
  return next
end
```

---

## 9.3 `emit_ztp_retry_exhausted_nonconsuming` — **cap-hit marker (abort-only)** → `ztp_retry_exhausted`

**When:** the governed zero-draw **cap** is reached before acceptance. There is at most **one** such row per merchant. Policy application (abort vs downgrade) is handled upstream; this is only the marker.

```pseudocode
proc emit_ztp_retry_exhausted_nonconsuming(
    merchant_id : int64,
    lineage     : Lineage,
    s_current   : Stream,       # counters unchanged
    lr          : LambdaRegime,
    attempts    : int,          # == last attempt index (≥1)
) -> next: TraceTotals

  assert attempts ≥ 1

  ctx := begin_event_micro(MODULE, SUBSTREAM_LABEL,
                           lineage.seed, lineage.parameter_hash,
                           lineage.manifest_fingerprint, lineage.run_id,
                           s_current)

  payload := {
    merchant_id  : merchant_id,
    attempts     : attempts,
    lambda_extra : lr.lambda_extra,
    aborted      : true          # abort-only marker; required by bound schema
  }

  end_event_emit(FAM_EXHAUSTED, ctx, /*stream_after*/ s_current, /*draws_hi,draws_lo*/ 0, 0, payload)

  next := trace_after_event_s4(lineage,
                                  ctx.before_hi, ctx.before_lo,
                                  s_current.ctr.hi, s_current.ctr.lo,
                                  "0")

  # Writer-sort key: (merchant_id, attempts)
  return next
end
```

---

## 9.4 `emit_ztp_final_nonconsuming` — **single acceptance record** → `ztp_final`

**When:** exactly **once per resolved merchant**—after acceptance (`k≥1`), after **A=0 short-circuit** (no attempts), or after **policy downgrade**. Absent only on hard abort.

```pseudocode
proc emit_ztp_final_nonconsuming(
    merchant_id   : int64,
    lineage       : Lineage,
    s_current     : Stream,                 # counters unchanged
    lr            : LambdaRegime,           # {lambda_extra, regime}
    K_target      : int,                    # ≥1 on acceptance; 0 on A=0 or downgrade
    attempts      : int,                    # ≥0; 0 only on A=0
    exhausted_opt : optional<bool>,         # present/true only for downgrade policy
    reason_opt    : optional<"no_admissible">, # only if schema version includes it (A=0 only)
) -> next: TraceTotals

  assert K_target ≥ 0
  assert attempts ≥ 0
  if attempts == 0:           assert K_target == 0            # A=0 short-circuit
  if exhausted_opt.present:   assert K_target == 0            # downgrade ⇒ K_target=0
  if reason_opt.present:      assert K_target == 0 and attempts == 0  # A=0 only, schema permitting

  ctx := begin_event_micro(MODULE, SUBSTREAM_LABEL,
                           lineage.seed, lineage.parameter_hash,
                           lineage.manifest_fingerprint, lineage.run_id,
                           s_current)

  payload := {
    merchant_id  : merchant_id,
    K_target     : K_target,
    lambda_extra : lr.lambda_extra,
    attempts     : attempts,
    regime       : lr.regime
  }
  if exhausted_opt.present: payload.exhausted := exhausted_opt.value
  if reason_opt.present:    payload.reason    := reason_opt.value   # only if schema has this field

  end_event_emit(FAM_FINAL, ctx, /*stream_after*/ s_current, /*draws_hi,draws_lo*/ 0, 0, payload)

  next := trace_after_event_s4(lineage,
                                  ctx.before_hi, ctx.before_lo,
                                  s_current.ctr.hi, s_current.ctr.lo,
                                  "0")

  # Writer-sort key: (merchant_id)
  return next
end
```

---

### Writer obligations (apply to **all** emitters)

* **Dictionary resolution only.** No path literals; partitions are exactly `{seed, parameter_hash, run_id}` and **must byte-match** embedded lineage on **event** rows.
* **Same-writer immediacy.** The **same writer** appends the trace **immediately after** writing the event row (crash-safe; prevents double-trace).
* **Zero-row discipline & idempotence.** If a slice yields no rows, write nothing. Re-runs with identical inputs produce **byte-identical** content; if the partition is complete, the writer **no-ops** (skip-if-final).
* **Budget identities.** Consuming attempt rows: `after > before`, `blocks == after - before`, `draws > "0"`. Non-consuming markers/final: `before == after`, `blocks = 0`, `draws = "0"`. **Budgets are measured, not inferred.**

---

# 10) Trace duty (writer responsibility; saturating)

> **What this section does.** It pins the **one-event → one-trace** contract for S4, using the **S1·L0 trace writer** with **saturating** totals. The trace is cumulative per **(module, substream_label)** and uses the same partition keys as S4 event streams—**`{seed, parameter_hash, run_id}`**—resolved via the **Data Dictionary**. After **every** S4 event append, the **same writer** must append **exactly one** `rng_trace_log` row **immediately after** the event; no other sink may emit trace rows. File order is **non-authoritative**; counters drive replay.

### Shared literals (recall)

```pseudocode
const MODULE          = "1A.s4.ztp"
const SUBSTREAM_LABEL = "poisson_component"
const FAM_TRACE       = "rng_trace_log"   # schemas.layer1.yaml#/rng/core/rng_trace_log
```

*The trace domain is exactly `(MODULE, SUBSTREAM_LABEL)` for **all** S4 events. Paths are dictionary-resolved.*

### Imported writer (authoritative)

* `update_rng_trace_totals(draws_str: string,
                           module: string, substream_label: string,
                           seed: u64, parameter_hash: hex64, run_id: hex32)
  -> TraceTotals`
  — **S1 variant (saturating)**; **call once per event** by the **same writer** that committed the event row; path is dictionary-resolved. Do **not** use the S0 non-saturating updater.

---

## 10.1 Pseudocode wrapper — one-event → one-trace (S4-scoped)

```pseudocode
proc trace_after_event_s4(
    lineage   : Lineage,        # {seed, parameter_hash, run_id, manifest_fingerprint}
    before_hi : u64, before_lo : u64,
    after_hi  : u64, after_lo  : u64,
    draws_str : string,         # decimal-u128 for THIS event; "0" if non-consuming
) -> next: TraceTotals

  # 0) Envelope identities (frozen in S4)
  (dhi, dlo)    := u128_delta(after_hi, after_lo, before_hi, before_lo)   # counter delta
  delta_blocks  := u128_to_uint64_or_abort(dhi, dlo)                      # fits u64 by spec
  (u_hi, u_lo)  := decimal_string_to_u128(draws_str)                      # parse draws
  is_draws_zero := (u_hi == 0 and u_lo == 0)

  if draws_str == "0" then
     # Non-consuming: before==after, blocks=0, draws="0"
     assert delta_blocks == 0
     assert is_draws_zero
  else
     # Consuming: after>before, blocks>0, draws>0
     assert delta_blocks > 0
     assert not is_draws_zero
  end if

  # 1) Single cumulative-trace append (S1·L0 — saturating totals)
  next := update_rng_trace_totals(
            draws_str, MODULE, SUBSTREAM_LABEL,
            lineage.seed, lineage.parameter_hash, lineage.run_id)

  # 2) Postconditions (MUST)
  # - Exactly one rng/core/rng_trace_log row appended in partition {seed, parameter_hash, run_id}
  # - Totals are saturating u64; consumer selects the FINAL row per (module, substream_label)
  return next
end
```

---

## 10.2 Where to call it (emitters)

* **Immediately after** each event append (`poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`), call
  `trace_after_event_s4(lineage, before_hi, before_lo, after_hi, after_lo, draws_str)`.

  * **Consuming attempts:** pass sampler-measured draws (e.g., `"3"` for inversion with $K=2$).
  * **Non-consuming markers/final:** pass `"0"`; counters must be unchanged.
* **Call shape matches §9 emitters.**

---

## 10.3 Partition & lineage rules for trace

* **Partitions (path keys):** `rng_trace_log` writes under **`{seed, parameter_hash, run_id}`** (dictionary-resolved).
* **Trace lineage fields.** Trace rows **omit** embedded lineage (no `seed/parameter_hash/run_id`) and carry **no `context`**; lineage is enforced by the partition path.
* **No `context` on trace.** Trace rows include `ts_utc`, `module`, `substream_label`, `rng_counter_after_{hi,lo}`, and cumulative totals only.

---

## 10.4 Behavior of totals (saturating) & consumer rule

* **Per-event deltas** are derived from the event that just wrote:
  $\Delta_{\text{blocks}} = u128(\text{after}) - u128(\text{before})$,
  $\Delta_{\text{draws}} = \mathrm{parse_u128}(\text{draws_str})$.
* **Totals are saturating `u64`** and **monotone**.
* **Consumer selection:** downstream selects the **final** trace row per `(module, substream_label)`, which must satisfy
  $\text{draws_total} = \sum \Delta_{\text{draws}}$ and
  $\text{blocks_total} = \sum \Delta_{\text{blocks}}$ over **all** S4 events in the partition.

---

## 10.5 Concurrency, idempotence, and “no double-trace”

* **Same-writer immediacy.** Within one `(module, substream_label)` and `{seed, parameter_hash, run_id}`, the **same writer** appends the trace **immediately after** the event row to prevent double emission/races.
* **Idempotence boundary.** If L2 marks a partition **complete**, emitters **no-op** (“skip-if-final”); no new trace rows are appended.
* **Stable merges.** Merges are **stable** w\.r.t. event writer-sort keys; trace rows stand independently. File order is **non-authoritative**.

---

## 10.6 Acceptance for §10 (checklist)

* After **each** S4 event append, the **same writer immediately calls** `trace_after_event_s4(...)` (or `update_rng_trace_totals` with identical args) **exactly once**.
* **Consuming vs non-consuming identities** enforced: attempts increase `blocks_total` & `draws_total`; markers/final increase **only** `events_total`.
* **Dictionary-resolved** path for `rng_trace_log`; partitions = `{seed, parameter_hash, run_id}`; trace rows have **no embedded lineage** and **no `context`**.
* **Saturating totals** semantics (S1 writer) only; **do not** use S0’s non-saturating updater.

---

# 11) Metrics helpers (values-only; same writer, **after event & trace fsync**)

> **What these helpers are.** Values-only, language-agnostic procedures the **same writer** calls **after** the event row **and its immediate trace append** have both been written & fsynced. They do **not** touch file paths or RNG; they emit counters/histograms/summaries keyed by run lineage (and optionally `merchant_id`). **No PII.** **Bounded/controlled cardinality.**

**Spec constraints (binding):**

* Every metric line **MUST** include `{ seed, parameter_hash, run_id, manifest_fingerprint }`.
* Minimal counters/gauges are fixed:
  `s4.merchants_in_scope, s4.accepted, s4.short_circuit_no_admissible, s4.downgrade_domestic, s4.aborted, s4.rejections, s4.attempts.total, s4.trace.rows, s4.regime.inversion, s4.regime.ptrs`.
* Histograms (SHOULD):
  `s4.attempts.hist, s4.lambda.hist, s4.ms.poisson_inversion, s4.ms.poisson_ptrs`.
* **Emission responsibility:** metrics are emitted by the **same process that wrote the event row and its trace**, **after fsync completes**.

---

## 11.1 Shared literals & types

```pseudocode
# Metric keys (strings); semantics per spec §13.2–§13.3
const M_IN_SCOPE       = "s4.merchants_in_scope"
const M_ACCEPTED       = "s4.accepted"
const M_SHORTCIRCUIT   = "s4.short_circuit_no_admissible"
const M_DOWNGRADE      = "s4.downgrade_domestic"
const M_ABORTED        = "s4.aborted"
const M_REJECTIONS     = "s4.rejections"
const M_ATTEMPTS_TOTAL = "s4.attempts.total"
const M_TRACE_ROWS     = "s4.trace.rows"
const M_REGIME_INV     = "s4.regime.inversion"
const M_REGIME_PTRS    = "s4.regime.ptrs"

const H_ATTEMPTS       = "s4.attempts.hist"
const H_LAMBDA         = "s4.lambda.hist"
const H_MS_INV         = "s4.ms.poisson_inversion"
const H_MS_PTRS        = "s4.ms.poisson_ptrs"

# Dimensions carried on every metric line (values-only; no paths/URIs)
type MetricsDims = {
  seed: u64, parameter_hash: hex64, run_id: hex32, manifest_fingerprint: hex64,
  merchant_id?: int64        # optional; enable only in debug/low-volume runs
}

# Abstract sink (host-integrated). These do not do I/O here; L2 wires them.
proc metrics_emit_counter   (dims: MetricsDims, key: string, delta: int)
proc metrics_emit_histogram (dims: MetricsDims, key: string, value: float64|int64)
proc metrics_emit_summary   (dims: MetricsDims, key: string, payload: map)
```

*All helpers below are invoked by the **same writer** **after** the event append **and** its immediate trace append (both fsynced).*

---

## 11.2 Scope & regime counters (once per merchant)

```pseudocode
# Call exactly once when a merchant enters S4 (S1 multi ∧ S3 eligible).
proc metrics_enter_scope(dims: MetricsDims):
  metrics_emit_counter(dims, M_IN_SCOPE, +1)

# Call exactly once when (λ,regime) is frozen (§7). Idempotent at call-site.
proc metrics_record_regime_once(dims: MetricsDims, regime: "inversion"|"ptrs"):
  if regime == "inversion":
    metrics_emit_counter(dims, M_REGIME_INV, +1)
  else:
    metrics_emit_counter(dims, M_REGIME_PTRS, +1)
```

---

## 11.3 Per-event increments (call **after trace append** of each event)

```pseudocode
# family ∈ {"poisson_component","ztp_rejection","ztp_retry_exhausted","ztp_final"}
# (maps 1:1 to rng/events/* IDs)
proc metrics_after_event_append(dims: MetricsDims, family: string):
  # One event → one trace: equals rows appended to rng/core/rng_trace_log
  metrics_emit_counter(dims, M_TRACE_ROWS, +1)

  if family == "poisson_component":
    metrics_emit_counter(dims, M_ATTEMPTS_TOTAL, +1)
  elif family == "ztp_rejection":
    metrics_emit_counter(dims, M_REJECTIONS, +1)
  # "ztp_retry_exhausted" and "ztp_final": no generic counters here
```

---

## 11.4 Finalisation metrics (accept / short-circuit / downgrade)

```pseudocode
# Call exactly once per resolved merchant, immediately AFTER writing ztp_final and fsync.
proc metrics_on_final(
    dims: MetricsDims,
    K_target: int, attempts: int, regime: "inversion"|"ptrs",
    lambda_extra: float64, exhausted: bool, reason_opt: optional<"no_admissible">
):
  # Outcome counters (mutually exclusive)
  if (K_target >= 1) and (exhausted == false):
    metrics_emit_counter(dims, M_ACCEPTED, +1)
  elif (K_target == 0) and (attempts == 0) and reason_opt.is_present:
    # A=0 short-circuit (emit 'reason' only if bound schema includes it)
    metrics_emit_counter(dims, M_SHORTCIRCUIT, +1)
  elif (K_target == 0) and (exhausted == true):
    # Cap hit + policy="downgrade_domestic"
    metrics_emit_counter(dims, M_DOWNGRADE, +1)

  # Histograms (SHOULD)
  metrics_emit_histogram(dims, H_ATTEMPTS, attempts)   # accepted → attempts; A=0 → 0; downgrade → cap value
  metrics_emit_histogram(dims, H_LAMBDA, lambda_extra)

  # Per-merchant summary (SHOULD). Omit for hard abort.
  metrics_emit_summary(dims, "s4.merchant.summary", {
      "merchant_id": dims.merchant_id?, "attempts": attempts,
      "accepted_K": K_target, "regime": regime,
      "exhausted": exhausted, "reason?": reason_opt?
  })
```

---

## 11.5 Cap-abort metrics (no finaliser written)

```pseudocode
# Call once when policy="abort" at cap; ztp_final is NOT written.
proc metrics_on_cap_abort(dims: MetricsDims, attempts: int):
  metrics_emit_counter(dims, M_ABORTED, +1)
  metrics_emit_histogram(dims, H_ATTEMPTS, attempts)
  # No merchant summary on hard abort
```

---

## 11.6 Per-branch timing (optional; caller measures)

```pseudocode
# If caller times sampler branch work per merchant, record elapsed ms (SHOULD).
proc metrics_observe_ms(dims: MetricsDims, regime: "inversion"|"ptrs", elapsed_ms: float64):
  if regime == "inversion":
    metrics_emit_histogram(dims, H_MS_INV,  elapsed_ms)
  else:
    metrics_emit_histogram(dims, H_MS_PTRS, elapsed_ms)
```

---

## 11.7 Call order (writer timeline)

```pseudocode
# For each event:
# 1) Emit event row
# 2) Append trace row (immediately; same writer)
# 3) Fsync event + trace
metrics_after_event_append(...)

# For an attempt with k==0 (rejection):
#   (handled via family=="ztp_rejection" in 9.2)
# On finaliser:
metrics_on_final(...)

# On cap abort (no ztp_final):
metrics_on_cap_abort(...)

# Once per merchant:
metrics_enter_scope(...); metrics_record_regime_once(...)

# Optional timing (per merchant):
metrics_observe_ms(...)
```

---

## 11.8 Acceptance for §11 (checklist)

* Metrics include `{ seed, parameter_hash, run_id, manifest_fingerprint }` on **every** line.
* Counters/histograms/summary keys **exactly** match the spec’s list; **no extra high-cardinality labels** beyond optional `merchant_id` (use sparingly).
* Emitted by the **same writer**, **after** the event row and its **immediate trace append** are fsynced.
* Values-only surface (no paths/URIs); no duplication of validator logic.

---

# 12) Partition & lineage enforcement (verify before write)

> **What this section gives you.** Concrete, language-agnostic **pseudocode guards** that make every S4 write **dictionary-resolved**, **partition-correct**, and **path↔embed equal**—before the first byte hits disk. It also includes a small **read-side verifier** for S1/S2 inputs. RNG logs are **logs-only** datasets partitioned by **`{seed, parameter_hash, run_id}`**; file order is **non-authoritative**.

---

## 12.1 Dictionary resolution & expected keys (no path literals)

```pseudocode
# Dictionary contracts (host-provided; authoritative, not hard-coded)
proc dict_expected_partitions(family: string) -> list[string]           # e.g., ["seed","parameter_hash","run_id"]
proc dict_path_for_family   (family: string, parts: map) -> string      # resolves to full path; no literals
```

*For all S4 streams (`rng_event_poisson_component`, `rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`, `rng_event_ztp_final`, and `rng_trace_log`), the dictionary declares partitions = **`["seed","parameter_hash","run_id"]`**. S4 must not embed physical paths; all locations are dictionary-resolved.*

---

## 12.2 Path token extraction (portable)

```pseudocode
# Pull out partition tokens from a dictionary-resolved path.
proc extract_partition_tokens(path: string, keys: list[string]) -> map:
  tokens ← {}
  for k in keys:
    tokens[k] ← parse_partition_token(path, k)   # e.g., ".../seed=123/..." → tokens["seed"]="123"
  return tokens
```

---

## 12.3 Write-side lineage verifier (family-agnostic)

```pseudocode
# Enforce dictionary partitions AND path↔embed equality BEFORE writing.
#
# family ∈ {
#   "rng_event_poisson_component","rng_event_ztp_rejection",
#   "rng_event_ztp_retry_exhausted","rng_event_ztp_final",
#   `rng_trace_log`
# }
# lineage = { seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }
#
proc prewrite_verify_partition_and_lineage(family: string, lineage: Lineage) -> VerifiedPartition:
  # 1) Dictionary declares the contract (authoritative)
  expect_keys ← dict_expected_partitions(family)                       # MUST be ["seed","parameter_hash","run_id"]
  assert expect_keys == ["seed","parameter_hash","run_id"]             # logs-only contract for S4
  # 2) Resolve path with EXACT lineage values (no literals)
  parts ← { "seed": lineage.seed,
            "parameter_hash": lineage.parameter_hash,
            "run_id": lineage.run_id }
  path  ← dict_path_for_family(family, parts)
  # 3) Re-parse to ensure dictionary round-tripped the same values
  got   ← extract_partition_tokens(path, expect_keys)
  assert got["seed"]           == to_string(lineage.seed)
  assert got["parameter_hash"] == lowercase_hex(lineage.parameter_hash)
  assert got["run_id"]         == lowercase_hex(lineage.run_id)
  # 4) Return the verified tuple for the writer to use
  return VerifiedPartition{ family:family, path:path, parts:parts }
end
```

*Why this is enough:* for RNG **event** logs the **embedded lineage fields** (envelope `{seed, parameter_hash, run_id}`) are set by the writer from `lineage`; because the **path was built from the same `lineage`**, **path↔embed equality** is guaranteed by construction. Any mismatch after write becomes a **structural failure** in validation.

---

## 12.4 Event writer prelude (call pattern used by §9 emitters)

```pseudocode
# Minimal prelude each emitter MAY run before begin_event_micro(...)
# Host-optional / non-normative when the S1 writer surfaces already handle resolution/append.
proc open_stream_for_write(family: string, lineage: Lineage) -> (VerifiedPartition, PathHandle):
  vp   ← prewrite_verify_partition_and_lineage(family, lineage)
  hndl ← open_for_append(vp.path)            # host I/O; may create dirs
  return (vp, hndl)
end
```

*Emitters in §9 rely on the S1 writer surfaces which dictionary-resolve internally; hosts that manage handles explicitly can use this prelude. No path literals; never bypass the verifier.*

---

## 12.5 Envelope lineage fill (writer responsibility)

All RNG **event** rows **embed** lineage in the **envelope**, and that lineage **must equal** the path tokens **byte-for-byte**:

```text
Envelope (event rows only):
{
  seed:u64, parameter_hash:hex64, run_id:hex32,   # embedded = path tokens
  module:"1A.s4.ztp", substream_label:"poisson_component", context:"ztp",
  rng_counter_before_lo:u64, rng_counter_before_hi:u64,
  rng_counter_after_lo:u64,  rng_counter_after_hi:u64,
  blocks:u64, draws:dec_u128, ts_utc
}
```

`rng_trace_log` **trace rows omit embedded lineage** (no `seed/parameter_hash/run_id`) and carry **no `context`**; lineage is enforced by the **partition path**.

---

## 12.6 Read-side verifier (for S1/S2 inputs S4 must consume)

```pseudocode
# S4 MUST enforce path↔embed equality when reading S1/S2 RNG logs (gates/facts).
# family ∈ {"rng_event_hurdle_bernoulli","rng_event_nb_final"}
proc verify_upstream_row_path_embed(family: string, row: map, path: string):
  keys ← ["seed","parameter_hash","run_id"]
  tok  ← extract_partition_tokens(path, keys)
  assert to_string(row["seed"])               == tok["seed"]
  assert lowercase_hex(row["parameter_hash"]) == tok["parameter_hash"]
  assert lowercase_hex(row["run_id"])         == tok["run_id"]
  # NB: S4 only reads values; it does not mutate or re-emit these rows.
end
```

*The frozen S4 spec requires **path↔embed equality on read** for S1/S2 rows; a mismatch is a **run-scoped** structural failure.*

---

## 12.7 Zero-row & idempotence discipline (producer-side)

```pseudocode
# If a slice yields zero events, write nothing (no empty parts).
proc maybe_noop_on_empty_slice(has_rows: bool, vp: VerifiedPartition):
  if not has_rows: return NOOP
  # else emitter proceeds; idempotence is handled by L2’s "skip-if-final" checks.
end
```

*Re-runs with identical inputs produce **byte-identical** content; concrete partition directories are **immutable** once published.*

---

## 12.8 Acceptance for §12 (checklist)

* **Dictionary-resolved only**; no path literals anywhere.
* **Expected partitions** for every S4 stream are exactly **`seed, parameter_hash, run_id`**; verified before write.
* **Path↔embed equality** holds on **event rows**: embedded `{seed, parameter_hash, run_id}` **byte-match** path tokens; `rng_trace_log` **trace rows omit embedded lineage** and have **no `context`** (lineage via partition path).
* **Read-side equality** is enforced for S1/S2 inputs S4 reads (gates/facts).
* **File order non-authoritative**; counters drive replay.
* **Logs-only posture**; no egress/validation writes here. (Fingerprint-scoped content belongs to S0/validators.)

These guards make it mechanically hard to drift from the partition contract: the **dictionary** declares the keys, **lineage** fills both path and event envelopes, and equality is enforced **before** writing—exactly as the frozen spec requires.

---

# 13) Concurrency & atomicity contract (crash-safe)

> The aim here is to make **writes deterministic, crash-safe, and idempotent**, matching the frozen S4 spec: per-merchant loops are **serial**; merchants may run **in parallel**; the writer either appends in a **single serialized stream** or uses **partitioned, stable merges**; and re-runs with identical inputs are **byte-identical** with **skip-if-final** behavior.

---

## 13.1 Writer domains & locks (no concurrent appends per domain)

**Domain key (logs-only partition):**
`dom = ( family ∈ { "rng_event_poisson_component", "rng_event_ztp_rejection", "rng_event_ztp_retry_exhausted", "rng_event_ztp_final", `rng_trace_log` }, seed, parameter_hash, run_id )`

```pseudocode
# Host-provided lock; exact primitive is platform-specific (mutex/file lock/shard gate).
proc with_partition_writer_lock(dom, body):
  lock_acquire(dom)
  try:
    body()
  finally:
    lock_release(dom)
```

**Rule (MUST).** At most **one** writer appends to a given `dom` at a time. This satisfies the “serial writer” option (simplest route to byte-identical outputs). If you use worker spills + merge (next §), workers **must not** append into the final path concurrently.

---

## 13.2 Two deterministic writer strategies (choose one)

1. **Serial writer (recommended for logs).**

   * One writer receives already-sorted events and **appends** rows in writer-sort order; emits **one trace** per event; **fsyncs** each append before returning.
   * Easiest to make byte-identical; no merge stage.

2. **Partitioned merge (if parallelizing I/O).**

   * Workers write **tmp segments** that are **already sorted** by the family’s writer-sort key.
   * A final **stable merge per partition** assembles `(merchant_id, attempt)` (and `(merchant_id, attempts)` / `(merchant_id)` for cap/final).
   * Merge uses **stage → fsync(tmp) → rename** for all-or-nothing publish.

*Back-pressure:* bound in-flight merchants so the finalizer never merges out of order. Avoid tiny files; batching is allowed (content/ordering/idempotence are mandated, not file sizes).

---

## 13.3 Atomic event append (serial writer path) *(host-optional plumbing)*

**Contract:** each event append is **durably written** before proceeding to trace; no half-rows.

```pseudocode
proc append_jsonl_atomic(path: string, row_bytes: bytes):
  fd ← open(path, flags=O_CREAT|O_WRONLY|O_APPEND)
  write_all(fd, row_bytes)             # row ends with '\n' (record boundary)
  fdatasync(fd)                         # fsync the append
  # leave fd open for batched appends; else close
```

---

## 13.4 Atomic publish for merged outputs (if using partitioned merge) *(host-optional plumbing)*

```pseudocode
proc publish_merged_atomic(final_path: string, merge: (out_fd) -> void):
  tmp ← final_path + ".tmp." + uuid4()
  out ← open(tmp, O_CREAT|O_WRONLY|O_TRUNC)
  merge(out)                            # write fully merged, sorted content
  fdatasync(out); close(out)
  rename(tmp, final_path)               # atomic swap to publish
  # If platform lacks atomic rename, fallback to linkat+unlink.
```

Crash between `fsync(tmp)` and `rename` leaves either prior `final_path` or intact `tmp`; recovery picks newest by policy.

---

## 13.5 Event+trace pairing (one event → one trace), crash windows

**Normal sequence (per event):**
`append EVENT (fsync) → append TRACE (same writer, immediately; fsync)` — both under the same `{seed, parameter_hash, run_id}`.

**Crash windows & recovery (informative):**

* **Before EVENT fsync:** no visible bytes; safe to retry emit.
* **After EVENT fsync, before TRACE append:** event row visible; **trace missing**. On resume, the orchestrator **repairs by appending the TRACE only** using the event’s **persisted envelope** (`rng_counter_before_{hi,lo}`, `rng_counter_after_{hi,lo}`, `draws_str`). No resampling.
* **After TRACE fsync:** both present; idempotent.

```pseudocode
proc repair_trace_for_last_event(lineage: Lineage, last_event: Envelope):
  # last_event has canonical envelope fields and decimal-u128 draws, already durable
  trace_after_event_s4(
    lineage,
    last_event.rng_counter_before_hi, last_event.rng_counter_before_lo,
    last_event.rng_counter_after_hi,  last_event.rng_counter_after_lo,
    last_event.draws )
```

Trace rows are **cumulative (saturating)**; a single append per event is required in steady state (see §10).

---

## 13.6 Idempotence & skip-if-final

* **Idempotence (state rule).** Identical inputs ⇒ **byte-identical** outputs. If a complete partition already exists, **skip-if-final** (no new bytes). Re-runs write **nothing** for zero-row slices.
* **No zero-row files.** Presence implies ≥1 row; empty artefacts are forbidden.

---

## 13.7 Stable merges (only if using partitioned merge)

* Worker segments must be **pre-sorted** by the family’s writer-sort key: attempts/rejections `(merchant_id, attempt)`; cap `(merchant_id, attempts)`; final `(merchant_id)`.
* Final merge is **stable**, preserving equal-key order. **File order is non-authoritative** in the spec; counters give true order, but merges must not manufacture reorders that violate writer keys.

---

## 13.8 Per-merchant serialism & cross-merchant parallelism

* The **attempt loop** for a merchant is **single-threaded**; do not interleave its counter spans with another merchant’s substream.
* Parallelism is across merchants up to a governed cap `C`.

---

## 13.9 Acceptance for §13 (checklist)

* **Single writer per domain** `(family, seed, parameter_hash, run_id)`; no concurrent appends. Families use full IDs:
  `rng_event_poisson_component`, `rng_event_ztp_final`, `rng_event_ztp_retry_exhausted`, `rng_event_ztp_final`, `rng_trace_log`.
* **Either** serial appends with **fdatasync per row**, **or** worker segments + **stable** merge with **stage → fsync → rename** publish.
* **One event → one trace** by the **same writer, immediately after** the event; if a crash occurs after EVENT fsync and before TRACE append, **repair the trace only** using the event’s persisted envelope counters and `draws_str` (no duplicate events, no resampling).
* **Idempotence & zero-row ban** honored; **skip-if-final** respected.
* **Stable writer-sort merges** (if used); **file order non-authoritative** remains true.

---

# 14) Idempotency & re-entrancy (helper-by-helper)

> Purpose: tell an implementer exactly **what is safe to repeat** and what **must never** be retried for each S4·L0 surface. We separate **pure helpers**, the **single-attempt adapter**, **emitters**, **trace**, **partition guards**, and **metrics**. Rules reflect uniqueness per stream, **one-event→one-trace** (same writer, **immediately after**), counters as order, zero-row ban, byte-identical re-runs, and skip-if-final.

---

## 14.1 Pure helpers (values-only; safe to re-call)

These are side-effect free. Re-calling with the **same inputs** returns the **same outputs**. They raise on contract failure; they never log or write.

### a) `assert_finite_positive(lambda_extra: float64) -> float64 | NUMERIC_INVALID`

```
IDEMPOTENT   : YES
RE-ENTRANT   : YES
SIDE-EFFECTS : NONE
ERRORS       : NUMERIC_INVALID if NaN/±Inf/≤0
```

### b) `compute_poisson_regime(lambda_extra: float64) -> "inversion" | "ptrs"`

```
IDEMPOTENT   : YES  (λ★ = 10 threshold; exact comparison; no epsilons)
RE-ENTRANT   : YES
SIDE-EFFECTS : NONE
NOTE         : Regime is fixed per merchant for the whole loop (no switching)
```

### c) `freeze_lambda_regime(lambda_extra_raw: float64) -> {lambda_extra, regime} | NUMERIC_INVALID`

```
IDEMPOTENT   : YES  (composition of a & b)
RE-ENTRANT   : YES
SIDE-EFFECTS : NONE
CONSTANCY    : Returned pair is reused verbatim for all S4 rows of the merchant
```

---

## 14.2 Single-attempt adapter (pure; consumes PRNG stream deterministically)

### d) `poisson_attempt_once(λ: float64, regime: "inversion"|"ptrs", s_before: Stream) -> (k: int≥0, s_after: Stream, bud: AttemptBudget)`

```
IDEMPOTENT   : YES, if called again with the same (s_before, λ) → identical (k, s_after, bud)
RE-ENTRANT   : YES, but calling with s_after advances further (by design)
SIDE-EFFECTS : NONE (values only)
ERRORS       : Propagates NUMERIC_INVALID if λ fails the guard
BUDGET LAW   : bud.blocks == u128(after)−u128(before); bud.draws encodes ACTUAL uniforms
```

---

## 14.3 Event emitters (append-only I/O; **not** idempotent)

**Uniqueness constraints (spec):**

* ≤1 `poisson_component` per `(merchant_id, attempt)`
* ≤1 `ztp_rejection` per `(merchant_id, attempt)`
* ≤1 `ztp_retry_exhausted` per merchant
* ≤1 `ztp_final` per **resolved** merchant
  *(Short names map 1:1 to families `rng/events/*`.)*

### e) `event_poisson_ztp(...) → rng_event_poisson_component`

```
IDEMPOTENT   : NO  (appends a new row)
RE-ENTRANT   : CONDITIONALLY SAFE
  • Safe to retry ONLY if the prior call failed BEFORE fsync (no visible bytes)
  • If EVENT fsync succeeded but TRACE did not: DO NOT re-emit the event;
    repair by appending TRACE only (see §10/§13)
SIDE-EFFECTS : Writes 1 event row (consuming) + 1 cumulative trace row
POSTCONDITIONS: Consuming identities (after>before; blocks==Δ; draws>"0")
TRACE RULE   : Same writer, append TRACE immediately after EVENT fsync (once)
```

### f) `emit_ztp_rejection_nonconsuming(...) → rng/events/ztp_rejection`

```
IDEMPOTENT   : NO
RE-ENTRANT   : Same rules as (e)
SIDE-EFFECTS : Writes 1 event row (non-consuming) + 1 trace row
POSTCONDITIONS: Non-consuming identities (before==after; blocks=0; draws="0")
TRACE RULE   : Same writer, append TRACE immediately after EVENT fsync (once)
```

### g) `emit_ztp_retry_exhausted_nonconsuming(...) → rng/events/ztp_retry_exhausted`

```
IDEMPOTENT   : NO  (≤1 per merchant)
RE-ENTRANT   : Same rules as (e)
SIDE-EFFECTS : Writes 1 event row (non-consuming) + 1 trace row
POSTCONDITIONS: Non-consuming identities; writer-sort (merchant_id, attempts)
PAYLOAD NOTE : Includes policy flag per bound schema (we use aborted:true)
TRACE RULE   : Same writer, append TRACE immediately after EVENT fsync (once)
```

### h) `emit_ztp_final_nonconsuming(...) → rng/events/ztp_final`

```
IDEMPOTENT   : NO  (exactly 1 per resolved merchant)
RE-ENTRANT   : Same rules as (e)
  • Short-circuit A=0: attempts=0, K_target=0 (optional reason if schema has it)
  • Downgrade policy: K_target=0, exhausted:true
  • Abort policy: DO NOT emit any final
SIDE-EFFECTS : Writes 1 event row (non-consuming) + 1 trace row
TRACE RULE   : Same writer, append TRACE immediately after EVENT fsync (once)
```

---

## 14.4 Trace wrapper (append-only; **not** idempotent)

### i) `trace_after_event_s4(...) → rng/core/rng_trace_log`

```
IDEMPOTENT   : NO  (appends a new cumulative row)
RE-ENTRANT   : CONDITIONALLY SAFE
  • Call exactly once per event in steady state
  • If crash occurred after EVENT fsync and BEFORE TRACE append: call ONCE to repair
SIDE-EFFECTS : Writes 1 cumulative trace row (saturating totals)
INVARIANTS   : Parses this event’s draws; checks consuming/non-consuming identities
```

---

## 14.5 Partition & lineage guards (pure; safe to re-call)

### j) `prewrite_verify_partition_and_lineage(family, lineage) -> VerifiedPartition`

```
IDEMPOTENT   : YES  (dictionary round-trip; equality asserts)
RE-ENTRANT   : YES
SIDE-EFFECTS : NONE (returns verified path+parts for the writer)
CONTRACT     : Declared partitions are ["seed","parameter_hash","run_id"]; path↔embed equality by construction
```

### k) `open_stream_for_write(family, lineage) -> (VerifiedPartition, PathHandle)`

```
IDEMPOTENT   : NO  (opens a new handle)
RE-ENTRANT   : SAFE under the domain lock (see §13); do not open two handles for the same append
SIDE-EFFECTS : Acquires OS resources; must be closed by the writer
```

---

## 14.6 Metrics helpers (values-only; increments — **not** idempotent)

### l) `metrics_after_event_append(...)`, `metrics_on_final(...)`, `metrics_on_cap_abort(...)`, `metrics_enter_scope(...)`, `metrics_record_regime_once(...)`, `metrics_observe_ms(...)`

```
IDEMPOTENT   : NO (counters/histograms increment)
RE-ENTRANT   : CALL ONCE per indicated moment
SIDE-EFFECTS : Values-only emission to the metrics sink; no paths/URIs; bounded cardinality
TIMING       : Same writer, AFTER event & TRACE fsync (see §11)
```

---

## 14.7 Crash windows & safe retry map (summary)

| Phase                                  | Safe to retry?     | Action                                                         |
|----------------------------------------|--------------------|----------------------------------------------------------------|
| Before EVENT fsync                     | ✅ Safe             | Re-emit the **same** event once; then TRACE.                   |
| After EVENT fsync, before TRACE append | ⚠️ Event visible   | **Do not re-emit event**. Append **TRACE only** once (repair). |
| After TRACE fsync                      | 🚫 No retry needed | Both present; re-runs skip-if-final → no-op.                   |

Trace is cumulative (saturating); counters drive order; file order is non-authoritative.

---

## 14.8 Acceptance for §14 (checklist)

* Pure helpers (`assert_finite_positive`, `compute_poisson_regime`, `freeze_lambda_regime`) are **idempotent & re-entrant**; no I/O.
* Single-attempt adapter is **deterministic** for a given `s_before` (idempotent on same inputs); advances the stream otherwise.
* Emitters and trace are **append-only** and **not idempotent**; obey **one-event→one-trace** with the **same writer immediately after** the event; repair only in the permitted crash window.
* Partition guard is **pure** and enforces dictionary partitions and path↔embed equality **before write**.
* Metrics are **values-only** increments; **same writer, after event & trace fsync**; call sites are “once per” as defined in §11.
* State-level idempotence holds: **zero-row ban**, **byte-identical re-runs**, **skip-if-final** when a partition is complete.

---

# 15) Budget reconciliation surfaces (counters ↔ draws)

> Purpose: give the implementer **exact, callable** surfaces that make every S4 event’s budgets **mechanically correct**—the **counter delta** (blocks) must match the envelope; the **uniforms consumed** (draws) must be the sampler’s **actual-use**; non-consuming rows must leave counters unchanged and write `"0"` draws; and the **trace totals** must increment by exactly the event deltas. Budgets are **measured, not inferred**. File order is **non-authoritative**—counters drive order and replay.

**Reuse (no re-implementation):** `u128_delta`, `decimal_string_to_u128`, `u128_to_decimal_string`, and `u128_to_uint64_or_abort` come from **S1·L0**. The single-attempt sampler (`poisson_attempt_with_budget`) that returns **measured** budgets is from **S2·L0**. We **do not** compute budgets from formulas.

---

## 15.1 Helpers (values-only; reused codecs)

```pseudocode
# Reused from S1·L0 (do NOT re-implement)
proc u128_delta(after_hi:u64, after_lo:u64, before_hi:u64, before_lo:u64) -> (hi:u64, lo:u64)
proc u128_to_uint64_or_abort(hi:u64, lo:u64) -> u64
proc decimal_string_to_u128(s:string) -> (hi:u64, lo:u64)
proc u128_to_decimal_string(hi:u64, lo:u64) -> string
```

*These are the only allowed primitives for decoding/encoding per-event budgets (`blocks`, `draws`).*

---

## 15.2 Reconciling a **consuming** attempt (`poisson_component`)

**Contract (from spec):** consuming rows must satisfy
`after > before`, `blocks == u128(after) − u128(before) > 0`, and `draws > "0"` (**actual uniforms consumed**).

```pseudocode
proc reconcile_consuming_budget(s_before:Stream, s_after:Stream, bud:AttemptBudget)
  # bud.blocks and bud.draws_* come from the S2 sampler (measured; not inferred)
  (dhi, dlo)   := u128_delta(s_after.ctr.hi, s_after.ctr.lo, s_before.ctr.hi, s_before.ctr.lo)
  delta_blocks := u128_to_uint64_or_abort(dhi, dlo)

  # MUST: blocks identity and positivity
  assert delta_blocks == bud.blocks and delta_blocks > 0

  # MUST: draws are actual uniforms; positive u128
  assert (bud.draws_hi, bud.draws_lo) > 0_u128

  draws_str := u128_to_decimal_string(bud.draws_hi, bud.draws_lo)
  return { blocks_delta: delta_blocks, draws_str: draws_str }
end
```

> Rationale: the sampler already **measures** uniforms (draws) and we **compute** blocks from counters; we only **reconcile** them against identities.

---

## 15.3 Reconciling a **non-consuming** marker/final (rejection, exhausted, final)

**Contract (from spec):** non-consuming rows must satisfy
`before == after`, `blocks = 0`, `draws = "0"` *(ZTP non-consuming rows: `before==after`, `blocks=0`, `draws="0"`)*.

```pseudocode
proc reconcile_nonconsuming_budget(s_current: Stream)
  (dhi, dlo)   := u128_delta(s_current.ctr.hi, s_current.ctr.lo,
                             s_current.ctr.hi, s_current.ctr.lo)
  delta_blocks := u128_to_uint64_or_abort(dhi, dlo)
  assert delta_blocks == 0

  draws_str := "0"
  return { blocks_delta: 0, draws_str: draws_str }
end
```

---

## 15.4 Emit-time envelope check (pre-writer sanity)

> A tiny guard used immediately **before** the writer stamps the envelope (canonical fields `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}`), so the row cannot violate the identities.

```pseudocode
proc assert_envelope_identities(kind: "consuming"|"nonconsuming",
                                s_before:Stream, s_after:Stream, draws_str:string)
  (dhi, dlo)  := u128_delta(s_after.ctr.hi, s_after.ctr.lo, s_before.ctr.hi, s_before.ctr.lo)
  blocks_u64  := u128_to_uint64_or_abort(dhi, dlo)
  (r_hi, r_lo):= decimal_string_to_u128(draws_str)    # decimal-u128

  # Decimal-u128 domain: non-negative base-10; no leading zeros (except "0")
  if kind == "consuming":
     assert blocks_u64 > 0
     assert (r_hi, r_lo) > 0_u128
  else:  # non-consuming
     assert blocks_u64 == 0
     assert (r_hi, r_lo) == 0_u128
  end if
end
```

---

## 15.5 Trace pairing (event deltas → cumulative totals)

**Spec rules:** one event → **one** cumulative trace row; **saturating** totals; for consuming attempts, totals increase by the event’s `blocks` and `draws`; for non-consuming, only `events_total` increases.

```pseudocode
proc reconcile_trace_step(prev:TraceTotals,
                          blocks_delta:u64, draws_str:string) -> next:TraceTotals
  (d_hi, d_lo) := decimal_string_to_u128(draws_str)
  d_u64        := u128_to_uint64_or_abort(d_hi, d_lo)  # totals are u64; single-event draws must fit u64

  # Saturating u64 additions (writer guarantees saturation semantics on totals)
  next.blocks_total := saturating_add(prev.blocks_total, blocks_delta)
  next.draws_total  := saturating_add(prev.draws_total,  d_u64)
  next.events_total := saturating_add(prev.events_total, 1)
  return next
end
```

> In practice the **S1 trace writer** performs the saturating update; this wrapper is a **test/audit check** to reason about “what totals must become”.

---

## 15.6 End-to-end pairing in the emitters (where §15 integrates)

* **Consuming attempt (authoritative write):**
  `reconcile_consuming_budget` → `assert_envelope_identities("consuming", …)` →
  `end_event_emit(...)` → *(optional test/audit)* `reconcile_trace_step(prev, blocks_delta, draws_str)` →
  **`update_rng_trace_totals(draws_str, MODULE, SUBSTREAM_LABEL, lineage.seed, lineage.parameter_hash, lineage.run_id)`**.

* **Non-consuming marker/final (authoritative write):**
  `reconcile_nonconsuming_budget` → `assert_envelope_identities("nonconsuming", …)` →
  `end_event_emit(...)` → *(optional test/audit)* `reconcile_trace_step(prev, 0, "0")` →
  **`update_rng_trace_totals("0", MODULE, SUBSTREAM_LABEL, lineage.seed, lineage.parameter_hash, lineage.run_id)`**.

*Only `update_rng_trace_totals(...)` performs the trace write; `reconcile_trace_step(...)` is **optional** and used for tests/audits.*

---

## 15.7 Validator-grade invariants (writer-side asserts)

* **Consuming:** `u128(after) − u128(before) == blocks` **and** `decimal(draws) > 0` *(envelope fields `rng_counter_*`)*.
* **Non-consuming:** `before == after` **and** `blocks == 0` **and** `draws == "0"`.
* **Totals (cumulative):** across all events in the partition, the final trace row must satisfy
  `draws_total == Σ parse_u128(draws)` and `blocks_total == Σ (u128(after) − u128(before))`.

---

## 15.8 Acceptance for §15 (checklist)

* **Budgets are measured, not inferred**: `draws` comes from the sampler; `blocks` comes from counters.
* **Envelope identities** enforced for consuming vs non-consuming rows.
* **One event → one trace**: trace totals increase by exactly the event deltas; totals are **saturating**.
* **File order is non-authoritative**; counters provide the total order and replay basis.

These surfaces make budget correctness **mechanical**: an implementer can’t emit a row that violates the spec’s identities, and trace totals will always reconcile with the **sum of per-event deltas**—exactly as frozen in S4.

---

# 16) Errors & signals (surfaces only; **no orchestration**)

> **What this section provides.** Pure, values-only **pseudocode surfaces** to construct and emit S4 failure **records**—with **stable keys**, **frozen codes**, and correct **scope**—so L1/L2 can abort cleanly without guessing payload shapes. These helpers **do not** write validation bundles or make abort decisions; they only build/emit the values the orchestrator needs. *In this state, “signals” are emitted as failure records; there is no separate signaling surface.*

---

## 16.1 Stable vocabulary & payload (authority)

**S4 codes & scopes.** The frozen spec defines merchant-scoped and run-scoped codes (e.g., `NUMERIC_INVALID`, `RNG_ACCOUNTING`, `UPSTREAM_MISSING_S2`, `PARTITION_MISMATCH`, `ZERO_ROW_FILE`, `STREAM_ID_MISMATCH`, `POLICY_INVALID`, etc.). **Producer behavior** (abort merchant vs abort run; no partial writes) is normative at the state level.

**Required payload fields (all codes):**

```text
{
  code,                                        # frozen S4 code string
  scope ∈ {"merchant","run"},
  reason : string,                             # human-readable short cause (no paths/PII)
  merchant_id? : int64,                        # present iff scope=="merchant"
  seed : u64, parameter_hash : hex64, run_id : hex32, manifest_fingerprint : hex64,
  attempts? : int,                             # if any attempts occurred; 0 on A=0 short-circuit
  lambda_extra? : float64,                     # present if computed or any attempts were made
  regime? : "inversion" | "ptrs"               # if derived for this merchant
}
```

**Logging keys (values-only; exact names):**
`s4.fail.code, s4.fail.scope, s4.fail.reason, s4.fail.attempts, s4.fail.lambda_extra, s4.fail.regime, s4.run.seed, s4.run.parameter_hash, s4.run.run_id, s4.run.manifest_fingerprint, s4.fail.merchant_id?`.

**Mapping to global validation.** S4 codes appear **as-is** in the ledger; the run’s record also carries the **S0** `failure_class` (F1–F10) per the validation schema (informative; L0/L1 do not assign it).

---

## 16.2 Shared types & sink (values-only)

```pseudocode
type FailureDims = {
  seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64,
  merchant_id?: int64
}

type FailureRecord = {
  code:string, scope:"merchant"|"run", reason:string,
  merchant_id?: int64,
  seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64,
  attempts?: int, lambda_extra?: float64, regime?: "inversion"|"ptrs"
}

# Values-only emit sink (host-integrated; no file paths here)
proc emit_failure_line(rec: FailureRecord)
```

---

## 16.3 Constructor (single source of shape)

```pseudocode
proc make_failure_record(
  code:string, scope:"merchant"|"run", reason:string,
  dims:FailureDims, attempts_opt?:int, lambda_opt?:float64, regime_opt?:"inversion"|"ptrs"
) -> FailureRecord
  rec.code   ← code
  rec.scope  ← scope
  rec.reason ← reason
  if scope == "merchant": assert dims.merchant_id is present
  rec.merchant_id?         ← dims.merchant_id?
  rec.seed                 ← dims.seed
  rec.parameter_hash       ← dims.parameter_hash
  rec.run_id               ← dims.run_id
  rec.manifest_fingerprint ← dims.manifest_fingerprint
  if attempts_opt is present: rec.attempts ← attempts_opt
  if lambda_opt   is present: rec.lambda_extra ← lambda_opt
  if regime_opt   is present: rec.regime ← regime_opt
  return rec
end
```

---

## 16.4 Merchant-scoped wrappers (common S4 codes)

> Wrappers **only** construct and emit the record; they do **not** loop, retry, or write any RNG/egress rows.

```pseudocode
proc fail_numeric_invalid(dims:FailureDims, lambda_extra:float64):
  # Trigger: λ is NaN/±Inf/≤0 (see §7 assert_finite_positive). Producer must write no attempts and no finaliser.
  rec ← make_failure_record("NUMERIC_INVALID","merchant",
         "lambda_extra non-finite or ≤ 0", dims,
         attempts_opt:=null, lambda_opt:=lambda_extra, regime_opt:=null)
  emit_failure_line(rec)
end
```

```pseudocode
proc fail_branch_purity(dims:FailureDims, reason:string):
  # Trigger: any S4 row for is_multi=false or is_eligible=false (gating violated).
  # If this code is not in the bound vocabulary, map to the canonical policy code (e.g., POLICY_INVALID).
  rec ← make_failure_record("BRANCH_PURITY","merchant",reason,dims)
  emit_failure_line(rec)
end
```

```pseudocode
proc fail_a_zero_mishandled(dims:FailureDims, attempts:int, regime:"inversion"|"ptrs"):
  # Trigger: A=0 but attempts>0 OR K_target≠0 OR (schema has it AND reason≠"no_admissible").
  rec ← make_failure_record("A_ZERO_MISHANDLED","merchant",
         "A=0 short-circuit mishandled",dims,attempts_opt:=attempts,lambda_opt:=null,regime_opt:=regime)
  emit_failure_line(rec)
end
```

```pseudocode
proc fail_attempt_gaps(dims:FailureDims, attempts_seen:int):
  # Trigger: attempt indices not contiguous from 1..a
  rec ← make_failure_record("ATTEMPT_GAPS","merchant","attempt indices not contiguous",dims,
         attempts_opt:=attempts_seen)
  emit_failure_line(rec)
end

proc fail_final_missing(dims:FailureDims, attempts:int, k_last:int, regime:"inversion"|"ptrs", lambda_extra:float64):
  # Trigger: observed acceptance (last k≥1) but no ztp_final row.
  rec ← make_failure_record("FINAL_MISSING","merchant","acceptance observed but no finaliser",
         dims, attempts_opt:=attempts, lambda_opt:=lambda_extra, regime_opt:=regime)
  emit_failure_line(rec)
end

proc fail_multiple_final(dims:FailureDims):
  rec ← make_failure_record("MULTIPLE_FINAL","merchant","more than one ztp_final",dims)
  emit_failure_line(rec)
end

proc fail_cap_with_final_abort(dims:FailureDims, attempts:int):
  # Trigger: exhausted + policy=abort, yet a ztp_final exists.
  rec ← make_failure_record("CAP_WITH_FINAL_ABORT","merchant",
         "cap hit with policy=abort but finaliser present",dims,attempts_opt:=attempts)
  emit_failure_line(rec)
end

proc note_ztp_exhausted_abort(dims:FailureDims, attempts:int, lambda_extra:float64, regime:"inversion"|"ptrs"):
  # Outcome (not a producer bug): cap hit and policy=abort → log; no ztp_final is written.
  rec ← make_failure_record("ZTP_EXHAUSTED_ABORT","merchant",
         "cap hit; policy=abort (no finaliser)",dims,attempts_opt:=attempts,lambda_opt:=lambda_extra,regime_opt:=regime)
  emit_failure_line(rec)
end
```

```pseudocode
proc fail_trace_missing(dims:FailureDims, attempts:int):
  # Trigger: event append without the required cumulative trace append (one-event→one-trace).
  # Preferred path is to repair the missing TRACE using the persisted event envelope (§10/§13);
  # emit this record only if repair is not possible.
  rec ← make_failure_record("TRACE_MISSING","merchant","missing cumulative trace for event",dims,
         attempts_opt:=attempts)
  emit_failure_line(rec)
end
```

```pseudocode
proc fail_regime_invalid(dims:FailureDims, regime_str:string):
  # Trigger: regime ∉ {"inversion","ptrs"} or regime switched mid-merchant
  rec ← make_failure_record("REGIME_INVALID","merchant","invalid or switched regime",dims)
  emit_failure_line(rec)
end
```

```pseudocode
proc fail_rng_accounting(dims:FailureDims, attempts:int, reason:string):
  # Trigger: consuming row with draws≤0 OR blocks≠after−before; OR non-consuming advanced counters.
  rec ← make_failure_record("RNG_ACCOUNTING","merchant",reason,dims,attempts_opt:=attempts)
  emit_failure_line(rec)
end
```

```pseudocode
proc fail_upstream_missing_s2(dims:FailureDims, reason:string):
  rec ← make_failure_record("UPSTREAM_MISSING_S2","merchant",reason,dims)
  emit_failure_line(rec)
end

proc fail_upstream_missing_s3(dims:FailureDims, reason:string):
  rec ← make_failure_record("UPSTREAM_MISSING_S3","merchant",reason,dims)
  emit_failure_line(rec)
end

proc fail_upstream_missing_s1(dims:FailureDims, reason:string):
  rec ← make_failure_record("UPSTREAM_MISSING_S1","merchant",reason,dims)
  emit_failure_line(rec)
end
```

---

## 16.5 Run-scoped wrappers (structural/authority)

```pseudocode
proc fail_policy_invalid(dims:FailureDims, reason:string):
  rec ← make_failure_record("POLICY_INVALID","run",reason,dims)
  emit_failure_line(rec)
end

proc fail_stream_id_mismatch(dims:FailureDims, got_module:string, got_substream_label:string, got_context?:string):
  # Event streams must match (module, substream_label, context); trace has no context.
  rec ← make_failure_record("STREAM_ID_MISMATCH","run",
        "module/substream_label/context deviate from registry (events); trace has no context",dims)
  emit_failure_line(rec)
end

proc fail_partition_mismatch(dims:FailureDims):
  # Applies to EVENT rows only; trace rows omit embedded lineage (lineage via partition path).
  rec ← make_failure_record("PARTITION_MISMATCH","run",
        "path tokens {seed,parameter_hash,run_id} ≠ embedded event envelope",dims)
  emit_failure_line(rec)
end

proc fail_dict_bypass_forbidden(dims:FailureDims):
  rec ← make_failure_record("DICT_BYPASS_FORBIDDEN","run","producer used literal paths",dims)
  emit_failure_line(rec)
end

proc fail_zero_row_file(dims:FailureDims, family:string):
  rec ← make_failure_record("ZERO_ROW_FILE","run","zero-row file written in "+family,dims)
  emit_failure_line(rec)
end

proc fail_unknown_context(dims:FailureDims, got_context:string):
  rec ← make_failure_record("UNKNOWN_CONTEXT","run","context="+got_context+" (expected 'ztp')",dims)
  emit_failure_line(rec)
end
```

---

## 16.6 “No partial writes” & caller obligations (non-negotiable)

* **Merchant-scoped failure:** after emitting the failure line, the caller **MUST NOT** write any more S4 rows for that merchant.
* **Run-scoped failure:** after emitting the failure line, the caller **MUST** stop writing immediately.
  L0 only provides the surfaces to make it trivial for L1/L2 to comply.

---

## 16.7 Where other sections call these

* **§7 Guard:** `assert_finite_positive` → on failure call `fail_numeric_invalid(...)`.
* **§9 Emitters:** if envelope identities fail (shouldn’t happen with our preflight), call `fail_rng_accounting(...)`; if trace is missing in the crash window, first attempt **trace repair** (§10/§13); on unrecoverable, call `fail_trace_missing(...)`.
* **§12 Read-side gates:** path↔embed mismatch on S1/S2 inputs → `fail_partition_mismatch(...)`; dictionary bypass detected → `fail_dict_bypass_forbidden(...)`.

---

## 16.8 Acceptance for §16 (checklist)

* Failure payloads use **exact** frozen keys and optional fields.
* Codes & scopes match the state’s **stable vocabulary**; no invented codes. (If a wrapper name is state-internal, its `code` must be mapped to a canonical code in the bound vocabulary.)
* Surfaces are **values-only**; **no bundles, no RNG writes, no orchestration**.
* “**No partial writes**” semantics respected through caller obligations.

These helpers make failure reporting **mechanical and uniform**: one constructor, thin wrappers for each frozen code, and zero ambiguity about fields or scope—so an implementer can abort cleanly without risking drift from the S4 spec.

---

# 17) Edge-case catalogue (L0 scope)

> Purpose: enumerate every edge L0 must recognise **and** the exact thing to emit/do so an implementer can’t drift. Each item states the **symptom**, the **allowed behaviour** (what to write or not write), and the **helper/signal** to call. All rules are bound to the frozen S4 spec: A=0 short-circuit, regime threshold at $\lambda^\star = 10$, consuming vs non-consuming identities, **one-event → one-trace**, dictionary partitions `{seed, parameter_hash, run_id}`, and downstream contract that S4 fixes **$K_{\text{target}}$** only.

---

## 17.1 Gates & branch purity

**Symptom.** Merchant is single (`is_multi=false`) or ineligible (`is_eligible=false`).
**Allowed behaviour.** **Write nothing** for S4 for that merchant. Emit a branch-purity failure **only if** S4 was incorrectly invoked despite gates being false.
**Signal (only on incorrect invocation).**

```pseudocode
fail_branch_purity(dims, "S4 called for single or ineligible merchant")
```

---

## 17.2 $A = 0$ (no admissible foreigns)

**Symptom.** $A := \lvert S3.\text{candidate_set} \setminus \{home\} \rvert = 0$.
**Allowed behaviour.** **No attempts.** Still compute $(\lambda_{\text{extra}}, \text{regime})$ once, then emit exactly one **non-consuming**
`ztp_final{K_target=0, attempts=0, regime, lambda_extra[, reason:"no_admissible"]?}` — the optional `reason` appears **only** if the bound schema version defines it. **No other S4 rows.**
**Guard.**

```pseudocode
assert A == 0
emit_ztp_final_nonconsuming(..., K_target:=0, attempts:=0, exhausted_opt:=absent, reason_opt:=maybe_present)
```

If any attempt or a non-zero `K_target` occurs on $A=0$ ⇒ **producer bug**.
**Signal.**

```pseudocode
fail_a_zero_mishandled(dims, attempts_seen, regime)   # emit 'reason' only if schema includes it
```

---

## 17.3 $\lambda$ numeric guard (finite & strictly positive)

**Symptom.** `lambda_extra` is NaN/±Inf/≤0 (including −0.0).
**Allowed behaviour.** **Do not write attempts or final.** Emit a merchant-scoped failure line.
**Signal.**

```pseudocode
fail_numeric_invalid(dims, lambda_extra)
```

---

## 17.4 Regime boundary & constancy

**Symptom.**

* $\lambda_{\text{extra}} = 10$ (boundary) ⇒ regime must be `"ptrs"`.
* Any row shows a regime that differs from the frozen one for that merchant (mid-loop switch).

**Allowed behaviour.** Regime is computed **once** from $\lambda^\star$ and is **constant** across all S4 rows (attempts, markers, final).
**Signal.**

```pseudocode
fail_regime_invalid(dims, got_regime)
```

---

## 17.5 Attempt indexing, gaps & multiplicities

**Symptom.** Attempts are not `1..a` contiguous, or duplicates exist; multiple finalisers; acceptance observed (`k≥1`) but no finaliser.
**Allowed behaviour.** Exactly **one** consuming attempt row per **writer-sort key** `(merchant_id, attempt)`, **one** `ztp_rejection` per zero draw, **≤1** `ztp_retry_exhausted` per merchant, **exactly one** `ztp_final` for resolved merchants.
**Signals.**

```pseudocode
fail_attempt_gaps(dims, attempts_seen)
fail_final_missing(dims, attempts_last, k_last, regime, lambda_extra)
fail_multiple_final(dims)
```

---

## 17.6 Cap semantics (retry exhaustion)

**Symptom.** Zero-draw **cap** reached before acceptance.
**Allowed behaviour.**

* After the **last zero attempt**:
  * **Policy `"abort"`** ⇒ write the **non-consuming** `ztp_retry_exhausted{attempts, lambda_extra, aborted:true}` marker and **no `ztp_final`** (exactly one exhausted marker exists).
  * **Policy `"downgrade_domestic"`** ⇒ **do not** write an exhausted marker; write **one** `ztp_final{K_target=0, exhausted:true}` (non-consuming).

**Signals.**

```pseudocode
# Context (not a producer bug): cap + policy=abort (no finaliser)
note_ztp_exhausted_abort(dims, attempts, lambda_extra, regime)
# Bug: exhausted AND final exists under policy=abort
fail_cap_with_final_abort(dims, attempts)
```

*(`ztp_retry_exhausted` is an abort-only stream in the bound schema; `aborted:true` is required.)*

---

## 17.7 Envelope identities (consuming vs non-consuming)

**Symptom.**

* Consuming attempt row has `blocks ≠ after−before` or `draws ≤ "0"`.
* Non-consuming row changes counters or `draws ≠ "0"`.

**Allowed behaviour.** Enforce identities at emit time; otherwise signal RNG accounting failure.
**Check + Signal.**

```pseudocode
assert_envelope_identities("consuming"|"nonconsuming", s_before, s_after, draws_str)  # envelope fields rng_counter_*{lo,hi}
fail_rng_accounting(dims, attempt_or_attempts, "envelope identity violated")
```

---

## 17.8 Event→Trace pairing & crash window

**Symptom.** Event row appended and fsynced, but the **trace** row is missing (crash between event fsync and trace append).
**Allowed behaviour.** On resume, **attempt trace repair first** by appending the **trace only** once using the event’s envelope (`before/after/draws`). Re-emitting the event is forbidden. If unrecoverable, log a trace-missing failure.
**Signal (only if unrecoverable).**

```pseudocode
fail_trace_missing(dims, attempts_last)
```

---

## 17.9 Path↔embed equality & dictionary discipline

**Symptom.** Path tokens `{seed, parameter_hash, run_id}` don’t match embedded lineage; writer used a literal path or wrong partitions.
**Allowed behaviour.** Reject write; or if detected post-write, log a run-scoped failure. **All** writes must be **dictionary-resolved**.
**Signals.**

```pseudocode
fail_partition_mismatch(dims)       # applies to EVENT rows; trace omits embedded lineage
fail_dict_bypass_forbidden(dims)
```

---

## 17.10 Schema versions & optional fields

**Symptom.** Producer populates `ztp_final.reason` when the bound schema version **doesn’t** define it; mixed schema versions interleaved in the same partition.
**Allowed behaviour.** Only populate optional fields that exist in the bound schema; **never** interleave versions in a partition; consumers pin on `(module, schema version)` (or `(context, schema version)`).
**Action.** Treat mis-versioning as producer error (run-scoped).

---

## 17.11 Ordering & timestamps

**Symptom.** Timestamps collide or appear out of “wall-clock” order.
**Allowed behaviour.** **Counters provide total order**; file order is non-authoritative; timestamps are observational only. No action required if counters are correct.

---

## 17.12 Sampler budgets & totals

**Symptom.** Event `draws` and counter delta disagree; trace totals don’t match $\sum$ (event deltas).
**Allowed behaviour.** **Budgets are measured**: `draws` are **actual uniforms**, `blocks` from **counter delta**. Trace totals are **saturating u64** and must equal $\sum$ of per-event deltas.
**Check + Signal.**

```pseudocode
# reconcile before emit and before trace (authoritative trace write via S1 updater)
reconcile_consuming_budget(...) / reconcile_nonconsuming_budget(...)
# optional (test/audit): reconcile_trace_step(prev, blocks_delta, draws_str)
# if mismatch (should be impossible with our surfaces), then:
fail_rng_accounting(dims, attempt_or_attempts, "budget reconciliation failed")
```

---

## 17.13 Stream identifiers

**Symptom.** `module`, `substream_label`, or `context` don’t match the frozen identifiers (`1A.s4.ztp`, `poisson_component`, `"ztp"`).
**Allowed behaviour.** Reject and log run-scoped failure.
**Signal.**

```pseudocode
fail_stream_id_mismatch(dims, got_module, got_substream_label, got_context)  # trace has no context
```

---

## 17.14 Concurrency hazards (writer domain)

**Symptom.** Two writers append concurrently to the same `(family, seed, parameter_hash, run_id)` domain; unstable merges reorder equal keys.
**Allowed behaviour.** Single writer per domain **or** partitioned, **stable** merges only; publish with **stage → fsync → rename**.
**Reference.** See §13 contract (locks, atomic append, stable merge).

---

## 17.15 Downstream contract protection

**Symptom.** Consumer derives $K_{\text{target}}$ from counting attempts or uses $\lambda_{\text{extra}}$ as a weight; S4 rows attempt to encode cross-country order.
**Allowed behaviour.** **Only** `ztp_final.K_target` is authoritative; **S3** remains sole inter-country order authority; **S6** realises $K_{\text{realized}}=\min(K_{\text{target}}, A)$.
**Action.** Producer never encodes order or probabilities; consumer rules live in S6/S7 and validators.

---

### Acceptance for §17 (checklist)

* Every edge above maps to a **single, mechanical** action (emit, skip, or failure signal) with **no drift** from spec.
* A=0 path produces **only** a non-consuming `ztp_final{K_target=0, attempts=0[, reason?]}` (schema-versioned).
* Regime is **binary64-decided** at $\lambda^\star = 10$ and **never switches** mid-merchant.
* Envelope identities and **one-event→one-trace** are enforced on every row; counters, not file order, define total order.
* Dictionary partitions `{seed, parameter_hash, run_id}` and **path↔embed equality** (events) are verified **before write**.

This catalogue makes the weird corners **boring**: each is turned into a tiny, repeatable action or signal so an implementer (or intern) can’t get it wrong and validators will pass cleanly.

---

# 18) Versioning & compatibility (what’s frozen vs additive)

> Goal: make evolution **safe and boring**. This section fixes what is **frozen (breaking if changed)** vs what is **additive-safe**, how we **signal** versions, how to **cut over / dual-write / roll back**, and what **consumers** must pin to. Grounded in the frozen S4 spec (labels, partitions, regime threshold, dictionary authority, governance artefacts).

---

## 18.1 Frozen literals & constants — **breaking if changed**

* **Identifiers (events vs trace):**
  **Events:** `module = "1A.s4.ztp"`, `substream_label = "poisson_component"`, `context = "ztp"` — **breaking** to rename.
  **Trace:** `module = "1A.s4.ztp"`, `substream_label = "poisson_component"` (**no `context`** on trace) — **breaking** to rename.

* **Regime threshold:** $\lambda^\star = 10$ selects `inversion` vs `ptrs` (binary64 exact). **Breaking** to change.

* **Numeric profile:** IEEE-754 **binary64**, **RNE**, **FMA-off**, **no FTZ/DAZ**; **strict-open** $u\in(0,1)$. **Breaking** to change.

* **Event families (set & consuming semantics):**
  `rng_event_poisson_component` (**consuming**),
  `rng_event_ztp_final` / `rng_event_ztp_retry_exhausted` / `rng_event_ztp_final` (**non-consuming**).
  **Breaking** to add/remove or flip consuming semantics. *(Short names map 1:1 to these dataset families.)*

* **Trace family:** `rng_trace_log`. **Breaking** to alter semantics/identity.

* **Partitions (logs only):** all S4 streams (incl. trace) are written under `{seed, parameter_hash, run_id}`. **Breaking** to alter.

* **One-event → one-trace:** **exactly one** cumulative trace row appended by the **same writer, immediately after** every event row (crash-safe). **Breaking** to change.

* **File order non-authority:** validators use **counters**, not file order/timestamps. **Breaking** to soften.

---

## 18.2 Governance artefacts & `parameter_hash` (value-level evolution)

* **Governed container:** `crossborder_hyperparams` carries $\theta$, `MAX_ZTP_ZERO_ATTEMPTS`, `ztp_exhaustion_policy`. Its **serialized bytes participate in `parameter_hash`**. Defaults: cap **64** unless governance overrides.

* **Features:** governed $X_m \in [0,1]$ mapping and optional `X_default` participate in `parameter_hash` (precedence: governed `X_default` overrides 0.0; else use 0.0).

*Implication.* Governance changes are **compatible** across runs (new `parameter_hash`); they **do not** require schema bumps.

---

## 18.3 Schema evolution model (additive-safe vs breaking)

**Additive-safe (examples):**

* Add **optional** payload field (e.g., `ztp_final.reason:"no_admissible"` for A=0 short-circuit). Default **absent**; consumers **ignore unknown keys**.
* Add **values-only metrics** keys (out of logs).

**Breaking (examples):**

* Rename any of `module/substream_label/context` (events) or change $\lambda^\star$ or numeric profile.
* Make `ztp_final` **consuming**, or interleave schema versions in one `{seed, parameter_hash, run_id}` partition.

**Coexistence rules (MUST):**

* **Events:** consumers pin on **either** `(module, schema_version)` **or** `(context, schema_version)` and must not “best-effort” parse.
* **Trace:** consumers pin on `(module, schema_version)` (trace has **no `context`**).
* Producers **must not** interleave v1 and v2 rows in the **same** family/partition.

---

## 18.4 Version signalling & dictionary pinning

* The **Data Dictionary pins one exact schema anchor version per family** (anchor-suffix `@vN`). **No path-segment versioning.**
* **Run manifest** must expose `{module_version, schema_version}`.

  * `schema_version` is the dictionary-pinned anchor (normative).
  * `module_version` is an **ops label** (free-form; non-normative for parsing).
* Optional mirroring in `ztp_final` is allowed **only if the bound schema includes those optional audit fields**.

---

## 18.5 Dual-write, cutover, backfill, rollback

1. **Dual-write window (recommended):** Producer **may** write v1 and v2 **to distinct families declared in the Dictionary** (e.g., a shadow family ID); each family is pinned to one anchor. **Never** mix two anchors under one family/partition.

2. **Cutover & freeze:** After consumers confirm v2, **freeze v1** (no further writes) and mark **deprecated** in dictionary/registry.

3. **Backfill policy:** Byte-identical backfill requires the **same code & schema (`manifest_fingerprint`) and the same governance artefacts (`parameter_hash`)**. If the **code/spec contract** changed, backfill **only** under the new version tags/families—**never rewrite** old partitions.

4. **Rollback stance:** Never overwrite or delete published partitions. After rollback, resume with the previous stable `(module, schema_version)` pair; update the Dictionary so consumers pin back.

---

## 18.6 Compatibility matrix (quick decision aid)

| Change proposal                                       | Safe? | Action                                                                                  |
|-------------------------------------------------------|:-----:|-----------------------------------------------------------------------------------------|
| Add optional field to `ztp_final` (default absent)    |   ✅   | Bump schema **minor**, update Dictionary; dual-write optional.                          |
| Add values-only metrics key                           |   ✅   | No schema change; ship with release notes.                                              |
| Dual-write v1 + v2                                    |   ✅   | Use **separate families** (Dictionary entries), one anchor per family; no interleaving. |
| Change $\lambda^\star$ 10 → other                     |   ❌   | **Breaking**; spec & schema **major**; consumers pin new version.                       |
| Rename `context`/labels (events) or trace identifiers |   ❌   | **Breaking**; spec & schema **major**, Dictionary update.                               |
| Change partitions `{seed, parameter_hash, run_id}`    |   ❌   | **Breaking**; not allowed for S4 logs.                                                  |
| Interleave v1 & v2 rows in one partition              |   ❌   | Forbidden; split families/partitions; never mix anchors.                                |

---

## 18.7 Consumer & validator stance (when versions differ)

* **Consumers (S6+):** read only the **core** `ztp_final{K_target, lambda_extra, attempts, regime, exhausted?}`; **ignore unknown keys**; never infer probabilities from S4 logs. S3 order authority unchanged.

* **Validators:** tolerate **additive fields** but enforce **core invariants** (attempt accounting/cardinalities, consuming vs non-consuming identities, existence/absence of `ztp_final`, cap semantics, one-event→one-trace, partition discipline).

---

## 18.8 “What’s frozen” checklist (producer guardrails)

* Labels/contexts (events; trace has no `context`), regime threshold $\lambda^\star$, numeric profile, event/trace families & consuming semantics, partitions, **same-writer immediate** one-event→one-trace rule. **Do not change without spec major.**

* Dictionary & schema are **the** authorities; no path literals; **per-family** anchor versions are pinned by the Dictionary.

* Governance value changes ($\theta$, `X_default`, cap/policy) are **per-run** via `parameter_hash`—compatible and reproducible.

---

## 18.9 Minimal pseudocode hooks (producer/ops)

```pseudocode
proc version_signal_in_manifest() -> {module_version:string, schema_version:string}
  # MUST expose in run manifest; OPTIONAL to mirror in ztp_final payload (only if schema defines fields)
  return {
    module_version: "s4.l0@v1",                                # ops label (non-normative)
    schema_version: dict_schema_version(FAM_FINAL)             # dictionary-pinned anchor (normative)
  }
end
```

```pseudocode
proc ensure_schema_anchor_pinned(family:string):
  anchor := dict_schema_anchor(family)         # e.g., ...#/rng/events/ztp_final@v1
  assert anchor.ends_with("@vN")               # S4 uses anchor-suffix; Dictionary pins exact version
end
```

```pseudocode
proc forbid_interleaved_versions(partition:{seed,parameter_hash,run_id}, family:string):
  v := dict_schema_version(family)
  # Validate each row in the partition against the single dictionary-pinned anchor 'v'
  assert all(read_rows(partition, family).map(row -> validates_against_anchor(row, v)))
end
```

---

## 18.10 Acceptance for §18 (checklist)

* **Frozen vs additive** boundaries honoured exactly as above; breaking changes require spec/schema **major**.
* Dictionary **pins per-family anchor versions**; producers **do not** interleave schema versions per partition.
* Governance value changes are tracked by the **governance ledger** and tied to `parameter_hash`.
* Dual-write → **cutover & freeze** → rollback rules followed; **no rewrites** of published partitions.

This section locks S4’s evolution path so future edits are **predictable for implementers** and **safe for consumers**—with clear guardrails on what can change additively vs what demands a deliberate, pinned, breaking upgrade.

---

# 19) Acceptance gates for L0 (scope fences)

> Purpose: define **mechanical gates** L0 must pass before it’s signed off. These gates ensure L0 is (a) truly **helpers-only**, (b) **reuses** S0/S1/S2 surfaces (no reinvention), (c) stamps **schema-correct** events with ironclad **envelope identities**, (d) enforces **dictionary partitions** + **path↔embed equality**, (e) upholds **numeric/RNG** rules, and (f) guarantees **one-event → one-trace** with **crash-safe** behavior. All gates are specified as **language-agnostic pseudocode** you can drop into a preflight test or CI.

---

## 19.1 Gate matrix (what must be true)

1. **Scope fence:** L0 contains **no orchestration loops**, **no validators**, **no path literals**.
2. **Reuse fence:** All PRNG/trace/dictionary/codec/sampler functions are **imported** from S0/S1/S2; only S4-specific helpers/adapters/emitters are new.
3. **Literal fence:** `module="1A.s4.ztp"`, `substream_label="poisson_component"`, `context="ztp"` are fixed for **event** rows; **trace** carries `module/substream_label` only (no `context`).
4. **Partition fence:** All streams write under `{seed, parameter_hash, run_id}` resolved via **dictionary**; **path↔embed equality** holds on **event rows**; `rng_trace_log` omits embedded lineage (lineage via partition path).
5. **Substream fence:** All S4 events derive the **same** merchant-scoped substream (label `"poisson_component"`, Ids `[merchant_u64]`), order-invariant.
6. **Envelope fence:** **Consuming** rows: `after>before, blocks==Δ, draws>"0"`; **non-consuming** rows: `before==after, blocks=0, draws="0"`.
7. **Trace fence:** After **every** event append, the **same writer** appends **exactly one** cumulative trace row **immediately after** the event (saturating totals).
8. **Numeric/RNG fence:** binary64 (RNE), FMA-off, strict-open $u\in(0,1)$; λ guard (finite & >0); regime fixed by $\lambda^\star=10$; budgets **measured, not inferred**.
9. **Idempotence fence:** zero-row ban; re-runs produce **byte-identical** logs; **skip-if-final** respected; crash window repaired by appending **trace only**.
10. **Uniqueness fence:** ≤1 `rng_event_poisson_component` per `(merchant_id,attempt)`, ≤1 `rng_event_ztp_rejection` per `(merchant_id,attempt)`, ≤1 `rng_event_ztp_retry_exhausted` per merchant, **exactly one** `rng_event_ztp_final` per resolved merchant.

---

## 19.2 Static gates (compile-time / lint-time)

```pseudocode
proc gate_static_scope_and_reuse(symtab):
  # Scope fence
  assert not symtab.contains_any(["attempt_loop", "validator_", "validate_"])
  # Path literals ban
  assert not symtab.contains_regex(r"(s3|gs|file)://")      # all I/O is dictionary-resolved

  # Reuse fence: required imports present (values-only writer surfaces per §9/§10)
  require_imports := {
    "S0": ["derive_substream","philox_block","u01","uniform1","uniform2"],
    "S1": ["begin_event_micro","end_event_emit","update_rng_trace_totals",
           "dict_path_for_family","decimal_string_to_u128","u128_to_decimal_string",
           "u128_delta","u128_to_uint64_or_abort"],
    "S2": ["poisson_attempt_with_budget","assert_finite_positive"]
  }
  for (pkg, funcs) in require_imports:
    for f in funcs: assert symtab.imports.contains(pkg, f)

  # Only new S4 symbols allowed
  new_allowed := [
    "assert_finite_positive","compute_poisson_regime","freeze_lambda_regime",
    "poisson_attempt_once",
    "event_poisson_ztp","emit_ztp_rejection_nonconsuming",
    "emit_ztp_retry_exhausted_nonconsuming","emit_ztp_final_nonconsuming",
    "trace_after_event_s4",
    "prewrite_verify_partition_and_lineage","open_stream_for_write",
    "metrics_","fail_","reconcile_","assert_envelope_identities"
  ]
  assert symtab.new_exports ⊆ new_allowed
end
```

---

## 19.3 Literal & substream gates

```pseudocode
proc gate_literals_and_substream():
  assert MODULE == "1A.s4.ztp"
  assert SUBSTREAM_LABEL == "poisson_component"
  assert CONTEXT == "ztp"
  # Substream derivation is order-invariant and merchant-scoped (typed SER; order-insensitive)
  s1 := derive_substream(M, "poisson_component", [{tag:"merchant_u64", value:U64(42)}])
  s2 := derive_substream(M, "poisson_component", [{value:U64(42), tag:"merchant_u64"}])  # swapped order
  assert s1.key == s2.key and s1.ctr == s2.ctr
end
```

---

## 19.4 Partition & path↔embed gates

```pseudocode
proc gate_partition_and_lineage(lineage:Lineage, s_current:Stream):
  vp  := prewrite_verify_partition_and_lineage("rng_event_ztp_final", lineage)   # asserts dict keys = ["seed","parameter_hash","run_id"]
  ctx := begin_event_micro(MODULE,SUBSTREAM_LABEL, lineage.seed, lineage.parameter_hash, lineage.manifest_fingerprint, lineage.run_id, s_current)
  end_event_emit("rng_event_ztp_final", ctx, s_current, 0, 0, payload_min())
  row := tail_read(vp.path)                                    # last EVENT row written
  assert to_string(row.seed)                  == to_string(lineage.seed)
  assert lowercase_hex(row.parameter_hash)    == lowercase_hex(lineage.parameter_hash)
  assert lowercase_hex(row.run_id)            == lowercase_hex(lineage.run_id)
end
```

---

## 19.5 Envelope identity gates (consuming & non-consuming)

```pseudocode
proc gate_envelope_identities(s_before:Stream, s_current:Stream):
  # Consuming: simulate one sampler step
  (k, s_after, bud) := poisson_attempt_once(λ:=3.5, regime:compute_poisson_regime(3.5), s_before)
  (hi,lo) := u128_delta(s_after.ctr.hi, s_after.ctr.lo, s_before.ctr.hi, s_before.ctr.lo)
  del     := u128_to_uint64_or_abort(hi,lo)
  assert del == bud.blocks and (bud.draws_hi,bud.draws_lo) > 0_u128
  assert_envelope_identities("consuming", s_before, s_after, u128_to_decimal_string(bud.draws_hi,bud.draws_lo))

  # Non-consuming: identities must hold
  assert_envelope_identities("nonconsuming", s_current, s_current, "0")
end
```

---

## 19.6 One-event → one-trace gate (steady-state & crash window)

```pseudocode
proc gate_one_event_one_trace(lineage:Lineage, prev:TraceTotals):
  # Append a consuming attempt event
  ctx := begin_event_micro(...); end_event_emit("rng_event_poisson_component", ctx, s_after, bud.draws_hi, bud.draws_lo, payload_attempt())
  next := trace_after_event_s4(lineage, ctx.before_hi,ctx.before_lo, s_after.ctr.hi,s_after.ctr.lo,
                               u128_to_decimal_string(bud.draws_hi,bud.draws_lo))
  (hi,lo) := u128_delta(s_after.ctr.hi,s_after.ctr.lo, ctx.before_hi,ctx.before_lo)
  db      := u128_to_uint64_or_abort(hi,lo)
  du      := u128_to_uint64_or_abort(bud.draws_hi,bud.draws_lo)
  assert next.events_total == prev.events_total + 1
  assert next.blocks_total == prev.blocks_total + db
  assert next.draws_total  == prev.draws_total  + du

  # Crash window: event fsynced, trace missing → repair by appending trace only once
  ctx2 := begin_event_micro(...); end_event_emit("rng_event_ztp_rejection", ctx2, s_current, 0,0, payload_rej())
  repaired := trace_after_event_s4(lineage, s_current.ctr.hi, s_current.ctr.lo, s_current.ctr.hi, s_current.ctr.lo, "0")
  assert repaired.events_total == next.events_total + 1
end
```

---

## 19.7 Numeric/RNG gates (λ guard, regime threshold, strict-open)

```pseudocode
proc gate_numeric_and_regime():
  # λ guard
  expect_error assert_finite_positive(NaN)
  expect_error assert_finite_positive(0.0)
  assert assert_finite_positive(1e-12) == 1e-12

  # Regime threshold exactness (binary64)
  assert compute_poisson_regime(9.999999999999998) == "inversion"    # < 10
  assert compute_poisson_regime(10.0)              == "ptrs"         # == 10

  # Strict-open uniform: never 0.0 or 1.0 across many samples
  s := derive_substream(M,"poisson_component",[...])
  for t in 1..1_000_000:
    (u, s) := uniform1(s)
    assert 0.0 < u and u < 1.0
end
```

---

## 19.8 Uniqueness & writer-sort gates

```pseudocode
proc gate_uniqueness_and_sort():
  # Generate events for one merchant with attempts=1..a, including one k=0 and one acceptance
  emit attempt(1,k=0) → then ztp_rejection(attempt=1)
  emit attempt(2,k=3)
  emit ztp_final(K_target=3, attempts=2, exhausted:false)

  # Read back and verify on dataset families
  rows := read_partition("rng_event_poisson_component");   assert unique_keys(rows, key=(merchant_id,attempt))
  rej  := read_partition("rng_event_ztp_rejection");       assert unique_keys(rej,  key=(merchant_id,attempt))
  ex   := read_partition("rng_event_ztp_retry_exhausted"); assert at_most_one(ex, key=merchant_id)
  fin  := read_partition("rng_event_ztp_final");           assert exactly_one(fin,  key=merchant_id)

  # Sort keys must be respected
  assert is_sorted(rows, key=(merchant_id,attempt))
  assert is_sorted(rej,  key=(merchant_id,attempt))
  assert is_sorted(ex,   key=(merchant_id,attempts))
  assert is_sorted(fin,  key=(merchant_id))
end
```

---

## 19.9 Idempotence & skip-if-final gates

```pseudocode
proc gate_idempotence_and_skip_if_final(lineage:Lineage, M:MerchantId):
  # Run once: produce rows for merchant M
  run_s4_l0_slice(lineage, M)
  snap1 := checksum_partition(lineage)

  # Run again with IDENTICAL inputs: must no-op (skip-if-final)
  run_s4_l0_slice(lineage, M)
  snap2 := checksum_partition(lineage)
  assert snap2 == snap1   # byte-identical; no duplicate rows; zero-row ban holds
end
```

---

## 19.10 Exit criteria (L0 acceptance)

L0 is **accepted** when **all** gates pass:

* **Static**: scope/reuse/path-literal bans; imports present; only allowed new S4 symbols are exported.
* **Runtime**: literals/substreams fixed; partitions & path↔embed equality on **event rows**; envelope identities; one-event→one-trace (**same writer, immediate**, incl. crash repair); numeric/RNG invariants; uniqueness & sort keys; idempotence & skip-if-final.

> These gates make sign-off **deterministic**: pass them once and the implementation will be portable, crash-safe, and validator-provable—ready for L1/L2 to “hit the ground running.”

---

# 20) Call-sequence scaffolds (non-normative)

> These scaffolds show the **exact call order** an orchestrator would follow using S4·L0. They are **host-language agnostic**, **non-normative**, and obey the frozen S4 rules: logs-only streams, `{seed, parameter_hash, run_id}` partitions via the **Data Dictionary**, **one event → one trace** (by the same writer), **measured** budgets, $\lambda^\star=10$ regime, and $A=0$ short-circuit.

**Shared prelude (per merchant in scope)**

```pseudocode
# Inputs from upstream gates (already read & verified):
#   merchant_id:int64, A:int≥0 (admissible foreign count from S3), lineage:Lineage

# 0) Enter scope & derive per-merchant substream
metrics_enter_scope({lineage..., merchant_id})
merchant_u64 := LOW64( SHA256( LE64(merchant_id) ) )                         # S0 rule
# M comes from S0: derive_master_material(seed, manifest_fingerprint_bytes)
s := derive_substream(M, SUBSTREAM_LABEL, [{tag:"merchant_u64", value:merchant_u64}])   # §6

# 1) Freeze λ & regime (pure; may raise NUMERIC_INVALID)
lr := freeze_lambda_regime(lambda_extra_raw)                                  # §7
metrics_record_regime_once({lineage..., merchant_id}, lr.regime)

# 2) Short-circuit check (A=0 handled in Scenario D)
# 3) Initialize totals accumulator (optional; or read current from tail of rng/core/rng_trace_log)
tot := { blocks_total:=0, draws_total:=0, events_total:=0 }
```

---

## A) Acceptance on attempt 1 (no rejections)

```pseudocode
attempt := 1

# One Poisson attempt (pure adapter; no I/O)
(k, s_after, bud) := poisson_attempt_once(lr.lambda_extra, lr.regime, s)    # §8

# Consuming event (emitter writes event + trace; returns updated totals)
tot := event_poisson_ztp(merchant_id, lineage, s, s_after, lr, attempt, k, bud, prev:=tot)   # §9.1
# Metrics fire AFTER the emitter returns (after event+trace fsync)
metrics_after_event_append({lineage..., merchant_id}, "rng_event_poisson_component")     # §11

# Finaliser (non-consuming) — acceptance path
emit_ztp_final_nonconsuming(merchant_id, lineage, s_after, lr,
                            K_target:=k, attempts:=attempt, exhausted_opt:=absent, reason_opt:=absent)   # §9.4
metrics_on_final({lineage..., merchant_id},
                 K_target:=k, attempts:=attempt, regime:=lr.regime,
                 lambda_extra:=lr.lambda_extra, exhausted:=false, reason_opt:=absent)     # §11
```

*Identities:* attempt row is **consuming** (`after>before`, `blocks==Δ`, `draws>"0"`); final is **non-consuming** (`before==after`, `draws="0"`). Exactly **one** trace row follows each event append.

---

## B) Rejections then acceptance (e.g., accept on attempt 3)

```pseudocode
attempt := 1
loop:
  (k, s_after, bud) := poisson_attempt_once(lr.lambda_extra, lr.regime, s)
  tot := event_poisson_ztp(merchant_id, lineage, s, s_after, lr, attempt, k, bud, prev:=tot)
  metrics_after_event_append({lineage..., merchant_id}, "rng_event_poisson_component")

  if k == 0 then
     # Zero marker (non-consuming), same counters; writer-sort key (merchant_id, attempt)
     tot := emit_ztp_rejection_nonconsuming(merchant_id, lineage, s_after, lr, attempt)
     metrics_after_event_append({lineage..., merchant_id}, "rng_event_ztp_rejection")
     attempt := attempt + 1
     s := s_after
     continue loop
  else
     # Acceptance → finaliser (non-consuming)
     emit_ztp_final_nonconsuming(merchant_id, lineage, s_after, lr,
                                 K_target:=k, attempts:=attempt, exhausted_opt:=absent, reason_opt:=absent)
     metrics_on_final({lineage..., merchant_id},
                      K_target:=k, attempts:=attempt, regime:=lr.regime,
                      lambda_extra:=lr.lambda_extra, exhausted:=false, reason_opt:=absent)
     break
  end if
end loop
```

*Uniqueness:* ≤1 attempt row per `(merchant_id,attempt)`; ≤1 rejection per `(merchant_id,attempt)`; exactly **one** final per resolved merchant.

---

## C) Exhaustion path (cap reached before acceptance)

```pseudocode
attempt := 1
while attempt ≤ MAX_ZTP_ZERO_ATTEMPTS:             # from crossborder_hyperparams (governed; in parameter_hash)
  (k, s_after, bud) := poisson_attempt_once(lr.lambda_extra, lr.regime, s)
  tot := event_poisson_ztp(merchant_id, lineage, s, s_after, lr, attempt, k, bud, prev:=tot)
  metrics_after_event_append({lineage..., merchant_id}, "rng_event_poisson_component")

  if k == 0:
    tot := emit_ztp_rejection_nonconsuming(merchant_id, lineage, s_after, lr, attempt)
    metrics_after_event_append({lineage..., merchant_id}, "rng_event_ztp_rejection")
    attempt := attempt + 1
    s := s_after
    continue
  else:
    # accepted before cap → finalise as in Scenario A
    emit_ztp_final_nonconsuming(... K_target:=k, attempts:=attempt, exhausted_opt:=absent, ...)
    metrics_on_final(...)
    return
  end if
end while

if ztp_exhaustion_policy == "abort":
   # Cap hit — ABORT: write exhausted marker (non-consuming), once; no final
   tot := emit_ztp_retry_exhausted_nonconsuming(merchant_id, lineage, s, lr, attempts:=attempt-1)
   metrics_after_event_append({lineage..., merchant_id}, "rng_event_ztp_retry_exhausted")
   metrics_on_cap_abort({lineage..., merchant_id}, attempts:=attempt-1)
   return
else:  # "downgrade_domestic"
   # Cap hit — DOWNGRADE: no exhausted marker; write final only
   emit_ztp_final_nonconsuming(merchant_id, lineage, s, lr,
                               K_target:=0, attempts:=attempt-1, exhausted_opt:=true, reason_opt:=absent)
   metrics_on_final({lineage..., merchant_id},
                    K_target:=0, attempts:=attempt-1, regime:=lr.regime,
                    lambda_extra:=lr.lambda_extra, exhausted:=true, reason_opt:=absent)
   return
end if
```

*Policy rule:* `"abort"` ⇒ **no** finaliser; `"downgrade_domestic"` ⇒ finaliser with `K_target=0, exhausted:true`. Exactly one exhausted marker per merchant.

---

## D) $A = 0$ short-circuit (no admissible foreigns)

```pseudocode
if A == 0:
  # No attempts. Still derive (λ, regime) for observability uniformity.
  emit_ztp_final_nonconsuming(merchant_id, lineage, s_current:=s, lr,
                              K_target:=0, attempts:=0,
                              exhausted_opt:=absent,
                              reason_opt:= maybe("no_admissible") if schema has it)
  metrics_on_final({lineage..., merchant_id},
                   K_target:=0, attempts:=0, regime:=lr.regime,
                   lambda_extra:=lr.lambda_extra, exhausted:=false,
                   reason_opt:= maybe("no_admissible"))
  return
end if
```

*Only* the finaliser is written; **no** attempts or markers. If the bound schema version lacks `reason`, omit it.

---

## E) Crash-window repair (event fsynced, trace missing) — optional tool

```pseudocode
# On resume, if an EVENT was durably appended but its TRACE row is missing:
last := read_last_event_row(lineage, MODULE, SUBSTREAM_LABEL)    # envelope has rng_counter_* and draws (decimal-u128)
tot  := trace_after_event_s4(lineage,
                             last.rng_counter_before_hi, last.rng_counter_before_lo,
                             last.rng_counter_after_hi,  last.rng_counter_after_lo,
                             last.draws)                          # append trace ONLY once
# Optional metrics: increment just the rows counter
metrics_emit_counter({lineage..., merchant_id}, M_TRACE_ROWS, +1)
```

Do **not** re-emit the event; **append the trace only once**. In steady state, every emitter already appends trace.

---

### Notes common to all scenarios

* **Dictionary resolution only**; emitters write the event **and** one cumulative trace; metrics fire **after the emitter returns** (after event+trace fsync).
* **Envelope identities** are enforced by the emitters: attempts are **consuming**; markers/final are **non-consuming**.
* **Uniqueness & sort keys** hold by construction: `(merchant_id,attempt)` for attempts/rejections; `(merchant_id,attempts)` for exhausted; `(merchant_id)` for final.

These scaffolds let an implementer (or intern) wire S4 with **zero ambiguity**, while staying strictly within L0’s helpers-only scope and the frozen S4 contracts.

---

# 21) Appendix A — Literal tables

> One-stop, copy-from appendix of **exact identifiers, anchors, fields, enums and keys** used by S4·L0. These are **spec literals**—changing them is **breaking** unless explicitly marked additive/optional. All tables here are grounded in the **frozen S4 expanded** spec.

---

## 21.1 Shared identifiers (all S4 events)

| Literal           | Value               | Notes                                                               |
|-------------------|---------------------|---------------------------------------------------------------------|
| `module`          | `1A.s4.ztp`         | Frozen identifier on every S4 event & trace row.                    |
| `substream_label` | `poisson_component` | Single label for all four S4 families (one budgeting/trace domain). |
| `context`         | `ztp`               | Fixed context on S4 **events**; **trace has no context**.           |

---

## 21.2 Stream families → schema anchors → partitions → writer sort keys

| Family (Dictionary ID)          | JSON-Schema anchor (JSON-Pointer)                     | Consuming?     | Partitions (logs)                | Writer sort key                   |
|---------------------------------|-------------------------------------------------------|----------------|----------------------------------|-----------------------------------|
| `rng_event_poisson_component`   | `schemas.layer1.yaml#/rng/events/poisson_component`   | **Yes**        | `{seed, parameter_hash, run_id}` | `(merchant_id, attempt)`          |
| `rng_event_ztp_rejection`       | `schemas.layer1.yaml#/rng/events/ztp_rejection`       | No (marker)    | `{seed, parameter_hash, run_id}` | `(merchant_id, attempt)`          |
| `rng_event_ztp_retry_exhausted` | `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` | No (marker)    | `{seed, parameter_hash, run_id}` | `(merchant_id, attempts)`         |
| `rng_event_ztp_final`           | `schemas.layer1.yaml#/rng/events/ztp_final`           | No (finaliser) | `{seed, parameter_hash, run_id}` | `(merchant_id)`                   |
| `rng_trace_log`                 | `schemas.layer1.yaml#/rng/core/rng_trace_log`         | (trace)        | `{seed, parameter_hash, run_id}` | n/a (cumulative per module/label) |

**Mandatory equalities.** For **event rows**, embedded `{seed, parameter_hash, run_id}` **byte-match** the path tokens; trace rows **omit** embedded lineage (lineage via partition path) and have **no `context`**. All paths are **dictionary-resolved** (no literals). **File order is non-authoritative**; counters give total order.

---

## 21.3 Envelope (minimum fields & identities)

| Field                           | Type / Format                  | Notes                                                 |
|---------------------------------|--------------------------------|-------------------------------------------------------|
| `ts_utc`                        | string (UTC, **µs precision**) | Exactly 6 fractional digits (truncate); observational |
| `module`                        | `1A.s4.ztp`                    | See §21.1.                                            |
| `substream_label`               | `poisson_component`            | See §21.1.                                            |
| `context`                       | `ztp`                          | Events only; **trace has no context**.                |
| `rng_counter_before_lo`, `…_hi` | `u64`                          | Philox 128-bit counter (start).                       |
| `rng_counter_after_lo`,  `…_hi` | `u64`                          | Philox 128-bit counter (end).                         |
| `blocks`                        | `u64`                          | `u128(after) − u128(before)` (writer computes).       |
| `draws`                         | **decimal u128 string**        | **Actual uniforms consumed**; `"0"` on non-consuming. |

**Identities (must).**
Consuming rows: `after>before`, `blocks==Δ`, `draws>"0"`.
Non-consuming rows: `before==after`, `blocks=0`, `draws="0"`.

---

## 21.4 Payload minima per family

**Types used:** `merchant_id:int64`, `attempt:int≥1`, `attempts:int≥0`, `k:int≥0`, `K_target:int≥0`, `lambda_extra:float64`, `regime∈{"inversion","ptrs"}`, `exhausted:bool`, `reason∈{"no_admissible"}` *(optional; only if that schema version defines it)*.

| Family                           | Payload (minimum fields)                                                               |
|----------------------------------|----------------------------------------------------------------------------------------|
| `rng_event_poisson_component`   | `{ merchant_id, attempt, k, lambda_extra, regime }`                                    |
| `rng_event_ztp_rejection`       | `{ merchant_id, attempt, k:0, lambda_extra }`                                          |
| `rng_event_ztp_retry_exhausted` | `{ merchant_id, attempts, lambda_extra [, aborted:true]? }` *(policy flag if defined)* |
| `rng_event_ztp_final`           | `{ merchant_id, K_target, lambda_extra, attempts, regime, exhausted? [, reason?] }`    |

**Cardinality.** ≤1 `poisson_component` per `(merchant_id,attempt)`; ≤1 `ztp_rejection` per `(merchant_id,attempt)`; ≤1 `ztp_retry_exhausted` per merchant; **exactly one** `ztp_final` per **resolved** merchant (absent only on hard abort).

---

## 21.5 Closed enums & constants

| Name                    | Values / Constant                  | Notes                                                              |
|-------------------------|------------------------------------|--------------------------------------------------------------------|
| `regime`                | `{"inversion","ptrs"}`             | Chosen once per merchant by $\lambda^\star = 10$ (binary64 exact). |
| `ztp_exhaustion_policy` | `{"abort","downgrade_domestic"}`   | Governed in `crossborder_hyperparams`; bytes in `parameter_hash`.  |
| `reason` *(optional)*   | `{"no_admissible"}`                | Only if bound `ztp_final` schema version defines it.               |
| **Numeric profile**     | binary64, RNE, FMA-off, no FTZ/DAZ | Strict-open $u\in(0,1)$; budgets **measured**.                     |

---

## 21.6 Substream derivation (SER/UEL literals)

| Element              | Literal / Rule                                                           | 
|----------------------|--------------------------------------------------------------------------|
| PRNG label           | `"poisson_component"` (all S4 families share it)                         |
| SER tag set (closed) | `{ "merchant_u64", "iso", "i", "j" }` *(S4 uses **merchant_u64** only)* |
| `merchant_u64`       | `LOW64( SHA256( LE64(merchant_id:int64) ) )`                             |
| Message layout       | `UER("mlr:1A") \|\| UER(label) \|\| SER(Ids)` (no delimiters)            |
| Domain               | One substream per merchant; same for attempts, markers, final.           |

*If `iso` is ever used in other states, it must be **UPPERCASE ASCII** before UER/SER (S0 rule).*

**Trace domain.** All events share one trace domain `(module="1A.s4.ztp", substream_label="poisson_component")`; **one cumulative trace row per event** appended by the **same writer, immediately after** the event.

---

## 21.7 Dictionary dataset IDs (no path literals)

| Constant        | Dictionary family (ID)          |
|-----------------|---------------------------------|
| `FAM_POISSON`   | `rng_event_poisson_component`   |
| `FAM_REJECTION` | `rng_event_ztp_rejection`       |
| `FAM_EXHAUSTED` | `rng_event_ztp_retry_exhausted` |
| `FAM_FINAL`     | `rng_event_ztp_final`           |
| `FAM_TRACE`     | `rng_trace_log`                 |

**Partitions declared by Dictionary:** always `{seed, parameter_hash, run_id}` for S4 logs; **path↔embed equality** enforced (events; trace omits embedded lineage).

---

## 21.8 Governance artefact & participation in `parameter_hash`

| Artefact name             | Keys it carries                                                                                       | Participates in `parameter_hash` |
|---------------------------|-------------------------------------------------------------------------------------------------------|----------------------------------|
| `crossborder_hyperparams` | `θ` (ZTP link params), `MAX_ZTP_ZERO_ATTEMPTS`, `ztp_exhaustion_policy` (and `X_default` if governed) | **Yes**                          |

**Default cap**: `MAX_ZTP_ZERO_ATTEMPTS = 64` unless governance overrides.

---

## 21.9 Field encodings & formatting

| Field    | Encoding rule                                                                                              |
|----------|------------------------------------------------------------------------------------------------------------|
| `draws`  | **decimal u128 string** (non-negative base-10; **no leading zeros** except `"0"`; `"0"` for non-consuming) |
| `ts_utc` | UTC string with **exactly 6 fractional digits** (microseconds; truncate, no rounding).                     |
| Booleans | JSON `true`/`false` (no ints for booleans).                                                                |
| Integers | JSON numbers; `merchant_id:int64`, `attempt:int≥1`, `attempts:int≥0`, `K_target:int≥0`.                    |
| Floats   | JSON numbers; **binary64** arithmetic upstream; no stringified floats.                                     |

All numbers **stay numbers**; use shortest **round-trip** JSON.

---

## 21.10 Consuming vs non-consuming summary (quick crib)

| Family                           | Consuming? | Counters change?            | `draws` value            |
|----------------------------------|------------|-----------------------------|--------------------------|
| `rng_event_poisson_component`   | **Yes**    | `after>before`, `blocks>0`  | `>"0"` (actual uniforms) |
| `rng_event_ztp_rejection`       | No         | `before==after`, `blocks=0` | `"0"`                    |
| `rng_event_ztp_retry_exhausted` | No         | `before==after`, `blocks=0` | `"0"`                    |
| `rng_event_ztp_final`           | No         | `before==after`, `blocks=0` | `"0"`                    |

One event append **→** one cumulative `rng_trace_log` append (same `(module, substream_label)`); **same writer** performs both **immediately**.

---

## 21.11 Writer sort keys & uniqueness

| Family                          | Writer sort key           | Uniqueness per merchant     |
|---------------------------------|---------------------------|-----------------------------|
| `rng_event_poisson_component`   | `(merchant_id, attempt)`  | ≤1 per key                  |
| `rng_event_ztp_rejection`       | `(merchant_id, attempt)`  | ≤1 per key                  |
| `rng_event_ztp_retry_exhausted` | `(merchant_id, attempts)` | ≤1 total                    |
| `rng_event_ztp_final`           | `(merchant_id)`           | **Exactly 1** when resolved |

Violations are producer bugs; see §16 for failure signals.

---

## 21.12 Acceptance crib (emitters)

* Use **Dictionary** to resolve paths; partitions = `{seed, parameter_hash, run_id}`.
* Stamp envelope **identities**; budgets are **measured** (draws) and **counter-derived** (blocks).
* Append **one** cumulative trace row **after** each event append (same writer, immediate).
* Keep **regime** fixed ($\lambda^\star=10$); **A=0** path writes only `ztp_final{K_target=0, attempts=0[, reason?]}`.

This appendix is the **single source** of S4 literals and closed vocabularies—pinning identifiers, fields, anchors, partitions, enums, and sort keys so implementers can code directly without hunting other documents.

---

# 22) Appendix B — Import provenance matrix

> Single place that shows **every helper S4·L0 uses**, **where it comes from**, and the **contract we rely on**. If a name exists in multiple states, we show the **required variant** (e.g., S1’s *saturating* trace). No bodies here—just binding surfaces, so implementers and reviewers can verify reuse at a glance.

---

## A) PRNG core & substreams (REUSE from S0·L0)

| S4 surface (used in §§6–9,15)             | Origin    | Contract we depend on                                                                                       |     
|-------------------------------------------|-----------|-------------------------------------------------------------------------------------------------------------|
| `derive_substream(M,label,Ids) -> Stream` | **S0·L0** | Order-invariant: `UER("mlr:1A") \|\| UER(label) \|\| SER(Ids)`; SER v1 tags `{iso,merchant_u64,i,j}` only.  |     
| `philox_block(s) -> (x0,x1,s')`           | **S0·L0** | PHILOX-2×64-10; **advances counter by +1 block**.                                                           |     
| `u01(x) -> float64`                       | **S0·L0** | **Strict-open** mapping to (0,1); if it rounds to 1.0, remap to `1−2⁻⁵³`.                                   |     
| `uniform1(s)` / `uniform2(s)`             | **S0·L0** | **Low lane** single / **both lanes** from one block; budgets = **actual uniforms** (1 / 2).                 |     
| `normal_box_muller(s)`                    | **S0·L0** | Consumes **exactly one block**; **2 uniforms**; **no cache**; `TAU` hex literal.                            |     
| `merchant_u64_from_id64(id64)`            | **S0·L0** | Canonical typed scalar: `LOW64(SHA256(LE64(id64)))` for SER.                                                |     

---

## B) Writer / trace / dictionary (REUSE S0/S1)

| S4 surface (used in §§9–12,15)                                                                             | Origin               | Contract we depend on                                                                                                                                                                                                                              |
|------------------------------------------------------------------------------------------------------------|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `begin_event_micro(...) -> EventCtx`                                                                       | **S1·L0**            | **Microsecond** `ts_utc` (exactly 6 digits; **truncate**), captures `{seed, parameter_hash, manifest_fingerprint, run_id}` and `rng_counter_before_{hi,lo}`.                                                                                       |
| `end_event_emit(family, ctx, stream_after, draws_hi, draws_lo, payload)`                                   | **S1·L0 (required)** | Writes one JSONL row; writer computes `blocks = u128(after) − u128(before)`; encodes **decimal-u128 `draws`**; asserts non-consuming equality when `draws=="0"`.                                                                                   |
| `update_rng_trace_totals(draws_str, MODULE, SUBSTREAM_LABEL, seed, parameter_hash, run_id) -> TraceTotals` | **S1·L0 (required)** | **Saturating `u64`** cumulative trace; **one row per event** by the **same writer immediately after** the event; partitions `{seed, parameter_hash, run_id}`; trace rows **do not embed lineage** (no `seed/parameter_hash/run_id`; no `context`). |
| `dict_path_for_family(family,seed,parameter_hash,run_id)`                                                  | **S0·L0**            | **Dictionary-resolved** paths only; no literals.                                                                                                                                                                                                   |

---

## C) 128-bit counters & codecs (REUSE S1)

| S4 surface (used in §§9–10,15)                                 | Origin    | Contract we depend on                                                                            |
|----------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------|
| `decimal_string_to_u128(s) -> (hi,lo)`                         | **S1·L0** | Authoritative **decimal-u128** parser for `draws` (non-negative; `"0"` or no leading zeros).     |
| `u128_to_decimal_string(hi,lo) -> string`                      | **S1·L0** | Partner encoder used by emitters before trace.                                                   |
| `u128_delta(after_hi,after_lo,before_hi,before_lo) -> (hi,lo)` | **S1·L0** | Counter delta; pair with…                                                                        |
| `u128_to_uint64_or_abort(hi,lo) -> u64`                        | **S1·L0** | …downcast for per-event `blocks` and for trace totals (writer applies **saturating** semantics). |

---

## D) Sampler capsules & numeric guards (REUSE S2·L0)

| S4 surface (used in §8)                      | Origin    | Contract we depend on                                                                                                                                                |
|----------------------------------------------|-----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `poisson_attempt_with_budget(λ: float64, s)` | **S2·L0** | **Inversion if λ<10; PTRS otherwise** (normative constants). Returns `(k, s', AttemptBudget{blocks,draws_hi,draws_lo})` with **measured** budgets (actual uniforms). |
| `assert_finite_positive(x: float64, name)`   | **S2·L0** | **Hard error** if NaN/±Inf or ≤0; reused for λ guard in S4.                                                                                                          |

---

## E) Types & records we reuse (no re-defs)

| Type                                                  | Origin    | Notes                                               |
|-------------------------------------------------------|-----------|-----------------------------------------------------|
| `Stream { key:u64, ctr:{hi:u64,lo:u64} }`             | **S0·L0** | Philox stream; **one block per `philox_block`**.    |
| `EventCtx`                                            | **S1·L0** | From `begin_event_micro`; carries envelope prelude. |
| `TraceTotals {blocks_total,draws_total,events_total}` | **S1·L0** | **Saturating** cumulative counters used by trace.   |

---

## F) Defined **here** in S4·L0 (new surfaces)

| S4·L0 surface                                                                                                                     | Role              | Notes                                                                                                                                           |
|-----------------------------------------------------------------------------------------------------------------------------------|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `assert_finite_positive`, `compute_poisson_regime`, `freeze_lambda_regime`                                                        | **Pure** helpers  | Binary64 guard + $\lambda^\star=10$ regime label (fixed per merchant). (Defined in §7.)                                                         |
| `poisson_attempt_once`                                                                                                            | **Pure adapter**  | Calls S2’s capsule **once**; returns `(k,s_after,AttemptBudget)`; **no I/O**. (Defined in §8.)                                                  |
| `event_poisson_ztp` · `emit_ztp_rejection_nonconsuming` · `emit_ztp_retry_exhausted_nonconsuming` · `emit_ztp_final_nonconsuming` | **Emitters**      | The four S4 event families; **one event → one trace**; dictionary-resolved; partitions `{seed,parameter_hash,run_id}`. (Defined in §9.)         |
| `trace_after_event_s4`                                                                                                            | **Trace wrapper** | Asserts envelope identities then calls **S1** `update_rng_trace_totals(draws_str, MODULE, SUBSTREAM_LABEL, seed, parameter_hash, run_id)` once. |
| `prewrite_verify_partition_and_lineage`, `open_stream_for_write`                                                                  | **Guards**        | Enforce dictionary partitions and **path↔embed equality** before write. (Defined in §12.)                                                       |

---

## G) Explicitly **not** imported (to prevent drift)

* Any legacy/non-saturating trace updater (**do not** use S0’s totals variant in S4).
* Any event wrappers from other states (payload/labels differ). S4 defines its own **ZTP** emitters.
* Any path string literals (all I/O is **Data Dictionary** resolved).

---

## H) Quick cross-refs (where to read the originals)

* **S0·L0** (PRNG, substreams, `u01`, `uniform1/2`, normal, merchant scalar, dictionary): *S0 L0 — PRNG & Dictionary surfaces*.
* **S1·L0** (microsecond `begin_event_micro`, decimal-u128 parser/encoder, *saturating* trace): *S1 L0 — Writer & Trace surfaces*.
* **S2·L0** (Poisson capsule, budgets, PTRS constants, guards): *S2 L0 — Poisson capsule & Numeric guards*.

---

## Acceptance for Appendix B

* Every S4·L0 call-site points to a **single upstream helper** (no re-definitions).
* **S1 trace updater** is the only trace writer (saturating) used in S4.
* All I/O paths are **dictionary-resolved**; **no literals** appear in S4·L0.
* The only **new** code in S4·L0 is S4-specific glue (pure helpers, adapter, emitters, guards); **everything else is imported** exactly as above.

---

# 23) Appendix C — Field encodings & rounding

> Single, copy-from appendix for **wire formats**: JSONL framing, envelope/payload field encodings, exact decimal/u128 grammar for `draws`, timestamp precision, integer domains, float printing and rounding rules, counter pairing (hi/lo), and consuming vs non-consuming identities. All rules here mirror the **frozen S4 expanded** spec and inherited S0/S1/S2 contracts.

---

## C.1 JSONL framing & character set

* **One JSON object per line**, UTF-8, terminated by `\n`. No BOM. (Consumers treat **line boundaries** as record boundaries.)
* Object key **order is non-semantic**; equality is by **field names/values**, not physical order. (Counter arithmetic always uses the named hi/lo fields; see C.3.)

---

## C.2 Envelope fields (minimum & formats)

| Field                        | Type / Encoding         | Rules                                                                                                                                                                     |
|------------------------------|-------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ts_utc`                     | string                  | RFC-3339 UTC with **exactly 6 fractional digits** (microseconds), trailing `Z`. **Truncate** to 6 digits (**no rounding**). Observational only—**not** used for ordering. |
| `module`                     | string                  | **`"1A.s4.ztp"`** (frozen).                                                                                                                                               |
| `substream_label`            | string                  | **`"poisson_component"`** (frozen; shared by all S4 events).                                                                                                              |
| `context`                    | string                  | **`"ztp"`** on **event** rows; **trace has no context**.                                                                                                                  |
| `seed`                       | uint64 (JSON number)    | Non-negative, 64-bit unsigned.                                                                                                                                            |
| `parameter_hash`             | hex64 string            | Lower-case hex; equals path token **byte-for-byte**.                                                                                                                      |
| `manifest_fingerprint`       | hex64 string            | Lower-case hex (embedded only; not a path key).                                                                                                                           |
| `run_id`                     | hex32 string            | Lower-case hex; equals path token **byte-for-byte**.                                                                                                                      |
| `rng_counter_before_{lo,hi}` | uint64                  | 128-bit **before** counter split into two u64 words.                                                                                                                      |
| `rng_counter_after_{lo,hi}`  | uint64                  | 128-bit **after** counter split into two u64 words.                                                                                                                       |
| `blocks`                     | uint64                  | **Unsigned** 64-bit; **must equal** `u128(after) − u128(before)` (see C.3).                                                                                               |
| `draws`                      | **decimal u128 string** | **Authoritative uniforms consumed** (grammar in **C.4**). `"0"` for non-consuming events.                                                                                 |

**Mandatory equalities (identities):**

* **Consuming** (`rng_event_poisson_component`): `after > before`, `blocks == u128(after) − u128(before)`, `parse_u128(draws) > 0`.
* **Non-consuming** (`rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`, `rng_event_ztp_final`): `before == after`, `blocks == 0`, `draws == "0"`. **File order is non-authoritative**; counters drive replay.

---

## C.3 128-bit counters & arithmetic (pairing & deltas)

* Compose the 128-bit integer as the pair **(hi, lo)**: `U = (hi << 64) | lo`. Field names carry their role (`…_lo`, `…_hi`); key order in JSON is irrelevant.
* **Delta rule (authoritative):**
  `blocks := u128(after_hi,after_lo) − u128(before_hi,before_lo)` (unsigned 128-bit arithmetic), then **downcast** to uint64 with **fail-on-overflow**. *Totals are `u64`; single-event `blocks` must fit `u64`; overflow is a producer error.*

---

## C.4 `draws` — decimal-u128 string **grammar** (authoritative)

* **No sign, no exponent**, ASCII digits only.
* Either exactly `"0"`, **or** a non-zero canonical form with no leading zeros.

```
REGEX: ^(0|[1-9][0-9]*)$
```

* Parser is the S1 authoritative routine `decimal_string_to_u128`; encoder is `u128_to_decimal_string`. Use **only** these.

---

## C.5 Floating-point fields (binary64) & JSON printing

* All float payload fields (e.g., `lambda_extra`) are **IEEE-754 binary64** results produced in a **fixed operation order**. **FMA-off**, **no FTZ/DAZ**.
* **Printing rule:** use “**shortest round-trip**” binary64 → JSON (emit the minimal decimal that parses back to the same binary64). Do **not** stringify as text; **do not** force fixed precision.
* **Only one float comparison drives control flow** (outside S4’s emitters): the **regime** threshold at **$\lambda^\star = 10$**: `λ < 10 → "inversion"`, `λ ≥ 10 → "ptrs"`. No epsilons.
* **Numbers stay numbers**: all numeric fields are JSON numbers (no quoted floats/ints).

---

## C.6 Integer & enum domains (payload)

| Name          | Type / Domain                | Notes                                                                                     |
|---------------|------------------------------|-------------------------------------------------------------------------------------------|
| `merchant_id` | int64                        | From ingress S1/S2/S3; JSON number.                                                       |
| `attempt`     | int ≥ 1                      | 1-based, strictly increasing per merchant.                                                |
| `attempts`    | int ≥ 0                      | `0` **only** on A=0 short-circuit; else equals last attempt index.                        |
| `k`           | int ≥ 0                      | Poisson draw at that attempt.                                                             |
| `K_target`    | int ≥ 0                      | Accepted/capped target.                                                                   |
| `regime`      | `"inversion"` \| `"ptrs"`    | Fixed per merchant (λ★ rule).                                                             |
| `exhausted`   | bool                         | Present **only** on downgrade policy path.                                                |
| `reason`      | `"no_admissible"` (optional) | Present **only** if the bound `ztp_final` schema version defines it, and only on **A=0**. |

---

## C.7 Open-interval uniforms (strict-open mapping)

Uniforms are generated on the **open** interval $u\in(0,1)$ with the S0 hex-literal multiplier:

```
u = ((x + 1) * 0x1.0000000000000p-64)  ∈ (0,1),  x ∈ {0,…,2^64−1}
if u == 1.0: u := 0x1.fffffffffffffp-1   # 1 − 2^−53
```

This mapping does **not** affect `blocks`/`draws` identities (budgets remain measured/derived as specified).

---

## C.8 Consuming vs non-consuming **budget tables** (quick crib)

| Family                          | Consuming? | Counter delta                    | `draws`                      |
|---------------------------------|------------|----------------------------------|------------------------------|
| `rng_event_poisson_component`   | Yes        | `after > before` → `blocks > 0`  | `>"0"` (**actual uniforms**) |
| `rng_event_ztp_rejection`       | No         | `before == after` → `blocks = 0` | `"0"`                        |
| `rng_event_ztp_retry_exhausted` | No         | `before == after` → `blocks = 0` | `"0"`                        |
| `rng_event_ztp_final`           | No         | `before == after` → `blocks = 0` | `"0"`                        |

**Budgets are measured, not inferred**: `draws` comes from the sampler; `blocks` from counter delta.

---

## C.9 Path ↔ embed equality & partitions (logs-only)

All S4 streams write under:

```
.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

For **event rows**, the embedded `{seed, parameter_hash, run_id}` **byte-match** the path tokens (dictionary-resolved; **no** path literals). Trace rows **omit** embedded lineage (lineage via partition path) and carry **no `context`**.

---

## C.10 Example **minimal** rows (illustrative encodings)

> The examples below are **illustrative snapshots** (not one merchant timeline). Hex strings shortened for readability.

**Attempt (consuming):**

```json
{"ts_utc":"2025-08-15T10:03:12.345678Z","module":"1A.s4.ztp","substream_label":"poisson_component","context":"ztp",
 "seed":7,"parameter_hash":"ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12",
 "manifest_fingerprint":"cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34",
 "run_id":"deab12deab12deab12deab12deab12de",
 "rng_counter_before_lo":1,"rng_counter_before_hi":0,"rng_counter_after_lo":3,"rng_counter_after_hi":0,
 "blocks":2,"draws":"3",
 "merchant_id":12345,"attempt":2,"k":2,"lambda_extra":3.5,"regime":"inversion"}
```

**Zero marker (non-consuming):**

```json
{"ts_utc":"2025-08-15T10:03:12.345679Z","module":"1A.s4.ztp","substream_label":"poisson_component","context":"ztp",
 "seed":7,"parameter_hash":"ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12",
 "manifest_fingerprint":"cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34",
 "run_id":"deab12deab12deab12deab12deab12de",
 "rng_counter_before_lo":3,"rng_counter_before_hi":0,"rng_counter_after_lo":3,"rng_counter_after_hi":0,
 "blocks":0,"draws":"0",
 "merchant_id":12345,"attempt":2,"k":0,"lambda_extra":3.5}
```

**Finaliser (non-consuming):**

```json
{"ts_utc":"2025-08-15T10:03:12.345680Z","module":"1A.s4.ztp","substream_label":"poisson_component","context":"ztp",
 "seed":7,"parameter_hash":"ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12",
 "manifest_fingerprint":"cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34",
 "run_id":"deab12deab12deab12deab12deab12de",
 "rng_counter_before_lo":3,"rng_counter_before_hi":0,"rng_counter_after_lo":3,"rng_counter_after_hi":0,
 "blocks":0,"draws":"0",
 "merchant_id":12345,"K_target":2,"lambda_extra":3.5,"attempts":2,"regime":"inversion"}
```

All three satisfy the identities in **C.2/C.3/C.8**; counters give the total order; timestamps are observational only.

---

## C.11 Quick acceptance crib (encodings)

* `ts_utc` has **exactly 6** fractional digits (truncate; no rounding).
* `draws` matches **C.4 regex**; `"0"` only for non-consuming.
* `blocks == u128(after) − u128(before)`; consuming rows have `blocks>0` & `draws>"0"`.
* Floats print with **shortest round-trip**; binary64 math profile holds; **numbers stay numbers**.
* For **event rows**, embedded `{seed, parameter_hash, run_id}` **byte-match** path tokens; paths are **dictionary-resolved**. Trace rows omit embedded lineage and carry no `context`.

This appendix pins every wire-level decision—so an implementer (or validator author) can encode/parse S4 rows **without guesswork** and remain perfectly aligned with the frozen spec.

---