# S7 — Integer Allocation Across Legal Country Set (Layer 1 · Segment 1A)

# 1) Intent, scope, non-goals **(Binding)**

**Intent (what S7 does).**
S7 takes **N** from S2, the **ordered legal country set** from S3, **currency→country weights** from S5, and the **selected foreign membership** from S6, then produces **deterministic integer counts per country** that **sum exactly to N**. It records a **`residual_rank`** for the largest-remainder rounding step. S7 **does not** create or persist any inter-country order; consumers continue to use S3’s `candidate_rank` as the **sole authority** for cross-country order.    

**Scope (what S7 covers).**
S7 SHALL:

* Allocate counts over the **domain = {home} ∪ (S6-selected foreigns)**, respecting S3’s total, contiguous **`candidate_rank`** (home at rank 0). **Order authority remains S3.** 
* Use **S5 `ccy_country_weights_cache`** as the weight authority; S7 MAY only **ephemerally** restrict/renormalise it to the domain (no persistence). 
* Treat **S2 `nb_final.n_outlets → N`** and **S4 `ztp_final.K_target`** as read-only facts (no reinterpretation). 
* Emit one deterministic **`rng_event.residual_rank`** row per domain country (draws=`"0"`; blocks=0), with a trace append after each event. 
* Default to **deterministic-only** operation (no RNG consumption). A feature-flagged **Dirichlet lane** MAY exist (policy OFF by default) and is specified elsewhere in §4.4.

**Non-goals (what S7 MUST NOT do).**
S7 MUST NOT:

* **Pick countries** (that is S6), **define or encode inter-country order** (that is S3), or **persist weights** (that is S5).   
* **Materialise sites or within-country site order** (that is S8; egress `outlet_catalogue` explicitly does **not** encode cross-country order). 
* **Alter** S2’s **N** or S4’s **`K_target`**, or reinterpret any S4 audit fields beyond reading `K_target`. 
* **Write a counts dataset** as a new authority surface by default; counts flow forward to S8. (Any future S7 counts cache would require a dictionary ID and schema anchor before use.) 

**Outcome (success criteria).**
On completion, for every merchant S7 provides: (i) per-country **integer counts** that sum to **N** over the domain; (ii) a complete set of **`residual_rank`** events consistent with the deterministic largest-remainder rounding; and (iii) no new order or weight surfaces introduced—**S3/S5 remain the authorities**.   

---

# 2) Interfaces & “no re-derive” boundaries **(Binding)**

**2.1 Upstream authorities S7 MUST trust (read-side contracts).**
S7 reads **only** the artefacts below, at the stated `$ref` anchors and partitions. Embedded lineage fields (where present) **MUST** byte-equal the path tokens (path↔embed equality).

* **Domestic count (fact):** `rng_event_nb_final` → `schemas.layer1.yaml#/rng/events/nb_final`, partitioned by `{seed, parameter_hash, run_id}`. **Exactly one** per resolved merchant; `n_outlets (N) ≥ 2`; **non-consuming** envelope. 
* **Foreign target (fact):** `rng_event_ztp_final` → `schemas.layer1.yaml#/rng/events/ztp_final`, partitioned by `{seed, parameter_hash, run_id}`. **Exactly one** per resolved merchant **unless** S4 aborted; S7 treats only `K_target` as a decision fact (other fields audit-only).
* **Inter-country order & domain base:** `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set`, partitioned by `[parameter_hash]`. **Sole authority** for inter-country order; rank is **total & contiguous** per merchant with `home=0`. 
* **Weights authority:** `ccy_country_weights_cache` → `schemas.1A.yaml#/prep/ccy_country_weights_cache`, partitioned by `[parameter_hash]`. Group-sum per currency **= 1 ± 1e-6**; **no order is implied**. **Gate:** S7 MUST read only when **S5 PASS** is present for the same `parameter_hash`.
* **Selected-foreign membership (optional convenience):** `s6_membership` → `schemas.1A.yaml#/s6/membership`, partitioned by `{seed, parameter_hash}`. **Gate:** S7 MAY read **only** if **S6 PASS** exists for the same `{seed, parameter_hash}`. When absent, S7 **MUST** reconstruct membership from `rng_event.gumbel_key` (selected rows). **Order remains from S3.**
* **Membership via events (authoritative log):** `rng_event_gumbel_key` → `schemas.layer1.yaml#/rng/events/gumbel_key`, partitioned by `{seed, parameter_hash, run_id}`; single-uniform budget (`blocks=1`, `draws="1"`); if `selected=true` then `selection_order ∈ [1..K]`. Zero-weights **must** carry `key:null` and can’t be selected. 
* **Merchant→currency map (if produced):** `merchant_currency` → `schemas.1A.yaml#/prep/merchant_currency`, partitioned by `[parameter_hash]`; **PK `(merchant_id)`**; κₘ in ISO-4217. If present, S7 **MUST NOT** override it. 

**2.2 Downstream consumers (write-side promises).**

* **S8 `outlet_catalogue`** consumes S7’s **per-country integer counts** to materialise sites. Egress **does NOT encode inter-country order**; consumers **MUST** join S3 `candidate_rank`. Egress remains gated by the layer **fingerprint PASS**; S7 does not alter that gate.
* **RNG logs:** S7 emits only its own event family (`residual_rank`; see §5/§6) and appends one cumulative `rng_trace_log` row **after each** event; readers treat event files as **set-semantics**. 

**2.3 “No re-derive” boundaries (hard prohibitions & guarantees).**

* **Order authority:** S7 **MUST NOT** create, persist, or imply any inter-country order. **S3 `candidate_rank` is sole authority**; S8 and any consumer **MUST** continue to join it. 
* **Weights authority:** S7 **MUST NOT** persist weights or alter S5 values. Any subset/renormalisation used for allocation is **ephemeral** and **not written**. 
* **S4 facts:** S7 **MUST NOT** reinterpret S4 fields beyond reading `K_target`. `lambda_extra`, `regime`, `attempts`, `exhausted?` remain **audit-only**. 
* **Membership authority:** If `s6_membership` is read, S7 treats it as the membership set but **MUST** still obtain order from S3; if not read, S7 reconstructs membership **only** from `rng_event.gumbel_key` selection flags (or counter-replay per S6 rules), **never** from S7-invented logic.
* **Egress scope:** By default, S7 **MUST NOT** publish a new counts dataset as an authority surface; counts flow into S8. Any future S7 counts cache would require a Dictionary ID and schema anchor. 

**2.4 Lineage, partitions, and gates (enforcement summary).**

* **Partitions:** events/logs under `{seed, parameter_hash, run_id}`; parameter-scoped tables under `[parameter_hash]`. Path↔embed equality is binding.
* **PASS discipline:** **S5 PASS** required before reading weights; **S6 PASS** required before reading any S6 convenience surface; layer **egress PASS** governs `outlet_catalogue`. **No PASS → no read.**

---

# 3) Inputs — datasets, schemas, partitions & gates **(Binding)**

**3.1 Required inputs (ID → `$ref`, partitions, what S7 uses).**

* **Domestic count (fact):** `rng_event_nb_final` → `schemas.layer1.yaml#/rng/events/nb_final` — **partitions:** `{seed, parameter_hash, run_id}`. S7 reads **`n_outlets (N) ≥ 2`** as the total to allocate; one record per resolved merchant.  
* **Order & domain base (sole authority):** `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set` — **partitions:** `[parameter_hash]`. Guarantees a **total, contiguous** `candidate_rank` with **home=0**; S7 reads only order + admissible set.  
* **Foreign-target fact (for consistency checks):** `rng_event_ztp_final` → `schemas.layer1.yaml#/rng/events/ztp_final` — **partitions:** `{seed, parameter_hash, run_id}`. S7 may assert `|membership| = min(K_target, |Eligible|)`; other fields remain audit-only. 
* **Weights authority:** `ccy_country_weights_cache` → `schemas.1A.yaml#/prep/ccy_country_weights_cache` — **partitions:** `[parameter_hash]`. Per-currency group sum **= 1 ± 1e-6**; S7 **ephemerally** restricts/renormalises to the S7 domain (no persistence). **Gate:** **S5 PASS required.**  

**3.2 Conditional / optional inputs.**

* **Selected-foreign membership (convenience only):** `s6_membership` → `schemas.1A.yaml#/s6/membership` — **partitions:** `{seed, parameter_hash}`. **Gate:** **S6 PASS** for same `{seed, parameter_hash}`. If absent, S7 reconstructs membership from `rng_event_gumbel_key` selections; **order still comes from S3.**  
* **Membership via events (authoritative log when needed):** `rng_event_gumbel_key` → `schemas.layer1.yaml#/rng/events/gumbel_key` — **partitions:** `{seed, parameter_hash, run_id}`. Used only when `s6_membership` is not emitted. 
* **Merchant→currency map (if produced):** `merchant_currency` → `schemas.1A.yaml#/prep/merchant_currency` — **partitions:** `[parameter_hash]`. If present, S7 **MUST NOT** override it when resolving the merchant’s currency for the S5 weight vector. 

**3.3 Gates S7 MUST verify before reading.**

* **S6 PASS (convenience reads):** To read any S6-derived dataset (e.g., `s6_membership`), S7 verifies the **S6 receipt** at `data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/(S6_VALIDATION.json, _passed.flag)` and checks the flag’s content hash. **No PASS → no read.** 
* **S5 PASS (weights):** To read `ccy_country_weights_cache`, S7 honours S5’s **parameter-scoped PASS** sidecar (`S5_VALIDATION.json` + `_passed.flag`) colocated under the weights partition. **No PASS → no read.** 

**3.4 Partition keys, lineage, and equality (enforcement).**

* **Events/logs** are partitioned by `{seed, parameter_hash, run_id}`; **parameter-scoped tables** by `[parameter_hash]`. Embedded lineage (where present) **MUST byte-equal** path tokens (path↔embed equality). 
* **Core RNG logs** (`rng_audit_log`, `rng_trace_log`) exist under the same event partitions and are used by validators; S7 does not need to read them to allocate counts. 

**3.5 FK & encoding baselines (domains).**

* **ISO / currency codes:** uppercase **ISO-3166-1 alpha-2** for `country_iso`, uppercase **ISO-4217** for `currency` across all inputs (FKs enforced where declared). 
* **Deprecated surfaces (MUST NOT read):** `country_set` (legacy, seed+parameter partitions) is **not** an order authority; S7 **MUST NOT** consume it. Use `s3_candidate_set` instead. 

---

# 4) Configuration & policy **(Binding)**

**4.1 Residual quantisation precision (binding).**
S7 **MUST** quantise residuals at **`dp_resid = 8`** **before** any tie-breaks or ranking. Quantisation uses the S0 numeric profile (binary64, RNE). This mirrors the binding residual-dp discipline already used for integerisation elsewhere. 

**4.2 Decimal rounding algorithm (binding).**
Quantise via the fixed **ties-to-even** decimal rule: let `s = 10^dp_resid`; compute `q = round_RNE(value * s) / s` in binary64, then use `q` for all downstream comparisons and ordering. 

**4.3 Deterministic tie-break order (binding).**
When ranking residuals to distribute the remainder, apply a **total** and **stable** order:

1. **Residual** (quantised) **descending**; 2) **ISO-3166-1 alpha-2** code **A→Z**; 3) **`candidate_rank` ascending**; 4) stable input index. Persist `residual_rank` as the **1-based** position in this order. 

**4.4 Optional bounds policy (Hamilton-style) (feature-flag; default: OFF).**
If enabled, S7 enforces per-country integer **floors/ceilings** and uses a bounded Hamilton procedure with a hard feasibility guard `ΣL_i ≤ N ≤ ΣU_i`; capacities restrict bumps and residual ranking is applied only to countries with remaining capacity. If infeasible at any step, S7 **MUST** fail the merchant (no partial outputs).

**4.5 Logging mode (binding).**
S7 **MUST** emit one **`rng_event.residual_rank`** per `(merchant_id, country_iso)` in the domain, with **non-consuming** envelope (i.e., `draws="0"`, `blocks=0`) and then append **exactly one** cumulative **`rng_trace_log`** row **after each** event append. Event files are **set-semantics** (readers must not assume file order).

**4.6 RNG lane switch (Dirichlet) (feature-flag; default: OFF).**
If the **Dirichlet lane** is enabled by policy, S7 **MAY** emit exactly one `rng_event.dirichlet_gamma_vector` per merchant (arrays for `{alpha[], gamma_raw[], weights[]}`) in addition to §4.5 logs. α-vector formation **MUST** produce strictly positive α and be **mean-anchored** to the S5 weights restricted to the S7 domain (policy defines α₀; this spec requires α>0 and domain-normalisation only). When this lane is **OFF** (default), S7 remains **deterministic-only** and **MUST NOT** consume RNG for allocation. 

**4.7 Pass-through of upstream authorities (binding).**
S7 **MUST NOT** persist any new weight surface and **MUST NOT** encode or imply inter-country order; any subset/renormalisation of S5 weights is **ephemeral** to the allocation step, and inter-country order **always** comes from S3 `candidate_rank`.

**4.8 Gates inherited by configuration (binding).**
Reading any S6 convenience surface requires a **valid S6 PASS**; reading S5 weights requires a **valid S5 PASS**. **No PASS → no read.** (These gates are enforced even when S7 runs deterministic-only.)

**4.9 Enumerations & labels (binding, listed in Appendix A).**
`module`, `substream_label`, error codes, and tie-break keys are frozen literals. Producers **MUST** use the Appendix A values when emitting `rng_event.residual_rank` (and `dirichlet_gamma_vector` if enabled). (See also §2.4 for partition/lineage rules.) 

---

# 5) Outputs — datasets/logs & contracts **(Binding)**

**5.1 Event logs S7 MUST emit.**

* **`rng_event.residual_rank`** — one row **per (`merchant_id`, `country_iso`)** in the S7 domain; **non-consuming** envelope (**`draws="0"`, `blocks=0`**); **partition:** `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; **schema:** `schemas.layer1.yaml#/rng/events/residual_rank`. Persist `residual∈[0,1)` and **`residual_rank≥1`** (1=largest). After **each** event append, S7 **MUST** append exactly one cumulative row to **`rng_trace_log`** for `(module, substream_label)`. **Module/Substream (normative):** `module="1A.integerisation"`, `substream_label="residual_rank"`.
  *Envelope fields follow the layer law: `ts_utc` is RFC3339 with **exactly 6 fractional digits**, lineage fields present, and path↔embed equality holds.* 

* **(Feature-flag lane; default OFF)** **`rng_event.dirichlet_gamma_vector`** — **at most one** row **per merchant** when Dirichlet allocation is enabled by policy; **partition:** `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; **schema:** `schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector`. Arrays `{country_isos, alpha, gamma_raw, weights}` **MUST** be equal length; `weights` sum to **1 ± 1e-6**. **Module/Substream (normative):** `module="1A.dirichlet_allocator"`, `substream_label="dirichlet_gamma_vector"`. **S7 does not emit** per-component `gamma_component` events.
  *Order of `country_isos` when S7 produces this event:* **home first, then foreigns in S3 `candidate_rank` order filtered to membership** (supersedes the current help-text wording; see §12 for the doc patch). 

**5.2 Core RNG logs S7 MUST update.**

* **`rng_trace_log`** — append **exactly one** cumulative row **after each S7 event append**; partitions `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; **schema:** `schemas.layer1.yaml#/rng/core/rng_trace_log`. Totals reconcile (`events_total`, `draws_total`, `blocks_total`). **Reader semantics are set-based** (no reliance on file order). 

**5.3 Datasets S7 MUST/MUST NOT publish.**

* **MUST NOT** publish any **inter-country order** surface. Egress `outlet_catalogue` **does not encode** cross-country order; consumers **MUST** join S3 `candidate_rank`. 
* **MUST NOT** persist a new **weights** table. S5 remains the single authority. 
* **No counts table by default.** Integer counts flow forward into S8; any future S7 counts cache would require a **Dictionary ID** and **schema anchor** before use. (Note: the only registered counts table today is **`s3_integerised_counts`**, produced by S3, not S7.) 

**5.4 Partitions, lineage & equality (enforcement).**

* All S7 events/logs are partitioned by **`{seed, parameter_hash, run_id}`**; embedded lineage (when present) **MUST byte-equal** the path tokens. **`ts_utc`** MUST match the layer pattern with **6-digit microseconds**. **Hard-fail** on mismatches.

**5.5 Module/substream literals (frozen).**

* `rng_event.residual_rank` → `module="1A.integerisation"`, `substream_label="residual_rank"`. (Dictionary shows producer lineage **1A.integerisation**.) 
* `rng_event.dirichlet_gamma_vector` (if enabled) → `module="1A.dirichlet_allocator"`, `substream_label="dirichlet_gamma_vector"`. (Dictionary shows producer lineage **1A.dirichlet_allocator**.) 

**5.6 Publishing discipline & retention.**

* **Atomic publish:** stage → fsync → **atomic rename** into the Dictionary path; no partials. (Same discipline as S3/S6; inherited layer convention.) 
* **Retention:** event streams (e.g., `residual_rank`, `dirichlet_gamma_vector`) keep **180 days**; core RNG logs keep **365 days**.

**5.7 Prohibitions (isolation).**
S7 writes **only** the families above. It **MUST NOT** write S1–S6 event families (e.g., `gumbel_key`, `poisson_component`, `nb_final`, `ztp_*`) nor any S8 egress. Those are owned by their respective states. 

---

# 6) Deterministic processing specification — no pseudocode **(Binding)**

**6.0 Pre-flight (per merchant).**
S7 MUST confirm presence/schema-pass of: `nb_final` (read `N`), `s3_candidate_set` (order/domain base), `ccy_country_weights_cache` (weights), and either `s6_membership` (if emitted, with S6 PASS) **or** sufficient S6 RNG events to reconstruct membership; embedded lineage MUST byte-equal the path tokens. **No PASS → no read.**   

---

**6.1 Domain assembly (ordered legal set).**
a) Start from **S3** candidates for the merchant; this is the **sole** inter-country order authority (`candidate_rank` total & contiguous; `home=0`). 
b) Membership of foreigns comes from **S6**: if the `s6_membership` convenience dataset is emitted (and PASSed), use it; else reconstruct **exactly** from S6 RNG events (selected flags in `gumbel_key`, or counter-replay per S6 rules). In all cases, **order remains from S3**.  
c) Define the **domain** $D$ = {home} ∪ (S6-selected foreigns) as an **ordered set** keyed by S3 `candidate_rank` (home first). If $K_{target}=0$ or S6 selected set is empty, set $D={\text{home}}$.  

---

**6.2 Share vector for allocation (ephemeral; not persisted).**
a) Resolve the merchant’s currency (from S5, e.g., `merchant_currency` if produced); read the **weights authority** `ccy_country_weights_cache`. 
b) **Restrict** the S5 weight vector to countries in (D) and **ephemerally renormalise** (binary64, RNE) so that $\sum_{i\in D} s_i = 1.0$ (subject to rounding). **Do not persist** the restricted or renormalised vector. 
c) **Feasibility guard:** if $\sum_{i\in D} s_i = 0$ (should not occur given S5’s per-currency $\sum=1$), S7 **MUST** hard-fail this merchant (`E_ZERO_SUPPORT`). 

---

**6.3 Fractional targets (numeric profile inherited from S0).**
For each $i\in D$, compute $a_i = N \cdot s_i$ in **binary64 / RNE** (S0 numeric law). No stochasticity is involved. 

---

**6.4 Floor step and remainder law.**
Set $b_i = \lfloor a_i \rfloor$ (integer floors). Define the remainder $d = N - \sum_{i\in D} b_i$. It MUST hold that $0 \le d < |D|$. 

---

**6.5 Residuals and quantisation (binding dp).**
Define residuals $r_i = a_i - b_i$. Quantise each residual to **`dp_resid = 8`** using the S0 rounding rule (ties-to-even) and carry the quantised value forward for **all** downstream comparisons and logging (the unquantised residual MUST NOT be used for any ordering). Persist this quantised residual in the S7 event payload. 

---

**6.6 Deterministic bump rule (no new order is created).**
Distribute the remainder by awarding **+1** to exactly **$d$** countries, using the **total order defined in §4.3** (residual first, then the declared tie-breakers). The resulting per-country counts are $c_i = b_i + \mathbf{1}{i\ \text{is in the top } d}$.
**Persist** a `residual_rank` for every $i\in D$ as the **1-based** position in that total order (1 = highest residual after quantisation). **Inter-country order remains S3 `candidate_rank`; S7 writes no order surface.** 

---

**6.7 Optional bounded variant (feature-flag; default OFF).**
If a **bounds policy** is configured, S7 enforces integer floors/ceilings $L_i \le c_i \le U_i$:
a) **Feasibility check**: $\sum L_i \le N \le \sum U_i$; otherwise **hard-fail** the merchant (`E_BOUNDS_INFEASIBLE`).
b) Apply the floor step $b_i \leftarrow \max(b_i, L_i)$; recompute $d$.
c) During the bump, only countries with remaining **capacity** $b_i < U_i$ participate in the residual order; ties resolved by the same total order.
This variant MUST NOT change any other contract (no new datasets, no new order surface). 

---

**6.8 Event & trace discipline (write-side).**
a) Emit exactly **one** `rng_event.residual_rank` **per (`merchant_id`, `country_iso`) in $D$**, with **non-consuming** envelope (`draws="0"`, `blocks=0`).
b) After **each** event append, emit **one** cumulative `rng_trace_log` row for `(module="1A.integerisation", substream_label="residual_rank")`.
c) If the **Dirichlet lane** is enabled by policy, S7 MAY also emit exactly one `dirichlet_gamma_vector` **per merchant**; otherwise it MUST NOT consume RNG. Event files are **set-semantics**; readers MUST NOT rely on row/file order.  

---

**6.9 Degenerate/single-country path.**
If $D={\text{home}}$: set $s_{\text{home}}=1$, $a_{\text{home}}=N$, $b_{\text{home}}=N$, $d=0$, $c_{\text{home}}=N$. Emit a single `residual_rank` for home with residual **0.00000000** and **rank=1**; no events are emitted for absent countries. 

---

**6.10 Success conditions (checked again in §7/§9).**

* **Sum law:** $\sum_{i\in D} c_i = N$; each $c_i \ge 0$.
* **Proximity law:** $|c_i - N\cdot s_i| \le 1$ for all $i\in D$.
* **Authority boundaries:** S3 `candidate_rank` remains the only cross-country order; S5 remains the only weights authority; S7 wrote **no** new order/weight surface.  

---

# 7) Invariants & integrity constraints **(Binding)**

**7.1 Allocation laws (must hold per merchant).**

* **Sum law:** The per-country integer counts **MUST** sum to **`N`** and each **`count_i ≥ 0`**.
* **Proximity law:** For every country in the S7 domain, **`|count_i − N·s_i| ≤ 1`** (Largest-Remainder property under fixed dp). 
* **Bounds variant (if enabled):** If floors/ceilings are in force, S7 **MUST** satisfy **`Σ L_i ≤ N ≤ Σ U_i`** and **`L_i ≤ count_i ≤ U_i`**; otherwise S7 **FAILS** the merchant. 

**7.2 Domain & order authority.**

* **Domain law:** S7 allocates only over **`D = {home} ∪ (S6-selected foreigns)`**; when `K_target=0` or the foreign set is empty, S7 **MUST** allocate **all `N`** to **home**. 
* **Order authority separation:** S3’s `s3_candidate_set.candidate_rank` remains the **sole** inter-country order; S7 **MUST NOT** create, encode, or imply any cross-country order. Downstream consumers (incl. `outlet_catalogue`) **MUST** join S3 for order.

**7.3 Relationship to S4/S6 facts.**

* **Target vs. realised size:** S6 realises the membership size **`K_realized = min(K_target, |Eligible|)`**; S7 **MUST** accept that membership as given and **MUST NOT** reinterpret S4 fields beyond reading `K_target`.
* **No weight persistence:** S5 `ccy_country_weights_cache` is the weight authority; any restriction/renormalisation used by S7 is **ephemeral** and **MUST NOT** be persisted. **No PASS → no read** for S5 surfaces. 

**7.4 Residual & ranking integrity.**

* **Residual range:** The residual recorded per country is in **`[0,1)`** (exclusive of 1.0) and is the **quantised** value used for ordering. 
* **Quantisation discipline:** Residuals **MUST** be quantised to **`dp_resid = 8`** under binary64 RNE **before** any ordering. 
* **Total & contiguous residual order:** `residual_rank` is a **1-based**, contiguous ranking within the domain; ties **MUST** break by **ISO A→Z** (then S3 `candidate_rank`), yielding a total, stable order consistent with S3. 

**7.5 Event/logging invariants.**

* **Per-domain coverage:** S7 **MUST** emit exactly **one** `rng_event.residual_rank` per `(merchant_id, country_iso)` in the S7 domain. (Non-consuming: `draws="0"`, `blocks=0`.) 
* **Trace cadence:** After **each** S7 event append, **exactly one** cumulative `rng_trace_log` row is appended; totals reconcile for the `(module, substream_label)` key. 
* **Envelope legality:** All S7 RNG events carry the layer envelope with **`ts_utc`** in RFC-3339 UTC with **exactly 6 fractional digits**, and counters satisfy the **blocks = after − before** identity. 

**7.6 Partitions, lineage & path discipline.**

* **Partition law:** S7 events/logs are under `{seed, parameter_hash, run_id}`; any embedded lineage fields **MUST** byte-equal the path tokens (**path↔embed equality**). Parameter-scoped tables (if any) are under `[parameter_hash]`. 
* **Set semantics:** Readers **MUST NOT** rely on file order for S7 event streams; semantics are set-based. (Ordering for joins comes from S3.) 

**7.7 Determinism & idempotence.**

* With identical `{seed, parameter_hash, run_id}` and identical upstream inputs, S7 **MUST** produce byte-identical outputs (events and values). Any input change **requires** a new `run_id` (see §10). 

**7.8 Gating & consumption.**

* **Upstream gates:** To read any S6 convenience surface, S7 **MUST** verify the **S6 PASS** receipt for the same `{seed, parameter_hash}`; to read S5 weights, S7 **MUST** verify S5 PASS for the same `parameter_hash`. **No PASS → no read.** 
* **Downstream gate:** S8 **MUST** verify the presence of the complete S7 residual-rank event set and continue enforcing the layer’s egress PASS when materialising `outlet_catalogue`. 

**7.9 Prohibitions (must never occur).**

* S7 **MUST NOT** publish a new inter-country order surface; **MUST NOT** persist a new weights table; and **MUST NOT** emit S1–S6 event families. (S7 writes only its own event family/families per §5.)

---

# 8) Error handling, edge cases & degrade ladder **(Binding)**

**Purpose.** Define what S7 must treat as **errors** (hard-fail per merchant / run), what counts as **deterministic non-errors** (degrade but valid), and what **gates** must be enforced before any read/write.

---

## 8.1 Pre-flight gates (hard requirements)

S7 **MUST** fail a merchant **before compute** if any of the following are missing or invalid:

* **PASS receipts:** Attempt to read an S6 convenience surface without a valid **S6 PASS** for the same `{seed, parameter_hash}`; or attempt to read S5 weights without a valid **S5 PASS** for the same `parameter_hash`. **No PASS → no read.** → `E_PASS_GATE_MISSING`.
* **Schema/lineage:** Any required input fails its `$ref` schema or **path↔embed equality** (embedded lineage fields differ from partition tokens). → `E_SCHEMA_INVALID` / `E_PATH_EMBED_MISMATCH`.
* **Authority presence:** `s3_candidate_set` not present/valid (total, contiguous `candidate_rank`, `home=0`) or S4/S2 fact streams (`ztp_final`, `nb_final`) absent/invalid. → `E_UPSTREAM_MISSING`.

---

## 8.2 Domain & membership edge cases

* **Deterministic single-country domain (non-error):** If `K_target=0` **or** the S6-selected foreign set is empty, S7 **MUST** allocate all **`N`** to **home** and still emit one `residual_rank` (residual=0, rank=1). → `DEG_SINGLE_COUNTRY` (diagnostic only). 
* **Membership not a subset of S3 (error):** If any S6-selected foreign ISO is not in S3’s admissible set for the merchant, S7 **MUST** fail the merchant (authority breach). → `E_S6_NOT_SUBSET_S3`. 

---

## 8.3 Weight support & zero-mass checks

* **Zero support on domain (error):** If the S5 weight vector, **restricted to the S7 domain**, sums to 0 (should not occur given per-currency Σ=1), S7 **MUST** hard-fail the merchant and produce no outputs. → `E_ZERO_SUPPORT`. 
* **Renormalisation (non-error):** Restrict-and-renormalise to domain (ephemeral) is allowed and **MUST NOT** be persisted by S7. (S5 remains the weight authority.) 

---

## 8.4 Bounds policy variant (feature-flag; default OFF)

When the **bounded Hamilton** variant is enabled:

* **Feasibility:** If `Σ L_i > N` or `Σ U_i < N`, S7 **MUST** fail the merchant; no partial writes. → `E_BOUNDS_INFEASIBLE`.
* **Capacity during bump:** During remainder distribution, only countries with `b_i < U_i` participate; if capacity exhaustion prevents allocating all `d` units, S7 **MUST** fail the merchant. → `E_BOUNDS_CAP_EXHAUSTED`.
* **No new authorities:** This variant **MUST NOT** create any new weight/order surface. (S3/S5 remain authorities.) 

---

## 8.5 RNG isolation & accounting (applies even when deterministic)

* **Residual-rank events:** `rng_event.residual_rank` **MUST** be **non-consuming** (`draws="0"`, `blocks=0`). Missing or malformed envelope/lineage is **FAIL**. → `E_RNG_ENVELOPE`. 
* **Trace cadence:** After **each** S7 event append, append **exactly one** cumulative `rng_trace_log` row; totals reconcile for `(module, substream_label)`. Missing/misaligned trace rows are **FAIL**. → `RNG_ACCOUNTING_FAIL`. 
* **Dirichlet lane (if enabled):** Arrays `{country_isos, alpha, gamma_raw, weights}` must be equal length; `alpha_i>0`; Σ`weights`=1±1e-6; otherwise **FAIL**. → `E_DIRICHLET_SHAPE` / `E_DIRICHLET_NONPOS` / `E_DIRICHLET_SUM`. (Lane is **OFF by default**.) 

---

## 8.6 Integerisation integrity

* **Sum law breach:** If Σ counts ≠ **N** or any `count_i<0`, S7 **MUST** fail the merchant. → `INTEGER_SUM_MISMATCH`.
* **Ranking discipline:** Residuals **MUST** be quantised at `dp_resid=8` **before** ordering; `residual_rank` is 1-based, total & contiguous. Violations are **FAIL**. → `E_RESIDUAL_QUANTISATION`. 

---

## 8.7 I/O integrity & publish atomics

* **Atomic publish:** Writers **MUST** stage → fsync → **atomic rename** into Dictionary paths; no partials. Any short write, partial instance, or partition mismatch is **FAIL**. → `E_IO_ATOMICS`. 
* **Set semantics:** Readers **MUST NOT** rely on file order for event streams. (Order for joins continues to come from S3.) 

---

## 8.8 Per-merchant outcomes (closed set)

* **`SUCCESS`** — Merchant processed; all invariants in §7 hold; events logged; ready for S8 consumption once layer egress PASS is satisfied. 
* **`STRUCTURAL_FAIL`** — Any §8.1/§8.2/§8.7 failure (schema/lineage/gate/authority/IO).
* **`INTEGERISATION_FAIL`** — Any §8.6 breach (sum law, residual quantisation/ranking discipline).
* **`RNG_ACCOUNTING_FAIL`** — Any §8.5 envelope/trace reconciliation breach. 
* **`BOUNDS_FAIL`** — Any §8.4 infeasibility or capacity-exhaustion when bounds are enabled.

*(Numeric exit codes, if used by your runner, can be enumerated in Appendix A with their textual labels; this spec fixes the meanings.)*

---

## 8.9 Degrade ladder (non-error determinism)

S7 recognises the following **deterministic** conditions as **valid**, non-error outcomes. They **MUST** still satisfy §7 invariants and logging discipline:

* **`DEG_SINGLE_COUNTRY`** — Domain = {home}; all `N` allocated to home; one `residual_rank` emitted (residual=0, rank=1). 
* **`DEG_ZERO_REMAINDER`** — `d=0`; no bumps applied; residuals/ranks still logged for transparency.
* **`DEG_TIES_RESOLVED`** — Residual ties resolved by the binding tie-break order (ISO A→Z, then `candidate_rank`). *(Diagnostic only; not emitted in payloads.)*

---

## 8.10 Envelope timestamp & lineage strictness (reminder)

All S7 RNG events **MUST** carry `ts_utc` in RFC-3339 **UTC** with **exactly 6 fractional digits**, and embedded `{seed, parameter_hash, run_id, manifest_fingerprint}` **MUST** byte-equal the partition tokens. → Mismatch **FAIL**. 

---

# 9) Validation battery & PASS gate **(Binding)**

**Purpose.** Prove that S7’s outputs are structurally correct, authority-compliant, and byte-replayable **before** S8 consumes them. S7 does **not** introduce a new receipt surface; the pre-read acceptance for S8 is defined here (S8 still obeys the layer egress PASS on `outlet_catalogue`). 

---

## 9.1 Structural & schema checks

The validator SHALL:

* Load all S7 event streams written by this state (at minimum `rng_event.residual_rank`) and assert **JSON-Schema pass** at their anchors, including envelope fields. For `residual_rank`: required fields, residual in **[0,1)** per description, `residual_rank ≥ 1`. 
* Enforce **`ts_utc` format with exactly 6 fractional digits** and RFC-3339 “Z”, as required by the layer envelope. 

## 9.2 Lineage & partition discipline

* Assert **path↔embed equality** for `{seed, parameter_hash, run_id}` on all S7 events (and any S6 convenience inputs read by the validator). 
* If the validator reads S6 or S5 convenience/authority surfaces, it MUST first verify their **PASS receipts** (S6 seed+parameter; S5 parameter). **No PASS → no read.** 

## 9.3 Domain reconstruction & membership compliance

* Recompute the S7 **domain** $D$ from **S3** (`candidate_rank` total & contiguous; `home=0`) intersected with **S6 membership** (dataset if present, else reconstructed from `rng_event.gumbel_key` selection flags). Membership MUST be a subset of S3’s admissible set.
* If `K_target` exists (from S4), assert **`|membership| = min(K_target, |Eligible|)`** (informational—S7 does not reinterpret S4 beyond this). 

## 9.4 Weight authority & restriction

* Read **S5 `ccy_country_weights_cache`** (authority; parameter-scoped) and assert per-currency **Σ weight = 1.0 ± 1e-6** and domain legality (ISO FKs).
* **Restrict and renormalise ephemerally** to the S7 domain $D$ for re-derivation; validator MUST confirm that S7 **did not persist** any new weights surface. 

## 9.5 Integerisation re-derivation (deterministic)

Using **S0 numeric law** (binary64, RNE), the validator SHALL:

1. Compute $a_i=N\cdot s_i$ for all $i\in D$, then $b_i=\lfloor a_i\rfloor$ and $d=N-\sum b_i$.
2. Quantise residuals $r_i=a_i-b_i$ to **dp=8** (ties-to-even).
3. Order countries by the **binding tie-break** (residual↓, then ISO A→Z, then `candidate_rank`↑; stable) and award **+1** to the top $d$.
4. Reconstruct `residual_rank` and compare **byte-for-byte** to S7’s event payloads; assert **Σ counts = N**, counts ≥ 0, and **$|c_i - N s_i|\le 1$**. 

## 9.6 RNG accounting & envelope legality

* For **`rng_event.residual_rank`**: assert **non-consuming** envelopes (`draws="0"`, `blocks=0`) and that **`rng_trace_log`** has **exactly one** cumulative append **after each** event; reconcile `events_total`, `draws_total`, and `blocks_total` for the `(module="1A.integerisation", substream_label="residual_rank")` key. 
* If the **Dirichlet lane** is enabled: assert equal-length arrays `{country_isos, alpha, gamma_raw, weights}`, **αᵢ>0**, and **Σ weights = 1 ± 1e-6** at the event anchor. (S7 does **not** emit per-component `gamma_component` events.)

## 9.7 Bounds variant (when enabled)

* Verify feasibility **`ΣL_i ≤ N ≤ ΣU_i`**; apply capacity-aware bump checks; **fail** if allocating all $d$ units is impossible under capacity. (No new authority surfaces introduced.) 

## 9.8 Authority & isolation checks

* **Order:** Confirm S7 **did not** write any inter-country order surface; consumers must continue to join S3 `candidate_rank`. 
* **Weights:** Confirm S7 **did not** persist a new weights table; S5 remains authority. 
* **Legacy surfaces:** Ensure S7 does **not** revive `country_set` as an order authority (legacy; deprecated). 
* **Family isolation:** S7 wrote only its own event family (`residual_rank` and, if enabled, `dirichlet_gamma_vector`) and did **not** emit S1–S6 families. 

## 9.9 S8 pre-read acceptance (the “gate”)

S8 **MUST** verify, for the same `{seed, parameter_hash[, run_id]}`:

* Presence of a **complete** `residual_rank` set covering the S7 domain (one row per `(merchant_id,country_iso)`). 
* **PASS receipts** for any S6 convenience surfaces used by S8 (if any), and that S5 weights read by S8 are PASSed for the `parameter_hash`. 
* Layer egress rule still applies to `outlet_catalogue`: **no read** until the fingerprint PASS flag for that egress exists and matches its bundle hash. 

## 9.10 Validator results & failure mapping

* **SUCCESS** — All checks above pass; S8 may proceed.
* **STRUCTURAL_FAIL** — Any schema/lineage/gate breach.
* **INTEGERISATION_FAIL** — Any sum/proximity/quantisation/ranking breach.
* **RNG_ACCOUNTING_FAIL** — Envelope or trace reconciliation breach.
* **BOUNDS_FAIL** — Any infeasibility/capacity-exhaustion in the bounds variant. (Codes map 1:1 to §8.)

---

**Outcome.** A run is **validator-clean** when §9.1–§9.8 pass. S8 then performs §9.9 checks before materialising `outlet_catalogue` (which itself remains governed by the layer egress PASS). This preserves the authority boundaries: **S3 owns order**, **S5 owns weights**, **S7 allocates** deterministically with auditable logs.

---

# 10) Concurrency, sharding & determinism **(Binding)**

**10.1 Work partitioning (who does what, where).**

* **Shard-by-merchant.** Producers **MUST** assign **each merchant to exactly one worker** for S7; no two workers may emit S7 events for the **same merchant**. Sharding **MUST** depend only on stable inputs (e.g., IDs), not on scheduling or file listing order. Event partitions are always **`{seed, parameter_hash, run_id}`**. 
* **Read parallelism is free.** Inputs (`s3_candidate_set`, S5 weights, S6 membership/events, S2/S4 facts) **MAY** be read in parallel; readers **MUST NOT** rely on physical file order (Dictionary `ordering: []`). Authority for cross-country order **remains** S3 `candidate_rank`.

**10.2 Set semantics & stable merges.**

* **Set, not sequence.** S7 event streams (e.g., `rng_event.residual_rank`) have **set semantics**; physical row order is non-authoritative (`ordering: []` in the Dictionary). Any multi-part merge **MUST** be value-stable regardless of part ordering. 
* **Uniqueness within a merchant.** Exactly **one** `residual_rank` row per `(merchant_id, country_iso)` in the S7 domain; duplicates are **FAIL** at validation. (This mirrors S3’s “total & contiguous” uniqueness discipline for `candidate_rank`.) 

**10.3 Idempotency & backfill.**

* **Same inputs ⇒ identical outputs.** Re-running S7 with the **same `{seed, parameter_hash, run_id}`** and identical upstream inputs **MUST** yield **byte-identical** S7 outputs. If any input or config changes, a **new `run_id`** is required. 
* **At-most-once publish.** If a target partition already exists, producers **MUST** verify content hash; if identical, treat as **no-op**; if different, **hard-fail** (no overwrite). 

**10.4 Atomic publish & immutability.**

* **Stage → fsync → atomic rename.** Writers **MUST** publish via a temporary path and **atomically** promote; partial contents **MUST NOT** become visible. After publish, partitions are **immutable**. (Same discipline as S5/S6.)

**10.5 Trace cadence under parallelism.**

* **One trace append per event.** After **each** S7 event append, producers **MUST** append **exactly one** cumulative row to `rng_trace_log` for the key `(module="1A.integerisation", substream_label="residual_rank")`. Totals **MUST** reconcile irrespective of writer concurrency. 
* **No double-emission.** A merchant’s S7 events **MUST NOT** be emitted by multiple workers (would inflate `events_total`). Detect and fail on any concurrent write intent for the same merchant. 

**10.6 Lineage & partition equality (concurrent safety checks).**

* **Path↔embed equality is binding.** Where lineage columns exist, embedded `{seed, parameter_hash, run_id}` **MUST** byte-equal the partition tokens; violations are **FAIL** (pre-flight and validator). 
* **Canonical paths.** Event and log paths **MUST** match the Dictionary patterns for their families; S7 uses the same run-scoped paths as other RNG families. 

**10.7 Determinism across worker counts & retries.**

* Changing the **number of workers** or task scheduling **MUST NOT** change any value or emitted row. Determinism is guaranteed by: (i) S3’s authoritative order; (ii) S5’s authority weights; (iii) S7’s **dp=8** quantisation & fixed tie-breaks; and (iv) set-semantics + atomic publish.
* **Retry semantics.** On failure, producers **MUST NOT** partially publish; they MAY retry the **same** `{seed, parameter_hash, run_id}` after cleaning temp paths. (If anything upstream changed, bump `run_id` per §10.3.) 

**10.8 Ownership & isolation.**

* **Producers & families.** S7 writes **only** its families: `rng_event.residual_rank` (and optional `dirichlet_gamma_vector` when the Dirichlet lane is enabled). Module/substream lineage for these families is frozen in the Dictionary.
* **No cross-state emissions.** S7 **MUST NOT** emit S1–S6 families (e.g., `gumbel_key`, `poisson_component`) nor any S8 egress. Those families are owned by their states. 

**10.9 Reader discipline.**

* **Never rely on file order.** Readers and validators **MUST** treat all S7 streams as unordered sets; join/order always comes from S3 `candidate_rank`.

**10.10 Dirichlet lane concurrency (feature-flag; default OFF).**

* When enabled, S7 **MAY** emit **one** `dirichlet_gamma_vector` per merchant under the same run-scoped partitions; arrays **MUST** be equal-length and Σweights=1±1e-6. Concurrency rules above (atomic publish, set semantics, trace cadence) apply identically.

---

# Appendix A — Enumerations & literal labels (Normative)

All literals below are **case-sensitive** and **binding**. Producers and validators **MUST** use them exactly as written.

## A.1 `module` (RNG producer lineage)

* `1A.integerisation` — producer of `rng_event.residual_rank` (default S7 lane).
* `1A.dirichlet_allocator` — producer of `rng_event.dirichlet_gamma_vector` (**feature-flag; default OFF**).

## A.2 `substream_label` (RNG event families)

* `residual_rank` — deterministic, **non-consuming** S7 event (always ON).
* `dirichlet_gamma_vector` — stochastic Dirichlet snapshot (**feature-flag; default OFF**).

> Trace rows in `rng_trace_log` **MUST** key off the exact `(module, substream_label)` pairs above.

## A.3 Tie-break keys (total order for remainder bumps)

Order of precedence (**freeze this order**):

1. `residual` — **quantised** residual at `dp_resid=8`, **descending**.
2. `country_iso` — ISO-3166-1 alpha-2, **A→Z**.
3. `candidate_rank` — from S3, **ascending**.
4. *(implicit)* stable input index — implementation detail to guarantee stability; **not persisted**.

## A.4 Error / failure / degrade labels

**Errors (merchant-scoped FAIL):**

* `E_PASS_GATE_MISSING` — attempted read without required S5/S6 PASS.
* `E_SCHEMA_INVALID` — input failed schema validation.
* `E_PATH_EMBED_MISMATCH` — path↔embed lineage inequality.
* `E_UPSTREAM_MISSING` — required S2/S3/S4 artefact absent/invalid.
* `E_S6_NOT_SUBSET_S3` — membership contains ISO not in S3 admissible set.
* `E_ZERO_SUPPORT` — restricted S5 weights sum to 0 on domain.
* `E_BOUNDS_INFEASIBLE` — ΣLᵢ>N or ΣUᵢ<N in bounded variant.
* `E_BOUNDS_CAP_EXHAUSTED` — cannot allocate all remainder under Uᵢ caps.
* `E_RNG_ENVELOPE` — missing/malformed envelope on S7 events.
* `RNG_ACCOUNTING_FAIL` — trace totals don’t reconcile (events/draws/blocks).
* `E_DIRICHLET_SHAPE` — Dirichlet arrays not equal length (feature-lane).
* `E_DIRICHLET_NONPOS` — any αᵢ≤0 (feature-lane).
* `E_DIRICHLET_SUM` — Σweights ≠ 1±1e-6 (feature-lane).
* `INTEGER_SUM_MISMATCH` — Σcounts≠N or any count<0.
* `E_RESIDUAL_QUANTISATION` — residual not quantised @ dp=8 before ordering.
* `E_IO_ATOMICS` — atomic publish discipline violated.

**Outcome classes (validator mapping):**

* `STRUCTURAL_FAIL` · `INTEGERISATION_FAIL` · `RNG_ACCOUNTING_FAIL` · `BOUNDS_FAIL` · `SUCCESS`.

**Deterministic degrade (non-error diagnostics):**

* `DEG_SINGLE_COUNTRY` — domain={home}; all N to home.
* `DEG_ZERO_REMAINDER` — d=0; no bumps applied.
* `DEG_TIES_RESOLVED` — ties broken per binding order (ISO, then rank).

## A.5 Dataset & event IDs used by S7 (with roles)

**Read-only authorities / facts**

* `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set` · **partitions:** `[parameter_hash]`
  *Sole inter-country order (`candidate_rank`, contiguous; home=0).*
* `ccy_country_weights_cache` → `schemas.1A.yaml#/prep/ccy_country_weights_cache` · **partitions:** `[parameter_hash]`
  *Weights authority; Σ per currency = 1±1e-6; **S5 PASS required**.*
* `rng_event.nb_final` → `schemas.layer1.yaml#/rng/events/nb_final` · **partitions:** `{seed,parameter_hash,run_id}`
  *Fact: `n_outlets = N ≥ 2` (non-consuming).*
* `rng_event.ztp_final` → `schemas.layer1.yaml#/rng/events/ztp_final` · **partitions:** `{seed,parameter_hash,run_id}`
  *Fact: `K_target` (others audit-only).*

**Membership sources**

* `s6_membership` (convenience) → `schemas.1A.yaml#/s6/membership` · **partitions:** `{seed,parameter_hash}`
  *Use only with **S6 PASS**; order still from S3.*
* `rng_event.gumbel_key` (authoritative events) → `schemas.layer1.yaml#/rng/events/gumbel_key` · **partitions:** `{seed,parameter_hash,run_id}`
  *Reconstruct membership when `s6_membership` absent.*

**Optional helper**

* `merchant_currency` → `schemas.1A.yaml#/prep/merchant_currency` · **partitions:** `[parameter_hash]`
  *If present, S7 MUST NOT override.*

**S7 emissions**

* `rng_event.residual_rank` → `schemas.layer1.yaml#/rng/events/residual_rank` · **partitions:** `{seed,parameter_hash,run_id}`
  *Non-consuming; one row per (merchant,country) in domain; `module="1A.integerisation"`, `substream_label="residual_rank"`.*
* `rng_event.dirichlet_gamma_vector` (**feature-flag**) → `schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector` · **partitions:** `{seed,parameter_hash,run_id}`
  *At most one row per merchant; `module="1A.dirichlet_allocator"`, `substream_label="dirichlet_gamma_vector"`.*

**Core logs**

* `rng_trace_log` → `schemas.layer1.yaml#/rng/core/rng_trace_log` · **partitions:** `{seed,parameter_hash,run_id}`
  *Append **exactly one** cumulative row after **each** S7 event append.*

**Downstream (consumer; not written by S7)**

* `outlet_catalogue` → `schemas.1A.yaml#/egress/outlet_catalogue`
  *S8 materialises; egress **never** encodes inter-country order (consumers join S3).*

## A.6 Partition token names (used by S7)

* Events/logs: `{seed, parameter_hash, run_id}`.
* Parameter-scoped tables (reads): `[parameter_hash]`.

> **Path↔embed equality is binding** wherever lineage columns are embedded; bytes must match partition tokens exactly.

---

# Appendix B — Worked examples (Informative)

Assume domain $D={\text{GB (home)}, \text{DE}, \text{FR}}$ with S3 `candidate_rank` fixed (home=0; others contiguous). Residuals are **quantised to dp=8** (ties-to-even) **before** ordering. Tie-break order: **residual↓, country_iso A→Z, candidate_rank↑**.

---

## B1) Core LRR example (dp=8 quantisation)

* Inputs: $N=13$; restricted S5 weights on $D$: GB 0.58, DE 0.27, FR 0.15 (sum=1.00).
* Fractionals $a=N\cdot s$: GB 7.54, DE 3.51, FR 1.95
  Floors $b$: GB 7, DE 3, FR 1 → remainder $d=13-(7+3+1)=2$
  Residuals $r=a-b$ (dp=8): GB **0.54000000**, DE **0.51000000**, FR **0.95000000**
* Order by residual: FR(0.95) → GB(0.54) → DE(0.51).
  Bump +1 to top **2**: FR and GB.
* **Final counts:** GB 8, DE 3, FR 2 (sum=13).
  **Residual ranks:** FR 1, GB 2, DE 3.

---

## B2) Tie on residuals (ISO tie-break)

* Inputs: $N=10$; weights: GB 0.35, FR 0.35, DE 0.30.
* $a$: GB 3.50, FR 3.50, DE 3.00 → $b$: 3,3,3 → (d=1)
  Residuals (dp=8): GB **0.50000000**, FR **0.50000000**, DE **0.00000000**
* Tie between GB and FR on residual → ISO A→Z decides: **FR** < GB.
  Bump goes to **FR**.
* **Final counts:** GB 3, FR 4, DE 3.
  **Residual ranks:** FR 1, GB 2, DE 3.

---

## B3) Bounded variant (capacity restricts the bump)

* Inputs: $N=10$; weights: GB 0.34, DE 0.33, FR 0.33.
  Bounds: $L=(\text{GB}=3,\text{DE}=1,\text{FR}=2)$, $U=(\text{GB}=3,\text{DE}=4,\text{FR}=3)$.
  Feasible since $\sum L=6 \le 10 \le \sum U=10$.
* $a$: GB 3.40, DE 3.30, FR 3.30 → $b$: 3,3,3 → $d=1$
  Residuals (dp=8): GB **0.40000000**, DE **0.30000000**, FR **0.30000000**
  Capacity: GB $b{=}3=U$ (no room), FR $3=U$ (no room), DE $3<4$ (room).
* Although GB has the highest residual, only **DE** is capacity-eligible, so the +1 goes to **DE**.
* **Final counts:** GB 3, DE 4, FR 3.
  **Residual ranks (full domain):** GB 1, DE 2, FR 3. *(Allocation skips ineligible ranks.)*

---

## B4) Zero-remainder (diagnostic)

* Inputs: $N=10$; weights: GB 0.40, DE 0.30, FR 0.30.
  (a): 4.00, 3.00, 3.00 → (b): 4,3,3 → (d=0).
  Residuals (dp=8): **0.00000000** each → no bumps applied.
* **Final counts:** GB 4, DE 3, FR 3.
  **Residual ranks:** determined solely by ISO A→Z then `candidate_rank` (used only for tie bookkeeping; (d=0)).

These examples illustrate exactly how dp=8 quantisation, tie-breaking, and the bounded Hamilton variant behave—without any reliance on code execution.

---

# Appendix C — Storage conventions (Informative)

These are **non-binding** operational defaults that make S7 artefacts easy to store, move, and read at scale. Reader logic **must not** rely on any file order (set semantics still apply); paths and formats remain governed by the Dataset Dictionary. Treat everything here as “good defaults,” not authority.

## C.1 File format & compression (suggested)

* **JSON Lines (NDJSON)**: simple, append-friendly.

  * Extension: `.jsonl.zst`
  * Compression: **Zstandard level 3** (fast, widely supported)
  * Line endings: `\n` (LF) only; **one JSON object per line**; no trailing commas / no pretty print.
* **Parquet**: columnar, efficient for analytics.

  * Compression: `zstd` **level 3**
  * Row group target: **128–256 MiB uncompressed** (choose a fixed value per family)
  * Encodings: **dictionary** for low-cardinality columns (e.g., `country_iso`, `module`, `substream_label`); `BYTE_ARRAY` stats on categorical fields; enable **statistics**.
* **Do not mix formats** within a single family/partition. Pick **one** per family (e.g., all `residual_rank` as JSONL **or** all as Parquet).

## C.2 Writer sort (advised; readers must not rely on it)

* Within each part file, write rows in a **stable canonical order** to aid diffs and compression:

  1. `merchant_id` ↑
  2. `country_iso` ↑
  3. *(if present)* `candidate_rank` ↑
* This is **for compression & human diffability only**. Reader semantics remain **set-based**; never depend on file order.

## C.3 Part sizing & file naming

* **Compressed part size target:** **64–128 MiB**. Avoid “tiny files” (<8 MiB compressed).
* **Naming:** `part-00000-of-000NN.<ext>` for fixed counts, or `part-<uuid>.<ext>` for streaming emitters.
* **One family per directory**; no multi-family mixing in a single folder.

## C.4 Paths & partitions (reminder)

* Use the **run-scoped** partition law for S7 events/logs:
  `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
* If you add convenience subfolders, keep them **purely cosmetic**, e.g.:
  `…/rng/{module}/{substream_label}/seed=…/parameter_hash=…/run_id=…/part-*.jsonl.zst`
  *(Module/substream names are frozen; see Appendix A.)*

## C.5 Checksums & manifests (recommended)

* Emit a per-part **SHA-256** sidecar: `part-….<ext>.sha256` (hex digest of the compressed bytes).
* Optionally write a folder **manifest**: `_MANIFEST.json` listing parts, sizes, SHA-256, and total logical rows.
* Keep a single **folder hash** (SHA-256 over the concatenated part hashes, in lexicographic name order) as a quick integrity anchor.

## C.6 Atomic publish (recap)

* **Stage → fsync → atomic rename** into the Dictionary path. Never expose partial contents.
* Write any `_MANIFEST.json` and checksum sidecars **before** the final atomic rename.
* After publish, treat partitions as **immutable**; backfills must go to a **new** `run_id`.

## C.7 Retention / TTL (typical defaults)

* **S7 event families** (e.g., `residual_rank`, optional `dirichlet_gamma_vector`): **180 days**.
* **Core RNG logs** (`rng_trace_log`, `rng_audit_log`): **365 days**.
* Implement lifecycle rules at the object store layer; compact small parts weekly before TTL expiry.

## C.8 Storage class & encryption (ops defaults)

* Object storage class: **standard** for the first 30 days, then transition to **infrequent access** if read rates drop.
* Encryption at rest: **SSE-KMS** (or equivalent) with a project-scoped key; bucket-level **deny** on unencrypted puts.
* Server-side checksums enabled; reject uploads without Content-MD5 (or use the SHA-256 sidecars from **C.5**).

## C.9 Metadata & headers

* Set `Content-Type` appropriately:

  * JSONL: `application/x-ndjson` (or `application/jsonl`)
  * Parquet: `application/vnd.apache.parquet`
* Add helpful custom headers/metadata:

  * `x-run-seed`, `x-parameter-hash`, `x-run-id`, `x-content-sha256`, `x-module`, `x-substream`.

## C.10 Compaction & housekeeping

* **Small-file compaction:** if a partition has >128 parts or >30% parts <8 MiB, compact to the target size.
* **Orphan cleanup:** delete any `_staging` subfolders older than 24 h; alert on dangling staging content.
* **Directory hygiene:** keep only `{parts, .sha256, _MANIFEST.json}` files in a partition directory—no temp or editor artefacts.

## C.11 Access patterns (for downstreams)

* Always **predicate** reads on the partition tokens (`seed`, `parameter_hash`, `run_id`) rather than listing entire buckets.
* For Parquet, **column-prune** to just the fields you need (`merchant_id`, `country_iso`, `residual`, `residual_rank`, lineage).
* For JSONL, read in **streaming mode** and avoid in-memory concatenation of entire partitions.

---
