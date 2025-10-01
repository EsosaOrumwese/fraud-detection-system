# S8.1 — State, notation & row model

## Scope

Fix the **authorities**, **symbols**, and the **per-row contract** for the egress dataset **`outlet_catalogue`**. This section does not consume RNG; it establishes exactly what inputs S8 needs and what a row means so that S8.2 can expand rows deterministically.

---

## 1) Authorities & lineage (must-use inputs)

**Lineage keys (from S0; immutable within a run):**

* `manifest_fingerprint = F` (hex64, lowercase) — also the egress partition “fingerprint”. **Rows must echo this value** in-column (`manifest_fingerprint`).
* `global_seed = S_master` (u64; **policy:** ≤ 2^63−1 for engine compatibility) — the master RNG seed for the run; echoed per row as `global_seed`. *(S8 uses **no** RNG, but the seed is part of lineage.)*
* `parameter_hash = P` (hex64) — parameter universe digest used by upstream states; not an egress partition key, but **required** for event partitions and reconciliation.
* `run_id` (hex32) — **logs only**; never participates in egress partitioning.

**Partition echo identity (normative):**
For every persisted row: `seed == global_seed` and `fingerprint == manifest_fingerprint`.

**Country membership & order (sole authority):**

* `country_set(seed, parameter_hash)` provides, per merchant $m$, an **ordered** ISO-2 tuple
  $\mathcal{C}_m=(c_0,\dots,c_{K_m})$ with **exactly one** home row `rank(c_0)=0`, and unique ISO codes overall; **this is the only source of inter-country order** (egress never encodes it).

**Final integer allocations (from S7):**

* $n_{m,c}\in\mathbb{Z}_{\ge 0}$ is the **largest-remainder** site count for merchant $m$ and legal country $c\in\mathcal{C}_m$. Residual order evidence lives in the parameter-scoped cache; S8 does **not** re-derive it.

**Merchant-level provenance (carried into egress rows):**

* `single_vs_multi_flag` — **boolean** (true = multi-site). *(Implied: `raw_nb_outlet_draw==1` ⇒ false; otherwise true.)*
* `raw_nb_outlet_draw = N_m` — the merchant’s **accepted Negative-Binomial total** (after hurdle, before cross-country allocation). **In S8 this equals the conservation sum** $\sum_{c\in\mathcal{C}_m} n_{m,c}$ and is written identically on every row for merchant $m$.
* `home_country_iso` — equals the ISO of the unique `rank=0` entry $c_0$ for $m$ (merchant-constant).

**Pre-flight presence tests (abort S8 if any fail):**

1. `country_set` exists for all merchants in scope and has exactly one `rank=0` per merchant; ISO codes are unique per merchant.
2. $\{n_{m,c}\}$ is available for **every** $(m,c)\in\mathcal{C}_m$.
3. Lineage triplet $(F,\ S_{\text{master}},\ P)$ is present and well-typed.

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

* **PK:** (`merchant_id`, `legal_country_iso`, `site_order`).
* **Write order (and file sort):** lexicographic by that same tuple.
* **Policy:** **no inter-country order** is encoded here; consumers must join `country_set.rank`.

---

## 3) Notation & encoders (normative)

Let:

* $\mathcal{M}$ be the merchant set in scope.
* For $m\in\mathcal{M}$, $\mathcal{C}_m=(c_0,\ldots,c_{K_m})$ from `country_set`.
* $n_{m,c}\in\mathbb{Z}_{\ge 0}$ are final counts from S7.
* **Merchant total (conservation):**

  $$
  N_m\ :=\ \sum_{c\in\mathcal{C}_m} n_{m,c}\ \in\ \mathbb{Z}_{\ge 1}.
  $$

  S8 writes $\texttt{raw _nb _outlet _draw}=N_m$ on **every** row of merchant $m$.

**Overflow threshold (six-digit site ids):**

$$
U \;=\; 999{,}999.
$$

If any $n_{m,c}>U$, S8 will later emit a `site_sequence_overflow` (zero-draw) and **abort** egress for this fingerprint. (Defined here; enforced in S8.4/S8.5.)

**Fixed site-id encoder (bijection inside a block):**
Define $\sigma:\{1,\ldots,U\}\to\{0,1\}^6$ (decimal string) by **left-padding to six digits** in the **C locale (ASCII digits)**:

$$
\sigma(j) \;=\; \text{zpad6}(j)\quad\text{(e.g., }1\mapsto\text{"000001"}\text{)}.
$$

Inside a given $(m,c)$ block, $\sigma$ is injective and yields `site_id` that matches `^[0-9]{6}$`. Because `site_order ≥ 1`, `site_id="000000"` is **unreachable**.

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
* **PK tuple** (`merchant_id`,`legal_country_iso`,`site_order`) is therefore **unique**.
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
3. **Determinism.** S8 is a pure function of $(\{n_{m,c}\},F,S_{\text{master}})$; there are **no** RNG draws in S8. *(S8’s RNG events, introduced later, are **zero-draw** attestations.)*

---

## 6) Minimal pre-S8.2 validator (reference)

```pseudo
function s8_1_preflight(m, C_m, n_map, F, S_master, P):
    # C_m: ordered list of ISO for merchant m from country_set (rank 0..K_m)
    assert len(C_m) >= 1 and rank(C_m[0]) == 0                     # unique home
    assert unique(C_m)                                              # ISO uniqueness

    # lineage present
    assert is_hex64(F) and is_uint64(S_master) and is_hex64(P)

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
* emit exactly $n_{m,c}$ rows with `site_order = 1..n_{m,c}`, `site_id = zpad6(site_order)` (C locale),
* place the deterministic **write order** (`merchant_id`, `legal_country_iso`, `site_order`),
* and stage the partition under `…/seed={seed}/fingerprint={F}/` for validation and atomic commit.

---

### Column domains & keys (from schema; for quick reference)

* `site_id` matches `^[0-9]{6}$`;
* `raw_nb_outlet_draw ≥ 1` and is **constant per merchant**; additionally $\texttt{raw _nb _outlet _draw} = \sum_c \texttt{final _country _outlet _count}$ (conservation);
* `final_country_outlet_count ∈ {1,…,999999}`;
* `site_order ≥ 1`;
* FK for both ISO-2 fields to the canonical ISO dataset;
* **PK:** (`merchant_id`, `legal_country_iso`, `site_order`); partitions (`seed`, `fingerprint`).

---

This locks the **inputs**, **symbols**, and the **row semantics** with exact domains and authorities, so we can implement S8.2’s deterministic expansion without guesswork.

---

# S8.2 — Deterministic construction of per-country sequences

## Scope & purpose

For each merchant–country block $(m,c)$ with integerised count $n_{m,c}\ge 0$ (from S7), materialise **exactly $n_{m,c}$** rows in **`egress/outlet_catalogue`**, encoding **within-country** order only. S8 consumes **no RNG**; it is a pure function of $\{n_{m,c}\}$, the run’s `manifest_fingerprint` $F$ and `global_seed` $S_{\text{master}}$.

---

## Authoritative dataset contract (target, keys, domains)

* **Target path & partitions (fixed):**
  `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet`
  partitions: `["seed","fingerprint"]`.
  **PK:** `["merchant_id","legal_country_iso","site_order"]`.
  **Sort keys / write order:** the same tuple.
  **Inter-country order is NOT encoded** here; consumers must join `alloc/country_set.rank`.

* **Selected column domains (enforced at write):**
  `site_id` matches `^[0-9]{6}$`; `raw_nb_outlet_draw ≥ 1`; `final_country_outlet_count ∈ {1,…,999999}`; `site_order ≥ 1`; both ISO fields FK to canonical ISO.
  Cross-field: $1 \le \texttt{site_order} \le \texttt{final _country _outlet _count}$.

---

## Inputs (MUST) and fixed encoders

For merchant $m$ with **ordered** country set $\mathcal{C}_m$ from `country_set` (unique `rank=0` home), S8 receives: $n_{m,c}\in\mathbb{Z}_{\ge 0}$ for each $c\in\mathcal{C}_m$, and run lineage $F,S_{\text{master}},P{=}\texttt{parameter _hash}$.

* **Merchant totals (conservation, normative):**

  $$
  N_m \;:=\; \sum_{c\in\mathcal C_m} n_{m,c}\ \in\ \mathbb Z_{\ge 1}.
  $$

  S8 writes `raw_nb_outlet_draw = N_m` **identically** on every row of merchant $m$.
  *This removes any dependency on a “wide record.”*

* **Implied single/multi flag:** `single_vs_multi_flag = (N_m > 1)` (if not supplied as boolean upstream, cast at write).

* **Home country:** `home_country_iso = c_0`, where `rank(c_0)=0` in `country_set` for $m$.

* **Overflow threshold:** $U=999{,}999$.

* **Site-id encoder (C locale):** $\sigma(j)=\text{zpad6}(j)$ for $j\in\{1,\dots,U\}$ using **ASCII digits**. Because $j\ge 1$, `"000000"` is unreachable.

---

## Normative construction

### (A) Central pre-scan for overflow (exactly-once, then abort)

Before emitting **any** rows:

1. Build $\mathcal{O}=\{(m,c): n_{m,c}>U\}$.
2. If $\mathcal{O}\neq\varnothing$:

   * Let $(m^\*,c^\*)=\min_{\text{lex}} \mathcal{O}$ under `(merchant_id, legal_country_iso)`.
   * **Emit exactly one** zero-draw `site_sequence_overflow` with payload:

     ```json
     {
       "merchant_id": m*,
       "legal_country_iso": c*,
       "attempted_count": n_{m*,c*},
       "max_seq": 999999,
       "overflow_by": n_{m*,c*} - 999999,
       "severity": "ERROR"
     }
     ```

     Path: `logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
     Schema: `schemas.layer1.yaml#/rng/events/site_sequence_overflow`
   * **Abort** the egress build for this `(seed,fingerprint)` — no staging, no partials.

*(This ensures 0/1 overflow events under sharding.)*

### (B) Per-block sequence space

For each $(m,c)$, define

$$
\mathcal{J}_{m,c}=\{1,2,\dots,n_{m,c}\}.
$$

If $n_{m,c}=0$ then $\mathcal{J}_{m,c}=\varnothing$ and **no rows** are emitted for that block.

### (C) Row expansion (pure map)

For each $(m,c)$ with $n_{m,c}>0$, and for each $j\in\mathcal{J}_{m,c}$, **emit one row**:

$$
\begin{aligned}
&\texttt{merchant_id}=m,\qquad \texttt{legal _country _iso}=c,\\
&\texttt{site _order}=j,\qquad \texttt{site _id}=\sigma(j)\ \ (\text{6 digits, C locale}),\\
&\texttt{home _country _iso}=c_0,\quad
  \texttt{single _vs _multi _flag}=(N_m>1),\\
&\texttt{raw _nb _outlet _draw}=N_m,\quad
  \texttt{final _country _outlet _count}=n_{m,c},\\
&\texttt{manifest _fingerprint}=F,\quad \texttt{global _seed}=S_{\text{master}}.
\end{aligned}
$$

*Single-site trivial case:* if $N_m=1$, the only non-empty block is $c_0$ with $n_{m,c_0}=1$; S8 emits exactly **one** row with `site_order=1`, `site_id="000001"`.

### (D) Write-stability ordering (must)

Generate (or sort) rows **lexicographically** by
$(\texttt{merchant _id},\texttt{legal _country _iso},\texttt{site _order})$.
This matches the dataset’s sort keys and guarantees byte-stable output across platforms. **Inter-country order is not encoded**; consumers use `country_set.rank`.

### (E) Audit attestation (non-consuming)

For each non-empty block $(m,c)$, **emit exactly one** zero-draw `sequence_finalize` with payload:

```json
{
  "merchant_id": m,
  "legal_country_iso": c,
  "site_count": n_{m,c},
  "start_sequence": "000001",
  "end_sequence": "<zpad6(n_{m,c})>"
}
```

Path: `logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
Schema: `schemas.layer1.yaml#/rng/events/sequence_finalize`.

Counters are non-advancing (`before==after`); see S8.4.

---

## Invariants (MUST hold)

1. **Row count:** For every $(m,c)$, the number of materialised rows equals $n_{m,c}$; for $n_{m,c}=0$ there are **zero** rows.
2. **Within-block order & bijection:** Inside a block, `site_order` is a **gap-free** $\{1..n_{m,c}\}$ and `site_id = zpad6(site_order)`; thus `site_id` is unique **within the block**.
3. **Write order:** Rows are written in `(merchant_id, legal_country_iso, site_order)` lexicographic order.
4. **Partition echo:** For every row, `seed == global_seed` and `fingerprint == manifest_fingerprint`.
5. **Merchant conservation & constants:** For each merchant $m$:
   $\texttt{raw _nb _outlet _draw} = \sum_c \texttt{final _country _outlet _count}$ and is identical on every row; `home_country_iso` and `single_vs_multi_flag` are merchant-constant.
6. **No RNG:** S8 emits only **zero-draw** events; `draws=0` and `after==before` in their envelopes (asserted in S8.4).

---

## Error handling (abort semantics)

Abort S8 for the merchant-set/partition if any occurs:

* `E-S8.2-OVERFLOW` — handled by **(A)**: one `site_sequence_overflow` event, then abort; **no** egress written.
* `E-S8.2-DOMAIN` — a to-be-emitted row would violate schema domain/range/regex (e.g., `site_order<1`, `site_id` not `^[0-9]{6}$`, `final_country_outlet_count<1` for a persisted row).
* `E-S8.2-PK-DUP` — duplicate `("merchant_id","legal_country_iso","site_order")` within staged output. (Should be impossible; still enforced.)
* `E-S8.2-ECHO` — any row’s `global_seed` or `manifest_fingerprint` doesn’t equal the partition tokens. (Checked at write.)
* `E-S8.2-ATTEST` — required zero-draw event emission fails for either label. *(Caller must fail the build; S8.4 reconciles payload and envelope counters.)*

---

## Reference pseudocode (deterministic; language-agnostic)

```pseudo
function s8_2_construct_and_stage(F, S_master, parameter_hash, country_set, counts):
    # country_set: iterable of (merchant_id=m, legal_country_iso=c, rank, is_home)
    # counts: map[(m,c)] -> n >= 0

    # ---- (A) pre-scan overflow ----
    offenders := []
    for (m,c) in country_set:
        n := counts[(m,c)]
        if n > 999999: offenders.append((m,c,n))
    if not empty(offenders):
        (m*, c*, n*) := lexicographic_min(offenders by (m,c))
        emit_event(
            label="site_sequence_overflow", draws=0,
            payload={
              merchant_id:m*, legal_country_iso:c*,
              attempted_count:n*, max_seq:999999, overflow_by:n*-999999,
              severity:"ERROR"
            },
            seed=S_master, parameter_hash=parameter_hash, manifest_fingerprint=F
        )
        abort("E-S8.2-OVERFLOW")

    # ---- compute merchant totals & home ----
    by_merchant := group counts by m
    STAGE := []

    for m in sort(keys(by_merchant)):
        N_m := sum(n for (_, n) in by_merchant[m])        # conservation definition
        home := iso_with_rank0(country_set, m)
        H := (N_m > 1)

        for (c, n) in by_merchant[m]:
            if n == 0: continue
            for j in 1..n:
                STAGE.append({
                  manifest_fingerprint: F,
                  merchant_id: m,
                  site_id: zpad6(j),                       # C locale, ASCII digits
                  home_country_iso: home,
                  legal_country_iso: c,
                  single_vs_multi_flag: H,
                  raw_nb_outlet_draw: N_m,
                  final_country_outlet_count: n,
                  site_order: j,
                  global_seed: S_master
                })

            emit_event(
              label="sequence_finalize", draws=0,
              payload={
                merchant_id:m, legal_country_iso:c,
                site_count:n, start_sequence:"000001", end_sequence:zpad6(n)
              },
              seed=S_master, parameter_hash=parameter_hash, manifest_fingerprint=F
            )

    # ---- (D) write-stability ----
    STAGE.sort_by((merchant_id, legal_country_iso, site_order))
    parquet_write("data/layer1/1A/outlet_catalogue/seed={S_master}/fingerprint={F}/", STAGE)
```

---

## Conformance tests (must-pass)

1. **Zero-block:** $n_{m,c}=0$ → no rows for that $(m,c)$. Table remains valid and ordered.
2. **Happy path:** $n_{m,c}=3$ → three rows; `site_order=[1,2,3]`; `site_id=["000001","000002","000003"]`; `final_country_outlet_count=3` constant; PK unique; one `sequence_finalize` with `start="000001"`, `end="000003"`.
3. **Overflow (centralised):** some $n_{m,c}=1{,}000{,}000$ → **one** `site_sequence_overflow` with `attempted_count=1_000_000`, `max_seq=999_999`, `overflow_by=1`; **no** egress staged/written.
4. **Write order:** Generate rows out of order intentionally; final files must be sorted by `(merchant_id, legal_country_iso, site_order)`.
5. **Domain guard:** Inject `site_id="12345"` (5 digits) or persist a row with `final_country_outlet_count=0` → schema validator rejects with `E-S8.2-DOMAIN`.
6. **Partition echo:** All rows echo `seed==global_seed` and `fingerprint==manifest_fingerprint`; otherwise `E-S8.2-ECHO`.
7. **Conservation:** For each merchant, $\sum_c \texttt{final _country _outlet _count} = \texttt{raw _nb _outlet _draw}$ across that merchant’s rows.

---

## Complexity & determinism

Let $T=\sum_m\sum_{c\in\mathcal{C}_m} n_{m,c}$. Construction is $\Theta(T)$ time and output size; sorting is linear if rows are generated in key order (or $T\log T$ if you materialise then sort). With fixed $(\{n_{m,c}\},F,S_{\text{master}})$, replay is **byte-stable**.

---

This locks S8.2: exact expansion rules, **centralised overflow** guard, conservation-defined merchant totals, aligned event payloads, partition echoes, write-stability, and conformance tests — all wired to your schema and registry.

---

# S8.3 — Keys, domains, cross-field constraints & validator (schema-tight)

## Scope

This sub-state turns the egress schema for **`outlet_catalogue`** into **executable predicates**: primary/partition/sort keys, column domains (types, ranges, regex), **cross-field** rules (`site_id = zpad6(site_order)`, per-block constants), **additional uniqueness** (within-block `site_id`), **FK**s, **echo invariants** (row ↔ partition), and **merchant-level conservation**. These rules are enforced at write-time, then mirrored by S9.

---

## Authoritative dataset contract (path, keys, schema)

* **Path & partitions (fixed):**
  `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet`
  with **partition keys** `["seed","fingerprint"]`. Writer must ensure every row echoes `global_seed==seed` and `manifest_fingerprint==fingerprint`.

* **Primary key (PK):** `["merchant_id","legal_country_iso","site_order"]`.
  **Sort keys / write order:** same tuple — `(merchant_id, legal_country_iso, site_order)`.
  **Policy:** **Inter-country order is not encoded** (consumers join `country_set.rank`).

* **Schema ref:** `schemas.1A.yaml#/egress/outlet_catalogue`. (Columns and constraints below copy that schema exactly.)

* **Schema extension (uniqueness note):**
  `x-unique-keys: [["merchant_id","legal_country_iso","site_id"]]`
  *(Within-block `site_id` uniqueness; no global uniqueness across countries or merchants.)*

* **Registry notes / gate:** Depends on `country_set` and RNG event streams (`sequence_finalize`, `site_sequence_overflow`).
  **Producer module:** `1A.site_id_allocator` (a **module**, not a dataset).
  1B may read **only after** `_passed.flag` matches `SHA256(validation_bundle_1A)` for the same fingerprint.

---

## Column domains (normative — from schema)

For every persisted row:

* `manifest_fingerprint`: **string**, pattern `^[a-f0-9]{64}$` (lowercase hex64). **Must equal** partition `{fingerprint}`.
* `merchant_id`: `id64` (non-null).
* `site_id`: **string**, `^[0-9]{6}$` (six decimal digits; zero-padded). *(Reachable set excludes `"000000"` because `site_order ≥ 1` — see cross-field rules.)*
* `home_country_iso`: ISO-2 with FK → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024.country_iso`.
* `legal_country_iso`: ISO-2 with the **same FK**.
* `single_vs_multi_flag`: **boolean** (writer may cast upstream {0,1} → bool at write).
* `raw_nb_outlet_draw`: `int32`, **minimum 1** (merchant-constant).
* `final_country_outlet_count`: `int32`, **minimum 1**, \*\*maximum 999999\`.
* `site_order`: `int32`, **minimum 1**. *(Upper bound tied by cross-field constraint.)*
* `global_seed`: `uint64`. **Must equal** partition `{seed}`.

**Cross-field domain (schema-declared):**

$$
\boxed{\,1 \le \texttt{site _order} \le \texttt{final _country _outlet _count}\,}.
$$

---

## Cross-field constraints (normative — beyond column types)

1. **Site-ID encoder (bijection in block).**
   Within each $(m,c)$: `site_id == zpad6(site_order)` using the **C locale (ASCII digits)**.
   Implications: `site_id` is **unique within the block** (bijective with `site_order ∈ {1..n_{m,c}}`); `"000000"` is **unreachable**.

2. **Block constants (groupwise).**
   For a fixed $(m,c)$: `final_country_outlet_count` is **constant** and equals the block size, and `legal_country_iso == c` for **all** rows; hence

$$
\#\{\text{rows for }(m,c)\} = \texttt{final _country _outlet _count}.
$$

3. **Merchant constants & conservation.**
   For each merchant $m$:

* `raw_nb_outlet_draw` is **constant** across all rows for $m$, and
* **Conservation (must-hold):**

  $$
  \texttt{raw _nb _outlet _draw}(m)\ =\ \sum_{c}\ \texttt{final _country _outlet _count}(m,c).
  $$
* `single_vs_multi_flag` and `home_country_iso` are **merchant-constant**.
  *(Equality of `home_country_iso` to the rank-0 ISO in `country_set` is asserted in S9 policy tests.)*

4. **Partition echo invariants.**
   Every row: `global_seed == {seed}` and `manifest_fingerprint == {fingerprint}`.

5. **Inter-country order separation (policy).**
   Egress **must not** encode cross-country order; consumers **must** join `alloc/country_set.rank` (0=home; foreigns in Gumbel order).

6. **Overflow limit (defense-in-depth).**
   No block may have `final_country_outlet_count > 999999`. If observed in staged content, treat as a hard error (overflow should have been pre-scanned in S8.2).

---

## Formal constraints (equational form)

**Encoder identity (per row):**

$$
\boxed{\,\texttt{site _id}=\text{zpad6}(\texttt{site _order})\,}.
$$

**Within-block uniqueness:**

$$
\forall (m,c):\ \ \mathrm{Unique}\big(\{\texttt{site _id}:(m,c,*)\}\big).
$$

**Merchant conservation:**

$$
\forall m:\ \ \texttt{raw _nb _outlet _draw}(m)\ =\ \sum_{c} \texttt{final _country _outlet _count}(m,c).
$$

**Block constancy:**

$$
\forall (m,c):\ \ \texttt{final _country _outlet _count}\ \text{is constant over the block}.
$$

---

## Error codes (abort semantics)

On the staged partition (prior to atomic commit):

* `E-S8.3-PK-DUP` — duplicate PK `(merchant_id, legal_country_iso, site_order)`.
* `E-S8.3-SITEID-DUP` — duplicate `site_id` within the same `(merchant_id, legal_country_iso)` block.
* `E-S8.3-DOMAIN` — column domain breach (regex/min/max/type).
* `E-S8.3-CROSSFIELD` — cross-field breach (`1 ≤ site_order ≤ final_country_outlet_count` **or** `site_id != zpad6(site_order)`).
* `E-S8.3-BLOCKCONST` — within a block, `final_country_outlet_count` not constant **or** `#rows != final_country_outlet_count`.
* `E-S8.3-MERCHCONST` — merchant constants drift (`raw_nb_outlet_draw`, `single_vs_multi_flag`, `home_country_iso`).
* `E-S8.3-CONSERVATION` — for any merchant, $\sum_c \texttt{final _country _outlet _count} \ne \texttt{raw _nb _outlet _draw}$.
* `E-S8.3-FK-ISO` — `home_country_iso` or `legal_country_iso` not in canonical ISO (FK breach).
* `E-S8.3-ECHO` — partition echo mismatch (row vs directory tokens).
* `E-S8.3-OVERFLOW` — any block with `final_country_outlet_count > 999999` observed in staged content (should be pre-blocked by S8.2). Abort; ensure a `site_sequence_overflow` exists; no commit.

---

## Reference validator (single-pass, implementation-ready)

Runs **before** S8.5’s atomic publish against the **staging** output for `(seed, fingerprint)`.

```pseudo
function validate_outlet_catalogue_stage(seed, fingerprint, rows_iter):
    seen_pk      := HashSet()                           # (m,c,j)
    seen_siteid  := HashMap<(m,c), HashSet>()           # site_id uniqueness within block
    block_rows   := HashMap<(m,c), int64>()             # observed rows per block
    block_fcount := HashMap<(m,c), int32>()             # asserted final_country_outlet_count
    merch_draw   := HashMap<m, int32>()                 # merchant-constant draw
    merch_flag   := HashMap<m, bool>()                  # merchant-constant flag
    merch_home   := HashMap<m, ISO2>()                  # merchant-constant home ISO
    merch_sum    := HashMap<m, int64>()                 # sum of final_country_outlet_count per merchant

    for row in rows_iter:
        # Echo invariants
        if not (row.global_seed == seed and row.manifest_fingerprint == fingerprint):
            raise E-S8.3-ECHO

        # Column domains / regex / FK
        if not matches(row.manifest_fingerprint, "^[a-f0-9]{64}$"): raise E-S8.3-DOMAIN
        if not matches(row.site_id, "^[0-9]{6}$"): raise E-S8.3-DOMAIN
        if row.raw_nb_outlet_draw < 1: raise E-S8.3-DOMAIN
        if row.final_country_outlet_count < 1 or row.final_country_outlet_count > 999999: raise E-S8.3-DOMAIN
        if row.site_order < 1: raise E-S8.3-DOMAIN
        if not (is_valid_iso2(row.home_country_iso) and is_valid_iso2(row.legal_country_iso)):
            raise E-S8.3-FK-ISO

        # Cross-field rules
        if row.site_order > row.final_country_outlet_count: raise E-S8.3-CROSSFIELD
        if row.site_id != zpad6(row.site_order): raise E-S8.3-CROSSFIELD

        # PK uniqueness
        pk := (row.merchant_id, row.legal_country_iso, row.site_order)
        if not add_unique(seen_pk, pk): raise E-S8.3-PK-DUP

        # Block invariants
        k := (row.merchant_id, row.legal_country_iso)
        block_rows[k] = block_rows.get(k, 0) + 1
        if k not in block_fcount:
            block_fcount[k] = row.final_country_outlet_count
        else:
            if block_fcount[k] != row.final_country_outlet_count: raise E-S8.3-BLOCKCONST

        S := seen_siteid.get_or_create(k, HashSet())
        if not add_unique(S, row.site_id): raise E-S8.3-SITEID-DUP

        # Merchant constants & conservation tally
        m := row.merchant_id
        if m not in merch_draw: merch_draw[m] = row.raw_nb_outlet_draw
        else: if merch_draw[m] != row.raw_nb_outlet_draw: raise E-S8.3-MERCHCONST

        if m not in merch_flag: merch_flag[m] = row.single_vs_multi_flag
        else: if merch_flag[m] != row.single_vs_multi_flag: raise E-S8.3-MERCHCONST

        if m not in merch_home: merch_home[m] = row.home_country_iso
        else: if merch_home[m] != row.home_country_iso: raise E-S8.3-MERCHCONST

        merch_sum[m] = merch_sum.get(m, 0) + row.final_country_outlet_count

    # Post-pass checks
    for k in block_rows.keys():
        if block_rows[k] != block_fcount[k]: raise E-S8.3-BLOCKCONST
        if block_fcount[k] > 999999: raise E-S8.3-OVERFLOW

    for m in merch_sum.keys():
        if merch_sum[m] != merch_draw[m]: raise E-S8.3-CONSERVATION

    return OK
```

* `is_valid_iso2` performs the FK test by joining the canonical ISO dataset embedded in the schema.
* This validator is **O(T)** over $T$ rows; memory is proportional to the number of blocks/merchants in the staged partition.

---

## Conformance tests (must-pass)

1. **Happy path / small block.** $(m,c)$ with $n_{m,c}=3$: `site_order=[1,2,3]`, `site_id=["000001","000002","000003"]`, `final_country_outlet_count=3`; PK unique; `site_id` unique within block. ✔︎
2. **Zero-block elision.** If $n_{m,c}=0$, there are **no rows** for $(m,c)$. ✔︎
3. **Partition echo mismatch.** Valid row data but `global_seed` ≠ partition `seed` → `E-S8.3-ECHO`. ✔︎
4. **Site-ID collision.** Duplicate `site_id` within a block → `E-S8.3-SITEID-DUP` / `E-S8.3-CROSSFIELD`. ✔︎
5. **Block-constant drift.** `#rows != final_country_outlet_count` or value not constant → `E-S8.3-BLOCKCONST`. ✔︎
6. **Merchant constant drift.** Change `raw_nb_outlet_draw` mid-merchant → `E-S8.3-MERCHCONST`. ✔︎
7. **Conservation breach.** $\sum_c \texttt{final _country _outlet _count}$ ≠ `raw_nb_outlet_draw` → `E-S8.3-CONSERVATION`. ✔︎
8. **Domain guard.** `final_country_outlet_count=1_000_000` or `site_id="12345"` → `E-S8.3-DOMAIN` (and/or `E-S8.3-OVERFLOW`). ✔︎
9. **FK breach.** `legal_country_iso="ZZ"` not in canonical ISO → `E-S8.3-FK-ISO`. ✔︎

---

## Why this matters (auditability & hand-off)

These predicates make S8’s output **mechanically checkable** and replayable: PK/partition/echo ensure immutability; domain & regex prevent malformed IDs; **within-block bijection** fixes the semantics of `site_id`; **conservation** ties the merchant total to per-country counts; FK prevents drift in country codes; and separation of inter-country order avoids policy leakage. With the 1B gate (`_passed.flag` equals `SHA256(validation_bundle_1A)`), downstream will only ever read a partition that satisfies all of the above.

---

# S8.4 — Event emission (audit trail)

## 1) Purpose & scope (normative)

S8 constructs **within-country** site sequences *without consuming RNG*. It must still emit *structured RNG events* to (a) attest what was written and (b) keep Philox lineage continuous. Labels in scope:

* **`sequence_finalize`** — one **non-consuming** attestation per **non-empty** $(m,c)$ block. Role: “Final sequence allocation per (merchant,country) block.”
* **`site_sequence_overflow`** — **non-consuming** guardrail when $n_{m,c}>999{,}999$; emitted **once** per `(seed,fingerprint)` then the build **aborts** (no egress).

All RNG events carry the **common envelope** (`rng_envelope`) including `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label`, and **Philox before/after counters**; **non-consuming ⇒ `before == after`** for both 64-bit limbs.

Partitions for both streams are fixed as:
`seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}`.

---

## 2) Event schemas & payload contracts

### 2.1 Common envelope (shared by all events)

Minimum required envelope fields (see schema for the full set):

```
required: [
  ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
  module, substream_label,
  rng_counter_before_lo, rng_counter_before_hi,
  rng_counter_after_lo,  rng_counter_after_hi
]
```

**Non-consuming invariant:**
`rng_counter_before_lo == rng_counter_after_lo` AND
`rng_counter_before_hi == rng_counter_after_hi`.

Pinned producer: `module = "1A.site_id_allocator"`.

---

### 2.2 `sequence_finalize` (schema & math)

**Payload fields (normative):**
`merchant_id ∈ ℕ⁺`, `legal_country_iso ∈ [A-Z]{2}`, `site_count ∈ ℕ⁺`, `start_sequence ∈ ^[0-9]{6}$`, `end_sequence ∈ ^[0-9]{6}$`.

For a realized block $(m,c)$ with $n_{m,c}\ge 1$:

$$
\texttt{site _count}=n_{m,c},\quad
\texttt{start _sequence}=\text{"000001"},\quad
\texttt{end _sequence}=\mathrm{zpad6}(n_{m,c}).
$$

*(If $n_{m,c}=0$, **no event**.)*

**Path:**
`logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
**Schema pointer:** `schemas.layer1.yaml#/rng/events/sequence_finalize`.

---

### 2.3 `site_sequence_overflow` (schema & math)

**Payload fields (normative):**
`merchant_id`, `legal_country_iso`, `attempted_count ∈ ℕ⁺`, `max_seq = 999999` (const), `overflow_by ∈ ℕ⁺`, `severity = "ERROR"`.

Trigger when $n_{m,c}>U$, $U=999{,}999$:

$$
\texttt{attempted _count}=n_{m,c},\quad
\texttt{overflow _by}=n_{m,c}-U.
$$

**Exactly-once policy (per `(seed,fingerprint)`):** emit the **lexicographically first** offending $(m,c)$ under `(merchant_id, legal_country_iso)`, then **abort S8** (no egress).

**Path:**
`logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
**Schema pointer:** `schemas.layer1.yaml#/rng/events/site_sequence_overflow`.

---

## 3) Determinism & RNG-accounting invariants (MUST hold)

**EV-0 (zero-draw):** For both labels, envelope counters **do not advance** (`before == after`); the run’s `rng_trace_log` records **draws = 0** for `(module="1A.site_id_allocator", substream_label=⋅)` and counter deltas reconcile to 0.

**EV-1 (cardinality):**

$$
\#\,\texttt{sequence _finalize}(m,*)=\sum_{c\in\mathcal C_m}\mathbf 1[n_{m,c}\ge 1],\qquad
\#\,\texttt{site _sequence _overflow}\in\{0,1\}.
$$

If overflow is emitted ⇒ **no egress** for the `(seed,fingerprint)` partition.

**EV-2 (payload coherence):** Each `sequence_finalize` satisfies
`site_count = n_{m,c}`, `start_sequence="000001"`, `end_sequence=zpad6(n_{m,c})`, and matches rows in `outlet_catalogue` (S8.2/S8.5).

**EV-3 (catalog conformance):** Stream paths match the registered partitions `{seed, parameter_hash, run_id}` and validate against their schema pointers.

---

## 4) Emission timing & ordering (normative)

1. **Central overflow pre-scan:** if any $n_{m,c}>U$ exists, emit the **single** `site_sequence_overflow` event (non-consuming) and **abort immediately** (no staging, no partials).
2. **Per-block finalize:** after materialising each non-empty block’s rows (S8.2), emit **exactly one** `sequence_finalize` (non-consuming).

**Stability guideline:** emit in the same merchant/country order used for writing `(merchant_id, legal_country_iso, site_order)` to ease forensics. *(Guideline, not a schema constraint.)*

---

## 5) Reference emission algorithm (pseudocode)

```pseudo
const U := 999_999
env := {
  run_id, seed, parameter_hash, manifest_fingerprint,
  module="1A.site_id_allocator"
}

# ---- centralized overflow pre-scan ----
offenders := [(m,c,n) | each block (m,c) with n>U]
if not empty(offenders):
    (m*,c*,n*) := lexicographic_min(offenders by (merchant_id, legal_country_iso))
    C := current_philox_counter()   # (lo,hi)
    emit_jsonl(
      path="logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl",
      record = env + {
        ts_utc=now(), substream_label="site_sequence_overflow",
        rng_counter_before_lo=C.lo, rng_counter_before_hi=C.hi,
        rng_counter_after_lo=C.lo,  rng_counter_after_hi=C.hi
      } + {
        merchant_id:m*, legal_country_iso:c*,
        attempted_count:n*, max_seq:999999, overflow_by:(n*-999999),
        severity:"ERROR"
      }
    )
    abort("ERR_S8_OVERFLOW")  # no egress written

# ---- per-block finalize (after rows materialised) ----
for each non-empty (m,c) in write_order:
    n := n_{m,c}
    C := current_philox_counter()
    emit_jsonl(
      path="logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl",
      record = env + {
        ts_utc=now(), substream_label="sequence_finalize",
        rng_counter_before_lo:C.lo, rng_counter_before_hi:C.hi,
        rng_counter_after_lo:C.lo,  rng_counter_after_hi:C.hi
      } + {
        merchant_id:m, legal_country_iso:c,
        site_count:n, start_sequence:"000001", end_sequence:zpad6(n)
      }
    )
```

---

## 6) JSONL examples (illustrative)

### 6.1 `sequence_finalize` (n=3)

```json
{
  "ts_utc":"2025-08-15T12:00:00Z",
  "run_id":"r2025_08_15_001",
  "seed":1469598103934665603,
  "parameter_hash":"a4c9...d2a1",
  "manifest_fingerprint":"f0ab...9c33",
  "module":"1A.site_id_allocator",
  "substream_label":"sequence_finalize",
  "rng_counter_before_lo":0,
  "rng_counter_before_hi":0,
  "rng_counter_after_lo":0,
  "rng_counter_after_hi":0,

  "merchant_id":123456789,
  "legal_country_iso":"GB",
  "site_count":3,
  "start_sequence":"000001",
  "end_sequence":"000003"
}
```

### 6.2 `site_sequence_overflow` (n=1,000,005)

```json
{
  "ts_utc":"2025-08-15T12:00:00Z",
  "run_id":"r2025_08_15_001",
  "seed":1469598103934665603,
  "parameter_hash":"a4c9...d2a1",
  "manifest_fingerprint":"f0ab...9c33",
  "module":"1A.site_id_allocator",
  "substream_label":"site_sequence_overflow",
  "rng_counter_before_lo":0,
  "rng_counter_before_hi":0,
  "rng_counter_after_lo":0,
  "rng_counter_after_hi":0,

  "merchant_id":123456789,
  "legal_country_iso":"US",
  "attempted_count":1000005,
  "max_seq":999999,
  "overflow_by":6,
  "severity":"ERROR"
}
```

---

## 7) Validation & reconciliation (conformance suite)

1. **JSON-Schema validation** of each record against its pointer; **reject** any envelope or payload violation.
2. **Trace reconciliation:** for $\ell\in\{$`sequence_finalize`,`site_sequence_overflow`$\}$:

   $$
   \sum \texttt{rng _trace _log.draws}\big|_{(module=\text{"1A.site_id_allocator"},\,substream=\ell)}=0,
   \quad
   \sum(C^{after}-C^{before})=0.
   $$
3. **Cardinality checks:** one `sequence_finalize` per non-empty block; **0/1** overflow per `(seed,fingerprint)` and, if present, **no egress partition** for that fingerprint.
4. **Egress cross-check:** for each `sequence_finalize(m,c)`, `outlet_catalogue` has exactly `site_count` rows for $(m,c)$ with `site_order=1..site_count` and `site_id` spanning `start_sequence..end_sequence`.

---

## 8) Failure semantics (normative)

* **ERR _S8 _OVERFLOW** — overflow event emitted; hard abort; no egress.
* **ERR _S8 _EVENT _SCHEMA** — JSON-schema failure on any event record.
* **ERR _S8 _TRACE _MISMATCH** — any non-consuming label shows `draws>0` or counter deltas.
* **ERR _S8 _PATH _PARTITION** — event files not under exact `{seed, parameter_hash, run_id}` partitions.

---

## 9) Operational notes

* `(module, substream_label)` names are **pinned** for lineage and S9 filters.
* The human-readable **event catalog** is **generated from** `schemas.layer1.yaml#/rng/events` and is **non-authoritative**; the JSON-Schemas are the source of truth.

---

## 10) Why this matters downstream

Zero-draw events with strict cardinalities let S9 prove S8’s rows were written **exactly** as specified — no hidden RNG, no re-ordering — and ensure clean abort on overflow (no partial or zombie egress).

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

**Registry dependencies:** `outlet_catalogue` depends (indirectly) on `country_set` → S8 (site _id allocator) → RNG `sequence_finalize` events. 1B consumption is gated by a validation artefact (see §7).

---

## 2) Inputs to the writer (recap)

From S8.2 you have a deterministic stream of rows already in **final write order** `(merchant_id, legal_country_iso, site_order)` with lineage echoes `global_seed=S_master`, `manifest_fingerprint=F`.
Zero-block elision and the **central overflow pre-scan** have run; for every non-empty `(m,c)`, S8.4 emitted **one** `sequence_finalize` (non-consuming). If overflow occurred, S8.4 emitted **one** `site_sequence_overflow` (partition-scoped) and **no rows** exist for this `(seed,fingerprint)`.

---

## 3) Staging & atomic commit (normative)

### 3.1 Two-phase publish

1. **Precondition (immutability guard).**
   If the final partition directory

   ```
   …/outlet_catalogue/seed=S_master/fingerprint=F/
   ```

   already exists **and is non-empty**, **abort**: egress is immutable per `(seed,fingerprint)`.

2. **Stage.**
   Write Parquet parts to a **temporary** directory:

   ```
   stage = …/seed=S_master/fingerprint=F/_staging/
   ```

   Ensure file handles are closed and data is durable (fsync or equivalent).

3. **Validate staged content** (see §4). **Do not** publish if any check fails.

4. **Atomic publish.**
   Atomically **rename/move** `stage` → final partition directory:

   ```
   …/seed=S_master/fingerprint=F/
   ```

   The operation must be metadata-atomic on the backing filesystem (e.g., POSIX `rename(2)`). On failure, best-effort delete `_staging/` and **abort**.

5. **Post-publish rule.**
   After publish, **no further writes** under the partition. All validation artefacts live under `validation/fingerprint=F/` (see §7).

### 3.2 Idempotence & retries

* **Idempotence:** reruns that reach step (1) and detect a non-empty final partition **must stop** (no overwrite).
* **Retry window:** failures **before** rename may safely re-enter from step (2) after cleaning `_staging/`. Failures **after** rename are considered committed.

> **Note (object stores):** if atomic directory rename is unavailable, use a single-writer strategy that writes under `_staging/` and then performs an atomic *directory marker* / manifest publish equivalent. Semantics must be identical to POSIX rename (no partial visibility).

---

## 4) Must-pass validation (write-time, before commit)

Run these checks on **staged** files for `(seed=S_master, fingerprint=F)`; they mirror S8.3 and the schema.

**V-PK & order.**

* `count(rows) == count(distinct merchant_id, legal_country_iso, site_order)`.
* Read of staged parts yields lexicographic `(merchant_id, legal_country_iso, site_order)`. Writer should either stream in that order or sort.

**V-echo (row ↔ path).**

* Every row has `global_seed == S_master` and `manifest_fingerprint == F`.

**V-domains & regex.**

* Enforce schema ranges/patterns:
  `final_country_outlet_count ∈ [1,999999]`, `site_order ≥ 1`, `raw_nb_outlet_draw ≥ 1`, `site_id ~ ^[0-9]{6}$`, both ISO columns pass FK to canonical ISO.

**V-cross-field invariants.**

* Per row: `1 ≤ site_order ≤ final_country_outlet_count`; `site_id == zpad6(site_order)` (C locale).
* Per block `(m,c)`: `final_country_outlet_count` **constant**; `#rows == final_country_outlet_count`; **within-block** `site_id` unique.
* Per merchant: **conservation** — `raw_nb_outlet_draw == Σ_c final_country_outlet_count`.

**V-overflow (defense-in-depth).**

* Assert `max(site_order in block) ≤ 999999`.

**V-events (sync with S8.4).**

* For each **non-empty** `(m,c)` block in staged content, there is **exactly one** non-consuming `sequence_finalize` event under the registered path for the same `{seed, parameter_hash, run_id}` with `site_count=zpad6^{-1}(end_sequence)`.
* For the partition overall, there is **at most one** `site_sequence_overflow` event. If present, then **no staged egress must exist** (this validation fails if rows are present).

> Implement using the S8.3 validator on `stage/` plus an event reader on `logs/rng/events/*/seed=S_master/parameter_hash=…/run_id=…/`.

---

## 5) File layout & performance (binding where stated)

**Write order.** Generate (or sort) rows in `(merchant_id, legal_country_iso, site_order)` to avoid a global `T log T` sort; S8.2 naturally produces this order.

**Deterministic part numbering (binding).**
Name parts `part-00000.parquet`, `part-00001.parquet`, … in **the exact order rows are written** after ordering in the previous bullet. This ensures byte-stable manifests across platforms/shards.

**Row groups (advisory).**
Prefer row groups that do **not** interleave merchants excessively; where feasible, align row-group boundaries to `(merchant_id, legal_country_iso)` to tighten stats and accelerate block scans on `site_order`.

**Compression & metadata (binding where configured).**
Use the registry’s Parquet codec (e.g., Zstd level 3). Write the following file-level key/value metadata for provenance:
`schema_ref`, `seed`, `fingerprint`. *(No new artefacts; in-file metadata only.)*

**Streaming memory bound.**
With streaming writes, peak memory is `O(B)` for the writer’s row-group buffer (64–256 MB typical). S8 invariants are checkable on the fly (sequential `site_order`, block-constant counts).

---

## 6) Concurrency & sharding (determinism-safe)

**Shard by merchant** (or merchant ranges). Each shard must:

1. iterate merchants in ascending `merchant_id`;
2. within a merchant, iterate `legal_country_iso` ascending, emitting `site_order=1..n_{m,c}`;
3. produce shard parts in final key order.

At publish time, **one** of the following must hold:

* **Single merger:** concatenate shard outputs into a single `_staging/` in key order, then perform **one** atomic rename; **or**
* **Single writer to `_staging/`:** coordinated writers append parts **sequentially** in key order (with deterministic part numbering), then **one** atomic rename.

The partition is **immutable**; a single **atomic rename** must occur at the end. If the final partition already exists, **abort** (no overwrite).

---

## 7) Governance, validation bundle & 1B gate

After publishing `outlet_catalogue`, the validation process emits:

* `validation_bundle_1A` at
  `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` (contains schema/PK/FK checks, RNG accounting, metrics), and
* `_passed.flag` in the **same** folder whose **content hash equals** `SHA256(validation_bundle_1A)`.

**Hand-off condition:** **1B may read `outlet_catalogue` only if** `_passed.flag` exists and matches the bundle digest for the **same** fingerprint. This gate is registry-enforced.

---

## 8) Error codes (abort semantics)

* `E-S8.5-IMMUTABLE-EXISTS` — final partition exists and is non-empty; do not overwrite.
* `E-S8.5-SCHEMA` — any row violates the egress schema (types, ranges, regex).
* `E-S8.5-PK-DUP` — duplicate PK `(merchant_id, legal_country_iso, site_order)` in staged content.
* `E-S8.5-ECHO` — row’s `global_seed`/`manifest_fingerprint` mismatches path tokens.
* `E-S8.5-BLOCKCONST` — within a block, `final_country_outlet_count` not constant or `#rows != final_country_outlet_count`.
* `E-S8.5-SITEID` — `site_id != zpad6(site_order)` or not unique within a block.
* `E-S8.5-CONSERVATION` — merchant conservation identity fails.
* `E-S8.5-OVERFLOW` — any `site_order` or `final_country_outlet_count` exceeds `999999`.
* `E-S8.5-EVENTSYNC` — missing/misplaced `sequence_finalize` for a non-empty block **or** presence of any `site_sequence_overflow` while staging exists.
* `E-S8.5-ATOMIC-RENAME` — atomic rename/publish failed; partition remains uncommitted.

---

## 9) Reference publisher (language-agnostic pseudocode)

```pseudo
function publish_outlet_catalogue(rows_iter_sorted, S_master, F, parameter_hash, run_id):
    final_dir = f"data/layer1/1A/outlet_catalogue/seed={S_master}/fingerprint={F}/"
    staging   = final_dir + "_staging/"

    # (1) immutability guard
    if exists(final_dir) and not is_empty(final_dir):
        raise E-S8.5-IMMUTABLE-EXISTS

    # (2) stage writes (deterministic part numbering)
    mkdirs(staging)
    i := 0
    for batch in partition_into_rowgroups(rows_iter_sorted):
        parquet_write(staging + format("part-%05d.parquet", i), batch,
                      schema="schemas.1A.yaml#/egress/outlet_catalogue",
                      file_meta={schema_ref, seed:S_master, fingerprint:F})
        i := i + 1

    # (3) validate staged content
    validate_schema_pk_and_order(staging)
    validate_partition_echo(staging, seed=S_master, fingerprint=F)
    validate_block_and_conservation(staging)
    validate_iso_fk(staging)
    validate_event_sync(seed=S_master, parameter_hash, run_id)  # S8.4 contract

    # (4) atomic publish
    atomic_rename(staging, final_dir)
```

---

## 10) Conformance tests (must pass)

1. **Happy path:** two merchants with counts `{GB:3, US:2}` and `{GB:1}`. Expect 6 rows; PK unique; per-block counts equal; exactly **three** `sequence_finalize`; echoes correct; deterministic part numbering. ✔︎
2. **Immutability:** create final partition, then attempt re-publish → `E-S8.5-IMMUTABLE-EXISTS`. ✔︎
3. **Event sync:** remove one `sequence_finalize` for a non-empty block → `E-S8.5-EVENTSYNC`. ✔︎
4. **Overflow defense:** craft a staged block with `final_country_outlet_count=1_000_000` → `E-S8.5-OVERFLOW`; ensure no final publish occurs. ✔︎
5. **Echo mismatch:** alter one row’s `global_seed` ≠ partition seed → `E-S8.5-ECHO`. ✔︎
6. **FK breach:** inject `legal_country_iso="ZZ"` → FK failure. ✔︎
7. **Conservation breach:** make merchant’s Σ block counts differ from `raw_nb_outlet_draw` → `E-S8.5-CONSERVATION`. ✔︎

---

## 11) Policy alignment (schema authority)

* Use the **JSON-Schema** as the canonical contract; if Avro is needed downstream, generate it at release time from JSON-Schema.
* Keep “inter-country order not encoded in egress” explicit in dataset notes and tests.

---

This locks down how S8 turns the deterministic S8.2 stream into an **immutable, byte-stable** egress partition with **atomic publish**, **event-synced validation**, and the **validation-bundle gate** that authorises 1B reads.

---

# S8.6 — Determinism & validator contract

## 1) Determinism (pure-function statement)

**Inputs (authorities):**

* **Lineage:** `manifest_fingerprint = F` (hex64), `global_seed = S_master` (u64). These appear in-row and in the egress **partition keys** `(seed={S_master}, fingerprint={F})`.
* **Membership & order:** `country_set(seed=S_master, parameter_hash=P)` → for each merchant $m$, the ordered ISO tuple $\mathcal C_m=(c_0,\dots,c_{K_m})$ with **exactly one** home (`rank=0`). *(Inter-country order lives **only** here.)*
* **Final integer counts:** $\{n_{m,c}\}_{(m,c)}$ from S7 (largest-remainder). S8 does **not** re-draw or re-rank.
* **Merchant constants (written by S8):** `home_country_iso=c_0` (from `country_set`), `raw_nb_outlet_draw = N_m` with

  $$
  N_m \;=\; \sum_{c\in\mathcal C_m} n_{m,c} \;\in\; \mathbb Z_{\ge 1},
  $$

  and `single_vs_multi_flag` **constant per merchant** (writer may derive as `N_m>1` if not provided upstream).

**Definition (no RNG):**

$$
\boxed{\,(\{n_{m,c}\}, F, S_{\text{master}})\ \xrightarrow{\ \text{S8 (pure)}\ }\ \texttt{outlet _catalogue}\,}
$$

Rows are generated by the fixed map $j\mapsto(\texttt{site _order}=j,\ \texttt{site _id}=\mathrm{zpad6}(j))$ for $j\in\{1,\dots,n_{m,c}\}$ using **C-locale ASCII digits**, and written in **lexicographic** order `(merchant_id, legal_country_iso, site_order)`. **No RNG is consumed**; S8’s RNG events are **non-consuming** (`before==after`, `draws=0`).

**Why replay is byte-stable:** (i) construction is local to $(m,c)$, (ii) generation order equals sort keys, (iii) partition echoes lock rows to path tokens, (iv) overflow is centrally handled (0/1 event, then abort).

---

## 2) What must be validated (staged egress, pre-publish)

Validator runs on **staged** `…/outlet_catalogue/seed={S_master}/fingerprint={F}/_staging/` before S8.5’s atomic rename.

### 2.1 Schema & key contract (dataset-local)

**Schema conformance** (`schemas.1A.yaml#/egress/outlet_catalogue`):

* `site_id` matches `^[0-9]{6}$` (C-locale semantics); `raw_nb_outlet_draw ≥ 1`; `final_country_outlet_count ∈ [1,999999]`; `site_order ≥ 1`.
* `home_country_iso` and `legal_country_iso` both FK to canonical ISO.

**Keys, partitions, order:**

* **PK** uniqueness: `(merchant_id, legal_country_iso, site_order)`.
* **Partitions:** every row echoes `global_seed=={seed}` and `manifest_fingerprint=={fingerprint}`.
* **Order:** rows are (or read as) `(merchant_id, legal_country_iso, site_order)` lexicographic.

**Cross-field invariants (per row):**

$$
1 \le \texttt{site _order} \le \texttt{final _country _outlet _count},\qquad
\texttt{site _id} = \mathrm{zpad6}(\texttt{site _order}).
$$

**Block invariants (per $(m,c)$):** `final_country_outlet_count` **constant**; `#rows == final_country_outlet_count`; **within-block** `site_id` is unique.

**Merchant conservation:** for each $m$,

$$
\texttt{raw _nb _outlet _draw}(m) \;=\; \sum_c \texttt{final _country _outlet _count}(m,c).
$$

**Policy guard:** **No inter-country order** encoded in egress; consumers join `country_set.rank`.

### 2.2 Overflow rule (capacity)

Because `site_id` is 6-digit, require $n_{m,c}\le 999{,}999$ for all $(m,c)$. If any $n_{m,c}>999{,}999$, S8 must have emitted **one** `site_sequence_overflow` (zero-draw, partition-scoped) and **aborted**; staged egress must be **absent**.

### 2.3 RNG audit attestation (non-consuming labels)

**Event streams & paths (dictionary/registry):**

* `sequence_finalize` — one per **non-empty** block:
  `logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
* `site_sequence_overflow` — **0/1** per `(seed,fingerprint)`:
  `logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`

Both use the common RNG envelope; **non-consuming ⇒** `before==after`, `draws=0`.

**Cardinality & payload coherence:**

$$
\#\texttt{sequence _finalize} \;=\; \sum_{(m,c)} \mathbf 1[n_{m,c}>0],\qquad
\#\texttt{site _sequence _overflow}\in\{0,1\}.
$$

For each `sequence_finalize(m,c)`: `site_count = n_{m,c}`, `start_sequence="000001"`, `end_sequence=zpad6(n_{m,c})` and **`legal_country_iso=c`**. If overflow exists ⇒ **no staged egress**.

**Trace reconciliation:** for labels in scope, per-label and per-event **draws=0** and **counter deltas = 0** (envelope and `rng_trace_log` agree).

---

## 3) Error catalogue (writer-side abort semantics)

* `E-S8.6-SCHEMA` — schema violation on staged egress.
* `E-S8.6-PK-DUP` — duplicate PK `(merchant_id, legal_country_iso, site_order)`.
* `E-S8.6-ECHO` — row’s `global_seed`/`manifest_fingerprint` ≠ path tokens.
* `E-S8.6-CROSSFIELD` — `site_id != zpad6(site_order)` or `site_order` out of `[1, final_country_outlet_count]`.
* `E-S8.6-BLOCKCONST` — per-block constancy/row-count mismatch.
* `E-S8.6-SITEID-DUP` — duplicate `site_id` within a block.
* `E-S8.6-CONSERVATION` — merchant conservation identity fails.
* `E-S8.6-FK-ISO` — ISO FK failure.
* `E-S8.6-OVERFLOW` — overflow event observed **with** staged egress, or staged content shows count > 999,999.
* `E-S8.6-RNGCARD` — missing/excess `sequence_finalize` or overflow cardinality breach.
* `E-S8.6-RNGZERO` — any non-consuming event advances counters or shows non-zero draws.

All are **hard-fail**; S8.5 must **not** publish.

---

## 4) Reference validator (single-pass over rows + event sync)

```pseudo
function validate_s8(staged_rows, seed, fingerprint, iso_table,
                     n_map, seq_finalize_events, overflow_events, rng_trace,
                     parameter_hash, run_id):

  # A) Dataset-local checks
  pk_set        := HashSet()
  siteid_sets   := HashMap<(m,c), HashSet()>()
  block_rows    := HashMap<(m,c), int64>()         # observed rows
  block_fcount  := HashMap<(m,c), int32>()         # asserted final_country_outlet_count
  merch_sum     := HashMap<m, int64>()             # sum of block counts
  merch_draw    := HashMap<m, int32>()             # observed raw_nb_outlet_draw per merchant
  merch_flag    := HashMap<m, bool>()              # observed single_vs_multi_flag (constancy only)
  merch_home    := HashMap<m, ISO2>()              # observed home_country_iso (constancy only)

  for row in staged_rows:
    # Echo
    if not (row.global_seed == seed and row.manifest_fingerprint == fingerprint): raise E-S8.6-ECHO

    # Domains & FK
    if not matches(row.site_id, "^[0-9]{6}$"): raise E-S8.6-SCHEMA
    if row.raw_nb_outlet_draw < 1 or row.site_order < 1: raise E-S8.6-SCHEMA
    if row.final_country_outlet_count < 1 or row.final_country_outlet_count > 999999: raise E-S8.6-SCHEMA
    if not (row.home_country_iso in iso_table and row.legal_country_iso in iso_table): raise E-S8.6-FK-ISO

    # Cross-field
    if row.site_order > row.final_country_outlet_count: raise E-S8.6-CROSSFIELD
    if row.site_id != zpad6(row.site_order): raise E-S8.6-CROSSFIELD

    # PK uniqueness
    pk := (row.merchant_id, row.legal_country_iso, row.site_order)
    if not add_unique(pk_set, pk): raise E-S8.6-PK-DUP

    # Block tallies
    k := (row.merchant_id, row.legal_country_iso)
    block_rows[k] = block_rows.get(k,0) + 1
    if k not in block_fcount: block_fcount[k] = row.final_country_outlet_count
    else if block_fcount[k] != row.final_country_outlet_count: raise E-S8.6-BLOCKCONST

    S := siteid_sets.get_or_create(k, HashSet())
    if not add_unique(S, row.site_id): raise E-S8.6-SITEID-DUP

    # Merchant constancy + conservation tally
    m := row.merchant_id
    merch_sum[m]  = merch_sum.get(m,0) + row.final_country_outlet_count
    if m not in merch_draw: merch_draw[m] = row.raw_nb_outlet_draw
    else if merch_draw[m] != row.raw_nb_outlet_draw: raise E-S8.6-CONSERVATION
    if m not in merch_flag: merch_flag[m] = row.single_vs_multi_flag
    else if merch_flag[m] != row.single_vs_multi_flag: raise E-S8.6-SCHEMA
    if m not in merch_home: merch_home[m] = row.home_country_iso
    else if merch_home[m] != row.home_country_iso: raise E-S8.6-SCHEMA

  # Block equality & overflow defence
  for k in block_rows.keys():
    if block_rows[k] != block_fcount[k]: raise E-S8.6-BLOCKCONST
    if block_fcount[k] > 999999: raise E-S8.6-OVERFLOW

  for m in merch_sum.keys():
    if merch_sum[m] != merch_draw[m]: raise E-S8.6-CONSERVATION

  # B) RNG event sync (non-consuming, cardinality, payload)
  # Partition tokens on events
  assert all(e.seed==seed and e.parameter_hash==parameter_hash and e.run_id==run_id for e in seq_finalize_events)
  assert all(e.seed==seed and e.parameter_hash==parameter_hash and e.run_id==run_id for e in overflow_events)

  want_sf := sum_{(m,c)} 1[n_map[(m,c)] > 0]
  have_sf := len(seq_finalize_events)
  if have_sf != want_sf: raise E-S8.6-RNGCARD

  for e in seq_finalize_events:
    m := e.merchant_id
    c := e.legal_country_iso          # aligned to egress naming
    n := e.site_count
    if n != n_map[(m,c)]: raise E-S8.6-RNGCARD
    if e.start_sequence != "000001" or e.end_sequence != zpad6(n): raise E-S8.6-RNGCARD
    if not counters_equal(e.before, e.after) or trace_draws(rng_trace,"sequence_finalize",m,c) != 0:
        raise E-S8.6-RNGZERO

  any_overflow := any(n_map[(m,c)] > 999999 for (m,c) in n_map.keys())
  if any_overflow:
    # centralised policy: 0/1 overflow per partition, and no rows
    if len(overflow_events) != 1: raise E-S8.6-RNGCARD
    if not is_empty(staged_rows): raise E-S8.6-OVERFLOW
    e := overflow_events[0]
    if e.attempted_count <= 999999 or e.overflow_by != (e.attempted_count - 999999):
        raise E-S8.6-RNGCARD
    if not counters_equal(e.before, e.after) or trace_draws(rng_trace,"site_sequence_overflow") != 0:
        raise E-S8.6-RNGZERO
  else:
    if len(overflow_events) != 0: raise E-S8.6-RNGCARD

  return OK
```

---

## 5) What S9 additionally proves (hand-off gate)

S9 writes **`validation_bundle_1A`** under
`data/layer1/1A/validation/fingerprint={F}/` and `_passed.flag` whose **content hash equals** `SHA256(bundle)`. **1B may read `outlet_catalogue` only if** this pair exists and matches the same fingerprint. S9’s bundle includes per-label RNG accounting (draw sums = 0; counter deltas = 0), PK/UK/FK/echo proofs, conservation metrics, and policy notes.

---

## 6) Conformance tests (must-pass)

1. **Happy path, two blocks.** $(m,GB)\, n{=}3$, $(m,US)\, n{=}2$ → 5 rows; ordered keys; per-block constants; PK unique; `site_id=zpad6(site_order)`; **two** `sequence_finalize` with coherent payloads; **zero** overflow; non-consuming envelopes. ✔︎
2. **Zero-block elision.** Add $(m,FR)\, n{=}0$ → **no rows** for FR and **no** finalize for FR. ✔︎
3. **Overflow guard (centralised).** Set $n_{m,US}=1\,000\,005$ → **one** `site_sequence_overflow` for the partition; **no staged egress**; validator aborts publish. ✔︎
4. **Echo mismatch.** Flip a row’s `global_seed` or `manifest_fingerprint` → `E-S8.6-ECHO`. ✔︎
5. **PK duplication.** Duplicate `(merchant_id, legal_country_iso, site_order)` → `E-S8.6-PK-DUP`. ✔︎
6. **Cross-field failure.** `site_id="000010"` with `site_order=9` → `E-S8.6-CROSSFIELD`. ✔︎
7. **ISO FK breach.** `legal_country_iso="ZZ"` → `E-S8.6-FK-ISO`. ✔︎
8. **RNG non-consumption.** Tweak a finalize envelope so `after≠before` or trace shows draws>0 → `E-S8.6-RNGZERO`. ✔︎
9. **Conservation breach.** Make $\sum_c \texttt{final _country _outlet _count}\neq \texttt{raw _nb _outlet _draw}$ for merchant $m$ → `E-S8.6-CONSERVATION`. ✔︎

---

## 7) Implementation notes (binding where stated)

* **Where to run:** execute this validator **inside S8.5** on `_staging/` before atomic publish. If any check fails, **do not publish**; S9 still emits a bundle for forensics (without `_passed.flag`).
* **Event naming:** use `legal_country_iso` in event payloads to align with egress terminology.
* **Locale:** `zpad6` is C-locale/ASCII; forbid locale-dependent digits.

---

This locks S8’s **pure-function determinism**, the **exact writer-time validator** (mirrored in S9), centralised overflow semantics, RNG **zero-draw** accounting, conservation equality, and the cryptographic 1A→1B gate.

---

# S8.7 — Complexity, streaming & ops

## 1) Scope (what this section binds)

S8 takes country-level integers $\{n_{m,c}\}$ and materialises the egress table **`outlet_catalogue`** (one row per realised site) under

```
data/layer1/1A/outlet_catalogue/
  seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet
```

with **PK** `(merchant_id, legal_country_iso, site_order)`, and **write order = sort keys** `(merchant_id, legal_country_iso, site_order)`. **Inter-country order is never encoded** in egress (consumers join `country_set.rank`). These dataset mechanics are **authoritative** for complexity and ops below.

---

## 2) Work & memory complexity

Let:

* $M$ = number of merchants in scope.
* For merchant $m$, $\mathcal{C}_m$ = ordered legal country set from `country_set`.
* $T=\sum_m\sum_{c\in\mathcal{C}_m} n_{m,c}$ = **total rows** (sites) to emit.

**Row materialisation.** Construction is a **pure map** $j\mapsto(\texttt{site _order}=j,\ \texttt{site _id}=\mathrm{zpad6}(j))$ per $(m,c)$ using **ASCII digits** (C locale). Therefore:

* **Time:** $\Theta(T)$ for row construction.
* **Extra sorting cost:** **none** if you generate in key order `(merchant_id, legal_country_iso, site_order)`; otherwise a global $T\log T$ appears and **must be avoided**.

**Memory (streaming writer).** With a streaming Parquet writer and contiguous emission in key order:

* Peak RAM is **O(row-group size)** (64–256 MiB typical) + small counters/accumulators for on-the-fly validation (per-block counts; optional small set if contiguity is not guaranteed). No full-table materialisation is required.

**RNG cost.** S8 consumes **no RNG**. Its events (`sequence_finalize`, `site_sequence_overflow`) are **non-consuming** and must keep Philox counters unchanged (**`before == after`, `draws=0`**).

---

## 3) I/O footprint & file layout (deterministic & scalable)

Let:

* $B_{\text{uncomp}}$ = average **uncompressed** row size for `outlet_catalogue`.
* Target row-group size $\approx 128\,\mathrm{MiB}$ uncompressed.
* $G$ = number of row-groups; $P$ = number of part files.

**Planning formulas:**

$$
G \;\approx\; \left\lceil \frac{T \cdot B_{\text{uncomp}}}{128\,\mathrm{MiB}} \right\rceil,\qquad
P \;\approx\; \left\lceil \frac{G}{\text{row _groups _per _part}} \right\rceil.
$$

**Naming & path (binding).** Parts **must** be named

```
part-00000.parquet, part-00001.parquet, …
```

under `…/seed={seed}/fingerprint={manifest_fingerprint}/`. The partition is **immutable**; a two-phase publish is **required** (stage → validate → **atomic rename**).

**Compression & encodings (advisory but consistent).** Parquet is mandated; use a consistent codec across parts (e.g., Zstd level 3). Where feasible, align row-groups (optionally parts) with block boundaries $(m,c)$ to speed `site_order` scans. (Performance hint; schema & path remain binding.)

**Partition echo (binding).** Every row **must** echo the directory tokens: `global_seed==seed` and `manifest_fingerprint==fingerprint`.

---

## 4) Deterministic concurrency model

**Sharding unit (binding).** **Merchant** is the parallelisation unit. Each shard:

1. processes a disjoint set of merchants **in ascending `merchant_id`**, and
2. within each merchant, iterates `legal_country_iso` **ascending**, emitting `site_order = 1..n_{m,c}`.

This preserves global lexicographic order when shard outputs are merged.

**Multi-writer staging.** Multiple shards may emit parts into a single `_staging/` directory (unique temp filenames per shard), then a **single** metadata-atomic rename publishes the partition. Each part **must** be internally ordered by the dataset keys.
If you require **byte-identical part listings across replays**, perform a deterministic concatenation/renumbering pass at publish time and emit `part-00000.parquet …` in a canonical shard-key order.

**Idempotence & immutability.** If the final partition exists and is non-empty, **abort**; do **not** overwrite. Retries are allowed only **before** the atomic rename, after cleaning `_staging/`.

**Event emission ordering.** Emit `sequence_finalize` **after** each non-empty block’s rows are staged; emit `site_sequence_overflow` **once per partition** and **abort immediately** if any $n_{m,c}>999{,}999$. Both events are **non-consuming** (`before == after`).

---

## 5) Online validation while streaming (single pass)

To avoid a second full scan before publish, perform **on-the-fly checks** as rows are written. For the **current block** $k=(m,c)$ maintain:

* `count_rows[k]` (seen rows),
* `final_count[k]` (first `final_country_outlet_count`; must be constant),
* **Either** a small set of `site_id` **or** (preferred with sequential emission) two scalars:

  * `last_site_order[k]` (start at 0),
  * `max_site_order[k]` (monotone).

**Per-row predicates (must hold):**

$$
\begin{aligned}
&\text{regex(site _id)}=\texttt{^[0-9]{6}\$}\ \text{(ASCII digits)}, \\
&1\le \texttt{site _order}\le \texttt{final _country _outlet _count},\quad
\texttt{site _id}=\mathrm{zpad6}(\texttt{site _order}), \\
&\texttt{raw _nb _outlet _draw}\ge 1, \\
&\texttt{home _country _iso},\ \texttt{legal _country _iso}\in \text{ISO2 (FK)}, \\
&(\texttt{global _seed},\texttt{manifest _fingerprint})=(\texttt{seed},\texttt{fingerprint}).
\end{aligned}
$$

**Gap-free optimisation (sequential write).** If rows within a block are emitted in order:

* assert `site_order == last_site_order[k] + 1` and set `last_site_order[k] = site_order`;
* set `max_site_order[k] = site_order`; uniqueness of `site_id` then follows **without a set**.

**At block boundary:** assert `count_rows[k] == final_count[k]` and `max_site_order[k] == final_count[k]`, then reset.
**Per merchant $m$:** maintain `sum_final_counts[m] += final_count[(m,c)]`; on merchant boundary assert **conservation**:

$$
\texttt{raw _nb _outlet _draw}(m) \;=\; \sum_{c} \texttt{final _country _outlet _count}(m,c).
$$

On any breach, **abort**; do not publish.

---

## 6) Overflow guard & abort semantics

Let $U=999{,}999$ (6 digits). If **any** $n_{m,c}>U$:

* Perform a **central pre-scan** and emit **exactly one** `site_sequence_overflow` event for the lexicographically first offending $(m,c)$ under `(merchant_id, legal_country_iso)`.
* **Do not** stage any `outlet_catalogue` rows.
* **Abort** the publish for this `(seed,fingerprint)`.

Presence of an overflow event **implies** absence of an egress partition for that fingerprint.

---

## 7) Throughput formulas & capacity planning

Definitions:

* $r_w$ = sustained row write rate per writer (rows/s) after encoding + compression.
* $k$ = number of writers (merchant shards) in parallel.
* $T$ = total rows.
* $E = \sum_{(m,c)} \mathbf 1[n_{m,c}>0]$ = number of non-empty blocks ⇒ number of `sequence_finalize` events.

**Wall-clock write time (idealised):**

$$
t_{\text{emit}} \;\approx\; \frac{T}{k\,r_w}\quad\text{(excludes final validation & rename)}.
$$

**Validation time.** With on-the-fly checks, overhead is **O(1)** per row; remaining fixed cost is the staged schema/PK/FK scan (linear in bytes) and typically overlaps with writer flushes.

**Log volume.** `sequence_finalize` produces **E** JSONL records; `site_sequence_overflow` produces **at most 1** per partition and aborts. Both are small envelopes and **zero-draw**.

---

## 8) Monitoring, SLOs & alerts (binding where stated)

* **SLO-S8-01 (schema & keys):** 100% of staged partitions pass schema, PK, and FK checks before publish. **Alert** on `E-S8.5-SCHEMA`, `E-S8.5-PK-DUP`, `E-S8.5-ECHO`.
* **SLO-S8-02 (event sync):** For any successful publish, `count(sequence_finalize) == E` and **zero** overflow; envelopes are **non-advancing** and reconcile to **draws=0**. **Alert** on `E-S8.5-EVENTSYNC` / `E-S8.6-RNGZERO`.
* **SLO-S8-03 (immutability):** 0 overwrites of existing partitions; any attempt triggers `E-S8.5-IMMUTABLE-EXISTS`. **Alert** and block job.
* **SLO-S8-04 (gate integrity):** 1B reads only **after** `_passed.flag` hash equals `SHA256(validation_bundle_1A)` for the **same** fingerprint. Missing/invalid gate is a **hard block**.

---

## 9) Failure, retry & idempotence matrix

| Failure point            | Example error                | Effect                    | Allowed action                                           |
| ------------------------ | ---------------------------- | ------------------------- | -------------------------------------------------------- |
| Preflight / overflow     | `site_sequence_overflow`     | No staging, abort         | Fix inputs or reduce $n_{m,c}$; rerun                    |
| During stream            | Domain/PK/FK breach          | Abort shard; no publish   | Fix; rerun shard(s)                                      |
| Validation (stage)       | Event mismatch / echo fail   | Abort; remove `_staging/` | Fix; restage & re-validate                               |
| Atomic rename            | Filesystem/object-store fail | `_staging/` remains       | Retry rename or roll back; **never** partial-write final |
| Re-run on existing final | `E-S8.5-IMMUTABLE-EXISTS`    | Guarded                   | Do not overwrite; new fingerprint on change              |

> **Object stores:** if atomic directory rename is unavailable, use a single-writer manifest publish that is equivalent to POSIX `rename(2)` in atomicity/visibility.

---

## 10) Retention, licensing & PII

* `outlet_catalogue`: **retention 365 days**, `pii: false`, licence `Proprietary-Internal` (dataset dictionary).
* RNG events & validation artefacts follow their own retention policies (e.g., RNG logs 180 days; validation bundle per registry).
* Consumers **must** verify the **gate** before reading.

---

## 11) Ops recipes (deterministic writer patterns)

**A. Single-node writer (reference).**

1. Iterate merchants ascending; within each merchant, iterate `legal_country_iso` ascending.
2. For $(m,c)$ with $n_{m,c}>0$, emit rows `site_order=1..n_{m,c}`, `site_id=zpad6(site_order)`; otherwise skip.
3. Maintain on-the-fly predicates (§5); at block end, emit one `sequence_finalize`.
4. Flush Parquet parts under `_staging/`; run validator; **atomic rename**.

**B. Sharded writer (multi-node).**

* Partition by merchant ranges; each shard writes **ordered** rows to the **same** `_staging/` with unique temp part names.
* A single coordinator validates `_staging/` and performs the **one** atomic rename (optionally canonicalises `part-00000.parquet …`).
* If overflow is detected by pre-scan, emit the single overflow event and **do not** validate or rename.

---

## 12) Conformance & load tests (must/should)

1. **Scale linearity (must):** Double $T$ with fixed $k$ → $t_{\text{emit}}$ doubles within 10% tolerance. ✔︎
2. **Deterministic replay (must):** Same inputs, different shard counts $k\in\{1,4,16\}$ → identical row content; and, if deterministic concatenation is enabled, identical part listings. ✔︎
3. **Overflow abort (must):** Inject $n_{m,c}=1{,}000{,}005$ → one `site_sequence_overflow`; **no** egress partition published. ✔︎
4. **Event zero-draw (must):** Doctor one event to advance counters → validator fails with `RNGZERO`; publish blocked. ✔︎
5. **Immutability guard (must):** Pre-create final partition then rerun → `IMMUTABLE-EXISTS`; no overwrite. ✔︎

---

## 13) What S9 will re-prove (for the gate)

S9 re-checks: schema/PK/FK, block counts and bijection (`site_id = zpad6(site_order)`), event cardinalities, **zero-draw** envelopes, **merchant conservation**, and writes **`validation_bundle_1A`** plus `_passed.flag` whose **content hash equals** `SHA256(bundle)`. **1B reads only after** this gate.

---

### TL;DR (binding bits)

* **Time:** $\Theta(T)$; **memory:** streaming = row-group-bounded.
* **Order:** generate in `(merchant_id, legal_country_iso, site_order)`; **no global sort**.
* **Overflow:** $n_{m,c}\le 999{,}999$ or emit **one** overflow event per partition and abort.
* **Publish:** stage → validate → **atomic rename**; partition **immutable**; verify **gate** before 1B.
* **Encoding:** `zpad6` uses **ASCII digits** (C locale); forbid locale-dependent digits.

---
