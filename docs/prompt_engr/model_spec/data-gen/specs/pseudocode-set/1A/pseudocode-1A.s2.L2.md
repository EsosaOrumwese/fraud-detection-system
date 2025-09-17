# S2·L2 — Orchestrator (Merchant NB Count)

## 1) Purpose & Non-Goals

**Purpose.** Orchestrate State-2 by wiring the frozen **L1 kernels (S2.1→S2.5)** with the correct ordering, gates, safe parallel windows, lineage availability, and persistence scopes—using only the approved L0/L1 surfaces. L2 itself does not compute model math or write evidence directly; emits happen inside L1 via L0’s writer/trace with dictionary-resolved paths.

**Non-Goals.** No new algorithms or helpers; no schema/dictionary changes; no path literals; no validators/corridors (L3 territory); no alternate numeric/RNG policy; no per-event extra trace rows; never serialize numbers as strings; never put `module`, `substream_label`, or `manifest_fingerprint` in paths. **L2 never writes evidence or trace; L1+L0 writer do.**

---

## 2) Contract (inputs → outputs → side-effects)

**Inputs (closed set).**
* **Run lineage:** `{seed, parameter_hash, manifest_fingerprint, run_id}` (present before orchestration).
* **Merchant workset:** unique merchants **gated by S1 hurdle** (`rng_event_hurdle_bernoulli` with `is_multi==true`).
* **NB inputs:** design vectors `x_mu,x_phi` (frozen shapes) and governed coefficients `β_mu,β_phi` (shape-aligned).

**Outputs (append-only evidence).**
* RNG event families under dictionary partitions **`{seed, parameter_hash, run_id}`**:
  - `rng_event_gamma_component`
  - `rng_event_poisson_component`
  - **Exactly one** `rng_event_nb_final` per merchant
  (IDs & partitions are dictionary-approved; presence is gated by the hurdle. **No path strings in L2**—writers resolve paths.)

**Side-effects (trace discipline).**
After each event row is persisted, the **L1/L0 writer** appends the **saturating** RNG trace row; if the writer’s trace append fails, L2 treats it as terminal and routes to the abort path (the already-written event row remains for validators).

---

## 3) Authorities & Contracts (symbolic only)

**Labels / modules (closed set; referenced symbolically).**
`gamma_nb / 1A.nb_and_dirichlet_sampler`, `poisson_nb / 1A.nb_poisson_component`, `nb_final / 1A.nb_sampler`. (Pinned in S2·L0 §3; do not hand-type elsewhere.)

**Schemas (authoritative).**
`schemas.layer1.yaml#/rng/events/gamma_component`, `schemas.layer1.yaml#/rng/events/poisson_component`, `schemas.layer1.yaml#/rng/events/nb_final`. Payload number fields are JSON **numbers**, not strings.

**Dictionary partitions & gating.**
All three **event** families are partitioned by **`["seed","parameter_hash","run_id"]`** and **gated** by the hurdle (`is_multi==true`). **Trace** rows live under the same partitions but **embed only** `{seed, run_id}` (the `parameter_hash` is path-only). L2 never embeds path strings; writers resolve paths from the dictionary.

**Path ↔ embed equality (enforced).**
Event path partitions must equal the embedded envelope fields `{seed, parameter_hash, run_id}`; `manifest_fingerprint` is **embedded-only** (not a path partition). Any violation is terminal.

**Finaliser contract.**
`nb_final` is **non-consuming** (`before==after`, `blocks=0`, `draws:"0"`), and it **echoes** `mu` and `dispersion_k` bit-for-bit from S2.2. L2 ensures it **invokes S2.5 at most once** per merchant/run (**resume-safe**: skip if already present); L1 emits and the writer/trace prove non-consumption.

---

## 4) Inputs & Host Shims (read-only)

**What L2 receives (inputs):**

* **Run lineage:** `{seed, parameter_hash, manifest_fingerprint, run_id}` (fixed for the run; present before S2).
* **Merchant workset:** unique merchants **gated by S1 hurdle** (`rng_event_hurdle_bernoulli` with `is_multi==true`), discovered via the dictionary’s gating blocks.
* **NB inputs:** design vectors `x_mu, x_phi` (frozen shapes) and governed coefficients `β_mu, β_phi` (shape-aligned), as consumed by S2·L1.

**What L2 may read (host shims; no writes, policy-free):**

* **Dictionary / registry resolvers** to obtain **dataset IDs** and confirm **partitions** for the three S2 RNG families under `{seed, parameter_hash, run_id}`. L2 never assembles path strings; the writer resolves paths.
* **Existence/uniqueness checks** (idempotent resume hygiene):
  `rng_audit_exists(seed, parameter_hash, run_id)`;
  `hurdle_is_unique(merchant_id, lineage)`;
  `nb_final_exists(merchant_id, lineage)` → if true, **skip** merchant (resume-safe; do not emit).
* **Read-only** lookups for schema refs / labels / modules (`gamma_nb`, `poisson_nb`, `nb_final`) used **symbolically** by L1 emitters via L0; L2 never hard-codes these.

**What L2 never does:** re-implement writers, samplers, numeric policy, or schemas; **emit events** or trace rows directly; open or mutate governance artefacts late (S0 L2 pattern).

---

## 5) Pre-Run Gates (must pass before orchestration)

1. **RNG audit present (and first).**
   A **single** audit row exists for this `{seed, parameter_hash, run_id}` **before any S2 emission**. Absence → terminal (route to abort). L2 does not write the audit; it only checks presence.

2. **Hurdle uniqueness & presence-gate.**
   Exactly **one** hurdle row per merchant for the run; **only** merchants with `is_multi==true` enter S2. Downstream NB families are presence-gated in the dictionary (`gating.gated_by=="rng_event_hurdle_bernoulli"`).

3. **Numeric profile inherited.**
   Binary64, RNE, **FMA-OFF**, fixed evaluation order—**attested upstream**. L2 does not alter numeric configuration and must not introduce mixed-precision paths.

4. **Partitions & path↔embed equality.**
   Event paths are partitioned **exactly** by `{seed, parameter_hash, run_id}` and the envelope embeds the **same** values. `manifest_fingerprint` is **embedded-only** (never a path partition). **Trace** rows use the same partitions but **embed only** `{seed, run_id}` (the `parameter_hash` is path-only). Any mismatch is terminal (route to abort).

5. **Family bindings & non-consuming finaliser.**
   L1 emitters must target the approved S2 families and schema anchors; `nb_final` is **non-consuming** (`before==after`, `blocks=0`, `draws:"0"`) and **echoes** `{mu, dispersion_k}` bit-for-bit. L2 enforces **“≤ 1 finaliser per merchant/run”** (resume-safe: **skip** merchant if `nb_final` already exists).

---

## 6) Concurrency Model & Ordering

**Unit of work = one merchant.** L2 may run **many merchants in parallel**, but each merchant’s work is **fully serialised** in the exact S2 order **S2.1 → S2.2 → (S2.3/S2.4 loop) → S2.5**. Within that unit, **each event write followed by its single trace append (done by the L1/L0 writer)** is a hard serialization point. L2 never writes evidence or trace.

### 6.1 Across-merchant concurrency (allowed)

* You may shard the **gated merchant set** (those with `is_multi==true`) across threads/workers.
* The **iteration order and join/flush order** of merchants must be deterministic (e.g., ascending `merchant_id`, then publish in that order). Evidence determinism does **not** depend on log order (substreams are keyed), but deterministic joins keep operational output reproducible.

### 6.2 Within-merchant ordering (strict)

* **Barrier order:**

  1. **S2.1 Load & Guard** (no RNG, no writes)
  2. **S2.2 Links → Parameters** (deterministic, no writes)
  3. **Loop:** **S2.3 Attempt** (**emit only if** `λ>0` and finite; order **Gamma → Poisson**) then **S2.4 Accept** (deterministic check) until first `K≥2`
  4. **S2.5 Finalise** (emit **one** `nb_final`, non-consuming)
* **Per attempt (valid):** exactly **two** events, **in order**
  **Γ step** → write `gamma_component` → writer **immediately** appends trace →
  **Π step** → write `poisson_component` → writer **immediately** appends trace.
* **λ-invalid attempt:** **emit no S2 events** (no Gamma, no Poisson), signal the numeric error, and **stop** S2 for that merchant (no final).
* **Finaliser:** write `nb_final` (non-consuming) → writer **immediately** appends trace.
  All evidence I/O (event + trace) is performed by L1 emitters via L0’s writer/trace.

### 6.3 Serialization points & trace discipline

* Each **event write** is immediately followed by **one** cumulative trace append (saturating totals). The pair *(event, trace)* forms a **hard serialization point**; do not reorder, merge, or batch these.
* If the writer’s trace append fails **after** a successful event write, treat as **terminal** for the merchant/run per failure policy and route to the canonical abort; the written event row remains for validators.

### 6.4 Gating & idempotence enforcement

* **Presence gate:** run S2 only for merchants whose hurdle shows `is_multi==true`.
* **At-most-one finaliser:** if an `nb_final` already exists for `(seed, parameter_hash, run_id, merchant)`, **skip** that merchant (resume-safe).
* **No partial backfill:** if component events exist **without** a finaliser for a merchant/run, L2 **must not** emit additional components to “fill gaps.” Route to the canonical failure path (or let the host re-run clean). This avoids duplicate evidence and counter drift.

### 6.5 Substreams & counter hygiene

* Substreams are **per family** (`gamma_nb`, `poisson_nb`, `nb_final`); **never** chain counters across labels.
* Determinism does **not** rely on wall-clock or file order: keyed substreams and counters guarantee replay. L2 must still maintain **Gamma → Poisson** emission order within each **valid** attempt.

### 6.6 Scheduling & resource hints (host-agnostic)

* Parallelism knobs (threads, batches) are **host** concerns; L2’s logic and outcomes are invariant to scheduling, provided the within-merchant ordering above is respected.
* Join/flush order must be deterministic (e.g., stable sorting of merchant chunks before commit), even though evidence determinism does not depend on it.

### 6.7 Acceptance for §6

* Parallel **across** merchants is allowed; **within** a merchant the order **S2.1→S2.2→(S2.3/S2.4)\*→S2.5** is enforced.
* Every **valid** attempt produces **exactly two** events **in Γ→Π order**, each immediately followed by a **single** writer-driven trace append. For a λ-invalid case, **no S2 events are emitted** and the merchant is stopped.
* Exactly **one** `nb_final` is ever written per merchant/run; merchants with an existing finaliser are **skipped**; partial component-only merchants are **not** backfilled by L2.
* No cross-label counter chaining; no batching/reordering of *(event→trace)* pairs; **no path literals** in L2.

---

## 7) Main Orchestrator (high-level control flow)

> **Goal:** enumerate **gated** merchants and, for each, drive **S2.1 → S2.2 → (S2.3/S2.4 loop) → S2.5** in order. L2 itself never writes events—L1 emitters (via L0 writer/trace) do that. No path literals; all dataset IDs/paths resolve via the dictionary.

### 7.1 Inputs/Outputs (at a glance)

* **Inputs:** lineage `{seed, parameter_hash, manifest_fingerprint, run_id}`; **gated workset** of merchants (from S1 hurdle with `is_multi==true`); access to design vectors `x_mu,x_phi` and governed coefficients `β_mu,β_phi` per merchant (read-only).
* **Outputs:** per-merchant in-memory handoff `{N, r}` (accepted outlets `N≥2`; rejection count `r≥0`). Evidence (Gamma/Poisson components + one `nb_final`) is produced by **L1** under dictionary partitions.

### 7.2 Pseudocode (code-agnostic; orchestration only)

```pseudocode
function orchestrate_S2(lineage, merchant_iter, nb_inputs_provider, host_opts) -> Iterator[Result]
  # lineage = { seed, parameter_hash, manifest_fingerprint, run_id }
  # merchant_iter yields merchant_id in deterministic order (e.g., ascending)
  # nb_inputs_provider(m) -> { x_mu, x_phi, beta_mu, beta_phi } (read-only handles)
  # host_opts carries parallelism hints only (threads, batches); L2 logic invariant to it

  # --- Pre-run gates (fail fast) ---
  require rng_audit_exists(lineage)                                  # gate 1
  hurdle_index = build_hurdle_index(lineage)                         # map merchant_id -> is_multi
  require hurdle_index.is_unique_per_merchant()                      # gate 2

  # --- Build gated workset (presence-gated by hurdle) ---
  workset = [m for m in merchant_iter if hurdle_index[m] == true]

  # --- Across-merchant parallel window (host-managed) ---
  for merchant_id in workset:

    # Idempotent resume: skip if finaliser already present for this run/merchant
    if nb_final_exists(merchant_id, lineage):
        yield Result.skip(merchant_id, reason="finaliser_exists")
        continue

    # Fetch deterministic NB inputs (read-only)
    inputs = nb_inputs_provider(merchant_id)                         # {x_mu, x_phi, beta_mu, beta_phi}

    # S2.1 Load & Guard (no RNG, no writes)
    ctx_or_error = S2_1_load_and_guard(merchant_id, lineage, inputs)
    if ctx_or_error.is_error():
        yield Result.fail(merchant_id, ctx_or_error.signal)          # L2 routes to Batch-F as policy dictates
        continue
    ctx = ctx_or_error.value

    # Initialise per-family substreams & trace totals (L0; no writes)
    # Derive run master from seed + raw 32 bytes of manifest_fingerprint (not the hex text)
    M = derive_master_material(lineage.seed, hex64_to_raw32(lineage.manifest_fingerprint))
    # Use a typed Ids tuple; merchant_u64 is the canonical key from S0
    ids = [ { tag:"merchant_u64", value: merchant_u64_from_id64(merchant_id) } ]
    s_gamma = derive_substream(M, label="gamma_nb",  ids)
    s_pois  = derive_substream(M, label="poisson_nb",ids)
    s_final = derive_substream(M, label="nb_final",  ids)

    totals_gamma = TraceTotals{draws_total:0, blocks_total:0, events_total:0}
    totals_pois  = TraceTotals{draws_total:0, blocks_total:0, events_total:0}
    totals_final = TraceTotals{draws_total:0, blocks_total:0, events_total:0}

    # S2.2 Links → Parameters (no RNG, no writes)
    ctx_or_error = S2_2_links_to_params(ctx)
    if ctx_or_error.is_error():
        yield Result.fail(merchant_id, ctx_or_error.signal)
        continue
    ctx = ctx_or_error.value

    # S2.3/S2.4 loop — emit-as-you-go Gamma→Poisson attempts until accept (K≥2)
    rejections = 0
    while true:
        attempt = S2_3_attempt_once(ctx, s_gamma, totals_gamma, s_pois, totals_pois)
        if attempt.is_error():
            # e.g., λ invalid (**no S2 events emitted**). Stop for this merchant.
            yield Result.fail(merchant_id, attempt.signal)
            break

        (G, lambda, K,
         s_gamma, totals_gamma,
         s_pois,  totals_pois) = attempt.value

        if K >= 2:
            # S2.5 Finalise (non-consuming) — emits one nb_final; updates totals_final
            handoff, totals_final =
                S2_5_finalise(ctx,
                              N=K, r=rejections,
                              s_final=s_final, totals_final=totals_final)
            yield Result.ok(merchant_id, handoff)                    # {N, r}
            break
        else:
            rejections += 1
            continue
```

### 7.3 Notes (determinism, idempotence, evidence discipline)

* **Within-merchant ordering is strict:** S2.1 → S2.2 → (S2.3/S2.4)\* → S2.5. Each **valid** attempt produces **exactly two** events in order (**Gamma → Poisson**), each immediately followed by a **single** saturating trace append (performed inside L1 via L0).
* **λ-invalid:** **emit no S2 events** for that merchant (no Gamma, no Poisson, no final) and stop S2 for that merchant; surface the signal.
* **Idempotent resume:** merchants with an existing `nb_final` for `(seed, parameter_hash, run_id)` are **skipped**. L2 **must not** “backfill” additional component events for partial merchants; route to the canonical failure path instead.
* **No cross-label counter chaining:** substreams are per family (`gamma_nb`, `poisson_nb`, `nb_final`); replay does not rely on wall-clock or file order—only counters and keyed substreams.
* **L2 never writes evidence:** all writes occur in L1 using L0’s writer; L2 only calls kernels and processes signals.

### 7.4 Failure propagation hooks (signals → aborts)

* On `ERR_S2_INPUTS_INCOMPLETE`, `ERR_S2_NUMERIC_INVALID`, or gating-breach signals from L1, **stop** S2 for that merchant.
* If policy requires a run-scoped abort (e.g., structural partition or path↔embed violation detected upstream), L2 calls the Batch-F **abort\_run/abort\_run\_atomic** with the canonical payload; L2 does **not** invent new failure shapes.
* Partial merchants (components without final) are handled per policy (usually terminal → abort), not “filled in” by L2.

### 7.5 Acceptance for §7

* Per merchant, the orchestrator executes **exactly** S2.1 → S2.2 → (S2.3/S2.4)\* → S2.5 in order.
* Each **valid** attempt yields **Gamma → Poisson** events (and trace) immediately; **one** `nb_final` per merchant/run is emitted (non-consuming).
* Merchants with an existing `nb_final` are **skipped**; no partial backfill; no path literals; no helper re-definitions; no validator logic inside L2.

---

## 8) DAGs (Per-merchant and Run-level)

### 8.1 — Per-merchant DAG (one merchant `m`)

```
[Fixed for run]   seed, parameter_hash, manifest_fingerprint, run_id
[Per-merchant]    merchant_id = m, x_mu(m), x_phi(m), β_mu, β_phi

Gate-A: rng_audit_log exists for {seed, parameter_hash, run_id}
Gate-B: hurdle for m is present & unique, with is_multi == true
    │
    ▼
S2.1(m): Load & Guard                    # no RNG, no writes
    inputs:  x_mu, x_phi, β_mu, β_phi, lineage
    outputs: ctx_m
    │
    ▼
S2.2(m): Links → Parameters              # no RNG, no writes
    inputs:  ctx_m
    outputs: ctx_m + { mu>0, phi>0 }
    │
    ▼
(loop t = 0,1,2, …)  Attempt t
    │
    ├─► Capsule: draw G_t (no emission yet)              # S2.3
    │     outputs:  G_t, updated {s_gamma, totals_gamma} (budgets tracked, no rows written)
    │
    ├─► Compose λ_t = (mu / phi) * G_t                  # binary64, fixed order
    │     guard: if λ_t ≤ 0 or non-finite → signal numeric invalid,
    │            **emit no S2 events** and STOP S2 for merchant m (no S2.4 / no S2.5)
    │
    ├─► Γ step (label "gamma_nb")                        # S2.3 (valid λ only)
    │     side-effects:
    │       • emit 1 row to rng_event_gamma_component (authoritative envelope)
    │       • append 1 row to rng_trace_log (cumulative, saturating)
    │
    ├─► Π step (label "poisson_nb")                     # S2.3 (valid λ only)
    │     side-effects:
    │       • emit 1 row to rng_event_poisson_component (authoritative envelope)
    │       • append 1 row to rng_trace_log (cumulative, saturating)
    │     outputs:  K_t, updated {s_pois, totals_pois}
    │
    └─► Accept?  if (K_t ≥ 2) then
           │
           ▼
        S2.5(m): Finalise (label "nb_final")            # non-consuming event
           side-effects:
             • emit 1 row to rng_event_nb_final (before==after; blocks=0; draws="0")
             • append 1 row to rng_trace_log (events_total +1; draws_total unchanged)
           outputs: handoff_m = { N := K_t, r := t }
        (end)
         else
           t := t + 1  and repeat Attempt
```

**Edge invariants (enforced by writers/validators):**

* **Per valid attempt:** exactly **two** component events in order **Γ → Π**, each immediately followed by **one** trace append.
  If λ is invalid (≤0 or non-finite): **no events** are emitted (no Gamma, no Poisson) and the merchant **stops** (no final).
* **Partitions & equality:** all RNG **event** families are written under `{seed, parameter_hash, run_id}` with **path↔embed equality**; **trace** rows embed only `{seed, run_id}` (`parameter_hash` is path-only).
* **Budgets vs counters:** `blocks = u128(after) − u128(before)` (counters) and `draws =` **actual uniforms consumed** (decimal u128) are **independent** checks—never inferred from one another.
* **Finaliser:** `nb_final` is **non-consuming** and **echoes** `{ mu, dispersion_k := phi }` **bit-for-bit**; at most **one** finaliser per `(run, merchant)`.

---

### 8.2 — Run-level DAG (whole State-2)

```
                           ┌─────────────────────────────────────────────┐
                           │ Fixed run inputs:                           │
                           │   seed, parameter_hash, manifest_fingerprint│
                           │   run_id, governed coefficients (β_μ, β_φ)  │
                           └─────────────────────────────────────────────┘
                                        │
Gate-0: rng_audit_log exists            │
Gate-1: hurdle index built & unique     ▼
Gate-2: presence gate ⇒ M* = { m | is_multi(m) == true }
                                        │
          ┌────────────────── Parallel across m ∈ M* ───────────────────┐
          │                                                             │
          ▼                                                             ▼
  Per-merchant DAG(m₁) …                                       Per-merchant DAG(m_k)
          │                                                             │
          └───────────────────────────────┬─────────────────────────────┘
                                          ▼
                                        Done
```

**Run-level rules:**

* **Idempotent resume:** if `nb_final` already exists for `(seed, parameter_hash, run_id, m)`, **skip** merchant `m`. **Do not** backfill partial component attempts—route to the canonical failure path or re-run clean.
* **No cross-label counter chaining;** determinism does not rely on wall-clock/file order (keyed substreams + counters guarantee replay).
* L2 **never** writes evidence; all emits occur in L1 via L0’s writer/trace (**dictionary-resolved IDs**).
* Per-merchant design vectors (`x_mu,x_phi`) are loaded at merchant scope; governed coefficients are fixed for the run via `parameter_hash`.

---

## 9) Attempt & Acceptance Delegation

**What lives where.**

* **L1 owns the attempt and emissions.** A single call to `S2_3_attempt_once(...)` **emits-as-it-goes** component events using L0 emitters and immediately appends the **saturating** trace after each event. **Per valid attempt**, this is exactly two events in order (**Gamma → Poisson**).
* **L2 only loops and decides acceptance.** L2 never batches/buffers events, never computes sampler math, and never writes evidence directly.

**Per-attempt contract (from L1).**

* **Draw $G$ (capsule, no emission yet)** inside L1.
* Compute and **guard** $\lambda = (\mu/\phi)\,G$ in fixed binary64 order.
* **If λ is valid:** emit **Gamma** then **Poisson** (each immediately followed by a single trace append).
* **If λ is non-finite or ≤0:** **emit no S2 events** for that merchant (no Gamma, no Poisson, no final) and stop S2 for that merchant.
* Returns `(G, λ, K)` plus updated per-family substreams/totals **or** a **signal** (e.g., λ-invalid: **no S2 events emitted**).

**Acceptance rule (deterministic).**

* **Accept first `K ≥ 2`**, set `N := K`, `r := #rejections` (count of `K ∈ {0,1}` seen).
* **Reject** if `K ∈ {0,1}` and loop again (no hidden caps; corridor checks live in validation).
* On **numeric-invalid λ** (**no S2 events emitted**), **stop** S2 for that merchant and route the signal to failure handling (L2/L3 policy).

**What L2 must not do.**

* Do **not** re-emit, reorder, or batch component events.
* Do **not** infer `draws` from counters or touch envelopes; L1/L0 already enforce `blocks = after−before` and `draws = actual uniforms`.
* Do **not** “fill in” partial merchants (components without final); treat per policy (usually terminal → abort), not backfill.

### 9.1 Orchestration loop (code-agnostic)

```pseudocode
# Called inside §7 Main Orchestrator per merchant after S2.2 computed (mu, phi)
rejections := 0
while true:
    attempt = S2_3_attempt_once(ctx, s_gamma, totals_gamma, s_pois, totals_pois)
    if attempt.is_error():
        # e.g., ERR_S2_NUMERIC_INVALID for lambda (no S2 events emitted)
        signal = attempt.signal
        return Result.fail(merchant_id, signal)   # L2 routes to Batch-F as policy dictates

    (G, lambda, K,
     s_gamma, totals_gamma,
     s_pois,  totals_pois) = attempt.value

    if K >= 2:
        # Single non-consuming finaliser; echoes (mu, phi) bit-for-bit
        handoff, totals_final = S2_5_finalise(
                                  ctx,
                                  N = K,
                                  r = rejections,
                                  s_final = s_final,
                                  totals_final = totals_final
                                )
        return Result.ok(merchant_id, handoff)    # {N, r}
    else:
        rejections += 1
        continue
```

**Ordering & evidence discipline (L2 enforces).**

* Within each **valid** attempt, **Gamma → Poisson** order is preserved; each event is immediately followed by **one** trace append (performed by L1 via L0).
* Substreams are **per family** (`gamma_nb`, `poisson_nb`, `nb_final`); **no cross-label counter chaining**.
* Finaliser is emitted **once** (non-consuming: `before==after`, `blocks=0`, `draws:"0"`), echoing `mu/phi` bit-for-bit.

**Idempotence & resume.**

* If an `nb_final` already exists for `(seed, parameter_hash, run_id, merchant)`, L2 **skips** the merchant (no partial backfill).
* If component events exist without a finaliser, L2 does **not** produce more components to “complete” an attempt; route to failure handling per policy.

---

## 10) Gating, Idempotence & Resume

**Presence-gate (entry).**
A merchant enters S2 **iff** its S1 hurdle event exists, is **unique**, and `is_multi == true`. L2 must not orchestrate S2 for any merchant failing this gate.

**Idempotence keys.**
All S2 RNG **event** families are partitioned by `{seed, parameter_hash, run_id}`. Those three values **plus** `merchant_id` define the idempotence scope for “exactly one finaliser”:

* **At-most-one finaliser:** per `(seed, parameter_hash, run_id, merchant_id)`, there must be **≤ 1** `nb_final`.
* **Skip-if-final:** if a finaliser already exists for the merchant/run, L2 **skips** that merchant entirely (no more component attempts are allowed).

**Branch purity.**
NB component/final streams must **not** appear for merchants without the hurdle gate (`is_multi == true`). Any such row is a **terminal** branch-purity violation (route to abort).

**Path↔embed discipline (gate on write).**
For any S2 **event**, the path partitions must equal the envelope’s `{seed, parameter_hash, run_id}`; `manifest_fingerprint` is **embedded-only** (never a path partition).
For **trace** rows, partitions are the same but the **embed set is `{seed, run_id}` only** (`parameter_hash` is path-only). Any mismatch is terminal.

**Resume semantics (crash / re-run).**

* **Finaliser present:** skip the merchant (`Result.skip(finaliser_exists)`). Evidence for that merchant is complete.
* **Components present, no finaliser:** do **not** “backfill” additional attempts. Treat as **terminal** per policy (usually run-abort via Batch-F) so the run can re-start clean. This avoids duplicated/interleaved attempts and keeps counters/trace coherent.
* **No S2 evidence yet:** proceed normally.

**No duplicate attempts.**
Within a merchant, attempts are **serial** and, for a **valid attempt**, produce **exactly two** events in order (**Gamma → Poisson**). L2 must not repeat or parallelise attempts for the same merchant; each **event write** is immediately followed by a **single** writer-driven trace append.

**No cross-label counter chaining.**
Substreams are per family (`gamma_nb`, `poisson_nb`, `nb_final`). L2 must never chain counters across labels or rely on wall-clock/file order for determinism.

**Minimal guards (code-agnostic).**

```pseudocode
def gated(merchant_id, lineage) -> bool:
    h = lookup_hurdle(merchant_id, lineage)
    return h.exists and h.unique and (h.payload.is_multi == true)

def should_skip(merchant_id, lineage) -> bool:
    return nb_final_exists(merchant_id, lineage)

# Entry check per merchant:
require gated(merchant_id, lineage)
if should_skip(merchant_id, lineage):
    yield Result.skip(merchant_id, "finaliser_exists"); continue

# Mid-run detection (partial components):
if components_exist_without_finaliser(merchant_id, lineage):
    yield Result.fail(merchant_id, "partial_components")
    route_to_abort_via_batchF()     # canonical S0.9 failure path
    continue
```

**Acceptance for §10**

* Presence-gate enforced (S2 runs only for `is_multi == true`).
* Per merchant/run: **≤ 1** `nb_final` (skip-if-final is applied); **no** attempt backfill.
* Path↔embed equality holds for events; trace embeds `{seed, run_id}` only; `parameter_hash` is not embedded; `manifest_fingerprint` is not a path partition.
* No components appear for non-gated merchants (branch purity).
* Within-merchant, attempts are serial, produce **Γ→Π** pairs **per valid attempt**, and never chain counters across labels.

---

## 11) Failure Propagation (Batch-F)

**Principle.** L2 **does not** create new failure shapes or “fix” data. It **routes** typed signals from L1 (or hard guards in L2) into the **canonical Batch-F** paths, stops S2 for the affected merchant, and—when required—commits an **atomic** run-scoped failure bundle. Evidence already written by L1 (events/trace) is left intact; L2 never backfills.

---

### 11.1 Signal → action map (minimal, complete)

| Source               | Typical signal (code)            | Scope        | When it triggers                                                 | L2 action                                                                              |
|----------------------|----------------------------------|--------------|------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| **Gate**             | `ERR_S2_GATING_VIOLATION`        | merchant     | Missing/duplicate hurdle; or `is_multi==false`                   | **Stop** merchant; **record** via Batch-F merchant log (no run abort); do not enter S2 |
| **Inputs**           | `ERR_S2_INPUTS_INCOMPLETE:{key}` | merchant     | Missing/ill-typed `x_mu/x_phi/β_mu/β_phi`                        | **Stop** merchant; **record** via Batch-F merchant log                                 |
| **Numeric**          | `ERR_S2_NUMERIC_INVALID`         | merchant     | Non-finite/≤0 `mu/phi`, or invalid `λ` (no S2 events emitted)    | **Stop** merchant; **record** via Batch-F merchant log                                 |
| **Branch purity**    | `ERR_S2_BRANCH_PURITY`           | run          | Any S2 event observed for a non-gated merchant                   | **Abort run** (atomic failure bundle)                                                  |
| **Partition/embed**  | `ERR_PARTITION_EMBED_MISMATCH`   | run          | Path partitions ≠ envelope `{seed, parameter_hash, run_id}`      | **Abort run** (atomic)                                                                 |
| **Trace discipline** | `ERR_TRACE_APPEND_FAILED`        | run          | Event written but trace append failed                            | **Abort run** (atomic)                                                                 |
| **Schema/type**      | `ERR_SCHEMA_VIOLATION`           | run          | Writer rejects row on schema/type grounds (payload/fields/shape) | **Abort run** (atomic)                                                                 |
| **Resume hygiene**   | `ERR_PARTIAL_COMPONENTS`         | run (policy) | Components exist without a finaliser                             | Treat as **terminal** per policy (route to run abort); **no backfill**                 |
| **Idempotence**      | *(not an error)*                 | —            | `nb_final` already exists for merchant/run                       | **Skip** merchant (no emissions)                                                       |

> Notes: (i) Corridor breaches (rejection-rate, p99, CUSUM) are **L3** validator failures, not L2. (ii) Merchant-scoped recordings use the Batch-F **merchant log** (no run abort). (iii) L2 never mutates evidence to “recover”.

---

### 11.2 Orchestration hooks (code-agnostic)

```pseudocode
# Called on each kernel return / guard failure
function handle_signal_or_continue(merchant_id, signal, lineage):
  match signal:
    case OK:
      return CONTINUE

    case SkipFinaliserExists:
      yield Result.skip(merchant_id, "finaliser_exists")
      return STOP_MERCHANT

    # Merchant-scoped: record to merchant log, do NOT abort the run
    case ERR_S2_INPUTS_INCOMPLETE | ERR_S2_NUMERIC_INVALID | ERR_S2_GATING_VIOLATION:
      payload = build_failure_payload(class="F-merchant", code=signal.code,
                 ctx={state:"1A.S2", module:"L2.orchestrator",
                      merchant_id, seed:lineage.seed,
                      parameter_hash:lineage.parameter_hash,
                      manifest_fingerprint:lineage.manifest_fingerprint,
                      run_id:lineage.run_id, detail:signal.detail})
      merchant_abort_log_write(rows=[payload], parameter_hash=lineage.parameter_hash)
      yield Result.fail(merchant_id, signal)
      return STOP_MERCHANT

    # Run-scoped: structural/discipline violations → atomic abort
    case ERR_PARTITION_EMBED_MISMATCH | ERR_TRACE_APPEND_FAILED |
         ERR_S2_BRANCH_PURITY | ERR_PARTIAL_COMPONENTS | ERR_SCHEMA_VIOLATION:
      payload = build_failure_payload(class="F-run", code=signal.code,
                 ctx={state:"1A.S2", module:"L2.orchestrator",
                      seed:lineage.seed, parameter_hash:lineage.parameter_hash,
                      manifest_fingerprint:lineage.manifest_fingerprint,
                      run_id:lineage.run_id, detail:signal.detail})
      abort_run_atomic(payload, partial_partitions=[])
      raise TERMINATE_RUN
```

**Rationale.** Merchant issues should not take down the whole run; structural discipline violations must. In both cases, L2 **stops further S2 work** for the affected scope and leaves already-written evidence intact.

---

### 11.3 Atomicity, idempotence, and evidence hygiene

* **Atomic commit.** Batch-F `abort_run(_atomic)` writes one canonical failure bundle + sentinel(s); re-runs with the same lineage **must not** overwrite it.
* **Idempotent resume.** Merchants with an existing `nb_final` are **skipped**; L2 never continues a partial merchant by emitting more components.
* **No retries/clamping.** Beyond the acceptance loop semantics, L2 does **not** retry, clamp, or otherwise alter values to pass gates; failures reflect reality for audit.
* **Leave evidence intact.** Any already-written component events remain for validators; L2 ensures no further S2 emissions occur for the failed merchant.

---

### 11.4 Acceptance for §11

* Every error path maps to a **single** Batch-F action (**skip merchant**, **merchant-scoped record**, or **atomic run abort**).
* No ad-hoc failure shapes are introduced; L2 never writes evidence directly nor backfills partial merchants.
* Resume semantics are deterministic: **skip-if-final**, **no backfill**, **abort on structural/discipline violations**.

---

## 12) Path/Embed & Partitions (enforcement stance)

**Single source of truth.** Paths, dataset IDs, and partitions come from the **dataset dictionary**. L2 never embeds path strings or mutates partitions; all emits happen in L1 via L0’s writer, which resolves IDs→paths and stamps the envelope.

**Partitions (RNG families).**

* `rng_event_gamma_component`, `rng_event_poisson_component`, `rng_event_nb_final`
  **Path partitions:** `{seed, parameter_hash, run_id}`
  **Envelope must embed the same trio** (`seed`, `parameter_hash`, `run_id`) — **path↔embed equality** required.
* `rng_trace_log`
  **Path partitions:** `{seed, parameter_hash, run_id}`
  **Envelope embeds only `{seed, run_id}`** (`parameter_hash` is **path-only**).

**Embed-only fields (never part of the path).**
`module`, `substream_label`, and `manifest_fingerprint` are **embedded-only** envelope fields. They must **not** appear in path partitions or directory layout.

**Writer guarantees (what L2 relies on).**

* **Event→Trace pairing:** after each event write, **exactly one** cumulative **saturating** trace row is appended.
* **Path↔embed equality checks** happen at write time; violations surface as errors.
* **Type discipline:** payload floats are JSON **numbers** (not strings); `blocks` is an integer; `draws` is a **decimal uint128 string**.

**Non-consuming finaliser.**
`nb_final` must encode **no consumption**: `before == after`, `blocks = 0`, `draws = "0"`, and echo `mu/dispersion_k` **bit-for-bit** from S2.2.

**Presence gating (branch purity).**
No S2 RNG family may appear for a merchant whose hurdle gate is absent, non-unique, or `is_multi == false`. Any such row is a terminal **branch-purity** violation (route to abort).

**Idempotence stance.**

* **At most one** `nb_final` per `(seed, parameter_hash, run_id, merchant_id)`. If present, **skip** the merchant (resume-safe).
* L2 **never backfills** component events for partial merchants; route to the canonical failure path instead.

**Operational guardrails (code-agnostic).**

```pseudocode
# invoked on any emit error surfaced from L1/L0
on_emit_error(e):
  if e.kind in { PATH_EMBED_MISMATCH, TRACE_APPEND_FAILED, BRANCH_PURITY }:
      route_to_abort_run_atomic(e.payload)     # terminal for the run
  else:
      route_to_merchant_failure(e.payload)     # stop S2 for this merchant

# pre-work checks per merchant/run
require gated(hurdle_exists_and_is_multi(merchant_id, lineage))
if nb_final_exists(merchant_id, lineage):
    skip_merchant()
```

**Acceptance for §12.**

* All S2 RNG **events** are written under `{seed, parameter_hash, run_id}` with **path↔embed equality**; **trace** rows embed `{seed, run_id}` only.
* `module`, `substream_label`, `manifest_fingerprint` remain **embed-only**.
* Floats pass as numbers; `draws` is decimal-u128; `nb_final` is provably **non-consuming**.
* Presence-gating, idempotence, and no-backfill rules are enforced at orchestration level; violations are routed to Batch-F.
* **No path literals** appear in L2.

---

## 13) Resource & Concurrency Hints (host-agnostic)

**Goal.** Give the *host* safe knobs for throughput without changing bytes on disk or control flow. L2 logic/outcomes are invariant so long as **within-merchant ordering** is respected and *(event → trace)* pairs are not reordered or batched. L2 never writes evidence or trace.

**Knobs (suggested, not required)**

* `max_workers` (int) — parallelism **across merchants** only. **Within a merchant is always serial.**
* `chunk_size` (int) — size of merchant batches handed to workers (e.g., 256). **Scheduling only.**
* `work_queue_bound` (int) — bound the pending merchant queue to apply back-pressure.
* `io_yield_every` (int) — cooperative yield frequency during long acceptance runs (e.g., every 8 attempts) for fairness; **does not** batch events and **does not** delay the trace append.
* `progress_hook` (fn) — `(merchant_id, stage|attempt_index|accepted, r)` for **non-evidence** logging/monitoring.
* `skip_if_final` (bool, default **true**) — idempotent resume: if `nb_final` exists, **skip** merchant.
* `partial_components_policy` (enum) — `{ abort_run, fail_merchant }`; L2 **never** backfills.
* `deterministic_order` (bool, default **true**) — enforce stable **iteration and join/flush order** (e.g., ascending `merchant_id`) for reproducible logs.

**Invariants the host must not break**

* **Within a merchant:** strict order **S2.1 → S2.2 → (S2.3/S2.4 loop) → S2.5**; per **valid** attempt **Gamma → Poisson**; each event **immediately** followed by **one** writer-driven trace append.
* **No attempt batching, no event reordering, no cross-label counter chaining.**
* **No path literals** anywhere; L1/L0 resolve IDs→paths and stamp envelopes.
* Memory footprint stays merchant-local (ctx, three substreams, three trace totals); free on finaliser or failure.
* Fault tolerance: if a worker dies mid-merchant and **no** finaliser exists, treat as **partial** per policy (`abort_run` or `fail_merchant`); **do not** “continue” emitting more components on resume.

---

## 14) Public API (signatures)

> Code-agnostic, descriptive types. **No path strings** in the API. Evidence is written **only** inside L1 via L0 writers.

### 14.1 Orchestrator entrypoint

```pseudocode
type Lineage  = { seed:u64, parameter_hash:Hex64, manifest_fingerprint:Hex64, run_id:Hex32 }
type NBInputs = { x_mu:f64[], x_phi:f64[], beta_mu:f64[], beta_phi:f64[] }

type HostOpts = {
  max_workers?: int,
  chunk_size?: int,
  work_queue_bound?: int,
  io_yield_every?: int,
  skip_if_final?: bool = true,
  partial_components_policy?: enum{ abort_run, fail_merchant } = abort_run,
  deterministic_order?: bool = true,
  progress_hook?: fn(merchant_id:u64, stage:string, attempt:int, accepted:bool, r:int): void
}

type Result =
  | { kind:"ok",   merchant_id:u64, handoff:{ N:i64, r:i64 } }
  | { kind:"skip", merchant_id:u64, reason:"finaliser_exists" }
  | { kind:"fail", merchant_id:u64, signal:{ code:string, detail:any } }

function orchestrate_S2(
  lineage: Lineage,
  merchants: Iterator[u64],                  # deterministic order when deterministic_order=true
  nb_inputs_provider: fn(u64)->NBInputs,     # read-only handles; no writes
  opts?: HostOpts
) -> Iterator[Result]
```

**Behavioral contract**

* Enumerates **gated** merchants (presence gate via S1 hurdle) and, for each, drives **S2.1 → S2.2 → (S2.3/S2.4 loop) → S2.5**.
* Yields exactly **one** `Result` per merchant:

  * `ok` with `{N,r}` on success;
  * `skip` when `nb_final` already exists;
  * `fail` with a typed `signal` (L2 routes to Batch-F per policy).
* Never writes evidence directly; never re-implements helpers/math/schemas; **never backfills** partial merchants.

### 14.2 Optional host hooks (non-evidence)

```pseudocode
type Hooks = {
  on_start_merchant?: fn(merchant_id:u64, lineage:Lineage): void,
  on_attempt?:        fn(merchant_id:u64, attempt:int): void,
  on_accept?:         fn(merchant_id:u64, N:i64, r:i64): void,
  on_fail?:           fn(merchant_id:u64, signal:{code:string, detail:any}): void,
  on_skip?:           fn(merchant_id:u64, reason:string): void
}
```

Hooks **must not** mutate data or produce evidence; they exist for telemetry/logging only and must not affect determinism or ordering.

**Acceptance for §§13–14**

* Resource knobs influence **throughput only**, not bytes or control flow; within-merchant ordering and *(event→trace)* pairing are maintained.
* API has **no path literals**, exposes only lineage, merchant iteration, and a read-only inputs provider.
* Results are explicit (`ok/skip/fail`); failure signals are typed and routed to Batch-F; resume semantics (`skip_if_final`, **no backfill**) are preserved.

---

## 15) Logging & Progress (non-evidence)

**Goal.** Give operators visibility without creating or mutating **evidence**. Logs must be optional, best-effort, and must **not** influence control flow or bytes on disk.

**Principles**

* **Non-evidence only.** No schema rows, no “shadow traces,” no sampling detail (no `u`, counters, or RNG draws).
* **Determinism-safe.** Turning logs on/off **must not** change ordering, retries, or outputs (including join/flush order).
* **Minimal, structured.** One line per notable event; machine-parsable key/values.

**Recommended fields (per log line)**

* `ts_utc` (RFC-3339 UTC, **exactly 6 fractional digits**, **truncated**, trailing `Z`)
* `component="1A.S2.L2"`, `merchant_id`
* `seed`, `parameter_hash`, `run_id` (for correlation; **do not** log `manifest_fingerprint` contents unless policy allows)
* `stage` ∈ {`start_merchant`,`load_guard`,`links_params`,`attempt`,`accept`,`finalise`,`skip_finaliser_exists`,`fail`}
* `attempt` (int, 0-based) when `stage="attempt"`
* `accepted` (bool) and `r` (int) when `stage="accept"`
* `signal_code` when `stage="fail"` (e.g., `ERR_S2_NUMERIC_INVALID`)
* `duration_ms` (optional) for stage timing

**Never log**

* PRNG internals (`before/after` counters, `draws`, `u`, `G`, `λ`, `K`)
* Evidence payload numbers (`mu`, `phi`, etc.)
* **Any path strings** resolved by the dictionary (avoid leaking storage layout)

**Hook pattern (illustrative, non-blocking)**

```pseudocode
if hooks.on_start_merchant: hooks.on_start_merchant(merchant_id, lineage)
if hooks.on_attempt:        hooks.on_attempt(merchant_id, attempt_idx)
if hooks.on_accept:         hooks.on_accept(merchant_id, N, r)
if hooks.on_fail:           hooks.on_fail(merchant_id, signal)
if hooks.on_skip:           hooks.on_skip(merchant_id, "finaliser_exists")
```

Hooks must not throw; hook failures are logged and **ignored** (must not affect ordering or outcomes).

---

## 16) Acceptance (for this L2 file)

L2 is **green** when all of the following hold:

**Scope & discipline**

* Implements **orchestrator only**: S2.1 → S2.2 → (S2.3/S2.4 loop) → S2.5; no new helpers/math; no validators/corridors.
* All evidence I/O occurs inside **L1 via L0** (dictionary-resolved writers). **No path literals** appear in L2.

**Gating & idempotence**

* Presence gate enforced: S2 runs **iff** hurdle `is_multi==true`.
* Per `(seed, parameter_hash, run_id, merchant_id)`: **≤ 1** `nb_final`; merchants with an existing finaliser are **skipped** (resume-safe).
* No “partial backfill”: if components exist without a finaliser, L2 does **not** emit more; routes to the canonical failure path.

**Ordering & concurrency**

* **Within a merchant:** strict order S2.1→S2.2→(S2.3/S2.4)\*→S2.5; per **valid** attempt **Gamma → Poisson**.
* **Across merchants:** parallel allowed; **iteration and join/flush order deterministic** for logs; outcomes invariant to scheduling.
* Each event write is immediately followed by **one** cumulative, **saturating** trace append (writer-driven serialization point).

**Path/Embed & partitions**

* RNG families (`gamma_component`, `poisson_component`, `nb_final`) written under partitions `{seed, parameter_hash, run_id}` with **path↔embed equality**; **trace rows embed `{seed, run_id}` only** (`parameter_hash` path-only).
* `module`, `substream_label`, `manifest_fingerprint` remain **embed-only** (never in path partitions).

**RNG & evidence invariants**

* Substreams are **per family**; **no cross-label counter chaining**.
* `blocks = after − before` (counters); `draws =` **actual uniforms consumed** (decimal u128) — identities kept **independent**.
* `nb_final` is **non-consuming** (`before==after`, `blocks=0`, `draws:"0"`) and **echoes** `mu`/`dispersion_k` bit-for-bit from S2.2.

**Failure flow**

* L1 signals (`ERR_S2_INPUTS_INCOMPLETE`, `ERR_S2_NUMERIC_INVALID`, gating breaches, etc.) are **routed** to Batch-F (merchant-scoped record or atomic run abort) per policy. L2 invents **no** new failure shapes.
* On structural/discipline violations (path↔embed mismatch, trace append failure, branch purity), L2 performs **atomic run abort** via Batch-F.

**Logging & progress**

* Any logs are **non-evidence**: optional, structured, and determinism-safe; they never include RNG internals or evidence payloads; hook failures are ignored.

---