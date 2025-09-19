# S3 · L1 — State Kernels (Pure, deterministic, I/O-free)

# 0) Purpose, Scope, Non-Goals (S3 · L1 — State Kernels)

**Purpose.** Define a small set of **pure, deterministic kernels** that implement **State-3 business logic** by transforming **`Ctx + BOM (+ feature flags)`** into **in-memory, schema-shaped row sets** ready for emission. These kernels **reuse L0 helpers** (primarily S3; S0/S1/S2 where already defined) and return arrays that **L2 can emit without reshaping** (L2 will attach lineage).

**Scope.**

* **What L1 does**

  * Consumes **values only** (not files): a pre-validated **`Ctx`**, **BOM** artefacts, and **feature flags**.
  * Applies **deterministic logic** end-to-end: ladder evaluation → candidate assembly → deterministic ranking (**single order authority**) → optional priors → optional integerisation → optional sequencing → packaging of outputs.
  * Produces **host-neutral arrays** whose **field names/types match the S3 schema anchors**; lineage fields are deliberately **absent** (L2 attaches them).

* **How L1 works**

  * Calls **only L0 helpers** (S3 first; S0/S1/S2 if already defined); **no I/O**, **no path resolution**, **no RNG**.
  * Every kernel states **Preconditions / Inputs / Outputs / Errors / Determinism / Complexity** so an implementer can lift it verbatim.

**Non-Goals.**

* **No I/O** (no dictionary/registry reads, no writes, no path literals).
* **No RNG** (S3 is fully deterministic).
* **No orchestration** (looping, idempotence, atomic publish live in **L2**).
* **No validation/CI** (proofs live in **L3**; L1 may use tiny asserts locally but does not ship bundles).
* **No policy authoring** (BOM governs; L1 only evaluates policy deterministically).

---

# 0a) Design Invariants (anchor summary)

These invariants hold for all S3 · L1 kernels to guarantee **replayability, portability, and zero implementer ambiguity**.

### Inputs & Gating

* **Entry gates satisfied:** `Ctx` already enforces **`is_multi == true`** (S1) and **`N ≥ 2`** (S2 accepted draw). L1 assumes these; it never resamples or relaxes them.
* **BOM is authoritative:** rule ladder, ISO set, and optional priors/bounds configs are version-pinned/digested and treated as **read-only facts**.

### Determinism & Numeric Discipline

* **RNG-free:** outcomes are pure functions of inputs.
* **Binary64 policy:** where floats appear (e.g., priors algebra), assume IEEE-754 binary64, round-to-nearest-even, **no FMA**, no reordering of reductions (Neumaier when needed).
* **Exact decimal where required:** any fixed-decimal strings (priors) use **base-10 half-even quantisation** via integer/rational paths; no locale effects.
* **Stable ordering:** all sorts are **stable** and use fully specified keys; string compares are **ASCII**; ISO codes are canonical **uppercase**.

### Single Sources of Truth

* **Inter-country order:** **only** `candidate_rank` (home = 0; foreigns contiguous). File order is non-authoritative.
* **Priors semantics:** **scores, not probabilities**; **no renormalisation** anywhere in S3.
* **Integerisation semantics:** **Largest-Remainder (Hamilton)**; Σ`count` = **N** (from S2); residuals quantised by `dp_resid` before tie-break.
* **Sequencing semantics:** within each country, `site_order = 1..nᵢ` contiguous; optional `site_id` is **zero-padded order (width 6)**.

### Feature Flags (run-constant per parameter set)

* `priors_enabled`

  * **true:** compute priors with a **constant `dp`**; zero/absent scores are permitted (policy-dependent) and yield zero weights.
  * **false:** integerisation uses **uniform** shares.
* `integerisation_enabled`

  * **true:** produce **`CountRow[]`** (Σ`count` = N); floors/ceilings from bounds policy may apply.
  * **false:** no counts; **sequencing must be disabled**.
* `sequencing_enabled`

  * **true:** **requires counts**; produce **`SequenceRow[]`** (per-country contiguity, optional 6-digit IDs).
  * **false:** no sequencing rows.

### Error Posture (merchant-scoped, non-emitting)

* **Fail-fast** on domain/shape violations: unknown ISO/vocab, duplicate countries, missing single home, infeasible floors/ceilings, invalid fixed-dp strings, rank non-contiguity, non-contiguous sequencing, or policy misconfiguration.
* **No auto-repair**; L2 decides how to proceed for the merchant.

### Complexity & Memory Targets (per merchant slice)

* **Ranking:** **O(k log k)**, memory **O(k)** (k = number of candidate countries).
* **Integerisation:** **O(k log k)** + linear arithmetic; memory **O(k)**.
* **Sequencing:** **O(∑nᵢ)** to build rows + **O(k log k)** for final country order.
* **No universe-wide materialisation**; operate only on the current merchant’s arrays.

### Layer Boundaries (clarity for implementers)

* **L0** supplies atoms (BOM loaders, helpers, comparators, quantisers, LRR, sequencing, emit surfaces).
* **L1** composes atoms into **pure kernels** returning **schema-shaped arrays (minus lineage)**.
* **L2** orchestrates merchants, attaches lineage, and **emits** via L0 emitters (idempotence + atomic publish).
* **L3** validates bytes against schema and state contracts (order, sums, fixed-dp, contiguity).

**Result:** With these invariants, S3 · L1 kernels are copy-pastable, cross-language identical, and ready for **L2** to wire with zero guesswork.

---

# 1) Imports & Reuse Map (S0/S1/S2/S3 · L0)

**Goal.** Keep L1 *pure and tiny* by **reusing** helpers that already exist. L1 defines **kernels only**; it never re-implements utilities that live in L0 (any state). If a helper isn’t listed here and isn’t in L0, L1 does not call it.

---

## 1.1 Import policy (resolution & collisions)

* **Resolution order:** **S3·L0 first**, then S0/S1/S2·L0 **only if** the helper does not exist in S3·L0 *and* is state-agnostic.
* **Name qualification:** import with explicit module qualifiers (e.g., `S3L0.ADMISSION_ORDER_KEY`, `S0L0.STABLE_SORT`).
* **Never import:** RNG emitters/trace (`begin_event_micro`, `end_event_emit`, `update_rng_trace_totals`), PRNG substreams/samplers — **S3 is RNG-free**.
* **No path/dictionary I/O:** L1 never calls emitters or dictionary resolvers; those live in **L0 §15** and **L2**.

---

## 1.2 From S3 · L0 (primary surface)

### BOM & context

* `OPEN_BOM_S3(feature_flags) -> BOM`
* `BUILD_CTX(ingress_rows, s1_hurdle_rows, s2_nb_final_rows, bom, channel_vocab:Set<string>) -> Ctx`

### Closed vocabs & ISO

* `BUILD_VOCAB_VIEWS(ladder) -> { REASONS:Set<string>, TAGS:Set<string> }`
* `NORMALISE_REASON_CODES(codes, REASONS) -> array<string>`  *(A→Z, deduped, closed-set enforced)*
* `NORMALISE_FILTER_TAGS(tags, TAGS) -> array<string>`       *(A→Z, deduped, closed-set enforced)*
* `ASSERT_CHANNEL_IN_INGRESS_VOCAB(ch, CHANNEL_VOCAB:Set<string>)`
* `NORMALISE_AND_VALIDATE_ISO2(s, iso_set:Set<ISO2>) -> ISO2`

### Admission order & ranking

* `ASSERT_ADMISSION_META_DOMAIN(m:AdmissionMeta)`
* `ADMISSION_ORDER_KEY(m:AdmissionMeta) -> tuple`  *(precedence, priority, rule_id, ISO, stable_idx)*
* `ASSIGN_STABLE_IDX(foreigns[]) -> foreigns[]`
* `SORT_FOREIGNS_BY_ADMISSION_KEY(foreigns[]) -> foreigns[]`
* `RANK_CANDIDATES(rows:array<CandidateRow>, meta_src:Map<ISO2,AdmissionMeta>, home_iso:ISO2) -> array<RankedCandidateRow>`
  *(home = 0; foreigns contiguous; contiguity asserted)*

### Priors (scores, not probabilities)

* `SELECT_PRIOR_DP(priors_cfg) -> int`  *(constant per run/parameter set)*
* `QUANTIZE_WEIGHT_TO_DP(w:f64, dp:int) -> FixedDpDecStr`  *(base-10 half-even, exact rational path)*
* `EVAL_PRIOR_SCORE(c:RankedCandidateRow, ctx:Ctx, priors_cfg) -> f64|null`  *(policy hook; deterministic)*

### Integerisation (Largest-Remainder)

* `MAKE_SHARES_FOR_INTEGERISATION(ranked:array<RankedCandidateRow>, priors?:array<PriorRow>) -> array<Rational>`
* `MAKE_BOUNDS_FOR_INTEGERISATION(ranked:array<RankedCandidateRow>, bounds_cfg?:BoundsCfg) -> { floors:Map<ISO2,int>, ceilings:Map<ISO2,int>, dp_resid:int }`
* `LRR_INTEGERISE(shares[], iso[], N:int, bounds?, stable?:array<int>) -> (counts:array<int>, residual_rank:array<int>)`

### Sequencing (within-country)

* `BUILD_SITE_SEQUENCE_FOR_COUNTRY(merchant_id:u64, country_iso:ISO2, count_i:int, with_site_id:bool) -> array<SequenceRow>`
* `FORMAT_SITE_ID_ZEROPAD6(k:int) -> string`
* `ASSERT_CONTIGUOUS_SITE_ORDER(rows:array<SequenceRow>)`

### Tiny asserts (local guards L1 may reuse)

* `ASSERT_CANDIDATE_SET_SHAPE(rows:array<RankedCandidateRow>)`  *(one home; no dup ISO; ranks contiguous)*
* `ASSERT_PRIORS_BLOCK_SHAPE(rows:array<PriorRow>)`             *(dp constant; fixed-dp valid)*
* `ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(rows:array<CountRow>, N:int)`

> Note: `ASSERT_NO_VOLATILE_FIELDS` exists in L0 for emit-time hygiene, but L1 is I/O-free and does not need it.

---

## 1.3 From S0 / S1 / S2 · L0 (read-only / generic)

* **Ordering / numeric discipline (S0·L0):** `STABLE_SORT(seq, key)`, `CMP_ASCII(a,b)`, **Neumaier reductions** (if a kernel sums floats deterministically), and the **binary64 / RNE / no-FMA** numeric posture (policy).
* **Event shapes (S1·L0, S2·L0):** used **only** to understand inputs (`is_multi` from S1; `nb_final` payload echo μ, φ, N from S2). L1 does **not** write evidence or touch RNG surfaces.

> If an equivalent helper exists in S3·L0, prefer **S3·L0**.

---

## 1.4 Kernel → helper map (at a glance)

| L1 Kernel                    | Primary helpers used (all from **S3·L0** unless noted)                                                                                   |
|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `s3_build_ctx`               | `BUILD_CTX`                                                                                                                              |
| `s3_evaluate_rule_ladder`    | `BUILD_VOCAB_VIEWS`, `NORMALISE_REASON_CODES`, `NORMALISE_FILTER_TAGS`, `ASSERT_CHANNEL_IN_INGRESS_VOCAB`, `NORMALISE_AND_VALIDATE_ISO2` |
| `s3_make_candidate_set`      | `NORMALISE_AND_VALIDATE_ISO2`, `MAKE_REASON_CODES_FOR_CANDIDATE`, `MAKE_FILTER_TAGS_FOR_CANDIDATE`                                       |
| `s3_rank_candidates`         | `ASSIGN_STABLE_IDX`, `ADMISSION_ORDER_KEY`, `ORDER_FOREIGNS`, `RANK_CANDIDATES` *(uses `home_iso` from `Ctx`)*                           |
| `s3_compute_priors` (opt)    | `SELECT_PRIOR_DP`, `EVAL_PRIOR_SCORE`, `QUANTIZE_WEIGHT_TO_DP`, `ASSERT_PRIORS_BLOCK_SHAPE`                                              |
| `s3_integerise_counts` (opt) | `MAKE_SHARES_FOR_INTEGERISATION`, `MAKE_BOUNDS_FOR_INTEGERISATION`, `LRR_INTEGERISE`, `ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK`              |
| `s3_sequence_sites` (opt)    | `BUILD_SITE_SEQUENCE_FOR_COUNTRY`, `FORMAT_SITE_ID_ZEROPAD6`, `ASSERT_CONTIGUOUS_SITE_ORDER`                                             |
| `s3_package_outputs`         | *(no new helpers — shapes rows; L2 will attach lineage and emit)*                                                                        |

---

## 1.5 Explicit non-imports (to keep L1 pure)

* **RNG & evidence:** `begin_event_micro`, `end_event_emit`, `update_rng_trace_totals`, Philox substreams/samplers.
* **I/O & emitters:** dictionary resolvers, file writers, `EMIT_S3_*`, `FS.*`.
* **Wall-clock / timestamps:** any helper that injects time.
* **Policy authorship:** any function that mutates ladder/priors/bounds — L1 only **evaluates** fixed policy from BOM.

**Result.** With this import map, every S3·L1 kernel is a small, copy-pastable function that calls only pre-defined helpers, stays RNG-free and I/O-free, and returns arrays L2 can emit **without reshaping**.

---

# 2) Types & Shapes (+ IDs/Constants quick table)

**Goal.** Pin the exact **in-memory shapes** that S3·L1 kernels return so **L2 can attach lineage and emit *without reshaping***. All rows below are **schema-shaped minus lineage** (L1 does **not** populate `parameter_hash` / `manifest_fingerprint`; L2 will).

---

## 2.1 Record aliases (reference, not redefinition)

> All strings are ASCII; ISO codes are **uppercase ISO-3166-1 alpha-2**. Arrays noted “A→Z” are **deduped and sorted** lexicographically.

### `DecisionTrace`

* `reason_codes: string[]` — **closed set**, A→Z
* `filter_tags: string[]` — **closed set**, A→Z

### `CandidateRow`  *(unordered before ranking)*

* `merchant_id: u64`
* `country_iso: ISO2`  *(uppercase; member of BOM ISO set)*
* `is_home: bool`
* `reason_codes: string[]`  *(A→Z, closed set)*
* `filter_tags: string[]`   *(A→Z, closed set)*

### `RankedCandidateRow`  *(single source of inter-country order)*

* `merchant_id: u64`
* `country_iso: ISO2`
* `is_home: bool`
* `reason_codes: string[]` *(A→Z)*
* `filter_tags: string[]`  *(A→Z)*
* `candidate_rank: int32 ≥ 0` — **contiguous per merchant, home = 0**

### `PriorRow`  *(optional; scores, not probabilities)*

* `merchant_id: u64`
* `country_iso: ISO2`
* `base_weight_dp: string`  *(fixed-dp decimal string; see S3·L0 §7)*
* `dp: int32`  *(constant across the run/parameter set)*

### `CountRow`  *(optional; LRR integerisation)*

* `merchant_id: u64`
* `country_iso: ISO2`
* `count: int32 ≥ 0`
* `residual_rank: int32 ≥ 1`  *(1..M permutation per merchant slice)*

### `SequenceRow`  *(optional; within-country order)*

* `merchant_id: u64`
* `country_iso: ISO2`
* `site_order: int32 ≥ 1`  *(contiguous 1..nᵢ)*
* `site_id?: string`  *(optional; exactly 6 digits; zero-padded `site_order` when present)*

### `Ctx`  *(input to kernels; produced by L0)*

* `merchant_id: u64`
* `home_country_iso: ISO2`
* `channel: string`  *(ingress-provided closed vocabulary)*
* `N: int32`  *(S2 accepted draw, N ≥ 2)*
* `…`  *(pass-through references to ingress/S1/S2 rows, lineage fields, and BOM handle)*

---

## 2.2 Field-level guarantees (that L1 must uphold)

* **Order authority:** Only **`candidate_rank`** defines inter-country order (home rank 0; foreigns contiguous). File order is non-authoritative.
* **Closed vocabularies:** `reason_codes`, `filter_tags` originate **only** from the governed ladder; arrays are **A→Z** and **deduped**.
* **ISO discipline:** `country_iso` is canonical **uppercase** and a member of the BOM ISO set.
* **Priors semantics:** `base_weight_dp` is a **fixed-dp decimal string**; `dp` is **constant for the run**; **no renormalisation** anywhere in S3.
* **Integerisation semantics:** `Σ count = N` (from `Ctx`); `residual_rank` reflects the deterministic LRR tie-order (descending **quantised** residual, then ISO A→Z, then stable index).
* **Sequencing semantics:** Per-country `site_order = 1..nᵢ` contiguous; if `site_id` is present, it equals zero-padded `site_order` (width 6).

---

## 2.3 IDs & constants — quick table (for L2 hand-off)

| Dataset (L2 emits)      | Schema anchor             | Partition(s)     | Logical order (writer applies)                           |
|-------------------------|---------------------------|------------------|----------------------------------------------------------|
| `s3_candidate_set`      | `#/s3/candidate_set`      | `parameter_hash` | `(merchant_id ASC, candidate_rank ASC, country_iso ASC)` |
| `s3_base_weight_priors` | `#/s3/base_weight_priors` | `parameter_hash` | `(merchant_id ASC, country_iso ASC)`                     |
| `s3_integerised_counts` | `#/s3/integerised_counts` | `parameter_hash` | `(merchant_id ASC, country_iso ASC)`                     |
| `s3_site_sequence`      | `#/s3/site_sequence`      | `parameter_hash` | `(merchant_id ASC, country_iso ASC, site_order ASC)`     |

**Constants (referenced by kernels):**

* **Tie-break tuple (ranking key):** `(precedence, priority, rule_id, country_iso, stable_idx)`
* **`dp` (priors):** integer, **0..18**, **constant per run/parameter set**
* **`dp_resid` (residual binning):** default **8** (policy may override)
* **`SITE_ID_WIDTH`:** `6` → `site_id` format `^[0-9]{6}$`
* **Channel vocabulary (ingress):** **ingress-provided closed set** (passed in; not hard-coded)

---

## 2.4 Shape crosswalk (kernel outputs → emit rows)

* `s3_make_candidate_set` → `CandidateRow[]` *(unordered)*
* `s3_rank_candidates` → `RankedCandidateRow[]` → **L2 emits → `s3_candidate_set`**
* `s3_compute_priors` *(opt)* → `PriorRow[]` → **L2 emits → `s3_base_weight_priors`**
* `s3_integerise_counts` *(opt)* → `CountRow[]` → **L2 emits → `s3_integerised_counts`**
* `s3_sequence_sites` *(opt)* → `SequenceRow[]` → **L2 emits → `s3_site_sequence`**

*(All four are **schema-shaped minus lineage**; L2 adds `{parameter_hash, manifest_fingerprint}` and calls L0 emitters.)*

---

## 2.5 Invariants the shapes imply (fast checks L1 can call)

* **Candidate set:** exactly **one** `is_home=true`; no duplicate `country_iso`.
* **Ranking:** the `candidate_rank` set is **contiguous `0..K−1`** and includes exactly one row with `is_home=true ∧ candidate_rank=0`.
* **Priors:** all rows share the **same `dp`**; every `base_weight_dp` parses as valid fixed-dp.
* **Counts:** `Σ count == Ctx.N`; `residual_rank` is a **1..M permutation**.
* **Sequence:** per-country `site_order` is **1..nᵢ** contiguous; if present, `site_id == zero_pad(site_order, 6)`.

These definitions are the contract between **L1** and **L2/L3**: L1 returns exactly these shapes; L2 emits; L3 validates.

---

# 3) Feature Flags & Policy Handles (+ Flag Matrix)

**Goal.** Make it unambiguous which optional outputs S3·L1 must produce, which policies it may read, and what to do when a flag is enabled but the required policy is absent. Flags are **deterministic and run-constant** for a given `parameter_hash`. L1 only **evaluates** policy (never authors/edits it), and remains **pure/I-O-free**.

---

## 3.1 Inputs to L1 (and where they come from)

* **`feature_flags`** *(host-provided; run-constant under the same `parameter_hash`)*

  * `priors_enabled: bool`
  * `integerisation_enabled: bool`
  * `sequencing_enabled: bool`

* **Policy handles (opened once in L0 §3 via `OPEN_BOM_S3`)**

  * `priors_cfg?: PriorsCfg` — present iff priors policy exists; carries `dp:int`, `selection_rules`, `constants`.
  * `bounds_cfg?: BoundsCfg` — present iff bounds/thresholds policy exists; may carry `floors`, `ceilings`, `dp_resid`.

**Invariants**

* Flags **do not** change mid-run for a given `parameter_hash`.
* If a flag is **true**, the corresponding policy **must be present** (*except* integerisation, which is valid without `bounds_cfg`). Missing required policy ⇒ **merchant-scoped error** (see §3.4).

---

## 3.2 Kernel-facing contract (outputs per flag)

* **Always:** `RankedCandidateRow[]` (from `s3_rank_candidates`) — **single source of inter-country order** via `candidate_rank`.
* **If `priors_enabled`:** produce `PriorRow[]` (scores, fixed-dp string, constant `dp`).
* **If `integerisation_enabled`:** produce `CountRow[]` that sum to `Ctx.N` (LRR; floors/ceilings applied when provided).
* **If `sequencing_enabled`:** produce `SequenceRow[]` (per-country contiguous `site_order`, optional 6-digit `site_id`).

**Dependency rule:** `sequencing_enabled == true` **requires** `integerisation_enabled == true` (sequencing needs counts). If violated ⇒ **error**.

---

## 3.3 Flag Matrix (inputs → outputs → required policy)

| `priors_enabled` | `integerisation_enabled` | `sequencing_enabled` | L1 Outputs (in addition to `RankedCandidateRow[]`) | Policy required                        | Notes                                                         |
|------------------|--------------------------|----------------------|----------------------------------------------------|----------------------------------------|---------------------------------------------------------------|
| false            | false                    | false                | *(none)*                                           | *(none)*                               | Candidates only; L2 later emits `candidate_set`.              |
| true             | false                    | false                | `PriorRow[]`                                       | `priors_cfg`                           | Scores only; **no** counts/sequence.                          |
| false            | true                     | false                | `CountRow[]`                                       | *(bounds_cfg optional)*               | Shares = **uniform** (no priors); floors/ceilings if present. |
| true             | true                     | false                | `PriorRow[]`, `CountRow[]`                         | `priors_cfg` (+ `bounds_cfg` optional) | Counts use priors→shares (zero/missing prior ⇒ zero weight).  |
| false            | true                     | true                 | `CountRow[]`, `SequenceRow[]`                      | *(bounds_cfg optional)*               | **Valid** (counts required for sequencing).                   |
| true             | true                     | true                 | `PriorRow[]`, `CountRow[]`, `SequenceRow[]`        | `priors_cfg` (+ `bounds_cfg` optional) | Full pipeline.                                                |

**Invalid combination:** `sequencing_enabled && !integerisation_enabled` ⇒ **error**.

---

## 3.4 Error posture (merchant-scoped, non-emitting)

L1 **raises** (no best-effort) on:

* **Policy missing / dependency broken**

  * `priors_enabled && priors_cfg == null` ⇒ `ERR_S3_PRIOR_DISABLED` *(or `ERR_S3_AUTHORITY_MISSING` if BOM load failed)*.
  * `sequencing_enabled && !integerisation_enabled` ⇒ `ERR_S3_SEQ_DOMAIN`.
* **Policy malformed**

  * `priors_cfg.dp` not integer or out of `[0..18]` ⇒ `ERR_S3_PRIOR_DOMAIN`.
  * `bounds_cfg` floors/ceilings inconsistent ⇒ `ERR_S3_INT_DOMAIN`.
* **Runtime infeasible**

  * Integerisation cannot place all `N` units under ceilings/floors ⇒ `ERR_S3_INT_INFEASIBLE`.

All errors are **merchant-scoped**; L2 decides whether to skip or halt the run.

---

## 3.5 Determinism rules tied to flags

* **Priors**

  * `dp` is **constant per run/parameter set**, taken from `priors_cfg`.
  * `base_weight_dp` strings are produced via **base-10 half-even** quantisation (L0 §7). **No renormalisation**.
* **Integerisation**

  * Largest-Remainder on **deterministic shares** (priors→shares or uniform fallback).
  * Residuals quantised by `dp_resid` (default **8**, or from `bounds_cfg`).
* **Sequencing**

  * Per-country `site_order = 1..nᵢ`; optional `site_id = zero_pad(site_order, 6)`.

---

## 3.6 Tiny interface L1 expects the host to pass

```
feature_flags: {
  priors_enabled: bool,
  integerisation_enabled: bool,
  sequencing_enabled: bool
}

bom_handles: {
  ladder: Ladder,               // required
  iso_universe: ISOUniverse,    // required
  priors_cfg?: PriorsCfg,       // required iff priors_enabled
  bounds_cfg?: BoundsCfg        // optional; used iff integerisation_enabled
}
```

**Pre-flight checks (once at L1 entry):**

* If `priors_enabled`, assert `priors_cfg` present and `dp ∈ [0..18]`.
* If `sequencing_enabled`, assert `integerisation_enabled` is `true`.
* If `bounds_cfg` present, assert floors/ceilings consistency; set `dp_resid := bounds_cfg.dp_resid ?? 8`.

---

## 3.7 Efficiency implications (so flags don’t surprise the host)

* **Priors:** adds **O(k)** arithmetic + a final **O(k log k)** sort for output order.
* **Integerisation:** adds two **O(k log k)** sorts (eligibles + residual rank) + linear arithmetic.
* **Sequencing:** adds **O(∑nᵢ)** to build rows + **O(k log k)** for final country order.
* **Memory:** remains **O(k)** (plus **O(∑nᵢ)** for sequencing rows).

---

## 3.8 One-screen “what happens if…?” (developer crib)

* **Only candidates:** all flags `false` → build ctx → evaluate ladder → candidates → rank → **package(candidate_set)**.
* **Candidates + priors:** `priors=true` → above + compute priors (scores) → **package(candidate_set, priors)**.
* **Candidates + counts:** `integerisation=true` (priors may be off) → above + integerise (uniform shares if priors off) → **package(candidate_set, counts)**.
* **Full:** all flags `true` (and policies present) → **package(candidate_set, priors, counts, sequence)**.

This matrix and the contracts above ensure an implementer always knows **exactly** which arrays L1 returns, which policies must exist, and how to fail fast when a dependency is unmet—keeping implementation **friction-free**.

---

# 4) Error Vocabulary (L1 surface)

**What this is.** A small, stable set of **merchant-scoped**, **non-emitting** errors that L1 kernels may raise when a contract is violated. L1 is **pure** (no I/O, no RNG), so failures are **deterministic** and reproducible. **L2** decides how to handle a failed merchant; **L3** may mirror these codes in validation reports.

---

## 4.1 Error payload (host-neutral shape)

Each kernel raises an object with at least:

* `code: string` — one of the codes below
* `message: string` — short, stable explanation (no stack traces)
* `where: string` — `"<kernel>/<step>"` (e.g., `"s3_rank_candidates/contiguity"`)
* `merchant_id: u64`
* `context: { … }` — minimal facts (e.g., offending `country_iso`, expected vs observed sizes)
* `lineage?: { parameter_hash: Hex64, manifest_fingerprint: Hex64 }` — optional (echoed from `Ctx` when available)

> **Scope:** merchant only. L1 never writes; there are **no partial emits**.

---

## 4.2 Context & gating

* **`ERR_S3_CTX_MISSING_INPUTS`** — `s3_build_ctx`: a required upstream row (ingress / S1 hurdle / S2 `nb_final`) is absent.
* **`ERR_S3_CTX_MULTIPLE_INPUTS`** — more than one upstream row where **exactly one** is required.
* **`ERR_S3_CTX_LINEAGE_MISMATCH`** — upstream rows disagree on `parameter_hash` / `manifest_fingerprint`.
* **`ERR_S3_CTX_ENTRY_GATES`** — entry preconditions fail: `is_multi != true` **or** `N < 2`.

**Effect:** stop L1 for this merchant; no arrays produced.

---

## 4.3 BOM / policy

* **`ERR_S3_AUTHORITY_MISSING`** — required BOM artefact handle missing (ladder / ISO / priors / bounds per flags).
* **`ERR_S3_RULE_LADDER_INVALID`** — ladder not a total order **or** closed sets invalid (caught in L0; surfaced when used).
* **`ERR_S3_POLICY_DEPENDENCY`** — flags demand a policy that isn’t present (e.g., `priors_enabled=true` but `priors_cfg=null`).

---

## 4.4 Closed vocabularies & ISO

* **`ERR_S3_RULE_EVAL_DOMAIN`** — unknown `reason_code` / `filter_tag` **or** `channel` not in closed vocabularies.
* **`ERR_S3_ISO_INVALID_FORMAT`** — not exactly two ASCII letters.
* **`ERR_S3_ISO_NOT_IN_UNIVERSE`** — canonical ISO not in the BOM ISO set.

Raised by: `s3_evaluate_rule_ladder`, `s3_make_candidate_set`.

---

## 4.5 Candidate set & ranking

* **`ERR_S3_RANK_DOMAIN`** — candidate domain error: missing **single** home, duplicate `country_iso`, or **rank set not contiguous `0..K−1`**.
* **`ERR_S3_ORDER_KEY_DOMAIN`** — admission metadata invalid for a foreign (missing/ill-typed `(precedence, priority, rule_id)`).

Raised by: `s3_make_candidate_set` (home/dupes), `s3_rank_candidates` (key/contiguity).

---

## 4.6 Priors (scores, not probabilities)

* **`ERR_S3_PRIOR_DISABLED`** — `priors_enabled=true` but `priors_cfg` absent.
* **`ERR_S3_PRIOR_DOMAIN`** — invalid dp or score: `dp ∉ [0..18]`, NaN/Inf/negative score, or policy hook returned an invalid value.
* **`ERR_S3_PRIOR_DP_INCONSISTENT`** — observed `dp` not constant within the run slice (should not occur if using `priors_cfg.dp`).
* **`ERR_S3_FIXED_DP_FORMAT`** — `base_weight_dp` not a valid fixed-dp decimal string.

Raised by: `s3_compute_priors`.

---

## 4.7 Integerisation (Largest-Remainder)

* **`ERR_S3_INT_DOMAIN`** — bad inputs to integerisation (negative `N`, malformed bounds, vector length mismatches).
* **`ERR_S3_INT_INFEASIBLE`** — infeasible under bounds: `sum(floors) > N` or not enough capacity after ceilings to place all `N`.
* **`ERR_S3_ASSERT_DOMAIN`** — post-condition failure (e.g., `Σ count ≠ N`) — defensive catch; should not occur when the wrapper is used correctly.

Raised by: `s3_integerise_counts`.

---

## 4.8 Sequencing (within-country)

* **`ERR_S3_SEQ_DOMAIN`** — dependency violation or bad input (e.g., sequencing enabled without integerisation; missing counts).
* **`ERR_S3_SEQ_RANGE`** — per-country count exceeds supported `SITE_ID_MAX` when `site_id` is requested.
* **`ERR_S3_SEQ_NONCONTIGUOUS`** — `site_order` not contiguous `1..nᵢ`, or `site_id` ≠ zero-padded order when present.

Raised by: `s3_sequence_sites`.

---

## 4.9 Flag dependency & packaging

* **`ERR_S3_FLAG_MATRIX`** — invalid flag combination (e.g., `sequencing_enabled=true` while `integerisation_enabled=false`).
* **`ERR_S3_PACKAGE_SHAPE`** — internal consistency failure when assembling the outputs struct (e.g., sequence returned without counts).

Raised by: pre-flight flag checks, `s3_package_outputs`.

---

## 4.10 Severity & handling guidance (for L2/L3)

* **Severity:** all L1 errors are **blocking for that merchant**; other merchants are unaffected.
* **Emit behavior:** none — L1 never writes. L2 should **not** emit partial datasets for a failing merchant.
* **Logging:** include `merchant_id`, `code`, `where`, and the smallest useful `context` (e.g., offending ISO).
* **Validation parity:** L3 can raise the same codes when verifying emitted bytes (e.g., rank contiguity, `Σ count = N`, fixed-dp parse).

---

## 4.11 “Where raised” index (kernel → codes)

* `s3_build_ctx` → `ERR_S3_CTX_*`
* `s3_evaluate_rule_ladder` → `ERR_S3_RULE_EVAL_DOMAIN`, `ERR_S3_ISO_*`, `ERR_S3_AUTHORITY_MISSING`
* `s3_make_candidate_set` → `ERR_S3_RANK_DOMAIN`, `ERR_S3_ISO_*`
* `s3_rank_candidates` → `ERR_S3_ORDER_KEY_DOMAIN`, `ERR_S3_RANK_DOMAIN`
* `s3_compute_priors` → `ERR_S3_PRIOR_*`, `ERR_S3_FIXED_DP_FORMAT`
* `s3_integerise_counts` → `ERR_S3_INT_*`, `ERR_S3_ASSERT_DOMAIN`
* `s3_sequence_sites` → `ERR_S3_SEQ_*`
* `s3_package_outputs` → `ERR_S3_FLAG_MATRIX`, `ERR_S3_PACKAGE_SHAPE`

**Result:** This vocabulary gives each kernel a clear, minimal, deterministic failure surface that implementers can wire directly to host handling — **no ambiguity, no surprises**.

---

# 5) Call-Graph & Dataflow (no I/O)

**Goal.** Show—at a glance—how S3·L1 kernels compose per merchant: what each consumes, what it returns, and where feature flags branch. Everything is **pure, deterministic, RNG-free, and I/O-free**.

---

## 5.1 One-screen call graph (per merchant)

```
OPEN_BOM_S3        BUILD_CTX                     // L0 (done once per run/slice; no I/O in L1)
     │                 │
     └──► s3_build_ctx(Ctx) ────────────────────────────────────────┐
                               │                                     │
                               ▼                                     │
                     s3_evaluate_rule_ladder ──► DecisionTrace       │
                               │                                     │
                               ▼                                     │
                        s3_make_candidate_set ──► CandidateRow[]     │
                               │                                     │
                               ▼                                     │
                        s3_rank_candidates ────► RankedCandidateRow[]│
                               │                 (candidate_rank)    │
                 ┌─────────────┴──────────────┐                      │
                 │ priors_enabled?            │                      │
                 │        yes                 │ no                   │
                 ▼                            │                      │
             s3_compute_priors ───► PriorRow[]                       │
                 │                                                    │
                 └───────────┬────────────────────────────────────────┘
                             │ integerisation_enabled?
                             │
                  yes ───────▼─────────── no
                      s3_integerise_counts ───► CountRow[]
                             │
                             │ sequencing_enabled?
                             │
                  yes ───────▼─────────── no
                      s3_sequence_sites ───► SequenceRow[]

                               ▼
                       s3_package_outputs
             ⇒ { candidate_set, priors?, counts?, sequence? }
```

---

## 5.2 Pre-flight & branch rules (flags → kernels)

1. **Always** run: `s3_build_ctx → s3_evaluate_rule_ladder → s3_make_candidate_set → s3_rank_candidates`.
2. If `priors_enabled`, run `s3_compute_priors`.
3. If `integerisation_enabled`, run `s3_integerise_counts` (shares = **priors→shares** when priors exist, else **uniform**).
4. If `sequencing_enabled`, require `integerisation_enabled == true`, then run `s3_sequence_sites`.
5. `s3_package_outputs` returns only the arrays produced by the chosen path.

**Invalid:** `sequencing_enabled && !integerisation_enabled` ⇒ **raise** and return **no arrays** for this merchant.

---

## 5.3 Kernel I/O contract (values only; shapes are schema-aligned)

| Step                         | Consumes                                                           | Produces (in-memory)                           |
|------------------------------|--------------------------------------------------------------------|------------------------------------------------|
| `s3_build_ctx`               | Ingress row, S1 hurdle row, S2 `nb_final`, BOM, **channel_vocab**  | `Ctx` (gates passed; ISO/channel canonical)    |
| `s3_evaluate_rule_ladder`    | `Ctx`, `BOM.ladder`, **channel_vocab**                             | `DecisionTrace{reason_codes[], filter_tags[]}` |
| `s3_make_candidate_set`      | `Ctx`, `DecisionTrace`, `BOM.iso_universe`                         | `CandidateRow[]` (unordered)                   |
| `s3_rank_candidates`         | `CandidateRow[]`, **home ISO from `Ctx`**, admission meta (ladder) | `RankedCandidateRow[]` (`candidate_rank`)      |
| `s3_compute_priors` (opt)    | `RankedCandidateRow[]`, `Ctx`, `priors_cfg`                        | `PriorRow[]`                                   |
| `s3_integerise_counts` (opt) | `RankedCandidateRow[]`, `Ctx.N`, `PriorRow[]?`, `bounds_cfg?`      | `CountRow[]` (Σcount = `Ctx.N`)                |
| `s3_sequence_sites` (opt)    | `RankedCandidateRow[]`, `CountRow[]`, `Ctx`                        | `SequenceRow[]` (per-country contiguous)       |
| `s3_package_outputs`         | All produced arrays                                                | `{candidate_set, priors?, counts?, sequence?}` |

> All arrays are **schema-shaped minus lineage**. L2 adds `{parameter_hash, manifest_fingerprint}` and emits via S3·L0.

---

## 5.4 Determinism anchors (used along the path)

* **Ordering:** stable sorts with fully specified keys; inter-country order **only** via `candidate_rank` (home = 0; contiguous).
* **Priors:** fixed-dp strings via base-10 half-even; `dp` constant per run/parameter set.
* **Integerisation:** Largest-Remainder with residuals quantised at `dp_resid` (default 8) before tie-break; floors/ceilings enforced.
* **Sequencing:** `site_order = 1..nᵢ` contiguous per country; optional 6-digit `site_id = zero_pad(site_order)`.

---

## 5.5 Error propagation (merchant-scoped, non-emitting)

* **Context gates:** missing inputs; lineage mismatch; `is_multi != true`; `N < 2`.
* **Policy/domain:** unknown ISO/vocab; duplicate countries; missing single home.
* **Ranking:** bad admission metadata; non-contiguous ranks.
* **Priors:** missing/invalid `priors_cfg`; invalid `dp` or fixed-dp string.
* **Integerisation:** infeasible under bounds (e.g., `Σ floors > N`, or insufficient capacity under ceilings).
* **Sequencing:** dependency violation (no counts), out-of-range per-country totals, non-contiguous site order.
* **Packaging:** inconsistent flag matrix (e.g., sequence without counts).

On any error, L1 returns **no arrays** for that merchant. L2 decides handling.

---

## 5.6 Efficiency profile (per merchant slice)

* **Ranking:** **O(k log k)**, memory **O(k)**.
* **Priors:** O(k) arithmetic + final **O(k log k)** order.
* **Integerisation:** **O(k log k)** (two sorts) + linear arithmetic; memory **O(k)**.
* **Sequencing:** **O(∑nᵢ)** build + **O(k log k)** final country order.
* **No global materialisation**; arrays are slice-local and trivially parallel across merchants (L2 concern).

---

## 5.7 Minimal end-to-end pseudocode (host-neutral, no I/O)

```
PROC s3_process_merchant(ingress, s1, s2, bom, flags) ->
     {candidate_set, priors?, counts?, sequence?}

  ctx    := s3_build_ctx(ingress, s1, s2, bom, channel_vocab)
  trace  := s3_evaluate_rule_ladder(ctx, bom.ladder, channel_vocab)
  cand   := s3_make_candidate_set(ctx, trace, bom.iso_universe)

  // derive admission metadata (precedence, priority, rule_id) per foreign from ladder—pure, no I/O
  meta   := admission_meta_from_ladder(bom.ladder)

  ranked := s3_rank_candidates(cand, meta, ctx.home_country_iso)
  out    := { candidate_set: ranked }

  IF flags.priors_enabled:
    pri        := s3_compute_priors(ranked, ctx, bom.priors_cfg)
    out.priors := pri

  IF flags.integerisation_enabled:
    cnt         := s3_integerise_counts(ranked, ctx.N, out.priors?, bom.bounds_cfg?)
    out.counts  := cnt

    IF flags.sequencing_enabled:
      seq          := s3_sequence_sites(ranked, cnt, ctx /* with_site_id per policy/host */)
      out.sequence := seq

  RETURN out
```

> `derive_admission_meta_from_ladder(…)` is a **pure L1 derivation** of `(precedence, priority, rule_id)` per foreign ISO from the ladder (no I/O, no RNG).

---

**Result.** This section keeps §5 strictly **L1-level**: a small call graph, exact value contracts, deterministic anchors, and minimal pseudocode—ready for implementers, with zero L2/L3 noise.

---

# 5a) Data Shapes at Each Step (one-liner map)

> All arrays are **schema-shaped minus lineage** (`parameter_hash`, `manifest_fingerprint` are attached later by L2). ISO codes are **uppercase**; arrays marked “A→Z” are **deduped & sorted** (ASCII).

* **`s3_build_ctx` → `Ctx`**
  `{ merchant_id:u64, home_country_iso:ISO2, channel:string /* ingress closed set */, N:int≥2, … }`
  *(Plus pass-through refs to ingress/S1/S2 rows and BOM handle; **entry gates satisfied**.)*

* **`s3_evaluate_rule_ladder` → `DecisionTrace`**
  `{ reason_codes:string[] /* A→Z, closed */, filter_tags:string[] /* A→Z, closed */ }`

* **`s3_make_candidate_set` → `CandidateRow[]` (unordered)**
  Each: `{ merchant_id:u64, country_iso:ISO2, is_home:bool, reason_codes:string[] /* A→Z */, filter_tags:string[] /* A→Z */ }`
  *(Exactly one `is_home=true`; **no duplicate `country_iso`** per merchant; ISO ∈ BOM set.)*

* **`s3_rank_candidates` → `RankedCandidateRow[]`**
  Each: `{ merchant_id:u64, country_iso:ISO2, is_home:bool, reason_codes:string[] /* A→Z */, filter_tags:string[] /* A→Z */, candidate_rank:int≥0 }`
  *(Inter-country order = **`candidate_rank` only**; **home=0**; ranks contiguous **0..K−1**.)*

* **(opt) `s3_compute_priors` → `PriorRow[]`**
  Each: `{ merchant_id:u64, country_iso:ISO2, base_weight_dp:FixedDpDecStr, dp:int }`
  *(**Scores, not probabilities**; `dp` ∈ `[0..18]`, **constant per run/parameter set**.)*

* **(opt) `s3_integerise_counts` → `CountRow[]`**
  Each: `{ merchant_id:u64, country_iso:ISO2, count:int≥0, residual_rank:int≥1 }`
  *(Σ `count` = `Ctx.N`; `residual_rank` is a **1..M permutation** for the slice.)*

* **(opt) `s3_sequence_sites` → `SequenceRow[]`**
  Each: `{ merchant_id:u64, country_iso:ISO2, site_order:int≥1, site_id?:string /* 6 digits */ }`
  *(Per-country `site_order` is **1..nᵢ** contiguous; if present, `site_id == zero_pad(site_order, 6)`.)*

* **`s3_package_outputs` → `{ candidate_set, priors?, counts?, sequence? }`**
  `candidate_set: RankedCandidateRow[]; priors?: PriorRow[]; counts?: CountRow[]; sequence?: SequenceRow[]`
  *(Arrays are ready for L2 emitters; **L2 attaches lineage and writes** to S3 datasets.)*

---

# 6) Kernel — `s3_build_ctx` (Ctx assembly)

**Mission.** Build a clean, deterministic **`Ctx`** for one merchant by stitching together the three authoritative upstream rows and the BOM—**without I/O** and **without RNG**—so all downstream kernels run on a canonical, validated basis.

---

## 6.1 Contract (what this kernel guarantees)

* **Pure & deterministic.** No I/O, no RNG, no wall-clock.
* **Entry gates enforced.** `is_multi == true` (from S1) and **`N ≥ 2`** (accepted draw from S2).
* **Lineage equality.** `parameter_hash` and `manifest_fingerprint` **match** across ingress, S1, S2.
* **Canonical fields.** `home_country_iso` is **uppercase ISO2** and a **member** of the BOM ISO set; `channel` is in the **ingress closed vocabulary**.
* **One output.** A single `Ctx` record; failure is **merchant-scoped** and **non-emitting** (L1 returns no arrays for this merchant).

---

## 6.2 Inputs & outputs (values only)

**Inputs (host passes values; L1 does not read files):**

* `ingress_rows: array<Record>`     // 0..1 row for this merchant
* `s1_hurdle_rows: array<Record>`   // 0..1
* `s2_nb_final_rows: array<Record>` // 0..1 (the **non-consuming** final from S2)
* `bom: BOM`                        // already opened in L0 (ladder, ISO, optional policies)
* `channel_vocab: Set<string>`      // ingress-provided closed set (passed in; not hard-coded)

**Output:**

* `Ctx = { merchant_id:u64, home_country_iso:ISO2, channel:string, N:int≥2, s1_is_multi:bool, ingress_row, s1_hurdle_row, s2_nb_final_row, lineage:{parameter_hash,manifest_fingerprint}, bom }`

---

## 6.3 Errors this kernel may raise (merchant-scoped)

* `ERR_S3_CTX_MISSING_INPUTS`, `ERR_S3_CTX_MULTIPLE_INPUTS`, `ERR_S3_CTX_LINEAGE_MISMATCH`, `ERR_S3_CTX_ENTRY_GATES`
* `ERR_S3_AUTHORITY_MISSING` (if `bom` lacks required handles), `ERR_S3_RULE_EVAL_DOMAIN` (channel), `ERR_S3_ISO_INVALID_FORMAT`, `ERR_S3_ISO_NOT_IN_UNIVERSE`

---

## 6.4 Dependencies (helpers reused; all pre-defined in L0)

* `ASSERT_SINGLETON(rows,label)`
* `ASSERT_LINEAGE_EQUAL(a,b)`
* `ASSERT_CHANNEL_IN_INGRESS_VOCAB(ch, channel_vocab:Set<string>)`
* `NORMALISE_AND_VALIDATE_ISO2(s, bom.iso_universe.set) -> ISO2`
* `ASSERT_S2_ACCEPTED_N(N)` *(checks N≥2)*

> **Note.** This kernel is a thin wrapper around **`S3L0.BUILD_CTX`** for single-sourcing. Implementations may simply call `S3L0.BUILD_CTX(ingress_rows, s1_hurdle_rows, s2_nb_final_rows, bom, channel_vocab)` and forward any errors.

---

## 6.5 Pseudocode (language-agnostic, I/O-free)

```
PROC s3_build_ctx(ingress_rows, s1_hurdle_rows, s2_nb_final_rows, bom, channel_vocab) -> Ctx

  // ---- 0) BOM presence (opened in L0) ----
  REQUIRES bom != null AND bom.ladder != null AND bom.iso_universe != null

  // ---- 1) Uniqueness per upstream surface ----
  CALL ASSERT_SINGLETON(ingress_rows,     "ingress")
  CALL ASSERT_SINGLETON(s1_hurdle_rows,   "s1.hurdle")
  CALL ASSERT_SINGLETON(s2_nb_final_rows, "s2.nb_final")

  LET ingress := ingress_rows[0]
  LET s1      := s1_hurdle_rows[0]
  LET s2      := s2_nb_final_rows[0]

  // ---- 2) Merchant & lineage equality ----
  // Inline merchant-id equality (L0 has no dedicated helper for ID equality)
  IF ingress.merchant_id != s1.merchant_id: RAISE ERR_S3_CTX_LINEAGE_MISMATCH
  IF ingress.merchant_id != s2.merchant_id: RAISE ERR_S3_CTX_LINEAGE_MISMATCH
  CALL ASSERT_LINEAGE_EQUAL(ingress, s1)
  CALL ASSERT_LINEAGE_EQUAL(ingress, s2)

  // ---- 3) Entry gates for S3 ----
  IF s1.is_multi != true: RAISE ERR_S3_CTX_ENTRY_GATES
  CALL ASSERT_S2_ACCEPTED_N(s2.n_outlets)  // N ≥ 2

  // ---- 4) Closed vocabularies & ISO canonicalisation ----
  CALL ASSERT_CHANNEL_IN_INGRESS_VOCAB(ingress.channel, channel_vocab)
  LET home_iso := NORMALISE_AND_VALIDATE_ISO2(ingress.home_country_iso, bom.iso_universe.set)

  // ---- 5) Assemble lineage echo (path=embed checked later by L2) ----
  LET lineage := {
    parameter_hash:       ingress.parameter_hash,
    manifest_fingerprint: ingress.manifest_fingerprint
  }

  // ---- 6) Construct Ctx (pure value) ----
  RETURN {
    merchant_id      : ingress.merchant_id,
    home_country_iso : home_iso,
    channel          : ingress.channel,
    N                : s2.n_outlets,     // authoritative total sites for S3
    s1_is_multi      : s1.is_multi,
    ingress_row      : ingress,
    s1_hurdle_row    : s1,
    s2_nb_final_row  : s2,
    lineage          : lineage,
    bom              : bom
  }

END PROC
```

---

## 6.6 Determinism & complexity

* **Determinism.** Pure computation; no I/O; relies only on input values and BOM content; identical inputs yield identical outputs.
* **Complexity.** **O(1)** per merchant (membership checks/normalisation are constant-time on small strings; ISO set lookup O(1)).

---

## 6.7 Edge cases (explicit)

* **`N ∈ {0,1}`**: rejected by `ASSERT_S2_ACCEPTED_N` (S2 guarantees accepted **N ≥ 2**).
  *(Any references to `N=0` behavior in later optional kernels are **defensive** only and **unreachable under S3 gates**.)*
* **Channel missing or unknown**: `ERR_S3_RULE_EVAL_DOMAIN`.
* **Home ISO lower-case or aliased**: normalised to **uppercase**, then membership-checked; invalid raises `ERR_S3_ISO_*`.
* **Mixed lineage or merchant IDs**: `ERR_S3_CTX_LINEAGE_MISMATCH`; the merchant is skipped by L2.

---

## 6.8 Interface for downstream kernels

`Ctx` provides everything S3 needs, so downstream kernels take **only** `Ctx` and the relevant BOM handles:

* `s3_evaluate_rule_ladder(Ctx, bom.ladder, channel_vocab)`
* `s3_make_candidate_set(Ctx, DecisionTrace, bom.iso_universe)`
* `s3_rank_candidates(CandidateRow[], admission_meta_from_ladder(bom.ladder), Ctx.home_country_iso)`
* *(optional)* `s3_compute_priors(RankedCandidateRow[], Ctx, bom.priors_cfg)`
* *(optional)* `s3_integerise_counts(RankedCandidateRow[], Ctx.N, priors?, bom.bounds_cfg?)`
* *(optional)* `s3_sequence_sites(RankedCandidateRow[], CountRow[], Ctx, with_site_id)`

**Result.** With `s3_build_ctx` in place, every later kernel runs on a **canonical, validated** basis—no re-checks, no ambiguity, and no hidden I/O.

---

# 7) Kernel — `s3_evaluate_rule_ladder` (policy apply)

**Mission.** Deterministically apply the governed **rule ladder** to a merchant’s `Ctx` and produce a clean, closed-vocabulary **`DecisionTrace`**: `reason_codes[]` and `filter_tags[]`, both **A→Z** and **deduped**. **No I/O. No RNG.**

---

## 7.1 Contract (what this kernel guarantees)

* **Pure & deterministic.** No I/O, no RNG, no wall-clock.
* **Closed sets only.** Every `reason_code` and `filter_tag` belongs to the ladder’s governed vocabularies.
* **Stable ordering.** Returned arrays are **A→Z** (ASCII) and **deduped**.
* **Merchant-scoped.** Errors affect only this merchant; on failure, L1 returns **no arrays** for this merchant.

---

## 7.2 Inputs & outputs (values only)

**Inputs**

* `ctx : Ctx` — from §6; gates satisfied; ISO/channel canonical.
* `ladder : Ladder` — from BOM; total-ordered rules; exposes **closed** `reason_codes` / `filter_tags`.
* `channel_vocab : Set<string>` — ingress-provided closed set (passed in; not hard-coded).

**Output**

* `DecisionTrace = { reason_codes: string[] /* A→Z, closed */, filter_tags: string[] /* A→Z, closed */ }`

*(A transient `rule_trace[]` for diagnostics is host-optional and **not** part of this API.)*

---

## 7.3 Errors this kernel may raise

* `ERR_S3_AUTHORITY_MISSING` — ladder handle missing.
* `ERR_S3_RULE_LADDER_INVALID` — ladder not a total order or vocabs invalid (should have been caught at BOM open; surfaced here if encountered).
* `ERR_S3_RULE_EVAL_DOMAIN` — unknown `reason_code`/`filter_tag`, or `ctx.channel` not in the ingress vocabulary.

---

## 7.4 Helpers reused (all from L0; no new definitions)

* `BUILD_VOCAB_VIEWS(ladder) -> { REASONS:Set<string>, TAGS:Set<string> }`
* `NORMALISE_REASON_CODES(codes, REASONS) -> array<string>`  *(A→Z, closed, dedup)*
* `NORMALISE_FILTER_TAGS(tags, TAGS) -> array<string>`       *(A→Z, closed, dedup)*
* `ASSERT_CHANNEL_IN_INGRESS_VOCAB(ctx.channel, channel_vocab:Set<string>)`
* *(Policy hook, deterministic)* `MATCHES_RULE(ctx, rule) -> bool` and `RULE_OUTCOME(rule) -> { reason_code?:string, tags?:array<string> }`
  *(Data-driven by the ladder policy; L1 does not author policy.)*

---

## 7.5 Pseudocode (language-agnostic, I/O-free)

```
PROC s3_evaluate_rule_ladder(ctx: Ctx, ladder: Ladder, channel_vocab: Set<string>) -> DecisionTrace

  // ---- 0) Authority presence & basic gate ----
  REQUIRES ladder != null
  CALL ASSERT_CHANNEL_IN_INGRESS_VOCAB(ctx.channel, channel_vocab)   // may raise ERR_S3_RULE_EVAL_DOMAIN

  // ---- 1) Build closed-set views once (O(|vocab|)) ----
  LET { REASONS, TAGS } := BUILD_VOCAB_VIEWS(ladder)

  // ---- 2) Evaluate rules in the ladder’s total order ----
  LET buf_reasons := EMPTY_ARRAY()
  LET buf_tags    := EMPTY_ARRAY()

  // Rules are total-ordered (e.g., by (precedence, priority, rule_id))
  FOR EACH rule IN ladder.rules:
    IF NOT MATCHES_RULE(ctx, rule): CONTINUE

    LET out := RULE_OUTCOME(rule)  // {reason_code?:string, tags?:array<string>}

    // Collect reason_code when present (closed-set guarded)
    IF HAS_KEY(out, "reason_code") AND out.reason_code != null:
      IF NOT CONTAINS(REASONS, out.reason_code): RAISE ERR_S3_RULE_EVAL_DOMAIN
      APPEND(buf_reasons, out.reason_code)

    // Collect tags when present (closed-set guarded)
    IF HAS_KEY(out, "tags") AND out.tags != null:
      FOR EACH t IN out.tags:
        IF NOT CONTAINS(TAGS, t): RAISE ERR_S3_RULE_EVAL_DOMAIN
        APPEND(buf_tags, t)

  // ---- 3) Canonicalise: A→Z + dedup (host-identical) ----
  LET reason_codes := NORMALISE_REASON_CODES(buf_reasons, REASONS)
  LET filter_tags  := NORMALISE_FILTER_TAGS(buf_tags, TAGS)

  RETURN { reason_codes, filter_tags }
END PROC
```

---

## 7.6 Determinism & complexity

* **Determinism.** Output is a pure function of `(ctx, ladder, channel_vocab)`; ladder order is fixed; canonicalisation is ASCII A→Z.
* **Complexity.** `O(#rules)` to scan + `O(r log r + t log t)` to sort/dedup reason codes/tags (typically small).

---

## 7.7 Edge cases (explicit)

* **No rules fire:** returns `{ reason_codes:[], filter_tags:[] }` (legal; candidate assembly still proceeds; home exists by contract).
* **Duplicate emissions:** duplicates are collapsed by canonicalisation.
* **Policy emits nothing but later flags require priors/integerisation:** fine—integerisation falls back to **uniform** shares when priors are absent/zero (§3).

---

## 7.8 Interface to the next steps

* `DecisionTrace` feeds **`s3_make_candidate_set`** to annotate candidate rows **per merchant** (not per country).
* Admission metadata for ranking `(precedence, priority, rule_id)` per foreign ISO is derived **separately** from the ladder and consumed by **`s3_rank_candidates`**—pure mapping, no I/O.

**Result.** `s3_evaluate_rule_ladder` yields a closed-set, canonical trace that downstream kernels can use without re-checking policy or vocab semantics—**zero ambiguity** for implementers.

---

# 8) Kernel — `s3_make_candidate_set`

**Mission.** Deterministically build the **unordered** candidate set for a merchant: `{home} ∪ admissible_foreigns`, and annotate each row with **closed-vocabulary, A→Z** `reason_codes[]` and `filter_tags[]`. **No I/O. No RNG.**

---

## 8.1 Contract (what this kernel guarantees)

* **Pure & deterministic.** No I/O, no RNG, no wall-clock.
* **Exactly one home.** The merchant’s `home_country_iso` is present **once** with `is_home=true`.
* **No duplicates.** Each `country_iso` appears at most once.
* **Closed sets.** `reason_codes[]` and `filter_tags[]` on every row come from governed sets, are **deduped**, and **A→Z**.
* **Unordered output.** Inter-country **order is not encoded here**; ranking happens in §9.

---

## 8.2 Inputs & outputs (values only)

**Inputs**

* `ctx : Ctx` — from §6; `home_country_iso` canonical; `N≥2`; lineage consistent.
* `trace : DecisionTrace` — from §7; `reason_codes[]` / `filter_tags[]` already **A→Z** and **closed-set**.
* `iso_universe : ISOUniverse` — from BOM; canonical ISO set.
* `ladder : Ladder` — from BOM (policy data; deterministic).
* *(Policy hook, deterministic)* `ADMIT_FOREIGN(ctx, iso, ladder, trace) -> bool` — admits/denies a foreign ISO; pure, data-driven.

**Output**

* `CandidateRow[]` *(unordered)*.
  Each row: `{ merchant_id:u64, country_iso:ISO2, is_home:bool, reason_codes:string[] /* A→Z */, filter_tags:string[] /* A→Z */ }`.

---

## 8.3 Errors this kernel may raise (merchant-scoped)

* `ERR_S3_RULE_EVAL_DOMAIN` — if `trace` contains a value outside the closed vocabularies *(should be caught in §7; surfaced only if called out of order)*.
* `ERR_S3_ISO_NOT_IN_UNIVERSE` — if an ISO is not in `iso_universe` *(defensive; should not happen given §6)*.
* `ERR_S3_RANK_DOMAIN` — if the constructed set would lack a single home or introduces duplicates *(defensive)*.

---

## 8.4 Helpers reused (pre-defined in L0; no new utilities)

* `NORMALISE_AND_VALIDATE_ISO2(s, iso_universe.set) -> ISO2` *(defensive; home already canonical in `Ctx`)*
* *(Policy hook, deterministic)* `ADMIT_FOREIGN(ctx, iso, ladder, trace) -> bool`

> Note: `DecisionTrace` from §7 is already closed-set and A→Z; no re-normalisation is performed here.

---

## 8.5 Pseudocode (language-agnostic, I/O-free)

```
PROC s3_make_candidate_set(ctx: Ctx,
                           trace: DecisionTrace,
                           iso_universe: ISOUniverse,
                           ladder: Ladder) -> array<CandidateRow>

  // ---- 0) Guards on authority (defensive) ----
  REQUIRES ctx != null AND trace != null AND iso_universe != null AND ladder != null

  // ---- 1) Home candidate (guaranteed present exactly once) ----
  LET home_iso := ctx.home_country_iso             // canonical & BOM-member by §6
  IF NOT CONTAINS(iso_universe.set, home_iso): RAISE ERR_S3_ISO_NOT_IN_UNIVERSE

  LET row_home := {
    merchant_id  : ctx.merchant_id,
    country_iso  : home_iso,
    is_home      : true,
    reason_codes : trace.reason_codes,   // already A→Z, closed
    filter_tags  : trace.filter_tags     // already A→Z, closed
  }

  // ---- 2) Enumerate admissible foreign ISOs (deterministic, no duplicates) ----
  LET seen := SET{ home_iso }
  LET rows := ARRAY{ row_home }

  // Iterate canonical ISO universe; caller may provide a prefiltered list in host layers if desired
  FOR EACH iso IN iso_universe.set:
    IF iso == home_iso OR CONTAINS(seen, iso): CONTINUE

    // Pure policy hook (data-driven; no I/O)
    IF NOT ADMIT_FOREIGN(ctx, iso, ladder, trace): CONTINUE

    IF NOT CONTAINS(iso_universe.set, iso): RAISE ERR_S3_ISO_NOT_IN_UNIVERSE  // defensive mirror

    INSERT(seen, iso)
    APPEND(rows, {
      merchant_id  : ctx.merchant_id,
      country_iso  : iso,          // canonical uppercase per BOM
      is_home      : false,
      reason_codes : trace.reason_codes,   // merchant-level annotation (A→Z)
      filter_tags  : trace.filter_tags
    })

  // ---- 3) Final defensive checks (single home; no duplicates) ----
  LET home_count := COUNT(r IN rows WHERE r.is_home == true)
  IF home_count != 1: RAISE ERR_S3_RANK_DOMAIN

  IF SIZE(seen) != SIZE( SET( MAP(rows, r -> r.country_iso) ) ): RAISE ERR_S3_RANK_DOMAIN

  RETURN rows     // unordered; §9 will assign candidate_rank
END PROC
```

---

## 8.6 Determinism & complexity

* **Determinism.** Pure function of `(ctx, trace, iso_universe, ladder)`; no randomness; closed-set annotation is stable.
* **Complexity.** `O(k)` in the number of considered ISO codes (membership checks + a single pass); memory `O(k)`. *(Hosts may prefilter the foreign list deterministically to keep `k` small.)*

---

## 8.7 Edge cases (explicit)

* **No foreigns admitted.** Returns `[home]` only; legal (ranking will produce `home=0`).
* **Policy erroneously “admits” home as foreign.** Deduplicated by `seen`; home remains only once.
* **Empty trace.** `reason_codes[]` / `filter_tags[]` are empty (legal); downstream steps still proceed.
* **Prefiltered foreigns (host).** Passing a deterministic prefiltered list instead of scanning the whole universe is equivalent; behavior must remain pure.

---

## 8.8 Interface to next step

* Pass `CandidateRow[]` to **`s3_rank_candidates`** (§9), along with a deterministic map of admission metadata per foreign ISO `(precedence, priority, rule_id)` derived from the ladder.
* **Do not** rely on the array’s order; `candidate_rank` produced in §9 is the **only** authority for inter-country order.

**Result.** `s3_make_candidate_set` yields a clean, deduplicated, merchant-annotated candidate pool that §9 can rank deterministically—**zero ambiguity** for the implementer.

---

# 9) Kernel — `s3_rank_candidates` (single order authority)

**Mission.** Turn an **unordered** `CandidateRow[]` into a **total, contiguous** inter-country order by assigning **`candidate_rank`** with **home = 0** and foreigns ranked deterministically by the **admission-order key**. **No I/O. No RNG.**

---

## 9.1 Contract (what this kernel guarantees)

* **Pure & deterministic.** No I/O, no RNG, no wall-clock.
* **Single source of truth for order.** Output `candidate_rank` is the **only** inter-country order; file order is non-authoritative.
* **Contiguity.** Ranks are **0..K−1** contiguous per merchant, with **exactly one** row at `candidate_rank = 0 ∧ is_home = true`.
* **Stable tie-breaks.** Foreigns are ordered by the lexicographic key
  `(precedence, priority, rule_id, country_iso, stable_idx)` *(ints ↑; strings A→Z; `stable_idx` last-resort)*.

---

### 9.1a Policy Hooks Index (reference; all pure, data-driven, no I/O)

| Hook name                    | Inputs                                                  | Output                                    | Notes                                          |
|------------------------------|---------------------------------------------------------|-------------------------------------------|------------------------------------------------|
| `admission_meta_from_ladder` | `ladder: Ladder`                                        | `Map<ISO2,{precedence,priority,rule_id}>` | Derived deterministically from ladder; no I/O  |
| `ADMIT_FOREIGN`              | `ctx:Ctx, iso:ISO2, ladder:Ladder, trace:DecisionTrace` | `bool`                                    | Admission predicate; pure                      |
| `MATCHES_RULE`               | `ctx:Ctx, rule:Rule`                                    | `bool`                                    | Ladder evaluation; pure                        |
| `RULE_OUTCOME`               | `rule:Rule`                                             | `{reason_code?:string, tags?:string[]}`   | Closed sets only                               |
| `EVAL_PRIOR_SCORE`           | `c:RankedCandidateRow, ctx:Ctx, priors_cfg:PriorsCfg`   | `f64 \| null`                             | Score (not probability); null = no selection   |

---

## 9.2 Inputs & outputs (values only)

**Inputs**

* `candidates : array<CandidateRow>` — unordered set from §8 *(one home, no duplicate ISO)*.
* `admission_meta_map : Map<ISO2, { precedence:int, priority:int, rule_id:string }>` — per-foreign ISO, derived **deterministically** from the ladder (policy value; no I/O).
* `home_iso : ISO2` — from `Ctx.home_country_iso` (canonical uppercase).

> *Deriving `(precedence, priority, rule_id)` is policy-driven and deterministic. L1 **consumes** the map; it does not author policy.*

**Output**

* `ranked : array<RankedCandidateRow>` — schema-shaped rows with `candidate_rank:int≥0` *(home=0; foreigns contiguous)*.

---

## 9.3 Errors this kernel may raise (merchant-scoped)

* `ERR_S3_RANK_DOMAIN` — missing **single** home, duplicate `country_iso`, or post-check contiguity violation *(defensive)*.
* `ERR_S3_ORDER_KEY_DOMAIN` — missing/invalid admission metadata for a foreign *(e.g., precedence/priority not ints; empty `rule_id`)*.

---

## 9.4 Helpers reused (all pre-defined in L0)

* `ASSERT_CANDIDATE_SET_SHAPE(rows)` — one home; no duplicate ISO *(defensive)*.
* `ASSIGN_STABLE_IDX(foreigns[]) -> foreigns[]` — sets `stable_idx = enumeration order`.
* `ADMISSION_ORDER_KEY(meta) -> tuple` — `(precedence, priority, rule_id, country_iso, stable_idx)`.
* `RANK_CANDIDATES(candidates[], admission_meta_map, home_iso:ISO2) -> array<RankedCandidateRow>` — assigns `candidate_rank` *(home = 0; foreigns contiguous)* and performs contiguity checks.

---

## 9.5 Pseudocode (language-agnostic, I/O-free)

```
PROC s3_rank_candidates(candidates: array<CandidateRow>,
                        admission_meta_map: Map<ISO2, {precedence:int, priority:int, rule_id:string}>,
                        home_iso: ISO2)
     -> array<RankedCandidateRow>

  // ---- 0) Defensive domain guards on the unordered set ----
  REQUIRES candidates != null AND LENGTH(candidates) >= 1
  CALL ASSERT_CANDIDATE_SET_SHAPE(candidates)   // one home; no duplicate ISO

  // There must be exactly one is_home row and it must match the ctx.home_country_iso
  LET home_rows := FILTER(candidates, r -> r.is_home == true)
  REQUIRES LENGTH(home_rows) == 1
  REQUIRES home_rows[0].country_iso == home_iso    // home alignment with Ctx

  // ---- 1) Validate admission metadata coverage for every foreign ISO ----
  FOR EACH r IN candidates:
    IF r.country_iso == home_iso: CONTINUE
    LET m := admission_meta_map[r.country_iso]
    IF m == null OR NOT IS_INT(m.precedence) OR NOT IS_INT(m.priority)
       OR NOT IS_STRING(m.rule_id) OR LENGTH(m.rule_id) == 0:
      RAISE ERR_S3_ORDER_KEY_DOMAIN

  // ---- 2) Delegate to L0 canonical ranking (home=0; foreigns contiguous) ----
  LET ranked := RANK_CANDIDATES(candidates, admission_meta_map, home_iso)

  // ---- 3) Postconditions (contiguity & home rank 0) ----
  LET ranks := MAP(ranked, r -> r.candidate_rank)
  REQUIRES SET_EQUALS( SET(ranks), SET([0..LENGTH(ranked)-1]) )
  REQUIRES COUNT(r IN ranked WHERE r.is_home == true AND r.candidate_rank == 0) == 1

  RETURN ranked
END PROC
```

---

## 9.6 Determinism & complexity

* **Determinism.** Output is a pure function of `(candidates, admission_meta_map, home_iso)`; stable sorts with **fully specified keys**; ASCII string order; no RNG.
* **Complexity.** **O(k log k)** per merchant *(k = number of candidate countries)*; memory **O(k)**.

---

## 9.7 Edge cases (explicit)

* **Only home present.** Returns a single row with `candidate_rank = 0`; valid.
* **Foreign missing metadata.** `ERR_S3_ORDER_KEY_DOMAIN`.
* **Conflicting metadata** (e.g., identical `(precedence,priority,rule_id)` across different ISOs): still a **total** order via `country_iso` + `stable_idx`; if fields are missing/ill-typed, raise `ERR_S3_ORDER_KEY_DOMAIN`.

---

## 9.8 Interface to next steps

* `ranked` feeds **all** optional kernels:

  * `s3_compute_priors(ranked, ctx, priors_cfg?)`
  * `s3_integerise_counts(ranked, ctx.N, priors?, bounds_cfg?)`
  * `s3_sequence_sites(ranked, counts, ctx, with_site_id)`
* For L2: `ranked` is already **schema-shaped** for `s3_candidate_set`; **L2 attaches lineage** and emits.

**Result.** `s3_rank_candidates` produces the **only** inter-country order S3 recognizes — `candidate_rank` — with guaranteed contiguity and stability, eliminating implementer guesswork.

---

# 10) Kernel — `s3_compute_priors` (optional; scores only)

**Mission.** When **`priors_enabled`**, compute a **deterministic score** per ranked candidate and return it as a **fixed-decimal string** with an explicit integer **`dp`** (constant within the run/parameter set). These are **scores (not probabilities)**; **no renormalisation** occurs in S3. **No I/O. No RNG.**

---

## 10.1 Contract (what this kernel guarantees)

* **Pure & deterministic.** No I/O, no RNG, no wall-clock.
* **Scores, not probabilities.** Returned values are **not normalised**; downstream must not interpret them as probabilities.
* **Fixed-dp strings.** Each row contains `base_weight_dp:string` and a constant integer `dp` (per run/parameter set).
* **Schema-shaped output.** Rows match `s3_base_weight_priors` (minus lineage).
* **Merchant-scoped errors** on contract violations (L1 never writes).

---

## 10.2 Inputs & outputs (values only)

**Inputs**

* `ranked : array<RankedCandidateRow>` — from §9; canonical ISO; `candidate_rank` set.
* `ctx    : Ctx` — from §6; `N ≥ 2`; lineage consistent.
* `priors_cfg : PriorsCfg` — from BOM; includes **`dp:int`** and deterministic **`selection_rules` / `constants`**.

**Output**

* `priors : array<PriorRow>`
  Each row: `{ merchant_id:u64, country_iso:ISO2, base_weight_dp:string, dp:int }`
  *(Sorted `(merchant_id ASC, country_iso ASC)` for emit-readiness.)*

---

## 10.3 Errors this kernel may raise (merchant-scoped)

* `ERR_S3_PRIOR_DISABLED` — priors flag true but `priors_cfg` missing.
* `ERR_S3_PRIOR_DOMAIN` — invalid `dp` or score (`dp ∉ [0..18]`, score NaN/Inf/negative).
* `ERR_S3_FIXED_DP_FORMAT` — defensive: a constructed fixed-dp string fails structural validation.
* `ERR_S3_PRIOR_DP_INCONSISTENT` — `dp` not constant within the returned slice (should not occur if using `priors_cfg.dp`).

---

## 10.4 Helpers reused (all from L0)

* `SELECT_PRIOR_DP(priors_cfg) -> int`
* `EVAL_PRIOR_SCORE(c: RankedCandidateRow, ctx: Ctx, priors_cfg) -> f64 | null`  *(policy hook; deterministic; `null` = “no score”)*
* `ASSERT_DP_RANGE(dp)` — `dp ∈ [0..18]`
* `ASSERT_SCORE_DOMAIN(w)` — finite, non-negative
* `QUANTIZE_WEIGHT_TO_DP(w, dp) -> FixedDpDecStr` — base-10 **half-even** via integer/rational path
* `ASSERT_PRIORS_BLOCK_SHAPE(rows[])` — `dp` constant; strings parse *(uses fixed-dp parser internally)*

---

## 10.5 Pseudocode (language-agnostic, I/O-free)

```
PROC s3_compute_priors(ranked: array<RankedCandidateRow>,
                       ctx: Ctx,
                       priors_cfg: PriorsCfg) -> array<PriorRow>

  // ---- 0) Required policy & dp ----
  REQUIRES priors_cfg != null                         // ERR_S3_PRIOR_DISABLED if absent
  LET dp := SELECT_PRIOR_DP(priors_cfg)               // deterministic dp
  CALL ASSERT_DP_RANGE(dp)                            // ERR_S3_PRIOR_DOMAIN if out of range

  // ---- 1) Evaluate deterministic score per candidate ----
  LET out := EMPTY_ARRAY()
  FOR EACH c IN ranked:
    LET w := EVAL_PRIOR_SCORE(c, ctx, priors_cfg)     // may be null (policy excludes)
    IF w == null: CONTINUE
    CALL ASSERT_SCORE_DOMAIN(w)                       // ERR_S3_PRIOR_DOMAIN on NaN/Inf/negative
    LET s := QUANTIZE_WEIGHT_TO_DP(w, dp)             // fixed-dp string (base-10 half-even)
    APPEND(out, {
      merchant_id   : c.merchant_id,
      country_iso   : c.country_iso,
      base_weight_dp: s,
      dp            : dp
    })

  // ---- 2) Order for emit-readiness ----
  LET priors_sorted := STABLE_SORT(out, key = (r -> (r.merchant_id, r.country_iso)))

  // ---- 3) Defensive consistency (dp constant; strings parse) ----
  CALL ASSERT_PRIORS_BLOCK_SHAPE(priors_sorted)

  RETURN priors_sorted
END PROC
```

---

## 10.6 Determinism & complexity

* **Determinism.** Output is a pure function of `(ranked, ctx, priors_cfg)`; fixed-dp quantisation uses an exact integer/rational path with base-10 half-even rounding.
* **Complexity.** `O(k)` policy algebra + `O(k log k)` final sort; memory **O(k)** *(k = #candidates)*.

---

## 10.7 Edge cases (explicit)

* **No rules select any candidate (all `null`).** Returns **empty array** (legal). Integerisation uses **uniform** shares if enabled.
* **Zero scores permitted by policy.** Rows are produced with `"0.000…"`; zeros flow deterministically into integerisation.
* **Huge/tiny magnitudes.** Quantiser’s big-int rational path handles all magnitudes; no locale/float-format dependence.
* **Per-merchant `dp` variance.** Forbidden: `dp` comes only from `priors_cfg` and is constant per run; kernel asserts it.

---

## 10.8 Interface to next steps

* If `integerisation_enabled`, pass `ranked`, `ctx.N`, and **these priors** to **`s3_integerise_counts`** (§11).
* L2 later attaches lineage and emits `PriorRow[]` to **`s3_base_weight_priors`** (parameter-scoped) in `(merchant_id, country_iso)` order.

**Result.** `s3_compute_priors` yields cross-language identical, fixed-dp **scores** with constant `dp`, making integerisation deterministic and emission trivial—**no renormalisation, no ambiguity**.

---

# 11) Kernel — `s3_integerise_counts` (optional)

**Mission.** When **`integerisation_enabled`**, convert deterministic **shares** over ranked candidates into **integer counts** that sum to **`N`** (from `Ctx`), and record a deterministic **`residual_rank`** for auditability. **No I/O. No RNG.**

---

## 11.1 Contract (what this kernel guarantees)

* **Pure & deterministic.** No I/O, no RNG, no wall-clock.
* **Sum equality.** Returned counts satisfy **Σ `count` = `Ctx.N`**.
* **Deterministic tie-breaks.** Uses Largest-Remainder with residuals quantised at **`dp_resid`** (default 8), tie-broken by **ISO A→Z**, then **stable index**.
* **Schema-shaped output.** Rows match `s3_integerised_counts` (minus lineage): `{ merchant_id, country_iso, count, residual_rank }`.
* **Bounds respected.** Optional floors/ceilings from policy are enforced; infeasible configs **raise**.

---

## 11.2 Inputs & outputs (values only)

**Inputs**

* `ranked : array<RankedCandidateRow>` — from §9; canonical ISO; `candidate_rank` set.
* `N      : int` — `Ctx.N` *(accepted NB draw; by contract **N ≥ 2**).*
* `priors? : array<PriorRow>` — from §10; may be empty or missing *(kernel handles both)*.
* `bounds_cfg? : BoundsCfg` — from BOM; may define `floors`, `ceilings`, and `dp_resid`.

**Output**

* `counts : array<CountRow>`
  Each row: `{ merchant_id:u64, country_iso:ISO2, count:int≥0, residual_rank:int≥1 }`
  *(Sorted `(merchant_id ASC, country_iso ASC)` for emit-readiness.)*

---

## 11.3 Errors this kernel may raise (merchant-scoped)

* **`ERR_S3_INT_DOMAIN`** — invalid inputs (non-integer or **`N < 2`**, vector length mismatch, malformed bounds).
* **`ERR_S3_INT_INFEASIBLE`** — infeasible under bounds (e.g., `Σ floors > N`, or after applying ceilings there isn’t enough capacity to place all `N`).
* **`ERR_S3_ASSERT_DOMAIN`** — post-condition failure *(e.g., Σcount ≠ N)* — defensive; should not occur when using the wrapper correctly.

---

## 11.4 Helpers reused (all from L0)

* `MAKE_SHARES_FOR_INTEGERISATION(ranked[], priors?[]) -> Rational[]`
  *(Converts priors → shares; falls back to **uniform** if priors absent or all-zero.)*
* `MAKE_BOUNDS_FOR_INTEGERISATION(ranked[], bounds_cfg?) -> { floors, ceilings, dp_resid }`
* `LRR_INTEGERISE(shares[], iso[], N, bounds?, stable?) -> (counts[], residual_rank[])`
* `ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(rows[], N)` *(Σcount = N; `residual_rank` is a 1..M permutation).*

---

## 11.5 Pseudocode (language-agnostic, I/O-free)

```
PROC s3_integerise_counts(ranked: array<RankedCandidateRow>,
                          N: int,
                          priors?: array<PriorRow>,
                          bounds_cfg?: BoundsCfg) -> array<CountRow>

  // ---- 0) Guards ----
  REQUIRES ranked != null AND LENGTH(ranked) >= 1
  REQUIRES IS_INT(N) AND N >= 2

  // ---- 1) Shares & bounds (deterministic) ----
  LET shares := MAKE_SHARES_FOR_INTEGERISATION(ranked, priors?)   // priors→shares or uniform fallback
  LET iso    := MAP(ranked, r -> r.country_iso)                   // canonical uppercase ISO2
  LET bounds := MAKE_BOUNDS_FOR_INTEGERISATION(ranked, bounds_cfg?)
  LET stable := [0..LENGTH(ranked)-1]                             // last-resort tiebreak

  // ---- 2) Largest-Remainder integerisation ----
  LET (cnt, rrank) := LRR_INTEGERISE(shares, iso, N, bounds, stable)
  // cnt[i] >= 0; Σ cnt == N; rrank[i] ∈ 1..M with deterministic order

  // ---- 3) Build schema-shaped rows (emit-readiness order) ----
  LET out := EMPTY_ARRAY()
  FOR i IN 0..LENGTH(ranked)-1:
    APPEND(out, {
      merchant_id  : ranked[i].merchant_id,
      country_iso  : ranked[i].country_iso,
      count        : cnt[i],
      residual_rank: rrank[i]
    })
  LET counts_sorted := STABLE_SORT(out, key=(r -> (r.merchant_id, r.country_iso)))

  // ---- 4) Defensive post-conditions ----
  CALL ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(counts_sorted, N)

  RETURN counts_sorted
END PROC
```

---

## 11.6 Determinism & complexity

* **Determinism.** Pure function of `(ranked, N, priors?, bounds_cfg?)`; exact rational arithmetic + base-10 half-even quantisation of residuals at `dp_resid`; tie tuple `(residual_q DESC, ISO A→Z, stable_idx)`.
* **Complexity.** **O(k log k)** (two sorts inside LRR + final emit order), memory **O(k)** *(k = #candidates)*.

---

## 11.7 Edge cases (explicit)

* **No priors or all-zero priors.** Uniform shares are used; counts still sum to `N`.
* **Tight floors.** If `Σ floors > N` → `ERR_S3_INT_INFEASIBLE`.
* **Ceiling saturation.** If after ceilings the remaining capacity is `< N − Σ base` → `ERR_S3_INT_INFEASIBLE`.
* **Single candidate (home only).** Returns one row with `count = N` (subject to floors/ceilings).

---

## 11.8 Interface to next steps

* If `sequencing_enabled`, pass `ranked`, `counts`, `ctx`, and `with_site_id` to **`s3_sequence_sites`** (§12).
* L2 later attaches lineage and emits `CountRow[]` to **`s3_integerised_counts`** (parameter-scoped), preserving `(merchant_id, country_iso)` order.

**Result.** `s3_integerise_counts` yields **portable, reproducible integer allocations** that exactly sum to `N`, with a deterministic `residual_rank` suitable for audit and downstream use—**zero ambiguity** for the implementer.

---

# 12) Kernel — `s3_sequence_sites` (optional)

**Mission.** When **`sequencing_enabled`**, build per–(merchant, country) **contiguous** `site_order = 1..nᵢ` sequences and (optionally) a **zero-padded 6-digit** `site_id` derived from the order. **No I/O. No RNG.**

---

## 12.1 Contract (what this kernel guarantees)

* **Pure & deterministic.** No I/O, no RNG, no wall-clock.
* **Within-country contiguity.** For every country with `count = nᵢ > 0`, rows exist with `site_order = 1..nᵢ` (no gaps).
* **Optional `site_id`.** If enabled, `site_id == zero_pad(site_order, 6)`; when disabled, it is **absent**.
* **Schema-shaped output.** Rows match `s3_site_sequence` (minus lineage): `{ merchant_id, country_iso, site_order[, site_id] }`.
* **Ordering for emit.** Returned rows are sorted `(merchant_id ASC, country_iso ASC, site_order ASC)`.

**Dependency.** Requires **counts** from integerisation. If `sequencing_enabled && !integerisation_enabled` (i.e., counts absent) ⇒ **raise**.

---

## 12.2 Inputs & outputs (values only)

**Inputs**

* `ranked       : array<RankedCandidateRow>` — from §9; canonical ISO; `candidate_rank` set.
* `counts       : array<CountRow>` — from §11; **one per country**; Σ`count = N`.
* `ctx          : Ctx` — from §6; provides `merchant_id`.
* `with_site_id : bool` — whether to emit 6-digit `site_id`.

**Output**

* `sequence : array<SequenceRow>`
  Each row: `{ merchant_id:u64, country_iso:ISO2, site_order:int≥1, site_id?:string /* 6 digits */ }`.

---

## 12.3 Errors this kernel may raise (merchant-scoped)

* **`ERR_S3_SEQ_DOMAIN`** — missing counts / dependency violated; **mismatched or non-bijective coverage** (countries differ or duplicates in `counts`).
* **`ERR_S3_SEQ_RANGE`** — `count_i` exceeds supported `SITE_ID_MAX` when `with_site_id == true`.
* **`ERR_S3_SEQ_NONCONTIGUOUS`** — a country’s sequence is not `1..nᵢ` contiguous; or `site_id` ≠ zero-padded order when present.

---

## 12.4 Helpers reused (all from L0)

* `BUILD_SITE_SEQUENCE_FOR_COUNTRY(merchant_id, iso, count_i, with_site_id) -> array<SequenceRow>`
* `ASSERT_CONTIGUOUS_SITE_ORDER(rows[])`
* `FORMAT_SITE_ID_ZEROPAD6(k) -> string`
* *(Constants)* `SITE_ID_WIDTH = 6`, `SITE_ID_MAX = 999_999`

---

## 12.5 Pseudocode (language-agnostic, I/O-free)

```
PROC s3_sequence_sites(ranked: array<RankedCandidateRow>,
                       counts: array<CountRow>,
                       ctx: Ctx,
                       with_site_id: bool) -> array<SequenceRow>

  // ---- 0) Guards & bijective alignment ----
  REQUIRES ranked != null AND counts != null AND ctx != null

  LET iso_ranked := SET( MAP(ranked, r -> r.country_iso) )
  LET iso_counts := SET( MAP(counts, c -> c.country_iso) )

  // Equal sets of countries (order-free equality)
  IF iso_ranked != iso_counts: RAISE ERR_S3_SEQ_DOMAIN

  // No duplicate countries in counts; 1:1 coverage
  REQUIRES LENGTH(counts) == SIZE(iso_counts)  // else duplicates in counts
  REQUIRES LENGTH(ranked) == SIZE(iso_ranked)  // defensive mirror

  // Build fast lookup (ISO -> count_i)
  LET CNT := MAP<ISO2,int>()
  FOR EACH c IN counts:
    IF HAS_KEY(CNT, c.country_iso): RAISE ERR_S3_SEQ_DOMAIN   // duplicate guard
    SET CNT[c.country_iso] := c.count

  // ---- 1) Build per-country sequences ----
  LET out := EMPTY_ARRAY()

  // Iterate in any deterministic order (final sort enforces emit order)
  FOR EACH r IN ranked:
    LET iso := r.country_iso
    LET n   := CNT[iso]  // exists by 1:1 coverage

    IF with_site_id AND n > SITE_ID_MAX: RAISE ERR_S3_SEQ_RANGE

    LET chunk := BUILD_SITE_SEQUENCE_FOR_COUNTRY(ctx.merchant_id, iso, n, with_site_id)

    // Defensive contiguity (construction guarantees it)
    CALL ASSERT_CONTIGUOUS_SITE_ORDER(chunk)

    // Defensive formatting when site IDs are enabled
    IF with_site_id:
      FOR EACH row IN chunk:
        IF row.site_id != FORMAT_SITE_ID_ZEROPAD6(row.site_order): RAISE ERR_S3_SEQ_NONCONTIGUOUS

    APPEND_ALL(out, chunk)

  // ---- 2) Emit-readiness order ----
  LET seq_sorted := STABLE_SORT(out, key = (x -> (x.merchant_id, x.country_iso, x.site_order)))

  RETURN seq_sorted
END PROC
```

---

## 12.6 Determinism & complexity

* **Determinism.** Pure function of `(ranked, counts, ctx, with_site_id)`; no randomness; canonical per-country construction.
* **Complexity.** **O(∑nᵢ)** to build rows + **O(k log k)** final country order *(k = #countries)*; memory **O(∑nᵢ)**.

---

## 12.7 Edge cases (explicit)

* **`N = 0`.** All `count_i = 0` ⇒ returns an **empty** sequence array (legal).
* **`count_i = 0`.** A country contributes **no rows** (legal).
* **Only home present.** Emits `n_home` rows for home; no others.
* **Site ID disabled.** `site_id` omitted entirely; only `site_order` emitted.

---

## 12.8 Interface to packaging & emit

* `sequence` feeds `s3_package_outputs` along with `candidate_set` (+ optional `priors`, `counts`).
* **L2** attaches lineage and emits `sequence` rows to **`s3_site_sequence`** (parameter-scoped), preserving `(merchant_id, country_iso, site_order)` order.

**Result.** `s3_sequence_sites` produces byte-stable, per-country **contiguous sequences**—and optional 6-digit IDs—ready for L2 to emit, with zero ambiguity or host-dependent behavior.

---

# 13) Materialisation Helpers — Shape Rows for Emit

**Mission.** Map kernel outputs into **schema-shaped arrays (minus lineage)** with the **logical orders** that L2’s emitters expect—**without I/O** and **without RNG**. These helpers are pure transforms + lightweight guards so L2 can attach `{parameter_hash, manifest_fingerprint}` and call S3·L0 emitters directly.

---

## 13.1 Conventions (apply to all helpers)

* **Pure & deterministic**; no I/O, no wall-clock, no RNG.
* **Schema-shaped** rows only; **lineage is intentionally absent** (L2 will add).
* **Logical sort** applied so L2 can stream straight to disk.
* **Tiny asserts** from L0 ensure table-level invariants before returning arrays.

---

## 13.2 `to_candidate_set_rows` — from `RankedCandidateRow[]`

**Shape & order expected by writer:** `(merchant_id, candidate_rank, country_iso)`
**Guards used:** `ASSERT_CANDIDATE_SET_SHAPE` *(one home; no dup ISO; ranks contiguous `0..K−1`)*

```
PROC to_candidate_set_rows(ranked: array<RankedCandidateRow>) -> array<Record>
  REQUIRES ranked != null AND LENGTH(ranked) >= 1
  CALL ASSERT_CANDIDATE_SET_SHAPE(ranked)

  // Already schema-shaped; project & sort to logical order
  LET rows := MAP(ranked, r -> {
    merchant_id    : r.merchant_id,
    country_iso    : r.country_iso,
    is_home        : r.is_home,
    reason_codes   : r.reason_codes,
    filter_tags    : r.filter_tags,
    candidate_rank : r.candidate_rank
  })

  RETURN STABLE_SORT(rows, key = (x -> (x.merchant_id, x.candidate_rank, x.country_iso)))
END PROC
```

**Determinism/Complexity.** `O(k log k)`; memory `O(k)`.

---

## 13.3 `to_prior_rows` — from `PriorRow[]` (optional)

**Shape & order expected by writer:** `(merchant_id, country_iso)`
**Guards used:** `ASSERT_PRIORS_BLOCK_SHAPE` *(dp constant; fixed-dp strings parse)*

```
PROC to_prior_rows(priors: array<PriorRow>) -> array<Record>
  REQUIRES priors != null
  IF LENGTH(priors) == 0: RETURN priors

  CALL ASSERT_PRIORS_BLOCK_SHAPE(priors)

  RETURN STABLE_SORT(priors, key = (r -> (r.merchant_id, r.country_iso)))
END PROC
```

**Determinism/Complexity.** `O(k log k)`; memory `O(k)`.

---

## 13.4 `to_count_rows` — from `CountRow[]` (optional)

**Shape & order expected by writer:** `(merchant_id, country_iso)`
**Guards used:** `ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(out, N)` *(Σcount = N; `residual_rank` is a 1..M permutation)*

```
PROC to_count_rows(counts: array[CountRow], N: int) -> array<Record>
  REQUIRES counts != null AND IS_INT(N) AND N >= 0
  IF LENGTH(counts) == 0:
    REQUIRES N == 0
    RETURN counts

  LET out := STABLE_SORT(counts, key = (r -> (r.merchant_id, r.country_iso)))
  CALL ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(out, N)
  RETURN out
END PROC
```

**Determinism/Complexity.** `O(k log k)`; memory `O(k)`.

---

## 13.5 `to_sequence_rows` — from `SequenceRow[]` (optional)

**Shape & order expected by writer:** `(merchant_id, country_iso, site_order)`
**Guards used:** `ASSERT_SEQUENCE_TABLE_SHAPE` *(per-country contiguity 1..nᵢ; `site_id` equals zero-padded order when present)*

```
PROC to_sequence_rows(seq: array[SequenceRow]) -> array<Record>
  REQUIRES seq != null
  IF LENGTH(seq) == 0: RETURN seq

  LET out := STABLE_SORT(seq, key = (x -> (x.merchant_id, x.country_iso, x.site_order)))
  CALL ASSERT_SEQUENCE_TABLE_SHAPE(out)
  RETURN out
END PROC
```

**Determinism/Complexity.** `O(∑nᵢ)` to scan + `O(k log k)` country order; memory `O(∑nᵢ)`.

---

## 13.6 Packaging helper — one struct for L2

**Goal.** Return a single, self-describing payload so L2 can attach lineage and emit in one pass.

```
TYPE S3L1Outputs = {
  candidate_set: array<Record>,   // required  (from to_candidate_set_rows)
  priors?:       array<Record>,   // optional  (from to_prior_rows)
  counts?:       array<Record>,   // optional  (from to_count_rows)
  sequence?:     array<Record>    // optional  (from to_sequence_rows)
}

PROC s3_package_outputs(candidate_set: array[Record],
                        priors?: array[Record],
                        counts?: array[Record],
                        sequence?: array[Record],
                        flags: { priors_enabled:bool,
                                 integerisation_enabled:bool,
                                 sequencing_enabled:bool }) -> S3L1Outputs

  // Flag consistency (defensive; should already be checked upstream)
  IF flags.sequencing_enabled AND NOT flags.integerisation_enabled:
    RAISE ERR_S3_FLAG_MATRIX    // cannot have sequence without counts

  // Cross-field consistency
  IF sequence != null AND counts == null:
    RAISE ERR_S3_PACKAGE_SHAPE  // sequence requires counts

  LET out := { candidate_set: candidate_set }
  IF flags.priors_enabled          AND priors   != null: out.priors   := priors
  IF flags.integerisation_enabled  AND counts   != null: out.counts   := counts
  IF flags.sequencing_enabled      AND sequence != null: out.sequence := sequence
  RETURN out
END PROC
```

**Determinism/Complexity.** `O(1)` (struct assembly).

---

## 13.7 “Minus lineage” reminder (for L2)

These helpers **never** add `{parameter_hash, manifest_fingerprint}`. L2 must:

1. attach lineage from `Ctx`;
2. verify **embed = path** at emit time (S3·L0 §15);
3. call the correct emitter with the already-sorted arrays:

   * `EMIT_S3_CANDIDATE_SET`, `EMIT_S3_BASE_WEIGHT_PRIORS`,
   * `EMIT_S3_INTEGERISED_COUNTS`, `EMIT_S3_SITE_SEQUENCE`.

---

## 13.8 Edge cases (explicit)

* **Empty arrays are legal** when the corresponding flag is enabled but the outcome is empty (e.g., no priors selected; `N = 0` → empty sequence).
* **Pre-sorted inputs** are allowed; we still apply the logical order to be explicit and host-agnostic.
* **Per-merchant packaging** is independent; arrays from one merchant never mingle with others in L1.

---

## 13.9 Why this reduces friction

* **Ready-to-emit:** arrays already have the correct **shapes and sort orders**, so L2 can attach lineage and call emitters—no reshaping or extra passes.
* **Guarded:** tiny asserts catch contract drift early (contiguity, sums, dp, fixed-dp, sequence formatting).
* **Pure & portable:** no I/O; no host-specific details; same behavior in any language.

---

# 14) Determinism, Complexity & Memory Targets

**Goal.** Make S3·L1 kernels **byte-predictable** across languages and **bounded** in time/space so implementers can reason about performance and correctness up-front.

---

## 14.1 Determinism (global guarantees)

* **RNG-free & I/O-free.** All kernels are pure functions of their inputs (`Ctx`, BOM, flags, prior kernel outputs). No wall-clock, env vars, or filesystem.
* **Numeric policy.** IEEE-754 **binary64**, round-to-nearest-even, **no FMA**; no reordering of reductions. Wherever exact decimal is required (priors; residual bins), use **base-10 half-even quantisation via integer/rational arithmetic** (from L0).
* **Ordering policy.**

  * Inter-country order = **`candidate_rank` only** (home = 0; foreigns contiguous).
  * Stable sorts with **fully specified keys** (ints ↑; strings ASCII A→Z; documented tie-break tuples).
  * Within-country order: `site_order = 1..nᵢ` contiguous; optional `site_id` is **zero-padded order (width 6)**.
* **Lineage separation.** L1 returns schema-shaped arrays **without** `{parameter_hash, manifest_fingerprint}`; L2 attaches lineage and emits.
* **Error posture.** Fail-fast, **merchant-scoped**, deterministic codes; no best-effort auto-repair.

---

## 14.2 Per-kernel time/space targets (k = #candidate countries; nᵢ = count per country)

| Kernel                       | Time (Big-O)                     | Space (Big-O) | Notes                                                              |
|------------------------------|----------------------------------|---------------|--------------------------------------------------------------------|
| `s3_build_ctx`               | O(1)                             | O(1)          | Gate + canonicalise channel/ISO; lineage equality checks.          |
| `s3_evaluate_rule_ladder`    | O(#rules) + O(R log R + T log T) | O(R+T)        | R/T = emitted reason/tag counts (small); stable A→Z dedup.         |
| `s3_make_candidate_set`      | O(k)                             | O(k)          | Single pass; unordered output; no sort.                            |
| `s3_rank_candidates`         | **O(k log k)**                   | O(k)          | Stable sort by `(precedence, priority, rule_id, ISO, stable_idx)`. |
| `s3_compute_priors` (opt)    | O(k) + **O(k log k)**            | O(k)          | Policy algebra per row + final emit order.                         |
| `s3_integerise_counts` (opt) | **O(k log k)**                   | O(k)          | LRR: two sorts (eligibles + residual rank) + linear arithmetic.    |
| `s3_sequence_sites` (opt)    | **O(∑nᵢ)** + O(k log k)          | O(∑nᵢ)        | Build contiguous sequences + final country order.                  |
| `to_*_rows` materialisers    | **O(k log k)** (or O(∑nᵢ)+sort)  | O(k)/O(∑nᵢ)   | Apply logical writer order + tiny asserts.                         |
| `s3_package_outputs`         | O(1)                             | O(1)          | Struct assembly; flag consistency checks.                          |

**Implication.** The only super-linear steps are the **stable sorts** (ranking, integerisation, emit-order, and sequencing’s final country order). Everything else is linear.

---

## 14.3 Memory discipline

* **Slice-local.** Operate only on the current merchant’s arrays; never materialise the universe.
* **O(k) working set.** Arrays sized by candidate count; sequencing adds **O(∑nᵢ)** temporary rows.
* **No hidden copies.** Prefer map/transform + a single stable sort before returning. Avoid repeated re-sorting.

---

## 14.4 Parallelism & throughput

* **Embarrassingly parallel per merchant.** L2 can shard merchant IDs across workers; no shared mutable state in L1.
* **BOM memo is read-only.** Opened once (L0) and reused by all merchants; no per-call overhead in L1.
* **Good batching.** L1 returns arrays in logical order so L2 can stream emits using writer row-groups with minimal shuffles.

---

## 14.5 Deterministic tie-break & rounding anchors

* **Ranking key (foreigns):** `(precedence, priority, rule_id, ISO, stable_idx)` — ints asc; strings A→Z; `stable_idx` set by deterministic enumeration.
* **Residual bins (LRR):** quantise fractional remainders with **`dp_resid`** (default 8; or from policy) using base-10 half-even; tie-break by ISO A→Z, then `stable_idx`.
* **Fixed-dp priors:** `dp ∈ [0..18]`, base-10 half-even; **constant `dp` per run/parameter set**.

---

## 14.6 Edge-case behaviour (performance-relevant)

* **k = 1 (home only).** Ranking O(1); integerisation assigns all N to home; sequencing builds a single contiguous block. Fast path.
* **N = 0.** **Unreachable under S3 entry gates** (S2 enforces `N ≥ 2`). Documented defensively only: if ever encountered, integerisation would return zeros and sequencing would be empty.
* **Tight bounds.** Detect infeasibility early (`Σ floors > N` or ceiling saturation) to avoid wasted passes.

---

## 14.7 Host-level knobs (safe to tune without changing semantics)

* **Sort implementation.** Any **stable** O(k log k) sort (e.g., mergesort/timsort) is acceptable; key order must match the documented tuples.
* **Map/set structures.** Hash or ordered maps are fine; semantics require set membership and a deterministic final sort only.
* **Numeric libs.** For fixed-dp / residual bins, use arbitrary-precision integer/rational operations (as provided in L0) to avoid float drift.

---

## 14.8 What never changes (non-negotiables)

* No RNG, no I/O, no wall-clock in L1.
* Inter-country order lives only in **`candidate_rank`**.
* Priors are **scores**; **no renormalisation**.
* Integerisation returns `Σ count = N`; sequencing returns per-country **1..nᵢ** contiguity.

**Result.** With these targets, S3·L1 kernels are **predictably fast**, **space-bounded**, and **portable**—and they produce byte-identical arrays that L2 can emit immediately, with **zero ambiguity** for implementers.

---

# 15) Edge-Case Handling (explicit)

**Goal.** Remove ambiguity by stating exactly what each kernel does under edge inputs. All behaviors are **pure, deterministic, merchant-scoped, non-emitting on error**.

---

## 15.1 Inputs & gating (Ctx)

* **Missing / multiple upstream rows** (ingress, S1 hurdle, S2 `nb_final`) → `ERR_S3_CTX_MISSING_INPUTS` / `ERR_S3_CTX_MULTIPLE_INPUTS`.
* **Lineage mismatch** (`parameter_hash`/`manifest_fingerprint` differ) → `ERR_S3_CTX_LINEAGE_MISMATCH`.
* **Entry gates:** `is_multi != true` or `N < 2` → `ERR_S3_CTX_ENTRY_GATES`.
* **Channel not in ingress vocab** → `ERR_S3_RULE_EVAL_DOMAIN`.
* **Home ISO invalid or outside BOM set** → `ERR_S3_ISO_INVALID_FORMAT` / `ERR_S3_ISO_NOT_IN_UNIVERSE`.
* **Effect:** abort L1 for this merchant; return no arrays.

---

## 15.2 Ladder evaluation (policy apply)

* **No rules fire** → `DecisionTrace{reason_codes=[], filter_tags=[]}` (valid; downstream continues).
* **Policy emits unknown code/tag** → `ERR_S3_RULE_EVAL_DOMAIN`.
* **Duplicate codes/tags** → collapsed by A→Z dedup (valid).
* **Effect:** always returns a canonical trace or raises deterministically.

---

## 15.3 Candidate set assembly

* **Only home admitted** → returns `[home]` (valid).
* **Attempted duplicate home or foreign** → construction prevents; final assert raises `ERR_S3_RANK_DOMAIN` if violated.
* **Trace empty** → rows still carry `reason_codes=[]`, `filter_tags=[]` (valid).
* **Foreign ISO not in BOM set** (shouldn’t happen after §6) → `ERR_S3_ISO_NOT_IN_UNIVERSE`.

---

## 15.4 Deterministic ranking (single order authority)

* **Only home present** → one row with `candidate_rank=0` (valid).
* **Missing admission metadata for a foreign** → `ERR_S3_ORDER_KEY_DOMAIN`.
* **Conflicting metadata** (same `(precedence,priority,rule_id)` across ISOs) → still total via `country_iso` A→Z then `stable_idx` (valid).
* **Non-contiguous ranks** (should not occur if helper is used) → defensive post-check raises `ERR_S3_RANK_DOMAIN`.

---

## 15.5 Priors (optional; scores only)

* **Flag true but `priors_cfg` absent** → `ERR_S3_PRIOR_DISABLED`.
* **`dp` invalid** (`dp ∉ [0..18]`) → `ERR_S3_PRIOR_DOMAIN`.
* **All scores null** (policy selects none) → returns **empty** `PriorRow[]` (valid).
* **Zero scores** allowed → quantised `"0…"` strings; carried forward (valid).
* **NaN/Inf/negative** from policy hook → `ERR_S3_PRIOR_DOMAIN`.
* **Fixed-dp string malformed** (defensive parse) → `ERR_S3_FIXED_DP_FORMAT`.
* **`dp` varies within slice** (shouldn’t happen with `priors_cfg.dp`) → `ERR_S3_PRIOR_DP_INCONSISTENT`.

---

## 15.6 Integerisation (optional; Largest-Remainder)

* **No priors** or **all-zero priors** → shares = **uniform** (valid).
* **`N < 2`** (contradicts entry gates) → raise `ERR_S3_INT_DOMAIN` if encountered here; normally blocked in §6.
* **Single candidate (home only)** → returns `{count = N}` subject to floors/ceilings (valid).
* **Bounds infeasible:**

  * `Σ floors > N` → `ERR_S3_INT_INFEASIBLE`.
  * After ceilings, not enough capacity to place leftovers → `ERR_S3_INT_INFEASIBLE`.
* **Post-sum mismatch** (defensive) → `ERR_S3_ASSERT_DOMAIN`.
* **Residual ties** → broken by `(residual_q DESC, ISO A→Z, stable_idx)` (deterministic).

---

## 15.7 Sequencing (optional; within-country)

* **Dependency:** `sequencing_enabled && !integerisation_enabled` → `ERR_S3_SEQ_DOMAIN`.
* **Coverage mismatch** (country sets differ or duplicates in `counts`) → `ERR_S3_SEQ_DOMAIN`.
* **`count_i = 0`** → country contributes **no rows** (valid).
* **`with_site_id = true` and `count_i > SITE_ID_MAX` (999 999)** → `ERR_S3_SEQ_RANGE`.
* **Non-contiguous `site_order`** or `site_id != zero_pad(site_order,6)` → `ERR_S3_SEQ_NONCONTIGUOUS`.

---

## 15.8 Packaging & flags

* **Invalid flag combo** (`sequence=true`, `integerisation=false`) → `ERR_S3_FLAG_MATRIX`.
* **Packaging inconsistency** (sequence present but counts missing) → `ERR_S3_PACKAGE_SHAPE`.
* **Empty optional arrays** (e.g., priors empty) → **valid**; L2 may still emit empty partitions if desired.

---

## 15.9 Numerical / ordering anchors (made explicit)

* **Fixed-dp priors:** base-10 **half-even** quantisation via integer/rational arithmetic; locale-independent; **dp constant** per run.
* **Residual bins:** quantise with `dp_resid` (default 8 or from policy), then tie-break by ISO A→Z, then `stable_idx`.
* **All sorts:** **stable** with fully specified keys; strings compare in **ASCII**; ISO already uppercase; no host-specific collation.

---

## 15.10 Quick “where handled” index

| Edge case                                  | Kernel / Helper that handles it               | Error / Outcome                                 |
|--------------------------------------------|-----------------------------------------------|-------------------------------------------------|
| Missing/multiple upstream rows             | `s3_build_ctx` (`ASSERT_SINGLETON`)           | `ERR_S3_CTX_*`                                  |
| Lineage mismatch                           | `s3_build_ctx` (`ASSERT_LINEAGE_EQUAL`)       | `ERR_S3_CTX_LINEAGE_MISMATCH`                   |
| `is_multi != true` or `N < 2`              | `s3_build_ctx` (`ASSERT_S2_ACCEPTED_N`)       | `ERR_S3_CTX_ENTRY_GATES`                        |
| Unknown channel / vocab                    | `s3_evaluate_rule_ladder` (closed-set checks) | `ERR_S3_RULE_EVAL_DOMAIN`                       |
| Only home / duplicate ISO                  | `s3_make_candidate_set`, `s3_rank_candidates` | Valid / `ERR_S3_RANK_DOMAIN`                    |
| Missing admission metadata for foreign     | `s3_rank_candidates`                          | `ERR_S3_ORDER_KEY_DOMAIN`                       |
| Priors flag but missing policy             | `s3_compute_priors`                           | `ERR_S3_PRIOR_DISABLED`                         |
| Priors dp invalid / score NaN/Inf/negative | `s3_compute_priors`                           | `ERR_S3_PRIOR_DOMAIN`                           |
| Integerisation infeasible                  | `s3_integerise_counts` (`LRR_INTEGERISE`)     | `ERR_S3_INT_INFEASIBLE`                         |
| Sequence without counts                    | `s3_sequence_sites` / `s3_package_outputs`    | `ERR_S3_SEQ_DOMAIN` / `ERR_S3_FLAG_MATRIX`      |
| `site_id` formatting / range               | `s3_sequence_sites`                           | `ERR_S3_SEQ_RANGE` / `ERR_S3_SEQ_NONCONTIGUOUS` |

---

## 15.11 Developer crib (decision outcomes)

* **Candidates-only** → `{ candidate_set }`
* **+ priors** → `{ candidate_set, priors }`
* **+ integerisation (no priors)** → `{ candidate_set, counts }` *(uniform shares)*
* **Full** (priors + counts + sequence) → `{ candidate_set, priors, counts, sequence }`

**Bottom line:** every non-standard input path is either **explicitly supported** with deterministic behavior or **rejected** with a clear, merchant-scoped error—so implementers never have to guess.

---

# 16) Tiny Asserts (callable within kernels)

**Goal.** One-liners you can drop into any S3·L1 kernel to fail fast. All are **pure**, host-neutral, and raise **merchant-scoped**, deterministic errors. Where an equivalent assert already exists in **S3·L0**, L1 should **call the L0 version**; the signatures below mirror those surfaces to keep call-sites clear.

---

## 16.1 Candidate set / ranking

```
PROC ASSERT_SINGLE_HOME_NO_DUPES(rows: array<CandidateRow|RankedCandidateRow>)
REQUIRES rows != null AND LENGTH(rows) ≥ 1
LET home_cnt := COUNT(r IN rows WHERE r.is_home)
IF home_cnt != 1: RAISE ERR_S3_RANK_DOMAIN
LET iso_set := SET( MAP(rows, r -> r.country_iso) )
IF SIZE(iso_set) != LENGTH(rows): RAISE ERR_S3_RANK_DOMAIN
ENSURES true
```

```
PROC ASSERT_RANKS_CONTIGUOUS_ZERO_BASE(ranked: array<RankedCandidateRow>)
LET ranks := MAP(ranked, r -> r.candidate_rank)
LET K := LENGTH(ranks)
IF SET(ranks) != SET([0..K-1]): RAISE ERR_S3_RANK_DOMAIN
IF COUNT(r IN ranked WHERE r.is_home AND r.candidate_rank==0) != 1: RAISE ERR_S3_RANK_DOMAIN
ENSURES true
```

> In practice, prefer **L0**: `ASSERT_CANDIDATE_SET_SHAPE(rows)` and the post-check performed inside `RANK_CANDIDATES`.

---

## 16.2 Priors (scores, not probabilities)

```
PROC ASSERT_DP_CONSTANT(rows: array<PriorRow>)
IF LENGTH(rows)==0: RETURN
LET d0 := rows[0].dp
FOR EACH r IN rows: IF r.dp != d0: RAISE ERR_S3_PRIOR_DP_INCONSISTENT
ENSURES true
```

```
PROC ASSERT_FIXED_DP_BLOCK(rows: array<PriorRow>)
FOR EACH r IN rows:
  LET _ := PARSE_FIXED_DP(r.base_weight_dp)   // raises ERR_S3_FIXED_DP_FORMAT on failure
CALL ASSERT_DP_CONSTANT(rows)
ENSURES true
```

> In practice, prefer **L0**: `ASSERT_PRIORS_BLOCK_SHAPE(rows)`.

---

## 16.3 Integerisation

```
PROC ASSERT_COUNTS_SUM_AND_PERM(rows: array<CountRow>, N: int)
LET s := 0
LET perm := EMPTY_ARRAY()
FOR EACH r IN rows: s := s + r.count; APPEND(perm, r.residual_rank)
IF s != N: RAISE ERR_S3_ASSERT_DOMAIN
LET M := LENGTH(perm)
IF SET(perm) != SET([1..M]): RAISE ERR_S3_ASSERT_DOMAIN
ENSURES true
```

> Prefer **L0**: `ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(rows, N)`.

---

## 16.4 Sequencing

```
PROC ASSERT_SEQUENCE_TABLE_SHAPE(seq: array<SequenceRow>)
LET groups := GROUP_BY(seq, key=(x -> x.country_iso))
FOR EACH (iso, rows) IN groups:
  LET n := LENGTH(rows)
  LET sorted := STABLE_SORT(rows, key=(x -> x.site_order))
  FOR i FROM 1 TO n:
    IF sorted[i-1].site_order != i: RAISE ERR_S3_SEQ_NONCONTIGUOUS
  // If site_id present, it must match zero-padded order
  FOR EACH r IN sorted:
    IF HAS_KEY(r,"site_id") AND r.site_id != FORMAT_SITE_ID_ZEROPAD6(r.site_order):
      RAISE ERR_S3_SEQ_NONCONTIGUOUS
ENSURES true
```

> Prefer **L0**: same-name `ASSERT_SEQUENCE_TABLE_SHAPE(seq)`.

---

## 16.5 ISO & vocab

```
PROC ASSERT_ISO_MEMBER_CANONICAL(iso: string, iso_set: Set<ISO2>)
LET canon := NORMALISE_AND_VALIDATE_ISO2(iso, iso_set)  // raises on failure
ENSURES canon == iso
```

```
PROC ASSERT_CHANNEL_VOCAB(ch: string, channel_vocab: Set<string>)
CALL ASSERT_CHANNEL_IN_INGRESS_VOCAB(ch, channel_vocab)   // raises ERR_S3_RULE_EVAL_DOMAIN
ENSURES true
```

---

## 16.6 Flags & packaging

```
PROC ASSERT_FLAG_MATRIX(flags)
IF flags.sequencing_enabled AND NOT flags.integerisation_enabled: RAISE ERR_S3_FLAG_MATRIX
ENSURES true
```

```
PROC ASSERT_PACKAGE_SHAPE(out)
IF HAS_KEY(out, "sequence") AND NOT HAS_KEY(out, "counts"): RAISE ERR_S3_PACKAGE_SHAPE
ENSURES true
```

---

# 16a) Integration Points with L2/L3 (for implementers)

**Goal.** Show exactly how **L2** wires **L1** and how **L3** validates the bytes—so implementers can connect pieces with **zero guesswork**.

---

## L2 (orchestrator & emit) — minimal responsibilities

**What L2 does**

1. **Open BOM once** (L0 §3): `bom := OPEN_BOM_S3(flags)` (memoised).
2. **For each merchant (parallel OK):**

   * **Read values** (not paths): `ingress, s1, s2` (host I/O layer).
   * **L1 kernels (pure):**

     ```
     ctx    := s3_build_ctx(ingress, s1, s2, bom, channel_vocab)
     trace  := s3_evaluate_rule_ladder(ctx, bom.ladder, channel_vocab)
     cand   := s3_make_candidate_set(ctx, trace, bom.iso_universe, bom.ladder)
     ranked := s3_rank_candidates(cand, admission_meta_from_ladder(bom.ladder), ctx.home_country_iso)

     priors? := flags.priors_enabled
                ? s3_compute_priors(ranked, ctx, bom.priors_cfg)
                : null

     counts? := flags.integerisation_enabled
                ? s3_integerise_counts(ranked, ctx.N, priors?, bom.bounds_cfg?)
                : null

     seq?    := flags.sequencing_enabled
                ? s3_sequence_sites(ranked, counts?, ctx, with_site_id)
                : null

     rows := s3_package_outputs(
               to_candidate_set_rows(ranked),
               priors? != null ? to_prior_rows(priors?) : null,
               counts? != null ? to_count_rows(counts?, ctx.N) : null,
               seq?    != null ? to_sequence_rows(seq?)        : null,
               flags )
     ```
   * **Attach lineage** (from `ctx.lineage`): add `{parameter_hash, manifest_fingerprint}` to each row set.
   * **Emit via L0 (parameter-scoped, atomic):**

     * `EMIT_S3_CANDIDATE_SET(rows.candidate_set, parameter_hash, manifest_fp, skip_if_final=true)`
     * If present: `EMIT_S3_BASE_WEIGHT_PRIORS`, `EMIT_S3_INTEGERISED_COUNTS`, `EMIT_S3_SITE_SEQUENCE`.

**Guards in L2 before emit**

* Verify **embed = path** (`parameter_hash` in rows == partition key).
* Use **idempotence probe** (skip if final exists) per dataset/partition.
* Emit in **logical order** (the `to_*_rows` helpers already sorted accordingly).

**What L2 never does**

* Never compute or mutate business logic; never randomise; never change row shapes or field names.

---

## L3 (validator) — byte-level proof of contracts

**Per-dataset checks (streaming OK)**

* **`s3_candidate_set`**

  * Schema anchor matches; partition = `parameter_hash`.
  * **Rank contiguity:** `candidate_rank` is 0..K contiguous; exactly one `is_home ∧ rank=0`.
  * No duplicate `(merchant_id, country_iso)`.

* **`s3_base_weight_priors`** *(if present)*

  * Schema anchor matches; partition = `parameter_hash`.
  * **DP constant** within partition; every `base_weight_dp` **parses** as fixed-dp (no exponents/locale).
  * No renormalisation checks (scores only).

* **`s3_integerised_counts`** *(if present)*

  * Schema anchor matches; partition = `parameter_hash`.
  * **Sum equals N** (join N from S2 or echo/derived consistently); `residual_rank` is **1..M permutation**.

* **`s3_site_sequence`** *(if present)*

  * Schema anchor matches; partition = `parameter_hash`.
  * For each `(merchant_id, country_iso)` group: `site_order` is **1..nᵢ** contiguous; if `site_id` present, equals zero-padded order.

**Cross-dataset checks**

* `sequence` present ⇒ `counts` present (flag dependency).
* All datasets embed the same `{parameter_hash, manifest_fingerprint}` and match the **path partition**.
* *(Optional)* Compare emitted shapes against L1 materialised arrays in pre-emit logs for replayability.

---

## Suggested L2/L3 “gotchas” to avoid

* **Do not** re-sort by file order to interpret inter-country order—**always** read `candidate_rank`.
* **Do not** renormalise priors into probabilities; they are **scores**.
* **Do not** soften infeasible bounds; raise and quarantine the merchant (errors are merchant-scoped).
* **Do not** attach volatile timestamps to S3 rows; S3 tables are **stable** datasets.

---

**Result.** With these tiny asserts and integration points, **L1** stays small and pure; **L2** knows exactly how to attach lineage and emit; **L3** knows exactly which invariants to prove—making the whole S3 pipeline deterministic, portable, and friction-free.

---

# 17) Acceptance Checklist (L1 “done”)

Use this as the **go/no-go** gate for S3·L1. Every box must pass before you freeze.

---

## A. Structure & Scope

* [ ] **Pure kernels only**: no I/O, no RNG, no wall-clock, no path literals.
* [ ] **L0 reuse**: every helper called exists in **S3·L0** (or S0/S1/S2·L0 where stated); no re-implementation or drift.
* [ ] **No undefined calls / TODOs**: every function referenced is defined or explicitly imported; no policy authoring in L1.

---

## B. Inputs, Flags, BOM

* [ ] **Inputs** to kernels are **values**: `Ctx`, `BOM`, `feature_flags`, prior kernel outputs.
* [ ] **Flags run-constant** per `parameter_hash`; invalid combo (`sequencing=true` & `integerisation=false`) is rejected.
* [ ] **Policy handles** present when required (`priors_cfg` if `priors_enabled`); `bounds_cfg` optional for integerisation.

---

## C. Kernel Coverage (build → rank → optional → package)

* [ ] `s3_build_ctx` gates & canonicalises (singletons, **merchant/id & lineage equality**, `is_multi==true`, `N≥2`, ISO/channel valid).
* [ ] `s3_evaluate_rule_ladder` applies ladder deterministically; emits closed-set, **A→Z** `reason_codes[]/filter_tags[]`.
* [ ] `s3_make_candidate_set` returns `{home} ∪ foreigns` (unordered); **one home**, **no duplicate ISO**.
* [ ] `s3_rank_candidates` assigns **`candidate_rank`** with **home=0**, foreigns contiguous **0..K−1**, using the documented key; **home ISO matches `Ctx`**.
* [ ] *(opt)* `s3_compute_priors` returns **scores** (fixed-dp string) with **constant `dp`**; **no renormalisation**.
* [ ] *(opt)* `s3_integerise_counts` returns counts that **sum to `N`** with deterministic `residual_rank`; floors/ceilings enforced.
* [ ] *(opt)* `s3_sequence_sites` returns per-country **contiguous** `site_order=1..nᵢ` (+ optional zero-padded `site_id`).
* [ ] `s3_package_outputs` returns `{candidate_set, priors?, counts?, sequence?}` consistent with flags and dependencies.

---

## D. Shapes & Schema Alignment (minus lineage)

* [ ] All kernel outputs are **schema-shaped** arrays using exact field names/types expected by the S3 datasets.
* [ ] Logical order for emit is documented **and applied in materialisers** (`to_*_rows`).
* [ ] **Lineage is absent** in L1 outputs by design; L2 attaches `{parameter_hash, manifest_fingerprint}` before emit.

---

## E. Determinism & Numeric Discipline

* [ ] **Ordering**: stable sorts with fully specified keys; inter-country order is **only** `candidate_rank`.
* [ ] **Fixed-dp**: base-10 **half-even** via integer/rational arithmetic; `dp ∈ [0..18]`, **constant per run/parameter set**.
* [ ] **LRR residuals**: quantised at `dp_resid` (default 8 or policy), tie-break `(residual_q DESC, ISO A→Z, stable_idx)`.

---

## F. Error Posture (merchant-scoped, non-emitting)

* [ ] Every kernel declares and raises only the documented **L1 error codes** (no generic exceptions).
* [ ] Fail-fast on domain/shape/policy violations; **no best-effort** auto-repair.
* [ ] Messages include `code`, `where`, and minimal `context` (e.g., offending ISO); deterministic and reproducible.

---

## G. Performance Targets (per merchant)

* [ ] Ranking & integerisation **O(k log k)**; sequencing **O(∑nᵢ)** + country sort **O(k log k)**; others **O(k)** or **O(1)**.
* [ ] Memory **O(k)** (plus **O(∑nᵢ)** for sequencing); no universe-wide materialisation.
* [ ] No unnecessary re-sorting/copies; single stable sort before return where needed.

---

## H. Integration Ready (L2/L3)

* [ ] L2 flow is unambiguous: attach lineage → verify **embed = path** → emit via S3·L0 emitters **in logical order**; idempotence/atomic publish per L0 §15.
* [ ] L3 parity: invariants L3 must prove are listed (rank contiguity 0..K−1 with `home=0`, Σcount = N, dp constant, sequence contiguity, fixed-dp parse).

---

## I. Edge-Cases Explicit

* [ ] Documented behaviors for: **only home**, **no foreigns**, **N=0**, **no/zero priors**, **tight/invalid bounds**, **large counts** (`SITE_ID_MAX`), **empty optional arrays**.
* [ ] Packaging rejects inconsistent states (sequence without counts; invalid flag matrix).

---

## J. Doc Hygiene

* [ ] Section cross-refs correct; no stale references; naming consistent with L0 and schema (ASCII terms, uppercase ISO).
* [ ] Examples (if any) are illustrative and consistent with rules (no hidden semantics or implied renormalisation).

---

**If all items are ✅, S3·L1 is “done” and ready to freeze.**

---

# 18) Schema/Dataset Crosswalk for L2 (1 screen)

> One-glance map from **L1 arrays** → **emit rows** → **dataset**. L2 attaches lineage, verifies the partition, and calls the emitter. All partitions are **parameter-scoped** (`parameter_hash=…`). File order is non-authoritative; **logical order** below is what writers enforce.

```
DATASET: s3_candidate_set
FROM   : to_candidate_set_rows( RankedCandidateRow[] )
SCHEMA : schemas.1A.yaml#/s3/candidate_set
PARTN  : parameter_hash={…}
ORDER  : (merchant_id ASC, candidate_rank ASC, country_iso ASC)
EMIT   : EMIT_S3_CANDIDATE_SET(rows, parameter_hash, manifest_fp, skip_if_final=true)
FLAGS  : always (no flag gating)
CHECKS : embed=path; ASSERT_CANDIDATE_SET_SHAPE (one home; ranks 0..K−1 contiguous)
NOTES  : Inter-country order lives ONLY in candidate_rank (home=0)
```

```
DATASET: s3_base_weight_priors      [optional]
FROM   : to_prior_rows( PriorRow[] )
SCHEMA : schemas.1A.yaml#/s3/base_weight_priors
PARTN  : parameter_hash={…}
ORDER  : (merchant_id ASC, country_iso ASC)
EMIT   : EMIT_S3_BASE_WEIGHT_PRIORS(rows, parameter_hash, manifest_fp, skip_if_final=true)
FLAGS  : priors_enabled == true
CHECKS : embed=path; ASSERT_PRIORS_BLOCK_SHAPE (dp constant; fixed-dp valid)
NOTES  : Scores, not probabilities; NO renormalisation
```

```
DATASET: s3_integerised_counts      [optional]
FROM   : to_count_rows( CountRow[], N=Ctx.N )
SCHEMA : schemas.1A.yaml#/s3/integerised_counts
PARTN  : parameter_hash={…}
ORDER  : (merchant_id ASC, country_iso ASC)
EMIT   : EMIT_S3_INTEGERISED_COUNTS(rows, parameter_hash, manifest_fp, skip_if_final=true)
FLAGS  : integerisation_enabled == true
CHECKS : embed=path; ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(out, N)  // Σcount == N; residual_rank is 1..M permutation
NOTES  : LRR; floors/ceilings enforced upstream
```

```
DATASET: s3_site_sequence           [optional]
FROM   : to_sequence_rows( SequenceRow[] )
SCHEMA : schemas.1A.yaml#/s3/site_sequence
PARTN  : parameter_hash={…}
ORDER  : (merchant_id ASC, country_iso ASC, site_order ASC)
EMIT   : EMIT_S3_SITE_SEQUENCE(rows, parameter_hash, manifest_fp, skip_if_final=true)
FLAGS  : sequencing_enabled == true  AND  integerisation_enabled == true
CHECKS : embed=path; ASSERT_SEQUENCE_TABLE_SHAPE (per-country site_order 1..nᵢ contiguous; if present, site_id == zero_pad(site_order,6))
NOTES  : Within-country only; inter-country order is NOT here
```

**L2 pre-emit routine (per dataset, per partition)**

1. **Attach lineage**: add `{parameter_hash, manifest_fingerprint}` from `Ctx`.
2. **Idempotence**: if `skip_if_final == true` and final exists → skip.
3. **Embed = path**: verify row `parameter_hash` equals the partition key.
4. **Logical order**: arrays are already sorted by `to_*_rows`; no extra reshapes.
5. **Emit**: call the matching `EMIT_S3_*` (atomic publish; no volatile fields).

**Flag wiring (summary)**

* **candidate_set**: always.
* **priors**: only if `priors_enabled`.
* **counts**: only if `integerisation_enabled`.
* **sequence**: only if `sequencing_enabled && integerisation_enabled`.

This crosswalk lets L2 wire outputs with zero guesswork: **what to emit, where, how it’s sorted, which checks to run, and which flags gate it**.

---