# S8 — Materialize outlet stubs & per-country sequences (pre-S8.1)

## Goal

Given a fixed run lineage and the allocations produced upstream, **materialize** the immutable egress table `outlet_catalogue`, one row per realized site, with per-country sequencing only. No RNG is consumed in S8.&#x20;

---

## Inputs (authorities, partitions, domains)

1. **Run lineage (S0):**

* **Manifest fingerprint** $F\in\{0,\dots,2^{256}-1\}$ stored as **hex64** in-column and used to partition egress under `{fingerprint}`.
* **Master seed** $S_{\text{master}}\in\{0,\dots,2^{64}-1\}$, stored per row as `global_seed`. Both are carried from S0 and never mutated.&#x20;

2. **Country set (S3–S6 output, already persisted):**
   For each merchant $m$, an **ordered** ISO set $\mathcal{C}_m=(c_0,\dots,c_{K_m})$ with `rank(c_0)=0` (home) and `rank(c_i)=i` (foreign). Authority: `alloc/country_set`, partitioned by `{seed, parameter_hash}`; this is the **only** carrier of inter-country order.&#x20;

3. **Integer outlet counts (S7):**
   Final **largest-remainder** counts $n_{m,c}\in\mathbb{Z}_{\ge 0}$ per $(m,c)$; residual ordering already cached in `ranking_residual_cache_1A` (parameter-scoped) to make integerization reproducible.&#x20;

4. **Wide allocation & provenance:**
   Per-merchant fields needed in egress rows, e.g.
   `single_vs_multi_flag` $H_m\in\{0,1\}$, `raw_nb_outlet_draw` $N_m\ge1$, `home_country_iso` (ISO-2). These are **deterministic** inputs carried forward to S8.&#x20;

**Pre-flight presence tests (must-pass before S8 emits anything):**

* `country_set(seed, parameter_hash)` exists and covers all merchants in scope; exactly one home row (`rank=0`).
* Integer counts $\{n_{m,c}\}$ available for all $(m,c)\in \texttt{country_set}$.
* Lineage pair $(F,S_{\text{master}})$ present. Absent inputs ⇒ S8 aborts.&#x20;

---

## Output (single immutable table)

### Dataset & path

**`egress/outlet_catalogue`** (Parquet), partitioned by `{seed, fingerprint}`:

```
data/layer1/1A/outlet_catalogue/
  seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet
```

The artefact registry pins path, partitioning, and schema pointer.&#x20;

### Schema keys & ordering

* **Primary key:** $(\texttt{merchant_id},\ \texttt{legal_country_iso},\ \texttt{site_order})$.
* **Partition keys:** `seed`, `fingerprint`.
* **Sort keys (write order):** `(merchant_id, legal_country_iso, site_order)`.
* **No inter-country order here** (policy): consumers **must** join `alloc/country_set.rank` when they need cross-country sequencing.&#x20;

### Required columns (selected, with domains)

* `manifest_fingerprint` ∈ hex64 (= $F$ on every row)
* `global_seed` ∈ uint64 (= $S_{\text{master}}$)
* `merchant_id` (id64)
* `home_country_iso`, `legal_country_iso` (ISO-2; FK to canonical ISO)
* `single_vs_multi_flag` ∈ {0,1}
* `raw_nb_outlet_draw` ∈ $\mathbb{Z}_{\ge1}$ (equals $N_m$ on **home** block rows)
* `final_country_outlet_count` ∈ $\mathbb{Z}_{\ge0}$ (groupwise constant = $n_{m,c}$)
* `site_order` ∈ $\{1,\dots,n_{m,c}\}$
* `site_id` ∈ `^[0-9]{6}$` (the **left-padded** image of `site_order` within the $(m,c)$ block)&#x20;

**Overflow threshold:** $U=999{,}999$. S8 must **abort** if any $n_{m,c} > U$ and emit a `site_sequence_overflow` guard event (see S8.4).&#x20;

---

## Construction contract (what S8 will do next)

For each $(m,c)$ with $n_{m,c} > 0$, expand the **per-country sequence**

$$
\mathcal{J}_{m,c}=\{1,\dots,n_{m,c}\}
$$

and write one row per $j\in\mathcal{J}_{m,c}$ with

$$
\texttt{site_order}=j,\qquad \texttt{site_id}=\mathrm{zpad6}(j).
$$

This expansion is **purely deterministic** (no RNG). Before/after the write S8 emits one **non-consuming** `sequence_finalize` event per block $(m,c)$ for auditability (envelope counters unchanged).&#x20;

---

## Determinism & invariants at the boundary

* **Pure function:** $(\{n_{m,c}\},F,S_{\text{master}})\mapsto \texttt{outlet_catalogue}$ is **bit-stable** across replays.
* **Row counts:** for each $(m,c)$, `#rows == n_{m,c}` and `site_order` is a **gap-free permutation** of $\{1..n_{m,c}\}$.
* **Identity columns:** every row repeats the partition’s `seed` and `fingerprint` (`global_seed`, `manifest_fingerprint`).
* **Country-order separation:** **never** encode cross-country order in egress; 1B (and S9) must recover it from `country_set.rank`.&#x20;

---

## Minimal reference algorithm (collector for S8.1+)

```
INPUT:
  F = manifest_fingerprint (hex64)
  S_master = global_seed (u64)
  country_set(seed, parameter_hash)      # (merchant_id, country_iso, rank, is_home)
  counts n[m,c] from S7                  # integerized largest-remainder counts
  wide fields per m: H_m, N_m, home_iso  # provenance

OUTPUT:
  outlet_catalogue (seed= S_master, fingerprint = F)

1  assert exists(country_set) and exists(counts) and F,S_master not null
2  for each (m,c) in country_set:
3      n := n[m,c] (default 0); if n > 999999: emit overflow event; abort
4      for j in 1..n:
5          emit row:
6            merchant_id=m, legal_country_iso=c, home_country_iso=home_iso(m)
7            site_order=j, site_id=zpad6(j)
8            final_country_outlet_count=n, single_vs_multi_flag=H_m, raw_nb_outlet_draw=N_m
9            manifest_fingerprint=F, global_seed=S_master
10 write rows ordered by (merchant_id, legal_country_iso, site_order)
11 emit one non-consuming sequence_finalize event per (m,c) with n > 0
```

---

# S8.1 — State & notation (deepened)

## Objects fixed by upstream states

For a merchant $m$ with legal country set $\mathcal{C}_m$ (from `country_set`, the **only** authority on inter-country membership/order), S7 provides **integer outlet counts** $n_{m,c}\in\mathbb{Z}_{\ge 0}$ for each $c\in\mathcal{C}_m$. These are already persisted and schema-governed; S8 consumes them read-only.&#x20;

## Per-block sequence space

For each $(m,c)$ define the **within-country** sequence index set

$$
\boxed{\ \mathcal{J}_{m,c}=\{1,2,\dots,n_{m,c}\}\ }.
$$

If $n_{m,c}=0$ then $\mathcal{J}_{m,c}=\varnothing$ and **no rows** are emitted for that block; otherwise $|\mathcal{J}_{m,c}|=n_{m,c}$. This is the **only** order S8 encodes in egress; cross-country order remains out of scope and must be joined from `country_set.rank`.&#x20;

## Site-id encoder (formal)

Let the **overflow threshold** be $U=999{,}999$ (max 6-digit number). Define the encoder

$$
\boxed{\ \sigma:\{1,\dots,U\}\to\{0,1,\dots,9\}^6\ }
$$

as **six-digit, zero-padded, base-10** formatting:

$$
\sigma(j)=\text{zpad6}(j)=d_5d_4d_3d_2d_1d_0,
$$

where $d_k=\big\lfloor j/10^k\big\rfloor\bmod 10$ for $k=0,\dots,5$ (most-significant digit $d_5$ left). Equivalently, `sprintf("%06d", j)`. The egress schema constrains the codomain by the regex `^[0-9]{6}$`.&#x20;

### Mapping domain per block

S8 uses $\sigma$ **only** on $j\in\mathcal{J}_{m,c}$. Thus the block’s image set is

$$
\Sigma_{m,c}=\sigma(\mathcal{J}_{m,c})=\{\text{zpad6}(1),\ldots,\text{zpad6}(n_{m,c})\}.
$$

## Properties & invariants (used by S8 and validated in S9)

1. **Cardinality & bijection (per block).**
   $\sigma|_{\mathcal{J}_{m,c}}$ is a bijection onto $\Sigma_{m,c}$; hence $|\Sigma_{m,c}|=n_{m,c}$ and

$$
j_1\neq j_2 \iff \sigma(j_1)\neq \sigma(j_2).
$$

This guarantees **uniqueness** of `site_id` within a $(m,c)$ block. (Dataset’s declared PK is $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$; `site_id` is additionally unique **within** block by construction.)&#x20;

2. **Monotonicity in lexicographic order.**
   Because all codes are width-6, numeric and lexicographic orders coincide:

$$
j_1 < j_2 \ \Longleftrightarrow\ \sigma(j_1)\ \text{lex} <\ \sigma(j_2).
$$

Hence writing rows in increasing `site_order` also produces increasing `site_id` strings inside each block. (The table’s sort keys are `(merchant_id, legal_country_iso, site_order)`.)&#x20;

3. **Regex & range discipline.**
   Every emitted `site_id` must match `^[0-9]{6}$`; every `site_order` lies in $\{1,\dots,n_{m,c}\}$; and $n_{m,c}\ge 0$ is carried as the constant `final_country_outlet_count` per block. These are literal schema constraints for `outlet_catalogue`.&#x20;

4. **Overflow guard (must-hold).**

$$
\boxed{\ n_{m,c}\le U\ } \quad\text{for all }(m,c).
$$

If violated, S8 emits `site_sequence_overflow` and **aborts** (no partial egress). This mirrors the declared 6-digit format and the documented guardrail in S8.2/S8.4.&#x20;

5. **Scope separation (country order).**
   Egress **never** encodes inter-country order; consumers **must** join `country_set.rank` to obtain the sequence $c_0,c_1,\dots$. S9 re-asserts this contract.

## Row-key & identifier sets (notation convenience)

* **PK tuples (per block):** $\mathcal{K}_{m,c}=\{(m,c,j): j\in\mathcal{J}_{m,c}\}$.
* **Identifier tuples:** $\mathcal{I}_{m,c}=\{(m,c,\sigma(j)): j\in\mathcal{J}_{m,c}\}$.
  The write materialises exactly $|\mathcal{K}_{m,c}|=|\mathcal{I}_{m,c}|=n_{m,c}$ rows; **no RNG** is consumed, and a non-consuming `sequence_finalize` audit event is emitted per non-empty block (envelope counters unchanged).&#x20;

## Minimal reference (encoder & guards)

```
INPUT : n_{m,c} ≥ 0
PARAM : U = 999_999
OUTPUT: for j in 1..n_{m,c}, (site_order=j, site_id=zpad6(j))

1  assert n_{m,c} ≤ U                         # overflow guard
2  for j := 1 to n_{m,c}:
3      site_order := j
4      site_id    := format("%06d", j)        # σ(j), matches ^[0-9]{6}$
5  # (S8 emits 'sequence_finalize' for n_{m,c} > 0; before==after in envelope)
```

This aligns with the egress schema (PK, regex, ranges) and the artefact registry/dictionary that fix paths and the “no inter-country order in egress” policy.

**Side note (narrative parity).** The narrative explicitly states S8 assigns monotone `site_order` $1..n_i$, zero-padded `site_id` per $(m,i)$, raises `site_sequence_overflow` if $n_i > 999999$, and writes to `…/outlet_catalogue/seed={seed}/fingerprint={fingerprint}/…`.&#x20;

---

# S8.2 — Deterministic construction of per-country sequences

## Formal objective

For each merchant–country block $(m,c)$ with integerised count $n_{m,c}\ge 0$ (from S7) and sequence space $\mathcal{J}_{m,c}=\{1,\dots,n_{m,c}\}$ (from S8.1), materialise **exactly** $n_{m,c}$ rows in `egress/outlet_catalogue`, encoding **within-country** order only. No RNG is consumed in S8. The dataset’s path, partitioning, and schema pointer are fixed by the registry/dictionary.

---

## (1) Row expansion (cartesian sum over per-country sequences)

For each $(m,c)$ with $n_{m,c} > 0$, and for each $j\in\mathcal{J}_{m,c}$, emit one row with

$$
\begin{aligned}
&\texttt{merchant_id}=m,\quad
 \texttt{legal_country_iso}=c,\quad
 \texttt{site_order}=j,\quad
 \texttt{site_id}=\sigma(j),\\
&\texttt{home_country_iso}=\text{from merchant lineage},\\
&\texttt{single_vs_multi_flag},\ \texttt{raw_nb_outlet_draw}\ \text{carried from hurdle/NB lineage},\\
&\texttt{final_country_outlet_count}=n_{m,c},\quad
 \texttt{manifest_fingerprint}=\mathrm{hex}(F),\quad
 \texttt{global_seed}=S_{\text{master}}.
\end{aligned}
$$

This is a **pure map** from deterministic inputs to rows; the coder $\sigma$ is the width-6, zero-padded base-10 encoder from S8.1 (regex `^[0-9]{6}$`). Schema domains for these columns (PK, ranges, regex) are enforced at write and later in S9.

**Block-constant fields.** Within a fixed $(m,c)$, `final_country_outlet_count` must be **groupwise constant** and equal to $n_{m,c}$; `site_order` must permute $1..n_{m,c}$ with no gaps/dupes. These are validated again in S9.4.&#x20;

---

## (2) Overflow guard (must abort on breach)

Let $U=999{,}999$. Because `site_id` is a 6-digit string, require

$$
\boxed{\,n_{m,c}\le U\ \text{ for all }(m,c)\,}.
$$

If any $n_{m,c} > U$, emit a **guardrail** event `site_sequence_overflow` and **abort** the build (no partial egress). The event is catalogued with the common RNG envelope; as a non-consuming event its counters satisfy `before == after`.

---

## (3) Write-stability ordering (canonical row order)

Materialise rows sorted lexicographically by the dataset’s **sort keys**

$$
(\texttt{merchant_id},\ \texttt{legal_country_iso},\ \texttt{site_order}),
$$

which mirror the construction loop ordering. **Inter-country order is intentionally not encoded** here; consumers must join `alloc/country_set.rank` to recover cross-country sequencing. The dictionary/registry lock both the egress sort keys and the “country order lives only in `country_set`” policy.

---

## Determinism, keys, and schema contracts (what this construction guarantees)

* **No RNG consumption.** S8 emits a non-consuming `sequence_finalize` event **once per $(m,c)$ with $n_{m,c} > 0$** to certify the realised block size; envelopes prove **before==after** counters.&#x20;
* **Primary key satisfied.** Rows are unique on $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$; the schema declares this as the PK and S9.3 re-checks cardinality equality.&#x20;
* **Regex & ranges.** `site_id` matches `^[0-9]{6}$`; `site_order≥1`; `final_country_outlet_count≥0`; `raw_nb_outlet_draw≥1`; country codes are ISO-2 with FK to the canonical table.&#x20;
* **Partitioning & lineage.** Egress is written at
  `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…`
  with per-row `global_seed` and `manifest_fingerprint` equal to the partition keys.&#x20;

---

## Minimal reference algorithm (language-agnostic)

```
INPUT:
  F (hex64 manifest_fingerprint), S_master (u64 global_seed)
  COUNTRY_SET := table of (merchant_id=m, country_iso=c, rank, is_home)         # read-only
  COUNTS      := map (m,c) ↦ n_{m,c} ≥ 0                                        # from S7
  WIDE(m)     := {home_country_iso, single_vs_multi_flag, raw_nb_outlet_draw}   # provenance
PARAM:
  U := 999_999

OUTPUT:
  OUTLET_CATALOGUE partition seed=S_master, fingerprint=F

1  for each (m,c) in COUNTRY_SET:
2      n := COUNTS[m,c] default 0
3      if n > U:
4          emit_event("site_sequence_overflow", m, c, n; before==after)   # non-consuming
5          abort("n_{m,c} exceeds 6-digit capacity")
6      for j in 1..n:
7          row := {
8              merchant_id=m, legal_country_iso=c,
9              site_order=j, site_id=zpad6(j),                              # σ(j)
10             home_country_iso=WIDE(m).home_country_iso,
11             single_vs_multi_flag=WIDE(m).single_vs_multi_flag,
12             raw_nb_outlet_draw=WIDE(m).raw_nb_outlet_draw,
13             final_country_outlet_count=n,
14             manifest_fingerprint=F, global_seed=S_master
15         }
16         append(row)
17     if n > 0:
18         emit_event("sequence_finalize", m, c, site_count=n; before==after)
19 sort output by (merchant_id, legal_country_iso, site_order)
20 write to data/layer1/1A/outlet_catalogue/seed=S_master/fingerprint=F/part-*.parquet
```

All event paths, partitions and roles are fixed by the registry (`rng_event_sequence_finalize`, `rng_event_site_sequence_overflow`) and share the **rng envelope** schema used across 1A.&#x20;

---

## Complexity & replay

Let $T=\sum_{m}\sum_{c} n_{m,c}$ be the total outlet count. The construction is $\mathcal{O}(T)$ and byte-replayable for fixed $(\{n_{m,c}\},F,S_{\text{master}})$ because no randomness or platform-dependent ordering is involved.&#x20;

---

## What S9 will later assert (preview)

S9 re-proves: (i) per-block row count equals $n_{m,c}$ and `site_order=1..n_{m,c}`; (ii) `site_id = zpad6(site_order)`; (iii) `sequence_finalize` exists per non-empty block with **zero draws**; and (iv) inter-country order is **absent** from egress and must be joined from `country_set.rank`.&#x20;

That’s S8.2, fully specified and tied to your schema and registry contracts.

---



# S8.3 — Constraints & keys (enforced)

## 1) Domain constraints (row-level predicates)

For any materialized row $(m,c,j)$ in `egress/outlet_catalogue`:

**(a) `site_id` format.**
Let $\sigma(j)=\text{zpad6}(j)\in\{0,\dots,9\}^6$. Enforce

$$
\texttt{site_id}=\sigma(j)\quad\wedge\quad \texttt{site_id}\sim\texttt{"^[0-9]{6}\$"}.
$$

This couples the regex to the constructive definition used in S8.1–S8.2.

**(b) `site_order` range.**

$$
\texttt{site_order}=j\in\{1,\dots,n_{m,c}\},\quad n_{m,c}\in\mathbb{Z}_{\ge0}.
$$

If $n_{m,c}=0$ the block emits no rows; otherwise the set is gap-free.&#x20;

**(c) Block constant & non-negativity.**

$$
\texttt{final_country_outlet_count}=n_{m,c}\ \ (\text{constant over rows with fixed }(m,c)),\qquad n_{m,c}\ge0.
$$

This field is the realized count per $(m,c)$.&#x20;

**(d) NB provenance guard.**

$$
\texttt{raw_nb_outlet_draw}\in\mathbb{Z}_{\ge1},\qquad \texttt{single_vs_multi_flag}\in\{0,1\}.
$$

Types and minima are schema-declared.&#x20;

**(e) ISO foreign keys.**

$$
\texttt{home_country_iso},\ \texttt{legal_country_iso}\in \text{ISO2},\quad
(\text{FK}\to \texttt{iso3166_canonical_2024.country_iso}).
$$

The ISO domain (upper-case `^[A-Z]{2}$`) and FK target are defined in the ingress schema; egress columns reference that table.

**(f) Lineage fields.**

$$
\texttt{manifest_fingerprint}\sim\texttt{"^[a-f0-9]{64}\$"},\qquad
\texttt{global_seed}\in\{0,\dots,2^{64}\!-\!1\}.
$$


Every row repeats the partition keys for replayability.&#x20;

**(g) Overflow guard (by construction).**
Since `site_id` is width-6, require $n_{m,c}\le U=999{,}999$. Violation emits `site_sequence_overflow` and **aborts** S8. (Guard is asserted in S8.2; validated again here.)&#x20;

---

## 2) Keys, uniqueness, partitioning, ordering

**Primary key (PK).**

$$
\boxed{\ \text{PK}=(\texttt{merchant_id},\ \texttt{legal_country_iso},\ \texttt{site_order})\ }.
$$

S8’s construction guarantees uniqueness because each block $(m,c)$ emits exactly one row for each $j\in\{1,\dots,n_{m,c}\}$. S9 re-proves

$$
\#\text{rows}=\#\,\text{unique}(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order}).
$$

**Partition keys.**
Dataset is partitioned by

$$
(\texttt{seed},\ \texttt{fingerprint})=(\texttt{global_seed},\ \texttt{manifest_fingerprint}),
$$

and those values are also stored per-row (one-to-many equality). Path pattern is fixed by the registry/dictionary.

**Sort keys (write order).**
Rows are written in lexicographic order on

$$
(\texttt{merchant_id},\ \texttt{legal_country_iso},\ \texttt{site_order}),
$$

which matches generation order and stabilizes Parquet row-groups. Inter-country order is **not** encoded here and must be joined from `country_set.rank`.

---

## 3) Immutability (per partition)

For a fixed partition `(seed, fingerprint)`, the egress is **immutable**: subsequent consumers (including 1B) may read it only after S9 writes `_passed.flag` that matches the bundle digest; any change to parameters or artefacts produces a **new** `manifest_fingerprint` and thus a new partition.

---

## 4) Minimal enforcement routine (reference)

A validator that enforces S8.3 at write-time (subset of S9 structural checks):

```
INPUT: OUTLET (table just built), ISO (canonical iso3166), F, S_master
ASSERT: schema matches schemas.1A.yaml#/egress/outlet_catalogue

# A) Domain predicates
for each row r in OUTLET:
    assert r.manifest_fingerprint matches ^[a-f0-9]{64}$
    assert r.site_id          matches ^[0-9]{6}$
    assert r.site_order      >= 1
    assert r.final_country_outlet_count >= 0
    assert r.raw_nb_outlet_draw >= 1
    assert r.home_country_iso  in ISO.country_iso
    assert r.legal_country_iso in ISO.country_iso
    assert r.global_seed == S_master
    assert r.manifest_fingerprint == F
    # constructive coupling (optional but strong):
    assert r.site_id == zpad6(r.site_order)

# B) Per-(m,c) block checks
for each (m,c):
    let S = rows where merchant_id=m and legal_country_iso=c
    n = unique(S.final_country_outlet_count)
    assert |unique(n)| == 1
    assert |S| == n
    assert sorted(S.site_order) == [1..n]

# C) Keys & uniqueness
assert |OUTLET| == |unique(merchant_id,legal_country_iso,site_order)|

# D) Overflow (redundant if construction enforced)
for each (m,c): assert max(site_order in block) ≤ 999999
```

These checks align with the schema contracts and the S9 cross-dataset invariants that will be recomputed post-write.

---

## 5) Failure semantics (at S8)

* **Schema/PK breach** or any domain violation ⇒ abort S8; emit diagnostics; no partial write.
* **Overflow** ($n_{m,c} > 999{,}999$) ⇒ emit `site_sequence_overflow` (non-consuming event) and abort.
* **FK breach** (ISO not in canonical list) ⇒ abort; this is a hard structural failure.

---

## 6) Why these constraints matter (downstream contract)

* They guarantee S9 can reproduce counts and per-block permutations **exactly**, and that 1B can derive cross-country order only via `country_set.rank` (not inferred from egress sort). This separation is explicitly encoded in both schema text and the dataset dictionary.

---



# S8.4 — Event emission (audit trail)

## Purpose

Although S8 is **RNG-free**, we still emit **structured RNG events** to certify what was written and to keep the Philox lineage continuous. All events carry the **common RNG envelope** — timestamps, `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label`, and **Philox counters before/after** — and for **non-consuming** events we assert `before == after` and `draws = 0`.&#x20;

---

## Event kinds, semantics, and paths

### 1) `sequence_finalize`  — per-block attestation

**When:** exactly **once** for each $(m,c)$ block with $n_{m,c} > 0$ immediately after materialising the $\mathcal{J}_{m,c}=\{1..n_{m,c}\}$ rows.
**Role:** “Final sequence allocation per (merchant,country) block.”
**Envelope:** per common envelope; `module="1A.site_id_allocator"`, `substream_label="sequence_finalize"`, `rng_counter_before == rng_counter_after`.
**Payload (minimum):** `merchant_id=m`, `country_iso=c`, `site_count=n_{m,c}`.
**Path & schema:**
`logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` with schema pointer `schemas.layer1.yaml#/rng/events/sequence_finalize`.

### 2) `site_sequence_overflow` — guardrail (rare)

**When:** only if $n_{m,c} > U$ with $U=999{,}999$ (six-digit limit). Emit **one** event for the offending $(m,c)$, then **abort** the build.
**Role:** “Guardrail events when site sequence space is exhausted.”
**Envelope:** same as above; **non-consuming** (`before == after`).
**Payload (minimum):** `merchant_id=m`, `country_iso=c`, `site_count=n_{m,c}`, `threshold=U`.
**Path & schema:**
`logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` with schema pointer `schemas.layer1.yaml#/rng/events/site_sequence_overflow`.

**Catalog coverage.** Both labels are registered in the **data dictionary / artefact registry** under the RNG event catalog for 1A, with partitioning by `{seed, parameter_hash, run_id}` and the producing module identities.

---

## Determinism & accounting invariants

* **I-EV1 (non-consumption):** For both labels, `rng_counter_before == rng_counter_after` and the corresponding `rng_trace_log.draws = 0`. (S9.5 re-checks per-label counter advances.)&#x20;
* **I-EV2 (cardinality):**
  $\#\texttt{sequence_finalize}(m,*) = \#\{\,c: n_{m,c} > 0\,\}$.
  $\#\texttt{site_sequence_overflow}(m,*) = 0$ unless a breach occurs, in which case **one** event exists and the partition is not written.&#x20;
* **I-EV3 (payload coherence):** In every `sequence_finalize` event, `site_count` **equals** the egress block size $n_{m,c}$ for that $(m,c)$. (S9.4/9.5 cross-checks.)&#x20;

---

## Reference emission algorithm (language-agnostic)

```
INPUT:
  F (manifest_fingerprint), S_master (global_seed), run_id
  n[m,c] ≥ 0 from S7
  U := 999_999
  envelope_base := { seed=S_master, parameter_hash, manifest_fingerprint=F,
                     run_id, module="1A.site_id_allocator" }

for each (m,c):
    if n[m,c] > U:
        emit_jsonl(
          path = "logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...",
          envelope = envelope_base ⊕ { substream_label="site_sequence_overflow",
                                       rng_counter_before = C, rng_counter_after = C },
          payload  = { merchant_id=m, country_iso=c, site_count=n[m,c], threshold=U }
        )
        abort("site_sequence_overflow")

    if n[m,c] > 0:
        emit_jsonl(
          path = "logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...",
          envelope = envelope_base ⊕ { substream_label="sequence_finalize",
                                       rng_counter_before = C, rng_counter_after = C },
          payload  = { merchant_id=m, country_iso=c, site_count=n[m,c] }
        )
# Note: C is the current Philox counter for the substream; non-consuming events do not advance it.
```

Paths, partitioning, and schema pointers above are exactly those declared in the **dataset dictionary** and **artefact registry** for 1A RNG events.

---

## What S9 will assert about S8.4 (preview)

* Presence of exactly one `sequence_finalize` per non-empty $(m,c)$ block.
* **Zero-draw** envelopes for both labels (`before == after`).
* For any overflow attempt seen in logs, no egress partition exists for that `(seed,fingerprint)`; otherwise, no `site_sequence_overflow` should exist.&#x20;

All of the above mirrors your S8 spec and the registered schemas/paths for event logs; it keeps the audit trail strong without spending RNG in S8.

---

# S8.5 — Output assembly & storage

## Target dataset, path, and partitions

Write the ordered rows (from S8.2) to the immutable egress:

```
data/layer1/1A/outlet_catalogue/
  seed={S_master}/fingerprint={F}/part-*.parquet
```

The **artefact registry** and **dataset dictionary** fix the path, partitioning keys `("seed","fingerprint")`, ordering `(merchant_id, legal_country_iso, site_order)`, and the schema pointer `schemas.1A.yaml#/egress/outlet_catalogue`. Inter-country order is **not** encoded here by policy; consumers must join `country_set.rank`.

## Schema contract (must hold on write)

Enforce the egress schema exactly as declared:

* **PK:** `["merchant_id","legal_country_iso","site_order"]`.
* **Partition keys (repeated per row):** `global_seed = S_master`, `manifest_fingerprint = F` (hex64).
* **Domain predicates:**
  `site_id` matches `^[0-9]{6}$`; `site_order ≥ 1`; `final_country_outlet_count ≥ 0`; `raw_nb_outlet_draw ≥ 1`; `home_country_iso` & `legal_country_iso` are ISO-2 with FK to the canonical ISO table.&#x20;

These constraints (and the “no country order in egress” rule) are reiterated in the S8 spec and overview.

## Assembly discipline (ordering & file layout)

1. **Materialize in canonical order:** sort the in-memory stream lexicographically by `(merchant_id, legal_country_iso, site_order)` before writing (or generate in that order). This matches the dataset dictionary’s sort keys and S8.2’s construction loop.&#x20;

2. **Row-grouping (advice).** Prefer row groups that do not interleave merchants excessively; when feasible, align boundaries with `(merchant_id, legal_country_iso)` blocks to yield tight column-stats for `site_order` and faster point lookups. (Advisory; not a schema requirement.)

3. **File names & compression.** Write as `part-00000.parquet`, `part-00001.parquet`, … under the partition. Use consistent compression across parts (e.g., Snappy/Zstd); the dictionary fixes **format=parquet** (codec choice is operational).&#x20;

## Atomicity & immutability

* **Two-phase commit.** Write to a temp path `…/seed=S/fingerprint=F/_staging/*`, fsync, then atomically **rename** the directory to `…/seed=S/fingerprint=F/`. On any error, delete `_staging` (best-effort) and abort.
* **No overwrite.** If the **final** partition directory already exists (non-empty), abort: egress for `(seed,fingerprint)` is **immutable** and must not be rewritten. This immutability is stated in S8.3 and the dataset definition.&#x20;

## Dependency chain (provenance)

The registry encodes that `outlet_catalogue` depends—indirectly—on:
`country_set` → `site_id_allocator` (this module) → RNG event `sequence_finalize`. These identities govern discovery and validation joins.

## Write-time checks (fail-fast subset)

Immediately before commit, verify:

* **Partition echo:** all rows have `global_seed=S_master`, `manifest_fingerprint=F`.
* **Key shape:** `count(rows) == count(distinct merchant_id,legal_country_iso,site_order)`.
* **Per-block integrity:** for each $(m,c)$, `|rows| = final_country_outlet_count`, `site_order = 1..n_{m,c}`, and `site_id = zpad6(site_order)`.
* **FK presence:** both country codes resolve in the canonical ISO table.
* **Event sync:** for each non-empty $(m,c)$, exactly one `sequence_finalize` event was emitted (non-consuming).

## Minimal reference writer (language-agnostic)

```
INPUT:
  rows (ordered by merchant_id, legal_country_iso, site_order)
  S_master, F
  partition_dir = "…/outlet_catalogue/seed=S_master/fingerprint=F/"
  staging_dir   = partition_dir + "_staging/"

1  if exists(partition_dir) and not empty: abort("immutable_partition_exists")
2  mkdirs(staging_dir)
3  write_parquet(parts from rows, schema = schemas.1A.yaml#/egress/outlet_catalogue)
4  validate_partition(staging_dir)     # checks above (keys, regex, FK, echoes)
5  rename(staging_dir, partition_dir)  # atomic commit
6  # do not write anything else into the partition; S9 will later validate and sign
```

---



# S8.6 — Determinism & validation invariants

## A. Determinism (what makes S8 a pure function)

Fix:

* lineage keys $(F,S_{\text{master}})$ (persisted per row as `manifest_fingerprint`, `global_seed`), and
* the upstream integer allocations $\{n_{m,c}\}_{(m,c)}$ (from S7), together with the country membership $\mathcal{C}_m$ (from `country_set`).

S8 performs a **deterministic map**:

$$
\boxed{\ (\{n_{m,c}\},F,S_{\text{master}})\ \longmapsto\ \texttt{outlet_catalogue}\ }
$$

with **no RNG draws** and a fixed write order `(merchant_id, legal_country_iso, site_order)`. Replays over identical inputs yield **byte-identical** partitions; every row echoes the partition keys (`global_seed=S_{\text{master}}`, `manifest_fingerprint=F`).&#x20;

Why this holds:

1. **Construction is functional.** Each block $(m,c)$ emits rows for $j\in\{1,\dots,n_{m,c}\}$ with `site_order=j` and `site_id=σ(j)`, where $σ$ is fixed (6-digit zero-pad). No draws, no clock, no nondeterministic sources.&#x20;
2. **Stable ordering.** Emission (and write) are lexicographically ordered by `(merchant_id, legal_country_iso, site_order)`, matching dataset sort keys.&#x20;
3. **Partition echo.** Row values equal directory partitioning: `seed=S_master`, `fingerprint=F`. The dictionary/registry fix both the path and schema pointer.

---

## B. Validation checks (fail-fast, at S8 write time)

These are enforced immediately before/at write (S9 will re-assert them later).

### B1) **Count consistency (per block)**

For each $(m,c)$,

$$
\#\{\text{rows for }(m,c)\}\ =\ n_{m,c},
$$

and within the block `final_country_outlet_count` is **constant** and equals $n_{m,c}$.&#x20;

### B2) **Range & regex coupling**

Using the S8.1 encoder $σ$:

$$
\texttt{site_order}\in\{1,\dots,n_{m,c}\},\quad
\texttt{site_id} = σ(\texttt{site_order}),\quad
\texttt{site_id}\sim\texttt{c}.
$$

Regex and column domains are fixed by the egress schema.&#x20;

### B3) **Uniqueness / PK**

No duplicate primary key tuples:

$$
\big|\text{rows}\big|\ =\ \big|\text{unique}(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})\big|.
$$

This follows from the bijection $j\mapsto (\texttt{site_order}=j)$ inside each block, but is re-checked mechanically.&#x20;

### B4) **Overflow guard**

With $U=999{,}999$ (6-digit max), require

$$
\boxed{\ n_{m,c}\le U\ \ \forall(m,c)\ }.
$$

If any $n_{m,c} > U$: **emit** `site_sequence_overflow(m,c,n_{m,c},U)` (non-consuming envelope) and **abort**—no partial egress.&#x20;

### B5) **Country-order separation (policy)**

S8 **must not encode** inter-country order in `outlet_catalogue`. Cross-country order lives **only** in `country_set.rank` (0=home, then foreigns). Any consumer requiring order must join `country_set`. This is a named policy in the schema authority and reiterated in S8.

### B6) **Partition echo / lineage**

For all rows, assert:

$$
\texttt{global_seed}=S_{\text{master}},\qquad \texttt{manifest_fingerprint}=F,
$$

matching the partition directory `seed={seed}/fingerprint={fingerprint}`.&#x20;

### B7) **ISO foreign keys & minima**

`home_country_iso` and `legal_country_iso` validate against the canonical ISO table; `raw_nb_outlet_draw ≥ 1`; `final_country_outlet_count ≥ 0`. All are declared in the egress schema.&#x20;

### B8) **Event presence (non-consuming attestation)**

For each non-empty $(m,c)$, exactly one `sequence_finalize` event exists with payload `site_count=n_{m,c}` and **zero** draws (envelope `before == after`). If any overflow guard fired, a corresponding `site_sequence_overflow` event exists and the egress partition is **not** written.&#x20;

---

## C. Minimal fail-fast validator (language-agnostic)

```
INPUT:
  OUTLET (candidate), COUNTS n[m,c], ISO_TABLE, F, S_master
  EVENTS: sequence_finalize, site_sequence_overflow

# B6: partition echo
assert all(OUTLET.global_seed == S_master)
assert all(OUTLET.manifest_fingerprint == F)

# B1/B2/B3: per-block integrity + PK
for each (m,c) in unique(OUTLET.merchant_id, OUTLET.legal_country_iso):
    S := OUTLET rows for (m,c)
    n := unique(S.final_country_outlet_count); assert |n|==1
    assert |S| == n[0]
    assert sorted(S.site_order) == [1..n[0]]
    assert all(S.site_id == zpad6(S.site_order))            # σ coupling
assert |OUTLET| == |unique(merchant_id, legal_country_iso, site_order)|

# B4: overflow (guardrail)
for each (m,c) in COUNTS:
    if n[m,c] > 999_999:
        assert exists(EVENTS.site_sequence_overflow where merchant_id=m and country_iso=c)
        abort("site_sequence_overflow")
    else:
        if n[m,c] > 0:
            assert exists one EVENTS.sequence_finalize with (m,c, site_count=n[m,c])
            assert event.envelope.before == event.envelope.after   # zero-draw
        else:
            assert not exists EVENTS.sequence_finalize for (m,c)

# B7: ISO + minima
assert all(OUTLET.home_country_iso  in ISO_TABLE.country_iso)
assert all(OUTLET.legal_country_iso in ISO_TABLE.country_iso)
assert min(OUTLET.raw_nb_outlet_draw) >= 1
assert min(OUTLET.final_country_outlet_count) >= 0

# B5: country-order separation is a policy assertion (checked again in S9/hand-off)
```

The dataset dictionary and artefact registry fix the **paths**, **partition keys**, **sort keys**, and **schema refs** used above.

---

## D. What S9 will re-prove (context)

S9 later re-checks these properties and adds cross-dataset equalities (e.g., $\sum_i n_{m,i}=N_m^{\text{raw}}$), RNG accounting, and bundle signing before 1B consumption. But S8 must fail-fast on B1–B8 to prevent writing an invalid partition.&#x20;

---



# S8.7 — Complexity (deepened)

## Work and space

Let $M=$ number of merchants and

$$
T \;=\; \sum_{m=1}^{M}\ \sum_{c\in\mathcal{C}_m} n_{m,c}
$$

be the **total number of sites** to materialize.

* **Time:** row materialisation is a single pass over $(m,c)$ blocks emitting $n_{m,c}$ rows with `site_order = 1..n_{m,c}` and `site_id = σ(site_order)`. Each row’s construction is $O(1)$, hence **$\mathcal{O}(T)$** total time. There is **no RNG** and no per-row lookups beyond block-constant fields.&#x20;
* **Output size:** one Parquet row per site ⇒ **$\Theta(T)$** bytes on disk (modulo codec). The egress table is the only S8 output; path and partition keys are fixed.&#x20;
* **Sorting:** if emission follows the dataset’s sort keys `(merchant_id, legal_country_iso, site_order)`, **no extra $T\log T$ sort** is needed; the generation order is already lexicographic **within** each $(m,c)$ block and across blocks when iterating merchants then countries.&#x20;

## Memory & streaming

* **Peak memory:** with streaming writes, memory is $\mathcal{O}(B)$ where $B$ is the row-group buffer (e.g., 64–256 MB). You never need the full table in memory: emit rows for a block, flush a row group, continue. The invariants S8 enforces (block-constant `final_country_outlet_count`, sequential `site_order`) are checkable on the fly.&#x20;
* **Per-block footprint:** computing `σ(j)=zpad6(j)` and incrementing `site_order` are $O(1)$; overflow guard $n_{m,c}\le 999{,}999$ is a single comparison per block.&#x20;

## Parallelisation (while preserving determinism)

You can shard the build **by merchant** (or by merchant ranges) provided every shard:

1. iterates its merchants in ascending `merchant_id`, and
2. inside each merchant, iterates `legal_country_iso` ascending, emitting `site_order=1..n_{m,c}`.

Then **concatenate** part files in shard-key order (or let the writer generate `part-*.parquet` per shard directory) and rely on the table’s sort keys for read-time order guarantees. No global sort is required as long as each shard emits rows already in the final key order. (Inter-country order **must not** be encoded here anyway; it lives in `country_set.rank`.)&#x20;

**Concurrency guards.** The partition
`…/outlet_catalogue/seed={seed}/fingerprint={fingerprint}/`
is **immutable**; use a staging directory per shard and a single atomic move/manifest at the end. If the final partition exists, abort (no overwrite).&#x20;

## I/O considerations

* **Row-group tuning.** Prefer row groups aligned to `(merchant_id, legal_country_iso)` boundaries where feasible to tighten stats on `site_order` and accelerate block scans; not a schema constraint, but improves performance. (Schema still mandates sort keys; consumers should not infer inter-country order.)&#x20;
* **Event emission cost.** `sequence_finalize` is **one JSONL record per non-empty block** (zero-draw envelope, before=after). Its cost is $\mathcal{O}(\#\{(m,c):n_{m,c} > 0\})\le \mathcal{O}(T)$ and negligible vs. Parquet output. Overflow (rare) emits a single guard event then aborts.&#x20;

## Failure and short-circuiting

* **Overflow:** first block with $n_{m,c} > 999{,}999$ triggers `site_sequence_overflow` and **aborts**; no partial egress is committed. Cost is proportional to work done until detection.&#x20;
* **Structural violations:** PK/regex/ISO FK checks are linear in $T$ and can be enforced streaming before commit; failures short-circuit write.&#x20;

---

## Recap (concise, as requested)

* Within each $(\texttt{merchant},\texttt{legal_country})$ block, `site_id = zpad6(j)` for $j=1..n_{m,c}$; **overflow beyond `999999`** is a **hard error** with an explicit guardrail event.&#x20;
* **Primary key:** `(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})`; **country order** lives **only** in `alloc/country_set.rank` (0=home, then foreigns).&#x20;
* Emit one `sequence_finalize` per non-empty $(m,c)$; write under
  `…/seed={seed}/fingerprint={fingerprint}/…`. Complexity is $\mathcal{O}(T)$ time, $\Theta(T)$ space; no extra $T\log T$ sort if you generate in key order.

