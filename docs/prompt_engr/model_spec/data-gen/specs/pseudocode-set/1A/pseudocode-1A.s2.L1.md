# L1 — State-2 Runtime Kernels (Merchant NB Count)

## Purpose

Define the **state-specific kernels** for S2 that (a) consume S0/S1 lineage + S2 inputs, (b) call **S2·L0** helpers to produce **`gamma_component` → `poisson_component`** evidence per attempt, and (c) emit exactly one **non-consuming** **`nb_final`** echoing $(\mu,\phi,N,r)$. It’s code-agnostic but implementation-ready: L1 **calls** L0 (PRNG, samplers, writer, trace, numeric shims), never re-implements helpers, schemas, or paths. **Counters are never chained across labels; each family derives its own keyed substream.**

## Scope (what’s in / out)

**In**

* **S2.1–S2.5 kernels only:** deterministic link→parameter compute; one-attempt “Γ then Poisson” emission; deterministic acceptance rule (**accept iff** $k \ge 2$); finaliser emit; typed in-memory handoff $(N,r)$.
* **Event I/O via L0:** envelopes + payloads + cumulative **saturating** trace, with paths resolved by the **dataset dictionary** (no hard-coded strings). **Trace rows embed only `{seed, run_id}`; `parameter_hash` is path-only.**

**Out**

* **Orchestration/concurrency** (partitioning, retries, scheduling) → L2.
* **Validation/corridors/CI** (coverage, rejection-rate thresholds, CUSUM) → L3.
* **Reusable helpers** (PRNG, u01, Box–Muller, samplers, writer, trace, formatting) → L0.
* No schema re-definitions, path literals, or cross-merchant logic in L1.

## Run prerequisites (must already hold)

* **Lineage & math profile:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id` are fixed; numeric policy pinned (**binary64**, RNE, **FMA-off**, no FTZ/DAZ; fixed evaluation order).
* **Gate:** S1 hurdle stream exists and is unique per merchant; S2 runs **iff** `is_multi == true` (**gated streams are discoverable in the dictionary under** `gating.gated_by: "rng_event_hurdle_bernoulli"`).
* **Inputs present & well-typed:** design vectors `x_mu`, `x_phi` (frozen shapes) and governed coefficients `β_mu`, `β_phi` available for the merchant; all finite.
* **L0 availability:** access to **S2·L0** for `nb2_params_from_design`, `gamma_attempt_with_budget`, `poisson_attempt_with_budget`, `event_gamma_nb`, `event_poisson_nb`, `emit_nb_final_nonconsuming`, and the writer/trace surface.
* **Dictionary/schemas pinned:** event families are **`gamma_component`**, **`poisson_component`**, **`nb_final`** under partitions `{seed, parameter_hash, run_id}`; **trace** lives at `rng_trace_log` under the same partitions but **embeds only** `{seed, run_id}`. Payload floats are passed as **numbers** (writer emits shortest-decimal JSON).
* **Substream labels & modules fixed:** `gamma_nb / 1A.nb_and_dirichlet_sampler`, `poisson_nb / 1A.nb_poisson_component`, `nb_final / 1A.nb_sampler`.
* **RNG invariants understood:** **strict-open** $u\in(0,1)$, lane policy (single-uniform = low lane; Box–Muller uses both lanes, **no cache**), **blocks = after − before**, **draws = actual uniforms consumed** (independent identities), and **microsecond** `ts_utc` (**6 digits, truncated, trailing `Z`**) on events/trace.
* **Audit presence:** `rng_audit_log` exists for the run prior to any S2 events.


## Authorities & literals (schemas, dictionary, labels/modules, partitions)

* **Labels / modules (closed set).**
  `gamma_nb / 1A.nb_and_dirichlet_sampler`, `poisson_nb / 1A.nb_poisson_component`, `nb_final / 1A.nb_sampler`. Fixed for S2; reference **symbolically** (no hand-typing in kernels).

* **Schemas (authoritative).**
  `schemas.layer1.yaml#/rng/events/gamma_component`, `schemas.layer1.yaml#/rng/events/poisson_component`, `schemas.layer1.yaml#/rng/events/nb_final`.

* **Dictionary IDs / paths / partitions (no literals in L1).**
  `rng_event_gamma_component` → `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` *(example; resolved via dictionary)*
  `rng_event_poisson_component` → `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` *(example; resolved via dictionary)*
  `rng_event_nb_final` → `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` *(example; resolved via dictionary)*
  **Partitions for all RNG streams:** `["seed","parameter_hash","run_id"]`. **Gated by** hurdle: `is_multi == true` (per dictionary `gating` block). **Paths are resolved via the dictionary in L0; L1 never embeds path strings.**

* **Payload literals (family specifics).**
  `gamma_component` payload **must include** `context:"nb"` and `index:0` (plus `alpha` and `gamma_value` as JSON numbers). `poisson_component` payload includes `context:"nb"`, `lambda` (number) and `k` (integer).

* **Non-consuming finaliser.**
  `nb_final` **must** encode zero consumption: `before==after`, `blocks=0`, `draws:"0"`. `manifest_fingerprint` is embedded in the event envelope but **not** a path partition for RNG streams.


## L0 dependencies (Reuse Index)

L1 **calls**, never re-implements, the following **S2·L0** helpers; envelope math, path resolution, and trace semantics are handled by L0/writer:

* **NB math.** `nb2_params_from_design(x_mu,x_phi,β_mu,β_phi) → {mu, dispersion_k}` (binary64, fixed-order Neumaier; values later **echoed** in `nb_final`).
* **Attempt capsules.** `gamma_attempt_with_budget(φ, sγ)`; `poisson_attempt_with_budget(λ, sπ)`.  
  L1 **calls the Γ capsule pre-guard (no emission)** to obtain `G` and budgets; after λ passes the guard, L1 emits `gamma_component` using the writer/trace surface and proceeds to `event_poisson_nb(λ, …)` (whose emitter performs the Π attempt). (strict-open `u∈(0,1)`, lane policy; budgets = **actual uniforms**).
* **Emitters.** `event_gamma_nb(...)`, `event_poisson_nb(...)`, `emit_nb_final_nonconsuming(...)` (writer computes `blocks` from counters; **payload numbers remain numbers**; trace totals are **saturating u64**).
* **Writer / trace surface (single I/O).** `begin_event_micro(...)` → `end_event_emit(...)` → `update_rng_trace_totals(...)`; dictionary resolver (`dict_path_for_family(...)`). **No path strings in L1.** (Trace rows embed only `{seed, run_id}`; `parameter_hash` is path-only.)
* **Dictionary reality check.** IDs, paths, partitions, and **gating** for the three families are pinned in the dataset dictionary—L1 relies on it (no inline name lists).


## Kernel index (what follows in this doc)

* **S2.1 — Load & Guard (no RNG):** verify gate; load `x_mu,x_phi,β_mu,β_phi`; assemble lineage; signal numeric/input issues upward (no S2 events).
* **S2.2 — NB Links → Parameters (no RNG):** compute $\mu,\phi$ via L0; guard `>0`; retain exact floats for `nb_final`.
* **S2.3 — One Attempt: Γ then Poisson (RNG; guarded emission):** draw $G\sim\Gamma(\phi,1)$ via the **capsule** (no emission), compute/guard $\lambda=(\mu/\phi)G$, then **emit** `gamma_component` and **emit** `poisson_component`. **Two events per valid attempt**; writer/trace via L0.
* **S2.4 — Acceptance Control (deterministic):** accept iff `k ≥ 2`; else increment `r` and repeat S2.3.
* **S2.5 — Finalise (non-consuming) & Handoff:** emit one `nb_final` (`blocks=0`, `draws:"0"`) echoing `(μ,φ,N,r)`; return `(N,r)` to downstream.

---

# S2.1 — Load & Guard (no RNG)

## Intent

Prepare a **merchant-scoped** context for S2: verify hurdle gating, assemble lineage, and sanity-check NB inputs (`x_mu, x_phi, β_mu, β_phi`). **No RNG** and **no file I/O** beyond dictionary/registry lookups via L0; **emit no S2 events** here. Gated NB streams may exist **iff** the S1 hurdle says `is_multi == true`.

## Inputs (must already be present)

* **Lineage:** `seed, parameter_hash, manifest_fingerprint, run_id` (fixed for the run).
* **Gate proof (hurdle):** exactly one row in `rng_event_hurdle_bernoulli` for this `merchant_id` under `{seed,parameter_hash,run_id}`, whose **payload** has `is_multi==true`; envelope literals must be `module:"1A.hurdle_sampler"`, `substream_label:"hurdle_bernoulli"`. Schema anchor: `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.
* **NB design & coefficients:** `x_mu, x_phi` (frozen shapes), governed `β_mu, β_phi` (shape-aligned), all entries **finite**. (NB mean excludes GDP; NB dispersion includes `ln g_c`.)
* **Dictionary bindings (symbolic only; no path literals in L1):**
  `rng_event_gamma_component`, `rng_event_poisson_component`, `rng_event_nb_final` → partitions `["seed","parameter_hash","run_id"]`, **gated_by** `rng_event_hurdle_bernoulli` with predicate `is_multi == true`.

## Preconditions (signal up if any fail)

* **Hurdle uniqueness & gate:** hurdle present and **unique** per merchant in the run; `is_multi==true` required for S2. Also confirm **path↔embed equality** on hurdle for `{seed,parameter_hash,run_id}` and envelope literals.
* **Numeric readiness:** `len(x_mu)==len(β_mu)` and `len(x_phi)==len(β_phi)`; every element of `x_*` and `β_*` is finite. Otherwise, **signal** a merchant-scoped numeric/input failure and **emit no S2 events**.
* **Audit presence:** an `rng_audit_log` exists for this `{seed,parameter_hash,run_id}` **before** any S2 emission. (L1 checks presence; abort wiring is L2/L3.)

## Procedure (code-agnostic)

```pseudocode
function S2_1_load_and_guard(merchant_id:u64, lineage, inputs) -> NBContext
  # lineage = { seed, parameter_hash, manifest_fingerprint, run_id }
  # inputs  = { x_mu:f64[], x_phi:f64[], beta_mu:f64[], beta_phi:f64[] }

  # 0) Hurdle gate (no RNG, no writes)
  hurdle = lookup_hurdle_event(merchant_id, lineage)              # schemas.layer1.yaml#/rng/events/hurdle_bernoulli
  require(hurdle.exists)                                          # present
  require_unique_hurdle_per_merchant(merchant_id, lineage)        # uniqueness
  require(hurdle.payload.is_multi == true)                        # gate pass (dictionary gating)
  require_path_embed_equality(hurdle, lineage)                    # {seed,parameter_hash,run_id} match
  require_literals(hurdle.envelope.module  == "1A.hurdle_sampler" and
                   hurdle.envelope.substream_label == "hurdle_bernoulli")  # registry-closed

  # 1) NB inputs
  require_shapes_match(len(inputs.x_mu)  == len(inputs.beta_mu))
  require_shapes_match(len(inputs.x_phi) == len(inputs.beta_phi))
  require_all_finite(inputs.x_mu, inputs.x_phi, inputs.beta_mu, inputs.beta_phi)

  # 2) Bind literals symbolically (S2 L0 §3; no path strings)
  labels  = { gamma: "gamma_nb", poisson: "poisson_nb", final: "nb_final" }
  modules = { gamma: "1A.nb_and_dirichlet_sampler",
              poisson: "1A.nb_poisson_component",
              final:   "1A.nb_sampler" }

  # 3) Construct merchant-scoped context for S2.2+
  ctx = NBContext{
    merchant_id, lineage,
    x_mu: inputs.x_mu, x_phi: inputs.x_phi,
    beta_mu: inputs.beta_mu, beta_phi: inputs.beta_phi,
    labels, modules,
    rejections: 0
  }
  return ctx
```

**Notes.** Dictionary declares both **gating** and **partitions**; L1 never embeds path strings or re-derives policy. Substreams are **not** derived here—each family derives its own keyed substream at emission time (no counter chaining).

## Outputs

* **NBContext** (in-memory only): `{ merchant_id, lineage, x_mu, x_phi, β_mu, β_phi, labels, modules, rejections=0 }`.
* **No events emitted**; **no RNG consumed**.

## Failure signals (raised to caller; L2/L3 perform abort/record)

* `ERR_S2_INPUTS_INCOMPLETE:{key}` — missing `x_*`/`β_*` or shape mismatch.
* `ERR_S2_NUMERIC_INVALID` — any non-finite entry in `x_*`/`β_*`.
* `ERR_S2_GATING_VIOLATION` — no hurdle event, multiple hurdle rows, envelope literal mismatch, path↔embed inequality, or `is_multi==false`.

---

# S2.2 — NB Links → Parameters (no RNG)

## Intent

Deterministically compute the **NB2** parameters for this merchant from fixed design vectors and governed coefficients—**no RNG, no I/O**—and retain the exact binary64 values for a **byte-equal echo** in `nb_final`.

$$
\mu=\exp(\beta_\mu^\top x^{(\mu)}),\qquad \phi=\exp(\beta_\phi^\top x^{(\phi)})
$$

## Inputs (from S2.1 / artefacts)

* `x_mu : f64[Dμ]`, `x_phi : f64[Dφ]` — frozen shapes; **mean excludes GDP**, **dispersion includes** `ln g_c` with $g_c>0$.
* `β_mu : f64[Dμ]`, `β_phi : f64[Dφ]` — governed by `parameter_hash` (shape-aligned, finite).
* `lineage = {seed, parameter_hash, manifest_fingerprint, run_id}` — carried forward; **no I/O** here.

## Preconditions (signal up if any fail)

* All entries in `x_mu, x_phi, β_mu, β_phi` are **finite**; shapes match (`len(x_mu)=len(β_mu)`, `len(x_phi)=len(β_phi)`).
* Numeric policy in force: **binary64**, **RNE**, **FMA-OFF**, no FTZ/DAZ; **fixed evaluation order** (no BLAS, no parallel reductions).

## Procedure (code-agnostic; calls L0)

```pseudocode
function S2_2_links_to_params(ctx: NBContext) -> NBContext
  # ctx already holds finite, shape-aligned x_mu, x_phi, beta_mu, beta_phi

  # 1) Deterministic transform (Neumaier dots + exp; no RNG, no I/O)
  nb = nb2_params_from_design(ctx.x_mu, ctx.x_phi, ctx.beta_mu, ctx.beta_phi)   # L0

  # 2) Attach exact binary64 values for downstream use and final echo
  ctx.mu  = nb.mu                 # > 0, finite
  ctx.phi = nb.dispersion_k       # > 0, finite

  return ctx
```

* `nb2_params_from_design` performs **serial Neumaier** dots, uses the sealed `exp` from the math profile, and **hard-guards** `mu>0`, `phi>0`. There is **no clamping**; any non-finite/≤0 condition maps to `ERR_S2_NUMERIC_INVALID` (L1 **signals**; L2/L3 perform abort/log).

## Outputs

* Updated **NBContext** with `{mu, phi}` attached (in-memory only).
* **No events emitted; no RNG consumed.**

## Invariants & obligations

* **No RNG**, **no path strings**, **no schema writes** here.
* Downstream forms $\lambda = (\mu/\phi)\,G$ in **binary64** (fixed order) using these exact values—**no recompute drift**.
* `nb_final` will echo `mu` and `dispersion_k` **bit-for-bit** and is schema-pinned (`schemas.layer1.yaml#/rng/events/nb_final`) and **non-consuming** (`before==after`, `blocks=0`, `draws:"0"`).
* Payload floats remain **numbers**; the writer emits shortest-round-trip decimals (L0 surface).

**Why this is correct:** It mirrors the frozen S2 links (mean/dispersion roles and positivity), relies on L0’s deterministic numeric profile, and enforces the “compute once, echo exactly” contract that L3 will validate.

---

# S2.3 — One Attempt: Γ then Poisson (RNG; guarded emission)
*Symbols:* `G` (Gamma draw), `λ` (Poisson mean), `K` (Poisson count), `N` (accepted), `r` (rejections).

## Intent

For a **single attempt** at merchant scope: (1) draw $G\sim\Gamma(\phi,1)$ via the **capsule** (no emission), (2) compute $\lambda=(\mu/\phi)\,G$ and **guard BEFORE any emission**; only if λ>0 & finite do we **emit** `gamma_component` and then **emit** `poisson_component` for K~Poisson(λ). Exactly **two events per valid attempt**, in **gamma → poisson** order, using label-scoped substreams and authoritative RNG envelopes via L0. No path strings.

## Inputs (from S2.2 / context)

* `mu, phi` (binary64, >0) from S2.2; `merchant_id`, lineage `{seed, parameter_hash, manifest_fingerprint, run_id}`.
* **Labels/modules fixed:** `gamma_nb/1A.nb_and_dirichlet_sampler`, `poisson_nb/1A.nb_poisson_component`.
* **Families & partitions:** `rng_event_gamma_component`, `rng_event_poisson_component` under partitions `["seed","parameter_hash","run_id"]`, **gated** by the hurdle `is_multi==true`.

## Preconditions (must hold)

* `mu>0`, `phi>0` (already guarded in S2.2).
* Substreams are **keyed by label & merchant** (order-invariant mapping). Attempts advance counters **monotonically within each substream**; **no cross-label chaining**.

## Procedure (code-agnostic; emits as it goes)

```pseudocode
function S2_3_attempt_once(ctx: NBContext,
                           s_gamma: Stream, totals_gamma: TraceTotals,
                           s_pois:  Stream, totals_pois:  TraceTotals)
  -> (G:f64, lambda:f64, K:i64,
      s_gamma':Stream, totals_gamma':TraceTotals,
      s_pois': Stream, totals_pois': TraceTotals)

  # 1) Γ draw (label "gamma_nb") — draw via capsule, no emission yet
  #    Capture 'before' envelope first; capsule advances the stream and returns actual-use budgets.
  ctx_gamma = begin_event_micro(MODULE_GAMMA, LABEL_GAMMA,
                                ctx.lineage.seed, ctx.lineage.parameter_hash,
                                ctx.lineage.manifest_fingerprint, ctx.lineage.run_id,
                                /*s_before*/ s_gamma)                                                # writer prelude
  (G, s_gamma', bud_gamma) = gamma_attempt_with_budget(ctx.phi, s_gamma)  

 # 2) Compose λ in binary64 (fixed order; guard BEFORE any emission)
  tmp    = ctx.mu / ctx.phi                # fixed evaluation order
  lambda = tmp * G

  # Guard λ > 0 and finite — if invalid, emit NOTHING and stop (no Gamma, no Poisson, no final)
  if not is_finite(lambda) or (lambda <= 0.0):
      signal(ERR_S2_NUMERIC_INVALID, { merchant_id: ctx.merchant_id, where: "lambda" })
      return (G, lambda, K := -1, s_gamma', totals_gamma, s_pois, totals_pois) 

  # 3) Emit Gamma now (writer computes blocks from counters; 'draws' from budgets), then Π step
  payload_gamma = { merchant_id: ctx.merchant_id, context:"nb", index:0,
                    alpha: ctx.phi, gamma_value: G }
  end_event_emit(/*family*/ "rng_event_gamma_component",
                 /*ctx*/ ctx_gamma,
                 /*stream_after*/ s_gamma',
                 /*draws_hi*/ bud_gamma.draws_hi, /*draws_lo*/ bud_gamma.draws_lo,
                 /*payload*/ payload_gamma)                                                            # envelope+payload write
  draws_str_gamma = u128_to_decimal_string(bud_gamma.draws_hi, bud_gamma.draws_lo)
  (_, _, evt_gamma) = update_rng_trace_totals(ctx_gamma.module, ctx_gamma.substream_label,
                                             ctx.lineage.seed, ctx.lineage.parameter_hash, ctx.lineage.run_id,
                                             ctx_gamma.before_hi, ctx_gamma.before_lo, s_gamma'.ctr.hi, s_gamma'.ctr.lo,
                                             totals_gamma.draws_total, totals_gamma.blocks_total, totals_gamma.events_total,
                                             draws_str_gamma)
  totals_gamma' = TraceTotals{ blocks_total: totals_gamma.blocks_total /*+Δ*/,  # writer computes Δ internally
                              draws_total:  totals_gamma.draws_total  /*+draws*/,
                              events_total: evt_gamma }

  # 4) Π step (label "poisson_nb") — emit Poisson component for valid λ
  (K, s_pois', totals_pois') =
      event_poisson_nb(
        merchant_id = ctx.merchant_id,
        seed        = ctx.lineage.seed,
        parameter_hash        = ctx.lineage.parameter_hash,
        manifest_fingerprint  = ctx.lineage.manifest_fingerprint,
        run_id      = ctx.lineage.run_id,
        s_before    = s_pois,
        lambda      = lambda,
        prev_totals = totals_pois
      )

  return (G, lambda, K, s_gamma', totals_gamma', s_pois', totals_pois')
```

### Why emit-as-you-go

The schema/dictionary define `gamma_component` and `poisson_component` as approved RNG families under `{seed, parameter_hash, run_id}`. L0 emitters stamp the authoritative envelope (counters → `blocks`; budgets → `draws`) and update the **saturating** trace row once per event.

### Payload correctness

* `gamma_component` payload: `{merchant_id, context:"nb", index:0, alpha, gamma_value}`.
* `poisson_component` payload: `{merchant_id, context:"nb", lambda, k}`.
  Payload floats are **numbers**; the writer prints shortest-decimal JSON.

## Outputs (per attempt)

* **Emitted:** for a **valid attempt**, exactly **1** `gamma_component` **then** **1** `poisson_component` (schema-true, dictionary-gated/partitioned). If λ is non-finite or ≤0, **emit nothing** and signal the numeric error (no Gamma, no Poisson).
* **Returned (in-memory):** `(G, λ, K)` and updated substreams/totals for both families (used by S2.4 acceptance).

## Invariants & budgeting discipline

* **Bit-replay:** fixed keyed substreams + per-attempt cardinality ensure reproducible `(G,K)` and counters.
* **Consumption identities:** `blocks = u128(after) − u128(before)` (counters), `draws = actual uniforms consumed` (decimal u128). Independent checks (capsules measure budgets; writer reconciles counters).
* **Strict-open** $u\in(0,1)$; single-uniform events use the **low lane**; Box–Muller consumes **both lanes** of one block; **no caching**.

## Failure signals (to caller; L2/L3 decide aborts)

* `ERR_S2_NUMERIC_INVALID` — any **non-finite** or **≤ 0** λ; **emit no S2 events** for that merchant (**no Gamma, no Poisson, no final**) and stop S2 for that merchant.

---

# S2.4 — Acceptance Control (deterministic)

## Intent

Turn the stream of **attempts** from S2.3 into a single **accepted** domestic outlet count by **rejecting** any Poisson result $K\in\{0,1\}$ and **accepting the first** $K\ge2$. Record the rejection count $r$ (= attempts before acceptance). **S2.4 emits nothing**; finalisation is S2.5. Corridor checks (overall rejection rate, p99, CUSUM) are enforced by the validator, **not** here.

## Inputs (from S2.2/S2.3)

* `mu, phi` (binary64, >0) from S2.2.
* The S2.3 **attempt** function that **emits** component events per valid attempt in strict order: **`gamma_component` → `poisson_component`**, on their label-scoped substreams (`gamma_nb`, `poisson_nb`). *In the numeric-invalid case (non-finite or ≤0 λ), S2.3 **emits nothing** and signals up.*

## Preconditions (must hold)

* $\mu>0,\ \phi>0$ (guarded in S2.2).
* Per attempt (valid): **Gamma then Poisson**; if λ is invalid: **no emissions**. Within each `(merchant, substream_label)` stream, counters are monotone and **attempt intervals do not overlap**. **No cross-label counter chaining.**

## Procedure (code-agnostic; **no RNG**, **no I/O**)

```pseudocode
function S2_4_accept(ctx: NBContext,
                     s_gamma: Stream, totals_gamma: TraceTotals,
                     s_pois:  Stream, totals_pois:  TraceTotals)
  -> (N:i64, r:i64,
      s_gamma':Stream, totals_gamma':TraceTotals,
      s_pois': Stream, totals_pois': TraceTotals)

  t := 0   # number of rejections so far

  loop:
      # One attempt (S2.3): if λ is valid, emits Gamma then Poisson; otherwise emits nothing
      (G, lambda, K,
       s_gamma, totals_gamma,
       s_pois,  totals_pois) := S2_3_attempt_once(ctx, s_gamma, totals_gamma, s_pois, totals_pois)

      # DEV_ASSERTS (no-op in prod):
      #   totals_gamma.events_total increased by +1 iff λ is valid
      #   totals_pois.events_total increased by +1 iff λ is valid

      if K < 0:
          # Numeric-invalid λ branch: S2.3 emitted nothing and signalled
          # S2.4 must NOT proceed to finalise; surface the failure upward.
          signal(ERR_S2_NUMERIC_INVALID, { merchant_id: ctx.merchant_id, where: "lambda" })
          return (N := -1, r := t, s_gamma, totals_gamma, s_pois, totals_pois)

      if K >= 2:
          N := K
          r := t
          return (N, r, s_gamma, totals_gamma, s_pois, totals_pois)  # S2.5 will emit nb_final
      else:
          t := t + 1   # reject {0,1} and continue; S2.4 emits no rows
```

### Why this is deterministic

Acceptance depends **only** on $K$ from S2.3. Substreams are **keyed per label**, so counters advance deterministically within each family; there is **no** cross-label counter chaining. The λ compute was already done in S2.3 in fixed binary64 order (no FMA).

## Outputs

* In-memory: `(N := first K≥2, r := #rejections)`; passed to **S2.5**.
* **No events** are produced in S2.4. Evidence is already in the component streams written by S2.3; the single `nb_final` will be written in S2.5.
* **Error path:** if λ was invalid (K < 0 sentinel), S2.4 signals `ERR_S2_NUMERIC_INVALID` and **must not** proceed to S2.5.

## Invariants & evidence (checked later by the validator)

* If `nb_final` exists for a merchant, there must be **≥1** prior `gamma_component` **and** **≥1** prior `poisson_component` (payload `context:"nb"`) with matching lineage keys; attempts have **exactly two events** in **Gamma→Poisson** order **per valid attempt**; `nb_final` is **non-consuming** (`before==after`, `draws:"0"`).
* Attempt pairing and the accepted attempt index $t=r$ are reconstructible **solely by counter intervals** (no reliance on time/file order).

## Notes (non-operational here)

* **No hard cap** in S2.4; drift/instability is caught by validator corridors (e.g., overall rejection rate ≤ 0.06; p99 of $r$ ≤ 3).
* Gating remains **presence-based** from S1: NB streams **exist iff** the hurdle shows `is_multi==true`.

---

# S2.5 — Finalise (non-consuming) & Handoff

## Intent

Emit **exactly one** final event for this merchant that echoes the deterministic NB parameters and the accepted count with a **provably non-consuming** RNG envelope, then return a typed handoff for downstream. Finaliser never consumes RNG: `before == after`, `blocks = 0`, `draws = "0"`.

## Inputs (from S2.4 / context)

* `mu, phi` (binary64, > 0) computed in **S2.2** — must be echoed **bit-for-bit** in payload.
* `(N, r)` from **S2.4** — accepted outlets `N ≥ 2`, rejections `r ≥ 0`.
* Lineage `{seed, parameter_hash, manifest_fingerprint, run_id}`, `merchant_id`.
* `s_final` substream handle for `LABEL_FINAL="nb_final"`; `MODULE_FINAL="1A.nb_sampler"` (bound via L0 literals).

## Preconditions (must hold; else signal up)

* **Acceptance domain:** `N ≥ 2` and `r ≥ 0`. If not, **signal** `ERR_S2_NUMERIC_INVALID:{where:"finaliser_inputs"}` and **do not** emit `nb_final`.
* **Inputs echoable:** `mu` and `phi` present and finite (carried from S2.2).
* **Evidence prerequisites:** S2.3 has already run (Gamma→Poisson attempts per the gate). Coverage and ordering are enforced by the validator later; L1 does not rescan logs here.

## Procedure (code-agnostic; calls L0)

```pseudocode
function S2_5_finalise(ctx: NBContext,
                       N:i64, r:i64,
                       s_final: Stream, totals_final: TraceTotals)
  -> (handoff:{N:i64, r:i64}, totals_final': TraceTotals)

  # 1) Emit single non-consuming finaliser (L0 enforces before==after, draws=="0")
  totals_final' =
      emit_nb_final_nonconsuming(
        merchant_id         = ctx.merchant_id,
        seed                = ctx.lineage.seed,
        parameter_hash      = ctx.lineage.parameter_hash,
        manifest_fingerprint= ctx.lineage.manifest_fingerprint,
        run_id              = ctx.lineage.run_id,
        s_final             = s_final,               # NO RNG consumption
        mu                  = ctx.mu,               # echo exactly
        dispersion_k        = ctx.phi,              # echo exactly
        n_outlets           = N,                    # N ≥ 2
        nb_rejections       = r,                    # r ≥ 0
        prev                = totals_final
      )

  # 2) Typed handoff downstream (in-memory only)
  return ({ N:N, r:r }, totals_final')
```

**Why L0 call:** `emit_nb_final_nonconsuming(...)` stamps the `nb_final` envelope with lineage + `before/after` counters and computes `blocks` from counters; it serializes `draws:"0"` and appends a **saturating** trace row. L1 never re-implements envelopes, counters, or paths.

## Outputs

* **Emitted:** exactly **one** `nb_final` event for this merchant (schema `schemas.layer1.yaml#/rng/events/nb_final`), presence-gated by S1 hurdle (`is_multi==true`) under the dictionary partitions `{seed, parameter_hash, run_id}`.
* **In-memory:** typed handoff `{N, r}` for downstream (e.g., cross-border stage **S3**).
* **Trace:** cumulative totals updated once for the `nb_final` substream: `events_total += 1`; `draws_total` unchanged (zero); `blocks_total` reconciles **0** via `after==before`.

## Invariants & evidence (checked by validator later)

* **Non-consumption proof:** writer enforces `draws:"0"` and `after == before`.
* **Echo binding:** `payload.mu == ctx.mu` and `payload.dispersion_k == ctx.phi` at **bit equality**.
* **Per-merchant cardinality:** exactly **one** `nb_final`; for that merchant/run there exist **≥ 1** prior `gamma_component` **and** **≥ 1** prior `poisson_component` (`context:"nb"`), pairable by **counter intervals** (not time/file order).
* **Partitions & gating:** path partitions and envelope lineage keys match; families remain presence-gated by S1 hurdle.

## Failure signals (to caller; L2/L3 decide aborts)

* `ERR_S2_NUMERIC_INVALID:{where:"finaliser_inputs"}` — if `N < 2`, `r < 0`, or missing/invalid `mu/phi`.
  *(L1 **signals**; L2/L3 commit failure bundles per S0 Batch-F.)*

---

# Failure surfaces (signals only)

L1 does **not** commit failure bundles or abort runs. It **signals** typed failures upward (for L2/L3 to log/abort/validate). On **any** signal for a merchant, L1 must **stop emitting** further S2 events for that merchant immediately.

**Signal types (merchant-scoped unless noted):**

* `ERR_S2_GATING_VIOLATION` — missing or non-unique hurdle event, or `is_multi == false` at entry.
* `ERR_S2_INPUTS_INCOMPLETE:{key}` — required NB inputs absent or shape-mismatched (`x_mu`, `x_phi`, `β_mu`, `β_phi`).
* `ERR_S2_NUMERIC_INVALID` — any **non-finite** or **≤ 0** λ; **emit no S2 events** for that merchant (**no Gamma, no Poisson, no final**) and stop S2 for that merchant.
* `ERR_S2_COMPOSITION_INVALID` — `λ = (mu/phi)·G` computed as a **finite** but **≤ 0** value (distinct from non-finite). **Emit no S2 events** for that merchant and stop S2 for that merchant.
* `ERR_S2_BRANCH_PURITY` (run-scoped if systemic) — any NB event observed for a merchant without the gating hurdle `is_multi == true`.

> **On signal:** return a typed failure to the caller. L2 constructs the canonical failure payload and commits/aborts; L3 enforces coverage/corridors. L1 never writes failure files and never “fixes” data by clamping or retrying outside the acceptance rule.

---

# Determinism & budgeting (reference)

**Numeric & serialization**

* All math in **binary64**, RNE; **FMA OFF**, no FTZ/DAZ; fixed evaluation order.
* Payload floats are passed as **numbers**; the writer prints shortest round-trip JSON (callers never stringify).

**RNG discipline**

* Substreams are **keyed by (label, merchant)** and order-invariant; **no counter chaining across labels**.
* `u01` is **strict-open (0,1)**; single-uniform events consume the **low lane**; Box–Muller consumes **both lanes from the same block** (no caching).
* **Per valid attempt:** exactly **two** component events in order — `gamma_component` then `poisson_component`. (If λ is invalid, **no S2 events are emitted** for that merchant, and S2 stops for that merchant.)
* **Envelope identities:**
  `blocks = u128(after) − u128(before)` (counters),
  `draws =` **actual uniforms consumed** (decimal u128).
  They are **independent**; never infer one from the other.
* **Timestamps:** `ts_utc` is RFC-3339 UTC with **exactly 6** fractional digits (microseconds), **truncated**, with trailing `Z`.

**Finaliser**

* `nb_final` is **non-consuming** (`before==after`, `blocks=0`, `draws:"0"`), and **echoes** `mu`/`phi` bit-for-bit.

**Acceptance & pairing**

* Acceptance is deterministic: **accept first `K ≥ 2`**; `r` = #rejections (`K∈{0,1}`) before acceptance.
* Validator pairs attempts and reconstructs `r` **solely from counter intervals** (no reliance on wall-clock order).

**Paths, partitions, gating**

* L1 never hard-codes paths; it emits via the L0 writer with dictionary-resolved IDs.
* All RNG **event** streams are partitioned by `{seed, parameter_hash, run_id}` and **exist iff** the hurdle gate `is_multi == true`.
* **Path↔embed equality** must hold for `{seed, parameter_hash, run_id}` on every event envelope.
* RNG **trace** rows are under the same partitions but embed only `{seed, run_id}` (parameter_hash is path-only).

**Trace semantics**

* After **every** event, the cumulative RNG trace updates with **saturating** `u64` totals; consumers read the **final** row per `(module, substream_label)`.

---

# Public API (signatures)

> L1 is code-agnostic. Signatures below are descriptive; names match the kernels in this file. **No path strings**; all event I/O goes through L0.

## Primary entry

```
merchant_nb_outlet_count(
  merchant_id: u64,
  lineage: { seed:u64, parameter_hash:Hex64, manifest_fingerprint:Hex64, run_id:Hex32 },
  inputs:  { x_mu:f64[], x_phi:f64[], beta_mu:f64[], beta_phi:f64[] }
) -> {
  handoff: { N:i64, r:i64 },                                # accepted outlets (N≥2) and rejection count r≥0
  substreams: { gamma:Stream, poisson:Stream, final:Stream },   # updated handles (optional to return)
  totals:    { gamma:TraceTotals, poisson:TraceTotals, final:TraceTotals }  # saturating u64
}
```

**Side-effects:**

* Emits **two RNG events per valid attempt** in order: `gamma_component` → `poisson_component`.
* Emits **exactly one** `nb_final` (non-consuming) per merchant.
* If λ is **non-finite or ≤ 0** for an attempt: **emit nothing**, signal `ERR_S2_NUMERIC_INVALID`, and **stop** S2 for that merchant (no Gamma, no Poisson, no final).

## Kernel surface (callable internally or by a thin L2)

```
S2_1_load_and_guard(
  merchant_id, lineage, {x_mu, x_phi, beta_mu, beta_phi}
) -> NBContext

S2_2_links_to_params(
  ctx: NBContext
) -> NBContext                     # attaches {mu, phi}

S2_3_attempt_once(
  ctx: NBContext,
  s_gamma:Stream, totals_gamma:TraceTotals,
  s_pois: Stream, totals_pois: TraceTotals
) -> (G:f64, lambda:f64, K:i64,
      s_gamma':Stream, totals_gamma':TraceTotals,
      s_pois': Stream,  totals_pois': TraceTotals)
# Emits: 1 gamma_component, then (iff λ>0 & finite) 1 poisson_component

S2_4_accept(
  ctx, s_gamma, totals_gamma, s_pois, totals_pois
) -> (N:i64, r:i64,
      s_gamma':Stream, totals_gamma':TraceTotals,
      s_pois': Stream,  totals_pois': TraceTotals)
# No emissions here

S2_5_finalise(
  ctx: NBContext, N:i64, r:i64,
  s_final:Stream, totals_final:TraceTotals
) -> (handoff:{N:i64, r:i64}, totals_final':TraceTotals)
# Emits: 1 nb_final (non-consuming)
```

**L0 dependencies (called by L1):**
`nb2_params_from_design`, `event_gamma_nb`, `event_poisson_nb`, `emit_nb_final_nonconsuming`, `begin_event_micro`, `end_event_emit`, `update_rng_trace_totals` (saturating), dictionary resolver.
(*Note:* In **S2.3**, L1 performs **Γ via `gamma_attempt_with_budget` → guard λ → writer**, and therefore does **not** call `event_gamma_nb` to avoid any pre-guard emission.)
**Never** re-implement helpers; payload floats are passed as **numbers** (writer prints shortest-decimal JSON).

---

# Acceptance (for this L1 file)

L1 is **green** when all of the following hold:

**Scope**

* Only S2.1–S2.5 kernels are implemented; no orchestration/concurrency (L2) and no validators/corridors (L3).
* No reusable helpers defined here; every generic helper is imported from L0.

**Gating & partitions**

* NB streams exist **iff** S1 hurdle shows `is_multi == true`.
* All RNG **event** families (`gamma_component`, `poisson_component`, `nb_final`) are written under partitions **{seed, parameter_hash, run_id}** (resolved via dictionary; **no path literals** in L1).
* **Path↔embed equality** holds for `{seed, parameter_hash, run_id}` on every event envelope.

**Emissions & schemas**

* **Per valid attempt:** exactly **2** events in order — `gamma_component` then `poisson_component`; payloads:

  * Gamma: `{merchant_id, context:"nb", index:0, alpha, gamma_value}` (numbers).
  * Poisson: `{merchant_id, context:"nb", lambda, k}` (numbers).
* **λ-invalid attempt:** **no emissions**; L1 signals `ERR_S2_NUMERIC_INVALID` and **stops** S2 for that merchant (no final).
* **Finaliser:** exactly **1** `nb_final` with `{merchant_id, mu, dispersion_k, n_outlets, nb_rejections}` (numbers), and a **non-consuming** envelope (`before==after`, `blocks=0`, `draws:"0"`).

**Numeric & echo binding**

* S2.2 computes `{mu, phi}` with binary64, fixed-order Neumaier dots; `mu>0`, `phi>0`.
* `nb_final.mu == mu` and `nb_final.dispersion_k == phi` at **bit equality**.
* `lambda` formed in fixed binary64 order as `(mu/phi)*G`; if non-finite/≤0, **no** Poisson emission for that attempt and **no** final for the merchant.

**RNG discipline**

* Substreams keyed by **(label, merchant)**; **no cross-label counter chaining**.
* `u01` is **strict-open (0,1)**; single-uniform uses **low lane**; Box–Muller uses **both lanes** (no cache).
* Envelope identities are respected:

  * `blocks = u128(after) − u128(before)` (from counters)
  * `draws  =` **actual uniforms consumed** (decimal u128)
    No attempt to equate or derive one from the other.
* `ts_utc` is RFC-3339 UTC with **exactly 6** fractional digits (truncated) and trailing `Z`.

**Trace**

* After **each** event, cumulative RNG trace totals are updated with **saturating** `u64` counters; consumers select the **final** row per `(module, substream_label)`.
* Trace rows embed only `{seed, run_id}` (the `parameter_hash` is **path-only**).

**No hidden IO / literals**

* L1 contains **no** hard-coded paths, schema fragments, or module/label strings outside the symbolic literals section; everything is referenced via L0 literals + dictionary.

**Failure signalling**

* On any of: missing/misaligned inputs; non-finite/≤0 `mu/phi`; non-finite/≤0 `lambda`; hurdle gate misuse — L1 **signals** (`ERR_S2_*`) and stops S2 emissions for that merchant. L1 does **not** commit failure files or abort runs; L2/L3 own that.

---