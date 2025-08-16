# S8.1 — State, notation & row model

## Scope

Fix the **authorities**, **symbols**, and the **per-row contract** for the egress dataset **`outlet_catalogue`**. This section does not consume RNG; it establishes exactly what inputs S8 needs and what a row means so that S8.2 can expand rows deterministically.

---

## 1) Authorities & lineage (must-use inputs)

**Lineage keys (from S0; immutable within a run):**

* `manifest_fingerprint = F` (hex64, lowercase) — also the egress partition “fingerprint”. Rows must echo this value in-column.
* `global_seed = S_master` (u64) — the master RNG seed for the run; echoed per row as `global_seed`. (S8 uses **no** RNG, but the seed is part of lineage.)
* `run_id` (hex32) — **logs only**; never participates in egress partitioning.

**Country membership & order (sole authority):**

* `country_set(seed, parameter_hash)` provides, per merchant $m$, an **ordered** ISO-2 tuple
  $\mathcal{C}_m=(c_0,\dots,c_{K_m})$ with **exactly one** home row `rank(c_0)=0`, and unique ISO codes overall; **this is the only source of inter-country order** (egress never encodes it).

**Final integer allocations (from S7):**

* $n_{m,c}\in\mathbb{Z}_{\ge 0}$ is the **largest-remainder** site count for merchant $m$ and legal country $c\in\mathcal{C}_m$. Residual order evidence lives in the parameter-scoped cache; S8 does **not** re-derive it.

**Merchant-level provenance (carried into egress rows):**

* `single_vs_multi_flag` — **boolean** (true = multi-site).
* `raw_nb_outlet_draw = N_m` — the merchant’s ZTP draw **before** cross-country allocation; schema requires it on every egress row. (Constant within merchant $m$.)
* `home_country_iso` — equals the ISO of the unique `rank=0` entry $c_0$ for $m$.

**Pre-flight presence tests (abort S8 if any fail):**

1. `country_set` exists for all merchants in scope and has exactly one `rank=0` per merchant; ISO codes are unique per merchant.
2. $\{n_{m,c}\}$ is available for **every** $(m,c)\in\mathcal{C}_m$.
3. Lineage pair $(F, S_{\text{master}})$ is present.

---

## 2) Dataset target & partitions (authoritative)

**Target egress dataset & path (dictionary/registry):**

```
data/layer1/1A/outlet_catalogue/
  seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet
schema_ref: schemas.1A.yaml#/egress/outlet_catalogue
partitions: ["seed","fingerprint"]
```

This path, partitioning, and schema pointer are fixed by the artefact registry; `outlet_catalogue` depends on `country_set` and the `sequence_finalize` event (audit).

**Primary key & write order (schema/locked spec):**

* **PK:** $(\texttt{merchant_id},\ \texttt{legal_country_iso},\ \texttt{site_order})$.
* **Write order (and file sort):** lexicographic by that same tuple.
* **Policy:** **no inter-country order** is encoded here; consumers must join `country_set.rank`.

---

## 3) Notation & encoders (normative)

Let:

* $\mathcal{M}$ be the merchant set in scope.
* For $m\in\mathcal{M}$, $\mathcal{C}_m=(c_0,\ldots,c_{K_m})$ from `country_set`.
* $N_m=\texttt{raw_nb_outlet_draw}(m)\in\mathbb{Z}_{\ge 1}$.
* $n_{m,c}\in\mathbb{Z}_{\ge 0}$ are final counts from S7.

**Overflow threshold (six-digit site ids):**

$$
U \;=\; 999{,}999.
$$

If any $n_{m,c}>U$, S8 will later emit a `site_sequence_overflow` (zero-draw) and **abort** egress for this fingerprint. (Defined here; enforced in S8.4/S8.5.)

**Fixed site-id encoder (bijection inside a block):**
Define $\sigma:\{1,\ldots,U\}\to\{0,1\}^6$ (decimal string) by **left-padding to six digits**:

$$
\sigma(j) \;=\; \text{zpad6}(j)\quad\text{(e.g., }1\mapsto\text{"000001"}\text{)}.
$$

Inside a given $(m,c)$ block, $\sigma$ is injective and yields `site_id` that matches `^[0-9]{6}$`.

---

## 4) Row model (what one row means)

For each **non-empty** block $(m,c)$ where $n_{m,c}>0$, S8 will produce exactly $n_{m,c}$ rows, one for each **row index** $j\in\{1,\ldots,n_{m,c}\}$. Each row carries:

### 4.1 Merchant-level columns (constant within merchant $m$)

* `merchant_id` — id64.
* `single_vs_multi_flag` — **boolean**. (If upstream is 0/1, cast to bool at write.)
* `raw_nb_outlet_draw` — equals $N_m$ for **every** row of merchant $m$.
* `home_country_iso` — equals $c_0$ (the unique `rank=0` ISO) for merchant $m$.
* `global_seed` — equals $S_{\text{master}}$ (partition echo).
* `manifest_fingerprint` — equals $F$ (partition echo).

### 4.2 Block-level columns (constant within $(m,c)$)

* `legal_country_iso = c` (ISO-2; FK to canonical ISO).
* `final_country_outlet_count = n_{m,c}`.
  **Persisted rows must satisfy** $1\le n_{m,c}\le U$; when $n_{m,c}=0$ **no rows are written** for $(m,c)$. (Schema domain is $\{1,\ldots,999{,}999\}$ for this column.)

### 4.3 Row-level columns (vary with $j$)

* `site_order = j` with domain $j\in\{1,\ldots,n_{m,c}\}$.
* `site_id = σ(j)` — the 6-digit zero-padded image of `site_order`.
* **PK tuple** $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$ is therefore **unique**.
* **Within each $(m,c)$:** `site_id` is unique by construction (bijection $j\leftrightarrow\sigma(j)$); S9 also re-asserts this mechanically.

### 4.4 Cross-field invariants (every persisted row)

$$
\boxed{\ 1 \le \texttt{site_order} \le \texttt{final_country_outlet_count}\ },\quad
\boxed{\ \texttt{site_id}=\text{zpad6}(\texttt{site_order})\ },\quad
\boxed{\ \texttt{home_country_iso},\ \texttt{legal_country_iso}\in \text{ISO2 (FK)}\ }.
$$

These are schema-enforced or checked by the write-time validator.

---

## 5) Policy & separation of concerns (must-hold)

1. **No inter-country order in egress.** The egress table is **not** allowed to encode cross-country order; any consumer needing “home/foreign sequencing” **must** join `country_set.rank`. (Checked later in S8.6/S9.)
2. **Partition echo.** Every row’s `global_seed` and `manifest_fingerprint` **must equal** the directory tokens `seed` and `fingerprint`.
3. **Determinism.** S8 is a pure function of $(\{n_{m,c}\},F,S_{\text{master}})$; there are **no** RNG draws in S8. (S8’s RNG events, introduced later, are **zero-draw** attestations.)

---

## 6) Minimal pre-S8.2 validator (reference)

```pseudo
function s8_1_preflight(m, C_m, n_map, F, S_master):
    # C_m: ordered list of ISO for merchant m from country_set (rank 0..K_m)
    assert len(C_m) >= 1 and rank(C_m[0]) == 0                                       # unique home
    assert unique(C_m)                                                                # ISO uniqueness

    # lineage present
    assert is_hex64(F) and is_uint64(S_master)

    # counts available
    for c in C_m:
        assert exists(n_map[(m,c)]) and n_map[(m,c)] >= 0

    return OK
```

This validator enforces only **presence & authority**; range/domain/PK/overflow are enforced in S8.2–S8.5 against the egress schema.

---

## 7) Where S8.2 picks up

Given the state above, **S8.2** will:

* iterate each $(m,c)$ with $n_{m,c}>0$,
* emit exactly $n_{m,c}$ rows with `site_order = 1..n_{m,c}`, `site_id = zpad6(site_order)`,
* place the deterministic **write order** `(merchant_id, legal_country_iso, site_order)`,
* and stage the partition under `…/seed={seed}/fingerprint={F}/` for validation and atomic commit.

---

### Column domains & keys (from schema; for quick reference)

* `site_id` matches `^[0-9]{6}$`;
* `raw_nb_outlet_draw ≥ 1`;
* `final_country_outlet_count ∈ {1,…,999999}`;
* `site_order ≥ 1`;
* FK for both ISO-2 fields to the canonical ISO dataset;
* **PK:** `(merchant_id, legal_country_iso, site_order)`; partitions `(seed, fingerprint)`.

---

This locks the **inputs**, **symbols**, and the **row semantics** with exact domains and authorities, so we can implement S8.2’s deterministic expansion without guesswork.

---

# S8.2 — Deterministic construction of per-country sequences

## Scope & purpose

For each merchant–country block $(m,c)$ with integerised count $n_{m,c}\ge 0$ (from S7), materialise **exactly $n_{m,c}$** rows in **`egress/outlet_catalogue`**, encoding **within-country** order only. S8 consumes **no RNG**; it is a pure function of $\{\!n_{m,c}\!\}$, the run’s `manifest_fingerprint` $F$ and `global_seed` $S_{\text{master}}$.

---

## Authoritative dataset contract (target, keys, domains)

* **Target path & partitions (fixed):**
  `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet` with partitions `["seed","fingerprint"]`. **PK:** `["merchant_id","legal_country_iso","site_order"]`. **Sort keys / write order:** the same tuple. **Inter-country order is NOT encoded** here; consumers must join `alloc/country_set.rank`.
* **Selected column domains (enforced at write):**
  `site_id` matches `^[0-9]{6}$`; `raw_nb_outlet_draw ≥ 1`; `final_country_outlet_count ∈ {1,…,999999}`; `site_order ≥ 1`; both ISO fields FK to canonical ISO. Cross-field: $1 \le \texttt{site_order} \le \texttt{final_country_outlet_count}$.

---

## Inputs (MUST) and fixed encoders

For merchant $m$ with **ordered** country set $\mathcal{C}_m$ from `country_set` (unique `rank=0` home), S8 receives: $n_{m,c}\in\mathbb{Z}_{\ge 0}$ for each $c\in\mathcal{C}_m$; merchant-wide lineage columns (`single_vs_multi_flag` boolean; `raw_nb_outlet_draw=N_m≥1`; `home_country_iso=c_0`); and run lineage $F,S_{\text{master}}$. **Overflow threshold:** $U=999{,}999$. **Site-id encoder:** $\sigma(j)=\text{zpad6}(j)$ for $j\in\{1,\dots,U\}$.

---

## Normative construction

### (A) Per-block sequence space

For each $(m,c)$, define

$$
\mathcal{J}_{m,c}=\{1,2,\dots,n_{m,c}\}.
$$

If $n_{m,c}=0$ then $\mathcal{J}_{m,c}=\varnothing$ and **no rows** are emitted for that block.

### (B) Overflow guard (must-abort)

If $n_{m,c}>U$ for any $(m,c)$, **emit** a zero-draw guard event `site_sequence_overflow` for that $(m,c)$ and **abort** the egress build for this `(seed,fingerprint)` (no partials). Event lives at
`logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with schema `schemas.layer1.yaml#/rng/events/site_sequence_overflow`. (S8.4 specifies envelopes; here we require the guard to fire.)

### (C) Row expansion (pure map)

For each $(m,c)$ with $n_{m,c}>0$, and for each $j\in\mathcal{J}_{m,c}$, **emit one row**:

$$
\begin{aligned}
&\texttt{merchant_id}=m,\qquad \texttt{legal_country_iso}=c,\\
&\texttt{site_order}=j,\qquad \texttt{site_id}=\sigma(j)\ \ (\text{6 digits}),\\
&\texttt{home_country_iso}=c_0\ \ (\text{merchant home}),\\
&\texttt{single_vs_multi_flag}=\text{bool},\ \texttt{raw_nb_outlet_draw}=N_m,\\
&\texttt{final_country_outlet_count}=n_{m,c},\\
&\texttt{manifest_fingerprint}=F,\ \texttt{global_seed}=S_{\text{master}}.
\end{aligned}
$$

This fixes **scope**: some fields are per-merchant constants (`single_vs_multi_flag`, `raw_nb_outlet_draw`, `home_country_iso`), some per-block constants (`legal_country_iso`, `final_country_outlet_count`), and some per-row (`site_order`, `site_id`).

### (D) Write-stability ordering (must)

Before writing, sort (or generate) rows **lexicographically** by
$(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$. This matches the dataset’s sort keys and guarantees byte-stable output across platforms. **Inter-country order is not encoded**; use `country_set.rank` when needed.

### (E) Audit attestation (non-consuming)

For each non-empty block $(m,c)$, **emit exactly one** zero-draw `sequence_finalize` event (payload at minimum `{merchant_id, country_iso, site_count=n_{m,c}}`) under
`logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with schema `schemas.layer1.yaml#/rng/events/sequence_finalize`. (Counter equality & `draws=0` are specified in S8.4; S8.2 **requires** the emission here.)

---

## Error handling (abort semantics)

Abort S8 for the merchant-set/partition if any occurs:

* `E-S8.2-OVERFLOW`: $\exists(m,c): n_{m,c}>U$. Must log `site_sequence_overflow` (zero-draw) first; **no** egress written.
* `E-S8.2-DOMAIN`: a to-be-emitted row would violate schema domain/range/regex (e.g., `site_order<1`, `site_id` not `^[0-9]{6}$`, `final_country_outlet_count<1` for a persisted row).
* `E-S8.2-PK-DUP`: duplicate `(`merchant_id`, `legal_country_iso`, `site_order`)` within the staged partition. (Should be impossible given construction; still enforced.)
* `E-S8.2-ECHO`: any row’s `global_seed` or `manifest_fingerprint` doesn’t equal the partition tokens. (Checked at write.)

*(Event envelope mis-configuration and zero-draw reconciliation are validated in S8.4/S8.6, but S8.2’s caller must fail if emission itself errors.)*

---

## Invariants (MUST hold)

1. **Row count:** For every $(m,c)$, the number of materialised rows equals $n_{m,c}$; for $n_{m,c}=0$ there are **zero** rows.
2. **Within-block order & bijection:** Inside a block, `site_order` is a **gap-free permutation** of $\{1..n_{m,c}\}$ and `site_id = zpad6(site_order)`; thus `site_id` is unique in the block.
3. **Write order:** Rows are written in `(merchant_id, legal_country_iso, site_order)` lexicographic order.
4. **No RNG:** S8 emits only **zero-draw** events; `draws=0` and `after==before` in their envelopes (asserted in S8.4).

---

## Reference pseudocode (deterministic; language-agnostic)

```pseudo
function s8_2_construct_and_stage(F, S_master, country_set, counts, wide_by_merchant):
    # country_set: list of (merchant_id=m, country_iso=c, rank, is_home) in rank order
    # counts: map[(m,c)] -> n >= 0
    # wide_by_merchant[m] -> {home_country_iso, single_vs_multi_flag, raw_nb_outlet_draw}

    STAGE := []  # in-memory stream (or direct writer with enforced order)
    for (m,c) in country_set:
        n := counts[(m,c)]  # default 0 if absent -> (S8.1 preflight disallows absence)
        if n > 999999:
            emit_event(label="site_sequence_overflow", draws=0,
                       payload={merchant_id:m, country_iso:c, site_count:n, threshold:999999})
            abort("E-S8.2-OVERFLOW")

        if n == 0: continue

        H := wide_by_merchant[m].single_vs_multi_flag   # boolean
        N := wide_by_merchant[m].raw_nb_outlet_draw     # int32 >=1
        home := wide_by_merchant[m].home_country_iso    # ISO2

        for j in 1..n:
            row := {
              manifest_fingerprint: F,
              merchant_id: m,
              site_id: zpad6(j),
              home_country_iso: home,
              legal_country_iso: c,
              single_vs_multi_flag: H,
              raw_nb_outlet_draw: N,
              final_country_outlet_count: n,
              site_order: j,
              global_seed: S_master
            }
            assert matches(row.site_id, "^[0-9]{6}$")
            assert 1 <= row.site_order and row.site_order <= row.final_country_outlet_count
            STAGE.append(row)

        emit_event(label="sequence_finalize", draws=0,
                   payload={merchant_id:m, country_iso:c, site_count:n})

    # Write-stability: enforce lexicographic order before write (or stream in-order).
    STAGE.sort_by((merchant_id, legal_country_iso, site_order))

    # Stage to parquet files under seed=S_master/fingerprint=F (S8.5 handles atomic commit)
    parquet_write("data/layer1/1A/outlet_catalogue/seed={S_master}/fingerprint={F}/", STAGE)
```

Casts & echoes (row ↔ partition) are enforced here; schema constraints are validated at write. Paths/keys match the dictionary and schema.

---

## Conformance tests (must-pass)

1. **Zero-block:** $n_{m,c}=0$ → no rows for that $(m,c)$. Table remains valid and ordered.
2. **Happy path:** $n_{m,c}=3$ → three rows; `site_order=[1,2,3]`; `site_id=["000001","000002","000003"]`; `final_country_outlet_count=3` constant; PK unique.
3. **Overflow:** $n_{m,c}=1{,}000{,}000$ → emit exactly one `site_sequence_overflow` (zero-draw) for $(m,c)$; **no** egress written for the partition.
4. **Write order:** Shuffle generation intentionally; final file(s) must still be sorted by `(merchant_id, legal_country_iso, site_order)`.
5. **Domain guard:** Inject `site_id="12345"` (5 digits) or `final_country_outlet_count=0` on a persisted row → schema validator rejects with `E-S8.2-DOMAIN`.
6. **Event attestation:** For non-empty blocks, presence of one `sequence_finalize` (zero-draw) with `site_count=n_{m,c}`; for valid runs, **no** `site_sequence_overflow`. Paths match dictionary entries.

---

## Complexity & determinism

Let $T=\sum_m\sum_{c\in\mathcal{C}_m} n_{m,c}$. Construction is $\Theta(T)$ time and output size; sorting is linear if rows are generated in key order (or $T\log T$ if you materialise then sort). With fixed $(\{n_{m,c}\},F,S_{\text{master}})$, replay is **byte-stable**.

---

This locks S8.2: the exact expansion rule, overflow guard, row/field scopes, write-stability order, error semantics, and conformance tests, all wired to your schema and registry. Next up, S8.3 will nail the **keys, constraints, and validator predicates** the writer must enforce.

---

# S8.3 — Keys, domains, cross-field constraints & validator (schema-tight)

## Scope

This sub-state turns the egress schema for **`outlet_catalogue`** into **executable predicates**: primary/partition/sort keys, column domains (types, ranges, regex), **cross-field** rules (e.g., `site_id = zpad6(site_order)`, per-block constants), **additional uniqueness** (within-block `site_id`), **FK**s, and **echo invariants** (row ↔ partition). These rules are enforced at write-time, then mirrored by S9.

---

## Authoritative dataset contract (path, keys, schema)

* **Path & partitions (fixed):**
  `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet`
  with **partition keys** `["seed","fingerprint"]`. Writer must ensure every row echoes `global_seed==seed` and `manifest_fingerprint==fingerprint`.

* **Primary key (PK):** `["merchant_id","legal_country_iso","site_order"]`.
  **Sort keys / write order:** same tuple — `(merchant_id, legal_country_iso, site_order)`. **Inter-country order is not encoded** (consumers join `country_set.rank`).

* **Schema ref:** `schemas.1A.yaml#/egress/outlet_catalogue`. (Columns and constraints below copy that schema exactly.)

* **Registry notes / gate:** This dataset depends on `country_set`, `site_id_allocator` (S8 loop), and the `sequence_finalize` event; 1B may read **only after** `_passed.flag` matches `SHA256(validation_bundle_1A)` for the same fingerprint.

---

## Column domains (normative — from schema)

For every persisted row:

* `manifest_fingerprint`: **string**, pattern `^[a-f0-9]{64}$` (lowercase hex64). **Must equal** partition `{fingerprint}`.
* `merchant_id`: `id64` (non-null).
* `site_id`: **string**, `^[0-9]{6}$` (six decimal digits; zero-padded).
* `home_country_iso`: ISO-2 with FK → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024.country_iso`.
* `legal_country_iso`: ISO-2 with the **same FK**. (Two separate columns, same FK target.)
* `single_vs_multi_flag`: **boolean** (writer may cast upstream {0,1} → bool at write).
* `raw_nb_outlet_draw`: `int32`, **minimum 1**. (Replicate merchant’s $N_m$ on **every** row for that merchant.)
* `final_country_outlet_count`: `int32`, **minimum 1**, **maximum 999999**. (Rows exist **only** when $n_{m,c}\ge 1$; zero-blocks emit **no rows**.)
* `site_order`: `int32`, **minimum 1**. (Upper bound tied by cross-field constraint below.)
* `global_seed`: `uint64`. **Must equal** partition `{seed}`.

**Cross-field domain (schema-declared):**

$$
\boxed{\ 1 \le \texttt{site_order} \le \texttt{final_country_outlet_count}\ }.
$$

This is enforced in addition to the per-column minima.

---

## Cross-field constraints (normative — beyond column types)

These are **must-hold** semantics derived from S8.1/S8.2 and locked S8:

1. **Site-ID encoder (bijection in block).**
   Within each $(m,c)$, `site_id == zpad6(site_order)`. This is a **total bijection** between `site_order ∈ {1..n_{m,c}}` and 6-digit strings in the block; it implies **within-block uniqueness** of `site_id`. (Schema regex ensures shape; this rule pins its semantics.)

2. **Block constants (groupwise).**
   For a fixed $(m,c)$, `final_country_outlet_count` is **constant** and equals the block size, and `legal_country_iso == c` for **all** rows in that block. Consequently,

$$
\#\{ \text{rows for }(m,c)\} \;=\; \texttt{final_country_outlet_count}.
$$

This is validated by S8 and re-asserted by S9.

3. **Merchant constants.**
   For a fixed merchant $m$: `raw_nb_outlet_draw` is **constant** across all of that merchant’s rows; `single_vs_multi_flag` is constant; `home_country_iso` is constant and equals the ISO of the unique `rank=0` row in `country_set`. (S8.1 preflight guarantees unique home.)

4. **Partition echo invariants.**
   Every row must satisfy:
   `global_seed == {seed}` and `manifest_fingerprint == {fingerprint}` of the partition path. This couples rows to their directory tokens.

5. **Inter-country order separation (policy).**
   No attempt to encode cross-country order in egress; consumers **must** join `alloc/country_set.rank` to recover that order (0=home; foreigns by Gumbel order). This is stated in schema description and dictionary and will be checked by S9 policy tests.

6. **Overflow limit (consistency with S8.2).**
   By construction and schema max, for all $(m,c)$: $n_{m,c} \le 999{,}999$; if violated, S8 emits `site_sequence_overflow` and **aborts** the partition (no egress). (Predicate exists here and in S8.2 for defense-in-depth.)

7. **Additional uniqueness (normative, validator-enforced).**
   Although the schema’s PK is `(merchant_id, legal_country_iso, site_order)`, the locked S8 also requires **within-block** uniqueness of `site_id`. Therefore **for each (m,c)**:

$$
\text{Unique}\big(\texttt{site_id}\big).
$$

This is enforced by the S8/S9 validators (not encoded as a separate unique key in schema).

---

## Error codes (abort semantics)

On the staged partition (prior to atomic commit):

* `E-S8.3-PK-DUP`: duplicate PK `(merchant_id, legal_country_iso, site_order)`. (Hard error; abort.)
* `E-S8.3-SITEID-DUP`: duplicate `site_id` within the same `(merchant_id, legal_country_iso)` block. (Normative uniqueness; abort.)
* `E-S8.3-DOMAIN`: any column violates its domain (regex/min/max/type). (E.g., `site_id` not 6 digits; `final_country_outlet_count` out of `[1,999999]`; `raw_nb_outlet_draw < 1`.)
* `E-S8.3-CROSSFIELD`: any row violates `1 ≤ site_order ≤ final_country_outlet_count` or `site_id != zpad6(site_order)`.
* `E-S8.3-BLOCKCONST`: within a block, `final_country_outlet_count` not constant or `#rows != final_country_outlet_count`.
* `E-S8.3-MERCHCONST`: merchant constants drift (`raw_nb_outlet_draw`, `single_vs_multi_flag`, or `home_country_iso` not constant for merchant).
* `E-S8.3-FK-ISO`: `home_country_iso` or `legal_country_iso` not found in canonical ISO dataset. (FK breach; hard structural failure.)
* `E-S8.3-ECHO`: partition echo mismatch (row’s `global_seed`/`manifest_fingerprint` differ from path tokens).
* `E-S8.3-OVERFLOW`: block with $n_{m,c} > 999{,}999$ observed in staged content (should be pre-blocked by S8.2). Abort and ensure a `site_sequence_overflow` exists; no commit.

---

## Reference validator (single-pass, implementation-ready)

The validator runs **before** S8.5’s atomic publish against the **staging** output for `(seed, fingerprint)`.

```pseudo
function validate_outlet_catalogue_stage(seed, fingerprint, rows_iter):
    # Hash maps keyed by (m,c) and m
    seen_pk        := HashSet()                      # tuples (m,c,j)
    seen_siteid    := HashMap<(m,c), HashSet>()      # enforce within-block uniqueness
    block_count    := HashMap<(m,c), int64>()        # observed rows per block
    block_fcount   := HashMap<(m,c), int32>()        # final_country_outlet_count asserted
    merch_draw     := HashMap<m, int32>()            # raw_nb_outlet_draw per merchant
    merch_flag     := HashMap<m, bool>()             # single_vs_multi_flag per merchant
    merch_home     := HashMap<m, ISO2>()             # home_country_iso per merchant

    for row in rows_iter:
        # 0) Partition echo
        assert row.global_seed == seed and row.manifest_fingerprint == fingerprint
            or raise E-S8.3-ECHO

        # 1) Types & regex
        assert matches(row.manifest_fingerprint, "^[a-f0-9]{64}$") else E-S8.3-DOMAIN
        assert matches(row.site_id, "^[0-9]{6}$") else E-S8.3-DOMAIN
        assert row.raw_nb_outlet_draw >= 1 else E-S8.3-DOMAIN
        assert 1 <= row.final_country_outlet_count <= 999999 else E-S8.3-DOMAIN
        assert 1 <= row.site_order else E-S8.3-DOMAIN
        assert is_valid_iso2(row.home_country_iso) and is_valid_iso2(row.legal_country_iso)
            else E-S8.3-FK-ISO

        # 2) Cross-field constraints
        assert row.site_order <= row.final_country_outlet_count else E-S8.3-CROSSFIELD
        assert row.site_id == zpad6(row.site_order) else E-S8.3-CROSSFIELD

        # 3) PK uniqueness
        pk := (row.merchant_id, row.legal_country_iso, row.site_order)
        assert add_unique(seen_pk, pk) else E-S8.3-PK-DUP

        # 4) Within-block invariants
        k := (row.merchant_id, row.legal_country_iso)
        block_count[k]  := block_count.get(k,0) + 1
        if k not in block_fcount:
            block_fcount[k] = row.final_country_outlet_count
        else:
            assert block_fcount[k] == row.final_country_outlet_count else E-S8.3-BLOCKCONST

        S := seen_siteid.get_or_create(k, HashSet())
        assert add_unique(S, row.site_id) else E-S8.3-SITEID-DUP

        # 5) Merchant constants
        m := row.merchant_id
        if m not in merch_draw: merch_draw[m] = row.raw_nb_outlet_draw
        else: assert merch_draw[m] == row.raw_nb_outlet_draw else E-S8.3-MERCHCONST

        if m not in merch_flag: merch_flag[m] = row.single_vs_multi_flag
        else: assert merch_flag[m] == row.single_vs_multi_flag else E-S8.3-MERCHCONST

        if m not in merch_home: merch_home[m] = row.home_country_iso
        else: assert merch_home[m] == row.home_country_iso else E-S8.3-MERCHCONST

    # 6) Per-block cardinality equality and overflow double-guard
    for k in block_count.keys():
        assert block_count[k] == block_fcount[k] else E-S8.3-BLOCKCONST
        assert block_fcount[k] <= 999999 else E-S8.3-OVERFLOW

    return OK
```

* `is_valid_iso2` performs the FK test by joining the canonical ISO dataset embedded in the schema.
* This validator is **O(T)** over $T$ rows; memory is proportional to the number of concurrent blocks/merchants in the staged partition.

---

## Conformance tests (must-pass)

1. **Happy path / small block.** For $(m,c)$ with $n_{m,c}=3$, rows have `site_order=[1,2,3]`, `site_id=["000001","000002","000003"]`, `final_country_outlet_count=3`; PK unique; within-block `site_id` unique. ✔︎

2. **Zero-block elision.** If $n_{m,c}=0$, there are **no rows** for $(m,c)$. (Therefore no possibility of `final_country_outlet_count=0` on persisted rows.) ✔︎

3. **Partition echo mismatch.** Write a row with the right data but `global_seed` ≠ partition `seed` → `E-S8.3-ECHO`. ✔︎

4. **Site-ID collision.** Duplicate a `site_id` within a block (e.g., two rows with `site_order=2` or incorrect `site_id`) → `E-S8.3-SITEID-DUP` or `E-S8.3-CROSSFIELD`. ✔︎

5. **Block-constant drift.** Vary `final_country_outlet_count` inside the same block or make `#rows != final_country_outlet_count` → `E-S8.3-BLOCKCONST`. ✔︎

6. **Merchant constant drift.** Change `raw_nb_outlet_draw` mid-merchant → `E-S8.3-MERCHCONST`. ✔︎

7. **Domain guard.** Set `final_country_outlet_count=1_000_000` or `site_id="12345"` → `E-S8.3-DOMAIN` (and/or `E-S8.3-OVERFLOW`). ✔︎

8. **FK breach.** Inject `legal_country_iso="ZZ"` not in canonical ISO → `E-S8.3-FK-ISO`. ✔︎

---

## Why this matters (auditability & hand-off)

These predicates make S8’s output **mechanically checkable**: PK/partition/echo ensure immutability; domain & regex prevent malformed IDs; within-block bijection fixes the semantics of `site_id`; FK prevents drift in country codes; and separation of country order avoids policy leaks. The dictionary’s hand-off gate (`_passed.flag` equals `SHA256(validation_bundle_1A)`) means **1B will never read** unless all of the above pass under S9 as well.

---

# S8.4 — Event emission (audit trail)

## 1) Purpose & scope (normative)

S8 constructs **within-country** site sequences *without consuming RNG*. Nevertheless, it must emit *structured RNG events* to (a) attest what was written and (b) keep the Philox lineage continuous. The two labels in scope are:

* **`sequence_finalize`** — one **non-consuming** attestation per non-empty $(m,c)$ block. Role: “Final sequence allocation per (merchant,country) block.”
* **`site_sequence_overflow`** — **non-consuming** guardrail on 6-digit space exhaustion; emitted *only* when $n_{m,c}>999{,}999$, and the build aborts.

All RNG events carry the **common envelope** (`rng_envelope`) fields, including `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label`, and **Philox before/after counters**; non-consuming events must preserve counters: `before == after`.

Paths, partitioning and schema pointers are fixed in the **dataset dictionary** and **artefact registry**, with partitions `seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}`.

---

## 2) Event schemas & payload contracts

### 2.1 Common envelope (shared by all events)

All events **must** include the `rng_envelope` properties below (subset shown for brevity; see schema for the full list). Counters are 2×64 Philox integers. **Requirement (non-consuming):** `rng_counter_before_lo == rng_counter_after_lo` and `rng_counter_before_hi == rng_counter_after_hi`.

```
required: [
  ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
  module, substream_label,
  rng_counter_before_lo, rng_counter_before_hi,
  rng_counter_after_lo,  rng_counter_after_hi
]
```

### 2.2 `sequence_finalize` (schema & math)

**Schema fields (payload):**
`merchant_id ∈ ℕ⁺`, `country_iso ∈ [A-Z]{2}`, `site_count ≥ 0`, `start_sequence ∈ ^[0-9]{6}$`, `end_sequence ∈ ^[0-9]{6}$`.

**Definition for a realized block $(m,c)$ with $n_{m,c} \ge 1$:**

$$
\texttt{site_count} = n_{m,c},\quad
\texttt{start_sequence}=\text{"000001"},\quad
\texttt{end_sequence} = \mathrm{zpad6}(n_{m,c}).
$$

If $n_{m,c}=0$, **no** event is emitted for that $(m,c)$. Producer module string: `"1A.site_id_allocator"`. Substream label string: `"sequence_finalize"`.

**Path & partitions:**
`logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.

### 2.3 `site_sequence_overflow` (schema & math)

**Schema fields (payload):**
`merchant_id`, `country_iso`, `attempted_count ≥ 0`, `max_seq = 999999` (const), `overflow_by ≥ 1`, `severity = "ERROR"`.

**Definition:** Trigger when $n_{m,c} > U$, $U=999{,}999$. Then

$$
\texttt{attempted_count}=n_{m,c},\qquad
\texttt{overflow_by}=n_{m,c}-U.
$$

Producer: `"1A.site_id_allocator"`. Substream: `"site_sequence_overflow"`. **Emit exactly one** event for the offending $(m,c)$, then **abort S8** (no partial egress).

**Path & partitions:**
`logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.

---

## 3) Determinism & RNG-accounting invariants (MUST hold)

* **EV-0 (non-consumption):** For both labels, envelope counters **do not** advance (`before == after`). The run’s `rng_trace_log` must record **draws = 0** for these labeled substreams, and its counters must reconcile exactly with the per-event envelopes.

* **EV-1 (cardinality):**
  $\#\texttt{sequence_finalize}(m,*)=\#\{c:\ n_{m,c}>0\}$.
  $\#\texttt{site_sequence_overflow}(m,*) \in \{0,1\}$ and equals 1 **only** if some $n_{m,c}>U$, in which case **no egress partition is written**.

* **EV-2 (payload coherence):** In every `sequence_finalize`, `site_count = n_{m,c}`, and
  `start_sequence="000001"`, `end_sequence=zpad6(n_{m,c})`. This must match the rows materialized in `outlet_catalogue` (S8.2/S8.5).

* **EV-3 (catalog & path conformance):** Each event stream must live at the exact catalogued path with partitions `{seed, parameter_hash, run_id}` and be validated against the registered schema pointers.

---

## 4) Emission timing & ordering (normative)

For each $(m,c)$ processed in S8:

1. **Overflow check**: If $n_{m,c}>U$ → emit `site_sequence_overflow` (non-consuming) → **abort** immediately.
2. If $n_{m,c}>0$: after the block’s rows are materialised (S8.2), emit one `sequence_finalize` (non-consuming).

Event emission order **follows** the dataset sort discipline `(merchant_id, legal_country_iso, site_order)` so that envelopes can be correlated with nearby egress output during forensics; this is a stability guideline, not a schema constraint.

---

## 5) Reference emission algorithm (pseudocode)

```pseudo
const U := 999_999
envelope_base := {
  run_id, seed, parameter_hash, manifest_fingerprint,
  module="1A.site_id_allocator"
}

for each merchant m in ascending order:
  for each legal country c for m in ascending ISO:
    n := n[m,c]                      # from S7 integerisation/output routing
    C_before := current_philox_counter()  # 128-bit (lo,hi)

    if n > U:
        emit_jsonl(
          path="logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl",
          record = envelope_base + {
            ts_utc=now(), substream_label="site_sequence_overflow",
            rng_counter_before_lo=C_before.lo, rng_counter_before_hi=C_before.hi,
            rng_counter_after_lo=C_before.lo,  rng_counter_after_hi=C_before.hi
          } + {
            merchant_id=m, country_iso=c,
            attempted_count=n, max_seq=999999, overflow_by=(n-U),
            severity="ERROR"
          }
        )
        abort("ERR_S8_OVERFLOW")

    if n > 0:
        start_seq := "000001"
        end_seq   := zpad6(n)
        emit_jsonl(
          path="logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl",
          record = envelope_base + {
            ts_utc=now(), substream_label="sequence_finalize",
            rng_counter_before_lo=C_before.lo, rng_counter_before_hi=C_before.hi,
            rng_counter_after_lo=C_before.lo,  rng_counter_after_hi=C_before.hi
          } + {
            merchant_id=m, country_iso=c,
            site_count=n, start_sequence=start_seq, end_sequence=end_seq
          }
        )
```

Paths and schema refs used above are exactly those registered in the **dataset dictionary** / **artefact registry** for 1A.

---

## 6) JSONL examples (illustrative)

### 6.1 `sequence_finalize` (n=3)

```json
{
  "ts_utc":"2025-08-15T12:00:00Z",
  "run_id":"r2025_08_15_001",
  "seed": 1469598103934665603,
  "parameter_hash":"a4c9...d2a1",
  "manifest_fingerprint":"f0ab...9c33",
  "module":"1A.site_id_allocator",
  "substream_label":"sequence_finalize",
  "rng_counter_before_lo": 0,
  "rng_counter_before_hi": 0,
  "rng_counter_after_lo":  0,
  "rng_counter_after_hi":  0,

  "merchant_id": 123456789,
  "country_iso": "GB",
  "site_count": 3,
  "start_sequence": "000001",
  "end_sequence":   "000003"
}
```

Schema pointer: `schemas.layer1.yaml#/rng/events/sequence_finalize`; path under `.../sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`.

### 6.2 `site_sequence_overflow` (n=1,000,005)

```json
{
  "ts_utc":"2025-08-15T12:00:00Z",
  "run_id":"r2025_08_15_001",
  "seed": 1469598103934665603,
  "parameter_hash":"a4c9...d2a1",
  "manifest_fingerprint":"f0ab...9c33",
  "module":"1A.site_id_allocator",
  "substream_label":"site_sequence_overflow",
  "rng_counter_before_lo": 0,
  "rng_counter_before_hi": 0,
  "rng_counter_after_lo":  0,
  "rng_counter_after_hi":  0,

  "merchant_id": 123456789,
  "country_iso": "US",
  "attempted_count": 1000005,
  "max_seq": 999999,
  "overflow_by": 6,
  "severity": "ERROR"
}
```

Schema pointer: `schemas.layer1.yaml#/rng/events/site_sequence_overflow`; path under `.../site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`.

---

## 7) Validation & reconciliation (conformance suite)

1. **JSON-schema conformance** for each file against its schema pointer (two labels above). **Reject** any record failing the envelope or payload validation.
2. **Trace reconciliation:** For labels $\ell\in\{\text{sequence_finalize},\text{site_sequence_overflow}\}$, compute
   $D_{\text{trace}}(\ell)=\sum \texttt{rng_trace_log.draws}$ over rows with `(module="1A.site_id_allocator", substream_label=ℓ)` and prove $D_{\text{trace}}(\ell)=0$. Enforce counters sum identity across the trace: $C^{\text{after}}-C^{\text{before}}=\sum \texttt{draws}$.
3. **Event cardinality checks:**
   (i) `sequence_finalize`: exactly one per non-empty $(m,c)$.
   (ii) `site_sequence_overflow`: none unless overflow; if present, **abort implies no egress partition** for that `(seed,fingerprint)`.
4. **Egress cross-checks:** For each `sequence_finalize(m,c)`, verify in `outlet_catalogue` that the block exists with exactly `site_count` rows, `site_order=1..site_count`, and `site_id` spans `start_sequence..end_sequence`. (Paths/ordering/PK constraints are fixed for `outlet_catalogue`.)

---

## 8) Failure semantics (normative)

* **ERR_S8_OVERFLOW** — on $n_{m,c}>999{,}999$: emit `site_sequence_overflow` (non-consuming) and **abort**; do not write or partially commit `outlet_catalogue`.
* **ERR_S8_EVENT_SCHEMA** — any JSON-schema failure on event emission.
* **ERR_S8_TRACE_MISMATCH** — if any non-consuming label shows `draws>0` or counter deltas in `rng_trace_log`.
* **ERR_S8_PATH_PARTITION** — if event files are not under the exact `{seed, parameter_hash, run_id}` partitions registered in the dictionary/registry.

---

## 9) Operational notes

* **Produced-by** module names for these logs are pinned in the dictionary/registry (producer: `1A.site_id_allocator`). This is important for automated lineage views and for S9 to filter by `(module, substream_label)`.
* The **schema catalog** that governs these event names is centrally registered as `rng_event_schema_catalog`.

---

## 10) Why this matters downstream

S9’s RNG accounting relies on **zero-draw** invariants for non-consuming labels and on one-per-block `sequence_finalize` to prove that S8 rows were written *exactly* as specified, without “hidden” RNG usage or re-ordering. This closes the audit trail between S7 allocation, S8 egress, and the RNG trace.

---

That’s the complete, hand-off-ready spec for **S8.4**: strict schemas, precise paths/partitions, counter-level invariants, and unambiguous failure behavior tied to the registry/dictionary you’ve already ratified.

---

# S8.5 — Output assembly & storage

## 1) Target dataset (authoritative)

**Dataset:** `outlet_catalogue`
**Path (partitioned):**

```
data/layer1/1A/outlet_catalogue/
  seed={global_seed}/fingerprint={manifest_fingerprint}/part-*.parquet
```

**Schema ref:** `schemas.1A.yaml#/egress/outlet_catalogue`
**Partitions:** `["seed","fingerprint"]`
**Primary key & sort order:** `["merchant_id","legal_country_iso","site_order"]` (lexicographic).
**Contract note:** inter-country order is **not** encoded; consumers must join `alloc/country_set.rank`.

**Registry dependencies:** `outlet_catalogue` depends (indirectly) on `country_set` → `site_id_allocator` (S8) → `rng_event_sequence_finalize`. 1B consumption is gated by a validation artefact (see §7).

---

## 2) Inputs to the writer (recap)

From S8.2 you have a deterministic, in-memory (or streaming) sequence of rows already in **final write order** `(merchant_id, legal_country_iso, site_order)` with per-row lineage echoes `global_seed=S_master`, `manifest_fingerprint=F`. Zero-block elision and overflow checks have been applied; for every non-empty `(m,c)`, S8.4 emitted **one** `sequence_finalize` event (non-consuming).

---

## 3) Staging & atomic commit (normative)

### 3.1 Two-phase publish

1. **Precondition (immutability guard).**
   If the **final** partition directory

   ```
   …/outlet_catalogue/seed=S_master/fingerprint=F/
   ```

   already exists **and is non-empty**, **abort**: this egress is immutable per `(seed,fingerprint)` and must not be rewritten.

2. **Stage.**
   Write all Parquet parts to a **temporary** directory:

   ```
   stage = …/seed=S_master/fingerprint=F/_staging/
   ```

   Ensure files are closed and fsync’d.

3. **Validate staged content** (see §4) against the authoritative schema & rules. **Do not** publish if any check fails.

4. **Atomic publish.**
   Atomically **rename/move** `stage` → final partition directory:

   ```
   …/seed=S_master/fingerprint=F/
   ```

   The move must be metadata-atomic on the backing filesystem (e.g., POSIX `rename(2)`). On any failure, best-effort delete `_staging/` and **abort**.

5. **Post-publish rule.**
   After publish, **do not write anything else** under the partition. All further validation artefacts live under `validation/fingerprint=F/` (see §7).

### 3.2 Idempotence & retries

* **Idempotence:** reruns that reach step (1) and detect a non-empty final partition **must stop** (no overwrite). This preserves reproducibility and lineage guarantees.
* **Retry window:** failures **before** rename may safely re-enter from step (2) after cleaning `_staging/`. Failures **after** rename are considered committed.

---

## 4) Must-pass validation (write-time, before commit)

Run these checks on **staged** files for `(seed=S_master, fingerprint=F)`; they mirror S8.3 and the schema:

**V-PK & order.**

* `count(rows) == count(distinct merchant_id, legal_country_iso, site_order)`.
* Files are lexicographically ordered by `(merchant_id, legal_country_iso, site_order)` (or at least *read* produces that order; writer should sort or stream in that order).

**V-echo (row ↔ path).**

* Every row has `global_seed == S_master` and `manifest_fingerprint == F`.

**V-domains & regex.**

* Enforce schema-declared ranges/patterns:
  `final_country_outlet_count ∈ [1,999999]`, `site_order ≥ 1`, `raw_nb_outlet_draw ≥ 1`, `site_id ~ ^[0-9]{6}$`, both ISO columns pass FK to canonical ISO table.

**V-cross-field invariants.**

* Per row: `1 ≤ site_order ≤ final_country_outlet_count`; `site_id == zpad6(site_order)`.
* Per block `(m,c)`: `final_country_outlet_count` **constant**; `#rows == final_country_outlet_count`; **within-block** `site_id` unique.

**V-overflow (defense-in-depth).**

* Assert `max(site_order in block) ≤ 999999`. (S8.2 should already have aborted; this is a belt-and-braces gate.)

**V-events (sync).**

* For each **non-empty** `(m,c)` block in the staged content, verify the presence of **exactly one** non-consuming `sequence_finalize` event at the registered path/label for the same `{seed, parameter_hash, run_id}`. For overflowed runs (if any), there must be **no** staged egress and exactly one `site_sequence_overflow` per offending block.

> A minimal reference validator for these predicates is already outlined in S8.3; reuse it here against `stage/` prior to rename.

---

## 5) File layout & performance (binding where stated)

**Write order.** Generate (or sort) rows in the dataset’s **sort-key order** `(merchant_id, legal_country_iso, site_order)` to avoid a global `T log T` sort; S8’s construction loop naturally produces this order.

**Row groups (advisory).** Prefer row groups that *do not interleave merchants excessively*; where feasible, align row-group boundaries to `(merchant_id, legal_country_iso)` to tighten stats and accelerate block scans on `site_order`. (This is performance guidance, not a schema rule.)

**Compression & naming.** Format is Parquet (per schema); use consistent codec across parts (e.g., Zstd level 3 per registry note); name parts `part-00000.parquet`, `part-00001.parquet`, … .

**Streaming memory bound.** With streaming writes, peak memory is `O(B)` for the writer’s row-group buffer (64–256 MB typical). S8 invariants are checkable on the fly (sequential `site_order`, block-constant counts).

---

## 6) Concurrency & sharding (determinism-safe)

**Shard by merchant** (or merchant ranges). Each shard must:

1. iterate merchants in ascending `merchant_id`, and
2. within a merchant, iterate `legal_country_iso` ascending, emitting `site_order=1..n_{m,c}`.

Produce per-shard `_staging/` content in final key order. At publish time, **either** (a) concatenate parts in shard-key order into the single partition, **or** (b) let each shard write parts under the same `_staging/` and rely on the final atomic move. The partition is **immutable**; a single **atomic rename** must occur at the end. If the final partition already exists, **abort** (no overwrite).

---

## 7) Governance, validation bundle & 1B gate

After publishing `outlet_catalogue`, the validation process emits:

* `validation_bundle_1A` at
  `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` (contains schema/PK/FK checks, RNG accounting, metrics), and
* `_passed.flag` in the **same** folder whose **content hash equals** `SHA256(validation_bundle_1A)`.

**Hand-off condition:** **1B may read `outlet_catalogue` only if** `_passed.flag` exists and matches the bundle digest for the **same** fingerprint. This gate is part of the registry contract and the state-flow hand-off.

---

## 8) Error codes (abort semantics)

* `E-S8.5-IMMUTABLE-EXISTS` — final partition exists and is non-empty; do not overwrite.
* `E-S8.5-SCHEMA` — any row violates the egress schema (types, ranges, regex).
* `E-S8.5-PK-DUP` — duplicate PK `(merchant_id, legal_country_iso, site_order)` in staged content.
* `E-S8.5-ECHO` — any row’s `global_seed`/`manifest_fingerprint` mismatches the partition tokens.
* `E-S8.5-BLOCKCONST` — within a block, `final_country_outlet_count` not constant or `#rows != final_country_outlet_count`.
* `E-S8.5-SITEID` — `site_id` not equal to `zpad6(site_order)` or not unique within a block.
* `E-S8.5-OVERFLOW` — any `site_order` or `final_country_outlet_count` exceeds `999999` (should have been caught earlier; defense-in-depth).
* `E-S8.5-EVENTSYNC` — missing/misplaced `sequence_finalize` (non-empty block) or presence of `site_sequence_overflow` while staging exists.
* `E-S8.5-ATOMIC-RENAME` — atomic rename/publish failed; partition remains uncommitted.

---

## 9) Reference publisher (language-agnostic pseudocode)

```pseudo
function publish_outlet_catalogue(rows_iter_sorted, S_master, F, parameter_hash, run_id):
    final_dir  = f"data/layer1/1A/outlet_catalogue/seed={S_master}/fingerprint={F}/"
    staging    = final_dir + "_staging/"

    # (1) immutability guard
    if exists(final_dir) and not is_empty(final_dir):
        raise E-S8.5-IMMUTABLE-EXISTS

    # (2) stage writes
    mkdirs(staging)
    parquet_write_parts(staging, rows_iter_sorted, schema="schemas.1A.yaml#/egress/outlet_catalogue")

    # (3) validate staged content
    validate_schema_and_pk(staging)                      # schema ref & PK/sort keys
    validate_partition_echo(staging, seed=S_master, fingerprint=F)
    validate_block_invariants(staging)                   # counts, site_order, zpad6, uniqueness
    validate_iso_fk(staging)
    validate_event_sync(seed=S_master, parameter_hash, run_id)  # one finalize per non-empty (m,c)

    # (4) atomic publish
    atomic_rename(staging, final_dir)                    # POSIX rename, single op
```

The `validate_*` helpers implement §4’s predicates; `validate_event_sync` inspects the two RNG event logs under their registered paths.

---

## 10) Conformance tests (must pass)

1. **Happy path:** two merchants, `(GB,US)` with counts `{3,2}` and `{1,0}`. Expect 6 rows; PK unique; per-block counts equal; exactly **three** `sequence_finalize` events; partition echoes correct. ✔︎
2. **Immutability:** create final partition, then attempt re-publish → `E-S8.5-IMMUTABLE-EXISTS`. ✔︎
3. **Event sync:** remove one `sequence_finalize` for a non-empty block → `E-S8.5-EVENTSYNC`. ✔︎
4. **Overflow defense:** craft a staged block with `final_country_outlet_count=1_000_000` → `E-S8.5-OVERFLOW`; ensure no final publish occurs. ✔︎
5. **Echo mismatch:** alter one row’s `global_seed` ≠ partition seed → `E-S8.5-ECHO`. ✔︎
6. **FK breach:** inject `legal_country_iso="ZZ"` not in canonical ISO → schema/validator failure. ✔︎

---

## 11) Policy alignment (schema authority)

* Use the **JSON-Schema** referenced above as the canonical contract; do **not** carry Avro sidecars in source. If Avro is required downstream, generate it at build/release time from JSON-Schema.
* Keep “inter-country order not encoded in egress” prominent in dataset notes and tests.

---

This section finalises how S8 takes the deterministic row stream from S8.2, **stages → validates → atomically commits** an immutable egress partition, and wires it to the **validation bundle gate** that authorises 1B reads. Every step above is directly tied to your schema, registry paths, and locked S8 text.

---

# S8.6 — Determinism & validator contract

## 1) Determinism (pure-function statement)

**Inputs (authorities):**

* Lineage: `manifest_fingerprint = F` (hex64), `global_seed = S_master` (u64). These also appear in-row and in the egress **partition keys** `(seed={S_master}, fingerprint={F})`.
* Membership & order: `country_set(seed,parameter_hash)` → for each merchant $m$, the ordered ISO tuple $\mathcal{C}_m=(c_0,\dots,c_{K_m})$ with **exactly one** home (`rank=0`). (Inter-country order lives **only** here.)
* Final integer counts: $\{n_{m,c}\}_{(m,c)}$ from S7 (largest-remainder outputs). S8 does **not** re-draw or re-rank. (RNG evidence for S7 sits in residual/cache & events.)
* Merchant-level constants: `single_vs_multi_flag` (**boolean**), `raw_nb_outlet_draw=N_m≥1`, `home_country_iso=c_0`. These repeat on **every** row for merchant $m$.

**Definition (no RNG):**

$$
\boxed{\ (\{n_{m,c}\},F,S_{\text{master}})\ \xrightarrow{\ \text{S8 (pure)}\ }\ \texttt{outlet_catalogue}\ }
$$

Rows are generated by the **fixed map** $j\mapsto\big(\text{site_order}=j,\ \text{site_id}=\mathrm{zpad6}(j)\big)$ for $j\in\{1,\dots,n_{m,c}\}$, with **write-stability** order `(merchant_id, legal_country_iso, site_order)`. **No RNG is consumed**; S8’s RNG events are **non-consuming attestations** (counters `before==after`, `draws=0`).

**Why replay is byte-stable:**

1. Construction is functional and local to $(m,c)$; no clocks, no sampling.
2. Sort keys equal the generation order; cross-engine equality follows from lexicographic write discipline.
3. Partition echoes `global_seed==seed`, `manifest_fingerprint==fingerprint`; schema and dictionary lock path, partitions, and column patterns.

---

## 2) What must be validated (staged egress, pre-publish)

The validator runs on the **staged** `outlet_catalogue/seed={S_master}/fingerprint={F}/_staging/` produced by S8.2 and S8.4, before the atomic rename in S8.5.

### 2.1 Schema & key contract (dataset-local)

**Schema conformance** against `schemas.1A.yaml#/egress/outlet_catalogue`:

* `site_id` \~ `^[0-9]{6}$`; `raw_nb_outlet_draw ≥ 1`; `final_country_outlet_count ∈ [1,999999]`; `site_order ≥ 1`.
* `home_country_iso` and `legal_country_iso` have **FK** to canonical ISO (ingress schema).

**Keys & partitions**:

* **PK** uniqueness on `(merchant_id, legal_country_iso, site_order)`.
* **Partitions**: directory keys are `(seed, fingerprint)`, and **every row** echoes `global_seed==seed`, `manifest_fingerprint==fingerprint`.
* **Sort keys** (write order): `(merchant_id, legal_country_iso, site_order)`; either streamed that way or sorted before write.

**Cross-field invariants** (every row):

$$
1 \le \texttt{site_order} \le \texttt{final_country_outlet_count},\qquad
\texttt{site_id} = \mathrm{zpad6}(\texttt{site_order}).
$$

Within a block $(m,c)$: `final_country_outlet_count` is **constant**, number of rows equals that constant, and **within-block** `site_id` is unique.

**Policy guard:** **Inter-country order is not encoded** in egress; consumers must use `country_set.rank`. (Presence as dataset note + checked downstream as policy.)

### 2.2 Overflow rule (capacity)

Because `site_id` is 6-digit, require $n_{m,c}\le 999{,}999$ for all $(m,c)$. If any $n_{m,c}>999{,}999$: S8 must have emitted `site_sequence_overflow` (zero-draw) and **aborted**; the staged egress must be **absent**. The validator re-asserts this.

### 2.3 RNG audit attestation (non-consuming labels)

**Event streams & paths** (dictionary/registry):

* `sequence_finalize` (one per non-empty block):
  `logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
* `site_sequence_overflow` (only on overflow):
  `logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
  Both use the **common RNG envelope**; **non-consuming** ⇒ `before==after`, `draws=0`.

**Presence & cardinality:**

$$
\#\texttt{sequence_finalize}=\sum_{(m,c)}\mathbf{1}\{n_{m,c}>0\},\quad
\#\texttt{site_sequence_overflow}\in\{0,1\}\ (\text{if any }n_{m,c}>U).
$$

Mismatch is structural failure; also, if any overflow exists, **no** egress must be published for this `(seed,fingerprint)`.

**Payload coherence:** for each `sequence_finalize(m,c)`, `site_count = n_{m,c}`, and implied `start_sequence="000001"`, `end_sequence=zpad6(n_{m,c})` must match the staged rows for that block. (Schema/text pin these semantics.)

**Trace reconciliation:** the **rng accounting** proves **zero-draw**: counters do not advance for these labels and `rng_trace_log` shows `draws=0` totals per label. (Certified later in S9’s bundle table, but the writer may pre-check.)

---

## 3) Error catalogue (writer-side abort semantics)

* `E-S8.6-SCHEMA` — any JSON-Schema violation on staged egress.
* `E-S8.6-PK-DUP` — duplicate PK `(merchant_id, legal_country_iso, site_order)`.
* `E-S8.6-ECHO` — some row’s `global_seed`/`manifest_fingerprint` ≠ partition tokens.
* `E-S8.6-CROSSFIELD` — `site_id ≠ zpad6(site_order)` or `site_order` out of `[1, final_country_outlet_count]`.
* `E-S8.6-BLOCKCONST` — within a block, `final_country_outlet_count` not constant or `#rows ≠ final_country_outlet_count`.
* `E-S8.6-SITEID-DUP` — duplicate `site_id` within a block $(m,c)$.
* `E-S8.6-FK-ISO` — ISO FK failure for `home_country_iso` or `legal_country_iso`.
* `E-S8.6-OVERFLOW` — a block with $n_{m,c}>999{,}999$ exists alongside staged egress (must have aborted with event).
* `E-S8.6-RNGCARD` — wrong **cardinality**: missing/excess `sequence_finalize` or illegal presence of overflow vs staged egress.
* `E-S8.6-RNGZERO` — any non-consuming event shows counter advance or `draws>0` in trace.

All are **hard-fail**; S8.5 must **not** publish the partition. (S9 will still write a bundle with diagnostics, but `_passed.flag` will be withheld.)

---

## 4) Reference validator (single-pass over rows + event sync)

This is the **writer-time** version; S9 re-implements the same plus more cross-dataset checks.

```pseudo
function validate_s8(staged_rows, seed, fingerprint, iso_table,
                     n_map, seq_finalize_events, overflow_events, rng_trace):
  # A) Partition echo + schema-local domains / FK
  for row in staged_rows:
    assert row.global_seed == seed and row.manifest_fingerprint == fingerprint     # ECHO
    assert regex(row.site_id, "^[0-9]{6}$")                                        # SCHEMA
    assert row.raw_nb_outlet_draw >= 1 and row.site_order >= 1                     # SCHEMA
    assert 1 <= row.final_country_outlet_count <= 999999                           # SCHEMA
    assert row.home_country_iso  in iso_table.country_iso                          # FK-ISO
    assert row.legal_country_iso in iso_table.country_iso                          # FK-ISO
    assert row.site_id == zpad6(row.site_order)                                    # CROSSFIELD
    pk := (row.merchant_id, row.legal_country_iso, row.site_order)
    assert add_unique(pk_set, pk)                                                  # PK-DUP
    # per-block tallies
    k := (row.merchant_id, row.legal_country_iso)
    block_rows[k]  += 1
    block_fcount[k] = ensure_const(block_fcount[k], row.final_country_outlet_count)# BLOCKCONST
    assert row.site_order <= block_fcount[k]                                       # CROSSFIELD
    assert add_unique(siteid_sets[k], row.site_id)                                 # SITEID-DUP

  # B) Block equality & overflow defence
  for k in keys(block_rows):
    assert block_rows[k] == block_fcount[k]                                        # BLOCKCONST
    assert block_fcount[k] <= 999999                                               # OVERFLOW

  # C) RNG event sync (non-consuming)
  # cardinality
  want_sf := sum_{(m,c)} 1[n_map[(m,c)] > 0]
  have_sf := count(seq_finalize_events)
  assert have_sf == want_sf                                                        # RNGCARD
  # per (m,c) payload match & zero-draw
  for e in seq_finalize_events:
    (m,c,n) := (e.merchant_id, e.country_iso, e.site_count)
    assert n == n_map[(m,c)]                                                       # RNGCARD
    assert counters_equal(e.before, e.after) and trace_draws(rng_trace,"sequence_finalize",m,c) == 0  # RNGZERO
  # overflow logic
  any_overflow := exists((m,c) where n_map[(m,c)] > 999999)
  if any_overflow:
    assert count(overflow_events) >= 1 and staged_rows.is_empty()                  # RNGCARD
    for e in overflow_events:
      assert e.attempted_count > 999999 and counters_equal(e.before, e.after)      # RNGZERO
  else:
    assert count(overflow_events) == 0

  return OK
```

* `trace_draws(…, label, m, c)` reads `rng_trace_log` (per registry/dictionary) and proves **zero** draws for these labels.
* Event paths & schema refs are fixed in the dictionary/registry (see §2.3).

---

## 5) What S9 will additionally prove (hand-off gate context)

S9 packages its results as **`validation_bundle_1A`** under
`data/layer1/1A/validation/fingerprint={F}/`, and the gate file **`_passed.flag`** whose **content hash equals** `SHA256(bundle)`. **1B may read `outlet_catalogue` only after verifying this pair for the same fingerprint** (enforced by both dictionary note and registry).

For RNG accounting across the whole run, S9 emits `rng_accounting.json` inside the bundle (per-label coverage, draw sums, counter deltas). Any mismatch (schema/PK/UK/FK, RNG replay, or corridor metrics) is a **hard fail**; bundle is still written for forensics, but `_passed.flag` is withheld.

---

## 6) Conformance tests (must-pass)

1. **Happy path, two blocks:** $(m,GB)$ with $n=3$, $(m,US)$ with $n=2$. Expect 5 rows ordered by `(merchant_id, legal_country_iso, site_order)`; `final_country_outlet_count` constants per block; PK unique; `site_id` = zpad6(`site_order`); **two** `sequence_finalize` events with `site_count` 3 and 2; **zero** overflow; non-consuming envelopes. ✔︎
2. **Zero-block elision:** include a third $(m,FR)$ with $n=0$; expect **no rows** for FR and **no** `sequence_finalize` for FR. ✔︎
3. **Overflow guard:** set $n_{m,US}=1{,}000{,}005$. Expect **one** `site_sequence_overflow` (non-consuming) and **no staged egress** (validator must fail publish with `E-S8.6-OVERFLOW`). ✔︎
4. **Echo mismatch:** flip one row’s `global_seed` or `manifest_fingerprint` ≠ partition → `E-S8.6-ECHO`. ✔︎
5. **PK duplication:** duplicate `(merchant_id, legal_country_iso, site_order)` → `E-S8.6-PK-DUP`. ✔︎
6. **Cross-field failure:** set `site_id="000010"` when `site_order=9` → `E-S8.6-CROSSFIELD`. ✔︎
7. **ISO FK breach:** inject `legal_country_iso="ZZ"` not in canonical ISO → `E-S8.6-FK-ISO`. ✔︎
8. **RNG non-consumption:** doctor one `sequence_finalize` to have `after ≠ before` or a non-zero draw in trace → `E-S8.6-RNGZERO`. ✔︎
9. **Event cardinality:** drop one `sequence_finalize` for a non-empty block → `E-S8.6-RNGCARD`. ✔︎

---

## 7) Implementation notes (binding where stated)

* **Validator location:** Run this validator **inside S8.5** on `_staging/` before the atomic rename. **If any check fails, do not publish**; leave diagnostics for S9 (which will still write a bundle but not `_passed.flag`).
* **Policy visibility:** Keep the **“no inter-country order in egress”** statement in schema/dictionary and assert it during S9 hand-off documentation.

---

This pins S8.6 at 100%: a formal pure-function statement for S8, the complete **writer-time** validator (mirrored by S9), precise event sync and zero-draw rules, overflow behaviour, error codes, and the 1A→1B cryptographic gate that depends on S9’s bundle.

---

# S8.7 — Complexity, streaming & ops

## 1) Scope (what this section binds)

S8 takes country-level integers $\{n_{m,c}\}$ and materialises the egress table **`outlet_catalogue`** (one row per realised site) under
`data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet`, with **PK** `(merchant_id, legal_country_iso, site_order)`, and **write order = sort keys** `(merchant_id, legal_country_iso, site_order)`. Inter-country order is **never** encoded in egress (consumers join `country_set.rank`). These dataset mechanics are **authoritative** and used below for complexity and ops.

---

## 2) Work & memory complexity

Let:

* $M$ = number of merchants in scope.
* For merchant $m$, $\mathcal{C}_m$ = ordered legal country set from `country_set`.
* $T=\sum_m\sum_{c\in\mathcal{C}_m} n_{m,c}$ = **total rows** (sites) to emit.

**Row materialisation.** Construction is a **pure map** $j\mapsto (\texttt{site_order}=j,\ \texttt{site_id}=\mathrm{zpad6}(j))$ per $(m,c)$; hence:

* **Time:** $\Theta(T)$ for row construction.
* **Extra sorting cost:** **none** if you generate in key order `(merchant_id, legal_country_iso, site_order)`; otherwise a global $T\log T$ appears and must be avoided.

**Memory (streaming writer).** With a streaming Parquet writer and contiguous emission in key order:

* Peak RAM is **O(row-group size)** (64–256 MiB typical) plus small hash sets for on-the-fly validation (per-block counters and uniqueness of `site_id` within current $(m,c)$). No full-table materialisation is required.

**RNG cost.** S8 consumes **no RNG**. Its events (`sequence_finalize`, `site_sequence_overflow`) are **non-consuming** and must keep Philox counters unchanged (`before == after`, `draws=0`).

---

## 3) I/O footprint & file layout (deterministic & scalable)

**Rows & parts.** Define:

* $B_{\text{uncomp}}$ = average uncompressed row byte size for `outlet_catalogue`.
* $r_g$ = desired Parquet **row-group** size in rows (target 128 MiB uncompressed per row-group).
* $P$ = number of part files (each may hold one or more row-groups).

Then the **expected number of row-groups**:

$$
G \approx \left\lceil \frac{T \cdot B_{\text{uncomp}}}{128\,\mathrm{MiB}} \right\rceil,\quad
P \approx \left\lceil \frac{G}{\text{row_groups_per_part}} \right\rceil.
$$

**Naming & path.** Parts **must** be named `part-00000.parquet`, … under
`…/seed={seed}/fingerprint={manifest_fingerprint}/`. The partition is **immutable**; two-phase publish is **required** (stage → validate → atomic rename).

**Compression & encodings (advisory but consistent).** Parquet format is mandated; codec selection is operational (e.g., Zstd level 3) and should be **consistent across parts**. Align row-groups (and optionally parts) with **block boundaries** $(m,c)$ where feasible to improve `site_order` predicates and scans. These are performance hints; schema & path remain binding.

**Partition echo.** Every row **must** echo the directory tokens: `global_seed==seed` and `manifest_fingerprint==fingerprint`.

---

## 4) Deterministic concurrency model

**Sharding unit.** **Merchant** is the recommended parallelisation unit. A shard processes a disjoint subset of merchants, **in ascending `merchant_id`**, and within each merchant iterates `legal_country_iso` **ascending**, emitting `site_order=1..n_{m,c}`. This preserves global lexicographic order when shards merge outputs.

**Multi-writer staging.** Allow multiple shard writers to emit parts into a **single `_staging/` directory** (unique temp filenames per shard), then perform **one** metadata-atomic rename to the final partition. Writers **must** produce parts that are internally ordered; overall global order is guaranteed by the sort key tuple and the fact that analytic readers respect Parquet row-group statistics rather than file creation order. (If you require byte-identical part listings across replays, concatenate parts deterministically at publish time.)

**Idempotence & immutability.** If the final partition already exists and is non-empty, **abort**; do **not** overwrite. Retries are allowed only **before** the atomic rename, after cleaning `_staging/`.

**Event emission ordering.** Emit `sequence_finalize` **after** each non-empty block’s rows are staged; emit `site_sequence_overflow` **and abort** immediately if $n_{m,c}>999{,}999$. Both events are non-consuming (`before == after`).

---

## 5) Online validation while streaming (single pass)

To avoid a second full scan before publish, perform **on-the-fly checks** as rows are written:

For current block key $k=(m,c)$ keep:

* `count_rows[k]` (seen rows),
* `final_count[k]` (first `final_country_outlet_count` encountered; must remain constant),
* `siteid_set[k]` (seen `site_id`s; can be **O(1)** memory using last-seen `site_order` if rows are strictly sequential).

**Per row predicate (must-hold):**

$$
\begin{aligned}
&\text{regex(site_id)}=\texttt{^[0-9]{6}\$},\quad
1\le \texttt{site_order}\le \texttt{final_country_outlet_count},\\
&\texttt{site_id}=\text{zpad6}(\texttt{site_order}),\quad
\texttt{raw_nb_outlet_draw}\ge 1,\\
&\texttt{home_country_iso},\texttt{legal_country_iso}\in\text{ISO2 (FK)},\\
&(\texttt{global_seed},\texttt{manifest_fingerprint})=(\texttt{seed},\texttt{fingerprint}).
\end{aligned}
$$


At **block boundary**, assert `count_rows[k] == final_count[k]` and reset. Abort on any breach; do not publish. These checks are the same predicates listed in S8.3/S8.6 and mirrored by S9.

---

## 6) Overflow guard & abort semantics

Let $U=999{,}999$ (6 digits). If **any** $n_{m,c}>U$:

* Emit **exactly one** `site_sequence_overflow(m,c)` event (non-consuming envelope).
* **Do not** stage `outlet_catalogue` rows.
* **Abort** the publish for this `(seed,fingerprint)`.
  The presence of overflow events **implies** absence of an egress partition for that fingerprint.

---

## 7) Throughput formulas & capacity planning

**Definitions.**

* $r_w$ = sustained row write rate per writer (rows/s) after encoding + compression.
* $k$ = number of writers (merchant shards) in parallel.
* $T$ = total rows.
* $E$ = number of non-empty $(m,c)$ blocks → count of `sequence_finalize` events.

**Wall-clock write time (idealised):**

$$
t_{\text{emit}} \approx \frac{T}{k \cdot r_w} \quad (\text{not including validation & rename}).
$$

**Staging validation time.** With on-the-fly checks, incremental overhead is **O(1)** per row; the dominant fixed cost is **schema/PK/FK scan** of the staged files which is linear in file bytes and usually overlaps with writer flushes. (If you stream strictly in key order, no global sort is needed.)

**Log volume.** `sequence_finalize` produces **E** JSONL records; `site_sequence_overflow` produces **at most 1** per offending block and aborts. Both events are tiny envelopes with no RNG draw.

---

## 8) Monitoring, SLOs & alerts (binding where stated)

**SLO-S8-01 (schema & keys):** 100% of staged partitions pass schema, PK uniqueness, and FK checks before publish. **Alert** on any `E-S8.5-SCHEMA` / `E-S8.5-PK-DUP` / `E-S8.5-ECHO`.

**SLO-S8-02 (event sync):** For a successful publish, `count(sequence_finalize) == E` and **zero** overflows; envelope counters are non-advancing and reconcile to **draws=0** in `rng_trace_log`. **Alert** on `E-S8.5-EVENTSYNC` / `E-S8.6-RNGZERO`.

**SLO-S8-03 (immutability):** 0 overwrites of existing partitions; any attempt to republish triggers `E-S8.5-IMMUTABLE-EXISTS`. **Alert** and block job.

**SLO-S8-04 (gate integrity):** 1B reads only **after** `_passed.flag` content hash matches `SHA256(validation_bundle_1A)` for the same fingerprint. Missing/invalid gate is a **hard block**.

---

## 9) Failure, retry & idempotence matrix

| Failure point            | Example error              | Effect                    | Allowed action                                           |
|--------------------------|----------------------------|---------------------------|----------------------------------------------------------|
| Preflight / overflow     | `site_sequence_overflow`   | No staging, abort         | Fix inputs or reduce $n_{m,c}$; rerun                    |
| During stream            | Domain/PK/FK breach        | Abort shard; no publish   | Fix; rerun shard(s)                                      |
| Validation (stage)       | Event mismatch / echo fail | Abort; remove `_staging/` | Fix; restage & re-validate                               |
| Atomic rename            | Filesystem error           | `_staging/` remains       | Retry rename or roll back; **never** partial-write final |
| Re-run on existing final | `E-S8.5-IMMUTABLE-EXISTS`  | Guarded                   | Do not overwrite; new fingerprint on change              |

---

## 10) Retention, licensing & PII

* `outlet_catalogue`: **retention 365 days**, `pii: false`, licence `Proprietary-Internal` (dataset dictionary). RNG events & validation artefacts follow their own retention policies (RNG logs typically 180 days; validation bundle per registry). Consumers must verify the **gate** before reading.

---

## 11) Ops recipes (deterministic writer patterns)

**A. Single-node writer (reference).**

1. Iterate merchants ascending; within each merchant, iterate `legal_country_iso` ascending.
2. For block $(m,c)$ with $n_{m,c}>0$, emit rows `site_order=1..n_{m,c}`, `site_id=zpad6(site_order)`; otherwise skip.
3. Maintain on-the-fly predicates (§5); at block end, emit one `sequence_finalize`.
4. Flush Parquet parts under `_staging/`; run validator; atomic rename.

**B. Sharded writer (multi-node).**

* Partition by merchant ranges; each shard writes **ordered** rows to the **same** `_staging/` directory with unique part files.
* A single coordinator runs validation against `_staging/` and performs the **one** atomic rename.
* If any shard reports overflow, emit events and **do not** validate or rename.

---

## 12) Conformance & load tests (must/should)

1. **Scale linearity (must):** Double $T$ with fixed $k$ → `t_emit` doubles within 10% tolerance (same hardware). ✔︎ (Confirms $\Theta(T)$).
2. **Deterministic replay (must):** Same inputs, different shard counts $k\in\{1,4,16\}$ → **identical** row content (and, if concatenated deterministically, identical part listings). ✔︎
3. **Overflow abort (must):** Inject $n_{m,c}=1{,}000{,}005$ → `site_sequence_overflow` present; **no** egress partition published. ✔︎
4. **Event zero-draw (must):** Doctor one event to advance counters → validator fails with `RNGZERO`; publish blocked. ✔︎
5. **Immutability guard (must):** Create final partition then rerun → `IMMUTABLE-EXISTS`; no overwrite. ✔︎

---

## 13) What S9 will re-prove (for the gate)

S9 re-checks: schema/PK/FK, block counts and bijection (`site_id = zpad6(site_order)`), event cardinalities, **zero-draw** envelopes, and writes **`validation_bundle_1A`** plus `_passed.flag` whose **content hash equals** `SHA256(bundle)`. **1B reads only after** this check.

---

### TL;DR (binding bits)

* **Time:** $\Theta(T)$; **memory:** streaming $=$ row-group-bounded.
* **Order:** generate in `(merchant_id, legal_country_iso, site_order)`; no global sort.
* **Overflow:** $n_{m,c}\le 999{,}999$ or abort with event.
* **Publish:** stage → validate → **atomic rename**; partition **immutable**; verify **gate** before 1B.

That closes S8.7 with the exact complexity, streaming, concurrency, and ops contract consistent with the locked spec, schema, registry, and dictionary.

---