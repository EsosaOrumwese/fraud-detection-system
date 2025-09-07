# L2 · State-1 — Orchestration / DAG

# 1) Purpose

Coordinate **S1.1 → S1.5** to (a) emit **exactly one** hurdle event per merchant into the authoritative stream, (b) maintain a **cumulative** RNG trace for `(module="1A.hurdle_sampler", substream_label="hurdle_bernoulli")`, and (c) return an in-memory **handoff tuple** $\Xi_m$ with a **next_state** ∈ {SingleHomePlacement, NegativeBinomialS2}. L2 adds **no new math** and **no policy**; it only wires the frozen kernels and enforces the path/partition, timestamp, numeric, and budget invariants already defined.

---

# 2) Contract (inputs → outputs)

## Inputs (closed set)

1. **Run lineage & gate (from S0):**

   * `seed:u64`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`, `run_id:hex32`.
   * **Gate:** An `rng_audit_log` for `{seed, parameter_hash, run_id}` **exists before** the first hurdle event is emitted.

2. **Merchant universe (from S0, same `manifest_fingerprint`):**

   * Set `M ⊂ u64` of `merchant_id`.
   * Mapping `home_iso: u64 → str` (ISO-3166-1 alpha-2, uppercase).
   * **Coverage obligation:** every `m ∈ M` must yield **exactly one** hurdle event row in this run.

3. **Model artefacts (governed):**

   * **Design vectors** $x_m ∈ ℝ^D$: intercept + MCC + **channel** + **5** GDP-bucket dummies; produced in S0 (materialized under `parameter_hash`); consumed as-is (S1 **does not** rebuild).
   * **Coefficient vector** $\beta ∈ ℝ^D$: single YAML; atomic load; aligned to $x_m$.
   * **Frozen block order assertions:** channel **exactly** `["CP","CNP"]`; buckets **exactly** `[1,2,3,4,5]`; and `|β| == dim(x_m)`.

4. **Registry & dictionary anchors (authoritative paths/schemas):**

   * **Hurdle event** dataset id `rng_event_hurdle_bernoulli`
     Path template:
     `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
     Schema: `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`
     **Partitions are exactly:** `{seed, parameter_hash, run_id}` (no `fingerprint`, `module`, or `substream_label` in the path).
   * **RNG trace** dataset id `rng_trace_log`
     Path: `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`
     Schema: `schemas.layer1.yaml#/rng/core/rng_trace_log`.

5. **Numeric policy (relied on from S0):**

   * IEEE-754 **binary64**, **round-to-nearest even**, **no FMA**, **no FTZ/DAZ**, fixed-order reductions. (Required by S1.2 two-branch logistic.)

6. **Serialization & typing rules (apply everywhere):**

   * **Lineage types:** `seed` is a **JSON integer**; `run_id`, `parameter_hash`, `manifest_fingerprint` are **hex strings**.
   * **Counters & totals:** `rng_counter_*_{lo,hi}`, `blocks`, and all *_total fields are **JSON integers**.
   * **Trace embedding:** the trace row embeds **`seed` and `run_id`** (and they **must equal** the path keys); **`parameter_hash` is path-only**.
   * **Floats:** `pi` and (if present) `u` are **JSON numbers** serialized with **shortest round-trip** decimal.
   * **Timestamp:** `ts_utc` is RFC-3339 **UTC** with **exactly 6** fractional digits (microseconds) and a trailing `Z`.
   * **Counter field names** are normative: `rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`. Producers **must** use these exact keys.

---

## Outputs / side-effects (closed set)

1. **Authoritative hurdle events (persisted):**

   * **Cardinality:** exactly one row per `{seed, parameter_hash, run_id, merchant_id}`.
   * **Envelope (must be present and correct):**

     * `ts_utc` (microseconds), `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"`,
     * lineage keys `{seed, parameter_hash, manifest_fingerprint, run_id}`,
     * counters `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}`,
     * `draws` as **decimal u128 string**,
     * `blocks:u64` (normative).
   * **Payload (minimal & authoritative):**

     * `merchant_id:u64`,
     * `pi:number` (binary64 round-trip),
     * `is_multi:boolean`,
     * `deterministic:boolean`,
     * `u:number|null` with **presence rule**: present iff `0 < pi < 1`, else `null`.
   * **Mandatory identities per row:**

     * `u128(after) − u128(before) = decimal_string_to_u128(draws)`,
     * **Hurdle law:** `blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`,
     * **Determinism law:**
       `pi ∈ {0.0,1.0} ⇒ u=null ∧ deterministic=true ∧ is_multi=(pi==1.0)`;
       `0 < pi < 1 ⇒ u∈(0,1) ∧ deterministic=false ∧ is_multi=(u < pi)`.

2. **Cumulative RNG trace (persisted):**

   * **Granularity:** cumulative per `(module, substream_label)` within `{seed, parameter_hash, run_id}`; **no merchant dimension**, **no per-event trace rows**.
   * **Totals (saturating `u64`):** `blocks_total`, `draws_total`, `events_total`.
   * **Counter words for reconciliation:** `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}`.
   * **Reconciliation duties:**
     `blocks_total` equals the unsigned counter delta across all emitted events; `draws_total` equals the saturating sum of per-event `draws`; `events_total` counts emissions (saturating).

3. **Handoffs (in memory only):**

   * For each merchant, return $\Xi_m=(\text{is_multi}:\mathbf{bool},\,N:\mathbb{N},\,K:\mathbb{N},\,\mathcal C:\text{set[ISO]},\,C^\star:\text{u128})$ and `next_state ∈ {SingleHomePlacement, NegativeBinomialS2}`.
   * **Construction:** `is_multi` from the emitted hurdle event; `N:=1, K:=0, 𝓒:={home_iso}` if single-site (`SingleHomePlacement`); `N,K` unassigned and route `NegativeBinomialS2` if multi-site.
   * **Counter discipline:** `C*` is the **post** counter from the hurdle envelope; it is **audit-only** — **no counter chaining** to downstream RNG. All downstream streams derive their own base counters from their own labels.

4. **Cardinality & coverage obligations (per run):**

   * Hurdle row count **equals** `|M|` (the merchant universe for this run).
   * There is **exactly one** hurdle record per merchant.
   * Trace totals reconcile with the set of emitted rows and their counter deltas.

5. **Non-goals / exclusions (by design):**

   * L2 emits **no validation bundle** and introduces **no new artefacts** besides the two streams above.
   * L2 performs **no retries** and adds **no parallel reduction** for trace; per-merchant processing is serialized to keep the cumulative trace trivial and deterministic.
   * L2 does **not** enumerate or trigger downstream RNG streams; presence of later 1A streams is validated separately and must be **iff** `is_multi=true`.

---

That’s the contract your implementer can wire to: fixed inputs, fixed outputs, exact field names and types, invariant laws, and no hidden behavior.

---

# 3) Determinism & scheduling

## 3.1 Determinism anchors (what fixes the bytes)

1. **Keyed substreams (order-invariant RNG).**
   For each merchant `m`, the RNG **base counter** is derived from the frozen mapping:

   ```
   master = derive_master_material(seed, manifest_fingerprint_bytes); merchant_u64 = merchant_u64_from_id64(m); base = derive_substream(master, substream_label="hurdle_bernoulli", ids=(merchant_u64))
   ```

   This removes any dependence on execution order, batching, or concurrency. Two runs with the same `(seed, parameter_hash, manifest_fingerprint)` produce identical counters for every `m`.

2. **Single-uniform law + lane policy.**
   Hurdle draws **0** uniforms if `π ∈ {0,1}`, otherwise draws **exactly 1** uniform using **low lane** and the **open-interval** map `u01: (0,1)`. As a result:

   * `u` is never `0` or `1`.
   * The envelope must satisfy the **budget identity**:

     ```
     u128(after) − u128(before) = decimal_string_to_u128(draws)
     ```

     and for hurdle specifically:

     ```
     blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}
     ```

3. **Numeric profile (relied on from S0).**
   All FP compute uses IEEE-754 **binary64**, **round-to-nearest-even**, **no FMA**, **no FTZ/DAZ**, **fixed-order** reductions. S1.2 evaluates the logistic via the two-branch stable form under this policy. Given the same `(β, x_m)`, `π` is deterministic.

4. **Run-id neutrality.**
   `run_id` partitions logs but **does not** affect RNG or math. Only `(seed, parameter_hash, manifest_fingerprint)` bind substreams and model artefacts.

5. **Serialization contracts.**

   * `ts_utc` is RFC-3339 **UTC** with **exactly 6** fractional digits (microseconds).
   * **Lineage & counters:** `seed` is a **JSON integer**; `run_id`, `parameter_hash`, and `manifest_fingerprint` are **hex strings**. Event/trace counters and totals are **JSON integers**.
   * For `rng_trace_log`, only **`seed` (int)** and **`run_id` (hex string)** are embedded; **`parameter_hash` is path-only**.
   * `π` and (if present) `u` are **JSON numbers** emitted with **shortest binary64 round-trip** decimal.

---

## 3.2 Scheduling model (simple, replayable, validator-friendly)

**Gate first.**
Before any merchant processing, **assert** that the RNG audit exists for `{seed, parameter_hash, run_id}`. No events may be emitted without this.

**Merchant order is fixed.**
Iterate `m ∈ M` in a **total order** (ascending `merchant_id`). This fixes append order of event rows and the sequence of cumulative trace updates (RNG outcomes are order-invariant anyway due to keyed substreams).

**Per-merchant pipeline is serial.**
For each merchant, execute the five kernels **in sequence**:

```
S1.1  Load & Guard     →   S1.2  η→π (no RNG)
   →  S1.3  RNG & Decision (≤1 uniform)
   →  S1.4  Emit Event + Update Cumulative Trace
   →  S1.5  Handoff (in-memory)
```

* This keeps the **trace cumulative** and trivially reconcilable to emitted budgets and counter deltas — no post-hoc reduction, no merge races, no clock-skew issues in totals.
* **Do not run S1.4 in parallel.** Emission and cumulative trace update are the single serialization point by design. (S1.1–S1.3 *could* be parallelized in theory, but we deliberately keep the whole per-merchant pipeline serial to avoid coordination code. If you ever parallelize earlier stages, you must still serialize S1.4 and preserve the same per-merchant ordering.)

**Event→Trace ordering.**
Within a merchant, call S1.4 once:

1. write the **event** (authoritative envelope + payload), then
2. append the **cumulative** trace row.
   If the event write fails, **do not** update the trace.

---

## 3.3 Idempotency, duplicates, and write discipline

1. **Exactly one row per merchant per run.**
   Within `{seed, parameter_hash, run_id}`, there must be **exactly one** hurdle record for each `merchant_id`. The dataset cardinality equals `|M|` (the ingress merchant universe for the run).

2. **Hard duplicate guard (mandatory).**
   The event writer **must abort** on any second attempt to emit a hurdle row for the same `(seed, parameter_hash, run_id, merchant_id)` — **no upserts**, **no silent skips**. This preserves idempotency and keeps validators’ uniqueness checks meaningful.

3. **Partition ↔ embed equality.**
   Event path partitions are **exactly** `{seed, parameter_hash, run_id}` (no `fingerprint`, `module`, `substream_label` in the path). The envelope must embed the same lineage keys and the literals:

```
module          = "1A.hurdle_sampler"
substream_label = "hurdle_bernoulli"
```

4. **Counters & identities are authoritative.**
   Persist the exact `rng_counter_before_{lo,hi}` and `rng_counter_after_{lo,hi}` from S1.3’s streams. Enforce on write:

```
u128(after) − u128(before) = decimal_string_to_u128(draws)
blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}
```

Reject the write if these fail.

5. **Timestamp precision and typing.**
   Emit `ts_utc` with **microsecond** precision (`… .ffffffZ`). Emit **counters** (and `seed`) as **integers**; emit **hex lineage ids** (`run_id`, `parameter_hash`, `manifest_fingerprint`) as **lowercase hex strings**; emit `π` and `u` as **shortest round-trip** JSON numbers.

---

### 3.4 Concurrency & restart semantics (minimal but explicit)

* **Process scope:** The orchestrator processes merchants in one pass. There’s no mid-run resumption protocol; re-running the same run keys should start from a **clean target** (or rely on the writer’s **duplicate guard** to fail early without altering existing rows).
* **Shard appends:** Writers may append to multiple `part-*` shards, but **within the process** the per-merchant order is maintained. Object key order in JSON is non-semantic; field **names** are normative.
* **Trace saturation:** `events_total`, `blocks_total`, `draws_total` are **saturating u64**. Totals reflect the number of successful event emissions. They are updated **once** per merchant, immediately after the corresponding event write.

---

## 3.5 Why this is sufficient (and not over-engineered)

* RNG replay is guaranteed by **keyed substreams** and the **single-uniform law**; scheduling only affects append order, not values.
* Serializing S1.4 keeps the **cumulative trace** trivially correct — no reducers, no lock contention, no reconciliation complexity.
* The **duplicate guard** and **partition/embed equality** make the writer idempotent and validator-friendly.
* All laws and types (microsecond `ts_utc`, integer counters, round-trip floats) are captured here so validators can deterministically re-derive `u`, re-check identities, and reconcile the final totals.

---

# 4) Per-merchant wiring diagram + orchestrator skeleton

This section shows, with no gaps, **how S1.1→S1.5 are wired for each merchant** and gives a drop-in orchestrator. It uses only frozen L0/L1 primitives and the S1 expansion; no new logic is invented.

---

## 4.1 Sub-state flow (inside the per-merchant loop)

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Inputs fixed for the run: seed, parameter_hash, manifest_fingerprint,     │
│ run_id, merchant universe M, home_iso(m), design vectors x_m, β.          │
│ Gate: rng_audit_log exists for {seed, parameter_hash, run_id}.            │
└───────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
        for m in sort_ascending(M):                           (deterministic order)
                 │
                 ├─ S1.1  Load & Guard
                 │        • fetch x_m (from S0.5 materialization) and atomically load β
                 │        • assert |β| == dim(x_m), encoder block order, rng audit presence
                 │        • bind event dataset/schema + path partitions {seed, parameter_hash, run_id}
                 │        → (β, x_m, ctx)
                 │                                                             
                 ├─ S1.2  Probability map
                 │        • η = β·x_m (Neumaier dot); π = logistic_branch_stable(η) in binary64
                 │        • assert finite η; 0 ≤ π ≤ 1
                 │        → (η, π)                                                
                 │
                 ├─ S1.3  RNG & decision
                 │        • master = derive_master_material(seed, manifest_fingerprint_bytes);
                 │          merchant_u64 = merchant_u64_from_id64(m);
                 │          s_base = derive_substream(master, "hurdle_bernoulli", (merchant_u64))
                 │        • if π∈{0,1}: draws="0", blocks=0, u=null, after=before
                 │          else: (u, s_after, draws="1"), blocks=1 with low lane, u∈(0,1), is_multi=(u<π)
                 │        → Decision{deterministic, is_multi, u|null, draws, blocks,
                 │                     before_hi/lo, after_hi/lo, stream_before, stream_after}        
                 │
                 ├─ S1.4  Emit event + update cumulative trace   (serialization point; do not parallelize)
                 │        • write hurdle event to:  *(resolved via the dataset **dictionary** at runtime — do **not** hard-code path strings)*
                 │          logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
                 │          with full envelope (microsecond ts_utc, counters, draws u128 string, blocks) and minimal payload
                 │        • identities:
                 │            u128(after) − u128(before) = decimal_string_to_u128(draws);
                 │            blocks == u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}
                 │        • append cumulative rng_trace_log row (saturating totals; per (module,substream))
                 │        → (totals' (blocks_total, draws_total, events_total), emitted:EmittedHurdle)                                 
                 │
                 └─ S1.5  Handoff (in-memory only)
                          • Read **is_multi** (payload) and **C*** = post counter (envelope) **from the emitted event**.
                          • Set **N,K,𝓒 by rule**: if single-site, `N=1, K=0, 𝓒={home_iso(m)}`; else leave `N,K` unassigned and route `NegativeBinomialS2`.
                          • next_state = SingleHomePlacement (formerly S7) if single-site; else NegativeBinomialS2 (formerly S2) (multi-site)
                          → append (m, Xi_m, next_state)                                                           
```

**Non-negotiables enforced along the path:**

* **Order-invariant substreams:** `master = derive_master_material(seed, manifest_fingerprint_bytes); merchant_u64 = merchant_u64_from_id64(m); base = derive_substream(master, "hurdle_bernoulli", (merchant_u64))`; no cross-label chaining.
* **Single-uniform law + lane policy:** 0 draws if π∈{0,1}; else 1 draw using **low lane**; `u∈(0,1)`.
* **Budget identities:** `u128(after)−u128(before) = decimal_string_to_u128(draws)` and `blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}` (hurdle).
* **Authoritative paths/schemas:** hurdle events under `{seed, parameter_hash, run_id}`; `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"` in envelope; trace is cumulative (no merchant dimension).

---

## 4.2 Orchestrator skeleton (drop-in, code-agnostic)

```pseudocode
# Types used in this section
struct Totals { blocks_total:u64, draws_total:u64, events_total:u64 }    # L0 order: (blocks, draws, events)

# Minimal projection for routing (authoritative fields for S1.5 consumption)
# Note: Full envelope includes before_* counters, draws, blocks; L2 reads only the subset it needs here.
struct EmittedHurdle {
  envelope: {
    module: string,                  # "1A.hurdle_sampler"
    substream_label: string,         # "hurdle_bernoulli"
    seed: u64,
    parameter_hash: hex64,
    manifest_fingerprint: hex64,
    run_id: hex32,
    rng_counter_after_hi: u64,
    rng_counter_after_lo: u64
  },
  payload: {
    merchant_id: u64,
    pi: f64,                         # same binary64 value that was serialized
    is_multi: bool,
    deterministic: bool,
    u: f64|null                      # null iff deterministic
  }
}

# Entry: orchestrate State-1 over the merchant universe
function run_S1(seed:u64, parameter_hash:hex64, manifest_fingerprint:hex64, manifest_fingerprint_bytes: bytes[32], run_id:hex32,
                merchants:list<u64>, home_iso_of: map<u64,string>)
  # Gate: audit-before-first-event
  assert exists_rng_audit_row(seed, parameter_hash, run_id), E_S1_RNG_AUDIT_MISSING  # 

  # Pre-loop hygiene
  if has_duplicates(merchants):
      abort_run(E_S1_DUPLICATE_MERCHANT_IN_UNIVERSE, offending_ids(merchants))
  for m in merchants:
      if not is_valid_iso_alpha2(home_iso_of.get(m)):
          abort_run(E_S1_HOME_ISO_INVALID, {merchant_id:m, home_iso:home_iso_of.get(m)})

  # Empty-universe early return
  if merchants.is_empty():
      return ([], Totals{0,0,0})

  totals   = Totals{0,0,0}
  handoffs = []

  # Deterministic file/trace order (RNG is order-invariant anyway)
  for m in sort_ascending(merchants):
      # S1.1 — Load & Guard
      (beta, x_m, ctx) = S1_1_load_and_guard(m, seed, parameter_hash, manifest_fingerprint, manifest_fingerprint_bytes, run_id)
      # asserts: |beta|==dim(x_m); path partitions {seed,parameter_hash,run_id} bound; audit exists.  

      # S1.2 — Probability map (no RNG)
      (eta, pi) = S1_2_probability_map(beta, x_m)  # finite(eta); 0≤pi≤1  

      # S1.3 — RNG & Decision (≤1 uniform; keyed base counter)
      decision = S1_3_rng_and_decision(pi, m, ctx)
      # decision carries: deterministic,is_multi,u|null,draws("0"|"1"),blocks(0|1),
      # before_hi/lo, after_hi/lo, stream_before/after.  

      # S1.4 — Emit event + update cumulative trace  (serialization point)
      (totals, emitted) = S1_4_emit_event_and_update_trace(m, pi, decision, ctx, totals)
# writes 1 hurdle row; appends cumulative rng_trace_log; enforces budget identity.  
      # S1.5 — Build handoff tuple & routing (in-memory only; no counter chaining)
      (Xi_m, next_state) = S1_5_build_handoff_and_route(emitted, home_iso_of[m])
      append(handoffs, (m, Xi_m, next_state))  # Xi_m = (is_multi, N, K, 𝓒, C*).  

  # Post-condition (checked later by validator): totals reconcile with Σ(event budgets) and counter delta.  
  return (handoffs, totals)
```

**Notes for implementers (binding, not suggestions):**

* **Do not** run S1.4 in parallel; emission + trace update is the single serialization point.
* Enforce **duplicate guard** in the event writer: a second write for the same `(seed, parameter_hash, run_id, merchant_id)` **must abort** (no upsert/skip).
* The event **path partitions are exactly** `{seed, parameter_hash, run_id}`; envelope embeds the same plus `module`/`substream_label` literals; `manifest_fingerprint` is **embedded only**.
* `ts_utc` uses **microseconds** (6 fractional digits). `pi` and (if present) `u` are JSON numbers with **binary64 round-trip** decimals. **Counters are JSON integers; lineage types are `seed`=integer and `run_id`/`parameter_hash`/`manifest_fingerprint`=hex strings (trace embeds only `seed` & `run_id`).**

---

## 4.3 Mini call-map (what each sub-state consumes/produces)

| Step     | Consumes                                                                                                        | Calls (L1/L0)                                                                            | Produces / Side-effects                                                                                                            |
|----------|-----------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| **S1.1** | `m`, `{seed,parameter_hash,manifest_fingerprint,run_id}` + `manifest_fingerprint_bytes`, `x_m` (S0.5), β (YAML) | `atomic_load_yaml_vector`, `fetch_hurdle_design_vector_for`, `exists_rng_audit_row`      | `(β, x_m, ctx)` with bound dataset/schema/path; **no writes**; guards: block-order check, path-partition lint, RNG audit presence. |
| **S1.2** | `(β, x_m)`                                                                                                      | `dot_neumaier`, `logistic_branch_stable`                                                 | `(η, π)` (finite; `[0,1]`); **no writes**                                                                                          |
| **S1.3** | `π`, `m`, `ctx`                                                                                                 | `derive_substream`, `uniform1` (only if `0<π<1`)                                         | `Decision{…}` with before/after counters, `draws`, `blocks`, `u`, `null`.                                                          |
| **S1.4** | `m`, `π`, `Decision`, `ctx`, `totals`                                                                           | `begin_event_micro`, `end_event_emit`, `update_rng_trace_totals`, `f64_to_json_shortest` | **Writes** one hurdle event row; **appends** cumulative trace; returns `(totals', emitted:EmittedHurdle)`.                         |
| **S1.5** | `emitted:EmittedHurdle`, `home_iso(m)`                                                                          | —                                                                                        | `Xi_m` and `next_state ∈ {SingleHomePlacement, NegativeBinomialS2}`; **no writes**; `C*` is audit-only.                            |

---

## 4.4 Why this wiring is correct and sufficient

* The **keyed substream** per merchant and the **single-uniform law** make RNG outputs independent of scheduling; the serial **S1.4** keeps the cumulative trace trivial and validator-friendly.
* Event **schema/path** and **budget identities** are enforced at the emission point; validators later replay counters and reconcile totals without extra hints.
* The handoff $\Xi_m$ is built from the **authoritative emitted event**, carries **audit-only** counters, and routes unambiguously to `SingleHomePlacement`/`NegativeBinomialS2`.

## 4.5A — Per-merchant DAG (one merchant `m`)

```
[Inputs fixed for run: seed, parameter_hash, manifest_fingerprint, run_id]
[Inputs per m: merchant_id=m, home_iso(m), x_m from S0.5, β (single YAML)]

Gate-A: rng_audit_log exists for {seed, parameter_hash, run_id}
    │
    ▼
S1.1(m): Load & Guard
    inputs: x_m, β, lineage
    outputs: (β, x_m, ctx)
    │
    ▼
S1.2(m): Probability Map  (no RNG)
    inputs: (β, x_m)
    outputs: (η, π) with 0≤π≤1
    │
    ▼
S1.3(m): RNG & Decision  (≤1 uniform)
    inputs: (π, m, ctx)
    outputs: Decision{deterministic, is_multi, u|null, draws("0"|"1"), blocks(0|1),
                      before_hi/lo, after_hi/lo, stream_before/after}
    │
    ▼   ── Serialization point (do NOT parallelize S1.4) ──
S1.4(m): Emit Event + Update Cumulative Trace
    inputs: (m, π, Decision, ctx, totals_in)
    side-effects:
      • append one row to rng_event_hurdle_bernoulli (authoritative envelope + minimal payload)
      • append one row to rng_trace_log (cumulative, saturating)
    outputs: (totals_out, emitted:EmittedHurdle)
    │
    └────► S1.5(m): Handoff (in-memory only; no counter chaining)
             inputs: emitted:EmittedHurdle, home_iso(m)
             outputs: Xi_m, next_state ∈ {SingleHomePlacement, NegativeBinomialS2}
```

**Edge invariants (enforced across S1.3→S1.4):**

* `u128(after) − u128(before) = decimal_string_to_u128(draws)`
* `blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`
* if `0 < π < 1`: `u ∈ (0,1)`, `deterministic=false`, `is_multi = (u < π)`
* if `π ∈ {0,1}`: `u=null`, `deterministic=true`, `is_multi = (π == 1.0)`

---

## 4.5B — Run-level DAG (whole state-1)

```
                           ┌─────────────────────────────────────────────────────┐
                           │ Fixed run inputs: seed, parameter_hash,             │
                           │ manifest_fingerprint, manifest_fingerprint_bytes,   │
                           │ run_id, M, home_iso(.), β, x_m                      │
                           └─────────────────────────────────────────────────────┘
                                           │
                                           ▼
                         Gate-A: rng_audit_log exists for {seed, parameter_hash, run_id}
                                           │
                                           ▼
                           Deterministic loop over m ∈ sort_ascending(M)
                                           │
             ┌────────────────────────────────────────────────────────────────────────┐
             │ For each merchant m:                                                   │
             │   S1.1(m) → S1.2(m) → S1.3(m) → S1.4(m) → S1.5(m)                      │
             │                     (S1.4 is the only serialized emission/trace step)  │
             └────────────────────────────────────────────────────────────────────────┘
                      │                 │
                      │                 └──► append (m, Xi_m, next_state) → handoffs[]
                      │
                      └──► rng_trace_log cumulative totals evolve monotonically (saturating)
                                           │
                                           ▼
                               Return (handoffs, final_totals)
```

---

## 4.5C — Explicit edge list (so nothing is ambiguous)

* **E0:** `Gate-A → S1.1(m)` for all `m`. (Audit must exist before any emission.)
* **E1:** `S1.1(m) → S1.2(m)` carries `(β, x_m)`.
* **E2:** `S1.2(m) → S1.3(m)` carries `(π)` (and `ctx` from S1.1).
* **E3:** `S1.3(m) → S1.4(m)` carries `Decision` bundle + `(π, ctx)` + current `totals`.
* **E4:** `S1.4(m) → S1.5(m)` carries `emitted:EmittedHurdle` and `home_iso(m)`.
* **E5:** `S1.4(m) → S1.4(m+1)` is the **serialization** on cumulative trace totals (`totals_out → totals_in` of the next merchant).
* **E6:** `S1.5(m) → handoffs[]` appends `(m, Xi_m, next_state)`.

---

## 4.5D — What may/shall not be parallelized

* **Shall not:** S1.4 (event emission + cumulative trace update) — keep strictly serial to maintain trivially correct cumulative totals.
* **May (future, if ever):** parts of S1.1–S1.3 could be overlapped, **provided** S1.4 is still invoked in the same deterministic merchant order. We are **not** doing this now to avoid introducing coordination and because the spec expects cumulative trace without reductions.

---

## 4.5E — Writer/trace discipline (idempotency & uniqueness)

* **Uniqueness key:** `(seed, parameter_hash, run_id, merchant_id)` — **writer must abort** on a second attempt (no upsert/silent skip).
* **Partitions:** event path partitions are **exactly** `{seed, parameter_hash, run_id}`; `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"` are in the **envelope**, not the path.
* **Typing & time:** `ts_utc` uses **microseconds**; **counters** are JSON integers; **lineage types:** `seed` is a JSON integer, and `run_id`/`parameter_hash`/`manifest_fingerprint` are lowercase **hex strings**; `pi`/`u` are JSON numbers serialized as **shortest round-trip** binary64.

---

# 5) L2 state it maintains (minimal)

L2 carries *only* what it must to wire S1.1→S1.5 deterministically and return clean handoffs. No new math, no hidden caches that change semantics.

## 5.1 Run-lifetime state

* `totals : { blocks_total:u64, draws_total:u64, events_total:u64 }`
  Initialized to `{0,0,0}` and **updated only by S1.4** (cumulative, saturating).
  Invariants each iteration `i`:

  * `events_total[i] = events_total[i-1] + 1` (exactly one event per merchant).
  * `blocks_total[i] = blocks_total[i-1] + decision.blocks` (0 or 1).
  * `draws_total[i] = draws_total[i-1] + u128_to_uint64_or_abort(decimal_string_to_u128(decision.draws))` (0 or 1 for hurdle).
    *(L2 can assert these deltas cheaply; S1.4 already enforces the per-event identities.)*

* `handoffs : list<(merchant_id:u64, Xi, next_state:{SingleHomePlacement|NegativeBinomialS2})>`
  Append-only, one entry per processed merchant, in the same deterministic order as the loop. Not persisted by L2.
  End-of-run invariant: `len(handoffs) == |M|` and each `merchant_id` appears exactly once.

* `seen_merchants : set<u64>` (hygiene)
  Used to catch duplicate `merchant_id` values in `M` **before** any write. If a duplicate is seen, abort early (prevents duplicate emissions).

## 5.2 Per-iteration scratch (ephemeral; do not persist)

* `(beta, x_m, ctx)` from **S1.1** — discarded after use; `ctx` is re-created each merchant to preserve the S1.1 guards and path lints.
* `(eta, pi)` from **S1.2** — transient floats.
* `decision` from **S1.3** — used immediately by **S1.4**; discarded after S1.4 returns.
* `emitted : EmittedHurdle` from **S1.4** — passed directly to **S1.5**; not retained after building `Xi_m`.

## 5.3 Optional, semantics-neutral caches (allowed but not required)

* `beta_cached : f64[D] | None`
  Memoize the hurdle coefficient vector after the first S1.1 to avoid repeated YAML reads. If used, assert `equal_vectors(beta, beta_cached)` on subsequent iterations (should always hold under the same `parameter_hash`).

* `ctx_static : { module, substream_label, event_dataset_id, event_schema_ref, event_path_tpl } | None`
  You may cache the constant literals returned by the first S1.1. Still call S1.1 for each merchant to fetch `x_m` and re-validate shapes/partitions/audit presence.

> Anything not listed above is out of scope for L2 state. In particular, L2 does **not** keep clocks, extra counters, alt RNG state, or any per-merchant trace beyond what S1.4 returns.

---

## 5.4 Empty-universe behavior (normative)

If the merchant universe is empty:

* L2 still enforces **Gate-A** (audit-before-first-event).
* L2 performs **no writes** (no hurdle events, no trace rows).
* L2 returns `handoffs = []` and `totals = { blocks_total:0, draws_total:0, events_total:0 }`.
* Validators MUST accept a run with zero emissions as valid.

**Pseudocode patch (early return):**

```pseudocode
assert exists_rng_audit_row(seed, parameter_hash, run_id)
if merchants.is_empty():
    return ([], {blocks_total:0, draws_total:0, events_total:0})
```

---

# 6) Gates & asserts (where L2 enforces them)

L2 has exactly three responsibilities here: **gate the run**, **sanity-check inputs**, and **verify the minimal loop-level invariants** that aren’t already enforced by L1.

## 6.1 Pre-loop gates (hard stops)

1. **Audit-before-first-event** …(unchanged)
2. **Merchant universe hygiene** (now with explicit error classes):

   * If `M` contains duplicates → **abort** `E_S1_DUPLICATE_MERCHANT_IN_UNIVERSE`
     *class:* `S1.PRECONDITION`; *fields:* `{merchant_id}`
     *text:* “Duplicate merchant_id found in universe.”
   * If `home_iso_of[m]` missing/invalid → **abort** `E_S1_HOME_ISO_INVALID`
     *class:* `S1.PRECONDITION`; *fields:* `{merchant_id, home_iso}`
     *text:* “home_iso missing or not ISO-3166-1 alpha-2.”

> These two are **precondition** failures (not writer/runtime errors) and map to your S1 failure taxonomy as *input hygiene*.

## 6.2 In-loop asserts (cheap, deterministic)

* **Duplicate guard (runtime):**
  If `m ∈ seen_merchants` during iteration → **abort** `E_S1_DUPLICATE_MERCHANT_RUNTIME`
  *class:* `S1.PRECONDITION`; *fields:* `{merchant_id}`
  *text:* “Duplicate merchant_id encountered during processing.”

* **Totals evolve monotonically** …(unchanged)

## 6.3 End-of-run checks (lightweight)

Add explicit zero-universe acceptance:

* If `|M| == 0`, then `len(handoffs) == 0`, `events_total == 0`, `blocks_total == 0`, `draws_total == 0`. This is **valid**.

## 6.4 Failure behavior (clarified)

* L2 mints **only** the hygiene errors named above:

  * `E_S1_DUPLICATE_MERCHANT_IN_UNIVERSE` (pre-loop)
  * `E_S1_HOME_ISO_INVALID` (pre-loop)
  * `E_S1_DUPLICATE_MERCHANT_RUNTIME` (in-loop)
* All other failures propagate directly from S1.1–S1.5 with their original classes/fields.
* No retries; no compensation writes; if S1.4 event write fails, **do not** update trace or totals.

---

This keeps L2 lean: a tiny bit of **state** (totals + handoffs + seen set), one **hard gate** (audit), a couple of **input hygiene** checks, and three **loop-level** invariants tied directly to what S1.4 returns. Everything else stays where it belongs—in the L1 kernels and, later, in L3 validators.

---

# 7) Write discipline (so validators smile)

This section pins **exactly how S1 writes** its two streams. It mirrors the schemas and the L1 kernel contracts; nothing new is invented here.

---

## 7.1 Authoritative hurdle event writer

**Target (fixed):**
`logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
Schema: `#/rng/events/hurdle_bernoulli`. Partitions are **exactly** `{seed, parameter_hash, run_id}`.

**One call → one row**

* Each S1.4 call **must** append **exactly one** JSONL row.
* Row key (logical uniqueness): `(seed, parameter_hash, run_id, merchant_id)`. A second attempt for the same key **must abort** (no upserts, no silent skips).

**Envelope fields (mandatory and authoritative):**

* `ts_utc`: RFC-3339 UTC with **exactly 6** fractional digits (microseconds) and `Z`.
* `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"`.
* Lineage keys: `{seed, parameter_hash, manifest_fingerprint, run_id}` — values **must equal** the path partitions (for the three partitioned keys).
* Counters: `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}` (unsigned 64-bit words).
* Budgets:

  * `draws`: **decimal u128 string** (e.g., `"0"` or `"1"` for hurdle).
  * `blocks`: **u64** computed from the counter delta.

**Payload fields (minimal and complete):**

* `merchant_id:u64`.
* `pi:number` (binary64, serialized shortest-round-trip).
* `is_multi:boolean`.
* `deterministic:boolean`.
* `u:number|null` with the **presence rule**: `u` is **null** iff `pi ∈ {0,1}`, otherwise `u ∈ (0,1)`.

**Row identities enforced at write (reject row if any fail):**

* `u128(after) − u128(before) = decimal_string_to_u128(draws)`.
* **Hurdle law:** `blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`.
* Determinism law:

  * `pi ∈ {0,1} ⇒ u=null ∧ deterministic=true ∧ is_multi=(pi==1.0)`.
  * `0<pi<1 ⇒ u∈(0,1) ∧ deterministic=false ∧ is_multi=(u<pi)`.

**Typing discipline:**

* **Counters** and **`seed`** are **JSON integers**.
* **Hex lineage ids** — `run_id`, `parameter_hash`, `manifest_fingerprint` — are lowercase **hex strings** (per schema).
* `pi` and `u` are **JSON numbers** that parse back to the same binary64.
* Object key order is non-semantic; **field names are normative** (use the exact schema names).

**I/O discipline:**

* Append-only **JSONL**; each event is a single line ending with `\n`.
* Use atomic append (or write-temp-then-rename for new shards) to avoid partial lines.
* S1.4 emits the event **before** updating the trace; if the event write fails, **do not** attempt the trace update.

---

## 7.2 Cumulative RNG trace writer

**Target (fixed):**
`logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`
Schema: `#/rng/core/rng_trace_log`. No merchant dimension; **per (module, substream)**.

**One emission → one cumulative line**

* After each successful hurdle event write, append **one** JSONL row with the updated totals for `(module, substream_label)`.

**Fields (normative):**

* `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"`.
* Lineage keys: `{seed, parameter_hash, run_id}`.
* **Embedded lineage subset (trace schema):** row **embeds** `seed` and `run_id`; **`parameter_hash` is path-only**.
  Writers MUST ensure `row.seed == seed` and `row.run_id == run_id` (byte-for-byte).
* Counters: `rng_counter_before_{lo,hi}`, `rng_counter_after_{lo,hi}` (words taken from the same event’s `before/after`).
* Totals (saturating `u64`):

  * `events_total` (event count so far),
  * `blocks_total` (normative — must equal unsigned counter delta across all emissions to date),
  * `draws_total` (diagnostic — saturating sum of per-event `draws`).

**Trace identities (enforced at write):**

* `blocks_total(new) = blocks_total(prev) + u128_to_uint64_or_abort(u128(after) − u128(before))`.
* `events_total(new) = events_total(prev) + 1`.
* `draws_total(new) = draws_total(prev) + u128_to_uint64_or_abort(decimal_string_to_u128(draws_event))`.

**I/O discipline:**

* Append-only JSONL, atomic per line.
* The trace append happens **immediately after** the corresponding event row is persisted.
* If the trace append fails, the run aborts; the already-written event row remains (validators reconcile this).

---

## 7.3 Partition & embedding equality (lint)

* Event path partitions are **exactly** `{seed, parameter_hash, run_id}`.
* Envelope must embed the **same values** for those keys; `manifest_fingerprint` is embedded but **not** in the path.
* `module` and `substream_label` are **envelope** literals — **never** part of the path.
* L2/L3 validators compare path partitions ↔ embedded fields byte-for-byte.

---

## 7.4 Sharding & ordering

* `part-*.jsonl` naming is free-form, but shards must behave append-only.
* Within a single run process, hurdle events appear in **ascending `merchant_id`** order (our loop order); this is a convenience for ops, not part of the RNG semantics.
* Object key order in JSON is unspecified; do not rely on it.

---

## 7.5 Failure semantics (write layer)

* **Hard abort on duplicates:** the writer **must** reject a second event for the same `(seed, parameter_hash, run_id, merchant_id)`.
* **No partial side-effects:** if the event write fails, **do not** write/advance the trace; if the trace write fails, abort the run without retrying (previous rows remain).
* **No auto-healing:** L2 does not delete/overwrite shards. Any inconsistency is handled by validators and operator action.

---

## 7.6 What is explicitly **not** allowed

* Adding extra fields to the event or trace rows beyond the schema.
* Placing `fingerprint`, `module`, or `substream_label` in the **path**.
* Emitting per-event trace rows.
* Serializing `pi`/`u` as **strings**, or emitting **counters** as strings.  
  (Lineage ids `run_id`, `parameter_hash`, `manifest_fingerprint` **must** be lowercase **hex strings** per schema.)
* Writing `u=0` or `u=1` (mapping is strict-open (0,1)).
* Emitting hurdle rows without a prior **audit row** for the run.

---

These rules keep the writers **idempotent, replayable, and validator-friendly**: partitions and embeds always match, floats reparse exactly, budgets reconcile with counters, and the cumulative trace is trivially correct.

---

# 8) Orchestrator skeleton (the one routine we’ll flesh out)

This is the **final, consolidated** State-1 orchestrator. It wires the frozen L1 kernels (**S1.1 → S1.5**) and applies all L2 responsibilities from §§3–7: audit gating, input hygiene, empty-universe handling, deterministic ordering, serialization of S1.4, delta checks on cumulative totals, and typed handoff. No new algorithms are introduced here.

---

## 8.1 Types & inputs (reference)

```pseudocode
struct Totals {
  blocks_total: u64,  # saturating; normative (matches counter deltas)
  draws_total: u64,   # saturating
  events_total: u64   # saturating
}

# Minimal projection for routing; S1.5 consumes this subset (see §4).
struct EmittedHurdle {
  envelope: {
    module: string, substream_label: string,
    seed: u64, parameter_hash: hex64, manifest_fingerprint: hex64, run_id: hex32,
    rng_counter_after_hi: u64, rng_counter_after_lo: u64
  },
  payload: {
    merchant_id: u64, pi: f64, is_multi: bool, deterministic: bool, u: f64|null
  }
}
```

**Inputs (closed set):**

* `seed:u64, parameter_hash:hex64, manifest_fingerprint:hex64, manifest_fingerprint_bytes: bytes[32], run_id:hex32`
* `merchants:list<u64>` and `home_iso_of: map<u64,string>` (ISO-3166-1 alpha-2)
* Frozen artefacts reachable by L1 (S0.5 design vectors `x_m`, hurdle coefficients β)

**Host-provided helpers (simple guards; no new math):**

* `exists_rng_audit_row(seed, parameter_hash, run_id): bool`
* `has_duplicates(list<u64>): bool`
* `offending_ids(list<u64>): list<u64>`  # only if duplicates
* `is_valid_iso_alpha2(str): bool`

**Frozen L0 helpers referenced by L2 (not host-provided):**
* `decimal_string_to_u128(str_dec): (u64 hi, u64 lo)`  # parses decimal u128 (draws)
* `u128_to_uint64_or_abort(hi:u64, lo:u64): u64`       # casts per-event u128 to u64 or aborts (hurdle draws ∈ {0,1})

---

## 8.3 What this guarantees (and why it’s enough)

* **Replayability:** RNG outcomes are fixed by **keyed substreams** and the **single-uniform law**; scheduling only affects append order, not values. Concretely:  
  `master = derive_master_material(seed, manifest_fingerprint_bytes); merchant_u64 = merchant_u64_from_id64(merchant_id); base = derive_substream(master, label="hurdle_bernoulli", (merchant_u64))`.
* **Validator-friendliness:** Every row obeys budget identities; partitions exactly match embedded lineage keys; `ts_utc` uses microseconds; counters are integers; floats round-trip in binary64. The cumulative trace is trivially reconcilable because it’s updated **immediately after** each event in the same loop.
* **Idempotency & coverage:** One hurdle row per merchant per run; duplicates abort; empty universes are valid no-op runs.

This is the orchestrator an implementer can paste and fill with the L1 calls exactly as specified—nothing more, nothing less.

---

# 9) Failure propagation (what L2 does on error)

L2’s failure policy is simple: **detect early, write atomically, and bubble the original error**. No retries, no compensations, no silent skips. The aim is to keep failures **diagnostic**, **deterministic**, and **validator-friendly**.

---

## 9.1 Philosophy (one paragraph)

* L2 is **wiring**, not logic. If any S1.x kernel raises, L2 **immediately aborts the run** and returns that exact error (code + fields) to the caller.
* L2 mints only a **tiny set of hygiene errors** (pre-loop duplicates, bad/missing `home_iso`, and a defensive in-loop duplicate) and otherwise preserves the original failure provenance.
* **Never** attempt compensation (e.g., backfills, rewrites, or “fixing” counters). Partial success is allowed only where the spec already permits it (e.g., an event row may exist without the trace row if the trace append failed—see §9.3).

---

## 9.2 Failure taxonomy (source → example → L2 action)

| Source                      | Example error (symbolic)                                                 | When it triggers                                        | L2 action        | Side-effect state at abort                                                                   |
|-----------------------------|--------------------------------------------------------------------------|---------------------------------------------------------|------------------|----------------------------------------------------------------------------------------------|
| **Gate**                    | `E_S1_RNG_AUDIT_MISSING`                                                 | Audit row not present before first event                | `abort_run(...)` | No S1 writes happened                                                                        |
| **Hygiene (pre-loop)**      | `E_S1_DUPLICATE_MERCHANT_IN_UNIVERSE`                                    | `merchants` contains duplicates                         | `abort_run(...)` | No S1 writes happened                                                                        |
|                             | `E_S1_HOME_ISO_INVALID`                                                  | Missing/invalid `home_iso(m)`                           | `abort_run(...)` | No S1 writes happened                                                                        |
| **Hygiene (in-loop)**       | `E_S1_DUPLICATE_MERCHANT_RUNTIME`                                        | Same `m` encountered again                              | `abort_run(...)` | Prior merchants’ rows remain; current merchant not written                                   |
| **S1.1**                    | `E_S1_INPUT_MISSING_XM`, `E_S1_DSGN_SHAPE_MISMATCH`, path/partition lint | x-vector absent; β/x mismatch; bad partitions           | Bubble error     | Nothing written for this merchant                                                            |
| **S1.2**                    | `E_S1_NUMERIC_NONFINITE_ETA`, `E_S1_PI_OOB`                              | Dot/logistic produced bad values                        | Bubble error     | Nothing written for this merchant                                                            |
| **S1.3**                    | `E_S1_U_OOB`, `E_S1_DTRM_INCONSISTENT`                                   | RNG boundary/consistency failures                       | Bubble error     | Nothing written for this merchant                                                            |
| **S1.4 (pre-write checks)** | `E_S1_BLOCKS_MISMATCH`, `E_S1_BUDGET_IDENTITY`                           | Envelope identities fail                                | Bubble error     | Nothing written for this merchant                                                            |
| **S1.4 (event write)**      | `E_IO_EVENT_WRITE`, `E_S1_EVENT_DUPLICATE`                               | Append fails; duplicate key                             | Bubble error     | Event not written (I/O failure) **or** duplication rejected; no trace append attempted       |
| **S1.4 (trace write)**      | `E_IO_TRACE_WRITE`                                                       | Cumulative trace append fails                           | Bubble error     | Event row **persisted**; trace for this merchant **missing** (allowed; validators reconcile) |
| **S1.5**                    | `E_S1_INPUT_EVENT_KIND_MISMATCH`                                         | Emitted summary isn’t a hurdle event (shouldn’t happen) | Bubble error     | Event already persisted; handoff not produced                                                |

**Notes**

* `E_S1_EVENT_DUPLICATE` is raised by the **writer** if a second event for the same `(seed, parameter_hash, run_id, merchant_id)` is attempted. L2 also prevents this via hygiene; the writer remains the last line of defense.
* All I/O failures (permissions, disk full, atomic-rename failure) surface as `E_IO_*`; L2 does not retry.

---

## 9.3 Atomicity & ordering on failure (write layer rules)

* **Event-before-trace ordering is strict.** S1.4 **must** persist the **event** first, then append the **trace**.
* **If the event write fails:** **do not** attempt the trace append. Abort with the event’s error.
* **If the trace write fails:** abort after the failure. The already-persisted event row remains. Validators will detect the mismatch and report it; no ad-hoc cleanup is attempted.
* **Line atomicity:** event and trace lines are appended atomically (either a full line with `\n` is present, or no line). If your platform cannot guarantee this, implement write-to-temp then rename.

---

## 9.4 Abort semantics & restart

* **Immediate stop:** On any error (gate, hygiene, S1.x, or I/O), L2 **stops processing further merchants** and returns the error to the caller.
* **Idempotency after abort:** Any events written **before** the failure remain valid; no rewrites occur. Cumulative totals may not match a simple count because the run **did not complete**—that’s expected and is not “fixed” by L2.
* **Re-run policy:** Re-running with the same `{seed, parameter_hash, run_id}` should start from a **clean target**. If the environment cannot guarantee a clean slate, the writer’s duplicate-guard will abort early without altering existing files.

---

## 9.5 Operator visibility (minimal, actionable)

* L2 may log a single operator record on **hygiene aborts**:

  * `duplicate_merchant_ids`: list of offending ids.
  * `bad_home_iso`: `{merchant_id, home_iso}`.
* For S1.x or I/O failures, the **original** error (code + fields) is forwarded to the caller; L2 may log `{stage: "S1.x", merchant_id, error_code}` for triage.
* No sensitive payloads or large blobs in logs; keep to ids and error metadata.

---

## 9.6 What L2 does **not** do (by design)

* No retries/backoffs, no partial compensations, no schema changes, no “best-effort” merges.
* No deletion or mutation of existing shards; L2 is strictly append-only at the writer layer.
* No masking/relabeling of S1 errors; L2 preserves the original error identity and fields.
* No continuation past an error (no “skip and keep going” mode).

---

**Result:** failures are **deterministic**, **containment is precise**, and any partial state is **spec-allowed** and fully diagnosable by validators and operators—without L2 inventing new behavior.

---

# 10) Definition of done (acceptance checks for the doc + impl)

A State-1 run is **done** (spec-true) only if **all** checks below pass. Treat this list as both the authoring DOD (for the doc) and the implementation DOD (for the runtime).

## 10.1 Run setup & gating

* [ ] **Gate-A present:** an RNG audit row exists for `{seed, parameter_hash, run_id}` **before** the first event is emitted.
* [ ] **Audit path ↔ embed equality:** the audit row’s **path partitions** `{seed, parameter_hash, run_id}` **exactly match** the values embedded in that audit row’s envelope/fields.  ← **added**
* [ ] **Universe hygiene:** `merchants` has **no duplicates**; every `m` has a valid `home_iso(m)` (ISO-3166-1 alpha-2, uppercase).
* [ ] **Empty-universe rule:** if `|M|=0`, the orchestrator returns `handoffs=[]` and `totals={0,0,0}` and writes **nothing**. (Validators accept zero-emission runs.)

## 10.2 Event stream (authoritative)

* [ ] **Cardinality:** exactly **one** hurdle row per merchant; dataset row count equals `|M|`.
* [ ] **Uniqueness key:** no duplicate `(seed, parameter_hash, run_id, merchant_id)`; a second emit for the same key **fails**.
* [ ] **Partition ↔ embed equality:** path partitions are **exactly** `{seed, parameter_hash, run_id}` and **match** embedded values; `manifest_fingerprint` is embedded (not in path); `module="1A.hurdle_sampler"` and `substream_label="hurdle_bernoulli"` are **envelope** literals (not path).
* [ ] **Envelope completeness:** `ts_utc` (UTC, microseconds), counters `rng_counter_before_{lo,hi}` & `rng_counter_after_{lo,hi}`, `draws` (decimal u128 string), `blocks` (u64).
* [ ] **Payload minimality & typing:** payload fields are exactly `{merchant_id:u64, pi:number, is_multi:bool, deterministic:bool, u:number|null}` with `pi`/`u` serialized as shortest round-trip binary64 numbers. **Envelope lineage types:** `seed` is a JSON integer; `run_id`, `parameter_hash`, `manifest_fingerprint` are hex strings. **Counters** are JSON integers.
* [ ] **Budget identities per row:** `u128(after) − u128(before) = decimal_string_to_u128(draws)` and **for hurdle**
      `blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`.
* [ ] **Determinism law per row:**
  `pi∈{0,1} ⇒ (u=null ∧ deterministic=true ∧ is_multi=(pi==1.0))`;
  `0<pi<1 ⇒ (u∈(0,1) ∧ deterministic=false ∧ is_multi=(u<pi))`.
* [ ] **Schema conformance:** every event JSONL line **validates** against `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.  ← **added**

## 10.3 RNG trace (cumulative)

* [ ] **Granularity:** cumulative rows per `(module="1A.hurdle_sampler", substream_label="hurdle_bernoulli")` within `{seed, parameter_hash, run_id}` (no merchant dimension).
* [ ] **Embed/path equality (trace):** embedded `seed` and `run_id` match path keys; **`parameter_hash` is path-only**.
* [ ] **Totals progression:** after each emission, the appended line updates **saturating** `events_total`, `blocks_total`, `draws_total` and includes the matching before/after counter words.
* [ ] **Reconciliation:** final `blocks_total` equals the unsigned counter delta across all emitted events; final `draws_total` equals the saturating sum of `draws` over all events; `events_total == |M|`.
* [ ] **Ordering:** event write precedes trace append for each merchant; if the event write fails, **no** trace append is attempted.

## 10.4 Orchestrator & state behavior

* [ ] **Deterministic loop order:** merchants processed in ascending `merchant_id`.
* [ ] **Serialized emission:** **S1.4** is not run in parallel; exactly one call → one event line → one trace line.
* [ ] **Loop-level delta checks executed:** `events_total` +1, `blocks_total` + `decision.blocks`,`draws_total` + `u128_to_uint64_or_abort(decimal_string_to_u128(decision.draws))` after each S1.4.
* [ ] **Typed handoff:** S1.4 returns `EmittedHurdle`; S1.5 consumes it directly (no ad-hoc reconstruction).
* [ ] **Handoff correctness:** for each merchant, $\Xi_m=(\text{is_multi},N,K,\mathcal C,C^\star)$ is produced; `C*` is the **post** hurdle counter (audit-only); next_state is `SingleHomePlacement` (formerly S7) iff single-site else `NegativeBinomialS2` (formerly S2).

## 10.5 Replay & invariance smoke tests (recommended)

* [ ] **Rerun invariance:** two runs with identical `{seed, parameter_hash, manifest_fingerprint, run_id}` and the same inputs produce byte-identical hurdle rows and trace (order included).
* [ ] **Order invariance of RNG:** swapping merchant processing order (in a controlled test) **does not** change any `pi`, `u`, `is_multi`, or counters per merchant (only file append order).
* [ ] **Fixture replay:** for a seeded, tiny fixture (e.g., `|M|=3`), recomputing `η, π` offline yields the same `π`; for stochastic rows (`draws="1"`), regenerated `u` equals the persisted `u` under the same substream base counter.

---

# 11) What we intentionally did **not** add

The following were **deliberately excluded** to keep L2 lean, deterministic, and aligned with the spec:

* **No parallel emission:** S1.4 (event write + cumulative trace) is the **only** serialization point and is not parallelized. (Avoids reducers/locks and preserves trivial reconciliation.)
* **No retries/backoffs/compensation:** All failures abort immediately; no best-effort re-writes, no auto healing, no “skip and continue” mode.
* **No schema drift:** We did not add optional/extra fields to event or trace rows; only the schema-declared fields are written.
* **No path variations:** We did not place `fingerprint`, `module`, or `substream_label` in paths; partitions are **exactly** `{seed, parameter_hash, run_id}` for events and `{seed, parameter_hash, run_id}` for trace.
* **No counter chaining:** We do not propagate hurdle counters downstream; `C*` is audit-only in the handoff; downstream states derive their own substreams from their own labels.
* **No per-event trace:** Trace is cumulative per substream; there’s no per-event trace dataset.
* **No alternate numeric/RNG modes:** We did not introduce fast-math, FMA, FTZ/DAZ, different PRNGs, or different lane policies. S1 relies on S0’s attested binary64 profile and uses the low-lane, open-interval uniform.
* **No writer mutations:** No delete/overwrite of shards, no compaction, no re-ordering; writers are append-only (atomic line appends or temp-then-rename).
* **No additional artefacts or toggles:** Beyond the governed β and the S0-materialized $x_m$, L2 introduces no new artefacts, flags, or config switches.
* **No downstream orchestration:** L2 does not enumerate or trigger later 1A RNG streams; presence of those is validated elsewhere and gated by `is_multi`.
* **No validation bundle here:** L2 for State-1 does not assemble a validation bundle; that’s handled in the validator layer (S1.V/L3) for this state.

These exclusions are intentional: they prevent over-engineering, reduce surface area for bugs, and ensure validators can reason about outputs with simple, deterministic rules.

---

# Appendix A — Error → Class mapping (operational taxonomy)

| Error code                            | Class                 | Owner / where raised | Typical cause                                                   | Retry |
|---------------------------------------|-----------------------|----------------------|-----------------------------------------------------------------|-------|
| `E_S1_RNG_AUDIT_MISSING`              | `S1.PRECONDITION`     | L2 gate              | Audit row absent                                                | No    |
| `E_S1_DUPLICATE_MERCHANT_IN_UNIVERSE` | `S1.PRECONDITION`     | L2 pre-loop          | Duplicate IDs in `M`                                            | No    |
| `E_S1_HOME_ISO_INVALID`               | `S1.PRECONDITION`     | L2 pre-loop          | Missing/invalid ISO                                             | No    |
| `E_S1_DUPLICATE_MERCHANT_RUNTIME`     | `S1.PRECONDITION`     | L2 in-loop           | Same merchant twice                                             | No    |
| `E_S1_INPUT_MISSING_XM`               | `S1.INPUT`            | S1.1                 | Missing design vector                                           | No    |
| `E_S1_DSGN_SHAPE_MISMATCH`            | `S1.DESIGN.ALIGNMENT` | S1.1                 | `β ≠ dim(x_m)`                                                  | No    |
| `E_S1_NUMERIC_NONFINITE_ETA`          | `S1.NUMERIC`          | S1.2                 | Non-finite `η`                                                  | No    |
| `E_S1_PI_OOB`                         | `S1.NUMERIC`          | S1.2                 | `π∉[0,1]`                                                       | No    |
| `E_S1_U_OOB`                          | `S1.RNG.BOUNDARY`     | S1.3                 | `u∉(0,1)`                                                       | No    |
| `E_S1_DTRM_INCONSISTENT`              | `S1.RNG.CONSISTENCY`  | S1.3/1.4             | Deterministic branch mismatch                                   | No    |
| `E_S1_BLOCKS_MISMATCH`                | `S1.BUDGET.IDENTITY`  | S1.4                 | `blocks≠u128_to_uint64_or_abort(decimal_string_to_u128(draws))` | No    |
| `E_S1_BUDGET_IDENTITY`                | `S1.BUDGET.IDENTITY`  | S1.4                 | `after−before≠decimal_string_to_u128(draws)`                    | No    |
| `E_S1_EVENT_DUPLICATE`                | `IO.WRITE.DUPLICATE`  | S1.4 writer          | 2nd emit for same key                                           | No    |
| `E_IO_EVENT_WRITE`                    | `IO.WRITE.FAIL`       | S1.4 writer          | Append/rename failed                                            | No    |
| `E_IO_TRACE_WRITE`                    | `IO.WRITE.FAIL`       | S1.4 writer          | Trace append failed                                             | No    |
| `E_S1_INPUT_EVENT_KIND_MISMATCH`      | `S1.PRECONDITION`     | S1.5                 | Not a hurdle event                                              | No    |

---

# Appendix B — Canonical JSONL examples

## B.1 Deterministic row (`π=1.0`, no draw)

```json
{"envelope":{"ts_utc":"2025-08-30T12:34:56.123456Z","module":"1A.hurdle_sampler","substream_label":"hurdle_bernoulli","seed":12345,"parameter_hash":"ab…cd","manifest_fingerprint":"ff…01","run_id":"de…ad","rng_counter_before_lo":100,"rng_counter_before_hi":0,"rng_counter_after_lo":100,"rng_counter_after_hi":0,"draws":"0","blocks":0},"payload":{"merchant_id":9001,"pi":1.0,"is_multi":true,"deterministic":true,"u":null}}
```

* `draws:"0"`, `blocks:0`, counters unchanged; `is_multi=true` because `π==1.0`; `u:null`.

## B.2 Stochastic row (`0<π<1`, one draw)

```json
{"envelope":{"ts_utc":"2025-08-30T12:34:57.000001Z","module":"1A.hurdle_sampler","substream_label":"hurdle_bernoulli","seed":12345,"parameter_hash":"ab…cd","manifest_fingerprint":"ff…01","run_id":"de…ad","rng_counter_before_lo":101,"rng_counter_before_hi":0,"rng_counter_after_lo":102,"rng_counter_after_hi":0,"draws":"1","blocks":1},"payload":{"merchant_id":9002,"pi":0.34285714285714286,"is_multi":true,"deterministic":false,"u":0.12345678901234568}}
```

* `draws:"1"`, `blocks:1`, `after = before + 1`; `u∈(0,1)` and `is_multi = (u<π)`.

## B.3 Trace cumulative line (after example B.2)

```json
{"ts_utc":"2025-08-30T12:34:57.000010Z","module":"1A.hurdle_sampler","substream_label":"hurdle_bernoulli","seed":12345,"parameter_hash":"ab…cd","run_id":"de…ad","rng_counter_before_lo":101,"rng_counter_before_hi":0,"rng_counter_after_lo":102,"rng_counter_after_hi":0,"events_total":2,"blocks_total":1,"draws_total":1}
```

* Cumulative per (module, substream). Totals are **saturating u64**.

*(Counters and `seed` are JSON integers; `run_id`/`parameter_hash`/`manifest_fingerprint` are hex strings; `pi`/`u` are round-trip binary64 numbers; `ts_utc` has exactly 6 fractional digits.)*

---

# Appendix C — Tiny fixture harness (recommended)

```pseudocode
# Fixture: three merchants, deterministic order
seed=12345; parameter_hash="ab…cd"; manifest_fingerprint="ff…01"; run_id="de…ad"
M=[9001,9002,9003]; home_iso_of={9001:"GB",9002:"US",9003:"DE"}

(handoffs, totals) = run_S1(seed, parameter_hash, manifest_fingerprint, run_id, M, home_iso_of)

# Acceptance asserts (subset)
assert totals.events_total == 3
assert dataset_cardinality("rng_event_hurdle_bernoulli", seed, parameter_hash, run_id) == 3
for m in M: assert exists_event_row(m)
replay_row = read_event_row(merchant_id=9002)
if replay_row.payload.deterministic == false:
    u_recomputed = replay_uniform_from_counter(replay_row.envelope.rng_counter_before_hi,
                                               replay_row.envelope.rng_counter_before_lo)
    assert nearly_equal(u_recomputed, replay_row.payload.u)
```

---