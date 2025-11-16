# 1A — Merchant→Country realism (state-overview, S0–S9)

## S0 — Universe, symbols, authority (RNG-free)

**Goal.** Freeze the canonical universe and the precedence model so S1–S9 are reproducible.
**Fix for the run.** Merchant universe from `merchant_ids`; ISO set; GDP vintage; Jenks buckets; **JSON-Schema is the sole shape authority**; Dictionary = IDs→paths/partitions; Registry = bindings/licences. **Inter-country order is *not* in `outlet_catalogue`; S3 `candidate_rank` is the sole order authority.** 
**Notes.** This is where you also pin numeric posture (IEEE-754 binary64) and open-interval uniforms inherited by later states. 

---

## S1 — Hurdle (single vs multi) — Bernoulli event (RNG-bounded)

**Goal.** Decide `is_multi` per merchant; produce one **hurdle event** per `(seed, parameter_hash, run_id, merchant)`. RNG envelope + cumulative trace are binding. 
**Invariants.** Single uniform when stochastic (`draws ∈ {"0","1"}`, `blocks ∈ {0,1}`); `u∈(0,1)` only in the stochastic branch; **presence-based gating**: all downstream 1A RNG streams appear **iff** `is_multi=true`. Exactly **one** hurdle row per merchant.
**Outputs.** Events+trace only; parameter-scoped partitions `{seed, parameter_hash, run_id}` (path↔embed equality). 

---

## S2 — Total outlet count **N** (Negative-Binomial via Poisson–Gamma) (RNG-bounded)

**Goal.** For `is_multi=true`, draw **N ≥ 2**; for singles, S2 is skipped. S2.1 gates entry, assembles features/coeffs; later steps emit NB events. 
**Invariants.** Entry requires S1 `is_multi=true`; branch purity enforced; lineage keys present; S2.1 emits **no** events (deterministic), later S2 emits events; downstream consumers treat S2 rows as the **sole source** of `raw_nb_outlet_draw`. 

---

## S3 — Cross-border candidate set, order, integer counts, and (in your build) sequencing (RNG-free)

**Goal.** Build the admissible **candidate set** per merchant with **total order** `candidate_rank` (home rank = 0, contiguous), derive **integerised counts** (sum to **N**), and (in your current variant) materialise **within-country sequences**.
**Outputs (parameter-scoped).**

* `s3_candidate_set` — **sole inter-country order authority**. 
* `s3_base_weight_priors` (if policy on) — fixed-dp strings (not probabilities). 
* `s3_integerised_counts` — deterministic integers + `residual_rank`. 
* `s3_site_sequence` (your variant A) — `site_order = 1..count_i` and optional **6-digit** `site_id`. **Overflow `count_i>999,999` ⇒ `ERR_S3_SITE_SEQUENCE_OVERFLOW` (stop merchant).** 
  **Key laws.** `candidate_rank` total & contiguous (home=0); integerisation is largest-remainder with residuals quantised to **dp=8**; optional bounds `(L,U)` with feasibility checks; sequencing **never** alters inter-country order.

---

## S4 — Foreign-count **K_target** via Zero-Truncated Poisson (logs-only) (RNG-bounded)

**Goal.** Compute λ and sample **ZTP** to fix **`K_target`** (≥0 with short-circuit rules); **S4 writes events only**—no tables. **Order and membership are not decided here.** 
**Envelope.** Exact budget/trace rules; records `attempt`, `attempts`, `before/after/blocks/draws`, λ and `K_target`; **`K_realized = min(K_target, A)` is owned by S6**. 

---

## S5 — Currency→Country weight expansion (RNG-free)

**Goal.** Deterministically expand currency surfaces to country **weights** (fixed-dp), to be used by S6/S7. **No priors/probability semantics in S4; weights live here.** 
**Output.** `ccy_country_weights_cache` (parameter-scoped). 

---

## S6 — Foreign-set selection (Gumbel-top-k) (RNG-bounded)

**Goal.** From S3 candidates and S5 weights, select **`K_realized`** foreign countries with **Gumbel-top-k**; **membership only**—persisted order still comes from S3 (`candidate_rank`). 
**Evidence.** One `gumbel_key` event per considered candidate (logged in **S3-rank order**), budgets 1 draw per candidate; validator re-derives the membership from keys + S3/S5. 

---

## S7 — Integer allocation across legal country set (RNG-free)

**Goal.** Turn real-valued expectations into **per-country integers** that **sum to N**, with floors/bounds and a deterministic **bump rule**; record `residual_rank`. (In your build, S3 already emits counts; S7 is the spec’d allocator if you choose that split.) 

---

## S8 — Materialise outlet stubs & sequences (egress) (RNG-free + non-consuming events)

**Goal.** Write **`outlet_catalogue`** (immutable, order-free egress) under `…/seed={seed}/fingerprint={manifest_fingerprint}/`. **Writer sort** `[merchant_id, legal_country_iso, site_order]`. **Multi-site only.** 
**Within-country law.** For each `(merchant, country)` with `n_i≥1`, emit `site_order = 1..n_i`; `site_id = "{site_order:06d}"`. Per-merchant sum of `n_i` equals **N** (`raw_nb_outlet_draw`). **No inter-country order encoded—consumers must join S3.**
**Instrumentation (non-consuming).** `sequence_finalize` per block; **`site_sequence_overflow`** if `n_i>999,999` (ERROR; fail merchant).

---

## S9 — Replay validation & PASS gate (fingerprint-scoped)

**Goal.** Deterministically re-derive S1–S8 outcomes (counts, ranks, sequences, budgets) and publish `validation_bundle_1A/` with **`_passed.flag`** = **SHA-256 over `index.json` entries in ASCII-lex order** (flag excluded). **Consumers must verify: *no PASS → no read*.**

---

## Cross-state invariants (to keep everything green)

* **Order authority boundary.** `outlet_catalogue` is **order-free**; **S3 `candidate_rank` is *sole* inter-country order** (home=0, contiguous). 1B joins S3 for order.
* **Partition law & lineage equality.** Parameter-scoped tables carry `[parameter_hash]`; egress carries `[seed, fingerprint]`. Wherever lineage appears in both path and rows (e.g., `manifest_fingerprint`), **byte-equality is mandatory**.
* **Schema authority.** **JSON-Schema** controls shapes; Dictionary governs IDs→paths/partitions/writer sort; Registry binds licences/gates. **No literal paths in code.** 
* **RNG posture.** Open-interval mapping; budget/trace identity per event family; presence-gating via S1 hurdle; validators re-derive using logged keys/counters.
* **Six-digit sequence space.** Per-country `n_i ≤ 999,999`; otherwise the merchant **must fail** (S3 overflow rule; S8 guards/telemetry echo this).

---

## Where each dataset/artefact lives (authoritative IDs)

* **S3 surfaces (parameter-scoped):**
  `s3_candidate_set` · `s3_base_weight_priors` (if present) · `s3_integerised_counts` · `s3_site_sequence` (variant A). 
* **S8 egress (fingerprint-scoped):**
  `outlet_catalogue` — order-free; PK = `[merchant_id, legal_country_iso, site_order]`. **Consumers join S3 for order & read only after PASS.** 
* **S9 bundle (fingerprint-scoped):**
  `validation_bundle_1A/` + `_passed.flag` (ASCII-lex hashing law). 