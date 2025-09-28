# S4 · L3 Validator

## 1) Scope & Non-Goals

**Purpose (what L3 does):**
Validate, **read-only**, that S4 outputs conform **byte-for-byte** to the S4 spec & contracts. Emit only verdict artifacts per merchant: `_passed.flag` **or** `_failed.json`.

**What L3 must prove (per merchant):**

* **Labels & literals**

  * `module == "1A.ztp_sampler"`
  * `substream_label == "poisson_component"`
  * `context == "ztp"` on **all S4 events**; **absent** on trace
* **Partitions & lineage**

  * **Events** reside under `{seed, parameter_hash, run_id}` and **embed == path** for those keys
  * **Trace** resides under `{seed, parameter_hash, run_id}` but **embeds only `{seed, run_id}`** (no `parameter_hash`, no `context`)
* **Identities**

  * **Attempts** are **consuming** (`after > before`, `draws > "0"`)
  * **Rejection / Exhausted / Final** are **non-consuming** (`after == before`, `draws == "0"`)
* **Event → Trace adjacency**

  * After **every event**, there is **exactly one** immediate **cumulative** trace row (same `(module, substream_label)`), and trace deltas equal that event’s **measured** budgets & counter movement; totals are saturating & monotone
* **Attempt sequence & resume**

  * Attempts contiguous **1..n** with **n ≤ 64**, no gaps/dupes
  * If resuming, start at `max(attempt) + 1`; **never** re-emit prior attempts
  * Ordering & replay are derived from **counters**, not file order
* **Terminal correctness (exactly one legal outcome)**

  * **Accept:** first `K ≥ 1` → one **final**, **no** exhausted
  * **Cap-abort:** attempts = 64 → one **exhausted**, **no** final
  * **Cap-downgrade:** attempts = 64 → one **final** flagged exhausted, **no** exhausted marker
  * **A = 0:** one **final** only (no attempts/markers)
* **Gates**

  * Presence of any S4 rows ⇒ **S1.is_multi == true** **and** **S3.is_eligible == true**
  * If S3 implies **A = 0**, S4 must be **final-only**

**Non-Goals (explicitly out of scope):**

* ✗ RNG replay / Poisson recomputation (budgets are **measured**, not inferred)
* ✗ Mutating producer datasets or “fixing” rows
* ✗ Reinterpreting S3 order or S2 counts (**S4 fixes `K_target` only**)
* ✗ Constructing path strings by hand (paths resolved via the **Data Dictionary**)

**Run model assumptions:**

* Single-writer discipline per `(seed, parameter_hash, run_id, merchant)` partition
* File order is **non-authoritative**; **counters define** order & adjacency
* Streaming **per merchant**; constant memory (current window + last trace row)
* Validator writes are **atomic** (tmp → fsync → rename) into a **parameter-scoped** validation bundle

**Pass / Fail:**

* **PASS:** all checks hold → write `_passed.flag`
* **FAIL:** first broken rule → write `_failed.json { code, minimal context }` and stop for that merchant

---

## 2) Frozen Literals & Contract Pins

> Centralising the constants and invariants L3 will enforce so there are **no magic numbers** and **no drift** across ports. Everything below is treated as law in the checks that follow.

```text
# Label literals (apply to EVERY S4 row, events & trace)
# NOTE: Resolved from S4·L0 imports in §5 (single source of truth).
#   MODULE            ← S4_L0.MODULE
#   SUBSTREAM         ← alias of S4_L0.SUBSTREAM_LABEL
#   CONTEXT_EVENTS    ← alias of S4_L0.EVENT_CONTEXT

# (The three label pins are not re-declared here; see §5 imports and aliases.)

# Partitions (dictionary-pinned)
EVENT_PART_KEYS     = ["seed","parameter_hash","run_id"]
TRACE_PART_KEYS     = ["seed","parameter_hash","run_id"]

# Embed policy (row lineage)
EVENT_EMBED_KEYS    = ["seed","parameter_hash","run_id"]   # embed == path (byte-equal) for all 3
TRACE_EMBED_KEYS    = ["seed","run_id"]                    # parameter_hash is path-only; NO 'context' on trace

# Attempt numbering
ATTEMPT_INDEX_BASE  = 1         # Poisson payload attempt is 1-based
MAX_ZTP_ATTEMPTS    = 64        # schema-pinned cap (exhausted marker uses attempts:64)

# Family identities & payload keys (mutually exclusive)
FAMILY_ID = {
  "attempt"   : { "consuming": true,  "payload_key": "lambda"       },  # draws > "0"; counters advance
  "rejection" : { "consuming": false, "payload_key": "lambda_extra" },  # draws == "0"; before == after
  "exhausted" : { "consuming": false, "payload_key": "lambda_extra" },
  "final"     : { "consuming": false, "payload_key": "lambda_extra" }
}

# Trace duty & totals law
TRACE_AFTER_EVERY_EVENT = true   # exactly one immediate cumulative trace row per event (same writer)
TOTALS_SATURATING       = true   # totals are monotone (never decrease); u64/u128 saturating as per schema

# Ordering principle
COUNTERS_AUTHORITATIVE  = true   # counters (before/after) define order & adjacency; file order is advisory
```

**Terminal policy pins (exactly one legal outcome per merchant):**

* **Accept:** first `K ≥ 1` → one **final** with `K_target == K` from that attempt; **no** exhausted marker.
* **Cap–abort:** `attempts == 64` → one **exhausted** marker; **no** final.
* **Cap–downgrade:** `attempts == 64` → one **final** flagged exhausted (or equivalent field); **no** exhausted marker.
* **A = 0 short-circuit:** one **final** only (zero attempts & markers).

**Gate pins:**

* Presence of any S4 rows ⇒ `is_multi == true` **and** `is_eligible == true`.
* If upstream implies **A = 0**, S4 must be **final-only**.

**Budget law pins:**

* **Measured, not inferred.** `draws` is the recorded decimal u128 from the sampler; `blocks` derives from counter deltas; attempts are consuming (`draws > "0"`), markers/final are non-consuming (`draws == "0"`, `before == after`).

---

## 3) External Contracts (Schema & Dictionary anchors)

> L3 resolves **everything** via these symbolic IDs/anchors—no hand-typed paths. Partitions and lineage rules come from the **Data Dictionary**; row shapes from **JSON-Schema**.

### 3.1 Symbolic schema anchors (authoritative)

```text
SCHEMA.poisson_attempt     = "schemas.layer1.yaml#/rng/events/poisson_component"
SCHEMA.ztp_rejection       = "schemas.layer1.yaml#/rng/events/ztp_rejection"
SCHEMA.ztp_exhausted       = "schemas.layer1.yaml#/rng/events/ztp_retry_exhausted"
SCHEMA.ztp_final           = "schemas.layer1.yaml#/rng/events/ztp_final"
SCHEMA.rng_trace_log       = "schemas.layer1.yaml#/rng/core/rng_trace_log"
```

(These are the exact anchors your S4 L0 binds to, including the trace schema.) 

### 3.2 Symbolic dataset IDs (dictionary-pinned)

```text
DATASET.poisson_attempt    = "rng_event_poisson_component"
DATASET.ztp_rejection      = "rng_event_ztp_rejection"
DATASET.ztp_exhausted      = "rng_event_ztp_retry_exhausted"
DATASET.ztp_final          = "rng_event_ztp_final"
DATASET.rng_trace_log      = "rng_trace_log"

DATASET.s1_hurdle          = "rng_event_hurdle_bernoulli"          # gate check
DATASET.s3_elig_flags      = "crossborder_eligibility_flags"        # gate check (parameter-scoped)
```

(Dictionary governs IDs, partitions, and “one cumulative trace after each RNG event” guidance.)

### 3.3 Partitions & lineage (from dictionary)

```text
# All S4 logs live under these partition keys:
EVENT_PART_KEYS  = ["seed","parameter_hash","run_id"]   # attempts / rejection / exhausted / final
TRACE_PART_KEYS  = ["seed","parameter_hash","run_id"]   # rng_trace_log

# Embed policy checked by L3:
EVENT_EMBED_KEYS = ["seed","parameter_hash","run_id"]   # embed == path (byte-equal) for all three
TRACE_EMBED_KEYS = ["seed","run_id"]                    # parameter_hash is path-only; no 'context' on trace
```

(Trace path/partitions and “emit exactly one cumulative row after each RNG event append” are explicitly stated in the dictionary; L0 restates the same lineage split.)

### 3.4 Label/literal pins (from S4 contracts)

> Resolved from **S4·L0** imports in §5 (single source of truth).  
> L3 treats any deviation from those imported literals as a violation.

### 3.5 Per-family notes L3 will enforce

* **`rng_event_poisson_component`** → `SCHEMA.poisson_attempt`
  **Partitions:** `seed, parameter_hash, run_id` (embed==path).
  **Literals:** `module="1A.ztp_sampler"`, `substream_label="poisson_component"`, **`context:"ztp"` present**.
  **Identity:** **consuming** (`draws > "0"`, counters advance). 

* **`rng_event_ztp_rejection` / `rng_event_ztp_retry_exhausted` / `rng_event_ztp_final`** → `SCHEMA.ztp_*`
  **Partitions:** same as above.
  **Literals:** same; **`context:"ztp"` present**.
  **Identity:** **non-consuming** (`draws=="0"`, `before==after`). 

* **`rng_trace_log`** → `SCHEMA.rng_trace_log`
  **Partitions:** same as above.
  **Embeds:** only `{seed, run_id}`; **no `context`**.
  **Duty:** **exactly one** cumulative trace row **immediately after** each S4 event append (same writer).

* **Gates (read-only):**
  **`rng_event_hurdle_bernoulli`** (prove `is_multi==true`) and
  **`crossborder_eligibility_flags`** (prove `is_eligible==true`). 

> With these anchors and IDs centralized, every subsequent L3 check resolves paths from the **Data Dictionary** and shapes from **JSON-Schema**—keeping the validator portable and free of path literals.

---

## 4) Core Types (records used in checks)

> Fixed, language-agnostic shapes the L3 checks operate on. Names and fields mirror your S4 contracts (labels, partitions, payload keys, identities) so every checker is type-clear and portable.

```text
# -- Scalar aliases -------------------------------------------------------------
type Hex32  = string   # 32 hex chars (uppercase)   # run_id etc.
type Hex64  = string   # 64 hex chars (uppercase)   # parameter_hash
type U128S  = string   # decimal u128 as string (exact, no FP)

# -- Run & gates ----------------------------------------------------------------
type RunArgs = {
  seed: u64,
  parameter_hash: Hex64,
  run_id: Hex32
}

type GateSignals = {
  is_multi: bool,       # from S1 hurdle
  is_eligible: bool,    # from S3 eligibility
  N?: int,              # OPTIONAL: S2 nb_final total (if host exposes it)
  A?: int               # OPTIONAL: S3 admissible set size (if host exposes it)
}

# -- Counters, totals, enums ----------------------------------------------------
type Counter = { hi: u64, lo: u64 }          # 128-bit envelope counter split
type Totals  = { blocks_total: u64,
                 draws_total:  U128S,
                 events_total: u64 }         # saturating, monotone (never decrease)

enum EventFamily { "attempt", "rejection", "exhausted", "final" }

enum TerminalKind { "ACCEPT", "CAP_ABORT", "CAP_DOWNGRADE", "A0_FINAL_ONLY" }

# -- S4 event records (partitions & literals are checked, not stored here) -----
# Labels/literals are frozen: module="1A.ztp_sampler", substream="poisson_component".
# context:"ztp" is present on ALL S4 events; absent on trace.
type BaseEvent = {
  merchant_id: u64,
  before: Counter,             # envelope before
  after:  Counter,             # envelope after
  draws:  U128S,               # measured; "0" for non-consuming families
  blocks: u64,                 # after − before (derived by writer)
  module:    string,           # must equal frozen literal
  substream_label: string      # must equal frozen literal
  # NOTE: partitions are enforced externally via dictionary (seed,parameter_hash,run_id).
}

# Attempts — consuming; payload uses 'lambda' (NOT lambda_extra).
type AttemptEvent = BaseEvent & {
  family:  "attempt",
  context: "ztp",
  attempt: int,                # 1-based, contiguous
  payload: { lambda: f64, regime?: "inversion" | "ptrs", k?: int }
}

# Markers/Final — non-consuming; payload uses 'lambda_extra'.
type MarkerEvent = BaseEvent & {
  family:   "rejection" | "exhausted" | "final",
  context:  "ztp",
  payload: {
    lambda_extra: f64,
    attempts?: int,            # e.g., exhausted carries attempts:64
    regime?: "inversion" | "ptrs",
    exhausted?: bool,          # final may carry exhausted:true in downgrade
    reason?: "no_admissible"   # optional (schema-dependent) short-circuit reason
  }
}

# Discriminated union the pipeline can iterate over in counter order
type S4Event = AttemptEvent | MarkerEvent

# -- S4 trace rows (cumulative, per (module, substream)) -----------------------
# Trace rows embed ONLY {seed, run_id}; parameter_hash is path-only; NO context.
type TraceRow = {
  merchant_id: u64,
  module:      string,         # frozen literal
  substream_label: string,     # frozen literal
  totals:      Totals,         # cumulative, saturating
  seed:        u64,
  run_id:      Hex32
  # NOTE: Partitions are {seed,parameter_hash,run_id}; embed==path is enforced externally.
}

# -- Verdicts, failures, and run stats -----------------------------------------
type Failure = {
  code: string,                # stable taxonomy (e.g., E_TRACE_ADJACENCY)
  dataset: string,             # dataset id (attempt/rejection/exhausted/final/trace)
  merchant_id: u64,
  attempt?: int,               # present for attempt-sequence/adjacency issues
  context?: any,               # minimal payload for debugging (before/after, deltas, etc.)
  run: { seed: u64, parameter_hash: Hex64, run_id: Hex32 }
}

type Verdict = { ok: true,  terminal: TerminalKind }
             | { ok: false, failure: Failure }

type RunStats = {
  checked: int, passed: int, failed: int,
  terminals_by_type: { ACCEPT:int, CAP_ABORT:int, CAP_DOWNGRADE:int, A0_FINAL_ONLY:int },
  attempts_hist: map<int,int>,     # 1..64 → count
  env_errors: int
}
```

**Invariants the checkers will enforce against these types:**

* **AttemptEvent:** `draws > "0"` **and** `after != before`; payload has **`lambda`** (not `lambda_extra`).
* **MarkerEvent:** `draws == "0"` **and** `after == before`; payload has **`lambda_extra`** (not `lambda`).
* **TraceRow:** one **immediate** row per event; `totals` deltas exactly match the event’s `draws`/counter deltas; totals are **saturating**.

These definitions give every subsequent section a concrete, portable contract to program against—no ambiguity, no hidden fields.

---

## 5) Host Shims (read-only I/O; no semantics)

> Minimal, portable environment L3 expects. Shims **read** producer data and **write** validator artifacts atomically. They perform no business logic, no RNG, no path string hand-coding.

```text
# -- Errors (environment/contract) ---------------------------------------------
enum EnvError {
  "E_ENV_MISSING_DATASET",     # dataset id not found / empty for run slice
  "E_ENV_DICT_RESOLVE",        # dictionary lookup failed / invalid partitions
  "E_ENV_SCHEMA_ANCHOR",       # schema anchor not found
  "E_ENV_IO"                   # fs/read/perm error
}

# -- Dictionary & Schema resolvers (no semantics) ------------------------------
# Resolve dataset metadata; NEVER construct paths by hand in L3.
function dict_resolve(dataset_id:str) -> {
  id:str,
  partitions: [str],           # e.g., ["seed","parameter_hash","run_id"]
  path_template:str,           # dictionary-pinned template
  writer_sort?: [str],         # advisory; L3 orders by counters anyway
  schema_ref:str               # authoritative JSON-Schema anchor
} throws EnvError

# Ensure anchor exists; optional light row validator for V1 checks.
function schema_resolve(anchor:str) -> Schema throws EnvError
function SAMPLE(row:Record) -> any
    # Implementer: return a truncated projection for error context, or just the row.
    return row

# Validate one row against a resolved JSON-Schema (lightweight is fine here)
function schema_validate_row(schema:Schema, row:Record) -> bool
    # IMPLEMENTER: plug your JSON-Schema engine; return true/false only
    return JSON_SCHEMA_VALIDATE(schema, row)

# -- Dataset readers (projected, streaming) ------------------------------------
# Open S4 EVENT family iterator for a merchant. Projection keeps memory O(1).
# MUST read under dict_resolve(dataset_id).partitions (byte-equal keys).
function open_events(
  dataset_id:str,
  run:{seed:u64, parameter_hash:Hex64, run_id:Hex32},
  merchant_id:u64,
  projection:[str] = ["merchant_id","before","after","draws","blocks",
                      "module","substream_label","context","payload","attempt"]
) -> Iterator<Record> throws EnvError

# Open S4 TRACE iterator for (module, substream). L3 checks adjacency.
function open_trace(
  run:{seed:u64, parameter_hash:Hex64, run_id:Hex32},
  merchant_id:u64,
  module:str, substream:str,
  projection:[str] = ["merchant_id","module","substream_label",
                      "totals","seed","run_id"]
) -> Iterator<Record> throws EnvError

# Enumerate merchants that have ANY S4 rows for this run slice.
# Implementation may union merchants from attempts/rejection/exhausted/final.
function list_merchants_with_s4(
  run:{seed:u64, parameter_hash:Hex64, run_id:Hex32}
) -> Set<u64> throws EnvError

# -- Gate readers (S1/S3) -----------------------------------------------------
# Read gating facts for a merchant (values-only). MAY include N/A if the host provides them.
function read_gates(
  run:{seed:u64, parameter_hash:Hex64, run_id:Hex32}, merchant_id:u64
) -> GateSignals throws EnvError

# (Optional) S3 candidate set for A=0 corroboration; not required to PASS/FAIL.
function read_candidate_set_size(
  parameter_hash:Hex64, merchant_id:u64
) -> Optional<int> throws EnvError

# -- Atomic artifact writers (validator bundle) --------------------------------
# All writes are under a parameter-scoped validation bundle; never touch producer data.
function resolve_bundle_root(parameter_hash:Hex64) -> str

function atomically_write(path:str, bytes:byte[]) -> void throws EnvError
function atomically_write_json(path:str, obj:any) -> void throws EnvError
function rename(src:str, dst:str) -> void throws EnvError

# -- Concurrency helper (across merchants only) --------------------------------
# Execute fn(m) for each merchant with bounded parallelism; within a merchant, L3 stays single-threaded.
function parallel_for_merchants(
  merchants:Set<u64>, max_workers:int, fn:(u64)->void
) -> void

# -- Small utilities (no business semantics) -----------------------------------
# Parse/compare decimal u128 strings; reuse S1·L0 authoritative surfaces.
# Expectation: u128_from_dec returns an opaque BigUInt supporting comparison & subtraction.
# (Do not re-define here; import & alias for clarity/portability.)

IMPORT S4_L0: MODULE, SUBSTREAM_LABEL, EVENT_CONTEXT, MAX_ZTP_ATTEMPTS
alias SUBSTREAM       := SUBSTREAM_LABEL
alias CONTEXT_EVENTS  := EVENT_CONTEXT
# Optional guard (detects accidental drift at runtime; safe to omit)
ASSERT( MODULE == "1A.ztp_sampler" and SUBSTREAM == "poisson_component" and CONTEXT_EVENTS == "ztp" )

IMPORT S1_L0: decimal_string_to_u128
alias u128_from_dec := decimal_string_to_u128

function u128_is_zero(s:string) -> bool
    return u128_from_dec(s) == u128_from_dec("0")

function to_dec(x:BigUInt) -> U128S           # convert BigUInt → canonical decimal string (no FP)
    # IMPLEMENTER: use a pure big-int to string; locale/rounding MUST NOT alter digits
    return BIGUINT_TO_DECIMAL(x)

# Stable binary64 encoding for fingerprints (locale/rounding agnostic)
function f64_to_hexbits(x:f64) -> string
    # IMPLEMENTER: reinterpret the IEEE-754 bits of x as 64-bit unsigned
    # and return uppercase hex (16 nybbles). This is stable across ports.
    return U64_TO_HEX( REINTERPRET_F64_AS_U64(x) )

# -- Glue helpers for boolean-style checks ------------------------------------
const OK = true
global __LAST_FAILURE : Failure = null

# Record a failure and return false so callers can do:
#   CHECK(...) or return FAIL_FROM_LAST()
function FAILC(code:string, dataset:string, merchant_id:u64, run:RunArgs, context:any={}) -> bool:
    __LAST_FAILURE = { code:code, dataset:dataset, merchant_id:merchant_id, context:context, run:run }
    return false

# Convert the last recorded failure into a Verdict for early return
function FAIL_FROM_LAST() -> Verdict:
    return { ok:false, failure: __LAST_FAILURE }

# -- Non-consuming iterator helpers -------------------------------------------
function HAS_NEXT(it: Iterator[Any]) -> bool:
    r = it.peek()      # host shim must provide non-consuming peek
    return r != null

function PEEK_MERCHANT(it_events: Iterator[S4Event]) -> u64:
    r = it_events.peek()
    return (r == null) ? 0 : r.merchant_id

# -- Deterministic merge of event families by counters -------------------------
# Ordering: consuming attempts first, then non-consuming markers in fixed order:
#   attempt  < rejection < exhausted < final
function MERGE_BY_COUNTERS(iters: List[Iterator[S4Event]]) -> Iterator[S4Event]:
    heap = []  # (key, family_rank, record, source_id)
    FAMILY_RANK = { "attempt":0, "rejection":1, "exhausted":2, "final":3 }

    # prime heap with first item from each source
    for i, it in ENUMERATE(iters):
        if HAS_NEXT(it):
            r = it.next()
            key = (r.before.hi, r.before.lo, r.after.hi, r.after.lo)
            heap.push( (key, FAMILY_RANK[r.family], r, i) )
    HEAPIFY(heap)

    out = []
    while SIZE(heap) > 0:
        (key, rank, r, src) = HEAPPOP(heap)
        out.push(r)
        it = iters[src]
        if HAS_NEXT(it):
            n = it.next()
            nkey = (n.before.hi, n.before.lo, n.after.hi, n.after.lo)
            HEAPPUSH(heap, (nkey, FAMILY_RANK[n.family], n, src))
    return ITER(out)   # wrap list as iterator

# Wrap a list as a peekable iterator (used throughout this doc)
function ITER(xs: List[Any]) -> Iterator[Any]:
    i = 0
    cache = null
    return {
      next:  () -> ( cache != null ? (tmp := cache, cache := null, tmp)
                                   : (i < SIZE(xs) ? (tmp := xs[i], i := i+1, tmp) : null) ),
      peek:  () -> ( cache != null ? cache
                                   : (i < SIZE(xs) ? (cache := xs[i]) : null) )
    }
```

**Requirements & notes (for implementers):**

* All **paths** must be derived from `dict_resolve(..)` and the run’s partition keys; shims must enforce **embed == path** for events and **{seed,run_id} only** for trace rows.
* `open_events`/`open_trace` may return in arbitrary file order; L3 derives order/adjacency from **counters**.
* Readers should project only the listed fields to keep memory use low; iterators must be streaming.
* Writers must use **tmp → fsync → rename** to avoid partial artifacts.
* Any `EnvError` increments `stats.env_errors` and ultimately maps to **exit code 2**.

---

## 6) Orchestrator (run-level driver)

> Drives S4·L3 over the run slice. Safe parallelism **across merchants only**; single-threaded **within** a merchant. Produces only validator artifacts; never mutates producer datasets.

```text
# Public entrypoint
function validate_s4_run(dict:Dictionary, schemas:Schemas, run:RunArgs,
                         options:{max_workers:int}= {max_workers:8}) -> int:
    bundle_root := resolve_bundle_root(run.parameter_hash)
    stats := RunStats.zero()

    # -- Preflight: contracts exist (fail fast as ENV errors) ----------------
    REQUIRED_DATASETS := [
      DATASET.poisson_attempt,
      DATASET.ztp_rejection,
      DATASET.ztp_exhausted,
      DATASET.ztp_final,
      DATASET.rng_trace_log
    ]
    REQUIRED_SCHEMAS := [
      SCHEMA.poisson_attempt,
      SCHEMA.ztp_rejection,
      SCHEMA.ztp_exhausted,
      SCHEMA.ztp_final,
      SCHEMA.rng_trace_log
    ]

    try:
        for ds in REQUIRED_DATASETS:
            meta := dict_resolve(ds)                     # throws EnvError
            assert meta.partitions == EVENT_PART_KEYS
        for a in REQUIRED_SCHEMAS:
            _ := schema_resolve(a)                       # throws EnvError
    catch EnvError as e:
        stats.env_errors += 1
        write_summary(bundle_root, stats)
        return compute_exit_code(stats)                  # exit code 2

    # -- Discover merchants (unit of parallelism) ---------------------------
    merchants := list_merchants_with_s4(run)             # may be empty
    if SIZE(merchants) == 0:
        write_summary(bundle_root, stats)                # nothing to validate
        return compute_exit_code(stats)                  # 0

    # -- Parallel across merchants only (each merchant single-threaded) -----
    mutex stats_lock
    parallel_for_merchants(merchants, options.max_workers, fn (m:u64) -> void:
        verdict:Verdict
        try:
            verdict = validate_merchant(dict, schemas, run, m)  # Section 7
        catch EnvError as e:
            failure := {
              code: map_env_error(e), dataset: "*", merchant_id: m,
              run: { seed: run.seed, parameter_hash: run.parameter_hash, run_id: run.run_id }
            }
            atomically_write_json(bundle_root + "/" + STR(m) + "/_failed.json", failure)
            lock(stats_lock):
                stats.failed += 1
                stats.env_errors += 1
            return

        if verdict.ok:
            atomically_write(bundle_root + "/" + STR(m) + "/_passed.flag", "ok\n")
            lock(stats_lock):
                stats.passed += 1
                stats.checked += 1
                stats.terminals_by_type[verdict.terminal] += 1
        else:
            atomically_write_json(bundle_root + "/" + STR(m) + "/_failed.json", verdict.failure)
            lock(stats_lock):
                stats.failed += 1
                stats.checked += 1
                # optional: if failure carries attempt, update attempts histogram hint
                if HAS_KEY(verdict.failure, "attempt"):
                    a := verdict.failure.attempt
                    if 1 <= a <= MAX_ZTP_ATTEMPTS:
                        stats.attempts_hist[a] = stats.attempts_hist.get(a,0) + 1
    )

    # -- Run summary & exit code ---------------------------------------------
    write_summary(bundle_root, stats)                     # Section 4 helpers
    return compute_exit_code(stats)
```

**Notes for implementers**

* **Idempotence:** all writes are atomic (tmp→fsync→rename inside `atomically_write*` shims). Re-running over the same inputs regenerates identical artifacts.
* **Determinism:** merchants may run in any order; within a merchant, `validate_merchant(..)` is single-threaded to preserve event→trace adjacency checks.
* **ENV errors:** any `EnvError` (missing dataset, bad anchor, IO) increments `stats.env_errors` and yields process exit **2** (per §4). Data failures yield exit **1**; all-pass yields **0**.
* `map_env_error(e)` should return a stable code such as `E_ENV_MISSING_DATASET`, `E_ENV_DICT_RESOLVE`, `E_ENV_SCHEMA_ANCHOR`, or `E_ENV_IO` (see §5).

---

## 7) Per-Merchant Driver (single-threaded)

> Executes the full S4 check pipeline for **one** merchant; **fail-fast** on first breach; **no** producer mutations.

```text
function validate_merchant(dict:Dictionary, schemas:Schemas, run:RunArgs, m:u64) -> Verdict:
  # V0 — GATING & PRESENCE ----------------------------------------------------
  gates := read_gates(run, m)                                      # S1/S3 facts
  if not (gates.is_multi and gates.is_eligible):
      return FAIL("E_GATING_BREACH", dataset="*", merchant_id=m,
                  run=run, context={ "is_multi":gates.is_multi, "is_eligible":gates.is_eligible })

  # Open streaming iterators (values-only; dictionary-resolved partitions) ----
  it_attempts  := open_events(DATASET.poisson_attempt,   run, m)
  it_reject    := open_events(DATASET.ztp_rejection,     run, m)
  it_exhaust   := open_events(DATASET.ztp_exhausted,     run, m)
  it_final     := open_events(DATASET.ztp_final,         run, m)
  it_trace     := open_trace(run, m, MODULE, SUBSTREAM)
  # Buffer small per-merchant slices once (≤ ~130 rows typical) and reuse safely
  A := BUF_ALL(it_attempts)
  R := BUF_ALL(it_reject)
  X := BUF_ALL(it_exhaust)
  F := BUF_ALL(it_final)
  TR := BUF_ALL(it_trace)

  have_any := (SIZE(A) > 0 or SIZE(R) > 0 or SIZE(X) > 0 or SIZE(F) > 0)
  if not have_any:
      # No S4 rows for this merchant (shouldn't be scheduled by §6 discovery). Treat as pass-noop.
      return PASS(terminal="A0_FINAL_ONLY")  # or a neutral terminal, never emitted as data

  # Optional cross-state gate enforcement (will use A/N if the host supplies them)
  CHECK_GATES(gates, SIZE(A)>0, SIZE(R)>0, SIZE(X)>0, SIZE(F)>0, run) or return FAIL_FROM_LAST()

  # V1 — SCHEMA/PARTITIONS/LINEAGE (events & trace) ---------------------------
  # Resolve concrete schemas once (anchors preflighted in §6)
  sch_attempt  := schema_resolve(SCHEMA.poisson_attempt)
  sch_reject   := schema_resolve(SCHEMA.ztp_rejection)
  sch_exhaust  := schema_resolve(SCHEMA.ztp_exhausted)
  sch_final    := schema_resolve(SCHEMA.ztp_final)
  sch_trace    := schema_resolve(SCHEMA.rng_trace_log)

  CHECK_SCHEMA_PARTITIONS_LINEAGE(ITER(A),  sch_attempt, run, DATASET.poisson_attempt) or return FAIL_FROM_LAST()
  CHECK_SCHEMA_PARTITIONS_LINEAGE(ITER(R),  sch_reject,  run, DATASET.ztp_rejection)   or return FAIL_FROM_LAST()
  CHECK_SCHEMA_PARTITIONS_LINEAGE(ITER(X),  sch_exhaust, run, DATASET.ztp_exhausted)   or return FAIL_FROM_LAST()
  CHECK_SCHEMA_PARTITIONS_LINEAGE(ITER(F),  sch_final,   run, DATASET.ztp_final)       or return FAIL_FROM_LAST()
  CHECK_TRACE_SCHEMA_PARTITIONS_LINEAGE(ITER(TR), sch_trace, run)                      or return FAIL_FROM_LAST()

  # V2 — LITERALS (labels & context placement) --------------------------------
  CHECK_LITERALS(ITER(A), DATASET.poisson_attempt, run) or return FAIL_FROM_LAST()
  CHECK_LITERALS(ITER(R), DATASET.ztp_rejection,   run) or return FAIL_FROM_LAST()
  CHECK_LITERALS(ITER(X), DATASET.ztp_exhausted,   run) or return FAIL_FROM_LAST()
  CHECK_LITERALS(ITER(F), DATASET.ztp_final,       run) or return FAIL_FROM_LAST()
  CHECK_TRACE_LITERALS(ITER(TR), run)                    or return FAIL_FROM_LAST()

  # V3 — MERGE BY COUNTERS; IDENTITIES & PAYLOAD KEYS -------------------------
  # File order is non-authoritative; counters define order & adjacency.
  # Buffer once so we can iterate for identity checks and again for adjacency.
  events_buf := BUF_ALL( MERGE_BY_COUNTERS([ ITER(A), ITER(R), ITER(X), ITER(F) ]) )

  # Per-event checks (consuming vs non-consuming; payload key discipline)
  for ev in ITER(events_buf):
      if ev.family == "attempt":
          ASSERT_ATTEMPT_CONSUMES(ev)   or return FAIL_FROM_LAST()
          CHECK_PAYLOAD_KEYS(ev, run)    or return FAIL_FROM_LAST()   # requires 'lambda', not 'lambda_extra'
      else:  # rejection/exhausted/final
          ASSERT_MARKER_NONCONSUMES(ev)    or return FAIL_FROM_LAST()
          CHECK_PAYLOAD_KEYS_MARKER(ev,run) or return FAIL_FROM_LAST()  # requires 'lambda_extra', not 'lambda'

  # V4 — EVENT → TRACE ADJACENCY (one-to-one, immediate, cumulative) ----------
  CHECK_EVENT_TRACE_ADJACENCY(ITER(events_buf), ITER(TR), run) or return FAIL_FROM_LAST()

  # V5 — ATTEMPT SEQUENCE & RESUME --------------------------------------------
  # Attempts must be contiguous 1..n (n ≤ 64); if resuming, start at max+1; no re-emits.
  seq_ok, max_attempt := CHECK_ATTEMPT_SEQUENCE_AND_RESUME(ITER(A), run)
  if not seq_ok:
      return FAIL("E_ATTEMPT_SEQUENCE", dataset=DATASET.poisson_attempt, merchant_id=m,
                  run=run, context={ "max_attempt": max_attempt })

  # V6 — TERMINAL OUTCOME (exactly one legal terminal) ------------------------
  ok, term := CHECK_TERMINAL_POLICY(ITER(A), ITER(R), ITER(X), ITER(F))
  if not ok:
      return FAIL("E_TERMINAL_CARDINALITY", dataset="*", merchant_id=m, run=run, context=term)
      
  # V8 — HYGIENE (duplicates, late label drift) --------------------------------
  CHECK_HYGIENE(MERGE_BY_COUNTERS([ITER(A), ITER(R), ITER(X), ITER(F)]), ITER(TR), run)
    or return FAIL_FROM_LAST()      

  # PASS — record terminal kind (for run summary); emit _passed.flag upstream --
  return PASS(terminal=term)
```

**Why these steps match S4’s contracts (grounding):**

* **Counters define order; file order is advisory** → merge by `(before, after)` and resume from `max(attempt)+1` using persisted `{k, s_after}`; never resample prior attempts.
* **Label domain & context placement** are frozen: `module="1A.ztp_sampler"`, `substream="poisson_component"`, **`context:"ztp"` on events only; trace has none**. 
* **Consuming vs non-consuming identities** and **measured budgets** come from L0: attempts advance counters and have `draws > "0"`; markers/final do not and have `draws == "0"`. 
* **One event → one immediate cumulative trace row**, appended by the same writer; L3 only verifies adjacency and deltas. 
* **Terminal fence & legality** (accept vs cap-abort vs cap-downgrade vs A=0) are explicitly enumerated in L2’s policy/appendix, including the “stop once resolved” rule. 

> Next sections will define the called checkers (`CHECK_*`, `ASSERT_*`, `MERGE_BY_COUNTERS`) with exact failure codes and minimal contexts so this driver can be dropped into your L3 file and run in any target language.

---

## 8) V0 — Gating Preconditions (S1/S3)

> Enter/skip rules from **upstream authorities**. If any rule fails, **S4 must have written nothing** for the merchant; otherwise this is a hard failure. L2 already asserts these preflight gates; L3 verifies them against the bytes on disk. 

```text
# Inputs
#   gates := read_gates(run, m)   # {is_multi:bool, is_eligible:bool, N:int, A:int, policy:str?}
#   have_s4 := have_attempts or have_rejects or have_exhausts or have_finals

function CHECK_GATES(gates, have_attempts:bool, have_rejects:bool, have_exhausts:bool, have_finals:bool, run:RunArgs) -> bool:
    have_s4 = (have_attempts or have_rejects or have_exhausts or have_finals)
    # 1) If any S4 rows exist, S1 and S3 must both have approved the merchant
    if have_s4 and not (gates.is_multi and gates.is_eligible):
        return FAILC("E_GATING_BREACH", "*", /*merchant*/0, run,
                     { "have_s4": true, "is_multi": gates.is_multi, "is_eligible": gates.is_eligible })

    # 2) OPTIONAL scalar domain checks (only if host provided N/A)
    if have_s4 and HAS_KEY(gates,"N") and gates.N < 2:
        return FAILC("E_GATING_BREACH", "*", 0, run, { "N": gates.N })
    if have_s4 and HAS_KEY(gates,"A") and gates.A < 0:
        return FAILC("E_GATING_BREACH", "*", 0, run, { "A": gates.A })

    # 3) A==0 short-circuit rule (upstream says no admissible foreigns)
    #    If A==0, S4 must be final-only: no attempts, no rejection/exhausted markers.
    if HAS_KEY(gates,"A") and gates.A == 0:
        if have_attempts or have_rejects or have_exhausts:
            return FAILC("E_A0_PROTOCOL", "*", 0, run, { "found": "attempt/marker with A==0" })
        # Final-only specifics (shape/value) are checked later in terminal policy.

    return OK
```

**Grounding (what L3 is enforcing):**

* **Preflight gates before any sampling/emission**: `is_eligible == true` **and** `is_multi == true`; `N ≥ 2`; `A ≥ 0`; exhaustion policy governed. L2 asserts this up front; L3 verifies the presence of S4 rows is consistent with those gates. 
* **A=0 short-circuit**: when `A==0`, S4 must emit **one** finaliser and **no** attempts/markers (L2 K-1 → K-6 only). Any attempt/marker with `A==0` is a protocol breach. 
* **Gate sources**: `is_eligible` comes from **`crossborder_eligibility_flags`** (parameter-scoped); `is_multi` from S1 hurdle; L3 reads these as facts—values-only, read-only.

**Notes for implementers**

* `read_gates(..)` should supply `is_multi`, `is_eligible`, and typed scalars `N` (from S2 `nb_final`) and `A` (size of S3’s admissible set). The exact storage tables are resolved via the Data Dictionary; L3 does **not** hardcode paths.
* L3 uses **fail-fast**: on any gating breach it returns `FAIL(...)` immediately; the per-merchant driver writes `_failed.json` and stops further checks for that merchant.

---

## 9) V1 — Schema, Partitions & Lineage

> Validate row **shape** (schema), **where rows live** (partitions), and **what they embed** (lineage), before any deeper logic. No producer writes.

### What this stage enforces

* **Schema:** each family row conforms to its JSON-Schema anchor. 
* **Partitions (dictionary):** all S4 logs are under `{seed, parameter_hash, run_id}`; L3 never invents paths—it resolves via the dictionary. 
* **Lineage (embed policy):**

  * **Events:** embed **all three** keys and **embed == path** byte-for-byte.
  * **Trace:** embed **only `{seed, run_id}`** (no `parameter_hash`), still under the same partitions. 

---

### Implementation

```text
# Shared helper: check exact key presence
function _require_keys(row:Record, keys:[str]) -> bool:
    for k in keys:
        if not HAS_KEY(row, k): return false
    return true

# -- Events: schema + partitions + embed==path --------------------------------
function CHECK_SCHEMA_PARTITIONS_LINEAGE(
    it: Iterator[Record], schema: Schema, run: RunArgs, dataset_id: str
) -> bool:

    while row := it.next():
        # 1) Schema shape
        if not schema_validate_row(schema, row):
            return FAILC("E_SCHEMA", dataset_id, row.merchant_id, run,
                         {"where":"schema", "row_sample":SAMPLE(row)})

        # 2) Partition lineage keys must be embedded on events
        if not _require_keys(row, ["seed","parameter_hash","run_id"]):
            return FAILC("E_PARTITION_KEYS", dataset_id, row.merchant_id, run,
                         {"where":"embed:missing", "required":["seed","parameter_hash","run_id"]})

        # 3) Embed == path (byte-equal) for all three keys
        if row.seed != run.seed or row.parameter_hash != run.parameter_hash or row.run_id != run.run_id:
            return FAILC("E_PARTITION_KEYS", dataset_id, row.merchant_id, run,
                         {"where":"embed!=path",
                          "got":{"seed":row.seed,"parameter_hash":row.parameter_hash,"run_id":row.run_id},
                          "expected":{"seed":run.seed,"parameter_hash":run.parameter_hash,"run_id":run.run_id}}) 

    return OK

# -- Trace: schema + partitions + lineage subset (no parameter_hash) ----------
function CHECK_TRACE_SCHEMA_PARTITIONS_LINEAGE(
    it_trace: Iterator[Record], schema_trace: Schema, run: RunArgs
) -> bool:

    while tr := it_trace.next():
        # 1) Schema shape
        if not schema_validate_row(schema_trace, tr):
            return FAILC("E_SCHEMA", DATASET.rng_trace_log, tr.merchant_id, run,
                         {"where":"schema", "row_sample":SAMPLE(tr)})

        # 2) Partition keys must come from dictionary (path), not embed;
        #    Trace embeds ONLY seed & run_id; parameter_hash MUST NOT be embedded.
        if not _require_keys(tr, ["seed","run_id"]):
            return FAILC("E_PARTITION_KEYS", DATASET.rng_trace_log, tr.merchant_id, run,
                         {"where":"trace:embed:missing", "required":["seed","run_id"]})

        if HAS_KEY(tr, "parameter_hash"):
            return FAILC("E_PARTITION_KEYS", DATASET.rng_trace_log, tr.merchant_id, run,
                         {"where":"trace:embed:has_parameter_hash"})

        # 3) Embed == path for the two embedded keys
        if tr.seed != run.seed or tr.run_id != run.run_id:
            return FAILC("E_PARTITION_KEYS", DATASET.rng_trace_log, tr.merchant_id, run,
                         {"where":"trace:embed!=path",
                          "got":{"seed":tr.seed,"run_id":tr.run_id},
                          "expected":{"seed":run.seed,"run_id":run.run_id}})

    return OK
```

**Notes for implementers**

* `schema_validate_row` can be a light structural check; if you don’t have a full validator, assert required fields & types per anchor. Anchors are authoritative and pinned in §3.1. 
* Partitions and the trace embed rule (embed only `{seed, run_id}`; parameter_hash path-only) are explicitly defined in the Data Dictionary and mirrored in S4’s L0/L2 prose—L3 treats violations as hard failures. 

With V1 in place, all downstream checks operate on rows that are already **shape-correct**, **correctly partitioned**, and **lineage-sound**.

---

## 10) V2 — Label & Literal Integrity

> Verify that **every** S4 row carries the frozen label literals, and that **`context` is placed correctly** (present on events, absent on trace). Fail fast on the first mismatch.

### What this stage enforces

* `module == "1A.ztp_sampler"` (events & trace)
* `substream_label == "poisson_component"` (events & trace)
* **Events only:** `context == "ztp"` (present and exact)
* **Trace:** **no** `context` field present

---

### Implementation

```text
# Helpers
function _eq_str(a:any, b:string) -> bool:
    return (TYPEOF(a) == "string") and (a == b)

# -- Event families: literals + context placement ------------------------------
function CHECK_LITERALS(
    it: Iterator[Record], dataset_id: string, run: RunArgs
) -> bool:

    while row := it.next():
        # Labels
        if not _eq_str(row.module, MODULE) or not _eq_str(row.substream_label, SUBSTREAM):
             return FAILC("E_LABEL_LITERALS", dataset_id, row.merchant_id, run, {
                            "got": { "module": row.module, "substream_label": row.substream_label },
                            "expected": { "module": MODULE, "substream_label": SUBSTREAM }
                        })

        # Context (events must carry `ztp`)
        if not HAS_KEY(row, "context"):
            return FAILC("E_CONTEXT_PLACEMENT", dataset_id, row.merchant_id, run,
                         { "where":"event:missing", "expected":"context=ztp" })

        if not _eq_str(row.context, CONTEXT_EVENTS):
            return FAILC("E_CONTEXT_PLACEMENT", dataset_id, row.merchant_id, run,
                         { "where":"event:value", "got": row.context, "expected": CONTEXT_EVENTS })

    return OK

# -- Trace: literals + forbidden context field ---------------------------------
function CHECK_TRACE_LITERALS(
    it_trace: Iterator[Record], run: RunArgs
) -> bool:

    while tr := it_trace.next():
        # Labels
        if not _eq_str(tr.module, MODULE) or not _eq_str(tr.substream_label, SUBSTREAM):
            return FAILC("E_LABEL_LITERALS", DATASET.rng_trace_log, tr.merchant_id, run, {
                            "where":"trace",
                            "got": { "module": tr.module, "substream_label": tr.substream_label },
                            "expected": { "module": MODULE, "substream_label": SUBSTREAM }
                        })

        # Context must NOT be present on trace
        if HAS_KEY(tr, "context"):
            return FAILC("E_CONTEXT_PLACEMENT", DATASET.rng_trace_log, tr.merchant_id, run,
                         { "where":"trace:forbidden_context", "got": tr.context })

    return OK
```

**Notes for implementers**

* Equality is **strict** and **case-sensitive**. Any deviation (extra whitespace, wrong casing) is a hard failure.
* These checks run **after** V1 (schema/partitions/lineage), so rows are already shape-valid and partition-correct; here we only assert the frozen literals and `context` placement.
* Failure codes used here:

  * `E_LABEL_LITERALS` — wrong `module` and/or `substream_label`.
  * `E_CONTEXT_PLACEMENT` — missing/incorrect `context` on events, or forbidden `context` on trace.

---

## 11) V3 — Consuming vs Non-Consuming Identities

> Prove the **identity** of each family strictly from envelopes & measured budgets.
> Attempts **consume**; markers/final are **non-consuming**. No exceptions.

### Helpers (counters & dataset mapping)

```text
function COUNTERS_EQUAL(a:Counter, b:Counter) -> bool:
    return (a.hi == b.hi) and (a.lo == b.lo)

function COUNTERS_ADVANCE(a:Counter, b:Counter) -> bool:
    return (b.hi > a.hi) or ((b.hi == a.hi) and (b.lo > a.lo))

function COUNTER_DELTA_BLOCKS(a:Counter, b:Counter) -> u64:
    # assumes b >= a; validator enforces this where required
    if (b.hi < a.hi) or (b.hi == a.hi and b.lo < a.lo):
        return ERROR("__UNDERFLOW__")  # caught and turned into failure
    # Compute (b - a) in 128 bits, return as u64 (writers ensure it fits)
    lo_delta  = (b.lo - a.lo) mod 2^64
    hi_delta  = b.hi - a.hi - (b.lo < a.lo ? 1 : 0)
    # hi_delta should be small; writer guarantees blocks == (b - a) fits u64
    return (hi_delta << 64) + lo_delta

function DATASET_FOR_FAMILY(fam:str) -> string:
    if fam == "attempt":   return DATASET.poisson_attempt
    if fam == "rejection": return DATASET.ztp_rejection
    if fam == "exhausted": return DATASET.ztp_exhausted
    if fam == "final":     return DATASET.ztp_final
    return "*"
```

### Checks

```text
# Attempts — must consume counters and have measured draws > "0"
function ASSERT_ATTEMPT_CONSUMES(ev:AttemptEvent, run:RunArgs) -> bool:
    if not COUNTERS_ADVANCE(ev.before, ev.after):
        return FAILC("E_CONSUMING_ID", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                     { "family":"attempt", "where":"counters", "before":ev.before, "after":ev.after })

    # blocks must equal counter delta
    delta = COUNTER_DELTA_BLOCKS(ev.before, ev.after)
    if delta == "__UNDERFLOW__":
        return FAILC("E_CONSUMING_ID", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                     { "family":"attempt", "where":"counter-underflow",
                       "before":ev.before, "after":ev.after })

    if ev.blocks != delta:
        return FAILC("E_CONSUMING_ID", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                     { "family":"attempt", "where":"blocks!=delta",
                       "got_blocks":ev.blocks, "delta":delta })

    # draws must be a non-zero decimal u128
    if u128_is_zero(ev.draws):
        return FAILC("E_CONSUMING_ID", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                     { "family":"attempt", "where":"draws==0", "draws":ev.draws })

    return OK

# Markers/Final — must NOT consume; draws must be "0"
function ASSERT_MARKER_NONCONSUMES(ev:MarkerEvent, run:RunArgs) -> bool:
    if not COUNTERS_EQUAL(ev.before, ev.after):
        return FAILC("E_NONCONSUMING_ID", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                     { "family":ev.family, "where":"counters",
                       "before":ev.before, "after":ev.after })

    if ev.blocks != 0:
        return FAILC("E_NONCONSUMING_ID", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                     { "family":ev.family, "where":"blocks!=0", "got_blocks":ev.blocks })

    if not u128_is_zero(ev.draws):
        return FAILC("E_NONCONSUMING_ID", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                     { "family":ev.family, "where":"draws!=0", "draws":ev.draws })

    return OK
```

**Why this is sufficient (and matches S4 contracts):**

* **Attempts consume:** writers advance counters and record **measured** draws (`draws > "0"`); blocks are exactly `after − before`.
* **Markers/final don’t consume:** counters equal; `blocks == 0`; `draws == "0"`.
* These are **family identities** fixed by S4 L0 and enforced in L2’s loop; L3 verifies them byte-for-byte here before moving on to payload keys and adjacency.

---

## 12) V4 — Payload Key Discipline

> Enforce the **payload key contract** per family and basic value domains.
> Attempts carry **`lambda`** (and no `lambda_extra`); markers/final carry **`lambda_extra`** (and no `lambda`). If present, `regime` must be in `{inversion, ptrs}`.

### Helpers

```text
function is_number(x:any) -> bool:
    return TYPEOF(x) == "number"

function is_finite(x:any) -> bool:
    return is_number(x) and (x == x) and (x != +INF) and (x != -INF)

function regime_ok(r:any) -> bool:
    return TYPEOF(r) == "string" and (r == "inversion" or r == "ptrs")
```

### Checks

```text
# Attempts — payload MUST use 'lambda' (no 'lambda_extra'); lambda must be finite > 0
function CHECK_PAYLOAD_KEYS(ev:AttemptEvent, run:RunArgs) -> bool:
    ds = DATASET_FOR_FAMILY(ev.family)

    # Required / forbidden keys
    if not HAS_KEY(ev.payload, "lambda"):
        return FAILC("E_PAYLOAD_KEY", ds, ev.merchant_id, run,
                     { "family":"attempt", "where":"missing:lambda" })

    if HAS_KEY(ev.payload, "lambda_extra"):
        return FAILC("E_PAYLOAD_KEY", ds, ev.merchant_id, run,
                     { "family":"attempt", "where":"forbidden:lambda_extra" })

    # Value domain
    L = ev.payload.lambda
    if not is_finite(L) or L <= 0.0:
        return FAILC("E_PAYLOAD_VALUE", ds, ev.merchant_id, run,
                     { "family":"attempt", "where":"lambda", "got":L, "expect":"> 0, finite" })

    # Regime (optional; if present must be one of {"inversion","ptrs"})
    if HAS_KEY(ev.payload, "regime") and not regime_ok(ev.payload.regime):
        return FAILC("E_PAYLOAD_VALUE", ds, ev.merchant_id, run,
                     { "family":"attempt", "where":"regime", "got":ev.payload.regime,
                       "expect":"optional: \"inversion\"|\"ptrs\"" })

    # Attempt index presence/type checked in sequence stage; ensure it's present & >= 1 here if provided
    if HAS_KEY(ev, "attempt") and (TYPEOF(ev.attempt) != "int" or ev.attempt < ATTEMPT_INDEX_BASE):
        return FAILC("E_PAYLOAD_VALUE", ds, ev.merchant_id, run,
                     { "family":"attempt", "where":"attempt", "got":ev.attempt, "expect":"int ≥ 1" })

    return OK


# Markers & Final — payload MUST use 'lambda_extra' (no 'lambda'); lambda_extra must be finite ≥ 0
function CHECK_PAYLOAD_KEYS_MARKER(ev:MarkerEvent, run:RunArgs) -> bool:
    ds = DATASET_FOR_FAMILY(ev.family)

    # Required / forbidden keys
    if not HAS_KEY(ev.payload, "lambda_extra"):
        return FAILC("E_PAYLOAD_KEY", ds, ev.merchant_id, run,
                     { "family":ev.family, "where":"missing:lambda_extra" })

    if HAS_KEY(ev.payload, "lambda"):
        return FAILC("E_PAYLOAD_KEY", ds, ev.merchant_id, run,
                     { "family":ev.family, "where":"forbidden:lambda" })

    # Value domain
    LX = ev.payload.lambda_extra
    if not is_finite(LX) or LX < 0.0:
        return FAILC("E_PAYLOAD_VALUE", ds, ev.merchant_id, run,
                     { "family":ev.family, "where":"lambda_extra", "got":LX, "expect":"≥ 0, finite" })

    # Optional regime (if present)
    if HAS_KEY(ev.payload, "regime") and not regime_ok(ev.payload.regime):
        return FAILC("E_PAYLOAD_VALUE", ds, ev.merchant_id, run,
                     { "family":ev.family, "where":"regime", "got":ev.payload.regime,
                       "expect":"\"inversion\"|\"ptrs\"" })

    # Optional counts fields sanity (do NOT enforce policy here; terminal policy handles it)
    if HAS_KEY(ev.payload, "attempts"):
        att = ev.payload.attempts
        min_allowed = (ev.family == "final") ? 0 : ATTEMPT_INDEX_BASE
        if TYPEOF(att) != "int" or att < min_allowed or att > MAX_ZTP_ATTEMPTS:
            return FAILC("E_PAYLOAD_VALUE", ds, ev.merchant_id, run,
                         { "family":ev.family, "where":"attempts", "got":att,
                           "expect": f"int in [{min_allowed},{MAX_ZTP_ATTEMPTS}] (final allows 0 for A=0)" })

    return OK
```

### Integration in the per-event loop (from §7)

```text
for ev in evs:
    if ev.family == "attempt":
        ASSERT_ATTEMPT_CONSUMES(ev)         or return FAIL_FROM_LAST()
        CHECK_PAYLOAD_KEYS(ev, run)         or return FAIL_FROM_LAST()
    else:
        ASSERT_MARKER_NONCONSUMES(ev)       or return FAIL_FROM_LAST()
        CHECK_PAYLOAD_KEYS_MARKER(ev, run)  or return FAIL_FROM_LAST()
```

**Failure codes used here**

* `E_PAYLOAD_KEY` — required key missing or forbidden key present.
* `E_PAYLOAD_VALUE` — numeric domain/enum violation (`lambda`/`lambda_extra` not finite or out of range; bad `regime`; malformed `attempt`/`attempts` scalar).

**Why this is sufficient**

* It enforces the **mutual exclusivity** of `lambda` vs `lambda_extra` precisely where it matters.
* It checks only minimal domains here (finite, sign, basic bounds); deeper semantics (e.g., attempts ≤ 64, accept/cap rules) are handled in later stages (Sequence & Terminal Policy), keeping concerns separated and the validator fast.

---

## 13) V5 — Event → Trace Adjacency (one-to-one)

> After **every** S4 event, there must be **exactly one** immediate **cumulative** trace row for the same `(module, substream_label)`. Its totals **deltas** must equal that event’s measured budgets and counter movement; totals are **saturating** (never decrease).

### What this stage enforces

* One-to-one cardinality: **|events| == |trace rows|** (per merchant, per `(module, substream_label)`).
* For each event `eᵢ` paired with trace row `tᵢ`:

  * `Δblocks_total(tᵢ) == eᵢ.blocks`
  * `Δdraws_total(tᵢ)  == eᵢ.draws` (decimal u128)
  * `Δevents_total(tᵢ) == 1`
* Totals are **monotone**: `tᵢ.totals ≥ tᵢ₋₁.totals` component-wise (saturating u64/u128).
* Trace ordering is derived from **totals.events_total** (strictly increasing by 1); file order is non-authoritative.

---

### Helpers

```text
# Numeric helpers for u128 totals (decimal strings)
function u128_cmp(a:U128S, b:U128S) -> int:         # returns -1, 0, 1
    aa = u128_from_dec(a)
    bb = u128_from_dec(b)
    if aa < bb: return -1
    if aa > bb: return  1
    return 0

function u128_sub(a:U128S, b:U128S) -> U128S:       # assumes a >= b
    return to_dec( u128_from_dec(a) - u128_from_dec(b) )

# Order trace rows by cumulative events_total (ties broken by draws_total, then blocks_total)
function ORDER_TRACE_ROWS(tr_it: Iterator[TraceRow]) -> List[TraceRow]:
    buf = []
    while tr := tr_it.next(): buf.push(tr)
    SORT(buf, key=(tr) -> (tr.totals.events_total, u128_from_dec(tr.totals.draws_total), tr.totals.blocks_total))
    return buf
```

### Check

```text
function CHECK_EVENT_TRACE_ADJACENCY(evs: Iterator[S4Event],
                                     tr_it: Iterator[TraceRow],
                                     run: RunArgs) -> bool:
    # Buffer tiny per-merchant trace slice and order by totals.events_total
    trace_rows = ORDER_TRACE_ROWS(tr_it)

    # Quick cardinality sanity: trace cannot be empty if events exist
    if HAS_NEXT(evs) and SIZE(trace_rows) == 0:
        return FAILC("E_TRACE_ADJACENCY", DATASET.rng_trace_log,
                     PEEK_MERCHANT(evs), run,
                     { "where":"missing-trace-for-first-event" })

    # Running previous totals (start at zero vector)
    prev_blocks  = 0
    prev_draws   = "0"
    prev_events  = 0

    i = 0
    while ev := evs.next():
        if i >= SIZE(trace_rows):
            return FAILC("E_TRACE_ADJACENCY", DATASET_FOR_FAMILY(ev.family),
                         ev.merchant_id, run,
                         { "where":"missing-trace-row", "event_index": i+1,
                           "expected_after_event":"one cumulative trace row" })

        tr = trace_rows[i]

        # Monotone (saturating) totals
        if tr.totals.blocks_total < prev_blocks or
           u128_cmp(tr.totals.draws_total, prev_draws) < 0 or
           tr.totals.events_total < prev_events:
            return FAILC("E_TRACE_ADJACENCY", DATASET.rng_trace_log,
                         ev.merchant_id, run,
                         { "where":"totals-nonmonotone",
                                  "prev":{ "blocks_total":prev_blocks,
                                           "draws_total":prev_draws,
                                           "events_total":prev_events },
                                  "got": { "blocks_total":tr.totals.blocks_total,
                                           "draws_total":tr.totals.draws_total,
                                           "events_total":tr.totals.events_total } })

        # Per-event deltas must equal event budgets & counter movement
        d_blocks = tr.totals.blocks_total - prev_blocks
        d_draws  = u128_sub(tr.totals.draws_total, prev_draws)
        d_events = tr.totals.events_total - prev_events

        if d_blocks != ev.blocks:
            return FAILC("E_TRACE_ADJACENCY", DATASET_FOR_FAMILY(ev.family),
                         ev.merchant_id, run,
                         { "where":"delta-blocks!=event.blocks",
                                  "event_blocks":ev.blocks, "trace_delta_blocks":d_blocks,
                                  "event_index": i+1 })

        if u128_cmp(d_draws, ev.draws) != 0:
            return FAILC("E_TRACE_ADJACENCY", DATASET_FOR_FAMILY(ev.family),
                         ev.merchant_id, run,
                         { "where":"delta-draws!=event.draws",
                                  "event_draws":ev.draws, "trace_delta_draws":d_draws,
                                  "event_index": i+1 })

        if d_events != 1:
            return FAILC("E_TRACE_ADJACENCY", DATASET.rng_trace_log,
                         ev.merchant_id, run,
                         { "where":"delta-events!=1",
                                  "delta_events": d_events, "event_index": i+1 })

        # Advance previous totals
        prev_blocks = tr.totals.blocks_total
        prev_draws  = tr.totals.draws_total
        prev_events = tr.totals.events_total
        i += 1

    # After pairing all events, there must be NO extra trace rows
    if i < SIZE(trace_rows):
        extra = SIZE(trace_rows) - i
        return FAILC("E_TRACE_ADJACENCY", DATASET.rng_trace_log,
                     trace_rows[i].merchant_id, run,
                     { "where":"extra-trace-rows", "count": extra })

    return OK
```

**Notes for implementers**

* We **buffer per-merchant trace rows** to order by `totals.events_total` (events per merchant are small—≤ ~66); this keeps the check deterministic while keeping memory bounded.
* Adjacency is proven by **one-to-one deltas** and `events_total` **+1** per event; file order is irrelevant.
* This stage runs after V1/V2/V3/V4, so rows already passed schema/partitions/lineage, literals, identities, and payload-key discipline.

---

## 14) V6 — Attempt Sequence & Resume

> Enforce **contiguous 1..n** attempt numbering (n ≤ `MAX_ZTP_ATTEMPTS`), strict **counter continuity** between attempts, and **no re-emits** on resume. Counters—not file order—define order.

### Helpers

```text
function CMP_COUNTER(a:Counter, b:Counter) -> int:
    if a.hi < b.hi: return -1
    if a.hi > b.hi: return  1
    if a.lo < b.lo: return -1
    if a.lo > b.lo: return  1
    return 0

function ORDER_ATTEMPTS_BY_COUNTER(attempts: List[AttemptEvent]) -> List[AttemptEvent]:
    # Order by 'after' counter; attempts are consuming so 'after' strictly increases.
    SORT(attempts, key=(e) -> (e.after.hi, e.after.lo))
    return attempts
```

### Check

```text
function CHECK_ATTEMPT_SEQUENCE_AND_RESUME(it_attempts: Iterator[AttemptEvent],
                                           run:RunArgs) -> (bool, int):

    # Collect (≤ 64) — safe to buffer per merchant
    buf: List[AttemptEvent] = []
    while ev := it_attempts.next(): buf.push(ev)

    if SIZE(buf) == 0:
        return (true, 0)   # A=0 final-only is handled elsewhere

    # Basic field presence/domain (attempt is int ≥ 1)
    for ev in buf:
        if TYPEOF(ev.attempt) != "int" or ev.attempt < ATTEMPT_INDEX_BASE:
            return (false, 0)   # driver will raise E_ATTEMPT_SEQUENCE with max_attempt=0

    # Order by authoritative counters
    ordered = ORDER_ATTEMPTS_BY_COUNTER(buf)

    # 1) First attempt must be 1
    if ordered[0].attempt != 1:
        return (false, 1)

    # 2) No duplicates; contiguous 1..n; counter continuity between attempts
    seen: Set<int> = {}
    seen.add(1)

    for i in range(1, SIZE(ordered)):    # i indexes the ordered list; expected attempt == i+1
        prev = ordered[i-1]
        curr = ordered[i]
        expected = i + 1

        # Contiguous indices 1..n (no gaps/dupes)
        if curr.attempt != expected:
            return (false, expected-1)

        if expected in seen:
            return (false, expected)
        seen.add(expected)

        # Counter continuity: next.before MUST equal prev.after (non-consuming markers may occur between; they don't move counters)
        if not COUNTERS_EQUAL(curr.before, prev.after):
            return (false, curr.attempt)

        # Monotone 'after' (redundant given continuity, but catches malformed rows)
        if CMP_COUNTER(prev.after, curr.after) >= 0:
            return (false, curr.attempt)

    # 3) Cap: n ≤ MAX_ZTP_ATTEMPTS
    n = SIZE(ordered)
    if n > MAX_ZTP_ATTEMPTS:
        return (false, n)

    # Success — return max attempt for resume/summary hints
    return (true, n)
```

**Why this is sufficient (and matches S4):**

* **Contiguity & no re-emits:** enforcing indices `1..n` in **counter order** guarantees no gaps/dupes and that any resume starts at `max+1`.
* **Counter continuity:** `curr.before == prev.after` proves no intervening consumption occurred between attempts; non-consuming markers are allowed (they don’t change counters).
* **Bounded attempts:** `n ≤ 64` matches the schema-pinned cap used by the exhausted marker.

This stage isolates sequence/resume correctness so the next stage (Terminal Policy) can reason on a clean, well-ordered attempt list.

---

## 15) V7 — Terminal Outcome Correctness (Exactly One)

> Decide the **single legal terminal** per merchant and prove it from bytes-on-disk.
> Legal outcomes: **ACCEPT**, **CAP_ABORT**, **CAP_DOWNGRADE**, **A0_FINAL_ONLY**.
> Anything else (zero or multiple terminals, or illegal combo) is a hard fail.

### Helpers

```text
function BUF_ALL[T](it: Iterator[T]) -> List[T]:
    xs = []; while x := it.next(): xs.push(x); return xs

function HAS_FLAG(obj:any, key:str) -> bool:
    return HAS_KEY(obj, key) and obj[key] == true

# Extract minimal terminal facts from buffered rows
type TermFacts = {
  attempts: List[AttemptEvent],            # ordered by counter (V6 already checked contiguity)
  n_attempts: int,                         # SIZE(attempts)
  rejections: List[MarkerEvent],           # any K<2 markers (payload form is non-authoritative here)
  exhausted_markers: List[MarkerEvent],    # ztp_retry_exhausted family
  finals: List[MarkerEvent],               # ztp_final family
  final_attempts?: int,                    # finals[0].payload.attempts if present
  final_exhausted?: bool,                  # finals[0].payload.exhausted if present
  final_K_target?: int                     # finals[0].payload.K_target if present
}

function GATHER_TERMINAL_FACTS(atts_it, rej_it, ex_it, fin_it) -> TermFacts:
    A = BUF_ALL(atts_it)
    R = BUF_ALL(rej_it)
    X = BUF_ALL(ex_it)
    F = BUF_ALL(fin_it)

    # order attempts by counter 'after' (they are consuming)
    A = ORDER_ATTEMPTS_BY_COUNTER(A)

    facts = {
      attempts: A,
      n_attempts: SIZE(A),
      rejections: R,
      exhausted_markers: X,
      finals: F
    }

    if SIZE(F) > 0:
        f0 = F[0]
        if HAS_KEY(f0.payload, "attempts"):     facts.final_attempts  = f0.payload.attempts
        if HAS_KEY(f0.payload, "exhausted"):    facts.final_exhausted = (f0.payload.exhausted == true)
        if HAS_KEY(f0.payload, "K_target"):     facts.final_K_target  = f0.payload.K_target

    return facts
```

### Check

```text
function CHECK_TERMINAL_POLICY(it_attempts, it_reject, it_exhaust, it_final)
      -> (bool, any):

    tf = GATHER_TERMINAL_FACTS(it_attempts, it_reject, it_exhaust, it_final)

    nA = tf.n_attempts
    nR = SIZE(tf.rejections)
    nX = SIZE(tf.exhausted_markers)
    nF = SIZE(tf.finals)

    # ---- Cardinality sanity: cannot have more than one terminal row -----------
    # Terminals are: exhausted marker (abort) OR final (accept/downgrade/A0)
    if nX > 1 or nF > 1 or (nX == 1 and nF == 1):
        return (false, { "where":"terminal-count", "exhausted_count": nX, "final_count": nF })

    # ---- A=0 final-only -------------------------------------------------------
    if nA == 0 and nR == 0 and nX == 0 and nF == 1:
        # Optional shape hints on final: attempts==0, reason:"no_admissible" if present
        f0 = tf.finals[0]
        if HAS_KEY(f0.payload,"attempts") and f0.payload.attempts != 0:
            return (false, { "where":"A0-final:attempts!=0", "attempts": f0.payload.attempts })
        if HAS_KEY(f0.payload,"exhausted") and f0.payload.exhausted == true:
            return (false, { "where":"A0-final:exhausted-flag" })
        return (true, "A0_FINAL_ONLY")

    # If we have no terminal at all (and some events), that's invalid
    if (nA > 0 or nR > 0) and (nX == 0 and nF == 0):
        return (false, { "where":"no-terminal", "n_attempts": nA, "n_rejections": nR })

    # ---- Cap Abort: attempts == MAX, one exhausted, no final ------------------
    if nA == MAX_ZTP_ATTEMPTS and nX == 1 and nF == 0:
        x = tf.exhausted_markers[0]
        # If present, payload.attempts must equal cap
        if HAS_KEY(x.payload,"attempts") and x.payload.attempts != MAX_ZTP_ATTEMPTS:
            return (false, { "where":"exhausted:attempts!=cap", "got":x.payload.attempts, "cap":MAX_ZTP_ATTEMPTS })
        # If present, aborted flag should be true (treat missing as acceptable)
        if HAS_KEY(x.payload,"aborted") and x.payload.aborted != true:
            return (false, { "where":"exhausted:aborted!=true" })
        return (true, "CAP_ABORT")

    # ---- Cap Downgrade: attempts == MAX, one final (flagged exhausted), no exhausted marker
    if nA == MAX_ZTP_ATTEMPTS and nF == 1 and nX == 0:
        f0 = tf.finals[0]
        # If present, final.attempts must equal cap
        if HAS_KEY(f0.payload,"attempts") and f0.payload.attempts != MAX_ZTP_ATTEMPTS:
            return (false, { "where":"final:attempts!=cap", "got":f0.payload.attempts, "cap":MAX_ZTP_ATTEMPTS })
        # Must be flagged exhausted if field exists; absence is tolerated per schema-version
        if HAS_KEY(f0.payload,"exhausted") and f0.payload.exhausted != true:
            return (false, { "where":"final:exhausted-flag-missing-or-false" })
        return (true, "CAP_DOWNGRADE")

    # ---- Accept: n_attempts >= 1, exactly one final, no exhausted ------------
    if nA >= 1 and nF == 1 and nX == 0:
        f0 = tf.finals[0]

        # If present, final.attempts must equal number of attempts performed
        if HAS_KEY(f0.payload,"attempts") and f0.payload.attempts != nA:
            return (false, { "where":"final:attempts!=n_attempts",
                             "final_attempts":f0.payload.attempts, "n_attempts":nA })

        # If present, final must NOT be marked exhausted
        if HAS_KEY(f0.payload,"exhausted") and f0.payload.exhausted == true:
            return (false, { "where":"final:unexpected-exhausted-flag" })

        # Optional mapping check: if attempts carry 'k', ensure final.K_target == k of the last attempt
        lastA = tf.attempts[nA-1]
        if HAS_KEY(lastA.payload, "k") and HAS_KEY(f0.payload, "K_target"):
            if TYPEOF(lastA.payload.k) != "int" or lastA.payload.k < 1:
                return (false, { "where":"attempt.k:domain", "k": lastA.payload.k })
            if f0.payload.K_target != lastA.payload.k:
                return (false, { "where":"K_target!=k(accepting_attempt)",
                                 "K_target": f0.payload.K_target, "k": lastA.payload.k })

        return (true, "ACCEPT")

    # ---- Otherwise: illegal combination --------------------------------------
    return (false, { "where":"illegal-combination",
                     "n_attempts": nA, "n_rejections": nR, "n_exhausted": nX, "n_final": nF })
```

**Notes for implementers**

* The policy treats **final presence** as the terminal for **ACCEPT**, **CAP_DOWNGRADE**, and **A0_FINAL_ONLY**; **EXHAUSTED** (abort) is terminal when present **without** a final.
* We tolerate schema-version optional fields (`attempts`, `exhausted`, `reason`) as **hints**: when present they must agree with the outcome; when absent, we decide from counts and caps.
* The optional **`K_target` ↔ `k`** equality check is enforced **only if both fields exist**, keeping the validator compatible with earlier payload shapes while still catching mismatches where available.

---

## 16) V8 — Hygiene (single-writer, duplicates, clashes)

> Catch “boring but deadly” integrity slips that don’t belong to earlier stages:
> duplicate rows, duplicate trace steps, and any residual clashes that suggest multiple writers or accidental re-emits.

### What this stage enforces

* **No duplicate S4 events** (same merchant, same envelope counters, same family, same payload key).
* **No duplicate trace rows** (same merchant, same `(module,substream_label)`, same totals triplet).
* **No off-contract family tags** or label drift (belt-and-braces recheck).
* Produces **clear, minimal** failures; otherwise passes silently.

---

### Helpers

```text
# Stable fingerprints to detect duplicates without storing full rows
function FPRINT_EVENT(ev:S4Event) -> string:
    # family|m|before.hi:lo|after.hi:lo|key|val
    if ev.family == "attempt":
        return CONCAT("A|", ev.merchant_id, "|",
                      ev.before.hi, ":", ev.before.lo, "|",
                      ev.after.hi,  ":", ev.after.lo,  "|LHEX|",
                      f64_to_hexbits(ev.payload.lambda))
    else:
        # markers/final fingerprint by non-consuming anchor + lambda_extra
        return CONCAT("M:", ev.family, "|", ev.merchant_id, "|",
                      ev.before.hi, ":", ev.before.lo, "|",
                      ev.after.hi,  ":", ev.after.lo,  "|LXHEX|",
                      f64_to_hexbits(ev.payload.lambda_extra))

function FPRINT_TRACE(tr:TraceRow) -> string:
    # module|substream|m|blocks_total|draws_total|events_total
    return CONCAT(tr.module, "|", tr.substream_label, "|", tr.merchant_id, "|",
                  tr.totals.blocks_total, "|", tr.totals.draws_total, "|", tr.totals.events_total)

function IN_ALLOWED_FAMILY(tag:string) -> bool:
    return (tag == "attempt" or tag == "rejection" or tag == "exhausted" or tag == "final")
```

### Check

```text
function CHECK_HYGIENE(evs: Iterator[S4Event], tr_it: Iterator[TraceRow], run:RunArgs) -> bool:

    seen_events : Set[string] = {}
    seen_trace  : Set[string] = {}

    # 1) Events: duplicates & residual family/label drift
    while ev := evs.next():
        # Family sanity (should already be enforced upstream)
        if not IN_ALLOWED_FAMILY(ev.family):
            return FAILC("E_HYGIENE", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                         { "where":"unknown-family", "family": ev.family })

        # Labels belt-and-braces (V2 already checked; keep a fast assert here)
        if ev.module != MODULE or ev.substream_label != SUBSTREAM:
            return FAILC("E_HYGIENE", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                         { "where":"label-drift",
                           "got":{ "module":ev.module, "substream_label":ev.substream_label },
                           "expected":{ "module":MODULE, "substream_label":SUBSTREAM } })

        # Duplicate detection
        fp = FPRINT_EVENT(ev)
        if fp in seen_events:
            return FAILC("E_HYGIENE", DATASET_FOR_FAMILY(ev.family), ev.merchant_id, run,
                         { "where":"duplicate-event", "fingerprint": fp })
        seen_events.add(fp)

    # 2) Trace: duplicates at the cumulative-totals level
    while tr := tr_it.next():
        if tr.module != MODULE or tr.substream_label != SUBSTREAM:
            return FAILC("E_HYGIENE", DATASET.rng_trace_log, tr.merchant_id, run,
                         { "where":"trace-label-drift",
                           "got":{ "module":tr.module, "substream_label":tr.substream_label },
                           "expected":{ "module":MODULE, "substream_label":SUBSTREAM } })

        tfp = FPRINT_TRACE(tr)
        if tfp in seen_trace:
            return FAILC("E_HYGIENE", DATASET.rng_trace_log, tr.merchant_id, run,
                         { "where":"duplicate-trace-row", "fingerprint": tfp })
        seen_trace.add(tfp)

    return OK
```

### Why this adds value (and doesn’t fight earlier stages)

* **Duplicates** won’t always be caught by sequence/adjacency alone (e.g., a repeated rejection marker with identical non-consuming counters). Fingerprints make that impossible to miss.
* **Label drift** here is a **cheap re-assertion** to catch edge cases where V2 ran on one iterator and a later buffer brings in a stray row.
* The checks are **purely defensive**; they keep memory constant (sets are per-merchant and small) and don’t duplicate heavier logic from V1–V7.

---

## 17) Artifact Writers & Exit Logic

> Emit **exactly one** verdict per merchant, atomically; never touch producer datasets. Deterministic re-runs over the same inputs reproduce identical artifacts.

```text
# -- Paths & constants ---------------------------------------------------------
const PASSED_FILE = "_passed.flag"
const FAILED_FILE = "_failed.json"
const SUMMARY_FILE = "_summary.json"

function merchant_dir(bundle_root:str, m:u64) -> str:
    return bundle_root + "/" + STR(m)

function tmp_path(path:str) -> str:
    return path + ".tmp"

# -- Verdict emitters (first-error wins per merchant) -------------------------
# Writes a tiny flag; content is informational only.
function emit_pass_flag(bundle_root:str, m:u64) -> void:
    dir = merchant_dir(bundle_root, m)
    path = dir + "/" + PASSED_FILE
    atomically_write(tmp_path(path), "ok\n")
    rename(tmp_path(path), path)

# Writes the first failure with minimal, stable context.
# failure := {
#   code:str, dataset:str, merchant_id:u64, attempt?:int,
#   context?:any, run:{seed:u64, parameter_hash:Hex64, run_id:Hex32}
# }
function emit_fail_json(bundle_root:str, m:u64, failure:Failure) -> void:
    dir = merchant_dir(bundle_root, m)
    path = dir + "/" + FAILED_FILE
    atomically_write_json(tmp_path(path), failure)
    rename(tmp_path(path), path)

# -- Run summary (optional, recommended) ---------------------------------------
# stats := { checked:int, passed:int, failed:int, env_errors:int,
#            terminals_by_type:{...}, attempts_hist:map<int,int> }
function write_summary(bundle_root:str, stats:RunStats) -> void:
    out = {
      "merchants_checked": stats.checked,
      "merchants_passed":  stats.passed,
      "merchants_failed":  stats.failed,
      "env_errors":        stats.env_errors,
      "terminals":         stats.terminals_by_type,
      "attempts_histogram": stats.attempts_hist
    }
    path = bundle_root + "/" + SUMMARY_FILE
    atomically_write_json(tmp_path(path), out)
    rename(tmp_path(path), path)

# -- Exit logic (process return code) ------------------------------------------
# 0 = PASS (no _failed.json), 1 = DATA FAIL (≥1 _failed.json), 2 = ENV/CONTRACT FAIL (anchor/IO/missing dataset)
function compute_exit_code(stats:RunStats) -> int:
    if stats.env_errors > 0: return 2
    if stats.failed > 0:     return 1
    return 0

# -- Map environment errors to stable failure codes (for _failed.json) --------
function map_env_error(e:EnvError) -> string:
    if e == "E_ENV_MISSING_DATASET": return "E_ENV_MISSING_DATASET"
    if e == "E_ENV_DICT_RESOLVE":    return "E_ENV_DICT_RESOLVE"
    if e == "E_ENV_SCHEMA_ANCHOR":   return "E_ENV_SCHEMA_ANCHOR"
    if e == "E_ENV_IO":              return "E_ENV_IO"
    return "E_ENV_UNKNOWN"
```

**Operational notes (determinism & hygiene)**

* **Atomicity:** `atomically_write*` must implement **tmp → fsync → rename** so no partial artifacts appear.
* **Idempotence:** running L3 again over *identical inputs* rewrites the same bytes; outputs are stable.
* **One verdict per merchant:** orchestrator calls **either** `emit_pass_flag` **or** `emit_fail_json`—never both. (If a previous run left conflicting files, treat the bundle as dirty and rerun into a clean bundle root.)
* **No mutations to producer data:** these writers operate **only** under the parameter-scoped validation bundle (`resolve_bundle_root(parameter_hash)`).

---

## 18) Failure Taxonomy (stable codes)

> A **small, stable** set of error codes. Each code includes the **minimal context** L3 must emit in `_failed.json`. These codes map 1:1 to earlier validator stages, so downstream automation can react deterministically.

### 18.1 Canonical codes

```text
# -- ENV/CONTRACT errors (process exit = 2) ------------------------------------
E_ENV_MISSING_DATASET   # required dataset absent/empty for run slice
E_ENV_DICT_RESOLVE      # dictionary lookup/metadata invalid
E_ENV_SCHEMA_ANCHOR     # schema anchor missing/invalid
E_ENV_IO                # filesystem/permission/read error
E_ENV_UNKNOWN           # catch-all (should be rare)

# -- DATA errors (process exit = 1) — mapped to validator stages --------------
# V0 — Gating
E_GATING_BREACH         # S4 rows exist but S1/S3 gates do not approve (or N/A out of domain)
E_A0_PROTOCOL           # A==0 upstream but S4 wrote attempts/markers (final-only rule broken)

# V1 — Schema / Partitions / Lineage
E_SCHEMA                # row not conforming to JSON-Schema anchor
E_PARTITION_KEYS        # embed!=path (events), illegal embed on trace, or missing keys

# V2 — Labels & context
E_LABEL_LITERALS        # wrong module/substream_label
E_CONTEXT_PLACEMENT     # missing/incorrect context on event OR context present on trace

# V3 — Family identities
E_CONSUMING_ID          # attempt didn’t advance counters or had draws=="0" or blocks!=delta
E_NONCONSUMING_ID       # marker/final advanced counters or had draws!="0" or blocks!=0

# V4 — Payload keys/values
E_PAYLOAD_KEY           # required key missing or forbidden key present (lambda vs lambda_extra)
E_PAYLOAD_VALUE         # numeric/enum domain violation (lambda/lambda_extra/regime/attempt(s))

# V5 — Event → Trace adjacency
E_TRACE_ADJACENCY       # missing/extra trace row; non-monotone totals; delta mismatch for blocks/draws/events

# V6 — Sequence & resume
E_ATTEMPT_SEQUENCE      # first!=1; non-contiguous; duplicate attempt; counter gap; cap exceeded

# V7 — Terminal policy
E_TERMINAL_CARDINALITY  # zero or multiple terminals; illegal combinations; bad cap flags
E_ACCEPT_MAPPING        # (optional) K_target in final != k of accepting attempt (when both present)

# V8 — Hygiene
E_HYGIENE               # duplicate event or trace row; unknown family tag; late label drift
```

---

### 18.2 Minimal contexts to include in `_failed.json`

All failures **must** include:

```json
{
  "code": "<one of the above>",
  "dataset": "<dataset id or '*'>",
  "merchant_id": <u64>,
  "run": { "seed": <u64>, "parameter_hash": "<Hex64>", "run_id": "<Hex32>" }
}
```

…and the **extra fields** below per code:

| Code                     | Add these minimal fields                                                                                                                                                                                                                                                               |
|--------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `E_GATING_BREACH`        | `{"have_s4":bool,"is_multi":bool,"is_eligible":bool}` (optionally `"N":int,"A":int`)                                                                                                                                                                                                   |
| `E_A0_PROTOCOL`          | `{"found":"attempt \| rejection \| exhausted"}`                                                                                                                                                                                                                                        |
| `E_SCHEMA`               | `{"where":"schema","row_sample":{...}}` *(truncate as needed)*                                                                                                                                                                                                                         |
| `E_PARTITION_KEYS`       | `{"where":"embed:missing \| embed!=path \| trace:embed:has_parameter_hash \| trace:embed:missing","got":{...},"expected":{...}}`                                                                                                                                                       |
| `E_LABEL_LITERALS`       | `{"got":{"module":str,"substream_label":str},"expected":{"module":MODULE,"substream_label":SUBSTREAM}}`                                                                                                                                                                                |
| `E_CONTEXT_PLACEMENT`    | `{"where":"event:missing \| event:value \| trace:forbidden_context","got":<value or null>,"expected":"ztp or none"}`                                                                                                                                                                   |
| `E_CONSUMING_ID`         | `{"family":"attempt","where":"counters \| blocks!=delta \| draws==0","before":Counter,"after":Counter,"got_blocks":u64,"delta":u64,"draws":U128S}`                                                                                                                                     |
| `E_NONCONSUMING_ID`      | `{"family":"rejection \| exhausted \| final","where":"counters \| blocks!=0 \| draws!=0","before":Counter,"after":Counter,"got_blocks":u64,"draws":U128S}`                                                                                                                             |
| `E_PAYLOAD_KEY`          | `{"family":"attempt \| rejection \| exhausted \| final","where":"missing:<k> \| forbidden:<k>"}`                                                                                                                                                                                       |
| `E_PAYLOAD_VALUE`        | `{"family":"attempt \| rejection \| exhausted \| final","where":"lambda \| lambda_extra \| regime \| attempt \| attempts","got":<val>,"expect":<desc>}`                                                                                                                                |
| `E_TRACE_ADJACENCY`      | `{"where":"missing-trace-row \| extra-trace-rows \| totals-nonmonotone \| delta-blocks!=event.blocks\| delta-draws!=event.draws \| delta-events!=1","event_index":int,"prev_totals":{...},"got_totals":{...}}`                                                                         |
| `E_ATTEMPT_SEQUENCE`     | `{"where":"first!=1 \| contiguity \| duplicate \| counter-gap \| after-nonmonotone \| cap-exceeded \| attempt:domain","expected":<int or desc>,"got":<int or desc>,"max_attempt":int}`                                                                                                 |
| `E_TERMINAL_CARDINALITY` | `{"where":"terminal-count \| no-terminal \| A0-final:attempts!=0 \| final:attempts!=cap \| final:unexpected-exhausted-flag \| exhausted:attempts!=cap \| exhausted:aborted!=true \| illegal-combination","exhausted_count":int,"final_count":int,"n_attempts":int,"n_rejections":int}` |
| `E_ACCEPT_MAPPING`       | `{"where":"K_target!=k(accepting_attempt)","K_target":int,"k":int}`                                                                                                                                                                                                                    |
| `E_HYGIENE`              | `{"where":"duplicate-event \| duplicate-trace-row \| unknown-family \| label-drift \| trace-label-drift","fingerprint":str}`                                                                                                                                                           |
| `E_ENV_*`                | `{"detail": "<resolver/anchor/path/IO message>"} `                                                                                                                                                                                                                                     |

---

### 18.3 Enum + builder (to keep outputs consistent)

```text
enum FailureCode {
  "E_ENV_MISSING_DATASET","E_ENV_DICT_RESOLVE","E_ENV_SCHEMA_ANCHOR","E_ENV_IO","E_ENV_UNKNOWN",
  "E_GATING_BREACH","E_A0_PROTOCOL",
  "E_SCHEMA","E_PARTITION_KEYS",
  "E_LABEL_LITERALS","E_CONTEXT_PLACEMENT",
  "E_CONSUMING_ID","E_NONCONSUMING_ID",
  "E_PAYLOAD_KEY","E_PAYLOAD_VALUE",
  "E_TRACE_ADJACENCY",
  "E_ATTEMPT_SEQUENCE",
  "E_TERMINAL_CARDINALITY","E_ACCEPT_MAPPING",
  "E_HYGIENE"
}

function FAIL(code:FailureCode, dataset:string, merchant_id:u64, run:RunArgs, context:any={}) -> Verdict:
    return { ok:false, failure:{ code:code, dataset:dataset, merchant_id:merchant_id, context:context, run:run } }

function PASS(terminal:TerminalKind) -> Verdict:
    return { ok:true, terminal: terminal }
```

---

### 18.4 Mapping back to validator stages

| Stage   | Check                         | Codes                                        |
|---------|-------------------------------|----------------------------------------------|
| **V0**  | Gates (S1/S3), A=0 final-only | `E_GATING_BREACH`, `E_A0_PROTOCOL`           |
| **V1**  | Schema, partitions, lineage   | `E_SCHEMA`, `E_PARTITION_KEYS`               |
| **V2**  | Labels & context              | `E_LABEL_LITERALS`, `E_CONTEXT_PLACEMENT`    |
| **V3**  | Consuming / non-consuming     | `E_CONSUMING_ID`, `E_NONCONSUMING_ID`        |
| **V4**  | Payload keys/values           | `E_PAYLOAD_KEY`, `E_PAYLOAD_VALUE`           |
| **V5**  | Event→trace adjacency         | `E_TRACE_ADJACENCY`                          |
| **V6**  | Attempt sequence & resume     | `E_ATTEMPT_SEQUENCE`                         |
| **V7**  | Terminal policy               | `E_TERMINAL_CARDINALITY`, `E_ACCEPT_MAPPING` |
| **V8**  | Hygiene                       | `E_HYGIENE`                                  |
| **ENV** | Dictionary/schema/IO          | `E_ENV_*` (exit code = 2)                    |

> With this taxonomy fixed, every failure your validator emits is compact, machine-parseable, and traceable to the exact rule that tripped—ideal for CI and quick operator triage.

---

## 19) Performance & Observability

> Make the validator **fast, deterministic, low-memory**, and **easy to operate**.
> Knobs are explicit; metrics are minimal but sufficient for CI/ops.

### 19.1 Complexity & memory bounds (per merchant)

```text
TIME:   O(E + T)     # E = number of S4 events; T = number of trace rows (E == T by design)
SPACE:  O(E_merchant)  with E_merchant ≤ ~ (64 attempts + markers + final) ≲ 130 rows typical
```

* **Trace buffering:** order per-merchant trace by `events_total`; buffer size ≤ `T_merchant` (small).
* **Attempts buffering:** ≤ `MAX_ZTP_ATTEMPTS` (=64). Markers/final small.

### 19.2 Runtime knobs (determinism-safe)

```text
type Options = {
  max_workers:int = 8,             # parallelism ACROSS merchants only
  read_batch:int = 512,            # iterator fetch size (projection already minimal)
  fsync_every:int = 1,             # artifact atomic writes (1 == fsync each write)
  fail_fast:bool = true,           # stop at first failure per merchant
  schema_strict:bool = true,       # strict JSON-Schema vs. shape-only
  debug_dump_on_fail:int = 0       # if >0, dump N rows around failing point (see 19.5)
}
```

### 19.3 Minimal hot-path allocations

* **Projection** in `open_events/open_trace` to required fields only.
* **Reuse** small structs for u128 parsing/comparison.
* **No string concat loops** on the hot path; preformat fingerprints once.

### 19.4 Metrics (exposed via `RunStats` + counters)

```text
type Metrics = {
  merchants_checked:int,
  merchants_passed:int,
  merchants_failed:int,
  env_errors:int,
  events_processed:long,
  trace_rows_processed:long,
  terminals:{ ACCEPT:int, CAP_ABORT:int, CAP_DOWNGRADE:int, A0_FINAL_ONLY:int },
  attempts_hist: map<int,int>,             # 1..64
  failures_by_code: map<string,int>,       # E_* tallies
  latency_ms_p50:int, latency_ms_p95:int,  # per-merchant validation time (optional)
}
```

Increment **on the hot path**:

* After each event row → `events_processed++`.
* After each trace row → `trace_rows_processed++`.
* On verdict → `merchants_passed/failed++`, `terminals[kind]++`.
* On failure → `failures_by_code[code]++`; if attempt present, `attempts_hist[a]++`.

Emit via `_summary.json` (§17) or your metrics sink (out-of-scope).

### 19.5 Optional debug sampling (bounded I/O)

```text
# If Options.debug_dump_on_fail > 0, write a small contextual dump next to _failed.json
function maybe_dump_context(bundle_root:str, merchant:u64,
                            around: {events: List[S4Event], traces: List[TraceRow]},
                            N:int) -> void:
    if N <= 0: return
    ctx = {
      "events_head":  TAKE(around.events, N),
      "trace_head":   TAKE(around.traces, N)
    }
    atomically_write_json( merchant_dir(bundle_root, merchant) + "/_debug_sample.json", ctx )
```

Call this **only** on failure, with tiny `N` (e.g., 5). Never dump entire partitions.

### 19.6 File-system hygiene

* **Atomic writes only:** tmp → fsync → rename (already in §17 shims).
* **Descriptor reuse:** keep dataset readers open per merchant; close promptly to avoid FD pressure.
* **No writes to producer datasets.**

### 19.7 Determinism & reproducibility

* **Order source:** counters, not file order.
* **No randomization:** sorting keys are fixed; ties broken deterministically (`events_total`, `draws_total`, `blocks_total`).
* **Re-run identical inputs ⇒ identical outputs.**

### 19.8 Back-pressure & large slices

* If a merchant exceeds expected bounds (e.g., >64 attempts due to producer bug), V6 fires `E_ATTEMPT_SEQUENCE` early; validator **does not** attempt to continue.
* Use `max_workers` to match IO bandwidth; increase `read_batch` if listing small files is the bottleneck.

### 19.9 Observability quick-checks (for dashboards)

* **Pass rate:** `merchants_passed / merchants_checked`.
* **Terminal mix:** `terminals{…}` — track cap pressure and A=0 incidence.
* **Top failure codes:** `failures_by_code` — should be sparse; spikes indicate regressions.
* **Latency percentiles:** p50/p95 per merchant to watch for IO hotspots.

---

**Outcome:** With these constraints and counters, L3 stays **streaming, low-memory, deterministic**, and **ops-friendly**, mirroring the production characteristics of your S4 L0/L1/L2 while producing just the small artifacts CI needs.

---

## 20) Validator KATs (CI Checklist)

> A compact, **executable** checklist of Known-Answer Tests that map 1:1 to L3’s stages (V0…V8).
> Each KAT gives the **minimal setup** (rows you feed to the validator) and the **expected verdict/code**.
> Use lightweight row builders in your test harness (e.g., `att(..)`, `rej(..)`, `exh(..)`, `fin(..)`, `tr(..)`) that emit records shaped like §4 Core Types.

**Notation (helpers you provide in tests):**

* `att(t, before, after, draws, blocks, λ, regime)` → AttemptEvent (family=`"attempt"`, payload `{lambda:λ, regime}`, `attempt=t`).
* `rej(t, before, λx)` / `exh(cap, before, λx, aborted=true)` / `fin(attempts, λx, Kt?, exhausted?)` → MarkerEvent with **non-consuming** counters (`after==before`) and payload `{lambda_extra:λx, …}`.
* `tr(prevTotals → totals)` → TraceRow cumulative step.
* All event rows carry `module=MODULE`, `substream_label=SUBSTREAM`, `context="ztp"`; trace rows never carry `context`. Partitions for all logs are `{seed, parameter_hash, run_id}`; events embed all three; trace embeds `{seed, run_id}` only.

---

### ✅ PASS cases (golden paths)

**KAT-P1 (ACCEPT):**
Setup: `att(1,…, K=0)`, `tr(Δblocks,Δdraws,Δevents=1)`; `att(2,…, K≥1)`, `tr(..)`; `fin(attempts=2, λx, Kt=K_of_att2)`; matching trace after final.
Expect: **PASS**, terminal=`ACCEPT`.

**KAT-P2 (CAP_ABORT):**  One-to-one cardinality: **|events| == |trace rows|** (per merchant, per `(module, substream_label)`).
Setup: 64 attempts with `K<2`, each paired with trace; `exh(cap=64, aborted=true)` (no final); trace after marker.
Expect: **PASS**, terminal=`CAP_ABORT`.

**KAT-P3 (CAP_DOWNGRADE):**
Setup: 64 attempts with `K<2`; `fin(attempts=64, exhausted=true)` (no exhausted marker); trace after final.
Expect: **PASS**, terminal=`CAP_DOWNGRADE`.

**KAT-P4 (A0_FINAL_ONLY):**
Setup: **no** attempts/markers; single `fin(attempts=0, reason="no_admissible")`; trace after final.
Gates: `is_multi=true`, `is_eligible=true`, *(optional)* A=0 corroboration.
Expect: **PASS**, terminal=`A0_FINAL_ONLY`.

---

### V0 — Gates

**KAT-G1:** S4 rows exist but `is_multi=false` → **`E_GATING_BREACH`**.
**KAT-G2:** S4 rows exist but `is_eligible=false` → **`E_GATING_BREACH`**.
**KAT-G3:** A=0 upstream, yet an `att(..)` or `rej(..)` exists → **`E_A0_PROTOCOL`**.

---

### V1 — Schema / Partitions / Lineage

**KAT-S1:** Event missing an embedded partition key (e.g., no `run_id`) → **`E_PARTITION_KEYS`**.
**KAT-S2:** Event embeds `{seed,parameter_hash,run_id}` that **don’t equal** the path keys → **`E_PARTITION_KEYS`**.
**KAT-S3:** Trace row **embeds `parameter_hash`** → **`E_PARTITION_KEYS`**.
**KAT-S4:** Malformed row vs schema (e.g., wrong type for `attempt`) → **`E_SCHEMA`**.

---

### V2 — Labels & Context

**KAT-L1:** Event with `module!="1A.ztp_sampler"` or `substream_label!="poisson_component"` → **`E_LABEL_LITERALS`**.
**KAT-L2:** Event missing `context` or `context!="ztp"` → **`E_CONTEXT_PLACEMENT`**.
**KAT-L3:** Trace row contains a `context` field → **`E_CONTEXT_PLACEMENT`**.

---

### V3 — Family Identities (consuming vs non-consuming)

**KAT-I1:** Attempt with `after==before` or `draws=="0"` or `blocks!=after−before` → **`E_CONSUMING_ID`**.
**KAT-I2:** Marker/final with `after>before` or `draws!="0"` or `blocks!=0` → **`E_NONCONSUMING_ID`**.

---

### V4 — Payload Keys & Values

**KAT-K1:** Attempt **lacks `lambda`** or **has `lambda_extra`** → **`E_PAYLOAD_KEY`**.
**KAT-K2:** Marker/final **lacks `lambda_extra`** or **has `lambda`** → **`E_PAYLOAD_KEY`**.
**KAT-K3:** `lambda<=0` or non-finite on attempt; `lambda_extra<0` or non-finite on markers/final → **`E_PAYLOAD_VALUE`**.
**KAT-K4:** `regime` not in `{inversion, ptrs}` when present → **`E_PAYLOAD_VALUE`**.

---

### V5 — Event → Trace Adjacency

**KAT-T1:** Missing trace row after an event → **`E_TRACE_ADJACENCY`** (`where:"missing-trace-row"`).
**KAT-T2:** Trace totals deltas don’t equal event budgets (blocks/draws/events) → **`E_TRACE_ADJACENCY`** (`where:"delta-*"`).
**KAT-T3:** Extra trace rows beyond number of events → **`E_TRACE_ADJACENCY`** (`where:"extra-trace-rows"`).
**KAT-T4:** Non-monotone totals (totals decrease) → **`E_TRACE_ADJACENCY`** (`where:"totals-nonmonotone"`).

---

### V6 — Attempt Sequence & Resume

**KAT-Q1:** First attempt index ≠ 1 → **`E_ATTEMPT_SEQUENCE`** (`where:"first!=1"`).
**KAT-Q2:** Gap (e.g., attempts 1,2,4) → **`E_ATTEMPT_SEQUENCE`** (`where:"contiguity"`).
**KAT-Q3:** Duplicate index (e.g., 1,2,2,3) → **`E_ATTEMPT_SEQUENCE`** (`where:"duplicate"`).
**KAT-Q4:** Counter gap (`next.before != prev.after`) → **`E_ATTEMPT_SEQUENCE`** (`where:"counter-gap"`).
**KAT-Q5:** More than 64 attempts → **`E_ATTEMPT_SEQUENCE`** (`where:"cap-exceeded"`).
**KAT-Q6 (Resume):** Attempts 1..k exist; resumed run starts at k+1 (no re-emits) → **PASS** (paired with a terminal case).

---

### V7 — Terminal Policy

**KAT-Z1:** Both **exhausted** and **final** present → **`E_TERMINAL_CARDINALITY`** (`where:"terminal-count"`).
**KAT-Z2:** Attempts exist but **no terminal** row → **`E_TERMINAL_CARDINALITY`** (`where:"no-terminal"`).
**KAT-Z3:** **Accept** case but `final.attempts != n_attempts` when present → **`E_TERMINAL_CARDINALITY`**.
**KAT-Z4:** **Cap-abort** case but exhausted payload `attempts != 64` when present → **`E_TERMINAL_CARDINALITY`**.
**KAT-Z5:** **Cap-downgrade** case but final lacks/false `exhausted` (when field present) → **`E_TERMINAL_CARDINALITY`**.
**KAT-Z6 (optional mapping):** Final carries `K_target`, accepting attempt carries `k`, but `K_target != k` → **`E_ACCEPT_MAPPING`**.

---

### V8 — Hygiene

**KAT-H1:** Duplicate **event** row (identical family, counters, payload key/val) → **`E_HYGIENE`** (`where:"duplicate-event"`).
**KAT-H2:** Duplicate **trace** row (identical cumulative totals) → **`E_HYGIENE`** (`where:"duplicate-trace-row"`).
**KAT-H3:** Unknown family tag or late label drift → **`E_HYGIENE`** (`where:"unknown-family|label-drift|trace-label-drift"`).

---

### ENV / CONTRACT (harness/infra)

**KAT-E1:** Missing required dataset (e.g., attempts table not present) → **exit=2**, `_failed.json` with `code:"E_ENV_MISSING_DATASET"`.
**KAT-E2:** Broken schema anchor → **exit=2**, `code:"E_ENV_SCHEMA_ANCHOR"`.
**KAT-E3:** Dictionary resolve error → **exit=2**, `code:"E_ENV_DICT_RESOLVE"`.

---

**How to use this in CI:**
For each KAT, materialise only the **minimal** rows required, run L3 over the slice, and assert the **exact** verdict (PASS with terminal kind, or `_failed.json.code`). This suite, plus the four PASS cases, guarantees coverage of every contract L3 enforces.

---