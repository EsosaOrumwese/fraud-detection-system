# State-4 · L1 (kernels/subroutines)

## 1) Purpose & Non-Goals (L1’s remit)

**Purpose.** L1 implements the **logic-only kernels** and the **ZTP attempt loop** that realise S4’s outcome — an authoritative `K_target` per merchant — by invoking **L0 emitters**. L1 transforms **values→values** (no paths) and drives control flow (A=0 short-circuit, accept, or cap policy branch). **S4 is logs-only**; it never encodes cross-country order.

**What L1 owns**

* Build per-merchant **Ctx** (N, A, openness `X_m`, θ, policy) and enforce **preflight gates**:
  `is_multi==true` (S1), `is_eligible==true` (S3), `N≥2` (S2 `nb_final`), and `A≥0`. **If any gate fails, emit nothing for S4.** 
* Compute $\lambda_{\text{extra}}=\exp(\theta_0+\theta_1\log N+\theta_2 X_m)$ in **binary64**; if non-finite or ≤0, fail the merchant (no S4 events). Freeze **regime** once per merchant: `"inversion"` if $\lambda<10$, else `"ptrs"`. 
* Run the **attempt loop** (cap = **64**) and decide when to emit **attempt**, **rejection**, **exhausted** (abort-only), and **final** via L0. One event → one **immediate** cumulative trace (same writer). 

**What L1 does *not* do**

* **No file paths/partitions/lineage stamping** in L1. L2 **supplies** `{seed, parameter_hash, run_id, manifest_fingerprint}` to L1, and the **L0 emitters** stamp the event envelope and append the **immediate** cumulative trace under dictionary-resolved `{seed, parameter_hash, run_id, manifest_fingerprint}`. 
* **No envelope/trace internals** in L1 (the emitters do event + immediate trace). 
* **No validation/CI** (L3 proves identities and corridors). S4 provides **logs only** and **never encodes inter-country order** (S3 remains order authority). 

**Authoritative outcome of S4.**
For each **resolved** merchant, emit **exactly one** `ztp_final` — **except** when cap hits and policy=`abort` (then **no final**; only the exhausted marker). On policy=`downgrade_domestic`, `ztp_final{K_target=0, exhausted:true}` is written. Downstream S6 **realises** $K_{\text{realized}}=\min(K_{\text{target}},A)$.

---

## 2) Binding Anchors (read-first pointers)

**L0 emitters L1 calls (names are normative; trace is appended by the emitter wrapper):**

* `event_poisson_ztp(…)` — **consuming attempt** → `rng_event_poisson_component`. 
* `emit_ztp_rejection_nonconsuming(…)` — **non-consuming zero marker** → `rng_event_ztp_rejection`. 
* `emit_ztp_retry_exhausted_nonconsuming(…)` — **non-consuming cap-hit marker (abort-only)** with **`attempts:64`** and **`aborted:true`** → `rng_event_ztp_retry_exhausted`. 
* `emit_ztp_final_nonconsuming(…)` — **non-consuming finaliser** → `rng_event_ztp_final`. *(Absent only on policy=`abort`.)* 

> **Trace discipline.** L0 emitters append **one** cumulative `rng_trace_log` row **immediately after** each event (same writer); L1 never calls the trace writer directly. 

**Schema anchors (authoritative JSON-Schema pointers):**

* `schemas.layer1.yaml#/rng/events/poisson_component` — attempt payload uses **`lambda`**; **`attempt` is required**. 
* `schemas.layer1.yaml#/rng/events/ztp_rejection` — non-consuming; uses **`lambda_extra`** and `attempt`. 
* `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` — non-consuming; requires **`attempts:64`** and **`aborted:true`**. 
* `schemas.layer1.yaml#/rng/events/ztp_final` — non-consuming finaliser with `{K_target, lambda_extra, attempts, regime[, exhausted?][, reason?]}`. 
* `schemas.layer1.yaml#/rng/core/rng_trace_log` — trace rows **embed `run_id` & `seed`**; **no `context`**. 

**Data Dictionary (IDs, partitions, writer-sort keys):**

* `rng_event_poisson_component` — partitions `["seed","parameter_hash","run_id"]`; ordering `["merchant_id","attempt"]`. 
* `rng_event_ztp_rejection` — same partitions; ordering `["merchant_id","attempt"]`. 
* `rng_event_ztp_retry_exhausted` — same partitions; ordering `["merchant_id","attempts"]`. 
* `rng_event_ztp_final` — same partitions; ordering `["merchant_id"]`. 
* `rng_trace_log` — same partitions; **no mandated writer-sort** (cumulative per `(module, substream_label)`). 

**Expanded spec (L1 must respect):**

* **Gates:** S1 `is_multi=true`, S3 `is_eligible=true`; ineligible/single merchants **produce no S4 events**. 
* **A=0 short-circuit:** emit a single `ztp_final{K_target=0, attempts:0[, reason:"no_admissible"]?}`; **no attempts**. 
* **Cap semantics:** cap is **64**; policy=`abort` ⇒ **no** final; policy=`downgrade_domestic` ⇒ final with `K_target=0, exhausted:true`.
* **Separation of concerns:** S4 **fixes `K_target` only**; **S6 realises** $K_{\text{realized}}=\min(K_{\text{target}},A)$; S3 remains the **order authority**.

---

## 3) Closed Literals & Constants (copy-safe)

These are the **only** literals and fixed constants L1 should ever type. Everything else (paths, lineage, partitions) is L2/L0 territory.

### 3.1 Required string literals

| Surface           | Value               | Where it applies            | Notes                                    |
|-------------------|---------------------|-----------------------------|------------------------------------------|
| `module`          | `1A.s4.ztp`         | **All S4 events** & trace   | **Spec-pinned** (frozen label registry). |
| `substream_label` | `poisson_component` | **All S4 events** & trace   | **Spec-pinned** (frozen label registry). |
| `context`         | `ztp`               | **Events only** (not trace) | Trace has **no** `context`.              |

### 3.2 Enumerations

| Name                    | Allowed values                      | Binding                                                           |
|-------------------------|-------------------------------------|-------------------------------------------------------------------|
| `regime`                | `{ "inversion", "ptrs" }`           | Schema enum; **fixed per merchant** (chosen once; see threshold). |
| `ztp_exhaustion_policy` | `{ "abort", "downgrade_domestic" }` | Governed; appears in inputs/policy but **not** in event payloads. |
| `reason` *(optional)*   | `{ "no_admissible" }`               | **Omit unless the bound `ztp_final` schema version defines it.**  |

### 3.3 Numeric thresholds & caps

* **Regime boundary:** $\lambda_{\text{extra}}^\star = 10$. If $\lambda_{\text{extra}} < 10 \Rightarrow$`inversion`; else `ptrs`. Binary64 decision (**no epsilons**).
* **ZTP zero-draw cap:** **64 attempts** maximum (**spec-fixed**). The schema pins this via `ztp_retry_exhausted.attempts = 64` (const) in the abort marker.
* **Attempt index domain:** `attempt ≥ 1` (**schema**). Enforce **1..64** by **spec** (loop cap), and ensure indices are **1-based, strictly increasing**.

### 3.4 Payload minima (field names are normative)

Use **exactly** these payload keys when forming inputs to L0 emitters (L1 provides values; **L0 stamps the envelope**):

| Family                          | Minimum payload (no lineage fields)                                                                                 |
|---------------------------------|---------------------------------------------------------------------------------------------------------------------|
| `rng_event_poisson_component`   | `{ merchant_id, attempt, k, lambda }` — **consuming** attempt *(“lambda” per schema v2)*.                           |
| `rng_event_ztp_rejection`       | `{ merchant_id, attempt, k:0, lambda_extra }` — **non-consuming** zero marker.                                      |
| `rng_event_ztp_retry_exhausted` | `{ merchant_id, attempts:64, lambda_extra, aborted:true }` — **non-consuming**, **abort-only** (**both required**). |
| `rng_event_ztp_final`           | `{ merchant_id, K_target, lambda_extra, attempts, regime[, exhausted?, reason?] }` — **non-consuming** finaliser.   |

### 3.5 Numeric profile (constraints L1 must respect)

* **IEEE-754** binary64; **RNE**; **FMA off**; no FTZ/DAZ.
* **Strict-open** $u\in(0,1)$; **budgets are measured**, not inferred (`draws` = actual uniforms; `blocks = after − before`); L0 stamps and logs them.

### 3.6 Copy-safe constant block (for your pseudocode)

```text
# Literals (spec-pinned)
MODULE              := "1A.s4.ztp"                 # events & trace
SUBSTREAM_LABEL     := "poisson_component"         # events & trace
EVENT_CONTEXT       := "ztp"                       # events only (trace has no context)

# Enums
REGIME              ∈ {"inversion","ptrs"}
POLICY              ∈ {"abort","downgrade_domestic"}
REASON_OPT          ∈ {"no_admissible"}            # omit unless this schema version defines it

# Thresholds & caps
LAMBDA_REGIME_STAR  := 10.0                        # binary64 exact
MAX_ZTP_ATTEMPTS    := 64                          # spec-fixed cap; loop enforces 1..64; schema pins attempts:64 on exhausted

# Schema-aligned payload keys (no lineage here)
POISSON_ATTEMPT_PAY := { merchant_id, attempt, k, lambda }                  # attempts use 'lambda' (schema v2)
ZTP_REJECTION_PAY   := { merchant_id, attempt, k:0, lambda_extra }
ZTP_EXHAUSTED_PAY   := { merchant_id, attempts:64, lambda_extra, aborted:true }
ZTP_FINAL_PAY       := { merchant_id, K_target, lambda_extra, attempts, regime [, exhausted?, reason?] }
```

---

## 4) Numeric & RNG Policy (constraints L1 must respect)

This section fixes the math and randomness rules L1 must **obey** while driving S4’s attempt loop. L1 does *not* stamp envelopes or traces—that’s L0—but every kernel here must compute under these constraints so the rows L0 writes are **bit-reproducible** across machines.

### 4.1 Floating-point profile (determinism)

* **Format:** IEEE-754 **binary64** throughout; all intermediates and constants are binary64.
* **Rounding mode:** **Round-to-Nearest, ties-to-Even (RNE)**.
* **FMA:** **Disabled** (no fused multiply-add).
* **Denormals:** **No FTZ/DAZ** (no flush-to-zero, no denormals-are-zero).
* **Math functions:** use natural log/exp with domain guards; do not substitute polynomial “fast-math.”
* **Comparisons & branches:** evaluate on binary64 values; no epsilon heuristics unless explicitly specified (none here).

### 4.2 Link function (how λ is computed)

For each merchant, L1 computes the ZTP link **once** (constant for the entire loop):

$$
\lambda_{\text{extra}}=\exp\!\bigl(\theta_0+\theta_1\cdot\log N+\theta_2\cdot X_m\bigr)
$$

**Guards (fail-fast):** reject as **NUMERIC_INVALID** if $\lambda_{\text{extra}}$ is NaN, $+\infty$, or $\le 0$. *(Note: $\exp(\cdot)$ is positive; this guard is defensive against upstream numeric faults.)*
On success, **freeze** $\lambda_{\text{extra}}$ for this merchant; it does **not** change across attempts.

### 4.3 Regime selection (frozen per merchant)

Choose the **sampler regime** once from the frozen $\lambda_{\text{extra}}$:

* If $\lambda_{\text{extra}} < \lambda^\star$ with $\lambda^\star=10$: **inversion** regime.
* Else: **PTRS** regime.

This regime is a **per-merchant constant**; it **must not change in-loop**.

### 4.4 Uniforms & budgets (what “draws” and “blocks” mean)

All pseudo-random numbers are strict-open **$u\in(0,1)$**. L0 measures budgets; L1 must route all sampling through the L0 RNG lane so L0 can record:

* **before/after counters** for the event’s substream,
* **blocks** $=$ `after − before` (u128 delta),
* **draws** $=$ decimal-u128 count of the **actual** uniforms consumed by this event.

**Regime expectations (L1 codes to these; L0 measures):**

* **PTRS:** consumes a **variable (≥2)** number of uniforms **per attempt** (two per PTRS iteration; iterations may exceed one). **Budgets are measured, not inferred.**
* **Inversion:** consumes a **variable** number of uniforms (include the stopping draw). Route every uniform through the RNG lane so measured counts match what’s written.

> L1 never fabricates `draws`/`blocks`; it **routes** sampling through the provided RNG lane so L0 can measure and stamp the envelope.

### 4.5 Substreams & isolation (where randomness comes from)

* S4 uses **one merchant-keyed substream** defined by the pair `(module="1A.s4.ztp", substream_label="poisson_component")` **shared by all S4 events**.
* **Only attempts consume** on this substream; **rejection**, **exhausted**, and **final** are **non-consuming** under the **same label**.
* Do **not** mix labels or reuse substreams from other states; do **not** chain counters across families—each event is measured independently.

### 4.6 Attempt counter discipline

* Attempt index is **1-based** and **strictly increasing** per merchant.
* Maximum attempts **64** (**spec-fixed cap**). The loop must stop **no later** than attempt 64. *(The schema pins the cap on the exhausted marker via `attempts: 64`; it does not bound the attempt payload.)*

### 4.7 Non-consuming vs consuming events (**emitter-enforced** identities; L1 passes `(s_before,s_after,bud)`)

When calling an L0 emitter:

* **Consuming (attempt):** `after > before`, `blocks > 0`, `draws > "0"`.
* **Non-consuming (rejection, exhausted, final):** `after == before`, `blocks = 0`, `draws = "0"`.

### 4.8 A=0 short-circuit (no RNG)

If admissible foreigns **A = 0**, L1 must **not draw any uniforms**. Emit **one**
`ztp_final{ K_target=0, attempts:0 [, reason:"no_admissible"]? }` (non-consuming). **No attempt or marker rows** are written.

### 4.9 Concurrency & reproducibility

* Parallelize **across** merchants only; each merchant’s stream is serial within its substream.
* Preserve **event → immediate trace** adjacency: the **emitter** appends the trace **immediately (same writer)**; never interleave other labels between an event and its trace.
* All arithmetic and branching in this section are deterministic under the profile above; do not introduce data-dependent concurrency that would reorder attempts.

---

## 5) Upstream Gates & Preconditions (from S1–S3)

This section fixes exactly **when S4·L1 is allowed to run** and **what facts it must already have**—as *values*, not files. If any gate fails, **S4 emits nothing** for that merchant and surfaces a failure mapped to the S0.9 taxonomy (merchant-abort only where the expanded spec allows; otherwise run-abort via L0/L3).

### 5.1 Gate summary (decision surface)

Let $m$ be a merchant. S4·L1 may proceed **iff all** of the following hold:

1. **Hurdle branch — S1 proves multi.**
   **Exactly one** hurdle row exists for $m$ and its payload has `is_multi==true`. (Presence gating for S4 streams is enforced via the **Dictionary** on this predicate.)

2. **Eligibility — S3 permits cross-border.**
   `is_eligible==true`. If `is_eligible==false`, S4 **must not** emit any events.

3. **Multi-site total — S2 fixes $N\ge 2$.**
   **Exactly one** `nb_final` exists for $m$ and its payload satisfies `n_outlets = N ≥ 2`. (S4 never resamples or alters $N$.)

4. **Admissible universe — S3 yields $A$.**
   S3’s candidate set is valid (**home present, rank 0; ranks contiguous**), and

   $$
   A := \bigl|\ \text{S3.candidate\_set}\setminus\{\text{home}\}\ \bigr| \in \mathbb{Z}_{\ge 0}.
   $$

   If $A=0$, S4 **short-circuits** (finaliser only; no attempts).

5. **Policy present & valid — exhaustion handling.**
   `policy ∈ {"abort","downgrade_domestic"}` is provided (governed; participates in `parameter_hash`). The **cap is 64 (spec-fixed)**; the schema pins this on the **exhausted marker** via `attempts: 64`.

> **Authority boundaries.** Inter-country order authority remains **S3 `candidate_rank`** (contiguous; home = 0). S4 is **logs-only** and never encodes cross-country order.

---

### 5.2 Minimal inputs S4·L1 expects (values only)

Per merchant $m$, L1 requires these **value-level** inputs (no paths/IO):

* `is_multi : bool` — from S1 hurdle payload. **Must be `true`.**
* `is_eligible : bool` — from S3 eligibility. **Must be `true`.**
* `N : int` — from S2 `nb_final.n_outlets`. **Must satisfy $N\ge 2$.**
* `A : int` — computed as above from S3 ranked candidates. **Must satisfy $A\ge 0$.** Short-circuit if $A=0$.
* `X_m : float` — S4 openness feature (default 0.0 if missing, per expanded spec).
* `θ=(θ0,θ1,θ2)` — governed link parameters (**participate in `parameter_hash`**).
* `policy : {"abort","downgrade_domestic"}` — exhaustion policy (**participates in `parameter_hash`**).
  **Cap = 64 (spec-fixed)**; schema pins this in the exhausted marker via `attempts: 64`.

*(Lineage tokens `{seed, parameter_hash, run_id, manifest_fingerprint}` are made available to L0 for envelopes; L1 does not mint/compare them.)*

---

### 5.3 Preflight checks (what L1 must assert before any attempt)

**Fail fast** (no S4 emissions) if any predicate below is false:

* **G0 Eligibility:** `is_eligible==true`. Otherwise **emit nothing** for S4.
* **G1 Hurdle:** exactly one hurdle row exists and `is_multi==true`.
* **G2 NB fact:** `N` present and `N ≥ 2` from `nb_final`.
* **G3 S3 authority:** candidate set valid (home present; contiguous ranks) so that `A` is well-defined. If S3 failed rank/home checks, S3 already stops the merchant—S4 **must not** run.
* **G4 Policy domain:** `policy ∈ {"abort","downgrade_domestic"}`; **cap = 64 (spec-fixed)**; schema pins this on the exhausted marker via `attempts: 64`.

> **Scope reminder.** S4 **reads** `N`, `A`, `policy`, and emits **logs only**; it never alters `N` and never encodes cross-country order.

---

### 5.4 Preflight pseudocode (language-agnostic)

```text
PROC s4_preflight(ctx):
  # Eligibility & Hurdle
  REQUIRE ctx.is_eligible == true                              # else BYPASS S4 (no logs)
  REQUIRE ctx.is_multi   == true                               # else BYPASS S4 (no logs)

  # S2 fact
  REQUIRE IS_INT(ctx.N) AND ctx.N >= 2                         # else fail via F3/F4 mapping

  # S3 admissible universe
  REQUIRE IS_INT(ctx.A) AND ctx.A >= 0                         # else S3 already failed merchant

  # Policy
  REQUIRE ctx.policy IN {"abort","downgrade_domestic"}         # policy mismatch → configuration failure

  RETURN OK
END

IF ctx.A == 0:
  # Short-circuit: no RNG, no attempts, no markers
  CALL K-0(ctx)   # K-0 computes λ/regime and emits the non-consuming final via L0
  RETURN
```

---

## 6) Inputs (value-level, no I/O) + Preflight

This section lists the **exact values** S4·L1 needs per merchant and the **fail-fast** checks before any sampling. No paths, no lineage stamping, no writes—those belong to L0/L2. Sources are S1/S2/S3 outputs and governed S4 parameters.

### 6.1 Value inputs (per merchant $m$)

| Name                           | Type                                                   | Meaning / Source                                                                                                                                               |
|--------------------------------|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `merchant_id`                  | `int64`                                                | Ingress merchant key (used in all S4 payloads).                                                                                                                |
| `is_multi`                     | `bool`                                                 | S1 hurdle outcome; **must be true** for S4 to run. (Dictionary presence-gate ties S4 streams to hurdle `is_multi==true`.)                                      |
| `is_eligible`                  | `bool`                                                 | S3 cross-border eligibility; **must be true**. If false, S4 **emits nothing**.                                                                                 |
| `N`                            | `int ≥ 2`                                              | Total outlets from S2 **`nb_final`** (read-only in S4).                                                                                                        |
| `A`                            | `int ≥ 0`                                              | **Admissible foreign count** = number of S3 candidates **excluding home**. If `A==0` ⇒ short-circuit S4 (no attempts). Inter-country order stays S3 authority. |
| `X_m`                          | `float`                                                | Openness/feature term used in the S4 link $\lambda_{\text{extra}}$. *(Governed feature; default policy in S4 expanded; default to 0.0 if missing.)*            |
| `θ = (θ0, θ1, θ2)`             | `tuple(float)`                                         | S4 ZTP link parameters *(governed; participate in `parameter_hash`)*.                                                                                          |
| `policy`                       | `{"abort","downgrade_domestic"}`                       | Exhaustion policy *(participates in `parameter_hash`)*. **Cap = 64 (spec-fixed)**; schema v2 pins this on the exhausted marker via `attempts: 64`.             |
| `lineage` (pass-through to L0) | `{seed, parameter_hash, run_id, manifest_fingerprint}` | Provided to L0 for envelope/trace stamping; L1 **does not** mint or compare.                                                                                   |

> **Why only these?** S4 is **logs-only**: it fixes `K_target` via `ztp_final` and provides audit events. Cross-country order remains in S3; S4 never emits order or probabilities.

---

### 6.2 Provenance sanity (where each input is read from)

* **Hurdle (S1):** presence-gated S4 streams (`poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`) require hurdle **`is_multi==true`**.
* **Eligibility (S3):** `is_eligible==true` is a hard precondition; if false, **no S4 events**.
* **Total `N` (S2):** from the S2 `nb_final` row; S4 treats it as read-only.
* **Admissible `A` (S3):** candidate set valid (**home rank 0; ranks contiguous**), then $A=\lvert\text{candidates}\setminus\{\text{home}\}\rvert$. If S3 failed rank/home checks, S4 **must not** run.
* **(Reference — enforced by dictionary/L0; L2 orchestrates):** all S4 logs write under partitions `{seed, parameter_hash, run_id, manifest_fingerprint}`; writer-sort keys are fixed per family (attempts/rejections `(merchant_id,attempt)`, exhausted `(merchant_id,attempts)`, final `(merchant_id)`).

---

### 6.3 Preflight (fail-fast) checks

Run these *before* any attempt:

1. **Eligibility:** `is_eligible == true`. Otherwise **emit nothing** for $m$.
2. **Hurdle:** **exactly one** hurdle row exists and `is_multi == true`.
3. **NB final:** `N` is present and `N ≥ 2` (from S2 `nb_final`).
4. **S3 authority:** `A` is defined from a valid candidate set (home present; contiguous ranks). If `A == 0`, **short-circuit** (emit final only; no attempts).
5. **Policy domain:** `policy ∈ {"abort","downgrade_domestic"}`; **cap = 64 (spec-fixed)**; schema pins this on the exhausted marker via `attempts: 64`.

**Preflight pseudocode (value-only):**

```text
PROC s4_preflight(ctx):
  REQUIRE ctx.is_eligible == true                              # else BYPASS S4 (no logs)
  REQUIRE ctx.is_multi   == true                               # else BYPASS S4 (no logs)

  REQUIRE IS_INT(ctx.N) AND ctx.N >= 2                         # else fail via F3/F4 mapping
  REQUIRE IS_INT(ctx.A) AND ctx.A >= 0                         # else S3 already failed merchant

  REQUIRE ctx.policy IN {"abort","downgrade_domestic"}         # config failure if not

  IF ctx.A == 0:
    CALL K-0(ctx)   # computes λ/regime and emits the non-consuming final via L0
    RETURN SHORT_CIRCUIT

  RETURN OK
END
```

---

## 7) Outputs (authoritative results of S4)

**What S4 produces:** **logs only**, via L0 emitters. The single authoritative decision is **`K_target`** (fixed by `ztp_final`). S4 never writes cross-country order or any egress tables.

### 7.1 Event families (exact surfaces)

| Family (Dictionary ID)          | Consuming? | Minimal payload (no lineage; **no extra fields allowed**)                          | Partitions                     | Sort key                 |
|---------------------------------|-----------:|------------------------------------------------------------------------------------|--------------------------------|--------------------------|
| `rng_event_poisson_component`   |    **Yes** | `{ merchant_id, attempt, k, lambda }`                                              | `{seed,parameter_hash,run_id}` | `(merchant_id,attempt)`  |
| `rng_event_ztp_rejection`       |         No | `{ merchant_id, attempt, k:0, lambda_extra }`                                      | `{seed,parameter_hash,run_id}` | `(merchant_id,attempt)`  |
| `rng_event_ztp_retry_exhausted` |         No | `{ merchant_id, attempts:64, lambda_extra, aborted:true }`                         | `{seed,parameter_hash,run_id}` | `(merchant_id,attempts)` |
| `rng_event_ztp_final`           |         No | `{ merchant_id, K_target, lambda_extra, attempts, regime[, exhausted?, reason?] }` | `{seed,parameter_hash,run_id}` | `(merchant_id)`          |

**Envelope minima (stamped by L0):** each **event** row embeds `run_id, seed, parameter_hash, manifest_fingerprint` + `rng_counter_{before,after}_{hi,lo}`, `blocks`, `draws`; **trace** rows embed `run_id & seed` + before/after counters and cumulative totals (no `context`). One **cumulative** trace row is appended **immediately after every event** by the same writer.

### 7.2 Cardinality & outcomes (merchant-scoped)

* **Attempts & rejections:** at most one `poisson_component` per `(merchant_id,attempt)`; at most one `ztp_rejection` per `(merchant_id,attempt)`.
* **Cap path:** at most one `ztp_retry_exhausted` per merchant, and **only** when policy = `"abort"`. Payload **must** carry **`attempts:64` and `aborted:true`**.
* **Finaliser:** **exactly one** `ztp_final` per **resolved** merchant (absent only on hard abort). It **fixes** the authoritative **`K_target`** (≥1 on acceptance; 0 on A=0 short-circuit or `"downgrade_domestic"`).
**A = 0 short-circuit:** emit **only** `ztp_final{K_target=0, attempts:0, lambda_extra, regime [,reason:"no_admissible"]?}`; **no** attempts/rejections/exhausted. *(Omit `reason` unless the bound schema version defines it.)*

### 7.3 Event discipline & identities (must hold)

* **Consuming vs non-consuming:** attempts satisfy `after > before`, `blocks = after−before`, `draws > "0"`; markers/final satisfy `before == after`, `blocks = 0`, `draws = "0"`. L0 measures and stamps these; L1 must route sampling through the lane.
* **Trace adjacency:** one **cumulative** `rng_trace_log` append **after every event** (same writer, immediate).

### 7.4 Authority boundaries & hand-off

S4’s **only** authoritative decision is `K_target` (in `ztp_final`). S4 **does not** cap to `A` and **never** encodes inter-country order. S6 must realise $K_{\text{realized}}=\min(K_{\text{target}}, A)$ using S3’s `candidate_rank`.

---

## 8) Handoff Summary (quick-read)

**Audience:** the engineer wiring **L2 orchestration** and downstream state owners (S6/S7…).
**Promise:** after L1 finishes a merchant, you have everything needed to commit logs and continue—no guessing, no extra shaping.

---

### 8.1 What L1 guarantees when it returns (per merchant)

* **Decision:** exactly one of

  * **A=0 short-circuit:** a single `ztp_final{K_target=0, attempts:0[, reason?]}`; **no** attempts/rejections/exhausted.
  * **Accepted:** at least one `poisson_component` with `k>0`, then **one** `ztp_final{K_target≥1}`.
  * **Cap path (attempts ≤ 64):**

    * **policy="abort"** → `ztp_retry_exhausted{attempts:64, aborted:true}` **and no final**.
    * **policy="downgrade_domestic"** → **no** exhausted marker, **one** `ztp_final{K_target=0, exhausted:true}`.
* **Event→trace discipline:** after **every** event append, **the same writer immediately** appends **exactly one** cumulative trace row.
* **Schema-true payloads:** attempts `{merchant_id, attempt, k, lambda}`; rejections `{merchant_id, attempt, k:0, lambda_extra}`; exhausted `{merchant_id, attempts:64, lambda_extra, aborted:true}`; final `{merchant_id, K_target, lambda_extra, attempts, regime[, exhausted?, reason?]}`.
* **No order leakage:** S4 never encodes cross-country order; S3 `candidate_rank` remains the sole authority.
* **Idempotence surface:** if an event is present but its immediately following trace is missing, the crash window is **at most one trace**; no duplicate finals are ever written.

---

### 8.2 What L2 must do next (orchestrate & resume)

**For each merchant completed by L1:**

1. **Do not call emitters.** 
   L1 kernels (K-3..K-6) call L0 emitters and stamp **event + immediate trace (same writer)**. L2 supplies lineage/values to L1 **(including `manifest_fingerprint`)**, and manages parallelism, dedupe and resume.
   **Do not invoke emitters in L2.** **L0** resolves dictionary IDs and writes events + trace under `{seed, parameter_hash, run_id, manifest_fingerprint}`; L2 does **not** stamp lineage, resolve paths, or reshape payloads.

2. **Ordering & adjacency discipline.**
   Maintain the call order so that **each event** is immediately followed by its trace (as L0 already does). When batching across merchants, follow dictionary writer-sort keys to reduce merge churn: attempts/rejections `(merchant_id,attempt)`, exhausted `(merchant_id,attempts)`, final `(merchant_id)`. (Counters remain the authoritative order.)

3. **Resume safety (on rerun).**
   If an event exists without the following trace: call the **L0 trace-repair** to append **one** cumulative trace; **do not** re-emit the event. If a `ztp_final` exists, skip the merchant (finals are unique).

4. **Downstream visibility (no new datasets).**
   **Do not create auxiliary summary tables.** Downstream states read the authoritative `ztp_final` stream and apply their own logic.

5. **Handle failures.**
   Map surfaced L1 failures (e.g., `NUMERIC_INVALID` λ, `POLICY_CONFLICT`, `EMIT_FAIL`) to the canonical S0.9 failure codes; quarantine the merchant; do not partially commit additional events.

---

### 8.3 What S6/S7+ must rely on (downstream contract)

* **Authoritative quantity:** `K_target` from `ztp_final`.
* **Realisation rule:** `K_realized = min(K_target, A)` where `A` comes from S3; never exceed `A`.
* **Order:** use S3 `candidate_rank` (home=0; contiguous) for cross-country sequencing.
* **Audit:** attempts/rejections/exhausted logs provide the complete replay trail; **do not** infer probabilities from them.

---

### 8.4 What is **not** included in this handoff (so you don’t look for it)

* No coordinates/timezones, no egress tables, no inter-country order, no probabilities, no CI verdicts.
* L1 produced **logs only** and one authoritative decision `K_target`; everything else is either upstream (S1–S3) or downstream (S6+).

---

## 9) Type Ledger (value structs only, with payload crosswalk)

This ledger defines **only the value-level types** L1 manipulates and the **exact payload shapes** L0 will emit for each event family. **No paths, no lineage columns**—those are added by L0/L2.

### 9.1 Enums (closed)

```text
enum Regime    = { "inversion", "ptrs" }            # frozen per merchant after λ freeze
enum Policy    = { "abort", "downgrade_domestic" }  # governs cap-handling branch
enum ReasonOpt = { "no_admissible" }                # present only if bound schema version allows
```

### 9.2 Core value structs (inputs → kernels → finals)

```text
type Ctx = {
  merchant_id : int64,       # ingress key; appears in every payload
  is_eligible : bool,        # S3 gate; MUST be true (else S4 emits nothing)
  is_multi    : bool,        # S1 gate;  MUST be true
  N           : int,         # total outlets from S2; N ≥ 2
  A           : int,         # admissible foreigns from S3; A ≥ 0
  X_m         : float64,     # openness feature for λ link
  θ0, θ1, θ2  : float64,     # ZTP link parameters
  policy      : Policy,      # {"abort","downgrade_domestic"}
  # pass-through for L0 envelopes (L1 does not mint/compare these):
  lineage     : { seed: u64, parameter_hash: hex64, run_id: hex32, manifest_fingerprint: hex64 }
}

type LambdaInputs = {
  N   : int,
  X_m : float64,
  θ0  : float64,
  θ1  : float64,
  θ2  : float64
}

type LambdaRegime = {
  lambda_extra : float64,     # exp(θ0 + θ1·log N + θ2·X_m)
  regime       : Regime       # "inversion" if lambda_extra < 10, else "ptrs"
}

type AttemptResult = {
  attempt      : int,         # 1-based, strictly increasing
  k            : int,         # Poisson draw for this attempt
  lambda_extra : float64      # echoed for rejection/final; renamed to 'lambda' in attempt payload
  # NOTE: counters/blocks/draws are measured by L0; not fields here
}

type Finaliser = {
  K_target   : int,           # authoritative result (≥1 on accept; 0 on A=0 or downgrade)
  attempts   : int,           # last attempt index (0 on A=0 short-circuit)
  regime     : Regime,
  exhausted? : bool,          # present iff cap path taken with downgrade
  reason?    : ReasonOpt      # "no_admissible" when A=0, if this schema version allows
}
```

**Invariants on these types**

* `attempt` is **1..64** (spec-fixed cap) and **strictly increasing** within a merchant. *(Schema pins the cap on the exhausted marker via `attempts:64`; the attempt row itself has no schema max.)*
* `regime` is **fixed per merchant** after λ freeze (does not change in-loop).
* If `A == 0` then `Finaliser = {K_target:0, attempts:0, …}` and **no** `AttemptResult` exists; **no** `ztp_rejection` or `ztp_retry_exhausted` are written.
* If policy=`abort` and cap is hit, **no finaliser** exists (only the exhausted marker is emitted). If policy=`downgrade_domestic`, finaliser exists with `{K_target:0, attempts:64, exhausted:true}`.

### 9.3 Payload crosswalk (value → schema payloads)

> The tables below show the **exact** payload fields L0 will emit for each event, constructed from L1’s values. **No lineage fields** appear here; L0 stamps the envelope and the cumulative trace.

#### a) Attempt (consuming) → `rng_event_poisson_component`

```text
from  : { merchant_id, AttemptResult{ attempt, k, lambda_extra } }
emit  : { merchant_id, attempt, k, lambda = lambda_extra }     # attempts use field name "lambda" (schema v2)
```

#### b) Rejection (non-consuming, k=0) → `rng_event_ztp_rejection`

```text
from  : { merchant_id, AttemptResult{ attempt, lambda_extra } }
emit  : { merchant_id, attempt, k:0, lambda_extra }
```

#### c) Cap-hit marker (non-consuming, abort-only) → `rng_event_ztp_retry_exhausted`

```text
from  : { merchant_id, LambdaRegime{ lambda_extra } }
emit  : { merchant_id, attempts:64, lambda_extra, aborted:true }   # both fields are schema-required
```

#### d) Finaliser (non-consuming) → `rng_event_ztp_final`

```text
from  : { merchant_id, Finaliser{ K_target, attempts, regime, exhausted?, reason? }, LambdaRegime{ lambda_extra } }
emit  : { merchant_id, K_target, lambda_extra, attempts, regime [, exhausted?, reason?] }
# 'reason' MUST be omitted unless the bound schema version defines it.
```

### 9.4 Minimal constructor & guards (for kernels)

* **Construct `LambdaRegime` once** per merchant from `LambdaInputs`:

  $$
    \lambda_{\text{extra}}=\exp(\theta_0+\theta_1\log N+\theta_2 X_m),\quad
    \text{regime}=\begin{cases}
      \text{"inversion"} & \lambda_{\text{extra}}<10\\
      \text{"ptrs"}      & \text{otherwise}
    \end{cases}
  $$

  **Guard:** reject as **NUMERIC_INVALID** if $\lambda_{\text{extra}}$ is non-finite or $\le 0$.

* **`AttemptResult` is pure (value-only)**: it carries `(attempt, k, lambda_extra)`; **counters/blocks/draws are not fields**—L0 measures and stamps them in the envelope.

* **Create `Finaliser` exactly once**:

  * **Accepted:** `K_target = k` from the accepting attempt; `attempts = attempt`.
  * **A=0 short-circuit:** `K_target = 0`, `attempts = 0`, optional `reason = "no_admissible"` (if allowed).
  * **Cap downgrade:** `K_target = 0`, `attempts = 64`, `exhausted = true`.
  * **Cap abort:** **do not** construct a finaliser; emit only the exhausted marker.

---

## 10) Kernel Index (what this file implements)

Below is the **concise map of every L1 routine** you will implement for S4. Each item states what it does, whether it’s **pure**, **RNG-consuming (no event I/O)**, or **emits via L0**, the **value-level I/O**, and which **L0 emitter** it calls (if any). No paths, no lineage stamping here.

### Legend

* **Pure** = value→value logic; no RNG, no I/O.
* **RNG-consuming** = uses L0’s sampler (uniforms consumed); **no event/trace I/O**.
* **Emits** = calls an L0 **emitter** (which stamps envelope **and** appends the trace).

---

### K-0 — `short_circuit_A0(ctx)`: A=0 path (emit final only)

* **Purity:** Emits
* **Input:** `ctx = { merchant_id, is_eligible=true, is_multi=true, A=0, N, X_m, θ, policy, lineage:{seed,parameter_hash,run_id,manifest_fingerprint} }`
* **Output (value):** `Finaliser{K_target=0, attempts=0, regime, reason?}`
* **Emits:** `emit_ztp_final_nonconsuming(merchant_id, K_target=0, lambda_extra, attempts=0, regime [, reason])`
* **Notes:** No attempts, no rejections, **no exhausted** marker. O(1).

---

### K-1 — `freeze_lambda_regime(ctx)`: compute & freeze λ and regime

* **Purity:** Pure
* **Input:** `LambdaInputs{N, X_m, θ0, θ1, θ2}`
* **Output:** `LambdaRegime{ lambda_extra, regime∈{"inversion","ptrs"} }`
* **Math:** $\lambda_{\text{extra}}=\exp(\theta_0+\theta_1\log N+\theta_2 X_m)$; regime = `inversion` if $\lambda_{\text{extra}}<10$ else `ptrs`.
* **Errors:** `NUMERIC_INVALID` if λ non-finite or ≤0. O(1).

---

### K-2 — `poisson_attempt_once(lr, s_before)`: sample one attempt

* **Purity:** **RNG-consuming (no event I/O)**
* **Input:** `lr={lambda_extra, regime}`, `s_before` (current substream counter)
* **Calls (L0 sampler):** `poisson_attempt_with_budget(lambda_extra, regime, s_before)`
* **Output:** `(k, s_after, bud)` where `bud` contains the measured blocks/draws for this attempt
* **Notes:** Strict-open uniforms; PTRS/inversion per `regime`. Attempt index is supplied by the caller (K-7). O(1).

---

### K-3 — `emit_poisson_attempt(ctx, lr, attempt, k, s_before, s_after, bud)`

* **Purity:** Emits
* **Input:** `merchant_id`, `lineage:{seed,parameter_hash,run_id,manifest_fingerprint}`, `lr.lambda_extra`, `attempt`, `k`, `s_before`, `s_after`, `bud`
* **Emits:** `event_poisson_ztp(...)` → payload `{ merchant_id, attempt, k, lambda }` (where **`lambda = lr.lambda_extra`**; attempts use key **`lambda`** per schema v2).
  The **emitter** stamps the envelope and **immediately** appends one cumulative trace row (same writer).
* **Identities:** Consuming envelope (`after>before`, `blocks=after−before`, `draws>"0"`). O(1).

---

### K-4 — `emit_ztp_rejection_nonconsuming(ctx, lr, attempt)`

* **Purity:** Emits
* **Input:** `merchant_id`, `lineage:{seed,parameter_hash,run_id,manifest_fingerprint}`, `attempt`, `lr.lambda_extra`
* **Emits:** `emit_ztp_rejection_nonconsuming(...)` → `{ merchant_id, attempt, k:0, lambda_extra }` (+ immediate trace)
* **Identities:** Non-consuming (`before==after`, `blocks=0`, `draws="0"`). O(1).

---

### K-5 — `emit_ztp_retry_exhausted_nonconsuming(ctx, lr)`

* **Purity:** Emits
* **Input:** `merchant_id`, `lineage:{seed,parameter_hash,run_id,manifest_fingerprint}`, `lr.lambda_extra`
* **Emits:** `emit_ztp_retry_exhausted_nonconsuming(...)` → `{ merchant_id, attempts:64, lambda_extra, aborted:true }` (+ immediate trace)
* **Precondition:** `policy=="abort"` and attempts reached 64 with all `k==0`. O(1).

---

### K-6 — `emit_ztp_final_nonconsuming(ctx, fin, lr)`

* **Purity:** Emits
* **Input:** `merchant_id`, `lineage:{seed,parameter_hash,run_id,manifest_fingerprint}`, `fin:Finaliser{K_target, attempts, regime [, exhausted?, reason?]}`, `lr.lambda_extra`
* **Output (value):** `Finaliser` (echo)
* **Emits:** `emit_ztp_final_nonconsuming(...)` → `{ merchant_id, K_target, lambda_extra, attempts, regime [, exhausted?, reason?] }` (+ immediate trace)
* **Cardinality:** **Exactly one** final per resolved merchant (absent on **abort**). O(1).

---

### K-7 — `run_ztp_for_merchant(ctx)`

* **Purity:** Emits (drives the whole attempt loop)
* **Input:** `ctx = { merchant_id, is_eligible, is_multi, N, A, X_m, θ, policy, lineage:{seed,parameter_hash,run_id,manifest_fingerprint} }`
* **Output (value):** `Finaliser` **or** `null` (abort policy)
* **Control flow:**

  1. **Preflight:** `is_eligible==true`, `is_multi==true`, `N≥2`, `A≥0`, `policy∈{"abort","downgrade_domestic"}`.
  2. If **A==0** → **K-0** (final only) → return `Finaliser`.
  3. `lr := K-1(ctx)` (freeze λ & regime).
  4. For `attempt = 1..64`:

     * `(k, s_after, bud) := K-2(lr, s_before)` *(for `attempt=1`, obtain `s_before` from the substream’s current counter)*
     * **K-3** emit attempt (consuming).
     * If `k>0`: build `fin := Finaliser{K_target=k, attempts=attempt, regime=lr.regime}` → **K-6** emit final → return `fin`.
     * Else: **K-4** emit rejection (non-consuming) and continue.
  5. **Cap-hit @ attempt 64:**

     * If `policy=="abort"`: **K-5** emit exhausted (non-consuming) → return **null** (no final).
     * Else (`"downgrade_domestic"`): `fin := {K_target=0, attempts=64, regime=lr.regime, exhausted=true}` → **K-6** emit final → return `fin`.
* **Invariants:** One event → one **immediate** trace; attempts are **1-based, strictly increasing**; regime **constant per merchant**; **never** emit both exhausted **and** final in abort path.
* **Complexity:** **O(min(attempts,64))** time; **O(1)** memory; safe to parallelise **across** merchants only.

---

### Cross-kernel relationships & guarantees

* **Only K-3/K-4/K-5/K-6** perform emissions; **K-0** is a degenerate emit (final only).
* **K-7** is the **only** entry point L2 should call for a merchant; it orchestrates everything.
* After **K-7** returns, L2 receives either a **`Finaliser` value** (normal/downgrade) or **`null`** (abort with exhausted marker).

---

## 11) K-0 — Short-Circuit $A=0$ (**emits final only**)

### Intent

Handle merchants with **no admissible foreign countries** $(A=0)$. We **do not** enter the attempt loop. We still compute $\lambda_{\text{extra}}$ and freeze the sampler **regime** (for auditability), then emit **exactly one** non-consuming **finaliser** that fixes $K_{\text{target}}=0$. No attempts, no rejections, no exhausted marker.

---

### Inputs (value-level)

`Ctx {  
  merchant_id:int64,  
  is_eligible:bool  # MUST be true (S3 gate)  
  is_multi:bool     # MUST be true (S1 gate)  
  N:int, A:int (=0),  
  X_m:float64, θ0:float64, θ1:float64, θ2:float64,  
  policy:{"abort","downgrade_domestic"},   # irrelevant on this branch  
  lineage:{seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64}  # pass-through to L0  
}`

---

### Outputs (value & event)

* **Value:** `Finaliser{ K_target=0, attempts=0, regime [, reason?] }`.
* **Event (via L0):** one `rng_event_ztp_final` with payload
  `{ merchant_id, K_target:0, lambda_extra, attempts:0, regime [, reason:"no_admissible"]? }`.
  *`reason` MUST be omitted unless the bound schema version defines it.*

---

### Math (freeze link & regime once)

$$
\lambda_{\text{extra}}=\exp(\theta_0+\theta_1\log N+\theta_2 X_m),\qquad
\text{regime}=\begin{cases}
\text{“inversion”} & \lambda_{\text{extra}}<10\\
\text{“ptrs”} & \lambda_{\text{extra}}\ge 10
\end{cases}
$$

**Guard:** if $\lambda_{\text{extra}}$ is NaN / $+\infty$ / $\le 0$, **emit nothing** for S4 and raise **`NUMERIC_INVALID`** (merchant-scoped).

---

### Pseudocode (language-agnostic)

```text
PROC short_circuit_A0(ctx):
  # Precondition: ctx.is_eligible == true, ctx.is_multi == true, ctx.A == 0

  # 1) Compute λ and regime (value-only)
  lambda_extra := exp(ctx.θ0 + ctx.θ1 * log(ctx.N) + ctx.θ2 * ctx.X_m)
  IF NOT isfinite(lambda_extra) OR lambda_extra <= 0:
      RAISE NUMERIC_INVALID(lambda_extra)          # emit nothing for S4
      RETURN null

  regime := IF lambda_extra < 10 THEN "inversion" ELSE "ptrs"

  # 2) Build finaliser value
  fin := Finaliser{ K_target: 0, attempts: 0, regime }

  # 3) Emit exactly one non-consuming final via L0 (emitter stamps envelope + immediate trace)
  emit_ztp_final_nonconsuming(
      merchant_id = ctx.merchant_id,
      lineage     = { seed:ctx.lineage.seed, parameter_hash:ctx.lineage.parameter_hash, run_id:ctx.lineage.run_id, manifest_fingerprint:ctx.lineage.manifest_fingerprint  },
      lr          = { lambda_extra:lambda_extra, regime:regime },
      K_target    = 0,
      attempts    = 0,
      exhausted?  = absent,
      reason?     = maybe("no_admissible")   # only if schema version defines it
  )

  # 4) Return the value for in-memory handoff
  RETURN fin
END
```

**Operational notes**

* The finaliser is **non-consuming**; the L0 **emitter** appends **exactly one** cumulative trace row **immediately** after the event (same writer).
* On this branch there are **no** `poisson_component` attempts, **no** `ztp_rejection`, and **no** `ztp_retry_exhausted`—ever.

---

### Envelope & schema facts (L0 responsibility; L1 must respect)

* All S4 logs are written under partitions `{seed, parameter_hash, run_id, manifest_fingerprint}` (dictionary-resolved).
* **Event envelope** (stamped by L0) embeds `run_id, seed, parameter_hash, manifest_fingerprint` + counters; **trace** rows embed `run_id & seed` and have **no `context`**. One event → one trace. *(Trace dataset has no mandated writer-sort.)*

---

### Edge cases & forbidden states

* **A=0 with any attempt / rejection / exhausted row** ⇒ producer bug—do **not** write them.
* **Policy** (`"abort"` vs `"downgrade_domestic"`) is **irrelevant** here: both take the same short-circuit (final-only).
* If preflight shows `is_eligible=false`, `is_multi=false`, `N<2`, or invalid S3 candidates, **do not** run K-0; S4 writes nothing (presence gating).

---

## 12) K-1 — Freeze $\lambda$ & Regime (**pure**)

### Intent

Compute the **ZTP link** once for the merchant and **freeze** the sampler **regime** for the entire attempt loop. K-1 is **pure** (no I/O, no RNG, no envelopes, no trace) and returns a value object consumed unchanged by downstream kernels.

> **Single source of truth.** **K-0 (A=0)** and **K-7 (main loop)** **must call K-1** to obtain `{lambda_extra, regime}`. Do **not** re-implement this formula anywhere else.

---

### Inputs (values only)

* `LambdaInputs = { N:int (≥2), X_m:float64, θ0:float64, θ1:float64, θ2:float64 }`
  (`N` from S2; `X_m` openness feature; `θ·` governed link parameters)

### Output (value)

* `LambdaRegime = { lambda_extra:float64, regime:"inversion"|"ptrs" }` (frozen per merchant)

---

### Math (binary64; no FMA)

$$
\lambda_{\text{extra}}=\exp\!\bigl(\theta_0+\theta_1\cdot\log N+\theta_2\cdot X_m\bigr)
$$

**Guard (fail-fast):** if $\lambda_{\text{extra}}$ is NaN, $+\infty$, or $\le 0$ ⇒ **raise `NUMERIC_INVALID`** (merchant-scoped) and **emit nothing** for S4.
*(Note: $\exp(\cdot) > 0$; the “$\le 0$” guard is defensive against upstream numeric faults.)*

**Regime (threshold fixed):**

$$
\text{regime} =
\begin{cases}
\text{"inversion"}, & \lambda_{\text{extra}} < 10 \\[2pt]
\text{"ptrs"}, & \lambda_{\text{extra}} \ge 10
\end{cases}
$$

The threshold $\lambda^\star=10.0$ is exact in binary64; **do not** use epsilons. Regime is **constant per merchant** (does not change in-loop).

---

### Pseudocode (language-agnostic, **pure**)

```text
PROC freeze_lambda_regime(inp: LambdaInputs) -> LambdaRegime:
  # Preconditions from preflight: IS_INT(inp.N) ∧ inp.N ≥ 2
  s := inp.θ0 + inp.θ1 * log(inp.N) + inp.θ2 * inp.X_m     # binary64, RNE, FMA off
  λ := exp(s)                                              # binary64

  IF NOT isfinite(λ) OR λ <= 0:
      RAISE NUMERIC_INVALID(lambda_extra := λ)             # merchant-scoped; S4 emits nothing

  regime := IF λ < 10.0 THEN "inversion" ELSE "ptrs"       # freeze for loop
  RETURN { lambda_extra: λ, regime: regime }
END
```

---

### Determinism & constraints K-1 must respect

* **Numeric profile:** IEEE-754 binary64, **RNE**, **FMA off**, no FTZ/DAZ; branch on the computed binary64 $\lambda_{\text{extra}}$ (no epsilon bands).
* **Purity:** same inputs ⇒ same `{lambda_extra, regime}` on any host.
* **Freeze:** downstream kernels **must not recompute or alter** $\lambda_{\text{extra}}$ or `regime`; they **read** this object and never mutate it.

---

### Edge cases (handled here)

* **Very large $N$ / large $X_m$:** if `exp(s)` overflows or becomes non-finite ⇒ **`NUMERIC_INVALID`**; callers must bypass the loop and S4 **emits nothing**.
* **Tiny/negative $X_m$:** permitted; the guard solely decides validity.
* **A=0 branch:** **K-0 must call K-1** and use the returned `{lambda_extra, regime}` when emitting `ztp_final{K_target=0}` (no duplicate math).

---

### Worked micro-examples (illustrative)

* **Example A (inversion):** `N=4`, `X_m=0.0`, `θ0=ln(9)`, `θ1=0`, `θ2=0` ⇒ $\lambda_{\text{extra}}=9$ ⇒ `regime="inversion"`.
* **Example B (PTRS):** `N=4`, `X_m=0.0`, `θ0=ln(12)` ⇒ $\lambda_{\text{extra}}=12$ ⇒ `regime="ptrs"`.

---

## 13) K-2 — Poisson Attempt Adapter (**RNG-consuming, no event I/O**)

### Intent

Perform **one Poisson attempt** for the merchant using the frozen $\lambda_{\text{extra}}$ and **regime** from K-1, **without any emission**. K-2 delegates sampling to the **capsule** that returns the **post-attempt counter** and **measured budgets**; **K-3/K-4** handle emission.

---

### Inputs (values only)

* `lr : LambdaRegime = { lambda_extra: float64, regime: "inversion"|"ptrs" }` — frozen by **K-1**.
* `s_before : Stream` — merchant-scoped substream **before** this attempt (owned by S4’s `(module, substream_label)`).

### Outputs (values only)

* `(k:int, s_before:Stream, s_after:Stream, bud:AttemptBudget)` where
  `AttemptBudget = { blocks:u64, draws_hi:u64, draws_lo:u64 }`.
  *`s_before` is echoed unchanged for emission; `bud` holds **measured** (actual-use) uniforms for this attempt.*

> K-2 **does not** decide acceptance, emit rows, append trace, or increment the attempt index. The **caller (K-7)** supplies the 1-based `attempt` index and immediately calls **K-3**/**K-4**.

---

### Math / regime consistency

* Use the frozen `lr.lambda_extra`; **do not recompute** it here.
* Enforce producer invariant:

  $$
  \texttt{compute\_poisson\_regime}(lr.\lambda_{\text{extra}}) \;=\; lr.\text{regime}
  $$

  (`"inversion"` iff $\lambda_{\text{extra}}<10$; else `"ptrs"`). On mismatch, **RAISE `POLICY_CONFLICT`("regime drift")** — **no emission**.

---

### Pseudocode (language-agnostic; **RNG-consuming, no event I/O**)

```text
PROC poisson_attempt_once(lr: LambdaRegime, s_before: Stream)
  -> (k:int, s_before:Stream, s_after:Stream, bud:AttemptBudget):

  # 0) Defensive guards (should already hold if K-1 ran)
  REQUIRE isfinite(lr.lambda_extra) AND lr.lambda_extra > 0
  REQUIRE compute_poisson_regime(lr.lambda_extra) == lr.regime

  # 1) Delegate to the sampler capsule (inversion if λ<10, else PTRS)
  #    Capsule advances the substream and measures budgets.
  (k, s_after, bud) := poisson_attempt_with_budget(
                         lambda_extra = lr.lambda_extra,
                         regime       = lr.regime,
                         s_before     = s_before)

  # 2) Return values for the caller (K-7); attempt index is supplied by K-7.
  RETURN (k, s_after, bud)
END
```

---

### How K-2 is used by the loop

**K-7** will:

1. call **K-2** to get `(k, s_after, bud)`,
2. call **K-3** to emit the **consuming attempt** with payload `{merchant_id, attempt, k, lambda}` where `lambda := lr.lambda_extra`, supplying `(s_before, s_after, bud)` for the envelope,
3. branch to **K-4** (rejection) if `k==0`, or to **K-6** (finaliser) if `k>0`.

---

### Invariants & constraints K-2 must respect

* **No emission and no trace append** here (emitters do that).
* **Attempt is 1-based** and strictly increasing, but the **index is owned by K-7**.
* **Budgets are measured, not inferred**; return `bud` exactly as produced by the capsule (emitter encodes `draws` from `draws_hi/lo` and computes `blocks = after − before`).
* **Regime is constant per merchant** (frozen in K-1); do not change it here.
* **A=0 path:** **K-0 never calls K-2** (final-only).

---

### Edge cases

* **Domain/number fault:** if `lr.lambda_extra` is non-finite or $\le 0$, **RAISE `NUMERIC_INVALID`** (merchant-scoped) and **do not** call the capsule.
* **Capsule/runtime fault:** **RAISE `RNG_SAMPLER_FAIL`** (merchant-scoped); **no** S4 events are emitted.

---

## 14) K-3 — Emit Attempt (**uses L0 emitter**)

### Intent

Take the sampled attempt from K-2 and **write the consuming attempt event** via a single **L0 emitter**. The emitter stamps the envelope and **immediately appends one** cumulative trace row (same writer). Attempt payload **must** use the key **`lambda`** (attempts-only).

---

### Inputs (values only; no paths)

* `merchant_id : int64`
* `lineage : { seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }`  *(pass-through to L0)*
* `s_before : Stream`, `s_after : Stream`  *(substream counters before/after this attempt)*
* `lr : { lambda_extra:float64>0 finite, regime }`  *(from K-1; do **not** recompute)*
* `attempt : int`  *(≥1, strictly increasing)*
* `k : int`  *(≥0; acceptance iff `k>0`)*
* `bud : AttemptBudget{ blocks:u64, draws_hi:u64, draws_lo:u64 }`  *(measured in K-2)*

---

### Output (value)

* **Unit** (or small echo such as `{attempt, k}` if the orchestrator wants it).
  *(Do not couple L1 to a concrete trace-writer return type.)*

---

### Pseudocode (language-agnostic; **one emitter call = one event → one trace**)

```text
PROC emit_poisson_attempt(merchant_id, lineage, s_before, s_after, lr, attempt, k, bud):
  # Preconditions (value-level; identities are enforced by the emitter)
  REQUIRE attempt >= 1
  REQUIRE isfinite(lr.lambda_extra) AND lr.lambda_extra > 0
  # Consuming attempt; the emitter enforces `draws > "0"` and `after > before`

  # Payload note: attempts use field name 'lambda' (schema v2)
  payload := { merchant_id: merchant_id,
               attempt: attempt,
               k: k,
               lambda: lr.lambda_extra }

  # Single emitter call: writes event, stamps envelope, appends immediate cumulative trace
  event_poisson_ztp(
      lineage = lineage,               # {seed, parameter_hash, run_id}
      s_before = s_before,
      s_after  = s_after,
      budget   = bud,                  # {blocks, draws_hi, draws_lo}
      payload  = payload               # dataset = rng_event_poisson_component
  )

  RETURN
END
```

**Why this shape**

* **L0 owns** envelope/trace: K-3 never calls writer/trace internals and never computes counter deltas; it **passes** `(s_before, s_after, bud)` and **lets L0 enforce identities** (`after>before`, `blocks=after−before`, `draws>"0"`).
* **Schema correctness:** attempt payload uses **`lambda`** (not `lambda_extra`).

---

### Schema/Dictionary facts (reference; enforced by L0)

* **Schema anchor:** `#/rng/events/poisson_component` (attempt payload).
* **Dictionary ID & partitions:** `rng_event_poisson_component` under `{seed, parameter_hash, run_id, manifest_fingerprint}`; writer-sort `(merchant_id,attempt)`.
* **Trace dataset:** `rng_trace_log` (same partitions); no mandated writer-sort.

---

### When `k == 0` (rejection path)

Immediately call **K-4** to emit **one** `ztp_rejection` (non-consuming) with the same `attempt` and `lambda_extra`; counters must be unchanged and `draws="0"` (the emitter enforces).

---

### Failure & idempotence

* **Precondition failures:**
  – numeric/domain (λ non-finite/≤0) ⇒ **RAISE `NUMERIC_INVALID`**;
  – logic/consistency (e.g., bad attempt index) ⇒ **RAISE `POLICY_CONFLICT`**.
  *(Reserve **`EMIT_FAIL`** strictly for emitter/runtime write errors.)*
* **Crash window:** if an event exists without its adjacent trace, **do not re-emit the event**; L2 calls L0 **trace-repair** once to append the missing trace.

---

## 15) K-4 — Emit Rejection Marker (**uses L0 emitter**)

### Intent

When an attempt (K-3) yields `k == 0`, write a **non-consuming** rejection marker for that **same** `attempt` index with the frozen `lambda_extra`. This proves the zero draw occurred. The emitter must **not** advance counters and must append **one immediate** cumulative trace (same writer). *(Attempts use payload key `lambda`; **rejection uses `lambda_extra`**.)*

---

### Inputs (values only; no paths)

* `merchant_id : int64`
* `lineage : { seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }` *(pass-through to L0)*
* `s_curr : Stream` — **current** substream counters (equal to the `s_after` from the just-emitted attempt)
* `lr : { lambda_extra:float64>0 finite, regime }` — from K-1 *(regime not used in payload; diagnostic only)*
* `attempt : int` — **same index** used in K-3 (≥1; strictly increasing)

---

### Output (value)

* **Unit** (or no value). *(Do not couple L1 to a specific trace-writer return type.)*

---

### Pseudocode (language-agnostic; **one emitter call = one event → one trace**)

```text
PROC emit_ztp_rejection_nonconsuming(merchant_id, lineage, s_curr, lr, attempt):
  # Preconditions (value-level; identities are enforced by the emitter)
  REQUIRE attempt >= 1
  REQUIRE isfinite(lr.lambda_extra) AND lr.lambda_extra > 0

  # Single emitter call: non-consuming event + immediate cumulative trace
  emit_ztp_rejection_nonconsuming(
      lineage  = lineage,          # {seed, parameter_hash, run_id}
      s_before = s_curr,           # non-consuming: before == after
      s_after  = s_curr,
      payload  = { merchant_id: merchant_id,
                   attempt:     attempt,
                   k:           0,
                   lambda_extra: lr.lambda_extra }  # dataset: rng_event_ztp_rejection
  )
  RETURN
END
```

**Why this shape**

* **L0 owns** envelope/trace: K-4 never calls writer/trace internals and never computes counter deltas; it **passes** `s_curr` for both `before/after` and lets L0 enforce non-consuming identities (`after==before`, `blocks=0`, `draws="0"`).
* **Schema correctness:** rejection payload uses **`lambda_extra`** (not `lambda`).

---

### Schema/Dictionary facts (reference; enforced by L0)

* **Schema anchor:** `#/rng/events/ztp_rejection` (non-consuming marker).
* **Dictionary ID & partitions:** `rng_event_ztp_rejection` under `{seed, parameter_hash, run_id, manifest_fingerprint}`; writer-sort `(merchant_id,attempt)`.
* **Trace dataset:** `rng_trace_log` (same partitions); no mandated writer-sort.

---

### Cardinality & ordering

* At most **one** rejection per `(merchant_id, attempt)`.
* Rejection (and its trace) comes **after** the attempt (and its trace) for the same `attempt`, then the loop continues (or hits cap).
* File order is non-authoritative; counters define order, but emit in natural order for clarity.

---

### Edge cases & policy interaction

* **Cap @ attempt 64:** if `k==0` on attempt 64, emit this **rejection** first (non-consuming), then:

  * `policy="abort"` ⇒ emit **`ztp_retry_exhausted{attempts:64, aborted:true}`** (non-consuming); **no final**.
  * `policy="downgrade_domestic"` ⇒ **no** exhausted marker; emit final with `K_target=0, exhausted:true`.
* **A=0 short-circuit:** K-0 path — **never** emit rejections.
* **`k>0`:** Do **not** call K-4; go straight to the finaliser (K-6).

---

### Failure & idempotence

* **Precondition failures:**
  – numeric/domain (non-finite/≤0 `lambda_extra`) ⇒ **RAISE `NUMERIC_INVALID`**;
  – logic/consistency (e.g., invalid attempt index) ⇒ **RAISE `POLICY_CONFLICT`**.
  *(Reserve **`EMIT_FAIL`** strictly for emitter/runtime write errors.)*
* **Crash window:** if a rejection exists without its adjacent trace, **do not re-emit** the event; L2 calls L0 **trace-repair** once to append the missing trace.

---

## 16) K-5 — Emit Cap-Hit Marker (**uses L0 emitter**)

### Intent

At **attempt = 64**, if there has been **no acceptance** (`k==0` on the last attempt) **and** policy = `"abort"`, publish a **non-consuming** cap-hit **exhausted marker** and **stop**. This event **must not** advance RNG counters and is followed by **one immediate** cumulative trace (same writer). **No finaliser** is written on the abort path.

---

### Preconditions (value-level)

* `attempt == 64`.
* The immediately preceding **attempt** event (K-3) was emitted with `k==0`.
* The **rejection** for `attempt=64` (K-4) **was emitted** just prior (non-consuming).
* `s_curr` equals the **after** counters of the last attempt (and of the K-4 rejection).
* `policy == "abort"`.
* `lr.lambda_extra` is **finite** and `> 0`.
* **A=0** short-circuit never reaches K-5 (K-0 final only).

---

### Inputs (values; no paths)

* `merchant_id : int64`
* `lineage : { seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }`  *(pass to L0)*
* `s_curr : Stream`  *(current counters = last attempt’s `s_after`)*
* `lr : { lambda_extra:float64>0 finite, regime }`  *(regime not used in payload; diagnostic only)*
* `policy : "abort"`

> **Cap semantics:** **Cap = 64 (spec-fixed)**. Schema v2 **pins** this on the exhausted marker payload via `attempts: 64`.

---

### Output (value)

* **Unit** (no return value). *(Do not couple L1 to a trace-writer return type.)*

---

### Pseudocode (language-agnostic; **one emitter call = one event → one trace**)

```text
PROC emit_ztp_retry_exhausted_nonconsuming(merchant_id, lineage, s_curr, lr, policy):
  # Preconditions (value-level; identities enforced by the emitter)
  REQUIRE policy == "abort"
  REQUIRE isfinite(lr.lambda_extra) AND lr.lambda_extra > 0

  # Single emitter call: non-consuming exhausted marker + immediate cumulative trace
  emit_ztp_retry_exhausted_nonconsuming(
      lineage  = lineage,         # {seed, parameter_hash, run_id}
      s_before = s_curr,          # non-consuming: before == after
      s_after  = s_curr,
      payload  = { merchant_id:  merchant_id,
                   attempts:     64,                 # schema-pinned on this marker
                   lambda_extra: lr.lambda_extra,
                   aborted:      true }              # schema-required
  )
  RETURN
END
```

---

### Schema/Dictionary facts (reference; enforced by L0)

* **Schema anchor:** `#/rng/events/ztp_retry_exhausted` (non-consuming cap-hit).
* **Dictionary ID & partitions:** `rng_event_ztp_retry_exhausted` under `{seed, parameter_hash, run_id, manifest_fingerprint}`; writer-sort `(merchant_id,attempts)` (attempts = 64).
* **Trace dataset:** `rng_trace_log` (same partitions); no mandated writer-sort.

---

### Identities K-5 must satisfy (enforced by emitter)

* **Counters:** `after == before == s_curr`.
* **Blocks:** `blocks = 0`.
* **Draws:** `draws = "0"`.
* **Trace adjacency:** **exactly one** cumulative trace appended **immediately** after the event (same writer).

---

### Cardinality & policy

* At most **one** exhausted marker per merchant, and **only** when `policy=="abort"`.
* If `policy=="downgrade_domestic"`, **do not call K-5**; call **K-6** to emit `ztp_final{K_target=0, attempts:64, exhausted:true}` (non-consuming).
* **A=0** path (K-0): **never** emits exhausted; emits `ztp_final{K_target=0, attempts:0}` only.

---

### Failure & idempotence

* **Precondition failures:**
  – numeric/domain (`lambda_extra` non-finite/≤0) ⇒ **RAISE `NUMERIC_INVALID`**;
  – logic/ordering (e.g., attempt≠64 or missing prior K-4) ⇒ **RAISE `POLICY_CONFLICT`**.
  *(Reserve **`EMIT_FAIL`** strictly for emitter/runtime write errors.)*
* **Crash window:** if an exhausted event exists without its adjacent trace, **do not re-emit** the event; L2 calls L0 **trace-repair** once to append the missing trace.

---

## 17) K-6 — Emit Finaliser (**uses L0 emitter**)

### Intent

Publish the **non-consuming finaliser** that fixes the authoritative **`K_target`** for this merchant, and let the L0 emitter stamp the envelope and **append one immediate** cumulative trace (same writer). K-6 is used on:

* **Acceptance** (`k>0` at attempt `t`) → `K_target = k`, `attempts = t`.
* **Cap-downgrade** (`policy="downgrade_domestic"`) → `K_target = 0`, `attempts = 64`, `exhausted=true`.
* **A=0 short-circuit** (from K-0) → `K_target = 0`, `attempts = 0`, optional `reason:"no_admissible"` **only if** the bound schema version defines it.

> **Never** call K-6 on **cap-abort** (`policy="abort"` at attempt 64). That path is handled by **K-5** and produces **no final**.

---

### Inputs (values only; no paths)

* `merchant_id : int64`
* `lineage : { seed:u64, parameter_hash:hex64, run_id:hex32, manifest_fingerprint:hex64 }`  *(pass-through to L0)*
* `s_curr : Stream`  *(current counters; equals the last attempt’s `s_after`; final is non-consuming)*
* `lr : { lambda_extra:float64>0 finite, regime }`  *(from K-1; do **not** recompute)*
* `fin : Finaliser{ K_target:int≥0, attempts:int≥0, regime, exhausted?:bool, reason? }`

**Preconditions (value-level):**

* `isfinite(lr.lambda_extra)` and `lr.lambda_extra > 0`.
* **Mutually exclusive outcome rules** (enforce all):

  * **Acceptance:** `fin.K_target > 0` ⇒ `fin.attempts ≥ 1` **and** `exhausted` **absent**.
  * **Cap-downgrade:** `fin.exhausted == true` ⇒ `fin.attempts == 64` **and** `fin.K_target == 0`.
  * **A=0:** `fin.attempts == 0` ⇒ `fin.K_target == 0` **and** `exhausted` **absent**.
* If at cap with `policy=="abort"`, **do not call** K-6 (K-5 handled it).

---

### Output (value)

* **`Finaliser`** (echo) or **unit**. *(L1 must not depend on a specific trace-writer return type.)*

---

### Pseudocode (language-agnostic; **one emitter call = one event → one trace**)

```text
PROC emit_ztp_final_nonconsuming(merchant_id, lineage, s_curr, lr, fin) -> Finaliser OR UNIT:
  # Preconditions (value-level; envelope identities enforced by the emitter)
  REQUIRE isfinite(lr.lambda_extra) AND lr.lambda_extra > 0
  REQUIRE fin.K_target >= 0 AND fin.attempts >= 0

  # Outcome exclusivity (guards)
  IF fin.K_target > 0:
     REQUIRE fin.attempts >= 1 AND NOT present(fin.exhausted)
  IF present(fin.exhausted) AND fin.exhausted == true:
     REQUIRE fin.attempts == 64 AND fin.K_target == 0
  IF fin.attempts == 0:
     REQUIRE fin.K_target == 0 AND NOT present(fin.exhausted)

  # Single emitter call: non-consuming final + immediate cumulative trace
  emit_ztp_final_nonconsuming(
      lineage  = lineage,         # {seed, parameter_hash, run_id}
      s_before = s_curr,          # non-consuming: before == after
      s_after  = s_curr,
      payload  = { merchant_id:  merchant_id,
                   K_target:     fin.K_target,
                   lambda_extra: lr.lambda_extra,
                   attempts:     fin.attempts,
                   regime:       lr.regime
                   [, exhausted: fin.exhausted ]       # include only if present
                   [, reason:    fin.reason ] }        # include only if schema version defines it
  )

  RETURN fin   # or UNIT, per orchestrator preference
END
```

---

### Schema / Dictionary facts (reference; enforced by L0)

* **Schema anchor:** `#/rng/events/ztp_final` (non-consuming finaliser).
* **Dictionary:** `rng_event_ztp_final` under partitions `{seed, parameter_hash, run_id, manifest_fingerprint}`; writer-sort `(merchant_id)`.
* **Trace dataset:** `rng_trace_log` (same partitions); no mandated writer-sort.

---

### Identities K-6 must satisfy (emitter-enforced)

* **Counters:** `after == before == s_curr`.
* **Blocks:** `blocks = 0`.
* **Draws:** `draws = "0"`.
* **Trace adjacency:** **exactly one** cumulative trace appended **immediately** after the event (same writer).

---

### Failure & idempotence

* **Precondition failures:**
  – numeric/domain (`lambda_extra` non-finite/≤0) ⇒ **RAISE `NUMERIC_INVALID`**;
  – outcome inconsistency (violates exclusivity rules) ⇒ **RAISE `POLICY_CONFLICT`**.
  *(Reserve **`EMIT_FAIL`** strictly for emitter/runtime write errors.)*
* **Crash window:** if a final exists without its adjacent trace, **do not re-emit** the event; L2 calls L0 **trace-repair** once to append the missing trace.

---

## 18) K-7 — Main Attempt Loop (**control logic**)

### Intent

Drive the **entire S4 realisation** for a merchant: enforce preflight (including **eligibility** and **S3 candidate-set validity**), apply the **A=0 short-circuit**, freeze $\lambda_{\text{extra}}$ & **regime**, iterate attempts up to the **spec-fixed cap (64)**, and publish the correct evidence via L0 on each branch (**attempt**, optional **rejection**, optional **exhausted**, and the **finaliser** when applicable). Every emission guarantees **one event → one immediate cumulative trace** (same writer).

---

### Inputs (values; no I/O)

`Ctx { merchant_id, is_eligible, is_multi, N, A, X_m, θ0, θ1, θ2, policy ∈ {"abort","downgrade_domestic"}, lineage:{seed,parameter_hash,run_id,manifest_fingerprint} }`

### Output (values)

`Finaliser | null`

* Returns a **`Finaliser`** value on **acceptance**, **cap-downgrade**, or **A=0**.
* Returns **`null`** on **cap-abort** (exhausted marker only; no final).

---

### Control flow (language-agnostic pseudocode)

```text
PROC run_ztp_for_merchant(ctx) -> Finaliser | null:

  # 0) Preflight (fail-fast; no S4 emissions on failure)
  REQUIRE ctx.is_eligible == true                         # S3 gate (else BYPASS S4)
  REQUIRE ctx.is_multi    == true                         # S1 gate (else BYPASS S4)
  REQUIRE IS_INT(ctx.N) AND ctx.N >= 2                    # S2 nb_final
  REQUIRE IS_INT(ctx.A) AND ctx.A >= 0
  REQUIRE ctx.policy IN {"abort","downgrade_domestic"}

  # S3 candidate-set validity (A well-defined): home@rank0 and ranks contiguous
  # Precondition (from S3/L3): candidate set valid (home@rank0; contiguous ranks)

  # 1) A=0 short-circuit (no RNG, no attempts)
  IF ctx.A == 0:
      lr := freeze_lambda_regime({N:ctx.N, X_m:ctx.X_m, θ0:ctx.θ0, θ1:ctx.θ1, θ2:ctx.θ2})
      # freeze_lambda_regime RAISEs NUMERIC_INVALID if λ non-finite/≤0
      fin := Finaliser{ K_target:0, attempts:0, regime:lr.regime
                        [, reason:"no_admissible" ] }   # include 'reason' only if schema version defines it
      emit_ztp_final_nonconsuming(
        ctx.merchant_id, ctx.lineage,
        L0.get_substream_counter(ctx.merchant_id, MODULE="1A.s4.ztp", SUBSTREAM_LABEL="poisson_component"), lr, fin)
      RETURN fin

  # 2) Freeze λ & regime once (constant across loop)
  lr := freeze_lambda_regime({N:ctx.N, X_m:ctx.X_m, θ0:ctx.θ0, θ1:ctx.θ1, θ2:ctx.θ2})

  # 3) Attempt loop (1..64, strictly increasing; cap is SPEC-FIXED 64)
  s_before := L0.get_substream_counter(ctx.merchant_id, MODULE="1A.s4.ztp", SUBSTREAM_LABEL="poisson_component")

  FOR attempt IN 1..64:
      # 3.1 Sample once (RNG-consuming, no event I/O)
      (k, s_before_echo, s_after, bud) := poisson_attempt_once(lr, s_before)
      # poisson_attempt_once RAISEs RNG_SAMPLER_FAIL on capsule/runtime error

      # 3.2 Emit consuming attempt (payload uses 'lambda' per schema v2)
      emit_poisson_attempt(ctx.merchant_id, ctx.lineage, s_before_echo, s_after, lr, attempt, k, bud)

      # 3.3 Branch on result
      IF k > 0:
          fin := Finaliser{ K_target:k, attempts:attempt, regime:lr.regime }
          emit_ztp_final_nonconsuming(ctx.merchant_id, ctx.lineage, s_after, lr, fin)
          RETURN fin

      # k == 0 → publish non-consuming rejection for the same index
      emit_ztp_rejection_nonconsuming(ctx.merchant_id, ctx.lineage, s_after, lr, attempt)

      # 3.4 Advance stream and continue
      s_before := s_after

  # 4) Cap reached with no acceptance (attempt 64 ended with k==0; K-4 already emitted for attempt=64)
  IF ctx.policy == "abort":
      emit_ztp_retry_exhausted_nonconsuming(ctx.merchant_id, ctx.lineage, s_before, lr, policy="abort")
      RETURN null                               # no finaliser on abort path
  ELSE:
      fin := Finaliser{ K_target:0, attempts:64, regime:lr.regime, exhausted:true }
      emit_ztp_final_nonconsuming(ctx.merchant_id, ctx.lineage, s_before, lr, fin)
      RETURN fin
END
```

> **Substream counters:** obtain via the **L0 helper** `get_substream_counter(...)`; do **not** read or mint counters in L1.

---

### Invariants (must hold at every emission)

* **Attempt index** is **1-based** and strictly increasing; max **64** (spec-fixed).
* **Regime** is frozen per merchant (from K-1) and **never** changes in-loop.
* **Consuming attempt (K-3)** — *emitter-enforced*: `after>before`, `blocks = after − before`, `draws > "0"`.
* **Non-consuming markers/final (K-4/K-5/K-6)** — *emitter-enforced*: `after==before`, `blocks=0`, `draws="0"`.
* **Trace adjacency** — *emitter-enforced*: after **every** event, append **exactly one** cumulative trace immediately (same writer).
* **Cardinality**: ≤1 rejection per `(merchant_id, attempt)`; ≤1 exhausted per merchant (abort-only); **exactly one** finaliser per **resolved** merchant (none on cap-abort).
* **Order authority**: S4 **never encodes cross-country order**; S3 `candidate_rank` remains sole authority.
* **Realisation happens downstream**: S6 computes $K_{\text{realized}}=\min(K_{\text{target}}, A)$; S4 does **not** cap to $A$.

---

### Failure handling (what emits, what doesn’t)

| Condition                                                                                  | Emits?                                   | Action                           |
|--------------------------------------------------------------------------------------------|------------------------------------------|----------------------------------|
| Preflight fails (ineligible, not multi, `N<2`, invalid `A`, bad policy, bad S3 ranks/home) | **No**                                   | **RAISE POLICY_CONFLICT** (gate) |
| `freeze_lambda_regime` detects non-finite/≤0 λ                                             | **No**                                   | **RAISE NUMERIC_INVALID**        |
| Sampler/capsule error in K-2                                                               | **No**                                   | **RAISE RNG_SAMPLER_FAIL**       |
| Cap-abort (64 zeros, `policy="abort"`)                                                     | **Exhausted marker only** (K-5)          | **RETURN null**                  |
| Cap-downgrade (64 zeros, `policy="downgrade_domestic"`)                                    | **Finaliser(K=0, exhausted:true)** (K-6) | **RETURN Finaliser**             |

No other outcomes are allowed. **EMIT_FAIL** is reserved strictly for emitter/runtime write errors.

---

### Idempotence & resume (operational discipline)

* If an **event** exists but its **adjacent trace** is missing (rare crash window): **do not re-emit** the event; L2 calls L0 **trace-repair** once to append the missing trace.
* If a **finaliser** exists for a merchant, the merchant is **resolved** — skip re-running the loop.
* Attempt emissions are idempotent by writer-sort and unique `(merchant_id, attempt)` keys.

---

### Performance & concurrency

* Per merchant: **O(min(attempts, 64))** time, **O(1)** memory.
* Safe parallelism **across merchants** only; within a merchant, preserve event→trace adjacency (same writer) and avoid interleaving with other labels.

---

### Notes on cap semantics (spec vs schema)

* **Cap = 64** is **spec-fixed**. The **schema v2 pins** this only on the **exhausted marker** payload (`attempts: 64`); attempt events themselves have no schema max.

---

## 19) Invariants & Acceptance (L1-level, checklist)

This section is your **go/no-go gate** for an S4·L1 implementation. Everything here must hold for every merchant processed. Organized from inputs → loop → emissions → handoff.

---

### 19.1 Preflight & gating

* [ ] **Eligibility:** `is_eligible == true` (S3). If false, **S4 emits nothing**.
* [ ] **Hurdle:** `is_multi == true` (S1).
* [ ] **Totals:** `N ≥ 2` (S2).
* [ ] **S3 candidate-set valid:** **home@rank 0** and **ranks contiguous** so that `A` is well-defined.
* [ ] **A=0 short-circuit:** run K-0 only → emit one `ztp_final{K_target=0, attempts=0 [,reason?]}`; **no** attempts/rejections/exhausted.
* [ ] **Policy:** `policy ∈ {"abort","downgrade_domestic"}`.
* [ ] If **any** gate fails (including ineligible or invalid S3 candidate set), **no S4 rows** are written (presence gating).

---

### 19.2 Numeric & regime (frozen per merchant)

* [ ] Compute $\lambda_{\text{extra}}=\exp(\theta_0+\theta_1\log N+\theta_2 X_m)$ in **binary64**, RNE, **FMA off**.
* [ ] Guard: $\lambda_{\text{extra}}$ is **finite** and **> 0**; else **no S4 emissions** (numeric invalid).
* [ ] **Regime** chosen once: `inversion` iff $\lambda_{\text{extra}}<10$, else `ptrs`; **never** changes in-loop.

---

### 19.3 Attempt loop discipline

* [ ] Attempts indexed **1-based**, **strictly increasing**, **upper bound = 64** (**spec-fixed**; schema v2 pins `attempts:64` on the **exhausted marker**).
* [ ] For each attempt $t$: exactly one **consuming** `poisson_component` event is written.
* [ ] If `k==0`, exactly one **non-consuming** `ztp_rejection` for the **same** attempt index.

---

### 19.4 Event → trace adjacency (same writer)

* [ ] After **every** event row, append **exactly one** cumulative `rng_trace_log` row **immediately by the same writer**.
* [ ] Trace rows embed `run_id` & `seed`, carry **no `context`**, and contain before/after counters & cumulative totals.

---

### 19.5 Envelope identities (emitter-enforced, per event)

* **Consuming** (`poisson_component`):
  * [ ] `after > before`, 
  * [ ] `blocks = after − before`, 
  * [ ] `draws > "0"`.
* **Non-consuming** (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`):
  * [ ] `after == before`, 
  * [ ] `blocks = 0`, 
  * [ ] `draws = "0"`.

*(L1 passes counters/budgets; **L0 emitters enforce** these identities.)*

---

### 19.6 Payload minima (names & types are normative)

* [ ] Attempt: `{merchant_id, attempt, k, lambda}` (**attempts use `lambda`**).
* [ ] Rejection: `{merchant_id, attempt, k:0, lambda_extra}`.
* [ ] Exhausted (abort-only): `{merchant_id, attempts:64, lambda_extra, aborted:true}` (**64 is const on this marker**).
* [ ] Final: `{merchant_id, K_target, lambda_extra, attempts, regime [, exhausted?, reason?]}`.
  *`reason` **must be omitted** unless the bound schema version defines it.*
  *(No lineage fields here—L0 stamps them in the envelope.)*

---

### 19.7 Cardinality (per merchant)

Let $A$ be admissible foreigns (from S3) and let the accepting attempt (if any) be $t$.

* **A=0**:
  * [ ] attempts = 0, rejections = 0, exhausted = 0, **final = 1** with `K_target=0`, `attempts=0`.
* **Accepted** (some `k>0` at $t$):
  * [ ] attempts = $t$, rejections = $t-1$, exhausted = 0, **final = 1** with `K_target = k_t`, `attempts = t`.
* **Cap-abort** (`policy="abort"`, all 64 zeros):
  * [ ] attempts = 64, rejections = 64, **exhausted = 1**, **final = 0**.
* **Cap-downgrade** (`policy="downgrade_domestic"`, all 64 zeros):
  * [ ] attempts = 64, rejections = 64, exhausted = 0, **final = 1** with `K_target=0`, `attempts=64`, `exhausted:true`.

Additionally:

* [ ] At most **one** rejection per `(merchant_id, attempt)`.
* [ ] At most **one** exhausted per merchant (abort-only).
* [ ] At most **one** final per **resolved** merchant.
* [ ] **Cap ordering:** on attempt **64** with `k==0`, **emit the rejection first**, then **exhausted** (abort) **or** **final with `exhausted:true`** (downgrade).

---

### 19.8 Partitions, lineage & ordering (reference; enforced by L0)

* [ ] All S4 logs write under partitions `{seed, parameter_hash, run_id, manifest_fingerprint}` (dictionary-resolved).
* [ ] **Event** rows’ embedded lineage equals path tokens; **trace** rows embed `run_id & seed`; `parameter_hash` is path-only.
* [ ] Writer-sort keys respected: attempts/rejections `(merchant_id,attempt)`, exhausted `(merchant_id,attempts)`, final `(merchant_id)`; trace has **no mandated** writer-sort.

---

### 19.9 Authority boundaries & downstream contract

* [ ] S4 is **logs-only**; it fixes `K_target` via `ztp_final` and **does not** encode cross-country order.
* [ ] S3 `candidate_rank` remains the **only** cross-country order.
* [ ] **Realisation happens downstream:** S6 computes $K_{\text{realized}}=\min(K_{\text{target}}, A)$. **S4 does not cap to $A$**.

---

### 19.10 Idempotence & resume

* [ ] If an event exists without its adjacent trace, **do not re-emit** the event—append the **single** missing trace via L0 repair.
* [ ] If a final exists, the merchant is resolved—**skip** re-running; no duplicate finals.
* [ ] Emissions are unique by natural keys: `(merchant_id, attempt)` for attempts/rejections; `(merchant_id)` for final; `(merchant_id, attempts)` for exhausted.

---

### 19.11 Performance & concurrency

* [ ] Per merchant: **O(min(attempts,64))** time, **O(1)** memory.
* [ ] Safe parallelism **across merchants** only; within a merchant, maintain event→trace adjacency by the same writer; do not interleave other labels between event and trace.

---

### 19.12 Quick cross-checks (easy counters to assert)

* [ ] `#trace_rows == #event_rows` (one event → one trace).
* [ ] `#rejections == #attempts − 1` on accepted path; `#rejections == #attempts` on cap paths; `#rejections == 0` on A=0.
* [ ] `final ∈ {0,1}`; `exhausted ∈ {0,1}` and **never** both present.
* [ ] For every **attempt event** row (ignoring intervening trace rows), the next event for the same merchant is either the **rejection for the same attempt**, or the **final**, or the **next attempt (attempt+1)**—no gaps, no duplicates.

---

## 20) Failure Matrix (L1 scope only)

**Scope.** These are the only failures L1 may surface while running S4. They’re expressed so an implementer can wire them straight into logging, metrics, and L2 orchestration. **L0 owns** file I/O and envelope/trace stamping (and enforces consuming/non-consuming identities). **L3 owns** validation/CI. When in doubt: **fail fast, emit nothing**; if something was already emitted, **never re-emit**, and let L2 repair a missing trace exactly once.

### 20.1 Principles

* **No partial writes from L1.** If a gate or numeric guard fails, **emit nothing** for that merchant.
* **Event→trace atomicity (operational).** Emitters append the **trace immediately** after each event (same writer). The only allowed crash window is “**event written, trace missing**”—handled by **trace-repair** (L2/L0) once.
* **Idempotence.** Natural keys must stay unique: `(merchant_id, attempt)` for attempts/rejections; `(merchant_id, attempts)` for exhausted; `(merchant_id)` for final.
* **Stop on first failure.** L1 raises a failure; L2 quarantines the merchant (no more S4 emissions this run).
* **Cap semantics.** **Cap = 64 (spec-fixed)**. Schema v2 **pins** `attempts:64` only on the **exhausted marker** payload.

---

### 20.2 Canonical failure set (L1)

| Code (L1)                   | Where detected               | Condition (examples)                                                                                                                                            | Rows that may exist                                   | L1 action              | L2 next step                                           |
|-----------------------------|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------|------------------------|--------------------------------------------------------|
| **POLICY_CONFLICT (gate)**  | Preflight (K-7 step 0)       | `is_eligible!=true`; **invalid S3 candidate set** (home≠rank0 or ranks not contiguous); `is_multi!=true`; `N<2`; `A<0`; `policy∉{"abort","downgrade_domestic"}` | **None**                                              | Raise; stop merchant   | Quarantine merchant; investigate upstream S1–S3/config |
| **NUMERIC_INVALID**         | K-0/K-1 (λ freeze)           | $\lambda_{\text{extra}}$ non-finite or $\le 0$                                                                                                                  | **None**                                              | Raise                  | Quarantine; check features/θ                           |
| **RNG_SAMPLER_FAIL**        | K-2 (capsule)                | Sampler/capsule throws; budget measurement fails                                                                                                                | **None**                                              | Raise                  | Quarantine; sampler diagnostics                        |
| **POLICY_CONFLICT (logic)** | K-5/K-6 (ordering/semantics) | At cap: `policy="abort"` but finaliser attempted; or `policy="downgrade_domestic"` but exhausted attempted; **emitter-detected identity violation**             | Possibly last **rejection** only (no final/exhausted) | Raise                  | Quarantine; fix policy wiring / logic                  |
| **EMIT_FAIL**               | K-3..K-6 (emitter call)      | I/O error while writing the **event** row (transactional failure)                                                                                               | **None** *(emitter transactional)*                    | Raise                  | Quarantine; check writer/storage                       |
| **TRACE_APPEND_FAIL**       | After successful event write | Event row fsynced; trace append failed/crashed                                                                                                                  | **Event exists; trace missing**                       | Raise                  | **Run trace-repair once**, never re-emit event         |
| **DUP_FINAL_GUARD**         | K-6                          | Attempt to emit a **second** finaliser for the merchant                                                                                                         | Existing **final** row                                | **Do not emit**; raise | Treat merchant as resolved; skip rest                  |

**Notes.**

* **Emitter-enforced identities.** L1 never calls writer/trace internals and never computes `blocks/draws`. If a consuming/non-consuming identity would be violated, the **emitter** raises a failure (no row written).
* **Partial state.** The **only** allowed partial state is **TRACE_APPEND_FAIL** (event exists; trace missing). All other failures must leave **no** new event row on disk.

---

### 20.3 Per-kernel failure semantics (what can be emitted before failure)

* **K-0 / K-1 (λ, regime):** On failure → **no emission** → `NUMERIC_INVALID`.
* **K-2 (sampler):** On capsule/runtime error → **no emission** → `RNG_SAMPLER_FAIL`.
* **K-3 (attempt):** Emits exactly one attempt event; if the trace append fails → `TRACE_APPEND_FAIL` (event exists; repair once). Identity violations are **emitter-detected** → `POLICY_CONFLICT (logic)`; **no row written**.
* **K-4 / K-5 / K-6 (non-consuming):** Same crash-window rule as K-3; identity violations are **emitter-detected** → `POLICY_CONFLICT (logic)`; **no row written**.
* **K-7 (control):** Any error from K-0..K-6 stops the merchant immediately. **No branch** may write both exhausted and final; if logic would, raise `POLICY_CONFLICT (logic)` **before** emitting.

---

### 20.4 What to log (operator breadcrumbs)

For every L1 failure, log this minimal tuple to help L2/ops triage:

```
{ code, merchant_id, is_eligible, s3_candidates_valid,
  attempt? (if in loop), A, N, policy,
  lambda_extra? (if computed), regime? (if frozen),
  last_stream_before? (hi, lo), last_stream_after? (hi, lo),
  writer: module="1A.s4.ztp", substream_label="poisson_component" }
```

* Omit fields you haven’t computed yet (e.g., `lambda_extra` on gate failures).
* Never dump raw paths; L2 resolves via the dictionary.

---

### 20.5 Retry & resume policy

* **Pure failures** (`POLICY_CONFLICT` gate, `NUMERIC_INVALID`, `RNG_SAMPLER_FAIL`): **do not retry** in the same run. Fix inputs/config and rerun the merchant in a new run.
* **I/O/trace failures** (`EMIT_FAIL`, `TRACE_APPEND_FAIL`): it is safe to **resume** the merchant in the same run **only** via L2’s idempotent rules: repair a missing trace **once**; never re-emit an already written event; if a final exists, **skip** further work (merchant is resolved).

---

## 21) Idempotence & Resume Rules

**Goal.** Make S4·L1 safe to re-run without ever duplicating rows or corrupting counters—no matter where a crash occurred. L1 stays value-only; **L2 orchestrates resume** using the rules here; **L0** provides emit/trace and **trace-repair**/**read-envelope**/**read-payload**/**substream** helpers.

---

### 21.1 What “idempotent” means here (hard guarantees)

* **Natural keys remain unique**—even on resume:

  * Attempts / Rejections: `(merchant_id, attempt)`
  * Exhausted: `(merchant_id, attempts)` (const **64**)
  * Final: `(merchant_id)`
* **One event → one cumulative trace** (same writer, immediate).
  The only legal crash window is: *event persisted, adjacent trace missing*.
* **Merchant resolution fence** (authoritative):

  * **Final exists** ⇒ merchant is **resolved** (skip re-run).
  * **Exhausted exists (abort)** ⇒ merchant is **resolved** (skip re-run).

---

### 21.2 Crash window model (what can be half-done)

Only the **trace** after a successfully written event may be missing. No other half-writes are permitted.

* **Events** are transactional: either fully written (payload + envelope) or not at all.
* **Trace** may be absent if a crash happened **after** event fsync and **before** trace append.

**Repair rule (the only repair allowed):** call **`L0.trace_repair(event_row)` once** to append the single missing trace derived from the event envelope (uses that event’s `before/after` counters and `draws`). **Never re-emit the event.**

---

### 21.3 Resume cases (what L2 must do)

| Case  | What you see on disk                                                             | What to do (idempotent action)                                                  |
|-------|----------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| **F** | A `ztp_final` exists for `(merchant_id)`                                         | **Skip** the merchant. Resolved.                                                |
| **E** | A `ztp_retry_exhausted{attempts:64}` exists for `(merchant_id)` and **no** final | **Skip** the merchant. Abort path resolved.                                     |
| **T** | An event exists **without** its adjacent trace                                   | Call **`L0.trace_repair(event_row)` once**. Do **not** re-emit the event.       |
| **P** | Partial progress (some attempts/rejections), **no** exhausted, **no** final      | **Continue safely** using Pattern A (preferred) or Pattern B (envelope-driven). |

**Pattern A — Keyed dedupe (preferred):**
For each prospective emit, **check the natural key first** (before any RNG):

* If the row **exists** → **skip** the emit and **do not sample RNG**.
  When needed for control flow, read from disk via L0 helpers:

  * `k := L0.read_attempt_payload_k(merchant_id, attempt)`
  * `s_after := L0.read_attempt_envelope_after(merchant_id, attempt)`
* If the row **does not exist** → proceed to sample (K-2) and emit (K-3/K-4/K-5/K-6).

**Pattern B — Continue from last attempt (envelope-driven):**
Let $t_{\max}$ be the largest attempt index on disk.
Set `s_before := L0.read_attempt_envelope_after(merchant_id, t_max)` (or `L0.get_substream_counter(..)` if none).
Resume at `attempt = t_max + 1`. *(Never resample for already-written attempts.)*

---

### 21.4 Pre-emit dedupe checks (L2 responsibilities)

Before **any RNG-consuming call (K-2)** or any emitter:

* `rng_event_poisson_component` → key `(merchant_id, attempt)`
* `rng_event_ztp_rejection` → key `(merchant_id, attempt)`
* `rng_event_ztp_retry_exhausted` → key `(merchant_id, attempts=64)`
* `rng_event_ztp_final` → key `(merchant_id)`

If present, **skip** the emit (treat as already done). Dedupe **must** occur **before** sampling to keep counters consistent.

---

### 21.5 Operational discipline (writer & ordering)

* **Adjacency:** keep **event → trace** adjacent by the same writer; on repair, append **only** the trace.
* **Ordering:** counters are the **authoritative total order**; writer sort
  (attempts/rejections `(merchant_id,attempt)`, exhausted `(merchant_id,attempts)`, final `(merchant_id)`) is an **audit convenience**.
* **No interleaving labels** between an event and its trace for the same writer/domain.

---

### 21.6 Pseudocode (idempotent resume loop, Pattern A)

```text
PROC run_or_resume_s4_for_merchant(ctx):

  # Resolution fences (skip if already done)
  IF exists_final(ctx.merchant_id):     RETURN RESOLVED
  IF exists_exhausted(ctx.merchant_id): RETURN RESOLVED_ABORT

  # A=0 short-circuit (final-only, keyed)
  IF ctx.A == 0:
     IF NOT exists_final(ctx.merchant_id):
        lr  := freeze_lambda_regime({N:ctx.N, X_m:ctx.X_m, θ0:ctx.θ0, θ1:ctx.θ1, θ2:ctx.θ2})
        fin := Finaliser{K_target:0, attempts:0, regime:lr.regime
                         [, reason:"no_admissible" ]}   # include reason only if schema defines it
        emit_ztp_final_nonconsuming(ctx.merchant_id, ctx.lineage,
                                    L0.get_substream_counter(ctx.merchant_id, MODULE="1A.s4.ztp", SUBSTREAM_LABEL="poisson_component"), lr, fin)
     RETURN RESOLVED

  # Freeze λ & regime once
  lr := freeze_lambda_regime({N:ctx.N, X_m:ctx.X_m, θ0:ctx.θ0, θ1:ctx.θ1, θ2:ctx.θ2})

  # Start from current substream counter
  s_before := L0.get_substream_counter(ctx.merchant_id, MODULE, SUBSTREAM_LABEL)

  FOR attempt IN 1..64:

     # --- Attempt event (dedupe BEFORE RNG) ---
     IF exists_attempt(ctx.merchant_id, attempt):
        # Do not sample; read from disk for control flow
        k        := L0.read_attempt_payload_k(ctx.merchant_id, attempt)
        s_after  := L0.read_attempt_envelope_after(ctx.merchant_id, attempt)
     ELSE:
        (k, s_before_echo, s_after, bud) := poisson_attempt_once(lr, s_before)
        emit_poisson_attempt(ctx.merchant_id, ctx.lineage,
                             s_before_echo, s_after, lr, attempt, k, bud)

     # --- Branch: accept vs reject ---
     IF k > 0 OR exists_final(ctx.merchant_id):
        IF NOT exists_final(ctx.merchant_id):
           fin := Finaliser{K_target:(k>0 ? k : L0.read_final_K(ctx.merchant_id)),
                            attempts:attempt, regime:lr.regime}
           emit_ztp_final_nonconsuming(ctx.merchant_id, ctx.lineage, s_after, lr, fin)
        RETURN RESOLVED

     # k == 0 ⇒ ensure rejection exists for this attempt (dedupe)
     IF NOT exists_rejection(ctx.merchant_id, attempt):
        emit_ztp_rejection_nonconsuming(ctx.merchant_id, ctx.lineage, s_after, lr, attempt)

     # Advance stream
     s_before := s_after

  # --- Cap reached with no acceptance ---
  IF ctx.policy == "abort":
     IF NOT exists_exhausted(ctx.merchant_id):
        emit_ztp_retry_exhausted_nonconsuming(ctx.merchant_id, ctx.lineage, s_before, lr, "abort")
     RETURN RESOLVED_ABORT
  ELSE:
     IF NOT exists_final(ctx.merchant_id):
        fin := Finaliser{K_target:0, attempts:64, regime:lr.regime, exhausted:true}
        emit_ztp_final_nonconsuming(ctx.merchant_id, ctx.lineage, s_before, lr, fin)
     RETURN RESOLVED
END
```

**Notes**

* **Pre-emit dedupe happens before any RNG** (before K-2).
* For already-written attempts, **never resample**; read `k` and `s_after` via **L0 read helpers**.
* **Cap = 64** is **spec-fixed**; schema v2 **pins** `attempts:64` only on the **exhausted marker**.

---

## 22) Performance & Run Discipline — deep pass

**Objective.** Run S4·L1 fast and safely under real load, without ever risking non-determinism or duplicate evidence. L1 is **value-only**; **all I/O & trace are in L0 emitters**; **L2** orchestrates parallelism, batching, and resume.

---

### 22.1 Throughput model (what dominates)

* **Events per merchant.** Let $T$ be the accepting attempt index (if any).

  * **Accepted at $T \ge 1$:** events $= 2T$. *(For $T\ge1$: attempts $T$ + rejections $T-1$ + one final $=2T$.)*
  * **Cap-abort (64 zeros):** $64$ attempts + $64$ rejections + **1 exhausted** $= 129$ events.
  * **Cap-downgrade:** $64$ attempts + $64$ rejections + **1 final** $= 129$ events.
  * **A=0:** **1** event (final only).
* **Expected attempts** (informative, not normative):

  $$
  \mathbb{E}[T]=\frac{1}{1-e^{-\lambda_{\text{extra}}}}\quad\text{(capped at 64).}
  $$
* **Implication.** Runtime is event I/O-bound (attempt+trace pairs), not math-bound: K-1’s $\exp$ and $\log$ run **once**; RNG per attempt is modest vs event+trace appends.

---

### 22.2 Hot-path rules (hard, practical)

1. **Freeze once.** Compute $\lambda_{\text{extra}}$ and **regime** in **K-1** and pass the object; **never** recompute in-loop.
2. **Emit then branch.** For each attempt: **emit K-3** (attempt event) → then branch to **K-4** (k==0) or **K-6** (k>0).
3. **One event → one trace (same writer, immediate).** Use the **L0 emitter** that appends the trace **immediately**; do not interleave other labels between an event and its trace.
4. **Stop at 64.** Cap is **spec-fixed 64**; halt at attempt 64 and obey policy. *(Schema v2 pins `attempts:64` only on the **exhausted marker**.)*
5. **Zero heap churn.** No per-attempt heap objects; reuse a small **scratch** struct for `(s_before, s_after, bud)` and build the payload in place.

---

### 22.3 Numeric & RNG discipline (no drift)

* **Profile:** IEEE-754 binary64, RNE, **FMA off**; strict-open $u\in(0,1)$.
* **Regime:** frozen per merchant (`inversion` if $\lambda_{\text{extra}}<10$, else `ptrs`); **do not** branch differently later.
* **Budgets are measured.** **K-2** routes the sampler through the lane and returns `bud={blocks, draws_hi, draws_lo}`; **the emitter encodes** the decimal `draws` string and asserts envelope identities. L1 **never** fabricates `draws` or computes `blocks`.

---

### 22.4 Memory & allocation hygiene

* **Keep O(1) state:** `Ctx`, `LambdaRegime`, `s_before/s_after`, `AttemptBudget`, and loop locals.
* **No envelope copies.** L0 builds and stamps envelopes; L1 passes **values** only.
* **Struct-of-scalars.** Prefer locals (e.g., `attempt:int`, `k:int`, `lambda_extra:f64`) over ad-hoc maps to avoid incidental allocations.

---

### 22.5 Parallelism & scheduling (safe and fast)

* **Across merchants:** freely parallelise; **within a merchant** the loop is **serial** to preserve counters and adjacency.
* **(L2) Shard by partition.** If you run multiple writers, shard work by `(seed, parameter_hash, run_id)` to minimise cross-shard contention.
* **Fairness:** use work-stealing or a bounded queue so near-cap merchants don’t starve.
* **Writer context:** keep a stable writer context per merchant so the **emitter** can append the trace **immediately by the same writer**.

---

### 22.6 Batching & I/O posture (L2-assisted)

* **Dictionary-resolved paths** only; partitions = `{seed, parameter_hash, run_id, manifest_fingerprint}`. *(Reference; enforced by L0.)*
* **Writer-sort keys** when batching: attempts/rejections `(merchant_id,attempt)`, exhausted `(merchant_id,attempts)`, final `(merchant_id)`. File order is non-authoritative, but following it simplifies audits/merges.
* **Micro-batches:** flush in small batches (e.g., 128–512 events) per writer **without** breaking **event↔trace pair adjacency**. Pairs must remain adjacent; batching must never reorder event/trace.

> **Cap note:** Cap is **spec-fixed 64**; schema v2 pins `attempts:64` only on the **exhausted marker**.

---

### 22.7 Sizing & backpressure (practical knobs)

* **Expected events per merchant** (accepted path): $\mathbb{E}[\text{events}]\approx 2\,\mathbb{E}[T]$. Use this to size queues and target throughput.
* **Backpressure signal:** if writer queue depth grows or **trace-lag > 0** is observed, reduce concurrency or batch size.
* **Watch cap rate.** Track the fraction of merchants hitting 64; spikes imply (a) $\lambda$ regression, (b) policy shift, or (c) upstream gating drift.

---

### 22.8 Minimal observability (perf-safe, deterministic)

* **Counters (per run):**
  `n_short_circuit_A0`, `n_accepted`, `n_cap_abort`, `n_cap_downgrade`, histogram of `attempts` (1..64), regime mix.
* **Sanity gauges:**
  `events_written == traces_written` (**must be equal**),
  `rejections == attempts − 1` (accepted) **or** `== attempts` (cap paths).
* **Trace repair count:** number of times the single missing trace was appended (should be ~0).

---

### 22.9 Micro-optimisations that actually matter

* **Precompute $\log N$** once (N ≥ 2) and store `s = θ0 + θ1·logN + θ2·X_m`; `lambda_extra = exp(s)`.
* **Early break:** immediately finalise on `k>0`; avoid any extra work on that iteration.
* **No string work in L1:** pass `bud.draws_hi/lo`; **the emitter encodes** `draws`.
* **Tight rejection path:** for `k==0`, reuse the **same** `s_after` as `s_curr` for the non-consuming marker; do not touch counters.

---

### 22.10 Concurrency-safe idempotence (quick recipe)

* **Pre-emit dedupe happens before any RNG (before K-2).** For each prospective emit, L2 checks the family’s natural key: attempts/rejections `(merchant_id,attempt)`, exhausted `(merchant_id,attempts=64)`, final `(merchant_id)`. If key exists → **skip**; else **emit** (event + immediate trace).
* **Crash-window repair:** if `event_without_trace == true`, call **`L0.trace_repair(event_row)` once**; **never re-emit** the event.

---

### 22.11 What to forbid (perf killers)

* Path literals, schema edits, or any lineage stamping in L1.
* Recomputing $\lambda$ or `regime` inside the loop (see **K-1**).
* Emitting a trace later or from a different writer than the event (use the **emitter**).
* “Helpful” retries in L1 after EMIT/TRACE failures—bubble them; let L2 handle resume once.
* Allocating per-attempt objects or building large per-merchant arrays.

---

## 23) Worked Scenarios (normative, minimal)

**How to read this.** Each scenario shows the **event payloads** (no lineage fields) L1 will cause L0 to emit, **in order**. After **every event**, the **emitter** appends **one** cumulative trace **immediately (same writer)**. Attempts use payload key **`lambda`**; all other families use **`lambda_extra`**.

> In examples below, use any real `merchant_id`; `lambda_extra`/`regime` come from K-1. Traces are always emitted right after each event—omitted here for brevity.

---

### A) A = 0 short-circuit (final-only)

**Context:** `A=0` ⇒ no attempts; compute `lambda_extra`, freeze `regime`, then finalize.

**Events (in order):**

1. `rng_event_ztp_final`
   `{ "merchant_id": 123, "K_target": 0, "lambda_extra": 9.3, "attempts": 0, "regime": "inversion", "reason": "no_admissible" }`
   *(omit `reason` if the bound schema version doesn’t support it)*

**Counts:** attempts=0, rejections=0, exhausted=0, final=1.

---

### B) Accept on first attempt (t = 1)

**Context:** `A≥1`, `lambda_extra=12.0`, `regime="ptrs"`. First draw yields `k=3`.

**Events (in order):**

1. `rng_event_poisson_component`
   `{ "merchant_id": 123, "attempt": 1, "k": 3, "lambda": 12.0 }`
2. `rng_event_ztp_final`
   `{ "merchant_id": 123, "K_target": 3, "lambda_extra": 12.0, "attempts": 1, "regime": "ptrs" }`

**Counts:** attempts=1, rejections=0, exhausted=0, final=1.

---

### C) Reject once, then accept (t = 2)

**Context:** `lambda_extra=4.5`, `regime="inversion"`. Attempt 1 → `k=0`; Attempt 2 → `k=2`.

**Events (in order):**

1. `rng_event_poisson_component`
   `{ "merchant_id": 123, "attempt": 1, "k": 0, "lambda": 4.5 }`
2. `rng_event_ztp_rejection`
   `{ "merchant_id": 123, "attempt": 1, "k": 0, "lambda_extra": 4.5 }`
3. `rng_event_poisson_component`
   `{ "merchant_id": 123, "attempt": 2, "k": 2, "lambda": 4.5 }`
4. `rng_event_ztp_final`
   `{ "merchant_id": 123, "K_target": 2, "lambda_extra": 4.5, "attempts": 2, "regime": "inversion" }`

**Counts:** attempts=2, rejections=1, exhausted=0, final=1.

---

### D) Cap-hit with **abort** policy (`policy="abort"`)

**Context:** All 64 attempts draw `k=0`. `lambda_extra=2.8`, `regime="inversion"`.

**Events (in order):**

* For `attempt = 1..64` repeat **(in this order)**:
  a) `rng_event_poisson_component`
  `{ "merchant_id": 123, "attempt": t, "k": 0, "lambda": 2.8 }`
  b) `rng_event_ztp_rejection`
  `{ "merchant_id": 123, "attempt": t, "k": 0, "lambda_extra": 2.8 }`
* Cap marker (abort-only):
  `rng_event_ztp_retry_exhausted`
  `{ "merchant_id": 123, "attempts": 64, "lambda_extra": 2.8, "aborted": true }`

**Counts:** attempts=64, rejections=64, exhausted=1, final=0.

---

### E) Cap-hit with **downgrade** policy (`policy="downgrade_domestic"`)

**Context:** All 64 attempts draw `k=0`. `lambda_extra=7.1`, `regime="ptrs"`.

**Events (in order):**

* For `attempt = 1..64` repeat **(in this order)**:
  a) `rng_event_poisson_component`
  `{ "merchant_id": 123, "attempt": t, "k": 0, "lambda": 7.1 }`
  b) `rng_event_ztp_rejection`
  `{ "merchant_id": 123, "attempt": t, "k": 0, "lambda_extra": 7.1 }`
* Finaliser (no exhausted marker on downgrade):
  `rng_event_ztp_final`
  `{ "merchant_id": 123, "K_target": 0, "lambda_extra": 7.1, "attempts": 64, "regime": "ptrs", "exhausted": true }`

**Counts:** attempts=64, rejections=64, exhausted=0, final=1.

---

### Invariants to verify in every scenario

* **Event→trace adjacency (emitter-enforced):** after **each** event above, the **emitter** appends **one** cumulative trace **immediately (same writer)**.
* **Consuming vs non-consuming (emitter-enforced):** attempts are consuming (`draws > "0"`, `after > before`); all others are non-consuming (`draws = "0"`, `after == before`).
* **Acceptance step:** on acceptance at attempt `t`, there is **no rejection** for attempt `t`; the **final** follows the attempt.
* **Key uniqueness:**
  – Attempts/Rejections: unique per `(merchant_id, attempt)`
  – Exhausted: at most one per merchant (abort-only)
  – Final: at most one per **resolved** merchant
* **Authority:** S4 never encodes cross-country order; only `K_target` is authoritative for S4.
* **Cap:** **spec-fixed 64** attempts max; schema v2 pins `attempts:64` on the **exhausted marker** (abort path). On abort, **no final**; on downgrade, **no exhausted** marker.
* **Reason field:** `reason` **must be omitted** unless the bound `ztp_final` schema version defines it.

These five scenarios cover all legal branches of S4 and give an implementer a literal checklist of the rows they must produce (and in what order) to be correct.

---