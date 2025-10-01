# S9.1 — Scope, inputs, outputs (implementation-ready, **sealed** gate)

## 1) Purpose (what S9 proves)

For a fixed run lineage $\big(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id}\big)$, S9 must prove that 1A’s immutable egress:

1. **conforms to schema**,
2. is **internally consistent** with all upstream 1A artefacts and RNG logs, and
3. is **statistically sane** under governed corridors;

and, on success, emit a **sealed validation bundle** and a **`_passed.flag`** that authorise the 1A→1B hand-off **for exactly this** `manifest_fingerprint`.
**Seal definition:** `contents(_passed.flag) == SHA256(bundle.zip)` (lower-case hex).

---

## 2) Identity & authority (inputs are read-only)

### 2.1 Lineage/identity keys (must be present)

* `seed` (u64 master seed), `parameter_hash` (hex64), `manifest_fingerprint` (hex64), `run_id` (opaque run token). These are **inputs to validation** (never rewritten) and scope all lookups below.

### 2.2 Authoritative datasets & where order lives

* **Egress (fingerprint-scoped):**
  `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` with schema `schemas.1A.yaml#/egress/outlet_catalogue`. **Within-country** sequence only; **inter-country order is intentionally not encoded** here. PK and file ordering are `(merchant_id, legal_country_iso, site_order)`.
* **Country order (parameter-scoped & sole authority):**
  `country_set/seed={seed}/parameter_hash={parameter_hash}/` with schema `#/alloc/country_set`. Column `rank` (0 = home; 1..K = foreign order) is the **only** source of cross-country order. 1B must join it; S9 enforces this separation.
* **Integerisation trail (parameter-scoped):**
  `ranking_residual_cache_1A(seed,parameter_hash)` to reconstruct largest-remainder decisions (residuals in $[0,1)$ and `residual_rank`). **Dataset id carries `_1A`; schema pointer is `#/alloc/ranking_residual_cache`.**

### 2.3 RNG evidence (run-scoped)

* `rng_audit_log` (master envelope: algo, seed, counter/jump map).
* Structured **event logs** under `schemas.layer1.yaml#/rng/...` for labels used by 1A (e.g., `gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`), partitioned by `{seed, parameter_hash, run_id}`. Presence, schema conformance, **counter arithmetic**, and **zero-draw** where mandated are validated in S9.
* `rng_trace_log` (run-scoped; one record per `(module, substream_label)` with `draws`). Used for per-label draw-budget reconciliation.

### 2.4 Optional/diagnostic caches (parameter-scoped)

* `hurdle_pi_probs`, `sparse_flag`, `crossborder_eligibility_flags`. Used for corridor checks and coverage diagnostics; they do **not** change egress semantics.

---

## 3) Inputs — exact path/schema contracts (must use)

| Kind               | Path partitioning                                                                                  | Schema pointer / role                                                                                                                    |
| ------------------ | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Egress**         | `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`                                 | `schemas.1A.yaml#/egress/outlet_catalogue` (PK/order `(merchant_id,legal_country_iso,site_order)`) — **no inter-country order encoded**. |
| **Country set**    | `country_set/seed={seed}/parameter_hash={parameter_hash}/`                                         | `schemas.1A.yaml#/alloc/country_set` (rank carries cross-country order, `0=home`).                                                       |
| **Residual cache** | `ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/`                           | `#/alloc/ranking_residual_cache` (residual $[0,1)$, rank ≥1).                                                                          |
| **RNG events**     | `logs/rng/events/<label>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` | `schemas.layer1.yaml#/rng/events/<label>` (per-label schema; envelope with before/after counters).                                       |
| **Audit log**      | registry path for `rng_audit_log` (run-scoped)                                                     | envelope that pins master seed/stream map.                                                                                               |
| **Trace log**      | registry path for `rng_trace_log` (run-scoped)                                                     | per-label draw budgets used by S9.5 reconciliation.                                                                                      |

All paths/roles are documented in the **dataset dictionary** and **artefact registry**; S9 must resolve from there rather than hardcoding.

---

## 4) Outputs — what S9 writes & the 1A→1B gate

### 4.1 `validation_bundle_1A` (ZIP)

* **Location:** `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/bundle.zip`.
* **Index:** `index.json` conforming to `schemas.1A.yaml#/validation/validation_bundle` (table with `artifact_id` PK, columns `kind,path,mime,notes`).
  **`index.json` MUST include a top-level lineage object:**
  `{"seed":"<uint64>","parameter_hash":"<hex64>","manifest_fingerprint":"<hex64>","run_id":"<opaque>"}`.
* **Minimum contents:** `schema_checks.json`, `key_constraints.json`, `rng_accounting.json`, `metrics.csv`, plus `diffs/*` when mismatches arise.

### 4.2 `_passed.flag` (cryptographic **seal**)

* **Same folder**; its **file contents equal** `SHA256(bundle.zip)` (lowercase hex).
* **Registry contract:** `validation_passed_flag.digest = {sha256_of_bundle}`, with dependency `validation_passed_flag ← validation_bundle_1A`.

### 4.3 Hand-off condition to 1B (binding)

1B **may read** `outlet_catalogue(seed,fingerprint)` **iff** `_passed.flag` exists for that fingerprint **and** its content hash equals `SHA256(bundle.zip)`. Consumers **must** verify this before access; cross-country order must be recovered **only** via `country_set.rank`.

---

## 5) Boundary invariants fixed by S9.1 (assumed by S9.2+)

* **Scope coherence:** joins pair `outlet_catalogue(seed,fingerprint)` with caches at `(seed,parameter_hash)` and RNG logs at `(seed,parameter_hash,run_id)`. Mixed scopes are invalid.
* **Immutability:** inputs are read-only; S9 writes only under `…/validation/fingerprint={manifest_fingerprint}/`.
* **Single source of country order:** **only** `country_set.rank`; egress never encodes it.

---

## 6) Pre-flight presence & coherence checks (must pass before any deeper validation)

Let $P=(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id})$.

1. Exactly one `outlet_catalogue` partition exists at `(seed,fingerprint)`; at least one file present.
2. A matching `country_set` and `ranking_residual_cache_1A` exist at `(seed,parameter_hash)`.
3. Required RNG labels for 1A (per registry) are present for the run under `{seed,parameter_hash,run_id}` (e.g., `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`); absence is a **hard S9.1 fail**.
4. Dictionary/registry lookups for schema refs and paths resolve successfully (no stale IDs).
5. `rng_audit_log` **and** `rng_trace_log` partitions exist for `{seed,parameter_hash,run_id}` (trace may be empty for non-consuming labels).

---

## 7) Error taxonomy for S9.1 (machine codes & abort)

| Code                              | Trigger                                                          | Evidence artefact(s)                   |
| --------------------------------- | ---------------------------------------------------------------- | -------------------------------------- |
| `presence_missing_egress`         | Missing/empty `outlet_catalogue(seed,fingerprint)`               | `schema_checks.json` (egress section)  |
| `presence_missing_country_set`    | Missing `country_set(seed,parameter_hash)`                       | `schema_checks.json` (FK base missing) |
| `presence_missing_residual_cache` | Missing `ranking_residual_cache_1A(seed,parameter_hash)`         | `schema_checks.json`                   |
| `presence_missing_rng_streams`    | Any required RNG label absent for `{seed,parameter_hash,run_id}` | `rng_accounting.json` (coverage table) |
| `presence_missing_rng_trace`      | Missing `rng_trace_log(seed,parameter_hash,run_id)`              | `rng_accounting.json` (budget table)   |
| `registry_resolution_error`       | Schema/path cannot be resolved from dictionary/registry          | `schema_checks.json` (registry block)  |

All are **hard-fail** in S9.1; bundle may still be produced later with diagnostics, but `_passed.flag` will not be written.

---

## 8) Reference collector (handles for later S9.x)

```pseudo
function s9_1_collect_handles(seed, fingerprint, parameter_hash, run_id):
    outlet    := read_partition("outlet_catalogue", seed, fingerprint)                      # schemas.1A.yaml#/egress/outlet_catalogue
    cset      := read_partition("country_set", seed, parameter_hash)                        # #/alloc/country_set
    resid     := read_partition("ranking_residual_cache_1A", seed, parameter_hash)          # #/alloc/ranking_residual_cache
    hurdle    := read_param_scoped("hurdle_pi_probs", parameter_hash, optional=true)
    sparse    := read_param_scoped("sparse_flag", parameter_hash)
    xborder   := read_param_scoped("crossborder_eligibility_flags", parameter_hash)
    rng_audit := read_run_scoped("rng_audit_log", seed, parameter_hash, run_id)
    rng_trace := read_run_scoped("rng_trace_log", seed, parameter_hash, run_id)
    events := {
       "gumbel_key":             read_events("gumbel_key", seed, parameter_hash, run_id),
       "dirichlet_gamma_vector": read_events("dirichlet_gamma_vector", seed, parameter_hash, run_id),
       "residual_rank":          read_events("residual_rank", seed, parameter_hash, run_id),
       "sequence_finalize":      read_events("sequence_finalize", seed, parameter_hash, run_id)
    }
    assert exists(outlet) and exists(cset) and exists(resid) and exists(rng_audit) and exists(rng_trace)
    for label in required_labels: assert exists(events[label])  # coverage pre-check
    return {outlet,cset,resid,hurdle,sparse,xborder,rng_audit,rng_trace,events}
```

Path templates and required labels are taken from the registry/dictionary; **do not** hardcode.

---

## 9) Conformance tests (must pass for S9.1)

1. **Presence happy-path:** All partitions present; collector returns handles; proceed to S9.2+. ✔︎
2. **Missing RNG stream:** Drop `sequence_finalize` → expect `presence_missing_rng_streams` with coverage table in `rng_accounting.json`. ✔︎
3. **Mixed scopes:** Provide `country_set` at wrong `parameter_hash` → expect registry/scope failure; S9.1 aborts. ✔︎
4. **Egress absent:** No files at `(seed,fingerprint)` → `presence_missing_egress`; no further checks run. ✔︎
5. **Missing trace log:** Omit `rng_trace_log` for the run → `presence_missing_rng_trace`. ✔︎

---

## 10) Notes for S9.2 (notation) & beyond

S9.2 will bind the symbol table:
$n_{m,i}$ from **row counts** in egress (so $n_{m,i}\ge 0$; note: persisted **rows** always carry `final_country_outlet_count ≥ 1`), $s_{m,i,k}$ and `site_id` bijection (`zpad6`), $R_{m,i}$/$r_{m,i}$ from the residual cache, and the set $\mathcal{I}_m$ + order from `country_set.rank`. These definitions are then used in S9.3–S9.7 for structural checks, RNG accounting, and the bundle.

---

# S9.2 — Notation

## 1) Index sets, scope, and partitions (binding)

* **Merchants.** $m\in\mathcal{M}$ (values come from keys present in the inputs for this run).
* **Countries (canonical).** $i\in\mathcal{I}$ = ISO-3166-1 alpha-2 domain from the canonical ingress table referenced by schema FKs.
* **Legal countries for a merchant (sole authority).**

  $$
  \mathcal{I}_m \;=\; \{\, i : (m,i)\in\texttt{country_set}\ \text{at }(seed,\ \textit{parameter_hash})\,\},
  $$

  totally ordered by `rank` with $0$ = home. **Cross-country order exists only here**; egress never encodes it.

**Scope discriminants used everywhere in S9.**
Egress is keyed by `(seed, fingerprint)`, allocation caches by `(seed, parameter_hash)`, RNG event/trace logs by `(seed, parameter_hash, run_id)`. S9 joins only across matching scopes; mixed scopes are invalid.

---

## 2) Observables from egress `outlet_catalogue` (per $(m,i,k)$)

Let `OUT` denote the immutable egress partition at
`data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`, schema `schemas.1A.yaml#/egress/outlet_catalogue`. Its **PK and sort keys** are $(\texttt{merchant_id},\ \texttt{legal_country_iso},\ \texttt{site_order})$; **inter-country order is not encoded** here.

### 2.1 Count and within-country sequence

* **Materialised count** (defined by rows):

  $$
  n_{m,i} \;=\; \#\{\text{rows in OUT where }(\texttt{merchant_id},\texttt{legal_country_iso})=(m,i)\}.
  $$

  If $n_{m,i}=0$, no row for $(m,i)$ exists in egress. If $n_{m,i}\ge 1$, every persisted row must carry the same `final_country_outlet_count = n_{m,i}` (S8 contract; re-checked in S9.3/S9.4).

* **Within-country order.** For the $k$-th row of block $(m,i)$,

  $$
  s_{m,i,k}\in\{1,\dots,n_{m,i}\}\ \text{is the value of }\texttt{site_order}.
  $$

  The multiset ${s_{m,i,k}}$ must equal ${1,\dots,n_{m,i}}$ (gap-free permutation).

### 2.2 Site identifier & the encoder bijection

* **Encoder.** $\sigma:\mathbb{Z}_{\ge1}\to{0,1,\dots,9}^6$, $\sigma(j)=\mathrm{zpad6}(j)$ (left-pad base-10 to width 6). Regex: `^[0-9]{6}$`.
* **ID on row $k$.** $\text{id}*{m,i,k}=\texttt{site_id}\in{000000,\dots,999999}$. For persisted rows, S8 requires $\text{id}*{m,i,k}=\sigma(s_{m,i,k})$; S9 asserts the same. (Capacity guard $n_{m,i}\le 999,999$ enforced upstream; overflow aborts S8.)
* **Partial inverse.** $\sigma^{-1}(\texttt{site_id})=j$ iff the regex matches and $000001\le\texttt{site_id}\le 999999$; S9 may use this for diagnostics only (schema already provides `site_order`).

### 2.3 Merchant-wide constants repeated on rows

* $H_m\in{0,1}$ = `single_vs_multi_flag` (boolean).
* $N^{\mathrm{raw}}*m\in\mathbb{Z}*{\ge1}$ = `raw_nb_outlet_draw` (identical on **all** rows of merchant $m$); S9 later checks conservation $\sum_{i\in\mathcal{I}*m} n*{m,i} = N^{\mathrm{raw}}_m$.
* `home_country_iso` (constant per merchant; must equal the `country_set` row with `rank=0`). `legal_country_iso` = $i$ on the row.
* Lineage echoes: every row carries `manifest_fingerprint` (hex64) and `global_seed` (u64) equal to the partition tokens `(fingerprint, seed)`.

---

## 3) Observables from parameter-scoped caches (allocation trail)

All read from `(seed, parameter_hash)`.

* **Residuals & their order (largest-remainder trail).**
  $R_{m,i}\in[0,1)$ = `ranking_residual_cache_1A.residual`;
  $r_{m,i}\in{1,2,\dots}$ = `ranking_residual_cache_1A.residual_rank` (1 = largest). Used in S9.4.

* **Optional hurdle probability.** $\pi_m\in[0,1]$ from `hurdle_pi_probs` (diagnostic only; corridors may reference it).

* **As needed later:** `sparse_flag`, `crossborder_eligibility_flags` at the same scope; they never change egress semantics but appear in corridor/coverage diagnostics.

---

## 4) RNG lineage objects (run-scoped)

* **Audit envelope** $E=(\text{algo},S_{\text{master}},\text{stream map},\text{initial counters},\dots)$ from `rng_audit_log`.
* **Event traces** $T_\ell$ for labels $\ell \in \{\texttt{gumbel_key}, \texttt{dirichlet_gamma_vector}, \texttt{residual_rank}, \texttt{sequence_finalize}, \dots\}$: JSONL tuples $(\texttt{rng_counter_before}, \texttt{draws}, \texttt{rng_counter_after}, \texttt{key})$ with a common envelope. Presence, schema conformance, **monotone counter advance**, and **zero-draw** where mandated are asserted in S9.5/S9.6.
* **Trace log** with per-label budgets at the same run scope: `rng_trace_log(seed, parameter_hash, run_id)`.

---

## 5) Canonical column ↔ symbol table (dataset-backed)

| Dataset.column                 | Symbol               | Domain / notes                                                           |
|--------------------------------|----------------------|--------------------------------------------------------------------------|
| OUT.manifest_fingerprint       | $F$                  | hex64, equals `{fingerprint}` partition token.                           |
| OUT.global_seed                | $S_{\text{master}}$  | u64, equals `{seed}` partition token.                                    |
| OUT.merchant_id                | $m$                  | id64 (PK component).                                                     |
| OUT.legal_country_iso          | $i$                  | ISO-2 (PK component; FK to canonical ISO).                               |
| OUT.home_country_iso           | $\text{home}(m)$     | ISO-2; must equal `country_set.rank=0` for $m$.                          |
| OUT.site_order                 | $s_{m,i,k}$          | ${1,\dots,n_{m,i}}$ (PK component).                                      |
| OUT.site_id                    | $\text{id}_{m,i,k}$  | `^[0-9]{6}$`, equals $\sigma(s_{m,i,k})$.                                |
| OUT.final_country_outlet_count | $n_{m,i}$ (row echo) | Constant per $(m,i)$ when $n_{m,i}\ge1$. For $n_{m,i}=0$, no row exists. |
| OUT.single_vs_multi_flag       | $H_m$                | boolean; constant per $m$.                                               |
| OUT.raw_nb_outlet_draw         | $N^{\mathrm{raw}}_m$ | $\mathbb{Z}_{\ge1}$; constant per $m$.                                   |
| CST.country_iso                | $i$                  | ISO-2; PK with `merchant_id` in `country_set`.                           |
| CST.rank                       | $\text{rank}_{m}(i)$ | $0$=home; $1..K_m$=foreign order (sole authority).                       |
| RC.residual                    | $R_{m,i}$            | $[0,1)$ (exclusive max).                                                 |
| RC.residual_rank               | $r_{m,i}$            | ${1,2,\dots}$ (1 = largest).                                             |

---

## 6) Helper operators & sets (used later; defined now)

* **Row selection.** $\text{Rows}*{OUT}(m,i)={,\text{rows}\in \text{OUT}: (\texttt{merchant_id},\texttt{legal_country_iso})=(m,i),}$; then $n*{m,i}=|\text{Rows}_{OUT}(m,i)|$.
* **Presence predicate.** $\mathbf{1}^{\text{egress}}*{m,i}=\mathbb{I}[n*{m,i}>0]$. Define $\mathcal{I}^{\text{egress}}*m={,i:\mathbf{1}^{\text{egress}}*{m,i}=1,}$.
* **Block key sets.** $\mathcal{K}*{m,i}={(m,i,j): j\in{1,\dots,n*{m,i}}}$ and $\mathcal{I!D}*{m,i}={(m,i,\sigma(j)): j\in{1,\dots,n*{m,i}}}$ (defined only if $n_{m,i}\ge1$).
* **Z-pad encoder & inverse.** As in §2.2; $\sigma^{-1}$ defined where applicable.
* **Rank order projection.** For any list of foreign ISO codes $L\subseteq \mathcal{I}*m\setminus{\text{home}(m)}$,
  $\text{order}*{\text{country}}(L)$ = sort $L$ by `CST.rank` ascending. **Never** derive this from egress.
* **Decimal quantiser (for later corridor checks).** $q_8(x)=\text{round_half_to_even}(x,\ 8\text{ dp})$. (Defined here; not applied in S9.2.)

---

## 7) Deterministic decoding rules (zero ambiguity)

Given the authoritative inputs from S9.1:

1. **Counts.** Compute $n_{m,i}$ purely as egress row counts. If $n_{m,i}\ge1$, every row in $\text{Rows}*{OUT}(m,i)$ must echo `final_country_outlet_count = n_{m,i}` (validated later). If $n*{m,i}=0$, **no** row exists and no echo is present.

2. **Within-country order.** ${s_{m,i,k}}={1..n_{m,i}}$ and $\text{id}*{m,i,k}=\sigma(s*{m,i,k})$ (bijective).

3. **Cross-country order.** When an ordered country list is needed, **always** join to `country_set` and sort by `rank` (0 home, then $1..K_m$). Never infer cross-country order from any egress pattern (file/row ordering).

4. **Merchant constants.** $H_m$, $N^{\mathrm{raw}}_m$, and $\text{home}(m)$ are constants per $m$ discoverable from egress rows; $\text{home}(m)$ must match the `rank=0` row in `country_set`.

5. **Residual order.** When reconstructing integerisation tie-breaks, sort $R_{m,i}$ **descending** with ISO asc as secondary to obtain the deterministic $r_{m,i}$ ranking used by S7. (Cache already persists `residual_rank`; rule stated for completeness.)

---

## 8) Reference extraction routine (notation only — no validation yet)

```pseudo
function s9_2_symbols(OUT, CST, RC):
    # OUT = outlet_catalogue(seed, fingerprint)
    # CST = country_set(seed, parameter_hash)
    # RC  = ranking_residual_cache_1A(seed, parameter_hash)

    # 1) Per-merchant legal set with order (sole authority)
    I_m := { m -> list of (i, rank) from CST where merchant_id=m ordered by rank }

    # 2) Per-(m,i) egress counts and sequences
    n[m,i]  := count_rows(OUT where merchant_id=m and legal_country_iso=i)
    S[m,i]  := multiset(site_order from same rows)          # within-country sequence
    ID[m,i] := multiset(site_id   from same rows)           # 6-digit strings

    # 3) Merchant constants (echoed per row)
    H[m]    := constant value of single_vs_multi_flag across rows of m
    Nraw[m] := constant value of raw_nb_outlet_draw  across rows of m
    home[m] := constant value of home_country_iso     across rows of m

    # 4) Residuals and ranks (parameter-scoped)
    R[m,i]  := RC.residual(m,i)
    r[m,i]  := RC.residual_rank(m,i)

    return {I_m, n, S, ID, H, Nraw, home, R, r}
```

S9.3–S9.6 will apply schema/PK/FK predicates, equality proofs, and RNG replay using these symbols; S9.7 packages the bundle and `_passed.flag`.

---

## 9) Sanity notes (what S9.2 **does not** do)

* **No schema/key checks here.** Those are S9.3; S9.2 only defines names and how to read them.
* **No RNG accounting yet.** Counters/labels are introduced in §4; replay and zero-draw proofs are S9.5/S9.6.
* **No corridors yet.** Quantiser $q_8$ is defined but not applied until S9.6.

---

## 10) Quick conformance checks for notation extraction (should pass if inputs are well-formed)

1. For any $(m,i)$ with $n_{m,i}\ge1$, `max(S[m,i]) = n[m,i]` and `|S[m,i]| = n[m,i]`. ✔︎
2. For any $(m,i)$ with $n_{m,i}\ge1$ and any $s\in S[m,i]`, `sigma(s)`is in`ID[m,i]\`. ✔︎
3. For each merchant $m$, `home[m] == country_set.rank0.country_iso(m)`. ✔︎

---

This locks **S9.2**: the exact symbol table; where each symbol comes from (dataset, partition scope, and column); the bijection between `site_order` and `site_id`; the strict separation of **within-country** order (egress) from **cross-country** order (`country_set`); and the helper operators used to express validations, RNG replay, and corridor checks in the rest of S9.

---

# S9.3 — Structural validations

## 1) Scope (what S9.3 proves, strictly structural)

Given the fixed lineage $(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id})$ established in S9.1, S9.3 validates — **before** any RNG replay or corridor stats — that:

1. **All referenced datasets match their JSON-Schema contracts** (types, ranges, regex), with authoritative schema pointers from the dictionary/registry.
2. **Primary keys and partition echoes** hold exactly (no duplicates; per-row echo equals directory tokens).
3. **Foreign keys (ISO-3166), dataset scoping, and cross-dataset domain relations** are consistent.
4. **Block-level invariants** on egress are satisfied: gap-free within-country sequence; `site_id = zpad6(site_order)`; constant and correct `final_country_outlet_count` per $(m,i)$; zero-block elision (no rows when $n_{m,i}=0$); and **secondary uniqueness** of `site_id` within each $(m,i)$ block.

**Where order lives:** egress never encodes cross-country order; **only** `country_set.rank` carries it. This is a hard policy/contract, reasserted here.

---

## 2) Datasets, paths, partitions, schema pointers (authoritative)

| Dataset                          | Path (partitioned)                                                                      | Partitions                  | Schema pointer                                                                                                                                    |
| -------------------------------- | --------------------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **outlet_catalogue**            | `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`       | `["seed","fingerprint"]`    | `schemas.1A.yaml#/egress/outlet_catalogue` (PK/ordering = `["merchant_id","legal_country_iso","site_order"]`; **no inter-country order encoded**) |
| **country_set**                 | `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/`               | `["seed","parameter_hash"]` | `schemas.1A.yaml#/alloc/country_set` (column `rank`: 0=home; **sole authority** for cross-country order)                                          |
| **ranking_residual_cache_1A** | `data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/` | `["seed","parameter_hash"]` | `schemas.1A.yaml#/alloc/ranking_residual_cache` (residual $[0,1)$, ISO FK)                                                                      |

All lookups (paths, schema refs) must be resolved **from the dictionary/registry**, not hard-coded.

---

## 3) Dataset-local schema predicates (must-hold)

### 3.1 `outlet_catalogue` (egress)

* **PK & ordering (schema/dictionary):** primary key and sort keys are **exactly** `(merchant_id, legal_country_iso, site_order)`.
* **Secondary uniqueness (validator):** within each `(merchant_id, legal_country_iso)` block, the pair **`(merchant_id, legal_country_iso, site_id)` must be unique** (guards against duplicate IDs).
* **Regex & ranges:**
  `manifest_fingerprint ~ ^[a-f0-9]{64}$`; `site_id ~ ^[0-9]{6}$`; `site_order ≥ 1`; `raw_nb_outlet_draw ≥ 1`; `home_country_iso` and `legal_country_iso` are ISO-2 with FK to the canonical ISO table referenced by schema; `final_country_outlet_count` is a **row echo of the block size** (see §4).
* **Partition echo:** **every row** must satisfy `global_seed == {seed}` and `manifest_fingerprint == {fingerprint}` (directory tokens).
* **Policy note (structural check):** dataset **does not** encode cross-country order; consumers must join `country_set.rank`. S9 asserts the **absence** of any cross-country ordering column (e.g., `country_rank`, `country_sequence`).

### 3.2 `country_set` (allocation)

* **PK:** `(merchant_id, country_iso)`; `rank` is integer with `0` = home and increasing foreign order. ISO FK applies.
* **Per-merchant cardinality:** **exactly one** row with `rank=0`.
* **Per-merchant contiguity:** the multiset of ranks must be **exactly** `{0,1,2,…,K_m}` for some $K_m \ge 0$ (no gaps, no duplicates per rank).

### 3.3 `ranking_residual_cache_1A`

* **PK:** `(merchant_id, country_iso)`; `residual ∈ [0,1)` with `exclusiveMaximum: true`; ISO FK applies.
* **Per-merchant residual-rank contiguity:** if cache keys for merchant $m$ are $\mathcal{I}_m$, then the set of `residual_rank` must be **exactly** `{1,2,…,|\mathcal{I}_m|}` (unique per country; no gaps).

---

## 4) Cross-field & block invariants on egress (normative)

Let $\text{Rows}_{OUT}(m,i)$ be the egress rows for merchant $m$, legal country $i$ (possibly empty).

1. **Gap-free within-country sequence.**
   ${,\texttt{site_order},} = {1,2,\dots,n_{m,i}}$ where $n_{m,i} = |\text{Rows}*{OUT}(m,i)|$. (If $n*{m,i}=0$, no row exists.)

2. **Site-ID encoder (bijection).** For each row:

   $$
   \texttt{site_id} = \mathrm{zpad6}(\texttt{site_order}) \quad\text{and}\quad \texttt{site_id} \sim \texttt{"^[0-9]{6}\$"}.
   $$

   This couples the regex to construction used by S8.2.

3. **Block constant echo.**
   For $n_{m,i}\ge 1$: every row $r\in \text{Rows}_{OUT}(m,i)$ has `final_country_outlet_count == n_{m,i}` (constant across the block). (**Zero-blocks emit no rows**; the echo must never appear with value 0.)

4. **Merchant constants.**
   On all rows for merchant $m$: `single_vs_multi_flag` and `raw_nb_outlet_draw` are merchant-constants, and `home_country_iso` is constant and must equal the `country_set` row where `rank=0`.

5. **Secondary uniqueness (row-level).**
   Within each block $(m,i)$, all `site_id` values must be distinct.

6. **Partition echo (row↔path).**
   Already listed in §3.1; re-asserted here as a cross-field equality with directory tokens.

---

## 5) Foreign keys, scoping, and cross-dataset domains

* **ISO FK:** every `home_country_iso`, `legal_country_iso` (egress), and every `country_iso` in the allocation tables must be present in the canonical ISO domain referenced by the schemas.
* **Scope coherence:** pairs `outlet_catalogue(seed,fingerprint)` with `country_set(seed,parameter_hash)` / `ranking_residual_cache_1A(seed,parameter_hash)`; mixed scopes are invalid (flagged in S9.1).
* **Cross-dataset domain relations (structural):**

  * **Egress ⊆ Country-set:** For each merchant $m$, the set ${,i:,n_{m,i}>0,}$ **must be a subset of** ${,i:,(m,i)\in\texttt{country_set},}$.
  * **Residual-cache keys = Country-set keys:** For each $m$, keys present in `ranking_residual_cache_1A` **must equal** the keys present in `country_set` (same $(m,i)$ pairs).

---

## 6) Error taxonomy (machine codes; all are hard-fail)

**Schema / FK / echo**

* `s9.3.schema_violation.outlet_catalogue` — JSON-Schema mismatch in egress (type/range/regex).
* `s9.3.schema_violation.country_set` — schema mismatch in `country_set`.
* `s9.3.schema_violation.residual_cache` — schema mismatch in `ranking_residual_cache_1A`.
* `s9.3.fk_iso_breach` — any ISO FK failure in egress or allocation datasets.
* `s9.3.partition_echo_mismatch` — any row where `global_seed` ≠ `{seed}` or `manifest_fingerprint` ≠ `{fingerprint}`.

**Keys / ordering**

* `s9.3.pk_duplicate.outlet_catalogue` — duplicate `(merchant_id,legal_country_iso,site_order)`.
* `s9.3.pk_duplicate.country_set` — duplicate `(merchant_id,country_iso)` in `country_set`.
* `s9.3.pk_duplicate.residual_cache` — duplicate `(merchant_id,country_iso)` in residual cache.
* `s9.3.uk_duplicate.site_id_in_block` — duplicate `site_id` within a `(merchant_id,legal_country_iso)` block.
* `s9.3.sort_order_break` — (optional) rows not non-decreasing in `(merchant_id,legal_country_iso,site_order)` across files.

**Block invariants**

* `s9.3.block_count_mismatch` — for some $(m,i)$, `#rows != final_country_outlet_count` (constant echo violated).
* `s9.3.site_order_gap_or_dup` — within $(m,i)$, `site_order` not exactly ${1..n_{m,i}}$.
* `s9.3.site_id_mismatch` — any row with `site_id != zpad6(site_order)` or failing the 6-digit regex.
* `s9.3.merchant_constant_drift` — merchant-constant fields (`single_vs_multi_flag`, `raw_nb_outlet_draw`, or `home_country_iso`) vary across rows for the same merchant.

**Country-set & residual-cache structure**

* `s9.3.rank0_cardinality_breach` — missing or multiple `rank=0` rows for a merchant in `country_set`.
* `s9.3.rank_contiguity_breach` — ranks per merchant are not exactly `{0..K_m}` (gap/dup).
* `s9.3.residual_rank_contiguity_breach` — residual ranks per merchant are not exactly `{1..|I_m|}` (gap/dup).
* `s9.3.residual_cache_key_mismatch` — keys in residual cache differ from `country_set` keys for the merchant.
* `s9.3.egress_country_not_in_country_set` — egress contains country $i$ for merchant $m$ not present in `country_set`.

**Policy**

* `s9.3.cross_country_order_in_egress` — any attempt to encode cross-country order in `outlet_catalogue` (e.g., unexpected column).

All failures must be recorded in bundle artefacts (`schema_checks.json`, `key_constraints.json`, `fk_checks.json`, `egress_block_invariants.json`, `diffs/*`) to make the proof reproducible.

---

## 7) Reference validator (single pass + group reductions)

```pseudo
function validate_structural(seed, fingerprint, parameter_hash,
                             OUT: iterator over outlet_catalogue rows,
                             CST: iterator over country_set rows,
                             RC:  iterator over ranking_residual_cache rows,
                             ISO: set of valid ISO2 codes):

  # A) Schema validations (use JSON-Schema pointers from dictionary/registry)
  assert jsonschema_validate("schemas.1A.yaml#/egress/outlet_catalogue", OUT)         # s9.3.schema_violation.outlet_catalogue
  assert jsonschema_validate("schemas.1A.yaml#/alloc/country_set", CST)               # s9.3.schema_violation.country_set
  assert jsonschema_validate("schemas.1A.yaml#/alloc/ranking_residual_cache", RC)     # s9.3.schema_violation.residual_cache

  # B) Collect country_set & residual_cache domains and structure
  seen_cst := HashSet<(m,i)>()
  rank0    := HashMap<m, ISO2>()
  ranks_by_m := HashMap<m, List<int>>()

  for c in CST:
      key := (c.merchant_id, c.country_iso)
      if key in seen_cst: raise s9.3.pk_duplicate.country_set
      seen_cst.add(key)
      if c.country_iso notin ISO: raise s9.3.fk_iso_breach
      ranks_by_m.setdefault(c.merchant_id, []).append(c.rank)
      if c.rank == 0:
         if c.merchant_id in rank0: raise s9.3.rank0_cardinality_breach
         rank0[c.merchant_id] = c.country_iso

  # rank contiguity per merchant
  for m, ranks in ranks_by_m.items():
      if 0 notin ranks: raise s9.3.rank0_cardinality_breach
      K := max(ranks)
      if set(ranks) != set(range(0, K+1)): raise s9.3.rank_contiguity_breach

  seen_rc := HashSet<(m,i)>()
  rrank_by_m := HashMap<m, List<int>>()

  for t in RC:
      key := (t.merchant_id, t.country_iso)
      if key in seen_rc: raise s9.3.pk_duplicate.residual_cache
      seen_rc.add(key)
      if t.country_iso notin ISO: raise s9.3.fk_iso_breach
      rrank_by_m.setdefault(t.merchant_id, []).append(t.residual_rank)

  # residual rank contiguity per merchant
  for m, rr in rrank_by_m.items():
      L := len([1 for (mm,ii) in seen_cst if mm==m])
      if set(rr) != set(range(1, L+1)): raise s9.3.residual_rank_contiguity_breach

  # cross-dataset domain equality
  for key in seen_rc:
      if key notin seen_cst: raise s9.3.residual_cache_key_mismatch

  # C) Per-row checks on egress (echo, ISO FK, encoder, keys)
  seen_pk   := HashSet<(m,i,j)>()                          # (merchant_id, legal_country_iso, site_order)
  seen_sid  := HashSet<(m,i,site_id)>()                    # secondary uniqueness
  rows_in_block := HashMap<(m,i), int>()
  declared_n    := HashMap<(m,i), int>()
  max_site      := HashMap<(m,i), int>()
  merch_flag    := HashMap<m, bool>()
  merch_nraw    := HashMap<m, int>()
  merch_home    := HashMap<m, ISO2>()
  egress_keys   := HashSet<(m,i)>()

  for r in OUT:
      # Partition echo
      if r.global_seed != seed or r.manifest_fingerprint != fingerprint:
          raise s9.3.partition_echo_mismatch

      # ISO FKs (egress columns)
      if r.home_country_iso notin ISO or r.legal_country_iso notin ISO:
          raise s9.3.fk_iso_breach

      # Regex/range
      assert matches(r.manifest_fingerprint, "^[a-f0-9]{64}$")
      assert matches(r.site_id, "^[0-9]{6}$")
      assert r.site_order >= 1
      assert r.raw_nb_outlet_draw >= 1

      # Site encoder & keys
      if r.site_id != zpad6(r.site_order): raise s9.3.site_id_mismatch
      pk  := (r.merchant_id, r.legal_country_iso, r.site_order)
      sid := (r.merchant_id, r.legal_country_iso, r.site_id)
      if not add_unique(seen_pk, pk):  raise s9.3.pk_duplicate.outlet_catalogue
      if not add_unique(seen_sid, sid): raise s9.3.uk_duplicate.site_id_in_block

      # Block tallies (constant echo & counts)
      k := (r.merchant_id, r.legal_country_iso)
      egress_keys.add(k)
      rows_in_block[k] = rows_in_block.get(k,0) + 1
      max_site[k]      = max(max_site.get(k,0), r.site_order)
      if k not in declared_n:
          if r.final_country_outlet_count == 0: raise s9.3.block_count_mismatch
          declared_n[k] = r.final_country_outlet_count
      else:
          if declared_n[k] != r.final_country_outlet_count: raise s9.3.block_count_mismatch

      # Merchant constants
      m := r.merchant_id
      if m notin merch_flag: merch_flag[m] = r.single_vs_multi_flag
      elif merch_flag[m] != r.single_vs_multi_flag: raise s9.3.merchant_constant_drift

      if m notin merch_nraw: merch_nraw[m] = r.raw_nb_outlet_draw
      elif merch_nraw[m] != r.raw_nb_outlet_draw: raise s9.3.merchant_constant_drift

      if m notin merch_home: merch_home[m] = r.home_country_iso
      elif merch_home[m] != r.home_country_iso: raise s9.3.merchant_constant_drift

  # D) Close block checks: gap-free & echo equality
  for k in rows_in_block.keys():
      n_obs  = rows_in_block[k]
      n_decl = declared_n[k]
      if n_obs != n_decl: raise s9.3.block_count_mismatch
      if max_site[k] != n_obs: raise s9.3.site_order_gap_or_dup

  # E) Egress ⊆ Country-set per merchant
  for (m,i) in egress_keys:
      if (m,i) notin seen_cst: raise s9.3.egress_country_not_in_country_set

  # F) Merchant home-country coherence (egress vs country_set.rank=0)
  for m in merch_home.keys():
      if m notin rank0 or rank0[m] != merch_home[m]:
          raise s9.3.merchant_constant_drift   # or dedicated: s9.3.home_mismatch

  return OK
```

---

## 8) Evidence artefacts (written into the bundle)

S9.3 emits (append-only; final packaging in S9.7):

* `schema_checks.json` — for each dataset: `{dataset_id, files_scanned, violations:[{path, pointer, message}]}`.
* `key_constraints.json` — PK/UK cardinality proofs and any duplicates with sample offending keys.
* `fk_checks.json` — ISO FK coverage table and breaches.
* `egress_block_invariants.json` — per $(m,i)$: `n_rows`, `declared_n`, `max_site_order`, flags for `gap_free`, `encoder_ok`.
* `domain_diffs.json` — per merchant, diffs for **egress vs country_set** keys and **residual_cache vs country_set** keys.
* `policy_assertions.json` — presence of cross-country order **only** in `country_set.rank`.

These land under `data/layer1/1A/validation/fingerprint={fingerprint}/bundle.zip` in S9.7, and `_passed.flag` must hash to the bundle bytes.

---

## 9) Conformance tests (must-pass)

1. **Happy path:** pick $m$ with `country_set` entries `(GB rank=0, US rank=1)`, egress rows for GB×3 and US×2. Expect: PK unique; UK on `site_id` per block; per-block `site_order=1..n`; `site_id=zpad6(site_order)`; `final_country_outlet_count` equals block size; echo matches partition; ISO FK holds; `home_country_iso`==GB==rank0; ranks `{0,1}` contiguous. ✔︎
2. **Zero-block elision:** include FR in `country_set` but $n_{m,FR}=0`. Expect: **no** FR rows in egress; no `final_country_outlet_count=0\`; all checks pass. ✔︎
3. **PK duplicate:** duplicate `(merchant_id,legal_country_iso,site_order)` → `s9.3.pk_duplicate.outlet_catalogue`. ✔︎
4. **Site-ID UK breach:** duplicate `site_id` inside a block → `s9.3.uk_duplicate.site_id_in_block`. ✔︎
5. **Site-ID mismatch:** set `site_id="000010"` for `site_order=9` → `s9.3.site_id_mismatch`. ✔︎
6. **Block echo drift:** write two GB rows but set `final_country_outlet_count=3` → `s9.3.block_count_mismatch`. ✔︎
7. **Partition echo mismatch:** row’s `manifest_fingerprint` ≠ directory token → `s9.3.partition_echo_mismatch`. ✔︎
8. **ISO FK breach:** `legal_country_iso="ZZ"` not in canonical ISO → `s9.3.fk_iso_breach`. ✔︎
9. **Home mismatch:** `home_country_iso` on egress ≠ `country_set.rank=0` → `s9.3.merchant_constant_drift` (or `home_mismatch`). ✔︎
10. **Egress country not in country_set:** egress has CA but `country_set` for $m$ lacks CA → `s9.3.egress_country_not_in_country_set`. ✔︎
11. **Rank contiguity breach:** ranks `{0,2}` without `1` → `s9.3.rank_contiguity_breach`. ✔︎
12. **Residual cache key mismatch/contiguity:** residual cache missing US for $m$ or ranks not `{1..|I_m|}` → respective errors. ✔︎

---

## 10) Operational notes (binding where stated)

* **Authoritative schemas are JSON-Schema** per Schema Authority Policy; do **not** validate against Avro in source. If Avro is needed downstream, generate at build/release; the validator still uses JSON-Schema.
* **Dictionary/registry are the source of truth** for `path`, `partitioning`, `schema_ref`, and lineage notes (producer/consumer). The validator reads these at runtime and asserts conformance.
* **No inter-country order in egress**: keep this check active (policy assertion + absence of such columns); consumers must join `country_set.rank`.

---

This locks **S9.3**: dataset contracts from the dictionary/registry; executable schema, PK/UK, FK, echo and block predicates; complete error taxonomy; a reference validator; bundle evidence artefacts; and conformance tests — all aligned to S8’s construction and the Schema Authority Policy.

---

# S9.4 — Cross-dataset invariants

## 1) Scope (what S9.4 proves)

For a fixed lineage $P=(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id})$, S9.4 asserts **bit-exact equalities** (integers/strings only) across:

1. **Realisation and conservation:** egress site counts $n_{m,i}$ and merchant-level **raw draw** $N^{\mathrm{raw}}_m$.
2. **Coverage and order:** membership of legal countries and **cross-country order** derived **only** from `country_set` (and—if enabled—its *provenance* via the RNG `gumbel_key` label).
3. **Largest-remainder reproducibility:** persisted residuals/ranks used by integerisation.
4. **Within-country sequencing & finalisation coverage:** bijection `site_order ↔ site_id`, and **exactly one** `sequence_finalize` per non-empty $(m,i)$ block (event **coverage** only; non-consumption proof is S9.5).

**Scoping rule:** all **event-side** counts are over `(seed, parameter_hash, run_id)`; all **egress-side** counts are over `(seed, fingerprint)`. The lineage tuple in S9.1 binds them. No numeric tolerances appear in S9.4.

---

## 2) Inputs & authorities (recap)

* **Egress:** `outlet_catalogue/seed={seed}/fingerprint={fingerprint}` (PK/order = `merchant_id, legal_country_iso, site_order`; **no inter-country order encoded**).
* **Allocation (parameter-scoped):** `country_set(seed,parameter_hash)` (sole authority for cross-country order; `rank: 0=home, 1..K` foreigns), `ranking_residual_cache_1A(seed,parameter_hash)` (`residual ∈ [0,1)`, `residual_rank`).
* **RNG evidence (run-scoped):** `gumbel_key` (foreign selection ordering) and `sequence_finalize` (block coverage). Presence/shape were gated in S9.1/S9.3.

---

## 3) Formal statements (per merchant $m$)

Let:

* $\mathcal{I}_m={,i : (m,i)\in\texttt{country_set},}$ with total order by `rank` (0 = home). **Only** this dataset carries cross-country order.
* $n_{m,i}:=\#{\text{rows in egress with }(\texttt{merchant_id},\texttt{legal_country_iso})=(m,i)}$. If $n_{m,i}\ge1$ every row in the block echoes `final_country_outlet_count = n_{m,i}` (S9.3).
* $N^{\mathrm{raw}}_m$ = `raw_nb_outlet_draw` (merchant-constant; appears on each row of $m$).
* $R_{m,i}$ and $r_{m,i}$ from the residual cache.

### (A) Site-count realisation (definition equality)

$$
n_{m,i}=\big|\text{Rows}_{\text{egress}}(m,i)\big|
\quad \text{and} \quad
\{\texttt{site_order}\}=\{1,\dots,n_{m,i}\}.
$$

### (B) Country-set coverage & order (membership + rank continuity)

1. **Home uniqueness & coherence:** exactly one `country_set` row with `rank=0`; its `country_iso` equals the egress `home_country_iso` for merchant $m$.
2. **Foreign rank contiguity:** letting $K_m$ be the number of non-home rows, observed foreign ranks are **exactly** ${1,\dots,K_m}$ (no gaps/dupes).
3. **Membership:** for all egress rows $(m,i)$, $i\in\mathcal{I}*m$ (**egress ⊆ country_set**). Zero-blocks appear as **absence** of rows ($n*{m,i}=0$).

> **Note on `prior_weight`:** presence is required on foreign rows in `country_set`. Numeric equality to the renormalised candidate weights that seeded Gumbel is proven under S9.6 (numeric corridors), not here.

### (C) Allocation conservation (integerisation sums back to raw)

$$
\boxed{\ \sum_{i\in\mathcal{I}_m} n_{m,i} \;=\; N^{\mathrm{raw}}_m\ }\qquad\text{(exact integer equality).}
$$

### (D) Largest-remainder reproducibility (residuals & ranks)

Let $R_{m,i}\in[0,1)$ be the persisted fractional residuals and $r_{m,i}$ their deterministic rank (1 = largest). S9 must prove:

$$
\operatorname{argsort}_{i\in\mathcal{I}_m}\ (-R_{m,i},\ i_{\text{ISO asc}})\ \equiv\ \operatorname{order\ by}\ r_{m,i}.
$$

(Primary key: residual **descending**; tie-break: ISO **ascending**.)

### (E) Within-country sequencing & `sequence_finalize` coverage

For every non-empty block $(m,i)$:

1. **Encoder bijection on rows:** $\texttt{site_id}=\mathrm{zpad6}(\texttt{site_order})$.
2. **Event coverage:** there is **exactly one** `sequence_finalize` event for $(m,i)$ under $(seed,parameter_hash,run_id)$. For $n_{m,i}=0$ there must be **no** such event.

---

## 4) Gumbel-order provenance (when enabled)

Some releases require proving that foreign order (`rank=1..K_m`) equals **Top-K by `gumbel_key`** with ISO tie-break. S9.4 performs:

1. **Foreign candidate set:** $\mathcal{F}_m={,i\in\mathcal{I}_m:\ \text{rank}>0,}$.
2. **Evidence sequence:** sort the `gumbel_key` events for $m$ on $\mathcal{F}_m$ **by key desc, then ISO asc** to form $S_m$.
3. **Assertion:** for all $j\in{1..K_m}$, `country_set.rank=j` corresponds to the $j$-th element of $S_m$.

If $K_m=0$ (no foreigns), the required `gumbel_key` event count is **0** and this proof is vacuously true.

---

## 5) Algorithm (reference implementation)

```pseudo
function s9_4_cross_dataset(OUT, CST, RC, EVENTS):
  # EVENTS is a dict of label -> iterator; may contain "gumbel_key" and "sequence_finalize"

  # A) Egress tallies & merchant constants
  n := HashMap<(m,i) -> int>(0)
  merch_home := HashMap<m -> ISO2>()
  merch_raw  := HashMap<m -> int>()
  sid_errs := []
  for r in OUT:
      n[(r.merchant_id, r.legal_country_iso)] += 1
      merch_home[r.merchant_id] = r.home_country_iso
      merch_raw[r.merchant_id]  = r.raw_nb_outlet_draw
      if r.site_id != zpad6(r.site_order):
          sid_errs.append((r.merchant_id, r.legal_country_iso, r.site_order, r.site_id))
  if sid_errs: fail("s9.4.site_id_mismatch", dump=sid_errs)

  # B) Country-set structure & coverage against egress
  cset_by_m := group_rows(CST, key=merchant_id)
  home_diff := []; rank_gap := []; coverage_leaks := []
  for m, rows in cset_by_m:
      homes = [x for x in rows if x.rank==0]
      if len(homes) != 1 or merch_home.get(m) != homes[0].country_iso:
          home_diff.append(m)

      foreign = [x for x in rows if x.rank>0]
      K = len(foreign)
      franks = sorted([x.rank for x in foreign])
      if franks != list(range(1, K+1)): rank_gap.append(m)

      # egress ⊆ country_set
      for (m2,i2), cnt in n.items() where m2==m and cnt>0:
          if not any(x.country_iso==i2 for x in rows):
              coverage_leaks.append((m,i2))

  if home_diff:    fail("s9.4.country_set_home_mismatch", dump=home_diff)
  if rank_gap:     fail("s9.4.country_set_rank_contiguity", dump=rank_gap)
  if coverage_leaks: fail("s9.4.country_set_coverage", dump=coverage_leaks)

  # C) Conservation per merchant
  cons_diff := []
  for m, rows in cset_by_m:
      iso_list = [x.country_iso for x in rows]
      total = sum(n.get((m,i), 0) for i in iso_list)
      if total != merch_raw.get(m, 0):
          cons_diff.append((m, total, merch_raw.get(m, None)))
  if cons_diff: fail("s9.4.mass_not_conserved", dump=cons_diff)

  # D) Largest-remainder reproducibility
  rc_by_m := group_rows(RC, key=merchant_id)
  lr_diff := []
  for m, rows in rc_by_m:
      exp = sorted(rows, key=lambda r: (-r.residual, r.country_iso))
      if any(row.residual_rank != (idx+1) for idx,row in enumerate(exp)):
          lr_diff.append(m)
  if lr_diff: fail("s9.4.residual_rank_mismatch", dump=lr_diff)

  # E) sequence_finalize coverage: exactly one per non-empty (m,i)
  seq_counts := Counter<(m,i)>()
  for e in EVENTS.get("sequence_finalize", []):
      seq_counts[(e.merchant_id, e.country_iso)] += 1
  cov_err := []
  for (m,i), cnt in n.items():
      if cnt>0 and seq_counts.get((m,i),0) != 1: cov_err.append((m,i,"missing_or_multiple_seq_finalize"))
      if cnt==0 and seq_counts.get((m,i),0) != 0: cov_err.append((m,i,"seq_finalize_for_empty_block"))
  if cov_err: fail("s9.4.sequence_finalize_coverage", dump=cov_err)

  # F) Optional: Gumbel order provenance
  if "gumbel_key" in EVENTS:
      gk := {(e.merchant_id, e.country_iso): e.key for e in EVENTS["gumbel_key"]}
      order_err := []
      for m, rows in cset_by_m:
          foreign = [x for x in rows if x.rank>0]
          K = len(foreign)
          if K==0: continue
          S = sorted(foreign, key=lambda r: (-gk[(m,r.country_iso)], r.country_iso))
          if any(r.rank != (idx+1) for idx,r in enumerate(S)):
              order_err.append(m)
      if order_err: fail("s9.4.gumbel_order_mismatch", dump=order_err)

  return OK
```

---

## 6) Error taxonomy (machine codes; all hard-fail here)

| Code                                    | Meaning / Trigger                                                                   | Evidence artefact(s) written to bundle                                        |
| --------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `s9.4.site_id_mismatch`                 | Some row violates `site_id = zpad6(site_order)`                                     | `diffs/sequence.csv` (merchant,country,site_order,site_id)                  |
| `s9.4.country_set_home_mismatch`        | Egress `home_country_iso` ≠ `country_set.rank=0` (or multiple/no rank=0 rows)       | `diffs/coverage.csv` (merchant,egress_home,rank0_home)                      |
| `s9.4.country_set_rank_contiguity`      | Foreign ranks not exactly `1..K_m`                                                  | `diffs/coverage.csv` (merchant, observed_ranks)                              |
| `s9.4.country_set_coverage`             | Egress has $(m,i)$ not present in `country_set(m)`                                | `diffs/coverage.csv` (merchant,country)                                       |
| `s9.4.mass_not_conserved`               | $\sum_i n_{m,i} \ne N^{\mathrm{raw}}_m$                                        | `diffs/conservation.csv` (merchant, total_from_egress, raw_nb_draw)       |
| `s9.4.residual_rank_mismatch`           | Sorting residuals (desc, ISO asc) ≠ persisted `residual_rank`                       | `diffs/residual_rank_mismatch.csv` (merchant,country,residual,expected,found) |
| `s9.4.sequence_finalize_coverage`       | Missing/multiple `sequence_finalize` for non-empty block or present for empty block | `diffs/sequence_finalize_coverage.csv` (merchant,country,status)              |
| `s9.4.gumbel_order_mismatch` (optional) | `country_set.rank` order ≠ Top-K by `gumbel_key` evidence                           | `diffs/gumbel_order_mismatch.csv` (merchant,rank,iso,key,expected_order)     |

---

## 7) Artefacts written (bundle wiring)

S9.4 appends to the validation bundle (see S9.7 packaging, ZIP + `_passed.flag == SHA256(bundle.zip)`):

* `diffs/conservation.csv` — per merchant: `sum_n`, `raw_nb_draw`, `ok`.
* `diffs/coverage.csv` — home coherence, rank gaps, and egress⊆country_set leaks.
* `diffs/residual_rank_mismatch.csv` — residual/rank diffs.
* `diffs/sequence_finalize_coverage.csv` — event-coverage mismatches.
* `diffs/gumbel_order_mismatch.csv` — when Gumbel provenance is enabled.

---

## 8) Conformance tests (must-pass)

1. **Happy path:** `country_set = [GB(0), US(1), FR(2)]`; egress $n_{GB}=3, n_{US}=2, n_{FR}=0$; `raw_nb_outlet_draw=5`. Expect conservation 3+2+0=5; foreign ranks `{1,2}` contiguous; home coherence; egress⊆country_set; `site_id=zpad6(site_order)`; residual ranks match residual sort; `sequence_finalize` exactly once for GB and US, none for FR. ✔︎
2. **Coverage leak:** egress includes `DE` not in `country_set` → `s9.4.country_set_coverage`. ✔︎
3. **Home mismatch:** egress `home_country_iso=GB`, but `country_set.rank0=US` → `s9.4.country_set_home_mismatch`. ✔︎
4. **Rank gap:** foreign ranks `{1,3}` (missing `2`) → `s9.4.country_set_rank_contiguity`. ✔︎
5. **Conservation fail:** totals don’t match `raw_nb_outlet_draw` → `s9.4.mass_not_conserved`. ✔︎
6. **Residual rank drift:** persisted `residual_rank` disagrees with sort(−residual, ISO asc) → `s9.4.residual_rank_mismatch`. ✔︎
7. **Finalize coverage breach:** missing or duplicate `sequence_finalize` for a non-empty block → `s9.4.sequence_finalize_coverage`. ✔︎
8. **Gumbel provenance (enabled):** RNG shows `key(US)>key(FR)` but `country_set` has FR rank 1, US rank 2 → `s9.4.gumbel_order_mismatch`. ✔︎

---

## 9) Policy reminders binding to S9.4

* **Egress never encodes inter-country order**; all order comparisons reference `country_set.rank` (and, when required, `gumbel_key` evidence).
* **Exact equalities only** in S9.4; floating-point corridors (incl. `prior_weight` checks) live in S9.6.
* **Gate:** on any failure S9 still writes the bundle; `_passed.flag` is written **only** on success and must equal `SHA256(bundle.zip)`.

---

# S9.5 — RNG determinism & replay checks (implementation-ready, **budget-agnostic**)

## Scope (what S9.5 must prove)

For every RNG-touching step in 1A (NB mixture, ZTP diagnostics, Gumbel Top-K, Dirichlet, integerisation, sequence finalisation), the validator must **account for** and (where stable) **replay** exactly the random draws claimed, using only the audited RNG identity and each event’s **RNG envelope** (seed + 128-bit counters). Results must be **order-invariant** and reproducible under parallel execution.

> **Design choices locked in here**
>
> * We **do not hard-code sampler budgets** (e.g., “3 uniforms per gamma”). Draw consumption is proved by **trace vs event-envelope equality**.
> * **Hurdle policy:** exactly **one** `hurdle_bernoulli` event **per merchant**; if $\pi\in{0,1}$, the event is **deterministic** (`draws=0`, `u=null`, `deterministic=true`).
> * Degenerate cases are explicit: **$K=0$** (domestic-only) ⇒ **no** Dirichlet vector; **$M=0$** foreign candidates ⇒ **0** Gumbel events.

---

## Inputs & authorities

* **Audit log** (run-scoped): states RNG algorithm/seed and stream mapping; partition `{seed, parameter_hash, run_id}`.
* **Trace log** (run-scoped): one record per `(module, substream_label)` with **`draws`** consumed.
* **Structured RNG event streams** (label-scoped): `hurdle_bernoulli`, `gamma_component`, `poisson_component`, `nb_final`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`, `stream_jump` — each carries an **envelope** with 128-bit `before/after` counters.
* **Egress** `outlet_catalogue` (for seed/fingerprint echoes and block counts).
* **Country set** (for candidate cardinalities and $K_m$).

---

## S9.5.1 Envelope identity (run → egress)

Prove the egress partition came from the audited RNG for the active `{seed, parameter_hash, run_id}`:

1. `rng_audit_log.algorithm == "philox2x64-10"`.
2. For **all** egress rows in `(seed,fingerprint)`: `row.global_seed == rng_audit_log.seed`.
3. `rng_audit_log.{parameter_hash, manifest_fingerprint}` **equal** the partition tokens and per-row echoes.

**Any inequality ⇒ hard fail** (record and withhold `_passed.flag`).

---

## S9.5.2 128-bit counter arithmetic & per-label draw accounting

For each label $\ell$ (e.g., `gumbel_key`, `dirichlet_gamma_vector`, `gamma_component`, `poisson_component`, `residual_rank`, `sequence_finalize`, …):

1. **Stable order:** sort events by **`(before_hi,before_lo)` ascending** (use timestamp only for tie-break if needed).
2. For each event $e$, form 128-bit counters
   $C^\text{before}_e=(\texttt{before_hi}\ll64)+\texttt{before_lo}$ and
   $C^\text{after}_e=(\texttt{after_hi}\ll64)+\texttt{after_lo}$.
3. Define:

   * **Event-side draws:** $D_\text{events}(\ell)=\sum_{e\in T_\ell}\big(C^\text{after}_e-C^\text{before}_e\big)$
   * **Trace-side draws:** $D_\text{trace}(\ell)=\sum_{\text{trace rows for }\ell}\texttt{draws}$
   * **Jump stride:** $J(\ell)=\sum_{\texttt{stream_jump rows for }\ell}\texttt{jump_stride}$ (128-bit)
4. **Mandatory equalities (unsigned 128-bit):**

   * **Per-label:** $\boxed{,D_\text{events}(\ell) ;=; D_\text{trace}(\ell) ;+; J(\ell),}$
   * **Adjacency monotonicity:** for consecutive events $e_j,e_{j+1}$ in $T_\ell$:
     $C^\text{after}*{e_j}\le C^\text{before}*{e_{j+1}}$; equality **only** if the **intervening** events consume **0** draws.

Also assert **per-event** identity: `after == before + draws_e` where `draws_e = C_after − C_before`.

---

## S9.5.3 Event cardinalities (must match 1A logic; no budgets)

Compute **expected counts** from deterministic inputs, then compare to **observed** (events are scoped to `{seed, parameter_hash, run_id}`):

* **`hurdle_bernoulli`** — **exactly one** per merchant $m\in\mathcal{M}$. If $\pi_m\in{0,1}$ then the **event is deterministic** with `draws=0`, `u=null`, `deterministic=true`.
* **`gumbel_key`** — **one** per **foreign candidate**. If $K_m=0$ then **0** events for $m$.
* **`dirichlet_gamma_vector`** — **exactly one** per merchant **iff** $K_m \ge 1$ (vector length $K_m{+}1$); **none** if $K_m=0$. *(Normalisation checks move to S9.6.)*
* **Integerisation:** `residual_rank` — exactly **$|\mathcal{I}_m|$** per merchant; **non-consuming** (per-event `draws=0`).
* **NB composition:** per-attempt emit **one** `gamma_component` **and** **one** `poisson_component`; `nb_final` **exactly once** per merchant; attempts $\ge 1$. *(No uniform budgets asserted.)*
* **S8 attestation:** `sequence_finalize` — **exactly one** per $(m,i)$ with $n_{m,i}>0$; **non-consuming** (per-event `draws=0`). Global count equals $\sum_{m,i}\mathbf{1}[n_{m,i}>0]$.

---

## S9.5.4 Trace reconciliation (independent double-entry)

For every label $\ell$:

* **Equality:** $D_\text{trace}(\ell)=D_\text{events}(\ell)$ (when no jumps) or $D_\text{trace}(\ell)+J(\ell)=D_\text{events}(\ell)$ (with jumps).
* **Mismatch ⇒ `ERR_TRACE_EVENTS_DIVERGE[ℓ]`** (hard fail).
* **Non-consuming labels** (`residual_rank`, `sequence_finalize`) must have **per-event draws = 0**, hence contribute **0** to both sides.

---

## S9.5.5 Budget-**agnostic** spot checks (sanity without sampler assumptions)

These checks **only** use event payload structure and cross-dataset counts; they **never** assume a specific sampler’s uniform cost.

* **Hurdle:** `count(hurdle_bernoulli events) == |𝓜|`. Additionally, `sum(per-event draws) == count({m: 0<π_m<1})` (degenerate events must have `draws=0`).
* **NB attempts:** per merchant, `count(gamma_component) == count(poisson_component) >= 1` and `count(nb_final) == 1`.
* **Dirichlet shape:** for each merchant with $K_m\ge1`, arrays in `dirichlet_gamma_vector\` are **co-length $K_m+1$** and aligned by ISO order (not cross-country **rank**; the event carries its own list).
* **Gumbel:** `count(gumbel_key for m) == K_m`. *(We don’t assert “1 uniform per candidate”; the trace equality already proves draw consumption.)*

---

## S9.5.6 Replay spot-checks (payload re-derivation where stable)

To keep the replay stable across implementations, we only replay transforms with **sampler-independent contracts**:

1. **Gumbel keys (always).** From each event’s `rng_counter_before` and `seed`, regenerate $u\in(0,1)$ via the audited generator; compute
   $z=\log w - \log(-\log u)$ and compare to payload fields (`u`, `key`) **bit-for-bit**. On first mismatch, persist a **reproducer** `{seed, before_hi, before_lo, label, merchant_id, country_iso}`.

2. **Dirichlet vector (optional, only if sampler digest is declared).** If the audit or event payload declares a `gamma_sampler_digest`, regenerate $\Gamma(\alpha_i,1)$ from `rng_counter_before` and compare **`gamma_raw`** arrays bit-for-bit. Otherwise, **skip RNG replay** and perform **shape-only** checks here (normalisation & corridor checks live in S9.6).

*(No replay for NB gamma/poisson here; their budgets are sampler-dependent. Their draw usage is already proved by S9.5.2–S9.5.4.)*

---

## Error taxonomy (normative)

* `ERR_RNG_ALGO_MISMATCH` — audit.algorithm ≠ expected.
* `ERR_RNG_SEED_MISMATCH` — any egress row `global_seed` ≠ audit.seed, or audit lineage ≠ partition tokens.
* `ERR_COUNTER_ADVANCE_MISMATCH[ℓ]` — $\sum(\text{after−before}) \ne D_\text{trace}(\ell)+J(\ell)$ for label $\ell$.
* `ERR_ADJACENCY_BREAK[ℓ]` — per-label counter adjacency not monotone (or equal without zero-draw).
* `ERR_EVENT_CARDINALITY[ℓ]` — observed label counts differ from required counts (per S9.5.3).
* `ERR_TRACE_EVENTS_DIVERGE[ℓ]` — $D_\text{trace}(\ell) \ne D_\text{events}(\ell)$ (after jumps).
* `ERR_NONCONSUMING_HAS_DRAWS[ℓ]` — any `residual_rank`/`sequence_finalize` with `after>before`.
* `ERR_REPLAY_MISMATCH[ℓ]` — regenerated `u`/`key` (or `gamma_raw`, when replay is enabled) don’t match the payload.

All are **hard fails**; write evidence to the bundle and withhold `_passed.flag`.

---

## Validator outputs (machine-readable)

Write `rng_accounting.json` with, per label (and per merchant where relevant):
`{observed_events, expected_events, draws_trace, draws_events, jumps, counter_adjacency_ok, nonconsuming_ok, replay_sampled, replay_ok, ok, notes}`.
Include the **first reproducer** for any replay mismatch.

---

## Reference validator (language-agnostic pseudocode)

```pseudo
INPUT:
  audit  := rng_audit_log(seed, parameter_hash, run_id)
  trace  := rng_trace_log(seed, parameter_hash, run_id)
  events := dict(label -> iterator)
  egress := outlet_catalogue(seed, fingerprint)
  cset   := country_set(seed, parameter_hash)           # for K_m and foreign candidates

# 1) Envelope identity
assert audit.algorithm == "philox2x64-10"                                 # ERR_RNG_ALGO_MISMATCH
assert all(row.global_seed == audit.seed for row in egress)               # ERR_RNG_SEED_MISMATCH
assert audit.parameter_hash == parameter_hash and audit.manifest_fingerprint == fingerprint

# 2) Per-label accounting (sum of deltas == trace draws + jumps; adjacency monotone)
for ℓ in events.keys():
    T := sort_by_before_counter(events[ℓ])                                # (before_hi, before_lo) asc
    Δevents := sum( to_u128(e.after) - to_u128(e.before) for e in T )
    Dtrace  := sum(x.draws for x in trace where x.substream_label==ℓ)
    Jumps   := sum(j.jump_stride for j in events.get("stream_jump",[]) where j.label==ℓ)
    assert Δevents == Dtrace + Jumps                                      # ERR_COUNTER_ADVANCE_MISMATCH[ℓ]
    assert adjacency_monotone(T)                                          # ERR_ADJACENCY_BREAK[ℓ]
    if ℓ in {"residual_rank","sequence_finalize"}:
        assert all(to_u128(e.after) == to_u128(e.before) for e in T)      # ERR_NONCONSUMING_HAS_DRAWS[ℓ]

# 3) Event cardinalities (expected from cset & egress)
for m in merchants_in_run():
    Km := count_foreign_in_country_set(cset, m)
    assert count(events["gumbel_key"] where merchant==m) == Km            # ERR_EVENT_CARDINALITY[gumbel_key]
    if Km >= 1:
        assert exactly_one(events["dirichlet_gamma_vector"] where m)      # ERR_EVENT_CARDINALITY[dirichlet_gamma_vector]
    else:
        assert count(dirichlet_gamma_vector where m) == 0
    assert count(residual_rank where m) == size_of_country_set(cset,m)    # ERR_EVENT_CARDINALITY[residual_rank]
    # Hurdle: exactly one per merchant; degenerate π ⇒ draws=0
    assert exactly_one(events["hurdle_bernoulli"] where m)                # ERR_EVENT_CARDINALITY[hurdle_bernoulli]
    if pi_is_degenerate(m): assert draws_of(hurdle_bernoulli[m]) == 0

# NB composition (per merchant)
for m in merchants_with_nb():
    gc := count(gamma_component where m)
    pc := count(poisson_component where m)
    nf := count(nb_final where m)
    assert gc == pc and gc >= 1 and nf == 1                               # ERR_EVENT_CARDINALITY[nb_*]

# 4) Trace reconciliation already implied by §2; re-write summary to rng_accounting.json

# 5) Replay spot-checks (deterministic sample)
for (m,i) in deterministic_sample(seed, fingerprint, events["gumbel_key"]):
    e := event_for(m,i)
    u := philox_uniform_u64_to_(0,1)(audit.seed, e.before_counter)
    key_hat := log(weight(m,i)) - log(-log(u))
    assert bit_equal(key_hat, e.key) and bit_equal(u, e.u)                # ERR_REPLAY_MISMATCH[gumbel_key]

if sampler_digest_available("gamma"):
    for m in deterministic_sample_merchants(seed, fingerprint):
        e := dirichlet_event_for(m)
        gamma_hat := regenerate_gamma_vector(e.before_counter, e.alpha, sampler_digest)
        assert arrays_bit_equal(gamma_hat, e.gamma_raw)                    # ERR_REPLAY_MISMATCH[dirichlet_gamma_vector]
```

---

## Conformance tests (negative/edge)

1. **Order-invariance:** shuffle processing order across executors → counters/draws reconciliation still passes. ✔︎
2. **Non-consuming guard:** flip one `sequence_finalize` event to have `after>before` → `ERR_NONCONSUMING_HAS_DRAWS[sequence_finalize]`. ✔︎
3. **Trace tamper:** alter `rng_trace_log.draws` for `gumbel_key` by +1 → `ERR_TRACE_EVENTS_DIVERGE[gumbel_key]`. ✔︎
4. **Dirichlet degenerate:** merchant with $K_m=0$ still emits a vector → `ERR_EVENT_CARDINALITY[dirichlet_gamma_vector]`. ✔︎
5. **Gumbel coverage:** remove one foreign candidate’s event → `ERR_EVENT_CARDINALITY[gumbel_key]`. ✔︎
6. **Hurdle determinism:** merchant with $\pi=1$ has hurdle event with `draws>0` → `ERR_NONCONSUMING_HAS_DRAWS[hurdle_bernoulli]`. ✔︎
7. **NB pairing:** `gamma_component` count ≠ `poisson_component` count → `ERR_EVENT_CARDINALITY[nb_*]`. ✔︎

---

This version of **S9.5** applies your design goals precisely: **sealed determinism without sampler lock-in**, explicit degenerate branches, strict per-label counter math, hard cardinalities, and **stable** replay (Gumbel always; Dirichlet only when a sampler digest is declared).

---

# S9.6 — Statistical corridors (implementation-ready, **tolerances governed**)

This section defines the **release-time sanity tests** that must hold (as *hard gates*) before `_passed.flag` can be written. All corridor metrics are **derived deterministically** from egress, allocation caches, and RNG evidence locked earlier; results are recorded to `metrics.csv` inside the validation bundle, and any breach produces a **hard fail** (bundle written; flag withheld).

---

## 1) Inputs, scope, determinism

**Authoritative inputs (read-only):**

* `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}`: immutable egress (per-row: `H_m = single_vs_multi_flag`, `N^{raw}_m = raw_nb_outlet_draw`, block counts `n_{m,i}`). Inter-country order is **not** encoded here.
* `country_set/seed={seed}/parameter_hash={parameter_hash}`: **sole** carrier of cross-country order (`rank`: 0=home; 1..K foreign). Also provides `prior_weight` if present.
* `ranking_residual_cache_1A(seed,parameter_hash)`: persistent residuals (used only where residuals appear in definitions).
* RNG event streams (run-scoped): especially `dirichlet_gamma_vector` (to rebuild $q_{m,i}$) and ZTP/NB signals (`poisson_component(context="ztp")`, `ztp_rejection`, `ztp_retry_exhausted`, `nb_final`).
* Optional cache: `hurdle_pi_probs(parameter_hash)` for model-implied $\pi_m$. If absent, **skip** the hurdle corridor and record “not evaluated”.

**Tolerances & bands (governed):** read **only** from `numeric_tolerances.yaml` (or equivalent governed config) and **echo** values into `metrics.csv`:

* `eps_pi`, `eps_LRR`, `eps_rho`, `ztp_rate_band = [a_L, a_U]`
* `eps_sum1` (sum-to-one guard), `eps_prior` (prior-weight coherence)

**Numeric policy:** IEEE-754 binary64; all sums use **Neumaier compensation**. Apply **no** quantisation except where explicitly stated. (If residuals are used, employ the shared `Q_8` operator as defined earlier.)

**Outputs:** `metrics.csv` inside `validation_bundle_1A(fingerprint)`; bundle and `_passed.flag` contract as in S9.7. **Any corridor breach** ⇒ gate fails; bundle still materialises.

---

## 2) Corridor catalogue (definitions, math, thresholds, gating)

### 2.1 Hurdle calibration (multi-site prevalence) — *optional if cache present*

**Empirical rate:** $\displaystyle \widehat{\pi}=\frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}}H_m$, where $H_m\in{0,1}$ from egress.
**Model average:** $\displaystyle \bar{\pi}=\frac{1}{|\mathcal{M}|}\sum_{m}\pi_m$ from `hurdle_pi_probs`.
**Gate:** $|\widehat{\pi}-\bar{\pi}|\le \texttt{eps_pi}\`.
**Record-only:** Wilson 95% CI for $\widehat{\pi}$ and z-gap.

### 2.2 Integerisation fidelity (largest-remainder L1 guard)

**Goal.** Although mass conservation is exact (S9.4), we guard that realised shares align with pre-integer shares.

* **Rebuild pre-integer shares:** from `dirichlet_gamma_vector` events (S9.4 rules), obtain binary64 weights $w_{m,i}$ and set $q_{m,i}!=!w_{m,i}$ (post-normalisation).
* **Realised shares:** $n_{m,i}/N^{raw}_m$ from egress.
* **Per-merchant L1 gap:** $\displaystyle \Delta_m=\sum_{i\in\mathcal{I}*m}\left|,\frac{n*{m,i}}{N^{raw}*m}-q*{m,i}\right|$.
  **Gate:** $\max_m \Delta_m \le \texttt{eps_LRR}\`. Also record p50/p99 of $\Delta_m$.

### 2.3 Sparsity behaviour (currency-level)

**Observed rate:** $\widehat{\rho}=\frac{1}{|\mathcal{K}|}\sum_{\kappa\in\mathcal{K}}\mathbf{1}[\texttt{sparse_flag}(\kappa)=1]$.
**Expected rate:** $\rho_{\text{expected}}$ from governed config.
**Gate:** $|\widehat{\rho}-\rho_{\text{expected}}|\le \texttt{eps_rho}\`.

### 2.4 ZTP acceptance corridor (foreign-count draw $K$)

Let $T=$ total `poisson_component(context="ztp")` attempts and $A=$ number of **accepted** draws (from ZTP accept signals / `nb_final` where appropriate). Define $\widehat{a}=A/T$ (guard $T>0$).

**Gate:** $\widehat{a}\in[\texttt{a_L},\texttt{a_U}]\`.
**Record-only:** if model inputs expose $\lambda_m$, report $\bar a=\text{mean}_m(1-e^{-\lambda_m})$ and $\widehat{a}-\bar a$.

### 2.5 Prior-weight coherence (parameter vs realised mechanisms)

When available, we verify two numeric coherences:

**(a) Dirichlet α normalisation & mean vs prior**
For merchants with a `dirichlet_gamma_vector` event: let $\alpha_{m,i}>0$ be the event’s `alpha` array; define $p^\alpha_{m,i}=\alpha_{m,i}/\sum_j\alpha_{m,j}$.
**Gates:**

* **Sum-to-one:** $\left|\sum_i p^\alpha_{m,i}-1\right|\le\texttt{eps_sum1}$ (per merchant).
* **Prior match (if `country_set.prior_weight` present):** $|p^\alpha_{m,i}-\texttt{prior_weight}_{m,i}|\le\texttt{eps_prior}$ for all $i$.

**(b) Dirichlet weights normalisation**
For all merchants with a Dirichlet event: with reconstructed $w_{m,i}$, require $\left|\sum_i w_{m,i}-1\right|\le\texttt{eps_sum1}$ and $w_{m,i}\ge -\texttt{eps_sum1}$ (non-negativity within numeric noise). *(These complement schema checks and make the corridor explicit.)*

> If $K_m=0$ (no foreigns), both 2.5(a) and 2.5(b) are **skipped** and logged as unevaluated.

---

## 3) Algorithms (reference, deterministic & streaming)

```pseudo
function s9_6_corridors(OUT, CST, DIRICHLET_EVENTS, HURDLE_PI_PROBS?, ZTP_EVENTS, TOLS):
    # TOLS is read from numeric_tolerances.yaml:
    #   {eps_pi, eps_LRR, eps_rho, a_L, a_U, eps_sum1, eps_prior, rho_expected}
    # --- Precompute basic tallies ---
    M := distinct merchants in OUT
    H[m]    := merchant-constant single_vs_multi_flag from OUT
    Nraw[m] := merchant-constant raw_nb_outlet_draw   from OUT
    I_m     := { ordered list of i from CST where merchant_id=m }           # rank-ordered (0..K)
    n[(m,i)]:= number of OUT rows with (merchant_id=m, legal_country_iso=i)

    # --- (1) Hurdle calibration ---
    if HURDLE_PI_PROBS? present:
        pi_bar := mean_over_m( HURDLE_PI_PROBS[m] )
        pi_hat := mean_over_m( H[m] )
        gap_pi := abs(pi_hat - pi_bar)
        wilson_center, wilson_half := wilson_interval(pi_hat, |M|, z=1.96)
        gate_hurdle := (gap_pi <= TOLS.eps_pi)
        emit_metric("hurdle_pi_hat", pi_hat, TOLS.eps_pi, "record+gate", 1)
        emit_metric("hurdle_pi_bar", pi_bar, "", "record-only", 1)
        emit_metric("hurdle_gap", gap_pi, TOLS.eps_pi, gate_hurdle?"pass":"fail", 1)
        emit_metric("hurdle_wilson_center", wilson_center, "", "record-only", 1)
        emit_metric("hurdle_wilson_halfwidth", wilson_half, "", "record-only", 1)
    else:
        gate_hurdle := true
        emit_metric("hurdle_evaluated", 0, "", "skipped", 0)

    # --- (2) Integerisation fidelity L1 ---
    W := reconstruct_dirichlet_weights(DIRICHLET_EVENTS)     # (m,i) -> w_{m,i}; Σ_i w=1 per m (up to eps_sum1)
    Δ := []
    for m in M:
        denom := R64(Nraw[m])
        acc := 0.0 ; comp := 0.0
        for i in I_m:
            share_real  := R64(n[(m,i)]) / denom
            share_model := W.get((m,i), 0.0)                 # domestic present even if K=0
            term := abs(share_real - share_model)
            t := acc + term
            comp += (abs(acc) >= abs(term)) ? (acc - t + term) : (term - t + acc)
            acc = t
        Δ_m := acc + comp
        Δ.append(Δ_m)
    Δ_max := max(Δ) ; Δ_p50 := percentile(Δ, 50) ; Δ_p99 := percentile(Δ, 99)
    gate_lrr := (Δ_max <= TOLS.eps_LRR)
    emit_metric("lrr_L1_max", Δ_max, TOLS.eps_LRR, gate_lrr?"pass":"fail", 1)
    emit_metric("lrr_L1_p50", Δ_p50, "", "record-only", 1)
    emit_metric("lrr_L1_p99", Δ_p99, "", "record-only", 1)

    # --- (3) Sparsity behaviour ---
    rho_hat := mean_over_currencies( sparse_flag[kappa] )    # from governed domain or run’s candidate set
    gap_rho := abs(rho_hat - TOLS.rho_expected)
    gate_rho := (gap_rho <= TOLS.eps_rho)
    emit_metric("sparse_rate_hat", rho_hat, TOLS.eps_rho, gate_rho?"pass":"fail", 1)
    emit_metric("sparse_rate_expected", TOLS.rho_expected, "", "record-only", 1)
    emit_metric("sparse_rate_gap", gap_rho, TOLS.eps_rho, gate_rho?"pass":"fail", 1)

    # --- (4) ZTP acceptance ---
    T := count(ZTP_EVENTS where label="poisson_component" and context="ztp")
    A := count_acceptances_from_ztp(ZTP_EVENTS)              # successes with K>=1
    a_hat := (T == 0) ? 1.0 : R64(A) / R64(T)                # guard
    gate_ztp := (TOLS.a_L <= a_hat and a_hat <= TOLS.a_U)
    emit_metric("ztp_attempts", T, "", "record-only", 1)
    emit_metric("ztp_acceptances", A, "", "record-only", 1)
    emit_metric("ztp_rate_hat", a_hat, f"[{TOLS.a_L},{TOLS.a_U}]", gate_ztp?"pass":"fail", 1)

    # --- (5) Prior-weight coherence (if applicable) ---
    # (a) α-means vs prior_weight
    gate_prior := true
    for each merchant m with dirichlet event e:
        α := e.alpha  # array aligned to e.country_isos
        Sα := compensated_sum(α)
        pα := [α_j / Sα for α_j in α]
        sum_err := abs(compensated_sum(pα) - 1.0)
        if sum_err > TOLS.eps_sum1: gate_prior = false; emit_metric("alpha_sum1_err", sum_err, TOLS.eps_sum1, "fail", 1)
        for each iso in e.country_isos where prior_weight available:
            pw := prior_weight[m, iso]
            gap := abs(pα[idx(iso)] - pw)
            if gap > TOLS.eps_prior: gate_prior = false
            emit_metric("prior_gap", gap, TOLS.eps_prior, (gap<=TOLS.eps_prior)?"pass":"fail", 1)

    # (b) Dirichlet weights sum-to-one & non-negativity
    gate_wsum := true
    for m in merchants_present_in(W):
        wvals := [W[(m,i)] for i in I_m if (m,i) in W]
        sum_w := compensated_sum(wvals)
        min_w := min(wvals) if wvals else 0.0
        err := abs(sum_w - 1.0)
        emit_metric("dirichlet_sum1_err", err, TOLS.eps_sum1, (err<=TOLS.eps_sum1)?"pass":"fail", 1)
        if err > TOLS.eps_sum1 or min_w < -TOLS.eps_sum1: gate_wsum = false

    # --- (6) Decide & emit ---
    corridors_pass := gate_hurdle and gate_lrr and gate_rho and gate_ztp and gate_prior and gate_wsum
    write_metrics_csv()  # deterministic column/row order
    return corridors_pass
```

> `reconstruct_dirichlet_weights` must **exactly** follow S9.4/S9.5 replay rules (using event envelopes only, no extra randomness).
> `count_acceptances_from_ztp` reads ZTP/NB events per S9.5 cardinalities (accept if a success indicator is present for $K\ge1$).
> All thresholds are read from **`numeric_tolerances.yaml`** and **echoed** into `metrics.csv` (see §4).

---

## 4) `metrics.csv` schema (bundle content)

Flat CSV, deterministic column order:

| column      | type          | meaning                                                                                             |
| ----------- | ------------- | --------------------------------------------------------------------------------------------------- |
| `metric`    | string        | identifier (e.g., `hurdle_pi_hat`, `lrr_L1_max`, `prior_gap`, `dirichlet_sum1_err`, `ztp_rate_hat`) |
| `value`     | number        | measured value (binary64)                                                                           |
| `threshold` | number/string | configured gate value or band (e.g., `eps_LRR`, or `"[a_L,a_U]"`)                                   |
| `notes`     | string        | short status (`pass`/`fail`/`record-only`/`skipped`) and any extra details                          |
| `evaluated` | {0,1}         | 1 if evaluated; 0 if skipped by policy (e.g., missing `hurdle_pi_probs` or `K_m=0`)                 |

The bundle index must include this artefact; the bundle remains **sealed**: `_passed.flag` content equals `SHA256(bundle.zip)`.

---

## 5) Error taxonomy (machine codes; hard-fail)

* `corridor_breach_hurdle_gap` — $|\widehat{\pi}-\bar{\pi}|>\texttt{eps_pi}$ (only if hurdle evaluated).
* `corridor_breach_lrr_L1` — $\max_m \Delta_m>\texttt{eps_LRR}$.
* `corridor_breach_sparse_rate` — $|\widehat{\rho}-\rho_{\text{expected}}|>\texttt{eps_rho}$.
* `corridor_breach_ztp_rate` — $\widehat{a}\notin[\texttt{a_L},\texttt{a_U}]$.
* `corridor_breach_alpha_sum1` — $\big|\sum_i p^\alpha_{m,i}-1\big|>\texttt{eps_sum1}$ for any merchant with Dirichlet event.
* `corridor_breach_prior_weight` — any $|p^\alpha_{m,i}-\texttt{prior_weight}_{m,i}|>\texttt{eps_prior}`where`prior_weight\` is present.
* `corridor_breach_dirichlet_sum1` — $\big|\sum_i w_{m,i}-1\big|>\texttt{eps_sum1}$ or $\min_i w_{m,i}<-\texttt{eps_sum1}$.

On any breach, `corridors_pass=false`; the bundle is written, `_passed.flag` is **not**.

---

## 6) Conformance tests (must pass)

1. **Happy path:** `hurdle_pi_probs` present; $|\widehat{\pi}-\bar{\pi}|=0.005\le\texttt{eps_pi}$; $\max\Delta_m=7\cdot10^{-14}\le\texttt{eps_LRR}$; $|\widehat{\rho}-\rho_{\text{expected}}|=0.001\le\texttt{eps_rho}$; $\widehat{a}\in[\texttt{a_L},\texttt{a_U}]$; Dirichlet α and $w$ sum-to-one within `eps_sum1`; `prior_weight` diffs $\le\texttt{eps_prior}\` → **pass**, bundle sealed. ✔︎
2. **Hurdle skipped:** remove `hurdle_pi_probs` → metrics show `evaluated=0` for hurdle; other corridors pass → **pass**. ✔︎
3. **LRR breach (numerical):** perturb a Dirichlet weight by $5!\times!10^{-12}$, yielding $\max\Delta_m=2!\times!10^{-12}>\texttt{eps_LRR}$ → `corridor_breach_lrr_L1`. ✔︎
4. **Sparse drift:** flip half the currencies’ flags with $\rho_{\text{expected}}=0.2$ → `corridor_breach_sparse_rate`. ✔︎
5. **ZTP out of band:** force $\widehat{a}=0.1$ while band is $[0.3,0.7]$ → `corridor_breach_ztp_rate`. ✔︎
6. **Prior mismatch:** set `prior_weight` off by $2!\times!10^{-10}$ with `eps_prior=1e-12` → `corridor_breach_prior_weight`. ✔︎
7. **Dirichlet sum error:** make $\sum_i w_{m,i}=0.999999999$ with `eps_sum1=1e-12` → `corridor_breach_dirichlet_sum1`. ✔︎

---

## 7) Operational notes

* **Do not hard-code thresholds**; read from governed `numeric_tolerances.yaml` and **echo** into `metrics.csv`.
* **No extra randomness** is consumed; reconstruction uses the validated event envelopes from S9.5.
* **Immutability & gate:** corridors are part of the **same** bundle+flag contract — 1B must still verify `_passed.flag == SHA256(bundle.zip)` before reading egress.

---

This pins **S9.6** at “100%”: corridor definitions & math, degenerate/skip rules, deterministic algorithms with numeric policy, CSV schema & bundle wiring, expanded error taxonomy (incl. **prior-weight coherence** and **sum-to-one** guards), conformance tests, and gating semantics tied to the central tolerances file and S9.7 sealing rules.

---

# S9.7 — Bundle & Signing (implementation-ready)

## 1) Purpose & contract (what S9.7 certifies)

After **S9.2→S9.6 all pass**, S9.7 emits a **single audit artefact** — a **ZIP bundle** — and a **flag file** that together authorise 1B to read 1A egress for **this exact** fingerprint:

```
data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
  ├─ bundle.zip
  └─ _passed.flag   # ASCII: SHA256(bundle.zip)
```

**Index contract.** `bundle.zip/index.json` MUST conform to the registry-resolved schema for the validation bundle index (the registry/dictionary provides the exact pointer; in schemas it’s the `validation_bundle` index table). **Do not hardcode** the pointer; resolve via the artefact registry.

**Minimum payloads inside the ZIP (same folder as `index.json`):**

* `schema_checks.json`
* `key_constraints.json`
* `rng_accounting.json`
* `metrics.csv`
* `diffs/*` (zero or more CSVs written by S9.3–S9.6)

**Gate.** Compute `H = SHA256(bundle.zip bytes)` and write `_passed.flag` whose **contents** are exactly the 64-char lowercase hex `H`. 1B **must** recompute and compare before reading egress.

The artefact registry encodes: paths, ownership, immutability, and the policy **“verify `_passed.flag` equals SHA256(bundle.zip) before reading egress”**.

---

## 2) Bundle index (inside the ZIP)

A **table** with PK `artifact_id`. Columns are fixed to avoid ambiguity:

* `artifact_id` (PK, string, unique)
* `kind ∈ {"plot","table","diff","text","summary"}`
* `path` (UTF-8, **relative path** within the ZIP, POSIX separators `/`)
* `mime` (media type, e.g. `application/json`, `text/csv`) — optional if schema allows
* `notes` (free text) — optional

**Normative examples (rows):**

```
("schema_checks","table","schema_checks.json","application/json","JSON-Schema results")
("key_constraints","table","key_constraints.json","application/json",null)
("rng_accounting","table","rng_accounting.json","application/json",null)
("corridor_metrics","table","metrics.csv","text/csv","Release gates & thresholds echoed")
("residual_diffs","diff","diffs/residual_rank_mismatch.csv","text/csv","Exact mismatches")
```

> If the schema supports per-file digests, include `sha256` per row; otherwise you may echo the global digest in `notes`.

**Validation rule.** Build `index.json`, then validate it against the registry-resolved `validation_bundle` index schema **before** zipping.

---

## 3) Canonical packaging (byte-stable ZIP)

To guarantee re-runs on the same inputs yield **identical bytes** (stable `H`):

1. **Materialise payloads** first (`schema_checks.json`, `key_constraints.json`, `rng_accounting.json`, `metrics.csv`, `diffs/*`). These are immutable byte inputs to the ZIP step.

2. **Canonical `index.json`**:

   * UTF-8, LF newlines, **no BOM**.
   * Canonical JSON (object keys sorted, stable number/string emission).

3. **ZIP determinism rules**:

   * File names UTF-8; **paths sorted lexicographically by `path`**.
   * Compression: **DEFLATE** at a **fixed governed level** (e.g., `6`); do not vary by host.
   * **Timestamps**: set per-entry mtime to a **fixed epoch** (e.g., `1980-01-01T00:00:00Z`) if the library supports it; otherwise normalise to zero.
   * Disable variable extra fields; prefer no ZIP64 unless required by size.
   * **Relative paths only**; must match `index.json.path` exactly.

4. **Compute digest & sign**:

   * Let `B` = exact ZIP bytes.
   * `H = SHA256(B)` as 64-char lowercase hex.
   * Write the ZIP, then atomically write `_passed.flag` with **ASCII text** `H`.

5. **Immutability & idempotency**:

   * The `validation/fingerprint={F}/` prefix is **append-only**.
   * If `bundle.zip` exists, recompute `H'`; if bytes differ, **refuse to overwrite** (raise `s9.7.zip_noncanonical_or_conflict`); if identical, it’s idempotent (leave flag as-is).
   * **Never** write `_passed.flag` unless **all** S9 gates are true.

**Atomic writes.** Write to `*.tmp` and **fsync + rename** for both `bundle.zip` and `_passed.flag` to prevent torn reads.

---

## 4) Reference pack-and-sign algorithm

```pseudo
INPUT:
  lineage := (seed, parameter_hash, manifest_fingerprint, run_id)
  s9_status := {s9_2_ok, s9_3_ok, s9_4_ok, s9_5_ok, s9_6_ok}
  payloads := {
     "schema_checks.json",
     "key_constraints.json",
     "rng_accounting.json",
     "metrics.csv",
     "diffs/*"  # zero or more CSVs
  }
  registry := artefact dictionary (resolves schema pointers & target paths)
  ZIP_LEVEL := governed compression level (e.g., 6)

# 0) Require upstream pass
assert all(s9_status.values)    # else we'll still make a diagnostics bundle, but no flag

# 1) Assemble index rows (relative paths)
rows := [
  ("schema_checks","table","schema_checks.json","application/json",null),
  ("key_constraints","table","key_constraints.json","application/json",null),
  ("rng_accounting","table","rng_accounting.json","application/json",null),
  ("corridor_metrics","table","metrics.csv","text/csv",null)
]
for f in list_files("diffs/"):
  rows.append(("diff_"+basename_no_ext(f),"diff","diffs/"+basename(f),"text/csv",null))

index := to_table(rows, pk="artifact_id")

# 2) Validate index using registry-resolved schema pointer
ptr := registry.schema_ptr("validation_bundle_index")   # do not hardcode
assert jsonschema_validate(index, ptr)

# 3) Canonicalise index.json (UTF-8, LF, sorted keys); write to temp
write_canonical_json("index.json.tmp", index)

# 4) Build canonical ZIP (sorted paths, fixed timestamps & compression)
paths := sort(["index.json"] + [r.path for r in rows])
move("index.json.tmp","index.json")
B := zip_bytes(paths,
               compression="deflate", level=ZIP_LEVEL,
               fixed_epoch="1980-01-01T00:00:00Z",
               sort_names=true, utf8_filenames=true)

# 5) Compute digest, write artefacts atomically
H := sha256_hex(B)      # 64-char lowercase hex
write_atomic(".../validation/fingerprint={F}/bundle.zip.tmp", B)
rename_atomic(".../validation/fingerprint={F}/bundle.zip.tmp",
              ".../validation/fingerprint={F}/bundle.zip")

if all(s9_status.values):
   write_atomic_text(".../validation/fingerprint={F}/_passed.flag.tmp", H)
   rename_atomic(".../validation/fingerprint={F}/_passed.flag.tmp",
                 ".../validation/fingerprint={F}/_passed.flag")

# 6) Post-write verify (defensive)
B2 := read_bytes(".../validation/fingerprint={F}/bundle.zip")
assert sha256_hex(B2) == H
```

---

## 5) Failure semantics (when **no flag** is written)

**Hard fail ⇒ withhold `_passed.flag`:**

* Any S9.3 schema/PK/FK/block invariant breach.
* Any S9.4 cross-dataset equality failure (conservation, coverage, home mismatch, residual-rank mismatch, optional Gumbel-order mismatch).
* Any S9.5 RNG lineage, counter, trace/event reconciliation, or replay failure.
* Any S9.6 corridor breach.

In all cases, **still** write `bundle.zip` (diagnostics) but **do not** write `_passed.flag`.

---

## 6) What exactly goes into the bundle (minimum viable set)

* `index.json` — authoritative artefact map (this section’s schema).
* `schema_checks.json` — per-dataset JSON-Schema results (paths & pointers included).
* `key_constraints.json` — PK/UK/FK proofs and duplicates.
* `rng_accounting.json` — per-label draws, counter deltas, jumps, trace reconciliation, and replay spot-checks (with first failing `{seed,counter,label,...}`).
* `metrics.csv` — S9.6 corridor metrics and thresholds (echoed).
* `diffs/*.csv` — reproducible mismatches (`conservation.csv`, `coverage.csv`, `residual_rank_mismatch.csv`, `sequence_finalize_coverage.csv`, etc.).

---

## 7) Hand-off to 1B (defence-in-depth preflight)

Before reading egress `(seed, fingerprint)`, 1B **must**:

1. **Lineage echo (cheap sanity):**

```pseudo
r := read_one_row("outlet_catalogue", seed, fingerprint)
assert r.manifest_fingerprint == fingerprint
```

2. **Validation proof:**

```pseudo
B  := read_bytes("validation/fingerprint={F}/bundle.zip")
H' := sha256_hex(B)
Hf := read_text("validation/fingerprint={F}/_passed.flag").strip()
assert H' == Hf
```

3. **Order policy reminder:** egress **does not** encode cross-country order; 1B must join `country_set(seed, parameter_hash).rank`.

---

## 8) Error taxonomy (S9.7-specific)

* `s9.7.index_schema_violation` — `index.json` fails the bundle index schema.
* `s9.7.bundle_write_error` — I/O error writing the ZIP.
* `s9.7.flag_write_on_fail` — attempt to create `_passed.flag` despite upstream failure (guard).
* `s9.7.zip_noncanonical_or_conflict` — an existing bundle differs bytewise for the same fingerprint.
* `s9.7.sha_mismatch_postwrite` — post-write SHA differs from computed `H` (abort; leave no flag).
* `s9.7.consumer_flag_mismatch` — 1B finds `SHA256(bundle) ≠ contents(_passed.flag)`; consumption must abort.

All are **hard-fail**; record in logs/registry notes; **never** emit a flag on producer-side failure.

---

## 9) Conformance tests (must pass)

1. **Happy path determinism.** Re-run S9 with identical inputs on different hosts: byte-identical `bundle.zip` (same `H`), `_passed.flag` contains exactly `H`, 1B preflight succeeds. ✔︎
2. **Bundle-only on breach.** Induce a corridor breach (S9.6): `bundle.zip` exists with metrics/diffs, `_passed.flag` absent; 1B preflight fails at step 2. ✔︎
3. **Index schema guard.** Break `index.json` (e.g., wrong `kind`); get `s9.7.index_schema_violation`; no flag written. ✔︎
4. **Atomicity.** Kill process mid-write: only `*.tmp` present; no partial `bundle.zip` or flag; next run succeeds. ✔︎
5. **Consumer defence.** Corrupt `_passed.flag` by one nibble: 1B preflight hash mismatch; refuses to read egress. ✔︎

---

## 10) Operational notes

* **Resolve pointers from the registry**, not constants (paths, schema refs, partition templates).
* **Canonical JSON & ZIP** are essential for reproducibility; enforce at build time.
* **Immutability model:** for a fingerprint `{F}`, valid states are (a) **bundle+flag** (authorised) or (b) **bundle-only** (blocked). No third state.
* **Provenance.** Include the lineage `(seed, parameter_hash, manifest_fingerprint, run_id)` and validator commit in `index.json.notes` or a `README.txt` inside the ZIP.
* **Dependency wiring in the registry:** declare `validation_passed_flag.digest = SHA256(bundle.zip)` and `validation_passed_flag ← validation_bundle_1A`.

---

This locks **S9.7**: exact index & contents, byte-stable packaging, SHA-256 signing, atomic write & immutability rules, consumer preflight, error taxonomy, and conformance tests — all aligned with the earlier S9 guarantees and the artefact registry/data dictionary.

---

# S9.8 — Failure semantics (implementation-ready)

This section locks the **decision logic**, **severity classes**, **machine codes**, **evidence map**, **write rules**, and **idempotence/concurrency** for S9. It is the **only** authority on when `_passed.flag` is written or withheld and how 1B must interpret outcomes. All rules bind to the S9.1–S9.7 contracts and your registry/dictionary.

---

## 1) Scope & contract (what S9.8 governs)

**Inputs:** pass/fail booleans and artefacts from:

* **S9.3** structural validations,
* **S9.4** cross-dataset equalities,
* **S9.5** RNG lineage, accounting & replay,
* **S9.6** statistical corridors,
* plus the **S9.7** pack-and-sign step.

**Outputs (mutually exclusive end states per `fingerprint`):**

* **PASS:** `bundle.zip` **and** `_passed.flag` whose **ASCII contents equal `SHA256(bundle.zip)`**.
* **FAIL:** `bundle.zip` only (full diagnostics); **no** `_passed.flag`.

**Hard-fail authority:** *Any* schema/keys/FK violation, RNG lineage/replay mismatch, cross-dataset equality failure, or corridor breach is a **hard fail**. Diagnostics still materialise in the bundle; the flag is withheld. Record-only numerics (Wilson CI, z-scores, etc.) never gate release.

---

## 2) Severity classes (closed set)

### A) **Hard fail** (release blocked; no hand-off)

Triggers (any one suffices):

1. **Structural / schema:** JSON-Schema breach in `outlet_catalogue`, `country_set`, or `ranking_residual_cache_1A`; partition echo mismatch; PK/UK duplicates; ISO FK breach.
   *Evidence:* `schema_checks.json`, `key_constraints.json`.
2. **RNG lineage / replay:** audit algo/seed mismatch; missing required label streams; counter advance ≠ declared draws (+ jumps); replay mismatch for `gumbel_key` / `dirichlet_gamma_vector`.
   *Evidence:* `rng_accounting.json`.
3. **Cross-dataset equalities:** mass not conserved; egress outside `country_set`; home mismatch; rank gaps; `site_id ≠ zpad6(site_order)`; missing or extra `sequence_finalize`.
   *Evidence:* `diffs/*`.
4. **Corridors:** any corridor outside configured bounds (hurdle gap; LRR L1 guard; sparsity gap; ZTP acceptance).
   *Evidence:* `metrics.csv`.

**Outcome:** write **bundle only**; **do not** write `_passed.flag`.

### B) **Soft warn** (record-only)

Non-structural numerical observations that **do not** contradict exact contracts. These appear in `metrics.csv` (and optionally `decision_summary.json`) and **do not** block the flag **under the current charter**. (A governed switch may escalate; see §5.)

---

## 3) Error taxonomy & evidence map (canonical codes)

| Class           | Code (prefix `s9.*`)                                                                                        | Typical trigger                                  | Evidence in bundle                       |
| --------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------- |
| Structural      | `s9.3.schema_violation.*`                                                                                   | JSON-Schema mismatch                             | `schema_checks.json`                     |
| Keys/FK         | `s9.3.pk_duplicate.*`, `s9.3.fk_iso_breach`                                                                 | PK dup; ISO not in canonical set                 | `key_constraints.json`                   |
| Partition echo  | `s9.3.partition_echo_mismatch`                                                                              | Row echo ≠ directory tokens                      | `schema_checks.json` (echo section)      |
| RNG envelope    | `s9.5.ERR_RNG_ALGO_MISMATCH`, `s9.5.ERR_RNG_SEED_MISMATCH`                                                  | Audit algo/seed mismatch                         | `rng_accounting.json` (header)           |
| Draw accounting | `s9.5.ERR_COUNTER_ADVANCE_MISMATCH[ℓ]`, `s9.5.ERR_ADJACENCY_BREAK[ℓ]`, `s9.5.ERR_NONCONSUMING_HAS_DRAWS[ℓ]` | Counter math / adjacency / zero-draw violations  | `rng_accounting.json` (per-label)        |
| Replay          | `s9.5.ERR_REPLAY_MISMATCH[ℓ]`                                                                               | Gumbel/Dirichlet payload regen mismatch          | `rng_accounting.json` (reproducer tuple) |
| Equalities      | `s9.4.mass_not_conserved`                                                                                   | $\sum_i n_{m,i}\ne N^{\text{raw}}_m$        | `diffs/conservation.csv`                 |
| Coverage/home   | `s9.4.country_set_coverage`, `s9.4.country_set_home_mismatch`, `s9.4.country_set_rank_contiguity`           | Egress outside set; home ISO mismatch; rank gaps | `diffs/coverage.csv`                     |
| Sequencing      | `s9.4.site_id_mismatch`, `s9.4.sequence_finalize_coverage`                                                  | `site_id` bijection; finalize coverage           | `diffs/sequence.csv`                     |
| Corridors       | `s9.6.corridor_breach_*`                                                                                    | Hurdle/LRR/sparse/ZTP out-of-band                | `metrics.csv` (with thresholds)          |
| S9.7 writer     | `s9.7.index_schema_violation`, `s9.7.bundle_write_error`, `s9.7.sha_mismatch_postwrite`                     | Index invalid / I/O / digest self-check          | Pack step logs; `index.json` presence    |

> **Minimum set invariant (diagnostics on early fail):** Even if an early step fails, S9 **must still emit** all minimum files named in S9.7. When a step never ran, write a **stub** file with `{ "evaluated": 0, "notes": "not evaluated due to prior failure <code>" }`. This preserves S9.7’s index contract.

---

## 4) Canonical decision routine (single source of truth)

```pseudo
function s9_8_decide_and_emit(results, pack_bundle):
    # results: hard gates and soft warnings collected from S9.3–S9.6
    with results as {
      schema_pass, keys_pass, fk_pass,
      rng_envelope_pass, rng_accounting_pass, rng_replay_pass,
      eq_conservation_pass, eq_coverage_pass, eq_site_id_pass,
      corridors_pass,
      soft_warnings:list[code]
    }:

        # Prepare diagnostics stubs for any steps that did not execute
        ensure_minimum_payloads_exist_as_stubs_if_missing()

        # Structural gates (ordered precedence)
        if not (schema_pass and keys_pass and fk_pass):
            pack_bundle(write_flag=false, failure_class="structural", soft_warnings=soft_warnings)
            return EXIT_STRUCTURAL_FAIL

        if not (rng_envelope_pass and rng_accounting_pass and rng_replay_pass):
            pack_bundle(write_flag=false, failure_class="rng_lineage", soft_warnings=soft_warnings)
            return EXIT_RNG_FAIL

        if not (eq_conservation_pass and eq_coverage_pass and eq_site_id_pass):
            pack_bundle(write_flag=false, failure_class="equalities", soft_warnings=soft_warnings)
            return EXIT_EQUALITIES_FAIL

        if not corridors_pass:
            pack_bundle(write_flag=false, failure_class="corridors", soft_warnings=soft_warnings)
            return EXIT_CORRIDOR_FAIL

        # Success path: pack & sign (S9.7); flag contents == SHA256(bundle.zip)
        H = pack_bundle(write_flag=true, failure_class=null, soft_warnings=soft_warnings)
        emit_summary(stdout, { status:"PASS", sha256:H, soft_warnings })
        return EXIT_OK
```

**Binding notes:**

* `pack_bundle(write_flag=…)` is the S9.7 canonical pack-and-sign. On `true` it **must** write `_passed.flag` whose contents equal `SHA256(bundle.zip)`. On `false` it **must not** write the flag.
* Precedence is fixed: **structural → RNG → equalities → corridors**. The first failing class selects the **exit code**, but all encountered error codes are still recorded in the bundle artefacts.

---

## 5) Idempotence, determinism & concurrency

* **Idempotence:** Same inputs ⇒ byte-identical `bundle.zip` (see S9.7 canonical ZIP) ⇒ identical `_passed.flag`.
* **Immutable target:** For a `fingerprint={F}` there are only two valid terminal states: **(a)** `bundle.zip + _passed.flag` or **(b)** `bundle.zip` only. No third state. **Never overwrite** a flag for `{F}`.
* **Concurrency guard:** Write to `*.tmp`, `fsync`, then **atomic rename**. Always write `_passed.flag` **last** and **only** on PASS.
* **Policy switch (optional):** A governed config may promote selected soft warnings to **hard fails** (e.g., `treat_warnings_as_errors=true` or a list of `warn_codes_to_fail`). S9.8 must read this strictly from config (not code).

---

## 6) Consumer contract (1B reaffirmed)

Before reading `outlet_catalogue(seed,fingerprint)`:

1. Compute `SHA256(bundle.zip)` in `…/validation/fingerprint={fingerprint}/`.
2. Read `_passed.flag` and require **text equality** with the computed digest.
3. If either file missing or digests differ ⇒ **abort consumption**.
4. Remember: **cross-country order lives only in `country_set.rank`**; egress never encodes it.

---

## 7) Conformance tests (negative & edge)

1. **Schema failure path:** Put `site_id="ABC123"` in egress. Expect `s9.3.schema_violation.outlet_catalogue`; bundle written with diagnostics stubs for later steps; **no flag**; `EXIT_STRUCTURAL_FAIL`. ✔︎
2. **RNG counter drift:** Add +1 to `rng_trace_log.draws` for `gumbel_key`. Expect `ERR_COUNTER_ADVANCE_MISMATCH[gumbel_key]`; bundle-only; `EXIT_RNG_FAIL`. ✔︎
3. **Conservation breach:** Two rows realised but `final_country_outlet_count=3`. Expect `s9.4.mass_not_conserved`; bundle-only; `EXIT_EQUALITIES_FAIL`. ✔︎
4. **Corridor breach:** Force ZTP acceptance to 0.1 with corridor `[0.3,0.7]`. Expect `s9.6.corridor_breach_ztp_rate`; bundle-only; `EXIT_CORRIDOR_FAIL`. ✔︎
5. **Soft warn only:** Conservation exact, but tiny L1 drift flagged as warning under policy (not escalated). Expect **PASS**, bundle+flag, `soft_warnings` listed. ✔︎
6. **Idempotence:** Re-run S9 end-to-end with identical inputs on different hosts; expect byte-identical ZIP digest and same `_passed.flag`. ✔︎
7. **Concurrency:** Kill process mid-pack; only `*.tmp` present; no flag. Next run finishes and produces valid bundle+flag. ✔︎

---

## 8) Operator runbook (remediation pointers)

* **Structural:** fix schemas/regex, repair partition echoes/PK/FK; re-emit and re-run S9.
* **RNG lineage:** ensure required labels exist; correct draw accounting / adjacency; fix replay payloads.
* **Equalities:** debug S7 integerisation & S8 write path; ensure `country_set` is the **sole** cross-country order carrier.
* **Corridors:** examine governed thresholds; investigate model drift (hurdle/ZTP/sparsity); adjust config (not code) if policy dictates.

---

## 9) CI wiring (exit codes & logs)

* `EXIT_OK = 0`
* `EXIT_STRUCTURAL_FAIL = 10`
* `EXIT_RNG_FAIL = 20`
* `EXIT_EQUALITIES_FAIL = 30`
* `EXIT_CORRIDOR_FAIL = 40`

**Always** write the bundle (`index.json`, `schema_checks.json`, `key_constraints.json`, `rng_accounting.json`, `metrics.csv`, `diffs/*`). S9.7 computes and writes `_passed.flag` **only** on PASS.

---

## 10) Optional convenience artefact (record-only)

You **may** include `decision_summary.json` (kind=`"summary"`) in the ZIP, containing:

```json
{
  "lineage": { "seed": "...", "parameter_hash": "...", "manifest_fingerprint": "...", "run_id": "..." },
  "status": "PASS|FAIL",
  "failure_class": "structural|rng_lineage|equalities|corridors|null",
  "sha256_bundle": "…",     // present only on PASS
  "soft_warnings": ["code1","code2"],
  "error_counts": { "s9.3.schema_violation.outlet_catalogue": 1, "s9.4.mass_not_conserved": 0, ... }
}
```

Not a gate; purely for operator UX. Do **not** make it required.

---

**Summary.** S9.8 freezes a binary gate: **any hard-fail ⇒ bundle-only; full pass ⇒ bundle + `_passed.flag` (flag = `SHA256(bundle.zip)`)**. It also mandates deterministic packaging, immutable end states, and consumer preflight, aligning perfectly with S9.1–S9.7 and your artefact registry/dictionary.

---

# S9.9 — Hand-off to 1B (consumer contract, implementation-ready)

This section fixes the **exact gate** 1B must satisfy before consuming 1A egress, the **preflight**, **join rules** for cross-country order, **scope hygiene**, **consumer error taxonomy**, and **reference loaders**. It binds to the locked S9, the artefact registry, the data dictionary, and schemas.

---

## 1) Purpose & immutable contract (what S9.9 governs)

1B is authorised to read `outlet_catalogue(seed, fingerprint)` **iff** both hold:

1. `bundle.zip` exists at
   `data/layer1/1A/validation/fingerprint={fingerprint}/bundle.zip`, and
2. `_passed.flag` exists **in the same folder** and its **ASCII contents equal** `SHA256(bundle.zip)` (64-char lowercase hex).

> **Mandatory policy:** Inter-country order is **not** encoded in egress. 1B **must** obtain country order **only** by joining `country_set.rank`.

---

## 2) Inputs & authorities (consumption scope)

* **Egress (immutable):**
  `outlet_catalogue/seed={seed}/fingerprint={fingerprint}`
  schema `schemas.1A.yaml#/egress/outlet_catalogue`.
  **PK & physical order:** `(merchant_id, legal_country_iso, site_order)`.
  **No inter-country order** present here.

* **Country order (sole authority):**
  `country_set/seed={seed}/parameter_hash={parameter_hash}`
  schema `#/alloc/country_set`, with `rank: 0=home, 1..K` foreign.
  **Only** source of cross-country sequencing.

* **Validation proof:**
  `…/validation/fingerprint={fingerprint}/bundle.zip` and `_passed.flag` (text = `SHA256(bundle.zip)`).
  `index.json` inside the ZIP conforms to the registry-resolved `validation_bundle` index schema (pointer resolved via dictionary; **do not** hardcode).

> **Scope note:** egress is keyed by `(seed, fingerprint)`; order by `(seed, parameter_hash)`. 1B must know both keys and **never** mix scopes.

---

## 3) Mandatory preflight (must run before any read)

Run these steps **in order**; on any failure ⇒ **abort** consumption.

1. **Egress lineage echo.**
   Read any row from `outlet_catalogue(seed,fingerprint)` and assert
   `row.manifest_fingerprint == fingerprint`.

2. **Validation proof (binary gate).**
   Read `bundle.zip` bytes → compute `H' = SHA256(bytes)`;
   read `_passed.flag` text → `H_flag`. Require `H' == H_flag`.

3. **Country-set presence for the intended parameters.**
   Assert `country_set(seed, parameter_hash)` exists. 1B must **never** infer order.

4. **(Recommended defence-in-depth)** Validate `index.json` inside the bundle against the registered bundle-index schema and log a warning on mismatch (does **not** override step 2).

---

## 4) Join semantics (obtaining cross-country order)

**Join key:** `(merchant_id, legal_country_iso)`
**Scopes:** egress `(seed,fingerprint)`; country_set `(seed,parameter_hash)`.

**Join rule:** **inner join** egress → country_set. S9.4 guarantees coverage, so any miss indicates corruption or scope mix.

**Ordering convention (if 1B needs ordered output):**

1. `country_set.rank` ascending (0,1,2,…)
2. `site_order` ascending within `(m,i)`
3. Tertiary (display-only): `legal_country_iso` ascending.

**Reference SQL:**

```sql
WITH egress AS (
  SELECT *
  FROM outlet_catalogue
  WHERE seed = :seed AND fingerprint = :fingerprint
),
cset AS (
  SELECT merchant_id, country_iso AS legal_country_iso, rank
  FROM country_set
  WHERE seed = :seed AND parameter_hash = :parameter_hash
)
SELECT
  e.merchant_id,
  e.legal_country_iso,
  c.rank  AS country_rank,     -- authoritative cross-country order
  e.site_order,                -- within-country sequence
  e.site_id,
  e.raw_nb_outlet_draw,
  e.single_vs_multi_flag,
  e.home_country_iso
FROM egress e
JOIN cset  c
  ON (e.merchant_id = c.merchant_id AND e.legal_country_iso = c.legal_country_iso)
ORDER BY e.merchant_id, c.rank, e.site_order;
```

> **Never** emulate cross-country order from ISO lexicographic order, file order, or any egress pattern.

---

## 5) Recommended materialisation (downstream table schema)

If 1B persists a joined view:

* **Required lineage columns:** `seed`, `fingerprint`, `parameter_hash`
* **Keys/fields:** `merchant_id`, `legal_country_iso`, `country_rank`, `site_order`, `site_id`, plus required outlet attributes
* **Primary key:** `(merchant_id, legal_country_iso, site_order)` **scoped by** `{seed, fingerprint}`
* **Checks:** `country_rank >= 0`; `site_order >= 1`; `site_id ~ '^[0-9]{6}$'`
* **Provenance:** store exact `parameter_hash` used for the join (guard against scope drift)

---

## 6) Caching & scope hygiene

* It is valid to **cache** `country_set(seed, parameter_hash)` and reuse it across multiple `fingerprint`s sharing the same `(seed, parameter_hash)`.
* It is **invalid** to join egress for one `parameter_hash` to a `country_set` from another. Always thread both keys through 1B pipelines.
* If multiple parameter sets are supported, keep per-`parameter_hash` caches **namespaced** to avoid accidental mixing.

---

## 7) Consumer error taxonomy (machine codes & actions)

| Code                                  | Trigger                                                        | Action                            |
| ------------------------------------- | -------------------------------------------------------------- | --------------------------------- |
| `consumer.flag_missing`               | `_passed.flag` absent                                          | Abort; request S9 to run.         |
| `consumer.flag_mismatch`              | `SHA256(bundle.zip) ≠ contents(_passed.flag)`                  | Abort; possible tamper/staleness. |
| `consumer.egress_lineage_mismatch`    | `manifest_fingerprint` in sampled row ≠ `fingerprint`          | Abort; wrong partition.           |
| `consumer.country_set_missing`        | Missing `country_set(seed, parameter_hash)`                    | Abort; cannot recover order.      |
| `consumer.scope_mismatch`             | Join uses `country_set` from different `seed`/`parameter_hash` | Abort; scope violation.           |
| `consumer.invalid_join_multiplicity`  | Join creates dup/missing rows (should be impossible post-S9)   | Abort; report upstream.           |
| `consumer.order_inferred_from_egress` | Sorting/logic uses egress to imply cross-country order         | Block; policy violation.          |
| `consumer.bundle_missing`             | `bundle.zip` missing at expected path                          | Abort; request S9 to run.         |
| `consumer.index_schema_warn`          | `index.json` fails schema (optional defence check)             | Warn; gate still depends on flag. |

---

## 8) Reference preflight loader (language-agnostic)

```pseudo
function load_L1A_for_1B(seed, fingerprint, parameter_hash):
  # (1) lineage echo
  probe := read_one("outlet_catalogue", seed, fingerprint)
  if probe.manifest_fingerprint != fingerprint:
      raise "consumer.egress_lineage_mismatch"

  # (2) validation proof
  B  := read_bytes("validation/fingerprint={fingerprint}/bundle.zip")
  if B is None: raise "consumer.bundle_missing"
  H' := sha256_hex(B)
  F  := read_text("validation/fingerprint={fingerprint}/_passed.flag")
  if F is None: raise "consumer.flag_missing"
  if H'.strip() != F.strip(): raise "consumer.flag_mismatch"

  # (3) authoritative order
  CST := read_table("country_set", seed, parameter_hash)
  if CST is None: raise "consumer.country_set_missing"

  # (4) join (inner) and optional materialisation
  OUT := read_table("outlet_catalogue", seed, fingerprint)
  T   := inner_join(OUT, CST, keys=("merchant_id","legal_country_iso"))
  # Optional: enforce PK & checks here
  return T
```

---

## 9) Streaming join (large-scale pattern, optional)

For very large partitions, 1B can do a **sort-merge** by `(merchant_id, legal_country_iso)` with a broadcast/cache of `CST` keyed by `(merchant_id, country_iso)`. Ordering of the output should be `(merchant_id, rank, site_order)` as per §4.

---

## 10) Conformance tests (consumer-side)

1. **Happy path:** valid bundle+flag; correct `(seed,fingerprint,parameter_hash)` → loader returns rows ordered by `(rank, site_order)`. ✔︎
2. **Missing flag:** remove `_passed.flag` → `consumer.flag_missing`; no read. ✔︎
3. **Flag mismatch:** alter one nibble in `_passed.flag` → `consumer.flag_mismatch`; no read. ✔︎
4. **Wrong parameter_hash:** join with a different `parameter_hash` → `consumer.scope_mismatch` (or `consumer.country_set_missing`). ✔︎
5. **Order inference attempt:** remove join and sort by ISO → detect via guard/policy → `consumer.order_inferred_from_egress`. ✔︎
6. **Multiplicity guard:** corrupt CST to duplicate `(m,i)` → `consumer.invalid_join_multiplicity`. ✔︎

---

## 11) Operational notes for 1B

* **Defence-in-depth:** Even with S9 guarantees, 1B must re-hash the bundle and compare to `_passed.flag`. This prevents stale or tampered reads.
* **Observability:** Log `{seed, fingerprint, parameter_hash, sha256_bundle}` for each successful load.
* **Immutability:** Egress/validation paths are read-only. If re-loading later, **re-run the preflight**; do not trust previously cached checks.
* **Ordering reminder:** Always obtain cross-country order from `country_set.rank`.

---

### Why this is “100%”

* Binary **gate** defined unambiguously (bundle digest equals `_passed.flag`).
* Exact **preflight** and **join** semantics; strict **scope hygiene**.
* Clear **consumer errors** and **reference loaders** (SQL & pseudocode).
* Conformance tests and operational guidance, aligned with S9.1–S9.8 and your registry/dictionary.

---

# S9.10 — Numeric-determinism checks (policy enforcement, implementation-ready)

This section converts the governed numeric policy for 1A (binary64, **FMA off**, **serial reductions**, **Q8 residual quantisation**) into **executable validations**. It consumes artefacts already written in S5/S7 and the S9 RNG/event evidence, emits **hard pass/fail** outcomes, and writes machine-readable diagnostics into the **validation bundle** (S9.7). Any failure here is a **hard gate** per S9.8 (bundle only; no `_passed.flag`).

---

## 1) Scope & contract

**S9.10 proves that:**

1. **S5 cache invariants (currency → country weights):** renormalisations and sparse equal-split respect the governed arithmetic (**IEEE-754 binary64**, ties-to-even, no FMA), using **serial** (fixed-order) compensated sums; totals hit **sum-to-one** within policy.

2. **S7 Dirichlet + LRR invariants (per merchant):** event-logged gamma vectors normalise correctly under the governed reducer; **Q8-quantised residuals** reproduce the **persisted residual values and residual ranks** exactly, which in turn fixes the LRR integerisation order.

3. **Environment coherence:** the run’s manifest/registry declares the **same numeric policy digests** the validator expects (e.g., `numeric_env_sha256`, `residual_quantisation_policy_sha256`). Any mismatch is a **hard fail**.

**Bundle outputs (S9.7):**

* `metrics.csv` rows for S5 sum-to-one deltas, sparse equal-split max error, per-merchant S7 sum-to-one deltas, and residual-rank reproducibility rate.
* `diffs/*` CSVs for any violations (keys below).
* `rng_accounting.json` header augmented with a `"numeric_policy"` block (digests, compile flags, FTZ/DAZ).

**Hard-fail rule:** Any check in §3 fails ⇒ **withhold** `_passed.flag` (S9.8). The bundle still materialises.

---

## 2) Governing definitions (normative)

### 2.1 Arithmetic model (binding)

All numerics that **affect ordering/integerisation** execute in IEEE-754 **binary64**, **roundTiesToEven**, **FMA disabled**, **no FTZ/DAZ**, and **serial reductions** in a fixed iteration order.

We denote correctly-rounded binary64 evaluation of an expression $\psi$ by $\mathrm{R}_{64}[\psi]$. Multiplication/addition (to prevent accidental FMA):

* `mul(a,b)  = R64[a*b]`
* `add(x,y)  = R64[x+y]`
* `fma_off(a,b,c) = R64( R64[a*b] + c )`

### 2.2 Deterministic reducers & quantiser

**Serial Neumaier reducer (fixed order):** for $v_1,\ldots,v_m$,

* $S=0,\,c=0$;
* for each $v$ in the **specified** order:

  * $t=S+v$;
  * $c \mathrel{+}= (|S|\ge|v| ? (S-t+v) : (v-t+S))$;
  * $S=t$;
* return $S+c$.

**Q8 residual quantiser (ties-to-even):**

* Let $K = \mathrm{binary64}(100000000.0)$.
* $Q_8(x) = \mathrm{R}_{64}\!\big(\mathrm{R}_{64}(x\cdot K) / K\big),\; x\in[0,1).$

**Residual-rank sort key (S7/LRR):**

* Sort by $(\textbf{residual} \downarrow,\ \textbf{ISO} \uparrow)$.
* **Note:** This matches S9.2/S9.4’s deterministic rule (no `rank` in the tie-break).

**Fixed iteration orders used below:**

* S5 sums: **ISO ascending** within a currency’s eligible countries.
* S7 sums & residual construction: **`country_set.rank` ascending**, then ISO ascending (only for the *reduction* order; sorting for ranks uses the key above).

---

## 3) Mathematical statements (what is checked)

### 3.1 S5 cache groups (per currency $\kappa$)

Let $(w^{(\kappa)}_i)_{i=1}^D$ be the stored weight vector over the $D$ eligible countries for currency $\kappa$.

1. **Sum-to-one (governed reducer):**

$$
\delta_\kappa = \Big|\,1 - \sum_{i=1}^D w^{(\kappa)}_i \Big| \le 10^{-12},
$$

with **serial Neumaier** in **ISO asc**. Record $\delta_\kappa$.

2. **Sparse equal-split (only if `sparse_flag(κ)=1`):**

$$
\epsilon_\kappa = \max_i \Big|\, w^{(\kappa)}_i - \tfrac{1}{D} \Big| \le 10^{-12}.
$$

Record $\epsilon_\kappa$. Any $\kappa$ failing either bound ⇒ **hard fail**.

### 3.2 S7 Dirichlet & residual-rank (per merchant $m$)

For $C_m$ the legal countries (from `country_set`) and `DIR_EVT[m]` the single `dirichlet_gamma_vector` event (when $|C_m|>1$), with aligned arrays (`country_isos`, `weights`, `gamma_raw`):

1. **Dirichlet normalisation (event contract):**

$$
\bigg| 1 - \sum_{i\in C_m} w_i \bigg| \le 10^{-6},
$$

reduced by **serial Neumaier** in **rank asc then ISO asc**. (Record the tighter internal re-sum too; gate on $10^{-6}$.)

2. **Residual value & rank reproducibility (Q8):**

* Let $N^{\text{raw}}_m$ be the merchant constant from egress.
* $a_i = \mathrm{R}_{64}[N^{\text{raw}}_m \cdot w_i],\quad f_i=\lfloor a_i\rfloor,\quad r_i = Q_8(a_i - f_i)$.
* **Value check:** persisted `RES_CACHE[m,i].residual` **bit-equals** $r_i$.
* **Rank check:** sorting countries by $(r_i \downarrow, \text{ISO} \uparrow)$ must reproduce the persisted `residual_rank` $1,2,\ldots$.
* Any mismatch ⇒ **hard fail** with concrete diffs.

3. **Single-country edge:** If $|C_m|=1$: require **one** residual record with `residual=0.0` and `residual_rank=1`. (No Dirichlet event required.)

---

## 4) Reference validator (language-agnostic pseudocode)

```pseudo
INPUTS
  # S5
  S5_WEIGHTS[κ]: array[(iso, weight)]
  SPARSE_FLAG[κ]: bool
  # S7
  DIR_EVT[m]: { country_isos[], weights[], gamma_raw[] }     # present iff |C_m|>1
  RES_CACHE[m,i]: { residual: float64, residual_rank: int }
  # Egress for Nraw
  OUTLET: outlet_catalogue(seed, fingerprint)
  # Country sets (order)
  CSET[m]: array[(iso, rank)]    # authoritative
  # Policy digests (declared by producer manifest/registry)
  DIGEST.expected: {
     numeric_env_sha256,
     residual_quantisation_policy_sha256
  }

HELPERS
  sum_comp(values, order_by):  # serial Neumaier in deterministic order
  Q8(x):                       # R64(R64(x*K)/K) with K = binary64(1e8)
  Nraw(m):                     # merchant-constant from OUTLET (home row)

# --- 0) Environment coherence (hard gate)
assert manifest_has_digest("numeric_env", DIGEST.expected.numeric_env_sha256),
       "s9.10.numeric_env_mismatch"
assert manifest_has_digest("residual_quantisation_policy",
                           DIGEST.expected.residual_quantisation_policy_sha256),
       "s9.10.numeric_env_mismatch"

# --- 1) S5 checks
for κ in S5_WEIGHTS:
    W = S5_WEIGHTS[κ]                         # [(iso, w), ...]
    δ = abs( 1.0 - sum_comp([w for (_,w) in W], order_by=ISO_ASC) )
    record_metric("s5.sum_to_one_delta", κ, δ, threshold=1e-12, evaluated=1)
    if δ > 1e-12:
        write_csv_append("diffs/s5_sum_to_one.csv", [κ, δ])
        fail("s9.10.s5.sum_to_one_violation")

    if SPARSE_FLAG[κ]:
        D = len(W)
        ε = max_i abs(W[i].w - (1.0 / D))
        record_metric("s5.sparse_equal_split_maxerr", κ, ε, threshold=1e-12, evaluated=1)
        if ε > 1e-12:
            write_csv_append("diffs/s5_sparse_equal_split.csv", [κ, ε, D])
            fail("s9.10.s5.equal_split_violation")
    else:
        record_metric("s5.sparse_equal_split_maxerr", κ, 0.0, threshold=1e-12, evaluated=0)

# --- 2) S7 checks
ok_count = 0; tot = 0
for m in merchants_in(OUTLET):
    C = sort(CSET[m], by=(rank ASC, iso ASC))      # authoritative order for reductions
    tot += 1
    if len(C) == 1:
        (i, _) = C[0]
        cache = RES_CACHE[m,i]
        if not (cache.residual == 0.0 and cache.residual_rank == 1):
            write_csv_append("diffs/s7_single_country.csv", [m, i, cache.residual, cache.residual_rank])
            fail("s9.10.s7.single_country_residual_event_missing")
        ok_count += 1
        continue

    if DIR_EVT[m] is None or not aligns(DIR_EVT[m].country_isos, C):
        write_csv_append("diffs/s7_dirichlet_alignment.csv", [m, "missing_or_misaligned"])
        fail("s9.10.s7.dirichlet_event_missing_or_misaligned")

    W = reorder(DIR_EVT[m].weights, to_order=C)
    δm = abs( 1.0 - sum_comp(W, order_by=RANK_ASC_THEN_ISO) )
    record_metric("s7.dirichlet_sum_to_one_delta", m, δm, threshold=1e-6, evaluated=1)
    if δm > 1e-6:
        write_csv_append("diffs/s7_dirichlet_sum_to_one.csv", [m, δm])
        fail("s9.10.s7.dirichlet_sum_to_one_violation")

    Nr = float64(Nraw(m))
    A  = [ R64(Nr * wi) for wi in W ]
    F  = [ floor(ai)     for ai in A ]
    Rq = [ Q8( R64(ai - fi) ) for (ai,fi) in zip(A,F) ]

    # Rank by (residual desc, ISO asc)
    ORDER = argsort(enumerate(C), key=( -Rq[idx], C[idx].iso ))
    for k, (idx, (iso, _rank)) in enumerate(ORDER, start=1):
        cache = RES_CACHE[m, iso]
        if not bit_equal(cache.residual, Rq[idx]):
            write_csv_append("diffs/s7_residual_value.csv", [m, iso, as_hex(cache.residual), as_hex(Rq[idx])])
            fail("s9.10.s7.residual_value_mismatch")
        if cache.residual_rank != k:
            write_csv_append("diffs/s7_residual_rank.csv", [m, iso, cache.residual_rank, k])
            fail("s9.10.s7.residual_rank_mismatch")
    ok_count += 1

pass_fraction = ok_count / tot
record_metric("s7.residual_rank_repro_rate", "GLOBAL", pass_fraction, threshold=1.0, evaluated=1)
# success if we didn't fail; S9.7 will package metrics & diffs; S9.8 gates the flag
```

**Notes**

* We **do not** draw new randomness; we only use logged `dirichlet_gamma_vector` payloads plus egress constants.
* “Exact match” for residual values is **bit-equality** of binary64 after Q8. Any decimal round-trip would have been caught by S9.3 schema checks.

---

## 5) Error taxonomy (machine codes & evidence)

| Code                                             | Meaning                                                                                    | Evidence written (bundle)                                            |
| ------------------------------------------------ |--------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| `s9.10.numeric_env_mismatch`                     | Producer manifest/registry digests don’t match validator’s expected numeric policy.        | `metrics.csv` note + `index.json.notes` policy digests               |
| `s9.10.s5.sum_to_one_violation`                  | Some currency $\kappa$ fails $\delta_\kappa \le 1e{-12}$.                                  | `diffs/s5_sum_to_one.csv` (κ, δ)                                     |
| `s9.10.s5.equal_split_violation`                 | Sparse equal-split max error $>1e{-12}$.                                                   | `diffs/s5_sparse_equal_split.csv` (κ, maxerr, D)                     |
| `s9.10.s7.dirichlet_event_missing_or_misaligned` | Dirichlet event missing or its `country_isos` misaligned with `country_set(rank,iso)`.     | `diffs/s7_dirichlet_alignment.csv`                                   |
| `s9.10.s7.dirichlet_sum_to_one_violation`        | ($1-\sum w_i > 1e{-6}$) under the governed reducer.                                       | `diffs/s7_dirichlet_sum_to_one.csv` (m, δ)                           |
| `s9.10.s7.residual_value_mismatch`               | Persisted residual ≠ Q8(Nraw·w − floor(Nraw·w)) (bit-equal check).                         | `diffs/s7_residual_value.csv` (m, iso, cache, recomputed)            |
| `s9.10.s7.residual_rank_mismatch`                | Sorting by $(\text{residual}\downarrow,\ ISO\uparrow)$ does not reproduce `residual_rank`. | `diffs/s7_residual_rank.csv` (m, iso, cache_rank, recomputed_rank) |
| `s9.10.s7.single_country_residual_event_missing` | ($C_m = 1$) but residual cache not `0.0/1`.                                               | `diffs/s7_single_country.csv` (m, iso, residual, rank)               |

All are **hard fails** (S9.8). The bundle still materialises; `_passed.flag` is withheld.

---

## 6) Bundle wiring (what S9.7 must package)

Write `metrics.csv` rows (using your bundle schema column order):

* `("s5.sum_to_one_delta", κ, δ, "1e-12", "S5 ISO-asc serial Neumaier", 1)`
* `("s5.sparse_equal_split_maxerr", κ, ε, "1e-12", "only if sparse_flag=1", evaluated)`
* `("s7.dirichlet_sum_to_one_delta", m, δm, "1e-6", "rank→ISO serial Neumaier", 1)`
* `("s7.residual_rank_repro_rate", "GLOBAL", pass_fraction, "1.0", "bit-equal after Q8", 1)`

Emit diffs listed in §5 under `diffs/*.csv` and add them to `index.json`.
Augment `rng_accounting.json` (or a `numeric_policy.json` companion) with:

* `numeric_env_sha256`, `residual_quantisation_policy_sha256`,
* detected runtime toggles (FMA off, FTZ/DAZ off), if captured.

---

## 7) Conformance tests (must pass)

1. **Happy path:** All S5 groups satisfy $\delta_\kappa \le 1e{-12}$; sparse groups have $\epsilon_\kappa \le 1e{-12}$; all merchants reproduce residual values/ranks; **PASS** → bundle+flag. ✔︎
2. **Rounding drift (intentional):** Quantise residuals at 7 dp in a test build → `s9.10.s7.residual_value_mismatch`; **FAIL** (bundle only). ✔︎
3. **Parallel reduction swap:** Replace serial Neumaier with parallel sum → some $\delta_\kappa>1e{-12}$ → `s9.10.s5.sum_to_one_violation`; **FAIL**. ✔︎
4. **FTZ/DAZ on:** Runtime logs FTZ=ON but manifest digest expects OFF → `s9.10.numeric_env_mismatch`; **FAIL**. ✔︎
5. **Single-country omission:** Drop the residual cache row for $|C_m|=1$ → `s9.10.s7.single_country_residual_event_missing`; **FAIL**. ✔︎

---

## 8) Relationship to other S9 gates (no duplication)

* **S9.3**: schema/PK/FK/echo.
* **S9.4**: exact equalities (conservation, coverage, encoder, residual-rank *ordering* using persisted values).
* **S9.5**: RNG lineage, counters, replay spot-checks.
* **S9.6**: corridors.
* **S9.10**: **numeric policy** itself (binary64 + serial reducers + Q8) was respected when producing those persisted values.

---

## 9) Implementation notes (binding)

* Resolve **schema pointers and paths via the registry/dictionary**; do **not** hardcode.
* Use a **precomputed binary64 constant** `K = 100000000.0` for Q8; do not build `10^8` via integer pow at runtime.
* Ensure **array alignment**: if the event lists `country_isos`, the validator must reorder the arrays to match `country_set(rank,iso)` for reductions; then apply the sorting key $(residual\downarrow,\ ISO\uparrow)$ for rank checks.
* Persist **bit patterns** (e.g., `as_hex(float64)`) in diffs for forensic reproducibility.

---

**This locks S9.10**: exact numeric-policy definitions, fixed reduction orders, Q8 quantiser, executable pseudocode, error taxonomy with bundle evidence, metrics wiring, conformance tests, and binding notes — aligned with S9.1–S9.9, the registry/dictionary, and the governed policy digests.

---