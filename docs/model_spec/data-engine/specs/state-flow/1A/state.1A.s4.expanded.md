# S4 — Foreign-country count **K (target)** via Zero-Truncated Poisson (ZTP), logs-only producer


## 0) Document contract & status

**Master spec.** This document is **normative** for S4. Any pseudocode shown here is **illustrative** only; the definitive, language-agnostic build guidance must **derive** from this spec.

**Schema authority.** For 1A, **JSON-Schema is the single schema authority**; registry/dictionary entries point only to `schemas.*.yaml` anchors (JSON Pointer fragments). Avro, if generated, is **non-authoritative** and must **not** be referenced by 1A artefacts.

**Inherited numeric/RNG law (from S0).**

* IEEE-754 **binary64**, **RNE**, **FMA-off**, **no FTZ/DAZ** for any computation that can affect decisions/order. Non-finite values are hard errors.
* PRNG is **counter-based Philox** with **open-interval** mapping `u∈(0,1)`; **draws** = actual uniforms consumed; **blocks** = counter delta. Envelopes and trace obey the budgeting/trace rules already established upstream.

**Lineage & partitions (read-side discipline).** Where S4 reads upstream RNG events (S1/S2), **path partitions must equal embedded envelope fields** `{seed, parameter_hash, run_id}` **byte-for-byte**. S4 itself **emits logs only** (no Parquet egress).

**Scope boundary (what S4 does / doesn’t).**

* **Does:** compute `λ_extra`, sample ZTP for a foreign-count **target `K_target`**, and emit **RNG events only** (including a **non-consuming finaliser** that fixes `K_target`).
* **Does not:** choose countries (S6), allocate counts (S7), sequence/IDs or write `outlet_catalogue` (S8), or produce validation bundles (S9). Authority for inter-country order remains in S3’s `candidate_set`/`candidate_rank`.

**Branch purity (gates owned upstream).** S4 runs **only** for merchants with **S1 `is_multi=true`** and **S3 `is_eligible=true`**; singles and ineligible merchants produce **no S4 events**.

---

## 0A) One-page quick map (for implementers)

> A single-screen view of **what runs**, **what’s read/written**, and **where S4 hands off**. All MUST/SHOULD rules are defined in §§0–2A and later sections; this is the wiring diagram you keep beside the code.

### Flow (gates → ZTP loop → outcomes)

```
S1 hurdle      S3 eligibility        S3 admissible set size A
is_multi? ──►  is_eligible? ──►  compute A := size(S3.candidate_set \ {home})
   │ no             │ no                     │
   └──────────► BYPASS S4 (domestic only) ◄──┘

            yes             yes
                 ▼
           [Parameterise]
  η = θ0 + θ1·log N + θ2·X (binary64, fixed order)
  λ = exp(η) ; if non-finite/≤0 → NUMERIC_INVALID (abort S4 for m)

                 ▼
       A == 0 ? ────────────── yes ──►  emit ztp_final{K_target=0[, reason:"no_admissible"]?} (non-consuming)
           │ no
           ▼
     ZTP attempt loop (attempt = 1..)
       draw K ~ Poisson(λ)  →  emit poisson_component{attempt, k} (consuming)
             │
             ├─ K == 0 → emit ztp_rejection{attempt} (non-consuming) → next attempt
             │
             ├─ K ≥ 1 → ACCEPT:
             │          emit ztp_final{K_target=K, attempts=attempt, exhausted=false} (non-consuming)
             │          STOP
             │
             └─ attempts == MAX_ZTP_ZERO_ATTEMPTS ?
                    │ yes → policy:
                    │        • "abort"  → emit ztp_retry_exhausted{attempts, aborted:true} (non-consuming); ZTP_EXHAUSTED_ABORT (no final)
                    │        • "downgrade_domestic" → emit ztp_final{K_target=0, exhausted:true} (non-consuming)
                    └ no  → next attempt
```

**After each event append:** append exactly **one** cumulative `rng_trace_log` row (saturating totals).

---

### Quick I/O (what S4 reads and writes)

**Reads (values / streams):**

* **S1 hurdle** (gate): `is_multi=true` ⇒ in scope.
* **S2 `nb_final`** (fact): authoritative **`N ≥ 2`** (non-consuming).
* **S3 eligibility** (gate) and **A** definition: **`A := size(S3.candidate_set \ {home})`**.
* **Hyper-parameters** `θ`, **cap** `MAX_ZTP_ZERO_ATTEMPTS` (governed), **policy** `ztp_exhaustion_policy`.
* **Features** `X ∈ [0,1]` (default **0.0** if missing).

**Writes (logs only; partitions from dictionary = `{seed, parameter_hash, run_id}`):**

* `rng_event_poisson_component` (context=`"ztp"`) — **consuming** attempts (`attempt` is **1-based**).
* `rng_event_ztp_rejection` — **non-consuming** zero markers.
* `rng_event_ztp_retry_exhausted` — **non-consuming** cap marker.
* `rng_event_ztp_final` — **non-consuming** finaliser fixing `{K_target, lambda_extra, attempts, regime, exhausted?}`.
* `rng_trace_log` — **one row per event append** (cumulative, saturating).

---

### Hard literals & regimes (so no one guesses)

* **module:** `1A.ztp_sampler`
* **substream_label:** `poisson_component`
* **context:** `"ztp"`
* **Poisson regimes:** **Inversion** if `λ < 10`, **PTRS** if `λ ≥ 10` (spec-fixed threshold/constants).
* **Budget law:** `draws` = uniforms consumed; `blocks` = `after − before`.
* **File order is non-authoritative** — pairing/replay by **counters** only.

---

### Handoff (what downstream consumes)

* S4 exports **`K_target`** (or `K_target=0` via `A=0` short-circuit or policy **downgrade**).
* **S6 MUST realise** `K_realized = min(K_target, A)` (select up to `K_realized` foreigns); S6 owns selection/weights.
* S4 **never** encodes inter-country order (still only in S3 `candidate_rank`).

---

## 1) Purpose, scope & non-goals

### Purpose (what S4 is).
For each merchant `m` on the eligible multi-site branch, compute a deterministic **log-link**

$$
\eta_m=\theta_0+\theta_1\log N_m+\theta_2 X_m+\cdots\quad\text{(binary64, fixed order)}
$$
**Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.

and set $\lambda_{\text{extra},m}=\exp(\eta_m)>0$; then **sample ZTP** by drawing from Poisson$(\lambda)$ and **rejecting zeros** until acceptance or a governed **zero-draw cap** is hit. Record the attempt stream(s), zero-rejection markers, and a **non-consuming finaliser** that fixes **`K_target`** and run facts. S4 writes **no Parquet egress**—only RNG event logs under dictionary partitions `{seed, parameter_hash, run_id}`.
**By definition ZTP yields `K ≥ 1`; `K_target = 0` occurs only via (a) the `A=0` short-circuit or (b) the exhaustion policy = `"downgrade_domestic"` (never from ZTP itself).**

### Scope (what S4 owns).

* **Parameterisation:** evaluate $\eta$ and $\lambda$ in **binary64** with fixed operation order; **abort** the merchant if $\lambda$ is non-finite or ≤ 0. (If the features view lacks `X_m`, use **`X_m := 0.0`**.)
* **RNG protocol:** use keyed Philox substreams; **open-interval** $u\in(0,1)$; per-event envelopes obey **draws vs blocks** identities. **After each S4 event append, the producer MUST append exactly one cumulative `rng_trace_log` row** (saturating totals) for the S4 module/substream.
* **Events produced (logs-only):**

  1. one or more `poisson_component` attempts with `context:"ztp"` (**consuming**; attempts are **1-based**: `attempt = 1,2,…`),
  2. `ztp_rejection` markers for zeros (**non-consuming**),
  3. optional `ztp_retry_exhausted` on cap (**non-consuming**),
  4. **exactly one** `ztp_final` (**non-consuming**) that **fixes** `{K_target, lambda_extra, attempts, regime, exhausted?}`.

### Non-goals (what S4 must not do).

* **No re-sampling or alteration of `N`.** Authoritative **`N`** is fixed by S2’s non-consuming `nb_final`; S4 only **reads** it.
* **No country choice or order.** S4 **does not** select which countries—S6 does; order authority remains S3’s `candidate_rank (home=0; contiguous)`.
* **No integerisation or sequencing.** Counts allocation (S7) and within-country sequence/IDs (S8) are out of scope here.
* **No egress or consumer gates.** `outlet_catalogue` and the 1A→1B gate live in S9.
* **No path literals.** All locations are dictionary-resolved; events must be written under `{seed, parameter_hash, run_id}` with **path↔embed equality** for those keys.

### Branch & universe awareness (clarifying notes).

* **Definition of the admissible foreign universe.** Let **`A := size(S3.candidate_set \ {home})`**.
* **Eligibility short-circuit (`A=0`).** If **A=0** for a merchant, S4 **MUST NOT** sample and must resolve the merchant with a **finaliser carrying `K_target=0`** and, if the schema includes this optional field, `reason:"no_admissible"` (domestic-only downstream).
* **Cap governance.** The zero-draw cap **`MAX_ZTP_ZERO_ATTEMPTS`** is a **governed value** (default **64**) that **participates in `parameter_hash`**; the **exhaustion policy** `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` is also governed and participates in `parameter_hash`.

### Hand-off contract (forward-looking pointer).
S4 **exports** an accepted **`K_target`** (or a deterministic `K_target=0` under short-circuit/policy). **S6 must realise**

$$
K_{\text{realized}}=\min\big(K_{\text{target}},\,A\big),
$$

and may log a shortfall marker in its own state; S4 does **not** encode inter-country order at any point (that remains in S3).

---

## 2) Authorities & schema anchors

### Single schema authority.
For 1A, **JSON-Schema is the only schema authority**. Every dataset/stream S4 references **must** be a `schema_ref` JSON Pointer into `schemas.*.yaml`. Avro (`.avsc`) may be generated but is **non-authoritative** and **must not** be referenced by the registry/dictionary.

### What S4 writes (logs only): authoritative event anchors.

* `schemas.layer1.yaml#/rng/events/poisson_component` — **consuming** attempt rows with `context="ztp"`; payload includes `k`, `attempt`. Budgets are measured via the envelope (`draws` vs `blocks`).
* `schemas.layer1.yaml#/rng/events/ztp_rejection` — **non-consuming** zero-draw marker (`k=0`, `attempt`).
* `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` — **non-consuming** cap-hit marker (`attempts=…`).
* `schemas.layer1.yaml#/rng/events/ztp_final` — **non-consuming** finaliser fixing `{K_target, lambda_extra, attempts, regime, exhausted?}` for the merchant (mirrors S2’s non-consuming finaliser pattern).
* `schemas.layer1.yaml#/rng/core/rng_trace_log` — **trace stream** with cumulative totals per `(module, substream_label)`; append **exactly one** row after each S4 event (saturating).

### What S4 reads / gates it respects.

* **S1 hurdle events** (presence gate for multi-site RNG): partitioned by `{seed, parameter_hash, run_id}`. S4 emits **no** events for `is_multi = false`.
* **S2 `nb_final`** (exactly one, **non-consuming**): fixes **`N`**; S4 **must not** re-sample or alter **N**.
* **S3 eligibility & admissible set size.** S4 requires `is_eligible = true`. Let **`A := size(S3.candidate_set \ {home})`**; S4 uses **A** only for the **A=0** short-circuit (no sampling). S4 does **not** use S3 inter-country order here.

### Authority boundaries (reaffirmed).

* Inter-country **order authority** remains **only** in **S3 `candidate_set.candidate_rank`** (home=0; contiguous). S4 **never** encodes cross-country order; it only logs the ZTP outcome.

### Dictionary vs Schema roles.

* **JSON-Schema** defines **row shape/keys** and payload/envelope fields.
* The **Data Dictionary** defines **dataset IDs**, **partitions** (RNG logs: `{seed, parameter_hash, run_id}`), and **writer sort keys**; path resolution and lifecycle live there.

### File order is non-authoritative.
Pairing and replay are determined **only by counters** in the RNG envelopes (hi/lo counters and deltas), not by physical file order or timestamps.

---

## 2A) Label / stream registry (frozen identifiers)

> These literals fix **module / substream / context** so replay and budgeting are stable across releases. Changing any is a **breaking change**.

| Stream                          | **module**       | **substream_label** | **context** |
|---------------------------------|------------------|---------------------|-------------|
| `rng_event_poisson_component`   | `1A.ztp_sampler` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_rejection`       | `1A.ztp_sampler` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_retry_exhausted` | `1A.ztp_sampler` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_final`           | `1A.ztp_sampler` | `poisson_component` | `"ztp"`     |

**Note.** All S4 events share `substream_label="poisson_component"` to aggregate budgets/trace under one domain; event type is distinguished by the table/anchor and `context:"ztp"`.

**Budgeting, envelopes & trace (MUST).**

* `poisson_component(context="ztp")` is **consuming**; envelopes must satisfy **`blocks == after − before`** and **`draws > 0`**.
* `ztp_rejection`, `ztp_retry_exhausted`, and `ztp_final` are **non-consuming**: **`before == after`**, **`blocks = 0`**, **`draws = "0"`**.
* **After each S4 event append, the producer MUST append exactly one cumulative `rng_trace_log` row** (saturating totals) for this `(module, substream_label)`.

**Dictionary partitions (read/write discipline).** All S4 streams are **logs** partitioned by **`{seed, parameter_hash, run_id}`**. When reading S1/S2 or writing S4, **path keys must equal embedded envelope fields** for those partitions **byte-for-byte**.

**Reminder (non-authority of file order).** Do not rely on writer order; validators and replayers must use **envelope counters** to sequence and pair events.

---

## 2B) Bill of Materials (BOM)

> Single place that enumerates every **governed artefact**, **value view**, and **authority** S4 depends on; what each item is for, whether it **participates in `parameter_hash`**, and how it is scoped. **Values, not paths.** Physical resolution always comes from the **Data Dictionary**.

### 2B.1 Governed artefacts (participate in `parameter_hash`) — **N**

| Name                      | Role in S4                                    | Kind                               | Scope | Fields / Contents (relevant to S4)                                                                       | Owner    | Versioning / Digest  | Participates in `parameter_hash` | Default / Notes                     |
|---------------------------|-----------------------------------------------|------------------------------------|-------|----------------------------------------------------------------------------------------------------------|----------|----------------------|----------------------------------|-------------------------------------|
| `crossborder_hyperparams` | Parameterises ZTP link & exhaustion behaviour | Artefact (governed values)         | value | `θ = {θ₀, θ₁, θ₂, …}`; `MAX_ZTP_ZERO_ATTEMPTS`; `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` | Governed | semver + byte digest | **Yes**                          | Cap default **64** unless specified |
| `crossborder_features`    | Optional merchant feature(s) for η            | Artefact / View (parameter-scoped) | value | `X_m ∈ [0,1]` (and any documented transforms)                                                            | Governed | semver + byte digest | **Yes**                          | If `X_m` missing, **use 0.0**       |

### 2B.2 Authorities (schema & dictionary) — **N**

| Name                                                                                                                                                                                                                         | Role                                                                             | Kind                    | Scope     | Source of truth       | Participates in `parameter_hash` | Notes                                                            |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|-------------------------|-----------|-----------------------|----------------------------------|------------------------------------------------------------------|
| RNG event schemas (`schemas.layer1.yaml#/rng/events/poisson_component`, `schemas.layer1.yaml#/rng/events/ztp_rejection`, `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`, `schemas.layer1.yaml#/rng/events/ztp_final`) | Define row/envelope shapes for all S4 logs                                       | **JSON-Schema anchors** | authority | `schemas.layer1.yaml` | No                               | Serialization authority only (row shape/keys)                    |
| Data Dictionary entries (S4 logs)                                                                                                                                                                                            | Define dataset IDs, **partitions** `{seed, parameter_hash, run_id}`, writer sort | Dictionary              | authority | Data Dictionary       | No                               | Paths, partitions, writer sort; **file order non-authoritative** |

### 2B.3 Upstream runtime surfaces S4 must read (gates & facts) — **N**

| Name                               | Role in S4                             | Kind                     | Partitions / Scope               | Source of truth | Notes                                                                                         |
|------------------------------------|----------------------------------------|--------------------------|----------------------------------|-----------------|-----------------------------------------------------------------------------------------------|
| S1 hurdle events                   | **Gate**: `is_multi = true` ⇒ in scope | RNG log                  | `{seed, parameter_hash, run_id}` | S1 producer     | Enforce path↔embed equality on read                                                           |
| S2 `nb_final`                      | **Fixes** `N ≥ 2` (non-consuming)      | RNG log                  | `{seed, parameter_hash, run_id}` | S2 producer     | Exactly one non-consuming finaliser per merchant                                              |
| S3 `crossborder_eligibility_flags` | **Gate**: `is_eligible = true`         | Parameter-scoped dataset | `parameter_hash`                 | S3 producer     | Deterministic; no RNG                                                                         |
| S3 `candidate_set`                 | Defines admissible universe size **A** | Parameter-scoped dataset | `parameter_hash`                 | S3 producer     | **A := size(S3.candidate_set \ {home})** (foreigns only). S4 uses **A** only for the `A=0` check |

### 2B.4 Hard literals & spec constants (breaking if changed) — **N**

| Literal / Constant                                   | Role                      | Kind          | Participates in `parameter_hash` | Notes                                                           |
|------------------------------------------------------|---------------------------|---------------|----------------------------------|-----------------------------------------------------------------|
| `module = "1A.ztp_sampler"`                               | Envelope identity         | Spec literal  | No                               | Frozen identifier for replay/tooling                            |
| `substream_label = "poisson_component"`              | Envelope identity         | Spec literal  | No                               | Family reuse; disambiguated by `context="ztp"`                  |
| `context = "ztp"`                                    | Envelope identity         | Spec literal  | No                               | Tags S4 attempts/markers/final                                  |
| Poisson regime threshold **λ★ = 10**                 | Selects Inversion vs PTRS | Spec constant | No                               | Regime constants/threshold are spec-fixed (breaking if changed) |
| Numeric profile (binary64, RNE, FMA-off, no FTZ/DAZ) | Deterministic math        | Spec constant | No                               | Inherited from S0; breaking if changed                          |
| Open-interval mapping `u ∈ (0,1)`                    | RNG mapping               | Spec constant | No                               | Inherited from S0                                               |

### 2B.5 Trace & observability (values, not paths) — **N**

| Name                  | Role                                                                  | Kind             | Scope                            | Participates in `parameter_hash` | Notes                                                                                                                          |
|-----------------------|-----------------------------------------------------------------------|------------------|----------------------------------|----------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| `rng_trace_log`       | **Cumulative** budget/coverage totals per `(module, substream_label)` | RNG trace stream | `{seed, parameter_hash, run_id}` | No                               | **MUST append exactly one row after every S4 event append** (saturating)                                                       |
| Run counters (`s4.*`) | Ops/telemetry                                                         | Values           | per-run                          | No                               | e.g., `s4.merchants_in_scope`, `s4.accepted`, `s4.rejections`, `s4.retry_exhausted`, `s4.policy.*`, `s4.ms.*`, `s4.trace.rows` |

**Definition.** "Saturating totals" = cumulative counters that never decrease per `(module, substream_label)`; validators reconcile these against event budgets.

**BOM discipline (MUST).**

1. Items listed as **governed artefacts** **must** be passed to S4 as **values** and **participate in `parameter_hash`** (reproducibility).
2. **Authorities** (schemas/dictionary) define shapes and partitions/sort; **do not** put physical paths in S4.
3. **Upstream surfaces** are read-only; S4 enforces path↔embed equality on read.
4. **Spec literals/constants** are frozen; changing them is **breaking** and requires a spec revision.

---

## 3) Host inputs (values, not paths)

**What these are.** Run-constant **values** S4 receives from the orchestrator to bind lineage, parameterisation, and policy. They are **not** filesystem paths; all physical locations are resolved via the **Data Dictionary**.

### 3.1 Lineage surfaces (read-only values)

* `seed : u64`
* `parameter_hash : hex64`
* `run_id : str`
* `manifest_fingerprint : hex64`

**MUST.** S4 **must not** mutate these; when S4 writes logs, any lineage fields required by the stream schema **must** byte-match the path tokens.

### 3.2 Hyper-parameters & features (governed values)

* **ZTP link parameters** `θ = (θ₀, θ₁, θ₂, …)` — real-valued; **governed**.
  **MUST.** The bytes of `θ` **participate in `parameter_hash`**.
  **Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.
* **Merchant feature** `X_m ∈ [0,1]` (e.g., "openness") — governed mapping & provenance (document monotone transform, cohort, scaling).
  **Default.** If `X_m` is missing, **MUST use `X_m := 0.0`**. A different default MAY be supplied by governance and **MUST** participate in `parameter_hash`.
  **Precedence.** If governance provides `X_default`, it **overrides** 0.0; otherwise **use 0.0**.
* **Exhaustion cap** `MAX_ZTP_ZERO_ATTEMPTS ∈ ℕ⁺` — **governed** (default **64**); **participates** in `parameter_hash`.
* **Exhaustion policy** `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` — **governed**; **participates** in `parameter_hash`.

### 3.3 Prohibitions (MUST NOT)

* No literal storage paths in S4 text or implementations.
* No dynamic/environment-dependent sources for `θ`, the `X` transform/default, the cap, or the policy; they **must** be governed values bound into the run’s `parameter_hash`.

---

## 4) Required upstream datasets & gates

### 4.1 Gates S4 must respect (branch purity)

* **S1 hurdle (presence gate).** S4 runs for a merchant **iff** `is_multi = true`. Singles produce **no** S4 events.
* **S3 eligibility.** Merchant must be **cross-border eligible**; if ineligible, S4 **must** emit nothing.

### 4.2 Authoritative fact S4 must read (never alter)

* **S2 `nb_final`.** The accepted **`N_m ≥ 2`** (exactly one **non-consuming** finaliser per merchant). S4 **must not** re-sample or alter `N_m`.

### 4.3 Admissible-set size (context only)

* Define **`A_m := size(S3.candidate_set \ {home})`** (foreign countries only).
  **Use in S4.** Only for the **A=0** short-circuit; S4 does **not** use S3’s order here.

### 4.4 Partitions when reading

* S1/S2 logs are read under **`{seed, parameter_hash, run_id}`**; **path↔embed equality** must hold for these keys (byte-for-byte).
* S3 tables are read under **`parameter_hash={…}`** (parameter-scoped).
* **File order is non-authoritative;** pairing/replay **must** use **envelope counters** only.

### 4.5 Zero-row discipline

* Dataset **presence** implies ≥1 row for the run’s partition. **Zero-row artefacts are forbidden**; treat as producer error upstream.

---

## 5) Symbols & domains

### 5.1 Upstream facts & context

* `N_m ∈ {2,3,…}` — accepted multi-site total from S2 (**authoritative**).
* `A_m ∈ {0,1,2,…}` — size of S3’s admissible foreign set (foreigns only).

### 5.2 Link and intensity

$$
\eta_m = \theta_0 + \theta_1 \log N_m + \theta_2 X_m + \cdots
$$

Compute in **binary64** with **fixed operation order**.

$$
\lambda_{\text{extra},m} = \exp(\eta_m) > 0
$$

**MUST.** Abort the merchant in S4 (`NUMERIC_INVALID`) if $\lambda$ is non-finite or ≤ 0.
**Default for features.** If `X_m` absent, **use `X_m := 0.0`** (deterministic).

### 5.3 Draw outcomes (targets vs realisation)

* `K_target,m ∈ {0,1,2,…}` — result recorded by S4:
  **ZTP yields `K≥1`;** `K_target=0` appears only from **A=0 short-circuit** or policy **"downgrade_domestic"** (never from ZTP itself).
* `K_realized,m = min(K_target, A_m)` — applied later by **S6** (top-K selection).

### 5.4 Attempting & regimes

* `attempt ∈ {1,2,…}` — **1-based** index of Poisson attempts for the merchant.
* `regime ∈ {"inversion","ptrs"}` — closed enum indicating the Poisson sampler branch chosen by the fixed λ-threshold.

### 5.5 PRNG & envelopes

* Uniforms `u ∈ (0,1)` (strict-open) per S0 law.
* **Envelope identities:**

  * **Consuming attempts:** `draws` = actual uniforms consumed; `blocks` = `after − before`.
  * **Markers/final:** `before == after`, `blocks = 0`, `draws = "0"`.
* **Trace duty.** The **trace-after-every-event** obligation from §2A applies: after each S4 event append, append exactly one cumulative `rng_trace_log` row (saturating totals) for the S4 module/substream.

### 5.6 Caps & policies

* `MAX_ZTP_ZERO_ATTEMPTS ∈ ℕ⁺` — governed; default **64**.
* `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` — governed.

### 5.7 Determinism requirement (MUST)

* For fixed inputs and lineage, the Poisson attempt sequence and resolved `K_target` are **bit-replayable** under the keyed substream and frozen literals; **counters provide the total order** (timestamps are observational only).

---

## 6) Outputs (streams) & partitions

### What S4 writes.
S4 is a **logs-only** producer. It emits **RNG event rows** (serialization per JSON-Schema). **No 1A egress tables.** 
Every S4 stream is partitioned by **`{ seed, parameter_hash, run_id }`**. Every S4 **event** row carries a full **RNG envelope**; trace rows carry only `ts_utc, module, substream_label` and cumulative counters per **§14.1**.

### Streams (authoritative event anchors).

1. **`poisson_component`** (with `context:"ztp"`) — **consuming** attempt rows.
   **Payload (minimum):** `{ merchant_id, attempt:int≥1, k:int≥0, lambda_extra:float64, regime:"inversion"|"ptrs" }`
   **Domain:** `merchant_id` is **int64** per ingress `merchant_ids` (see `schemas.ingress.layer1.yaml#/merchant_ids`).
   **Envelope (minimum):** `{ ts_utc, module, substream_label, context, before, after, blocks, draws }`.
2. **`ztp_rejection`** — **non-consuming** marker for a **zero** draw.
   **Payload:** `{ merchant_id, attempt, k:0, lambda_extra }` + non-consuming envelope.
3. **`ztp_retry_exhausted`** — **non-consuming** marker when the zero-draw **cap** is hit **and policy="abort"**.
   **Payload:** `{ merchant_id, attempts:int, lambda_extra, aborted:true }` + non-consuming envelope.
4. **`ztp_final`** — **non-consuming** **finaliser** that **fixes** the outcome for the merchant.
   **Payload:** `{ merchant_id, K_target:int, lambda_extra, attempts:int, regime, exhausted?:bool [ , reason:"no_admissible"]? }` + non-consuming envelope.

### Partitioning & path↔embed equality (MUST).

* All four streams are written under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.
* The envelope’s `{ seed, parameter_hash, run_id }` **must equal** the path tokens **byte-for-byte**. A mismatch is a structural failure.

### Row ordering (writer-sort) (MUST).

* `poisson_component`, `ztp_rejection`: sort by **`(merchant_id, attempt)`** (stable).
* `ztp_retry_exhausted`: **`(merchant_id, attempts)`** (single row per merchant if present).
* `ztp_final`: **`(merchant_id)`** (exactly one per **resolved** merchant; absent only under hard abort).

### Cardinality & presence rules (MUST).

* **Exactly one** `ztp_final` per **resolved** merchant.
* Acceptance ⇒ **≥1** `poisson_component(context:"ztp")` exists; the **last** such row has `k≥1`.
* Cap path ⇒ `ztp_retry_exhausted` exists; if policy is `"downgrade_domestic"`, a `ztp_final{K_target=0, exhausted:true}` **must** exist; if policy is `"abort"`, **no** `ztp_final` is written.

### Zero-row discipline & idempotence (MUST).

* **Zero-row files are forbidden.** If no rows are produced for a slice, write nothing.
* Re-runs with identical inputs produce byte-identical content; if the partition already exists and is complete, the writer **must** no-op ("skip-if-final").

### Non-authority of file order (MUST).
**File order is non-authoritative;** pairing/replay **MUST** use **envelope counters** (hi/lo and deltas) only.

### Trace duty (pointer).
After each S4 event append, append exactly **one** cumulative `rng_trace_log` row—see **§7 Trace duty**.

---

## 7) Determinism & RNG protocol

**Substream keying & identifiers (MUST).**

* Use the **frozen literals** from §2A for `module`, `substream_label`, `context:"ztp"`.
* Each merchant’s attempt loop uses a **merchant-keyed** substream; **attempt** is **1-based** and strictly increasing.

**Open-interval uniforms & budgets (MUST).**

* Map counters to uniforms on the **open interval** `u∈(0,1)`.
* **Budget identities:**

  * `poisson_component(context:"ztp")` rows are **consuming**: `blocks == after − before`, and `draws > 0`.
  * `ztp_rejection`, `ztp_retry_exhausted`, `ztp_final` are **non-consuming**: `before == after`, `blocks == 0`, `draws == "0"`.

**Poisson regimes (fixed & measurable) (MUST).**

* **Inversion** for `λ < 10` — consumes exactly `K + 1` uniforms for `K`.
* **PTRS** for `λ ≥ 10` — consumes a **variable** count per attempt (≥2). Threshold/constants are spec-fixed.
* **Budgets are measured, not inferred**: validators rely on the envelope.

**Replay & ordering (MUST).**

* **Monotone, non-overlapping** counters per merchant/substream provide a total order; **timestamps are observational only**.
* Replaying attempts must reconstruct the same sequence and acceptance (bit-replay under the fixed literals).

**Concurrency discipline (MUST).**

* Parallelize **across** merchants only; a single merchant’s attempt loop is **serial** with fixed iteration order.
* Any merge/sink stages must be **deterministic and stable** with respect to the writer-sort keys in §6.

**Trace duty (MUST).**

* **After each S4 event append, append exactly one cumulative `rng_trace_log` record** (saturating totals) for **`(module, substream_label)`**.
* **Responsibility:** the writer that commits the event row **MUST** immediately append the single cumulative `rng_trace_log` row; higher-level sinks **MUST NOT** emit additional trace rows.

---

## 8) Parameterisation & target distribution

### Link & intensity (MUST).

* Compute

  $$
  \eta_m = \theta_0 + \theta_1 \log N_m + \theta_2 X_m + \cdots
  $$

  in **binary64** with a **fixed operation order**.
* Set $\lambda_{\text{extra},m} = \exp(\eta_m)$. If $\lambda$ is **NaN/Inf/≤0**, fail the merchant in S4 with `NUMERIC_INVALID`.

**Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.

### Target distribution (ZTP) (MUST).

* Let $Y \sim \text{Poisson}(\lambda_{\text{extra}})$. Define the **ZTP target**

  $$
  K_{\text{target}} = Y \,\big|\, (Y \ge 1).
  $$

  Acceptance probability is $1 - e^{-\lambda_{\text{extra}}}$ (for ops observability; not a decision gate).

### Realisation method (MUST).

* Realise ZTP by **sampling Poisson** and **rejecting zeros** until acceptance or the governed **zero-draw cap** is hit.
* On acceptance at attempt `a`: write the consuming `poisson_component` for that attempt and then write a **non-consuming `ztp_final`** echoing `{K_target, lambda_extra, attempts=a, regime, exhausted:false}`.
* On cap: follow the governed **exhaustion policy**:
  * `"abort"` ⇒ write `ztp_retry_exhausted{attempts, aborted:true}` and **no** `ztp_final` (merchant leaves S4 with `ZTP_EXHAUSTED_ABORT`).
  * `"downgrade_domestic"` ⇒ **do not** write `ztp_retry_exhausted`; write `ztp_final{K_target=0, exhausted:true}` (domestic-only downstream).

### Universe-aware short-circuit (MUST).

* If the **admissible foreign set is empty** (`A=0` from S3), **do not sample**; immediately write `ztp_final{K_target=0[, reason:"no_admissible"]?}` (non-consuming).

### Separation of concerns (MUST).

* S4 **fixes** the **target** count **`K_target`** only.
* In S6, the realised selection size is

  $$
  K_{\text{realized}}=\min\big(K_{\text{target}},\,A\big),
  $$

  and S6 may log a shortfall marker in its own state. S4 never encodes inter-country order.

---

## 9) Sampling algorithm (attempt loop & cap)

### 9.0 Overview (what this section fixes)

For each merchant **m** on the multi-site, cross-border path, S4 deterministically computes the intensity $\lambda_{\text{extra},m}$ and then realises a **Zero-Truncated Poisson** by repeatedly sampling $Y\sim \text{Poisson}(\lambda)$ and **rejecting zeros** until it accepts $K_{\text{target}}\ge 1$ or hits a governed **zero-draw cap**. S4 **emits logs only**: consuming **attempt** rows, **non-consuming** rejection/cap markers, and a **non-consuming finaliser** that fixes **`K_target`** (or records a governed `K_target=0` outcome). S4 never chooses which countries—that is later.

---

### 9.1 Preconditions (merchant enters S4) — **MUST**

* **Branch purity:** S1 `is_multi = true`. If `false` ⇒ **emit nothing** in S4 for m.
* **Eligibility:** S3 `is_eligible = true`. If `false` ⇒ **emit nothing** in S4 for m.
* **Total outlets:** S2 `nb_final` exists and fixes **`N_m ≥ 2`** (read-only).
* **Admissible set size:** obtain **`A_m := size(S3.candidate_set \ {home})`** (foreigns only).

---

### 9.2 Universe-aware short-circuit — **MUST**

If **`A_m = 0`**, S4 **MUST NOT** sample. It **MUST** immediately write a **non-consuming**
`ztp_final{ K_target=0, lambda_extra: computed λ (see 9.3), attempts:0, regime: "inversion"|"ptrs" (from λ), exhausted:false [ , reason:"no_admissible"]? }`
and **skip** S6 (domestic-only downstream).

*Note:* Computing λ is still required for observability/trace uniformity; the optional `reason` field is written **only if present** in the schema.
The `regime` is derived once from λ for observability/validator uniformity; it **does not imply** that a Poisson attempt occurred.

---

### 9.3 Deterministic parameterisation — **MUST**

* **Link:** $\eta_m = \theta_0 + \theta_1 \log N_m + \theta_2 X_m + \cdots$ evaluated in **binary64**, fixed operation order (no FMA/FTZ/DAZ).
  **Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.
* **Intensity:** $\lambda_{\text{extra},m}=\exp(\eta_m)$.
* **Guard:** If $\lambda$ is **NaN/Inf/≤0**, fail merchant in S4 with `NUMERIC_INVALID` (no attempts written).
* **Regime selection (fixed threshold):** if $\lambda < 10$ ⇒ **regime = "inversion"**; else **"ptrs"**. The chosen **regime is constant per merchant** (no mid-loop switching).

---

### 9.4 Substream & envelope set-up — **MUST**

* Use the **frozen identifiers** (module / substream / context) from §2A for all S4 events.
* Start a merchant-keyed **attempt counter** `a := 1` (attempts are **1-based**).
* Each event’s envelope **must** carry `{ts_utc, module, substream_label, context, before, after, blocks, draws}`.
* **Budget law:** consuming attempts satisfy `blocks == after − before` and `draws > 0`; markers/final are **non-consuming** with `before == after`, `blocks == 0`, `draws = "0"`.

---

### 9.5 Attempt loop (realising ZTP) — **MUST**

Repeat until **acceptance** or **cap**:

1. **Draw attempt `a`.** Sample $K_a \sim \text{Poisson}(\lambda)$ using the merchant’s **fixed regime**.
   **Emit** a **consuming** `poisson_component{ merchant_id, attempt:a, k:K_a, lambda_extra, regime }`.

2. **Zero?**

   * If **`K_a == 0`**: **emit** a **non-consuming** `ztp_rejection{ merchant_id, attempt:a, k:0, lambda_extra }`.
     **Cap check (now):**
     - If **`a == MAX_ZTP_ZERO_ATTEMPTS`** ⇒ **emit** a **non-consuming** `ztp_retry_exhausted{ merchant_id, attempts:a, lambda_extra }` and apply policy (see below).
     - Else **set `a := a+1`** and continue.
   * If **`K_a ≥ 1`** (**ACCEPT**): set `K_target := K_a`; **emit** a **non-consuming**
     `ztp_final{ merchant_id, K_target, lambda_extra, attempts:a, regime, exhausted:false }` and **STOP**.

3. **Policy on cap (from the prior branch):**

   * **`"abort"` ⇒ STOP** with **no `ztp_final`**; outcome is `ZTP_EXHAUSTED_ABORT`.
   * **`"downgrade_domestic"` ⇒ emit** a **non-consuming**
     `ztp_final{ merchant_id, K_target=0, lambda_extra, attempts:a, regime, exhausted:true }` and **STOP** (domestic-only downstream).

*Trace note:* After **each** event append in steps (1)–(3), **append exactly one** cumulative `rng_trace_log` row (saturating totals) for `(module, substream_label)` (see §7).

**Norms inside the loop**

* **No regime switching** mid-merchant.
* **No silent retries:** each Poisson draw writes exactly one **consuming** attempt; each zero writes exactly one **non-consuming** rejection marker.
* **Attempt indexing** is **1-based, strictly increasing**, and **monotone** within m.

---

### 9.6 Ordering & replay — **MUST**

* Within a merchant’s substream, envelope counters are **monotone, non-overlapping**; validators reconstruct attempt order **from counters** (not timestamps or file order).
* The accepting attempt (or capped path) is the **last** event sequence for that merchant’s substream; the presence/absence of `ztp_final` reflects the policy outcome unambiguously.
* After **each** S4 append, write one **cumulative** `rng_trace_log` row (saturating totals) for `(module, substream_label)`.

---

### 9.7 Postconditions (what S4 fixes) — **MUST**

For a resolved merchant:

* Either **`K_target ≥ 1`** via acceptance, with exactly one `ztp_final{…, exhausted:false}`, or
* **`K_target = 0`** via **A=0** short-circuit or **"downgrade_domestic"** policy, with exactly one `ztp_final{…, exhausted:true [ , reason:"no_admissible"]? }`, or
* **Abort** under `"abort"` policy at cap: **no `ztp_final`**; exactly one `ztp_retry_exhausted`.
* In all acceptance/short-circuit/downgrade cases, **exactly one** `ztp_final` exists for the merchant.
* No S4 Parquet products exist; only the four event streams.

---

### 9.8 Prohibitions & edge discipline — **MUST NOT**

* **MUST NOT** write any S4 events for singles or ineligible merchants.
* **MUST NOT** compute or encode inter-country order in S4.
* **MUST NOT** switch the Poisson regime mid-loop or reuse counters across merchants.
* **MUST NOT** emit zero-row files for any S4 stream partitions.

---

### 9.9 Determinism under concurrency — **MUST**

* A merchant’s attempt loop executes **serially** (fixed iteration order).
* Concurrency is **across** merchants only; any writer/merge step must be **stable** w\.r.t. the sort keys in §6 to ensure **byte-identical** outputs for identical inputs.

---

### 9.10 Observability hooks (values-only) — **SHOULD**

For each `(seed, parameter_hash, run_id)`:

* per-merchant: `{attempts, zero_rejections, accepted_K (or 0), regime, exhausted?}`
* per-run: acceptance-rate estimate $1-e^{-\bar{\lambda}}$ vs observed, cap rate, regime split, elapsed-ms quantiles.

---

## 9A) Universe awareness & short-circuits

### What "A" is (precise).
Let **`A := size(S3.candidate_set \ {home})`** be the count of *foreign* ISO2s in the merchant’s admissible universe (home excluded). S4 **does not** use `candidate_rank` here—only the set size.

### How S4 obtains A (read-side discipline).

* Read **`s3_candidate_set`** under **`parameter_hash={…}`** (parameter-scoped).
* **MUST** enforce path↔embed equality for required lineage fields on read.
* **MUST NOT** infer A from file order or any non-governed source.
* Missing/ill-formed admissible-set data is an **upstream S3 error**, not an S4 defect.

### Short-circuit when `A = 0` (no admissible foreigns).

* **MUST NOT** run the Poisson loop.
* **MUST** still compute `lambda_extra` (binary64, fixed order) for observability and regime derivation.
* **MUST** immediately write a **non-consuming**
  `ztp_final{ K_target=0, lambda_extra, attempts:0, regime: "inversion"|"ptrs", exhausted:false [ , reason:"no_admissible"]? }`.
  *(The `reason` field is written only if present in the finaliser schema.)*
* **MUST** skip S6 (no top-K) and proceed along the domestic-only path downstream (S7 will allocate `{home: N}`).

### When `A > 0` (normal case).

* Run the Poisson loop per **§9.5**.
* Acceptance yields **`K_target ≥ 1`**.
* **MUST NOT** cap `K_target` to `A` in S4. S4 fixes **`K_target`**; **S6 MUST** realise `K_realized = min(K_target, A)` (see **§9B**).

### Invariant & logging.

* Exactly one `ztp_final` per resolved merchant (absent only on hard abort).
* **Informative:** ops counters **SHOULD** record short-circuits (count of `K_target=0` due to `A=0`).

### Prohibitions.

* **MUST NOT** emit any S4 events for `is_multi=false` or `is_eligible=false`.
* **MUST NOT** encode inter-country order in S4.

---

## 9B) S4 → **S6** handshake

### Purpose.
Fix what S6 must consume from S4 and how to realise selection size for all outcomes.

### What S6 reads from S4 (authoritative):
fields from **`ztp_final`** for the merchant:

* `K_target : int` — the **target** foreign count S4 fixed (≥1 on acceptance; 0 on short-circuit/downgrade).
* `lambda_extra : float64` — intensity used (audit/diagnostics; not a decision gate in S6).
* `attempts : int≥0` — number of Poisson attempts written by S4 (0 iff short-circuit).
* `regime : "inversion"|"ptrs"` — Poisson regime S4 used (closed enum).
* `exhausted? : bool` — present and `true` only when cap hit and policy was **"downgrade_domestic"**.

### What S6 must combine with its own inputs:

* **`A`** (admissible foreign set size) and the **ordered/weighted foreign candidate list** S6 owns.

### Realisation rule (binding).

* **MUST** compute **`K_realized = min(K_target, A)`**.
* If `K_target = 0` (short-circuit or downgrade): **MUST** skip top-K entirely and continue with the domestic-only path.
* If `K_target > A`: **MUST** select **all `A`** foreigns (top-K shortfall). S6 **MAY** emit its own **non-consuming** marker (e.g., `topk_shortfall{K_target, A}`) in **its** state; S4 does not emit this marker.

### Outcomes matrix (exhaustive).

| S4 outcome                                                   | `A`                | S6 must…                                                                                                           |
|--------------------------------------------------------------|--------------------|--------------------------------------------------------------------------------------------------------------------|
| `ztp_final{K_target ≥ 1, exhausted:false}`                   | `A ≥ K_target`     | Select exactly `K_target` foreigns via its governed top-K mechanism; proceed.                                      |
| `ztp_final{K_target ≥ 1, exhausted:false}`                   | `0 < A < K_target` | Select **all `A`** (shortfall); **MUST** treat `K_realized = A`.                                                   |
| `ztp_final{K_target=0 [ , reason:"no_admissible"]? }`        | `A = 0`            | Skip top-K; domestic-only path.                                                                                    |
| `ztp_final{K_target=0, exhausted:true}` (policy = downgrade) | any `A`            | Skip top-K; domestic-only path.                                                                                    |
| Cap + policy = `"abort"` (no `ztp_final`)                    | any `A`            | **MUST NOT** run S6 for this merchant; pipeline treats merchant as **aborted** for S4+ (downstream states ignore). |

### Lineage continuity (MUST).

* S6 **must** carry forward the same `{seed, parameter_hash, run_id}` lineage triplet for any logs it writes.
* S6 **must not** reinterpret `lambda_extra` or `regime`.

### Authority boundaries (reaffirmed).

* S4 **fixes counts only at the target level** (`K_target`).
* S6 **owns**: which foreign ISO2s are chosen and in what order/weight for later stages.
* S3 `candidate_rank` remains the sole cross-country **order** authority; S4 never encodes order.

### Prohibitions.

* **MUST NOT** ignore `ztp_final` (if present).
* **MUST NOT** realise `K` greater than `A`.
* **MUST NOT** treat Poisson attempts or rejections as authoritative selection signals (they are evidence only; `ztp_final` is the single acceptance record).

---

## 10) Draw accounting & envelopes

### 10.1 Streams S4 writes (reminder).
Logs only, all partitioned by `{seed, parameter_hash, run_id}` with a full RNG **envelope** on every row:

* `poisson_component` (with `context:"ztp"`): **consuming** attempt rows.
* `ztp_rejection`: **non-consuming** zero marker.
* `ztp_retry_exhausted`: **non-consuming** cap-hit marker.
* `ztp_final`: **non-consuming** finaliser that **fixes** `{K_target, …}`.

### 10.2 Envelope fields (MUST).
Every S4 event row **must** carry:

* `ts_utc` (microsecond; observational only—never used for ordering).
* `module`, `substream_label`, `context` — **must match** the frozen identifiers in §2A.
* `before` (u128), `after` (u128), `blocks` (u64), `draws` (decimal-u128 as **string**).
* **MUST.** `draws` uses the S0 **canonical decimal-u128** format (no sign, no exponent, no leading zeros except `"0"`).
* Path↔embed equality: embedded `{seed, parameter_hash, run_id}` **must equal** path tokens **byte-for-byte**.

### 10.3 Budget identities (MUST).

* **Consuming attempts** (`poisson_component(context:"ztp")`):
  `blocks == after − before` (**strictly positive**), and `draws` parses as decimal-u128 and is **> 0** (actual uniforms consumed).
* **Non-consuming markers/final** (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`):
  `before == after`, `blocks == 0`, `draws == "0"`.

### 10.4 Per-attempt write discipline (MUST).

* Exactly **one** consuming `poisson_component` row **per attempt index** for the merchant (attempts are **1-based** and contiguous).
* If that attempt’s `k == 0`, write exactly **one** `ztp_rejection{attempt}` **after** the attempt row.
* If that attempt’s `k ≥ 1` (acceptance), **no rejection marker** for that attempt; instead write exactly **one** `ztp_final{attempts := a}` after the attempt row.
* If the **cap** is reached with all zeros:
  - if policy=`"abort"` → write exactly **one** `ztp_retry_exhausted{attempts := MAX, aborted:true}` and **no** `ztp_final`;
  - if policy=`"downgrade_domestic"` → **do not** write an exhausted marker; write `ztp_final{K_target=0, exhausted:true}` (non-consuming).

### 10.5 Monotone, non-overlapping counters (MUST).

* Within a merchant’s substream, counter spans **must** be **strictly increasing and non-overlapping** for consuming events.
* Ordering and pairing for replay/validation is by **counters only** (timestamps and file order are non-authoritative).

### 10.6 Payload typing & constancy (MUST).

* **Attempt rows** (`poisson_component`, `ztp_rejection`): `attempt:int≥1`.
* **Finaliser / cap rows** (`ztp_final`, `ztp_retry_exhausted`): `attempts:int≥0` (==0 only on A=0 short-circuit).
* Common fields (where present): `k:int≥0`, `K_target:int≥0`, `lambda_extra:float64 (finite, >0)`, `regime ∈ {"inversion","ptrs"}`.
* For a given merchant, `lambda_extra` and `regime` **must** be identical across all S4 rows for that merchant (computed once in §9.3).

### 10.7 Writer sort & uniqueness (MUST).

* Sort keys (as in §6):
  - attempts/rejections by `(merchant_id, attempt)` (stable),
  - cap marker by `(merchant_id, attempts)`,
  - finaliser by `(merchant_id)`.
* Uniqueness constraints:
  - ≤1 `poisson_component` per `(merchant_id, attempt)`,
  - ≤1 `ztp_rejection` per `(merchant_id, attempt)`,
  - ≤1 `ztp_retry_exhausted` per merchant,
  - ≤1 `ztp_final` per **resolved** merchant.

### 10.8 Trace duty (MUST).

* After **each** S4 row append, write one cumulative `rng_trace_log` record (saturating totals) keyed by `(module, substream_label)`.
  - Consuming attempt: trace counters **increase** by the event’s `blocks`/`draws`.
  - Non-consuming marker/final: trace counters **do not increase**; only the event count increments.

### 10.9 Zero-row files & idempotence (MUST).

* Zero-row files are **forbidden**; empty slices write nothing.
* Re-running with identical inputs **must** produce byte-identical content; if a complete partition already exists, **must** no-op (skip-if-final).

---

## 11) Invariants (state-level)

### 11.1 Branch purity & scope.

* **No S4 events** for merchants with `is_multi=false` or `is_eligible=false`.
* S4 is **logs-only**; S4 writes **no Parquet egress** and **never encodes inter-country order**.

### 11.2 Parameterisation & regime.

* For each merchant, `η` and `λ_extra` are computed **once** (binary64, fixed order); `λ_extra` must be **finite and >0**.
* The Poisson **regime** (`"inversion"` if `λ<10`, otherwise `"ptrs"`) is **fixed** for the merchant; **no regime switching** mid-loop.

### 11.3 Attempts, markers, finalisers.

* **Acceptance path:**
  - ≥1 consuming `poisson_component(context:"ztp")`, with the **last** having `k ≥ 1`.
  - Exactly **one** non-consuming `ztp_final{K_target≥1, exhausted:false}`.
  - No `ztp_retry_exhausted`.
* **Cap path:**
  - A sequence of `poisson_component` with `k=0` and matching `ztp_rejection`s.
  - Policy=`"abort"` ⇒ exactly **one** `ztp_retry_exhausted{aborted:true}` and **no** `ztp_final`.
  - Policy=`"downgrade_domestic"` ⇒ **no** exhausted marker; exactly **one** `ztp_final{K_target=0, exhausted:true}`.
* **A=0 short-circuit:**
  - Exactly **one** `ztp_final{K_target=0, attempts:0 [ , reason:"no_admissible"]? }`; **no** attempts, **no** rejections, **no** cap marker.

### 11.4 Counter & budget identities.

* For every consuming attempt row: `after > before`, `blocks == after − before`, and `draws > 0` (decimal-u128).
* For every non-consuming marker/final: `before == after`, `blocks == 0`, `draws == "0"`.
* Within a merchant’s substream, counter spans are **monotone** and **non-overlapping**.

### 11.5 Cardinality & contiguity.

* Attempt indices are **contiguous**: `1..a` for attempts; `ztp_final.attempts == a` on acceptance/cap, and `== 0` on A=0 short-circuit.
* Exactly **one** `ztp_final` per **resolved** merchant (absent only on hard abort).
* At most **one** `ztp_retry_exhausted` per merchant, and only when the cap is reached.

### 11.6 Partitions, lineage & identifiers.

* All S4 streams live under `{seed, parameter_hash, run_id}`; embedded lineage **equals** path tokens **byte-for-byte**.
* `module`, `substream_label`, `context` **must** match the frozen registry in §2A.

### 11.7 Determinism & concurrency.

* For fixed inputs and lineage, the attempt sequence, acceptance, and finaliser content are **bit-replayable** (counter-based).
* Concurrency is **across** merchants only; each merchant’s loop is **serial**. Writer merges are **stable** w\.r.t. §6 sort keys.
* Re-runs on identical inputs yield **byte-identical** outputs (idempotence).

### 11.8 Separation of concerns (downstream compatibility).

* S4 **fixes** only `K_target` (or governed `0`); **S6** realises `K_realized = min(K_target, A)` and owns which foreign ISO2s are chosen.
* S3 `candidate_rank` remains the sole cross-country **order** authority; S4 never writes order.

### 11.9 Prohibitions.

* **MUST NOT** emit any S4 rows for singles/ineligible merchants.
* **MUST NOT** compute/encode inter-country order.
* **MUST NOT** write zero-row files.
* **MUST NOT** change `λ_extra` or `regime` across attempts for a merchant.
* **MUST NOT** use timestamps or file order to reconstruct sequencing (counters only).

---

## 12) Failure vocabulary (stable codes)

> **Principles.**
> - Fail **deterministically**; never emit partial merchant output.
> - **Scope** every failure (Merchant vs Run).
> - Emit **values-only** context (no paths), with stable keys.
> - Prefer **merchant-scoped** failure; reserve **run-scoped** for structural/authority violations.

### 12.1 Required failure payload (all codes) — **MUST**

Each failure record **MUST** include:

```
{
  code,
  scope ∈ {"merchant","run"},
  reason : str,
  merchant_id? : int64,
  seed : u64, parameter_hash : hex64, run_id : str, manifest_fingerprint : hex64,
  attempts? : int,          // present if any attempts occurred; 0 for A=0 short-circuit; omitted otherwise
  lambda_extra? : float64,  // present if computed (§9.3) or any attempts were made
  regime? : "inversion" | "ptrs"
}
```

*`merchant_id` is present for merchant-scoped failures.*

### 12.2 Stable codes — **MUST**

| Code                    | Scope    | Condition (trigger)                                                                                      | Required producer behavior                                                  |
|-------------------------|----------|----------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `UPSTREAM_MISSING_S1`   | Merchant | No authoritative hurdle decision found for merchant (S1)                                                 | **Abort** merchant; write no S4 events; upstream coverage error.            |
| `NUMERIC_INVALID`       | Merchant | $\lambda_{\text{extra}}$ is NaN/Inf/≤0 after §9.3                                                        | **Abort** merchant; **no** attempts; **no** `ztp_final`; log failure.       |
| `BRANCH_PURITY`         | Merchant | Any S4 event for `is_multi=false` or `is_eligible=false`                                                 | **Abort** merchant; suppress further S4 events; log failure.                |
| `A_ZERO_MISSHANDLED`    | Merchant | `A=0` **and** (any attempts **or** `K_target≠0` **or** *(if schema has field)* `reason≠"no_admissible"`) | **Abort** merchant; log failure (implementation bug).                       |
| `ATTEMPT_GAPS`          | Merchant | Attempt indices not contiguous from 1..a                                                                 | **Abort** merchant; log failure.                                            |
| `FINAL_MISSING`         | Merchant | Acceptance observed (last `poisson_component.k≥1`) but **no** `ztp_final`                                | **Abort** merchant; log failure.                                            |
| `MULTIPLE_FINAL`        | Merchant | >1 `ztp_final` for merchant                                                                              | **Abort** merchant; log failure.                                            |
| `CAP_WITH_FINAL_ABORT`  | Merchant | `ztp_retry_exhausted` present and policy=`abort` **but** a `ztp_final` exists                            | **Abort** merchant; log failure.                                            |
| `ZTP_EXHAUSTED_ABORT`   | Merchant | Cap hit and policy=`abort`                                                                               | **Stop** merchant; **no** `ztp_final`; log this code (outcome; not a bug).  |
| `TRACE_MISSING`         | Merchant | Event append without a corresponding **cumulative** `rng_trace_log` update                               | **Abort** merchant; log failure; trace duty breached.                       |
| `POLICY_INVALID`        | Run      | `ztp_exhaustion_policy` **missing or** ∉ {"abort","downgrade_domestic"}                                  | **Abort run**; configuration/artefact error.                                |
| `REGIME_INVALID`        | Merchant | `regime` ∉ {"inversion","ptrs"} **or** regime switched mid-merchant                                      | **Abort** merchant; log failure.                                            |
| `RNG_ACCOUNTING`        | Merchant | Consuming row with `draws≤0` **or** `blocks≠after−before`; **or** non-consuming marker advanced counters | **Abort** merchant; log failure; counters must be monotone/non-overlapping. |
| `STREAM_ID_MISMATCH`    | Run      | `module/substream_label/context` deviate from §2A registry                                               | **Abort run**; label registry violated.                                     |
| `PARTITION_MISMATCH`    | Run      | Path tokens `{seed,parameter_hash,run_id}` ≠ embedded envelope fields                                    | **Abort run**; structural violation.                                        |
| `DICT_BYPASS_FORBIDDEN` | Run      | Producer used literal paths (bypassed dictionary)                                                        | **Abort run**; structural violation.                                        |
| `UPSTREAM_MISSING_S2`   | Merchant | S2 `nb_final` absent for merchant entering S4                                                            | **Abort** merchant; upstream coverage error.                                |
| `UPSTREAM_MISSING_A`    | Merchant | **`s3_candidate_set`** unavailable/ill-formed for the merchant (A cannot be derived)                     | **Abort** merchant; upstream S3 error.                                      |
| `ZERO_ROW_FILE`         | Run      | Any S4 stream wrote a zero-row file                                                                      | **Abort run**; zero-row files forbidden.                                    |
| `UNKNOWN_CONTEXT`       | Run      | S4 events have `context≠"ztp"`                                                                           | **Abort run**; schema/producer bug.                                         |

### 12.3 No partial writes — **MUST**

* On **merchant-scoped** failure, **MUST NOT** emit additional S4 rows for that merchant after logging the failure.
* On **run-scoped** failure, **MUST** stop writing immediately.

### 12.4 Logging keys (stable) — **MUST**

Use these values-only keys for failure lines:

```
s4.fail.code, s4.fail.scope, s4.fail.reason,
s4.fail.attempts, s4.fail.lambda_extra, s4.fail.regime,
s4.run.seed, s4.run.parameter_hash, s4.run.run_id, s4.run.manifest_fingerprint,
s4.fail.merchant_id?
```

### 12.5 Mapping to validation — **Informative**

Validator checks for `ATTEMPT_GAPS`, `FINAL_MISSING`, `RNG_ACCOUNTING`, `TRACE_MISSING` mirror these producer codes; failures should correlate 1:1.

**Informative.** S4 codes are the canonical names for this state and appear **as-is** in the global ledger; the run’s failure record also carries the S0 global `failure_class` per the validation schema.

---

## 13) Observability (values-only; bytes-safe)

> **Aim.** Minimal, stable metrics for S4 health/cost/behavior **without** paths/PII or duplicating validator logic. Metrics are values-only and keyed to run lineage.

### 13.1 Run lineage dimensions — **MUST**

Every metric line **MUST** include:

```
{ seed, parameter_hash, run_id, manifest_fingerprint }
```

### 13.2 Minimal counters & gauges — **MUST**

| Key                              | Type    | Definition                                                                                                                                  |
|----------------------------------|---------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `s4.merchants_in_scope`          | counter | # merchants that entered S4 (S1 multi **and** S3 eligible).                                                                                 |
| `s4.accepted`                    | counter | # merchants with `ztp_final{K_target≥1, exhausted:false}`.                                                                                  |
| `s4.short_circuit_no_admissible` | counter | # merchants resolved via **A=0** short-circuit (detect as `attempts==0 ∧ K_target==0` and, **if field exists**, `reason=="no_admissible"`). |
| `s4.downgrade_domestic`          | counter | # merchants with `ztp_final{K_target=0, exhausted:true}`.                                                                                   |
| `s4.aborted`                     | counter | # merchants with `ZTP_EXHAUSTED_ABORT`.                                                                                                     |
| `s4.rejections`                  | counter | Total zero-draw rejections written (count of `ztp_rejection`).                                                                              |
| `s4.attempts.total`              | counter | Total attempts across all merchants (count of `poisson_component`).                                                                         |
| `s4.trace.rows`                  | counter | Total S4 events appended (sum over all four streams; should equal cumulative trace row count).                                              |
| `s4.regime.inversion`            | counter | # merchants whose regime was `"inversion"`.                                                                                                 |
| `s4.regime.ptrs`                 | counter | # merchants whose regime was `"ptrs"`.                                                                                                      |

### 13.3 Distributions / histograms — **SHOULD**

| Key                       | Kind      | Definition                                                                       |
|---------------------------|-----------|----------------------------------------------------------------------------------|
| `s4.attempts.hist`        | histogram | Per-merchant attempts (accepted path → `attempts`; A=0 → 0; abort → cap value).  |
| `s4.lambda.hist`          | histogram | Bucketed $\lambda_{\text{extra}}$ (e.g., log-buckets); values are finite and >0. |
| `s4.ms.poisson_inversion` | histogram | Milliseconds spent in inversion branch (per merchant).                           |
| `s4.ms.poisson_ptrs`      | histogram | Milliseconds spent in PTRS branch (per merchant).                                |

### 13.4 Derived rates (computed by metrics layer) — **SHOULD**

* `s4.accept_rate = s4.accepted / s4.merchants_in_scope`
* `s4.cap_rate = s4.aborted / s4.merchants_in_scope`
* `s4.mean_attempts = s4.attempts.total / s4.merchants_in_scope`

### 13.5 Per-merchant summaries — **SHOULD**

Emit one values-only summary per **resolved** merchant:

```
s4.merchant.summary = {
  merchant_id,
  attempts,
  accepted_K : (K_target | 0),
  regime,
  exhausted : bool,
  reason?          // present only if the ztp_final schema has this optional field
}
```

*`accepted_K` is 0 for A=0 short-circuit or downgrade. Omit the summary for hard abort (policy=`abort`).*

### 13.6 Emission points — **MUST**

* Increment outcome counters **exactly once per merchant**: on writing `ztp_final` (accepted/downgrade/short-circuit) **or** on logging `ZTP_EXHAUSTED_ABORT`.
* Update attempt/rejection counters **immediately after** writing each corresponding row.
* Write histogram samples **once per merchant** at resolution (on final/abort).
* **Emission responsibility:** Metrics **MUST** be emitted by the same process that writes the event rows, **after** the event fsync completes.

### 13.7 Cardinality & privacy — **MUST**

* **Values-only; no paths/URIs.**
* **Bounded cardinality:** keys are run-scoped plus `merchant_id`; no high-cardinality labels beyond those.
* **No PII.** `merchant_id` is an ID; do not log names or free-text beyond stable enum `reason` values.

### 13.8 Alerting hints — **Informative**

* **Cap rate spike** (e.g., `s4.cap_rate > 0.01`) → investigate θ or `X` transform drift.
* **Mean attempts ↑** or **rejections ↑** → indicative of low $\lambda$; check cohorts with small `N` or `X`.
* **Unexpected regime split** → verify regime threshold/constants.
* Any **`NUMERIC_INVALID` > 0** → input/overflow issue; block release.

### 13.9 Output format — **MUST**

All metrics are emitted as structured values (e.g., JSON lines) with the lineage dimension and keys from this section; consumers/aggregation are outside S4’s scope.

---

## 14) Interfaces & dictionary (lookup table)

> **Goal.** Freeze exactly what S4 **writes** and **reads**, how each stream is **partitioned**, which **envelope** fields are required, the **writer sort keys**, and who **consumes** the output. Physical paths come from the **Data Dictionary**; S4 **must not** hard-code paths.

### 14.1 Streams S4 **writes** (logs-only)

| Stream ID                                            | Schema anchor (authoritative)                         | Partitions (path keys)         | Required envelope fields (all rows)                                      | Required payload (minimum)                                                                                                                          | Writer sort keys (stable)                                               | Consumers                                             |
|------------------------------------------------------|-------------------------------------------------------|--------------------------------|--------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|-------------------------------------------------------|
| `rng_event_poisson_component` (with `context:"ztp"`) | `schemas.layer1.yaml#/rng/events/poisson_component`   | `seed, parameter_hash, run_id` | `ts_utc, module, substream_label, context, before, after, blocks, draws` | `{ merchant_id, attempt:int≥1, k:int≥0, lambda_extra:float64, regime:"inversion" \| "ptrs" }`                                                       | `(merchant_id, attempt)`                                                | S4 validator, observability                           |
| `rng_event_ztp_rejection`                            | `schemas.layer1.yaml#/rng/events/ztp_rejection`       | `seed, parameter_hash, run_id` | *(same envelope fields as above)*                                        | `{ merchant_id, attempt:int≥1, k:0, lambda_extra }`                                                                                                 | `(merchant_id, attempt)`                                                | S4 validator, observability                           |
| `rng_trace_log`                                      | `schemas.layer1.yaml#/rng/core/rng_trace_log`         | `seed, parameter_hash, run_id` | `ts_utc, module, substream_label`                                        | `{ module, substream_label, rng_counter_after_hi:u64,  rng_counter_after_lo:u64  }`                                                                 | `(module, substream_label, rng_counter_after_hi, rng_counter_after_lo)` | S4 validator, observability                           |
| `rng_event_ztp_retry_exhausted`                      | `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` | `seed, parameter_hash, run_id` | *(same envelope fields as above)*                                        | `{ merchant_id, attempts:int≥1, lambda_extra, aborted:true }`                                                                                       | `(merchant_id, attempts)`                                               | S4 validator, observability (abort-only)              |
| `rng_event_ztp_final`                                | `schemas.layer1.yaml#/rng/events/ztp_final`           | `seed, parameter_hash, run_id` | *(same envelope fields as above)*                                        | `{ merchant_id, K_target:int≥0, lambda_extra:float64, attempts:int≥0, regime:"inversion" \| "ptrs", exhausted?:bool [ , reason:"no_admissible"]? }` | `(merchant_id)`                                                         | **S6** (reads `K_target,…`), validator, observability |

**MUST.**

* **Path↔embed equality:** For **event streams**, embedded `{seed, parameter_hash, run_id}` **must equal** path tokens **byte-for-byte**.  
  `rng_trace_log` **omits** these fields by design; lineage equality for trace rows is enforced via the partition path keys.
* **Label registry:** For **event streams**, `module`, `substream_label`, `context` **must** match §2A’s frozen literals.  
  `rng_trace_log` carries only `module` and `substream_label` (no `context`).
* **File order is non-authoritative:** Pairing/replay **MUST** use **envelope counters** only.
* **Trace duty:** After each event append, **append exactly one** cumulative `rng_trace_log` row (see §§7/10).
* **Failure records sink:** On abort, write values-only `failure.json` under the S0 bundle path `data/layer1/1A/validation/failures/fingerprint={manifest_fingerprint}/seed={seed}/run_id={run_id}/` using the payload keys in §12.1/§12.4. *(Not a stream.)*

**Schema versioning note.** The optional `reason:"no_admissible"` field on `ztp_final` is **present only** in schema versions that include it (per §21.1 it is absent in this version). Its mention in the table is **forward-compatible**; producers must omit it unless the bound schema version defines it.

---

### 14.2 Surfaces S4 **reads** (gates / facts)

| Surface                            | Schema anchor                                       | Partitions                     | What S4 uses (only)                                                                             | Notes                            |
|------------------------------------|-----------------------------------------------------|--------------------------------|-------------------------------------------------------------------------------------------------|----------------------------------|
| S1 hurdle events                   | `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`  | `seed, parameter_hash, run_id` | **Gate:** `is_multi==true` to enter S4                                                          | S4 writes nothing for singles    |
| S2 `nb_final`                      | `schemas.layer1.yaml#/rng/events/nb_final`          | `seed, parameter_hash, run_id` | **Fact:** authoritative `N_m≥2` (non-consuming; one per merchant)                               | Read-only; S4 must not alter `N` |
| S3 `crossborder_eligibility_flags` | `schemas.1A.yaml#/s3/crossborder_eligibility_flags` | `parameter_hash`               | **Gate:** `is_eligible==true`                                                                   | Deterministic; no RNG            |
| S3 `candidate_set`                 | `schemas.1A.yaml#/s3/candidate_set`                 | `parameter_hash`               | **Context:**  `A := size(S3.candidate_set \ {home})` (foreign count only); S4 doesn’t use order | File order non-authoritative     |

**MUST.** When reading S1/S2 logs, enforce **path↔embed** equality on `{seed, parameter_hash, run_id}`; treat violations as structural failures (run-scoped).

---

### 14.3 Ordering & idempotence requirements (writer)

* **Sort before write** per table above; merges must be **stable** w.r.t. sort keys.
* **Skip-if-final:** if a complete partition already exists with byte-identical content, **no-op**.
* **Uniqueness per merchant:** ≤1 `poisson_component` per `(merchant_id, attempt)`; ≤1 `ztp_rejection` per `(merchant_id, attempt)`; ≤1 `ztp_retry_exhausted`; ≤1 `ztp_final` if the merchant is **resolved** (absent only under hard abort).

---

## 15) Numeric policy & equality (S4-local application)

> **Goal.** Pin the exact math, equality, and comparison discipline S4 applies so results are reproducible and validator-provable—without tolerances or hidden heuristics.

### 15.1 Floating-point profile (binding)

* **IEEE-754 binary64**, **round-to-nearest-even**, **FMA-off**, **no FTZ/DAZ** for any computation that can affect outcomes or payloads.
* All merchant-local computations run with a **fixed operation order**; no parallel/underdetermined reductions.

**MUST.** Treat **NaN/Inf** anywhere in `η`/`λ_extra` evaluation as a hard error (`NUMERIC_INVALID`); write no attempts.

---

### 15.2 Link evaluation & regime threshold

* **Link:** $\eta = \theta_0 + \theta_1 \log N + \theta_2 X + \cdots$ evaluated in **binary64**, fixed order.
  **Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.
* **Intensity:** $\lambda_{\text{extra}}=\exp(\eta)$ (**finite, >0** required).
* **Regime (spec-fixed threshold):**
  * If $\lambda_{\text{extra}} < 10$ → `regime="inversion"`
  * Else (including `==10`) → `regime="ptrs"`
    Regime is **fixed per merchant** (no switching mid-loop).
  *(Primary rule.)* See **§15.6 Payload constancy within a merchant** for the one-time evaluation and constancy of `regime` and `lambda_extra`.
* **Informative.** PTRS constants are normative and pinned upstream in **S0.3.7**; **S2 §3.2** implements that profile for NB Poisson.

---

### 15.3 Uniform mapping & budget identities

* **Open-interval uniforms:** map PRNG counters to `u∈(0,1)` (strict-open; never include 0 or 1).
* **Consuming attempts** (`poisson_component`) must satisfy **both**:
  `blocks == after − before` (**>0**) and `draws` (decimal-u128 string) parses and **>0**.
* **Non-consuming markers/final** (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`) must satisfy:
  `before == after`, `blocks == 0`, `draws == "0"`.

---

### 15.4 Equality & ordering rules

* **Exact equality** for integers, counters, regime enums, and lineage tokens (no tolerances).
* **Float comparisons:** the only float comparison that affects control flow is the **regime split** at `λ<10` vs `≥10`; apply it directly in binary64 (**no epsilons**).
* **Ordering for replay/validation:** use **counters** exclusively; timestamps are observational; **file order is non-authoritative**.

---

### 15.5 Determinism & concurrency

* **Serial per merchant:** the attempt loop is single-threaded with fixed iteration order.
* **Across merchants:** concurrency allowed; any writer/merge must be **stable** w\.r.t. §14 sort keys so identical inputs yield **byte-identical** outputs.

---

### 15.6 Payload constancy within a merchant

* `lambda_extra` and `regime` are computed **once** and **must** be identical across all S4 rows for that merchant (attempts, markers, final).
* Attempt indices are **contiguous** starting at 1; `ztp_final.attempts` equals the last attempt index (or 0 for A=0 short-circuit).

---

### 15.7 Prohibitions

* **No epsilons** or fuzzy checks in producer logic (validators may compute diagnostics, but producer decisions are exact).
* **No regime drift**, **no counter reuse**, **no zero-row files**, **no path literals**.

---

## 16) Complexity & parallelism

**16.1 Per-merchant asymptotics**

* **Attempt loop (Poisson):** amortised **O(1)** work per attempt; **O(1)** memory.
* **Expected attempts:** $\mathbb{E}[\text{attempts}]=1/p$, with $p=1-e^{-\lambda_{\text{extra}}}$. The governed cap `MAX_ZTP_ZERO_ATTEMPTS` bounds worst-case attempts.
* **Uniform budgets (qualitative):**

  * **Inversion** (`λ<10`): exactly **`K+1` uniforms** for a draw returning `K`.
  * **PTRS** (`λ≥10`): a small, **variable** count per attempt (≥2). Budgets are **measured from envelopes**; producers do not infer them.
* **Rows per merchant (expected):**

  * **Acceptance path:** `attempts`×`poisson_component` + (`attempts−1`)×`ztp_rejection` + 1×`ztp_final`.
  * **Cap + downgrade:** `MAX`×`poisson_component` + `MAX`×`ztp_rejection` + 1×`ztp_retry_exhausted` + 1×`ztp_final`.
  * **Cap + abort:** `MAX`×`poisson_component` + `MAX`×`ztp_rejection` + 1×`ztp_retry_exhausted`.
  * **A=0 short-circuit:** 1×`ztp_final` only.

**16.2 Throughput & sizing**

* **Concurrency model:** run merchants **in parallel** up to a worker cap `C`; each merchant’s loop remains **serial**.
* **Writer strategy (deterministic):**
  (a) **Serial writer**: one writer enforces §6 sort keys—simplest route to byte-identical outputs.
  (b) **Partitioned merge**: workers spill **sorted** chunks; a final **stable** merge per partition assembles `(merchant_id, attempt)` order (and cap/final keys).
* **Back-pressure:** bound in-flight merchants; size queues so the writer never merges out-of-order.
* **File layout:** avoid tiny files; batch into sensible row-groups. The spec mandates **content & order** (§6) and **idempotence**, not physical sizes.

**16.3 Determinism & resume**

* **Idempotence:** identical inputs ⇒ **byte-identical** outputs. If a complete partition exists, **skip-if-final**.
* **Resume:** stage→fsync→rename ensures an all-or-nothing publish; reruns are safe.

**16.4 Instrumentation overhead**

* Metrics (values-only, §13) update at acceptance/short-circuit/abort and **after each event append**; they do not affect control flow.

---

## 17) Deterministic read-side lineage gates

> These gates ensure S4 runs only for the correct merchants and reads only authoritative inputs, with lineage equality enforced **byte-for-byte**.

### 17.1 Lineage equality for S1/S2 reads — MUST
When reading S1/S2 logs, embedded envelope fields **`{seed, parameter_hash, run_id}` must equal** the path tokens **byte-for-byte**. Any mismatch is a **run-scoped structural failure** (`PARTITION_MISMATCH`); S4 must abort the run.

### 17.2 Upstream coverage & uniqueness — MUST

* **Hurdle presence (S1):** exactly one authoritative hurdle decision **must** exist for the run.

  * If **absent** ⇒ **`UPSTREAM_MISSING_S1`** (merchant-scoped abort); S4 **must not** write any S4 rows for that merchant.
  * If present with `is_multi=false` ⇒ merchant is out of scope; any S4 events would be `BRANCH_PURITY`.
* **NB final (S2):** exactly one **non-consuming** `nb_final` per merchant in scope; it fixes **`N_m≥2`**. Absence ⇒ `UPSTREAM_MISSING_S2` (merchant-scoped abort).
* **Eligibility & admissible context (S3):** S4 requires an eligibility verdict and an admissible set to derive **`A`**. Missing/ill-formed context ⇒ `UPSTREAM_MISSING_A` (merchant-scoped abort). S4 **does not** use S3 order at this state.

  * **File order is non-authoritative** for S3 reads: derive **`A := size(S3.candidate_set \ {home})`** from set contents only (never from writer order).

### 17.3 Dictionary resolution — MUST
All physical locations (read and write) are resolved via the **Data Dictionary**. Hard-coding or constructing literal paths is forbidden (`DICT_BYPASS_FORBIDDEN`, run-scoped).

### 17.4 Partition scopes — MUST

* **Reads:** S1/S2 under **`{seed, parameter_hash, run_id}`**; S3 under **`parameter_hash={…}`** (parameter-scoped).
* **Writes:** all S4 streams under **`{seed, parameter_hash, run_id}`**. Path↔embed equality must hold for every S4 row written.

### 17.5 Time & ordering neutrality — MUST
S4 must not depend on wall-clock time or file enumeration order. Ordering/replay is by **counters only** (per §10); timestamps are observational.

### 17.6 Merchant scope isolation — MUST
A merchant’s attempt loop uses a **merchant-keyed** substream and may not interleave counter spans with another merchant’s substream. Counter reuse across merchants is forbidden.

### 17.7 Deterministic inputs surface — MUST
`η`/`λ_extra`, `regime`, and `A` must be determined solely from governed values (`θ`, `X` transform/default, `MAX_ZTP_ZERO_ATTEMPTS`, `ztp_exhaustion_policy`) and authoritative upstream facts (S1, S2, S3). No environment-dependent inputs are permitted.

### 17.8 Failure handling — MUST
On any gate violation above, producers emit exactly one **values-only** failure line (per §12) and stop in the appropriate scope (merchant/run). **No partial merchant output** may be written after a merchant-scoped failure.

---

## 18) Artefact governance & parameter-hash participation

### 18.1 Purpose.
Pin exactly which governed inputs S4 depends on, how they are versioned and normalised, and how their bytes participate in the run’s **`parameter_hash`**. S4 is **logs-only** and is partitioned by `{seed, parameter_hash, run_id}`; these rules ensure **reproducible** K-draws and traceability.

### 18.2 Governance ledger (S4-relevant artefacts) — MUST

| Artefact (governed value) | Purpose in S4                          | Owner       | Semver | Digest algo | Participates in `parameter_hash` | Notes                                             |
|---------------------------|----------------------------------------|-------------|--------|-------------|----------------------------------|---------------------------------------------------|
| `θ = (θ₀, θ₁, θ₂, …)`     | Link parameters for `η`                | Policy      | x.y.z  | SHA-256     | **YES**                          | Numeric values serialised canonically (see §18.3) |
| `X` transform spec        | Map raw signals → `X_m ∈ [0,1]`        | Policy/Data | x.y.z  | SHA-256     | **YES**                          | Includes scaling, cohort, monotone mapping        |
| `X_default`               | Fallback when `X_m` missing            | Policy      | x.y.z  | SHA-256     | **YES**                          | Must be in \[0,1]                                 |
| `MAX_ZTP_ZERO_ATTEMPTS`   | Zero-draw cap (int)                    | Policy      | x.y.z  | SHA-256     | **YES**                          | Default 64 unless governed otherwise              |
| `ztp_exhaustion_policy`   | `"abort"` or `"downgrade_domestic"`    | Policy      | x.y.z  | SHA-256     | **YES**                          | Closed enum                                       |
| Label/stream registry     | `module`, `substream_label`, `context` | Engine      | x.y.z  | SHA-256     | **NO** (code contract)           | Changes are **breaking**; see §19                 |
| S0 numeric/RNG profile    | FP & PRNG law                          | Engine      | x.y.z  | SHA-256     | **NO** (code contract)           | Changes are **breaking**; see §19                 |

**Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.

### 18.3 Normalisation & hashing — MUST

* **Number serialisation:** All floating-point values **MUST** be serialised using **shortest round-trip binary64** text (no locale/epsilon variants).
* **Key order:** Within each artefact, keys **MUST** be sorted **lexicographically** before serialisation.
* **Concatenation order:** Compute

  ```
  parameter_hash = H(
    bytes(θ) ||
    bytes(X-transform) ||
    bytes(X_default) ||
    bytes(MAX_ZTP_ZERO_ATTEMPTS) ||
    bytes(ztp_exhaustion_policy)
  )
  ```

  using the **exact artefact order** shown above (top→bottom).
* Any change to these bytes **must** produce a new `parameter_hash` and hence a new S4 run partition.

### 18.4 Change classes & scope — MUST

* **Policy changes** (θ, X transform/default, cap, policy) **participate** in `parameter_hash`; **not** breaking by themselves.
* **Code-contract changes** (labels/contexts, envelope field set, regime threshold/constants, partition keys, S0 numeric/PRNG law) **do not** flow through `parameter_hash`; they are **breaking** (see §19).
* **Upstream inputs (S1/S2/S3)** are authoritative **inputs** and **do not** participate in `parameter_hash` (they may change outcomes, but not the hash).

### 18.5 Provenance & auditability — MUST
For each governed artefact, the run manifest (outside S4 logs) **must** report: `{name, version, digest, owner, last_updated}`. Producers **must** ensure the values injected into S4 match those versions **byte-for-byte**.

### 18.6 Prohibitions — MUST NOT

* **MUST NOT** fetch governed values from environment variables, clocks, or non-versioned stores.
* **MUST NOT** compute `θ` or `X` from non-governed sources.

---

## 19) Compatibility & evolution

**Goal.** Define which changes are **additive-safe**, which are **breaking**, how to **version/tag** them, and how to **migrate** without ambiguity or data loss. S4 is logs-only; forward compatibility hinges on **stable labels, envelopes, partitions, and semantics**.

### 19.1 Change taxonomy — **MUST**

Classify each contemplated change into exactly one bucket:

1. **Policy change** (participates in `parameter_hash`): `θ`, `X` transform/default, `MAX_ZTP_ZERO_ATTEMPTS`, `ztp_exhaustion_policy`.
2. **Additive-safe schema extension**: optional payload fields with defaults; **no** change in meaning of existing fields.
3. **Breaking code-contract change**: labels/contexts, envelope structure, regime threshold/constants, partition keys, or meanings of existing fields.

### 19.2 Additive-safe changes — **MUST**

Allowed without breaking consumers, provided JSON-Schema marks fields **optional** with **default behaviour** and consumers are tolerant readers:

* Add an **optional** payload field to `poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`, or `ztp_final` (e.g., `reason`, `merchant_features_hash`, `cap_policy_version`).
* Add an **optional** boolean like `short_circuit?: true` to `ztp_final` (A=0 case), default `false`.
* Add **observability-only** counters/histograms (values-only, §13) not used in control flow.
* Tighten **validator corridors** (outside S4 producer; no producer behaviour change).

**MUST.** Preserve **existing meanings**; defaults **must** exactly reproduce prior behaviour. Keep **writer sort keys, partitions, labels, contexts** unchanged.

### 19.3 Breaking changes — **MUST NOT** (without a major)

Require a **major** bump + migration (see §19.5):

* Changing any **label/stream identifier** in §2A: `module`, `substream_label`, or `context:"ztp"`.
* Changing **partition keys** (currently `{seed, parameter_hash, run_id}`) or the **path↔embed equality** rule.
* Modifying the **envelope field set**, types, or semantics (`before/after/blocks/draws`).
* Changing the **regime threshold** (`λ<10` inversion → `ptrs`) or **PTRS constants**, or the **open-interval** rule for `u01`.
* Removing or altering the **`ztp_final`** contract (e.g., making it consuming, changing its role as the single acceptance record).
* Using **timestamps** or **file order** for ordering instead of counters.
* Altering **writer sort keys** per stream.

### 19.4 Deprecation policy — **MUST**

* Any additive field later removed is **breaking**.
* Announce deprecations as **"present but ignored"** for at least **one minor** release before removal; keep validators tolerant during the window.
* Record deprecations in the **Data Dictionary** and **artefact registry** changelog.

### 19.5 Migration playbook (for breaking changes) — **MUST**

1. **Version & tag.**

   * Bump the **module literal** (e.g., `1A.ztp_sampler.v2`).
   * Introduce **versioned schema anchors** by **suffixing anchor IDs with `@vN`** (e.g., `schemas.layer1.yaml#/rng/events/poisson_component@v2`). 
   * S4 normatively uses this suffix scheme; path-segment anchor versioning is **not used** by S4. 
   * The **Data Dictionary must pin** the exact anchor version per stream.

2. **Dual-write window (optional, recommended).**

   * Producers **MAY** dual-write v1 and v2 for a bounded window; the Dictionary **must** list both.
   * Validators pin to the intended version per run configuration.

3. **Cutover & freeze.**

   * After consumers confirm v2 ingestion, freeze v1 (no more writes) and mark it **deprecated** in dictionary/registry.

4. **Backfill policy.**

   * Backfills **must** run with the same **`parameter_hash`** inputs to guarantee byte-identical outcomes.
   * When the **code contract** changes, backfill under **new version tags** only (do **not** rewrite old partitions).

### 19.6 Coexistence rules — **MUST**

* Consumers **must** pin on one of: `(module, schema version)` or `(context, schema version)`; never "best-effort".
* Producers **must not** interleave v1 and v2 rows within the same `(seed, parameter_hash, run_id)` partition.

### 19.7 Consumer & validator impact — **MUST**

* **S6**: Reads only `ztp_final{K_target, lambda_extra, attempts, regime, exhausted?}`; tolerant to **optional** new fields; **must** ignore unknown keys.
* **Validators**: Tolerate additive fields; enforce invariants on the **core** set (attempt accounting, cardinalities, counters, existence/absence of `ztp_final`, cap semantics).
* **Downstream order**: S3 `candidate_rank` remains the sole authority—unchanged by S4 evolution.

### 19.8 Version signalling — **MUST**

* Expose `{module_version, schema_version}` in the S4 run manifest (outside logs) and **optionally** in `ztp_final` as **optional** payload fields for audit.
* Track `θ`/`X`/cap/policy versions in the **governance ledger** (§18) and tie them to `parameter_hash`.

### 19.9 Rollback stance — **MUST**

* Rollbacks **must not** overwrite or delete already-published partitions.
* After rollback, producers **must** resume writing with the previous stable `(module, schema)` pair; the Dictionary must point consumers accordingly.

### 19.10 Examples of safe vs breaking changes — **Informative**

* **Safe (additive):** Add optional `reason:"no_admissible"` to `ztp_final` (default absent).
* **Breaking:** Rename `context:"ztp"` → `"ztp_k"`; change `λ` threshold to 8; make `ztp_final` consuming.

---

## 20) Handoff to later states

### 20.1 Purpose.
Freeze exactly what S4 exports, who consumes it, and how downstream must interpret it. S4 is **logs-only**; it fixes a **target** foreign count and nothing else.

### 20.2 What S4 exports (authoritative for downstream).
From `ztp_final` for merchant *m*:

* `K_target : int≥0` — target foreign count (**authoritative outcome of S4**).
  - `≥1` on acceptance;
  - `=0` only via **A=0 short-circuit** or **exhaustion policy = "downgrade_domestic"**.
* `lambda_extra : float64` — intensity used (audit/diagnostics only; not a gate downstream).
* `attempts : int≥0` — number of Poisson attempts written by S4 (`0` iff short-circuit).
* `regime : "inversion"|"ptrs"` — Poisson sampler branch (closed enum).
* `exhausted? : bool` — present/`true` only for **cap + downgrade** outcome; omitted otherwise.
* Optional `reason : "no_admissible"` — present only for A=0 short-circuit (if the schema includes this optional field).

### 20.3 Who consumes S4 and how.

* **S6 (top-K selection)** — *MUST* read `ztp_final{K_target, lambda_extra, attempts, regime, exhausted?, reason?}` and combine with its own admissible foreign set of size `A`.
  - *Realisation rule (binding):* **`K_realized = min(K_target, A)`**.
  - If `K_target = 0` (short-circuit/downgrade): *MUST* skip top-K and continue domestic-only.
  - If `K_target > A` (shortfall): *MUST* select **all A**; **MAY** log a non-consuming `topk_shortfall{K_target, A}` marker **in S6**.
* **S7 (allocation / integerisation)** — *MUST NOT* infer any probability from S4 logs. It receives the set chosen by S6 and later allocates **N** across {home + chosen foreigns} (outside S4’s scope).
* **S8 (sequencing / IDs)** — unaffected by S4 semantics; it operates on per-country counts.
* **S9 (egress / handoff to 1B)** — S4 contributes no egress rows. S9’s `outlet_catalogue` contains **no** inter-country order; consumers recover order from S3 `candidate_rank`.

### 20.4 Authority boundaries (reaffirmed).

* S4 **never** encodes inter-country order; **S3 `candidate_rank`** remains the sole authority for cross-country order (home=0; contiguous).
* S4 **fixes only** the **target** count (`K_target`); S6/S7/S8 own *which* countries, *how many per country*, and *per-country sequences* respectively.
* S4’s `lambda_extra`, `attempts`, `regime` are **audit surfaces**, not consumer gates.

### 20.5 Consumer pitfalls (MUST NOT).

* *MUST NOT* derive **`K_target`** by counting Poisson attempts or rejections; the **only** authoritative target is `ztp_final.K_target`. *(S6 later realises `K_realized = min(K_target, A)`.)*
* *MUST NOT* treat `lambda_extra` as a probabilistic weight for later selection.
* *MUST NOT* exceed `A` when realising K (enforced in **S6 (Top-K selection)** via `min(K_target, A)`).
* *MUST NOT* process a merchant **without a `ztp_final`** (e.g., `NUMERIC_INVALID` or cap + policy=`"abort"`).

### 20.6 Lineage continuity (MUST).
All downstream states (S6+) *must* carry forward `{seed, parameter_hash, run_id}` as read from S4; they *must not* reinterpret or recompute `lambda_extra` or `regime`.

---

## 21) Glossary & closed vocabularies — **Normative (terms)** / **Informative (glossary)**

### 21.1 Closed vocabularies (enumerations) — MUST

* `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` — governed policy when the zero-draw cap is hit.
* `regime ∈ {"inversion","ptrs"}` — Poisson sampler branch; set once per merchant from the λ threshold.
* `context == "ztp"` — fixed context string on all S4 events.
* `module == "1A.ztp_sampler"`, `substream_label == "poisson_component"` — fixed label literals (see §2A).
* `reason ∈ {"no_admissible"}` — optional `ztp_final` payload enum for A=0 short-circuit. 
  *(Schema presence.)* The `reason` field is optional and **absent in this schema version**; adding it in a later schema revision is **additive-safe**; this document fixes the vocabulary in advance.

### 21.2 Terms (precise meanings) — MUST/SHOULD

* **ZTP (Zero-Truncated Poisson)** — Distribution of `Y | (Y≥1)` where `Y~Poisson(λ)`. Realised by rejecting 0s from Poisson draws.
* **PTRS** — Poisson sampling regime for large λ (two uniforms + geometric attempts; constants/threshold fixed).
* **Inversion** — Poisson sampling regime for small λ; consumes exactly `K+1` uniforms for result `K`.
* **`attempt` (int≥1)** — 1-based index of a Poisson draw for a merchant; strictly increasing and contiguous on accepted/capped paths.
* **`attempts` (int≥0)** — on `ztp_final`/cap rows: equals last attempt index; **0 only for A=0 short-circuit**.
* **`draws` (decimal-u128 string)** — actual uniforms consumed by the event (consuming rows only).
* **`blocks` (u64)** — counter delta = **`after − before`** (consuming rows only).
* **`before` / `after` (u128)** — PRNG counters that prove order; **timestamps are observational only**.
* **`K_target` (int≥0)** — S4’s authoritative **target** foreign count: result of ZTP acceptance (`≥1`) or governed `0` (A=0 / downgrade).
* **`K_realized` (int≥0)** — realised selection size used by **S6**: `min(K_target, A)`.
* **`A` (int≥0)** — size of admissible foreign set from S3 (foreigns only; home excluded).
* **`exhausted` (bool)** — `true` only when the cap is hit and policy=`"downgrade_domestic"`; omitted otherwise.
* **`λ_extra` (float64 > 0)** — intensity for extra-country count; computed from log-link `η` in binary64 with fixed order.
* **`parameter_hash` (hex64)** — run’s parameter set hash; partitions S4 inputs/outputs with `seed`/`run_id`.
* **`manifest_fingerprint` (hex64)** — run fingerprint used by egress/validation (S4 writes logs only).

### 21.3 Notational conventions — SHOULD

* `log` denotes natural logarithm.
* Where float comparisons affect control flow (λ threshold), comparisons are exact in binary64 (`λ < 10` ⇒ inversion; else PTRS).
* All sets/maps over ISO2 codes are **order-free** unless explicitly sorted/ranked by a defined key.

### 21.4 Prohibitions (terminology drift) — MUST NOT

* *MUST NOT* call `K_target` "realised K" in S4; **only S6** realises K vis-à-vis `A`.
* *MUST NOT* use "probability" for `base_weight_dp` (priors live outside S4); S4 has no priors and no Dirichlet.
* *MUST NOT* use "order" to describe any S4 output; cross-country order belongs exclusively to S3 `candidate_rank`.

---