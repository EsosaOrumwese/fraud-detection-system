# S8 — Materialize outlet stubs & per-country sequences

## Inputs → Outputs

**Inputs.**
Let the run be characterized by:

* **Manifest fingerprint** $F \in \{0,\dots,2^{256}\!-\!1\}$ (hex64), derived in S0. This value is stored per-row and used for partitioning.
* **Master seed** $S_{\text{master}} \in \{0,\dots,2^{64}\!-\!1\}$ (a.k.a. `global_seed`), fixed for the run by S0.
* **Country set** per merchant $m$: an ordered set $\mathcal{C}_m=\{c_0,\dots,c_{K_m}\}$ with `rank(c_0)=0` (home) and `rank(c_i)=i` for foreigns. Persisted already in `alloc/country_set`.
* **Integer outlet counts** per $(m,c)$: $n_{m,c}\in\mathbb{Z}_{\ge 0}$, the final largest-remainder counts from S7 (with the residual ordering cached in `ranking_residual_cache`).
* **Per-merchant flags and provenance** carried from earlier states: `single_vs_multi_flag` (hurdle outcome), `raw_nb_outlet_draw` $N_m$, `home_country_iso`, etc., available on the wide allocation record used to assemble egress. (Columns and constraints summarized below.)

**Outputs.**
A single immutable Parquet table **`egress/outlet_catalogue`**, partitioned by `seed` and `fingerprint`, with schema and constraints:

* **Primary key:** $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$.
* **Uniqueness:** additionally $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$ (same tuple) and a per-row 6-digit `site_id` string.
* **Partition keys:** `seed`, `fingerprint`; **Sort keys:** `(merchant_id, legal_country_iso, site_order)`.
* **Selected columns:**
  `manifest_fingerprint` (hex64), `merchant_id` (id64), `site_id` (string, `^[0-9]{6}$`), `home_country_iso` (ISO-2), `legal_country_iso` (ISO-2), `single_vs_multi_flag` (bool), `raw_nb_outlet_draw` (int32, ≥1), `final_country_outlet_count` (int32, ≥0), `site_order` (int32, ≥1), `global_seed` (uint64).
  *Inter-country order is **not** encoded here; consumers must join `alloc/country_set.rank`.*

Materialization path:
`data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/part-*.parquet` (artefact dependency: `country_set`, `site_id_allocator`, and the `sequence_finalize` event).

---

## S8.1 State & notation

Fix a merchant $m$ and its legal country set $\mathcal{C}_m$. For each $c\in\mathcal{C}_m$, let $n_{m,c}$ be the integer number of outlets allocated to $c$ (possibly 0). Define the **sequence space** for block $(m,c)$ as

$$
\mathcal{J}_{m,c} \;=\; \{1,2,\dots,n_{m,c}\}.
$$

Define the **site identifier encoder** $\sigma:\mathbb{Z}_{\ge1}\to\{0,1,\dots,9\}^6$ by left-padding a base-10 representation to width 6:

$$
\sigma(j) \;=\; \text{the 6-character string of } j \text{ in base 10 with leading zeros.}
$$

Equivalently, $\sigma(j) = \mathrm{sprintf}(\text{“\%06d”},j)$. The codomain is constrained by the regex `^[0-9]{6}$`.

Let the **overflow threshold** be $U=999{,}999$ (max 6-digit number).

---

## S8.2 Deterministic construction of per-country sequences

**(1) Row expansion.**
For each $(m,c)$ with $n_{m,c}>0$, create one row per $j\in\mathcal{J}_{m,c}$ with:

* `merchant_id = m`,
* `legal_country_iso = c`,
* `site_order = j`,
* `site_id = \sigma(j)` (*per-(m,c) block; resets at each country*),
* `home_country_iso` carried from merchant lineage,
* `single_vs_multi_flag`, `raw_nb_outlet_draw` carried from hurdle/NB lineage,
* `final_country_outlet_count = n_{m,c}`,
* `manifest_fingerprint = hex(F)`,
* `global_seed = S_{\text{master}}`.

This realizes a **cartesian sum** over per-country sequences and is purely functional (no RNG consumption).

**(2) Overflow guard.**
For any $(m,c)$ with $n_{m,c}>U$, raise a hard error (**abort the build**) and emit a `site_sequence_overflow` event (see S8.4). Formally,

$$
n_{m,c} \le U \quad \text{is a required invariant.}
$$

The condition reflects the declared 6-digit `site_id` format and the documented overflow guard. Per **S0.3.6**, `site_sequence_overflow` is **non‑consuming** (`draws = 0`; envelope before == after).

**(3) Ordering for write-stability.**
Before writing, order rows lexicographically by $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$. Note: **inter-country order** (home vs foreign selection order) is **not** encoded in this table and must be recovered via a join on `alloc/country_set` using its `rank` column when needed.

---

## S8.3 Constraints & keys (enforced)

From the egress schema:

1. **Domain constraints.**
   `site_id` matches `^[0-9]{6}$`; `site_order ≥ 1`; `final_country_outlet_count ≥ 0`; `raw_nb_outlet_draw ≥ 1`; ISO-2 codes validated against canonical ISO dataset via FK.

2. **Keys & uniqueness.**
   Primary key is $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$; dataset is partitioned by `(seed, fingerprint)`; sort keys mirror the construction order above.

3. **Immutability.**
   Rows are immutable for a given $(\texttt{seed},\texttt{fingerprint})$ partition.

---

## S8.4 Event emission (audit trail)

Although S8 consumes **no RNG**, we still produce explicit JSONL **RNG-event** records following the common envelope (timestamps, run id, seed, manifest fingerprint, module, substream label, and Philox counters before/after). For non-consuming events, counters **do not advance** (before = after).
Per **S0.3.6**, these events are **non‑consuming** and must report `draws = 0`.

* **`sequence_finalize`** (one per $(m,c)$ with $n_{m,c}>0$): semantic role *“Final sequence allocation per (merchant,country) block.”* Envelope fields per `rng_envelope`; module e.g. `"1A.site_id_allocator"`; label `"sequence_finalize"`. Schema catalogued; path and role defined in registry/dictionary.

* **`site_sequence_overflow`** (rare, guardrail): emitted **only** when $n_{m,c}>U$; the build aborts thereafter. Role: *“Guardrail events when site sequence space is exhausted.”*

All event schemas share the common envelope; the event catalog for 1A is registered (`rng_event_schema_catalog`).

---

## S8.5 Output assembly & storage

Write the ordered rows to:

$$
\texttt{data/layer1/1A/outlet_catalogue/seed=}S_{\text{master}}\texttt{/fingerprint=}F\texttt{/part-*.parquet}.
$$

The artefact registry fixes this path and the dependency chain (`country_set` → `site_id_allocator` → `rng_event_sequence_finalize`).

Schema columns and their constraints (regex, mins) are as declared in `schemas.1A.yaml#/egress/outlet_catalogue`; remember **country order is not encoded** here.

---

## S8.6 Determinism & validation invariants

**Determinism.** Given fixed $(F,S_{\text{master}})$ and fixed upstream allocations $\{n_{m,c}\}$, S8 is a pure function:

$$
\big(\{n_{m,c}\}, F, S_{\text{master}}\big) \;\mapsto\; \texttt{outlet_catalogue}
$$

with no RNG draws. Therefore replay is byte-stable under identical partitions. (The seed and fingerprint are also stored per-row as `global_seed` and `manifest_fingerprint`.)

**Validation checks (fail-fast):**

1. **Count consistency:** For each $(m,c)$, the number of materialized rows equals $n_{m,c}$.
2. **Range & regex:** `site_order ∈ {1,…,n_{m,c}}`; `site_id = σ(site_order)` and matches `^[0-9]{6}$`.
3. **Uniqueness:** No duplicate $(m,c,\texttt{site_order})$.
4. **Overflow:** Assert $n_{m,c}\le U$; otherwise emit `site_sequence_overflow` and abort.
5. **Country-order separation:** No attempt to encode cross-country order inside `outlet_catalogue`; downstream tests enforce that any consumer requiring order must join `alloc/country_set.rank`.

---

## S8.7 Complexity

Let $M$ be number of merchants and $T=\sum_{m}\sum_{c\in\mathcal{C}_m} n_{m,c}$ total sites. Construction is $\mathcal{O}(T)$ time and $\Theta(T)$ output size. Sorting by the schema’s sort keys is naturally consistent with generation order (stable append within $(m,c)$), so no extra $T\log T$ sort is needed if emission is performed in that key order.

---

### Recap (concise)

* Within each $(\texttt{merchant}, \texttt{legal_country})$ block, **site ids** are the 6-digit left-padded images of the **per-country** sequence $j=1..n_{m,c}$; overflow beyond `999999` is a hard error with an explicit overflow event.
* The **primary key** is $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$; country **order** itself lives in `alloc/country_set.rank`.
* A `sequence_finalize` event is logged per $(m,c)$ block; the dataset is written under `…/seed={seed}/fingerprint={fingerprint}/…`.
