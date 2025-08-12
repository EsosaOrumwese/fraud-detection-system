# S9.1 — Scope, inputs, outputs (deepened)

## Purpose (scope of S9)

Establish, for a fixed run lineage $(\texttt{seed}, \texttt{manifest_fingerprint}, \texttt{parameter_hash}, \texttt{run_id})$, that 1A’s *immutable egress* is (i) schema-valid, (ii) internally consistent with **all** upstream artefacts and RNG logs, and (iii) statistically sane within governed corridors. Success emits a **signed validation bundle** and a `_passed.flag` authorising the 1A→1B hand-off **for exactly this** `manifest_fingerprint`.

---

## Inputs (read-only, with partitions & authority)

1. **Egress (authoritative, run-scoped)**

* Dataset: `outlet_catalogue`
* Partition: `seed={seed}/fingerprint={manifest_fingerprint}`
* Schema: `schemas.1A.yaml#/egress/outlet_catalogue`
* Semantics: within-country `site_order` only; **no** inter-country order encoded here. This table is immutable under a given `fingerprint`.

2. **Allocation caches (parameter-scoped)**

* `country_set(seed={seed}/parameter_hash={parameter_hash})` — the **only** authority on inter-country order (`rank`; 0=home).
* `ranking_residual_cache_1A(seed, parameter_hash)` — persisted fractional residuals + ranks used to *reproduce* largest-remainder integerisation.

3. **Diagnostic / eligibility caches (parameter-scoped)**

* `hurdle_pi_probs(parameter_hash)` (if present) — model-implied multi-site probabilities.
* `sparse_flag(parameter_hash)` — currency sparsity mask.
* `crossborder_eligibility_flags(parameter_hash)` — the S3 policy firewall outcome.

4. **RNG evidence (run-scoped)**

* `rng_audit_log` — master envelope (algo, master seed, label map, jumps).
* Structured event logs under `schemas.layer1.yaml#/rng/...` for the labels used by 1A (e.g., `gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`). Paths/catalog are fixed by the registry/dictionary.

5. **Lineage keys (scope discriminants)**

* `parameter_hash` (artefact bundle identity from S0).
* `manifest_fingerprint` (run-closure identity from S0).
* `seed`, `run_id` (RNG/run scoping). All are treated as **inputs to validation**, never overwritten.

**Pre-flight presence tests (must pass before S9.2+):**

* Exactly one `outlet_catalogue` partition at `(seed,fingerprint)`.
* Matching `country_set`/`ranking_residual_cache_1A` at `(seed,parameter_hash)`.
* RNG evidence present for **every** label referenced in the registry for the run’s modules. Missing any of these is a hard S9.1 failure.

---

## Outputs (state products and contracts)

1. **`validation_bundle_1A` (ZIP)**

* Location: `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
* Index: `index.json` conforming to `schemas.1A.yaml#/validation/validation_bundle`
* Contents at minimum: schema checks, key constraints, RNG accounting, corridor metrics, reproducible diffs, and provenance. (Exact structure elaborated later in S9.7.)

2. **`_passed.flag`**

* Same folder as the bundle. Its **content hash equals the bundle hash** (registry contract). Presence + digest match is the sole authorisation signal for 1B to consume this egress partition.

3. **Hand-off condition to 1B**

* 1B **may read** `outlet_catalogue(seed,fingerprint)` **iff** `_passed.flag` exists **and** its digest matches the bundle’s.
* Inter-country order is **only** in `country_set.rank`; 1B **must** join it when needed. This is a hard contract of the schema/policy.

---

## Boundary invariants fixed by S9.1 (what later S9.x assumes)

* **Scope coherence.** Joins always pair `outlet_catalogue(seed,fingerprint)` with caches at `(seed,parameter_hash)` and RNG logs at `(seed,run_id,parameter_hash,fingerprint)` per registry. Mixed scopes are invalid.
* **Immutability.** All inputs are **read-only**; S9 writes only the bundle + flag under the `fingerprint` folder. Egress rows are never mutated during validation.
* **Single source of country order.** Any claim about cross-country ordering must be provable from `country_set.rank`, not from `outlet_catalogue`.

---

## Minimal reference algorithm (collector for S9.2+)

```
INPUT:
  seed, manifest_fingerprint, parameter_hash, run_id

OUTPUT:
  handles = {
    outlet:        read_partition("outlet_catalogue", seed, fingerprint),
    cset:          read_partition("country_set",      seed, parameter_hash),
    residuals:     read_partition("ranking_residual_cache_1A", seed, parameter_hash),
    hurdle_pi:     read_parameter_scoped("hurdle_pi_probs", parameter_hash, optional=true),
    sparse_flag:   read_parameter_scoped("sparse_flag", parameter_hash),
    flags:         read_parameter_scoped("crossborder_eligibility_flags", parameter_hash),
    rng_audit:     read_run_scoped("rng_audit_log", seed, run_id, fingerprint, parameter_hash),
    rng_events:    { read_label_stream(ℓ) for ℓ in registry.labels_for_run(run_id) }
  }

# Pre-flight asserts (abort S9.1 if any fail)
1  assert exists(outlet)      and outlet.partition == (seed,fingerprint)
2  assert exists(cset)        and cset.partition   == (seed,parameter_hash)
3  assert exists(residuals)   and residuals.partition == (seed,parameter_hash)
4  assert exists(rng_audit)   and all required rng_events[ℓ] exist for this run
5  return handles
```

If these pass, S9 proceeds to **S9.2 (notation)** and then into **S9.3–S9.6** for structural, cross-dataset, RNG-replay, and corridor checks, before emitting the bundle and `_passed.flag` in **S9.7**.

---

## Failure semantics at S9.1 (presence/scope only)

* `missing_egress_partition(seed,fingerprint)` — no `outlet_catalogue` for the run’s `fingerprint`.
* `missing_cache(seed,parameter_hash, name)` — required allocation/diagnostic cache absent.
* `missing_rng_evidence(label)` — any required RNG label stream absent for the run.
  Any of the above aborts S9 immediately; a partial bundle may be written with a clear error index, but `_passed.flag` is **never** created.

---

# S9.2 — Notation (per merchant/country)

## Index sets & scoping

* Merchants: $m \in \mathcal{M}$.
* ISO-3166 countries: $i \in \mathcal{I}$ (canonical FK target in the ingress schema). For a given merchant $m$, the **legal set** $\mathcal{I}_m$ comes from `country_set(seed, parameter_hash)`; this dataset is the **only** authority for cross-country order and membership.
* Within a fixed $(m,i)$, outlets are indexed by a **within-country** position $k\in\{1,\dots,n_{m,i}\}$ (= `site_order`). `outlet_catalogue` stores only **within-country** order; cross-country order lives in `country_set.rank`.

Partitions / scope discriminants used throughout S9:

* Egress: `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}`.
* Allocation caches: `country_set/seed={seed}/parameter_hash={parameter_hash}`, `ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}`.
* RNG events: `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.

---

## Observables from egress (per $(m,i,k)$)

* $n_{m,i}\in\mathbb{Z}_{\ge 0}$: **final per-country outlet count**, defined as the row count for $(m,i)$ in `outlet_catalogue`; equivalently the maximum `site_order` observed for $(m,i)$. Schema PK is $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$.
* $s_{m,i,k}\in\{1,\dots,n_{m,i}\}$: **within-country order**, the `site_order` on the $k$-th row; per schema it must be a **gap-free permutation** of $1..n_{m,i}$ for fixed $(m,i)$.
* $\text{id}_{m,i,k}\in\{000000,\dots,999999\}$: **`site_id`**, a 6-digit **zero-padded** image of the per-country sequence. In S8 we log a `sequence_finalize` event per $(m,i)$; overflow $>999999$ is guarded by a dedicated overflow stream. In S9 we assert `site_id` matches the padded `site_order`. Pattern: `^[0-9]{6}$`.
* $H_m\in\{0,1\}$: **`single_vs_multi_flag`** carried on each row (1 = multi-site).
* $N^{\mathrm{raw}}_m\in\mathbb{Z}_{\ge 1}$: **raw NB draw** on the **home-country** row (pre-spread), stored as `raw_nb_outlet_draw`. Used for conservation: $\sum_{i\in\mathcal{I}_m} n_{m,i}\stackrel{!}=N^{\mathrm{raw}}_m$.

---

## Observables from parameter-scoped caches

* $R_{m,i}\in[0,1)$: **largest-remainder residual**, `ranking_residual_cache_1A.residual`. Schema bounds enforce $[0,1)$ with **exclusive** upper bound.
* $r_{m,i}\in\{1,2,\dots\}$: **residual rank** (1 = largest), `ranking_residual_cache_1A.residual_rank`. Used to reconstruct deterministic tie-breaks.
* $\pi_m\in[0,1]$: optional **hurdle probability** from `hurdle_pi_probs` (diagnostic only; never consulted during sampling). If the cache is disabled, $\pi_m$ is *undefined* and excluded from corridor checks.

---

## RNG lineage objects (run-scoped)

* **Audit envelope** $E$: record from `rng_audit_log` describing algorithm, master seed $S_{\text{master}}$, stream map and initial counters; S9 uses it to sanity-check label → substream mapping and counter arithmetic.
* **Event traces** $T_\ell$: for each RNG label $\ell$ used by 1A (e.g.,
  `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`, and earlier `gumbel_key`), the JSONL stream supplies tuples
  $(\texttt{rng_counter_before},\ \texttt{draws},\ \texttt{rng_counter_after},\ \texttt{key})$ under the common envelope. S9 will check **presence, counters’ monotone advance,** and **payload coherence** per schema. Paths and schemas are pinned by the dictionary.

---

## Sets, joins, and helper notation used later in S9

* Legal-country set for merchant $m$: $\mathcal{I}_m=\{\,i:\ (m,i)\in \texttt{country_set}\,\}$, with total order given by `rank` (0 = home). **S9 never infers order from egress.**
* Egress row count operator: $\#\text{rows}_{(m,i)} := |\{ \text{rows in `outlet_catalogue` for }(m,i)\}|$. Then $n_{m,i}=\#\text{rows}_{(m,i)}$.
* Conservation identity (checked exactly in S9.4): $\sum_{i\in\mathcal{I}_m} n_{m,i} = N^{\mathrm{raw}}_m$.
* Residual reproducibility (S9.4): Sort $R_{m,i}$ **descending** (secondary key = ISO lexicographic) to recover the deterministic $r_{m,i}$ order used by integerisation.

---

## Dataset / column ↔ symbol table (compact)

* `outlet_catalogue.manifest_fingerprint` → run fingerprint (hex64) for every row.
* `outlet_catalogue.merchant_id` $=$ $m$; `outlet_catalogue.legal_country_iso` $=$ $i$; `outlet_catalogue.site_order` $=$ $s_{m,i,k}$; `outlet_catalogue.site_id` $=$ $\text{id}_{m,i,k}$.
* `outlet_catalogue.single_vs_multi_flag` $=$ $H_m$; `outlet_catalogue.raw_nb_outlet_draw` $=$ $N^{\mathrm{raw}}_m$ (on the home row).
* `ranking_residual_cache_1A.residual` $=$ $R_{m,i}$; `residual_rank` $=$ $r_{m,i}$.
* `country_set.rank` (0 = home; 1..K = foreign order) defines the ordered $\mathcal{I}_m$; **not present** in `outlet_catalogue`.

---

## Practical reminder for S9’s checks

* **Within-country order**: `site_order` must be exactly $\{1,\dots,n_{m,i}\}$; S9 will fail on gaps/dupes.
* **Cross-country order**: validated **only** against `country_set.rank`. Any implication of cross-country order from egress is a design violation.
* **RNG evidence**: S9 expects event streams for all labels referenced by the registry (e.g., `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`); absence is a structural failure.

---

# S9.3 — Structural validations (schemas, keys, FK)

All checks here are **must-pass**. Any violation aborts S9 and gets written as a reproducible diff into the bundle. Your draft bullets match the registry and schema contracts below.

## A) Schema conformance (authoritative refs + core column rules)

Validate each dataset against its schema pointer:

* **`outlet_catalogue`** → `schemas.1A.yaml#/egress/outlet_catalogue`
  PK = `["merchant_id","legal_country_iso","site_order"]`; sort keys mirror that tuple; **inter-country order is not encoded** here. Columns include:
  `manifest_fingerprint` matches `^[a-f0-9]{64}$`; `site_id` matches `^[0-9]{6}$`; `home_country_iso`/`legal_country_iso` are ISO-2 with FK to canonical ISO; `single_vs_multi_flag` boolean; `raw_nb_outlet_draw ≥ 1`; `final_country_outlet_count ≥ 0`; `site_order ≥ 1`.

* **`country_set`** → `schemas.1A.yaml#/alloc/country_set`
  PK = `["merchant_id","country_iso"]`; `rank` is an **int ≥ 0** (0 = home); ISO FK applies to `country_iso`. This table is the **only** authority for inter-country order.

* **`ranking_residual_cache_1A`** → `schemas.1A.yaml#/alloc/ranking_residual_cache`
  PK = `["merchant_id","country_iso"]`; residual in **\[0,1)** with `exclusiveMaximum: true`; ISO FK on `country_iso`.

The dataset dictionary fixes each dataset’s path/partitioning used by the validator loader:
`outlet_catalogue: data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…` (partitioning `["seed","fingerprint"]`);
`country_set: …/seed={seed}/parameter_hash={parameter_hash}/…`;
`ranking_residual_cache_1A: …/seed={seed}/parameter_hash={parameter_hash}/…`.

## B) Primary / unique keys (exact cardinality checks)

Enforce uniqueness of declared keys with **integer equality**:

$$
\big|\text{rows in } \texttt{outlet_catalogue}\big|
\stackrel{!}{=}
\big|\text{unique }(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})\big|.
$$

Replicate for `country_set` and `ranking_residual_cache_1A` using their PKs. Any deficit implies duplicates; any surplus indicates erroneous deduplication—both are **hard failures** recorded in `key_constraints.json`.

> Reminder: `outlet_catalogue`’s sort keys equal its PK (so an optional ordering check may assert rows are non-decreasing in that tuple), but **no cross-country ordering may be inferred** from this table. That order lives only in `country_set.rank`.

## C) Foreign keys & lineage guards

* **ISO FKs.** Every `legal_country_iso` and `home_country_iso` in egress, and every `country_iso` in both caches, must appear in the canonical ISO-3166 dataset named in the FK clauses of the schemas. Violations are **hard FK failures**.

* **Fingerprint discipline (egress).** `outlet_catalogue.manifest_fingerprint` must (i) match `^[a-f0-9]{64}$` **and** (ii) be **identical** to the partition’s `{fingerprint}` for **every row**. This ties every egress row to the validated run closure.

* **Partition sanity.** The validator also asserts that each dataset is read **only** from its dictionary-pinned path with the correct partition keys (`["seed","fingerprint"]` for egress; `["seed","parameter_hash"]` for caches). Mis-placement is a structural failure.

---

## Reference validator algorithm (structural pass/fail)

```
INPUT:
  seed, manifest_fingerprint, parameter_hash
  paths from dataset dictionary

# —— Load partitions (fail if missing/mis-partitioned)
OUT := read("outlet_catalogue", seed=seed, fingerprint=manifest_fingerprint)
CS  := read("country_set",      seed=seed, parameter_hash=parameter_hash)
RC  := read("ranking_residual_cache_1A", seed=seed, parameter_hash=parameter_hash)

# —— (A) Schema checks (JSON-Schema)
assert schema_validate(OUT, "#/egress/outlet_catalogue")
assert schema_validate(CS,  "#/alloc/country_set")
assert schema_validate(RC,  "#/alloc/ranking_residual_cache")

# —— (B) PK uniqueness (cardinality equality)
assert nrows(OUT) == nunique(OUT, ["merchant_id","legal_country_iso","site_order"])
assert nrows(CS)  == nunique(CS,  ["merchant_id","country_iso"])
assert nrows(RC)  == nunique(RC,  ["merchant_id","country_iso"])

# —— (C1) ISO-2 foreign keys (egress + caches)
ISO := read_canonical_iso()  # schemas.ingress.layer1.yaml#/iso3166_canonical_2024
assert set(OUT.home_country_iso).issubset(ISO.country_iso)
assert set(OUT.legal_country_iso).issubset(ISO.country_iso)
assert set(CS.country_iso).issubset(ISO.country_iso)
assert set(RC.country_iso).issubset(ISO.country_iso)

# —— (C2) Fingerprint discipline (egress)
assert all(OUT.manifest_fingerprint == manifest_fingerprint)
assert all(regex("^[a-f0-9]{64}$").matches(OUT.manifest_fingerprint))

# —— (C3) Partition sanity from dictionary
assert partition_keys(OUT) == ["seed","fingerprint"]
assert partition_keys(CS)  == ["seed","parameter_hash"]
assert partition_keys(RC)  == ["seed","parameter_hash"]

# Emit diffs for any failing asserts and abort S9 if any check fails.
```

Citations for the schema fields (regex/ranges/FKs), keys, and dictionary paths:

---

## What gets written on failure (bundle evidence)

* `schema_checks.json`: row-level violations per dataset with pointers to offending columns (e.g., `site_id pattern`, `raw_nb_outlet_draw min`).
* `key_constraints.json`: duplicate-key listings for the failing PK with example tuples.
* `diffs/`: when FKs fail, include the set difference between observed ISO codes and the canonical ISO table.

Once **S9.3** passes, S9 proceeds to **S9.4 (cross-dataset equalities)**—conservation, coverage, and residual-rank reproducibility—which are specified immediately after this section in your design.



# S9.4 — Cross-dataset invariants (exact equalities)

All equalities are performed with **integer/bit-exact** comparison on persisted values; decimals that originate from floating math are first **reconstructed deterministically** (Dirichlet gamma → weights) and then **quantised to 8 dp** exactly as in generation (see S7/S8 design), so the validator compares like-for-like. Inter-country order is **not encoded** in `outlet_catalogue` by policy; order lives only in `country_set.rank`.

---

## (1) Site count realisation (per merchant m, country i)

Let

* $n_{m,i}$ be the **declared** `final_country_outlet_count` (same across all rows for a fixed $(m,i)$),
* $\widehat n_{m,i}$ be the **materialised** row count for $(m,i)$,
* $\mathcal{S}_{m,i}=\{s_{m,i,k}\}_{k=1}^{\widehat n_{m,i}}$ the multiset of `site_order` values observed for $(m,i)$.

Checks:

$$
\boxed{\ \widehat n_{m,i} \;=\; n_{m,i}\ } \quad\text{and}\quad
\boxed{\ \mathcal{S}_{m,i}=\{1,2,\dots,n_{m,i}\}\ \text{(as a set)}\ }.
$$

Equivalently: no gaps or dupes in `site_order`; the per-row `final_country_outlet_count` equals the groupwise constant $n_{m,i}$. These are schema-level invariants restated as cross-row equalities.

---

## (2) Country-set coverage (per merchant m)

Let

* $\mathcal{I}^{\text{alloc}}_m=\{\,i:(m,i)\in\texttt{country_set}\,\}$ (all legal countries for $m$; `rank=0` marks home),
* $\mathcal{I}^{\text{egress}}_m=\{\,i:\widehat n_{m,i}>0\,\}$ (countries that actually have outlet rows).

Checks:

1. **Support inclusion** (rows only where legal): $\boxed{\ \mathcal{I}^{\text{egress}}_m \subseteq \mathcal{I}^{\text{alloc}}_m\ }$.
2. **Zero-count coverage** (legal even if zero): for every $i\in\mathcal{I}^{\text{alloc}}_m\setminus\mathcal{I}^{\text{egress}}_m$, assert that the allocation cache implies $n_{m,i}=0$ (i.e., floor-only and residual selection did not grant a unit).
3. **Home coherence**: exactly one home row in `country_set` with `is_home=true` and `rank=0`, and its ISO equals every egress row’s `home_country_iso` for merchant $m$.

*(Remark: “inter-country order” is carried **only** by `country_set.rank`; validators must not infer it from egress.)*

---

## (3) Allocation conservation (per merchant m)

Let $\mathcal{I}_m=\mathcal{I}^{\text{alloc}}_m$. Let $N^{\text{raw}}_m$ be the **NB draw before spread** (persisted on the home-country egress row). Check:

$$
\boxed{\ \sum_{i\in\mathcal{I}_m} n_{m,i} \;=\; N^{\text{raw}}_m\ }.
$$

This proves the integerised spread (S7) conserved mass from the NB acceptance in S2 through S8 write.

**Related single/multi consistency.** Additionally assert $H_m=\mathbf{1}\{N^{\text{raw}}_m\ge 2\}$ on every row for $m$ (because H is the hurdle outcome).

---

## (4) Largest-remainder reproducibility (per merchant m)

Reconstruct the **pre-integer allocations** deterministically and match the persisted **residual cache**:

**Inputs to reconstruction.**
One `dirichlet_gamma_vector` event for $m$ provides arrays $(\alpha_i,\,\gamma_i^{\text{raw}},\,w_i)$ for $i\in\mathcal{I}_m$, with $\sum_i w_i=1$ (schema enforces array alignment and near-unity). Read $N^{\text{raw}}_m$ from egress (home row). No new RNG is used.

**Deterministic reconstruction.**

$$
a_{m,i} = N^{\text{raw}}_m\,w_i,\qquad
f_{m,i}=\lfloor a_{m,i}\rfloor,\qquad
R^{\text{raw}}_{m,i}=a_{m,i}-f_{m,i}\in[0,1).
$$

Quantise **exactly** as in generation:

$$
R_{m,i}=\operatorname{round}_{8\text{dp}}\!\left(R^{\text{raw}}_{m,i}\right).
$$

Compute deficit $d = N^{\text{raw}}_m - \sum_i f_{m,i}$ (guaranteed $0\le d<|\mathcal{I}_m|$). Sort indices by the **stable key** $(R_{m,i}\ \text{desc},\ \text{ISO asc})$; assign **1-based** ranks $r_{m,i}$.

**Checks (against cache).**

$$
\boxed{\ R_{m,i}\ \text{equals}\ \texttt{ranking_residual_cache.residual}\ }\quad\text{and}\quad
\boxed{\ r_{m,i}\ \text{equals}\ \texttt{ranking_residual_cache.residual_rank}\ }.
$$

Domain guards: $R_{m,i}\in[0,1)$ and integer ranks as per schema. Any mismatch is a determinism failure.

---

## (5) Site-ID sequencing (per block (m,i))

Define $\sigma(j)=\text{zpad6}(j)\in\{000000,\dots,999999\}$. For each observed row with `site_order = k`:

$$
\boxed{\ \text{id}_{m,i,k}\ =\ \sigma(k)\ } \quad\text{and}\quad \boxed{\ k\in\{1,\dots,n_{m,i}\}\ }.
$$

Cross-check with one `sequence_finalize` event per $(m,i)$ with $n_{m,i}>0$: the event must exist; its **envelope counters do not advance** (S8 is RNG-free); and its metadata `(merchant_id, country_iso, n)` matches the block realised in egress. If any block has $n_{m,i}>999{,}999$, the build must have emitted `site_sequence_overflow` and aborted; presence of such a block in egress is a hard error.

---

## (6) Policy coherence (eligibility vs foreign rows)

Let $e_m=\texttt{crossborder_eligibility_flags.is_eligible}$.

**Corrected invariant (design-consistent):**

$$
\boxed{\ e_m=0\ \Rightarrow\ \sum_{i\neq \text{home}} n_{m,i}=0\ } \quad\text{and}\quad
\boxed{\ \sum_{i\neq \text{home}} n_{m,i}>0\ \Rightarrow\ e_m=1\ }.
$$

(*Note:* $H_m$ is the hurdle single/multi flag; many merchants with $e_m=0$ are **still multi-site domestically** (they passed S1 and reached S3). So we do **not** force $H_m=0$ here. This matches S3’s gate semantics: ineligible merchants skip ZTP/S4–S6 and remain domestic-only.)

---

## Minimal validator algorithm (language-agnostic)

```
INPUT  : outlet_catalogue (egress for seed,fingerprint),
         country_set (seed, parameter_hash),
         ranking_residual_cache_1A (seed, parameter_hash),
         dirichlet_gamma_vector events (seed, parameter_hash, run_id),
         crossborder_eligibility_flags (parameter_hash)

OUTPUT : pass/fail + diffs in validation bundle

1  # --- prep keyed views ---
2  E := group outlet_catalogue by (merchant_id, legal_country_iso)
       with fields: n_decl = first(final_country_outlet_count),
                    n_rows = count(*),
                    home_iso = first(home_country_iso),
                    H = first(single_vs_multi_flag),
                    Nraw = first(raw_nb_outlet_draw)
3  S := country_set keyed by (merchant_id) with sets:
       I_alloc(m) = { country_iso }, and unique home h(m) with rank=0
4  R := ranking_residual_cache_1A keyed by (merchant_id,country_iso)
       with residual, residual_rank
5  G := dirichlet_gamma_vector events keyed by (merchant_id) with arrays w_i

6  # --- (1) site count realisation ---
7  for each (m,i) in E:
8      assert E.n_rows == E.n_decl
9      assert site_order values are exactly {1..E.n_decl}

10 # --- (2) country-set coverage ---
11 for each m:
12     assert I_egress(m) := {i: (m,i) in E and E.n_rows>0}
13     assert I_egress(m) ⊆ I_alloc(m)
14     assert home_iso is constant in E(m,*) and equals h(m)
15     for i in I_alloc(m) \ I_egress(m): assert E.n_decl==0 (if present) or absent

16 # --- (3) conservation & hurdle coherence ---
17 for each m:
18     assert sum_i n_decl(m,i) over I_alloc(m) == Nraw(m)
19     assert H(m) == 1  iff  Nraw(m) >= 2

20 # --- (4) residual reproducibility ---
21 for each m with |I_alloc(m)| >= 1:
22     w := G.weights(m)   # schema guarantees sum w ≈ 1
23     align w to I_alloc(m) by ISO order
24     a_i := Nraw(m) * w_i
25     f_i := floor(a_i); R_raw := a_i - f_i
26     R_q  := round_to_8dp(R_raw)              # exact decimal rounding
27     sort I_alloc(m) by (R_q desc, ISO asc) to get rank r_i
28     for each i in I_alloc(m):
29         assert R_q == R.residual(m,i) and r_i == R.residual_rank(m,i)

30 # --- (5) site-id sequencing & events ---
31 for each (m,i) in E with n_decl>0:
32     assert site_id == zpad6(site_order) for all rows
33     assert a 'sequence_finalize' event exists for (m,i),
           with n == n_decl and envelope.before == envelope.after

34 # --- (6) policy coherence ---
35 for each m:
36     if crossborder_eligibility_flags.is_eligible(m) == 0:
37         assert sum_{i≠home(m)} n_decl(m,i) == 0
38     if sum_{i≠home(m)} n_decl(m,i) > 0:
39         assert crossborder_eligibility_flags.is_eligible(m) == 1
```

All diffs and counts are bundled under the run’s `fingerprint` path; `_passed.flag` equals the bundle hash upon success (hand-off precondition for 1B).

---

### Notes on numerics & evidence

* **Quantisation/ordering:** Residuals are rounded to **8 dp**, ties broken by **ISO lexicographic** order; this is the exact scheme used in S7 integerisation (deterministic).
* **Event linkage:** `dirichlet_gamma_vector` and `residual_rank` events provide the evidence trail for (4); `sequence_finalize` certifies that the $(m,i)$ block was written with the stated $n_{m,i}$ and that **no RNG** was consumed during sequencing (before==after).
* **Schema domains:** Types/ranges/regex/FKs used above come straight from the authoritative schemas (egress + caches).

---

# S9.5 — RNG determinism & replay checks

Let the master RNG be **Philox 2×64-10** with a 64-bit seed and a 128-bit counter. Every RNG event row carries the **common envelope** with `(seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi})`; the run-scoped audit log states the algorithm. Egress rows carry the `global_seed` so we can assert one-to-many equality to the audit seed.

## S9.5.1 Envelope identity (run → egress)

**Goal.** Show the run’s audited RNG identity matches *every* egress row.

Checks (all must pass):

1. **Algorithm**: `rng_audit_log.algorithm = "philox2x64-10"`.
2. **Seed**: `rng_audit_log.seed = outlet_catalogue.global_seed` for **all** rows in the `(seed, fingerprint)` partition.
3. **Lineage keys**: `rng_audit_log.parameter_hash = {parameter_hash}` and `rng_audit_log.manifest_fingerprint = {fingerprint}`, equal to the active partitions and the per-row `manifest_fingerprint`.

## S9.5.2 128-bit counter arithmetic & draw accounting (per label)

For each label $\ell$ (e.g., `gumbel_key`, `dirichlet_gamma_vector`, `gamma_component`, `poisson_component`, `residual_rank`, `sequence_finalize`, …), let the event trace $T_\ell$ be the chronologically ordered rows (same `substream_label=\ell`) with the common envelope. Let

$$
C^{\text{before}}_e = (\texttt{before_hi}_e \ll 64) + \texttt{before_lo}_e,\quad
C^{\text{after}}_e  = (\texttt{after_hi}_e \ll 64) + \texttt{after_lo}_e
$$

interpreted as unsigned 128-bit integers. The **observed advance** for the label is

$$
\Delta C_\ell \;=\; C^{\text{after}}_{\text{last}} - C^{\text{before}}_{\text{first}} \in \mathbb{Z}_{\ge 0}.
$$

From the **structured trace log**, each emitted draw record has a `draws` count (number of $(0,1)$ uniforms consumed). Define the **declared advance**

$$
D_\ell \;=\; \sum_{e\in \texttt{rng_trace_log}:\ \text{substream_label}=\ell} e.\texttt{draws}.
$$

The check is

$$
\boxed{\ \Delta C_\ell \stackrel{!}{=} D_\ell\ } \quad\text{for every label }\ell,
$$

and (optional) **adjacency**: for consecutive events $e_j,e_{j+1}\in T_\ell$, assert $C^{\text{after}}_{e_j} \le C^{\text{before}}_{e_{j+1}}$ with equality iff the intervening `draws=0` (e.g., non-consuming events). `rng_trace_log` schema provides `draws`; non-consuming events still carry the envelope (before=after).

> Note: A rare `stream_jump` may advance counters without draws; the validator adds the **sum of jump strides** (from `stream_jump.jump_stride_{lo,hi}`) to $D_\ell$ before comparing to $\Delta C_\ell$.

## S9.5.3 Event cardinalities (must match process logic)

Compute **expected** counts from deterministic inputs and realized outputs, then compare to **observed** counts by label:

* **`gumbel_key`** — exactly **one** event per (merchant, **candidate foreign** country) used in top-$K$ selection; payload includes `(weight,u,key,selected,selection_order)`. (Open-interval `u01` enforced by schema.)
* **`dirichlet_gamma_vector`** — **one** vector event per merchant **iff** $|C|=K{+}1>1$; none when $K=0$ (domestic-only path). Arrays `(country_isos,alpha,gamma_raw,weights)` must be aligned and weights sum to 1 within tolerance.
* **`residual_rank`** — exactly **$|C|$** events per merchant (including $|C|=1$ domestic); no RNG consumption (counters do **not** advance).
* **NB composition** (`gamma_component`, `poisson_component`) — **two** events per NB **attempt**; `nb_final` **exactly once** at acceptance; attempts ≥1 (enforce per-attempt discipline).
* **`sequence_finalize`** — exactly **one** per $(m,i)$ with $n_{m,i}>0$; **zero** draws (before=after). Also assert the total equals $\sum_i \mathbf{1}\{n_{m,i}>0\}$, and its payload `(site_count)` equals $n_{m,i}$.

Paths, partitioning and schema pointers for these labels are fixed by the **dataset dictionary** and artefact registry; the validator cross-checks existence under `seed, parameter_hash, run_id`.

## S9.5.4 Replay spot-checks (payload re-derivation)

Pick a **deterministic sample** of merchants (e.g., hash of `(merchant_id ⊕ seed ⊕ fingerprint)` mod $M$) and for each sampled case:

1. **Recompute Gumbel keys.** From the event’s `rng_counter_before` and the run seed, regenerate the required uniforms $u\in(0,1)$ and apply the **schema-declared transform** $z=\log w - \log(-\log u)$; compare the logged `u` and `key=z` bit-for-bit. (`u` must satisfy the `u01` primitive.)

2. **Recompute Dirichlet gammas.** From `dirichlet_gamma_vector`’s envelope start counter, regenerate $\gamma_i\sim\Gamma(\alpha_i,1)$ in the same array order, re-normalise to `weights`; compare to the logged `gamma_raw`/`weights` arrays (length equality and sum-to-one constraint).

Abort on the **first** mismatch and write a reproducer: the exact `(seed, before_counter_hi, before_counter_lo, substream_label)` plus the module name and merchant id.

---

## Minimal validator algorithm (language-agnostic)

```
INPUT:
  rng_audit_log, rng_trace_log
  rng event streams: gumbel_key, dirichlet_gamma_vector, residual_rank,
                     gamma_component, poisson_component, nb_final,
                     sequence_finalize, stream_jump
  outlet_catalogue (for global_seed), country_set (for |C| and candidates)

# --- S9.5.1 Envelope identity ---
assert rng_audit_log.algorithm == "philox2x64-10"
assert rng_audit_log.seed == all_unique(outlet_catalogue.global_seed)
assert rng_audit_log.parameter_hash == {parameter_hash}
assert rng_audit_log.manifest_fingerprint == {fingerprint}
assert all(outlet_catalogue.manifest_fingerprint == {fingerprint})

# --- S9.5.2 Draw accounting (per label) ---
for each label ℓ:
    Tℓ := events with substream_label==ℓ ordered by ts_utc
    Cbefore := first(Tℓ).counter_before_hi<<64 | counter_before_lo
    Cafter  :=  last(Tℓ).counter_after_hi <<64 | counter_after_lo
    ΔC := Cafter - Cbefore

    D := sum(draws over rng_trace_log where substream_label==ℓ)
    J := sum(jump_stride over stream_jump where substream_label==ℓ)  # optional
    assert ΔC == D + J

    # adjacency monotonicity
    assert for all consecutive e: e.after <= next.before
    # equality iff draws==0 (non-consuming)

# --- S9.5.3 Cardinalities ---
for each merchant m:
    M_candidates := |candidate foreign set|  # from S6 inputs
    assert count(gumbel_key for m) == M_candidates
    if |C_m|>1: assert exists exactly 1 dirichlet_gamma_vector for m
    assert count(residual_rank for m) == |C_m|
    NB_attempts := count(gamma_component for m) == count(poisson_component for m)
    assert count(nb_final for m) == 1
    for each (m,i) with n_{m,i}>0:
        assert exists exactly 1 sequence_finalize with site_count == n_{m,i}

# --- S9.5.4 Replay spot-checks (deterministic sample) ---
S := deterministic_sample_of_merchants(seed, fingerprint)
for m in S:
    # Gumbel
    for a few i in candidates(m):
        u_regen := philox_u01(seed, counter_before_of_event(m,i,"gumbel_key"))
        key_regen := log(weight(m,i)) - log(-log(u_regen))
        assert approx_equal(u_regen, logged.u) and approx_equal(key_regen, logged.key)

    # Dirichlet
    if |C_m|>1:
        gammas := philox_gamma_vector(seed, counter_before_of_event(m,"dirichlet_gamma_vector"), alpha(m))
        weights := gammas / sum(gammas)
        assert arrays_equal(weights, logged.weights) and arrays_equal(gammas, logged.gamma_raw)
```

Schemas that back these checks: **rng envelope**, **rng_audit_log**, **rng_trace_log**, and event schemas for `gumbel_key`, `dirichlet_gamma_vector`, `sequence_finalize`, plus NB event streams (`gamma_component`, `poisson_component`, `nb_final`) and ZTP diagnostics; all are catalogued by the registry & dictionary with fixed paths/partitions.

## Notes & corner cases

* **Non-consuming events.** `residual_rank` and `sequence_finalize` consume **zero** uniforms; envelopes must satisfy `before == after`. These are still required for lineage.
* **Open-interval uniforms.** Any logged `u` must satisfy the `u01` primitive: $u\in(0,1)$. Breaches are hard schema failures.
* **NB attempts & ZTP.** S2 enforces exactly one `nb_final` after ≥1 attempts; if the ZTP branch is used elsewhere (foreign count), corresponding `ztp_*` diagnostics must reconcile attempts vs. accepts.

On success, we write `rng_accounting.json` (per-label counts, advances, spot-check results) into the **validation bundle** that authorizes the 1A→1B hand-off for this fingerprint.

---



# S9.6 — Statistical corridors (release-time sanity)

**Purpose.** Quantify four governed sanity checks (hurdle calibration, integerization fidelity, sparsity behavior, ZTP acceptance) and **gate release** on their thresholds. All metrics are written into the **validation bundle** keyed by `{fingerprint=manifest_fingerprint}`; 1B is authorized only if the bundle passes and `_passed.flag` matches its hash.

---

## (1) Hurdle calibration (optional)

Let \$\mathcal{M}\$ be the merchant universe in the egress partition. Define the **empirical multi-site rate**

$$
\widehat{\pi} \;=\; \frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}} H_m,
$$

with \$H_m=\texttt{single_vs_multi_flag}\in{0,1}\$ read from `outlet_catalogue` (home-country row per \$m\$). When the optional cache `hurdle_pi_probs` is present, join on `merchant_id` and compute the **model-implied mean**

$$
\bar{\pi}\;=\;\frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}}\pi_m,
$$

then assert the **gap corridor**

$$
\boxed{\;|\widehat{\pi}-\bar{\pi}|\ \le\ \varepsilon_\pi\;}\quad(\varepsilon_\pi=0.02\text{ by default}).
$$

Both \$\widehat{\pi}\$ and \$\bar{\pi}\$ and the absolute deviation are persisted to the bundle metrics. The cache identity and schema are fixed as `schemas.1A.yaml#/model/hurdle_pi_probs`.

**Diagnostics (non-gating, recorded).** Add a **Wilson 95% CI** for \$\widehat{\pi}\$ to help triage drift:

$$
\widehat{\pi}_{\text{Wilson}} \pm 1.96\sqrt{\frac{\widehat{\pi}(1-\widehat{\pi})}{|\mathcal{M}|+3.84}},
$$

plus the standardized gap \$z=(\widehat{\pi}-\bar{\pi})/\sqrt{\bar{\pi}(1-\bar{\pi})/|\mathcal{M}|}\$ (report only; corridor remains absolute gap as above).

---

## (2) Integerization fidelity (largest-remainder)

For each merchant \$m\$, S7 turns **pre-integer shares** \$q_{m,i}\$ (the Dirichlet-or-deterministic weights used for the spread) into integer site counts \$n_{m,i}\$ with **largest-remainder** while conserving the accepted NB draw \$N^{\text{raw}}_m\$ (from the home row). Validation recomputes:

* **Conservation identity (hard):**

$$
\sum_{i\in\mathcal{I}_m} n_{m,i} \;=\; N^{\text{raw}}_m
$$

and that `site_order` is a permutation \$1..n_{m,i}\$ (done in §S9.4).

* **Per-merchant L1 rounding error (numerical guard, soft → configurable hard):**

$$
\Delta_m \;=\; \sum_{i\in\mathcal{I}_m}\left|\frac{n_{m,i}}{N^{\text{raw}}_m}-q_{m,i}\right|.
$$

Require

$$
\boxed{\ \max_{m}\Delta_m\ \le\ \varepsilon_{\text{LRR}}\ }\qquad(\varepsilon_{\text{LRR}}=10^{-12}\text{ by default}).
$$

Here \$q_{m,i}\$ is rebuilt **deterministically** from the authoritative inputs used by 1A (Dirichlet weights for the realized country order, or the deterministic fallback), and the **residual cache** is cross-checked in §S9.4 to ensure the same fractional parts and ranks were used in integerization.

**Notes.** Equalities are tested in integer/bit space; \$\Delta_m\$ is computed in binary64 with Kahan-style summation (deterministic CPU order) and reported. Any conservation failure is **hard fail** regardless of \$\varepsilon_{\text{LRR}}\$.

---

## (3) Sparsity behavior (currency-level)

From `sparse_flag/parameter_hash={parameter_hash}` (PK `currency`, columns `is_sparse, obs_count, threshold`), compute the **empirical sparsity rate**

$$
\widehat{\rho}\;=\;\frac{1}{|\mathcal{K}|}\sum_{\kappa\in\mathcal{K}}\mathbf{1}\{\texttt{is_sparse}(\kappa)=1\}.
$$

The **expected rate** \$\rho_{\text{expected}}\$ is implied by your policy “equal-split fallback iff \$Y\<T\$” (equivalently \$\tilde{Y}\<T+\alpha D\$), given the reference distribution of \$Y\$; S9 simply consumes the configured bound and asserts

$$
\boxed{\;|\widehat{\rho}-\rho_{\text{expected}}|\ \le\ \varepsilon_\rho\;}
$$

and records \$(\widehat{\rho},\rho_{\text{expected}},\varepsilon_\rho)\$ in the bundle. The dataset identity and semantics are fixed by `schemas.1A.yaml#/prep/sparse_flag` and S5’s construction.

---

## (4) ZTP acceptance (foreign-count \$K\$)

S4 draws \$K\$ via **rejection from Poisson(λ)** until \$K\ge1\$ (or a hard cap at 64 attempts), logging **every** `poisson_component(context="ztp")` and every rejection as `ztp_rejection`. By design, the **per-attempt acceptance probability** is

$$
a(\lambda)\;=\;1-e^{-\lambda}.
$$

We validate the **system acceptance** in two ways:

**(4a) Empirical acceptance rate over attempts (gating).**
Let \$A\$ be the count of accepting attempts (exactly the number of merchants that succeeded, since there is one acceptance per successful merchant) and \$T\$ the **total attempts** across eligible merchants (rejections + acceptances; aborted merchants contribute 64 rejections and 0 acceptances). Then

$$
\widehat{a}\;=\;\frac{A}{T}.
$$

Assert the corridor

$$
\boxed{\;a_L\ \le\ \widehat{a}\ \le\ a_U\;}
$$

with \$(a_L,a_U)\$ configured and recorded. (CI also watches S4’s own gates on mean rejections and high-percentile attempts.)

**(4b) Model-implied acceptance (recorded).**
Rebuild \$\lambda_{\text{extra},m}\$ from S4 inputs (\$N_m\$, openness \$X_m\$, hyper-parameters \$\theta\$) and compute

$$
\bar{a}\;=\;\frac{1}{|\mathcal{M}_{\text{elig}}|}\sum_{m\in\mathcal{M}_{\text{elig}}}\bigl(1-e^{-\lambda_{\text{extra},m}}\bigr).
$$

Report \$(\widehat{a},\bar{a},\widehat{a}-\bar{a})\$; **do not gate** on the difference (to avoid double-penalizing modelling drift—the primary gate is the operational corridor). All events, contexts, and caps (64) are fixed by your S4 spec and RNG schemas.

**CI parity.** S4 also stipulates: mean `ztp_rejection` count per merchant < 0.05, and \$p_{99.9}<3\$; S9 reads and mirrors these as part of the metrics table and will **hard-fail** if violated.

---

## Reference algorithm (language-agnostic)

```
INPUT:
  outlet_catalogue(seed, fingerprint),            # schema: #/egress/outlet_catalogue
  country_set(seed, parameter_hash),              # schema: #/alloc/country_set
  ranking_residual_cache_1A(seed, parameter_hash) # schema: #/alloc/ranking_residual_cache
  sparse_flag(parameter_hash),                    # schema: #/prep/sparse_flag
  [optional] hurdle_pi_probs(parameter_hash),     # schema: #/model/hurdle_pi_probs
  rng events: poisson_component(context="ztp"), ztp_rejection, ztp_retry_exhausted
  hyperparams θ, openness X_m as per artefacts used in S4

OUTPUT:
  metrics.csv in validation bundle; pass/fail decision

1  # HURDLE
2  M := merchants in outlet_catalogue (home-country row per m)
3  π_hat := mean(outlet_catalogue.single_vs_multi_flag on home rows)
4  if hurdle_pi_probs exists:
5      π_bar := mean(hurdle_pi_probs.pi over M)
6      assert abs(π_hat - π_bar) <= ε_π
7      record (π_hat, π_bar, abs diff, Wilson CI)

8  # INTEGERIZATION FIDELITY
9  for each merchant m:
10     Nraw := home-row raw_nb_outlet_draw
11     n_mi := counts per legal_country_iso from outlet_catalogue
12     assert sum_i n_mi == Nraw                         # exact
13     q_mi := recomputed pre-integer shares (Dirichlet/deterministic) in S7 order
14     Δ_m := sum_i | n_mi / Nraw - q_mi |
15  assert max_m Δ_m <= ε_LRR
16  record max, p50, p99 of Δ_m

17  # SPARSITY RATE
18  ρ_hat := mean(sparse_flag.is_sparse over currencies κ)
19  assert abs(ρ_hat - ρ_expected) <= ε_ρ
20  record (ρ_hat, ρ_expected, abs diff)

21  # ZTP ACCEPTANCE
22  T := total number of poisson_component(context="ztp") events
23  A := |{ merchants with at least one accepted K >= 1 }|
24  â := A / T
25  assert a_L <= â <= a_U
26  # optional model-implied
27  if θ, X_m available:
28      λ_m := exp(θ0 + θ1 log N_m + θ2 X_m) for eligible m
29      a_bar := mean(1 - exp(-λ_m))
30      record (â, a_bar, â - a_bar)

31  write all metrics + thresholds into bundle; sign; create _passed.flag on success
```

**Where the contracts come from.** Egress primary keys and semantics (no inter-country order in egress), `country_set` as the **only** carrier of cross-country order, residual cache semantics, RNG event schemas (`gumbel_key`, `dirichlet_gamma_vector`, `poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`), and the S4 ZTP procedure and caps are all already fixed in your schemas, dataset dictionary, and state-flow specs; S9.6 only **reads** and checks them.

---

## Failure semantics (for S9.6 gates)

* **Hard fail:** any corridor breach in (1)–(4); conservation failure (caught in §S9.4); schema/lineage violations elsewhere. Bundle materializes with a reproducible diff; `_passed.flag` is **not** written.
* **Recorded only (non-gating):** Wilson CI, \$z\$-score for hurdle gap, \$\widehat{a}-\bar{a}\$ for ZTP. These are captured in `metrics.csv` to aid drift triage but do **not** change pass/fail.

---

# S9.7 — Bundle contents & signing (deep dive)

## What the bundle is

A **ZIP archive** written at
`data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
whose internal **index** (`index.json`) conforms to `schemas.1A.yaml#/validation/validation_bundle`. The bundle is the single audit artifact that certifies this fingerprinted egress; its presence + matching flag authorise 1A→1B hand-off.

### Minimal required contents (logical)

* `index.json` — **table of artefacts** (plots/tables/diffs/summaries) per the index schema (PK `artifact_id`, columns: `kind`, `path`, `mime`, `notes`).
* `schema_checks.json` — per-dataset JSON-Schema results (pass/fail + row-level violations).
* `key_constraints.json` — PK/UK/FK uniqueness and FK set-difference proofs.
* `rng_accounting.json` — per-label draw accounting and replay spot-check outcomes.
* `metrics.csv` — corridor metrics (π gap, ZTP acceptance, sparsity rate, largest-remainder max error, etc.).
* `diffs/` — directory containing reproducible diffs (e.g., residual-rank mismatch listings).

The dataset dictionary binds the **bundle’s location, partitioning, and schema ref**: the **format is `zip`**, partition key is `fingerprint`, schema ref is `schemas.1A.yaml#/validation/validation_bundle`.

---

## Index schema (inside the ZIP)

`index.json` must realise the `validation_bundle.index_schema` table:

* Primary key: `artifact_id` (string).
* Columns:
  `kind ∈ {plot, table, diff, text, summary}`,
  `path` (relative path within the ZIP),
  `mime` (optional),
  `notes` (optional).

Typical entries:

* `("schema_checks","table","schema_checks.json","application/json","JSON-Schema results")`
* `("rng_accounting","table","rng_accounting.json","application/json",null)`
* `("corridor_metrics","table","metrics.csv","text/csv","Release gates & thresholds")`
* `("residual_diffs","diff","diffs/residual_rank_mismatch.csv","text/csv","Exact mismatches")`

---

## Signing & `_passed.flag` (self-verification)

After producing the ZIP **bytes** $B$, compute

$$
\boxed{H\;=\;\mathrm{SHA256}(B)}.
$$

Write `_passed.flag` **in the same folder**; its **digest equals the bundle’s SHA-256** (registry contract). This flag is the only thing 1B trusts to authorise consumption of `outlet_catalogue(seed,fingerprint)`.

* Registry entries fix both artefacts:

  * `validation_bundle_1A` at `…/validation/fingerprint={manifest_fingerprint}/` (digest is the bundle hash).
  * `validation_passed_flag` at `…/_passed.flag` (digest recorded as `{sha256_of_bundle}`; depends on the bundle).

**Hand-off contract.** 1B **may read** `outlet_catalogue(seed,fingerprint)` **iff** `_passed.flag` exists **and** its digest equals the bundle’s SHA-256. Cross-country order remains **only** in `country_set.rank` and must be joined by 1B.

---

## Reproducibility & layout rules

* **Canonical packaging.** Zip entries use **UTF-8** names; sort **lexicographically** by `path` before writing, and store with stable compression (e.g., DEFLATE level fixed) to ensure identical bytes across replays; this stabilises $H$. (The index is the authoritative map regardless.)
* **Provenance.** Include in `index.json.notes` (or a `README.txt`) the run lineage: `(seed, parameter_hash, manifest_fingerprint, run_id)` and validator code commit. The artefact registry already keys these identities per path.
* **No mutation.** Both the egress and the bundle directory are treated as **immutable** for a fingerprint; S9 writes only within `…/validation/fingerprint={manifest_fingerprint}/`.

---

## Minimal reference algorithm (pack & sign)

```
INPUT:
  fingerprint, seed, parameter_hash, run_id
  payloads: schema_checks.json, key_constraints.json,
            rng_accounting.json, metrics.csv, diffs/*

OUTPUT:
  data/layer1/1A/validation/fingerprint={fingerprint}/bundle.zip
  data/layer1/1A/validation/fingerprint={fingerprint}/_passed.flag

1  # Build index rows (artifact_id, kind, path, mime, notes)
2  IDX := [
       ("schema_checks","table","schema_checks.json","application/json",null),
       ("key_constraints","table","key_constraints.json","application/json",null),
       ("rng_accounting","table","rng_accounting.json","application/json",null),
       ("corridor_metrics","table","metrics.csv","text/csv",null)
    ] + [("diff_"+name,"diff","diffs/"+name,"text/csv",null) for name in list_diffs()]

3  # Write index.json according to schemas.1A.yaml#/validation/validation_bundle.index_schema
4  assert schema_validate(IDX, "validation_bundle.index_schema")            # table-oriented

5  # Canonicalize ZIP: sort by 'path'; fixed compression level
6  B := zip_bytes( ["index.json"] + [row.path for row in IDX] )

7  # Sign: compute SHA-256 over the ZIP bytes
8  H := sha256_hex(B)  # lowercase hex

9  # Persist bundle & flag
10 write_file(".../validation/fingerprint={fingerprint}/bundle.zip", B)
11 write_text(".../validation/fingerprint={fingerprint}/_passed.flag", H)

12 # (Optional) Write a tiny sidecar manifest.json carrying lineage keys for convenience
```

Paths and contracts for `validation_bundle_1A` and `_passed.flag` are fixed by the artefact registry & data dictionary; 1B’s loader is allowed to proceed **only** when the flag’s digest matches the bundle’s hash.

---

## What 1B should verify on read (defence in depth)

* `_passed.flag` exists and equals `SHA256(bundle.zip)`.
* `index.json` conforms to the bundle index schema.
* The egress partition being consumed is exactly `seed={seed}/fingerprint={fingerprint}` referenced by the bundle; **never** infer cross-country order from egress—join `country_set.rank`.

That’s the full **bundle & signing** spec wired to your registry, dictionary, and schema pointers.


# S9.8 — Failure semantics (expanded)

## Severity classes & what happens

### Hard fail (release blocked)

Trigger conditions (any one ⇒ **no hand-off**):

1. **Structural / schema:** any JSON-Schema violation in `outlet_catalogue`, `country_set`, or `ranking_residual_cache_1A`; partition/key misuse (wrong `{seed,fingerprint}` or `{seed,parameter_hash}`), PK/UK duplicates, or ISO FK breaches. Evidence goes to `schema_checks.json` and `key_constraints.json`. `_passed.flag` is **not** written.

2. **Lineage / RNG:** audit envelope mismatch (algo, seed, lineage keys), missing required RNG streams, counter-advance ≠ declared draws, or any **replay** mismatch in the spot-checks (e.g., Gumbel key or Dirichlet gamma arrays not regenerating from `(seed,counter)`). Evidence goes to `rng_accounting.json` with per-label deltas and reproducer tuples.

3. **Cross-dataset equalities:** conservation failure

$$
\sum_i n_{m,i}\neq N_m^{\text{raw}}
$$

for any $m$; country-set coverage/home-ISO contradictions; or site-ID/sequence inconsistencies (`site_id ≠ zpad6(site_order)` or missing `sequence_finalize`). These are **must-pass** equalities; diffs are written under `diffs/`.

4. **Statistical corridors:** any corridor outside configured bounds (hurdle gap, integerization L1 guard, sparsity rate gap, ZTP acceptance corridor). Metrics recorded in `metrics.csv`; corridor breach ⇒ hard fail.

**Bundle behavior.** Even on hard fail, the validator still emits the **ZIP bundle** with full diagnostics (`index.json`, tables, diffs). It **does not** write `_passed.flag`. 1B must not consume the egress without a matching flag for this `fingerprint` (registry contract).

---

### Soft warn (release policy can escalate)

Non-structural numerical guards that do **not** contradict exact contracts, e.g.:

* Largest-remainder L1 guard $\Delta_m$ exceeding $\varepsilon_{\text{LRR}}$ **while conservation holds** and residual cache matches. Recorded as a **warning** in `metrics.csv`; release policy may promote to hard fail if desired.

* Optional inputs absent (e.g., `hurdle_pi_probs` not materialised): hurdle calibration is **skipped**; no fail is raised (flag stays governed by the remaining corridors). The bundle notes “metric not evaluated”.

---

## Canonical decision routine

```
INPUT :
  results = {
    schema_pass, keys_pass, fk_pass,
    rng_envelope_pass, rng_accounting_pass, rng_replay_pass,
    eq_conservation_pass, eq_coverage_pass, eq_site_id_pass,
    corridors_pass, soft_warnings[]  # list of (code, detail)
  }

# Hard-fail if any mandatory gate failed
if not (schema_pass and keys_pass and fk_pass):
    return FAIL("structural"), write_bundle(no_flag)

if not (rng_envelope_pass and rng_accounting_pass and rng_replay_pass):
    return FAIL("rng_lineage"), write_bundle(no_flag)

if not (eq_conservation_pass and eq_coverage_pass and eq_site_id_pass):
    return FAIL("cross_dataset_equalities"), write_bundle(no_flag)

if not corridors_pass:
    return FAIL("corridors"), write_bundle(no_flag)

# Otherwise success: bundle + signed flag
write_bundle(zip_bytes); write_passed_flag(sha256(bundle))
return PASS(with soft_warnings)
```

* `write_passed_flag(H)` writes `_passed.flag` whose **content equals** the bundle’s SHA-256; 1B authorises consumption only when the flag exists and matches.

---

## Error taxonomy (machine codes & evidence)

| Class           | Code                             | Typical trigger                                              | Evidence artefact(s)                                   |
| --------------- | -------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------ |
| Structural      | `schema_violation`               | bad regex (`site_id`), out-of-range counts, wrong partition  | `schema_checks.json`, dataset path from dictionary     |
| Keys/FK         | `pk_duplicate`, `fk_iso_missing` | duplicate PK tuple; ISO not in canonical table               | `key_constraints.json`, FK set difference              |
| RNG envelope    | `rng_envelope_mismatch`          | audit: seed/algo/fingerprint/parameter_hash mismatch        | `rng_accounting.json` header                           |
| Draw accounting | `counter_advance_mismatch`       | $\Delta C_\ell \ne \sum \text{draws}$ (± jumps)              | per-label section in `rng_accounting.json`             |
| Replay          | `replay_payload_mismatch`        | regenerated Gumbel key or gamma vector disagrees             | `rng_accounting.json` with reproducer `(seed,counter)` |
| Equalities      | `mass_not_conserved`             | $\sum_i n_{m,i}\ne N^{\text{raw}}_m$                         | `diffs/conservation.csv`                               |
| Equalities      | `country_set_incoherent`         | egress rows outside `country_set`; home mismatch             | `diffs/coverage.csv`                                   |
| Sequencing      | `site_id_mismatch`               | `site_id` ≠ `zpad6(site_order)`; missing `sequence_finalize` | `diffs/sequence.csv`                                   |
| Corridors       | `corridor_breach_*`              | hurdle gap, ZTP, sparsity, or LRR guard exceeded             | `metrics.csv` with thresholds                          |

All artefact types and the signing/flag contract are enumerated in your S9.7 bundle spec and artefact registry.

---

## Operator guidance (remediation)

* **Schema/keys/FK:** regenerate offending dataset partition(s) under the correct path/partition keys; fix ISO source or mapping; re-run S9.
* **RNG lineage:** verify substream labels present per registry, counter strides, and any `stream_jump` handling; fix producer to log correct `draws`/envelopes; re-emit streams and re-validate.
* **Conservation / coverage:** check S7 integerisation (residual quantisation + ISO tiebreak) and S8 write order; ensure `country_set` truly remains sole authority for cross-country order.
* **Corridors:** inspect drift dashboards for hurdle or ZTP stats; adjust thresholds only via governed config (never inline).

---

## Release invariant (re-stated)

For a given `fingerprint`, **either** you have **(bundle, `_passed.flag`)** and 1B may read `outlet_catalogue(seed,fingerprint)` **or** you have a bundle **without** the flag and release is blocked. No other state is valid.

This nails the failure semantics and ties each outcome to the evidence stored in the signed bundle and the `_passed.flag` contract.

---

# S9.9 — Hand-off to 1B (contract)

## Preconditions (gate to consume 1A)

For a fixed run lineage, 1B is authorised to read 1A’s egress **iff** the validator produced:

* a **bundle** at `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/bundle.zip`, and
* a **_passed.flag** in the same folder whose **contents equal** `SHA256(bundle.zip)`.

These artefacts and their digests are defined in the registry as `validation_bundle_1A` and `validation_passed_flag`. 1B must verify the flag–bundle digest equality before any read.

---

## What 1B reads (and what it must join)

* **Egress (immutable):**
  `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}` with schema `schemas.1A.yaml#/egress/outlet_catalogue`. **Within-country** sequence only (`site_order`), PK = `["merchant_id","legal_country_iso","site_order"]`. **Inter-country order is intentionally not encoded here.**

* **Country order (authoritative):**
  `country_set/seed={seed}/parameter_hash={parameter_hash}` with schema `#/alloc/country_set`. Column `rank` carries **cross-country order** (`0=home; 1..K` foreigns). 1B **must** join this to obtain inter-country sequencing.

This separation (order **only** in `country_set.rank`) is also locked by the **Schema Authority Policy** and reiterated in the state-flow spec.

---

## How 1B discovers the datasets

1B should resolve paths and schemas from the **artefact registry** / **data dictionary** entries:

* `outlet_catalogue`: cross-layer dataset, path `…/seed={seed}/fingerprint={manifest_fingerprint}/`, `schema: schemas.1A.yaml#/egress/outlet_catalogue`.
* `country_set`: path `…/seed={seed}/parameter_hash={parameter_hash}/`, `schema: schemas.1A.yaml#/alloc/country_set`. The dictionary explicitly states it is the **only** authority for cross-country order.

> **Scope note.** `outlet_catalogue` is keyed by `{seed,fingerprint}`, while `country_set` is keyed by `{seed,parameter_hash}`. 1B must know **both** `fingerprint` (from the release to consume) **and** `parameter_hash` (the parameter bundle used by 1A) to join correctly. Do **not** infer `parameter_hash` from egress rows (it’s not a partition key there).

---

## Minimal consumption contract (reference routine)

```
INPUT  : seed, manifest_fingerprint, parameter_hash
PRECOND: verify_pass_flag(fingerprint)  # SHA256(bundle.zip) == contents(_passed.flag)

# Load with schema refs from dictionary
OUT := read("outlet_catalogue", seed=seed, fingerprint=manifest_fingerprint)
CST := read("country_set",      seed=seed, parameter_hash=parameter_hash)

# Sanity (defence-in-depth; should already be proven by S9):
assert pattern_hex64(OUT.manifest_fingerprint) and all_equal(OUT.manifest_fingerprint, manifest_fingerprint)
assert unique_key(OUT, ["merchant_id","legal_country_iso","site_order"])

# Join to get inter-country order
J := OUT
     JOIN CST
       ON (OUT.merchant_id = CST.merchant_id
           AND OUT.legal_country_iso = CST.country_iso)

# 1B must use:
# - CST.rank for inter-country sequencing
# - OUT.site_order for within-country sequencing
# Never infer cross-country order from OUT alone.
```

All column names and semantics (`site_order` = within-country sequence; `rank` = cross-country order) are fixed by the schema authority policy and schemas.

---

## Invariants 1B must preserve

* **Immutability of 1A egress.** 1B does **not** mutate or rewrite `outlet_catalogue`; it only **reads** it after a passing bundle.
* **Ordering discipline.** Any 1B output that needs country sequencing must order by `(merchant_id, rank, site_order)` after the join; within each `(merchant,country)` block, preserve `site_order` and the 6-digit `site_id` (z-padded mapping of `site_order`).
* **Schema fidelity.** Respect the egress PK and the country-set FK to canonical ISO; those contracts were validated in S9 and must remain true downstream.

---

## Recap (aligned to your section)

* **Inputs:** `outlet_catalogue(seed,fingerprint)`, `country_set(seed,parameter_hash)`, `ranking_residual_cache_1A(seed,parameter_hash)`, `hurdle_pi_probs(parameter_hash)` (opt), `sparse_flag(parameter_hash)`, `crossborder_eligibility_flags(parameter_hash)`, RNG audit + event logs, lineage keys. (S9 listed these as read-only.)
* **Outputs:** `validation_bundle_1A(fingerprint)` (ZIP with `index.json`) and `_passed.flag = SHA256(bundle)`. Presence & digest match are the **sole authorisation** for 1B to consume the `(seed,fingerprint)` egress.

That’s the exact 1A→1B contract: pass-flag-gated read of `outlet_catalogue`, **mandatory** join to `country_set` for cross-country order, and discovery via registry/dictionary pointers.
