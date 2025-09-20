# S3·L2 — Orchestrator

# 1) Purpose & Scope (L2 = Orchestrator)

## 1.1 What L2 is

The **single legal wiring** of S3: invoke S3·L1 kernels in the only permitted order and **publish** S3’s parameter-scoped datasets **via L0 emitters** using atomic, idempotent semantics. L2 adds **no new math** and performs **no RNG** or validation; it simply zips L1’s in-memory results into the final tables.

## 1.2 What L2 is not

* **No randomness.** S3 has **no RNG families**; L2 must not introduce any.
* **No policy/algorithm changes.** Ordering, priors, integerisation, and sequencing rules are fixed by S3 Expanded/L1. L2 does **zero** recomputation or renormalisation.
* **No path literals / schema drift.** Dataset IDs, partitions, schema anchors, and required logical row orders are dictionary-resolved and enforced by L0 emitters—never hardcoded in L2.

## 1.3 Audience & constraints

* **Audience:** implementers wiring S3 to run.
* **Determinism:** outputs are **byte-identical** for fixed inputs/lineage; **no timestamps** in table rows.
* **Scope of outputs (S3 only):**

  * Required: `s3_candidate_set`
  * Optional: `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence`
    All are **parameter-scoped** (partition key = `parameter_hash`).

## 1.4 Core contracts L2 must uphold

* **Single order authority.** Inter-country order is **only** `candidate_rank` (home=0, contiguous). L2 must not derive, alter, or re-rank it.
* **Parameter-scoped partitions + lineage.** S3 tables partition by `parameter_hash` only. Before publish, L2 **attaches lineage fields** to each row and L0 verifies **embed = path**:

  * `row.parameter_hash == partition.parameter_hash`
  * `row.manifest_fingerprint == manifest_fingerprint_used`
* **Atomic, idempotent publish.** tmp → fsync → rename; per-dataset **skip-if-final** at the partition level; safe re-runs are no-ops.
* **Dataset-specific logical row ordering at write:**

  * `candidate_set`: `(merchant_id, candidate_rank, country_iso)`
  * `base_weight_priors`: `(merchant_id, country_iso)`
  * `integerised_counts`: `(merchant_id, country_iso)`
  * `site_sequence`: `(merchant_id, country_iso, site_order)`
    File order is **non-authoritative** for inter-country order; only `candidate_rank` is.

## 1.5 Inputs & preconditions (summarised for L2)

* **In-memory from L1:** `Ctx`, `DecisionTrace`, `CandidateRow[]`, `RankedCandidateRow[]`, and (if enabled) `PriorRow[]`, `CountRow[]`, `SequenceRow[]`—already **schema-true (minus lineage)**. L2 **attaches lineage** and publishes.
* **Opened policy/BOM handles:** ladder/ISO/prior policies are opened read-only before orchestration (by host/L0).
* **No S1/S2 evidence reads in S3.** S3 consumes no RNG logs; prior states’ evidence/validators are out of scope for L2.

## 1.6 Success criteria (acceptance gates for this document)

* L2 calls **only** the S3·L1 kernels, in the documented order, and uses **only** L0 emitters for I/O.
* Every publish enforces: **embed = path**, **skip-if-final**, and the dataset’s **logical row order** listed above.
* **No RNG, no policy math, no schema/partition drift**; outputs are parameter-scoped and dictionary-aligned.
* `candidate_rank` remains the **sole** inter-country order; L2 does not mutate it.

---

# 2) Inputs, Preconditions & Non-Goals

## 2.1 Run-level prerequisites (must hold before S3·L2 starts)

1. **Version lock.** A single `{parameter_hash, manifest_fingerprint}` is fixed for the run and does not change mid-run.
2. **Dictionary & schemas online.** Dataset dictionary and JSON-Schema anchors for all S3 outputs are loaded and immutable for the process lifetime.
3. **L0 emitters bound.** Parameter-scoped emitters for `s3_candidate_set`, `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence` are available with atomic tmp→fsync→rename semantics.
4. **BOM/policy opened (read-only).** Ladder, ISO universe, fixed-dp (`dp`), residual-dp (`dp_resid`), integerisation/sequence knobs, and optional bounds config are materialised in memory.
5. **Work domain fixed.** The exact merchant set for this run is fixed by the controller **with a deterministic iteration order** (e.g., ascending `merchant_id` or a documented stable key).
6. **No RNG families in S3.** No PRNG seeds/counters; no event/trace writers are in scope for S3.

## 2.2 Host inputs (values, not paths)

* `parameter_hash : str` — sole partition key for all S3 outputs.
* `manifest_fingerprint : str` — embedded in rows; must equal the run’s value.
* `bom.ladder : Ladder` — governed rule family used by L1.
* `bom.iso_universe : Set[ISO2]` — closed country universe.
* `bom.dp : int`, `bom.dp_resid : int` — fixed decimals (run-constant).
* `bom.bounds? : BoundsConfig` — optional per-country L/U for counts.
* `options.emit_priors : bool`, `options.emit_counts : bool`, `options.emit_sequence : bool`.
* `runtime.N_WORKERS : int`, `runtime.batch_rows : int`, `runtime.mem_watermark : bytes` — practical throughput knobs with deterministic defaults.

> **L2 never uses paths.** Dataset IDs/partitions are resolved by L0 at publish.

## 2.3 Per-merchant inputs (computed via L1 during orchestration)

L2 invokes the **pure** S3·L1 kernels (serial per merchant) which return schema-shaped arrays **without lineage**:

1. `Ctx` ← `s3_build_ctx(…)` — includes `merchant_id`, `home_country_iso`, and fields L2 will attach at publish.
2. `DecisionTrace` ← `s3_evaluate_rule_ladder(Ctx, bom.ladder)`.
3. `CandidateRow[]` ← `s3_make_candidate_set(Ctx, DecisionTrace, bom.iso_universe, bom.ladder)` — includes **home** + admitted foreigns (closed vocab for reasons/tags).
4. `RankedCandidateRow[]` ← `s3_rank_candidates(CandidateRow[], meta_from_ladder, Ctx.home_country_iso)` — **total order**, `candidate_rank` contiguous with home=0.
5. *(opt)* `PriorRow[]` ← `s3_compute_priors(RankedCandidateRow[], bom.dp)` — fixed-dp **scores** (no renorm).
6. *(opt)* `CountRow[]` ← `s3_integerise_counts(RankedCandidateRow[], N, bom.bounds?, bom.dp_resid)` — LRR integerisation; **Σ count = N**.
7. *(opt)* `SequenceRow[]` ← `s3_sequence_within_country(CountRow[], site_id_cfg?)` — per-country `site_order` 1..nᵢ (optional 6-digit `site_id`).

> L2 **never edits** these arrays except to **attach lineage** (`parameter_hash`, `manifest_fingerprint`) immediately before publish.

## 2.4 Preconditions (checked by L2 before orchestration)

* **BOM complete:** `ladder`, `iso_universe`, `dp`, `dp_resid` present.
* **Options legal:**

  * If `emit_sequence = true` ⇒ **`emit_counts = true`**.
  * Bounds may exist **only** if `emit_counts = true`.
* **Merchant domain non-empty** or L2 exits cleanly with no publishes.
* **Single-writer rule:** no concurrent writers against the same dataset+`parameter_hash`.
* **Dictionary lock:** dataset IDs/partition templates resolved by L0 remain stable for the process lifetime.

## 2.5 Outputs (owned by L2 to publish, not compute)

Per merchant (and per enabled lane), L2 publishes via L0 the **parameter-scoped** datasets:

* **Required:** `s3_candidate_set` — logical sort: `(merchant_id, candidate_rank, country_iso)`.
* **Optional:**

  * `s3_base_weight_priors` — `(merchant_id, country_iso)`
  * `s3_integerised_counts` — `(merchant_id, country_iso)`
  * `s3_site_sequence` — `(merchant_id, country_iso, site_order)`

**Emit rules (enforced by L2):**

* **Order:** `candidate_set` → \[`priors`] → \[`counts`] → \[`sequence`].
* **Idempotence:** **skip-if-final** per dataset/`parameter_hash`.
* **Embed = path equality:** before publish, L2 attaches lineage and L0 verifies
  `row.parameter_hash == partition.parameter_hash` and
  `row.manifest_fingerprint == manifest_fingerprint_used`.

## 2.6 Non-Goals (explicitly out of scope)

* **No RNG, no timestamps in outputs.**
* **No policy math.** L2 never computes/renormalises priors, counts, or sequences; it only calls L1.
* **No schema/partition edits.** Schemas are authoritative; partitions are parameter-scoped only.
* **No validation/CI corridors.** Those live in L3/validator harness.
* **No backfill/healing.** On error, L2 routes/fails; it never fabricates rows.
* **No cross-state reads.** S3·L2 never touches S1/S2 RNG logs.

## 2.7 Failure conditions (deterministic, surfaced)

L2 **fails fast** (merchant- or run-scoped) when:

* Illegal option combo (e.g., `emit_sequence=true` with `emit_counts=false`).
* Required BOM element missing.
* Attempted publish where **final already exists** ⇒ **no-op skip** by design (`skip_if_final=true`); **not a failure**. Fail only on invariant breaches (e.g., embed≠path, manifest mismatch).
* **Embed ≠ path** lineage mismatch detected at publish time.

---

# 3) Datasets & Partitions Managed by L2

## 3.1 Inventory (what L2 *publishes*, not computes)

**Required**

* **`s3_candidate_set`** — deterministic, **sole authority for inter-country order** via `candidate_rank` (home=0, contiguous).
  **Schema:** `schemas.1A.yaml#/s3/candidate_set` · **Logical row order at write:** `(merchant_id, candidate_rank, country_iso)` · **Partition:** `parameter_hash={…}`

**Optional lanes** (emit only if enabled by run options / S3 ownership)

* **`s3_base_weight_priors`** — deterministic **scores** (fixed-dp strings), *not* probabilities.
  **Schema:** `#/s3/base_weight_priors` · **Logical order:** `(merchant_id, country_iso)` · **Partition:** `parameter_hash={…}`
* **`s3_integerised_counts`** — per-country integer counts with `residual_rank`; **Σ(count) = N** from S2.
  **Schema:** `#/s3/integerised_counts` · **Logical order:** `(merchant_id, country_iso)` · **Partition:** `parameter_hash={…}`
* **`s3_site_sequence`** — within-country `site_order` = `1..nᵢ` (and optional 6-digit `site_id`); **never** reorders countries.
  **Schema:** `#/s3/site_sequence` · **Logical order:** `(merchant_id, country_iso, site_order)` · **Partition:** `parameter_hash={…}`

> **Deprecated (not published by S3·L2):** `country_set`, `ranking_residual_cache_1A`. They are not order authorities and are kept only for dictionary backward compatibility.

---

## 3.2 Partition scope & lineage (binding)

* **Partitioning:** **parameter-scoped only.** Every S3 dataset partitions *only* by `parameter_hash` (S3 has no `seed` partitions).
* **Embedded lineage per row:** `{ parameter_hash: Hex64, manifest_fingerprint: Hex64 }`.
* **Equality rules at publish:** L2 attaches lineage, then L0 enforces
  `row.parameter_hash == partition.parameter_hash` and
  `row.manifest_fingerprint == manifest_fingerprint_used_for_run`.
  Any mismatch ⇒ write-side error (no partials).
* **No path literals in L2.** L2 references **dataset IDs**; L0 resolves dictionary → (path, schema, partitions, sort keys).

---

## 3.3 Logical row ordering (writer discipline)

L2 must hand rows to the writer in these **logical orders** (stable sorts) for deterministic, reader-friendly blocks:

* **`s3_candidate_set`**: `(merchant_id ASC, candidate_rank ASC, country_iso ASC)`; guarantees **total, contiguous** ranks and `candidate_rank(home)=0`.
  *File order outside this contract is non-authoritative for inter-country order.*
* **`s3_base_weight_priors`**: `(merchant_id, country_iso)`; priors are **not** duplicated in `candidate_set`.
* **`s3_integerised_counts`**: `(merchant_id, country_iso)`; each `count ≥ 0`, **Σ(count) = N**; persist `residual_rank`.
* **`s3_site_sequence`**: `(merchant_id, country_iso, site_order)`; `site_order` is **exactly** `1..count_i`; optional `site_id` is zero-padded 6-digit string.

---

## 3.4 Emit order, idempotence & atomicity

* **Per-dataset emit order (per run/slice):**
  `candidate_set → [priors] → [counts] → [sequence]`
  This keeps downstream joins and audits predictable.
* **Idempotence:** **skip-if-final** per dataset/`parameter_hash`. Re-runs with identical inputs produce byte-identical outputs and perform **no writes** for already-final partitions.
* **Atomic publish:** stage tmp → fsync → **atomic rename** into the dictionary location. No partials, no mismatched partitions, no cross-dataset interleaving within a partition.

---

## 3.5 Optionality & legality matrix

| Lane                 | May publish?       | Preconditions / Notes                                                                        |
|----------------------|--------------------|----------------------------------------------------------------------------------------------|
| `candidate_set`      | **Yes (required)** | Always emitted when S3 runs. **Sole order authority = `candidate_rank`.**                    |
| `base_weight_priors` | Optional           | If S3 computes priors; values are **fixed-dp scores** (run-constant `dp`), **no renorm**.    |
| `integerised_counts` | Optional           | If S3 performs integerisation; **Σ(count) = N**; `residual_rank` recorded; bounds if present |
| `site_sequence`      | Optional           | If S3 owns sequencing; **requires counts**; never permutes inter-country order.              |

**Illegal combo (reject deterministically):** `emit_sequence = true` **and** `emit_counts = false`.

---

## 3.6 Uniqueness & non-duplication (binding)

Per merchant:

* **`s3_candidate_set`**: unique `(country_iso)` and unique `(candidate_rank)`; **exactly one** home row with `is_home = true` and `candidate_rank = 0`.
* **`s3_base_weight_priors`** (if any): unique `(country_iso)`; `dp` is run-constant.
* **`s3_integerised_counts`** (if any): unique `(country_iso)`; counts are integers; `residual_rank` total and contiguous within the merchant.
* **`s3_site_sequence`** (if any): unique `(country_iso, site_order)` and (if present) unique `(country_iso, site_id)`.

Additionally, **no country outside the ISO universe** may appear in any S3 dataset.

---

## 3.7 Non-reinterpretation rules (downstream/host)

* **Inter-country order** lives **only** in `s3_candidate_set.candidate_rank`. File order and ISO lexicographic order are non-authoritative.
* **Priors** (if emitted) are **deterministic scores**; **never renormalise** in L2 or downstream.
* **Sequencing** never permutes countries; it orders **within** each country block only.

---

## 3.8 Dictionary cross-check (for implementers)

Before wiring emit calls, confirm the dictionary exposes for each dataset ID: **schema anchor**, **partition template** (parameter-scoped), and the **logical sort keys** listed above. L2 must rely on these dictionary contracts—**no hard-coded paths**.

---

# 3A) Orchestration Surfaces — Function Import Ledger

**Intent.** List every surface that **S3·L2** invokes: imported **L1 kernels**, **L0 emitters**, read-only **host shims**, and the minimal **L2-local glue** needed to orchestrate. No hidden globals, no path literals, no new policy. These IDs are the **canonical node names** referenced by §4–§7.

---

## 3A.1 Imported from S3·L1 (pure, deterministic, no I/O)

```
PROC s3_build_ctx(ingress, s1_s2_facts, bom, vocab) -> Ctx
  Purpose: Immutable per-merchant context (merchant_id, home_country_iso, N, etc.).
  Determinism: Pure (no side effects).
  Errors: Missing ingress/vocab fields ⇒ deterministic error (no partials).

PROC s3_evaluate_rule_ladder(ctx: Ctx, ladder: Ladder) -> DecisionTrace
  Purpose: Deterministic ladder decision + closed-vocab reason/filter tags.
  Determinism: Pure.

PROC s3_make_candidate_set(ctx: Ctx, trace: DecisionTrace,
                           iso_universe: Set[ISO2], ladder: Ladder) -> CandidateRow[]
  Purpose: Unordered {home ∪ admitted foreigns} with reason/filter tags.
  Guarantees: Exactly one home ISO present; no duplicates.
  Determinism: Pure.

PROC s3_rank_candidates(cands: CandidateRow[],
                        admission_meta_map: Map[ISO2,{precedence:int,priority:int,rule_id:str}],
                        home_iso: ISO2) -> RankedCandidateRow[]
  Purpose: Impose total order; `candidate_rank` contiguous; home=0.
  Source of admission_meta_map: from ladder/BOM (passed through; not constructed in L2).
  Determinism: Pure.

PROC s3_compute_priors(ranked: RankedCandidateRow[], dp: int) -> PriorRow[]   # optional
  Purpose: Fixed-decimal **scores** (not probabilities); run-constant dp; no renorm.
  Determinism: Pure.

PROC s3_integerise_counts(ranked: RankedCandidateRow[], N: int,
                          bounds?: BoundsConfig, dp_resid: int) -> CountRow[]   # optional
  Purpose: Largest-remainder integerisation; Σ count = N; `residual_rank` recorded.
  Determinism: Pure.

PROC s3_sequence_within_country(counts: CountRow[], site_id_cfg?) -> SequenceRow[]   # optional
  Purpose: Within-country `site_order` = 1..nᵢ; optional 6-digit `site_id`.
  Determinism: Pure.
```

---

## 3A.2 Imported from S3·L0 (emitters; side-effecting, dictionary-resolved)

```
PROC EMIT_S3_CANDIDATE_SET(rows: RankedCandidateRow[],
                           parameter_hash: Hex64, manifest_fingerprint: Hex64,
                           skip_if_final: bool) -> void
  Contract: Partition = parameter_hash; writer sort = (merchant_id, candidate_rank, country_iso).
            Atomic tmp→fsync→rename; idempotent (skip-if-final); embed == path enforced.

PROC EMIT_S3_BASE_WEIGHT_PRIORS(rows: PriorRow[],
                                parameter_hash: Hex64, manifest_fingerprint: Hex64,
                                skip_if_final: bool) -> void
  Contract: Writer sort = (merchant_id, country_iso); values are fixed-dp scores.

PROC EMIT_S3_INTEGERISED_COUNTS(rows: CountRow[],
                                parameter_hash: Hex64, manifest_fingerprint: Hex64,
                                skip_if_final: bool) -> void
  Contract: Writer sort = (merchant_id, country_iso); Σ count = N; residual_rank present.

PROC EMIT_S3_SITE_SEQUENCE(rows: SequenceRow[],
                           parameter_hash: Hex64, manifest_fingerprint: Hex64,
                           skip_if_final: bool) -> void
  Contract: Writer sort = (merchant_id, country_iso, site_order); never permutes inter-country order.
```

*All emitters resolve dataset IDs/paths via the dictionary. L2 provides rows already shaped/sorted and with lineage attached; L0 enforces embed=path equality.*

---

## 3A.3 Host adapters (read-only shims; no policy logic, no paths)

```
PROC HOST_OPEN_BOM() -> { ladder: Ladder, iso_universe: Set[ISO2],
                          dp: int, dp_resid: int, bounds?: BoundsConfig,
                          toggles: { emit_priors: bool, emit_counts: bool, emit_sequence: bool } }

PROC HOST_MERCHANT_LIST(parameter_hash: Hex64) -> List[merchant_id]
  Purpose: Provide the deterministic merchant worklist for this partition (e.g., ascending order).
  Determinism: order is stable for the run; returns values, not paths.

PROC OBSERVE_PARTITION_STATE(parameter_hash: Hex64)
  -> { has_any_final: bool,
       manifest_fingerprint?: Hex64,
       toggles_snapshot?: { emit_priors: bool, emit_counts: bool, emit_sequence: bool } }
  Purpose: Read-only probe for §10 resume guards; reflects on-disk truth; no writes.

PROC HOST_WORKER_POOL(N_WORKERS: int) -> Pool
  Purpose: Parallelise across merchants only; within-merchant work stays serial.

PROC HOST_DICTIONARY_HANDLE() -> DictHandle
  Purpose: Provide stable dictionary/registry handles for L0 emitters.
```

---

## 3A.4 L2-local glue (orchestration only; no policy, no I/O beyond emit)

```
PROC run_S3_L2(run_cfg) -> void
  Purpose: Entrypoint. Open BOM/handles; guard options; start worker pool; iterate merchants
           in a deterministic order; dispatch per-merchant processing; gather results.
  Notes: Enforces single-writer rule per dataset+parameter_hash.

PROC process_merchant_S3(merchant_id, run_ctx) -> PublishBundle
  Purpose: Call L1 kernels in the only legal sequence; collect arrays:
           ranked (+ priors? + counts? + sequence?) — no publishing here.

PROC package_for_emit(bundle: PublishBundle,
                      lineage: { parameter_hash: Hex64, manifest_fingerprint: Hex64 })
                      -> { cand_rows: RankedCandidateRow[],
                           prior_rows?: PriorRow[], count_rows?: CountRow[], seq_rows?: SequenceRow[] }
  Purpose: Attach lineage; apply dataset writer sorts; freeze rows for emit.
  Rule: No reshaping after this point.

PROC emit_slice_in_order(rows_by_dataset, lineage,
                         skip_if_final: bool = true) -> void
  Purpose: Emit strictly in order: candidate_set → [priors] → [counts] → [sequence];
           enforce idempotence (skip-if-final) and single-writer rule.

PROC guard_options(toggles) -> void
  Purpose: Deterministic legality checks (e.g., emit_sequence ⇒ emit_counts). Signal; do not “heal”.
```

*If any glue proves reusable across states, we can later promote it to L0; for S3 it remains L2-local and fully specified here.*

---

## 3A.5 Name registry (DAG node IDs ↔ function IDs)

| DAG Node ID             | Function ID                  |
|-------------------------|------------------------------|
| `N0_open_bom`           | `HOST_OPEN_BOM`              |
| `N1_build_ctx`          | `s3_build_ctx`               |
| `N2_eval_ladder`        | `s3_evaluate_rule_ladder`    |
| `N3_make_candidates`    | `s3_make_candidate_set`      |
| `N4_rank_candidates`    | `s3_rank_candidates`         |
| `N5_priors_opt`         | `s3_compute_priors`          |
| `N6_counts_opt`         | `s3_integerise_counts`       |
| `N7_sequence_opt`       | `s3_sequence_within_country` |
| `N8_package`            | `package_for_emit`           |
| `N9_emit_candidates`    | `EMIT_S3_CANDIDATE_SET`      |
| `N10_emit_priors_opt`   | `EMIT_S3_BASE_WEIGHT_PRIORS` |
| `N11_emit_counts_opt`   | `EMIT_S3_INTEGERISED_COUNTS` |
| `N12_emit_sequence_opt` | `EMIT_S3_SITE_SEQUENCE`      |

*These IDs will be referenced verbatim in §4 (One-Screen DAG) and §5 (Full DAG).*

---

## 3A.6 Determinism & side-effects summary

* **Pure surfaces:** All L1 kernels; L2 glue `process_merchant_S3`, `package_for_emit`, `guard_options`.
* **Side-effecting surfaces:** Only L0 emitters; `run_S3_L2` manages scheduling/dispatch (no policy).
* **RNG-free:** No PRNG or timestamps anywhere in S3·L2.
* **Parameter-scoped only:** Partitions are `parameter_hash`; lineage `{parameter_hash, manifest_fingerprint}` is attached in L2 and verified by L0 (**embed=path** equality).

---

This ledger gives a complete import map and stable names so the DAG (§4–§5) and wiring (§7) can reference them unambiguously without redefining any logic.

---

# 3B) L2 Common Glue Checklist (orchestrator-only, normative)

## A) DAG & Wiring

* [ ] **One-screen DAG** present (human view) showing mandatory path, optional lanes, and the domestic-only short-circuit.
* [ ] **Authoritative DAG spec** present: stable node IDs, full **edge list (u→v)** with optionality flags, and explicit **prohibited edges**.
* [ ] Exactly **one permitted topological order** is stated.
* [ ] **Per-merchant sequence** is strictly **serial** in the L1-kernel order (no kernel interleaving).

## B) Concurrency & Scheduling

* [ ] **Across-merchant parallelism** allowed; **within-merchant** kernels run serially.
* [ ] A **deterministic merchant iteration order** is specified (e.g., ascending `merchant_id` or a documented stable key).
* [ ] **Single-writer rule:** no concurrent writes to the same dataset + `parameter_hash`.
* [ ] Work-chunking knobs (`N_WORKERS`, batch size, memory watermark) have **safe, deterministic defaults**.

## C) Options Matrix & Dependencies

* [ ] Options and **legal combinations** are listed (e.g., `emit_sequence` **requires** `emit_counts`; `emit_counts` may depend on priors/shares policy).
* [ ] **Illegal combos** raise deterministic, documented errors (L2 routes; it does not “heal”).

## D) Publish Discipline (per dataset)

* [ ] **Per-dataset emit order** is stated: **`candidate_set → [priors] → [counts] → [sequence]`**.
* [ ] **Skip-if-final** semantics per dataset/partition (`parameter_hash`) are explicit; re-runs are safe no-ops.
* [ ] **Atomic publish** via L0 emitters (tmp → fsync → rename); **no path literals** in L2.
* [ ] **Logical row sort keys** listed inline (applied in `package_for_emit(...)`):

  * `candidate_set`: `(merchant_id, candidate_rank, country_iso)`
  * `base_weight_priors`: `(merchant_id, country_iso)`
  * `integerised_counts`: `(merchant_id, country_iso)`
  * `site_sequence`: `(merchant_id, country_iso, site_order)`

## E) Determinism & Lineage

* [ ] L2 is **RNG-free** and writes **no timestamps** into rows.
* [ ] Outputs are **parameter-scoped only** (partition key = `parameter_hash`; **no `seed`**).
* [ ] L2 **attaches lineage** in `package_for_emit(...)`; L0 verifies **embed = path** at publish:

  * `row.parameter_hash == partition.parameter_hash`
  * `row.manifest_fingerprint == run.manifest_fingerprint`
* [ ] **Inter-country order authority = `candidate_rank` only** (home = 0; contiguous). File order is non-authoritative.

## F) Orchestration Surfaces (no reinvention)

* [ ] L2 **does not re-define** L0/L1 helpers; it **imports** them per §3A.
* [ ] The **Function Import Ledger** (§3A.5) maps each surface to its L2 call site (node ID).

### Function Import Ledger (this doc’s surfaces ↔ sections)

| Surface                            | Source | Purpose (1-liner)                          | Called from (L2 § / Node) |
|------------------------------------|--------|--------------------------------------------|---------------------------|
| `s3_build_ctx`                     | L1     | Build per-merchant context (`Ctx`)         | §7.1 / N1                 |
| `s3_evaluate_rule_ladder`          | L1     | Rule ladder → `DecisionTrace`              | §7.2 / N2                 |
| `s3_make_candidate_set`            | L1     | `{home}+foreigns` with reasons/tags        | §7.3 / N3                 |
| `s3_rank_candidates`               | L1     | Total order; set `candidate_rank` (home=0) | §7.4 / N4                 |
| `s3_compute_priors` (opt)          | L1     | Fixed-dp scores (no renorm)                | §7.5 / N5                 |
| `s3_integerise_counts` (opt)       | L1     | LRR integerisation; Σ = N                  | §7.6 / N6                 |
| `s3_sequence_within_country` (opt) | L1     | Contiguous `site_order`; optional IDs      | §7.7 / N7                 |
| `package_for_emit`                 | L2     | Attach lineage; apply writer sorts         | §7.8 / N8                 |
| `EMIT_S3_CANDIDATE_SET`            | L0     | Atomic publish; idempotent                 | §9 / N9                   |
| `EMIT_S3_BASE_WEIGHT_PRIORS` (opt) | L0     | Atomic publish; idempotent                 | §9 / N10                  |
| `EMIT_S3_INTEGERISED_COUNTS` (opt) | L0     | Atomic publish; idempotent                 | §9 / N11                  |
| `EMIT_S3_SITE_SEQUENCE` (opt)      | L0     | Atomic publish; idempotent                 | §9 / N12                  |
| `HOST_OPEN_BOM`                    | Host   | Open policy handles (read-only)            | §2 / §6 / N0              |
| `HOST_WORKER_POOL`                 | Host   | Across-merchant worker pool                | §6                        |

> Low-level L0 internals (`RESOLVE_S3_DATASET`, `OPEN_WRITER`, etc.) are **encapsulated** by the `EMIT_*` surfaces and are not called from L2.

## G) Error Taxonomy (deterministic, minimal)

* [ ] Merchant-scoped errors (illegal option combos, missing policy handles) have **stable codes**.
* [ ] Dataset-scoped “final exists” is handled as an idempotent **skip** (not an error) when `skip_if_final = true`.
* [ ] On kernel failure, **stop emits** for that merchant; never fabricate rows/backfill.

## H) Logging (operational, not evidence)

* [ ] Deterministic, human-readable progress (merchants processed; datasets published/skipped).
* [ ] No event/trace logs (S3 has none).

## I) Resource & Throughput Knobs (practical)

* [ ] Documented knobs with **deterministic defaults** (`N_WORKERS`, batch sizes, memory watermark).
* [ ] Single-machine focus; modest multi-core allowed; no cluster assumptions.

## J) Acceptance Gates (for the L2 section set)

* [ ] DAG (§A) + options matrix (§C) + publish protocol (§D) + determinism/lineage (§E) are all present and consistent.
* [ ] Orchestration uses only imported L0/L1/Host surfaces; **Function Import Ledger** is complete.
* [ ] No RNG, no policy math, no schema/partition drift, no path literals.
* [ ] Byte-identical outputs for fixed inputs/lineage.

---

# 4) One-Screen DAG (Human)

## 4.1 Legend (read this first)

* **\[■] Required node** · **\[◇] Optional node (guarded by options)**
* **────** required edge · **- - -** optional edge (taken only if the option is enabled and inputs exist)
* **⟂** **options-off short-circuit** (all optional lanes disabled)
* **Node IDs** are the canonical IDs from **§3A.5** (do not rename).

## 4.2 Run-level view (open once → fan out → gather)

```
[■ N0_open_bom: HOST_OPEN_BOM] ──► [■ Start worker pool (across merchants)]
                                          │
                                          ▼
                               per-merchant DAG (below, in parallel)
                                          │
                                          ▼
                                   [■ Gather / finalize]
```

Constraints: open BOM once; parallelism is **across merchants only**; each merchant executes the per-merchant DAG **serially**.

## 4.3 Per-merchant DAG (strict kernel order, then package → emit)

```
          ┌──────────────────────────────────────────────────────────────────┐
          │                         L1 KERNELS (pure)                        │
          └──────────────────────────────────────────────────────────────────┘
[■ N1_build_ctx: s3_build_ctx]
        │
        ▼
[■ N2_eval_ladder: s3_evaluate_rule_ladder]
        │
        ▼
[■ N3_make_candidates: s3_make_candidate_set]
        │
        ▼
[■ N4_rank_candidates: s3_rank_candidates]  ── establishes candidate_rank (home=0, contiguous)
        │
        ├──────────────⟂────────────────────────────────────────────────────────┐
        │                                                                        │
        │            (all optional lanes disabled)                               │
        │                                                                        ▼
        │                                                           [■ N8_package: package_for_emit]
        │                                                                        │
        │                                                                        ▼
        │                                                           [■ N9_emit_candidates: EMIT_S3_CANDIDATE_SET]
        │                                                                        │
        │                                                                        └──────► END (for this merchant)
        │
        │  (one or more optional lanes enabled and inputs present)
        ▼
[◇ N5_priors_opt: s3_compute_priors] - - - - - - - - - - - - - - - - - - - - - -┐
        │                                                                       │
        ▼                                                                       │
[◇ N6_counts_opt: s3_integerise_counts]   (Σ count = N; bounds if provided)     │
        │                                                                       │
        ▼                                                                       │
[◇ N7_sequence_opt: s3_sequence_within_country]   (requires counts)             │
        │                                                                       │
        └───────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
                       [■ N8_package: package_for_emit]
                                     │
                                     ▼
        [■ N9_emit_candidates] ─► [◇ N10_emit_priors_opt] ─► [◇ N11_emit_counts_opt] ─► [◇ N12_emit_sequence_opt]
```

### 4.3.1 Notes that bind this DAG

* **Serial within merchant.** `N1 → N2 → N3 → N4` always executes in order. Optional nodes `N5–N7` are taken only if enabled **and** legal (see §3B Options Matrix).
* **Domestic-only is not a skip.** If the ladder admits only the home country, optional lanes may still run when enabled (e.g., counts/sequence for home only). The **⟂** short-circuit triggers **only** when *all* optional lanes are disabled.
* **Single package point.** `N8_package` runs once—either directly after `N4` (when ⟂) or after the last enabled optional kernel. **Lineage is attached** and **writer sorts are applied** at `N8`; no reshaping after this point.
* **Emit order is fixed.** `N9 → N10? → N11? → N12?` is the mandatory dataset order. Each emit is idempotent (`skip_if_final=true`) and atomic (tmp→fsync→rename).

## 4.4 Prohibited edges (must not appear)

* Any edge that **reorders kernels** (e.g., `N3 → N2`, `N4 → N3`).
* Emitting **before** packaging (`N9/N10/N11/N12 → N8`).
* `N7` reachable when `N6` not taken (**sequencing requires counts**).
* Cross-merchant edges that interleave emits for the **same** dataset partition (violates single-writer rule).

## 4.5 Single permitted topological order (per merchant)

A valid linearization is:

```
N1 → N2 → N3 → N4 → [N5?] → [N6?] → [N7?] → N8 → N9 → [N10?] → [N11?] → [N12?]
```

`?` denotes optional nodes whose inclusion is governed by the options and legality rules in **§3B**.

---

This one-screen DAG is the human backbone. **§5 (Full DAG Specification)** will enumerate the same nodes/edges formally with the edge list and data contracts; **§7 (Kernel Wiring)** will show the exact call sites using the function IDs already fixed in **§3A**.

---

# 5) Full DAG Specification (Authoritative)

## 5.1 Node registry (stable IDs, types, sources)

| ID  | Human name                    | Function ID (source)              | Type              | Optional | Purpose (one-liner)                                                |
|-----|-------------------------------|-----------------------------------|-------------------|----------|--------------------------------------------------------------------|
| N0  | Open BOM                      | `HOST_OPEN_BOM` (Host)            | side-effect (RO)  | No       | Open ladder/ISO/dp/bounds/toggles for the run (read-only values).  |
| N1  | Build context                 | `s3_build_ctx` (L1)               | pure              | No       | Build immutable per-merchant `Ctx` (IDs, home ISO, lineage tuple). |
| N2  | Evaluate rule ladder          | `s3_evaluate_rule_ladder` (L1)    | pure              | No       | Deterministic rule decision → `DecisionTrace`.                     |
| N3  | Make candidate set            | `s3_make_candidate_set` (L1)      | pure              | No       | `{home} ∪ admitted foreigns` with reason/filter tags.              |
| N4  | Rank candidates               | `s3_rank_candidates` (L1)         | pure              | No       | Impose total order; **`candidate_rank` contiguous; home=0**.       |
| N5  | Compute priors                | `s3_compute_priors` (L1)          | pure              | Yes      | Fixed-dp **scores** (no renorm).                                   |
| N6  | Integerise counts             | `s3_integerise_counts` (L1)       | pure              | Yes      | LRR integerisation; Σcount = **N**; apply bounds if provided.      |
| N7  | Sequence within country       | `s3_sequence_within_country` (L1) | pure              | Yes      | Per-country `site_order` 1..nᵢ; optional 6-digit `site_id`.        |
| N8  | Package for emit              | `package_for_emit` (L2)           | pure              | No       | Attach lineage; apply writer sorts; freeze rows for emit.          |
| N9  | Emit candidate_set            | `EMIT_S3_CANDIDATE_SET` (L0)      | side-effect (I/O) | No       | Atomic/idempotent publish of `s3_candidate_set`.                   |
| N10 | Emit base_weight_priors (opt) | `EMIT_S3_BASE_WEIGHT_PRIORS` (L0) | side-effect (I/O) | Yes      | Atomic/idempotent publish of `s3_base_weight_priors`.              |
| N11 | Emit integerised_counts (opt) | `EMIT_S3_INTEGERISED_COUNTS` (L0) | side-effect (I/O) | Yes      | Atomic/idempotent publish of `s3_integerised_counts`.              |
| N12 | Emit site_sequence (opt)      | `EMIT_S3_SITE_SEQUENCE` (L0)      | side-effect (I/O) | Yes      | Atomic/idempotent publish of `s3_site_sequence`.                   |

*Notes:* “pure” = deterministic, no I/O; “side-effect (RO)” = read-only side effect (opening handles/values); “side-effect (I/O)” = writer emit via L0.

---

## 5.2 Edge list (u → v) with guards

**Required spine**

* `N0 → N1`
* `N1 → N2`
* `N2 → N3`
* `N3 → N4`
* `N8 → N9`  *(package precedes first emit)*

**Optional lanes (taken only if enabled & legal; see §3B)**

* `N4 → N5` *(if `emit_priors = true`)*
* `N5 → N6` *(if `emit_counts = true`)*
  **or** `N4 → N6` *(if `emit_counts = true` and priors disabled)*
* `N6 → N7` *(if `emit_sequence = true` **and** `emit_counts = true`)*
* `{ last of (N4, N5, N6, N7) actually taken } → N8`
* `N9 → N10` *(if `emit_priors = true`)*
* `N10 → N11` *(if `emit_counts = true`)* **or** `N9 → N11` *(if priors disabled and `emit_counts = true`)*
* `N11 → N12` *(if `emit_sequence = true`)*
* **Short-circuit to package:** `N4 → N8` **only if** *all* optional lanes are disabled (`emit_priors = emit_counts = emit_sequence = false`)

**Prohibited edges (must not exist)**

* Any kernel reordering (e.g., `N3 → N2`, `N4 → N3`).
* Emitting **before** packaging (`N9/N10/N11/N12 → N8`).
* `N7` reachable when `N6` not taken (sequencing without counts).
* Cross-merchant edges that interleave writers for the **same** dataset partition.

---

## 5.3 Data contracts on edges (payloads in flight)

> All payloads are **in-memory values** (no lineage yet) until `N8`, where lineage is attached.

* **`N1 → N2`**: `Ctx`
* **`N2 → N3`**: `DecisionTrace`
* **`N3 → N4`**: `CandidateRow[]`  *(unordered; contains exactly one home ISO; no duplicates)*
* **`N4 → {N5 or N6 or N8}`**: `RankedCandidateRow[]`
  Guarantees: `candidate_rank` contiguous starting at 0 for home; per-merchant uniqueness of `(country_iso)` and `(candidate_rank)`.
* **`N5 → {N6 or N8}`**: `PriorRow[]` *(if enabled; fixed-dp scores; one per `(merchant_id, country_iso)`)*
* **`N6 → {N7 or N8}`**: `CountRow[]` *(if enabled; Σcount = N; each row carries `residual_rank`)*
* **`N7 → N8`**: `SequenceRow[]` *(if enabled; per-country `site_order = 1..count_i`; optional zero-padded 6-digit `site_id`)*
* **`N8 → N9/N10/N11/N12`**: `{ cand_rows, prior_rows?, count_rows?, seq_rows? }`
  Lineage now attached to each row: `{ parameter_hash, manifest_fingerprint }`.
  Writer sorts applied:

  * `candidate_set`: `(merchant_id, candidate_rank, country_iso)`
  * `base_weight_priors`: `(merchant_id, country_iso)`
  * `integerised_counts`: `(merchant_id, country_iso)`
  * `site_sequence`: `(merchant_id, country_iso, site_order)`

---

## 5.4 Guards & short-circuit rules

* **Options-off short-circuit.** If **all** optional lanes are disabled, execute `N4 → N8 → N9` and skip `N5–N7` and `N10–N12`.
  *Domestic-only merchants **do not** short-circuit by themselves; optional lanes may still run for home-only if enabled.*
* **Options legality (pre-checked):**

  * `emit_sequence = true` **requires** `emit_counts = true`.
  * Bounds may be provided **only** when `emit_counts = true`.
* **Counts dependence.** If `emit_counts = true`, `N6` consumes ranked candidates (and priors if the integerisation policy uses them, as defined in L1). L2 **never** computes or renormalises shares.
* **Single package point.** Exactly one `N8` per merchant, after the last taken kernel node.

---

## 5.5 Concurrency window & scheduling discipline

* **Across merchants:** may run `N1..N12` in parallel for different merchants using a worker pool.
* **Within a merchant:** execute
  `N1 → N2 → N3 → N4 → [N5?] → [N6?] → [N7?] → N8 → N9 → [N10?] → [N11?] → [N12?]` **serially**.
* **Single-writer rule:** never run two emitters concurrently that target the **same** dataset partition `(dataset_id, parameter_hash)`.
* **Deterministic merchant iteration:** use a stable order (e.g., ascending `merchant_id`); file order is non-authoritative beyond each dataset’s writer sort.

---

## 5.6 Emit protocol binding (dataset semantics)

* **`N9` — candidate_set (required).** Parameter-scoped partition; L0 enforces **embed = path** and **skip-if-final**; atomic tmp→fsync→rename.
* **`N10` — base_weight_priors (optional).** Same partition/idempotence rules; values are **scores** (no renorm).
* **`N11` — integerised_counts (optional).** Σcount = N must already hold (from L1); `residual_rank` present.
* **`N12` — site_sequence (optional).** Requires counts; never permutes inter-country order; writer sort `(merchant_id, country_iso, site_order)`.

---

## 5.7 Failure propagation (deterministic, no healing)

* If any kernel node (`N1–N7`) fails for a merchant, **do not** execute `N8–N12` for that merchant; surface the failure to the run controller.
* If an emit node signals “final exists” and `skip_if_final = true`, treat as **idempotent skip** (not an error).
* If **embed ≠ path** at any emit node, fail that merchant’s publish immediately (writer-side invariant breach).
* L2 never fabricates rows or backfills; reruns with the same lineage are safe no-ops wherever finals already exist.

---

## 5.8 Single permitted topological order (normalized form)

Per merchant, the only legal linearization is:

```
N1 → N2 → N3 → N4 → [N5?] → [N6?] → [N7?] → N8 → N9 → [N10?] → [N11?] → [N12?]
```

`?` nodes appear only if their guards in **§5.4** evaluate true.

---

## 5.9 Cross-reference map (for implementers)

* **Surfaces:** §3A (Function Import Ledger)
* **Checklist gates:** §3B (Common Glue Checklist)
* **Datasets/partitions/sorts:** §3 (Datasets & Partitions Managed by L2)
* **Per-merchant “human” view:** §4 (One-Screen DAG)

---

This section is the authoritative wiring: if any other place disagrees with **§5**, **§5 wins**.

---

# 6) Concurrency & Scheduling Model

## 6.1 Goals & Constraints

* **Deterministic & reproducible.** Same inputs/lineage ⇒ same bytes on disk.
* **Across-merchant parallelism only.** Within a merchant, execution is **strictly serial** in the DAG order.
* **Single-writer rule.** Never write concurrently to the **same** dataset + `parameter_hash` partition.
* **Idempotent re-runs.** All emits use `skip_if_final=true`; reruns become no-ops where finals exist.
* **No RNG, no timestamps in rows.** S3 is deterministic; clocks do not affect outputs.

## 6.2 Work Unit & Domain

* **Work unit:** one **merchant** (identified by `merchant_id`) processed through the per-merchant DAG (**§5**), producing 1–4 S3 datasets depending on options.
* **Domain:** a deterministic, finite list of merchants selected by the run controller for this `{parameter_hash, manifest_fingerprint}`.

## 6.3 Worker-Pool Topology (single-machine, multi-core)

* **Pool:** `HOST_WORKER_POOL(N_WORKERS)` creates a fixed-size pool.
* **Queue:** bounded FIFO with deterministic dispatch (see §6.4).
* **Affinity:** none needed; workers are stateless; all state is carried in task payloads.

## 6.4 Deterministic Dispatch Order

* **Merchant iteration order:** ascending `merchant_id` (or the run controller’s documented stable order).
* **Dispatch policy:** push tasks to the queue **in that order**; worker completion order does **not** affect file ordering beyond each dataset’s **writer sort** (see §3).
* **Backpressure:** when the queue is full, the producer blocks; no reordering.

## 6.5 Within-Merchant Serial Execution

Execute the **exact linearization** (per merchant):

```
N1 → N2 → N3 → N4 → [N5?] → [N6?] → [N7?] → N8 → N9 → [N10?] → [N11?] → [N12?]
```

Option-guarded nodes (`?`) are included/excluded per **§3B** and **§5.4**. **No interleaving** of kernels or emits for the same merchant.

## 6.6 Packaging & Emit Window

* **Single package point:** call `package_for_emit` (N8) **once per merchant**, *after* the last taken kernel node.
* **Attach lineage** (`parameter_hash`, `manifest_fingerprint`) here.
* **Apply writer sorts** here; rows are frozen post-`N8`.
* **Emit sequence:** `EMIT_S3_CANDIDATE_SET` → `[EMIT_S3_BASE_WEIGHT_PRIORS]?` → `[EMIT_S3_INTEGERISED_COUNTS]?` → `[EMIT_S3_SITE_SEQUENCE]?` (N9→N12).

## 6.7 Single-Writer Rule (enforcement)

* Hold a **writer lock per dataset+partition** during each `EMIT_*`. L2 must **not** schedule two emits that target the same `(dataset_id, parameter_hash)` concurrently (L0 may implement the lock internally; L2 must still avoid scheduling overlap).
* Safe default: **serialize emits** per merchant (N9..N12) and avoid cross-merchant overlap to the same dataset partition (since `parameter_hash` is run-constant).

## 6.8 Memory & Buffering Discipline

* **Per-worker memory bound:** keep only **one merchant’s arrays** resident at a time (ranked + optional priors/counts/sequence).
* **Row batching:** if emitters support chunked writes, use a deterministic `batch_rows` (e.g., 10–50k) per dataset; otherwise emit the full merchant slice in one call.
* **No caching across merchants** in L2.

## 6.9 Idempotence & Resume

* **Skip-if-final:** set `skip_if_final=true` on every `EMIT_*` call. If final exists, treat as **skip** (not error).
* **Resume semantics:** rerunning `run_S3_L2` with the **same** `{parameter_hash, manifest_fingerprint}` is safe; merchants already published are skipped at emit time. Kernels may still run but must not publish duplicates.

## 6.10 Options Matrix & Gatekeeping

* Call `guard_options(toggles)` **before** starting the pool.
* Enforce: `emit_sequence ⇒ emit_counts`; bounds only valid if `emit_counts=true`.
* If illegal, **fail fast** (run-scoped) before queuing any merchant.

## 6.11 Failure Handling (deterministic)

* **Kernel failure (N1–N7):** stop `N8–N12` for that merchant; surface a merchant-scoped failure to the run controller; continue with other merchants.
* **Emit invariant breach:** if `embed ≠ path` or the writer signals a non-idempotent error, mark merchant as failed; do not attempt subsequent emits for that merchant.
* **No healing/backfill** at L2.

## 6.12 Practical Defaults & Safe Ranges

* `N_WORKERS`: default = `min(physical_cores, 8)`; safe range 1–32.
* `batch_rows`: default = `20_000` (if emitters support chunking); safe range 5_000–100_000.
* `mem_watermark`: choose to keep per-worker peak below available RAM / `N_WORKERS` (e.g., 256–512 MB per worker), given expected merchant slice sizes.

## 6.13 Task Payload (what each worker receives)

Each submitted task gets a **run context** with **values only** (no paths):

* `lineage`: `{ parameter_hash, manifest_fingerprint }`
* `toggles`: `{ emit_priors, emit_counts, emit_sequence }`
* `bom`: `{ ladder, iso_universe, dp, dp_resid, bounds?, site_id_cfg?, admission_meta_map, vocab }`
* `inputs`: `{ ingress_by_id : Map[merchant_id → IngressRow], s1s2_by_id : Map[merchant_id → S1S2Facts] }`

> These come from **Host/L0** set-up prior to orchestration (see §2 and §3A.3). L2 reads values from this context; it never opens files or resolves paths.

## 6.14 Scheduling Pseudocode (host-neutral)

*(References surfaces from §3A; orchestration-only, no policy, no paths.)*

```
PROC run_S3_L2(run_cfg):
  bom := HOST_OPEN_BOM()
  guard_options(run_cfg.toggles)
  part_state := OBSERVE_PARTITION_STATE(parameter_hash = run_cfg.parameter_hash)
  guard_resume(run_cfg, part_state)

  pool := HOST_WORKER_POOL(run_cfg.N_WORKERS)
  FOR merchant_id IN HOST_MERCHANT_LIST(run_cfg.parameter_hash):
    pool.submit( TASK process_merchant_S3(merchant_id,
                  run_ctx = {bom, toggles=run_cfg.toggles,
                             inputs=run_cfg.inputs,
                             lineage={parameter_hash=run_cfg.parameter_hash,
                                      manifest_fingerprint=run_cfg.manifest_fingerprint}}) )
  pool.join_all()
END PROC

PROC process_merchant_S3(merchant_id, run_ctx):
  // Kernels (pure; L2 does no I/O)
  ingress := run_ctx.inputs.ingress_by_id[merchant_id]
  facts   := run_ctx.inputs.s1s2_by_id[merchant_id]

  ctx    := s3_build_ctx(ingress, facts, run_ctx.bom, run_ctx.bom.vocab)
  trace  := s3_evaluate_rule_ladder(ctx, run_ctx.bom.ladder)
  cands  := s3_make_candidate_set(ctx, trace, run_ctx.bom.iso_universe, run_ctx.bom.ladder)
  ranked := s3_rank_candidates(cands, run_ctx.bom.admission_meta_map, ctx.home_country_iso)

  priors   := run_ctx.toggles.emit_priors   ? s3_compute_priors(ranked, run_ctx.bom.dp) : NULL
  counts   := run_ctx.toggles.emit_counts   ? s3_integerise_counts(ranked, ctx.N, run_ctx.bom.bounds?, run_ctx.bom.dp_resid) : NULL
  sequence := run_ctx.toggles.emit_sequence ? s3_sequence_within_country(counts, run_ctx.bom.site_id_cfg?) : NULL

  // Package (attach lineage; writer sorts)
  rows := package_for_emit(
            bundle  = { ranked, priors?, counts?, sequence? },
            lineage = run_ctx.lineage)

  // Emit (idempotent; atomic; in order; single-writer rule respected)
  emit_slice_in_order(rows, lineage = run_ctx.lineage, skip_if_final = TRUE)
END PROC
```

## 6.15 Acceptance Checklist (for this section)

* Deterministic merchant iteration and **across-merchant parallelism** defined.
* **Within-merchant serial** execution guaranteed; DAG order preserved.
* **Single-writer rule** enforced; no concurrent writers to the same dataset partition.
* **Idempotent emits** (`skip_if_final`) and **atomic publish** mandated.
* **No RNG, no timestamps**, no policy math in L2; only L1 kernels + L0 emitters used.
* Memory/batching guidance present; resume semantics are safe and defined.
* Task payload enumerated; no undefined surfaces or path literals.

---

# 7) Kernel Wiring (Per-Merchant Orchestration)

## 7.1 Intent & invariants

**Intent.** For a single `merchant_id`, invoke S3·L1 kernels in the only legal order, then **package** outputs (attach lineage, apply writer sorts) and **emit** datasets via L0 in a fixed order.

**Invariants.**

* No RNG; no timestamps in rows.
* Within this merchant, execution is **strictly serial** in the order below.
* Inter-country order authority is **`candidate_rank` (home=0, contiguous)** as produced by ranking; L2 never mutates it.
* Outputs are **parameter-scoped**; lineage `{parameter_hash, manifest_fingerprint}` is attached exactly once at packaging.

---

## 7.2 Inputs (per merchant) and outputs (by dataset)

**Inputs (from host/run context; values only):**

* `merchant_id`
* `run.lineage`: `{ parameter_hash: Hex64, manifest_fingerprint: Hex64 }`
* `bom`: `{ ladder, iso_universe, dp, dp_resid, bounds?, site_id_cfg?, admission_meta_map, vocab }`
* `ingress`, `s1_s2_facts` (the minimal facts L1 expects)

**Outputs (after emit, if lanes enabled):**

* `s3_candidate_set` (required)
* `s3_base_weight_priors` (optional)
* `s3_integerised_counts` (optional)
* `s3_site_sequence` (optional)

---

## 7.3 The only legal kernel sequence (N1 → N8)

> Node IDs match §5; surfaces match §3A.

### 7.3.1 N1 — Build context (pure)

```
ingress := HOST_GET_INGRESS(merchant_id)
facts   := HOST_GET_S1S2_FACTS(merchant_id)
ctx     := s3_build_ctx(ingress, facts, bom, bom.vocab)
```

**Produces:** immutable `ctx` (includes `merchant_id`, `home_country_iso`, **`N`** from S2, etc.).

### 7.3.2 N2 — Evaluate rule ladder (pure)

```
trace := s3_evaluate_rule_ladder(ctx, bom.ladder)
```

**Produces:** deterministic `DecisionTrace` with closed-vocab tags.

### 7.3.3 N3 — Make candidate set (pure)

```
cands := s3_make_candidate_set(ctx, trace, bom.iso_universe, bom.ladder)
```

**Guarantees (pre-rank):** contains **exactly one** home ISO; no duplicate ISO entries.

### 7.3.4 N4 — Rank candidates (pure)

```
ranked := s3_rank_candidates(cands,
                             bom.admission_meta_map,   // from BOM (policy), not built in L2
                             ctx.home_country_iso)
```

**Guarantees (post-rank):** `candidate_rank` is total and **contiguous**; home has rank **0**; per-merchant uniqueness across `(country_iso)` and `(candidate_rank)`.

---

## 7.4 Optional lanes (N5–N7), guarded by options & legality

> Evaluate guards **before** calling; see §3B Options Matrix.

### 7.4.1 N5 — Priors (pure, optional)

```
priors := bom.toggles.emit_priors
          ? s3_compute_priors(ranked, bom.dp)
          : NULL
```

**Semantics:** fixed-dp **scores** (not probabilities); **no renorm**.

### 7.4.2 N6 — Integerise counts (pure, optional)

```
counts := bom.toggles.emit_counts
          ? s3_integerise_counts(ranked, ctx.N, bom.bounds?, bom.dp_resid)
          : NULL
```

**Semantics:** Largest-Remainder integerisation; **Σ count = ctx.N**; `residual_rank` recorded per row. Bounds, if supplied, enforced here (pure).

### 7.4.3 N7 — Sequence within country (pure, optional; requires counts)

```
sequence := bom.toggles.emit_sequence
            ? s3_sequence_within_country(counts, bom.site_id_cfg?)
            : NULL
```

**Guard:** `emit_sequence` **requires** `emit_counts`.
**Semantics:** `site_order = 1..count_i` per country; optional zero-padded 6-digit `site_id`. Countries are **never** reordered.

---

## 7.5 N8 — Package for emit (attach lineage; apply writer sorts; pure)

```
rows := package_for_emit(
          bundle  = { ranked, priors?, counts?, sequence? },
          lineage = { parameter_hash      = run.lineage.parameter_hash,
                      manifest_fingerprint= run.lineage.manifest_fingerprint })
```

**`package_for_emit` responsibilities (and return shape):**

* Attach lineage to every row.
* Apply **writer sorts** (logical row ordering) for each dataset:

  * `candidate_set`: `(merchant_id, candidate_rank, country_iso)`
  * `base_weight_priors`: `(merchant_id, country_iso)`
  * `integerised_counts`: `(merchant_id, country_iso)`
  * `site_sequence`: `(merchant_id, country_iso, site_order)`
* **Return**:
  - `candidate_rows   : RankedCandidateRow[]`
  - `prior_rows?      : PriorRow[]`
  - `count_rows?      : CountRow[]`
  - `sequence_rows?   : SequenceRow[]`
* **Freeze** rows; no reshaping after packaging.

---

## 7.6 Emit sequence (N9 → N12): idempotent, atomic (side-effect via L0)

```
EMIT_S3_CANDIDATE_SET   (rows.candidate_rows,  run.lineage.parameter_hash, run.lineage.manifest_fingerprint, TRUE)

IF rows.prior_rows    != NULL: EMIT_S3_BASE_WEIGHT_PRIORS (rows.prior_rows,    run.lineage.parameter_hash, run.lineage.manifest_fingerprint, TRUE)
IF rows.count_rows    != NULL: EMIT_S3_INTEGERISED_COUNTS (rows.count_rows,    run.lineage.parameter_hash, run.lineage.manifest_fingerprint, TRUE)
IF rows.sequence_rows != NULL: EMIT_S3_SITE_SEQUENCE      (rows.sequence_rows, run.lineage.parameter_hash, run.lineage.manifest_fingerprint, TRUE)
```

**Rules:** fixed dataset order **candidate → \[priors] → \[counts] → \[sequence]**; each emit is idempotent (`skip_if_final=true`), atomic (tmp→fsync→rename), and enforces **embed=path**.

---

## 7.7 Pre/Postconditions (per step)

| Step   | Preconditions                     | Postconditions                                                               |
|--------|-----------------------------------|------------------------------------------------------------------------------|
| N1     | ingress + s1/s2 facts; BOM opened | `ctx` built; immutable; includes `home_country_iso`, `N`                     |
| N2     | `ctx`                             | `trace` produced; pure                                                       |
| N3     | `ctx`, `trace`, `iso_universe`    | `cands` non-empty; exactly one home; no duplicate ISO                        |
| N4     | `cands`, `bom.admission_meta_map` | `ranked` with contiguous `candidate_rank`; home=0; per-merchant uniqueness   |
| N5     | `ranked`; `emit_priors==true`     | `priors` (scores, fixed-dp) or `NULL`                                        |
| N6     | `ranked`; `emit_counts==true`     | `counts` with **Σ count = ctx.N**; `residual_rank`; or `NULL`                |
| N7     | `counts`; `emit_sequence==true`   | `sequence` with per-country `site_order = 1..nᵢ`; optional 6-digit `site_id` |
| N8     | arrays ready                      | lineage attached; writer sorts applied; rows frozen                          |
| N9–N12 | packaged rows by dataset          | idempotent, atomic publishes in fixed order; partitions are parameter-scoped |

---

## 7.8 Failure routing (merchant-scoped; no healing)

* If any kernel `N1–N7` fails ⇒ **do not** call `N8–N12`; surface a merchant-scoped failure to the run controller.
* If an emitter reports “final exists” with `skip_if_final=true` ⇒ treat as **idempotent skip** (not an error).
* If an emitter detects **embed ≠ path** ⇒ fail this merchant’s publish immediately; no subsequent emits for this merchant.

---

## 7.9 Acceptance gates (for this section)

* Calls **only** the surfaces named in §3A; no new helpers invented.
* Exact sequence `N1→N2→N3→N4→[N5?]→[N6?]→[N7?]→N8→N9→[N10?]→[N11?]→[N12?]` is followed.
* Lineage is attached **once** at packaging; writer sorts applied there.
* Emit order is fixed; idempotence and atomic publish mandated.
* **No RNG**, **no timestamps**, **no renorm**, **no path literals**; inter-country order remains `candidate_rank` as produced at `N4`.

---

# 8) Options Matrix & Dependency Rules

## 8.1 Purpose

Define the **only legal ways** the optional lanes (priors, counts, sequence) may be enabled, and the **deterministic rules** L2 enforces **before** orchestration. These rules control which nodes (`N5–N7`, `N10–N12`) appear in the DAG per merchant and guarantee that **no illegal path** can run.

---

## 8.2 Toggles (run-level) and derived enables (merchant-level)

**Run-level toggles** (opened from BOM; see §2 & §3A):

* `emit_priors : bool`
* `emit_counts : bool`
* `emit_sequence : bool`

**Derived merchant-level enables** (computed once per merchant **after** `N4` ranking):

```
enable_priors    := emit_priors
enable_counts    := emit_counts
enable_sequence  := emit_sequence AND enable_counts   // sequencing requires counts
```

> L2 **does not** derive policy from data. If a lane is enabled but its input slice is empty, the lane still runs and produces zero rows; legality is about **wiring**, not volume. (Note: S3 multi-site guarantees `N ≥ 2`; a domestic-only merchant simply has all N in home.)

---

## 8.3 Legality matrix (run-level)

Reject illegal rows **before** any merchant is queued.

| Case | `emit_priors` | `emit_counts` | `emit_sequence` | Legal? | Reason / Rule                          |
|-----:|:-------------:|:-------------:|:---------------:|:------:|----------------------------------------|
|    A |       0       |       0       |        0        |   ✓    | Candidate set only.                    |
|    B |       1       |       0       |        0        |   ✓    | Priors only (scores; independent).     |
|    C |       0       |       1       |        0        |   ✓    | Counts only (Σ=N).                     |
|    D |       1       |       1       |        0        |   ✓    | Priors + counts.                       |
|    E |       0       |       0       |        1        |   ✗    | **Illegal:** sequence requires counts. |
|    F |       1       |       0       |        1        |   ✗    | **Illegal:** sequence requires counts. |
|    G |       0       |       1       |        1        |   ✓    | Counts + sequence.                     |
|    H |       1       |       1       |        1        |   ✓    | Priors + counts + sequence.            |

**Binding rule:** `emit_sequence ⇒ emit_counts`.

---

## 8.4 Dependency rules (binding semantics)

1. **Sequence depends on counts.** If `emit_sequence=true`, L2 requires `emit_counts=true`. `N7`/`N12` are unreachable without `N6`/`N11`.
2. **Counts may use priors policy (outside L2).** If integerisation uses priors, L1 handles it (pure). L2 never computes/renormalises shares or priors.
3. **Priors are scores, not probabilities.** No renormalisation in L2; only dataset **writer sorts** apply.
4. **Inter-country order is fixed before options.** `candidate_rank` (home=0, contiguous) is set at `N4` and never mutated by optional lanes.
5. **Bounds are meaningful only with counts.** If bounds exist but `emit_counts=false`, L2 ignores them (may warn). If `emit_counts=true`, L1 enforces bounds in `s3_integerise_counts` (pure).
6. **Single package point.** Regardless of lanes, L2 calls `N8` **exactly once** after the last enabled kernel and emits datasets **in order** `N9 → [N10?] → [N11?] → [N12?]`.

---

## 8.5 Options-off short-circuit (data-aware)

**Predicate:** after `N4`, if the ranked set contains **only home** *and* all optional lanes are **disabled** (`enable_priors=enable_counts=enable_sequence=0`), then L2 **short-circuits**:

```
N4 → N8 → N9   // package + emit candidate_set only
```

Domestic-only **does not** short-circuit by itself; if any lane is enabled, it still runs for home.

---

## 8.6 Guard function (normative orchestration gate)

Run this guard **before** starting the pool (and optionally per merchant; it’s idempotent).

```
PROC guard_options(toggles):
  IF toggles.emit_sequence AND NOT toggles.emit_counts:
      RAISE ERROR O-ILLEGAL-SEQ-WITHOUT-COUNTS
  RETURN OK
END PROC
```

**Error code:** `O-ILLEGAL-SEQ-WITHOUT-COUNTS` (run-scoped).
Optional soft guard: warn when `bounds` present while `emit_counts=false` → `O-BOUNDS-IGNORED`.

---

## 8.7 Node guards (edge gating in the DAG)

Compute the optional nodes per merchant once, then choose the single packaging point:

```
enable_priors    := emit_priors
enable_counts    := emit_counts
enable_sequence  := emit_sequence AND enable_counts

take_N5 := enable_priors
take_N6 := enable_counts
take_N7 := enable_sequence

// Next node after N4:
next_after_N4 := (take_N5 ? N5 : (take_N6 ? N6 : N8))

// Last kernel actually taken (determines where N8 sits):
last_kernel := (take_N7 ? N7 : (take_N6 ? N6 : (take_N5 ? N5 : N4)))

// Emit sequence is always:
emit_plan := [ N9,
               (take_N5 ? N10 : ∅),
               (take_N6 ? N11 : ∅),
               (take_N7 ? N12 : ∅) ]
```

This guarantees **one** `N8` (after `last_kernel`) and the fixed emit order thereafter.

---

## 8.8 Examples (sanity checks)

* **Priors only:** `emit_priors=1, emit_counts=0, emit_sequence=0`
  Path: `N1→N2→N3→N4→N5→N8→N9→N10`.
* **Counts + Sequence:** `emit_priors=0, emit_counts=1, emit_sequence=1`
  Path: `N1→N2→N3→N4→N6→N7→N8→N9→N11→N12`.
* **All lanes on:** `emit_priors=1, emit_counts=1, emit_sequence=1`
  Path: `N1→N2→N3→N4→N5→N6→N7→N8→N9→N10→N11→N12`.
* **Options-off short-circuit:** toggles all `0`, ranked = `{home}`
  Path: `N1→N2→N3→N4→N8→N9`.

---

## 8.9 Acceptance checklist (for this section)

* Rule `emit_sequence ⇒ emit_counts` is explicit and enforced by `guard_options`.
* Legality matrix present; illegal combos fail **before** scheduling.
* Optional nodes/edges are gated by **derived enables**; a single `N8`; fixed emit order.
* No L2-side renormalisation or policy math; bounds only apply when counts are emitted.
* Options-off short-circuit defined precisely (domestic-only + all lanes disabled).

---

# 9) Publish Protocol (Per Dataset)

## 9.1 Overview (what “publish” means here)

Publishing is the **only side-effect** S3 performs: L2 hands already-packaged rows (from `package_for_emit` in §7.5) to the **L0 emitters** in a fixed order. Each emitter:

* resolves dataset IDs/paths from the **dictionary** (never from L2),
* enforces **embed = path** lineage equality,
* writes via **atomic tmp → fsync → rename**,
* applies **`skip_if_final = true`** for idempotence.

L2 **never** reshapes rows after packaging, never renormalises values, and never writes directly.

---

## 9.2 Pre-publish invariants (must already hold)

Before any emit call:

1. **Rows are frozen & sorted** (done in `package_for_emit`):

   * `candidate_set`: `(merchant_id, candidate_rank, country_iso)`
   * `base_weight_priors`: `(merchant_id, country_iso)`
   * `integerised_counts`: `(merchant_id, country_iso)`
   * `site_sequence`: `(merchant_id, country_iso, site_order)`
2. **Lineage attached** to every row:

   * `row.parameter_hash == run.parameter_hash`
   * `row.manifest_fingerprint == run.manifest_fingerprint`
3. **Single-writer rule (at emit time):** the scheduler will not attempt concurrent writes to the **same** `(dataset_id, parameter_hash)` partition.

---

## 9.3 Emit order (binding)

Per merchant slice, the only legal order is:

```
EMIT_S3_CANDIDATE_SET
→ [EMIT_S3_BASE_WEIGHT_PRIORS]      // if priors enabled
→ [EMIT_S3_INTEGERISED_COUNTS]      // if counts enabled
→ [EMIT_S3_SITE_SEQUENCE]           // if sequence enabled
```

`EMIT_S3_SITE_SEQUENCE` is **reachable only if** counts were emitted in this run (see §8: `emit_sequence ⇒ emit_counts`).

---

## 9.4 Dataset contracts at publish time

### 9.4.1 `s3_candidate_set` (required)

**Call:**
`EMIT_S3_CANDIDATE_SET(rows, parameter_hash, manifest_fingerprint, skip_if_final = true)`

**Row sort:** `(merchant_id, candidate_rank, country_iso)`
**Partition:** `parameter_hash={…}` (no `seed`)
**Authority:** `candidate_rank` is the **only** inter-country order (home=0, contiguous); file order is non-authoritative.
**Uniqueness (per merchant):** exactly one `is_home=true` (rank 0); no duplicate `country_iso` or `candidate_rank`.
**Idempotence/atomicity:** if final exists, deterministic **skip**; otherwise atomic tmp→fsync→rename.

---

### 9.4.2 `s3_base_weight_priors` (optional)

**Call:**
`EMIT_S3_BASE_WEIGHT_PRIORS(rows, parameter_hash, manifest_fingerprint, skip_if_final = true)`

**Row sort:** `(merchant_id, country_iso)`
**Partition:** `parameter_hash={…}`
**Semantics:** values are **fixed-dp scores** (not probabilities). **No renormalisation** at L2 or emitter.
**Uniqueness (per merchant):** one row per `country_iso`.
**Idempotence/atomicity:** as above.

---

### 9.4.3 `s3_integerised_counts` (optional)

**Call:**
`EMIT_S3_INTEGERISED_COUNTS(rows, parameter_hash, manifest_fingerprint, skip_if_final = true)`

**Row sort:** `(merchant_id, country_iso)`
**Partition:** `parameter_hash={…}`
**Semantics:** Σ `count` = **N** (from S2/`ctx.N`); `residual_rank` persisted per row; bounds (if provided) already enforced in L1.
**Uniqueness (per merchant):** one row per `country_iso`.
**Idempotence/atomicity:** as above.

---

### 9.4.4 `s3_site_sequence` (optional; requires counts)

**Call:**
`EMIT_S3_SITE_SEQUENCE(rows, parameter_hash, manifest_fingerprint, skip_if_final = true)`

**Row sort:** `(merchant_id, country_iso, site_order)`
**Partition:** `parameter_hash={…}`
**Semantics:** `site_order` is exactly `1..count_i` per country; optional `site_id` is a zero-padded 6-digit string.
**Authority:** never permutes **inter-country** order; ordering is **within-country** only.
**Uniqueness (per merchant):** unique `(country_iso, site_order)` and, if present, unique `(country_iso, site_id)`.
**Idempotence/atomicity:** as above.

---

## 9.5 Emitter-side checks (performed by L0; L2 relies on them)

* **Embed = path:** verify `row.parameter_hash` equals the partition key; verify `row.manifest_fingerprint` equals the run’s fingerprint. Mismatch ⇒ writer-side error (fail this merchant’s publish).
* **Schema & sorting sanity:** rows match the dataset’s schema anchor; writer sort is respected (L2 supplies sorted rows).
* **Idempotence:** if a final marker already exists for `(dataset, parameter_hash)`, perform a deterministic **skip**.
* **Atomic publish:** no partials visible; either the new part is present, or nothing changed.

> L2 **must not** bypass these checks; it calls only the emitters.

---

## 9.6 Emit pseudocode (language-agnostic; per merchant)

```
PROC emit_slice_in_order(rows_by_dataset, lineage, skip_if_final = TRUE):
  // 1) candidate_set (always)
  EMIT_S3_CANDIDATE_SET(
      rows_by_dataset.candidate_rows,
      lineage.parameter_hash,
      lineage.manifest_fingerprint,
      skip_if_final)

  // 2) priors (optional)
  IF rows_by_dataset.prior_rows != NULL:
      EMIT_S3_BASE_WEIGHT_PRIORS(
          rows_by_dataset.prior_rows,
          lineage.parameter_hash,
          lineage.manifest_fingerprint,
          skip_if_final)

  // 3) counts (optional)
  IF rows_by_dataset.count_rows != NULL:
      EMIT_S3_INTEGERISED_COUNTS(
          rows_by_dataset.count_rows,
          lineage.parameter_hash,
          lineage.manifest_fingerprint,
          skip_if_final)

  // 4) sequence (optional; requires counts)
  IF rows_by_dataset.sequence_rows != NULL:
      EMIT_S3_SITE_SEQUENCE(
          rows_by_dataset.sequence_rows,
          lineage.parameter_hash,
          lineage.manifest_fingerprint,
          skip_if_final)
END PROC
```

---

## 9.7 Failure routing (no healing)

* **Embed≠path** or schema/sort breach at an emitter ⇒ **fail this merchant’s publish immediately**; do not attempt later emits for this merchant.
* **Final exists** with `skip_if_final=true` ⇒ **skip** (not an error).
* **I/O error** during tmp/final rename ⇒ fail merchant; L2 does not backfill or fabricate rows.
* **Illegal lane order** (e.g., attempting sequence without counts) cannot occur if §8 guards are enforced; if observed, fail merchant with a deterministic code and stop.

---

## 9.8 Zero-row behavior (normative)

If a lane is enabled but produces **zero rows** for a merchant, the emitter **must** treat the empty slice as a **no-op publish** (no files written) and return success. Idempotence semantics remain unchanged.

---

## 9.9 Acceptance checklist (for this section)

* Emit order exactly **candidate → \[priors] → \[counts] → \[sequence]**.
* Rows are **pre-sorted** and **lineage-attached** *before* the first emit.
* Each emitter enforces **embed = path**, **atomic publish**, **skip-if-final**.
* Partitions are **parameter-scoped only** (no `seed` in S3 paths).
* No L2 post-packaging reshapes or renormalisation; `candidate_rank` authority preserved.
* **Single-writer rule** respected; failure routing is deterministic; no backfill or “healing”.

---

# 10) Idempotence & Resume Semantics

## 10.1 Definitions (binding)

* **Partition (S3):** a dataset slice addressed by `(dataset_id, parameter_hash)`. S3 never partitions by `seed`.
* **Lineage tuple (run):** `{ parameter_hash, manifest_fingerprint }` fixed for the process lifetime (§2).
* **Final exists (dataset, parameter_hash):** L0 reports that the target partition is already **finalised** for the current dataset. With `skip_if_final=true`, subsequent emits are **no-ops** (no bytes written).
* **Slice (merchant scope):** the rows for one merchant produced by §7.5 `package_for_emit(...)`. L2 may emit many slices to the **same** partition across merchants.
* **Byte-identical re-run:** re-running with the **same lineage** and **same toggles** yields identical rows per merchant; emitters therefore write nothing new (no-ops where finals exist).

> **Finalisation policy is L0-managed.** L2 does not assume **when** a partition becomes final (e.g., after a prior complete run or via an L0 marker). During a fresh run, “final” is typically absent and emitters accept slices; on resume, some partitions may be final already.

---

## 10.2 Idempotence rules (must always hold)

1. **Emitters enforce idempotence.** Every `EMIT_S3_*` call uses `skip_if_final=true`. If the partition is final, the emitter performs a **deterministic skip**.
2. **No mutation after packaging.** Rows are frozen in `package_for_emit(...)`; L2 does not reshape, re-sort, or renormalise post-packaging.
3. **Embed = path.** At publish, `row.parameter_hash` must equal the partition key; `row.manifest_fingerprint` must equal the run’s fingerprint.
4. **Exactly-once effect per slice.** Re-calling an emitter with the same slice and same lineage either:

   * writes bytes exactly once (first time), or
   * performs a no-op (subsequent times). **No duplicates** are ever created.

---

## 10.3 Resume scenarios (deterministic outcomes)

| Scenario | What changed                                                                       | Behavior (binding)                                                                                                                                                         |
|----------|------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **R1**   | Crash **before** any emit                                                          | Re-run: all merchants flow through kernels; emitters write normally (no finals exist).                                                                                     |
| **R2**   | Crash **after** some emits for some merchants                                      | Re-run: non-final partitions continue to accept slices; already-final partitions are **skipped** by emitters.                                                              |
| **R3**   | Re-run with **same** `{parameter_hash, manifest_fingerprint}` and **same toggles** | Fully idempotent: kernels may recompute; emitters no-op where finals exist; any remaining merchants publish exactly once.                                                  |
| **R4**   | Re-run with **same** `parameter_hash` but **different manifest_fingerprint**      | **Illegal resume.** Abort with `IDEMP-MANIFEST-MISMATCH`. Changing the manifest under the same partition risks mixed manifests embedded in rows.                           |
| **R5**   | Re-run with **same** lineage but **different toggles**                             | **Illegal resume if any dataset for this partition is final.** Abort with `IDEMP-TOGGLE-MISMATCH`. Change toggles only on a clean partition or use a new `parameter_hash`. |
| **R6**   | Re-run with **new** `parameter_hash`                                               | Treated as a **new target**; all emits proceed; old partitions remain immutable.                                                                                           |

**Normative guard:** L2 must verify **R4/R5** up front (see §10.6) and fail fast **before** scheduling.

---

## 10.4 Emitter semantics required for idempotence (L0 responsibilities)

* **Skip-if-final:** With `skip_if_final=true` and `(dataset, parameter_hash)` final, emitter returns success without writing.
* **Duplicate-slice safety:** If a slice is re-submitted to a **non-final** partition (e.g., mid-run retry), emitter must either
  (a) deduplicate by the dataset’s uniqueness keys (e.g., `candidate_set`: `(merchant_id,country_iso)` & `(merchant_id,candidate_rank)`), **or**
  (b) detect identical payload and no-op.
* **Atomic commit:** tmp → fsync → rename; no partials visible on crash.
* **Partition immutability:** Once final, emitters must not append or rewrite.

> L2 never bypasses emitters and does not mark partitions final; both are L0 concerns.

---

## 10.5 Ordering & determinism under resume

* **Within-merchant order** (N1…N12) remains serial regardless of resume.
* **Emit order per merchant** is fixed: `candidate_set → [priors] → [counts] → [sequence]`.
* **Merchant dispatch order** is deterministic (e.g., ascending `merchant_id`); worker completion order cannot affect dataset order because **writer sorts** (§7.5, §9) define the on-disk logical order.

---

## 10.6 Resume guards (must run before scheduling)

```
PROC guard_resume(run_cfg, observed_partition_state):
  // 1) If any dataset partition is already final for this parameter_hash,
  //    its metadata must match the current run.
  IF observed_partition_state.has_any_final_for(run_cfg.parameter_hash):
      IF observed_partition_state.manifest_fingerprint != run_cfg.manifest_fingerprint:
          RAISE ERROR IDEMP-MANIFEST-MISMATCH
      IF observed_partition_state.toggles_snapshot != run_cfg.toggles:
          RAISE ERROR IDEMP-TOGGLE-MISMATCH

  // 2) Consistency across datasets: all finals (if any) must agree.
  IF observed_partition_state.has_mixed_final_metadata_for(run_cfg.parameter_hash):
      RAISE ERROR IDEMP-INCONSISTENT-FINALS

  RETURN OK
END PROC
```

**Notes.**

* `observed_partition_state` is a **host/L0 read-only** summariser (e.g., a small sidecar or controller view) and may return:
  `has_any_final_for(parameter_hash): bool`,
  `manifest_fingerprint: Hex64 (if final exists)`,
  `toggles_snapshot: {emit_priors, emit_counts, emit_sequence} (if final exists)`,
  `has_mixed_final_metadata_for(parameter_hash): bool`.
* If no finals exist, the guard passes vacuously.

---

## 10.7 Merchant-level retry safety

* **Kernel failure (N1–N7):** mark merchant failed; no emits called. Re-run later with same lineage: kernels recompute; emits write once.
* **Emit-time transient (e.g., I/O error on rename):** treat merchant as failed; resume recomputes kernels and re-attempts emits. Atomic publish ensures **no duplicates**.

---

## 10.8 Interaction with the options matrix (§8)

* `emit_sequence ⇒ emit_counts` remains enforced on resume.
* Changing toggles between runs that target the **same** `parameter_hash` is **forbidden** once any dataset is final (R5). Use a new `parameter_hash` if you must change options.

---

## 10.9 Pseudocode: idempotent re-run (host-neutral)

```
PROC run_S3_L2(run_cfg):
  // Open BOM, verify options’ legality
  bom := HOST_OPEN_BOM()
  guard_options(bom.toggles)

  // Observe partition state and guard resume
  part_state := OBSERVE_PARTITION_STATE(parameter_hash = run_cfg.parameter_hash)   // Host/L0 read-only
  guard_resume(run_cfg, part_state)

  // Launch deterministic worker pool and process merchants (see §6)
  ...
END PROC
```

---

## 10.10 Acceptance checklist (for this section)

* Guards for **manifest** and **toggle** mismatches exist and fire **before** scheduling.
* `skip_if_final=true` mandated for all emits; **final exists ⇒ no-op**.
* Exactly-once semantics defined for repeated slice submissions.
* No mutation after packaging; **embed=path** reaffirmed at publish.
* Resume is safe for **R1–R3**; **R4–R5** are **forbidden** with explicit error codes; inconsistent finals detected (`IDEMP-INCONSISTENT-FINALS`).
* Atomic commits guaranteed; no partials, no backfill.

---

# 11) Determinism & Ordering Guarantees

## 11.1 Definition (binding)

For a fixed **lineage tuple** `{parameter_hash, manifest_fingerprint}`, fixed **BOM** (ladder, ISO set, dp constants, bounds) and fixed **options** (`emit_*`), an S3·L2 run **must produce byte-identical outputs** on every execution—independent of host scheduling, thread interleavings, or worker count.

**Implications**

* **Zero stochasticity:** **no RNG** anywhere in S3·L2.
* **No time-of-run fields:** **no timestamps** are written to any S3 dataset rows.
* Writer behavior (atomic publish, idempotence) prevents partials/duplication and does **not** change bytes for a given slice.

---

## 11.2 Sources of nondeterminism (and how we eliminate them)

1. **Iteration/dispatch order**
   *Risk:* host maps/sets and thread pools can scramble work ordering.
   *Rule:* L2 defines a **deterministic merchant iteration order** (e.g., ascending `merchant_id`) and enqueues in that order (§6.4). Worker completion order is irrelevant because rows are **pre-sorted at packaging** (§7.5) and emits follow a fixed sequence (§9.3).

2. **Concurrent writes to the same partition**
   *Risk:* racy interleaving could cause non-reproducible layouts or failed renames.
   *Rule:* **Single-writer rule** per `(dataset_id, parameter_hash)`; serialize emits targeting the same partition (§6.7). Emit order is fixed (§9.3).

3. **Locale/Collation**
   *Risk:* locale-dependent string comparison may reorder rows.
   *Rule:* All writer sorts use explicit **structural keys** and numeric rank. Treat string keys as **bytewise/ASCII**; never rely on host locale.

4. **Floating-point drift**
   *Risk:* libm/flags differences could alter priors/counts.
   *Rule:* L2 **does not compute numeric policy**. All math is in L1 (already pinned). L2 preserves arrays and sorts by structural keys only (§7.5).

5. **Path discovery & filesystem state**
   *Risk:* ad-hoc concatenation or time-based temp names introduces variability.
   *Rule:* L2 never constructs paths; L0 emitters resolve dictionary paths and use **atomic tmp → fsync → rename**. No time-based naming.

6. **Resume variability**
   *Risk:* toggles or manifest changes between runs could mix bytes.
   *Rule:* §10 guards enforce **manifest/toggle equality** for resumes; otherwise abort deterministically.

---

## 11.3 Global ordering guarantees

* **Inter-country ordering authority:** `candidate_rank` is the **only** inter-country order for S3. It is established by ranking (N4), is **contiguous** with `home=0`, and **must not be mutated** by L2 or optional lanes. File order is non-authoritative.
* **Within-country ordering:** if the sequence lane is enabled, `site_order` is **exactly `1..nᵢ`** per country; sequencing never permutes country blocks.
* **Dataset writer sorts (logical row order at write):**

  * `s3_candidate_set`: `(merchant_id, candidate_rank, country_iso)`
  * `s3_base_weight_priors`: `(merchant_id, country_iso)`
  * `s3_integerised_counts`: `(merchant_id, country_iso)`
  * `s3_site_sequence`: `(merchant_id, country_iso, site_order)`
* **Emit order (dataset level):** per merchant slice, always
  `candidate_set → [priors] → [counts] → [sequence]`.

---

## 11.4 Packaging invariants (the determinism hinge)

There is exactly **one** packaging point (N8) per merchant:

* **Attach lineage exactly once:** `{parameter_hash, manifest_fingerprint}`.
* **Apply writer sorts exactly once** per dataset.
* **Freeze rows post-N8:** L2 must not mutate, re-sort, or renormalise after packaging.
* **Emitters** verify **embed = path** and perform idempotent, atomic publish.

These invariants render worker scheduling irrelevant to bytes on disk.

---

## 11.5 Merchant-level execution guarantees

* **Serial within merchant:** Always execute
  `N1 → N2 → N3 → N4 → [N5?] → [N6?] → [N7?] → N8 → N9 → [N10?] → [N11?] → [N12?]` with no interleaving.
* **Short-circuit determinism:** If the ranked set is **home-only** *and* all optional lanes are **disabled**, take `N4 → N8 → N9`—the only legal short-circuit (§8.5).
* **Option gating is deterministic:** `emit_sequence ⇒ emit_counts` is enforced before scheduling (§8); optional nodes are taken solely from toggles, not from timing.

---

## 11.6 Partitioning & lineage guarantees

* **Parameter-scoped only:** all S3 datasets partition by `parameter_hash` (no `seed`).
* **Embed = path:** emitters reject any row whose embedded `parameter_hash` does not equal the partition key; `manifest_fingerprint` embedded equals the run’s fingerprint.
* **Immutability of finals:** once a partition is final, subsequent emits with `skip_if_final=true` are **no-ops**; L2 never appends or rewrites.

---

## 11.7 What L2 must never do (to preserve determinism)

* Recompute or renormalise priors, counts, or sequence.
* Re-sort inter-country order or inject new tie-breakers.
* Construct filesystem paths or rely on timestamps/clock.
* Emit outside the mandated dataset order.
* Write concurrently to the same `(dataset_id, parameter_hash)` partition.
* Change toggles or manifest mid-run.

---

## 11.8 Determinism self-checks (developer hygiene)

Before freezing L2, verify:

* Running the same slice twice (same lineage/toggles) produces a **bit-for-bit identical** packaged buffer.
* Varying worker counts (`N_WORKERS=1` vs `N_WORKERS=8`) yields **byte-identical** output partitions.
* Re-running after partial completion writes **no new bytes** to finalized partitions (emitters report skips).
* Host locale changes do not affect sort results (keys are structural, not locale-aware).

---

## 11.9 Acceptance checklist (for this section)

* Determinism definition satisfied: no RNG, no timestamps, byte-identical for fixed lineage/toggles.
* All nondeterminism vectors identified with concrete mitigations (dispatch, concurrency, locale, paths, resumes).
* Ordering guarantees binding: `candidate_rank` authority; within-country `site_order`; writer sorts; fixed emit order.
* Packaging invariants present and mandatory; single N8 per merchant.
* “Must never do” list anchors guardrails for implementers.

---

# 12) Partitioning & Lineage Discipline

## 12.1 Scope (binding)

* **Partition key (S3):** `parameter_hash` **only**. S3 never partitions by `seed`, `run_id`, date, or any mutable dimension.
* **Lineage tuple (embedded in rows):** `{ parameter_hash: Hex64, manifest_fingerprint: Hex64 }`. These fields **must** appear in **every** emitted row of every S3 dataset.
* **Authority split:** L2 **attaches lineage once** at **N8 `package_for_emit`**; L0 emitters **verify** lineage at publish. L2 never mutates lineage post-packaging.

---

## 12.2 Partition addressing & immutability

* **Address form:** `(dataset_id, parameter_hash)`. The **dictionary** resolves concrete paths; L2 never constructs paths.
* **Finality:** once a `(dataset_id, parameter_hash)` is **final**, it is immutable; re-runs with `skip_if_final=true` are **no-ops** (§10).
* **Single-writer rule:** at most one writer may target the same `(dataset_id, parameter_hash)` at a time (§6.7).

---

## 12.3 Embedded lineage rules (per row)

For each S3 dataset (`candidate_set`, optional `base_weight_priors`, `integerised_counts`, `site_sequence`):

1. **Presence:** every row embeds both `parameter_hash` and `manifest_fingerprint`.
2. **Equality (publish-time checks):**

   * `row.parameter_hash == target_partition.parameter_hash`
   * `row.manifest_fingerprint == run.manifest_fingerprint`
3. **Cross-dataset consistency (run-scoped):** within a run, all S3 datasets **embed the same** lineage tuple.
4. **No transformation:** lineage strings are exact bytes; **no** case folding, trimming, or re-encoding.

---

## 12.4 Packaging-time discipline (N8, pure)

L2 attaches lineage and applies writer sorts **exactly once**.

```
PROC package_for_emit(bundle, lineage):
  REQUIRE lineage.parameter_hash != NULL
  REQUIRE lineage.manifest_fingerprint != NULL

  cand  := ATTACH_LINEAGE_AND_SORT(bundle.ranked,      lineage,
                                   sort=(merchant_id, candidate_rank, country_iso))
  prior := (bundle.priors_opt   ? ATTACH_LINEAGE_AND_SORT(bundle.priors_opt,   lineage,
                                   sort=(merchant_id, country_iso)) : NULL)
  cnt   := (bundle.counts_opt   ? ATTACH_LINEAGE_AND_SORT(bundle.counts_opt,   lineage,
                                   sort=(merchant_id, country_iso)) : NULL)
  seq   := (bundle.sequence_opt ? ATTACH_LINEAGE_AND_SORT(bundle.sequence_opt, lineage,
                                   sort=(merchant_id, country_iso, site_order)) : NULL)

  // Pure self-checks (defensive; no I/O):
  ASSERT_ALL_ROWS(lineage.parameter_hash,      IN [cand, prior?, cnt?, seq?])
  ASSERT_ALL_ROWS(lineage.manifest_fingerprint,IN [cand, prior?, cnt?, seq?])

  RETURN { candidate=cand, priors_opt=prior, counts_opt=cnt, sequence_opt=seq }
END PROC
```

**Post-N8 invariant:** rows are **frozen**; L2 must not reshape, re-sort, or reattach lineage.

---

## 12.5 Publish-time lineage & partition checks (L0)

Each emitter **must** enforce:

* **Embed = path:** reject if `row.parameter_hash` ≠ partition key.
* **Manifest equality:** reject if `row.manifest_fingerprint` ≠ run fingerprint.
* **Schema & writer-sort sanity:** rows match schema; sort keys match §3.3.
* **Atomicity & idempotence:** tmp → fsync → rename; `skip_if_final=true` yields a deterministic **skip**.
  L2 never bypasses emitters.

---

## 12.6 Resume & toggle guards (interaction with §10)

* If **any** S3 dataset for `parameter_hash = H` is already final, a resume targeting `H` **must** embed the same `manifest_fingerprint`; otherwise fail `IDEMP-MANIFEST-MISMATCH`.
* If options differ from the recorded snapshot for `H`, fail `IDEMP-TOGGLE-MISMATCH`.
* Changing parameters or toggles ⇒ use a **new** `parameter_hash`.

---

## 12.7 Forbidden behavior

* Emitting rows whose `row.parameter_hash` ≠ partition key.
* Mixing different `manifest_fingerprint` values across datasets within the same `parameter_hash`.
* Introducing additional partition dimensions (e.g., `seed`, date shards).
* Attaching/mutating lineage **after** `package_for_emit`.
* Publishing any row without both lineage fields present.

---

## 12.8 Developer hygiene (self-checks)

Before freezing:

* **Round-trip:** run with `N_WORKERS=1` and `N_WORKERS>1` → lineage bytes identical and match the run.
* **Resume:** run, crash post-some-emits, re-run → finals are skipped; no mixed manifests.
* **Cross-dataset:** for a given merchant slice, lineage tuples in `candidate_set`, `priors` (if any), `counts` (if any), `sequence` (if any) are **identical**.

---

## 12.9 Acceptance checklist (for this section)

* Partition scope enforced: **parameter-scoped only**.
* Lineage tuple defined; attached once at packaging; verified at publish.
* Cross-dataset lineage equality mandated.
* Emitters’ **embed=path** and **manifest** checks are binding; no bypass.
* Forbidden behaviors enumerated; resume/toggle guards align with §10.
* Packaging pseudocode present; rows frozen post-N8.

---

# 13) Host Interfaces Used (Read-Only Shims)

## 13.1 Intent (binding)

Define the **minimal, host-facing surfaces** L2 may call to obtain values/handles and to schedule work. These shims:

* return **values**, not paths;
* are **deterministic** for a fixed run lineage and options;
* have **no side-effects** beyond opening read-only handles or allocating workers.

L2 calls **only** these shims (plus L0 emitters and L1 kernels). No other host APIs are permitted.

---

## 13.2 Design principles

* **Read-only:** shims never modify datasets or create files.
* **Path-agnostic:** they never return filesystem paths; L0 emitters resolve paths from the dictionary.
* **Deterministic:** for fixed `{parameter_hash, manifest_fingerprint, toggles}`, outputs are stable for the run lifetime.
* **Thread-safe:** multiple workers may invoke shims; results must be safe to share or copy.

---

## 13.3 Shim registry (signatures, purpose, contracts)

### 13.3.1 Run materials / policy

```
PROC HOST_OPEN_BOM()
  -> { ladder: Ladder,
       iso_universe: Set[ISO2],
       dp: int,
       dp_resid: int,
       bounds?: BoundsConfig,
       toggles: { emit_priors: bool, emit_counts: bool, emit_sequence: bool },
       vocab: Vocab,                         // ingress/channel/etc. vocab used by L1
       admission_meta_map: Map[ISO2,{precedence:int,priority:int,rule_id:str}],
       site_id_cfg?: SiteIdConfig }          // optional sequencing config
```

**Purpose.** Open all **policy values** needed by S3; read-only for the run.
**Determinism.** Values are stable for the run lifetime.
**Failure.** Any missing required component ⇒ run-scoped error; L2 must not start scheduling.

---

### 13.3.2 Merchant domain & iteration

```
PROC HOST_MERCHANT_LIST(parameter_hash: Hex64)
  -> List[merchant_id]    // deterministic order (e.g., ascending merchant_id)
```

**Purpose.** Provide the exact merchant worklist for this run/partition in **stable order**.
**Determinism.** List and order must be invariant for the run.
**Failure.** Empty list allowed (L2 exits cleanly). Non-deterministic order is forbidden.

---

### 13.3.3 Ingress & prior-state facts (read-only views)

```
PROC HOST_GET_INGRESS(merchant_id)
  -> IngressRecord       // minimal fields required by s3_build_ctx

PROC HOST_GET_S1S2_FACTS(merchant_id)
  -> { is_multi: bool,
       N: int,          // accepted NB count (≥2) for multi merchants
       r: int }         // NB rejections (≥0)
```

**Purpose.** Supply the **exact facts** S3·L1 expects for kernels; no RNG log reads.
**Determinism.** Facts reflect the controller’s authoritative state for this run.
**Failure.** Missing facts ⇒ merchant-scoped failure; L2 skips emits for that merchant.

---

### 13.3.4 Worker pool

```
PROC HOST_WORKER_POOL(N_WORKERS: int)
  -> Pool
```

**Purpose.** Execute **across-merchant** tasks concurrently; **within-merchant** stays serial.
**Determinism.** Pool scheduling does not affect bytes because rows are pre-sorted at package time and emits are ordered.

---

### 13.3.5 Dictionary handle (for L0 internals)

```
PROC HOST_DICTIONARY_HANDLE()
  -> DictHandle
```

**Purpose.** Provide a stable handle to the dataset dictionary for L0 emitters.
**Note.** L2 does **not** call dictionary methods directly; it passes the handle to L0 if the emitter binding requires it.

---

### 13.3.6 Partition state (for resume guards)

```
PROC OBSERVE_PARTITION_STATE(parameter_hash: Hex64)
  -> { has_any_final: bool,
       manifest_fingerprint?: Hex64,
       toggles_snapshot?: { emit_priors: bool, emit_counts: bool, emit_sequence: bool },
       has_mixed_final_metadata?: bool }   // finals disagree across datasets for this partition
```

**Purpose.** Allow §10 guards to enforce **manifest/toggle equality** before resuming and detect mixed finals.
**Determinism.** Reflects on-disk truth.
**Failure.** If unreadable, treat as “no finals”; L2 may proceed, and operators should investigate.

---

### 13.3.7 Optional operational logging (non-evidence)

```
PROC HOST_LOG(level: {"INFO","WARN","ERROR"}, message: string, kv?: Map)
  -> void
```

**Purpose.** Human-readable progress only (merchants processed, datasets published/skipped).
**Determinism.** Messages must not influence logic; timestamps (if any) are non-deterministic and **must not** be consumed by L2.

---

## 13.4 Usage map (where each shim is called)

| Shim                      | Used in § / Node         | Purpose                                                                                                                                         |
|---------------------------|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `HOST_OPEN_BOM`           | §6 run entry; §7.3 N1/N4 | Acquire run policy/materials (`vocab`, `ladder`, `iso_universe`, `dp`, `dp_resid`, `bounds?`, `toggles`, `admission_meta_map`, `site_id_cfg?`). |
| `HOST_MERCHANT_LIST`      | §6.4                     | Deterministic worklist for dispatch.                                                                                                            |
| `HOST_GET_INGRESS`        | §7.3 N1                  | Supply ingress to `s3_build_ctx`.                                                                                                               |
| `HOST_GET_S1S2_FACTS`     | §7.3 N1                  | Supply S1/S2 facts to `s3_build_ctx`.                                                                                                           |
| `HOST_WORKER_POOL`        | §6.3                     | Across-merchant parallelism.                                                                                                                    |
| `HOST_DICTIONARY_HANDLE`  | §9 (via L0 emitters)     | Dictionary resolution inside emitters.                                                                                                          |
| `OBSERVE_PARTITION_STATE` | §10.6                    | Enforce idempotent resume guards.                                                                                                               |
| `HOST_LOG`                | §16                      | Operational progress output.                                                                                                                    |

---

## 13.5 Determinism & safety requirements

* **No paths, ever:** these shims never emit filesystem paths for S3 datasets.
* **Value stability:** returned values must not change mid-run; cache in memory after first call.
* **Thread safety:** concurrent reads must be safe; either immutable snapshots or per-call copies.
* **Error transparency:** failures return explicit, stable codes; L2 routes them (no hidden retries).

---

## 13.6 Forbidden behavior

* Computing policy math or altering arrays destined for emit.
* Writing files, creating directories, or mutating dataset contents.
* Returning non-deterministic iterables (e.g., hash-map iteration without ordering).
* Exposing host locale or time to L2 logic.

---

## 13.7 Acceptance checklist (for this section)

* All shims are **read-only**, **deterministic**, and **path-agnostic**.
* Signatures are explicit; inputs/outputs typed; failure modes stated.
* Mapping from shims → DAG nodes/sections is complete.
* No overlap with L0 emitters or L1 kernels; no redundant definitions.
* BOM includes `vocab`, `admission_meta_map`, and (optional) `site_id_cfg?`; resume probe exposes `has_mixed_final_metadata`.

---

# 14) Resource & Throughput Knobs (Practical)

## 14.1 Goals (what we’re optimizing for)

* **Deterministic speed-ups** on a single machine (multi-core) with byte-identical outputs for fixed lineage/options.
* **Zero surprises:** every knob has a safe default, a bounded range, and a single, clear effect.
* **No policy drift:** knobs never change math, order authority, or schema—only *throughput* and *resource usage*.

---

## 14.2 Knob inventory (definitions, defaults, safe ranges)

| Knob                | Type  | Default                     | Safe Range        | Effect (plain language)                                                                                         |
|---------------------|-------|-----------------------------|-------------------|-----------------------------------------------------------------------------------------------------------------|
| `N_WORKERS`         | int   | `min(physical_cores, 8)`    | `1 … 32`          | Parallelism **across merchants**. Within a merchant is always serial (§6).                                      |
| `batch_rows`        | int   | `20_000`                    | `5_000 … 100_000` | Chunk size when emitters support streamed writes; amortises writer overhead, esp. for `site_sequence`.          |
| `mem_watermark`     | bytes | `256–512 MB` **per worker** | host-dependent    | Upper bound for *resident arrays per worker* (ranked/priors/counts/sequence). Controls memory pressure.         |
| `queue_capacity`    | int   | `2 × N_WORKERS`             | `N_WORKERS … 8×`  | Bounded in-flight merchant tasks; provides backpressure **without reordering** (§6.4).                          |
| `emit_backpressure` | bool  | `true`                      | `true/false`      | When `true`, serialize emits so only **one** writer targets a given `(dataset, parameter_hash)` at once (§6.7). |
| `flush_hint`        | bool  | `true`                      | `true/false`      | If emitters expose a flush API, request fsync before atomic rename (stronger resumes; no byte changes).         |

> **Determinism:** changing knobs **must not** change bytes—only throughput and resource use.

---

## 14.3 What dominates runtime in S3·L2

* **Packaging & sorting** small arrays (`candidate_set`, `priors`, `counts`)—CPU-light.
* **`site_sequence` emits** when enabled—can be large (rows scale with `N`).
* **Atomic publish cost** (tmp→fsync→rename)—amortised by `batch_rows` when streaming is available.

---

## 14.4 Sizing memory safely (per worker)

Let `C = #countries after ranking`, `N = total outlets (from S2)`.

Upper-bound intuition for resident bytes per worker:

```
bytes_worker  ≈  rows(ranked)*row_bytes_r
              +  rows(priors?)*row_bytes_p
              +  rows(counts?)*row_bytes_c
              +  rows(sequence?)*row_bytes_s
```

with `rows(ranked)≈C`, `rows(priors)≈C`, `rows(counts)≈C`, `rows(sequence)≈N`.

**Heuristic:** choose `mem_watermark` so `max_expected(bytes_worker) ≤ mem_watermark`, and ensure
`N_WORKERS × mem_watermark` fits RAM with headroom for runtime/OS.
If `sequence` is enabled and `N` can be large, prefer:

* higher `batch_rows` (if streaming) to reduce per-emit overhead, and/or
* lower `N_WORKERS` to cap concurrent peaks.

---

## 14.5 Choosing `N_WORKERS` (CPU vs I/O bound)

* **I/O-bound (typical when `sequence` on):** start `N_WORKERS = min(cores, 8)`. If high iowait, **reduce** `N_WORKERS` or **increase** `batch_rows`.
* **Very small slices (no `sequence`):** you can raise `N_WORKERS` (e.g., up to 16–24 on big machines) so long as memory remains below watermark.

*Determinism note:* varying `N_WORKERS` does not change bytes; rows are **frozen/sorted at packaging** (§7.5) and emits are fixed-order (§9.3).

---

## 14.6 Emission strategy (enforcing single-writer without throttling the pool)

* Keep **packaging** fully parallel across workers.
* Gate emits with **`emit_backpressure = true`**:

  * Use a **per-(dataset, parameter_hash) mutex** or a single “writer lane” that dequeues emits FIFO.
  * This preserves the **single-writer rule** while workers continue computing next merchants.
* If emitters already lock internally, keep `emit_backpressure=true` to minimise retries/spin and make scheduling deterministic.

---

## 14.7 Chunked vs monolithic emits

* If L0 emitters **support streaming/chunked writes**, set `batch_rows` and stream large slices (notably `site_sequence`) **in writer-sort order**. The emitter must still produce one **single final artefact** via atomic rename.
* If emitters are **monolithic**, ignore `batch_rows` and emit each merchant slice in one call.

**Never** violate logical order: chunking must preserve the dataset’s writer sort
`(merchant_id, candidate_rank, country_iso)` / `(merchant_id, country_iso)` / `(merchant_id, country_iso, site_order)`—and **must not interleave merchants** within a partition.

---

## 14.8 Practical presets (single machine)

**Laptop (4–8 cores, 16–32 GB RAM)**

* `N_WORKERS = 4–6`
* `batch_rows = 20_000`
* `emit_backpressure = true`
* `mem_watermark = 256 MB/worker`

**Workstation (8–32 cores, 64–256 GB RAM)**

* `N_WORKERS = min(cores, 12)`
* `batch_rows = 50_000` (if streaming)
* `emit_backpressure = true`
* `mem_watermark = 512 MB/worker`

**Sequence-heavy runs (large `N`)**

* Reduce `N_WORKERS` by 25–50% **or** raise `mem_watermark`.
* Prefer `batch_rows ≥ 50_000` if streaming is available.

---

## 14.9 Observability to guide tuning (non-intrusive)

Expose these counters via §16 logging (do **not** influence logic):

* `merchants_processed_total`
* `emit_skips_total` (idempotence) **per dataset**
* `rows_emitted_total` **per dataset**
* `chunk_writes_total` **per dataset** (if streaming)
* `max_bytes_in_worker` (peak resident per worker)
* `avg_emit_ms` **per dataset**

**Interpretation:**

* High `emit_skips_total` on resume = healthy idempotence.
* Large `avg_emit_ms` with low CPU ⇒ I/O bound ⇒ increase `batch_rows` or lower `N_WORKERS`.
* `max_bytes_in_worker` near `mem_watermark` ⇒ reduce `N_WORKERS` or trim `batch_rows`.

---

## 14.10 Guardrails (what knobs must *not* do)

* Must **not** change: `candidate_rank`, writer sorts, schema, partitions, lineage fields, or dataset emit order.
* Must **not** introduce timestamps or any RNG.
* Must **not** allow concurrent writers to the same `(dataset_id, parameter_hash)` partition.

---

## 14.11 Acceptance checklist (for this section)

* Every knob has a **default**, a **safe range**, and a **clear effect**.
* Guidance covers memory sizing, CPU/I-O balance, and sequence-heavy cases.
* Single-writer enforcement strategy is stated; streaming preserves writer order.
* Observability counters listed for deterministic tuning.
* No knob alters policy, schema, partitions, lineage, or order authority.

---

# 15) Error Taxonomy (Deterministic, Minimal)

## 15.1 Principles

* **Deterministic:** same inputs/lineage ⇒ same errors at the same nodes.
* **Minimal:** only what’s needed to keep wiring correct and bytes safe.
* **Scoped:** every error is **RUN**, **MERCHANT**, or **DATASET/PARTITION** scoped.
* **No healing/backfill:** L2 never fabricates rows or “fixes” data; it routes/aborts.
* **Stable codes:** `UPPER_SNAKE` identifiers; payload carries context.

---

## 15.2 Code catalog (by scope)

### A) Run-scoped (abort before or without scheduling merchants)

| Code                           | Trigger (Where)                                                   | Required Action                   | Retryability                                     |
|--------------------------------|-------------------------------------------------------------------|-----------------------------------|--------------------------------------------------|
| `HOST-BOM-MISSING`             | Missing ladder/ISO/dp/dp_resid/bounds/toggles (N0)               | Abort run; report missing keys    | yes (after host fix)                             |
| `HOST-POOL-FAILURE`            | Worker pool cannot be created (§6.3)                              | Abort run                         | yes                                              |
| `HOST-DICT-HANDLE-FAIL`        | Dictionary handle unavailable (§13.3.5)                           | Abort run                         | yes                                              |
| `O-ILLEGAL-SEQ-WITHOUT-COUNTS` | Toggles violate §8 rule (pre-dispatch)                            | Abort run; do not queue merchants | yes (fix toggles)                                |
| `IDEMP-MANIFEST-MISMATCH`      | Finals exist but manifest differs for this `parameter_hash` (§10) | Abort run                         | yes (align manifest or use new `parameter_hash`) |
| `IDEMP-TOGGLE-MISMATCH`        | Finals exist but toggles differ for this `parameter_hash` (§10)   | Abort run                         | yes (align toggles or new `parameter_hash`)      |
| `IDEMP-INCONSISTENT-FINALS`    | Finals for this `parameter_hash` disagree across datasets (§10)   | Abort run                         | yes (operator reconciliation required)           |

### B) Merchant-scoped (stop this merchant; others continue)

| Code                        | Trigger (Where)                                       | Required Action            | Retryability                                 |
|-----------------------------|-------------------------------------------------------|----------------------------|----------------------------------------------|
| `KERNEL-INGRESS-MISSING`    | `HOST_GET_INGRESS` lacks required fields (N1)         | Fail merchant; skip N8–N12 | yes                                          |
| `KERNEL-S1S2-MISSING`       | `HOST_GET_S1S2_FACTS` lacks `is_multi`/`N`/`r` (N1)   | Fail merchant              | yes                                          |
| `KERNEL-LADDER-FAIL`        | Ladder evaluation cannot produce a decision (N2)      | Fail merchant              | yes                                          |
| `KERNEL-CANDIDATE-NO-HOME`  | Candidate set lacks exactly one home ISO (N3 assert)  | Fail merchant              | yes (data/policy fix)                        |
| `KERNEL-CANDIDATE-DUP-ISO`  | Duplicate ISO in candidate set (N3 assert)            | Fail merchant              | yes                                          |
| `KERNEL-RANK-NONCONTIG`     | Rank not contiguous or home≠0 (N4 assert)             | Fail merchant              | yes                                          |
| `KERNEL-PRIORS-FAIL`        | Priors kernel fails (N5)                              | Fail merchant              | yes                                          |
| `KERNEL-COUNTS-INFEASIBLE`  | Integerisation infeasible (bounds, Σ≠N) (N6)          | Fail merchant              | yes (policy/bounds fix)                      |
| `KERNEL-SEQUENCE-NO-COUNTS` | Sequence invoked without counts (guard breach) (N7)   | Fail merchant              | yes (fix options; should be prevented by §8) |
| `PACKAGE-LINEAGE-MISSING`   | `parameter_hash`/`manifest_fingerprint` missing (N8)  | Fail merchant; do not emit | yes (fix run ctx)                            |
| `PACKAGE-SORT-BREACH`       | Writer-sort cannot be applied (bad/missing keys) (N8) | Fail merchant              | yes                                          |

### C) Dataset/Partition-scoped (publish-time; per dataset)

| Code                       | Trigger (Where)                                         | Required Action                               | Retryability                 |
|----------------------------|---------------------------------------------------------|-----------------------------------------------|------------------------------|
| `EMIT-FINAL-EXISTS`        | Partition already final & `skip_if_final=true` (N9–N12) | **Skip** (informational; not an error)        | n/a                          |
| `EMIT-EMBED-PATH-MISMATCH` | `row.parameter_hash` ≠ partition key (N9–N12)           | Fail merchant’s publish; stop remaining emits | yes (fix lineage)            |
| `EMIT-MANIFEST-MISMATCH`   | `row.manifest_fingerprint` ≠ run fingerprint (N9–N12)   | Fail merchant’s publish                       | yes                          |
| `EMIT-SCHEMA-MISMATCH`     | Rows violate dataset schema (N9–N12)                    | Fail merchant’s publish                       | yes                          |
| `EMIT-ATOMIC-FAILED`       | tmp/fsync/rename failed (N9–N12)                        | Fail merchant’s publish                       | yes (transient I/O)          |
| `EMIT-ILLEGAL-ORDER`       | Attempt to emit sequence without counts (N12)           | Fail merchant’s publish                       | yes (fix options; §8 guards) |

> **Zero-row behavior:** calling an emitter with an **empty slice** is a **no-op success** (informational), not an error (see §9.8).

---

## 15.3 Error payload (what every record must include)

```
{
  code: <STABLE_CODE>,
  node: <N0..N12>,
  scope: <RUN | MERCHANT | DATASET>,
  parameter_hash: <Hex64>,
  manifest_fingerprint: <Hex64>,
  dataset_id?: <s3_candidate_set | s3_base_weight_priors | s3_integerised_counts | s3_site_sequence>,
  merchant_id?: <id>,
  toggles_snapshot: { emit_priors: bool, emit_counts: bool, emit_sequence: bool },
  message: <short human summary>,
  details?: <structured kvs: missing_keys, iso, bound_name, expected, observed, ...>
}
```

**Scope semantics:**

* `RUN`: abort immediately; do not open the worker pool.
* `MERCHANT`: stop N8–N12 for this merchant; others continue.
* `DATASET`: stop remaining emits for this merchant; others continue.

---

## 15.4 Where each code can occur (DAG map)

* **N0**: `HOST-BOM-MISSING`
* **N1**: `KERNEL-INGRESS-MISSING`, `KERNEL-S1S2-MISSING`
* **N2**: `KERNEL-LADDER-FAIL`
* **N3**: `KERNEL-CANDIDATE-NO-HOME`, `KERNEL-CANDIDATE-DUP-ISO`
* **N4**: `KERNEL-RANK-NONCONTIG`
* **N5**: `KERNEL-PRIORS-FAIL`
* **N6**: `KERNEL-COUNTS-INFEASIBLE`
* **N7**: `KERNEL-SEQUENCE-NO-COUNTS`
* **N8**: `PACKAGE-LINEAGE-MISSING`, `PACKAGE-SORT-BREACH`
* **N9–N12**: `EMIT-*` family (incl. `EMIT-FINAL-EXISTS` as **skip**)

---

## 15.5 Routing logic (normative)

* **Run-scoped:** fail fast; return control to the run controller; do **not** open the worker pool.
* **Merchant-scoped:** mark merchant failed; do **not** call N8–N12; continue with other merchants.
* **Dataset/Partition-scoped:** mark merchant failed for remaining emits; continue other merchants.

**Never** downgrade a dataset/partition error to a skip (except the two explicit informational cases: `EMIT-FINAL-EXISTS` and *empty slice no-op*).

---

## 15.6 Pseudocode (host-neutral) for error handling

```
PROC process_merchant_S3(merchant_id, run_ctx):
  TRY:
    // N1..N7 kernels and N8 packaging
    emit_slice_in_order(...)
  CATCH e WHERE e.scope IN {MERCHANT, DATASET}:
    HOST_LOG("ERROR", e.code, {merchant_id, node:e.node, dataset:e.dataset_id?})
    RETURN FAIL
END PROC

PROC run_S3_L2(run_cfg):
  TRY:
    guard_options(run_cfg.toggles)                           // §8
    part_state := OBSERVE_PARTITION_STATE(run_cfg.parameter_hash)
    guard_resume(run_cfg, part_state)                        // §10
  CATCH e WHERE e.scope == RUN:
    HOST_LOG("ERROR", e.code, {...})
    ABORT

  pool := HOST_WORKER_POOL(run_cfg.N_WORKERS)
  FOR m IN HOST_MERCHANT_LIST(run_cfg.parameter_hash):
    pool.submit(process_merchant_S3(m, run_ctx))
  pool.join_all()
END PROC
```

---

## 15.7 Acceptance checklist (for this section)

* Stable, minimal error codes with clear **scope**, **node**, and **action**.
* `EMIT-FINAL-EXISTS` and **empty-slice no-op** treated as **skips**, not errors.
* Guards cover options and resume **before** work begins; merchant/dataset failures never heal or backfill.
* Error payload shape ensures triage without guesswork.
* DAG map shows exactly **where** each code may arise, and codes align with §§6–14 (including `IDEMP-INCONSISTENT-FINALS` from §10).

---

This taxonomy keeps S3·L2 predictable under all failure modes: we either **skip deterministically**, **fail this merchant**, or **abort the run**—with a stable codebook an implementer can wire directly into logs or a controller.

---

# 16) Logging (Operational, Not Evidence)

## 16.1 Intent & scope

Operational visibility for S3·L2 orchestration: progress, options, throughput, and failures. **Not evidence**: validators/consumers must ignore these logs entirely. No schema coupling; logs are disposable.

* **Side effect:** `HOST_LOG(level, message, kv?)` only.
* **Determinism:** messages **must not** influence control flow or outputs.
* **Non-goals:** do **not** log RNG events (S3 has none), row payloads, PII, or filesystem paths.

---

## 16.2 Principles (binding)

* **Separation from data:** logs are never written into S3 datasets; S3 datasets never depend on logs.
* **Structured-first:** stable keys with JSON-like `kv`.
* **Stable names, flexible values:** event names and key names are stable; counts/durations may vary.
* **Timestamp policy:** `ts` is **optional** and explicitly **non-deterministic**; prefer `seq` counters for reproducible traces.
* **Low overhead:** logging must not materially degrade throughput.

---

## 16.3 Base envelope (all events)

Each log entry **must** include:

```
{
  "comp": "S3.L2",                      // component
  "phase": "<RUN|MERCHANT|EMIT>",       // coarse scope
  "level": "<INFO|WARN|ERROR>",
  "parameter_hash": "<Hex64>",
  "manifest_fingerprint": "<Hex64>",
  "event": "<STABLE_EVENT_NAME>",       // §16.4
  "seq": <u64>,                         // monotonically increasing per process; no wrap
  "ts?": "<ISO-8601>",                  // optional; nondeterministic
  "kv": { ... }                         // event-specific fields
}
```

> `seq` is required and increments once per log call; `ts` (if present) is never used for logic.

---

## 16.4 Event catalog (stable names & required fields)

### RUN-scope

* **`RUN_START`** — L2 starting.
  `kv: { "toggles": {emit_priors, emit_counts, emit_sequence}, "workers": N_WORKERS }`
* **`BOM_OPENED`** — `HOST_OPEN_BOM` succeeded.
  `kv: { "dp": dp, "dp_resid": dp_resid, "bounds": <bool> }`
* **`RESUME_GUARDS_OK`** — §10 guards passed (or no finals).
  `kv: { "has_any_final": <bool> }`
* **`POOL_STARTED`** — worker pool created.
  `kv: { "workers": N_WORKERS, "queue_capacity": queue_capacity }`
* **`RUN_SUMMARY`** — end-of-run stats.

  ```
  kv: {
    "merchants_total": int, "merchants_ok": int, "merchants_failed": int,
    "rows_emitted": { "candidate_set": int, "priors": int, "counts": int, "sequence": int },
    "emit_skips":   { "candidate_set": int, "priors": int, "counts": int, "sequence": int },
    "avg_emit_ms":  { "candidate_set": int, "priors": int, "counts": int, "sequence": int }
  }
  ```

### MERCHANT-scope

* **`MERCHANT_START`** — begin per-merchant orchestration.
  `kv: { "merchant_id": id }`
* **`MERCHANT_KERNELS_DONE`** — N1…N4 (and N5–N7 if taken) completed.
  `kv: { "merchant_id": id, "lanes": { "priors": bool, "counts": bool, "sequence": bool },
         "countries": int, "N_outlets?": int }`
* **`MERCHANT_PACKAGE_DONE`** — N8 completed.
  `kv: { "merchant_id": id,
         "rows": { "candidate": int, "priors": int, "counts": int, "sequence": int } }`
* **`MERCHANT_DONE`** — per-merchant result.
  `kv: { "merchant_id": id, "status": "<OK|FAIL>" }`

### EMIT-scope (per dataset call)

* **`EMIT_BEGIN`** — before emitter call.
  `kv: { "merchant_id": id, "dataset": "<candidate_set|priors|counts|sequence>", "rows": int }`
* **`EMIT_SKIPPED_FINAL`** — idempotent skip.
  `kv: { "merchant_id": id, "dataset": "<...>" }`
* **`EMIT_COMMITTED`** — emit completed successfully.
  `kv: { "merchant_id": id, "dataset": "<...>", "rows": int, "ms": int }`
* **`EMIT_FAIL`** — emitter returned non-idempotent failure.
  `kv: { "merchant_id": id, "dataset": "<...>", "code": "<EMIT-*>", "msg": str }`

### ERROR/WARN mapping (deterministic)

* Map **§15 error codes** 1:1 into `event="<ERROR_CODE>"` with `level="ERROR"` and include the §15 payload keys (`node`, `dataset_id?`, `toggles_snapshot`, `details?`, …).
* Non-fatal advisories use `level="WARN"` (e.g., bounds present but counts disabled).

---

## 16.5 Where to log (and where not)

* **Allowed backends:** stdout, JSONL file, or host logging service via `HOST_LOG`.
* **Forbidden:** writing logs into S3 dataset trees, sidecar “evidence” within partitions, or leaking S3 dataset paths.

---

## 16.6 Volume & sampling

* **Default verbosity:** `INFO` for RUN/MERCHANT milestones and EMIT events; `ERROR` on failures; `WARN` for advisories.
* **Sampling:** allowed **only** for high-frequency `EMIT_COMMITTED` when chunked writes are very fine-grained. If sampling,

  * include a counter of suppressed events (e.g., `kv.suppressed: 37`), and
  * **never** sample `EMIT_SKIPPED_FINAL` or any `ERROR`/`WARN`.

---

## 16.7 Example entries (illustrative)

```
{ "comp":"S3.L2","phase":"RUN","level":"INFO","event":"RUN_START",
  "parameter_hash":"ab12..","manifest_fingerprint":"cd34..","seq":1,
  "kv":{"toggles":{"priors":true,"counts":true,"sequence":false},"workers":8} }

{ "comp":"S3.L2","phase":"MERCHANT","level":"INFO","event":"MERCHANT_KERNELS_DONE",
  "parameter_hash":"ab12..","manifest_fingerprint":"cd34..","seq":42,
  "kv":{"merchant_id":"M123","lanes":{"priors":1,"counts":1,"sequence":0},"countries":5,"N_outlets":37} }

{ "comp":"S3.L2","phase":"EMIT","level":"INFO","event":"EMIT_SKIPPED_FINAL",
  "parameter_hash":"ab12..","manifest_fingerprint":"cd34..","seq":87,
  "kv":{"merchant_id":"M123","dataset":"candidate_set"} }

{ "comp":"S3.L2","phase":"RUN","level":"ERROR","event":"KERNEL-COUNTS-INFEASIBLE",
  "parameter_hash":"ab12..","manifest_fingerprint":"cd34..","seq":133,
  "kv":{"merchant_id":"M456","node":"N6",
        "details":{"bound":"min_US","expected":12,"observed":9}} }
```

---

## 16.8 Privacy & content rules

* **No PII** beyond `merchant_id`. No coordinates, free-text policies, or row dumps.
* **No secrets/paths.** Dictionary/partition paths and temp locations must never appear.
* Messages should be short; heavy data belongs in external metrics if required.

---

## 16.9 Acceptance checklist (for this section)

* Logging is **operational-only**; zero coupling to data products.
* Stable event names with required `kv` keys; base envelope present for all logs.
* Deterministic mapping from §15 errors to `ERROR` events.
* Volume controls present; timestamps optional and non-deterministic.
* No PII beyond `merchant_id`; no filesystem paths; low overhead.

---

# 17) Acceptance Checklist (L2)

## 17.1 Green-gate summary (all must be **true**)

* [ ] **Scope locked.** L2 is *wiring only*: no RNG, no policy math, no schema/partition drift (§1–§2).
* [ ] **Datasets fixed.** Publish set, partitions, and writer sorts match §3; **parameter-scoped only**.
* [ ] **Surfaces fixed.** Only §3A function IDs are called; §3B checklist passes.
* [ ] **DAGs canonical.** §4 (human) and §5 (authoritative) agree on nodes/edges and prohibited edges.
* [ ] **Concurrency safe.** Across-merchant parallelism only; within-merchant serial; **single-writer rule** enforced (§6).
* [ ] **Kernel wiring exact.** `N1→…→N8→N9→…` with **one** packaging point; lineage attached once (§7).
* [ ] **Options legal.** Matrix + guards honored; `emit_sequence ⇒ emit_counts` (§8).
* [ ] **Publish correct.** Fixed emit order, pre-sorted rows, **embed=path**, atomic + idempotent (§9).
* [ ] **Resume safe.** Manifest/toggle guards; `skip_if_final` semantics; exactly-once slices (§10).
* [ ] **Deterministic.** Byte-identical for fixed lineage/options; **no timestamps** in rows (§11).
* [ ] **Lineage discipline.** Attach at N8; verify at emit; no path literals (§12).
* [ ] **Host shims.** Only read-only, path-agnostic interfaces (§13).
* [ ] **Knobs practical.** §14 defaults/ranges change throughput **without** changing bytes.
* [ ] **Errors minimal.** §15 codes + routing; `EMIT-FINAL-EXISTS` and empty-slice are **skips**.
* [ ] **Logging operational.** §16 structured logs; zero coupling to data.

---

## 17.2 Section-by-section gates (tick with evidence)

### §1–§2 Purpose, Scope, Inputs/Preconditions

* [ ] L2 defined as orchestration-only; non-goals explicit.
* [ ] Run lineage `{parameter_hash, manifest_fingerprint}` fixed; BOM opened read-only.

### §3 Datasets & Partitions

* [ ] Required/optional datasets listed; **writer sorts** stated.
* [ ] Partition key = `parameter_hash` only; **embed=path** rule present.

### §3A Orchestration Surfaces (Function Import Ledger)

* [ ] All L1 kernels, L0 emitters, and host shims declared with signatures.
* [ ] L2-local glue limited to orchestration; no policy.

### §3B Common Glue Checklist

* [ ] Checklist included and **passes** (DAG, emit order, idempotence, lineage).

### §4–§5 DAGs

* [ ] Node registry `N0..N12` stable; full edge list with guards + prohibited edges.
* [ ] Single permitted topological order listed.

### §6 Concurrency & Scheduling

* [ ] Deterministic merchant iteration order documented.
* [ ] Single-writer rule enforced; one packaging point; serialized emits per merchant.

### §7 Kernel Wiring

* [ ] `N1..N7` pure; `N8` attaches lineage + writer sorts; `N9..N12` fixed emit order.
* [ ] No reshaping after packaging.

### §8 Options & Dependencies

* [ ] Legality matrix; illegal combos rejected **pre-dispatch**.
* [ ] Derived enables + **options-off short-circuit** defined.

### §9 Publish Protocol

* [ ] Pre-publish invariants; emitter contracts; **zero-row = no-op**.
* [ ] Atomic tmp→fsync→rename; `skip_if_final` mandated.

### §10 Idempotence & Resume

* [ ] Resume guards (`IDEMP-*`) defined; exactly-once semantics for slices.
* [ ] R1–R6 scenarios covered with deterministic outcomes.

### §11 Determinism & Ordering

* [ ] `candidate_rank` sole inter-country order; within-country `site_order` when enabled.
* [ ] Locale-agnostic sorts; no RNG/timestamps.

### §12 Partitioning & Lineage

* [ ] Packaging-time attach; publish-time **embed=path** + manifest checks.
* [ ] Cross-dataset lineage equality required.

### §13 Host Interfaces

* [ ] Shims return values/handles only; path-agnostic; thread-safe.

### §14 Resources & Knobs

* [ ] Defaults & ranges specified; knobs do **not** change bytes.
* [ ] Single-writer/backpressure strategy documented.

### §15 Errors

* [ ] Stable codes with scope; DAG map of where each can arise; routing logic present.
* [ ] Includes `IDEMP-INCONSISTENT-FINALS` per §10.

### §16 Logging

* [ ] Base envelope; event catalog; §15 error→`ERROR` mapping; privacy rules.

---

## 17.3 Dry-run acceptance (developer self-test)

* [ ] **`N_WORKERS=1` vs `N_WORKERS=8`** → output partitions are **bit-identical**.
* [ ] **Resume mid-run** (some partitions final) → re-run with same lineage/toggles writes **no new bytes** to finals.
* [ ] **Illegal options** (`emit_sequence=true`, `emit_counts=false`) → run aborts with `O-ILLEGAL-SEQ-WITHOUT-COUNTS`.
* [ ] **Manifest mismatch resume** (finals exist, different fingerprint) → `IDEMP-MANIFEST-MISMATCH`.
* [ ] **Mixed finals detection** → `IDEMP-INCONSISTENT-FINALS`.
* [ ] **Embed/path breach simulation** at emit → `EMIT-EMBED-PATH-MISMATCH` and merchant publish stops.

---

## 17.4 Freeze sign-off (record)

Fill before freezing:

```
Doc version: __________   SHA256: ______________________________________
Lineage tuple: parameter_hash=________________  manifest_fingerprint=________________
Toggles: priors=__  counts=__  sequence=__
Merchant iteration order: _____________________
DAG version: N0..N12 registry @ commit ________
Emitters binding (L0): version/commit ___________
Checklist owner: ___________   Date: __________
```

---

# 18) Worked Runflow (Illustrative, Non-Normative)

## 18.1 Run setup

**Lineage / options**

```
parameter_hash        = "ab12…"
manifest_fingerprint  = "cd34…"
toggles               = { emit_priors: true, emit_counts: true, emit_sequence: true }
```

**Host open**

```
bom := HOST_OPEN_BOM()
  ladder        = <governed ruleset>
  iso_universe  = {"GB","IE","FR","NL","DE"}
  dp            = 6
  dp_resid      = 8
  bounds        = { min: {GB:1}, max: {} }   // optional; example only
```

**Merchant domain (stable order)**

```
HOST_MERCHANT_LIST(parameter_hash="ab12…") = ["M123","M456"]
```

`N_WORKERS=4`; across-merchant parallelism is allowed; within-merchant is serial (§6).

---

## 18.2 Merchant “M123” — foreigns admitted; all lanes enabled

### 18.2.1 Kernels (pure)

**N1 `s3_build_ctx` → `Ctx`**

```
Ctx = { merchant_id:"M123", home_country_iso:"GB", … }
```

**N2 `s3_evaluate_rule_ladder` → `DecisionTrace`**

```
DecisionTrace = { eligible:true, tags:["ALLOW:EU","DEFAULT"], … }
```

**N3 `s3_make_candidate_set` → `CandidateRow[]` (unordered)**

```
[
  {iso:"GB", is_home:true,  reason_codes:["HOME"],  filter_tags:[]},
  {iso:"IE", is_home:false, reason_codes:["ALLOW"], filter_tags:[]},
  {iso:"FR", is_home:false, reason_codes:["ALLOW"], filter_tags:[]},
  {iso:"NL", is_home:false, reason_codes:["ALLOW"], filter_tags:[]}
]
```

**N4 `s3_rank_candidates` → `RankedCandidateRow[]`**

```
[
  {iso:"GB", candidate_rank:0, is_home:true},
  {iso:"IE", candidate_rank:1},
  {iso:"FR", candidate_rank:2},
  {iso:"NL", candidate_rank:3}
]
```

Contiguous ranks; **home=0**; this is the **sole inter-country order**.

**N5 `s3_compute_priors` (scores; dp=6)**

```
[
  {iso:"GB", score:"0.402500"},
  {iso:"IE", score:"0.215000"},
  {iso:"FR", score:"0.230000"},
  {iso:"NL", score:"0.152500"}
]
```

Scores are **not probabilities**; no renorm.

**N6 `s3_integerise_counts` (Σ=N; N from S2, say N=37; dp_resid=8)**

```
[
  {iso:"GB", count:15, residual_rank:3},
  {iso:"IE", count: 8, residual_rank:1},
  {iso:"FR", count: 8, residual_rank:2},
  {iso:"NL", count: 6, residual_rank:4}
]  // sum = 37
```

**N7 `s3_sequence_within_country` (requires counts)**

```
[
  // GB 1..15
  {iso:"GB", site_order:1,  site_id:"000001"}, … {iso:"GB", site_order:15, site_id:"000015"},
  // IE 1..8
  {iso:"IE", site_order:1,  site_id:"000001"}, … {iso:"IE", site_order:8,  site_id:"000008"},
  // FR 1..8, NL 1..6
  …
]
```

Within-country only; **countries are never reordered**.

### 18.2.2 Package & emit

**N8 `package_for_emit`** (attach lineage; apply writer sorts; freeze rows)

`candidate_rows` — writer sort: `(merchant_id, candidate_rank, country_iso)`
*(File order is non-authoritative for inter-country order; only `candidate_rank` is.)*

```
{M123, GB, rank:0, …, parameter_hash:"ab12…", manifest_fingerprint:"cd34…"}
{M123, IE, rank:1, …, parameter_hash:"ab12…", manifest_fingerprint:"cd34…"}
{M123, FR, rank:2, …, parameter_hash:"ab12…", manifest_fingerprint:"cd34…"}
{M123, NL, rank:3, …, parameter_hash:"ab12…", manifest_fingerprint:"cd34…"}
```

`prior_rows` — writer sort: `(merchant_id, country_iso)`
`count_rows` — writer sort: `(merchant_id, country_iso)`
`sequence_rows` — writer sort: `(merchant_id, country_iso, site_order)`

**Emit order (idempotent; atomic)**

```
EMIT_S3_CANDIDATE_SET      (candidate_rows, "ab12…", "cd34…", skip_if_final=true)
EMIT_S3_BASE_WEIGHT_PRIORS (prior_rows,     "ab12…", "cd34…", skip_if_final=true)
EMIT_S3_INTEGERISED_COUNTS (count_rows,     "ab12…", "cd34…", skip_if_final=true)
EMIT_S3_SITE_SEQUENCE      (sequence_rows,  "ab12…", "cd34…", skip_if_final=true)
```

---

## 18.3 Merchant “M456” — options-off short-circuit; candidates only

Assume ladder admits **only home**, and **all optional lanes are disabled** at run level.

`N1..N4` produce:

```
RankedCandidateRow[] = [{iso:"GB", candidate_rank:0, is_home:true}]
```

**Short-circuit:** `N4 → N8 → N9` (package + emit candidate_set only).

---

## 18.4 Across-merchant concurrency (timeline sketch)

```
t0: N0_open_bom
t1: submit M123, M456 (deterministic order)
t2: M123 runs N1..N7 (pure) in worker A  |  M456 runs N1..N4 (pure) in worker B
t3: M456 short-circuits → N8 → N9 (candidate_set)
t4: M123 N8 package → N9..N12 (all datasets)
t5: gather, RUN_SUMMARY
```

**Single-writer enforcement:** even with parallel workers, emits targeting the same `(dataset, parameter_hash)` are **serialized** (backpressure or per-partition mutex) (§6.7).

---

## 18.5 Idempotent resume (two scenarios)

**R2 — Crash after some emits**
Re-run with same lineage/toggles:

* Already-final partitions ⇒ emitters **skip** (no-op).
* Remaining datasets for M123 commit atomically in order.

**R5 — Resume with different toggles (forbidden)**
Changing `emit_counts=false` while `candidate_set` is final for `"ab12…"` triggers:

```
ERROR IDEMP-TOGGLE-MISMATCH   // abort before scheduling
```

---

## 18.6 Operator’s log excerpts (illustrative)

*(Matches §16 event names and envelope.)*

```
INFO RUN_START              kv={toggles:{priors:1,counts:1,sequence:1}, workers:4}
INFO BOM_OPENED             kv={dp:6, dp_resid:8, bounds:true}
INFO RESUME_GUARDS_OK       kv={has_any_final:false}
INFO MERCHANT_START         kv={merchant_id:"M123"}
INFO MERCHANT_START         kv={merchant_id:"M456"}
INFO MERCHANT_KERNELS_DONE  kv={merchant_id:"M456", lanes:{priors:0,counts:0,sequence:0}, countries:1}
INFO MERCHANT_PACKAGE_DONE  kv={merchant_id:"M456", rows:{candidate:1, priors:0, counts:0, sequence:0}}
INFO EMIT_COMMITTED         kv={merchant_id:"M456", dataset:"candidate_set", rows:1, ms:7}
INFO MERCHANT_DONE          kv={merchant_id:"M456", status:"OK"}
INFO MERCHANT_KERNELS_DONE  kv={merchant_id:"M123", lanes:{priors:1,counts:1,sequence:1}, countries:4, N_outlets:37}
INFO MERCHANT_PACKAGE_DONE  kv={merchant_id:"M123", rows:{candidate:4, priors:4, counts:4, sequence:37}}
INFO EMIT_COMMITTED         kv={merchant_id:"M123", dataset:"candidate_set", rows:4, ms:9}
INFO EMIT_COMMITTED         kv={merchant_id:"M123", dataset:"priors", rows:4, ms:4}
INFO EMIT_COMMITTED         kv={merchant_id:"M123", dataset:"counts", rows:4, ms:5}
INFO EMIT_COMMITTED         kv={merchant_id:"M123", dataset:"sequence", rows:37, ms:22}
INFO MERCHANT_DONE          kv={merchant_id:"M123", status:"OK"}
INFO RUN_SUMMARY            kv={merchants_total:2, merchants_ok:2, merchants_failed:0,
                                rows_emitted:{candidate_set:5,priors:4,counts:4,sequence:37},
                                emit_skips:{candidate_set:0,priors:0,counts:0,sequence:0}}
```

---

## 18.7 What this runflow demonstrates (tie-back)

* **DAG fidelity:** nodes/edges exactly match §5; short-circuit is `N4 → N8 → N9` only.
* **Order authority preserved:** `candidate_rank` is the only inter-country order; sequencing is within-country only.
* **Emit order & idempotence:** `candidate → [priors] → [counts] → [sequence]` with `skip_if_final=true`; resume is safe.
* **Partitioning/lineage discipline:** rows embed `{parameter_hash, manifest_fingerprint}` at packaging and match the partition at publish.
* **Concurrency discipline:** parallel across merchants; single writer per `(dataset, parameter_hash)`.

---

# 19) Appendices

## 19.A Dataset ↔ Schema ↔ Sort ↔ Partition (one-pager)

| Dataset ID              | Schema Anchor                       | Writer Sort (logical)                        | Partition Keys   | Ownership / Notes                                                                                                               |
|-------------------------|-------------------------------------|----------------------------------------------|------------------|---------------------------------------------------------------------------------------------------------------------------------|
| `s3_candidate_set`      | `schemas.1A.yaml#/s3/candidate_set` | `(merchant_id, candidate_rank, country_iso)` | `parameter_hash` | **Required.** Sole authority for inter-country order (`candidate_rank`, home=0, contiguous). *File order is non-authoritative.* |
| `s3_base_weight_priors` | `#/s3/base_weight_priors`           | `(merchant_id, country_iso)`                 | `parameter_hash` | Optional. **Scores**, not probabilities. No renorm in L2.                                                                       |
| `s3_integerised_counts` | `#/s3/integerised_counts`           | `(merchant_id, country_iso)`                 | `parameter_hash` | Optional. Σcount=N; `residual_rank` recorded.                                                                                   |
| `s3_site_sequence`      | `#/s3/site_sequence`                | `(merchant_id, country_iso, site_order)`     | `parameter_hash` | Optional; **requires counts**. Never permutes country blocks.                                                                   |

**Rules recap:** parameter-scoped only; lineage `{parameter_hash, manifest_fingerprint}` embedded in every row; emit order `candidate → [priors] → [counts] → [sequence]`; atomic tmp→fsync→rename; `skip_if_final=true`.

---

## 19.B DAG Node Registry (N0..N12)

| ID  | Function ID (Source)                   | Type           | Summary                                               |
|-----|----------------------------------------|----------------|-------------------------------------------------------|
| N0  | `HOST_OPEN_BOM` (Host)                 | side-effect RO | Open ladder/ISO/dp/bounds/toggles for the run.        |
| N1  | `s3_build_ctx` (L1)                    | pure           | Build `Ctx` (ids, home ISO, lineage tuple).           |
| N2  | `s3_evaluate_rule_ladder` (L1)         | pure           | Deterministic policy decision → `DecisionTrace`.      |
| N3  | `s3_make_candidate_set` (L1)           | pure           | `{home} ∪ admitted foreigns` with tags.               |
| N4  | `s3_rank_candidates` (L1)              | pure           | Total order; **`candidate_rank`** contiguous; home=0. |
| N5  | `s3_compute_priors` (L1, opt)          | pure           | Fixed-dp **scores**; no renorm.                       |
| N6  | `s3_integerise_counts` (L1, opt)       | pure           | LRR; Σcount=N; bounds optional.                       |
| N7  | `s3_sequence_within_country` (L1, opt) | pure           | `site_order` 1..nᵢ; optional 6-digit `site_id`.       |
| N8  | `package_for_emit` (L2)                | pure           | Attach lineage; apply writer sorts; freeze rows.      |
| N9  | `EMIT_S3_CANDIDATE_SET` (L0)           | I/O            | Publish candidates; idempotent; atomic.               |
| N10 | `EMIT_S3_BASE_WEIGHT_PRIORS` (L0, opt) | I/O            | Publish priors; idempotent; atomic.                   |
| N11 | `EMIT_S3_INTEGERISED_COUNTS` (L0, opt) | I/O            | Publish counts; idempotent; atomic.                   |
| N12 | `EMIT_S3_SITE_SEQUENCE` (L0, opt)      | I/O            | Publish sequence; idempotent; atomic.                 |

**Prohibited edges:** reordering kernels; emitting before N8; `N7` without `N6`; concurrent writers to the same `(dataset, parameter_hash)`.

---

## 19.C Function Surfaces (copy-paste ledger)

### L1 kernels (import only; pure)

* `s3_build_ctx(ingress, s1_s2_facts, bom, vocab) -> Ctx`
* `s3_evaluate_rule_ladder(Ctx, ladder) -> DecisionTrace`
* `s3_make_candidate_set(Ctx, DecisionTrace, iso_universe, ladder) -> CandidateRow[]`
* `s3_rank_candidates(CandidateRow[], admission_meta_map, home_iso) -> RankedCandidateRow[]`
* `s3_compute_priors(RankedCandidateRow[], dp) -> PriorRow[]` *(opt)*
* `s3_integerise_counts(RankedCandidateRow[], N, bounds?, dp_resid) -> CountRow[]` *(opt)*
* `s3_sequence_within_country(CountRow[], site_id_cfg?) -> SequenceRow[]` *(opt)*

### L2 glue (this doc; orchestration only)

* `run_S3_L2(run_cfg) -> void`
* `process_merchant_S3(merchant_id, run_ctx) -> PublishBundle`
* `package_for_emit(bundle, lineage) -> { candidate_rows, prior_rows?, count_rows?, sequence_rows? }`
* `emit_slice_in_order({candidate_rows, prior_rows?, count_rows?, sequence_rows?}, lineage, skip_if_final=true) -> void`
* `guard_options(toggles) -> void`
* `guard_resume(run_cfg, observed_partition_state) -> void`   ← *(resume guard from §10)*

### L0 emitters (I/O; dictionary-resolved)

* `EMIT_S3_CANDIDATE_SET(...)` · `EMIT_S3_BASE_WEIGHT_PRIORS(...)` · `EMIT_S3_INTEGERISED_COUNTS(...)` · `EMIT_S3_SITE_SEQUENCE(...)`

### Host shims (read-only)

* `HOST_OPEN_BOM()` · `HOST_MERCHANT_LIST(parameter_hash)` · `HOST_GET_INGRESS(merchant_id)` · `HOST_GET_S1S2_FACTS(merchant_id)` · `HOST_WORKER_POOL(N_WORKERS)` · `HOST_DICTIONARY_HANDLE()` · `OBSERVE_PARTITION_STATE(parameter_hash)` · `HOST_LOG(level,msg,kv?)`

---

## 19.D Options Matrix (quick reference)

| Toggles (`priors`, `counts`, `sequence`) | Legal? | Enforced Edges                                  |
|------------------------------------------|:------:|-------------------------------------------------|
| 0,0,0                                    |   ✓    | `N4 → N8 → N9`                                  |
| 1,0,0                                    |   ✓    | `N4 → N5 → N8 → N9 → N10`                       |
| 0,1,0                                    |   ✓    | `N4 → N6 → N8 → N9 → N11`                       |
| 1,1,0                                    |   ✓    | `N4 → N5 → N6 → N8 → N9 → N10 → N11`            |
| 0,0,1                                    |   ✗    | **Illegal:** sequence requires counts           |
| 1,0,1                                    |   ✗    | **Illegal:** sequence requires counts           |
| 0,1,1                                    |   ✓    | `N4 → N6 → N7 → N8 → N9 → N11 → N12`            |
| 1,1,1                                    |   ✓    | `N4 → N5 → N6 → N7 → N8 → N9 → N10 → N11 → N12` |

Guard: **`emit_sequence ⇒ emit_counts`**. Bounds valid only if counts emitted.

---

## 19.E Error Codes (pocket list)

* **Run-scoped:** `HOST-BOM-MISSING`, `HOST-POOL-FAILURE`, `HOST-DICT-HANDLE-FAIL`, `O-ILLEGAL-SEQ-WITHOUT-COUNTS`, `IDEMP-MANIFEST-MISMATCH`, `IDEMP-TOGGLE-MISMATCH`, **`IDEMP-INCONSISTENT-FINALS`**.
* **Merchant-scoped:** `KERNEL-INGRESS-MISSING`, `KERNEL-S1S2-MISSING`, `KERNEL-LADDER-FAIL`, `KERNEL-CANDIDATE-NO-HOME`, `KERNEL-CANDIDATE-DUP-ISO`, `KERNEL-RANK-NONCONTIG`, `KERNEL-PRIORS-FAIL`, `KERNEL-COUNTS-INFEASIBLE`, `KERNEL-SEQUENCE-NO-COUNTS`, `PACKAGE-LINEAGE-MISSING`, `PACKAGE-SORT-BREACH`.
* **Dataset/Partition:** `EMIT-FINAL-EXISTS` *(skip)*, `EMIT-EMBED-PATH-MISMATCH`, `EMIT-MANIFEST-MISMATCH`, `EMIT-SCHEMA-MISMATCH`, `EMIT-ATOMIC-FAILED`, `EMIT-ILLEGAL-ORDER`.

**Routing:** run ⇒ abort; merchant ⇒ skip emits for merchant; dataset ⇒ stop further emits for merchant (others continue).

---

## 19.F Quick-start Runbook (single machine)

1. **Open BOM & guards**
   `bom := HOST_OPEN_BOM(); guard_options(bom.toggles); guard_resume(run_cfg, OBSERVE_PARTITION_STATE(parameter_hash))`
2. **Start pool**
   `pool := HOST_WORKER_POOL(N_WORKERS)`; iterate merchants from `HOST_MERCHANT_LIST(parameter_hash)` in deterministic order.
3. **Per merchant**
   Call **N1..N7** (pure) → `package_for_emit` (attach lineage + writer sorts) → `emit_slice_in_order` (idempotent, atomic).
4. **Done**
   Emit `RUN_SUMMARY` via `HOST_LOG`.

**Safe defaults:** `N_WORKERS = min(cores, 8)`, `batch_rows = 20_000`, `emit_backpressure = true`, writer sorts per 19.A.

---

## 19.G Glossary & Symbols

* **Ctx**: immutable per-merchant context from `s3_build_ctx`.
* **DecisionTrace**: deterministic ladder result + tags.
* **CandidateRow / RankedCandidateRow**: pre-/post-order arrays; `candidate_rank` authoritative after ranking.
* **PriorRow / CountRow / SequenceRow**: optional arrays for priors, integerised counts (Σ=N, `residual_rank`), and within-country sequencing (`site_order` 1..nᵢ).
* **Lineage**: `{parameter_hash, manifest_fingerprint}` embedded in every row.
* **Partition**: `(dataset_id, parameter_hash)`; S3 has no `seed` partitions.
* **Final exists**: target partition already final; emitters **skip** with `skip_if_final=true`.

---

## 19.H Acceptance Sign-off (copy form)

```
Doc version: __________   SHA256: ______________________________________
Lineage: parameter_hash=________________  manifest_fingerprint=________________
Toggles: priors=__  counts=__  sequence=__
Merchant iteration order: _____________________
DAG registry N0..N12 @ commit: ________________
L0 emitters binding @ commit: _________________
All §17 gates ticked by: ___________   Date: __________
```

---

## 19.I Operator’s Counters (from §14/§16)

* `merchants_processed_total`, `merchants_ok`, `merchants_failed`
* `rows_emitted_total` per dataset; `emit_skips_total` per dataset
* `avg_emit_ms` per dataset; `chunk_writes_total` (if streaming)
* `max_bytes_in_worker`

**Use:** diagnose CPU vs I/O bottlenecks without changing bytes.

---