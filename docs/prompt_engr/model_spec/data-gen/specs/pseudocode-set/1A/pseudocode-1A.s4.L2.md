# S4·L2 — Orchestrator

# 0) Quick-Start (One Screen, Copy-Ready)

**Goal:** wire S4 (ZTP) deterministically with **kernels-only** calls from L2. No payload crafting, no envelope/trace stamping here—that’s **L1→L0**. One event → **one immediate** cumulative trace (same writer). Attempts use **`lambda`**; markers/final use **`lambda_extra`**. Cap is **64**. A=0 → **final-only**.  

**Enter S4 only if (from S1/S2/S3):** `is_multi==true`, `is_eligible==true`, `N≥2`, `A≥0`. If any fail: **emit nothing** for S4.  

**A=0 short-circuit:** compute λ/regime once (K-1), then **final-only** `ztp_final{K_target=0, attempts:0 [,reason]?}`, **no attempts/markers**.  

**Attempt loop (1..64):** per attempt call **K-2 → K-3 → (K-6 | K-4)**; on cap with no acceptance: **policy="abort" → K-5** (exhausted **only**), else **K-6** final `{K_target=0, attempts:64, exhausted:true}`. All emission appends **exactly one** immediate trace.   

---

### Copy-ready recipe (L2 → L1 kernels only)

```text
PROC orchestrate_s4_for_merchant(ctx):
  # Gates (S1/S2/S3)
  REQUIRE ctx.is_multi == true      # S1 hurdle
  REQUIRE ctx.is_eligible == true   # S3 eligibility
  REQUIRE ctx.N >= 2                # S2 nb_final
  A := ctx.A                        # |S3.candidate_set \\ {home}|
  IF final_exists(ctx.merchant_id) OR exhausted_exists(ctx.merchant_id): RETURN
  IF A == 0:
    lr  := K1.freeze_lambda_regime(ctx.N, ctx.X_m, ctx.θ0, ctx.θ1, ctx.θ2)
    s   := derive_merchant_stream(ctx.lineage, ctx.merchant_id)
    K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr,
                         {K_target:0, attempts:0 [,reason?]}) ; RETURN

  # Resume
  lr := K1.freeze_lambda_regime(ctx.N, ctx.X_m, ctx.θ0, ctx.θ1, ctx.θ2)
  s  := resume_stream_or_fresh(ctx)                 # from last s_after, else derive fresh
  a0 := resume_attempt_index(ctx.merchant_id)       # max(attempt)+1 or 1

  FOR attempt IN a0 .. 64:
    IF exists_attempt(ctx.merchant_id, attempt):
       {k, s_after} := read_attempt_k_after(ctx.merchant_id, attempt)  # no RNG
       s := s_after
    ELSE:
       (k, s_after, bud) := K2.do_poisson_attempt_once(lr, s)          # RNG-consuming
        K3.emit_poisson_attempt(ctx.merchant_id, ctx.lineage, s, s_after, lr, attempt, k, bud)
        s := s_after
    IF k > 0:
       K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr, {K_target:k, attempts:attempt})
       RETURN
    IF NOT exists_rejection(ctx.merchant_id, attempt):
       K4.emit_ztp_rejection_nonconsuming(ctx.merchant_id, ctx.lineage, s, lr, attempt)

  # Cap reached (64 zeros)
  IF ctx.policy == "abort":
     IF NOT exists_exhausted(ctx.merchant_id):
        K5.emit_ztp_retry_exhausted_nonconsuming(ctx.merchant_id, ctx.lineage, s, lr, policy="abort")
     RETURN
  ELSE:
     IF NOT exists_final(ctx.merchant_id):
        K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr,
                             {K_target:0, attempts:64, exhausted:true})
     RETURN
```

* **Why this is authoritative:**
  • Gates & A=0 are fixed in expanded + L1.  
  • Loop shape & kernel order are fixed in L1 (K-2→K-3→[K-6|K-4]; cap → K-5/K-6).  
  • Emission semantics (consuming vs non-consuming) + **one event → one immediate trace** are L0-true.  
  • Attempt payload uses **`lambda`**; markers/final use **`lambda_extra`**; partitions `{seed,parameter_hash,run_id}` are stamped by L0.  
  • Cap path: abort ⇒ exhausted **only** (`attempts:64`, `aborted:true`); downgrade ⇒ final `{…, attempts:64, exhausted:true}`.  

**Handoff to L3:** L2 ensures: no attempt gaps; ≤64 attempts; exactly one terminal outcome per merchant; adjacency preserved. L3 will validate consuming/non-consuming identities, counters vs draws, and cumulative trace totals.  

**Upstream tie-ins (don’t forget):** presence gate `is_multi==true` is from **S1** (hurdle); S0 sets the RNG/trace regime and counter rules that L0 enforces at write.  

---

# 1) Intent & Scope (L2’s Job)

**Intent (what L2 does):** Orchestrate **State-4 (ZTP)** deterministically, per merchant, by driving the **kernel call sequence** only—**K-1 → (A=0? K-6 : loop[K-2 → K-3 → (K-6 | K-4)] → cap: K-5|K-6)**—and by enforcing **gates, substream derivation, idempotence/resume, single-writer discipline**, and a **single terminal outcome**. L2 **never** constructs payloads or stamps envelopes/trace; those are owned by **L1→L0** emitters (one event → **one immediate** cumulative trace). Attempts use **`lambda`**; rejection/exhausted/final use **`lambda_extra`**.  

**Entry gates (must hold or S4 writes nothing):**
`is_multi==true` (from S1 hurdle), `is_eligible==true` (S3), `N≥2` (from S2 `nb_final`), and a valid admissible set size **A≥0** (from S3). If **A=0**, L2 must short-circuit: compute λ/regime via **K-1** and write **one** non-consuming `ztp_final{K_target=0, attempts:0 [,reason]?}`—**no attempts/markers**.  

**Terminal outcomes (exactly one per merchant):**
(1) **Acceptance** at attempt *t*: `ztp_final{K_target≥1, attempts:t}`; (2) **Cap-abort** (64 zeros, `policy="abort"`): `ztp_retry_exhausted{attempts:64, aborted:true}`, **no final**; (3) **Cap-downgrade** (64 zeros, `policy="downgrade_domestic"`): `ztp_final{K_target=0, attempts:64, exhausted:true}`. L2 must not invent other outcomes.  

**Separation of duties (binding):**

* **L1 kernels** compute values/assemble payloads and call **one** L0 emitter each; **emitters stamp envelopes and append the immediate trace** (same writer). L2 **never** calls L0 directly. 
* **S4 fixes counts only at the target level (`K_target`) and MUST NOT encode cross-country order**; S6 realises `K_realized = min(K_target, A)` using S3’s order authority.  

**Determinism, idempotence & resume (L2 obligations):**

* **Derive the merchant-scoped substream once** (S0 discipline); counters—not file order—define total order. **Attempt** is 1-based, strictly increasing, max **64**. 
* **Deduplicate before RNG:** if attempt *a* exists, **do not resample**; read `{k, s_after}` from store and branch. Resume at `max(attempt)+1`, seeding `s_before := last.s_after`. 
* **Event→trace adjacency is inviolate:** each emission writes exactly **one** event followed by **one immediate** cumulative trace (same writer); on crash where an event exists but the trace is missing, **do not re-emit** the event—append the **trace-only** repair once.  

**Out-of-scope for L2 (non-goals):**

* No computation of λ/regime beyond calling **K-1**; no payload crafting; no envelope or partition logic; no post-hoc validation (L3). L2 also **must not** alter `K_target` to fit `A`; S4 fixes `K_target`, S6 realises `min(K_target, A)`. 

**Concurrency model:** per-merchant loops run **serially**; parallelism is **across** merchants only (writer/merge steps must be stable w.r.t. stream sort keys to keep outputs byte-identical). 

**Handoff expectation:** When L2 returns, the merchant is resolved via one terminal outcome; downstream S6 consumes `ztp_final{K_target, lambda_extra, attempts, regime [,exhausted?]}` (absent only on cap-abort). 

---

# 2) Authorities, Versions & Separation of Duties

**What this section fixes:** the sources of truth L2 must obey, the exact versions in force, and a hard “who-does-what” boundary so the orchestrator never invents policy or bytes.

## 2.1 Binding authorities (schema & dictionary)

* **Authoritative event streams for S4:**
  `rng_event_poisson_component` (attempt, **consuming**), `rng_event_ztp_rejection` (zero marker, **non-consuming**), `rng_event_ztp_retry_exhausted` (cap-abort marker, **non-consuming**), `rng_event_ztp_final` (finaliser, **non-consuming**). Attempt payload **uses key `lambda`**; markers/final **use `lambda_extra`**.  

* **Trace stream:** `rng_trace_log` under partitions `{seed, parameter_hash, run_id}` with **no `context` field** (trace embeds only `run_id` and `seed`; `parameter_hash` is path-only). **One immediate cumulative trace append** (same writer) after **each** event row. **File order is non-authoritative; counters define order.**  

* **Partitions & path↔embed:** All S4 logs are dictionary-resolved under `{seed, parameter_hash, run_id}`; **events’ envelopes** are stamped by L0; L2 passes lineage values, **never paths**.  

* **Labels:** `(module, substream_label, context)` are **spec-pinned** for S4:
  `module="1A.s4.ztp"`, `substream_label="poisson_component"` for **all S4 events and trace**; `context="ztp"` on **events only** (trace has none).  

## 2.2 Version facts L2 must treat as constants

* **Schema version (attempt payload key):** attempts carry `lambda` (not `lambda_extra`). This is a **schema-true field name** used by L1→L0 emitters. 

* **Cap is fixed at 64 in this schema:** the abort marker **requires** `attempts:64` (const) and `aborted:true`; downgrade path writes a finaliser with `attempts:64, exhausted:true`. L2 treats 64 as **pinned** (no runtime override).  

* **Trace lineage shape (v15):** trace rows embed `{run_id, seed}`, **no `context`**; partitions `{seed, parameter_hash, run_id}`; totals are **saturating** and monotone; consumer selects final row per `(module, substream_label)`.  

## 2.3 Separation of duties (allowed vs forbidden)

| Layer                            | Owns                                                                                                                                                                                               | May call      | **Must not**                                                                                                                                                               |
|----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **L0 (emitters & trace writer)** | Stamp authoritative **envelopes**; write **event** row; append **one immediate** cumulative **trace**; enforce consuming vs non-consuming identities; enforce partitions/lineage                   | —             | Expose no orchestration; never rely on file order (counters rule)                                                                                                          |
| **L1 (kernels)**                 | Compute values/assemble **payloads**; call **exactly one** L0 emitter per kernel; keep payload keys schema-true (`lambda` for attempts; `lambda_extra` for markers/final)                          | L0            | Never stamp envelopes/trace directly; never recompute λ/Regime outside **K-1**                                                                                             |
| **L2 (this file)**               | **Orchestrate**: gates, substream derivation, idempotence/resume, **K-1 → (A=0? K-6 : loop[K-2 → K-3 → (K-6 \| K-4)] → cap[K-5/K-6])**, single-writer discipline, exactly **one** terminal outcome | L1 (K-1..K-6) | **Never call L0** directly; never craft payloads; never stamp envelopes/trace; never encode inter-country order (S4 sets **K_target** only; S6 realises `min(K_target,A)`) |
| **L3 (validator)**               | Read-only checks on structure, lineage, counters vs draws, identities, corridors; gate downstream                                                                                                  | —             | Never write or restamp; no path literals (dictionary only)                                                                                                                 |

**Why this matters:** keeping L2 **kernel-only** ensures (a) **one event → one immediate trace** remains invariant, (b) payload field names and consuming identities stay **schema-true**, and (c) resumes/dedupes can rely on **counters** and natural keys rather than fragile file order. All three are mandated by your L0/L1 contracts.  

---

# 3) Inputs & Context Assembly (“Ctx” Contract)

**Purpose.** Define the exact **value-level bundle** L2 must assemble per merchant—no paths, no payload crafting—so orchestration starts from a validated, deterministic context. If any gate fails, **S4 emits nothing** for that merchant. 

## 3.1 Required fields (per merchant `m`) — types, source, constraints

| Field              | Type                                                                           | Source / Meaning                                                    | Must hold                       |
|--------------------|--------------------------------------------------------------------------------|---------------------------------------------------------------------|---------------------------------|
| `merchant_id`      | `int64`                                                                        | Ingress key used in all S4 payloads.                                | present                         |
| `lineage`          | `{ seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }` | Pass-through to emitters; L0 stamps envelopes using these tokens.   | present                         |
| `is_multi`         | `bool`                                                                         | S1 hurdle outcome; S4 runs only for `true`.                         | `true`                          |
| `is_eligible`      | `bool`                                                                         | S3 eligibility; if `false`, S4 writes no events.                    | `true`                          |
| `N`                | `int ≥ 2`                                                                      | S2 **`nb_final`**; S4 never alters `N`.                             | `≥ 2`                           |
| `A`                | `int ≥ 0`                                                                      | S3 admissible foreigns size: `A = size(S3.candidate_set \\ {home})` | `≥ 0`                           |
| `θ = (θ0, θ1, θ2)` | tuple(`float`)                                                                 | S4 ZTP link params (governed; participate in `parameter_hash`).     | finite                          |  
| `X_m`              | `float ∈ [0,1]`                                                                | Feature for link; **default 0.0 if missing** (expanded spec).       | in [0,1]                        |
| `policy`           | `"abort" \| "downgrade_domestic"`                                              | Exhaustion policy (governed).                                       | **Cap pinned at 64** by schema. |

> **Authority boundaries.** S4 is **logs-only**: it fixes `K_target` via `ztp_final` and never encodes cross-country order; S6 later realises `K_realized = min(K_target, A)` using S3’s order authority. 

## 3.2 Preflight (gates & short-circuit)

L2 MUST assert these before any sampling or emission (order doesn’t matter).

* `is_eligible == true` and `is_multi == true`. 
* `N` is integer and `N ≥ 2`. 
* `A` is integer and `A ≥ 0`. 
* `policy ∈ {"abort","downgrade_domestic"}`. 

**A=0 path.** If `A == 0`, L2 must **not** drive attempts: call **K-1** (freeze λ/regime) then **K-6** to emit **one** non-consuming `ztp_final{K_target=0, attempts:0 [,reason]?}`; **no attempt or marker rows** are written.  

## 3.3 Context assembly (value-only; no paths)

L2 constructs `Ctx` as the minimal bundle passed to kernels:

```
Ctx = {
  merchant_id,
  lineage:{seed, parameter_hash, run_id, manifest_fingerprint},
  is_multi, is_eligible,
  N, A,
  θ0, θ1, θ2, X_m,
  policy
}
```

* All values are read-only to S4 and **dictionary-resolved** (no path literals); L0 will enforce partitions `{seed, parameter_hash, run_id}` and stamp envelopes/trace. 
* L2 **does not** add payload keys or envelope fields here; those are assembled by L1 kernels and stamped by L0 emitters. 

**Outcome of §3.** If all gates pass, L2 has a complete `Ctx` and can proceed to §4 (DAG) and §6-§9 (substream, resume, and loop); otherwise it must **emit nothing** for S4 and return.  

---

# 4) Upstream Gate Checks (Enter/Skip Rules)

**Purpose.** Define the **must-hold conditions**—all from upstream authorities—before L2 may orchestrate S4. If any gate fails, **S4 writes nothing** for that merchant. *No payload crafting, no emitters here; L2 only decides whether to proceed.*

---

## 4.1 Gates (what must be true) — with source and action

| Gate                    | What must be true                                   | Authority (read-only)                | L2 action if **false**                                                                                         | L2 action if **true** |
|-------------------------|-----------------------------------------------------|--------------------------------------|----------------------------------------------------------------------------------------------------------------|-----------------------|
| **Hurdle in-scope**     | `is_multi == true`                                  | **S1** hurdle result                 | **BYPASS S4** (domestic-only path); no S4 events                                                               | Continue gates        |
| **Eligibility**         | `is_eligible == true`                               | **S3** eligibility flag              | **BYPASS S4**; no S4 events                                                                                    | Continue gates        |
| **NB total**            | `N ≥ 2` (authoritative)                             | **S2** `nb_final` (non-consuming)    | **BYPASS S4**; merchant not in S4 scope                                                                        | Continue gates        |
| **Admissible universe** | `A := size(S3.candidate_set \\ {home})` with `A ≥ 0` | **S3** candidate set (deterministic) | If `A<0` or set invalid → fail-fast per failure mapping; otherwise treat `A==0` as **short-circuit** (see 4.2) | Continue (4.3)        |
| **Policy domain**       | `policy ∈ {"abort","downgrade_domestic"}`           | governed config surfaced to L2       | fail-fast; do **not** emit                                                                                     | Continue              |

> Notes
> - L2 **does not** alter `N` or `A`; S4 fixes **only** the target count (`K_target`) later and **never** encodes order.
> - All checks are **value-level**; no path literals—use dictionary lookups only.

---

## 4.2 A=0 short-circuit (final-only path)

When `A == 0`, L2 **must not** drive the attempt loop:

1. Call **K-1** `freeze_lambda_regime(N, X_m, θ)` (single source of truth for `λ`, `regime`).
2. Derive the merchant substream once (S0 discipline).
3. Call **K-6** to emit **one** non-consuming `ztp_final{K_target=0, attempts=0 [,reason?]}`.
4. **Stop** (no attempt or marker rows are written).

---

## 4.3 Proceed (all gates passed; `A ≥ 1`)

If all gates in **4.1** pass **and** `A ≥ 1`, L2 may orchestrate S4:

* Derive the merchant-scoped substream once (S0).
* Compute `λ, regime` via **K-1** (no inline math in L2).
* Enter the bounded attempt loop **1..64** using **kernels only** (details in §§9-10).

---

## 4.4 Copy-ready gate routine (value-only; no emitters)

```text
PROC s4_preflight(ctx):
  # Required gates (skip order is fine; all must hold)
  REQUIRE ctx.is_multi     == true        # S1
  REQUIRE ctx.is_eligible  == true        # S3
  REQUIRE IS_INT(ctx.N) AND ctx.N >= 2    # S2 nb_final
  REQUIRE IS_INT(ctx.A) AND ctx.A >= 0    # S3 candidate_set size
  REQUIRE ctx.policy IN {"abort","downgrade_domestic"}

  IF exists_final(ctx.merchant_id) OR exists_exhausted(ctx.merchant_id):
      RETURN SKIP_ALREADY_RESOLVED

  IF ctx.A == 0:
      # Short-circuit: final-only; no attempts/markers
      lr := K1.freeze_lambda_regime(ctx.N, ctx.X_m, ctx.θ0, ctx.θ1, ctx.θ2)
      s  := derive_merchant_stream(ctx.lineage, ctx.merchant_id)
      K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr, {K_target:0, attempts:0 [,reason?]})
      RETURN SHORT_CIRCUIT_FINAL

  RETURN PROCEED   # all gates passed; go to loop setup
```

---

## 4.5 Failure mapping (if a gate cannot be satisfied)

* **Missing/invalid S1/S2/S3 inputs** → standardized failure (`HURDLE_MISSING`, `NB_FINAL_MISSING`, `S3_CANDIDATE_INVALID`).
* **Policy out of domain** → `POLICY_INVALID`.
* **Numeric invalid at K-1** (non-finite `λ` or `≤0`) → `NUMERIC_INVALID`; **no** events written.

*On any gate failure, L2 stops S4 for that merchant; other merchants may proceed.*

---

# 5) Orchestration DAG & Call Graph (Authoritative)

**What this section fixes:** the **only legal execution shape** L2 may drive for **State-4 (ZTP)**—as kernel calls (K-1…K-6) with guards and terminal outcomes. L2 *never* calls L0 directly and *never* crafts payloads or stamps envelopes/trace.

---

## 5.1 ASCII DAG (authoritative)

```
[ENTER S4]
   │
   │ Gates OK?  (is_multi && is_eligible && N≥2 && A≥0)
   │—— no ────────────────────────────────▶ [STOP: S4 writes nothing]
   │
   v
[K-1 freeze λ,regime]  (single source of truth; no inline math in L2)
   │
   │ A == 0 ?
   │—— yes ─▶ [K-6 final]  (K_target=0, attempts=0 [,reason?]) ─▶ [STOP]
   │
   v
[Derive merchant substream once (S0)]
   │
   │   Attempt loop (bounded): a = 1..64
   │   ┌────────────────────────────────────────────────────────────────┐
   │   │  [K-2 sample once]  →  [K-3 emit attempt (consuming; λ)]       │
   │   │            │ k>0?                      │ k==0                  │
   │   │            │                           v                       │
   │   │        yes v                      [K-4 emit rejection]         │
   │   │       [K-6 final]  ────────────────────┘                       │
   │   │            │ (attempts=a; exhausted absent)                    │
   │   │            v                                                   │
   │   │          [STOP]                                                │
   │   └────────────────────────────────────────────────────────────────┘
   │
   │ Cap reached (64 zeros):
   │  policy == "abort"         policy == "downgrade_domestic"
   │        v                              v
   │   [K-5 exhausted]               [K-6 final]
   │   (attempts=64,                 (K_target=0, attempts=64,
   │    aborted=true)                 exhausted=true)
   │        v                              v
   └──────▶ [STOP]                    └────▶ [STOP]
```

**Global invariants baked into the DAG**

* **Kernels-only orchestration:** K-1, then either **K-6** (A=0) or bounded loop **K-2 → K-3 → (K-6 | K-4)**, then terminal (**K-5** or **K-6**).
* **Single terminal outcome per merchant:** acceptance final *or* exhausted marker *or* downgrade final.
* **Attempt indices:** 1-based, strictly increasing, **max 64**.
* **Event discipline (owned by L0 via L1 emitters):** every event is immediately followed by one cumulative trace (same writer). Attempts are **consuming**; rejection/exhausted/final are **non-consuming**.
* **No order leakage:** S4 fixes **K_target only**; cross-country order remains S3’s authority; S6 realises `min(K_target, A)`.

---

## 5.2 Legal edges (state machine spec)

Each edge is *(from → to | guard / action)*; all actions are **kernel calls** (no L0 here).

* **E0.** `ENTER → STOP | (¬is_multi ∨ ¬is_eligible ∨ N<2 ∨ A<0) / return`
* **E1.** `ENTER → K-1 | (is_multi ∧ is_eligible ∧ N≥2 ∧ A≥0) / K-1`
* **E2.** `K-1 → K-6 | (A==0) / final(K_target=0, attempts=0 [,reason?])`
* **E3.** `K-1 → SUBSTREAM | (A≥1) / derive_merchant_stream(lineage, merchant_id)`
* **E4.** `SUBSTREAM → K-2 | (a in 1..64 and attempt a not on disk) / sample once`
* **E5.** `SUBSTREAM → BRANCH | (attempt a exists) / read{k, s_after} (no RNG)`
* **E6.** `K-2 → K-3 | always / emit attempt (payload uses λ)`
* **E7.** `K-3 → K-6 | (k>0) / final(K_target=k, attempts=a)`
* **E8.** `K-3 → K-4 | (k==0) / emit rejection (payload uses λ_extra)`
* **E9.** `K-4 → NEXT | (a<64) / a:=a+1; s_before:=s_after`
* **E10.** `K-4 → CAP | (a==64) / cap reached`
* **E11.** `CAP → K-5 | (policy=="abort") / exhausted( attempts=64, aborted=true )`
* **E12.** `CAP → K-6 | (policy=="downgrade_domestic") / final( K_target=0, attempts=64, exhausted=true )`
* **E13.** `K-6 → STOP | always / return`
* **E14.** `K-5 → STOP | always / return`

*“BRANCH” and “NEXT” are control points internal to L2; they have no I/O.*

---

## 5.3 Call graph (who calls whom)

| Caller (L2) | Callee (Kernel)                                 | When                           | Notes                                                  |
|-------------|-------------------------------------------------|--------------------------------|--------------------------------------------------------|
| L2          | **K-1** `freeze_lambda_regime`                  | Always, before A-path          | Single source of truth for `λ, regime`                 |
| L2          | **K-6** `do_emit_ztp_final`                     | A=0; acceptance; cap-downgrade | Non-consuming; attempts: 0 or a or 64 (with exhausted) |
| L2          | **K-2** `do_poisson_attempt_once`               | Each new attempt               | RNG-consuming; no I/O                                  |
| L2          | **K-3** `emit_poisson_attempt`                  | Right after K-2                | Consuming event; payload uses **`lambda`**             |
| L2          | **K-4** `emit_ztp_rejection_nonconsuming`       | When `k==0`                    | Non-consuming; payload uses **`lambda_extra`**         |
| L2          | **K-5** `emit_ztp_retry_exhausted_nonconsuming` | Cap with `policy=="abort"`     | Non-consuming; **`attempts:64, aborted:true`**         |

**Prohibited edges (explicitly disallowed)**

* L2 → **L0 emitters** (any family).
* K-4/K-5 before K-3 in a given attempt.
* Any second terminal after a terminal (final/exhausted).
* Any attempt index outside **1..64** or non-contiguous attempt sequence.
* Re-sampling an attempt that already exists on disk.

---

## 5.4 Ordering & determinism notes

* **Substream lifetime:** derived **once** per merchant; `s_before` advances only via **K-2** results (or by reading `s_after` from persisted rows).
* **Resume is deterministic:** if attempts exist, resume at `max(attempt)+1` with `s_before := last.s_after`; never resample existing attempts.
* **Total order:** defined by envelope counters (not file order).
* **Trace adjacency:** emission guarantees one immediate cumulative trace (same writer); L2 never appends trace.

---

## 5.5 Acceptance checklist (for this section)

* DAG exactly as above; no extra edges.
* Call graph uses **only** K-1…K-6 in the positions shown.
* Accept/Cap/A=0 terminals produce **exactly one** terminal outcome per merchant.
* Attempts: contiguous 1..64; consuming vs non-consuming identities preserved.
* No L0 calls from L2; no payload construction in L2; no order encoding in S4.

---

# 6) Substream Derivation (Deterministic, S0 Discipline)

**Purpose.** Give L2 a **single, deterministic recipe** to obtain the merchant-scoped PRNG stream that drives **all** S4 events (attempt, rejection, exhausted, final). L2 derives the stream **once per merchant** and never fabricates counters or budgets; **L1/L0 consume the stream** and stamp event+trace.

---

## 6.1 Frozen literals (must match the spec)

```
MODULE          = "1A.s4.ztp"
SUBSTREAM_LABEL = "poisson_component"     # used for every S4 event
CONTEXT         = "ztp"                   # in EVENT envelopes only (trace has no context)
```

> All S4 events use the same `(MODULE, SUBSTREAM_LABEL)`; **trace rows** share this domain and carry **no `context`**. One event → **one immediate** cumulative trace (same writer).

---

## 6.2 Merchant key (Ids) — how to build it

* Compute a **stable merchant tag** once:
  `merchant_u64 := LOW64( SHA256( LE64(merchant_id) ) )`
  (little-endian encode → SHA-256 → take low 64-bits).

* **Ids** passed to the substream is a **typed list**; for S4 we use:
  `Ids = [ { tag: "merchant_u64", value: merchant_u64 } ]`

> **SER v1** allows only `{iso, merchant_u64, i, j}` tags; if `iso` is ever used elsewhere, it must be **UPPERCASE ASCII** before encoding. Order within `Ids` is serialized deterministically (order-invariant).

---

## 6.3 Master material (from S0)

Derive the master PRNG material **once** from the run lineage:

```
M := S0.derive_master_material(lineage.seed, BYTES(lineage.manifest_fingerprint))
```

`manifest_fingerprint` is the run’s artefact digest; changing it yields a different master (and therefore different streams), which is intended.

---

## 6.4 Derive the merchant-scoped stream (one per merchant)

Use S0’s order-invariant derivation:

```
s0 := S0.derive_substream(M, SUBSTREAM_LABEL, Ids)   # label = "poisson_component"
```

**This `s0` is the only stream** L2 passes into S4 kernels for this merchant.

* **Attempts (K-2→K-3)**: consume RNG, advancing counters.
* **Markers/final (K-4/K-5/K-6)**: **non-consuming**; they must receive the **current** stream (so `before==after`, `blocks=0`, `draws="0"`).

> **Never** chain substreams across labels or derive from a prior event’s `after`. All S4 families live under the **same** `(MODULE, SUBSTREAM_LABEL)`.

---

## 6.5 Resume discipline (when attempts already exist)

* If any attempt rows exist on disk, do **not** re-derive and resample from `s0`.
  Instead:

  1. Let `t_max := max(attempt)` on disk.
  2. Read the stored projection `{ k, s_after }` for `t_max`.
  3. Set `s_before := s_after` and resume at `attempt := t_max + 1`.

* If **no** attempt exists, start with `s_before := s0` and `attempt := 1`.

> **Counters define order** (file order/timestamps are non-authoritative). The stream you pass into each kernel is exactly the “before” you branch from (persisted or freshly derived).

---

## 6.6 What L2 must **not** do

* **Do not** compute or mutate budgets; they are **measured** by the sampler and emitted by L1/L0.
* **Do not** fabricate counters or “estimate” `after`; always use the stream returned by K-2 or the persisted `s_after`.
* **Do not** mint multiple streams per merchant; the **same** merchant-scoped stream drives every S4 family.
* **Do not** stamp envelopes or traces; that is **L0’s** job.

---

## 6.7 Copy-ready helper (value-only)

```text
PROC derive_merchant_stream(lineage, merchant_id) -> Stream:
  merchant_u64 := LOW64( SHA256( LE64(merchant_id) ) )
  M := S0.derive_master_material(lineage.seed, BYTES(lineage.manifest_fingerprint))
  RETURN S0.derive_substream(M, "poisson_component", [
           { tag:"merchant_u64", value: merchant_u64 }
         ])
```

Use this to seed `s_before` (fresh runs) or as the base when no attempts exist. On resume, always set `s_before := last.s_after` from disk instead of re-deriving.

---

## 6.8 Acceptance checklist (for this section)

* One merchant-scoped stream per merchant (`MODULE="1A.s4.ztp"`, `SUBSTREAM_LABEL="poisson_component"`).
* Derived via **S0** from `{seed, manifest_fingerprint}` + `merchant_u64`.
* Attempts consume; markers/final are non-consuming (must receive the **current** stream).
* Resume uses persisted `s_after`; **no resampling** of existing attempts.
* L2 never stamps envelopes/trace or computes budgets.

---

# 7) Idempotence & Resume Semantics

**Purpose.** Make re-runs **byte-identical** and restarts **deterministic**. L2 must: (a) **dedupe before RNG**, (b) **resume from persisted state**, (c) preserve **event→trace adjacency**, and (d) produce **exactly one** terminal outcome per merchant—even across crashes.

---

## 7.1 First principles (what never changes)

* **Deduplicate before RNG.** If an attempt row already exists on disk for `(merchant_id, attempt=a)`, L2 **must not** resample. Read the persisted projection `{k, s_after}` and branch on that.
* **Counters define order.** File order/timestamps are **non-authoritative**; the envelope counters are the total order.
* **One event → one immediate trace (same writer).** L2 never appends trace; emitters (via L1) do event **then** cumulative trace atomically.
* **Non-consuming vs consuming.** Attempts are **consuming**; rejection/exhausted/final are **non-consuming** and must be passed the **current** stream (`before==after`).
* **Single stream per merchant.** Derive the merchant-scoped stream once (see §6) and thread it; on resume, start from the last persisted `s_after`.

---

## 7.2 Natural keys & skip rules (per family)

| Family (effect)                          | Natural key                  | When to **skip**   | What to read when skipping                         |
|------------------------------------------|------------------------------|--------------------|----------------------------------------------------|
| `poisson_component` (attempt; consuming) | `(merchant_id, attempt)`     | If present on disk | `{k:int, s_after:Stream}` to drive branch/advance  |
| `ztp_rejection` (non-consuming)          | `(merchant_id, attempt)`     | If present on disk | — (no branch state; stream remains as is)          |
| `ztp_retry_exhausted` (non-consuming)    | `(merchant_id, attempts=64)` | If present on disk | —                                                  |
| `ztp_final` (non-consuming)              | `(merchant_id)`              | If present on disk | `K_target:int` (for reporting/confirming terminal) |

*Terminal resolution fence:* if **final** or **exhausted** exists for a merchant, the merchant is **resolved**; L2 performs no further S4 writes.

---

## 7.3 Resume algorithm (attempt index & stream)

1. **Resolve fence first.**
   If `final_exists(mid)` or `exhausted_exists(mid)` → **return** (merchant done).

2. **Resume attempt index.**
   Let `t_max := max_attempt(mid)` (or `null` if none).

   * If `null` → `attempt := 1`.
   * Else → `attempt := t_max + 1`.

3. **Resume stream.**

   * If `t_max == null` → `s_before := derive_merchant_stream(lineage, mid)`.
   * Else → read `{k, s_after}` for `t_max` and set `s_before := s_after`.

4. **Pre-emit dedupe each iteration.**
   Before sampling attempt `a`, check `exists_attempt(mid,a)`.

   * If **exists** → read `{k, s_after}`; **do not** call K-2; branch using `k`; set `s_before := s_after`.
   * If **missing** → call **K-2** to sample once, then **K-3** to emit attempt (consuming), and continue.

---

## 7.4 Crash windows & trace repair

* **Event persisted, trace missing.** L2 must **not** re-emit the event. The next emitter append (any family) will repair the missing **trace** using the persisted event’s envelope (adjacency invariant). If a repair is impossible, emit the standardized **TRACE_MISSING** failure and stop for that merchant.
* **After terminal events.** If a crash happens after a finaliser/exhausted marker is persisted, the resolution fence will short-circuit all further work on resume.

---

## 7.5 Concurrency & idempotence together

* **Per-merchant single writer.** Never run two K-7 loops for the same merchant in parallel. Across merchants, parallelism is safe.
* **Stable writers.** Writer merges must be stable w.r.t. the family’s writer-sort; counters—not file order—remain the source of truth.

---

## 7.6 Copy-ready helpers (L2 only; read-only I/O)

```text
PROC resume_attempt_index(merchant_id) -> int:
  IF final_exists(merchant_id) OR exhausted_exists(merchant_id): RETURN 0
  t_max := max_attempt(merchant_id)
  RETURN (t_max == null ? 1 : t_max + 1)

PROC resume_stream_or_fresh(ctx) -> Stream:
  mid := ctx.merchant_id
  base := derive_merchant_stream(ctx.lineage, mid)                  # §6
  t_max := max_attempt(mid)
  IF t_max == null: RETURN base
  {k, s_after} := read_attempt_k_after(mid, t_max)
  RETURN s_after

PROC pre_emit_dedupe(merchant_id, attempt) -> maybe<{k:int, s_after:Stream}>:
  IF exists_attempt(merchant_id, attempt):
      RETURN read_attempt_k_after(merchant_id, attempt)
```

*Usage inside the loop:*

* `a0 := resume_attempt_index(mid)`; if `a0 == 0` → resolved, return.
* `s := resume_stream_or_fresh(ctx)`.
* For each `a in a0..64`, call `pre_emit_dedupe(mid,a)` before K-2; branch accordingly.

---

## 7.7 Failure mapping (idempotence & resume)

| Condition                                                     | Failure code       | Effect                         |
|---------------------------------------------------------------|--------------------|--------------------------------|
| Missing/invalid upstream inputs (S1/S2/S3)                    | `UPSTREAM_INVALID` | Stop S4 for this merchant      |
| Attempt gaps on disk (e.g., 1,2,4 exists)                     | `ATTEMPT_GAPS`     | Stop merchant; operator triage |
| Policy/domain mismatch on cap path                            | `POLICY_INVALID`   | Stop merchant                  |
| Numeric invalid at K-1 (λ non-finite/≤0)                      | `NUMERIC_INVALID`  | Stop merchant (no writes)      |
| Event persisted but trace missing **and repair not possible** | `TRACE_MISSING`    | Stop merchant (log failure)    |

---

## 7.8 Acceptance checklist (for this section)

* Dedupe happens **before** RNG every iteration.
* Resume sets `attempt := max+1`, `s_before := last.s_after` (or fresh base).
* Exactly one terminal outcome per merchant; terminal fence enforced on resume.
* No re-emits to repair trace; adjacency repaired by the next emitter append.
* Per-merchant single writer; counters are the only order authority.

---

# 8) Policy Handling & Terminal Outcomes (A=0 & Cap=64)

**Purpose.** Specify—unambiguously—the **only** end states L2 may drive for a merchant in **S4**, and the exact kernel(s) to call for each path. L2 never crafts payloads or calls L0; it **routes control** to the correct **L1 kernel** (which calls the L0 emitter that writes the event and appends the immediate cumulative trace).

---

## 8.1 Outcome matrix (authoritative)

| Path                 | When it triggers (value-level)              | Kernel(s) L2 must call                      | Event family written                  | Required fields (at a glance)                                                      | Notes                                                                                                        |
|----------------------|---------------------------------------------|---------------------------------------------|---------------------------------------|------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| **A=0 final-only**   | `A == 0` after gates                        | **K-1** (freeze λ,regime) → **K-6** (final) | `ztp_final` (non-consuming)           | `K_target=0`, `attempts=0`, `lambda_extra`, `regime` [, `reason` if schema allows] | **No attempts** (`poisson_component`) **and no markers** (`ztp_rejection`/`ztp_retry_exhausted`) are written |
| **Acceptance final** | First attempt *t* with `k>0`                | **K-6** (final)                             | `ztp_final` (non-consuming)           | `K_target=k≥1`, `attempts=t`, `lambda_extra`, `regime`                             | `exhausted` **absent**                                                                                       |
| **Cap-abort**        | 64 zeros and `policy=="abort"`              | **K-5** (exhausted)                         | `ztp_retry_exhausted` (non-consuming) | `attempts=64`, `aborted=true`, `lambda_extra`                                      | **No final** is written                                                                                      |
| **Cap-downgrade**    | 64 zeros and `policy=="downgrade_domestic"` | **K-6** (final)                             | `ztp_final` (non-consuming)           | `K_target=0`, `attempts=64`, `exhausted=true`, `lambda_extra`, `regime`            | **No exhausted marker**                                                                                      |

**Identity reminder.** Attempts (K-3) are **consuming** and use payload key **`lambda`**; all markers/finals (K-4/K-5/K-6) are **non-consuming** and use **`lambda_extra`**. L1 kernels enforce this and the emitter appends **one immediate** cumulative trace per event.

---

## 8.2 A=0 short-circuit (final-only)

When `A == 0` **after gates**:

1. **K-1** `freeze_lambda_regime(N, X_m, θ)` → `{lambda_extra, regime}` (value-only).
2. Derive merchant substream once (see §6).
3. **K-6** `do_emit_ztp_final(… , fin)` with `fin := {K_target:0, attempts:0, regime [,reason:"no_admissible"]}` (include `reason` only if the bound schema version defines it).
4. **Stop**—no attempts (`poisson_component`) and no markers (`ztp_rejection`/`ztp_retry_exhausted`) are written on this path.

---

## 8.3 Acceptance path (first `k>0`)

Inside the bounded loop (see §9/§10), at the first attempt index **t** such that `k>0`:

* Construct `fin := {K_target:k, attempts:t, regime}` (value level).
* Call **K-6** to emit the **non-consuming** finaliser.
* **Stop** for this merchant.
* Invariants: `exhausted` **must be absent**; no exhausted marker may follow a normal acceptance final.

---

## 8.4 Cap path (64 zeros)

If attempts **1..64** all yield `k==0`, branch by **policy**:

**a) Abort policy** (`policy=="abort"`):

* Call **K-5** to emit **only** `ztp_retry_exhausted` (non-consuming) with `attempts=64` and `aborted=true`.
* **Do not** emit a final on this path (**exhausted only**).
* **Stop**.

**b) Downgrade policy** (`policy=="downgrade_domestic"`):

* Build `fin := {K_target:0, attempts:64, regime, exhausted:true}`.
* Call **K-6** to emit the **final** (non-consuming).
* **Do not** emit an exhausted marker on this path (**final only**).
* **Stop**.

> **Cap is fixed at 64** in the current schema version: L2 treats the cap as a constant; there is no runtime override in L2.

---

## 8.5 Exclusivity & resolution fence (must hold)

* **Exactly one terminal outcome per merchant** per run:

  * acceptance final **or** exhausted marker **or** downgrade final.
* Once a terminal exists (`final_exists` **or** `exhausted_exists`), the merchant is **resolved**; the L2 loop **must not** emit anything else for that merchant (including on resume).
* On acceptance, **no** exhausted marker is permitted; on cap-abort, **no** final; on cap-downgrade, **no** exhausted marker.

---

## 8.6 Copy-ready calls (L2 → L1 kernels)

**A=0 final-only**

```text
lr  := K1.freeze_lambda_regime(ctx.N, ctx.X_m, ctx.θ0, ctx.θ1, ctx.θ2)
s0  := derive_merchant_stream(ctx.lineage, ctx.merchant_id)
fin := { K_target:0, attempts:0, regime:lr.regime [,reason:"no_admissible"] }
K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s0, lr, fin)
```

**Acceptance @ attempt t**

```text
fin := { K_target:k, attempts:t, regime:lr.regime }     # exhausted absent
K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr, fin)
```

**Cap-abort**

```text
K5.emit_ztp_retry_exhausted_nonconsuming(
    ctx.merchant_id, ctx.lineage, s, lr, policy="abort")
```

**Cap-downgrade**

```text
fin := { K_target:0, attempts:64, regime:lr.regime, exhausted:true }
K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr, fin)
```

*(In all cases the emitter, called by the kernel, writes the event and appends the **immediate** cumulative trace; L2 never touches trace.)*

---

## 8.7 Guardrails & failure mapping (policy/outcome layer)

* **Policy domain:** if `policy ∉ {"abort","downgrade_domestic"}` → `POLICY_INVALID` (stop this merchant; no writes).
* **Final/exhausted duplication:** if a terminal row already exists, treat merchant as **resolved**; skip additional terminals.
* **Misrouted cap end:** emitting both exhausted and final on the same merchant at cap end is a **hard error**; L2 must ensure exactly one per policy.

---

## 8.8 Acceptance checklist (for this section)

* A=0 emits **one** final (attempts=0) and **nothing else**.
* Acceptance emits **one** final (attempts=t), `exhausted` **absent**.
* Cap-abort emits **one** exhausted marker and **no** final.
* Cap-downgrade emits **one** final with `attempts=64`, `exhausted:true`, and **no** exhausted marker.
* Exactly one terminal per merchant; resolution fence enforced.
* L2 calls **K-1/K-5/K-6** as specified; **no direct L0 calls**; **no payload construction** in L2.

---

# 9) Downstream Emissions L2 Causes (via L1→L0)

**Purpose.** Specify exactly **what bytes hit disk** when L2 drives S4—*without* L2 crafting payloads or calling emitters directly. L2 calls **L1 kernels**; each kernel calls **one** L0 emitter that (a) writes the **event** and (b) appends **one immediate** cumulative **trace** (same writer). L2’s job is to pass the **correct stream** and **lineage** and to choose the **right kernel** at the **right time**.

---

## 9.1 Event families & identities (authoritative)

| Family (what gets written)                         | Identity        | Consuming? | Payload minima (keys that matter)                                                      | Trace                       | Notes                                                                                           |
|----------------------------------------------------|-----------------|-----------:|----------------------------------------------------------------------------------------|-----------------------------|-------------------------------------------------------------------------------------------------|
| `rng_event_poisson_component` (attempt)            | `attempt`       |    **Yes** | `{ merchant_id, attempt, k, **lambda** }`                                              | **Immediate** (same writer) | Exactly one per new attempt index; advances counters using the sampler’s measured budgets       |
| `rng_event_ztp_rejection` (zero marker)            | `attempt`       |         No | `{ merchant_id, attempt, **lambda_extra** }`                                           | **Immediate**               | Only for attempts with `k==0`; must use the current stream (before==after)                      |
| `rng_event_ztp_retry_exhausted` (cap-abort marker) | `(attempts=64)` |         No | `{ merchant_id, attempts:64, aborted:true, **lambda_extra** }`                         | **Immediate**               | Only when `policy=="abort"` and 64 zeros; **no** final follows                                  |
| `rng_event_ztp_final` (finaliser)                  | `merchant_id`   |         No | `{ merchant_id, K_target, **lambda_extra**, attempts, regime [,exhausted?, reason?] }` | **Immediate**               | A=0: attempts=0; accept: attempts=t (no `exhausted`); downgrade: attempts=64 + `exhausted:true` |

**Field discipline.** Attempts **use `lambda`**; markers/final **use `lambda_extra`**. L2 never builds these payloads—**L1 kernels do**.

---

## 9.2 What L2 must pass to kernels (and only this)

* **Lineage tokens (value-only):** `{ seed, parameter_hash, run_id, manifest_fingerprint }`. L0 will stamp these into the event envelope and the trace row.
* **Stream handle:**

  * **Attempts (K-3):** pass `s_before` and `s_after` returned by K-2; this enforces consuming semantics and correct budget accounting.
  * **Markers/finals (K-4/K-5/K-6):** pass **current** stream `s_curr` (non-consuming → `before==after`, `blocks=0`, `draws="0"`).
* **No paths.** All paths/partitions are dictionary-resolved by L0; L2 provides **values only**.

---

## 9.3 Family-by-family effects (what your kernel call causes)

* **K-3 → `poisson_component` (attempt, consuming).**
  Writes one event for the attempt and appends one **immediate** cumulative trace. Counters advance according to the sampler’s **measured** budgets; L2 **never** infers budgets.

* **K-4 → `ztp_rejection` (non-consuming).**
  Writes one marker for that `attempt` and appends the immediate trace; counters do **not** advance (before==after).

* **K-5 → `ztp_retry_exhausted` (non-consuming).**
  Writes the abort terminal marker with `attempts=64, aborted:true` and appends the immediate trace. **No** `ztp_final` is permitted afterward.

* **K-6 → `ztp_final` (non-consuming).**
  Writes the finaliser and appends the immediate trace. Variants:

  * A=0 → `{K_target=0, attempts=0 [,reason?]}`
  * Accept@t → `{K_target=k≥1, attempts=t}` (no `exhausted`)
  * Cap-downgrade → `{K_target=0, attempts=64, exhausted:true}`

---

## 9.4 Natural keys, partitions & writer sorts (skip/resume primitives)

* **Natural keys** L2 uses for dedupe/skip:

  * Attempt: `(merchant_id, attempt)`
  * Rejection: `(merchant_id, attempt)`
  * Exhausted: `(merchant_id, attempts=64)`
  * Final: `(merchant_id)`

* **Partitions (events & trace):** `{ seed, parameter_hash, run_id }` (stamped by L0).
  **Path↔embed equality** is enforced by the emitter; L2 just passes **values**.

* **Writer order:** file order is **not** authoritative; **envelope counters** define total order. L2 must respect **one event → one immediate trace** adjacency by using kernels only.

---

## 9.5 What L2 must never do (to keep emissions correct)

* **Never** call L0 emitters directly.
* **Never** craft or mutate payloads (`lambda` vs `lambda_extra`, `attempts`, flags).
* **Never** estimate budgets or fabricate counters; use the sampler’s measured budgets and the stream returned by K-2 (or the persisted `s_after`).
* **Never** emit more than **one** terminal outcome per merchant.
* **Never** re-emit an event to repair a missing trace; adjacency is repaired on the next emitter append.

---

## 9.6 Copy-ready “cause & effect” (L2 → L1)

```text
# Attempt (new index)
(k, s_after, bud) := K2.do_poisson_attempt_once(lr, s_before)         # RNG-consuming
K3.emit_poisson_attempt(merchant_id, lineage, s_before, s_after, lr, attempt, k, bud)
# → writes rng_event_poisson_component + immediate trace; counters advance

# Rejection (k == 0 and row missing)
K4.emit_ztp_rejection_nonconsuming(merchant_id, lineage, s_after, lr, attempt)
# → writes rng_event_ztp_rejection + immediate trace; non-consuming (before==after)

# Cap-abort terminal (64 zeros)
K5.emit_ztp_retry_exhausted_nonconsuming(merchant_id, lineage, s, lr, policy="abort")
# → writes rng_event_ztp_retry_exhausted + immediate trace; no final allowed afterward

# Finaliser (A=0, accept, or downgrade)
K6.do_emit_ztp_final(merchant_id, lineage, s_curr, lr, fin)
# → writes rng_event_ztp_final + immediate trace; non-consuming (before==after)
```

This is the **only** set of emissions L2 can cause in S4. Everything else (payload assembly, envelope stamping, trace adjacency, partitions, counters) is guaranteed by the L1→L0 surfaces you’ve frozen.

---

# 10) Main Attempt Loop Contract (Bounded 1..64)

**Purpose.** Pin the exact, reproducible control flow L2 must execute for attempts **1..64**—using **kernels only**—and the identities the emitters must satisfy. No payload crafting or direct L0 calls here; L2 passes **values + stream** and calls the right **K-** kernel at the right time.

---

## 10.1 Loop shape (authoritative)

* **Start:** `attempt := resume_attempt_index(merchant_id)` (1 if none on disk; else `max+1`) and `s_before := resume_stream_or_fresh(ctx)` (persisted `s_after` if any; else merchant `s0`). See §7.

* **Bound:** iterate **attempt ∈ {1,…,64}**; 64 is **schema-pinned** for the exhausted marker (`attempts:64`). 

* **Per-iteration contract:**

  1. **Pre-emit dedupe:** if the attempt row exists → read `{k, s_after}` and **do not** sample; else
     **K-2**: `(k, s_after, bud) := do_poisson_attempt_once(lr, s_before)` (RNG-consuming; no I/O). 
  2. If we sampled in step (1), **K-3**: `emit_poisson_attempt(…, s_before, s_after, lr, attempt, k, bud)` (consuming **attempt**; payload key `lambda`; **immediate** trace). 
  3. **Branch:**
     - If `k > 0` → **K-6** finaliser `{K_target=k, attempts=attempt}` (non-consuming; **no `exhausted`**) and **return**. 
     - Else (`k == 0`) → ensure one **K-4** rejection for this index (non-consuming; `lambda_extra`; **immediate** trace). 
  4. **Advance:** `s_before := s_after` and continue.

* **Cap reached (no acceptance by 64):**
  - If `policy=="abort"` → **K-5** exhausted only (`attempts=64`, `aborted:true`) and **stop**.
  - Else (`"downgrade_domestic"`) → **K-6** finaliser `{K_target=0, attempts=64, exhausted:true}` and **stop**. 

---

## 10.2 Identities the emitters enforce (L0 truth)

* **Consuming attempt (`poisson_component`, context:"ztp")**: `after > before`, `blocks = after−before`, **`draws > "0"`**; budgets are **measured**, not inferred (inversion: exactly `K+1` uniforms; PTRS: variable ≥2). 
* **Non-consuming (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`)**: `before == after`, `blocks = 0`, **`draws = "0"`**. 
* **Trace adjacency:** after **each** event append, the **same writer immediately appends one** cumulative `rng_trace_log` row for `(module, substream_label)`; no other sink may emit trace rows. 

---

## 10.3 Stream discipline (what L2 must pass)

* **K-2/K-3 (attempt):** pass both `s_before` and the returned `s_after` + `bud` (actual-use budgets). L2 must **not** fabricate counters or budgets. 
* **K-4/K-5/K-6 (non-consuming):** pass the **current** stream `s_after` (identity: `before==after`, `draws="0"`, `blocks=0`). 
* **One stream per merchant:** all S4 families share `(module="1A.s4.ztp", substream_label="poisson_component")`; trace rows share the same domain; **no cross-label chaining**. 

---

## 10.4 Legal/illegal actions (per iteration)

| Step         | **Must**                                              | **Must not**                                                   |
|--------------|-------------------------------------------------------|----------------------------------------------------------------|
| Dedupe       | Skip sampling if attempt exists; read `{k,s_after}`   | Resample an existing attempt                                   |
| Sample       | Call **K-2** once; use returned `bud`                 | Infer budgets; modify counters                                 |
| Emit attempt | Call **K-3**; attempts use `lambda`                   | Use `lambda_extra` on attempts                                 |
| Reject       | Call **K-4** once per zero; non-consuming             | Advance counters; emit multiple rejections for same index      |
| Accept       | Call **K-6**; final only; stop                        | Add `exhausted`; emit exhausted after final                    |
| Cap          | Call **K-5** (abort) **or** **K-6** (downgrade); stop | Emit both exhausted and final; omit `attempts:64` on exhausted |

---

## 10.5 Copy-ready loop (kernels only)

**Single-writer discipline (this merchant):** serialize emits; after each event append, the **same writer immediately appends one** cumulative trace row (no interleaving).

```text
FOR attempt IN resume_attempt_index(merchant_id) .. 64:
  pre := pre_emit_dedupe(merchant_id, attempt)        # §7; maybe {k, s_after}
  IF pre != null:
     k := pre.k; s := pre.s_after
  ELSE:
     (k, s_after, bud) := K2.do_poisson_attempt_once(lr, s)
     K3.emit_poisson_attempt(merchant_id, lineage, s, s_after, lr, attempt, k, bud)
     s := s_after

  IF k > 0:
     K6.do_emit_ztp_final(merchant_id, lineage, s, lr, {K_target:0, attempts:64, exhausted:true})
     RETURN

  IF NOT exists_rejection(merchant_id, attempt):
     K4.emit_ztp_rejection_nonconsuming(merchant_id, lineage, s, lr, attempt)
# end loop

IF policy == "abort":
   IF NOT exists_exhausted(merchant_id):
      K5.emit_ztp_retry_exhausted_nonconsuming(merchant_id, lineage, s, lr, policy="abort")
ELSE:
   IF NOT exists_final(merchant_id):
      K6.do_emit_ztp_final(merchant_id, lineage, s, lr, {K_target:0, attempts:64, exhausted:true})
RETURN
```

This loop contract, together with §6-§9 and the identities above, is sufficient for any implementer/LLM to produce **byte-identical**, validator-passing S4 runs. It is anchored to **L1 v12** (kernel surfaces & attempt payload `lambda`) and **L0 v15** (consuming/non-consuming identities, trace adjacency, budgets), with the cap and A=0 semantics mandated by the **expanded S4** spec.  

---

# 11) Concurrency & Single-Writer Discipline

**Purpose.** Make parallel runs **safe and byte-identical**. L2 must serialize **within** a merchant, parallelize **across** merchants, and respect the writer’s **one-event → one-immediate-trace** contract. Ordering is by **counters**, not file order.  

---

## 11.1 Per-merchant serialism (non-negotiable)

* The S4 attempt loop is **single-threaded** per merchant with a fixed iteration order (attempts 1..64, contiguous). Do **not** overlap two K-7 loops for the same `(seed, parameter_hash, run_id, merchant_id)`. 
* Counters—not timestamps or file order—define the total order; resume uses the **persisted `s_after`** for the last attempt. 

## 11.2 Across-merchant parallelism (allowed, with guardrails)

* You **may** run many merchants in parallel. Any writer/merge must be **stable** with respect to the family’s sort keys so identical inputs yield **byte-identical** outputs. 
* Recommended: shard by merchant ranges; keep deterministic scheduling (e.g., ascending `merchant_id`) if your infra’s merge order is not proven stable. 

## 11.3 Single-writer adjacency (event→trace)

* For **every** S4 event, the **same writer** must append **exactly one** cumulative `rng_trace_log` row **immediately after** the event append (saturating totals). No other sink may emit trace rows. L2 **never** writes trace.  
* Identities are enforced by the emitter: attempts are **consuming** (`after>before`, `blocks=Δ>0`, `draws>"0"`); markers/final are **non-consuming** (`before==after`, `blocks=0`, `draws="0"`). 

## 11.4 Locks, fences & who owns what

* **Per-merchant lock (L2):** acquire before K-7; release after terminal outcome. Prevents two orchestrations for the same merchant. (Terminal fence: if `final` **or** `exhausted` exists, merchant is resolved—skip.) 
* **Writer fence (L0):** the *(event, trace)* pair is a hard serialization point; do not interleave other writes between them. 

## 11.5 Merges & file layout

* **Stable merge**: if writers spill sorted chunks, a final **stable** merge per partition must preserve the effective order for each family’s natural keys (`(merchant_id, attempt)` for attempts & rejections; `(merchant_id, attempts=64)` for exhausted; `(merchant_id)` for final). 
* **Dictionary-resolved partitions** `{seed, parameter_hash, run_id}`; path↔embed equality is enforced by the emitter. L2 passes **values only**. 

## 11.6 Crash windows (no re-emit)

* If an event persisted but its trace is missing, L2 must **not** re-emit the event. The next emitter append will repair the trace using the persisted envelope. If repair is impossible, surface the standardized failure and stop for that merchant. 

## 11.7 Copy-ready policy for the orchestrator

* **Acquire:** `lock(mid)` before `orchestrate_s4_for_merchant`.
* **Check resolution:** if `final_exists(mid)` **or** `exhausted_exists(mid)` → `unlock(mid)` and **return**.
* **Run:** execute K-7 serially for the merchant; inside the loop, call only **K-2/K-3/K-4**, then **K-6** (accept) or **K-5/K-6** (cap end) per policy. 
* **Release:** `unlock(mid)` immediately after the terminal is written (no further S4 writes allowed for that merchant).

## 11.8 Back-pressure & limits (operator guidance)

* Bound **in-flight merchants** to keep writer queues from merging out-of-order; use a worker cap `C` sized so the trace writer remains immediate. Avoid tiny files; batch reasonable row-groups. 

---

## 11.9 Acceptance checklist (freeze gate for §11)

* Per-merchant **single-threaded** K-7; no overlapping loops. 
* Across-merchant **parallel OK** with **stable** merges. 
* **One event → one immediate trace (same writer)** invariant held. 
* **Counters define order**; file order non-authoritative. 
* **Resolution fence**: once terminal exists, merchant is done. 
* L2 **never** writes trace or calls L0 directly; values-only handoff to kernels; partitions are dictionary-resolved. 

These rules align exactly with the **S4 expanded** concurrency doctrine and the **L0 v15** writer/trace contract, ensuring reproducible, byte-identical output at scale.  

---

# 12) Store Interfaces (Read-Only)

**Purpose.** Specify the **exact read-only queries** L2 uses to dedupe, resume, branch, and fence terminals—without crafting payloads or touching emitters. All reads are **value-level** and **dictionary-resolved** under the logs’ partitions; L2 never uses path literals. Events are written by L1→L0; L2 only **observes** them.  

---

## 12.1 Datasets L2 reads (IDs, partitions, writer sort)

| Family (Dictionary ID)                 | Partitions (logs)                | Natural writer sort (for scans)                                   |
|----------------------------------------|----------------------------------|-------------------------------------------------------------------|
| `rng_event_poisson_component`          | `{seed, parameter_hash, run_id}` | `["merchant_id","attempt"]`                                       |
| `rng_event_ztp_rejection`              | `{seed, parameter_hash, run_id}` | `["merchant_id","attempt"]`                                       |
| `rng_event_ztp_retry_exhausted`        | `{seed, parameter_hash, run_id}` | `["merchant_id","attempts"]`                                      |
| `rng_event_ztp_final`                  | `{seed, parameter_hash, run_id}` | `["merchant_id"]`                                                 |
| `rng_trace_log` (read rarely; see §13) | `{seed, parameter_hash, run_id}` | cumulative per `(module, substream_label)` (no mandated row sort) |

These partitions and sorts are **authoritative**; emitters enforce **path↔embed** equality, and the trace is appended **immediately** after each event by the **same writer**.  

---

## 12.2 Natural keys & minimal projections (what to fetch)

| Purpose                          | Dataset               | Natural key                  | Minimal projection                                            |
|----------------------------------|-----------------------|------------------------------|---------------------------------------------------------------|
| Existence / branch on attempt    | `poisson_component`   | `(merchant_id, attempt)`     | `{ k:int, s_after:Stream }`                                   |
| Ensure one rejection per attempt | `ztp_rejection`       | `(merchant_id, attempt)`     | `exists_only`                                                 |
| Terminal fence (abort)           | `ztp_retry_exhausted` | `(merchant_id, attempts=64)` | `exists_only`                                                 |
| Terminal fence (final)           | `ztp_final`           | `(merchant_id)`              | `{ K_target:int, attempts:int, regime:str, exhausted?:bool }` |
| Resume index                     | `poisson_component`   | `merchant_id` (range)        | `max(attempt)` per merchant                                   |

> **Why these shapes:** L2 needs only `{k, s_after}` to **branch** and **advance** deterministically; all payload construction remains in L1. Terminals are keyed so one row settles a merchant.  

---

## 12.3 Canonical predicates (value-level; dictionary-resolved)

All queries are **scoped by lineage** and merchant:

```
WHERE seed = :seed AND parameter_hash = :parameter_hash AND run_id = :run_id
  AND merchant_id = :merchant_id
```

Then per family:

* **Attempt exists / read**
  `FROM rng_event_poisson_component WHERE attempt = :a` → projection `{k, s_after}`.
  *(If present, skip K-2; branch using `k`; set `s_before := s_after`.)* 

* **Rejection exists**
  `FROM rng_event_ztp_rejection WHERE attempt = :a` → boolean. *(Used to avoid duplicate K-4.)*

* **Exhausted exists**
  `FROM rng_event_ztp_retry_exhausted WHERE attempts = 64` → boolean. *(Abort path terminal.)*

* **Final exists / read K**
  `FROM rng_event_ztp_final` (latest by key) → `{K_target, attempts, regime, exhausted?}`. *(Terminal fence + reporting.)*

* **Max attempt**
  `SELECT MAX(attempt) FROM rng_event_poisson_component` for `(seed, parameter_hash, run_id, merchant_id)`. *(Resume at `max+1`.)*

These are **read-only**; L2 never mutates rows or envelopes. File order is **non-authoritative**—envelope **counters** define total order. 

---

## 12.4 Existence helpers (L2 surface, semantics)

Define read-only helpers with clear idempotence:

```text
exists_attempt(mid, a)        -> bool
exists_rejection(mid, a)      -> bool
exists_final(mid)             -> bool
exists_exhausted(mid)         -> bool
max_attempt(mid)              -> int | null
read_attempt_k_after(mid, a)  -> { k:int, s_after:Stream }   # exact persisted projection
read_final_K(mid)             -> int                         # K_target from final row
```

*Rules:*

* **Deduplicate before RNG:** if `exists_attempt(mid,a)` → **do not** call K-2; use `read_attempt_k_after` to branch. 
* **Terminal fence:** if `exists_final(mid)` **or** `exists_exhausted(mid)` → merchant is **resolved**; L2 writes nothing more. 

---

## 12.5 Resume recipe (index + stream)

1. If terminal exists → **return** (resolved).
2. `t_max := max_attempt(mid)` → `attempt := (t_max == null ? 1 : t_max + 1)`.
3. If `t_max == null` → `s_before := derive_merchant_stream(...)`; else `s_before := read_attempt_k_after(mid, t_max).s_after`.
   *(Never resample existing attempts; never fabricate counters.)* 

---

## 12.6 Trace read (rare) & repair note

L2 normally **does not** read trace. If ops suspects “event persisted, trace missing,” L0 provides a **trace-only repair** path on the next emit; L2 should **not re-emit** the event. If a repair is impossible, surface a standardized failure and stop for the merchant. 

---

## 12.7 What L2 must **not** do at the store layer

* No path literals; **dictionary-resolved** datasets only.
* No payload reconstruction from store rows beyond `{k, s_after}` and terminal fields; **no** “budget inference.”
* No direct writes; **all** emission is via kernels → L0 emitters (which stamp envelope & append immediate trace). 

---

## 12.8 Acceptance checklist (freeze gate for §12)

* All queries scoped by `{seed, parameter_hash, run_id, merchant_id}`. 
* Natural keys and projections match the table in §12.2. 
* Dedupe-before-RNG is implementable using `exists_*` + `read_attempt_k_after`. 
* Terminal fence enforced using `exists_final` / `exists_exhausted`. 
* No trace writes or event re-emits from L2; repair is emitter-side. 

This store-interface surface gives the orchestrator **everything** it needs to be idempotent and deterministic while staying strictly within the **L0 v15** writer/trace contract and your **L1 v12** kernel semantics.  

---

# 13) Crash-Safety & Trace-Repair Semantics

**Purpose.** Define exactly what can break on a crash, what L2 is allowed to fix, and how to resume **byte-identically** without corrupting counters, envelopes, or traces. L2 never re-emits events; it only resumes or triggers **trace-only** repair through the L0/L1 surfaces already defined.  

---

## 13.1 The only legal crash window

* **Events are transactional.** Either the event row (payload + envelope) is fully written, or it isn’t present at all. 
* **Traces may be missing.** The sole allowed half-done state is: **“event persisted, adjacent cumulative trace missing.”** This can happen if a crash occurs **after** the event fsync and **before** the immediate trace append by the same writer. 

**Never re-emit the event.** Repairs append **one** missing trace derived from the persisted event envelope (its `before/after` counters & `draws`). 

---

## 13.2 What L0/L1 guarantee (why repair is trace-only)

* **Adjacency is an invariant:** **one event → one immediate cumulative trace** by the **same writer**; no interleaving labels between them. 
* **Identities are authoritative:** attempts are **consuming** (`after>before`, `blocks>0`, `draws>"0"`); markers/final are **non-consuming** (`before==after`, `blocks=0`, `draws="0"`). These are **stamped by L0**. 
* **Ordering authority:** file order is not authoritative; **envelope counters** define total order. 

---

## 13.3 What L2 must do on resume (decision table)

| On-disk observation (scoped by `{seed, parameter_hash, run_id, merchant_id}`) | L2 action                                                                       |
|-------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| `ztp_final` exists *(any payload)*                                            | **Stop** for this merchant (resolved).                                          |
| `ztp_retry_exhausted{attempts:64,aborted:true}` exists and **no** final       | **Stop** (abort path resolved).                                                 |
| An **event** exists **without** its adjacent trace                            | Trigger **trace-only repair** once (see 13.4). **Do not** re-emit the event.    |
| Partial progress (some attempts/rejections), **no** terminal                  | **Continue** with §7 Pattern-A/Pattern-B idempotent resume (dedupe before RNG). |

---

## 13.4 Trace-only repair (the one repair L2 may cause)

**When:** you detect an event row for which the immediate cumulative trace row is missing.
**What L2 does:** **Resume only**; L2 performs **no writes**. The **next emitter append** (any family) will append the missing cumulative trace using the persisted event envelope in the same `(module, substream_label)` domain (trace has **no `context`**).

**Semantics:** Counters in the persisted event envelope remain the single source of ordering. Repair is idempotent and owned by the writer that appends the next event’s trace.

> L2 must **never** re-emit the original event to fix a missing trace; doing so would double-advance counters and violate consuming/non-consuming identities. 

---

## 13.5 Copy-ready repair & resume snippet (value-level; no emitters)

```text
# Called at the start of orchestrate_s4_for_merchant(ctx)
IF exists_final(mid) OR exists_exhausted(mid): RETURN RESOLVED

# Optional: scan last event for this merchant to detect missing-adjacent-trace
# Optional: detect "event without adjacent trace" for ops visibility only.
# Do not write or call any trace writer from L2. Simply resume.
# proceed to §7 resume (dedupe-before-RNG) and §10 loop
```

* `last_event_without_adjacent_trace` is an **ops helper** that inspects the expected event→trace adjacency per domain; if non-portable, skip it—repair will still happen at the next emitter append. 

---

## 13.6 Guardrails & failure mapping

* **TRACE_MISSING (unrepairable).** If the store cannot locate the event envelope needed to compute the missing trace (e.g., corrupted partition), surface a standardized failure and **stop** S4 for that merchant; do not synthesize counters. 
* **ATTEMPT_GAPS.** If attempts on disk are non-contiguous (e.g., 1,2,4), stop this merchant and escalate; do **not** fabricate attempt 3. 
* **POLICY_INVALID / NUMERIC_INVALID.** If policy is out of domain or `λ` fails numeric guards at K-1, **emit nothing** and stop for this merchant. 

---

## 13.7 Acceptance checklist (freeze gate for §13)

* L2 **never** re-emits events; **trace-only** repair is the sole permitted fix. 
* After the next successful emit, **event→trace adjacency** is restored (same writer, immediate). 
* All resumes use §7 rules: **dedupe before RNG**, counters define order, stream resumes from **persisted `s_after`**. 
* Exactly **one terminal** per merchant; terminal fence enforced before any repair or resume. 

These rules align exactly with your L1 contract (idempotence, adjacency, identities) and L0’s writer/trace guarantees, ensuring crashes never produce counter drift or duplicate bytes—and that repairs are deterministic and auditable.  

---

# 14) Failure Handling & Escalation (Standardized)

**Purpose.** Give L2 a **deterministic playbook** for what to do when things go wrong—using the *same* codes, scopes, and artefacts across the engine. L2 does **not** craft payload bytes or stamp files itself; it classifies, **stops correctly**, and routes to the **S0 failure framework** where applicable. Merchant-level failures quarantine the merchant; run-level failures abort the run.  

---

## 14.1 Principles (binding)

* **Fail fast; emit nothing** for that merchant once a blocking failure is detected. 
* **Stop on first failure** at the merchant scope; do not “accumulate” errors. 
* **Never re-emit** an already written event to “fix” anything; the only repair allowed is **trace-only** (see §13). 
* **Scopes:** failures are **RUN**, **DATASET**, or **MERCHANT** scoped; the scope controls escalation (abort vs quarantine). 
* **Taxonomy & artefacts come from S0** (single source of truth for payload, locations, atomics).  

---

## 14.2 Canonical failure set (S4 orchestration surface)

| Code (who detects)                      | Where it happens  | Condition (examples)                                                                                                                  |      Scope      | L2 action                                                                                        |
|-----------------------------------------|-------------------|---------------------------------------------------------------------------------------------------------------------------------------|:---------------:|--------------------------------------------------------------------------------------------------|
| **POLICY_CONFLICT (gate)** *(L1/L2)*    | Preflight         | `is_eligible!=true`, invalid S3 ranks (home≠0/contiguity), `is_multi!=true`, `N<2`, `A<0`, or `policy∉{"abort","downgrade_domestic"}` |    MERCHANT     | **Quarantine** merchant; no S4 rows.                                                             |
| **NUMERIC_INVALID** *(K-1)*             | Freeze λ/regime   | `λ` non-finite or `≤0` (pure guard)                                                                                                   |    MERCHANT     | **Quarantine**; emit nothing.                                                                    |
| **RNG_SAMPLER_FAIL** *(K-2)*            | Sampler capsule   | Capsule throws / budget measurement fails                                                                                             |    MERCHANT     | **Quarantine**; collect sampler diagnostics.                                                     |
| **EMIT_FAIL** *(emitters)*              | Event write       | I/O failure writing **event** row (transactional)                                                                                     | MERCHANT or RUN | **Quarantine** merchant; if systemic writer/partition drift → escalate to S0 run-abort (F10/F5). |
| **TRACE_APPEND_FAIL** *(emitters)*      | After event write | Event fsynced; trace append failed/crashed                                                                                            |    MERCHANT     | **Do not re-emit** event; **trace-repair once** (see §13) then resume.                           |
| **ATTEMPT_GAPS** *(L2)*                 | Resume scan       | Attempts on disk non-contiguous (e.g., 1,2,4)                                                                                         |    MERCHANT     | **Stop** merchant; surface standardized failure; operator triage.                                |
| **POLICY_CONFLICT (logic)** *(K-5/K-6)* | Cap routing       | Abort policy but finaliser attempted; or downgrade policy but exhausted attempted                                                     |    MERCHANT     | **Quarantine** merchant; fix orchestration.                                                      |

> **Run-level** structural/systemic breaches (dictionary/path, numeric policy, coverage corridors) are handled by S0 classes **F7-F10**: `numeric_rounding_mode|fma_detected|…` (F7), `event_family_missing|corridor_breach` (F8), `dictionary_path_violation` (F9), `io_write_failure|incomplete_dataset_instance` (F10). L2 must surface these via S0’s failure framework and abort the run. 

---

## 14.3 What L2 does for each class

* **Merchant-scoped failures** (policy gate, numeric invalid, sampler fail, logic conflict, attempt gaps):
  *Action:* **stop S4 for that merchant now** (no further rows), record metrics, continue with other merchants. 

* **I/O/trace anomalies** (event written, trace missing):
  *Action:* **do not** re-emit event; invoke **trace-only repair** exactly once, then resume (§13). 

* **Run-scoped failures** (S0 F7-F10):
  *Action:* call S0 failure framework → **abort bundle**; halt emitters; stop run atomically.  

---

## 14.4 Standard payload (S0 artefact) & routing

L2 does **not** craft failure JSON. When a run- or dataset-level abort is required, L2 routes through S0’s canonical surfaces:

* `L0.build_failure_payload(failure_class, failure_code, ctx)` → canonical JSON (stable keys, no floats, no PII/paths).
* `L0.abort_run_atomic(payload, partial_partitions[])` → writes `validation/failures/fingerprint={...}/seed={...}/run_id={...}/failure.json` atomically.
* Optional merchant-abort log (parameter-scoped): `L0.merchant_abort_log_write(rows, parameter_hash)`. 

S3’s validator taxonomy (shape/keys/scopes) is the precedent for stable payloads and routing. 

---

## 14.5 Decision tree (L2—operational)

1. **Resolution fence first:** if `final_exists(mid)` or `exhausted_exists(mid)` → **skip merchant** (resolved). 
2. **Gates:** if any gate fails → **POLICY_CONFLICT (gate)** → **quarantine**; no S4 rows. 
3. **Freeze λ:** if **K-1** raises **NUMERIC_INVALID** → **quarantine**. 
4. **Loop:**

   * If sampler throws → **RNG_SAMPLER_FAIL** → **quarantine**. 
   * Emit attempt; if accept → final & **stop**.
   * Emit rejection; advance.
5. **Cap:** at 64 zeros → route by policy: **K-5** (abort) *or* **K-6** (downgrade). If mixed → **POLICY_CONFLICT (logic)** → **quarantine**. 
6. **Crash on append:** event present, trace missing → **trace-repair once**; resume. 
7. **Systemic breach:** dictionary/path/numeric policy/corridor → S0 **F7-F10** run-abort. 

---

## 14.6 Retry policy (when to resume vs rerun)

* **Pure input/math failures** (`POLICY_CONFLICT`, `NUMERIC_INVALID`, `RNG_SAMPLER_FAIL`): **do not retry in the same run**; fix inputs/config; rerun merchant in a new run. 
* **I/O/trace failures** (`EMIT_FAIL`, `TRACE_APPEND_FAIL`): safe to **resume in the same run** using idempotent rules; **never** re-emit an event; if a terminal exists, **skip** the merchant. 

---

## 14.7 Merchant vs Run examples (ground truth)

* **Merchant quarantine (no rows):** K-1 computes `λ=NaN` → **NUMERIC_INVALID** → merchant skipped; no S4 logs written. 
* **Merchant resolved (abort):** 64 zeros + `policy="abort"` → **exhausted** written (`attempts:64, aborted:true`) → terminal fence; on resume, skip merchant. 
* **Run abort:** L0 detects **partition/path drift** or **I/O atomics** breach → S0 **F9/F10** → single failure bundle under `validation/failures/...` and process halts. 

---

## 14.8 Acceptance checklist (freeze gate for §14)

* [ ] Merchant failures **quarantine** only that merchant; no further S4 writes for it this run. 
* [ ] Run-level breaches escalate via S0 **Batch-F** surfaces to a single atomic failure bundle. 
* [ ] No re-emits; **trace-only** repair is the sole allowed fix for the crash window. 
* [ ] Cap semantics enforced (abort → exhausted only; downgrade → final with `exhausted:true`); **never both terminals**. 
* [ ] Natural keys remain unique; counters define order; L2 never crafts payloads or calls L0 directly. 

---

# 15) Telemetry & Run Metrics (Operator-Facing)

**Purpose.** Make runs observable in a way that is **stable, low-cardinality, values-only**, and **byte-safe**. Emission happens **after** successful event+immediate-trace fsync by the **same writer**; L2 never stamps bytes. L2’s duties here are: wire the metrics sink, call the **“once”** counters at the right moments, and ensure emission points in the loop are hit exactly once per event/outcome.

---

## 15.1 Lineage dimensions (MUST carry on every metric)

```
{ seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 [, merchant_id?:i64] }
```

*`merchant_id` is optional and only for low-volume/debug runs.*

---

## 15.2 Minimal counters & gauges (MUST)

| Key                              | Type    | What it counts (run-scoped; increment sites)                      |
|----------------------------------|---------|-------------------------------------------------------------------|
| `s4.merchants_in_scope`          | counter | # merchants that entered S4 (call **once**, after gates)          |
| `s4.accepted`                    | counter | # merchants that wrote an **acceptance final**                    |
| `s4.short_circuit_no_admissible` | counter | # merchants A=0 **final-only**                                    |
| `s4.downgrade_domestic`          | counter | # merchants **cap-downgrade** final                               |
| `s4.aborted`                     | counter | # merchants **cap-abort** (exhausted marker; no final)            |
| `s4.rejections`                  | counter | Total **zero draws** (increment after each `ztp_rejection`)       |
| `s4.attempts.total`              | counter | Total **attempt rows** (increment after each `poisson_component`) |
| `s4.trace.rows`                  | counter | Total **trace rows** appended (== total event rows)               |
| `s4.regime.inversion`            | counter | # merchants whose λ froze to **inversion**                        |
| `s4.regime.ptrs`                 | counter | # merchants whose λ froze to **PTRS**                             |

**Who emits:**

* L2 calls **`metrics_enter_scope`** once after gates; **`metrics_record_regime_once`** after K-1 (freeze λ/regime).
* The emitter (via L1) calls **`metrics_after_event_append`** after **every** event+trace pair (increments `attempts.total`, `rejections`, `trace.rows`).

---

## 15.3 Distributions / histograms (SHOULD)

| Key                       | Kind      | Definition & when to emit                                                                                                |
|---------------------------|-----------|--------------------------------------------------------------------------------------------------------------------------|
| `s4.attempts.hist`        | histogram | Attempts per merchant at resolution (accept → `t`; A=0 → `0`; cap-paths → `64`). Emit **once per merchant** at terminal. |
| `s4.lambda.hist`          | histogram | Bucketed `λ_extra` (e.g., log buckets). Emit **once per merchant** at terminal.                                          |
| `s4.ms.poisson_inversion` | histogram | Elapsed ms spent in **inversion** sampler (optional; per merchant).                                                      |
| `s4.ms.poisson_ptrs`      | histogram | Elapsed ms spent in **PTRS** sampler (optional; per merchant).                                                           |

*If you instrument per-attempt timings, have L2 time **K-2** and call `metrics_observe_ms(regime, elapsed_ms)` once per merchant (e.g., sum or P95) to keep cardinality bounded.*

---

## 15.4 Derived rates (SHOULD; computed by metrics layer)

```
s4.accept_rate  = s4.accepted / s4.merchants_in_scope
s4.cap_rate     = s4.aborted  / s4.merchants_in_scope
s4.mean_attempts = s4.attempts.total / s4.merchants_in_scope
```

---

## 15.5 Per-merchant summary (SHOULD)

Emit exactly **one** values-only summary for each **resolved** merchant (omit on hard abort):

```json
s4.merchant.summary = {
  "merchant_id":   i64,
  "attempts":      int,        // 0 for A=0; t for accept; 64 for cap paths
  "accepted_K":    int,        // 0 for A=0 or downgrade; k≥1 for accept
  "regime":        "inversion"|"ptrs",
  "exhausted":     bool,       // true only on downgrade path
  "reason":        "no_admissible"   // OPTIONAL; include only if bound schema version defines it
}
```

---

## 15.6 Emission points & who is responsible (MUST)

* **Once per merchant (L2):**

  * After gates pass: `metrics_enter_scope(dims)`
  * After **K-1** freezes λ/regime: `metrics_record_regime_once(dims, lr.regime)`

* **After every event+trace (emitter via L1; same writer):**

  * `metrics_after_event_append(dims, family)` where `family ∈ {"poisson_component","ztp_rejection","ztp_retry_exhausted","ztp_final"}`
  * This is where `s4.attempts.total`, `s4.rejections`, `s4.trace.rows` are incremented.

* **At terminal (emitter via L1):**

  * **Accept/A=0/Downgrade:** `metrics_on_final(dims, K_target, attempts, regime, lambda_extra, exhausted, reason_opt)`
  * **Cap-abort:** `metrics_on_cap_abort(dims, attempts=64)`

*All emissions are **values-only**; no paths/URIs; keys/names exactly as listed above.*

---

## 15.7 Cardinality & privacy (MUST)

* **Values-only**; no file paths, URIs, or free-text beyond stable enums.
* **Bounded cardinality:** run lineage dims + optional `merchant_id`; no high-cardinality labels.
* **No PII.** IDs only; `reason` is a closed enum when present.

---

## 15.8 Alerting hints (informative)

* **Cap rate spike** (e.g., `s4.cap_rate > 0.01`) → check θ or `X_m` scaling/cohorts.
* **Mean attempts ↑** or **rejections ↑** → indicative of low λ; examine cohorts with small `N` or `X_m`.
* **Regime split drift** → verify λ<10 switch and constants.
* Any **`NUMERIC_INVALID` > 0** → input/overflow issue; block release until resolved.

---

## 15.9 Acceptance checklist (freeze gate for §15)

* [ ] Every metric line carries `{seed, parameter_hash, run_id, manifest_fingerprint}` (and optional `merchant_id`).
* [ ] `s4.merchants_in_scope` and `s4.regime.*` increment **once per merchant** at the right moments.
* [ ] `s4.attempts.total`, `s4.rejections`, `s4.trace.rows` increment **after** event+trace fsync by the same writer.
* [ ] Exactly one per-merchant summary emitted at terminal (omit on hard abort).
* [ ] Cardinality/PII rules respected; no payload reconstruction in L2; no direct L0 calls.

---

# 16) Performance & Run Discipline

**Purpose.** Run S4 at scale **without** violating invariants (adjacent trace, consuming vs non-consuming identities, counter order, single terminal per merchant). L2 improves throughput only via **orchestration choices**—never by crafting payloads or touching emitters.

---

## 16.1 Throughput levers L2 is allowed to use

* **Across-merchant parallelism:** run many merchants in parallel.
* **Within-merchant serialism:** one K-7 loop per merchant; attempts 1..64 are contiguous and single-threaded.
* **Dedupe-before-RNG:** skip sampling for persisted attempts; this removes useless sampler work on resume.
* **Early terminals:** return immediately on acceptance; short-circuit A=0 path up front.

---

## 16.2 Batching & I/O shape (safe defaults)

* **Batch between merchants, never within an event→trace pair.** Let the emitter finish *event + immediate cumulative trace* as one atomic unit; do not interleave unrelated writes between the two.
* **Stable merges:** if your sink merges chunk files, require a *stable* merge with the family’s writer keys (attempts/rejections keyed by `(merchant_id, attempt)`, exhausted by `(merchant_id, attempts=64)`, final by `(merchant_id)`), so identical inputs produce identical bytes.

---

## 16.3 Worker sizing & back-pressure

* Cap **in-flight merchants** so trace adjacency stays “immediate” in practice (no queueing that defers the trace append behind other work).
* Prefer **deterministic scheduling** (e.g., ascending `merchant_id`) if your merge layer’s stability is uncertain.
* On sustained back-pressure, **pause new merchants**, don’t split or parallelize within a merchant.

---

## 16.4 Sampler runtime considerations (what’s safe to vary)

* **Zero attempts are cheap**; a long run of zeros up to 64 should not starve the system if across-merchant concurrency is sized sanely.
* **Regime split matters:** inversion (λ<10) vs PTRS (λ≥10) may have different CPU footprints; track regime counters and time K-2 to spot hotspots.
* Never “optimize” by changing regime selection or sampler math—**K-1/K-2 decide; L2 only schedules.**

---

## 16.5 Memory & stream state

* Keep **one stream handle** per active merchant; replace it only with the `s_after` returned by K-2 (or the persisted `s_after` on resume). Do not copy or clone streams.
* Hold only **minimal projections** from store reads: `{k, s_after}` for attempts; booleans for existence; terminal fields for fence checks.

---

## 16.6 Retries & error pressure

* **RNG/logic failures (merchant-scoped):** stop the merchant immediately; continue others. Do **not** retry K-2 in a tight loop after an exception.
* **I/O/trace anomalies:** never re-emit events; allow the next emitter append to perform **trace-only** repair (see §13); resume once.

---

## 16.7 Determinism guardrails under load

* **Counters are the order authority.** Never reorder work based on wall-clock or file arrival; always resume from persisted `s_after` and `max(attempt)`.
* **One terminal per merchant.** Fence with `exists_final`/`exists_exhausted` before resuming or scheduling new work.
* **No direct L0 calls.** L2 does not stamp envelopes or traces; that keeps serialisation points uniform across workers.

---

## 16.8 Telemetry hooks that protect performance

Emit (values-only) at the points defined in §15 so ops can react before drift becomes failure:

* `s4.accept_rate`, `s4.cap_rate`, `s4.mean_attempts` for macro health.
* Regime split (`s4.regime.*`) and per-merchant attempt histograms to catch λ/cohort issues.
* Dedupe/resume counters to spot thrash or mis-sized batches.

---

## 16.9 “Do / Don’t” (quick discipline checklist)

**Do**

* Serialize per-merchant; parallelize across merchants.
* Dedupe before RNG; resume from `{k, s_after}`; return immediately at terminal.
* Keep event→trace adjacency “immediate” by sizing workers and queues conservatively.
* Require stable merges and dictionary-resolved partitions only.

**Don’t**

* Don’t parallelize within a merchant; don’t resample persisted attempts.
* Don’t fabricate counters or budgets; don’t reconstruct payloads.
* Don’t re-emit events to fix trace; don’t emit both exhausted **and** final at cap end.
* Don’t rely on file order; don’t call L0 emitters directly from L2.

---

## 16.10 Acceptance checklist (freeze gate for §16)

* Per-merchant single writer; across-merchant concurrency bounded and deterministic.
* Stable merges; no interleaving within an event→trace pair.
* Resume/dedupe rules guarantee byte-identical outputs after crashes.
* No policy/math moved into L2; all payloads and identities remain with L1→L0.
* Metrics provide enough signal to adjust worker counts without touching logic.

---

# 17) Handoff to L3 & Validation Hooks

**Purpose.** Define exactly what L2 must guarantee *before* validation, what L3 will assert from read-only bytes, and how L2 triggers L3. L2 never validates by itself; it ensures the state is in a **clean, fully-written, deterministic** condition for L3 to read.

---

## 17.1 Pre-handoff conditions (L2 MUST ensure)

For the lineage `{seed, parameter_hash, run_id, manifest_fingerprint}` in scope:

1. **Terminal fence satisfied per merchant:** each merchant is either

   * **Acceptance final** (one `ztp_final` with `K_target≥1`, `attempts=t`, no `exhausted`), or
   * **Cap-abort** (one `ztp_retry_exhausted` with `attempts=64`, `aborted:true`, **no final**), or
   * **Cap-downgrade** (one `ztp_final` with `K_target=0`, `attempts=64`, `exhausted:true`, **no exhausted marker**), or
   * **A=0 short-circuit** (one `ztp_final` with `K_target=0`, `attempts=0` [, `reason` only if schema allows]).
2. **No attempt gaps per merchant:** attempts present are contiguous from 1 to `t` (or none, for A=0).
3. **Exactly one event → one immediate trace:** every event row has its adjacent cumulative trace row (same writer).
4. **No pending work:** L2 has released per-merchant locks; no second K-7 loop is active for the same merchant.
5. **No direct L0 usage by L2:** all emissions were via L1 kernels.

> If any of the above is not true, L2 must resolve (resume/repair or quarantine that merchant per §14) **before** invoking L3.

---

## 17.2 What L2 passes to L3 (values only)

* **Lineage tokens**: `{seed, parameter_hash, run_id, manifest_fingerprint}`.
* **Dataset IDs (dictionary names)** for the four S4 event families and `rng_trace_log`.
* **Optional scope filter** (merchant subset) when running L3 in shard mode.

L2 gives **no paths** and **no payload reconstructions**; L3 reads bytes from the authoritative datasets.

---

## 17.3 L3’s read-only assertions (what L3 will check)

Per merchant (scoped by lineage):

**Structure & identities**

* **Attempt rows** exist only at integer indices `1..t`, contiguous; no duplicates.
* **Consuming vs non-consuming identities** are respected:
  attempts (`poisson_component`) consuming; rejections/exhausted/finals non-consuming.
* **Event→trace adjacency**: exactly one cumulative trace appended **immediately** after each event; trace domain has no `context`.
* **Partitions path↔embed equality** on events; trace partitions match lineage.

**Payload keys**

* Attempt payload uses **`lambda`** (not `lambda_extra`).
* Rejection / exhausted / final payloads use **`lambda_extra`**; final carries `attempts` and `regime` (and `exhausted` only on downgrade variant; `reason` only when schema version defines it).

**Terminal exclusivity & correctness**

* **Acceptance**: one `ztp_final{K_target≥1, attempts=t}`, `exhausted` absent; no exhausted marker exists.
* **Cap-abort**: one `ztp_retry_exhausted{attempts=64, aborted:true}`; **no final** exists.
* **Cap-downgrade**: one `ztp_final{K_target=0, attempts=64, exhausted:true}`; **no exhausted marker** exists.
* **A=0**: one `ztp_final{K_target=0, attempts=0 [,reason?]}`; **no attempts/markers** exist.

**Run-consistency & invariants**

* **Single regime per merchant** (frozen at K-1) echoed identically on all non-attempt events.
* **Monotone counters** per (module, substream_label); totals are saturating.
* **Natural keys unique**: attempt & rejection keyed by `(merchant_id, attempt)`, exhausted by `(merchant_id, attempts=64)`, final by `(merchant_id)`.

On failure, L3 emits standardized diagnostics; L2 does not “self-validate.”

---

## 17.4 L2 → L3 invocation (copy-ready)

```text
PROC validate_s4(lineage, merchants?=ALL):
  input := {
    lineage,
    datasets: {
      attempts: "rng_event_poisson_component",
      rejections: "rng_event_ztp_rejection",
      exhausted: "rng_event_ztp_retry_exhausted",
      finals: "rng_event_ztp_final",
      trace: "rng_trace_log"
    },
    merchants: merchants?
  }
  L3.run_s4_validator(input)
  # L3 returns PASS or a structured failure bundle; L2 does not reinterpret.
```

**Batch pattern:** run per shard of merchants; stop the release if **any** shard returns FAIL.

---

## 17.5 Failure routing (when L3 finds issues)

* **Merchant-scoped violations** (e.g., attempt gaps, wrong identities, duplicate terminals): quarantine the merchant; do not emit more S4 rows for it in this run.
* **Run-scoped violations** (e.g., dictionary/path drift, systemic identity failure): route through the S0 failure framework to **abort** the run atomically (see §14).

L2 **never** edits data to “make L3 pass.”

---

## 17.6 Acceptance checklist (freeze gate for §17)

* [ ] L2 hands L3 only lineage + dataset IDs; no paths, no payload reconstruction.
* [ ] All merchants meet the pre-handoff conditions in §17.1.
* [ ] L3’s assertions cover structure, identities, adjacency, payload keys, terminal exclusivity, counters, and uniqueness.
* [ ] Failures route per §14: merchant quarantine vs run abort; L2 does not mutate bytes.

This handoff ensures validation is **deterministic, read-only, and authority-true**, and that any implementation following L0/L1/L2 will **pass L3** or fail in a way that’s auditable and uniform across teams.

---

# 18) Acceptance Checklist (Freeze Gate for L2)

**Purpose.** A crisp, evaluable gate you (and CI) can run to decide if **S4 · L2** is freeze-ready. This is not guidance—these are **musts**. If any box is unchecked, L2 is **not** ready.

---

## A. Scope & Duties (layer boundaries)

* [ ] L2 **only** orchestrates (gates, substream derivation, dedupe/resume, kernel calls, single terminal); it **never** crafts payloads, stamps envelopes/trace, or calls L0 directly.
* [ ] All emissions happen via **L1 kernels** (K-3/K-4/K-5/K-6), each of which calls exactly one L0 emitter that writes the event **and** the immediate cumulative trace.

## B. Upstream gates & context

* [ ] Enter S4 **only if** `is_multi==true`, `is_eligible==true`, `N≥2`, `A≥0`.
* [ ] If `A==0`, take the **final-only** short-circuit (no attempts/markers).
* [ ] `Ctx` contains only values: `{merchant_id, lineage:{seed,parameter_hash,run_id,manifest_fingerprint}, N, A, is_multi, is_eligible, θ0..2, X_m, policy}`—no paths.

## C. Substream derivation (deterministic, S0 discipline)

* [ ] Merchant-scoped stream derived **once** via S0 with `(module="1A.s4.ztp", substream_label="poisson_component")`.
* [ ] **One stream per merchant**; attempts consume it; markers/finals are non-consuming and receive the **current** stream (before==after).
* [ ] Resume uses **persisted** `s_after` from the last attempt (never re-derive+resample persisted attempts).

## D. Orchestration DAG (authoritative)

* [ ] **A=0:** `K-1 → K-6 → stop`.
* [ ] **Else:** bounded loop attempts **1..64** with per-iteration `K-2 → K-3 → (K-6 | K-4)`; on cap: `policy=="abort" → K-5`, else `K-6(exhausted:true)`.
* [ ] **Kernel-only**: K-1..K-6 in these positions; no raw L0 calls from L2.

## E. Emission identities & payload keys (L0 truth)

* [ ] **Attempt** (`poisson_component`) is **consuming**; payload uses key **`lambda`** (not `lambda_extra`).
* [ ] **Rejection / Exhausted / Final** are **non-consuming**; payloads use **`lambda_extra`**.
* [ ] **One event → one immediate trace** (same writer) after **every** event append.
* [ ] Partitions for events/trace are `{seed, parameter_hash, run_id}`; events enforce path↔embed equality; trace carries no `context`.

## F. Idempotence & resume

* [ ] **Deduplicate before RNG** each iteration: if attempt `a` exists, **do not** sample; read `{k, s_after}` and branch.
* [ ] Resume index is `max(attempt)+1` (or `1` if none).
* [ ] Counters (not file order) define total order.

## G. Policy handling & terminal exclusivity

* [ ] Exactly **one** terminal per merchant:
  - **Accept:** `ztp_final{K_target≥1, attempts=t}` (no `exhausted`).
  - **Cap-abort:** `ztp_retry_exhausted{attempts:64, aborted:true}` (**no** final).
  - **Cap-downgrade:** `ztp_final{K_target=0, attempts=64, exhausted:true}` (**no** exhausted marker).
  - **A=0:** `ztp_final{K_target=0, attempts=0 [,reason?]}` (no attempts/markers).
* [ ] Cap is treated as **64** (schema-pinned); no runtime override in L2.

## H. Concurrency & single-writer discipline

* [ ] Per-merchant K-7 is **single-threaded**; no overlapping loops for the same merchant.
* [ ] Across merchants: parallel OK; merges/writers are **stable** with the families’ natural keys.
* [ ] L2 never interleaves other work between an event and its immediate trace append.

## I. Crash-safety & trace repair

* [ ] On “event persisted, trace missing,” L2 **never re-emits** the event; it allows **trace-only** repair once (next emitter append).
* [ ] If repair is impossible, L2 surfaces a standardized failure and **stops the merchant**.

## J. Store interfaces (read-only)

* [ ] L2 uses only dictionary-resolved datasets and minimal projections:
  - attempts `(merchant_id, attempt) → {k, s_after}`;
  - rejection existence;
  - exhausted `(merchant_id, attempts=64)` existence;
  - final `(merchant_id) → {K_target, attempts, regime [,exhausted?]}`;
  - `max(attempt)` for resume.
* [ ] No payload reconstruction beyond these projections; no budget inference.

## K. Telemetry & run metrics

* [ ] After gates: increment `s4.merchants_in_scope`; after K-1: `s4.regime.*`.
* [ ] After every event+trace: increment `s4.attempts.total` / `s4.rejections` / `s4.trace.rows`.
* [ ] At terminal: emit one per-merchant summary (omit on hard abort); metrics are values-only and low-cardinality.

## L. Handoff to L3 (validation readiness)

* [ ] Pre-handoff conditions satisfied: no attempt gaps; ≤64 attempts; exactly one terminal per merchant; adjacency invariant held; no active per-merchant loop.
* [ ] L2 passes L3 **only** lineage + dataset IDs (no paths, no mutations) and does **not** “fix” data to make validation pass.

---

## M. Quick self-test (must pass before freeze)

1. **A=0 case:** merchant with `A=0` produces exactly one `ztp_final{K_target=0, attempts=0}`; no attempt/rejection/exhausted rows.
2. **Accept@3 case:** attempts at 1 & 2 emit attempts+rejections; attempt 3 emits attempt+final; no `exhausted`.
3. **Cap-abort case:** 64 attempts with rejections; terminal is exhausted only (no final).
4. **Cap-downgrade case:** 64 attempts with rejections; terminal is final `{attempts=64, exhausted:true}`; no exhausted marker.
5. **Crash window:** inject crash after an attempt event append; on resume, **no re-emit**; trace is repaired on the next emitter append; resume continues deterministically from persisted `s_after`.

---

## N. Sign-off matrix

| Role               | You confirm…                                                                       | Sign   |
|--------------------|------------------------------------------------------------------------------------|--------|
| **Author**         | L2 calls only K-1..K-6; no direct L0 calls; all invariants in A-L hold.            | ______ |
| **Reviewer**       | Orchestration matches DAG; identities & terminals exclusive; resume/dedupe obeyed. | ______ |
| **Ops**            | Concurrency, metrics, and crash-repair are implementable and monitored.            | ______ |
| **Validator (L3)** | Preconditions met; L3 passes on the canonical scenarios above.                     | ______ |

---

**Outcome:** When every box in **A-L** is checked and the **self-tests** pass, this L2 is **freeze-ready**.

---

# 19) Worked Scenarios (Normative, Deterministic)

**How to read this.** Each scenario fixes: **inputs (value-level Ctx)** → **kernel calls from L2** → **events written (family, identity, payload keys)** → **on-disk keys & counts** → **resume notes**. L2 calls **kernels only**; each kernel calls one L0 emitter that writes the **event** and appends **one immediate** cumulative **trace** (same writer). Attempts use payload key **`lambda`**; markers/finals use **`lambda_extra`**.  

---

## 19.1 A=0 — Final-only (no attempts/markers)

**Inputs.** `is_multi=true, is_eligible=true, N≥2, A=0, θ, X_m, policy∈{abort,downgrade}`.
**Calls.** `K-1 (freeze λ,regime)` → derive merchant stream → `K-6 (final)` → **stop**.
**Events (in order).**

1. `rng_event_ztp_final` (non-consuming): `{ merchant_id, K_target:0, lambda_extra, attempts:0, regime [,reason]? }` → **immediate trace**. *(Include `reason:"no_admissible"` only if the bound schema version allows it.)* 

**On disk (by natural keys).** Final: 1; Attempts: 0; Rejections: 0; Exhausted: 0.
**Resume.** Merchant is terminal; fence prevents further work. 

---

## 19.2 Accept @1 — Immediate acceptance

**Inputs.** `is_multi=true, is_eligible=true, N≥2, A≥1`.
**Calls.** Derive stream → `K-1` → Attempt 1: `K-2` sample → `K-3` emit attempt → `k>0` ⇒ `K-6` final → **stop**.
**Events (in order).**

1. `rng_event_poisson_component` (consuming): `{ merchant_id, attempt:1, k>0, **lambda** }` → **immediate trace**.
2. `rng_event_ztp_final` (non-consuming): `{ merchant_id, K_target:k, **lambda_extra**, attempts:1, regime }` → **immediate trace**. *(No rejection for attempt 1.)* 

**On disk.** Attempts: 1; Rejections: 0; Final: 1; Exhausted: 0.
**Resume.** Terminal fence stops re-entry. Counters/trace adjacency are emitter-enforced. 

---

## 19.3 Accept @4 — Three zeros then accept

**Inputs.** As above; first three attempts yield `k=0`, fourth yields `k>0`.
**Calls.** For `t=1..3`: `K-2` → `K-3` attempt → `K-4` rejection; at `t=4`: `K-2` → `K-3` attempt → **`k>0`** ⇒ `K-6` final → **stop**.
**Events (in order).** *(Each event followed by **immediate** trace)*

* `t=1..3`:
  a) `poisson_component`: `{…, attempt:t, k:0, **lambda**}`
  b) `ztp_rejection`: `{…, attempt:t, **lambda_extra**}`
* `t=4`:
  a) `poisson_component`: `{…, attempt:4, k>0, **lambda**}`
  b) `ztp_final`: `{…, K_target:k, **lambda_extra**, attempts:4, regime }` *(no rejection at 4)*. 

**On disk.** Attempts: 4; Rejections: 3; Final: 1; Exhausted: 0.
**Resume.** If crash after any attempt, resume at `max(attempt)+1` and `s_before := last.s_after`; never resample persisted attempts. 

---

## 19.4 Cap-Abort — 64 zeros, `policy="abort"`

**Inputs.** All attempts draw `k=0`; `policy="abort"`.
**Calls.** For `t=1..64`: `K-2` → `K-3` attempt → `K-4` rejection; cap end: **`K-5` exhausted** → **stop**.
**Events (in order).**

* For each `t=1..64`:
  a) `poisson_component`: `{…, attempt:t, k:0, **lambda**}` → trace
  b) `ztp_rejection`: `{…, attempt:t, **lambda_extra**}` → trace
* Cap marker (abort-only):
  `ztp_retry_exhausted`: `{…, attempts:64, **lambda_extra**, aborted:true }` → trace. 

**On disk.** Attempts: 64; Rejections: 64; Exhausted: 1; Final: 0.
**Resume.** Terminal fence via exhausted marker; **no final** allowed thereafter. 

---

## 19.5 Cap-Downgrade — 64 zeros, `policy="downgrade_domestic"`

**Inputs.** All attempts `k=0`; `policy="downgrade_domestic"`.
**Calls.** For `t=1..64`: `K-2` → `K-3` → `K-4`; cap end: **`K-6` final `{K_target=0, attempts=64, exhausted:true}`** → **stop**.
**Events (in order).**

* For each `t=1..64`: attempt + rejection as above → traces.
* Finaliser (no exhausted on this path):
  `ztp_final`: `{…, K_target:0, **lambda_extra**, attempts:64, regime, exhausted:true }` → trace. 

**On disk.** Attempts: 64; Rejections: 64; Final: 1; Exhausted: 0.
**Resume.** Final ends merchant; fence prevents any exhausted emit. 

---

## 19.6 Crash Windows — Deterministic resume & trace repair

**Case A — Crash after attempt *event* append (k=0) but before its trace.**

* **On disk:** attempt row present; adjacent trace missing.
* **Resume:** L2 **does not re-emit** the event; it continues with pre-emit dedupe (reads `{k, s_after}`), then emits the rejection via `K-4`. The **next emitter append** repairs the missing **trace** for the prior event (same writer), then writes the new event’s trace—maintaining adjacency. 

**Case B — Crash after terminal.**

* If `ztp_final` or `ztp_retry_exhausted` exists, the merchant is **resolved**; L2’s fence stops further work on resume. 

---

### Invariants you should observe in **every** scenario

* **Adjacency:** each event is followed by **exactly one** immediate cumulative trace (same writer). 
* **Identities:** attempts are **consuming** (`after>before`, `draws>"0"`); markers/final are **non-consuming** (`before==after`, `draws="0"`). 
* **Keys:** Attempts/Rejections unique per `(merchant_id, attempt)`; Exhausted at most one per merchant; Final at most one per resolved merchant. 
* **Authority split:** S4 fixes **`K_target`** only; **no order** encoded in S4; S6 will realise `min(K_target, A)` using S3’s order authority. 

These scenarios, driven strictly by **K-1…K-6** and L0’s event/trace contract, are **normative**: any conforming implementation should yield byte-identical logs and pass L3’s read-only checks.  

---

# 20) Run Modes & Entry Points

**Purpose.** Expose clear, callable entry points for **how** to run S4’s orchestrator under different operational modes—without guessing. Every mode uses **kernels only** (K-1…K-6); emit/trace stamping is owned by L0 (one event → **one immediate** cumulative trace, same writer). Attempts use **`lambda`**; markers/final use **`lambda_extra`**. Cap is **64** (abort marker requires `attempts:64, aborted:true`).   

---

## 20.1 Supported run modes (what they do)

* **Cold Run (full scope).** Drive all merchants that pass S1/S2/S3 gates for the given lineage. L2 derives the merchant stream once, freezes λ/`regime` via **K-1**, then runs the bounded loop 1..64 using **K-2/K-3/K-4** and closes with the correct terminal (**K-6** or **K-5**, per policy). 

* **Resume Run (crash-safe).** Same as Cold, but starts from **persisted state**: dedupe-before-RNG per attempt, resume at `max(attempt)+1` with `s_before := last.s_after`. If an event exists without its adjacent trace, **do not re-emit**; the next emitter append repairs trace (one-event → one-trace invariant). 

* **Subset Run (filtered).** As Cold/Resume, but restricted to an explicit merchant set. Resolution fence applies: if `final` or `exhausted` exists, **skip** merchant (already resolved). 

* **Dry-Run (read-only preflight).** No emission. L2 assembles `Ctx`, checks gates (S1/S2/S3), derives stream, and **may** call **K-1** to freeze λ/`regime` for telemetry planning—but never calls emitting kernels. Useful for capacity checks and policy review. 

> **Idempotence note.** Writers are dictionary-resolved and no-op on complete partitions; re-runs with identical inputs produce **byte-identical** outputs. 

---

## 20.2 Entry points (call surfaces)

### Per-merchant

```text
orchestrate_s4_for_merchant(ctx)         # §0/§10 loop, kernels only; writes events via L1→L0
s4_preflight(ctx) -> {SKIP|SHORT_CIRCUIT_FINAL|PROCEED}   # §4 gates & A=0 handling (no RNG)
```

### Batch (across merchants)

```text
orchestrate_s4_batch(ctxs)                # serial per merchant; parallelize across merchants safely (§11)
```

### Modes (wrappers)

```text
run_cold(lineage, merchants=ALL)          # Cold
run_resume(lineage, merchants=ALL)        # Resume (dedupe-before-RNG; resume index & stream §7)
run_subset(lineage, merchant_list)        # Subset
run_dry(lineage, merchants=ALL)           # Dry-run (preflight + K-1 only; no emit)
```

All entry points **call kernels only** (K-1…K-6). L2 never calls L0 emitters directly; emitters stamp envelopes and append the **immediate** cumulative trace under `{seed, parameter_hash, run_id}`. 

---

## 20.3 Required arguments (values only)

* `lineage : { seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }` (pass-through to emitters). 
* Per-merchant `Ctx` fields: `{ merchant_id:i64, is_multi:bool, is_eligible:bool, N:int≥2, A:int≥0, θ0,θ1,θ2, X_m∈[0,1], policy∈{"abort","downgrade_domestic"} }`. A=0 triggers **final-only** (`ztp_final{K_target=0, attempts=0 [,reason]?}`) and **no attempts/markers**. 

---

## 20.4 Lifecycle (what each entry does)

1. **Gates**: check S1/S2/S3 + policy; if fail ⇒ **emit nothing**. If terminal exists (final or exhausted) ⇒ **skip** merchant. 

2. **A=0**: **K-1** → **K-6** final-only; stop.

3. **Else**: derive merchant stream; run attempt loop **1..64**:
   - new attempt ⇒ **K-2** sample once (RNG-consuming) → **K-3** emit attempt (payload key **`lambda`**; immediate trace).
   - `k>0` ⇒ **K-6** emit final (non-consuming; uses **`lambda_extra`**; no `exhausted`).
   - `k==0` ⇒ ensure one **K-4** rejection (non-consuming; **`lambda_extra`**).
   - at cap: `policy=="abort"` ⇒ **K-5** exhausted only (`attempts:64, aborted:true`); else ⇒ **K-6** final `{attempts:64, exhausted:true}`. 

4. **Resume semantics** (if mode=Resume): use `max(attempt)` and persisted `{k, s_after}`; **never resample** existing attempts; counters define order, not file timestamps. 

---

## 20.5 Outputs & invariants (per mode)

* **Cold/Subset:** merchants end in exactly **one** terminal (accept final / abort exhausted / downgrade final / A=0 final). No attempt gaps; attempts are **consuming**, markers/final **non-consuming**; every event has an **immediate** trace by the **same writer**. 

* **Resume:** same invariants; plus **dedupe-before-RNG** and deterministic stream resume (`s_before := last.s_after`). 

* **Dry-Run:** **writes nothing**; returns gate results and λ/`regime` for telemetry planning.

---

## 20.6 When to call L3 (handoff)

After any run that produced bytes (Cold/Resume/Subset), invoke L3 with **lineage + dataset IDs**; L2 does not mutate data to “make validation pass.” (See §17.) 

---

## 20.7 Acceptance checks for §20 (freeze gate)

* Entry points present for all four modes; **kernels-only** orchestration; **no direct L0 calls**. 
* Cold/Resume/Subset respect gates, A=0, cap semantics, and terminal exclusivity; Dry-Run emits nothing but may call **K-1**. 
* Idempotence & resume are implemented via read-only store interfaces (natural keys, `{k, s_after}`) and **never** re-emit events for trace repair. 

This section keeps L2 **hands-on and unambiguous** while staying faithful to the frozen contracts in **S4·L1 v12** and **S4·L0 v15** (payload keys, trace adjacency, partitions, cap semantics).  

---

# Appendix A — Kernel Call Sheet (L2 → L1)

**Goal.** Make the callable surface from **L2 → L1** unambiguous. L2 **only** calls these kernels. Each kernel calls **exactly one** L0 emitter (or sampler) internally. L2 passes **values + stream**—never crafts payloads, never stamps envelopes/trace.  
**If any example conflicts with this call sheet, the call sheet wins.**

---

## A.1 Type aliases (values only)

```
Lineage      = { seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }
LambdaInputs = { N:int≥2, X_m:float∈[0,1], θ0:float, θ1:float, θ2:float }
LambdaRegime = { lambda_extra:float>0, regime:"inversion"|"ptrs" }
AttemptBudget= { blocks:u64, draws_hi:u64, draws_lo:u64 }        # measured actual-use
Finaliser    = { K_target:int≥0, attempts:int≥0, regime:"inversion"|"ptrs", exhausted?:bool, reason? }
Stream       = PRNG stream handle (merchant-scoped; §6)
Ctx          = { merchant_id:i64, lineage:Lineage, is_multi:bool, is_eligible:bool,
                 N:int≥2, A:int≥0, θ0,θ1,θ2:float, X_m:float∈[0,1], policy:"abort"|"downgrade_domestic" }
```

**Payload key rule (schema-true):** attempts use **`lambda`**; rejection/exhausted/final use **`lambda_extra`**.
**Identity rule:** attempts **consuming**; rejection/exhausted/final **non-consuming**; each event is followed by **one immediate** cumulative trace (same writer).

---

## A.2 Kernel surfaces (signatures are normative)

### K-1 — `freeze_lambda_regime(inputs: LambdaInputs) -> LambdaRegime`

* **REQUIRES:** `inputs.N≥2`, `inputs.X_m∈[0,1]`; all inputs finite.
* **ENSURES:** returns `{lambda_extra>0, regime ∈ {"inversion","ptrs"}}` with regime = (`lambda_extra` < 10 ? inversion : ptrs).
* **ERRORS:** `NUMERIC_INVALID` if λ non-finite or ≤ 0.
* **SIDE EFFECTS:** none (pure).

---

### K-2 — `do_poisson_attempt_once(lr: LambdaRegime, s_before: Stream) -> (k:int≥0, s_after: Stream, bud: AttemptBudget)`

* **REQUIRES:** `isfinite(lr.lambda_extra) ∧ lr.lambda_extra>0` and `compute_poisson_regime(lr.lambda_extra)==lr.regime`.
* **REQUIRES:** `lambda_extra>0`, finite; `regime` consistent with `lambda_extra`; `s_before` from §6 stream.
* **ENSURES:** calls the sampler **once**; advances the stream; returns **measured** `bud` (actual-use).
* **SIDE EFFECTS:** none (no event I/O here).

---

### K-3 — `emit_poisson_attempt(merchant_id:i64, lineage:Lineage, s_before:Stream, s_after:Stream, lr:LambdaRegime, attempt:int≥1, k:int≥0, bud:AttemptBudget) -> void`

* **REQUIRES:** `attempt≥1`; `s_after` is the K-2 return for this attempt; `bud` is measured.
* **EMITS:** **attempt event** → `rng_event_poisson_component` with payload `{ merchant_id, attempt, k, **lambda** }`;
  **immediately** appends one cumulative trace (same writer).
* **IDENTITY:** consuming (`after>before`, `blocks=Δ>0`, `draws>"0"`).

---

### K-4 — `emit_ztp_rejection_nonconsuming(merchant_id:i64, lineage:Lineage, s_curr:Stream, lr:LambdaRegime, attempt:int≥1) -> void`

* **REQUIRES:** `k==0` for this `attempt`; rejection row not already present.
* **EMITS:** **rejection marker** → `rng_event_ztp_rejection` with `{ merchant_id, attempt, **lambda_extra** }` + **immediate** trace.
* **IDENTITY:** non-consuming (`before==after`, `blocks=0`, `draws="0"`).

---

### K-5 — `emit_ztp_retry_exhausted_nonconsuming(merchant_id:i64, lineage:Lineage, s_curr:Stream, lr:LambdaRegime, policy:"abort") -> void`

* **REQUIRES:** `policy == "abort"` and cap reached (64 zeros).
* **EMITS:** **cap-abort marker** → `rng_event_ztp_retry_exhausted` with `{ merchant_id, attempts:64, **lambda_extra**, aborted:true }` + **immediate** trace.
* **IDENTITY:** non-consuming.

---

### K-6 — `do_emit_ztp_final(merchant_id:i64, lineage:Lineage, s_curr:Stream, lr:LambdaRegime, fin:Finaliser) -> Finaliser`

* **REQUIRES:** terminal path chosen:
  - **A=0**: `fin={K_target:0, attempts:0, regime [,reason?]}`;
  - **Accept@t**: `fin={K_target:k≥1, attempts:t, regime}` (no `exhausted`);
  - **Downgrade**: `fin={K_target:0, attempts:64, regime, exhausted:true}`.
* **EMITS:** **finaliser** → `rng_event_ztp_final` with `{ merchant_id, K_target, **lambda_extra**, attempts, regime [,exhausted?, reason?] }` + **immediate** trace.
* **ENSURES:** **exactly one** final per resolved merchant (absent on abort path); returns `fin` (echo).
* **IDENTITY:** non-consuming.

---

## A.3 Per-kernel call facts (what L2 passes)

* **Lineage**: `{ seed, parameter_hash, run_id, manifest_fingerprint }` to every emitter kernel.
* **Stream**:
  - Attempts: pass **`s_before`** and the **`s_after`** returned by K-2;
  - Markers/finals: pass the **current** stream `s_curr` (non-consuming → `before==after`).
* **Values**:
  - K-1 takes `{N, X_m, θ0..2}`;
  - K-2 takes `{lr, s_before}`;
  - K-3 takes `{attempt, k, bud, s_before, s_after, lr}`;
  - K-4 takes `{attempt, lr}`;
  - K-5 takes `{lr, policy="abort"}` (L2 checks policy before call);
  - K-6 takes `{fin, lr}`.

---

## A.4 Error & identity mapping (so L2 can route failures)

* **K-1** may raise `NUMERIC_INVALID` (no events written).
* **K-2** may raise `RNG_SAMPLER_FAIL` (no event written yet); L2 quarantines merchant per §14.
* **K-3/K-4/K-5/K-6** stamp envelopes and append **one immediate** trace (same writer); identities enforced by L0.
* **Never** re-emit events to fix trace; repair is **trace-only** and occurs on the next emitter append.

---

## A.5 Example call sequence (from L2’s K-7 loop; kernels only)

```
# Preflight & A=0 handled earlier
lr := K1.freeze_lambda_regime({N:ctx.N, X_m:ctx.X_m, θ0:ctx.θ0, θ1:ctx.θ1, θ2:ctx.θ2})
s  := derive_merchant_stream(ctx.lineage, ctx.merchant_id)

FOR attempt IN resume_attempt_index(ctx.merchant_id) .. 64:
  pre := pre_emit_dedupe(ctx.merchant_id, attempt)
  IF pre != null:
     k := pre.k; s := pre.s_after
  ELSE:
     (k, s_after, bud) := K2.do_poisson_attempt_once(lr, s)
     K3.emit_poisson_attempt(ctx.merchant_id, ctx.lineage, s, s_after, lr, attempt, k, bud)
     s := s_after

  IF k > 0:
     K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr, {K_target:k, attempts:attempt, regime:lr.regime})
     RETURN

  IF NOT exists_rejection(ctx.merchant_id, attempt):
     K4.emit_ztp_rejection_nonconsuming(ctx.merchant_id, ctx.lineage, s, lr, attempt)

# Cap
IF ctx.policy == "abort":
   IF NOT exists_exhausted(ctx.merchant_id):
      K5.emit_ztp_retry_exhausted_nonconsuming(ctx.merchant_id, ctx.lineage, s, lr, policy="abort")
ELSE:
   IF NOT exists_final(ctx.merchant_id):
      K6.do_emit_ztp_final(ctx.merchant_id, ctx.lineage, s, lr, {K_target:0, attempts:64, regime:lr.regime, exhausted:true})
```

---

## A.6 Prohibited calls (layer hygiene)

* L2 **must not** call any **L0** emitter directly.
* L2 **must not** craft payload fields (`lambda`/`lambda_extra`, `attempts`, `exhausted`, `reason`).
* L2 **must not** fabricate counters or budgets; only pass the **measured** `AttemptBudget` from K-2 or the **persisted** `s_after` from store.

This sheet is the operative contract between **L2** and **L1** for **State-4**. Any implementation that adheres to these signatures and rules will produce byte-identical, validator-passing results under the same lineage.

---

# Appendix B — Natural Keys & Dictionary IDs (Lookup)

**Purpose.** Give L2 a precise lookup map—**dataset IDs**, **partitions**, and **natural keys**—so skip/resume and terminal fencing are byte-safe and deterministic. L2 uses **dictionary-resolved** datasets only; it never uses path literals, never crafts payloads, and never stamps envelopes/trace. 

---

## B.1 Datasets (Dictionary IDs) & Partitions

| Family (Dictionary ID)          | What it is                       | Partitions (authoritative)         | Notes                                                                                                  |
|---------------------------------|----------------------------------|------------------------------------|--------------------------------------------------------------------------------------------------------|
| `rng_event_poisson_component`   | Attempt rows (consuming)         | `{ seed, parameter_hash, run_id }` | Payload uses **`lambda`**; each event is followed by **one immediate** cumulative trace (same writer). |
| `rng_event_ztp_rejection`       | Zero markers (non-consuming)     | `{ seed, parameter_hash, run_id }` | Payload uses **`lambda_extra`**; per attempt at `k==0`.                                                |
| `rng_event_ztp_retry_exhausted` | Cap-abort marker (non-consuming) | `{ seed, parameter_hash, run_id }` | Schema pins **`attempts:64`** and requires `aborted:true`.                                             |
| `rng_event_ztp_final`           | Finaliser (non-consuming)        | `{ seed, parameter_hash, run_id }` | Carries `{K_target, lambda_extra, attempts, regime [,exhausted?, reason?]}` per terminal rules.        |
| `rng_trace_log`                 | Cumulative trace rows            | `{ seed, parameter_hash, run_id }` | **No `context`** on trace; appended **immediately** after each event by the **same writer**.           |

> **Path↔embed equality** on **events** is enforced by the L0 emitters; L2 passes **values only** (lineage), never paths. File order is not authoritative—**envelope counters** define total order. 

---

## B.2 Natural Keys (Uniqueness & Skip/Resume)

| Family                                      | Natural key (per lineage)    | Uniqueness & use in L2                                                                                                                                    |
| ------------------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Attempt (`rng_event_poisson_component`)     | `(merchant_id, attempt)`     | **At most one** attempt row per index. Use to: (a) **dedupe before RNG**; (b) read `{k, s_after}` to branch and advance.                                  |
| Rejection (`rng_event_ztp_rejection`)       | `(merchant_id, attempt)`     | **At most one** zero marker per index. Use to avoid duplicate K-4 emits.                                                                                  |
| Exhausted (`rng_event_ztp_retry_exhausted`) | `(merchant_id, attempts=64)` | **At most one** per merchant; exists **only** on cap-abort; if present, merchant is **resolved** (no final permitted).                                    |
| Final (`rng_event_ztp_final`)               | `(merchant_id)`              | **At most one** per resolved merchant. Variants: A=0 (`attempts=0`), accept (`attempts=t`, no `exhausted`), downgrade (`attempts=64`, `exhausted:true`).  |

> **Terminal fence.** If **final** or **exhausted** exists for a merchant, L2 must **stop** S4 for that merchant (resolved). 

---

## B.3 Writer Sort (for scans) & Resume Projections

| Family    | Natural writer sort (within partition) | Minimal projection L2 reads                                                                |
|-----------|----------------------------------------|--------------------------------------------------------------------------------------------|
| Attempt   | `["merchant_id","attempt"]`            | `{ k:int, s_after:Stream }` (branching & stream advance)                                   |
| Rejection | `["merchant_id","attempt"]`            | `exists_only` (dedupe)                                                                     |
| Exhausted | `["merchant_id","attempts"]`           | `exists_only` (terminal fence)                                                             |
| Final     | `["merchant_id"]`                      | `{ K_target:int, attempts:int, regime:str [,exhausted?:bool] }` (terminal fence/reporting) |

> **Max attempt** for resume: `MAX(attempt)` from `rng_event_poisson_component`; resume at `max+1` and set `s_before := last.s_after`. Never resample persisted attempts. 

---

## B.4 Label Domain (for both events & trace)

```
module           = "1A.s4.ztp"
substream_label  = "poisson_component"
context (events) = "ztp"         # trace has no context
```

All S4 families share this domain; **trace rows** carry the same `(module, substream_label)` and are appended **immediately** after events. 

---

## B.5 What L2 must **never** do with IDs/keys

* Use path literals or invent dataset IDs—**always** resolve via the dictionary.
* Reconstruct payloads from store rows beyond the minimal projections above; **no budget inference**.
* Re-emit any event to “repair” trace; repairs are **trace-only** and occur on the next emitter append. 

This appendix is the complete lookup surface L2 needs to **skip, resume, and fence terminals** deterministically while staying inside the authority set of **S4·L0 v15** and the **S4 expanded spec**.  

---

# Appendix C — Substream & Lineage Tokens

**Purpose.** Nail down the *exact* identifiers and labels that make S4’s RNG and writes deterministic: the **lineage tokens** L2 passes, the **label domain** shared by all S4 logs, and the **merchant-scoped substream** L2 derives once and threads through kernels. L2 never stamps envelopes/trace—**L0 does**—and L2 never fabricates counters or budgets. 

---

## C.1 Lineage tokens (values L2 must pass to every kernel)

```
Lineage = {
  seed: u64,
  parameter_hash: hex64,
  run_id: hex32,
  manifest_fingerprint: hex64
}
```

* **Why:** L0 emitters stamp these into **event envelopes** and place rows under dictionary-resolved partitions `{seed, parameter_hash, run_id}`; `manifest_fingerprint` is carried in the envelope so bytes are lineage-bound. L2 passes **values only**, never paths. 

* **Trace rows:** same partitions; **no `context` field** on trace. (Trace is appended **immediately** after each event by the same writer.) 

---

## C.2 Label domain (shared by all S4 events & trace)

```
module           = "1A.s4.ztp"
substream_label  = "poisson_component"
context (events) = "ztp"      # trace has no context
```

* **Single label space:** every S4 family (attempt, rejection, exhausted, final) uses this `(module, substream_label)`; adjacency and cumulative totals are computed in that domain. 

---

## C.3 Merchant tag & Ids (for substream derivation)

```
merchant_u64 := LOW64( SHA256( LE64(merchant_id) ) )
Ids := [ { tag:"merchant_u64", value: merchant_u64 } ]
```

* **Order-invariant Ids:** tags are serialized deterministically; do not add ad-hoc tags.
* **Exactly one stream per merchant:** all S4 events for a merchant consume (or non-consume) the same stream. 

---

## C.4 Deriving the merchant substream (S0 discipline)

```
M  := S0.derive_master_material(lineage.seed, BYTES(lineage.manifest_fingerprint))
s0 := S0.derive_substream(M, "poisson_component", Ids)
```

* L2 derives **once per merchant** and threads it through kernels.
* **Attempts (K-2/K-3):** consuming → pass `s_before` and the `s_after` returned by K-2.
* **Markers/finals (K-4/K-5/K-6):** non-consuming → pass the **current** stream (identity: `before==after`, `blocks=0`, `draws="0"`). 

---

## C.5 Envelope & trace fields (what L0 stamps)

| Stream                                                     | Envelope fields (authoritative)                                                      | Identity                                         | Notes                                                                                                                                  |
|------------------------------------------------------------|--------------------------------------------------------------------------------------|--------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| **Attempt** (`rng_event_poisson_component`, context:"ztp") | lineage tokens, `(module, substream_label, context)`, `before, after, blocks, draws` | **Consuming** (`after>before`, `draws>"0"`)      | Payload uses **`lambda`**; budgets are **measured**, not inferred.                                                                     |
| **Rejection** (`rng_event_ztp_rejection`)                  | lineage tokens, `(module, substream_label)`                                          | **Non-consuming** (`before==after`, `draws="0"`) | Payload uses **`lambda_extra`**.                                                                                                       |
| **Exhausted** (`rng_event_ztp_retry_exhausted`)            | lineage tokens, `(module, substream_label)`                                          | **Non-consuming**                                | `attempts:64`, `aborted:true`, payload uses **`lambda_extra`**.                                                                        |
| **Final** (`rng_event_ztp_final`)                          | lineage tokens, `(module, substream_label)`                                          | **Non-consuming**                                | A=0: `attempts=0`; Accept: `attempts=t` (no `exhausted`); Downgrade: `attempts=64`, `exhausted:true`; payload uses **`lambda_extra`**. |
| **Trace** (`rng_trace_log`)                                | lineage tokens, `(module, substream_label)`, cumulative totals                       | —                                                | **No `context`**; appended **immediately** after each event by the **same writer**.                                                    |

*File order is non-authoritative—**envelope counters** define total order.* 

---

## C.6 Equality & determinism checks (what L2 assumes, what L0/L3 enforce)

* **Path↔embed equality (events):** partitions `{seed, parameter_hash, run_id}` in the path equal the envelope values; enforced by emitters and later asserted by L3. 
* **Adjacency:** each event is followed by **one** immediate cumulative trace; no interleaving; same writer. 
* **Counters rule:** dedupe/resume and terminal fencing rely on counters & natural keys—not timestamps or file order. 

---

## C.7 Copy-ready helpers (L2 values only)

```text
PROC build_lineage(seed, parameter_hash, run_id, manifest_fingerprint) -> Lineage:
  RETURN {seed, parameter_hash, run_id, manifest_fingerprint}

PROC derive_merchant_stream(lineage, merchant_id) -> Stream:
  merchant_u64 := LOW64( SHA256( LE64(merchant_id) ) )
  M  := S0.derive_master_material(lineage.seed, BYTES(lineage.manifest_fingerprint))
  RETURN S0.derive_substream(M, "poisson_component", [{tag:"merchant_u64", value:merchant_u64}])
```

Use `derive_merchant_stream` for fresh runs; on resume set `s_before := last.s_after` from persisted attempt rows (never re-derive to resample persisted attempts). 

---

## C.8 Do / Don’t (layer hygiene)

**Do**

* Pass lineage **values** to every kernel.
* Derive **one** merchant stream and thread it through kernels.
* Let L0 stamp envelopes and append **immediate** trace.

**Don’t**

* Don’t call L0 emitters directly from L2.
* Don’t fabricate counters/budgets or reconstruct payloads.
* Don’t introduce new tags or labels in the substream Ids.
* Don’t rely on file order for resume or fencing.

This appendix fixes the identifiers that make S4’s orchestration reproducible and audit-ready, in strict agreement with **S4·L0 v15** and the **S4 expanded** contracts.  

---

# Appendix D — Troubleshooting (Ops Playbook)

**Purpose.** A hands-on, read-only playbook to diagnose and recover S4 orchestration issues **without** crafting bytes or calling emitters from L2. L2 only reads, routes, resumes, or quarantines; L0 stamps bytes (event **then** immediate trace), and L1 assembles payloads. Attempts use **`lambda`**; markers/finals use **`lambda_extra`**. Cap is **64**.  

---

## D.1 How to use this playbook (scope)

* **Read-only triage.** Use the store interfaces from §12: `exists_*`, `read_attempt_k_after`, `max_attempt`. Never re-emit events from L2. 
* **Adjacency invariant.** Every event is followed by **one immediate** cumulative trace by the **same writer**; trace has **no `context`**; counters (not file order) define order. 
* **Terminal fence.** If `final` **or** `exhausted` exists, the merchant is **resolved**; L2 stops work for that merchant. 

---

## D.2 Quick triage flow (decision steps)

1. **Terminal present?**
   `exists_final` or `exists_exhausted` → *Resolved* → **skip merchant**. 
2. **Attempt gaps?**
   Scan attempts for contiguity `1..t`. If missing `a`, **stop merchant** with `ATTEMPT_GAPS`. 
3. **Event without trace?**
   If adjacency missing, **do not re-emit**; next emit repairs trace (trace-only). 
4. **Wrong terminal at cap?**
   Abort policy → **exhausted only**; Downgrade → **final (exhausted:true)**. Never both. 
5. **A=0 but attempts exist?**
   Route was wrong; future runs must short-circuit to `final(0, attempts=0)` **only**. 

---

## D.3 Common incidents — Symptoms → Checks → Action

### 1) *“We crashed; now we see an event row but no trace.”*

* **Check:** `poisson_component` exists for `(mid,a)`; adjacent `rng_trace_log` entry missing.
* **Action:** **Do not re-emit**. Resume loop. The next emitter append writes the missing **trace** using the persisted envelope; adjacency restored. 

### 2) *“Two attempt rows for the same (mid,a).”*

* **Check:** Uniqueness must be one attempt per `(merchant_id, attempt)`.
* **Action:** Treat as **ATTEMPT_GAPS/duplicate**; stop merchant; fix writer stability/merge. L2 must dedupe-before-RNG to prevent a second sample. 

### 3) *“Zero seen but no rejection row.”*

* **Check:** For `k==0` attempts, verify `ztp_rejection` exists for that attempt.
* **Action:** On resume, L2 ensures **one** K-4 rejection if missing (non-consuming, immediate trace). 

### 4) *“Cap reached; both exhausted and final exist.”*

* **Check:** At 64 zeros, policy must choose **exactly one** terminal.
* **Action:** Flag **POLICY_CONFLICT**; quarantine merchant. Correct L2 routing: abort→K-5 only; downgrade→K-6 (exhausted:true) only. 

### 5) *“A=0 but the run sampled attempts.”*

* **Check:** `A==0` after gates should emit **only** `ztp_final{K_target=0, attempts=0 [,reason?]}`.
* **Action:** Fix L2 gate path to K-1→K-6 and **stop**; no attempts or markers allowed. 

### 6) *“Attempt payload has `lambda_extra` (or rejection has `lambda`).”*

* **Check:** Payload keys are schema-true: attempts→**`lambda`**; markers/final→**`lambda_extra`**.
* **Action:** This is an L1 misuse; keep L2 kernel-only. Verify K-3/K-4/K-6 payload assembly. 

### 7) *“Identity mismatch: attempt marked non-consuming (or vice-versa).”*

* **Check:** Attempt must be **consuming** (`after>before`, `draws>"0"`); markers/finals **non-consuming** (`before==after`, `draws="0"`).
* **Action:** Ensure L2 passes **`s_before` & `s_after`** from K-2 to K-3; pass **current** stream to K-4/K-5/K-6 (non-consuming). 

### 8) *“Resume resampled a persisted attempt.”*

* **Check:** For existing `(mid,a)`, L2 must read `{k, s_after}` and **not** call K-2.
* **Action:** Fix pre-emit dedupe (Pattern-A) and resume (Pattern-B). 

### 9) *“Terminal exists but loop continued.”*

* **Check:** L2 must fence on `exists_final` **or** `exists_exhausted`.
* **Action:** Add resolution fence at loop entry. **Exactly one** terminal per merchant. 

### 10) *“Partition path vs envelope mismatch.”*

* **Check:** Events must satisfy path↔embed equality for `{seed, parameter_hash, run_id}`; trace has no `context`.
* **Action:** This is an L0/dictionary breach. Abort run via S0 failure framework. 

### 11) *“Regime inconsistent across events for a merchant.”*

* **Check:** Regime is frozen at K-1 and echoed on non-attempt events.
* **Action:** Ensure a single K-1 call per merchant; pass that `lr` to every kernel. 

### 12) *“Cap marker missing `attempts:64` or `aborted:true`.”*

* **Check:** Schema requires both on abort.
* **Action:** L1 K-5 must assemble payload with `attempts:64, aborted:true`; L2 ensures policy==abort. 

---

## D.4 Read-only triage helpers (L2)

```text
# Resolution fence
resolved(mid) := exists_final(mid) OR exists_exhausted(mid)

# Contiguity check
expect 1..t where t := max_attempt(mid)

# Branch projection
{ k, s_after } := read_attempt_k_after(mid, a)

# A=0 sanity
IF A==0 THEN assert attempts==0 AND no rejections/exhausted
```

These read-only checks use the dictionary-resolved datasets and natural keys from Appendix B; L2 never uses path literals. 

---

## D.5 Recovery procedures (what you may safely do)

* **Crash after event append:** proceed; next emit performs **trace-only repair**; do not re-emit event. 
* **Merchant anomaly (idempotence breach, attempt gaps):** quarantine merchant (stop further S4 writes), continue others; open an ops ticket with the exact natural keys. 
* **Systemic dictionary/IO breach:** escalate via S0 failure bundle and abort run atomically. 

---

## D.6 Preventative checks (pre-merge / CI)

* Unit: enforce **dedupe-before-RNG** and **single K-1** per merchant.
* Property: attempt payload key is **`lambda`**; markers/final use **`lambda_extra`**. 
* Contract: terminal exclusivity by policy; A=0 final-only. 
* Concurrency: per-merchant single writer; adjacency invariant. 

---

## D.7 Escalation map (code → action)

| Issue                                          | Where to fix       | Action                                                               |
|------------------------------------------------|--------------------|----------------------------------------------------------------------|
| Payload key wrong (`lambda` vs `lambda_extra`) | **L1 K-3/K-4/K-6** | Patch kernel payload assembly; L2 unchanged.                         |
| Emitted both exhausted & final at cap          | **L2**             | Fix policy routing (K-5 **or** K-6, not both).                       |
| Attempt non-consuming / marker consuming       | **L1/L0**          | Fix stream passing and emitter identity; L2 must pass correct `s_*`. |
| Resume resampled attempt                       | **L2**             | Enforce Pattern-A/Pattern-B strictly.                                |
| Partition/path drift                           | **L0/Dictionary**  | Abort via S0; investigate writer/config.                             |

---

## D.8 Known-good traces (sanity snapshots)

* **Accept@1:** `Attempt(1, k>0, λ) → Final(K=k, attempts=1, λ_extra, regime)`.
* **Cap-Abort:** For `t=1..64: Attempt(t,k=0,λ) + Rejection(t,λ_extra) → Exhausted(attempts=64, aborted:true, λ_extra)`.
* **Cap-Downgrade:** Same 64 pairs → `Final(K=0, attempts=64, exhausted:true, λ_extra)`.
* **A=0:** `Final(K=0, attempts=0 [,reason])` only. 

This appendix keeps ops **fast and safe**: no re-emits, no payload reconstruction, all decisions grounded in the authoritative **L0 v15** writer/trace contract, **L1 v12** kernel semantics, and the **S4 expanded** terminal rules.   

---